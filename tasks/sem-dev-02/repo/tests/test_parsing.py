import pytest

from timesheet.parsing import parse_duration


def test_rejects_malformed():
    with pytest.raises(ValueError):
        parse_duration("ninety minutes")
