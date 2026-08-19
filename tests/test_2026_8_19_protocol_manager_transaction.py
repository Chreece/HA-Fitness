from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / 'custom_components/fitness/config_flow.py').read_text()
RUNTIME = (ROOT / 'custom_components/fitness/live/runtime.py').read_text()


def test_protocol_options_are_staged_until_manual_hardware_selection_finishes():
    assert 'self._pending_protocol_selection = selected' in FLOW
    assert 'self._pending_protocol_automatic = automatic' in FLOW
    assert 'return await self._async_finish_protocol_options(selected_hw)' in FLOW
    block = FLOW.split('async def async_step_protocols', 1)[1].split('async def async_step_protocol_hardware', 1)[0]
    assert 'await runtime.async_set_protocol_selection(selected)' not in block


def test_returning_to_protocol_form_uses_staged_manual_choice():
    assert 'pending_selected = getattr(self, "_pending_protocol_selection", None)' in FLOW
    assert 'pending_automatic = getattr(self, "_pending_protocol_automatic", None)' in FLOW
    assert 'bool(pending_automatic.get("bluetooth", True))' in FLOW


def test_protocol_commit_defers_reload_until_hardware_policy_is_saved():
    assert 'await runtime.async_set_protocol_selection(selected, reload=False)' in FLOW
    assert 'await runtime.async_refresh_modules()' in FLOW
    assert 'runtime.request_hub_reload()' in FLOW
    assert 'reload: bool = True' in RUNTIME
    assert 'if reload:' in RUNTIME
