from scheduler.clock import deadline_after
from scheduler.http_client import request_deadline, retry_deadlines
from scheduler.jobs import Job, batch_deadline, job_deadline


def test_clock_contract():
    assert deadline_after(10, 5) == 15


def test_http_unchanged():
    assert request_deadline(5, 1000) == 1005
    assert retry_deadlines(1, 10, 1) == [11, 21]


def test_job_millisecond_precision():
    assert job_deadline(Job("t", 0.001), 0) == 1


def test_job_float_not_truncated():
    assert job_deadline(Job("v", 4.35), 0) == 4350


def test_batch_mixed():
    assert batch_deadline([Job("x", 10), Job("y", 0.5)], 1) == 10001
