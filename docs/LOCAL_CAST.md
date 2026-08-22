# HA-Fitness Local Cast

HA-Fitness uses a zero-registration local Cast path for profile dashboards.

Normal users do **not** need a Google Cast Developer account, a custom receiver application ID, a public Home Assistant URL, Cloudflare, Nabu Casa, or an app installed on the TV.

The path is:

```text
HA-Fitness backend
  -> Home Assistant's discovered Cast target
  -> public DashCast receiver (application 84912283)
  -> opaque temporary LAN URL served by HA-Fitness
  -> restricted Fitness TV dashboard
```

DashCast is an already-published receiver supported by PyChromecast. HA-Fitness launches it from the Home Assistant server and tells it to navigate directly (`force=True`) to a temporary URL on the Home Assistant LAN origin.

## What the installer does

1. Install HA-Fitness.
2. Configure Home Assistant's normal Google Cast integration so the TV/Chromecast appears as a `media_player` entity.
3. Pick that target in the Fitness TV profile.
4. Press **Cast**.

There is no per-installation receiver registration or app ID.

## Local authentication

The temporary DashCast URL does not contain a Home Assistant access token. It contains a high-entropy one-time bootstrap ticket generated in memory by HA-Fitness.

When the Cast device opens that URL, HA-Fitness:

- accepts it only from the local network;
- binds the resulting restricted session to the Cast browser's source address and user agent;
- creates an in-memory Fitness-only principal scoped to the selected Fitness profile;
- uses the existing restricted Fitness portal bridge for dashboard WebSocket-style calls, state reads and allowed service calls; and
- removes the ephemeral session when the Cast session is stopped or expires.

The Cast receiver never receives the user's Home Assistant refresh token or a persistent Fitness password.

## Network requirements

The Cast device must be able to reach Home Assistant's internal URL. HA-Fitness obtains that URL from Home Assistant's local network URL selection. A LAN IP URL such as `http://192.168.1.20:8123` is supported by DashCast and avoids the external HTTPS requirement of Home Assistant's official Lovelace Cast receiver.

Google Cast itself still requires the normal Cast platform/network connectivity, and the published DashCast application must remain available.

## Compatibility / fallback

The automatic DashCast path is used for the per-profile Fitness TV Cast action. Home Assistant's existing Cast integration remains the device-discovery/target source and can continue to serve as a compatibility fallback where appropriate.

The old experimental per-installation Custom Web Receiver setup is retained only as internal compatibility code for now and is no longer presented in the normal Fitness UI.

## Browser sender fallback

HA-Fitness keeps the browser Google Cast Web Sender path available as an independent fallback. Automatic HA-target casting prefers the zero-registration DashCast LAN route, while the browser Cast chooser remains usable from a compatible Chrome browser. The browser fallback does not require HA-Fitness users to register a custom receiver; the old per-installation custom-receiver setup stays hidden from the normal UI.

DashCast URL delivery intentionally uses a single `DashCastController.load_url(..., force=True)` call. PyChromecast's `load_url()` already launches DashCast before sending the URL, so HA-Fitness must not launch DashCast separately first.
