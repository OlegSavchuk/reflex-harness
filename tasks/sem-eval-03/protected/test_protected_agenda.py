from agenda.intervals import overlaps
from agenda.slots import free_slots


def test_touching_intervals_do_not_overlap():
    assert overlaps(540, 600, 600, 660) is False
    assert overlaps(600, 660, 540, 600) is False


def test_real_overlaps():
    assert overlaps(540, 600, 599, 660) is True
    assert overlaps(500, 700, 550, 560) is True


def test_free_slots_between_meetings():
    assert free_slots([(600, 630), (690, 720)], 540, 720, 30) == [540, 570, 630, 660]


def _ov(*args):
    return overlaps(*args)


def test_overlap_outside_a_test_function():
    assert _ov(0, 30, 30, 60) is False
