from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FRONT=(ROOT/'custom_components/fitness/frontend/fitness-dashboard.js').read_text()
GARMIN=(ROOT/'custom_components/fitness/device_adapters/garmin/coordinator.py').read_text()
CYC=(ROOT/'custom_components/fitness/device_adapters/cycplus_m1.py').read_text()
RUNTIME=(ROOT/'custom_components/fitness/live/runtime.py').read_text()

def test_v109_frontend_and_no_outer_overflow_lock():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in FRONT
    block=FRONT.split('  _claimDashboardScrollOwner() {',1)[1].split('  _scheduleDashboardScrollOwnerClaim() {',1)[0]
    assert 'element.style.overflowY = "hidden"' not in block
    assert 'scrollbarWidth = "none"' in block
    assert 'overflow-x:clip!important' in FRONT

def test_cast_toolbar_order_and_back_scope():
    cast=FRONT.split('const profileActions = profileNavTool + (FITNESS_TV_CAST_RECEIVER',1)[1].split(': (canControl ?',1)[0]
    positions=[cast.index(f'id="{x}"') for x in ['light-feedback-toggle','tts-announcements-toggle','configure','backend-config','dashboards']]
    assert positions == sorted(positions)
    handler=FRONT.split('  _handleCastRemoteBackPress(event, source = "key") {',1)[1].split('  _handleCastRemoteKeydown',1)[0]
    inner=handler.split('if (this._castRemoteMode === "inner") {',1)[1].split('this._ensureCastRemoteOuterFocus()',1)[0]
    assert '_showCastExitConfirmation()' not in inner
    assert 'Back inside a card/menu is navigation' in inner

def test_cast_modals_are_bounded_and_remote_focusable():
    assert 'const top = castModal ? 6' in FRONT
    assert 'cast-modal-open' in FRONT
    assert 'max-height:calc(100dvh - 24px)!important' in FRONT
    assert 'this._castRemoteMode = "inner"' in FRONT

def test_music_sources_and_search_footer():
    assert '.music-source{display:grid;grid-template-columns:34px minmax(0,1fr)' in FRONT
    search=FRONT.split('async _openMusicSearch()',1)[1].split('const root =',1)[0]
    assert search.index('music-search-error') < search.index('run-music-search')
    assert '.music-search-form>.modal-actions{position:sticky!important;bottom:0!important;margin-top:auto!important' in FRONT

def test_garmin_automatic_sync_requires_fresh_advertisement_and_handles_phone_owner():
    assert 'FRESH_ADVERTISEMENT_MAX_AGE = 120.0' in GARMIN
    assert 'manual_request_until' in GARMIN
    assert 'not manual_request and not self._endpoint_recent(endpoint)' in GARMIN
    assert 'bluetooth_connection_busy' in GARMIN
    assert 'PHONE_HOST_RETRY_DELAY' in GARMIN

def test_cycplus_has_bounded_connect_and_stronger_registry_merge():
    assert 'CYCPLUS_CONNECT_TIMEOUT = 35.0' in CYC
    assert 'async with asyncio.timeout(CYCPLUS_CONNECT_TIMEOUT)' in CYC
    assert 'max_attempts=2' in CYC
    assert 'physical_serial:cycplus:m1:' in RUNTIME
    assert 'if not provisional_merge and not requires_reassignment:' in RUNTIME

def test_cast_radio_stream_is_sticky_and_recoverable():
    tv=(ROOT/'custom_components/fitness/tv_dashboard.py').read_text()
    assert 'Keep one audible Cast receiver sticky' in tv
    assert 'owner_is_live_cast' in tv
    assert 'mediaContentId.startsWith(FITNESS_MUSIC_PREFIXES.radio) && this._audioOwner' in FRONT
    assert 'async _recoverRadioPlayback(reason = "stream-ended")' in FRONT
    assert 'this._radioRecoveryAttempts >= 3' in FRONT
    assert 'fresh_resolve:String(mediaContentId || "").startsWith(FITNESS_MUSIC_PREFIXES.radio)' in FRONT
    assert 'this._cancelRadioRecovery();' in FRONT
    radio=(ROOT/'custom_components/fitness/music/radio_browser.py').read_text()
    assert 'resolved_url = str(row.get("url_resolved") or "").strip()' in radio
    assert 'url = resolved_url or url or str(row.get("url") or "").strip()' in radio


def test_cast_modal_close_returns_remote_navigation_to_outer_dashboard():
    modal=FRONT.split('  _showModal(content) {',1)[1].split('  async _openMediaBrowser()',1)[0]
    close=modal.split('const closeModal = () => {',1)[1].split('};',1)[0]
    assert 'this._castRemoteMode = "outer"' in close
    assert 'this._castRemoteSection = null' in close
    assert 'this._ensureCastRemoteOuterFocus()' in close
