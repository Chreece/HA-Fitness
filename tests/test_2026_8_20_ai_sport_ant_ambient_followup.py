from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus_core/adapter.py").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()


def test_ai_cards_keep_canonical_profile_id_and_visible_regeneration_state():
    assert 'this._profileId = String(this.config.profile_entry_id || "");' in JS
    assert 'this._profile?.entry_id||""' in JS
    assert 'regenerate:true' in JS
    assert 'ai-working-banner' in JS
    assert '700-(performance.now()-started)' in JS


def test_automatic_comparison_cards_are_strictly_grouped_by_sport():
    assert 'def workout_comparisons_by_sport(' in MANAGER
    assert 'if current_sport in generic or prev_sport != current_sport:' in MANAGER
    assert '"workout_comparisons": manager.workout_comparisons_by_sport()' in DASHBOARD
    assert 'const cards = hasExplicitMetrics' in JS
    assert ': this._renderSportGroups(sportGroups);' in JS
    assert 'sport_${String(sport || "").toLowerCase()}' in JS


def test_remote_ant_uses_protocol_serial_and_migrates_usb_descriptor_aliases():
    assert 'await this._antRequestMessage(0x61)' in JS
    assert 'antplus_serial_source:protocolSerial ? "ant_protocol" : "usb_descriptor"' in JS
    assert 'antplus_usb_serial_number:usbSerial' in JS
    assert 'vol.Optional("antplus_serial_source")' in REMOTE
    assert 'vol.Optional("antplus_usb_serial_number")' in REMOTE
    assert 'serial_source: str | None = None' in ANT
    assert 'usb_serial: str | None = None' in ANT
    assert 'def _migrate_remote_adapter_alias(' in ANT
    assert 'adapter.serial_source != "ant_protocol"' in ANT


def test_non_cast_ambient_layer_is_viewport_fixed_not_content_height_bounded():
    assert '--fitness-dashboard-host-left' in JS
    assert ':host(:not([fitness-cast-receiver]))>.fitness-ambient-layer{position:fixed!important' in JS
    assert 'inset:var(--fitness-dashboard-host-top,0px) 0 0 var(--fitness-dashboard-host-left,0px)!important' in JS
