"""Canonical identity resolution for merged ANT+/Bluetooth fitness sensors."""
from __future__ import annotations
import json
from pathlib import Path
import re
from typing import Any

CATALOG_PATH = Path(__file__).with_name("device_catalog.json")

_FIELD_ALIASES = {
    "manufacturer_name": "manufacturer", "manufacturer": "manufacturer",
    "model_name": "model", "model": "model", "model_number_string": "model",
    "model_no": "model_id",
    "serial": "serial_number", "serial_no": "serial_number",
    "device_serial": "serial_number", "serial_number": "serial_number",
    "hardware_revision": "hw_version", "hardware_rev": "hw_version", "hw_version": "hw_version",
    "software_revision": "sw_version", "software_ver": "sw_version", "sw_version": "sw_version",
    "firmware_revision": "firmware_version", "firmware_version": "firmware_version",
    "model_id": "model_id",
}

def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip("\x00 ")
    return value or None

def _clean(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

def _numeric_only(value: Any) -> bool:
    text = _text(value)
    return bool(text and re.fullmatch(r"[0-9._-]+", text))

def _looks_address(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", text))

_EMPTY_CATALOG: dict[str, Any] = {
    "version": 1,
    "manufacturers": {},
    "products": [],
    "profile_models": {},
}

def _load_catalog_at_import() -> dict[str, Any]:
    """Load the optional recognition catalog outside radio callbacks.

    A missing, truncated, or malformed catalog must never prevent Fitness from
    starting. Identity recognition degrades to protocol/GATT facts instead.
    """
    try:
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        return dict(_EMPTY_CATALOG)
    return raw if isinstance(raw, dict) else dict(_EMPTY_CATALOG)

_CATALOG = _load_catalog_at_import()

def load_catalog() -> dict[str, Any]:
    """Return the immutable process-local catalog snapshot."""
    return _CATALOG

def canonical_identity_fields(metadata: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in metadata.items():
        target = _FIELD_ALIASES.get(str(key))
        if target is None:
            continue
        text = _text(value)
        if text is None:
            continue
        if target == "model" and _numeric_only(text):
            result.setdefault("model_id", text)
            continue
        result[target] = text
    return result

def _catalog_manufacturer(endpoints: dict[str, Any]) -> str | None:
    catalog = load_catalog().get("manufacturers", {})
    ant_map = catalog.get("antplus", {}) or {}
    bt_map = catalog.get("bluetooth_manufacturer_data", {}) or {}
    ant = endpoints.get("antplus")
    if ant is not None:
        mid = ant.metadata.get("manufacturer_id")
        if mid is not None and str(mid) in ant_map:
            return str(ant_map[str(mid)])
    bt = endpoints.get("bluetooth")
    if bt is not None:
        for value in bt.metadata.get("manufacturer_data_ids") or []:
            if str(value) in bt_map:
                return str(bt_map[str(value)])
    return None

def _matches_rule(rule: dict[str, Any], name: str, endpoints: dict[str, Any]) -> bool:
    prefix = _text(rule.get("name_prefix"))
    if prefix and _clean(name).startswith(_clean(prefix)):
        return True
    transport = rule.get("transport")
    if not transport:
        return False
    endpoint = endpoints.get(str(transport))
    if endpoint is None:
        return False
    if "manufacturer_id" in rule and endpoint.metadata.get("manufacturer_id") != rule.get("manufacturer_id"):
        return False
    if "manufacturer_data_id" in rule and rule.get("manufacturer_data_id") not in (endpoint.metadata.get("manufacturer_data_ids") or []):
        return False
    if "model_no" in rule and endpoint.metadata.get("model_no") != rule.get("model_no"):
        return False
    return True


def catalog_product_id(name: str, endpoints: dict[str, Any]) -> str | None:
    """Return the data-driven product-family ID for safe cross-transport merge."""
    for product in load_catalog().get("products", []) or []:
        if not isinstance(product, dict):
            continue
        rules = product.get("match_any") or []
        if any(isinstance(rule, dict) and _matches_rule(rule, name, endpoints) for rule in rules):
            value = _text(product.get("id"))
            if value:
                return value
    return None

def _catalog_product(name: str, endpoints: dict[str, Any]) -> dict[str, str]:
    for product in load_catalog().get("products", []) or []:
        if not isinstance(product, dict):
            continue
        rules = product.get("match_any") or []
        if any(isinstance(rule, dict) and _matches_rule(rule, name, endpoints) for rule in rules):
            return {key: str(product[key]) for key in ("name", "manufacturer", "model", "model_id") if product.get(key) not in (None, "")}
    return {}

def _generic_profile_model(endpoints: dict[str, Any]) -> str | None:
    ant = endpoints.get("antplus")
    if ant is None:
        return None
    profiles = [int(x) for x in (ant.metadata.get("profiles") or []) if str(x).isdigit()]
    models = load_catalog().get("profile_models", {}) or {}
    names = [str(models[str(profile)]) for profile in profiles if str(profile) in models]
    return names[0] if names else None

def resolve_identity(sensor) -> dict[str, Any]:
    candidates: dict[str, tuple[int, str]] = {}
    def offer(field: str, value: Any, score: int) -> None:
        text = _text(value)
        if text is None:
            return
        if field == "model" and _numeric_only(text):
            offer("model_id", text, score)
            return
        previous = candidates.get(field)
        if previous is None or score > previous[0]:
            candidates[field] = (score, text)

    for key, value in canonical_identity_fields(sensor.metadata).items():
        offer(key, value, 60)
    for transport, endpoint in sensor.endpoints.items():
        # Standard GATT Device Information is the most specific product identity
        # source. Catalog rules fill gaps / prettify generic protocol IDs, but do
        # not override an exact model/revision reported by the device itself.
        base = 100 if endpoint.metadata.get("identity_source") == "gatt_device_information" else (65 if transport == "antplus" else 55)
        for key, value in canonical_identity_fields(endpoint.metadata).items():
            offer(key, value, base)

    product = _catalog_product(sensor.name, sensor.endpoints)
    for key, value in product.items():
        offer(key, value, 90)
    manufacturer = _catalog_manufacturer(sensor.endpoints)
    if manufacturer:
        offer("manufacturer", manufacturer, 75)
    generic_model = _generic_profile_model(sensor.endpoints)
    if generic_model:
        offer("model", generic_model, 35)
    if "firmware_version" in candidates:
        offer("sw_version", candidates["firmware_version"][1], candidates["firmware_version"][0] + 1)

    identity = {key: value for key, (_score, value) in candidates.items()}
    name = product.get("name")
    if not name:
        advertised = _text(sensor.name)
        if advertised and advertised != "Fitness sensor" and not _looks_address(advertised) and not _numeric_only(advertised):
            if not re.fullmatch(r".+\s+[0-9._-]+", advertised):
                name = advertised
    if not name:
        manufacturer = identity.get("manufacturer")
        model = identity.get("model")
        if manufacturer and model:
            name = model if _clean(manufacturer) in _clean(model) else f"{manufacturer} {model}"
        elif model:
            name = model
        elif manufacturer and generic_model:
            name = f"{manufacturer} {generic_model}"
        elif generic_model:
            name = generic_model
        else:
            name = "Fitness sensor"
    identity["name"] = name
    identity["ready"] = bool(product or identity.get("model") or (identity.get("manufacturer") and identity.get("serial_number")))
    return identity
