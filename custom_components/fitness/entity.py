"""Shared Fitness entity helpers."""

from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_LANGUAGE, DOMAIN
from .device_translations import device_name


def _entry_language(entry) -> str:
    """Return the configured Fitness profile language."""
    return str(
        entry.options.get(
            CONF_LANGUAGE,
            entry.data.get(CONF_LANGUAGE, "en"),
        )
        or "en"
    )


def device_info(entry, kind: str) -> DeviceInfo:
    """Return stable device identifiers with a localized, uncluttered name.

    Names intentionally do not repeat the integration name or profile name.
    The identifiers stay unchanged, so existing entities, history, dashboards
    and automations survive the display-name migration.
    """
    translated_kind = "recovery" if kind == "sleep" else kind
    label = device_name(_entry_language(entry), kind)
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{kind}")},
        translation_key=translated_kind,
        name=label,
        manufacturer="Fitness",
        model=label,
    )
