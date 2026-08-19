"""Fitness control buttons."""

import asyncio
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify

from .const import DOMAIN
from .entity import device_info
from .live import get_live_runtime

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = get_live_runtime(hass)
    from .live.runtime import HUB_ENTRY_TYPE

    if entry.data.get("entry_type") == HUB_ENTRY_TYPE:
        for transport in sorted(runtime.adapter_entity_transports):
            async_add_entities(
                [AdapterScanNowButton(runtime, transport)],
                config_subentry_id=runtime.adapter_subentry_id(transport),
            )

        # Normal live transport is automatic. Archive-capable adapters expose one
        # generic explicit retry action in addition to automatic reconnect policy.
        materialized: set[str] = set()
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(hass)

        def _repair_cross_sensor_archive_button_entity_id(
            sensor_id: str, sensor, action, unique_id: str
        ) -> None:
            """Repair an integration-generated button named for another sensor.

            Home Assistant intentionally keeps entity IDs stable when a device is
            renamed.  That is normally desirable.  The exception repaired here is
            cross-device contamination: the unique ID belongs to this physical
            sensor, but its entity ID starts with the name of a *different* live
            sensor currently known to Fitness.  User-chosen/arbitrary IDs are left
            untouched.
            """
            entity_id = entity_registry.async_get_entity_id(
                "button", DOMAIN, unique_id
            )
            if entity_id is None or "." not in entity_id:
                return
            current_slug = slugify(str(getattr(sensor, "name", "") or ""))
            if not current_slug:
                return
            object_id = entity_id.split(".", 1)[1]
            if object_id == current_slug or object_id.startswith(f"{current_slug}_"):
                return
            other_slugs = {
                slugify(str(other.name or ""))
                for other in runtime.sensors.values()
                if runtime.resolve_sensor_id(other.sensor_id) != sensor_id
                and str(other.name or "").strip()
            }
            if not any(
                object_id == stale or object_id.startswith(f"{stale}_")
                for stale in other_slugs
                if stale
            ):
                return
            action_slug = slugify(
                str(getattr(action, "unique_suffix", "archive_sync") or "archive_sync")
            )
            desired = f"button.{current_slug}_{action_slug}"
            if desired == entity_id or entity_registry.async_get(desired) is not None:
                return
            entity_registry.async_update_entity(entity_id, new_entity_id=desired)

        def _collect_archive_buttons() -> None:
            provider = runtime.providers.get("bluetooth")
            registry = getattr(provider, "device_archives", None) if provider else None
            if registry is None:
                return
            added = []
            accepted_markers: set[str] = set()
            candidates: list[tuple[str, object, object]] = []
            for sensor in runtime.sensors.values():
                sensor_id = runtime.resolve_sensor_id(sensor.sensor_id)
                endpoint = sensor.endpoints.get("bluetooth")
                metadata = endpoint.metadata if endpoint is not None else {}
                action = registry.sync_action_for_metadata(metadata)
                if action is None:
                    continue
                marker = f"{sensor_id}:{action.adapter_id}"
                if runtime.sensor_is_accepted(sensor_id):
                    accepted_markers.add(marker)
                candidates.append((sensor_id, sensor, action))

            materialized.intersection_update(accepted_markers)
            for sensor_id, sensor, action in candidates:
                marker = f"{sensor_id}:{action.adapter_id}"
                unique_id = f"fitness_{sensor_id}_{action.unique_suffix}"
                _repair_cross_sensor_archive_button_entity_id(
                    sensor_id, sensor, action, unique_id
                )
                if marker in materialized:
                    if entity_registry.async_get_entity_id("button", DOMAIN, unique_id) is not None:
                        continue
                    materialized.discard(marker)
                # Manual archive retry must exist before capability verification.
                # Secure adapters may only grant workout_history after
                # the first successful protocol handshake; hiding the button until
                # then creates a circular dependency where users cannot retry the
                # handshake that grants the capability.
                if not runtime.sensor_is_accepted(sensor_id):
                    continue
                materialized.add(marker)
                added.append(ArchiveSyncWorkoutsButton(runtime, sensor_id, action))
            if added:
                subentry = runtime.ensure_sensors_subentry()
                async_add_entities(
                    added,
                    config_subentry_id=(
                        subentry.subentry_id if subentry is not None else None
                    ),
                )

        _collect_archive_buttons()
        entry.async_on_unload(runtime.add_structure_listener(_collect_archive_buttons))
        return

    manager = hass.data[DOMAIN][entry.entry_id]
    # Live controls are stable profile infrastructure. Sensor assignment only
    # changes availability/routing; it must never require a profile reload just
    # to create or remove controls.
    entities = [
        StartWorkoutButton(manager, entry),
        PauseWorkoutButton(manager, entry),
        ResumeWorkoutButton(manager, entry),
        StopWorkoutButton(manager, entry),
    ]
    if manager.config.get("ai_enabled"):
        entities.append(RegenerateEvaluationButton(manager, entry))
    async_add_entities(entities)


class AdapterScanNowButton(ButtonEntity):
    """Run one bounded adapter-owned discovery refresh on explicit request."""

    _attr_has_entity_name = True
    _attr_translation_key = "adapter_scan_now"
    _attr_icon = "mdi:radar"

    def __init__(self, runtime, transport: str):
        self.runtime = runtime
        self.transport = transport
        self._running = False
        self._attr_unique_id = f"fitness_{transport}_adapter_scan_now"
        self._attr_device_info = runtime.adapter_device_info(transport)

    async def async_added_to_hass(self):
        self.async_on_remove(self.runtime.add_listener(self._update))

    def _update(self):
        self.async_write_ha_state()

    @property
    def available(self):
        return bool(
            self.runtime.adapter_enabled(self.transport)
            and not self.runtime.transport_in_use(self.transport)
            and not self._running
        )

    async def async_press(self):
        if not self.available:
            return
        self._running = True
        self.async_write_ha_state()
        try:
            async with asyncio.timeout(15.0):
                provider = self.runtime.providers.get(self.transport)
                if self.transport == "bluetooth":
                    refresh = getattr(provider, "async_refresh_discovery", None)
                    if refresh is not None:
                        await refresh()
                elif self.transport == "antplus":
                    manager = getattr(provider, "adapter_manager", None)
                    refresh = getattr(manager, "async_refresh_local", None)
                    if refresh is not None:
                        await refresh()
                await self.runtime.async_refresh_adapter_presence()
        except TimeoutError:
            # Scanning is a best-effort control-plane action. Runtime/provider
            # diagnostics expose any durable adapter problem; never block HA.
            _LOGGER.debug("Fitness %s adapter scan timed out", self.transport)
        except Exception as err:  # noqa: BLE001 - user action must not destabilize HA
            _LOGGER.debug(
                "Fitness %s adapter scan failed: %s",
                self.transport,
                err,
            )
        finally:
            self._running = False
            self.async_write_ha_state()


class BaseFitnessButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, manager, entry):
        self.manager = manager
        self.entry = entry
        self.runtime = get_live_runtime(manager.hass)

    async def async_added_to_hass(self):
        self.async_on_remove(self.manager.add_listener(self._update))

    def _update(self):
        self.async_write_ha_state()


class ArchiveSyncWorkoutsButton(ButtonEntity):
    """Request an immediate adapter-owned archive retry without blocking HA."""

    _attr_has_entity_name = True

    def __init__(self, runtime, sensor_id: str, action):
        self.runtime = runtime
        self.sensor_id = runtime.resolve_sensor_id(sensor_id)
        self.action = action
        self._attr_translation_key = action.translation_key
        self._attr_icon = action.icon
        self._attr_unique_id = f"fitness_{self.sensor_id}_{action.unique_suffix}"
        self._attr_device_info = runtime.sensor_device_info(self.sensor_id)
        self._attr_extra_state_attributes = {
            "sync_scope": "full",
            "sync_capabilities": sorted(action.capabilities),
        }

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.runtime.add_sensor_value_listener(
                self.sensor_id, "availability", None, self._update
            )
        )
        self.async_on_remove(self.runtime.add_structure_listener(self._update))

    def _update(self):
        self.async_write_ha_state()

    def _coordinator(self):
        self.sensor_id = self.runtime.resolve_sensor_id(self.sensor_id)
        sensor = self.runtime.sensors.get(self.sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        provider = self.runtime.providers.get("bluetooth")
        registry = getattr(provider, "device_archives", None) if provider else None
        if endpoint is None or registry is None:
            return None
        return registry.coordinator_for_metadata(endpoint.metadata)

    @property
    def available(self):
        self.sensor_id = self.runtime.resolve_sensor_id(self.sensor_id)
        sensor = self.runtime.sensors.get(self.sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        return bool(
            sensor
            and endpoint is not None
            and endpoint.metadata.get("archive_compatible") is not False
            and self._coordinator() is not None
            and self.runtime.sensor_is_accepted(self.sensor_id)
            and self.runtime.sensor_assigned_profile_ids(self.sensor_id)
        )

    async def async_press(self):
        coordinator = self._coordinator()
        if coordinator is None:
            return
        sync_now = getattr(coordinator, "async_sync_now", None)
        if callable(sync_now):
            await sync_now(self.sensor_id)
            return
        coordinator.schedule(self.sensor_id, delay=0.0, force=True)


class BaseLiveFitnessButton(BaseFitnessButton):
    """Profile Live control updated only by the bounded live notification path."""

    async def async_added_to_hass(self):
        self.async_on_remove(self.manager.add_live_listener(self._update))


class StartWorkoutButton(BaseLiveFitnessButton):
    _attr_translation_key = "start_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_start_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return bool(
            self.runtime.profile_has_assigned_live_sensor(self.entry)
            and not self.manager.session_active
            and not self.manager.session_armed
        )

    async def async_press(self):
        await self.manager.async_start_session()


class PauseWorkoutButton(BaseLiveFitnessButton):
    _attr_translation_key = "pause_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_pause_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return bool((self.manager.session_active or self.manager.session_armed) and not self.manager.session_paused)

    async def async_press(self):
        await self.manager.async_pause_session()


class ResumeWorkoutButton(BaseLiveFitnessButton):
    _attr_translation_key = "resume_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_resume_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return bool((self.manager.session_active or self.manager.session_armed) and self.manager.session_paused)

    async def async_press(self):
        await self.manager.async_resume_session()


class StopWorkoutButton(BaseLiveFitnessButton):
    _attr_translation_key = "stop_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_stop_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return self.manager.session_active or self.manager.session_armed

    async def async_press(self):
        await self.manager.async_stop_session()


class RegenerateEvaluationButton(BaseFitnessButton):
    _attr_translation_key = "regenerate_ai_evaluation"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_regenerate_ai"
        self._attr_device_info = device_info(entry, "evaluation")

    async def async_press(self):
        await self.manager.async_generate_ai(
            general=True, workout=True, raise_on_failure=True
        )
