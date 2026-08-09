import pytest
from conftest import load_module

hr = load_module("fitness_test_heart_rate", "engine/heart_rate.py")


def test_tanaka_prediction():
    assert hr.predicted_max_hr_tanaka(40) == pytest.approx(180.0)


def test_heart_rate_reserve():
    assert hr.heart_rate_reserve(190, 50) == 140


@pytest.mark.parametrize(
    ("current", "maximum", "resting", "expected"),
    [
        (120, 190, 50, 50.0),
        (50, 190, 50, 0.0),
        (190, 190, 50, 100.0),
    ],
)
def test_hrr_percent(current, maximum, resting, expected):
    assert hr.hrr_percent(current, maximum, resting) == pytest.approx(expected)


def test_hrr_rejects_invalid_reserve():
    assert hr.hrr_percent(100, 50, 50) is None
