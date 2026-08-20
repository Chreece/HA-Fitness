from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONST = (ROOT / "custom_components/fitness/const.py").read_text(encoding="utf-8")
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_ignore_workout_lights_while_cast_is_alive_defaults_on_everywhere():
    assert 'CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE = "tv_dashboard_ignore_lights_when_cast_active"' in CONST
    assert "DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE = True" in CONST
    assert "default=DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE" in FLOW
    assert "current.get(\n                        CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,\n                        DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE" in FLOW
    assert 'vol.Optional(\n            "ignore_lights_when_cast_active",\n            default=DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE' in TV
    assert 'current.ignore_lights_when_cast_active ?? true' in FRONTEND
    assert 'tv.ignore_lights_when_cast_active ?? true' in FRONTEND


def test_live_fitness_cast_replaces_light_feedback_without_touching_lights():
    helper = MANAGER[
        MANAGER.index("    def _tv_cast_suppresses_feedback_lights("):
        MANAGER.index("    async def _async_snapshot_feedback_lights(")
    ]
    assert "get_tv_dashboard_hub(self.hass).is_any_cast_active(" in helper
    assert "if self._tv_cast_suppresses_feedback_lights():" in helper
    assert 'self.last_feedback_light_result = "suppressed_by_tv_cast"' in helper
    assert "return []" in helper


def test_casting_resumes_persisted_track_or_playlist_automatically():
    cast = MANAGER[
        MANAGER.index("    async def async_cast_tv_dashboard("):
        MANAGER.index("    async def async_start_tv_workout(")
    ]
    assert "if cast_ok:" in cast
    assert "async_play_last_media(" in cast
    assert "timeout=8.0" in cast
    start = MANAGER[
        MANAGER.index("    async def async_start_tv_workout("):
        MANAGER.index("    async def async_stop_tv_dashboard(")
    ]
    assert "media_state(self.entry.entry_id)" in start
    assert "async_play_last_media(" not in start


def test_local_browser_cast_also_autoplays_current_saved_selection():
    assert "async _autoplaySelectionAfterLocalCast()" in FRONTEND
    helper = FRONTEND[
        FRONTEND.index("  async _autoplaySelectionAfterLocalCast()"):
        FRONTEND.index("  async _stopLocalCast()")
    ]
    assert "this._lastMediaSnapshot" in helper
    assert 'this._sendMediaCommand("play", payload)' in helper
    assert "playlist_context:this._playlistContextSnapshot()" in helper
    assert "position:this._mediaSeconds(snapshot.position)" in helper
    assert "void this._autoplaySelectionAfterLocalCast();" in FRONTEND


def test_music_selection_remains_immediate_autoplay_for_tracks_and_playlists():
    selection = FRONTEND[
        FRONTEND.index("  async _selectMusic(item, options = {})"):
        FRONTEND.index("  async _playlistTransport(")
    ]
    assert 'this._sendMediaCommand("select", {' in selection
    assert "playlist_context:this._playlistContextSnapshot()" in selection
    assert 'if (!result?.playing) throw new Error("Playback did not start")' in selection
    assert "await this._playSelectedMAItems(items);" in FRONTEND
    assert "await this._selectMusic(items[0], {keepPlaylist:true});" in FRONTEND


def test_cast_receiver_toolbar_only_exposes_cast_relevant_action_buttons():
    dashboard = FRONTEND.index("class FitnessTvDashboardCard")
    render = FRONTEND[
        FRONTEND.index("  _render() {", dashboard):
        FRONTEND.index("  async _toggleFullscreen()", dashboard)
    ]
    assert "const profileActions = profileNavTool + (FITNESS_TV_CAST_RECEIVER" in render
    receiver_branch = render[
        render.index("const profileActions = profileNavTool + (FITNESS_TV_CAST_RECEIVER"):
        render.index(": (canControl ? [", render.index("const profileActions = profileNavTool + (FITNESS_TV_CAST_RECEIVER"))
    ]
    assert 'id="stop-cast"' not in receiver_branch
    assert 'id="fullscreen"' not in receiver_branch
    assert 'id="cast"' not in receiver_branch
    assert 'id="cards"' not in receiver_branch
    assert 'id="arrange"' in receiver_branch
    assert 'mdi:arrow-all' in receiver_branch
    assert 'id="remote-sensors"' not in receiver_branch
    assert 'id="configure"' in receiver_branch
    assert 'id="backend-config"' in receiver_branch
    assert 'id="light-feedback-toggle"' in receiver_branch
    assert 'id="tts-announcements-toggle"' in receiver_branch
    assert 'id="stop-cast"' in render  # desktop/local Cast control remains available


def test_tv_profile_payload_and_frontend_revision_expose_new_setting():
    assert DASHBOARD.count('"ignore_lights_when_cast_active": bool(') >= 2
    assert 'CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE' in DASHBOARD
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in FRONTEND
    assert '?v=unreleased-110' in DASHBOARD


def test_cast_handoff_does_not_restart_media_that_fresh_receiver_already_resumed():
    play_last = TV[
        TV.index("    async def async_play_last_media("):
        TV.index("    async def async_dispatch_media_command(")
    ]
    assert 'if state.get("playing") and self.is_any_cast_active(profile_entry_id):' in play_last
    assert '"reason": "already_playing_on_cast"' in play_last

    local = FRONTEND[
        FRONTEND.index("  async _autoplaySelectionAfterLocalCast()"):
        FRONTEND.index("  async _stopLocalCast()")
    ]
    assert "if (Boolean(snapshot.playing)) return true;" in local
    assert "play -> gap -> play" in local


def test_double_back_exit_prompt_is_translated_for_all_dashboard_languages():
    assert DASHBOARD.count('"cast_exit_confirm"') >= 15
    assert 'Press Back once more to exit Cast' in DASHBOARD
    assert 'Πατήστε Πίσω άλλη μία φορά για έξοδο από το Cast' in DASHBOARD
    assert 'Drücke Zurück noch einmal, um Cast zu beenden' in DASHBOARD
