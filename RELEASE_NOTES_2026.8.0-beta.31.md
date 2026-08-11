# HA-Fitness 2026.8.0-beta.31

## Progressive Evaluation domains

- Grouped Evaluation entities now materialize when any scientifically valid component in that domain is available.
- Richer longitudinal metrics automatically become the domain state as sufficient history accumulates.
- Sleep consistency can begin from current/short-term sleep duration and later progress to duration, bedtime, wake-time, and midpoint variability.
- Sleep deficit can begin from the latest valid adult sleep duration before a full seven-night history exists.
- Autonomic recovery can use current or short-term HRV/resting-HR context before a 28-day baseline is available.
- Training load can materialize from TRIMP, training duration, or workout frequency and later progress to 7-vs-28-day load change.
- Heart-rate recovery can materialize from any valid HRR checkpoint and later add personal baseline context.
- Cross-domain training/recovery correlation remains intentionally gated until enough paired observations exist.
