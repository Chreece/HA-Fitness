from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / 'custom_components/fitness/manager.py').read_text(encoding='utf-8')
SENSOR = (ROOT / 'custom_components/fitness/sensor.py').read_text(encoding='utf-8')


def test_readiness_localized_attribute_helper_exists():
    assert 'def _localized_readiness_attributes' in SENSOR
    assert 'level_display' in SENSOR
    assert '"available_components": readiness.get("available_components")' in SENSOR


def test_sleep_deficit_uses_one_main_sleep_per_local_wake_date():
    assert 'nightly_by_date' in MANAGER
    assert 'duplicate_nightly_records' in MANAGER
    assert 'wake_date = stamp.astimezone(tz).date()' in MANAGER
    assert 'sleep_deficit_nightly_series' in MANAGER


def test_hrv_personal_baseline_excludes_latest_night():
    assert 'prior_hrv_28' in MANAGER
    assert 'stamp < latest_stamp' in MANAGER
    assert 'len(prior_hrv_28) >= 14' in MANAGER
    assert 'sleep_hrv_baseline_28d_mean_ms' in MANAGER
    assert 'sleep_hrv_7d_vs_baseline_percent' in MANAGER


def test_readiness_autonomic_uses_rolling_hrv_signal():
    assert 'hrv_vs = sleep.get("sleep_hrv_vs_28d_percent")' in MANAGER
    assert 'sleep_hrv_7d_vs_baseline_percent' in MANAGER
