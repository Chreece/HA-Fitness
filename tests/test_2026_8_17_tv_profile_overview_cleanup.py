from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()


def test_overview_cast_view_is_hidden_subview_but_retained_for_cast():
    assert 'title="Fitness TV Overview Cast", path="cast-overview", subview=True, setup=True' in DASHBOARD
    assert '"view_path": "cast-overview"' in DASHBOARD


def test_live_card_uses_profile_sensor_assignment_not_active_owner():
    block = FRONTEND.split("_profileOwnsLiveSensor", 1)[1].split("_conditionalCardVisibilitySignature", 1)[0]
    assert "live_sensor_metrics" in block
    assert "has_assigned_live_sensor" in block
    assert "assigned_live_sensor_ids" in block
    assert '"has_assigned_live_sensor": bool(assigned_live_sensor_ids)' in DASHBOARD
    assert '"assigned_live_sensor_ids": assigned_live_sensor_ids' in DASHBOARD
    assert "owner_entry_id" not in block


def test_profile_overview_has_assignment_and_complete_removal_controls():
    assert 'data-profile-assign' in FRONTEND
    assert 'complete-remove-profile' in FRONTEND
    assert 'delete-backend-profile' in FRONTEND
    assert 'type:"fitness/access/profile/delete"' in FRONTEND


def test_complete_profile_removal_scrubs_tv_preferences():
    assert "async_remove_profile_preferences" in TV
    assert "async_remove_profile_preferences(entry.entry_id)" in ACCESS


def test_music_adapters_can_be_removed_per_profile():
    assert FRONTEND.count('querySelectorAll("[data-remove-music-adapter]")') >= 2
    assert 'profile-adapter-removed' in FRONTEND
    assert 'removedMusicAdapters' in FRONTEND
    assert 'delete musicAdapterOptions[adapterId]' in FRONTEND


def test_unique_sleep_recovery_and_readiness_motion_exists():
    assert "fitness-sleep-orbit" in FRONTEND
    assert "fitness-readiness-breathe" in FRONTEND
    assert "fitness-recovery-flow" in FRONTEND
    assert "fitness-recovery-sheen" in FRONTEND


def test_backend_flow_main_menu_has_icon_and_button_copy_can_shrink():
    assert 'class="flow-home"' in FRONTEND
    assert 'mdi:view-dashboard-outline' in FRONTEND
    assert '.flow-home>span,.flow-submit>span,.flow-menu>span{display:block!important' in FRONTEND
    assert 'font-size:clamp(11px,1vw,13px)!important' in FRONTEND


def test_new_profile_overview_actions_are_localized_in_german():
    assert '"assign_user":"Home-Assistant-Benutzer zuweisen"' in DASHBOARD
    assert '"complete_remove":"Vollständig entfernen"' in DASHBOARD
    assert '"complete_remove_confirm":"Dieses Fitness-Profil vollständig entfernen?' in DASHBOARD
