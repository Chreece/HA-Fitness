"""Repairs flows for direct-device interaction and credentials."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .device_credentials import async_get_device_credential_store

_AUTH_KEY_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_PIN_RE = re.compile(r"^[0-9]{4,8}$")


def _instructions(data: dict[str, Any]) -> str:
    steps = [str(item).strip() for item in data.get("instructions", []) if str(item).strip()]
    return "\n".join(f"{idx}. {step}" for idx, step in enumerate(steps, 1))


class DeviceUserActionRepairFlow(RepairsFlow):
    """Collect adapter-requested input without exposing it in entity state."""

    def __init__(self, issue_id: str, data: dict[str, Any]) -> None:
        self.issue_id = issue_id
        self.data = data

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        return await self.async_step_credentials(user_input)

    async def async_step_credentials(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        fields = tuple(str(x) for x in self.data.get("fields", ()))
        errors: dict[str, str] = {}
        if user_input is not None:
            clean: dict[str, str] = {}
            for field in fields:
                value = str(user_input.get(field, "")).strip()
                if field == "auth_key":
                    value = value.replace(" ", "").replace(":", "")
                    if not _AUTH_KEY_RE.fullmatch(value):
                        errors[field] = "invalid_auth_key"
                        continue
                    value = value.lower()
                elif field == "pin":
                    if not _PIN_RE.fullmatch(value):
                        errors[field] = "invalid_pin"
                        continue
                elif not value:
                    errors[field] = "required"
                    continue
                clean[field] = value
            if not errors:
                store = async_get_device_credential_store(self.hass)
                await store.async_set(
                    str(self.data.get("sensor_id") or ""),
                    str(self.data.get("adapter_id") or ""),
                    clean,
                )
                self.hass.bus.async_fire(
                    "fitness_device_reconfigure_completed",
                    {
                        "sensor_id": str(self.data.get("sensor_id") or ""),
                        "adapter_id": str(self.data.get("adapter_id") or ""),
                    },
                )
                return self.async_create_entry(title="", data={})

        schema: dict[Any, Any] = {}
        for field in fields:
            text_type = selector.TextSelectorType.PASSWORD if field == "auth_key" else selector.TextSelectorType.TEXT
            schema[vol.Required(field)] = selector.TextSelector(
                selector.TextSelectorConfig(type=text_type, multiline=False)
            )
        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "device": str(self.data.get("device") or "Fitness device"),
                "instructions": _instructions(self.data),
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow for a direct-device action request."""
    del hass
    payload = dict(data or {})
    if not issue_id.startswith("device_action_"):
        raise ValueError(f"Unsupported Fitness repair issue: {issue_id}")
    return DeviceUserActionRepairFlow(issue_id, payload)
