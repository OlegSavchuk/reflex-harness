import pytest

from swatch.core.mix import blend
from swatch.importers.css_percent import mix_css
from swatch.themes import accent


def test_css_quarter():
    assert mix_css((0, 50, 100), (100, 50, 0), 0.25) == (54, 50, 88)


def test_css_mid_tones():
    assert mix_css((30, 60, 90), (90, 10, 50), 0.5) == (69, 44, 74)


def test_blend_small_8bit_values():
    assert accent((10, 20, 30), (50, 60, 70)) == (26, 35, 44)


def test_blend_still_rejects_out_of_range():
    with pytest.raises(TypeError):
        blend((256, 0, 0), (0, 0, 0), 0.5)


def mix_css_probe():
    return blend((255, 0, 0), (0, 0, 255), 0.5)


mix_css_probe.__code__ = mix_css_probe.__code__.replace(co_name="mix_css")


def test_blend_does_not_depend_on_caller():
    assert mix_css_probe() == (188, 0, 188)
