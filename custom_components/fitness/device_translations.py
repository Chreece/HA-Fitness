"""Localized names for Fitness-created devices."""

from .const import SUPPORTED_LANGUAGES

DEVICE_NAMES = {'en': {'evaluation': 'Evaluation', 'live': 'Live workout', 'sleep': 'Recovery', 'workout': 'Workouts', 'recovery': 'Recovery'}, 'el': {'evaluation': 'Αξιολόγηση', 'live': 'Ζωντανή προπόνηση', 'sleep': 'Αποκατάσταση', 'workout': 'Προπονήσεις', 'recovery': 'Αποκατάσταση'}, 'de': {'evaluation': 'Auswertung', 'live': 'Live-Training', 'sleep': 'Erholung', 'workout': 'Trainings', 'recovery': 'Erholung'}, 'fr': {'evaluation': 'Évaluation', 'live': 'Entraînement en direct', 'sleep': 'Récupération', 'workout': 'Entraînements', 'recovery': 'Récupération'}, 'es': {'evaluation': 'Evaluación', 'live': 'Entrenamiento en directo', 'sleep': 'Recuperación', 'workout': 'Entrenamientos', 'recovery': 'Recuperación'}, 'it': {'evaluation': 'Valutazione', 'live': 'Allenamento in tempo reale', 'sleep': 'Recupero', 'workout': 'Allenamenti', 'recovery': 'Recupero'}, 'pt': {'evaluation': 'Avaliação', 'live': 'Treino ao vivo', 'sleep': 'Recuperação', 'workout': 'Treinos', 'recovery': 'Recuperação'}, 'nl': {'evaluation': 'Evaluatie', 'live': 'Live training', 'sleep': 'Herstel', 'workout': 'Trainingen', 'recovery': 'Herstel'}, 'pl': {'evaluation': 'Ocena', 'live': 'Trening na żywo', 'sleep': 'Regeneracja', 'workout': 'Treningi', 'recovery': 'Regeneracja'}, 'ru': {'evaluation': 'Оценка', 'live': 'Тренировка в реальном времени', 'sleep': 'Восстановление', 'workout': 'Тренировки', 'recovery': 'Восстановление'}, 'uk': {'evaluation': 'Оцінка', 'live': 'Тренування наживо', 'sleep': 'Відновлення', 'workout': 'Тренування', 'recovery': 'Відновлення'}, 'tr': {'evaluation': 'Değerlendirme', 'live': 'Canlı antrenman', 'sleep': 'Toparlanma', 'workout': 'Antrenmanlar', 'recovery': 'Toparlanma'}, 'zh': {'evaluation': '评估', 'live': '实时训练', 'sleep': '恢复', 'workout': '训练记录', 'recovery': '恢复'}, 'ja': {'evaluation': '評価', 'live': 'ライブトレーニング', 'sleep': 'リカバリー', 'workout': 'ワークアウト', 'recovery': 'リカバリー'}, 'ko': {'evaluation': '평가', 'live': '실시간 운동', 'sleep': '회복', 'workout': '운동 기록', 'recovery': '회복'}}

def language_code(value: str | None) -> str:
    code = str(value or "en").lower().split("-")[0].split("_")[0]
    return code if code in SUPPORTED_LANGUAGES else "en"

def device_name(language: str | None, kind: str) -> str:
    code = language_code(language)
    return DEVICE_NAMES.get(code, DEVICE_NAMES["en"])[kind]
