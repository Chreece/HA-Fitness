"""Native Home Assistant Spotify adapter."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .base import MusicAdapter, MusicAdapterInfo


def _loaded_spotify_entries(hass: HomeAssistant) -> list[Any]:
    try:
        entries = hass.config_entries.async_entries("spotify")
    except Exception:  # noqa: BLE001
        return []
    result: list[Any] = []
    for entry in entries:
        state = getattr(entry, "state", None)
        if state not in (None, ConfigEntryState.LOADED) and str(state).lower() not in {"loaded", "configentrystate.loaded"}:
            continue
        result.append(entry)
    return result


class SpotifyMusicAdapter(MusicAdapter):
    """Expose installed Home Assistant Spotify account instances honestly."""

    def __init__(self, entries: list[Any], *, selected_account_id: str = "") -> None:
        account_options = tuple((str(entry.entry_id), str(entry.title or "Spotify")) for entry in entries)
        valid_ids = {item[0] for item in account_options}
        selected = selected_account_id if selected_account_id in valid_ids else (account_options[0][0] if len(account_options) == 1 else "")
        self.info = MusicAdapterInfo(
            adapter_id="spotify",
            name="Spotify",
            icon="mdi:spotify",
            can_search=False,
            can_browse=True,
            can_play_link=False,
            account_setup="home_assistant",
            setup_hint_key="music_adapter_spotify_hint",
            setup_path="/config/integrations/integration/spotify",
            source="spotify",
            account_options=account_options,
            selected_account_id=selected,
        )

    @classmethod
    async def async_create(
        cls, hass: HomeAssistant, *, profile_options: dict[str, Any] | None = None
    ) -> "SpotifyMusicAdapter | None":
        entries = _loaded_spotify_entries(hass)
        if not entries:
            return None
        selected_account_id = str((profile_options or {}).get("account_id") or "").strip()
        return cls(entries, selected_account_id=selected_account_id)

    async def async_search(self, query: str, *, limit: int, scopes: list[str] | None = None, media_types: list[str] | None = None):
        # HA's native Spotify integration currently exposes library browsing/control,
        # not a resolvable browser-audio search surface. Do not fake search support.
        return []
