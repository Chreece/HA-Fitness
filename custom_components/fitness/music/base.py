"""Shared primitives for Fitness TV music adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import SearchMediaQuery
from homeassistant.core import HomeAssistant

DEFAULT_MUSIC_SEARCH_LIMIT = 50
MIN_MUSIC_SEARCH_LIMIT = 10
MAX_MUSIC_SEARCH_LIMIT = 100

MUSIC_SEARCH_MEDIA_TYPES: tuple[str, ...] = (
    "track",
    "album",
    "playlist",
    "artist",
    "radio",
    "podcast",
    "audiobook",
)
DEFAULT_MUSIC_SEARCH_MEDIA_TYPES: tuple[str, ...] = MUSIC_SEARCH_MEDIA_TYPES


def clamp_search_limit(value: Any) -> int:
    """Clamp a user configured result count to the supported range."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_MUSIC_SEARCH_LIMIT
    return max(MIN_MUSIC_SEARCH_LIMIT, min(MAX_MUSIC_SEARCH_LIMIT, parsed))


@dataclass(frozen=True, slots=True)
class MusicAdapterInfo:
    """Public capabilities of one installed Fitness music adapter."""

    adapter_id: str
    name: str
    icon: str
    can_search: bool = False
    can_browse: bool = False
    can_play_link: bool = False
    available: bool = True
    experimental: bool = False
    account_setup: str = "none"
    setup_hint: str = ""
    setup_hint_key: str = ""
    setup_path: str = ""
    source: str = "fitness"
    account_options: tuple[tuple[str, str], ...] = ()
    selected_account_id: str = ""
    search_scopes: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.adapter_id,
            "name": self.name,
            "icon": self.icon,
            "can_search": self.can_search,
            "can_browse": self.can_browse,
            "can_play_link": self.can_play_link,
            "available": self.available,
            "enabled": self.available,
            "experimental": self.experimental,
            "account_setup": self.account_setup,
            "setup_hint": self.setup_hint,
            "setup_hint_key": self.setup_hint_key,
            "setup_path": self.setup_path,
            "source": self.source,
            "account_options": [{"id": account_id, "name": name} for account_id, name in self.account_options],
            "selected_account_id": self.selected_account_id,
            "search_scopes": [dict(item) for item in self.search_scopes],
            "unavailable_reason": "",
        }


class MusicAdapter:
    """Base class for one installed/usable Fitness music source."""

    info: MusicAdapterInfo

    async def async_search(
        self,
        query: str,
        *,
        limit: int,
        scopes: list[str] | None = None,
        media_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search this adapter."""
        raise NotImplementedError


async def async_find_media_source(
    hass: HomeAssistant, domains: tuple[str, ...]
) -> tuple[str, Any] | None:
    """Return one installed HA media source whose root domain matches."""
    try:
        root = await media_source.async_browse_media(hass, None)
    except Exception:  # noqa: BLE001 - source registry can be unavailable at startup
        return None
    wanted = {domain.casefold() for domain in domains}
    for child in list(getattr(root, "children", None) or []):
        content_id = str(getattr(child, "media_content_id", "") or "").strip()
        if not content_id.startswith("media-source://"):
            continue
        domain = content_id[len("media-source://") :].split("/", 1)[0].strip()
        if domain.casefold() not in wanted:
            continue
        detail = child
        try:
            detail = await media_source.async_browse_media(hass, content_id)
        except Exception:  # noqa: BLE001 - child can still be a valid source
            pass
        return content_id, detail
    return None


async def async_search_media_source(
    hass: HomeAssistant,
    source_id: str,
    query: str,
    *,
    limit: int,
    adapter_id: str,
    adapter_name: str,
) -> list[dict[str, Any]]:
    """Normalize Home Assistant Media Source search results."""
    searched = await media_source.async_search_media(
        hass,
        source_id,
        SearchMediaQuery(search_query=query),
    )
    results: list[dict[str, Any]] = []
    for item in list(getattr(searched, "result", ()) or ()):
        try:
            raw = item.as_dict(parent=False)
        except Exception:  # noqa: BLE001 - third-party source result
            continue
        content_id = str(raw.get("media_content_id") or "").strip()
        title = str(raw.get("title") or content_id).strip()
        if not content_id or not title:
            continue
        results.append(
            {
                "title": title,
                "media_content_id": content_id,
                "can_play": bool(raw.get("can_play")),
                "can_expand": bool(raw.get("can_expand")),
                "thumbnail": str(raw.get("thumbnail") or "").strip(),
                "icon": str(raw.get("icon") or "").strip(),
                "media_class": str(raw.get("media_class") or "").strip(),
                "artist": str(raw.get("artist") or raw.get("media_artist") or "").strip(),
                "album": str(raw.get("album") or raw.get("media_album_name") or "").strip(),
                "year": raw.get("year") or raw.get("release_year") or "",
                "duration": float(raw.get("duration") or raw.get("media_duration") or 0.0) if isinstance(raw.get("duration") or raw.get("media_duration"), (int, float)) else 0.0,
                "provider": str(raw.get("provider") or adapter_id).strip(),
                "provider_name": str(raw.get("provider_name") or adapter_name).strip(),
                "provider_origin": str(raw.get("provider_origin") or adapter_name).strip(),
                "details": str(raw.get("details") or "").strip(),
                "adapter_id": adapter_id,
                "adapter_name": adapter_name,
            }
        )
        if len(results) >= clamp_search_limit(limit):
            break
    return results
