"""Persistent TV-dashboard preferences and in-browser audio routing for Fitness."""

from __future__ import annotations

import asyncio
from ipaddress import ip_address
import json
import logging
import re
import socket
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin, urlparse
from uuid import uuid4

from aiohttp import ClientTimeout, WSMsgType, web
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CAST_APP_ID_HOMEASSISTANT_LOVELACE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.network import get_url
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .access_control import get_fitness_access_controller
from .live import get_live_runtime
from .resource_safety import async_call_service, bounded_payload, bounded_websocket_payload

from .const import (
    CONF_TV_DASHBOARD_ENABLED,
    CONF_TV_DUCKING_PERCENT,
    CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
    CONF_TV_MEDIA_PLAYER_ID,
    CONF_TV_YTDLP_ENABLED,
    DEFAULT_TV_DUCKING_PERCENT,
    DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
    DOMAIN,
)

from .music_adapters import (
    DEFAULT_MUSIC_SEARCH_LIMIT,
    DEFAULT_MUSIC_SEARCH_MEDIA_TYPES,
    MAX_MUSIC_SEARCH_LIMIT,
    MIN_MUSIC_SEARCH_LIMIT,
    MUSIC_SEARCH_MEDIA_TYPES,
    async_music_adapters,
    async_music_provider_catalog,
    async_resolve_fitness_media as resolve_music_adapter_media,
    async_search_music,
    clamp_search_limit,
)
from .music.radio_browser import FITNESS_RADIO_PREFIX
from .music.direct_url import FITNESS_URL_PREFIX
from .music.yt_dlp import FITNESS_YTDLP_PREFIX
from .music.youtube import FITNESS_YOUTUBE_PREFIX
from .music.soundcloud import FITNESS_SOUNDCLOUD_PREFIX
from .music.music_assistant import (
    FITNESS_MA_PREFIX,
    async_music_assistant_playlist,
    async_music_assistant_playlist_remove,
    async_music_assistant_queue_command,
    async_play_music_assistant_uri,
    async_play_music_assistant_uris,
    async_seek_music_assistant,
    async_stop_music_assistant_player,
    decode_music_assistant_media_id,
    music_assistant_busy_provider_tokens,
    music_assistant_direct_sendspin_url,
    music_assistant_entries,
    music_assistant_music_provider_scopes,
    music_assistant_queue_state,
    music_assistant_sendspin_url,
    select_music_assistant_entry,
)
from .remote_gateway import async_register_remote_gateway_websocket_commands

TV_AUDIO_EVENT = "fitness_tv_audio"
TV_MEDIA_EVENT = "fitness_tv_media"
TV_MEDIA_STATE_EVENT = "fitness_tv_media_state"
TV_SETTINGS_EVENT = "fitness_tv_settings"
TV_STORE_VERSION = 1
TV_STORE_KEY = "fitness.tv_dashboard"
TV_HUB_KEY = "_tv_dashboard_hub"
DEFAULT_TV_SCALE_PERCENT = 70
DEFAULT_TV_OLED_PROTECTION = False
DEFAULT_AUDIO_OUTPUT_ID = "__fitness_browser__"
DEFAULT_DASHBOARD_NAME = "Main"
MAX_DASHBOARD_NAME_LENGTH = 48
CAST_CLIENT_STALE_SECONDS = 14.0
CAST_STATE_GRACE_SECONDS = 5.0

# Fitness-native media prefixes live with their owning adapter modules.
RADIO_BROWSER_BASE = "https://all.api.radio-browser.info"
RADIO_BROWSER_TIMEOUT = 12.0
MUSIC_PROXY_TTL_SECONDS = 30 * 60
MUSIC_PROXY_VIEW_KEY = "_tv_music_proxy_view_registered"
MA_SENDSPIN_PROXY_TTL_SECONDS = 30 * 60.0
MA_SENDSPIN_PROXY_VIEW_KEY = "_tv_ma_sendspin_proxy_view_registered"
MUSIC_PROXY_CONNECT_SECONDS = 15.0
MUSIC_PROXY_READ_SECONDS = 90.0
SENDSPIN_MAX_MESSAGE_BYTES = 2 * 1024 * 1024
TV_CLIENTS_PER_PROFILE_LIMIT = 64
TV_PROXY_TOKEN_LIMIT = 256
TV_MA_PLAYERS_PER_PROFILE_LIMIT = 64
TV_ANNOUNCEMENT_LIMIT = 64
TV_PROXY_CONCURRENCY_LIMIT = 16
TV_SENDSPIN_CONCURRENCY_LIMIT = 16
TV_MUSIC_SEARCH_CONCURRENCY_LIMIT = 4
TV_MUSIC_QUERY_LIMIT = 256
TV_PROXY_REDIRECT_LIMIT = 5
_FITNESS_MA_PLAYER_RE = re.compile(r"^fitness-tv-[A-Za-z0-9_-]{8,220}$")
_SAFE_PROXY_REQUEST_HEADERS = {
    "accept",
    "accept-language",
    "origin",
    "referer",
    "user-agent",
}
_RANGE_RE = re.compile(r"^bytes=(?:\d+-\d*|-\d+)$")

_LOGGER = logging.getLogger(__name__)


def _public_http_target(value: Any) -> tuple[str, str, int | None]:
    """Return a normalized public-HTTP target tuple or raise ValueError."""
    raw = str(value or "").strip()
    if len(raw) > 8_192:
        raise ValueError("invalid_proxy_target")
    try:
        parsed = urlparse(raw)
        port = parsed.port
    except ValueError as err:
        raise ValueError("invalid_proxy_target") from err
    host = str(parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or host == "localhost"
        or host.endswith((".localhost", ".local", ".internal", ".home.arpa"))
    ):
        raise ValueError("invalid_proxy_target")
    try:
        address = ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("private_proxy_target")
    return raw, host, port


async def _async_validate_public_http_target(hass: HomeAssistant, value: Any) -> str:
    """Reject local/special destinations before opening an upstream stream."""
    raw, host, port = _public_http_target(value)
    try:
        ip_address(host)
        return raw
    except ValueError:
        pass

    def _resolve() -> list[tuple[Any, ...]]:
        return socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
        )

    try:
        async with asyncio.timeout(5.0):
            rows = await hass.async_add_executor_job(_resolve)
    except (OSError, TimeoutError) as err:
        raise ValueError("proxy_target_unavailable") from err
    addresses = {
        str(row[4][0]).split("%", 1)[0]
        for row in rows
        if len(row) > 4 and row[4]
    }
    if not addresses or any(not ip_address(item).is_global for item in addresses):
        raise ValueError("private_proxy_target")
    return raw

# These IDs are intentionally stable. They are stored per Fitness profile and
# are therefore independent of card titles or the user's dashboard language.
TV_CARD_IDS: tuple[str, ...] = (
    "today",
    "live_workout",
    "workout",
    "ai_today",
    "ai_last_workout",
    "workout_highlights",
    "workout_rpe",
    "strength_details",
    "sleep_recovery",
    "sleep_stages",
    "recovery",
    "evaluation",
    "progress",
    "training_adaptation",
    "training_load",
    "route",
    "comparison",
    "training_plan",
    "fitness_tests",
    "plugin_rss",
    "plugin_weather",
    "plugin_lights",
    "plugin_music",
    "plugin_video",
    "plugin_tts",
)
DEFAULT_TV_CARD_IDS: tuple[str, ...] = (
    "live_workout",
    "workout",
    "sleep_recovery",
    "evaluation",
)


class FitnessTVDashboardHub:
    """Coordinate persistent TV preferences and one audible browser per profile."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store[dict[str, Any]](
            hass,
            TV_STORE_VERSION,
            TV_STORE_KEY,
        )
        self._loaded = False
        self._data: dict[str, Any] = {"profiles": {}}
        self._load_lock = asyncio.Lock()
        self._store_lock = asyncio.Lock()
        # profile -> client -> metadata about active dashboards
        self._clients: dict[str, dict[str, dict[str, Any]]] = {}
        # announcement -> (expected client, completion future)
        self._announcements: dict[str, tuple[str, asyncio.Future[bool]]] = {}
        # Most recent shared media state per profile so controllers and receivers stay in sync.
        self._media_state: dict[str, dict[str, Any]] = {}
        # Profile -> Cast entity expected to own audio. While a cast launch is
        # in progress, audio commands wait briefly for the receiver heartbeat
        # instead of falling back to the laptop that initiated the cast.
        self._expected_cast: dict[str, str] = {}
        # Monotonic launch generation per profile. Every new server-side Cast
        # request invalidates older in-flight wake/retry work so a late failure
        # from an offline target cannot tear down a newer successful receiver.
        self._cast_generation: dict[str, int] = {}
        self._expected_cast_generation: dict[str, int] = {}
        # Browser-local Cast sessions have no Home Assistant media_player entity.
        # Track them separately so a remote browser can hand music/TTS ownership
        # to the Cast receiver without pretending the TV is server-discovered.
        # profile -> source/controller client id that initiated the local Cast.
        self._expected_local_cast: dict[str, str] = {}
        self._local_cast_established_at: dict[str, float] = {}
        self._local_cast_accept_after: dict[str, float] = {}
        # Exactly one browser owns audible music/TTS per Fitness profile. This
        # prevents old tabs or previous Cast receiver sessions from continuing
        # to play after a newer dashboard session takes over.
        self._audio_owner: dict[str, str] = {}
        # When a fresh Cast launch is expected, existing Cast browser IDs are
        # ignored so a stale background receiver cannot immediately reclaim audio.
        self._ignored_cast_clients: dict[str, set[str]] = {}
        # A Cast session only becomes authoritative after the new TV browser has
        # actually heartbeated.  This prevents a stale Cast entity app_id from
        # making the laptop believe a powered-off TV is still running Fitness.
        self._cast_established_at: dict[str, float] = {}
        self._cast_accept_after: dict[str, float] = {}
        self._cast_watchdogs: dict[str, asyncio.Task[None]] = {}
        self._cast_target_unsubs: dict[str, Callable[[], None]] = {}
        # Opaque, short-lived targets used by the same-origin audio proxy.
        # This avoids HTTPS mixed-content/CORS failures for public radio and
        # direct stream URLs while never exposing the upstream URL in the TV UI.
        self._music_proxy_targets: dict[str, tuple[str, float, dict[str, str]]] = {}
        # Opaque one-profile/one-MA-server WebSocket relay tickets.  The browser
        # never receives the MA server URL and the relay works through the same
        # HA HTTPS origin, including remote Fitness TV clients and Cast receivers.
        self._ma_sendspin_targets: dict[str, tuple[str, str, str, float]] = {}
        # Fitness profile -> MA browser player id -> MA config entry id.  This
        # lets profile/HA unload stop account-backed queues (Spotify etc.) before
        # their Sendspin browser disappears and leaves the provider falsely busy.
        self._ma_players: dict[str, dict[str, str]] = {}
        self._active_proxy_streams = 0
        self._active_sendspin_streams = 0
        self._active_music_searches: set[str] = set()
        self._active_music_resolutions: set[str] = set()
        # Radio Browser country codes change very rarely, so cache them for the
        # lifetime of this hub instead of downloading them on every search.
        self._radio_country_codes: list[dict[str, str]] | None = None

    async def async_load(self) -> None:
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                return
            saved = await self._store.async_load()
            rewrite_loaded_profiles = False
            if isinstance(saved, dict):
                profiles = saved.get("profiles")
                if isinstance(profiles, dict):
                    rewrite_loaded_profiles = True
                    clean_profiles: dict[str, dict[str, Any]] = {}
                    for raw_profile_id, raw_profile in profiles.items():
                        profile_id = str(raw_profile_id or "").strip()[:128]
                        if not profile_id or not isinstance(raw_profile, dict):
                            continue
                        clean_profiles[profile_id] = self._sanitize_profile(raw_profile)
                        if len(clean_profiles) >= 256:
                            break
                    self._data = {"profiles": clean_profiles}
                    # Restore only the last selected media, never a stale playing
                    # flag. A fresh browser/Cast receiver must explicitly start it.
                    for profile_entry_id, raw_profile in clean_profiles.items():
                        last_media = self._sanitize_last_media(raw_profile.get("last_media"))
                        if last_media:
                            self._media_state[str(profile_entry_id)] = {
                                **last_media,
                                "playing": False,
                                "error": False,
                            }
            self._loaded = True
            if rewrite_loaded_profiles:
                # Always rewrite the now-small snapshot. Comparing it recursively to
                # a potentially enormous legacy object would itself block MainThread.
                await self._async_save_data()

    async def _async_save_data(self) -> None:
        """Serialize TV preference writes so rapid controls cannot overlap."""
        async with self._store_lock:
            await self._store.async_save(self._data)

    @staticmethod
    def _sanitize_cards(cards: Any) -> list[str]:
        allowed = set(TV_CARD_IDS)
        result: list[str] = []
        for raw in cards if isinstance(cards, (list, tuple)) else ():
            card_id = str(raw)
            if card_id in allowed and card_id not in result:
                result.append(card_id)
        return result

    @staticmethod
    def _sanitize_favorites(favorites: Any) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw in favorites if isinstance(favorites, (list, tuple)) else ():
            if not isinstance(raw, dict):
                continue
            media_content_id = str(raw.get("media_content_id") or "").strip()[:4096]
            if not media_content_id or media_content_id in seen:
                continue
            seen.add(media_content_id)
            item = {
                "media_content_id": media_content_id,
                "title": str(raw.get("title") or media_content_id).strip()[:512],
            }
            for key, limit in (
                ("artist", 512), ("album", 512), ("thumbnail", 4096),
                ("details", 512), ("provider", 240), ("provider_name", 240),
                ("provider_origin", 512),
            ):
                value = str(raw.get(key) or "").strip()
                if value:
                    item[key] = value[:limit]
            year = str(raw.get("year") or "").strip()
            if year:
                item["year"] = year[:16]
            try:
                duration = float(raw.get("duration") or 0)
            except (TypeError, ValueError):
                duration = 0.0
            if duration > 0:
                item["duration"] = duration
            result.append(item)
            if len(result) >= 100:
                break
        return result

    @staticmethod
    def _sanitize_playlist_item(raw: Any) -> dict[str, Any]:
        """Normalize one persisted Fitness playlist media item."""
        if not isinstance(raw, dict):
            return {}
        media_content_id = str(raw.get("media_content_id") or "").strip()
        if not media_content_id:
            return {}
        item: dict[str, Any] = {
            "media_content_id": media_content_id[:4096],
            "title": str(raw.get("title") or media_content_id).strip()[:512],
        }
        for key, limit in (
            ("artist", 512), ("album", 512), ("thumbnail", 4096),
            ("details", 512), ("provider", 240), ("provider_name", 240),
            ("provider_origin", 512), ("provider_instance", 240),
            ("media_class", 80), ("adapter_id", 120), ("adapter_name", 240),
            ("external_url", 4096),
        ):
            value = str(raw.get(key) or "").strip()
            if value:
                item[key] = value[:limit]
        year = str(raw.get("year") or "").strip()
        if year:
            item["year"] = year[:16]
        try:
            duration = float(raw.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration > 0:
            item["duration"] = duration
        item["is_live"] = bool(raw.get("is_live", False))
        item["can_play"] = bool(raw.get("can_play", True))
        item["can_expand"] = bool(raw.get("can_expand", False))
        return item

    @classmethod
    def _sanitize_user_playlists(cls, playlists: Any) -> list[dict[str, Any]]:
        """Keep profile-owned playlists bounded and free of provider secrets."""
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, raw in enumerate(playlists if isinstance(playlists, (list, tuple)) else ()):
            if not isinstance(raw, dict):
                continue
            playlist_id = str(raw.get("id") or "").strip()[:120]
            if not playlist_id or playlist_id in seen:
                continue
            seen.add(playlist_id)
            name = str(raw.get("name") or f"Playlist {index + 1}").strip()[:160] or f"Playlist {index + 1}"
            items: list[dict[str, Any]] = []
            for raw_item in raw.get("items") if isinstance(raw.get("items"), (list, tuple)) else ():
                item = cls._sanitize_playlist_item(raw_item)
                if item:
                    items.append(item)
                if len(items) >= 500:
                    break
            thumbnail = str(raw.get("thumbnail") or "").strip()[:4096]
            if not thumbnail:
                thumbnail = next((str(item.get("thumbnail") or "") for item in items if item.get("thumbnail")), "")
            result.append({
                "id": playlist_id,
                "name": name,
                "items": items,
                "thumbnail": thumbnail,
            })
            if len(result) >= 50:
                break
        return result

    @staticmethod
    def _sanitize_music_adapters(adapters: Any) -> list[str]:
        result: list[str] = []
        for raw in adapters if isinstance(adapters, (list, tuple)) else ():
            adapter_id = str(raw or "").strip()
            if not adapter_id or len(adapter_id) > 120 or adapter_id in result:
                continue
            result.append(adapter_id)
            if len(result) >= 100:
                break
        return result

    @staticmethod
    def _sanitize_music_search_types(media_types: Any) -> list[str]:
        """Keep the ordered, supported result types selected for music search."""
        requested = {
            str(item or "").strip().lower()
            for item in media_types if isinstance(media_types, (list, tuple))
        }
        return [media_type for media_type in MUSIC_SEARCH_MEDIA_TYPES if media_type in requested]

    @staticmethod
    def _sanitize_music_search_scopes(scopes: Any) -> dict[str, list[str]]:
        """Keep profile-scoped search-provider selections as adapter -> scope ids."""
        if not isinstance(scopes, dict):
            return {}
        result: dict[str, list[str]] = {}
        for raw_adapter_id, raw_values in scopes.items():
            adapter_id = str(raw_adapter_id or "").strip()
            if not adapter_id or len(adapter_id) > 120 or not isinstance(raw_values, (list, tuple)):
                continue
            values: list[str] = []
            for item in raw_values[:100]:
                value = str(item or "").strip()[:240]
                if value and value not in values:
                    values.append(value)
            # Preserve an explicit empty list: it is different from never having
            # saved provider scopes for this adapter.
            result[adapter_id] = values
            if len(result) >= 100:
                break
        return result

    @staticmethod
    def _sanitize_music_adapter_options(options: Any) -> dict[str, dict[str, Any]]:
        """Keep small, profile-scoped adapter settings without provider secrets."""
        if not isinstance(options, dict):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for raw_adapter_id, raw_values in options.items():
            adapter_id = str(raw_adapter_id or "").strip()
            if not adapter_id or len(adapter_id) > 120 or not isinstance(raw_values, dict):
                continue
            clean: dict[str, Any] = {}
            for raw_key, raw_value in raw_values.items():
                key = str(raw_key or "").strip()
                if not key or len(key) > 80:
                    continue
                if isinstance(raw_value, bool):
                    clean[key] = raw_value
                elif isinstance(raw_value, int):
                    clean[key] = max(-1_000_000, min(1_000_000, raw_value))
                elif isinstance(raw_value, str):
                    clean[key] = raw_value.strip()[:240]
                elif isinstance(raw_value, (list, tuple)):
                    values: list[str] = []
                    for item in raw_value[:50]:
                        value = str(item or "").strip()[:240]
                        if value and value not in values:
                            values.append(value)
                    clean[key] = values
            if clean:
                result[adapter_id] = clean
            if len(result) >= 100:
                break
        return result

    @staticmethod
    def _sanitize_last_media(last_media: Any) -> dict[str, Any]:
        if not isinstance(last_media, dict):
            return {}
        media_content_id = str(last_media.get("media_content_id") or "").strip()[:4096]
        if not media_content_id:
            return {}
        result: dict[str, Any] = {
            "media_content_id": media_content_id,
            "title": str(last_media.get("title") or media_content_id).strip()[:512],
        }
        for key, limit in (
            ("artist", 512), ("album", 512), ("thumbnail", 4096),
            ("details", 512), ("provider", 240), ("provider_name", 240),
            ("provider_origin", 512),
        ):
            value = str(last_media.get(key) or "").strip()
            if value:
                result[key] = value[:limit]
        year = str(last_media.get("year") or "").strip()
        if year:
            result["year"] = year[:16]
        try:
            duration = float(last_media.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        try:
            position = float(last_media.get("position") or 0)
        except (TypeError, ValueError):
            position = 0.0
        if duration > 0:
            result["duration"] = duration
            position = min(max(0.0, position), duration)
        if position > 0:
            result["position"] = max(0.0, position)
        playlist_context = FitnessTVDashboardHub._sanitize_playlist_context(
            last_media.get("playlist_context")
        )
        if playlist_context:
            result["playlist_context"] = playlist_context
        return result

    @classmethod
    def _sanitize_profile(cls, raw: Any) -> dict[str, Any]:
        """Discard unknown or unbounded fields from one persisted TV profile.

        Dashboard definitions are part of the durable profile state.  Older
        versions accidentally sanitized them out while loading the Store, which
        made every restart rewrite the profile back to the legacy single
        ``Main`` dashboard.  Normalize/migrate them here before the cleaned
        snapshot is written back.
        """
        if not isinstance(raw, dict):
            return {}
        result: dict[str, Any] = {}
        dashboards, active_dashboard_id = cls._sanitize_dashboards(raw)
        result["dashboards"] = dashboards
        result["active_dashboard_id"] = active_dashboard_id
        active_dashboard = next(
            row for row in dashboards if row["id"] == active_dashboard_id
        )
        # Keep the legacy field synchronized for older dashboard clients while
        # the canonical multi-dashboard definition remains ``dashboards``.
        result["cards"] = list(active_dashboard["cards"])
        sanitizers = {
            "favorites": cls._sanitize_favorites,
            "user_playlists": cls._sanitize_user_playlists,
            "last_media": cls._sanitize_last_media,
            "audio_output_id": cls._sanitize_audio_output_id,
            "music_adapters": cls._sanitize_music_adapters,
            "music_adapter_options": cls._sanitize_music_adapter_options,
            "music_search_adapters": cls._sanitize_music_adapters,
            "music_search_scopes": cls._sanitize_music_search_scopes,
            "music_search_types": cls._sanitize_music_search_types,
        }
        for key, sanitizer in sanitizers.items():
            if key in raw:
                result[key] = sanitizer(raw.get(key))
        for key in (
            "oled_protection",
            "animations_enabled",
            "toolbar_auto_hide",
            "light_feedback_enabled",
            "tts_announcements_enabled",
        ):
            if key in raw:
                result[key] = bool(raw.get(key))
        if "tv_scale_percent" in raw:
            try:
                result["tv_scale_percent"] = max(
                    10, min(150, int(raw.get("tv_scale_percent")))
                )
            except (TypeError, ValueError):
                pass
        if "music_search_limit" in raw:
            result["music_search_limit"] = clamp_search_limit(
                raw.get("music_search_limit")
            )
        return result

    @classmethod
    def _sanitize_playlist_context(cls, raw: Any) -> dict[str, Any]:
        """Keep enough bounded playlist context to resume queue navigation."""
        if not isinstance(raw, dict):
            return {}
        kind = str(raw.get("kind") or "").strip().lower()
        if kind not in {"user", "provider", "youtube_playlist", "selection"}:
            return {}
        result: dict[str, Any] = {"kind": kind}
        context_id = str(raw.get("id") or "").strip()
        if context_id:
            result["id"] = context_id[:240]
        title = str(raw.get("title") or "").strip()
        if title:
            result["title"] = title[:512]
        try:
            index = int(raw.get("index") or 0)
        except (TypeError, ValueError):
            index = 0
        result["index"] = max(0, min(499, index))
        result["shuffle"] = bool(raw.get("shuffle", False))
        repeat = str(raw.get("repeat") or "off").strip().lower()
        result["repeat"] = repeat if repeat in {"off", "one", "all"} else "off"

        item = cls._sanitize_playlist_item(raw.get("item"))
        if item:
            result["item"] = item

        if kind == "selection":
            items: list[dict[str, Any]] = []
            for raw_item in raw.get("items") if isinstance(raw.get("items"), (list, tuple)) else ():
                item = cls._sanitize_playlist_item(raw_item)
                if item:
                    items.append(item)
                if len(items) >= 100:
                    break
            if items:
                result["items"] = items
        return result

    @staticmethod
    def _sanitize_audio_output_id(value: Any) -> str:
        output = str(value or DEFAULT_AUDIO_OUTPUT_ID).strip()
        if output == DEFAULT_AUDIO_OUTPUT_ID or output.startswith("media_player."):
            return output
        return DEFAULT_AUDIO_OUTPUT_ID

    async def async_audio_output_id(self, profile_entry_id: str) -> str:
        """Return the persisted audio output for one Fitness profile."""
        prefs = await self.async_preferences(profile_entry_id)
        return self._sanitize_audio_output_id(prefs.get("audio_output_id"))

    def light_feedback_enabled(self, profile_entry_id: str) -> bool:
        """Return the per-profile optical feedback switch without blocking."""
        profile = self._data.get("profiles", {}).get(str(profile_entry_id))
        return bool(profile.get("light_feedback_enabled", True)) if isinstance(profile, dict) else True

    def tts_announcements_enabled(self, profile_entry_id: str) -> bool:
        """Return the per-profile automatic TTS switch without blocking."""
        profile = self._data.get("profiles", {}).get(str(profile_entry_id))
        return bool(profile.get("tts_announcements_enabled", True)) if isinstance(profile, dict) else True

    @staticmethod
    def _sanitize_card_layout(value: Any) -> dict[str, dict[str, float | int]]:
        """Return a bounded, portable per-card layout map."""
        if not isinstance(value, dict):
            return {}
        allowed = set(TV_CARD_IDS)
        result: dict[str, dict[str, float | int]] = {}
        for card_id, raw in list(value.items())[: len(TV_CARD_IDS)]:
            card_id = str(card_id)
            if card_id not in allowed or not isinstance(raw, dict):
                continue
            item: dict[str, float | int] = {}
            try:
                width_percent = float(raw.get("width_percent") or 0)
            except (TypeError, ValueError):
                width_percent = 0
            if width_percent > 0:
                item["width_percent"] = round(max(8.0, min(100.0, width_percent)), 1)
            try:
                column_span = int(round(float(raw.get("column_span") or 0)))
            except (TypeError, ValueError):
                column_span = 0
            if column_span > 0:
                item["column_span"] = max(1, min(12, column_span))
            try:
                height = int(round(float(raw.get("height") or 0)))
            except (TypeError, ValueError):
                height = 0
            if height > 0:
                item["height"] = max(120, min(1600, height))
            if "x_percent" in raw:
                try:
                    x_percent = float(raw.get("x_percent"))
                except (TypeError, ValueError):
                    x_percent = float("nan")
                if x_percent == x_percent and float("-inf") < x_percent < float("inf"):
                    item["x_percent"] = round(max(0.0, min(100.0, x_percent)), 1)
            if item:
                result[card_id] = item
        return result

    @classmethod
    def _sanitize_dashboards(cls, profile: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        """Return bounded dashboard definitions, migrating the legacy single cards list."""
        raw = profile.get("dashboards")
        dashboards: list[dict[str, Any]] = []
        if isinstance(raw, list):
            for index, item in enumerate(raw[:12]):
                if not isinstance(item, dict):
                    continue
                dashboard_id = str(item.get("id") or f"dashboard-{index + 1}")[:64]
                name = str(item.get("name") or f"Dashboard {index + 1}").strip()[:MAX_DASHBOARD_NAME_LENGTH]
                dashboards.append({
                    "id": dashboard_id,
                    "name": name or f"Dashboard {index + 1}",
                    "cards": cls._sanitize_cards(item.get("cards")),
                    "layout": cls._sanitize_card_layout(item.get("layout")),
                    "theme": str(item.get("theme") or "performance")[:32],
                })
        if not dashboards:
            cards = cls._sanitize_cards(profile.get("cards"))
            if "cards" not in profile:
                cards = list(DEFAULT_TV_CARD_IDS)
            dashboards = [{"id": "main", "name": DEFAULT_DASHBOARD_NAME, "cards": cards, "layout": cls._sanitize_card_layout(profile.get("card_layout")), "theme": str(profile.get("fitness_theme") or "performance")[:32]}]
        ids = {row["id"] for row in dashboards}
        active = str(profile.get("active_dashboard_id") or dashboards[0]["id"])
        if active not in ids:
            active = dashboards[0]["id"]
        return dashboards, active

    async def async_manage_dashboard(
        self,
        profile_entry_id: str,
        *,
        action: str,
        dashboard_id: str = "",
        name: str = "",
        dashboard_max: int = 3,
    ) -> dict[str, Any]:
        """Create, rename, select or delete one profile dashboard."""
        await self.async_load()
        current = self._data["profiles"].get(profile_entry_id)
        if not isinstance(current, dict):
            current = {}
        updated = dict(current)
        dashboards, active = self._sanitize_dashboards(updated)
        action = str(action or "").strip()
        dashboard_id = str(dashboard_id or "").strip()
        if action == "create":
            if len(dashboards) >= max(1, int(dashboard_max)):
                raise ValueError("dashboard_limit_reached")
            new_id = f"dashboard-{uuid4().hex[:12]}"
            clean_name = str(name or f"Dashboard {len(dashboards)+1}").strip()[:MAX_DASHBOARD_NAME_LENGTH]
            dashboards.append({"id": new_id, "name": clean_name or f"Dashboard {len(dashboards)+1}", "cards": list(DEFAULT_TV_CARD_IDS), "layout": {}, "theme": "performance"})
            active = new_id
        elif action == "rename":
            clean_name = str(name or "").strip()[:MAX_DASHBOARD_NAME_LENGTH]
            if not clean_name:
                raise ValueError("invalid_dashboard_name")
            found = False
            for row in dashboards:
                if row["id"] == dashboard_id:
                    row["name"] = clean_name
                    found = True
                    break
            if not found:
                raise ValueError("dashboard_not_found")
        elif action == "delete":
            if len(dashboards) <= 1:
                raise ValueError("last_dashboard")
            dashboards = [row for row in dashboards if row["id"] != dashboard_id]
            if active == dashboard_id:
                active = dashboards[0]["id"]
        elif action == "select":
            if dashboard_id not in {row["id"] for row in dashboards}:
                raise ValueError("dashboard_not_found")
            active = dashboard_id
        else:
            raise ValueError("invalid_dashboard_action")
        updated["dashboards"] = dashboards
        updated["active_dashboard_id"] = active
        # Keep legacy cards synchronized with the active dashboard for older clients.
        active_row = next(row for row in dashboards if row["id"] == active)
        updated["cards"] = list(active_row["cards"])
        self._data["profiles"][profile_entry_id] = updated
        await self._async_save_data()
        return await self.async_preferences(profile_entry_id)

    async def async_preferences(self, profile_entry_id: str) -> dict[str, Any]:
        await self.async_load()
        profile = self._data["profiles"].get(profile_entry_id)
        if not isinstance(profile, dict):
            profile = {}
        dashboards, active_dashboard_id = self._sanitize_dashboards(profile)
        active_dashboard = next(
            row for row in dashboards if row["id"] == active_dashboard_id
        )
        cards = list(active_dashboard["cards"])
        try:
            scale = int(profile.get("tv_scale_percent", DEFAULT_TV_SCALE_PERCENT))
        except (TypeError, ValueError):
            scale = DEFAULT_TV_SCALE_PERCENT
        return {
            "cards": cards,
            "dashboards": dashboards,
            "active_dashboard_id": active_dashboard_id,
            "favorites": self._sanitize_favorites(profile.get("favorites")),
            "user_playlists": self._sanitize_user_playlists(profile.get("user_playlists")),
            "last_media": self._sanitize_last_media(profile.get("last_media")),
            "tv_scale_percent": max(10, min(150, scale)),
            "oled_protection": bool(
                profile.get("oled_protection", DEFAULT_TV_OLED_PROTECTION)
            ),
            "animations_enabled": bool(profile.get("animations_enabled", True)),
            "toolbar_auto_hide": bool(profile.get("toolbar_auto_hide", False)),
            "light_feedback_enabled": bool(profile.get("light_feedback_enabled", True)),
            "tts_announcements_enabled": bool(profile.get("tts_announcements_enabled", True)),
            "audio_output_id": self._sanitize_audio_output_id(profile.get("audio_output_id")),
            "music_adapters": self._sanitize_music_adapters(profile.get("music_adapters")),
            "music_adapters_configured": "music_adapters" in profile,
            "music_adapter_options": self._sanitize_music_adapter_options(profile.get("music_adapter_options")),
            "music_search_limit": clamp_search_limit(profile.get("music_search_limit", DEFAULT_MUSIC_SEARCH_LIMIT)),
            "music_search_adapters": self._sanitize_music_adapters(profile.get("music_search_adapters")),
            "music_search_configured": "music_search_adapters" in profile,
            "music_search_scopes": self._sanitize_music_search_scopes(profile.get("music_search_scopes")),
            "music_search_types": (
                self._sanitize_music_search_types(profile.get("music_search_types"))
                if "music_search_types" in profile
                else list(DEFAULT_MUSIC_SEARCH_MEDIA_TYPES)
            ),
            "music_search_types_configured": "music_search_types" in profile,
        }

    async def async_set_preferences(
        self,
        profile_entry_id: str,
        *,
        cards: list[str] | None = None,
        dashboard_id: str | None = None,
        card_layout: dict[str, Any] | None = None,
        favorites: list[dict[str, Any]] | None = None,
        user_playlists: list[dict[str, Any]] | None = None,
        last_media: dict[str, Any] | None = None,
        tv_scale_percent: int | None = None,
        oled_protection: bool | None = None,
        animations_enabled: bool | None = None,
        toolbar_auto_hide: bool | None = None,
        light_feedback_enabled: bool | None = None,
        tts_announcements_enabled: bool | None = None,
        audio_output_id: str | None = None,
        music_adapters: list[str] | None = None,
        music_adapter_options: dict[str, Any] | None = None,
        music_search_limit: int | None = None,
        music_search_adapters: list[str] | None = None,
        music_search_scopes: dict[str, Any] | None = None,
        music_search_types: list[str] | None = None,
    ) -> dict[str, Any]:
        await self.async_load()
        current = self._data["profiles"].get(profile_entry_id)
        if not isinstance(current, dict):
            current = {}
        previous_audio_output = self._sanitize_audio_output_id(current.get("audio_output_id"))
        updated = dict(current)
        if cards is not None or card_layout is not None:
            dashboards, active = self._sanitize_dashboards(updated)
            target_id = str(dashboard_id or active)
            for row in dashboards:
                if row["id"] == target_id:
                    if cards is not None:
                        row["cards"] = self._sanitize_cards(cards)
                    if card_layout is not None:
                        row["layout"] = self._sanitize_card_layout(card_layout)
                    break
            updated["dashboards"] = dashboards
            updated["active_dashboard_id"] = target_id if target_id in {row["id"] for row in dashboards} else active
            active_row = next(row for row in dashboards if row["id"] == updated["active_dashboard_id"])
            updated["cards"] = list(active_row["cards"])
        if favorites is not None:
            updated["favorites"] = self._sanitize_favorites(favorites)
        if user_playlists is not None:
            updated["user_playlists"] = self._sanitize_user_playlists(user_playlists)
        if last_media is not None:
            sanitized_media = self._sanitize_last_media(last_media)
            if sanitized_media:
                updated["last_media"] = sanitized_media
        if tv_scale_percent is not None:
            updated["tv_scale_percent"] = max(10, min(150, int(tv_scale_percent)))
        if oled_protection is not None:
            updated["oled_protection"] = bool(oled_protection)
        if animations_enabled is not None:
            updated["animations_enabled"] = bool(animations_enabled)
        if toolbar_auto_hide is not None:
            updated["toolbar_auto_hide"] = bool(toolbar_auto_hide)
        if light_feedback_enabled is not None:
            updated["light_feedback_enabled"] = bool(light_feedback_enabled)
        if tts_announcements_enabled is not None:
            updated["tts_announcements_enabled"] = bool(tts_announcements_enabled)
        if audio_output_id is not None:
            updated["audio_output_id"] = self._sanitize_audio_output_id(audio_output_id)
        if music_adapters is not None:
            updated["music_adapters"] = self._sanitize_music_adapters(music_adapters)
        if music_adapter_options is not None:
            updated["music_adapter_options"] = self._sanitize_music_adapter_options(music_adapter_options)
        if music_search_limit is not None:
            updated["music_search_limit"] = clamp_search_limit(music_search_limit)
        if music_search_adapters is not None:
            updated["music_search_adapters"] = self._sanitize_music_adapters(music_search_adapters)
        if music_search_scopes is not None:
            updated["music_search_scopes"] = self._sanitize_music_search_scopes(music_search_scopes)
        if music_search_types is not None:
            updated["music_search_types"] = self._sanitize_music_search_types(music_search_types)
        self._data["profiles"][profile_entry_id] = updated
        await self._async_save_data()
        next_audio_output = self._sanitize_audio_output_id(updated.get("audio_output_id"))
        if (
            audio_output_id is not None
            and previous_audio_output.startswith("media_player.")
            and previous_audio_output != next_audio_output
            and self._audio_owner.get(profile_entry_id) == f"ha:{previous_audio_output}"
            and self.hass.services.has_service("media_player", "media_stop")
        ):
            try:
                await async_call_service(
                    self.hass,
                    "media_player", "media_stop", {},
                    target={"entity_id": previous_audio_output}, blocking=True,
                    timeout=15.0,
                )
            except Exception:
                pass
            self._audio_owner.pop(profile_entry_id, None)
        return await self.async_preferences(profile_entry_id)

    async def async_remove_profile_preferences(self, profile_entry_id: str) -> None:
        """Remove all Fitness TV state owned by one deleted backend profile."""
        await self.async_load()
        profile_entry_id = str(profile_entry_id)
        self._data.get("profiles", {}).pop(profile_entry_id, None)
        self._clients.pop(profile_entry_id, None)
        self._media_state.pop(profile_entry_id, None)
        self._expected_cast.pop(profile_entry_id, None)
        self._cast_generation.pop(profile_entry_id, None)
        self._expected_cast_generation.pop(profile_entry_id, None)
        self._expected_local_cast.pop(profile_entry_id, None)
        self._local_cast_established_at.pop(profile_entry_id, None)
        self._local_cast_accept_after.pop(profile_entry_id, None)
        self._ignored_cast_clients.pop(profile_entry_id, None)
        self._cast_established_at.pop(profile_entry_id, None)
        self._cast_accept_after.pop(profile_entry_id, None)
        watchdog = self._cast_watchdogs.pop(profile_entry_id, None)
        if watchdog is not None and not watchdog.done():
            watchdog.cancel()
        unsub = self._cast_target_unsubs.pop(profile_entry_id, None)
        if unsub is not None:
            try:
                unsub()
            except Exception:
                pass
        self._audio_owner.pop(profile_entry_id, None)
        await self._async_save_data()

    def heartbeat(self, profile_entry_id: str, client_id: str, *, is_cast_receiver: bool = False) -> None:
        profile_entry_id = str(profile_entry_id or "")[:128]
        client_id = str(client_id or "")[:240]
        if not profile_entry_id or not client_id:
            return
        now = time.monotonic()
        clients = self._clients.setdefault(profile_entry_id, {})
        clients[client_id] = {
            "last_seen": now,
            "is_cast_receiver": bool(is_cast_receiver),
        }
        if len(clients) > TV_CLIENTS_PER_PROFILE_LIMIT:
            for stale_id, _metadata in sorted(
                clients.items(), key=lambda item: float(item[1].get("last_seen") or 0)
            )[: len(clients) - TV_CLIENTS_PER_PROFILE_LIMIT]:
                clients.pop(stale_id, None)
        self._prune(now)

        # A newly-created receiver after expect_cast() is the only Cast client
        # allowed to take ownership. Existing background receiver IDs remain
        # ignored for this launch.
        if is_cast_receiver and profile_entry_id in self._expected_cast:
            ignored = self._ignored_cast_clients.get(profile_entry_id, set())
            if client_id in ignored:
                # Cast/Android TV may reuse the same browser window and therefore
                # the same client_id after quit_app -> show_lovelace_view. Once
                # the new launch is armed and HA reports the Lovelace app again,
                # that reused client is fresh and must be allowed to reclaim audio.
                armed_at = self._cast_accept_after.get(profile_entry_id)
                if armed_at is None or now < armed_at:
                    return
                ignored.discard(client_id)
                if not ignored:
                    self._ignored_cast_clients.pop(profile_entry_id, None)
            self._cast_established_at.setdefault(profile_entry_id, now)
            owner = self._audio_owner.get(profile_entry_id)
            owner_meta = clients.get(owner) if owner else None
            owner_is_live_cast = bool(
                owner
                and owner != client_id
                and owner_meta
                and bool(owner_meta.get("is_cast_receiver"))
                and owner not in self._ignored_cast_clients.get(profile_entry_id, set())
                and now - float(owner_meta.get("last_seen", 0.0)) <= CAST_CLIENT_STALE_SECONDS
            )
            # Keep one audible Cast receiver sticky. Multiple receiver/browser
            # instances can coexist briefly while Google/Android TV replaces a
            # Lovelace WebView. A later heartbeat must not steal ownership and
            # stop the receiver that already has the active radio/audio stream.
            if not owner_is_live_cast:
                self._claim_audio_owner(profile_entry_id, client_id)
            self._ensure_cast_watchdog(profile_entry_id)
        elif is_cast_receiver and profile_entry_id in self._expected_local_cast:
            # Browser-local Cast has no HA media_player state to reconcile. The
            # sender explicitly arms the handoff immediately before loading the
            # Fitness view; the next receiver heartbeat becomes authoritative.
            ignored = self._ignored_cast_clients.get(profile_entry_id, set())
            if client_id in ignored:
                armed_at = self._local_cast_accept_after.get(profile_entry_id)
                if armed_at is None or now < armed_at:
                    return
                ignored.discard(client_id)
                if not ignored:
                    self._ignored_cast_clients.pop(profile_entry_id, None)
            self._local_cast_established_at.setdefault(profile_entry_id, now)
            owner = self._audio_owner.get(profile_entry_id)
            owner_meta = clients.get(owner) if owner else None
            owner_is_live_cast = bool(
                owner
                and owner != client_id
                and owner_meta
                and bool(owner_meta.get("is_cast_receiver"))
                and owner not in self._ignored_cast_clients.get(profile_entry_id, set())
                and now - float(owner_meta.get("last_seen", 0.0)) <= CAST_CLIENT_STALE_SECONDS
            )
            if not owner_is_live_cast:
                self._claim_audio_owner(profile_entry_id, client_id)

    def _prune(self, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        cutoff = current - 30.0
        for profile_id in list(self._clients):
            clients = self._clients[profile_id]
            for client_id in list(clients):
                meta = clients.get(client_id) or {}
                if float(meta.get("last_seen", 0.0)) < cutoff:
                    clients.pop(client_id, None)
            owner = self._audio_owner.get(profile_id)
            if owner and not str(owner).startswith("ha:") and owner not in clients:
                self._audio_owner.pop(profile_id, None)
            ignored = self._ignored_cast_clients.get(profile_id)
            if ignored is not None:
                ignored.intersection_update(clients)
                if not ignored:
                    self._ignored_cast_clients.pop(profile_id, None)
            if not clients:
                self._clients.pop(profile_id, None)

    def _cast_target_state_ok(self, profile_entry_id: str) -> bool:
        target = self.cast_target(profile_entry_id)
        if not target:
            return False
        state = self.hass.states.get(target)
        if state is None or state.state in {"off", "standby", "unknown", "unavailable"}:
            return False
        return str(state.attributes.get("app_id") or "") == CAST_APP_ID_HOMEASSISTANT_LOVELACE

    def is_local_cast_active(self, profile_entry_id: str) -> bool:
        """Return True while a browser-local Cast receiver is alive for the profile."""
        self._prune()
        if profile_entry_id not in self._expected_local_cast:
            return False
        if profile_entry_id not in self._local_cast_established_at:
            return False
        client_id = self.active_cast_client(profile_entry_id)
        if client_id is None:
            return False
        meta = (self._clients.get(profile_entry_id) or {}).get(client_id) or {}
        return (
            time.monotonic() - float(meta.get("last_seen", 0.0))
            <= CAST_CLIENT_STALE_SECONDS
        )

    def is_any_cast_active(self, profile_entry_id: str) -> bool:
        """Return whether either server-side or browser-local Fitness Cast is active."""
        return self.is_local_cast_active(profile_entry_id) or self.is_cast_active(profile_entry_id)

    def has_cast_expectation(self, profile_entry_id: str) -> bool:
        """Return whether media must be routed only to a Cast receiver."""
        return (
            profile_entry_id in self._expected_cast
            or profile_entry_id in self._expected_local_cast
        )

    def _cast_receiver_heartbeat_alive(self, profile_entry_id: str) -> bool:
        """Return whether a real Fitness Cast browser is still heartbeating."""
        self._prune()
        if profile_entry_id not in self._cast_established_at:
            return False
        client_id = self.active_cast_client(profile_entry_id)
        if client_id is None:
            return False
        meta = (self._clients.get(profile_entry_id) or {}).get(client_id) or {}
        return (
            time.monotonic() - float(meta.get("last_seen", 0.0))
            <= CAST_CLIENT_STALE_SECONDS
        )

    def is_cast_active(self, profile_entry_id: str) -> bool:
        """Return True while the actual Fitness Cast browser is alive.

        The receiver heartbeat is authoritative. Cast media_player state/app_id
        can briefly flap while Android/Google TV buffers or changes playback
        state; treating that transient entity state as a disconnect used to
        revoke audio ownership every few seconds.
        """
        return self._cast_receiver_heartbeat_alive(profile_entry_id)

    def _ensure_cast_target_monitor(self, media_player: str) -> None:
        if media_player in self._cast_target_unsubs:
            return

        @callback
        def _target_changed(_event) -> None:
            self.hass.async_create_task(
                self.async_reconcile_cast_target(media_player)
            )

        self._cast_target_unsubs[media_player] = async_track_state_change_event(
            self.hass, [media_player], _target_changed
        )

    def _maybe_remove_cast_target_monitor(self, media_player: str | None) -> None:
        target = str(media_player or "")
        if not target or target in self._expected_cast.values():
            return
        unsub = self._cast_target_unsubs.pop(target, None)
        if unsub is not None:
            unsub()

    def _cancel_cast_watchdog(self, profile_entry_id: str) -> None:
        task = self._cast_watchdogs.pop(profile_entry_id, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    def _ensure_cast_watchdog(self, profile_entry_id: str) -> None:
        task = self._cast_watchdogs.get(profile_entry_id)
        if task is not None and not task.done():
            return

        async def _watch() -> None:
            try:
                while self.cast_target(profile_entry_id):
                    await asyncio.sleep(8.0)
                    if profile_entry_id not in self._cast_established_at:
                        continue
                    if not self.is_cast_active(profile_entry_id):
                        await self.async_mark_cast_inactive(
                            profile_entry_id, reason="cast_receiver_lost"
                        )
                        return
            except asyncio.CancelledError:
                return
            finally:
                if self._cast_watchdogs.get(profile_entry_id) is asyncio.current_task():
                    self._cast_watchdogs.pop(profile_entry_id, None)

        self._cast_watchdogs[profile_entry_id] = self.hass.async_create_task(_watch())

    async def async_reconcile_cast_target(self, media_player: str) -> None:
        """Drop logical Cast sessions when HA says the target/app is no longer alive."""
        now = time.monotonic()
        for profile_entry_id, target in tuple(self._expected_cast.items()):
            if target != media_player or profile_entry_id not in self._cast_established_at:
                continue
            established_at = self._cast_established_at.get(profile_entry_id, now)
            if now - established_at < CAST_STATE_GRACE_SECONDS:
                continue
            if (
                not self._cast_target_state_ok(profile_entry_id)
                and not self._cast_receiver_heartbeat_alive(profile_entry_id)
            ):
                await self.async_mark_cast_inactive(
                    profile_entry_id, reason="cast_target_inactive"
                )

    async def async_reconcile_profile(self, profile_entry_id: str) -> None:
        target = self.cast_target(profile_entry_id)
        if not target or profile_entry_id not in self._cast_established_at:
            return
        established_at = self._cast_established_at.get(profile_entry_id, time.monotonic())
        if time.monotonic() - established_at < CAST_STATE_GRACE_SECONDS:
            return
        if not self.is_cast_active(profile_entry_id):
            await self.async_mark_cast_inactive(
                profile_entry_id, reason="cast_receiver_lost"
            )

    async def async_mark_cast_inactive(
        self,
        profile_entry_id: str,
        *,
        reason: str,
        media_player: str | None = None,
        generation: int | None = None,
    ) -> None:
        """Clear stale Cast ownership without touching a newer launch attempt."""
        target = self.cast_target(profile_entry_id)
        if not target:
            return
        bound_target = str(media_player or target)
        bound_generation = (
            int(generation)
            if generation is not None
            else self._expected_cast_generation.get(profile_entry_id)
        )
        if not self.cast_attempt_is_current(
            profile_entry_id, bound_target, bound_generation
        ):
            return
        # Cast teardown removes the receiver/audio owner before its final browser
        # pause can be accepted. Persist the latest shared progress first so Stop
        # Cast resumes from the same song position on the controller. Persistence
        # may await storage I/O, so re-check ownership afterwards before any
        # destructive receiver/client cleanup.
        await self.async_persist_media_state(profile_entry_id)
        if not self.cast_attempt_is_current(
            profile_entry_id, bound_target, bound_generation
        ):
            return
        target = bound_target
        clients = self._clients.get(profile_entry_id) or {}
        cast_clients = {
            client_id
            for client_id, meta in clients.items()
            if bool((meta or {}).get("is_cast_receiver"))
        }
        for client_id in cast_clients:
            self.hass.bus.async_fire(
                TV_MEDIA_EVENT,
                {
                    "profile_entry_id": profile_entry_id,
                    "client_id": client_id,
                    "command": "stop",
                    "data": {"reason": reason},
                },
            )
        self._ignored_cast_clients.setdefault(profile_entry_id, set()).update(cast_clients)
        if self._audio_owner.get(profile_entry_id) in cast_clients:
            self._audio_owner.pop(profile_entry_id, None)
        for announcement_id, (client_id, future) in tuple(self._announcements.items()):
            if client_id in cast_clients and not future.done():
                future.set_result(False)
        self.clear_expected_cast(
            profile_entry_id, target, generation=bound_generation
        )
        await self.async_broadcast_media_state(
            profile_entry_id, {"playing": False, "error": False}
        )

    async def async_wait_cast_active(
        self,
        profile_entry_id: str,
        *,
        timeout: float = 8.0,
        media_player: str | None = None,
        generation: int | None = None,
    ) -> str | None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, timeout)
        while loop.time() < deadline:
            if media_player is not None and not self.cast_attempt_is_current(
                profile_entry_id, media_player, generation
            ):
                return None
            if self.is_any_cast_active(profile_entry_id):
                client_id = self.active_cast_client(profile_entry_id)
                if client_id is not None:
                    if media_player is not None and not self.cast_attempt_is_current(
                        profile_entry_id, media_player, generation
                    ):
                        return None
                    return self._claim_audio_owner(profile_entry_id, client_id)
            await asyncio.sleep(0.2)
        return None

    def _claim_audio_owner(self, profile_entry_id: str, client_id: str) -> str:
        previous = self._audio_owner.get(profile_entry_id)
        self._audio_owner[profile_entry_id] = client_id
        if previous != client_id:
            # Stop every other still-live browser without allowing its stale
            # state to overwrite the new owner's shared media state.
            for other_id in (self._clients.get(profile_entry_id) or {}):
                if other_id == client_id:
                    continue
                self.hass.bus.async_fire(
                    TV_MEDIA_EVENT,
                    {
                        "profile_entry_id": profile_entry_id,
                        "client_id": other_id,
                        "command": "stop",
                        "data": {"reason": "session_replaced"},
                    },
                )
        return client_id

    def is_audio_owner(self, profile_entry_id: str, client_id: str) -> bool:
        self._prune()
        return self._audio_owner.get(profile_entry_id) == client_id

    def cast_target(self, profile_entry_id: str) -> str | None:
        """Return the Cast target currently bound to this Fitness profile."""
        target = str(self._expected_cast.get(profile_entry_id) or "").strip()
        return target or None

    def broadcast_settings(self, profile_entry_id: str, settings: dict[str, Any]) -> None:
        """Push TV-profile setting changes to all live dashboard clients."""
        self.hass.bus.async_fire(
            TV_SETTINGS_EVENT,
            {"profile_entry_id": profile_entry_id, **dict(settings)},
        )

    def arm_cast_receiver(self, profile_entry_id: str) -> None:
        """Allow the next fresh receiver heartbeat to represent the Cast launch."""
        if profile_entry_id in self._expected_cast:
            self._cast_accept_after[profile_entry_id] = time.monotonic() + 0.35

    def expect_local_cast(self, profile_entry_id: str, source_client_id: str) -> None:
        """Hand audible ownership from the initiating browser to local Cast."""
        if profile_entry_id in self._expected_cast:
            self.clear_expected_cast(profile_entry_id)
        self._expected_local_cast[profile_entry_id] = str(source_client_id or "")
        self._local_cast_established_at.pop(profile_entry_id, None)
        # A short barrier lets a reused Cast browser id distinguish the fresh
        # show_lovelace_view launch from an old background receiver heartbeat.
        self._local_cast_accept_after[profile_entry_id] = time.monotonic() + 0.35
        clients = self._clients.get(profile_entry_id) or {}
        self._audio_owner.pop(profile_entry_id, None)
        for client_id in tuple(clients):
            self.hass.bus.async_fire(
                TV_MEDIA_EVENT,
                {
                    "profile_entry_id": profile_entry_id,
                    "client_id": client_id,
                    "command": "stop",
                    "data": {"reason": "cast_handoff"},
                },
            )
        self._ignored_cast_clients[profile_entry_id] = {
            client_id
            for client_id, meta in clients.items()
            if bool((meta or {}).get("is_cast_receiver"))
        }

    def clear_expected_local_cast(self, profile_entry_id: str) -> None:
        """Clear browser-local Cast routing without touching server Cast state."""
        self._expected_local_cast.pop(profile_entry_id, None)
        self._local_cast_established_at.pop(profile_entry_id, None)
        self._local_cast_accept_after.pop(profile_entry_id, None)
        clients = self._clients.get(profile_entry_id) or {}
        owner = self._audio_owner.get(profile_entry_id)
        if owner and bool((clients.get(owner) or {}).get("is_cast_receiver")):
            self._audio_owner.pop(profile_entry_id, None)
            self._ignored_cast_clients.setdefault(profile_entry_id, set()).add(owner)

    async def async_mark_local_cast_inactive(
        self, profile_entry_id: str, *, reason: str
    ) -> None:
        """Stop a browser-local Cast receiver and return the profile to controller mode."""
        await self.async_persist_media_state(profile_entry_id)
        clients = self._clients.get(profile_entry_id) or {}
        cast_clients = {
            client_id
            for client_id, meta in clients.items()
            if bool((meta or {}).get("is_cast_receiver"))
        }
        for client_id in cast_clients:
            self.hass.bus.async_fire(
                TV_MEDIA_EVENT,
                {
                    "profile_entry_id": profile_entry_id,
                    "client_id": client_id,
                    "command": "stop",
                    "data": {"reason": reason},
                },
            )
        self._ignored_cast_clients.setdefault(profile_entry_id, set()).update(cast_clients)
        if self._audio_owner.get(profile_entry_id) in cast_clients:
            self._audio_owner.pop(profile_entry_id, None)
        self.clear_expected_local_cast(profile_entry_id)
        await self.async_broadcast_media_state(
            profile_entry_id, {"playing": False, "error": False}
        )

    def expect_cast(self, profile_entry_id: str, media_player: str) -> int:
        """Bind a new server Cast attempt and return its launch generation."""
        if profile_entry_id in self._expected_local_cast:
            self.clear_expected_local_cast(profile_entry_id)
        media_player = str(media_player)
        previous_target = self._expected_cast.get(profile_entry_id)
        if previous_target and previous_target != media_player:
            self.clear_expected_cast(profile_entry_id, previous_target)
        generation = int(self._cast_generation.get(profile_entry_id, 0)) + 1
        self._cast_generation[profile_entry_id] = generation
        self._expected_cast_generation[profile_entry_id] = generation
        self._expected_cast[profile_entry_id] = media_player
        self._cast_established_at.pop(profile_entry_id, None)
        self._cast_accept_after.pop(profile_entry_id, None)
        self._cancel_cast_watchdog(profile_entry_id)
        self._ensure_cast_target_monitor(media_player)
        clients = self._clients.get(profile_entry_id) or {}
        # Stop every existing browser audio element before the Cast receiver is
        # restarted. Keep the shared media state marked playing so the fresh TV
        # browser can resume exactly one copy of the selected station.
        self._audio_owner.pop(profile_entry_id, None)
        for client_id in tuple(clients):
            self.hass.bus.async_fire(
                TV_MEDIA_EVENT,
                {
                    "profile_entry_id": profile_entry_id,
                    "client_id": client_id,
                    "command": "stop",
                    "data": {"reason": "cast_handoff"},
                },
            )
        self._ignored_cast_clients[profile_entry_id] = {
            client_id
            for client_id, meta in clients.items()
            if bool((meta or {}).get("is_cast_receiver"))
        }
        owner = self._audio_owner.get(profile_entry_id)
        if owner in self._ignored_cast_clients.get(profile_entry_id, set()):
            self._audio_owner.pop(profile_entry_id, None)
        return generation

    def cast_attempt_is_current(
        self,
        profile_entry_id: str,
        media_player: str,
        generation: int | None = None,
    ) -> bool:
        """Return whether target/generation still owns this profile's launch."""
        if str(self._expected_cast.get(profile_entry_id) or "") != str(media_player):
            return False
        if generation is None:
            return True
        return self._expected_cast_generation.get(profile_entry_id) == int(generation)

    def clear_expected_cast(
        self,
        profile_entry_id: str,
        media_player: str | None = None,
        generation: int | None = None,
    ) -> None:
        current = self._expected_cast.get(profile_entry_id)
        if media_player is not None and current != str(media_player):
            return
        if generation is not None and self._expected_cast_generation.get(profile_entry_id) != int(generation):
            return
        if media_player is None or current == str(media_player):
            self._expected_cast.pop(profile_entry_id, None)
            self._expected_cast_generation.pop(profile_entry_id, None)
            self._cast_established_at.pop(profile_entry_id, None)
            self._cast_accept_after.pop(profile_entry_id, None)
            self._cancel_cast_watchdog(profile_entry_id)
            clients = self._clients.get(profile_entry_id) or {}
            owner = self._audio_owner.get(profile_entry_id)
            if owner and bool((clients.get(owner) or {}).get("is_cast_receiver")):
                self._audio_owner.pop(profile_entry_id, None)
                self._ignored_cast_clients.setdefault(profile_entry_id, set()).add(owner)
            # Keep pre-existing receiver IDs ignored until they naturally go
            # stale. Otherwise a background Cast page can become audible again
            # as soon as the fresh receiver is established.
            self._maybe_remove_cast_target_monitor(current)

    def active_cast_client(self, profile_entry_id: str) -> str | None:
        self._prune()
        clients = self._clients.get(profile_entry_id) or {}
        owner = self._audio_owner.get(profile_entry_id)
        if owner and bool((clients.get(owner) or {}).get("is_cast_receiver")):
            return owner
        ignored = self._ignored_cast_clients.get(profile_entry_id, set())
        cast_clients = {
            client_id: meta
            for client_id, meta in clients.items()
            if bool((meta or {}).get("is_cast_receiver")) and client_id not in ignored
        }
        if not cast_clients:
            return None
        return max(
            cast_clients,
            key=lambda client_id: float(
                (cast_clients.get(client_id) or {}).get("last_seen", 0.0)
            ),
        )

    def active_client(self, profile_entry_id: str) -> str | None:
        self._prune()
        clients = self._clients.get(profile_entry_id) or {}
        owner = self._audio_owner.get(profile_entry_id)
        if owner in clients:
            return owner
        cast_client = self.active_cast_client(profile_entry_id)
        if cast_client is not None:
            return cast_client
        if not clients:
            return None
        return max(
            clients,
            key=lambda client_id: float(
                (clients.get(client_id) or {}).get("last_seen", 0.0)
            ),
        )

    def is_active(self, profile_entry_id: str) -> bool:
        return self.active_client(profile_entry_id) is not None

    async def async_wait_active(
        self,
        profile_entry_id: str,
        *,
        timeout: float = 8.0,
    ) -> str | None:
        expect_cast = self.has_cast_expectation(profile_entry_id)
        candidate = (
            self.active_cast_client(profile_entry_id)
            if expect_cast
            else self.active_client(profile_entry_id)
        )
        if candidate is not None:
            return self._claim_audio_owner(profile_entry_id, candidate)

        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, timeout)
        while loop.time() < deadline:
            await asyncio.sleep(0.2)
            candidate = (
                self.active_cast_client(profile_entry_id)
                if expect_cast
                else self.active_client(profile_entry_id)
            )
            if candidate is not None:
                return self._claim_audio_owner(profile_entry_id, candidate)

        # Never fall back to the laptop while a Cast launch/session is expected.
        # Doing so can create phantom playback when the TV is powered off or the
        # receiver has died but a stale Cast entity still reports the HA app_id.
        if expect_cast:
            return None
        candidate = self.active_client(profile_entry_id)
        return (
            self._claim_audio_owner(profile_entry_id, candidate)
            if candidate is not None
            else None
        )

    @staticmethod
    def _media_seconds(value: Any) -> float:
        try:
            number = float(value or 0)
        except (TypeError, ValueError):
            return 0.0
        if number < 0 or number != number or number == float("inf"):
            return 0.0
        return number

    def media_state(self, profile_entry_id: str) -> dict[str, Any]:
        state = self._media_state.get(profile_entry_id) or {}
        media_content_id = str(state.get("media_content_id") or "").strip()
        # No selection means there is nothing that can truthfully be playing or
        # failing. Keep this invariant server-side so every laptop/TV sees the
        # same state even if an HTMLAudioElement emitted a teardown error.
        if not media_content_id:
            return {
                "title": "",
                "artist": "",
                "album": "",
                "year": "",
                "thumbnail": "",
                "details": "",
                "provider": "",
                "provider_name": "",
                "provider_origin": "",
                "playlist_context": {},
                "media_content_id": "",
                "playing": False,
                "error": False,
                "position": 0.0,
                "duration": 0.0,
            }
        duration = self._media_seconds(state.get("duration"))
        position = self._media_seconds(state.get("position"))
        if duration > 0:
            position = min(position, duration)
        return {
            "title": str(state.get("title") or ""),
            "artist": str(state.get("artist") or ""),
            "album": str(state.get("album") or ""),
            "year": str(state.get("year") or ""),
            "thumbnail": str(state.get("thumbnail") or ""),
            "details": str(state.get("details") or ""),
            "provider": str(state.get("provider") or ""),
            "provider_name": str(state.get("provider_name") or ""),
            "provider_origin": str(state.get("provider_origin") or ""),
            "playlist_context": self._sanitize_playlist_context(
                state.get("playlist_context")
            ),
            "media_content_id": media_content_id,
            "playing": bool(state.get("playing")),
            "error": bool(state.get("error")),
            "position": position,
            "duration": duration,
        }

    def set_media_state(
        self,
        profile_entry_id: str,
        *,
        title: str | None = None,
        artist: str | None = None,
        album: str | None = None,
        year: str | int | None = None,
        thumbnail: str | None = None,
        details: str | None = None,
        provider: str | None = None,
        provider_name: str | None = None,
        provider_origin: str | None = None,
        playlist_context: dict[str, Any] | None = None,
        media_content_id: str | None = None,
        playing: bool | None = None,
        error: bool | None = None,
        position: float | int | None = None,
        duration: float | int | None = None,
    ) -> dict[str, Any]:
        current = self.media_state(profile_entry_id)
        if media_content_id is not None:
            next_id = str(media_content_id)
            if next_id != str(current.get("media_content_id") or ""):
                current.update({
                    "artist": "",
                    "album": "",
                    "year": "",
                    "thumbnail": "",
                    "details": "",
                    "provider": "",
                    "provider_name": "",
                    "provider_origin": "",
                    "playlist_context": {},
                    "position": 0.0,
                    "duration": 0.0,
                })
            current["media_content_id"] = next_id
        if title is not None:
            current["title"] = str(title)
        if artist is not None:
            current["artist"] = str(artist)
        if album is not None:
            current["album"] = str(album)
        if year is not None:
            current["year"] = str(year)
        if thumbnail is not None:
            current["thumbnail"] = str(thumbnail)
        if details is not None:
            current["details"] = str(details)
        if provider is not None:
            current["provider"] = str(provider)
        if provider_name is not None:
            current["provider_name"] = str(provider_name)
        if provider_origin is not None:
            current["provider_origin"] = str(provider_origin)
        if playlist_context is not None:
            current["playlist_context"] = self._sanitize_playlist_context(
                playlist_context
            )
        if playing is not None:
            current["playing"] = bool(playing)
        if error is not None:
            current["error"] = bool(error)
        if position is not None:
            current["position"] = self._media_seconds(position)
        if duration is not None:
            current["duration"] = self._media_seconds(duration)
        if current.get("duration", 0) > 0:
            current["position"] = min(current.get("position", 0), current["duration"])
        if not str(current.get("media_content_id") or "").strip():
            current.update(
                {
                    "title": "",
                    "artist": "",
                    "album": "",
                    "year": "",
                    "thumbnail": "",
                    "details": "",
                    "provider": "",
                    "provider_name": "",
                    "provider_origin": "",
                    "playlist_context": {},
                    "media_content_id": "",
                    "playing": False,
                    "error": False,
                    "position": 0.0,
                    "duration": 0.0,
                }
            )
        self._media_state[profile_entry_id] = current
        return current

    async def async_persist_media_state(self, profile_entry_id: str) -> dict[str, Any]:
        """Persist the latest in-memory resume point without changing playback."""
        state = self.media_state(profile_entry_id)
        if str(state.get("media_content_id") or "").strip():
            await self.async_set_preferences(profile_entry_id, last_media=state)
        return state

    async def async_restore_last_media(self, profile_entry_id: str) -> dict[str, Any]:
        """Restore the persistent last selection without claiming it is playing."""
        await self.async_load()
        current = self.media_state(profile_entry_id)
        if str(current.get("media_content_id") or "").strip():
            return current
        prefs = await self.async_preferences(profile_entry_id)
        last_media = self._sanitize_last_media(prefs.get("last_media"))
        if not last_media:
            return current
        await self.async_broadcast_media_state(
            profile_entry_id,
            {**last_media, "playing": False, "error": False},
        )
        return self.media_state(profile_entry_id)

    async def async_play_last_media(
        self, profile_entry_id: str, *, timeout: float = 10.0
    ) -> dict[str, Any]:
        """Play the profile's last selected media on the live TV receiver."""
        state = await self.async_restore_last_media(profile_entry_id)
        media_content_id = str(state.get("media_content_id") or "").strip()
        if not media_content_id:
            return {"available": False, "sent": False, "playing": False, "error": False}
        # During a Cast handoff an already-playing session stays marked playing
        # so the fresh receiver can resume it immediately from its first heartbeat.
        # Do not then force a second fresh-resolve Play, which would tear down the
        # just-started source and cause a play -> gap -> play cycle.
        if state.get("playing") and self.is_any_cast_active(profile_entry_id):
            return {
                "available": True,
                "sent": False,
                "playing": True,
                "error": bool(state.get("error")),
                "reason": "already_playing_on_cast",
            }
        # Clear a previous browser error before retrying. The receiver resolves
        # media_source IDs again so expiring stream URLs are never reused.
        replay_metadata = {
            key: state.get(key)
            for key in (
                "artist",
                "album",
                "year",
                "thumbnail",
                "details",
                "provider",
                "provider_name",
                "provider_origin",
                "playlist_context",
                "position",
                "duration",
            )
        }
        await self.async_broadcast_media_state(
            profile_entry_id,
            {
                **replay_metadata,
                "title": str(state.get("title") or media_content_id),
                "media_content_id": media_content_id,
                "playing": False,
                "error": False,
            },
        )
        result = await self.async_dispatch_media_command(
            profile_entry_id,
            command="play",
            data={
                **replay_metadata,
                "media_content_id": media_content_id,
                "title": str(state.get("title") or media_content_id),
                "fresh_resolve": True,
            },
        )
        if not result.get("sent"):
            return {"available": True, "sent": False, "playing": False, "error": False}
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, timeout)
        while loop.time() < deadline:
            current = self.media_state(profile_entry_id)
            if current.get("playing") or current.get("error"):
                return {
                    "available": True,
                    "sent": True,
                    "playing": bool(current.get("playing")),
                    "error": bool(current.get("error")),
                }
            await asyncio.sleep(0.2)
        current = self.media_state(profile_entry_id)
        return {
            "available": True,
            "sent": True,
            "playing": bool(current.get("playing")),
            "error": bool(current.get("error")),
        }

    def _audio_output_platform(self, entity_id: str) -> str:
        entry = er.async_get(self.hass).async_get(str(entity_id or ""))
        return str(entry.platform or "") if entry is not None else ""

    def _ha_output_busy_owner(
        self, output: str, profile_entry_id: str
    ) -> str | None:
        """Return another profile actively owning one physical HA output."""
        owner_token = f"ha:{output}"
        output_state = self.hass.states.get(output)
        output_playing = bool(output_state and output_state.state == "playing")
        for other_profile, owner in tuple(self._audio_owner.items()):
            if other_profile == profile_entry_id or owner != owner_token:
                continue
            other_playing = bool(
                (self._media_state.get(other_profile) or {}).get("playing")
            )
            if output_playing and other_playing:
                return other_profile
            # Paused/ended/stale output ownership must not lock a shared speaker
            # forever. The next profile to start playback becomes its owner.
            self._audio_owner.pop(other_profile, None)
        return None

    @staticmethod
    def _player_supports(state: Any, feature: MediaPlayerEntityFeature) -> bool:
        if state is None:
            return False
        try:
            return bool(int(state.attributes.get("supported_features", 0) or 0) & int(feature))
        except (TypeError, ValueError):
            return False

    def _absolute_audio_url(self, value: str) -> str:
        value = str(value or "").strip()
        if not value or value.startswith(("http://", "https://")):
            return value
        if value.startswith("/"):
            return get_url(self.hass, prefer_external=False).rstrip("/") + value
        return value

    async def _async_play_on_ha_output(
        self, profile_entry_id: str, output: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Play one Fitness selection on a Home Assistant media_player output."""
        state = self.hass.states.get(output)
        if state is None or state.state in {"unavailable", "unknown"}:
            return {"sent": False, "reason": "audio_output_unavailable"}
        media_content_id = str(data.get("media_content_id") or "").strip()
        if not media_content_id:
            return {"sent": False, "reason": "no_media"}
        if self._ha_output_busy_owner(output, profile_entry_id) is not None:
            return {"sent": False, "reason": "audio_output_in_use"}

        platform = self._audio_output_platform(output)
        ma_managed = (
            platform in {"music_assistant", "mass"}
            or bool(state.attributes.get("mass_player_type"))
        )
        playable = media_content_id
        ma_preferred_source = False

        if media_content_id.startswith(FITNESS_MA_PREFIX):
            playable = decode_music_assistant_media_id(media_content_id)
            if not playable or not ma_managed:
                return {"sent": False, "reason": "music_assistant_output_required"}
            ma_preferred_source = True
        elif media_content_id.startswith(
            (FITNESS_RADIO_PREFIX, FITNESS_URL_PREFIX, FITNESS_YTDLP_PREFIX)
        ):
            resolved = await self.async_resolve_fitness_media(
                media_content_id, ytdlp_enabled=True
            )
            if str(resolved.get("kind") or "") != "audio" or not resolved.get("url"):
                return {"sent": False, "reason": "audio_output_source_unsupported"}
            playable = self._absolute_audio_url(str(resolved.get("url") or ""))
            ma_preferred_source = True
        elif media_content_id.startswith(
            (FITNESS_YOUTUBE_PREFIX, FITNESS_SOUNDCLOUD_PREFIX)
        ):
            # These adapters are browser-embed transports. Do not pretend that
            # their page/widget identifier is a directly playable speaker URL.
            return {"sent": False, "reason": "audio_output_source_unsupported"}
        elif media_content_id.startswith(("http://", "https://")):
            ma_preferred_source = True
        elif not media_content_id.startswith("media-source://"):
            # MA accepts provider/library URIs in addition to URLs. Prefer its
            # richer queue/player routing for an MA-managed output, while HA
            # media-source identifiers stay on the standard media_player path.
            ma_preferred_source = True

        try:
            if not self._player_supports(state, MediaPlayerEntityFeature.PLAY_MEDIA):
                return {"sent": False, "reason": "audio_output_cannot_play_media"}
            play_payload: dict[str, Any] = {
                "media_content_id": playable,
                "media_content_type": "music",
            }
            if ma_managed and ma_preferred_source:
                # Targeting the MA-created media_player already routes through
                # Music Assistant. The standard HA action is more portable than
                # depending on an MA-only custom action and still gives MA queue
                # ownership for provider URIs/direct URLs.
                play_payload["enqueue"] = "replace"
            await async_call_service(
                self.hass,
                "media_player",
                "play_media",
                play_payload,
                target={"entity_id": output},
                blocking=True,
                timeout=30.0,
            )
            position = self._media_seconds(data.get("position"))
            if position > 0 and self.hass.services.has_service("media_player", "media_seek"):
                try:
                    await async_call_service(
                        self.hass,
                        "media_player",
                        "media_seek",
                        {"seek_position": position},
                        target={"entity_id": output},
                        blocking=True,
                        timeout=15.0,
                    )
                except Exception:
                    pass
        except Exception:
            return {"sent": False, "reason": "audio_output_play_failed"}

        self._audio_owner[profile_entry_id] = f"ha:{output}"
        await self.async_broadcast_media_state(
            profile_entry_id,
            {
                **data,
                "media_content_id": media_content_id,
                "playing": True,
                "error": False,
                "output_entity_id": output,
            },
        )
        return {
            "sent": True,
            "playing": True,
            "error": False,
            "output_entity_id": output,
        }

    async def _async_control_ha_output(
        self, profile_entry_id: str, output: str, command: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        service = {"pause": "media_pause", "stop": "media_stop", "play": "media_play"}.get(command)
        payload: dict[str, Any] = {}
        if command == "play" and self._ha_output_busy_owner(output, profile_entry_id) is not None:
            return {"sent": False, "reason": "audio_output_in_use"}
        if command == "seek":
            service = "media_seek"
            payload["seek_position"] = self._media_seconds(data.get("position"))
        if not service or not self.hass.services.has_service("media_player", service):
            return {"sent": False, "reason": "audio_output_command_unsupported"}
        try:
            await async_call_service(
                self.hass,
                "media_player",
                service,
                payload,
                target={"entity_id": output},
                blocking=True,
                timeout=20.0,
            )
        except Exception:
            return {"sent": False, "reason": "audio_output_command_failed"}
        patch = {"output_entity_id": output}
        if command in {"pause", "stop"}:
            patch["playing"] = False
            if self._audio_owner.get(profile_entry_id) == f"ha:{output}":
                self._audio_owner.pop(profile_entry_id, None)
        elif command == "play":
            patch["playing"] = True
        elif command == "seek":
            patch["position"] = payload["seek_position"]
        await self.async_broadcast_media_state(profile_entry_id, patch)
        return {"sent": True, "output_entity_id": output}

    async def async_dispatch_media_command(
        self,
        profile_entry_id: str,
        *,
        command: str,
        data: dict[str, Any] | None = None,
        source_client_id: str | None = None,
    ) -> dict[str, Any]:
        self._prune()
        await self.async_reconcile_profile(profile_entry_id)
        prefs = await self.async_preferences(profile_entry_id)
        audio_output = self._sanitize_audio_output_id(prefs.get("audio_output_id"))
        if audio_output.startswith("media_player."):
            command_data = dict(data or {})
            command_data.pop("await_result", None)
            media_content_id = str(command_data.get("media_content_id") or "").strip()
            if str(command) in {"select", "play"} and media_content_id:
                await self.async_set_preferences(profile_entry_id, last_media={
                    "media_content_id": media_content_id,
                    "title": str(command_data.get("title") or media_content_id),
                    "artist": str(command_data.get("artist") or ""),
                    "album": str(command_data.get("album") or ""),
                    "year": str(command_data.get("year") or ""),
                    "thumbnail": str(command_data.get("thumbnail") or ""),
                    "details": str(command_data.get("details") or ""),
                    "provider": str(command_data.get("provider") or ""),
                    "provider_name": str(command_data.get("provider_name") or ""),
                    "provider_origin": str(command_data.get("provider_origin") or ""),
                    "playlist_context": command_data.get("playlist_context") or {},
                    "duration": self._media_seconds(command_data.get("duration")),
                    "position": self._media_seconds(command_data.get("position")),
                })
            clients = self._clients.get(profile_entry_id) or {}
            for other_id in clients:
                self.hass.bus.async_fire(TV_MEDIA_EVENT, {
                    "profile_entry_id": profile_entry_id, "client_id": other_id,
                    "command": "stop", "data": {"reason": "ha_audio_output_selected"},
                })
            if str(command) == "select":
                return await self._async_play_on_ha_output(profile_entry_id, audio_output, command_data)
            if str(command) == "play" and media_content_id:
                return await self._async_play_on_ha_output(profile_entry_id, audio_output, command_data)
            return await self._async_control_ha_output(profile_entry_id, audio_output, str(command), command_data)
        cast_client = (
            self.active_cast_client(profile_entry_id)
            if self.is_any_cast_active(profile_entry_id)
            else None
        )
        clients = self._clients.get(profile_entry_id) or {}
        cast_expected = self.has_cast_expectation(profile_entry_id)
        if cast_client is not None:
            client_id = cast_client
        elif cast_expected:
            # Once a profile is cast-bound, laptop controls must wait only for
            # the Cast browser. Never route the command back to the laptop.
            client_id = await self.async_wait_cast_active(
                profile_entry_id, timeout=4.0
            )
        elif source_client_id and source_client_id in clients:
            client_id = source_client_id
        else:
            client_id = await self.async_wait_active(profile_entry_id, timeout=2.0)
        if client_id is None:
            return {
                "sent": False,
                "reason": "cast_unavailable" if cast_expected else "no_active_client",
            }
        command_data = dict(data or {})
        wait_for_result = bool(command_data.pop("await_result", False))
        media_content_id = ""
        if str(command) in {"select", "play"}:
            media_content_id = str(command_data.get("media_content_id") or "").strip()
            if media_content_id:
                await self.async_set_preferences(
                    profile_entry_id,
                    last_media={
                        "media_content_id": media_content_id,
                        "title": str(command_data.get("title") or media_content_id),
                        "artist": str(command_data.get("artist") or ""),
                        "album": str(command_data.get("album") or ""),
                        "year": str(command_data.get("year") or ""),
                        "thumbnail": str(command_data.get("thumbnail") or ""),
                        "details": str(command_data.get("details") or ""),
                        "provider": str(command_data.get("provider") or ""),
                        "provider_name": str(command_data.get("provider_name") or ""),
                        "provider_origin": str(command_data.get("provider_origin") or ""),
                        "playlist_context": command_data.get("playlist_context") or {},
                        "duration": self._media_seconds(command_data.get("duration")),
                        "position": self._media_seconds(command_data.get("position")),
                    },
                )
                if wait_for_result:
                    await self.async_broadcast_media_state(
                        profile_entry_id,
                        {
                            "media_content_id": media_content_id,
                            "title": str(command_data.get("title") or media_content_id),
                            "artist": str(command_data.get("artist") or ""),
                            "album": str(command_data.get("album") or ""),
                            "year": str(command_data.get("year") or ""),
                            "thumbnail": str(command_data.get("thumbnail") or ""),
                            "details": str(command_data.get("details") or ""),
                            "provider": str(command_data.get("provider") or ""),
                            "provider_name": str(command_data.get("provider_name") or ""),
                            "provider_origin": str(command_data.get("provider_origin") or ""),
                            "playlist_context": command_data.get("playlist_context") or {},
                            "duration": self._media_seconds(command_data.get("duration")),
                            "position": self._media_seconds(command_data.get("position")),
                            "playing": False,
                            "error": False,
                        },
                    )
        # Keep browser playback single-owner even when an old tab/receiver has
        # missed an earlier owner handoff.  New playback and explicit pause/stop
        # both silence every non-owner client so one stale Radio Browser stream
        # cannot remain audible underneath the active player.
        command_name = str(command)
        if command_name in {"select", "play"}:
            for other_id in clients:
                if other_id == client_id:
                    continue
                self.hass.bus.async_fire(
                    TV_MEDIA_EVENT,
                    {
                        "profile_entry_id": profile_entry_id,
                        "client_id": other_id,
                        "command": "stop",
                        "data": {"reason": "new_media_selected"},
                    },
                )
        elif command_name in {"pause", "stop"}:
            for other_id in clients:
                if other_id == client_id:
                    continue
                self.hass.bus.async_fire(
                    TV_MEDIA_EVENT,
                    {
                        "profile_entry_id": profile_entry_id,
                        "client_id": other_id,
                        "command": "stop",
                        "data": {"reason": f"{command_name}_non_owner_cleanup"},
                    },
                )

        self._claim_audio_owner(profile_entry_id, client_id)
        payload = {
            "profile_entry_id": profile_entry_id,
            "client_id": client_id,
            "command": str(command),
            "data": command_data,
        }
        self.hass.bus.async_fire(TV_MEDIA_EVENT, payload)
        if wait_for_result and media_content_id:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 12.0
            while loop.time() < deadline:
                current = self.media_state(profile_entry_id)
                if str(current.get("media_content_id") or "") == media_content_id:
                    if current.get("playing") or current.get("error"):
                        return {
                            "sent": True,
                            "client_id": client_id,
                            "playing": bool(current.get("playing")),
                            "error": bool(current.get("error")),
                            "state": current,
                        }
                await asyncio.sleep(0.1)
            current = self.media_state(profile_entry_id)
            return {
                "sent": True,
                "client_id": client_id,
                "playing": bool(
                    str(current.get("media_content_id") or "") == media_content_id
                    and current.get("playing")
                ),
                "error": bool(
                    str(current.get("media_content_id") or "") == media_content_id
                    and current.get("error")
                ),
                "reason": "playback_timeout",
                "state": current,
            }
        return {"sent": True, "client_id": client_id}

    async def async_broadcast_media_state(self, profile_entry_id: str, state: dict[str, Any]) -> None:
        normalized = self.set_media_state(
            profile_entry_id,
            title=state.get("title"),
            artist=state.get("artist"),
            album=state.get("album"),
            year=state.get("year"),
            thumbnail=state.get("thumbnail"),
            details=state.get("details"),
            provider=state.get("provider"),
            provider_name=state.get("provider_name"),
            provider_origin=state.get("provider_origin"),
            playlist_context=(
                state.get("playlist_context")
                if "playlist_context" in state
                else None
            ),
            media_content_id=state.get("media_content_id"),
            playing=state.get("playing"),
            error=state.get("error"),
            position=state.get("position"),
            duration=state.get("duration"),
        )
        self.hass.bus.async_fire(
            TV_MEDIA_STATE_EVENT,
            {"profile_entry_id": profile_entry_id, **normalized},
        )

    async def _async_radio_browser_json(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        """Fetch one Radio Browser response without requiring its HA integration."""
        session = async_get_clientsession(self.hass)
        url = f"{RADIO_BROWSER_BASE}{path}"
        async with asyncio.timeout(RADIO_BROWSER_TIMEOUT):
            response = await session.get(
                url,
                params=params or {},
                headers={"User-Agent": "HA-Fitness/0.0.0"},
            )
            response.raise_for_status()
            return await response.json(content_type=None)

    @staticmethod
    def _radio_item(raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        station_uuid = str(raw.get("stationuuid") or "").strip()
        name = str(raw.get("name") or "").strip()
        if not station_uuid or not name:
            return None
        details = [
            str(raw.get("country") or "").strip(),
            str(raw.get("codec") or "").strip(),
        ]
        bitrate = raw.get("bitrate")
        try:
            if int(bitrate or 0) > 0:
                details.append(f"{int(bitrate)} kbps")
        except (TypeError, ValueError):
            pass
        return {
            "title": name,
            "artist": "",
            "media_content_id": f"{FITNESS_RADIO_PREFIX}{station_uuid}",
            "can_play": True,
            "can_expand": False,
            "thumbnail": str(raw.get("favicon") or "").strip(),
            "album": "",
            "year": "",
            "duration": 0.0,
            "provider": "radio_browser",
            "provider_name": "Radio Browser",
            "provider_origin": "Radio Browser",
            "details": " · ".join(item for item in details if item),
            "media_class": "radio",
        }

    async def async_music_browse(
        self,
        provider: str,
        *,
        query: str = "",
        country_code: str = "",
        ytdlp_enabled: bool = False,
    ) -> dict[str, Any]:
        """Browse Fitness-native music providers."""
        provider = str(provider or "").strip().lower()
        query = str(query or "").strip()
        country_code = str(country_code or "").strip().upper()[:2]

        if provider != "radio":
            return {"provider": provider, "title": "", "children": []}

        if self._radio_country_codes is None:
            countries_raw = await self._async_radio_browser_json(
                "/json/countrycodes",
                params={"hidebroken": "true", "order": "name"},
            )
            countries: list[dict[str, str]] = []
            seen_codes: set[str] = set()
            for country in countries_raw if isinstance(countries_raw, list) else []:
                if not isinstance(country, dict):
                    continue
                # Radio Browser's /countrycodes endpoint stores the ISO 3166-1
                # alpha-2 code in the `name` field. Friendly localized names are
                # rendered client-side with Intl.DisplayNames.
                code = str(country.get("name") or "").strip().upper()
                if len(code) != 2 or not code.isalpha() or code in seen_codes:
                    continue
                seen_codes.add(code)
                countries.append({"code": code})
            countries.sort(key=lambda item: item["code"] )
            self._radio_country_codes = countries
        countries = list(self._radio_country_codes)

        if len(country_code) != 2 or not country_code.isalpha():
            country_code = ""

        if country_code:
            # Exact country endpoint is documented by Radio Browser. Fetch a
            # generous top slice and apply an optional station-name query here,
            # avoiding undocumented exact-search parameters.
            raw = await self._async_radio_browser_json(
                f"/json/stations/bycountrycodeexact/{country_code}",
                params={
                    "hidebroken": "true",
                    "limit": 1000 if query else 100,
                    "order": "clickcount",
                    "reverse": "true",
                },
            )
            if query and isinstance(raw, list):
                needle = query.casefold()
                raw = [
                    item for item in raw
                    if isinstance(item, dict)
                    and needle in str(item.get("name") or "").casefold()
                ][:100]
            title = query or country_code
        elif query:
            raw = await self._async_radio_browser_json(
                "/json/stations/search",
                params={
                    "hidebroken": "true",
                    "limit": 100,
                    "order": "clickcount",
                    "reverse": "true",
                    "name": query,
                },
            )
            title = query
        else:
            raw = await self._async_radio_browser_json(
                "/json/stations/topclick/100",
                params={"hidebroken": "true"},
            )
            title = "Internet radio"
        children = []
        for item in raw if isinstance(raw, list) else []:
            normalized = self._radio_item(item)
            if normalized is not None:
                children.append(normalized)
        return {
            "provider": "radio",
            "title": title,
            "children": children,
            "can_search": True,
            "countries": countries,
            "country_code": country_code,
        }

    async def async_resolve_fitness_media(
        self, media_content_id: str, *, ytdlp_enabled: bool = False
    ) -> dict[str, Any]:
        """Resolve a Fitness-native ID through its owning adapter module."""
        return await resolve_music_adapter_media(
            self.hass,
            self,
            str(media_content_id or "").strip(),
            ytdlp_enabled=ytdlp_enabled,
        )

    def _music_proxy_url(
        self, target: str, *, headers: dict[str, str] | None = None
    ) -> str:
        """Return an opaque same-origin proxy URL for a remote audio stream."""
        now = time.monotonic()
        self._music_proxy_targets = {
            token: item
            for token, item in self._music_proxy_targets.items()
            if item[1] > now
        }
        while len(self._music_proxy_targets) >= TV_PROXY_TOKEN_LIMIT:
            self._music_proxy_targets.pop(next(iter(self._music_proxy_targets)))
        token = uuid4().hex
        safe_headers: dict[str, str] = {}
        for key, value in (headers or {}).items():
            name = str(key).strip()[:128]
            if name and name.lower() in _SAFE_PROXY_REQUEST_HEADERS:
                safe_headers[name] = str(value)[:4096]
            if len(safe_headers) >= 32:
                break
        self._music_proxy_targets[token] = (
            str(target)[:8192],
            now + MUSIC_PROXY_TTL_SECONDS,
            safe_headers,
        )
        return f"/fitness/music/proxy/{token}"

    def music_proxy_target(
        self, token: str
    ) -> tuple[str, dict[str, str]] | None:
        """Resolve one live proxy token without accepting arbitrary URLs."""
        item = self._music_proxy_targets.get(str(token or ""))
        if item is None:
            return None
        target, expires, headers = item
        if expires <= time.monotonic():
            self._music_proxy_targets.pop(str(token or ""), None)
            return None
        return target, dict(headers)

    def issue_ma_sendspin_proxy(
        self, profile_entry_id: str, ma_entry_id: str, client_id: str
    ) -> str:
        """Issue a short-lived same-origin WebSocket relay ticket for Sendspin."""
        now = time.monotonic()
        self._ma_sendspin_targets = {
            token: item
            for token, item in self._ma_sendspin_targets.items()
            if item[3] > now
        }
        while len(self._ma_sendspin_targets) >= TV_PROXY_TOKEN_LIMIT:
            self._ma_sendspin_targets.pop(next(iter(self._ma_sendspin_targets)))
        token = uuid4().hex + uuid4().hex
        profile_entry_id = str(profile_entry_id)[:128]
        ma_entry_id = str(ma_entry_id)[:128]
        client_id = str(client_id)[:240]
        self._ma_sendspin_targets[token] = (
            profile_entry_id,
            ma_entry_id,
            client_id,
            now + MA_SENDSPIN_PROXY_TTL_SECONDS,
        )
        if client_id:
            players = self._ma_players.setdefault(profile_entry_id, {})
            players[client_id] = ma_entry_id
            while len(players) > TV_MA_PLAYERS_PER_PROFILE_LIMIT:
                players.pop(next(iter(players)))
        return f"/fitness/music/ma/sendspin/{token}"

    def ma_sendspin_target(self, token: str) -> tuple[str, str, str] | None:
        """Resolve a live Sendspin relay ticket without accepting arbitrary URLs."""
        item = self._ma_sendspin_targets.pop(str(token or ""), None)
        if item is None:
            return None
        profile_entry_id, ma_entry_id, client_id, expires = item
        if expires <= time.monotonic():
            return None
        return profile_entry_id, ma_entry_id, client_id

    def remember_ma_player(
        self, profile_entry_id: str, ma_entry_id: str, player_id: str
    ) -> None:
        """Remember one Fitness-owned MA queue so unload can release it."""
        profile_entry_id = str(profile_entry_id or "").strip()
        ma_entry_id = str(ma_entry_id or "").strip()
        player_id = str(player_id or "").strip()
        if profile_entry_id and ma_entry_id and player_id:
            players = self._ma_players.setdefault(profile_entry_id, {})
            players[player_id[:240]] = ma_entry_id[:128]
            while len(players) > TV_MA_PLAYERS_PER_PROFILE_LIMIT:
                players.pop(next(iter(players)))

    def owns_ma_player(
        self, profile_entry_id: str, ma_entry_id: str, player_id: str
    ) -> bool:
        """Return whether this exact profile issued the MA browser player."""
        return (
            bool(player_id)
            and self._ma_players.get(str(profile_entry_id), {}).get(str(player_id))
            == str(ma_entry_id)
        )

    def begin_proxy_stream(self) -> bool:
        if self._active_proxy_streams >= TV_PROXY_CONCURRENCY_LIMIT:
            return False
        self._active_proxy_streams += 1
        return True

    def end_proxy_stream(self) -> None:
        self._active_proxy_streams = max(0, self._active_proxy_streams - 1)

    def begin_sendspin_stream(self) -> bool:
        if self._active_sendspin_streams >= TV_SENDSPIN_CONCURRENCY_LIMIT:
            return False
        self._active_sendspin_streams += 1
        return True

    def end_sendspin_stream(self) -> None:
        self._active_sendspin_streams = max(0, self._active_sendspin_streams - 1)

    def begin_music_search(self, profile_entry_id: str) -> bool:
        profile_entry_id = str(profile_entry_id)
        if (
            profile_entry_id in self._active_music_searches
            or len(self._active_music_searches) >= TV_MUSIC_SEARCH_CONCURRENCY_LIMIT
        ):
            return False
        self._active_music_searches.add(profile_entry_id)
        return True

    def end_music_search(self, profile_entry_id: str) -> None:
        self._active_music_searches.discard(str(profile_entry_id))

    def begin_music_resolution(self, profile_entry_id: str) -> bool:
        profile_entry_id = str(profile_entry_id)
        if (
            profile_entry_id in self._active_music_resolutions
            or len(self._active_music_resolutions) >= TV_MUSIC_SEARCH_CONCURRENCY_LIMIT
        ):
            return False
        self._active_music_resolutions.add(profile_entry_id)
        return True

    def end_music_resolution(self, profile_entry_id: str) -> None:
        self._active_music_resolutions.discard(str(profile_entry_id))

    async def async_release_profile_music(
        self, profile_entry_id: str, *, reason: str = "profile_unload"
    ) -> None:
        """Release Fitness-owned MA queues and make shared playback paused.

        This runs before a Fitness profile unload/reload.  Browser transports can
        vanish instantly during an HA restart; stopping MA server-side first is
        what releases Spotify/provider locks reliably.
        """
        profile_entry_id = str(profile_entry_id or "").strip()
        players = dict(self._ma_players.pop(profile_entry_id, {}))
        state = self.media_state(profile_entry_id)
        # HA/profile reload can destroy browser transports before they get a
        # final pause callback. Persist the in-memory queue position first.
        if str(state.get("media_content_id") or "").strip():
            await self.async_set_preferences(profile_entry_id, last_media=state)
        owner = str(self._audio_owner.get(profile_entry_id) or "").strip()
        if owner.startswith("ha:"):
            output = owner[3:]
            if output.startswith("media_player.") and self.hass.services.has_service(
                "media_player", "media_stop"
            ):
                try:
                    await async_call_service(
                        self.hass,
                        "media_player", "media_stop", {},
                        target={"entity_id": output}, blocking=True,
                        timeout=15.0,
                    )
                except Exception:  # noqa: BLE001 - shutdown cleanup is best effort
                    pass
        elif str(state.get("media_content_id") or "").startswith(FITNESS_MA_PREFIX):
            if owner and owner not in players:
                try:
                    prefs = await self.async_preferences(profile_entry_id)
                    entry = _selected_music_assistant_entry(
                        self.hass, prefs.get("music_adapter_options") or {}
                    )
                    if entry is not None:
                        players[owner] = str(entry.entry_id)
                except Exception:  # noqa: BLE001 - shutdown cleanup is best effort
                    pass
        for player_id, ma_entry_id in players.items():
            entry = self.hass.config_entries.async_get_entry(str(ma_entry_id))
            if entry is None:
                continue
            try:
                async with asyncio.timeout(10.0):
                    await async_stop_music_assistant_player(entry, player_id)
            except Exception:  # noqa: BLE001 - never block HA/profile unload
                pass
        self._audio_owner.pop(profile_entry_id, None)
        if str(state.get("media_content_id") or "").strip():
            await self.async_broadcast_media_state(
                profile_entry_id, {"playing": False, "error": False}
            )

    async def async_speak(
        self,
        profile_entry_id: str,
        *,
        message: str,
        tts_entity: str,
        language: str | None,
        ducking_percent: int,
        wait_for_dashboard: float = 8.0,
        playback_timeout: float = 150.0,
    ) -> bool:
        """Send generated TTS to the active Fitness TV browser and await completion."""
        client_id = await self.async_wait_active(
            profile_entry_id,
            timeout=wait_for_dashboard,
        )
        if client_id is None:
            return False

        # Generate a standard HA TTS media-source ID, but do not send it to the
        # Cast media_player. The dashboard browser resolves and plays it inside
        # the already-running HA Cast app, so the Lovelace view remains loaded.
        from homeassistant.components.tts.media_source import (  # noqa: PLC0415
            generate_media_source_id,
        )

        media_content_id = generate_media_source_id(
            self.hass,
            message=message,
            engine=tts_entity,
            language=language,
            cache=False,
        )
        announcement_id = uuid4().hex
        if len(self._announcements) >= TV_ANNOUNCEMENT_LIMIT:
            return False
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._announcements[announcement_id] = (client_id, future)

        self.hass.bus.async_fire(
            TV_AUDIO_EVENT,
            {
                "profile_entry_id": profile_entry_id,
                "client_id": client_id,
                "announcement_id": announcement_id,
                "media_content_id": media_content_id,
                "ducking_percent": max(0, min(100, int(ducking_percent))),
            },
        )

        try:
            return bool(
                await asyncio.wait_for(future, timeout=max(1.0, playback_timeout))
            )
        except TimeoutError:
            return False
        finally:
            self._announcements.pop(announcement_id, None)

    def acknowledge(
        self,
        announcement_id: str,
        client_id: str,
        success: bool,
    ) -> None:
        pending = self._announcements.get(announcement_id)
        if pending is None:
            return
        expected_client, future = pending
        if expected_client != client_id or future.done():
            return
        future.set_result(bool(success))


def get_tv_dashboard_hub(hass: HomeAssistant) -> FitnessTVDashboardHub:
    """Return the process-wide Fitness TV dashboard hub."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    hub = domain_data.get(TV_HUB_KEY)
    if not isinstance(hub, FitnessTVDashboardHub):
        hub = FitnessTVDashboardHub(hass)
        domain_data[TV_HUB_KEY] = hub
    return hub


class FitnessMusicProxyView(HomeAssistantView):
    """Stream Fitness-native remote audio through the HA origin for Cast."""

    url = "/fitness/music/proxy/{token}"
    name = "api:fitness:music-proxy"
    requires_auth = False
    cors_allowed = True

    async def get(self, request: web.Request, token: str) -> web.StreamResponse:
        """Proxy only opaque URLs previously issued by the Fitness hub."""
        hub = get_tv_dashboard_hub(request.app["hass"])
        proxy_target = hub.music_proxy_target(token)
        if not proxy_target:
            raise web.HTTPNotFound()
        if not hub.begin_proxy_stream():
            raise web.HTTPTooManyRequests(
                text="Too many active Fitness audio streams",
                headers={"Retry-After": "5"},
            )
        target, target_headers = proxy_target
        try:
            headers = {
                "User-Agent": "HA-Fitness/0.0.0",
                "Accept-Encoding": "identity",
                **target_headers,
            }
            if range_header := request.headers.get("Range"):
                if not _RANGE_RE.fullmatch(range_header.strip()):
                    raise web.HTTPBadRequest(text="Invalid byte range")
                headers["Range"] = range_header.strip()
            session = async_get_clientsession(hub.hass)
            upstream = None
            try:
                for _redirect in range(TV_PROXY_REDIRECT_LIMIT + 1):
                    target = await _async_validate_public_http_target(hub.hass, target)
                    upstream = await session.get(
                        target,
                        headers=headers,
                        allow_redirects=False,
                        timeout=ClientTimeout(
                            total=None,
                            connect=MUSIC_PROXY_CONNECT_SECONDS,
                            sock_connect=MUSIC_PROXY_CONNECT_SECONDS,
                            sock_read=MUSIC_PROXY_READ_SECONDS,
                        ),
                    )
                    if upstream.status not in {301, 302, 303, 307, 308}:
                        break
                    location = str(upstream.headers.get("Location") or "").strip()
                    upstream.release()
                    upstream = None
                    if not location or _redirect >= TV_PROXY_REDIRECT_LIMIT:
                        raise ValueError("proxy_redirect_limit")
                    target = urljoin(target, location)
            except web.HTTPException:
                raise
            except Exception as err:  # noqa: BLE001 - remote stream errors map to 502
                if upstream is not None:
                    upstream.release()
                raise web.HTTPBadGateway(text="Unable to open remote audio stream") from err
            if upstream is None or upstream.status not in {200, 206}:
                status = upstream.status if upstream is not None else 502
                if upstream is not None:
                    upstream.release()
                raise web.HTTPBadGateway(text=f"Remote audio returned HTTP {status}")

            response_headers = {"Cache-Control": "no-store"}
            for name in (
                "Content-Type",
                "Content-Length",
                "Content-Range",
                "Accept-Ranges",
                "icy-name",
                "icy-description",
                "icy-br",
            ):
                value = upstream.headers.get(name)
                if value:
                    response_headers[name] = value
            response = web.StreamResponse(status=upstream.status, headers=response_headers)
            await response.prepare(request)
            try:
                async for chunk in upstream.content.iter_chunked(64 * 1024):
                    await response.write(chunk)
            except (ConnectionResetError, asyncio.CancelledError):
                pass
            finally:
                upstream.release()
            try:
                await response.write_eof()
            except ConnectionResetError:
                pass
            return response
        finally:
            hub.end_proxy_stream()


class FitnessMASendspinProxyView(HomeAssistantView):
    """Relay Music Assistant Sendspin through HA without exposing MA credentials."""

    url = "/fitness/music/ma/sendspin/{token}"
    name = "api:fitness:music-assistant-sendspin"
    requires_auth = False
    cors_allowed = True

    async def get(self, request: web.Request, token: str) -> web.StreamResponse:
        """Bound public relay concurrency before opening either WebSocket."""
        hub = get_tv_dashboard_hub(request.app["hass"])
        if not hub.begin_sendspin_stream():
            raise web.HTTPTooManyRequests(
                text="Too many active Fitness music relays",
                headers={"Retry-After": "5"},
            )
        try:
            return await self._get_limited(request, token)
        finally:
            hub.end_sendspin_stream()

    async def _get_limited(self, request: web.Request, token: str) -> web.StreamResponse:
        """Authenticate to MA's browser proxy, then bridge Sendspin frames."""
        hass: HomeAssistant = request.app["hass"]
        hub = get_tv_dashboard_hub(hass)
        target = hub.ma_sendspin_target(token)
        if target is None:
            raise web.HTTPNotFound()
        profile_entry_id, ma_entry_id, client_id = target
        if not _profile_loaded(hass, profile_entry_id):
            raise web.HTTPNotFound()
        entry = hass.config_entries.async_get_entry(ma_entry_id)
        if entry is None:
            raise web.HTTPNotFound()

        # Music Assistant's normal /sendspin endpoint authenticates browser
        # clients and auto-whitelists the supplied client_id for that MA user.
        # The HA Music Assistant integration already stores a long-lived token
        # in the config entry, so Fitness can perform that handshake server-side
        # without ever exposing the credential to JavaScript.
        ma_token = str((getattr(entry, "data", {}) or {}).get("token") or "").strip()
        upstream_url = (
            music_assistant_sendspin_url(entry)
            if ma_token
            else music_assistant_direct_sendspin_url(entry)
        )
        if not upstream_url:
            raise web.HTTPBadGateway(text="Music Assistant Sendspin server URL is unavailable")

        client_ws = web.WebSocketResponse(
            heartbeat=25, max_msg_size=SENDSPIN_MAX_MESSAGE_BYTES
        )
        await client_ws.prepare(request)
        session = async_get_clientsession(hass)
        try:
            async with asyncio.timeout(MUSIC_PROXY_CONNECT_SECONDS):
                upstream_ws = await session.ws_connect(
                    upstream_url,
                    heartbeat=25,
                    max_msg_size=SENDSPIN_MAX_MESSAGE_BYTES,
                )
            if ma_token:
                await upstream_ws.send_json(
                    {"type": "auth", "token": ma_token, "client_id": client_id}
                )
                async with asyncio.timeout(10):
                    auth_reply = await upstream_ws.receive()
                if auth_reply.type != WSMsgType.TEXT:
                    raise RuntimeError("Music Assistant Sendspin authentication failed")
                try:
                    auth_payload = json.loads(auth_reply.data)
                except (TypeError, json.JSONDecodeError) as err:
                    raise RuntimeError(
                        "Music Assistant Sendspin authentication returned invalid data"
                    ) from err
                if auth_payload.get("type") != "auth_ok":
                    raise RuntimeError("Music Assistant Sendspin authentication was rejected")
        except Exception:  # noqa: BLE001 - remote MA errors become clean close
            await client_ws.close(code=1011, message=b"Music Assistant unavailable")
            return client_ws

        async def _client_to_upstream() -> None:
            async for message in client_ws:
                if message.type == WSMsgType.TEXT:
                    await upstream_ws.send_str(message.data)
                elif message.type == WSMsgType.BINARY:
                    await upstream_ws.send_bytes(message.data)
                elif message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR}:
                    break

        async def _upstream_to_client() -> None:
            async for message in upstream_ws:
                if message.type == WSMsgType.TEXT:
                    await client_ws.send_str(message.data)
                elif message.type == WSMsgType.BINARY:
                    await client_ws.send_bytes(message.data)
                elif message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR}:
                    break

        tasks = {
            asyncio.create_task(_client_to_upstream()),
            asyncio.create_task(_upstream_to_client()),
        }
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            try:
                task.result()
            except Exception:  # noqa: BLE001 - peer disconnects simply close relay
                pass
        await upstream_ws.close()
        if not client_ws.closed:
            await client_ws.close()
        return client_ws


def _music_adapter_enabled_for_preferences(prefs: dict[str, Any], adapter_id: str) -> bool:
    """Return whether a profile may use an installed music adapter."""
    if not bool(prefs.get("music_adapters_configured")):
        return True
    return str(adapter_id or "").strip() in {
        str(item).strip() for item in (prefs.get("music_adapters") or []) if str(item).strip()
    }


def _profile_ytdlp_enabled(hass: HomeAssistant, profile_entry_id: str) -> bool:
    """Return whether the profile explicitly opted into yt-dlp playback."""
    entry = hass.config_entries.async_get_entry(profile_entry_id)
    if entry is not None:
        return bool({**entry.data, **entry.options}.get(CONF_TV_YTDLP_ENABLED, False))
    manager = hass.data.get(DOMAIN, {}).get(profile_entry_id)
    config = getattr(manager, "config", {}) if manager is not None else {}
    return bool(config.get(CONF_TV_YTDLP_ENABLED, False)) if isinstance(config, dict) else False


def _profile_loaded(hass: HomeAssistant, profile_entry_id: str) -> bool:
    manager = hass.data.get(DOMAIN, {}).get(profile_entry_id)
    return manager is not None


async def _require_profile_access(
    hass: HomeAssistant, connection, profile_entry_id: str, *, hub=None
):
    """Authorize read/view access to one Fitness profile."""
    tv_hub = hub or get_tv_dashboard_hub(hass)
    await get_fitness_access_controller(hass).async_require_profile(
        connection, profile_entry_id, cast_hub=tv_hub
    )
    return tv_hub


async def _require_profile_control(
    hass: HomeAssistant, connection, profile_entry_id: str, *, hub=None
):
    """Authorize active control/configuration of one Fitness profile."""
    tv_hub = hub or get_tv_dashboard_hub(hass)
    await get_fitness_access_controller(hass).async_require_profile_control(
        connection, profile_entry_id, cast_hub=tv_hub
    )
    return tv_hub


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/preferences",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    }
)
@websocket_api.async_response
async def websocket_tv_preferences(hass: HomeAssistant, connection, msg) -> None:
    """Return persistent card selection for one Fitness profile."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_access(hass, connection, profile_entry_id)
    result = await hub.async_preferences(profile_entry_id)
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/preferences/save",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Optional("cards"): vol.All([str], vol.Length(max=len(TV_CARD_IDS))),
        vol.Optional("dashboard_id"): vol.All(str, vol.Length(max=64)),
        vol.Optional("card_layout"): vol.All(
            dict, bounded_websocket_payload(max_nodes=512, max_depth=4, max_string_length=128)
        ),
        vol.Optional("favorites"): vol.All(
            [dict], vol.Length(max=100),
            bounded_websocket_payload(max_nodes=2_048, max_depth=5, max_string_length=4_096),
        ),
        vol.Optional("user_playlists"): [dict],
        vol.Optional("last_media"): vol.All(
            dict,
            bounded_websocket_payload(max_nodes=256, max_depth=5, max_string_length=4_096),
        ),
        vol.Optional("tv_scale_percent"): vol.All(vol.Coerce(int), vol.Range(min=10, max=150)),
        vol.Optional("oled_protection"): bool,
        vol.Optional("animations_enabled"): bool,
        vol.Optional("toolbar_auto_hide"): bool,
        vol.Optional("light_feedback_enabled"): bool,
        vol.Optional("tts_announcements_enabled"): bool,
        vol.Optional("audio_output_id"): str,
        vol.Optional("music_adapters"): vol.All([str], vol.Length(max=32)),
        vol.Optional("music_adapter_options"): vol.All(
            dict,
            bounded_websocket_payload(max_nodes=512, max_depth=5, max_string_length=2_048),
        ),
        vol.Optional("music_search_limit"): vol.All(vol.Coerce(int), vol.Range(min=MIN_MUSIC_SEARCH_LIMIT, max=MAX_MUSIC_SEARCH_LIMIT)),
        vol.Optional("music_search_adapters"): vol.All([str], vol.Length(max=32)),
        vol.Optional("music_search_scopes"): vol.All(
            dict,
            bounded_websocket_payload(max_nodes=512, max_depth=4, max_string_length=256),
        ),
        vol.Optional("music_search_types"): [str],
    }
)
@websocket_api.async_response
async def websocket_tv_preferences_save(hass: HomeAssistant, connection, msg) -> None:
    """Persist TV-only preferences for one Fitness profile."""
    try:
        bounded_payload(
            msg,
            max_nodes=8_192,
            max_depth=8,
            max_string_length=8_192,
        )
    except vol.Invalid:
        connection.send_error(msg["id"], "invalid_payload", "Fitness preferences are too large")
        return
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    result = await hub.async_set_preferences(
        profile_entry_id,
        cards=list(msg["cards"]) if "cards" in msg else None,
        dashboard_id=msg.get("dashboard_id"),
        card_layout=dict(msg["card_layout"]) if "card_layout" in msg else None,
        favorites=list(msg["favorites"]) if "favorites" in msg else None,
        user_playlists=list(msg["user_playlists"]) if "user_playlists" in msg else None,
        last_media=dict(msg["last_media"]) if "last_media" in msg else None,
        tv_scale_percent=msg.get("tv_scale_percent"),
        oled_protection=msg.get("oled_protection"),
        animations_enabled=msg.get("animations_enabled"),
        toolbar_auto_hide=msg.get("toolbar_auto_hide"),
        light_feedback_enabled=msg.get("light_feedback_enabled"),
        tts_announcements_enabled=msg.get("tts_announcements_enabled"),
        audio_output_id=msg.get("audio_output_id"),
        music_adapters=list(msg["music_adapters"]) if "music_adapters" in msg else None,
        music_adapter_options=dict(msg["music_adapter_options"]) if "music_adapter_options" in msg else None,
        music_search_limit=msg.get("music_search_limit"),
        music_search_adapters=list(msg["music_search_adapters"]) if "music_search_adapters" in msg else None,
        music_search_scopes=dict(msg["music_search_scopes"]) if "music_search_scopes" in msg else None,
        music_search_types=list(msg["music_search_types"]) if "music_search_types" in msg else None,
    )
    if any(key in msg for key in ("tv_scale_percent", "oled_protection", "animations_enabled", "toolbar_auto_hide", "light_feedback_enabled", "tts_announcements_enabled")):
        hub.broadcast_settings(
            profile_entry_id,
            {
                "tv_scale_percent": result["tv_scale_percent"],
                "oled_protection": result["oled_protection"],
                "animations_enabled": result["animations_enabled"],
                "toolbar_auto_hide": result["toolbar_auto_hide"],
                "light_feedback_enabled": result["light_feedback_enabled"],
                "tts_announcements_enabled": result["tts_announcements_enabled"],
            },
        )
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/dashboard/manage",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("action"): vol.In({"create", "rename", "delete", "select"}),
        vol.Optional("dashboard_id"): vol.All(str, vol.Length(max=64)),
        vol.Optional("name"): vol.All(str, vol.Length(max=MAX_DASHBOARD_NAME_LENGTH)),
    }
)
@websocket_api.async_response
async def websocket_tv_dashboard_manage(hass: HomeAssistant, connection, msg) -> None:
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    from .access_control import get_fitness_access_controller
    controller = get_fitness_access_controller(hass)
    await controller.async_load()
    try:
        result = await hub.async_manage_dashboard(
            profile_entry_id,
            action=str(msg["action"]),
            dashboard_id=str(msg.get("dashboard_id") or ""),
            name=str(msg.get("name") or ""),
            dashboard_max=controller.dashboard_max(),
        )
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/profile/configure",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("enabled"): bool,
        vol.Optional("cast_media_player_id", default=""): vol.All(str, vol.Length(max=255)),
        vol.Optional("ducking_percent", default=DEFAULT_TV_DUCKING_PERCENT): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        vol.Optional(
            "ignore_lights_when_cast_active",
            default=DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
        ): bool,
        vol.Optional("tv_scale_percent", default=DEFAULT_TV_SCALE_PERCENT): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=150)
        ),
        vol.Optional("oled_protection", default=DEFAULT_TV_OLED_PROTECTION): bool,
    }
)
@websocket_api.async_response
async def websocket_tv_profile_configure(hass: HomeAssistant, connection, msg) -> None:
    """Configure one profile's independent Fitness TV target and display settings."""
    profile_entry_id = str(msg["profile_entry_id"])
    entry = hass.config_entries.async_get_entry(profile_entry_id)
    if entry is None or not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return

    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    access = await get_fitness_access_controller(hass).async_descriptor(connection)
    current_config = {**entry.data, **entry.options}
    if access.get("is_admin"):
        target = str(msg.get("cast_media_player_id") or "").strip()
        enabled = bool(msg["enabled"])
    else:
        # Profile owners may tune their own TV/music experience, but only the
        # local Fitness administrator can enable/disable the account-facing TV
        # view or assign a Home-Assistant-network Cast target.
        target = str(current_config.get(CONF_TV_MEDIA_PLAYER_ID) or "").strip()
        enabled = bool(current_config.get(CONF_TV_DASHBOARD_ENABLED, False))
    if target and not target.startswith("media_player."):
        connection.send_error(msg["id"], "invalid_target", "Cast target must be a media_player entity")
        return

    await hub.async_set_preferences(
        profile_entry_id,
        tv_scale_percent=int(msg.get("tv_scale_percent", DEFAULT_TV_SCALE_PERCENT)),
        oled_protection=bool(msg.get("oled_protection", DEFAULT_TV_OLED_PROTECTION)),
    )

    options = dict(entry.options)
    options.update(
        {
            CONF_TV_DASHBOARD_ENABLED: enabled,
            CONF_TV_MEDIA_PLAYER_ID: target,
            CONF_TV_DUCKING_PERCENT: int(
                msg.get("ducking_percent", DEFAULT_TV_DUCKING_PERCENT)
            ),
            CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE: bool(
                msg.get(
                    "ignore_lights_when_cast_active",
                    DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                )
            ),
        }
    )
    hass.config_entries.async_update_entry(entry, options=options)
    result = {
        "enabled": enabled,
        "ytdlp_enabled": bool(current_config.get(CONF_TV_YTDLP_ENABLED, False)),
        "cast_media_player_id": target or None,
        "ducking_percent": int(msg.get("ducking_percent", DEFAULT_TV_DUCKING_PERCENT)),
        "ignore_lights_when_cast_active": bool(
            msg.get(
                "ignore_lights_when_cast_active",
                DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
            )
        ),
        "tv_scale_percent": int(msg.get("tv_scale_percent", DEFAULT_TV_SCALE_PERCENT)),
        "oled_protection": bool(msg.get("oled_protection", DEFAULT_TV_OLED_PROTECTION)),
    }
    hub.broadcast_settings(profile_entry_id, result)
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/heartbeat",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("client_id"): vol.All(str, vol.Length(max=240)),
        vol.Optional("is_cast_receiver", default=False): bool,
    }
)
@websocket_api.async_response
async def websocket_tv_heartbeat(hass: HomeAssistant, connection, msg) -> None:
    """Mark one full-screen Fitness TV browser as active and reconcile Cast truth."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    is_cast_receiver = bool(msg.get("is_cast_receiver", False))
    hub.heartbeat(
        profile_entry_id,
        str(msg["client_id"]),
        is_cast_receiver=is_cast_receiver,
    )
    # The TV receiver's very first heartbeat can race HA's Cast state update.
    # Laptop/controller heartbeats are safe points to reconcile stale sessions.
    if not is_cast_receiver:
        await hub.async_reconcile_profile(profile_entry_id)
    # On a fresh HA process the in-memory media state is empty even though the
    # per-profile last selection is persisted. Restore it before returning the
    # first heartbeat so the frontend does not overwrite a valid Radio Browser,
    # HA media, yt-dlp, YouTube, SoundCloud, etc. selection with a blank state.
    state = await hub.async_restore_last_media(profile_entry_id)
    connection.send_result(
        msg["id"],
        {
            "active": True,
            "audio_owner": hub.is_audio_owner(profile_entry_id, str(msg["client_id"])),
            "cast_target": hub.cast_target(profile_entry_id),
            "cast_active": hub.is_cast_active(profile_entry_id),
            "local_cast_active": hub.is_local_cast_active(profile_entry_id),
            "media_state": state,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/cast/rearm",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("entity_id"): vol.All(str, vol.Length(max=255)),
    }
)
@websocket_api.async_response
async def websocket_tv_cast_rearm(hass: HomeAssistant, connection, msg) -> None:
    """Reattach a still-running HA Cast receiver after an HA process restart."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    entity_id = str(msg.get("entity_id") or "").strip()
    state = hass.states.get(entity_id) if entity_id else None
    app_id = str(state.attributes.get("app_id") or "") if state is not None else ""
    if not entity_id or app_id != CAST_APP_ID_HOMEASSISTANT_LOVELACE:
        connection.send_result(msg["id"], {"armed": False, "entity_id": entity_id})
        return
    hub.expect_cast(profile_entry_id, entity_id)
    hub.arm_cast_receiver(profile_entry_id)
    connection.send_result(msg["id"], {"armed": True, "entity_id": entity_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/local_cast_handoff",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("source_client_id"): vol.All(str, vol.Length(max=240)),
        vol.Optional("reason", default="local_cast_started"): vol.All(str, vol.Length(max=64)),
    }
)
@websocket_api.async_response
async def websocket_tv_local_cast_handoff(hass: HomeAssistant, connection, msg) -> None:
    """Arm browser-local Cast so its receiver owns all Fitness TV audio."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    hub.expect_local_cast(profile_entry_id, str(msg["source_client_id"]))
    connection.send_result(msg["id"], {"armed": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/local_cast_stopped",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Optional("reason", default="local_cast_stopped"): vol.All(str, vol.Length(max=64)),
    }
)
@websocket_api.async_response
async def websocket_tv_local_cast_stopped(hass: HomeAssistant, connection, msg) -> None:
    """Release browser-local Cast ownership when the sender session ends."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    await hub.async_mark_local_cast_inactive(
        profile_entry_id,
        reason=str(msg.get("reason") or "local_cast_stopped"),
    )
    connection.send_result(msg["id"], {"stopped": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/ack",
        vol.Required("announcement_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("client_id"): vol.All(str, vol.Length(max=240)),
        vol.Required("success"): bool,
    }
)
@websocket_api.async_response
async def websocket_tv_ack(hass: HomeAssistant, connection, msg) -> None:
    """Acknowledge completion (or failure) of one browser TTS announcement."""
    profile_entry_id = str(msg["profile_entry_id"])
    hub = await _require_profile_control(hass, connection, profile_entry_id)
    hub.acknowledge(
        str(msg["announcement_id"]),
        str(msg["client_id"]),
        bool(msg["success"]),
    )
    connection.send_result(msg["id"], {"acknowledged": True})




@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/media_command",
        vol.Required("profile_entry_id"): str,
        vol.Required("command"): str,
        vol.Optional("source_client_id"): str,
        vol.Optional("data", default={}): vol.All(
            dict,
            bounded_websocket_payload(max_nodes=256, max_depth=4, max_string_length=4_096),
        ),
    }
)
@websocket_api.async_response
async def websocket_tv_media_command(hass: HomeAssistant, connection, msg) -> None:
    """Forward a shared music control command to the active TV dashboard client."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_control(hass, connection, profile_entry_id)
    result = await hub.async_dispatch_media_command(
        profile_entry_id,
        command=str(msg.get("command") or ""),
        data=dict(msg.get("data") or {}),
        source_client_id=(
            str(msg.get("source_client_id"))
            if msg.get("source_client_id")
            else None
        ),
    )
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/media_state",
        vol.Required("profile_entry_id"): str,
        vol.Optional("source_client_id"): str,
        vol.Optional("state", default=None): vol.Any(
            None,
            vol.All(
                dict,
                bounded_websocket_payload(max_nodes=512, max_depth=5, max_string_length=4_096),
            ),
        ),
    }
)
@websocket_api.async_response
async def websocket_tv_media_state(hass: HomeAssistant, connection, msg) -> None:
    """Get or update shared media state for one TV dashboard profile."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    provided = msg.get("state")
    source_client_id = str(msg.get("source_client_id") or "")
    if isinstance(provided, dict) and (
        not source_client_id or hub.is_audio_owner(profile_entry_id, source_client_id)
    ):
        await hub.async_broadcast_media_state(profile_entry_id, provided)
        # Persist a useful resume point when playback is deliberately paused
        # (including route teardown). Avoid writing storage on every progress tick.
        media_content_id = str(provided.get("media_content_id") or "").strip()
        if media_content_id and provided.get("playing") is False and not provided.get("error"):
            await hub.async_set_preferences(
                profile_entry_id,
                last_media={
                    "media_content_id": media_content_id,
                    "title": str(provided.get("title") or media_content_id),
                    "artist": str(provided.get("artist") or ""),
                    "album": str(provided.get("album") or ""),
                    "year": str(provided.get("year") or ""),
                    "thumbnail": str(provided.get("thumbnail") or ""),
                    "details": str(provided.get("details") or ""),
                    "provider": str(provided.get("provider") or ""),
                    "provider_name": str(provided.get("provider_name") or ""),
                    "provider_origin": str(provided.get("provider_origin") or ""),
                    "playlist_context": provided.get("playlist_context") or {},
                    "duration": hub._media_seconds(provided.get("duration")),
                    "position": hub._media_seconds(provided.get("position")),
                },
            )
    connection.send_result(msg["id"], hub.media_state(profile_entry_id))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/adapters",
        vol.Required("profile_entry_id"): str,
        vol.Optional("ma_player_id", default=""): vol.All(str, vol.Length(max=240)),
    }
)
@websocket_api.async_response
async def websocket_tv_music_adapters(hass: HomeAssistant, connection, msg) -> None:
    """Return capability descriptors for installed Fitness/HA music adapters."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    prefs = await hub.async_preferences(profile_entry_id)
    configured = bool(prefs.get("music_adapters_configured"))
    selected = set(prefs.get("music_adapters") or [])
    current_player_id = _authorized_ma_player_id(
        hass, hub, profile_entry_id, prefs, msg.get("ma_player_id")
    )
    adapters = await async_music_adapters(
        hass,
        hub,
        ytdlp_enabled=_profile_ytdlp_enabled(hass, profile_entry_id),
        adapter_options=prefs.get("music_adapter_options") or {},
        current_player_id=current_player_id,
    )
    rows = []
    for adapter in adapters:
        if not adapter.info.available:
            continue
        row = adapter.info.as_dict()
        profile_enabled = adapter.info.adapter_id in selected if configured else True
        row["selected"] = profile_enabled
        row["profile_enabled"] = profile_enabled
        rows.append(row)
    catalog = await async_music_provider_catalog(
        hass,
        adapter_options=prefs.get("music_adapter_options") or {},
        ytdlp_enabled=_profile_ytdlp_enabled(hass, profile_entry_id),
    )
    connection.send_result(
        msg["id"],
        {
            "adapters": rows,
            "configured": configured,
            "music_search_limit": prefs.get("music_search_limit", DEFAULT_MUSIC_SEARCH_LIMIT),
            "music_search_adapters": prefs.get("music_search_adapters") or [],
            "music_search_configured": bool(prefs.get("music_search_configured")),
            "music_search_scopes": prefs.get("music_search_scopes") or {},
            "music_search_types": prefs.get("music_search_types") or [],
            "music_search_types_configured": bool(prefs.get("music_search_types_configured")),
            "music_adapter_options": prefs.get("music_adapter_options") or {},
            "provider_catalog": catalog,
            "ytdlp_enabled": _profile_ytdlp_enabled(hass, profile_entry_id),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/search",
        vol.Required("profile_entry_id"): str,
        vol.Required("query"): vol.All(str, vol.Length(max=TV_MUSIC_QUERY_LIMIT)),
        vol.Optional("adapters", default=["all"]): [str],
        vol.Optional("scopes", default={}): vol.All(
            dict,
            bounded_websocket_payload(max_nodes=512, max_depth=4, max_string_length=256),
        ),
        vol.Optional("media_types"): [str],
        vol.Optional("ma_player_id", default=""): vol.All(str, vol.Length(max=240)),
    }
)
@websocket_api.async_response
async def websocket_tv_music_search(hass: HomeAssistant, connection, msg) -> None:
    """Search one, several or all enabled searchable music adapters."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    requested_adapters = list(msg.get("adapters") or ["all"])[:32]
    prefs = await hub.async_preferences(profile_entry_id)
    if "all" in requested_adapters:
        if prefs.get("music_adapters_configured"):
            requested_adapters = list(prefs.get("music_adapters") or [])
    if not hub.begin_music_search(profile_entry_id):
        connection.send_error(
            msg["id"], "music_search_busy", "A music search is already running"
        )
        return
    try:
        current_player_id = _authorized_ma_player_id(
            hass, hub, profile_entry_id, prefs, msg.get("ma_player_id")
        )
        result = await async_search_music(
            hass,
            hub,
            query=str(msg.get("query") or ""),
            adapter_ids=requested_adapters,
            ytdlp_enabled=_profile_ytdlp_enabled(hass, profile_entry_id),
            limit=prefs.get("music_search_limit", DEFAULT_MUSIC_SEARCH_LIMIT),
            adapter_options=prefs.get("music_adapter_options") or {},
            search_scopes={
                str(key): [str(item) for item in value]
                for key, value in dict(msg.get("scopes") or {}).items()
                if isinstance(value, list)
            },
            media_types=list(msg["media_types"])[:16] if "media_types" in msg else None,
            current_player_id=current_player_id,
        )
    except Exception as err:  # noqa: BLE001 - provider errors become WS errors
        _LOGGER.warning("Fitness music search failed", exc_info=err)
        connection.send_error(msg["id"], "music_search_error", "Music search failed")
        return
    finally:
        hub.end_music_search(profile_entry_id)
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/ytdlp",
        vol.Required("profile_entry_id"): str,
        vol.Required("enabled"): bool,
        vol.Optional("acknowledged", default=False): bool,
    }
)
@websocket_api.async_response
async def websocket_tv_music_ytdlp(hass: HomeAssistant, connection, msg) -> None:
    """Enable/disable the optional yt-dlp adapter from Music Providers."""
    profile_entry_id = str(msg["profile_entry_id"])
    entry = hass.config_entries.async_get_entry(profile_entry_id)
    if entry is None or not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = get_tv_dashboard_hub(hass)
    await _require_profile_control(hass, connection, profile_entry_id, hub=hub)
    enabled = bool(msg["enabled"])
    if enabled and not bool(msg.get("acknowledged")):
        connection.send_error(
            msg["id"],
            "yt_dlp_ack_required",
            "The yt-dlp legal acknowledgement must be accepted before enabling it",
        )
        return
    options = dict(entry.options)
    options[CONF_TV_YTDLP_ENABLED] = enabled
    # This UI-only option does not require rebuilding the profile manager. A
    # normal config-entry reload briefly tears down every entity and can leave
    # the dashboard on Home Assistant's red configuration-error card.
    get_live_runtime(hass).suppress_entry_reload_once(entry.entry_id)
    hass.config_entries.async_update_entry(entry, options=options)
    prefs = await hub.async_preferences(profile_entry_id)
    configured = bool(prefs.get("music_adapters_configured"))
    selected = list(prefs.get("music_adapters") or [])
    if enabled and configured and "yt_dlp" not in selected:
        selected.append("yt_dlp")
    if not enabled and "yt_dlp" in selected:
        selected = [item for item in selected if item != "yt_dlp"]
    if configured:
        await hub.async_set_preferences(profile_entry_id, music_adapters=selected)
    hub.broadcast_settings(profile_entry_id, {"ytdlp_enabled": enabled})
    connection.send_result(msg["id"], {"enabled": enabled})


def _selected_music_assistant_entry(
    hass: HomeAssistant, adapter_options: dict[str, Any]
) -> Any | None:
    entries = music_assistant_entries(hass, loaded_only=True)
    selected_account_id = str(
        (adapter_options.get("music_assistant") or {}).get("account_id") or ""
    ).strip()
    return select_music_assistant_entry(entries, selected_account_id)


def _authorized_ma_player_id(
    hass: HomeAssistant,
    hub: FitnessTVDashboardHub,
    profile_entry_id: str,
    prefs: dict[str, Any],
    value: Any,
) -> str:
    """Return a player only when it was issued for this profile/MA account."""
    player_id = str(value or "").strip()
    if not player_id:
        return ""
    entry = _selected_music_assistant_entry(
        hass, prefs.get("music_adapter_options") or {}
    )
    if entry is None or not hub.owns_ma_player(
        profile_entry_id, str(entry.entry_id), player_id
    ):
        return ""
    return player_id


def _require_owned_ma_player(
    connection,
    msg: dict[str, Any],
    hub: FitnessTVDashboardHub,
    profile_entry_id: str,
    entry: Any,
    value: Any,
) -> str | None:
    """Reject cross-profile or arbitrary Music Assistant queue identifiers."""
    player_id = str(value or "").strip()
    if not player_id or not hub.owns_ma_player(
        profile_entry_id, str(entry.entry_id), player_id
    ):
        connection.send_error(
            msg["id"], "invalid_player", "Music Assistant player is not owned by this profile"
        )
        return None
    return player_id


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/ma/sendspin",
        vol.Required("profile_entry_id"): str,
        vol.Optional("client_id", default=""): str,
    }
)
@websocket_api.async_response
async def websocket_tv_music_ma_sendspin(hass: HomeAssistant, connection, msg) -> None:
    """Issue a short-lived same-origin relay socket for MA Sendspin playback."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_control(hass, connection, profile_entry_id)
    prefs = await hub.async_preferences(profile_entry_id)
    entry = _selected_music_assistant_entry(
        hass, prefs.get("music_adapter_options") or {}
    )
    if entry is None:
        connection.send_error(
            msg["id"], "music_assistant_unavailable", "Music Assistant server is unavailable"
        )
        return
    # Be defensive around cached/older frontend calls: search metadata must not
    # fail merely because a client id was omitted. Return the authoritative id
    # so the browser uses the same value for Sendspin hello and MA queue_id.
    client_id = str(msg.get("client_id") or "").strip()
    if len(client_id) > 240:
        client_id = ""
    if not _FITNESS_MA_PLAYER_RE.fullmatch(client_id):
        client_id = ""
    client_id = client_id or f"fitness-tv-{uuid4().hex}"
    # After an HA restart MA can still retain the old Fitness queue even though
    # this new hub has no live audio owner yet. Stop only that orphaned queue
    # before reissuing its Sendspin relay; never interrupt the current live owner.
    state = hub.media_state(profile_entry_id)
    if not (
        hub.is_audio_owner(profile_entry_id, client_id)
        and bool(state.get("playing"))
        and str(state.get("media_content_id") or "").startswith(FITNESS_MA_PREFIX)
    ):
        try:
            async with asyncio.timeout(10.0):
                await async_stop_music_assistant_player(entry, client_id)
        except Exception:  # noqa: BLE001 - stale cleanup must not block relay creation
            pass
    relay_url = hub.issue_ma_sendspin_proxy(
        profile_entry_id, str(entry.entry_id), client_id
    )
    connection.send_result(msg["id"], {"url": relay_url, "client_id": client_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/ma/play",
        vol.Required("profile_entry_id"): str,
        vol.Required("player_id"): vol.All(str, vol.Length(max=240)),
        vol.Optional("media_content_id", default=""): vol.All(str, vol.Length(max=4_096)),
        vol.Optional("media_content_ids", default=[]): [str],
        vol.Optional("provider_instance", default=""): vol.All(str, vol.Length(max=240)),
    }
)
@websocket_api.async_response
async def websocket_tv_music_ma_play(hass: HomeAssistant, connection, msg) -> None:
    """Queue one MA result on the Fitness Sendspin browser player."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_control(hass, connection, profile_entry_id)
    prefs = await hub.async_preferences(profile_entry_id)
    entry = _selected_music_assistant_entry(
        hass, prefs.get("music_adapter_options") or {}
    )
    if entry is None:
        connection.send_error(
            msg["id"], "music_assistant_unavailable", "Music Assistant server is unavailable"
        )
        return
    player_id = _require_owned_ma_player(
        connection, msg, hub, profile_entry_id, entry, msg.get("player_id")
    )
    if player_id is None:
        return
    media_content_ids = [
        str(item or "").strip()
        for item in list(msg.get("media_content_ids") or [])[:100]
        if str(item or "").strip()
    ]
    single_media_id = str(msg.get("media_content_id") or "").strip()
    if single_media_id and single_media_id not in media_content_ids:
        media_content_ids.insert(0, single_media_id)
    media_uris = [decode_music_assistant_media_id(item) for item in media_content_ids]
    media_uris = [item for item in media_uris if item]
    if not media_uris:
        connection.send_error(msg["id"], "invalid_media", "Invalid Music Assistant media id")
        return
    provider_instance = str(msg.get("provider_instance") or "").strip()
    provider_domains = {
        media_uri.split("://", 1)[0]
        for media_uri in media_uris
        if "://" in media_uri
    }
    busy = music_assistant_busy_provider_tokens(entry, current_player_id=player_id)
    # Re-check provider availability at play time, not only when the search dialog
    # was opened. This also observes external playback exposed by HA media-player
    # integrations (for example an active Spotify Connect session).
    provider_scopes = await music_assistant_music_provider_scopes(
        entry, hass=hass, current_player_id=player_id
    )
    externally_busy = {
        str(scope.get("id") or "") for scope in provider_scopes if scope.get("busy")
    } | {
        str(scope.get("domain") or "") for scope in provider_scopes if scope.get("busy")
    }
    busy.update(token for token in externally_busy if token)
    if (provider_instance and provider_instance in busy) or bool(provider_domains.intersection(busy)):
        connection.send_error(
            msg["id"],
            "provider_busy",
            "This music-provider account is currently playing on another device",
        )
        return
    try:
        if len(media_uris) > 1:
            await async_play_music_assistant_uris(entry, player_id, media_uris)
        else:
            await async_play_music_assistant_uri(entry, player_id, media_uris[0])
    except Exception as err:  # noqa: BLE001 - MA errors become explicit WS errors
        _LOGGER.warning("Fitness Music Assistant playback failed", exc_info=err)
        connection.send_error(msg["id"], "music_assistant_play_error", "Music Assistant playback failed")
        return
    connection.send_result(msg["id"], {"playing": True, "player_id": player_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/ma/state",
        vol.Required("profile_entry_id"): str,
        vol.Required("player_id"): vol.All(str, vol.Length(max=240)),
    }
)
@websocket_api.async_response
async def websocket_tv_music_ma_state(hass: HomeAssistant, connection, msg) -> None:
    """Return MA's authoritative queue position and current-item duration."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_access(hass, connection, profile_entry_id)
    prefs = await hub.async_preferences(profile_entry_id)
    entry = _selected_music_assistant_entry(
        hass, prefs.get("music_adapter_options") or {}
    )
    if entry is None:
        connection.send_error(
            msg["id"], "music_assistant_unavailable", "Music Assistant server is unavailable"
        )
        return
    player_id = _require_owned_ma_player(
        connection, msg, hub, profile_entry_id, entry, msg.get("player_id")
    )
    if player_id is None:
        return
    connection.send_result(msg["id"], music_assistant_queue_state(entry, player_id))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/ma/seek",
        vol.Required("profile_entry_id"): str,
        vol.Required("player_id"): vol.All(str, vol.Length(max=240)),
        vol.Required("position"): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def websocket_tv_music_ma_seek(hass: HomeAssistant, connection, msg) -> None:
    """Seek the current MA queue item to an absolute position in seconds."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_control(hass, connection, profile_entry_id)
    prefs = await hub.async_preferences(profile_entry_id)
    entry = _selected_music_assistant_entry(
        hass, prefs.get("music_adapter_options") or {}
    )
    if entry is None:
        connection.send_error(
            msg["id"], "music_assistant_unavailable", "Music Assistant server is unavailable"
        )
        return
    player_id = _require_owned_ma_player(
        connection, msg, hub, profile_entry_id, entry, msg.get("player_id")
    )
    if player_id is None:
        return
    try:
        result = await async_seek_music_assistant(entry, player_id, msg.get("position", 0))
    except Exception as err:  # noqa: BLE001 - MA errors become explicit WS errors
        _LOGGER.warning("Fitness Music Assistant seek failed", exc_info=err)
        connection.send_error(msg["id"], "music_assistant_seek_error", "Music Assistant seek failed")
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/ma/queue",
        vol.Required("profile_entry_id"): str,
        vol.Required("player_id"): vol.All(str, vol.Length(max=240)),
        vol.Required("action"): vol.In(["next", "previous", "shuffle", "repeat"]),
        vol.Optional("enabled"): bool,
        vol.Optional("repeat_mode", default="off"): vol.In(["off", "one", "all"]),
    }
)
@websocket_api.async_response
async def websocket_tv_music_ma_queue(hass: HomeAssistant, connection, msg) -> None:
    """Control MA's native queue for provider/Fitness playlists."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_control(hass, connection, profile_entry_id)
    prefs = await hub.async_preferences(profile_entry_id)
    entry = _selected_music_assistant_entry(hass, prefs.get("music_adapter_options") or {})
    if entry is None:
        connection.send_error(msg["id"], "music_assistant_unavailable", "Music Assistant server is unavailable")
        return
    player_id = _require_owned_ma_player(
        connection, msg, hub, profile_entry_id, entry, msg.get("player_id")
    )
    if player_id is None:
        return
    try:
        result = await async_music_assistant_queue_command(
            entry,
            player_id,
            str(msg.get("action") or ""),
            enabled=msg.get("enabled"),
            repeat_mode=str(msg.get("repeat_mode") or "off"),
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Fitness Music Assistant queue command failed", exc_info=err)
        connection.send_error(msg["id"], "music_assistant_queue_error", "Music Assistant queue command failed")
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/ma/playlist",
        vol.Required("profile_entry_id"): str,
        vol.Required("media_content_id"): vol.All(str, vol.Length(max=4_096)),
        vol.Optional("provider_instance", default=""): vol.All(str, vol.Length(max=240)),
    }
)
@websocket_api.async_response
async def websocket_tv_music_ma_playlist(hass: HomeAssistant, connection, msg) -> None:
    """Open a provider/library MA playlist in the Fitness browser."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_access(hass, connection, profile_entry_id)
    prefs = await hub.async_preferences(profile_entry_id)
    entry = _selected_music_assistant_entry(hass, prefs.get("music_adapter_options") or {})
    if entry is None:
        connection.send_error(msg["id"], "music_assistant_unavailable", "Music Assistant server is unavailable")
        return
    media_uri = decode_music_assistant_media_id(str(msg.get("media_content_id") or ""))
    try:
        result = await async_music_assistant_playlist(
            entry, media_uri, provider_instance=str(msg.get("provider_instance") or "")
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Fitness Music Assistant playlist read failed", exc_info=err)
        connection.send_error(msg["id"], "music_assistant_playlist_error", "Music Assistant playlist is unavailable")
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/ma/playlist/remove",
        vol.Required("profile_entry_id"): str,
        vol.Required("library_id"): vol.All(str, vol.Length(max=240)),
        vol.Required("positions"): vol.All([vol.Coerce(int)], vol.Length(max=1_000)),
    }
)
@websocket_api.async_response
async def websocket_tv_music_ma_playlist_remove(hass: HomeAssistant, connection, msg) -> None:
    """Remove tracks from an editable MA playlist."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_control(hass, connection, profile_entry_id)
    prefs = await hub.async_preferences(profile_entry_id)
    entry = _selected_music_assistant_entry(hass, prefs.get("music_adapter_options") or {})
    if entry is None:
        connection.send_error(msg["id"], "music_assistant_unavailable", "Music Assistant server is unavailable")
        return
    try:
        await async_music_assistant_playlist_remove(
            entry, str(msg.get("library_id") or ""), list(msg.get("positions") or [])
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Fitness Music Assistant playlist edit failed", exc_info=err)
        connection.send_error(msg["id"], "music_assistant_playlist_edit_error", "Music Assistant playlist update failed")
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/browse",
        vol.Required("profile_entry_id"): str,
        vol.Required("provider"): str,
        vol.Optional("query", default=""): vol.All(str, vol.Length(max=TV_MUSIC_QUERY_LIMIT)),
        vol.Optional("country_code", default=""): vol.All(str, vol.Length(max=8)),
    }
)
@websocket_api.async_response
async def websocket_tv_music_browse(hass: HomeAssistant, connection, msg) -> None:
    """Browse a Fitness-native music provider without another HA integration."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_control(hass, connection, profile_entry_id)
    provider = str(msg.get("provider") or "").strip()
    prefs = await hub.async_preferences(profile_entry_id)
    if provider == "radio" and not _music_adapter_enabled_for_preferences(prefs, "radio_browser"):
        connection.send_error(msg["id"], "music_adapter_disabled", "Radio Browser is disabled for this Fitness profile")
        return
    try:
        result = await hub.async_music_browse(
            provider,
            query=str(msg.get("query") or ""),
            country_code=str(msg.get("country_code") or ""),
            ytdlp_enabled=_profile_ytdlp_enabled(hass, profile_entry_id),
        )
    except Exception as err:  # noqa: BLE001 - provider/network errors become WS errors
        _LOGGER.warning("Fitness music provider browse failed", exc_info=err)
        connection.send_error(msg["id"], "music_provider_error", "Music provider is unavailable")
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/music/resolve",
        vol.Required("profile_entry_id"): str,
        vol.Required("media_content_id"): vol.All(str, vol.Length(max=8_192)),
    }
)
@websocket_api.async_response
async def websocket_tv_music_resolve(hass: HomeAssistant, connection, msg) -> None:
    """Resolve a Fitness-native media ID to its current browser playback target."""
    profile_entry_id = str(msg["profile_entry_id"])
    if not _profile_loaded(hass, profile_entry_id):
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    hub = await _require_profile_control(hass, connection, profile_entry_id)
    media_content_id = str(msg.get("media_content_id") or "")
    prefs = await hub.async_preferences(profile_entry_id)
    if media_content_id.startswith(FITNESS_RADIO_PREFIX) and not _music_adapter_enabled_for_preferences(prefs, "radio_browser"):
        connection.send_error(msg["id"], "music_adapter_disabled", "Radio Browser is disabled for this Fitness profile")
        return
    if not hub.begin_music_resolution(profile_entry_id):
        connection.send_error(
            msg["id"], "music_resolve_busy", "A media item is already being prepared"
        )
        return
    try:
        result = await hub.async_resolve_fitness_media(
            media_content_id,
            ytdlp_enabled=_profile_ytdlp_enabled(hass, profile_entry_id),
        )
    except Exception as err:  # noqa: BLE001 - invalid/remote media becomes WS error
        _LOGGER.warning("Fitness music resolution failed", exc_info=err)
        connection.send_error(msg["id"], "music_resolve_error", "Unable to prepare this media item")
        return
    finally:
        hub.end_music_resolution(profile_entry_id)
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/start_workout",
        vol.Required("profile_entry_id"): str,
        vol.Optional("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_tv_start_workout(hass: HomeAssistant, connection, msg) -> None:
    """Prepare the profile TV, restore music, then arm workout capture."""
    profile_entry_id = str(msg["profile_entry_id"])
    manager = hass.data.get(DOMAIN, {}).get(profile_entry_id)
    if manager is None:
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not loaded")
        return
    await _require_profile_control(hass, connection, profile_entry_id)
    result = await manager.async_start_tv_workout(
        str(msg.get("entity_id") or "").strip() or None
    )
    connection.send_result(msg["id"], result)


def async_register_tv_websocket_commands(hass: HomeAssistant) -> None:
    """Register TV-dashboard commands with Home Assistant's WebSocket API."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get(MUSIC_PROXY_VIEW_KEY):
        hass.http.register_view(FitnessMusicProxyView())
        domain_data[MUSIC_PROXY_VIEW_KEY] = True
    if not domain_data.get(MA_SENDSPIN_PROXY_VIEW_KEY):
        hass.http.register_view(FitnessMASendspinProxyView())
        domain_data[MA_SENDSPIN_PROXY_VIEW_KEY] = True
    websocket_api.async_register_command(hass, websocket_tv_preferences)
    websocket_api.async_register_command(hass, websocket_tv_preferences_save)
    websocket_api.async_register_command(hass, websocket_tv_dashboard_manage)
    websocket_api.async_register_command(hass, websocket_tv_profile_configure)
    websocket_api.async_register_command(hass, websocket_tv_heartbeat)
    websocket_api.async_register_command(hass, websocket_tv_cast_rearm)
    websocket_api.async_register_command(hass, websocket_tv_local_cast_handoff)
    websocket_api.async_register_command(hass, websocket_tv_local_cast_stopped)
    websocket_api.async_register_command(hass, websocket_tv_ack)
    websocket_api.async_register_command(hass, websocket_tv_media_command)
    websocket_api.async_register_command(hass, websocket_tv_media_state)
    websocket_api.async_register_command(hass, websocket_tv_music_adapters)
    websocket_api.async_register_command(hass, websocket_tv_music_search)
    websocket_api.async_register_command(hass, websocket_tv_music_ytdlp)
    websocket_api.async_register_command(hass, websocket_tv_music_ma_sendspin)
    websocket_api.async_register_command(hass, websocket_tv_music_ma_play)
    websocket_api.async_register_command(hass, websocket_tv_music_ma_state)
    websocket_api.async_register_command(hass, websocket_tv_music_ma_seek)
    websocket_api.async_register_command(hass, websocket_tv_music_ma_queue)
    websocket_api.async_register_command(hass, websocket_tv_music_ma_playlist)
    websocket_api.async_register_command(hass, websocket_tv_music_ma_playlist_remove)
    websocket_api.async_register_command(hass, websocket_tv_music_browse)
    websocket_api.async_register_command(hass, websocket_tv_music_resolve)
    websocket_api.async_register_command(hass, websocket_tv_start_workout)
    async_register_remote_gateway_websocket_commands(hass)
