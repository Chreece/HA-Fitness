import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
ENTITIES = (ROOT / "custom_components/fitness/providers/entities.py").read_text(encoding="utf-8")
AUTOFILL = (ROOT / "custom_components/fitness/providers/autofill.py").read_text(encoding="utf-8")
TRANSLATIONS = ROOT / "custom_components/fitness/translations"


def test_sex_selector_and_birthday_datepicker_are_used():
    assert FLOW.count('translation_key="sex"') == 1
    assert FLOW.count('_sex_selector()') >= 2
    assert FLOW.count('selector.DateSelector()') >= 4
    assert 'vol.Required(CONF_DATE_OF_BIRTH, default="1980-01-01"): selector.DateSelector()' in FLOW
    assert 'translation_key="birth_month"' not in FLOW
    assert '"label": "Female"' not in FLOW
    assert '"January"' not in FLOW


def test_greek_sex_and_birthday_are_localized():
    data = json.loads((TRANSLATIONS / "el.json").read_text(encoding="utf-8"))
    assert data["selector"]["sex"]["options"]["male"] == "Άνδρας"
    assert data["selector"]["sex"]["options"]["female"] == "Γυναίκα"
    assert data["config"]["step"]["user"]["data"]["date_of_birth"] == "Ημερομηνία γέννησης"


def test_all_languages_have_sex_and_birthday_date_labels():
    for path in TRANSLATIONS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert set(data["selector"]["sex"]["options"]) == {
            "female", "male", "other", "prefer_not_to_say"
        }
        assert data["config"]["step"]["user"]["data"]["date_of_birth"].strip()
        assert data["options"]["step"]["profile"]["data"]["date_of_birth"].strip()


def test_garmin_middle_dot_vo2max_unit_is_normalized():
    assert '.replace("·", "*")' in ENTITIES
    assert '"ml/(kg*min)"' in ENTITIES
    assert "('garmin_connect',CONF_VO2MAX):{'vo2_max','vo2max'}" in AUTOFILL


def test_options_optional_inputs_can_be_cleared_without_autofill_returning():
    start = FLOW.index("async def async_step_fitness_inputs")
    end = FLOW.index("async def async_step_live_devices", start)
    block = FLOW[start:end]
    assert "exact_defaults = exact_profile_defaults(" in block
    assert "self.config_entry.entry_id" in block
    assert "def current_text(key, *, required=False):" in block
    assert "if required:" in block
    assert 'return str(exact_defaults.get(key, ""))' in block
    assert 'return ""' in block
    assert "_optional_suggested(" in block


def test_gender_other_and_prefer_not_to_say_are_one_backend_choice():
    assert 'options=["female", "male", "prefer_not_to_say"]' in FLOW
    assert 'return "prefer_not_to_say" if value == "other" else value' in FLOW
    data = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))
    assert data["selector"]["sex"]["options"]["prefer_not_to_say"] == "Other / Prefer not to say"
