from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKOUTS = (ROOT / "custom_components/fitness/providers/workouts.py").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
CYCPLUS = (ROOT / "custom_components/fitness/device_adapters/cycplus_m1.py").read_text()
GARMIN_FIT = (ROOT / "custom_components/fitness/device_adapters/garmin/fit.py").read_text()


def test_v121_promotes_gps_to_first_class_durable_workout_field():
    assert "gps_track: list[list[float]] | None = None" in WORKOUTS
    assert 'result["gps_track"] = _persistent_route(self.gps_track)' in WORKOUTS
    assert "PERSISTENCE_MAX_ROUTE_POINTS = 2048" in WORKOUTS
    assert "self.gps_track = _find_route(self.extra, self.provider_values)" in WORKOUTS


def test_fit_adapters_write_canonical_route_not_only_extra_payload():
    assert "gps_track=_gps_points(relevant)" in CYCPLUS
    assert "gps_track=_gps_points(relevant)" in GARMIN_FIT


def test_dashboard_prefers_canonical_route_before_legacy_provenance_recovery():
    assert 'track = _route_points(data.get("gps_track")) or _route_points(extra)' in DASHBOARD
    assert 'track = _route_points(data.get("provider_values") or {})' in DASHBOARD
    assert '["gps_track",w?.gps_track]' in FRONTEND


def test_ai_cards_coalesce_resize_bursts_and_bottom_anchor_is_preserved():
    assert 'cardId === "ai_today" || cardId === "training_plan"' in FRONTEND
    assert "__fitnessAiResizeTimer" in FRONTEND
    assert 'scrollbarGutter = "stable"' in FRONTEND
    assert "bottomSurface.scrollTop = target" not in FRONTEND


def test_v121_frontend_cache_contract():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in FRONTEND
