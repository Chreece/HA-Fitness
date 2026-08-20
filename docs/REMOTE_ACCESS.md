# Fitness accounts and Cloudflare external access

HA-Fitness uses **independent Fitness accounts** for its TV/dashboard surface. Fitness users are no longer Home Assistant users that are assigned to a Fitness profile, and Fitness credentials are not stored in or delegated to Home Assistant.

## Fitness account roles

| Role | Fitness access | Login scope |
| --- | --- | --- |
| **Administrator** | Full HA-Fitness administration and every Fitness profile | Local network by default; optional exact remote hostname |
| **Local user** | Full control of its own assigned profile; optional administrator-granted view-only profiles | Local network only |
| **Remote user** | Same profile rights as a local user, plus its own public hostname | Its exact configured Fitness hostname |

A non-admin account controls only its own assigned profile. An administrator can grant additional profiles as **view only**. View-only users can browse every dashboard in the granted profile, but cannot change cards, profile settings, workouts, music, sensors, Cast/TTS or other controls. The normal Fitness TV toolbar is hidden while a profile is being viewed read-only.

The Fitness TV overview and Fitness-account administration are available only to Fitness administrators.

Active native Home Assistant administrators retain Fitness administrator access. Independent Fitness administrators are supported alongside them, while ordinary Home Assistant users receive no Fitness rights automatically.

## Fitness credentials and first login

When an administrator creates a Fitness account, HA-Fitness generates a strong **first-time password**. The plaintext password is returned to the administrator once and is never persisted in readable form. If it is lost, an administrator can replace it with a new temporary password; the old password is not recoverable.

On first login the user must choose a new password and may change the login name. Passwords must be at least 14 characters, use multiple character classes, and are rejected when they are common, repetitive, predictable, or contain account/profile identifiers. Passwords are stored with a per-account salt using `scrypt` and constant-time verification.

After first login, users can change their own login name and password from **Account settings** in the Fitness portal. They must provide their current password before a credential change.

Fitness sign-in requires **HTTPS**. Session cookies are `Secure`, `HttpOnly`, `SameSite=Strict` browser-session cookies. Sessions have both absolute and idle timeouts, are bound to the hostname and browser user-agent fingerprint, and state-changing portal requests require a per-session CSRF token. Repeated failed logins are rate-limited and temporarily locked out.

## What HA-Fitness manages in Cloudflare

HA-Fitness manages only the DNS layer. It **does not edit nginx, Certbot**, certificates, router forwarding or firewall configuration.

Global administrator settings:

- **Cloudflare zone**, for example `example.com`;
- **Fitness base domain**, for example `fitness.example.com`;
- a scoped **Cloudflare API token**;
- the public IPv4 used as the A-record target.

Each **Remote Fitness account**, and each Administrator with **Remote access** enabled, owns:

- one DNS-safe **Subdomain**, for example `chreece`;
- the resulting URL, for example `https://chreece.fitness.example.com`.

When a remote account is enabled, HA-Fitness creates or updates one **DNS-only A record** for that exact account hostname. The record is marked as HA-Fitness-managed and an unrelated record at the same hostname is never adopted or overwritten.

When the remote account is disabled, deleted, changed to Local, or moved to another hostname, HA-Fitness blocks that account/hostname in its own authorization state first and then removes the old managed DNS record. If Cloudflare is temporarily unavailable, access stays blocked and cleanup can be retried later.

## One-time Cloudflare setup

1. In Cloudflare, create an API token scoped to the required zone with **Zone Read** and **DNS Edit** permissions.
2. Open **Fitness settings -> Fitness accounts** as a Fitness administrator.
3. In **Cloudflare external access**, enter:
   - Zone: `example.com`
   - Fitness base domain: `fitness.example.com`
   - API token
   - Public IPv4: the address already reaching the existing nginx/Home Assistant reverse proxy
4. Save the configuration.
5. Configure the Home Assistant host/reverse proxy separately. DNS alone is not enough: nginx (or an equivalent reverse proxy) must accept the Fitness base domain and wildcard user hosts, HTTPS/443 must reach that proxy, a valid TLS certificate must cover those names (for example a Certbot-managed wildcard or per-host certificate), and the original `Host` header must be preserved (for nginx, normally `proxy_set_header Host $host;`). HA-Fitness intentionally does not edit nginx, Certbot, firewall or router configuration.
6. HA-Fitness activates the exact-host Fitness guard when the integration loads. If that guard cannot be installed safely, Remote Fitness DNS is withheld or withdrawn instead of exposing the normal Home Assistant frontend.

There is an **info button** beside the Cloudflare configuration explaining these requirements in the selected Fitness language.

The API token is stored in private HA-Fitness storage. The browser only receives whether a token is configured; the saved token itself is never returned.

## Creating a Remote Fitness account

1. Open **Fitness settings -> Fitness accounts** as a Fitness administrator.
2. Add an account and choose **Remote user**.
3. Select the account's own Fitness profile.
4. Enter a subdomain such as `chreece`. The default login name follows the subdomain and can be changed.
5. Optionally grant other Fitness profiles as view-only.
6. Save the account.
7. Copy the one-time first password shown to the administrator.
8. HA-Fitness creates `chreece.fitness.example.com` as a DNS-only A record pointing at the configured public IPv4.
9. The user opens `https://chreece.fitness.example.com`. The hostname fixes the account identity server-side, so the page shows the assigned account instead of accepting another username. The user chooses a supported Fitness language, enters the temporary password, and is forced to choose a strong personal password before the dashboard opens. The chosen language is retained for that restricted dashboard session.

The subdomain belongs to the **account**, not to the profile settings. A Remote URL shown under the account is therefore resolved automatically from that account's subdomain and the global Fitness base domain.

## Giving a Fitness administrator remote access

An independent **Administrator** account can optionally enable **Remote access** in the same account row. The administrator keeps full Fitness-admin permissions and can still sign in locally, while Internet login is accepted only on that administrator's exact assigned hostname. A personal Fitness profile remains optional for administrators; the remote DNS record is account-owned rather than borrowed from a profile.

The same reverse-proxy/TLS requirements apply as for a normal Remote user.

## Creating a Local Fitness account

Create the account the same way but choose **Local user**. No public subdomain is created. The account can authenticate only from the local/private network and still uses the same HTTPS Fitness login and first-password flow.

## Public hostname confinement

A request to a configured remote hostname, for example:

```text
https://chreece.fitness.example.com
```

enters the restricted HA-Fitness login/portal. It does **not** expose the generic Home Assistant frontend, authentication API or websocket surface through that hostname.

After login, HA-Fitness exposes only its restricted account bridge and the profiles permitted by that Fitness account:

- the account's own profile is controllable;
- administrator-granted profiles are view-only;
- another profile ID does not bypass the ACL;
- a disabled or unknown Fitness subdomain returns 404;
- a Remote account cannot authenticate on a different remote account's hostname.

The restricted bridge allows the Fitness dashboard to read the states and Fitness websocket operations it needs, but write operations remain subject to the same profile control ACL.

### Remote browser Bluetooth and USB

An authenticated Remote Fitness user may use the dashboard's browser-side Bluetooth or USB gateway when their browser supports Web Bluetooth/WebUSB. The hardware stays attached to the user's browser: Home Assistant receives only bounded decoded gateway frames and does not obtain arbitrary USB/Bluetooth access to the remote computer. Pairing/device selection requires an explicit browser permission flow and a user action over HTTPS.

The restricted portal sends `Permissions-Policy` with `bluetooth=(self)` and `usb=(self)`, so third-party origins/frames cannot inherit device access. Gateway frames, strings, batch sizes, remembered devices and assignments are bounded server-side; every request is still checked against the authenticated Fitness profile ACL. Browser support remains platform-dependent, so an unsupported browser must use a supported Chromium-family browser or a local Home Assistant Bluetooth/ANT+ route instead.

## Per-account diagnostics

The administrator's Fitness Accounts screen refreshes account diagnostics without overwriting unsaved form edits. It reports, as available:

- current state (`live`, `ready`, `setup required`, `DNS pending`, `locked`, `error`, `disabled`);
- active Fitness sessions;
- last login and last seen times;
- local-network or remote-hostname login scope;
- failed-login count and lockout expiry;
- password/first-login status;
- Cloudflare DNS state and error;
- last account/login/DNS error.

## DNS safety rules

HA-Fitness intentionally applies several restrictions:

- only valid public IPv4 A-record targets are accepted;
- only DNS-safe single-label remote-account subdomains are accepted;
- records are created with Cloudflare proxying disabled;
- unrelated DNS records are never taken over;
- only records HA-Fitness can identify as managed are deleted;
- global zone/base/target/token changes that could orphan active managed records are blocked;
- API-token rotation is allowed after the replacement token is validated.

Because these records are deliberately **DNS-only**, clients connect directly to the configured public IPv4. Cloudflare's HTTP proxy/WAF/DDoS layer is not in the request path, so the public nginx/TLS origin must remain securely configured.
