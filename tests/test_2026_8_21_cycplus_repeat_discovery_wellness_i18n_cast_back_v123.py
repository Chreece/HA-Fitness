from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
FRONTEND = (FIT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
SENSOR = (FIT / "sensor.py").read_text(encoding="utf-8")


def test_verified_serial_route_cannot_reopen_add_for_installed_physical_device():
    assert "def _accepted_verified_serial_owner" in RUNTIME
    block = RUNTIME.split("def _accepted_verified_serial_owner", 1)[1].split(
        "def _schedule_sensor_discovery", 1
    )[0]
    assert 'fitness_serial_identity_verified' in block
    assert "self.sensor_is_accepted(candidate_id)" in block
    schedule = RUNTIME.split("def _schedule_sensor_discovery", 1)[1].split(
        "def sensor_is_accepted", 1
    )[0]
    assert "installed_owner = self._accepted_verified_serial_owner(sensor_id)" in schedule
    assert "self._merge_physical_sensors(installed_owner, sensor)" in schedule
    assert "self._abort_discovery_flows_after_accepted_merge" in schedule


def test_wellness_entities_use_native_translation_keys_in_all_languages():
    assert 'translation_key=f"device_{metric}"' in SENSOR
    base = json.loads((FIT / "strings.json").read_text(encoding="utf-8"))
    keys = {f"device_{metric}" for metric in (
        "heart_rate", "resting_heart_rate", "hrv_ms", "respiratory_rate", "spo2",
        "skin_temperature", "steps", "distance_m", "calories", "active_minutes",
        "stress", "body_battery", "sleep_score", "vo2_max", "weight", "bmi",
        "body_fat", "body_water", "muscle_mass", "battery", "charging", "wear_state",
    )}
    assert keys <= set(base["entity"]["sensor"])
    for code in ("el","de","fr","es","it","pt","nl","pl","ru","uk","tr","zh","ja","ko"):
        translated = json.loads((FIT / "translations" / f"{code}.json").read_text(encoding="utf-8"))
        entities = translated["entity"]["sensor"]
        assert keys <= set(entities), code
        assert all(str(entities[key].get("name") or "").strip() for key in keys), code


def test_visible_cast_exit_confirmation_means_next_distinct_back_exits():
    back = FRONTEND.split("_handleCastRemoteBackPress(event", 1)[1].split(
        "_beginCastRemoteBack", 1
    )[0]
    assert 'const exitNotice = this.shadowRoot?.getElementById("cast-exit-confirm")' in back
    assert "const confirmationVisible = !!exitNotice && !exitNotice.hidden" in back
    assert 'if (confirmationVisible && Number(this._castRemoteExitArmedUntil || 0) > now)' in back
    assert 'void this._quitCastFromRemote("double back", quitAuthorization)' in back
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in FRONTEND
