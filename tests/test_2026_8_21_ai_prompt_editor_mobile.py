from pathlib import Path

JS = Path("custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_ai_prompt_editor_keeps_typing_inside_card_and_autogrows():
    assert "function _fitnessWireAiPromptEditor(host, editor)" in JS
    assert 'host._aiTextEditing=true' in JS
    assert 'if(this._aiTextEditing)return;' in JS
    assert 'editor.style.height=`${Math.max(40,editor.scrollHeight||40)}px`' in JS
    assert '["pointerdown","pointerup","click","dblclick","touchstart","touchend","keydown","keyup","keypress"]' in JS
    assert 'textarea rows="1" maxlength="2000"' in JS
    assert 'overflow:hidden;resize:none;white-space:pre-wrap;overflow-wrap:anywhere' in JS


def test_today_ai_controls_render_before_plan_content_and_are_compact():
    prompt = '</button>${promptBox}${actions}${chips?'
    assert prompt in JS
    assert '.ai-actions{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px}' in JS
    assert 'min-height:32px' in JS


def test_both_ai_cards_use_shared_prompt_editor():
    assert JS.count("_fitnessWireAiPromptEditor(this,this.shadowRoot.querySelector") >= 2
