from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONST = (
    ROOT / "custom_components/fitness/const.py"
).read_text(encoding="utf-8")
FLOW = (
    ROOT / "custom_components/fitness/config_flow.py"
).read_text(encoding="utf-8")
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def test_supported_language_registry_contains_all_shipped_languages():
    for code in (
        "en", "el", "de", "fr", "es", "it", "pt", "nl",
        "pl", "ru", "uk", "tr", "zh", "ja", "ko",
    ):
        assert f'"{code}":' in CONST


def test_setup_has_language_selector():
    assert "CONF_LANGUAGE" in FLOW
    assert "def _language_selector" in FLOW
    assert "SUPPORTED_LANGUAGES.items()" in FLOW
    assert "default=_default_language(self.hass)" in FLOW


def test_unsupported_ui_language_defaults_to_english():
    assert 'return code if code in SUPPORTED_LANGUAGES else "en"' in FLOW


def test_options_profile_can_change_language():
    options = FLOW[FLOW.index("class FitnessOptionsFlow"):]
    assert "CONF_LANGUAGE" in options
    assert "_language_selector()" in options
    assert "CONF_LANGUAGE: _normalize_language(" in options


def test_manager_prefers_profile_language_with_legacy_ui_fallback():
    method_start = MANAGER.index("def _ai_language")
    method_end = MANAGER.index("def _prompt_strings", method_start)
    method = MANAGER[method_start:method_end]

    assert "configured = self.config.get(CONF_LANGUAGE)" in method
    assert "getattr(self.hass.config, " in method
    assert "SUPPORTED_LANGUAGES" in method


def test_config_flow_version_bumped_for_profile_schema():
    assert "VERSION = 11" in FLOW
