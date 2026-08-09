from math import exp
import pytest
from conftest import load_module

training = load_module("fitness_test_training", "engine/training.py")


def test_fractional_hr_reserve():
    assert training.fractional_hr_reserve(120, 50, 190) == pytest.approx(0.5)
    assert training.fractional_hr_reserve(None, 50, 190) is None
    assert training.fractional_hr_reserve(120, 190, 190) is None


def test_banister_trimp_male():
    result = training.banister_trimp(60, 120, 50, 190, "male")
    expected = 60 * 0.5 * 0.64 * exp(1.92 * 0.5)
    assert result == pytest.approx(expected)


def test_banister_trimp_female():
    result = training.banister_trimp(60, 120, 50, 190, "female")
    expected = 60 * 0.5 * 0.86 * exp(1.67 * 0.5)
    assert result == pytest.approx(expected)


def test_mechanical_work_trapezoid_and_gap_filter():
    samples = [
        {"_timestamp_epoch": 0, "power": 100},
        {"_timestamp_epoch": 10, "power": 200},
        {"_timestamp_epoch": 20, "power": 300},
        {"_timestamp_epoch": 100, "power": 999},
    ]
    # 10s * mean(100,200) + 10s * mean(200,300) = 4000 J.
    assert training.mechanical_work_kj(samples) == pytest.approx(4.0)


def test_hrr_intensity_time():
    samples = [
        {"_timestamp_epoch": 0, "heart_rate": 80},   # 21.4% HRR => very light
        {"_timestamp_epoch": 10, "heart_rate": 100}, # 35.7% => light
        {"_timestamp_epoch": 20, "heart_rate": 120}, # 50% => moderate
        {"_timestamp_epoch": 30, "heart_rate": 150}, # 71.4% => vigorous
        {"_timestamp_epoch": 40, "heart_rate": 180}, # 92.9% => near-max
        {"_timestamp_epoch": 50, "heart_rate": 180},
    ]
    result = training.time_in_hrr_intensity(samples, 50, 190)
    assert result == {
        "very_light": 10.0,
        "light": 10.0,
        "moderate": 10.0,
        "vigorous": 10.0,
        "near_maximal": 10.0,
    }


def test_aerobic_efficiency_and_decoupling_power():
    samples = []
    # 24 minutes, 2-minute samples. First half ratio 2.0; second half ratio 1.8.
    for i in range(13):
        ts = i * 120
        ratio = 2.0 if i <= 6 else 1.8
        hr = 150
        samples.append(
            {"_timestamp_epoch": ts, "heart_rate": hr, "power": hr * ratio}
        )

    result = training.aerobic_efficiency_and_decoupling(samples, 1440)
    assert result["efficiency_kind"] == "power_hr"
    assert result["efficiency"] == pytest.approx((7*2.0 + 6*1.8)/13, abs=1e-5)
    assert result["decoupling_percent"] == pytest.approx(10.0, abs=0.01)


def test_decoupling_requires_duration_and_samples():
    samples = [
        {"_timestamp_epoch": i * 60, "heart_rate": 150, "speed": 12}
        for i in range(6)
    ]
    result = training.aerobic_efficiency_and_decoupling(samples, 300)
    assert result["efficiency_kind"] == "speed_hr"
    assert result["decoupling_percent"] is None


def test_coefficient_of_variation():
    assert training.coefficient_of_variation([10, 10, 10]) == pytest.approx(0)
    assert training.coefficient_of_variation([0, 0]) is None



def test_banister_invalid_inputs():
    assert training.banister_trimp(None, 120, 50, 190, "male") is None
    assert training.banister_trimp(0, 120, 50, 190, "male") is None
    assert training.banister_trimp(60, None, 50, 190, "male") is None


def test_mechanical_work_invalid_and_insufficient_samples():
    assert training.mechanical_work_kj([]) is None
    assert training.mechanical_work_kj([{"_timestamp_epoch": 1, "power": 100}]) is None
    assert training.mechanical_work_kj([
        {"_timestamp_epoch": "bad", "power": 100},
        {"_timestamp_epoch": 1, "power": "bad"},
    ]) is None


def test_intensity_time_ignores_invalid_and_large_gaps():
    samples = [
        {"_timestamp_epoch": 0, "heart_rate": 120},
        {"_timestamp_epoch": 60, "heart_rate": 120},  # ignored gap >30 sec
        {"_timestamp_epoch": "bad", "heart_rate": 120},
        {"_timestamp_epoch": 70, "heart_rate": "bad"},
    ]
    result = training.time_in_hrr_intensity(samples, 50, 190)
    assert sum(result.values()) == 0
    assert sum(training.time_in_hrr_intensity(samples, None, 190).values()) == 0


def test_aerobic_efficiency_invalid_rows_and_power_preference():
    samples = [
        {"_timestamp_epoch": 0, "heart_rate": 0, "power": 200},
        {"_timestamp_epoch": "bad", "heart_rate": 150, "power": 200},
        {"_timestamp_epoch": 10, "heart_rate": 150, "power": "bad", "speed": 10},
        {"_timestamp_epoch": 20, "heart_rate": 150, "power": 300},
        {"_timestamp_epoch": 30, "heart_rate": 150, "power": 300},
        {"_timestamp_epoch": 40, "heart_rate": 150, "power": 300},
        {"_timestamp_epoch": 50, "heart_rate": 150, "power": 300},
        {"_timestamp_epoch": 60, "heart_rate": 150, "power": 300},
        {"_timestamp_epoch": 70, "heart_rate": 150, "power": 300},
    ]
    result = training.aerobic_efficiency_and_decoupling(samples, 70)
    assert result["efficiency_kind"] == "power_hr"
    assert result["efficiency"] == pytest.approx(2.0)


def test_aerobic_efficiency_empty_duration():
    assert training.aerobic_efficiency_and_decoupling([], 0) == {
        "efficiency": None,
        "efficiency_kind": None,
        "decoupling_percent": None,
    }
