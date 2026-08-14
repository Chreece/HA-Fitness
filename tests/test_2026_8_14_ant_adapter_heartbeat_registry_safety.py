"""ANT gateway heartbeats must remain outside HA registry hot paths."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (ROOT / "custom_components/fitness/live/antplus_core/adapter.py").read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()


def test_adapter_device_registry_is_identity_gated():
    block = ADAPTER.split("def _merge_or_register_device", 1)[1].split(
        "def _ensure_record", 1
    )[0]
    assert "_registry_identity_cache" in block
    assert "if self._registry_identity_cache.get(adapter.stable_key) == signature:" in block
    assert "return" in block
    assert "self._registry_identity_cache[adapter.stable_key] = signature" in block


def test_remote_heartbeat_can_reuse_record_without_registry_mutation():
    ensure = ADAPTER.split("def _ensure_record", 1)[1].split(
        "async def async_start", 1
    )[0]
    assert "self._merge_or_register_device(adapter)" in ensure
    # _merge_or_register_device itself is now identity-gated before dr/er access.
    merge = ADAPTER.split("def _merge_or_register_device", 1)[1].split(
        "def _ensure_record", 1
    )[0]
    guard = merge.index("if self._registry_identity_cache.get(adapter.stable_key) == signature:")
    registry = merge.index("device_registry = dr.async_get(self.hass)")
    assert guard < registry


def test_adapter_callback_never_changes_capture_preference():
    block = ANT.split("def _adapter_changed", 1)[1].split(
        "@property", 1
    )[0]
    assert "async_set_capture" not in block
    assert "desired_capture" not in block


def test_provider_startup_restores_instead_of_forcing_capture_on():
    setup = ANT.split("async def _async_create_adapter_manager", 1)[1].split(
        "async def async_bind_hub", 1
    )[0]
    assert "await self._async_restore_receiver_states()" in setup
    assert "await self._async_enable_receivers()" not in setup

    restore = ANT.split("async def _async_restore_receiver_states", 1)[1].split(
        "async def _async_enable_receivers", 1
    )[0]
    assert "async_set_capture" not in restore
    assert "record.desired_capture" in restore
