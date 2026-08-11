import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "custom_components" / "fitness"
SENSOR = (FITNESS / "sensor.py").read_text(encoding="utf-8")

SCIENTIFIC = {
    "sleep_consistency",
    "sleep_deficit_7d",
    "autonomic_recovery_trend",
    "cardiorespiratory_fitness_trend",
    "training_load",
    "heart_rate_recovery",
    "training_recovery_relationship",
    "vo2max_percent_predicted",
}
COMMON = {"scientific_basis", "formula", "data_used", "what_it_means", "why_useful"}


def test_every_scientific_evaluation_has_translated_user_detail_attributes():
    strings = json.loads((FITNESS / "strings.json").read_text(encoding="utf-8"))
    greek = json.loads((FITNESS / "translations" / "el.json").read_text(encoding="utf-8"))
    for key in SCIENTIFIC:
        en_attrs = strings["entity"]["sensor"][key]["state_attributes"]
        el_attrs = greek["entity"]["sensor"][key]["state_attributes"]
        assert COMMON <= set(en_attrs)
        assert set(en_attrs) == set(el_attrs)
        assert all(item.get("name") for item in el_attrs.values())


def test_legacy_vo2max_developer_metadata_is_not_added_to_scientific_entity():
    start = SENSOR.index('grouped_metrics = {')
    end = SENSOR.index('e = self.manager.evaluation()', start)
    block = SENSOR[start:end]
    assert 'scientific_metrics = grouped_metrics | {"vo2max_percent_predicted"}' in block
    assert 'if m in scientific_metrics:' in block
    # Scientific metrics take the clean attrs={} path before the legacy explanation branch.
    assert block.index('if m in scientific_metrics:') < block.index('sensor_explanation(')


def test_ai_evaluation_attributes_are_localized_too():
    greek = json.loads((FITNESS / "translations" / "el.json").read_text(encoding="utf-8"))
    for key in ("ai_general_evaluation", "ai_workout_evaluation"):
        attrs = greek["entity"]["sensor"][key]["state_attributes"]
        assert attrs["text"]["name"] == "Κείμενο αξιολόγησης"
        assert attrs["generated_at"]["name"] == "Δημιουργήθηκε στις"
        assert attrs["ai_entity"]["name"] == "Πάροχος AI"
