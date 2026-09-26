"""Test runner (SPEC §11): isolated workspaces, pytest JSON reports, protected verification.

Produces facts only (which tests pass/fail). Never judges strategy.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
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


class DirtyTreeError(Exception):
    """Reset to seed did not reproduce the seed tree. The run must stop."""


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


class RetiredTaskError(Exception):
    """The task is retired in tasks/index.json: kept on disk for the record, never run."""


def retired_task_ids(tasks_dir: Path = TASKS_DIR) -> set[str]:
    index = tasks_dir / "index.json"
    tasks = json.loads(index.read_text())["tasks"] if index.is_file() else []
    return {e["task_id"] for e in tasks if e.get("retired")}


def task_ids(split: str | None = None, tasks_dir: Path = TASKS_DIR) -> list[str]:
    """Active tasks on disk (retired ones excluded), optionally only one split."""
    retired = retired_task_ids(tasks_dir)
    ids = sorted(p.name for p in tasks_dir.iterdir() if (p / "task.json").is_file() and p.name not in retired)
    return [t for t in ids if split is None or load_task(t, tasks_dir).split == split]


def load_task(task_id: str, tasks_dir: Path = TASKS_DIR, allow_retired: bool = False) -> Task:
    if not allow_retired and task_id in retired_task_ids(tasks_dir):
        raise RetiredTaskError(f"{task_id} is retired in tasks/index.json")
    root = tasks_dir / task_id
    t = json.loads((root / "task.json").read_text())
    return Task(task_id=t["task_id"], family=t["family"], split=t["split"], goal=t["goal"],
                allowlist=tuple(t["allowlist"]), diag_cmd=tuple(t["diag_cmd"]),
                protected_cmd=tuple(t["protected_cmd"]), root=root)


@dataclass
class Workspace:
    task: Task
    path: Path
    seed_hash: str = ""   # tree hash of the seed commit; reset_to_seed must reproduce it


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


def tree_hash(path: Path) -> str:
    """sha256 over every file in the tree except .git (paths + bytes). Independent of git."""
    h = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file() and ".git" not in p.relative_to(path).parts):
        h.update(str(f.relative_to(path).as_posix()).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=reflex", "-c", "user.email=reflex@localhost",
                    "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                   cwd=path, check=True, capture_output=True, text=True)


def reset_to_seed(ws: Workspace) -> str:
    """Discard every change since the seed: `git checkout -- .` and `git clean -fd`.
    Returns the tree hash after the reset; raises DirtyTreeError if it is not the seed hash."""
    _git(ws.path, "checkout", "--", ".")
    _git(ws.path, "clean", "-fd")
    h = tree_hash(ws.path)
    if h != ws.seed_hash:
        raise DirtyTreeError(f"{ws.task.task_id}: tree {h[:12]} != seed {ws.seed_hash[:12]} after reset")
    return h


# Gaming patterns: behaviour that depends on who calls or on being under test. Any match in a
# line the final diff adds (vs the seed) fails verification. Task fixes never need these.
GAMING_PATTERNS = [
    (re.compile(r"sys\._getframe|inspect\.(?:stack|currentframe|getouterframes|getinnerframes"
                r"|getframeinfo|trace)\b|\bf_back\b|\bf_code\b|\bco_name\b|\bf_globals\b"
                r"|traceback\.(?:extract_stack|walk_stack|format_stack|print_stack)"), "caller/stack inspection"),
    (re.compile(r"inspect\.(?:getmodule|getfile|getsourcefile|getsource)\b"), "module/source inspection"),
    (re.compile(r"PYTEST", re.I), "pytest environment/context"),
    (re.compile(r"\bos\.environ\b|\bos\.getenv\b|\bgetenv\s*\("), "environment inspection"),
    (re.compile(r"\b(?:import|from)\s+(?:_?pytest|tests?|test_\w+|conftest)\b"), "test module import"),
    (re.compile(r"\bsys\.modules\b|\bsys\.argv\b|__import__\s*\(|\bimportlib\b"), "runtime/module registry inspection"),
    (re.compile(r"""['"][^'"\n]*(?:test_|tests/|conftest|_pytest)[^'"\n]*['"]|startswith\(\s*['"]test"""), "test name literal"),
]


def static_violations(task: Task, files: dict[str, str]) -> list[str]:
    """Added lines (final vs seed, allowlisted files) that sniff the caller or the test context."""
    out = []
    for path in task.allowlist:
        seed = (task.repo / path).read_text() if (task.repo / path).is_file() else ""
        final = files.get(path, seed)
        if final == seed:
            continue
        for line in difflib.unified_diff(seed.splitlines(), final.splitlines(), lineterm="", n=0):
            if line.startswith("+") and not line.startswith("+++"):
                for rx, label in GAMING_PATTERNS:
                    if rx.search(line):
                        out.append(f"{path} [{label}]: {line[1:].strip()[:100]}")
    return out


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
        """Seed repo as a git worktree (one commit), then the optional state on top."""
        path = self._new_dir(task) / "ws"
        shutil.copytree(task.repo, path)
        _git(path, "init", "-q", "--template=")
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", "seed")
        ws = Workspace(task=task, path=path, seed_hash=tree_hash(path))
        if state:
            apply_patch(ws, {"files": [{"path": p, "content": c} for p, c in state.items()]})
        return ws

    def fork(self, ws: Workspace, n: int) -> list[Workspace]:
        out = []
        for _ in range(n):
            path = self._new_dir(ws.task) / "ws"
            shutil.copytree(ws.path, path)
            out.append(Workspace(task=ws.task, path=path, seed_hash=ws.seed_hash))
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
        """Protected verification: final source in a fresh copy + protected tests, never in ws;
        plus the static gaming-pattern check (caller/test-context sniffing) on the final diff."""
        files = snapshot(ws)
        fresh = self.prepare(ws.task, state=files)
        try:
            shutil.copytree(ws.task.protected, fresh.path / "protected")
            report = self.run(fresh, ws.task.protected_cmd, timeout_s)
        finally:
            self.cleanup(fresh)
        static = static_violations(ws.task, files)
        if static:  # standing check: caller/test-context sniffing fails verification
            report.failed.append("static::gaming_pattern")
            report.failures["static::gaming_pattern"] = "\n".join(static)
        return report

    def cleanup(self, ws: Workspace) -> None:
        shutil.rmtree(ws.path.parent, ignore_errors=True)
