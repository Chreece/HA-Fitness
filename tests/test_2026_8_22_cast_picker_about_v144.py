from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
TRANS = (ROOT / "custom_components/fitness/dashboard_translations.py").read_text(encoding="utf-8")


def test_browser_tv_off_target_is_selectable_but_send_action_is_disabled():
    launch_targets = DASH[DASH.index("def _tv_browser_launch_targets") : DASH.index("def _validated_browser_receiver_origin")]
    assert 'state.state not in {"unavailable", "unknown", "off"}' in launch_targets
    assert 'data-available="${target?.available === false ? "0" : "1"}"' in JS
    assert '${unavailable ? "disabled" : ""}' not in JS[JS.index("  _smartTvBrowserSection(l, {overview=false} = {})") : JS.index("  async _createSmartTvReceiver", JS.index("  _smartTvBrowserSection(l, {overview=false} = {})"))]
    helper = JS[JS.index("const _fitnessSmartTvLaunchSelection") : JS.index("const _fitnessMusicAdapterHint")]
    assert "const manual = !selection;" in helper
    assert "const targetAvailable = manual || Boolean(target?.available);" in helper
    assert "const available = cast.connected || (!cast.busy && targetAvailable);" in helper
    assert "button.disabled = cast.connecting || (!cast.connected && !targetAvailable);" in helper
    assert 'manual ? "mdi:link-variant-plus" : "mdi:open-in-new"' in helper
    assert "labels?.smart_tv_send_link" in helper
    assert '"smart_tv_send_link"' in TRANS


def test_automatic_browser_tv_send_never_exposes_manual_link_and_failed_ticket_is_revoked():
    receiver = DASH[DASH.index("async def websocket_tv_browser_receiver") : DASH.index("async def websocket_tv_overview_heartbeat")]
    assert "if not launch_succeeded:" in receiver
    assert "account_controller.revoke_cast_sessions(" in receiver
    assert "target_entity_id=target_key" in receiver
    frontend = JS[JS.index("  async _createSmartTvReceiver(root, {overview=false} = {})") : JS.index("  async _openCastPicker()")]
    assert "if (launch.manual)" in frontend
    assert "if (box) box.hidden = false;" in frontend
    assert "Automatic launch is a send action, not a link-generation workflow." in frontend
    assert "if (box) box.hidden = true;" in frontend
    assert "smart_tv_send_failed" in frontend


def test_profile_ha_cast_section_has_exactly_one_semantic_stop_control_while_busy():
    update = JS[JS.index("  _updateMediaControls(error = false)") : JS.index("  _style()", JS.index("  _updateMediaControls(error = false)"))]
    assert 'const castConnected = this._castState === "connected";' in update
    assert 'const castPending = this._castState === "connecting";' in update
    assert "modalHaStart.hidden = false;" in update
    assert "modalHaStart.disabled = castPending || (!castConnected" in update
    assert "if (modalHaStop) { modalHaStop.hidden = true; modalHaStop.disabled = true; }" in update
    cast_start = JS[JS.index("  async _castDashboard(entityId)") : JS.index("  async _stopCastDashboard(entityId)")]
    assert 'buttonLabel.textContent = active ? l.cast_stop' in cast_start
    assert 'buttonIcon.setAttribute("icon", active ? "mdi:cast-off"' in cast_start


def test_overview_cast_picker_stacks_copy_and_target_controls_without_overlap():
    setup = JS[JS.index("class FitnessTvSetupCard") :]
    assert ".overview-cast-section{display:grid;grid-template-columns:minmax(0,1fr);" in setup
    assert ".overview-cast-section .cast-section-copy>span,.overview-cast-section .cast-section-copy strong,.overview-cast-section .cast-section-copy small{display:block;min-width:0}" in setup
    assert ".overview-cast-section .cast-target-control{display:grid;grid-template-columns:minmax(0,1fr);gap:6px;width:100%;min-width:0}" in setup
    assert ".overview-cast-section .cast-target-control>select{display:block;width:100%;min-width:0;max-width:100%}" in setup
    assert ".overview-smart-tv-controls{display:grid;grid-template-columns:minmax(0,1fr);" in setup


def test_admin_about_is_dedicated_fitness_tv_metadata_and_restricted_portal_safe():
    assert '@websocket_api.websocket_command({vol.Required("type"): "fitness/dashboard/about"})' in DASH
    start = DASH.index("def _dashboard_about_payload")
    about = DASH[start : DASH.index("async def websocket_dashboard_config", start)]
    for expected in ("Fitness TV", "HA-Fitness", "manifest.json", "changelog.md", "LICENSE", "documentation", "issue_tracker", "copyright"):
        assert expected in about
    assert '"fitness/dashboard/about": ("dashboard", "websocket_dashboard_about")' in ACCOUNTS
    setup = JS[JS.index("class FitnessTvSetupCard") :]
    assert "async _openAboutFitness()" in setup
    assert 'type:"fitness/dashboard/about"' in setup
    assert "l.fitness_tv_changelog" in setup
    assert "GitHub" in setup
    assert "l.issues" in setup
    assert "mdi:scale-balance" in setup


def test_about_is_removed_from_per_user_and_hub_options_flows():
    assert 'menu.append("about")' not in FLOW
    assert '["protocols", *menu_options, "about"]' not in FLOW
    assert "async def async_step_about" not in FLOW
    assert "def _about_payload" not in FLOW
    assert "_aboutMarkup(step)" not in JS
    assert 'String(step.step_id || "") === "about"' not in JS


def test_v144_frontend_cache_bust_is_consistent():
    assert '_RESOURCE_URL += "&build=cast-ui-155"' in DASH
    assert 'frontend_cache_version = f"{frontend_version}-cast-ui-155"' in ACCOUNTS
