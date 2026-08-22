"""Registry/orchestration for independently maintained music adapters."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

from .base import MUSIC_SEARCH_MEDIA_TYPES, MusicAdapter, clamp_search_limit
from .direct_url import async_resolve as resolve_direct_url
from .legacy_spotify import async_resolve as resolve_legacy_spotify
from .music_assistant import MusicAssistantMusicAdapter
from .radio_browser import RadioBrowserMusicAdapter, async_resolve as resolve_radio
from .soundcloud import async_resolve as resolve_soundcloud
from .provider_catalog import async_provider_catalog
from .youtube import async_resolve as resolve_youtube
from .yt_dlp import YTDLPMusicAdapter, async_resolve as resolve_ytdlp

if TYPE_CHECKING:
    from ..tv_dashboard import FitnessTVDashboardHub


async def async_music_adapters(
    hass: HomeAssistant,
    hub: "FitnessTVDashboardHub",
    *,
    ytdlp_enabled: bool,
    adapter_options: dict[str, dict[str, Any]] | None = None,
    current_player_id: str = "",
    allow_music_assistant: bool = True,
) -> list[MusicAdapter]:
    """Return only currently installed and usable adapters."""
    adapters: list[MusicAdapter] = [RadioBrowserMusicAdapter(hub)]
    options = adapter_options or {}
    if allow_music_assistant:
        created = await asyncio.gather(
            MusicAssistantMusicAdapter.async_create(
                hass,
                profile_options=options.get("music_assistant"),
                current_player_id=current_player_id,
            ),
        )
        adapters.extend(adapter for adapter in created if adapter is not None)
    if ytdlp_enabled and YTDLPMusicAdapter.available():
        adapters.append(YTDLPMusicAdapter(hass))
    adapters.sort(key=lambda adapter: (adapter.info.adapter_id != "radio_browser", adapter.info.name.casefold()))
    return adapters


async def async_music_provider_catalog(
    hass: HomeAssistant,
    *,
    adapter_options: dict[str, dict[str, Any]] | None = None,
    ytdlp_enabled: bool = False,
    allow_music_assistant: bool = True,
) -> list[dict[str, Any]]:
    """Return install/configure choices separately from active adapters."""
    return await async_provider_catalog(
        hass,
        adapter_options=adapter_options,
        ytdlp_enabled=ytdlp_enabled,
        allow_music_assistant=allow_music_assistant,
    )


async def async_search_music(
    hass: HomeAssistant,
    hub: "FitnessTVDashboardHub",
    *,
    query: str,
    adapter_ids: list[str] | None,
    ytdlp_enabled: bool,
    limit: int,
    adapter_options: dict[str, dict[str, Any]] | None = None,
    search_scopes: dict[str, list[str]] | None = None,
    media_types: list[str] | None = None,
    current_player_id: str = "",
    allow_music_assistant: bool = True,
) -> dict[str, Any]:
    """Search selected installed adapters concurrently."""
    query = str(query or "").strip()[:256]
    limit = clamp_search_limit(limit)
    if not query:
        return {"query":"", "children":[], "groups":[], "errors":{}, "limit":limit}
    adapters = await async_music_adapters(
        hass,
        hub,
        ytdlp_enabled=ytdlp_enabled,
        adapter_options=adapter_options,
        current_player_id=current_player_id,
        allow_music_assistant=allow_music_assistant,
    )
    searchable = [adapter for adapter in adapters if adapter.info.can_search and adapter.info.available]
    selected_media_types = (
        [
            media_type
            for media_type in MUSIC_SEARCH_MEDIA_TYPES
            if media_type in {str(item).strip().lower() for item in media_types if str(item).strip()}
        ]
        if media_types is not None
        else list(MUSIC_SEARCH_MEDIA_TYPES)
    )
    if media_types is not None and not selected_media_types:
        return {
            "query": query, "children": [], "groups": [], "errors": {},
            "searched_adapters": [], "media_types": [], "limit": limit,
        }
    requested = {str(item).strip() for item in (adapter_ids or []) if str(item).strip()}
    if requested and "all" not in requested:
        searchable = [adapter for adapter in searchable if adapter.info.adapter_id in requested]

    async def _run(adapter: MusicAdapter):
        try:
            scopes = [
                str(item)[:256]
                for item in list(
                    (search_scopes or {}).get(adapter.info.adapter_id) or []
                )[:32]
            ]
            async with asyncio.timeout(30.0):
                children = await adapter.async_search(
                    query,
                    limit=limit,
                    scopes=scopes,
                    media_types=selected_media_types,
                )
            return adapter, children, None
        except Exception as err:  # noqa: BLE001 - isolate provider failures
            # Provider exceptions can contain credentials, full upstream URLs,
            # or large response snippets. Keep those out of the browser payload.
            return adapter, [], type(err).__name__

    completed = await asyncio.gather(*(_run(adapter) for adapter in searchable))
    groups: list[dict[str, Any]] = []
    flat: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for adapter, children, error in completed:
        if error:
            errors[adapter.info.adapter_id] = error
        normalized = []
        for child in children[:limit]:
            row = dict(child)
            row.setdefault("adapter_id", adapter.info.adapter_id)
            row.setdefault("adapter_name", adapter.info.name)
            normalized.append(row)
        groups.append({"adapter":adapter.info.as_dict(), "children":normalized, "error":error or ""})
        flat.extend(normalized)
    return {
        "query": query,
        "children": flat,
        "groups": groups,
        "errors": errors,
        "searched_adapters": [adapter.info.adapter_id for adapter in searchable],
        "media_types": selected_media_types,
        "limit": limit,
    }


async def async_resolve_fitness_media(
    hass: HomeAssistant,
    hub: "FitnessTVDashboardHub",
    media_content_id: str,
    *,
    ytdlp_enabled: bool,
) -> dict[str, Any]:
    """Delegate Fitness-native IDs to their owning adapter module."""
    media_content_id = str(media_content_id or "").strip()
    for resolver in (resolve_radio, resolve_youtube, resolve_soundcloud, resolve_direct_url, resolve_legacy_spotify):
        result = await resolver(hub, media_content_id)
        if result is not None:
            return result
    result = await resolve_ytdlp(hass, hub, media_content_id, enabled=ytdlp_enabled)
    if result is not None:
        return result
    raise ValueError("Not a Fitness-native media ID")
