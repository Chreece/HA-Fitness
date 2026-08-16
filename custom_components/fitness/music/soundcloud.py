"""SoundCloud link playback adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote

FITNESS_SOUNDCLOUD_PREFIX = "fitness-soundcloud://"


async def async_resolve(_hub, media_content_id: str) -> dict[str, Any] | None:
    """Resolve a SoundCloud URL for the embedded SoundCloud widget."""
    if not media_content_id.startswith(FITNESS_SOUNDCLOUD_PREFIX):
        return None
    target = unquote(media_content_id[len(FITNESS_SOUNDCLOUD_PREFIX) :]).strip()
    if not target:
        raise ValueError("Missing SoundCloud target")
    return {
        "kind": "soundcloud",
        "url": target,
        "title": target,
        "provider": "soundcloud",
        "provider_name": "SoundCloud",
        "provider_origin": "SoundCloud",
    }
