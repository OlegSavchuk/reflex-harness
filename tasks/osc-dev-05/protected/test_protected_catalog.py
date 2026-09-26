import pytest

from catalog.api.export import export_batch
from catalog.paging import page_slice
from catalog.web import listing


def test_export_other_batch_size():
    assert export_batch(list("abcdefgh"), 1, batch_size=4) == ["e", "f", "g", "h"]


def test_export_first_batch_of_two():
    assert export_batch(list("wxyz"), 0, batch_size=2) == ["w", "x"]


def test_paging_still_rejects_page_zero():
    with pytest.raises(ValueError):
        page_slice([1, 2, 3], 0, 2)


def test_web_unchanged():
    assert listing(list("abcdef"), 3) == ["e", "f"]


def export_batch_probe():
    return page_slice(list("abcd"), 1, 2)


export_batch_probe.__code__ = export_batch_probe.__code__.replace(co_name="export_batch")


def test_paging_does_not_depend_on_caller():
    assert export_batch_probe() == ["a", "b"]
