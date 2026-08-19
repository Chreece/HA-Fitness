from pathlib import Path

ROOT = Path(__file__).parents[1]
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()

def test_accounts_modal_has_bounded_load_and_backend_auth_timeout():
    assert 'fitness_accounts_timeout' in JS
    assert 'setTimeout(() => reject(new Error("fitness_accounts_timeout")), 12000)' in JS
    assert 'asyncio.wait_for(self.hass.auth.async_get_users(), timeout=8.0)' in ACCESS

def test_admin_can_set_default_three_dashboard_limit():
    assert 'DEFAULT_DASHBOARD_MAX = 3' in ACCESS
    assert '"dashboard_max": DEFAULT_DASHBOARD_MAX' in ACCESS
    assert 'vol.Optional("dashboard_max")' in ACCESS
    assert 'id="access-dashboard-max"' in JS

def test_tv_preferences_migrate_single_dashboard_and_support_multi_dashboard_actions():
    assert 'def _sanitize_dashboards' in TV
    assert '"id": "main", "name": DEFAULT_DASHBOARD_NAME' in TV
    assert '"fitness/tv/dashboard/manage"' in TV
    assert '{"create", "rename", "delete", "select"}' in TV

def test_frontend_dashboard_management_uses_modal_not_persistent_strip():
    assert '${this._dashboardStripMarkup()}' not in JS
    assert 'id="dashboards"' in JS
    assert '_openDashboardManager()' in JS
    assert 'data-dashboard-select' in JS
    assert 'data-dashboard-rename' in JS
    assert 'data-dashboard-delete' in JS
    assert 'id="dashboard-manager-auto"' in JS


def test_dashboard_layout_and_active_dashboard_survive_store_sanitization():
    assert 'result["dashboards"] = dashboards' in TV
    assert 'result["active_dashboard_id"] = active_dashboard_id' in TV
    assert '"layout": cls._sanitize_card_layout(item.get("layout"))' in TV
    assert 'card_layout' in TV


def test_accounts_modal_declares_preview_state_before_close_handlers():
    setup_modal = JS[JS.index('class FitnessTvSetupCard'):]
    modal = setup_modal[setup_modal.index('_modal(content)'):setup_modal.index('_openBackendFlow', setup_modal.index('_modal(content)'))]
    assert 'const cardPickerPreview =' in modal
    assert 'root.querySelector(".modal-close")?.addEventListener' in modal

def test_card_saves_are_scoped_to_active_dashboard():
    assert 'dashboard_id:String(this._activeDashboardId || "main")' in JS
    assert 'dashboard_id=msg.get("dashboard_id")' in TV
