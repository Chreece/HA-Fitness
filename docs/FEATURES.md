# Features & data flow

## One person, several sources

Fitness organizes data around a person rather than a vendor. Source selection happens per capability, so different devices can contribute heart rate, speed, cadence, power, sleep or completed workouts.

## Live workout

The Live workout device exposes the measurements and Fitness calculations that are currently available. Fitness does not label an activity as running or cycling from weak evidence alone. Live announcements can include elapsed time, actual live sensor values and the most useful calculated context.

## Completed workouts and merging

Completed workout adapters normalize provider-specific fields into a common Fitness workout model. Representations of the same physical workout can be merged so a later watch sync does not erase useful data collected live. Field provenance is retained where relevant.

Direct archive adapters can also obtain completed workouts locally from supported hardware. The Garmin local adapter selects GFDI transport from device capabilities, downloads FIT activities read-only in bounded background sessions and feeds them through the same canonical workout merge. See [Local Garmin workout synchronization](GARMIN_LOCAL.md).

Provider placeholder values such as meaningless zero distance/power are treated as missing when they do not make sense for the activity.

## RPE

Fitness accepts whole-number session RPE from 1–10. Provider RPE is used as the initial value when a supported adapter exposes it. The user can override it from the Workout card; dependent RPE-load and comparison values are recalculated.

## Heart-rate recovery

After a live workout, Fitness can collect HR recovery measurements. Recovery feedback is separated from the workout itself and personal historical comparisons are preferred over universal labels.

## Recovery and readiness

Recovery can use merged sleep, HRV/resting-HR history, recent training and HR recovery. The Fitness Training Readiness score is calculated only when enough independent evidence exists. Its component scores, confidence, formula and scientific context remain inspectable.

## Strength analysis

Detailed strength analysis is optional. When enabled, Fitness can normalize exercises/sets, calculate volume, estimate 1RM from suitable sets and compare exercise progression. When disabled, that deeper parsing and progression model are not used.

## Cards

Fitness provides adaptive cards for live workouts, completed workouts, recovery/sleep and evaluation. Entity-backed values can open Home Assistant's native More Info dialog. Cards hide unavailable/unknown values and irrelevant placeholders.

## Coaching and smart-home feedback

Optional TTS and AI announcements can describe live progress, pause/resume, HR recovery and completed workouts. AI receives structured Fitness data; deterministic localized TTS remains available without AI. Compatible lights can provide temporary intensity feedback and are restored to their captured state afterward.

## Data-quality rules

Fitness calculations are based on normalized Fitness-owned data. Historical calculations validate timestamps, plausible ranges, completeness and duplicate/merge behavior before using records. A result is left unavailable when its evidence requirements are not met.
