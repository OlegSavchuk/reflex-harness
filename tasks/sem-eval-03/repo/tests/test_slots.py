from agenda.booking import first_free
from agenda.slots import free_slots


def test_slot_right_after_meeting():
    assert free_slots([(540, 600)], 540, 720, 60) == [600, 630, 660]


def test_first_free_after_meeting():
    assert first_free([(480, 540)], 480, 600, 30) == 540


def test_empty_day():
    assert free_slots([], 540, 600, 60) == [540]
