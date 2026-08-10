# Fitness 2026.8.0-beta.17

Live workout stability and coaching-noise reduction release.

- Separates high-frequency live events from completed-workout provider discovery.
- Caches live sources, stores at most one sample/second and publishes live state
  at most twice/second.
- Avoids full provider/workout evaluation on every live sensor update.
- Requires 10 seconds in the same intensity zone before optical feedback.
- Zone changes are light-only.
- HR-recovery checkpoints/completion are light-only.
- TTS is limited to workout start/wait→ready, one stop/recovery message and the
  configured periodic live update.
