# Fitness 2026.8.0-beta.1

This is the first public beta of **Fitness for Home Assistant**.

Fitness combines live exercise data, completed workouts, physiological inputs,
long-term Home Assistant statistics, scientifically grounded derived training
metrics, and optional AI evaluation in a person-centered integration.

## What to test in this beta

- Setup and reconfiguration flows.
- Live workout start/stop behavior.
- ANT+ Capture switch snapshot/restore.
- Live sensor availability outside workouts.
- Garmin/Strava/other workout-source normalization and merging.
- Post-workout HRR collection.
- Lazy creation of optional sensors.
- Recorder-based long-term evaluation.
- Room-aware light/TTS coaching.
- AI Task general and workout evaluations.

## Versioning

This project uses `YYYY.MM.release`. During prerelease testing the stage is appended,
so this release is `2026.8.0-beta.1`. The intended stable tag for this line will be
`2026.8.0`.

Please report bugs with Home Assistant version, Fitness version, relevant entity
attributes, and logs where possible.
