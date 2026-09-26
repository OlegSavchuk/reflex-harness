"""Test runner (SPEC §11): isolated workspaces, pytest JSON reports, protected verification.

Produces facts only (which tests pass/fail). Never judges strategy.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Protocol

TASKS_DIR = Path(__file__).resolve().parents[1] / "tasks"
LONGREPR_CHARS = 4000  # per failing test, for prompts and focal resolution


class PatchRejected(Exception):
    """Patch touches a path outside the task allowlist. Nothing was written."""


class RunnerError(Exception):
    """Infrastructure failure (no report produced). Missing evidence, not a test failure."""


@dataclass(frozen=True)
class Task:
    task_id: str
    family: str
    split: str
    goal: str
    allowlist: tuple[str, ...]
    diag_cmd: tuple[str, ...]
    protected_cmd: tuple[str, ...]
    root: Path

    @property
    def repo(self) -> Path:
        return self.root / "repo"

    @property
    def protected(self) -> Path:
        return self.root / "protected"


def load_task(task_id: str, tasks_dir: Path = TASKS_DIR) -> Task:
    root = tasks_dir / task_id
    t = json.loads((root / "task.json").read_text())
    return Task(task_id=t["task_id"], family=t["family"], split=t["split"], goal=t["goal"],
                allowlist=tuple(t["allowlist"]), diag_cmd=tuple(t["diag_cmd"]),
                protected_cmd=tuple(t["protected_cmd"]), root=root)


@dataclass
class Workspace:
    task: Task
    path: Path


@dataclass
class TestReport:
    __test__ = False  # not a pytest test class
    passed: list[str]
    failed: list[str]                 # includes setup/teardown errors
    skipped: list[str]
    collection_errors: list[str]      # modules that failed to import/collect
    failures: dict[str, str]          # nodeid -> truncated longrepr
    exit_code: int
    duration_s: float
    timed_out: bool = False
    raw: dict = field(default_factory=dict, repr=False)  # full JSON report (tracebacks for context.py)

    @property
    def all_pass(self) -> bool:
        return (bool(self.passed) and not self.failed and not self.collection_errors
                and not self.timed_out)


@dataclass
class ScriptResult:
    """Output of a diagnostic check script (the `diagnostic` config's first call)."""
    exit_code: int
    output: str          # stdout + stderr, truncated
    duration_s: float
    timed_out: bool = False


class Runner(Protocol):
    def prepare(self, task: Task, state: dict[str, str] | None = None) -> Workspace: ...
    def run(self, ws: Workspace, cmd: tuple[str, ...], timeout_s: float) -> TestReport: ...
    def fork(self, ws: Workspace, n: int) -> list[Workspace]: ...
    def verify(self, ws: Workspace, timeout_s: float) -> TestReport: ...
    def run_script(self, ws: Workspace, source: str, timeout_s: float) -> ScriptResult: ...


def normalize_path(path: str, allowlist: tuple[str, ...]) -> str:
    """Return the allowlisted posix path, or raise PatchRejected."""
    p = PurePosixPath(path.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts:
        raise PatchRejected(f"path escapes workspace: {path!r}")
    norm = str(PurePosixPath(*[part for part in p.parts if part != "."]))
    if norm not in allowlist:
        raise PatchRejected(f"path not in allowlist: {path!r}")
    return norm


def apply_patch(ws: Workspace, patch: dict) -> list[str]:
    """Apply full-file replacements {"files": [{"path", "content"}]}. All-or-nothing."""
    files = patch.get("files") or []
    if not files:
        raise PatchRejected("patch has no files")
    staged = {}
    for f in files:
        norm = normalize_path(f["path"], ws.task.allowlist)
        if norm in staged:
            raise PatchRejected(f"path repeated in patch: {norm!r}")
        staged[norm] = f["content"]
    for norm, content in staged.items():
        target = ws.path / norm
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return sorted(staged)


def snapshot(ws: Workspace) -> dict[str, str]:
    """Contents of every allowlisted file (missing files omitted)."""
    return {p: (ws.path / p).read_text() for p in ws.task.allowlist if (ws.path / p).is_file()}


def state_hash(ws: Workspace) -> str:
    h = hashlib.sha256()
    files = snapshot(ws)
    for p in ws.task.allowlist:
        h.update(p.encode() + b"\0" + (files[p].encode() if p in files else b"<missing>") + b"\0")
    return h.hexdigest()


def _sandbox_env() -> dict[str, str]:
    """Model-written code runs here: pass no credentials, only what Python needs."""
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
    return env


def parse_report(raw: dict, exit_code: int, duration_s: float) -> TestReport:
    passed, failed, skipped, failures = [], [], [], {}
    for t in raw.get("tests", []):
        nodeid, outcome = t["nodeid"], t["outcome"]
        if outcome in ("passed", "xfail", "xfailed"):
            passed.append(nodeid)
        elif outcome == "skipped":
            skipped.append(nodeid)
        else:  # failed, error, xpassed(strict)
            failed.append(nodeid)
            stage = next((t[s] for s in ("setup", "call", "teardown")
                          if t.get(s, {}).get("outcome") == "failed"), {})
            failures[nodeid] = str(stage.get("longrepr", ""))[-LONGREPR_CHARS:]
    collection_errors = [c["nodeid"] for c in raw.get("collectors", [])
                         if c.get("outcome") == "failed"]
    for c in raw.get("collectors", []):
        if c.get("outcome") == "failed":
            failures[c["nodeid"] or "<collection>"] = str(c.get("longrepr", ""))[-LONGREPR_CHARS:]
    return TestReport(passed=sorted(passed), failed=sorted(failed), skipped=sorted(skipped),
                      collection_errors=sorted(collection_errors), failures=failures,
                      exit_code=exit_code, duration_s=duration_s, raw=raw)


class LocalRunner:
    """Workspaces are temp-dir copies of the task repo, outside the project tree."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir

    def _new_dir(self, task: Task) -> Path:
        return Path(tempfile.mkdtemp(prefix=f"reflex-{task.task_id}-", dir=self.base_dir))

    def prepare(self, task: Task, state: dict[str, str] | None = None) -> Workspace:
        path = self._new_dir(task) / "ws"
        shutil.copytree(task.repo, path)
        ws = Workspace(task=task, path=path)
        if state:
            apply_patch(ws, {"files": [{"path": p, "content": c} for p, c in state.items()]})
        return ws

    def fork(self, ws: Workspace, n: int) -> list[Workspace]:
        out = []
        for _ in range(n):
            path = self._new_dir(ws.task) / "ws"
            shutil.copytree(ws.path, path)
            out.append(Workspace(task=ws.task, path=path))
        return out

    def run(self, ws: Workspace, cmd: tuple[str, ...], timeout_s: float) -> TestReport:
        report_file = ws.path.parent / "report.json"
        report_file.unlink(missing_ok=True)
        argv = [sys.executable, "-m", *cmd, "-q", "-p", "no:cacheprovider",
                "--json-report", f"--json-report-file={report_file}"]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(argv, cwd=ws.path, env=_sandbox_env(), capture_output=True,
                                  text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return TestReport(passed=[], failed=[], skipped=[], collection_errors=[],
                              failures={"<timeout>": f"exceeded {timeout_s}s"}, exit_code=-1,
                              duration_s=time.monotonic() - t0, timed_out=True)
        duration = time.monotonic() - t0
        if not report_file.exists():
            raise RunnerError(f"no JSON report (exit {proc.returncode}): "
                              f"{(proc.stderr or proc.stdout)[-500:]}")
        return parse_report(json.loads(report_file.read_text()), proc.returncode, duration)

    def run_script(self, ws: Workspace, source: str, timeout_s: float) -> ScriptResult:
        """Run a model-written check script against the workspace code.

        The script is saved in a scratch dir beside the workspace (kept for the record) and
        executed against a throwaway copy of it, so neither the script nor anything it writes
        can reach the state hash, a snapshot, or a patch. No allowlist applies.
        """
        scratch = ws.path.parent / "scratch"
        scratch.mkdir(exist_ok=True)
        script = scratch / f"check_{len(list(scratch.glob('check_*.py'))) + 1}.py"
        script.write_text(source)
        [copy] = self.fork(ws, 1)
        env = {**_sandbox_env(), "PYTHONPATH": str(copy.path)}
        t0 = time.monotonic()
        try:
            proc = subprocess.run([sys.executable, str(script)], cwd=copy.path, env=env,
                                  capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            return ScriptResult(exit_code=-1, output=f"{out[-LONGREPR_CHARS:]}\n<timeout after {timeout_s}s>",
                                duration_s=time.monotonic() - t0, timed_out=True)
        finally:
            self.cleanup(copy)
        out = (proc.stdout + ("\n" + proc.stderr if proc.stderr else ""))[-LONGREPR_CHARS:]
        return ScriptResult(exit_code=proc.returncode, output=out, duration_s=time.monotonic() - t0)

    def verify(self, ws: Workspace, timeout_s: float) -> TestReport:
        """Protected verification: final source in a fresh copy + protected tests, never in ws."""
        fresh = self.prepare(ws.task, state=snapshot(ws))
        try:
            shutil.copytree(ws.task.protected, fresh.path / "protected")
            return self.run(fresh, ws.task.protected_cmd, timeout_s)
        finally:
            self.cleanup(fresh)

    def cleanup(self, ws: Workspace) -> None:
        shutil.rmtree(ws.path.parent, ignore_errors=True)
