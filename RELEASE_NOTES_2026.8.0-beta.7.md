# Fitness 2026.8.0-beta.7

Workout-provider architecture release.

## Added

- explicit Garmin Connect adapter
- explicit Strava adapter
- explicit Polar adapter
- explicit Hevy adapter
- explicit Peloton adapter
- explicit Oura adapter
- generic fallback adapter for other/future workout integrations
- shared provider normalization helpers and adapter registry
- adapter-specific regression tests

All providers still feed the same conservative workout deduplication/merge layer,
so complementary records can enrich one physical workout without losing provider
provenance.
