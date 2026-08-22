from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()


def test_successful_portal_login_persists_language_to_bound_profile_and_session_mirrors_it():
    assert "self._persist_login_language(row, language)" in ACCOUNTS
    assert "language=self.account_language(row)" in ACCOUNTS
    assert "session.language = self.account_language(row)" in ACCOUNTS


def test_remote_dashboard_uses_each_profiles_persisted_language_not_session_override():
    assert 'const lang=String(p?.language||session.language||"en")' in ACCOUNTS
    assert '...p,language:lang,labels:p?.labels_by_language?.[lang]' in ACCOUNTS
    assert 'p=>({...p,language:lang' not in ACCOUNTS


def test_profile_language_has_priority_in_dashboard_translation_helpers():
    assert 'this._profile?.language || globalThis.__FITNESS_PUBLIC_SESSION__?.language' in FRONTEND
    assert 'profile?.language || this._access?.language || globalThis.__FITNESS_PUBLIC_SESSION__?.language' in FRONTEND
    assert 'globalThis.__FITNESS_PUBLIC_SESSION__?.language || profile?.language' not in FRONTEND


def test_v117_cache_contract_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in FRONTEND
    assert '?v=unreleased-138' in DASHBOARD
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS
