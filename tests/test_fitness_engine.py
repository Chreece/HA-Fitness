import pytest
from conftest import load_module

fitness = load_module("fitness_test_fitness", "engine/fitness.py")


def test_uth_vo2max():
    assert fitness.uth_vo2max(190, 50) == pytest.approx(58.14)
    assert fitness.uth_vo2max(0, 50) is None


def test_friend_prediction_and_percent():
    male = fitness.friend_predicted_vo2max(40, "male", 75)
    female = fitness.friend_predicted_vo2max(40, "female", 75)
    assert male is not None
    assert female is not None
    assert male > female
    assert fitness.percent_predicted(male, male) == pytest.approx(100.0)


def test_friend_invalid_inputs():
    assert fitness.friend_predicted_vo2max(40, None, 75) is None
    assert fitness.friend_predicted_vo2max(40, "male", 0) is None
    assert fitness.percent_predicted(50, 0) is None


@pytest.mark.parametrize(
    ("pct", "expected"),
    [
        (89.9, "below_reference"),
        (90.0, "around_reference"),
        (110.0, "around_reference"),
        (110.1, "above_reference"),
    ],
)
def test_reference_status(pct, expected):
    assert fitness.reference_status(pct) == expected


def test_hrv_personal_status():
    assert fitness.hrv_personal_status(50, 55, 70) == "below_personal_baseline"
    assert fitness.hrv_personal_status(60, 55, 70) == "within_personal_baseline"
    assert fitness.hrv_personal_status(75, 55, 70) == "above_personal_baseline"


def test_threshold_pace_from_speed():
    assert fitness.threshold_pace_from_speed(4.0) == pytest.approx(4.1666667)
    assert fitness.threshold_pace_from_speed(1.0) is None
    assert fitness.threshold_pace_from_speed(9.0) is None



def test_reference_and_hrv_none_paths():
    assert fitness.reference_status(None) is None
    assert fitness.hrv_personal_status(None, 50, 70) is None
    assert fitness.threshold_pace_from_speed(None) is None
