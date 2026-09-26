import pytest

from flagship.env import parse_bool
from flagship.flags import enabled_features


def test_parse_bool_values():
    assert parse_bool(" ON ") is True and parse_bool("1") is True
    assert parse_bool("No") is False and parse_bool("") is False


def test_parse_bool_rejects_garbage():
    with pytest.raises(ValueError):
        parse_bool("maybe")


def test_features_other_env():
    assert enabled_features({"FEATURE_A": "Yes", "FEATURE_B": "OFF", "FEATURE_C": "1"}) == ["a", "c"]


def _parse(value):
    return parse_bool(value)


def test_parse_outside_a_test_function():
    assert _parse("false") is False
