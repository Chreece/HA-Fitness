# HA-Fitness 2026.8.0-beta.29

Evaluation and sleep polish test build.

- Greek translations for Sleep entities and Sleep setup labels.
- Removes obsolete mirrored Evaluation entities from the HA entity registry.
- Adds evidence-based, data-gated Evaluation metrics from merged workouts, merged sleep history and Home Assistant Recorder statistics.
- Persists and de-duplicates merged completed workouts and sleep periods for longitudinal evaluation.
- Adds sleep-duration, sleep-HRV, resting-HR, VO2max, training-load and HR-recovery longitudinal context without proprietary readiness/recovery scores.
- Rejects internally impossible sleep-awake values such as broad daytime Garmin awake-duration sensors.
- Normal Live/Workout/Sleep entities keep compact provenance; scientific method/explanation attributes remain Evaluation-only.
