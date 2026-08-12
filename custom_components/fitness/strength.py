"""Optional provider-independent detailed strength analysis."""
from __future__ import annotations

import re
from typing import Any


def _num(value):
    try:
        v=float(value)
        return v if v == v and abs(v) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _first(d: dict, names: tuple[str, ...]):
    norm={re.sub(r"[^a-z0-9]", "", str(k).lower()): v for k,v in d.items()}
    for name in names:
        key=re.sub(r"[^a-z0-9]", "", name.lower())
        if key in norm and norm[key] not in (None, ""):
            return norm[key]
    return None


def exercise_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def estimated_1rm_epley(weight_kg: float, reps: float) -> float | None:
    if weight_kg <= 0 or reps < 1 or reps > 12:
        return None
    if reps == 1:
        return weight_kg
    return weight_kg * (1.0 + reps / 30.0)


def _normalize_set(raw: dict[str, Any]) -> dict[str, Any] | None:
    reps=_num(_first(raw, ("reps","repetitions","rep_count","repsCount")))
    weight=_num(_first(raw, ("weight_kg","weightKg","weight","load_kg","loadKg","load")))
    rpe=_num(_first(raw, ("rpe","rating_of_perceived_exertion","perceived_exertion")))
    if reps is None and weight is None:
        return None
    if reps is not None and (reps <= 0 or reps > 100):
        return None
    if weight is not None and (weight < 0 or weight > 1000):
        return None
    out={"reps": int(round(reps)) if reps is not None else None, "weight_kg": round(weight,3) if weight is not None else None}
    if rpe is not None and 1 <= rpe <= 10:
        out["rpe"]=int(round(rpe))
    st=_first(raw,("type","set_type","setType"))
    if st is not None: out["type"]=str(st)
    return {k:v for k,v in out.items() if v is not None}


def _candidate_exercises(value: Any, out: list[dict], depth=0):
    if depth > 7: return
    if isinstance(value, dict):
        name=_first(value,("exercise_name","exerciseName","name","title","exercise"))
        sets=_first(value,("sets","working_sets","workingSets","set_data","setData"))
        if name and isinstance(sets,list):
            normalized=[s for item in sets if isinstance(item,dict) and (s:=_normalize_set(item))]
            if normalized:
                out.append({"name":str(name),"sets":normalized})
        for v in value.values(): _candidate_exercises(v,out,depth+1)
    elif isinstance(value,list):
        for v in value: _candidate_exercises(v,out,depth+1)


def analyze_strength(workout, prior_workouts: list) -> dict[str, Any] | None:
    candidates=[]
    _candidate_exercises(workout.provider_values, candidates)
    _candidate_exercises(workout.extra, candidates)
    unique={}
    for ex in candidates:
        key=exercise_id(ex["name"])
        if key and key not in unique: unique[key]=ex
    if not unique:
        return None
    prior_best={}
    prior_volume={}
    for old in prior_workouts:
        details=(old.extra or {}).get("fitness_strength") if isinstance(old.extra,dict) else None
        if not isinstance(details,dict): continue
        for ex in details.get("exercises",[]):
            key=ex.get("id")
            if not key: continue
            if ex.get("estimated_1rm_kg") is not None: prior_best[key]=ex["estimated_1rm_kg"]
            if ex.get("volume_kg") is not None: prior_volume[key]=ex["volume_kg"]
    exercises=[]; total_sets=0; total_reps=0; total_volume=0.0; best_e1rm=None; progression=[]
    for key,raw in unique.items():
        sets=raw["sets"]; total_sets += len(sets)
        reps_sum=sum(int(s.get("reps",0)) for s in sets); total_reps += reps_sum
        volume=sum(float(s.get("weight_kg",0))*int(s.get("reps",0)) for s in sets); total_volume += volume
        predictions=[]
        for s in sets:
            if s.get("weight_kg") is not None and s.get("reps") is not None:
                pred=estimated_1rm_epley(float(s["weight_kg"]), int(s["reps"]))
                if pred is not None: predictions.append((pred,s))
        best=max(predictions,key=lambda x:x[0]) if predictions else None
        e1=round(best[0],1) if best else None
        ex={"id":key,"name":raw["name"],"sets":sets,"set_count":len(sets),"total_reps":reps_sum,"volume_kg":round(volume,1),"estimated_1rm_kg":e1,"estimated_1rm_formula":"epley" if e1 is not None else None}
        if best: ex["best_set"]={"weight_kg":best[1].get("weight_kg"),"reps":best[1].get("reps")}
        if key in prior_best and e1 is not None and prior_best[key]:
            ex["previous_estimated_1rm_kg"]=prior_best[key]
            ex["e1rm_change_percent"]=round((e1-prior_best[key])/prior_best[key]*100,1)
            progression.append(ex["e1rm_change_percent"])
        if key in prior_volume and prior_volume[key]:
            ex["previous_volume_kg"]=prior_volume[key]
            ex["volume_change_percent"]=round((volume-prior_volume[key])/prior_volume[key]*100,1)
        exercises.append({k:v for k,v in ex.items() if v is not None})
        if e1 is not None: best_e1rm=e1 if best_e1rm is None else max(best_e1rm,e1)
    return {"method":"fitness_detailed_strength_v1","estimated_1rm_formula":"epley","exercises":exercises,"exercise_count":len(exercises),"total_sets":total_sets,"total_reps":total_reps,"volume_kg":round(total_volume,1),"best_estimated_1rm_kg":best_e1rm,"mean_e1rm_change_percent":round(sum(progression)/len(progression),1) if progression else None}
