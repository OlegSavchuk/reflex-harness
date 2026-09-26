"""Atlas connectivity failures are named explicitly (tests/conftest.py), never unnamed errors."""
from pathlib import Path

from reflex_harness import config as rh_config

pytest_plugins = ["pytester"]
CONFTEST = (Path(__file__).parent / "conftest.py").read_text()
INNER = '''
import pytest
from pymongo.errors import ServerSelectionTimeoutError

@pytest.mark.atlas
def test_needs_atlas():
    raise AssertionError("body must not run")

def test_drops():
    raise ServerSelectionTimeoutError("cluster0.example.net:27017: timed out")

def test_unit():
    assert True
'''


def run_inner(pytester, *args):
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(test_inner=INNER)
    return pytester.runpytest("-q", *args)


def test_unreachable_atlas_fails_atlas_tests_by_name(pytester, monkeypatch):
    monkeypatch.setattr(rh_config, "MONGODB_URI", "mongodb://127.0.0.1:9/")   # nothing listens there
    r = run_inner(pytester, "-k", "needs_atlas or unit")
    r.assert_outcomes(passed=1, failed=1)
    r.stdout.fnmatch_lines(["MongoDB Atlas: UNREACHABLE (ServerSelectionTimeoutError: *); 1 atlas tests will FAIL "
                            "with 'Atlas unreachable'",
                            "*Atlas unreachable: test_inner.py::test_needs_atlas needs MongoDB Atlas (*"])
    assert "body must not run" not in r.stdout.str()


def test_connection_lost_during_a_test_is_named(pytester, monkeypatch):
    monkeypatch.setattr(rh_config, "MONGODB_URI", "")
    r = run_inner(pytester, "-k", "drops")
    r.assert_outcomes(failed=1)
    r.stdout.fnmatch_lines(["*Atlas unreachable: test_inner.py::test_drops lost its connection to MongoDB Atlas "
                            "(ServerSelectionTimeoutError: cluster0.example.net:27017: timed out)*",
                            "*Atlas unreachable*", "Atlas unreachable: test_inner.py::test_drops"])


def test_no_uri_skips_atlas_tests_with_a_reason(pytester, monkeypatch):
    monkeypatch.setattr(rh_config, "MONGODB_URI", "")
    r = run_inner(pytester, "-k", "needs_atlas or unit", "-rs")
    r.assert_outcomes(passed=1, skipped=1)
    r.stdout.fnmatch_lines(["MongoDB Atlas: MONGODB_URI not set; 1 atlas tests will SKIP",
                            "*needs Atlas: MONGODB_URI not set (test_inner.py::test_needs_atlas)*"])
