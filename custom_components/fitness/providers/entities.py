"""Generic entity/value helpers with unit normalization."""

from __future__ import annotations

from dataclasses import dataclass
import math

from homeassistant.core import HomeAssistant, valid_entity_id

from ..const import SOURCE_ENTITY, SOURCE_USER


@dataclass(slots=True)
class ResolvedInput:
    value: float | None
    source: str | None
    entity_id: str | None = None
    original_value: float | None = None
    original_unit: str | None = None
    canonical_unit: str | None = None


def is_entity_reference(raw) -> bool:
    return isinstance(raw, str) and valid_entity_id(raw.strip())


def validate_number_or_entity(
    raw,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
    required: bool = False,
) -> bool:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return not required

    text = str(raw).strip()
    if valid_entity_id(text):
        return True

    try:
        value = float(text)
    except (TypeError, ValueError):
        return False

    if min_value is not None and value < min_value:
        return False
    if max_value is not None and value > max_value:
        return False
    return True


def _unit_key(unit: str | None) -> str:
    if not unit:
        return ""
    return (
        str(unit)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("°", "")
        .replace("per", "/")
    )


def _convert_mass(value: float, unit: str) -> float | None:
    """Convert mass to kg."""
    u = _unit_key(unit)
    if u in ("kg", "kilogram", "kilograms", ""):
        return value
    if u in ("g", "gram", "grams"):
        return value / 1000.0
    if u in ("mg", "milligram", "milligrams"):
        return value / 1_000_000.0
    if u in ("lb", "lbs", "pound", "pounds"):
        return value * 0.45359237
    if u in ("oz", "ounce", "ounces"):
        return value * 0.028349523125
    if u in ("st", "stone", "stones"):
        return value * 6.35029318
    return None


def _convert_length_cm(value: float, unit: str) -> float | None:
    """Convert length to cm."""
    u = _unit_key(unit)
    if u in ("cm", "centimeter", "centimeters", ""):
        return value
    if u in ("m", "meter", "meters"):
        return value * 100.0
    if u in ("mm", "millimeter", "millimeters"):
        return value / 10.0
    if u in ("in", "inch", "inches"):
        return value * 2.54
    if u in ("ft", "foot", "feet"):
        return value * 30.48
    return None


def _convert_hr(value: float, unit: str) -> float | None:
    """Convert heart-rate-like values to bpm."""
    u = _unit_key(unit)
    if u in ("", "bpm", "beats/min", "beats/minute", "1/min", "min^-1"):
        return value
    if u in ("hz", "1/s", "s^-1"):
        return value * 60.0
    return None


def _convert_power(value: float, unit: str) -> float | None:
    """Convert power to watts."""
    u = _unit_key(unit)
    if u in ("", "w", "watt", "watts"):
        return value
    if u in ("kw", "kilowatt", "kilowatts"):
        return value * 1000.0
    return None


def _convert_vo2max(value: float, unit: str) -> float | None:
    """Canonical VO2max is mL/kg/min."""
    u = _unit_key(unit)
    if u in (
        "",
        "ml/kg/min",
        "ml/kg/minute",
        "ml·kg−1·min−1",
        "mlkg-1min-1",
        "ml/(kg*min)",
    ):
        return value

    # L/kg/min -> mL/kg/min
    if u in ("l/kg/min", "l/kg/minute"):
        return value * 1000.0

    return None


def _convert_pace(value: float, unit: str) -> float | None:
    """Convert pace/speed values to minutes per kilometre."""
    u = _unit_key(unit)

    if u in ("", "min/km", "minperkm", "min/km."):
        return value
    if u in ("s/km", "sec/km", "second/km", "seconds/km"):
        return value / 60.0
    if u in ("min/mi", "min/mile", "min/miles"):
        return value / 1.609344
    if u in ("s/mi", "sec/mi", "s/mile"):
        return value / 60.0 / 1.609344

    # A threshold "pace" source may actually expose speed.
    if u in ("m/s", "mps"):
        return 1000.0 / value / 60.0 if value > 0 else None
    if u in ("km/h", "kph", "kmh"):
        return 60.0 / value if value > 0 else None
    if u in ("mph", "mi/h"):
        kmh = value * 1.609344
        return 60.0 / kmh if kmh > 0 else None

    return None



def _convert_speed(value: float, unit: str) -> float | None:
    """Convert speed to km/h."""
    u = _unit_key(unit)
    if u in ("", "km/h", "kmh", "kph"):
        return value
    if u in ("m/s", "mps"):
        return value * 3.6
    if u in ("mph", "mi/h"):
        return value * 1.609344
    if u in ("ft/s", "fps"):
        return value * 1.09728
    return None


def _convert_distance(value: float, unit: str) -> float | None:
    """Convert distance to km."""
    u = _unit_key(unit)
    if u in ("", "km", "kilometer", "kilometers"):
        return value
    if u in ("m", "meter", "meters"):
        return value / 1000.0
    if u in ("mi", "mile", "miles"):
        return value * 1.609344
    if u in ("ft", "foot", "feet"):
        return value * 0.0003048
    return None


def _convert_altitude(value: float, unit: str) -> float | None:
    """Convert altitude/elevation to meters."""
    u = _unit_key(unit)
    if u in ("", "m", "meter", "meters"):
        return value
    if u in ("ft", "foot", "feet"):
        return value * 0.3048
    return None


def _convert_cadence(value: float, unit: str) -> float | None:
    """Normalize cadence to events per minute.

    rpm and spm are both rates per minute; semantics (pedal revolutions versus
    steps) remain attached to the source entity and are not treated as equal
    biomechanical quantities.
    """
    u = _unit_key(unit)
    if u in (
        "", "rpm", "spm", "1/min", "min^-1",
        "steps/min", "steps/minute", "revolutions/min",
    ):
        return value
    if u in ("hz", "1/s", "s^-1"):
        return value * 60.0
    return None


def convert_to_canonical(
    value: float,
    unit: str | None,
    quantity: str | None,
) -> tuple[float | None, str | None]:
    """Convert an entity value into Fitness' canonical internal unit."""
    if quantity is None:
        return value, unit

    converters = {
        "weight": (_convert_mass, "kg"),
        "height": (_convert_length_cm, "cm"),
        "heart_rate": (_convert_hr, "bpm"),
        "power": (_convert_power, "W"),
        "vo2max": (_convert_vo2max, "mL/kg/min"),
        "pace": (_convert_pace, "min/km"),
        "speed": (_convert_speed, "km/h"),
        "distance": (_convert_distance, "km"),
        "altitude": (_convert_altitude, "m"),
        "cadence": (_convert_cadence, "1/min"),
    }

    item = converters.get(quantity)
    if item is None:
        return value, unit

    converter, canonical = item
    converted = converter(value, unit or "")
    return converted, canonical


def resolve_number_or_entity(
    hass: HomeAssistant,
    raw,
    *,
    quantity: str | None = None,
) -> ResolvedInput:
    """Resolve a direct number or entity and normalize entity units.

    Direct numeric values are interpreted in the canonical unit documented by
    the setup field. Entity values are converted from their unit_of_measurement.
    """
    if raw is None:
        return ResolvedInput(None, None)

    text = str(raw).strip()
    if not text:
        return ResolvedInput(None, None)

    if valid_entity_id(text):
        state = hass.states.get(text)
        if state is None or state.state in ("unknown", "unavailable", ""):
            return ResolvedInput(None, SOURCE_ENTITY, text)

        try:
            original = float(state.state)
        except (TypeError, ValueError):
            return ResolvedInput(None, SOURCE_ENTITY, text)

        original_unit = state.attributes.get("unit_of_measurement")
        converted, canonical = convert_to_canonical(
            original,
            original_unit,
            quantity,
        )

        return ResolvedInput(
            converted,
            SOURCE_ENTITY,
            text,
            original_value=original,
            original_unit=original_unit,
            canonical_unit=canonical,
        )

    try:
        value = float(text)
    except (TypeError, ValueError):
        return ResolvedInput(None, None)

    canonical_units = {
        "weight": "kg",
        "height": "cm",
        "heart_rate": "bpm",
        "power": "W",
        "vo2max": "mL/kg/min",
        "pace": "min/km",
        "speed": "km/h",
        "distance": "km",
        "altitude": "m",
        "cadence": "1/min",
    }

    return ResolvedInput(
        value,
        SOURCE_USER,
        original_value=value,
        canonical_unit=canonical_units.get(quantity),
    )


def numeric_entity_state(
    hass: HomeAssistant,
    entity_id: str | None,
    *,
    quantity: str | None = None,
) -> float | None:
    if not entity_id:
        return None

    resolved = resolve_number_or_entity(
        hass,
        entity_id,
        quantity=quantity,
    )
    return resolved.value
