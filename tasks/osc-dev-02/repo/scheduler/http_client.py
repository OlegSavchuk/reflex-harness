"""HTTP request budgets. Timeouts are integer milliseconds."""
from scheduler.clock import deadline_after

DEFAULT_TIMEOUT_MS = 30_000


def request_deadline(now_ms: int, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> int:
    return deadline_after(now_ms, timeout_ms)


def retry_deadlines(now_ms: int, timeout_ms: int, retries: int) -> list[int]:
    out, t = [], now_ms
    for _ in range(retries + 1):
        t = deadline_after(t, timeout_ms)
        out.append(t)
    return out
