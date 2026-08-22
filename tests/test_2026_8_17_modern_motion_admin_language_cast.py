from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")


def test_modern_dashboard_motion_is_lightweight_icon_only_and_cast_static():
    assert "_startDashboardEntryMotion()" in FRONTEND
    assert 'cards.forEach((card, index) => this._ensureCardLivingMotion(card, index))' in FRONTEND
    assert "_cardMotionRoots(card)" in FRONTEND
    assert 'const icons = this._cardMotionElements(card, "ha-icon")' in FRONTEND
    assert 'movement-icons-only' in FRONTEND
    assert 'data-fitness-motion-lite' in FRONTEND
    assert '_applyCastMotionPolicy(card)' in FRONTEND
    assert 'data-fitness-cast-static' in FRONTEND
    assert 'if (FITNESS_TV_CAST_RECEIVER) return false;' in FRONTEND
    assert "new MutationObserver" in FRONTEND


def test_profile_animation_preference_and_reduced_motion_remain_authoritative():
    assert "_motionEnabled()" in FRONTEND
    assert 'matchMedia?.("(prefers-reduced-motion: reduce)")' in FRONTEND
    assert 'this._animationsEnabled' in FRONTEND
    assert "_cancelDashboardMotion()" in FRONTEND


def test_cast_buttons_are_toggles_and_receiver_gets_only_requested_profile_controls():
    assert 'this.shadowRoot.getElementById("cast")?.addEventListener("click"' in FRONTEND
    assert 'this._castState === "connected"' in FRONTEND
    assert 'this._castMode === "server"' in FRONTEND
    assert 'void this._stopCurrentCast()' in FRONTEND
    assert 'id="light-feedback-toggle"' in FRONTEND
    assert 'id="tts-announcements-toggle"' in FRONTEND
    assert 'id="backend-config"' in FRONTEND
    assert 'id="configure"' in FRONTEND


def test_main_tv_overview_is_admin_only_castable_and_accounts_stay_account_focused():
    assert 'this._access?.is_admin' in FRONTEND
    assert 'id="manage-access"' in FRONTEND
    assert 'type:"fitness/accounts/admin"' in FRONTEND
    assert 'type:"fitness/accounts/save"' in FRONTEND
    assert 'type:"fitness/accounts/delete"' in FRONTEND
    assert 'data-account-language' not in FRONTEND
    assert 'href="/config/person"' not in FRONTEND
    assert 'access.get("is_admin") and access.get("local_ha_hardware_allowed")' in DASHBOARD

def test_profile_language_is_authoritative_and_account_settings_have_no_override():
    # Keep the websocket field readable for upgrade compatibility, but account
    # assignment must not persist or mutate a second language authority.
    assert 'vol.Optional("language"): vol.In(sorted(SUPPORTED_LANGUAGES))' in ACCESS
    bind = ACCESS[ACCESS.index('async def _async_bind_account'):ACCESS.index('async def async_remove_account')]
    assert 'options[CONF_LANGUAGE] = selected_language' not in bind
    assert '"language": selected_language' not in bind
    assert 'data-access-language' not in FRONTEND
    assert 'language:String(language?.value || "en")' not in FRONTEND
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
