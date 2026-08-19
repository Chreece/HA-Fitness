"""Security and performance regression contracts for the cumulative build."""

from pathlib import Path


ROOT = Path(__file__).parents[1] / "custom_components" / "fitness"
ACCESS = (ROOT / "access_control.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
REMOTE = (ROOT / "remote_gateway.py").read_text(encoding="utf-8")
TV = (ROOT / "tv_dashboard.py").read_text(encoding="utf-8")
CYCPLUS = (ROOT / "device_adapters" / "cycplus_m1.py").read_text(encoding="utf-8")
MUSIC = (ROOT / "music" / "registry.py").read_text(encoding="utf-8")
SAFETY = (ROOT / "resource_safety.py").read_text(encoding="utf-8")


def test_navigation_rejects_non_http_and_non_same_origin_targets() -> None:
    assert "const _fitnessSafeExternalUrl" in FRONTEND
    assert "const _fitnessSafeInternalTarget" in FRONTEND
    assert 'url.origin !== location.origin' in FRONTEND
    assert 'raw.startsWith("//")' in FRONTEND
    assert "window.location.href = target" not in FRONTEND
    assert "history.pushState(null, \"\", internalTarget)" in FRONTEND


def test_public_audio_proxy_rejects_private_egress_and_bounds_resources() -> None:
    assert "not address.is_global" in TV
    assert "socket.getaddrinfo(" in TV
    assert "allow_redirects=False" in TV
    assert "TV_PROXY_REDIRECT_LIMIT = 5" in TV
    assert "TV_PROXY_CONCURRENCY_LIMIT = 16" in TV
    assert "TV_SENDSPIN_CONCURRENCY_LIMIT = 16" in TV
    assert "_SAFE_PROXY_REQUEST_HEADERS" in TV
    assert "_RANGE_RE.fullmatch" in TV
    assert "allow_redirects=True" not in TV


def test_music_assistant_queue_ids_are_profile_and_account_owned() -> None:
    assert "def owns_ma_player(" in TV
    assert "def _require_owned_ma_player(" in TV
    for handler in (
        "websocket_tv_music_ma_play",
        "websocket_tv_music_ma_state",
        "websocket_tv_music_ma_seek",
        "websocket_tv_music_ma_queue",
    ):
        body = TV.split(f"async def {handler}", 1)[1].split(
            "@websocket_api.websocket_command", 1
        )[0]
        assert "_require_owned_ma_player(" in body
    assert "_FITNESS_MA_PLAYER_RE.fullmatch" in TV


def test_remote_sensor_identity_and_cast_origin_are_server_bounded() -> None:
    assert "REMOTE_BLE_IDENTITY_FIELDS" in REMOTE
    assert "clean_key not in REMOTE_BLE_IDENTITY_FIELDS" in REMOTE
    ant = REMOTE.split("async def websocket_remote_gateway_ant_packets", 1)[1].split(
        "async def websocket_remote_gateway_status", 1
    )[0]
    assert '"adapter_id": f"webusb:{gateway_id}"' in ant
    assert 'packet.get("adapter_id")' not in ant
    assert "def _https_origin(" in REMOTE
    assert "browser == client" in REMOTE


def test_websocket_payloads_and_access_mutations_are_bounded() -> None:
    assert "def bounded_payload(" in SAFETY
    assert "payload_too_complex" in SAFETY
    assert "payload_too_deep" in SAFETY
    assert "bounded_websocket_payload" in TV
    assert "bounded_websocket_payload" in REMOTE
    assert "bounded_websocket_payload" in DASHBOARD
    assert "self._load_lock = asyncio.Lock()" in ACCESS
    assert "self._mutation_lock = asyncio.Lock()" in ACCESS


def test_cycplus_catalogue_decode_and_persistence_have_hard_caps() -> None:
    assert "MAX_CATALOGUE_BYTES = 2 * 1024 * 1024" in CYCPLUS
    assert "MAX_CATALOGUE_FILES = 4_096" in CYCPLUS
    assert "MAX_FIT_SESSIONS = 64" in CYCPLUS
    assert "MAX_STORED_DEVICES = 64" in CYCPLUS
    extract = CYCPLUS.split("def extract_fit_filenames", 1)[1].split(
        "def parse_disk_space", 1
    )[0]
    assert "json.loads" not in extract
    assert "_FIT_FILENAME.finditer(text)" in extract
    assert "bisect_left" in CYCPLUS and "bisect_right" in CYCPLUS
    assert "self._sync_semaphore = asyncio.Semaphore(1)" in CYCPLUS
    assert "async with self._sync_semaphore" in CYCPLUS


def test_hot_frontend_and_music_search_paths_skip_redundant_work() -> None:
    assert "_fitnessStateSignature" in FRONTEND
    assert "if (signature === this._fitnessStateSignature) return" in FRONTEND
    assert "if (signature === this._ambientSignature) return" in FRONTEND
    assert "TV_MUSIC_SEARCH_CONCURRENCY_LIMIT = 4" in TV
    assert "begin_music_search" in TV
    assert "begin_music_resolution" in TV
    assert 'query = str(query or "").strip()[:256]' in MUSIC


def test_public_frontend_is_cached_and_translation_path_is_allowlisted() -> None:
    assert "self._frontend_body: bytes | None = None" in DASHBOARD
    assert "self._read_lock = asyncio.Lock()" in DASHBOARD
    assert "if language not in SUPPORTED_DASHBOARD_LANGUAGES" in DASHBOARD

