from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_admin_and_other_modals_use_one_mobile_touch_scroll_owner():
    assert '.fitness-modal-scroll-region{box-sizing:border-box!important;display:block!important;flex:1 1 auto!important' in JS
    assert 'height:100dvh!important;' in JS
    assert '.fitness-modal-scroll-region>.access-admin-body' in JS
    assert 'const body = root.querySelector(".fitness-modal-scroll-region") || root.querySelector(".access-admin-body")' in JS
    assert 'const currentBody = root.querySelector(".fitness-modal-scroll-region") || root.querySelector(".access-admin-body")' in JS


def test_mobile_cards_have_real_spacing_without_changing_saved_desktop_layout():
    assert ':host(:not([fitness-cast-receiver])) .tv-grid{gap:12px!important' in JS
    assert ':host(:not([fitness-cast-receiver])) .tv-card-slot{margin:0!important}' in JS


def test_workout_map_keeps_route_visible_and_metrics_are_interactive():
    assert '<div class="map-shade"></div>' not in JS
    assert 'class="map-metrics map-metrics-left"' in JS
    assert 'class="map-metrics map-metrics-right"' in JS
    assert '.map-metrics{position:absolute;top:54px;bottom:24px;z-index:4' in JS
    assert '.map-metrics-left{left:8px}' in JS
    assert '.map-metrics-right{right:8px}' in JS
    assert 'pointer-events:auto' in JS
    assert "fact.setAttribute('role','button')" in JS
    assert "'.workout-map-tools,.map-metrics,.route-badge,.map-attribution'" in JS


def test_browser_device_resumes_dashboard_and_workout_selection_after_backgrounding():
    assert '_captureDashboardResumeState()' in JS
    assert '_restoreDashboardResumeState()' in JS
    assert 'fitness:dashboard-resume:' in JS
    assert 'document.addEventListener("visibilitychange", this._boundDashboardVisibility)' in JS
    assert 'window.addEventListener("pagehide", this._boundDashboardPageHide' in JS
    assert 'fitness:card-ui:' in JS
    assert '_fitnessCardUiSet(this,"selected_uid"' in JS


def test_motion_is_icons_only_on_browser_and_static_on_cast():
    assert 'if (FITNESS_TV_CAST_RECEIVER) return false;' in JS
    assert 'card.__fitnessLivingMode = this._motionEnabled() ? "movement-icons-only" : "static"' in JS
    assert '/heart|pulse|cardio|speedometer|gauge|run|walk|shoe|bike|bicycle|rowing|swim|motion|cadence|rotate/' in JS
    assert 'data-fitness-motion-lite' in JS
    assert 'data-fitness-cast-static' in JS
    assert ':host([fitness-cast-receiver]) .fitness-ambient-layer i{display:none!important;animation:none!important;transition:none!important;filter:none!important}' in JS


def test_cast_card_move_requires_edit_activation_and_wraps_on_edges():
    assert 'data-card-move-edit="1"' in JS
    assert '_setCastCardMoveMode(cardId = "")' in JS
    assert 'String(this._castLayoutMoveCardId || "") === cardId' in JS
    assert 'let wrapped = false;' in JS
    assert 'cross * 10000 + edge' in JS
    assert 'const insertAfter = wrapped ? ["left", "up"].includes(wanted)' in JS
