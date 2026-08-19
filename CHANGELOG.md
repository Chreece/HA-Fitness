# Changelog

## Unreleased

- Added a compact multi-dashboard navigator below the main toolbar: when a profile has multiple dashboards it shows the active dashboard name, position and previous/next controls without covering cards; it remains available when the toolbar auto-hides, participates in TV-remote navigation, removes the duplicated textual plus from Add dashboard, and trims the synthetic final grid-row gap that left dead space at the bottom.
- Garmin invalid-file handling now preserves a small private bounded forensic copy under `.storage/fitness_garmin_invalid`, records FIT/header/compression diagnostics, accepts raw FIT plus zlib/gzip/raw-DEFLATE wrappers only when they reveal a genuine FIT header, and re-probes older invalid records once so potentially useful monitoring/SpO2/sleep files can be investigated instead of silently discarded.

- Hardened Garmin full-device sync so successful partial batches enter an explicit cooldown state, manual retries respect the watch settle window, malformed/opaque FileSync records are retried and quarantined individually instead of aborting the archive, and diagnostics expose the last successful batch and next retry time.
- Expanded the goal-aware AI coach with rolling seven-day structured training plans, guided live execution/TTS, Fitness Tests and capability-driven smartwatch export hooks.
- Added Fitness TV plugin cards for RSS/news, weather, lights, music, video and TTS plus built-in Performance, Minimal, OLED, Glass and Classic presentation themes.
- Refined the Workouts card with sport-specific summaries, header navigation/edit/delete controls, expandable details and Strava-style GPS route presentation; Garmin and CYCPLUS M1 now expose their stored FIT routes through the canonical `gps_track` key.
- Daily AI workout/rest recommendations now refresh at 00:00:01 local time, after a genuinely fresh completed sleep session, and when the selected/default AI provider becomes available.
- Remote Fitness accounts now use their own authenticated `/fitness-tv/main` athlete portal URL while retaining strict one-profile authorization.

## 2026.8.01a04

- Reworked Fitness infrastructure into separate **Fitness Protocols** and **Fitness Devices** services: protocol hardware is managed independently while physical fitness devices remain merged across Bluetooth/ANT+ routes.
- Replaced the old single-protocol setup with **Manage sensor protocols**, supporting Bluetooth/ANT+ multi-select, automatic or manual hardware discovery, bounded **Discover now**, manual adapter selection, and ownership-aware enable/disable behavior that never shuts down shared Home Assistant hardware.
- Added the first-class merged **Workout history** dashboard card with calendar browsing, stored workout details, editing/deletion and GPS-route display for canonical Fitness workouts from local devices and external providers.
- Improved dashboard card selection so desktop/tablet dashboards remain visible and reflow beside the selector while choices are changed.
- Added per-profile optional AI daily training suggestions and once-per-minute live-workout analysis, with safe fallback from the selected AI Task to Home Assistant's preferred AI Task and silent AI disablement if neither is available.
- Fixed infrastructure entries being exposed as Fitness users, stale fake ANT+/Bluetooth protocol devices, protocol-manager state loss/reload races, and dashboard WebSocket registration/startup regressions.

## 2026.8.01a03

- Expanded direct smart-device support and the universal health/history model for sleep, activity, heart rate/HRV, SpO2, temperature, stress, device state and workout data without inventing unsupported measurements.
- Added/expanded local adapters and device recognition for Xiaomi Mi Band generations, selected Amazfit/Huami devices, Ultrahuman Ring AIR, MyKronoz ZeTime, HPlus-family devices and other documented/open protocol families.
- Added reusable Home Assistant Repair/reconfigure flows for devices that require pairing mode, authentication keys, confirmation or other user action, with secure credential storage and automatic retry.
- Improved Smart Fitness Device discovery/ownership/merge behavior so one physical device can use multiple transports without becoming duplicate Fitness devices.
- Added richer canonical daily summaries and bounded intraday health history while keeping storage, Bluetooth work and synchronization bounded.

## 2026.8.01a02

- Added direct local Garmin and CYCPLUS M1 workout-archive synchronization with bounded/resumable FIT import, canonical workout merging, device diagnostics and safe Bluetooth lifecycle handling.
- Added Smart workout-device discovery/setup, profile ownership for stored-workout imports, shared-sensor routing and conservative cross-transport physical-device merging.
- Expanded Fitness TV and profile management with configurable dashboard composition, themes, music/TTS/media integrations, remote sensors/Cast workflows and responsive desktop/mobile/TV controls.
- Added shared household scale routing, profile weight/BMI handling, recovery/readiness/history improvements and broader HealthSync/Apple Health workout/sleep ingestion.
- Completed broad performance, stall-safety, security and localization passes across radio hot paths, storage, remote gateways, media relays, WebSockets and all 15 bundled languages.

## 2026.8.01a01

First public alpha release of HA-Fitness. This entry consolidates all development history that predates the alpha release into the major capabilities delivered at that point.

- Established multi-user Fitness profiles, canonical workout/history storage, provider reconciliation, retention and Home Assistant workout calendars.
- Built the adaptive Fitness dashboard and Fitness TV experience, including **Modern fitness visual cards**, consolidated user-focused views, **Fitness live workout** presentation with auto-fit/wrap behavior, route/GPS visualization and native-style workout map interaction.
- Added live Bluetooth and ANT+ fitness sensor support with physical-device identity, assignment, transport handover, diagnostics, bounded discovery and workout ownership.
- Added workout, recovery, readiness, training-load, sleep and evaluation models with historical baselines and science/method documentation.
- Added Fitness TV music, TTS, Cast, remote-access and browser sensor workflows with profile-scoped permissions and settings.
- Added dashboard customization, visual editors, Community card discovery, responsive layouts and stability work preventing unnecessary map blinking/reloads.
- Added provider/device adapters, normalized completed-workout imports and canonical history reconciliation while keeping Home Assistant startup and runtime work bounded.
- Established the project-wide security, storage, performance, localization, testing and release foundations used by later alpha releases.

### Versioning

Release tags and `manifest.json` use the same canonical version. Alpha prereleases use `YYYY.M.RRaXX` (for example `2026.8.01a01`), beta prereleases use `YYYY.M.RR-betaXX`, and stable releases use `YYYY.M.RR`.

See [Science & methods](docs/SCIENCE.md) for the physiological and training calculations used by Fitness.
