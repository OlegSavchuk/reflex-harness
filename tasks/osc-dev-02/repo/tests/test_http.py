from scheduler.http_client import request_deadline, retry_deadlines


def test_request_deadline():
    assert request_deadline(1000, 250) == 1250


def test_request_deadline_default():
    assert request_deadline(0) == 30000


def test_retry_deadlines():
    assert retry_deadlines(0, 100, 2) == [100, 200, 300]
