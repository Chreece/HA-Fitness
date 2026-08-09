# Fitness 2026.8.0-beta.14

Fixes announcement target selection and simplifies intensity light feedback.

- Configured TTS media players are respected as the primary targets.
- Room media players are used only to replace configured players assigned to a
  different Workout room.
- Area-less and same-room configured players remain selected.
- Start/Stop/Recovery announcements fall back to localized static text after a
  short AI timeout.
- Intensity changes use a single three-second color cue instead of blinking.
