from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
EXPL = (
    ROOT / "custom_components/fitness/explanations.py"
).read_text(encoding="utf-8")
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")
SENSOR = (
    ROOT / "custom_components/fitness/sensor.py"
).read_text(encoding="utf-8")


def _provenance_catalog():
    tree = ast.parse(EXPL)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name)
                and target.id == "_PROVENANCE_TEXT"
                for target in node.targets
            ):
                return ast.literal_eval(node.value)
    raise AssertionError("_PROVENANCE_TEXT not found")


def test_all_languages_have_internal_provenance_vocabulary():
    catalog = _provenance_catalog()
    expected_languages = {
        "en", "el", "de", "fr", "es", "it", "pt", "nl",
        "pl", "ru", "uk", "tr", "zh", "ja", "ko",
    }
    required = {
        "calculated", "direct", "provider", "history", "profile",
        "sources", "why", "caveat", "provider_note",
        "history_note", "direct_note",
    }

    assert set(catalog) == expected_languages
    for language, values in catalog.items():
        assert set(values) == required, language
        assert all(str(value).strip() for value in values.values())


def test_greek_provenance_is_localized():
    catalog = _provenance_catalog()
    assert catalog["el"]["calculated"] == "Υπολογισμός από το Fitness"
    assert "πάροχο" in catalog["el"]["provider_note"]


def test_runtime_uses_selected_language_for_human_provenance():
    assert "def provenance_text(language: str, key: str)" in EXPL
    assert "self._ai_language()" in MANAGER
    assert "localized_evaluation_provenance" in SENSOR


def test_technical_fields_are_not_translated():
    start = MANAGER.index("def localized_evaluation_provenance")
    end = MANAGER.index("def evaluation(", start)
    block = MANAGER[start:end]

    for technical in (
        "formula", "input_sources", "entity_id",
        "raw_value", "raw_unit",
    ):
        assert f'provenance_text(language, "{technical}")' not in block
