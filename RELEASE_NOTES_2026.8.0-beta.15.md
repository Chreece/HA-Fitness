# Fitness 2026.8.0-beta.15

Fixes Home Assistant config-entry migration after the language schema update.

- Adds the required `async_migrate_entry` handler.
- Existing profiles migrate automatically to version 11.
- Existing configuration is preserved.
- Missing profile language is initialized from HA UI language when supported,
  otherwise English.
