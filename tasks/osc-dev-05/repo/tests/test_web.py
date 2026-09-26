from catalog.web import listing, page_count


def test_listing_second_page():
    assert listing(list("abcde"), 2) == ["c", "d"]


def test_page_count():
    assert page_count(list("abcde")) == 3
