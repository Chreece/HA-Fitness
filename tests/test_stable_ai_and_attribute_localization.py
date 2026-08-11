import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "custom_components" / "fitness"
MANAGER = (FITNESS / "manager.py").read_text(encoding="utf-8")
BUTTON = (FITNESS / "button.py").read_text(encoding="utf-8")
DETAILS = (FITNESS / "evaluation_details.py").read_text(encoding="utf-8")


def test_ai_service_payload_is_bounded_and_workout_prompt_is_curated():
    assert "def _bounded_ai_json" in MANAGER
    assert "max_bytes: int = 16000" in MANAGER
    assert "self._ai_workout_summary(workout)" in MANAGER
    assert "+ json.dumps(\n                workout.as_dict()" not in MANAGER


def test_manual_ai_regeneration_surfaces_failure_instead_of_silent_noop():
    assert "raise_on_failure=True" in BUTTON
    assert "Fitness AI Task generation failed" in MANAGER
    assert "Fitness conversation AI generation failed" in MANAGER
    assert "Fitness AI evaluation could not be generated" in MANAGER


def test_scientific_detail_attribute_keys_are_stable_machine_keys():
    for key in (
        "scientific_basis",
        "formula",
        "data_used",
        "what_it_means",
        "why_useful",
    ):
        assert f'result["{key}"]' in DETAILS


def test_cardiorespiratory_attribute_names_are_translated_without_renaming_keys():
    en = json.loads((FITNESS / "strings.json").read_text(encoding="utf-8"))
    el = json.loads((FITNESS / "translations" / "el.json").read_text(encoding="utf-8"))
    en_attrs = en["entity"]["sensor"]["cardiorespiratory_fitness_trend"]["state_attributes"]
    el_attrs = el["entity"]["sensor"]["cardiorespiratory_fitness_trend"]["state_attributes"]
    assert en_attrs["current_vo2max_ml_kg_min"]["name"] == "Current VO₂max"
    assert el_attrs["current_vo2max_ml_kg_min"]["name"] == "Τρέχον VO₂max"
    assert el_attrs["scientific_basis"]["name"] == "Επιστημονική βάση"
    assert el_attrs["why_useful"]["name"] == "Γιατί είναι χρήσιμο"
