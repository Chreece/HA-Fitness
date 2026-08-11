from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
CAP = (ROOT / "custom_components/fitness/providers/capabilities.py").read_text(encoding="utf-8")


def test_profile_inputs_have_entity_dropdown_and_custom_value():
    assert "def _number_or_entity_selector" in FLOW
    assert "custom_value=True" in FLOW
    assert "_compatible_profile_entities" in FLOW


def test_entity_dropdown_uses_runtime_capability_catalog():
    assert "profile_entity_choices" in FLOW
    assert "convert_to_canonical(" in CAP
    assert "_PROFILE_ALIASES" in CAP


def test_manual_numeric_or_entity_validation_remains():
    assert "validate_number_or_entity(" in FLOW
    assert "is_entity_reference(value)" in FLOW
