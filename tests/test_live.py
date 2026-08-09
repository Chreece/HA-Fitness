import pytest
from conftest import load_module

live = load_module("fitness_test_live", "engine/live.py")


def test_percent_max_hr():
    assert live.percent_max_hr(150, 200) == pytest.approx(75.0)
    assert live.percent_max_hr(150, 0) is None


def test_percent_hrr():
    assert live.percent_hrr(120, 190, 50) == pytest.approx(50.0)
    assert live.percent_hrr(120, 50, 50) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (29.9, "very_light"),
        (30.0, "light"),
        (39.9, "light"),
        (40.0, "moderate"),
        (59.9, "moderate"),
        (60.0, "vigorous"),
        (89.9, "vigorous"),
        (90.0, "near_maximal"),
    ],
)
def test_acsm_intensity_boundaries(value, expected):
    assert live.acsm_hrr_intensity(value) == expected


def test_relative_and_pace_conversions():
    assert live.relative_percent(200, 250) == pytest.approx(80.0)
    assert live.relative_percent(200, 0) is None
    assert live.pace_from_speed_kmh(12) == pytest.approx(5.0)
    assert live.speed_from_pace_min_km(5) == pytest.approx(12.0)



def test_live_none_paths():
    assert live.percent_max_hr(None, 190) is None
    assert live.percent_hrr(None, 190, 50) is None
    assert live.acsm_hrr_intensity(None) is None
    assert live.relative_percent(None, 100) is None
    assert live.pace_from_speed_kmh(0) is None
    assert live.speed_from_pace_min_km(0) is None
