# Fitness 2026.8.0-beta.3

Third public beta of Fitness for Home Assistant.

## Personal historical context for live-generated workouts

Completed workouts created from Fitness live sessions now keep raw factual
measurements separate from personal historical comparisons.

Fitness finds similar prior workouts from the previous 90 days and, when enough
data exists, compares:
- aerobic efficiency
- aerobic decoupling
- average heart rate
- average power or speed
- Banister TRIMP

It also exposes the number of comparable workouts, a relative load-context state,
and a concise personal-context summary.

The AI workout evaluation receives these personal comparisons together with the
existing long-term Fitness/Recorder context.

All beta.2 duplicate-matching safeguards and previous functionality remain.
