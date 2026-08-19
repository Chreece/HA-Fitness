from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import runpy


ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "custom_components" / "fitness"
TRANSLATIONS = FITNESS / "translations"
FRONTEND_PATH = FITNESS / "frontend" / "fitness-dashboard.js"
LANGUAGES = (
    "en", "el", "de", "fr", "es", "it", "pt", "nl",
    "pl", "ru", "uk", "tr", "zh", "ja", "ko",
)
PLACEHOLDER = re.compile(r"\{[^}]+\}")


def _leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, (*path, key))
    else:
        yield path, value


def _get(value, path):
    for part in path:
        value = value[part]
    return value


def _native_documents():
    return {
        language: json.loads(
            (TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")
        )
        for language in LANGUAGES
    }


def _dashboard_catalogs():
    """Evaluate only the dependency-free literal dashboard language groups."""

    tree = ast.parse((FITNESS / "dashboard.py").read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        else:
            continue
        if not isinstance(target, ast.Name):
            continue
        try:
            values[target.id] = ast.literal_eval(node.value)
        except (TypeError, ValueError):
            continue

    # The three original music dictionaries receive literal additions before
    # the audited overlay is merged. Reproduce those additions in source order.
    for node in tree.body:
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "update"
        ):
            continue
        target = node.value.func.value
        if not (
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and node.value.args
        ):
            continue
        try:
            language = ast.literal_eval(target.slice)
            addition = ast.literal_eval(node.value.args[0])
        except (TypeError, ValueError):
            continue
        values[target.value.id][language].update(addition)

    catalogs = {
        language: dict(labels)
        for language, labels in values["_DASHBOARD_TEXT"].items()
    }
    for extra in (
        "_RPE_DASHBOARD_TEXT",
        "_RECOVERY_REFINEMENT_TEXT",
        "_SESSION_STATUS_TEXT",
    ):
        for language in LANGUAGES:
            catalogs[language].update(values[extra][language])

    for group in (
        "_DASHBOARD_UI_TEXT",
        "_TV_DASHBOARD_TEXT",
        "_TV_DASHBOARD_SETTINGS_TEXT",
        "_TV_DASHBOARD_EXTRA_TEXT",
        "_TV_DASHBOARD_MUSIC_TEXT",
        "_TV_DASHBOARD_INTERACTION_TEXT",
        "_TV_DASHBOARD_FLOW_TEXT",
        "_TV_DASHBOARD_REMOTE_TEXT",
        "_TV_DASHBOARD_ACCESS_TEXT",
        "_TV_DASHBOARD_MULTI_TEXT",
        "_TV_DASHBOARD_LAYOUT_TEXT",
    ):
        for language in LANGUAGES:
            catalogs[language].update(values[group].get(language, {}))

    audited = runpy.run_path(
        str(FITNESS / "dashboard_translations.py")
    )["DASHBOARD_LANGUAGE_AUDIT_TEXT"]
    for language in LANGUAGES:
        catalogs[language].update(audited[language])
    return catalogs, values["_PACE_TEXT"]


def test_native_catalogs_have_exact_shape_nonempty_values_and_placeholder_parity():
    assert tuple(sorted(path.stem for path in TRANSLATIONS.glob("*.json"))) == tuple(
        sorted(LANGUAGES)
    )
    documents = _native_documents()
    canonical = json.loads((FITNESS / "strings.json").read_text(encoding="utf-8"))
    assert documents["en"] == canonical

    canonical_leaves = dict(_leaves(canonical))
    for language, document in documents.items():
        leaves = dict(_leaves(document))
        assert set(leaves) == set(canonical_leaves), language
        for path, value in leaves.items():
            if isinstance(canonical_leaves[path], str):
                assert isinstance(value, str) and value.strip(), (language, path)
                assert set(PLACEHOLDER.findall(value)) == set(
                    PLACEHOLDER.findall(canonical_leaves[path])
                ), (language, path)


def test_reviewed_flow_service_and_entity_audit_is_applied_to_every_language():
    audit = runpy.run_path(str(ROOT / "tools" / "apply_language_audit.py"))
    entities = runpy.run_path(
        str(ROOT / "tools" / "language_audit_entity_names.py")
    )
    documents = _native_documents()

    assert tuple(audit["LANGUAGES"]) == LANGUAGES
    assert tuple(entities["LANGUAGES"]) == LANGUAGES
    for language, document in documents.items():
        for concept, paths in audit["PATHS"].items():
            for path in paths:
                expected = (
                    entities["ENTITY_NAMES"][path][language]
                    if path in entities["ENTITY_NAMES"]
                    else audit["TEXT"][concept][language]
                )
                assert _get(document, path) == expected
        for path, translations in entities["ENTITY_NAMES"].items():
            assert _get(document, path) == translations[language]

        service = document["services"]["delete_workouts_before"]
        assert service["name"] and service["description"]
        assert set(service["fields"]) == {"config_entry_id", "days"}
        for field in service["fields"].values():
            assert field["name"] and field["description"]


def test_non_english_native_catalogs_do_not_retain_unreviewed_exact_english_copy():
    documents = _native_documents()
    english = dict(_leaves(documents["en"]))
    # Brand names, scientific notation, identical cognates and month names are
    # intentionally unchanged; ordinary UI prose is not.
    allowed_identical = {
        "Fitness", "VO₂max", "Name", "April", "August", "September",
        "November", "December", "Sport", "Formula",
    }
    for language in LANGUAGES[1:]:
        for path, value in _leaves(documents[language]):
            if isinstance(value, str) and value == english[path]:
                assert value in allowed_identical, (language, path, value)


def test_dashboard_runtime_labels_cover_every_language_key_and_placeholder():
    catalogs, pace = _dashboard_catalogs()
    assert tuple(catalogs) == LANGUAGES
    assert set(pace) == set(LANGUAGES)
    english_keys = set(catalogs["en"])
    assert len(english_keys) >= 479

    for language, labels in catalogs.items():
        assert set(labels) == english_keys, language
        assert pace[language].strip()
        for key, value in labels.items():
            assert isinstance(value, str) and value.strip(), (language, key)
            assert set(PLACEHOLDER.findall(value)) == set(
                PLACEHOLDER.findall(catalogs["en"][key])
            ), (language, key)

    frontend = FRONTEND_PATH.read_text(encoding="utf-8")
    references = set(re.findall(r"\b(?:l|labels)\.([A-Za-z0-9_]+)", frontend))
    assert references <= english_keys | {"pace"}


def test_dashboard_uses_profile_language_and_has_no_direct_ui_text_leaks():
    frontend = FRONTEND_PATH.read_text(encoding="utf-8")
    dashboard = (FITNESS / "dashboard.py").read_text(encoding="utf-8")

    assert '"labels": {**_DASHBOARD_TEXT[lang], "pace": _PACE_TEXT[lang]}' in dashboard
    assert '"labels_by_language"' in dashboard
    assert "profile?.language || this._access?.language || this._hass?.language" in frontend
    assert "FITNESS_ACCESS_COPY" not in frontend
    assert "provider.legal_disclaimer" not in frontend

    forbidden = (
        "notification channel(s)",
        "${items.length} selected",
        ">0 selected<",
        'aria-label="Select"',
        ">No settings are available.<",
        ">Continue setup<",
        "Unsupported flow step type",
        "Selected results",
        "No configured Fitness",
        "evidence signal(s)",
    )
    for literal in forbidden:
        assert literal not in frontend

    # A missing catalog value must never silently turn an otherwise localized
    # screen back into English. Product/technical constants may remain, but UI
    # labels are consumed directly from the complete runtime catalog.
    static_fallbacks = (
        r"\b(?:l|labels)\??\.[A-Za-z0-9_]+\s*\|\|\s*[\"']",
        r"(?:this\._uiLabels|this\._labels\([^)]*\)|"
        r"(?:this\._profile|profile)\?\.labels)\??\.[A-Za-z0-9_]+"
        r"\s*\|\|\s*[\"']",
    )
    for pattern in static_fallbacks:
        assert re.search(pattern, frontend) is None

    # Technical exception detail belongs in the console, never in a translated
    # status region shown to the user.
    for raw_error_display in (
        "this._status = String(err",
        "this._error = String(err",
        "setStatus(String(err",
        "textContent = String(err",
    ):
        assert raw_error_display not in frontend


def test_custom_card_picker_names_and_descriptions_cover_all_languages():
    frontend = FRONTEND_PATH.read_text(encoding="utf-8")
    names = frontend[
        frontend.index("const PICKER_CARD_NAMES = {"):
        frontend.index("const PICKER_LANG", frontend.index("const PICKER_CARD_NAMES = {"))
    ]
    descriptions = frontend[
        frontend.index("const PICKER_DESCRIPTIONS = {"):
        frontend.index("const PICKER_ENGLISH_LIVE_CARD")
    ]
    for language in LANGUAGES:
        assert re.search(rf"\b{language}:\s*\{{", names)
        assert re.search(rf"\b{language}:\s*", descriptions)


def test_scientific_formula_prose_is_complete_for_every_supported_language():
    scientific = runpy.run_path(str(FITNESS / "scientific_translations.py"))
    assert tuple(scientific["SCIENTIFIC_LANGUAGES"]) == LANGUAGES

    evaluation = scientific["EVALUATION_FORMULAS"]
    live = scientific["LIVE_FORMULAS"]
    assert len(evaluation["en"]) == 10
    assert len(live["en"]) == 22
    for catalog in (evaluation, live):
        keys = set(catalog["en"])
        for language in LANGUAGES:
            assert set(catalog[language]) == keys
            assert all(value.strip() for value in catalog[language].values())

    tree = ast.parse((FITNESS / "live_details.py").read_text(encoding="utf-8"))
    live_metrics = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "CALCULATED_LIVE_METRICS"
    )
    assert set(live["en"]) == live_metrics
    assert "EVALUATION_FORMULAS[code].get(metric)" in (
        FITNESS / "evaluation_details.py"
    ).read_text(encoding="utf-8")
    assert "LIVE_FORMULAS[code].get(metric)" in (
        FITNESS / "live_details.py"
    ).read_text(encoding="utf-8")


def test_music_provider_copy_is_routed_through_translation_keys():
    base = (FITNESS / "music" / "base.py").read_text(encoding="utf-8")
    catalog = (FITNESS / "music" / "provider_catalog.py").read_text(encoding="utf-8")
    frontend = FRONTEND_PATH.read_text(encoding="utf-8")

    assert "setup_hint_key" in base
    assert '"description_key"' in catalog
    assert '"provider_name"' in catalog
    assert "_fitnessMusicProviderDescription" in frontend
    assert "_fitnessMusicAdapterHint" in frontend
