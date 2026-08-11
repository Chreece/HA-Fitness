import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_stable_version_and_single_changelog():
    manifest = json.loads((ROOT / "custom_components/fitness/manifest.json").read_text())
    assert manifest["version"] == "2026.8.1"
    assert not list(ROOT.glob("RELEASE_NOTES_*.md"))
    assert "2026.8.0 — First stable public release" in CHANGELOG
    assert "status-stable" in README


def test_ai_uses_curated_fitness_context_and_language_guard():
    assert "def _ai_evaluation_context" in MANAGER
    assert '"home_assistant_long_term_statistics"' not in MANAGER[MANAGER.index("def _ai_evaluation_context"):MANAGER.index("def _general_ai_prompt")]
    assert "not a generic JSON/data analyst" in MANAGER
    assert "MANDATORY OUTPUT LANGUAGE" in MANAGER
    assert "_call_ai_with_language_guard" in MANAGER
    assert "_ai_result_language_mismatch" in MANAGER


def test_grouped_evaluation_attributes_are_specific_not_boilerplate():
    section = SENSOR[SENSOR.index("grouped_metrics = {"):SENSOR.index("grouped = {")]
    assert 'attrs = {"evaluation_scope": m}' not in section
    assert 'attrs = {}' in section
