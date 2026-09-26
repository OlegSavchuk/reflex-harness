"""Deadline arithmetic shared by the HTTP client and the job runner."""


def deadline_after(start_ms: int, timeout_ms: int) -> int:
    """Return the absolute deadline in integer milliseconds."""
    if not isinstance(timeout_ms, int):
        raise TypeError(f"timeout_ms must be int, got {type(timeout_ms).__name__}")
    if timeout_ms < 0:
        raise ValueError("timeout_ms must be non-negative")
    return start_ms + timeout_ms
