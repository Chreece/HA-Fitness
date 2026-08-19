"""Small persistent credential vault for direct Fitness devices.

Home Assistant's integration storage is used rather than device metadata or
entity attributes so secret material is never exposed in the state machine.
Credentials are keyed by the canonical Fitness sensor id and adapter id.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_STORE_VERSION = 1
_STORE_KEY = "fitness_device_credentials"
_MAX_DEVICES = 128


class DeviceCredentialStore:
    """Lazily loaded persistent per-device credential store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(hass, _STORE_VERSION, _STORE_KEY, private=True)
        self._lock = asyncio.Lock()
        self._loaded = False
        self._data: dict[str, dict[str, dict[str, str]]] = {"devices": {}}

    async def _async_ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            loaded = await self._store.async_load() or {}
            devices = loaded.get("devices")
            if isinstance(devices, dict):
                self._data = {"devices": devices}
            self._loaded = True

    @staticmethod
    def _key(sensor_id: str, adapter_id: str) -> str:
        return f"{adapter_id}:{sensor_id}"

    async def async_get(self, sensor_id: str, adapter_id: str) -> dict[str, str]:
        await self._async_ensure_loaded()
        value = self._data.setdefault("devices", {}).get(self._key(sensor_id, adapter_id), {})
        return deepcopy(value) if isinstance(value, dict) else {}

    async def async_set(
        self,
        sensor_id: str,
        adapter_id: str,
        values: dict[str, Any],
    ) -> None:
        await self._async_ensure_loaded()
        clean = {
            str(key): str(value).strip()
            for key, value in values.items()
            if value is not None and str(value).strip()
        }
        async with self._lock:
            devices = self._data.setdefault("devices", {})
            devices[self._key(sensor_id, adapter_id)] = clean
            if len(devices) > _MAX_DEVICES:
                # Credential entries have no useful ordering metadata. Drop only
                # the oldest insertion-order keys and keep the current device.
                keep_key = self._key(sensor_id, adapter_id)
                for key in list(devices):
                    if len(devices) <= _MAX_DEVICES:
                        break
                    if key != keep_key:
                        devices.pop(key, None)
            await self._store.async_save(self._data)

    async def async_remove(self, sensor_id: str, adapter_id: str) -> None:
        await self._async_ensure_loaded()
        async with self._lock:
            if self._data.setdefault("devices", {}).pop(self._key(sensor_id, adapter_id), None) is not None:
                await self._store.async_save(self._data)


def async_get_device_credential_store(hass: HomeAssistant) -> DeviceCredentialStore:
    """Return the process-local credential store singleton."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    key = "_device_credential_store"
    store = domain_data.get(key)
    if not isinstance(store, DeviceCredentialStore):
        store = domain_data[key] = DeviceCredentialStore(hass)
    return store
