from .const import DOMAIN
"""Fitness integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers import config_validation as cv
import importlib
import voluptuous as vol

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DAYS,
    CONF_LANGUAGE,
    CONF_PROFILE_NAME,
    CONF_WEIGHT,
    CONF_WEIGHT_SCALE_ENTITY,
    CONF_WORKOUT_RETENTION_DAYS,
    DEFAULT_WORKOUT_RETENTION_DAYS,
    DOMAIN,
    MAX_WORKOUT_RETENTION_DAYS,
    SERVICE_DELETE_WORKOUTS_BEFORE,
    SERVICE_CAST_TV_DASHBOARD,
    SERVICE_STOP_TV_DASHBOARD,
    SERVICE_START_TV_WORKOUT,
    SERVICE_TEST_TTS,
    SERVICE_AI_TTS,
    SERVICE_CLEAR_WORKOUT_HISTORY,
    SERVICE_CLEAR_FIT_FILES,
    SERVICE_MANAGE_BLUETOOTH_DEVICE,
    SERVICE_DELETE_WORKOUT_TOMBSTONE,
    SERVICE_EDIT_WORKOUT_TOMBSTONE,
    SERVICE_CLEAR_WORKOUT_TOMBSTONES,
    SERVICE_CLEAR_SAVED_DATA,
    CONF_FIT_FILE_RETENTION_COUNT,
    DEFAULT_FIT_FILE_RETENTION_COUNT,
    STORE_KEY_PREFIX,
    STORE_VERSION,
    SUPPORTED_LANGUAGES,
)
from .manager import FitnessManager
from .dashboard import async_setup_dashboard

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button", "select", "number", "calendar", "binary_sensor", "switch"]
HUB_PLATFORMS = ["sensor", "button", "binary_sensor", "switch", "event", "select"]

_DELETE_WORKOUTS_BEFORE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_DAYS): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=MAX_WORKOUT_RETENTION_DAYS),
        ),
    }
)



# This integration is configured exclusively through config entries.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration-level Fitness actions."""
    del config

    async def _delete_workouts_before(call: ServiceCall) -> None:
        entry_id = str(call.data[ATTR_CONFIG_ENTRY_ID])
        manager = hass.data.get(DOMAIN, {}).get(entry_id)
        if manager is None:
            raise HomeAssistantError(
                f"Fitness config entry {entry_id!r} is not loaded"
            )
        await manager.async_delete_workouts_before(int(call.data[ATTR_DAYS]))

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_WORKOUTS_BEFORE,
        _delete_workouts_before,
        schema=_DELETE_WORKOUTS_BEFORE_SCHEMA,
    )

    async def _cast_tv_dashboard(call: ServiceCall) -> None:
        entry_id = str(call.data[ATTR_CONFIG_ENTRY_ID])
        manager = hass.data.get(DOMAIN, {}).get(entry_id)
        if manager is None:
            raise HomeAssistantError(
                f"Fitness config entry {entry_id!r} is not loaded"
            )
        if not await manager.async_cast_tv_dashboard(
            str(call.data.get("entity_id") or "").strip() or None
        ):
            raise HomeAssistantError(
                "Fitness TV dashboard is disabled, has no Cast target, or could not be shown"
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CAST_TV_DASHBOARD,
        _cast_tv_dashboard,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): str,
                vol.Optional("entity_id"): str,
            }
        ),
    )

    async def _start_tv_workout(call: ServiceCall) -> None:
        entry_id = str(call.data[ATTR_CONFIG_ENTRY_ID])
        manager = hass.data.get(DOMAIN, {}).get(entry_id)
        if manager is None:
            raise HomeAssistantError(
                f"Fitness config entry {entry_id!r} is not loaded"
            )
        result = await manager.async_start_tv_workout(
            str(call.data.get("entity_id") or "").strip() or None
        )
        if not result.get("cast") or not result.get("workout_started"):
            raise HomeAssistantError(
                "Fitness TV could not be prepared or workout capture could not be started"
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_TV_WORKOUT,
        _start_tv_workout,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): str,
                vol.Optional("entity_id"): str,
            }
        ),
    )

    async def _stop_tv_dashboard(call: ServiceCall) -> None:
        entry_id = str(call.data[ATTR_CONFIG_ENTRY_ID])
        manager = hass.data.get(DOMAIN, {}).get(entry_id)
        if manager is None:
            raise HomeAssistantError(
                f"Fitness config entry {entry_id!r} is not loaded"
            )
        if not await manager.async_stop_tv_dashboard(
            str(call.data.get("entity_id") or "").strip() or None
        ):
            raise HomeAssistantError(
                "Fitness TV has no usable Cast target or the Cast receiver could not be stopped"
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_TV_DASHBOARD,
        _stop_tv_dashboard,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): str,
                vol.Optional("entity_id"): str,
            }
        ),
    )

    async def _test_tts(call: ServiceCall) -> None:
        entry_id = str(call.data[ATTR_CONFIG_ENTRY_ID])
        manager = hass.data.get(DOMAIN, {}).get(entry_id)
        if manager is None:
            raise HomeAssistantError(
                f"Fitness config entry {entry_id!r} is not loaded"
            )
        result = await manager.async_test_tts(
            str(call.data.get("message") or "").strip() or None
        )
        if result not in {"tv_success", "success", "partial_success"}:
            raise HomeAssistantError(
                f"Fitness TTS test failed ({result or 'unknown'})"
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST_TTS,
        _test_tts,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): str,
                vol.Optional("message"): str,
            }
        ),
    )

    async def _ai_tts(call: ServiceCall) -> None:
        entry_id = str(call.data[ATTR_CONFIG_ENTRY_ID])
        manager = hass.data.get(DOMAIN, {}).get(entry_id)
        if manager is None:
            raise HomeAssistantError(
                f"Fitness config entry {entry_id!r} is not loaded"
            )
        result = await manager.async_ai_tts(
            str(call.data.get("prompt") or "").strip()
        )
        if result not in {"tv_success", "success", "partial_success"}:
            raise HomeAssistantError(
                f"Fitness AI-to-TTS failed ({result or 'unknown'})"
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_AI_TTS,
        _ai_tts,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): str,
                vol.Required("prompt"): vol.All(str, vol.Length(min=1)),
            }
        ),
    )

    async def _profile_manager(call: ServiceCall) -> FitnessManager:
        entry_id = str(call.data[ATTR_CONFIG_ENTRY_ID])
        manager = hass.data.get(DOMAIN, {}).get(entry_id)
        if not isinstance(manager, FitnessManager):
            raise HomeAssistantError(f"Fitness profile {entry_id!r} is not loaded")
        return manager

    async def _clear_workout_history(call: ServiceCall) -> None:
        manager = await _profile_manager(call)
        await manager.async_clear_workout_history_regenerable()

    hass.services.async_register(DOMAIN, SERVICE_CLEAR_WORKOUT_HISTORY, _clear_workout_history, schema=vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): str}))

    async def _clear_fit_files(call: ServiceCall) -> None:
        manager = await _profile_manager(call)
        retain = int(call.data.get("retain_count", manager.config.get(CONF_FIT_FILE_RETENTION_COUNT, DEFAULT_FIT_FILE_RETENTION_COUNT)))
        runtime_module = importlib.import_module(".live.runtime", __package__)
        runtime = getattr(runtime_module, "get_live_" + "runtime")(hass)
        provider = runtime.providers.get("bluetooth")
        archives = getattr(provider, "device_archives", None)
        if archives is not None:
            await archives.async_clear_fit_cache(retain, profile_id=manager.entry.entry_id, ownership=str(call.data.get("ownership") or "profile"))

    hass.services.async_register(DOMAIN, SERVICE_CLEAR_FIT_FILES, _clear_fit_files, schema=vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): str, vol.Optional("retain_count"): vol.All(vol.Coerce(int), vol.Range(min=0, max=500)), vol.Optional("ownership", default="profile"): vol.In({"profile", "all_fitness_owned"})}))

    async def _manage_bluetooth_device(call: ServiceCall) -> None:
        from homeassistant.helpers import device_registry as dr
        runtime_module = importlib.import_module(".live.runtime", __package__)
        runtime = getattr(runtime_module, "get_live_" + "runtime")(hass)
        device_id = str(call.data.get("device_id") or "")
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            raise HomeAssistantError("Fitness Bluetooth device was not found")
        sensor_id = next((value.split(":", 1)[1] for domain, value in device.identifiers if domain == DOMAIN and value.startswith("live_sensor:")), None)
        sensor = runtime.sensors.get(runtime.resolve_sensor_id(sensor_id or "")) if sensor_id else None
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if sensor is None or endpoint is None:
            raise HomeAssistantError("Selected Fitness device has no local Bluetooth route")
        provider = runtime.providers.get("bluetooth")
        if provider is not None:
            for profile_id in runtime.sensor_assigned_profile_ids(sensor.sensor_id):
                await provider.async_disconnect_sensor(profile_id, sensor.sensor_id)
        if str(call.data.get("action") or "disconnect") != "unpair":
            return
        # Unpairing is destructive. Refuse whenever another config entry shares this HA device.
        fitness_entry_ids = {entry.entry_id for entry in hass.config_entries.async_entries(DOMAIN)}
        if any(entry_id not in fitness_entry_ids for entry_id in device.config_entries):
            raise HomeAssistantError("This Bluetooth device is shared with another integration; Fitness only disconnected it")
        from homeassistant.components import bluetooth
        ble_device = bluetooth.async_ble_device_from_address(hass, endpoint.address, connectable=True)
        if ble_device is None:
            raise HomeAssistantError("Bluetooth device is not currently known to the local adapter; it was disconnected but not unpaired")
        from .device_adapters.garmin.coordinator import _bluez_device_path
        from .device_adapters.garmin.bluez_agent import async_bluez_remove_device
        path = _bluez_device_path(ble_device, endpoint.address)
        if not path:
            raise HomeAssistantError("The selected Bluetooth route is not a local BlueZ device and cannot be unpaired by Fitness")
        await async_bluez_remove_device(path)

    hass.services.async_register(DOMAIN, SERVICE_MANAGE_BLUETOOTH_DEVICE, _manage_bluetooth_device, schema=vol.Schema({vol.Required("device_id"): str, vol.Required("action", default="disconnect"): vol.In({"disconnect", "unpair"})}))

    async def _clear_tombstones(call: ServiceCall) -> None:
        manager = await _profile_manager(call); await manager.async_clear_workout_tombstones()
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_WORKOUT_TOMBSTONES, _clear_tombstones, schema=vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): str}))

    async def _delete_tombstone(call: ServiceCall) -> None:
        manager = await _profile_manager(call)
        if not await manager.async_delete_workout_tombstone(int(call.data["index"])):
            raise HomeAssistantError("Workout tombstone index does not exist")
    hass.services.async_register(DOMAIN, SERVICE_DELETE_WORKOUT_TOMBSTONE, _delete_tombstone, schema=vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): str, vol.Required("index"): vol.All(vol.Coerce(int), vol.Range(min=0, max=999))}))

    async def _edit_tombstone(call: ServiceCall) -> None:
        manager = await _profile_manager(call)
        updates = {key: call.data[key] for key in ("name", "sport", "start", "end", "duration_s", "distance_m") if key in call.data}
        if not await manager.async_edit_workout_tombstone(int(call.data["index"]), updates):
            raise HomeAssistantError("Workout tombstone could not be edited")
    hass.services.async_register(DOMAIN, SERVICE_EDIT_WORKOUT_TOMBSTONE, _edit_tombstone, schema=vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): str, vol.Required("index"): vol.All(vol.Coerce(int), vol.Range(min=0, max=999)), vol.Optional("name"): str, vol.Optional("sport"): str, vol.Optional("start"): str, vol.Optional("end"): str, vol.Optional("duration_s"): vol.Coerce(float), vol.Optional("distance_m"): vol.Coerce(float)}))

    async def _clear_saved_data(call: ServiceCall) -> None:
        if not bool(call.data.get("confirm")):
            raise HomeAssistantError("Set confirm=true to clear all saved Fitness profile data")
        manager = await _profile_manager(call); await manager.async_clear_saved_data()
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_SAVED_DATA, _clear_saved_data, schema=vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): str, vol.Required("confirm", default=False): bool}))

    # Live adapter state is owned by the Local Sensors config entry.  Global
    # integration setup must stay constant-time and must not touch storage,
    # Bluetooth, ANT+, USB, gateways, or discovery.
    return True



def _default_profile_language(hass: HomeAssistant) -> str:
    """Return a supported language for migrated pre-language entries."""
    raw = str(getattr(hass.config, "language", None) or "en").lower()
    code = raw.split("-")[0].split("_")[0]
    return code if code in SUPPORTED_LANGUAGES else "en"


async def async_migrate_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Migrate Fitness profiles while preserving safe source ownership.

    Version 14 separates the confirmed/manual current body weight from an
    optional shared scale entity.  Older weight-entity configurations are moved
    to the shareable scale field and, when currently available, seed the manual
    current weight without making the scale an exclusive personal source.
    """
    if config_entry.version > 14:
        return False

    data = dict(config_entry.data)
    options = dict(config_entry.options)

    if config_entry.version < 12:
        if CONF_LANGUAGE not in data and CONF_LANGUAGE not in options:
            data[CONF_LANGUAGE] = _default_profile_language(hass)

        if (
            CONF_WORKOUT_RETENTION_DAYS not in data
            and CONF_WORKOUT_RETENTION_DAYS not in options
        ):
            data[CONF_WORKOUT_RETENTION_DAYS] = DEFAULT_WORKOUT_RETENTION_DAYS

    if config_entry.version < 13 and not data.get("entry_type"):
        from .providers.capabilities import exclusive_profile_source_overrides

        options.update(exclusive_profile_source_overrides(hass, config_entry))

    if config_entry.version < 14 and not data.get("entry_type"):
        from .providers.entities import is_entity_reference, resolve_number_or_entity

        current_weight = options.get(CONF_WEIGHT, data.get(CONF_WEIGHT))
        if is_entity_reference(current_weight):
            options.setdefault(CONF_WEIGHT_SCALE_ENTITY, str(current_weight).strip())
            resolved = resolve_number_or_entity(
                hass, current_weight, quantity="weight"
            ).value
            if resolved is not None and 20 <= float(resolved) <= 500:
                options[CONF_WEIGHT] = round(float(resolved), 1)

    if config_entry.version < 14:
        hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            options=options,
            version=14,
        )

    return True


@callback
def _schedule_sensors_adapters_entry(hass: HomeAssistant) -> None:
    """Check radio presence after startup; runtime creates the hub only if useful."""
    from .live import get_live_runtime

    async def _refresh() -> None:
        runtime = get_live_runtime(hass)
        await runtime.async_initialize()
        await runtime.async_refresh_adapter_presence()

    @callback
    def _run(_event=None) -> None:
        hass.async_create_task(_refresh())

    if hass.state is CoreState.running:
        _run()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _run)



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    from .live import get_live_runtime
    from .live.runtime import HUB_ENTRY_TYPE, DEVICES_HUB_ENTRY_TYPE
    runtime = get_live_runtime(hass)

    if entry.data.get("entry_type") == HUB_ENTRY_TYPE:
        if entry.title != "Fitness Protocols":
            hass.config_entries.async_update_entry(entry, title="Fitness Protocols")
        await runtime.async_register_hub(entry)
        initial_transport = str(entry.data.get("initial_transport") or "").strip()
        initial_protocols = entry.data.get("initial_protocols")
        initial_hardware = entry.data.get("initial_hardware")
        if isinstance(initial_protocols, list):
            selected = {str(item) for item in initial_protocols if str(item) in {"bluetooth", "antplus"}}
            await runtime.async_set_protocol_selection(selected)
            if isinstance(initial_hardware, dict):
                for transport in selected:
                    cfg = initial_hardware.get(transport) if isinstance(initial_hardware.get(transport), dict) else {}
                    await runtime.async_set_hardware_selection(
                        transport,
                        automatic=bool(cfg.get("automatic", True)),
                        selected=set(cfg.get("selected") or []),
                    )
            data = dict(entry.data)
            data.pop("initial_protocols", None)
            data.pop("initial_hardware", None)
            data.pop("initial_transport", None)
            hass.config_entries.async_update_entry(entry, data=data)
        elif initial_transport in {"bluetooth", "antplus"}:
            # Backward compatibility with the old one-protocol setup flow.
            await runtime.async_set_transport_enabled(initial_transport, True)
            data = dict(entry.data)
            data.pop("initial_transport", None)
            hass.config_entries.async_update_entry(entry, data=data)
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))
        await hass.config_entries.async_forward_entry_setups(entry, HUB_PLATFORMS)
        return True

    if entry.data.get("entry_type") == DEVICES_HUB_ENTRY_TYPE:
        if entry.title != "Fitness Devices":
            hass.config_entries.async_update_entry(entry, title="Fitness Devices")
        await runtime.async_register_devices_hub(entry)
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))
        await hass.config_entries.async_forward_entry_setups(entry, HUB_PLATFORMS)
        return True

    # Defensive runtime guard for profiles created before v13 or changed through
    # an external config-entry API.  Setup selectors already prevent reuse, but
    # backend isolation must never depend on the frontend behaving correctly.
    from .providers.capabilities import exclusive_profile_source_overrides
    source_overrides = exclusive_profile_source_overrides(hass, entry)
    if source_overrides:
        options = dict(entry.options)
        options.update(source_overrides)
        hass.config_entries.async_update_entry(entry, options=options)

    # Keep the person config-entry title concise.
    profile_name = str(entry.options.get(CONF_PROFILE_NAME, entry.data.get(CONF_PROFILE_NAME, entry.title)) or entry.title)
    if entry.title != profile_name:
        hass.config_entries.async_update_entry(entry, title=profile_name)

    await async_setup_dashboard(hass)
    await runtime.async_register_profile(entry)
    # The Live Workout device is permanent profile infrastructure.  Do not
    # create/delete it as sensors or adapters appear and disappear.
    runtime.ensure_profile_live_registry(entry)
    manager = FitnessManager(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = manager

    await manager.async_setup()
    from .weight_scales import get_weight_scale_router
    await get_weight_scale_router(hass).async_register_profile(entry, manager)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _schedule_sensors_adapters_entry(hass)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    from .live import get_live_runtime

    runtime = get_live_runtime(hass)
    if runtime.consume_entry_reload_suppression(entry.entry_id):
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .live.runtime import HUB_ENTRY_TYPE, DEVICES_HUB_ENTRY_TYPE
    entry_type = entry.data.get("entry_type")
    is_hub = entry_type == HUB_ENTRY_TYPE
    is_devices_hub = entry_type == DEVICES_HUB_ENTRY_TYPE
    platforms = HUB_PLATFORMS if (is_hub or is_devices_hub) else PLATFORMS
    if not is_hub:
        # Release server-owned music queues before the browser/runtime disappears.
        # In particular, an orphaned MA Spotify queue can keep the account locked
        # after an HA/profile restart even though no Fitness browser can play it.
        try:
            hub = hass.data.get(DOMAIN, {}).get("_tv_dashboard_hub")
            if hub is not None:
                async with asyncio.timeout(20.0):
                    await hub.async_release_profile_music(
                        entry.entry_id, reason="config_entry_unload"
                    )
        except TimeoutError:
            _LOGGER.warning(
                "Timed out releasing Fitness music for profile %s",
                entry.entry_id,
            )
        except Exception:
            # Shutdown cleanup is best effort and must never prevent unloading HA.
            pass
    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unloaded:
        runtime = hass.data.get(DOMAIN, {}).get("_live_runtime")
        if is_hub:
            remote_gateway = hass.data.get(DOMAIN, {}).get(
                "_remote_gateway_runtime"
            )
            if remote_gateway is not None:
                try:
                    async with asyncio.timeout(8.0):
                        await remote_gateway.async_shutdown()
                except TimeoutError:
                    _LOGGER.warning("Timed out stopping Fitness remote gateway")
            if runtime:
                try:
                    async with asyncio.timeout(30.0):
                        await runtime.async_unregister_hub(entry.entry_id)
                except TimeoutError:
                    _LOGGER.warning("Timed out unloading Fitness live sensor hub")
            return True
        if is_devices_hub:
            if runtime:
                await runtime.async_unregister_devices_hub(entry.entry_id)
            return True
        try:
            from .weight_scales import get_weight_scale_router
            await get_weight_scale_router(hass).async_unregister_profile(entry.entry_id)
        except Exception:  # noqa: BLE001 - unload must never be blocked by scale UX
            _LOGGER.exception("Unable to unregister Fitness shared scale profile")
        manager = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if manager:
            try:
                async with asyncio.timeout(30.0):
                    await manager.async_shutdown()
            except TimeoutError:
                _LOGGER.warning(
                    "Timed out unloading Fitness profile %s", entry.entry_id
                )
        if runtime:
            try:
                async with asyncio.timeout(20.0):
                    await runtime.async_unregister_profile(entry.entry_id)
            except TimeoutError:
                _LOGGER.warning(
                    "Timed out releasing live sensors for Fitness profile %s",
                    entry.entry_id,
                )
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete every Fitness-owned persistent record for a removed user profile."""
    from .live.runtime import HUB_ENTRY_TYPE, DEVICES_HUB_ENTRY_TYPE

    if entry.data.get("entry_type") in {HUB_ENTRY_TYPE, DEVICES_HUB_ENTRY_TYPE}:
        return

    try:
        from .weight_scales import get_weight_scale_router
        await get_weight_scale_router(hass).async_unregister_profile(entry.entry_id, permanent=True)
    except Exception:  # noqa: BLE001 - profile removal remains best effort
        _LOGGER.exception("Unable to remove Fitness shared scale routing")

    # The profile store contains canonical workouts, deletion tombstones, sleep
    # history, long-term/metric history, AI evaluations and other Fitness-owned
    # per-user state. Removing the config entry must remove the store itself,
    # not merely unload its entities.
    store = Store(hass, STORE_VERSION, f"{STORE_KEY_PREFIX}.{entry.entry_id}")
    await store.async_remove()

    runtime = hass.data.get(DOMAIN, {}).get("_live_runtime")
    if runtime is not None:
        # Defensive cleanup if HA invokes removal while runtime still knows the
        # profile. Sensor assignments live in the removed config entry, so no
        # shared physical sensor or other user's data is deleted.
        try:
            async with asyncio.timeout(20.0):
                await runtime.async_unregister_profile(entry.entry_id)
        except TimeoutError:
            _LOGGER.warning(
                "Timed out removing live state for Fitness profile %s",
                entry.entry_id,
            )


async def async_remove_config_entry_device(hass, config_entry, device_entry) -> bool:
    """Allow native Fitness sensors/adapters/receivers to be deleted.

    Physical sensors are forgotten completely so their next transmission starts
    a fresh discovery/assignment flow. Adapter and receiver registry devices are
    removable too; the always-on presence layer recreates them only when their
    underlying hardware/proxy/gateway is detected again.
    """
    from .live import get_live_runtime
    from .live.runtime import HUB_ENTRY_TYPE, DEVICES_HUB_ENTRY_TYPE

    if config_entry.data.get("entry_type") not in {HUB_ENTRY_TYPE, DEVICES_HUB_ENTRY_TYPE}:
        return False

    identifiers = {
        str(identifier)
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    }
    runtime = get_live_runtime(hass)
    await runtime.async_initialize()

    sensor_identifier = next(
        (value for value in identifiers if value.startswith("live_sensor:")),
        None,
    )
    if sensor_identifier is not None:
        # Persist revocation before Home Assistant finishes removing the device.
        # Continuous BLE/ANT advertisements may arrive during deletion; they must
        # only start a fresh discovery flow, never recreate an accepted device.
        await runtime.async_forget_sensor(sensor_identifier.split(":", 1)[1])
        return True

    if any(value.startswith("usb_adapter:") for value in identifiers):
        # The receiver remains physically discoverable. Do not immediately
        # recreate it here; the next ANT receiver refresh/transmission does so.
        return True

    if any(value.startswith("live_adapter:") for value in identifiers):
        # Logical adapters are derived from physical radio presence.
        return True

    return False
