"""Small localized text catalog for workout calendar event content.

Calendar event payloads are not Home Assistant entities and therefore cannot use
entity attribute translation metadata. Fitness uses the profile language (which
is preselected from the HA UI language during setup) for event text instead.
"""
from __future__ import annotations

_TRANSLATIONS = {
    "en": {
        "workouts": "Workouts",
        "workout": "Workout",
        "duration": "Duration",
        "distance": "Distance",
        "avg_hr": "Avg HR",
        "avg_power": "Avg power",
        "calories": "Calories",
        "details": "Full merged workout details are available in Fitness.",
        "running": "Running",
        "cycling": "Cycling",
        "swimming": "Swimming",
        "walking": "Walking",
        "hiking": "Hiking",
        "strength": "Strength",
    },
    "de": {
        "workouts": "Trainingseinheiten",
        "workout": "Training",
        "duration": "Dauer",
        "distance": "Distanz",
        "avg_hr": "Ø Herzfrequenz",
        "avg_power": "Ø Leistung",
        "calories": "Kalorien",
        "details": "Alle zusammengeführten Trainingsdetails sind in Fitness verfügbar.",
        "running": "Laufen",
        "cycling": "Radfahren",
        "swimming": "Schwimmen",
        "walking": "Gehen",
        "hiking": "Wandern",
        "strength": "Krafttraining",
    },
    "el": {
        "workouts": "Προπονήσεις",
        "workout": "Προπόνηση",
        "duration": "Διάρκεια",
        "distance": "Απόσταση",
        "avg_hr": "Μέσος καρδιακός ρυθμός",
        "avg_power": "Μέση ισχύς",
        "calories": "Θερμίδες",
        "details": "Όλες οι συγχωνευμένες λεπτομέρειες της προπόνησης είναι διαθέσιμες στο Fitness.",
        "running": "Τρέξιμο",
        "cycling": "Ποδηλασία",
        "swimming": "Κολύμβηση",
        "walking": "Περπάτημα",
        "hiking": "Πεζοπορία",
        "strength": "Ενδυνάμωση",
    },
    "es": {
        "workouts": "Entrenamientos", "workout": "Entrenamiento", "duration": "Duración",
        "distance": "Distancia", "avg_hr": "FC media", "avg_power": "Potencia media",
        "calories": "Calorías", "details": "Todos los detalles combinados del entrenamiento están disponibles en Fitness.",
        "running": "Carrera", "cycling": "Ciclismo", "swimming": "Natación", "walking": "Caminata",
        "hiking": "Senderismo", "strength": "Fuerza",
    },
    "fr": {
        "workouts": "Entraînements", "workout": "Entraînement", "duration": "Durée",
        "distance": "Distance", "avg_hr": "FC moyenne", "avg_power": "Puissance moyenne",
        "calories": "Calories", "details": "Tous les détails fusionnés de l’entraînement sont disponibles dans Fitness.",
        "running": "Course", "cycling": "Cyclisme", "swimming": "Natation", "walking": "Marche",
        "hiking": "Randonnée", "strength": "Musculation",
    },
    "it": {
        "workouts": "Allenamenti", "workout": "Allenamento", "duration": "Durata",
        "distance": "Distanza", "avg_hr": "FC media", "avg_power": "Potenza media",
        "calories": "Calorie", "details": "Tutti i dettagli unificati dell’allenamento sono disponibili in Fitness.",
        "running": "Corsa", "cycling": "Ciclismo", "swimming": "Nuoto", "walking": "Camminata",
        "hiking": "Escursionismo", "strength": "Forza",
    },
    "ja": {
        "workouts": "ワークアウト", "workout": "ワークアウト", "duration": "時間",
        "distance": "距離", "avg_hr": "平均心拍数", "avg_power": "平均パワー",
        "calories": "カロリー", "details": "統合されたワークアウトの詳細は Fitness で確認できます。",
        "running": "ランニング", "cycling": "サイクリング", "swimming": "水泳", "walking": "ウォーキング",
        "hiking": "ハイキング", "strength": "筋力トレーニング",
    },
    "ko": {
        "workouts": "운동", "workout": "운동", "duration": "시간",
        "distance": "거리", "avg_hr": "평균 심박수", "avg_power": "평균 파워",
        "calories": "칼로리", "details": "통합된 전체 운동 세부 정보는 Fitness에서 확인할 수 있습니다.",
        "running": "러닝", "cycling": "사이클링", "swimming": "수영", "walking": "걷기",
        "hiking": "하이킹", "strength": "근력 운동",
    },
    "nl": {
        "workouts": "Work-outs", "workout": "Work-out", "duration": "Duur",
        "distance": "Afstand", "avg_hr": "Gem. hartslag", "avg_power": "Gem. vermogen",
        "calories": "Calorieën", "details": "Alle samengevoegde trainingsdetails zijn beschikbaar in Fitness.",
        "running": "Hardlopen", "cycling": "Fietsen", "swimming": "Zwemmen", "walking": "Wandelen",
        "hiking": "Hiken", "strength": "Krachttraining",
    },
    "pl": {
        "workouts": "Treningi", "workout": "Trening", "duration": "Czas trwania",
        "distance": "Dystans", "avg_hr": "Śr. tętno", "avg_power": "Śr. moc",
        "calories": "Kalorie", "details": "Pełne scalone szczegóły treningu są dostępne w Fitness.",
        "running": "Bieganie", "cycling": "Kolarstwo", "swimming": "Pływanie", "walking": "Chodzenie",
        "hiking": "Wędrówka", "strength": "Trening siłowy",
    },
    "pt": {
        "workouts": "Treinos", "workout": "Treino", "duration": "Duração",
        "distance": "Distância", "avg_hr": "FC média", "avg_power": "Potência média",
        "calories": "Calorias", "details": "Todos os detalhes combinados do treino estão disponíveis no Fitness.",
        "running": "Corrida", "cycling": "Ciclismo", "swimming": "Natação", "walking": "Caminhada",
        "hiking": "Trilha", "strength": "Força",
    },
    "ru": {
        "workouts": "Тренировки", "workout": "Тренировка", "duration": "Длительность",
        "distance": "Дистанция", "avg_hr": "Средний пульс", "avg_power": "Средняя мощность",
        "calories": "Калории", "details": "Все объединённые данные тренировки доступны в Fitness.",
        "running": "Бег", "cycling": "Велоспорт", "swimming": "Плавание", "walking": "Ходьба",
        "hiking": "Поход", "strength": "Силовая тренировка",
    },
    "tr": {
        "workouts": "Antrenmanlar", "workout": "Antrenman", "duration": "Süre",
        "distance": "Mesafe", "avg_hr": "Ort. nabız", "avg_power": "Ort. güç",
        "calories": "Kalori", "details": "Birleştirilmiş tüm antrenman ayrıntıları Fitness'ta kullanılabilir.",
        "running": "Koşu", "cycling": "Bisiklet", "swimming": "Yüzme", "walking": "Yürüyüş",
        "hiking": "Doğa yürüyüşü", "strength": "Kuvvet",
    },
    "uk": {
        "workouts": "Тренування", "workout": "Тренування", "duration": "Тривалість",
        "distance": "Дистанція", "avg_hr": "Сер. пульс", "avg_power": "Сер. потужність",
        "calories": "Калорії", "details": "Усі об’єднані дані тренування доступні у Fitness.",
        "running": "Біг", "cycling": "Велоспорт", "swimming": "Плавання", "walking": "Ходьба",
        "hiking": "Похід", "strength": "Силове тренування",
    },
    "zh": {
        "workouts": "训练", "workout": "训练", "duration": "时长",
        "distance": "距离", "avg_hr": "平均心率", "avg_power": "平均功率",
        "calories": "卡路里", "details": "完整的合并训练详情可在 Fitness 中查看。",
        "running": "跑步", "cycling": "骑行", "swimming": "游泳", "walking": "步行",
        "hiking": "徒步", "strength": "力量训练",
    },
}


def normalize_language(value: str | None) -> str:
    """Return a supported base language."""
    language = str(value or "en").strip().lower().replace("_", "-").split("-", 1)[0]
    return language if language in _TRANSLATIONS else "en"


def tr(language: str | None, key: str) -> str:
    """Translate a calendar label with English fallback."""
    lang = normalize_language(language)
    return _TRANSLATIONS.get(lang, _TRANSLATIONS["en"]).get(key, _TRANSLATIONS["en"].get(key, key))
