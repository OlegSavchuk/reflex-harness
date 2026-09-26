from imaging.print_layout import pages_needed, printed_size


def test_printed_size_enlarged():
    assert printed_size(800, 600, 150) == (1200, 900)


def test_printed_size_small_zoom():
    assert printed_size(1000, 500, 8) == (80, 40)


def test_pages_needed():
    assert pages_needed(2000, 1000, 50, (1000, 1000)) == 1
