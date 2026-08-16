"""Compatibility guard for favorites created by the old Spotify-link path."""

from __future__ import annotations

from typing import Any

FITNESS_SPOTIFY_PREFIX = "fitness-spotify://"


async def async_resolve(_hub, media_content_id: str) -> dict[str, Any] | None:
    """Reject obsolete Spotify favorites instead of claiming false browser playback."""
    if not media_content_id.startswith(FITNESS_SPOTIFY_PREFIX):
        return None
    raise ValueError(
        "Spotify links are not directly playable by Fitness TV. "
        "Enable the installed Spotify or Music Assistant adapter instead."
    )
