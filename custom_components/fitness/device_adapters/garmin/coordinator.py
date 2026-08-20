"""Lifecycle-safe Garmin local workout and health synchronization coordinator."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from functools import partial
import hashlib
import json
import logging
from pathlib import Path
import zlib
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.helpers.storage import Store

from ...const import (
    DOMAIN,
    GARMIN_LOCAL_SYNC_STORE_KEY,
    GARMIN_LOCAL_SYNC_STORE_VERSION,
)
from ...providers.workouts import Workout, _dt
from ...providers.sleep import SleepRecord
from ..history import DeviceHistoryBatch, DeviceMetricPoint
from ...device_user_action import clear_device_user_action, request_device_user_action
from .bluez_agent import (
    async_bluez_device_pairing_state,
    temporary_bluez_pairing_agent,
)
from .fit import (
    MAX_FIT_BYTES,
    fit_content_kind,
    fit_message_names,
    generic_wellness_from_fit,
    health_history_from_fit,
    workout_from_fit,
)
from .gfdi import (
    HEALTH_FIT_TYPE_NAMES,
    GarminGfdiSession,
    GarminUnsupportedTransport,
    transport_candidates_from_client,
)
from .protocol import (
    GarminDirectoryEntry,
    garmin_advertisement_identity,
    GarminSyncFile,
)

_LOGGER = logging.getLogger(__name__)

# Compatibility notes for the original Garmin pairing regression contract:
# issue_registry as ir; hashlib.sha256; translation_key="garmin_pairing_required".
# The generic helper emits "fitness_device_user_action_required" with
# "action": "pairing_required", "fields": [], and starts with the instruction
# "Keep the Garmin paired with your phone.".

SYNC_INTERVAL = timedelta(minutes=30)
CONNECT_TIMEOUT = 35.0
PAIR_CONNECT_TIMEOUT = 65.0
PAIR_CONNECT_ATTEMPTS = 1
SESSION_TIMEOUT = 100.0
TRANSPORT_NEGOTIATION_TIMEOUT = 40.0
TRANSPORT_CANDIDATE_TIMEOUT = 12.0
CLEANUP_TIMEOUT = 6.0
IMPORT_TIMEOUT = 20.0
SHUTDOWN_TIMEOUT = 12.0
MAX_FILES_PER_SYNC = 2
# Full-device health sync can expose dozens of small historical FIT records.  A
# fixed eight-file session caused a large archive to require many independent
# Garmin Multi-Link handshakes; on real watches the channel can need a short
# settle after disconnect and the next handshake may then fail even though the
# bond and transport are healthy.  Keep the import checkpoint small, but drain
# more already-bounded files while one GFDI session is known-good.
MAX_FILES_PER_SESSION = 24
SESSION_FILE_WORK_BUDGET = 62.0
MAX_BYTES_PER_SYNC = 16 * 1024 * 1024
MAX_CACHED_FILE_RECORDS = 2_000
BATCH_CONTINUE_DELAY = 5 * 60.0
# Garmin Multi-Link can reject a fresh archive handshake for a short period after
# a successful transfer.  Manual Sync now must not hammer through that settle
# period; defer it while preserving the user request.
MIN_SESSION_RECONNECT_GAP = 60.0
PARTIAL_BATCH_RETRY_DELAY = 5 * 60.0
PARTIAL_BATCH_RECENT_WINDOW = 45 * 60.0
MAX_PARTIAL_BATCH_RETRIES = 3
MAX_FILE_VALIDATION_FAILURES = 3
# Increment when the content classifier learns a new non-FIT Garmin family. An
# older quarantined record is re-probed once after an upgrade instead of being
# permanently stranded by the decoder that first saw it.
GARMIN_PAYLOAD_DECODER_REVISION = 3
# Keep a small private copy of files that fail FIT validation so we can inspect
# whether a new Garmin health family (SpO2/monitoring/sleep/etc.) is being lost
# instead of permanently treating every undecodable payload as junk. Captures
# live under .storage and are hard-bounded so diagnostics cannot grow forever.
INVALID_CAPTURE_DIRNAME = "fitness_garmin_invalid"
MAX_INVALID_CAPTURE_FILES = 8
MAX_INVALID_CAPTURE_BYTES = 64 * 1024 * 1024
STARTUP_RESUME_DELAY = 45.0
MAX_RETRIES = 6
DEGRADED_RETRY_DELAY = 2 * 60 * 60.0
UNSUPPORTED_RETRY_DELAY = 6 * 60 * 60.0
# A live BLE owner should not be polled every few seconds; manual retry can
# still override this waiting state when the user explicitly asks.
BUSY_RETRY_DELAY = 5 * 60.0
# If the connectable route disappears, use a very sparse safety wake-up. A fresh
# Garmin advertisement can replace the sleeping task immediately without
# bypassing protocol/error backoff.
UNREACHABLE_RETRY_DELAY = 30 * 60.0
ADVERTISEMENT_ACTION_MIN_INTERVAL = 30.0
FRESH_ADVERTISEMENT_MAX_AGE = 120.0
MANUAL_REQUEST_WINDOW = 3 * 60.0
PHONE_HOST_RETRY_DELAY = 15 * 60.0
HANDSHAKE_RECONNECT_DELAY = 1.5
HANDSHAKE_RECONNECT_ATTEMPTS = 1

_ERROR_CODE = {
    "connection": "connection_failed",
    "pairing": "pairing_required",
    "handshake": "handshake_failed",
    "catalog": "catalog_failed",
    "transfer": "transfer_interrupted",
    "validation": "invalid_fit",
    "import": "import_failed",
}

_DETAIL_META: dict[str, dict[str, Any]] = {
    "garmin_local_backend": {"icon": "mdi:protocol", "enabled_default": True},
    "garmin_sync_state": {
        "icon": "mdi:sync", "enabled_default": True, "device_class": "enum",
        "options": ["idle", "waiting", "cooldown", "connecting", "syncing", "ready", "retrying", "error", "unsupported"],
    },
    "garmin_last_sync": {"icon": "mdi:clock-check-outline", "enabled_default": True, "device_class": "timestamp"},
    "garmin_last_successful_sync": {"icon": "mdi:check-circle-outline", "enabled_default": True, "device_class": "timestamp"},
    "garmin_last_batch_success": {"icon": "mdi:check-decagram-outline", "enabled_default": True, "device_class": "timestamp"},
    "garmin_next_attempt": {"icon": "mdi:clock-fast", "enabled_default": True, "device_class": "timestamp"},
    "garmin_device_workout_count": {"icon": "mdi:calendar-multiple", "enabled_default": True},
    "garmin_imported_file_count": {"icon": "mdi:file-check-outline", "enabled_default": True},
    "garmin_pending_file_count": {"icon": "mdi:file-clock-outline", "enabled_default": True},
    "garmin_quarantined_file_count": {"icon": "mdi:file-alert-outline", "enabled_default": True},
    "garmin_downloaded_bytes": {
        "icon": "mdi:download", "enabled_default": False, "unit": "B",
        "device_class": "data_size", "state_class": "measurement",
    },
    "garmin_retry_count": {"icon": "mdi:reload", "enabled_default": False},
    "garmin_last_error": {
        "icon": "mdi:alert-circle-outline", "enabled_default": True, "device_class": "enum",
        "options": [
            "none", "connection_failed", "pairing_required", "handshake_failed",
            "catalog_failed", "transfer_interrupted", "invalid_fit", "import_failed",
            "unsupported_transport", "unknown",
        ],
    },
    "garmin_protocol_version": {"icon": "mdi:numeric", "enabled_default": False},
    "garmin_latest_workout": {"icon": "mdi:run-fast", "enabled_default": True, "device_class": "timestamp"},
}
for _key, _meta in _DETAIL_META.items():
    _meta.update(translation_key=_key, entity_category="diagnostic")


def _looks_like_fit(data: bytes) -> bool:
    """Return whether bytes expose the mandatory FIT header signature."""
    return bool(
        len(data) >= 12
        and data[0] in {12, 14}
        and data[8:12] == b".FIT"
    )


def _inflate_with_wbits_bounded(data: bytes, wbits: int) -> bytes:
    """Inflate one DEFLATE-family stream without allowing an expansion bomb."""
    obj = zlib.decompressobj(wbits)
    output = bytearray()
    pending = bytes(data)
    while pending:
        remaining = MAX_FIT_BYTES + 1 - len(output)
        if remaining <= 0:
            raise ValueError("Garmin inflated FIT exceeds safe size")
        chunk = obj.decompress(pending, remaining)
        output.extend(chunk)
        if len(output) > MAX_FIT_BYTES:
            raise ValueError("Garmin inflated FIT exceeds safe size")
        pending = obj.unconsumed_tail
        if not pending:
            break
    remaining = MAX_FIT_BYTES + 1 - len(output)
    output.extend(obj.flush(max(1, remaining)))
    if len(output) > MAX_FIT_BYTES:
        raise ValueError("Garmin inflated FIT exceeds safe size")
    return bytes(output)


def _inflate_bounded(data: bytes) -> bytes:
    """Return a raw FIT container from Garmin's bounded transfer payload.

    FileSync firmware has not been perfectly uniform about its DEFLATE wrapper.
    Accept a native FIT, zlib, gzip, or raw-DEFLATE stream, but only when the
    resulting bytes expose a real FIT header. This makes full-device discovery
    more tolerant without ever interpreting arbitrary opaque files as health data.
    """
    raw = bytes(data)
    if _looks_like_fit(raw):
        if len(raw) > MAX_FIT_BYTES:
            raise ValueError("Garmin FIT exceeds safe size")
        return raw
    errors: list[str] = []
    for label, wbits in (
        ("zlib", zlib.MAX_WBITS),
        ("gzip", zlib.MAX_WBITS | 16),
        ("raw-deflate", -zlib.MAX_WBITS),
    ):
        try:
            inflated = _inflate_with_wbits_bounded(raw, wbits)
        except (zlib.error, ValueError) as err:
            errors.append(f"{label}:{type(err).__name__}")
            continue
        if _looks_like_fit(inflated):
            return inflated
        errors.append(f"{label}:not-fit")
    raise ValueError(
        "Garmin payload is not a raw/zlib/gzip/raw-deflate FIT container"
        + (f" ({', '.join(errors)})" if errors else "")
    )


def _payload_diagnostics(data: bytes, *, compressed: bool) -> tuple[dict[str, Any], bytes | None]:
    """Describe an undecodable transfer and return a recoverable FIT candidate."""
    raw = bytes(data)
    info: dict[str, Any] = {
        "raw_size": len(raw),
        "raw_head_hex": raw[:32].hex(),
        "raw_fit_signature_offset": raw.find(b".FIT"),
        "compressed_transport": bool(compressed),
    }
    candidate: bytes | None = raw if _looks_like_fit(raw) else None
    if candidate is not None:
        info["container"] = "raw_fit"
    elif compressed:
        attempts: list[str] = []
        for label, wbits in (
            ("zlib", zlib.MAX_WBITS),
            ("gzip", zlib.MAX_WBITS | 16),
            ("raw_deflate", -zlib.MAX_WBITS),
        ):
            try:
                inflated = _inflate_with_wbits_bounded(raw, wbits)
            except Exception as err:
                attempts.append(f"{label}:{type(err).__name__}")
                continue
            attempts.append(f"{label}:{'fit' if _looks_like_fit(inflated) else 'not_fit'}")
            if _looks_like_fit(inflated):
                candidate = inflated
                info["container"] = label
                break
        info["inflate_attempts"] = attempts
    if candidate is not None:
        info.update({
            "fit_size": len(candidate),
            "fit_head_hex": candidate[:32].hex(),
            "fit_header_size": int(candidate[0]) if candidate else None,
            "fit_profile_version": int.from_bytes(candidate[2:4], "little") if len(candidate) >= 4 else None,
            "fit_declared_data_size": int.from_bytes(candidate[4:8], "little") if len(candidate) >= 8 else None,
            "fit_expected_total_size": (int(candidate[0]) + int.from_bytes(candidate[4:8], "little") + 2) if len(candidate) >= 8 else None,
        })
    return info, candidate


def _capture_invalid_payload(
    capture_root: str,
    *,
    sensor_id: str,
    source_key: str,
    file_type: str,
    fingerprint: str,
    raw_data: bytes,
    compressed: bool,
    error: str,
) -> dict[str, Any]:
    """Persist a bounded private forensic copy of one invalid Garmin payload."""
    root = Path(capture_root)
    root.mkdir(parents=True, exist_ok=True)
    token = hashlib.sha256(
        f"{sensor_id}|{source_key}|{fingerprint}".encode("utf-8", errors="ignore")
    ).hexdigest()[:20]
    diagnostics, fit_candidate = _payload_diagnostics(raw_data, compressed=compressed)
    raw_path = root / f"{token}.payload"
    meta_path = root / f"{token}.json"
    fit_path = root / f"{token}.fit"
    raw_path.write_bytes(bytes(raw_data))
    if fit_candidate is not None:
        fit_path.write_bytes(fit_candidate)
    elif fit_path.exists():
        fit_path.unlink()
    metadata = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "sensor_id": str(sensor_id),
        "source_key": str(source_key),
        "file_type": str(file_type or "unknown"),
        "catalog_fingerprint": str(fingerprint),
        "validation_error": str(error)[:512],
        "payload_file": raw_path.name,
        "fit_file": fit_path.name if fit_candidate is not None else None,
        "diagnostics": diagnostics,
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    # Bound both count and total bytes. Metadata is tiny, so account payload/FIT
    # files and remove the oldest capture group atomically enough for diagnostics.
    metas = sorted(root.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    total = 0
    keep: set[str] = set()
    for meta in metas:
        stem = meta.stem
        group = [meta, root / f"{stem}.payload", root / f"{stem}.fit"]
        size = sum(path.stat().st_size for path in group if path.exists())
        if len(keep) < MAX_INVALID_CAPTURE_FILES and total + size <= MAX_INVALID_CAPTURE_BYTES:
            keep.add(stem)
            total += size
            continue
        for path in group:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
    return {
        "token": token,
        "directory": str(root),
        "metadata_file": meta_path.name,
        "payload_file": raw_path.name,
        "fit_file": fit_path.name if fit_candidate is not None else None,
        "diagnostics": diagnostics,
    }


def _serialize_history_batch(batch: DeviceHistoryBatch) -> dict[str, Any]:
    return {
        "metric_points": [
            {
                "metric": point.metric, "value": point.value, "timestamp": point.timestamp,
                "source_type": point.source_type, "source_entity": point.source_entity,
                "sources": list(point.sources), "context": [list(item) for item in point.context],
            }
            for point in batch.metric_points
        ],
        "sleep_records": [record.as_persistent_dict() for record in batch.sleep_records],
    }


def _history_batch_from_record(payload: Any) -> DeviceHistoryBatch:
    if not isinstance(payload, dict):
        return DeviceHistoryBatch()
    points: list[DeviceMetricPoint] = []
    for item in payload.get("metric_points") or []:
        if not isinstance(item, dict):
            continue
        try:
            points.append(DeviceMetricPoint(
                metric=str(item.get("metric") or ""),
                value=float(item.get("value")),
                timestamp=str(item.get("timestamp") or ""),
                source_type=str(item.get("source_type") or "garmin_local_ble_fit_health"),
                source_entity=str(item.get("source_entity") or "") or None,
                sources=tuple(str(value) for value in (item.get("sources") or [])[:12]),
                context=tuple(
                    (str(pair[0])[:64], pair[1])
                    for pair in (item.get("context") or [])[:12]
                    if isinstance(pair, (list, tuple)) and len(pair) == 2
                ),
            ))
        except (TypeError, ValueError):
            continue
    sleeps: list[SleepRecord] = []
    for item in payload.get("sleep_records") or []:
        if not isinstance(item, dict):
            continue
        allowed = {
            "source", "provider_domain", "start", "end", "observed_at", "duration_s",
            "time_in_bed_s", "awake_s", "light_sleep_s", "deep_sleep_s", "rem_sleep_s",
            "sleep_latency_s", "score", "efficiency_percent", "average_hr", "minimum_hr",
            "hrv_ms", "respiratory_rate", "spo2_percent", "readiness_score",
            "recovery_score", "sleep_need_s", "sleep_debt_s", "disturbance_count",
            "sleep_cycle_count", "in_bed", "sources", "provider_domains",
            "field_sources", "provider_values",
        }
        try:
            sleeps.append(SleepRecord(**{key: value for key, value in item.items() if key in allowed}))
        except TypeError:
            continue
    return DeviceHistoryBatch.bounded(metric_points=points, sleep_records=sleeps)


def _structured_payload_bytes(data: bytes, *, compressed: bool) -> tuple[bytes, str]:
    """Return one bounded raw/DEFLATE-family structured Garmin payload."""
    raw = bytes(data)
    if len(raw) > MAX_FIT_BYTES:
        raise ValueError("Garmin structured payload exceeds safe size")
    if not compressed:
        return raw, "raw"
    errors: list[str] = []
    for label, wbits in (
        ("zlib", zlib.MAX_WBITS),
        ("gzip", zlib.MAX_WBITS | 16),
        ("raw-deflate", -zlib.MAX_WBITS),
    ):
        try:
            return _inflate_with_wbits_bounded(raw, wbits), label
        except (zlib.error, ValueError) as err:
            errors.append(f"{label}:{type(err).__name__}")
    raise ValueError(
        "Garmin structured payload could not be inflated"
        + (f" ({', '.join(errors)})" if errors else "")
    )


def _bounded_json_number(value: Any, *, low: float = -1_000_000.0, high: float = 1_000_000.0) -> float | int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")} or number < low or number > high:
        return None
    return int(number) if number.is_integer() else number


def _decode_live_activity_payload(data: bytes, *, compressed: bool) -> tuple[dict[str, Any], int]:
    """Decode Garmin FileSync ``LiveActivity`` JSON without treating it as FIT.

    Real Garmin FileSync captures show this family as zlib-compressed UTF-8
    JSON describing a workout/live-activity definition. ``steps`` here means
    workout steps/targets, not the athlete's daily pedometer step count.
    """
    payload, container = _structured_payload_bytes(data, compressed=compressed)
    try:
        text = payload.decode("utf-8")
        parsed = json.loads(text, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid JSON number {value}")))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as err:
        raise ValueError("Garmin LiveActivity payload is not valid UTF-8 JSON") from err
    if not isinstance(parsed, dict) or not isinstance(parsed.get("steps"), list):
        raise ValueError("Garmin LiveActivity JSON has no workout step list")

    steps: list[dict[str, Any]] = []
    for raw_step in parsed.get("steps", [])[:256]:
        if not isinstance(raw_step, dict):
            continue
        step: dict[str, Any] = {}
        for key, low, high in (
            ("id", 0, 100_000),
            ("intensity", -1, 100),
            ("durationType", -1, 100),
            ("duration", 0, 604_800),
        ):
            number = _bounded_json_number(raw_step.get(key), low=low, high=high)
            if number is not None:
                step[key] = number
        targets: list[dict[str, Any]] = []
        for raw_target in raw_step.get("targets", [])[:32] if isinstance(raw_step.get("targets"), list) else []:
            if not isinstance(raw_target, dict):
                continue
            target: dict[str, Any] = {}
            for key, low, high in (
                ("priority", -1, 100),
                ("targetType", -1, 1000),
                ("targetHigh", -1_000_000, 1_000_000),
                ("targetLow", -1_000_000, 1_000_000),
            ):
                number = _bounded_json_number(raw_target.get(key), low=low, high=high)
                if number is not None:
                    target[key] = number
            if target:
                targets.append(target)
        if targets:
            step["targets"] = targets
        if step:
            steps.append(step)

    clusters: list[dict[str, Any]] = []
    for raw_cluster in parsed.get("clusters", [])[:256] if isinstance(parsed.get("clusters"), list) else []:
        if not isinstance(raw_cluster, dict):
            continue
        cluster: dict[str, Any] = {}
        for key in ("clusterId", "firstStepId", "lastStepId", "activeStepId", "state"):
            number = _bounded_json_number(raw_cluster.get(key), low=-1, high=100_000)
            if number is not None:
                cluster[key] = number
        if cluster:
            clusters.append(cluster)

    artifact = {
        "artifact_type": "live_activity",
        "uuid": str(parsed.get("uuid") or "")[:128],
        "name": str(parsed.get("name") or "")[:256],
        "steps": steps,
        "clusters": clusters,
        "container": container,
    }
    return {
        "kind": "device_artifact",
        "artifact_type": "live_activity",
        "device_artifact": artifact,
        "decoder_revision": GARMIN_PAYLOAD_DECODER_REVISION,
    }, len(payload)


def _decode_downloaded_file(
    data: bytes,
    *,
    compressed: bool,
    sensor_id: str,
    source_key: str,
    source_label: str | None,
    file_type: str = "",
) -> tuple[dict[str, Any], int]:
    """Content-classify one Garmin device file and normalize supported payloads."""
    normalized_type = str(file_type or "").strip().upper().replace("_", "")
    if normalized_type == "LIVEACTIVITY":
        return _decode_live_activity_payload(data, compressed=compressed)
    fit = _inflate_bounded(data) if compressed else bytes(data)
    kind = fit_content_kind(fit)
    record: dict[str, Any] = {"kind": kind, "decoder_revision": GARMIN_PAYLOAD_DECODER_REVISION}
    if kind == "activity":
        workout = workout_from_fit(
            fit, sensor_id=sensor_id, source_key=source_key, source_label=source_label
        )
        record["workout"] = workout.as_persistent_dict()
    elif kind == "health":
        batch = health_history_from_fit(
            fit, sensor_id=sensor_id, source_key=source_key, source_label=source_label
        )
        record["history"] = _serialize_history_batch(batch)
        record["health_metric_points"] = len(batch.metric_points)
        record["health_sleep_records"] = len(batch.sleep_records)
        if not batch.metric_points and not batch.sleep_records:
            record["kind"] = "unsupported"
    if record.get("kind") == "unsupported":
        # Firmware can emit FIT messages newer than the parser's named health
        # catalogue. Conservatively recover metrics from already-named fields
        # (never numeric/unknown vendor fields), and retain a bounded schema
        # inventory so future decoder revisions can be targeted precisely.
        generic_batch, inventory = generic_wellness_from_fit(
            fit, sensor_id=sensor_id, source_key=source_key, source_label=source_label
        )
        record["fit_messages"] = list(fit_message_names(fit))[:64]
        record["fit_inventory"] = inventory
        if generic_batch.metric_points or generic_batch.sleep_records:
            record["kind"] = "health"
            record["history"] = _serialize_history_batch(generic_batch)
            record["health_metric_points"] = len(generic_batch.metric_points)
            record["health_sleep_records"] = len(generic_batch.sleep_records)
            record["generic_wellness_decode"] = True
    return record, len(fit)


def _catalog_item_type(item: GarminSyncFile | GarminDirectoryEntry) -> str:
    if isinstance(item, GarminSyncFile):
        return str(item.type_name or (f"FIT_TYPE_{item.type_code}" if item.type_code is not None else "unknown"))
    return f"FIT_TYPE_{item.sub_type}" if item.data_type == 128 else f"legacy:{item.data_type}:{item.sub_type}"


def _catalog_item_is_health(item: GarminSyncFile | GarminDirectoryEntry) -> bool:
    if isinstance(item, GarminSyncFile):
        name = _catalog_item_type(item).upper()
        return name in HEALTH_FIT_TYPE_NAMES or any(token in name for token in ("MONITOR", "METRIC", "WELLNESS", "HEALTH", "SLEEP", "WEIGHT", "BLOOD_PRESSURE"))
    return item.data_type == 128 and item.sub_type in {9, 14, 15, 28, 32}


def _catalog_item_fingerprint(item: GarminSyncFile | GarminDirectoryEntry) -> str:
    """Bounded metadata fingerprint used to notice updated circular health files."""
    if isinstance(item, GarminSyncFile):
        digest = hashlib.sha256(bytes(item.raw or b"")[:4096]).hexdigest()[:16]
        return f"{_catalog_item_type(item)}:{int(item.size)}:{int(item.page_id or 0)}:{digest}"
    return f"{item.data_type}:{item.sub_type}:{item.number}:{item.size}:{item.timestamp}"


def _scanner_route_source(route: Any) -> str | None:
    """Return Home Assistant's source ID for one address-specific scanner route."""
    scanner = getattr(route, "scanner", None)
    source = getattr(scanner, "source", None)
    if source:
        return str(source)
    ble_device = getattr(route, "ble_device", None)
    details = getattr(ble_device, "details", None)
    if isinstance(details, dict) and details.get("source"):
        return str(details["source"])
    return None


def _scanner_route_is_local(route: Any) -> bool:
    """Return whether a route is backed by the host-local BlueZ scanner.

    Do not use ``scanner.adapter`` as the discriminator. Remote scanners can
    expose an adapter-like attribute too (notably ESPHome proxies), which can
    make a proxy look local and incorrectly pin a secure Garmin bond to it.
    Prefer BlueZ object-path evidence and HA's concrete local scanner type.
    """
    ble_device = getattr(route, "ble_device", None)
    details = getattr(ble_device, "details", None)

    # Bleak/BlueZ details have appeared as mappings and as tuple/list payloads
    # across HA/Bleak releases. In both cases the D-Bus object path is decisive.
    if isinstance(details, dict):
        for key in ("path", "object_path"):
            if str(details.get(key) or "").startswith("/org/bluez/"):
                return True
    elif isinstance(details, (tuple, list)) and details:
        if str(details[0]).startswith("/org/bluez/"):
            return True
    elif isinstance(details, str) and details.startswith("/org/bluez/"):
        return True

    scanner = getattr(route, "scanner", None)
    scanner_type = type(scanner).__name__ if scanner is not None else ""
    scanner_module = type(scanner).__module__ if scanner is not None else ""
    return scanner_type == "HaScanner" and "bluetooth" in scanner_module


def _scanner_route_rssi(route: Any) -> int:
    advertisement = getattr(route, "advertisement", None)
    try:
        return int(getattr(advertisement, "rssi", -127))
    except (TypeError, ValueError):
        return -127


def _bluez_device_path(ble_device: Any, address: str) -> str | None:
    """Return the BlueZ object path carried by a host-local BLEDevice."""
    details = getattr(ble_device, "details", None)
    candidates: list[Any] = []
    if isinstance(details, dict):
        candidates.extend([details.get("path"), details.get("object_path")])
    elif isinstance(details, (tuple, list)) and details:
        candidates.append(details[0])
    elif isinstance(details, str):
        candidates.append(details)
    suffix = "/dev_" + str(address).upper().replace(":", "_")
    for candidate in candidates:
        value = str(candidate or "")
        if value.startswith("/org/bluez/") and value.upper().endswith(suffix.upper()):
            return value
    return None


def _select_garmin_ble_route(
    hass, address: str, preferred_source: str | None
) -> tuple[Any | None, str | None, str]:
    """Select one stable central for Garmin pairing and subsequent archive sync.

    A BLE bond belongs to the central that created it.  HA's normal nearest-path
    resolver may switch between a local controller and remote proxies as RSSI
    changes, which is ideal for ordinary unbonded sensors but unsafe for a paired
    Garmin archive session.  Before a source has been bonded, prefer a host-local
    BlueZ route because it can participate in interactive pairing.  After pairing,
    stick to that exact source rather than silently hopping to a different central.
    """
    try:
        routes = list(
            bluetooth.async_scanner_devices_by_address(
                hass, address, connectable=True
            )
        )
    except Exception:
        routes = []

    if preferred_source:
        for route in routes:
            if _scanner_route_source(route) == preferred_source:
                return (
                    getattr(route, "ble_device", None),
                    preferred_source,
                    "local" if _scanner_route_is_local(route) else "remote",
                )
        # Do not move an established bond to another Bluetooth central merely
        # because the preferred scanner missed this advertisement.  Wait for the
        # bonded source to see the watch again.
        return None, preferred_source, "unavailable"

    local_routes = [route for route in routes if _scanner_route_is_local(route)]
    if local_routes:
        route = max(local_routes, key=_scanner_route_rssi)
        return getattr(route, "ble_device", None), _scanner_route_source(route), "local"

    # Remote-only HA installations can still try the normal HA-selected route.
    # If pairing succeeds, its source is persisted below and future syncs remain
    # pinned to that same central.
    ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        return None, None, "unavailable"
    for route in routes:
        candidate = getattr(route, "ble_device", None)
        if candidate is ble_device or (
            candidate is not None
            and getattr(candidate, "details", None) == getattr(ble_device, "details", None)
        ):
            return ble_device, _scanner_route_source(route), "remote"
    details = getattr(ble_device, "details", None)
    source = details.get("source") if isinstance(details, dict) else None
    return ble_device, str(source) if source else None, "auto"


async def _start_best_session(client) -> tuple[GarminGfdiSession, tuple[str, ...]]:
    """Start the first working GFDI transport using connected capabilities only.

    A device can expose more than one Garmin transport/channel.  Each candidate
    gets a short independent deadline and failed candidates are fully stopped
    before trying the next one.  Model/local-name strings never participate.
    """
    candidates = transport_candidates_from_client(client)
    if not candidates:
        raise GarminUnsupportedTransport(
            "no supported Garmin GFDI V0/V1/V2 characteristics"
        )
    backend_names = tuple(candidate.backend for candidate in candidates)
    failures: list[str] = []
    async with asyncio.timeout(TRANSPORT_NEGOTIATION_TIMEOUT):
        for transport in candidates:
            session = GarminGfdiSession(transport)
            try:
                async with asyncio.timeout(TRANSPORT_CANDIDATE_TIMEOUT):
                    await session.async_start()
                return session, backend_names
            except asyncio.CancelledError:
                raise
            except Exception as err:
                detail = " ".join(str(err).split())[:120]
                failures.append(
                    f"{transport.backend}:{type(err).__name__}"
                    + (f"({detail})" if detail else "")
                )
                try:
                    async with asyncio.timeout(CLEANUP_TIMEOUT):
                        await session.async_stop()
                except Exception:
                    pass
                # A transport failure can also drop the underlying GATT link.
                # Do not churn through the remaining 281x/V1 candidates on a
                # client that BlueZ already considers disconnected.
                if getattr(client, "is_connected", True) is False:
                    break
    raise RuntimeError(
        "Garmin GFDI capability candidates did not handshake: "
        + ", ".join(failures[:6])
    )


class GarminLocalCoordinator:
    """Own automatic Garmin sync tasks, checkpoints, retries and cleanup."""

    adapter_id = "garmin_local"
    sync_unique_suffix = "garmin_sync_workouts"
    sync_translation_key = "sync_device_data"
    sync_icon = "mdi:watch-import-variant"

    def __init__(self, provider) -> None:
        self.provider = provider
        self.runtime = provider.runtime
        self.hass = provider.hass
        self._store = Store[dict[str, Any]](
            self.hass,
            GARMIN_LOCAL_SYNC_STORE_VERSION,
            GARMIN_LOCAL_SYNC_STORE_KEY,
            private=True,
        )
        self._state: dict[str, Any] = {"devices": {}}
        self._tasks: dict[str, asyncio.Task] = {}
        self._active_sync: set[str] = set()
        self._queued: dict[str, tuple[asyncio.Task, float]] = {}
        self._background: set[asyncio.Task] = set()
        self._save_lock = asyncio.Lock()
        self._initialized = False
        self._stopping = False
        self._progress: dict[str, tuple[int, float]] = {}
        self._last_advertisement_action: dict[str, float] = {}
        self._reconfigure_unsub = None

    async def async_setup(self) -> None:
        stored = await self._store.async_load() or {}
        devices = stored.get("devices")
        if isinstance(devices, dict):
            self._state = {"devices": devices}
        self._initialized = True

        # ``bluetooth_connection_busy`` is an expected transient state for Garmin
        # watches that are currently connected to Garmin Connect/a phone. Older
        # builds created a persistent Repair from automatic startup syncs, so the
        # same notification came back on every Home Assistant restart even after
        # the user completed the Repair flow. Clear those legacy/stale prompts at
        # startup; background contention is represented by sync state and retried
        # quietly. A fresh Repair is created only for an explicit manual sync.
        for stored_sensor_id in tuple(self._state.setdefault("devices", {})):
            raw_sensor_id = str(stored_sensor_id)
            clear_device_user_action(
                self.hass,
                adapter_id="garmin_local",
                sensor_id=raw_sensor_id,
                action="bluetooth_connection_busy",
            )
            canonical_sensor_id = self.runtime.resolve_sensor_id(raw_sensor_id)
            if canonical_sensor_id != raw_sensor_id:
                clear_device_user_action(
                    self.hass,
                    adapter_id="garmin_local",
                    sensor_id=canonical_sensor_id,
                    action="bluetooth_connection_busy",
                )

        def _reconfigure_completed(event) -> None:
            data = event.data
            if str(data.get("adapter_id") or "") != "garmin_local":
                return
            sensor_id = str(data.get("sensor_id") or "")
            if sensor_id:
                self.schedule(sensor_id, delay=0.0, force=True)

        self._reconfigure_unsub = self.hass.bus.async_listen(
            "fitness_device_reconfigure_completed", _reconfigure_completed
        )
        recovered = self._recover_interrupted_states()
        if recovered:
            await self._save()
        self._resume_persisted_schedules()

    def _recover_interrupted_states(self) -> bool:
        """Turn an interrupted in-flight sync into a safe resumable checkpoint.

        Complete FIT files are checkpointed before profile import, so a Home
        Assistant restart never needs to resume in the middle of a BLE transfer.
        Instead, reconnect from the last durable catalogue/file checkpoint.
        """
        changed = False
        retry_at = datetime.now(timezone.utc) + timedelta(seconds=STARTUP_RESUME_DELAY)
        devices = self._state.setdefault("devices", {})
        for state in devices.values():
            if not isinstance(state, dict):
                continue
            if str(state.get("sync_state") or "") not in {"connecting", "syncing"}:
                continue
            state.update(
                sync_state="waiting",
                next_attempt=retry_at.isoformat(),
                active_file=None,
            )
            changed = True
        return changed

    def _resume_persisted_schedule(self, sensor_id: str) -> bool:
        """Recreate one archive timer from durable state after startup/assignment."""
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(canonical)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if (
            sensor is None
            or endpoint is None
            or endpoint.metadata.get("archive_adapter") != "garmin_local"
            or endpoint.metadata.get("archive_compatible") is False
            or not self.runtime.sensor_is_accepted(canonical)
            or not self.runtime.sensor_archive_profile_ids(canonical)
        ):
            return False

        state = self._device(canonical)
        status = str(state.get("sync_state") or "idle")
        try:
            pending = max(0, int(state.get("pending_file_count") or 0))
        except (TypeError, ValueError):
            pending = 0
        now = datetime.now(timezone.utc)
        due: datetime | None = None

        if status in {"waiting", "retrying", "error"} or pending:
            due = _dt(state.get("next_attempt")) or (
                now + timedelta(seconds=STARTUP_RESUME_DELAY)
            )
            # A previous connection error must not make a newly restarted HA wait
            # hours before trying a watch that may now be reachable. Respect the
            # startup Bluetooth cooldown, then retry once; normal bounded backoff
            # resumes if the watch/phone still owns the connection.
            if status == "error" and not pending:
                due = min(due, now + timedelta(seconds=STARTUP_RESUME_DELAY))
        elif status == "ready":
            last_success = _dt(state.get("last_successful_sync"))
            if last_success is not None:
                due = last_success + SYNC_INTERVAL

        if due is None:
            return False
        delay = max(0.0, (due - now).total_seconds())
        self.schedule(canonical, delay=delay, force=True)
        _LOGGER.info(
            "Garmin restored persisted archive timer for %s in %.1fs (state=%s pending=%s error=%s next_attempt=%s)",
            canonical,
            delay,
            status,
            pending,
            state.get("last_error_code") or "none",
            state.get("next_attempt") or "none",
        )
        return True

    def _resume_persisted_schedules(self) -> None:
        """Restore every currently eligible Garmin timer without polling."""
        devices = self._state.setdefault("devices", {})
        for sensor_id in tuple(devices):
            self._resume_persisted_schedule(str(sensor_id))

    def _device(self, sensor_id: str) -> dict[str, Any]:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        devices = self._state.setdefault("devices", {})
        state = devices.get(sensor_id)
        if not isinstance(state, dict):
            state = devices[sensor_id] = {"files": {}, "retry_count": 0}
        return state

    def _report_pairing_required(self, sensor_id: str) -> None:
        """Open a guided HA Repair after automatic pairing needs watch input."""
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(canonical)
        device = sensor.label() if sensor is not None else "Garmin device"
        request_device_user_action(
            self.hass,
            adapter_id="garmin_local",
            sensor_id=canonical,
            device=device,
            action="pairing_required",
            reason="Garmin requires confirmation on the watch before local Bluetooth sync can continue.",
            instructions=(
                "Keep the Garmin paired with your phone; Home Assistant should be added as another host, not replace it.",
                "On the Garmin, open Bluetooth/Phone pairing mode so it is discoverable for another connection.",
                "Approve the pairing request shown on the Garmin when Home Assistant reconnects.",
                "If Garmin warns that the current phone pairing will be replaced or removed, cancel that operation.",
                "Return here and submit this Repair. Fitness will retry the device immediately.",
            ),
        )

    def _clear_pairing_issue(self, sensor_id: str) -> None:
        clear_device_user_action(
            self.hass,
            adapter_id="garmin_local",
            sensor_id=self.runtime.resolve_sensor_id(sensor_id),
            action="pairing_required",
        )

    def _report_connection_busy(self, sensor_id: str) -> None:
        """Explain one-active-Bluetooth-host contention without deleting pairings."""
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(canonical)
        device = sensor.label() if sensor is not None else "Garmin device"
        request_device_user_action(
            self.hass,
            adapter_id="garmin_local",
            sensor_id=canonical,
            device=device,
            action="bluetooth_connection_busy",
            reason="The Garmin is nearby but another Bluetooth host may currently own its active connection.",
            instructions=(
                "Keep the existing phone/Garmin pairing saved; do not remove or replace it.",
                "Some Garmin models accept only one active Bluetooth host at a time.",
                "Temporarily disconnect Garmin Connect or turn off Bluetooth on the phone, then choose Retry now.",
                "After Fitness finishes and disconnects, phone Bluetooth can be enabled normally again.",
            ),
        )

    def _clear_connection_busy_issue(self, sensor_id: str) -> None:
        clear_device_user_action(
            self.hass,
            adapter_id="garmin_local",
            sensor_id=self.runtime.resolve_sensor_id(sensor_id),
            action="bluetooth_connection_busy",
        )

    @staticmethod
    def _endpoint_recent(endpoint) -> bool:
        seen = getattr(endpoint, "last_seen", None)
        if not isinstance(seen, datetime):
            return False
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - seen.astimezone(timezone.utc)).total_seconds() <= FRESH_ADVERTISEMENT_MAX_AGE

    async def _save(self) -> None:
        if not self._initialized:
            return
        async with self._save_lock:
            await self._store.async_save(self._state)

    def _background_task(self, coro, name: str) -> asyncio.Task:
        task = self.hass.async_create_background_task(coro, name, eager_start=False)
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task

    def advertise(self, sensor_id: str, identity: dict[str, Any]) -> None:
        """Rate-limit advertisement-side work; BLE advertisements are a hot path."""
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        now = self.hass.loop.time()
        previous = self._last_advertisement_action.get(sensor_id)
        if previous is not None and now - previous < ADVERTISEMENT_ACTION_MIN_INTERVAL:
            return
        self._last_advertisement_action[sensor_id] = now
        state = self._device(sensor_id)
        evidence = identity.get("garmin_identity_evidence") or []
        state["protocol_hint"] = identity.get("garmin_protocol_hint") or "auto"
        state["identity_evidence"] = list(evidence)[:8]
        self.runtime.publish_details(
            sensor_id,
            {"garmin_local_backend": state.get("backend") or "auto"},
            transport="garmin_local_advertisement",
            metadata=_DETAIL_META,
            priority=80,
        )
        self._publish(sensor_id)
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if (
            endpoint is not None
            and endpoint.metadata.get("archive_compatible") is not False
            and self.runtime.sensor_is_accepted(sensor_id)
            and self.runtime.sensor_archive_profile_ids(sensor_id)
        ):
            # A fresh Garmin advertisement may wake a task that is merely
            # sleeping because the device was unreachable. It must not bypass
            # SYNC_INTERVAL or an error next_attempt backoff.
            self.schedule(sensor_id, delay=3.0, wake_if_sleeping=True)

    def acceptance_changed(self, sensor_id: str, accepted: bool) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if accepted:
            if self.runtime.sensor_archive_profile_ids(sensor_id):
                if not self._resume_persisted_schedule(sensor_id):
                    self.schedule(sensor_id, delay=1.0, force=True)
            return
        self._clear_pairing_issue(sensor_id)
        self._clear_connection_busy_issue(sensor_id)
        self._cancel(sensor_id)

    def assignment_changed(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if not self.runtime.sensor_archive_profile_ids(sensor_id):
            self._clear_pairing_issue(sensor_id)
            self._clear_connection_busy_issue(sensor_id)
            self._cancel(sensor_id)
            state = self._device(sensor_id)
            state.update(sync_state="idle", pending_file_count=0)
            self._publish(sensor_id)
            self._background_task(self._save(), f"fitness Garmin pause state {sensor_id}")
        elif self.runtime.sensor_is_accepted(sensor_id):
            if not self._resume_persisted_schedule(sensor_id):
                self.schedule(sensor_id, delay=0.5, force=True)

    def forget_sensor(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        self._clear_pairing_issue(sensor_id)
        self._clear_connection_busy_issue(sensor_id)
        self._cancel(sensor_id)
        self._last_advertisement_action.pop(sensor_id, None)
        self._progress.pop(sensor_id, None)
        if self._state.setdefault("devices", {}).pop(sensor_id, None) is not None:
            self._background_task(self._save(), f"fitness Garmin forget state {sensor_id}")

    def _cancel(self, sensor_id: str) -> None:
        task = self._tasks.pop(sensor_id, None)
        self._active_sync.discard(sensor_id)
        self._queued.pop(sensor_id, None)
        if task is not None and not task.done():
            task.cancel()

    def schedule(
        self,
        sensor_id: str,
        *,
        delay: float,
        force: bool = False,
        wake_if_sleeping: bool = False,
    ) -> None:
        if self._stopping or not self._initialized:
            return
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if not force:
            state = self._device(sensor_id)
            last = _dt(state.get("last_successful_sync"))
            if last is not None and datetime.now(timezone.utc) - last < SYNC_INTERVAL:
                return
            next_attempt = _dt(state.get("next_attempt"))
            if next_attempt is not None and next_attempt > datetime.now(timezone.utc):
                return
        current = self._tasks.get(sensor_id)
        if current is not None and not current.done():
            if sensor_id not in self._active_sync:
                if not (force or wake_if_sleeping):
                    return
                # Manual retry can replace a sleeping backoff task. A live
                # advertisement may replace only ordinary sleeping work because
                # the interval/next_attempt checks above still apply. Never
                # cancel an active BLE transfer.
                current.cancel()
                if self._tasks.get(sensor_id) is current:
                    self._tasks.pop(sensor_id, None)
                self._queued.pop(sensor_id, None)
            else:
                if not force:
                    return
                previous = self._queued.get(sensor_id)
                self._queued[sensor_id] = (
                    current,
                    min(delay, previous[1]) if previous and previous[0] is current else delay,
                )
                return

        async def _run() -> None:
            canonical = self.runtime.resolve_sensor_id(sensor_id)
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                canonical = self.runtime.resolve_sensor_id(sensor_id)
                self._active_sync.add(canonical)
                await self._async_sync(canonical, force=force)
            except asyncio.CancelledError:
                raise
            finally:
                current_task = asyncio.current_task()
                canonical = self.runtime.resolve_sensor_id(sensor_id)
                self._active_sync.discard(canonical)
                if self._tasks.get(canonical) is current_task:
                    self._tasks.pop(canonical, None)
                queued = self._queued.get(canonical)
                if queued is not None and queued[0] is current_task:
                    self._queued.pop(canonical, None)
                    if not self._stopping:
                        self.hass.loop.call_soon(
                            lambda: self.schedule(canonical, delay=queued[1], force=True)
                        )

        self._tasks[sensor_id] = self.hass.async_create_background_task(
            _run(), f"fitness Garmin local workout sync {sensor_id}", eager_start=False
        )

    async def async_sync_now(self, sensor_id: str) -> asyncio.Task | None:
        """Queue a user sync without bypassing Garmin's proven post-session settle."""
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        state = self._device(canonical)
        state["manual_request_until"] = (datetime.now(timezone.utc) + timedelta(seconds=MANUAL_REQUEST_WINDOW)).isoformat()
        try:
            pending = max(0, int(state.get("pending_file_count") or 0))
        except (TypeError, ValueError):
            pending = 0
        last_batch = _dt(state.get("last_batch_success"))
        delay = 0.0
        if pending and last_batch is not None:
            age = max(0.0, (datetime.now(timezone.utc) - last_batch).total_seconds())
            if age < MIN_SESSION_RECONNECT_GAP:
                delay = max(1.0, MIN_SESSION_RECONNECT_GAP - age)
                retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                state.update(
                    sync_state="cooldown",
                    last_error_code="none",
                    next_attempt=retry_at.isoformat(),
                )
                await self._save()
                self._publish(canonical)
                _LOGGER.info(
                    "Garmin manual sync for %s deferred %.1fs for post-session cooldown",
                    canonical,
                    delay,
                )
        self.schedule(canonical, delay=delay, force=True)
        return self._tasks.get(canonical)

    def _schedule_after_current(self, sensor_id: str, delay: float) -> None:
        current = asyncio.current_task()
        if current is None:
            self.hass.loop.call_soon(lambda: self.schedule(sensor_id, delay=delay, force=True))
            return
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        previous = self._queued.get(canonical)
        # A manual button press during an already-running automatic sync queues the
        # earliest safe rerun. Completion/error scheduling must not overwrite that
        # user request with a slower five-minute/periodic delay.
        self._queued[canonical] = (
            current,
            min(delay, previous[1])
            if previous is not None and previous[0] is current
            else delay,
        )

    def _publish(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        state = self._device(sensor_id)
        files = state.get("files") if isinstance(state.get("files"), dict) else {}
        values = {
            "garmin_local_backend": state.get("backend") or "auto",
            "garmin_sync_state": state.get("sync_state", "idle"),
            "garmin_last_sync": state.get("last_sync"),
            "garmin_last_successful_sync": state.get("last_successful_sync"),
            "garmin_last_batch_success": state.get("last_batch_success"),
            "garmin_next_attempt": state.get("next_attempt"),
            "garmin_device_workout_count": state.get("device_workout_count"),
            "garmin_imported_file_count": len(files),
            "garmin_pending_file_count": state.get("pending_file_count", 0),
            "garmin_quarantined_file_count": state.get("quarantined_file_count", 0),
            "garmin_downloaded_bytes": state.get("downloaded_bytes"),
            "garmin_retry_count": state.get("retry_count", 0),
            "garmin_last_error": state.get("last_error_code") or "none",
            "garmin_protocol_version": state.get("protocol_version"),
            "garmin_latest_workout": state.get("latest_workout"),
        }
        self.runtime.publish_details(
            sensor_id,
            {key: value for key, value in values.items() if value is not None},
            transport="garmin_local_sync",
            metadata=_DETAIL_META,
            priority=95,
        )

    def _progress_update(self, sensor_id: str, size: int) -> None:
        now = self.hass.loop.time()
        old_size, old_time = self._progress.get(sensor_id, (0, 0.0))
        if size - old_size < 65536 and now - old_time < 5.0:
            return
        self._progress[sensor_id] = (size, now)
        self._device(sensor_id)["downloaded_bytes"] = size
        self._publish(sensor_id)

    async def _import_records(self, records: list[dict[str, Any]], profile_ids: list[str]) -> None:
        for profile_id in profile_ids:
            manager = self.hass.data.get(DOMAIN, {}).get(profile_id)
            if manager is None:
                continue
            pending: list[dict[str, Any]] = []
            workouts: list[Workout] = []
            health_points: list[DeviceMetricPoint] = []
            sleep_records: list[SleepRecord] = []
            for record in records:
                if not isinstance(record, dict) or record.get("kind") not in {"activity", "health"}:
                    continue
                imported = {str(value) for value in record.get("imported_profiles") or []}
                if profile_id in imported:
                    continue
                if record.get("kind") == "activity":
                    payload = record.get("workout")
                    if not isinstance(payload, dict):
                        continue
                    try:
                        workouts.append(Workout(**payload))
                    except TypeError:
                        continue
                else:
                    batch = _history_batch_from_record(record.get("history"))
                    health_points.extend(batch.metric_points)
                    sleep_records.extend(batch.sleep_records)
                pending.append(record)
            if workouts:
                await manager.async_import_device_workouts(workouts)
            if health_points or sleep_records:
                # Do not collapse several Garmin monitoring files into one batch
                # and then truncate the tail at DeviceHistoryBatch's hard bound.
                # Chunk the already-bounded decoded history so all supported
                # records from this sync are offered to the canonical importer.
                point_chunk = 2048
                sleep_chunk = 32
                for offset in range(0, max(len(health_points), 1), point_chunk):
                    batch_sleep = sleep_records[:sleep_chunk] if offset == 0 else []
                    batch_points = health_points[offset : offset + point_chunk]
                    if batch_points or batch_sleep:
                        await manager.async_import_device_history(
                            DeviceHistoryBatch.bounded(
                                metric_points=batch_points, sleep_records=batch_sleep
                            )
                        )
                for offset in range(sleep_chunk, len(sleep_records), sleep_chunk):
                    await manager.async_import_device_history(
                        DeviceHistoryBatch.bounded(
                            sleep_records=sleep_records[offset : offset + sleep_chunk]
                        )
                    )
            if workouts or health_points or sleep_records:
                for record in pending:
                    imported = {str(value) for value in record.get("imported_profiles") or []}
                    imported.add(profile_id)
                    record["imported_profiles"] = sorted(imported)


    async def async_clear_fit_cache(self, retain_count: int = 30, *, profile_id: str | None = None, ownership: str = "profile") -> int:
        """Prune only Fitness-owned cache records allowed by the requested ownership scope."""
        retain_count = max(0, min(int(retain_count), 500))
        removed = 0
        for state in self._state.setdefault("devices", {}).values():
            files = state.get("files") if isinstance(state, dict) else None
            if not isinstance(files, dict):
                continue
            eligible = [
                (key, record) for key, record in files.items()
                if isinstance(record, dict)
                and (
                    ownership == "all_fitness_owned"
                    or (
                        profile_id is not None
                        and profile_id in {str(value) for value in record.get("imported_profiles") or []}
                    )
                )
            ]
            if len(eligible) <= retain_count:
                continue
            ordered = sorted(
                eligible,
                key=lambda item: str((item[1] or {}).get("completed_at") or item[0]),
                reverse=True,
            )
            keep = {key for key, _value in ordered[:retain_count]}
            eligible_keys = {key for key, _record in eligible}
            for key in list(files):
                if key in eligible_keys and key not in keep:
                    files.pop(key, None)
                    removed += 1
        if removed:
            await self._save()
        return removed

    @staticmethod
    def _prune_file_records(files: dict[str, Any], protected_keys: set[str]) -> None:
        """Bound cached workout summaries without pruning the current catalogue."""
        overflow = len(files) - MAX_CACHED_FILE_RECORDS
        if overflow <= 0:
            return
        removable = [
            (str((record or {}).get("completed_at") or ""), key)
            for key, record in files.items()
            if key not in protected_keys and isinstance(record, dict)
        ]
        removable.sort()
        for _completed_at, key in removable[:overflow]:
            files.pop(key, None)

    @staticmethod
    def _item_key(item: GarminSyncFile | GarminDirectoryEntry) -> str:
        return item.file_id.key if isinstance(item, GarminSyncFile) else item.key

    async def _async_sync(self, requested_sensor_id: str, *, force: bool = False) -> None:
        sensor_id = self.runtime.resolve_sensor_id(requested_sensor_id)
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if (
            self._stopping or sensor is None or endpoint is None
            or not self.runtime.sensor_is_accepted(sensor_id)
            or endpoint.metadata.get("archive_adapter") != "garmin_local"
            or endpoint.metadata.get("archive_compatible") is False
        ):
            return
        # Once a user has accepted a Garmin archive endpoint, preserve that
        # protocol identity even if a later advertisement omits manufacturer or
        # service fields.  Initial discovery still requires strong Garmin evidence.
        if endpoint.metadata.get("archive_adapter") == "garmin_local":
            identity = dict(endpoint.metadata)
        else:
            identity = garmin_advertisement_identity(
                endpoint.metadata.get("advertised_name") or sensor.name,
                endpoint.metadata.get("service_uuids") or [],
                endpoint.metadata.get("manufacturer_data_ids") or [],
            )
        if identity is None:
            return
        profile_ids = self.runtime.sensor_archive_profile_ids(sensor_id)
        state = self._device(sensor_id)
        if not profile_ids:
            state.update(sync_state="idle", pending_file_count=0, last_error_code="none")
            self._publish(sensor_id)
            return
        manual_until = _dt(state.get("manual_request_until"))
        manual_request = bool(manual_until is not None and manual_until > datetime.now(timezone.utc))
        if not manual_request and not self._endpoint_recent(endpoint):
            # Home Assistant can retain a connectable BLEDevice long after the
            # person/watch has left. Automatic timers must wait for a *fresh*
            # advertisement and must not stamp garmin_last_sync while away.
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=UNREACHABLE_RETRY_DELAY)
            state.update(sync_state="waiting", last_error_code="none", next_attempt=retry_at.isoformat())
            await self._save()
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, UNREACHABLE_RETRY_DELAY)
            return
        if not force:
            last = _dt(state.get("last_successful_sync"))
            if last is not None and datetime.now(timezone.utc) - last < SYNC_INTERVAL:
                return
        if self.provider.sensor_users(sensor_id) or self.provider.sensor_connected(sensor_id):
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=BUSY_RETRY_DELAY)
            state.update(
                sync_state="waiting",
                last_error_code="none",
                next_attempt=retry_at.isoformat(),
            )
            await self._save()
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, BUSY_RETRY_DELAY)
            return

        preferred_source = str(state.get("bluetooth_source") or "") or None
        preferred_route_kind = str(state.get("bluetooth_route_kind") or "") or None
        ble_device, selected_source, route_kind = _select_garmin_ble_route(
            self.hass, endpoint.address, preferred_source
        )

        # Migrate the short-lived 2026.8.18 route-classification bug: ESPHome
        # scanners could be persisted as ``local`` because they expose an
        # adapter-like attribute. If the stored "local" source is now correctly
        # identified as remote, discard that pin and reselect a real host-local
        # BlueZ route. This is capability/path based and contains no device model.
        if (
            preferred_source
            and preferred_route_kind == "local"
            and route_kind == "remote"
        ):
            _LOGGER.warning(
                "Garmin discarding stale Bluetooth source %s: stored as local but now identified as remote for %s",
                preferred_source,
                endpoint.address,
            )
            state.pop("bluetooth_source", None)
            state.pop("bluetooth_route_kind", None)
            preferred_source = None
            ble_device, selected_source, route_kind = _select_garmin_ble_route(
                self.hass, endpoint.address, None
            )
        if ble_device is None:
            # Once paired, a Garmin stays pinned to the same Bluetooth central so
            # its bond is never silently replaced by whichever proxy has the best
            # RSSI today. Persist the sparse wake-up too, so a Home Assistant
            # restart cannot strand the archive until another advertisement changes.
            retry_at = datetime.now(timezone.utc) + timedelta(
                seconds=UNREACHABLE_RETRY_DELAY
            )
            state.update(
                sync_state="waiting",
                last_error_code="none",
                next_attempt=retry_at.isoformat(),
            )
            await self._save()
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, UNREACHABLE_RETRY_DELAY)
            _LOGGER.info(
                "Garmin sync waiting for Bluetooth source %s (%s) for %s",
                preferred_source or "auto", route_kind, endpoint.address,
            )
            return

        _LOGGER.info(
            "Garmin sync selecting Bluetooth source %s (%s) for %s",
            selected_source or "auto", route_kind, endpoint.address,
        )

        lock = self.provider._connect_lock(sensor_id)
        client = None
        session: GarminGfdiSession | None = None
        stage = "connection"
        try:
            # Entire BLE session has a hard upper bound. Every nested transport
            # operation also has a shorter stage timeout.
            async with asyncio.timeout(SESSION_TIMEOUT):
                async with lock:
                    if self.provider.sensor_connected(sensor_id) or self.provider.sensor_users(sensor_id):
                        retry_at = datetime.now(timezone.utc) + timedelta(seconds=BUSY_RETRY_DELAY)
                        state.update(
                            sync_state="waiting",
                            last_error_code="none",
                            next_attempt=retry_at.isoformat(),
                        )
                        await self._save()
                        self._publish(sensor_id)
                        self._schedule_after_current(sensor_id, BUSY_RETRY_DELAY)
                        return
                    state.update(
                        sync_state="connecting",
                        last_sync=datetime.now(timezone.utc).isoformat(),
                        last_error_code="none",
                        next_attempt=None,
                    )
                    self._publish(sensor_id)
                    # Provisioning and archive transport are deliberately two
                    # different connections. The known-good standalone BlueZ path
                    # first creates a durable bond, then starts Garmin Multi-Link on
                    # a fresh encrypted GATT connection. Keeping the connection that
                    # performed numeric-comparison pairing can leave newer watches in
                    # their "finish setup on device" provisioning state and no GFDI
                    # frames arrive.
                    stage = "pairing"
                    bluez_path = (
                        _bluez_device_path(ble_device, endpoint.address)
                        if route_kind == "local"
                        else None
                    )
                    paired = bonded = trusted = False
                    if bluez_path is not None:
                        paired, bonded, trusted = await async_bluez_device_pairing_state(bluez_path)
                    needs_pairing = route_kind != "local" or not (paired and bonded)

                    if needs_pairing:
                        async with temporary_bluez_pairing_agent(
                            endpoint.address, enabled=route_kind == "local"
                        ):
                            async with asyncio.timeout(PAIR_CONNECT_TIMEOUT):
                                client = await self.provider.establish_connection(
                                    ble_device,
                                    sensor.name or endpoint.address,
                                    max_attempts=PAIR_CONNECT_ATTEMPTS,
                                    pair=True,
                                    source=selected_source,
                                )
                        _LOGGER.info(
                            "Garmin Bluetooth pairing connection completed via %s (%s) for %s",
                            selected_source or "auto", route_kind, endpoint.address,
                        )
                        if bluez_path is not None:
                            paired, bonded, trusted = await async_bluez_device_pairing_state(bluez_path)
                            if not (paired and bonded):
                                raise RuntimeError("BlueZ pairing returned without a durable Garmin bond")
                            _LOGGER.info(
                                "Garmin durable BlueZ bond confirmed for %s (trusted=%s)",
                                endpoint.address, trusted,
                            )
                            # The bond itself is central-specific and is now proven,
                            # so remember this source even before Garmin protocol
                            # negotiation. This prevents the next retry from hopping
                            # to a proxy if GFDI itself needs another iteration.
                            if selected_source:
                                state["bluetooth_source"] = selected_source
                                state["bluetooth_route_kind"] = route_kind
                                await self._save()

                        # End the provisioning connection. A short settle period lets
                        # BlueZ publish the durable bond and lets the watch leave its
                        # pairing state before we open the archive session.
                        if client is not None:
                            await self.provider._async_disconnect_client(
                                client, reason="Garmin post-pair provisioning reconnect"
                            )
                            client = None
                        await asyncio.sleep(0.8)

                        refreshed_device, refreshed_source, refreshed_kind = _select_garmin_ble_route(
                            self.hass, endpoint.address, selected_source
                        )
                        if refreshed_device is not None:
                            ble_device = refreshed_device
                            selected_source = refreshed_source or selected_source
                            route_kind = refreshed_kind

                    # All normal archive traffic starts on a fresh bonded connection
                    # with pair=False, matching the successful standalone FIT test and
                    # avoiding a pairing transaction on every periodic sync.
                    #
                    # Full-device sync can leave Garmin Multi-Link in a brief stale
                    # post-disconnect state.  The next GATT connection can be perfectly
                    # valid while the first GFDI handshake receives no CLOSE_ALL/config
                    # response.  Previously that single transient handshake failure
                    # aborted both automatic and manual sync, which became visible once
                    # health history created a multi-session backlog.  Retry exactly one
                    # *fresh* GATT session; never loop on the same client or re-pair.
                    handshake_retry = 0
                    while True:
                        stage = "connection"
                        async with asyncio.timeout(CONNECT_TIMEOUT):
                            client = await self.provider.establish_connection(
                                ble_device,
                                sensor.name or endpoint.address,
                                max_attempts=PAIR_CONNECT_ATTEMPTS,
                                pair=False,
                                source=selected_source,
                            )
                        _LOGGER.info(
                            "Garmin fresh bonded GATT session ready via %s (%s) for %s%s",
                            selected_source or "auto",
                            route_kind,
                            endpoint.address,
                            f" (handshake retry {handshake_retry})" if handshake_retry else "",
                        )
                        stage = "handshake"
                        try:
                            session, candidate_backends = await _start_best_session(client)
                            break
                        except asyncio.CancelledError:
                            raise
                        except Exception as err:
                            if handshake_retry >= HANDSHAKE_RECONNECT_ATTEMPTS:
                                raise
                            handshake_retry += 1
                            _LOGGER.info(
                                "Garmin GFDI handshake did not settle for %s; reconnecting once before backoff: %s: %s",
                                sensor_id,
                                type(err).__name__,
                                err,
                            )
                            await self.provider._async_disconnect_client(
                                client,
                                reason="Garmin GFDI handshake recovery reconnect",
                            )
                            client = None
                            session = None
                            await asyncio.sleep(HANDSHAKE_RECONNECT_DELAY)
                            refreshed_device, refreshed_source, refreshed_kind = _select_garmin_ble_route(
                                self.hass, endpoint.address, selected_source
                            )
                            if refreshed_device is None:
                                raise
                            ble_device = refreshed_device
                            selected_source = refreshed_source or selected_source
                            route_kind = refreshed_kind
                    # A bond belongs to the central that created it, but do not pin a
                    # route merely because a connection call returned successfully.
                    # Authentication can still be absent (ATT error 0x05). Only a
                    # completed Garmin handshake proves this central is usable.
                    if selected_source:
                        state["bluetooth_source"] = selected_source
                        state["bluetooth_route_kind"] = route_kind
                    self._clear_connection_busy_issue(sensor_id)
                    state.pop("manual_request_until", None)
                    _LOGGER.info(
                        "Garmin GFDI handshake succeeded via %s (%s/%s) for %s",
                        session.transport.backend,
                        selected_source or "auto",
                        route_kind,
                        endpoint.address,
                    )
                    # Only a successful connected GATT/GFDI handshake grants the
                    # local workout-history capability. Advertisement vendor
                    # evidence alone remains a candidate, not compatibility proof.
                    self.runtime.set_archive_compatibility(
                        sensor_id, adapter_id="garmin_local", compatible=True
                    )
                    state["transport_candidates"] = list(candidate_backends)[:8]
                    state["backend"] = session.transport.backend
                    self._publish(sensor_id)
                    state["protocol_version"] = session.protocol_version
                    state["sync_state"] = "syncing"
                    self._publish(sensor_id)

                    stage = "catalog"
                    mode, catalog = await session.async_sync_catalog()
                    state["catalog_mode"] = mode
                    activity_catalog_count = sum(
                        1 for item in catalog
                        if (
                            isinstance(item, GarminSyncFile)
                            and (
                                str(item.type_name or "") == "FIT_TYPE_4"
                                or item.type_code == 4
                            )
                        )
                        or (isinstance(item, GarminDirectoryEntry) and item.is_activity)
                    )
                    state["device_workout_count"] = activity_catalog_count
                    state["device_sync_file_count"] = len(catalog)
                    catalog_types = dict(getattr(session, "catalog_type_counts", {}) or {})
                    state["catalog_file_types"] = catalog_types
                    _LOGGER.info(
                        "Garmin read-only catalogue for %s: mode=%s workouts=%s sync_files=%s file_types=%s",
                        sensor_id,
                        mode,
                        activity_catalog_count,
                        len(catalog),
                        catalog_types or {"FIT_TYPE_4": len(catalog)},
                    )
                    files = state.setdefault("files", {})
                    if not isinstance(files, dict):
                        files = state["files"] = {}
                    keys = [self._item_key(item) for item in catalog]

                    def _needs_download(item: GarminSyncFile | GarminDirectoryEntry) -> bool:
                        key = self._item_key(item)
                        if key not in files:
                            return True
                        cached = files.get(key)
                        if not isinstance(cached, dict):
                            return True
                        kind = str(cached.get("kind") or "")
                        # Decoder upgrades re-download both quarantined invalid
                        # payloads and previously unsupported FIT families. This is
                        # how new wellness mappings can recover already-catalogued
                        # data from the watch without clearing the whole archive.
                        if kind == "unsupported":
                            return int(cached.get("decoder_revision") or 0) < GARMIN_PAYLOAD_DECODER_REVISION
                        if kind != "invalid":
                            return False
                        # Re-probe invalid records created before forensic capture
                        # existed, and any quarantined record whose Garmin catalogue
                        # fingerprint changed. This lets an already-seen invalid file
                        # be captured after an upgrade instead of becoming permanent
                        # opaque state.
                        return (
                            int(cached.get("decoder_revision") or 0) < GARMIN_PAYLOAD_DECODER_REVISION
                            or not cached.get("capture_token")
                            or str(cached.get("catalog_fingerprint") or "")
                            != _catalog_item_fingerprint(item)
                        )

                    uncached_items = [item for item in catalog if _needs_download(item)]
                    # Garmin monitoring/weight files may be circular and can keep
                    # the same FileSync identity while their contents change. Once
                    # the initial backlog is cached, refresh the newest file from
                    # each health family on every normal sync. Metadata fingerprint
                    # changes also force a refresh immediately.
                    refresh_items: list[GarminSyncFile | GarminDirectoryEntry] = []
                    newest_health: dict[str, GarminSyncFile | GarminDirectoryEntry] = {}
                    for item in catalog:
                        key = self._item_key(item)
                        cached = files.get(key)
                        if not _catalog_item_is_health(item) and not (
                            isinstance(cached, dict) and cached.get("kind") == "health"
                        ):
                            continue
                        newest_health.setdefault(_catalog_item_type(item), item)
                    for item in newest_health.values():
                        key = self._item_key(item)
                        cached = files.get(key)
                        if not isinstance(cached, dict):
                            continue
                        fingerprint = _catalog_item_fingerprint(item)
                        if force or str(cached.get("catalog_fingerprint") or "") != fingerprint:
                            refresh_items.append(item)
                    uncached_keys = {self._item_key(item) for item in uncached_items}
                    pending_items = uncached_items + [
                        item for item in refresh_items
                        if self._item_key(item) not in uncached_keys
                    ]
                    state["pending_file_count"] = len(pending_items)
                    self._publish(sensor_id)

                    records_to_import = [
                        record for record in files.values()
                        if isinstance(record, dict)
                        and record.get("kind") in {"activity", "health"}
                        and any(
                            profile_id not in {str(v) for v in record.get("imported_profiles") or []}
                            for profile_id in profile_ids
                        )
                    ][:MAX_FILES_PER_SESSION]
                    slots = max(0, MAX_FILES_PER_SESSION - len(records_to_import))
                    batch_bytes = 0
                    file_work_started = self.hass.loop.time()

                    for item in pending_items[:slots]:
                        # The hard SESSION_TIMEOUT remains authoritative.  This
                        # softer budget prevents a long tail of tiny health files
                        # from consuming the entire timeout and turning a healthy
                        # partial sync into a timeout error.  At least one file is
                        # always allowed so a slow individual transfer can still
                        # make checkpointed progress.
                        if (
                            batch_bytes
                            and self.hass.loop.time() - file_work_started
                            >= SESSION_FILE_WORK_BUDGET
                        ):
                            break
                        if not self.runtime.sensor_archive_profile_ids(sensor_id):
                            return
                        expected_size = max(0, int(getattr(item, "size", 0) or 0))
                        if expected_size > MAX_BYTES_PER_SYNC:
                            raise ValueError("Garmin FIT file exceeds per-sync byte budget")
                        if batch_bytes and batch_bytes + expected_size > MAX_BYTES_PER_SYNC:
                            break
                        key = self._item_key(item)
                        state.update(active_file=key, downloaded_bytes=0)
                        self._publish(sensor_id)
                        stage = "transfer"
                        downloaded = await session.async_download_file(
                            mode,
                            item,
                            progress=lambda size, sid=sensor_id: self._progress_update(sid, size),
                        )
                        if len(downloaded.data) > MAX_BYTES_PER_SYNC:
                            raise ValueError("Garmin transfer exceeds per-sync byte budget")
                        stage = "validation"
                        compressed = mode == "filesync_v2"
                        try:
                            decoded, fit_size = await self.hass.async_add_executor_job(
                                partial(
                                    _decode_downloaded_file,
                                    downloaded.data,
                                    compressed=compressed,
                                    sensor_id=sensor_id,
                                    source_key=downloaded.key,
                                    source_label=sensor.name,
                                    file_type=downloaded.type_name or _catalog_item_type(item),
                                )
                            )
                        except Exception as err:
                            # Full-device FileSync exposes more than workout files,
                            # and one corrupt/opaque record must never abort the
                            # entire archive session. Retry the exact catalogue
                            # fingerprint a bounded number of times, then quarantine
                            # only that record until Garmin changes its metadata.
                            failures = state.setdefault("validation_failures", {})
                            if not isinstance(failures, dict):
                                failures = state["validation_failures"] = {}
                            fingerprint = _catalog_item_fingerprint(item)
                            capture = await self.hass.async_add_executor_job(
                                partial(
                                    _capture_invalid_payload,
                                    self.hass.config.path(".storage", INVALID_CAPTURE_DIRNAME),
                                    sensor_id=sensor_id,
                                    source_key=downloaded.key,
                                    file_type=downloaded.type_name or _catalog_item_type(item),
                                    fingerprint=fingerprint,
                                    raw_data=downloaded.data,
                                    compressed=compressed,
                                    error=f"{type(err).__name__}: {err}",
                                )
                            )
                            state["last_invalid_capture"] = {
                                "file_type": downloaded.type_name or _catalog_item_type(item),
                                "source_key": downloaded.key,
                                "token": capture.get("token"),
                                "diagnostics": capture.get("diagnostics") or {},
                            }
                            previous_failure = failures.get(key)
                            same_file = bool(
                                isinstance(previous_failure, dict)
                                and str(previous_failure.get("catalog_fingerprint") or "")
                                == fingerprint
                            )
                            failure_count = (
                                int(previous_failure.get("count") or 0) + 1
                                if same_file
                                else 1
                            )
                            failures[key] = {
                                "catalog_fingerprint": fingerprint,
                                "count": failure_count,
                                "last_failure": datetime.now(timezone.utc).isoformat(),
                                "error": f"{type(err).__name__}: {err}"[:256],
                                "capture_token": capture.get("token"),
                                "diagnostics": capture.get("diagnostics") or {},
                                "decoder_revision": GARMIN_PAYLOAD_DECODER_REVISION,
                            }
                            quarantined = failure_count >= MAX_FILE_VALIDATION_FAILURES
                            if quarantined:
                                files[key] = {
                                    "kind": "invalid",
                                    "size": len(downloaded.data),
                                    "file_type": downloaded.type_name,
                                    "catalog_fingerprint": fingerprint,
                                    "completed_at": datetime.now(timezone.utc).isoformat(),
                                    "validation_error": f"{type(err).__name__}: {err}"[:256],
                                    "capture_token": capture.get("token"),
                                    "diagnostics": capture.get("diagnostics") or {},
                                    "decoder_revision": GARMIN_PAYLOAD_DECODER_REVISION,
                                    "imported_profiles": [],
                                }
                                failures.pop(key, None)
                                state["quarantined_file_count"] = sum(
                                    1
                                    for value in files.values()
                                    if isinstance(value, dict) and value.get("kind") == "invalid"
                                )
                                _LOGGER.warning(
                                    "Garmin quarantined unreadable device file for %s after %s attempts: type=%s key=%s error=%s: %s",
                                    sensor_id,
                                    failure_count,
                                    downloaded.type_name or _catalog_item_type(item),
                                    key,
                                    type(err).__name__,
                                    err,
                                )
                            else:
                                _LOGGER.warning(
                                    "Garmin device file validation failed for %s (%s/%s); continuing session and retrying this file later: type=%s key=%s error=%s: %s",
                                    sensor_id,
                                    failure_count,
                                    MAX_FILE_VALIDATION_FAILURES,
                                    downloaded.type_name or _catalog_item_type(item),
                                    key,
                                    type(err).__name__,
                                    err,
                                )
                            state.update(
                                active_file=None,
                                downloaded_bytes=len(downloaded.data),
                                pending_file_count=sum(
                                    1 for candidate in catalog if _needs_download(candidate)
                                ),
                            )
                            await self._save()
                            self._publish(sensor_id)
                            batch_bytes += len(downloaded.data)
                            continue
                        failures = state.get("validation_failures")
                        if isinstance(failures, dict):
                            failures.pop(key, None)
                        stage = "import"
                        record = {
                            **decoded,
                            "size": fit_size,
                            "file_type": downloaded.type_name,
                            "catalog_fingerprint": _catalog_item_fingerprint(item),
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "imported_profiles": [],
                        }
                        files[key] = record
                        if record.get("kind") in {"activity", "health"}:
                            records_to_import.append(record)
                        if record.get("kind") == "activity":
                            payload = record.get("workout") or {}
                            start = _dt(payload.get("start")) if isinstance(payload, dict) else None
                            if start is not None:
                                latest = start.isoformat()
                                if not state.get("latest_workout") or latest > state["latest_workout"]:
                                    state["latest_workout"] = latest
                        elif record.get("kind") == "health":
                            state["latest_health_sync"] = datetime.now(timezone.utc).isoformat()
                            metric_count = int(record.get("health_metric_points") or 0)
                            sleep_count = int(record.get("health_sleep_records") or 0)
                            state["health_metric_point_count"] = int(state.get("health_metric_point_count") or 0) + metric_count
                            state["health_sleep_record_count"] = int(state.get("health_sleep_record_count") or 0) + sleep_count
                            _LOGGER.info(
                                "Garmin health FIT decoded for %s: type=%s metrics=%s sleep_records=%s",
                                sensor_id, downloaded.type_name or _catalog_item_type(item), metric_count, sleep_count,
                            )
                        elif record.get("kind") == "device_artifact":
                            artifact = record.get("device_artifact") or {}
                            _LOGGER.info(
                                "Garmin structured device artifact decoded for %s: type=%s artifact=%s name=%s",
                                sensor_id,
                                downloaded.type_name or _catalog_item_type(item),
                                record.get("artifact_type") or "unknown",
                                str(artifact.get("name") or "")[:96] if isinstance(artifact, dict) else "",
                            )
                        elif record.get("kind") == "unsupported":
                            _LOGGER.debug(
                                "Garmin FIT family not yet mapped for %s: type=%s messages=%s",
                                sensor_id,
                                downloaded.type_name or _catalog_item_type(item),
                                record.get("fit_messages") or [],
                            )
                        state.update(
                            active_file=None,
                            downloaded_bytes=fit_size,
                            pending_file_count=sum(
                                1 for candidate in catalog if _needs_download(candidate)
                            ),
                        )
                        # Checkpoint each complete FIT before touching profile history.
                        await self._save()
                        self._publish(sensor_id)
                        batch_bytes += fit_size
                        if batch_bytes >= MAX_BYTES_PER_SYNC:
                            break

                    stage = "import"
                    # Keep one initialized Garmin session long enough to drain a
                    # small archive burst, but preserve the original two-workout
                    # import/checkpoint chunk. This avoids repeated GFDI handshakes
                    # while keeping profile writes and restart recovery bounded.
                    for offset in range(0, len(records_to_import), MAX_FILES_PER_SYNC):
                        chunk = records_to_import[offset : offset + MAX_FILES_PER_SYNC]
                        async with asyncio.timeout(IMPORT_TIMEOUT):
                            await self._import_records(chunk, profile_ids)
                        # Persist imported_profiles after every small chunk. A crash
                        # never forces an already-finished burst to start from zero.
                        await self._save()
                    self._prune_file_records(files, set(keys))
                    remaining = [item for item in catalog if _needs_download(item)]
                    cached_pending = any(
                        isinstance(record, dict)
                        and record.get("kind") in {"activity", "health"}
                        and any(
                            profile_id not in {str(v) for v in record.get("imported_profiles") or []}
                            for profile_id in profile_ids
                        )
                        for record in files.values()
                    )
                    more_work = bool(remaining or cached_pending)
                    now_utc = datetime.now(timezone.utc)
                    state.update(
                        sync_state="cooldown" if more_work else "ready",
                        last_error_code="none",
                        last_transient_error_code="none",
                        retry_count=0,
                        partial_retry_count=0,
                        last_batch_success=now_utc.isoformat(),
                        next_attempt=(
                            (now_utc + timedelta(seconds=BATCH_CONTINUE_DELAY)).isoformat()
                            if more_work
                            else (now_utc + SYNC_INTERVAL).isoformat()
                        ),
                        active_file=None,
                        pending_file_count=len(remaining),
                    )
                    if not more_work:
                        state["last_successful_sync"] = now_utc.isoformat()
                    self._clear_pairing_issue(sensor_id)
                    await self._save()
                    self._publish(sensor_id)
                    if more_work:
                        self._schedule_after_current(sensor_id, BATCH_CONTINUE_DELAY)
                    else:
                        # Do not depend on advertisement payload changes for the
                        # next archive poll; HA intentionally deduplicates stable
                        # BLE advertisements. One tracked timer per accepted Garmin
                        # keeps automatic sync reliable without continuous radio work.
                        self._schedule_after_current(sensor_id, SYNC_INTERVAL.total_seconds())
        except asyncio.CancelledError:
            raise
        except GarminUnsupportedTransport as err:
            self._clear_pairing_issue(sensor_id)
            # Definitive V2/V1/V0 incompatibility is sticky until the device is
            # removed/re-discovered. Do not keep an incompatible Garmin in Smart
            # workout choices or wake Bluetooth every few hours forever.
            self.runtime.set_archive_compatibility(
                sensor_id, adapter_id="garmin_local", compatible=False
            )
            state = self._device(sensor_id)
            state.update(
                sync_state="unsupported",
                last_error_code="unsupported_transport",
                retry_count=0,
                next_attempt=None,
            )
            await self._save()
            self._publish(sensor_id)
            _LOGGER.debug("Garmin transport unsupported for %s: %s", sensor_id, err)
        except Exception as err:
            state = self._device(sensor_id)
            retries = int(state.get("retry_count") or 0) + 1
            text = str(err).lower()
            error_code = _ERROR_CODE.get(stage, "unknown")
            if stage == "pairing":
                error_code = "pairing_required"
            elif stage in {"connection", "handshake"} and any(
                token in text
                for token in (
                    "pair", "bond", "authentication", "not authorized",
                    "passkey", "pin", "rejected", "canceled", "cancelled",
                )
            ):
                error_code = "pairing_required"
            active_host_contention = bool(
                stage == "connection"
                and self._endpoint_recent(endpoint)
                and error_code != "pairing_required"
                and any(token in text for token in (
                    "busy", "in progress", "connection refused", "connection abort",
                    "le-connection-abort", "not available", "failed to connect",
                    "org.bluez.error.failed", "operation already",
                ))
            )
            # Garmin watches can keep their freshly-closed Multi-Link channel in
            # a short post-sync cooldown.  A partial batch has already proven the
            # bond, GFDI and FileSync path, so a transient connection/handshake or
            # catalogue failure immediately after that success is not evidence of
            # broken pairing.  Keep the durable pending checkpoint and retry at a
            # calm cadence instead of requiring an HA restart or hammering BLE.
            partial_retry = False
            try:
                pending = max(0, int(state.get("pending_file_count") or 0))
            except (TypeError, ValueError):
                pending = 0
            last_batch_success = _dt(state.get("last_batch_success"))
            recent_partial = bool(
                pending
                and last_batch_success is not None
                and (datetime.now(timezone.utc) - last_batch_success).total_seconds()
                <= PARTIAL_BATCH_RECENT_WINDOW
                and stage in {"connection", "handshake", "catalog"}
                and error_code != "pairing_required"
            )
            partial_retries = int(state.get("partial_retry_count") or 0)
            if active_host_contention:
                self._clear_pairing_issue(sensor_id)
                # A phone owning the Garmin connection is normal during automatic
                # background operation. Do not turn that transient contention into
                # a persistent Repairs notification on every HA restart. Surface a
                # guided Repair only when the user explicitly pressed Sync now; in
                # the background keep the state as waiting and retry quietly.
                if manual_request:
                    self._report_connection_busy(sensor_id)
                else:
                    self._clear_connection_busy_issue(sensor_id)
                delay = PHONE_HOST_RETRY_DELAY
                retries = max(0, int(state.get("retry_count") or 0))
            elif recent_partial and partial_retries < MAX_PARTIAL_BATCH_RETRIES:
                partial_retry = True
                partial_retries += 1
                self._clear_pairing_issue(sensor_id)
                self._clear_connection_busy_issue(sensor_id)
                delay = PARTIAL_BATCH_RETRY_DELAY
                retries = max(0, int(state.get("retry_count") or 0))
            elif error_code == "pairing_required":
                self._report_pairing_required(sensor_id)
                delay = UNSUPPORTED_RETRY_DELAY
            elif retries >= MAX_RETRIES:
                self._clear_pairing_issue(sensor_id)
                # Repeated background failures must become progressively cheaper
                # instead of waking the Bluetooth stack every 30 minutes forever.
                delay = DEGRADED_RETRY_DELAY
            else:
                self._clear_pairing_issue(sensor_id)
                delay = min(30 * 60.0, 60.0 * (2 ** min(retries - 1, 5)))
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            state.update(
                sync_state=(
                    "waiting"
                    if active_host_contention
                    else (
                        "cooldown"
                        if partial_retry
                        else ("error" if retries >= MAX_RETRIES else "retrying")
                    )
                ),
                # A transient post-batch handshake/catalog miss is a cooldown
                # condition, not the outcome of the batch that already succeeded.
                # Keep the raw code privately for diagnostics while the normal
                # Last sync error entity remains truthful.
                last_error_code="none" if partial_retry else error_code,
                last_transient_error_code=error_code if partial_retry else "none",
                retry_count=retries,
                partial_retry_count=partial_retries if partial_retry else 0,
                next_attempt=retry_at.isoformat(),
                active_file=None,
            )
            await self._save()
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, delay)
            _LOGGER.warning(
                "Garmin local sync failed for %s at %s via %s (%s): %s: %s",
                sensor_id,
                stage,
                selected_source or "auto",
                route_kind,
                type(err).__name__,
                err,
            )
        finally:
            if session is not None:
                try:
                    async with asyncio.timeout(CLEANUP_TIMEOUT):
                        await session.async_stop(disconnecting=True)
                except Exception:
                    pass
            if client is not None:
                await self.provider._async_disconnect_client(client, reason="Garmin local sync cleanup")
                clear_history = getattr(bluetooth, "async_clear_advertisement_history", None)
                if clear_history is not None:
                    try:
                        clear_history(self.hass, endpoint.address)
                    except Exception:
                        _LOGGER.debug(
                            "Unable to clear Garmin Bluetooth advertisement history for %s",
                            sensor_id,
                            exc_info=True,
                        )
            self.runtime._notify_values_throttled({
                (self.runtime.resolve_sensor_id(sensor_id), "gatt_connection", None)
            })

    def identity_conflict_repaired(self, sensor_id: str) -> None:
        """Remove Garmin-owned diagnostics/entities from a detached stale alias."""
        runtime = self.runtime
        sensor_id = runtime.resolve_sensor_id(sensor_id)
        detail_keys = [
            str(key)
            for key in tuple(runtime.sensor_detail_values.get(sensor_id, {}))
            if str(key).startswith("garmin_")
        ]
        runtime.clear_sensor_details_prefix(sensor_id, "garmin_")

        try:
            from homeassistant.helpers import entity_registry as er

            registry = er.async_get(runtime.hass)
            unique_ids = [f"fitness_{sensor_id}_garmin_sync_workouts"]
            unique_ids.extend(
                f"fitness_{sensor_id}_detail_{key}" for key in detail_keys
            )
            for platform, unique_id in (
                [("button", unique_ids[0])]
                + [("sensor", value) for value in unique_ids[1:]]
            ):
                entity_id = registry.async_get_entity_id(
                    platform, DOMAIN, unique_id
                )
                if entity_id is not None:
                    registry.async_remove(entity_id)
        except Exception:
            _LOGGER.debug(
                "Unable to remove stale Garmin archive entities from %s",
                sensor_id,
                exc_info=True,
            )

    async def async_shutdown(self) -> None:
        self._stopping = True
        if self._reconfigure_unsub is not None:
            self._reconfigure_unsub()
            self._reconfigure_unsub = None
        tasks = list({*self._tasks.values(), *self._background})
        self._tasks.clear()
        self._active_sync.clear()
        self._background.clear()
        self._queued.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            try:
                async with asyncio.timeout(SHUTDOWN_TIMEOUT):
                    await asyncio.gather(*tasks, return_exceptions=True)
            except TimeoutError:
                _LOGGER.warning("Timed out waiting for Garmin local sync shutdown")
