from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import types

from conftest import FITNESS, install_homeassistant_stubs, load_module


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
TRANSLATIONS = (ROOT / "custom_components/fitness/dashboard_translations.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


install_homeassistant_stubs()
pkg = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
pkg.__path__ = [str(FITNESS.parent.parent)]
fitness_pkg = sys.modules.setdefault("custom_components.fitness", types.ModuleType("custom_components.fitness"))
fitness_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault("custom_components.fitness.providers", types.ModuleType("custom_components.fitness.providers"))
providers_pkg.__path__ = [str(FITNESS / "providers")]
adapters_pkg = sys.modules.setdefault(
    "custom_components.fitness.providers.sleep_adapters",
    types.ModuleType("custom_components.fitness.providers.sleep_adapters"),
)
adapters_pkg.__path__ = [str(FITNESS / "providers" / "sleep_adapters")]
load_module("custom_components.fitness.providers.sleep", "providers/sleep.py")
load_module(
    "custom_components.fitness.providers.sleep_adapters.registry_types",
    "providers/sleep_adapters/registry_types.py",
)
saa = load_module(
    "custom_components.fitness.providers.sleep_adapters.sleep_as_android",
    "providers/sleep_adapters/sleep_as_android.py",
)


def _event(at, event_type):
    return {"last_updated": at, "attributes": {"event_type": event_type}}


def test_sleep_as_android_does_not_guess_unobserved_prefix_as_sleep():
    start = datetime(2026, 8, 16, 22, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=8)
    phases = [
        _event(start + timedelta(minutes=30), "light_sleep"),
        _event(start + timedelta(hours=2, minutes=30), "awake"),
        _event(start + timedelta(hours=2, minutes=45), "rem"),
    ]
    record = saa.record_from_event_history(
        tracking_entity_id="event.sleep_tracking",
        phase_entity_id="event.sleep_phase",
        tracking_states=[_event(start, "started"), _event(end, "stopped")],
        phase_states=phases,
    )

    assert record is not None
    assert record.time_in_bed_s == 8 * 3600
    assert record.duration_s == 7.25 * 3600
    assert record.awake_s == 15 * 60
    provider = record.provider_values["sleep_as_android"]
    assert provider["unobserved_active_s"] == 30 * 60
    assert provider["duration_method"] == "classified_phase_intervals"


def test_sleep_as_android_tracking_only_session_remains_a_documented_fallback():
    start = datetime(2026, 8, 16, 22, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=7)
    record = saa.record_from_event_history(
        tracking_entity_id="event.sleep_tracking",
        phase_entity_id=None,
        tracking_states=[_event(start, "started"), _event(end, "stopped")],
        phase_states=[],
    )
    assert record is not None
    assert record.duration_s == record.time_in_bed_s == 7 * 3600
    assert record.provider_values["sleep_as_android"]["duration_method"] == "tracking_active_time_fallback"


def test_sleep_deficit_uses_local_wake_dates_and_refreshes_after_midnight():
    assert "today = now.astimezone(tz).date()" in MANAGER
    assert "first_date = today - timedelta(days=max(0, days - 1))" in MANAGER
    assert "first_date <= stamp.astimezone(tz).date() <= today" in MANAGER
    assert "async_track_time_change(" in MANAGER
    assert "self._handle_sleep_calendar_tick" in MANAGER
    assert "hour=0" in MANAGER and "minute=5" in MANAGER


def test_ytdlp_is_selectable_per_profile_without_forced_readdition_or_reload():
    assert 'adapter?.id !== "yt_dlp"' not in FRONTEND
    assert 'if (ytdlpEnabled && !musicAdapters.includes("yt_dlp"))' not in FRONTEND
    ytdlp = TV[TV.index("async def websocket_tv_music_ytdlp"):TV.index("def _selected_music_assistant_entry")]
    assert "get_live_runtime(hass).suppress_entry_reload_once(entry.entry_id)" in ytdlp
    assert "hass.config_entries.async_update_entry(entry, options=options)" in ytdlp


def test_cast_focus_navigation_and_tooltips_are_lightweight_and_localized():
    assert "_restoreCastRemotePreviousFocus()" in FRONTEND
    assert '["ArrowUp","ArrowDown"].includes(key)' in FRONTEND
    assert "_castRemoteSectionTrail.push(current)" in FRONTEND
    assert "_restoreCastRemoteFocusSnapshot(castFocusSnapshot)" in FRONTEND
    assert "_scheduleCastFocusTooltip(element)" in FRONTEND
    assert "_castElementHasVisibleText(element)" in FRONTEND
    assert "_positionCastFocusTooltip(tooltip, element)" in FRONTEND
    assert "FITNESS_TV_FOCUS_TOOLTIP_DELAY_MS = 1600" in FRONTEND
    assert "FITNESS_TV_FOCUS_TOOLTIP_VISIBLE_MS = 2600" in FRONTEND
    assert 'tooltip.dataset.placement = belowFits ? "below" : "above"' in FRONTEND
    assert 'this._castFocusTooltipDismissTimer = setTimeout' in FRONTEND
    assert 'this.shadowRoot.querySelectorAll(".tv-toolbar button[title]")' in FRONTEND
    assert 'button.removeAttribute("title")' in FRONTEND
    assert '--cast-tooltip-arrow-left' in FRONTEND
    assert 'bottom:22px' not in FRONTEND
    assert "cast_entity_details_hint" in FRONTEND
    assert "cast_progress_navigation_hint" in FRONTEND
    assert "filter = \"none\"" in FRONTEND
    for key in ("cast_entity_details_hint", "cast_progress_navigation_hint", "cast_top_bar", "cast_card"):
        assert f'"{key}"' in TRANSLATIONS


def test_cast_targets_and_buttons_remain_readable_and_safe():
    assert '${unavailable ? "disabled" : ""}' in FRONTEND
    assert 'class="add-profile-row overview-cast-target ${unavailable ? "unavailable" : ""}' in FRONTEND
    assert ".overview-cast-target.unavailable" in FRONTEND
    assert "font-size:clamp(10px" in FRONTEND
    assert "white-space:nowrap" in FRONTEND
    assert ".flow-home span{display:block!important}" in FRONTEND
    start = FRONTEND.index("const profileActions =")
    receiver_actions = FRONTEND[start:FRONTEND.index('].join("") : "")', start)]
    assert 'id="stop-cast"' not in receiver_actions


def test_empty_cards_and_recovery_bars_are_handled_on_tv_and_user_dashboards():
    assert "this.hidden = true;" in FRONTEND
    assert 'this.closest?.(".tv-card-slot")' in FRONTEND
    assert "hasAdaptationInformation" in FRONTEND
    assert "data-fitness-bar" in FRONTEND
    assert "setTimeout(() => this._syncCardGridSpan(card, wrapper), 140)" in FRONTEND


def test_readme_has_audience_hardware_support_disclaimer_and_two_images():
    for heading in (
        "## TL;DR",
        "## Who Fitness is for",
        "## What you need",
        "## Supported sources and sensors",
        "### Live sensor protocols",
    ):
        assert heading in README
    assert "assets/fitness-overview.png" in README
    assert "assets/fitness-data-flow.svg" in README
    assert "Health notice" in README
    assert (ROOT / "assets/fitness-data-flow.svg").is_file()
