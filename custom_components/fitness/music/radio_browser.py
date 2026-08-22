"""Radio Browser adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import MusicAdapter, MusicAdapterInfo, clamp_search_limit

if TYPE_CHECKING:
    from ..tv_dashboard import FitnessTVDashboardHub

FITNESS_RADIO_PREFIX = "fitness-radio://"


class RadioBrowserMusicAdapter(MusicAdapter):
    """Fitness-native Radio Browser adapter."""

    def __init__(self, hub: "FitnessTVDashboardHub") -> None:
        self._hub = hub
        self.info = MusicAdapterInfo(
            adapter_id="radio_browser",
            name="Radio Browser",
            icon="mdi:radio-tower",
            can_search=True,
            can_browse=True,
        )

    async def async_search(self, query: str, *, limit: int, scopes: list[str] | None = None, media_types: list[str] | None = None) -> list[dict[str, Any]]:
        if media_types is not None and "radio" not in {str(item).strip().lower() for item in media_types}:
            return []
        result = await self._hub.async_music_browse("radio", query=query)
        children = result.get("children") if isinstance(result, dict) else []
        return list(children or [])[:clamp_search_limit(limit)]


async def async_resolve(hub: "FitnessTVDashboardHub", media_content_id: str) -> dict[str, Any] | None:
    """Resolve one stable Radio Browser selection."""
    if not media_content_id.startswith(FITNESS_RADIO_PREFIX):
        return None
    station_uuid = media_content_id[len(FITNESS_RADIO_PREFIX) :].strip()
    if not station_uuid:
        raise ValueError("Missing Radio Browser station UUID")
    try:
        click = await hub._async_radio_browser_json(f"/json/url/{station_uuid}")
    except Exception:  # noqa: BLE001 - directory fallback
        click = None
    url = str((click or {}).get("url") or "").strip() if isinstance(click, dict) else ""
    title = str((click or {}).get("name") or "").strip() if isinstance(click, dict) else ""
    try:
        rows = await hub._async_radio_browser_json(f"/json/stations/byuuid/{station_uuid}")
    except Exception:  # noqa: BLE001
        rows = []
    row = rows[0] if isinstance(rows, list) and rows else {}
    normalized = hub._radio_item(row) if isinstance(row, dict) else None
    if isinstance(row, dict):
        # Prefer Radio Browser's verified/resolved stream target over the raw
        # click URL. The raw URL may be a short playlist/redirect endpoint that
        # produces a second of audio and then closes; url_resolved is the best
        # current direct stream endpoint for Cast/browser playback.
        resolved_url = str(row.get("url_resolved") or "").strip()
        url = resolved_url or url or str(row.get("url") or "").strip()
        title = title or str(row.get("name") or "").strip()
    if not url:
        raise ValueError("Radio station has no playable stream URL")
    return {
        "kind": "audio",
        "url": hub._music_proxy_url(url),
        "title": title,
        "artist": "",
        "thumbnail": str((normalized or {}).get("thumbnail") or ""),
        "duration": 0.0,
        "is_live": True,
        "details": str((normalized or {}).get("details") or ""),
        "provider": "radio_browser",
        "provider_name": "Radio Browser",
        "provider_origin": "Radio Browser",
    }
