import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANS = ROOT / "custom_components/fitness/translations"
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
EXPL = (ROOT / "custom_components/fitness/explanations.py").read_text(encoding="utf-8")


def test_all_languages_have_provenance_vocabulary():
    required = {"calculated","direct","provider","history","profile","sources",
                "why","caveat","provider_note","history_note","direct_note"}
    for path in TRANS.glob("*.json"):
        data=json.loads(path.read_text(encoding="utf-8"))
        assert set(data["evaluation_provenance"]) == required
        assert all(v.strip() for v in data["evaluation_provenance"].values())


def test_greek_provenance_is_greek():
    data=json.loads((TRANS/"el.json").read_text(encoding="utf-8"))
    assert data["evaluation_provenance"]["calculated"] == "Υπολογισμός από το Fitness"
    assert "πάροχο" in data["evaluation_provenance"]["provider_note"]


def test_runtime_uses_selected_language_for_human_provenance():
    assert "def provenance_text(language: str, key: str)" in EXPL
    assert "self._ai_language()" in MANAGER
    assert "localized_evaluation_provenance" in SENSOR


def test_technical_fields_are_not_run_through_translation():
    start=MANAGER.index("def localized_evaluation_provenance")
    end=MANAGER.index("def evaluation(",start)
    block=MANAGER[start:end]
    for technical in ("formula", "input_sources", "entity_id", "raw_value", "raw_unit"):
        assert f'provenance_text(language, "{technical}")' not in block
