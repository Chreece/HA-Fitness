from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_workout_browser_request_limit_matches_backend_contract():
    assert 'vol.Range(min=1, max=500)' in DASHBOARD
    assert 'type:"fitness/workouts/list",profile_entry_id:this._profileId,limit:500' in FRONTEND


def test_workout_browser_does_not_flash_empty_before_successful_load():
    assert 'this._loading||!this._loaded' in FRONTEND
    assert 'this._loading=true;this._render();try' in FRONTEND
    assert 'this._error?`<div class="muted">' in FRONTEND


def test_card_picker_is_offset_below_toolbar():
    source = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
    assert "padding:28px 12px 12px!important" in source
    assert "max-height:calc(100dvh - var(--modal-top,68px) - 48px)" in source
