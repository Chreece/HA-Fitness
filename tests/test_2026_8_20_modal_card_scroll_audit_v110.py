from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_all_dashboard_cards_keep_natural_height_instead_of_clipping_content():
    assert 'card.toggleAttribute("fitness-natural-height", true);' in FRONTEND
    assert 'const requestedInnerHeight = Math.max(intrinsicInnerScrollHeight' in FRONTEND
    assert ':host([fitness-natural-height]) > ha-card{' in FRONTEND
    assert 'height:auto!important;max-height:none!important' in FRONTEND


def test_every_regular_modal_is_normalized_to_one_shared_scroll_region():
    assert 'function _fitnessNormalizeModalScroll(modalCard, {disabled=false}={})' in FRONTEND
    assert 'region.className = "fitness-modal-scroll-region";' in FRONTEND
    # Dashboard and setup/overview surfaces must both use the same contract.
    assert FRONTEND.count('_fitnessNormalizeModalScroll(modalCard, {disabled:backendFlowModal || cardPickerPreview})') >= 2
    assert FRONTEND.count('_fitnessWireModalScroll(modalCard, scrollBody);') >= 2


def test_shared_modal_region_is_shrinkable_scrollable_and_keeps_children_natural_height():
    assert '.fitness-modal-scroll-region{' in FRONTEND
    assert 'flex:1 1 auto!important' in FRONTEND
    assert 'min-height:0!important' in FRONTEND
    assert 'overflow-y:auto!important' in FRONTEND
    assert 'scrollbar-gutter:stable!important' in FRONTEND
    assert '.fitness-modal-scroll-region>.music-source-list' in FRONTEND
    assert 'height:auto!important' in FRONTEND
    assert 'max-height:none!important' in FRONTEND
    assert 'overflow:visible!important' in FRONTEND


def test_modal_wheel_scrolls_the_shared_body_even_when_pointer_is_over_a_row():
    assert 'const canScroll = scrollRegion.scrollHeight > scrollRegion.clientHeight + 1;' in FRONTEND
    assert 'scrollRegion.scrollTop = before + delta;' in FRONTEND
    assert 'event.preventDefault();' in FRONTEND
    assert 'event.stopPropagation();' in FRONTEND


def test_modal_inventory_and_card_catalog_stay_covered_by_shared_contract():
    # This is intentionally broad: if new menus/cards are added, the generic
    # normalizer should continue to cover them without a per-modal CSS patch.
    modal_count = len(re.findall(r'<div class="modal-card[^\"]*">', FRONTEND))
    card_catalog = re.search(r'const FITNESS_TV_CARD_CATALOG = Object\.freeze\(\[(.*?)\]\);', FRONTEND, re.S)
    assert modal_count >= 28
    assert card_catalog is not None
    assert len(re.findall(r'\{id:"[^"]+"', card_catalog.group(1))) >= 26
