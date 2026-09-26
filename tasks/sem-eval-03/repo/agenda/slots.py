"""Free-slot search."""
from agenda.intervals import overlaps


def free_slots(busy: list[tuple[int, int]], day_start: int, day_end: int, length: int,
               step: int = 30) -> list[int]:
    """Start times (minutes) at which a meeting of `length` minutes fits without clashing."""
    return [t for t in range(day_start, day_end - length + 1, step)
            if not any(overlaps(t, t + length, s, e) for s, e in busy)]
