"""Localized names for Fitness-created devices."""

from .const import SUPPORTED_LANGUAGES

DEVICE_NAMES = {'en': {'evaluation': 'Evaluation', 'live': 'Live workout', 'sleep': 'Sleep', 'workout': 'Workouts'}, 'el': {'evaluation': 'Αξιολόγηση', 'live': 'Ζωντανή προπόνηση', 'sleep': 'Ύπνος', 'workout': 'Προπονήσεις'}, 'de': {'evaluation': 'Auswertung', 'live': 'Live-Training', 'sleep': 'Schlaf', 'workout': 'Trainings'}, 'fr': {'evaluation': 'Évaluation', 'live': 'Entraînement en direct', 'sleep': 'Sommeil', 'workout': 'Entraînements'}, 'es': {'evaluation': 'Evaluación', 'live': 'Entrenamiento en directo', 'sleep': 'Sueño', 'workout': 'Entrenamientos'}, 'it': {'evaluation': 'Valutazione', 'live': 'Allenamento in tempo reale', 'sleep': 'Sonno', 'workout': 'Allenamenti'}, 'pt': {'evaluation': 'Avaliação', 'live': 'Treino ao vivo', 'sleep': 'Sono', 'workout': 'Treinos'}, 'nl': {'evaluation': 'Evaluatie', 'live': 'Live training', 'sleep': 'Slaap', 'workout': 'Trainingen'}, 'pl': {'evaluation': 'Ocena', 'live': 'Trening na żywo', 'sleep': 'Sen', 'workout': 'Treningi'}, 'ru': {'evaluation': 'Оценка', 'live': 'Тренировка в реальном времени', 'sleep': 'Сон', 'workout': 'Тренировки'}, 'uk': {'evaluation': 'Оцінка', 'live': 'Тренування наживо', 'sleep': 'Сон', 'workout': 'Тренування'}, 'tr': {'evaluation': 'Değerlendirme', 'live': 'Canlı antrenman', 'sleep': 'Uyku', 'workout': 'Antrenmanlar'}, 'zh': {'evaluation': '评估', 'live': '实时训练', 'sleep': '睡眠', 'workout': '训练记录'}, 'ja': {'evaluation': '評価', 'live': 'ライブトレーニング', 'sleep': '睡眠', 'workout': 'ワークアウト'}, 'ko': {'evaluation': '평가', 'live': '실시간 운동', 'sleep': '수면', 'workout': '운동 기록'}}

def language_code(value: str | None) -> str:
    code = str(value or "en").lower().split("-")[0].split("_")[0]
    return code if code in SUPPORTED_LANGUAGES else "en"

def device_name(language: str | None, kind: str) -> str:
    code = language_code(language)
    return DEVICE_NAMES.get(code, DEVICE_NAMES["en"])[kind]
