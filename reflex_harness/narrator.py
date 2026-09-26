"""failure_narrative + error_symbols (SPEC §9.3).

The narrative describes the structural failure pattern only: no identifiers, paths, domain
nouns or test names — those belong in error_symbols. Dev and eval tasks use different
domains, so a narrative that says "refund" or "invoice" hurts cross-domain retrieval.
The narrator call (Gate 6) runs validate_narrative and retries once with the violations.
"""
import ast
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
