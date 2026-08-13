"""Global Fitness live-adapter enable/disable controls."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .live import get_live_runtime


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = get_live_runtime(hass)
    # One entity set owns global infrastructure, not one set per person.
    if next(iter(runtime.profile_entries), None) != entry.entry_id:
        return
    async_add_entities(
        [AdapterEnabledSwitch(runtime, entry, transport) for transport in sorted(runtime.configured_transports)]
    )


class AdapterEnabledSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Enabled"
    _attr_icon = "mdi:access-point-network"

    def __init__(self, runtime, entry, transport: str):
        self.runtime = runtime
        self.entry = entry
        self.transport = transport
        self._attr_unique_id = f"fitness_{transport}_adapter_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"live_adapter:{transport}")},
            name=f"Fitness {transport.upper()} Adapter",
            manufacturer="Fitness",
            model=f"{transport.upper()} live transport",
        )

    @property
    def is_on(self):
        return self.runtime.adapter_enabled(self.transport)

    @property
    def available(self):
        # Never let infrastructure configuration tear a receiver out from under
        # an active workout or HR-recovery lease.
        return not self.runtime.transport_in_use(self.transport)

    async def _reload_profiles(self):
        # Platforms differ when the last adapter is disabled/enabled, so refresh
        # every profile after the global module set has changed.
        for entry_id in list(self.runtime.profile_entries):
            await self.hass.config_entries.async_reload(entry_id)

    async def async_turn_on(self, **kwargs):
        del kwargs
        await self.runtime.async_set_transport_enabled(self.transport, True)
        self.async_write_ha_state()
        self.hass.async_create_task(self._reload_profiles())

    async def async_turn_off(self, **kwargs):
        del kwargs
        if self.runtime.transport_in_use(self.transport):
            return
        await self.runtime.async_set_transport_enabled(self.transport, False)
        self.async_write_ha_state()
        self.hass.async_create_task(self._reload_profiles())
