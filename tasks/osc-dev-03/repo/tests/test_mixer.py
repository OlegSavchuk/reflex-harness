from soundmix.ui.mixer import channel_output, peak


def test_fader_cut():
    assert channel_output([0.5, -0.5], -6) == [0.2506, -0.2506]


def test_fader_unity():
    assert channel_output([0.3, -0.7], 0) == [0.3, -0.7]


def test_fader_deep_cut():
    assert channel_output([0.8], -20) == [0.08]


def test_peak():
    assert peak([0.1, -0.6, 0.3]) == 0.6
