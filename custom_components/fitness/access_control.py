"""Fitness TV account roles and profile access control.

Fitness profiles are backend data records.  Access to those records is a separate
concern and is deliberately assigned by a Fitness administrator; a user can never
self-bind to a profile.

Access model:
- Any active Home Assistant administrator/owner has global Fitness administration
  rights regardless of an optional Fitness profile binding.
- local: a non-admin account controls its own bound profile from a local network
  connection and may additionally receive explicit view-only grants.
- remote: a non-admin account controls its own bound profile from its configured
  remote subdomain and may additionally receive explicit view-only grants.

Per-profile external access can optionally manage DNS-only Cloudflare A records.
Fitness owns only the exact records it creates and the profile access policy;
nginx/TLS/Certbot remain infrastructure outside Home Assistant. Disabling external
access changes authorization first and then removes the managed DNS record, so a
Cloudflare outage can never leave the profile logically enabled.
"""
from __future__ import annotations

import asyncio
import html
import logging
from ipaddress import ip_address
import re
import secrets
import unicodedata
from typing import Any
from urllib.parse import urlparse

from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.storage import Store

from .cloudflare_dns import CloudflareDNSClient, CloudflareDNSError
from .const import CONF_LANGUAGE, DOMAIN, SUPPORTED_LANGUAGES

ACCESS_STORE_VERSION = 1
ACCESS_STORE_KEY = "fitness.access_control"
ACCESS_CONTROLLER_KEY = "_fitness_access_control"
DEFAULT_DASHBOARD_MAX = 3
MAX_DASHBOARD_MAX = 12
DEFAULT_CLOUDFLARE_ZONE = ""
DEFAULT_CLOUDFLARE_BASE_DOMAIN = ""
_EXTERNAL_HOST_MIDDLEWARE_KEY = "_fitness_external_host_middleware"
_EXTERNAL_GATE_COOKIE = "fitness_external_gate"
_EXTERNAL_GATE_PATH = "/fitness-external/start"
_LOGGER = logging.getLogger(__name__)

ROLE_ADMIN = "admin"
ROLE_LOCAL = "local"
ROLE_REMOTE = "remote"
ROLES = {ROLE_ADMIN, ROLE_LOCAL, ROLE_REMOTE}

_CAST_SYSTEM_USER_NAMES = {"Home Assistant Cast", "Fitness TV Cast"}
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def _normalize_domain(value: Any) -> str:
    raw = str(value or "").strip().lower().rstrip(".")
    if not raw:
        return ""
    if "://" in raw:
        parsed = urlparse(raw)
        raw = str(parsed.hostname or "").strip().lower().rstrip(".")
    if "/" in raw or ":" in raw:
        return ""
    labels = raw.split(".")
    if len(labels) < 2 or any(not _SLUG_RE.fullmatch(label) for label in labels):
        return ""
    return raw


def _normalize_slug(value: Any) -> str:
    slug = str(value or "").strip().lower()
    return slug if _SLUG_RE.fullmatch(slug) else ""


def _normalize_public_ipv4(value: Any) -> str:
    """Return a canonical public IPv4 address or an empty string."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        address = ip_address(raw)
    except ValueError:
        return ""
    if address.version != 4 or not address.is_global:
        return ""
    return str(address)


def _domain_within_zone(base_domain: str, zone: str) -> bool:
    base = _normalize_domain(base_domain)
    root = _normalize_domain(zone)
    return bool(base and root and (base == root or base.endswith(f".{root}")))


def _normalize_language(value: Any) -> str:
    """Return one Fitness-supported language code."""
    raw = str(value or "en").strip().lower()
    code = raw.split("-", 1)[0].split("_", 1)[0]
    return code if code in SUPPORTED_LANGUAGES else "en"


def _is_local_remote(remote: Any) -> bool:
    """Return whether a websocket peer is on a local/private network."""
    value = str(remote or "").strip()
    if not value:
        return False
    # ActiveConnection.remote is already the HA-resolved peer address (trusted
    # proxy handling happens before the websocket connection is constructed).
    if value.startswith("[") and "]" in value:
        value = value[1:value.index("]")]
    elif value.count(":") == 1 and "." in value:
        value = value.rsplit(":", 1)[0]
    if "%" in value:
        value = value.split("%", 1)[0]
    try:
        address = ip_address(value)
    except ValueError:
        return False
    return bool(address.is_private or address.is_loopback or address.is_link_local)


def _slug_seed(value: Any) -> str:
    """Return a conservative DNS-label seed from a display value."""
    raw = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    raw = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    raw = re.sub(r"-+", "-", raw)
    return raw[:63].strip("-")




class FitnessAccessController:
    """Persist and enforce Fitness TV account bindings."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(
            hass,
            ACCESS_STORE_VERSION,
            ACCESS_STORE_KEY,
            private=True,
            atomic_writes=True,
        )
        self._loaded = False
        self._load_lock = asyncio.Lock()
        self._mutation_lock = asyncio.Lock()
        # Session-only public-entry gate token. It is intentionally regenerated
        # on every HA restart so an old browser session must pass the Fitness
        # sign-in entry page again. Home Assistant remains the real authenticator.
        self._external_gate_token = secrets.token_urlsafe(32)
        self._data: dict[str, Any] = {
            "remote_base_domain": DEFAULT_CLOUDFLARE_BASE_DOMAIN,
            "cloudflare": {
                "zone": DEFAULT_CLOUDFLARE_ZONE,
                "base_domain": DEFAULT_CLOUDFLARE_BASE_DOMAIN,
                "api_token": "",
                "record_target": "",
                "zone_id": "",
            },
            "external_profiles": {},
            "external_accounts": {},
            "dashboard_max": DEFAULT_DASHBOARD_MAX,
            "accounts": {},
        }

    async def async_load(self) -> None:
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                return
            saved = await self._store.async_load()
            if isinstance(saved, dict):
                accounts = saved.get("accounts")
                clean_accounts: dict[str, dict[str, Any]] = {}
                if isinstance(accounts, dict):
                    for raw_user_id, raw_account in accounts.items():
                        user_id = str(raw_user_id or "").strip()[:128]
                        if not user_id or not isinstance(raw_account, dict):
                            continue
                        role = str(raw_account.get("role") or "").strip().lower()
                        if role not in ROLES:
                            continue
                        clean: dict[str, Any] = {
                            "role": role,
                            "ha_user_id": user_id,
                            "enabled": bool(raw_account.get("enabled", True)),
                        }
                        profile_id = str(
                            raw_account.get("profile_entry_id") or ""
                        ).strip()[:128]
                        if profile_id:
                            clean["profile_entry_id"] = profile_id
                        views = sorted(self._view_profile_ids(raw_account))[:256]
                        if views:
                            clean["view_profile_entry_ids"] = views
                        # Account language was a duplicate authority and caused
                        # profile/UI language drift. The bound profile is now the
                        # sole Fitness language source; old account values migrate
                        # away simply by not copying them into the sanitized store.
                        slug = _normalize_slug(raw_account.get("remote_slug"))
                        if role == ROLE_REMOTE and slug:
                            clean["remote_slug"] = slug
                        if "previous_local_only" in raw_account:
                            clean["previous_local_only"] = bool(
                                raw_account.get("previous_local_only")
                            )
                        clean_accounts[user_id] = clean
                        if len(clean_accounts) >= 1_024:
                            break
                try:
                    dashboard_max = int(saved.get("dashboard_max", DEFAULT_DASHBOARD_MAX))
                except (TypeError, ValueError):
                    dashboard_max = DEFAULT_DASHBOARD_MAX
                saved_cloudflare = saved.get("cloudflare")
                if not isinstance(saved_cloudflare, dict):
                    saved_cloudflare = {}
                legacy_base = _normalize_domain(saved.get("remote_base_domain"))
                zone = _normalize_domain(saved_cloudflare.get("zone"))
                base_domain = _normalize_domain(
                    saved_cloudflare.get("base_domain") or legacy_base
                )
                # No installation-specific domain is ever assumed. Invalid or
                # incomplete saved namespace settings are cleared and must be
                # configured explicitly by a Fitness administrator.
                if not _domain_within_zone(base_domain, zone):
                    base_domain = ""
                record_target = _normalize_public_ipv4(
                    saved_cloudflare.get("record_target")
                )
                api_token = str(saved_cloudflare.get("api_token") or "").strip()[:512]
                zone_id = str(saved_cloudflare.get("zone_id") or "").strip()[:128]

                clean_external: dict[str, dict[str, Any]] = {}
                raw_external = saved.get("external_profiles")
                if isinstance(raw_external, dict):
                    for raw_profile_id, raw_row in raw_external.items():
                        profile_id = str(raw_profile_id or "").strip()[:128]
                        if not profile_id or not isinstance(raw_row, dict):
                            continue
                        slug = _normalize_slug(raw_row.get("subdomain"))
                        if not slug:
                            continue
                        clean_external[profile_id] = {
                            "enabled": bool(raw_row.get("enabled", False)),
                            "subdomain": slug,
                            "dns_record_id": str(raw_row.get("dns_record_id") or "")[:128],
                            "dns_name": _normalize_domain(raw_row.get("dns_name")),
                            "dns_zone_id": str(raw_row.get("dns_zone_id") or "")[:128],
                            "dns_state": str(raw_row.get("dns_state") or "disabled")[:64],
                            "last_error": str(raw_row.get("last_error") or "")[:128],
                            "cleanup_dns_record_id": str(raw_row.get("cleanup_dns_record_id") or "")[:128],
                            "cleanup_dns_name": _normalize_domain(raw_row.get("cleanup_dns_name")),
                            "cleanup_dns_zone_id": str(raw_row.get("cleanup_dns_zone_id") or "")[:128],
                        }
                        if len(clean_external) >= 1_024:
                            break
                clean_external_accounts: dict[str, dict[str, Any]] = {}
                raw_external_accounts = saved.get("external_accounts")
                if isinstance(raw_external_accounts, dict):
                    for raw_account_id, raw_row in raw_external_accounts.items():
                        account_id = str(raw_account_id or "").strip()[:64]
                        if not account_id or not isinstance(raw_row, dict):
                            continue
                        slug = _normalize_slug(raw_row.get("subdomain"))
                        if not slug:
                            continue
                        clean_external_accounts[account_id] = {
                            "enabled": bool(raw_row.get("enabled", False)),
                            "subdomain": slug,
                            "dns_record_id": str(raw_row.get("dns_record_id") or "")[:128],
                            "dns_name": _normalize_domain(raw_row.get("dns_name")),
                            "dns_zone_id": str(raw_row.get("dns_zone_id") or "")[:128],
                            "dns_state": str(raw_row.get("dns_state") or "disabled")[:64],
                            "last_error": str(raw_row.get("last_error") or "")[:128],
                            "cleanup_dns_record_id": str(raw_row.get("cleanup_dns_record_id") or "")[:128],
                            "cleanup_dns_name": _normalize_domain(raw_row.get("cleanup_dns_name")),
                            "cleanup_dns_zone_id": str(raw_row.get("cleanup_dns_zone_id") or "")[:128],
                        }
                        if len(clean_external_accounts) >= 1_024:
                            break

                self._data = {
                    "remote_base_domain": base_domain,
                    "cloudflare": {
                        "zone": zone,
                        "base_domain": base_domain,
                        "api_token": api_token,
                        "record_target": record_target,
                        "zone_id": zone_id,
                    },
                    "external_profiles": clean_external,
                    "external_accounts": clean_external_accounts,
                    "dashboard_max": max(1, min(MAX_DASHBOARD_MAX, dashboard_max)),
                    "accounts": clean_accounts,
                }
            self._loaded = True
            await self._async_bootstrap_owner()

    async def _async_bootstrap_owner(self) -> None:
        accounts = self._data["accounts"]
        if any(
            isinstance(row, dict)
            and row.get("enabled", True)
            and row.get("role") == ROLE_ADMIN
            for row in accounts.values()
        ):
            return
        owner = await self.hass.auth.async_get_owner()
        if owner is None:
            return
        accounts[owner.id] = {
            "role": ROLE_ADMIN,
            "ha_user_id": owner.id,
            "enabled": True,
        }
        await self._store.async_save(self._data)

    def _account(self, user_id: str | None) -> dict[str, Any] | None:
        if not user_id:
            return None
        row = self._data.get("accounts", {}).get(str(user_id))
        if not isinstance(row, dict) or not row.get("enabled", True):
            return None
        return row

    def _cloudflare(self) -> dict[str, Any]:
        row = self._data.get("cloudflare")
        return row if isinstance(row, dict) else {}

    def _cloudflare_ready(self) -> bool:
        cfg = self._cloudflare()
        return bool(
            _normalize_domain(cfg.get("zone"))
            and _normalize_domain(cfg.get("base_domain"))
            and str(cfg.get("api_token") or "").strip()
            and _normalize_public_ipv4(cfg.get("record_target"))
        )

    @staticmethod
    def _external_comment(profile_entry_id: str) -> str:
        return f"Managed by HA-Fitness profile {str(profile_entry_id)[:64]}"

    def _external_profile(self, profile_entry_id: str) -> dict[str, Any] | None:
        row = self._data.get("external_profiles", {}).get(str(profile_entry_id))
        return row if isinstance(row, dict) else None

    @staticmethod
    def _external_account_comment(account_id: str) -> str:
        return f"Managed by HA-Fitness account {str(account_id)[:64]}"

    def _external_account(self, account_id: str) -> dict[str, Any] | None:
        row = self._data.get("external_accounts", {}).get(str(account_id))
        return row if isinstance(row, dict) else None

    def _external_account_host(self, account_id: str) -> str:
        row = self._external_account(account_id)
        if not row or not row.get("enabled", False):
            return ""
        slug = _normalize_slug(row.get("subdomain"))
        base = _normalize_domain(self._cloudflare().get("base_domain"))
        return f"{slug}.{base}" if slug and base else ""

    def external_account_descriptor(self, account_id: str) -> dict[str, Any]:
        """Return public DNS state for an account-owned admin hostname."""
        row = self._external_account(account_id) or {}
        host = self._external_account_host(account_id)
        cfg = self._cloudflare()
        return {
            "enabled": bool(row.get("enabled", False)),
            "subdomain": str(row.get("subdomain") or ""),
            "url": f"https://{host}" if host else None,
            "dns_state": str(row.get("dns_state") or "disabled"),
            "last_error": str(row.get("last_error") or "") or None,
            "base_domain": _normalize_domain(cfg.get("base_domain")),
            "zone": _normalize_domain(cfg.get("zone")),
            "cloudflare_configured": self._cloudflare_ready(),
            "host_router_ready": bool(
                self.hass.data.get(DOMAIN, {}).get("_fitness_account_portal_middleware")
                or self.hass.data.get(DOMAIN, {}).get(_EXTERNAL_HOST_MIDDLEWARE_KEY)
            ),
        }

    async def _async_sync_bound_profile_user_local_only(
        self, profile_entry_id: str
    ) -> None:
        """Legacy compatibility hook; Fitness accounts no longer mutate HA users."""
        # Authentication and LAN/remote policy now belong to the independent
        # Fitness account store. Never relax or rewrite a Home Assistant user's
        # ``local_only`` flag just because a Fitness hostname is published.
        return

    def _external_profile_host(self, profile_entry_id: str) -> str:
        row = self._external_profile(profile_entry_id)
        if not row or not row.get("enabled", False):
            return ""
        slug = _normalize_slug(row.get("subdomain"))
        base = _normalize_domain(self._cloudflare().get("base_domain"))
        return f"{slug}.{base}" if slug and base else ""

    def external_profile_descriptor(self, profile_entry_id: str) -> dict[str, Any]:
        """Return the public, secret-free external-access state for a profile."""
        row = self._external_profile(profile_entry_id) or {}
        host = self._external_profile_host(profile_entry_id)
        cfg = self._cloudflare()
        return {
            "enabled": bool(row.get("enabled", False)),
            "subdomain": str(row.get("subdomain") or ""),
            "url": f"https://{host}" if host else None,
            "dns_state": str(row.get("dns_state") or "disabled"),
            "last_error": str(row.get("last_error") or "") or None,
            "base_domain": _normalize_domain(cfg.get("base_domain")),
            "zone": _normalize_domain(cfg.get("zone")),
            "cloudflare_configured": self._cloudflare_ready(),
            "host_router_ready": bool(
                self.hass.data.get(DOMAIN, {}).get("_fitness_account_portal_middleware")
                or self.hass.data.get(DOMAIN, {}).get(_EXTERNAL_HOST_MIDDLEWARE_KEY)
            ),
        }

    def _external_profile_for_host(self, host: str) -> str | None:
        hostname = str(host or "").strip().lower().rstrip(".")
        if hostname.startswith("[") and "]" in hostname:
            hostname = hostname[1:hostname.index("]")]
        elif hostname.count(":") == 1:
            hostname = hostname.rsplit(":", 1)[0]
        for profile_id in self._data.get("external_profiles", {}):
            if self._external_profile_host(str(profile_id)) == hostname:
                return str(profile_id)
        return None

    def _host_is_external_namespace(self, host: str) -> bool:
        hostname = str(host or "").strip().lower().rstrip(".")
        if hostname.count(":") == 1:
            hostname = hostname.rsplit(":", 1)[0]
        base = _normalize_domain(self._cloudflare().get("base_domain"))
        return bool(base and hostname.endswith(f".{base}"))

    def _refresh_token_client_host(self, connection) -> str:
        token_id = getattr(connection, "refresh_token_id", None)
        if not token_id:
            return ""
        token = self.hass.auth.async_get_refresh_token(str(token_id))
        client_id = str(getattr(token, "client_id", "") or "") if token else ""
        if not client_id:
            return ""
        try:
            parsed = urlparse(client_id)
            if str(parsed.scheme or "").lower() != "https":
                return ""
            return str(parsed.hostname or "").lower().rstrip(".")
        except ValueError:
            return ""

    def _remote_account_host(self, account: dict[str, Any]) -> str:
        profile_id = str(account.get("profile_entry_id") or "")
        if profile_id and self._external_profile(profile_id) is not None:
            # Once a profile has adopted explicit external-access state, disabled
            # means disabled. Never fall back to the legacy logical remote slug.
            return self._external_profile_host(profile_id)
        base = _normalize_domain(self._data.get("remote_base_domain"))
        slug = _normalize_slug(account.get("remote_slug"))
        return f"{slug}.{base}" if base and slug else ""

    def _session_allowed(self, connection, account: dict[str, Any]) -> bool:
        role = account.get("role")
        if role == ROLE_ADMIN:
            return _is_local_remote(getattr(connection, "remote", None))
        if role == ROLE_LOCAL:
            if _is_local_remote(getattr(connection, "remote", None)):
                return True
            profile_id = str(account.get("profile_entry_id") or "")
            expected = self._external_profile_host(profile_id) if profile_id else ""
            return bool(expected and self._refresh_token_client_host(connection) == expected)
        if role == ROLE_REMOTE:
            expected = self._remote_account_host(account)
            return bool(
                _is_local_remote(getattr(connection, "remote", None))
                or (expected and self._refresh_token_client_host(connection) == expected)
            )
        return False

    def _is_cast_system_connection(self, connection) -> bool:
        user = getattr(connection, "user", None)
        return bool(
            user
            and getattr(user, "system_generated", False)
            and str(getattr(user, "name", "") or "") in _CAST_SYSTEM_USER_NAMES
        )

    def _all_profile_ids(self) -> set[str]:
        return {
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data.get("entry_type") not in {"live_hub", "devices_hub"}
        }

    @staticmethod
    def _profile_language(entry) -> str:
        if entry is None:
            return "en"
        config = {**entry.data, **entry.options}
        return _normalize_language(config.get(CONF_LANGUAGE) or "en")

    def _account_language(self, account: dict[str, Any] | None) -> str:
        """Return the bound profile language; accounts have no language override."""
        profile_id = str((account or {}).get("profile_entry_id") or "")
        entry = self.hass.config_entries.async_get_entry(profile_id) if profile_id else None
        return self._profile_language(entry) if entry is not None else _normalize_language(getattr(self.hass.config, "language", "en"))

    @staticmethod
    def _view_profile_ids(account: dict[str, Any] | None) -> set[str]:
        if not isinstance(account, dict):
            return set()
        raw = account.get("view_profile_entry_ids")
        if not isinstance(raw, list):
            return set()
        return {str(item).strip() for item in raw if str(item).strip()}

    @staticmethod
    def _fitness_principal(connection) -> dict[str, Any] | None:
        principal = getattr(connection, "fitness_principal", None)
        if not isinstance(principal, dict) or not principal.get("enabled", True):
            return None
        role = str(principal.get("role") or "none")
        return principal if role in ROLES else None

    async def _ha_native_admin(self, connection) -> bool:
        """Return whether this connection belongs to an active HA administrator.

        Native Home Assistant administrators permanently retain Fitness
        administrator access. Independent Fitness administrators remain fully
        supported as a separate login path; ordinary HA users gain no Fitness
        rights merely from having a Home Assistant account.
        """
        user = getattr(connection, "user", None)
        return bool(
            user
            and getattr(user, "is_active", True)
            and getattr(user, "is_admin", False)
        )

    async def async_descriptor(self, connection) -> dict[str, Any]:
        """Describe the current Fitness identity.

        Independent Fitness sessions are authoritative for normal Fitness
        accounts. Active Home Assistant administrators also retain global Fitness
        administration; non-admin HA users gain no Fitness rights from legacy
        Home Assistant user bindings.
        """
        await self.async_load()
        principal = self._fitness_principal(connection)
        if principal is not None:
            role = str(principal.get("role") or "none")
            profile_id = str(principal.get("profile_entry_id") or "") or None
            entry = self.hass.config_entries.async_get_entry(profile_id) if profile_id else None
            remote_slug = str(principal.get("remote_slug") or "") or None
            remote_enabled = bool(principal.get("remote_enabled")) or role == ROLE_REMOTE
            return {
                "account_id": str(principal.get("account_id") or "") or None,
                "username": str(principal.get("username") or "") or None,
                "display_name": str(principal.get("display_name") or "") or None,
                "role": role,
                "is_admin": role == ROLE_ADMIN,
                "ha_admin": False,
                "can_manage": role == ROLE_ADMIN,
                "profile_entry_id": profile_id,
                "view_profile_entry_ids": (
                    [] if role == ROLE_ADMIN else sorted(self._view_profile_ids(principal))
                ),
                "remote_slug": remote_slug,
                "remote_url": (
                    f"https://{remote_slug}.{_normalize_domain(self._cloudflare().get('base_domain'))}"
                    if remote_enabled and remote_slug and _normalize_domain(self._cloudflare().get("base_domain"))
                    else None
                ),
                "external_access": (
                    self.external_account_descriptor(str(principal.get("account_id") or ""))
                    if role == ROLE_ADMIN and remote_enabled
                    else self.external_profile_descriptor(profile_id)
                    if profile_id and role == ROLE_REMOTE
                    else None
                ),
                "language": self._profile_language(entry),
                "session_allowed": True,
            }

        user = getattr(connection, "user", None)
        ha_admin = bool(
            user
            and getattr(user, "is_active", True)
            and getattr(user, "is_admin", False)
        )
        native_admin = bool(ha_admin and await self._ha_native_admin(connection))
        if native_admin:
            return {
                "role": ROLE_ADMIN,
                "is_admin": True,
                "ha_admin": True,
                "native_ha_admin": True,
                "can_manage": True,
                "profile_entry_id": None,
                "view_profile_entry_ids": [],
                "remote_slug": None,
                "remote_url": None,
                "external_access": None,
                "language": _normalize_language(getattr(self.hass.config, "language", "en")),
                "session_allowed": True,
            }

        return {
            "role": "none",
            "is_admin": False,
            "ha_admin": False,
            "can_manage": False,
            "profile_entry_id": None,
            "view_profile_entry_ids": [],
            "remote_slug": None,
            "remote_url": None,
            "external_access": None,
            "language": _normalize_language(getattr(self.hass.config, "language", "en")),
            "session_allowed": False,
        }

    async def async_visible_profile_ids(self, connection, *, cast_hub=None) -> set[str]:
        await self.async_load()
        if self._is_cast_system_connection(connection):
            if cast_hub is None:
                return set()
            return {
                entry.entry_id
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.data.get("entry_type") not in {"live_hub", "devices_hub"}
                and cast_hub.has_cast_expectation(entry.entry_id)
            }

        principal = self._fitness_principal(connection)
        if principal is not None:
            if str(principal.get("role")) == ROLE_ADMIN:
                return self._all_profile_ids()
            visible = self._view_profile_ids(principal)
            profile_id = str(principal.get("profile_entry_id") or "")
            if profile_id:
                visible.add(profile_id)
            return visible & self._all_profile_ids()

        if await self._ha_native_admin(connection):
            return self._all_profile_ids()
        return set()

    async def async_control_profile_ids(self, connection, *, cast_hub=None) -> set[str]:
        """Return profiles this Fitness identity may actively control/configure."""
        await self.async_load()
        if self._is_cast_system_connection(connection):
            return await self.async_visible_profile_ids(connection, cast_hub=cast_hub)

        principal = self._fitness_principal(connection)
        if principal is not None:
            if str(principal.get("role")) == ROLE_ADMIN:
                return self._all_profile_ids()
            profile_id = str(principal.get("profile_entry_id") or "")
            return {profile_id} if profile_id and profile_id in self._all_profile_ids() else set()

        if await self._ha_native_admin(connection):
            return self._all_profile_ids()
        return set()

    async def async_profile_access(
        self, connection, profile_entry_id: str, *, cast_hub=None
    ) -> str:
        profile_id = str(profile_entry_id)
        if profile_id in await self.async_control_profile_ids(connection, cast_hub=cast_hub):
            return "control"
        if profile_id in await self.async_visible_profile_ids(connection, cast_hub=cast_hub):
            return "view"
        return "none"

    async def async_require_profile(self, connection, profile_entry_id: str, *, cast_hub=None) -> None:
        visible = await self.async_visible_profile_ids(connection, cast_hub=cast_hub)
        if str(profile_entry_id) not in visible:
            raise Unauthorized

    async def async_require_profile_control(
        self, connection, profile_entry_id: str, *, cast_hub=None
    ) -> None:
        controlled = await self.async_control_profile_ids(connection, cast_hub=cast_hub)
        if str(profile_entry_id) not in controlled:
            raise Unauthorized

    async def async_require_admin(self, connection) -> dict[str, Any]:
        await self.async_load()
        principal = self._fitness_principal(connection)
        if principal is not None:
            if str(principal.get("role")) != ROLE_ADMIN:
                raise Unauthorized
            return principal
        if not await self._ha_native_admin(connection):
            raise Unauthorized
        user = getattr(connection, "user", None)
        # Native HA administrators are already system administrators, so they
        # retain global Fitness administration alongside independent Fitness
        # administrators.
        return {
            "role": ROLE_ADMIN,
            "ha_user_id": str(getattr(user, "id", "") or ""),
            "enabled": True,
            "native_ha_admin": True,
        }

    async def async_admin_snapshot(self, connection) -> dict[str, Any]:
        await self.async_require_admin(connection)
        # Imported lazily to avoid an access_control <-> tv_dashboard import cycle.
        from .tv_dashboard import get_tv_dashboard_hub

        hub = get_tv_dashboard_hub(self.hass)
        await hub.async_load()
        profile_rows: list[dict[str, Any]] = []
        profile_by_id: dict[str, dict[str, Any]] = {}
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("entry_type") in {"live_hub", "devices_hub"}:
                continue
            config = {**entry.data, **entry.options}
            prefs = await hub.async_preferences(entry.entry_id)
            row = {
                "entry_id": entry.entry_id,
                "name": str(config.get("profile_name") or entry.title or entry.entry_id),
                "language": self._profile_language(entry),
                "external_access": self.external_profile_descriptor(entry.entry_id),
                "bound_user_id": next(
                    (uid for uid, account in self._data["accounts"].items()
                     if isinstance(account, dict) and account.get("enabled", True)
                     and account.get("profile_entry_id") == entry.entry_id),
                    None,
                ),
                "viewer_user_ids": sorted(
                    uid for uid, account in self._data["accounts"].items()
                    if isinstance(account, dict) and account.get("enabled", True)
                    and entry.entry_id in self._view_profile_ids(account)
                ),
                "tv_dashboard_enabled": bool(config.get("tv_dashboard_enabled", False)),
                "cast_media_player_id": str(config.get("tv_dashboard_media_player_id") or "") or None,
                "cast_target": hub.cast_target(entry.entry_id),
                "cast_active": hub.is_any_cast_active(entry.entry_id),
                "local_cast_active": hub.is_local_cast_active(entry.entry_id),
                "light_feedback_enabled": bool(prefs.get("light_feedback_enabled", True)),
                "tts_announcements_enabled": bool(prefs.get("tts_announcements_enabled", True)),
            }
            profile_rows.append(row)
            profile_by_id[entry.entry_id] = row

        users = []
        try:
            auth_users = await asyncio.wait_for(self.hass.auth.async_get_users(), timeout=8.0)
        except TimeoutError:
            auth_users = []
        for user in auth_users:
            if getattr(user, "system_generated", False):
                continue
            bound = self._account(user.id)
            effective_role = ROLE_ADMIN if bool(user.is_admin) else (str(bound.get("role")) if bound else None)
            bound_profile_id = str(bound.get("profile_entry_id") or "") if bound else ""
            bound_profile = profile_by_id.get(bound_profile_id)
            users.append({
                "user_id": user.id,
                "name": str(user.name or user.id),
                "is_admin": bool(user.is_admin),
                "is_owner": bool(user.is_owner),
                "is_active": bool(user.is_active),
                "local_only": bool(user.local_only),
                "fitness_role": effective_role,
                "fitness_profile_entry_id": bound_profile_id or None,
                "view_profile_entry_ids": [] if user.is_admin else sorted(self._view_profile_ids(bound)),
                "remote_slug": str(bound.get("remote_slug") or "") if bound else None,
                "remote_url": str((bound_profile or {}).get("external_access", {}).get("url") or "") or None,
                "language": _normalize_language(
                    (bound_profile or {}).get("language")
                    or getattr(self.hass.config, "language", "en")
                ),
            })
        return {
            "remote_base_domain": self._data.get("remote_base_domain") or "",
            "cloudflare": {
                "zone": _normalize_domain(self._cloudflare().get("zone")),
                "base_domain": _normalize_domain(self._cloudflare().get("base_domain")),
                "record_target": _normalize_public_ipv4(self._cloudflare().get("record_target")),
                "api_token_configured": bool(str(self._cloudflare().get("api_token") or "").strip()),
                "configured": self._cloudflare_ready(),
                "host_router_ready": bool(self.hass.data.get(DOMAIN, {}).get(_EXTERNAL_HOST_MIDDLEWARE_KEY)),
            },
            "dashboard_max": int(self._data.get("dashboard_max", DEFAULT_DASHBOARD_MAX)),
            "supported_languages": dict(SUPPORTED_LANGUAGES),
            "users": sorted(users, key=lambda item: item["name"].casefold()),
            "profiles": sorted(profile_rows, key=lambda item: item["name"].casefold()),
        }

    async def async_set_access_settings(
        self,
        connection,
        *,
        domain: str | None = None,
        dashboard_max: int | None = None,
        cloudflare_zone: str | None = None,
        cloudflare_base_domain: str | None = None,
        cloudflare_api_token: str | None = None,
        cloudflare_record_target: str | None = None,
        clear_cloudflare_api_token: bool = False,
    ) -> dict[str, Any]:
        """Serialize account-level access and global Cloudflare settings."""
        async with self._mutation_lock:
            await self.async_require_admin(connection)
            current = dict(self._cloudflare())
            zone = _normalize_domain(
                cloudflare_zone if cloudflare_zone is not None else current.get("zone")
            )
            base_input = (
                cloudflare_base_domain
                if cloudflare_base_domain is not None
                else (domain if domain is not None else current.get("base_domain"))
            )
            base = _normalize_domain(base_input)
            if not zone:
                raise ValueError("invalid_cloudflare_zone")
            if not base or not _domain_within_zone(base, zone):
                raise ValueError("invalid_remote_base_domain")

            target_input = (
                cloudflare_record_target
                if cloudflare_record_target is not None
                else current.get("record_target")
            )
            target = _normalize_public_ipv4(target_input)
            if str(target_input or "").strip() and not target:
                raise ValueError("invalid_public_ipv4")

            token = str(current.get("api_token") or "").strip()
            if clear_cloudflare_api_token:
                token = ""
            elif cloudflare_api_token is not None and str(cloudflare_api_token).strip():
                token = str(cloudflare_api_token).strip()[:512]

            external_enabled = any(
                isinstance(row, dict) and row.get("enabled", False)
                for collection in (
                    self._data.get("external_profiles", {}),
                    self._data.get("external_accounts", {}),
                )
                for row in collection.values()
            )
            critical_changed = any(
                (old or "") != (new or "")
                for old, new in (
                    (_normalize_domain(current.get("zone")), zone),
                    (_normalize_domain(current.get("base_domain")), base),
                    (_normalize_public_ipv4(current.get("record_target")), target),
                )
            )
            if external_enabled and (critical_changed or not token):
                # Do not orphan active managed records by removing the token or
                # changing the namespace/target underneath them. Token rotation
                # is safe because the replacement is validated below.
                raise ValueError("cloudflare_settings_in_use")

            zone_id = str(current.get("zone_id") or "")
            if token:
                try:
                    client = CloudflareDNSClient(self.hass, token)
                    zone_id = await client.async_zone_id(zone)
                    # A harmless exact-name list confirms the token can access DNS
                    # for the selected zone without mutating any record.
                    await client.async_records(zone_id, base)
                except CloudflareDNSError as err:
                    raise ValueError(err.code) from err
            else:
                zone_id = ""

            self._data["cloudflare"] = {
                "zone": zone,
                "base_domain": base,
                "api_token": token,
                "record_target": target,
                "zone_id": zone_id,
            }
            # Keep the pre-Cloudflare remote-account contract as a compatibility
            # alias. New profile external access uses the same base domain.
            self._data["remote_base_domain"] = base
            if dashboard_max is not None:
                self._data["dashboard_max"] = max(
                    1, min(MAX_DASHBOARD_MAX, int(dashboard_max))
                )
            await self._store.async_save(self._data)
            return await self.async_admin_snapshot(connection)

    async def async_set_remote_base_domain(self, connection, domain: str) -> dict[str, Any]:
        """Backward-compatible remote-domain setter."""
        return await self.async_set_access_settings(connection, domain=domain)

    def dashboard_max(self) -> int:
        """Return the administrator-defined per-profile dashboard ceiling."""
        return max(1, min(MAX_DASHBOARD_MAX, int(self._data.get("dashboard_max", DEFAULT_DASHBOARD_MAX))))

    def _default_external_slug(self, entry) -> str:
        """Return one unique slug derived from the profile name."""
        config = {**entry.data, **entry.options}
        seeds = [
            _slug_seed(config.get("profile_name") or entry.title),
            f"fitness-{str(entry.entry_id)[:8].lower()}",
        ]
        used = {
            _normalize_slug(row.get("subdomain"))
            for profile_id, row in self._data.get("external_profiles", {}).items()
            if str(profile_id) != str(entry.entry_id)
            and isinstance(row, dict)
            and row.get("enabled", False)
        }
        used.update(
            _normalize_slug(row.get("subdomain"))
            for row in self._data.get("external_accounts", {}).values()
            if isinstance(row, dict) and row.get("enabled", False)
        )
        for seed in seeds:
            if seed and seed not in used and _normalize_slug(seed):
                return seed
        base = f"fitness-{str(entry.entry_id)[:8].lower()}"
        for suffix in range(2, 1000):
            candidate = f"{base[:58]}-{suffix}"
            if candidate not in used and _normalize_slug(candidate):
                return candidate
        raise ValueError("remote_slug_in_use")

    async def async_set_external_profile(
        self,
        connection,
        *,
        profile_entry_id: str,
        enabled: bool,
        subdomain: str | None = None,
    ) -> dict[str, Any]:
        """Enable/disable one profile hostname and reconcile its DNS record."""
        async with self._mutation_lock:
            await self.async_require_profile_control(connection, profile_entry_id)
            return await self._async_set_external_profile(
                profile_entry_id=profile_entry_id,
                enabled=enabled,
                subdomain=subdomain,
            )

    async def _async_set_external_profile(
        self,
        *,
        profile_entry_id: str,
        enabled: bool,
        subdomain: str | None,
    ) -> dict[str, Any]:
        profile_id = str(profile_entry_id)
        entry = self.hass.config_entries.async_get_entry(profile_id)
        if entry is None or entry.domain != DOMAIN or entry.data.get("entry_type") in {"live_hub", "devices_hub"}:
            raise ValueError("profile_not_found")

        external = self._data.setdefault("external_profiles", {})
        current = dict(self._external_profile(profile_id) or {})
        requested_slug = _normalize_slug(subdomain)
        if subdomain and not requested_slug:
            raise ValueError("invalid_remote_slug")

        if not enabled:
            # Authorization is the first mutation: even when Cloudflare is down,
            # the stale hostname stops resolving to this Fitness profile now.
            if current:
                current["enabled"] = False
                current["dns_state"] = "blocked"
                current["last_error"] = ""
                external[profile_id] = current
                await self._store.async_save(self._data)
                # Revoke HA-level remote login before any best-effort DNS cleanup.
                # The profile is already disabled in Fitness authorization above.
                await self._async_sync_bound_profile_user_local_only(profile_id)
                try:
                    await self._async_delete_external_dns(profile_id, current)
                    await self._async_delete_pending_external_dns(profile_id, current)
                except CloudflareDNSError as err:
                    current["dns_state"] = "cleanup_failed"
                    current["last_error"] = err.code
                    external[profile_id] = current
                    await self._store.async_save(self._data)
                    return self.external_profile_descriptor(profile_id)
            external.pop(profile_id, None)
            await self._store.async_save(self._data)
            await self._async_sync_bound_profile_user_local_only(profile_id)
            return self.external_profile_descriptor(profile_id)

        if not self._cloudflare_ready():
            raise ValueError("cloudflare_not_configured")
        slug = requested_slug or _normalize_slug(current.get("subdomain")) or self._default_external_slug(entry)
        for other_profile_id, other in external.items():
            if str(other_profile_id) == profile_id or not isinstance(other, dict):
                continue
            if other.get("enabled", False) and _normalize_slug(other.get("subdomain")) == slug:
                raise ValueError("remote_slug_in_use")
        for other in self._data.get("external_accounts", {}).values():
            if isinstance(other, dict) and other.get("enabled", False) and _normalize_slug(other.get("subdomain")) == slug:
                raise ValueError("remote_slug_in_use")

        cfg = self._cloudflare()
        zone = _normalize_domain(cfg.get("zone"))
        base = _normalize_domain(cfg.get("base_domain"))
        target = _normalize_public_ipv4(cfg.get("record_target"))
        token = str(cfg.get("api_token") or "").strip()
        client = CloudflareDNSClient(self.hass, token)
        try:
            zone_id = str(cfg.get("zone_id") or "") or await client.async_zone_id(zone)
            host = f"{slug}.{base}"
            record_id = await client.async_ensure_a_record(
                zone_id=zone_id,
                name=host,
                target=target,
                comment=self._external_comment(profile_id),
                record_id=str(current.get("dns_record_id") or "") if _normalize_domain(current.get("dns_name")) == host else "",
            )
        except CloudflareDNSError as err:
            raise ValueError(err.code) from err

        old = current if current.get("enabled", False) else None
        row = {
            "enabled": True,
            "subdomain": slug,
            "dns_record_id": record_id,
            "dns_name": host,
            "dns_zone_id": zone_id,
            "dns_state": "active",
            "last_error": "",
            "cleanup_dns_record_id": str(current.get("cleanup_dns_record_id") or ""),
            "cleanup_dns_name": _normalize_domain(current.get("cleanup_dns_name")),
            "cleanup_dns_zone_id": str(current.get("cleanup_dns_zone_id") or ""),
        }
        external[profile_id] = row
        cfg["zone_id"] = zone_id
        await self._store.async_save(self._data)
        # HA's local-only login gate must be relaxed only after the exact
        # hostname is active in Fitness authorization.
        await self._async_sync_bound_profile_user_local_only(profile_id)

        if old and _normalize_domain(old.get("dns_name")) and _normalize_domain(old.get("dns_name")) != host:
            try:
                await self._async_delete_external_dns(profile_id, old)
            except CloudflareDNSError as err:
                row["dns_state"] = "active_cleanup_pending"
                row["last_error"] = err.code
                row["cleanup_dns_record_id"] = str(old.get("dns_record_id") or "")
                row["cleanup_dns_name"] = _normalize_domain(old.get("dns_name"))
                row["cleanup_dns_zone_id"] = str(old.get("dns_zone_id") or "")
                external[profile_id] = row
                await self._store.async_save(self._data)
                return self.external_profile_descriptor(profile_id)
        try:
            await self._async_delete_pending_external_dns(profile_id, row)
        except CloudflareDNSError as err:
            row["dns_state"] = "active_cleanup_pending"
            row["last_error"] = err.code
            external[profile_id] = row
            await self._store.async_save(self._data)
        return self.external_profile_descriptor(profile_id)

    async def _async_delete_external_dns(self, profile_id: str, row: dict[str, Any]) -> None:
        cfg = self._cloudflare()
        token = str(cfg.get("api_token") or "").strip()
        if not token:
            raise CloudflareDNSError("cloudflare_token_required")
        zone_id = str(row.get("dns_zone_id") or cfg.get("zone_id") or "")
        client = CloudflareDNSClient(self.hass, token)
        if not zone_id:
            zone_id = await client.async_zone_id(_normalize_domain(cfg.get("zone")))
        name = _normalize_domain(row.get("dns_name"))
        if not name:
            slug = _normalize_slug(row.get("subdomain"))
            base = _normalize_domain(cfg.get("base_domain"))
            name = f"{slug}.{base}" if slug and base else ""
        if not name:
            return
        await client.async_delete_managed_record(
            zone_id=zone_id,
            name=name,
            comment=self._external_comment(profile_id),
            record_id=str(row.get("dns_record_id") or ""),
        )

    async def _async_delete_pending_external_dns(
        self, profile_id: str, row: dict[str, Any]
    ) -> None:
        """Delete an older managed hostname left behind by a slug change."""
        cleanup_name = _normalize_domain(row.get("cleanup_dns_name"))
        if not cleanup_name:
            return
        cleanup = {
            "dns_record_id": str(row.get("cleanup_dns_record_id") or ""),
            "dns_name": cleanup_name,
            "dns_zone_id": str(row.get("cleanup_dns_zone_id") or ""),
            "subdomain": "",
        }
        await self._async_delete_external_dns(profile_id, cleanup)
        row.pop("cleanup_dns_record_id", None)
        row.pop("cleanup_dns_name", None)
        row.pop("cleanup_dns_zone_id", None)

    async def _async_delete_external_account_dns(self, account_id: str, row: dict[str, Any]) -> None:
        cfg = self._cloudflare()
        token = str(cfg.get("api_token") or "").strip()
        if not token:
            raise CloudflareDNSError("cloudflare_token_required")
        zone_id = str(row.get("dns_zone_id") or cfg.get("zone_id") or "")
        client = CloudflareDNSClient(self.hass, token)
        if not zone_id:
            zone_id = await client.async_zone_id(_normalize_domain(cfg.get("zone")))
        name = _normalize_domain(row.get("dns_name"))
        if not name:
            slug = _normalize_slug(row.get("subdomain"))
            base = _normalize_domain(cfg.get("base_domain"))
            name = f"{slug}.{base}" if slug and base else ""
        if not name:
            return
        await client.async_delete_managed_record(
            zone_id=zone_id,
            name=name,
            comment=self._external_account_comment(account_id),
            record_id=str(row.get("dns_record_id") or ""),
        )

    async def _async_delete_pending_external_account_dns(
        self, account_id: str, row: dict[str, Any]
    ) -> None:
        cleanup_name = _normalize_domain(row.get("cleanup_dns_name"))
        if not cleanup_name:
            return
        cleanup = {
            "dns_record_id": str(row.get("cleanup_dns_record_id") or ""),
            "dns_name": cleanup_name,
            "dns_zone_id": str(row.get("cleanup_dns_zone_id") or ""),
            "subdomain": "",
        }
        await self._async_delete_external_account_dns(account_id, cleanup)
        row.pop("cleanup_dns_record_id", None)
        row.pop("cleanup_dns_name", None)
        row.pop("cleanup_dns_zone_id", None)

    async def _async_set_external_account(
        self, *, account_id: str, enabled: bool, subdomain: str | None
    ) -> dict[str, Any]:
        """Enable/disable one account-owned hostname and reconcile its DNS record."""
        account_id = str(account_id or "").strip()[:64]
        if not account_id:
            raise ValueError("account_not_found")
        external = self._data.setdefault("external_accounts", {})
        current = dict(self._external_account(account_id) or {})
        requested_slug = _normalize_slug(subdomain)
        if subdomain and not requested_slug:
            raise ValueError("invalid_remote_slug")

        if not enabled:
            if current:
                current["enabled"] = False
                current["dns_state"] = "blocked"
                current["last_error"] = ""
                external[account_id] = current
                await self._store.async_save(self._data)
                try:
                    await self._async_delete_external_account_dns(account_id, current)
                    await self._async_delete_pending_external_account_dns(account_id, current)
                except CloudflareDNSError as err:
                    current["dns_state"] = "cleanup_failed"
                    current["last_error"] = err.code
                    external[account_id] = current
                    await self._store.async_save(self._data)
                    return self.external_account_descriptor(account_id)
            external.pop(account_id, None)
            await self._store.async_save(self._data)
            return self.external_account_descriptor(account_id)

        if not self._cloudflare_ready():
            raise ValueError("cloudflare_not_configured")
        slug = requested_slug or _normalize_slug(current.get("subdomain"))
        if not slug:
            raise ValueError("invalid_remote_slug")
        for other_id, other in self._data.get("external_profiles", {}).items():
            if isinstance(other, dict) and other.get("enabled", False) and _normalize_slug(other.get("subdomain")) == slug:
                raise ValueError("remote_slug_in_use")
        for other_id, other in external.items():
            if str(other_id) == account_id or not isinstance(other, dict):
                continue
            if other.get("enabled", False) and _normalize_slug(other.get("subdomain")) == slug:
                raise ValueError("remote_slug_in_use")

        cfg = self._cloudflare()
        zone = _normalize_domain(cfg.get("zone"))
        base = _normalize_domain(cfg.get("base_domain"))
        target = _normalize_public_ipv4(cfg.get("record_target"))
        token = str(cfg.get("api_token") or "").strip()
        client = CloudflareDNSClient(self.hass, token)
        try:
            zone_id = str(cfg.get("zone_id") or "") or await client.async_zone_id(zone)
            host = f"{slug}.{base}"
            record_id = await client.async_ensure_a_record(
                zone_id=zone_id,
                name=host,
                target=target,
                comment=self._external_account_comment(account_id),
                record_id=(
                    str(current.get("dns_record_id") or "")
                    if _normalize_domain(current.get("dns_name")) == host else ""
                ),
            )
        except CloudflareDNSError as err:
            raise ValueError(err.code) from err

        old = current if current.get("enabled", False) else None
        row = {
            "enabled": True,
            "subdomain": slug,
            "dns_record_id": record_id,
            "dns_name": host,
            "dns_zone_id": zone_id,
            "dns_state": "active",
            "last_error": "",
            "cleanup_dns_record_id": str(current.get("cleanup_dns_record_id") or ""),
            "cleanup_dns_name": _normalize_domain(current.get("cleanup_dns_name")),
            "cleanup_dns_zone_id": str(current.get("cleanup_dns_zone_id") or ""),
        }
        external[account_id] = row
        cfg["zone_id"] = zone_id
        await self._store.async_save(self._data)

        if old and _normalize_domain(old.get("dns_name")) and _normalize_domain(old.get("dns_name")) != host:
            try:
                await self._async_delete_external_account_dns(account_id, old)
            except CloudflareDNSError as err:
                row["dns_state"] = "active_cleanup_pending"
                row["last_error"] = err.code
                row["cleanup_dns_record_id"] = str(old.get("dns_record_id") or "")
                row["cleanup_dns_name"] = _normalize_domain(old.get("dns_name"))
                row["cleanup_dns_zone_id"] = str(old.get("dns_zone_id") or "")
                external[account_id] = row
                await self._store.async_save(self._data)
                return self.external_account_descriptor(account_id)
        try:
            await self._async_delete_pending_external_account_dns(account_id, row)
        except CloudflareDNSError as err:
            row["dns_state"] = "active_cleanup_pending"
            row["last_error"] = err.code
            external[account_id] = row
            await self._store.async_save(self._data)
        return self.external_account_descriptor(account_id)

    async def async_reconcile_external_profiles(self) -> None:
        """Best-effort startup repair of profile login gates and DNS records."""
        await self.async_load()
        async with self._mutation_lock:
            # Repair HA's local-only flag even if Cloudflare is temporarily
            # unavailable. This makes persisted External access authoritative
            # after an upgrade/restart and immediately re-locks disabled users.
            for profile_id in list(self._data.get("external_profiles", {})):
                await self._async_sync_bound_profile_user_local_only(str(profile_id))
            if not self._cloudflare_ready():
                return
            for profile_id, row in list(self._data.get("external_profiles", {}).items()):
                if not isinstance(row, dict):
                    continue
                if not row.get("enabled", False):
                    if row.get("dns_state") != "cleanup_failed":
                        continue
                    try:
                        await self._async_delete_external_dns(str(profile_id), row)
                        await self._async_delete_pending_external_dns(str(profile_id), row)
                    except CloudflareDNSError as err:
                        row["last_error"] = err.code
                        self._data["external_profiles"][str(profile_id)] = row
                    else:
                        self._data["external_profiles"].pop(str(profile_id), None)
                    continue
                try:
                    await self._async_set_external_profile(
                        profile_entry_id=str(profile_id),
                        enabled=True,
                        subdomain=str(row.get("subdomain") or ""),
                    )
                except (ValueError, CloudflareDNSError) as err:
                    row["dns_state"] = "error"
                    row["last_error"] = str(getattr(err, "code", err))[:128]
                    self._data["external_profiles"][str(profile_id)] = row
            for account_id, row in list(self._data.get("external_accounts", {}).items()):
                if not isinstance(row, dict):
                    continue
                if not row.get("enabled", False):
                    if row.get("dns_state") != "cleanup_failed":
                        continue
                    try:
                        await self._async_delete_external_account_dns(str(account_id), row)
                        await self._async_delete_pending_external_account_dns(str(account_id), row)
                    except CloudflareDNSError as err:
                        row["last_error"] = err.code
                        self._data["external_accounts"][str(account_id)] = row
                    else:
                        self._data["external_accounts"].pop(str(account_id), None)
                    continue
                try:
                    await self._async_set_external_account(
                        account_id=str(account_id),
                        enabled=True,
                        subdomain=str(row.get("subdomain") or ""),
                    )
                except (ValueError, CloudflareDNSError) as err:
                    row["dns_state"] = "error"
                    row["last_error"] = str(getattr(err, "code", err))[:128]
                    self._data["external_accounts"][str(account_id)] = row
            await self._store.async_save(self._data)

    def _has_other_admin(self, user_id: str) -> bool:
        return any(
            uid != str(user_id)
            and isinstance(row, dict)
            and row.get("enabled", True)
            and row.get("role") == ROLE_ADMIN
            for uid, row in self._data.get("accounts", {}).items()
        )

    def _default_remote_slug(self, user, entry) -> str:
        """Create a stable free logical subdomain for a remote Fitness account."""
        candidates = [
            _slug_seed(getattr(user, "name", "")),
            _slug_seed(({**entry.data, **entry.options}.get("profile_name")) or entry.title),
            f"fitness-{str(user.id)[:8].lower()}",
        ]
        used = {
            _normalize_slug(row.get("remote_slug"))
            for row in self._data.get("accounts", {}).values()
            if isinstance(row, dict) and row.get("enabled", True)
        }
        for seed in candidates:
            if seed and seed not in used and _normalize_slug(seed):
                return seed
        base = f"fitness-{str(user.id)[:8].lower()}"
        for suffix in range(2, 1000):
            candidate = f"{base[:58]}-{suffix}"
            if candidate not in used and _normalize_slug(candidate):
                return candidate
        raise ValueError("remote_slug_in_use")

    async def async_bind_account(
        self,
        connection,
        *,
        user_id: str,
        role: str,
        profile_entry_id: str | None = None,
        remote_slug: str | None = None,
        view_profile_entry_ids: list[str] | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Atomically validate and persist one account/profile binding."""
        async with self._mutation_lock:
            return await self._async_bind_account(
                connection,
                user_id=user_id,
                role=role,
                profile_entry_id=profile_entry_id,
                remote_slug=remote_slug,
                view_profile_entry_ids=view_profile_entry_ids,
                language=language,
            )

    async def _async_bind_account(
        self,
        connection,
        *,
        user_id: str,
        role: str,
        profile_entry_id: str | None = None,
        remote_slug: str | None = None,
        view_profile_entry_ids: list[str] | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        await self.async_require_admin(connection)
        role = str(role or "").strip().lower()
        if role not in ROLES:
            raise ValueError("invalid_role")
        user = await self.hass.auth.async_get_user(str(user_id))
        if user is None or getattr(user, "system_generated", False):
            raise ValueError("user_not_found")
        if not user.is_active:
            raise ValueError("user_inactive")

        current = self._account(user.id)
        # ``language`` remains in the command signature for upgrade compatibility,
        # but is deliberately ignored. Profile configuration is the sole language
        # authority for Fitness TV, menus and TTS.
        _ = language

        row: dict[str, Any] = {
            "role": role,
            "ha_user_id": user.id,
            "enabled": True,
        }
        previous_local_only = (
            current.get("previous_local_only")
            if isinstance(current, dict) and "previous_local_only" in current
            else bool(user.local_only)
        )

        # A Fitness administrator is an access role, not a replacement for the
        # administrator's own Fitness profile.  Keep/allow one optional profile
        # binding for admins while local/remote users still require exactly one.
        requested_profile_id = str(profile_entry_id or "").strip()
        if (
            role == ROLE_ADMIN
            and not requested_profile_id
            and profile_entry_id is None
            and isinstance(current, dict)
        ):
            requested_profile_id = str(current.get("profile_entry_id") or "").strip()

        profile_entry = None
        if requested_profile_id:
            profile_entry = self.hass.config_entries.async_get_entry(requested_profile_id)
            if (
                profile_entry is None
                or profile_entry.domain != DOMAIN
                or profile_entry.data.get("entry_type") in {"live_hub", "devices_hub"}
            ):
                raise ValueError("profile_not_found")
            for existing_user_id, existing in self._data["accounts"].items():
                if existing_user_id == user.id or not isinstance(existing, dict):
                    continue
                if (
                    existing.get("enabled", True)
                    and existing.get("role") in {ROLE_ADMIN, ROLE_LOCAL, ROLE_REMOTE}
                    and existing.get("profile_entry_id") == requested_profile_id
                ):
                    raise ValueError("profile_already_assigned")
            row["profile_entry_id"] = requested_profile_id
        elif role in {ROLE_LOCAL, ROLE_REMOTE}:
            raise ValueError("profile_not_found")

        # Account assignment never mutates profile language. The profile's own
        # settings remain authoritative and survive account-role changes.

        if view_profile_entry_ids is None and isinstance(current, dict):
            requested_view_ids = self._view_profile_ids(current)
        else:
            requested_view_ids = {
                str(item).strip()
                for item in (view_profile_entry_ids or [])
                if str(item).strip()
            }
        requested_view_ids.discard(requested_profile_id)
        if role == ROLE_ADMIN:
            requested_view_ids.clear()
        known_profile_ids = self._all_profile_ids()
        if not requested_view_ids.issubset(known_profile_ids):
            raise ValueError("profile_not_found")
        if requested_view_ids:
            row["view_profile_entry_ids"] = sorted(requested_view_ids)

        if role == ROLE_ADMIN:
            if not user.is_admin:
                raise ValueError("admin_requires_ha_admin")
            if isinstance(current, dict) and current.get("role") in {ROLE_LOCAL, ROLE_REMOTE}:
                await self.hass.auth.async_update_user(
                    user, local_only=bool(previous_local_only)
                )
        else:
            if user.is_admin:
                raise ValueError("fitness_user_must_not_be_ha_admin")
            row["previous_local_only"] = bool(previous_local_only)
            assert profile_entry is not None
            if role == ROLE_LOCAL:
                # Keep HA's own local-only gate as defense in depth unless this
                # exact profile was explicitly published for external access.
                await self.hass.auth.async_update_user(
                    user,
                    local_only=not bool(
                        self._external_profile_host(profile_entry.entry_id)
                    ),
                )
            else:
                # Remote URLs are profile-owned now. Do not invent a second account
                # slug: once External access is configured, the exact profile host
                # is the only public hostname for this account. Preserve an older
                # pre-Cloudflare slug only while that profile has never adopted the
                # explicit external-access model, so upgrades do not break legacy
                # installations in one step.
                external_state = self._external_profile(profile_entry.entry_id)
                legacy_slug = _normalize_slug((current or {}).get("remote_slug"))
                if external_state is None and legacy_slug:
                    row["remote_slug"] = legacy_slug
                effective_remote_host = self._remote_account_host(row)
                await self.hass.auth.async_update_user(
                    user, local_only=not bool(effective_remote_host)
                )

        self._data["accounts"][user.id] = row
        await self._store.async_save(self._data)
        return await self.async_admin_snapshot(connection)

    async def async_remove_account(self, connection, user_id: str) -> dict[str, Any]:
        """Remove one binding without racing another access-policy update."""
        async with self._mutation_lock:
            return await self._async_remove_account(connection, user_id)

    async def _async_remove_account(self, connection, user_id: str) -> dict[str, Any]:
        await self.async_require_admin(connection)
        user_id = str(user_id)
        account = self._account(user_id)
        profile_id = str((account or {}).get("profile_entry_id") or "")
        removed = self._data["accounts"].pop(user_id, None)
        if isinstance(removed, dict) and removed.get("role") in {ROLE_LOCAL, ROLE_REMOTE}:
            user = await self.hass.auth.async_get_user(user_id)
            if user is not None and "previous_local_only" in removed:
                await self.hass.auth.async_update_user(
                    user, local_only=bool(removed.get("previous_local_only"))
                )
        if profile_id and self._external_profile(profile_id):
            await self._async_set_external_profile(
                profile_entry_id=profile_id,
                enabled=False,
                subdomain=None,
            )
        await self._store.async_save(self._data)
        return await self.async_admin_snapshot(connection)

    async def async_remove_profile(self, connection, profile_entry_id: str) -> dict[str, Any]:
        """Remove a profile and its access records as one serialized operation."""
        async with self._mutation_lock:
            return await self._async_remove_profile(connection, profile_entry_id)

    async def _async_remove_profile(self, connection, profile_entry_id: str) -> dict[str, Any]:
        await self.async_require_admin(connection)
        entry = self.hass.config_entries.async_get_entry(str(profile_entry_id))
        if entry is None or entry.domain != DOMAIN or entry.data.get("entry_type") in {"live_hub", "devices_hub"}:
            raise ValueError("profile_not_found")
        if self._external_profile(entry.entry_id):
            await self._async_set_external_profile(
                profile_entry_id=entry.entry_id,
                enabled=False,
                subdomain=None,
            )
        # Remove any ownership binding and scrub view-only grants before
        # removing the backend entry.
        for user_id, row in list(self._data["accounts"].items()):
            if not isinstance(row, dict):
                continue
            if row.get("profile_entry_id") == entry.entry_id:
                self._data["accounts"].pop(user_id, None)
                user = await self.hass.auth.async_get_user(str(user_id))
                if user is not None and "previous_local_only" in row:
                    await self.hass.auth.async_update_user(
                        user, local_only=bool(row.get("previous_local_only"))
                    )
                continue
            view_ids = self._view_profile_ids(row)
            if entry.entry_id in view_ids:
                view_ids.discard(entry.entry_id)
                if view_ids:
                    row["view_profile_entry_ids"] = sorted(view_ids)
                else:
                    row.pop("view_profile_entry_ids", None)
        await self._store.async_save(self._data)
        # A complete backend-profile removal also owns the matching Fitness TV
        # profile state. Scrub its cards, music choices, playlists and other TV
        # preferences instead of leaving an orphan keyed by the deleted entry.
        from .tv_dashboard import get_tv_dashboard_hub
        await get_tv_dashboard_hub(self.hass).async_remove_profile_preferences(entry.entry_id)
        await self.hass.config_entries.async_remove(entry.entry_id)
        return await self.async_admin_snapshot(connection)


def get_fitness_access_controller(hass: HomeAssistant) -> FitnessAccessController:
    data = hass.data.setdefault(DOMAIN, {})
    controller = data.get(ACCESS_CONTROLLER_KEY)
    if controller is None:
        controller = FitnessAccessController(hass)
        data[ACCESS_CONTROLLER_KEY] = controller
    return controller


def _external_gate_response(controller: FitnessAccessController, profile_id: str) -> web.Response:
    """Return a small Fitness-branded pre-authentication entry page.

    The page never accepts a password. It clears Home Assistant's browser token
    cache for this public origin and then hands authentication back to Home
    Assistant, preserving HA password/MFA/provider policy instead of creating a
    second credential database inside a custom integration.
    """
    entry = controller.hass.config_entries.async_get_entry(str(profile_id))
    language = controller._profile_language(entry) if entry is not None else "en"
    copy = {
        "en": ("Fitness sign in", "Sign in to open your Fitness dashboards.", "Home Assistant securely verifies your password and MFA. HA-Fitness never stores your password.", "Sign in"),
        "el": ("Σύνδεση Fitness", "Συνδεθείτε για να ανοίξετε τους πίνακες Fitness.", "Το Home Assistant επαληθεύει με ασφάλεια τον κωδικό και το MFA. Το HA-Fitness δεν αποθηκεύει τον κωδικό σας.", "Σύνδεση"),
        "de": ("Fitness-Anmeldung", "Melde dich an, um deine Fitness-Dashboards zu öffnen.", "Home Assistant prüft Passwort und MFA sicher. HA-Fitness speichert dein Passwort nicht.", "Anmelden"),
    }.get(language, ("Fitness sign in", "Sign in to open your Fitness dashboards.", "Home Assistant securely verifies your password and MFA. HA-Fitness never stores your password.", "Sign in"))
    profile_name = str(({**entry.data, **entry.options}.get("profile_name") if entry is not None else "") or (entry.title if entry is not None else "Fitness"))
    nonce = secrets.token_urlsafe(18)
    title, intro, auth_note, action = (html.escape(str(value)) for value in copy)
    safe_profile = html.escape(profile_name)
    body = f"""<!doctype html><html lang="{html.escape(language)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark light"><title>{title}</title><style nonce="{nonce}">:root{{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;min-height:100dvh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 25% 18%,#173b55 0,#0d151d 38%,#080b10 76%);color:#f5f7fa}}main{{width:min(440px,100%);padding:28px;border:1px solid rgba(255,255,255,.12);border-radius:22px;background:rgba(24,28,33,.94);box-shadow:0 24px 70px rgba(0,0,0,.45)}}.brand{{display:flex;align-items:center;gap:10px;color:#41bdf5;font-weight:800;letter-spacing:.02em}}h1{{font-size:28px;margin:18px 0 8px}}h2{{font-size:15px;margin:0 0 20px;color:#aeb8c2;font-weight:650}}p{{line-height:1.5;color:#d7dde3}}small{{display:block;line-height:1.45;color:#9ba6b2;margin-top:18px}}button{{width:100%;margin-top:20px;min-height:48px;border:0;border-radius:13px;background:#41bdf5;color:#071018;font-size:16px;font-weight:800;cursor:pointer}}button:focus-visible{{outline:3px solid white;outline-offset:3px}}</style></head><body><main><div class="brand">HA-Fitness</div><h1>{title}</h1><h2>{safe_profile}</h2><p>{intro}</p><form method="get" action="{_EXTERNAL_GATE_PATH}"><button type="submit">{action}</button></form><small>{auth_note}</small></main><script nonce="{nonce}">try{{localStorage.removeItem("hassTokens");sessionStorage.removeItem("hassTokens");}}catch(_e){{}}</script></body></html>"""
    response = web.Response(
        text=body,
        content_type="text/html",
        charset="utf-8",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": f"default-src 'none'; style-src 'nonce-{nonce}'; script-src 'nonce-{nonce}'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        },
    )
    # Visiting the public root intentionally starts a fresh Fitness entry session.
    response.del_cookie(_EXTERNAL_GATE_COOKIE, path="/")
    return response


def _external_document_navigation(request: web.Request) -> bool:
    """Return whether this request represents a browser page navigation."""
    if request.method not in {"GET", "HEAD"}:
        return False
    destination = str(request.headers.get("Sec-Fetch-Dest") or "").lower()
    accept = str(request.headers.get("Accept") or "").lower()
    return destination in {"document", "iframe"} or "text/html" in accept


def async_register_external_host_routing(hass: HomeAssistant) -> None:
    """Register the independent Fitness-account portal and Host router.

    Kept under the legacy function name so dashboard startup and older tests do
    not need a second lifecycle hook. External hostnames are now account-owned;
    they never fall through to generic Home Assistant pages.
    """
    from .fitness_accounts import (
        async_register_fitness_account_http_views,
        async_register_fitness_portal_routing,
    )

    async_register_fitness_account_http_views(hass)
    async_register_fitness_portal_routing(hass)

# WebSocket admin/access API -------------------------------------------------
import voluptuous as vol
from homeassistant.components import websocket_api


@websocket_api.websocket_command({vol.Required("type"): "fitness/access/info"})
@websocket_api.async_response
async def websocket_fitness_access_info(hass: HomeAssistant, connection, msg) -> None:
    controller = get_fitness_access_controller(hass)
    connection.send_result(msg["id"], await controller.async_descriptor(connection))


@websocket_api.websocket_command({vol.Required("type"): "fitness/access/admin"})
@websocket_api.async_response
async def websocket_fitness_access_admin(hass: HomeAssistant, connection, msg) -> None:
    controller = get_fitness_access_controller(hass)
    connection.send_result(msg["id"], await controller.async_admin_snapshot(connection))


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/access/settings/save",
    vol.Optional("remote_base_domain"): vol.All(str, vol.Length(max=253)),
    vol.Optional("dashboard_max"): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_DASHBOARD_MAX)),
    vol.Optional("cloudflare_zone"): vol.All(str, vol.Length(max=253)),
    vol.Optional("cloudflare_base_domain"): vol.All(str, vol.Length(max=253)),
    vol.Optional("cloudflare_api_token"): vol.All(str, vol.Length(max=512)),
    vol.Optional("cloudflare_record_target"): vol.All(str, vol.Length(max=64)),
    vol.Optional("clear_cloudflare_api_token", default=False): bool,
})
@websocket_api.async_response
async def websocket_fitness_access_settings_save(hass: HomeAssistant, connection, msg) -> None:
    controller = get_fitness_access_controller(hass)
    try:
        result = await controller.async_set_access_settings(
            connection,
            domain=(str(msg.get("remote_base_domain") or "") if "remote_base_domain" in msg else None),
            dashboard_max=msg.get("dashboard_max"),
            cloudflare_zone=(str(msg.get("cloudflare_zone") or "") if "cloudflare_zone" in msg else None),
            cloudflare_base_domain=(str(msg.get("cloudflare_base_domain") or "") if "cloudflare_base_domain" in msg else None),
            cloudflare_api_token=(str(msg.get("cloudflare_api_token") or "") if "cloudflare_api_token" in msg else None),
            cloudflare_record_target=(str(msg.get("cloudflare_record_target") or "") if "cloudflare_record_target" in msg else None),
            clear_cloudflare_api_token=bool(msg.get("clear_cloudflare_api_token", False)),
        )
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    # A Remote Fitness account may have been created before Cloudflare was
    # configured or while the API was unavailable. Saving global Cloudflare
    # settings is an explicit administrator action, so retry those account-owned
    # DNS records immediately instead of requiring an HA restart or another
    # account edit. Reconciliation records per-account errors without exposing
    # the API token.
    from .fitness_accounts import get_fitness_account_controller

    await get_fitness_account_controller(hass).async_reconcile_remote_dns()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/access/external/save",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("enabled"): bool,
    vol.Optional("subdomain"): vol.All(str, vol.Length(max=63)),
})
@websocket_api.async_response
async def websocket_fitness_external_access_save(hass: HomeAssistant, connection, msg) -> None:
    controller = get_fitness_access_controller(hass)
    try:
        result = await controller.async_set_external_profile(
            connection,
            profile_entry_id=str(msg["profile_entry_id"]),
            enabled=bool(msg["enabled"]),
            subdomain=(str(msg.get("subdomain") or "") if "subdomain" in msg else None),
        )
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/access/account/save",
    vol.Required("user_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("role"): vol.In(sorted(ROLES)),
    vol.Optional("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Optional("remote_slug"): vol.All(str, vol.Length(max=63)),
    vol.Optional("view_profile_entry_ids"): vol.All(
        [vol.All(str, vol.Length(max=128))], vol.Length(max=256)
    ),
    vol.Optional("language"): vol.In(sorted(SUPPORTED_LANGUAGES)),
})
@websocket_api.async_response
async def websocket_fitness_access_account_save(hass: HomeAssistant, connection, msg) -> None:
    controller = get_fitness_access_controller(hass)
    try:
        result = await controller.async_bind_account(
            connection,
            user_id=str(msg["user_id"]),
            role=str(msg["role"]),
            profile_entry_id=(
                str(msg.get("profile_entry_id") or "")
                if "profile_entry_id" in msg
                else None
            ),
            remote_slug=str(msg.get("remote_slug") or "") or None,
            view_profile_entry_ids=(
                [str(item) for item in msg.get("view_profile_entry_ids", [])]
                if "view_profile_entry_ids" in msg
                else None
            ),
            language=(str(msg.get("language") or "") if "language" in msg else None),
        )
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/access/account/delete",
    vol.Required("user_id"): vol.All(str, vol.Length(max=128)),
})
@websocket_api.async_response
async def websocket_fitness_access_account_delete(hass: HomeAssistant, connection, msg) -> None:
    controller = get_fitness_access_controller(hass)
    try:
        result = await controller.async_remove_account(connection, str(msg["user_id"]))
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/access/profile/delete",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
})
@websocket_api.async_response
async def websocket_fitness_access_profile_delete(hass: HomeAssistant, connection, msg) -> None:
    controller = get_fitness_access_controller(hass)
    try:
        result = await controller.async_remove_profile(connection, str(msg["profile_entry_id"]))
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(msg["id"], result)


def async_register_fitness_access_websocket_commands(hass: HomeAssistant) -> None:
    """Register Fitness account/access commands once per HA process."""
    websocket_api.async_register_command(hass, websocket_fitness_access_info)
    websocket_api.async_register_command(hass, websocket_fitness_access_settings_save)
    # The previous HA-user binding/profile-hostname mutation commands are kept
    # only as migration code and are intentionally no longer registered.
    websocket_api.async_register_command(hass, websocket_fitness_access_profile_delete)
