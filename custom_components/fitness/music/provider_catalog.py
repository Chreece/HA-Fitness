"""Install/configure catalogue kept separate from active Fitness music adapters."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .yt_dlp import YTDLPMusicAdapter

from .music_assistant import (
    MUSIC_ASSISTANT_INSTALL_URL,
    music_assistant_entries,
    music_assistant_music_provider_instances,
    music_assistant_music_provider_manifests,
    music_assistant_add_provider_url,
    music_assistant_edit_provider_url,
    music_assistant_is_addon,
    music_assistant_settings_url,
    music_assistant_provider_url,
    music_assistant_setup_path,
    select_music_assistant_entry,
)

# Music Assistant source shortcuts are *not* Fitness adapters.  They are links into
# the selected MA server so the user can configure a source there.  Music Assistant
# remains one adapter in Fitness regardless of how many MA sources/accounts exist.
#
# This tuple is only an icon/name fallback. Connected MA servers are queried live
# through providers/manifests so newly added/removed music sources follow MA itself.
# Provider code being Apache-2.0 does not by itself grant permission to use a third-
# party streaming service outside its own terms/API rules, so Fitness does not copy
# these providers natively just because their implementation is open source.
_MUSIC_ASSISTANT_SOURCE_SHORTCUTS: tuple[tuple[str, str, str], ...] = (
    ("apple_music", "Apple Music", "mdi:apple"),
    ("ard_audiothek", "ARD Sounds / Audiothek", "mdi:radio"),
    ("audible", "Audible", "mdi:book-music"),
    ("audiobookshelf", "Audiobookshelf", "mdi:bookshelf"),
    ("bandcamp", "Bandcamp", "mdi:music-box"),
    ("bbc_sounds", "BBC Sounds", "mdi:radio"),
    ("deezer", "Deezer", "mdi:music-circle"),
    ("digitally_incorporated", "DI.fm Network", "mdi:radio-tower"),
    ("emby", "Emby", "mdi:play-network"),
    ("gpodder", "gPodder", "mdi:podcast"),
    ("ibroadcast", "iBroadcast", "mdi:cloud-music"),
    ("internet_archive", "Internet Archive", "mdi:archive-music"),
    ("itunes_podcasts", "iTunes Podcast Search", "mdi:podcast"),
    ("jellyfin", "Jellyfin", "mdi:jellyfish"),
    ("kion_music", "KION Music", "mdi:music-circle"),
    ("filesystem_local", "Local Files", "mdi:folder-music"),
    ("musicme", "MusicMe", "mdi:music-circle"),
    ("neteasecloudmusic", "NetEase Cloud Music", "mdi:cloud-music"),
    ("nicovideo", "Nico Nico Video", "mdi:video-music"),
    ("nugs", "Nugs.net", "mdi:music-circle"),
    ("nts", "NTS Radio", "mdi:radio"),
    ("opensubsonic", "OpenSubsonic / Subsonic", "mdi:server"),
    ("orf_radiothek", "ORF Radiothek", "mdi:radio"),
    ("pandora", "Pandora", "mdi:music-circle"),
    ("phishin", "Phish.in", "mdi:music-circle"),
    ("plex", "Plex", "mdi:plex"),
    ("podcast_index", "Podcast Index", "mdi:podcast"),
    ("podcastfeed", "Podcast RSS Feed", "mdi:rss"),
    ("qobuz", "Qobuz", "mdi:music-circle"),
    ("qqmusic", "QQ Music", "mdi:music-circle"),
    ("radiobrowser", "Radio Browser", "mdi:radio-tower"),
    ("radioparadise", "Radio Paradise", "mdi:radio"),
    ("siriusxm", "SiriusXM", "mdi:satellite-uplink"),
    ("somafm", "SomaFM Radio", "mdi:radio"),
    ("soundcloud", "SoundCloud", "mdi:soundcloud"),
    ("spotify", "Spotify", "mdi:spotify"),
    ("tidal", "Tidal", "mdi:music-circle"),
    ("tunein", "TuneIn", "mdi:radio"),
    ("yandex_music", "Yandex Music", "mdi:music-circle"),
    ("yousee_music", "YouSee Musik", "mdi:music-circle"),
    ("ytmusic", "YouTube Music", "mdi:youtube"),
    ("zvuk", "Zvuk Music", "mdi:music-circle"),
)



def _music_assistant_provider_destination(entry: Any, provider_id: str, instance_ids: list[str]) -> str:
    """Deep-link directly to edit or add one MA music provider."""
    if entry is None:
        return ""
    if len(instance_ids) == 1:
        return music_assistant_edit_provider_url(entry, instance_ids[0])
    return music_assistant_add_provider_url(entry, provider_id)


async def async_provider_catalog(
    hass: HomeAssistant,
    *,
    adapter_options: dict[str, dict[str, Any]] | None = None,
    ytdlp_enabled: bool = False,
) -> list[dict[str, Any]]:
    """Return explicit setup choices; never mix them into installed adapters."""
    entries = music_assistant_entries(hass, loaded_only=True)
    ma_installed = bool(entries)
    selected_account_id = str(
        ((adapter_options or {}).get("music_assistant") or {}).get("account_id") or ""
    ).strip()
    selected_entry = select_music_assistant_entry(entries, selected_account_id)
    provider_page = (
        music_assistant_provider_url(selected_entry)
        if selected_entry is not None
        else ""
    )
    ma_settings_path = (
        music_assistant_settings_url(selected_entry)
        if selected_entry is not None
        else music_assistant_setup_path(
            hass, entries, selected_account_id=selected_account_id, destination="settings"
        )
    )
    ma_path = provider_page or music_assistant_setup_path(
        hass, entries, selected_account_id=selected_account_id, destination="providers"
    )
    ma_instances = (
        await music_assistant_music_provider_instances(selected_entry)
        if selected_entry is not None
        else {}
    )

    rows: list[dict[str, Any]] = [
        {
            "id": "yt_dlp",
            "name": "yt-dlp",
            "icon": "mdi:youtube",
            "installed": YTDLPMusicAdapter.available(),
            "enabled": bool(ytdlp_enabled),
            "setup_path": "",
            "description_key": "ytdlp_disclaimer",
            "kind": "fitness_optional_adapter",
            "external": False,
            "requires_acknowledgement": True,
        },
        {
            "id": "music_assistant",
            "name": "Music Assistant",
            "icon": "mdi:music-circle",
            "installed": ma_installed,
            "setup_path": ma_settings_path if ma_installed else MUSIC_ASSISTANT_INSTALL_URL,
            "description_key": (
                "music_provider_ma_installed_description"
                if ma_installed
                else "music_provider_ma_install_description"
            ),
            "kind": "adapter",
            "external": bool((ma_settings_path if ma_installed else MUSIC_ASSISTANT_INSTALL_URL).startswith(("http://", "https://"))),
        },
    ]

    # Do not show dozens of unavailable MA sources when MA itself is not installed.
    if not ma_installed or not ma_path:
        return rows

    manifests = await music_assistant_music_provider_manifests(selected_entry)
    static_by_id = {
        provider_id: {"name": display_name, "icon": icon}
        for provider_id, display_name, icon in _MUSIC_ASSISTANT_SOURCE_SHORTCUTS
    }
    if manifests:
        source_rows = [
            (
                item["domain"],
                item.get("name") or static_by_id.get(item["domain"], {}).get("name") or item["domain"],
                item.get("icon") or static_by_id.get(item["domain"], {}).get("icon") or "mdi:music-circle",
            )
            for item in manifests
        ]
    else:
        # Compatibility fallback for an older/offline MA client.  When connected,
        # the live providers/manifests response above is authoritative.
        source_rows = [
            (provider_id, display_name, icon)
            for provider_id, display_name, icon in _MUSIC_ASSISTANT_SOURCE_SHORTCUTS
        ]

    for provider_id, display_name, icon in source_rows:
        instance_ids = list(ma_instances.get(provider_id) or [])
        provider_destination = _music_assistant_provider_destination(
            selected_entry, provider_id, instance_ids
        )
        rows.append(
            {
                "id": f"music_assistant_source:{provider_id}",
                "name": display_name,
                "provider_name": display_name,
                "icon": icon if str(icon).startswith("mdi:") else "mdi:music-circle",
                "installed": bool(instance_ids),
                "setup_path": provider_destination or ma_path,
                "description_key": (
                    "music_provider_configured_description"
                    if instance_ids
                    else "music_provider_setup_description"
                ),
                "configured": bool(instance_ids),
                "kind": "provider_source",
                "external": (provider_destination or ma_path).startswith(("http://", "https://")),
                "provider_domain": provider_id,
                "provider_instances": instance_ids,
            }
        )

    return rows
