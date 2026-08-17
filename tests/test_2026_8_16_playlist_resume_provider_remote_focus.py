from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_last_media_keeps_playlist_context_and_replays_saved_position():
    assert "def _sanitize_playlist_context" in TV
    assert 'last_media.get("playlist_context")' in TV
    play_last = TV[TV.index("async def async_play_last_media("):TV.index("async def async_dispatch_media_command(")]
    assert '"playlist_context",' in play_last
    assert '"position",' in play_last


def test_cast_stop_and_profile_unload_persist_resume_state_before_transport_teardown():
    cast_stop = TV[TV.index("async def async_mark_cast_inactive("):TV.index("async def async_wait_cast_active(")]
    assert cast_stop.index("await self.async_persist_media_state(profile_entry_id)") < cast_stop.index("self._audio_owner.pop")
    local_stop = TV[TV.index("async def async_mark_local_cast_inactive("):TV.index("def expect_cast(")]
    assert local_stop.index("await self.async_persist_media_state(profile_entry_id)") < local_stop.index("self._audio_owner.pop")
    release = TV[TV.index("async def async_release_profile_music("):TV.index("async def async_speak(")]
    assert "await self.async_set_preferences(profile_entry_id, last_media=state)" in release


def test_playlist_context_is_shared_restored_and_sent_with_select_and_play():
    assert "_playlistContextSnapshot(context = this._activePlaylistContext)" in FRONTEND
    assert "_restorePlaylistContext(raw = {})" in FRONTEND
    assert "this._restorePlaylistContext(this._lastMediaSnapshot?.playlist_context || {});" in FRONTEND
    assert "playlist_context:this._playlistContextSnapshot()," in FRONTEND
    select = FRONTEND[FRONTEND.index("async _selectMusic("):FRONTEND.index("async _playlistTransport(")]
    play = FRONTEND[FRONTEND.index("async _playMusic()"):FRONTEND.index("async _pauseMusic()")]
    assert "playlist_context:this._playlistContextSnapshot()," in select
    assert "playlist_context:this._playlistContextSnapshot()," in play


def test_ma_playlist_resume_rebuilds_full_fitness_queue_then_restores_index_and_seek():
    ma = FRONTEND[FRONTEND.index("async _playMusicAssistant("):FRONTEND.index("async _resolveFitnessMedia(")]
    assert "contextItems.length === playlistItems.length" in ma
    assert "playPayload.media_content_ids = contextItems.map" in ma
    assert 'action:"next"' in ma
    assert 'type:"fitness/tv/music/ma/seek"' in ma
    assert "position:selectedMetadata.position" in ma


def test_youtube_playlist_resume_restores_playlist_item_index_and_track_time():
    youtube = FRONTEND[FRONTEND.index("async _playYouTube("):FRONTEND.index("async _playFitnessNativeMedia(")]
    assert "playerVars.start = Math.floor(resumePosition)" in youtube
    assert "playerVars.index = playlistIndex" in youtube


def test_provider_details_are_compacted_for_now_playing_and_result_types_are_localized():
    assert "_compactMediaDetails(providerLabel, details)" in FRONTEND
    result_metadata = FRONTEND[
        FRONTEND.index("  _mediaResultMetadata(item = {}) {"):
        FRONTEND.index("  _isMAItem(item = {})", FRONTEND.index("  _mediaResultMetadata(item = {}) {"))
    ]
    assert "const mediaType = FITNESS_MUSIC_SEARCH_TYPES.find" in result_metadata
    assert 'const typeLabel = mediaType ? String(labels?.[mediaType.label] || "").trim() : "";' in result_metadata
    assert "item.details" not in result_metadata
    assert "metadata.details = this._compactMediaDetails(providerLabel, metadata.details);" in FRONTEND


def test_now_playing_text_is_bounded_to_progress_width_and_marquees_only_on_overflow():
    assert 'class="media-scroll-line"' in FRONTEND
    assert ".media-now-main{min-width:0;width:min(420px,100%);max-width:420px}" in FRONTEND
    assert ".media-progress-wrap{display:grid" in FRONTEND
    assert "width:min(420px,100%);max-width:420px" in FRONTEND
    assert ":host([fitness-cast-receiver]) .media-now-main,:host([fitness-cast-receiver]) .media-copy{width:min(300px,100%);max-width:300px}" in FRONTEND
    assert ":host([fitness-cast-receiver]) .media-progress-wrap{gap:3px;margin-top:1px;font-size:8px;width:min(300px,100%);max-width:300px}" in FRONTEND
    assert "_updateMediaMarquee()" in FRONTEND
    assert "element.scrollWidth - line.clientWidth" in FRONTEND
    assert "@keyframes fitness-media-marquee" in FRONTEND


def test_cast_remote_has_visible_focus_press_feedback_and_range_navigation():
    remote = FRONTEND[FRONTEND.index("  _clearCastRemoteFocus() {"):FRONTEND.index("  _claimWindowController() {")]
    assert "_markCastRemoteFocus(element, pressed = false, record = true)" in remote
    assert 'element.style.outline = "2px solid color-mix(in srgb,var(--primary-color,#03a9f4) 92%,white 8%)"' in remote
    assert 'pressed ? "translate3d(0,0,0) scale(.985)" : "translate3d(0,-1px,0) scale(1.018)"' in remote
    assert 'element.style.filter = "none"' in remote
    assert '["Enter","NumpadEnter","Select","Accept"," "]' in remote
    assert "target.click?.();" in remote
    assert 'String(active?.type || "").toLowerCase() === "range"' in remote
    assert "active.stepDown?.()" in remote
    assert "active.stepUp?.()" in remote
    assert "this._markCastRemoteFocus(best);" in remote
