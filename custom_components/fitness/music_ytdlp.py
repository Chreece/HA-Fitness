"""Optional yt-dlp powered YouTube search and audio resolution for Fitness TV."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import shutil
from typing import Any
from urllib.parse import quote_plus, urlparse

YTDLP_SEARCH_LIMIT = 50
YTDLP_SOCKET_TIMEOUT = 20
YOUTUBE_HOSTS = frozenset({
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
})


class FitnessYTDLPError(RuntimeError):
    """Raised when yt-dlp cannot provide a usable Fitness TV result."""


class FitnessYTDLPLiveStream(FitnessYTDLPError):
    """Raised when the target is an active YouTube live stream."""


@dataclass(slots=True)
class YTDLPResolvedAudio:
    """One browser-playable audio target returned by yt-dlp."""

    url: str
    title: str
    headers: dict[str, str]
    artist: str = ""
    thumbnail: str = ""
    duration: float | None = None


class _QuietLogger:
    """Collect the last yt-dlp warning/error without writing to HA stdout."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def debug(self, msg: str) -> None:
        return

    def info(self, msg: str) -> None:
        return

    def warning(self, msg: str) -> None:
        if msg:
            self.messages.append(str(msg))

    def error(self, msg: str) -> None:
        if msg:
            self.messages.append(str(msg))

    @property
    def last_message(self) -> str:
        return self.messages[-1] if self.messages else ""


def _yt_dlp_module():
    try:
        return importlib.import_module("yt_dlp")
    except ImportError as err:  # pragma: no cover - HA installs manifest requirement
        raise FitnessYTDLPError(
            "yt-dlp is not installed. Reload the Fitness integration after Home Assistant installs its requirements."
        ) from err


def _js_runtimes() -> tuple[dict[str, dict[str, str]], str | None]:
    """Return yt-dlp JS runtime configuration and the detected runtime name."""
    # Prefer an existing host runtime first. This lets advanced users keep using
    # their system Deno/Node/QuickJS/Bun without Fitness changing anything.
    for name, executables in (
        ("deno", ("deno",)),
        ("node", ("node",)),
        ("quickjs", ("qjs", "quickjs")),
        ("bun", ("bun",)),
    ):
        for executable in executables:
            path = shutil.which(executable)
            if path:
                return {name: {"path": path}}, name

    # Some Python environments may already provide the official Deno PyPI
    # wrapper. It is optional here because Home Assistant's Alpine/musl image
    # cannot install Deno's manylinux-only binary wheel as a requirement.
    try:
        deno_module = importlib.import_module("deno")
        finder = getattr(deno_module, "find_deno_bin", None)
        path = str(finder() if callable(finder) else "").strip()
        if path:
            return {"deno": {"path": path}}, "deno_managed"
    except (ImportError, OSError, RuntimeError):
        pass

    # Home Assistant installs nodejs-wheel for Fitness. Unlike the Deno PyPI
    # distribution, its binary dependency publishes both musllinux and
    # manylinux wheels for x86_64 and aarch64. The package installs a normal
    # `node` console command into the Python environment. Prefer PATH, then the
    # directory beside the active Python executable in case HA's launcher PATH
    # is unusually narrow.
    try:
        importlib.import_module("nodejs_wheel")
        path = shutil.which("node")
        if not path:
            import sys
            from pathlib import Path

            executable = "node.exe" if sys.platform == "win32" else "node"
            candidate = Path(sys.executable).resolve().parent / executable
            if candidate.is_file():
                path = str(candidate)
        if path:
            return {"node": {"path": path}}, "node_managed"
    except (ImportError, OSError, RuntimeError):
        pass
    return {}, None


def runtime_status() -> dict[str, Any]:
    """Return non-sensitive runtime capability information for the UI."""
    _, runtime = _js_runtimes()
    return {
        "available": runtime is not None,
        "runtime": runtime,
        "managed": runtime in {"deno_managed", "node_managed"},
    }


def _validated_youtube_target(target: str) -> str:
    """Return one allowed public YouTube URL or raise a user-facing error."""
    target = str(target or "").strip()
    if not target:
        raise FitnessYTDLPError("Missing YouTube target")
    parsed = urlparse(target)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or host not in YOUTUBE_HOSTS:
        raise FitnessYTDLPError("Only YouTube and YouTube Music URLs are accepted by the native yt-dlp player")
    return target


def _base_options(logger: _QuietLogger) -> dict[str, Any]:
    runtimes, _runtime = _js_runtimes()
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "logger": logger,
        "skip_download": True,
        "socket_timeout": YTDLP_SOCKET_TIMEOUT,
        "noplaylist": True,
        # Never load user/system yt-dlp config inside Home Assistant. Fitness
        # should be deterministic and must not unexpectedly consume credentials,
        # cookies, output templates, proxies or post-processors from host config.
        "ignoreconfig": True,
    }
    if runtimes:
        options["js_runtimes"] = runtimes
    return options


def _duration_label(seconds: Any) -> str:
    try:
        total = max(0, int(seconds or 0))
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def search_youtube(query: str, limit: int = YTDLP_SEARCH_LIMIT) -> list[dict[str, Any]]:
    """Search YouTube with yt-dlp and return the requested number of results."""
    query = str(query or "").strip()
    try:
        limit = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        limit = YTDLP_SEARCH_LIMIT
    if not query:
        return []

    yt_dlp = _yt_dlp_module()
    logger = _QuietLogger()
    options = _base_options(logger)
    # Flat extraction is intentional: search should be fast and should not
    # resolve fifty expiring media streams. The selected result is resolved later.
    options.update({"extract_flat": True, "playlistend": limit})

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(
                f"ytsearch{limit}:{query}",
                download=False,
            )
    except Exception as err:  # noqa: BLE001 - third-party extractor boundary
        detail = logger.last_message or str(err)
        raise FitnessYTDLPError(f"YouTube search failed: {detail}") from err

    entries = info.get("entries") if isinstance(info, dict) else None
    results: list[dict[str, Any]] = []
    for raw in entries if isinstance(entries, list) else []:
        if not isinstance(raw, dict):
            continue
        video_id = str(raw.get("id") or "").strip()
        title = str(raw.get("title") or "").strip()
        webpage_url = str(raw.get("webpage_url") or raw.get("url") or "").strip()
        if webpage_url and not webpage_url.startswith(("http://", "https://")):
            webpage_url = ""
        if not webpage_url and video_id:
            webpage_url = f"https://www.youtube.com/watch?v={video_id}"
        if not webpage_url or not title:
            continue
        uploader = str(
            raw.get("channel") or raw.get("uploader") or raw.get("uploader_id") or ""
        ).strip()
        duration_seconds = raw.get("duration")
        duration = _duration_label(duration_seconds)
        details = " · ".join(part for part in (uploader, duration) if part)
        album = str(raw.get("album") or "").strip()
        year_value = raw.get("release_year") or raw.get("release_date") or raw.get("upload_date") or ""
        year_text = str(year_value or "").strip()
        year = int(year_text[:4]) if len(year_text) >= 4 and year_text[:4].isdigit() else None
        thumbnail = str(raw.get("thumbnail") or "").strip()
        if not thumbnail:
            thumbnails = raw.get("thumbnails")
            if isinstance(thumbnails, list):
                for candidate in reversed(thumbnails):
                    if isinstance(candidate, dict) and candidate.get("url"):
                        thumbnail = str(candidate["url"])
                        break
        live_status = str(raw.get("live_status") or "").strip().lower()
        is_live = bool(raw.get("is_live")) or live_status == "is_live"
        is_upcoming = live_status == "is_upcoming"
        # Upcoming streams are not playable yet. Active live streams are kept
        # and routed through the YouTube player rather than the direct-audio
        # proxy, which intentionally rejects segmented live manifests.
        if is_upcoming:
            continue
        if is_live:
            details = " · ".join(part for part in (uploader, "LIVE") if part)
        results.append(
            {
                "title": title,
                "url": webpage_url,
                "thumbnail": thumbnail,
                "artist": uploader,
                "album": album,
                "year": year,
                "duration": float(duration_seconds) if isinstance(duration_seconds, (int, float)) else None,
                "details": details,
                "is_live": is_live,
                "live_status": live_status,
            }
        )
        if len(results) >= limit:
            break
    return results



def search_youtube_playlists(query: str, limit: int = YTDLP_SEARCH_LIMIT) -> list[dict[str, Any]]:
    """Search YouTube's playlist-only result filter with yt-dlp.

    yt-dlp's YoutubeSearchURL extractor understands the normal YouTube results
    URL with the playlist-only filter.  Keep extraction flat so a search does
    not recursively resolve every track in every returned playlist.
    """
    query = str(query or "").strip()
    try:
        limit = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        limit = YTDLP_SEARCH_LIMIT
    if not query:
        return []

    yt_dlp = _yt_dlp_module()
    logger = _QuietLogger()
    options = _base_options(logger)
    options.update({"extract_flat": True, "playlistend": limit, "noplaylist": False})
    search_url = (
        "https://www.youtube.com/results?search_query="
        f"{quote_plus(query)}&sp=EgIQAw%253D%253D"
    )
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(search_url, download=False)
    except Exception as err:  # noqa: BLE001 - third-party extractor boundary
        detail = logger.last_message or str(err)
        raise FitnessYTDLPError(f"YouTube playlist search failed: {detail}") from err

    entries = info.get("entries") if isinstance(info, dict) else None
    results: list[dict[str, Any]] = []
    for raw in entries if isinstance(entries, list) else []:
        if not isinstance(raw, dict):
            continue
        playlist_id = str(raw.get("id") or "").strip()
        title = str(raw.get("title") or "").strip()
        url = str(raw.get("webpage_url") or raw.get("url") or "").strip()
        if url and not url.startswith(("http://", "https://")):
            url = ""
        if not url and playlist_id:
            url = f"https://www.youtube.com/playlist?list={playlist_id}"
        if not url or not title:
            continue
        owner = str(raw.get("channel") or raw.get("uploader") or raw.get("uploader_id") or "").strip()
        thumbnail = str(raw.get("thumbnail") or "").strip()
        thumbnails = raw.get("thumbnails")
        if not thumbnail and isinstance(thumbnails, list):
            for candidate in reversed(thumbnails):
                if isinstance(candidate, dict) and candidate.get("url"):
                    thumbnail = str(candidate["url"])
                    break
        results.append({
            "title": title,
            "url": url,
            "thumbnail": thumbnail,
            "artist": owner,
            "album": "",
            "year": None,
            "duration": None,
            "details": "YouTube playlist",
            "playlist_id": playlist_id,
        })
        if len(results) >= limit:
            break
    return results


def list_youtube_playlist_entries(target: str, limit: int = 100) -> list[dict[str, Any]]:
    """Return flat playlist entries without resolving media streams.

    Playback resolution is deliberately a second step so inaccessible/deleted
    entries can be discarded independently instead of poisoning the whole
    playlist.
    """
    target = _validated_youtube_target(target)
    try:
        limit = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        limit = 100
    yt_dlp = _yt_dlp_module()
    logger = _QuietLogger()
    options = _base_options(logger)
    options.update({"extract_flat": True, "playlistend": limit, "noplaylist": False})
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(target, download=False)
    except Exception as err:  # noqa: BLE001 - third-party extractor boundary
        detail = logger.last_message or str(err)
        raise FitnessYTDLPError(f"YouTube playlist extraction failed: {detail}") from err
    entries = info.get("entries") if isinstance(info, dict) else None
    rows: list[dict[str, Any]] = []
    for raw in entries if isinstance(entries, list) else []:
        if not isinstance(raw, dict):
            continue
        video_id = str(raw.get("id") or "").strip()
        url = str(raw.get("webpage_url") or raw.get("url") or "").strip()
        if url and not url.startswith(("http://", "https://")):
            url = ""
        if not url and video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
        title = str(raw.get("title") or "").strip()
        if not url or not title:
            continue
        live_status = str(raw.get("live_status") or "").strip().lower()
        if bool(raw.get("is_live")) or live_status in {"is_live", "is_upcoming"}:
            # Fitness' direct browser-audio path intentionally excludes live
            # and upcoming items from yt-dlp playlists.
            continue
        rows.append({
            "title": title,
            "url": url,
            "artist": str(raw.get("channel") or raw.get("uploader") or "").strip(),
            "thumbnail": str(raw.get("thumbnail") or "").strip(),
            "duration": raw.get("duration"),
        })
        if len(rows) >= limit:
            break
    return rows

def _selected_download(info: dict[str, Any]) -> dict[str, Any]:
    """Return the selected direct media dictionary produced by yt-dlp."""
    url = str(info.get("url") or "").strip()
    if url:
        return info
    requested = info.get("requested_downloads")
    if isinstance(requested, list):
        for item in requested:
            if isinstance(item, dict) and str(item.get("url") or "").strip():
                return item
    return info


def resolve_youtube_audio(target: str) -> YTDLPResolvedAudio:
    """Resolve one YouTube URL to a fresh direct audio URL plus required headers."""
    target = _validated_youtube_target(target)

    yt_dlp = _yt_dlp_module()
    logger = _QuietLogger()
    options = _base_options(logger)
    options.update(
        {
            # Prefer a direct HTTPS audio stream because Fitness proxies it
            # through HA. HLS/DASH manifests can reference additional segment
            # URLs and are much less reliable in browser/Cast playback.
            "format": "bestaudio[protocol=https][ext=m4a][acodec^=mp4a]/bestaudio[protocol=https][ext=m4a]",
        }
    )

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            raw = ydl.extract_info(target, download=False)
            if isinstance(raw, dict) and (
                bool(raw.get("is_live"))
                or str(raw.get("live_status") or "").lower() == "is_live"
            ):
                raise FitnessYTDLPLiveStream(
                    "Active YouTube live streams use the YouTube player instead of the direct audio proxy"
                )
            info = ydl.sanitize_info(raw)
    except FitnessYTDLPLiveStream:
        raise
    except Exception as err:  # noqa: BLE001 - third-party extractor boundary
        detail = logger.last_message or str(err)
        raise FitnessYTDLPError(f"YouTube audio resolution failed: {detail}") from err

    if not isinstance(info, dict):
        raise FitnessYTDLPError("yt-dlp returned no usable media information")
    selected = _selected_download(info)
    url = str(selected.get("url") or "").strip()
    protocol = str(selected.get("protocol") or info.get("protocol") or "").lower()
    if not url.startswith(("http://", "https://")):
        raise FitnessYTDLPError("yt-dlp did not return a direct playable audio URL")
    if any(token in protocol for token in ("m3u8", "dash", "ism")):
        raise FitnessYTDLPError("yt-dlp selected a segmented stream that Fitness cannot proxy reliably")
    ext = str(selected.get("ext") or info.get("ext") or "").lower()
    acodec = str(selected.get("acodec") or info.get("acodec") or "").lower()
    if ext not in {"m4a", "mp4"} or (acodec and not acodec.startswith("mp4a")):
        raise FitnessYTDLPError("yt-dlp did not return browser-safe AAC/M4A audio")

    headers_raw = selected.get("http_headers") or info.get("http_headers") or {}
    headers = {
        str(key): str(value)
        for key, value in headers_raw.items()
        if isinstance(key, str)
        and isinstance(value, (str, int, float))
        and key.lower() not in {"cookie", "authorization"}
    } if isinstance(headers_raw, dict) else {}
    title = str(info.get("title") or target).strip()
    artist = str(
        info.get("artist")
        or info.get("channel")
        or info.get("uploader")
        or info.get("creator")
        or ""
    ).strip()
    thumbnail = str(info.get("thumbnail") or "").strip()
    duration_raw = info.get("duration")
    try:
        duration = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration = None
    return YTDLPResolvedAudio(
        url=url,
        title=title,
        headers=headers,
        artist=artist,
        thumbnail=thumbnail,
        duration=duration,
    )
