"""Review annotations. Linter diagnostics carry 1-based line numbers; search matches carry
0-based line indexes."""
from codeview.core.source import snippet


def _annotation(lines: list[str], line_no: int, note: str) -> str:
    return "\n".join([f"# {note}", *snippet(lines, line_no)])


def lint_annotation(lines: list[str], diag: dict) -> str:
    """diag: {"line": 1-based int, "code": str, "message": str}."""
    return _annotation(lines, diag["line"], f"{diag['code']}: {diag['message']}")


def search_annotation(lines: list[str], match: dict) -> str:
    """match: {"index": 0-based line index, "term": str}."""
    return _annotation(lines, match["index"], f"found {match['term']!r}")
