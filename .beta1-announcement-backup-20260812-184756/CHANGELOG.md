# Changelog

## 2026.8.6

- Added **Fitness Training Readiness**, a transparent 0–100 Fitness-owned readiness estimate that combines available personal autonomic recovery, sleep, training recovery and post-exercise recovery evidence. Missing domains are omitted and weights are renormalized; the entity exposes component scores, evidence, confidence, formula and scientific basis in attributes.
- Renamed the former Sleep device to the translated **Recovery** device using Home Assistant device-name translations while keeping the stable device identifier for migration safety.
- Expanded the Sleep & Recovery card with a color-coded readiness hero, confidence, component bars and retained sleep detail/stage views.


## 2026.8.6 — Validated canonical history

- Added a public **Fitness live workout** Lovelace card so the current session metrics and Start/Pause/Resume/Stop controls can be added manually from Home Assistant's card picker, while keeping the generated Live workout dashboard view.
- Fixed responsive Sleep & Recovery layouts for long translated labels and values: metric tiles now auto-fit/wrap instead of overflowing the card, and the sleep-stage legend handles narrow/mobile widths more safely.

- Historical 7/28/90-day evaluation now consumes persistent canonical Fitness history after Fitness normalization/selection, validation and daily deduplication; raw provider Recorder rows no longer directly produce historical results.
- Recorder is retained only as a 90-day bootstrap/import source for existing installations. Imported observations are materialized into Fitness storage, while current merged Fitness observations supersede imported values for the same day.
- Added shared validation before historical calculations: real timestamps, finite numeric values, broad corruption bounds, chronological ordering, distinct-day deduplication, strict coverage and provenance/audit metadata.
- Workout and sleep longitudinal calculations now validate Fitness-owned persisted records before calculation. Incomplete/corrupt sleep sessions and malformed workouts are rejected with auditable reasons.
- Historical summaries expose raw/valid/rejected sample counts, rejection reasons, coverage, oldest/newest valid sample and canonical data source.


## 2026.8.4 dashboard history audit

- Historical Evaluation metrics now require real Recorder coverage: at least 5/7 days for 7-day means, 21/28 days for 28-day means, and 60/90 days for 90-day means. Insufficient history is unavailable instead of being presented as a long-term result.
- Sleep 7/28-day averages and variability use the same strict completed-night coverage rules; the 7-day deficit remains unavailable below five completed nights.
- VO₂max Evaluation now exposes its actual Recorder daily series and renders a compact modern history trend when enough samples exist.
- Historical entity attributes expose sample coverage and minimum requirements so users can verify why a trend is or is not shown.

- Fixed the 7-day sleep deficit so it is derived only from completed sleep sessions in the rolling 7-day history; it no longer falls back to `7 h - latest sleep`. Sleep as Android Recorder reconstruction now imports every completed session from an 8-day window, while an in-progress sleep remains excluded until its `stopped` event. The evaluation entity exposes observed-night count, rolling average, window size, and minimum sample requirement for verification.

## 2026.8.4

- Sleep merge consistency: when multiple providers describe the same night, Fitness now keeps duration + Light/Deep/REM/Awake from one coherent stage-rich provider bundle instead of mixing a duration from one provider with stages from another. The Sleep & Recovery donut total also reads the merged `last_sleep_duration` entity directly.
- Workout card deduplication: GPS workouts now show the map followed by the complete normalized workout metric grid only once. The separate pre-map workout summary is kept only for workouts without route data.
- Hassfest dependency fixes: declare Home Assistant `http` as a dependency and optional Recorder integration access through `after_dependencies`.
- GitHub Actions maintenance: update `actions/checkout` from v4 to v5 (Node 24 runtime).

- Fixed Home Assistant **Add Card** discovery for the three consolidated Fitness cards: the frontend now mutates the existing `window.customCards` registry in place instead of replacing the Array object, preserving Home Assistant's registry reference.
- Disabled automatic picker previews for the asynchronous/profile-aware Fitness summary cards. They remain fully selectable and visually configurable, but the card picker no longer instantiates live workout/sleep/evaluation content before a stable configuration exists.

- Workout map interaction now behaves like a native map: mouse/touch drag pans the route, two-finger pinch zooms on touchscreens, mouse wheel/trackpad zoom works on desktop, and double-tap/double-click fits the route again. The temporary gesture transform is rendered without rebuilding OSM tiles, with a single tile redraw when the gesture finishes.
- Removed the map navigation/zoom button cluster because direct drag/pinch/wheel interaction replaces it.

- Final dashboard stability polish: consolidated cards now keep their shadow DOM and embedded children alive across unrelated Home Assistant state updates, eliminating the periodic full-card/map blink caused by rebuilding every child on every `hass` assignment.
- Workout map navigation now includes directional pan controls (up/down/left/right), zoom in/out, and fit/reset; manual navigation no longer causes a second redraw on the next HA state update.
- Workout route redraws now key off the actual GPS payload and displayed workout values instead of provider `last_updated`, so unrelated provider refreshes do not reload OpenStreetMap tiles.
- The Home Assistant card picker now exposes only the three consolidated public cards: **Fitness workout**, **Fitness sleep & recovery**, and **Fitness evaluation**. Legacy component cards remain private implementation details only.
- The generated Community dashboard is simplified to a three-card summary Overview plus a separate native **Live workout** view for session sensors and controls.

- Consolidated the adaptive dashboard into three user-focused cards: **Workout** (normalized metrics, sport-aware running pace, GPS route and baseline comparison), **Sleep & Recovery** (sleep stages, duration, HRV and recovery context), and **Fitness Evaluation** (cardiorespiratory progress and training load), while retaining long-term trend graphs without duplicating the same information across separate cards.
- Dashboard card text now follows the **current Home Assistant UI language** when that language is supported by Fitness, independently of the Fitness profile language used for AI/TTS. All 15 Fitness dashboard translations are exposed to the frontend with English fallback.
- Workout cards remain provider-independent by consuming normalized/merged Fitness workout entities. GPS is shown only when the selected workout sources expose a usable route, so providers without GPS simply omit the map instead of showing an empty map card.
- Consolidated cards use natural Home Assistant Sections sizing and capability-aware child content to avoid the large gaps and overlapping card layouts seen on narrow/mobile dashboards.

- Dashboard card sizing now uses Home Assistant Sections natural-height behavior (no fixed row reservation), eliminating both card overlap and large artificial gaps between adaptive Fitness cards.
- Sleep-stage donut totals and individual stage durations now display values of 60 minutes or more as hours + minutes; the recovery card applies the same formatting to sleep deficit.
- Running pace is now driven by the normalized **merged Fitness workout** rather than raw provider-card attributes. Nested provider sport metadata such as Garmin `sportType.sportTypeKey = running` is normalized, and pace falls back to `moving time ÷ distance` (or duration ÷ distance) when average speed is unavailable.

- Dashboard layout polish: increased Home Assistant Sections grid allocation for adaptive Fitness cards so Progress, Recovery and Training Load cards no longer overlap on narrow/mobile dashboards.
- Sleep visualizations now show durations of 60 minutes or more as hours + minutes instead of large raw minute totals.
- Running workout summaries convert compatible average-speed values to pace in `min/km` when the completed workout is identified as running, trail running, treadmill running or jogging.
- Removed the informational OpenStreetMap tile-loading note from the workout route card while retaining normal OpenStreetMap attribution.

- Added adaptive **Fitness today** and **Workout highlights** cards inspired by modern fitness-app overview patterns; they automatically hide unavailable metrics and use the selected Fitness user's entities.

- Sleep as Android now stays completely silent while sleep tracking is active; phase/paused/resumed events do not update Fitness sleep, history, evaluation or AI. The completed session is reconstructed once from Recorder after `stopped`, including Awake/Light/Deep/REM where available.
- Fixed frontend `CustomElementRegistry` errors by registering unique constructors for every Fitness card editor instead of reusing the same constructor under multiple custom-element names.
- Enhanced the latest-workout route card with tighter framing, interactive zoom in/out/reset controls, and an adaptive workout summary using only metrics available for the selected Fitness user.

- Modern fitness visual cards: added profile-aware **Fitness progress**, **Fitness recovery**, and **Fitness training load** cards with compact personal-baseline context and visual trend cues.
- Workout route map now frames GPS tracks more tightly while preserving route endpoints and map attribution.
- Lovelace resource registration now reconciles duplicate Fitness resources, forces the canonical resource to `module`, and keeps one cache-busted frontend URL so Community cards load automatically without a manual `import()`.


- Fixed Community card discovery by versioning the bundled frontend resource on dashboard UI revisions, forcing Home Assistant/browser caches to load the current card registrations and visual editors.
- Stopped the workout-route card from rebuilding its OpenStreetMap tile DOM on every Home Assistant state update; route source lookup and rendering are now cached and only refreshed when the route data or card width actually changes, eliminating map blinking/reloads.
- Added explicit Home Assistant card-picker metadata for Fitness route, baseline comparison and sleep-stage cards.
 — Adaptive dashboards

- Added native visual editors for all bundled Fitness custom cards. Baseline comparison and sleep-stage cards now ask only for a Fitness user/profile and automatically resolve the compatible Fitness entities, matching the route-card experience.
- Manual custom-card configuration remains backward compatible with explicit `metrics`, `entities`, or route `entity`/`attribute` values for advanced users.

- Added a modern, localized Fitness Community dashboard with Overview, Progress, Workouts, and Recovery & Sleep views.
- Added capability-aware visualizations for long-term Fitness evaluation, workout comparison, sleep stages, and available Recorder statistics.
- Added automatic workout-route discovery from selected completed-workout providers, including Garmin Connect route/polyline data, with an OpenStreetMap route card.
- Added a visual editor for the Fitness workout route card: users select only their Fitness profile, while Fitness automatically resolves the compatible workout provider entity and GPS/route attribute. With a single Fitness profile, even that selection is automatic.
- Kept advanced manual `entity`/`attribute` route-card configuration backward compatible while removing it from the normal user workflow.
- Localized the route-card profile selector, explanation, route title, empty state, and privacy text across every language supported by Fitness.

## 2026.8.0 — First stable public release

- Refactored sleep support into provider-specific sleep adapter modules for Garmin Connect, Oura, Fitbit, Withings, WHOOP, Suunto, SleepIQ, Eight Sleep and Sleep as Android.
- Added explicit provider ownership for Suunto, Fitbit and Withings completed-workout discovery while retaining conservative normalized parsing and the generic fallback for future integrations.
- Expanded the README with separate workout and sleep compatibility tables and capability-based support notes.

- Scientific live-workout provenance: every Fitness-calculated live metric now identifies itself as calculated and exposes formula, exact data used, localized interpretation/usefulness, and a study citation where a specific scientific basis applies. Raw provider measurements remain lightweight.
- Correct legacy localized naming for the last-workout AI evaluation without overwriting user-customized names. — First stable public release
- Completed the localization pass for all Fitness-created devices, entities and user-facing state attributes across every supported language; device names are now concise (Evaluation, Live workout, Sleep, Workouts) and no longer repeat the integration/profile prefix. Live, completed-workout and sleep provenance labels are localized as well, while stable raw attribute keys remain unchanged for templates and automations.
- Fitness output devices are centrally excluded from every setup source selector so Evaluation/Live/Sleep/Workout devices can never feed back into Fitness as inputs.
- Completed-workout provenance uses human-readable provider names where possible, while exact entity IDs remain untouched.

Fitness 2026.8.0 consolidates the complete prerelease line into the first stable public release.

### Highlights

- Capability-aware setup suggests only profile, live-workout, completed-workout and sleep sources that Fitness can actually parse.
- Multi-source live workouts select metrics independently, use sticky failover, normalize units, and keep high-frequency updates isolated to Live entities.
- Completed workouts from multiple providers are conservatively deduplicated and merged without losing complementary fields or provenance.
- Sleep records from multiple supported providers are merged by sleep episode/night without merging unrelated naps or separate periods.
- Evaluation is organized into compact evidence-based domains for sleep consistency/deficit, autonomic recovery, cardiorespiratory fitness, training load, heart-rate recovery and training/recovery relationships.
- Evaluation entities materialize progressively as valid evidence becomes available and enrich themselves as longer history accumulates.
- Home Assistant Recorder history and personal baselines are preferred over one-off population interpretations where appropriate.
- Evaluation attributes now emphasize metric-specific evidence, windows, baselines, sample counts and research references instead of generic repeated boilerplate. All user-facing Evaluation attribute labels are localized through Home Assistant translation keys; legacy developer metadata is kept internal.
- Optional AI is interpretation-only: deterministic calculations remain independent of AI. AI prompts receive curated fitness-semantic context rather than raw Recorder/provider dumps and enforce the profile language.
- Full localization is included for English, Greek, German, French, Spanish, Italian, Portuguese, Dutch, Polish, Russian, Ukrainian, Turkish, Chinese, Japanese and Korean.
- Room-aware lights, TTS, notifications, ANT+ capture ownership, post-workout recovery, scientific references and automated validation/testing are included.

### Upgrade note

The stable release keeps the lazy entity lifecycle introduced during prereleases. Obsolete fine-grained Evaluation mirrors from older betas are migrated away; grouped Evaluation domains retain the scientifically useful information as state plus attributes.

---

## Prerelease development history

The entries below document the development path to 2026.8.0. They are retained for traceability; separate `RELEASE_NOTES_*.md` files are no longer used.

## 2026.8.0-beta.26

### Hassfest translation-schema fix

- Removed unsupported top-level `evaluation_provenance` sections from
  `strings.json` and all `translations/*.json`.
- Preserved all 15 provenance languages in Fitness' internal deterministic
  localization catalog in `explanations.py`.
- Runtime provenance localization still follows the selected Fitness language.
- Added regression tests that reject custom/unsupported Home Assistant
  translation top-level keys.
- Retains beta.25 evaluation availability fixes.

## 2026.8.0-beta.25

### Evaluation availability hotfix

- Fixed `NameError: provenance_text is not defined` in
  `localized_evaluation_provenance()`.
- Added the missing `provenance_text` import in `manager.py`.
- Added regression coverage for provenance helper imports and direct-scope
  unresolved names.
- Retains beta.24 birth-date constant imports and listener exception isolation.

## 2026.8.0-beta.24

### Critical evaluation availability fix

- Fixed missing `CONF_BIRTH_DAY`, `CONF_BIRTH_MONTH`, and `CONF_BIRTH_YEAR` imports used by evaluation provenance.
- Fixes evaluation entities becoming unavailable after upgrading from beta.20 to beta.22/23.
- Hardened `_notify()` so an exception in one entity listener is logged and cannot block updates for the remaining Fitness entities.
- Added regression coverage for undefined Fitness constants and listener isolation.

## 2026.8.0-beta.23

### Provenance localization

- Localized human-facing evaluation provenance descriptions in all 15 supported languages.
- Provider/direct/history explanatory notes now follow the user's selected Fitness language.
- Kept formulas, entity IDs, method identifiers, numerical values and units untranslated intentionally.
- Added regression tests for complete provenance vocabulary and technical-field preservation.

## 2026.8.0-beta.22

### Explainable evaluation provenance

- Every evaluation sensor now receives deterministic value provenance.
- Calculated entities expose their actual formula and concrete input sources.
- Source details can include entity ID, raw value/unit, normalized unit,
  configured value, provider entity or workout source.
- HR reserve, VO₂max, FRIEND reference, threshold pace/power, power-to-weight,
  HRV status, fitness age difference and acute:chronic ratio now explain their
  exact derivation.
- Direct provider metrics explicitly state that Fitness is exposing a provider
  value rather than claiming a proprietary calculation.
- Long-term metrics identify their 7/28/42/90-day history window and aggregation.
- Expanded the deterministic explanation catalog so known evaluation metrics no
  longer fall back to a generic method description.
- Added regression coverage for provenance completeness and AI-free metadata.

## 2026.8.0-beta.21

### Setup localization and Garmin VO₂max fixes

- Localized sex and birth-month selector choices in all 15 supported languages.
- Removed hard-coded English selector labels from config/options flows.
- Added Unicode unit normalization for Garmin/Home Assistant VO₂max
  `mL/(kg·min)` and equivalent multiplication/minus glyphs.
- Existing empty Fitness Input fields now propose strict exact autofill matches;
  existing user-selected values always take precedence.
- Added regression tests for Greek selector labels, all selector translations,
  Garmin VO₂max unit normalization and options autofill.

## 2026.8.0-beta.20

### Deterministic explanations and complete localization

- Sensor scientific/explanatory attributes are explicitly AI-free and deterministic.
- AI remains only an optional coaching/interpretation layer.
- Scientific calculation strings now use stable formulas/algorithm identifiers instead of AI-generated or model-dependent prose.
- Corrected explanation metric keys so workout TRIMP, mechanical work, aerobic efficiency/decoupling, HR recovery and threshold W/kg receive their specific method metadata.
- Completed field-specific `data_description` help for every setup/options field in all 15 shipped languages.
- Removed generic setup-help fallback wording from the shipped translations.
- Added localization structure/completeness tests and deterministic-metadata regression tests.
- Added a practical TL;DR near the top of the README for new users.

## 2026.8.0-beta.19

### Source failover, setup UX and explainable sensors

- Added sticky per-metric live-source failover before a metric becomes unavailable.
- Different metrics can use different live devices simultaneously.
- Added source entity/device/integration, fallback status and switch-history diagnostics.
- Profile numeric/entity inputs now offer a compatible-entity dropdown plus manual custom value.
- Periodic coaching remains anchored to workout time and refreshes current statistics before each evaluation.
- Added deterministic localized method/calculation/usefulness/input attributes to calculated/evaluation sensors.
- Added detailed setup field explanations in every shipped UI language with English fallback.
- Retains 30-second derived calculations, 1 Hz canonical sampling, serialized AI/TTS and serialized/restoring light feedback.

## 2026.8.0-beta.18

### Strict autofill, 30-second live calculations and feedback serialization

- Exact documented profile autofill for Garmin, Hevy and Oura only.
- HA-ANT-Plus live sensor-device preselection; adapter/control-only devices excluded.
- Exact explicit-adapter workout-device preselection.
- Derived live calculations cached and refreshed every 30 seconds.
- Live sensor entity getters no longer run full Fitness evaluation.
- AI requests serialized and mutually exclusive with audible Fitness TTS.
- Lifecycle and zone light cues serialized with guaranteed state restoration.
- Extended RGBW/RGBWW/color-temperature snapshot fidelity.

## 2026.8.0-beta.17

### Live workout stability and quieter coaching

- Split high-frequency live sensor events from completed-workout provider events.
- Cached live source mappings instead of rediscovering them for every measurement.
- Capped stored live samples at 1 Hz and live entity publication at 2 Hz.
- Removed full Fitness/provider/workout evaluation from the live intensity hot path;
  HR intensity now uses a session-start cached physiology basis.
- Zone changes must remain stable for 10 seconds before optical feedback.
- Zone feedback is light-only; no zone AI/TTS announcements.
- Recovery 10/30/60/120 checkpoints and completion are light-only.
- Automatic speech is limited to start/wait→ready, one stop/recovery-procedure
  message, and the configured periodic live announcement.
- Added hot-path, announcement-policy and stability regression tests.

## 2026.8.0-beta.16

### Sequential TTS playback

- Added a per-profile TTS playback lock shared by all Fitness announcements.
- Fitness now waits for actual media-player playback to finish before sending
  the next announcement.
- Multiple speakers receiving the same announcement are still started together.
- Added playback-start and hard-finish safety timeouts for players with incomplete
  state reporting.
- Added TTS serialization regression tests.

## 2026.8.0-beta.15

### Config-entry migration fix

- Added `async_migrate_entry` for schema version 11.
- Existing Fitness profiles now upgrade cleanly after the per-profile language
  field was introduced.
- Migration preserves existing data/options and only adds a language when absent.
- Migrated profiles default to the current supported Home Assistant UI language,
  otherwise English.
- Added migration regression tests.

## 2026.8.0-beta.14

### Announcement targeting and simpler intensity lights

- Explicit configured TTS media players are now authoritative.
- Selected-room media players are substituted only when a configured
  area-bound player belongs to a different room.
- Area-less configured players always remain; same-room configured players stay
  without automatically adding every other media player in the room.
- Session lifecycle AI wording has a 2.5-second deadline with immediate localized
  static fallback so Start/Stop/Recovery announcements remain timely.
- TTS service dispatch waits until Home Assistant accepts the action.
- Intensity light feedback no longer heartbeat-blinks.
- Accepted intensity changes now show one color for three seconds and restore the
  previous state.
- Added regression tests for announcement target precedence, TTS fallback timing,
  and non-blinking intensity feedback.

## 2026.8.0-beta.13

### Per-profile language

- Added a language selector to initial Fitness profile setup.
- The selector contains exactly the 15 languages already localized by Fitness.
- New profiles preselect the current Home Assistant UI language when supported,
  otherwise English.
- Language can be changed later from the Profile options page.
- All static coaching/session/recovery text and AI output instructions now use
  the profile language.
- Existing profiles without the setting continue to follow HA UI language for
  backward compatibility.
- Added translated field labels and language regression tests.

## 2026.8.0-beta.12

### Visual workout lifecycle feedback

- Start Workout now gives green/temporary or persistent-red light feedback based
  on whether usable live sensor data is already available.
- Waiting-for-live red persists until the first valid live data arrives; the
  subsequent green cue restores the exact pre-wait light state.
- Added three-second recovery-stage cues: red at stop, orange at 10 s, yellow at
  30 s, blue at 60 s and green at 120 s.
- Lifecycle cues use the existing room/configured color-capable light resolver.
- Lifecycle cues suspend intensity pulses to protect the original-state snapshot,
  then intensity feedback resumes after the start-green cue.
- Light cues are asynchronous and cannot delay HR-recovery measurement timing.
- Added lifecycle-light regression tests.

## 2026.8.0-beta.11

### Spoken workout lifecycle and HR-recovery guidance

- Added AI/static localized announcements when Start Workout is pressed.
- Distinguishes immediately available live data from waiting-for-sensor state.
- Announces the actual live sensor names when timing begins.
- Added spoken post-exercise HR-recovery guidance at 10/30/60/120 seconds with
  remaining time.
- Missing HR at a recovery checkpoint is reported truthfully rather than marked
  collected.
- Recovery speech/AI is asynchronous and cannot delay measurement checkpoints.
- Final workout evaluation/summary is deferred until HR recovery finishes so it
  can include the collected recovery values.
- Added localized deterministic guidance for all currently shipped UI languages.
- Added lifecycle/recovery regression tests.

## 2026.8.0-beta.10

### Resilient workout-provider fallback

- Known providers now use explicit adapter → scoped generic fallback → safe ignore.
- Generic fallback runs only for the affected provider/device.
- Working explicit adapters are never parsed twice.
- Adapter exceptions are isolated and exposed in diagnostics.
- Unknown/future integrations continue through the generic adapter.
- Added adapter status/count/error diagnostics and regression tests.
- Retains beta.9 startup/replay protection and beta.8 Dependabot automation.

## 2026.8.0-beta.9

### Workout announcement reliability

- Startup-restored provider workouts are silent historical baseline.
- Added a provider restoration window before external announcements are armed.
- Added debounce for multi-entity provider workout updates.
- AI/TTS/notifications require substantive completed-workout information.
- The AI workout prompt independently rejects incomplete workout data.
- Added regression tests for restart and incomplete-provider behavior.
- Includes beta.8 Dependabot auto-merge workflow.

## 2026.8.0-beta.8

### Safe Dependabot auto-merge

- Added a Dependabot-only auto-merge workflow.
- Dependabot PRs use squash auto-merge and never administrator bypass.
- Normal contributor PRs are excluded by an explicit author check.
- Added regression coverage for the workflow's bot-only guard and permissions.
- Documented the required GitHub auto-merge and branch-status-check settings.
- Runtime Fitness behavior is unchanged from beta.7.

## 2026.8.0-beta.7

### Maintainable workout-provider adapters

- Replaced provider-specific workout heuristics with a registry-based adapter
  architecture plus a generic fallback.
- Added explicit Garmin Connect, Strava, Polar, Hevy, Peloton and Oura adapters.
- Polar Last exercise now maps its documented AccessLink attributes, including
  provider-preserved Running Index and training load.
- Known providers are owned by exactly one explicit adapter; unknown/future
  integrations continue through the generic adapter.
- Added ISO-8601 duration parsing and shared distance/speed normalization helpers
  for provider contracts.
- Added adapter-registry and cross-provider enrichment regression tests.

## 2026.8.0-beta.6

### Tests and HACS release engineering

- Added pytest coverage for heart-rate calculations, live intensity boundaries,
  VO₂max/reference calculations, Banister TRIMP, mechanical work, HRR intensity
  time, aerobic efficiency/decoupling and coefficient of variation.
- Added unit-normalization tests for weight, height, HR, power, pace, speed,
  distance, altitude and cadence.
- Added workout identity/merge regression tests covering Garmin+Strava
  enrichment, conflicting workouts, sparse providers and complete-link grouping.
- Added repository metadata/JSON/brand structure tests.
- Added GitHub Actions for pytest, HACS validation and hassfest.
- Added Dependabot, CODEOWNERS, issue forms, contribution guidelines and a release
  checklist.
- Runtime Fitness behavior is unchanged from beta.5.

## 2026.8.0-beta.5

### Branding polish

- Rebuilt the Fitness logo with generous safe padding so GitHub does not crop it.
- Rebuilt the README overview entirely with real rendered typography for sharp, readable text.
- Rebuilt the GitHub social preview with real typography.
- Refreshed Home Assistant/HACS icon assets from the new graphical mark.
- Runtime integration behavior is unchanged from beta.4.

## 2026.8.0-beta.4

### Documentation and branding

- Added Home Assistant local brand assets under `custom_components/fitness/brand/`.
- Added HACS repository brand assets under `brand/`.
- Added GitHub avatar, social-preview, logo and overview assets.
- Replaced the development-history-style README with user documentation focused on
  setup, live workouts, workout merging, calculated sensors, equations,
  longitudinal evaluation, AI/coaching, scientific basis and limitations.
- Added direct research references for the deterministic physiological methods.

## 2026.8.0-beta.3

### Personal historical workout comparison

- Live-generated Fitness workouts now compare against up to 20 similar prior
  Fitness workouts from the previous 90 days.
- Historical comparison never overwrites raw workout measurements.
- Added aerobic efficiency, decoupling, average HR, average power/speed and
  TRIMP comparisons against the user's own comparable-workout baseline.
- Added deterministic lower/similar/higher personal load context.
- Added a concise personal-context workout summary.
- Workout AI evaluation now explicitly receives this comparable-workout context.
- New comparison entities use the existing lazy-creation lifecycle.


## 2026.8.0-beta.2

### Safer workout merging

- Replaced the previous `start within 5 minutes + compatible sport` duplicate
  matcher with conservative multi-field matching.
- Added hard conflict checks for sport, duration, distance and explicit end time.
- Requires progressively stronger supporting evidence as provider start times
  differ.
- Changed workout grouping from transitive `any()` matching to complete-link
  `all()` matching to prevent nearby separate workouts from being chained into
  one merged activity.
- Reduced the diagnostic workout identity bucket from five minutes to one minute.
- Complementary fields and provider provenance are still merged/preserved for
  records identified as the same workout.


## 2026.8.0-beta.1

First public beta of Fitness for Home Assistant.

### Live workouts

- Arms a workout first and starts the session timer only after valid live exercise
  data arrives.
- Live entities are unavailable outside an active workout so stale sensor values are
  not presented as current exercise data.
- Supports live heart rate, power, cadence, speed, distance and altitude when those
  capabilities are available.
- Adds HRmax percentage, heart-rate reserve percentage/intensity, threshold-relative
  metrics, power-to-weight, pace and other prerequisite-driven live calculations.
- Adds within-session averages/maxima, Banister TRIMP, mechanical work, intensity
  duration, aerobic efficiency and aerobic decoupling when calculable.
- Measures post-exercise heart-rate recovery at 10, 30, 60 and 120 seconds when
  suitable HR data remains available.

### Workouts and evaluation

- Normalizes completed workouts from selected workout-provider devices.
- Merges matching representations of the same workout instead of discarding
  complementary Garmin/Strava/provider data.
- Preserves provider provenance and mismatched provider values in attributes.
- Uses Fitness workout history for 7/28/42-day training-load context and longer-term
  HRR/efficiency/decoupling summaries when enough history exists.
- Uses Home Assistant Recorder long-term statistics for relevant configured/provider
  entities when available.
- Optional AI Task evaluation uses deterministic and longitudinal context rather than
  relying only on the latest raw values.

### Entity lifecycle

- Optional entities are created lazily after their first valid calculation.
- Once created, entities remain registered permanently and become unavailable when
  prerequisites temporarily disappear.
- Existing entity-registry entries from older builds are preserved during upgrade.

### Coaching and feedback

- Optional room-aware color-light feedback, TTS and notifications.
- Runtime Workout room selector follows Home Assistant areas.
- Intensity transitions have a five-second minimum transition guard.
- Light feedback pulses five times and restores the exact pre-feedback light state.
- ANT+ Capture switches are snapshotted before Fitness starts a workout: switches
  already on stay on after the workout; switches Fitness enabled are restored to
  their original off state after the workout/recovery phase.

### Localization

- Ships translations for English, Greek, German, French, Spanish, Italian,
  Portuguese, Dutch, Polish, Russian, Ukrainian, Turkish, Chinese, Japanese and
  Korean.

### Beta note

This is a public beta. Calculations and entity/configuration structure may still be
refined before the first stable release.
