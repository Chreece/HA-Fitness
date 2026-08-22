from datetime import datetime, timezone
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fitness_history_v146", ROOT / "custom_components/fitness/history.py")
_history = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_history)
validate_series = _history.validate_series
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
REGISTRY = (ROOT / "custom_components/fitness/music/registry.py").read_text(encoding="utf-8")
YTDLP = (ROOT / "custom_components/fitness/music/yt_dlp.py").read_text(encoding="utf-8")
YTDLP_CORE = (ROOT / "custom_components/fitness/music_ytdlp.py").read_text(encoding="utf-8")
WELLNESS = (ROOT / "custom_components/fitness/providers/wellness.py").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")


def test_dashcast_only_exits_for_explicit_expired_cast_lease():
    assert 'Number(status||0)===410' in ACCOUNTS
    assert 'String(data?.error||"")==="cast_session_expired"' in ACCOUNTS
    assert '[401,403,404,410].includes' not in ACCOUNTS
    assert 'expireCastPortal(r.status,data)' in ACCOUNTS


def test_cast_picker_has_lightweight_live_target_status_polling():
    assert '"fitness/dashboard/cast_targets"' in DASH
    assert 'websocket_dashboard_cast_targets' in DASH
    assert '"fitness/dashboard/cast_targets": ("dashboard", "websocket_dashboard_cast_targets")' in ACCOUNTS
    assert 'type:"fitness/dashboard/cast_targets"' in FRONTEND
    assert '_fitnessStartCastTargetWatch(this, root, {overview:false, preferred})' in FRONTEND
    assert '_fitnessStartCastTargetWatch(this, root, {overview:true})' in FRONTEND
    assert 'target.available === false ? "disabled" : ""' in FRONTEND
    assert 'cast_available' in DASH


def test_music_search_action_is_next_to_query_field():
    assert 'class="music-search-query-row"' in FRONTEND
    assert '.music-search-query-row{display:grid' in FRONTEND
    form = FRONTEND[FRONTEND.index('<div class="music-search-form">'):FRONTEND.index('const adapters = await this._loadMusicAdapters()')]
    assert '<div class="modal-actions"><button class="primary-tool run-music-search"' not in form


def test_remote_sessions_do_not_expose_music_assistant():
    assert 'allow_music_assistant: bool = True' in REGISTRY
    assert 'if allow_music_assistant:' in REGISTRY
    assert 'allow_music_assistant = await _music_assistant_local_allowed(hass, connection)' in TV
    assert 'allow_music_assistant=allow_music_assistant' in TV
    assert '_require_local_music_assistant' in TV


def test_ytdlp_results_are_aac_only_and_network_probed_before_offer_or_playback():
    assert 'bestaudio[protocol=https][ext=m4a][acodec^=mp4a]' in YTDLP_CORE
    assert 'bestaudio[protocol=https][vcodec=none]' not in YTDLP_CORE
    assert '_async_probe_browser_audio' in YTDLP
    assert 'response.status not in {200, 206}' in YTDLP
    assert '_YTDLP_BROWSER_AUDIO_TYPES' in YTDLP
    assert 'if not await _async_probe_browser_audio(self._hass, resolved)' in YTDLP
    assert 'if not await _async_probe_browser_audio(hass, resolved)' in YTDLP


def test_newest_measurement_wins_even_over_stale_merged_current():
    now = datetime(2026, 8, 22, 19, 0, tzinfo=timezone.utc)
    points, _audit = validate_series(
        "steps",
        [
            {"timestamp": "2026-08-22T08:00:00+00:00", "value": 5000, "source_type": "fitness_merged_current", "imported": False},
            {"timestamp": "2026-08-22T18:30:00+00:00", "value": 8123, "source_type": "direct_garmin_health", "imported": True},
        ],
        now=now,
    )
    assert points[-1]["value"] == 8123
    assert points[-1]["source_type"] == "direct_garmin_health"


def test_integration_freshness_uses_measurement_or_last_changed_not_attribute_refresh_time():
    assert 'timestamp=_measurement_timestamp(state).isoformat()' in WELLNESS
    assert 'State.last_updated`` can move merely because attributes refreshed' in WELLNESS
    assert 'getattr(state, "last_changed", None)' in WELLNESS
    assert 'Never stamp a stale integration value with' in MANAGER
    assert 'return parse_timestamp(getattr(state, "last_changed", None))' in MANAGER
    assert 'return parse_timestamp(getattr(state, "last_changed", None)) or now' not in MANAGER
    assert 'raw_points.sort(key=lambda item: parse_timestamp(item.get("timestamp"))' in MANAGER


def test_v146_cache_busts_both_ha_and_portal_frontends():
    assert 'cast-ui-155' in DASH
    assert 'cast-ui-155' in ACCOUNTS
