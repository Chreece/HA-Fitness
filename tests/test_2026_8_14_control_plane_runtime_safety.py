"""Regression guards for radio/control-plane isolation."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components/fitness"
RUNTIME = (FIT / "live/runtime.py").read_text(encoding="utf-8")
MANAGER = (FIT / "manager.py").read_text(encoding="utf-8")
SENSOR = (FIT / "sensor.py").read_text(encoding="utf-8")
ANT = (FIT / "live/antplus.py").read_text(encoding="utf-8")
ANT_ADAPTER = (FIT / "live/antplus_core/adapter.py").read_text(encoding="utf-8")
REMOTE = (FIT / "live/antplus_core/remote.py").read_text(encoding="utf-8")


def _method_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(name)


def test_presence_change_never_reloads_hub_or_profiles():
    method = _method_source(RUNTIME, "set_adapter_presence")
    assert "request_hub_reload" not in method
    assert "async_reload" not in method
    assert "_schedule_profile_reloads" not in method
    assert "self._notify()" in method


def test_presence_poll_does_not_reconcile_ant_registry_topology():
    method = _method_source(RUNTIME, "_start_presence_monitor")
    assert "ensure_ant_receiver_topology()" not in method


def test_volatile_endpoint_refresh_preserves_availability_notifications_without_registry_work():
    method = _method_source(RUNTIME, "refresh_transport_endpoint")
    assert "endpoint.last_seen = last_seen" in method
    assert "endpoint.available = bool(available)" in method
    assert 'dirty.add((sensor_id, "availability", None))' in method
    assert "_notify_values_throttled(dirty)" in method
    assert "device_registry" not in method
    assert "entity_registry" not in method
    assert "_schedule_save" not in method


def test_loaded_ant_provider_is_presence_authority_without_second_sysfs_scan():
    method = _method_source(RUNTIME, "async_refresh_adapter_presence")
    assert 'adapter_manager = getattr(ant_provider, "adapter_manager", None)' in method
    assert "any(record.available for record in adapter_manager.records.values())" in method
    provider_branch = method.split("if adapter_manager is not None:", 1)[1].split("else:", 1)[0]
    assert "_async_scan_local_ant_usb" not in provider_branch


def test_completed_workout_discovery_really_happens_after_debounce():
    schedule = _method_source(MANAGER, "_schedule_external_workout_recheck")
    assert "latest_workout()" not in schedule
    assert "_workout_signature" not in schedule
    settled = _method_source(MANAGER, "_async_process_external_workout_after_settle")
    assert settled.index("await asyncio.sleep(8)") < settled.index("latest = self.latest_workout()")


def test_profile_sensor_setup_has_one_whole_registry_scan():
    setup = _method_source(SENSOR, "async_setup_entry")
    assert setup.count("registry.entities.values()") == 1


def test_dynamic_sensor_materialization_is_coalesced_and_domain_scoped():
    setup = _method_source(SENSOR, "async_setup_entry")
    assert "pending_materialization_kinds" in setup
    assert "hass.loop.call_later(" in setup
    assert '{"workout", "evaluation"}' in setup
    assert '{"sleep", "evaluation"}' in setup
    assert '{"live"}' in setup


def test_ant_hardware_shutdown_does_not_block_ha_loop():
    assert "async def async_stop" in ANT_ADAPTER
    assert "async_add_executor_job(scanner.stop)" in ANT_ADAPTER
    bind = _method_source(ANT, "async_bind_hub")
    shutdown = _method_source(ANT, "async_shutdown")
    assert "await self.adapter_manager.async_stop()" in bind
    assert "await self.adapter_manager.async_stop()" in shutdown
    assert "await self.hass.async_add_executor_job(self.receiver.diagnostics.stop)" in shutdown
    remote_stop = _method_source(REMOTE, "stop")
    assert ".join(" not in remote_stop


def test_internal_ant_identity_persistence_suppresses_config_reload():
    method = _method_source(ANT_ADAPTER, "_persist_record")
    assert "runtime.suppress_entry_reload_once(self.entry.entry_id)" in method
    assert method.index("suppress_entry_reload_once") < method.index("async_update_entry")
