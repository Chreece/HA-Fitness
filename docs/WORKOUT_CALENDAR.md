# Workout calendar and historical workout reconciliation

The unreleased Fitness development build adds a Home Assistant calendar for each Fitness profile. The calendar is a view of the same canonical workout history used by Fitness calculations; it is not a separate workout database.

## One physical workout, one event

Every completed-workout candidate enters the same normalization and reconciliation pipeline:

```text
Fitness live/local completion ─┐
Garmin / Strava / Polar ... ───┼─> normalize -> reconcile -> canonical history -> calendar
Provider history APIs ─────────┤
HA Recorder history fallback ──┘
```

Fitness compares start time, compatible sport, duration, distance and end time conservatively. Multiple providers can therefore describe one physical session without producing multiple calendar events. If a later provider synchronization contains additional fields, Fitness re-runs reconciliation and enriches the existing canonical workout.

## Historical imports

Historical data is collected only from workout sources selected for the Fitness profile.

Fitness uses, in order:

1. completed workouts currently exposed by supported adapters;
2. provider-specific Home Assistant history APIs/actions where the adapter has an explicit safe contract;
3. Home Assistant Recorder history for selected completed-workout entities as a fallback.

Recorder is not scanned for every heart-rate, power, cadence or general fitness sensor. This keeps historical reconstruction bounded and prevents high-frequency live sensors from becoming a historical import workload.

## Persistence and retention

Calendar events are generated from Fitness canonical workout storage. Retention is configured per Fitness profile in **Settings → Devices & services → Fitness → Configure → Workout history**.

The default is **3650 days (10 years)**. This is long enough for meaningful longitudinal analysis while avoiding an unbounded JSON-backed store as the default on Home Assistant installations that run for many years. Set the value to **0** to retain canonical workouts indefinitely.

Automatic retention removes only Fitness's canonical stored copy. It does not create deletion tombstones. If the retention period is later increased and an upstream provider still exposes an older workout, Fitness may import it again. Provider duplicates do not consume separate calendar entries after reconciliation.

## Deleting workouts

The Fitness workout calendar supports Home Assistant's normal calendar delete operation.

Deleting an event:

- removes the matching canonical Fitness workout;
- saves the updated Fitness store immediately;
- records a compact deleted-workout tombstone;
- refreshes subscribed calendar views;
- prevents Garmin, Strava, Recorder or another historical source from automatically re-importing the same physical workout later.

Up to 1,000 individual deletion tombstones are retained. A deleted workout can therefore stay deleted even when the original provider continues exposing it.

For bulk cleanup, call `fitness.delete_workouts_before` with the Fitness config entry and an age in days. Fitness removes every canonical workout older than that age and stores **one persistent cutoff timestamp** rather than thousands of tombstones. Provider and Recorder reconciliation will not recreate workouts older than that explicit user-deletion cutoff.

Deleting a Fitness calendar event or using the bulk-delete action does **not** delete the workout from Garmin, Strava, Hevy or another upstream service. Fitness only controls its own canonical history.

## GPS start location

When a completed-workout record contains an explicit workout **start** latitude and longitude, Fitness normalizes the coordinates into `start_latitude` and `start_longitude` and writes the calendar event `location` as:

```text
50.123456, 6.123456
```

Only explicit start-coordinate fields are accepted. Generic route/polyline or ambiguous current-position values are not treated as a workout start location.

No reverse-geocoding network request is performed. This keeps the integration local and avoids turning calendar rendering into external I/O.

## Calendar description and structured metrics

Home Assistant's `CalendarEvent` schema exposes standard event fields (`start`, `end`, `summary`, `description`, `location`, UID/recurrence metadata). It does not provide arbitrary per-event attributes that the standard Calendar UI can render as translated workout fields.

For that reason the unreleased Fitness development build uses a compact calendar description containing only useful headline values when present, for example duration, distance, average heart rate, average power and calories.

The complete structured data remains in the canonical Fitness workout model, including provider measurements, Fitness-derived calculations, strength analysis, personal-baseline comparisons and provenance. This avoids duplicating a large metric dump inside every calendar event and keeps the canonical model available to Fitness dashboards and future workout-detail UI.

## Localization

Calendar text follows the configured Fitness profile language. During setup Fitness already preselects this from the Home Assistant UI language when supported.

The calendar catalog covers the same 15 language families currently supported by Fitness:

`de`, `el`, `en`, `es`, `fr`, `it`, `ja`, `ko`, `nl`, `pl`, `pt`, `ru`, `tr`, `uk`, `zh`.

Provider-supplied workout names are preserved verbatim. Generated fallback sport names and compact summary labels are localized.

A Home Assistant calendar event request does not contain the requesting user's frontend language, so one shared calendar entity cannot return different event text to two users viewing it simultaneously in different UI languages. The configured Fitness profile language is therefore the stable backend language for its events.

## Calendar identity

Calendar UIDs are source-independent and based on the canonical workout start-time identity bucket. Provider enrichment does not change the UID merely because another provider becomes the richest data source. This is important for deletion and frontend updates.

## What deletion does not do

Deletion is intentionally one-way from Fitness:

- it does not remove the original provider activity;
- it does not modify Home Assistant Recorder rows;
- it does not delete raw sensor history;
- it does not instruct another integration to delete anything.

This keeps Fitness from unexpectedly mutating external fitness services.
