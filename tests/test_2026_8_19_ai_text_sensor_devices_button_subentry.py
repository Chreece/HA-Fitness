from pathlib import Path

ROOT = Path(__file__).parents[1]
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text()
BUTTON = (ROOT / "custom_components/fitness/button.py").read_text()

def test_ai_plan_and_live_analysis_are_text_sensors_not_measurements():
    textual = SENSOR[SENSOR.index("textual = {"):SENSOR.index("if self.entity_description.metric in textual")]
    assert '"ai_daily_plan"' in textual
    assert '"ai_live_analysis"' in textual

def test_devices_hub_buttons_do_not_use_removed_legacy_sensor_subentry():
    block = BUTTON[BUTTON.index('if entry.data.get("entry_type") == DEVICES_HUB_ENTRY_TYPE:'):BUTTON.index('manager = hass.data[DOMAIN][entry.entry_id]', BUTTON.index('if entry.data.get("entry_type") == DEVICES_HUB_ENTRY_TYPE:'))]
    assert "ensure_sensors_subentry()" not in block
    assert "async_add_entities(added)" in block
