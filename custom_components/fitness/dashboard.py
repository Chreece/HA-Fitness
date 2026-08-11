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

_LOGGER = logging.getLogger(__name__)

_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"
_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=2026.8.4.3"
_SETUP_KEY = "_dashboard_frontend_setup"

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
        "route_privacy": "Map tiles are loaded from OpenStreetMap only when this card is shown.",
        "no_route": "No GPS route is available for the latest workout.",
        "ai_summary": "AI evaluation",
        "controls": "Workout controls",
        "days_7": "7 days",
        "days_28": "28 days",
        "days_90": "90 days",
    },
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
        "route_privacy": "Τα πλακίδια χάρτη φορτώνονται από το OpenStreetMap μόνο όταν εμφανίζεται αυτή η κάρτα.",
        "no_route": "Δεν υπάρχουν διαθέσιμα δεδομένα GPS για την τελευταία προπόνηση.",
        "ai_summary": "Αξιολόγηση με AI",
        "controls": "Έλεγχος προπόνησης",
        "days_7": "7 ημέρες",
        "days_28": "28 ημέρες",
        "days_90": "90 ημέρες",
    },
    "de": {"dashboard":"Fitness-Dashboard","description":"Training, Schlaf, Erholung und Fitnessfortschritt in einem adaptiven Dashboard.","overview":"Übersicht","progress":"Fortschritt","workouts":"Trainings","recovery":"Erholung & Schlaf","live":"Live-Training","current":"Aktuelles Training","latest_workout":"Letztes Training","latest_sleep":"Letzter Schlaf","evaluation":"Auswertung","fitness_progress":"Fitnessfortschritt","recovery_progress":"Erholungsfortschritt","training_progress":"Trainingsfortschritt","sleep_progress":"Schlaffortschritt","workout_metrics":"Trainingsmetriken","workout_comparison":"Vergleich mit deiner Basis","route":"Trainingsroute","route_privacy":"Kartendaten werden nur beim Anzeigen dieser Karte von OpenStreetMap geladen.","no_route":"Für das letzte Training ist keine GPS-Route verfügbar.","ai_summary":"KI-Auswertung","controls":"Trainingssteuerung","days_7":"7 Tage","days_28":"28 Tage","days_90":"90 Tage"},
    "fr": {"dashboard":"Tableau Fitness","description":"Entraînements, sommeil, récupération et progression dans un tableau adaptatif.","overview":"Vue d’ensemble","progress":"Progression","workouts":"Entraînements","recovery":"Récupération & sommeil","live":"Entraînement en direct","current":"Entraînement actuel","latest_workout":"Dernier entraînement","latest_sleep":"Dernier sommeil","evaluation":"Évaluation","fitness_progress":"Progression de la forme","recovery_progress":"Progression de la récupération","training_progress":"Progression de l’entraînement","sleep_progress":"Progression du sommeil","workout_metrics":"Mesures de l’entraînement","workout_comparison":"Comparaison à ta référence","route":"Parcours de l’entraînement","route_privacy":"Les tuiles cartographiques sont chargées depuis OpenStreetMap uniquement lorsque cette carte est affichée.","no_route":"Aucun parcours GPS n’est disponible pour le dernier entraînement.","ai_summary":"Évaluation IA","controls":"Commandes d’entraînement","days_7":"7 jours","days_28":"28 jours","days_90":"90 jours"},
    "es": {"dashboard":"Panel Fitness","description":"Entrenamientos, sueño, recuperación y progreso físico en un panel adaptativo.","overview":"Resumen","progress":"Progreso","workouts":"Entrenamientos","recovery":"Recuperación y sueño","live":"Entrenamiento en vivo","current":"Entrenamiento actual","latest_workout":"Último entrenamiento","latest_sleep":"Último sueño","evaluation":"Evaluación","fitness_progress":"Progreso físico","recovery_progress":"Progreso de recuperación","training_progress":"Progreso de entrenamiento","sleep_progress":"Progreso del sueño","workout_metrics":"Métricas del entrenamiento","workout_comparison":"Comparado con tu referencia","route":"Ruta del entrenamiento","route_privacy":"Los mosaicos del mapa se cargan desde OpenStreetMap solo cuando se muestra esta tarjeta.","no_route":"No hay una ruta GPS disponible para el último entrenamiento.","ai_summary":"Evaluación con IA","controls":"Controles de entrenamiento","days_7":"7 días","days_28":"28 días","days_90":"90 días"},
    "it": {"dashboard":"Dashboard Fitness","description":"Allenamenti, sonno, recupero e progressi in una dashboard adattiva.","overview":"Panoramica","progress":"Progressi","workouts":"Allenamenti","recovery":"Recupero e sonno","live":"Allenamento live","current":"Allenamento attuale","latest_workout":"Ultimo allenamento","latest_sleep":"Ultimo sonno","evaluation":"Valutazione","fitness_progress":"Progressi fitness","recovery_progress":"Progressi recupero","training_progress":"Progressi allenamento","sleep_progress":"Progressi sonno","workout_metrics":"Metriche allenamento","workout_comparison":"Confronto con il tuo riferimento","route":"Percorso allenamento","route_privacy":"Le mappe vengono caricate da OpenStreetMap solo quando questa scheda è visualizzata.","no_route":"Nessun percorso GPS disponibile per l’ultimo allenamento.","ai_summary":"Valutazione AI","controls":"Controlli allenamento","days_7":"7 giorni","days_28":"28 giorni","days_90":"90 giorni"},
    "pt": {"dashboard":"Painel Fitness","description":"Treinos, sono, recuperação e progresso físico num painel adaptativo.","overview":"Visão geral","progress":"Progresso","workouts":"Treinos","recovery":"Recuperação e sono","live":"Treino ao vivo","current":"Treino atual","latest_workout":"Último treino","latest_sleep":"Último sono","evaluation":"Avaliação","fitness_progress":"Progresso físico","recovery_progress":"Progresso da recuperação","training_progress":"Progresso do treino","sleep_progress":"Progresso do sono","workout_metrics":"Métricas do treino","workout_comparison":"Comparação com a tua referência","route":"Percurso do treino","route_privacy":"Os mosaicos do mapa são carregados do OpenStreetMap apenas quando este cartão é mostrado.","no_route":"Não existe percurso GPS para o último treino.","ai_summary":"Avaliação por IA","controls":"Controlos do treino","days_7":"7 dias","days_28":"28 dias","days_90":"90 dias"},
    "nl": {"dashboard":"Fitness-dashboard","description":"Trainingen, slaap, herstel en fitnessvoortgang in één adaptief dashboard.","overview":"Overzicht","progress":"Voortgang","workouts":"Trainingen","recovery":"Herstel & slaap","live":"Live training","current":"Huidige training","latest_workout":"Laatste training","latest_sleep":"Laatste slaap","evaluation":"Evaluatie","fitness_progress":"Fitnessvoortgang","recovery_progress":"Herstelvoortgang","training_progress":"Trainingsvoortgang","sleep_progress":"Slaapvoortgang","workout_metrics":"Trainingsgegevens","workout_comparison":"Vergelijking met je basislijn","route":"Trainingsroute","route_privacy":"Kaarttegels worden alleen van OpenStreetMap geladen wanneer deze kaart wordt getoond.","no_route":"Geen GPS-route beschikbaar voor de laatste training.","ai_summary":"AI-evaluatie","controls":"Trainingsbediening","days_7":"7 dagen","days_28":"28 dagen","days_90":"90 dagen"},
    "pl": {"dashboard":"Panel Fitness","description":"Treningi, sen, regeneracja i postęp kondycji w jednym adaptacyjnym panelu.","overview":"Przegląd","progress":"Postęp","workouts":"Treningi","recovery":"Regeneracja i sen","live":"Trening na żywo","current":"Bieżący trening","latest_workout":"Ostatni trening","latest_sleep":"Ostatni sen","evaluation":"Ocena","fitness_progress":"Postęp kondycji","recovery_progress":"Postęp regeneracji","training_progress":"Postęp treningu","sleep_progress":"Postęp snu","workout_metrics":"Metryki treningu","workout_comparison":"Porównanie z twoją bazą","route":"Trasa treningu","route_privacy":"Kafelki mapy są pobierane z OpenStreetMap tylko podczas wyświetlania tej karty.","no_route":"Brak trasy GPS dla ostatniego treningu.","ai_summary":"Ocena AI","controls":"Sterowanie treningiem","days_7":"7 dni","days_28":"28 dni","days_90":"90 dni"},
    "ru": {"dashboard":"Панель Fitness","description":"Тренировки, сон, восстановление и прогресс в одной адаптивной панели.","overview":"Обзор","progress":"Прогресс","workouts":"Тренировки","recovery":"Восстановление и сон","live":"Тренировка в реальном времени","current":"Текущая тренировка","latest_workout":"Последняя тренировка","latest_sleep":"Последний сон","evaluation":"Оценка","fitness_progress":"Прогресс формы","recovery_progress":"Прогресс восстановления","training_progress":"Прогресс тренировок","sleep_progress":"Прогресс сна","workout_metrics":"Показатели тренировки","workout_comparison":"Сравнение с вашей базой","route":"Маршрут тренировки","route_privacy":"Карты загружаются с OpenStreetMap только при отображении этой карточки.","no_route":"Для последней тренировки нет GPS-маршрута.","ai_summary":"Оценка ИИ","controls":"Управление тренировкой","days_7":"7 дней","days_28":"28 дней","days_90":"90 дней"},
    "uk": {"dashboard":"Панель Fitness","description":"Тренування, сон, відновлення та прогрес в одній адаптивній панелі.","overview":"Огляд","progress":"Прогрес","workouts":"Тренування","recovery":"Відновлення та сон","live":"Тренування наживо","current":"Поточне тренування","latest_workout":"Останнє тренування","latest_sleep":"Останній сон","evaluation":"Оцінка","fitness_progress":"Прогрес форми","recovery_progress":"Прогрес відновлення","training_progress":"Прогрес тренувань","sleep_progress":"Прогрес сну","workout_metrics":"Показники тренування","workout_comparison":"Порівняння з вашою базою","route":"Маршрут тренування","route_privacy":"Карти завантажуються з OpenStreetMap лише під час показу цієї картки.","no_route":"Для останнього тренування немає GPS-маршруту.","ai_summary":"Оцінка ШІ","controls":"Керування тренуванням","days_7":"7 днів","days_28":"28 днів","days_90":"90 днів"},
    "tr": {"dashboard":"Fitness paneli","description":"Antrenman, uyku, toparlanma ve fitness ilerlemesi tek uyarlanabilir panelde.","overview":"Genel bakış","progress":"İlerleme","workouts":"Antrenmanlar","recovery":"Toparlanma ve uyku","live":"Canlı antrenman","current":"Mevcut antrenman","latest_workout":"Son antrenman","latest_sleep":"Son uyku","evaluation":"Değerlendirme","fitness_progress":"Fitness ilerlemesi","recovery_progress":"Toparlanma ilerlemesi","training_progress":"Antrenman ilerlemesi","sleep_progress":"Uyku ilerlemesi","workout_metrics":"Antrenman ölçümleri","workout_comparison":"Kişisel bazla karşılaştırma","route":"Antrenman rotası","route_privacy":"Harita döşemeleri yalnızca bu kart gösterildiğinde OpenStreetMap'den yüklenir.","no_route":"Son antrenman için GPS rotası yok.","ai_summary":"AI değerlendirmesi","controls":"Antrenman kontrolleri","days_7":"7 gün","days_28":"28 gün","days_90":"90 gün"},
    "zh": {"dashboard":"Fitness 仪表板","description":"在一个自适应仪表板中查看训练、睡眠、恢复和体能进步。","overview":"概览","progress":"进步","workouts":"训练","recovery":"恢复与睡眠","live":"实时训练","current":"当前训练","latest_workout":"最近训练","latest_sleep":"最近睡眠","evaluation":"评估","fitness_progress":"体能进步","recovery_progress":"恢复进步","training_progress":"训练进步","sleep_progress":"睡眠进步","workout_metrics":"训练指标","workout_comparison":"与个人基线比较","route":"训练路线","route_privacy":"仅在显示此卡片时从 OpenStreetMap 加载地图瓦片。","no_route":"最近训练没有可用的 GPS 路线。","ai_summary":"AI 评估","controls":"训练控制","days_7":"7 天","days_28":"28 天","days_90":"90 天"},
    "ja": {"dashboard":"Fitness ダッシュボード","description":"ワークアウト、睡眠、回復、フィットネスの進歩を1つの適応型ダッシュボードにまとめます。","overview":"概要","progress":"進歩","workouts":"ワークアウト","recovery":"回復と睡眠","live":"ライブワークアウト","current":"現在のワークアウト","latest_workout":"最新のワークアウト","latest_sleep":"最新の睡眠","evaluation":"評価","fitness_progress":"フィットネスの進歩","recovery_progress":"回復の進歩","training_progress":"トレーニングの進歩","sleep_progress":"睡眠の進歩","workout_metrics":"ワークアウト指標","workout_comparison":"個人ベースラインとの比較","route":"ワークアウトルート","route_privacy":"このカードを表示している間だけ OpenStreetMap から地図タイルを読み込みます。","no_route":"最新のワークアウトに GPS ルートがありません。","ai_summary":"AI 評価","controls":"ワークアウト操作","days_7":"7日","days_28":"28日","days_90":"90日"},
    "ko": {"dashboard":"Fitness 대시보드","description":"운동, 수면, 회복 및 체력 향상을 하나의 적응형 대시보드에서 확인합니다.","overview":"개요","progress":"향상","workouts":"운동","recovery":"회복 및 수면","live":"실시간 운동","current":"현재 운동","latest_workout":"최근 운동","latest_sleep":"최근 수면","evaluation":"평가","fitness_progress":"체력 향상","recovery_progress":"회복 향상","training_progress":"훈련 향상","sleep_progress":"수면 향상","workout_metrics":"운동 지표","workout_comparison":"개인 기준선과 비교","route":"운동 경로","route_privacy":"이 카드가 표시될 때만 OpenStreetMap에서 지도 타일을 불러옵니다.","no_route":"최근 운동에 GPS 경로가 없습니다.","ai_summary":"AI 평가","controls":"운동 제어","days_7":"7일","days_28":"28일","days_90":"90일"},
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
                "labels": _DASHBOARD_TEXT[lang],
                "entities": entities,
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
    for item in resources.async_items():
        if str(item.get("url", "")).startswith(_RESOURCE_NAMESPACE):
            if item.get("url") != _RESOURCE_URL:
                await resources.async_update_item(item["id"], {"url": _RESOURCE_URL})
            return
    await resources.async_create_item({"res_type": "module", "url": _RESOURCE_URL})
    _LOGGER.info("Registered Fitness community dashboard resource: %s", _RESOURCE_URL)


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
