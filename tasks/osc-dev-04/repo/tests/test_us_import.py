from weather.us_import import feels_like_f


def test_hot_afternoon():
    assert feels_like_f(95, 50) == 101.8


def test_very_hot_dry():
    assert feels_like_f(104, 20) == 107.6
