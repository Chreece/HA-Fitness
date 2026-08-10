# Fitness 2026.8.0-beta.24

Critical evaluation-entity regression fix.

- Imports the birth-date constants required by evaluation provenance.
- Fixes the `NameError: CONF_BIRTH_YEAR is not defined` introduced by beta.22/23.
- Isolates entity listener failures so one broken Fitness entity can no longer prevent all remaining entities from updating.
- Adds regression checks for missing `CONF_*` imports and listener isolation.
