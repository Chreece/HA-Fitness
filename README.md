# Fitness for Home Assistant

**Current release: `2026.8.0-beta.1` — public beta**

Fitness is a person-centered Home Assistant integration that combines live exercise
data, completed workouts, physiological profile data, Home Assistant long-term
statistics, and optional AI evaluation into one local fitness model.

> **Beta status:** This integration is under active development. Entity names,
> calculations, configuration details, and provider adapters may still change before
> the first stable release. Fitness metrics are intended for training and wellness
> context and are not medical diagnoses.

## Highlights

- Live workout sessions from Home Assistant fitness sensors such as ANT+, BLE, power,
  cadence, speed, distance and heart-rate sources.
- Start is armed first: the workout timer begins only when valid live exercise data
  actually arrives.
- Scientifically grounded derived metrics including HRmax/HRR intensity, Banister
  TRIMP, mechanical work, heart-rate recovery, aerobic efficiency and decoupling.
- Completed-workout normalization and merging across selected workout providers such
  as Garmin, Strava and compatible activity integrations.
- Long-term evaluation using Fitness workout history plus Home Assistant Recorder
  statistics when available.
- Optional AI-generated general/workout evaluations using Home Assistant AI Task.
- Live coaching through lights and TTS/notifications.
- Lazy entity creation: optional sensors appear only after they become calculable,
  then remain registered and become unavailable when data is temporarily missing.
- Multi-language UI translations.

## Installation

### HACS custom repository

1. Open HACS.
2. Add `https://github.com/Chreece/HA-Fitness` as a custom **Integration**
   repository.
3. Install **Fitness**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration → Fitness**.

### Manual

Copy:

```text
custom_components/fitness/
```

into:

```text
/config/custom_components/fitness/
```

restart Home Assistant, then add **Fitness** from Devices & services.

## AI evaluation

- Sensor state = short overall verdict only.
- Full assessment = `text` attribute.
- Old persisted long AI text can never become the state again.
- Prompt requests one natural paragraph rather than a sensor-by-sensor summary.
- Prompt/output follows Home Assistant's configured language; unsupported locales
  fall back to English.

## Garmin Last activities

Fitness scans all entities belonging to the selected workout device and finds
the `last_activities` attribute automatically. No Garmin entity ID is hard-coded.

It imports completed activities including name/type/start, duration, distance,
HR, power, cadence, elevation, calories, training effect/load, intensity minutes,
VO2max, and speed where available. The newest timestamp wins against Fitness'
own locally captured sessions and other external workout sources.

## Localization

Custom integration localization is shipped through `translations/*.json`.

Included: en, el, de, fr, es, it, pt, nl, pl, ru, uk, tr, zh, ja, ko.

Greek contains translated setup/options/entity/button names. The other major
languages have localized setup essentials and buttons, with accurate English
fallbacks for entity terminology not manually authored.


## Unit normalization (alpha.15)

Direct values entered in setup are interpreted in the unit printed beside the field:

- weight: kg
- height: cm
- heart rate: bpm
- power: W
- VO2max: mL/kg/min
- threshold pace: min/km

When the user enters an entity ID instead, Fitness reads that entity's
`unit_of_measurement` and converts it to the canonical internal unit before any
calculation.

Supported conversions currently include:

- mass: kg, g, mg, lb/lbs, oz, stone
- length: cm, m, mm, inch, foot
- heart rate: bpm and Hz
- power: W and kW
- VO2max: mL/kg/min and L/kg/min
- pace/speed to min/km: min/km, s/km, min/mile, s/mile, m/s, km/h, mph

Unknown/incompatible units are not silently treated as the canonical unit; the
value resolves to unavailable instead, preventing scientifically invalid calculations.


## Dynamic scientifically-derived live entities (alpha.16)

Fitness now creates derived Live entities only when their prerequisites exist.

With live heart rate:
- Heart rate % of maximum
- Heart rate reserve %
- Heart rate intensity (ACSM HRR classification)
- Heart rate relative to threshold, if threshold HR exists

With live power:
- Current power-to-weight
- Power relative to threshold, if threshold power exists

With live speed:
- Current pace
- Speed relative to threshold, if threshold pace exists

ACSM HRR intensity states:
- very_light: <30 %HRR
- light: 30–39 %HRR
- moderate: 40–59 %HRR
- vigorous: 60–89 %HRR
- near_maximal: >=90 %HRR

These population ranges are explicitly documented as approximations. Threshold-relative
metrics are exposed separately because ventilatory/metabolic thresholds are more
individualized and should not be assumed equivalent to fixed HRR percentages.

## Live unit normalization

Live source entities are normalized before calculations:
- heart rate -> bpm
- power -> W
- cadence -> events/min
- speed -> km/h
- distance -> km
- altitude -> m

The original source entity and unit remain visible in entity attributes.


## Coaching, lights, notifications and TTS (alpha.17)

Setup can optionally select:
- one or more Home Assistant areas/rooms
- explicit light entities
- notify entities
- one TTS provider entity
- one or more media-player/speaker entities

### Live intensity feedback

While a Fitness live workout session is active, changes in the ACSM HRR intensity
classification trigger audiovisual coaching.

Color mapping is a user-interface convention, not a scientific claim:
- very low: blue
- low: green
- moderate: yellow
- high: orange
- near-maximal: red

All selected lights are snapshotted using a temporary Home Assistant scene, changed
for five seconds, and restored to their exact previous state. A newer intensity
change during the five seconds keeps the original snapshot, changes color, and
restarts the timer.

The spoken message is AI-generated when Fitness AI is enabled. A localized static
motivational sentence is used if AI is disabled or unavailable.

### New workout feedback

Fitness now tracks the signature of the newest normalized workout across Garmin,
other external sources and locally captured workouts. The existing workout at
Home Assistant startup is treated as historical and is not announced.

When a genuinely newer workout appears:
1. deterministic evaluation is immediately current
2. AI general/workout evaluation is regenerated if enabled
3. a spoken workout summary is sent to configured speakers
4. a notification is sent to all selected notify entities

AI workout text is used when available; otherwise a localized static summary is used.

### Home Assistant services

- `scene.create`, `scene.turn_on`, `scene.delete` for temporary light-state snapshots
- `notify.send_message` for notify entities
- `tts.speak` for spoken output


## Robust feedback targets (alpha.18)

Feedback configuration supports explicit entities and Home Assistant areas.
The later room-selection implementation supersedes the earlier entity-only design.

Light feedback safety:
- missing light -> ignored
- unavailable light -> ignored
- light without RGB/HS/XY-style color support -> ignored
- scene snapshot failure -> no lights are modified
- one light service failure -> other lights continue normally
- only safely snapshotted, available, color-capable lights are restored

Announcements:
- missing/unavailable TTS provider -> skipped
- missing/unavailable media player -> skipped
- one media-player failure -> other speakers continue
- missing/unavailable notify entity -> skipped
- one notification failure -> other notification targets continue

All integration settings remain editable through Configure after installation:
profile, physiological inputs, live devices, workout/long-term devices, AI, and
feedback/announcement entities.


## Room + explicit light selection (alpha.19)

Feedback lighting can be configured in two complementary ways:

1. Select one or more Home Assistant rooms/areas.
2. Select individual `light.*` entities.

For every selected room, Fitness discovers:
- light entities assigned directly to that area
- light entities whose owning device is assigned to that area

The resolved set is merged with explicitly selected lights and deduplicated.

Fitness then applies the same safety filtering:
- missing -> ignored
- unavailable -> ignored
- no color support -> ignored
- only RGB/HS/XY/RGBW/RGBWW-capable lights are controlled
- snapshot must succeed before any light is changed
- each service failure is isolated

The room selection itself is also editable after installation under Configure ->
Coaching, lights and announcements.


## Home Assistant ColorMode enum fix (alpha.20)

Home Assistant may expose `supported_color_modes` as `ColorMode` enum objects
instead of plain strings. Fitness now normalizes both forms.

For example:

`[<ColorMode.COLOR_TEMP: 'color_temp'>, <ColorMode.RGB: 'rgb'>]`

is normalized internally to:

`{'color_temp', 'rgb'}`

so RGB-capable lights are correctly detected.

Unavailable and on/off-only lights remain ignored.


## Immediate session coaching + diagnostics (alpha.21)

Live audiovisual coaching remains active only while `Session status` is `active`.

When Start workout is pressed:
1. ANT+ capture is started.
2. Fitness collects an initial sample.
3. If a valid current HR/intensity already exists, light/TTS feedback is triggered
   immediately.
4. If HR is not available yet, the first valid later live-state update triggers the
   initial feedback.
5. Further coaching only occurs when the scientific intensity category changes.

After Stop workout, live coaching stops.

The `Heart rate intensity` entity now exposes diagnostics including:
- feedback_enabled
- session_active
- configured_feedback_areas
- configured_feedback_lights
- resolved_feedback_lights
- tts_entity
- tts_available
- tts_media_players
- usable_tts_media_players
- last_feedback_intensity
- last_feedback_time
- last_light_feedback
- last_tts_feedback
- last_feedback_message

These diagnostics are intended to make room/light/TTS problems visible directly
from the Home Assistant entity UI.


## Startup capability + workout announcement fixes (alpha.22)

### Derived Live entities no longer disappear at startup

Entity existence is now based on configured capability rather than a transient
numeric state during Home Assistant startup.

Example:
- live HR source configured/discovered
- resting-HR entity configured
- resting-HR entity temporarily unavailable during HA startup

Fitness still creates:
- Heart rate reserve %
- Heart rate intensity

Their values remain unavailable until resting HR becomes usable, then update
normally without requiring an integration reload.

### Workout announcements survive restarts correctly

The last announced workout fingerprint is persisted in Fitness storage.

Workout fingerprints are now source-independent. They use normalized sport plus
a five-minute start-time bucket, so the same physical session does not become a
different "new" workout merely because Home Assistant switches from a locally
captured Fitness record to Garmin/Strava's copy after sync.

On first installation, if workout providers populate after Fitness loads, the
first observed external workout becomes the historical baseline and is not
announced.

Local workouts finalized by Stop workout are still announced immediately once,
then the persisted fingerprint prevents replay after restart.


## In-memory light state restoration (alpha.23)

Live intensity light feedback no longer depends on `scene.create`.

Before changing any usable color light, Fitness records its current state in
memory:
- on/off
- brightness
- active color mode
- RGB / HS / XY color where available
- color temperature in Kelvin
- active effect

After the five-second intensity color flash, Fitness restores every light
individually. An off light is turned off again; an on light is restored using
its previous active color representation and brightness.

This preserves the existing behavior for repeated intensity changes: the first
snapshot remains the original pre-feedback state until the final five-second
timer expires.

New diagnostics on Heart rate intensity:
- light_snapshot_active
- snapshotted_feedback_lights
- last_light_feedback

Expected successful lifecycle:
`snapshot_created` -> feedback color -> `success_restored`


## BPM in intensity coaching + periodic live announcements (alpha.24)

### Intensity-change coaching

Every live intensity-change announcement now includes the current heart rate when
available.

AI mode:
- current BPM is passed explicitly to the AI prompt
- the model is instructed to include it naturally in the short coaching sentence

Static fallback:
- the localized fallback sentence appends the current BPM in the Home Assistant
  language

### Periodic live workout announcements

A new optional setup/reconfigure setting is available under Coaching, lights and
announcements:

- Periodic live workout announcements: on/off
- Live announcement interval: 1–120 minutes, default 5

When enabled, a task starts with Start workout and stops immediately with Stop
workout. The first periodic announcement happens after the configured interval,
not immediately, because the normal intensity-change coaching handles the start of
the session.

Periodic summaries use whichever live measurements are currently available:
- heart rate
- HRR intensity
- power
- cadence
- pace derived from normalized speed

AI mode produces one concise natural spoken update and intentionally mentions only
the most useful live metrics. Static mode uses a localized deterministic summary.

Periodic-announcement diagnostics are also exposed on Heart rate intensity:
- periodic_live_announcements
- periodic_live_interval_minutes
- last_periodic_live_announcement_time
- last_periodic_live_message


## Smarter periodic live coaching (alpha.25)

Periodic coaching now receives both raw live measurements and individualized
relative context:

- current BPM
- %HRmax
- %HRR
- ACSM HRR intensity
- HR relative to threshold HR
- current power
- current W/kg
- power relative to threshold power
- cadence
- speed
- pace
- speed relative to threshold pace
- elapsed workout duration
- recent descriptive trends for HR, power, cadence and speed

Trend windows use roughly the last 90 seconds of captured samples and are explicitly
descriptive rather than diagnostic.

AI is instructed to prioritize relative intensity and trends, mention current BPM,
use no more than three numerical values, and finish with one actionable coaching cue.

The full context is exposed while a session is active in the Heart rate intensity
attribute `live_coaching_context`.


## Runtime Workout room select (alpha.26)

The Fitness Live device now exposes a `select` entity named `Workout room`.

Its options are populated dynamically from the Home Assistant area registry. The
selected value is persisted by area ID, so renaming an area does not lose the
selection.

Changing Workout room immediately changes physical coaching targets.

### Lights

When a room is selected:
- all available color-capable `light.*` entities in that room are used
- room membership checks entity `area_id` first, then the owning device `area_id`
- explicitly configured lights with no area remain global and continue to be used
- explicitly configured lights assigned to another area are suppressed
- unavailable/unknown/non-color lights remain ignored

### Spoken announcements

When a room is selected:
- available `media_player.*` entities in that room become announcement targets
- explicitly configured media players with no area remain global
- configured media players assigned to a different area are suppressed
- the configured `tts.*` provider itself remains unchanged

`notify.*` entities remain global and are not room-filtered.

This makes it possible to move a workout between rooms from a dashboard or
automation without reconfiguring the integration.


## Workout-room target semantics + media_play filtering (alpha.27)

Workout room now has explicit override semantics.

### Lights

If a Workout room is selected:
- all available color-capable lights in that room are used
- explicitly configured lights with no Home Assistant area remain global
- explicitly configured lights that belong to another area do not follow the
  workout; the newly selected room's lights replace them

Example:

Configured:
- `light.guest_room` -> area `guest_room`
- `light.portable_strip` -> no area

Workout room changes from Guest room to Living room:

Used:
- color lights in Living room
- `light.portable_strip`

Not used:
- `light.guest_room`

### Announcements

The same routing applies to `media_player.*`:
- room-bound players come from the selected Workout room
- explicitly configured area-less players remain global
- configured players in another room are replaced by players from the newly
  selected room

Additionally, Fitness now requires announcement media players to advertise
`MediaPlayerEntityFeature.PLAY`, the Home Assistant feature for the
`media_player.media_play` action. Missing, unknown, unavailable, or players
without PLAY support are ignored.

The TTS provider remains the configured `tts.*` entity and `notify.*` remains
global.


## Explicit Workout-room default behavior (alpha.28)

Workout room initialization is now deterministic:

1. A valid previously selected runtime Workout room is restored.
2. Otherwise, if setup/reconfigure contains one or more feedback areas, the first
   valid configured area becomes the initial Workout room.
3. Otherwise Workout room is `No room`.

Fitness never guesses or auto-selects an arbitrary Home Assistant area.

When Workout room is `No room`:
- explicitly configured area-less lights remain global and can still be used
- explicitly configured area-less media players remain global and can still be used
- configured area-bound entities follow the legacy configured-target behavior
- selecting a room later immediately switches room-bound light/speaker routing

The Workout room select also includes an explicit `No room` option so the runtime
room can be cleared intentionally.


## MediaPlayerEntityFeature import fix (alpha.29)

alpha.28 referenced `MediaPlayerEntityFeature.PLAY` in room-aware announcement
speaker filtering without importing `MediaPlayerEntityFeature` in the packaged
manager.py.

alpha.29 explicitly imports it from Home Assistant's media_player component.


## Provider-independent merged workout model (alpha.30)

Fitness no longer chooses a whole Garmin/Strava/provider record and discards the
others.

All completed-workout candidates from selected workout devices are normalized,
clustered by physical session (start time within five minutes + compatible sport),
and merged.

Supported discovery patterns include:
- activity/workout attributes directly on a sensor
- nested activity/workout dictionaries
- lists such as `last_activities`, `activities`, `workouts`, `sessions`
- sibling sensors such as Hevy's last-workout title/start/duration/volume layout

This covers Garmin Connect, Strava, Hevy and generic activity contracts used by
Polar/Oura/Peloton-style integrations, while also making future workout integrations
work without adding a hard-coded provider name when they expose recognizable fields.

The canonical value for a field comes from the richest matching provider record.
Provider disagreements are never discarded: the complete raw provider data and
normalized mismatches are retained in the Workout entities' attributes through:

- `sources`
- `provider_domains`
- `field_sources`
- `provider_values`
- `extra`

The Workout device now exposes additional common metrics including calories,
moving/elapsed time, speed, weighted power, max cadence, elevation loss, training
load/effect, workout VO2max, Strava-style relative effort, energy, strength-training
reps/exercise count/volume, device, gear and data sources.


## Scientific session + longitudinal evaluation upgrade (alpha.31)

Start Workout now arms capture first. Session timing begins only after the first
subsequent valid live HR/power/cadence/speed/distance update.

Outside an active Fitness workout, all live measurements and live session
statistics are unavailable. Session status remains available and can be:
`idle`, `waiting_for_live_data`, `active`, or `recovery`.

Live/local workout calculations now include classic Banister TRIMP, mechanical
work, HRR-intensity duration, aerobic efficiency/decoupling, and post-exercise
heart-rate recovery at 10/30/60/120 seconds.

After Stop Workout, the workout timer ends immediately and live entities become
unavailable. ANT capture may remain active for up to 120 seconds solely to
measure post-exercise HR recovery, then stops automatically.

Fitness also requests up to 90 days of Home Assistant Recorder long-term
statistics for relevant configured/provider entities. Cached 7/28/90-day means
and recent trends are included in deterministic/AI evaluation context. Numeric
Fitness sensors use measurement state class where appropriate so HA can build
long-term statistics too.


## Lazy permanent Fitness entities (alpha.32)

Optional sensors now use a create-on-first-valid-result lifecycle:

1. Fitness has never calculated a valid value -> entity does not exist.
2. First valid calculation -> entity is created.
3. Its description key is persisted in Fitness storage.
4. A later workout/source cannot calculate it -> entity remains registered and
   becomes unavailable.
5. Data becomes valid again -> the same entity resumes updating.

Entities are never deleted after first materialization. This protects entity IDs,
dashboards, automations, Recorder history, long-term statistics and user
customizations.

The calculation engine, workout engine, AI evaluation and coaching never depend
on the HA sensor entity existing. Missing/not-yet-created entities are only a UI
representation decision.

`Session status` is the one deliberate exception because it always has a useful
control state (`idle`, `waiting_for_live_data`, `active`, `recovery`).

During upgrades Fitness also inspects the HA entity registry and treats entities
already created by older versions as materialized. Thus alpha.31 entities are not
removed merely by installing alpha.32.

HRR-intensity duration sensors no longer materialize as artificial zeroes when
there was no usable HR + resting/max HR basis. Long-term training sensors also
stay absent before any qualifying Fitness workout history exists.

alpha.32 additionally fixes the missing `SensorStateClass` import in alpha.31.


## Stable intensity transitions + heartbeat light pulses (alpha.33)

### Five-second transition guard

After an intensity class is accepted, another intensity class cannot trigger
light/TTS feedback until the accepted intensity is at least five seconds old.

The first valid intensity after workout start is accepted immediately. If a new
class appears inside the five-second guard it is not committed; if it remains
current, the next live sensor update after the guard expires will accept it.

This avoids rapid light/TTS transitions caused by heart-rate values oscillating
around an intensity boundary.

### Five heartbeat-style light pulses

Intensity feedback no longer holds a colour for five seconds.

For each accepted intensity change, Fitness:
1. snapshots the original state of every usable feedback light;
2. sets the intensity colour;
3. restores the original state;
4. repeats this five times;
5. leaves the lights in their original state.

The full pulse period is based on current heart rate:

`pulse_interval = max(60 / BPM, 1.0 seconds)`

Examples:
- 50 bpm -> one pulse every 1.2 seconds
- 60 bpm -> one pulse every 1.0 second
- 120 bpm -> capped at one pulse every 1.0 second
- missing/invalid BPM -> one pulse every 1.0 second

Each cycle uses an approximately 50% colour / 50% original-state duty cycle.
The intensity TTS/AI coaching message is still spoken once per accepted
transition, not once per pulse.

Diagnostics on Heart rate intensity now include:
- `intensity_transition_min_age_seconds`
- `last_feedback_bpm`
- `last_feedback_pulse_interval_seconds`
- `last_feedback_pulse_count`


## ANT+ Capture snapshot/restore (2026.8.0-beta.1)

Fitness now discovers every Capture-like switch belonging to `antplus` /
`ant_plus`, including switches on USB-adapter hub devices that are separate from
the selected HR/power/cadence sensor devices.

On Start Workout:
- snapshot every available Capture switch state
- already ON -> leave ON
- OFF -> turn ON
- unavailable/unknown -> ignore safely

During the live workout all available ANT+ Capture switches are therefore ON.

On Stop Workout, or after the post-workout HRR collection finishes:
- originally ON -> restore ON
- originally OFF -> restore OFF

The snapshot is persisted across HA restarts. If HA restarts while Fitness owns
capture, it makes a delayed restoration attempt. Failed/unavailable restores
remain in the snapshot so they are not silently forgotten.

Diagnostics:
- `antplus_capture_switches`
- `antplus_capture_snapshot`
- `antplus_capture_changed_by_fitness`


## Versioning

Fitness follows `YYYY.MM.release` versioning.

Examples:

- `2026.8.0-beta.1` — beta 1 of the August 2026 release line
- `2026.8.0-beta.2` — beta 2
- `2026.8.0` — stable release
- `2026.8.1` — next patch/release in the same month

Git tags should match the manifest version exactly, for example:

```text
2026.8.0-beta.1
```
