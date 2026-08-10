import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
ENTITIES = (ROOT / "custom_components/fitness/providers/entities.py").read_text(encoding="utf-8")
AUTOFILL = (ROOT / "custom_components/fitness/providers/autofill.py").read_text(encoding="utf-8")
TRANSLATIONS = ROOT / "custom_components/fitness/translations"


def test_sex_and_month_selectors_use_translation_keys():
    assert FLOW.count('translation_key="sex"') == 2
    assert FLOW.count('translation_key="birth_month"') == 2
    assert '"label": "Female"' not in FLOW
    assert '"January"' not in FLOW


def test_greek_selector_values_are_localized():
    data = json.loads((TRANSLATIONS / "el.json").read_text(encoding="utf-8"))
    assert data["selector"]["sex"]["options"]["male"] == "Άνδρας"
    assert data["selector"]["sex"]["options"]["female"] == "Γυναίκα"
    assert data["selector"]["birth_month"]["options"]["8"] == "Αύγουστος"


def test_all_languages_have_full_selector_options():
    for path in TRANSLATIONS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert set(data["selector"]["sex"]["options"]) == {
            "female", "male", "other", "prefer_not_to_say"
        }
        assert set(data["selector"]["birth_month"]["options"]) == {
            str(i) for i in range(1, 13)
        }


def test_garmin_middle_dot_vo2max_unit_is_normalized():
    assert '.replace("·", "*")' in ENTITIES
    assert '"ml/(kg*min)"' in ENTITIES
    assert "('garmin_connect',CONF_VO2MAX):{'vo2_max','vo2max'}" in AUTOFILL


def test_options_empty_value_falls_back_to_exact_autofill():
    start = FLOW.index("async def async_step_fitness_inputs")
    end = FLOW.index("async def async_step_live_devices", start)
    block = FLOW[start:end]
    assert "exact_defaults = exact_profile_defaults(self.hass)" in block
    assert 'if value not in (None, ""):' in block
    assert 'return str(exact_defaults.get(key, ""))' in block
