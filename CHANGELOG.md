# Changelog

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
