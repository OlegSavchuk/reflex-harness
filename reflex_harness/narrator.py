"""failure_narrative + error_symbols (SPEC §9.3).

The narrative describes the structural failure pattern only: no identifiers, paths, domain
nouns or test names — those belong in error_symbols. Dev and eval tasks use different
domains, so a narrative that says "refund" or "invoice" hurts cross-domain retrieval.
Narratives are built from the task (seed code, seed failing tests, and for memory the
verified fix), never from an agent's attempts. The call runs validate_narrative and
retries once with the violations.
"""
import ast
import json
import re
from pathlib import Path, PurePosixPath

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_IDENTIFIER_SHAPES = [
    (re.compile(r"[\w.-]+\.py\b"), "file name"),
    (re.compile(r"[/\\]"), "path separator"),
    (re.compile(r"\b[A-Za-z0-9]+_[A-Za-z0-9_]+\b"), "snake_case identifier"),
    (re.compile(r"\b[A-Za-z][a-z0-9]+[A-Z][A-Za-z0-9]*\b"), "CamelCase identifier"),
    (re.compile(r"\b\w+\(\)"), "call syntax"),
]


def forbidden_tokens(repo: Path, allowlist, error_symbols: str) -> set[str]:
    """Lowercased tokens a narrative must not contain: symbols, path parts, defined names."""
    tokens = {s.lower() for s in error_symbols.split()}
    for rel in allowlist:
        p = PurePosixPath(rel)
        tokens.update(part.lower() for part in p.parent.parts)
        tokens.add(p.stem.lower())
        src = repo / rel
        if src.is_file():
            for node in ast.walk(ast.parse(src.read_text())):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    tokens.add(node.name.lower())
    tokens.discard("__init__")
    return tokens


def validate_narrative(text: str, forbidden: set[str]) -> list[str]:
    """Violations (empty = valid). Cheap and deterministic; plural forms count."""
    violations = []
    for rx, label in _IDENTIFIER_SHAPES:
        violations += [f"{label}: {m.group(0)!r}" for m in rx.finditer(text)]
    for word in _WORD.findall(text):
        w = word.lower()
        forms = {w, w[:-1] if w.endswith("s") else w, w[:-2] if w.endswith("es") else w}
        hit = forms & forbidden
        if hit:
            violations.append(f"task term: {word!r}")
    return sorted(set(violations))


NARRATOR_SYSTEM = (
    "You describe the structure of a bug as a reusable pattern, for retrieving similar bugs in "
    "unrelated codebases. You get the original code, the failing tests, the name of the function "
    "the failures point at, and, when known, the diff of a verified fix. Write 2-3 sentences of "
    "plain prose: how the code around the failing function is organized (for example a function "
    "shared by several callers that expect different things, or a function that relies on a "
    "helper or data type defined elsewhere), how the tests fail (for example an error raised "
    "inside the shared function for one caller only, or wrong values with no error), and, if a "
    "verified fix is given, where the defect actually was relative to the failing function (for "
    "example in one of its callers, or in a helper it depends on). Describe the original code "
    "only, never any attempt to fix it. Do not include identifiers, file, module or package "
    "names, paths, test names, exception names, literal values, or any noun about what the "
    'software does. Reply with JSON only: {"narrative": "<2-3 sentences>"}.'
)


def _short(nodeid: str) -> str:
    return nodeid.split("::")[-1]


def _crash_lines(report) -> dict[str, str]:
    out = {}
    for t in report.raw.get("tests", []):
        for stage in ("setup", "call", "teardown"):
            msg = ((t.get(stage) or {}).get("crash") or {}).get("message", "")
            if msg:
                out[t["nodeid"]] = msg.strip().splitlines()[0]
                break
    return out


def task_symbols(focal_name: str, baseline) -> str:
    """Lexical field from the task itself: focal name, seed failing tests, exception types.
    Same construction for memory and eval; never from an agent's edits."""
    syms = [focal_name] + [_short(n) for n in baseline.failed]
    for line in _crash_lines(baseline).values():
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))\b", line)
        if m:
            syms.append(m.group(1))
    return " ".join(dict.fromkeys(syms))


def narrate_task(seed_files: dict[str, str], baseline, focal_name: str, fix_diff: str | None,
                 forbidden: set[str], *, run_id: str, phase: str,
                 attempt_n: int) -> tuple[str, list[str], float]:
    """(narrative, remaining violations, cost) from seed code + seed failing tests (+ the
    verified fix's diff when known: memory building only). Validated; one retry."""
    from . import agent
    crashes = _crash_lines(baseline)
    packet = {"failing_function": focal_name, "code": seed_files,
              "failing_tests": [{"test": _short(n), "error": crashes.get(n, "")} for n in baseline.failed],
              "verified_fix": fix_diff or "not known"}
    msgs = [{"role": "system", "content": NARRATOR_SYSTEM},
            {"role": "user", "content": json.dumps(packet, indent=1)}]
    cost, text, violations = 0.0, "", ["no narrative"]
    for _ in range(2):
        r = agent.call(msgs, run_id=run_id, phase=phase, attempt_n=attempt_n, step="narrative",
                       component="narrator")
        cost += r.cost_usd
        text = ((r.data or {}).get("narrative") or "").strip()
        violations = validate_narrative(text, forbidden) if text else [f"no narrative: {r.error}"]
        if not violations:
            break
        msgs = msgs + [{"role": "assistant", "content": json.dumps({"narrative": text})},
                       {"role": "user", "content": "Rejected for: " + "; ".join(violations)
                        + ". Rewrite without them."}]
    return text, violations, cost
