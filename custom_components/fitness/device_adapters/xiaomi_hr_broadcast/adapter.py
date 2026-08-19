"""Discovery and guided setup for Xiaomi bands exposing standard BLE HR broadcast."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ...device_user_action import clear_device_user_action, request_device_user_action
from ..base import BluetoothArchiveAdapterSpec

BASE = "0000{}-0000-1000-8000-00805f9b34fb"
SERVICE_HR = BASE.format("180d")
ACTION_ENABLE_HR = "enable_heart_rate_broadcast"


@dataclass(slots=True, frozen=True)
class BroadcastModel:
    adapter_id: str
    model_id: str
    model: str
    names: tuple[str, ...]
    instructions: tuple[str, ...]


_MODELS: tuple[BroadcastModel, ...] = (
    BroadcastModel(
        "xiaomi_smart_band10_hr",
        "smart_band_10",
        "Xiaomi Smart Band 10",
        ("xiaomi smart band 10", "smart band 10"),
        (
            "On the band, open the app list.",
            "Open Settings, then Share HR.",
            "Turn Share HR on.",
            "Keep the band near Home Assistant and close Mi Fitness if it is holding the Bluetooth connection.",
            "Wait a few seconds. Fitness will use the standard Bluetooth Heart Rate Service automatically when it appears.",
        ),
    ),
    BroadcastModel(
        "xiaomi_smart_band10_pro_hr",
        "smart_band_10_pro",
        "Xiaomi Smart Band 10 Pro",
        ("xiaomi smart band 10 pro", "smart band 10 pro"),
        (
            "On the band, open Settings.",
            "Enable Bluetooth heart-rate sharing / Share HR.",
            "Keep the band near Home Assistant and close Mi Fitness if it is holding the Bluetooth connection.",
            "Wait a few seconds. Fitness will use the standard Bluetooth Heart Rate Service automatically when it appears.",
        ),
    ),
)


def _clean(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


class XiaomiHrBroadcastCoordinator:
    """Control-plane coordinator; standard live HR remains owned by BLE provider."""

    def __init__(self, provider, model: BroadcastModel) -> None:
        self.provider = provider
        self.runtime = provider.runtime
        self.hass = provider.hass
        self.model = model
        self.adapter_id = model.adapter_id

    async def async_setup(self) -> None:
        return None

    async def async_shutdown(self) -> None:
        return None

    def _sensor(self, sensor_id: str):
        return self.runtime.sensors.get(self.runtime.resolve_sensor_id(sensor_id))

    def _active(self, sensor_id: str) -> bool:
        sensor = self._sensor(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        return bool(endpoint and endpoint.metadata.get("hr_broadcast_active"))

    def _request(self, sensor_id: str) -> None:
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self._sensor(canonical)
        device = sensor.label() if sensor is not None else self.model.model
        request_device_user_action(
            self.hass,
            adapter_id=self.adapter_id,
            sensor_id=canonical,
            device=device,
            action=ACTION_ENABLE_HR,
            reason=(
                "Fitness recognized this Xiaomi band, but its standard Bluetooth "
                "heart-rate broadcast is not active."
            ),
            instructions=self.model.instructions,
        )

    def _clear(self, sensor_id: str) -> None:
        clear_device_user_action(
            self.hass,
            adapter_id=self.adapter_id,
            sensor_id=self.runtime.resolve_sensor_id(sensor_id),
            action=ACTION_ENABLE_HR,
        )

    def advertise(self, sensor_id: str, identity: dict[str, Any]) -> None:
        if identity.get("hr_broadcast_active"):
            self._clear(sensor_id)
        elif self.runtime.sensor_is_accepted(self.runtime.resolve_sensor_id(sensor_id)):
            self._request(sensor_id)

    def acceptance_changed(self, sensor_id: str, accepted: bool) -> None:
        if not accepted:
            self._clear(sensor_id)
        elif self._active(sensor_id):
            self._clear(sensor_id)
        else:
            self._request(sensor_id)

    def assignment_changed(self, sensor_id: str) -> None:
        if self.runtime.sensor_is_accepted(self.runtime.resolve_sensor_id(sensor_id)) and not self._active(sensor_id):
            self._request(sensor_id)

    def forget_sensor(self, sensor_id: str) -> None:
        self._clear(sensor_id)

    def identity_conflict_repaired(self, sensor_id: str) -> None:
        self._clear(sensor_id)


class _CoordinatorFactory:
    def __init__(self, model: BroadcastModel) -> None:
        self.model = model

    def __call__(self, provider):
        return XiaomiHrBroadcastCoordinator(provider, self.model)


def _spec(model: BroadcastModel) -> BluetoothArchiveAdapterSpec:
    def matchers() -> tuple[BluetoothCallbackMatcher, ...]:
        return tuple(BluetoothCallbackMatcher(local_name=name, connectable=False) for name in model.names)

    def match(
        name: str | None,
        service_uuids: Iterable[str],
        manufacturer_data: dict[int, bytes] | None,
    ) -> dict[str, Any] | None:
        del manufacturer_data
        normalized = _clean(name)
        if normalized not in model.names:
            return None
        services = {str(value).strip().lower() for value in (service_uuids or ())}
        return {
            "archive_adapter": model.adapter_id,
            "archive_compatible": False,
            "workout_archive": False,
            "manufacturer": "Xiaomi",
            "fitness_vendor_identity": "xiaomi",
            "model": model.model,
            "model_id": model.model_id,
            "smart_device_default_type": "fitness_tracker",
            "live_standard_profile": "bluetooth_heart_rate",
            "hr_broadcast_active": SERVICE_HR in services,
            "setup_requires_user_action": SERVICE_HR not in services,
        }

    return BluetoothArchiveAdapterSpec(
        adapter_id=model.adapter_id,
        coordinator_factory=_CoordinatorFactory(model),
        bluetooth_matchers=matchers,
        match_bluetooth=match,
        advertisement_capabilities=frozenset(),
        sync_capabilities=frozenset(),
        generic_identity_probe=True,
    )


ARCHIVE_ADAPTERS = tuple(_spec(model) for model in _MODELS)
