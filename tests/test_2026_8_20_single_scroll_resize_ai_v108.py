from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()


def test_v108_cache_is_synchronized():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert '?v=unreleased-138' in DASHBOARD
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS


def test_dashboard_claims_one_ha_scroll_owner_and_restores_outer_scroll():
    assert "_claimDashboardScrollOwner()" in FRONTEND
    assert "_releaseDashboardScrollOwner()" in FRONTEND
    assert 'element.style.overflowY = "hidden"' not in FRONTEND
    assert 'scrollbarWidth = "none"' in FRONTEND
    assert "this._dashboardScrollOwner = owner" in FRONTEND
    assert 'this.hasAttribute("fitness-public-portal")' in FRONTEND


def test_card_layout_is_persisted_server_side():
    assert "_sanitize_card_layout" in TV
    assert 'vol.Optional("card_layout")' in TV
    assert 'card_layout=dict(msg["card_layout"])' in TV
    assert 'row["layout"] = self._sanitize_card_layout(card_layout)' in TV


def test_resize_persists_precise_width_and_content_aware_height():
    assert "width_percent" in FRONTEND
    assert "resizeWidthPercent" in FRONTEND
    assert "contentAwareHeight" in FRONTEND
    assert "fitness-user-sized" in FRONTEND
    assert "--fitness-user-card-min-height" in FRONTEND
    assert "packUnits = 200" in FRONTEND


def test_every_editable_card_has_reset_to_best_size():
    assert 'class="card-reset-size"' in FRONTEND
    assert "_resetCardSize(item.id)" in FRONTEND
    assert "mdi:fit-to-screen-outline" in FRONTEND


def test_today_ai_shows_steps_without_opening_more_info():
    assert "const structured=!rest&&device" in FRONTEND
    assert "_fitnessWorkoutPrescriptionMarkup(device,this._profile,this._hass)" in FRONTEND
    assert "calculation_basis_text" in FRONTEND
    assert "const restReason=rest&&plan.rationale" in FRONTEND
    assert "const actionButtons=[]" in FRONTEND
    assert "if(canControl&&!rest&&device)" in FRONTEND
