# Changelog

## Unreleased

- Added direct local CYCPLUS M1 workout-archive support: verified Bluetooth discovery and profile assignment, automatic connect/reconnect, CRC-validated FIT import into canonical calendars, persistent file-boundary recovery for interrupted transfers, a manual retry button, translated sync entities in all 15 bundled languages, and Home Assistant device identity/storage/battery diagnostics.
- Fixed CYCPLUS M1 browser/local duplicate devices by correlating the exact advertised device number, retaining the autonomous Home Assistant Bluetooth route, keeping FIT recording identity separate from GATT DeviceInfo, reading the standard battery characteristic directly, and discovering live cadence/power/speed/distance capabilities from the connected GATT surface and real decoded samples.
- Hardened large CYCPLUS M1 archive imports after a 183-file backlog exposed a multi-gigabyte profile-store failure mode: automatic sync now downloads/imports at most three files per connection, resumes remaining batches after a cooling interval, commits each profile history once per batch, bounds FIT file/record/provenance memory, compacts legacy oversized workout payloads once on upgrade, cancels when unassigned, and time-bounds every M1/Bluetooth shutdown cleanup operation.
- Completed a general stall-safety audit: remote ANT+ packet batches now share one bounded assignment worker per profile/gateway; profile, topology, TV and M1 stores serialize writes; live samples, route decoding, gateway/client state, topology metadata and proxy frames have hard memory limits; optional services/providers/network calls have deadlines; and hub/profile unload cancels and awaits every owned monitor, transfer and control task under an overall timeout.
- Completed a security audit: Fitness TV navigation now accepts only same-origin internal routes or credential-free HTTP(S) links; local Cast fallback origins must match the authenticated browser client; remote BLE identity and ANT+ adapter fields are server-owned/allowlisted; Music Assistant player IDs are bound to the issuing profile and server; nested WebSocket inputs are bounded; and public opaque audio relays reject private/local destinations, validate every redirect/range/header, hide provider exception details and enforce global concurrency ceilings.
- Completed a performance audit: CYCPLUS catalogue parsing is a single capped scan, FIT session lookup uses a timestamp index with session/record/storage ceilings, all M1 archive syncs are globally serialized, music searches/resolutions and public relays are admission-controlled, the public Cast module is cached in memory, and profile cards/ambient TV styling skip unrelated Home Assistant state updates.
- Completed the Fitness overview/profile-management pass: backend-only profiles are shown with configure, assignment and deletion controls; merged backend/Fitness TV profiles can now be removed completely; the hidden Cast overview remains available as a subview.
- Fixed profile-scoped localization and controls, including translated backend settings, a Main menu icon, persistent per-profile music-adapter removal and adaptive button labels with a readable minimum size.
- Fixed live-workout visibility for profiles whose accepted sensors are assigned before live metric entities exist, and preserved local BLE availability when an equivalent browser Bluetooth identity is merged or disconnected.
- Added distinct self-running animations for the sleep score, recovery progress and training-readiness indicators.
- Audited laptop, TV and phone layouts and hardened responsive toolbars, profile/access actions, music-adapter controls, modal viewport/safe-area sizing, keyboard focus and mobile touch targets without changing the established desktop card grid or TV remote order.
- Completed a 15-language audit across Home Assistant setup/options/services, dashboard and card-picker controls, compound entity names, music-provider metadata and scientific formula details. Profile/account language is authoritative, catalogs enforce exact key and placeholder parity, and raw backend exception text is no longer exposed as UI copy.

## 2026.8.01a01

First public alpha release of HA-Fitness. This release is intentionally marked alpha while the expanded Fitness TV, multi-user, Cast, live-sensor, audio/TTS and remote-access workflows receive wider real-world testing.

- Added profile-persistent music search result-type filters for Tracks, Albums, Playlists, Artists, Radio, Podcasts and Audiobooks. Music Assistant collection results are now native playable queue targets, and result groups are interleaved so tracks cannot consume the entire Fitness search limit before album/playlist matches appear.
### Internal development checkpoint: 2026.8.10

Release tags and `manifest.json` use the same canonical version. Alpha prereleases use `YYYY.M.RRaXX` (for example `2026.8.01a01`), beta prereleases use `YYYY.M.RR-betaXX`, and stable releases use `YYYY.M.RR`. Frontend cache revisions are independent implementation revisions and may retain an `unreleased-N` identifier until deliberately rebased.

- Reworked Fitness TV music-provider search around configured Music Assistant provider instances. The single Music Assistant adapter now exposes its configured music sources as selectable search scopes, supports one/many/all source selection, and hides provider/account instances that are already playing elsewhere when Music Assistant or Home Assistant exposes that active session.
- Added native Music Assistant playback inside Fitness TV using the official Sendspin browser client through a short-lived same-origin Home Assistant WebSocket relay. Supported MA track/radio/podcast/audiobook results now play on the current Fitness TV audio owner and participate in the same play/pause state and TTS duck/restore path as other providers instead of opening the Music Assistant web UI.
- Moved yt-dlp enablement out of general Fitness TV settings and into **Music Providers**. Enabling it requires the legal acknowledgement there; the backend option is retained only as the persisted compatibility setting.
- Fixed Fitness TV search UX so the compact **Searching music…** indicator lives immediately below the search field and is visible only during a real search request. Provider/account rows that are unavailable because they are already active elsewhere are not offered as selectable search scopes.
- Standardized Fitness TV modal behavior so headers remain sticky, action bars remain reachable and menu bodies scroll independently in both the profile dashboard and administrator setup surfaces. Frontend cache revision is now `unreleased-61`.

- Added server-enforced Fitness TV account roles: a local Fitness administrator, one-profile local users and one-profile remote users. Users cannot self-enroll or enumerate other Fitness profiles; the same authorization boundary now protects dashboard data, workout controls, music, Cast/TTS and remote BLE/ANT+ gateway traffic. Remote accounts use administrator-managed per-user slugs under one wildcard DNS/TLS base domain, with exact-subdomain session validation and immediate Fitness revocation when the account is removed.
- Fixed browser-local Cast authentication after the receiver reported **The supplied authentication is invalid**. Fitness now mirrors Home Assistant's browser Web Sender flow: it reuses the refresh token backing the currently authenticated HA WebSocket session together with that token's matching OAuth client ID, instead of minting a separate admin/system Cast credential. The Cast receiver therefore keeps the current HA user's permissions, and Fitness never revokes the user's browser refresh token when casting stops. Legacy temporary Fitness Cast tokens are cleaned up safely.
- Fixed browser-local Cast media handoff: an authenticated local Cast session now becomes the Fitness TV audio owner even though it has no Home Assistant `media_player` entity. Music, TTS, play/pause/seek and future media commands route to the Cast receiver while the initiating laptop/phone becomes controller-only; stopping the Google Cast session releases that ownership and pauses the shared media state. The toolbar and Cast dialog Stop buttons now follow the real local Google Cast session/receiver state.
- Added authenticated Fitness Remote Gateway protocol v1 for athletes training on another network: remote browser/native clients can publish raw standard BLE fitness characteristic frames or ANT+ extended channel packets into the existing HA-Fitness decoders while automatically assigning the resulting physical sensor to the selected Fitness profile.
- Added browser Web Bluetooth pairing/reconnect for Heart Rate, Cycling Power, CSC, RSC and FTMS sensors plus experimental WebUSB ANT+ scanning for Dynastream ANTUSB2/ANTUSB-m sticks. Radio permissions stay local to the athlete's browser; future Android/iOS/Windows senders can reuse the same backend packet contract.
- Added browser-local Google Cast to Fitness TV. A remote laptop/Android browser can choose a Cast display on its own local Wi-Fi independently of HA's server-side Cast discovery. The standard HA Cast receiver authenticates with the already logged-in browser user's HA session credentials and an externally reachable HTTPS HA URL.
- Split the Cast picker into **Local network TV** and **Home Assistant network devices**, added a Remote Sensors toolbar/dialog, localized its primary UI in English/Greek/German, and bumped the frontend resource to `unreleased-59`.

- Fixed Music Assistant provider setup routing for Home Assistant Container: Fitness now opens the selected Music Assistant server's own **Music Sources** page using the URL stored by the HA Music Assistant config entry. Existing MA provider instances deep-link to their exact edit page when the current MA frontend exposes one; unconfigured sources fall back to the Music Sources page because MA does not currently expose a URL route that preselects a new provider setup flow.
- Hardened Fitness TV route-away playback: leaving a Fitness profile now snapshots the real position, publishes the shared session as paused, destroys the detached browser player, and re-resolves/resumes from the saved position when the user returns and presses Play. This applies to direct/HA/yt-dlp HTML audio and carries resume positions into YouTube and SoundCloud embeds where those APIs allow seeking.
- Modernized Fitness TV surfaces with larger consistent corner radii, subtle borders/shadows, blurred modal backdrops, rounded menus/inputs/provider rows and shared rounded styling for mounted dashboard cards.
- Split Fitness TV music into one maintainable Python module per adapter plus a small registry/facade. Active adapter lists now contain only installed/usable music adapters; generic Home Assistant sources such as Camera, Cloud, Drive or unrelated media integrations are no longer mistaken for music adapters.
- Music Assistant is exposed as one aggregate Fitness adapter regardless of how many provider accounts/sources it contains. A separate Add music provider catalogue offers Music Assistant source setup shortcuts for Spotify, Apple Music, Tidal, Qobuz, Deezer, SoundCloud, YouTube Music, Bandcamp, Jellyfin, Plex, Subsonic and Audible without turning those MA sources into duplicate Fitness adapters. Native Home Assistant Spotify is a separate adapter only when an actual Spotify config entry is installed.
- Fitness TV music preferences are profile-scoped: enabled adapters, adapter account/server choice metadata and configurable search result count (10–100, default 50) are persisted under the Fitness TV profile store. Third-party credentials/tokens remain owned by Home Assistant or Music Assistant.
- Search music now shows only installed, enabled, searchable adapters, keeps a visible working state, and can search one/many/all selected adapters. Normal YouTube/YouTube Music links remain on the normal YouTube player; yt-dlp remains its own opt-in adapter. Seek verification/synchronization remains enforced for HTML audio, proxied yt-dlp audio, YouTube and SoundCloud.
- Added a Fitness TV fullscreen control and hardened both music/provider and profile-settings dialogs so their bodies scroll inside the viewport while action controls remain reachable.
- Strengthened the yt-dlp acknowledgement around user responsibility, applicable law/service terms/content rights, penalties/consequences and non-excludable legal rights/liabilities.

- Added native HealthSync / Apple Health sleep and completed-workout adapters. Sleep uses the upstream Sleep last night stage attributes plus full onset/wake timestamps; dashboard routes remain source-owned and synthetic sleep score stays an inline fallback only when HealthSync has no score entity.
- Added HealthSync recent-workout-slot parsing, Apple Health workout-type normalization (including functional/traditional strength and HIIT), runtime listener recognition for dynamically named workout slots, and permanent workout-history import through `healthsync.get_readings` bounded by the Fitness retention window and parsed off Home Assistant's event loop.

- Made unaccepted Bluetooth discovery sensors effectively zero-background after their first stable identity registration: recurring advertisements now refresh only in-memory last-seen/RSSI/source/availability and return before runtime registration, diagnostics, vendor decoding, passive telemetry, storage, structure notifications or config-flow work.
- Dynamic Bluetooth advertisement payload diagnostics and proprietary passive decoding now begin only after the user accepts the sensor; discovery itself retains only stable identity/capability facts.

- Made native sensor deletion UI-safe: deletion now revokes the sensor in memory and returns without synchronously persisting the sensor store or rescanning entity platforms.
- Deferred profile/subentry/entity cleanup until after the Home Assistant device-delete transaction and added a short endpoint rediscovery quarantine so active ANT+/BLE broadcasts cannot immediately rebuild discovery while the delete UI is closing.

- Removed repeated ANT capability-model work from high-rate telemetry: repeated pages no longer recompute capability snapshots; capability resolution now runs only for new capability evidence/command status.
- Collapsed ANT metric notifications to one newest-device callback per RF packet instead of one callback per changed metric, eliminating multi-metric scheduler/GIL amplification.
- Raw ANT protocol-event handling now rejects ordinary telemetry profiles before capability analysis.

- Removed per-packet remote ANT+ work from Home Assistant's MainThread. HA event callbacks now hand one bounded packet batch to the ANT worker and return; packet copying, event classification, page/key parsing, diagnostics and telemetry coalescing all run off-loop.
- Ordinary remote RF traffic no longer confirms or mutates adapter Capture state. Capture state is updated only by explicit gateway hello/status/control confirmation events.

- Prevented remote ANT+ adapter heartbeat/presence messages from re-entering Home Assistant device/entity registries when adapter identity is unchanged; registry materialization is now identity-gated.
- ANT+ provider startup and adapter callbacks now respect the user's persisted Capture state instead of forcing Capture ON.

- Converted radio-driven topology persistence, DeviceInfo enrichment and entity materialization from periodic throttles into true quiet-period debounces. Continuous ANT+ traffic can no longer run registry/storage work every ~0.75 s.
- Reduced accepted ANT+ event-loop mailbox delivery from 4 Hz to 2 Hz and physical sensor HA state publication from 2 Hz to 1 Hz; workout live sampling remains on its independent path.
- Idle radio packets now return before scanning Fitness profiles for workout ownership when no armed/active/recovery session exists.

- Prevented premature generic ANT+ discovery: ANT-only endpoints such as a bare `Power Meter` stay provisional until catalog/common-page identity is strong enough to merge or safely create one physical device.
- Fixed accepted-BLE + provisional-ANT merge overhead: registry cleanup now runs only when the discarded side actually had an accepted HA device, and accepted-registry cleanup is delayed out of the ANT identity burst.
- Reduced radio-driven topology pressure by debouncing structure materialization to 750 ms and removing global runtime fan-out from ordinary identity/capability enrichment.

- Restored Home Assistant event-loop safety for adapter-owned ANT receiver activation/deactivation: synchronous USB receiver enable/disable calls now run through `async_add_executor_job` while the adapter switch remains the sole lifecycle control.

- Simplified native live transport lifecycle: adapter `Activate` switches are now the only module controls. Workouts never start/stop ANT+/Bluetooth capture.
- Removed all ANT receiver capture buttons/state entities and all manual Bluetooth GATT connect/disconnect buttons. Old entities are pruned automatically.
- Bluetooth GATT is now fully automatic: after a physical sensor is exclusively claimed, Fitness connects GATT only when fresh ANT+ is unavailable, disconnects when ANT+ returns, and disconnects when the owning session no longer needs it.
- ANT receiver paths stay active for the lifetime of the enabled ANT+ provider and are disabled only when the ANT+ adapter module is switched off/unloaded.

- Removed Bluetooth-manager/proxy resolution from physical sensor GATT button availability. Opening a device page now evaluates only cached connectability; BLE-device resolution happens only during an actual GATT connection attempt.
- Removed per-sensor Start/Stop Capture and Capture Active entities. Adapter enablement is again the transport/module control boundary; obsolete capture entities are pruned from the entity registry.
- Tightened adaptive dashboard visibility: Training Load requires a reliable personal baseline and sufficient recent workout evidence, and baseline-comparison elements require enough comparable workouts before rendering.
- Fixed Average HR vs personal baseline rendering to use the stable comparison metric key, show explicit baseline/current/difference numbers, and mark the numeric baseline on the heat gauge.
- Added an HRV-vs-28-day-baseline heat bar to Recovery when latest HRV and a meaningful baseline are both available.
- Bumped the single Fitness dashboard resource revision to `2026.8.11.2`.

- Replaced remaining native sensor vendor-specific decoder branches with a data-driven vendor/product decoder registry. Product matching, company IDs and proprietary byte layouts now live in `live/device_catalog.json`; `vendor_registry.py` is generic and validates catalog consistency.
- Removed native ANT+/BLE vendor-name tables and vendor-specific sport inference. ANT manufacturer names and proprietary BLE values now resolve through the catalog; the native `live/` Python tree has regression protection against device/vendor literals.

- Fixed Home Assistant 2026.8 DeviceInfo validation for native fitness sensors/adapters by using only valid primary-device fields.
- Disabled adapters now remain disabled across restart/presence changes; provider modules fully unload and volatile endpoint/live-source state is invalidated.
- Moved Bluetooth adapter-level `Capture active` to per-physical-sensor ANT+/Bluetooth capture-state entities.
- Training-load/evaluation UI now hides until real workout/load/adaptation evidence exists.
- Average-HR-vs-baseline now shows explicit baseline/current/difference values and a full heat-band gauge around the personal baseline.

### Internal development checkpoint: 2026.8.11

- Expanded Fitness TV now-playing state with artwork, artist/title/details, elapsed/remaining time and seekable progress shared across dashboard clients; SoundCloud, yt-dlp YouTube, Home Assistant media and direct audio expose the richest metadata available from each source.
- Fixed Fitness TV settings dialogs to use a bounded scrollable body with a sticky Save action.
- Replaced the incompatible Deno PyPI requirement with a Home-Assistant-managed pinned Node.js wheel fallback for yt-dlp YouTube extraction; the Node.js distribution provides Alpine/musl and glibc wheels, while existing host Deno/Node/QuickJS/Bun runtimes remain supported.
- Refined Fitness TV setup/navigation, compatible manual profile sensors, ambient fitness/intensity backgrounds, Cast wake-lock handling, and country-filtered Radio Browser browsing.
- Added opt-in native yt-dlp YouTube search/playback for Fitness TV: server-side search returns up to 10 selectable results, resolved audio is proxied through Home Assistant without forwarding account cookies, and Spotify links now fail explicitly instead of reporting false playback.
- Radio Browser country choices are now sorted alphabetically by their localized display names rather than ISO country code order.

### Runtime safety and shared-sensor refinements

- Made Local Sensor discovery sticky after the first fresh ANT+/BLE observation. Radio silence now changes only runtime availability; it never aborts/recreates Home Assistant discovery flows. The confirmed discovery state survives restart until setup or explicit deletion/reassignment.
- Limited the Workout owner select to genuinely shared sensors (>1 assigned profile) and made it available only during an overlapping live session involving at least two assigned profiles. Session start/finish refreshes this control at control-plane frequency only.
- Hardened the optional sensor recognition catalog so malformed/missing JSON can never abort Fitness startup and catalog I/O is no longer performed from Bluetooth advertisement callbacks.
- Added exercise-owned temporary per-sensor capture policy: ANT+ is enabled for the workout, BLE/GATT is enabled only when ANT+ becomes unavailable, and the user's pre-workout capture positions are restored when no overlapping Fitness session remains.
- Added explicit mid-workout physical-sensor owner transfer. The current owner must be paused; the target must have the sensor assigned and be armed/active. Live values and transport ownership are cleared before the handoff so measurements cannot feed two profiles.
- Moved workout retention into the Workout configuration section and added translations.
- Removing a Fitness user config entry now removes its complete Fitness-owned persistent profile store.
- Workout calendars use `<profile name> <translated Workouts>`.


## 2026.8.11 — Unified workout calendar & historical reconciliation

- Added exclusive physical-sensor workout ownership across shared Fitness profiles: a sensor may be assigned to many profiles but feeds only one active workout owner, with deterministic oldest-session claiming.
- Sensor locks now persist until every overlapping armed/active/recovery session is finished, preventing a still-worn sensor from being inherited by another ongoing workout after the original owner stops.
- Added Local Sensors → Sensor assignments so accepted native sensors can be reassigned to any combination of Fitness profiles after setup.
- ANT↔Bluetooth transport handover now operates strictly underneath the physical workout lock; first ANT takeover packets no longer hide the previous BLE state before GATT disconnect reconciliation.
- Physical ANT/BLE identity merges now migrate workout locks, measurement provenance and per-profile transport state safely to the canonical sensor ID.
- Added retry/claim guards so failed BLE fallback cannot create phantom transport ownership or retry at advertisement frequency.

- Reworked native ANT+/Bluetooth physical-sensor identity into a canonical, data-driven model. Raw numeric ANT model/manufacturer IDs remain diagnostics and can no longer replace a meaningful HA device name/model; standard ANT common pages and Bluetooth Device Information enrich manufacturer, model, serial, hardware and software/firmware information in-place.
- Added an expandable `live/device_catalog.json` for manufacturer/product/profile recognition instead of runtime vendor exceptions. Cross-transport auto-merge remains conservative: serial identity or an explicit catalog product-family rule is required.
- Added merged diagnostic entities for decoded ANT+ metadata/advanced metrics and BLE advertisement/GATT information. Equal facts from ANT+/BLE share one canonical entity with per-transport source values; battery is one merged passive entity. High-frequency/advanced protocol diagnostics are disabled by default.
- Added physical-sensor protocol Event entities for positively detected ANT+ event capabilities, plus manual Bluetooth GATT connect/disconnect buttons. GATT is automatically used for assigned workouts only when ANT+ data is not fresh, is shared safely between multiple Fitness profiles, and is disconnected as soon as fresh ANT+ data takes ownership.
- Hardened native radio hot paths with per-sensor/per-metric dirty notifications, unchanged-value suppression, coalesced workout-manager processing and a fast repeated-advertisement path so radio traffic cannot fan out into writes for every physical Fitness entity.
- Hardened BLE discovery/device materialization further: volatile manufacturer/service payload bytes, RSSI, scanner source and availability no longer participate in topology identity; raw advertisement diagnostics are sampled at 10-second intervals, HA-side Bluetooth callbacks are service-filtered, device-registry updates are identity-signature cached, and entity materialization after discovery acceptance is deferred/coalesced off the config-flow response path.
- Added stale endpoint expiry and bounded diagnostic states: silent radios can become unavailable without deleting topology, active GATT connections stay available, long protocol diagnostics are moved to attributes instead of exceeding Home Assistant's 255-character state limit, and the enabled Active transport entity no longer duplicates the complete GATT/ANT diagnostic surface into Recorder.
- Control capabilities advertised/confirmed by ANT+/BLE are retained as diagnostics, but Fitness does not fabricate writable protocol payloads. A control becomes actionable only when a verified encoder/range/acknowledgement contract is implemented.
- Serialized Bluetooth GATT connect/disconnect per canonical physical sensor so multiple Fitness profiles cannot race duplicate connections; failed partial connections now clean up ownership/client state before retry.
- Reduced enabled physical-sensor state payloads further: normal advertisements no longer resolve Device Registry identity unless stable topology actually changes, and the Available entity exposes only compact canonical status rather than duplicating full transport/GATT diagnostics.
- Fixed Home Assistant startup stalls caused by Fitness synchronously rebuilding provider/workout/recovery/evaluation state while entity platforms were being added. Profile startup now restores persisted Fitness state only; provider discovery/listener registration is deferred until `EVENT_HOMEASSISTANT_STARTED`.
- Added cached canonical latest-workout, readiness and recovery snapshots so dozens of Fitness entities no longer rescan provider registries or rebuild longitudinal summaries independently during state writes.
- Fitness Evaluation and readiness/recovery entity properties now remain unavailable during HA bootstrap instead of triggering expensive calculations on the main event loop; they refresh immediately after post-start initialization.
- Added regression tests enforcing non-blocking startup architecture and cache-backed workout reads.

- Refined the Recovery dashboard card by integrating Training Readiness into the next-workout recovery panel and reducing visual height.
- Training Readiness now models elapsed training recovery continuously between recovery anchors instead of changing only at fixed time thresholds.
- Added numeric endpoints/current markers to workout-baseline, VO₂max and training-load gauges; heart-rate baseline deviation now uses distance-from-baseline status colors.
- Fixed Latest Sleep total duration so Awake time is excluded from actual sleep while remaining visible in stage composition.


- Added configurable canonical workout retention per Fitness profile. The default is 3650 days (10 years); `0` keeps workouts indefinitely. Automatic retention is reversible in the sense that increasing it can allow still-exposed provider history to be imported again.
- Added the `fitness.delete_workouts_before` action for explicit bulk cleanup by age. It stores one persistent deletion cutoff so old Garmin/Strava/Recorder history cannot repopulate deliberately removed workouts.
2026.8.11 adds a canonical workout calendar and extends workout reconciliation beyond the newest provider activity.

### Highlights

- Added one Home Assistant **Workout calendar** per Fitness profile. Each event represents one canonical physical workout with its actual start/end time.
- Added historical workout ingestion from currently exposed provider history, supported provider-specific history APIs, and selected completed-workout entities in Home Assistant Recorder.
- Historical, local and newly synchronized provider workouts all use the same conservative `merged_workouts()` reconciliation path. Later Garmin/Strava/Hevy/etc. data enriches an existing workout instead of being ignored or creating a duplicate.
- Local completed workouts now enter the same canonical history path as provider workouts.
- Replaced the fixed workout-count cap with configurable canonical workout retention. The default is **3650 days (10 years)** and `0` means unlimited.
- Added Home Assistant calendar deletion support. Deleting an event removes the canonical Fitness workout and stores a compact tombstone so provider/history synchronization cannot automatically resurrect it.
- Added normalized workout start latitude/longitude fields and calendar `location` output when explicit start GPS coordinates are available.
- Added compact localized calendar summaries for all 15 languages already supported by Fitness. Full structured workout measurements/calculations stay in Fitness history/dashboard because Home Assistant `CalendarEvent` does not expose arbitrary rendered per-event attributes.
- Added regression tests and dedicated documentation for calendar identity, GPS start location, deletion persistence, localization, historical reconciliation and retention.

### Storage behavior

Workout calendar events are projections of Fitness canonical workout storage; they are not maintained in a second calendar database. Canonical retention is configured per profile (default 3650 days; `0` unlimited). Individual deleted-workout tombstones are persisted separately (up to 1,000), while bulk deletion uses one persistent cutoff timestamp so explicit user cleanup survives restart and provider re-sync.

---

## 2026.8.10 — Recovery, readiness & personal context

2026.8.10 turns the beta recovery work into a cohesive release focused on **personal baselines, explainable recovery and trustworthy history**.

### Highlights

- Added **Ready for the next workout**, an evidence-informed recovery-time estimate with remaining time, approximate ready-at time, recovery progress, confidence, limiting factors, uncertainty range and physiological recovery signals.
- Added a **personal HRV baseline** using recent rolling HRV against preceding personal history, while keeping the latest-night deviation separately inspectable.
- Improved **Training Readiness** with localized, auditable component evidence and clearer presentation alongside — but not conflated with — the recovery-time estimate.
- Added **training adaptation status** using recent training exposure together with longer-term personal load history, VO2max trend, HRV/RHR context and readiness; immature histories return insufficient data instead of unstable load classifications.
- Hardened **7-day sleep deficit** so one validated main sleep is counted per local wake date and duplicate provider synchronization cannot inflate the result.
- Improved **workout reconciliation** so stale live/provider duplicates are re-clustered before they can inflate workout counts, training load or evaluation.
- Improved completed-workout RPE handling, live/provider workout merging, GPS-route ownership, live workout presentation and HR-recovery feedback.
- Reworked the **Recovery & Sleep dashboard** so readiness, time-to-next-workout, recovery progress/signals and last-sleep information form one clear responsive story with state-aware colors and localized labels.
- Expanded localization and regression coverage across the supported languages and recovery/evaluation UI.

### Scientific and safety boundary

Fitness remains a training/wellness overview, not a medical device or health advisor. Recovery time, Training Readiness and training-adaptation states are transparent Fitness-owned interpretations informed by the methods and literature documented in [Science & methods](docs/SCIENCE.md); they are not diagnoses or guarantees of physiological recovery.

---

## 2026.8.10-beta2

- Added Fitness-owned estimated recovery time after the latest canonical workout, combining workout dose with personal readiness/HRV/RHR/HRR evidence and exposing confidence/method details.
- Training adaptation now requires a mature 28-day personal load baseline before classifying high/excessive load; sparse histories report insufficient data instead of unstable ratios.
- Re-cluster stored workouts on read so stale live/provider duplicates cannot inflate 7/28-day workout counts or training load.
- Integrated training adaptation into the Training Load card and added estimated recovery time to the Recovery card.

- Fixed Training Readiness failing to materialize because its localized readiness-attribute helper was missing. Readiness now exposes stable machine-readable attributes plus a localized display level across all 15 supported languages.
- Hardened 7-day sleep-deficit history: long-term calculations now count one main validated sleep per local wake date, preventing late provider synchronization or duplicate nightly records from inflating the deficit. The entity exposes a per-night deficit breakdown and duplicate-record diagnostics for auditing.
- Added a Fitness-owned personal HRV baseline. The newest night is excluded from its own reference baseline; recent HRV uses a 7-night rolling mean when enough observations exist and is compared with the preceding 28-day personal baseline (minimum 14 prior HRV nights). The latest-night deviation remains exposed separately.
- Training Readiness autonomic recovery now consumes the less noisy rolling HRV-vs-personal-baseline signal when available, with transparent baseline/sample attributes.


## 2026.8.10-beta1

- Fixed Sleep as Android completion latency: a STOPPED event now materializes the completed sleep immediately from the live tracking/phase event timeline instead of waiting for Recorder to commit. Recorder reconstruction remains the restart/history source and now retries delayed commits. Stale Sleep as Android aggregate values (such as yesterday's sleep score) are no longer merged into a newly completed night unless they were refreshed near that sleep's end.

- Workout-device cleanup is now capability-aware: provider placeholder zeroes for unsupported movement/mechanical metrics are treated as missing, stale optional Workout registry entities are pruned on setup, and the old duplicate single-source entity is removed in favor of the merged source list.
- Workout highlights now render the workout name as its own safely wrapping heading and suppress irrelevant zero/unknown/unavailable tiles so translated or long titles cannot escape their card.
- RPE provider provenance is now adapter-aware. Fitness uses a provider-supplied session RPE as the initial completed-workout value when available, while keeping the Workout-card control editable; user overrides preserve the provider baseline and immediately recalculate session-RPE load and long-term RPE statistics.
- Added documented session-RPE handling for Garmin self-evaluation data and Polar Training Load Pro. Garmin 1-10/self-evaluation fields and common `directWorkoutRpe` representations are normalized conservatively; Polar RPE uses the explicit value when available or derives it from documented Perceived Load = RPE × duration. Algorithmic WHOOP Strain, Suunto 1-5 feeling, and Hevy per-set RPE are deliberately not misclassified as session RPE.
- Fixed live/provider workout reconciliation: live-capture sport is provisional, authoritative provider sport/name can replace it after sync, while Fitness-owned live metrics/HRR/RPE and provider metrics are merged into the same physical workout using conservative time/duration/end matching.
- Live capture no longer infers cycling from generic cadence or heart-rate-only sources; running/cycling names require strong source evidence, otherwise the session remains a generic Workout until a provider supplies the sport.
- Workout GPS routes are now tied to the current merged workout identity, preventing a previous provider route from appearing on a newer non-GPS workout. The Workout card always retains normalized workout highlights even when a valid route exists.
- The Live Workout card now renders all currently available non-config entities belonging to the Live device, while hiding unknown/unavailable values and keeping completed-workout RPE on the Workout card.
- Updated optical HR-zone feedback to the requested six-color scale: below Zone 1 purple, Zone 1 blue, Zone 2 green, Zone 3 yellow, Zone 4 orange, Zone 5 red. The scientific ACSM intensity entities remain unchanged.
- Light feedback/restore service calls now request zero transition to avoid a visible intermediate color/fade before the saved light snapshot is restored.
- Periodic AI coaching now explicitly includes elapsed time, actual current HR and speed when available, the most useful calculated relative/trend context, and a motivational line; it only calls the session running/cycling with strong live-source evidence. Deterministic TTS now follows the same structure with localized live/calculated values and motivation.
- HRR collection keeps the 10-second sample silently, gives light/spoken checkpoint feedback at 30/60/90 seconds, and uses the 120-second completion message instead of announcing zero seconds remaining. Missing RPE is requested only after HRR completion for live workouts.


## 2026.8.9-beta2

- Added integer 1–10 session RPE as a native Fitness Number entity and modern Live Workout card input. Provider-supplied RPE is normalized when available; Fitness only asks the user for RPE when the completed workout does not already contain one.
- Added localized AI/static RPE reminders after locally stopped workouts and external workout announcements. Editing RPE after completion immediately recalculates session-RPE load, relative load context and long-term Fitness summaries.
- Added session-RPE load (RPE × duration minutes), 7/28-day RPE-load history, and completed-workout RPE/load entities.
- Promoted 2-minute heart-rate recovery into personal 90-day baseline/comparison attributes alongside the existing 30/60/120-second collection.
- Added optional Detailed strength analysis (off by default): conservative exercise/set parsing, volume, best-set Epley estimated 1RM, and per-exercise progression stored in canonical workout attributes without creating one entity per exercise.
- Added Fitness-owned aerobic/high-intensity load decomposition from validated intensity-zone time. It is explicitly a transparent training heuristic, not a measured energy-system split.
- Expanded the Live and completed Workout cards with modern RPE, load, strength and progression presentation when those capabilities are available.


## 2026.8.9-beta1

- Completed the spoken workout lifecycle: waiting/ready/start, pause, resume, all 10/30/60/120-second heart-rate-recovery checkpoints, recovery completion and final workout feedback now use AI guidance with localized deterministic TTS fallback.
- HR-recovery checkpoints announce whether HR was collected and how many seconds remain.
- Periodic coaching now receives every available canonical live measurement: heart rate, power, cadence, speed, distance and altitude, plus derived personal context and recent trends. AI coaching ends with an actionable cue and short motivational line.
- Workout start/resume guidance includes motivation. Final workout feedback adds congratulations only when enough meaningful workout/recovery data was collected.
- AI announcement prompts explicitly require the configured Fitness language; non-AI environments retain localized deterministic TTS.


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
