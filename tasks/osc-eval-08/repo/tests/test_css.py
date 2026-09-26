from palette.importers.css_float import mix_css


def test_red_blue_midpoint():
    assert mix_css((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.5) == (0.502, 0.0, 0.502)


def test_same_colour():
    assert mix_css((0.2, 0.4, 0.6), (0.2, 0.4, 0.6), 0.3) == (0.2, 0.4, 0.6)
