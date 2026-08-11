import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
BASE = json.loads((FIT / "strings.json").read_text(encoding="utf-8"))
SUPPORTED = {"en", "el", "de", "fr", "es", "it", "pt", "nl", "pl", "ru", "uk", "tr", "zh", "ja", "ko"}


def test_every_supported_language_has_every_entity_and_attribute_key():
    base_entity = BASE["entity"]
    for code in SUPPORTED:
        path = FIT / "translations" / f"{code}.json"
        assert path.exists(), code
        translated = json.loads(path.read_text(encoding="utf-8"))["entity"]
        for platform, entries in base_entity.items():
            assert set(entries) <= set(translated.get(platform, {})), (code, platform)
            for key, spec in entries.items():
                assert translated[platform][key].get("name"), (code, platform, key)
                for attr_key in spec.get("state_attributes", {}):
                    attrs = translated[platform][key].get("state_attributes", {})
                    assert attr_key in attrs, (code, key, attr_key)
                    assert attrs[attr_key].get("name"), (code, key, attr_key)


def test_device_names_are_localized_and_do_not_repeat_fitness_or_profile():
    source = (FIT / "device_translations.py").read_text(encoding="utf-8")
    assert "Live workout" in source
    assert "Ζωντανή προπόνηση" in source
    assert "实时训练" in source
    entity = (FIT / "entity.py").read_text(encoding="utf-8")
    assert 'name=f"Fitness' not in entity
    assert "profile_name" not in entity

def test_config_entry_title_no_longer_has_fitness_prefix():
    flow = (FIT / "config_flow.py").read_text(encoding="utf-8")
    init = (FIT / "__init__.py").read_text(encoding="utf-8")
    assert 'title=f"Fitness – {name}"' not in flow
    assert 'title=name' in flow
    assert 'async_update_entry(entry, title=profile_name)' in init
