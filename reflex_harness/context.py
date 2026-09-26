"""Context resolution and prompt assembly (SPEC §7.1).

The model sees only what this module hands it. Configs differ only in which blocks are
included; flags come from the config document, never from task-specific logic.

Focal function: pinned once per task from the seed's baseline failing run, before attempt 1,
and reused for every attempt, config and arm (harness bookkeeping, not a hint). Resolution
chain: deepest allowlisted frame in the failing tracebacks ("traceback"); else the task's
context_manifest.json ("manifest", disclosed). If the pinned function no longer exists, it is
re-resolved from the current run ("re-resolved").

Traceback filter: configs without callers/deps see, per failing test, only its name, the
first line of the error, and the focal-function frame. callers/deps configs see the full
traceback. Otherwise caller frames would leak into `focused` and the configs would not differ.
"""
from __future__ import annotations

import ast
import json
from collections import Counter
from dataclasses import dataclass, field

from .runner import TestReport, Workspace

FAILURES_CHARS = 8000   # cap on the failing-test block
SCRIPT_OUTPUT_CHARS = 3000


class ContextError(Exception):
    """No focal function could be resolved (task needs a context_manifest.json)."""


@dataclass(frozen=True)
class Site:
    path: str
    name: str        # enclosing function/class name ("<module>" at top level)
    start: int
    end: int


@dataclass(frozen=True)
class PinnedFocal:
    path: str
    function: str
    source: str      # "traceback" | "manifest"

    def as_doc(self) -> dict:
        return {"path": self.path, "function": self.function, "source": self.source}


@dataclass
class Context:
    config_id: str
    focal: Site
    focal_source: str                       # "traceback" | "manifest" | "re-resolved"
    callers: list[Site] = field(default_factory=list)
    deps: list[Site] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)   # shown, editable, in order
    failures: str = ""
    full_traceback: bool = False


# ---------- ast helpers ----------

def _defs(tree: ast.AST):
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]


def _parse(ws: Workspace, path: str) -> ast.Module | None:
    f = ws.path / path
    try:
        return ast.parse(f.read_text()) if f.is_file() else None
    except SyntaxError:
        return None


def enclosing_def(ws: Workspace, path: str, lineno: int) -> Site | None:
    """Innermost function containing lineno (classes only if no function does)."""
    tree = _parse(ws, path)
    if tree is None:
        return None
    hits = [n for n in _defs(tree) if n.lineno <= lineno <= n.end_lineno]
    funcs = [n for n in hits if not isinstance(n, ast.ClassDef)]
    best = max(funcs or hits, key=lambda n: n.lineno, default=None)
    return Site(path, best.name, best.lineno, best.end_lineno) if best else None


def find_def(ws: Workspace, name: str, paths=None) -> Site | None:
    for path in paths or ws.task.allowlist:
        tree = _parse(ws, path)
        for n in (tree.body if tree else []):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name:
                return Site(path, n.name, n.lineno, n.end_lineno)
    return None


# ---------- focal / callers / deps ----------

def _traceback(report: TestReport, nodeid: str) -> list[dict]:
    for t in report.raw.get("tests", []):
        if t["nodeid"] == nodeid:
            stage = next((t[s] for s in ("setup", "call", "teardown")
                          if t.get(s, {}).get("outcome") == "failed"), {})
            return stage.get("traceback", []) or []
    return []


def _crash(report: TestReport, nodeid: str) -> dict:
    for t in report.raw.get("tests", []):
        if t["nodeid"] == nodeid:
            stage = next((t[s] for s in ("setup", "call", "teardown")
                          if t.get(s, {}).get("outcome") == "failed"), {})
            return stage.get("crash", {}) or {}
    return {}


def _focal_frame(ws: Workspace, report: TestReport, nodeid: str) -> tuple[dict, Site] | None:
    """Deepest frame in an allowlisted file, with its enclosing function."""
    for fr in reversed(_traceback(report, nodeid)):
        if fr.get("path") in ws.task.allowlist:
            site = enclosing_def(ws, fr["path"], fr["lineno"])
            if site:
                return fr, site
    return None


def resolve_focal(ws: Workspace, report: TestReport) -> tuple[Site, str]:
    """Most common deepest source frame across failing tests; else the task manifest."""
    sites = [f[1] for n in report.failed if (f := _focal_frame(ws, report, n))]
    if sites:
        counts = Counter(sites)
        best = max(counts.values())
        return next(s for s in sites if counts[s] == best), "traceback"
    manifest = ws.task.root / "context_manifest.json"
    if manifest.is_file():
        m = json.loads(manifest.read_text())["focal"]
        site = find_def(ws, m["function"], [m["path"]])
        if site:
            return site, "manifest"
    raise ContextError(f"{ws.task.task_id}: no source frame in failing tracebacks and no "
                       f"usable context_manifest.json")


def pin_focal(ws: Workspace, baseline: TestReport) -> PinnedFocal:
    """Resolve the focal once, from the seed's baseline failing run."""
    site, source = resolve_focal(ws, baseline)
    return PinnedFocal(site.path, site.name, source)


def locate_focal(ws: Workspace, pinned: PinnedFocal, report: TestReport) -> tuple[Site, str]:
    """Current line range of the pinned focal; re-resolve only if it no longer exists."""
    tree = _parse(ws, pinned.path)
    hit = next((n for n in (_defs(tree) if tree else []) if n.name == pinned.function), None)
    if hit is not None:
        return Site(pinned.path, hit.name, hit.lineno, hit.end_lineno), pinned.source
    site, _ = resolve_focal(ws, report)
    return site, "re-resolved"


def resolve_callers(ws: Workspace, focal: Site) -> list[Site]:
    """Every function in allowlisted files that calls the focal name (ast Call nodes)."""
    out = []
    for path in ws.task.allowlist:
        tree = _parse(ws, path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                if name == focal.name:
                    site = enclosing_def(ws, path, node.lineno) or Site(path, "<module>", 1, 1)
                    if site != focal and site not in out:
                        out.append(site)
    return out


def _annotation_names(fn: ast.AST) -> set[str]:
    names = set()
    args = fn.args
    for a in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
        if a is not None and a.annotation is not None:
            names |= {n.id for n in ast.walk(a.annotation) if isinstance(n, ast.Name)}
    if fn.returns is not None:
        names |= {n.id for n in ast.walk(fn.returns) if isinstance(n, ast.Name)}
    return names


def resolve_dependencies(ws: Workspace, focal: Site) -> list[Site]:
    """Project functions the focal body calls and classes in its annotations."""
    tree = _parse(ws, focal.path)
    fn = next((n for n in _defs(tree) if n.name == focal.name and n.lineno == focal.start), None)
    if fn is None:
        return []
    names = [n.func.id if isinstance(n.func, ast.Name) else n.func.attr
             for n in ast.walk(fn) if isinstance(n, ast.Call)
             and isinstance(n.func, (ast.Name, ast.Attribute))]
    if not isinstance(fn, ast.ClassDef):
        names += sorted(_annotation_names(fn))
    out = []
    for name in dict.fromkeys(names):
        site = find_def(ws, name)
        if site and site != focal and site not in out:
            out.append(site)
    return out


# ---------- failing-test block ----------

def _first_line(msg: str) -> str:
    return (msg or "").strip().splitlines()[0] if (msg or "").strip() else ""


def failures_block(ws: Workspace, report: TestReport, focal: Site, full: bool) -> str:
    parts = []
    for nodeid in report.failed:
        if full:
            parts.append(f"FAILED {nodeid}\n{report.failures.get(nodeid, '').strip()}")
            continue
        line = f"FAILED {nodeid}\n  error: {_first_line(_crash(report, nodeid).get('message', ''))}"
        ff = _focal_frame(ws, report, nodeid)
        if ff and ff[1] == focal:
            fr = ff[0]
            src = (ws.path / fr["path"]).read_text().splitlines()[fr["lineno"] - 1].strip()
            line += f"\n  at {fr['path']}:{fr['lineno']} in {focal.name}: {src}"
        parts.append(line)
    for nodeid in report.collection_errors:
        parts.append(f"COLLECTION ERROR {nodeid}\n{report.failures.get(nodeid, '').strip()}")
    if report.timed_out:
        parts.append("TIMEOUT: the test run exceeded its time limit")
    text = "\n\n".join(parts)
    return text if len(text) <= FAILURES_CHARS else text[:FAILURES_CHARS] + "\n[truncated]"


# ---------- assembly ----------

def build_context(ws: Workspace, report: TestReport, config: dict, pinned: PinnedFocal) -> Context:
    flags = config["context"]
    focal, source = locate_focal(ws, pinned, report)
    ctx = Context(config_id=config["config_id"], focal=focal, focal_source=source)
    if flags.get("callers"):
        ctx.callers = resolve_callers(ws, focal)
    if flags.get("deps"):
        ctx.deps = resolve_dependencies(ws, focal)
    ctx.full_traceback = bool(flags.get("callers") or flags.get("deps"))
    for site in [focal, *ctx.callers, *ctx.deps]:
        if site.path not in ctx.files:
            ctx.files[site.path] = (ws.path / site.path).read_text()
    if flags.get("error", True):
        ctx.failures = failures_block(ws, report, focal, ctx.full_traceback)
    return ctx


SYSTEM_PATCH = (
    "You fix bugs in a Python repository. You see only the files and test output below; "
    "you cannot open other files or run anything. Reply with JSON only: "
    '{"files": [{"path": "<path>", "content": "<complete new file content>"}], '
    '"note": "<one line: what you changed and why>"}. '
    "Each entry replaces a whole file, so include the complete content. "
    "Only change files shown under EDITABLE FILES. Never edit tests."
)

SYSTEM_CHECK = (
    "You investigate bugs in a Python repository before fixing them. You see only the files "
    "and test output below. Write one short Python script that prints whatever would tell you "
    "the cause of the failures: it will run from the repository root with the project "
    "importable, and you will see its output before writing a fix. It cannot change the "
    'repository. Reply with JSON only: {"script": "<python source>", "note": "<one line: what it checks>"}.'
)


def _site_label(s: Site) -> str:
    return f"{s.name} ({s.path}:{s.start}-{s.end})"


RESET_LINE = ("The code has been reset to its original state. None of the edits described in "
              "the prior attempts below are present.")


def render(ctx: Context, goal: str, prior_attempts: list[str], step: str = "patch",
           check: tuple[str, str] | None = None, reset_note: bool = False) -> list[dict]:
    """Chat messages for one call. step: "patch" | "check" (diagnostic config's first call).
    reset_note: first attempt after a strategy switch (the tree was reset to the seed)."""
    sec = [f"GOAL\n{goal}",
           f"FOCAL FUNCTION\n{_site_label(ctx.focal)}"]
    if ctx.callers:
        sec.append("CALLERS OF THE FOCAL FUNCTION\n" + "\n".join(_site_label(s) for s in ctx.callers))
    if ctx.deps:
        sec.append("DEPENDENCIES OF THE FOCAL FUNCTION\n" + "\n".join(_site_label(s) for s in ctx.deps))
    sec.append("EDITABLE FILES\n" + "\n\n".join(f"--- {p}\n{c.rstrip()}" for p, c in ctx.files.items()))
    if ctx.failures:
        sec.append("FAILING TESTS\n" + ctx.failures)
    if reset_note:
        sec.append(RESET_LINE)
    if prior_attempts:
        sec.append("PRIOR ATTEMPTS ON THIS TASK\n" + "\n".join(prior_attempts))
    if check is not None:
        script, output = check
        out = output if len(output) <= SCRIPT_OUTPUT_CHARS else output[-SCRIPT_OUTPUT_CHARS:]
        sec.append(f"YOUR CHECK SCRIPT\n{script.rstrip()}\n\nITS OUTPUT\n{out.rstrip() or '<no output>'}")
    sec.append("Write the check script now." if step == "check" else "Write the fix now.")
    system = SYSTEM_CHECK if step == "check" else SYSTEM_PATCH
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(sec)}]


# ---------- what an attempt changed (ladder step 7, Jev packet) ----------

def _def_sources(text: str, path: str) -> dict[str, str]:
    """{"path::name": source} for every function/class; "<module>" holds the rest."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {f"{path}::<unparseable>": text}
    out, lines = {}, text.splitlines()
    covered = set()
    for n in _defs(tree):
        if isinstance(n, ast.ClassDef):
            continue
        out[f"{path}::{n.name}"] = "\n".join(lines[n.lineno - 1:n.end_lineno])
        covered.update(range(n.lineno, n.end_lineno + 1))
    out[f"{path}::<module>"] = "\n".join(l for i, l in enumerate(lines, 1) if i not in covered)
    return out


def seed_function_keys(ws: Workspace) -> set[str]:
    """Every function defined in the allowlisted seed files, as "path::name"."""
    keys = set()
    for path in ws.task.allowlist:
        f = ws.task.repo / path
        if f.is_file():
            keys |= {k for k in _def_sources(f.read_text(), path) if not k.endswith("::<module>")}
    return keys


def edited_functions(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Functions whose source differs between two file snapshots ("path::name")."""
    changed = set()
    for path in set(before) | set(after):
        if before.get(path) == after.get(path):
            continue
        b, a = _def_sources(before.get(path, ""), path), _def_sources(after.get(path, ""), path)
        changed |= {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    return sorted(changed)


# ---------- focal region (ladder steps 7 and 9) ----------

@dataclass(frozen=True)
class FocalRegion:
    """Pinned focal + seed functions the failing tests call directly + (implicitly) any
    function the agent creates during the run. Module-level lines of the focal file are
    ignored; module-level edits in other files are outside. Entries are "path::name"."""
    focal: str
    fixed: frozenset          # focal + test-called seed functions
    seed_functions: frozenset

    def inside(self, edited: str) -> bool:
        if edited.endswith("::<module>"):
            return edited.split("::")[0] == self.focal.split("::")[0]
        return edited in self.fixed or edited not in self.seed_functions


def test_called_functions(ws: Workspace, failing: list[str], seed_keys: set[str]) -> set[str]:
    """Seed functions called directly (by name or as a method) inside the failing tests' bodies."""
    by_name: dict[str, set[str]] = {}
    for k in seed_keys:
        by_name.setdefault(k.split("::")[-1], set()).add(k)
    out = set()
    for nodeid in failing:
        path, _, rest = nodeid.partition("::")
        name = rest.split("::")[-1].split("[")[0]
        src = ws.task.repo / path
        if not src.is_file():
            continue
        tree = ast.parse(src.read_text())
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name), None)
        for node in ast.walk(fn) if fn else []:
            if isinstance(node, ast.Call):
                f = node.func
                called = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                out |= by_name.get(called, set())
    return out


def focal_region(ws: Workspace, pinned: PinnedFocal, baseline: TestReport) -> FocalRegion:
    """Built once per run from the seed baseline, like the pinned focal."""
    seed = seed_function_keys(ws)
    focal = f"{pinned.path}::{pinned.function}"
    return FocalRegion(focal=focal, fixed=frozenset({focal} | test_called_functions(ws, baseline.failed, seed)),
                       seed_functions=frozenset(seed))
