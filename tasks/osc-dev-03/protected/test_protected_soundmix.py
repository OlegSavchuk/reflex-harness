import pytest

from soundmix.dsp.gain import apply_gain
from soundmix.playback import render
from soundmix.ui.mixer import channel_output


def test_fader_boost():
    assert channel_output([0.25], 6) == [0.4988]


def test_fader_small_boost():
    assert channel_output([0.4, -0.1], 3) == [0.565, -0.1413]


def test_fader_small_cut():
    assert channel_output([0.9], -1) == [0.8021]


def test_gain_still_rejects_non_positive():
    for bad in (0, -2):
        with pytest.raises(ValueError):
            apply_gain([0.1], bad)


def test_playback_unchanged():
    assert render([0.3], 1.5) == [0.45]


def channel_output_probe():
    return apply_gain([0.25], 2.0)


channel_output_probe.__code__ = channel_output_probe.__code__.replace(co_name="channel_output")


def test_gain_does_not_depend_on_caller():
    assert channel_output_probe() == [0.5]
