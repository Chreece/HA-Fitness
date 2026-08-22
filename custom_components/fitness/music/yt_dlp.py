"""Optional yt-dlp search/playback adapter."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, unquote, urlparse

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..music_ytdlp import (
    FitnessYTDLPError,
    FitnessYTDLPLiveStream,
    list_youtube_playlist_entries,
    resolve_youtube_audio,
    runtime_status,
    search_youtube,
    search_youtube_playlists,
)
from .base import MusicAdapter, MusicAdapterInfo, clamp_search_limit

if TYPE_CHECKING:
    from ..tv_dashboard import FitnessTVDashboardHub

FITNESS_YTDLP_PREFIX = "fitness-ytdlp://"
_YTDLP_MEDIA_HOST_SUFFIXES = (".googlevideo.com",)
_YTDLP_BROWSER_AUDIO_TYPES = {"audio/mp4", "audio/m4a", "video/mp4"}


async def _async_probe_browser_audio(hass: HomeAssistant, resolved) -> bool:
    """Verify the resolved stream can actually be fetched as browser-safe audio."""
    parsed = urlparse(str(getattr(resolved, "url", "") or ""))
    host = str(parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not any(host.endswith(suffix) for suffix in _YTDLP_MEDIA_HOST_SUFFIXES):
        return False
    headers = dict(getattr(resolved, "headers", {}) or {})
    headers.pop("Cookie", None)
    headers.pop("cookie", None)
    headers.pop("Authorization", None)
    headers.pop("authorization", None)
    headers["Range"] = "bytes=0-1"
    headers["Accept-Encoding"] = "identity"
    try:
        session = async_get_clientsession(hass)
        async with session.get(
            resolved.url,
            headers=headers,
            timeout=ClientTimeout(total=7),
            allow_redirects=True,
        ) as response:
            if response.status not in {200, 206}:
                return False
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type not in _YTDLP_BROWSER_AUDIO_TYPES:
                return False
            return bool(await response.content.read(1))
    except (ClientError, TimeoutError, OSError, ValueError):
        return False


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
        """Return only yt-dlp items that Fitness can actually play.

        Flat YouTube search results are cheap but optimistic.  Probe candidate
        tracks with the exact direct-audio resolver used by playback and omit
        anything that cannot produce one browser-safe HTTPS audio stream.
        """
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
            # Fetch spare candidates because unavailable/segmented/live items
            # are filtered by the playback probe below.
            candidate_limit = min(100, max(per_type_limit + 8, per_type_limit * 2))
            candidates = await self._hass.async_add_executor_job(search_youtube, query, candidate_limit)
            semaphore = asyncio.Semaphore(4)

            async def _playable(row: dict[str, Any]) -> dict[str, Any] | None:
                if bool(row.get("is_live")):
                    return None
                target = str(row.get("url") or "").strip()
                if not target:
                    return None
                async with semaphore:
                    try:
                        resolved = await self._hass.async_add_executor_job(resolve_youtube_audio, target)
                    except (FitnessYTDLPError, FitnessYTDLPLiveStream):
                        return None
                    if not await _async_probe_browser_audio(self._hass, resolved):
                        return None
                return row

            # Probe in modest batches so we stop doing extractor work as soon as
            # enough playable results have been found.
            for offset in range(0, len(candidates), 8):
                batch = await asyncio.gather(*(_playable(row) for row in candidates[offset:offset + 8]))
                track_rows.extend(row for row in batch if row is not None)
                if len(track_rows) >= per_type_limit:
                    break
            track_rows = track_rows[:per_type_limit]
        if want_playlists:
            # A playlist search result is only useful when at least one entry
            # survives the exact browser-audio resolver used during playback.
            # Probe a few flat entries from spare candidates; do not recursively
            # resolve whole playlists during search.
            candidate_limit = min(24, max(per_type_limit + 4, per_type_limit * 2))
            candidates = await self._hass.async_add_executor_job(
                search_youtube_playlists, query, candidate_limit
            )
            playlist_semaphore = asyncio.Semaphore(2)

            async def _playable_playlist(row: dict[str, Any]) -> dict[str, Any] | None:
                target = str(row.get("url") or "").strip()
                if not target:
                    return None
                async with playlist_semaphore:
                    try:
                        entries = await self._hass.async_add_executor_job(
                            list_youtube_playlist_entries, target, 8
                        )
                    except FitnessYTDLPError:
                        return None
                    for entry in entries[:8]:
                        entry_target = str(entry.get("url") or "").strip()
                        if not entry_target or bool(entry.get("is_live")):
                            continue
                        try:
                            resolved = await self._hass.async_add_executor_job(
                                resolve_youtube_audio, entry_target
                            )
                        except (FitnessYTDLPError, FitnessYTDLPLiveStream):
                            continue
                        if not await _async_probe_browser_audio(self._hass, resolved):
                            continue
                        return row
                return None

            for offset in range(0, len(candidates), 3):
                batch = await asyncio.gather(*(
                    _playable_playlist(row)
                    for row in candidates[offset:offset + 3]
                ))
                playlist_rows.extend(row for row in batch if row is not None)
                if len(playlist_rows) >= per_type_limit:
                    break
            playlist_rows = playlist_rows[:per_type_limit]

        def normalize(row: dict[str, Any], *, kind: str) -> dict[str, Any] | None:
            target = str(row.get("url") or "").strip()
            title = str(row.get("title") or "").strip()
            if not target or not title:
                return None
            marker = "playlist" if kind == "playlist" else "track"
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
                "duration": 0.0 if kind == "playlist" else (row.get("duration") or 0.0),
                "details": details,
                "media_class": kind,
                "provider": "yt_dlp",
                "provider_name": "YouTube",
                "provider_origin": "YouTube · yt-dlp",
                "adapter_id": self.info.adapter_id,
                "adapter_name": self.info.name,
                "external_url": target,
                "is_live": False,
            }

        normalized_tracks = [item for row in track_rows if (item := normalize(row, kind="track"))]
        normalized_playlists = [item for row in playlist_rows if (item := normalize(row, kind="playlist"))]
        if not normalized_tracks:
            return normalized_playlists[:limit]
        if not normalized_playlists:
            return normalized_tracks[:limit]
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
    if marker == "live":
        raise FitnessYTDLPError("Live YouTube results are not exposed by the browser-playable yt-dlp adapter")
    if marker == "playlist":
        rows = await hass.async_add_executor_job(list_youtube_playlist_entries, target, 100)
        playable: list[tuple[dict[str, Any], Any]] = []
        # Resolve in small groups. Failed/deleted/segmented entries are simply
        # removed from the Fitness queue, so Next always advances to another
        # item that passed the same resolver used for playback.
        for offset in range(0, len(rows), 6):
            batch = rows[offset:offset + 6]
            results = await asyncio.gather(*(
                hass.async_add_executor_job(resolve_youtube_audio, str(row.get("url") or ""))
                for row in batch
            ), return_exceptions=True)
            for row, resolved_item in zip(batch, results):
                if isinstance(resolved_item, Exception):
                    continue
                if not await _async_probe_browser_audio(hass, resolved_item):
                    continue
                playable.append((row, resolved_item))
            if len(playable) >= 100:
                break
        if not playable:
            raise FitnessYTDLPError("This YouTube playlist contains no browser-playable tracks")
        playlist_items = []
        for row, _resolved in playable:
            item_target = str(row.get("url") or "")
            playlist_items.append({
                "title": str(row.get("title") or item_target),
                "media_content_id": f"{FITNESS_YTDLP_PREFIX}{quote(f'track|{item_target}', safe='')}",
                "can_play": True,
                "thumbnail": str(row.get("thumbnail") or ""),
                "artist": str(row.get("artist") or ""),
                "duration": float(row.get("duration") or 0.0) if isinstance(row.get("duration"), (int, float)) else 0.0,
                "details": "yt-dlp",
                "provider": "yt_dlp",
                "provider_name": "YouTube",
                "provider_origin": "YouTube · yt-dlp",
                "media_class": "track",
                "external_url": item_target,
            })
        first_row, first = playable[0]
        return {
            "kind": "audio",
            "url": hub._music_proxy_url(first.url, headers=first.headers),
            "title": first.title or str(first_row.get("title") or target),
            "artist": first.artist or str(first_row.get("artist") or ""),
            "thumbnail": first.thumbnail or str(first_row.get("thumbnail") or ""),
            "duration": hub._media_seconds(first.duration),
            "details": "yt-dlp playlist",
            "provider": "yt_dlp",
            "provider_name": "YouTube",
            "provider_origin": "YouTube · yt-dlp",
            "media_class": "playlist",
            "playlist_title": target,
            "playlist_items": playlist_items,
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
    if not await _async_probe_browser_audio(hass, resolved):
        raise FitnessYTDLPError("The resolved YouTube audio stream is not playable by this browser")
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
