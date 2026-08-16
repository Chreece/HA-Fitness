"""Normal YouTube/YouTube Music link playback adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote

FITNESS_YOUTUBE_PREFIX = "fitness-youtube://"


async def async_resolve(_hub, media_content_id: str) -> dict[str, Any] | None:
    """Resolve a normal YouTube URL for the embedded YouTube player."""
    if not media_content_id.startswith(FITNESS_YOUTUBE_PREFIX):
        return None
    target = unquote(media_content_id[len(FITNESS_YOUTUBE_PREFIX) :]).strip()
    if not target.lower().startswith(("http://", "https://")):
        raise ValueError("YouTube playback requires an HTTP(S) URL")
    return {
        "kind": "youtube",
        "url": target,
        "title": "YouTube",
        "artist": "",
        "thumbnail": "",
        "duration": 0.0,
        "details": "Video",
        "provider": "youtube",
        "provider_name": "YouTube",
        "provider_origin": "YouTube",
    }
