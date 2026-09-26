"""Duration parsing for timesheet entries."""
import re

_DURATION = re.compile(r"^(\d+)h(\d+)m$")


def parse_duration(text: str) -> int:
    """'1h30m' -> 90 (minutes)."""
    m = _DURATION.match(text.strip())
    if not m:
        raise ValueError(f"bad duration: {text!r}")
    return int(m.group(1)) * 60 + int(m.group(1))
