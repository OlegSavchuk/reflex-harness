"""Background jobs. Job timeouts are configured in seconds."""
from dataclasses import dataclass

from scheduler.clock import deadline_after


@dataclass(frozen=True)
class Job:
    name: str
    timeout_s: float


def job_deadline(job: Job, started_ms: int) -> int:
    return deadline_after(started_ms, job.timeout_s)


def batch_deadline(jobs: list[Job], started_ms: int) -> int:
    return max((job_deadline(j, started_ms) for j in jobs), default=started_ms)
