"""Frontend dashboard support for Fitness."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_when_setup

from .const import (
    CONF_LANGUAGE,
    CONF_PROFILE_NAME,
    CONF_WORKOUT_DEVICE_IDS,
    DOMAIN,
)
from .profile_data import (
    DATA_MAP_KIND_TO_KEY,
    LIVE_RAW_ROUTE_KEYS,
    routes_from_attributes,
)
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

_LOGGER = logging.getLogger(__name__)

_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"
_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=2026.8.11.14"
_SETUP_KEY = "_dashboard_frontend_setup"

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

_RECOVERY_REFINEMENT_TEXT: dict[str, dict[str, str]] = {
    "en": {"recovery_from_last_workout":"Time to recover from last workout","total_recovery":"Total recovery","at_time":"at","baseline":"Baseline","current":"Current","fitness_sleep_score":"Fitness sleep score"},
    "el": {"recovery_from_last_workout":"Χρόνος αποκατάστασης από την τελευταία προπόνηση","total_recovery":"Πλήρης αποκατάσταση","at_time":"στις","baseline":"Βάση","current":"Τώρα","fitness_sleep_score":"Βαθμολογία ύπνου Fitness"},
    "de": {"recovery_from_last_workout":"Erholungszeit nach dem letzten Training","total_recovery":"Vollständig erholt","at_time":"um","baseline":"Basis","current":"Aktuell","fitness_sleep_score":"Fitness-Schlafscore"},
    "fr": {"recovery_from_last_workout":"Temps de récupération après le dernier entraînement","total_recovery":"Récupération complète","at_time":"à","baseline":"Référence","current":"Actuel","fitness_sleep_score":"Score de sommeil Fitness"},
    "es": {"recovery_from_last_workout":"Tiempo de recuperación del último entrenamiento","total_recovery":"Recuperación completa","at_time":"a las","baseline":"Referencia","current":"Actual","fitness_sleep_score":"Puntuación de sueño Fitness"},
    "it": {"recovery_from_last_workout":"Tempo di recupero dall'ultimo allenamento","total_recovery":"Recupero completo","at_time":"alle","baseline":"Baseline","current":"Attuale","fitness_sleep_score":"Punteggio sonno Fitness"},
    "pt": {"recovery_from_last_workout":"Tempo de recuperação do último treino","total_recovery":"Recuperação total","at_time":"às","baseline":"Referência","current":"Atual","fitness_sleep_score":"Pontuação de sono Fitness"},
    "nl": {"recovery_from_last_workout":"Hersteltijd van de laatste training","total_recovery":"Volledig hersteld","at_time":"om","baseline":"Basislijn","current":"Huidig","fitness_sleep_score":"Fitness-slaapscore"},
    "pl": {"recovery_from_last_workout":"Czas regeneracji po ostatnim treningu","total_recovery":"Pełna regeneracja","at_time":"o","baseline":"Poziom bazowy","current":"Aktualnie","fitness_sleep_score":"Wynik snu Fitness"},
    "ru": {"recovery_from_last_workout":"Время восстановления после последней тренировки","total_recovery":"Полное восстановление","at_time":"в","baseline":"Базовый уровень","current":"Сейчас","fitness_sleep_score":"Оценка сна Fitness"},
    "uk": {"recovery_from_last_workout":"Час відновлення після останнього тренування","total_recovery":"Повне відновлення","at_time":"о","baseline":"Базовий рівень","current":"Зараз","fitness_sleep_score":"Оцінка сну Fitness"},
    "tr": {"recovery_from_last_workout":"Son antrenmandan toparlanma süresi","total_recovery":"Tam toparlanma","at_time":"saat","baseline":"Baz","current":"Güncel","fitness_sleep_score":"Fitness uyku puanı"},
    "zh": {"recovery_from_last_workout":"上次训练后的恢复时间","total_recovery":"完全恢复","at_time":"于","baseline":"基线","current":"当前","fitness_sleep_score":"Fitness 睡眠评分"},
    "ja": {"recovery_from_last_workout":"前回ワークアウトからの回復時間","total_recovery":"完全回復","at_time":"","baseline":"ベースライン","current":"現在","fitness_sleep_score":"Fitness 睡眠スコア"},
    "ko": {"recovery_from_last_workout":"마지막 운동 후 회복 시간","total_recovery":"완전 회복","at_time":"","baseline":"기준선","current":"현재","fitness_sleep_score":"Fitness 수면 점수"},
}
for _code, _labels in _RECOVERY_REFINEMENT_TEXT.items():
    _DASHBOARD_TEXT.setdefault(_code, {}).update(_labels)

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


def _route_candidates(hass: HomeAssistant, manager) -> list[dict[str, str]]:
    """Return route data only when it belongs to the current merged workout."""
    selected = set(manager.config.get(CONF_WORKOUT_DEVICE_IDS) or [])
    latest = manager.latest_workout()
    if not selected or latest is None:
        return []
    registry = er.async_get(hass)
    result: list[dict[str, str]] = []
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


@websocket_api.websocket_command({vol.Required("type"): "fitness/dashboard/config"})
@websocket_api.async_response
async def websocket_dashboard_config(hass: HomeAssistant, connection, msg) -> None:
    """Return dashboard-safe profile metadata and entity mappings."""
    registry = er.async_get(hass)
    profiles: list[dict[str, Any]] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if manager is None:
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

        profiles.append(
            {
                "entry_id": entry.entry_id,
                "profile_name": _profile_name(entry),
                "language": lang,
                "labels": {**_DASHBOARD_TEXT[lang], "pace": _PACE_TEXT.get(lang, "Pace")},
                "labels_by_language": {
                    code: {**labels, "pace": _PACE_TEXT.get(code, _PACE_TEXT.get("en", "Pace"))}
                    for code, labels in _DASHBOARD_TEXT.items()
                },
                "entities": entities,
                "data_entities": data_entities,
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
                "route_candidates": _route_candidates(hass, manager),
            }
        )
    connection.send_result(msg["id"], {"profiles": profiles})


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
        if str(item.get("url", "")).startswith(_RESOURCE_NAMESPACE)
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


async def async_setup_dashboard(hass: HomeAssistant) -> None:
    """Serve/register the Fitness dashboard strategy once per HA process."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_SETUP_KEY):
        return
    domain_data[_SETUP_KEY] = True

    frontend_path = Path(__file__).parent / "frontend"
    websocket_api.async_register_command(hass, websocket_dashboard_config)

    async def _http_ready(_hass: HomeAssistant, _component: str) -> None:
        try:
            await _hass.http.async_register_static_paths(
                [StaticPathConfig("/fitness/frontend", str(frontend_path), False)]
            )
        except Exception:  # noqa: BLE001 - dashboard is optional UI enhancement
            _LOGGER.exception(
                "Unable to serve Fitness dashboard frontend; Fitness itself remains available"
            )

    async def _lovelace_ready(_hass: HomeAssistant, _component: str) -> None:
        try:
            await _async_register_resource(_hass)
        except Exception:  # noqa: BLE001 - optional UI enhancement
            _LOGGER.exception(
                "Unable to auto-register Fitness dashboard resource; Fitness itself remains available"
            )

    # Frontend/dashboard support is optional. Register after the owning core
    # integrations are ready so headless Fitness setups still load normally.
    async_when_setup(hass, "http", _http_ready)
    async_when_setup(hass, "lovelace", _lovelace_ready)
