"""Source excerpts shared by every annotation kind. Line numbers are 1-based."""


def snippet(lines: list[str], line_no: int, context: int = 1) -> list[str]:
    """Numbered lines around `line_no` (1-based); the target line is marked with '>'."""
    if not 1 <= line_no <= len(lines):
        raise ValueError(f"line {line_no} is outside 1..{len(lines)}")
    lo, hi = max(1, line_no - context), min(len(lines), line_no + context)
    return [f"{'>' if n == line_no else ' '}{n:>3} {lines[n - 1]}" for n in range(lo, hi + 1)]
