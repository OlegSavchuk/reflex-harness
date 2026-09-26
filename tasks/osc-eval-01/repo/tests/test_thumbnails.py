from imaging.thumbnails import fits_within, thumbnail_size


def test_thumbnail_medium():
    assert thumbnail_size(1920, 1080) == (480, 270)


def test_thumbnail_small():
    assert thumbnail_size(1000, 800, "small") == (100, 80)


def test_fits_within():
    assert fits_within((100, 80), (120, 90))
