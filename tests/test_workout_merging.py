import sys
import types
from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

pkg = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
pkg.__path__ = [str(FITNESS.parent.parent)]
fitness_pkg = sys.modules.setdefault("custom_components.fitness", types.ModuleType("custom_components.fitness"))
fitness_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault("custom_components.fitness.providers", types.ModuleType("custom_components.fitness.providers"))
providers_pkg.__path__ = [str(FITNESS / "providers")]

if "custom_components.fitness.const" not in sys.modules:
    load_module("custom_components.fitness.const", "const.py")

workouts = load_module("custom_components.fitness.providers.workouts", "providers/workouts.py")
Workout = workouts.Workout


def test_same_garmin_strava_run_merges_and_enriches():
    garmin = Workout(
        source="garmin",
        sport="running",
        start="2026-08-09T16:02:00+00:00",
        duration_s=2712,
        distance_m=8400,
        avg_hr=151,
        provider_domains=["garmin_connect"],
    )
    strava = Workout(
        source="strava",
        sport="run",
        start="2026-08-09T16:02:12+00:00",
        duration_s=2710,
        distance_m=8390,
        avg_power=287,
        elevation_gain_m=84,
        provider_domains=["strava"],
    )

    merged = workouts.merged_workouts([garmin, strava])
    assert len(merged) == 1
    result = merged[0]
    assert result.avg_hr == 151
    assert result.avg_power == 287
    assert result.elevation_gain_m == 84
    assert set(result.provider_domains) == {"garmin_connect", "strava"}


def test_different_sports_never_merge():
    a = Workout(source="a", sport="running", start="2026-08-09T16:00:00+00:00", duration_s=1800, distance_m=5000)
    b = Workout(source="b", sport="cycling", start="2026-08-09T16:00:05+00:00", duration_s=1800, distance_m=5000)
    assert len(workouts.merged_workouts([a, b])) == 2


def test_nearby_separate_runs_do_not_merge_on_conflicting_duration_distance():
    a = Workout(source="a", sport="running", start="2026-08-09T16:00:00+00:00", duration_s=1200, distance_m=3000)
    b = Workout(source="b", sport="running", start="2026-08-09T16:04:00+00:00", duration_s=900, distance_m=2000)
    assert len(workouts.merged_workouts([a, b])) == 2


def test_sparse_provider_can_merge_with_nearly_identical_start():
    sparse = Workout(source="provider_a", sport="workout", start="2026-08-09T16:00:00+00:00")
    rich = Workout(source="provider_b", sport="running", start="2026-08-09T16:00:20+00:00", duration_s=1800, distance_m=5000)
    assert len(workouts.merged_workouts([sparse, rich])) == 1


def test_one_minute_apart_needs_supporting_evidence():
    a = Workout(source="a", sport="running", start="2026-08-09T16:00:00+00:00")
    b = Workout(source="b", sport="running", start="2026-08-09T16:01:00+00:00")
    assert len(workouts.merged_workouts([a, b])) == 2


def test_complete_link_prevents_transitive_chain_merge():
    a = Workout(source="a", sport="running", start="2026-08-09T16:00:00+00:00", duration_s=1800)
    b = Workout(source="b", sport="running", start="2026-08-09T16:01:00+00:00", duration_s=1900)
    c = Workout(source="c", sport="running", start="2026-08-09T16:02:00+00:00", duration_s=2000)

    # A↔B and B↔C are plausible, but A↔C lacks enough evidence at the larger
    # time separation; complete-link grouping must not silently chain all three.
    groups = workouts.merged_workouts([a, b, c])
    assert len(groups) >= 2


def test_provider_disagreement_is_preserved():
    rich = Workout(
        source="garmin",
        sport="running",
        start="2026-08-09T16:00:00+00:00",
        duration_s=1800,
        distance_m=5000,
        avg_hr=150,
        max_hr=180,
        provider_domains=["garmin_connect"],
    )
    other = Workout(
        source="strava",
        sport="running",
        start="2026-08-09T16:00:05+00:00",
        duration_s=1805,
        distance_m=5010,
        avg_hr=151,
        provider_domains=["strava"],
    )
    merged = workouts.merged_workouts([rich, other])[0]
    assert merged.avg_hr in (150, 151)
    assert merged.provider_values
