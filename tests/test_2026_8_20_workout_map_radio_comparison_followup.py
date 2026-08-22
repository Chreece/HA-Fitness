from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
RADIO = (ROOT / "custom_components/fitness/music/radio_browser.py").read_text(encoding="utf-8")


def _method(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    return source[begin:source.index(end, begin)]


def test_workout_viewer_rpe_wraps_inside_narrow_card():
    workout = _method(FRONTEND, "class FitnessWorkoutCard", "function _fitnessCanonicalZone")
    assert ".viewer-rpe-scale{display:grid;grid-template-columns:repeat(5,minmax(0,1fr))" in workout
    assert "data-workout-rpe=" in workout


def test_workout_viewer_map_has_metric_overlay_and_own_pan_zoom_reset_controls():
    workout = _method(FRONTEND, "class FitnessWorkoutCard", "function _fitnessCanonicalZone")
    assert 'class="map-metrics map-metrics-left"' in workout
    assert 'class="map-metrics map-metrics-right"' in workout
    assert '_fitMapState(pts,width,height,sideReserve)' in workout
    assert '<div class="map-shade"></div>' not in workout
    assert "fact.setAttribute('role','button')" in workout
    assert "data-workout-map-zoom=\"1\"" in workout
    assert "data-workout-map-zoom=\"-1\"" in workout
    assert "data-workout-map-reset" in workout
    assert "wrap.addEventListener('wheel'" in workout
    assert "wrap.addEventListener('pointerdown'" in workout
    assert "this._mapViews.delete(key);this._render();" in workout


def test_comparison_sport_panels_do_not_create_intrinsic_height_feedback_loop():
    comparison = _method(FRONTEND, "class FitnessComparisonCard", "class FitnessSleepStageCard")
    assert "grid-auto-rows:max-content" in comparison
    assert "grid-template-columns:repeat(auto-fit,minmax(min(280px,100%),1fr))" in comparison
    assert "container-type:inline-size" not in comparison
    assert "height:auto!important" in comparison


def test_direct_radio_browser_is_live_with_metadata_and_never_restores_position():
    assert '"is_live": True' in RADIO
    assert '"thumbnail": str((normalized or {}).get("thumbnail") or "")' in RADIO
    sanitize = _method(TV, "    def _sanitize_last_media(", "    @classmethod\n    def _sanitize_profile")
    assert "media_content_id.startswith(FITNESS_RADIO_PREFIX)" in sanitize
    assert 'result["is_live"] = True' in sanitize
    assert "duration = 0.0" in sanitize
    assert "position = 0.0" in sanitize
    native = _method(FRONTEND, "  async _playFitnessNativeMedia(", "  async _playResolvedMedia(")
    assert "const resumePosition = this._mediaSeconds(isLive ? 0 : persistedMetadata.position);" in native


def test_radio_recovery_is_truthful_and_disabling_provider_clears_owned_media():
    recover = _method(FRONTEND, "  async _recoverRadioPlayback(", "  async _ensureCastMusicPlayback(")
    assert "this._radioRecovering = true;" in recover
    assert "playing:false,error:false,position:0,duration:0" in recover
    assert "playing:false,error:true,position:0,duration:0" in recover
    preferences = _method(TV, "    async def async_set_preferences(", "    async def async_remove_profile_preferences(")
    assert "removed_music_adapters" in preferences
    assert "active_provider in removed_music_adapters" in preferences
    assert 'command="stop"' in preferences
    assert '{"media_content_id": "", "playing": False, "error": False, "is_live": False}' in preferences
    adapters_ws = _method(TV, "async def websocket_tv_music_adapters(", "async def websocket_tv_music_search(")
    assert "music_provider_unavailable" in adapters_ws
    assert "active_provider not in available_adapter_ids" in adapters_ws
