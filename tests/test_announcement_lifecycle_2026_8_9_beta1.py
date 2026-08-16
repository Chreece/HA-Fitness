from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]

M = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")

F = (
    ROOT / "custom_components/fitness/feedback.py"
).read_text(encoding="utf-8")


def test_beta1_version():
    manifest = json.loads(
        (
            ROOT
            / "custom_components/fitness/manifest.json"
        ).read_text()
    )

    assert manifest["version"] == "0.0.0" or re.fullmatch(
        r"\d{4}\.\d{1,2}\.\d+(?:-(?:alpha|beta)\d+)?",
        manifest["version"],
    )


def test_full_session_event_policy():
    start = M.index(
        "async def _async_session_guidance_message"
    )

    end = M.index(
        "async def _async_announce_session_guidance",
        start,
    )

    section = M[start:end]

    for event in (
        "waiting_live",
        "started_with_live",
        "live_available",
        "paused",
        "resumed",
        "recovery_wait",
        "recovery_checkpoint",
        "recovery_complete",
        "no_recovery",
    ):
        assert f'"{event}"' in section

    assert "MANDATORY OUTPUT LANGUAGE:" in section


def test_pause_resume_are_spoken():
    assert 'self._queue_session_guidance("paused")' in M
    assert 'self._queue_session_guidance("resumed")' in M


def test_all_hrr_checkpoints_are_spoken():
    start = M.index(
        "async def _async_collect_heart_rate_recovery"
    )

    end = M.index(
        "def session_duration",
        start,
    )

    section = M[start:end]

    for seconds in (10, 30, 60, 120):
        assert f"({seconds}," in section

    assert (
        "remaining = max(0, 120 - seconds)"
        in section
    )

    assert '"recovery_checkpoint"' in section
    assert "collected=(hr is not None)" in section

    assert (
        'await self._async_announce_session_guidance('
        in section
    )

    assert '"recovery_complete"' in section

    assert "recovery_completed = False" in section
    assert "recovery_completed = True" in section


def test_periodic_coaching_uses_all_primary_live_metrics():
    for key in (
        "heart_rate_bpm",
        "power_w",
        "cadence_per_min",
        "speed_kmh",
        "distance_km",
        "altitude_m",
    ):
        assert f"'{key}'" in M

    assert "'available_live_metrics'" in M


def test_periodic_ai_has_motivation_and_language():
    start = M.index(
        "async def _async_periodic_live_message"
    )

    end = M.index(
        "def _static_smart_live_message",
        start,
    )

    section = M[start:end]

    assert "available_live_metrics" in section
    assert "motivational" in section
    assert "MANDATORY OUTPUT LANGUAGE:" in section


def test_static_fallbacks_cover_all_languages():
    for code in (
        "en",
        "el",
        "de",
        "fr",
        "es",
        "it",
        "pt",
        "nl",
        "pl",
        "ru",
        "uk",
        "tr",
        "zh",
        "ja",
        "ko",
    ):
        assert f'"{code}":' in F

    assert '"paused":' in F
    assert '"resumed":' in F

    assert "_SESSION_MOTIVATION" in F
    assert "_SESSION_CONGRATULATION" in F


def test_final_congratulation_requires_rich_data():
    assert "rich_count" in M
    assert "rich = rich_count >= 3" in M

    assert "static_congratulation(" in M

    assert (
        "congratulatory motivational"
        in M
    )
