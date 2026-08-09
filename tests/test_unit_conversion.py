import sys
import types
import pytest
from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

# Minimal package namespace so relative imports resolve without loading the
# integration's Home Assistant-dependent __init__.py.
pkg = types.ModuleType("custom_components")
pkg.__path__ = [str(FITNESS.parent.parent)]
sys.modules.setdefault("custom_components", pkg)

fitness_pkg = types.ModuleType("custom_components.fitness")
fitness_pkg.__path__ = [str(FITNESS)]
sys.modules.setdefault("custom_components.fitness", fitness_pkg)

providers_pkg = types.ModuleType("custom_components.fitness.providers")
providers_pkg.__path__ = [str(FITNESS / "providers")]
sys.modules.setdefault("custom_components.fitness.providers", providers_pkg)

const = load_module("custom_components.fitness.const", "const.py")
entities = load_module("custom_components.fitness.providers.entities", "providers/entities.py")


@pytest.mark.parametrize(
    ("value", "unit", "quantity", "expected", "canonical"),
    [
        (165.3467, "lb", "weight", 75.0, "kg"),
        (6.0, "ft", "height", 182.88, "cm"),
        (2.0, "Hz", "heart_rate", 120.0, "bpm"),
        (0.25, "kW", "power", 250.0, "W"),
        (4.0, "m/s", "pace", 4.1666667, "min/km"),
        (12.0, "km/h", "pace", 5.0, "min/km"),
        (10.0, "mph", "speed", 16.09344, "km/h"),
        (5.0, "mi", "distance", 8.04672, "km"),
        (1000.0, "ft", "altitude", 304.8, "m"),
        (2.0, "Hz", "cadence", 120.0, "1/min"),
    ],
)
def test_convert_to_canonical(value, unit, quantity, expected, canonical):
    converted, actual_unit = entities.convert_to_canonical(value, unit, quantity)
    assert converted == pytest.approx(expected, rel=1e-6)
    assert actual_unit == canonical


def test_unsupported_unit_is_rejected():
    value, unit = entities.convert_to_canonical(75, "bananas", "weight")
    assert value is None
    assert unit == "kg"


def test_number_or_entity_validation():
    assert entities.validate_number_or_entity("sensor.weight", required=True)
    assert entities.validate_number_or_entity("75", min_value=20, max_value=300)
    assert not entities.validate_number_or_entity("nope", required=True)
    assert not entities.validate_number_or_entity("5", min_value=20)
