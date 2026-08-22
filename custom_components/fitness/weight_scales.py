"""Shared scale routing for Fitness profiles.

One Home Assistant scale entity may be used by several Fitness profiles.  The
router listens to each configured scale exactly once, performs a tiny bounded
matching heuristic after the value has stabilised, and waits for an explicit
user confirmation before changing any profile weight.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .const import CONF_PROFILE_NAME, CONF_WEIGHT_SCALE_ENTITY, DOMAIN
from .providers.entities import convert_to_canonical

_LOGGER = logging.getLogger(__name__)

ROUTER_DATA_KEY = "_weight_scale_router"
STORE_VERSION = 1
STORE_KEY = "fitness.shared_weight_scales"
MAX_TRACKED_SCALES = 16
MAX_PENDING_MEASUREMENTS = 16
STABILIZE_SECONDS = 2.5
PENDING_TTL_HOURS = 24
MIN_WEIGHT_KG = 20.0
MAX_WEIGHT_KG = 500.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value or ""))
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _source_label(value: Any, limit: int = 96) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


class SharedWeightScaleRouter:
    """Route shared scale measurements without polling or automatic assignment."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = Store(hass, STORE_VERSION, STORE_KEY)
        self._profiles: dict[str, Any] = {}
        self._state_unsub: Callable[[], None] | None = None
        self._tracked_entities: tuple[str, ...] = ()
        self._debounce_tasks: dict[str, asyncio.Task] = {}
        self._listeners: set[Callable[[], None]] = set()
        self._pending: list[dict[str, Any]] = []
        self._last_measurements: dict[str, float] = {}
        self._save_task: asyncio.Task | None = None
        self._loaded = False
        self._load_lock = asyncio.Lock()
        self._sequence = 0

    async def async_initialize(self) -> None:
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                return
            stored = await self.store.async_load() or {}
            now = _utcnow()
            cutoff = now - timedelta(hours=PENDING_TTL_HOURS)
            pending: list[dict[str, Any]] = []
            for raw in list(stored.get("pending") or [])[-MAX_PENDING_MEASUREMENTS:]:
                if not isinstance(raw, dict):
                    continue
                measured_at = _parse_dt(raw.get("measured_at"))
                if measured_at is None or measured_at < cutoff:
                    continue
                try:
                    value = float(raw.get("value_kg"))
                except (TypeError, ValueError):
                    continue
                if not MIN_WEIGHT_KG <= value <= MAX_WEIGHT_KG:
                    continue
                candidates = [str(item) for item in raw.get("profile_entry_ids") or [] if item]
                if not candidates:
                    continue
                pending.append(
                    {
                        "id": str(raw.get("id") or "")[:96],
                        "entity_id": str(raw.get("entity_id") or "")[:128],
                        "value_kg": round(value, 3),
                        "measured_at": measured_at.isoformat(),
                        "profile_entry_ids": candidates[:32],
                        "suggested_profile_id": str(raw.get("suggested_profile_id") or ""),
                        "match_delta_kg": raw.get("match_delta_kg"),
                        "dismissed_profile_ids": [
                            str(item) for item in raw.get("dismissed_profile_ids") or []
                            if str(item) in candidates
                        ][:32],
                        "source_kind": _source_label(raw.get("source_kind"), 32),
                        "source_integration": _source_label(raw.get("source_integration"), 64),
                        "source_device": _source_label(raw.get("source_device"), 96),
                        "source_display": _source_label(raw.get("source_display"), 192),
                    }
                )
            self._pending = pending[-MAX_PENDING_MEASUREMENTS:]
            raw_last_values = stored.get("last_values") or {}
            if isinstance(raw_last_values, dict):
                for entity_id, raw_value in list(raw_last_values.items())[:MAX_TRACKED_SCALES]:
                    entity_id = str(entity_id or "")[:128]
                    try:
                        value = float(raw_value)
                    except (TypeError, ValueError):
                        continue
                    if entity_id.startswith("sensor.") and math.isfinite(value) and MIN_WEIGHT_KG <= value <= MAX_WEIGHT_KG:
                        self._last_measurements[entity_id] = round(value, 3)
            self._sequence = int(stored.get("sequence") or 0)
            self._loaded = True

    async def async_register_profile(self, entry, manager) -> None:
        await self.async_initialize()
        self._profiles[entry.entry_id] = manager
        self._rebind_listener()
        self._prune_pending()

    async def async_unregister_profile(self, entry_id: str, *, permanent: bool = False) -> None:
        """Detach a loaded profile without losing pending confirmations on reload.

        Config-entry option changes unload/reload the profile.  Only an actual
        config-entry removal may delete that profile from persisted pending
        scale measurements.
        """
        entry_id = str(entry_id)
        self._profiles.pop(entry_id, None)
        self._rebind_listener()
        if not permanent:
            return

        changed = False
        for item in list(self._pending):
            candidates = [pid for pid in item["profile_entry_ids"] if pid != entry_id]
            if candidates != item["profile_entry_ids"]:
                item["profile_entry_ids"] = candidates
                changed = True
            if not candidates:
                self._pending.remove(item)
                changed = True
            elif item.get("suggested_profile_id") not in candidates:
                item["suggested_profile_id"] = candidates[0]
                item["match_delta_kg"] = None
                changed = True
        if changed:
            self._schedule_save()
            self._notify_listeners()

    def _configured_scale(self, manager) -> str:
        return str(manager.config.get(CONF_WEIGHT_SCALE_ENTITY) or "").strip()

    def _measurement_source(self, entity_id: str) -> dict[str, str]:
        """Describe the real Home Assistant source behind a weight entity.

        Classification is deliberately vendor-neutral.  A provider, wearable,
        phone or other device that happens to expose a weight value remains a
        provider/device source; it is called a physical scale only when Home
        Assistant's device metadata or the device's sibling composition sensors
        provide scale-specific evidence.
        """
        state = self.hass.states.get(entity_id)
        friendly = _source_label(
            state.attributes.get("friendly_name") if state is not None else ""
        )
        platform = ""
        device_name = ""
        manufacturer = ""
        model = ""
        device_id = ""
        sibling_evidence: list[str] = []
        try:
            registry = er.async_get(self.hass)
            entity_entry = registry.async_get(entity_id)
        except Exception:  # noqa: BLE001 - registry metadata is optional context
            registry = None
            entity_entry = None
        if entity_entry is not None:
            platform = _source_label(getattr(entity_entry, "platform", ""), 64).lower()
            device_id = str(getattr(entity_entry, "device_id", "") or "")
            if device_id:
                try:
                    device = dr.async_get(self.hass).async_get(device_id)
                except Exception:  # noqa: BLE001 - never block a measurement on metadata
                    device = None
                if device is not None:
                    device_name = _source_label(
                        getattr(device, "name_by_user", None)
                        or getattr(device, "name", None)
                        or getattr(device, "model", None)
                    )
                    manufacturer = _source_label(getattr(device, "manufacturer", None), 64)
                    model = _source_label(getattr(device, "model", None), 96)
                if registry is not None:
                    for sibling in registry.entities.values():
                        if str(getattr(sibling, "device_id", "") or "") != device_id:
                            continue
                        sibling_state = self.hass.states.get(sibling.entity_id)
                        sibling_evidence.extend(
                            str(value or "")
                            for value in (
                                sibling.entity_id,
                                getattr(sibling, "name", None),
                                getattr(sibling, "original_name", None),
                                getattr(sibling, "translation_key", None),
                                (sibling_state.attributes.get("friendly_name") if sibling_state is not None else None),
                                (sibling_state.attributes.get("device_class") if sibling_state is not None else None),
                            )
                            if value
                        )

        evidence = " ".join(
            part.casefold()
            for part in (platform, device_name, manufacturer, model, friendly, entity_id)
            if part
        )
        scale_markers = (
            "scale", "weighing", "body composition", "body_comp", "impedance",
            "waage", "bilancia", "báscula", "balance", "weegschaal", "waga",
        )
        wearable_markers = (
            "watch", "forerunner", "fenix", "epix", "vivoactive", "venu",
            "band", "ring", "tracker", "phone", "smartphone", "bike computer",
            "cycling computer", "edge ",
        )
        composition_markers = (
            "body_fat", "body fat", "impedance", "body_water", "body water",
            "muscle_mass", "muscle mass", "bone_mass", "bone mass",
            "visceral_fat", "visceral fat", "fat_free_mass", "fat free mass",
        )
        sibling_text = " ".join(value.casefold() for value in sibling_evidence)
        composition_hits = sum(1 for marker in composition_markers if marker in sibling_text)
        explicit_scale = any(marker in evidence for marker in scale_markers)
        explicit_non_scale_device = any(marker in evidence for marker in wearable_markers)
        is_physical_scale = explicit_scale or (
            composition_hits >= 2 and not explicit_non_scale_device
        )

        provider = platform.replace("_", " ").strip().title() if platform else ""
        kind = "scale" if is_physical_scale else ("provider" if platform else "entity")

        parts: list[str] = []
        if provider:
            parts.append(provider)
        if device_name and device_name.casefold() not in {part.casefold() for part in parts}:
            parts.append(device_name)
        elif not device_name and friendly and friendly.casefold() not in {part.casefold() for part in parts}:
            parts.append(friendly)
        display = " · ".join(parts) or friendly or entity_id
        return {
            "source_kind": kind,
            "source_integration": provider[:64],
            "source_device": device_name[:96],
            "source_display": display[:192],
        }

    def _rebind_listener(self) -> None:
        entities = tuple(
            sorted(
                {
                    entity_id
                    for manager in self._profiles.values()
                    if (entity_id := self._configured_scale(manager)).startswith("sensor.")
                }
            )[:MAX_TRACKED_SCALES]
        )
        if entities == self._tracked_entities:
            return
        if self._state_unsub is not None:
            self._state_unsub()
            self._state_unsub = None
        self._tracked_entities = entities
        if entities:
            self._state_unsub = async_track_state_change_event(
                self.hass, entities, self._handle_state_event
            )

    @callback
    def _handle_state_event(self, event: Event) -> None:
        entity_id = str(event.data.get("entity_id") or "")
        new_state = event.data.get("new_state")
        if entity_id not in self._tracked_entities or new_state is None:
            return
        old = self._debounce_tasks.pop(entity_id, None)
        if old is not None and not old.done():
            old.cancel()

        async def _settle() -> None:
            try:
                await asyncio.sleep(STABILIZE_SECONDS)
                current = self.hass.states.get(entity_id)
                if current is None or current.state in ("", "unknown", "unavailable"):
                    return
                await self._async_process_measurement(
                    entity_id,
                    current.state,
                    current.attributes.get("unit_of_measurement"),
                    getattr(current, "last_updated", None),
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - a scale must never affect HA stability
                _LOGGER.exception("Unable to route Fitness shared scale measurement")
            finally:
                task = self._debounce_tasks.get(entity_id)
                if task is asyncio.current_task():
                    self._debounce_tasks.pop(entity_id, None)

        task = self.hass.async_create_background_task(
            _settle(), f"fitness shared scale settle {entity_id}", eager_start=False
        )
        self._debounce_tasks[entity_id] = task

    async def _async_process_measurement(
        self, entity_id: str, raw_value: Any, unit: str | None, measured_at: datetime | None
    ) -> None:
        try:
            numeric = float(raw_value)
        except (TypeError, ValueError):
            return
        value_kg, _unit = convert_to_canonical(numeric, unit, "weight")
        if value_kg is None:
            return
        value_kg = float(value_kg)
        if not math.isfinite(value_kg) or not MIN_WEIGHT_KG <= value_kg <= MAX_WEIGHT_KG:
            return

        now = _utcnow()
        rounded = round(value_kg, 3)
        previous = self._last_measurements.get(entity_id)
        # A fresh scale measurement must actually change the weight value. HA may
        # emit state_changed for attribute-only updates; never ask again for the
        # exact same canonical weight, regardless of how much time passed.
        if previous is not None and round(float(previous), 3) == rounded:
            return
        self._last_measurements[entity_id] = rounded

        candidates = [
            entry_id
            for entry_id, manager in self._profiles.items()
            if self._configured_scale(manager) == entity_id
        ]
        if not candidates:
            return

        # When a scale belongs to only one Fitness profile, there is no ambiguity
        # to resolve. If its newly observed value already equals that profile's
        # confirmed weight, there is also nothing useful to ask or update.
        if len(candidates) == 1:
            only_manager = self._profiles.get(candidates[0])
            current_weight = getattr(only_manager, "current_weight_kg", None) if only_manager is not None else None
            try:
                if current_weight is not None and round(float(current_weight), 3) == rounded:
                    self._schedule_save()
                    return
            except (TypeError, ValueError):
                pass

        nearest: tuple[float, str] | None = None
        for entry_id in candidates:
            manager = self._profiles[entry_id]
            current_weight = getattr(manager, "current_weight_kg", None)
            if current_weight is None:
                continue
            try:
                delta = abs(float(current_weight) - value_kg)
            except (TypeError, ValueError):
                continue
            if nearest is None or (delta, entry_id) < nearest:
                nearest = (delta, entry_id)

        suggested = nearest[1] if nearest is not None else candidates[0]
        self._sequence += 1
        timestamp = measured_at if isinstance(measured_at, datetime) else now
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        source = self._measurement_source(entity_id)
        item = {
            "id": f"scale-{self._sequence}",
            "entity_id": entity_id,
            "value_kg": round(value_kg, 3),
            "measured_at": timestamp.astimezone(timezone.utc).isoformat(),
            "profile_entry_ids": candidates[:32],
            "suggested_profile_id": suggested,
            "match_delta_kg": round(nearest[0], 3) if nearest is not None else None,
            "dismissed_profile_ids": [],
            **source,
        }
        # A scale can chatter while a person remains standing on it. Keep only
        # the newest unconfirmed measurement for that physical source.
        self._pending = [row for row in self._pending if row.get("entity_id") != entity_id]
        self._pending.append(item)
        self._pending = self._pending[-MAX_PENDING_MEASUREMENTS:]
        self._schedule_save()
        self._notify_listeners()

    def _prune_pending(self) -> None:
        # Profile entries are registered one-by-one during Home Assistant
        # startup.  Pruning candidate IDs against only the profiles loaded so
        # far would silently lose confirmations for profiles that have not yet
        # finished setup.  Permanent removals are handled explicitly by
        # async_unregister_profile(..., permanent=True).
        cutoff = _utcnow() - timedelta(hours=PENDING_TTL_HOURS)
        kept = []
        for item in self._pending:
            measured_at = _parse_dt(item.get("measured_at"))
            candidates = [str(pid) for pid in item.get("profile_entry_ids") or [] if pid]
            if measured_at is None or measured_at < cutoff or not candidates:
                continue
            item["profile_entry_ids"] = candidates[:32]
            kept.append(item)
        if len(kept) != len(self._pending):
            self._pending = kept[-MAX_PENDING_MEASUREMENTS:]
            self._schedule_save()

    def pending_for(
        self,
        visible_profile_ids: set[str] | list[str] | tuple[str, ...],
        *,
        require_profile_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return only pending measurements the caller may act on."""
        allowed = {str(item) for item in visible_profile_ids}
        required = str(require_profile_id or "")
        result: list[dict[str, Any]] = []
        for item in self._pending:
            original_candidates = [str(pid) for pid in item.get("profile_entry_ids") or []]
            dismissed = {str(pid) for pid in item.get("dismissed_profile_ids") or []}
            if required and (required not in original_candidates or required in dismissed):
                continue
            candidates = [pid for pid in original_candidates if pid in allowed]
            if not candidates:
                continue
            suggested = str(item.get("suggested_profile_id") or "")
            if suggested not in candidates:
                suggested = candidates[0]
            candidate_rows = []
            for entry_id in candidates:
                manager = self._profiles.get(entry_id)
                if manager is None:
                    continue
                candidate_rows.append(
                    {
                        "entry_id": entry_id,
                        "profile_name": str(
                            manager.config.get(CONF_PROFILE_NAME)
                            or getattr(manager.entry, "title", "")
                            or entry_id
                        )[:96],
                    }
                )
            if not candidate_rows:
                continue
            source = {
                "source_kind": _source_label(item.get("source_kind"), 32),
                "source_integration": _source_label(item.get("source_integration"), 64),
                "source_device": _source_label(item.get("source_device"), 96),
                "source_display": _source_label(item.get("source_display"), 192),
            }
            if not source["source_display"]:
                source = self._measurement_source(str(item.get("entity_id") or ""))
            result.append(
                {
                    "id": str(item.get("id") or ""),
                    "entity_id": str(item.get("entity_id") or ""),
                    "value_kg": item.get("value_kg"),
                    "measured_at": item.get("measured_at"),
                    "suggested_profile_id": suggested,
                    "match_delta_kg": item.get("match_delta_kg"),
                    "dismissed_profile_ids": sorted(dismissed),
                    "candidates": candidate_rows,
                    **source,
                }
            )
        return result[:MAX_PENDING_MEASUREMENTS]

    async def async_confirm(
        self, measurement_id: str, profile_entry_id: str, allowed_profile_ids: set[str]
    ) -> bool:
        measurement_id = str(measurement_id or "")
        profile_entry_id = str(profile_entry_id or "")
        if profile_entry_id not in allowed_profile_ids:
            return False
        item = next((row for row in self._pending if row.get("id") == measurement_id), None)
        if item is None or profile_entry_id not in (item.get("profile_entry_ids") or []):
            return False
        manager = self._profiles.get(profile_entry_id)
        if manager is None:
            return False
        applied = await manager.async_accept_scale_weight(
            item.get("value_kg"),
            str(item.get("entity_id") or ""),
            str(item.get("measured_at") or ""),
        )
        if not applied:
            return False
        self._pending.remove(item)
        self._schedule_save()
        self._notify_listeners()
        return True

    async def async_dismiss_for_profile(
        self, measurement_id: str, profile_entry_id: str, allowed_profile_ids: set[str]
    ) -> bool:
        """Hide one measurement from one user's dashboard without deleting it for others/admin."""
        measurement_id = str(measurement_id or "")
        profile_entry_id = str(profile_entry_id or "")
        if profile_entry_id not in allowed_profile_ids:
            return False
        item = next((row for row in self._pending if row.get("id") == measurement_id), None)
        if item is None or profile_entry_id not in (item.get("profile_entry_ids") or []):
            return False
        dismissed = {str(pid) for pid in item.get("dismissed_profile_ids") or []}
        if profile_entry_id in dismissed:
            return True
        dismissed.add(profile_entry_id)
        item["dismissed_profile_ids"] = sorted(dismissed)[:32]
        self._schedule_save()
        self._notify_listeners()
        return True

    async def async_dismiss(
        self, measurement_id: str, allowed_profile_ids: set[str]
    ) -> bool:
        measurement_id = str(measurement_id or "")
        item = next((row for row in self._pending if row.get("id") == measurement_id), None)
        if item is None:
            return False
        if not allowed_profile_ids.intersection(set(item.get("profile_entry_ids") or [])):
            return False
        self._pending.remove(item)
        self._schedule_save()
        self._notify_listeners()
        return True

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)

        @callback
        def _remove() -> None:
            self._listeners.discard(listener)

        return _remove

    def _notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:  # noqa: BLE001 - dashboard subscribers are isolated
                _LOGGER.exception("Fitness shared scale listener failed")

    def _schedule_save(self) -> None:
        if not self._loaded or (self._save_task is not None and not self._save_task.done()):
            return

        async def _save() -> None:
            await asyncio.sleep(0)
            try:
                await self.store.async_save(
                    {
                        "sequence": self._sequence,
                        "pending": list(self._pending[-MAX_PENDING_MEASUREMENTS:]),
                        "last_values": {
                            entity_id: value
                            for entity_id, value in list(self._last_measurements.items())[-MAX_TRACKED_SCALES:]
                        },
                    }
                )
            except Exception:  # noqa: BLE001 - persistence must not destabilize HA
                _LOGGER.exception("Unable to persist Fitness shared scale state")

        self._save_task = self.hass.async_create_background_task(
            _save(), "fitness shared scale save", eager_start=False
        )

    async def async_shutdown(self) -> None:
        if self._state_unsub is not None:
            self._state_unsub()
            self._state_unsub = None
        for task in list(self._debounce_tasks.values()):
            task.cancel()
        self._debounce_tasks.clear()
        if self._save_task is not None and not self._save_task.done():
            try:
                async with asyncio.timeout(5.0):
                    await self._save_task
            except (TimeoutError, asyncio.CancelledError):
                self._save_task.cancel()


def get_weight_scale_router(hass: HomeAssistant) -> SharedWeightScaleRouter:
    domain_data = hass.data.setdefault(DOMAIN, {})
    router = domain_data.get(ROUTER_DATA_KEY)
    if router is None:
        router = SharedWeightScaleRouter(hass)
        domain_data[ROUTER_DATA_KEY] = router
    return router
