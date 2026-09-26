from catalog.api.export import export_batch

RECORDS = list("abcdefgh")


def test_first_batch():
    assert export_batch(RECORDS, 0) == ["a", "b", "c"]


def test_second_batch():
    assert export_batch(RECORDS, 1) == ["d", "e", "f"]


def test_last_partial_batch():
    assert export_batch(RECORDS, 2) == ["g", "h"]
