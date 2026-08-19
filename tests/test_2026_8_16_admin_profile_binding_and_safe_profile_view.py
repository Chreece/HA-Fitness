from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")


def test_ha_account_profile_selector_is_hidden_only_for_no_fitness_account():
    assert 'class="access-profile-field ${role === "none" ? "hidden" : ""}"' in FRONTEND
    assert 'const withoutProfile = current === "none";' in FRONTEND
    assert 'profileField?.classList.toggle("hidden", withoutProfile);' in FRONTEND
    assert 'viewField?.classList.toggle("hidden", withoutProfile);' in FRONTEND
    assert 'if (profile) profile.disabled = withoutProfile;' in FRONTEND


def test_fitness_admin_can_keep_an_own_profile_binding():
    assert 'role == ROLE_ADMIN' in ACCESS
    assert 'row["profile_entry_id"] = requested_profile_id' in ACCESS
    assert 'existing.get("role") in {ROLE_ADMIN, ROLE_LOCAL, ROLE_REMOTE}' in ACCESS
    assert 'profile_entry_id:String(profile?.value || "")' in FRONTEND


def test_browser_profile_lovelace_uses_known_good_setup_wrapper():
    profile_block = DASHBOARD[DASHBOARD.index('for entry in entries:'):DASHBOARD.index('return {"title": "Fitness TV", "views": views}')]
    browser = profile_block[:profile_block.index('path=f"cast-{entry.entry_id}"')]
    assert 'profile_wrapper=True' in browser
    assert 'if setup or profile_wrapper' in DASHBOARD
    assert 'document.createElement(FITNESS_TV_DASHBOARD_CARD_TAG)' in FRONTEND
    assert 'card.setConfig({type:`custom:${FITNESS_TV_DASHBOARD_CARD_TAG}`, profile_entry_id:profileEntryId})' in FRONTEND


def test_frontend_revision_is_71_and_no_people_route_returns():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-89"' in FRONTEND
    assert 'fitness-dashboard.js' in DASHBOARD
    assert '/config/people' not in FRONTEND
    assert '/config/people' not in DASHBOARD
