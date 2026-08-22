from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")


def test_profile_cast_is_singleton_and_sender_ui_offers_stop_while_busy():
    assert "def _require_cast_idle" in TV
    assert "self._require_cast_idle(profile_entry_id)" in TV
    assert '"cast_already_active"' in TV
    picker = JS[JS.index("async _openCastPicker()") : JS.index("async _stopCastDashboard", JS.index("async _openCastPicker()"))]
    assert "currentCast?.busy" in picker
    assert "cast-stop" in picker
    assert "return;" in picker


def test_profile_cast_green_state_requires_receiver_confirmed_connected_state():
    refresh = JS[JS.index("  _refreshCastUiState() {") : JS.index("  _cancelRadioRecovery()", JS.index("  _refreshCastUiState() {"))]
    assert "real receiver heartbeat" in refresh
    assert 'this._castState === "connected"' in refresh
    assert "FITNESS_TV_CAST_APP_ID" not in refresh
    assert ".tool.cast-pending#cast" in JS
    assert "var(--secondary-text-color)!important" in JS


def test_overview_cast_is_singleton_and_receiver_heartbeat_is_authoritative():
    descriptor = DASH[DASH.index("def _tv_overview_cast_descriptor") : DASH.index("def _tv_cast_targets") ]
    assert '"busy": bool(active or connecting)' in descriptor
    assert "last_seen" in descriptor
    assert "_fitness_cast_app_active(app_id)" not in descriptor
    assert "websocket_tv_overview_browser_handoff" in DASH
    assert '"cast_already_active"' in DASH[DASH.index("async def websocket_tv_overview_browser_handoff") : DASH.index("async def websocket_tv_overview_cast") ]
    heartbeat = DASH[DASH.index("async def websocket_tv_overview_heartbeat") : DASH.index("async def websocket_tv_overview_status") ]
    assert 'result["cast_conflict"] = True' in heartbeat


def test_dashcast_visual_safety_removes_filters_stale_height_and_keeps_route_overlays():
    assert ':host([fitness-cast-receiver]) .tv-card-slot{filter:none!important' in JS
    assert ':host([fitness-cast-receiver]) .fitness-ambient-layer{display:none!important' in JS
    assert '.selected-route,.map-scene svg,.workout-map-scene svg{filter:none!important;opacity:1!important;visibility:visible!important;z-index:3!important}' in JS
    assert '.map-metrics,.workout-map-tools,.route-badge,.map-attribution,.attribution{visibility:visible!important;opacity:1!important}' in JS
    assert "const previousVisualHeight = FITNESS_TV_CAST_RECEIVER" in JS
    assert "const renderedWrapperHeight = FITNESS_TV_CAST_RECEIVER" in JS


def test_overview_cast_keeps_admin_actions_except_fitness_devices_and_uses_dedicated_about_dialog():
    setup = JS[JS.index("class FitnessTvSetupCard") :]
    assert 'const overviewTitle = FITNESS_TV_CAST_RECEIVER ? "Overview Cast"' in setup
    assert 'id="about-fitness"' in setup
    assert 'void this._openAboutFitness()' in setup
    assert 'type:"fitness/dashboard/about"' in setup
    assert '_openBackendFlow("add", "", "", "about")' not in setup
    assert 'this._access?.native_ha_admin && !FITNESS_TV_CAST_RECEIVER && !this.hasAttribute("fitness-public-portal")' in setup
    assert ':host([fitness-cast-receiver]) .setup-actions{display:none' not in JS
    assert ':host([fitness-cast-receiver]) .profile-actions{display:none' not in JS


def test_restricted_overview_portal_exposes_only_fitness_config_flow_bridge():
    for command in (
        "fitness/dashboard/about",
        "fitness/dashboard/config_flow/start",
        "fitness/dashboard/config_flow/step",
        "fitness/dashboard/config_flow/cancel",
        "fitness/tv/overview/heartbeat",
        "fitness/tv/overview/status",
    ):
        assert f'"{command}"' in ACCOUNTS
    assert "_require_fitness_config_flow_admin" in DASH
    assert "hass.config_entries.flow.async_init(" in DASH
    assert 'context = {"source": "user", "fitness_dashboard_flow": True}' in DASH
    assert "hass.config_entries.flow.async_init(DOMAIN, context=context)" in DASH
    assert "Fitness command is not available through the restricted portal" in ACCOUNTS


def test_overview_cast_profile_view_claims_profile_audio_without_launching_second_cast():
    assert "const overviewCastPortal=Boolean(castPortal&&castBootstrap?.overview)" in ACCOUNTS
    assert "fitness/tv/overview/heartbeat" in ACCOUNTS
    assert "const routeProfile=" in ACCOUNTS
    assert 'addEventListener("location-changed",syncRoute)' in ACCOUNTS
    assert 'addEventListener("popstate",syncRoute)' in ACCOUNTS
    assert "FITNESS_TV_OVERVIEW_CAST_RECEIVER" in JS
    assert "is_cast_receiver:FITNESS_TV_CAST_RECEIVER," in JS
    assert "is_cast_receiver:FITNESS_TV_CAST_RECEIVER && !FITNESS_TV_OVERVIEW_CAST_RECEIVER" not in JS
    assert "if (!FITNESS_TV_OVERVIEW_CAST_RECEIVER)" in JS


def test_ha_media_output_transport_is_real_output_authoritative_and_shared():
    assert "def _ensure_audio_output_monitor" in TV
    assert "async_track_state_change_event" in TV
    reconcile = TV[TV.index("async def async_reconcile_audio_output") : TV.index("def _ha_output_busy_owner") ]
    assert 'playing = output_state.state == "playing"' in reconcile
    assert "await self.async_broadcast_media_state" in reconcile
    control = TV[TV.index("async def _async_control_ha_output") : TV.index("async def async_dispatch_media_command") ]
    assert '"pause": "media_pause"' in control
    assert '"play": "media_play"' in control
    assert "await self.async_broadcast_media_state" in control
    assert 'const playing = hasSelection && !failed && Boolean(shared.playing || localTransportPlaying);' in JS


def test_user_cast_and_overview_cast_titles_are_explicit():
    assert '`${this._profile?.profile_name || "Fitness"} User Cast`' in JS
    assert 'const overviewTitle = FITNESS_TV_CAST_RECEIVER ? "Overview Cast"' in JS
