# Fitness 2026.8.0-beta.2

Second public beta of Fitness for Home Assistant.

## Main change: safer duplicate-workout detection

Garmin, Strava and other selected providers can still contribute complementary
fields to one Fitness workout, but records are now merged much more
conservatively.

The matcher checks normalized sport, start time, duration, distance and explicit
end time when those values are available. Contradictory duration/distance/sport
data prevents merging, and records with increasingly different start times need
increasingly strong supporting agreement.

Workout clustering also now requires a candidate to match every record already
in the group, preventing transitive chain merges of nearby separate sessions.

All beta.1 functionality is retained.
