# Changelog

## Unreleased

- Fixed release/test contract drift: prerelease validation no longer hard-codes the previous alpha version, Garmin manual-sync safety coverage now verifies the structural background-scheduling contract instead of depending on neighboring class names, and every direct-device manual sync button uses the universal localized `sync_device_data` label.
- Exposed directly synchronized device wellness data as native Home Assistant sensors without any extra device polling: Fitness now materializes canonical steps, SpO₂, heart rate/HRV, respiration, stress/body battery, activity/intensity minutes, floors, calories, sleep score, temperature, blood pressure, VO₂ max, body composition, battery/wear/charging and every other supported canonical health metric as soon as synchronized data exists; cumulative daily metrics use total-increasing semantics and the persisted per-device metric catalog is expanded safely to 64 metrics.
- Added a modern synchronized-wellness infographic card, data-aware empty-card layout previews, clipping-safe multiline dashboard/settings actions, and a single hidden-scrollbar TV/Cast viewport so empty cards reclaim layout space outside edit mode and nested TV cards no longer create a second right-side scrollbar.
- Hardened the independent Fitness web portal: remote subdomains now authenticate only the administrator-assigned account even if a form is tampered with, login offers every bundled Fitness language and carries that choice into the restricted dashboard session, same-origin/CSRF and streaming request-size checks are stricter, Web Bluetooth/WebUSB are explicitly same-origin only, and additional cross-origin isolation headers are applied.
- Added the first real local workout-delivery target: accepted/assigned Bangle.js devices can receive Fitness tests, today’s AI structured workout, and weekly AI-plan workouts over a bounded explicit Bluetooth write into three HA-Fitness-owned Storage files; writable-device discovery now also requires profile-control permission.
- Fixed Remote Fitness wildcard-host routing when Home Assistant HTTP is already running: Fitness now activates its exact-host guard in aiohttp’s prepared middleware chain after freeze, retries a previously failed registration, and fails closed by withholding/withdrawing managed remote DNS instead of exposing the generic Home Assistant login.
- Replaced HA-user bindings with independent private **Fitness accounts** and explicit Administrator/Local/Remote roles: Fitness now owns scrypt-hashed credentials, one-time administrator-visible setup passwords, forced strong-password first login, self-service username/password changes, LAN-only local/admin login, exact-host remote login, rate limiting/lockout, CSRF-protected Secure/HttpOnly/SameSite sessions, per-account live diagnostics, and strict own-profile/view-only ACLs. Remote-account subdomains now own Cloudflare DNS and open a restricted Fitness-only HTTPS portal instead of generic Home Assistant; HA administrators are bootstrap-only until the first usable Fitness administrator exists.
- Expanded Garmin local GFDI archive decoding so previously unsupported FIT records are reprocessed with explicit wellness decoders plus conservative named-field extraction for steps, stress, respiration, resting HR, SpO2, body battery, intensity minutes, sleep score, blood pressure, VO2 max and related data; unknown fields remain inventoried rather than guessed. AI training suggestions now expose a clickable More details/Hide details panel for structured workout and rationale.
- Repacked Fitness TV cards as true dense masonry on TV so short cards can fill earlier holes instead of forcing a source-order last row; Up now restores a hidden toolbar whenever there is no visible section above, remote selection uses a foreground/background depth transition, Recovery/Training Readiness fills avoid the TV Chromium transform-compositor conflict, and two distinct physical Back presses reliably stop Cast.
- Simplified Fitness Account presentation before the independent-account migration: profile language remains the single language authority and redundant account controls were removed. This groundwork is now superseded by the independent Fitness-account portal described above.
- Garmin FileSync now recognizes `LiveActivity` as bounded zlib/JSON structured device data rather than invalid FIT, persists the workout/live-activity definition as a device artifact, and re-probes older quarantined files whenever the payload decoder revision advances.
- Added the Cloudflare DNS foundation: administrators configure zone, Fitness base domain, scoped API token and public IPv4 once. The final model now assigns each managed DNS-only hostname to a Remote Fitness account rather than storing External access as a user-facing profile setting; managed records never overwrite unrelated DNS and nginx/Certbot remain untouched.
- Added a compact multi-dashboard navigator below the main toolbar: when a profile has multiple dashboards it shows the active dashboard name, position and previous/next controls without covering cards; it remains available when the toolbar auto-hides, participates in TV-remote navigation, removes the duplicated textual plus from Add dashboard, and trims the synthetic final grid-row gap that left dead space at the bottom.
- Garmin invalid-file handling now preserves a small private bounded forensic copy under `.storage/fitness_garmin_invalid`, records FIT/header/compression diagnostics, accepts raw FIT plus zlib/gzip/raw-DEFLATE wrappers only when they reveal a genuine FIT header, and re-probes older invalid records once so potentially useful monitoring/SpO2/sleep files can be investigated instead of silently discarded.

- Hardened Garmin full-device sync so successful partial batches enter an explicit cooldown state, manual retries respect the watch settle window, malformed/opaque FileSync records are retried and quarantined individually instead of aborting the archive, and diagnostics expose the last successful batch and next retry time.
- Expanded the goal-aware AI coach with rolling seven-day structured training plans, guided live execution/TTS, Fitness Tests and capability-driven smartwatch export hooks.
- Added Fitness TV plugin cards for RSS/news, weather, lights, music, video and TTS plus built-in Performance, Minimal, OLED, Glass and Classic presentation themes.
- Refined the Workouts card with sport-specific summaries, header navigation/edit/delete controls, expandable details and Strava-style GPS route presentation; Garmin and CYCPLUS M1 now expose their stored FIT routes through the canonical `gps_track` key.
- Daily AI workout/rest recommendations now refresh at 00:00:01 local time, after a genuinely fresh completed sleep session, and when the selected/default AI provider becomes available.
- Remote Fitness accounts use the restricted `/fitness-auth/` portal and exact-host ACL rather than the earlier generic `/fitness-tv/main` entry.

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
