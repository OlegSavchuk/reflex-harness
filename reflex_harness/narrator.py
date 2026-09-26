"""failure_narrative + error_symbols (SPEC §9.3).

The narrative describes the structural failure pattern only: no identifiers, paths, domain
nouns or test names — those belong in error_symbols. Dev and eval tasks use different
domains, so a narrative that says "refund" or "invoice" hurts cross-domain retrieval.
The narrator call (Gate 6) runs validate_narrative and retries once with the violations.
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
    "You describe how a coding agent's repair attempts failed, as a reusable pattern for "
    "retrieving similar failures in unrelated codebases. Write 2-3 sentences of plain prose "
    "describing the structural pattern only: what kind of code the agent changed (for example a "
    "helper shared by several callers, or local arithmetic inside one function), what happened "
    "to the tests (for example fixing one group broke another and the agent reverted, the same "
    "tests kept failing, or failures shrank without clearing), and whether the edits stayed in "
    "one place. Do not include identifiers, file, module or package names, paths, test names, "
    "exception names, literal values, or any noun about what the software does. "
    'Reply with JSON only: {"narrative": "<2-3 sentences>"}.'
)


def error_symbols(views: list[dict], focal_name: str, reports) -> str:
    """Lexical field: failing test names, exception types, focal and edited function names."""
    syms = [focal_name]
    for v in views:
        syms += v["failing_before"] + v["failing_after"]
        syms += [f.split("::")[-1] for f in v["functions_edited"] if not f.endswith("<module>")]
    for rep in reports:
        for t in rep.raw.get("tests", []):
            for stage in ("setup", "call", "teardown"):
                msg = (t.get(stage) or {}).get("crash", {}).get("message", "")
                m = re.match(r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))\b", msg)
                if m:
                    syms.append(m.group(1))
    return " ".join(dict.fromkeys(s for s in syms if s))


def narrate(views: list[dict], forbidden: set[str], *, run_id: str, phase: str,
            attempt_n: int) -> tuple[str, list[str], float]:
    """(narrative, remaining violations, cost). Validated; one retry with the violations."""
    from . import agent
    user = "ATTEMPTS\n" + json.dumps(views, indent=1)
    msgs = [{"role": "system", "content": NARRATOR_SYSTEM}, {"role": "user", "content": user}]
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
