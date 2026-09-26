"""MongoDB Atlas connectivity for the test suite.

Tests that need Atlas carry `@pytest.mark.atlas`. Right after collection, if any are selected,
one ping (3 s timeout) reports on the terminal whether Atlas is reachable. Then:
- MONGODB_URI unset: atlas tests SKIP ("needs Atlas: MONGODB_URI not set").
- Atlas unreachable: atlas tests FAIL at once with "Atlas unreachable: <test id> ...", instead of
  hanging on the driver timeout.
- A connection error during any test (e.g. the network drops mid-suite) fails that test with
  "Atlas unreachable: <test id> lost its connection ...".
Every such test is listed again in an "Atlas unreachable" section of the final summary.
"""
import time

import pytest
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError

from reflex_harness import config as rh_config

PING_TIMEOUT_MS = 3000
_state = {"checked": False, "ok": False, "detail": ""}
_unreachable: list[str] = []


def _first_line(e: BaseException) -> str:
    return f"{type(e).__name__}: {(str(e).splitlines() or [''])[0][:200]}"


def _check_atlas() -> None:
    if _state["checked"]:
        return
    _state["checked"] = True
    if not rh_config.MONGODB_URI:
        _state["detail"] = "MONGODB_URI not set"
        return
    t0 = time.monotonic()
    try:
        with MongoClient(rh_config.MONGODB_URI, serverSelectionTimeoutMS=PING_TIMEOUT_MS,
                         connectTimeoutMS=PING_TIMEOUT_MS) as c:
            c.admin.command("ping")
    except PyMongoError as e:
        _state["detail"] = _first_line(e)
        return
    _state.update(ok=True, detail=f"ping {round((time.monotonic() - t0) * 1000)} ms")


def pytest_configure(config):
    config.addinivalue_line("markers", "atlas: needs a reachable MongoDB Atlas cluster (MONGODB_URI)")


def pytest_collection_modifyitems(session, config, items):
    atlas = [i for i in items if i.get_closest_marker("atlas")]
    tr = config.pluginmanager.get_plugin("terminalreporter")
    if not atlas:
        line = "MongoDB Atlas check: no atlas tests selected"
    else:
        _check_atlas()
        if _state["ok"]:
            line = f"MongoDB Atlas: reachable ({_state['detail']}); {len(atlas)} atlas tests will run"
        elif not rh_config.MONGODB_URI:
            line = f"MongoDB Atlas: MONGODB_URI not set; {len(atlas)} atlas tests will SKIP"
        else:
            line = (f"MongoDB Atlas: UNREACHABLE ({_state['detail']}); {len(atlas)} atlas tests will FAIL "
                    f"with 'Atlas unreachable'")
    if tr is not None:
        tr.write_line(line)


def pytest_runtest_setup(item):
    if item.get_closest_marker("atlas") and not rh_config.MONGODB_URI:
        pytest.skip(f"needs Atlas: MONGODB_URI not set ({item.nodeid})")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    if item.get_closest_marker("atlas"):
        _check_atlas()
        if not _state["ok"]:  # fail before the test body runs, not after a 30 s driver timeout
            _unreachable.append(item.nodeid)
            pytest.fail(f"Atlas unreachable: {item.nodeid} needs MongoDB Atlas ({_state['detail']})",
                        pytrace=False)
    try:
        return (yield)
    except ConnectionFailure as e:
        _unreachable.append(item.nodeid)
        pytest.fail(f"Atlas unreachable: {item.nodeid} lost its connection to MongoDB Atlas ({_first_line(e)})",
                    pytrace=False)


def pytest_terminal_summary(terminalreporter):
    if _unreachable:
        terminalreporter.section("Atlas unreachable", red=True)
        for nodeid in dict.fromkeys(_unreachable):
            terminalreporter.write_line(f"Atlas unreachable: {nodeid}")
