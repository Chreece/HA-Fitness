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

## Remote-user subdomains

Fitness uses a wildcard DNS/TLS model so account creation and removal do not depend on a specific DNS vendor API.

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

Removing the Fitness account immediately removes its binding, so that HA user can no longer access any Fitness profile through Fitness TV. Because the DNS record is a wildcard, the hostname can still resolve at DNS level after removal; Fitness rejects it. This avoids requiring Cloudflare/Route53/etc. credentials inside Fitness.

## Home Assistant identity boundary

Version 1 intentionally reuses Home Assistant authentication. Fitness does **not** store a second password database and does not copy Home Assistant credentials.

This provides strict isolation inside Fitness TV, but it does not turn the Home Assistant frontend into a separate standalone Fitness-only application. A Fitness user may still have whatever non-Fitness Home Assistant access the administrator grants to that HA user. Use dedicated non-admin Home Assistant users for local/remote Fitness accounts and restrict their Home Assistant permissions as appropriate.

A future dedicated Fitness remote portal can build on the same profile/access model if completely separate Fitness-only login sessions are desired.

## Administrator workflow

1. Create the backend Fitness profile in Home Assistant.
2. Create or choose the Home Assistant user that will authenticate.
3. Open **Fitness TV -> Fitness accounts** as the local Fitness administrator.
4. Assign one of:
   - **Local user** + one Fitness profile; or
   - **Remote user** + one Fitness profile + optional subdomain slug.
5. For remote users, configure the wildcard base domain once and give the generated direct profile URL to the user.
6. Remove the Fitness account binding to revoke Fitness access immediately. Deleting the backend Fitness profile also removes any binding to it.

Users never get an account-assignment control in their own Fitness TV UI.
