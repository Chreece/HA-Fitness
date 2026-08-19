# Features & data flow

## One person, several sources

Fitness organizes data around a person rather than a vendor. Source selection happens per capability, so different devices can contribute heart rate, speed, cadence, power, sleep or completed workouts.

## Live workout

The Live workout device exposes the measurements and Fitness calculations that are currently available. Fitness does not label an activity as running or cycling from weak evidence alone. Live announcements can include elapsed time, actual live sensor values and the most useful calculated context.

## Completed workouts and merging

Completed workout adapters normalize provider-specific fields into a common Fitness workout model. Representations of the same physical workout can be merged so a later watch sync does not erase useful data collected live. Field provenance is retained where relevant.

Direct archive adapters can also obtain completed workouts locally from supported hardware. The Garmin local adapter recognizes vendor/protocol evidence rather than model names, dynamically discovers the connected GFDI capabilities, tries bounded V2 -> V1 -> V0 candidates, downloads FIT activities read-only in bounded background sessions and feeds them through the same canonical workout merge. See [Local Garmin workout synchronization](GARMIN_LOCAL.md).

Direct-device health-history adapters can also import non-FIT wellness data directly from supported Bluetooth wearables, including explicit sleep stages and daily activity/HR metrics when the protocol exposes them. See [Direct device health history](DIRECT_DEVICE_HISTORY.md).

Provider placeholder values such as meaningless zero distance/power are treated as missing when they do not make sense for the activity.

## RPE

Fitness accepts whole-number session RPE from 1–10. Provider RPE is used as the initial value when a supported adapter exposes it. The user can override it from the Workout card; dependent RPE-load and comparison values are recalculated.

## Heart-rate recovery

After a live workout, Fitness can collect HR recovery measurements. Recovery feedback is separated from the workout itself and personal historical comparisons are preferred over universal labels.

## Recovery and readiness

Recovery can use merged sleep, HRV/resting-HR history, recent training and HR recovery. The Fitness Training Readiness score is calculated only when enough independent evidence exists. Its component scores, confidence, formula and scientific context remain inspectable.

## Strength analysis

Detailed strength analysis is optional. When enabled, Fitness can normalize exercises/sets, calculate volume, estimate 1RM from suitable sets and compare exercise progression. When disabled, that deeper parsing and progression model are not used.

## Shared household scales

A Fitness profile has two separate weight inputs: an editable **current weight** and an optional Home Assistant **scale entity**. The same physical scale may be selected by several profiles. Fitness watches each configured scale through one bounded state-change router rather than polling it separately for every person.

When a fresh stable scale reading arrives, Fitness compares it with the confirmed current weights of the profiles that share that scale and suggests the closest match. The measurement is **never assigned automatically**: the affected dashboard shows the reading, a user dropdown (preselected with the best match), **Confirm**, and **Ignore**. Choosing another user before Confirm moves that measurement to the selected profile. Confirmed readings become that profile's current weight and are retained in Fitness history.

## Cards

Fitness provides adaptive cards for live workouts, completed workouts, recovery/sleep and evaluation. Entity-backed values can open Home Assistant's native More Info dialog. Cards hide unavailable/unknown values and irrelevant placeholders.

## Coaching and smart-home feedback

Optional TTS and AI announcements can describe live progress, pause/resume, HR recovery and completed workouts. AI receives structured Fitness data; deterministic localized TTS remains available without AI. Compatible lights can provide temporary intensity feedback and are restored to their captured state afterward.

## Data-quality rules

Fitness calculations are based on normalized Fitness-owned data. Historical calculations validate timestamps, plausible ranges, completeness and duplicate/merge behavior before using records. A result is left unavailable when its evidence requirements are not met.


## Smart workout devices

Direct archive devices are discovered automatically and managed through **Smart workout devices**. Fitness merges verified live/archive transports into one physical device, keeps one primary profile for stored-workout imports, and never uses consumer model names for protocol routing. See [Smart workout devices](SMART_WORKOUT_DEVICES.md).
