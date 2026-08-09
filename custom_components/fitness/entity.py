"""Shared Fitness entity helpers."""

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def device_info(entry, kind: str) -> DeviceInfo:
    suffix = {
        "live": "Live",
        "workout": "Workout",
        "evaluation": "Evaluation",
    }[kind]
    profile = entry.data.get("profile_name", entry.title)
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{kind}")},
        name=f"Fitness – {profile} – {suffix}",
        manufacturer="Fitness",
        model=f"Fitness {suffix}",
    )
