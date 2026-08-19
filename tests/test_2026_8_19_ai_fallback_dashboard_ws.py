"""Regressions for Fitness AI fail-closed routing and dashboard websocket setup."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components/fitness"
DASHBOARD = (BASE / "dashboard.py").read_text(encoding="utf-8")
MANAGER = (BASE / "manager.py").read_text(encoding="utf-8")


def test_dashboard_config_websocket_decorators_are_on_registered_handler():
    marker = '@websocket_api.websocket_command({vol.Required("type"): "fitness/dashboard/config"})\n@websocket_api.async_response\nasync def websocket_dashboard_config'
    assert marker in DASHBOARD
    helper_pos = DASHBOARD.index("def _dashboard_today_summary")
    assert "@websocket_api.websocket_command" not in DASHBOARD[max(0, helper_pos - 160):helper_pos]


def test_ai_selected_provider_failure_always_retries_ha_default():
    start = MANAGER.index("async def _call_ai_unlocked")
    end = MANAGER.index("def _ai_result_language_mismatch", start)
    block = MANAGER[start:end]
    assert 'configured_entity.startswith("conversation.")' in block
    assert 'configured_entity.startswith("ai_task.")' in block
    assert "fallback = await self._call_ai_task_service(prompt, task_name)" in block
    assert "self._disable_ai_runtime(task_name)" in block
    assert "self._report_ai_provider_unavailable" not in block


def test_ai_disables_runtime_after_default_also_fails():
    assert "self._ai_runtime_disabled = False" in MANAGER
    start = MANAGER.index("def _disable_ai_runtime")
    end = MANAGER.index("def _ai_result_language_mismatch", start)
    block = MANAGER[start:end]
    assert "self._ai_runtime_disabled = True" in block
    assert "_LOGGER.info(" in block
    assert "_LOGGER.warning(" not in block
