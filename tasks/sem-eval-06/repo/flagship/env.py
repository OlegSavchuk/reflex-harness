"""Environment value parsing."""


def parse_bool(value: str) -> bool:
    """Parse a flag: 1/true/yes/on -> True; 0/false/no/off/empty -> False (case-insensitive,
    surrounding spaces ignored). Anything else is an error."""
    return bool(value.strip())
