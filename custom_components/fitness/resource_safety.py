"""Shared time bounds for calls into optional Home Assistant integrations."""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.core import HomeAssistant


DEFAULT_SERVICE_TIMEOUT = 20.0


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
