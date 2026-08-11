import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "custom_components" / "fitness"

CALCULATED_TRANSLATION_KEYS = {
    "session_duration",
    "heart_rate_percent_max",
    "heart_rate_reserve_percent",
    "heart_rate_intensity",
    "heart_rate_relative_threshold",
    "current_power_to_weight",
    "power_relative_threshold",
    "current_pace",
    "speed_relative_threshold",
    "live_average_heart_rate",
    "live_maximum_heart_rate",
    "live_average_power",
    "live_maximum_power",
    "live_average_cadence",
    "live_average_speed",
    "live_banister_trimp",
    "live_mechanical_work",
    "live_aerobic_efficiency",
    "live_aerobic_decoupling",
    "live_time_moderate",
    "live_time_vigorous",
    "live_time_near_maximal",
}


def test_calculated_live_entities_expose_scientific_user_attributes_in_every_language():
    files = [FITNESS / "strings.json", *sorted((FITNESS / "translations").glob("*.json"))]
    required = {
        "calculated_by_fitness",
        "scientific_basis",
        "formula",
        "data_used",
        "what_it_means",
        "why_useful",
    }
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        sensors = data["entity"]["sensor"]
        for key in CALCULATED_TRANSLATION_KEYS:
            attrs = sensors[key].get("state_attributes", {})
            assert required <= set(attrs), f"{path.name}:{key} missing {required - set(attrs)}"
            for attr in required:
                assert attrs[attr]["name"].strip(), f"{path.name}:{key}:{attr} empty"


def test_raw_live_measurements_do_not_claim_fitness_calculation():
    data = json.loads((FITNESS / "strings.json").read_text(encoding="utf-8"))
    sensors = data["entity"]["sensor"]
    for key in ("current_heart_rate", "current_power", "current_cadence", "current_speed", "current_distance", "current_altitude"):
        assert "calculated_by_fitness" not in sensors[key].get("state_attributes", {})


def test_live_detail_code_and_legacy_ai_title_migration_present():
    live = (FITNESS / "live_details.py").read_text(encoding="utf-8")
    sensor = (FITNESS / "sensor.py").read_text(encoding="utf-8")
    assert '"live_banister_trimp": "banister_trimp_validation_2014"' in live
    assert '"heart_rate_intensity": "acsm_hrr_intensity_2011"' in live
    assert '"live_aerobic_decoupling": "cardiovascular_drift_2001"' in live
    assert 'attrs.update(live_user_details(' in sensor
    assert '"Τελευταίας προπόνησης με AI"' in sensor
    assert 'registry.async_update_entity(self.entity_id, name=None)' in sensor
