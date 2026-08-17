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

Remote subdomains use a wildcard-DNS model.  Fitness owns the logical slug and
access policy, while DNS/TLS/reverse-proxy provisioning remains infrastructure
outside Home Assistant.  This means removing a remote account immediately makes
its wildcard hostname useless without needing to mutate public DNS.
"""
from __future__ import annotations

from ipaddress import ip_address
import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.storage import Store

from .const import CONF_LANGUAGE, DOMAIN, SUPPORTED_LANGUAGES

ACCESS_STORE_VERSION = 1
ACCESS_STORE_KEY = "fitness.access_control"
ACCESS_CONTROLLER_KEY = "_fitness_access_control"

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
        self._data: dict[str, Any] = {
            "remote_base_domain": "",
            "accounts": {},
        }

    async def async_load(self) -> None:
        if self._loaded:
            return
        saved = await self._store.async_load()
        if isinstance(saved, dict):
            accounts = saved.get("accounts")
            self._data = {
                "remote_base_domain": _normalize_domain(saved.get("remote_base_domain")),
                "accounts": accounts if isinstance(accounts, dict) else {},
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
        base = _normalize_domain(self._data.get("remote_base_domain"))
        slug = _normalize_slug(account.get("remote_slug"))
        return f"{slug}.{base}" if base and slug else ""

    def _session_allowed(self, connection, account: dict[str, Any]) -> bool:
        role = account.get("role")
        if role == ROLE_ADMIN:
            return _is_local_remote(getattr(connection, "remote", None))
        if role == ROLE_LOCAL:
            return _is_local_remote(getattr(connection, "remote", None))
        if role == ROLE_REMOTE:
            expected = self._remote_account_host(account)
            return bool(expected and self._refresh_token_client_host(connection) == expected)
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
            if entry.data.get("entry_type") != "live_hub"
        }

    @staticmethod
    def _profile_language(entry) -> str:
        if entry is None:
            return "en"
        config = {**entry.data, **entry.options}
        return _normalize_language(config.get(CONF_LANGUAGE) or "en")

    def _account_language(self, account: dict[str, Any] | None) -> str:
        if isinstance(account, dict) and account.get("language"):
            return _normalize_language(account.get("language"))
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

    async def async_descriptor(self, connection) -> dict[str, Any]:
        await self.async_load()
        user = getattr(connection, "user", None)
        user_id = str(getattr(user, "id", "") or "")
        account = self._account(user_id)
        ha_admin = bool(
            user
            and getattr(user, "is_active", True)
            and getattr(user, "is_admin", False)
        )

        # Home Assistant administrator/owner status is the authoritative global
        # Fitness administration permission.  A Fitness account row may still
        # bind that administrator to their own profile, but it can never remove
        # their HA-admin rights or make the admin dashboard depend on a profile.
        if ha_admin:
            profile_id = str((account or {}).get("profile_entry_id") or "") or None
            return {
                "role": ROLE_ADMIN,
                "is_admin": True,
                "ha_admin": True,
                "can_manage": True,
                "profile_entry_id": profile_id,
                "view_profile_entry_ids": sorted(self._view_profile_ids(account)),
                "remote_slug": None,
                "remote_url": None,
                "language": self._account_language(account),
                "session_allowed": True,
            }

        if account is None:
            return {
                "role": "none",
                "is_admin": False,
                "ha_admin": False,
                "can_manage": False,
                "profile_entry_id": None,
                "view_profile_entry_ids": [],
                "remote_slug": None,
                "remote_url": None,
                "language": _normalize_language(getattr(self.hass.config, "language", "en")),
                "session_allowed": False,
            }

        role = str(account.get("role") or "none")
        session_allowed = self._session_allowed(connection, account)
        expected_host = self._remote_account_host(account) if role == ROLE_REMOTE else ""
        return {
            "role": role,
            "is_admin": False,
            "ha_admin": False,
            "can_manage": False,
            "profile_entry_id": str(account.get("profile_entry_id") or "") or None,
            "view_profile_entry_ids": sorted(self._view_profile_ids(account)),
            "remote_slug": str(account.get("remote_slug") or "") or None,
            "remote_url": (
                f"https://{expected_host}/fitness-tv/profile-{account.get('profile_entry_id')}"
                if expected_host and account.get("profile_entry_id")
                else None
            ),
            "language": self._account_language(account),
            "session_allowed": session_allowed,
        }

    async def async_visible_profile_ids(self, connection, *, cast_hub=None) -> set[str]:
        await self.async_load()
        if self._is_cast_system_connection(connection):
            if cast_hub is None:
                return set()
            return {
                entry.entry_id
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.data.get("entry_type") != "live_hub"
                and cast_hub.has_cast_expectation(entry.entry_id)
            }

        user = getattr(connection, "user", None)
        if bool(user and getattr(user, "is_active", True) and getattr(user, "is_admin", False)):
            return self._all_profile_ids()

        account = self._account(getattr(user, "id", None))
        if account is None or not self._session_allowed(connection, account):
            return set()
        visible = self._view_profile_ids(account)
        profile_id = str(account.get("profile_entry_id") or "")
        if profile_id:
            visible.add(profile_id)
        return visible & self._all_profile_ids()

    async def async_control_profile_ids(self, connection, *, cast_hub=None) -> set[str]:
        """Return profiles this connection may actively control/configure."""
        await self.async_load()
        if self._is_cast_system_connection(connection):
            return await self.async_visible_profile_ids(connection, cast_hub=cast_hub)

        user = getattr(connection, "user", None)
        if bool(user and getattr(user, "is_active", True) and getattr(user, "is_admin", False)):
            return self._all_profile_ids()

        account = self._account(getattr(user, "id", None))
        if account is None or not self._session_allowed(connection, account):
            return set()
        profile_id = str(account.get("profile_entry_id") or "")
        return {profile_id} if profile_id and profile_id in self._all_profile_ids() else set()

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
        user = getattr(connection, "user", None)
        if not (
            user
            and getattr(user, "is_active", True)
            and getattr(user, "is_admin", False)
        ):
            raise Unauthorized
        account = self._account(getattr(user, "id", None))
        return account or {
            "role": ROLE_ADMIN,
            "ha_user_id": str(getattr(user, "id", "") or ""),
            "enabled": True,
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
            if entry.data.get("entry_type") == "live_hub":
                continue
            config = {**entry.data, **entry.options}
            prefs = await hub.async_preferences(entry.entry_id)
            row = {
                "entry_id": entry.entry_id,
                "name": str(config.get("profile_name") or entry.title or entry.entry_id),
                "language": self._profile_language(entry),
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
        for user in await self.hass.auth.async_get_users():
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
                "view_profile_entry_ids": sorted(self._view_profile_ids(bound)),
                "remote_slug": str(bound.get("remote_slug") or "") if bound else None,
                "language": _normalize_language(
                    (bound or {}).get("language")
                    or (bound_profile or {}).get("language")
                    or getattr(self.hass.config, "language", "en")
                ),
            })
        return {
            "remote_base_domain": self._data.get("remote_base_domain") or "",
            "supported_languages": dict(SUPPORTED_LANGUAGES),
            "users": sorted(users, key=lambda item: item["name"].casefold()),
            "profiles": sorted(profile_rows, key=lambda item: item["name"].casefold()),
        }

    async def async_set_remote_base_domain(self, connection, domain: str) -> dict[str, Any]:
        await self.async_require_admin(connection)
        normalized = _normalize_domain(domain)
        if domain and not normalized:
            raise ValueError("invalid_remote_base_domain")
        self._data["remote_base_domain"] = normalized
        await self._store.async_save(self._data)
        return await self.async_admin_snapshot(connection)

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
        selected_language = _normalize_language(
            language if language is not None
            else (current or {}).get("language") or getattr(self.hass.config, "language", "en")
        )

        row: dict[str, Any] = {
            "role": role,
            "ha_user_id": user.id,
            "enabled": True,
            "language": selected_language,
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
                or profile_entry.data.get("entry_type") == "live_hub"
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

        if profile_entry is not None:
            # The backend user's language is authoritative for profile menus,
            # Fitness TV and language-aware local TTS. Update in place so an
            # active workout is not interrupted by a config-entry reload.
            options = dict(profile_entry.options)
            options[CONF_LANGUAGE] = selected_language
            self.hass.config_entries.async_update_entry(profile_entry, options=options)
            manager = self.hass.data.get(DOMAIN, {}).get(profile_entry.entry_id)
            if manager is not None and isinstance(getattr(manager, "config", None), dict):
                manager.config[CONF_LANGUAGE] = selected_language

        if view_profile_entry_ids is None and isinstance(current, dict):
            requested_view_ids = self._view_profile_ids(current)
        else:
            requested_view_ids = {
                str(item).strip()
                for item in (view_profile_entry_ids or [])
                if str(item).strip()
            }
        requested_view_ids.discard(requested_profile_id)
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
                # HA itself will also reject future remote logins for this user.
                await self.hass.auth.async_update_user(user, local_only=True)
            else:
                slug = _normalize_slug(remote_slug)
                if remote_slug and not slug:
                    raise ValueError("invalid_remote_slug")
                if not _normalize_domain(self._data.get("remote_base_domain")):
                    raise ValueError("remote_base_domain_required")
                if not slug:
                    slug = self._default_remote_slug(user, profile_entry)
                for existing_user_id, existing in self._data["accounts"].items():
                    if existing_user_id == user.id or not isinstance(existing, dict):
                        continue
                    if existing.get("enabled", True) and existing.get("remote_slug") == slug:
                        raise ValueError("remote_slug_in_use")
                row["remote_slug"] = slug
                await self.hass.auth.async_update_user(user, local_only=False)

        self._data["accounts"][user.id] = row
        await self._store.async_save(self._data)
        return await self.async_admin_snapshot(connection)

    async def async_remove_account(self, connection, user_id: str) -> dict[str, Any]:
        await self.async_require_admin(connection)
        user_id = str(user_id)
        account = self._account(user_id)
        removed = self._data["accounts"].pop(user_id, None)
        if isinstance(removed, dict) and removed.get("role") in {ROLE_LOCAL, ROLE_REMOTE}:
            user = await self.hass.auth.async_get_user(user_id)
            if user is not None and "previous_local_only" in removed:
                await self.hass.auth.async_update_user(
                    user, local_only=bool(removed.get("previous_local_only"))
                )
        await self._store.async_save(self._data)
        return await self.async_admin_snapshot(connection)

    async def async_remove_profile(self, connection, profile_entry_id: str) -> dict[str, Any]:
        await self.async_require_admin(connection)
        entry = self.hass.config_entries.async_get_entry(str(profile_entry_id))
        if entry is None or entry.domain != DOMAIN or entry.data.get("entry_type") == "live_hub":
            raise ValueError("profile_not_found")
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
        await self.hass.config_entries.async_remove(entry.entry_id)
        return await self.async_admin_snapshot(connection)


def get_fitness_access_controller(hass: HomeAssistant) -> FitnessAccessController:
    data = hass.data.setdefault(DOMAIN, {})
    controller = data.get(ACCESS_CONTROLLER_KEY)
    if controller is None:
        controller = FitnessAccessController(hass)
        data[ACCESS_CONTROLLER_KEY] = controller
    return controller

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
    vol.Optional("remote_base_domain", default=""): str,
})
@websocket_api.async_response
async def websocket_fitness_access_settings_save(hass: HomeAssistant, connection, msg) -> None:
    controller = get_fitness_access_controller(hass)
    try:
        result = await controller.async_set_remote_base_domain(
            connection, str(msg.get("remote_base_domain") or "")
        )
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/access/account/save",
    vol.Required("user_id"): str,
    vol.Required("role"): vol.In(sorted(ROLES)),
    vol.Optional("profile_entry_id"): str,
    vol.Optional("remote_slug"): str,
    vol.Optional("view_profile_entry_ids"): [str],
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
    vol.Required("user_id"): str,
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
    vol.Required("profile_entry_id"): str,
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
    websocket_api.async_register_command(hass, websocket_fitness_access_admin)
    websocket_api.async_register_command(hass, websocket_fitness_access_settings_save)
    websocket_api.async_register_command(hass, websocket_fitness_access_account_save)
    websocket_api.async_register_command(hass, websocket_fitness_access_account_delete)
    websocket_api.async_register_command(hass, websocket_fitness_access_profile_delete)
