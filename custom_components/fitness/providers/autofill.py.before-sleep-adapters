"""Strict documented setup autofill for Fitness."""
from __future__ import annotations
from collections import defaultdict
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from ..const import (
    ANTPLUS_DOMAINS, CONF_RESTING_HR, CONF_THRESHOLD_HR,
    CONF_THRESHOLD_PACE, CONF_THRESHOLD_POWER, CONF_VO2MAX, CONF_WEIGHT,
)
from .entities import convert_to_canonical

PROFILE_QUANTITY={
    CONF_WEIGHT:'weight', CONF_RESTING_HR:'heart_rate', CONF_VO2MAX:'vo2max',
    CONF_THRESHOLD_HR:'heart_rate', CONF_THRESHOLD_PACE:'pace',
    CONF_THRESHOLD_POWER:'power',
}
EXACT_PROFILE_KEYS={
    ('garmin_connect',CONF_WEIGHT):{'weight'},
    ('garmin_connect',CONF_RESTING_HR):{'resting_heart_rate'},
    ('garmin_connect',CONF_VO2MAX):{'vo2_max','vo2max'},
    ('garmin_connect',CONF_THRESHOLD_HR):{'lactate_threshold_hr','lactate_threshold_heart_rate'},
    ('garmin_connect',CONF_THRESHOLD_PACE):{'lactate_threshold_speed','lactate_threshold_pace'},
    ('hevy',CONF_WEIGHT):{'body_weight'},
    ('oura',CONF_VO2MAX):{'vo2_max','vo2max'},
}
WORKOUT_DOMAINS={'garmin_connect','ha_strava','strava','polar','hevy','peloton','oura'}

def _domain(hass, config_entry_id):
    if not config_entry_id: return None
    entry=hass.config_entries.async_get_entry(config_entry_id)
    return entry.domain if entry else None

def _norm(value):
    return str(value or '').strip().lower().replace('-','_').replace(' ','_')

def _entry_keys(hass, entry):
    state=hass.states.get(entry.entity_id)
    values={_norm(getattr(entry,'translation_key',None)),_norm(entry.name),
            _norm(entry.original_name),_norm(entry.entity_id.split('.',1)[-1]),
            _norm(state.attributes.get('friendly_name') if state else None)}
    expanded=set(values)
    for value in list(values):
        for prefix in ('garmin_connect_','garmin_','hevy_','oura_','polar_','strava_','peloton_'):
            if value.startswith(prefix): expanded.add(value[len(prefix):])
    return {x for x in expanded if x}

def _unit_compatible(hass, entry, quantity):
    state=hass.states.get(entry.entity_id)
    if state is None or state.state in ('unknown','unavailable',''): return True
    try: value=float(state.state)
    except (TypeError,ValueError): return False
    converted,_=convert_to_canonical(value,state.attributes.get('unit_of_measurement'),quantity)
    return converted is not None

def exact_profile_candidates(hass):
    registry=er.async_get(hass); result=defaultdict(list)
    for entry in registry.entities.values():
        if not entry.entity_id.startswith('sensor.'): continue
        domain=_domain(hass,entry.config_entry_id)
        if not domain: continue
        keys=_entry_keys(hass,entry)
        for (wanted,field),exact in EXACT_PROFILE_KEYS.items():
            if domain==wanted and keys.intersection(exact) and _unit_compatible(hass,entry,PROFILE_QUANTITY[field]):
                result[field].append(entry.entity_id)
        if domain=='garmin_connect' and any(k=='ftp' or k.startswith('ftp_') for k in keys) and _unit_compatible(hass,entry,'power'):
            result[CONF_THRESHOLD_POWER].append(entry.entity_id)
    return {k:sorted(set(v)) for k,v in result.items()}

def exact_profile_defaults(hass):
    return {k:v[0] for k,v in exact_profile_candidates(hass).items() if len(v)==1}

def _device_domains(hass,device):
    ids=set(getattr(device,'config_entries',None) or [])
    one=getattr(device,'config_entry_id',None)
    if one: ids.add(one)
    return {d for d in (_domain(hass,eid) for eid in ids) if d}

def _by_device(registry):
    out=defaultdict(list)
    for entry in registry.entities.values():
        if entry.device_id: out[entry.device_id].append(entry)
    return out

def exact_antplus_live_device_ids(hass):
    devices=dr.async_get(hass); entries=er.async_get(hass); by=_by_device(entries); result=[]
    tokens=('heart_rate','heartrate','power','cadence','speed','distance','altitude','elevation')
    for device in devices.devices.values():
        if not _device_domains(hass,device).intersection(ANTPLUS_DOMAINS): continue
        sensors=[e for e in by.get(device.id,[]) if e.entity_id.startswith('sensor.')]
        if any(any(t in key for t in tokens) for e in sensors for key in _entry_keys(hass,e)):
            result.append(device.id)
    return sorted(set(result))

def _has(keys,*tokens): return any(all(t in key for t in tokens) for key in keys)

def exact_workout_device_ids(hass):
    devices=dr.async_get(hass); entries=er.async_get(hass); by=_by_device(entries); result=[]
    for device in devices.devices.values():
        domains=_device_domains(hass,device).intersection(WORKOUT_DOMAINS)
        if not domains: continue
        keys=set()
        for e in by.get(device.id,[]):
            if e.entity_id.startswith('sensor.'): keys.update(_entry_keys(hass,e))
        match=False
        if 'garmin_connect' in domains:
            match=any('last_activity' in k or 'last_activities' in k for k in keys)
        elif domains.intersection({'ha_strava','strava'}):
            match=any('activity' in k and not any(b in k for b in ('summary','recent','year_to_date','all_time','gear')) for k in keys)
        elif 'polar' in domains: match=any('last_exercise' in k for k in keys)
        elif 'hevy' in domains: match=_has(keys,'last','workout','start')
        elif 'peloton' in domains: match=_has(keys,'start','time') and (_has(keys,'duration') or _has(keys,'distance') or _has(keys,'heart','rate'))
        elif 'oura' in domains: match=_has(keys,'last','workout','type') and (_has(keys,'last','workout','duration') or _has(keys,'last','workout','distance') or _has(keys,'last','workout','calories'))
        if match: result.append(device.id)
    return sorted(set(result))
