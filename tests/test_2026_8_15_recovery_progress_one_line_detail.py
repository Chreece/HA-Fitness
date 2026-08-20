from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
BACKEND = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_recovery_progress_owns_compact_ready_remaining_and_certainty_detail():
    assert 'const recoveryProgressDetail = recoveryComplete' in FRONTEND
    assert "l.recovery_done_short" in FRONTEND
    assert "l.ready_at_compact" in FRONTEND
    assert "l.remaining_compact" in FRONTEND
    assert "l.certain_compact" in FRONTEND
    assert 'detail:recoveryProgressDetail' in FRONTEND
    assert 'Math.round(recoveryPct) >= 100' in FRONTEND
    assert 'class="next-main"' not in FRONTEND
    assert 'class="next-confidence"' not in FRONTEND


def test_same_day_ready_time_is_compact_localized_and_detail_stays_one_line():
    assert 'format(0, "day")' in FRONTEND
    assert 'return `${day} ${timeText}`;' in FRONTEND
    assert 'at_time || "at"' not in FRONTEND
    assert 'Math.round(remaining * 60)' in FRONTEND
    assert "l.minutes_short" in FRONTEND
    assert '.recovery-score-progress .recovery-score-detail{white-space:nowrap' in FRONTEND
    assert 'overflow-x:auto' in FRONTEND


def test_compact_recovery_wording_is_translatable_in_every_supported_language():
    for code in ("en","el","de","fr","es","it","pt","nl","pl","ru","uk","tr","zh","ja","ko"):
        row = next(
            line for line in BACKEND.splitlines()
            if line.startswith(f'    "{code}": {{') and 'recovery_from_last_workout' in line
        )
        for key in (
            "recovery_done_short", "ready_at_compact", "remaining_compact",
            "certain_compact", "minutes_short",
        ):
            assert f'"{key}":' in row


def test_dashboard_resource_version_remains_synchronized():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in FRONTEND
    assert '?v=unreleased-110' in BACKEND
