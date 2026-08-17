"""Optional yt-dlp search/playback adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote, unquote

from homeassistant.core import HomeAssistant

from ..music_ytdlp import (
    FitnessYTDLPError,
    FitnessYTDLPLiveStream,
    resolve_youtube_audio,
    runtime_status,
    search_youtube,
    search_youtube_playlists,
)
from .base import MusicAdapter, MusicAdapterInfo, clamp_search_limit

if TYPE_CHECKING:
    from ..tv_dashboard import FitnessTVDashboardHub

FITNESS_YTDLP_PREFIX = "fitness-ytdlp://"


class YTDLPMusicAdapter(MusicAdapter):
    """Opt-in yt-dlp adapter. It only exists when it is usable."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self.info = MusicAdapterInfo(
            adapter_id="yt_dlp",
            name="YouTube via yt-dlp",
            icon="mdi:youtube",
            can_search=True,
            experimental=True,
            account_setup="fitness_opt_in",
            setup_hint_key="music_adapter_ytdlp_hint",
        )

    @staticmethod
    def available() -> bool:
        return bool(runtime_status().get("available"))

    async def async_search(self, query: str, *, limit: int, scopes: list[str] | None = None, media_types: list[str] | None = None) -> list[dict[str, Any]]:
        requested = {str(item).strip().lower() for item in (media_types or ["track"])}
        want_tracks = "track" in requested
        want_playlists = "playlist" in requested
        if not want_tracks and not want_playlists:
            return []
        limit = clamp_search_limit(limit)
        per_type_limit = limit if want_tracks ^ want_playlists else max(1, (limit + 1) // 2)
        track_rows: list[dict[str, Any]] = []
        playlist_rows: list[dict[str, Any]] = []
        if want_tracks:
            track_rows = await self._hass.async_add_executor_job(search_youtube, query, per_type_limit)
        if want_playlists:
            playlist_rows = await self._hass.async_add_executor_job(search_youtube_playlists, query, per_type_limit)

        def normalize(row: dict[str, Any], *, kind: str) -> dict[str, Any] | None:
            target = str(row.get("url") or "").strip()
            title = str(row.get("title") or "").strip()
            if not target or not title:
                return None
            is_live = bool(row.get("is_live"))
            marker = "playlist" if kind == "playlist" else ("live" if is_live else "track")
            details = str(row.get("details") or "").strip()
            return {
                "title": title,
                "media_content_id": f"{FITNESS_YTDLP_PREFIX}{quote(f'{marker}|{target}', safe='')}",
                "can_play": True,
                "can_expand": False,
                "thumbnail": str(row.get("thumbnail") or "").strip(),
                "artist": str(row.get("artist") or "").strip(),
                "album": str(row.get("album") or "").strip(),
                "year": row.get("year") or "",
                "duration": 0.0 if is_live or kind == "playlist" else (row.get("duration") or 0.0),
                "details": details,
                "media_class": kind,
                "provider": "yt_dlp",
                "provider_name": "YouTube",
                "provider_origin": "YouTube · yt-dlp",
                "adapter_id": self.info.adapter_id,
                "adapter_name": self.info.name,
                "external_url": target,
                "is_live": is_live,
            }

        normalized_tracks = [item for row in track_rows if (item := normalize(row, kind="track"))]
        normalized_playlists = [item for row in playlist_rows if (item := normalize(row, kind="playlist"))]
        if not normalized_tracks:
            return normalized_playlists[:limit]
        if not normalized_playlists:
            return normalized_tracks[:limit]
        # Interleave types so playlist results cannot be starved by track hits.
        results: list[dict[str, Any]] = []
        for index in range(max(len(normalized_tracks), len(normalized_playlists))):
            if index < len(normalized_tracks):
                results.append(normalized_tracks[index])
            if index < len(normalized_playlists):
                results.append(normalized_playlists[index])
            if len(results) >= limit:
                break
        return results[:limit]


async def async_resolve(
    hass: HomeAssistant,
    hub: "FitnessTVDashboardHub",
    media_content_id: str,
    *,
    enabled: bool,
) -> dict[str, Any] | None:
    if not media_content_id.startswith(FITNESS_YTDLP_PREFIX):
        return None
    if not enabled:
        raise FitnessYTDLPError("yt-dlp is disabled for this Fitness profile")
    decoded = unquote(media_content_id[len(FITNESS_YTDLP_PREFIX) :]).strip()
    if not decoded:
        raise ValueError("Missing yt-dlp media target")
    marker = "track"
    target = decoded
    if "|" in decoded:
        candidate, rest = decoded.split("|", 1)
        if candidate in {"track", "playlist", "live"}:
            marker, target = candidate, rest.strip()
    if not target:
        raise ValueError("Missing yt-dlp media target")
    # Playlists and active live streams belong on YouTube's player.  They are
    # segmented/queue media, not a single finite direct audio file that Fitness
    # can safely proxy and seek as HTMLAudio.
    if marker in {"playlist", "live"}:
        return {
            "kind": "youtube",
            "url": target,
            "title": target,
            "details": "yt-dlp playlist" if marker == "playlist" else "yt-dlp live",
            "provider": "yt_dlp",
            "provider_name": "YouTube",
            "provider_origin": "YouTube · yt-dlp",
            "media_class": marker,
            "is_live": marker == "live",
            "duration": 0.0,
        }
    try:
        resolved = await hass.async_add_executor_job(resolve_youtube_audio, target)
    except FitnessYTDLPLiveStream:
        # A live result can lose its live marker during a flat search result.
        # Full yt-dlp extraction is authoritative: use YouTube's player and
        # expose it as a non-seekable LIVE item rather than proxying segments.
        return {
            "kind": "youtube",
            "url": target,
            "title": target,
            "details": "yt-dlp live",
            "provider": "yt_dlp",
            "provider_name": "YouTube",
            "provider_origin": "YouTube · yt-dlp",
            "media_class": "live",
            "is_live": True,
            "duration": 0.0,
        }
    except FitnessYTDLPError:
        # Ordinary videos may still require YouTube's own player when yt-dlp
        # cannot provide one simple browser-safe direct audio URL.
        return {
            "kind": "youtube",
            "url": target,
            "title": target,
            "details": "yt-dlp fallback",
            "provider": "yt_dlp",
            "provider_name": "YouTube",
            "provider_origin": "YouTube · yt-dlp",
        }
    return {
        "kind": "audio",
        "url": hub._music_proxy_url(resolved.url, headers=resolved.headers),
        "title": resolved.title,
        "artist": resolved.artist,
        "thumbnail": resolved.thumbnail,
        "duration": hub._media_seconds(resolved.duration),
        "details": "yt-dlp",
        "provider": "yt_dlp",
        "provider_name": "YouTube",
        "provider_origin": "YouTube · yt-dlp",
        "fallback_kind": "youtube",
        "fallback_url": target,
    }
