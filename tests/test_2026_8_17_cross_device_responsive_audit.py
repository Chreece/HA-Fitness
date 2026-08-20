"""Regression contracts from the laptop, TV and phone layout audit."""

from pathlib import Path


FRONTEND = Path(__file__).parents[1] / "custom_components/fitness/frontend/fitness-dashboard.js"


def _source() -> str:
    return FRONTEND.read_text(encoding="utf-8")


def test_laptop_grid_breakpoints_and_live_measurement_are_preserved() -> None:
    source = _source()

    assert ".tv-grid{--tv-columns:4;--tv-row:4px" in source  # legacy declaration is overridden by v106 masonry
    assert "@media(max-width:1500px){:host(:not([fitness-cast-receiver])) .tv-grid{--tv-columns:3}}" in source
    assert ":host(:not([fitness-cast-receiver])) .tv-grid{--tv-columns:2}" in source
    assert "@media(max-width:760px){:host(:not([fitness-cast-receiver])) .tv-grid{--tv-columns:1}" in source
    assert "this._cardResizeObserver = new ResizeObserver" in source
    assert "this._cardResizeObserver?.observe(card)" in source


def test_keyboard_focus_remains_visible_on_laptop_and_backend_flows() -> None:
    source = _source()

    assert ".tool:focus-visible,.icon-tool:focus-visible,.primary-tool:focus-visible" in source
    assert ".flow-close:focus-visible,.flow-home:focus-visible,.flow-submit:focus-visible,.flow-menu:focus-visible" in source
    assert "outline:2px solid var(--primary-color);outline-offset:2px" in source


def test_tv_receiver_uses_explicit_compact_toolbar_rows() -> None:
    source = _source()

    assert ":host([fitness-cast-receiver]) .tv-grid{--tv-columns:2}" in source
    assert 'grid-template-areas:"brand profile actions" "music music music"' in source
    assert ":host([fitness-cast-receiver]) .tv-brand{grid-area:brand}" in source
    assert ":host([fitness-cast-receiver]) .tv-actions{grid-area:actions}" in source
    assert ":host([fitness-cast-receiver]) .music-controls{grid-area:music" in source
    assert 'grid-template-areas:"brand profile" "actions actions" "music music"' in source
    assert ":host([fitness-cast-receiver]){height:100dvh}" in source


def test_tv_remote_navigation_and_modal_focus_order_are_unchanged() -> None:
    source = _source()

    assert "_castRemoteInnerElements(section = this._castRemoteSection)" in source
    assert "_leaveCastRemoteSection(source = \"back\")" in source
    assert ".fitness-remote-section-selected,.fitness-remote-section-active" in source
    assert "modalRoot" in source


def test_phone_toolbars_and_profile_actions_wrap_without_reordering_dom() -> None:
    source = _source()

    assert ":host(:not([fitness-cast-receiver])) .tv-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(44px,1fr))" in source
    assert ".setup-actions,.profile-actions{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}" in source
    assert ".profile-badges,.profile-actions{grid-column:1/-1}" in source
    assert ".profile-actions>.profile-assign{grid-column:1/-1}" in source


def test_phone_account_grid_does_not_create_implicit_columns() -> None:
    source = _source()

    assert ".access-domain-row,.access-user-row{grid-template-columns:1fr}" in source
    assert ".access-slug-field,.access-view-field,.access-user-actions,.access-url{grid-column:1}" in source


def test_phone_music_adapter_controls_stack_in_both_profile_surfaces() -> None:
    source = _source()
    stacked_actions = ".adapter-actions{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}"

    assert source.count(stacked_actions) >= 2
    assert source.count(".adapter-actions .adapter-account{grid-column:1/-1;max-width:none}") >= 2
    assert source.count(".provider-catalog-row{grid-template-columns:30px minmax(0,1fr)}") >= 2
    assert source.count(".adapter-actions>*{width:100%;min-width:0;max-width:none;min-height:44px}") >= 2
    assert source.count(".provider-catalog-row>.adapter-setup{grid-column:1/-1;width:100%;max-width:none;min-width:0") >= 2


def test_phone_inputs_touch_targets_and_dynamic_modals_are_safe() -> None:
    source = _source()

    assert "--modal-effective-top:min(var(--modal-top,68px),max(6px,calc(100dvh - 180px)))" in source
    assert "safe-area-inset-bottom" in source
    assert ".setup-shell{min-height:100dvh}" in source
    assert 'input:not([type="checkbox"]):not([type="range"]),select{font-size:16px}' in source
    assert ".tool,.icon-tool,.primary-tool,.adapter-setup,.add-profile-row,.access-domain-row input,.access-user-row input,.access-user-row select{min-height:44px}" in source


def test_adaptive_button_text_keeps_readable_floor() -> None:
    source = _source()

    # Inline-size containment removes a button label from intrinsic sizing and
    # made translated actions collapse to narrow, empty-looking pills.
    assert "container-type:inline-size" not in source
    assert "font-size:clamp(11px,.76vw,13px)" in source
    assert "font-size:clamp(11px,1vw,13px)" in source
    assert "word-break:normal;overflow-wrap:normal" in source


def test_translated_provider_actions_keep_intrinsic_width_and_separate_copy() -> None:
    source = _source()

    assert source.count(".setting-adapters-head>span>strong,.setting-adapters-head>span>small{display:block}") >= 2
    assert source.count(".adapter-actions>*{flex:0 1 auto;min-width:104px;max-width:190px}") >= 2
    assert source.count(".provider-catalog-row>.adapter-setup{min-width:clamp(132px,16vw,190px)") >= 2
    assert ".adapter-actions>.adapter-account{flex:1 1 140px;min-width:120px}" in source


def test_backend_flow_header_keeps_main_menu_label_and_fixed_close_button() -> None:
    source = _source()

    assert ".flow-home{min-width:126px;max-width:min(240px,45vw)" in source
    assert ".flow-close{width:40px;min-width:40px;flex:0 0 40px}" in source
    assert ".flow-home span{display:block}" in source
    assert ".flow-home span{display:none}" not in source
