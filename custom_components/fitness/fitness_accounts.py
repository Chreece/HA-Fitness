"""Independent HA-Fitness accounts, authentication and restricted web portal.

Fitness accounts are deliberately separate from Home Assistant users.  Home
Assistant administrators retain an emergency/bootstrap management path from the
local HA UI, but normal Fitness users authenticate only against this private
store and receive a server-side Fitness session with profile-scoped ACLs.

The public browser never receives a Home Assistant access token.  Remote/local
Fitness sessions call a narrow HTTP bridge which reuses the existing Fitness
backend handlers with a synthetic Fitness principal, so every profile read/write
continues through the same access checks as the native dashboard.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import html
import inspect
import json
import logging
import re
import secrets
from typing import Any
import uuid

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.storage import Store

from .const import CONF_LANGUAGE, DOMAIN, SUPPORTED_LANGUAGES

_LOGGER = logging.getLogger(__name__)

ACCOUNT_STORE_VERSION = 1
ACCOUNT_STORE_KEY = "fitness.accounts"
ACCOUNT_CONTROLLER_KEY = "_fitness_account_controller"
PORTAL_REGISTERED_KEY = "_fitness_account_portal_registered"
PORTAL_MIDDLEWARE_KEY = "_fitness_account_portal_middleware"
ACCOUNT_WS_REGISTERED_KEY = "_fitness_account_ws_registered"

ROLE_ADMIN = "admin"
ROLE_ADMIN_USER = "admin_user"
ROLE_USER = "user"
ROLES = {ROLE_ADMIN, ROLE_ADMIN_USER, ROLE_USER}
ADMIN_ROLES = {ROLE_ADMIN, ROLE_ADMIN_USER}

NETWORK_LOCAL_ONLY = "local_only"
NETWORK_REMOTE_ONLY = "remote_only"
NETWORK_LOCAL_REMOTE = "local_remote"
NETWORK_ACCESS_MODES = {NETWORK_LOCAL_ONLY, NETWORK_REMOTE_ONLY, NETWORK_LOCAL_REMOTE}

# Accepted only while loading/migrating stores from the pre-v139 model where
# role and network reachability were encoded in the same field.
_LEGACY_ROLE_LOCAL = "local"
_LEGACY_ROLE_REMOTE = "remote"
_LEGACY_ROLE_REMOTE_LOCAL = "remote_local"
_LEGACY_ROLES = {_LEGACY_ROLE_LOCAL, _LEGACY_ROLE_REMOTE, _LEGACY_ROLE_REMOTE_LOCAL}


def _is_admin_role(role: Any) -> bool:
    return str(role or "") in ADMIN_ROLES


def _role_requires_profile(role: Any) -> bool:
    return str(role or "") in {ROLE_ADMIN_USER, ROLE_USER}


def _normalized_role_and_network(
    role: Any,
    network_access: Any = None,
    *,
    remote_enabled: bool = False,
    profile_entry_id: Any = None,
) -> tuple[str, str]:
    """Normalize new role/network fields and migrate the old combined roles."""
    raw_role = str(role or "").strip().lower()
    raw_network = str(network_access or "").strip().lower()
    if raw_role == _LEGACY_ROLE_LOCAL:
        return ROLE_USER, NETWORK_LOCAL_ONLY
    if raw_role == _LEGACY_ROLE_REMOTE:
        return ROLE_USER, NETWORK_REMOTE_ONLY
    if raw_role == _LEGACY_ROLE_REMOTE_LOCAL:
        return ROLE_USER, NETWORK_LOCAL_REMOTE
    if raw_role not in ROLES:
        return raw_role, raw_network
    if raw_network not in NETWORK_ACCESS_MODES:
        # Old administrators had only a remote_enabled flag. An administrator
        # with a bound profile was effectively also a Fitness user.
        if raw_role == ROLE_ADMIN and profile_entry_id:
            raw_role = ROLE_ADMIN_USER
        raw_network = NETWORK_LOCAL_REMOTE if remote_enabled else NETWORK_LOCAL_ONLY
    return raw_role, raw_network


def _account_remote_enabled(row: dict[str, Any] | None) -> bool:
    """Return whether this account is allowed to use its assigned remote host."""
    if not isinstance(row, dict):
        return False
    _role, network = _normalized_role_and_network(
        row.get("role"),
        row.get("network_access"),
        remote_enabled=bool(row.get("remote_enabled", False)),
        profile_entry_id=row.get("profile_entry_id"),
    )
    return network in {NETWORK_REMOTE_ONLY, NETWORK_LOCAL_REMOTE}


def _account_local_enabled(row: dict[str, Any] | None) -> bool:
    """Return whether this account is allowed to authenticate from the LAN."""
    if not isinstance(row, dict):
        return False
    _role, network = _normalized_role_and_network(
        row.get("role"),
        row.get("network_access"),
        remote_enabled=bool(row.get("remote_enabled", False)),
        profile_entry_id=row.get("profile_entry_id"),
    )
    return network in {NETWORK_LOCAL_ONLY, NETWORK_LOCAL_REMOTE}

_SESSION_COOKIE = "__Host-fitness_session"
_CAST_SESSION_COOKIE = "fitness_cast_session"
_CAST_BOOTSTRAP_TTL = timedelta(minutes=3)
_LANGUAGE_COOKIE = "__Host-fitness_language"
_LOGIN_CSRF_COOKIE = "__Host-fitness_login_csrf"
_SESSION_MAX_AGE = timedelta(hours=12)
_SESSION_IDLE_MAX = timedelta(hours=2)
_LOGIN_WINDOW = timedelta(minutes=15)
_LOGIN_MAX_FAILURES = 5
_LOCKOUT_DURATION = timedelta(minutes=15)

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}$")
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_ENTITY_RE = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z0-9_]+$")

# Small deliberately conservative list. The structural checks below do most of
# the work; this list only catches the passwords people most often try first.
_COMMON_PASSWORDS = {
    "password", "password1", "password123", "qwerty", "qwerty123", "12345678",
    "123456789", "1234567890", "letmein", "welcome", "welcome123", "admin",
    "administrator", "fitness", "homeassistant", "changeme", "iloveyou",
}

_TEMP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _utcnow()).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_username(value: Any) -> str:
    raw = str(value or "").strip()
    return raw if _USERNAME_RE.fullmatch(raw) else ""


def _normalize_slug(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if _SLUG_RE.fullmatch(raw) else ""


def _host_only(host: Any) -> str:
    value = str(host or "").strip().lower().rstrip(".")
    if value.startswith("[") and "]" in value:
        return value[1 : value.index("]")]
    if value.count(":") == 1:
        return value.rsplit(":", 1)[0]
    return value


def _client_is_local(remote: Any) -> bool:
    # Reuse the exact HA-Fitness trusted-peer logic so websocket and portal ACLs
    # agree on what "local" means after HA's trusted-proxy processing.
    from .access_control import _is_local_remote

    return _is_local_remote(remote)


def _effective_remote(request: web.Request) -> str:
    """Return the client IP after one trusted local reverse-proxy hop.

    Home Assistant normally resolves trusted proxies before views run. This
    fallback is deliberately narrow: X-Forwarded-For is considered only when
    the immediate peer is already local/private, which matches a same-host or
    LAN nginx reverse proxy without trusting arbitrary Internet headers.
    """
    peer = str(request.remote or "").strip()
    if _client_is_local(peer):
        forwarded = str(request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
        if forwarded:
            candidate = forwarded.strip("[]")
            try:
                from ipaddress import ip_address

                ip_address(candidate.split("%", 1)[0])
                return candidate
            except ValueError:
                pass
    return peer


def _same_origin_form(request: web.Request) -> bool:
    """Accept only HTTPS forms originating from this exact public hostname.

    Origin/Referer are authoritative when present.  Do not reject an otherwise
    exact-origin request merely because a reverse-proxy/browser reports
    ``Sec-Fetch-Site: same-site`` for sibling hostnames under the same base
    domain.  When neither header is available, Fetch Metadata remains a narrow
    fallback for same-origin/explicit navigation only.
    """
    from urllib.parse import urlparse

    request_host = _host_only(request.host)

    def _matches(value: str) -> bool:
        try:
            parsed = urlparse(value)
        except ValueError:
            return False
        return (
            str(parsed.scheme or "").lower() == "https"
            and _host_only(parsed.netloc) == request_host
        )

    origin = str(request.headers.get("Origin") or "").strip()
    if origin:
        return _matches(origin)

    referer = str(request.headers.get("Referer") or "").strip()
    if referer:
        return _matches(referer)

    site = str(request.headers.get("Sec-Fetch-Site") or "").strip().lower()
    return site in {"none", "same-origin"}


def _login_csrf_valid(request: web.Request, form: dict[str, str]) -> bool:
    """Validate the host-only pre-authentication login nonce.

    The nonce is rendered into the login form and also stored in a Secure,
    HttpOnly, SameSite=Strict, __Host- cookie. This remains reliable behind
    reverse proxies and browsers that report Origin/Referer/Fetch-Metadata in
    surprising ways, while a sibling subdomain or third-party site cannot read
    the hidden value or send the host-only cookie.
    """
    cookie = str(request.cookies.get(_LOGIN_CSRF_COOKIE) or "")
    submitted = str(form.get("login_csrf") or "")
    return bool(cookie and submitted and secrets.compare_digest(cookie, submitted))


async def _bounded_form_body(request: web.Request, *, limit: int = 16_384) -> dict[str, str]:
    """Read a small URL-encoded form with a hard limit, including chunked POSTs."""
    content_type = str(request.content_type or "").lower()
    if content_type != "application/x-www-form-urlencoded":
        raise web.HTTPUnsupportedMediaType(text="URL-encoded form required")
    content_length = request.content_length
    if content_length is not None and content_length > limit:
        raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=content_length)
    body = bytearray()
    while not request.content.at_eof():
        remaining = limit + 1 - len(body)
        if remaining <= 0:
            raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=len(body))
        chunk = await request.content.read(min(16_384, remaining))
        if not chunk:
            break
        body.extend(chunk)
        if len(body) > limit:
            raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=len(body))
    try:
        from urllib.parse import parse_qs

        parsed = parse_qs(bytes(body).decode("utf-8"), keep_blank_values=True, max_num_fields=12)
    except (UnicodeDecodeError, ValueError) as err:
        raise web.HTTPBadRequest(text="Invalid form") from err
    return {str(key): str(values[-1]) if values else "" for key, values in parsed.items()}


async def _bounded_json_body(request: web.Request, *, limit: int) -> dict[str, Any]:
    """Read one JSON object without letting a chunked body bypass our limit."""
    content_length = request.content_length
    if content_length is not None and content_length > limit:
        raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=content_length)
    body = bytearray()
    while not request.content.at_eof():
        remaining = limit + 1 - len(body)
        if remaining <= 0:
            raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=len(body))
        chunk = await request.content.read(min(65536, remaining))
        if not chunk:
            break
        body.extend(chunk)
        if len(body) > limit:
            raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=len(body))
    try:
        payload = json.loads(bytes(body) or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as err:
        raise web.HTTPBadRequest(text="Invalid JSON") from err
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="JSON object required")
    return payload

def _secure_request(request: web.Request) -> bool:
    if bool(request.secure) or str(request.scheme or "").lower() == "https":
        return True
    # nginx commonly terminates TLS on the same private host before forwarding to
    # Home Assistant. Only honor X-Forwarded-Proto from a local/private peer.
    return bool(
        _client_is_local(request.remote)
        and str(request.headers.get("X-Forwarded-Proto") or "").split(",", 1)[0].strip().lower()
        == "https"
    )


def _safe_text(value: Any, limit: int = 256) -> str:
    return str(value or "").strip()[:limit]


def _scrypt_hash(password: str, salt: bytes) -> str:
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32
    )
    return digest.hex()


def _password_policy(password: str, *, username: str = "", subdomain: str = "", profile_name: str = "") -> str | None:
    """Return a stable validation code, or None when the password is acceptable."""
    value = str(password or "")
    if len(value) < 14:
        return "password_too_short"
    if len(value) > 128:
        return "password_too_long"
    lowered = value.casefold()
    compact_common = re.sub(r"[^a-z0-9]", "", lowered)
    if lowered in _COMMON_PASSWORDS or compact_common in {re.sub(r"[^a-z0-9]", "", item) for item in _COMMON_PASSWORDS}:
        return "password_too_common"
    if any(sequence in compact_common for sequence in ("123456", "654321", "abcdef", "qwerty", "asdfgh", "zxcvbn")):
        return "password_too_predictable"
    classes = sum(
        bool(re.search(pattern, value))
        for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]")
    )
    if classes < 3:
        return "password_not_complex_enough"
    if re.search(r"(.)\1{4,}", value):
        return "password_too_repetitive"
    compact = re.sub(r"[^a-z0-9]", "", lowered)
    for forbidden in (username, subdomain, profile_name):
        token = re.sub(r"[^a-z0-9]", "", str(forbidden or "").casefold())
        if len(token) >= 4 and token in compact:
            return "password_contains_account_info"
    return None


def _json_safe(value: Any, *, depth: int = 0) -> Any:
    """Bound/normalize values before returning them through the public portal."""
    if depth > 8:
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str):
            return value[:32768]
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 2048:
                break
            out[str(key)[:256]] = _json_safe(item, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item, depth=depth + 1) for item in list(value)[:4096]]
    if hasattr(value, "as_dict"):
        try:
            return _json_safe(value.as_dict(), depth=depth + 1)
        except Exception:  # noqa: BLE001
            return str(value)[:1024]
    return str(value)[:1024]


def _collect_entity_ids(value: Any, output: set[str] | None = None, *, depth: int = 0) -> set[str]:
    output = output if output is not None else set()
    if depth > 10 or len(output) >= 4096:
        return output
    if isinstance(value, str):
        if _ENTITY_RE.fullmatch(value):
            output.add(value)
        return output
    if isinstance(value, dict):
        for item in value.values():
            _collect_entity_ids(item, output, depth=depth + 1)
        return output
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_entity_ids(item, output, depth=depth + 1)
    return output


@dataclass(slots=True)
class FitnessSession:
    token: str
    account_id: str
    csrf: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    host: str
    user_agent_hash: str
    language: str = "en"
    state_entity_ids: tuple[str, ...] = ()


class FitnessPortalConnection:
    """Small ActiveConnection-compatible result sink for reused Fitness handlers."""

    def __init__(self, principal: dict[str, Any], remote: str | None) -> None:
        self.fitness_principal = dict(principal)
        self.remote = str(remote or "")
        self.user = None
        self.refresh_token_id = None
        self.subscriptions: dict[int, Callable[[], None]] = {}
        self.result: Any = None
        self.error: dict[str, str] | None = None

    def send_result(self, _msg_id: int, result: Any = None) -> None:
        self.result = result

    def send_error(self, _msg_id: int, code: str, message: str, **_kwargs: Any) -> None:
        self.error = {"code": str(code), "message": str(message)}

    def send_event(self, _msg_id: int, _event: Any) -> None:
        # Subscription commands are intentionally not exposed by the request/
        # response portal bridge. Live state is refreshed by bounded polling.
        return


_PORTAL_LOGIN_TEXT: dict[str, dict[str, str]] = {
    "en":{"sign_in":"Sign in","remote":"Remote Fitness access","account":"Fitness account","username":"Username","password":"Password","privacy":"Your password is verified only by HA-Fitness. This browser receives a restricted Fitness session, never a Home Assistant access token.","language":"Language"},
    "el":{"sign_in":"Σύνδεση","remote":"Απομακρυσμένη πρόσβαση Fitness","account":"Λογαριασμός Fitness","username":"Όνομα χρήστη","password":"Κωδικός πρόσβασης","privacy":"Ο κωδικός επαληθεύεται μόνο από το HA-Fitness. Ο browser λαμβάνει περιορισμένη συνεδρία Fitness και ποτέ Home Assistant access token.","language":"Γλώσσα"},
    "de":{"sign_in":"Anmelden","remote":"Fitness-Fernzugriff","account":"Fitness-Konto","username":"Benutzername","password":"Passwort","privacy":"Das Passwort wird nur von HA-Fitness geprüft. Der Browser erhält eine eingeschränkte Fitness-Sitzung, niemals ein Home-Assistant-Zugriffstoken.","language":"Sprache"},
    "fr":{"sign_in":"Se connecter","remote":"Accès Fitness à distance","account":"Compte Fitness","username":"Nom d’utilisateur","password":"Mot de passe","privacy":"Le mot de passe est vérifié uniquement par HA-Fitness. Le navigateur reçoit une session Fitness restreinte, jamais un jeton Home Assistant.","language":"Langue"},
    "es":{"sign_in":"Iniciar sesión","remote":"Acceso remoto a Fitness","account":"Cuenta Fitness","username":"Usuario","password":"Contraseña","privacy":"La contraseña solo la verifica HA-Fitness. El navegador recibe una sesión Fitness restringida, nunca un token de Home Assistant.","language":"Idioma"},
    "it":{"sign_in":"Accedi","remote":"Accesso Fitness remoto","account":"Account Fitness","username":"Nome utente","password":"Password","privacy":"La password viene verificata solo da HA-Fitness. Il browser riceve una sessione Fitness limitata, mai un token Home Assistant.","language":"Lingua"},
    "pt":{"sign_in":"Entrar","remote":"Acesso remoto Fitness","account":"Conta Fitness","username":"Utilizador","password":"Palavra-passe","privacy":"A palavra-passe é verificada apenas pelo HA-Fitness. O navegador recebe uma sessão Fitness limitada, nunca um token do Home Assistant.","language":"Idioma"},
    "nl":{"sign_in":"Aanmelden","remote":"Fitness-toegang op afstand","account":"Fitness-account","username":"Gebruikersnaam","password":"Wachtwoord","privacy":"Het wachtwoord wordt alleen door HA-Fitness gecontroleerd. De browser krijgt een beperkte Fitness-sessie, nooit een Home Assistant-token.","language":"Taal"},
    "pl":{"sign_in":"Zaloguj","remote":"Zdalny dostęp Fitness","account":"Konto Fitness","username":"Nazwa użytkownika","password":"Hasło","privacy":"Hasło jest weryfikowane wyłącznie przez HA-Fitness. Przeglądarka otrzymuje ograniczoną sesję Fitness, nigdy token Home Assistant.","language":"Język"},
    "ru":{"sign_in":"Войти","remote":"Удалённый доступ Fitness","account":"Учётная запись Fitness","username":"Имя пользователя","password":"Пароль","privacy":"Пароль проверяется только HA-Fitness. Браузер получает ограниченную сессию Fitness и никогда не получает токен Home Assistant.","language":"Язык"},
    "uk":{"sign_in":"Увійти","remote":"Віддалений доступ Fitness","account":"Обліковий запис Fitness","username":"Ім’я користувача","password":"Пароль","privacy":"Пароль перевіряє лише HA-Fitness. Браузер отримує обмежену сесію Fitness і ніколи не отримує токен Home Assistant.","language":"Мова"},
    "tr":{"sign_in":"Oturum aç","remote":"Uzaktan Fitness erişimi","account":"Fitness hesabı","username":"Kullanıcı adı","password":"Parola","privacy":"Parola yalnızca HA-Fitness tarafından doğrulanır. Tarayıcı sınırlı bir Fitness oturumu alır; Home Assistant erişim belirteci almaz.","language":"Dil"},
    "zh":{"sign_in":"登录","remote":"远程 Fitness 访问","account":"Fitness 账户","username":"用户名","password":"密码","privacy":"密码仅由 HA-Fitness 验证。浏览器只获得受限的 Fitness 会话，不会获得 Home Assistant 访问令牌。","language":"语言"},
    "ja":{"sign_in":"ログイン","remote":"リモート Fitness アクセス","account":"Fitness アカウント","username":"ユーザー名","password":"パスワード","privacy":"パスワードは HA-Fitness だけが検証します。ブラウザーには制限された Fitness セッションのみが渡され、Home Assistant のアクセストークンは渡されません。","language":"言語"},
    "ko":{"sign_in":"로그인","remote":"원격 Fitness 접속","account":"Fitness 계정","username":"사용자 이름","password":"비밀번호","privacy":"비밀번호는 HA-Fitness에서만 확인합니다. 브라우저는 제한된 Fitness 세션만 받으며 Home Assistant 액세스 토큰은 받지 않습니다.","language":"언어"},
}


_PORTAL_APP_TEXT: dict[str, dict[str, str]] = {
    "en":{"profile":"Fitness profile","administration":"Fitness administration","view_only":"view only","account":"Account","sign_out":"Sign out","account_settings":"Account settings","login_name":"Login name","current_password":"Current password","new_password":"New password","cancel":"Cancel","save":"Save","saving":"Saving…","saved":"Saved","unable_save":"Unable to save"},
    "el":{"profile":"Προφίλ Fitness","administration":"Διαχείριση Fitness","view_only":"μόνο προβολή","account":"Λογαριασμός","sign_out":"Αποσύνδεση","account_settings":"Ρυθμίσεις λογαριασμού","login_name":"Όνομα σύνδεσης","current_password":"Τρέχων κωδικός","new_password":"Νέος κωδικός","cancel":"Ακύρωση","save":"Αποθήκευση","saving":"Αποθήκευση…","saved":"Αποθηκεύτηκε","unable_save":"Αδυναμία αποθήκευσης"},
    "de":{"profile":"Fitness-Profil","administration":"Fitness-Verwaltung","view_only":"nur ansehen","account":"Konto","sign_out":"Abmelden","account_settings":"Kontoeinstellungen","login_name":"Anmeldename","current_password":"Aktuelles Passwort","new_password":"Neues Passwort","cancel":"Abbrechen","save":"Speichern","saving":"Speichern…","saved":"Gespeichert","unable_save":"Speichern nicht möglich"},
    "fr":{"profile":"Profil Fitness","administration":"Administration Fitness","view_only":"lecture seule","account":"Compte","sign_out":"Déconnexion","account_settings":"Paramètres du compte","login_name":"Identifiant","current_password":"Mot de passe actuel","new_password":"Nouveau mot de passe","cancel":"Annuler","save":"Enregistrer","saving":"Enregistrement…","saved":"Enregistré","unable_save":"Enregistrement impossible"},
    "es":{"profile":"Perfil Fitness","administration":"Administración Fitness","view_only":"solo lectura","account":"Cuenta","sign_out":"Cerrar sesión","account_settings":"Ajustes de cuenta","login_name":"Nombre de acceso","current_password":"Contraseña actual","new_password":"Nueva contraseña","cancel":"Cancelar","save":"Guardar","saving":"Guardando…","saved":"Guardado","unable_save":"No se pudo guardar"},
    "it":{"profile":"Profilo Fitness","administration":"Amministrazione Fitness","view_only":"sola lettura","account":"Account","sign_out":"Esci","account_settings":"Impostazioni account","login_name":"Nome di accesso","current_password":"Password attuale","new_password":"Nuova password","cancel":"Annulla","save":"Salva","saving":"Salvataggio…","saved":"Salvato","unable_save":"Impossibile salvare"},
    "pt":{"profile":"Perfil Fitness","administration":"Administração Fitness","view_only":"só leitura","account":"Conta","sign_out":"Terminar sessão","account_settings":"Definições da conta","login_name":"Nome de acesso","current_password":"Palavra-passe atual","new_password":"Nova palavra-passe","cancel":"Cancelar","save":"Guardar","saving":"A guardar…","saved":"Guardado","unable_save":"Não foi possível guardar"},
    "nl":{"profile":"Fitness-profiel","administration":"Fitness-beheer","view_only":"alleen bekijken","account":"Account","sign_out":"Afmelden","account_settings":"Accountinstellingen","login_name":"Aanmeldnaam","current_password":"Huidig wachtwoord","new_password":"Nieuw wachtwoord","cancel":"Annuleren","save":"Opslaan","saving":"Opslaan…","saved":"Opgeslagen","unable_save":"Opslaan mislukt"},
    "pl":{"profile":"Profil Fitness","administration":"Administracja Fitness","view_only":"tylko podgląd","account":"Konto","sign_out":"Wyloguj","account_settings":"Ustawienia konta","login_name":"Nazwa logowania","current_password":"Obecne hasło","new_password":"Nowe hasło","cancel":"Anuluj","save":"Zapisz","saving":"Zapisywanie…","saved":"Zapisano","unable_save":"Nie można zapisać"},
    "ru":{"profile":"Профиль Fitness","administration":"Администрирование Fitness","view_only":"только просмотр","account":"Аккаунт","sign_out":"Выйти","account_settings":"Настройки аккаунта","login_name":"Имя входа","current_password":"Текущий пароль","new_password":"Новый пароль","cancel":"Отмена","save":"Сохранить","saving":"Сохранение…","saved":"Сохранено","unable_save":"Не удалось сохранить"},
    "uk":{"profile":"Профіль Fitness","administration":"Адміністрування Fitness","view_only":"лише перегляд","account":"Обліковий запис","sign_out":"Вийти","account_settings":"Налаштування облікового запису","login_name":"Ім’я входу","current_password":"Поточний пароль","new_password":"Новий пароль","cancel":"Скасувати","save":"Зберегти","saving":"Збереження…","saved":"Збережено","unable_save":"Не вдалося зберегти"},
    "tr":{"profile":"Fitness profili","administration":"Fitness yönetimi","view_only":"salt görüntüleme","account":"Hesap","sign_out":"Çıkış yap","account_settings":"Hesap ayarları","login_name":"Giriş adı","current_password":"Mevcut parola","new_password":"Yeni parola","cancel":"İptal","save":"Kaydet","saving":"Kaydediliyor…","saved":"Kaydedildi","unable_save":"Kaydedilemedi"},
    "zh":{"profile":"Fitness 配置文件","administration":"Fitness 管理","view_only":"仅查看","account":"账户","sign_out":"退出登录","account_settings":"账户设置","login_name":"登录名","current_password":"当前密码","new_password":"新密码","cancel":"取消","save":"保存","saving":"正在保存…","saved":"已保存","unable_save":"无法保存"},
    "ja":{"profile":"Fitness プロフィール","administration":"Fitness 管理","view_only":"表示のみ","account":"アカウント","sign_out":"サインアウト","account_settings":"アカウント設定","login_name":"ログイン名","current_password":"現在のパスワード","new_password":"新しいパスワード","cancel":"キャンセル","save":"保存","saving":"保存中…","saved":"保存しました","unable_save":"保存できません"},
    "ko":{"profile":"Fitness 프로필","administration":"Fitness 관리","view_only":"보기 전용","account":"계정","sign_out":"로그아웃","account_settings":"계정 설정","login_name":"로그인 이름","current_password":"현재 비밀번호","new_password":"새 비밀번호","cancel":"취소","save":"저장","saving":"저장 중…","saved":"저장됨","unable_save":"저장할 수 없음"},
}

def _portal_language(value: Any) -> str:
    code = str(value or "en").strip().lower().split("-")[0].split("_")[0]
    return code if code in SUPPORTED_LANGUAGES else "en"


class FitnessAccountController:
    """Persist independent Fitness accounts and manage browser sessions."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(
            hass, ACCOUNT_STORE_VERSION, ACCOUNT_STORE_KEY, private=True, atomic_writes=True
        )
        self._loaded = False
        self._load_lock = asyncio.Lock()
        self._mutation_lock = asyncio.Lock()
        self._accounts: dict[str, dict[str, Any]] = {}
        # Cast-only accounts never touch persistent storage. They exist only so
        # the already-hardened restricted Fitness portal bridge can serve one
        # profile to a LAN Cast receiver without exposing a Home Assistant token.
        self._ephemeral_cast_accounts: dict[str, dict[str, Any]] = {}
        self._cast_bootstrap: dict[str, dict[str, Any]] = {}
        self._sessions: dict[str, FitnessSession] = {}
        self._login_attempts: dict[str, list[datetime]] = {}

    async def async_load(self) -> None:
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                return
            saved = await self._store.async_load()
            accounts = saved.get("accounts") if isinstance(saved, dict) else None
            if isinstance(accounts, dict):
                for account_id, row in accounts.items():
                    clean = self._sanitize_account(account_id, row)
                    if clean is not None:
                        self._accounts[clean["account_id"]] = clean
            self._loaded = True
            if not self._accounts:
                await self._async_migrate_legacy_accounts()

    def _sanitize_account(self, account_id: Any, row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        account_id = _safe_text(account_id or row.get("account_id"), 64)
        profile_id = _safe_text(row.get("profile_entry_id"), 128)
        role, network_access = _normalized_role_and_network(
            _safe_text(row.get("role"), 24).lower(),
            row.get("network_access"),
            remote_enabled=bool(row.get("remote_enabled", False)),
            profile_entry_id=profile_id,
        )
        username = _normalize_username(row.get("username"))
        if not account_id or role not in ROLES or network_access not in NETWORK_ACCESS_MODES or not username:
            return None
        views = sorted(
            {
                _safe_text(item, 128)
                for item in (row.get("view_profile_entry_ids") or [])
                if _safe_text(item, 128)
            }
        )[:256]
        clean = {
            "account_id": account_id,
            "display_name": _safe_text(row.get("display_name") or username, 128),
            "username": username,
            "role": role,
            "network_access": network_access,
            "enabled": bool(row.get("enabled", True)),
            "remote_enabled": network_access in {NETWORK_REMOTE_ONLY, NETWORK_LOCAL_REMOTE},
            "profile_entry_id": profile_id,
            "view_profile_entry_ids": views,
            "remote_slug": _normalize_slug(row.get("remote_slug")),
            "password_salt": _safe_text(row.get("password_salt"), 256),
            "password_hash": _safe_text(row.get("password_hash"), 256),
            "password_change_required": bool(row.get("password_change_required", True)),
            "created_at": _safe_text(row.get("created_at") or _iso(), 64),
            "updated_at": _safe_text(row.get("updated_at") or _iso(), 64),
            "password_changed_at": _safe_text(row.get("password_changed_at"), 64),
            "last_login_at": _safe_text(row.get("last_login_at"), 64),
            "last_seen_at": _safe_text(row.get("last_seen_at"), 64),
            "last_error_code": _safe_text(row.get("last_error_code"), 128),
            "last_error_at": _safe_text(row.get("last_error_at"), 64),
            "failed_login_count": max(0, min(1000, int(row.get("failed_login_count") or 0))),
            "lockout_until": _safe_text(row.get("lockout_until"), 64),
            "legacy_ha_user_id": _safe_text(row.get("legacy_ha_user_id"), 128),
        }
        return clean

    async def _async_migrate_legacy_accounts(self) -> None:
        """One-way migration from the previous HA-user binding model.

        Credentials cannot be migrated because the old model delegated passwords
        to HA. Migrated users therefore require an administrator password reset
        before they can use the new Fitness login.
        """
        from .access_control import get_fitness_access_controller

        legacy = get_fitness_access_controller(self.hass)
        await legacy.async_load()
        rows = getattr(legacy, "_data", {}).get("accounts", {})  # noqa: SLF001
        if not isinstance(rows, dict) or not rows:
            return
        for legacy_user_id, old in rows.items():
            if not isinstance(old, dict) or old.get("role") not in (ROLES | _LEGACY_ROLES):
                continue
            user = await self.hass.auth.async_get_user(str(legacy_user_id))
            display = _safe_text(getattr(user, "name", "") or f"Fitness {str(legacy_user_id)[:8]}", 128)
            profile_id = _safe_text(old.get("profile_entry_id"), 128)
            role, network_access = _normalized_role_and_network(
                old.get("role"), old.get("network_access"),
                remote_enabled=bool(old.get("remote_enabled", False)),
                profile_entry_id=profile_id,
            )
            remote_slug = _normalize_slug(old.get("remote_slug"))
            if network_access in {NETWORK_REMOTE_ONLY, NETWORK_LOCAL_REMOTE} and profile_id:
                desc = legacy.external_profile_descriptor(profile_id)
                remote_slug = _normalize_slug(desc.get("subdomain")) or remote_slug
            seed = remote_slug or re.sub(r"[^A-Za-z0-9_.-]+", "-", display).strip("-._")[:48]
            username = _normalize_username(seed) or f"fitness-{secrets.token_hex(4)}"
            username = self._unique_username(username)
            account_id = uuid.uuid4().hex
            self._accounts[account_id] = {
                "account_id": account_id,
                "display_name": display,
                "username": username,
                "role": role,
                "network_access": network_access,
                "enabled": bool(old.get("enabled", True)),
                "remote_enabled": network_access in {NETWORK_REMOTE_ONLY, NETWORK_LOCAL_REMOTE},
                "profile_entry_id": profile_id,
                "view_profile_entry_ids": sorted(
                    {_safe_text(item, 128) for item in old.get("view_profile_entry_ids", []) if _safe_text(item, 128)}
                ),
                "remote_slug": remote_slug,
                "password_salt": "",
                "password_hash": "",
                "password_change_required": True,
                "created_at": _iso(),
                "updated_at": _iso(),
                "password_changed_at": "",
                "last_login_at": "",
                "last_seen_at": "",
                "last_error_code": "password_reset_required",
                "last_error_at": _iso(),
                "failed_login_count": 0,
                "lockout_until": "",
                "legacy_ha_user_id": str(legacy_user_id),
            }
        if self._accounts:
            await self._async_save()

    async def _async_save(self) -> None:
        await self._store.async_save({"accounts": self._accounts})

    def _unique_username(self, candidate: str, *, exclude_account_id: str = "") -> str:
        base = _normalize_username(candidate) or f"fitness-{secrets.token_hex(4)}"
        used = {
            str(row.get("username") or "").casefold()
            for aid, row in self._accounts.items()
            if aid != exclude_account_id
        }
        if base.casefold() not in used:
            return base
        for suffix in range(2, 10000):
            tail = f"-{suffix}"
            option = f"{base[:64-len(tail)]}{tail}"
            if option.casefold() not in used and _normalize_username(option):
                return option
        raise ValueError("username_in_use")

    def account(self, account_id: str | None) -> dict[str, Any] | None:
        key = str(account_id or "")
        row = self._accounts.get(key)
        if row is None:
            row = self._ephemeral_cast_accounts.get(key)
        if not isinstance(row, dict) or not row.get("enabled", True):
            return None
        return row

    def account_by_username(self, username: str) -> dict[str, Any] | None:
        needle = str(username or "").casefold()
        for row in self._accounts.values():
            if row.get("enabled", True) and str(row.get("username") or "").casefold() == needle:
                return row
        return None

    def account_by_profile(self, profile_entry_id: str) -> dict[str, Any] | None:
        """Return the enabled Fitness account that owns a profile."""
        needle = str(profile_entry_id or "").strip()
        if not needle:
            return None
        for row in self._accounts.values():
            if (
                row.get("enabled", True)
                and str(row.get("profile_entry_id") or "") == needle
            ):
                return row
        return None

    def account_by_remote_host(self, host: str) -> dict[str, Any] | None:
        hostname = _host_only(host)
        from .access_control import get_fitness_access_controller

        access = get_fitness_access_controller(self.hass)
        base = str(access._cloudflare().get("base_domain") or "").strip().lower().rstrip(".")  # noqa: SLF001
        if not base:
            return None
        for row in self._accounts.values():
            if not row.get("enabled", True) or not _account_remote_enabled(row):
                continue
            slug = _normalize_slug(row.get("remote_slug"))
            if slug and hostname == f"{slug}.{base}":
                return row
        return None

    def principal(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "account_id": str(row.get("account_id") or ""),
            "role": str(row.get("role") or "none"),
            "network_access": str(row.get("network_access") or NETWORK_LOCAL_ONLY),
            "username": str(row.get("username") or ""),
            "display_name": str(row.get("display_name") or row.get("username") or "Fitness"),
            "profile_entry_id": str(row.get("profile_entry_id") or "") or None,
            "view_profile_entry_ids": list(row.get("view_profile_entry_ids") or []),
            "remote_slug": str(row.get("remote_slug") or "") or None,
            "remote_enabled": _account_remote_enabled(row),
            "is_admin": str(row.get("role") or "") in {"admin", "admin_user"},
            "enabled": bool(row.get("enabled", True)),
        }

    def has_usable_admin(self) -> bool:
        """Return whether an enabled independent Fitness admin can actually sign in.

        A native HA administrator is only a bootstrap identity until at least
        one independent Fitness administrator has credentials. This prevents
        the old HA-admin role from silently remaining a permanent Fitness role
        while still making a clean migration/first setup possible.
        """
        return any(
            row.get("enabled", True)
            and _is_admin_role(row.get("role"))
            and bool(str(row.get("password_hash") or ""))
            for row in self._accounts.values()
        )

    async def async_admin_snapshot(self) -> dict[str, Any]:
        await self.async_load()
        from .access_control import get_fitness_access_controller

        access = get_fitness_access_controller(self.hass)
        await access.async_load()
        profiles = []
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("entry_type") in {"live_hub", "devices_hub"}:
                continue
            cfg = {**entry.data, **entry.options}
            profiles.append({
                "entry_id": entry.entry_id,
                "name": str(cfg.get("profile_name") or entry.title or entry.entry_id),
                "language": str(cfg.get("language") or "en"),
            })
        accounts = [self.public_account(row, include_diagnostics=True) for row in self._accounts.values()]
        cfg = access._cloudflare()  # noqa: SLF001
        return {
            "accounts": sorted(accounts, key=lambda item: str(item.get("display_name") or "").casefold()),
            "profiles": sorted(profiles, key=lambda item: str(item.get("name") or "").casefold()),
            "cloudflare": {
                "zone": str(cfg.get("zone") or ""),
                "base_domain": str(cfg.get("base_domain") or ""),
                "record_target": str(cfg.get("record_target") or ""),
                "api_token_configured": bool(str(cfg.get("api_token") or "").strip()),
                "configured": access._cloudflare_ready(),  # noqa: SLF001
                "host_router_ready": bool(self.hass.data.get(DOMAIN, {}).get(PORTAL_MIDDLEWARE_KEY)),
            },
            "dashboard_max": access.dashboard_max(),
        }

    def public_account(self, row: dict[str, Any], *, include_diagnostics: bool = False) -> dict[str, Any]:
        account_id = str(row.get("account_id") or "")
        active_sessions = sum(1 for sess in self._sessions.values() if sess.account_id == account_id)
        from .access_control import get_fitness_access_controller

        access = get_fitness_access_controller(self.hass)
        profile_id = str(row.get("profile_entry_id") or "")
        remote_enabled = _account_remote_enabled(row)
        if remote_enabled and _is_admin_role(row.get("role")):
            dns = access.external_account_descriptor(account_id)
        elif remote_enabled and profile_id:
            dns = access.external_profile_descriptor(profile_id)
        else:
            dns = {}
        remote_url = None
        if remote_enabled:
            slug = _normalize_slug(row.get("remote_slug"))
            base = str(access._cloudflare().get("base_domain") or "").strip().lower().rstrip(".")  # noqa: SLF001
            if slug and base:
                remote_url = f"https://{slug}.{base}"
        state = "disabled" if not row.get("enabled", True) else "ready"
        last_error = str(row.get("last_error_code") or "")
        if not row.get("password_hash"):
            state = "setup_required"
        elif _parse_dt(row.get("lockout_until")) and _parse_dt(row.get("lockout_until")) > _utcnow():
            state = "locked"
        elif active_sessions:
            state = "live"
        elif remote_enabled and dns.get("dns_state") not in {"active", "active_cleanup_pending"}:
            state = "error" if dns.get("last_error") else "dns_pending"
        elif last_error and last_error not in {"password_reset_required"}:
            state = "error"
        result = {
            "account_id": account_id,
            "display_name": str(row.get("display_name") or ""),
            "username": str(row.get("username") or ""),
            "role": str(row.get("role") or ""),
            "network_access": str(row.get("network_access") or NETWORK_LOCAL_ONLY),
            "enabled": bool(row.get("enabled", True)),
            "profile_entry_id": str(row.get("profile_entry_id") or "") or None,
            "view_profile_entry_ids": list(row.get("view_profile_entry_ids") or []),
            "remote_slug": str(row.get("remote_slug") or "") or None,
            "remote_enabled": remote_enabled,
            "remote_url": remote_url,
            "password_change_required": bool(row.get("password_change_required", True)),
            "credentials_configured": bool(row.get("password_hash")),
            "current_state": state,
        }
        if include_diagnostics:
            result["diagnostics"] = {
                "active_sessions": active_sessions,
                "last_login_at": str(row.get("last_login_at") or "") or None,
                "last_seen_at": str(row.get("last_seen_at") or "") or None,
                "last_error_code": last_error or None,
                "last_error_at": str(row.get("last_error_at") or "") or None,
                "failed_login_count": int(row.get("failed_login_count") or 0),
                "lockout_until": str(row.get("lockout_until") or "") or None,
                "dns_state": dns.get("dns_state") if dns else None,
                "dns_error": dns.get("last_error") if dns else None,
                "dns_url": dns.get("url") if dns else remote_url,
                "login_scope": str(row.get("network_access") or NETWORK_LOCAL_ONLY),
                "password_change_required": bool(row.get("password_change_required", True)),
                "credentials_configured": bool(row.get("password_hash")),
            }
        return result

    def sharing_snapshot(self, owner_account_id: str) -> dict[str, Any]:
        """Return view-only sharing choices for one account's own dashboard."""
        owner = self._accounts.get(str(owner_account_id or ""))
        if not isinstance(owner, dict):
            raise ValueError("account_not_found")
        owner_profile = str(owner.get("profile_entry_id") or "")
        if not owner_profile:
            raise ValueError("profile_not_found")
        viewers: list[dict[str, Any]] = []
        for account_id, row in self._accounts.items():
            if account_id == owner_account_id or not row.get("enabled", True):
                continue
            # Administrators already have global visibility; listing them as a
            # share target would imply that this checkbox grants admin access.
            if _is_admin_role(row.get("role")):
                continue
            viewers.append({
                "account_id": account_id,
                "display_name": str(row.get("display_name") or row.get("username") or account_id),
                "selected": owner_profile in {str(item) for item in (row.get("view_profile_entry_ids") or [])},
            })
        viewers.sort(key=lambda item: (str(item["display_name"]).casefold(), item["account_id"]))
        return {
            "owner_account_id": owner_account_id,
            "profile_entry_id": owner_profile,
            "viewers": viewers,
        }

    async def async_set_shared_viewers(
        self, owner_account_id: str, viewer_account_ids: list[str]
    ) -> dict[str, Any]:
        """Grant/revoke view-only access to the caller's own Fitness profile.

        This operation edits only the owner's profile ID inside other users'
        view lists. It can never change roles, network access, ownership or any
        other viewer setting.
        """
        await self.async_load()
        async with self._mutation_lock:
            owner = self._accounts.get(str(owner_account_id or ""))
            if not isinstance(owner, dict) or not owner.get("enabled", True):
                raise ValueError("account_not_found")
            owner_profile = str(owner.get("profile_entry_id") or "")
            if not owner_profile:
                raise ValueError("profile_not_found")
            requested = {str(item) for item in (viewer_account_ids or []) if str(item)}
            allowed = {
                account_id
                for account_id, row in self._accounts.items()
                if account_id != owner_account_id
                and row.get("enabled", True)
                and not _is_admin_role(row.get("role"))
            }
            if not requested.issubset(allowed):
                raise ValueError("account_not_found")
            for account_id, row in self._accounts.items():
                if account_id not in allowed:
                    continue
                views = {str(item) for item in (row.get("view_profile_entry_ids") or []) if str(item)}
                if account_id in requested:
                    views.add(owner_profile)
                else:
                    views.discard(owner_profile)
                row["view_profile_entry_ids"] = sorted(views)
                row["updated_at"] = _iso()
            await self._async_save()
        return self.sharing_snapshot(owner_account_id)

    async def async_save_account(
        self,
        *,
        account_id: str | None,
        display_name: str,
        role: str,
        network_access: str | None,
        profile_entry_id: str | None,
        view_profile_entry_ids: list[str] | None,
        remote_slug: str | None,
        remote_enabled: bool = False,
        username: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        await self.async_load()
        async with self._mutation_lock:
            role = str(role or "").lower().strip()
            account_id = str(account_id or "").strip()
            current = self._accounts.get(account_id) if account_id else None
            if not account_id:
                account_id = uuid.uuid4().hex
            profile_id = _safe_text(profile_entry_id, 128)
            role, network_access = _normalized_role_and_network(
                role, network_access, remote_enabled=bool(remote_enabled), profile_entry_id=profile_id
            )
            if role not in ROLES:
                raise ValueError("invalid_role")
            if network_access not in NETWORK_ACCESS_MODES:
                raise ValueError("invalid_network_access")
            if _role_requires_profile(role) and not profile_id:
                raise ValueError("profile_not_found")
            if role == ROLE_ADMIN and profile_id:
                raise ValueError("admin_profile_not_allowed")
            remote_enabled = network_access in {NETWORK_REMOTE_ONLY, NETWORK_LOCAL_REMOTE}
            if profile_id:
                entry = self.hass.config_entries.async_get_entry(profile_id)
                if entry is None or entry.domain != DOMAIN or entry.data.get("entry_type") in {"live_hub", "devices_hub"}:
                    raise ValueError("profile_not_found")
                # One owning account per profile. Admins may optionally bind their
                # own profile, but no second local/remote owner can claim it.
                for aid, other in self._accounts.items():
                    if aid == account_id or not other.get("enabled", True):
                        continue
                    if str(other.get("profile_entry_id") or "") == profile_id:
                        raise ValueError("profile_already_assigned")
            views = {
                _safe_text(item, 128)
                for item in (view_profile_entry_ids or [])
                if _safe_text(item, 128)
            }
            views.discard(profile_id)
            known = {
                entry.entry_id
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.data.get("entry_type") not in {"live_hub", "devices_hub"}
            }
            if not views.issubset(known):
                raise ValueError("profile_not_found")
            if _is_admin_role(role):
                views.clear()
            slug = _normalize_slug(remote_slug)
            if remote_enabled and not slug:
                # Enabling remote access on an existing account should not fail
                # just because it predates remote hostnames. Derive a safe first
                # slug from the existing identity/display name; admins can edit
                # it before saving if they want a different hostname.
                slug = (
                    _normalize_slug((current or {}).get("remote_slug"))
                    or _normalize_slug((current or {}).get("username"))
                    or _normalize_slug(display_name)
                )
            if remote_enabled:
                if not slug:
                    raise ValueError("invalid_remote_slug")
                for aid, other in self._accounts.items():
                    if (
                        aid != account_id
                        and other.get("enabled", True)
                        and _account_remote_enabled(other)
                        and _normalize_slug(other.get("remote_slug")) == slug
                    ):
                        raise ValueError("remote_slug_in_use")
            else:
                slug = ""
            requested_username = _normalize_username(username)
            if network_access == NETWORK_REMOTE_ONLY:
                # A dedicated remote hostname selects the account, so a second
                # user-editable login name is redundant and confusing. Keep an
                # internal identifier derived from the assigned hostname.
                requested_username = _normalize_username(slug)
            elif username is not None and not requested_username:
                raise ValueError("invalid_username")
            if not requested_username:
                requested_username = (
                    _normalize_username(slug)
                    or _normalize_username((current or {}).get("username"))
                    or _normalize_username(re.sub(r"[^A-Za-z0-9_.-]+", "-", display_name).strip("-._"))
                    or f"fitness-{secrets.token_hex(4)}"
                )
            requested_username = self._unique_username(requested_username, exclude_account_id=account_id)
            if current and _is_admin_role(current.get("role")) and current.get("enabled", True) and (not _is_admin_role(role) or not enabled):
                other_admins = [
                    other for aid, other in self._accounts.items()
                    if aid != account_id and other.get("enabled", True) and _is_admin_role(other.get("role"))
                ]
                if not other_admins:
                    raise ValueError("last_admin")
            now = _iso()
            row = {
                "account_id": account_id,
                "display_name": _safe_text(display_name or requested_username, 128),
                "username": requested_username,
                "role": role,
                "network_access": network_access,
                "enabled": bool(enabled),
                "remote_enabled": remote_enabled,
                "profile_entry_id": profile_id,
                "view_profile_entry_ids": sorted(views),
                "remote_slug": slug,
                "password_salt": str((current or {}).get("password_salt") or ""),
                "password_hash": str((current or {}).get("password_hash") or ""),
                "password_change_required": bool((current or {}).get("password_change_required", True)),
                "created_at": str((current or {}).get("created_at") or now),
                "updated_at": now,
                "password_changed_at": str((current or {}).get("password_changed_at") or ""),
                "last_login_at": str((current or {}).get("last_login_at") or ""),
                "last_seen_at": str((current or {}).get("last_seen_at") or ""),
                "last_error_code": str((current or {}).get("last_error_code") or ""),
                "last_error_at": str((current or {}).get("last_error_at") or ""),
                "failed_login_count": int((current or {}).get("failed_login_count") or 0),
                "lockout_until": str((current or {}).get("lockout_until") or ""),
                "legacy_ha_user_id": str((current or {}).get("legacy_ha_user_id") or ""),
            }
            self._accounts[account_id] = row
            await self._async_save()

            # The hostname belongs to the Fitness account. Normal remote users
            # keep the established profile-scoped DNS ledger; remote-enabled
            # administrators use an account-scoped ledger so an admin does not
            # need to own a Fitness profile just to receive a secure hostname.
            from .access_control import get_fitness_access_controller

            access = get_fitness_access_controller(self.hass)
            old_role = str((current or {}).get("role") or "")
            old_profile = str((current or {}).get("profile_entry_id") or "")
            old_slug = _normalize_slug((current or {}).get("remote_slug"))
            old_enabled = bool((current or {}).get("enabled", True))
            old_remote_enabled = _account_remote_enabled(current) and old_enabled
            wants_remote = remote_enabled and row["enabled"] and bool(slug)
            router_ready = self.hass.data.get(DOMAIN, {}).get(PORTAL_MIDDLEWARE_KEY) is True
            should_publish = wants_remote and router_ready

            async def _set_remote_dns(*, old: bool, publish: bool, target_slug: str | None) -> None:
                target_role = old_role if old else role
                target_profile = old_profile if old else profile_id
                if _is_admin_role(target_role):
                    await access._async_set_external_account(  # noqa: SLF001
                        account_id=account_id, enabled=publish, subdomain=target_slug
                    )
                    return
                if target_profile:
                    await access._async_set_external_profile(  # noqa: SLF001
                        profile_entry_id=target_profile, enabled=publish, subdomain=target_slug
                    )

            if wants_remote and not router_ready:
                self._record_error(row, "host_router_unavailable")
                await self._async_save()
                try:
                    await _set_remote_dns(old=False, publish=False, target_slug=None)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning(
                        "Unable to withdraw Fitness remote DNS while hostname routing is unavailable: %s",
                        err,
                    )

            same_ledger = (
                (_is_admin_role(old_role) and _is_admin_role(role))
                or (old_role == role and old_profile == profile_id)
            )
            old_same_binding = (
                old_remote_enabled and wants_remote and same_ledger and old_slug == slug
            )
            if old_remote_enabled and not old_same_binding:
                same_binding_slug_change = bool(
                    should_publish and same_ledger and old_slug != slug
                )
                if not same_binding_slug_change:
                    try:
                        await _set_remote_dns(old=True, publish=False, target_slug=None)
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.warning(
                            "Fitness account %s is blocked but old remote DNS cleanup is pending: %s",
                            account_id, err,
                        )
                        self._record_error(row, f"cloudflare_cleanup:{err}")
                        await self._async_save()
            if should_publish:
                try:
                    await _set_remote_dns(old=False, publish=True, target_slug=slug)
                    if (
                        str(row.get("last_error_code") or "").startswith("cloudflare_")
                        or row.get("last_error_code") == "host_router_unavailable"
                    ):
                        row["last_error_code"] = ""
                        row["last_error_at"] = ""
                        await self._async_save()
                except Exception as err:  # noqa: BLE001
                    self._record_error(row, f"cloudflare_publish:{getattr(err, 'code', err)}")
                    await self._async_save()
            self._revoke_account_sessions(account_id)
            return self.public_account(row, include_diagnostics=True)

    async def async_delete_account(self, account_id: str) -> None:
        await self.async_load()
        async with self._mutation_lock:
            row = self._accounts.get(str(account_id))
            if not row:
                raise ValueError("account_not_found")
            # Do not allow the last explicit Fitness administrator to be removed.
            if _is_admin_role(row.get("role")):
                others = [
                    a for aid, a in self._accounts.items()
                    if aid != account_id and a.get("enabled", True) and _is_admin_role(a.get("role"))
                ]
                if not others:
                    raise ValueError("last_admin")
            if _account_remote_enabled(row):
                from .access_control import get_fitness_access_controller

                try:
                    access = get_fitness_access_controller(self.hass)
                    if _is_admin_role(row.get("role")):
                        await access._async_set_external_account(  # noqa: SLF001
                            account_id=str(account_id), enabled=False, subdomain=None
                        )
                    elif row.get("profile_entry_id"):
                        await access._async_set_external_profile(  # noqa: SLF001
                            profile_entry_id=str(row["profile_entry_id"]), enabled=False, subdomain=None
                        )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Unable to clean Fitness remote DNS during account removal: %s", err)
            self._accounts.pop(str(account_id), None)
            self._revoke_account_sessions(str(account_id))
            await self._async_save()

    async def async_prepare_initial_password(
        self, password: str, *, username: str = "", remote_slug: str = "", profile_name: str = ""
    ) -> dict[str, Any]:
        """Hash a first-login password without persisting its plaintext."""
        code = _password_policy(
            str(password or ""),
            username=str(username or ""),
            subdomain=str(remote_slug or ""),
            profile_name=str(profile_name or ""),
        )
        if code:
            raise ValueError(code)
        salt = secrets.token_bytes(16)
        digest = await self.hass.async_add_executor_job(_scrypt_hash, str(password), salt)
        now = _iso()
        return {
            "password_salt": salt.hex(),
            "password_hash": digest,
            "password_change_required": True,
            "password_changed_at": now,
        }

    async def async_set_initial_password(self, account_id: str, password: str) -> None:
        """Install a first-login password and require it to be changed."""
        await self.async_load()
        async with self._mutation_lock:
            row = self.account(account_id)
            if row is None:
                raise ValueError("account_not_found")
            await self._async_set_password(row, str(password or ""), force_change=True)
            row["last_error_code"] = ""
            row["last_error_at"] = ""
            await self._async_save()
            self._revoke_account_sessions(account_id)

    async def async_finalize_pending_profile_account(
        self, profile_entry_id: str, spec: dict[str, Any]
    ) -> dict[str, Any]:
        """Bind a native config-flow account to its newly created profile."""
        profile_entry_id = _safe_text(profile_entry_id, 128)
        entry = self.hass.config_entries.async_get_entry(profile_entry_id)
        if entry is None:
            raise ValueError("profile_not_found")
        config = {**entry.data, **entry.options}
        display_name = _safe_text(
            spec.get("display_name") or config.get(CONF_PROFILE_NAME) or entry.title, 128
        )
        account = await self.async_save_account(
            account_id=None,
            display_name=display_name,
            role=str(spec.get("role") or ""),
            network_access=str(spec.get("network_access") or ""),
            profile_entry_id=profile_entry_id,
            view_profile_entry_ids=[
                str(item) for item in (spec.get("view_profile_entry_ids") or []) if str(item)
            ],
            remote_slug=str(spec.get("remote_slug") or "") or None,
            username=str(spec.get("username") or "") or None,
            enabled=bool(spec.get("enabled", True)),
        )
        salt = str(spec.get("password_salt") or "")
        digest = str(spec.get("password_hash") or "")
        try:
            salt_bytes = bytes.fromhex(salt)
            digest_bytes = bytes.fromhex(digest)
        except ValueError as err:
            raise ValueError("invalid_prepared_password") from err
        if len(salt_bytes) != 16 or len(digest_bytes) != 32:
            raise ValueError("invalid_prepared_password")
        account_id = str(account.get("account_id") or "")
        async with self._mutation_lock:
            row = self.account(account_id)
            if row is None:
                raise ValueError("account_not_found")
            row["password_salt"] = salt
            row["password_hash"] = digest
            row["password_change_required"] = True
            row["password_changed_at"] = str(spec.get("password_changed_at") or _iso())
            row["last_error_code"] = ""
            row["last_error_at"] = ""
            row["updated_at"] = _iso()
            await self._async_save()
            self._revoke_account_sessions(account_id)
            return self.public_account(row, include_diagnostics=True)

    async def async_generate_temporary_password(self, account_id: str) -> str:
        await self.async_load()
        async with self._mutation_lock:
            row = self.account(account_id)
            if row is None:
                raise ValueError("account_not_found")
            # A temporary credential must itself pass the same policy we impose
            # on the user. Seed every character class explicitly, fill the rest
            # with cryptographic randomness, shuffle with SystemRandom, and retry
            # if the result happens to contain account/profile text.
            classes = (
                "ABCDEFGHJKLMNPQRSTUVWXYZ",
                "abcdefghijkmnopqrstuvwxyz",
                "23456789",
                "!@#$%",
            )
            rng = secrets.SystemRandom()
            password = ""
            for _attempt in range(32):
                chars = [secrets.choice(group) for group in classes]
                chars.extend(secrets.choice(_TEMP_ALPHABET) for _ in range(16))
                rng.shuffle(chars)
                candidate = "".join(chars)
                try:
                    await self._async_set_password(row, candidate, force_change=True)
                except ValueError as err:
                    if str(err).startswith("password_"):
                        continue
                    raise
                password = candidate
                break
            if not password:
                raise RuntimeError("temporary_password_generation_failed")
            row["last_error_code"] = ""
            row["last_error_at"] = ""
            await self._async_save()
            self._revoke_account_sessions(account_id)
            # The plaintext is returned only in this response and is never saved.
            return password

    async def _async_set_password(self, row: dict[str, Any], password: str, *, force_change: bool) -> None:
        profile_name = ""
        profile_id = str(row.get("profile_entry_id") or "")
        entry = self.hass.config_entries.async_get_entry(profile_id) if profile_id else None
        if entry is not None:
            cfg = {**entry.data, **entry.options}
            profile_name = str(cfg.get("profile_name") or entry.title or "")
        code = _password_policy(
            password,
            username=str(row.get("username") or ""),
            subdomain=str(row.get("remote_slug") or ""),
            profile_name=profile_name,
        )
        if code:
            raise ValueError(code)
        salt = secrets.token_bytes(16)
        digest = await self.hass.async_add_executor_job(_scrypt_hash, password, salt)
        row["password_salt"] = salt.hex()
        row["password_hash"] = digest
        row["password_change_required"] = bool(force_change)
        row["password_changed_at"] = _iso()
        row["updated_at"] = _iso()

    async def async_change_credentials(
        self,
        account_id: str,
        *,
        current_password: str | None,
        new_password: str | None,
        new_username: str | None,
        first_login: bool = False,
        preserve_session_token: str | None = None,
    ) -> dict[str, Any]:
        await self.async_load()
        async with self._mutation_lock:
            row = self.account(account_id)
            if row is None:
                raise ValueError("account_not_found")
            if not first_login:
                if not current_password or not await self._async_verify_password(row, current_password):
                    raise ValueError("invalid_current_password")
            if new_username is not None and str(row.get("network_access") or "") != NETWORK_REMOTE_ONLY:
                username = _normalize_username(new_username)
                if not username:
                    raise ValueError("invalid_username")
                row["username"] = self._unique_username(username, exclude_account_id=account_id)
            if new_password:
                await self._async_set_password(row, new_password, force_change=False)
            elif first_login:
                raise ValueError("new_password_required")
            row["password_change_required"] = False
            row["last_error_code"] = ""
            row["last_error_at"] = ""
            row["updated_at"] = _iso()
            await self._async_save()
            self._revoke_account_sessions_except(account_id, preserve_session_token)
            return self.public_account(row, include_diagnostics=True)

    async def _async_verify_password(self, row: dict[str, Any], password: str) -> bool:
        salt_hex = str(row.get("password_salt") or "")
        expected = str(row.get("password_hash") or "")
        if not salt_hex or not expected:
            return False
        try:
            salt = bytes.fromhex(salt_hex)
        except ValueError:
            return False
        actual = await self.hass.async_add_executor_job(_scrypt_hash, str(password), salt)
        return hmac.compare_digest(actual, expected)

    def account_language(self, row: dict[str, Any] | None) -> str:
        """Return the bound Fitness profile language for an account."""
        profile_id = _safe_text((row or {}).get("profile_entry_id"), 128)
        entry = self.hass.config_entries.async_get_entry(profile_id) if profile_id else None
        if entry is not None:
            config = {**entry.data, **entry.options}
            return _portal_language(config.get(CONF_LANGUAGE))
        return _portal_language(getattr(self.hass.config, "language", "en"))

    def _persist_login_language(self, row: dict[str, Any], language: str) -> None:
        """Make the successfully selected portal language the profile language."""
        profile_id = _safe_text(row.get("profile_entry_id"), 128)
        entry = self.hass.config_entries.async_get_entry(profile_id) if profile_id else None
        if entry is None or entry.domain != DOMAIN or entry.data.get("entry_type") in {"live_hub", "devices_hub"}:
            return
        normalized = _portal_language(language)
        current = _portal_language(entry.options.get(CONF_LANGUAGE, entry.data.get(CONF_LANGUAGE, "en")))
        if current == normalized:
            return
        options = dict(entry.options)
        options[CONF_LANGUAGE] = normalized
        self.hass.config_entries.async_update_entry(entry, options=options)

    def _attempt_key(self, remote: str, username: str) -> str:
        return f"{str(remote or '')[:96]}|{str(username or '').casefold()[:64]}"

    def _prune_attempts(self, key: str) -> list[datetime]:
        cutoff = _utcnow() - _LOGIN_WINDOW
        rows = [stamp for stamp in self._login_attempts.get(key, []) if stamp >= cutoff]
        self._login_attempts[key] = rows
        return rows

    async def async_authenticate(self, *, username: str, password: str, remote: str, host: str, user_agent: str, language: str = "en") -> tuple[dict[str, Any], FitnessSession]:
        await self.async_load()
        key = self._attempt_key(remote, username)
        attempts = self._prune_attempts(key)
        if len(attempts) >= _LOGIN_MAX_FAILURES:
            raise ValueError("login_rate_limited")
        row = self.account_by_username(username)
        host_account = self.account_by_remote_host(host)
        if row is None or (host_account is not None and row.get("account_id") != host_account.get("account_id")):
            self._login_attempts.setdefault(key, []).append(_utcnow())
            await asyncio.sleep(0.25)
            raise ValueError("invalid_credentials")
        lockout = _parse_dt(row.get("lockout_until"))
        if lockout and lockout > _utcnow():
            raise ValueError("account_locked")
        network_access = str(row.get("network_access") or NETWORK_LOCAL_ONLY)
        local_client = _client_is_local(remote)
        expected = self.account_by_remote_host(host)
        exact_remote_host = bool(
            expected is not None and expected.get("account_id") == row.get("account_id")
        )
        if network_access == NETWORK_LOCAL_ONLY and not local_client:
            self._record_error(row, "local_network_required")
            await self._async_save()
            raise ValueError("local_network_required")
        if network_access == NETWORK_REMOTE_ONLY and not exact_remote_host:
            self._record_error(row, "remote_host_mismatch")
            await self._async_save()
            raise ValueError("remote_host_mismatch")
        if network_access == NETWORK_LOCAL_REMOTE and not (local_client or exact_remote_host):
            self._record_error(row, "remote_host_mismatch")
            await self._async_save()
            raise ValueError("remote_host_mismatch")
        if not await self._async_verify_password(row, password):
            row["failed_login_count"] = int(row.get("failed_login_count") or 0) + 1
            self._login_attempts.setdefault(key, []).append(_utcnow())
            if row["failed_login_count"] >= _LOGIN_MAX_FAILURES:
                row["lockout_until"] = _iso(_utcnow() + _LOCKOUT_DURATION)
            self._record_error(row, "invalid_credentials")
            await self._async_save()
            await asyncio.sleep(0.25)
            raise ValueError("invalid_credentials")
        row["failed_login_count"] = 0
        row["lockout_until"] = ""
        row["last_login_at"] = _iso()
        row["last_seen_at"] = row["last_login_at"]
        row["last_error_code"] = ""
        row["last_error_at"] = ""
        await self._async_save()
        # The language chosen on a successful Fitness login becomes the
        # persistent language of the bound Fitness profile.  The profile is the
        # single source of truth for dashboard strings, AI and TTS; the session
        # merely mirrors that persisted value.
        self._persist_login_language(row, language)
        session = self._create_session(
            row,
            host=host,
            user_agent=user_agent,
            language=self.account_language(row),
        )
        return row, session

    def _record_error(self, row: dict[str, Any], code: str) -> None:
        row["last_error_code"] = str(code)[:128]
        row["last_error_at"] = _iso()

    def _create_session(self, row: dict[str, Any], *, host: str, user_agent: str, language: str = "en") -> FitnessSession:
        now = _utcnow()
        token = secrets.token_urlsafe(36)
        session = FitnessSession(
            token=token,
            account_id=str(row["account_id"]),
            csrf=secrets.token_urlsafe(24),
            created_at=now,
            last_seen_at=now,
            expires_at=now + _SESSION_MAX_AGE,
            host=_host_only(host),
            user_agent_hash=hashlib.sha256(str(user_agent or "").encode()).hexdigest()[:24],
            language=_portal_language(language),
        )
        self._sessions[token] = session
        self._prune_sessions()
        return session

    def _prune_sessions(self) -> None:
        now = _utcnow()
        for token, session in list(self._sessions.items()):
            if session.expires_at <= now or session.last_seen_at + _SESSION_IDLE_MAX <= now:
                self._sessions.pop(token, None)
        live_accounts = {session.account_id for session in self._sessions.values()}
        for account_id in tuple(self._ephemeral_cast_accounts):
            if account_id not in live_accounts:
                self._ephemeral_cast_accounts.pop(account_id, None)
        self._prune_cast_bootstrap(now)

    def _prune_cast_bootstrap(self, now: datetime | None = None) -> None:
        now = now or _utcnow()
        for ticket, spec in list(self._cast_bootstrap.items()):
            expires = spec.get("expires_at")
            session_token = str(spec.get("session_token") or "")
            if not isinstance(expires, datetime) or expires <= now:
                self._cast_bootstrap.pop(ticket, None)
                continue
            if session_token and session_token not in self._sessions:
                self._cast_bootstrap.pop(ticket, None)

    def issue_cast_bootstrap(
        self,
        *,
        profile_entry_id: str = "",
        target_entity_id: str,
        overview: bool = False,
        network_access: str = NETWORK_LOCAL_ONLY,
    ) -> str:
        """Issue an opaque short-lived URL ticket for a restricted Fitness TV receiver."""
        self._prune_sessions()
        overview = bool(overview)
        profile_entry_id = str(profile_entry_id or "").strip()
        target_entity_id = str(target_entity_id or "").strip()
        network_access = str(network_access or NETWORK_LOCAL_ONLY).strip().lower()
        if network_access not in {NETWORK_LOCAL_ONLY, NETWORK_REMOTE_ONLY}:
            raise ValueError("invalid_network_access")
        if not target_entity_id or (not overview and not profile_entry_id):
            raise ValueError("invalid_cast_session")
        if not overview:
            entry = self.hass.config_entries.async_get_entry(profile_entry_id)
            if entry is None or entry.domain != DOMAIN or entry.data.get("entry_type") in {"live_hub", "devices_hub"}:
                raise ValueError("profile_not_found")
        # A new launch supersedes old bootstrap URLs for the same profile/TV.
        self.revoke_cast_sessions(profile_entry_id=profile_entry_id, target_entity_id=target_entity_id)
        ticket = secrets.token_urlsafe(36)
        self._cast_bootstrap[ticket] = {
            "profile_entry_id": profile_entry_id,
            "target_entity_id": target_entity_id,
            "overview": overview,
            "created_at": _utcnow(),
            "expires_at": _utcnow() + _CAST_BOOTSTRAP_TTL,
            "session_token": "",
            "remote": "",
            "user_agent_hash": "",
            "network_access": network_access,
        }
        return ticket

    def cast_bootstrap_redeemed(self, ticket: str) -> bool:
        """Return whether a short-lived TV bootstrap URL reached its receiver."""
        self._prune_sessions()
        spec = self._cast_bootstrap.get(str(ticket or ""))
        if not isinstance(spec, dict):
            return False
        token = str(spec.get("session_token") or "")
        return bool(token and token in self._sessions)

    async def async_wait_cast_bootstrap_redeemed(
        self, ticket: str, *, timeout: float = 18.0
    ) -> bool:
        """Wait for the TV browser/DashCast receiver to redeem its opaque URL."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, float(timeout))
        while loop.time() < deadline:
            if self.cast_bootstrap_redeemed(ticket):
                return True
            await asyncio.sleep(0.35)
        return self.cast_bootstrap_redeemed(ticket)

    async def async_redeem_cast_bootstrap(
        self, request: web.Request, ticket: str
    ) -> tuple[dict[str, Any], FitnessSession] | None:
        """Redeem/reload one DashCast bootstrap URL from the local TV only."""
        await self.async_load()
        self._prune_sessions()
        spec = self._cast_bootstrap.get(str(ticket or ""))
        if not isinstance(spec, dict):
            return None
        remote = _effective_remote(request)
        ticket_network = str(spec.get("network_access") or NETWORK_LOCAL_ONLY)
        if ticket_network == NETWORK_LOCAL_ONLY and not _client_is_local(remote):
            return None
        if ticket_network == NETWORK_REMOTE_ONLY and _client_is_local(remote):
            return None
        ua_hash = hashlib.sha256(str(request.headers.get("User-Agent") or "").encode()).hexdigest()[:24]
        bound_remote = str(spec.get("remote") or "")
        bound_ua = str(spec.get("user_agent_hash") or "")
        if bound_remote and bound_remote != str(remote or ""):
            return None
        if bound_ua and not hmac.compare_digest(bound_ua, ua_hash):
            return None
        session_token = str(spec.get("session_token") or "")
        if session_token:
            session = self._sessions.get(session_token)
            row = self.account(session.account_id) if session is not None else None
            if session is None or row is None:
                self._cast_bootstrap.pop(str(ticket), None)
                return None
            session.last_seen_at = _utcnow()
            return row, session

        overview = bool(spec.get("overview"))
        profile_entry_id = str(spec.get("profile_entry_id") or "")
        if not overview:
            entry = self.hass.config_entries.async_get_entry(profile_entry_id)
            if entry is None or entry.domain != DOMAIN:
                self._cast_bootstrap.pop(str(ticket), None)
                return None
        account_id = f"cast-{uuid.uuid4().hex}"
        row = {
            "account_id": account_id,
            "role": ROLE_USER,
            "network_access": ticket_network,
            "username": f"cast-{uuid.uuid4().hex[:12]}",
            "display_name": "Fitness TV",
            "profile_entry_id": profile_entry_id,
            "view_profile_entry_ids": [],
            "remote_slug": "",
            "remote_enabled": False,
            "enabled": True,
            "password_change_required": False,
            "_cast_target_entity_id": str(spec.get("target_entity_id") or ""),
            "_cast_overview_only": overview,
        }
        if overview:
            row["role"] = ROLE_ADMIN
            row["network_access"] = ticket_network
        self._ephemeral_cast_accounts[account_id] = row
        session = self._create_session(
            row,
            host=request.host,
            user_agent=str(request.headers.get("User-Agent") or ""),
            language=self.account_language(row),
        )
        spec["session_token"] = session.token
        spec["remote"] = str(remote or "")
        spec["user_agent_hash"] = ua_hash
        spec["expires_at"] = session.expires_at
        return row, session

    def revoke_cast_sessions(
        self, *, profile_entry_id: str = "", target_entity_id: str = ""
    ) -> None:
        """Revoke ephemeral Cast portal sessions matching a profile/target."""
        profile_entry_id = str(profile_entry_id or "")
        target_entity_id = str(target_entity_id or "")
        account_ids = {
            account_id
            for account_id, row in self._ephemeral_cast_accounts.items()
            if (not profile_entry_id or str(row.get("profile_entry_id") or "") == profile_entry_id)
            and (not target_entity_id or str(row.get("_cast_target_entity_id") or "") == target_entity_id)
        }
        for token, session in list(self._sessions.items()):
            if session.account_id in account_ids:
                self._sessions.pop(token, None)
        for account_id in account_ids:
            self._ephemeral_cast_accounts.pop(account_id, None)
        for ticket, spec in list(self._cast_bootstrap.items()):
            if (
                not profile_entry_id
                or str(spec.get("profile_entry_id") or "") == profile_entry_id
            ) and (
                not target_entity_id
                or str(spec.get("target_entity_id") or "") == target_entity_id
            ):
                self._cast_bootstrap.pop(ticket, None)

    def _revoke_account_sessions(self, account_id: str) -> None:
        for token, session in list(self._sessions.items()):
            if session.account_id == str(account_id):
                self._sessions.pop(token, None)

    def _revoke_account_sessions_except(self, account_id: str, keep_token: str | None) -> None:
        keep = str(keep_token or "")
        for token, session in list(self._sessions.items()):
            if session.account_id == str(account_id) and token != keep:
                self._sessions.pop(token, None)

    def _cast_session_token_from_request(self, request: web.Request) -> str:
        """Return a bound ephemeral Cast session token without relying on cookies."""
        ticket = str(request.headers.get("X-Fitness-Cast-Ticket") or "").strip()
        if not ticket:
            return ""
        spec = self._cast_bootstrap.get(ticket)
        if not isinstance(spec, dict):
            return ""
        remote = _effective_remote(request)
        if not _client_is_local(remote):
            return ""
        expires = spec.get("expires_at")
        if not isinstance(expires, datetime) or expires <= _utcnow():
            return ""
        bound_remote = str(spec.get("remote") or "")
        if bound_remote and bound_remote != str(remote or ""):
            return ""
        ua_hash = hashlib.sha256(str(request.headers.get("User-Agent") or "").encode()).hexdigest()[:24]
        bound_ua = str(spec.get("user_agent_hash") or "")
        if bound_ua and not hmac.compare_digest(bound_ua, ua_hash):
            return ""
        session_token = str(spec.get("session_token") or "")
        return session_token if session_token in self._sessions else ""

    async def async_session(self, request: web.Request, *, touch: bool = True) -> tuple[dict[str, Any], FitnessSession] | None:
        await self.async_load()
        self._prune_sessions()
        token = str(
            request.cookies.get(_SESSION_COOKIE)
            or request.cookies.get(_CAST_SESSION_COOKIE)
            or self._cast_session_token_from_request(request)
            or ""
        )
        session = self._sessions.get(token)
        if session is None:
            return None
        if session.host and session.host != _host_only(request.host):
            self._sessions.pop(token, None)
            return None
        ua_hash = hashlib.sha256(str(request.headers.get("User-Agent") or "").encode()).hexdigest()[:24]
        if session.user_agent_hash and not hmac.compare_digest(session.user_agent_hash, ua_hash):
            self._sessions.pop(token, None)
            return None
        row = self.account(session.account_id)
        if row is None:
            self._sessions.pop(token, None)
            return None
        role = str(row.get("role") or "")
        network_access = str(row.get("network_access") or NETWORK_LOCAL_ONLY)
        local_client = _client_is_local(_effective_remote(request))
        host_row = self.account_by_remote_host(request.host)
        exact_remote_host = bool(
            host_row is not None and host_row.get("account_id") == row.get("account_id")
        )
        if network_access == NETWORK_LOCAL_ONLY and not local_client:
            return None
        if network_access == NETWORK_REMOTE_ONLY and not exact_remote_host:
            return None
        if network_access == NETWORK_LOCAL_REMOTE and not (local_client or exact_remote_host):
            return None
        # A profile-language change made from Fitness settings immediately
        # becomes authoritative for subsequent portal requests.  Do not keep a
        # second, stale language preference on the remote session.
        session.language = self.account_language(row)
        if touch:
            session.last_seen_at = _utcnow()
            row["last_seen_at"] = _iso(session.last_seen_at)
        return row, session

    async def async_logout(self, request: web.Request) -> None:
        token = str(
            request.cookies.get(_SESSION_COOKIE)
            or request.cookies.get(_CAST_SESSION_COOKIE)
            or ""
        )
        session = self._sessions.pop(token, None)
        if session is not None and session.account_id in self._ephemeral_cast_accounts:
            self._ephemeral_cast_accounts.pop(session.account_id, None)
        self._prune_cast_bootstrap()

    async def async_reconcile_remote_dns(self) -> None:
        await self.async_load()
        from .access_control import get_fitness_access_controller

        access = get_fitness_access_controller(self.hass)
        await access.async_load()
        router_ready = self.hass.data.get(DOMAIN, {}).get(PORTAL_MIDDLEWARE_KEY) is True

        async def _set_dns(row: dict[str, Any], enabled: bool) -> None:
            account_id = str(row.get("account_id") or "")
            slug = _normalize_slug(row.get("remote_slug"))
            if _is_admin_role(row.get("role")):
                await access._async_set_external_account(  # noqa: SLF001
                    account_id=account_id, enabled=enabled, subdomain=(slug if enabled else None)
                )
                return
            profile_id = str(row.get("profile_entry_id") or "")
            if profile_id:
                await access._async_set_external_profile(  # noqa: SLF001
                    profile_entry_id=profile_id, enabled=enabled, subdomain=(slug if enabled else None)
                )

        remote_rows = [
            row for row in self._accounts.values()
            if row.get("enabled", True) and _account_remote_enabled(row)
        ]
        if not router_ready:
            for row in remote_rows:
                self._record_error(row, "host_router_unavailable")
                try:
                    await _set_dns(row, False)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning(
                        "Unable to withdraw Fitness remote DNS while hostname routing is unavailable: %s",
                        err,
                    )
            await self._async_save()
            return

        for row in remote_rows:
            if not _normalize_slug(row.get("remote_slug")):
                continue
            try:
                await _set_dns(row, True)
                if (
                    row.get("last_error_code", "").startswith("cloudflare_")
                    or row.get("last_error_code") == "host_router_unavailable"
                ):
                    row["last_error_code"] = ""
                    row["last_error_at"] = ""
            except Exception as err:  # noqa: BLE001
                self._record_error(row, f"cloudflare_reconcile:{getattr(err, 'code', err)}")
        await self._async_save()


# ---------------------------------------------------------------------------
# Restricted backend bridge

_PUBLIC_WS_NAMES: dict[str, tuple[str, str]] = {
    "fitness/dashboard/config": ("dashboard", "websocket_dashboard_config"),
    "fitness/dashboard/cast_targets": ("dashboard", "websocket_dashboard_cast_targets"),
    "fitness/dashboard/about": ("dashboard", "websocket_dashboard_about"),
    "fitness/dashboard/flow_translations": ("dashboard", "websocket_dashboard_flow_translations"),
    "fitness/dashboard/config_flow/start": ("dashboard", "websocket_dashboard_config_flow_start"),
    "fitness/dashboard/config_flow/step": ("dashboard", "websocket_dashboard_config_flow_step"),
    "fitness/dashboard/config_flow/cancel": ("dashboard", "websocket_dashboard_config_flow_cancel"),
    "fitness/dashboard/options_flow/start": ("dashboard", "websocket_dashboard_options_flow_start"),
    "fitness/dashboard/options_flow/step": ("dashboard", "websocket_dashboard_options_flow_step"),
    "fitness/dashboard/options_flow/cancel": ("dashboard", "websocket_dashboard_options_flow_cancel"),
    "fitness/tv/browser_receiver": ("dashboard", "websocket_tv_browser_receiver"),
    "fitness/tv/overview/heartbeat": ("dashboard", "websocket_tv_overview_heartbeat"),
    "fitness/tv/overview/status": ("dashboard", "websocket_tv_overview_status"),
    "fitness/tv/overview/browser_handoff": ("dashboard", "websocket_tv_overview_browser_handoff"),
    "fitness/tv/overview/cast": ("dashboard", "websocket_tv_overview_cast"),
    "fitness/tv/overview/stop": ("dashboard", "websocket_tv_overview_stop"),
    "fitness/workouts/list": ("dashboard", "websocket_workouts_list"),
    "fitness/workouts/delete": ("dashboard", "websocket_workouts_delete"),
    "fitness/workouts/edit": ("dashboard", "websocket_workouts_edit"),
    "fitness/body_composition": ("dashboard", "websocket_body_composition"),
    "fitness/training/tests": ("dashboard", "websocket_training_tests"),
    "fitness/training/daily_plan": ("dashboard", "websocket_training_daily_plan"),
    "fitness/training/plan": ("dashboard", "websocket_training_plan"),
    "fitness/training/plan/start": ("dashboard", "websocket_training_plan_start"),
    "fitness/training/step": ("dashboard", "websocket_training_step"),
    "fitness/training/export_targets": ("dashboard", "websocket_training_export_targets"),
    "fitness/training/export": ("dashboard", "websocket_training_export"),
    "fitness/training/start": ("dashboard", "websocket_training_start"),
    "fitness/weight/confirm": ("dashboard", "websocket_weight_confirm"),
    "fitness/weight/dismiss": ("dashboard", "websocket_weight_dismiss"),
    "fitness/sensor/claim": ("dashboard", "websocket_sensor_claim"),
    "fitness/tv/preferences": ("tv_dashboard", "websocket_tv_preferences"),
    "fitness/tv/preferences/save": ("tv_dashboard", "websocket_tv_preferences_save"),
    "fitness/tv/dashboard/manage": ("tv_dashboard", "websocket_tv_dashboard_manage"),
    "fitness/tv/profile/configure": ("tv_dashboard", "websocket_tv_profile_configure"),
    "fitness/tv/heartbeat": ("tv_dashboard", "websocket_tv_heartbeat"),
    "fitness/tv/cast/status": ("tv_dashboard", "websocket_tv_cast_status"),
    "fitness/tv/cast/rearm": ("tv_dashboard", "websocket_tv_cast_rearm"),
    "fitness/tv/local_cast_handoff": ("tv_dashboard", "websocket_tv_local_cast_handoff"),
    "fitness/tv/local_cast_stopped": ("tv_dashboard", "websocket_tv_local_cast_stopped"),
    "fitness/tv/ack": ("tv_dashboard", "websocket_tv_ack"),
    "fitness/tv/media_command": ("tv_dashboard", "websocket_tv_media_command"),
    "fitness/tv/media_state": ("tv_dashboard", "websocket_tv_media_state"),
    "fitness/tv/music/adapters": ("tv_dashboard", "websocket_tv_music_adapters"),
    "fitness/tv/music/search": ("tv_dashboard", "websocket_tv_music_search"),
    "fitness/tv/music/ytdlp": ("tv_dashboard", "websocket_tv_music_ytdlp"),
    "fitness/tv/music/ma/play": ("tv_dashboard", "websocket_tv_music_ma_play"),
    "fitness/tv/music/ma/state": ("tv_dashboard", "websocket_tv_music_ma_state"),
    "fitness/tv/music/ma/seek": ("tv_dashboard", "websocket_tv_music_ma_seek"),
    "fitness/tv/music/ma/queue": ("tv_dashboard", "websocket_tv_music_ma_queue"),
    "fitness/tv/music/ma/playlist": ("tv_dashboard", "websocket_tv_music_ma_playlist"),
    "fitness/tv/music/ma/playlist/remove": ("tv_dashboard", "websocket_tv_music_ma_playlist_remove"),
    "fitness/tv/music/ma/sendspin": ("tv_dashboard", "websocket_tv_music_ma_sendspin"),
    "fitness/tv/music/browse": ("tv_dashboard", "websocket_tv_music_browse"),
    "fitness/tv/music/resolve": ("tv_dashboard", "websocket_tv_music_resolve"),
    "fitness/tv/start_workout": ("tv_dashboard", "websocket_tv_start_workout"),
    # Fitness-administrator-only commands. Their handlers still perform the
    # same role check against the synthetic Fitness principal.
    "fitness/accounts/share": ("fitness_accounts", "websocket_fitness_accounts_share"),
    "fitness/accounts/share/save": ("fitness_accounts", "websocket_fitness_accounts_share_save"),
    "fitness/accounts/admin": ("fitness_accounts", "websocket_fitness_accounts_admin"),
    "fitness/accounts/save": ("fitness_accounts", "websocket_fitness_accounts_save"),
    "fitness/accounts/delete": ("fitness_accounts", "websocket_fitness_accounts_delete"),
    "fitness/accounts/reset_password": ("fitness_accounts", "websocket_fitness_accounts_reset_password"),
    "fitness/access/settings/save": ("access_control", "websocket_fitness_access_settings_save"),
    "fitness/access/profile/delete": ("access_control", "websocket_fitness_access_profile_delete"),
}


def _handler_for(command_type: str):
    spec = _PUBLIC_WS_NAMES.get(command_type)
    if spec is None:
        return None
    module_name, function_name = spec
    if module_name == "dashboard":
        from . import dashboard as module
    elif module_name == "fitness_accounts":
        from . import fitness_accounts as module
    elif module_name == "access_control":
        from . import access_control as module
    else:
        from . import tv_dashboard as module
    return getattr(module, function_name, None)


async def _run_fitness_handler(hass: HomeAssistant, principal: dict[str, Any], remote: str, payload: dict[str, Any]) -> Any:
    command_type = str(payload.get("type") or "")
    handler = _handler_for(command_type)
    if handler is None:
        raise web.HTTPForbidden(text="Fitness command is not available through the restricted portal")
    msg = dict(payload)
    msg["id"] = 1
    connection = FitnessPortalConnection(principal, remote)
    target = getattr(handler, "__wrapped__", handler)
    try:
        result = target(hass, connection, msg)
        if inspect.isawaitable(result):
            await result
    except Unauthorized as err:
        raise web.HTTPForbidden(text="Fitness profile access denied") from err
    if connection.error:
        code = connection.error.get("code") or "fitness_error"
        message = connection.error.get("message") or code
        body = json.dumps({"error": code, "message": message})
        if code in {"unauthorized", "not_allowed"}:
            raise web.HTTPForbidden(text=body, content_type="application/json")
        raise web.HTTPBadRequest(text=body, content_type="application/json")
    return _json_safe(connection.result)


# ---------------------------------------------------------------------------
# HTTP views / HTML shell


def _security_headers(nonce: str = "", *, cast_receiver: bool = False) -> dict[str, str]:
    script = f"'nonce-{nonce}' " if nonce else ""
    external_images = " https:" if cast_receiver else ""
    external_media = " https:" if cast_receiver else ""
    return {
        "Cache-Control": "no-store, max-age=0",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Strict-Transport-Security": "max-age=31536000",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=(self), bluetooth=(self)",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "X-Permitted-Cross-Domain-Policies": "none",
        "X-DNS-Prefetch-Control": "off",
        "Content-Security-Policy": (
            "default-src 'none'; "
            f"script-src 'self' {script}; style-src 'unsafe-inline'; img-src 'self' data:{external_images}; "
            f"connect-src 'self'; media-src 'self' blob:{external_media}; font-src 'self'; form-action 'self'; "
            "base-uri 'none'; frame-ancestors 'none'"
        ),
    }


def _error_copy(code: str) -> str:
    return {
        "invalid_credentials": "Invalid username or password.",
        "account_locked": "This account is temporarily locked after repeated failed sign-ins.",
        "login_rate_limited": "Too many sign-in attempts. Try again later.",
        "local_network_required": "This Fitness account can only sign in from the home-server network.",
        "remote_host_mismatch": "This account is not assigned to this Fitness hostname.",
        "https_required": "Fitness sign-in requires HTTPS.",
        "password_reset_required": "An administrator must generate a first-time password for this account.",
    }.get(str(code), "Unable to sign in.")


def _login_page(*, title: str, username: str, error: str = "", remote: bool = False, language: str = "en") -> web.Response:
    nonce = secrets.token_urlsafe(18)
    login_csrf = secrets.token_urlsafe(32)
    language = _portal_language(language)
    text = _PORTAL_LOGIN_TEXT.get(language, _PORTAL_LOGIN_TEXT["en"])
    safe_title = html.escape(title or "HA-Fitness")
    safe_username = html.escape(username or "")
    error_html = f'<div class="error" role="alert">{html.escape(_error_copy(error))}</div>' if error else ""
    mode = text["remote"] if remote else text["account"]
    options = "".join(
        f'<option value="{html.escape(code)}"{" selected" if code == language else ""}>{html.escape(label)}</option>'
        for code, label in SUPPORTED_LANGUAGES.items()
    )
    # A dedicated remote hostname is an account capability, not a username
    # discovery surface. The assigned account is shown as identity only; POST
    # authentication ignores any client-selected username for this host.
    identity = (
        f'<div class="assigned"><small>{html.escape(text["account"])}</small><strong>{safe_title}</strong></div>'
        if remote else
        f'<label>{html.escape(text["username"])}<input name="username" value="{safe_username}" autocomplete="username" required maxlength="64"></label>'
    )
    body = f"""<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark light"><title>{html.escape(text['sign_in'])} · HA-Fitness</title><style nonce="{nonce}">
:root{{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;min-height:100dvh;display:grid;place-items:center;padding:22px;background:radial-gradient(circle at 25% 18%,#173b55 0,#0d151d 38%,#080b10 76%);color:#f5f7fa}}main{{width:min(460px,100%);padding:28px;border:1px solid rgba(255,255,255,.12);border-radius:24px;background:rgba(24,28,33,.96);box-shadow:0 24px 70px rgba(0,0,0,.45)}}.brand-row{{display:flex;align-items:center;justify-content:space-between;gap:12px}}.brand{{color:#41bdf5;font-weight:850;letter-spacing:.03em}}.language{{display:flex;align-items:center;gap:7px;color:#9ba6b2;font-size:12px}}select{{min-height:36px;border-radius:10px;border:1px solid #3b434c;background:#11161b;color:#fff;padding:0 9px}}h1{{margin:16px 0 4px;font-size:28px}}.mode{{color:#9ba6b2;margin-bottom:20px}}label{{display:grid;gap:6px;margin:13px 0;color:#cbd3db;font-size:13px}}input{{width:100%;min-height:48px;border-radius:12px;border:1px solid #3b434c;background:#11161b;color:#fff;padding:0 13px;font:inherit}}button{{width:100%;min-height:48px;margin-top:15px;border:0;border-radius:13px;background:#41bdf5;color:#071018;font-size:16px;font-weight:850;cursor:pointer}}.assigned{{display:grid;gap:3px;margin:10px 0 4px;padding:13px;border:1px solid #36404a;border-radius:13px;background:#10161c}}.assigned small{{margin:0;color:#8f9aa5}}.assigned strong{{font-size:16px}}.error{{padding:10px 12px;border-radius:11px;background:#4a1717;color:#ffcccc;margin:12px 0}}small{{display:block;margin-top:16px;color:#8f9aa5;line-height:1.45}}input:focus,button:focus,select:focus{{outline:3px solid #fff;outline-offset:2px}}</style></head><body><main><div class="brand-row"><div class="brand">HA-Fitness</div><label class="language">{html.escape(text['language'])}<select id="fitness-language" aria-label="{html.escape(text['language'])}">{options}</select></label></div><h1>{safe_title}</h1><div class="mode">{html.escape(mode)}</div>{error_html}<form method="post" action="/fitness-auth/login" autocomplete="on"><input type="hidden" name="login_csrf" value="{html.escape(login_csrf)}"><input type="hidden" name="language" value="{language}">{identity}<label>{html.escape(text['password'])}<input type="password" name="password" autocomplete="current-password" required maxlength="128"></label><button type="submit">{html.escape(text['sign_in'])}</button></form><small>{html.escape(text['privacy'])}</small></main><script nonce="{nonce}">document.getElementById("fitness-language").addEventListener("change",e=>{{const u=new URL(location.href);u.searchParams.set("lang",e.target.value);location.href=u.toString();}});</script></body></html>"""
    response = web.Response(text=body, content_type="text/html", charset="utf-8", headers=_security_headers(nonce))
    response.set_cookie(
        _LOGIN_CSRF_COOKIE,
        login_csrf,
        path="/",
        secure=True,
        httponly=True,
        samesite="Strict",
        max_age=600,
    )
    return response


def _password_page(row: dict[str, Any], *, error: str = "", csrf_token: str = "") -> web.Response:
    nonce = secrets.token_urlsafe(18)
    err = f'<div class="error">{html.escape(error.replace("_", " "))}</div>' if error else ""
    body = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Secure your Fitness account</title><style nonce="{nonce}">:root{{font-family:system-ui;color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;min-height:100dvh;display:grid;place-items:center;background:#0a1016;color:#fff;padding:20px}}main{{width:min(500px,100%);padding:26px;border-radius:22px;background:#191d22;border:1px solid #343a41}}label{{display:grid;gap:6px;margin:13px 0}}input{{min-height:46px;border-radius:11px;border:1px solid #46505a;background:#0d1217;color:#fff;padding:0 12px}}button{{width:100%;min-height:48px;margin-top:12px;border:0;border-radius:12px;background:#41bdf5;color:#071018;font-weight:800}}.error{{padding:10px;border-radius:10px;background:#4a1717;color:#ffd0d0}}small{{color:#a8b2bc;line-height:1.45}}</style></head><body><main><h1>Secure your Fitness account</h1><p>Choose a strong password before continuing.</p>{err}<form method="post" action="/fitness-auth/password"><input type="hidden" name="csrf" value="{html.escape(csrf_token)}"><label>New password<input type="password" name="new_password" autocomplete="new-password" required maxlength="128"></label><label>Repeat password<input type="password" name="confirm_password" autocomplete="new-password" required maxlength="128"></label><button type="submit">Save and continue</button></form><small>Use at least 14 characters and a mix of character types. Passwords containing account/profile identifiers or common passwords are rejected.</small></main></body></html>"""
    return web.Response(text=body, content_type="text/html", charset="utf-8", headers=_security_headers(nonce))


def _portal_app_page(
    row: dict[str, Any],
    session: FitnessSession,
    visible_profiles: list[dict[str, str]],
    *,
    cast_receiver: bool = False,
    bootstrap_config: dict[str, Any] | None = None,
    bootstrap_states: dict[str, Any] | None = None,
    bootstrap_preferences: dict[str, Any] | None = None,
    cast_overview_only: bool = False,
) -> web.Response:
    nonce = secrets.token_urlsafe(18)
    language = _portal_language(session.language)
    app_text = _PORTAL_APP_TEXT.get(language, _PORTAL_APP_TEXT["en"])
    app_text_payload = json.dumps(app_text, separators=(",", ":")).replace("</", "<\\/")
    principal = {
        "account_id": row["account_id"],
        "role": row["role"],
        "username": row["username"],
        "display_name": row.get("display_name") or row["username"],
        "profile_entry_id": row.get("profile_entry_id") or None,
        "view_profile_entry_ids": list(row.get("view_profile_entry_ids") or []),
        "is_admin": str(row.get("role") or "") in {"admin", "admin_user"},
        "csrf": session.csrf,
        "visible_profiles": visible_profiles,
        "language": language,
    }
    payload = json.dumps(principal, separators=(",", ":")).replace("</", "<\\/")
    bootstrap_payload = json.dumps(
        {
            "config": bootstrap_config if cast_receiver else None,
            "states": bootstrap_states if cast_receiver else None,
            "preferences": bootstrap_preferences if cast_receiver else None,
            "overview": bool(cast_receiver and cast_overview_only),
        },
        separators=(",", ":"),
    ).replace("</", "<\\/")
    frontend_version = "unreleased-138"
    frontend_cache_version = f"{frontend_version}-cast-ui-146"
    cast_receiver_js = "true" if cast_receiver else "false"
    portal_top_display = "none" if cast_receiver else "flex"
    body = f"""<!doctype html><html lang="{html.escape(language)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark light"><title>HA-Fitness</title><style nonce="{nonce}">
:root{{--primary-color:#03a9f4;--accent-color:#03a9f4;--primary-background-color:#0b0f14;--primary-text-color:#f3f5f7;--text-primary-color:#ffffff;--secondary-text-color:#aab4bf;--disabled-text-color:#78828c;--card-background-color:#1c1f22;--ha-card-background:#1c1f22;--secondary-background-color:#25292d;--divider-color:#3b4147;--error-color:#ef5350;--success-color:#43a047;--warning-color:#ffb300;--info-color:#039be5;--ha-card-box-shadow:0 2px 8px rgba(0,0,0,.20);--ha-card-border-radius:12px;--state-icon-color:#aab4bf;--state-icon-active-color:#03a9f4;--paper-item-icon-color:#aab4bf;--paper-item-icon-active-color:#03a9f4;--mdc-theme-primary:#03a9f4;--mdc-theme-on-primary:#ffffff;--mdc-theme-surface:#1c1f22;--mdc-theme-on-surface:#f3f5f7;color-scheme:dark;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0b0f14;color:var(--primary-text-color)}}*{{box-sizing:border-box}}html,body{{margin:0;min-height:100dvh;background:#0b0f14;color:var(--primary-text-color);overscroll-behavior-y:none}}body{{overflow-x:hidden;touch-action:pan-y;background:var(--fitness-portal-background,#0b0f14)}}ha-card{{display:block;background:var(--card-background-color);color:var(--primary-text-color)}}#portal-top{{position:sticky;z-index:10000;top:0;width:100%;display:{portal_top_display};justify-content:flex-end;gap:7px;align-items:center;padding:max(8px,env(safe-area-inset-top)) max(10px,env(safe-area-inset-right)) 8px max(10px,env(safe-area-inset-left));background:color-mix(in srgb,#0b0f14 88%,transparent);border-bottom:1px solid #252c34;backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}}#portal-top button,#portal-top select{{min-height:40px;max-width:min(42vw,240px);border-radius:12px;border:1px solid var(--divider-color);background:#171b20;color:#fff;padding:0 11px;font:inherit;overflow:hidden;text-overflow:ellipsis}}#app{{min-height:calc(100dvh - var(--fitness-portal-top-height,57px));width:100%;overflow-x:hidden;touch-action:pan-y;background:var(--fitness-tv-ambient,var(--fitness-portal-background,#0b0f14));--fitness-tv-toolbar-reveal-top:calc(var(--fitness-portal-top-height,57px) + 4px)}}#app>fitness-tv-dashboard-card,#app>fitness-tv-setup-card{{display:block;min-height:calc(100dvh - var(--fitness-portal-top-height,57px));background:var(--fitness-tv-ambient,var(--fitness-portal-background,#0b0f14))}}</style></head><body><div id="portal-top"><select id="profile-nav" aria-label="{html.escape(app_text['profile'])}"></select><button id="logout-btn">{html.escape(app_text['sign_out'])}</button></div><main id="app"></main><script nonce="{nonce}">window.__FITNESS_PUBLIC_SESSION__={payload};window.__FITNESS_PORTAL_TEXT__={app_text_payload};window.__FITNESS_CAST_PORTAL__={cast_receiver_js};window.__FITNESS_CAST_BOOTSTRAP__={bootstrap_payload};
</script><script nonce="{nonce}" src="/fitness/frontend/fitness-mdi-icons.js?v=7.4.47-fitness-1"></script><script nonce="{nonce}">
const FITNESS_PORTAL_ICON_GLYPHS={{
"mdi:account-multiple-outline":"♙♙","mdi:account-circle-outline":"●","mdi:account-cog-outline":"⚙","mdi:cog-outline":"⚙","mdi:view-dashboard-edit-outline":"▦","mdi:view-dashboard-outline":"▦","mdi:view-grid-plus-outline":"⊞","mdi:drag":"☷","mdi:access-point":"◉","mdi:fullscreen":"⛶","mdi:fullscreen-exit":"⛶","mdi:cast":"▣","mdi:cast-off":"□","mdi:play":"▶","mdi:pause":"Ⅱ","mdi:folder-music-outline":"♫","mdi:album":"♪","mdi:skip-previous":"◀|","mdi:skip-next":"|▶","mdi:shuffle":"⇄","mdi:repeat":"↻","mdi:playlist-edit":"☷","mdi:chevron-left":"‹","mdi:chevron-right":"›","mdi:chevron-down":"⌄","mdi:chevron-up":"⌃","mdi:close":"×","mdi:eye-outline":"◉","mdi:content-save-outline":"✓","mdi:plus":"+","mdi:minus-circle-outline":"−","mdi:refresh":"↻","mdi:bluetooth-connect":"ᛒ","mdi:bluetooth-off":"ᛒ","mdi:usb":"⌁","mdi:usb-off":"⌁","mdi:check-circle":"✓","mdi:shield-lock-outline":"◆","mdi:loading":"◌","mdi:run-fast":"➤","mdi:sleep":"☾","mdi:heart-pulse":"♥"
}};
const fitnessPortalIconPath=(key)=>String(window.__FITNESS_MDI_PATHS__?.[key]||"");
const fitnessPortalGlyph=(key)=>FITNESS_PORTAL_ICON_GLYPHS[key]||"●";
if(!customElements.get("ha-icon"))customElements.define("ha-icon",class extends HTMLElement{{static get observedAttributes(){{return["icon"]}}connectedCallback(){{if(!this.shadowRoot)this.attachShadow({{mode:"open"}});this._draw()}}attributeChangedCallback(){{if(this.isConnected)this._draw()}}_draw(){{const key=String(this.getAttribute("icon")||"");const root=this.shadowRoot||this.attachShadow({{mode:"open"}});const path=fitnessPortalIconPath(key);this.setAttribute("aria-hidden","true");this.style.cssText="display:inline-flex;align-items:center;justify-content:center;width:var(--mdc-icon-size,22px);height:var(--mdc-icon-size,22px);line-height:1;flex:0 0 auto;color:inherit";if(path){{root.innerHTML='<svg viewBox="0 0 512 512" aria-hidden="true" focusable="false" style="display:block;width:100%;height:100%;fill:currentColor"><g transform="translate(0 448) scale(1 -1)"><path d="'+path+'"></path></g></svg>';return}}const glyph=fitnessPortalGlyph(key);root.innerHTML='<span aria-hidden="true" style="display:grid;place-items:center;width:100%;height:100%;font:800 78%/1 system-ui,sans-serif">'+glyph+'</span>'}}}});
if(!customElements.get("ha-card"))customElements.define("ha-card",class extends HTMLElement{{}});
if(!customElements.get("ha-circular-progress"))customElements.define("ha-circular-progress",class extends HTMLElement{{connectedCallback(){{this.setAttribute("aria-hidden","true");this.style.cssText="display:inline-block;width:22px;height:22px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%"}}}});
</script><script type="module" nonce="{nonce}" src="/fitness/frontend/fitness-dashboard.js?v={frontend_cache_version}"></script><script type="module" nonce="{nonce}">
const session=window.__FITNESS_PUBLIC_SESSION__;const portalText=window.__FITNESS_PORTAL_TEXT__||{{}};const castBootstrap=window.__FITNESS_CAST_BOOTSTRAP__||{{}};const csrf=session.csrf;const castPortal=Boolean(window.__FITNESS_CAST_PORTAL__);const castTicket=castPortal?String(location.pathname.split("/").filter(Boolean).pop()||""):"";const ADMIN_VIEW="__fitness_admin__";let currentProfile=session.is_admin?ADMIN_VIEW:(session.profile_entry_id||session.visible_profiles?.[0]?.entry_id||"");const app=document.getElementById("app");const nav=document.getElementById("profile-nav");
const syncPortalGeometry=()=>{{if(castPortal){{document.documentElement.style.setProperty("--fitness-portal-top-height","0px");return;}}const top=document.getElementById("portal-top");const h=Math.max(48,Math.ceil(top?.getBoundingClientRect?.().height||57));document.documentElement.style.setProperty("--fitness-portal-top-height",`${{h}}px`)}};syncPortalGeometry();addEventListener("resize",syncPortalGeometry,{{passive:true}});
if(session.is_admin&&!castPortal){{const o=document.createElement("option");o.value=ADMIN_VIEW;o.textContent=portalText.administration||"Fitness administration";o.selected=currentProfile===ADMIN_VIEW;nav.appendChild(o)}}for(const p of session.visible_profiles||[]){{const o=document.createElement("option");o.value=p.entry_id;o.textContent=p.name+(p.mode==="view"?` · ${{portalText.view_only||"view only"}}`:"");o.selected=p.entry_id===currentProfile;nav.appendChild(o)}}if(castPortal||(session.visible_profiles||[]).length+(session.is_admin?1:0)<2)nav.hidden=true;
const castHeaders=()=>castTicket?{{"X-Fitness-Cast-Ticket":castTicket}}:{{}};const portalReadCache=new Map();const portalInflight=new Map();
const normalizeDashboardConfig=(result)=>{{if(result&&Array.isArray(result.profiles)){{result.profiles=result.profiles.map(p=>{{const lang=String(p?.language||session.language||"en").toLowerCase().split("-")[0];return {{...p,language:lang,labels:p?.labels_by_language?.[lang]||p?.labels_by_language?.en||p?.labels}};}});const active=result.profiles.find(p=>String(p?.entry_id||"")===String(currentProfile||""))||result.profiles.find(p=>p?.access?.is_own)||result.profiles[0];const lang=String(active?.language||session.language||"en").toLowerCase().split("-")[0];hass.language=lang;result.labels=result.labels_by_language?.[lang]||result.labels_by_language?.en||result.labels;}}return result;}};
const cacheTtl=(msg)=>castPortal&&msg?.type==="fitness/dashboard/config"?15000:0;
const hass={{states:(castBootstrap.states||{{}}),language:session.language||"en",user:{{name:session.display_name,is_admin:session.is_admin}},connection:null,callWS:async(msg)=>{{const key=JSON.stringify(msg||{{}});if(castPortal&&msg?.type==="fitness/dashboard/config"&&castBootstrap.config){{if(!portalReadCache.has(key))portalReadCache.set(key,{{at:Date.now(),value:normalizeDashboardConfig(castBootstrap.config)}});return portalReadCache.get(key).value;}}if(castPortal&&msg?.type==="fitness/tv/preferences"&&castBootstrap.preferences&&String(msg?.profile_entry_id||"")===String(currentProfile||""))return castBootstrap.preferences;const ttl=cacheTtl(msg);const hit=portalReadCache.get(key);if(ttl&&hit&&Date.now()-hit.at<ttl)return hit.value;if(portalInflight.has(key))return portalInflight.get(key);const task=(async()=>{{const r=await fetch("/fitness-auth/ws",{{method:"POST",credentials:"same-origin",headers:{{"Content-Type":"application/json","X-Fitness-CSRF":csrf,...castHeaders()}},body:JSON.stringify(msg)}});const data=await r.json().catch(()=>({{}}));if(!r.ok){{expireCastPortal(r.status,data);const err=new Error(data.message||data.error||`HTTP ${{r.status}}`);err.code=String(data.error||"");throw err;}}const result=msg?.type==="fitness/dashboard/config"?normalizeDashboardConfig(data.result):data.result;if(ttl)portalReadCache.set(key,{{at:Date.now(),value:result}});return result;}})();portalInflight.set(key,task);try{{return await task;}}finally{{portalInflight.delete(key);}}}},callService:async(domain,service,serviceData={{}},target={{}})=>{{const r=await fetch("/fitness-auth/service",{{method:"POST",credentials:"same-origin",headers:{{"Content-Type":"application/json","X-Fitness-CSRF":csrf,...castHeaders()}},body:JSON.stringify({{domain,service,service_data:serviceData,target}})}});const data=await r.json().catch(()=>({{}}));if(!r.ok){{expireCastPortal(r.status,data);const err=new Error(data.message||data.error||`HTTP ${{r.status}}`);err.code=String(data.error||"");throw err;}}return data.result;}}}};
let statesRefreshInFlight=false;let statesEtag="";async function refreshStates(){{if(statesRefreshInFlight)return;try{{if(currentProfile===ADMIN_VIEW)return;statesRefreshInFlight=true;const headers={{...castHeaders()}};if(statesEtag)headers["If-None-Match"]=statesEtag;const r=await fetch("/fitness-auth/states",{{credentials:"same-origin",cache:"no-store",headers}});if(r.status===304)return;if(!r.ok){{expireCastPortal(r.status);return;}}statesEtag=String(r.headers.get("ETag")||"");const data=await r.json();const next=data.states||{{}};hass.states=next;if(card)card.hass=hass;}}catch(_e){{}}finally{{statesRefreshInFlight=false;}}}}
const overviewCastPortal=Boolean(castPortal&&castBootstrap?.overview);
let portalStateTimer=null;let portalHeartbeatTimer=null;let castPortalExpired=false;
const quitCastPortal=()=>{{if(castPortalExpired)return;castPortalExpired=true;if(portalStateTimer)clearInterval(portalStateTimer);if(portalHeartbeatTimer)clearInterval(portalHeartbeatTimer);try{{globalThis.cast?.framework?.CastReceiverContext?.getInstance?.()?.stop?.();}}catch(_e){{}}try{{globalThis.close?.();}}catch(_e){{}}setTimeout(()=>{{try{{globalThis.location?.replace?.("about:blank");}}catch(_e){{}}}},250);}};
const expireCastPortal=(status,data={{}})=>{{if(!castPortal||castPortalExpired)return false;const expired=Number(status||0)===410||String(data?.error||"")==="cast_session_expired";if(expired){{quitCastPortal();return true;}}return false;}};
async function armCastBootstrap(){{if(!castPortal||castPortalExpired)return null;const clientId=String(window.__fitnessTvClientId||`fitness-tv-${{Date.now()}}-${{Math.random().toString(36).slice(2)}}`);window.__fitnessTvClientId=clientId;if(overviewCastPortal){{const result=await hass.callWS({{type:"fitness/tv/overview/heartbeat",client_id:clientId}});if(result?.stop_requested||result?.cast_conflict){{quitCastPortal();return result;}}if(currentProfile&&currentProfile!==ADMIN_VIEW){{const profileResult=await hass.callWS({{type:"fitness/tv/heartbeat",profile_entry_id:currentProfile,client_id:clientId,is_cast_receiver:true}});if(profileResult?.stop_requested||profileResult?.cast_conflict)quitCastPortal();}}return result;}}if(!currentProfile||currentProfile===ADMIN_VIEW)return null;const result=await hass.callWS({{type:"fitness/tv/heartbeat",profile_entry_id:currentProfile,client_id:clientId,is_cast_receiver:true}});if(result?.stop_requested||result?.cast_conflict)quitCastPortal();return result;}}
const visibleProfileIds=new Set((session.visible_profiles||[]).map((p)=>String(p.entry_id||"")));
const routeProfile=()=>{{const path=String(location.pathname||"");if(session.is_admin&&(path==="/fitness-tv"||path==="/fitness-tv/"||path==="/fitness-tv/main"))return ADMIN_VIEW;const prefix="/fitness-tv/profile-";if(path.startsWith(prefix)){{const entryId=String(path.slice(prefix.length)||"");if(visibleProfileIds.has(entryId))return entryId;}}return "";}};
let card=null;function mount(profileId){{const requested=String(profileId||"");const allowed=requested===ADMIN_VIEW?Boolean(session.is_admin):visibleProfileIds.has(requested);if(!allowed)return;currentProfile=requested;statesEtag="";portalReadCache.clear();app.replaceChildren();if(requested===ADMIN_VIEW&&session.is_admin){{card=document.createElement("fitness-tv-setup-card");card.setConfig?.({{}})}}else{{card=document.createElement("fitness-tv-dashboard-card");card.setConfig?.({{profile_entry_id:requested}})}}card.setAttribute("fitness-public-portal","");if(castPortal)card.setAttribute("fitness-cast-receiver","");card.hass=hass;app.appendChild(card);if(!nav.hidden&&[...nav.options].some((o)=>o.value===requested))nav.value=requested;syncPortalGeometry();if(requested!==ADMIN_VIEW)void refreshStates();}}
const syncRoute=()=>{{const routed=routeProfile();if(routed&&routed!==currentProfile)mount(routed);}};
async function startPortal(){{const routed=routeProfile();if(routed)currentProfile=routed;if(castPortal){{try{{await armCastBootstrap();}}catch(err){{console.error("[Fitness TV] Cast bootstrap heartbeat failed",err);}}}}mount(currentProfile);if(castPortal)setTimeout(()=>void refreshStates(),1000);}}
nav.onchange=()=>mount(nav.value);addEventListener("location-changed",syncRoute);addEventListener("popstate",syncRoute);void startPortal();portalStateTimer=setInterval(refreshStates,castPortal?2500:3000);if(castPortal)portalHeartbeatTimer=setInterval(()=>void armCastBootstrap().catch((err)=>console.debug("[Fitness TV] portal heartbeat unavailable",err)),4000);
document.getElementById("logout-btn").onclick=async()=>{{await fetch("/fitness-auth/logout",{{method:"POST",headers:{{"X-Fitness-CSRF":csrf,...castHeaders()}}}});location.href="/"}};

</script></body></html>"""
    return web.Response(
        text=body,
        content_type="text/html",
        charset="utf-8",
        headers=_security_headers(nonce, cast_receiver=cast_receiver),
    )


class FitnessDashCastBootstrapView(HomeAssistantView):
    """Serve one profile through the restricted local Fitness portal for DashCast."""

    url = "/fitness/cast/{ticket}"
    name = "api:fitness:dashcast-bootstrap"
    requires_auth = False

    async def get(self, request: web.Request, ticket: str) -> web.Response:
        controller = get_fitness_account_controller(request.app["hass"])
        redeemed = await controller.async_redeem_cast_bootstrap(
            request, str(ticket or "")
        )
        if redeemed is None:
            raise web.HTTPNotFound(text="Fitness Cast session is unavailable")
        row, session = redeemed
        hass: HomeAssistant = request.app["hass"]
        if not row.get("_cast_overview_only") and not row.get("_cast_receiver_armed"):
            profile_entry_id = str(row.get("profile_entry_id") or "")
            if profile_entry_id:
                from .tv_dashboard import get_tv_dashboard_hub  # noqa: PLC0415
                hub = get_tv_dashboard_hub(hass)
                await hub.async_load()
                hub.expect_local_cast(profile_entry_id, f"smart-tv:{str(ticket)[:18]}")
                row["_cast_receiver_armed"] = True
        principal = controller.principal(row)
        remote = _effective_remote(request)
        visible = await _visible_profile_rows(hass, principal, remote)
        bootstrap_config: dict[str, Any] | None = None
        bootstrap_preferences: dict[str, Any] | None = None
        bootstrap_states: dict[str, Any] = {}
        try:
            config_result = await _run_fitness_handler(
                hass, principal, remote, {"type": "fitness/dashboard/config"}
            )
            if isinstance(config_result, dict):
                bootstrap_config = config_result
                entity_ids = tuple(sorted(_collect_entity_ids(config_result)))
                session.state_entity_ids = entity_ids
                for entity_id in entity_ids:
                    state = hass.states.get(entity_id)
                    if state is None:
                        continue
                    bootstrap_states[entity_id] = {
                        "entity_id": entity_id,
                        "state": state.state,
                        "attributes": _json_safe(dict(state.attributes)),
                        "last_changed": state.last_changed.isoformat(),
                        "last_updated": state.last_updated.isoformat(),
                    }
            profile_entry_id = str(row.get("profile_entry_id") or "")
            if profile_entry_id:
                prefs_result = await _run_fitness_handler(
                    hass,
                    principal,
                    remote,
                    {
                        "type": "fitness/tv/preferences",
                        "profile_entry_id": profile_entry_id,
                    },
                )
                if isinstance(prefs_result, dict):
                    bootstrap_preferences = prefs_result
        except Exception as err:  # noqa: BLE001 - preloading is a performance hint only
            _LOGGER.debug("Fitness Cast bootstrap preload unavailable: %s", err)
        response = _portal_app_page(
            row,
            session,
            visible,
            cast_receiver=True,
            bootstrap_config=bootstrap_config,
            bootstrap_states=bootstrap_states,
            bootstrap_preferences=bootstrap_preferences,
            cast_overview_only=bool(row.get("_cast_overview_only")),
        )
        # LAN receivers may use HTTP; remote receivers use the HTTPS portal.
        # In both cases the random in-memory session is bound to the first
        # receiver IP + user agent.
        response.set_cookie(
            _CAST_SESSION_COOKIE,
            session.token,
            path="/",
            secure=bool(request.secure or str(request.headers.get("X-Forwarded-Proto") or "").lower() == "https"),
            httponly=True,
            samesite="Strict",
        )
        return response


class FitnessPortalLoginView(HomeAssistantView):
    url = "/fitness-auth/login"
    name = "api:fitness:portal-login"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        controller = get_fitness_account_controller(request.app["hass"])
        await controller.async_load()
        remote_account = controller.account_by_remote_host(request.host)
        requested_language = str(request.query.get("lang") or "").strip()
        remembered_language = str(request.cookies.get(_LANGUAGE_COOKIE) or "").strip()
        language = _portal_language(
            requested_language or remembered_language or controller.account_language(remote_account)
        )
        response = _login_page(
            title=str((remote_account or {}).get("display_name") or "Fitness sign in"),
            username=str((remote_account or {}).get("username") or (remote_account or {}).get("remote_slug") or ""),
            remote=remote_account is not None,
            language=language,
        )
        response.set_cookie(
            _LANGUAGE_COOKIE, language, path="/", max_age=31536000,
            secure=True, httponly=False, samesite="Strict",
        )
        return response

    async def post(self, request: web.Request) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        controller = get_fitness_account_controller(hass)
        if not _secure_request(request):
            return _login_page(title="Fitness sign in", username="", error="https_required", language=_portal_language(request.query.get("lang")))
        form = await _bounded_form_body(request)
        if not _login_csrf_valid(request, form):
            raise web.HTTPForbidden(text="Cross-site Fitness sign-in is not allowed")
        password = str(form.get("password") or "")[:128]
        language = _portal_language(form.get("language"))
        remote_account = controller.account_by_remote_host(request.host)
        # On an administrator-assigned subdomain the hostname chooses the
        # account. Never accept a username override from a modified form.
        username = (
            str(remote_account.get("username") or "")
            if remote_account is not None
            else _safe_text(form.get("username"), 64)
        )
        try:
            row, session = await controller.async_authenticate(
                username=username,
                password=password,
                remote=_effective_remote(request),
                host=request.host,
                user_agent=str(request.headers.get("User-Agent") or ""),
                language=language,
            )
        except ValueError as err:
            return _login_page(
                title=str((remote_account or {}).get("display_name") or "Fitness sign in"),
                username=username,
                error=str(err),
                remote=remote_account is not None,
                language=language,
            )
        response = web.HTTPFound(location="/fitness-auth/password" if row.get("password_change_required") else "/fitness-auth/app")
        # Deliberately use a browser-session cookie: closing the browser/TV web
        # session requires a fresh Fitness login. The server still enforces the
        # stricter 12-hour absolute / 2-hour idle session limits in memory.
        response.set_cookie(
            _SESSION_COOKIE,
            session.token,
            path="/",
            secure=True,
            httponly=True,
            samesite="Strict",
        )
        response.del_cookie(_LOGIN_CSRF_COOKIE, path="/")
        response.set_cookie(
            _LANGUAGE_COOKIE, session.language, path="/", max_age=31536000,
            secure=True, httponly=False, samesite="Strict",
        )
        raise response


class FitnessPortalPasswordView(HomeAssistantView):
    url = "/fitness-auth/password"
    name = "api:fitness:portal-password"
    requires_auth = False

    async def get(self, request: web.Request) -> web.StreamResponse:
        controller = get_fitness_account_controller(request.app["hass"])
        auth = await controller.async_session(request)
        if auth is None:
            raise web.HTTPFound(location="/fitness-auth/login")
        row, session = auth
        if not row.get("password_change_required"):
            raise web.HTTPFound(location="/fitness-auth/app")
        return _password_page(row, csrf_token=session.csrf)

    async def post(self, request: web.Request) -> web.StreamResponse:
        controller = get_fitness_account_controller(request.app["hass"])
        auth = await controller.async_session(request)
        if auth is None:
            raise web.HTTPFound(location="/fitness-auth/login")
        row, _session = auth
        form = await _bounded_form_body(request)
        submitted_csrf = str(form.get("csrf") or "")
        if not submitted_csrf or not secrets.compare_digest(submitted_csrf, _session.csrf):
            raise web.HTTPForbidden(text="Cross-site Fitness credential change is not allowed")
        new_password = str(form.get("new_password") or "")[:128]
        if new_password != str(form.get("confirm_password") or "")[:128]:
            return _password_page(row, error="passwords_do_not_match", csrf_token=_session.csrf)
        try:
            await controller.async_change_credentials(
                str(row["account_id"]),
                current_password=None,
                new_password=new_password,
                new_username=None,
                first_login=True,
                preserve_session_token=_session.token,
            )
        except ValueError as err:
            return _password_page(row, error=str(err), csrf_token=_session.csrf)
        raise web.HTTPFound(location="/fitness-auth/app")


class FitnessPortalAppView(HomeAssistantView):
    url = "/fitness-auth/app"
    name = "api:fitness:portal-app"
    requires_auth = False

    async def get(self, request: web.Request) -> web.StreamResponse:
        controller = get_fitness_account_controller(request.app["hass"])
        auth = await controller.async_session(request)
        if auth is None:
            raise web.HTTPFound(location="/fitness-auth/login")
        row, session = auth
        if row.get("password_change_required"):
            raise web.HTTPFound(location="/fitness-auth/password")
        visible = await _visible_profile_rows(request.app["hass"], controller.principal(row), _effective_remote(request))
        return _portal_app_page(row, session, visible)


def _raise_missing_portal_session(request: web.Request) -> None:
    """End stale Cast pages cleanly instead of producing repeated auth failures."""
    if str(request.headers.get("X-Fitness-Cast-Ticket") or "").strip():
        raise web.HTTPGone(
            text=json.dumps({"error": "cast_session_expired"}),
            content_type="application/json",
        )
    raise web.HTTPUnauthorized()


class FitnessPortalSessionView(HomeAssistantView):
    url = "/fitness-auth/session"
    name = "api:fitness:portal-session"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        controller = get_fitness_account_controller(request.app["hass"])
        auth = await controller.async_session(request)
        if auth is None:
            _raise_missing_portal_session(request)
        row, session = auth
        return self.json({"account": controller.public_account(row), "csrf": session.csrf, "language": session.language})


def _sanitize_cast_overview_config(config: dict[str, Any]) -> dict[str, Any]:
    """Strip HA-local hardware/control metadata from the read-only TV overview."""
    safe = _json_safe(config)
    if not isinstance(safe, dict):
        return {}
    safe["cast_targets"] = []
    safe["audio_outputs"] = []
    safe["overview_cast"] = {"active": False, "target": None}
    access = safe.get("access")
    if isinstance(access, dict):
        access["local_ha_hardware_allowed"] = False
    for profile in safe.get("profiles") or []:
        if not isinstance(profile, dict):
            continue
        profile["route_candidates"] = {}
        tv = profile.get("tv_dashboard")
        if isinstance(tv, dict):
            tv["cast_media_player_id"] = ""
            tv["cast_target"] = None
    return safe


class FitnessPortalWSView(HomeAssistantView):
    url = "/fitness-auth/ws"
    name = "api:fitness:portal-ws-bridge"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        controller = get_fitness_account_controller(request.app["hass"])
        auth = await controller.async_session(request)
        if auth is None:
            _raise_missing_portal_session(request)
        row, session = auth
        if not hmac.compare_digest(str(request.headers.get("X-Fitness-CSRF") or ""), session.csrf):
            raise web.HTTPForbidden(text="CSRF validation failed")
        payload = await _bounded_json_body(request, limit=256_000)
        result = await _run_fitness_handler(
            request.app["hass"], controller.principal(row), _effective_remote(request), payload
        )
        return self.json({"result": result})


class FitnessPortalStatesView(HomeAssistantView):
    url = "/fitness-auth/states"
    name = "api:fitness:portal-states"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        controller = get_fitness_account_controller(request.app["hass"])
        auth = await controller.async_session(request)
        if auth is None:
            _raise_missing_portal_session(request)
        row, session = auth
        principal = controller.principal(row)
        entity_ids = set(session.state_entity_ids)
        if not entity_ids:
            config = await _run_fitness_handler(
                request.app["hass"], principal, _effective_remote(request), {"type": "fitness/dashboard/config"}
            )
            entity_ids = _collect_entity_ids(config)
            if str(row.get("account_id") or "") in controller._ephemeral_cast_accounts:  # noqa: SLF001
                session.state_entity_ids = tuple(sorted(entity_ids))
        states: dict[str, Any] = {}
        revision_parts: list[str] = []
        hass: HomeAssistant = request.app["hass"]
        selected_states: list[tuple[str, Any]] = []
        for entity_id in sorted(entity_ids):
            state = hass.states.get(entity_id)
            if state is None:
                revision_parts.append(f"{entity_id}:missing")
                continue
            selected_states.append((entity_id, state))
            revision_parts.append(
                f"{entity_id}:{state.state}:{state.last_updated.isoformat()}"
            )
        revision = hashlib.sha256("\n".join(revision_parts).encode("utf-8")).hexdigest()[:24]
        etag = f'"fitness-{revision}"'
        if str(request.headers.get("If-None-Match") or "").strip() == etag:
            return web.Response(
                status=304,
                headers={"ETag": etag, "Cache-Control": "no-store"},
            )
        for entity_id, state in selected_states:
            states[entity_id] = {
                "entity_id": entity_id,
                "state": state.state,
                "attributes": _json_safe(dict(state.attributes)),
                "last_changed": state.last_changed.isoformat(),
                "last_updated": state.last_updated.isoformat(),
            }
        response = self.json({"states": states})
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "no-store"
        return response


def _controlled_entity_ids(config: Any, controlled: set[str]) -> set[str]:
    if not isinstance(config, dict):
        return set()
    safe_profiles = [
        row for row in (config.get("profiles") or [])
        if isinstance(row, dict) and str(row.get("entry_id") or "") in controlled
    ]
    return _collect_entity_ids({"profiles": safe_profiles})


class FitnessPortalServiceView(HomeAssistantView):
    url = "/fitness-auth/service"
    name = "api:fitness:portal-service"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        controller = get_fitness_account_controller(hass)
        auth = await controller.async_session(request)
        if auth is None:
            _raise_missing_portal_session(request)
        row, session = auth
        if not hmac.compare_digest(str(request.headers.get("X-Fitness-CSRF") or ""), session.csrf):
            raise web.HTTPForbidden(text="CSRF validation failed")
        payload = await _bounded_json_body(request, limit=64_000)
        domain = str(payload.get("domain") or "")
        service = str(payload.get("service") or "")
        target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
        service_data = payload.get("service_data") if isinstance(payload.get("service_data"), dict) else {}
        principal = controller.principal(row)
        access = await _profile_access_sets(hass, principal, _effective_remote(request))
        controlled = access[1]
        if not controlled:
            raise web.HTTPForbidden(text="View-only Fitness account")
        # Direct entity service calls are limited to entity IDs the controlled
        # profile already exposes through its safe dashboard metadata.
        config = await _run_fitness_handler(hass, principal, _effective_remote(request), {"type": "fitness/dashboard/config"})
        allowed_entities = _controlled_entity_ids(config, controlled)
        entity_ids = target.get("entity_id", service_data.get("entity_id"))
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        entity_ids = [str(item) for item in (entity_ids or [])]
        if (domain, service) in {("button", "press"), ("number", "set_value")}:
            if not entity_ids or any(entity_id not in allowed_entities for entity_id in entity_ids):
                raise web.HTTPForbidden(text="Entity is outside this Fitness profile")
        elif domain == "fitness" and service in {"cast_tv_dashboard", "stop_tv_dashboard"}:
            if not _client_is_local(_effective_remote(request)):
                raise web.HTTPForbidden(text="Home Assistant TV control is available only on the local network")
            requested = str(service_data.get("profile_entry_id") or "")
            if requested not in controlled:
                raise web.HTTPForbidden(text="Fitness profile control required")
        else:
            raise web.HTTPForbidden(text="Service is not available through the restricted Fitness portal")
        await hass.services.async_call(domain, service, service_data, target=target or None, blocking=True)
        return self.json({"result": {"ok": True}})


class FitnessPortalAccountView(HomeAssistantView):
    url = "/fitness-auth/account"
    name = "api:fitness:portal-account"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        controller = get_fitness_account_controller(request.app["hass"])
        auth = await controller.async_session(request)
        if auth is None:
            _raise_missing_portal_session(request)
        row, session = auth
        if not hmac.compare_digest(str(request.headers.get("X-Fitness-CSRF") or ""), session.csrf):
            raise web.HTTPForbidden(text="CSRF validation failed")
        payload = await _bounded_json_body(request, limit=32_000)
        try:
            updated = await controller.async_change_credentials(
                str(row["account_id"]),
                current_password=str(payload.get("current_password") or ""),
                new_password=(str(payload.get("new_password")) if payload.get("new_password") else None),
                new_username=None,
                first_login=False,
                preserve_session_token=session.token,
            )
        except ValueError as err:
            return self.json({"error": str(err)}, status_code=400)
        return self.json({"account": updated})


class FitnessPortalLogoutView(HomeAssistantView):
    url = "/fitness-auth/logout"
    name = "api:fitness:portal-logout"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        controller = get_fitness_account_controller(request.app["hass"])
        auth = await controller.async_session(request, touch=False)
        if auth is not None:
            _row, session = auth
            if not hmac.compare_digest(str(request.headers.get("X-Fitness-CSRF") or ""), session.csrf):
                raise web.HTTPForbidden(text="CSRF validation failed")
        await controller.async_logout(request)
        response = self.json({"ok": True})
        response.del_cookie(_SESSION_COOKIE, path="/")
        response.del_cookie(_CAST_SESSION_COOKIE, path="/")
        return response


async def _profile_access_sets(hass: HomeAssistant, principal: dict[str, Any], remote: str) -> tuple[set[str], set[str]]:
    from .access_control import get_fitness_access_controller

    connection = FitnessPortalConnection(principal, remote)
    access = get_fitness_access_controller(hass)
    return (
        await access.async_visible_profile_ids(connection),
        await access.async_control_profile_ids(connection),
    )


async def _visible_profile_rows(hass: HomeAssistant, principal: dict[str, Any], remote: str) -> list[dict[str, str]]:
    visible, controlled = await _profile_access_sets(hass, principal, remote)
    rows: list[dict[str, str]] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id not in visible or entry.data.get("entry_type") in {"live_hub", "devices_hub"}:
            continue
        cfg = {**entry.data, **entry.options}
        rows.append({
            "entry_id": entry.entry_id,
            "name": str(cfg.get("profile_name") or entry.title or entry.entry_id),
            "mode": "control" if entry.entry_id in controlled else "view",
        })
    return rows



# ---------------------------------------------------------------------------
# Native / restricted WebSocket administration API

import voluptuous as vol
from homeassistant.components import websocket_api


async def _require_fitness_admin(hass: HomeAssistant, connection) -> None:
    from .access_control import get_fitness_access_controller

    await get_fitness_access_controller(hass).async_require_admin(connection)


async def _sharing_owner_account_id(hass: HomeAssistant, connection) -> str:
    """Return the authenticated Fitness account allowed to share its own profile."""
    from .access_control import get_fitness_access_controller

    descriptor = await get_fitness_access_controller(hass).async_descriptor(connection)
    account_id = str(descriptor.get("account_id") or "")
    profile_id = str(descriptor.get("profile_entry_id") or "")
    if not account_id or not profile_id or not descriptor.get("session_allowed"):
        raise PermissionError("fitness_account_required")
    return account_id


@websocket_api.websocket_command({vol.Required("type"): "fitness/accounts/share"})
@websocket_api.async_response
async def websocket_fitness_accounts_share(hass: HomeAssistant, connection, msg) -> None:
    """Return accounts the current Fitness user may grant view-only access to."""
    try:
        account_id = await _sharing_owner_account_id(hass, connection)
        controller = get_fitness_account_controller(hass)
        connection.send_result(msg["id"], controller.sharing_snapshot(account_id))
    except (PermissionError, ValueError) as err:
        connection.send_error(msg["id"], "unauthorized", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/accounts/share/save",
        vol.Optional("viewer_account_ids", default=[]): [vol.All(str, vol.Length(max=64))],
    }
)
@websocket_api.async_response
async def websocket_fitness_accounts_share_save(hass: HomeAssistant, connection, msg) -> None:
    """Update only view grants for the current Fitness user's own profile."""
    try:
        account_id = await _sharing_owner_account_id(hass, connection)
        controller = get_fitness_account_controller(hass)
        result = await controller.async_set_shared_viewers(
            account_id, [str(item) for item in (msg.get("viewer_account_ids") or [])]
        )
        connection.send_result(msg["id"], result)
    except (PermissionError, ValueError) as err:
        connection.send_error(msg["id"], "unauthorized", str(err))


@websocket_api.websocket_command({vol.Required("type"): "fitness/accounts/admin"})
@websocket_api.async_response
async def websocket_fitness_accounts_admin(hass: HomeAssistant, connection, msg) -> None:
    await _require_fitness_admin(hass, connection)
    controller = get_fitness_account_controller(hass)
    connection.send_result(msg["id"], await controller.async_admin_snapshot())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/accounts/save",
        vol.Optional("account_id"): vol.All(str, vol.Length(max=64)),
        vol.Required("display_name"): vol.All(str, vol.Length(min=1, max=128)),
        vol.Required("role"): vol.In(sorted(ROLES)),
        vol.Required("network_access"): vol.In(sorted(NETWORK_ACCESS_MODES)),
        vol.Optional("profile_entry_id"): vol.Any(None, vol.All(str, vol.Length(max=128))),
        vol.Optional("view_profile_entry_ids", default=[]): [vol.All(str, vol.Length(max=128))],
        vol.Optional("remote_slug"): vol.Any(None, vol.All(str, vol.Length(max=63))),
        vol.Optional("remote_enabled", default=False): bool,
        vol.Optional("username"): vol.Any(None, vol.All(str, vol.Length(max=64))),
        vol.Optional("enabled", default=True): bool,
    }
)
@websocket_api.async_response
async def websocket_fitness_accounts_save(hass: HomeAssistant, connection, msg) -> None:
    await _require_fitness_admin(hass, connection)
    controller = get_fitness_account_controller(hass)
    creating = not bool(str(msg.get("account_id") or "").strip())
    try:
        account = await controller.async_save_account(
            account_id=(str(msg.get("account_id") or "") or None),
            display_name=str(msg.get("display_name") or ""),
            role=str(msg.get("role") or ""),
            network_access=str(msg.get("network_access") or ""),
            profile_entry_id=(str(msg.get("profile_entry_id") or "") or None),
            view_profile_entry_ids=[str(item) for item in (msg.get("view_profile_entry_ids") or [])],
            remote_slug=(str(msg.get("remote_slug") or "") or None),
            remote_enabled=bool(msg.get("remote_enabled", False)),
            username=(str(msg.get("username")) if msg.get("username") is not None else None),
            enabled=bool(msg.get("enabled", True)),
        )
        temporary_password = None
        if creating:
            temporary_password = await controller.async_generate_temporary_password(
                str(account["account_id"])
            )
            account = controller.public_account(
                controller.account(str(account["account_id"])) or {}, include_diagnostics=True
            )
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(
        msg["id"],
        {
            "account": account,
            # This is intentionally the only response that contains the first-
            # time secret. It is never persisted in plaintext and cannot be
            # retrieved later; an administrator can only replace it.
            "temporary_password": temporary_password,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/accounts/delete",
        vol.Required("account_id"): vol.All(str, vol.Length(min=1, max=64)),
    }
)
@websocket_api.async_response
async def websocket_fitness_accounts_delete(hass: HomeAssistant, connection, msg) -> None:
    await _require_fitness_admin(hass, connection)
    controller = get_fitness_account_controller(hass)
    try:
        await controller.async_delete_account(str(msg["account_id"]))
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/accounts/reset_password",
        vol.Required("account_id"): vol.All(str, vol.Length(min=1, max=64)),
    }
)
@websocket_api.async_response
async def websocket_fitness_accounts_reset_password(hass: HomeAssistant, connection, msg) -> None:
    await _require_fitness_admin(hass, connection)
    controller = get_fitness_account_controller(hass)
    try:
        password = await controller.async_generate_temporary_password(str(msg["account_id"]))
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    connection.send_result(
        msg["id"],
        {
            "account_id": str(msg["account_id"]),
            "temporary_password": password,
            "password_change_required": True,
        },
    )


def async_register_fitness_account_websocket_commands(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(ACCOUNT_WS_REGISTERED_KEY):
        return
    for command in (
        websocket_fitness_accounts_share,
        websocket_fitness_accounts_share_save,
        websocket_fitness_accounts_admin,
        websocket_fitness_accounts_save,
        websocket_fitness_accounts_delete,
        websocket_fitness_accounts_reset_password,
    ):
        websocket_api.async_register_command(hass, command)
    data[ACCOUNT_WS_REGISTERED_KEY] = True

def get_fitness_account_controller(hass: HomeAssistant) -> FitnessAccountController:
    data = hass.data.setdefault(DOMAIN, {})
    controller = data.get(ACCOUNT_CONTROLLER_KEY)
    if controller is None:
        controller = FitnessAccountController(hass)
        data[ACCOUNT_CONTROLLER_KEY] = controller
    return controller


def async_register_fitness_account_http_views(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(PORTAL_REGISTERED_KEY):
        return
    for view in (
        FitnessDashCastBootstrapView(),
        FitnessPortalLoginView(), FitnessPortalPasswordView(), FitnessPortalAppView(),
        FitnessPortalSessionView(), FitnessPortalWSView(), FitnessPortalStatesView(),
        FitnessPortalServiceView(), FitnessPortalAccountView(), FitnessPortalLogoutView(),
    ):
        hass.http.register_view(view)
    data[PORTAL_REGISTERED_KEY] = True


def _async_install_portal_middleware(app: web.Application, middleware) -> str:
    """Install a middleware before or after aiohttp freezes the HA application.

    Home Assistant intentionally keeps its URL router mutable after HTTP startup,
    but aiohttp still freezes ``Application.middlewares`` when AppRunner starts.
    Fitness can be loaded after that point, so a normal ``append`` is not always
    possible.  aiohttp 3.x resolves requests from the prepared
    ``_middlewares_handlers`` tuple after freeze; update that prepared tuple and
    invalidate its middleware wrapper cache when the public API is already
    immutable.  All private attributes are capability-checked so a future
    aiohttp change fails closed instead of exposing generic HA routes on a
    Fitness hostname.
    """
    try:
        app.middlewares.append(middleware)
        return "registered_before_freeze"
    except RuntimeError:
        prepared = getattr(app, "_middlewares_handlers", None)
        if prepared is None:
            raise RuntimeError("aiohttp middleware chain is frozen but not prepared")

        old_run_middlewares = getattr(app, "_run_middlewares", None)
        try:
            prepared_tuple = tuple(prepared)
            from aiohttp import web_app as aiohttp_web_app

            cache = getattr(aiohttp_web_app, "_cached_build_middleware", None)
            if cache is None or not callable(getattr(cache, "cache_clear", None)):
                raise RuntimeError("aiohttp middleware cache invalidation is unavailable")

            # ``_prepare_middleware`` stores application middlewares in reverse
            # order. Appending Fitness before freeze therefore corresponds to
            # prepending it to the already-prepared tuple. Home Assistant's own
            # security/forwarded/auth middlewares remain outside this guard.
            app._middlewares_handlers = ((middleware, True), *prepared_tuple)  # type: ignore[attr-defined]  # noqa: SLF001
            app._run_middlewares = True  # type: ignore[attr-defined]  # noqa: SLF001
            cache.cache_clear()
        except Exception:
            # Never leave a partly modified chain behind if aiohttp internals
            # change. The caller marks the hostname router unavailable.
            if getattr(app, "_middlewares_handlers", None) != prepared:
                app._middlewares_handlers = prepared  # type: ignore[attr-defined]  # noqa: SLF001
            app._run_middlewares = old_run_middlewares  # type: ignore[attr-defined]  # noqa: SLF001
            raise
        return "registered_after_freeze"


def async_register_fitness_portal_routing(hass: HomeAssistant) -> None:
    """Install host routing for account-owned Fitness subdomains and base login."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(PORTAL_MIDDLEWARE_KEY) is True:
        return

    @web.middleware
    async def _fitness_portal_router(request: web.Request, handler):
        controller = get_fitness_account_controller(hass)
        await controller.async_load()
        remote_account = controller.account_by_remote_host(request.host)
        from .access_control import get_fitness_access_controller

        access = get_fitness_access_controller(hass)
        base = _host_only(access._cloudflare().get("base_domain"))  # noqa: SLF001
        host = _host_only(request.host)
        in_namespace = bool(base and (host == base or host.endswith(f".{base}")))
        if not in_namespace:
            return await handler(request)
        if host != base and remote_account is None:
            raise web.HTTPNotFound(text="Fitness remote account is disabled")
        # Only the dedicated Fitness portal and its own static assets exist on
        # Fitness hostnames. Generic Home Assistant API/auth/websocket routes are
        # intentionally not exposed through these public names.
        allowed_prefixes = ("/fitness-auth/", "/fitness/frontend/", "/fitness/brand/")
        if request.path.startswith(allowed_prefixes):
            return await handler(request)
        if request.method in {"GET", "HEAD"} and request.path in {"/", "/fitness-tv", "/fitness-tv/", "/fitness-tv/main"}:
            auth = await controller.async_session(request)
            if auth is None:
                raise web.HTTPFound(location="/fitness-auth/login")
            row, _session = auth
            if row.get("password_change_required"):
                raise web.HTTPFound(location="/fitness-auth/password")
            raise web.HTTPFound(location="/fitness-auth/app")
        destination = str(request.headers.get("Sec-Fetch-Dest") or "").lower()
        accepts_html = "text/html" in str(request.headers.get("Accept") or "").lower()
        if request.method in {"GET", "HEAD"} and (destination in {"document", "iframe"} or accepts_html):
            raise web.HTTPFound(location="/fitness-auth/app")
        raise web.HTTPNotFound(text="This hostname serves the restricted HA-Fitness portal only")

    try:
        mode = _async_install_portal_middleware(hass.http.app, _fitness_portal_router)
    except Exception as err:  # noqa: BLE001 - fail closed on unsupported aiohttp internals
        data[PORTAL_MIDDLEWARE_KEY] = False
        _LOGGER.error(
            "Fitness account hostname routing is unavailable; remote Fitness hostnames must not be published: %s",
            err,
        )
        return
    data[PORTAL_MIDDLEWARE_KEY] = True
    _LOGGER.info("Fitness account hostname routing active (%s)", mode)
