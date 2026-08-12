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
from .providers.workouts import workout_sport_kind

_LOGGER = logging.getLogger(__name__)

_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"
_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=2026.8.4.15"
_SETUP_KEY = "_dashboard_frontend_setup"

_PACE_TEXT: dict[str, str] = {
    "en": "Pace", "el": "Ρυθμός", "de": "Tempo", "fr": "Allure",
    "es": "Ritmo", "it": "Passo", "pt": "Ritmo", "nl": "Tempo",
    "pl": "Tempo", "ru": "Темп", "uk": "Темп", "tr": "Tempo",
    "zh": "配速", "ja": "ペース", "ko": "페이스",
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
        "sleep_score": "Sleep score",
        "sleep_duration": "Sleep duration",
        "sleep_hrv": "Sleep HRV",
        "sleep_deficit": "7-day sleep deficit",
        "training_load_snapshot": "Training load",
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
        "sleep_score": "Βαθμολογία ύπνου",
        "sleep_duration": "Διάρκεια ύπνου",
        "sleep_hrv": "HRV ύπνου",
        "sleep_deficit": "Έλλειμμα ύπνου 7 ημερών",
        "training_load_snapshot": "Προπονητικό φορτίο",
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
        "sleep_score": "Schlafwert",
        "sleep_duration": "Schlafdauer",
        "sleep_hrv": "Schlaf-HRV",
        "sleep_deficit": "7-Tage-Schlafdefizit",
        "training_load_snapshot": "Trainingsbelastung",
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
        "sleep_score": "Score de sommeil",
        "sleep_duration": "Durée du sommeil",
        "sleep_hrv": "VFC du sommeil",
        "sleep_deficit": "Déficit de sommeil sur 7 jours",
        "training_load_snapshot": "Charge d’entraînement",
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
        "sleep_score": "Puntuación de sueño",
        "sleep_duration": "Duración del sueño",
        "sleep_hrv": "HRV del sueño",
        "sleep_deficit": "Déficit de sueño de 7 días",
        "training_load_snapshot": "Carga de entrenamiento",
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
        "sleep_score": "Punteggio sonno",
        "sleep_duration": "Durata sonno",
        "sleep_hrv": "HRV del sonno",
        "sleep_deficit": "Deficit sonno 7 giorni",
        "training_load_snapshot": "Carico di allenamento",
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
        "sleep_score": "Pontuação do sono",
        "sleep_duration": "Duração do sono",
        "sleep_hrv": "HRV do sono",
        "sleep_deficit": "Défice de sono de 7 dias",
        "training_load_snapshot": "Carga de treino",
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
        "sleep_score": "Slaapscore",
        "sleep_duration": "Slaapduur",
        "sleep_hrv": "Slaap-HRV",
        "sleep_deficit": "Slaaptekort 7 dagen",
        "training_load_snapshot": "Trainingsbelasting",
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
        "sleep_score": "Ocena snu",
        "sleep_duration": "Czas snu",
        "sleep_hrv": "HRV podczas snu",
        "sleep_deficit": "Deficyt snu 7 dni",
        "training_load_snapshot": "Obciążenie treningowe",
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
        "sleep_score": "Оценка сна",
        "sleep_duration": "Длительность сна",
        "sleep_hrv": "HRV сна",
        "sleep_deficit": "Дефицит сна за 7 дней",
        "training_load_snapshot": "Тренировочная нагрузка",
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
        "sleep_score": "Оцінка сну",
        "sleep_duration": "Тривалість сну",
        "sleep_hrv": "HRV сну",
        "sleep_deficit": "Дефіцит сну за 7 днів",
        "training_load_snapshot": "Тренувальне навантаження",
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
        "sleep_score": "Uyku puanı",
        "sleep_duration": "Uyku süresi",
        "sleep_hrv": "Uyku HRV",
        "sleep_deficit": "7 günlük uyku açığı",
        "training_load_snapshot": "Antrenman yükü",
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
        "sleep_score": "睡眠评分",
        "sleep_duration": "睡眠时长",
        "sleep_hrv": "睡眠 HRV",
        "sleep_deficit": "7 天睡眠不足",
        "training_load_snapshot": "训练负荷",
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
        "sleep_score": "睡眠スコア",
        "sleep_duration": "睡眠時間",
        "sleep_hrv": "睡眠 HRV",
        "sleep_deficit": "7日間の睡眠不足",
        "training_load_snapshot": "トレーニング負荷",
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
        "sleep_score": "수면 점수",
        "sleep_duration": "수면 시간",
        "sleep_hrv": "수면 HRV",
        "sleep_deficit": "7일 수면 부족",
        "training_load_snapshot": "훈련 부하",
        "recent_load": "7일 TRIMP",
        "baseline_load": "28일 주간 기준",
        "workouts_7d": "운동 / 7일",
        "active_days_7d": "활동일 / 7일",
        "duration_7d": "훈련 / 7일",
        "improving": "향상",
        "stable": "안정",
        "declining": "감소"},
}


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


def _route_candidates(hass: HomeAssistant, manager) -> list[dict[str, str]]:
    """Return selected workout-source entities exposing usable route data."""
    selected = set(manager.config.get(CONF_WORKOUT_DEVICE_IDS) or [])
    if not selected:
        return []
    registry = er.async_get(hass)
    result: list[dict[str, str]] = []
    for registry_entry in registry.entities.values():
        if registry_entry.device_id not in selected:
            continue
        state = hass.states.get(registry_entry.entity_id)
        if state is None:
            continue
        attrs = state.attributes
        label = " ".join(
            (
                registry_entry.entity_id,
                registry_entry.name or "",
                registry_entry.original_name or "",
            )
        ).lower()
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
                "latest_workout": {
                    "sport": workout_sport_kind(manager.latest_workout()),
                    "name": (
                        manager.latest_workout().name
                        if manager.latest_workout() is not None
                        else None
                    ),
                },
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
