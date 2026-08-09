# Fitness 2026.8.0-beta.12

Adds visual workout lifecycle feedback to configured/room workout lights.

- Start with live data: green for 3 seconds, then restore.
- Start while waiting for live data: red until data arrives.
- First live data: green for 3 seconds, then restore the original pre-wait state.
- Workout stop: red for 3 seconds.
- HR recovery 10 s: orange for 3 seconds.
- HR recovery 30 s: yellow for 3 seconds.
- HR recovery 60 s: blue for 3 seconds.
- HR recovery 120 s: green for 3 seconds.
- Lifecycle cues do not delay HR-recovery sampling and are isolated from the
  normal intensity pulse feedback.
