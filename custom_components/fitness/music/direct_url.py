"""Direct HTTP(S)/Home Assistant audio link adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

if TYPE_CHECKING:
    from ..tv_dashboard import FitnessTVDashboardHub

FITNESS_URL_PREFIX = "fitness-url://"


async def async_resolve(
    hub: "FitnessTVDashboardHub", media_content_id: str
) -> dict[str, Any] | None:
    """Resolve a direct audio URL, proxying remote media through Home Assistant."""
    if not media_content_id.startswith(FITNESS_URL_PREFIX):
        return None
    target = unquote(media_content_id[len(FITNESS_URL_PREFIX) :]).strip()
    if not target.lower().startswith(("http://", "https://", "/")):
        raise ValueError("Direct audio must be an HTTP(S) or Home Assistant URL")
    url = (
        hub._music_proxy_url(target)
        if target.lower().startswith(("http://", "https://"))
        else target
    )
    return {
        "kind": "audio",
        "url": url,
        "title": target,
        "provider": "direct_url",
        "provider_name": "Direct URL",
        "provider_origin": "Direct URL",
    }
