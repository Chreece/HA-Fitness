# Fitness 2026.8.0-beta.16

Adds serialized TTS playback.

- Fitness waits for the current spoken message to finish before sending another.
- Session, recovery, periodic and intensity announcements share the same queue.
- Multiple speakers for one announcement still play together.
- Playback-state safety timeouts prevent broken players from blocking TTS forever.
