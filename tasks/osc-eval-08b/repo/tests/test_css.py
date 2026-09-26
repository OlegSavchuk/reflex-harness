from swatch.importers.css_percent import mix_css


def test_red_blue_midpoint():
    assert mix_css((100, 0, 0), (0, 0, 100), 0.5) == (74, 0, 74)


def test_grey_to_white():
    assert mix_css((40, 40, 40), (100, 100, 100), 0.5) == (78, 78, 78)


def test_same_colour():
    assert mix_css((20, 40, 60), (20, 40, 60), 0.3) == (20, 40, 60)
