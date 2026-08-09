# Fitness 2026.8.0-beta.9

Fixes completed-workout AI/announcement behavior.

- No previous workout is replayed after Home Assistant restart.
- Provider entities are allowed to settle before a new workout is accepted.
- Incomplete/unavailable workout representations cannot trigger AI, TTS or notifications.
- Includes the Dependabot automation introduced in beta.8.
