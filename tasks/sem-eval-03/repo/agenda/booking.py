"""Booking suggestions."""
from agenda.slots import free_slots


def first_free(busy: list[tuple[int, int]], day_start: int, day_end: int, length: int) -> int | None:
    slots = free_slots(busy, day_start, day_end, length)
    return slots[0] if slots else None
