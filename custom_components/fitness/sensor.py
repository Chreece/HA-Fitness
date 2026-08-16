"""Fitness sensor platform."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import PERCENTAGE, UnitOfPower

from .const import (
    DOMAIN,
    METRIC_ALTITUDE,
    METRIC_CADENCE,
    METRIC_DISTANCE,
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_SPEED,
    METHOD_FRIEND_2017,
    METHOD_PERSONAL_HRV_BASELINE,
    METHOD_ACSM_HRR_INTENSITY,
    METHOD_THRESHOLD_RELATIVE,
)
from .entity import device_info
from .engine.live import (
    acsm_hrr_intensity,
    pace_from_speed_kmh,
    percent_hrr,
    percent_max_hr,
    relative_percent,
    speed_from_pace_min_km,
)
from .providers.entities import resolve_number_or_entity
from .explanations import sensor_explanation  # Deterministic; never AI-generated.
from .evaluation_details import evaluation_user_details
from .live_details import CALCULATED_LIVE_METRICS, live_user_details
from .providers.evaluation import collect_provider_metrics
from .providers.workouts import fitness_owned_workout_value
from .profile_data import (
    DATA_MAP_KEYS,
    DATA_MAP_SCHEMA_VERSION,
    build_profile_routes,
    routes_to_attributes,
)

_LOGGER = logging.getLogger(__name__)



def _localized_readiness_attributes(language: str | None, readiness: dict) -> dict:
    """Return stable readiness attributes with a localized display level.

    Machine-readable keys/values remain stable for automations. Only the
    additional ``level_display`` value is localized for the entity details UI.
    """
    code = str(language or "en").lower().split("-")[0].split("_")[0]
    levels = {
        "en": {"excellent":"Excellent","high":"High","moderate":"Moderate","low":"Low","very_low":"Very low","insufficient_data":"Insufficient data"},
        "el": {"excellent":"Εξαιρετική","high":"Υψηλή","moderate":"Μέτρια","low":"Χαμηλή","very_low":"Πολύ χαμηλή","insufficient_data":"Ανεπαρκή δεδομένα"},
        "de": {"excellent":"Ausgezeichnet","high":"Hoch","moderate":"Mittel","low":"Niedrig","very_low":"Sehr niedrig","insufficient_data":"Unzureichende Daten"},
        "fr": {"excellent":"Excellente","high":"Élevée","moderate":"Modérée","low":"Faible","very_low":"Très faible","insufficient_data":"Données insuffisantes"},
        "es": {"excellent":"Excelente","high":"Alta","moderate":"Moderada","low":"Baja","very_low":"Muy baja","insufficient_data":"Datos insuficientes"},
        "it": {"excellent":"Eccellente","high":"Alta","moderate":"Moderata","low":"Bassa","very_low":"Molto bassa","insufficient_data":"Dati insufficienti"},
        "pt": {"excellent":"Excelente","high":"Alta","moderate":"Moderada","low":"Baixa","very_low":"Muito baixa","insufficient_data":"Dados insuficientes"},
        "nl": {"excellent":"Uitstekend","high":"Hoog","moderate":"Gemiddeld","low":"Laag","very_low":"Zeer laag","insufficient_data":"Onvoldoende gegevens"},
        "pl": {"excellent":"Doskonała","high":"Wysoka","moderate":"Umiarkowana","low":"Niska","very_low":"Bardzo niska","insufficient_data":"Niewystarczające dane"},
        "ru": {"excellent":"Отличная","high":"Высокая","moderate":"Умеренная","low":"Низкая","very_low":"Очень низкая","insufficient_data":"Недостаточно данных"},
        "uk": {"excellent":"Відмінна","high":"Висока","moderate":"Помірна","low":"Низька","very_low":"Дуже низька","insufficient_data":"Недостатньо даних"},
        "tr": {"excellent":"Mükemmel","high":"Yüksek","moderate":"Orta","low":"Düşük","very_low":"Çok düşük","insufficient_data":"Yetersiz veri"},
        "zh": {"excellent":"极佳","high":"高","moderate":"中等","low":"低","very_low":"很低","insufficient_data":"数据不足"},
        "ja": {"excellent":"非常に高い","high":"高い","moderate":"中程度","low":"低い","very_low":"非常に低い","insufficient_data":"データ不足"},
        "ko": {"excellent":"매우 좋음","high":"높음","moderate":"보통","low":"낮음","very_low":"매우 낮음","insufficient_data":"데이터 부족"},
    }
    level = str(readiness.get("level") or "insufficient_data")
    display = levels.get(code, levels["en"]).get(level, level)
    attrs = {
        "level": level,
        "level_display": display,
        "confidence_percent": readiness.get("confidence_percent"),
        "components_available": readiness.get("components_available") or readiness.get("available_components") or [],
        "components": readiness.get("components") or {},
        "reason": readiness.get("reason"),
        "data_source": readiness.get("data_source"),
        "updated_at": readiness.get("updated_at"),
    }
    return {key: value for key, value in attrs.items() if value is not None}



def _localized_recovery_time_level(language: str | None, level: str) -> str:
    code = str(language or "en").lower().split("-")[0].split("_")[0]
    labels = {
        "en":{"recovered_estimate":"Recovered estimate","ready":"Ready for next workout","nearly_recovered":"Nearly recovered","nearly_ready":"Nearly ready","recovering":"Recovering","substantial_recovery":"Substantial recovery needed","high_recovery_demand":"High recovery demand"},
        "el":{"recovered_estimate":"Εκτιμώμενη αποκατάσταση","ready":"Έτοιμος για την επόμενη προπόνηση","nearly_recovered":"Σχεδόν αποκαταστάθηκε","nearly_ready":"Σχεδόν έτοιμος","recovering":"Σε αποκατάσταση","substantial_recovery":"Χρειάζεται σημαντική αποκατάσταση","high_recovery_demand":"Υψηλή ανάγκη αποκατάστασης"},
        "de":{"recovered_estimate":"Voraussichtlich erholt","ready":"Bereit fürs nächste Training","nearly_recovered":"Fast erholt","nearly_ready":"Fast bereit","recovering":"In Erholung","substantial_recovery":"Deutliche Erholung nötig","high_recovery_demand":"Hoher Erholungsbedarf"},
        "fr":{"recovered_estimate":"Récupération estimée","ready":"Prêt pour le prochain entraînement","nearly_recovered":"Presque récupéré","nearly_ready":"Presque prêt","recovering":"En récupération","substantial_recovery":"Récupération importante nécessaire","high_recovery_demand":"Besoin élevé de récupération"},
        "es":{"recovered_estimate":"Recuperación estimada","ready":"Listo para el próximo entrenamiento","nearly_recovered":"Casi recuperado","nearly_ready":"Casi listo","recovering":"Recuperándose","substantial_recovery":"Se necesita recuperación importante","high_recovery_demand":"Alta necesidad de recuperación"},
        "it":{"recovered_estimate":"Recupero stimato","ready":"Pronto per il prossimo allenamento","nearly_recovered":"Quasi recuperato","nearly_ready":"Quasi pronto","recovering":"In recupero","substantial_recovery":"Serve recupero significativo","high_recovery_demand":"Elevata necessità di recupero"},
        "pt":{"recovered_estimate":"Recuperação estimada","ready":"Pronto para o próximo treino","nearly_recovered":"Quase recuperado","nearly_ready":"Quase pronto","recovering":"Em recuperação","substantial_recovery":"É necessária recuperação significativa","high_recovery_demand":"Elevada necessidade de recuperação"},
        "nl":{"recovered_estimate":"Geschat hersteld","ready":"Klaar voor de volgende training","nearly_recovered":"Bijna hersteld","nearly_ready":"Bijna klaar","recovering":"Herstellend","substantial_recovery":"Aanzienlijk herstel nodig","high_recovery_demand":"Hoge herstelbehoefte"},
        "pl":{"recovered_estimate":"Szacunkowo zregenerowany","ready":"Gotowy na kolejny trening","nearly_recovered":"Prawie zregenerowany","nearly_ready":"Prawie gotowy","recovering":"Regeneracja trwa","substantial_recovery":"Potrzebna znaczna regeneracja","high_recovery_demand":"Wysokie zapotrzebowanie na regenerację"},
        "ru":{"recovered_estimate":"Расчётное восстановление","ready":"Готов к следующей тренировке","nearly_recovered":"Почти восстановлен","nearly_ready":"Почти готов","recovering":"Восстановление","substantial_recovery":"Требуется значительное восстановление","high_recovery_demand":"Высокая потребность в восстановлении"},
        "uk":{"recovered_estimate":"Орієнтовно відновлено","ready":"Готовий до наступного тренування","nearly_recovered":"Майже відновлено","nearly_ready":"Майже готовий","recovering":"Відновлення","substantial_recovery":"Потрібне значне відновлення","high_recovery_demand":"Висока потреба у відновленні"},
        "tr":{"recovered_estimate":"Tahmini olarak toparlandı","ready":"Bir sonraki antrenmana hazır","nearly_recovered":"Neredeyse toparlandı","nearly_ready":"Neredeyse hazır","recovering":"Toparlanıyor","substantial_recovery":"Önemli toparlanma gerekli","high_recovery_demand":"Yüksek toparlanma ihtiyacı"},
        "zh":{"recovered_estimate":"预计已恢复","ready":"已准备好下一次训练","nearly_recovered":"接近恢复","nearly_ready":"接近准备完成","recovering":"恢复中","substantial_recovery":"仍需较多恢复","high_recovery_demand":"恢复需求高"},
        "ja":{"recovered_estimate":"推定回復済み","ready":"次のトレーニングに備う","nearly_recovered":"ほぼ回復","nearly_ready":"ほぼ準備完了","recovering":"回復中","substantial_recovery":"十分な回復が必要","high_recovery_demand":"高い回復需要"},
        "ko":{"recovered_estimate":"회복 추정 완료","ready":"다음 운동 준비 완료","nearly_recovered":"거의 회복됨","nearly_ready":"거의 준비됨","recovering":"회복 중","substantial_recovery":"상당한 회복 필요","high_recovery_demand":"높은 회복 필요"},
    }
    return labels.get(code, labels["en"]).get(level, level)

def _training_adaptation_evaluation(manager) -> dict:
    """Classify recent training adaptation from Fitness-owned longitudinal evidence.

    This is a monitoring classification, not a diagnosis. It intentionally combines
    load exposure with fitness and recovery trends because load alone cannot
    distinguish productive adaptation from maladaptation.
    """
    e = manager.evaluation()
    workout = e.get("workout_long_term") or {}
    recorder = e.get("recorder_long_term") or {}
    sleep = e.get("sleep_long_term") or {}
    readiness = manager.readiness_evaluation()
    workouts_28d = int(workout.get("workouts_28d") or 0)
    active_days_28d = int(workout.get("active_training_days_28d") or 0)
    acute = workout.get("banister_trimp_7d")
    chronic = workout.get("banister_trimp_28d_weekly_equivalent")
    ratio = (float(acute) / float(chronic)) if acute is not None and chronic not in (None, 0) else None
    vo2_slope = recorder.get("vo2max_slope_percent_per_30d")
    hrv_delta = sleep.get("sleep_hrv_7d_vs_baseline_percent")
    rhr_delta = recorder.get("resting_hr_vs_28d")
    ready = readiness.get("score")

    evidence_count = sum(x is not None for x in (ratio, vo2_slope, hrv_delta, rhr_delta, ready))
    # A recent/chronic ratio is unstable when the 28-day baseline contains only
    # a handful of sessions. Do not label a user "high load" merely because one
    # normal workout is divided by a tiny immature baseline.
    baseline_reliable = (
        workouts_28d >= 6
        and active_days_28d >= 4
        and chronic is not None
        and float(chronic) >= 15.0
    )
    if workouts_28d == 0:
        status = "absent"
    elif not baseline_reliable or evidence_count < 2:
        status = "insufficient_data"
    else:
        recovery_strain = ((hrv_delta is not None and float(hrv_delta) <= -10.0) or
                           (rhr_delta is not None and float(rhr_delta) >= 5.0) or
                           (ready is not None and float(ready) < 35.0))
        if ratio is not None and ratio >= 1.5:
            status = "excessive" if recovery_strain else "high_load"
        elif recovery_strain and ratio is not None and ratio >= 1.0:
            status = "strained"
        elif ratio is not None and ratio < 0.65:
            status = "insufficient_stimulus"
        elif vo2_slope is not None and float(vo2_slope) >= 0.5 and (ratio is None or 0.75 <= ratio <= 1.5) and not recovery_strain:
            status = "productive"
        elif vo2_slope is not None and float(vo2_slope) <= -1.0 and ratio is not None and ratio >= 0.8:
            status = "unproductive"
        else:
            status = "maintaining"
    return {
        "status": status, "workouts_28d": workouts_28d, "active_days_28d": active_days_28d,
        "trimp_7d": acute, "trimp_28d_weekly_equivalent": chronic,
        "recent_to_baseline_load_ratio": round(ratio, 3) if ratio is not None else None,
        "vo2max_slope_percent_per_30d": vo2_slope, "hrv_7d_vs_baseline_percent": hrv_delta,
        "resting_hr_vs_28d_bpm": rhr_delta, "readiness_score": ready,
        "evidence_count": evidence_count, "baseline_reliable": baseline_reliable,
        "minimum_workouts_28d_for_baseline": 6, "minimum_active_days_28d_for_baseline": 4,
    }


def _localized_training_adaptation_status(language: str | None, status: str) -> str:
    code = str(language or "en").lower().split("-")[0].split("_")[0]
    labels = {
      "en":{"productive":"Productive","maintaining":"Maintaining","insufficient_stimulus":"Insufficient stimulus","absent":"No recent training","high_load":"High load","excessive":"Excessive load","strained":"Strained","unproductive":"Unproductive","insufficient_data":"Insufficient data"},
      "el":{"productive":"Παραγωγική","maintaining":"Διατήρηση","insufficient_stimulus":"Ανεπαρκές ερέθισμα","absent":"Χωρίς πρόσφατη προπόνηση","high_load":"Υψηλό φορτίο","excessive":"Υπερβολικό φορτίο","strained":"Καταπόνηση","unproductive":"Μη παραγωγική","insufficient_data":"Ανεπαρκή δεδομένα"},
      "de":{"productive":"Produktiv","maintaining":"Erhaltend","insufficient_stimulus":"Unzureichender Reiz","absent":"Kein aktuelles Training","high_load":"Hohe Belastung","excessive":"Übermäßige Belastung","strained":"Beansprucht","unproductive":"Unproduktiv","insufficient_data":"Unzureichende Daten"},
      "fr":{"productive":"Productif","maintaining":"Maintien","insufficient_stimulus":"Stimulus insuffisant","absent":"Aucun entraînement récent","high_load":"Charge élevée","excessive":"Charge excessive","strained":"Sous tension","unproductive":"Non productif","insufficient_data":"Données insuffisantes"},
      "es":{"productive":"Productivo","maintaining":"Mantenimiento","insufficient_stimulus":"Estímulo insuficiente","absent":"Sin entrenamiento reciente","high_load":"Carga alta","excessive":"Carga excesiva","strained":"Forzado","unproductive":"No productivo","insufficient_data":"Datos insuficientes"},
      "it":{"productive":"Produttivo","maintaining":"Mantenimento","insufficient_stimulus":"Stimolo insufficiente","absent":"Nessun allenamento recente","high_load":"Carico elevato","excessive":"Carico eccessivo","strained":"Affaticato","unproductive":"Non produttivo","insufficient_data":"Dati insufficienti"},
      "pt":{"productive":"Produtivo","maintaining":"Manutenção","insufficient_stimulus":"Estímulo insuficiente","absent":"Sem treino recente","high_load":"Carga elevada","excessive":"Carga excessiva","strained":"Sob tensão","unproductive":"Não produtivo","insufficient_data":"Dados insuficientes"},
      "nl":{"productive":"Productief","maintaining":"Onderhoud","insufficient_stimulus":"Onvoldoende prikkel","absent":"Geen recente training","high_load":"Hoge belasting","excessive":"Overmatige belasting","strained":"Belast","unproductive":"Niet productief","insufficient_data":"Onvoldoende gegevens"},
      "pl":{"productive":"Produktywny","maintaining":"Utrzymanie","insufficient_stimulus":"Niewystarczający bodziec","absent":"Brak ostatnich treningów","high_load":"Wysokie obciążenie","excessive":"Nadmierne obciążenie","strained":"Przeciążenie","unproductive":"Nieproduktywny","insufficient_data":"Niewystarczające dane"},
      "ru":{"productive":"Продуктивно","maintaining":"Поддержание","insufficient_stimulus":"Недостаточный стимул","absent":"Нет недавних тренировок","high_load":"Высокая нагрузка","excessive":"Чрезмерная нагрузка","strained":"Напряжение","unproductive":"Непродуктивно","insufficient_data":"Недостаточно данных"},
      "uk":{"productive":"Продуктивно","maintaining":"Підтримання","insufficient_stimulus":"Недостатній стимул","absent":"Немає недавніх тренувань","high_load":"Високе навантаження","excessive":"Надмірне навантаження","strained":"Напруження","unproductive":"Непродуктивно","insufficient_data":"Недостатньо даних"},
      "tr":{"productive":"Üretken","maintaining":"Koruma","insufficient_stimulus":"Yetersiz uyaran","absent":"Yakın zamanda antrenman yok","high_load":"Yüksek yük","excessive":"Aşırı yük","strained":"Zorlanmış","unproductive":"Üretken değil","insufficient_data":"Yetersiz veri"},
      "zh":{"productive":"有效提升","maintaining":"维持","insufficient_stimulus":"刺激不足","absent":"近期无训练","high_load":"高负荷","excessive":"负荷过高","strained":"恢复受压","unproductive":"效果不佳","insufficient_data":"数据不足"},
      "ja":{"productive":"向上中","maintaining":"維持","insufficient_stimulus":"刺激不足","absent":"最近のトレーニングなし","high_load":"高負荷","excessive":"過剰負荷","strained":"回復負担","unproductive":"非生産的","insufficient_data":"データ不足"},
      "ko":{"productive":"향상 중","maintaining":"유지","insufficient_stimulus":"자극 부족","absent":"최근 훈련 없음","high_load":"높은 부하","excessive":"과도한 부하","strained":"회복 부담","unproductive":"비생산적","insufficient_data":"데이터 부족"}
    }
    return labels.get(code, labels["en"]).get(status, status)


@dataclass(frozen=True, kw_only=True)
class Desc(SensorEntityDescription):
    kind: str
    metric: str
    unit: str | None = None


# Completed-workout values that already belong to upstream Home Assistant
# integrations must not be mirrored as Fitness sensor entities. Fitness still
# normalizes these fields internally for calculations/history, while the
# dashboard links back to the original source entities.
FITNESS_OWNED_WORKOUT_FACT_FIELDS = {
    "last_workout": "name",
    "last_workout_duration": "duration_s",
    "last_workout_distance": "distance_m",
    "last_workout_avg_hr": "avg_hr",
    "last_workout_max_hr": "max_hr",
    "last_workout_avg_power": "avg_power",
    "last_workout_max_power": "max_power",
    "last_workout_avg_cadence": "avg_cadence",
    "last_workout_elevation_gain": "elevation_gain_m",
    "last_workout_calories": "calories",
    "last_workout_moving_time": "moving_time_s",
    "last_workout_elapsed_time": "elapsed_time_s",
    "last_workout_average_speed": "average_speed_m_s",
    "last_workout_max_speed": "max_speed_m_s",
    "last_workout_weighted_power": "weighted_power",
    "last_workout_max_cadence": "max_cadence",
    "last_workout_elevation_loss": "elevation_loss_m",
    "last_workout_training_load": "training_load",
    "last_workout_aerobic_effect": "aerobic_training_effect",
    "last_workout_anaerobic_effect": "anaerobic_training_effect",
    "last_workout_training_effect": "training_effect_label",
    "last_workout_vo2max": "vo2max",
    "last_workout_rpe": "session_rpe",
    "last_workout_relative_effort": "relative_effort",
    "last_workout_kilojoules": "kilojoules",
    "last_workout_total_reps": "total_reps",
    "last_workout_exercise_count": "exercise_count",
    "last_workout_volume": "volume_kg",
    "last_workout_device": "device_name",
    "last_workout_gear": "gear_name",
}

FITNESS_OWNED_WORKOUT_FACT_KEYS = frozenset({
    *FITNESS_OWNED_WORKOUT_FACT_FIELDS,
    "last_workout_sources",
})


# Latest-sleep measurements are likewise owned by their upstream integration.
# Fitness keeps the normalized SleepRecord internally for calculations, but it
# must never create a second HA entity for the same measurement.
SLEEP_SOURCE_MIRROR_KEYS = frozenset({
    "last_sleep_source",
    "last_sleep_duration",
    "last_sleep_score",
    "last_sleep_efficiency",
    "last_sleep_time_in_bed",
    "last_sleep_awake",
    "last_sleep_light",
    "last_sleep_deep",
    "last_sleep_rem",
    "last_sleep_hrv",
    "last_sleep_average_hr",
    "last_sleep_respiratory_rate",
    "last_sleep_spo2",
    "last_sleep_recovery_score",
    "last_sleep_readiness_score",
})

SOURCE_MIRROR_KEYS = SLEEP_SOURCE_MIRROR_KEYS


def _format_fitness_owned_workout_fact(key: str, value):
    """Format one fact captured by Fitness Live for its own workout entity."""
    if value is None:
        return None
    if key in {"last_workout", "last_workout_training_effect", "last_workout_device", "last_workout_gear"}:
        return str(value)
    if key in {"last_workout_duration", "last_workout_moving_time", "last_workout_elapsed_time"}:
        return round(float(value) / 60.0, 1)
    if key == "last_workout_distance":
        return round(float(value) / 1000.0, 2)
    if key in {"last_workout_average_speed", "last_workout_max_speed"}:
        return round(float(value) * 3.6, 2)
    if key in {"last_workout_avg_hr", "last_workout_max_hr", "last_workout_avg_power", "last_workout_max_power", "last_workout_weighted_power", "last_workout_calories", "last_workout_total_reps", "last_workout_exercise_count"}:
        return round(float(value))
    if key in {"last_workout_avg_cadence", "last_workout_max_cadence", "last_workout_elevation_gain", "last_workout_elevation_loss", "last_workout_training_load", "last_workout_aerobic_effect", "last_workout_anaerobic_effect", "last_workout_vo2max", "last_workout_relative_effort", "last_workout_kilojoules", "last_workout_volume"}:
        return round(float(value), 1)
    if key == "last_workout_rpe":
        return int(round(float(value)))
    return value


DESCRIPTIONS = (
    # Live device
    Desc(key="session_status", translation_key="session_status", kind="live", metric="session_status"),
    Desc(key="session_duration", translation_key="session_duration", kind="live", metric="session_duration", unit="s"),

    # The profile Live device intentionally exposes calculations only. Raw radio
    # measurements (heart rate, power, cadence, speed, distance and altitude)
    # belong exclusively to the physical sensor device under Sensors & Adapters.
    # The calculations below consume only measurements routed from physical
    # sensors assigned to this profile; no mirrored raw entities are created.
    Desc(key="heart_rate_percent_max", translation_key="heart_rate_percent_max", kind="live", metric="heart_rate_percent_max", unit="%"),
    Desc(key="heart_rate_reserve_percent", translation_key="heart_rate_reserve_percent", kind="live", metric="heart_rate_reserve_percent", unit="%"),
    Desc(key="heart_rate_intensity", translation_key="heart_rate_intensity", kind="live", metric="heart_rate_intensity"),
    Desc(key="heart_rate_relative_threshold", translation_key="heart_rate_relative_threshold", kind="live", metric="heart_rate_relative_threshold", unit="%"),
    Desc(key="current_power_to_weight", translation_key="current_power_to_weight", kind="live", metric="current_power_to_weight", unit="W/kg"),
    Desc(key="power_relative_threshold", translation_key="power_relative_threshold", kind="live", metric="power_relative_threshold", unit="%"),
    Desc(key="current_pace", translation_key="current_pace", kind="live", metric="current_pace", unit="min/km"),
    Desc(key="speed_relative_threshold", translation_key="speed_relative_threshold", kind="live", metric="speed_relative_threshold", unit="%"),
    Desc(key="live_average_heart_rate", translation_key="live_average_heart_rate", kind="live", metric="live_average_hr", unit="bpm"),
    Desc(key="live_maximum_heart_rate", translation_key="live_maximum_heart_rate", kind="live", metric="live_maximum_hr", unit="bpm"),
    Desc(key="live_average_power", translation_key="live_average_power", kind="live", metric="live_average_power", unit="W"),
    Desc(key="live_maximum_power", translation_key="live_maximum_power", kind="live", metric="live_maximum_power", unit="W"),
    Desc(key="live_average_cadence", translation_key="live_average_cadence", kind="live", metric="live_average_cadence", unit="1/min"),
    Desc(key="live_average_speed", translation_key="live_average_speed", kind="live", metric="live_average_speed", unit="km/h"),
    Desc(key="live_banister_trimp", translation_key="live_banister_trimp", kind="live", metric="live_banister_trimp"),
    Desc(key="live_mechanical_work", translation_key="live_mechanical_work", kind="live", metric="live_mechanical_work", unit="kJ"),
    Desc(key="live_aerobic_efficiency", translation_key="live_aerobic_efficiency", kind="live", metric="live_aerobic_efficiency"),
    Desc(key="live_aerobic_decoupling", translation_key="live_aerobic_decoupling", kind="live", metric="live_aerobic_decoupling", unit="%"),
    Desc(key="live_time_moderate", translation_key="live_time_moderate", kind="live", metric="live_time_moderate", unit="s"),
    Desc(key="live_time_vigorous", translation_key="live_time_vigorous", kind="live", metric="live_time_vigorous", unit="s"),
    Desc(key="live_time_near_maximal", translation_key="live_time_near_maximal", kind="live", metric="live_time_near_maximal", unit="s"),
    Desc(key="live_data", name="Live data", kind="live", metric="live_data"),

    # Workout device
    Desc(key="last_workout", translation_key="last_workout", kind="workout", metric="workout_name"),
    Desc(key="last_workout_duration", translation_key="last_workout_duration", kind="workout", metric="workout_duration", unit="min"),
    Desc(key="last_workout_distance", translation_key="last_workout_distance", kind="workout", metric="workout_distance", unit="km"),
    Desc(key="last_workout_avg_hr", translation_key="last_workout_avg_hr", kind="workout", metric="workout_avg_hr", unit="bpm"),
    Desc(key="last_workout_max_hr", translation_key="last_workout_max_hr", kind="workout", metric="workout_max_hr", unit="bpm"),
    Desc(key="last_workout_avg_power", translation_key="last_workout_avg_power", kind="workout", metric="workout_avg_power", unit="W"),
    Desc(key="last_workout_max_power", translation_key="last_workout_max_power", kind="workout", metric="workout_max_power", unit="W"),
    Desc(key="last_workout_avg_cadence", translation_key="last_workout_avg_cadence", kind="workout", metric="workout_avg_cadence", unit="spm"),
    Desc(key="last_workout_elevation_gain", translation_key="last_workout_elevation_gain", kind="workout", metric="workout_elevation", unit="m"),
    Desc(key="last_workout_calories", translation_key="last_workout_calories", kind="workout", metric="workout_calories", unit="kcal"),
    Desc(key="last_workout_moving_time", translation_key="last_workout_moving_time", kind="workout", metric="workout_moving_time", unit="min"),
    Desc(key="last_workout_elapsed_time", translation_key="last_workout_elapsed_time", kind="workout", metric="workout_elapsed_time", unit="min"),
    Desc(key="last_workout_average_speed", translation_key="last_workout_average_speed", kind="workout", metric="workout_average_speed", unit="km/h"),
    Desc(key="last_workout_max_speed", translation_key="last_workout_max_speed", kind="workout", metric="workout_max_speed", unit="km/h"),
    Desc(key="last_workout_weighted_power", translation_key="last_workout_weighted_power", kind="workout", metric="workout_weighted_power", unit="W"),
    Desc(key="last_workout_max_cadence", translation_key="last_workout_max_cadence", kind="workout", metric="workout_max_cadence", unit="1/min"),
    Desc(key="last_workout_elevation_loss", translation_key="last_workout_elevation_loss", kind="workout", metric="workout_elevation_loss", unit="m"),
    Desc(key="last_workout_training_load", translation_key="last_workout_training_load", kind="workout", metric="workout_training_load"),
    Desc(key="last_workout_aerobic_effect", translation_key="last_workout_aerobic_effect", kind="workout", metric="workout_aerobic_effect"),
    Desc(key="last_workout_anaerobic_effect", translation_key="last_workout_anaerobic_effect", kind="workout", metric="workout_anaerobic_effect"),
    Desc(key="last_workout_training_effect", translation_key="last_workout_training_effect", kind="workout", metric="workout_training_effect"),
    Desc(key="last_workout_vo2max", translation_key="last_workout_vo2max", kind="workout", metric="workout_vo2max", unit="mL/kg/min"),
    Desc(key="last_workout_rpe", translation_key="last_workout_rpe", kind="workout", metric="workout_rpe"),
    Desc(key="last_workout_session_rpe_load", translation_key="last_workout_session_rpe_load", kind="workout", metric="workout_session_rpe_load"),
    Desc(key="last_workout_rpe_load_vs_baseline", translation_key="last_workout_rpe_load_vs_baseline", kind="workout", metric="workout_rpe_load_vs_baseline", unit="%"),
    Desc(key="last_workout_fitness_aerobic_load", translation_key="last_workout_fitness_aerobic_load", kind="workout", metric="workout_fitness_aerobic_load", unit="%"),
    Desc(key="last_workout_fitness_high_intensity_load", translation_key="last_workout_fitness_high_intensity_load", kind="workout", metric="workout_fitness_high_intensity_load", unit="%"),
    Desc(key="last_workout_strength_sets", translation_key="last_workout_strength_sets", kind="workout", metric="workout_strength_sets"),
    Desc(key="last_workout_estimated_1rm", translation_key="last_workout_estimated_1rm", kind="workout", metric="workout_estimated_1rm", unit="kg"),
    Desc(key="last_workout_strength_progression", translation_key="last_workout_strength_progression", kind="workout", metric="workout_strength_progression", unit="%"),
    Desc(key="last_workout_relative_effort", translation_key="last_workout_relative_effort", kind="workout", metric="workout_relative_effort"),
    Desc(key="last_workout_kilojoules", translation_key="last_workout_kilojoules", kind="workout", metric="workout_kilojoules", unit="kJ"),
    Desc(key="last_workout_total_reps", translation_key="last_workout_total_reps", kind="workout", metric="workout_total_reps"),
    Desc(key="last_workout_exercise_count", translation_key="last_workout_exercise_count", kind="workout", metric="workout_exercise_count"),
    Desc(key="last_workout_volume", translation_key="last_workout_volume", kind="workout", metric="workout_volume", unit="kg"),
    Desc(key="last_workout_device", translation_key="last_workout_device", kind="workout", metric="workout_device"),
    Desc(key="last_workout_gear", translation_key="last_workout_gear", kind="workout", metric="workout_gear"),
    Desc(key="last_workout_sources", translation_key="last_workout_sources", kind="workout", metric="workout_sources"),
    Desc(key="last_workout_banister_trimp", translation_key="last_workout_banister_trimp", kind="workout", metric="workout_banister_trimp"),
    Desc(key="last_workout_trimp_per_hour", translation_key="last_workout_trimp_per_hour", kind="workout", metric="workout_trimp_per_hour"),
    Desc(key="last_workout_mechanical_work", translation_key="last_workout_mechanical_work", kind="workout", metric="workout_mechanical_work", unit="kJ"),
    Desc(key="last_workout_aerobic_efficiency", translation_key="last_workout_aerobic_efficiency", kind="workout", metric="workout_aerobic_efficiency"),
    Desc(key="last_workout_aerobic_decoupling", translation_key="last_workout_aerobic_decoupling", kind="workout", metric="workout_aerobic_decoupling", unit="%"),
    Desc(key="last_workout_hrr_10s", translation_key="last_workout_hrr_10s", kind="workout", metric="workout_hrr_10s", unit="bpm"),
    Desc(key="last_workout_hrr_30s", translation_key="last_workout_hrr_30s", kind="workout", metric="workout_hrr_30s", unit="bpm"),
    Desc(key="last_workout_hrr_60s", translation_key="last_workout_hrr_60s", kind="workout", metric="workout_hrr_60s", unit="bpm"),
    Desc(key="last_workout_hrr_120s", translation_key="last_workout_hrr_120s", kind="workout", metric="workout_hrr_120s", unit="bpm"),
    Desc(key="last_workout_time_moderate", translation_key="last_workout_time_moderate", kind="workout", metric="workout_time_moderate", unit="min"),
    Desc(key="last_workout_time_vigorous", translation_key="last_workout_time_vigorous", kind="workout", metric="workout_time_vigorous", unit="min"),
    Desc(key="last_workout_time_near_maximal", translation_key="last_workout_time_near_maximal", kind="workout", metric="workout_time_near_maximal", unit="min"),
    Desc(key="last_workout_comparable_count", translation_key="last_workout_comparable_count", kind="workout", metric="workout_comparable_count"),
    Desc(key="last_workout_efficiency_vs_baseline", translation_key="last_workout_efficiency_vs_baseline", kind="workout", metric="workout_efficiency_vs_baseline", unit="%"),
    Desc(key="last_workout_decoupling_vs_baseline", translation_key="last_workout_decoupling_vs_baseline", kind="workout", metric="workout_decoupling_vs_baseline", unit="%"),
    Desc(key="last_workout_hr_vs_baseline", translation_key="last_workout_hr_vs_baseline", kind="workout", metric="workout_hr_vs_baseline", unit="bpm"),
    Desc(key="last_workout_power_vs_baseline", translation_key="last_workout_power_vs_baseline", kind="workout", metric="workout_power_vs_baseline", unit="%"),
    Desc(key="last_workout_speed_vs_baseline", translation_key="last_workout_speed_vs_baseline", kind="workout", metric="workout_speed_vs_baseline", unit="%"),
    Desc(key="last_workout_trimp_vs_recent", translation_key="last_workout_trimp_vs_recent", kind="workout", metric="workout_trimp_vs_recent", unit="%"),
    Desc(key="last_workout_load_context", translation_key="last_workout_load_context", kind="workout", metric="workout_load_context"),
    Desc(key="last_workout_personal_context", translation_key="last_workout_personal_context", kind="workout", metric="workout_personal_context"),
    Desc(key="workout_data", name="Workout data", kind="workout", metric="workout_data"),

    # Sleep device
    Desc(key="readiness", translation_key="readiness", kind="sleep", metric="readiness", unit="%"),
    Desc(key="estimated_recovery_time", translation_key="estimated_recovery_time", kind="sleep", metric="estimated_recovery_time", unit="h"),
    Desc(key="last_sleep_source", translation_key="last_sleep_source", kind="sleep", metric="sleep_source"),
    Desc(key="last_sleep_duration", translation_key="last_sleep_duration", kind="sleep", metric="sleep_duration", unit="min"),
    Desc(key="last_sleep_score", translation_key="last_sleep_score", kind="sleep", metric="sleep_score"),
    Desc(key="last_sleep_efficiency", translation_key="last_sleep_efficiency", kind="sleep", metric="sleep_efficiency", unit="%"),
    Desc(key="last_sleep_time_in_bed", translation_key="last_sleep_time_in_bed", kind="sleep", metric="sleep_time_in_bed", unit="min"),
    Desc(key="last_sleep_awake", translation_key="last_sleep_awake", kind="sleep", metric="sleep_awake", unit="min"),
    Desc(key="last_sleep_light", translation_key="last_sleep_light", kind="sleep", metric="sleep_light", unit="min"),
    Desc(key="last_sleep_deep", translation_key="last_sleep_deep", kind="sleep", metric="sleep_deep", unit="min"),
    Desc(key="last_sleep_rem", translation_key="last_sleep_rem", kind="sleep", metric="sleep_rem", unit="min"),
    Desc(key="last_sleep_hrv", translation_key="last_sleep_hrv", kind="sleep", metric="sleep_hrv", unit="ms"),
    Desc(key="last_sleep_average_hr", translation_key="last_sleep_average_hr", kind="sleep", metric="sleep_average_hr", unit="bpm"),
    Desc(key="last_sleep_respiratory_rate", translation_key="last_sleep_respiratory_rate", kind="sleep", metric="sleep_respiratory_rate", unit="1/min"),
    Desc(key="last_sleep_spo2", translation_key="last_sleep_spo2", kind="sleep", metric="sleep_spo2", unit="%"),
    Desc(key="last_sleep_recovery_score", translation_key="last_sleep_recovery_score", kind="sleep", metric="sleep_recovery_score"),
    Desc(key="last_sleep_readiness_score", translation_key="last_sleep_readiness_score", kind="sleep", metric="sleep_readiness_score"),
    Desc(key="recovery_data", name="Recovery data", kind="sleep", metric="recovery_data"),

    # Evaluation device — compact evidence-based domains.
    Desc(key="sleep_consistency", translation_key="sleep_consistency", kind="evaluation", metric="sleep_consistency", unit="min"),
    Desc(key="sleep_deficit_7d", translation_key="sleep_deficit_7d", kind="evaluation", metric="sleep_deficit_7d", unit="min"),
    Desc(key="autonomic_recovery_trend", translation_key="autonomic_recovery_trend", kind="evaluation", metric="autonomic_recovery_trend", unit="%"),
    Desc(key="cardiorespiratory_fitness_trend", translation_key="cardiorespiratory_fitness_trend", kind="evaluation", metric="cardiorespiratory_fitness_trend", unit="%"),
    Desc(key="vo2max_percent_predicted", translation_key="vo2max_percent_predicted", kind="evaluation", metric="vo2max_percent_predicted", unit="%"),
    Desc(key="training_load", translation_key="training_load", kind="evaluation", metric="training_load", unit="min"),
    Desc(key="heart_rate_recovery", translation_key="heart_rate_recovery", kind="evaluation", metric="heart_rate_recovery", unit="bpm"),
    Desc(key="training_recovery_relationship", translation_key="training_recovery_relationship", kind="evaluation", metric="training_recovery_relationship"),
    Desc(key="training_adaptation_status", translation_key="training_adaptation_status", kind="evaluation", metric="training_adaptation_status"),
    Desc(key="ai_general_evaluation", translation_key="ai_general_evaluation", kind="evaluation", metric="ai_general"),
    Desc(key="ai_workout_evaluation", translation_key="ai_workout_evaluation", kind="evaluation", metric="ai_workout"),
    Desc(key="evaluation_data", name="Evaluation data", kind="evaluation", metric="evaluation_data"),


)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up profile sensors or global Local Sensors entities."""
    from .live import get_live_runtime
    from .live.runtime import HUB_ENTRY_TYPE
    runtime = get_live_runtime(hass)
    if entry.data.get("entry_type") == HUB_ENTRY_TYPE:
        from .live.ha_entities import async_setup_sensor_entities
        await async_setup_sensor_entities(runtime, async_add_entities)
        return

    manager = hass.data[DOMAIN][entry.entry_id]
    # Profile Live entities are permanent calculation infrastructure. Physical
    # sensor assignment affects data routing only, never profile entity/device
    # creation.
    registry = er.async_get(hass)

    # Remove obsolete Evaluation mirrors from older betas instead of leaving
    # permanent unavailable ghost entities in the device registry.
    deprecated_evaluation_keys = {
        "age", "weight", "resting_hr", "maximum_hr", "heart_rate_reserve",
        "vo2max", "friend_predicted_vo2max", "cardiorespiratory_status",
        "hrv_weekly", "hrv_last_night", "hrv_status", "threshold_hr",
        "threshold_pace", "threshold_power", "threshold_power_to_weight",
        "fitness_age", "fitness_age_difference", "training_readiness_context",
        "sleep_score_context", "acute_training_load", "chronic_training_load",
        "acute_chronic_ratio", "provider_training_status", "training_load_42d",
        "aerobic_decoupling_long_term", "aerobic_efficiency_long_term",
        "training_load_7d", "training_load_28d", "training_load_change_7_vs_28",
        "training_days_28d", "hrr_60s_long_term", "hrr_60s_vs_90d",
        "sleep_duration_7d_mean", "sleep_duration_28d_mean", "sleep_duration_vs_28d",
        "sleep_duration_shortfall", "sleep_midpoint_variability_14d",
        "sleep_hrv_7d_mean", "sleep_hrv_28d_mean", "sleep_hrv_vs_28d",
        "resting_hr_7d_mean", "resting_hr_28d_mean", "resting_hr_vs_28d",
        "vo2max_28d_mean", "vo2max_trend_14_vs_previous_14",
    }
    prefix = f"{entry.entry_id}_"
    # Live calculation entities are stable profile infrastructure. They are
    # created independently of radio/sensor assignment so accepting, deleting or
    # reassigning a physical sensor never requires rebuilding the profile.
    descriptions = {
        desc.key: desc
        for desc in DESCRIPTIONS
        if desc.key not in SOURCE_MIRROR_KEYS
        and not (
            desc.metric.startswith("ai_")
            and not manager.config.get("ai_enabled")
        )
    }
    live_keys = {desc.key for desc in DESCRIPTIONS if desc.kind == "live"}
    # Raw source mirrors existed in older betas on each profile Live device.
    # They are migrated away permanently: their canonical home is the physical
    # sensor device under Sensors & Adapters.
    deprecated_live_mirror_keys = {
        "current_heart_rate",
        "current_power",
        "current_cadence",
        "current_speed",
        "current_distance",
        "current_altitude",
    }
    registry_keys: set[str] = set()

    # One profile setup gets one whole-registry pass.  Older versions performed
    # four independent scans here; during reload storms that multiplied the cost
    # of every profile reconstruction.  Do migrations, stale cleanup and restore
    # bookkeeping while the registry is already in cache.
    for registry_entry in list(registry.entities.values()):
        if registry_entry.platform != DOMAIN:
            continue
        unique_id = registry_entry.unique_id or ""
        if not unique_id.startswith(prefix):
            continue
        key = unique_id[len(prefix):]

        if key in deprecated_evaluation_keys:
            registry.async_remove(registry_entry.entity_id)
            manager.materialized_sensor_keys.discard(key)
            continue

        if key in deprecated_live_mirror_keys:
            registry.async_remove(registry_entry.entity_id)
            manager.forget_materialized_sensor(key, persist=False)
            continue

        # Factual source fields (completed-workout and latest-sleep data) are
        # owned by their upstream integrations. Remove legacy Fitness mirrors.
        if key in SOURCE_MIRROR_KEYS:
            registry.async_remove(registry_entry.entity_id)
            manager.forget_materialized_sensor(key, persist=False)
            continue

        # Remove the obsolete duplicate source entity from older versions.
        if key == "last_workout_source":
            registry.async_remove(registry_entry.entity_id)
            manager.forget_materialized_sensor(key, persist=False)
            continue

        if key in descriptions:
            registry_keys.add(key)

    manager.remember_materialized_sensors(
        registry_keys,
        persist=True,
    )

    # The Live device is permanent profile infrastructure. Materialize its
    # complete calculation surface once, independent of sensor assignment. This
    # prevents accepting/reassigning/deleting a radio sensor from creating or
    # deleting profile entities. Values remain unavailable until their assigned
    # physical sensor inputs and an active session make the calculation valid.
    manager.remember_materialized_sensors(live_keys, persist=True)
    manager.remember_materialized_sensors(set(DATA_MAP_KEYS), persist=True)

    # Factual workout entities are legitimate only for facts Fitness itself
    # captured in a Live-created workout. Restore only the values Fitness owns;
    # provider-enriched fields (for example Garmin calories) remain upstream.
    fitness_workout = manager.latest_fitness_workout()
    if fitness_workout is not None:
        owned_keys = {"last_workout_sources"}
        for fact_key, field_name in FITNESS_OWNED_WORKOUT_FACT_FIELDS.items():
            if fitness_owned_workout_value(fitness_workout, field_name) is not None:
                owned_keys.add(fact_key)
        manager.remember_materialized_sensors(owned_keys, persist=True)

    # Recovery time is a stable Recovery-device entity, not a transient
    # capability. It must exist even when no completed workout is available yet.
    # Its state may legitimately be unavailable until the first workout arrives,
    # after which normal manager notifications update it. Keeping it permanently
    # materialized also avoids an integration-start ordering race where Fitness
    # loads before a workout provider such as Garmin/Strava.
    manager.remember_materialized_sensor(
        "estimated_recovery_time",
        persist=True,
    )

    created_keys: set[str] = set()

    def collect_new_entities(
        *,
        allow_probe: bool = False,
        kinds: set[str] | None = None,
    ) -> list[FitnessSensor]:
        """Collect materialized entities without blocking platform startup.

        Startup only restores keys already known to Fitness. Optional new metrics
        are discovered after manager updates, when Home Assistant is no longer
        waiting for this platform's setup coroutine to finish.
        """
        result: list[FitnessSensor] = []

        for key, desc in descriptions.items():
            if key in created_keys:
                continue
            if kinds is not None and desc.kind not in kinds:
                continue

            previously_created = manager.sensor_was_materialized(key)
            if not previously_created:
                if not allow_probe:
                    continue
                probe = FitnessSensor(manager, entry, desc)
                try:
                    if probe.native_value is None:
                        continue
                except Exception:
                    continue
                manager.remember_materialized_sensor(key, persist=True)

            created_keys.add(key)
            result.append(FitnessSensor(manager, entry, desc))

        return result

    # Critical startup rule: never call native_value merely to decide which
    # entities to add. Restoring the persisted materialization set is O(n) and
    # side-effect free.
    initial = collect_new_entities(allow_probe=False)
    if initial:
        async_add_entities(initial)

    pending_materialization_kinds: set[str] = set()
    materialization_handle = None

    @callback
    def _materialize_pending_sensors() -> None:
        nonlocal materialization_handle
        materialization_handle = None
        kinds = set(pending_materialization_kinds)
        pending_materialization_kinds.clear()
        if not kinds:
            return
        new_entities = collect_new_entities(allow_probe=True, kinds=kinds)
        if new_entities:
            async_add_entities(new_entities)

    @callback
    def _schedule_materialization(kinds: set[str]) -> None:
        nonlocal materialization_handle
        pending_materialization_kinds.update(kinds)
        if materialization_handle is not None:
            return
        # Entity discovery is control-plane work. Coalesce bursts and probe only
        # the domain that actually changed instead of walking all 116 descriptions
        # inside every manager notification.
        materialization_handle = hass.loop.call_later(
            1.0, _materialize_pending_sensors
        )

    @callback
    def _materialize_general() -> None:
        _schedule_materialization({"workout", "evaluation"})

    @callback
    def _materialize_sleep() -> None:
        _schedule_materialization({"sleep", "evaluation"})

    @callback
    def _materialize_live() -> None:
        _schedule_materialization({"live"})

    @callback
    def _cancel_materialization() -> None:
        nonlocal materialization_handle
        if materialization_handle is not None:
            materialization_handle.cancel()
            materialization_handle = None
        pending_materialization_kinds.clear()

    entry.async_on_unload(manager.add_listener(_materialize_general))
    entry.async_on_unload(manager.add_sleep_listener(_materialize_sleep))
    entry.async_on_unload(manager.add_live_listener(_materialize_live))
    entry.async_on_unload(_cancel_materialization)

    @callback
    def recovery_time_tick(_now) -> None:
        # Remaining recovery time is time-dependent even when no provider state
        # changes. A 15-minute tick keeps the Recovery device/card current with
        # negligible overhead.
        manager._notify_sleep()

    entry.async_on_unload(
        async_track_time_interval(hass, recovery_time_tick, timedelta(minutes=15))
    )


class FitnessSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, manager, entry, desc):
        self.manager = manager
        self.entry = entry
        self.entity_description = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_device_info = device_info(entry, desc.kind)
        self._data_map_attributes: dict = {
            "schema_version": DATA_MAP_SCHEMA_VERSION,
            "map_kind": "recovery" if desc.kind == "sleep" else desc.kind,
            "mapped_keys": [],
            "route_count": 0,
            "direct_source_count": 0,
        } if desc.key in DATA_MAP_KEYS else {}
        self._data_map_refresh_handle = None

    def _cancel_data_map_refresh(self):
        if self._data_map_refresh_handle is not None:
            self._data_map_refresh_handle.cancel()
            self._data_map_refresh_handle = None

    def _schedule_data_map_refresh(self, delay: float | None = None):
        """Coalesce source-map rebuilds without mirroring high-rate source values."""
        if self.entity_description.key not in DATA_MAP_KEYS:
            return
        if self._data_map_refresh_handle is not None:
            return
        if delay is None:
            delay = 2.0 if self.entity_description.key == "live_data" else 0.5
        self._data_map_refresh_handle = self.hass.loop.call_later(
            delay, self._refresh_data_map
        )

    @callback
    def _refresh_data_map(self):
        self._data_map_refresh_handle = None
        key = self.entity_description.key
        if key not in DATA_MAP_KEYS:
            return
        try:
            routes = build_profile_routes(
                self.hass,
                self.manager,
                self.entry,
                DATA_MAP_KEYS[key],
                DESCRIPTIONS,
            )
            attributes = routes_to_attributes(DATA_MAP_KEYS[key], routes)
        except Exception:
            _LOGGER.exception(
                "Unable to refresh Fitness %s source map for %s",
                key,
                self.entry.entry_id,
            )
            return
        if attributes == self._data_map_attributes:
            return
        self._data_map_attributes = attributes
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        if self.entity_description.key in DATA_MAP_KEYS:
            # Data-map sensors subscribe only to domains that can change routing
            # or a low-frequency inline fallback fact. High-rate source metrics
            # remain on their source entities and never rewrite the map sensor.
            # The scheduled builder is coalesced and writes only on attribute
            # changes, keeping Recorder traffic negligible.
            self.async_on_remove(self.manager.add_listener(self._schedule_data_map_refresh))
            key = self.entity_description.key
            if key == "live_data":
                self.async_on_remove(self.manager.add_live_listener(self._schedule_data_map_refresh))
            elif key == "workout_data":
                self.async_on_remove(self.manager.add_workout_history_listener(self._schedule_data_map_refresh))
            elif key in {"recovery_data", "evaluation_data"}:
                self.async_on_remove(self.manager.add_sleep_listener(self._schedule_data_map_refresh))
                if key == "evaluation_data":
                    self.async_on_remove(self.manager.add_workout_history_listener(self._schedule_data_map_refresh))
            self.async_on_remove(self._cancel_data_map_refresh)
            self._schedule_data_map_refresh(delay=0.5)
            return
        # Clear only known legacy auto-generated names. This lets the current
        # translation_key supply the corrected localized title without touching
        # genuinely user-customized entity names.
        if self.entity_description.key == "ai_workout_evaluation":
            registry = er.async_get(self.hass)
            registry_entry = registry.async_get(self.entity_id)
            if registry_entry is not None and registry_entry.name in {
                "Τελευταίας προπόνησης με AI",
                "Προπόνησης με AI",
                "Last workout with AI",
                "Last workout AI",
            }:
                registry.async_update_entity(self.entity_id, name=None)

        # Every Fitness sensor receives low-frequency/general manager updates.
        self.async_on_remove(
            self.manager.add_listener(self._update)
        )

        # Live sensors additionally receive the high-frequency live-only path.
        if self.entity_description.kind == "live":
            self.async_on_remove(
                self.manager.add_live_listener(self._update)
            )
        elif self.entity_description.kind == "sleep":
            self.async_on_remove(
                self.manager.add_sleep_listener(self._update)
            )

    def _update(self):
        self.async_write_ha_state()

    @property
    def state_class(self):
        textual = {
            "session_status",
            "heart_rate_intensity",
            "workout_name",
            "workout_source",
            "workout_training_effect",
            "workout_device",
            "workout_gear",
            "workout_sources",
            "workout_load_context",
            "workout_personal_context",
            "ai_general",
            "ai_workout",
            "cardiorespiratory_status",
            "hrv_status",
            "provider_training_status",
            "training_adaptation_status",
            "sleep_source",
            "live_data",
            "workout_data",
            "recovery_data",
            "evaluation_data",
        }
        if self.entity_description.metric in textual:
            return None
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self):
        return self.entity_description.unit

    @staticmethod
    def _sleep_source_names(record):
        names = {
            "garmin_connect": "Garmin Connect",
            "sleep_as_android": "Sleep as Android",
            "oura": "Oura",
            "fitbit": "Fitbit",
            "withings": "Withings",
            "whoop": "WHOOP",
            "suunto": "Suunto",
            "sleepiq": "SleepIQ",
            "eight_sleep": "Eight Sleep",
            "eightsleep": "Eight Sleep",
        }
        domains = list(record.provider_domains or [])
        if not domains and record.provider_domain and record.provider_domain != "merged":
            domains = [record.provider_domain]
        return [names.get(domain, domain.replace("_", " ").title()) for domain in domains]

    @classmethod
    def _sleep_source_name(cls, record):
        names = cls._sleep_source_names(record)
        return " + ".join(names) if names else None

    @staticmethod
    def _provider_display_name(value):
        """Return a human-readable provider name without altering entity IDs."""
        if not isinstance(value, str):
            return value
        if "." in value:
            # Entity IDs are valuable provenance and must stay exact.
            return value
        names = {
            "garmin_connect": "Garmin Connect",
            "sleep_as_android": "Sleep as Android",
            "antplus": "ANT+",
            "ant_plus": "ANT+",
            "stryd_ble": "Stryd",
            "google_fit": "Google Fit",
            "health_connect": "Health Connect",
            "samsung_health": "Samsung Health",
            "eight_sleep": "Eight Sleep",
            "eightsleep": "Eight Sleep",
            "withings": "Withings",
            "fitbit": "Fitbit",
            "oura": "Oura",
            "whoop": "WHOOP",
            "suunto": "Suunto",
            "hevy": "Hevy",
        }
        return names.get(value, value.replace("_", " ").title())

    @staticmethod
    def _meaningful_workout_value(metric: str, value):
        """Suppress provider placeholder zeroes that mean a metric was not recorded.

        Zero is retained for metrics where it is physiologically or analytically
        meaningful (for example training effect, percentages and comparisons).
        """
        if value is None:
            return None
        zero_is_missing = {
            "workout_distance", "workout_avg_power", "workout_max_power",
            "workout_avg_cadence", "workout_elevation", "workout_calories",
            "workout_moving_time", "workout_elapsed_time",
            "workout_average_speed", "workout_max_speed",
            "workout_weighted_power", "workout_max_cadence",
            "workout_elevation_loss", "workout_kilojoules",
            "workout_total_reps", "workout_exercise_count", "workout_volume",
            "workout_strength_sets", "workout_estimated_1rm",
            "workout_mechanical_work",
        }
        if metric in zero_is_missing and isinstance(value, (int, float)) and abs(float(value)) < 1e-12:
            return None
        return value

    @property
    def native_value(self):
        m = self.entity_description.metric

        if self.entity_description.key in DATA_MAP_KEYS:
            return "ready"

        if self.entity_description.kind == "live":
            if m == "session_status":
                return self.manager.session_status()

            if not self.manager.session_active:
                return None

            if m == "session_duration":
                return round(self.manager.session_duration())

            derived = self.manager.live_derived_values()
            session_stats = self.manager.live_session_statistics()

            if m == "heart_rate_percent_max":
                value = derived.get(m)
                return round(value, 1) if value is not None else None

            if m == "heart_rate_reserve_percent":
                value = derived.get(m)
                return round(value, 1) if value is not None else None

            if m == "heart_rate_intensity":
                return derived.get(m)

            if m == "heart_rate_relative_threshold":
                value = derived.get(m)
                return round(value, 1) if value is not None else None

            if m == "current_power_to_weight":
                value = derived.get(m)
                return round(value, 2) if value is not None else None

            if m == "power_relative_threshold":
                value = derived.get(m)
                return round(value, 1) if value is not None else None

            if m == "current_pace":
                value = derived.get(m)
                return round(value, 2) if value is not None else None

            if m == "speed_relative_threshold":
                value = derived.get(m)
                return round(value, 1) if value is not None else None

            live_stats_map = {
                "live_average_hr": session_stats.get("average_hr"),
                "live_maximum_hr": session_stats.get("maximum_hr"),
                "live_average_power": session_stats.get("average_power"),
                "live_maximum_power": session_stats.get("maximum_power"),
                "live_average_cadence": session_stats.get("average_cadence"),
                "live_average_speed": session_stats.get("average_speed"),
                "live_banister_trimp": session_stats.get("banister_trimp"),
                "live_mechanical_work": session_stats.get("mechanical_work_kj"),
                "live_aerobic_efficiency": session_stats.get("aerobic_efficiency"),
                "live_aerobic_decoupling": session_stats.get("aerobic_decoupling_percent"),
                "live_time_moderate": session_stats.get("time_moderate_s"),
                "live_time_vigorous": session_stats.get("time_vigorous_s"),
                "live_time_near_maximal": session_stats.get("time_near_maximal_s"),
            }
            value = live_stats_map.get(m)
            return round(value, 2) if value is not None else None

        if self.entity_description.kind == "sleep":
            if m in {"readiness", "estimated_recovery_time"} and not self.manager.post_start_ready:
                return None
            if m == "readiness":
                value = self.manager.readiness_evaluation().get("score")
                return round(float(value), 1) if value is not None else None
            if m == "estimated_recovery_time":
                value = self.manager.recovery_time_evaluation().get("remaining_hours")
                return round(float(value), 1) if value is not None else None
            r = self.manager.latest_sleep()
            if r is None:
                return None
            values = {
                "sleep_source": self._sleep_source_name(r),
                "sleep_duration": r.duration_s / 60 if r.duration_s is not None else None,
                "sleep_score": r.score,
                "sleep_efficiency": r.efficiency_percent,
                "sleep_time_in_bed": r.time_in_bed_s / 60 if r.time_in_bed_s is not None else None,
                "sleep_awake": r.awake_s / 60 if r.awake_s is not None else None,
                "sleep_light": r.light_sleep_s / 60 if r.light_sleep_s is not None else None,
                "sleep_deep": r.deep_sleep_s / 60 if r.deep_sleep_s is not None else None,
                "sleep_rem": r.rem_sleep_s / 60 if r.rem_sleep_s is not None else None,
                "sleep_hrv": r.hrv_ms,
                "sleep_average_hr": r.average_hr,
                "sleep_respiratory_rate": r.respiratory_rate,
                "sleep_spo2": r.spo2_percent,
                "sleep_recovery_score": r.recovery_score,
                "sleep_readiness_score": r.readiness_score,
            }
            value = values.get(m)
            return round(value, 2) if isinstance(value, (int, float)) else value

        if self.entity_description.kind == "sleep":
            record = self.manager.latest_sleep()
            if record is None:
                return {}
            return {
                **record.as_dict(),
                "merged_sources": list(record.provider_domains),
                "source_count": len(record.provider_domains),
            }

        if self.entity_description.kind == "workout":
            key = self.entity_description.key
            if key in FITNESS_OWNED_WORKOUT_FACT_KEYS:
                w = self.manager.latest_fitness_workout()
                if w is None:
                    return None
                if key == "last_workout_sources":
                    return ", ".join(w.provider_domains or w.sources) if (w.provider_domains or w.sources) else w.source
                field_name = FITNESS_OWNED_WORKOUT_FACT_FIELDS.get(key)
                value = fitness_owned_workout_value(w, field_name) if field_name else None
                return _format_fitness_owned_workout_fact(key, value)

            w = self.manager.latest_workout()
            if w is None:
                return None
            values = {
                "workout_name": w.name or w.sport or "Workout",
                "workout_duration": round(w.duration_s / 60, 1) if w.duration_s is not None else None,
                "workout_distance": round(w.distance_m / 1000, 2) if w.distance_m is not None else None,
                "workout_avg_hr": round(w.avg_hr) if w.avg_hr is not None else None,
                "workout_max_hr": round(w.max_hr) if w.max_hr is not None else None,
                "workout_avg_power": round(w.avg_power) if w.avg_power is not None else None,
                "workout_max_power": round(w.max_power) if w.max_power is not None else None,
                "workout_avg_cadence": round(w.avg_cadence, 1) if w.avg_cadence is not None else None,
                "workout_elevation": round(w.elevation_gain_m, 1) if w.elevation_gain_m is not None else None,
                "workout_calories": round(w.calories) if w.calories is not None else None,
                "workout_moving_time": round(w.moving_time_s / 60, 1) if w.moving_time_s is not None else None,
                "workout_elapsed_time": round(w.elapsed_time_s / 60, 1) if w.elapsed_time_s is not None else None,
                "workout_average_speed": round(w.average_speed_m_s * 3.6, 2) if w.average_speed_m_s is not None else None,
                "workout_max_speed": round(w.max_speed_m_s * 3.6, 2) if w.max_speed_m_s is not None else None,
                "workout_weighted_power": round(w.weighted_power) if w.weighted_power is not None else None,
                "workout_max_cadence": round(w.max_cadence, 1) if w.max_cadence is not None else None,
                "workout_elevation_loss": round(w.elevation_loss_m, 1) if w.elevation_loss_m is not None else None,
                "workout_training_load": round(w.training_load, 1) if w.training_load is not None else None,
                "workout_aerobic_effect": round(w.aerobic_training_effect, 1) if w.aerobic_training_effect is not None else None,
                "workout_anaerobic_effect": round(w.anaerobic_training_effect, 1) if w.anaerobic_training_effect is not None else None,
                "workout_training_effect": w.training_effect_label,
                "workout_vo2max": round(w.vo2max, 1) if w.vo2max is not None else None,
                "workout_relative_effort": round(w.relative_effort, 1) if w.relative_effort is not None else None,
                "workout_rpe": int(round(w.session_rpe)) if w.session_rpe is not None else None,
                "workout_session_rpe_load": round(w.session_rpe_load, 1) if w.session_rpe_load is not None else None,
                "workout_rpe_load_vs_baseline": round(w.session_rpe_load_vs_28d_percent, 1) if w.session_rpe_load_vs_28d_percent is not None else None,
                "workout_fitness_aerobic_load": round(w.fitness_aerobic_load, 1) if w.fitness_aerobic_load is not None else None,
                "workout_fitness_high_intensity_load": round(w.fitness_high_intensity_load, 1) if w.fitness_high_intensity_load is not None else None,
                "workout_strength_sets": round(w.strength_total_sets) if w.strength_total_sets is not None else None,
                "workout_estimated_1rm": round(w.strength_best_estimated_1rm_kg, 1) if w.strength_best_estimated_1rm_kg is not None else None,
                "workout_strength_progression": round(w.strength_progression_percent, 1) if w.strength_progression_percent is not None else None,
                "workout_kilojoules": round(w.kilojoules, 1) if w.kilojoules is not None else None,
                "workout_total_reps": round(w.total_reps) if w.total_reps is not None else None,
                "workout_exercise_count": round(w.exercise_count) if w.exercise_count is not None else None,
                "workout_volume": round(w.volume_kg, 1) if w.volume_kg is not None else None,
                "workout_device": w.device_name,
                "workout_gear": w.gear_name,
                "workout_sources": ", ".join(w.provider_domains or w.sources) if (w.provider_domains or w.sources) else w.source,
                "workout_banister_trimp": round(w.banister_trimp, 1) if w.banister_trimp is not None else None,
                "workout_trimp_per_hour": round(w.trimp_per_hour, 1) if w.trimp_per_hour is not None else None,
                "workout_mechanical_work": round(w.mechanical_work_kj, 1) if w.mechanical_work_kj is not None else None,
                "workout_aerobic_efficiency": round(w.aerobic_efficiency, 5) if w.aerobic_efficiency is not None else None,
                "workout_aerobic_decoupling": round(w.aerobic_decoupling_percent, 2) if w.aerobic_decoupling_percent is not None else None,
                "workout_hrr_10s": round(w.hrr_10s, 1) if w.hrr_10s is not None else None,
                "workout_hrr_30s": round(w.hrr_30s, 1) if w.hrr_30s is not None else None,
                "workout_hrr_60s": round(w.hrr_60s, 1) if w.hrr_60s is not None else None,
                "workout_hrr_120s": round(w.hrr_120s, 1) if w.hrr_120s is not None else None,
                "workout_time_moderate": round(w.time_moderate_s / 60, 1) if w.time_moderate_s is not None else None,
                "workout_time_vigorous": round(w.time_vigorous_s / 60, 1) if w.time_vigorous_s is not None else None,
                "workout_time_near_maximal": round(w.time_near_maximal_s / 60, 1) if w.time_near_maximal_s is not None else None,
                "workout_comparable_count": w.comparable_workout_count,
                "workout_efficiency_vs_baseline": round(w.efficiency_vs_baseline_percent, 1) if w.efficiency_vs_baseline_percent is not None else None,
                "workout_decoupling_vs_baseline": round(w.decoupling_vs_baseline_percent, 1) if w.decoupling_vs_baseline_percent is not None else None,
                "workout_hr_vs_baseline": round(w.avg_hr_vs_baseline_bpm, 1) if w.avg_hr_vs_baseline_bpm is not None else None,
                "workout_power_vs_baseline": round(w.avg_power_vs_baseline_percent, 1) if w.avg_power_vs_baseline_percent is not None else None,
                "workout_speed_vs_baseline": round(w.avg_speed_vs_baseline_percent, 1) if w.avg_speed_vs_baseline_percent is not None else None,
                "workout_trimp_vs_recent": round(w.trimp_vs_recent_mean_percent, 1) if w.trimp_vs_recent_mean_percent is not None else None,
                "workout_load_context": w.load_context,
                "workout_personal_context": w.personal_context_summary,
            }
            value = values.get(m)
            return self._meaningful_workout_value(m, value)

        # AI text is persisted state and is safe to expose during bootstrap.
        if m == "ai_general":
            return self.manager.ai_general_verdict or (
                "Updated" if self.manager.ai_general else None
            )
        if m == "ai_workout":
            return self.manager.ai_workout_verdict or (
                "Updated" if self.manager.ai_workout else None
            )

        # Evaluation/recovery summaries can scan provider registries and
        # longitudinal history. Never build them from an entity property while
        # Home Assistant is still bootstrapping.
        if not self.manager.post_start_ready:
            return None

        e = self.manager.evaluation()
        if m == "training_adaptation_status":
            result = _training_adaptation_evaluation(self.manager)
            return _localized_training_adaptation_status(self.manager._ai_language(), result["status"])

        workout_long_term = e.get("workout_long_term") or {}
        sleep_long_term = e.get("sleep_long_term") or {}
        recorder_long_term = e.get("recorder_long_term") or {}
        relationship = e.get("training_recovery_relationship") or {}
        latest_sleep = self.manager.latest_sleep()
        compact_map = {
            # Domain states use one stable physical quantity. Related longitudinal
            # calculations progressively populate attributes without changing the
            # state unit or meaning.
            # State is a Fitness-owned longitudinal calculation, not the
            # latest source sleep duration. Lower variability means greater
            # consistency; detailed 7d/28d context remains in attributes.
            "sleep_consistency": (
                sleep_long_term.get("sleep_midpoint_variability_28d_min")
                if sleep_long_term.get("sleep_midpoint_variability_28d_min") is not None
                else sleep_long_term.get("sleep_duration_variability_28d_min")
            ),
            # Never masquerade a one-night shortfall as a 7-day metric.
            # Until enough completed nights exist in the rolling history, the
            # 7-day deficit is unavailable rather than falling back to latest sleep.
            "sleep_deficit_7d": sleep_long_term.get("sleep_deficit_7d_min"),
            # These Evaluation states are deltas/trends calculated by Fitness.
            # Current raw HRV/VO2 values remain owned by their source entities
            # and are routed directly to the dashboard.
            "autonomic_recovery_trend": (
                sleep_long_term.get("sleep_hrv_7d_vs_baseline_percent")
                if sleep_long_term.get("sleep_hrv_7d_vs_baseline_percent") is not None
                else sleep_long_term.get("sleep_hrv_latest_vs_28d_percent")
            ),
            "cardiorespiratory_fitness_trend": (
                recorder_long_term.get("vo2max_slope_percent_per_30d")
                if recorder_long_term.get("vo2max_slope_percent_per_30d") is not None
                else recorder_long_term.get("vo2max_trend_14_vs_previous_14_percent")
            ),
            "training_load": (
                workout_long_term.get("training_duration_7d_min")
                if workout_long_term.get("training_duration_7d_min") is not None
                else workout_long_term.get("training_duration_28d_min")
            ),
            # State is change versus the personal 90-day HRR baseline; the
            # latest raw HRR remains source-owned / workout-context evidence.
            "heart_rate_recovery": (
                workout_long_term.get("hrr_60s_latest_vs_90d_bpm")
                if workout_long_term.get("hrr_60s_latest_vs_90d_bpm") is not None
                else workout_long_term.get("hrr_120s_latest_vs_90d_bpm")
            ),
            "training_recovery_relationship": relationship.get("primary_correlation"),
        }
        if m in compact_map:
            return compact_map[m]

        value = e.get(m)
        if isinstance(value, float):
            return round(value, 2)
        return value

    def _evaluation_data_used(self, metric: str, evaluation: dict) -> list[str]:
        """Return exact source entities/profile values used by an Evaluation domain."""
        items: list[str] = []
        seen: set[str] = set()

        def add_entity(entity_id: str | None):
            if not entity_id or entity_id in seen:
                return
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unknown", "unavailable", "", None):
                return
            unit = state.attributes.get("unit_of_measurement")
            text = f"{entity_id} = {state.state}" + (f" {unit}" if unit else "")
            items.append(text)
            seen.add(entity_id)

        def add_profile(label: str, value, unit: str | None = None):
            if value is None:
                return
            text = f"{label} = {value}" + (f" {unit}" if unit else "")
            if text not in seen:
                items.append(text)
                seen.add(text)

        provider = collect_provider_metrics(self.hass, self.manager.config)
        latest_sleep = self.manager.latest_sleep()
        latest_workout = self.manager.latest_workout()
        statistics = self.manager.long_term_statistics

        if metric in {"cardiorespiratory_fitness_trend", "vo2max_percent_predicted"}:
            summary = statistics.get("vo2max") or {}
            add_entity(summary.get("entity_id") if isinstance(summary, dict) else None)
            add_entity(provider.get("vo2max_entity"))
            configured = self.manager.config.get("vo2max")
            if isinstance(configured, str) and configured.startswith(("sensor.", "input_number.")):
                add_entity(configured)
            if metric == "vo2max_percent_predicted":
                add_profile("profile.age", evaluation.get("age"), "years")
                add_profile("profile.sex", self.manager.config.get("sex"))
                weight = self.manager.config.get("weight")
                if isinstance(weight, str) and weight.startswith(("sensor.", "input_number.")):
                    add_entity(weight)
                else:
                    add_profile("profile.weight", evaluation.get("weight"), "kg")

        if metric == "autonomic_recovery_trend":
            summary = statistics.get("resting_hr") or {}
            add_entity(summary.get("entity_id") if isinstance(summary, dict) else None)
            add_entity(provider.get("resting_hr_entity"))
            if latest_sleep:
                add_entity((latest_sleep.field_sources or {}).get("hrv_ms"))

        if metric == "sleep_deficit_7d":
            # This metric is calculated from Fitness-owned canonical nightly
            # history, not from whichever provider happens to represent the
            # latest sleep right now. Expose the exact nights that entered the
            # calculation so provider syncs cannot make attribution misleading.
            for item in (evaluation.get("sleep_long_term") or {}).get("sleep_deficit_nightly_series") or []:
                if not isinstance(item, dict):
                    continue
                date = item.get("date")
                minutes = item.get("sleep_minutes")
                if date is not None and minutes is not None:
                    add_profile(str(date), minutes, "min")

        if metric == "sleep_consistency":
            # Consistency is longitudinal. Attribute it to the canonical Fitness
            # history summary rather than only to the most recently synced raw
            # provider entities.
            sleep_summary = evaluation.get("sleep_long_term") or {}
            add_profile("Fitness canonical sleep nights (7d)", sleep_summary.get("nights_7d"))
            add_profile("Fitness canonical sleep nights (28d)", sleep_summary.get("nights_28d"))

        if metric in {"training_load", "heart_rate_recovery", "training_recovery_relationship"}:
            if latest_workout:
                for source in latest_workout.sources or []:
                    add_entity(source)
                for source in (latest_workout.field_sources or {}).values():
                    add_entity(source)
            if metric == "training_load":
                for key, label, unit in (("resting_hr", "profile.resting_hr", "bpm"), ("max_hr", "profile.maximum_hr", "bpm")):
                    configured = self.manager.config.get(key)
                    if isinstance(configured, str) and configured.startswith(("sensor.", "input_number.")):
                        add_entity(configured)
                    else:
                        add_profile(label, evaluation.get(key), unit)
            if metric == "training_recovery_relationship" and latest_sleep:
                for source in latest_sleep.sources or []:
                    if isinstance(source, str) and source.startswith(("sensor.", "binary_sensor.", "event.")):
                        add_entity(source)
                for source in (latest_sleep.field_sources or {}).values():
                    add_entity(source)

        return items[:12]

    def _live_input_value(self, metric: str) -> str | None:
        info = self.manager.live_source_info(metric)
        entity_id = info.get("source_entity")
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return entity_id
        unit = state.attributes.get("unit_of_measurement")
        value = state.state
        return f"{entity_id} = {value}{(' ' + str(unit)) if unit else ''}"

    def _live_calculation_data_used(self, metric: str) -> list[str]:
        """Return compact exact inputs for a Fitness-calculated live metric."""
        ctx = self.manager._session_profile_context or {}
        session_stats = self.manager.live_session_statistics()
        items: list[str] = []

        def source(name: str):
            value = self._live_input_value(name)
            if value and value not in items:
                items.append(value)

        def profile(label: str, key: str, unit: str = ""):
            value = ctx.get(key)
            if value is not None:
                text = f"{label} = {value}{(' ' + unit) if unit else ''}"
                if text not in items:
                    items.append(text)

        if metric in {"heart_rate_percent_max", "heart_rate_reserve_percent",
                      "heart_rate_intensity", "heart_rate_relative_threshold"}:
            source(METRIC_HEART_RATE)
        if metric in {"heart_rate_percent_max", "heart_rate_reserve_percent",
                      "heart_rate_intensity", "live_time_moderate",
                      "live_time_vigorous", "live_time_near_maximal",
                      "live_banister_trimp"}:
            profile("maximum HR", "max_hr", "bpm")
        if metric in {"heart_rate_reserve_percent", "heart_rate_intensity",
                      "live_time_moderate", "live_time_vigorous",
                      "live_time_near_maximal", "live_banister_trimp"}:
            profile("resting HR", "resting_hr", "bpm")
        if metric == "heart_rate_relative_threshold":
            profile("threshold HR", "threshold_hr", "bpm")

        if metric in {"current_power_to_weight", "power_relative_threshold"}:
            source(METRIC_POWER)
        if metric == "current_power_to_weight":
            profile("body mass", "weight", "kg")
        if metric == "power_relative_threshold":
            profile("threshold power", "threshold_power", "W")

        if metric in {"current_pace", "speed_relative_threshold"}:
            source(METRIC_SPEED)
        if metric == "speed_relative_threshold":
            profile("threshold pace", "threshold_pace", "min/km")

        if metric in {"live_average_hr", "live_maximum_hr", "live_banister_trimp",
                      "live_aerobic_efficiency", "live_aerobic_decoupling",
                      "live_time_moderate", "live_time_vigorous",
                      "live_time_near_maximal"}:
            source(METRIC_HEART_RATE)
        if metric in {"live_average_power", "live_maximum_power",
                      "live_mechanical_work", "live_aerobic_efficiency",
                      "live_aerobic_decoupling"}:
            source(METRIC_POWER)
        if metric in {"live_average_cadence"}:
            source(METRIC_CADENCE)
        if metric in {"live_average_speed", "live_aerobic_efficiency",
                      "live_aerobic_decoupling"}:
            source(METRIC_SPEED)

        if metric == "live_banister_trimp":
            items.append(f"session duration = {round(self.manager.session_duration()/60, 2)} min")
            avg = session_stats.get("average_hr")
            if avg is not None:
                items.append(f"session mean HR = {round(avg, 2)} bpm")
            sex = self.manager.config.get("sex")
            if sex:
                items.append(f"sex = {sex}")
        elif metric == "session_duration":
            items.append("Fitness workout start timestamp")
        elif metric.startswith("live_"):
            items.append(f"valid session samples = {len(self.manager.samples)}")

        return items[:10]

    @property
    def extra_state_attributes(self):
        """Return intentionally small attributes.

        Raw Live/Workout/Sleep entities expose provenance only. Methodology,
        explanations and scientific references are reserved for Fitness-owned
        Evaluation outputs, keeping high-frequency state rows small and avoiding
        duplicated provider diagnostics in Recorder.
        """
        m = self.entity_description.metric
        kind = self.entity_description.kind

        if self.entity_description.key in DATA_MAP_KEYS:
            return dict(self._data_map_attributes)

        if kind == "live":
            source_metric = {
                "heart_rate_percent_max": METRIC_HEART_RATE,
                "heart_rate_reserve_percent": METRIC_HEART_RATE,
                "heart_rate_intensity": METRIC_HEART_RATE,
                "heart_rate_relative_threshold": METRIC_HEART_RATE,
                "current_power_to_weight": METRIC_POWER,
                "power_relative_threshold": METRIC_POWER,
                "current_pace": METRIC_SPEED,
                "speed_relative_threshold": METRIC_SPEED,
            }.get(m, m)
            info = self.manager.live_source_info(source_metric)
            attrs = {
                key: info.get(key)
                for key in (
                    "source_entity",
                    "source_device_name",
                    "source_integration",
                )
                if info.get(key) is not None
            }
            if m in CALCULATED_LIVE_METRICS:
                attrs.update(live_user_details(
                    self.manager._ai_language(),
                    m,
                    self._live_calculation_data_used(m),
                ))
            return attrs

        if kind == "workout":
            workout = self.manager.latest_workout()
            if workout is None:
                return {}
            attrs = {}
            sources = workout.provider_domains or workout.sources
            if sources:
                attrs["sources"] = list(dict.fromkeys(
                    self._provider_display_name(source) for source in sources
                ))
            if workout.start:
                attrs["workout_start"] = workout.start
            from .providers.workouts import workout_sport_kind
            if (sport := workout_sport_kind(workout)):
                attrs["sport"] = sport
            field_source = (workout.field_sources or {}).get(m.removeprefix("workout_"))
            if field_source:
                attrs["field_source"] = self._provider_display_name(field_source)
            if m in {"workout_rpe", "workout_session_rpe_load", "workout_rpe_load_vs_baseline"}:
                rpe_meta = (workout.extra or {}).get("fitness_rpe") if isinstance(workout.extra, dict) else None
                if isinstance(rpe_meta, dict):
                    attrs["rpe_source"] = rpe_meta.get("active_source")
                    attrs["rpe_provider"] = rpe_meta.get("provider")
                    attrs["rpe_provider_capability"] = rpe_meta.get("provider_capability")
                    if rpe_meta.get("provider_base_rpe") is not None:
                        attrs["provider_base_rpe"] = rpe_meta.get("provider_base_rpe")
                    if rpe_meta.get("user_override_rpe") is not None:
                        attrs["user_override_rpe"] = rpe_meta.get("user_override_rpe")
            if m == "workout_hr_vs_baseline" and workout.avg_hr is not None and workout.avg_hr_vs_baseline_bpm is not None:
                attrs["current_average_hr_bpm"] = round(float(workout.avg_hr), 1)
                attrs["personal_baseline_average_hr_bpm"] = round(
                    float(workout.avg_hr) - float(workout.avg_hr_vs_baseline_bpm), 1
                )
                attrs["absolute_deviation_bpm"] = round(abs(float(workout.avg_hr_vs_baseline_bpm)), 1)
            return attrs

        if kind == "sleep":
            if m in {"readiness", "estimated_recovery_time"} and not self.manager.post_start_ready:
                return {}
            if m == "estimated_recovery_time":
                recovery = self.manager.recovery_time_evaluation()
                attrs = {key: value for key, value in recovery.items() if key != "remaining_hours" and value is not None}
                if recovery.get("level"):
                    attrs["level_display"] = _localized_recovery_time_level(self.manager._ai_language(), recovery["level"])
                return attrs
            if m == "readiness":
                readiness = self.manager.readiness_evaluation()
                attrs = _localized_readiness_attributes(self.manager._ai_language(), readiness)
                attrs.pop("score", None)
                details = evaluation_user_details(
                    self.manager._ai_language(),
                    "readiness",
                    {
                        "score": readiness.get("score"),
                        "level": readiness.get("level"),
                        "confidence_percent": readiness.get("confidence_percent"),
                        "available_components": readiness.get("available_components"),
                        "components": readiness.get("components"),
                        "data_source": readiness.get("data_source"),
                    },
                )
                attrs.update(details)
                return attrs
            sleep = self.manager.latest_sleep()
            if sleep is None:
                return {}
            attrs = {}
            source_names = self._sleep_source_names(sleep)
            if source_names:
                attrs["sources"] = list(dict.fromkeys(source_names))
            if sleep.start:
                attrs["sleep_start"] = sleep.start
            if sleep.end:
                attrs["sleep_end"] = sleep.end
            field_name = {
                "sleep_duration": "duration_s",
                "sleep_time_in_bed": "time_in_bed_s",
                "sleep_awake": "awake_s",
                "sleep_light": "light_sleep_s",
                "sleep_deep": "deep_sleep_s",
                "sleep_rem": "rem_sleep_s",
                "sleep_hrv": "hrv_ms",
                "sleep_average_hr": "average_hr",
                "sleep_respiratory_rate": "respiratory_rate",
                "sleep_spo2": "spo2_percent",
                "sleep_score": "score",
                "sleep_efficiency": "efficiency_percent",
            }.get(m)
            field_source = (sleep.field_sources or {}).get(field_name) if field_name else None
            if field_source:
                attrs["field_source"] = field_source
            if m == "sleep_score" and field_source == "fitness_calculated":
                attrs["calculated_by_fitness"] = True
                attrs["calculation_type"] = "wellness_heuristic"
                attrs["medical_interpretation"] = False
            if m in {"workout_strength_sets", "workout_estimated_1rm", "workout_strength_progression"}:
                details = (w.extra or {}).get("fitness_strength") if isinstance(w.extra, dict) else None
                if isinstance(details, dict):
                    attrs["strength_analysis"] = details
                    attrs["method"] = details.get("method")
                    attrs["estimated_1rm_formula"] = details.get("estimated_1rm_formula")
            return attrs

        # Evaluation attributes are deliberately transparent: these are Fitness
        # calculations/interpretations rather than measurements from another device.
        # During HA bootstrap, persisted AI attributes are safe but scientific
        # evaluation must wait for post-start initialization.
        if not self.manager.post_start_ready and m not in ("ai_general", "ai_workout"):
            return {}
        # Evaluation domains expose concrete evidence, not generic boilerplate.
        # Formula/provenance metadata is retained only for metrics where there is
        # one specific deterministic calculation to explain.
        grouped_metrics = {
            "sleep_consistency", "sleep_deficit_7d", "autonomic_recovery_trend",
            "cardiorespiratory_fitness_trend", "training_load",
            "heart_rate_recovery", "training_recovery_relationship",
            "training_adaptation_status",
        }
        scientific_metrics = grouped_metrics | {"vo2max_percent_predicted"}
        if m in scientific_metrics:
            # Scientific Evaluation entities expose only user-facing evidence:
            # calculation-specific values, study citation, formula, exact data
            # used, and concise localized interpretation. Legacy developer
            # metadata (method/calculation/inputs/value_origin/etc.) stays internal.
            attrs = {}
        elif m in ("ai_general", "ai_workout"):
            attrs = {}
        else:
            attrs = sensor_explanation(
                self.manager._ai_language(), "evaluation", m,
            )
            attrs.update(self.manager.localized_evaluation_provenance(m))

        e = self.manager.evaluation()
        workout = e.get("workout_long_term") or {}
        sleep = e.get("sleep_long_term") or {}
        recorder = e.get("recorder_long_term") or {}
        relation = e.get("training_recovery_relationship") or {}

        grouped = {
            "sleep_consistency": {
                "samples_7d": sleep.get("nights_7d"),
                "samples_28d": sleep.get("nights_28d"),
                "average_duration_7d_min": sleep.get("sleep_duration_7d_mean_min"),
                "average_duration_28d_min": sleep.get("sleep_duration_28d_mean_min"),
                "duration_variability_28d_min": sleep.get("sleep_duration_variability_28d_min"),
                "bedtime_variability_28d_min": sleep.get("bedtime_variability_28d_min"),
                "wake_time_variability_28d_min": sleep.get("wake_time_variability_28d_min"),
                "midpoint_variability_28d_min": sleep.get("sleep_midpoint_variability_28d_min"),
                "nights_below_7h_7d": sleep.get("nights_below_7h_7d"),
                "nights_below_7h_28d": sleep.get("nights_below_7h_28d"),
                "nights_below_7h_28d_percent": sleep.get("nights_below_7h_28d_percent"),
            },
            "sleep_deficit_7d": {
                "nights_observed": sleep.get("nights_7d"),
                "nights_below_7h": sleep.get("nights_below_7h_7d"),
                "reference_minimum_hours": 7,
                "average_sleep_minutes": sleep.get("sleep_duration_7d_mean_min"),
                "nightly_deficit_series": sleep.get("sleep_deficit_nightly_series") or [],
                "unique_nights": sleep.get("history_unique_nights"),
                "duplicate_nightly_records_ignored": sleep.get("history_duplicate_nightly_records_ignored"),
                "window_days": 7,
                "minimum_nights_required": 5,
                "excess_sleep_offsets_shortfall": False,
            },
            "autonomic_recovery_trend": {
                "sleep_hrv_7d_mean_ms": sleep.get("sleep_hrv_7d_mean_ms"),
                "sleep_hrv_28d_mean_ms": sleep.get("sleep_hrv_28d_mean_ms"),
                "sleep_hrv_baseline_28d_mean_ms": sleep.get("sleep_hrv_baseline_28d_mean_ms"),
                "sleep_hrv_baseline_nights": sleep.get("sleep_hrv_baseline_nights"),
                "sleep_hrv_latest_vs_28d_percent": sleep.get("sleep_hrv_latest_vs_28d_percent"),
                "sleep_hrv_7d_vs_baseline_percent": sleep.get("sleep_hrv_7d_vs_baseline_percent"),
                "sleep_hrv_vs_28d_percent": sleep.get("sleep_hrv_vs_28d_percent"),
                "resting_hr_current_bpm": recorder.get("resting_hr_current"),
                "resting_hr_7d_mean_bpm": recorder.get("resting_hr_7d_mean"),
                "resting_hr_28d_mean_bpm": recorder.get("resting_hr_28d_mean"),
                "resting_hr_vs_28d_bpm": recorder.get("resting_hr_vs_28d"),
            },
            "cardiorespiratory_fitness_trend": {
                "current_vo2max_ml_kg_min": recorder.get("vo2max_current"),
                "vo2max_28d_mean_ml_kg_min": recorder.get("vo2max_28d_mean"),
                "vo2max_90d_mean_ml_kg_min": recorder.get("vo2max_90d_mean"),
                "short_term_change_percent": recorder.get("vo2max_trend_14_vs_previous_14_percent"),
                "slope_percent_per_30d": recorder.get("vo2max_slope_percent_per_30d"),
                "percent_predicted": e.get("vo2max_percent_predicted"),
                "days_28d": recorder.get("vo2max_days_28d"),
                "days_90d": recorder.get("vo2max_days_90d"),
                # Recorder statistics rows contain many fields and can easily
                # exceed HA's 16 KiB state-attribute limit. The dashboard needs
                # only date/start + value, so expose a compact max-90-day series.
                "daily_series": [
                    {
                        "start": item.get("start") or item.get("date"),
                        "value": item.get("value")
                        if item.get("value") is not None
                        else item.get("mean"),
                    }
                    for item in (recorder.get("vo2max_daily") or [])[-90:]
                    if isinstance(item, dict)
                    and (
                        item.get("value") is not None
                        or item.get("mean") is not None
                    )
                ],
                "minimum_days_28d": 21,
                "minimum_days_90d": 60,
            },
            "training_load": {
                "trimp_7d": workout.get("banister_trimp_7d"),
                "trimp_28d": workout.get("banister_trimp_28d"),
                "trimp_28d_weekly_equivalent": workout.get("banister_trimp_28d_weekly_equivalent"),
                "workouts_7d": workout.get("workouts_7d"),
                "workouts_28d": workout.get("workouts_28d"),
                "active_days_7d": workout.get("active_training_days_7d"),
                "active_days_28d": workout.get("active_training_days_28d"),
                "training_duration_7d_min": workout.get("training_duration_7d_min"),
                "training_duration_28d_min": workout.get("training_duration_28d_min"),
                "distance_7d_km": workout.get("distance_7d_km"),
                "distance_28d_km": workout.get("distance_28d_km"),
                "last_recovery_interval_h": workout.get("last_recovery_interval_h"),
                "median_recovery_interval_28d_h": workout.get("median_recovery_interval_28d_h"),
            },
            "heart_rate_recovery": {
                "hrr_30s_bpm": workout.get("latest_hrr_30s"),
                "hrr_60s_bpm": workout.get("latest_hrr_60s"),
                "hrr_120s_bpm": workout.get("latest_hrr_120s"),
                "hrr_120s_personal_90d_baseline_bpm": workout.get("hrr_120s_baseline_90d"),
                "hrr_120s_latest_vs_baseline_bpm": workout.get("hrr_120s_latest_vs_90d_bpm"),
                "hrr_120s_samples_90d": workout.get("hrr_120s_samples_90d"),
                "personal_90d_baseline_bpm": workout.get("hrr_60s_baseline_90d"),
                "latest_vs_baseline_bpm": workout.get("hrr_60s_latest_vs_90d_bpm"),
                "samples_90d": workout.get("hrr_samples_90d"),
            },
            "training_recovery_relationship": {
                **relation,
                "causal_interpretation": False,
            },
            "training_adaptation_status": {
                **_training_adaptation_evaluation(self.manager),
                "causal_interpretation": False,
                "diagnostic_interpretation": False,
            },
            "vo2max_percent_predicted": {
            },
        }.get(m)
        if grouped:
            attrs.update({k: v for k, v in grouped.items() if v is not None})

        if m in scientific_metrics:
            attrs.update(
                evaluation_user_details(
                    self.manager._ai_language(),
                    m,
                    self._evaluation_data_used(m, e),
                )
            )

        if m in ("ai_general", "ai_workout"):
            full_text = self.manager.ai_general if m == "ai_general" else self.manager.ai_workout
            ai_entity = self.manager.config.get("ai_entity") or "preferred_default"
            if ai_entity == "__home_assistant_default__":
                ai_entity = "preferred_default"
            attrs.update({
                "text": full_text,
                "generated_at": self.manager.ai_last_generated,
                "ai_entity": ai_entity,
                "role": "interpretation_only",
            })
        return attrs

