"""Time intervals in minutes since midnight. Intervals are half-open: [start, end)."""


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """True if [a_start, a_end) and [b_start, b_end) share at least one minute."""
    return a_start <= b_end and b_start <= a_end
