"""Fitness integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import voluptuous as vol

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DAYS,
    CONF_LANGUAGE,
    CONF_PROFILE_NAME,
    CONF_WORKOUT_RETENTION_DAYS,
    DEFAULT_WORKOUT_RETENTION_DAYS,
    DOMAIN,
    MAX_WORKOUT_RETENTION_DAYS,
    SERVICE_DELETE_WORKOUTS_BEFORE,
    SUPPORTED_LANGUAGES,
)
from .manager import FitnessManager
from .dashboard import async_setup_dashboard

PLATFORMS = ["sensor", "button", "select", "number", "calendar", "binary_sensor", "switch"]
HUB_PLATFORMS = ["sensor", "button", "binary_sensor", "switch"]

_DELETE_WORKOUTS_BEFORE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_DAYS): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=MAX_WORKOUT_RETENTION_DAYS),
        ),
    }
)


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

    # Live adapters are global Fitness infrastructure, independent of any one
    # person's config entry. Disabled transports are not imported/loaded.
    from .live import get_live_runtime
    await get_live_runtime(hass).async_initialize()
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
    """Migrate older Fitness config entries to the current schema.

    Version 11 added the per-profile language setting. Version 12 adds
    canonical workout-history retention. Older entries are
    upgraded in place without changing any existing profile/device/AI/feedback
    configuration.
    """
    if config_entry.version > 12:
        return False

    if config_entry.version < 12:
        data = dict(config_entry.data)
        options = dict(config_entry.options)

        # Existing entries should keep following the user's HA language by
        # default, matching pre-v11 behaviour, but persist it now as a profile
        # setting so future UI-language changes do not silently alter Fitness.
        if (
            CONF_LANGUAGE not in data
            and CONF_LANGUAGE not in options
        ):
            data[CONF_LANGUAGE] = _default_profile_language(hass)

        if (
            CONF_WORKOUT_RETENTION_DAYS not in data
            and CONF_WORKOUT_RETENTION_DAYS not in options
        ):
            data[CONF_WORKOUT_RETENTION_DAYS] = DEFAULT_WORKOUT_RETENTION_DAYS

        hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            options=options,
            version=12,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    from .live import get_live_runtime
    from .live.runtime import HUB_ENTRY_TYPE
    runtime = get_live_runtime(hass)

    if entry.data.get("entry_type") == HUB_ENTRY_TYPE:
        if entry.title != "Local Sensors":
            hass.config_entries.async_update_entry(entry, title="Local Sensors")
        await runtime.async_register_hub(entry)
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))
        await hass.config_entries.async_forward_entry_setups(entry, HUB_PLATFORMS)
        return True

    # Keep the person config-entry title concise.
    profile_name = str(entry.options.get(CONF_PROFILE_NAME, entry.data.get(CONF_PROFILE_NAME, entry.title)) or entry.title)
    if entry.title != profile_name:
        hass.config_entries.async_update_entry(entry, title=profile_name)

    await async_setup_dashboard(hass)
    await runtime.async_register_profile(entry)
    manager = FitnessManager(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = manager

    await manager.async_setup()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .live.runtime import HUB_ENTRY_TYPE
    is_hub = entry.data.get("entry_type") == HUB_ENTRY_TYPE
    platforms = HUB_PLATFORMS if is_hub else PLATFORMS
    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unloaded:
        runtime = hass.data.get(DOMAIN, {}).get("_live_runtime")
        if is_hub:
            if runtime:
                await runtime.async_unregister_hub(entry.entry_id)
            return True
        manager = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if manager:
            await manager.async_shutdown()
        if runtime:
            await runtime.async_unregister_profile(entry.entry_id)
    return unloaded
