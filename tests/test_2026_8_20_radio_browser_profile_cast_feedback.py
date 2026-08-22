from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
BACKEND = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()


def test_dashboard_ambient_has_a_viewport_floor_without_turning_document_into_fixed_viewport():
    assert "_syncDashboardViewportFloor()" in FRONTEND
    assert '--fitness-dashboard-viewport-floor' in FRONTEND
    assert '--fitness-dashboard-host-top' in FRONTEND
    assert ':host(:not([fitness-cast-receiver])){min-height:max(var(--fitness-dashboard-viewport-floor,0px),calc(100dvh - var(--fitness-dashboard-host-top,0px)))!important' in FRONTEND
    assert ':host(:not([fitness-cast-receiver])) ha-card.tv-shell{min-height:max(var(--fitness-dashboard-viewport-floor,0px),calc(100dvh - var(--fitness-dashboard-host-top,0px)))!important' in FRONTEND
    assert ':host(:not([fitness-cast-receiver]))>.fitness-ambient-layer{position:fixed!important' in FRONTEND
    assert 'window.addEventListener("resize", this._boundViewportFloorSync' in FRONTEND
    assert 'visualViewport?.addEventListener?.("resize", this._boundViewportFloorSync' in FRONTEND


def test_radio_browser_source_requires_profile_enabled_adapter_on_frontend_and_backend():
    assert "await this._loadMusicAdapters()" in FRONTEND
    assert 'String(adapter?.id || adapter?.adapter_id || "") === "radio_browser"' in FRONTEND
    assert "adapter?.profile_enabled !== false" in FRONTEND
    assert '${radioEnabled ? `<button class="music-source" data-source="radio"' in FRONTEND
    assert "def _music_adapter_enabled_for_preferences" in BACKEND
    assert 'provider == "radio" and not _music_adapter_enabled_for_preferences(prefs, "radio_browser")' in BACKEND
    assert 'media_content_id.startswith(FITNESS_RADIO_PREFIX) and not _music_adapter_enabled_for_preferences(prefs, "radio_browser")' in BACKEND


def test_cast_media_browser_is_bounded_and_owns_its_scroll_region():
    assert ':host([fitness-cast-receiver]) .browser-modal{height:min(760px,calc(100dvh - 24px))!important' in FRONTEND
    assert '.browser-modal>.fitness-modal-scroll-region{flex:1 1 auto!important;min-height:0!important;height:auto!important;max-height:none!important;overflow-y:auto!important;overflow-x:hidden!important}' in FRONTEND
    assert ':host([fitness-cast-receiver]) .browser-modal .browser-head-actions' in FRONTEND


def test_slow_media_operations_show_shared_modal_progress_feedback():
    assert "_setModalTaskFeedback(message = \"\")" in FRONTEND
    assert 'className = "modal-task-feedback"' in FRONTEND
    assert 'card.setAttribute("aria-busy", "true")' in FRONTEND
    assert 'this._setModalTaskFeedback(`${l.loading} ${l.music_internet_radio}`.trim())' in FRONTEND
    assert 'this._setModalTaskFeedback(`${l.loading} ${l.media_browser}`.trim())' in FRONTEND
    assert 'this._setModalTaskFeedback(`${l.working} ${String(item.title || l.now_playing)}`.trim())' in FRONTEND


def test_radio_recovery_is_cancelable_and_pause_cleans_up_other_browser_players():
    assert "this._radioRecoveryGeneration = 0" in FRONTEND
    assert "this._radioRecoveryGeneration = Number(this._radioRecoveryGeneration || 0) + 1" in FRONTEND
    assert "const stillWanted = () => generation === Number(this._radioRecoveryGeneration || 0)" in FRONTEND
    assert "playbackAllowed && !playbackAllowed()" in FRONTEND
    assert 'if (["select","play"].includes(commandName)) {' in FRONTEND
    assert "this._cancelRadioRecovery();" in FRONTEND
    assert 'elif command_name in {"pause", "stop"}:' in BACKEND
    assert 'f"{command_name}_non_owner_cleanup"' in BACKEND
