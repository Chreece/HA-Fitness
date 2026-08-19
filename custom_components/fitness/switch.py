"""Per-physical-adapter controls for Fitness protocols."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .live import get_live_runtime
from .live.runtime import HUB_ENTRY_TYPE


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = get_live_runtime(hass)
    if entry.data.get("entry_type") != HUB_ENTRY_TYPE:
        return

    materialized: set[tuple[str, str]] = set()

    def _add_physical_adapter_controls() -> None:
        added = []
        ant_records = runtime.ant_receiver_records() if runtime.adapter_configured("antplus") else {}
        for stable_key in sorted(ant_records):
            token = ("antplus", stable_key)
            if token in materialized:
                continue
            materialized.add(token)
            added.extend(
                [
                    PhysicalAdapterEnabledSwitch(runtime, "antplus", stable_key),
                    PhysicalAdapterAutomaticScanSwitch(runtime, "antplus", stable_key),
                ]
            )
        if added:
            async_add_entities(added, config_subentry_id=runtime.adapter_subentry_id("antplus"))

        added = []
        bt_records = runtime.bluetooth_scanner_records() if runtime.adapter_configured("bluetooth") else {}
        for source in sorted(bt_records):
            token = ("bluetooth", source)
            if token in materialized:
                continue
            materialized.add(token)
            added.extend(
                [
                    PhysicalAdapterEnabledSwitch(runtime, "bluetooth", source),
                    PhysicalAdapterAutomaticScanSwitch(runtime, "bluetooth", source),
                ]
            )
        if added:
            async_add_entities(added, config_subentry_id=runtime.adapter_subentry_id("bluetooth"))

    _add_physical_adapter_controls()
    entry.async_on_unload(runtime.add_listener(_add_physical_adapter_controls))


class _PhysicalAdapterSwitch(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, runtime, transport: str, receiver_id: str):
        self.runtime = runtime
        self.transport = transport
        self.receiver_id = receiver_id
        self._attr_device_info = (
            runtime.ant_receiver_device_info(receiver_id)
            if transport == "antplus"
            else runtime.bluetooth_scanner_device_info(receiver_id)
        )

    async def async_added_to_hass(self):
        self.async_on_remove(self.runtime.add_listener(self._update))

    def _update(self):
        self.async_write_ha_state()


class PhysicalAdapterEnabledSwitch(_PhysicalAdapterSwitch):
    """Enable one physical radio adapter for Fitness."""

    _attr_name = "Enabled"
    _attr_icon = "mdi:access-point-network"

    def __init__(self, runtime, transport: str, receiver_id: str):
        super().__init__(runtime, transport, receiver_id)
        self._attr_unique_id = f"fitness_{transport}_{receiver_id}_enabled"

    @property
    def is_on(self):
        if self.transport == "antplus":
            record = self.runtime.ant_receiver_records().get(self.receiver_id)
            if record is not None:
                return bool(record.desired_capture)
        return self.runtime.receiver_enabled(self.transport, self.receiver_id)

    async def async_turn_on(self, **kwargs):
        del kwargs
        await self.runtime.async_set_receiver_enabled(self.transport, self.receiver_id, True)

    async def async_turn_off(self, **kwargs):
        del kwargs
        await self.runtime.async_set_receiver_enabled(self.transport, self.receiver_id, False)


class PhysicalAdapterAutomaticScanSwitch(_PhysicalAdapterSwitch):
    """Control automatic new-device discovery through one physical adapter."""

    _attr_name = "Automatic scan"
    _attr_icon = "mdi:radar"

    def __init__(self, runtime, transport: str, receiver_id: str):
        super().__init__(runtime, transport, receiver_id)
        self._attr_unique_id = f"fitness_{transport}_{receiver_id}_automatic_scan"

    @property
    def is_on(self):
        return self.runtime.receiver_automatic_scan(self.transport, self.receiver_id)

    @property
    def available(self):
        return self.runtime.receiver_enabled(self.transport, self.receiver_id)

    async def async_turn_on(self, **kwargs):
        del kwargs
        await self.runtime.async_set_receiver_automatic_scan(self.transport, self.receiver_id, True)

    async def async_turn_off(self, **kwargs):
        del kwargs
        await self.runtime.async_set_receiver_automatic_scan(self.transport, self.receiver_id, False)
