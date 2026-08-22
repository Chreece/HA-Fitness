from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ICONS = (ROOT / "custom_components/fitness/frontend/fitness-mdi-icons.js").read_text(encoding="utf-8")


def test_v136_frontend_contract_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in FRONTEND
    assert '?v=unreleased-138' in DASHBOARD
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS


def test_cast_copy_no_longer_advertises_retired_direct_lan_fallback_state():
    assert '"local_cast": "Google Cast από αυτόν τον browser"' in DASHBOARD
    assert '"local_cast_choose": "Επιλογή Google Cast TV"' in DASHBOARD
    # The modal may keep legacy config support internally, but it must not show
    # the old "Direct LAN not configured / HA fallback" status line anymore.
    assert '${_fitnessEscape(localCastModeLabel)}' not in FRONTEND
    assert 'throw new Error("local_cast_direct_not_configured")' not in FRONTEND
    assert '? l.local_cast_direct_setup_needed' not in FRONTEND


def test_cast_receiver_uses_inherited_theme_surfaces_not_forced_grey_palette():
    assert ':host([fitness-cast-receiver]){--card-background-color:#1d1f22' not in FRONTEND
    assert 'var(--fitness-tv-ambient,var(--primary-background-color,#0e1116))!important' in FRONTEND
    assert ':host([fitness-cast-receiver]) .tv-card-slot{filter:none!important' in FRONTEND
    assert ':host([fitness-cast-receiver]) .fitness-ambient-layer{display:none!important' in FRONTEND
    assert 'background:var(--card-background-color,#1d1f22)!important' in FRONTEND
    assert '--accent-color:var(--fitness-theme-accent,var(--primary-color,#03a9f4))' in FRONTEND
    assert 'border-top:2px solid var(--fitness-theme-accent,var(--primary-color,#03a9f4))!important' in FRONTEND


def test_restricted_cast_csp_allows_https_visual_assets_but_not_remote_icon_code():
    assert 'external_images = " https:" if cast_receiver else ""' in ACCOUNTS
    assert "img-src 'self' data:{external_images}" in ACCOUNTS
    assert 'cdn.jsdelivr.net' not in ACCOUNTS


def test_local_icon_subset_covers_every_static_mdi_icon_used_by_frontend():
    required = set(re.findall(r'["\\\'](mdi:[a-z0-9-]+)["\\\']', FRONTEND))
    bundled = set(re.findall(r'"(mdi:[a-z0-9-]+)":', ICONS))
    assert required
    assert required - bundled == set()
    assert len(bundled) >= 200
