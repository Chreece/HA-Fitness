"""Music Assistant adapter exposed as one provider, never one row per MA source."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .base import MusicAdapter, MusicAdapterInfo, clamp_search_limit

MUSIC_ASSISTANT_INSTALL_URL = "https://www.music-assistant.io/installation/"
MUSIC_ASSISTANT_MUSIC_PATH = "/#/music"
MUSIC_ASSISTANT_SETTINGS_PATH = "/#/settings"
MUSIC_ASSISTANT_PROVIDER_PATH = "/#/settings/providers?types=music"
MUSIC_ASSISTANT_ADD_PROVIDER_PATH = "/#/settings/addprovider/{provider_id}"
MUSIC_ASSISTANT_EDIT_PROVIDER_PATH = "/#/settings/editprovider/{instance_id}"
MUSIC_ASSISTANT_ADDON_INGRESS = "/hassio/ingress/music_assistant"
FITNESS_MA_PREFIX = "fitness-ma://"
MUSIC_ASSISTANT_SENDSPIN_PORT = 8927


def decode_music_assistant_media_id(media_content_id: str) -> str:
    """Decode a stable Fitness MA media id back to the MA media URI."""
    value = str(media_content_id or "").strip()
    if not value.startswith(FITNESS_MA_PREFIX):
        return ""
    return unquote(value[len(FITNESS_MA_PREFIX) :]).strip()


def music_assistant_entries(
    hass: HomeAssistant, *, loaded_only: bool = True
) -> list[Any]:
    """Return configured official/legacy Music Assistant entries."""
    entries: list[Any] = []
    for domain in ("music_assistant", "mass"):
        try:
            domain_entries = hass.config_entries.async_entries(domain)
        except Exception:  # noqa: BLE001 - tolerate HA version/test doubles
            domain_entries = []
        for entry in domain_entries:
            if loaded_only:
                state = getattr(entry, "state", None)
                if state not in (None, ConfigEntryState.LOADED) and str(state).lower() not in {
                    "loaded",
                    "configentrystate.loaded",
                }:
                    continue
            if entry not in entries:
                entries.append(entry)
    return entries


def _loaded_entries(hass: HomeAssistant) -> list[Any]:
    """Compatibility alias retained for unreleased tests/callers."""
    return music_assistant_entries(hass, loaded_only=True)


def music_assistant_entry_url(entry: Any) -> str:
    """Return the browser/server URL stored by the HA Music Assistant entry."""
    data = getattr(entry, "data", {}) or {}
    raw = str(data.get("url") or data.get("server_url") or "").strip().rstrip("/")
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def music_assistant_sendspin_url(entry: Any) -> str:
    """Return MA's authenticated browser Sendspin proxy endpoint.

    Stable Music Assistant exposes ``/sendspin`` on its normal web/API origin.
    That endpoint authenticates the web client and associates its ``client_id``
    with the MA user before proxying to the internal Sendspin server. Fitness
    authenticates this upstream connection server-side so the MA token is never
    exposed to the Fitness TV browser.
    """
    base = music_assistant_entry_url(entry)
    if not base:
        return ""
    try:
        parsed = urlsplit(base)
    except ValueError:
        return ""
    if not parsed.netloc:
        return ""
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((scheme, parsed.netloc, "/sendspin", "", ""))


def music_assistant_direct_sendspin_url(entry: Any) -> str:
    """Return MA's unauthenticated direct Sendspin endpoint for legacy fallback."""
    base = music_assistant_entry_url(entry)
    if not base:
        return ""
    try:
        parsed = urlsplit(base)
    except ValueError:
        return ""
    host = str(parsed.hostname or "").strip()
    if not host:
        return ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{host}:{MUSIC_ASSISTANT_SENDSPIN_PORT}/sendspin"


def _ma_url(entry: Any, route: str) -> str:
    """Return a browser-safe MA route for Container or Supervisor installs."""
    if music_assistant_is_addon(entry):
        # The hash fragment belongs to MA's SPA and is safe after the HA ingress
        # path; do not expose the add-on's internal container URL to the browser.
        return f"{MUSIC_ASSISTANT_ADDON_INGRESS}{route}"
    base = music_assistant_entry_url(entry)
    return f"{base}{route}" if base else ""


def music_assistant_music_url(entry: Any) -> str:
    """Return the Music Assistant library/player page."""
    return _ma_url(entry, MUSIC_ASSISTANT_MUSIC_PATH)


def music_assistant_settings_url(entry: Any) -> str:
    """Return the Music Assistant root settings page."""
    return _ma_url(entry, MUSIC_ASSISTANT_SETTINGS_PATH)


def music_assistant_provider_url(entry: Any) -> str:
    """Return the MA web UI page filtered to music providers."""
    return _ma_url(entry, MUSIC_ASSISTANT_PROVIDER_PATH)


def music_assistant_add_provider_url(entry: Any, provider_id: str) -> str:
    """Return MA's provider-specific setup page."""
    provider_id = str(provider_id or "").strip()
    if not provider_id:
        return ""
    route = MUSIC_ASSISTANT_ADD_PROVIDER_PATH.format(
        provider_id=quote(provider_id, safe="")
    )
    return _ma_url(entry, route)


def music_assistant_edit_provider_url(entry: Any, instance_id: str) -> str:
    """Return MA's provider-instance edit page."""
    instance_id = str(instance_id or "").strip()
    if not instance_id:
        return ""
    route = MUSIC_ASSISTANT_EDIT_PROVIDER_PATH.format(
        instance_id=quote(instance_id, safe="")
    )
    return _ma_url(entry, route)


def music_assistant_is_addon(entry: Any) -> bool:
    """Return whether this HA entry is connected to the Supervisor MA app."""
    runtime_data = getattr(entry, "runtime_data", None)
    mass = getattr(runtime_data, "mass", None)
    server_info = getattr(mass, "server_info", None)
    return bool(getattr(server_info, "homeassistant_addon", False))


def select_music_assistant_entry(
    entries: list[Any], selected_account_id: str = ""
) -> Any | None:
    """Choose the profile-selected MA server, or the sole configured server."""
    selected_account_id = str(selected_account_id or "").strip()
    if selected_account_id:
        for entry in entries:
            if str(getattr(entry, "entry_id", "")) == selected_account_id:
                return entry
    return entries[0] if len(entries) == 1 else None


def _mass_client(entry: Any) -> Any | None:
    runtime_data = getattr(entry, "runtime_data", None)
    return getattr(runtime_data, "mass", None)


async def music_assistant_music_provider_manifests(entry: Any) -> list[dict[str, str]]:
    """Return the selected MA server's currently supported music-source manifests.

    Querying ``providers/manifests`` keeps Fitness aligned with the exact Music
    Assistant server version instead of maintaining a permanently stale provider
    list.  A caller can still use its local fallback list when this API is not
    available on an older/offline server.
    """
    mass = _mass_client(entry)
    sender = getattr(mass, "send_command", None)
    if not callable(sender):
        return []
    try:
        manifests = await sender("providers/manifests")
    except Exception:  # noqa: BLE001 - optional external server/API
        return []
    if isinstance(manifests, dict):
        manifests = manifests.get("result") or manifests.get("items") or []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in manifests or []:
        if isinstance(item, dict):
            get = item.get
        else:
            get = lambda key, default=None, obj=item: getattr(obj, key, default)
        provider_type = get("type", "")
        provider_type = getattr(provider_type, "value", provider_type)
        if str(provider_type).lower() not in {"music", "providertype.music"}:
            continue
        domain = str(get("domain", "") or "").strip()
        # MA's builtin library is represented by the main Music Assistant row;
        # it is not a user-addable source and therefore gets no addprovider link.
        if not domain or domain in seen or domain in {"builtin"}:
            continue
        seen.add(domain)
        result.append(
            {
                "domain": domain,
                "name": str(get("name", "") or domain.replace("_", " ").title()).strip(),
                "description": str(get("description", "") or "").strip(),
                "icon": str(get("icon", "") or "").strip(),
            }
        )
    result.sort(key=lambda item: item["name"].casefold())
    return result


async def music_assistant_music_provider_instances(entry: Any) -> dict[str, list[str]]:
    """Return installed MA music-provider instance ids grouped by provider domain."""
    mass = _mass_client(entry)
    config = getattr(mass, "config", None)
    getter = getattr(config, "get_provider_configs", None)
    if not callable(getter):
        return {}
    try:
        configs = await getter()
    except Exception:  # noqa: BLE001 - MA server/API availability is optional here
        return {}
    result: dict[str, list[str]] = {}
    for item in configs or []:
        provider_type = getattr(getattr(item, "type", None), "value", getattr(item, "type", ""))
        if str(provider_type).lower() not in {"music", "providertype.music"}:
            continue
        domain = str(getattr(item, "domain", "") or "").strip()
        instance_id = str(getattr(item, "instance_id", "") or "").strip()
        if not domain:
            continue
        result.setdefault(domain, [])
        if instance_id and instance_id not in result[domain]:
            result[domain].append(instance_id)
    return result


def _queue_is_playing(queue: Any) -> bool:
    state = getattr(queue, "state", "")
    state = getattr(state, "value", state)
    return str(state or "").strip().lower() in {"playing", "playbackstate.playing"}


def _provider_tokens_from_object(value: Any) -> set[str]:
    """Collect provider instance/domain identifiers from an MA media object."""
    result: set[str] = set()
    if value is None:
        return result
    getter = value.get if isinstance(value, dict) else lambda key, default=None: getattr(value, key, default)
    for key in ("provider", "provider_instance", "provider_instance_id"):
        token = str(getter(key, "") or "").strip()
        if token:
            result.add(token)
    mappings = getter("provider_mappings", None) or []
    for mapping in mappings:
        mapping_get = mapping.get if isinstance(mapping, dict) else lambda key, default=None, obj=mapping: getattr(obj, key, default)
        for key in ("provider_instance", "provider_instance_id", "provider_domain", "provider"):
            token = str(mapping_get(key, "") or "").strip()
            if token:
                result.add(token)
    return result


def _queue_provider_tokens(queue: Any) -> set[str]:
    """Best-effort provider identifiers for the queue's current MA item."""
    item = getattr(queue, "current_item", None)
    values = [
        item,
        getattr(item, "media_item", None),
        getattr(item, "streamdetails", None),
        getattr(item, "stream_details", None),
    ]
    result: set[str] = set()
    for value in values:
        result.update(_provider_tokens_from_object(value))
    return result


def music_assistant_busy_provider_tokens(
    entry: Any, *, current_player_id: str = ""
) -> set[str]:
    """Return MA provider instance/domain ids currently playing elsewhere.

    Music Assistant keeps live PlayerQueue state in its client controller.  A queue
    owned by the current Fitness browser player is ignored; every other playing
    queue contributes its provider ids.  This intentionally observes MA playback
    regardless of whether it was started by Fitness or the MA UI/another client.
    """
    mass = _mass_client(entry)
    controller = getattr(mass, "player_queues", None)
    if controller is None:
        return set()
    try:
        queues = list(controller)
    except TypeError:
        raw = getattr(controller, "queues", None) or getattr(controller, "_queues", None) or {}
        queues = list(raw.values()) if isinstance(raw, dict) else list(raw or [])
    current_player_id = str(current_player_id or "").strip()
    result: set[str] = set()
    for queue in queues:
        queue_id = str(getattr(queue, "queue_id", "") or getattr(queue, "player_id", "") or "").strip()
        if current_player_id and queue_id == current_player_id:
            continue
        if not _queue_is_playing(queue):
            continue
        result.update(_queue_provider_tokens(queue))
    return result


async def music_assistant_music_provider_scopes(
    entry: Any,
    *,
    hass: HomeAssistant | None = None,
    current_player_id: str = "",
) -> list[dict[str, Any]]:
    """Return configured MA music-provider instances suitable as search scopes."""
    mass = _mass_client(entry)
    config = getattr(mass, "config", None)
    getter = getattr(config, "get_provider_configs", None)
    if not callable(getter):
        return []
    try:
        configs = await getter()
    except Exception:  # noqa: BLE001 - optional external server/API
        return []
    manifests = {
        item["domain"]: item for item in await music_assistant_music_provider_manifests(entry)
    }
    busy = music_assistant_busy_provider_tokens(entry, current_player_id=current_player_id)
    # Some account-backed HA integrations (notably Spotify Connect) expose
    # playback started outside Fitness. Treat the provider domain as busy while
    # that integration is actively playing so Fitness does not steal the account.
    externally_busy_domains: set[str] = set()
    if hass is not None:
        try:
            registry = er.async_get(hass)
            for state in hass.states.async_all():
                if not str(getattr(state, "entity_id", "")).startswith("media_player."):
                    continue
                if str(getattr(state, "state", "")).lower() != "playing":
                    continue
                entity = registry.async_get(state.entity_id)
                platform = str(getattr(entity, "platform", "") or "").strip()
                if platform:
                    externally_busy_domains.add(platform)
        except Exception:  # noqa: BLE001 - entity registry is advisory here
            externally_busy_domains = set()
    rows: list[dict[str, Any]] = []
    for item in configs or []:
        provider_type = getattr(getattr(item, "type", None), "value", getattr(item, "type", ""))
        if str(provider_type).lower() not in {"music", "providertype.music"}:
            continue
        domain = str(getattr(item, "domain", "") or "").strip()
        instance_id = str(getattr(item, "instance_id", "") or "").strip()
        if not domain or not instance_id or domain == "builtin":
            continue
        manifest = manifests.get(domain) or {}
        display_name = str(
            getattr(item, "name", "")
            or getattr(item, "display_name", "")
            or manifest.get("name")
            or domain.replace("_", " ").title()
        ).strip()
        is_busy = (
            instance_id in busy
            or domain in busy
            or domain in externally_busy_domains
        )
        rows.append(
            {
                "id": instance_id,
                "domain": domain,
                "name": display_name,
                "icon": str(manifest.get("icon") or "mdi:music-note"),
                "available": not is_busy,
                "busy": is_busy,
                "unavailable_reason": (
                    "This Music Assistant provider is currently playing on another device."
                    if is_busy
                    else ""
                ),
            }
        )
    rows.sort(key=lambda row: (str(row["name"]).casefold(), str(row["id"])))
    return rows



async def async_stop_music_assistant_player(entry: Any, player_id: str) -> bool:
    """Stop one Fitness-owned Music Assistant queue/player.

    Fitness browser players use their stable ``fitness-tv-*`` client id as the
    MA queue id.  Explicitly stopping that queue before a Fitness/HA reload
    releases account-backed providers such as Spotify instead of leaving an
    orphaned queue that makes the provider appear busy after restart.
    """
    mass = _mass_client(entry)
    player_id = str(player_id or "").strip()
    if mass is None or not player_id:
        return False
    queues = getattr(mass, "player_queues", None)
    stopper = getattr(queues, "stop", None)
    sender = getattr(mass, "send_command", None)
    try:
        if callable(stopper):
            await stopper(player_id)
        elif callable(sender):
            await sender("player_queues/stop", queue_id=player_id)
        else:
            return False
    except Exception:
        # A queue that already disappeared is effectively stopped.  Only return
        # False when MA is completely unavailable; shutdown must never block HA.
        state = music_assistant_queue_state(entry, player_id)
        return not bool(state.get("available"))
    return True


async def async_play_music_assistant_uri(
    entry: Any,
    player_id: str,
    media_uri: str,
) -> None:
    """Play one MA provider URI on the connected Fitness Sendspin web player."""
    mass = _mass_client(entry)
    player_id = str(player_id or "").strip()
    media_uri = str(media_uri or "").strip()
    if mass is None or not player_id or not media_uri:
        raise ValueError("Music Assistant player or media is missing")
    queues = getattr(mass, "player_queues", None)
    play_media = getattr(queues, "play_media", None)
    sender = getattr(mass, "send_command", None)

    # MA stable 2.9.x registers Sendspin 3.x clients by their explicit player_id.
    # The queue may materialize a moment after the WebSocket hello, so retry the
    # canonical queue command until that exact player queue exists.
    last_error: Exception | None = None
    for attempt in range(40):
        try:
            if callable(sender):
                await sender(
                    "player_queues/play_media",
                    queue_id=player_id,
                    media=media_uri,
                )
            elif callable(play_media):
                await play_media(player_id, media=media_uri)
            else:
                raise RuntimeError("Music Assistant queue API is unavailable")
            return
        except Exception as err:  # noqa: BLE001 - retry MA queue materialization race
            last_error = err
            if attempt < 39:
                await asyncio.sleep(0.25)
    raise RuntimeError(f"Music Assistant could not start this item: {last_error}") from last_error


async def async_play_music_assistant_uris(
    entry: Any, player_id: str, media_uris: list[str]
) -> None:
    """Play an ordered list of MA URIs as one native MA queue."""
    uris = [str(uri or "").strip() for uri in media_uris if str(uri or "").strip()]
    if not uris:
        raise ValueError("No Music Assistant media selected")
    if len(uris) == 1:
        await async_play_music_assistant_uri(entry, player_id, uris[0])
        return
    mass = _mass_client(entry)
    player_id = str(player_id or "").strip()
    sender = getattr(mass, "send_command", None)
    if mass is None or not player_id or not callable(sender):
        raise RuntimeError("Music Assistant queue API is unavailable")
    last_error: Exception | None = None
    for attempt in range(40):
        try:
            await sender("player_queues/play_media", queue_id=player_id, media=uris)
            return
        except Exception as err:  # noqa: BLE001
            last_error = err
            if attempt < 39:
                await asyncio.sleep(0.25)
    raise RuntimeError(f"Music Assistant could not start selected items: {last_error}") from last_error


async def async_music_assistant_queue_command(
    entry: Any, player_id: str, action: str, *, enabled: bool | None = None, repeat_mode: str = ""
) -> dict[str, Any]:
    """Run native MA playlist/queue transport commands."""
    mass = _mass_client(entry)
    sender = getattr(mass, "send_command", None)
    player_id = str(player_id or "").strip()
    action = str(action or "").strip().lower()
    if mass is None or not player_id or not callable(sender):
        raise RuntimeError("Music Assistant queue API is unavailable")
    if action in {"next", "previous"}:
        await sender(f"player_queues/{action}", queue_id=player_id)
    elif action == "shuffle":
        await sender("player_queues/shuffle", queue_id=player_id, shuffle_enabled=bool(enabled))
    elif action == "repeat":
        mode = str(repeat_mode or "off").lower()
        if mode not in {"off", "one", "all"}:
            raise ValueError("Invalid repeat mode")
        await sender("player_queues/repeat", queue_id=player_id, repeat_mode=mode)
    else:
        raise ValueError("Unsupported Music Assistant queue command")
    return music_assistant_queue_state(entry, player_id)


async def async_music_assistant_playlist(
    entry: Any, media_uri: str, *, provider_instance: str = ""
) -> dict[str, Any]:
    """Open an MA provider/library playlist and normalize its tracks for Fitness."""
    mass = _mass_client(entry)
    sender = getattr(mass, "send_command", None)
    if mass is None or not callable(sender):
        raise RuntimeError("Music Assistant playlist API is unavailable")
    provider, media_type, item_id = _ma_uri_parts(media_uri)
    if media_type != "playlist" or not item_id:
        raise ValueError("This Music Assistant result is not a playlist")
    lookup_provider = str(provider_instance or provider or "").strip()
    playlist = await sender(
        "music/playlists/get",
        item_id=item_id,
        provider_instance_id_or_domain=lookup_provider,
    )
    resolved_provider = str(_ma_value(playlist, "provider", lookup_provider) or lookup_provider)
    resolved_item_id = str(_ma_value(playlist, "item_id", item_id) or item_id)
    rows = await sender(
        "music/playlists/playlist_tracks",
        item_id=resolved_item_id,
        provider_instance_id_or_domain=resolved_provider,
    )
    if isinstance(rows, dict):
        rows = rows.get("items") or rows.get("result") or []
    tracks = [
        _ma_playlist_track_row(entry, mass, item, index + 1)
        for index, item in enumerate(list(rows or []))
        if str(_ma_value(item, "uri", "") or "").strip()
    ]
    library_id = resolved_item_id if resolved_provider == "library" else ""
    return {
        "title": str(_ma_value(playlist, "name", "") or "Playlist"),
        "media_content_id": f"{FITNESS_MA_PREFIX}{quote(str(_ma_value(playlist, 'uri', media_uri) or media_uri), safe='')}",
        "media_class": "playlist",
        "thumbnail": _ma_image_url(entry, mass, playlist),
        "provider": provider,
        "provider_instance": lookup_provider,
        "provider_origin": "Music Assistant" + (f" · {provider}" if provider else ""),
        "is_editable": bool(_ma_value(playlist, "is_editable", False) and library_id),
        "library_id": library_id,
        "children": tracks,
    }


async def async_music_assistant_playlist_remove(
    entry: Any, library_id: str, positions: list[int]
) -> None:
    """Remove selected provider-playlist positions when MA marks it editable."""
    mass = _mass_client(entry)
    sender = getattr(mass, "send_command", None)
    if mass is None or not callable(sender):
        raise RuntimeError("Music Assistant playlist API is unavailable")
    clean = tuple(sorted({int(pos) for pos in positions if int(pos) > 0}))
    if not library_id or not clean:
        raise ValueError("Playlist or track position is missing")
    await sender(
        "music/playlists/remove_playlist_tracks",
        db_playlist_id=str(library_id),
        positions_to_remove=clean,
    )


def music_assistant_queue_state(entry: Any, player_id: str) -> dict[str, Any]:
    """Return MA's authoritative queue progress for one Fitness player.

    Sendspin is the audio transport, but Music Assistant's PlayerQueue is the
    source of truth for the logical track duration and current media position.
    The MA client keeps ``elapsed_time`` fresh from QUEUE_TIME_UPDATED events;
    between updates ``corrected_elapsed_time`` advances it against wall clock.
    """
    mass = _mass_client(entry)
    player_id = str(player_id or "").strip()
    if mass is None or not player_id:
        return {
            "available": False,
            "active": False,
            "playing": False,
            "position": 0.0,
            "duration": 0.0,
            "seekable": False,
        }

    queues = getattr(mass, "player_queues", None)
    getter = getattr(queues, "get", None)
    queue = getter(player_id) if callable(getter) else None
    if queue is None:
        return {
            "available": False,
            "active": False,
            "playing": False,
            "position": 0.0,
            "duration": 0.0,
            "seekable": False,
        }

    state_value = getattr(getattr(queue, "state", None), "value", None)
    state = str(state_value or getattr(queue, "state", "") or "").lower()
    active = bool(getattr(queue, "active", False))
    playing = state.endswith("playing") or state == "playing"
    current_item = getattr(queue, "current_item", None)
    try:
        duration = float(getattr(current_item, "duration", 0) or 0)
    except (TypeError, ValueError):
        duration = 0.0

    try:
        corrected = getattr(queue, "corrected_elapsed_time")
        position = float(corrected or 0)
    except (AttributeError, TypeError, ValueError):
        try:
            position = float(getattr(queue, "elapsed_time", 0) or 0)
        except (TypeError, ValueError):
            position = 0.0
        if playing:
            try:
                updated = float(getattr(queue, "elapsed_time_last_updated", 0) or 0)
                speed = float(getattr(queue, "playback_speed", 1) or 1)
            except (TypeError, ValueError):
                updated, speed = 0.0, 1.0
            if updated > 0:
                position += max(0.0, time.time() - updated) * max(0.0, speed)

    position = max(0.0, position)
    duration = max(0.0, duration)
    if duration > 0:
        position = min(position, duration)

    return {
        "available": True,
        "active": active,
        "playing": playing,
        "state": state,
        "position": position,
        "duration": duration,
        "seekable": bool(active and duration > 0),
        "queue_item_id": str(getattr(current_item, "queue_item_id", "") or ""),
        "current_index": getattr(queue, "current_index", None),
        "items": int(getattr(queue, "items", 0) or 0),
        "shuffle_enabled": bool(getattr(queue, "shuffle_enabled", False)),
        "repeat_mode": str(getattr(getattr(queue, "repeat_mode", None), "value", getattr(queue, "repeat_mode", "off")) or "off").lower(),
        "active_playlist": str((getattr(queue, "extra_attributes", {}) or {}).get("active_playlist") or ""),
    }


async def async_seek_music_assistant(
    entry: Any, player_id: str, position: float | int
) -> dict[str, Any]:
    """Seek MA's current queue item and return the updated logical progress."""
    mass = _mass_client(entry)
    player_id = str(player_id or "").strip()
    if mass is None or not player_id:
        raise ValueError("Music Assistant player is missing")

    state = music_assistant_queue_state(entry, player_id)
    if not state.get("available") or not state.get("active"):
        raise RuntimeError("Music Assistant player queue is not active")
    duration = float(state.get("duration") or 0)
    if duration <= 0:
        raise RuntimeError("This Music Assistant item does not support seeking")
    try:
        requested = max(0.0, float(position or 0))
    except (TypeError, ValueError) as err:
        raise ValueError("Invalid Music Assistant seek position") from err
    requested = min(requested, duration)

    queues = getattr(mass, "player_queues", None)
    seeker = getattr(queues, "seek", None)
    sender = getattr(mass, "send_command", None)
    if callable(seeker):
        await seeker(player_id, int(requested))
    elif callable(sender):
        await sender("player_queues/seek", queue_id=player_id, position=int(requested))
    else:
        raise RuntimeError("Music Assistant seek API is unavailable")

    # The queue event can arrive just after the command response. Return the
    # requested position immediately so the UI does not jump backwards while
    # the authoritative QUEUE_TIME_UPDATED event catches up.
    result = music_assistant_queue_state(entry, player_id)
    result["position"] = requested
    result["duration"] = duration
    result["seekable"] = True
    return result


def music_assistant_setup_path(
    hass: HomeAssistant,
    entries: list[Any],
    *,
    selected_account_id: str = "",
    destination: str = "music",
) -> str:
    """Return the best browser destination for the selected MA server."""
    selected = select_music_assistant_entry(entries, selected_account_id)
    if selected is not None:
        if destination == "providers":
            return music_assistant_provider_url(selected)
        if destination == "settings":
            return music_assistant_settings_url(selected)
        return music_assistant_music_url(selected)
    if len(entries) > 1:
        return ""
    components = getattr(getattr(hass, "config", None), "components", set()) or set()
    if "hassio" in components:
        return MUSIC_ASSISTANT_ADDON_INGRESS
    return ""


def _ma_value(item: Any, key: str, default: Any = None) -> Any:
    """Read one MA model/dict value without depending on one model release."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _ma_name(value: Any) -> str:
    """Return a human-readable name from MA mappings/models/strings."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("name") or value.get("title") or "").strip()
    return str(getattr(value, "name", "") or getattr(value, "title", "") or "").strip()


def _item_artist(item: Any) -> str:
    artists = _ma_value(item, "artists")
    if artists:
        names = [_ma_name(value) for value in list(artists or [])]
        return ", ".join(name for name in names if name)
    return _ma_name(_ma_value(item, "artist"))


def _item_album(item: Any) -> str:
    return _ma_name(_ma_value(item, "album")) or _ma_name(_ma_value(item, "album_name"))


def _release_year(value: Any) -> int | None:
    """Normalize an MA year/release-date value to a four-digit year."""
    if value is None or value == "":
        return None
    if hasattr(value, "year"):
        try:
            year = int(value.year)
            if 1000 <= year <= 9999:
                return year
        except (TypeError, ValueError):
            pass
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        year = int(text[:4])
        if 1000 <= year <= 9999:
            return year
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if 1000 <= year <= 9999 else None


def _item_year(item: Any) -> int | None:
    direct = _release_year(_ma_value(item, "year"))
    if direct:
        return direct
    album = _ma_value(item, "album")
    album_year = _release_year(_ma_value(album, "year"))
    if album_year:
        return album_year
    for source in (_ma_value(item, "metadata"), _ma_value(album, "metadata")):
        for key in ("release_date", "year", "original_release_date"):
            value = _release_year(_ma_value(source, key))
            if value:
                return value
    return None


def _item_provider(item: Any) -> str:
    return str(
        _ma_value(item, "provider", "")
        or _ma_value(item, "provider_instance", "")
        or ""
    ).strip()


def _item_media_type(item: Any) -> str:
    media_type = _ma_value(item, "media_type", "")
    return str(getattr(media_type, "value", media_type) or "").strip().lower()


def _item_duration(item: Any) -> float:
    try:
        value = float(_ma_value(item, "duration", 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, value)


def _ma_image_object(item: Any) -> Any | None:
    """Return the best thumb image carried by an MA media item/mapping."""
    if item is None:
        return None
    image = _ma_value(item, "image")
    if image:
        return image
    album = _ma_value(item, "album")
    album_image = _ma_value(album, "image")
    if album_image:
        return album_image
    for source in (item, album):
        metadata = _ma_value(source, "metadata")
        images = _ma_value(metadata, "images")
        for candidate in list(images or []):
            image_type = _ma_value(candidate, "type", "")
            image_type = str(getattr(image_type, "value", image_type) or "").lower()
            if not image_type or image_type in {"thumb", "imagetype.thumb"}:
                return candidate
    return None


def _ma_image_url(entry: Any, mass: Any, item: Any, *, size: int = 256) -> str:
    """Resolve artwork from MA models, including Spotify ItemMapping thumbnails."""
    getter = getattr(mass, "get_media_item_image_url", None)
    if callable(getter):
        try:
            value = str(getter(item) or "").strip()
            if value:
                return value
        except Exception:  # noqa: BLE001 - optional client helper differs by version
            pass
    image = _ma_image_object(item)
    if image is None:
        return ""
    if isinstance(image, str):
        return image.strip()
    path = str(_ma_value(image, "path", "") or "").strip()
    proxy_id = str(_ma_value(image, "proxy_id", "") or "").strip()
    base = music_assistant_entry_url(entry)
    if proxy_id and base:
        return f"{base}/imageproxy/{quote(proxy_id, safe='')}?size={size}&fmt=jpg"
    if path.startswith(("http://", "https://")):
        return path
    if path.startswith("/") and base:
        return f"{base}{path}"
    return ""


def _ma_uri_parts(media_uri: str) -> tuple[str, str, str]:
    """Return provider, media type and item id from a canonical MA URI."""
    value = str(media_uri or "").strip()
    if "://" not in value:
        return "", "", ""
    parsed = urlsplit(value)
    provider = str(parsed.scheme or "").strip()
    media_type = str(parsed.netloc or "").strip().lower()
    item_id = unquote(str(parsed.path or "").lstrip("/"))
    return provider, media_type, item_id


def _ma_playlist_track_row(entry: Any, mass: Any, item: Any, position: int) -> dict[str, Any]:
    uri = str(_ma_value(item, "uri", "") or "").strip()
    provider = _item_provider(item)
    uri_provider = uri.split("://", 1)[0] if "://" in uri else provider
    return {
        "title": str(_ma_value(item, "name", "") or uri).strip(),
        "media_content_id": f"{FITNESS_MA_PREFIX}{quote(uri, safe='')}",
        "can_play": bool(uri),
        "can_expand": False,
        "thumbnail": _ma_image_url(entry, mass, item),
        "artist": _item_artist(item),
        "album": _item_album(item),
        "year": _item_year(item),
        "duration": _item_duration(item),
        "details": (_item_media_type(item) or "track").replace("_", " ").title(),
        "media_class": _item_media_type(item) or "track",
        "provider": uri_provider,
        "provider_instance": provider,
        "provider_name": uri_provider,
        "provider_origin": "Music Assistant" + (f" · {uri_provider}" if uri_provider else ""),
        "adapter_id": "music_assistant",
        "adapter_name": "Music Assistant",
        "playlist_position": int(position),
        "ma_uri": uri,
    }


def _ma_search_groups(results: Any) -> tuple[tuple[str, str], ...]:
    # SearchResults fields in current music-assistant-models. Duck-typing keeps
    # this custom integration tolerant of older/newer client versions.
    return (
        ("tracks", "track"),
        ("albums", "album"),
        ("artists", "artist"),
        ("playlists", "playlist"),
        ("radio", "radio"),
        ("podcasts", "podcast"),
        ("audiobooks", "audiobook"),
    )


class MusicAssistantMusicAdapter(MusicAdapter):
    """Search the selected Music Assistant server across configured sources."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: Any,
        *,
        entries: list[Any],
        selected_account_id: str = "",
        search_scopes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._mass = _mass_client(entry)
        account_options = tuple(
            (str(item.entry_id), str(item.title or "Music Assistant")) for item in entries
        )
        valid_ids = {item[0] for item in account_options}
        selected = (
            selected_account_id
            if selected_account_id in valid_ids
            else str(getattr(entry, "entry_id", "") or "")
        )
        searcher = getattr(getattr(self._mass, "music", None), "search", None)
        browser = getattr(getattr(self._mass, "music", None), "browse", None)
        self.info = MusicAdapterInfo(
            adapter_id="music_assistant",
            name="Music Assistant",
            icon="mdi:music-circle",
            can_search=callable(searcher),
            can_browse=callable(browser),
            account_setup="music_assistant",
            setup_hint=(
                "Searches the configured Music Assistant sources you choose and plays "
                "supported results natively in Fitness TV through a Sendspin browser player. "
                "Provider accounts remain owned by Music Assistant."
            ),
            setup_path=music_assistant_settings_url(entry) or music_assistant_setup_path(
                hass, entries, selected_account_id=selected, destination="settings"
            ),
            source="music_assistant",
            account_options=account_options,
            selected_account_id=selected,
            search_scopes=tuple(dict(item) for item in (search_scopes or [])),
        )

    @classmethod
    async def async_create(
        cls,
        hass: HomeAssistant,
        *,
        profile_options: dict[str, Any] | None = None,
        current_player_id: str = "",
    ) -> "MusicAssistantMusicAdapter | None":
        entries = music_assistant_entries(hass, loaded_only=True)
        if not entries:
            return None
        selected_account_id = str((profile_options or {}).get("account_id") or "").strip()
        entry = select_music_assistant_entry(entries, selected_account_id)
        if entry is None or _mass_client(entry) is None:
            return None
        scopes = await music_assistant_music_provider_scopes(
            entry, hass=hass, current_player_id=current_player_id
        )
        adapter = cls(
            hass,
            entry,
            entries=entries,
            selected_account_id=selected_account_id,
            search_scopes=scopes,
        )
        if not adapter.info.can_search and not adapter.info.can_browse:
            return None
        return adapter

    async def async_search(
        self,
        query: str,
        *,
        limit: int,
        scopes: list[str] | None = None,
        media_types: list[str] | None = None,
    ):
        searcher = getattr(getattr(self._mass, "music", None), "search", None)
        if not callable(searcher):
            return []
        limit = clamp_search_limit(limit)
        requested_scopes = [str(item).strip() for item in (scopes or []) if str(item).strip()]
        allowed_scopes = {
            str(item.get("id") or "")
            for item in self.info.search_scopes
            if item.get("available", True)
        }
        if requested_scopes:
            requested_scopes = [item for item in requested_scopes if item in allowed_scopes]
            if not requested_scopes:
                return []
        try:
            results = await searcher(
                str(query or "").strip(),
                limit=limit,
                providers=requested_scopes or None,
            )
        except TypeError:
            # Older MA client controllers did not expose the providers kwarg.
            # Prefer the raw command before falling back to an unscoped search.
            sender = getattr(self._mass, "send_command", None)
            if requested_scopes and callable(sender):
                results = await sender(
                    "music/search",
                    search_query=str(query or "").strip(),
                    limit=limit,
                    providers=requested_scopes,
                )
            else:
                results = await searcher(str(query or "").strip(), limit=limit)
        allowed_scope_domains = {
            str(scope.get("domain") or "").strip()
            for scope in self.info.search_scopes
            if str(scope.get("id") or "").strip() in requested_scopes
        }
        allowed_scope_tokens = set(requested_scopes) | {item for item in allowed_scope_domains if item}
        requested_media_types = (
            {str(item).strip().lower() for item in media_types if str(item).strip()}
            if media_types is not None
            else None
        )
        grouped_rows: list[list[dict[str, Any]]] = []
        for attr, fallback_type in _ma_search_groups(results):
            if requested_media_types is not None and fallback_type not in requested_media_types:
                continue
            group = (
                results.get(attr, []) if isinstance(results, dict)
                else getattr(results, attr, None) or []
            )
            type_rows: list[dict[str, Any]] = []
            for item in list(group or []):
                if _ma_value(item, "available", True) is False:
                    continue
                uri = str(_ma_value(item, "uri", "") or "").strip()
                title = str(_ma_value(item, "name", "") or uri).strip()
                if not uri or not title:
                    continue
                media_type = _item_media_type(item) or fallback_type
                if requested_media_types is not None and media_type not in requested_media_types:
                    continue
                provider = _item_provider(item)
                artist_value = _item_artist(item)
                album_value = _item_album(item)
                year_value = _item_year(item)
                duration_value = _item_duration(item)
                provider_tokens = _provider_tokens_from_object(item)
                if provider:
                    provider_tokens.add(provider)
                uri_provider = uri.split("://", 1)[0] if "://" in uri else ""
                if uri_provider:
                    provider_tokens.add(uri_provider)
                # MA versions/providers can occasionally return cross-provider matches
                # even for a scoped search. Enforce the user's selected provider
                # instances/domains again before exposing results in Fitness TV.
                if requested_scopes and provider_tokens.isdisjoint(allowed_scope_tokens):
                    continue
                thumbnail = _ma_image_url(self._entry, self._mass, item)
                provider_label = next(
                    (
                        str(scope.get("name") or "").strip()
                        for scope in self.info.search_scopes
                        if provider_tokens.intersection(
                            {
                                str(scope.get("id") or "").strip(),
                                str(scope.get("domain") or "").strip(),
                            }
                        )
                        and str(scope.get("name") or "").strip()
                    ),
                    provider,
                )
                provider_origin = " · ".join(
                    value for value in (self.info.name, provider_label) if value
                )
                media_type_label = media_type.replace("_", " ").title()
                icon = {
                    "album": "mdi:album",
                    "playlist": "mdi:playlist-music",
                    "artist": "mdi:account-music",
                    "radio": "mdi:radio",
                    "podcast": "mdi:podcast",
                    "audiobook": "mdi:book-music",
                }.get(media_type, "mdi:music-note")
                type_rows.append(
                    {
                        "title": title,
                        "media_content_id": f"{FITNESS_MA_PREFIX}{quote(uri, safe='')}",
                        # MA 2.9.x player_queues/play_media accepts collection URIs
                        # directly. Albums, playlists and artists therefore belong
                        # on the same native playback path as tracks and radio.
                        "can_play": media_type in {
                            "track", "album", "playlist", "artist",
                            "radio", "podcast", "audiobook",
                        },
                        "can_expand": False,
                        "thumbnail": thumbnail,
                        "artist": artist_value,
                        "album": album_value,
                        "year": year_value,
                        "duration": duration_value,
                        "details": media_type_label,
                        "media_class": media_type,
                        "icon": icon,
                        "provider": str(uri_provider or provider or "").strip(),
                        "provider_name": provider_label,
                        "provider_origin": provider_origin or self.info.name,
                        "provider_instance": provider,
                        "ma_uri": uri,
                        "adapter_id": self.info.adapter_id,
                        "adapter_name": self.info.name,
                    }
                )
            if type_rows:
                grouped_rows.append(type_rows)

        # Interleave result types instead of letting the first large track group
        # consume the whole per-adapter limit. This keeps albums/playlists visible
        # when several result-type checkboxes are enabled at the same time.
        rows: list[dict[str, Any]] = []
        while len(rows) < limit and any(grouped_rows):
            next_groups: list[list[dict[str, Any]]] = []
            for group in grouped_rows:
                if group and len(rows) < limit:
                    rows.append(group.pop(0))
                if group:
                    next_groups.append(group)
            grouped_rows = next_groups
        return rows
