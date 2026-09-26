from photokit.cli.manual import manual_crop


def test_manual_rect():
    assert manual_crop(400, 300, (10, 20, 110, 220)) == (10, 20, 110, 220)


def test_manual_quarter():
    assert manual_crop(400, 300, (0, 0, 200, 150)) == (0, 0, 200, 150)
