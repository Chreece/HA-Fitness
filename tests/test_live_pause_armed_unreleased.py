from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "custom_components/fitness/manager.py"
BUTTON = ROOT / "custom_components/fitness/button.py"

def test_waiting_session_can_pause_resume_and_not_autostart_while_paused():
    manager = MANAGER.read_text(encoding="utf-8")
    button = BUTTON.read_text(encoding="utf-8")
    assert "not self.session_armed or self.session_active or self.session_paused" in manager
    assert "self.session_armed and not self.session_active" in manager
    assert "self.session_paused and (self.session_active or self.session_armed)" in manager
    assert "self.manager.session_active or self.manager.session_armed" in button
    assert "and not self.manager.session_armed" in button
    assert "self.session_armed = False\n            self.session_paused = False" in manager
    assert manager.count("self._notify_live()") >= 4

def test_session_status_native_states_are_translated():
    import json

    strings = json.loads((ROOT / "custom_components/fitness/strings.json").read_text(encoding="utf-8"))
    greek = json.loads((ROOT / "custom_components/fitness/translations/el.json").read_text(encoding="utf-8"))

    english_states = strings["entity"]["sensor"]["session_status"]["state"]
    greek_states = greek["entity"]["sensor"]["session_status"]["state"]

    assert english_states["waiting_for_live_data"] == "Waiting for live data"
    assert english_states["paused"] == "Paused"
    assert greek_states["waiting_for_live_data"] == "Αναμονή ζωντανών δεδομένων"
    assert greek_states["paused"] == "Σε παύση"

def test_start_publishes_waiting_state_before_live_transport_prepare():
    manager = MANAGER.read_text(encoding="utf-8")
    start = manager.index("async def async_start_session")
    body = manager[start : start + 5000]
    armed = body.index("self.session_armed = True")
    waiting = body.index("self._queue_session_status_waiting_red()")
    notify = body.index("self._notify_live()", waiting)
    prepare = body.index("await get_live_runtime(self.hass).async_prepare_session")
    assert armed < waiting < notify < prepare
