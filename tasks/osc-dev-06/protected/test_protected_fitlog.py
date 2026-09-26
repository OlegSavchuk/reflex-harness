import pytest

from fitlog.core.pace import pace
from fitlog.report import best_pace
from fitlog.sessions import _summary, from_manual, from_watch


def test_manual_10k():
    assert from_manual(10.0, 55) == {'km': 10.0, 'pace': '5:30 /km'}


def test_manual_short():
    assert from_manual(3.2, 17) == {'km': 3.2, 'pace': '5:19 /km'}


def test_watch_unchanged():
    assert from_watch({"distance_m": 4000, "elapsed_s": 1000}) == {'km': 4.0, 'pace': '4:10 /km'}


def test_best_pace_unchanged():
    assert best_pace([(3000, 1000), (8000, 2500)]) == '5:12 /km'


def test_pace_still_rejects_zero():
    with pytest.raises(ValueError):
        pace(0, 100)


def from_manual_probe():
    return _summary(5000, 1500)


from_manual_probe.__code__ = from_manual_probe.__code__.replace(co_name="from_manual")


def test_pace_does_not_depend_on_caller():
    assert from_manual_probe() == {'km': 5.0, 'pace': '5:00 /km'}
