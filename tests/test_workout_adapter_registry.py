import sys
import types

from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

pkg = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
pkg.__path__ = [str(FITNESS.parent.parent)]
fitness_pkg = sys.modules.setdefault(
    "custom_components.fitness",
    types.ModuleType("custom_components.fitness"),
)
fitness_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault(
    "custom_components.fitness.providers",
    types.ModuleType("custom_components.fitness.providers"),
)
providers_pkg.__path__ = [str(FITNESS / "providers")]
adapters_pkg = sys.modules.setdefault(
    "custom_components.fitness.providers.workout_adapters",
    types.ModuleType("custom_components.fitness.providers.workout_adapters"),
)
adapters_pkg.__path__ = [str(FITNESS / "providers" / "workout_adapters")]

if "custom_components.fitness.const" not in sys.modules:
    load_module("custom_components.fitness.const", "const.py")
if "custom_components.fitness.providers.workouts" not in sys.modules:
    load_module(
        "custom_components.fitness.providers.workouts",
        "providers/workouts.py",
    )

base = load_module(
    "custom_components.fitness.providers.workout_adapters.base",
    "providers/workout_adapters/base.py",
)


def test_duration_parser_supports_iso8601_and_units():
    assert base.duration_seconds("PT1H2M3S") == 3723
    assert base.duration_seconds(5, "min") == 300
    assert base.duration_seconds(2, "h") == 7200


def test_distance_and_speed_normalization():
    assert base.distance_meters(5, "km") == 5000
    assert round(base.distance_meters(1, "mi"), 3) == 1609.344
    assert base.speed_m_s(36, "km/h") == 10
    assert round(base.speed_m_s(10, "mph"), 5) == 4.4704


def test_registry_has_explicit_provider_owners():
    # Import adapters first because registry imports them by package name.
    for name in ("garmin", "strava", "polar", "hevy", "peloton", "oura", "generic"):
        load_module(
            f"custom_components.fitness.providers.workout_adapters.{name}",
            f"providers/workout_adapters/{name}.py",
        )
    registry = load_module(
        "custom_components.fitness.providers.workout_adapters.registry",
        "providers/workout_adapters/registry.py",
    )

    supported = registry.supported_adapter_domains()
    assert supported["garmin"] == ("garmin_connect",)
    assert "ha_strava" in supported["strava"]
    assert supported["polar"] == ("polar",)
    assert supported["hevy"] == ("hevy",)
    assert supported["peloton"] == ("peloton",)
    assert supported["oura"] == ("oura",)

    domains = [domain for values in supported.values() for domain in values]
    assert len(domains) == len(set(domains))
