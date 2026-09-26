import pytest

from fitlog.core.pace import pace
from fitlog.report import best_pace


def test_best_pace():
    assert best_pace([(5000, 1500), (10000, 2700)]) == '4:30 /km'


def test_pace_rejects_zero():
    with pytest.raises(ValueError):
        pace(5000, 0)
