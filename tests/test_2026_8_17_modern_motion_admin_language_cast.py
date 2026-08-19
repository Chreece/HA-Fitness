from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")


def test_modern_dashboard_motion_is_entity_first_data_aware_and_continuously_alive():
    assert "_startDashboardEntryMotion()" in FRONTEND
    assert "Card frames are intentionally stationary" in FRONTEND
    assert "innerDelay = slideDuration" not in FRONTEND
    assert "_cardMotionRoots(card)" in FRONTEND
    assert 'tag.startsWith("fitness-")' in FRONTEND
    assert "_animateChartReveal(root" in FRONTEND
    assert "getTotalLength?.()" in FRONTEND
    assert 'transform:"scaleX(0)"' in FRONTEND
    assert 'transform:"scaleY(0)"' in FRONTEND
    assert 'clipPath:"circle(0% at 50% 50%)"' in FRONTEND
    assert 'fill:"both"' in FRONTEND
    assert "elementIndex * 22" in FRONTEND
    assert "_ensureChartTracer(card" in FRONTEND
    assert 'document.createElementNS("http://www.w3.org/2000/svg", "animateMotion")' in FRONTEND
    assert 'svg.style.overflow = "hidden"' in FRONTEND
    assert "_armCardMotionObservers(card" in FRONTEND
    assert "new MutationObserver" in FRONTEND
    assert "_animateCardStateRefresh(card)" in FRONTEND
    assert "@keyframes fitness-data-sheen" in FRONTEND
    assert "_animateRemoteSectionInterior(section, active)" in FRONTEND
    assert "_ensureCardLivingMotion(card" in FRONTEND
    assert 'semantic = "heart"' in FRONTEND
    assert 'semantic = "motion"' in FRONTEND
    assert 'semantic = "recovery"' in FRONTEND
    assert 'semantic = "energy"' in FRONTEND
    assert 'overflow-x:clip;overflow-y:visible' in FRONTEND


def test_profile_animation_preference_and_reduced_motion_remain_authoritative():
    assert "_motionEnabled()" in FRONTEND
    assert 'matchMedia?.("(prefers-reduced-motion: reduce)")' in FRONTEND
    assert 'this._animationsEnabled' in FRONTEND
    assert "_cancelDashboardMotion()" in FRONTEND


def test_cast_buttons_are_toggles_and_receiver_gets_only_requested_profile_controls():
    assert 'this.shadowRoot.getElementById("cast")?.addEventListener("click"' in FRONTEND
    assert 'this._serverCastActive && activeTarget' in FRONTEND
    assert 'this._serverCastActive && target && target === String(this._activeCastTarget || "")' in FRONTEND
    assert 'id="light-feedback-toggle"' in FRONTEND
    assert 'id="tts-announcements-toggle"' in FRONTEND
    assert 'id="backend-config"' in FRONTEND
    assert 'id="configure"' in FRONTEND


def test_main_tv_overview_is_admin_only_castable_and_accounts_stay_account_focused():
    # The overview itself is an admin-only surface, but admins may cast that whole
    # overview either through the HA server or a local browser Google Cast chooser.
    assert 'const isAdmin = Boolean(this._access?.is_admin);' in FRONTEND
    assert 'if (!isAdmin) {' in FRONTEND
    assert 'const destination = profiles.find((profile) => profile?.access?.is_own) || profiles[0];' in FRONTEND
    assert 'id="overview-cast-toggle"' in FRONTEND
    assert 'getElementById("overview-cast-toggle")?.addEventListener' in FRONTEND
    assert 'overview:true' in FRONTEND
    assert 'id="overview-cast-local"' in FRONTEND
    assert 'class="add-profile-row overview-cast-target ${unavailable ? "unavailable" : ""}"' in FRONTEND
    assert 'admin-profile-link' in FRONTEND
    assert 'lastMediaTitle' not in FRONTEND
    assert 'data-user-cast' not in FRONTEND
    assert 'data-user-tv-config' not in FRONTEND
    assert 'data-user-fitness-config' not in FRONTEND
    assert 'data-user-light-feedback' not in FRONTEND
    assert 'data-user-tts-announcements' not in FRONTEND
    assert 'data-profile-entry' not in FRONTEND
    assert 'data-assign-profile' not in FRONTEND
    assert 'type:"fitness/access/admin"' in FRONTEND


def test_account_language_is_persisted_and_drives_profile_frontend_and_options_flow():
    assert 'vol.Optional("language"): vol.In(sorted(SUPPORTED_LANGUAGES))' in ACCESS
    assert 'options[CONF_LANGUAGE] = selected_language' in ACCESS
    assert '"supported_languages": dict(SUPPORTED_LANGUAGES)' in ACCESS
    assert 'data-access-language' in FRONTEND
    assert 'language:String(language?.value || "en")' in FRONTEND
    assert 'profile?.language || this._access?.language || this._hass?.language || "en"' in FRONTEND
    assert 'language:String(profile?.language || this._access?.language || this._hass?.language || "en")' in FRONTEND
    assert '"account_language":"Γλώσσα"' in DASHBOARD


def test_light_and_tts_profile_switches_are_persistent_and_enforced():
    assert '"light_feedback_enabled": bool(profile.get("light_feedback_enabled", True))' in TV
    assert '"tts_announcements_enabled": bool(profile.get("tts_announcements_enabled", True))' in TV
    assert "def light_feedback_enabled(" in TV
    assert "def tts_announcements_enabled(" in TV
    assert "disabled_by_profile" in MANAGER
    assert "tts_announcements_enabled(" in MANAGER
    assert 'await self._async_speak(spoken, force=True)' in MANAGER
    assert '"light_feedback_enabled": bool(tv_preferences.get("light_feedback_enabled", True))' in DASHBOARD
    assert '"tts_announcements_enabled": bool(tv_preferences.get("tts_announcements_enabled", True))' in DASHBOARD
