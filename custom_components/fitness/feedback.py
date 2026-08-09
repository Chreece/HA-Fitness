"""Localized audiovisual coaching and workout-summary helpers."""

from __future__ import annotations

from dataclasses import dataclass


INTENSITY_RGB = {
    "very_light": (70, 130, 255),
    "light": (50, 205, 90),
    "moderate": (255, 205, 40),
    "vigorous": (255, 120, 20),
    "near_maximal": (255, 35, 35),
}


_MESSAGES = {
    "en": {
        "intensity": {
            "very_light": "Very low intensity. Settle into your rhythm and keep moving smoothly.",
            "light": "Low intensity. Nice and controlled—this is a good easy effort.",
            "moderate": "Moderate intensity. Steady work—keep the rhythm controlled and consistent.",
            "vigorous": "High intensity. Strong effort—stay controlled and keep your form together.",
            "near_maximal": "Very high intensity. You are close to maximal effort—use it purposefully and stay in control.",
        },
        "workout_title": "Workout updated",
        "workout": "{name} is complete. About {duration} minutes{distance}. Nice work—your fitness evaluation has been updated.",
    },
    "el": {
        "intensity": {
            "very_light": "Πολύ χαμηλή ένταση. Βρες τον ρυθμό σου και συνέχισε ομαλά.",
            "light": "Χαμηλή ένταση. Ωραία και ελεγχόμενη προσπάθεια—ιδανική για εύκολη δουλειά.",
            "moderate": "Μέτρια ένταση. Σταθερή προσπάθεια—κράτησε τον ρυθμό ελεγχόμενο.",
            "vigorous": "Υψηλή ένταση. Δυνατή προσπάθεια—μείνε ελεγχόμενος και κράτησε καλή τεχνική.",
            "near_maximal": "Πολύ υψηλή ένταση. Είσαι κοντά στη μέγιστη προσπάθεια—χρησιμοποίησέ την στοχευμένα και με έλεγχο.",
        },
        "workout_title": "Η προπόνηση ενημερώθηκε",
        "workout": "Η προπόνηση {name} ολοκληρώθηκε. Περίπου {duration} λεπτά{distance}. Μπράβο—η αξιολόγηση φυσικής κατάστασης ενημερώθηκε.",
    },
    "de": {
        "intensity": {
            "very_light": "Sehr niedrige Intensität. Finde deinen Rhythmus und bewege dich locker weiter.",
            "light": "Niedrige Intensität. Schön kontrolliert—eine gute lockere Belastung.",
            "moderate": "Moderate Intensität. Gleichmäßige Arbeit—halte den Rhythmus kontrolliert.",
            "vigorous": "Hohe Intensität. Starke Belastung—bleib kontrolliert und achte auf deine Technik.",
            "near_maximal": "Sehr hohe Intensität. Du bist nahe am Maximum—setze diese Belastung gezielt und kontrolliert ein.",
        },
        "workout_title": "Training aktualisiert",
        "workout": "{name} ist abgeschlossen. Etwa {duration} Minuten{distance}. Gute Arbeit—deine Fitnessbewertung wurde aktualisiert.",
    },
    "fr": {
        "intensity": {
            "very_light": "Intensité très faible. Trouve ton rythme et continue en douceur.",
            "light": "Faible intensité. Effort bien contrôlé—parfait pour une séance facile.",
            "moderate": "Intensité modérée. Effort régulier—garde un rythme maîtrisé.",
            "vigorous": "Intensité élevée. Bel effort—reste maîtrisé et garde une bonne technique.",
            "near_maximal": "Intensité très élevée. Tu es proche de l’effort maximal—utilise-le de façon ciblée et contrôlée.",
        },
        "workout_title": "Entraînement mis à jour",
        "workout": "{name} est terminé. Environ {duration} minutes{distance}. Beau travail—ton évaluation de forme a été mise à jour.",
    },
    "es": {
        "intensity": {
            "very_light": "Intensidad muy baja. Encuentra tu ritmo y sigue moviéndote con suavidad.",
            "light": "Intensidad baja. Buen control—un esfuerzo fácil y útil.",
            "moderate": "Intensidad moderada. Trabajo constante—mantén el ritmo controlado.",
            "vigorous": "Intensidad alta. Esfuerzo fuerte—mantén el control y una buena técnica.",
            "near_maximal": "Intensidad muy alta. Estás cerca del máximo—úsala con intención y mantén el control.",
        },
        "workout_title": "Entrenamiento actualizado",
        "workout": "{name} ha terminado. Aproximadamente {duration} minutos{distance}. Buen trabajo—tu evaluación de fitness se ha actualizado.",
    },
    "it": {
        "intensity": {
            "very_light": "Intensità molto bassa. Trova il ritmo e continua in modo fluido.",
            "light": "Intensità bassa. Ben controllata—un buon lavoro facile.",
            "moderate": "Intensità moderata. Lavoro costante—mantieni il ritmo sotto controllo.",
            "vigorous": "Intensità alta. Sforzo deciso—resta controllato e cura la tecnica.",
            "near_maximal": "Intensità molto alta. Sei vicino allo sforzo massimo—usalo con uno scopo preciso e resta in controllo.",
        },
        "workout_title": "Allenamento aggiornato",
        "workout": "{name} è terminato. Circa {duration} minuti{distance}. Ottimo lavoro—la valutazione fitness è stata aggiornata.",
    },
    "pt": {
        "intensity": {
            "very_light": "Intensidade muito baixa. Encontra o teu ritmo e continua de forma suave.",
            "light": "Intensidade baixa. Bem controlado—um bom esforço leve.",
            "moderate": "Intensidade moderada. Trabalho constante—mantém o ritmo controlado.",
            "vigorous": "Intensidade alta. Esforço forte—mantém o controlo e uma boa técnica.",
            "near_maximal": "Intensidade muito alta. Estás perto do máximo—usa este esforço de forma intencional e controlada.",
        },
        "workout_title": "Treino atualizado",
        "workout": "{name} terminou. Cerca de {duration} minutos{distance}. Bom trabalho—a tua avaliação de fitness foi atualizada.",
    },
    "nl": {
        "intensity": {
            "very_light": "Zeer lage intensiteit. Vind je ritme en blijf soepel bewegen.",
            "light": "Lage intensiteit. Mooi gecontroleerd—een goede rustige inspanning.",
            "moderate": "Matige intensiteit. Gelijkmatig werk—houd het ritme gecontroleerd.",
            "vigorous": "Hoge intensiteit. Sterke inspanning—blijf gecontroleerd en let op je techniek.",
            "near_maximal": "Zeer hoge intensiteit. Je zit dicht bij maximaal—gebruik dit doelgericht en blijf in controle.",
        },
        "workout_title": "Training bijgewerkt",
        "workout": "{name} is voltooid. Ongeveer {duration} minuten{distance}. Goed gedaan—je fitnessevaluatie is bijgewerkt.",
    },
    "pl": {
        "intensity": {
            "very_light": "Bardzo niska intensywność. Znajdź rytm i poruszaj się swobodnie.",
            "light": "Niska intensywność. Dobrze kontrolowana—świetna lekka praca.",
            "moderate": "Umiarkowana intensywność. Równa praca—utrzymuj kontrolowany rytm.",
            "vigorous": "Wysoka intensywność. Mocny wysiłek—zachowaj kontrolę i dobrą technikę.",
            "near_maximal": "Bardzo wysoka intensywność. Jesteś blisko maksimum—wykorzystuj ją celowo i zachowaj kontrolę.",
        },
        "workout_title": "Trening zaktualizowany",
        "workout": "{name} zakończony. Około {duration} minut{distance}. Dobra robota—ocena fitness została zaktualizowana.",
    },
    "ru": {
        "intensity": {
            "very_light": "Очень низкая интенсивность. Найди свой ритм и продолжай двигаться плавно.",
            "light": "Низкая интенсивность. Хорошо контролируется—подходящая лёгкая нагрузка.",
            "moderate": "Умеренная интенсивность. Ровная работа—сохраняй контролируемый ритм.",
            "vigorous": "Высокая интенсивность. Сильная нагрузка—сохраняй контроль и хорошую технику.",
            "near_maximal": "Очень высокая интенсивность. Ты близок к максимуму—используй такую нагрузку целенаправленно и контролируемо.",
        },
        "workout_title": "Тренировка обновлена",
        "workout": "{name} завершена. Около {duration} минут{distance}. Отличная работа—оценка физической формы обновлена.",
    },
    "uk": {
        "intensity": {
            "very_light": "Дуже низька інтенсивність. Знайди свій ритм і продовжуй рухатися плавно.",
            "light": "Низька інтенсивність. Добре контрольована—гарна легка робота.",
            "moderate": "Помірна інтенсивність. Рівна робота—тримай ритм під контролем.",
            "vigorous": "Висока інтенсивність. Сильне навантаження—зберігай контроль і хорошу техніку.",
            "near_maximal": "Дуже висока інтенсивність. Ти близько до максимуму—використовуй її цілеспрямовано й контрольовано.",
        },
        "workout_title": "Тренування оновлено",
        "workout": "{name} завершено. Близько {duration} хвилин{distance}. Гарна робота—оцінку фізичної форми оновлено.",
    },
    "tr": {
        "intensity": {
            "very_light": "Çok düşük yoğunluk. Ritmini bul ve akıcı şekilde hareket etmeye devam et.",
            "light": "Düşük yoğunluk. Güzel kontrollü—iyi bir kolay çalışma.",
            "moderate": "Orta yoğunluk. İstikrarlı çalışma—ritmi kontrollü tut.",
            "vigorous": "Yüksek yoğunluk. Güçlü efor—kontrolü ve iyi tekniği koru.",
            "near_maximal": "Çok yüksek yoğunluk. Maksimuma yakınsın—bu eforu amaçlı ve kontrollü kullan.",
        },
        "workout_title": "Antrenman güncellendi",
        "workout": "{name} tamamlandı. Yaklaşık {duration} dakika{distance}. Güzel çalışma—fitness değerlendirmen güncellendi.",
    },
    "zh": {
        "intensity": {
            "very_light": "强度很低。找到自己的节奏，保持顺畅运动。",
            "light": "低强度。控制得很好，这是很适合轻松训练的强度。",
            "moderate": "中等强度。保持稳定，并继续控制好节奏。",
            "vigorous": "高强度。很有力量的训练，保持控制并注意动作质量。",
            "near_maximal": "非常高的强度。你已接近最大努力，请有目的地使用这种强度并保持控制。",
        },
        "workout_title": "训练已更新",
        "workout": "{name} 已完成。大约 {duration} 分钟{distance}。做得很好，你的健身评估已更新。",
    },
    "ja": {
        "intensity": {
            "very_light": "とても低い強度です。自分のリズムを見つけて、滑らかに動き続けましょう。",
            "light": "低い強度です。よくコントロールできています。イージーな運動に適した強度です。",
            "moderate": "中程度の強度です。安定した運動を続け、リズムをコントロールしましょう。",
            "vigorous": "高い強度です。力強い運動です。コントロールと良いフォームを保ちましょう。",
            "near_maximal": "非常に高い強度です。最大努力に近いので、目的を持って使い、コントロールを保ちましょう。",
        },
        "workout_title": "ワークアウトを更新しました",
        "workout": "{name} が完了しました。約 {duration} 分{distance}。お疲れさまでした。フィットネス評価を更新しました。",
    },
    "ko": {
        "intensity": {
            "very_light": "매우 낮은 강도입니다. 리듬을 찾고 부드럽게 계속 움직이세요.",
            "light": "낮은 강도입니다. 잘 조절하고 있습니다. 가벼운 운동에 좋은 강도입니다.",
            "moderate": "중간 강도입니다. 안정적으로 운동하며 리듬을 조절하세요.",
            "vigorous": "높은 강도입니다. 강한 노력입니다. 통제력을 유지하고 자세를 지키세요.",
            "near_maximal": "매우 높은 강도입니다. 최대 노력에 가깝습니다. 목적에 맞게 사용하고 통제력을 유지하세요.",
        },
        "workout_title": "운동이 업데이트되었습니다",
        "workout": "{name} 완료. 약 {duration}분{distance}. 잘했습니다. 피트니스 평가가 업데이트되었습니다.",
    },
}


def language_code(language: str | None) -> str:
    value = str(language or "en").lower()
    code = value.split("-")[0].split("_")[0]
    return code if code in _MESSAGES else "en"


def intensity_rgb(intensity: str | None):
    return INTENSITY_RGB.get(intensity or "")




def static_workout_message(
    language: str | None,
    *,
    name: str,
    duration_minutes: int,
    distance_km: float | None,
) -> tuple[str, str]:
    code = language_code(language)
    messages = _MESSAGES.get(code, _MESSAGES["en"])

    if distance_km is None or distance_km <= 0:
        distance = ""
    else:
        if code == "el":
            distance = f" και {distance_km:.1f} χιλιόμετρα"
        elif code == "de":
            distance = f" und {distance_km:.1f} Kilometer"
        elif code == "fr":
            distance = f" et {distance_km:.1f} km"
        elif code == "es":
            distance = f" y {distance_km:.1f} km"
        elif code == "it":
            distance = f" e {distance_km:.1f} km"
        elif code == "pt":
            distance = f" e {distance_km:.1f} km"
        elif code == "nl":
            distance = f" en {distance_km:.1f} km"
        elif code == "pl":
            distance = f" i {distance_km:.1f} km"
        elif code in ("ru", "uk"):
            distance = f" и {distance_km:.1f} км"
        elif code == "tr":
            distance = f" ve {distance_km:.1f} km"
        elif code == "zh":
            distance = f"，{distance_km:.1f} 公里"
        elif code == "ja":
            distance = f"、{distance_km:.1f} km"
        elif code == "ko":
            distance = f", {distance_km:.1f} km"
        else:
            distance = f" and {distance_km:.1f} km"

    return (
        messages["workout_title"],
        messages["workout"].format(
            name=name,
            duration=duration_minutes,
            distance=distance,
        ),
    )


_BPM_TEMPLATES = {
    "en": " Current heart rate: {bpm} beats per minute.",
    "el": " Τρέχοντες καρδιακοί παλμοί: {bpm} ανά λεπτό.",
    "de": " Aktuelle Herzfrequenz: {bpm} Schläge pro Minute.",
    "fr": " Fréquence cardiaque actuelle : {bpm} battements par minute.",
    "es": " Frecuencia cardíaca actual: {bpm} latidos por minuto.",
    "it": " Frequenza cardiaca attuale: {bpm} battiti al minuto.",
    "pt": " Frequência cardíaca atual: {bpm} batimentos por minuto.",
    "nl": " Huidige hartslag: {bpm} slagen per minuut.",
    "pl": " Aktualne tętno: {bpm} uderzeń na minutę.",
    "ru": " Текущий пульс: {bpm} ударов в минуту.",
    "uk": " Поточний пульс: {bpm} ударів за хвилину.",
    "tr": " Güncel nabız: dakikada {bpm} atım.",
    "zh": " 当前心率：每分钟 {bpm} 次。",
    "ja": " 現在の心拍数は1分あたり {bpm} 回です。",
    "ko": " 현재 심박수는 분당 {bpm}회입니다.",
}

_PERIODIC_TEMPLATES = {
    "en": "Live update: {parts}. Keep the effort controlled and consistent.",
    "el": "Ζωντανή ενημέρωση: {parts}. Κράτησε την προσπάθεια ελεγχόμενη και σταθερή.",
    "de": "Live-Update: {parts}. Halte die Belastung kontrolliert und gleichmäßig.",
    "fr": "Point en direct : {parts}. Garde un effort régulier et maîtrisé.",
    "es": "Actualización en vivo: {parts}. Mantén el esfuerzo controlado y constante.",
    "it": "Aggiornamento live: {parts}. Mantieni lo sforzo controllato e costante.",
    "pt": "Atualização ao vivo: {parts}. Mantém o esforço controlado e consistente.",
    "nl": "Live-update: {parts}. Houd de inspanning gecontroleerd en gelijkmatig.",
    "pl": "Aktualizacja na żywo: {parts}. Utrzymuj wysiłek równy i kontrolowany.",
    "ru": "Текущие данные: {parts}. Сохраняй ровную и контролируемую нагрузку.",
    "uk": "Поточні дані: {parts}. Зберігай рівне та контрольоване навантаження.",
    "tr": "Canlı güncelleme: {parts}. Eforu kontrollü ve istikrarlı tut.",
    "zh": "实时更新：{parts}。保持稳定并控制好训练强度。",
    "ja": "ライブ更新：{parts}。運動強度を安定してコントロールしましょう。",
    "ko": "실시간 업데이트: {parts}. 운동 강도를 안정적으로 조절하세요.",
}

_LIVE_PARTS = {
    "en": {
        "hr": "heart rate {v} bpm",
        "intensity": "intensity {v}",
        "power": "power {v} watts",
        "cadence": "cadence {v} per minute",
        "pace": "pace {v} min/km",
    },
    "el": {
        "hr": "καρδιακοί παλμοί {v} bpm",
        "intensity": "ένταση {v}",
        "power": "ισχύς {v} watt",
        "cadence": "συχνότητα {v} ανά λεπτό",
        "pace": "ρυθμός {v} min/km",
    },
    "de": {
        "hr": "Herzfrequenz {v} bpm",
        "intensity": "Intensität {v}",
        "power": "Leistung {v} Watt",
        "cadence": "Kadenz {v} pro Minute",
        "pace": "Tempo {v} min/km",
    },
}


def static_intensity_message(
    language: str | None,
    intensity: str,
    bpm: float | int | None = None,
) -> str:
    """Localized intensity cue, optionally including current heart rate."""
    code = language_code(language)
    base = (
        _MESSAGES.get(code, _MESSAGES["en"])["intensity"].get(intensity)
        or _MESSAGES["en"]["intensity"].get(intensity)
        or "Keep going."
    )
    if bpm is None:
        return base

    try:
        bpm_value = int(round(float(bpm)))
    except (TypeError, ValueError):
        return base

    template = _BPM_TEMPLATES.get(code, _BPM_TEMPLATES["en"])
    return base + template.format(bpm=bpm_value)


def static_periodic_live_message(
    language: str | None,
    *,
    heart_rate: float | None,
    intensity: str | None,
    power: float | None,
    cadence: float | None,
    pace: float | None,
) -> str | None:
    """Create a concise localized live-data announcement."""
    code = language_code(language)
    labels = _LIVE_PARTS.get(code, _LIVE_PARTS["en"])
    parts: list[str] = []

    if heart_rate is not None:
        parts.append(labels["hr"].format(v=int(round(heart_rate))))
    if intensity is not None:
        parts.append(labels["intensity"].format(v=intensity))
    if power is not None:
        parts.append(labels["power"].format(v=int(round(power))))
    if cadence is not None:
        parts.append(labels["cadence"].format(v=int(round(cadence))))
    if pace is not None:
        parts.append(labels["pace"].format(v=f"{pace:.2f}"))

    if not parts:
        return None

    template = _PERIODIC_TEMPLATES.get(
        code,
        _PERIODIC_TEMPLATES["en"],
    )
    return template.format(parts=", ".join(parts))
