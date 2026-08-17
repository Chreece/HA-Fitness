"""Shared time bounds for calls into optional Home Assistant integrations."""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant


DEFAULT_SERVICE_TIMEOUT = 20.0


def bounded_payload(
    value: Any,
    *,
    max_nodes: int = 4_096,
    max_depth: int = 8,
    max_string_length: int = 8_192,
) -> Any:
    """Validate the size of a JSON-like WebSocket payload iteratively.

    Home Assistant limits the wire message, but a relatively small, deeply
    nested JSON document can still amplify into expensive sanitizing and
    persistence work.  Keeping this validator iterative also avoids consuming
    the Python call stack while rejecting hostile nesting.
    """
    stack: list[tuple[Any, int]] = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > max(1, int(max_nodes)):
            raise vol.Invalid("payload_too_complex")
        if depth > max(1, int(max_depth)):
            raise vol.Invalid("payload_too_deep")
        if isinstance(current, str):
            if len(current) > max(1, int(max_string_length)):
                raise vol.Invalid("payload_string_too_long")
            continue
        if isinstance(current, dict):
            stack.extend((key, depth + 1) for key in current)
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend((item, depth + 1) for item in current)
    return value


def bounded_websocket_payload(
    *,
    max_nodes: int = 4_096,
    max_depth: int = 8,
    max_string_length: int = 8_192,
):
    """Return a Voluptuous validator for one bounded JSON-like value."""

    def _validate(value: Any) -> Any:
        return bounded_payload(
            value,
            max_nodes=max_nodes,
            max_depth=max_depth,
            max_string_length=max_string_length,
        )

    return _validate


async def async_call_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    service_data: dict[str, Any] | None = None,
    *,
    timeout: float = DEFAULT_SERVICE_TIMEOUT,
    **kwargs: Any,
) -> Any:
    """Call a service without allowing a dependency to block Fitness forever."""
    async with asyncio.timeout(max(1.0, float(timeout))):
        return await hass.services.async_call(
            domain,
            service,
            service_data,
            **kwargs,
        )
