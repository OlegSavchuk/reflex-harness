from soundmix.playback import fade_out, render


def test_render_volume():
    assert render([0.2, -0.4], 2.0) == [0.4, -0.8]


def test_render_clips():
    assert render([0.8], 2.0) == [1.0]


def test_fade_out():
    assert fade_out([0.5, 0.5]) == [0.5, 0.25]
