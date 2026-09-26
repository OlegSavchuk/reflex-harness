import pytest

from vault.blocks import blocks_needed
from vault.quota import plan
from vault.uploads import blocks_for_upload


def test_plan_one_mebibyte():
    assert plan({"archive": 1024}) == {"archive": 256}


def test_plan_sector_multiple_kib():
    assert plan({"db": 512, "empty": 0}) == {"db": 128, "empty": 0}


def test_blocks_still_reject_unaligned():
    with pytest.raises(ValueError):
        blocks_needed(1000)


def test_uploads_unchanged():
    assert blocks_for_upload(1) == 1


def plan_probe():
    return blocks_needed(8192)


plan_probe.__code__ = plan_probe.__code__.replace(co_name="plan")


def test_blocks_do_not_depend_on_caller():
    assert plan_probe() == 2
