from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
YTDLP = (ROOT / "custom_components/fitness/music/yt_dlp.py").read_text(encoding="utf-8")


def _method(source: str, start: str, end: str) -> str:
    return source[source.index(start):source.index(end, source.index(start))]


def test_resume_audit_keeps_provider_specific_seek_only_where_transport_needs_it():
    native = _method(FRONTEND, "  async _playFitnessNativeMedia(", "  async _playResolvedMedia(")
    generic = _method(FRONTEND, "  async _playResolvedMedia(", "  async _handleMediaCommand(")
    ma = _method(FRONTEND, "  async _playMusicAssistant(", "  async _resolveFitnessMedia(")
    youtube = _method(FRONTEND, "  async _playYouTube(", "  async _playFitnessNativeMedia(")
    soundcloud = _method(FRONTEND, "  async _playSoundCloud(", "  _youtubeTarget(")

    # Both HTMLAudio transports capture the resume target before play() can fire
    # metadata/timeupdate at zero seconds, and use that immutable value to seek.
    assert "const resumePosition = this._mediaSeconds" in native
    assert "this._pendingHtmlAudioResumePosition = resumePosition;" in native
    assert "await this._resumeHtmlAudio(resumePosition);" in native
    assert "const resumePosition = this._mediaSeconds(this._musicMetadata.position);" in generic
    assert "this._pendingHtmlAudioResumePosition = resumePosition;" in generic
    assert "await this._resumeHtmlAudio(resumePosition);" in generic

    capture = _method(FRONTEND, "  _captureLocalMediaProgress(", "  async _resumeHtmlAudio(")
    assert "const pendingResume = this._mediaSeconds(this._pendingHtmlAudioResumePosition);" in capture
    assert "position + 1 < pendingResume" in capture
    assert "return;" in capture

    # Other transport adapters already restore their own authoritative clocks.
    assert 'type:"fitness/tv/music/ma/seek"' in ma
    assert "position:selectedMetadata.position" in ma
    assert "playerVars.start = Math.floor(resumePosition)" in youtube
    assert "event.target.seekTo?.(resumePosition, true)" in youtube
    assert "widget.seekTo?.(resumePosition * 1000)" in soundcloud

    # yt-dlp does not get a hard-coded frontend seek path. Finite tracks resolve
    # to generic HTMLAudio; playlist/live/fallback items use YouTube semantics.
    assert '"kind": "audio"' in YTDLP
    assert '"fallback_kind": "youtube"' in YTDLP
    assert 'if marker in {"playlist", "live"}' in YTDLP
    assert "resume" not in YTDLP.lower()


def test_cast_launch_generation_scopes_offline_failure_cleanup_to_its_own_target():
    assert "self._cast_generation: dict[str, int] = {}" in TV
    assert "self._expected_cast_generation: dict[str, int] = {}" in TV
    assert "def cast_attempt_is_current(" in TV
    assert "generation=bound_generation" in TV

    cast = _method(DASHBOARD, "async def async_cast_tv_dashboard(", "async def _async_register_resource(")
    assert "cast_generation = hub.expect_cast(entry.entry_id, media_player)" in cast
    assert cast.count("hub.cast_attempt_is_current(") >= 8
    assert "media_player=media_player" in cast
    assert "generation=cast_generation" in cast
    assert 'reason="cast_launch_failed"' in cast


def test_outer_remote_navigation_stays_in_card_grid_until_top_row_up():
    spatial = _method(FRONTEND, "  _moveCastRemoteSpatial(", "  _handleCastRemoteArrow(")
    assert "const cards = items.filter((item) => item !== toolbar);" in spatial
    assert "const cardTarget = this._moveCastRemoteSpatial(cards, current, key);" in spatial
    assert 'if (key === "ArrowUp" && cardTarget === current) return toolbar || current;' in spatial
    assert "return cardTarget || current;" in spatial

    # Preserve the already-working universal capture-phase remote path.
    assert 'window.addEventListener("keydown", this._boundCastKeydown, true);' in FRONTEND
    assert 'window.addEventListener("keyup", this._boundCastKeyup, true);' in FRONTEND
    assert 'window.addEventListener("popstate", this._boundCastPopstate, true);' in FRONTEND


def test_oled_pixel_shift_moves_toolbar_and_cards_as_one_safe_stage():
    assert '<div class="tv-oled-stage">' in FRONTEND
    assert ':host([fitness-cast-receiver]) .tv-oled-stage{width:calc(100% - 4px);margin:2px;transition:transform .8s ease;will-change:transform}' in FRONTEND
    assert ':host([oled-protection][fitness-cast-receiver]) .tv-oled-stage{transform:translate3d(var(--fitness-oled-x,0),var(--fitness-oled-y,0),0)}' in FRONTEND
    assert ':host([oled-protection][fitness-cast-receiver]) .tv-toolbar,:host([oled-protection][fitness-cast-receiver]) .tv-grid' not in FRONTEND


def test_stop_cast_toolbar_dispatches_only_one_stop_request():
    render = _method(FRONTEND, "  _render()", "  async _toggleFullscreen(")
    assert render.count("if (activeTarget) this._stopCastDashboard(activeTarget);") == 1
