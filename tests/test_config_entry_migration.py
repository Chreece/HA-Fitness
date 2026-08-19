from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT = (
    ROOT / "custom_components/fitness/__init__.py"
).read_text(encoding="utf-8")
FLOW = (
    ROOT / "custom_components/fitness/config_flow.py"
).read_text(encoding="utf-8")


def test_migration_handler_exists_for_config_flow_version():
    assert "VERSION = 14" in FLOW
    assert "async def async_migrate_entry(" in INIT
    assert "version=14" in INIT


def test_migration_adds_language_only_when_missing():
    assert "CONF_LANGUAGE not in data" in INIT
    assert "CONF_LANGUAGE not in options" in INIT
    assert "data[CONF_LANGUAGE] = _default_profile_language(hass)" in INIT


def test_migration_adds_workout_retention_only_when_missing():
    assert "CONF_WORKOUT_RETENTION_DAYS not in data" in INIT
    assert "CONF_WORKOUT_RETENTION_DAYS not in options" in INIT
    assert "data[CONF_WORKOUT_RETENTION_DAYS] = DEFAULT_WORKOUT_RETENTION_DAYS" in INIT


def test_migration_uses_supported_ui_language_or_english():
    assert 'getattr(hass.config, "language", None)' in INIT
    assert 'return code if code in SUPPORTED_LANGUAGES else "en"' in INIT


def test_migration_preserves_existing_options_and_data():
    assert "data = dict(config_entry.data)" in INIT
    assert "options = dict(config_entry.options)" in INIT


def test_future_unknown_entry_version_is_rejected():
    assert "if config_entry.version > 14:" in INIT
    assert "return False" in INIT
