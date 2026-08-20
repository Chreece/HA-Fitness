from __future__ import annotations

import ast
import html
import json
import secrets
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")


class _Response:
    def __init__(self, *, text: str, content_type: str, charset: str, headers: dict[str, str]):
        self.text = text
        self.content_type = content_type
        self.charset = charset
        self.headers = headers


class _Web:
    Response = _Response


def _renderer():
    tree = ast.parse(SOURCE)
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "_portal_app_page"
    )
    segment = ast.get_source_segment(SOURCE, node)
    assert segment
    namespace = {
        "Any": object,
        "FitnessSession": object,
        "ROLE_ADMIN": "admin",
        "_PORTAL_APP_TEXT": {
            "en": {
                "profile": "Fitness profile", "administration": "Fitness administration",
                "view_only": "view only", "account": "Account", "sign_out": "Sign out",
                "account_settings": "Account settings", "login_name": "Login name",
                "current_password": "Current password", "new_password": "New password",
                "cancel": "Cancel", "save": "Save", "saving": "Saving…", "saved": "Saved",
                "unable_save": "Unable to save",
            },
            "el": {
                "profile": "Προφίλ Fitness", "administration": "Διαχείριση Fitness",
                "view_only": "μόνο προβολή", "account": "Λογαριασμός", "sign_out": "Αποσύνδεση",
                "account_settings": "Ρυθμίσεις λογαριασμού", "login_name": "Όνομα σύνδεσης",
                "current_password": "Τρέχων κωδικός", "new_password": "Νέος κωδικός",
                "cancel": "Ακύρωση", "save": "Αποθήκευση", "saving": "Αποθήκευση…",
                "saved": "Αποθηκεύτηκε", "unable_save": "Αδυναμία αποθήκευσης",
            },
        },
        "_portal_language": lambda value: str(value or "en").split("-")[0] if str(value or "en").split("-")[0] in {"en", "el"} else "en",
        "_security_headers": lambda nonce="": {"Content-Security-Policy": f"nonce-{nonce}"},
        "html": html,
        "json": json,
        "secrets": secrets,
        "web": _Web,
    }
    exec("from __future__ import annotations\n" + segment, namespace)
    return namespace["_portal_app_page"]


def test_remote_portal_renderer_executes_and_localizes_chrome():
    render = _renderer()
    row = {
        "account_id": "acct-1",
        "role": "remote",
        "username": "j2",
        "display_name": "J2",
        "profile_entry_id": "profile-1",
        "view_profile_entry_ids": [],
    }
    session = SimpleNamespace(csrf="csrf", language="el")
    response = render(row, session, [{"entry_id": "profile-1", "name": "J2", "mode": "view"}])
    assert response.content_type == "text/html"
    assert '<html lang="el">' in response.text
    assert '>Λογαριασμός<' not in response.text
    assert '>Αποσύνδεση<' in response.text
    assert 'aria-label="Προφίλ Fitness"' in response.text
    assert '"language":"el"' in response.text


def test_remote_portal_renderer_normalizes_unknown_language_to_english():
    render = _renderer()
    row = {
        "account_id": "acct-1",
        "role": "remote",
        "username": "j2",
        "display_name": "J2",
        "profile_entry_id": "profile-1",
        "view_profile_entry_ids": [],
    }
    session = SimpleNamespace(csrf="csrf", language="xx")
    response = render(row, session, [])
    assert '<html lang="en">' in response.text
    assert '>Account<' not in response.text
    assert '>Sign out<' in response.text
    assert 'aria-label="Fitness profile"' in response.text
