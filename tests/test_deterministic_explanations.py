from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPLANATIONS = (
    ROOT / "custom_components/fitness/explanations.py"
).read_text(encoding="utf-8")
SENSOR = (
    ROOT / "custom_components/fitness/sensor.py"
).read_text(encoding="utf-8")


def test_sensor_explanations_have_no_ai_path():
    lowered = EXPLANATIONS.lower()
    for forbidden in (
        "_call_ai",
        "conversation.process",
        "ai_task.generate_data",
        "services.async_call",
    ):
        assert forbidden not in lowered


def test_sensor_module_marks_explanation_metadata_deterministic():
    assert "Deterministic; never AI-generated." in SENSOR
    assert "sensor_explanation(" in SENSOR


def test_known_methods_use_stable_scientific_identifiers():
    for method in (
        "Banister TRIMP",
        "Karvonen/ACSM %HRR",
        "ACSM %HRR",
        "HRR",
        "aerobic_decoupling",
        "aerobic_efficiency",
        "Friend et al. 2017 VO₂max reference equation",
    ):
        assert method in EXPLANATIONS


def test_calculation_strings_are_formula_or_algorithm_not_ai_prose():
    for formula in (
        "heart_rate / maximum_heart_rate × 100",
        "(heart_rate − resting_hr) / (maximum_hr − resting_hr) × 100",
        "end_exercise_hr − heart_rate_at_60s",
        "(first_half_efficiency − second_half_efficiency)",
    ):
        assert formula in EXPLANATIONS
