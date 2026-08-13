"""Regression audit for user-visible Fitness sensor attributes."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR_PATH = ROOT / "custom_components/fitness/sensor.py"
TRANSLATIONS = ROOT / "custom_components/fitness/translations"
LANGUAGES = ("en","el","de","fr","es","it","pt","nl","pl","ru","uk","tr","zh","ja","ko")
COMMON_SCIENCE = {"scientific_basis","formula","data_used","what_it_means","why_useful"}


def _scientific_grouped_attributes() -> dict[str, set[str]]:
    tree = ast.parse(SENSOR_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "grouped" for target in node.targets):
            continue
        value = node.value
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Dict)
        ):
            continue
        result = {}
        for key, attrs in zip(value.func.value.keys, value.func.value.values):
            if isinstance(key, ast.Constant) and isinstance(attrs, ast.Dict):
                result[str(key.value)] = {
                    str(attr.value)
                    for attr in attrs.keys
                    if isinstance(attr, ast.Constant)
                }
        if result:
            return result
    raise AssertionError("Could not find grouped scientific sensor attributes")


def _sensors(language: str) -> dict:
    payload = json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))
    return payload["entity"]["sensor"]


def test_all_supported_languages_have_same_sensor_attribute_schema_as_english():
    english = _sensors("en")
    for language in LANGUAGES[1:]:
        translated = _sensors(language)
        assert set(english) <= set(translated), language
        for entity, definition in english.items():
            expected = set(definition.get("state_attributes", {}))
            actual = set(translated[entity].get("state_attributes", {}))
            assert expected <= actual, (language, entity, sorted(expected - actual))


def test_every_generated_scientific_attribute_has_translation_in_every_language():
    grouped = _scientific_grouped_attributes()
    for language in LANGUAGES:
        sensors = _sensors(language)
        for entity, generated in grouped.items():
            translated = set(sensors[entity].get("state_attributes", {}))
            expected = generated | COMMON_SCIENCE
            assert expected <= translated, (language, entity, sorted(expected - translated))


def test_readiness_runtime_attributes_are_translated_everywhere():
    expected = {
        "level","level_display","confidence_percent","components_available",
        "components","reason","data_source","updated_at",
    }
    for language in LANGUAGES:
        translated = set(_sensors(language)["readiness"]["state_attributes"])
        assert expected <= translated, (language, sorted(expected - translated))


def test_sleep_deficit_attribution_uses_canonical_nights_not_latest_provider_dump():
    source = SENSOR_PATH.read_text(encoding="utf-8")
    start = source.index('if metric == "sleep_deficit_7d":')
    end = source.index('if metric == "sleep_consistency":', start)
    block = source[start:end]
    assert "sleep_deficit_nightly_series" in block
    assert "latest_sleep.sources" not in block
    assert '"excess_sleep_offsets_shortfall": False' in source
