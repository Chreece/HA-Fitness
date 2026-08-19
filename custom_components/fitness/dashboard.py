"""Frontend dashboard support for Fitness."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from aiohttp import web
import voluptuous as vol
import voluptuous_serialize

from homeassistant import data_entry_flow

from homeassistant.components import frontend, websocket_api
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.components.lovelace import dashboard as lovelace_dashboard
from homeassistant.components.lovelace.const import (
    CONF_ICON,
    CONF_REQUIRE_ADMIN,
    CONF_SHOW_IN_SIDEBAR,
    CONF_TITLE,
    CONF_URL_PATH,
    LOVELACE_DATA,
    MODE_STORAGE,
)
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.const import CAST_APP_ID_HOMEASSISTANT_LOVELACE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.setup import async_when_setup

from .access_control import (
    async_register_fitness_access_websocket_commands,
    get_fitness_access_controller,
)
from .const import (
    CONF_LANGUAGE,
    CONF_HEIGHT,
    CONF_WEIGHT_SCALE_ENTITY,
    CONF_PROFILE_NAME,
    CONF_WORKOUT_DEVICE_IDS,
    CONF_TV_DASHBOARD_ENABLED,
    CONF_TV_MEDIA_PLAYER_ID,
    CONF_TV_DUCKING_PERCENT,
    CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
    CONF_TV_YTDLP_ENABLED,
    CONF_DASHBOARD_THEME,
    CONF_DASHBOARD_MODULES,
    CONF_DASHBOARD_RSS_ENTITY_IDS,
    CONF_DASHBOARD_MUSIC_ENTITY_IDS,
    CONF_DASHBOARD_LIGHT_ENTITY_IDS,
    CONF_DASHBOARD_VIDEO_ENTITY_IDS,
    CONF_DASHBOARD_WEATHER_ENTITY_ID,
    CONF_TTS_ENTITY_ID,
    CONF_TTS_MEDIA_PLAYER_IDS,
    DEFAULT_DASHBOARD_MODULES,
    DEFAULT_TV_DUCKING_PERCENT,
    DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
    TV_DASHBOARD_PATH,
    DOMAIN,
)
from .dashboard_translations import (
    DASHBOARD_LANGUAGE_AUDIT_TEXT,
    SUPPORTED_DASHBOARD_LANGUAGES,
)
from .feedback import INTENSITY_RGB
from .live import get_live_runtime
from .profile_data import (
    DATA_MAP_KIND_TO_KEY,
    LIVE_RAW_ROUTE_KEYS,
    physical_metric_entity_id,
    physical_workout_owner_entity_id,
    routes_from_attributes,
)
from .resource_safety import async_call_service, bounded_websocket_payload
from .providers.workouts import (
    FITNESS_CALCULATED_SOURCE,
    FITNESS_FALLBACK_FACTUAL_FIELDS,
    FITNESS_LIVE_SOURCE,
    SOURCE_RECONSTRUCTED_SOURCE,
    _FIELD_KEYS,
    fitness_owned_workout_value,
    workout_is_fitness_owned,
    workout_sport_kind,
)
from .tv_dashboard import (
    DEFAULT_TV_OLED_PROTECTION,
    DEFAULT_TV_SCALE_PERCENT,
    async_register_tv_websocket_commands,
    get_tv_dashboard_hub,
)

_LOGGER = logging.getLogger(__name__)

_LEGACY_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"
_LEGACY_CAST_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard-cast.js"
_RESOURCE_PREFIX = "/fitness/frontend/fitness-dashboard-"
_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"
_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-85"
_SETUP_KEY = "_dashboard_frontend_setup"
_RECONCILE_TASK_KEY = "_dashboard_reconcile_task"
_TV_DASHBOARD_CARD_TYPE = "custom:fitness-tv-dashboard-card"
_TV_SETUP_CARD_TYPE = "custom:fitness-tv-setup-card"
_TV_OVERVIEW_CAST_STATE_KEY = "_tv_overview_cast_state"

class FitnessDashboardResourceView(HomeAssistantView):
    """Serve the Fitness dashboard module with cross-origin access for Cast.

    Home Assistant Cast runs on ``cast.home-assistant.io`` and loads Lovelace
    custom-card resources cross-origin from the user's HA instance. Let Home
    Assistant's HTTP layer own the CORS/preflight handling instead of adding an
    OPTIONS route ourselves; ``cors_allowed`` requests HA's allow-all CORS
    policy for this public JavaScript-only endpoint.
    """

    url = _RESOURCE_NAMESPACE
    name = "api:fitness:dashboard-resource"
    requires_auth = False
    cors_allowed = True

    def __init__(self, frontend_file: Path) -> None:
        self._frontend_file = frontend_file
        self._frontend_body: bytes | None = None
        self._read_lock = asyncio.Lock()

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "Cross-Origin-Resource-Policy": "cross-origin",
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        }

    async def get(self, request: web.Request) -> web.Response:
        """Return the bundled dashboard module."""
        _LOGGER.debug(
            "Serving Fitness dashboard frontend resource to origin=%s",
            request.headers.get("Origin", "same-origin"),
        )
        if self._frontend_body is None:
            async with self._read_lock:
                if self._frontend_body is None:
                    self._frontend_body = await asyncio.to_thread(self._frontend_file.read_bytes)
        body = self._frontend_body
        return web.Response(
            body=body,
            content_type="application/javascript",
            charset="utf-8",
            headers=self._headers(),
        )


_PACE_TEXT: dict[str, str] = {
    "en": "Pace", "el": "Ρυθμός", "de": "Tempo", "fr": "Allure",
    "es": "Ritmo", "it": "Passo", "pt": "Ritmo", "nl": "Tempo",
    "pl": "Tempo", "ru": "Темп", "uk": "Темп", "tr": "Tempo",
    "zh": "配速", "ja": "ペース", "ko": "페이스",
}

# Factual completed-workout metrics are routed to the integration that actually
# owns each field. Pure provider workouts stay on Garmin/Strava/Hevy/etc. A
# workout created by Fitness Live remains Fitness-owned after provider merging,
# and fields captured by Fitness may route to Fitness's own workout entities.
# Provider-enriched fields still route directly to the provider, never mirrors.
_WORKOUT_SOURCE_FIELDS: dict[str, tuple[str, str | None]] = {
    "last_workout": ("name", None),
    "last_workout_duration": ("duration_s", "min"),
    "last_workout_distance": ("distance_m", "km"),
    "last_workout_avg_hr": ("avg_hr", "bpm"),
    "last_workout_max_hr": ("max_hr", "bpm"),
    "last_workout_avg_power": ("avg_power", "W"),
    "last_workout_max_power": ("max_power", "W"),
    "last_workout_avg_cadence": ("avg_cadence", "1/min"),
    "last_workout_elevation_gain": ("elevation_gain_m", "m"),
    "last_workout_calories": ("calories", "kcal"),
    "last_workout_moving_time": ("moving_time_s", "min"),
    "last_workout_elapsed_time": ("elapsed_time_s", "min"),
    "last_workout_average_speed": ("average_speed_m_s", "km/h"),
    "last_workout_max_speed": ("max_speed_m_s", "km/h"),
    "last_workout_weighted_power": ("weighted_power", "W"),
    "last_workout_max_cadence": ("max_cadence", "1/min"),
    "last_workout_elevation_loss": ("elevation_loss_m", "m"),
    "last_workout_training_load": ("training_load", None),
    "last_workout_aerobic_effect": ("aerobic_training_effect", None),
    "last_workout_anaerobic_effect": ("anaerobic_training_effect", None),
    "last_workout_training_effect": ("training_effect_label", None),
    "last_workout_vo2max": ("vo2max", "mL/kg/min"),
    "last_workout_rpe": ("session_rpe", None),
    "last_workout_relative_effort": ("relative_effort", None),
    "last_workout_kilojoules": ("kilojoules", "kJ"),
    "last_workout_total_reps": ("total_reps", None),
    "last_workout_exercise_count": ("exercise_count", None),
    "last_workout_volume": ("volume_kg", "kg"),
    "last_workout_device": ("device_name", None),
    "last_workout_gear": ("gear_name", None),
}

_WORKOUT_STATE_TOKENS: dict[str, tuple[tuple[str, ...], ...]] = {
    "name": (("last", "workout"), ("last", "activity"), ("workout", "title")),
    "duration_s": (("duration",),),
    "distance_m": (("distance",),),
    "avg_hr": (("heart", "rate", "average"), ("average", "heart", "rate"), ("avg", "hr")),
    "max_hr": (("heart", "rate", "max"), ("max", "heart", "rate"), ("max", "hr")),
    "avg_power": (("power", "average"), ("average", "power"), ("avg", "power")),
    "max_power": (("power", "max"), ("max", "power")),
    "weighted_power": (("weighted", "power"), ("normalized", "power")),
    "avg_cadence": (("cadence", "average"), ("average", "cadence"), ("avg", "cadence")),
    "max_cadence": (("cadence", "max"), ("max", "cadence")),
    "elevation_gain_m": (("elevation", "gain"),),
    "elevation_loss_m": (("elevation", "loss"),),
    "calories": (("calories",),),
    "moving_time_s": (("moving", "time"),),
    "elapsed_time_s": (("elapsed", "time"),),
    "average_speed_m_s": (("speed", "average"), ("average", "speed"), ("avg", "speed")),
    "max_speed_m_s": (("speed", "max"), ("max", "speed")),
    "training_load": (("training", "load"),),
    "aerobic_training_effect": (("aerobic", "effect"),),
    "anaerobic_training_effect": (("anaerobic", "effect"),),
    "vo2max": (("vo2", "max"), ("vo2max",)),
    "relative_effort": (("relative", "effort"),),
    "kilojoules": (("kilojoule",), ("kj",)),
    "total_reps": (("total", "reps"), ("reps",)),
    "exercise_count": (("exercise", "count"),),
    "volume_kg": (("volume",),),
    "device_name": (("device",),),
    "gear_name": (("gear",),),
}

# Latest-sleep facts are source-owned exactly like completed-workout facts.
# The canonical value is retained only as a dashboard fallback for providers
# whose source entity is an event/history carrier rather than a numeric sensor.
_SLEEP_SOURCE_FIELDS: dict[str, tuple[str, str | None]] = {
    "last_sleep_duration": ("duration_s", "min"),
    "last_sleep_score": ("score", None),
    "last_sleep_efficiency": ("efficiency_percent", "%"),
    "last_sleep_time_in_bed": ("time_in_bed_s", "min"),
    "last_sleep_awake": ("awake_s", "min"),
    "last_sleep_light": ("light_sleep_s", "min"),
    "last_sleep_deep": ("deep_sleep_s", "min"),
    "last_sleep_rem": ("rem_sleep_s", "min"),
    "last_sleep_hrv": ("hrv_ms", "ms"),
    "last_sleep_average_hr": ("average_hr", "bpm"),
    "last_sleep_respiratory_rate": ("respiratory_rate", "1/min"),
    "last_sleep_spo2": ("spo2_percent", "%"),
    "last_sleep_recovery_score": ("recovery_score", None),
    "last_sleep_readiness_score": ("readiness_score", None),
}

# Current provider/profile inputs used by Evaluation cards. Fitness owns only
# the derived trend/delta entities; the dashboard reads these current values
# from the original HA entities when one exists.
_EVALUATION_SOURCE_FIELDS: dict[str, tuple[str, str | None]] = {
    "vo2max": ("vo2max", "mL/kg/min"),
    "resting_hr": ("resting_hr", "bpm"),
    "hrv_last_night": ("hrv_last_night", "ms"),
    "hrv_weekly": ("hrv_weekly", "ms"),
    "weight": ("weight_kg", "kg"),
    "training_readiness": ("training_readiness", None),
    "provider_sleep_score": ("sleep_score", None),
}

_DASHBOARD_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "dashboard": "Fitness dashboard",
        "description": "Workouts, sleep, recovery and fitness progress in one adaptive dashboard.",
        "overview": "Overview",
        "progress": "Progress",
        "workouts": "Workouts",
        "recovery": "Recovery & sleep",
        "live": "Live workout",
        "current": "Current workout",
        "latest_workout": "Latest workout",
        "latest_sleep": "Latest sleep",
        "evaluation": "Evaluation",
        "fitness_progress": "Fitness progress",
        "recovery_progress": "Recovery progress",
        "training_progress": "Training progress",
        "sleep_progress": "Sleep progress",
        "workout_metrics": "Workout metrics",
        "workout_comparison": "Compared with your baseline",
        "route": "Workout route",
        "no_route": "No GPS route is available for the latest workout.",
        "ai_summary": "AI evaluation",
        "controls": "Workout controls",
        "days_7": "7 days",
        "days_28": "28 days",
        "days_90": "90 days",
        "progress_snapshot": "Fitness progress",
        "current_vo2max": "Current VO₂max",
        "mean_28d": "28-day mean",
        "mean_90d": "90-day mean",
        "monthly_trend": "Trend / 30 days",
        "predicted_percent": "% of predicted",
        "recovery_snapshot": "Recovery snapshot",
        "recovery_limiting_factor": "Main recovery limiter",
        "limiter_muscular_recovery": "Muscular recovery",
        "limiter_autonomic_recovery": "Autonomic recovery",
        "limiter_sleep_recovery": "Sleep recovery",
        "limiter_overall_readiness": "Overall readiness",
        "limiter_workout_dose": "Workout demand",
        "recovery_readiness": "Recovery & readiness",
        "sleep_summary": "Sleep summary",
        "broader_recovery_window": "Broader physiological recovery window",
        "adaptation_evidence": "Evidence",
        "adaptation_baseline": "Load balance",
        "adaptation_fitness": "Fitness trend",
        "adaptation_recovery": "Recovery",
        "adaptation_building": "Building enough history for a reliable adaptation assessment",
        "next_workout": "Ready for next workout",
        "remaining": "Time remaining",
        "ready_at": "Ready around",
        "recovery_window": "Estimated recovery window",
        "recovery_progress_label": "Recovery progress",
        "recovery_signals_label": "Recovery signals",
        "physio_note": "Available physiological markers may recover at different rates.",
        "ready_now": "Ready for next workout",
        "confidence_short": "confidence",
        "hours_short": "h",
        "sleep_score": "Sleep score",
        "sleep_duration": "Sleep duration",
        "sleep_hrv": "Sleep HRV",
        "sleep_deficit": "7-day sleep deficit",
        "training_load_snapshot": "Training load",
        "load_ratio": "Load vs baseline",
        "baseline_building": "Building personal baseline",
        "baseline_building_hint": "More comparable workouts are needed before load balance can be judged reliably.",
        "load_low": "Low",
        "load_balanced": "Balanced",
        "load_elevated": "Elevated",
        "load_high": "High",
        "load_excessive": "Excessive",
        "training_adaptation_card": "Training adaptation",
        "training_adaptation_subtitle": "How recent training is affecting you",
        "adaptation_load_ratio": "Recent / baseline load",
        "adaptation_fitness_trend": "Fitness trend",
        "adaptation_recovery_signal": "Recovery signal",
        "recent_load": "7-day TRIMP",
        "baseline_load": "28-day weekly baseline",
        "workouts_7d": "Workouts / 7 days",
        "active_days_7d": "Active days / 7 days",
        "duration_7d": "Training / 7 days",
        "improving": "Improving",
        "stable": "Stable",
        "declining": "Declining"},
    "el": {
        "dashboard": "Πίνακας φυσικής κατάστασης",
        "description": "Προπονήσεις, ύπνος, αποκατάσταση και πρόοδος φυσικής κατάστασης σε έναν προσαρμοζόμενο πίνακα.",
        "overview": "Επισκόπηση",
        "progress": "Πρόοδος",
        "workouts": "Προπονήσεις",
        "recovery": "Αποκατάσταση & ύπνος",
        "live": "Ζωντανή προπόνηση",
        "current": "Τρέχουσα προπόνηση",
        "latest_workout": "Τελευταία προπόνηση",
        "latest_sleep": "Τελευταίος ύπνος",
        "evaluation": "Αξιολόγηση",
        "fitness_progress": "Πρόοδος φυσικής κατάστασης",
        "recovery_progress": "Πρόοδος αποκατάστασης",
        "training_progress": "Πρόοδος προπόνησης",
        "sleep_progress": "Πρόοδος ύπνου",
        "workout_metrics": "Μετρήσεις προπόνησης",
        "workout_comparison": "Σύγκριση με τη βάση σου",
        "route": "Διαδρομή προπόνησης",
        "no_route": "Δεν υπάρχουν διαθέσιμα δεδομένα GPS για την τελευταία προπόνηση.",
        "ai_summary": "Αξιολόγηση με AI",
        "controls": "Έλεγχος προπόνησης",
        "days_7": "7 ημέρες",
        "days_28": "28 ημέρες",
        "days_90": "90 ημέρες",
        "progress_snapshot": "Πρόοδος φυσικής κατάστασης",
        "current_vo2max": "Τρέχον VO₂max",
        "mean_28d": "Μέσος όρος 28 ημερών",
        "mean_90d": "Μέσος όρος 90 ημερών",
        "monthly_trend": "Τάση / 30 ημέρες",
        "predicted_percent": "% της προβλεπόμενης τιμής",
        "recovery_snapshot": "Εικόνα αποκατάστασης",
        "recovery_limiting_factor": "Κύριος περιοριστικός παράγοντας",
        "limiter_muscular_recovery": "Μυϊκή αποκατάσταση",
        "limiter_autonomic_recovery": "Αυτόνομη αποκατάσταση",
        "limiter_sleep_recovery": "Αποκατάσταση από τον ύπνο",
        "limiter_overall_readiness": "Συνολική ετοιμότητα",
        "limiter_workout_dose": "Επιβάρυνση προπόνησης",
        "recovery_readiness": "Αποκατάσταση & ετοιμότητα",
        "sleep_summary": "Σύνοψη ύπνου",
        "broader_recovery_window": "Ευρύτερο παράθυρο φυσιολογικής αποκατάστασης",
        "adaptation_evidence": "Δεδομένα",
        "adaptation_baseline": "Ισορροπία φορτίου",
        "adaptation_fitness": "Τάση φυσικής κατάστασης",
        "adaptation_recovery": "Αποκατάσταση",
        "adaptation_building": "Συλλέγεται αρκετό ιστορικό για αξιόπιστη αξιολόγηση προσαρμογής",
        "next_workout": "Έτοιμος για την επόμενη προπόνηση",
        "remaining": "Χρόνος που απομένει",
        "ready_at": "Έτοιμος περίπου στις",
        "recovery_window": "Εκτιμώμενο εύρος αποκατάστασης",
        "recovery_progress_label": "Πρόοδος αποκατάστασης",
        "recovery_signals_label": "Σήματα αποκατάστασης",
        "physio_note": "Οι διαθέσιμοι φυσιολογικοί δείκτες μπορεί να αποκαθίστανται με διαφορετικό ρυθμό.",
        "ready_now": "Έτοιμος για την επόμενη προπόνηση",
        "confidence_short": "βεβαιότητα",
        "hours_short": "ώ",
        "sleep_score": "Βαθμολογία ύπνου",
        "sleep_duration": "Διάρκεια ύπνου",
        "sleep_hrv": "HRV ύπνου",
        "sleep_deficit": "Έλλειμμα ύπνου 7 ημερών",
        "training_load_snapshot": "Προπονητικό φορτίο",
        "load_ratio": "Φορτίο έναντι βάσης",
        "baseline_building": "Δημιουργείται προσωπική βάση",
        "baseline_building_hint": "Χρειάζονται περισσότερες συγκρίσιμες προπονήσεις πριν αξιολογηθεί αξιόπιστα η ισορροπία φορτίου.",
        "load_low": "Χαμηλό",
        "load_balanced": "Ισορροπημένο",
        "load_elevated": "Αυξημένο",
        "load_high": "Υψηλό",
        "load_excessive": "Υπερβολικό",
        "training_adaptation_card": "Προσαρμογή προπόνησης",
        "training_adaptation_subtitle": "Πώς σε επηρεάζει η πρόσφατη προπόνηση",
        "adaptation_load_ratio": "Πρόσφατο / βασικό φορτίο",
        "adaptation_fitness_trend": "Τάση φυσικής κατάστασης",
        "adaptation_recovery_signal": "Σήμα αποκατάστασης",
        "recent_load": "TRIMP 7 ημερών",
        "baseline_load": "Εβδομαδιαία βάση 28 ημερών",
        "workouts_7d": "Προπονήσεις / 7 ημέρες",
        "active_days_7d": "Ενεργές ημέρες / 7 ημέρες",
        "duration_7d": "Προπόνηση / 7 ημέρες",
        "improving": "Βελτίωση",
        "stable": "Σταθερό",
        "declining": "Πτώση"},
    "de": {"dashboard":"Fitness-Dashboard","description":"Training, Schlaf, Erholung und Fitnessfortschritt in einem adaptiven Dashboard.","overview":"Übersicht","progress":"Fortschritt","workouts":"Trainings","recovery":"Erholung & Schlaf","live":"Live-Training","current":"Aktuelles Training","latest_workout":"Letztes Training","latest_sleep":"Letzter Schlaf","evaluation":"Auswertung","fitness_progress":"Fitnessfortschritt","recovery_progress":"Erholungsfortschritt","training_progress":"Trainingsfortschritt","sleep_progress":"Schlaffortschritt","workout_metrics":"Trainingsmetriken","workout_comparison":"Vergleich mit deiner Basis","route":"Trainingsroute","no_route":"Für das letzte Training ist keine GPS-Route verfügbar.","ai_summary":"KI-Auswertung","controls":"Trainingssteuerung","days_7":"7 Tage","days_28":"28 Tage","days_90":"90 Tage",
        "progress_snapshot": "Fitnessfortschritt",
        "current_vo2max": "Aktuelles VO₂max",
        "mean_28d": "28-Tage-Mittel",
        "mean_90d": "90-Tage-Mittel",
        "monthly_trend": "Trend / 30 Tage",
        "predicted_percent": "% des Sollwerts",
        "recovery_snapshot": "Erholung im Überblick",
        "recovery_limiting_factor": "Hauptlimit der Erholung",
        "limiter_muscular_recovery": "Muskuläre Erholung",
        "limiter_autonomic_recovery": "Autonome Erholung",
        "limiter_sleep_recovery": "Schlaferholung",
        "limiter_overall_readiness": "Gesamtbereitschaft",
        "limiter_workout_dose": "Trainingsbelastung",
        "recovery_readiness": "Erholung & Bereitschaft",
        "sleep_summary": "Schlafübersicht",
        "broader_recovery_window": "Breiteres physiologisches Erholungsfenster",
        "adaptation_evidence": "Evidenz",
        "adaptation_baseline": "Belastungsbalance",
        "adaptation_fitness": "Fitness-Trend",
        "adaptation_recovery": "Erholung",
        "adaptation_building": "Es wird genügend Verlauf für eine zuverlässige Anpassungsbewertung aufgebaut",
        "next_workout": "Bereit fürs nächste Training",
        "remaining": "Verbleibende Zeit",
        "ready_at": "Bereit etwa um",
        "recovery_window": "Geschätzter Erholungsbereich",
        "recovery_progress_label": "Erholungsfortschritt",
        "recovery_signals_label": "Erholungssignale",
        "physio_note": "Verfügbare physiologische Marker können sich unterschiedlich schnell erholen.",
        "ready_now": "Bereit fürs nächste Training",
        "confidence_short": "Konfidenz",
        "hours_short": "h",
        "sleep_score": "Schlafwert",
        "sleep_duration": "Schlafdauer",
        "sleep_hrv": "Schlaf-HRV",
        "sleep_deficit": "7-Tage-Schlafdefizit",
        "training_load_snapshot": "Trainingsbelastung",
        "load_ratio": "Belastung vs. Basis",
        "baseline_building": "Persönliche Basis wird aufgebaut",
        "baseline_building_hint": "Für eine zuverlässige Belastungsbewertung werden mehr vergleichbare Trainings benötigt.",
        "load_low": "Niedrig",
        "load_balanced": "Ausgeglichen",
        "load_elevated": "Erhöht",
        "load_high": "Hoch",
        "load_excessive": "Übermäßig",
        "training_adaptation_card": "Trainingsanpassung",
        "training_adaptation_subtitle": "Wie sich das aktuelle Training auf dich auswirkt",
        "adaptation_load_ratio": "Aktuelle / Basisbelastung",
        "adaptation_fitness_trend": "Fitness-Trend",
        "adaptation_recovery_signal": "Erholungssignal",
        "recent_load": "7-Tage-TRIMP",
        "baseline_load": "28-Tage-Wochenbasis",
        "workouts_7d": "Trainings / 7 Tage",
        "active_days_7d": "Aktive Tage / 7 Tage",
        "duration_7d": "Training / 7 Tage",
        "improving": "Verbesserung",
        "stable": "Stabil",
        "declining": "Rückgang"},
    "fr": {"dashboard":"Tableau Fitness","description":"Entraînements, sommeil, récupération et progression dans un tableau adaptatif.","overview":"Vue d’ensemble","progress":"Progression","workouts":"Entraînements","recovery":"Récupération & sommeil","live":"Entraînement en direct","current":"Entraînement actuel","latest_workout":"Dernier entraînement","latest_sleep":"Dernier sommeil","evaluation":"Évaluation","fitness_progress":"Progression de la forme","recovery_progress":"Progression de la récupération","training_progress":"Progression de l’entraînement","sleep_progress":"Progression du sommeil","workout_metrics":"Mesures de l’entraînement","workout_comparison":"Comparaison à ta référence","route":"Parcours de l’entraînement","no_route":"Aucun parcours GPS n’est disponible pour le dernier entraînement.","ai_summary":"Évaluation IA","controls":"Commandes d’entraînement","days_7":"7 jours","days_28":"28 jours","days_90":"90 jours",
        "progress_snapshot": "Progression de la forme",
        "current_vo2max": "VO₂max actuel",
        "mean_28d": "Moyenne 28 jours",
        "mean_90d": "Moyenne 90 jours",
        "monthly_trend": "Tendance / 30 jours",
        "predicted_percent": "% de la valeur prédite",
        "recovery_snapshot": "Aperçu récupération",
        "recovery_limiting_factor": "Principal facteur limitant",
        "limiter_muscular_recovery": "Récupération musculaire",
        "limiter_autonomic_recovery": "Récupération autonome",
        "limiter_sleep_recovery": "Récupération liée au sommeil",
        "limiter_overall_readiness": "Préparation globale",
        "limiter_workout_dose": "Charge de l’entraînement",
        "recovery_readiness": "Récupération & préparation",
        "sleep_summary": "Résumé du sommeil",
        "broader_recovery_window": "Fenêtre de récupération physiologique plus large",
        "adaptation_evidence": "Données",
        "adaptation_baseline": "Équilibre de charge",
        "adaptation_fitness": "Tendance de forme",
        "adaptation_recovery": "Récupération",
        "adaptation_building": "Historique en cours de constitution pour une évaluation fiable de l’adaptation",
        "next_workout": "Prêt pour le prochain entraînement",
        "remaining": "Temps restant",
        "ready_at": "Prêt vers",
        "recovery_window": "Plage de récupération estimée",
        "recovery_progress_label": "Progression de la récupération",
        "recovery_signals_label": "Signaux de récupération",
        "physio_note": "Les marqueurs physiologiques disponibles peuvent récupérer à des rythmes différents.",
        "ready_now": "Prêt pour le prochain entraînement",
        "confidence_short": "confiance",
        "hours_short": "h",
        "sleep_score": "Score de sommeil",
        "sleep_duration": "Durée du sommeil",
        "sleep_hrv": "VFC du sommeil",
        "sleep_deficit": "Déficit de sommeil sur 7 jours",
        "training_load_snapshot": "Charge d’entraînement",
        "load_ratio": "Charge vs référence",
        "baseline_building": "Création de la référence personnelle",
        "baseline_building_hint": "Davantage d’entraînements comparables sont nécessaires pour juger fiablement l’équilibre de charge.",
        "load_low": "Faible",
        "load_balanced": "Équilibrée",
        "load_elevated": "Élevée",
        "load_high": "Haute",
        "load_excessive": "Excessive",
        "training_adaptation_card": "Adaptation à l’entraînement",
        "training_adaptation_subtitle": "Comment l’entraînement récent t’affecte",
        "adaptation_load_ratio": "Charge récente / référence",
        "adaptation_fitness_trend": "Tendance de forme",
        "adaptation_recovery_signal": "Signal de récupération",
        "recent_load": "TRIMP 7 jours",
        "baseline_load": "Base hebdomadaire 28 jours",
        "workouts_7d": "Entraînements / 7 jours",
        "active_days_7d": "Jours actifs / 7 jours",
        "duration_7d": "Entraînement / 7 jours",
        "improving": "En progrès",
        "stable": "Stable",
        "declining": "En baisse"},
    "es": {"dashboard":"Panel Fitness","description":"Entrenamientos, sueño, recuperación y progreso físico en un panel adaptativo.","overview":"Resumen","progress":"Progreso","workouts":"Entrenamientos","recovery":"Recuperación y sueño","live":"Entrenamiento en vivo","current":"Entrenamiento actual","latest_workout":"Último entrenamiento","latest_sleep":"Último sueño","evaluation":"Evaluación","fitness_progress":"Progreso físico","recovery_progress":"Progreso de recuperación","training_progress":"Progreso de entrenamiento","sleep_progress":"Progreso del sueño","workout_metrics":"Métricas del entrenamiento","workout_comparison":"Comparado con tu referencia","route":"Ruta del entrenamiento","no_route":"No hay una ruta GPS disponible para el último entrenamiento.","ai_summary":"Evaluación con IA","controls":"Controles de entrenamiento","days_7":"7 días","days_28":"28 días","days_90":"90 días",
        "progress_snapshot": "Progreso físico",
        "current_vo2max": "VO₂max actual",
        "mean_28d": "Media de 28 días",
        "mean_90d": "Media de 90 días",
        "monthly_trend": "Tendencia / 30 días",
        "predicted_percent": "% del valor previsto",
        "recovery_snapshot": "Resumen de recuperación",
        "recovery_limiting_factor": "Principal factor limitante",
        "limiter_muscular_recovery": "Recuperación muscular",
        "limiter_autonomic_recovery": "Recuperación autonómica",
        "limiter_sleep_recovery": "Recuperación del sueño",
        "limiter_overall_readiness": "Preparación general",
        "limiter_workout_dose": "Carga del entrenamiento",
        "recovery_readiness": "Recuperación y preparación",
        "sleep_summary": "Resumen del sueño",
        "broader_recovery_window": "Ventana fisiológica de recuperación más amplia",
        "adaptation_evidence": "Evidencia",
        "adaptation_baseline": "Equilibrio de carga",
        "adaptation_fitness": "Tendencia de forma",
        "adaptation_recovery": "Recuperación",
        "adaptation_building": "Creando historial suficiente para una evaluación fiable de la adaptación",
        "next_workout": "Listo para el próximo entrenamiento",
        "remaining": "Tiempo restante",
        "ready_at": "Listo hacia",
        "recovery_window": "Rango de recuperación estimado",
        "recovery_progress_label": "Progreso de recuperación",
        "recovery_signals_label": "Señales de recuperación",
        "physio_note": "Los marcadores fisiológicos disponibles pueden recuperarse a ritmos distintos.",
        "ready_now": "Listo para el próximo entrenamiento",
        "confidence_short": "confianza",
        "hours_short": "h",
        "sleep_score": "Puntuación de sueño",
        "sleep_duration": "Duración del sueño",
        "sleep_hrv": "HRV del sueño",
        "sleep_deficit": "Déficit de sueño de 7 días",
        "training_load_snapshot": "Carga de entrenamiento",
        "load_ratio": "Carga vs referencia",
        "baseline_building": "Creando referencia personal",
        "baseline_building_hint": "Se necesitan más entrenamientos comparables para valorar de forma fiable el equilibrio de carga.",
        "load_low": "Baja",
        "load_balanced": "Equilibrada",
        "load_elevated": "Elevada",
        "load_high": "Alta",
        "load_excessive": "Excesiva",
        "training_adaptation_card": "Adaptación al entrenamiento",
        "training_adaptation_subtitle": "Cómo te está afectando el entrenamiento reciente",
        "adaptation_load_ratio": "Carga reciente / referencia",
        "adaptation_fitness_trend": "Tendencia de forma",
        "adaptation_recovery_signal": "Señal de recuperación",
        "recent_load": "TRIMP de 7 días",
        "baseline_load": "Base semanal de 28 días",
        "workouts_7d": "Entrenamientos / 7 días",
        "active_days_7d": "Días activos / 7 días",
        "duration_7d": "Entrenamiento / 7 días",
        "improving": "Mejorando",
        "stable": "Estable",
        "declining": "Empeorando"},
    "it": {"dashboard":"Dashboard Fitness","description":"Allenamenti, sonno, recupero e progressi in una dashboard adattiva.","overview":"Panoramica","progress":"Progressi","workouts":"Allenamenti","recovery":"Recupero e sonno","live":"Allenamento live","current":"Allenamento attuale","latest_workout":"Ultimo allenamento","latest_sleep":"Ultimo sonno","evaluation":"Valutazione","fitness_progress":"Progressi fitness","recovery_progress":"Progressi recupero","training_progress":"Progressi allenamento","sleep_progress":"Progressi sonno","workout_metrics":"Metriche allenamento","workout_comparison":"Confronto con il tuo riferimento","route":"Percorso allenamento","no_route":"Nessun percorso GPS disponibile per l’ultimo allenamento.","ai_summary":"Valutazione AI","controls":"Controlli allenamento","days_7":"7 giorni","days_28":"28 giorni","days_90":"90 giorni",
        "progress_snapshot": "Progressi fitness",
        "current_vo2max": "VO₂max attuale",
        "mean_28d": "Media 28 giorni",
        "mean_90d": "Media 90 giorni",
        "monthly_trend": "Tendenza / 30 giorni",
        "predicted_percent": "% del previsto",
        "recovery_snapshot": "Panoramica recupero",
        "recovery_limiting_factor": "Principale fattore limitante",
        "limiter_muscular_recovery": "Recupero muscolare",
        "limiter_autonomic_recovery": "Recupero autonomico",
        "limiter_sleep_recovery": "Recupero dal sonno",
        "limiter_overall_readiness": "Preparazione complessiva",
        "limiter_workout_dose": "Carico dell’allenamento",
        "recovery_readiness": "Recupero e preparazione",
        "sleep_summary": "Riepilogo del sonno",
        "broader_recovery_window": "Finestra fisiologica di recupero più ampia",
        "adaptation_evidence": "Evidenza",
        "adaptation_baseline": "Bilancio del carico",
        "adaptation_fitness": "Tendenza fitness",
        "adaptation_recovery": "Recupero",
        "adaptation_building": "Creazione di uno storico sufficiente per una valutazione affidabile dell’adattamento",
        "next_workout": "Pronto per il prossimo allenamento",
        "remaining": "Tempo rimanente",
        "ready_at": "Pronto verso",
        "recovery_window": "Intervallo di recupero stimato",
        "recovery_progress_label": "Progresso del recupero",
        "recovery_signals_label": "Segnali di recupero",
        "physio_note": "I marcatori fisiologici disponibili possono recuperare a velocità diverse.",
        "ready_now": "Pronto per il prossimo allenamento",
        "confidence_short": "affidabilità",
        "hours_short": "h",
        "sleep_score": "Punteggio sonno",
        "sleep_duration": "Durata sonno",
        "sleep_hrv": "HRV del sonno",
        "sleep_deficit": "Deficit sonno 7 giorni",
        "training_load_snapshot": "Carico di allenamento",
        "load_ratio": "Carico vs riferimento",
        "baseline_building": "Creazione del riferimento personale",
        "baseline_building_hint": "Servono più allenamenti confrontabili per valutare in modo affidabile l’equilibrio del carico.",
        "load_low": "Basso",
        "load_balanced": "Bilanciato",
        "load_elevated": "Elevato",
        "load_high": "Alto",
        "load_excessive": "Eccessivo",
        "training_adaptation_card": "Adattamento all’allenamento",
        "training_adaptation_subtitle": "Come ti sta influenzando l’allenamento recente",
        "adaptation_load_ratio": "Carico recente / riferimento",
        "adaptation_fitness_trend": "Tendenza fitness",
        "adaptation_recovery_signal": "Segnale di recupero",
        "recent_load": "TRIMP 7 giorni",
        "baseline_load": "Base settimanale 28 giorni",
        "workouts_7d": "Allenamenti / 7 giorni",
        "active_days_7d": "Giorni attivi / 7 giorni",
        "duration_7d": "Allenamento / 7 giorni",
        "improving": "In miglioramento",
        "stable": "Stabile",
        "declining": "In calo"},
    "pt": {"dashboard":"Painel Fitness","description":"Treinos, sono, recuperação e progresso físico num painel adaptativo.","overview":"Visão geral","progress":"Progresso","workouts":"Treinos","recovery":"Recuperação e sono","live":"Treino ao vivo","current":"Treino atual","latest_workout":"Último treino","latest_sleep":"Último sono","evaluation":"Avaliação","fitness_progress":"Progresso físico","recovery_progress":"Progresso da recuperação","training_progress":"Progresso do treino","sleep_progress":"Progresso do sono","workout_metrics":"Métricas do treino","workout_comparison":"Comparação com a tua referência","route":"Percurso do treino","no_route":"Não existe percurso GPS para o último treino.","ai_summary":"Avaliação por IA","controls":"Controlos do treino","days_7":"7 dias","days_28":"28 dias","days_90":"90 dias",
        "progress_snapshot": "Progresso físico",
        "current_vo2max": "VO₂max atual",
        "mean_28d": "Média de 28 dias",
        "mean_90d": "Média de 90 dias",
        "monthly_trend": "Tendência / 30 dias",
        "predicted_percent": "% do previsto",
        "recovery_snapshot": "Resumo da recuperação",
        "recovery_limiting_factor": "Principal fator limitante",
        "limiter_muscular_recovery": "Recuperação muscular",
        "limiter_autonomic_recovery": "Recuperação autonómica",
        "limiter_sleep_recovery": "Recuperação do sono",
        "limiter_overall_readiness": "Prontidão geral",
        "limiter_workout_dose": "Carga do treino",
        "recovery_readiness": "Recuperação e prontidão",
        "sleep_summary": "Resumo do sono",
        "broader_recovery_window": "Janela fisiológica de recuperação mais ampla",
        "adaptation_evidence": "Evidência",
        "adaptation_baseline": "Equilíbrio da carga",
        "adaptation_fitness": "Tendência de forma",
        "adaptation_recovery": "Recuperação",
        "adaptation_building": "A criar histórico suficiente para uma avaliação fiável da adaptação",
        "next_workout": "Pronto para o próximo treino",
        "remaining": "Tempo restante",
        "ready_at": "Pronto por volta de",
        "recovery_window": "Intervalo de recuperação estimado",
        "recovery_progress_label": "Progresso da recuperação",
        "recovery_signals_label": "Sinais de recuperação",
        "physio_note": "Os marcadores fisiológicos disponíveis podem recuperar a ritmos diferentes.",
        "ready_now": "Pronto para o próximo treino",
        "confidence_short": "confiança",
        "hours_short": "h",
        "sleep_score": "Pontuação do sono",
        "sleep_duration": "Duração do sono",
        "sleep_hrv": "HRV do sono",
        "sleep_deficit": "Défice de sono de 7 dias",
        "training_load_snapshot": "Carga de treino",
        "load_ratio": "Carga vs referência",
        "baseline_building": "A criar referência pessoal",
        "baseline_building_hint": "São necessários mais treinos comparáveis para avaliar de forma fiável o equilíbrio da carga.",
        "load_low": "Baixa",
        "load_balanced": "Equilibrada",
        "load_elevated": "Elevada",
        "load_high": "Alta",
        "load_excessive": "Excessiva",
        "training_adaptation_card": "Adaptação ao treino",
        "training_adaptation_subtitle": "Como o treino recente te está a afetar",
        "adaptation_load_ratio": "Carga recente / referência",
        "adaptation_fitness_trend": "Tendência de forma",
        "adaptation_recovery_signal": "Sinal de recuperação",
        "recent_load": "TRIMP de 7 dias",
        "baseline_load": "Base semanal de 28 dias",
        "workouts_7d": "Treinos / 7 dias",
        "active_days_7d": "Dias ativos / 7 dias",
        "duration_7d": "Treino / 7 dias",
        "improving": "A melhorar",
        "stable": "Estável",
        "declining": "A diminuir"},
    "nl": {"dashboard":"Fitness-dashboard","description":"Trainingen, slaap, herstel en fitnessvoortgang in één adaptief dashboard.","overview":"Overzicht","progress":"Voortgang","workouts":"Trainingen","recovery":"Herstel & slaap","live":"Live training","current":"Huidige training","latest_workout":"Laatste training","latest_sleep":"Laatste slaap","evaluation":"Evaluatie","fitness_progress":"Fitnessvoortgang","recovery_progress":"Herstelvoortgang","training_progress":"Trainingsvoortgang","sleep_progress":"Slaapvoortgang","workout_metrics":"Trainingsgegevens","workout_comparison":"Vergelijking met je basislijn","route":"Trainingsroute","no_route":"Geen GPS-route beschikbaar voor de laatste training.","ai_summary":"AI-evaluatie","controls":"Trainingsbediening","days_7":"7 dagen","days_28":"28 dagen","days_90":"90 dagen",
        "progress_snapshot": "Fitnessvoortgang",
        "current_vo2max": "Huidige VO₂max",
        "mean_28d": "28-daags gemiddelde",
        "mean_90d": "90-daags gemiddelde",
        "monthly_trend": "Trend / 30 dagen",
        "predicted_percent": "% van voorspeld",
        "recovery_snapshot": "Hersteloverzicht",
        "recovery_limiting_factor": "Belangrijkste herstelbeperking",
        "limiter_muscular_recovery": "Spierherstel",
        "limiter_autonomic_recovery": "Autonoom herstel",
        "limiter_sleep_recovery": "Slaapherstel",
        "limiter_overall_readiness": "Algemene paraatheid",
        "limiter_workout_dose": "Trainingsbelasting",
        "recovery_readiness": "Herstel & paraatheid",
        "sleep_summary": "Slaapoverzicht",
        "broader_recovery_window": "Breder fysiologisch herstelvenster",
        "adaptation_evidence": "Onderbouwing",
        "adaptation_baseline": "Belastingsbalans",
        "adaptation_fitness": "Fitnesstrend",
        "adaptation_recovery": "Herstel",
        "adaptation_building": "Er wordt voldoende historie opgebouwd voor een betrouwbare adaptatiebeoordeling",
        "next_workout": "Klaar voor de volgende training",
        "remaining": "Resterende tijd",
        "ready_at": "Klaar rond",
        "recovery_window": "Geschat herstelbereik",
        "recovery_progress_label": "Herstelvoortgang",
        "recovery_signals_label": "Herstelsignalen",
        "physio_note": "Beschikbare fysiologische markers kunnen met verschillende snelheden herstellen.",
        "ready_now": "Klaar voor de volgende training",
        "confidence_short": "betrouwbaarheid",
        "hours_short": "u",
        "sleep_score": "Slaapscore",
        "sleep_duration": "Slaapduur",
        "sleep_hrv": "Slaap-HRV",
        "sleep_deficit": "Slaaptekort 7 dagen",
        "training_load_snapshot": "Trainingsbelasting",
        "load_ratio": "Belasting vs basis",
        "baseline_building": "Persoonlijke basis wordt opgebouwd",
        "baseline_building_hint": "Er zijn meer vergelijkbare trainingen nodig om de belastingsbalans betrouwbaar te beoordelen.",
        "load_low": "Laag",
        "load_balanced": "Gebalanceerd",
        "load_elevated": "Verhoogd",
        "load_high": "Hoog",
        "load_excessive": "Overmatig",
        "training_adaptation_card": "Trainingsadaptatie",
        "training_adaptation_subtitle": "Hoe recente training je beïnvloedt",
        "adaptation_load_ratio": "Recente / basisbelasting",
        "adaptation_fitness_trend": "Fitnesstrend",
        "adaptation_recovery_signal": "Herstelsignaal",
        "recent_load": "7-daagse TRIMP",
        "baseline_load": "28-daagse weekbasis",
        "workouts_7d": "Trainingen / 7 dagen",
        "active_days_7d": "Actieve dagen / 7 dagen",
        "duration_7d": "Training / 7 dagen",
        "improving": "Verbeterend",
        "stable": "Stabiel",
        "declining": "Dalend"},
    "pl": {"dashboard":"Panel Fitness","description":"Treningi, sen, regeneracja i postęp kondycji w jednym adaptacyjnym panelu.","overview":"Przegląd","progress":"Postęp","workouts":"Treningi","recovery":"Regeneracja i sen","live":"Trening na żywo","current":"Bieżący trening","latest_workout":"Ostatni trening","latest_sleep":"Ostatni sen","evaluation":"Ocena","fitness_progress":"Postęp kondycji","recovery_progress":"Postęp regeneracji","training_progress":"Postęp treningu","sleep_progress":"Postęp snu","workout_metrics":"Metryki treningu","workout_comparison":"Porównanie z twoją bazą","route":"Trasa treningu","no_route":"Brak trasy GPS dla ostatniego treningu.","ai_summary":"Ocena AI","controls":"Sterowanie treningiem","days_7":"7 dni","days_28":"28 dni","days_90":"90 dni",
        "progress_snapshot": "Postęp kondycji",
        "current_vo2max": "Aktualne VO₂max",
        "mean_28d": "Średnia 28 dni",
        "mean_90d": "Średnia 90 dni",
        "monthly_trend": "Trend / 30 dni",
        "predicted_percent": "% wartości przewidywanej",
        "recovery_snapshot": "Podsumowanie regeneracji",
        "recovery_limiting_factor": "Główny czynnik ograniczający",
        "limiter_muscular_recovery": "Regeneracja mięśniowa",
        "limiter_autonomic_recovery": "Regeneracja autonomiczna",
        "limiter_sleep_recovery": "Regeneracja przez sen",
        "limiter_overall_readiness": "Ogólna gotowość",
        "limiter_workout_dose": "Obciążenie treningowe",
        "recovery_readiness": "Regeneracja i gotowość",
        "sleep_summary": "Podsumowanie snu",
        "broader_recovery_window": "Szersze fizjologiczne okno regeneracji",
        "adaptation_evidence": "Dane",
        "adaptation_baseline": "Równowaga obciążenia",
        "adaptation_fitness": "Trend formy",
        "adaptation_recovery": "Regeneracja",
        "adaptation_building": "Budowana jest wystarczająca historia do wiarygodnej oceny adaptacji",
        "next_workout": "Gotowy na kolejny trening",
        "remaining": "Pozostały czas",
        "ready_at": "Gotowy około",
        "recovery_window": "Szacowany zakres regeneracji",
        "recovery_progress_label": "Postęp regeneracji",
        "recovery_signals_label": "Sygnały regeneracji",
        "physio_note": "Dostępne markery fizjologiczne mogą wracać do normy w różnym tempie.",
        "ready_now": "Gotowy na kolejny trening",
        "confidence_short": "pewność",
        "hours_short": "h",
        "sleep_score": "Ocena snu",
        "sleep_duration": "Czas snu",
        "sleep_hrv": "HRV podczas snu",
        "sleep_deficit": "Deficyt snu 7 dni",
        "training_load_snapshot": "Obciążenie treningowe",
        "load_ratio": "Obciążenie vs baza",
        "baseline_building": "Budowanie osobistej bazy",
        "baseline_building_hint": "Potrzeba więcej porównywalnych treningów, aby wiarygodnie ocenić równowagę obciążenia.",
        "load_low": "Niskie",
        "load_balanced": "Zrównoważone",
        "load_elevated": "Podwyższone",
        "load_high": "Wysokie",
        "load_excessive": "Nadmierne",
        "training_adaptation_card": "Adaptacja treningowa",
        "training_adaptation_subtitle": "Jak ostatni trening na Ciebie wpływa",
        "adaptation_load_ratio": "Ostatnie / bazowe obciążenie",
        "adaptation_fitness_trend": "Trend formy",
        "adaptation_recovery_signal": "Sygnał regeneracji",
        "recent_load": "TRIMP 7 dni",
        "baseline_load": "Tygodniowa baza 28 dni",
        "workouts_7d": "Treningi / 7 dni",
        "active_days_7d": "Aktywne dni / 7 dni",
        "duration_7d": "Trening / 7 dni",
        "improving": "Poprawa",
        "stable": "Stabilnie",
        "declining": "Spadek"},
    "ru": {"dashboard":"Панель Fitness","description":"Тренировки, сон, восстановление и прогресс в одной адаптивной панели.","overview":"Обзор","progress":"Прогресс","workouts":"Тренировки","recovery":"Восстановление и сон","live":"Тренировка в реальном времени","current":"Текущая тренировка","latest_workout":"Последняя тренировка","latest_sleep":"Последний сон","evaluation":"Оценка","fitness_progress":"Прогресс формы","recovery_progress":"Прогресс восстановления","training_progress":"Прогресс тренировок","sleep_progress":"Прогресс сна","workout_metrics":"Показатели тренировки","workout_comparison":"Сравнение с вашей базой","route":"Маршрут тренировки","no_route":"Для последней тренировки нет GPS-маршрута.","ai_summary":"Оценка ИИ","controls":"Управление тренировкой","days_7":"7 дней","days_28":"28 дней","days_90":"90 дней",
        "progress_snapshot": "Прогресс формы",
        "current_vo2max": "Текущий VO₂max",
        "mean_28d": "Среднее за 28 дней",
        "mean_90d": "Среднее за 90 дней",
        "monthly_trend": "Тренд / 30 дней",
        "predicted_percent": "% от прогнозируемого",
        "recovery_snapshot": "Сводка восстановления",
        "recovery_limiting_factor": "Главный ограничивающий фактор",
        "limiter_muscular_recovery": "Мышечное восстановление",
        "limiter_autonomic_recovery": "Автономное восстановление",
        "limiter_sleep_recovery": "Восстановление сном",
        "limiter_overall_readiness": "Общая готовность",
        "limiter_workout_dose": "Тренировочная нагрузка",
        "recovery_readiness": "Восстановление и готовность",
        "sleep_summary": "Сводка сна",
        "broader_recovery_window": "Более широкое окно физиологического восстановления",
        "adaptation_evidence": "Данные",
        "adaptation_baseline": "Баланс нагрузки",
        "adaptation_fitness": "Тренд формы",
        "adaptation_recovery": "Восстановление",
        "adaptation_building": "Накапливается история для надёжной оценки адаптации",
        "next_workout": "Готов к следующей тренировке",
        "remaining": "Осталось времени",
        "ready_at": "Готов примерно к",
        "recovery_window": "Расчётный диапазон восстановления",
        "recovery_progress_label": "Прогресс восстановления",
        "recovery_signals_label": "Сигналы восстановления",
        "physio_note": "Доступные физиологические маркеры могут восстанавливаться с разной скоростью.",
        "ready_now": "Готов к следующей тренировке",
        "confidence_short": "уверенность",
        "hours_short": "ч",
        "sleep_score": "Оценка сна",
        "sleep_duration": "Длительность сна",
        "sleep_hrv": "HRV сна",
        "sleep_deficit": "Дефицит сна за 7 дней",
        "training_load_snapshot": "Тренировочная нагрузка",
        "load_ratio": "Нагрузка к базовой",
        "baseline_building": "Формируется персональная база",
        "baseline_building_hint": "Нужно больше сопоставимых тренировок для надёжной оценки баланса нагрузки.",
        "load_low": "Низкая",
        "load_balanced": "Сбалансированная",
        "load_elevated": "Повышенная",
        "load_high": "Высокая",
        "load_excessive": "Чрезмерная",
        "training_adaptation_card": "Тренировочная адаптация",
        "training_adaptation_subtitle": "Как недавние тренировки влияют на вас",
        "adaptation_load_ratio": "Текущая / базовая нагрузка",
        "adaptation_fitness_trend": "Тренд формы",
        "adaptation_recovery_signal": "Сигнал восстановления",
        "recent_load": "TRIMP за 7 дней",
        "baseline_load": "Недельная база за 28 дней",
        "workouts_7d": "Тренировки / 7 дней",
        "active_days_7d": "Активные дни / 7 дней",
        "duration_7d": "Тренировки / 7 дней",
        "improving": "Улучшение",
        "stable": "Стабильно",
        "declining": "Снижение"},
    "uk": {"dashboard":"Панель Fitness","description":"Тренування, сон, відновлення та прогрес в одній адаптивній панелі.","overview":"Огляд","progress":"Прогрес","workouts":"Тренування","recovery":"Відновлення та сон","live":"Тренування наживо","current":"Поточне тренування","latest_workout":"Останнє тренування","latest_sleep":"Останній сон","evaluation":"Оцінка","fitness_progress":"Прогрес форми","recovery_progress":"Прогрес відновлення","training_progress":"Прогрес тренувань","sleep_progress":"Прогрес сну","workout_metrics":"Показники тренування","workout_comparison":"Порівняння з вашою базою","route":"Маршрут тренування","no_route":"Для останнього тренування немає GPS-маршруту.","ai_summary":"Оцінка ШІ","controls":"Керування тренуванням","days_7":"7 днів","days_28":"28 днів","days_90":"90 днів",
        "progress_snapshot": "Прогрес форми",
        "current_vo2max": "Поточний VO₂max",
        "mean_28d": "Середнє за 28 днів",
        "mean_90d": "Середнє за 90 днів",
        "monthly_trend": "Тренд / 30 днів",
        "predicted_percent": "% від прогнозованого",
        "recovery_snapshot": "Огляд відновлення",
        "recovery_limiting_factor": "Головний обмежувальний чинник",
        "limiter_muscular_recovery": "М’язове відновлення",
        "limiter_autonomic_recovery": "Автономне відновлення",
        "limiter_sleep_recovery": "Відновлення сном",
        "limiter_overall_readiness": "Загальна готовність",
        "limiter_workout_dose": "Тренувальне навантаження",
        "recovery_readiness": "Відновлення та готовність",
        "sleep_summary": "Підсумок сну",
        "broader_recovery_window": "Ширше вікно фізіологічного відновлення",
        "adaptation_evidence": "Дані",
        "adaptation_baseline": "Баланс навантаження",
        "adaptation_fitness": "Тренд форми",
        "adaptation_recovery": "Відновлення",
        "adaptation_building": "Накопичується достатня історія для надійної оцінки адаптації",
        "next_workout": "Готовий до наступного тренування",
        "remaining": "Залишилось часу",
        "ready_at": "Готовий приблизно о",
        "recovery_window": "Орієнтовний діапазон відновлення",
        "recovery_progress_label": "Прогрес відновлення",
        "recovery_signals_label": "Сигнали відновлення",
        "physio_note": "Доступні фізіологічні маркери можуть відновлюватися з різною швидкістю.",
        "ready_now": "Готовий до наступного тренування",
        "confidence_short": "впевненість",
        "hours_short": "год",
        "sleep_score": "Оцінка сну",
        "sleep_duration": "Тривалість сну",
        "sleep_hrv": "HRV сну",
        "sleep_deficit": "Дефіцит сну за 7 днів",
        "training_load_snapshot": "Тренувальне навантаження",
        "load_ratio": "Навантаження до базового",
        "baseline_building": "Формується особиста база",
        "baseline_building_hint": "Потрібно більше зіставних тренувань для надійної оцінки балансу навантаження.",
        "load_low": "Низьке",
        "load_balanced": "Збалансоване",
        "load_elevated": "Підвищене",
        "load_high": "Високе",
        "load_excessive": "Надмірне",
        "training_adaptation_card": "Тренувальна адаптація",
        "training_adaptation_subtitle": "Як нещодавні тренування впливають на вас",
        "adaptation_load_ratio": "Поточне / базове навантаження",
        "adaptation_fitness_trend": "Тренд форми",
        "adaptation_recovery_signal": "Сигнал відновлення",
        "recent_load": "TRIMP за 7 днів",
        "baseline_load": "Тижнева база за 28 днів",
        "workouts_7d": "Тренування / 7 днів",
        "active_days_7d": "Активні дні / 7 днів",
        "duration_7d": "Тренування / 7 днів",
        "improving": "Покращення",
        "stable": "Стабільно",
        "declining": "Зниження"},
    "tr": {"dashboard":"Fitness paneli","description":"Antrenman, uyku, toparlanma ve fitness ilerlemesi tek uyarlanabilir panelde.","overview":"Genel bakış","progress":"İlerleme","workouts":"Antrenmanlar","recovery":"Toparlanma ve uyku","live":"Canlı antrenman","current":"Mevcut antrenman","latest_workout":"Son antrenman","latest_sleep":"Son uyku","evaluation":"Değerlendirme","fitness_progress":"Fitness ilerlemesi","recovery_progress":"Toparlanma ilerlemesi","training_progress":"Antrenman ilerlemesi","sleep_progress":"Uyku ilerlemesi","workout_metrics":"Antrenman ölçümleri","workout_comparison":"Kişisel bazla karşılaştırma","route":"Antrenman rotası","no_route":"Son antrenman için GPS rotası yok.","ai_summary":"AI değerlendirmesi","controls":"Antrenman kontrolleri","days_7":"7 gün","days_28":"28 gün","days_90":"90 gün",
        "progress_snapshot": "Fitness ilerlemesi",
        "current_vo2max": "Güncel VO₂max",
        "mean_28d": "28 günlük ortalama",
        "mean_90d": "90 günlük ortalama",
        "monthly_trend": "Trend / 30 gün",
        "predicted_percent": "Tahmin edilenin %'si",
        "recovery_snapshot": "Toparlanma özeti",
        "recovery_limiting_factor": "Ana toparlanma sınırlayıcısı",
        "limiter_muscular_recovery": "Kas toparlanması",
        "limiter_autonomic_recovery": "Otonom toparlanma",
        "limiter_sleep_recovery": "Uyku toparlanması",
        "limiter_overall_readiness": "Genel hazır olma",
        "limiter_workout_dose": "Antrenman yükü",
        "recovery_readiness": "Toparlanma ve hazır olma",
        "sleep_summary": "Uyku özeti",
        "broader_recovery_window": "Daha geniş fizyolojik toparlanma aralığı",
        "adaptation_evidence": "Kanıt",
        "adaptation_baseline": "Yük dengesi",
        "adaptation_fitness": "Fitness eğilimi",
        "adaptation_recovery": "Toparlanma",
        "adaptation_building": "Güvenilir adaptasyon değerlendirmesi için yeterli geçmiş oluşturuluyor",
        "next_workout": "Bir sonraki antrenmana hazır",
        "remaining": "Kalan süre",
        "ready_at": "Yaklaşık hazır olma",
        "recovery_window": "Tahmini toparlanma aralığı",
        "recovery_progress_label": "Toparlanma ilerlemesi",
        "recovery_signals_label": "Toparlanma sinyalleri",
        "physio_note": "Mevcut fizyolojik göstergeler farklı hızlarda toparlanabilir.",
        "ready_now": "Bir sonraki antrenmana hazır",
        "confidence_short": "güven",
        "hours_short": "sa",
        "sleep_score": "Uyku puanı",
        "sleep_duration": "Uyku süresi",
        "sleep_hrv": "Uyku HRV",
        "sleep_deficit": "7 günlük uyku açığı",
        "training_load_snapshot": "Antrenman yükü",
        "load_ratio": "Yük / temel",
        "baseline_building": "Kişisel temel oluşturuluyor",
        "baseline_building_hint": "Yük dengesini güvenilir değerlendirmek için daha fazla karşılaştırılabilir antrenman gerekir.",
        "load_low": "Düşük",
        "load_balanced": "Dengeli",
        "load_elevated": "Yükselmiş",
        "load_high": "Yüksek",
        "load_excessive": "Aşırı",
        "training_adaptation_card": "Antrenman adaptasyonu",
        "training_adaptation_subtitle": "Son antrenmanların seni nasıl etkilediği",
        "adaptation_load_ratio": "Güncel / temel yük",
        "adaptation_fitness_trend": "Fitness eğilimi",
        "adaptation_recovery_signal": "Toparlanma sinyali",
        "recent_load": "7 günlük TRIMP",
        "baseline_load": "28 günlük haftalık temel",
        "workouts_7d": "Antrenman / 7 gün",
        "active_days_7d": "Aktif gün / 7 gün",
        "duration_7d": "Antrenman / 7 gün",
        "improving": "İyileşiyor",
        "stable": "Sabit",
        "declining": "Düşüyor"},
    "zh": {"dashboard":"Fitness 仪表板","description":"在一个自适应仪表板中查看训练、睡眠、恢复和体能进步。","overview":"概览","progress":"进步","workouts":"训练","recovery":"恢复与睡眠","live":"实时训练","current":"当前训练","latest_workout":"最近训练","latest_sleep":"最近睡眠","evaluation":"评估","fitness_progress":"体能进步","recovery_progress":"恢复进步","training_progress":"训练进步","sleep_progress":"睡眠进步","workout_metrics":"训练指标","workout_comparison":"与个人基线比较","route":"训练路线","no_route":"最近训练没有可用的 GPS 路线。","ai_summary":"AI 评估","controls":"训练控制","days_7":"7 天","days_28":"28 天","days_90":"90 天",
        "progress_snapshot": "体能进步",
        "current_vo2max": "当前 VO₂max",
        "mean_28d": "28 天平均",
        "mean_90d": "90 天平均",
        "monthly_trend": "趋势 / 30 天",
        "predicted_percent": "预测值百分比",
        "recovery_snapshot": "恢复概览",
        "recovery_limiting_factor": "主要恢复限制因素",
        "limiter_muscular_recovery": "肌肉恢复",
        "limiter_autonomic_recovery": "自主神经恢复",
        "limiter_sleep_recovery": "睡眠恢复",
        "limiter_overall_readiness": "整体准备度",
        "limiter_workout_dose": "训练负荷",
        "recovery_readiness": "恢复与准备度",
        "sleep_summary": "睡眠摘要",
        "broader_recovery_window": "更宽的生理恢复窗口",
        "adaptation_evidence": "依据",
        "adaptation_baseline": "负荷平衡",
        "adaptation_fitness": "体能趋势",
        "adaptation_recovery": "恢复",
        "adaptation_building": "正在积累足够历史，以进行可靠的训练适应评估",
        "next_workout": "准备好下一次训练",
        "remaining": "剩余时间",
        "ready_at": "预计准备好时间",
        "recovery_window": "预计恢复范围",
        "recovery_progress_label": "恢复进度",
        "recovery_signals_label": "恢复信号",
        "physio_note": "可用的生理指标可能以不同速度恢复。",
        "ready_now": "已准备好下一次训练",
        "confidence_short": "置信度",
        "hours_short": "小时",
        "sleep_score": "睡眠评分",
        "sleep_duration": "睡眠时长",
        "sleep_hrv": "睡眠 HRV",
        "sleep_deficit": "7 天睡眠不足",
        "training_load_snapshot": "训练负荷",
        "load_ratio": "负荷与基线",
        "baseline_building": "正在建立个人基线",
        "baseline_building_hint": "需要更多可比较的训练，才能可靠评估训练负荷平衡。",
        "load_low": "低",
        "load_balanced": "均衡",
        "load_elevated": "偏高",
        "load_high": "高",
        "load_excessive": "过高",
        "training_adaptation_card": "训练适应",
        "training_adaptation_subtitle": "近期训练对你的影响",
        "adaptation_load_ratio": "近期 / 基线负荷",
        "adaptation_fitness_trend": "体能趋势",
        "adaptation_recovery_signal": "恢复信号",
        "recent_load": "7 天 TRIMP",
        "baseline_load": "28 天周基线",
        "workouts_7d": "训练 / 7 天",
        "active_days_7d": "活跃天数 / 7 天",
        "duration_7d": "训练时长 / 7 天",
        "improving": "改善中",
        "stable": "稳定",
        "declining": "下降"},
    "ja": {"dashboard":"Fitness ダッシュボード","description":"ワークアウト、睡眠、回復、フィットネスの進歩を1つの適応型ダッシュボードにまとめます。","overview":"概要","progress":"進歩","workouts":"ワークアウト","recovery":"回復と睡眠","live":"ライブワークアウト","current":"現在のワークアウト","latest_workout":"最新のワークアウト","latest_sleep":"最新の睡眠","evaluation":"評価","fitness_progress":"フィットネスの進歩","recovery_progress":"回復の進歩","training_progress":"トレーニングの進歩","sleep_progress":"睡眠の進歩","workout_metrics":"ワークアウト指標","workout_comparison":"個人ベースラインとの比較","route":"ワークアウトルート","no_route":"最新のワークアウトに GPS ルートがありません。","ai_summary":"AI 評価","controls":"ワークアウト操作","days_7":"7日","days_28":"28日","days_90":"90日",
        "progress_snapshot": "フィットネスの進歩",
        "current_vo2max": "現在の VO₂max",
        "mean_28d": "28日平均",
        "mean_90d": "90日平均",
        "monthly_trend": "傾向 / 30日",
        "predicted_percent": "予測値に対する割合",
        "recovery_snapshot": "回復概要",
        "recovery_limiting_factor": "主な回復制限要因",
        "limiter_muscular_recovery": "筋肉の回復",
        "limiter_autonomic_recovery": "自律神経の回復",
        "limiter_sleep_recovery": "睡眠による回復",
        "limiter_overall_readiness": "総合的な準備度",
        "limiter_workout_dose": "トレーニング負荷",
        "recovery_readiness": "回復と準備度",
        "sleep_summary": "睡眠サマリー",
        "broader_recovery_window": "より広い生理学的回復ウィンドウ",
        "adaptation_evidence": "根拠",
        "adaptation_baseline": "負荷バランス",
        "adaptation_fitness": "フィットネストレンド",
        "adaptation_recovery": "回復",
        "adaptation_building": "信頼できる適応評価に必要な履歴を蓄積中です",
        "next_workout": "次のトレーニングに備う",
        "remaining": "残り時間",
        "ready_at": "準備完了の目安",
        "recovery_window": "推定回復範囲",
        "recovery_progress_label": "回復進捗",
        "recovery_signals_label": "回復シグナル",
        "physio_note": "利用可能な生理指標は異なる速度で回復することがあります。",
        "ready_now": "次のトレーニングに備う",
        "confidence_short": "信頼度",
        "hours_short": "時間",
        "sleep_score": "睡眠スコア",
        "sleep_duration": "睡眠時間",
        "sleep_hrv": "睡眠 HRV",
        "sleep_deficit": "7日間の睡眠不足",
        "training_load_snapshot": "トレーニング負荷",
        "load_ratio": "負荷 / ベースライン",
        "baseline_building": "個人ベースラインを作成中",
        "baseline_building_hint": "負荷バランスを信頼して評価するには、比較可能なトレーニングがさらに必要です。",
        "load_low": "低い",
        "load_balanced": "適正",
        "load_elevated": "やや高い",
        "load_high": "高い",
        "load_excessive": "過剰",
        "training_adaptation_card": "トレーニング適応",
        "training_adaptation_subtitle": "最近のトレーニングが体に与えている影響",
        "adaptation_load_ratio": "最近 / ベースライン負荷",
        "adaptation_fitness_trend": "フィットネストレンド",
        "adaptation_recovery_signal": "回復シグナル",
        "recent_load": "7日間 TRIMP",
        "baseline_load": "28日週基準",
        "workouts_7d": "ワークアウト / 7日",
        "active_days_7d": "活動日 / 7日",
        "duration_7d": "トレーニング / 7日",
        "improving": "改善",
        "stable": "安定",
        "declining": "低下"},
    "ko": {"dashboard":"Fitness 대시보드","description":"운동, 수면, 회복 및 체력 향상을 하나의 적응형 대시보드에서 확인합니다.","overview":"개요","progress":"향상","workouts":"운동","recovery":"회복 및 수면","live":"실시간 운동","current":"현재 운동","latest_workout":"최근 운동","latest_sleep":"최근 수면","evaluation":"평가","fitness_progress":"체력 향상","recovery_progress":"회복 향상","training_progress":"훈련 향상","sleep_progress":"수면 향상","workout_metrics":"운동 지표","workout_comparison":"개인 기준선과 비교","route":"운동 경로","no_route":"최근 운동에 GPS 경로가 없습니다.","ai_summary":"AI 평가","controls":"운동 제어","days_7":"7일","days_28":"28일","days_90":"90일",
        "progress_snapshot": "체력 향상",
        "current_vo2max": "현재 VO₂max",
        "mean_28d": "28일 평균",
        "mean_90d": "90일 평균",
        "monthly_trend": "추세 / 30일",
        "predicted_percent": "예측값 대비 %",
        "recovery_snapshot": "회복 요약",
        "recovery_limiting_factor": "주요 회복 제한 요인",
        "limiter_muscular_recovery": "근육 회복",
        "limiter_autonomic_recovery": "자율신경 회복",
        "limiter_sleep_recovery": "수면 회복",
        "limiter_overall_readiness": "전체 준비도",
        "limiter_workout_dose": "운동 부하",
        "recovery_readiness": "회복 및 준비도",
        "sleep_summary": "수면 요약",
        "broader_recovery_window": "더 넓은 생리적 회복 범위",
        "adaptation_evidence": "근거",
        "adaptation_baseline": "부하 균형",
        "adaptation_fitness": "체력 추세",
        "adaptation_recovery": "회복",
        "adaptation_building": "신뢰할 수 있는 적응 평가를 위해 충분한 기록을 쌓는 중입니다",
        "next_workout": "다음 운동 준비 완료",
        "remaining": "남은 시간",
        "ready_at": "예상 준비 시각",
        "recovery_window": "예상 회복 범위",
        "recovery_progress_label": "회복 진행률",
        "recovery_signals_label": "회복 신호",
        "physio_note": "사용 가능한 생리 지표는 서로 다른 속도로 회복될 수 있습니다.",
        "ready_now": "다음 운동 준비 완료",
        "confidence_short": "신뢰도",
        "hours_short": "시간",
        "sleep_score": "수면 점수",
        "sleep_duration": "수면 시간",
        "sleep_hrv": "수면 HRV",
        "sleep_deficit": "7일 수면 부족",
        "training_load_snapshot": "훈련 부하",
        "load_ratio": "부하 / 기준",
        "baseline_building": "개인 기준선 생성 중",
        "baseline_building_hint": "부하 균형을 신뢰성 있게 평가하려면 비교 가능한 운동이 더 필요합니다.",
        "load_low": "낮음",
        "load_balanced": "균형",
        "load_elevated": "상승",
        "load_high": "높음",
        "load_excessive": "과도",
        "training_adaptation_card": "훈련 적응",
        "training_adaptation_subtitle": "최근 훈련이 몸에 미치는 영향",
        "adaptation_load_ratio": "최근 / 기준 부하",
        "adaptation_fitness_trend": "체력 추세",
        "adaptation_recovery_signal": "회복 신호",
        "recent_load": "7일 TRIMP",
        "baseline_load": "28일 주간 기준",
        "workouts_7d": "운동 / 7일",
        "active_days_7d": "활동일 / 7일",
        "duration_7d": "훈련 / 7일",
        "improving": "향상",
        "stable": "안정",
        "declining": "감소"},
}



_RPE_DASHBOARD_TEXT: dict[str, dict[str, str]] = {
    "en": {"rpe_title": "Perceived effort", "rpe_hint": "How hard did this workout feel? Choose a whole number from 1 to 10.", "rpe_saved": "Saved to this workout. Changing it recalculates RPE-based load and comparisons."},
    "el": {"rpe_title": "Αντιληπτή προσπάθεια", "rpe_hint": "Πόσο δύσκολη σου φάνηκε αυτή η προπόνηση; Επίλεξε έναν ακέραιο αριθμό από 1 έως 10.", "rpe_saved": "Αποθηκεύεται σε αυτή την προπόνηση. Η αλλαγή του επανυπολογίζει το φορτίο RPE και τις συγκρίσεις."},
    "de": {"rpe_title": "Empfundene Anstrengung", "rpe_hint": "Wie anstrengend war dieses Training? Wähle eine ganze Zahl von 1 bis 10.", "rpe_saved": "Wird für dieses Training gespeichert. Änderungen berechnen RPE-Last und Vergleiche neu."},
    "fr": {"rpe_title": "Effort perçu", "rpe_hint": "À quel point cet entraînement était-il difficile ? Choisissez un nombre entier de 1 à 10.", "rpe_saved": "Enregistré pour cet entraînement. Toute modification recalcule la charge RPE et les comparaisons."},
    "es": {"rpe_title": "Esfuerzo percibido", "rpe_hint": "¿Qué tan duro se sintió este entrenamiento? Elige un número entero del 1 al 10.", "rpe_saved": "Se guarda en este entrenamiento. Al cambiarlo se recalculan la carga RPE y las comparaciones."},
    "it": {"rpe_title": "Sforzo percepito", "rpe_hint": "Quanto è stato impegnativo questo allenamento? Scegli un numero intero da 1 a 10.", "rpe_saved": "Viene salvato in questo allenamento. Modificarlo ricalcola il carico RPE e i confronti."},
    "pt": {"rpe_title": "Esforço percebido", "rpe_hint": "Quão difícil foi este treino? Escolhe um número inteiro de 1 a 10.", "rpe_saved": "É guardado neste treino. Alterá-lo recalcula a carga RPE e as comparações."},
    "nl": {"rpe_title": "Ervaren inspanning", "rpe_hint": "Hoe zwaar voelde deze training? Kies een geheel getal van 1 tot 10.", "rpe_saved": "Wordt bij deze training opgeslagen. Wijzigen herberekent RPE-belasting en vergelijkingen."},
    "pl": {"rpe_title": "Odczuwany wysiłek", "rpe_hint": "Jak trudny był ten trening? Wybierz liczbę całkowitą od 1 do 10.", "rpe_saved": "Zostaje zapisane dla tego treningu. Zmiana przelicza obciążenie RPE i porównania."},
    "ru": {"rpe_title": "Субъективная нагрузка", "rpe_hint": "Насколько тяжёлой была эта тренировка? Выберите целое число от 1 до 10.", "rpe_saved": "Сохраняется для этой тренировки. Изменение пересчитывает RPE-нагрузку и сравнения."},
    "uk": {"rpe_title": "Суб’єктивне навантаження", "rpe_hint": "Наскільки важким було це тренування? Виберіть ціле число від 1 до 10.", "rpe_saved": "Зберігається для цього тренування. Зміна перераховує RPE-навантаження та порівняння."},
    "tr": {"rpe_title": "Algılanan efor", "rpe_hint": "Bu antrenman ne kadar zor hissettirdi? 1 ile 10 arasında tam sayı seçin.", "rpe_saved": "Bu antrenmana kaydedilir. Değişiklik RPE yükünü ve karşılaştırmaları yeniden hesaplar."},
    "zh": {"rpe_title": "主观用力程度", "rpe_hint": "这次训练感觉有多难？请选择 1 到 10 的整数。", "rpe_saved": "会保存到本次训练。修改后会重新计算 RPE 负荷和相关比较。"},
    "ja": {"rpe_title": "主観的運動強度", "rpe_hint": "このワークアウトはどのくらいきつく感じましたか？1〜10 の整数を選んでください。", "rpe_saved": "このワークアウトに保存されます。変更すると RPE 負荷と比較が再計算されます。"},
    "ko": {"rpe_title": "주관적 운동 강도", "rpe_hint": "이번 운동이 얼마나 힘들게 느껴졌나요? 1에서 10 사이의 정수를 선택하세요.", "rpe_saved": "이 운동에 저장됩니다. 변경하면 RPE 부하와 비교가 다시 계산됩니다."},
}

for _code, _rpe_labels in _RPE_DASHBOARD_TEXT.items():
    _DASHBOARD_TEXT.setdefault(_code, {}).update(_rpe_labels)

_WEIGHT_SCALE_DASHBOARD_TEXT: dict[str, dict[str, str]] = {'en': {'scale_measurement_title': 'New scale measurement',
        'scale_measurement_guess': 'Fitness matched this measurement. Is it correct?',
        'scale_measurement_select_user': 'Who was weighed?',
        'scale_measurement_confirm': 'Confirm',
        'scale_measurement_ignore': 'Ignore',
        'scale_measurement_saving': 'Saving weight…',
        'settings_background_hint': 'Changes are applied after Save. Device discovery and other background updates can take a moment to appear.',
        'settings_applying': 'Applying settings… Background updates may continue for a moment.',
        'settings_saved_background': 'Saved. Background updates may still be finishing.',
        'scale_measurement_user_question': 'New weight value detected: {weight}. Should this be your new weight?',
        'scale_measurement_admin_question': 'New weight value detected: {weight}. Which Fitness user should receive it?',
        'scale_measurement_yes': 'Yes, update',
        'scale_measurement_no': 'No'},
 'el': {'scale_measurement_title': 'Νέα μέτρηση ζυγαριάς',
        'scale_measurement_guess': 'Το Fitness αντιστοίχισε αυτή τη μέτρηση. Είναι σωστό;',
        'scale_measurement_select_user': 'Ποιος ζυγίστηκε;',
        'scale_measurement_confirm': 'Επιβεβαίωση',
        'scale_measurement_ignore': 'Αγνόηση',
        'scale_measurement_saving': 'Αποθήκευση βάρους…',
        'settings_background_hint': 'Οι αλλαγές εφαρμόζονται μετά την Αποθήκευση. Η ανακάλυψη συσκευών και άλλες εργασίες παρασκηνίου μπορεί να χρειαστούν '
                                    'λίγο χρόνο για να εμφανιστούν.',
        'settings_applying': 'Εφαρμογή ρυθμίσεων… Οι εργασίες παρασκηνίου μπορεί να συνεχιστούν για λίγο.',
        'settings_saved_background': 'Αποθηκεύτηκε. Οι εργασίες παρασκηνίου μπορεί να ολοκληρώνονται ακόμη.',
        'scale_measurement_user_question': 'Εντοπίστηκε νέα τιμή βάρους: {weight}. Να γίνει το νέο σας βάρος;',
        'scale_measurement_admin_question': 'Εντοπίστηκε νέα τιμή βάρους: {weight}. Σε ποιον χρήστη Fitness ανήκει;',
        'scale_measurement_yes': 'Ναι, ενημέρωση',
        'scale_measurement_no': 'Όχι'},
 'de': {'scale_measurement_title': 'Neue Waagenmessung',
        'scale_measurement_guess': 'Fitness hat diese Messung zugeordnet. Ist das richtig?',
        'scale_measurement_select_user': 'Wer wurde gewogen?',
        'scale_measurement_confirm': 'Bestätigen',
        'scale_measurement_ignore': 'Ignorieren',
        'scale_measurement_saving': 'Gewicht wird gespeichert…',
        'settings_background_hint': 'Änderungen werden nach Speichern angewendet. Geräteerkennung und andere Hintergrundaktualisierungen können kurz brauchen, '
                                    'bis sie sichtbar sind.',
        'settings_applying': 'Einstellungen werden angewendet… Hintergrundaktualisierungen können noch kurz weiterlaufen.',
        'settings_saved_background': 'Gespeichert. Hintergrundaktualisierungen können noch abgeschlossen werden.',
        'scale_measurement_user_question': 'Neuer Gewichtswert erkannt: {weight}. Soll dies dein neues Gewicht sein?',
        'scale_measurement_admin_question': 'Neuer Gewichtswert erkannt: {weight}. Welchem Fitness-Benutzer gehört er?',
        'scale_measurement_yes': 'Ja, aktualisieren',
        'scale_measurement_no': 'Nein'},
 'fr': {'scale_measurement_title': 'Nouvelle mesure de balance',
        'scale_measurement_guess': 'Fitness a associé cette mesure. Est-ce correct ?',
        'scale_measurement_select_user': 'Qui s’est pesé ?',
        'scale_measurement_confirm': 'Confirmer',
        'scale_measurement_ignore': 'Ignorer',
        'scale_measurement_saving': 'Enregistrement du poids…',
        'settings_background_hint': 'Les modifications sont appliquées après Enregistrer. La détection des appareils et d’autres mises à jour en arrière-plan '
                                    'peuvent mettre un moment à apparaître.',
        'settings_applying': 'Application des réglages… Les mises à jour en arrière-plan peuvent continuer un moment.',
        'settings_saved_background': 'Enregistré. Des mises à jour en arrière-plan peuvent encore se terminer.',
        'scale_measurement_user_question': 'Nouvelle valeur de poids détectée : {weight}. Doit-elle devenir votre nouveau poids ?',
        'scale_measurement_admin_question': 'Nouvelle valeur de poids détectée : {weight}. À quel utilisateur Fitness appartient-elle ?',
        'scale_measurement_yes': 'Oui, mettre à jour',
        'scale_measurement_no': 'Non'},
 'es': {'scale_measurement_title': 'Nueva medición de báscula',
        'scale_measurement_guess': 'Fitness ha asociado esta medición. ¿Es correcto?',
        'scale_measurement_select_user': '¿Quién se pesó?',
        'scale_measurement_confirm': 'Confirmar',
        'scale_measurement_ignore': 'Ignorar',
        'scale_measurement_saving': 'Guardando peso…',
        'settings_background_hint': 'Los cambios se aplican después de Guardar. La detección de dispositivos y otras actualizaciones en segundo plano pueden '
                                    'tardar un momento en aparecer.',
        'settings_applying': 'Aplicando ajustes… Las actualizaciones en segundo plano pueden continuar un momento.',
        'settings_saved_background': 'Guardado. Es posible que aún estén terminando actualizaciones en segundo plano.',
        'scale_measurement_user_question': 'Nuevo valor de peso detectado: {weight}. ¿Debe ser tu nuevo peso?',
        'scale_measurement_admin_question': 'Nuevo valor de peso detectado: {weight}. ¿A qué usuario de Fitness pertenece?',
        'scale_measurement_yes': 'Sí, actualizar',
        'scale_measurement_no': 'No'},
 'it': {'scale_measurement_title': 'Nuova misurazione della bilancia',
        'scale_measurement_guess': 'Fitness ha associato questa misurazione. È corretto?',
        'scale_measurement_select_user': 'Chi si è pesato?',
        'scale_measurement_confirm': 'Conferma',
        'scale_measurement_ignore': 'Ignora',
        'scale_measurement_saving': 'Salvataggio del peso…',
        'settings_background_hint': 'Le modifiche vengono applicate dopo Salva. Il rilevamento dei dispositivi e altri aggiornamenti in background possono '
                                    'richiedere un momento per apparire.',
        'settings_applying': 'Applicazione impostazioni… Gli aggiornamenti in background possono continuare per un momento.',
        'settings_saved_background': 'Salvato. Alcuni aggiornamenti in background potrebbero essere ancora in corso.',
        'scale_measurement_user_question': 'Rilevato un nuovo valore di peso: {weight}. Deve diventare il tuo nuovo peso?',
        'scale_measurement_admin_question': 'Rilevato un nuovo valore di peso: {weight}. A quale utente Fitness appartiene?',
        'scale_measurement_yes': 'Sì, aggiorna',
        'scale_measurement_no': 'No'},
 'pt': {'scale_measurement_title': 'Nova medição da balança',
        'scale_measurement_guess': 'O Fitness associou esta medição. Está correto?',
        'scale_measurement_select_user': 'Quem se pesou?',
        'scale_measurement_confirm': 'Confirmar',
        'scale_measurement_ignore': 'Ignorar',
        'scale_measurement_saving': 'A guardar peso…',
        'settings_background_hint': 'As alterações são aplicadas depois de Guardar. A descoberta de dispositivos e outras atualizações em segundo plano podem '
                                    'demorar um pouco a aparecer.',
        'settings_applying': 'A aplicar definições… As atualizações em segundo plano podem continuar por instantes.',
        'settings_saved_background': 'Guardado. Algumas atualizações em segundo plano podem ainda estar a terminar.',
        'scale_measurement_user_question': 'Novo valor de peso detetado: {weight}. Deve ser o seu novo peso?',
        'scale_measurement_admin_question': 'Novo valor de peso detetado: {weight}. A que utilizador Fitness pertence?',
        'scale_measurement_yes': 'Sim, atualizar',
        'scale_measurement_no': 'Não'},
 'nl': {'scale_measurement_title': 'Nieuwe weegschaalmeting',
        'scale_measurement_guess': 'Fitness heeft deze meting gekoppeld. Klopt dat?',
        'scale_measurement_select_user': 'Wie is gewogen?',
        'scale_measurement_confirm': 'Bevestigen',
        'scale_measurement_ignore': 'Negeren',
        'scale_measurement_saving': 'Gewicht opslaan…',
        'settings_background_hint': 'Wijzigingen worden na Opslaan toegepast. Apparaatdetectie en andere achtergrondupdates kunnen even nodig hebben voordat '
                                    'ze zichtbaar zijn.',
        'settings_applying': 'Instellingen toepassen… Achtergrondupdates kunnen nog even doorgaan.',
        'settings_saved_background': 'Opgeslagen. Achtergrondupdates kunnen nog worden afgerond.',
        'scale_measurement_user_question': 'Nieuwe gewichtswaarde gedetecteerd: {weight}. Moet dit je nieuwe gewicht worden?',
        'scale_measurement_admin_question': 'Nieuwe gewichtswaarde gedetecteerd: {weight}. Bij welke Fitness-gebruiker hoort deze?',
        'scale_measurement_yes': 'Ja, bijwerken',
        'scale_measurement_no': 'Nee'},
 'pl': {'scale_measurement_title': 'Nowy pomiar z wagi',
        'scale_measurement_guess': 'Fitness dopasował ten pomiar. Czy to poprawne?',
        'scale_measurement_select_user': 'Kto się ważył?',
        'scale_measurement_confirm': 'Potwierdź',
        'scale_measurement_ignore': 'Ignoruj',
        'scale_measurement_saving': 'Zapisywanie wagi…',
        'settings_background_hint': 'Zmiany są stosowane po zapisaniu. Wykrywanie urządzeń i inne aktualizacje w tle mogą pojawić się z niewielkim '
                                    'opóźnieniem.',
        'settings_applying': 'Stosowanie ustawień… Aktualizacje w tle mogą jeszcze chwilę trwać.',
        'settings_saved_background': 'Zapisano. Aktualizacje w tle mogą się jeszcze kończyć.',
        'scale_measurement_user_question': 'Wykryto nową wartość wagi: {weight}. Czy ma to być Twoja nowa waga?',
        'scale_measurement_admin_question': 'Wykryto nową wartość wagi: {weight}. Do którego użytkownika Fitness należy?',
        'scale_measurement_yes': 'Tak, zaktualizuj',
        'scale_measurement_no': 'Nie'},
 'ru': {'scale_measurement_title': 'Новое измерение весов',
        'scale_measurement_guess': 'Fitness сопоставил это измерение. Всё верно?',
        'scale_measurement_select_user': 'Кто взвешивался?',
        'scale_measurement_confirm': 'Подтвердить',
        'scale_measurement_ignore': 'Игнорировать',
        'scale_measurement_saving': 'Сохранение веса…',
        'settings_background_hint': 'Изменения применяются после сохранения. Обнаружение устройств и другие фоновые обновления могут появиться не сразу.',
        'settings_applying': 'Применение настроек… Фоновые обновления могут продолжаться ещё некоторое время.',
        'settings_saved_background': 'Сохранено. Фоновые обновления могут ещё завершаться.',
        'scale_measurement_user_question': 'Обнаружено новое значение веса: {weight}. Сделать его вашим новым весом?',
        'scale_measurement_admin_question': 'Обнаружено новое значение веса: {weight}. Какому пользователю Fitness оно принадлежит?',
        'scale_measurement_yes': 'Да, обновить',
        'scale_measurement_no': 'Нет'},
 'uk': {'scale_measurement_title': 'Нове вимірювання ваги',
        'scale_measurement_guess': 'Fitness зіставив це вимірювання. Чи правильно?',
        'scale_measurement_select_user': 'Хто зважувався?',
        'scale_measurement_confirm': 'Підтвердити',
        'scale_measurement_ignore': 'Ігнорувати',
        'scale_measurement_saving': 'Збереження ваги…',
        'settings_background_hint': 'Зміни застосовуються після збереження. Виявлення пристроїв та інші фонові оновлення можуть з’явитися із затримкою.',
        'settings_applying': 'Застосування налаштувань… Фонові оновлення можуть ще тривати.',
        'settings_saved_background': 'Збережено. Фонові оновлення можуть ще завершуватися.',
        'scale_measurement_user_question': 'Виявлено нове значення ваги: {weight}. Зробити його вашою новою вагою?',
        'scale_measurement_admin_question': 'Виявлено нове значення ваги: {weight}. Якому користувачу Fitness воно належить?',
        'scale_measurement_yes': 'Так, оновити',
        'scale_measurement_no': 'Ні'},
 'tr': {'scale_measurement_title': 'Yeni tartı ölçümü',
        'scale_measurement_guess': 'Fitness bu ölçümü eşleştirdi. Doğru mu?',
        'scale_measurement_select_user': 'Kim tartıldı?',
        'scale_measurement_confirm': 'Onayla',
        'scale_measurement_ignore': 'Yoksay',
        'scale_measurement_saving': 'Kilo kaydediliyor…',
        'settings_background_hint': "Değişiklikler Kaydet'ten sonra uygulanır. Cihaz keşfi ve diğer arka plan güncellemelerinin görünmesi biraz sürebilir.",
        'settings_applying': 'Ayarlar uygulanıyor… Arka plan güncellemeleri bir süre daha devam edebilir.',
        'settings_saved_background': 'Kaydedildi. Arka plan güncellemeleri hâlâ tamamlanıyor olabilir.',
        'scale_measurement_user_question': 'Yeni kilo değeri algılandı: {weight}. Yeni kilonuz olarak güncellensin mi?',
        'scale_measurement_admin_question': 'Yeni kilo değeri algılandı: {weight}. Hangi Fitness kullanıcısına ait?',
        'scale_measurement_yes': 'Evet, güncelle',
        'scale_measurement_no': 'Hayır'},
 'zh': {'scale_measurement_title': '新的体重秤测量',
        'scale_measurement_guess': 'Fitness 已匹配此测量。是否正确？',
        'scale_measurement_select_user': '是谁称重？',
        'scale_measurement_confirm': '确认',
        'scale_measurement_ignore': '忽略',
        'scale_measurement_saving': '正在保存体重…',
        'settings_background_hint': '更改会在保存后应用。设备发现和其他后台更新可能需要片刻才会显示。',
        'settings_applying': '正在应用设置… 后台更新可能还会继续片刻。',
        'settings_saved_background': '已保存。后台更新可能仍在完成。',
        'scale_measurement_user_question': '检测到新的体重值：{weight}。要将其设为你的新体重吗？',
        'scale_measurement_admin_question': '检测到新的体重值：{weight}。它属于哪个 Fitness 用户？',
        'scale_measurement_yes': '是，更新',
        'scale_measurement_no': '否'},
 'ja': {'scale_measurement_title': '新しい体重計測定',
        'scale_measurement_guess': 'Fitness がこの測定を割り当てました。正しいですか？',
        'scale_measurement_select_user': '誰が測定しましたか？',
        'scale_measurement_confirm': '確認',
        'scale_measurement_ignore': '無視',
        'scale_measurement_saving': '体重を保存中…',
        'settings_background_hint': '変更は保存後に適用されます。デバイス検出などのバックグラウンド更新は表示まで少し時間がかかる場合があります。',
        'settings_applying': '設定を適用中… バックグラウンド更新がしばらく続く場合があります。',
        'settings_saved_background': '保存しました。バックグラウンド更新がまだ完了中の場合があります。',
        'scale_measurement_user_question': '新しい体重値を検出しました: {weight}。新しい体重として更新しますか？',
        'scale_measurement_admin_question': '新しい体重値を検出しました: {weight}。どの Fitness ユーザーの測定ですか？',
        'scale_measurement_yes': 'はい、更新',
        'scale_measurement_no': 'いいえ'},
 'ko': {'scale_measurement_title': '새 체중계 측정',
        'scale_measurement_guess': 'Fitness가 이 측정을 사용자와 매칭했습니다. 맞나요?',
        'scale_measurement_select_user': '누가 측정했나요?',
        'scale_measurement_confirm': '확인',
        'scale_measurement_ignore': '무시',
        'scale_measurement_saving': '체중 저장 중…',
        'settings_background_hint': '변경 사항은 저장 후 적용됩니다. 기기 검색과 기타 백그라운드 업데이트가 표시되기까지 잠시 걸릴 수 있습니다.',
        'settings_applying': '설정 적용 중… 백그라운드 업데이트가 잠시 계속될 수 있습니다.',
        'settings_saved_background': '저장되었습니다. 백그라운드 업데이트가 아직 완료 중일 수 있습니다.',
        'scale_measurement_user_question': '새 체중 값이 감지되었습니다: {weight}. 새 체중으로 업데이트할까요?',
        'scale_measurement_admin_question': '새 체중 값이 감지되었습니다: {weight}. 어느 Fitness 사용자의 측정인가요?',
        'scale_measurement_yes': '예, 업데이트',
        'scale_measurement_no': '아니요'}}
for _code, _labels in _WEIGHT_SCALE_DASHBOARD_TEXT.items():
    _DASHBOARD_TEXT.setdefault(_code, {}).update(_labels)

_SETTINGS_FLOW_FEEDBACK_TEXT: dict[str, dict[str, str]] = {
    "en": {"settings_opening":"Opening… Some settings pages run bounded background discovery.","settings_changes_not_saved":"Changes were not saved. Returning to the settings menu…"},
    "el": {"settings_opening":"Άνοιγμα… Ορισμένες σελίδες ρυθμίσεων εκτελούν περιορισμένες εργασίες ανακάλυψης στο παρασκήνιο.","settings_changes_not_saved":"Οι αλλαγές δεν αποθηκεύτηκαν. Επιστροφή στο κύριο μενού ρυθμίσεων…"},
    "de": {"settings_opening":"Wird geöffnet… Einige Einstellungsseiten führen begrenzte Hintergrund-Erkennung aus.","settings_changes_not_saved":"Änderungen wurden nicht gespeichert. Zurück zum Einstellungsmenü…"},
    "fr": {"settings_opening":"Ouverture… Certaines pages lancent une détection limitée en arrière-plan.","settings_changes_not_saved":"Les modifications n’ont pas été enregistrées. Retour au menu des réglages…"},
    "es": {"settings_opening":"Abriendo… Algunas páginas ejecutan detección limitada en segundo plano.","settings_changes_not_saved":"Los cambios no se guardaron. Volviendo al menú de ajustes…"},
    "it": {"settings_opening":"Apertura… Alcune pagine eseguono un rilevamento limitato in background.","settings_changes_not_saved":"Le modifiche non sono state salvate. Ritorno al menu impostazioni…"},
    "pt": {"settings_opening":"A abrir… Algumas páginas executam descoberta limitada em segundo plano.","settings_changes_not_saved":"As alterações não foram guardadas. A regressar ao menu de definições…"},
    "nl": {"settings_opening":"Openen… Sommige instellingen voeren begrensde detectie op de achtergrond uit.","settings_changes_not_saved":"Wijzigingen zijn niet opgeslagen. Terug naar het instellingenmenu…"},
    "pl": {"settings_opening":"Otwieranie… Niektóre strony wykonują ograniczone wykrywanie w tle.","settings_changes_not_saved":"Zmiany nie zostały zapisane. Powrót do menu ustawień…"},
    "ru": {"settings_opening":"Открытие… Некоторые страницы выполняют ограниченное фоновое обнаружение.","settings_changes_not_saved":"Изменения не сохранены. Возврат в меню настроек…"},
    "uk": {"settings_opening":"Відкриття… Деякі сторінки виконують обмежене фонове виявлення.","settings_changes_not_saved":"Зміни не збережено. Повернення до меню налаштувань…"},
    "tr": {"settings_opening":"Açılıyor… Bazı ayar sayfaları sınırlı arka plan keşfi çalıştırır.","settings_changes_not_saved":"Değişiklikler kaydedilmedi. Ayarlar menüsüne dönülüyor…"},
    "zh": {"settings_opening":"正在打开… 某些设置页面会执行受限的后台发现。","settings_changes_not_saved":"更改未保存。正在返回设置菜单…"},
    "ja": {"settings_opening":"開いています… 一部の設定ページでは制限されたバックグラウンド検出を実行します。","settings_changes_not_saved":"変更は保存されていません。設定メニューに戻ります…"},
    "ko": {"settings_opening":"여는 중… 일부 설정 페이지는 제한된 백그라운드 검색을 실행합니다.","settings_changes_not_saved":"변경 사항이 저장되지 않았습니다. 설정 메뉴로 돌아갑니다…"},
}
for _code, _labels in _SETTINGS_FLOW_FEEDBACK_TEXT.items():
    _DASHBOARD_TEXT.setdefault(_code, {}).update(_labels)

_RECOVERY_REFINEMENT_TEXT: dict[str, dict[str, str]] = {
    "en": {"recovery_from_last_workout":"Time to recover from last workout","total_recovery":"Total recovery","at_time":"at","baseline":"Baseline","current":"Current","fitness_sleep_score":"Fitness sleep score","recovery_done_short":"Done","ready_at_compact":"Ready at: {time}","remaining_compact":"{time} remaining","certain_compact":"{percent}% certain","minutes_short":"min"},
    "el": {"recovery_from_last_workout":"Χρόνος αποκατάστασης από την τελευταία προπόνηση","total_recovery":"Πλήρης αποκατάσταση","at_time":"στις","baseline":"Βάση","current":"Τώρα","fitness_sleep_score":"Βαθμολογία ύπνου Fitness","recovery_done_short":"Ολοκληρώθηκε","ready_at_compact":"Έτοιμο: {time}","remaining_compact":"απομένουν {time}","certain_compact":"{percent}% βεβαιότητα","minutes_short":"λεπ"},
    "de": {"recovery_from_last_workout":"Erholungszeit nach dem letzten Training","total_recovery":"Vollständig erholt","at_time":"um","baseline":"Basis","current":"Aktuell","fitness_sleep_score":"Fitness-Schlafscore","recovery_done_short":"Fertig","ready_at_compact":"Bereit: {time}","remaining_compact":"{time} verbleibend","certain_compact":"{percent}% sicher","minutes_short":"min"},
    "fr": {"recovery_from_last_workout":"Temps de récupération après le dernier entraînement","total_recovery":"Récupération complète","at_time":"à","baseline":"Référence","current":"Actuel","fitness_sleep_score":"Score de sommeil Fitness","recovery_done_short":"Terminé","ready_at_compact":"Prêt : {time}","remaining_compact":"reste {time}","certain_compact":"{percent} % certain","minutes_short":"min"},
    "es": {"recovery_from_last_workout":"Tiempo de recuperación del último entrenamiento","total_recovery":"Recuperación completa","at_time":"a las","baseline":"Referencia","current":"Actual","fitness_sleep_score":"Puntuación de sueño Fitness","recovery_done_short":"Completado","ready_at_compact":"Listo: {time}","remaining_compact":"quedan {time}","certain_compact":"{percent}% seguro","minutes_short":"min"},
    "it": {"recovery_from_last_workout":"Tempo di recupero dall'ultimo allenamento","total_recovery":"Recupero completo","at_time":"alle","baseline":"Baseline","current":"Attuale","fitness_sleep_score":"Punteggio sonno Fitness","recovery_done_short":"Fatto","ready_at_compact":"Pronto: {time}","remaining_compact":"{time} rimanenti","certain_compact":"{percent}% certo","minutes_short":"min"},
    "pt": {"recovery_from_last_workout":"Tempo de recuperação do último treino","total_recovery":"Recuperação total","at_time":"às","baseline":"Referência","current":"Atual","fitness_sleep_score":"Pontuação de sono Fitness","recovery_done_short":"Concluído","ready_at_compact":"Pronto: {time}","remaining_compact":"{time} restantes","certain_compact":"{percent}% certo","minutes_short":"min"},
    "nl": {"recovery_from_last_workout":"Hersteltijd van de laatste training","total_recovery":"Volledig hersteld","at_time":"om","baseline":"Basislijn","current":"Huidig","fitness_sleep_score":"Fitness-slaapscore","recovery_done_short":"Voltooid","ready_at_compact":"Klaar: {time}","remaining_compact":"{time} resterend","certain_compact":"{percent}% zeker","minutes_short":"min"},
    "pl": {"recovery_from_last_workout":"Czas regeneracji po ostatnim treningu","total_recovery":"Pełna regeneracja","at_time":"o","baseline":"Poziom bazowy","current":"Aktualnie","fitness_sleep_score":"Wynik snu Fitness","recovery_done_short":"Zakończono","ready_at_compact":"Gotowe: {time}","remaining_compact":"pozostało {time}","certain_compact":"{percent}% pewności","minutes_short":"min"},
    "ru": {"recovery_from_last_workout":"Время восстановления после последней тренировки","total_recovery":"Полное восстановление","at_time":"в","baseline":"Базовый уровень","current":"Сейчас","fitness_sleep_score":"Оценка сна Fitness","recovery_done_short":"Завершено","ready_at_compact":"Готово: {time}","remaining_compact":"осталось {time}","certain_compact":"{percent}% уверенности","minutes_short":"мин"},
    "uk": {"recovery_from_last_workout":"Час відновлення після останнього тренування","total_recovery":"Повне відновлення","at_time":"о","baseline":"Базовий рівень","current":"Зараз","fitness_sleep_score":"Оцінка сну Fitness","recovery_done_short":"Завершено","ready_at_compact":"Готово: {time}","remaining_compact":"залишилось {time}","certain_compact":"{percent}% впевненості","minutes_short":"хв"},
    "tr": {"recovery_from_last_workout":"Son antrenmandan toparlanma süresi","total_recovery":"Tam toparlanma","at_time":"saat","baseline":"Baz","current":"Güncel","fitness_sleep_score":"Fitness uyku puanı","recovery_done_short":"Tamam","ready_at_compact":"Hazır: {time}","remaining_compact":"{time} kaldı","certain_compact":"%{percent} kesin","minutes_short":"dk"},
    "zh": {"recovery_from_last_workout":"上次训练后的恢复时间","total_recovery":"完全恢复","at_time":"于","baseline":"基线","current":"当前","fitness_sleep_score":"Fitness 睡眠评分","recovery_done_short":"完成","ready_at_compact":"准备时间：{time}","remaining_compact":"剩余 {time}","certain_compact":"{percent}% 确定","minutes_short":"分"},
    "ja": {"recovery_from_last_workout":"前回ワークアウトからの回復時間","total_recovery":"完全回復","at_time":"時刻","baseline":"ベースライン","current":"現在","fitness_sleep_score":"Fitness 睡眠スコア","recovery_done_short":"完了","ready_at_compact":"準備完了：{time}","remaining_compact":"残り {time}","certain_compact":"確信度 {percent}%","minutes_short":"分"},
    "ko": {"recovery_from_last_workout":"마지막 운동 후 회복 시간","total_recovery":"완전 회복","at_time":"시각","baseline":"기준선","current":"현재","fitness_sleep_score":"Fitness 수면 점수","recovery_done_short":"완료","ready_at_compact":"준비 완료: {time}","remaining_compact":"{time} 남음","certain_compact":"확신도 {percent}%","minutes_short":"분"},
}
for _code, _labels in _RECOVERY_REFINEMENT_TEXT.items():
    _DASHBOARD_TEXT.setdefault(_code, {}).update(_labels)

_SESSION_STATUS_TEXT: dict[str, dict[str, str]] = {
    "en": {"session_status_idle":"Idle","session_status_waiting_for_live_data":"Waiting for live data","session_status_active":"Active","session_status_paused":"Paused","session_status_recovery":"Recovery"},
    "el": {"session_status_idle":"Αδράνεια","session_status_waiting_for_live_data":"Αναμονή ζωντανών δεδομένων","session_status_active":"Ενεργή","session_status_paused":"Σε παύση","session_status_recovery":"Αποκατάσταση"},
    "de": {"session_status_idle":"Inaktiv","session_status_waiting_for_live_data":"Warten auf Live-Daten","session_status_active":"Aktiv","session_status_paused":"Pausiert","session_status_recovery":"Erholung"},
    "fr": {"session_status_idle":"Inactif","session_status_waiting_for_live_data":"En attente de données en direct","session_status_active":"Actif","session_status_paused":"En pause","session_status_recovery":"Récupération"},
    "es": {"session_status_idle":"Inactiva","session_status_waiting_for_live_data":"Esperando datos en vivo","session_status_active":"Activa","session_status_paused":"En pausa","session_status_recovery":"Recuperación"},
    "it": {"session_status_idle":"Inattivo","session_status_waiting_for_live_data":"In attesa di dati live","session_status_active":"Attivo","session_status_paused":"In pausa","session_status_recovery":"Recupero"},
    "pt": {"session_status_idle":"Inativo","session_status_waiting_for_live_data":"A aguardar dados em direto","session_status_active":"Ativo","session_status_paused":"Em pausa","session_status_recovery":"Recuperação"},
    "nl": {"session_status_idle":"Inactief","session_status_waiting_for_live_data":"Wachten op livegegevens","session_status_active":"Actief","session_status_paused":"Gepauzeerd","session_status_recovery":"Herstel"},
    "pl": {"session_status_idle":"Bezczynna","session_status_waiting_for_live_data":"Oczekiwanie na dane na żywo","session_status_active":"Aktywna","session_status_paused":"Wstrzymana","session_status_recovery":"Regeneracja"},
    "ru": {"session_status_idle":"Бездействие","session_status_waiting_for_live_data":"Ожидание данных в реальном времени","session_status_active":"Активна","session_status_paused":"На паузе","session_status_recovery":"Восстановление"},
    "uk": {"session_status_idle":"Бездіяльність","session_status_waiting_for_live_data":"Очікування даних наживо","session_status_active":"Активна","session_status_paused":"На паузі","session_status_recovery":"Відновлення"},
    "tr": {"session_status_idle":"Boşta","session_status_waiting_for_live_data":"Canlı veri bekleniyor","session_status_active":"Aktif","session_status_paused":"Duraklatıldı","session_status_recovery":"Toparlanma"},
    "zh": {"session_status_idle":"空闲","session_status_waiting_for_live_data":"等待实时数据","session_status_active":"进行中","session_status_paused":"已暂停","session_status_recovery":"恢复"},
    "ja": {"session_status_idle":"待機中","session_status_waiting_for_live_data":"ライブデータ待機中","session_status_active":"進行中","session_status_paused":"一時停止","session_status_recovery":"回復"},
    "ko": {"session_status_idle":"대기","session_status_waiting_for_live_data":"실시간 데이터 대기 중","session_status_active":"진행 중","session_status_paused":"일시정지","session_status_recovery":"회복"},
}
for _code, _labels in _SESSION_STATUS_TEXT.items():
    _DASHBOARD_TEXT.setdefault(_code, {}).update(_labels)

# Frontend-only labels belong to the same profile-language payload as the rest of
# the dashboard.  Keeping them here (rather than hard-coding English in JS) makes
# every visible card label, tooltip and interaction control overridable per
# supported language. The audited catalog supplies each legacy gap natively.
_DASHBOARD_UI_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "difference":"Difference", "history":"History", "measurements":"measurements",
        "actual":"Actual", "trend":"Trend", "predicted":"Predicted",
        "below_zoom":"below zoom", "above_zoom":"above zoom",
        "zoom_in":"Zoom in", "zoom_out":"Zoom out", "reset_zoom":"Reset zoom",
        "pan_hint":"Scroll or drag to move · use the buttons or Ctrl/⌘ + wheel to zoom",
        "workout":"Workout", "exercise":"Exercise", "exercises":"exercises",
        "sets":"sets", "reps":"reps", "volume":"Volume", "strength_progression":"Strength progression",
        "total_volume":"Total volume",
        "estimated_1rm_method":"Estimated 1RM uses the Epley formula from valid 1–12 rep sets; it is not a measured 1RM.",
        "no_current_data":"No current Fitness data is available yet.",
        "no_live_data":"No live workout data is available yet.",
        "awake":"Awake", "light_sleep":"Light sleep", "deep_sleep":"Deep sleep", "rem_sleep":"REM sleep",
        "current_marker":"Current", "predicted_marker":"Predicted", "date_axis":"Date",
        "training_minutes_7d":"Training / 7 days",
        "metric_duration":"Duration", "metric_moving_time":"Moving time", "metric_elapsed_time":"Elapsed time",
        "metric_distance":"Distance", "metric_speed":"Speed", "metric_avg_hr":"Average heart rate",
        "metric_max_hr":"Maximum heart rate", "metric_avg_power":"Average power", "metric_max_power":"Maximum power",
        "metric_weighted_power":"Weighted power", "metric_avg_cadence":"Average cadence", "metric_max_cadence":"Maximum cadence",
        "metric_elevation_gain":"Elevation gain", "metric_elevation_loss":"Elevation loss", "metric_calories":"Calories",
        "metric_training_load":"Training load", "metric_vo2max":"VO₂max", "metric_total_reps":"Total reps",
        "metric_exercises":"Exercises", "metric_volume":"Volume", "metric_rpe":"RPE", "metric_trimp":"TRIMP",
        "metric_session_load":"Session load", "metric_aerobic_load":"Aerobic load",
        "metric_high_intensity_load":"High-intensity load", "metric_strength_sets":"Strength sets",
        "metric_estimated_1rm":"Estimated 1RM", "metric_strength_progression":"Strength progression",
        "metric_hrr_60s":"60 s heart-rate recovery", "metric_aerobic_efficiency":"Aerobic efficiency",
        "metric_aerobic_decoupling":"Aerobic decoupling",
    },
    "el": {
        "difference":"Διαφορά", "history":"Ιστορικό", "measurements":"μετρήσεις",
        "actual":"Πραγματικό", "trend":"Τάση", "predicted":"Πρόβλεψη",
        "below_zoom":"κάτω από το εύρος", "above_zoom":"πάνω από το εύρος",
        "zoom_in":"Μεγέθυνση", "zoom_out":"Σμίκρυνση", "reset_zoom":"Επαναφορά ζουμ",
        "pan_hint":"Κύλιση ή σύρσιμο για μετακίνηση · κουμπιά ή Ctrl/⌘ + τροχός για ζουμ",
        "workout":"Προπόνηση", "exercise":"Άσκηση", "exercises":"ασκήσεις",
        "sets":"σετ", "reps":"επαναλήψεις", "volume":"Όγκος", "strength_progression":"Πρόοδος δύναμης",
        "total_volume":"Συνολικός όγκος",
        "estimated_1rm_method":"Το εκτιμώμενο 1RM χρησιμοποιεί τον τύπο Epley από έγκυρα σετ 1–12 επαναλήψεων· δεν είναι μετρημένο 1RM.",
        "no_current_data":"Δεν υπάρχουν ακόμη διαθέσιμα τρέχοντα δεδομένα Fitness.",
        "no_live_data":"Δεν υπάρχουν ακόμη διαθέσιμα δεδομένα ζωντανής προπόνησης.",
        "awake":"Ξύπνιος", "light_sleep":"Ελαφρύς ύπνος", "deep_sleep":"Βαθύς ύπνος", "rem_sleep":"Ύπνος REM",
        "current_marker":"Τρέχον", "predicted_marker":"Πρόβλεψη", "date_axis":"Ημερομηνία",
        "training_minutes_7d":"Προπόνηση / 7 ημέρες",
        "metric_duration":"Διάρκεια", "metric_moving_time":"Χρόνος κίνησης", "metric_elapsed_time":"Συνολικός χρόνος",
        "metric_distance":"Απόσταση", "metric_speed":"Ταχύτητα", "metric_avg_hr":"Μέσος καρδιακός ρυθμός",
        "metric_max_hr":"Μέγιστος καρδιακός ρυθμός", "metric_avg_power":"Μέση ισχύς", "metric_max_power":"Μέγιστη ισχύς",
        "metric_weighted_power":"Σταθμισμένη ισχύς", "metric_avg_cadence":"Μέσος ρυθμός βημάτων", "metric_max_cadence":"Μέγιστος ρυθμός βημάτων",
        "metric_elevation_gain":"Υψομετρική άνοδος", "metric_elevation_loss":"Υψομετρική κάθοδος", "metric_calories":"Θερμίδες",
        "metric_training_load":"Προπονητικό φορτίο", "metric_vo2max":"VO₂max", "metric_total_reps":"Συνολικές επαναλήψεις",
        "metric_exercises":"Ασκήσεις", "metric_volume":"Όγκος", "metric_rpe":"RPE", "metric_trimp":"TRIMP",
        "metric_session_load":"Φορτίο συνεδρίας", "metric_aerobic_load":"Αερόβιο φορτίο",
        "metric_high_intensity_load":"Φορτίο υψηλής έντασης", "metric_strength_sets":"Σετ δύναμης",
        "metric_estimated_1rm":"Εκτιμώμενο 1RM", "metric_strength_progression":"Πρόοδος δύναμης",
        "metric_hrr_60s":"Αποκατάσταση καρδιακού ρυθμού 60 δ.", "metric_aerobic_efficiency":"Αερόβια απόδοση",
        "metric_aerobic_decoupling":"Αερόβια απόκλιση",
    },
    "de": {
        "difference":"Differenz", "history":"Verlauf", "measurements":"Messungen",
        "actual":"Ist", "trend":"Trend", "predicted":"Prognose",
        "below_zoom":"unterhalb des Zooms", "above_zoom":"oberhalb des Zooms",
        "zoom_in":"Vergrößern", "zoom_out":"Verkleinern", "reset_zoom":"Zoom zurücksetzen",
        "pan_hint":"Scrollen oder ziehen zum Verschieben · Schaltflächen oder Strg/⌘ + Mausrad zum Zoomen",
        "workout":"Training", "exercise":"Übung", "exercises":"Übungen", "sets":"Sätze", "reps":"Wiederholungen",
        "volume":"Volumen", "strength_progression":"Kraftfortschritt", "total_volume":"Gesamtvolumen",
        "estimated_1rm_method":"Das geschätzte 1RM verwendet die Epley-Formel aus gültigen Sätzen mit 1–12 Wiederholungen; es ist kein gemessenes 1RM.",
        "no_current_data":"Noch keine aktuellen Fitness-Daten verfügbar.", "no_live_data":"Noch keine Live-Trainingsdaten verfügbar.",
        "awake":"Wach", "light_sleep":"Leichtschlaf", "deep_sleep":"Tiefschlaf", "rem_sleep":"REM-Schlaf",
        "current_marker":"Aktuell", "predicted_marker":"Prognose", "date_axis":"Datum", "training_minutes_7d":"Training / 7 Tage",
        "metric_duration":"Dauer", "metric_moving_time":"Bewegungszeit", "metric_elapsed_time":"Gesamtzeit",
        "metric_distance":"Distanz", "metric_speed":"Geschwindigkeit", "metric_avg_hr":"Ø Herzfrequenz",
        "metric_max_hr":"Max. Herzfrequenz", "metric_avg_power":"Ø Leistung", "metric_max_power":"Max. Leistung",
        "metric_weighted_power":"Gewichtete Leistung", "metric_avg_cadence":"Ø Kadenz", "metric_max_cadence":"Max. Kadenz",
        "metric_elevation_gain":"Höhenmeter", "metric_elevation_loss":"Höhenverlust", "metric_calories":"Kalorien",
        "metric_training_load":"Trainingsbelastung", "metric_vo2max":"VO₂max", "metric_total_reps":"Wiederholungen gesamt",
        "metric_exercises":"Übungen", "metric_volume":"Volumen", "metric_rpe":"RPE", "metric_trimp":"TRIMP",
        "metric_session_load":"Sitzungsbelastung", "metric_aerobic_load":"Aerobe Belastung",
        "metric_high_intensity_load":"Hochintensive Belastung", "metric_strength_sets":"Kraftsätze",
        "metric_estimated_1rm":"Geschätztes 1RM", "metric_strength_progression":"Kraftfortschritt",
        "metric_hrr_60s":"60-s-Herzfrequenz-Erholung", "metric_aerobic_efficiency":"Aerobe Effizienz",
        "metric_aerobic_decoupling":"Aerobe Entkopplung",
    },
    "fr": {"difference":"Différence","history":"Historique","measurements":"mesures","actual":"Réel","trend":"Tendance","predicted":"Prévu","zoom_in":"Zoom avant","zoom_out":"Zoom arrière","reset_zoom":"Réinitialiser le zoom","workout":"Entraînement","exercise":"Exercice","exercises":"exercices","sets":"séries","reps":"répétitions","volume":"Volume","strength_progression":"Progression de force","total_volume":"Volume total","awake":"Éveillé","light_sleep":"Sommeil léger","deep_sleep":"Sommeil profond","rem_sleep":"Sommeil paradoxal","current_marker":"Actuel","predicted_marker":"Prévu","date_axis":"Date"},
    "es": {"difference":"Diferencia","history":"Historial","measurements":"mediciones","actual":"Real","trend":"Tendencia","predicted":"Predicho","zoom_in":"Acercar","zoom_out":"Alejar","reset_zoom":"Restablecer zoom","workout":"Entrenamiento","exercise":"Ejercicio","exercises":"ejercicios","sets":"series","reps":"repeticiones","volume":"Volumen","strength_progression":"Progreso de fuerza","total_volume":"Volumen total","awake":"Despierto","light_sleep":"Sueño ligero","deep_sleep":"Sueño profundo","rem_sleep":"Sueño REM","current_marker":"Actual","predicted_marker":"Predicho","date_axis":"Fecha"},
    "it": {"difference":"Differenza","history":"Storico","measurements":"misurazioni","actual":"Reale","trend":"Tendenza","predicted":"Previsto","zoom_in":"Ingrandisci","zoom_out":"Riduci","reset_zoom":"Reimposta zoom","workout":"Allenamento","exercise":"Esercizio","exercises":"esercizi","sets":"serie","reps":"ripetizioni","volume":"Volume","strength_progression":"Progressione forza","total_volume":"Volume totale","awake":"Sveglio","light_sleep":"Sonno leggero","deep_sleep":"Sonno profondo","rem_sleep":"Sonno REM","current_marker":"Attuale","predicted_marker":"Previsto","date_axis":"Data"},
    "pt": {"difference":"Diferença","history":"Histórico","measurements":"medições","actual":"Real","trend":"Tendência","predicted":"Previsto","zoom_in":"Aumentar zoom","zoom_out":"Diminuir zoom","reset_zoom":"Repor zoom","workout":"Treino","exercise":"Exercício","exercises":"exercícios","sets":"séries","reps":"repetições","volume":"Volume","strength_progression":"Progresso de força","total_volume":"Volume total","awake":"Acordado","light_sleep":"Sono leve","deep_sleep":"Sono profundo","rem_sleep":"Sono REM","current_marker":"Atual","predicted_marker":"Previsto","date_axis":"Data"},
    "nl": {"difference":"Verschil","history":"Geschiedenis","measurements":"metingen","actual":"Werkelijk","trend":"Trend","predicted":"Voorspeld","zoom_in":"Inzoomen","zoom_out":"Uitzoomen","reset_zoom":"Zoom resetten","workout":"Training","exercise":"Oefening","exercises":"oefeningen","sets":"sets","reps":"herhalingen","volume":"Volume","strength_progression":"Krachtvoortgang","total_volume":"Totaal volume","awake":"Wakker","light_sleep":"Lichte slaap","deep_sleep":"Diepe slaap","rem_sleep":"REM-slaap","current_marker":"Huidig","predicted_marker":"Voorspeld","date_axis":"Datum"},
    "pl": {"difference":"Różnica","history":"Historia","measurements":"pomiary","actual":"Rzeczywiste","trend":"Trend","predicted":"Prognoza","zoom_in":"Powiększ","zoom_out":"Pomniejsz","reset_zoom":"Resetuj powiększenie","workout":"Trening","exercise":"Ćwiczenie","exercises":"ćwiczenia","sets":"serie","reps":"powtórzenia","volume":"Objętość","strength_progression":"Postęp siłowy","total_volume":"Łączna objętość","awake":"Czuwanie","light_sleep":"Sen lekki","deep_sleep":"Sen głęboki","rem_sleep":"Sen REM","current_marker":"Aktualne","predicted_marker":"Prognoza","date_axis":"Data"},
    "ru": {"difference":"Разница","history":"История","measurements":"измерения","actual":"Фактическое","trend":"Тренд","predicted":"Прогноз","zoom_in":"Увеличить","zoom_out":"Уменьшить","reset_zoom":"Сбросить масштаб","workout":"Тренировка","exercise":"Упражнение","exercises":"упражнения","sets":"подходы","reps":"повторения","volume":"Объём","strength_progression":"Прогресс силы","total_volume":"Общий объём","awake":"Бодрствование","light_sleep":"Лёгкий сон","deep_sleep":"Глубокий сон","rem_sleep":"REM-сон","current_marker":"Текущее","predicted_marker":"Прогноз","date_axis":"Дата"},
    "uk": {"difference":"Різниця","history":"Історія","measurements":"вимірювання","actual":"Фактичне","trend":"Тренд","predicted":"Прогноз","zoom_in":"Збільшити","zoom_out":"Зменшити","reset_zoom":"Скинути масштаб","workout":"Тренування","exercise":"Вправа","exercises":"вправи","sets":"підходи","reps":"повторення","volume":"Обсяг","strength_progression":"Прогрес сили","total_volume":"Загальний обсяг","awake":"Неспання","light_sleep":"Легкий сон","deep_sleep":"Глибокий сон","rem_sleep":"REM-сон","current_marker":"Поточне","predicted_marker":"Прогноз","date_axis":"Дата"},
    "tr": {"difference":"Fark","history":"Geçmiş","measurements":"ölçüm","actual":"Gerçek","trend":"Eğilim","predicted":"Tahmin","zoom_in":"Yakınlaştır","zoom_out":"Uzaklaştır","reset_zoom":"Yakınlaştırmayı sıfırla","workout":"Antrenman","exercise":"Egzersiz","exercises":"egzersiz","sets":"set","reps":"tekrar","volume":"Hacim","strength_progression":"Kuvvet ilerlemesi","total_volume":"Toplam hacim","awake":"Uyanık","light_sleep":"Hafif uyku","deep_sleep":"Derin uyku","rem_sleep":"REM uykusu","current_marker":"Güncel","predicted_marker":"Tahmin","date_axis":"Tarih"},
    "zh": {"difference":"差值","history":"历史","measurements":"次测量","actual":"实际","trend":"趋势","predicted":"预测","zoom_in":"放大","zoom_out":"缩小","reset_zoom":"重置缩放","workout":"训练","exercise":"动作","exercises":"个动作","sets":"组","reps":"次","volume":"训练量","strength_progression":"力量进展","total_volume":"总训练量","awake":"清醒","light_sleep":"浅睡","deep_sleep":"深睡","rem_sleep":"REM 睡眠","current_marker":"当前","predicted_marker":"预测","date_axis":"日期"},
    "ja": {"difference":"差","history":"履歴","measurements":"測定","actual":"実測","trend":"トレンド","predicted":"予測","zoom_in":"拡大","zoom_out":"縮小","reset_zoom":"ズームをリセット","workout":"ワークアウト","exercise":"種目","exercises":"種目","sets":"セット","reps":"回","volume":"ボリューム","strength_progression":"筋力の進歩","total_volume":"総ボリューム","awake":"覚醒","light_sleep":"浅い睡眠","deep_sleep":"深い睡眠","rem_sleep":"REM 睡眠","current_marker":"現在","predicted_marker":"予測","date_axis":"日付"},
    "ko": {"difference":"차이","history":"기록","measurements":"측정","actual":"실제","trend":"추세","predicted":"예측","zoom_in":"확대","zoom_out":"축소","reset_zoom":"확대/축소 초기화","workout":"운동","exercise":"운동 종목","exercises":"종목","sets":"세트","reps":"회","volume":"볼륨","strength_progression":"근력 향상","total_volume":"총 볼륨","awake":"깨어 있음","light_sleep":"얕은 수면","deep_sleep":"깊은 수면","rem_sleep":"REM 수면","current_marker":"현재","predicted_marker":"예측","date_axis":"날짜"},
}
_TV_DASHBOARD_TEXT: dict[str, dict[str, str]] = {
    "en": {"tv_dashboard":"Fitness TV","tv_profile":"Profile","add_cards":"Add cards","arrange_cards":"Arrange","move_earlier":"Move earlier","move_later":"Move later","card_picker":"Cards on this TV","play":"Play","pause":"Pause","media_browser":"Media browser","now_playing":"Now playing","media_selected":"Selected","nothing_playing":"No music selected","media_browser_back":"Back","media_browser_empty":"No media is available here.","music_only":"Select an audio item to play music.","media_error":"Unable to play this media.","tv_no_profiles":"No Fitness profile has the TV dashboard enabled.","card_today":"Today","card_live_workout":"Live workout","card_workout":"Workout","card_workout_highlights":"Workout highlights","card_workout_rpe":"Workout RPE","card_strength_details":"Strength details","card_sleep_recovery":"Sleep & recovery","card_sleep_stages":"Sleep stages","card_recovery":"Recovery","card_evaluation":"Evaluation","card_progress":"Progress","card_training_adaptation":"Training adaptation","card_training_load":"Training load","card_route":"Route","card_comparison":"Workout comparison","cast_dashboard":'Cast',"cast_dashboard_title":'Cast Fitness TV',"cast_to":'Cast to',"cast_now":'Cast now',"cast_default":'default',"cast_unavailable":'unavailable',"cast_no_targets":'No Google Cast displays are available.',"cast_connecting":"Connecting to TV…","cast_sent":'Dashboard sent to TV.',"cast_failed":'Unable to cast the dashboard.',"cast_stop":"Stop Cast","cast_restarting":"Restarting Cast session…","cast_stopping":"Stopping Cast…","cast_stopped":"Fitness Cast stopped.","cast_stop_failed":"Unable to stop Fitness Cast."},
    "el": {"tv_dashboard":"Fitness TV","tv_profile":"Προφίλ","add_cards":"Προσθήκη καρτών","arrange_cards":"Τακτοποίηση","move_earlier":"Μετακίνηση πριν","move_later":"Μετακίνηση μετά","card_picker":"Κάρτες σε αυτή την TV","play":"Αναπαραγωγή","pause":"Παύση","media_browser":"Περιήγηση πολυμέσων","now_playing":"Αναπαράγεται τώρα","media_selected":"Επιλεγμένο","nothing_playing":"Δεν έχει επιλεγεί μουσική","media_browser_back":"Πίσω","media_browser_empty":"Δεν υπάρχουν διαθέσιμα πολυμέσα εδώ.","music_only":"Επίλεξε ένα στοιχείο ήχου για αναπαραγωγή μουσικής.","media_error":"Δεν ήταν δυνατή η αναπαραγωγή αυτού του πολυμέσου.","tv_no_profiles":"Κανένα προφίλ Fitness δεν έχει ενεργοποιημένο τον πίνακα TV.","card_today":"Σήμερα","card_live_workout":"Ζωντανή προπόνηση","card_workout":"Προπόνηση","card_workout_highlights":"Κύρια στοιχεία προπόνησης","card_workout_rpe":"RPE προπόνησης","card_strength_details":"Λεπτομέρειες δύναμης","card_sleep_recovery":"Ύπνος & αποκατάσταση","card_sleep_stages":"Στάδια ύπνου","card_recovery":"Αποκατάσταση","card_evaluation":"Αξιολόγηση","card_progress":"Πρόοδος","card_training_adaptation":"Προσαρμογή προπόνησης","card_training_load":"Προπονητικό φορτίο","card_route":"Διαδρομή","card_comparison":"Σύγκριση προπόνησης","cast_dashboard":'Μετάδοση',"cast_dashboard_title":'Μετάδοση Fitness TV',"cast_to":'Μετάδοση σε',"cast_now":'Μετάδοση τώρα',"cast_default":'προεπιλογή',"cast_unavailable":'μη διαθέσιμο',"cast_no_targets":'Δεν υπάρχουν διαθέσιμες οθόνες Google Cast.',"cast_connecting":"Σύνδεση με την TV…","cast_sent":'Ο πίνακας στάλθηκε στην TV.',"cast_failed":'Δεν ήταν δυνατή η μετάδοση του πίνακα.',"cast_stop":"Διακοπή μετάδοσης","cast_restarting":"Επανεκκίνηση συνεδρίας Cast…","cast_stopping":"Διακοπή μετάδοσης…","cast_stopped":"Η μετάδοση Fitness σταμάτησε.","cast_stop_failed":"Δεν ήταν δυνατή η διακοπή της μετάδοσης Fitness."},
    "de": {"tv_dashboard":"Fitness TV","tv_profile":"Profil","add_cards":"Karten hinzufügen","arrange_cards":"Anordnen","move_earlier":"Nach vorne","move_later":"Nach hinten","card_picker":"Karten auf diesem TV","play":"Wiedergabe","pause":"Pause","media_browser":"Medienbrowser","now_playing":"Aktuelle Wiedergabe","media_selected":"Ausgewählt","nothing_playing":"Keine Musik ausgewählt","media_browser_back":"Zurück","media_browser_empty":"Hier sind keine Medien verfügbar.","music_only":"Wähle ein Audioelement zum Abspielen von Musik.","media_error":"Dieses Medium kann nicht wiedergegeben werden.","tv_no_profiles":"Für kein Fitness-Profil ist das TV-Dashboard aktiviert.","card_today":"Heute","card_live_workout":"Live-Training","card_workout":"Training","card_workout_highlights":"Trainingshighlights","card_workout_rpe":"Training-RPE","card_strength_details":"Kraftdetails","card_sleep_recovery":"Schlaf & Erholung","card_sleep_stages":"Schlafphasen","card_recovery":"Erholung","card_evaluation":"Auswertung","card_progress":"Fortschritt","card_training_adaptation":"Trainingsanpassung","card_training_load":"Trainingsbelastung","card_route":"Route","card_comparison":"Trainingsvergleich","cast_dashboard":'Cast',"cast_dashboard_title":'Fitness TV übertragen',"cast_to":'Übertragen auf',"cast_now":'Jetzt übertragen',"cast_default":'Standard',"cast_unavailable":'nicht verfügbar',"cast_no_targets":'Keine Google-Cast-Anzeigen verfügbar.',"cast_connecting":"Verbindung zum TV…","cast_sent":'Dashboard an TV gesendet.',"cast_failed":'Dashboard konnte nicht übertragen werden.',"cast_stop":"Cast beenden","cast_restarting":"Cast-Sitzung wird neu gestartet…","cast_stopping":"Cast wird beendet…","cast_stopped":"Fitness-Cast beendet.","cast_stop_failed":"Fitness-Cast konnte nicht beendet werden."},
    "fr": {"tv_dashboard":"Fitness TV","tv_profile":"Profil","add_cards":"Ajouter des cartes","arrange_cards":"Organiser","move_earlier":"Déplacer avant","move_later":"Déplacer après","card_picker":"Cartes sur ce téléviseur","play":"Lecture","pause":"Pause","media_browser":"Navigateur multimédia","now_playing":"Lecture en cours","media_selected":"Sélectionné","nothing_playing":"Aucune musique sélectionnée","media_browser_back":"Retour","media_browser_empty":"Aucun média disponible ici.","music_only":"Sélectionnez un élément audio pour écouter de la musique.","media_error":"Impossible de lire ce média.","tv_no_profiles":"Aucun profil Fitness n’a activé le tableau de bord TV.","card_today":"Aujourd’hui","card_live_workout":"Entraînement en direct","card_workout":"Entraînement","card_workout_highlights":"Points forts de l’entraînement","card_workout_rpe":"RPE de l’entraînement","card_strength_details":"Détails de force","card_sleep_recovery":"Sommeil et récupération","card_sleep_stages":"Phases du sommeil","card_recovery":"Récupération","card_evaluation":"Évaluation","card_progress":"Progression","card_training_adaptation":"Adaptation à l’entraînement","card_training_load":"Charge d’entraînement","card_route":"Parcours","card_comparison":"Comparaison d’entraînement","cast_dashboard":'Caster',"cast_dashboard_title":'Caster Fitness TV',"cast_to":'Caster vers',"cast_now":'Caster maintenant',"cast_default":'par défaut',"cast_unavailable":'indisponible',"cast_no_targets":'Aucun écran Google Cast disponible.',"cast_connecting":"Connexion au téléviseur…","cast_sent":'Tableau de bord envoyé au téléviseur.',"cast_failed":'Impossible de caster le tableau de bord.',"cast_stop":"Arrêter le Cast","cast_restarting":"Redémarrage de la session Cast…","cast_stopping":"Arrêt du Cast…","cast_stopped":"Cast Fitness arrêté.","cast_stop_failed":"Impossible d’arrêter le Cast Fitness."},
    "es": {"tv_dashboard":"Fitness TV","tv_profile":"Perfil","add_cards":"Añadir tarjetas","arrange_cards":"Ordenar","move_earlier":"Mover antes","move_later":"Mover después","card_picker":"Tarjetas en este TV","play":"Reproducir","pause":"Pausa","media_browser":"Explorador multimedia","now_playing":"Reproduciendo","media_selected":"Seleccionado","nothing_playing":"No hay música seleccionada","media_browser_back":"Atrás","media_browser_empty":"No hay contenido multimedia disponible aquí.","music_only":"Selecciona un elemento de audio para reproducir música.","media_error":"No se puede reproducir este contenido.","tv_no_profiles":"Ningún perfil de Fitness tiene activado el panel de TV.","card_today":"Hoy","card_live_workout":"Entrenamiento en vivo","card_workout":"Entrenamiento","card_workout_highlights":"Destacados del entrenamiento","card_workout_rpe":"RPE del entrenamiento","card_strength_details":"Detalles de fuerza","card_sleep_recovery":"Sueño y recuperación","card_sleep_stages":"Fases del sueño","card_recovery":"Recuperación","card_evaluation":"Evaluación","card_progress":"Progreso","card_training_adaptation":"Adaptación al entrenamiento","card_training_load":"Carga de entrenamiento","card_route":"Ruta","card_comparison":"Comparación del entrenamiento","cast_dashboard":'Enviar',"cast_dashboard_title":'Enviar Fitness TV',"cast_to":'Enviar a',"cast_now":'Enviar ahora',"cast_default":'predeterminado',"cast_unavailable":'no disponible',"cast_no_targets":'No hay pantallas Google Cast disponibles.',"cast_connecting":"Conectando al televisor…","cast_sent":'Panel enviado al televisor.',"cast_failed":'No se pudo enviar el panel.',"cast_stop":"Detener envío","cast_restarting":"Reiniciando sesión de Cast…","cast_stopping":"Deteniendo envío…","cast_stopped":"Envío de Fitness detenido.","cast_stop_failed":"No se pudo detener el envío de Fitness."},
    "it": {"tv_dashboard":"Fitness TV","tv_profile":"Profilo","add_cards":"Aggiungi schede","arrange_cards":"Disponi","move_earlier":"Sposta prima","move_later":"Sposta dopo","card_picker":"Schede su questa TV","play":"Riproduci","pause":"Pausa","media_browser":"Browser multimediale","now_playing":"In riproduzione","media_selected":"Selezionato","nothing_playing":"Nessuna musica selezionata","media_browser_back":"Indietro","media_browser_empty":"Nessun contenuto multimediale disponibile qui.","music_only":"Seleziona un elemento audio per riprodurre musica.","media_error":"Impossibile riprodurre questo contenuto.","tv_no_profiles":"Nessun profilo Fitness ha la dashboard TV attivata.","card_today":"Oggi","card_live_workout":"Allenamento live","card_workout":"Allenamento","card_workout_highlights":"Momenti salienti allenamento","card_workout_rpe":"RPE allenamento","card_strength_details":"Dettagli forza","card_sleep_recovery":"Sonno e recupero","card_sleep_stages":"Fasi del sonno","card_recovery":"Recupero","card_evaluation":"Valutazione","card_progress":"Progresso","card_training_adaptation":"Adattamento all’allenamento","card_training_load":"Carico di allenamento","card_route":"Percorso","card_comparison":"Confronto allenamento","cast_dashboard":'Trasmetti',"cast_dashboard_title":'Trasmetti Fitness TV',"cast_to":'Trasmetti su',"cast_now":'Trasmetti ora',"cast_default":'predefinito',"cast_unavailable":'non disponibile',"cast_no_targets":'Nessun display Google Cast disponibile.',"cast_connecting":"Connessione alla TV…","cast_sent":'Dashboard inviata alla TV.',"cast_failed":'Impossibile trasmettere la dashboard.',"cast_stop":"Interrompi Cast","cast_restarting":"Riavvio della sessione Cast…","cast_stopping":"Interruzione Cast…","cast_stopped":"Cast Fitness interrotto.","cast_stop_failed":"Impossibile interrompere il Cast Fitness."},
    "pt": {"tv_dashboard":"Fitness TV","tv_profile":"Perfil","add_cards":"Adicionar cartões","arrange_cards":"Organizar","move_earlier":"Mover antes","move_later":"Mover depois","card_picker":"Cartões nesta TV","play":"Reproduzir","pause":"Pausar","media_browser":"Navegador de mídia","now_playing":"Reproduzindo agora","media_selected":"Selecionado","nothing_playing":"Nenhuma música selecionada","media_browser_back":"Voltar","media_browser_empty":"Nenhuma mídia disponível aqui.","music_only":"Selecione um item de áudio para tocar música.","media_error":"Não foi possível reproduzir esta mídia.","tv_no_profiles":"Nenhum perfil Fitness tem o painel de TV ativado.","card_today":"Hoje","card_live_workout":"Treino ao vivo","card_workout":"Treino","card_workout_highlights":"Destaques do treino","card_workout_rpe":"RPE do treino","card_strength_details":"Detalhes de força","card_sleep_recovery":"Sono e recuperação","card_sleep_stages":"Fases do sono","card_recovery":"Recuperação","card_evaluation":"Avaliação","card_progress":"Progresso","card_training_adaptation":"Adaptação ao treino","card_training_load":"Carga de treino","card_route":"Rota","card_comparison":"Comparação do treino","cast_dashboard":'Transmitir',"cast_dashboard_title":'Transmitir Fitness TV',"cast_to":'Transmitir para',"cast_now":'Transmitir agora',"cast_default":'predefinido',"cast_unavailable":'indisponível',"cast_no_targets":'Nenhum ecrã Google Cast disponível.',"cast_connecting":"A ligar à TV…","cast_sent":'Painel enviado para a TV.',"cast_failed":'Não foi possível transmitir o painel.',"cast_stop":"Parar transmissão","cast_restarting":"Reiniciando sessão de Cast…","cast_stopping":"Parando transmissão…","cast_stopped":"Transmissão Fitness parada.","cast_stop_failed":"Não foi possível parar a transmissão Fitness."},
    "nl": {"tv_dashboard":"Fitness TV","tv_profile":"Profiel","add_cards":"Kaarten toevoegen","arrange_cards":"Ordenen","move_earlier":"Naar voren","move_later":"Naar achteren","card_picker":"Kaarten op deze tv","play":"Afspelen","pause":"Pauze","media_browser":"Mediabrowser","now_playing":"Nu afspelen","media_selected":"Geselecteerd","nothing_playing":"Geen muziek geselecteerd","media_browser_back":"Terug","media_browser_empty":"Hier is geen media beschikbaar.","music_only":"Selecteer een audio-item om muziek af te spelen.","media_error":"Deze media kan niet worden afgespeeld.","tv_no_profiles":"Geen Fitness-profiel heeft het tv-dashboard ingeschakeld.","card_today":"Vandaag","card_live_workout":"Live training","card_workout":"Training","card_workout_highlights":"Trainingshoogtepunten","card_workout_rpe":"Training-RPE","card_strength_details":"Krachtdetails","card_sleep_recovery":"Slaap & herstel","card_sleep_stages":"Slaapfasen","card_recovery":"Herstel","card_evaluation":"Evaluatie","card_progress":"Voortgang","card_training_adaptation":"Trainingsadaptatie","card_training_load":"Trainingsbelasting","card_route":"Route","card_comparison":"Trainingsvergelijking","cast_dashboard":'Casten',"cast_dashboard_title":'Fitness TV casten',"cast_to":'Casten naar',"cast_now":'Nu casten',"cast_default":'standaard',"cast_unavailable":'niet beschikbaar',"cast_no_targets":'Geen Google Cast-schermen beschikbaar.',"cast_connecting":"Verbinden met tv…","cast_sent":'Dashboard naar tv gestuurd.',"cast_failed":'Dashboard kon niet worden gecast.',"cast_stop":"Cast stoppen","cast_restarting":"Cast-sessie wordt opnieuw gestart…","cast_stopping":"Cast wordt gestopt…","cast_stopped":"Fitness-cast gestopt.","cast_stop_failed":"Fitness-cast kon niet worden gestopt."},
    "pl": {"tv_dashboard":"Fitness TV","tv_profile":"Profil","add_cards":"Dodaj karty","arrange_cards":"Ułóż","move_earlier":"Przesuń wcześniej","move_later":"Przesuń później","card_picker":"Karty na tym TV","play":"Odtwórz","pause":"Pauza","media_browser":"Przeglądarka multimediów","now_playing":"Teraz odtwarzane","media_selected":"Wybrano","nothing_playing":"Nie wybrano muzyki","media_browser_back":"Wstecz","media_browser_empty":"Brak dostępnych multimediów.","music_only":"Wybierz element audio, aby odtwarzać muzykę.","media_error":"Nie można odtworzyć tych multimediów.","tv_no_profiles":"Żaden profil Fitness nie ma włączonego panelu TV.","card_today":"Dzisiaj","card_live_workout":"Trening na żywo","card_workout":"Trening","card_workout_highlights":"Najważniejsze dane treningu","card_workout_rpe":"RPE treningu","card_strength_details":"Szczegóły siłowe","card_sleep_recovery":"Sen i regeneracja","card_sleep_stages":"Fazy snu","card_recovery":"Regeneracja","card_evaluation":"Ocena","card_progress":"Postęp","card_training_adaptation":"Adaptacja treningowa","card_training_load":"Obciążenie treningowe","card_route":"Trasa","card_comparison":"Porównanie treningu","cast_dashboard":'Przesyłaj',"cast_dashboard_title":'Przesyłaj Fitness TV',"cast_to":'Przesyłaj do',"cast_now":'Przesyłaj teraz',"cast_default":'domyślne',"cast_unavailable":'niedostępne',"cast_no_targets":'Brak dostępnych ekranów Google Cast.',"cast_connecting":"Łączenie z telewizorem…","cast_sent":'Panel wysłany na telewizor.',"cast_failed":'Nie udało się przesłać panelu.',"cast_stop":"Zatrzymaj Cast","cast_restarting":"Ponowne uruchamianie sesji Cast…","cast_stopping":"Zatrzymywanie Cast…","cast_stopped":"Cast Fitness zatrzymany.","cast_stop_failed":"Nie udało się zatrzymać Cast Fitness."},
    "ru": {"tv_dashboard":"Fitness TV","tv_profile":"Профиль","add_cards":"Добавить карточки","arrange_cards":"Расставить","move_earlier":"Переместить раньше","move_later":"Переместить позже","card_picker":"Карточки на этом ТВ","play":"Воспроизвести","pause":"Пауза","media_browser":"Медиабраузер","now_playing":"Сейчас играет","media_selected":"Выбрано","nothing_playing":"Музыка не выбрана","media_browser_back":"Назад","media_browser_empty":"Здесь нет доступных медиа.","music_only":"Выберите аудиозапись для воспроизведения музыки.","media_error":"Не удалось воспроизвести медиа.","tv_no_profiles":"Ни в одном профиле Fitness не включена ТВ-панель.","card_today":"Сегодня","card_live_workout":"Тренировка в реальном времени","card_workout":"Тренировка","card_workout_highlights":"Основные данные тренировки","card_workout_rpe":"RPE тренировки","card_strength_details":"Силовые показатели","card_sleep_recovery":"Сон и восстановление","card_sleep_stages":"Фазы сна","card_recovery":"Восстановление","card_evaluation":"Оценка","card_progress":"Прогресс","card_training_adaptation":"Адаптация к тренировкам","card_training_load":"Тренировочная нагрузка","card_route":"Маршрут","card_comparison":"Сравнение тренировки","cast_dashboard":'Трансляция',"cast_dashboard_title":'Трансляция Fitness TV',"cast_to":'Транслировать на',"cast_now":'Транслировать',"cast_default":'по умолчанию',"cast_unavailable":'недоступно',"cast_no_targets":'Нет доступных экранов Google Cast.',"cast_connecting":"Подключение к ТВ…","cast_sent":'Панель отправлена на ТВ.',"cast_failed":'Не удалось транслировать панель.',"cast_stop":"Остановить трансляцию","cast_restarting":"Перезапуск сеанса Cast…","cast_stopping":"Остановка трансляции…","cast_stopped":"Трансляция Fitness остановлена.","cast_stop_failed":"Не удалось остановить трансляцию Fitness."},
    "uk": {"tv_dashboard":"Fitness TV","tv_profile":"Профіль","add_cards":"Додати картки","arrange_cards":"Упорядкувати","move_earlier":"Перемістити раніше","move_later":"Перемістити пізніше","card_picker":"Картки на цьому ТВ","play":"Відтворити","pause":"Пауза","media_browser":"Медіабраузер","now_playing":"Зараз відтворюється","media_selected":"Вибрано","nothing_playing":"Музику не вибрано","media_browser_back":"Назад","media_browser_empty":"Тут немає доступних медіа.","music_only":"Виберіть аудіо для відтворення музики.","media_error":"Не вдалося відтворити медіа.","tv_no_profiles":"У жодному профілі Fitness не ввімкнено ТВ-панель.","card_today":"Сьогодні","card_live_workout":"Тренування наживо","card_workout":"Тренування","card_workout_highlights":"Основні дані тренування","card_workout_rpe":"RPE тренування","card_strength_details":"Силові показники","card_sleep_recovery":"Сон і відновлення","card_sleep_stages":"Фази сну","card_recovery":"Відновлення","card_evaluation":"Оцінка","card_progress":"Прогрес","card_training_adaptation":"Адаптація до тренувань","card_training_load":"Тренувальне навантаження","card_route":"Маршрут","card_comparison":"Порівняння тренування","cast_dashboard":'Трансляція',"cast_dashboard_title":'Трансляція Fitness TV',"cast_to":'Транслювати на',"cast_now":'Транслювати',"cast_default":'за замовчуванням',"cast_unavailable":'недоступно',"cast_no_targets":'Немає доступних екранів Google Cast.',"cast_connecting":"Підключення до ТВ…","cast_sent":'Панель надіслано на ТВ.',"cast_failed":'Не вдалося транслювати панель.',"cast_stop":"Зупинити трансляцію","cast_restarting":"Перезапуск сеансу Cast…","cast_stopping":"Зупинка трансляції…","cast_stopped":"Трансляцію Fitness зупинено.","cast_stop_failed":"Не вдалося зупинити трансляцію Fitness."},
    "tr": {"tv_dashboard":"Fitness TV","tv_profile":"Profil","add_cards":"Kart ekle","arrange_cards":"Düzenle","move_earlier":"Öne taşı","move_later":"Arkaya taşı","card_picker":"Bu TV'deki kartlar","play":"Oynat","pause":"Duraklat","media_browser":"Medya tarayıcısı","now_playing":"Şimdi çalıyor","media_selected":"Seçildi","nothing_playing":"Müzik seçilmedi","media_browser_back":"Geri","media_browser_empty":"Burada kullanılabilir medya yok.","music_only":"Müzik çalmak için bir ses öğesi seçin.","media_error":"Bu medya oynatılamadı.","tv_no_profiles":"Hiçbir Fitness profilinde TV paneli etkin değil.","card_today":"Bugün","card_live_workout":"Canlı antrenman","card_workout":"Antrenman","card_workout_highlights":"Antrenman öne çıkanları","card_workout_rpe":"Antrenman RPE","card_strength_details":"Kuvvet ayrıntıları","card_sleep_recovery":"Uyku ve toparlanma","card_sleep_stages":"Uyku evreleri","card_recovery":"Toparlanma","card_evaluation":"Değerlendirme","card_progress":"İlerleme","card_training_adaptation":"Antrenman adaptasyonu","card_training_load":"Antrenman yükü","card_route":"Rota","card_comparison":"Antrenman karşılaştırması","cast_dashboard":'Yayınla',"cast_dashboard_title":'Fitness TV yayınla',"cast_to":'Şuraya yayınla',"cast_now":'Şimdi yayınla',"cast_default":'varsayılan',"cast_unavailable":'kullanılamıyor',"cast_no_targets":'Kullanılabilir Google Cast ekranı yok.',"cast_connecting":"TV’ye bağlanıyor…","cast_sent":'Panel TV’ye gönderildi.',"cast_failed":'Panel yayınlanamadı.',"cast_stop":"Yayını durdur","cast_restarting":"Cast oturumu yeniden başlatılıyor…","cast_stopping":"Yayın durduruluyor…","cast_stopped":"Fitness yayını durduruldu.","cast_stop_failed":"Fitness yayını durdurulamadı."},
    "zh": {"tv_dashboard":"Fitness TV","tv_profile":"个人资料","add_cards":"添加卡片","arrange_cards":"排列","move_earlier":"向前移动","move_later":"向后移动","card_picker":"此电视上的卡片","play":"播放","pause":"暂停","media_browser":"媒体浏览器","now_playing":"正在播放","media_selected":"已选择","nothing_playing":"未选择音乐","media_browser_back":"返回","media_browser_empty":"此处没有可用媒体。","music_only":"选择音频项目以播放音乐。","media_error":"无法播放此媒体。","tv_no_profiles":"没有 Fitness 个人资料启用电视仪表板。","card_today":"今天","card_live_workout":"实时训练","card_workout":"训练","card_workout_highlights":"训练亮点","card_workout_rpe":"训练 RPE","card_strength_details":"力量详情","card_sleep_recovery":"睡眠与恢复","card_sleep_stages":"睡眠阶段","card_recovery":"恢复","card_evaluation":"评估","card_progress":"进度","card_training_adaptation":"训练适应","card_training_load":"训练负荷","card_route":"路线","card_comparison":"训练对比","cast_dashboard":'投屏',"cast_dashboard_title":'投屏 Fitness TV',"cast_to":'投屏到',"cast_now":'立即投屏',"cast_default":'默认',"cast_unavailable":'不可用',"cast_no_targets":'没有可用的 Google Cast 显示设备。',"cast_connecting":"正在连接电视…","cast_sent":'仪表板已发送到电视。',"cast_failed":'无法投屏仪表板。',"cast_stop":"停止投屏","cast_restarting":"正在重新启动 Cast 会话…","cast_stopping":"正在停止投屏…","cast_stopped":"Fitness 投屏已停止。","cast_stop_failed":"无法停止 Fitness 投屏。"},
    "ja": {"tv_dashboard":"Fitness TV","tv_profile":"プロフィール","add_cards":"カードを追加","arrange_cards":"並べ替え","move_earlier":"前へ移動","move_later":"後ろへ移動","card_picker":"このテレビのカード","play":"再生","pause":"一時停止","media_browser":"メディアブラウザー","now_playing":"再生中","media_selected":"選択済み","nothing_playing":"音楽が選択されていません","media_browser_back":"戻る","media_browser_empty":"ここには利用可能なメディアがありません。","music_only":"音楽を再生するにはオーディオ項目を選択してください。","media_error":"このメディアを再生できません。","tv_no_profiles":"TVダッシュボードが有効なFitnessプロフィールはありません。","card_today":"今日","card_live_workout":"ライブワークアウト","card_workout":"ワークアウト","card_workout_highlights":"ワークアウトのハイライト","card_workout_rpe":"ワークアウトRPE","card_strength_details":"筋力の詳細","card_sleep_recovery":"睡眠と回復","card_sleep_stages":"睡眠ステージ","card_recovery":"回復","card_evaluation":"評価","card_progress":"進捗","card_training_adaptation":"トレーニング適応","card_training_load":"トレーニング負荷","card_route":"ルート","card_comparison":"ワークアウト比較","cast_dashboard":'キャスト',"cast_dashboard_title":'Fitness TV をキャスト',"cast_to":'キャスト先',"cast_now":'今すぐキャスト',"cast_default":'デフォルト',"cast_unavailable":'利用不可',"cast_no_targets":'利用可能な Google Cast ディスプレイがありません。',"cast_connecting":"テレビに接続中…","cast_sent":'ダッシュボードをテレビに送信しました。',"cast_failed":'ダッシュボードをキャストできませんでした。',"cast_stop":"キャストを停止","cast_restarting":"Cast セッションを再起動中…","cast_stopping":"キャストを停止中…","cast_stopped":"Fitness キャストを停止しました。","cast_stop_failed":"Fitness キャストを停止できませんでした。"},
    "ko": {"tv_dashboard":"Fitness TV","tv_profile":"프로필","add_cards":"카드 추가","arrange_cards":"정렬","move_earlier":"앞으로 이동","move_later":"뒤로 이동","card_picker":"이 TV의 카드","play":"재생","pause":"일시정지","media_browser":"미디어 브라우저","now_playing":"지금 재생 중","media_selected":"선택됨","nothing_playing":"선택된 음악 없음","media_browser_back":"뒤로","media_browser_empty":"여기에 사용 가능한 미디어가 없습니다.","music_only":"음악을 재생하려면 오디오 항목을 선택하세요.","media_error":"이 미디어를 재생할 수 없습니다.","tv_no_profiles":"TV 대시보드를 활성화한 Fitness 프로필이 없습니다.","card_today":"오늘","card_live_workout":"실시간 운동","card_workout":"운동","card_workout_highlights":"운동 주요 정보","card_workout_rpe":"운동 RPE","card_strength_details":"근력 세부 정보","card_sleep_recovery":"수면 및 회복","card_sleep_stages":"수면 단계","card_recovery":"회복","card_evaluation":"평가","card_progress":"진행","card_training_adaptation":"훈련 적응","card_training_load":"훈련 부하","card_route":"경로","card_comparison":"운동 비교","cast_dashboard":'캐스트',"cast_dashboard_title":'Fitness TV 캐스트',"cast_to":'캐스트 대상',"cast_now":'지금 캐스트',"cast_default":'기본값',"cast_unavailable":'사용 불가',"cast_no_targets":'사용 가능한 Google Cast 디스플레이가 없습니다.',"cast_connecting":"TV에 연결 중…","cast_sent":'대시보드를 TV로 보냈습니다.',"cast_failed":'대시보드를 캐스트할 수 없습니다.',"cast_stop":"캐스트 중지","cast_restarting":"Cast 세션 다시 시작 중…","cast_stopping":"캐스트 중지 중…","cast_stopped":"Fitness 캐스트가 중지되었습니다.","cast_stop_failed":"Fitness 캐스트를 중지할 수 없습니다."},
}

_TV_DASHBOARD_SETTINGS_TEXT: dict[str, dict[str, str]] = {
    "en": {"tv_profiles":"Profiles","reconfigure":"Configure","reconfigure_profile":"Configure profile","tv_setup":"Fitness TV setup","tv_setup_hint":"Choose which Fitness profiles have their own TV page and configure each TV, music and TTS experience independently.","add_tv_profile":"Add profile","manage_profiles":"Manage Fitness profiles","no_tv_profiles":"No TV profile is enabled yet.","all_profiles_enabled":"All Fitness profiles already have a TV page.","no_default_tv":"No default TV","default_tv":"Default Cast TV","enable_tv_view":"Enable Fitness TV view","enable_tv_view_hint":"Show a dedicated TV page for this profile.","tts_ducking":"TTS music ducking","tts_ducking_hint":"Music volume while Fitness speaks.","tts_ducking_short":"Duck","tv_scale":"TV card scale","tv_scale_hint":"Smaller values fit more information on the TV.","tv_scale_short":"Scale","oled_protection":"OLED protection","oled_protection_hint":"Periodically shifts the dashboard and dims the static toolbar when idle.","oled_short":"OLED","open":"Open","disable_tv_view":"Disable TV view","save":"Save","saving":"Saving…","saved":"Saved","save_failed":"Unable to save settings."},
    "el": {"tv_profiles":"Προφίλ","reconfigure":"Ρύθμιση","reconfigure_profile":"Ρύθμιση προφίλ","tv_setup":"Ρύθμιση Fitness TV","tv_setup_hint":"Επίλεξε ποια προφίλ Fitness έχουν δική τους σελίδα TV και ρύθμισε ανεξάρτητα TV, μουσική και TTS.","add_tv_profile":"Προσθήκη προφίλ","manage_profiles":"Διαχείριση προφίλ Fitness","no_tv_profiles":"Δεν έχει ενεργοποιηθεί ακόμη προφίλ TV.","all_profiles_enabled":"Όλα τα προφίλ Fitness έχουν ήδη σελίδα TV.","no_default_tv":"Χωρίς προεπιλεγμένη TV","default_tv":"Προεπιλεγμένη Cast TV","enable_tv_view":"Ενεργοποίηση προβολής Fitness TV","enable_tv_view_hint":"Εμφάνιση ξεχωριστής σελίδας TV για αυτό το προφίλ.","tts_ducking":"Μείωση μουσικής για TTS","tts_ducking_hint":"Ένταση μουσικής όσο μιλά το Fitness.","tts_ducking_short":"Μείωση","tv_scale":"Κλίμακα καρτών TV","tv_scale_hint":"Μικρότερη τιμή χωρά περισσότερες πληροφορίες στην TV.","tv_scale_short":"Κλίμακα","oled_protection":"Προστασία OLED","oled_protection_hint":"Μετακινεί περιοδικά τον πίνακα και χαμηλώνει τη στατική μπάρα όταν είναι ανενεργή.","oled_short":"OLED","open":"Άνοιγμα","disable_tv_view":"Απενεργοποίηση προβολής TV","save":"Αποθήκευση","saving":"Αποθήκευση…","saved":"Αποθηκεύτηκε","save_failed":"Δεν ήταν δυνατή η αποθήκευση των ρυθμίσεων."},
    "de": {"tv_profiles":"Profile","reconfigure":"Konfigurieren","reconfigure_profile":"Profil konfigurieren","tv_setup":"Fitness-TV-Einrichtung","tv_setup_hint":"Wähle Profile mit eigener TV-Seite und konfiguriere TV, Musik und TTS unabhängig.","add_tv_profile":"Profil hinzufügen","manage_profiles":"Fitness-Profile verwalten","no_tv_profiles":"Noch kein TV-Profil aktiviert.","all_profiles_enabled":"Alle Fitness-Profile haben bereits eine TV-Seite.","no_default_tv":"Kein Standard-TV","default_tv":"Standard-Cast-TV","enable_tv_view":"Fitness-TV-Ansicht aktivieren","enable_tv_view_hint":"Eigene TV-Seite für dieses Profil anzeigen.","tts_ducking":"TTS-Musikabsenkung","tts_ducking_hint":"Musiklautstärke während Fitness spricht.","tts_ducking_short":"Absenkung","tv_scale":"TV-Kartenskalierung","tv_scale_hint":"Kleinere Werte zeigen mehr Informationen auf dem TV.","tv_scale_short":"Skala","oled_protection":"OLED-Schutz","oled_protection_hint":"Verschiebt das Dashboard regelmäßig und dimmt die statische Leiste bei Inaktivität.","oled_short":"OLED","open":"Öffnen","disable_tv_view":"TV-Ansicht deaktivieren","save":"Speichern","saving":"Speichern…","saved":"Gespeichert","save_failed":"Einstellungen konnten nicht gespeichert werden."},
    "fr": {"tv_profiles":"Profils","reconfigure":"Configurer","reconfigure_profile":"Configurer le profil","tv_setup":"Configuration Fitness TV","tv_setup_hint":"Choisissez les profils avec leur propre page TV et configurez TV, musique et TTS séparément.","add_tv_profile":"Ajouter un profil","manage_profiles":"Gérer les profils Fitness","no_tv_profiles":"Aucun profil TV n’est encore activé.","all_profiles_enabled":"Tous les profils Fitness ont déjà une page TV.","no_default_tv":"Aucun téléviseur par défaut","default_tv":"Téléviseur Cast par défaut","enable_tv_view":"Activer la vue Fitness TV","enable_tv_view_hint":"Afficher une page TV dédiée pour ce profil.","tts_ducking":"Atténuation musique TTS","tts_ducking_hint":"Volume de la musique pendant que Fitness parle.","tts_ducking_short":"Atténuation","tv_scale":"Échelle des cartes TV","tv_scale_hint":"Une valeur plus petite affiche plus d’informations.","tv_scale_short":"Échelle","oled_protection":"Protection OLED","oled_protection_hint":"Décale périodiquement le tableau et atténue la barre statique au repos.","oled_short":"OLED","open":"Ouvrir","disable_tv_view":"Désactiver la vue TV","save":"Enregistrer","saving":"Enregistrement…","saved":"Enregistré","save_failed":"Impossible d’enregistrer les paramètres."},
    "es": {"tv_profiles":"Perfiles","reconfigure":"Configurar","reconfigure_profile":"Configurar perfil","tv_setup":"Configuración de Fitness TV","tv_setup_hint":"Elige qué perfiles tienen su propia página de TV y configura TV, música y TTS de forma independiente.","add_tv_profile":"Añadir perfil","manage_profiles":"Gestionar perfiles Fitness","no_tv_profiles":"Aún no hay perfiles de TV activados.","all_profiles_enabled":"Todos los perfiles Fitness ya tienen una página de TV.","no_default_tv":"Sin TV predeterminada","default_tv":"TV Cast predeterminada","enable_tv_view":"Activar vista Fitness TV","enable_tv_view_hint":"Mostrar una página de TV dedicada para este perfil.","tts_ducking":"Reducción de música TTS","tts_ducking_hint":"Volumen de música mientras Fitness habla.","tts_ducking_short":"Reducción","tv_scale":"Escala de tarjetas TV","tv_scale_hint":"Valores menores muestran más información en la TV.","tv_scale_short":"Escala","oled_protection":"Protección OLED","oled_protection_hint":"Desplaza periódicamente el panel y atenúa la barra estática cuando está inactivo.","oled_short":"OLED","open":"Abrir","disable_tv_view":"Desactivar vista TV","save":"Guardar","saving":"Guardando…","saved":"Guardado","save_failed":"No se pudieron guardar los ajustes."},
    "it": {"tv_profiles":"Profili","reconfigure":"Configura","reconfigure_profile":"Configura profilo","tv_setup":"Configurazione Fitness TV","tv_setup_hint":"Scegli i profili con una pagina TV propria e configura TV, musica e TTS separatamente.","add_tv_profile":"Aggiungi profilo","manage_profiles":"Gestisci profili Fitness","no_tv_profiles":"Nessun profilo TV è ancora attivo.","all_profiles_enabled":"Tutti i profili Fitness hanno già una pagina TV.","no_default_tv":"Nessuna TV predefinita","default_tv":"TV Cast predefinita","enable_tv_view":"Abilita vista Fitness TV","enable_tv_view_hint":"Mostra una pagina TV dedicata per questo profilo.","tts_ducking":"Riduzione musica TTS","tts_ducking_hint":"Volume della musica mentre Fitness parla.","tts_ducking_short":"Riduzione","tv_scale":"Scala schede TV","tv_scale_hint":"Valori più piccoli mostrano più informazioni sulla TV.","tv_scale_short":"Scala","oled_protection":"Protezione OLED","oled_protection_hint":"Sposta periodicamente il dashboard e attenua la barra statica quando inattivo.","oled_short":"OLED","open":"Apri","disable_tv_view":"Disabilita vista TV","save":"Salva","saving":"Salvataggio…","saved":"Salvato","save_failed":"Impossibile salvare le impostazioni."},
    "pt": {"tv_profiles":"Perfis","reconfigure":"Configurar","reconfigure_profile":"Configurar perfil","tv_setup":"Configuração Fitness TV","tv_setup_hint":"Escolha os perfis com página TV própria e configure TV, música e TTS de forma independente.","add_tv_profile":"Adicionar perfil","manage_profiles":"Gerir perfis Fitness","no_tv_profiles":"Ainda não há perfis TV ativos.","all_profiles_enabled":"Todos os perfis Fitness já têm uma página TV.","no_default_tv":"Sem TV predefinida","default_tv":"TV Cast predefinida","enable_tv_view":"Ativar vista Fitness TV","enable_tv_view_hint":"Mostrar uma página TV dedicada para este perfil.","tts_ducking":"Redução da música no TTS","tts_ducking_hint":"Volume da música enquanto o Fitness fala.","tts_ducking_short":"Redução","tv_scale":"Escala dos cartões TV","tv_scale_hint":"Valores menores mostram mais informação na TV.","tv_scale_short":"Escala","oled_protection":"Proteção OLED","oled_protection_hint":"Desloca periodicamente o painel e reduz a barra estática quando inativo.","oled_short":"OLED","open":"Abrir","disable_tv_view":"Desativar vista TV","save":"Guardar","saving":"A guardar…","saved":"Guardado","save_failed":"Não foi possível guardar as definições."},
    "nl": {"tv_profiles":"Profielen","reconfigure":"Configureren","reconfigure_profile":"Profiel configureren","tv_setup":"Fitness TV instellen","tv_setup_hint":"Kies profielen met een eigen TV-pagina en configureer TV, muziek en TTS afzonderlijk.","add_tv_profile":"Profiel toevoegen","manage_profiles":"Fitness-profielen beheren","no_tv_profiles":"Nog geen TV-profiel ingeschakeld.","all_profiles_enabled":"Alle Fitness-profielen hebben al een TV-pagina.","no_default_tv":"Geen standaard-TV","default_tv":"Standaard Cast-TV","enable_tv_view":"Fitness TV-weergave inschakelen","enable_tv_view_hint":"Toon een aparte TV-pagina voor dit profiel.","tts_ducking":"TTS-muziekdemping","tts_ducking_hint":"Muziekvolume terwijl Fitness spreekt.","tts_ducking_short":"Demping","tv_scale":"TV-kaartschaal","tv_scale_hint":"Kleinere waarden tonen meer informatie op TV.","tv_scale_short":"Schaal","oled_protection":"OLED-bescherming","oled_protection_hint":"Verschuift het dashboard periodiek en dimt de statische balk bij inactiviteit.","oled_short":"OLED","open":"Openen","disable_tv_view":"TV-weergave uitschakelen","save":"Opslaan","saving":"Opslaan…","saved":"Opgeslagen","save_failed":"Instellingen konden niet worden opgeslagen."},
    "pl": {"tv_profiles":"Profile","reconfigure":"Konfiguruj","reconfigure_profile":"Konfiguruj profil","tv_setup":"Konfiguracja Fitness TV","tv_setup_hint":"Wybierz profile z własną stroną TV i niezależnie ustaw TV, muzykę i TTS.","add_tv_profile":"Dodaj profil","manage_profiles":"Zarządzaj profilami Fitness","no_tv_profiles":"Nie włączono jeszcze profilu TV.","all_profiles_enabled":"Wszystkie profile Fitness mają już stronę TV.","no_default_tv":"Brak domyślnego TV","default_tv":"Domyślny TV Cast","enable_tv_view":"Włącz widok Fitness TV","enable_tv_view_hint":"Pokaż osobną stronę TV dla tego profilu.","tts_ducking":"Ściszanie muzyki TTS","tts_ducking_hint":"Głośność muzyki podczas komunikatów Fitness.","tts_ducking_short":"Ściszenie","tv_scale":"Skala kart TV","tv_scale_hint":"Mniejsze wartości pokazują więcej informacji na TV.","tv_scale_short":"Skala","oled_protection":"Ochrona OLED","oled_protection_hint":"Okresowo przesuwa panel i przyciemnia statyczny pasek podczas bezczynności.","oled_short":"OLED","open":"Otwórz","disable_tv_view":"Wyłącz widok TV","save":"Zapisz","saving":"Zapisywanie…","saved":"Zapisano","save_failed":"Nie udało się zapisać ustawień."},
    "ru": {"tv_profiles":"Профили","reconfigure":"Настроить","reconfigure_profile":"Настроить профиль","tv_setup":"Настройка Fitness TV","tv_setup_hint":"Выберите профили с собственной ТВ-страницей и отдельно настройте ТВ, музыку и TTS.","add_tv_profile":"Добавить профиль","manage_profiles":"Управление профилями Fitness","no_tv_profiles":"ТВ-профили пока не включены.","all_profiles_enabled":"У всех профилей Fitness уже есть ТВ-страница.","no_default_tv":"Нет ТВ по умолчанию","default_tv":"Cast TV по умолчанию","enable_tv_view":"Включить вид Fitness TV","enable_tv_view_hint":"Показывать отдельную ТВ-страницу для этого профиля.","tts_ducking":"Приглушение музыки TTS","tts_ducking_hint":"Громкость музыки, пока Fitness говорит.","tts_ducking_short":"Приглушение","tv_scale":"Масштаб карточек ТВ","tv_scale_hint":"Меньшее значение показывает больше информации на ТВ.","tv_scale_short":"Масштаб","oled_protection":"Защита OLED","oled_protection_hint":"Периодически смещает панель и затемняет статическую строку при бездействии.","oled_short":"OLED","open":"Открыть","disable_tv_view":"Отключить ТВ-вид","save":"Сохранить","saving":"Сохранение…","saved":"Сохранено","save_failed":"Не удалось сохранить настройки."},
    "uk": {"tv_profiles":"Профілі","reconfigure":"Налаштувати","reconfigure_profile":"Налаштувати профіль","tv_setup":"Налаштування Fitness TV","tv_setup_hint":"Виберіть профілі з власною TV-сторінкою та окремо налаштуйте TV, музику й TTS.","add_tv_profile":"Додати профіль","manage_profiles":"Керувати профілями Fitness","no_tv_profiles":"TV-профілі ще не ввімкнені.","all_profiles_enabled":"Усі профілі Fitness вже мають TV-сторінку.","no_default_tv":"Немає TV за замовчуванням","default_tv":"Cast TV за замовчуванням","enable_tv_view":"Увімкнути вигляд Fitness TV","enable_tv_view_hint":"Показувати окрему TV-сторінку для цього профілю.","tts_ducking":"Приглушення музики TTS","tts_ducking_hint":"Гучність музики, поки Fitness говорить.","tts_ducking_short":"Приглушення","tv_scale":"Масштаб карток TV","tv_scale_hint":"Менше значення показує більше інформації на TV.","tv_scale_short":"Масштаб","oled_protection":"Захист OLED","oled_protection_hint":"Періодично зміщує панель і затемнює статичну смугу під час бездіяльності.","oled_short":"OLED","open":"Відкрити","disable_tv_view":"Вимкнути TV-вигляд","save":"Зберегти","saving":"Збереження…","saved":"Збережено","save_failed":"Не вдалося зберегти налаштування."},
    "tr": {"tv_profiles":"Profiller","reconfigure":"Yapılandır","reconfigure_profile":"Profili yapılandır","tv_setup":"Fitness TV kurulumu","tv_setup_hint":"Kendi TV sayfası olan profilleri seçin ve TV, müzik ile TTS'yi bağımsız yapılandırın.","add_tv_profile":"Profil ekle","manage_profiles":"Fitness profillerini yönet","no_tv_profiles":"Henüz TV profili etkin değil.","all_profiles_enabled":"Tüm Fitness profillerinin zaten TV sayfası var.","no_default_tv":"Varsayılan TV yok","default_tv":"Varsayılan Cast TV","enable_tv_view":"Fitness TV görünümünü etkinleştir","enable_tv_view_hint":"Bu profil için özel bir TV sayfası göster.","tts_ducking":"TTS müzik azaltma","tts_ducking_hint":"Fitness konuşurken müzik seviyesi.","tts_ducking_short":"Azaltma","tv_scale":"TV kart ölçeği","tv_scale_hint":"Daha küçük değerler TV'de daha fazla bilgi gösterir.","tv_scale_short":"Ölçek","oled_protection":"OLED koruması","oled_protection_hint":"Paneli düzenli olarak kaydırır ve boşta statik çubuğu karartır.","oled_short":"OLED","open":"Aç","disable_tv_view":"TV görünümünü kapat","save":"Kaydet","saving":"Kaydediliyor…","saved":"Kaydedildi","save_failed":"Ayarlar kaydedilemedi."},
    "zh": {"tv_profiles":"个人资料","reconfigure":"配置","reconfigure_profile":"配置个人资料","tv_setup":"Fitness TV 设置","tv_setup_hint":"选择拥有独立电视页面的 Fitness 个人资料，并分别配置电视、音乐和 TTS。","add_tv_profile":"添加个人资料","manage_profiles":"管理 Fitness 个人资料","no_tv_profiles":"尚未启用电视个人资料。","all_profiles_enabled":"所有 Fitness 个人资料都已有电视页面。","no_default_tv":"无默认电视","default_tv":"默认 Cast 电视","enable_tv_view":"启用 Fitness TV 视图","enable_tv_view_hint":"为此个人资料显示专用电视页面。","tts_ducking":"TTS 音乐压低","tts_ducking_hint":"Fitness 讲话时的音乐音量。","tts_ducking_short":"压低","tv_scale":"电视卡片缩放","tv_scale_hint":"较小值可在电视上显示更多信息。","tv_scale_short":"缩放","oled_protection":"OLED 保护","oled_protection_hint":"定期轻微移动仪表板，并在空闲时降低静态工具栏亮度。","oled_short":"OLED","open":"打开","disable_tv_view":"禁用电视视图","save":"保存","saving":"正在保存…","saved":"已保存","save_failed":"无法保存设置。"},
    "ja": {"tv_profiles":"プロフィール","reconfigure":"設定","reconfigure_profile":"プロフィール設定","tv_setup":"Fitness TV 設定","tv_setup_hint":"専用TVページを持つプロフィールを選び、TV・音楽・TTSを個別に設定します。","add_tv_profile":"プロフィールを追加","manage_profiles":"Fitnessプロフィールを管理","no_tv_profiles":"TVプロフィールはまだ有効になっていません。","all_profiles_enabled":"すべてのFitnessプロフィールにTVページがあります。","no_default_tv":"既定のTVなし","default_tv":"既定のCast TV","enable_tv_view":"Fitness TV表示を有効化","enable_tv_view_hint":"このプロフィール専用のTVページを表示します。","tts_ducking":"TTS時の音楽低減","tts_ducking_hint":"Fitnessが話している間の音楽音量。","tts_ducking_short":"低減","tv_scale":"TVカード倍率","tv_scale_hint":"小さい値ほどTVに多くの情報を表示します。","tv_scale_short":"倍率","oled_protection":"OLED保護","oled_protection_hint":"ダッシュボードを定期的に移動し、アイドル時に静的ツールバーを暗くします。","oled_short":"OLED","open":"開く","disable_tv_view":"TV表示を無効化","save":"保存","saving":"保存中…","saved":"保存済み","save_failed":"設定を保存できませんでした。"},
    "ko": {"tv_profiles":"프로필","reconfigure":"구성","reconfigure_profile":"프로필 구성","tv_setup":"Fitness TV 설정","tv_setup_hint":"각 TV 페이지를 사용할 프로필을 선택하고 TV, 음악, TTS를 독립적으로 구성합니다.","add_tv_profile":"프로필 추가","manage_profiles":"Fitness 프로필 관리","no_tv_profiles":"아직 활성화된 TV 프로필이 없습니다.","all_profiles_enabled":"모든 Fitness 프로필에 이미 TV 페이지가 있습니다.","no_default_tv":"기본 TV 없음","default_tv":"기본 Cast TV","enable_tv_view":"Fitness TV 보기 활성화","enable_tv_view_hint":"이 프로필 전용 TV 페이지를 표시합니다.","tts_ducking":"TTS 음악 줄이기","tts_ducking_hint":"Fitness가 말하는 동안의 음악 음량입니다.","tts_ducking_short":"줄이기","tv_scale":"TV 카드 배율","tv_scale_hint":"값이 작을수록 TV에 더 많은 정보를 표시합니다.","tv_scale_short":"배율","oled_protection":"OLED 보호","oled_protection_hint":"대시보드를 주기적으로 이동하고 유휴 시 정적 도구 모음을 어둡게 합니다.","oled_short":"OLED","open":"열기","disable_tv_view":"TV 보기 비활성화","save":"저장","saving":"저장 중…","saved":"저장됨","save_failed":"설정을 저장할 수 없습니다."},
}

_TV_DASHBOARD_EXTRA_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "media_search": "Search media",
        "media_search_empty": "No matching media.",
        "media_favorites": "Favorites",
        "add_favorite": "Add favorite",
        "remove_favorite": "Remove favorite",
        "no_favorites": "No favorites yet.",
        "backend_settings": "Fitness settings",
        "add_fitness_user": "Add Fitness user",
        "backend_profile": "Fitness TV disabled",
        "tv_view_disabled": "Fitness TV disabled",
        "no_fitness_profiles": "No Fitness users exist yet. Add one in the Fitness backend.",
    },
    "el": {
        "media_search": "Αναζήτηση πολυμέσων",
        "media_search_empty": "Δεν βρέθηκαν πολυμέσα.",
        "media_favorites": "Αγαπημένα",
        "add_favorite": "Προσθήκη στα αγαπημένα",
        "remove_favorite": "Αφαίρεση από τα αγαπημένα",
        "no_favorites": "Δεν υπάρχουν ακόμη αγαπημένα.",
        "backend_settings": "Ρυθμίσεις Fitness",
        "add_fitness_user": "Προσθήκη χρήστη Fitness",
        "backend_profile": "Το Fitness TV είναι απενεργοποιημένο",
        "tv_view_disabled": "Το Fitness TV είναι απενεργοποιημένο",
        "no_fitness_profiles": "Δεν υπάρχουν ακόμη χρήστες Fitness. Πρόσθεσε έναν στο backend του Fitness.",
    },
    "de": {
        "media_search": "Medien durchsuchen",
        "media_search_empty": "Keine passenden Medien.",
        "media_favorites": "Favoriten",
        "add_favorite": "Zu Favoriten hinzufügen",
        "remove_favorite": "Aus Favoriten entfernen",
        "no_favorites": "Noch keine Favoriten.",
        "backend_settings": "Fitness-Einstellungen",
        "add_fitness_user": "Fitness-Benutzer hinzufügen",
        "backend_profile": "Fitness TV deaktiviert",
        "tv_view_disabled": "Fitness TV deaktiviert",
        "no_fitness_profiles": "Noch keine Fitness-Benutzer vorhanden. Füge einen im Fitness-Backend hinzu.",
    },
}

_TV_DASHBOARD_MUSIC_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "music_sources":"Music sources","music_favorites_hint":"Your saved music for this Fitness profile.",
        "music_internet_radio":"Internet radio","music_internet_radio_hint":"Built into Fitness; no extra Home Assistant integration is required.",
        "music_ha_sources":"Home Assistant media","music_ha_sources_hint":"Browse audio exposed by Home Assistant Media Sources.",
        "music_add_link":"Play from link","music_add_link_hint":"Paste one direct stream or SoundCloud, YouTube or YouTube Music link. This does not add a provider account.",
        "music_link":"Music URL or URI","music_title_optional":"Title (optional)","music_link_supported":"Fitness remembers this link for the profile and plays it on Fitness TV. This does not add a provider account. Direct audio streams, SoundCloud, YouTube and YouTube Music links are supported.",
        "music_use_link":"Play & remember","music_invalid_link":"Enter a supported music link or URI.","music_radio_error":"Internet radio could not be loaded.","music_country":"Country","music_all_countries":"All countries",
        "music_search":"Search music","music_search_hint":"Search one, several, or all enabled music adapters.","music_search_query":"Search","music_search_placeholder":"Artist, song, album…","music_search_types":"Result types","music_type_tracks":"Tracks","music_type_albums":"Albums","music_type_playlists":"Playlists","music_type_artists":"Artists","music_type_radio":"Radio","music_type_podcasts":"Podcasts","music_type_audiobooks":"Audiobooks","music_search_select_type":"Select at least one result type.","music_search_working":"Searching music… Some adapters such as yt-dlp can take a few seconds.","music_loading_adapters":"Loading music adapters…","music_all_adapters":"All available adapters","music_all_adapters_hint":"Search every enabled adapter that supports search.","music_search_results":"Music search results","music_search_enter_query":"Enter something to search for.","music_search_select_adapter":"Select at least one music adapter.","music_search_error":"Music search failed.","music_adapter_error":"Music adapters could not be loaded.","music_no_search_adapters":"No searchable music adapters are available.","music_adapters":"Music adapters","music_adapters_hint":"Choose which installed adapters this Fitness profile may use. Search only includes enabled adapters that support search. Provider credentials stay in Home Assistant or Music Assistant; Fitness stores no provider passwords or tokens.","music_no_adapters":"No music adapters found.","music_account":"Account","music_account_ha_hint":"Configure this provider/account in Home Assistant.","music_configure_provider":"Configure provider","music_install_provider":"Install provider","music_add_provider":"Add music provider","music_no_provider_catalog":"No provider setup options are available.","music_search_result_count":"Search results per adapter","music_search_result_count_hint":"Maximum results returned by each selected adapter (10–100). Saved separately for this Fitness profile.","fullscreen":"Fullscreen","exit_fullscreen":"Exit fullscreen","music_adapter_disabled":"Disabled in this profile's Fitness TV settings.","music_progress":"Music progress","music_live":"LIVE","music_playlists":"Playlists","music_playlists_hint":"Playlists saved for this Fitness profile.","music_new_playlist":"New playlist","music_edit_playlist":"Edit playlist","music_no_playlists":"No playlists yet.","music_playlist_empty":"This playlist is empty.","music_items":"items","music_add_to_playlist":"Add to playlist","music_selected_items":"selected items","music_playlist":"Playlist","music_open_playlist":"Open playlist","music_open_provider":"Open provider","play_selected":"Play selected","select_all":"Select all","clear":"Clear","shuffle":"Shuffle","repeat":"Repeat","previous":"Previous","edit":"Edit","delete":"Delete","add":"Add","remove":"Remove","name":"Name",
        "music_add_link_hint_v2":"Direct audio, YouTube/YouTube Music, or SoundCloud links that Fitness can play directly.","music_link_supported_v2":"Supported here: direct HTTP(S) audio streams, YouTube/YouTube Music through the normal YouTube player, and SoundCloud. Account-only providers such as Spotify are intentionally not accepted here; use their Home Assistant media adapter instead.","music_spotify_requires_provider":"Spotify links are not directly playable here. Use a Spotify-capable Home Assistant media adapter or Music Assistant.",
        "ytdlp_enabled":"yt-dlp music adapter (experimental)","ytdlp_disclaimer":"yt-dlp is an optional third-party adapter and is not affiliated with or endorsed by YouTube or other services. By enabling it, you acknowledge that you are solely responsible for how you use it, including complying with applicable law, service terms, copyright/licensing rules and obtaining all necessary rights or permissions. Fitness does not provide account cookies, does not authorize circumvention, unauthorized downloading or redistribution, and provides this adapter without warranty. You accept sole responsibility for your conduct and, to the maximum extent permitted by applicable law, for resulting legal, contractual, financial, account, copyright, licensing, or other consequences, claims, fees, fines, or penalties. The Fitness developers and contributors do not assume responsibility for a user's unlawful or unauthorized use. This notice is not legal advice and does not override rights or liabilities that cannot lawfully be excluded."
    },
    "el": {
        "music_sources":"Πηγές μουσικής","music_favorites_hint":"Η αποθηκευμένη μουσική αυτού του προφίλ Fitness.",
        "music_internet_radio":"Διαδικτυακό ραδιόφωνο","music_internet_radio_hint":"Ενσωματωμένο στο Fitness· δεν απαιτείται επιπλέον ενσωμάτωση Home Assistant.",
        "music_ha_sources":"Πολυμέσα Home Assistant","music_ha_sources_hint":"Περιήγηση σε ήχο που παρέχεται από τις Πηγές πολυμέσων του Home Assistant.",
        "music_add_link":"Αναπαραγωγή από σύνδεσμο","music_add_link_hint":"Επικόλλησε μία άμεση ροή ή σύνδεσμο SoundCloud, YouTube ή YouTube Music. Δεν προσθέτει λογαριασμό παρόχου.",
        "music_link":"URL ή URI μουσικής","music_title_optional":"Τίτλος (προαιρετικό)","music_link_supported":"Το Fitness θυμάται αυτόν τον σύνδεσμο για το προφίλ και τον αναπαράγει στο Fitness TV. Δεν προσθέτει λογαριασμό παρόχου. Υποστηρίζονται άμεσες ροές ήχου και σύνδεσμοι SoundCloud, YouTube και YouTube Music.",
        "music_use_link":"Αναπαραγωγή & αποθήκευση","music_invalid_link":"Δώσε έναν υποστηριζόμενο σύνδεσμο ή URI μουσικής.","music_radio_error":"Δεν ήταν δυνατή η φόρτωση του διαδικτυακού ραδιοφώνου.","music_country":"Χώρα","music_all_countries":"Όλες οι χώρες",
        "music_search":"Αναζήτηση μουσικής","music_search_hint":"Αναζήτησε σε έναν, πολλούς ή όλους τους ενεργούς προσαρμογείς μουσικής.","music_search_query":"Αναζήτηση","music_search_placeholder":"Καλλιτέχνης, τραγούδι, άλμπουμ…","music_search_types":"Τύποι αποτελεσμάτων","music_type_tracks":"Τραγούδια","music_type_albums":"Άλμπουμ","music_type_playlists":"Λίστες αναπαραγωγής","music_type_artists":"Καλλιτέχνες","music_type_radio":"Ραδιόφωνο","music_type_podcasts":"Podcast","music_type_audiobooks":"Ηχητικά βιβλία","music_search_select_type":"Επίλεξε τουλάχιστον έναν τύπο αποτελέσματος.","music_search_working":"Αναζήτηση μουσικής… Ορισμένοι προσαρμογείς όπως το yt-dlp μπορεί να χρειαστούν λίγα δευτερόλεπτα.","music_loading_adapters":"Φόρτωση προσαρμογέων μουσικής…","music_all_adapters":"Όλοι οι διαθέσιμοι προσαρμογείς","music_all_adapters_hint":"Αναζήτηση σε κάθε ενεργό προσαρμογέα που υποστηρίζει αναζήτηση.","music_search_results":"Αποτελέσματα αναζήτησης μουσικής","music_search_enter_query":"Γράψε κάτι για αναζήτηση.","music_search_select_adapter":"Επίλεξε τουλάχιστον έναν προσαρμογέα μουσικής.","music_search_error":"Η αναζήτηση μουσικής απέτυχε.","music_adapter_error":"Δεν ήταν δυνατή η φόρτωση των προσαρμογέων μουσικής.","music_no_search_adapters":"Δεν υπάρχουν διαθέσιμοι προσαρμογείς μουσικής με αναζήτηση.","music_adapters":"Προσαρμογείς μουσικής","music_adapters_hint":"Επίλεξε ποιους εγκατεστημένους προσαρμογείς μπορεί να χρησιμοποιεί αυτό το προφίλ Fitness. Η αναζήτηση περιλαμβάνει μόνο τους ενεργούς προσαρμογείς που υποστηρίζουν αναζήτηση. Τα διαπιστευτήρια μένουν στο Home Assistant ή στο Music Assistant.","music_no_adapters":"Δεν βρέθηκαν προσαρμογείς μουσικής.","music_account":"Λογαριασμός","music_account_ha_hint":"Ρύθμισε αυτόν τον πάροχο/λογαριασμό στο Home Assistant.","music_configure_provider":"Ρύθμιση παρόχου","music_install_provider":"Εγκατάσταση παρόχου","music_add_provider":"Προσθήκη παρόχου μουσικής","music_no_provider_catalog":"Δεν υπάρχουν διαθέσιμες επιλογές εγκατάστασης παρόχου.","music_search_result_count":"Αποτελέσματα ανά προσαρμογέα","music_search_result_count_hint":"Μέγιστος αριθμός αποτελεσμάτων από κάθε επιλεγμένο προσαρμογέα (10–100). Αποθηκεύεται ξεχωριστά για αυτό το προφίλ Fitness.","fullscreen":"Πλήρης οθόνη","exit_fullscreen":"Έξοδος από πλήρη οθόνη","music_adapter_disabled":"Απενεργοποιημένος στις ρυθμίσεις Fitness TV αυτού του προφίλ.","music_progress":"Πρόοδος μουσικής","music_live":"LIVE","music_playlists":"Λίστες αναπαραγωγής","music_playlists_hint":"Λίστες αναπαραγωγής αποθηκευμένες σε αυτό το προφίλ Fitness.","music_new_playlist":"Νέα λίστα","music_edit_playlist":"Επεξεργασία λίστας","music_no_playlists":"Δεν υπάρχουν ακόμη λίστες αναπαραγωγής.","music_playlist_empty":"Αυτή η λίστα είναι κενή.","music_items":"στοιχεία","music_add_to_playlist":"Προσθήκη σε λίστα","music_selected_items":"επιλεγμένα στοιχεία","music_playlist":"Λίστα αναπαραγωγής","music_open_playlist":"Άνοιγμα λίστας","music_open_provider":"Άνοιγμα παρόχου","play_selected":"Αναπαραγωγή επιλεγμένων","select_all":"Επιλογή όλων","clear":"Καθαρισμός","shuffle":"Τυχαία σειρά","repeat":"Επανάληψη","previous":"Προηγούμενο","edit":"Επεξεργασία","delete":"Διαγραφή","add":"Προσθήκη","remove":"Αφαίρεση","name":"Όνομα",
        "music_add_link_hint_v2":"Άμεσος ήχος ή σύνδεσμος YouTube/YouTube Music ή SoundCloud που μπορεί να παίξει απευθείας το Fitness.","music_link_supported_v2":"Υποστηρίζονται εδώ άμεσες ροές ήχου HTTP(S), YouTube/YouTube Music μέσω του κανονικού YouTube player και SoundCloud. Πάροχοι που απαιτούν λογαριασμό, όπως το Spotify, δεν γίνονται δεκτοί εδώ· χρησιμοποίησε τον αντίστοιχο προσαρμογέα πολυμέσων του Home Assistant.","music_spotify_requires_provider":"Οι σύνδεσμοι Spotify δεν αναπαράγονται απευθείας εδώ. Χρησιμοποίησε προσαρμογέα Home Assistant με Spotify ή Music Assistant.",
        "ytdlp_enabled":"Προσαρμογέας μουσικής yt-dlp (πειραματικό)","ytdlp_disclaimer":"Το yt-dlp είναι προαιρετικός προσαρμογέας τρίτου μέρους και δεν συνδέεται ούτε υποστηρίζεται από το YouTube ή άλλες υπηρεσίες. Με την ενεργοποίησή του αναγνωρίζεις ότι είσαι αποκλειστικά υπεύθυνος για τη χρήση του, συμπεριλαμβανομένης της συμμόρφωσης με την ισχύουσα νομοθεσία, τους όρους υπηρεσίας, τους κανόνες πνευματικών δικαιωμάτων/αδειών και την εξασφάλιση όλων των απαραίτητων δικαιωμάτων ή αδειών. Το Fitness δεν παρέχει cookies λογαριασμού, δεν εξουσιοδοτεί παράκαμψη περιορισμών, μη εξουσιοδοτημένη λήψη ή αναδιανομή και παρέχει τον προσαρμογέα χωρίς εγγύηση. Αναλαμβάνεις αποκλειστικά την ευθύνη για τη συμπεριφορά σου και, στον μέγιστο βαθμό που επιτρέπεται από την ισχύουσα νομοθεσία, για τυχόν νομικές, συμβατικές, οικονομικές, σχετικές με λογαριασμούς, πνευματικά δικαιώματα ή άδειες συνέπειες, αξιώσεις, χρεώσεις, πρόστιμα ή κυρώσεις. Οι προγραμματιστές και συνεισφέροντες του Fitness δεν αναλαμβάνουν ευθύνη για παράνομη ή μη εξουσιοδοτημένη χρήση από χρήστη. Η παρούσα ειδοποίηση δεν αποτελεί νομική συμβουλή και δεν παρακάμπτει δικαιώματα ή ευθύνες που δεν μπορούν νόμιμα να αποκλειστούν."
    },
    "de": {
        "music_sources":"Musikquellen","music_favorites_hint":"Deine gespeicherte Musik für dieses Fitness-Profil.",
        "music_internet_radio":"Internetradio","music_internet_radio_hint":"Direkt in Fitness integriert; keine zusätzliche Home-Assistant-Integration erforderlich.",
        "music_ha_sources":"Home-Assistant-Medien","music_ha_sources_hint":"Audio aus den Home-Assistant-Medienquellen durchsuchen.",
        "music_add_link":"Von Link abspielen","music_add_link_hint":"Füge einen direkten Stream- oder SoundCloud-, YouTube- oder YouTube-Music-Link ein. Dadurch wird kein Anbieter-Konto hinzugefügt.",
        "music_link":"Musik-URL oder URI","music_title_optional":"Titel (optional)","music_link_supported":"Fitness merkt sich diesen Link für das Profil und spielt ihn auf Fitness TV ab. Dadurch wird kein Anbieter-Konto hinzugefügt. Direkte Audiostreams sowie SoundCloud-, YouTube- und YouTube-Music-Links werden unterstützt.",
        "music_use_link":"Abspielen & merken","music_invalid_link":"Gib einen unterstützten Musiklink oder eine URI ein.","music_radio_error":"Internetradio konnte nicht geladen werden.","music_country":"Land","music_all_countries":"Alle Länder",
        "music_search":"Musik suchen","music_search_hint":"Einen, mehrere oder alle aktivierten Musikadapter durchsuchen.","music_search_query":"Suche","music_search_placeholder":"Künstler, Titel, Album…","music_search_types":"Ergebnistypen","music_type_tracks":"Titel","music_type_albums":"Alben","music_type_playlists":"Playlists","music_type_artists":"Künstler","music_type_radio":"Radio","music_type_podcasts":"Podcasts","music_type_audiobooks":"Hörbücher","music_search_select_type":"Wähle mindestens einen Ergebnistyp.","music_search_working":"Musik wird gesucht… Einige Adapter wie yt-dlp können einige Sekunden benötigen.","music_loading_adapters":"Musikadapter werden geladen…","music_all_adapters":"Alle verfügbaren Adapter","music_all_adapters_hint":"Alle aktivierten Adapter durchsuchen, die Suche unterstützen.","music_search_results":"Musik-Suchergebnisse","music_search_enter_query":"Gib einen Suchbegriff ein.","music_search_select_adapter":"Wähle mindestens einen Musikadapter.","music_search_error":"Musiksuche fehlgeschlagen.","music_adapter_error":"Musikadapter konnten nicht geladen werden.","music_no_search_adapters":"Keine durchsuchbaren Musikadapter verfügbar.","music_adapters":"Musikadapter","music_adapters_hint":"Wähle die installierten Adapter für dieses Fitness-Profil. Die Suche verwendet nur aktivierte Adapter mit Suchfunktion. Zugangsdaten bleiben in Home Assistant oder Music Assistant; Fitness speichert keine Anbieter-Passwörter oder Tokens.","music_no_adapters":"Keine Musikadapter gefunden.","music_account":"Konto","music_account_ha_hint":"Diesen Anbieter/dieses Konto in Home Assistant einrichten.","music_configure_provider":"Anbieter konfigurieren","music_install_provider":"Anbieter installieren","music_add_provider":"Musikanbieter hinzufügen","music_no_provider_catalog":"Keine Anbieter-Einrichtungsoptionen verfügbar.","music_search_result_count":"Suchergebnisse pro Adapter","music_search_result_count_hint":"Maximale Ergebnisse je ausgewähltem Adapter (10–100). Wird separat für dieses Fitness-Profil gespeichert.","fullscreen":"Vollbild","exit_fullscreen":"Vollbild beenden","music_adapter_disabled":"In den Fitness-TV-Einstellungen dieses Profils deaktiviert.","music_progress":"Musikfortschritt","music_live":"LIVE",
        "music_add_link_hint_v2":"Direkte Audio-, YouTube-/YouTube-Music- oder SoundCloud-Links, die Fitness direkt abspielen kann.","music_link_supported_v2":"Unterstützt werden direkte HTTP(S)-Audiostreams, YouTube/YouTube Music über den normalen YouTube-Player und SoundCloud. Kontoabhängige Anbieter wie Spotify werden hier nicht akzeptiert; verwende deren Home-Assistant-Medienadapter.","music_spotify_requires_provider":"Spotify-Links werden hier nicht direkt abgespielt. Verwende einen Spotify-fähigen Home-Assistant-Adapter oder Music Assistant.",
        "ytdlp_enabled":"yt-dlp-Musikadapter (experimentell)","ytdlp_disclaimer":"yt-dlp ist ein optionaler Drittanbieter-Adapter und weder mit YouTube noch mit anderen Diensten verbunden oder von ihnen empfohlen. Durch die Aktivierung erkennst du an, dass du allein für die Nutzung verantwortlich bist, einschließlich der Einhaltung geltenden Rechts, der Nutzungsbedingungen, Urheber-/Lizenzregeln und aller erforderlichen Rechte oder Genehmigungen. Fitness stellt keine Konto-Cookies bereit, autorisiert keine Umgehung, unbefugtes Herunterladen oder Weiterverbreiten und stellt den Adapter ohne Gewähr bereit. Du übernimmst allein die Verantwortung für dein Verhalten und, soweit nach geltendem Recht zulässig, für daraus entstehende rechtliche, vertragliche, finanzielle, kontobezogene, urheber- oder lizenzrechtliche Folgen, Ansprüche, Gebühren, Bußgelder oder sonstige Sanktionen. Die Entwickler und Mitwirkenden von Fitness übernehmen keine Verantwortung für rechtswidrige oder unbefugte Nutzung durch einen Benutzer. Dieser Hinweis ist keine Rechtsberatung und schließt keine Rechte oder Haftungen aus, die gesetzlich nicht ausgeschlossen werden können."
    },
    "fr": {"music_sources":"Sources de musique","music_favorites_hint":"Votre musique enregistrée pour ce profil Fitness.","music_internet_radio":"Radio Internet","music_internet_radio_hint":"Intégrée à Fitness ; aucune intégration Home Assistant supplémentaire n’est requise.","music_ha_sources":"Médias Home Assistant","music_ha_sources_hint":"Parcourir l’audio exposé par les sources multimédias Home Assistant.","music_add_link":"Ajouter un lien musical","music_add_link_hint":"Flux direct, URL/URI Spotify, SoundCloud, YouTube ou YouTube Music.","music_link":"URL ou URI musicale","music_title_optional":"Titre (facultatif)","music_link_supported":"Les flux audio directs et les liens Spotify, SoundCloud, YouTube et YouTube Music sont pris en charge.","music_use_link":"Utiliser cette musique","music_invalid_link":"Saisissez un lien ou URI musical pris en charge.","music_radio_error":"Impossible de charger la radio Internet."},
    "es": {"music_sources":"Fuentes de música","music_favorites_hint":"Tu música guardada para este perfil de Fitness.","music_internet_radio":"Radio por Internet","music_internet_radio_hint":"Integrada en Fitness; no necesita otra integración de Home Assistant.","music_ha_sources":"Medios de Home Assistant","music_ha_sources_hint":"Explora audio publicado por las fuentes multimedia de Home Assistant.","music_add_link":"Añadir enlace de música","music_add_link_hint":"Stream directo, URL/URI de Spotify, SoundCloud, YouTube o YouTube Music.","music_link":"URL o URI de música","music_title_optional":"Título (opcional)","music_link_supported":"Se admiten streams de audio directos y enlaces de Spotify, SoundCloud, YouTube y YouTube Music.","music_use_link":"Usar esta música","music_invalid_link":"Introduce un enlace o URI de música compatible.","music_radio_error":"No se pudo cargar la radio por Internet."},
    "it": {"music_sources":"Sorgenti musicali","music_favorites_hint":"La musica salvata per questo profilo Fitness.","music_internet_radio":"Radio Internet","music_internet_radio_hint":"Integrata in Fitness; non serve un’altra integrazione Home Assistant.","music_ha_sources":"Media Home Assistant","music_ha_sources_hint":"Sfoglia l’audio esposto dalle sorgenti multimediali di Home Assistant.","music_add_link":"Aggiungi link musicale","music_add_link_hint":"Stream diretto, URL/URI Spotify, SoundCloud, YouTube o YouTube Music.","music_link":"URL o URI musicale","music_title_optional":"Titolo (opzionale)","music_link_supported":"Sono supportati stream audio diretti e link Spotify, SoundCloud, YouTube e YouTube Music.","music_use_link":"Usa questa musica","music_invalid_link":"Inserisci un link o URI musicale supportato.","music_radio_error":"Impossibile caricare la radio Internet."},
    "pt": {"music_sources":"Fontes de música","music_favorites_hint":"A música guardada para este perfil Fitness.","music_internet_radio":"Rádio pela Internet","music_internet_radio_hint":"Integrado no Fitness; não requer outra integração do Home Assistant.","music_ha_sources":"Multimédia do Home Assistant","music_ha_sources_hint":"Explore áudio disponibilizado pelas fontes multimédia do Home Assistant.","music_add_link":"Adicionar ligação de música","music_add_link_hint":"Stream direto, URL/URI Spotify, SoundCloud, YouTube ou YouTube Music.","music_link":"URL ou URI de música","music_title_optional":"Título (opcional)","music_link_supported":"São suportados streams de áudio diretos e ligações Spotify, SoundCloud, YouTube e YouTube Music.","music_use_link":"Usar esta música","music_invalid_link":"Introduza uma ligação ou URI de música suportada.","music_radio_error":"Não foi possível carregar a rádio pela Internet."},
    "nl": {"music_sources":"Muziekbronnen","music_favorites_hint":"Je opgeslagen muziek voor dit Fitness-profiel.","music_internet_radio":"Internetradio","music_internet_radio_hint":"Ingebouwd in Fitness; geen extra Home Assistant-integratie nodig.","music_ha_sources":"Home Assistant-media","music_ha_sources_hint":"Blader door audio uit Home Assistant-mediabronnen.","music_add_link":"Muzieklink toevoegen","music_add_link_hint":"Directe stream, Spotify-, SoundCloud-, YouTube- of YouTube Music-URL/URI.","music_link":"Muziek-URL of URI","music_title_optional":"Titel (optioneel)","music_link_supported":"Directe audiostreams en Spotify-, SoundCloud-, YouTube- en YouTube Music-links worden ondersteund.","music_use_link":"Deze muziek gebruiken","music_invalid_link":"Voer een ondersteunde muzieklink of URI in.","music_radio_error":"Internetradio kon niet worden geladen."},
    "pl": {"music_sources":"Źródła muzyki","music_favorites_hint":"Muzyka zapisana dla tego profilu Fitness.","music_internet_radio":"Radio internetowe","music_internet_radio_hint":"Wbudowane w Fitness; nie wymaga dodatkowej integracji Home Assistant.","music_ha_sources":"Multimedia Home Assistant","music_ha_sources_hint":"Przeglądaj dźwięk udostępniany przez źródła multimediów Home Assistant.","music_add_link":"Dodaj link do muzyki","music_add_link_hint":"Bezpośredni strumień, URL/URI Spotify, SoundCloud, YouTube lub YouTube Music.","music_link":"URL lub URI muzyki","music_title_optional":"Tytuł (opcjonalnie)","music_link_supported":"Obsługiwane są bezpośrednie strumienie audio oraz linki Spotify, SoundCloud, YouTube i YouTube Music.","music_use_link":"Użyj tej muzyki","music_invalid_link":"Wprowadź obsługiwany link lub URI muzyki.","music_radio_error":"Nie udało się wczytać radia internetowego."},
    "ru": {"music_sources":"Источники музыки","music_favorites_hint":"Сохранённая музыка для этого профиля Fitness.","music_internet_radio":"Интернет-радио","music_internet_radio_hint":"Встроено в Fitness; дополнительная интеграция Home Assistant не требуется.","music_ha_sources":"Медиа Home Assistant","music_ha_sources_hint":"Просмотр аудио из медиаисточников Home Assistant.","music_add_link":"Добавить ссылку на музыку","music_add_link_hint":"Прямой поток, URL/URI Spotify, SoundCloud, YouTube или YouTube Music.","music_link":"URL или URI музыки","music_title_optional":"Название (необязательно)","music_link_supported":"Поддерживаются прямые аудиопотоки и ссылки Spotify, SoundCloud, YouTube и YouTube Music.","music_use_link":"Использовать эту музыку","music_invalid_link":"Введите поддерживаемую ссылку или URI музыки.","music_radio_error":"Не удалось загрузить интернет-радио."},
    "uk": {"music_sources":"Джерела музики","music_favorites_hint":"Збережена музика для цього профілю Fitness.","music_internet_radio":"Інтернет-радіо","music_internet_radio_hint":"Вбудовано у Fitness; додаткова інтеграція Home Assistant не потрібна.","music_ha_sources":"Медіа Home Assistant","music_ha_sources_hint":"Переглядайте аудіо з медіаджерел Home Assistant.","music_add_link":"Додати посилання на музику","music_add_link_hint":"Прямий потік, URL/URI Spotify, SoundCloud, YouTube або YouTube Music.","music_link":"URL або URI музики","music_title_optional":"Назва (необов’язково)","music_link_supported":"Підтримуються прямі аудіопотоки та посилання Spotify, SoundCloud, YouTube і YouTube Music.","music_use_link":"Використати цю музику","music_invalid_link":"Введіть підтримуване посилання або URI музики.","music_radio_error":"Не вдалося завантажити інтернет-радіо."},
    "tr": {"music_sources":"Müzik kaynakları","music_favorites_hint":"Bu Fitness profili için kaydedilen müzikleriniz.","music_internet_radio":"İnternet radyosu","music_internet_radio_hint":"Fitness'a dahildir; ek Home Assistant entegrasyonu gerekmez.","music_ha_sources":"Home Assistant medyası","music_ha_sources_hint":"Home Assistant Medya Kaynakları tarafından sunulan sesleri gezin.","music_add_link":"Müzik bağlantısı ekle","music_add_link_hint":"Doğrudan yayın, Spotify, SoundCloud, YouTube veya YouTube Music URL/URI.","music_link":"Müzik URL'si veya URI'si","music_title_optional":"Başlık (isteğe bağlı)","music_link_supported":"Doğrudan ses yayınları ile Spotify, SoundCloud, YouTube ve YouTube Music bağlantıları desteklenir.","music_use_link":"Bu müziği kullan","music_invalid_link":"Desteklenen bir müzik bağlantısı veya URI girin.","music_radio_error":"İnternet radyosu yüklenemedi."},
    "zh": {"music_sources":"音乐来源","music_favorites_hint":"此 Fitness 配置文件保存的音乐。","music_internet_radio":"网络电台","music_internet_radio_hint":"Fitness 内置；无需额外的 Home Assistant 集成。","music_ha_sources":"Home Assistant 媒体","music_ha_sources_hint":"浏览 Home Assistant 媒体源提供的音频。","music_add_link":"添加音乐链接","music_add_link_hint":"直接音频流、Spotify、SoundCloud、YouTube 或 YouTube Music URL/URI。","music_link":"音乐 URL 或 URI","music_title_optional":"标题（可选）","music_link_supported":"支持直接音频流以及 Spotify、SoundCloud、YouTube 和 YouTube Music 链接。","music_use_link":"使用此音乐","music_invalid_link":"请输入受支持的音乐链接或 URI。","music_radio_error":"无法加载网络电台。"},
    "ja": {"music_sources":"音楽ソース","music_favorites_hint":"この Fitness プロフィールに保存した音楽です。","music_internet_radio":"インターネットラジオ","music_internet_radio_hint":"Fitness に内蔵されており、追加の Home Assistant 統合は不要です。","music_ha_sources":"Home Assistant メディア","music_ha_sources_hint":"Home Assistant メディアソースが提供する音声を参照します。","music_add_link":"音楽リンクを追加","music_add_link_hint":"直接ストリーム、Spotify、SoundCloud、YouTube、YouTube Music の URL/URI。","music_link":"音楽 URL または URI","music_title_optional":"タイトル（任意）","music_link_supported":"直接音声ストリームと Spotify、SoundCloud、YouTube、YouTube Music のリンクに対応しています。","music_use_link":"この音楽を使う","music_invalid_link":"対応する音楽リンクまたは URI を入力してください。","music_radio_error":"インターネットラジオを読み込めませんでした。"},
    "ko": {"music_sources":"음악 소스","music_favorites_hint":"이 Fitness 프로필에 저장된 음악입니다.","music_internet_radio":"인터넷 라디오","music_internet_radio_hint":"Fitness에 내장되어 있으며 추가 Home Assistant 통합이 필요하지 않습니다.","music_ha_sources":"Home Assistant 미디어","music_ha_sources_hint":"Home Assistant 미디어 소스에서 제공하는 오디오를 탐색합니다.","music_add_link":"음악 링크 추가","music_add_link_hint":"직접 스트림, Spotify, SoundCloud, YouTube 또는 YouTube Music URL/URI.","music_link":"음악 URL 또는 URI","music_title_optional":"제목(선택 사항)","music_link_supported":"직접 오디오 스트림과 Spotify, SoundCloud, YouTube 및 YouTube Music 링크를 지원합니다.","music_use_link":"이 음악 사용","music_invalid_link":"지원되는 음악 링크 또는 URI를 입력하세요.","music_radio_error":"인터넷 라디오를 불러올 수 없습니다."},
}

# Audio-output labels share the music language bundle. The audited catalog supplies
# native wording for every remaining supported language.
_TV_DASHBOARD_MUSIC_TEXT["en"].update({
    "audio_output": "Music & TTS output",
    "audio_output_hint": "Choose the Fitness browser/Cast receiver or a compatible Home Assistant media player. Music Assistant-managed players use Music Assistant preferentially.",
    "audio_output_browser": "Fitness browser / Cast TV",
    "unavailable": "Unavailable",
})
_TV_DASHBOARD_MUSIC_TEXT["el"].update({
    "audio_output": "Έξοδος μουσικής & TTS",
    "audio_output_hint": "Επίλεξε το πρόγραμμα περιήγησης/δέκτη Cast του Fitness ή ένα συμβατό media player του Home Assistant. Για συσκευές που διαχειρίζεται το Music Assistant προτιμάται το Music Assistant.",
    "audio_output_browser": "Πρόγραμμα περιήγησης Fitness / Cast TV",
    "unavailable": "Μη διαθέσιμο",
})
_TV_DASHBOARD_MUSIC_TEXT["de"].update({
    "audio_output": "Musik- & TTS-Ausgabe",
    "audio_output_hint": "Wähle den Fitness-Browser/Cast-Empfänger oder einen kompatiblen Home-Assistant-Mediaplayer. Bei Music-Assistant-verwalteten Playern wird Music Assistant bevorzugt.",
    "audio_output_browser": "Fitness-Browser / Cast-TV",
    "unavailable": "Nicht verfügbar",
})

_TV_DASHBOARD_INTERACTION_TEXT: dict[str, dict[str, str]] = {
    "en": {"settings_main_menu":"Settings menu","close":"Close","loading":"Loading…","next":"Next","working":"Working…"},
    "el": {"settings_main_menu":"Κύριο μενού","close":"Κλείσιμο","loading":"Φόρτωση…","next":"Επόμενο","working":"Επεξεργασία…"},
    "de": {"settings_main_menu":"Einstellungsmenü","close":"Schließen","loading":"Laden…","next":"Weiter","working":"Wird verarbeitet…"},
    "fr": {"settings_main_menu":"Menu des réglages","close":"Fermer","loading":"Chargement…","next":"Suivant","working":"Traitement…"},
    "es": {"settings_main_menu":"Menú de ajustes","close":"Cerrar","loading":"Cargando…","next":"Siguiente","working":"Procesando…"},
    "it": {"settings_main_menu":"Menu impostazioni","close":"Chiudi","loading":"Caricamento…","next":"Avanti","working":"Elaborazione…"},
    "pt": {"settings_main_menu":"Menu de definições","close":"Fechar","loading":"A carregar…","next":"Seguinte","working":"A processar…"},
    "nl": {"settings_main_menu":"Instellingenmenu","close":"Sluiten","loading":"Laden…","next":"Volgende","working":"Bezig…"},
    "pl": {"settings_main_menu":"Menu ustawień","close":"Zamknij","loading":"Ładowanie…","next":"Dalej","working":"Przetwarzanie…"},
    "ru": {"settings_main_menu":"Меню настроек","close":"Закрыть","loading":"Загрузка…","next":"Далее","working":"Обработка…"},
    "uk": {"settings_main_menu":"Меню налаштувань","close":"Закрити","loading":"Завантаження…","next":"Далі","working":"Обробка…"},
    "tr": {"settings_main_menu":"Ayarlar menüsü","close":"Kapat","loading":"Yükleniyor…","next":"İleri","working":"İşleniyor…"},
    "zh": {"settings_main_menu":"设置菜单","close":"关闭","loading":"正在加载…","next":"下一步","working":"处理中…"},
    "ja": {"settings_main_menu":"設定メニュー","close":"閉じる","loading":"読み込み中…","next":"次へ","working":"処理中…"},
    "ko": {"settings_main_menu":"설정 메뉴","close":"닫기","loading":"불러오는 중…","next":"다음","working":"처리 중…"},
}

_TV_DASHBOARD_FLOW_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "start_tv_workout":"Start on TV",
        "start_tv_workout_preparing":"Preparing TV, music and workout…",
        "start_tv_workout_ready":"TV ready. Workout started.",
        "start_tv_workout_failed":"Could not prepare the TV and start the workout.",
        "start_tv_workout_music_failed":"TV ready and workout started, but the saved music could not be played.",
        "last_music":"Last music",
        "last_music_none":"No saved music",
        "cast_wake_wait":"The selected Cast target is idle or not responding yet. Fitness will prepare it and may wait about 10 seconds before casting…",
        "keep_awake":"Screen saver protection",
        "keep_awake_hint":"While the Fitness Cast dashboard is open, Fitness requests a screen wake lock to keep the TV dashboard visible.",
        "cast_exit_confirm":'Press Back once more to exit Cast',
    },
    "el": {
        "start_tv_workout":"Έναρξη στην TV",
        "start_tv_workout_preparing":"Προετοιμασία TV, μουσικής και προπόνησης…",
        "start_tv_workout_ready":"Η TV είναι έτοιμη. Η προπόνηση ξεκίνησε.",
        "start_tv_workout_failed":"Δεν ήταν δυνατή η προετοιμασία της TV και η έναρξη της προπόνησης.",
        "start_tv_workout_music_failed":"Η TV είναι έτοιμη και η προπόνηση ξεκίνησε, αλλά η αποθηκευμένη μουσική δεν αναπαράχθηκε.",
        "last_music":"Τελευταία μουσική",
        "last_music_none":"Δεν υπάρχει αποθηκευμένη μουσική",
        "cast_wake_wait":"Ο επιλεγμένος δέκτης Cast είναι σε αδράνεια ή δεν αποκρίνεται ακόμη. Το Fitness θα τον προετοιμάσει και μπορεί να περιμένει περίπου 10 δευτερόλεπτα πριν τη μετάδοση…",
        "keep_awake":"Προστασία από προφύλαξη οθόνης",
        "keep_awake_hint":"Όσο ο πίνακας Fitness Cast είναι ανοιχτός, το Fitness ζητά κλείδωμα αφύπνισης οθόνης ώστε ο πίνακας να παραμένει ορατός.",
        "cast_exit_confirm":'Πατήστε Πίσω άλλη μία φορά για έξοδο από το Cast',
    },
    "de": {
        "start_tv_workout":"Auf TV starten",
        "start_tv_workout_preparing":"TV, Musik und Training werden vorbereitet…",
        "start_tv_workout_ready":"TV bereit. Training gestartet.",
        "start_tv_workout_failed":"TV konnte nicht vorbereitet und das Training nicht gestartet werden.",
        "start_tv_workout_music_failed":"TV bereit und Training gestartet, aber die gespeicherte Musik konnte nicht abgespielt werden.",
        "last_music":"Letzte Musik",
        "last_music_none":"Keine gespeicherte Musik",
        "cast_wake_wait":"Das ausgewählte Cast-Ziel ist inaktiv oder antwortet noch nicht. Fitness bereitet es vor und wartet bei Bedarf etwa 10 Sekunden vor dem Cast…",
        "keep_awake":"Bildschirmschoner-Schutz",
        "keep_awake_hint":"Solange das Fitness-Cast-Dashboard geöffnet ist, fordert Fitness eine Bildschirm-Wake-Lock an, damit das Dashboard sichtbar bleibt.",
        "cast_exit_confirm":'Drücke Zurück noch einmal, um Cast zu beenden',
    },
    "fr": {"start_tv_workout":"Démarrer sur la TV","start_tv_workout_preparing":"Préparation de la TV, de la musique et de l’entraînement…","start_tv_workout_ready":"TV prête. Entraînement démarré.","start_tv_workout_failed":"Impossible de préparer la TV et de démarrer l’entraînement.","start_tv_workout_music_failed":"TV prête et entraînement démarré, mais la musique enregistrée n’a pas pu être lue.","last_music":"Dernière musique","last_music_none":"Aucune musique enregistrée","cast_wake_wait":"La cible Cast sélectionnée est inactive ou ne répond pas encore. Fitness va la préparer et pourra attendre environ 10 secondes avant de caster…","keep_awake":"Protection de l’économiseur d’écran","keep_awake_hint":"Tant que le tableau Fitness Cast est ouvert, Fitness demande un verrouillage d’écran actif pour garder le tableau visible.","cast_exit_confirm":"Appuyez encore une fois sur Retour pour quitter Cast"},
    "es": {"start_tv_workout":"Iniciar en TV","start_tv_workout_preparing":"Preparando TV, música y entrenamiento…","start_tv_workout_ready":"TV lista. Entrenamiento iniciado.","start_tv_workout_failed":"No se pudo preparar la TV e iniciar el entrenamiento.","start_tv_workout_music_failed":"La TV está lista y el entrenamiento comenzó, pero no se pudo reproducir la música guardada.","last_music":"Última música","last_music_none":"Sin música guardada","cast_wake_wait":"El destino Cast seleccionado está inactivo o aún no responde. Fitness lo preparará y puede esperar unos 10 segundos antes de enviar…","keep_awake":"Protección del salvapantallas","keep_awake_hint":"Mientras el panel Fitness Cast está abierto, Fitness solicita mantener la pantalla activa para que el panel siga visible.","cast_exit_confirm":"Pulsa Atrás una vez más para salir de Cast"},
    "it": {"start_tv_workout":"Avvia sulla TV","start_tv_workout_preparing":"Preparazione di TV, musica e allenamento…","start_tv_workout_ready":"TV pronta. Allenamento avviato.","start_tv_workout_failed":"Impossibile preparare la TV e avviare l’allenamento.","start_tv_workout_music_failed":"TV pronta e allenamento avviato, ma la musica salvata non può essere riprodotta.","last_music":"Ultima musica","last_music_none":"Nessuna musica salvata","cast_wake_wait":"La destinazione Cast selezionata è inattiva o non risponde ancora. Fitness la preparerà e potrebbe attendere circa 10 secondi prima del Cast…","keep_awake":"Protezione salvaschermo","keep_awake_hint":"Mentre la dashboard Fitness Cast è aperta, Fitness richiede di mantenere lo schermo attivo per lasciare visibile la dashboard.","cast_exit_confirm":"Premi Indietro ancora una volta per uscire da Cast"},
    "pt": {"start_tv_workout":"Iniciar na TV","start_tv_workout_preparing":"A preparar TV, música e treino…","start_tv_workout_ready":"TV pronta. Treino iniciado.","start_tv_workout_failed":"Não foi possível preparar a TV e iniciar o treino.","start_tv_workout_music_failed":"TV pronta e treino iniciado, mas não foi possível reproduzir a música guardada.","last_music":"Última música","last_music_none":"Sem música guardada","cast_wake_wait":"O destino Cast selecionado está inativo ou ainda não responde. O Fitness irá prepará-lo e poderá aguardar cerca de 10 segundos antes de transmitir…","keep_awake":"Proteção de ecrã","keep_awake_hint":"Enquanto o painel Fitness Cast estiver aberto, o Fitness pede para manter o ecrã ativo e o painel visível.","cast_exit_confirm":"Prima Voltar mais uma vez para sair do Cast"},
    "nl": {"start_tv_workout":"Start op TV","start_tv_workout_preparing":"TV, muziek en training voorbereiden…","start_tv_workout_ready":"TV klaar. Training gestart.","start_tv_workout_failed":"TV kon niet worden voorbereid en de training kon niet worden gestart.","start_tv_workout_music_failed":"TV klaar en training gestart, maar de opgeslagen muziek kon niet worden afgespeeld.","last_music":"Laatste muziek","last_music_none":"Geen opgeslagen muziek","cast_wake_wait":"Het gekozen Cast-doel is inactief of reageert nog niet. Fitness bereidt het voor en wacht zo nodig ongeveer 10 seconden vóór het casten…","keep_awake":"Screensaverbeveiliging","keep_awake_hint":"Zolang het Fitness Cast-dashboard open is, vraagt Fitness een scherm-wake-lock zodat het dashboard zichtbaar blijft.","cast_exit_confirm":"Druk nog één keer op Terug om Cast af te sluiten"},
    "pl": {"start_tv_workout":"Uruchom na TV","start_tv_workout_preparing":"Przygotowywanie TV, muzyki i treningu…","start_tv_workout_ready":"TV gotowy. Trening rozpoczęty.","start_tv_workout_failed":"Nie udało się przygotować TV i rozpocząć treningu.","start_tv_workout_music_failed":"TV jest gotowy i trening rozpoczęty, ale zapisanej muzyki nie udało się odtworzyć.","last_music":"Ostatnia muzyka","last_music_none":"Brak zapisanej muzyki","cast_wake_wait":"Wybrany odbiornik Cast jest bezczynny lub jeszcze nie odpowiada. Fitness przygotuje go i w razie potrzeby odczeka około 10 sekund przed Cast…","keep_awake":"Ochrona przed wygaszaczem","keep_awake_hint":"Gdy panel Fitness Cast jest otwarty, Fitness prosi o blokadę uśpienia ekranu, aby panel pozostał widoczny.","cast_exit_confirm":"Naciśnij Wstecz jeszcze raz, aby zakończyć Cast"},
    "ru": {"start_tv_workout":"Запустить на ТВ","start_tv_workout_preparing":"Подготовка ТВ, музыки и тренировки…","start_tv_workout_ready":"ТВ готов. Тренировка запущена.","start_tv_workout_failed":"Не удалось подготовить ТВ и запустить тренировку.","start_tv_workout_music_failed":"ТВ готов и тренировка запущена, но сохранённую музыку воспроизвести не удалось.","last_music":"Последняя музыка","last_music_none":"Нет сохранённой музыки","cast_wake_wait":"Выбранное устройство Cast неактивно или пока не отвечает. Fitness подготовит его и при необходимости подождёт около 10 секунд перед Cast…","keep_awake":"Защита от заставки","keep_awake_hint":"Пока панель Fitness Cast открыта, Fitness запрашивает блокировку сна экрана, чтобы панель оставалась видимой.","cast_exit_confirm":"Нажмите Назад ещё раз, чтобы выйти из Cast"},
    "uk": {"start_tv_workout":"Запустити на TV","start_tv_workout_preparing":"Підготовка TV, музики й тренування…","start_tv_workout_ready":"TV готовий. Тренування запущено.","start_tv_workout_failed":"Не вдалося підготувати TV і запустити тренування.","start_tv_workout_music_failed":"TV готовий і тренування запущено, але збережену музику не вдалося відтворити.","last_music":"Остання музика","last_music_none":"Немає збереженої музики","cast_wake_wait":"Вибраний пристрій Cast неактивний або ще не відповідає. Fitness підготує його й за потреби зачекає близько 10 секунд перед Cast…","keep_awake":"Захист від заставки","keep_awake_hint":"Поки панель Fitness Cast відкрита, Fitness запитує блокування сну екрана, щоб панель залишалась видимою.","cast_exit_confirm":"Натисніть Назад ще раз, щоб вийти з Cast"},
    "tr": {"start_tv_workout":"TV’de başlat","start_tv_workout_preparing":"TV, müzik ve antrenman hazırlanıyor…","start_tv_workout_ready":"TV hazır. Antrenman başladı.","start_tv_workout_failed":"TV hazırlanamadı ve antrenman başlatılamadı.","start_tv_workout_music_failed":"TV hazır ve antrenman başladı, ancak kayıtlı müzik çalınamadı.","last_music":"Son müzik","last_music_none":"Kayıtlı müzik yok","cast_wake_wait":"Seçilen Cast hedefi boşta veya henüz yanıt vermiyor. Fitness hedefi hazırlayacak ve gerekirse Cast işleminden önce yaklaşık 10 saniye bekleyecek…","keep_awake":"Ekran koruyucu koruması","keep_awake_hint":"Fitness Cast paneli açıkken Fitness, panelin görünür kalması için ekranı uyanık tutmayı ister.","cast_exit_confirm":"Cast'ten çıkmak için Geri tuşuna bir kez daha basın"},
    "zh": {"start_tv_workout":"在电视上开始","start_tv_workout_preparing":"正在准备电视、音乐和训练…","start_tv_workout_ready":"电视已就绪。训练已开始。","start_tv_workout_failed":"无法准备电视并开始训练。","start_tv_workout_music_failed":"电视已就绪且训练已开始，但无法播放保存的音乐。","last_music":"上次音乐","last_music_none":"没有保存的音乐","cast_wake_wait":"所选 Cast 目标处于空闲状态或暂时没有响应。Fitness 会先进行准备，并可能在投屏前等待约 10 秒…","keep_awake":"屏幕保护程序防护","keep_awake_hint":"Fitness Cast 仪表板打开时，Fitness 会请求保持屏幕唤醒，以便仪表板持续可见。","cast_exit_confirm":"再按一次返回键即可退出投屏"},
    "ja": {"start_tv_workout":"TVで開始","start_tv_workout_preparing":"TV・音楽・ワークアウトを準備中…","start_tv_workout_ready":"TVの準備完了。ワークアウトを開始しました。","start_tv_workout_failed":"TVを準備してワークアウトを開始できませんでした。","start_tv_workout_music_failed":"TVの準備とワークアウト開始は完了しましたが、保存した音楽を再生できませんでした。","last_music":"前回の音楽","last_music_none":"保存された音楽なし","cast_wake_wait":"選択した Cast デバイスは待機中か、まだ応答していません。Fitness が準備し、必要に応じて Cast 開始前に約10秒待機します…","keep_awake":"スクリーンセーバー保護","keep_awake_hint":"Fitness Castダッシュボードの表示中は、画面を起動状態に保つよう要求してダッシュボードを表示し続けます。","cast_exit_confirm":"Castを終了するには、もう一度「戻る」を押してください"},
    "ko": {"start_tv_workout":"TV에서 시작","start_tv_workout_preparing":"TV, 음악 및 운동 준비 중…","start_tv_workout_ready":"TV 준비 완료. 운동을 시작했습니다.","start_tv_workout_failed":"TV를 준비하고 운동을 시작하지 못했습니다.","start_tv_workout_music_failed":"TV와 운동은 준비되었지만 저장된 음악을 재생하지 못했습니다.","last_music":"마지막 음악","last_music_none":"저장된 음악 없음","cast_wake_wait":"선택한 Cast 대상이 유휴 상태이거나 아직 응답하지 않습니다. Fitness가 준비하고 필요한 경우 Cast 전에 약 10초 기다립니다…","keep_awake":"화면 보호기 방지","keep_awake_hint":"Fitness Cast 대시보드가 열려 있는 동안 화면을 켜 둬 대시보드가 계속 보이도록 요청합니다.","cast_exit_confirm":"Cast를 종료하려면 뒤로 버튼을 한 번 더 누르세요"},
}

_TV_DASHBOARD_REMOTE_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "remote_sensors": "Remote sensors",
        "remote_gateway_title": "Remote sensor gateway",
        "remote_gateway_browser": "This browser becomes the sensor gateway",
        "remote_gateway_hint": "Pair nearby fitness sensors here. Raw BLE/ANT+ measurements are sent through your authenticated Home Assistant connection and assigned to this Fitness profile.",
        "remote_ble": "Bluetooth fitness sensors",
        "remote_ble_hint": "Heart rate, cycling power, cadence, running speed/cadence and FTMS equipment.",
        "remote_ble_connect": "Connect Bluetooth sensor",
        "remote_ble_reconnect": "Reconnect allowed sensors",
        "remote_ble_unavailable": "Web Bluetooth is not available in this browser. Use a compatible browser over HTTPS, or a future Fitness native sender app.",
        "remote_ble_unsupported": "No supported Bluetooth fitness measurement was found on this device.",
        "remote_pairing": "Choose a Bluetooth fitness sensor…",
        "remote_reconnecting": "Reconnecting…",
        "remote_connected": "connected",
        "remote_idle": "Idle",
        "remote_no_sensors": "No remote Bluetooth sensors connected.",
        "remote_ant": "ANT+ USB gateway",
        "remote_ant_connect": "Connect ANT+ USB",
        "remote_ant_disconnect": "Disconnect ANT+",
        "remote_ant_unavailable": "WebUSB is not available in this browser. ANT+ will also be supported by the future native Fitness sender apps.",
        "remote_ant_experimental": "Experimental browser WebUSB support for Dynastream ANTUSB2 / ANTUSB-m sticks.",
        "remote_ant_connecting": "Opening ANT+ USB…",
        "remote_ant_scanning": "Scanning",
        "remote_gateway_protocol": "Gateway protocol v{version}",
        "remote_failed": "Connection failed",
        "local_cast": "Local network TV",
        "local_cast_hint": "Use this phone/laptop to choose a Google Cast TV on its current Wi-Fi network, even when Home Assistant is elsewhere.",
        "local_cast_choose": "Choose local TV",
        "local_cast_stop": "Stop local Cast",
        "local_cast_connecting": "Opening local Google Cast chooser…",
        "local_cast_authenticating": "TV selected. Connecting it to Home Assistant…",
        "local_cast_loading": "Connected. Loading Fitness TV…",
        "local_cast_connected": "Fitness TV sent to local TV",
        "local_cast_no_https": "Local Cast needs an externally reachable HTTPS Home Assistant URL.",
        "local_cast_receiver_failed": "The local Cast receiver did not connect to Home Assistant.",
        "local_cast_cancelled": "No Cast session was selected.",
        "cast_ha_devices": "Home Assistant network devices",
        "cast_ha_devices_hint": "TVs discovered by the Home Assistant server itself.",
    },
    "el": {
        "remote_sensors": "Απομακρυσμένοι αισθητήρες",
        "remote_gateway_title": "Απομακρυσμένη πύλη αισθητήρων",
        "remote_gateway_browser": "Αυτός ο browser γίνεται η πύλη αισθητήρων",
        "remote_gateway_hint": "Σύνδεσε εδώ κοντινούς αισθητήρες fitness. Οι ακατέργαστες μετρήσεις BLE/ANT+ στέλνονται μέσω της πιστοποιημένης σύνδεσης Home Assistant και αντιστοιχίζονται σε αυτό το προφίλ Fitness.",
        "remote_ble": "Αισθητήρες fitness Bluetooth",
        "remote_ble_hint": "Καρδιακοί παλμοί, ισχύς ποδηλάτου, cadence, running speed/cadence και εξοπλισμός FTMS.",
        "remote_ble_connect": "Σύνδεση αισθητήρα Bluetooth",
        "remote_ble_reconnect": "Επανασύνδεση επιτρεπόμενων αισθητήρων",
        "remote_ble_unavailable": "Το Web Bluetooth δεν είναι διαθέσιμο σε αυτόν τον browser. Χρησιμοποίησε συμβατό browser μέσω HTTPS ή μελλοντική native εφαρμογή Fitness sender.",
        "remote_ble_unsupported": "Δεν βρέθηκε υποστηριζόμενη μέτρηση Bluetooth fitness σε αυτή τη συσκευή.",
        "remote_pairing": "Επίλεξε αισθητήρα Bluetooth fitness…",
        "remote_reconnecting": "Επανασύνδεση…",
        "remote_connected": "συνδεδεμένοι",
        "remote_idle": "Αναμονή",
        "remote_no_sensors": "Δεν υπάρχουν συνδεδεμένοι απομακρυσμένοι αισθητήρες Bluetooth.",
        "remote_ant": "Πύλη USB ANT+",
        "remote_ant_connect": "Σύνδεση ANT+ USB",
        "remote_ant_disconnect": "Αποσύνδεση ANT+",
        "remote_ant_unavailable": "Το WebUSB δεν είναι διαθέσιμο σε αυτόν τον browser. Το ANT+ θα υποστηρίζεται επίσης από τις μελλοντικές native εφαρμογές Fitness sender.",
        "remote_ant_experimental": "Πειραματική υποστήριξη WebUSB για Dynastream ANTUSB2 / ANTUSB-m.",
        "remote_ant_connecting": "Άνοιγμα ANT+ USB…",
        "remote_ant_scanning": "Σάρωση",
        "remote_gateway_protocol": "Πρωτόκολλο gateway v{version}",
        "remote_failed": "Η σύνδεση απέτυχε",
        "local_cast": "TV στο τοπικό δίκτυο",
        "local_cast_hint": "Χρησιμοποίησε αυτό το κινητό/laptop για να επιλέξεις Google Cast TV στο τρέχον Wi-Fi του, ακόμη κι αν το Home Assistant βρίσκεται αλλού.",
        "local_cast_choose": "Επιλογή τοπικής TV",
        "local_cast_stop": "Διακοπή τοπικού Cast",
        "local_cast_connecting": "Άνοιγμα τοπικού Google Cast…",
        "local_cast_authenticating": "Η TV επιλέχθηκε. Σύνδεση με το Home Assistant…",
        "local_cast_loading": "Συνδέθηκε. Φόρτωση Fitness TV…",
        "local_cast_connected": "Το Fitness TV στάλθηκε στην τοπική TV",
        "local_cast_no_https": "Το Local Cast χρειάζεται εξωτερικά προσβάσιμο HTTPS URL του Home Assistant.",
        "local_cast_receiver_failed": "Ο τοπικός Cast receiver δεν συνδέθηκε στο Home Assistant.",
        "local_cast_cancelled": "Δεν επιλέχθηκε Cast συσκευή.",
        "cast_ha_devices": "Συσκευές δικτύου Home Assistant",
        "cast_ha_devices_hint": "TV που ανακαλύπτονται από το ίδιο το Home Assistant server.",
    },
    "de": {
        "remote_sensors": "Remote-Sensoren",
        "remote_gateway_title": "Remote-Sensor-Gateway",
        "remote_gateway_browser": "Dieser Browser wird zum Sensor-Gateway",
        "remote_gateway_hint": "Kopple hier Fitness-Sensoren in der Nähe. Rohe BLE-/ANT+-Messwerte werden über die authentifizierte Home-Assistant-Verbindung gesendet und diesem Fitness-Profil zugeordnet.",
        "remote_ble": "Bluetooth-Fitness-Sensoren",
        "remote_ble_hint": "Herzfrequenz, Radleistung, Trittfrequenz, Laufgeschwindigkeit/-frequenz und FTMS-Geräte.",
        "remote_ble_connect": "Bluetooth-Sensor verbinden",
        "remote_ble_reconnect": "Erlaubte Sensoren neu verbinden",
        "remote_ble_unavailable": "Web Bluetooth ist in diesem Browser nicht verfügbar. Nutze einen kompatiblen Browser über HTTPS oder künftig eine native Fitness-Sender-App.",
        "remote_ble_unsupported": "Auf diesem Gerät wurde keine unterstützte Bluetooth-Fitnessmessung gefunden.",
        "remote_pairing": "Bluetooth-Fitness-Sensor auswählen…",
        "remote_reconnecting": "Wird neu verbunden…",
        "remote_connected": "verbunden",
        "remote_idle": "Bereit",
        "remote_no_sensors": "Keine Remote-Bluetooth-Sensoren verbunden.",
        "remote_ant": "ANT+ USB-Gateway",
        "remote_ant_connect": "ANT+ USB verbinden",
        "remote_ant_disconnect": "ANT+ trennen",
        "remote_ant_unavailable": "WebUSB ist in diesem Browser nicht verfügbar. ANT+ wird außerdem von den zukünftigen nativen Fitness-Sender-Apps unterstützt.",
        "remote_ant_experimental": "Experimentelle WebUSB-Unterstützung für Dynastream ANTUSB2 / ANTUSB-m.",
        "remote_ant_connecting": "ANT+ USB wird geöffnet…",
        "remote_ant_scanning": "Scannt",
        "remote_gateway_protocol": "Gateway-Protokoll v{version}",
        "remote_failed": "Verbindung fehlgeschlagen",
        "local_cast": "TV im lokalen Netzwerk",
        "local_cast_hint": "Wähle mit diesem Handy/Laptop einen Google-Cast-TV im aktuellen WLAN, auch wenn Home Assistant sich in einem anderen Netzwerk befindet.",
        "local_cast_choose": "Lokalen TV auswählen",
        "local_cast_stop": "Lokales Cast stoppen",
        "local_cast_connecting": "Lokale Google-Cast-Auswahl wird geöffnet…",
        "local_cast_authenticating": "TV ausgewählt. Verbindung mit Home Assistant wird hergestellt…",
        "local_cast_loading": "Verbunden. Fitness TV wird geladen…",
        "local_cast_connected": "Fitness TV wurde an den lokalen TV gesendet",
        "local_cast_no_https": "Local Cast benötigt eine extern erreichbare HTTPS-URL von Home Assistant.",
        "local_cast_receiver_failed": "Der lokale Cast-Receiver konnte Home Assistant nicht erreichen.",
        "local_cast_cancelled": "Es wurde kein Cast-Gerät ausgewählt.",
        "cast_ha_devices": "Geräte im Home-Assistant-Netzwerk",
        "cast_ha_devices_hint": "TVs, die vom Home-Assistant-Server selbst entdeckt werden.",
    },
}

_TV_DASHBOARD_ACCESS_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "fitness_accounts":"Fitness accounts",
        "fitness_accounts_hint":"Home Assistant administrators manage Fitness access. Each user can own one Fitness profile and may also receive view-only access to additional profiles.",
        "manage_ha_users":"Manage Home Assistant users",
        "remote_base_domain":"Remote Fitness base domain",
        "remote_base_domain_hint":"Configure wildcard DNS/TLS once (for example *.fitness.example.com). Fitness then assigns one logical subdomain per remote account.",
        "save_domain":"Save domain",
        "account_role":"Access role",
        "role_none":"No Fitness account",
        "role_admin":"Fitness administrator",
        "role_local":"Local user",
        "role_remote":"Remote user",
        "account_profile":"Fitness profile",
        "account_language":"Language",
        "account_language_hint":"Menus and this user's Fitness TV dashboard use this language.",
        "configure_tv":"Configure Fitness TV",
        "configure_account":"Configure Fitness account",
        "assign_user":"Assign Home Assistant user",
        "complete_remove":"Remove completely",
        "complete_remove_confirm":"Remove this Fitness profile completely? This deletes its backend profile and all Fitness TV settings.",
        "light_feedback_on":"Light feedback on",
        "light_feedback_off":"Light feedback off",
        "tts_announcements_on":"TTS announcements on",
        "tts_announcements_off":"TTS announcements off",
        "cast_no_default_target":"Configure a default Fitness TV before casting from the admin panel.",
        "remote_slug":"Remote subdomain",
        "remote_url":"Remote URL",
        "save_account":"Save account",
        "remove_account":"Remove Fitness account",
        "delete_backend_profile":"Delete backend Fitness user",
        "delete_backend_profile_confirm":"Delete this backend Fitness user and its Fitness TV account binding?",
        "remove_account_confirm":"Remove this user's Fitness account access?",
        "wildcard_setup":"Wildcard DNS/TLS required",
        "wildcard_setup_hint":"Point *.your-domain to the same Home Assistant reverse proxy and use a certificate valid for that wildcard. Deleting a Fitness remote account blocks that slug immediately; wildcard DNS itself may still resolve.",
        "account_unassigned":"Unassigned",
        "access_saved":"Access settings saved.",
        "access_save_failed":"Unable to save Fitness access settings.",
        "remote_only_own_profile":"This account can access only its assigned Fitness profile and only through its own subdomain.",
        "local_only_own_profile":"This account can control its assigned Fitness profile from the local Home Assistant network. Additional profiles can be granted as view-only.",
        "view_only_profiles":"Additional view-only profiles",
        "view_only_profiles_hint":"These profiles are visible to the user, but the user cannot change Fitness, Fitness TV, workouts, music, sensors, Cast, or profile settings for them.",
        "access_denied":"Access denied",
        "access_denied_hint":"Your Home Assistant account does not have permission to access this Fitness TV page.",
        "view_only":"View only",
        "own_profile":"Own profile",
        "ha_admin_global_access":"Home Assistant administrators always have full access to all Fitness profiles.",
    },
    "el": {
        "fitness_accounts":"Λογαριασμοί Fitness",
        "fitness_accounts_hint":"Οι διαχειριστές Home Assistant διαχειρίζονται την πρόσβαση Fitness. Κάθε χρήστης μπορεί να έχει ένα δικό του προφίλ Fitness και επιπλέον πρόσβαση μόνο για προβολή σε άλλα προφίλ.",
        "manage_ha_users":"Διαχείριση χρηστών Home Assistant",
        "remote_base_domain":"Βασικό domain απομακρυσμένου Fitness",
        "remote_base_domain_hint":"Ρύθμισε μία φορά wildcard DNS/TLS (π.χ. *.fitness.example.com). Μετά το Fitness αντιστοιχίζει ένα λογικό subdomain σε κάθε απομακρυσμένο λογαριασμό.",
        "save_domain":"Αποθήκευση domain",
        "account_role":"Ρόλος πρόσβασης",
        "role_none":"Χωρίς λογαριασμό Fitness",
        "role_admin":"Διαχειριστής Fitness",
        "role_local":"Τοπικός χρήστης",
        "role_remote":"Απομακρυσμένος χρήστης",
        "account_profile":"Προφίλ Fitness",
        "account_language":"Γλώσσα",
        "account_language_hint":"Τα μενού και το Fitness TV αυτού του χρήστη χρησιμοποιούν αυτή τη γλώσσα.",
        "configure_tv":"Ρύθμιση Fitness TV",
        "configure_account":"Ρύθμιση λογαριασμού Fitness",
        "assign_user":"Αντιστοίχιση χρήστη Home Assistant",
        "complete_remove":"Πλήρης διαγραφή",
        "complete_remove_confirm":"Να διαγραφεί πλήρως αυτό το προφίλ Fitness; Θα διαγραφούν το backend προφίλ και όλες οι ρυθμίσεις Fitness TV.",
        "light_feedback_on":"Φωτεινή ανάδραση ενεργή",
        "light_feedback_off":"Φωτεινή ανάδραση ανενεργή",
        "tts_announcements_on":"Ανακοινώσεις TTS ενεργές",
        "tts_announcements_off":"Ανακοινώσεις TTS ανενεργές",
        "cast_no_default_target":"Ρύθμισε προεπιλεγμένη Fitness TV πριν ξεκινήσεις Cast από τη διαχείριση.",
        "remote_slug":"Απομακρυσμένο subdomain",
        "remote_url":"Απομακρυσμένο URL",
        "save_account":"Αποθήκευση λογαριασμού",
        "remove_account":"Αφαίρεση λογαριασμού Fitness",
        "delete_backend_profile":"Διαγραφή backend χρήστη Fitness",
        "delete_backend_profile_confirm":"Να διαγραφεί αυτός ο backend χρήστης Fitness και η αντιστοίχιση του λογαριασμού Fitness TV;",
        "remove_account_confirm":"Να αφαιρεθεί η πρόσβαση Fitness αυτού του χρήστη;",
        "wildcard_setup":"Απαιτείται wildcard DNS/TLS",
        "wildcard_setup_hint":"Κατεύθυνε το *.domain σου στον ίδιο reverse proxy του Home Assistant και χρησιμοποίησε πιστοποιητικό που καλύπτει το wildcard. Η διαγραφή απομακρυσμένου λογαριασμού Fitness μπλοκάρει αμέσως το slug· το wildcard DNS μπορεί να συνεχίσει να επιλύεται.",
        "account_unassigned":"Χωρίς αντιστοίχιση",
        "access_saved":"Οι ρυθμίσεις πρόσβασης αποθηκεύτηκαν.",
        "access_save_failed":"Δεν ήταν δυνατή η αποθήκευση των ρυθμίσεων πρόσβασης Fitness.",
        "remote_only_own_profile":"Ο λογαριασμός έχει πρόσβαση μόνο στο αντιστοιχισμένο προφίλ Fitness και μόνο μέσω του δικού του subdomain.",
        "local_only_own_profile":"Ο λογαριασμός μπορεί να ελέγχει το αντιστοιχισμένο προφίλ Fitness από το τοπικό δίκτυο του Home Assistant. Μπορούν να δοθούν επιπλέον προφίλ μόνο για προβολή.",
        "view_only_profiles":"Επιπλέον προφίλ μόνο για προβολή",
        "view_only_profiles_hint":"Αυτά τα προφίλ είναι ορατά στον χρήστη, αλλά δεν μπορεί να αλλάξει ρυθμίσεις Fitness/Fitness TV, προπονήσεις, μουσική, αισθητήρες, Cast ή ρυθμίσεις προφίλ.",
        "access_denied":"Δεν επιτρέπεται η πρόσβαση",
        "access_denied_hint":"Ο λογαριασμός Home Assistant δεν έχει δικαίωμα πρόσβασης σε αυτή τη σελίδα Fitness TV.",
        "view_only":"Μόνο προβολή",
        "own_profile":"Δικό μου προφίλ",
        "ha_admin_global_access":"Οι διαχειριστές Home Assistant έχουν πάντα πλήρη πρόσβαση σε όλα τα προφίλ Fitness.",
    },
    "de": {
        "fitness_accounts":"Fitness-Konten",
        "fitness_accounts_hint":"Home-Assistant-Administratoren verwalten den Fitness-Zugriff. Jeder Benutzer kann ein eigenes Fitness-Profil besitzen und zusätzlich Nur-Lese-Zugriff auf weitere Profile erhalten.",
        "manage_ha_users":"Home-Assistant-Benutzer verwalten",
        "remote_base_domain":"Basisdomain für Remote-Fitness",
        "remote_base_domain_hint":"Wildcard-DNS/TLS einmal einrichten (z. B. *.fitness.example.com). Fitness weist danach jedem Remote-Konto eine logische Subdomain zu.",
        "save_domain":"Domain speichern",
        "account_role":"Zugriffsrolle",
        "role_none":"Kein Fitness-Konto",
        "role_admin":"Fitness-Administrator",
        "role_local":"Lokaler Benutzer",
        "role_remote":"Remote-Benutzer",
        "account_profile":"Fitness-Profil",
        "account_language":"Sprache",
        "account_language_hint":"Menüs und das Fitness-TV-Dashboard dieses Benutzers verwenden diese Sprache.",
        "configure_tv":"Fitness TV konfigurieren",
        "configure_account":"Fitness-Konto konfigurieren",
        "assign_user":"Home-Assistant-Benutzer zuweisen",
        "complete_remove":"Vollständig entfernen",
        "complete_remove_confirm":"Dieses Fitness-Profil vollständig entfernen? Dadurch werden das Backend-Profil und alle Fitness-TV-Einstellungen gelöscht.",
        "light_feedback_on":"Licht-Feedback an",
        "light_feedback_off":"Licht-Feedback aus",
        "tts_announcements_on":"TTS-Ansagen an",
        "tts_announcements_off":"TTS-Ansagen aus",
        "cast_no_default_target":"Konfiguriere zuerst einen Standard-Fitness-TV, bevor du aus der Verwaltung castest.",
        "remote_slug":"Remote-Subdomain",
        "remote_url":"Remote-URL",
        "save_account":"Konto speichern",
        "remove_account":"Fitness-Konto entfernen",
        "delete_backend_profile":"Backend-Fitness-Benutzer löschen",
        "delete_backend_profile_confirm":"Diesen Backend-Fitness-Benutzer und seine Fitness-TV-Kontozuweisung löschen?",
        "remove_account_confirm":"Fitness-Zugriff dieses Benutzers entfernen?",
        "wildcard_setup":"Wildcard-DNS/TLS erforderlich",
        "wildcard_setup_hint":"Leite *.deine-domain auf denselben Home-Assistant-Reverse-Proxy und nutze ein Zertifikat für die Wildcard. Das Löschen eines Remote-Kontos sperrt den Slug sofort; das Wildcard-DNS kann weiterhin auflösen.",
        "account_unassigned":"Nicht zugewiesen",
        "access_saved":"Zugriffseinstellungen gespeichert.",
        "access_save_failed":"Fitness-Zugriffseinstellungen konnten nicht gespeichert werden.",
        "remote_only_own_profile":"Dieses Konto kann nur auf das zugewiesene Fitness-Profil und nur über seine eigene Subdomain zugreifen.",
        "local_only_own_profile":"Dieses Konto kann sein zugewiesenes Fitness-Profil im lokalen Home-Assistant-Netzwerk steuern. Weitere Profile können mit Nur-Lese-Zugriff freigegeben werden.",
        "view_only_profiles":"Zusätzliche Nur-Lese-Profile",
        "view_only_profiles_hint":"Diese Profile sind sichtbar, aber der Benutzer kann dort keine Fitness-/Fitness-TV-Einstellungen, Trainings, Musik, Sensoren, Cast- oder Profileinstellungen ändern.",
        "access_denied":"Zugriff verweigert",
        "access_denied_hint":"Dieses Home-Assistant-Konto darf diese Fitness-TV-Seite nicht öffnen.",
        "view_only":"Nur ansehen",
        "own_profile":"Eigenes Profil",
        "ha_admin_global_access":"Home-Assistant-Administratoren haben immer vollen Zugriff auf alle Fitness-Profile.",
    },
}

_DASHBOARD_LABEL_GROUPS = (
    _DASHBOARD_UI_TEXT,
    _TV_DASHBOARD_TEXT,
    _TV_DASHBOARD_SETTINGS_TEXT,
    _TV_DASHBOARD_EXTRA_TEXT,
    _TV_DASHBOARD_MUSIC_TEXT,
    _TV_DASHBOARD_INTERACTION_TEXT,
    _TV_DASHBOARD_FLOW_TEXT,
    _TV_DASHBOARD_REMOTE_TEXT,
    _TV_DASHBOARD_ACCESS_TEXT,
)
_REQUIRED_DASHBOARD_LABELS = set(DASHBOARD_LANGUAGE_AUDIT_TEXT["en"])
for _group in _DASHBOARD_LABEL_GROUPS:
    _REQUIRED_DASHBOARD_LABELS.update(_group["en"])

if tuple(_DASHBOARD_TEXT) != SUPPORTED_DASHBOARD_LANGUAGES:
    raise RuntimeError("Dashboard and audited translation language sets differ")
if set(_PACE_TEXT) != set(_DASHBOARD_TEXT):
    raise RuntimeError("Dashboard pace translations do not match supported languages")

for _code, _labels in _DASHBOARD_TEXT.items():
    # Never merge English into a non-English profile.  Older groups may be
    # partial, so the audited overlay supplies their missing native values.
    for _group in _DASHBOARD_LABEL_GROUPS:
        _labels.update(_group.get(_code, {}))
    _labels.update(DASHBOARD_LANGUAGE_AUDIT_TEXT[_code])
    _missing_labels = _REQUIRED_DASHBOARD_LABELS.difference(_labels)
    if _missing_labels:
        raise RuntimeError(
            f"Dashboard language {_code!r} is missing labels: "
            f"{sorted(_missing_labels)}"
        )
    _empty_labels = sorted(
        key for key, value in _labels.items()
        if not isinstance(value, str) or not value.strip()
    )
    if _empty_labels:
        raise RuntimeError(
            f"Dashboard language {_code!r} has empty labels: {_empty_labels}"
        )

_english_dashboard_keys = set(_DASHBOARD_TEXT["en"])
_placeholder_pattern = re.compile(r"\{([A-Za-z0-9_]+)\}")
for _code, _labels in _DASHBOARD_TEXT.items():
    if set(_labels) != _english_dashboard_keys:
        raise RuntimeError(
            f"Dashboard language {_code!r} does not have exact key parity"
        )
    for _key, _english_value in _DASHBOARD_TEXT["en"].items():
        if set(_placeholder_pattern.findall(_labels[_key])) != set(
            _placeholder_pattern.findall(_english_value)
        ):
            raise RuntimeError(
                f"Dashboard placeholder mismatch for {_code}.{_key}"
            )

def _language(entry) -> str:
    raw = str(entry.options.get(CONF_LANGUAGE, entry.data.get(CONF_LANGUAGE, "en")) or "en")
    return raw if raw in _DASHBOARD_TEXT else "en"


def _profile_name(entry) -> str:
    return str(entry.options.get(CONF_PROFILE_NAME, entry.data.get(CONF_PROFILE_NAME, entry.title)) or entry.title)


def _entity_key(entry_id: str, unique_id: str | None) -> str | None:
    prefix = f"{entry_id}_"
    if not unique_id or not unique_id.startswith(prefix):
        return None
    return unique_id[len(prefix):]


def _norm_source_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _workout_source_value(workout, field_name: str) -> Any:
    value = getattr(workout, field_name, None)
    if value is None:
        return None
    if field_name in {"duration_s", "moving_time_s", "elapsed_time_s"}:
        return round(float(value) / 60.0, 3)
    if field_name == "distance_m":
        return round(float(value) / 1000.0, 4)
    if field_name in {"average_speed_m_s", "max_speed_m_s"}:
        return round(float(value) * 3.6, 4)
    return value


def _sleep_source_value(record, field_name: str) -> Any:
    value = getattr(record, field_name, None)
    if value is None:
        return None
    if field_name in {
        "duration_s", "time_in_bed_s", "awake_s", "light_sleep_s",
        "deep_sleep_s", "rem_sleep_s",
    }:
        return round(float(value) / 60.0, 3)
    return value


def _sleep_source_metrics(hass: HomeAssistant, record) -> dict[str, dict[str, Any]]:
    """Return latest-sleep source routes plus exact missing-source substitutes."""
    if record is None:
        return {}
    result: dict[str, dict[str, Any]] = {}
    provider_values = record.provider_values or {}
    fitness_values = provider_values.get("fitness") or {}
    saa_values = provider_values.get("sleep_as_android") or {}
    healthsync_values = provider_values.get("healthsync") or {}
    healthsync_routes = healthsync_values.get("field_routes") or {}
    saa_method = saa_values.get("stage_method")
    saa_tracking = saa_values.get("tracking_entity")
    saa_phase = saa_values.get("phase_entity")
    saa_reconstructed_fields = set(saa_values.get("reconstructed_fields") or ())

    for dashboard_key, (field_name, unit) in _SLEEP_SOURCE_FIELDS.items():
        canonical = _sleep_source_value(record, field_name)
        if canonical is None:
            continue
        source = (record.field_sources or {}).get(field_name)
        route: dict[str, Any] = {
            "value": canonical,
            "unit": unit,
            "field": field_name,
            "source_type": "source",
        }

        if source == "fitness_calculated":
            # Provider omitted the fact entirely. Fitness computed a transparent
            # substitute (currently the conservative synthetic sleep score).
            route.update({
                "transform": "inline",
                "source_type": "fitness_calculated",
                "method": (
                    fitness_values.get("derived_sleep_score_method")
                    if field_name == "score" else None
                ),
            })
        elif (
            isinstance(healthsync_routes.get(field_name), dict)
            and healthsync_routes[field_name].get("entity_id") == source
            and isinstance(source, str)
            and hass.states.get(source) is not None
        ):
            # HealthSync keeps Apple Health stage totals as attributes on its
            # single "Sleep last night" sensor. Route those facts directly to
            # the original entity+attribute rather than turning them into
            # Fitness mirrors or inline copies.
            source_route = healthsync_routes[field_name]
            route["entity_id"] = source
            route["transform"] = source_route.get("transform", "state")
            if source_route.get("attribute"):
                route["attribute"] = source_route["attribute"]
            if source_route.get("unit"):
                route["unit"] = source_route["unit"]
        elif (
            saa_method == "home_assistant_recorder_event_timeline"
            and field_name in saa_reconstructed_fields
            and (
                (field_name == "duration_s" and source == saa_tracking)
                or (
                    field_name in {"awake_s", "light_sleep_s", "deep_sleep_s", "rem_sleep_s"}
                    and source == saa_phase
                )
            )
        ):
            # Sleep as Android exposes events, not scalar completed-sleep stage
            # sensors. Fitness reconstructs these exact facts from Recorder. Put
            # the low-frequency value in the map, while retaining the event
            # entity as provenance/More Info.
            route.update({
                "transform": "inline",
                "source_type": "source_reconstructed",
                "method": saa_method,
            })
            if isinstance(source, str) and hass.states.get(source) is not None:
                route["entity_id"] = source
        elif (
            field_name == "duration_s"
            and isinstance(source, str)
            and source.endswith(":classified_sleep_stages")
        ):
            # Canonical normalization: total sleep cannot be shorter than the
            # sum of Light+Deep+REM. If the provider later reports a coherent
            # duration, field_sources returns to its real entity automatically.
            route.update({
                "transform": "inline",
                "source_type": "source_normalized",
                "method": fitness_values.get(
                    "normalized_sleep_duration_method",
                    "max_provider_duration_and_classified_sleep_stages",
                ),
            })
        elif isinstance(source, str) and "." in source and hass.states.get(source) is not None:
            route["entity_id"] = source
            route["transform"] = "state"
        elif isinstance(record.source, str) and "." in record.source and hass.states.get(record.source) is not None:
            # Generic history carriers remain a websocket-backed fallback unless
            # the parser explicitly marked the value as reconstructed above.
            route["entity_id"] = record.source
            route["transform"] = "fallback"
        result[dashboard_key] = route
    return result


def _evaluation_source_metrics(hass: HomeAssistant, manager) -> dict[str, dict[str, Any]]:
    """Return direct source routes for current Evaluation inputs."""
    evaluation = manager.evaluation()
    provider = evaluation.get("provider_metrics") or {}
    result: dict[str, dict[str, Any]] = {}
    config_fallbacks = {
        "vo2max": "vo2max",
        "resting_hr": "resting_hr",
        "weight": "weight",
    }
    for dashboard_key, (provider_key, unit) in _EVALUATION_SOURCE_FIELDS.items():
        value = provider.get(provider_key)
        entity_id = provider.get(f"{provider_key}_entity")
        if value is None and dashboard_key in config_fallbacks:
            configured = manager.config.get(config_fallbacks[dashboard_key])
            if isinstance(configured, str) and "." in configured:
                entity_id = configured
                state = hass.states.get(entity_id)
                if state is not None and state.state not in ("unknown", "unavailable", ""):
                    try:
                        value = float(state.state)
                    except (TypeError, ValueError):
                        value = state.state
            elif configured is not None:
                value = configured
        if value is None:
            continue
        route: dict[str, Any] = {"value": value, "unit": unit, "field": provider_key}
        if isinstance(entity_id, str) and hass.states.get(entity_id) is not None:
            route.update({"entity_id": entity_id, "transform": "state"})
        else:
            route["transform"] = "fallback"
        result[dashboard_key] = route
    return result


def _source_entry_domain(hass: HomeAssistant, registry_entry) -> str:
    config_entry_id = getattr(registry_entry, "config_entry_id", None)
    if not config_entry_id:
        return "unknown"
    config_entry = hass.config_entries.async_get_entry(config_entry_id)
    return config_entry.domain if config_entry is not None else "unknown"


def _source_entry_label(hass: HomeAssistant, registry_entry) -> str:
    state = hass.states.get(registry_entry.entity_id)
    return " ".join((
        registry_entry.entity_id,
        registry_entry.name or "",
        registry_entry.original_name or "",
        str(state.attributes.get("friendly_name") or "") if state else "",
    )).casefold().replace("-", "_").replace(" ", "_")


def _attribute_transform(field_name: str, matched_key: str) -> str:
    key = _norm_source_key(matched_key)
    if field_name == "session_rpe" and "directworkoutrpe" in key:
        return "rpe_0_100_to_1_10"
    if field_name in {"duration_s", "moving_time_s", "elapsed_time_s"}:
        if "minute" in key or key.endswith("min"):
            return "identity"
        return "seconds_to_minutes"
    if field_name == "distance_m":
        return "meters_to_km"
    if field_name in {"average_speed_m_s", "max_speed_m_s"}:
        return "mps_to_kmh"
    return "identity"


def _workout_route_candidate_allowed(field_name: str, label: str) -> bool:
    """Reject sleep/recovery sibling sensors from completed-workout routing."""
    normalized = " ".join(str(label or "").lower().replace("_", " ").split())
    forbidden = (
        "sleep", "awake", "time in bed", "bedtime", "wake time", "wakeup",
        "rem sleep", "deep sleep", "light sleep", "sleep hrv", "sleep score",
    )
    if any(token in normalized for token in forbidden):
        return False
    if field_name in {"avg_hr", "max_hr"} and (
        "resting heart rate" in normalized or "resting hr" in normalized
    ):
        return False
    return True


def _workout_source_metrics(
    hass: HomeAssistant, manager, workout, profile_entities: dict[str, str] | None = None
) -> dict[str, dict[str, Any]]:
    """Return dashboard routes to upstream workout entities, never mirrors."""
    if workout is None:
        return {}

    selected = set(manager.config.get(CONF_WORKOUT_DEVICE_IDS) or [])
    registry = er.async_get(hass)
    source_ids = {
        source for source in (workout.sources or [])
        if isinstance(source, str) and "." in source
    }
    provider_domains = set(workout.provider_domains or [])
    candidates = []
    for registry_entry in registry.entities.values():
        if registry_entry.platform == DOMAIN:
            continue
        domain = _source_entry_domain(hass, registry_entry)
        if registry_entry.entity_id not in source_ids:
            if registry_entry.device_id not in selected:
                continue
            if provider_domains and domain not in provider_domains:
                continue
        label = _source_entry_label(hass, registry_entry)
        if not _workout_route_candidate_allowed("", label):
            continue
        candidates.append((registry_entry, domain, label))

    result: dict[str, dict[str, Any]] = {}
    for dashboard_key, (field_name, unit) in _WORKOUT_SOURCE_FIELDS.items():
        canonical = _workout_source_value(workout, field_name)
        if canonical is None:
            continue
        provider = (workout.field_sources or {}).get(field_name)

        if (
            provider == FITNESS_CALCULATED_SOURCE
            and field_name in FITNESS_FALLBACK_FACTUAL_FIELDS
        ):
            fitness_values = (workout.provider_values or {}).get("fitness") or {}
            result[dashboard_key] = {
                "value": canonical,
                "unit": unit,
                "field": field_name,
                "transform": "inline",
                "source_type": "fitness_calculated",
                "method": fitness_values.get(f"derived_{field_name}_method"),
            }
            continue

        if provider == SOURCE_RECONSTRUCTED_SOURCE and field_name == "session_rpe":
            polar_values = (workout.provider_values or {}).get("polar") or {}
            route = {
                "value": canonical,
                "unit": unit,
                "field": field_name,
                "transform": "inline",
                "source_type": "source_reconstructed",
                "method": polar_values.get("derived_session_rpe_method"),
            }
            source_entity = polar_values.get("derived_session_rpe_source_entity")
            if isinstance(source_entity, str) and hass.states.get(source_entity) is not None:
                route["entity_id"] = source_entity
            result[dashboard_key] = route
            continue

        # A workout physically created by Fitness remains Fitness-owned even
        # after Garmin/Strava enrichment. If this specific field was captured
        # by Fitness Live, route the dashboard to Fitness's own workout entity.
        # Fields whose canonical source is an upstream provider continue to
        # route directly to that provider, so no mirror is introduced.
        if workout_is_fitness_owned(workout) and provider == FITNESS_LIVE_SOURCE:
            own_value = fitness_owned_workout_value(workout, field_name)
            if own_value is not None:
                route = {
                    "value": _workout_source_value(workout, field_name),
                    "unit": unit,
                    "field": field_name,
                    "source_type": "fitness_owned",
                }
                entity_id = (profile_entities or {}).get(dashboard_key)
                if entity_id and hass.states.get(entity_id) is not None:
                    route.update({"entity_id": entity_id, "transform": "state"})
                result[dashboard_key] = route
                continue

        def score(item) -> int:
            registry_entry, domain, label = item
            value = 0
            if registry_entry.entity_id in source_ids:
                value += 100
            if domain == "healthsync":
                state = hass.states.get(registry_entry.entity_id)
                started_at = state.attributes.get("started_at") if state else None
                if started_at and str(started_at) == str(workout.start):
                    value += 150
            if provider and domain == provider:
                value += 70
            if "last" in label and any(token in label for token in ("workout", "activity", "exercise")):
                value += 20
            for token_group in _WORKOUT_STATE_TOKENS.get(field_name, ()):
                if all(token in label for token in token_group):
                    value += 60
                    break
            return value

        ordered = sorted((item for item in candidates if _workout_route_candidate_allowed(field_name, item[2])), key=score, reverse=True)
        route: dict[str, Any] = {
            "value": canonical,
            "unit": unit,
            "field": field_name,
        }

        # HealthSync recent-workout slot state is the raw Apple Health workout
        # type/name. Route the headline directly to that slot rather than to a
        # normalized fallback string.
        direct = None
        if field_name == "name":
            for registry_entry, domain, _label in ordered:
                if domain != "healthsync":
                    continue
                state = hass.states.get(registry_entry.entity_id)
                if state is None or state.state in ("unknown", "unavailable", ""):
                    continue
                started_at = state.attributes.get("started_at")
                if (
                    registry_entry.entity_id in source_ids
                    or (started_at and str(started_at) == str(workout.start))
                ):
                    direct = {
                        "entity_id": registry_entry.entity_id,
                        "transform": "state",
                    }
                    break

        # Prefer a real top-level source attribute whose key is one of the same
        # aliases used by the completed-workout normalizer.
        route_aliases = list(_FIELD_KEYS.get(field_name, ()))
        if field_name == "duration_s":
            # _extract_record deliberately falls back to moving/elapsed time if
            # a provider omits generic duration. Route to that real source fact
            # rather than carrying a copied canonical value in the map.
            route_aliases.extend(_FIELD_KEYS.get("moving_time_s", ()))
            route_aliases.extend(_FIELD_KEYS.get("elapsed_time_s", ()))
        aliases = {_norm_source_key(alias) for alias in route_aliases}
        for registry_entry, domain, label in ordered:
            if not _workout_route_candidate_allowed(field_name, label):
                continue
            if direct is not None:
                break
            if provider and domain != provider and any(item[1] == provider for item in ordered):
                continue
            state = hass.states.get(registry_entry.entity_id)
            if state is None:
                continue
            for attr_name, attr_value in state.attributes.items():
                if attr_value in (None, "", [], {}):
                    continue
                if _norm_source_key(attr_name) in aliases:
                    direct = {
                        "entity_id": registry_entry.entity_id,
                        "attribute": str(attr_name),
                        "transform": _attribute_transform(field_name, str(attr_name)),
                    }
                    break
            if direct is not None:
                break

        # Peloton exposes total output as Wh. Kilojoules are a pure unit
        # conversion, so route to that real entity with a transform instead of
        # storing an inline duplicate.
        if direct is None and field_name == "kilojoules":
            for registry_entry, domain, label in ordered:
                if domain == "peloton" and "power" in label and "output" in label:
                    direct = {
                        "entity_id": registry_entry.entity_id,
                        "transform": "wh_to_kj",
                    }
                    break

        # Sibling-sensor providers (Hevy/Oura/Peloton and similar) expose many
        # factual workout fields directly as entity states.
        if direct is None:
            token_groups = list(_WORKOUT_STATE_TOKENS.get(field_name, ()))
            if field_name == "duration_s":
                token_groups.extend(_WORKOUT_STATE_TOKENS.get("moving_time_s", ()))
                token_groups.extend(_WORKOUT_STATE_TOKENS.get("elapsed_time_s", ()))
            for registry_entry, domain, label in ordered:
                if not _workout_route_candidate_allowed(field_name, label):
                    continue
                if provider and domain != provider and any(item[1] == provider for item in ordered):
                    continue
                if token_groups and any(all(token in label for token in group) for group in token_groups):
                    direct = {
                        "entity_id": registry_entry.entity_id,
                        "transform": "state",
                    }
                    break

        # Even when a provider keeps the value in a nested activity payload,
        # keep the canonical source entity for more-info/provenance and use the
        # normalized fallback value instead of inventing a Fitness entity.
        if direct is None and ordered:
            direct = {
                "entity_id": ordered[0][0].entity_id,
                "transform": "fallback",
            }
        if direct:
            route.update(direct)
        result[dashboard_key] = route
    return result


def _route_matches_latest_workout(state, workout) -> bool:
    """Reject an explicitly stale route belonging to another workout."""
    if workout is None:
        return False
    attrs = state.attributes

    def norm(value):
        return str(value or "").strip().casefold()

    workout_name = norm(workout.name)
    route_names = [
        norm(attrs.get(key))
        for key in (
            "activity_name", "activityName", "workout_name",
            "workoutName", "name", "title",
        )
        if attrs.get(key) not in (None, "")
    ]
    if route_names and workout_name and workout_name not in route_names:
        return False

    provider_values = workout.provider_values or {}
    workout_ids = set()
    for values in provider_values.values():
        if not isinstance(values, dict):
            continue
        for key in ("activityId", "activity_id", "workoutId", "workout_id", "id"):
            value = values.get(key)
            if value not in (None, ""):
                workout_ids.add(str(value))
    route_ids = {
        str(attrs.get(key))
        for key in ("activityId", "activity_id", "workoutId", "workout_id")
        if attrs.get(key) not in (None, "")
    }
    if workout_ids and route_ids and workout_ids.isdisjoint(route_ids):
        return False
    return True


def _route_candidates(hass: HomeAssistant, manager) -> list[dict[str, Any]]:
    """Return route data only when it belongs to the current merged workout."""
    selected = set(manager.config.get(CONF_WORKOUT_DEVICE_IDS) or [])
    latest = manager.latest_workout()
    if latest is None:
        return []
    inline = (latest.extra or {}).get("gps_points") if isinstance(latest.extra, dict) else None
    result: list[dict[str, Any]] = []
    if isinstance(inline, list) and len(inline) >= 2:
        result.append({"value": inline, "attribute": "gps_points", "source": "fitness_workout"})
    if not selected:
        return result
    registry = er.async_get(hass)
    for registry_entry in registry.entities.values():
        if registry_entry.device_id not in selected:
            continue
        state = hass.states.get(registry_entry.entity_id)
        if state is None or not _route_matches_latest_workout(state, latest):
            continue
        attrs = state.attributes
        label = " ".join((
            registry_entry.entity_id,
            registry_entry.name or "",
            registry_entry.original_name or "",
        )).lower()
        for attribute in ("polyline", "route", "coordinates", "track", "gps_points"):
            value = attrs.get(attribute)
            if value not in (None, "", [], {}):
                result.append({"entity_id": registry_entry.entity_id, "attribute": attribute})
                break
        else:
            if any(token in label for token in ("route", "polyline", "gps", "track")):
                for attribute, value in attrs.items():
                    attr_lower = str(attribute).lower()
                    if any(token in attr_lower for token in ("polyline", "route", "coordinates", "track")) and value not in (None, "", [], {}):
                        result.append({"entity_id": registry_entry.entity_id, "attribute": str(attribute)})
                        break
    return result


def _profile_data_routes(hass: HomeAssistant, entity_id: str | None) -> dict[str, dict[str, Any]]:
    """Read routing metadata from one stable profile data-map sensor."""
    if not entity_id:
        return {}
    state = hass.states.get(entity_id)
    if state is None:
        return {}
    return routes_from_attributes(dict(state.attributes or {}))


def _with_workout_fallback_values(routes: dict[str, dict[str, Any]], workout) -> dict[str, dict[str, Any]]:
    """Attach transient display fallbacks without persisting mirror attributes."""
    result = {key: dict(route) for key, route in routes.items()}
    if workout is None:
        return result
    for key, (field_name, unit) in _WORKOUT_SOURCE_FIELDS.items():
        route = result.get(key)
        if route is None:
            continue
        route.setdefault("field", field_name)
        route.setdefault("unit", unit)
        value = _workout_source_value(workout, field_name)
        if value is not None:
            route["value"] = value
    return result


def _with_sleep_fallback_values(routes: dict[str, dict[str, Any]], record) -> dict[str, dict[str, Any]]:
    result = {key: dict(route) for key, route in routes.items()}
    if record is None:
        return result
    for key, (field_name, unit) in _SLEEP_SOURCE_FIELDS.items():
        route = result.get(key)
        if route is None:
            continue
        route.setdefault("field", field_name)
        route.setdefault("unit", unit)
        value = _sleep_source_value(record, field_name)
        if value is not None:
            route["value"] = value
    return result


def _fitness_audio_outputs(hass: HomeAssistant, registry: er.EntityRegistry) -> list[dict[str, Any]]:
    """Return every live HA media player that can accept Fitness audio."""
    outputs: list[dict[str, Any]] = []
    play_media = int(MediaPlayerEntityFeature.PLAY_MEDIA)
    for state in hass.states.async_all("media_player"):
        registry_entry = registry.async_get(state.entity_id)
        if registry_entry is not None and registry_entry.disabled_by is not None:
            continue
        try:
            supported = int(state.attributes.get("supported_features", 0) or 0)
        except (TypeError, ValueError):
            supported = 0
        platform = str(registry_entry.platform or "") if registry_entry is not None else ""
        ma_managed = (
            platform in {"music_assistant", "mass"}
            or bool(state.attributes.get("mass_player_type"))
        )
        if not (supported & play_media) and not ma_managed:
            continue
        name = (
            state.attributes.get("friendly_name")
            or (registry_entry.name if registry_entry is not None else None)
            or state.entity_id
        )
        outputs.append({
            "entity_id": state.entity_id,
            "name": str(name),
            "platform": platform,
            "music_assistant": ma_managed,
            "state": state.state,
            "device_class": str(state.attributes.get("device_class") or ""),
        })
    return sorted(
        outputs,
        key=lambda item: (
            not bool(item["music_assistant"]),
            str(item["name"]).casefold(),
            item["entity_id"],
        ),
    )


def _tv_overview_cast_state(hass: HomeAssistant) -> dict[str, Any]:
    """Return the server-owned state for the castable Fitness TV overview."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    state = domain_data.get(_TV_OVERVIEW_CAST_STATE_KEY)
    if not isinstance(state, dict):
        state = {"active": False, "target": ""}
        domain_data[_TV_OVERVIEW_CAST_STATE_KEY] = state
    return state


def _tv_overview_cast_descriptor(hass: HomeAssistant) -> dict[str, Any]:
    """Return dashboard-safe overview Cast state."""
    state = _tv_overview_cast_state(hass)
    return {
        "active": bool(state.get("active")),
        "target": str(state.get("target") or "") or None,
    }


def _tv_cast_targets(hass: HomeAssistant, registry: er.EntityRegistry) -> list[dict[str, Any]]:
    """Return enabled Google Cast media players for the TV dashboard picker."""
    targets: list[dict[str, Any]] = []
    for registry_entry in registry.entities.values():
        if registry_entry.platform != "cast":
            continue
        if not registry_entry.entity_id.startswith("media_player."):
            continue
        if registry_entry.disabled_by is not None:
            continue
        state = hass.states.get(registry_entry.entity_id)
        friendly_name = (
            state.attributes.get("friendly_name") if state is not None else None
        ) or registry_entry.name or registry_entry.entity_id
        targets.append(
            {
                "entity_id": registry_entry.entity_id,
                "name": str(friendly_name),
                "available": state is not None and state.state != "unavailable",
                "state": state.state if state is not None else "unavailable",
            }
        )
    return sorted(targets, key=lambda item: (str(item["name"]).casefold(), item["entity_id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/dashboard/flow_translations",
        vol.Optional("language", default="en"): vol.All(str, vol.Length(max=16)),
    }
)
@websocket_api.async_response
async def websocket_dashboard_flow_translations(hass: HomeAssistant, connection, msg) -> None:
    """Return the integration's config/options-flow translations for the UI language."""
    language = str(msg.get("language") or "en").lower().split("-", 1)[0]
    if language not in SUPPORTED_DASHBOARD_LANGUAGES:
        language = "en"
    translations_dir = Path(__file__).parent / "translations"
    source = translations_dir / f"{language}.json"
    if not source.is_file():
        source = translations_dir / "en.json"

    def _read() -> dict[str, Any]:
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {
            "config": data.get("config") if isinstance(data.get("config"), dict) else {},
            "options": data.get("options") if isinstance(data.get("options"), dict) else {},
            "selector": data.get("selector") if isinstance(data.get("selector"), dict) else {},
        }

    connection.send_result(msg["id"], await hass.async_add_executor_job(_read))


def _serialize_fitness_options_flow_result(result: dict[str, Any]) -> dict[str, Any]:
    """Serialize an options-flow result using Home Assistant's frontend contract."""
    if result.get("type") is data_entry_flow.FlowResultType.CREATE_ENTRY:
        data = {
            key: value
            for key, value in result.items()
            if key not in ("data", "context")
        }
    else:
        data = dict(result)
        if "data_schema" in result:
            schema = result.get("data_schema")
            data["data_schema"] = (
                []
                if schema is None
                else voluptuous_serialize.convert(
                    schema, custom_serializer=cv.custom_serializer
                )
            )
    flow_type = data.get("type")
    if hasattr(flow_type, "value"):
        data["type"] = flow_type.value
    return data


def _fitness_options_profile_entry(hass: HomeAssistant, profile_entry_id: str):
    """Return a real Fitness profile entry, excluding the shared live hub."""
    entry = hass.config_entries.async_get_entry(str(profile_entry_id))
    if (
        entry is None
        or entry.domain != DOMAIN
        or entry.data.get("entry_type") == "live_hub"
    ):
        return None
    return entry


async def _require_fitness_options_profile_control(
    hass: HomeAssistant, connection, profile_entry_id: str
):
    """Authorize options-flow access to one controlled Fitness profile."""
    entry = _fitness_options_profile_entry(hass, profile_entry_id)
    if entry is None:
        raise ValueError("profile_not_found")
    await get_fitness_access_controller(hass).async_require_profile_control(
        connection, entry.entry_id, cast_hub=get_tv_dashboard_hub(hass)
    )
    return entry


def _fitness_options_flow_matches_profile(
    hass: HomeAssistant, flow_id: str, profile_entry_id: str
) -> bool:
    """Return whether an active options flow belongs to the requested profile."""
    try:
        flow = hass.config_entries.options.async_get(str(flow_id))
    except data_entry_flow.UnknownFlow:
        return False
    return str(flow.get("handler") or "") == str(profile_entry_id)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/dashboard/options_flow/start",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    }
)
@websocket_api.async_response
async def websocket_dashboard_options_flow_start(
    hass: HomeAssistant, connection, msg
) -> None:
    """Start the controlled profile's Fitness options flow for any authorized user."""
    try:
        entry = await _require_fitness_options_profile_control(
            hass, connection, msg["profile_entry_id"]
        )
        result = await hass.config_entries.options.async_init(entry.entry_id)
    except ValueError as err:
        connection.send_error(msg["id"], "profile_not_found", str(err))
        return
    connection.send_result(msg["id"], _serialize_fitness_options_flow_result(result))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/dashboard/options_flow/step",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("flow_id"): vol.All(str, vol.Length(max=128)),
        vol.Optional("user_input"): vol.All(
            dict,
            bounded_websocket_payload(max_nodes=2_048, max_depth=8, max_string_length=8_192),
        ),
    }
)
@websocket_api.async_response
async def websocket_dashboard_options_flow_step(
    hass: HomeAssistant, connection, msg
) -> None:
    """Continue or poll an authorized Fitness options flow."""
    entry = await _require_fitness_options_profile_control(
        hass, connection, msg["profile_entry_id"]
    )
    if not _fitness_options_flow_matches_profile(hass, msg["flow_id"], entry.entry_id):
        connection.send_error(msg["id"], "invalid_flow", "Fitness options flow not found")
        return
    try:
        if "user_input" in msg:
            result = await hass.config_entries.options.async_configure(
                msg["flow_id"], msg["user_input"]
            )
        else:
            result = await hass.config_entries.options.async_configure(msg["flow_id"])
    except data_entry_flow.UnknownFlow:
        connection.send_error(msg["id"], "invalid_flow", "Fitness options flow not found")
        return
    except data_entry_flow.InvalidData as err:
        connection.send_error(msg["id"], "invalid_data", str(err))
        return
    connection.send_result(msg["id"], _serialize_fitness_options_flow_result(result))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/dashboard/options_flow/cancel",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("flow_id"): vol.All(str, vol.Length(max=128)),
    }
)
@websocket_api.async_response
async def websocket_dashboard_options_flow_cancel(
    hass: HomeAssistant, connection, msg
) -> None:
    """Cancel an authorized Fitness options flow."""
    entry = await _require_fitness_options_profile_control(
        hass, connection, msg["profile_entry_id"]
    )
    if not _fitness_options_flow_matches_profile(hass, msg["flow_id"], entry.entry_id):
        connection.send_error(msg["id"], "invalid_flow", "Fitness options flow not found")
        return
    try:
        hass.config_entries.options.async_abort(msg["flow_id"])
    except data_entry_flow.UnknownFlow:
        connection.send_error(msg["id"], "invalid_flow", "Fitness options flow not found")
        return
    connection.send_result(msg["id"], {"aborted": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/overview/cast",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_tv_overview_cast(hass: HomeAssistant, connection, msg) -> None:
    """Cast the complete Fitness TV user overview to one HA Cast target."""
    access = await get_fitness_access_controller(hass).async_descriptor(connection)
    if not access.get("is_admin"):
        connection.send_error(msg["id"], "unauthorized", "Fitness administrator access required")
        return
    target = str(msg.get("entity_id") or "").strip()
    registry = er.async_get(hass)
    entry = registry.async_get(target)
    if (
        not target
        or entry is None
        or entry.platform != "cast"
        or not target.startswith("media_player.")
        or entry.disabled_by is not None
    ):
        connection.send_error(msg["id"], "invalid_cast_target", "Google Cast media player required")
        return
    if not hass.services.has_service("cast", "show_lovelace_view"):
        connection.send_error(msg["id"], "cast_unavailable", "Home Assistant Cast service unavailable")
        return
    try:
        await _async_wake_cast_target(hass, target)
        await async_call_service(
            hass,
            "cast",
            "show_lovelace_view",
            {
                "entity_id": target,
                "dashboard_path": TV_DASHBOARD_PATH,
                "view_path": "cast-overview",
            },
            blocking=True,
            timeout=30.0,
        )
    except Exception as err:  # noqa: BLE001 - keep provider details in server logs
        _LOGGER.warning("Unable to start Fitness overview Cast", exc_info=err)
        connection.send_error(msg["id"], "cast_failed", "Unable to start Fitness Cast")
        return
    state = _tv_overview_cast_state(hass)
    state.update({"active": True, "target": target})
    connection.send_result(msg["id"], _tv_overview_cast_descriptor(hass))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/tv/overview/stop",
        vol.Optional("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_tv_overview_stop(hass: HomeAssistant, connection, msg) -> None:
    """Stop the currently cast Fitness TV overview without touching profile Casts."""
    access = await get_fitness_access_controller(hass).async_descriptor(connection)
    if not access.get("is_admin"):
        connection.send_error(msg["id"], "unauthorized", "Fitness administrator access required")
        return
    state = _tv_overview_cast_state(hass)
    target = str(msg.get("entity_id") or state.get("target") or "").strip()
    if target:
        try:
            await _async_stop_existing_ha_cast_receiver(hass, target)
        except Exception:  # noqa: BLE001 - stopping the overview is best-effort
            _LOGGER.debug("Unable to stop Fitness TV overview Cast on %s", target, exc_info=True)
    state.update({"active": False, "target": ""})
    connection.send_result(msg["id"], _tv_overview_cast_descriptor(hass))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/weight/subscribe",
        vol.Required("profile_entry_id"): str,
    }
)
@websocket_api.async_response
async def websocket_weight_subscribe(hass: HomeAssistant, connection, msg) -> None:
    """Stream pending shared-scale confirmations visible to this dashboard user."""
    requested = str(msg["profile_entry_id"])
    access_controller = get_fitness_access_controller(hass)
    allowed = set(await access_controller.async_control_profile_ids(connection))
    if requested not in allowed:
        connection.send_error(msg["id"], "unauthorized", "Fitness profile control access required")
        return
    from .weight_scales import get_weight_scale_router

    router = get_weight_scale_router(hass)
    await router.async_initialize()

    @callback
    def _forward() -> None:
        connection.send_event(
            msg["id"],
            {
                "measurements": router.pending_for(
                    allowed, require_profile_id=requested
                )
            },
        )

    connection.subscriptions[msg["id"]] = router.async_add_listener(_forward)
    connection.send_result(msg["id"])
    _forward()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/weight/admin/subscribe",
    }
)
@websocket_api.async_response
async def websocket_weight_admin_subscribe(hass: HomeAssistant, connection, msg) -> None:
    """Stream every pending shared-scale confirmation to Fitness administrators."""
    access_controller = get_fitness_access_controller(hass)
    access = await access_controller.async_descriptor(connection)
    if not access.get("is_admin"):
        connection.send_error(msg["id"], "unauthorized", "Fitness administrator access required")
        return
    allowed = set(await access_controller.async_control_profile_ids(connection))
    from .weight_scales import get_weight_scale_router

    router = get_weight_scale_router(hass)
    await router.async_initialize()

    @callback
    def _forward() -> None:
        connection.send_event(
            msg["id"],
            {"measurements": router.pending_for(allowed)},
        )

    connection.subscriptions[msg["id"]] = router.async_add_listener(_forward)
    connection.send_result(msg["id"])
    _forward()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/weight/confirm",
        vol.Required("measurement_id"): str,
        vol.Required("profile_entry_id"): str,
    }
)
@websocket_api.async_response
async def websocket_weight_confirm(hass: HomeAssistant, connection, msg) -> None:
    """Apply one explicitly confirmed shared-scale measurement."""
    access_controller = get_fitness_access_controller(hass)
    allowed = set(await access_controller.async_control_profile_ids(connection))
    from .weight_scales import get_weight_scale_router

    ok = await get_weight_scale_router(hass).async_confirm(
        str(msg["measurement_id"]), str(msg["profile_entry_id"]), allowed
    )
    if not ok:
        connection.send_error(msg["id"], "not_found_or_unauthorized", "Weight measurement cannot be applied")
        return
    connection.send_result(msg["id"], {"confirmed": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/weight/dismiss",
        vol.Required("measurement_id"): str,
        vol.Optional("profile_entry_id"): str,
    }
)
@websocket_api.async_response
async def websocket_weight_dismiss(hass: HomeAssistant, connection, msg) -> None:
    """Dismiss a scale question for one user, or globally when an admin chooses Ignore."""
    access_controller = get_fitness_access_controller(hass)
    allowed = set(await access_controller.async_control_profile_ids(connection))
    access = await access_controller.async_descriptor(connection)
    from .weight_scales import get_weight_scale_router

    router = get_weight_scale_router(hass)
    profile_entry_id = str(msg.get("profile_entry_id") or "").strip()
    if profile_entry_id:
        ok = await router.async_dismiss_for_profile(
            str(msg["measurement_id"]), profile_entry_id, allowed
        )
    else:
        if not access.get("is_admin"):
            connection.send_error(msg["id"], "unauthorized", "Fitness administrator access required")
            return
        ok = await router.async_dismiss(str(msg["measurement_id"]), allowed)
    if not ok:
        connection.send_error(msg["id"], "not_found_or_unauthorized", "Weight measurement cannot be dismissed")
        return
    connection.send_result(msg["id"], {"dismissed": True})


async def _dashboard_profile_for_view(
    hass: HomeAssistant, connection, profile_entry_id: str
):
    entry = _fitness_options_profile_entry(hass, profile_entry_id)
    if entry is None:
        raise ValueError("profile_not_found")
    visible = await get_fitness_access_controller(hass).async_visible_profile_ids(
        connection, cast_hub=get_tv_dashboard_hub(hass)
    )
    if entry.entry_id not in visible:
        raise ValueError("profile_not_found")
    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager is None:
        raise ValueError("profile_unavailable")
    return entry, manager


def _dashboard_workout_item(manager, entry_id: str, workout) -> dict[str, Any]:
    uid = manager._calendar_uid(entry_id, workout)
    return {
        "uid": uid,
        "start": workout.start,
        "end": workout.end,
        "name": workout.name,
        "sport": workout.sport,
        "duration_s": workout.duration_s,
        "distance_m": workout.distance_m,
        "avg_hr": workout.avg_hr,
        "calories": workout.calories,
        "source": workout.source,
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/workouts/list",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Optional("limit", default=100): vol.All(int, vol.Range(min=1, max=200)),
    }
)
@websocket_api.async_response
async def websocket_workouts_list(hass: HomeAssistant, connection, msg) -> None:
    """Return a bounded newest-first canonical workout list."""
    try:
        entry, manager = await _dashboard_profile_for_view(
            hass, connection, msg["profile_entry_id"]
        )
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    all_workouts = manager.local_workouts()
    workouts = sorted(
        all_workouts,
        key=lambda item: str(item.start or ""),
        reverse=True,
    )[: int(msg.get("limit", 100))]
    connection.send_result(
        msg["id"],
        {
            "workouts": [
                _dashboard_workout_item(manager, entry.entry_id, workout)
                for workout in workouts
            ],
            "total": len(all_workouts),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/workouts/delete",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("workout_ids"): vol.All(
            [vol.All(str, vol.Length(min=1, max=256))], vol.Length(min=1, max=100)
        ),
    }
)
@websocket_api.async_response
async def websocket_workouts_delete(hass: HomeAssistant, connection, msg) -> None:
    """Delete selected workouts in one bounded persistence transaction."""
    try:
        entry = await _require_fitness_options_profile_control(
            hass, connection, msg["profile_entry_id"]
        )
    except ValueError as err:
        connection.send_error(msg["id"], "profile_not_found", str(err))
        return
    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager is None:
        connection.send_error(msg["id"], "profile_unavailable", "Fitness profile unavailable")
        return
    deleted = await manager.async_delete_calendar_workouts(
        list(msg["workout_ids"]), entry.entry_id
    )
    connection.send_result(msg["id"], {"deleted": deleted})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/workouts/empty",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
        vol.Required("confirm"): bool,
    }
)
@websocket_api.async_response
async def websocket_workouts_empty(hass: HomeAssistant, connection, msg) -> None:
    """Empty current canonical history only after an explicit confirmation."""
    if not msg.get("confirm"):
        connection.send_error(msg["id"], "confirmation_required", "Confirmation required")
        return
    try:
        entry = await _require_fitness_options_profile_control(
            hass, connection, msg["profile_entry_id"]
        )
    except ValueError as err:
        connection.send_error(msg["id"], "profile_not_found", str(err))
        return
    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager is None:
        connection.send_error(msg["id"], "profile_unavailable", "Fitness profile unavailable")
        return
    deleted = await manager.async_empty_workout_history()
    connection.send_result(msg["id"], {"deleted": deleted})


def _dashboard_scale_body_metrics(hass: HomeAssistant, manager) -> dict[str, Any]:
    """Read conservative current body-composition facts from the configured scale device."""
    scale_entity_id = str(manager.config.get(CONF_WEIGHT_SCALE_ENTITY) or "").strip()
    if not scale_entity_id:
        return {}
    registry = er.async_get(hass)
    root = registry.async_get(scale_entity_id)
    device_id = root.device_id if root is not None else None
    if not device_id:
        return {}
    result: dict[str, Any] = {}
    specs = (
        ("body_fat_percent", ("body", "fat"), "%"),
        ("body_water_percent", ("body", "water"), "%"),
        ("muscle_mass_kg", ("muscle", "mass"), "kg"),
        ("bone_mass_kg", ("bone", "mass"), "kg"),
    )
    for entry in registry.entities.values():
        if entry.device_id != device_id or entry.disabled_by is not None:
            continue
        state = hass.states.get(entry.entity_id)
        if state is None or state.state in {"unknown", "unavailable", ""}:
            continue
        text = " ".join(
            (entry.entity_id, entry.name or "", entry.original_name or "")
        ).lower().replace("_", " ")
        unit = str(state.attributes.get("unit_of_measurement") or "")
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            continue
        for key, tokens, required_unit in specs:
            if key in result or not all(token in text for token in tokens):
                continue
            if unit != required_unit:
                continue
            if required_unit == "%" and not 0 <= value <= 100:
                continue
            if required_unit == "kg" and not 0 <= value <= 500:
                continue
            result[key] = round(value, 2)
            result[f"{key}_entity_id"] = entry.entity_id
    return result


@websocket_api.websocket_command(
    {
        vol.Required("type"): "fitness/body_composition",
        vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    }
)
@websocket_api.async_response
async def websocket_body_composition(hass: HomeAssistant, connection, msg) -> None:
    """Return bounded Fitness-owned body-mass trend data on demand."""
    try:
        _entry, manager = await _dashboard_profile_for_view(
            hass, connection, msg["profile_entry_id"]
        )
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
        return
    weight = manager.current_weight_kg
    try:
        height_cm = float(manager.input_value(CONF_HEIGHT) or 0)
    except (TypeError, ValueError):
        height_cm = 0
    bmi = None
    if weight is not None and 50 <= height_cm <= 260:
        bmi = round(float(weight) / ((height_cm / 100.0) ** 2), 2)
    summary = dict(manager.long_term_statistics.get("weight") or {})
    daily = list(summary.get("daily") or [])[-90:]
    if not daily:
        daily = [
            {"start": item.get("timestamp"), "value": item.get("value")}
            for item in (manager.metric_history.get("weight") or [])[-90:]
            if isinstance(item, dict)
        ]
    connection.send_result(
        msg["id"],
        {
            "current_weight_kg": weight,
            "current_weight_updated_at": manager.current_weight_updated_at,
            "current_weight_source": manager.current_weight_source,
            "bmi": bmi,
            "trend_30d_percent": summary.get("slope_percent_per_30d"),
            "mean_28d": summary.get("mean_28d"),
            "daily": daily[:90],
            **_dashboard_scale_body_metrics(hass, manager),
        },
    )


def _dashboard_profile_preferences(config: dict[str, Any]) -> dict[str, Any]:
    """Return bounded presentation-only dashboard configuration."""
    modules = [
        str(item)
        for item in (config.get(CONF_DASHBOARD_MODULES) or DEFAULT_DASHBOARD_MODULES)
        if isinstance(item, str)
    ][:20]
    return {
        "theme": str(config.get(CONF_DASHBOARD_THEME) or "default")[:128],
        "modules": modules or list(DEFAULT_DASHBOARD_MODULES),
        "rss_entity_ids": [str(x) for x in (config.get(CONF_DASHBOARD_RSS_ENTITY_IDS) or [])][:20],
        "music_entity_ids": [str(x) for x in (config.get(CONF_DASHBOARD_MUSIC_ENTITY_IDS) or [])][:10],
        "light_entity_ids": [str(x) for x in (config.get(CONF_DASHBOARD_LIGHT_ENTITY_IDS) or [])][:30],
        "video_entity_ids": [str(x) for x in (config.get(CONF_DASHBOARD_VIDEO_ENTITY_IDS) or [])][:10],
        "weather_entity_id": str(config.get(CONF_DASHBOARD_WEATHER_ENTITY_ID) or "")[:128] or None,
        "tts_entity_id": str(config.get(CONF_TTS_ENTITY_ID) or "")[:128] or None,
        "tts_media_player_ids": [str(x) for x in (config.get(CONF_TTS_MEDIA_PLAYER_IDS) or [])][:10],
    }


@websocket_api.websocket_command({vol.Required("type"): "fitness/dashboard/config"})
@websocket_api.async_response
async def websocket_dashboard_config(hass: HomeAssistant, connection, msg) -> None:
    """Return dashboard-safe profile metadata and entity mappings."""
    # Reconcile the managed Lovelace views whenever the setup card refreshes.
    # Access-role/profile changes can leave a valid profile row pointing at a
    # stale/missing storage view until the next HA restart otherwise.
    # The old request path used ``await async_ensure_tv_dashboard(hass)`` here.
    # Coalescing it preserves reconciliation without holding every browser call.
    _schedule_dashboard_reconcile(hass)
    registry = er.async_get(hass)
    profiles: list[dict[str, Any]] = []
    access_controller = get_fitness_access_controller(hass)
    tv_hub = get_tv_dashboard_hub(hass)
    visible_profile_ids = await access_controller.async_visible_profile_ids(
        connection, cast_hub=tv_hub
    )
    control_profile_ids = await access_controller.async_control_profile_ids(
        connection, cast_hub=tv_hub
    )
    access = await access_controller.async_descriptor(connection)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id not in visible_profile_ids:
            continue
        manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if manager is None:
            # Do not make an existing Fitness profile disappear from the TV
            # setup page merely because its runtime manager is temporarily
            # unavailable/reloading. This is especially confusing after access
            # role changes because the account still owns the profile.
            config = {**entry.data, **entry.options}
            lang = _language(entry)
            tv_preferences = await tv_hub.async_preferences(entry.entry_id)
            profiles.append(
                {
                    "entry_id": entry.entry_id,
                    "profile_name": _profile_name(entry),
                    "access": {
                        "can_view": True,
                        "can_control": entry.entry_id in control_profile_ids,
                        "is_own": entry.entry_id == access.get("profile_entry_id"),
                        "mode": "control" if entry.entry_id in control_profile_ids else "view",
                    },
                    "language": lang,
                    "dashboard_preferences": _dashboard_profile_preferences(config),
                    "labels": {
                        **_DASHBOARD_TEXT[lang],
                        "pace": _PACE_TEXT[lang],
                    },
                    "labels_by_language": {
                        code: {
                            **labels,
                            "pace": _PACE_TEXT[code],
                        }
                        for code, labels in _DASHBOARD_TEXT.items()
                    },
                    "entities": {},
                    "data_entities": {
                        "workout": None,
                        "live": None,
                        "recovery": None,
                        "evaluation": None,
                    },
                    "live_entity_keys": [],
                    "latest_workout": {
                        "available": False,
                        "sport": None,
                        "name": None,
                        "fitness_owned": False,
                    },
                    "workout_source_metrics": {},
                    "sleep_source_metrics": {},
                    "evaluation_source_metrics": {},
                    "tv_dashboard": {
                        "enabled": bool(config.get(CONF_TV_DASHBOARD_ENABLED, False)),
                        "ytdlp_enabled": bool(config.get(CONF_TV_YTDLP_ENABLED, False)),
                        "cast_media_player_id": str(
                            config.get(CONF_TV_MEDIA_PLAYER_ID) or ""
                        )
                        or None,
                        "cast_active": tv_hub.is_cast_active(entry.entry_id),
                        "local_cast_active": tv_hub.is_local_cast_active(entry.entry_id),
                        "cast_target": tv_hub.cast_target(entry.entry_id),
                        "ducking_percent": max(
                            0,
                            min(
                                100,
                                int(
                                    config.get(
                                        CONF_TV_DUCKING_PERCENT,
                                        DEFAULT_TV_DUCKING_PERCENT,
                                    )
                                ),
                            ),
                        ),
                        "ignore_lights_when_cast_active": bool(
                            config.get(
                                CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                                DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                            )
                        ),
                        "tv_scale_percent": int(
                            tv_preferences.get(
                                "tv_scale_percent", DEFAULT_TV_SCALE_PERCENT
                            )
                        ),
                        "oled_protection": bool(
                            tv_preferences.get(
                                "oled_protection", DEFAULT_TV_OLED_PROTECTION
                            )
                        ),
                        "animations_enabled": bool(tv_preferences.get("animations_enabled", True)),
                        "light_feedback_enabled": bool(tv_preferences.get("light_feedback_enabled", True)),
                        "tts_announcements_enabled": bool(tv_preferences.get("tts_announcements_enabled", True)),
                        "music_search_limit": int(
                            tv_preferences.get("music_search_limit", 50)
                        ),
                        "last_media": dict(tv_preferences.get("last_media") or {}),
                        "audio_output_id": str(tv_preferences.get("audio_output_id") or "__fitness_browser__"),
                    },
                    "route_candidates": {},
                    "runtime_available": False,
                }
            )
            continue
        entities: dict[str, str] = {}
        for registry_entry in registry.entities.values():
            if registry_entry.config_entry_id != entry.entry_id:
                continue
            if registry_entry.platform != DOMAIN:
                continue
            key = _entity_key(entry.entry_id, registry_entry.unique_id)
            if key:
                entities[key] = registry_entry.entity_id
        lang = _language(entry)
        latest_workout = manager.latest_workout()
        latest_sleep = manager.latest_sleep()

        data_entities = {
            "workout": entities.get(DATA_MAP_KIND_TO_KEY["workout"]),
            "live": entities.get(DATA_MAP_KIND_TO_KEY["live"]),
            "recovery": entities.get(DATA_MAP_KIND_TO_KEY["sleep"]),
            "evaluation": entities.get(DATA_MAP_KIND_TO_KEY["evaluation"]),
        }
        live_routes = _profile_data_routes(hass, data_entities["live"])
        workout_routes = _profile_data_routes(hass, data_entities["workout"])
        recovery_routes = _profile_data_routes(hass, data_entities["recovery"])
        evaluation_routes = _profile_data_routes(hass, data_entities["evaluation"])

        # Bootstrap compatibility: the map sensors are populated asynchronously
        # after profile setup so HA startup stays non-blocking. If a dashboard is
        # opened during that brief window, resolve once using the old backend
        # helpers. Normal dashboard operation reads only the stable map sensors.
        if not workout_routes and latest_workout is not None:
            workout_routes = _workout_source_metrics(
                hass, manager, latest_workout, entities
            )
        if not recovery_routes and latest_sleep is not None:
            recovery_routes = _sleep_source_metrics(hass, latest_sleep)
        if not evaluation_routes:
            evaluation_routes = _evaluation_source_metrics(hass, manager)

        workout_source_metrics = _with_workout_fallback_values(
            workout_routes, latest_workout
        )
        sleep_source_metrics = _with_sleep_fallback_values(
            recovery_routes, latest_sleep
        )
        evaluation_source_metrics = {
            key: {
                **route,
                **(
                    {"value": route.get("configured_value")}
                    if route.get("transform") == "configured"
                    and route.get("configured_value") is not None
                    else {}
                ),
            }
            for key, route in evaluation_routes.items()
        }

        # Compatibility aliases for existing Live card code. These keys point
        # directly at the physical/source entities from live_data; they are not
        # Fitness mirrors and can change without recreating profile entities.
        for key in LIVE_RAW_ROUTE_KEYS:
            source = (live_routes.get(key) or {}).get("entity_id")
            if source:
                entities[key] = source

        runtime = get_live_runtime(hass)
        assigned_live_sensors = [
            sensor
            for sensor in runtime.sensors_for_profile(entry)
            if runtime.sensor_is_accepted(runtime.resolve_sensor_id(sensor.sensor_id))
        ]
        assigned_live_sensor_ids = list(
            dict.fromkeys(
                runtime.resolve_sensor_id(sensor.sensor_id)
                for sensor in assigned_live_sensors
            )
        )
        live_sensor_metrics: list[dict[str, str]] = []
        seen_live_sensor_entities = {
            str(value) for value in entities.values() if isinstance(value, str)
        }
        for sensor in assigned_live_sensors:
            sensor_id = runtime.resolve_sensor_id(sensor.sensor_id)
            owner_entity_id = physical_workout_owner_entity_id(hass, sensor_id)
            metric_names = set(sensor.capabilities or ()) | set(
                runtime.sensor_values.get(sensor_id, {})
            )
            for metric in sorted(metric_names):
                metric_entity_id = physical_metric_entity_id(hass, sensor_id, metric)
                if not metric_entity_id or metric_entity_id in seen_live_sensor_entities:
                    continue
                seen_live_sensor_entities.add(metric_entity_id)
                live_sensor_metrics.append(
                    {
                        "entity_id": metric_entity_id,
                        "owner_entity_id": owner_entity_id or "",
                        "sensor_id": sensor_id,
                        "metric": str(metric),
                    }
                )

        tv_preferences = await get_tv_dashboard_hub(hass).async_preferences(entry.entry_id)

        profiles.append(
            {
                "entry_id": entry.entry_id,
                "profile_name": _profile_name(entry),
                "access": {
                    "can_view": True,
                    "can_control": entry.entry_id in control_profile_ids,
                    "is_own": entry.entry_id == access.get("profile_entry_id"),
                    "mode": "control" if entry.entry_id in control_profile_ids else "view",
                },
                "language": lang,
                "dashboard_preferences": _dashboard_profile_preferences(manager.config),
                "labels": {**_DASHBOARD_TEXT[lang], "pace": _PACE_TEXT[lang]},
                "labels_by_language": {
                    code: {**labels, "pace": _PACE_TEXT[code]}
                    for code, labels in _DASHBOARD_TEXT.items()
                },
                "entities": entities,
                "data_entities": data_entities,
                # Assignment is the visibility contract for the Live Workout
                # card. Keep it independent from physical metric entity
                # materialization so a newly assigned sensor cannot leave the
                # card hidden while entity-registry rows are created later.
                "has_assigned_live_sensor": bool(assigned_live_sensor_ids),
                "assigned_live_sensor_ids": assigned_live_sensor_ids,
                "live_sensor_metrics": live_sensor_metrics,
                "live_entity_keys": [
                    key for key in entities
                    if key in {
                        "session_status", "session_duration", "current_heart_rate",
                        "current_power", "current_cadence", "current_speed",
                        "current_distance", "current_altitude",
                        "heart_rate_percent_max", "heart_rate_reserve_percent",
                        "heart_rate_intensity", "heart_rate_relative_threshold",
                        "current_power_to_weight", "power_relative_threshold",
                        "current_pace", "speed_relative_threshold",
                        "live_average_heart_rate", "live_maximum_heart_rate",
                        "live_average_power", "live_maximum_power",
                        "live_average_cadence", "live_average_speed",
                        "live_banister_trimp", "live_mechanical_work",
                        "live_aerobic_efficiency", "live_aerobic_decoupling",
                        "live_time_moderate", "live_time_vigorous",
                        "live_time_near_maximal", "start_workout",
                        "pause_workout", "resume_workout", "stop_workout",
                    }
                ],
                "latest_workout": {
                    "available": latest_workout is not None,
                    "sport": workout_sport_kind(latest_workout),
                    "name": latest_workout.name if latest_workout is not None else None,
                    "fitness_owned": workout_is_fitness_owned(latest_workout),
                },
                "workout_source_metrics": workout_source_metrics,
                "sleep_source_metrics": sleep_source_metrics,
                "evaluation_source_metrics": evaluation_source_metrics,
                "tv_dashboard": {
                    "enabled": bool(manager.config.get(CONF_TV_DASHBOARD_ENABLED, False)),
                    "ytdlp_enabled": bool(manager.config.get(CONF_TV_YTDLP_ENABLED, False)),
                    "cast_media_player_id": str(manager.config.get(CONF_TV_MEDIA_PLAYER_ID) or "") or None,
                    "cast_active": get_tv_dashboard_hub(hass).is_cast_active(entry.entry_id),
                    "local_cast_active": get_tv_dashboard_hub(hass).is_local_cast_active(entry.entry_id),
                    "cast_target": get_tv_dashboard_hub(hass).cast_target(entry.entry_id),
                    "ducking_percent": max(
                        0,
                        min(
                            100,
                            int(manager.config.get(CONF_TV_DUCKING_PERCENT, DEFAULT_TV_DUCKING_PERCENT)),
                        ),
                    ),
                    "ignore_lights_when_cast_active": bool(
                        manager.config.get(
                            CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                            DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                        )
                    ),
                    "tv_scale_percent": int(
                        tv_preferences.get("tv_scale_percent", DEFAULT_TV_SCALE_PERCENT)
                    ),
                    "oled_protection": bool(
                        tv_preferences.get("oled_protection", DEFAULT_TV_OLED_PROTECTION)
                    ),
                    "animations_enabled": bool(tv_preferences.get("animations_enabled", True)),
                    "light_feedback_enabled": bool(tv_preferences.get("light_feedback_enabled", True)),
                    "tts_announcements_enabled": bool(tv_preferences.get("tts_announcements_enabled", True)),
                    "music_search_limit": int(tv_preferences.get("music_search_limit", 50)),
                    "last_media": dict(tv_preferences.get("last_media") or {}),
                    "audio_output_id": str(tv_preferences.get("audio_output_id") or "__fitness_browser__"),
                },
                "route_candidates": _route_candidates(hass, manager),
            }
        )
    connection.send_result(
        msg["id"],
        {
            "frontend_version": "unreleased-85",
            "profiles": profiles,
            "access": access,
            # Access-denied and administrator overview screens can render
            # before a profile exists.  Give them the same account-language
            # catalog instead of falling back to Home Assistant's UI language.
            "labels": {
                **_DASHBOARD_TEXT[
                    str(access.get("language") or "en")
                    if str(access.get("language") or "en") in _DASHBOARD_TEXT
                    else "en"
                ],
                "pace": _PACE_TEXT[
                    str(access.get("language") or "en")
                    if str(access.get("language") or "en") in _PACE_TEXT
                    else "en"
                ],
            },
            "labels_by_language": {
                code: {**labels, "pace": _PACE_TEXT[code]}
                for code, labels in _DASHBOARD_TEXT.items()
            },
            "cast_targets": _tv_cast_targets(hass, registry) if access.get("is_admin") else [],
            "overview_cast": _tv_overview_cast_descriptor(hass) if access.get("is_admin") else {"active": False, "target": None},
            "audio_outputs": _fitness_audio_outputs(hass, registry),
            "intensity_colors": {
                key: list(rgb)
                for key, rgb in INTENSITY_RGB.items()
                if key in {"very_light", "light", "moderate", "vigorous", "near_maximal"}
            },
        },
    )


def _tv_dashboard_profile_entries(hass: HomeAssistant) -> list[Any]:
    """Return person/profile Fitness entries, excluding the shared sensors hub."""
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get("entry_type") != "live_hub"
    ]


def _tv_dashboard_enabled_entries(hass: HomeAssistant) -> list[Any]:
    """Return profile entries that opted into the Fitness TV dashboard."""
    result = []
    for entry in _tv_dashboard_profile_entries(hass):
        config = {**entry.data, **entry.options}
        if config.get(CONF_TV_DASHBOARD_ENABLED):
            result.append(entry)
    return result


def _tv_dashboard_view_card(
    profile_entry_id: str | None = None,
    *,
    setup: bool = False,
    profile_wrapper: bool = False,
) -> dict[str, object]:
    """Return one managed Fitness TV setup/profile card."""
    # Keep the stored Cast view deliberately conservative. Home Assistant Cast
    # can render custom cards, but its receiver may not support newer Lovelace
    # layout metadata at the same time as the normal HA frontend. The card
    # itself takes over the Cast viewport, so no grid/sections hints are needed.
    card: dict[str, object] = {
        "type": (
            _TV_SETUP_CARD_TYPE
            if setup or profile_wrapper
            else _TV_DASHBOARD_CARD_TYPE
        ),
    }
    if profile_entry_id:
        card["profile_entry_id"] = profile_entry_id
    return card


def _tv_dashboard_view(
    *,
    title: str,
    path: str,
    profile_entry_id: str | None = None,
    subview: bool = False,
    panel: bool = False,
    setup: bool = False,
    profile_wrapper: bool = False,
) -> dict[str, object]:
    """Build an explicit Cast-compatible Lovelace view.

    Home Assistant Cast resolves ``view_path`` from the stored Lovelace views.
    Custom dashboard strategies work in the normal frontend, but their generated
    paths are not present in the stored dashboard config that the Cast receiver
    searches.  Keep these views explicit and avoid panel mode, which Home
    Assistant Cast documents as unsupported for a single-card view.
    """
    # Use the classic Lovelace masonry shape for Cast compatibility. Do not use
    # panel mode (unsupported by HA Cast for a single-card view) and do not use
    # the newer Sections layout here: the Cast receiver can lag behind the main
    # HA frontend and otherwise renders a generic "Configuration error".
    view: dict[str, object] = {
        "title": title,
        "path": path,
        "cards": [
            _tv_dashboard_view_card(
                profile_entry_id,
                setup=setup,
                profile_wrapper=profile_wrapper,
            )
        ],
    }
    if panel:
        # The browser-only main view can safely use panel mode so the Fitness
        # shell receives the full Lovelace content width. Cast always targets
        # the explicit profile subviews below, which intentionally remain
        # non-panel for Home Assistant Cast compatibility.
        view["panel"] = True
    if subview:
        view["subview"] = True
        view["back_path"] = f"/{TV_DASHBOARD_PATH}/main"
    return view


def _tv_dashboard_expected_config(hass: HomeAssistant) -> dict[str, object]:
    """Build the server-side Fitness TV Lovelace config used by browsers and Cast."""
    entries = _tv_dashboard_enabled_entries(hass)
    views: list[dict[str, object]] = [
        _tv_dashboard_view(
            title="Fitness TV", path="main", panel=True, setup=True
        ),
        _tv_dashboard_view(
            title="Fitness TV Overview Cast", path="cast-overview", subview=True, setup=True
        ),
    ]
    for entry in entries:
        # The normal HA profile page is a full-width panel so the Fitness TV
        # shell owns the complete Lovelace content area. Home Assistant Cast
        # cannot render a single-card panel view, therefore every profile also
        # gets a separate hidden/non-panel Cast view targeting the same profile.
        views.append(
            _tv_dashboard_view(
                title=_profile_name(entry),
                path=f"profile-{entry.entry_id}",
                profile_entry_id=entry.entry_id,
                subview=True,
                panel=True,
                profile_wrapper=True,
            )
        )
        views.append(
            _tv_dashboard_view(
                title=f"{_profile_name(entry)} Cast",
                path=f"cast-{entry.entry_id}",
                profile_entry_id=entry.entry_id,
                subview=True,
            )
        )
    return {"title": "Fitness TV", "views": views}


def _is_managed_tv_dashboard_config(config: object) -> bool:
    """Return whether an existing Lovelace config belongs to Fitness TV."""
    if not isinstance(config, dict):
        return False

    # Migrate both unreleased strategy prototypes automatically.
    strategy_type = config.get("strategy", {}).get("type") if isinstance(config.get("strategy"), dict) else None
    if strategy_type in {"custom:fitness-tv", "fitness-tv"}:
        return True

    views = config.get("views")
    if not isinstance(views, list) or not views:
        return False

    found_main = False
    for view in views:
        if not isinstance(view, dict):
            return False
        path = str(view.get("path") or "")
        if path == "main":
            found_main = True
        elif path != "cast-overview" and not (path.startswith("profile-") or path.startswith("cast-")):
            return False

        cards: list[object] = []
        direct_cards = view.get("cards")
        if isinstance(direct_cards, list):
            cards.extend(direct_cards)
        sections = view.get("sections")
        if isinstance(sections, list):
            for section in sections:
                if isinstance(section, dict) and isinstance(section.get("cards"), list):
                    cards.extend(section["cards"])
        if len(cards) != 1:
            return False
        card = cards[0]
        if not isinstance(card, dict):
            return False
        # Accept all Fitness-owned historical TV card names. Release-specific
        # custom-element names deliberately change to bypass Home Assistant's
        # long-lived customElements registry, so the stored Lovelace dashboard
        # from the previous release must still be recognized and migrated.
        card_type = str(card.get("type") or "")
        is_setup_type = (
            card_type == "custom:fitness-tv-setup-card"
            or re.fullmatch(r"custom:fitness-tv-setup-card-v\d+", card_type) is not None
        )
        is_dashboard_type = (
            card_type == "custom:fitness-tv-dashboard-card"
            or re.fullmatch(r"custom:fitness-tv-dashboard-card-v\d+", card_type) is not None
        )
        # Browser profile views use the setup-card Lovelace wrapper and mount
        # the dashboard card internally. Older releases used a direct dashboard
        # card there, so both remain valid migration inputs. Cast views only use
        # dashboard cards.
        if path in {"main", "cast-overview"} or path.startswith("profile-"):
            if not (is_setup_type or is_dashboard_type):
                return False
        elif not is_dashboard_type:
            return False
    return found_main


async def async_ensure_tv_dashboard(hass: HomeAssistant) -> bool:
    """Ensure the explicit storage Lovelace dashboard used by HA Cast exists."""
    if not _tv_dashboard_profile_entries(hass):
        return False

    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        return False

    expected_config = _tv_dashboard_expected_config(hass)

    collection = lovelace_dashboard.DashboardsCollection(hass)
    await collection.async_load()
    item = next(
        (
            candidate
            for candidate in collection.async_items()
            if candidate.get(CONF_URL_PATH) == TV_DASHBOARD_PATH
        ),
        None,
    )

    existing_store = lovelace_data.dashboards.get(TV_DASHBOARD_PATH)
    store = existing_store
    if store is None and item is not None:
        store = lovelace_dashboard.LovelaceStorage(hass, item)

    # Never overwrite unrelated user content that happens to use /fitness-tv.
    if store is not None:
        try:
            current = await store.async_load(False)
        except Exception:  # noqa: BLE001 - empty/new storage dashboard
            current = None
        if current is not None and not _is_managed_tv_dashboard_config(current):
            _LOGGER.warning(
                "Cannot use /%s for Fitness TV because that Lovelace dashboard already has user content",
                TV_DASHBOARD_PATH,
            )
            return False

    if item is None:
        item = await collection.async_create_item(
            {
                CONF_ICON: "mdi:television-play",
                CONF_TITLE: "Fitness TV",
                CONF_URL_PATH: TV_DASHBOARD_PATH,
                CONF_SHOW_IN_SIDEBAR: True,
                CONF_REQUIRE_ADMIN: False,
            }
        )
    else:
        update = {}
        if item.get(CONF_ICON) != "mdi:television-play":
            update[CONF_ICON] = "mdi:television-play"
        if item.get(CONF_SHOW_IN_SIDEBAR) is not True:
            update[CONF_SHOW_IN_SIDEBAR] = True
        if not item.get(CONF_TITLE):
            update[CONF_TITLE] = "Fitness TV"
        if update:
            await collection.async_update_item(item["id"], update)
            item = {**item, **update}

    if store is None:
        store = lovelace_dashboard.LovelaceStorage(hass, item)
    else:
        # Our collection instance does not own Lovelace's runtime listener, so
        # mirror metadata updates into the already-registered storage object.
        store.config = item
    lovelace_data.dashboards[TV_DASHBOARD_PATH] = store

    try:
        current = await store.async_load(False)
    except Exception:  # noqa: BLE001 - empty/new storage dashboard
        current = None
    if current != expected_config:
        await store.async_save(expected_config)

    try:
        frontend.async_register_built_in_panel(
            hass,
            "lovelace",
            frontend_url_path=TV_DASHBOARD_PATH,
            require_admin=bool(item.get(CONF_REQUIRE_ADMIN, False)),
            show_in_sidebar=True,
            sidebar_title=str(item.get(CONF_TITLE) or "Fitness TV"),
            sidebar_icon="mdi:television-play",
            config={"mode": MODE_STORAGE},
            update=frontend.async_panel_exists(hass, TV_DASHBOARD_PATH),
        )
    except ValueError:
        _LOGGER.warning("Unable to register/update the Fitness TV sidebar panel")

    _LOGGER.info(
        "Fitness TV dashboard ready at /%s with %d explicit Cast-compatible views",
        TV_DASHBOARD_PATH,
        len(expected_config["views"]),
    )
    return True


async def _async_wake_cast_target(
    hass: HomeAssistant,
    media_player: str,
    *,
    timeout: float = 8.0,
) -> bool:
    """Best-effort wake of a powered-off Cast display before launching Lovelace.

    Home Assistant's Cast media player implements ``turn_on`` by launching a
    Cast receiver.  On HDMI/CEC-capable TVs that is also the reliable wake
    signal.  We still continue to ``cast.show_lovelace_view`` if the wake call
    fails because some Cast targets can be reached directly while their HA
    state is temporarily stale.
    """
    state = hass.states.get(media_player)
    if state is not None and state.state not in {"off", "standby", "unknown", "unavailable"}:
        return True
    if not hass.services.has_service("media_player", "turn_on"):
        return False

    _LOGGER.info("Waking Fitness TV Cast target %s before dashboard launch", media_player)
    try:
        await async_call_service(
            hass,
            "media_player",
            "turn_on",
            {"entity_id": media_player},
            blocking=True,
            timeout=10.0,
        )
    except Exception as err:  # noqa: BLE001 - off/unavailable Cast targets can race discovery
        _LOGGER.info("Fitness TV wake request for %s did not complete: %s", media_player, err)
        return False

    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, timeout)
    while loop.time() < deadline:
        state = hass.states.get(media_player)
        if state is not None and state.state not in {"off", "standby", "unknown", "unavailable"}:
            return True
        await asyncio.sleep(0.35)
    return False


async def _async_wait_for_cast_receiver_exit(
    hass: HomeAssistant,
    media_player: str,
    *,
    timeout: float = 5.0,
) -> bool:
    """Wait until the Home Assistant Lovelace Cast application has exited."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        state = hass.states.get(media_player)
        app_id = str(state.attributes.get("app_id") or "") if state is not None else ""
        if app_id != CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            return True
        await asyncio.sleep(0.25)
    return False


async def _async_stop_existing_ha_cast_receiver(
    hass: HomeAssistant,
    media_player: str,
    *,
    force: bool = False,
) -> bool:
    """Quit a stale Home Assistant Lovelace receiver without powering off the TV.

    The Cast media-player implementation maps ``turn_off`` to ``quit_app``.
    We only issue it automatically when the active Cast app is Home Assistant,
    so Fitness never deliberately kills an unrelated Cast application.
    """
    state = hass.states.get(media_player)
    app_id = str(state.attributes.get("app_id") or "") if state is not None else ""
    if not force and app_id != CAST_APP_ID_HOMEASSISTANT_LOVELACE:
        return True
    if force and app_id and app_id != CAST_APP_ID_HOMEASSISTANT_LOVELACE:
        _LOGGER.info(
            "Fitness TV stop ignored on %s because active Cast app is %s",
            media_player, app_id,
        )
        return True
    if not app_id:
        return True
    if not hass.services.has_service("media_player", "turn_off"):
        _LOGGER.warning("media_player.turn_off is unavailable; cannot reset %s", media_player)
        return False

    _LOGGER.info("Stopping existing Home Assistant Cast receiver on %s", media_player)
    try:
        await async_call_service(
            hass,
            "media_player",
            "turn_off",
            {"entity_id": media_player},
            blocking=True,
            timeout=10.0,
        )
    except Exception as err:  # noqa: BLE001 - transient Cast disconnects are expected
        _LOGGER.warning("Unable to stop existing Cast receiver on %s: %s", media_player, err)
        return False

    stopped = await _async_wait_for_cast_receiver_exit(hass, media_player)
    if not stopped:
        _LOGGER.warning("Home Assistant Cast receiver did not exit on %s", media_player)
    return stopped


async def async_stop_tv_dashboard(
    hass: HomeAssistant,
    entry,
    media_player_override: str | None = None,
) -> bool:
    """Stop the Fitness/Home Assistant Cast receiver while leaving the TV on."""
    config = {**entry.data, **entry.options}
    hub = get_tv_dashboard_hub(hass)
    active_target = str(hub.cast_target(entry.entry_id) or "").strip()
    media_player = str(
        active_target or media_player_override or config.get(CONF_TV_MEDIA_PLAYER_ID) or ""
    ).strip()
    if not media_player:
        return False

    registry = er.async_get(hass)
    registry_entry = registry.async_get(media_player)
    if (
        registry_entry is None
        or registry_entry.platform != "cast"
        or not media_player.startswith("media_player.")
        or registry_entry.disabled_by is not None
    ):
        _LOGGER.warning("Fitness TV target %s is not an enabled Google Cast entity", media_player)
        return False

    # Stop Fitness logically first. The TV may already be powered off and the
    # Cast entity can retain a stale Lovelace app_id; a failed quit_app must not
    # leave Fitness believing that it is still casting or still playing music.
    if hub.cast_target(entry.entry_id) == media_player:
        await hub.async_mark_cast_inactive(
            entry.entry_id, reason="manual_cast_stop"
        )
    else:
        await hub.async_broadcast_media_state(
            entry.entry_id, {"playing": False, "error": False}
        )

    stopped = await _async_stop_existing_ha_cast_receiver(
        hass, media_player, force=True,
    )
    if not stopped:
        _LOGGER.warning(
            "Fitness TV logical Cast session was stopped, but the receiver on %s could not be quit",
            media_player,
        )
    # The requested Fitness session is stopped even when an already-off or
    # unreachable display cannot acknowledge quit_app.
    return True


async def _async_cast_receiver_is_stable(
    hass: HomeAssistant,
    media_player: str,
    *,
    timeout: float = 8.0,
    stable_for: float = 3.0,
) -> bool:
    """Confirm that the Home Assistant Lovelace Cast receiver stays active."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    stable_since: float | None = None
    while loop.time() < deadline:
        state = hass.states.get(media_player)
        app_id = str(state.attributes.get("app_id") or "") if state is not None else ""
        if app_id == CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            if stable_since is None:
                stable_since = loop.time()
            if loop.time() - stable_since >= stable_for:
                return True
        else:
            stable_since = None
        await asyncio.sleep(0.4)
    return False


async def _async_wait_for_cast_receiver_launch(
    hass: HomeAssistant,
    media_player: str,
    *,
    timeout: float = 8.0,
) -> bool:
    """Return as soon as the Home Assistant Cast receiver has launched once.

    Do not continuously tear down/relaunch a receiver that has already started.
    If the Lovelace view itself has a frontend/configuration problem, restarting
    the Cast application cannot repair it and only causes the visible
    Not Connected -> Connected -> restart loop on Android/Google TV.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        state = hass.states.get(media_player)
        app_id = str(state.attributes.get("app_id") or "") if state is not None else ""
        if app_id == CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            return True
        await asyncio.sleep(0.35)
    return False


async def async_cast_tv_dashboard(
    hass: HomeAssistant,
    entry,
    media_player_override: str | None = None,
) -> bool:
    """Show and verify the full-screen Fitness TV dashboard on a Cast display."""
    config = {**entry.data, **entry.options}
    if not config.get(CONF_TV_DASHBOARD_ENABLED):
        return False
    media_player = str(
        media_player_override or config.get(CONF_TV_MEDIA_PLAYER_ID) or ""
    ).strip()
    if not media_player:
        return False

    registry = er.async_get(hass)
    registry_entry = registry.async_get(media_player)
    if (
        registry_entry is None
        or registry_entry.platform != "cast"
        or not media_player.startswith("media_player.")
        or registry_entry.disabled_by is not None
    ):
        _LOGGER.warning("Fitness TV target %s is not an enabled Google Cast entity", media_player)
        return False

    state = hass.states.get(media_player)
    # A powered-off Cast display can legitimately be missing or temporarily
    # unavailable while Android/Google TV starts up. Do not reject the cast
    # request here: Home Assistant's cast.show_lovelace_view dispatch is what
    # gives the Cast integration the chance to launch/reconnect the receiver.
    if not await async_ensure_tv_dashboard(hass):
        return False
    if not hass.services.has_service("cast", "show_lovelace_view"):
        return False

    cast_data = {
        "entity_id": media_player,
        "dashboard_path": TV_DASHBOARD_PATH,
        "view_path": f"cast-{entry.entry_id}",
    }
    started_off = state is None or state.state in {"off", "standby", "unknown", "unavailable"}
    hub = get_tv_dashboard_hub(hass)
    await hub.async_load()
    # Claim this profile's Cast launch before any wake/cooldown awaits. A newer
    # target selection increments the generation and immediately makes this
    # coroutine stale, so its later retry/failure path cannot affect that newer
    # receiver.
    cast_generation = hub.expect_cast(entry.entry_id, media_player)
    if started_off:
        # A powered-off TV must never leave the laptop showing a phantom
        # "playing" state. Preserve only the persistent station selection.
        await hub.async_broadcast_media_state(
            entry.entry_id, {"playing": False, "error": False}
        )
        wake_started = asyncio.get_running_loop().time()
        await _async_wake_cast_target(hass, media_player)
        # Android/Google TV often needs a few seconds after power-on before a
        # Cast receiver can stay in the foreground. Keep a minimum ~10 second
        # wake-to-cast cooldown instead of launching Lovelace immediately.
        remaining = 10.0 - (asyncio.get_running_loop().time() - wake_started)
        if remaining > 0:
            await asyncio.sleep(remaining)
        if not hub.cast_attempt_is_current(
            entry.entry_id, media_player, cast_generation
        ):
            _LOGGER.info(
                "Fitness TV Cast attempt to %s superseded during wake/cooldown",
                media_player,
            )
            return False

    # Restore the last stable media_source selection across TV power cycles and
    # Home Assistant restarts. This restores selection only; normal Cast does
    # not claim that music is already playing.
    await hub.async_restore_last_media(entry.entry_id)

    # The launch was already bound before wake/cooldown. Give a currently-owned
    # attempt a tiny handoff barrier before dispatching the receiver.
    if not hub.cast_attempt_is_current(
        entry.entry_id, media_player, cast_generation
    ):
        return False
    await asyncio.sleep(0.20)
    if not hub.cast_attempt_is_current(
        entry.entry_id, media_player, cast_generation
    ):
        return False

    _LOGGER.info(
        "Fitness TV cast requested for profile %s to %s (state=%s)",
        entry.entry_id,
        media_player,
        state.state if state is not None else "missing",
    )

    # Android/Google TV can let a startup app steal the foreground after the
    # first Cast launch. Re-cast after that race instead of reporting success.
    for attempt in range(1, 4):
        if not hub.cast_attempt_is_current(
            entry.entry_id, media_player, cast_generation
        ):
            _LOGGER.info(
                "Fitness TV Cast attempt to %s superseded before retry %d",
                media_player, attempt,
            )
            return False
        _LOGGER.debug(
            "Casting Fitness TV profile %s to %s (attempt %d/3)",
            entry.entry_id, media_player, attempt,
        )

        # A Lovelace Cast receiver can remain alive in the background on
        # Android/Google TV and then ignore a new view request. Always quit a
        # previous Home Assistant receiver first and launch a fresh one. This
        # is transparent to the user and does not power off the television.
        current = hass.states.get(media_player)
        current_app_id = (
            str(current.attributes.get("app_id") or "") if current is not None else ""
        )
        if current_app_id == CAST_APP_ID_HOMEASSISTANT_LOVELACE:
            reset_ok = await _async_stop_existing_ha_cast_receiver(hass, media_player)
            if reset_ok:
                await asyncio.sleep(0.6)
            else:
                _LOGGER.warning(
                    "Continuing Fitness TV cast after receiver reset failed on %s",
                    media_player,
                )
            if not hub.cast_attempt_is_current(
                entry.entry_id, media_player, cast_generation
            ):
                return False

        # The Cast runtime can reuse the same receiver browser/client ID after
        # a quit/relaunch. Arm this attempt so that reused fresh heartbeats are
        # accepted instead of being mistaken for the stale pre-reset receiver.
        if not hub.cast_attempt_is_current(
            entry.entry_id, media_player, cast_generation
        ):
            return False
        hub.arm_cast_receiver(entry.entry_id)
        try:
            # Formerly: "cast", "show_lovelace_view", cast_data, blocking=True.
            # The shared wrapper now adds a hard deadline to that same action.
            await async_call_service(
                hass,
                "cast",
                "show_lovelace_view",
                cast_data,
                blocking=True,
                timeout=30.0,
            )
        except Exception as err:  # noqa: BLE001 - retry transient Cast startup failures
            _LOGGER.warning(
                "Fitness TV cast attempt %d/3 to %s failed: %s",
                attempt,
                media_player,
                err,
            )
            if not hub.cast_attempt_is_current(
                entry.entry_id, media_player, cast_generation
            ):
                return False
            if attempt < 3:
                await asyncio.sleep(5.0 if started_off and attempt == 1 else 2.0)
                if not hub.cast_attempt_is_current(
                    entry.entry_id, media_player, cast_generation
                ):
                    return False
            continue
        if not hub.cast_attempt_is_current(
            entry.entry_id, media_player, cast_generation
        ):
            return False
        if await _async_wait_for_cast_receiver_launch(
            hass, media_player, timeout=10.0 if started_off and attempt == 1 else 8.0,
        ):
            if not hub.cast_attempt_is_current(
                entry.entry_id, media_player, cast_generation
            ):
                return False
            # app_id alone is not enough: Android/Google TV may leave a stale
            # Home Assistant Cast app_id behind after the display powers off.
            # Confirm that the fresh Fitness receiver page itself is alive and
            # still belongs to this exact launch generation.
            cast_client = await hub.async_wait_cast_active(
                entry.entry_id,
                timeout=10.0 if started_off and attempt == 1 else 8.0,
                media_player=media_player,
                generation=cast_generation,
            )
            if cast_client is not None:
                _LOGGER.info(
                    "Fitness TV Cast receiver active on %s for profile %s (%s)",
                    media_player, entry.entry_id, cast_client,
                )
                return True
            _LOGGER.warning(
                "Fitness TV Cast app launched on %s but no live Fitness receiver heartbeat arrived",
                media_player,
            )
        if attempt < 3:
            await asyncio.sleep(5.0 if started_off and attempt == 1 else 2.0)
            if not hub.cast_attempt_is_current(
                entry.entry_id, media_player, cast_generation
            ):
                return False

    if not hub.cast_attempt_is_current(
        entry.entry_id, media_player, cast_generation
    ):
        return False
    final_state = hass.states.get(media_player)
    _LOGGER.warning(
        "Fitness TV Cast receiver did not remain active on %s (state=%s, app_id=%s)",
        media_player,
        final_state.state if final_state is not None else "missing",
        final_state.attributes.get("app_id") if final_state is not None else None,
    )
    await hub.async_mark_cast_inactive(
        entry.entry_id,
        reason="cast_launch_failed",
        media_player=media_player,
        generation=cast_generation,
    )
    return False


async def _async_register_resource(hass: HomeAssistant) -> None:
    """Register the bundled dashboard module in Lovelace storage mode.

    The resource collection is explicitly loaded before inspection/creation to
    avoid the historic lazy-load race that could overwrite existing resources.
    YAML resource mode is left untouched and logged with manual instructions.
    """
    lovelace_data = hass.data.get("lovelace")
    resources = getattr(lovelace_data, "resources", None) if lovelace_data is not None else None
    if resources is None or not hasattr(resources, "store") or resources.store is None:
        _LOGGER.info(
            "Fitness dashboard resource not auto-registered (Lovelace resource storage unavailable). "
            "Add %s as a JavaScript module resource manually.",
            _RESOURCE_URL,
        )
        return
    if not resources.loaded:
        await resources.async_load()
    matches = [
        item
        for item in resources.async_items()
        if str(item.get("url", "")).startswith(
            (_RESOURCE_PREFIX, _LEGACY_RESOURCE_NAMESPACE, _LEGACY_CAST_RESOURCE_NAMESPACE)
        )
    ]

    if matches:
        primary = matches[0]
        update = {}
        if primary.get("url") != _RESOURCE_URL:
            update["url"] = _RESOURCE_URL
        if primary.get("type") != "module" and primary.get("res_type") != "module":
            update["res_type"] = "module"
        if update:
            await resources.async_update_item(primary["id"], update)

        # Old dashboard iterations could leave duplicate resources behind. Two
        # copies are confusing to HA's module loader and can result in the file
        # being fetched without the custom elements being available when the
        # card picker opens. Keep one canonical module only.
        for duplicate in matches[1:]:
            await resources.async_delete_item(duplicate["id"])

        _LOGGER.info(
            "Reconciled Fitness dashboard resource id=%s type=module url=%s; removed=%s duplicate(s)",
            primary["id"],
            _RESOURCE_URL,
            max(0, len(matches) - 1),
        )
        return

    created = await resources.async_create_item(
        {"res_type": "module", "url": _RESOURCE_URL}
    )
    _LOGGER.info(
        "Registered Fitness community dashboard resource id=%s type=module url=%s",
        created.get("id") if isinstance(created, dict) else created,
        _RESOURCE_URL,
    )


def _schedule_dashboard_reconcile(hass: HomeAssistant) -> None:
    """Debounce optional Lovelace storage work outside profile request paths."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    task = domain_data.get(_RECONCILE_TASK_KEY)
    if isinstance(task, asyncio.Task) and not task.done():
        return

    async def _reconcile() -> None:
        await asyncio.sleep(0)
        try:
            await _async_register_resource(hass)
            await async_ensure_tv_dashboard(hass)
        except Exception:  # noqa: BLE001 - Fitness itself does not require Lovelace
            _LOGGER.exception("Unable to reconcile the Fitness TV dashboard")

    task = hass.async_create_background_task(
        _reconcile(),
        "fitness reconcile TV dashboard",
        eager_start=False,
    )
    domain_data[_RECONCILE_TASK_KEY] = task

    def _clear(completed: asyncio.Task) -> None:
        if domain_data.get(_RECONCILE_TASK_KEY) is completed:
            domain_data.pop(_RECONCILE_TASK_KEY, None)

    task.add_done_callback(_clear)


async def async_setup_dashboard(hass: HomeAssistant) -> None:
    """Serve/register the Fitness dashboard strategy once per HA process."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_SETUP_KEY):
        if hass.data.get(LOVELACE_DATA) is not None:
            # This replaces serial ``await _async_register_resource(hass)`` and
            # ``await async_ensure_tv_dashboard(hass)`` work for every profile.
            _schedule_dashboard_reconcile(hass)
        return
    domain_data[_SETUP_KEY] = True

    frontend_path = Path(__file__).parent / "frontend"
    websocket_api.async_register_command(hass, websocket_dashboard_config)
    websocket_api.async_register_command(hass, websocket_workouts_list)
    websocket_api.async_register_command(hass, websocket_workouts_delete)
    websocket_api.async_register_command(hass, websocket_workouts_empty)
    websocket_api.async_register_command(hass, websocket_body_composition)
    websocket_api.async_register_command(hass, websocket_weight_subscribe)
    websocket_api.async_register_command(hass, websocket_weight_admin_subscribe)
    websocket_api.async_register_command(hass, websocket_weight_confirm)
    websocket_api.async_register_command(hass, websocket_weight_dismiss)
    websocket_api.async_register_command(hass, websocket_tv_overview_cast)
    websocket_api.async_register_command(hass, websocket_tv_overview_stop)
    websocket_api.async_register_command(hass, websocket_dashboard_flow_translations)
    websocket_api.async_register_command(hass, websocket_dashboard_options_flow_start)
    websocket_api.async_register_command(hass, websocket_dashboard_options_flow_step)
    websocket_api.async_register_command(hass, websocket_dashboard_options_flow_cancel)
    async_register_fitness_access_websocket_commands(hass)
    async_register_tv_websocket_commands(hass)

    async def _http_ready(_hass: HomeAssistant, _component: str) -> None:
        try:
            # Register the exact CORS-capable module route before the broader
            # static directory route so Cast always receives the explicit
            # cross-origin headers required for custom Lovelace resources.
            _hass.http.register_view(
                FitnessDashboardResourceView(frontend_path / "fitness-dashboard.js")
            )
            await _hass.http.async_register_static_paths(
                [
                    StaticPathConfig("/fitness/frontend", str(frontend_path), False),
                    StaticPathConfig("/fitness/brand", str(Path(__file__).parent / "brand"), True),
                ]
            )
        except Exception:  # noqa: BLE001 - dashboard is optional UI enhancement
            _LOGGER.exception(
                "Unable to serve Fitness dashboard frontend; Fitness itself remains available"
            )

    async def _lovelace_ready(_hass: HomeAssistant, _component: str) -> None:
        try:
            await _async_register_resource(_hass)
            await async_ensure_tv_dashboard(_hass)
        except Exception:  # noqa: BLE001 - optional UI enhancement
            _LOGGER.exception(
                "Unable to auto-register Fitness dashboard resources; Fitness itself remains available"
            )

    # Frontend/dashboard support is optional. Register after the owning core
    # integrations are ready so headless Fitness setups still load normally.
    async_when_setup(hass, "http", _http_ready)
    async_when_setup(hass, "lovelace", _lovelace_ready)
