import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_manifest_has_valid_release_version():
    manifest = json.loads(
        (ROOT / "custom_components/fitness/manifest.json").read_text()
    )
    assert re.fullmatch(
        r"\d{4}\.\d{1,2}\.\d+(?:-beta\d+)?",
        manifest["version"],
    )


def test_single_changelog():
    assert (ROOT / "CHANGELOG.md").is_file()
    assert not list(ROOT.glob("CHANGELOG_*.md"))


def test_long_windows_require_real_recorder_coverage():
    assert '"mean_7d": round(mean(v7), 3) if len(v7) >= 5 else None' in MANAGER
    assert '"mean_28d": round(mean(v28), 3) if len(v28) >= 21 else None' in MANAGER
    assert '"mean_90d": round(mean(v90), 3) if len(v90) >= 60 else None' in MANAGER
    assert 'len(recent14) >= 10 and len(prior14) >= 10' in MANAGER


def test_sleep_history_requires_completed_night_coverage():
    assert 'avg("duration_s", 7, 5)' in MANAGER
    assert 'avg("duration_s", 28, 21)' in MANAGER
    assert 'len(seven) >= 5' in MANAGER


def test_evaluation_exposes_auditable_history_series():
    assert '"daily_series": recorder.get("vo2max_daily") or []' in SENSOR
    assert '"minimum_days_28d": 21' in SENSOR
    assert '"minimum_days_90d": 60' in SENSOR
    assert 'class="history"' in FRONTEND
    assert 'aria-label="VO2max history"' in FRONTEND
