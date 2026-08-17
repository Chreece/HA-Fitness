# Fitness TV accounts and remote access

Fitness TV separates the Home Assistant login identity from the Fitness profile it is allowed to use. A user cannot enroll or bind themselves to a Fitness profile; only a local Fitness administrator can create or change the binding.

## Roles

| Role | Fitness visibility | Where Fitness TV is accepted | Management |
| --- | --- | --- | --- |
| **Fitness administrator** | Every Fitness profile | Local Home Assistant network only | May bind/remove Fitness accounts and add/delete backend Fitness profiles |
| **Local user** | Exactly one assigned profile | Local Home Assistant network only | Cannot manage accounts or other profiles |
| **Remote user** | Exactly one assigned profile | Only through that account's configured remote subdomain | Cannot manage accounts or other profiles |

The Home Assistant owner is bootstrapped as the first Fitness administrator if no Fitness administrator exists yet. Fitness prevents removal/demotion of the last Fitness administrator. A Fitness administrator must also be a Home Assistant administrator because backend Fitness profile/config-entry management is an HA administrator operation; Fitness itself still accepts the administrator role only from a local-network session.

While a user is assigned the **Local user** role, Fitness also marks that underlying Home Assistant user `local_only`, so Home Assistant itself rejects remote login for that account. Fitness remembers the previous HA `local_only` value and restores it when the Fitness account is removed or the backend profile is deleted. A **Remote user** is made non-local-only while assigned so it can authenticate through its remote Fitness hostname.

## What Fitness manages and what DNS still has to provide

Fitness deliberately manages the **logical access layer**, not your DNS provider or public TLS keys. This keeps Cloudflare, Route53, DuckDNS, router and certificate credentials out of the integration.

Fitness can manage from its UI:

- the remote Fitness base domain, for example `fitness.example.com`;
- the per-user slug, for example `alice`;
- the Home Assistant user -> Fitness role/profile binding;
- the exact remote URL generated for that user;
- authorization and immediate revocation of that Fitness account.

The network owner must provide these once outside Fitness:

1. **Public HTTPS reachability for Home Assistant.** Use an existing Home Assistant HTTPS/reverse-proxy setup, VPN/tunnel product that exposes the required hostname, or another supported public endpoint.
2. **Wildcard DNS.** Point `*.fitness.example.com` at the same public endpoint that reaches Home Assistant. A wildcard avoids creating/deleting a DNS record for every Fitness user.
3. **TLS valid for the wildcard hostname.** The reverse proxy must present a certificate valid for `*.fitness.example.com` (and normally the base hostname as well). This may be an ACME/Let's Encrypt wildcard certificate or a certificate managed by the chosen proxy/tunnel service.
4. **Preserve the incoming `Host` header.** Fitness uses the requested hostname to enforce each remote user's assigned slug, so the proxy must forward the original host instead of rewriting every request to one internal hostname.
5. **Configure Home Assistant for the reverse proxy when one is used.** Home Assistant must trust only the actual proxy addresses and correctly accept forwarded client information. Do not configure an unrestricted trusted-proxy range.
6. **Set Home Assistant's external HTTPS URL** to the normal externally reachable Home Assistant URL. Fitness's per-user subdomains are additional accepted entry points; they do not replace HA's normal external URL.

Depending on the network, the owner may additionally need router port-forwarding, dynamic-DNS updating, CGNAT workarounds, or a tunnel/VPN provider. Fitness cannot infer or safely change those network-level settings by itself.

Fitness could technically integrate with individual DNS/provider APIs in the future, but doing so would require provider-specific credentials and would reduce portability. The wildcard model means that is not required for normal operation.

## Remote-user subdomains

Example:

```text
Remote Fitness base domain: fitness.example.com
Wildcard DNS:                *.fitness.example.com -> your HA/reverse-proxy endpoint
Wildcard certificate:        *.fitness.example.com

Alice: https://alice.fitness.example.com/fitness-tv/profile-<alice-profile-id>
Bob:   https://bob.fitness.example.com/fitness-tv/profile-<bob-profile-id>
```

Configure the wildcard DNS record, TLS certificate and reverse proxy once. Fitness then owns only the logical per-account slug (`alice`, `bob`, ...). If the administrator leaves the slug blank, Fitness generates an unused DNS-safe slug automatically.

A remote Fitness session is accepted only when the Home Assistant WebSocket session was authenticated from the exact assigned hostname. Knowing another profile entry ID does not grant access: dashboard configuration, workout control, music, Cast, TTS acknowledgements, BLE gateway data and ANT+ gateway data all perform the same server-side profile authorization.

Removing the Fitness account immediately removes its binding, so that HA user can no longer access any Fitness profile through Fitness TV. Because the DNS record is a wildcard, the hostname can still resolve at DNS level after removal; Fitness rejects it. This avoids requiring DNS-provider credentials inside Fitness.

## Home Assistant identity boundary

Version 1 intentionally reuses Home Assistant authentication. Fitness does **not** store a second password database and does not copy Home Assistant credentials.

This provides strict isolation inside Fitness TV, but it does not turn the Home Assistant frontend into a separate standalone Fitness-only application. A Fitness user may still have whatever non-Fitness Home Assistant access the administrator grants to that HA user. Use dedicated non-admin Home Assistant users for local/remote Fitness accounts and restrict their Home Assistant permissions as appropriate.

A future dedicated Fitness remote portal can build on the same profile/access model if completely separate Fitness-only login sessions are desired.

## Administrator workflow

1. Create the backend Fitness profile in Home Assistant.
2. Create or choose the Home Assistant user that will authenticate.
3. Complete the one-time public HTTPS, wildcard DNS/TLS and reverse-proxy setup described above if remote users will be used.
4. Open **Fitness TV -> Fitness accounts** as the local Fitness administrator.
5. Set **Remote Fitness base domain** once.
6. Assign one of:
   - **Local user** + one Fitness profile; or
   - **Remote user** + one Fitness profile + optional subdomain slug.
7. Give a remote user the exact URL generated by Fitness.
8. Remove the Fitness account binding to revoke Fitness access immediately. Deleting the backend Fitness profile also removes any binding to it.

Users never get an account-assignment control in their own Fitness TV UI.
