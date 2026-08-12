"""Fitness integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_LANGUAGE, CONF_PROFILE_NAME, DOMAIN, SUPPORTED_LANGUAGES
from .manager import FitnessManager
from .dashboard import async_setup_dashboard

PLATFORMS = ["sensor", "button", "select", "number"]



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

    Version 11 added the per-profile language setting. Older entries are
    upgraded in place without changing any existing profile/device/AI/feedback
    configuration.
    """
    if config_entry.version > 11:
        return False

    if config_entry.version < 11:
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

        hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            options=options,
            version=11,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Keep the config-entry title concise as well. Older releases prefixed it
    # with "Fitness –", which duplicated the integration name in the UI.
    profile_name = str(entry.options.get(CONF_PROFILE_NAME, entry.data.get(CONF_PROFILE_NAME, entry.title)) or entry.title)
    if entry.title != profile_name:
        hass.config_entries.async_update_entry(entry, title=profile_name)

    hass.data.setdefault(DOMAIN, {})
    await async_setup_dashboard(hass)
    manager = FitnessManager(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = manager

    await manager.async_setup()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        manager = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if manager:
            await manager.async_shutdown()
    return unloaded
