from photokit.smart_crop import center_crop


def test_center_crop():
    assert center_crop(400, 300, 0.5) == (100, 75, 300, 225)
