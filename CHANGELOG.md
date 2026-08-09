# Changelog

## 2026.8.0-beta.13

### Per-profile language

- Added a language selector to initial Fitness profile setup.
- The selector contains exactly the 15 languages already localized by Fitness.
- New profiles preselect the current Home Assistant UI language when supported,
  otherwise English.
- Language can be changed later from the Profile options page.
- All static coaching/session/recovery text and AI output instructions now use
  the profile language.
- Existing profiles without the setting continue to follow HA UI language for
  backward compatibility.
- Added translated field labels and language regression tests.

## 2026.8.0-beta.12

### Visual workout lifecycle feedback

- Start Workout now gives green/temporary or persistent-red light feedback based
  on whether usable live sensor data is already available.
- Waiting-for-live red persists until the first valid live data arrives; the
  subsequent green cue restores the exact pre-wait light state.
- Added three-second recovery-stage cues: red at stop, orange at 10 s, yellow at
  30 s, blue at 60 s and green at 120 s.
- Lifecycle cues use the existing room/configured color-capable light resolver.
- Lifecycle cues suspend intensity pulses to protect the original-state snapshot,
  then intensity feedback resumes after the start-green cue.
- Light cues are asynchronous and cannot delay HR-recovery measurement timing.
- Added lifecycle-light regression tests.

## 2026.8.0-beta.11

### Spoken workout lifecycle and HR-recovery guidance

- Added AI/static localized announcements when Start Workout is pressed.
- Distinguishes immediately available live data from waiting-for-sensor state.
- Announces the actual live sensor names when timing begins.
- Added spoken post-exercise HR-recovery guidance at 10/30/60/120 seconds with
  remaining time.
- Missing HR at a recovery checkpoint is reported truthfully rather than marked
  collected.
- Recovery speech/AI is asynchronous and cannot delay measurement checkpoints.
- Final workout evaluation/summary is deferred until HR recovery finishes so it
  can include the collected recovery values.
- Added localized deterministic guidance for all currently shipped UI languages.
- Added lifecycle/recovery regression tests.

## 2026.8.0-beta.10

### Resilient workout-provider fallback

- Known providers now use explicit adapter → scoped generic fallback → safe ignore.
- Generic fallback runs only for the affected provider/device.
- Working explicit adapters are never parsed twice.
- Adapter exceptions are isolated and exposed in diagnostics.
- Unknown/future integrations continue through the generic adapter.
- Added adapter status/count/error diagnostics and regression tests.
- Retains beta.9 startup/replay protection and beta.8 Dependabot automation.

## 2026.8.0-beta.9

### Workout announcement reliability

- Startup-restored provider workouts are silent historical baseline.
- Added a provider restoration window before external announcements are armed.
- Added debounce for multi-entity provider workout updates.
- AI/TTS/notifications require substantive completed-workout information.
- The AI workout prompt independently rejects incomplete workout data.
- Added regression tests for restart and incomplete-provider behavior.
- Includes beta.8 Dependabot auto-merge workflow.

## 2026.8.0-beta.8

### Safe Dependabot auto-merge

- Added a Dependabot-only auto-merge workflow.
- Dependabot PRs use squash auto-merge and never administrator bypass.
- Normal contributor PRs are excluded by an explicit author check.
- Added regression coverage for the workflow's bot-only guard and permissions.
- Documented the required GitHub auto-merge and branch-status-check settings.
- Runtime Fitness behavior is unchanged from beta.7.

## 2026.8.0-beta.7

### Maintainable workout-provider adapters

- Replaced provider-specific workout heuristics with a registry-based adapter
  architecture plus a generic fallback.
- Added explicit Garmin Connect, Strava, Polar, Hevy, Peloton and Oura adapters.
- Polar Last exercise now maps its documented AccessLink attributes, including
  provider-preserved Running Index and training load.
- Known providers are owned by exactly one explicit adapter; unknown/future
  integrations continue through the generic adapter.
- Added ISO-8601 duration parsing and shared distance/speed normalization helpers
  for provider contracts.
- Added adapter-registry and cross-provider enrichment regression tests.

## 2026.8.0-beta.6

### Tests and HACS release engineering

- Added pytest coverage for heart-rate calculations, live intensity boundaries,
  VO₂max/reference calculations, Banister TRIMP, mechanical work, HRR intensity
  time, aerobic efficiency/decoupling and coefficient of variation.
- Added unit-normalization tests for weight, height, HR, power, pace, speed,
  distance, altitude and cadence.
- Added workout identity/merge regression tests covering Garmin+Strava
  enrichment, conflicting workouts, sparse providers and complete-link grouping.
- Added repository metadata/JSON/brand structure tests.
- Added GitHub Actions for pytest, HACS validation and hassfest.
- Added Dependabot, CODEOWNERS, issue forms, contribution guidelines and a release
  checklist.
- Runtime Fitness behavior is unchanged from beta.5.

## 2026.8.0-beta.5

### Branding polish

- Rebuilt the Fitness logo with generous safe padding so GitHub does not crop it.
- Rebuilt the README overview entirely with real rendered typography for sharp, readable text.
- Rebuilt the GitHub social preview with real typography.
- Refreshed Home Assistant/HACS icon assets from the new graphical mark.
- Runtime integration behavior is unchanged from beta.4.

## 2026.8.0-beta.4

### Documentation and branding

- Added Home Assistant local brand assets under `custom_components/fitness/brand/`.
- Added HACS repository brand assets under `brand/`.
- Added GitHub avatar, social-preview, logo and overview assets.
- Replaced the development-history-style README with user documentation focused on
  setup, live workouts, workout merging, calculated sensors, equations,
  longitudinal evaluation, AI/coaching, scientific basis and limitations.
- Added direct research references for the deterministic physiological methods.

## 2026.8.0-beta.3

### Personal historical workout comparison

- Live-generated Fitness workouts now compare against up to 20 similar prior
  Fitness workouts from the previous 90 days.
- Historical comparison never overwrites raw workout measurements.
- Added aerobic efficiency, decoupling, average HR, average power/speed and
  TRIMP comparisons against the user's own comparable-workout baseline.
- Added deterministic lower/similar/higher personal load context.
- Added a concise personal-context workout summary.
- Workout AI evaluation now explicitly receives this comparable-workout context.
- New comparison entities use the existing lazy-creation lifecycle.


## 2026.8.0-beta.2

### Safer workout merging

- Replaced the previous `start within 5 minutes + compatible sport` duplicate
  matcher with conservative multi-field matching.
- Added hard conflict checks for sport, duration, distance and explicit end time.
- Requires progressively stronger supporting evidence as provider start times
  differ.
- Changed workout grouping from transitive `any()` matching to complete-link
  `all()` matching to prevent nearby separate workouts from being chained into
  one merged activity.
- Reduced the diagnostic workout identity bucket from five minutes to one minute.
- Complementary fields and provider provenance are still merged/preserved for
  records identified as the same workout.


## 2026.8.0-beta.1

First public beta of Fitness for Home Assistant.

### Live workouts

- Arms a workout first and starts the session timer only after valid live exercise
  data arrives.
- Live entities are unavailable outside an active workout so stale sensor values are
  not presented as current exercise data.
- Supports live heart rate, power, cadence, speed, distance and altitude when those
  capabilities are available.
- Adds HRmax percentage, heart-rate reserve percentage/intensity, threshold-relative
  metrics, power-to-weight, pace and other prerequisite-driven live calculations.
- Adds within-session averages/maxima, Banister TRIMP, mechanical work, intensity
  duration, aerobic efficiency and aerobic decoupling when calculable.
- Measures post-exercise heart-rate recovery at 10, 30, 60 and 120 seconds when
  suitable HR data remains available.

### Workouts and evaluation

- Normalizes completed workouts from selected workout-provider devices.
- Merges matching representations of the same workout instead of discarding
  complementary Garmin/Strava/provider data.
- Preserves provider provenance and mismatched provider values in attributes.
- Uses Fitness workout history for 7/28/42-day training-load context and longer-term
  HRR/efficiency/decoupling summaries when enough history exists.
- Uses Home Assistant Recorder long-term statistics for relevant configured/provider
  entities when available.
- Optional AI Task evaluation uses deterministic and longitudinal context rather than
  relying only on the latest raw values.

### Entity lifecycle

- Optional entities are created lazily after their first valid calculation.
- Once created, entities remain registered permanently and become unavailable when
  prerequisites temporarily disappear.
- Existing entity-registry entries from older builds are preserved during upgrade.

### Coaching and feedback

- Optional room-aware color-light feedback, TTS and notifications.
- Runtime Workout room selector follows Home Assistant areas.
- Intensity transitions have a five-second minimum transition guard.
- Light feedback pulses five times and restores the exact pre-feedback light state.
- ANT+ Capture switches are snapshotted before Fitness starts a workout: switches
  already on stay on after the workout; switches Fitness enabled are restored to
  their original off state after the workout/recovery phase.

### Localization

- Ships translations for English, Greek, German, French, Spanish, Italian,
  Portuguese, Dutch, Polish, Russian, Ukrainian, Turkish, Chinese, Japanese and
  Korean.

### Beta note

This is a public beta. Calculations and entity/configuration structure may still be
refined before the first stable release.
