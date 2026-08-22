from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEALTH = (ROOT / "custom_components/fitness/health_catalog.py").read_text(encoding="utf-8")
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
BANGLE_ADAPTER = (ROOT / "custom_components/fitness/device_adapters/bangle/adapter.py").read_text(encoding="utf-8")
BANGLE = (ROOT / "custom_components/fitness/device_adapters/bangle/coordinator.py").read_text(encoding="utf-8")
GARMIN = (ROOT / "custom_components/fitness/device_adapters/garmin/coordinator.py").read_text(encoding="utf-8")
GARMIN_FIT_PATH = ROOT / "custom_components/fitness/device_adapters/garmin/fit.py"


def _dict_string_keys(source: str, assignment: str) -> set[str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == assignment:
            assert isinstance(node.value, ast.Dict)
            return {key.value for key in node.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == assignment for t in node.targets):
            assert isinstance(node.value, ast.Dict)
            return {key.value for key in node.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
    raise AssertionError(f"missing {assignment}")


def test_every_named_direct_device_metric_has_a_canonical_health_sensor():
    catalog = set(re.findall(r'HealthMetricSpec\("([a-z0-9_]+)"', HEALTH))
    sensor_metrics = set(re.findall(r'^\s*\("([a-z0-9_]+)",\s*"[^\n]+?",\s*(?:"[^\n]*?"|None)\),$', SENSOR, re.M))
    aliases = dict(re.findall(r'^\s*"([a-z0-9_]+)":\s*"([a-z0-9_]+)",$', HEALTH, re.M))

    emitted: set[str] = set()
    for path in (ROOT / "custom_components/fitness/device_adapters").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        emitted.update(re.findall(r'DeviceMetricPoint\(\s*"([a-z0-9_]+)"', source))
    emitted.update(_dict_string_keys(GARMIN_FIT_PATH.read_text(encoding="utf-8"), "_GENERIC_WELLNESS_FIELDS"))

    canonical_emitted = {aliases.get(metric, metric) for metric in emitted}
    assert canonical_emitted <= catalog
    assert catalog <= sensor_metrics
    assert {"steps", "spo2", "moderate_minutes", "vigorous_minutes", "sleep_score", "floors_climbed"} <= catalog
    assert "MAX_DEVICE_INTRADAY_METRICS = 64" in MANAGER
    assert '"moderate_minutes", "vigorous_minutes", "floors_climbed"' in MANAGER


def test_wellness_entities_are_data_driven_and_add_no_device_io():
    assert "WELLNESS_DESCRIPTIONS" in SENSOR
    assert 'if manager.device_intraday_history.get(desc.metric) or manager.metric_history.get(desc.metric)' in SENSOR
    assert 'if self.entity_description.kind == "wellness":' in SENSOR
    assert "No read here" in SENSOR
    assert "WELLNESS_ADDITIVE_METRICS" in SENSOR
    assert "SensorStateClass.TOTAL_INCREASING" in SENSOR


def test_modern_wellness_card_and_empty_card_reflow_contract():
    assert "class FitnessWellnessCard" in FRONTEND
    assert "device_moderate_minutes" in FRONTEND
    assert "device_vigorous_minutes" in FRONTEND
    assert "device_sleep_score" in FRONTEND
    assert 'emptyPreview.className = "fitness-empty-preview"' in FRONTEND
    assert 'wrapper.classList.toggle("fitness-empty-card", !hasInformation)' in FRONTEND
    assert ".fitness-empty-card{display:none!important}" in FRONTEND
    assert ":host([layout-editing]) .tv-card-slot.fitness-empty-card" in FRONTEND
    assert "new MutationObserver(syncInformation)" in FRONTEND


def test_remote_subdomain_identity_language_and_request_security_are_server_enforced():
    assert "SUPPORTED_LANGUAGES" in ACCOUNTS
    assert "_PORTAL_LOGIN_TEXT" in ACCOUNTS
    assert 'remote_account = controller.account_by_remote_host(request.host)' in ACCOUNTS
    assert "Never accept a username override from a modified form" in ACCOUNTS
    assert 'language=language' in ACCOUNTS
    assert 'labels:p?.labels_by_language?.[lang]' in ACCOUNTS
    assert 'usb=(self), bluetooth=(self)' in ACCOUNTS
    assert 'if origin:\n        return _matches(origin)' in ACCOUNTS
    assert 'if referer:\n        return _matches(referer)' in ACCOUNTS
    assert '_host_only(parsed.netloc) == request_host' in ACCOUNTS
    assert "async def _bounded_form_body" in ACCOUNTS
    assert "async def _bounded_json_body" in ACCOUNTS
    assert 'Cross-Origin-Resource-Policy' in ACCOUNTS
    assert 'X-Permitted-Cross-Domain-Policies' in ACCOUNTS


def test_bangle_is_a_bounded_explicit_local_workout_writer_and_garmin_is_still_read_only():
    assert '"workout_delivery"' in BANGLE_ADAPTER
    assert "async def async_write_workout" in BANGLE
    assert 'require("Storage").write' in BANGLE
    assert "MAX_WORKOUT_FILE_BYTES = 48 * 1024" in BANGLE
    assert "[:64]" in BANGLE
    assert "asyncio.timeout(SESSION_TIMEOUT)" in BANGLE
    assert "asyncio.timeout(CONNECT_TIMEOUT)" in BANGLE
    assert 'reason="bangle_js workout delivery cleanup"' in BANGLE
    assert "async def async_write_workout" not in GARMIN


def test_all_fitness_designed_workout_surfaces_offer_real_export_when_writable():
    assert "class FitnessTestsCard" in FRONTEND
    assert "class FitnessAiTodayCard" in FRONTEND
    assert "class FitnessTrainingPlanCard" in FRONTEND
    assert '_fitnessWorkoutExportTarget' in FRONTEND
    assert FRONTEND.count('type:"fitness/training/export"') >= 3
    assert 'daily_ai:true' in FRONTEND
    export_targets = DASHBOARD[DASHBOARD.index("async def websocket_training_export_targets"):DASHBOARD.index("async def websocket_training_export", DASHBOARD.index("async def websocket_training_export_targets") + 10)]
    assert "async_control_profile_ids" in export_targets
    assert "Fitness profile control required" in export_targets


def test_tv_cast_has_one_hidden_outer_scroll_surface_and_nested_plugin_rows_do_not_scroll():
    assert ':host([fitness-cast-receiver]){overflow:hidden!important}' in FRONTEND
    assert ':host([fitness-cast-receiver]) ha-card.tv-shell{height:100dvh;max-height:100dvh;overflow-y:auto!important;overflow-x:hidden!important' in FRONTEND
    assert ':host([fitness-cast-receiver]) ha-card.tv-shell{scrollbar-width:none;scrollbar-gutter:auto!important}' in FRONTEND
    assert ':host([fitness-cast-receiver]) ha-card.tv-shell::-webkit-scrollbar{display:none}' in FRONTEND
    assert '.rows{display:grid;gap:6px;max-height:none;overflow:visible}' in FRONTEND
    assert '.tv-card-slot[data-manual-height]{height:auto!important;min-height:var(--fitness-manual-card-height,120px)!important' in FRONTEND


def test_text_action_menus_wrap_and_backend_flow_keeps_last_line_reachable():
    for fragment in (
        '.cast-section-actions{display:flex;gap:8px;flex-wrap:wrap',
        '.remote-actions{display:flex;gap:8px;flex-wrap:wrap',
        '.flow-home{min-width:126px;max-width:min(240px,45vw);padding:7px 11px;font:inherit;white-space:normal',
        '.flow-actions{display:flex;justify-content:flex-end;align-items:center;align-self:stretch;gap:8px;margin-top:auto;position:sticky',
        '.flow-body{display:flex;flex-direction:column;align-items:stretch;gap:9px;padding:15px 15px max(22px,env(safe-area-inset-bottom))',
    ):
        assert fragment in FRONTEND


def test_frontend_cache_revision_is_consistent_for_this_feature_batch():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert '?v=unreleased-138' in DASHBOARD
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS


def test_remote_browser_gateway_is_permission_checked_and_resource_bounded():
    remote = (ROOT / "custom_components/fitness/remote_gateway.py").read_text(encoding="utf-8")
    assert "REMOTE_BLE_DEVICE_LIMIT = 256" in remote
    assert "REMOTE_BLE_STALE_SECONDS = 300.0" in remote
    assert "REMOTE_ASSIGNMENT_GATEWAY_LIMIT = 16" in remote
    assert "REMOTE_ASSIGNMENT_DEVICE_LIMIT = 512" in remote
    assert "async_require_profile_control" in remote
    assert "bounded_websocket_payload(max_nodes=512, max_depth=4, max_string_length=1_024)" in remote
    assert '"adapter_id": f"webusb:{gateway_id}"' in remote
    assert "client cannot invent an" in remote
    assert "for service_uuids" not in remote  # bounded islice is used instead of unbounded client iteration
    assert "islice(service_uuids, 64)" in remote
    assert "islice(characteristic_uuids, 64)" in remote
