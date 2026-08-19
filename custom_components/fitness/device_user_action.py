"""Home Assistant native user-action requests for direct fitness devices."""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_ALLOWED_FIELDS = {"auth_key", "pin", "confirmation_code"}


def issue_id(adapter_id: str, sensor_id: str, action: str) -> str:
    raw = f"{adapter_id}\0{sensor_id}\0{action}".encode("utf-8", errors="ignore")
    return f"device_action_{hashlib.sha256(raw).hexdigest()[:20]}"


def request_device_user_action(
    hass: HomeAssistant,
    *,
    adapter_id: str,
    sensor_id: str,
    device: str,
    action: str,
    instructions: Iterable[str],
    fields: Iterable[str] = (),
    reason: str = "Device interaction is required before Fitness can continue syncing.",
) -> str:
    """Create a guided, fixable Repair and always emit the user-action event."""
    clean_fields = tuple(field for field in fields if field in _ALLOWED_FIELDS)
    clean_steps = tuple(str(step).strip() for step in instructions if str(step).strip())[:12]
    issue = issue_id(adapter_id, sensor_id, action)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="device_user_action_required",
        translation_placeholders={
            "device": device,
            "reason": reason,
            "instructions": "\n".join(
                f"{index}. {step}" for index, step in enumerate(clean_steps, 1)
            ),
        },
        data={
            "adapter_id": adapter_id,
            "sensor_id": sensor_id,
            "device": device,
            "action": action,
            "instructions": list(clean_steps),
            "fields": list(clean_fields),
        },
    )
    hass.bus.async_fire(
        "fitness_device_user_action_required",
        {
            "sensor_id": sensor_id,
            "adapter_id": adapter_id,
            "action": action,
            "device": device,
            "instructions": list(clean_steps),
            "fields": list(clean_fields),
        },
    )
    return issue


def clear_device_user_action(
    hass: HomeAssistant,
    *,
    adapter_id: str,
    sensor_id: str,
    action: str,
) -> None:
    ir.async_delete_issue(hass, DOMAIN, issue_id(adapter_id, sensor_id, action))
