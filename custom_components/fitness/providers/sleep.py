"""Provider-independent sleep normalization, clustering and merging."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class SleepRecord:
    source: str
    provider_domain: str
    start: str | None = None
    end: str | None = None
    observed_at: str | None = None
    duration_s: float | None = None
    time_in_bed_s: float | None = None
    awake_s: float | None = None
    light_sleep_s: float | None = None
    deep_sleep_s: float | None = None
    rem_sleep_s: float | None = None
    sleep_latency_s: float | None = None
    score: float | None = None
    efficiency_percent: float | None = None
    average_hr: float | None = None
    minimum_hr: float | None = None
    hrv_ms: float | None = None
    respiratory_rate: float | None = None
    spo2_percent: float | None = None
    readiness_score: float | None = None
    recovery_score: float | None = None
    sleep_need_s: float | None = None
    sleep_debt_s: float | None = None
    disturbance_count: float | None = None
    sleep_cycle_count: float | None = None
    in_bed: bool | None = None
    sources: list[str] = field(default_factory=list)
    provider_domains: list[str] = field(default_factory=list)
    field_sources: dict[str, str] = field(default_factory=dict)
    provider_values: dict[str, dict[str, Any]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        number = float(text)
        if number > 10_000_000_000:
            number /= 1000
        if 946_684_800 <= number <= 4_102_444_800:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        return None
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result


def _record_interval(record: SleepRecord) -> tuple[datetime, datetime] | None:
    start = _dt(record.start)
    end = _dt(record.end)
    if start and end and end > start:
        return start, end
    if start and record.duration_s and record.duration_s > 0:
        from datetime import timedelta
        return start, start + timedelta(seconds=float(record.duration_s))
    if end and record.duration_s and record.duration_s > 0:
        from datetime import timedelta
        return end - timedelta(seconds=float(record.duration_s)), end
    return None


def _same_sleep(a: SleepRecord, b: SleepRecord) -> bool:
    """Return whether two provider records describe the same physical sleep."""
    ai = _record_interval(a)
    bi = _record_interval(b)

    if ai and bi:
        a_start, a_end = ai
        b_start, b_end = bi
        overlap = max(0.0, (min(a_end, b_end) - max(a_start, b_start)).total_seconds())
        shorter = min((a_end - a_start).total_seconds(), (b_end - b_start).total_seconds())
        if shorter > 0 and overlap / shorter >= 0.60:
            return True
        midpoint_a = a_start + (a_end - a_start) / 2
        midpoint_b = b_start + (b_end - b_start) / 2
        if abs((midpoint_a - midpoint_b).total_seconds()) <= 45 * 60:
            duration_diff = abs((a_end - a_start).total_seconds() - (b_end - b_start).total_seconds())
            if duration_diff <= max(60 * 60, shorter * 0.20):
                return True
        return False

    # Sparse provider records may have only one timestamp. Keep the fallback
    # deliberately tight so a daytime nap cannot merge into the main night.
    at = _dt(a.end or a.start)
    bt = _dt(b.end or b.start)
    if at and bt:
        return abs((at - bt).total_seconds()) <= 30 * 60

    # Some integrations publish a nightly aggregate with no explicit sleep
    # timestamps. Its HA update timestamp can safely merge it into an interval
    # from another provider when it arrived around the same morning.
    ao = _dt(a.observed_at)
    bo = _dt(b.observed_at)
    if ao and bo and abs((ao - bo).total_seconds()) <= 6 * 3600:
        return True
    interval, observed = (ai, bo) if ai and bo else ((bi, ao) if bi and ao else (None, None))
    if interval and observed:
        _start, end = interval
        # Sleep as Android sensor aggregates (for example sleep_score) can keep
        # yesterday's value until the integration publishes the new result. Do
        # not attach such a stale sparse record to tonight's freshly completed
        # event timeline merely because it is within the broad daily window.
        sparse = b if ai and bo else a
        tolerance = 2 * 3600 if sparse.provider_domain == "sleep_as_android" else 12 * 3600
        return abs((observed - end).total_seconds()) <= tolerance
    return False


def _richness(record: SleepRecord) -> int:
    excluded = {"source", "provider_domain", "sources", "provider_domains", "field_sources", "provider_values"}
    return sum(
        getattr(record, item.name) is not None
        for item in fields(SleepRecord)
        if item.name not in excluded
    )


def _candidate_rank(record: SleepRecord, field_name: str) -> tuple[int, int, int, str]:
    """Deterministic field quality without pretending provider scores are equal."""
    explicit_timing = int(bool(record.start and record.end))
    stage_detail = sum(
        getattr(record, name) is not None
        for name in ("light_sleep_s", "deep_sleep_s", "rem_sleep_s", "awake_s")
    )
    # Scores/readiness/recovery are provider-defined. Prefer the primary/richest
    # record deterministically but retain every provider value below.
    if field_name in {"score", "readiness_score", "recovery_score"}:
        return (explicit_timing, _richness(record), stage_detail, record.provider_domain)
    return (explicit_timing, stage_detail, _richness(record), record.provider_domain)



def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def fitness_derived_sleep_score(record: SleepRecord) -> float | None:
    """Return a conservative Fitness-derived sleep score when providers omit one.

    This is a transparent wellness heuristic, not a clinical sleep-quality
    assessment. It requires actual sleep duration plus Light/Deep/REM stages.
    Provider-native scores always take precedence.
    """
    if record.score is not None or record.duration_s is None:
        return None
    stages = (record.light_sleep_s, record.deep_sleep_s, record.rem_sleep_s)
    if any(value is None for value in stages):
        return None
    classified = sum(float(value or 0.0) for value in stages)
    if classified <= 0:
        return None

    hours = float(record.duration_s) / 3600.0
    # Broad 8-hour-centered duration component. This intentionally does not
    # claim individual medical sleep requirements.
    duration_score = _clamp_score(100.0 - abs(hours - 8.0) * 20.0)

    deep_pct = float(record.deep_sleep_s or 0.0) / classified * 100.0
    rem_pct = float(record.rem_sleep_s or 0.0) / classified * 100.0
    deep_score = _clamp_score(100.0 - abs(deep_pct - 20.0) * 4.0)
    rem_score = _clamp_score(100.0 - abs(rem_pct - 25.0) * 4.0)
    stage_score = (deep_score + rem_score) / 2.0

    bed_seconds = record.time_in_bed_s
    if bed_seconds is None and record.awake_s is not None:
        bed_seconds = float(record.duration_s) + float(record.awake_s)
    if bed_seconds is not None and float(bed_seconds) > 0:
        efficiency = float(record.duration_s) / float(bed_seconds) * 100.0
        efficiency_score = _clamp_score((efficiency - 65.0) / 25.0 * 100.0)
        score = 0.55 * duration_score + 0.25 * efficiency_score + 0.20 * stage_score
    else:
        score = 0.70 * duration_score + 0.30 * stage_score
    return round(_clamp_score(score), 1)

def merge_sleep_records(group: list[SleepRecord]) -> SleepRecord:
    """Merge representations of one sleep period, retaining full provenance."""
    if not group:
        raise ValueError("sleep merge group cannot be empty")

    ordered = sorted(group, key=lambda record: (_richness(record), record.provider_domain), reverse=True)
    primary = ordered[0]
    merged = SleepRecord(source=primary.source, provider_domain=primary.provider_domain)

    scalar_fields = [
        item.name for item in fields(SleepRecord)
        if item.name not in {
            "source", "provider_domain", "sources", "provider_domains",
            "field_sources", "provider_values",
        }
    ]

    for record in ordered:
        for source in record.sources or [record.source]:
            if source and source not in merged.sources:
                merged.sources.append(source)
        for domain in record.provider_domains or [record.provider_domain]:
            if domain and domain not in merged.provider_domains:
                merged.provider_domains.append(domain)
        for domain, values in record.provider_values.items():
            merged.provider_values.setdefault(domain, {}).update(values)

    # Keep the core sleep-duration/stage bundle coherent. When multiple
    # providers describe the same physical night, do not combine a duration
    # from provider A with Light/Deep/REM from provider B. Prefer the strongest
    # record that contains a usable sleep duration plus at least the three
    # physiological sleep stages, then use that record consistently for the
    # bundle. Other provider values remain preserved in provider_values.
    stage_bundle_fields = {
        "duration_s", "light_sleep_s", "deep_sleep_s", "rem_sleep_s", "awake_s"
    }
    stage_bundle_candidates = [
        record for record in group
        if record.duration_s is not None
        and all(
            getattr(record, field_name) is not None
            for field_name in ("light_sleep_s", "deep_sleep_s", "rem_sleep_s")
        )
    ]
    stage_bundle_winner = (
        max(
            stage_bundle_candidates,
            key=lambda record: _candidate_rank(record, "duration_s"),
        )
        if stage_bundle_candidates
        else None
    )

    # A provider's total sleep time cannot be shorter than the sum of all
    # classified asleep stages. Some integrations expose a stale/partial
    # "duration" alongside a newer stage breakdown. Preserve a longer duration
    # (it may include unclassified sleep), but raise an impossible shorter
    # duration to Light + Deep + REM.
    coherent_duration_s: float | None = None
    if stage_bundle_winner is not None:
        classified_sleep_s = sum(
            float(getattr(stage_bundle_winner, field_name) or 0.0)
            for field_name in ("light_sleep_s", "deep_sleep_s", "rem_sleep_s")
        )
        provider_duration_s = float(stage_bundle_winner.duration_s or 0.0)
        coherent_duration_s = max(provider_duration_s, classified_sleep_s)

    for field_name in scalar_fields:
        candidates = [record for record in group if getattr(record, field_name) is not None]
        if not candidates:
            continue
        winner = (
            stage_bundle_winner
            if stage_bundle_winner is not None
            and field_name in stage_bundle_fields
            and getattr(stage_bundle_winner, field_name) is not None
            else max(candidates, key=lambda record: _candidate_rank(record, field_name))
        )
        value = getattr(winner, field_name)
        if (
            field_name == "duration_s"
            and stage_bundle_winner is not None
            and winner is stage_bundle_winner
            and coherent_duration_s is not None
        ):
            value = coherent_duration_s
        setattr(merged, field_name, value)
        merged.field_sources[field_name] = (
            (
                f"{winner.provider_domain}:classified_sleep_stages"
                if field_name == "duration_s"
                and coherent_duration_s is not None
                and coherent_duration_s != getattr(winner, field_name)
                else (winner.field_sources or {}).get(field_name)
            )
            or winner.provider_domain
        )

        for record in candidates:
            candidate_value = getattr(record, field_name)
            merged.provider_values.setdefault(record.provider_domain, {})[
                f"normalized_{field_name}"
            ] = candidate_value

    if merged.score is None:
        calculated_score = fitness_derived_sleep_score(merged)
        if calculated_score is not None:
            merged.score = calculated_score
            merged.field_sources["score"] = "fitness_calculated"
            merged.provider_values.setdefault("fitness", {})["derived_sleep_score"] = calculated_score
            merged.provider_values["fitness"]["derived_sleep_score_method"] = (
                "duration_55_efficiency_25_stages_20"
                if (merged.time_in_bed_s is not None or merged.awake_s is not None)
                else "duration_70_stages_30"
            )

    if len(merged.provider_domains) > 1:
        merged.provider_domain = "merged"
        merged.source = "merged:" + ",".join(merged.provider_domains)
    elif merged.provider_domains:
        merged.provider_domain = merged.provider_domains[0]
        if merged.sources:
            merged.source = merged.sources[0]

    return merged


def merged_sleeps(records: list[SleepRecord]) -> list[SleepRecord]:
    """Complete-link cluster provider records into physical sleep periods."""
    groups: list[list[SleepRecord]] = []
    for record in sorted(records, key=lambda item: _dt(item.end or item.start) or datetime.min.replace(tzinfo=timezone.utc)):
        placed = False
        for group in groups:
            if all(_same_sleep(record, existing) for existing in group):
                group.append(record)
                placed = True
                break
        if not placed:
            groups.append([record])
    return [merge_sleep_records(group) for group in groups]


def newest_sleep(records: list[SleepRecord]) -> SleepRecord | None:
    merged = merged_sleeps(records)
    return max(
        merged,
        key=lambda item: _dt(item.end or item.start) or datetime.min.replace(tzinfo=timezone.utc),
    ) if merged else None
