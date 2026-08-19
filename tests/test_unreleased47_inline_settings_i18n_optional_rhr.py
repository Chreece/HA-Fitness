import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components/fitness"
FLOW = (BASE / "config_flow.py").read_text(encoding="utf-8")
DASH = (BASE / "dashboard.py").read_text(encoding="utf-8")
FRONTEND = (BASE / "frontend/fitness-dashboard.js").read_text(encoding="utf-8")
STRINGS = json.loads((BASE / "strings.json").read_text(encoding="utf-8"))


def test_resting_hr_is_optional_during_setup_and_options():
    required_start = FLOW.index("async def async_step_required")
    required_end = FLOW.index("async def async_step_optional", required_start)
    required = FLOW[required_start:required_end]
    assert "_validate_manual_weight(user_input.get(CONF_WEIGHT))" in required
    assert "CONF_WEIGHT_SCALE_ENTITY" in required
    assert "_number(20, 500, step=0.1)" in required
    assert "CONF_RESTING_HR: (20, 150, False)" in required
    assert "vol.Required(CONF_WEIGHT" in required
    assert "_optional_suggested(\n                        CONF_RESTING_HR" in required

    options_start = FLOW.index("async def async_step_fitness_inputs")
    options_end = FLOW.index("async def async_step_live_devices", options_start)
    options = FLOW[options_start:options_end]
    assert "CONF_RESTING_HR: (20, 150, False)" in options
    assert "_optional_suggested(\n                    CONF_RESTING_HR" in options
    assert "vol.Required(\n                    CONF_RESTING_HR" not in options


def test_inline_flow_receives_and_applies_selector_translations():
    assert '"selector": data.get("selector")' in DASH
    assert "_localizedSchema(step)" in FRONTEND
    assert "this._flowTranslations?.selector?.[translationKey]?.options" in FRONTEND
    assert "form.schema = this._localizedSchema(step);" in FRONTEND

    greek = json.loads((BASE / "translations/el.json").read_text(encoding="utf-8"))
    assert greek["selector"]["sex"]["options"]["male"] == "Άνδρας"
    assert greek["selector"]["sex"]["options"]["female"] == "Γυναίκα"


def test_live_sensor_page_is_translated_in_all_shipped_languages():
    english_title = STRINGS["options"]["step"]["live_devices"]["title"]
    for path in (BASE / "translations").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in ("config", "options"):
            step = data[section]["step"]["live_devices"]
            assert step["title"]
            assert step["description"]
            assert step["data"]["live_sensor_ids"]
            assert step["data"]["live_device_ids"]
        if path.stem != "en":
            assert data["options"]["step"]["live_devices"]["title"] != english_title


def test_inline_options_save_is_explicit_and_main_menu_discards_unsaved_changes():
    assert 'const submitLabel = this._mode === "options" || step.last_step' in FRONTEND
    assert 'this.shadowRoot.querySelector(".flow-home")?.addEventListener("click", () => this._saveAndReturnToMenu());' in FRONTEND
    block = FRONTEND[FRONTEND.index("  async _saveAndReturnToMenu() {"):FRONTEND.index("  _renderLoading()", FRONTEND.index("  async _saveAndReturnToMenu() {"))]
    assert "await this._submit(this._formData);" not in block
    assert "this._formDirty" in block
    assert "settings_changes_not_saved" in block
    assert "await this._restartOptionsFlow();" in block
    assert "Do not redraw the parent while an options flow is returning" in FRONTEND
    assert "setTimeout(() => this._load(), 100);" in FRONTEND
    assert "white-space:nowrap" in FRONTEND


def test_tv_setup_enable_buttons_use_renderable_icons_and_menu_has_icons():
    assert FRONTEND.count('icon="mdi:plus-circle-outline"') >= 2
    assert FRONTEND.count('icon="mdi:monitor-dashboard"') >= 2
    assert 'class="modal-title-with-icon"><ha-icon icon="mdi:plus-circle-outline"' in FRONTEND
    assert 'class="tool enable-profile"><ha-icon icon="mdi:television-play"' in FRONTEND
    assert "FITNESS_FLOW_MENU_ICONS" in FRONTEND
    assert 'tv_dashboard:"mdi:television"' in FRONTEND
    assert 'live_devices:"mdi:access-point"' in FRONTEND


def test_tv_setup_text_does_not_name_an_external_frontend_extension():
    combined = (BASE / "strings.json").read_text(encoding="utf-8")
    for path in (BASE / "translations").glob("*.json"):
        combined += path.read_text(encoding="utf-8")
    forbidden = "Browser" + " Mod"
    assert forbidden not in combined


def test_unreleased_frontend_revision_is_47():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-85"' in FRONTEND
    assert '?v=unreleased-85' in DASH
