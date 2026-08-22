from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()


def test_cast_cards_have_outer_surface_before_shadow_dom():
    assert ':host([fitness-cast-receiver]) .tv-card-slot:not(.fitness-empty-card),' in JS
    assert ':host([fitness-cast-receiver]) .tv-card-slot:not(.fitness-empty-card)>.tv-mounted-card{' in JS
    assert 'background-color:var(--ha-card-background,var(--card-background-color,#1d1f22))!important' in JS
    assert 'border-radius:var(--ha-card-border-radius,var(--fitness-theme-radius,22px))!important' in JS


def test_cast_surface_fix_is_cache_busted_for_both_receiver_paths():
    assert '_RESOURCE_URL += "&build=cast-ui-155"' in DASH
    assert 'frontend_cache_version = f"{frontend_version}-cast-ui-155"' in ACCOUNTS
