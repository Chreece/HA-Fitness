"""Global Fitness live-adapter enable/disable controls."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .live import get_live_runtime
from .live.runtime import HUB_ENTRY_TYPE


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = get_live_runtime(hass)
    if entry.data.get("entry_type") != HUB_ENTRY_TYPE:
        return
    async_add_entities(
        [AdapterEnabledSwitch(runtime, transport) for transport in sorted(runtime.configured_transports)]
    )


class AdapterEnabledSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Enabled"
    _attr_icon = "mdi:access-point-network"

    def __init__(self, runtime, transport: str):
        self.runtime = runtime
        self.transport = transport
        self._attr_unique_id = f"fitness_{transport}_adapter_enabled"
        self._attr_device_info = runtime.adapter_device_info(transport)

    @property
    def is_on(self):
        return self.runtime.adapter_enabled(self.transport)

    @property
    def available(self):
        return not self.runtime.transport_in_use(self.transport)

    async def async_turn_on(self, **kwargs):
        del kwargs
        await self.runtime.async_set_transport_enabled(self.transport, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        del kwargs
        if self.runtime.transport_in_use(self.transport):
            return
        await self.runtime.async_set_transport_enabled(self.transport, False)
        self.async_write_ha_state()
