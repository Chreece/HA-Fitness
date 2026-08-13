from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
FIT=ROOT/"custom_components/fitness"

def test_english_translation_is_exact_strings_json_copy():
    s=json.loads((FIT/"strings.json").read_text(encoding="utf-8")); e=json.loads((FIT/"translations/en.json").read_text(encoding="utf-8")); assert s==e

def test_recovery_v2_attribute_schema_is_identical_in_all_languages():
    e=json.loads((FIT/"translations/en.json").read_text(encoding="utf-8")); expected=set(e["entity"]["sensor"]["estimated_recovery_time"]["state_attributes"]); assert "ready_for_next_workout_at" in expected; assert "workout_demand_components_hours" in expected; assert "base_candidates_hours" not in expected
    for path in (FIT/"translations").glob("*.json"):
        d=json.loads(path.read_text(encoding="utf-8")); actual=set(d["entity"]["sensor"]["estimated_recovery_time"]["state_attributes"]); assert actual==expected, path.name

def test_recovery_v2_levels_are_localized():
    s=(FIT/"sensor.py").read_text(encoding="utf-8"); assert '"ready":"Ready for next workout"' in s; assert '"nearly_ready":"Nearly ready"' in s; assert '"ready":"Έτοιμος για την επόμενη προπόνηση"' in s

def test_recovery_v2_keeps_old_total_attribute_as_alias():
    m=(FIT/"manager.py").read_text(encoding="utf-8"); x=m[m.index("def recovery_time_evaluation"):m.index("def readiness_evaluation",m.index("def recovery_time_evaluation"))]; assert '"estimated_total_recovery_hours": round(central_hours, 1)' in x; assert '"estimated_recovery_hours": round(central_hours, 1)' in x
