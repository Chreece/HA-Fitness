"""Data-driven vendor/product registry for native fitness sensors.

Runtime transports never contain vendor names, company identifiers or
proprietary byte offsets. Those facts live in device_catalog.json.
"""
from __future__ import annotations

from typing import Any

from .device_identity import load_catalog


def _text(value: Any) -> str:
    return str(value or "").strip()


def _clean(value: Any) -> str:
    return "".join(ch for ch in _text(value).lower() if ch.isalnum())


def catalog_manufacturer_name(namespace: str, identifier: Any) -> str | None:
    """Resolve a protocol manufacturer identifier from the catalog."""
    manufacturers = load_catalog().get("manufacturers", {}) or {}
    mapping = manufacturers.get(str(namespace), {}) or {}
    value = mapping.get(str(identifier))
    return str(value) if value not in (None, "") else None


def _bluetooth_observation(info) -> dict[str, Any]:
    manufacturer_data = getattr(info, "manufacturer_data", {}) or {}
    service_data = getattr(info, "service_data", {}) or {}
    return {
        "name": _text(getattr(info, "name", None)),
        "transport": "bluetooth",
        "manufacturer_data_ids": {int(key) for key in manufacturer_data},
        "service_uuids": {
            str(value).lower()
            for value in (getattr(info, "service_uuids", None) or [])
        },
        "service_data_ids": {str(key).lower() for key in service_data},
        "manufacturer_data": manufacturer_data,
        "service_data": service_data,
    }


def _matches_observation_rule(rule: dict[str, Any], observation: dict[str, Any]) -> bool:
    prefix = _text(rule.get("name_prefix"))
    if prefix and not _clean(observation.get("name")).startswith(_clean(prefix)):
        return False

    transport = rule.get("transport")
    if transport and str(transport) != str(observation.get("transport")):
        return False

    if "manufacturer_data_id" in rule:
        if int(rule["manufacturer_data_id"]) not in observation.get("manufacturer_data_ids", set()):
            return False

    if "service_uuid" in rule:
        if str(rule["service_uuid"]).lower() not in observation.get("service_uuids", set()):
            return False

    # Rules with only a name prefix are valid. Rules without any supported
    # observable discriminator are not considered a match here.
    return bool(
        prefix
        or "manufacturer_data_id" in rule
        or "service_uuid" in rule
    )


def _matching_products(observation: dict[str, Any]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for product in load_catalog().get("products", []) or []:
        if not isinstance(product, dict):
            continue
        rules = product.get("match_any") or []
        if any(
            isinstance(rule, dict)
            and _matches_observation_rule(rule, observation)
            for rule in rules
        ):
            matches.append(product)
    return matches


def _decoder_definitions() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for decoder in load_catalog().get("vendor_decoders", []) or []:
        if not isinstance(decoder, dict):
            continue
        decoder_id = _text(decoder.get("id"))
        if decoder_id:
            result[decoder_id] = decoder
    return result


def _source_payload(
    decoder: dict[str, Any], observation: dict[str, Any]
) -> bytes | None:
    source = decoder.get("source") or {}
    kind = str(source.get("kind") or "")
    source_id = source.get("id")
    if kind == "manufacturer_data":
        try:
            payload = observation.get("manufacturer_data", {}).get(int(source_id))
        except (TypeError, ValueError):
            return None
    elif kind == "service_data":
        payload = observation.get("service_data", {}).get(str(source_id).lower())
    else:
        return None
    if payload is None:
        return None
    try:
        return bytes(payload)
    except (TypeError, ValueError):
        return None


def _decode_integer(payload: bytes, field: dict[str, Any]) -> float | None:
    try:
        offset = int(field.get("offset", 0))
        length = int(field.get("length", 1))
    except (TypeError, ValueError):
        return None
    if offset < 0 or length <= 0 or offset + length > len(payload):
        return None

    encoding = str(field.get("encoding") or "uint_le")
    chunk = payload[offset : offset + length]
    if encoding == "uint_le":
        raw = int.from_bytes(chunk, byteorder="little", signed=False)
    elif encoding == "uint_be":
        raw = int.from_bytes(chunk, byteorder="big", signed=False)
    elif encoding == "int_le":
        raw = int.from_bytes(chunk, byteorder="little", signed=True)
    elif encoding == "int_be":
        raw = int.from_bytes(chunk, byteorder="big", signed=True)
    else:
        return None

    try:
        scale = float(field.get("scale", 1.0))
        add = float(field.get("add", 0.0))
    except (TypeError, ValueError):
        return None
    value = raw * scale + add

    minimum = field.get("valid_min")
    maximum = field.get("valid_max")
    if minimum is not None and value < float(minimum):
        return None
    if maximum is not None and value > float(maximum):
        return None
    return float(value)



def vendor_registry_issues() -> list[str]:
    """Return non-fatal catalog/decoder consistency problems."""
    catalog = load_catalog()
    definitions = _decoder_definitions()
    issues: list[str] = []

    referenced: set[str] = set()
    for product in catalog.get("products", []) or []:
        if not isinstance(product, dict):
            issues.append("products contains a non-object entry")
            continue
        product_id = _text(product.get("id")) or "<unnamed>"
        for decoder_id in product.get("decoder_ids") or []:
            decoder_id = _text(decoder_id)
            if not decoder_id:
                issues.append(f"{product_id}: empty decoder id")
                continue
            referenced.add(decoder_id)
            if decoder_id not in definitions:
                issues.append(f"{product_id}: unknown decoder {decoder_id}")

    for decoder_id, decoder in definitions.items():
        transport = _text(decoder.get("transport"))
        phase = _text(decoder.get("phase"))
        if transport not in {"bluetooth", "antplus"}:
            issues.append(f"{decoder_id}: unsupported transport {transport!r}")
        if phase not in {"advertisement", "packet", "gatt"}:
            issues.append(f"{decoder_id}: unsupported phase {phase!r}")
        source = decoder.get("source")
        if not isinstance(source, dict) or not _text(source.get("kind")):
            issues.append(f"{decoder_id}: missing source")
        fields = decoder.get("fields")
        if not isinstance(fields, list) or not fields:
            issues.append(f"{decoder_id}: no fields")
            continue
        for index, field in enumerate(fields):
            if not isinstance(field, dict):
                issues.append(f"{decoder_id}: field {index} is not an object")
                continue
            if not _text(field.get("metric")):
                issues.append(f"{decoder_id}: field {index} has no metric")
            try:
                if int(field.get("offset", 0)) < 0:
                    issues.append(f"{decoder_id}: field {index} has negative offset")
                if int(field.get("length", 1)) <= 0:
                    issues.append(f"{decoder_id}: field {index} has invalid length")
            except (TypeError, ValueError):
                issues.append(f"{decoder_id}: field {index} has invalid offset/length")

    # Unreferenced decoders are allowed for staged catalog expansion.
    return issues

def decode_bluetooth_advertisement(
    info,
) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    """Apply catalog-selected proprietary Bluetooth advertisement decoders."""
    observation = _bluetooth_observation(info)
    definitions = _decoder_definitions()

    decoder_ids: list[str] = []
    for product in _matching_products(observation):
        for decoder_id in product.get("decoder_ids") or []:
            decoder_id = _text(decoder_id)
            if decoder_id and decoder_id not in decoder_ids:
                decoder_ids.append(decoder_id)

    values: dict[str, float] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for decoder_id in decoder_ids:
        decoder = definitions.get(decoder_id)
        if not decoder:
            continue
        if decoder.get("transport") != "bluetooth":
            continue
        if decoder.get("phase") != "advertisement":
            continue
        payload = _source_payload(decoder, observation)
        if payload is None:
            continue
        for field in decoder.get("fields") or []:
            if not isinstance(field, dict):
                continue
            metric = _text(field.get("metric"))
            if not metric:
                continue
            value = _decode_integer(payload, field)
            if value is None:
                continue
            values[metric] = value
            field_meta = dict(field.get("metadata") or {})
            field_meta["decoder_id"] = decoder_id
            metadata[metric] = field_meta

    return values, metadata
