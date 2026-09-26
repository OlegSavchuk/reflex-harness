from scheduler.jobs import Job, batch_deadline, job_deadline


def test_job_deadline_fractional_seconds():
    assert job_deadline(Job("resize", 1.5), 1000) == 2500


def test_job_deadline_whole_seconds():
    assert job_deadline(Job("email", 2), 0) == 2000


def test_batch_deadline():
    assert batch_deadline([Job("a", 0.25), Job("b", 3)], 100) == 3100


def test_batch_deadline_empty():
    assert batch_deadline([], 7) == 7
