"""Localized deterministic explanations for Fitness sensor calculations.

This module is intentionally AI-free. Entity metadata must remain fast, stable,
reproducible, and independent of any LLM/provider response.
"""

from __future__ import annotations

# Method names remain scientific/protocol names. User-facing prose is localized.
_LANGUAGE_TEXT = {
    "en": {
        "calculated": "Calculated by Fitness from the listed inputs.",
        "provider": "Provided by the selected fitness integration; its internal calculation may be proprietary.",
        "raw": "Direct live measurement from the active sensor source.",
        "use_load": "Useful for comparing training load and accumulated exercise stress over time.",
        "use_intensity": "Useful for understanding current cardiovascular exercise intensity.",
        "use_threshold": "Useful for comparing current or completed-workout effort with your configured physiological/performance threshold.",
        "use_recovery": "Useful for describing how quickly heart rate falls after exercise.",
        "use_efficiency": "Useful for following the relationship between external work and cardiovascular response.",
        "use_baseline": "Useful for comparing this result with your own recent history rather than a population cutoff.",
        "use_general": "Useful as context for your fitness profile and workout evaluation.",
        "periodic": "Derived live values are refreshed from the canonical workout samples every 30 seconds.",
    },
    "el": {
        "calculated": "Υπολογίζεται από το Fitness από τα αναφερόμενα δεδομένα εισόδου.",
        "provider": "Παρέχεται από την επιλεγμένη ενσωμάτωση fitness· ο εσωτερικός υπολογισμός της μπορεί να είναι ιδιόκτητος.",
        "raw": "Άμεση ζωντανή μέτρηση από την ενεργή πηγή αισθητήρα.",
        "use_load": "Χρήσιμο για σύγκριση προπονητικού φορτίου και συσσωρευμένης επιβάρυνσης με τον χρόνο.",
        "use_intensity": "Χρήσιμο για την κατανόηση της τρέχουσας καρδιαγγειακής έντασης της άσκησης.",
        "use_threshold": "Χρήσιμο για σύγκριση της προσπάθειας με το ρυθμισμένο φυσιολογικό ή αγωνιστικό κατώφλι.",
        "use_recovery": "Χρήσιμο για να περιγράφει πόσο γρήγορα πέφτει ο καρδιακός ρυθμός μετά την άσκηση.",
        "use_efficiency": "Χρήσιμο για παρακολούθηση της σχέσης εξωτερικού έργου και καρδιαγγειακής απόκρισης.",
        "use_baseline": "Χρήσιμο για σύγκριση με το δικό σου πρόσφατο ιστορικό και όχι με γενικό όριο πληθυσμού.",
        "use_general": "Χρήσιμο ως πλαίσιο για το προφίλ φυσικής κατάστασης και την αξιολόγηση της προπόνησης.",
        "periodic": "Οι παράγωγες ζωντανές τιμές ανανεώνονται από τα κανονικοποιημένα δείγματα προπόνησης κάθε 30 δευτερόλεπτα.",
    },
    "de": {
        "calculated": "Wird von Fitness aus den aufgeführten Eingabewerten berechnet.",
        "provider": "Wird von der gewählten Fitness-Integration geliefert; deren interne Berechnung kann proprietär sein.",
        "raw": "Direkte Live-Messung von der aktuell verwendeten Sensorquelle.",
        "use_load": "Nützlich zum Vergleich von Trainingsbelastung und kumulierter Belastung über die Zeit.",
        "use_intensity": "Nützlich zur Einschätzung der aktuellen kardiovaskulären Trainingsintensität.",
        "use_threshold": "Nützlich zum Vergleich der Belastung mit deinem konfigurierten physiologischen oder Leistungs-Schwellenwert.",
        "use_recovery": "Nützlich zur Beschreibung, wie schnell die Herzfrequenz nach Belastungsende sinkt.",
        "use_efficiency": "Nützlich zur Beobachtung des Verhältnisses von äußerer Leistung und kardiovaskulärer Reaktion.",
        "use_baseline": "Nützlich für den Vergleich mit deiner eigenen jüngeren Historie statt mit einem Bevölkerungsgrenzwert.",
        "use_general": "Nützlich als Kontext für Fitnessprofil und Trainingsauswertung.",
        "periodic": "Abgeleitete Live-Werte werden alle 30 Sekunden aus den kanonischen Trainingsdaten aktualisiert.",
    },
    "fr": {
        "calculated": "Calculé par Fitness à partir des données d'entrée indiquées.",
        "provider": "Fourni par l'intégration fitness sélectionnée ; son calcul interne peut être propriétaire.",
        "raw": "Mesure en direct provenant de la source de capteur active.",
        "use_load": "Utile pour comparer la charge d'entraînement et le stress cumulé dans le temps.",
        "use_intensity": "Utile pour comprendre l'intensité cardiovasculaire actuelle de l'exercice.",
        "use_threshold": "Utile pour comparer l'effort au seuil physiologique ou de performance configuré.",
        "use_recovery": "Utile pour décrire la vitesse de baisse de la fréquence cardiaque après l'exercice.",
        "use_efficiency": "Utile pour suivre la relation entre travail externe et réponse cardiovasculaire.",
        "use_baseline": "Utile pour comparer le résultat à ton historique récent plutôt qu'à un seuil de population.",
        "use_general": "Utile comme contexte pour le profil fitness et l'évaluation de l'entraînement.",
        "periodic": "Les valeurs live dérivées sont recalculées toutes les 30 secondes.",
    },
    "es": {
        "calculated": "Calculado por Fitness a partir de las entradas indicadas.",
        "provider": "Proporcionado por la integración de fitness seleccionada; su cálculo interno puede ser propietario.",
        "raw": "Medición en vivo directa de la fuente de sensor activa.",
        "use_load": "Útil para comparar la carga de entrenamiento y el estrés acumulado con el tiempo.",
        "use_intensity": "Útil para comprender la intensidad cardiovascular actual del ejercicio.",
        "use_threshold": "Útil para comparar el esfuerzo con tu umbral fisiológico o de rendimiento configurado.",
        "use_recovery": "Útil para describir la rapidez con la que baja la frecuencia cardíaca después del ejercicio.",
        "use_efficiency": "Útil para seguir la relación entre trabajo externo y respuesta cardiovascular.",
        "use_baseline": "Útil para comparar el resultado con tu propio historial reciente.",
        "use_general": "Útil como contexto para el perfil de fitness y la evaluación del entrenamiento.",
        "periodic": "Los valores derivados en vivo se actualizan cada 30 segundos.",
    },
    "it": {
        "calculated": "Calcolato da Fitness dagli input indicati.",
        "provider": "Fornito dall'integrazione fitness selezionata; il calcolo interno può essere proprietario.",
        "raw": "Misurazione live diretta dalla sorgente sensore attiva.",
        "use_load": "Utile per confrontare carico di allenamento e stress accumulato nel tempo.",
        "use_intensity": "Utile per comprendere l'intensità cardiovascolare attuale.",
        "use_threshold": "Utile per confrontare lo sforzo con la soglia fisiologica o prestativa configurata.",
        "use_recovery": "Utile per descrivere quanto rapidamente scende la frequenza cardiaca dopo l'esercizio.",
        "use_efficiency": "Utile per seguire la relazione tra lavoro esterno e risposta cardiovascolare.",
        "use_baseline": "Utile per confrontare il risultato con la tua storia recente.",
        "use_general": "Utile come contesto per profilo fitness e valutazione dell'allenamento.",
        "periodic": "I valori live derivati vengono aggiornati ogni 30 secondi.",
    },
    "pt": {
        "calculated": "Calculado pelo Fitness a partir dos dados indicados.",
        "provider": "Fornecido pela integração fitness selecionada; o cálculo interno pode ser proprietário.",
        "raw": "Medição em direto da fonte de sensor ativa.",
        "use_load": "Útil para comparar carga de treino e esforço acumulado ao longo do tempo.",
        "use_intensity": "Útil para compreender a intensidade cardiovascular atual do exercício.",
        "use_threshold": "Útil para comparar o esforço com o limiar fisiológico ou de desempenho configurado.",
        "use_recovery": "Útil para descrever a rapidez da queda da frequência cardíaca após o exercício.",
        "use_efficiency": "Útil para acompanhar a relação entre trabalho externo e resposta cardiovascular.",
        "use_baseline": "Útil para comparar o resultado com o teu próprio histórico recente.",
        "use_general": "Útil como contexto para o perfil fitness e avaliação do treino.",
        "periodic": "Os valores derivados em direto são atualizados a cada 30 segundos.",
    },
    "nl": {
        "calculated": "Door Fitness berekend uit de vermelde invoerwaarden.",
        "provider": "Geleverd door de gekozen fitnessintegratie; de interne berekening kan eigendomsspecifiek zijn.",
        "raw": "Directe livemeting van de actieve sensorbron.",
        "use_load": "Nuttig om trainingsbelasting en opgebouwde belasting door de tijd te vergelijken.",
        "use_intensity": "Nuttig om de actuele cardiovasculaire trainingsintensiteit te begrijpen.",
        "use_threshold": "Nuttig om inspanning te vergelijken met je ingestelde fysiologische of prestatiedrempel.",
        "use_recovery": "Nuttig om te beschrijven hoe snel de hartslag na inspanning daalt.",
        "use_efficiency": "Nuttig om de relatie tussen extern werk en cardiovasculaire respons te volgen.",
        "use_baseline": "Nuttig om het resultaat met je eigen recente historie te vergelijken.",
        "use_general": "Nuttig als context voor fitnessprofiel en trainingsevaluatie.",
        "periodic": "Afgeleide livewaarden worden elke 30 seconden bijgewerkt.",
    },
    "pl": {
        "calculated": "Obliczane przez Fitness na podstawie wskazanych danych wejściowych.",
        "provider": "Dostarczane przez wybraną integrację fitness; jej obliczenia mogą być własnościowe.",
        "raw": "Bezpośredni pomiar na żywo z aktywnego źródła czujnika.",
        "use_load": "Przydatne do porównywania obciążenia treningowego w czasie.",
        "use_intensity": "Przydatne do oceny aktualnej intensywności wysiłku sercowo-naczyniowego.",
        "use_threshold": "Przydatne do porównania wysiłku z ustawionym progiem fizjologicznym lub wydolnościowym.",
        "use_recovery": "Przydatne do opisu szybkości spadku tętna po wysiłku.",
        "use_efficiency": "Przydatne do śledzenia relacji pracy zewnętrznej i odpowiedzi sercowo-naczyniowej.",
        "use_baseline": "Przydatne do porównania wyniku z własną niedawną historią.",
        "use_general": "Przydatne jako kontekst profilu fitness i oceny treningu.",
        "periodic": "Pochodne wartości na żywo są aktualizowane co 30 sekund.",
    },
    "ru": {
        "calculated": "Рассчитывается Fitness по указанным входным данным.",
        "provider": "Предоставляется выбранной фитнес-интеграцией; внутренний расчёт может быть закрытым.",
        "raw": "Прямое живое измерение от активного источника датчика.",
        "use_load": "Полезно для сравнения тренировочной нагрузки во времени.",
        "use_intensity": "Полезно для оценки текущей сердечно-сосудистой интенсивности.",
        "use_threshold": "Полезно для сравнения усилия с настроенным физиологическим или мощностным порогом.",
        "use_recovery": "Полезно для описания скорости снижения пульса после нагрузки.",
        "use_efficiency": "Полезно для отслеживания связи внешней работы и сердечно-сосудистой реакции.",
        "use_baseline": "Полезно для сравнения результата с собственной недавней историей.",
        "use_general": "Полезно как контекст для фитнес-профиля и оценки тренировки.",
        "periodic": "Производные живые значения обновляются каждые 30 секунд.",
    },
    "uk": {
        "calculated": "Розраховується Fitness із зазначених вхідних даних.",
        "provider": "Надається вибраною фітнес-інтеграцією; внутрішній розрахунок може бути закритим.",
        "raw": "Пряме живе вимірювання з активного джерела датчика.",
        "use_load": "Корисно для порівняння тренувального навантаження з часом.",
        "use_intensity": "Корисно для оцінки поточної серцево-судинної інтенсивності.",
        "use_threshold": "Корисно для порівняння з налаштованим фізіологічним або продуктивним порогом.",
        "use_recovery": "Корисно для опису швидкості падіння пульсу після навантаження.",
        "use_efficiency": "Корисно для відстеження зв’язку зовнішньої роботи та серцево-судинної реакції.",
        "use_baseline": "Корисно для порівняння з власною недавньою історією.",
        "use_general": "Корисно як контекст профілю та оцінки тренування.",
        "periodic": "Похідні живі значення оновлюються кожні 30 секунд.",
    },
    "tr": {
        "calculated": "Fitness tarafından belirtilen girdilerden hesaplanır.",
        "provider": "Seçilen fitness entegrasyonu tarafından sağlanır; iç hesaplama özel olabilir.",
        "raw": "Etkin sensör kaynağından doğrudan canlı ölçüm.",
        "use_load": "Antrenman yükünü zaman içinde karşılaştırmak için kullanışlıdır.",
        "use_intensity": "Mevcut kardiyovasküler egzersiz yoğunluğunu anlamak için kullanışlıdır.",
        "use_threshold": "Eforu yapılandırılmış fizyolojik veya performans eşiğiyle karşılaştırmak için kullanışlıdır.",
        "use_recovery": "Egzersiz sonrası kalp hızının ne kadar hızlı düştüğünü açıklamak için kullanışlıdır.",
        "use_efficiency": "Dış iş ile kardiyovasküler yanıt arasındaki ilişkiyi izlemek için kullanışlıdır.",
        "use_baseline": "Sonucu kendi yakın geçmişinle karşılaştırmak için kullanışlıdır.",
        "use_general": "Fitness profili ve antrenman değerlendirmesi için bağlam sağlar.",
        "periodic": "Türetilmiş canlı değerler her 30 saniyede yenilenir.",
    },
    "zh": {
        "calculated": "由 Fitness 根据列出的输入数据计算。",
        "provider": "由所选健身集成提供；其内部计算可能是专有的。",
        "raw": "来自当前活动传感器源的实时直接测量。",
        "use_load": "用于比较随时间变化的训练负荷和累积压力。",
        "use_intensity": "用于了解当前心血管运动强度。",
        "use_threshold": "用于将当前或已完成训练的强度与设定阈值比较。",
        "use_recovery": "用于描述运动后心率下降的速度。",
        "use_efficiency": "用于观察外部功与心血管反应之间的关系。",
        "use_baseline": "用于与个人近期历史而非人群阈值比较。",
        "use_general": "用于提供健身档案和训练评估背景。",
        "periodic": "派生实时值每30秒更新一次。",
    },
    "ja": {
        "calculated": "Fitness が記載された入力値から計算します。",
        "provider": "選択したフィットネス統合から提供され、内部計算は独自方式の場合があります。",
        "raw": "現在のアクティブなセンサーソースからの直接ライブ測定です。",
        "use_load": "時間経過に伴うトレーニング負荷の比較に役立ちます。",
        "use_intensity": "現在の心血管運動強度の把握に役立ちます。",
        "use_threshold": "運動強度を設定した生理学的・パフォーマンス閾値と比較するのに役立ちます。",
        "use_recovery": "運動後に心拍数がどれだけ速く低下するかの把握に役立ちます。",
        "use_efficiency": "外的仕事量と心血管反応の関係を追跡するのに役立ちます。",
        "use_baseline": "一般集団ではなく自分自身の最近の履歴との比較に役立ちます。",
        "use_general": "フィットネスプロフィールとワークアウト評価の背景情報になります。",
        "periodic": "派生ライブ値は30秒ごとに更新されます。",
    },
    "ko": {
        "calculated": "Fitness가 표시된 입력값으로 계산합니다.",
        "provider": "선택한 피트니스 통합에서 제공하며 내부 계산은 독점 방식일 수 있습니다.",
        "raw": "현재 활성 센서 소스의 직접 실시간 측정입니다.",
        "use_load": "시간에 따른 훈련 부하와 누적 스트레스를 비교하는 데 유용합니다.",
        "use_intensity": "현재 심혈관 운동 강도를 이해하는 데 유용합니다.",
        "use_threshold": "운동 강도를 설정된 생리학적 또는 성능 임계값과 비교하는 데 유용합니다.",
        "use_recovery": "운동 후 심박수가 얼마나 빠르게 감소하는지 설명하는 데 유용합니다.",
        "use_efficiency": "외부 작업과 심혈관 반응의 관계를 추적하는 데 유용합니다.",
        "use_baseline": "집단 기준보다 자신의 최근 기록과 비교하는 데 유용합니다.",
        "use_general": "피트니스 프로필과 운동 평가의 배경 정보로 유용합니다.",
        "periodic": "파생 실시간 값은 30초마다 갱신됩니다.",
    },
}

_METHODS = {
    "heart_rate_percent_max": ("%HRmax", "heart_rate / maximum_heart_rate × 100", ["heart_rate", "maximum_heart_rate"], "use_intensity"),
    "heart_rate_reserve_percent": ("Karvonen/ACSM %HRR", "(heart_rate − resting_hr) / (maximum_hr − resting_hr) × 100", ["heart_rate", "resting_hr", "maximum_hr"], "use_intensity"),
    "heart_rate_intensity": ("ACSM %HRR", "%HRR → ACSM intensity band", ["heart_rate", "resting_hr", "maximum_hr"], "use_intensity"),
    "heart_rate_relative_threshold": ("HR / threshold_HR", "heart_rate / threshold_heart_rate × 100", ["heart_rate", "threshold_heart_rate"], "use_threshold"),
    "current_power_to_weight": ("W/kg", "power_w / body_mass_kg", ["power", "weight"], "use_threshold"),
    "power_relative_threshold": ("power / threshold_power", "power / configured_threshold_power × 100", ["power", "threshold_power"], "use_threshold"),
    "current_pace": ("pace(speed)", "60 / speed_km_h", ["speed"], "use_threshold"),
    "speed_relative_threshold": ("speed / threshold_speed", "speed / threshold_speed × 100", ["speed", "threshold_pace"], "use_threshold"),
    "live_banister_trimp": ("Banister TRIMP", "duration_min × fractional_HRR × Banister_weighting(fractional_HRR, sex)", ["duration", "heart_rate", "resting_hr", "maximum_hr", "sex"], "use_load"),
    "last_workout_banister_trimp": ("Banister TRIMP", "duration_min × fractional_HRR × Banister_weighting(fractional_HRR, sex)", ["duration", "heart_rate", "resting_hr", "maximum_hr", "sex"], "use_load"),
    "last_workout_trimp_per_hour": ("Banister TRIMP/h", "Banister_TRIMP / workout_duration_hours", ["banister_trimp", "duration"], "use_load"),
    "live_mechanical_work": ("∫ power dt", "Σ((power_a + power_b) / 2 × Δt) / 1000", ["power", "time"], "use_load"),
    "last_workout_mechanical_work": ("∫ power dt", "Σ((power_a + power_b) / 2 × Δt) / 1000", ["power", "time"], "use_load"),
    "live_aerobic_efficiency": ("aerobic_efficiency", "mean(power / heart_rate) when power is available; otherwise mean(speed / heart_rate)", ["heart_rate", "power_or_speed"], "use_efficiency"),
    "last_workout_aerobic_efficiency": ("aerobic_efficiency", "mean(power / heart_rate) when power is available; otherwise mean(speed / heart_rate)", ["heart_rate", "power_or_speed"], "use_efficiency"),
    "live_aerobic_decoupling": ("aerobic_decoupling", "(first_half_efficiency − second_half_efficiency) / first_half_efficiency × 100", ["heart_rate", "power_or_speed", "time"], "use_efficiency"),
    "last_workout_aerobic_decoupling": ("aerobic_decoupling", "(first_half_efficiency − second_half_efficiency) / first_half_efficiency × 100", ["heart_rate", "power_or_speed", "time"], "use_efficiency"),
    "last_workout_hrr_10s": ("HRR", "end_exercise_hr − heart_rate_at_10s", ["end_heart_rate", "heart_rate_10s"], "use_recovery"),
    "last_workout_hrr_30s": ("HRR", "end_exercise_hr − heart_rate_at_30s", ["end_heart_rate", "heart_rate_30s"], "use_recovery"),
    "last_workout_hrr_60s": ("HRR", "end_exercise_hr − heart_rate_at_60s", ["end_heart_rate", "heart_rate_60s"], "use_recovery"),
    "last_workout_hrr_120s": ("HRR", "end_exercise_hr − heart_rate_at_120s", ["end_heart_rate", "heart_rate_120s"], "use_recovery"),
    "hrr_60s_long_term": ("personal_HRR_baseline", "summary(recent workout_hrr_60s values in personal history window)", ["last_workout_hrr_60s", "history"], "use_baseline"),
    "aerobic_decoupling_long_term": ("personal_aerobic_decoupling_baseline", "summary(recent aerobic_decoupling values in personal history window)", ["workout_decoupling", "history"], "use_baseline"),
    "aerobic_efficiency_long_term": ("personal_aerobic_efficiency_baseline", "summary(recent aerobic_efficiency values in personal history window)", ["workout_efficiency", "history"], "use_baseline"),
    "friend_predicted_vo2max": ("Friend et al. 2017 VO₂max reference equation", "Friend_et_al_2017_reference(age, sex)", ["age", "sex"], "use_general"),
    "vo2max_percent_predicted": ("% predicted VO₂max", "measured_or_provider_vo2max / predicted_reference_vo2max × 100", ["vo2max", "predicted_vo2max"], "use_general"),
    "heart_rate_reserve": ("HRR reserve", "maximum_heart_rate − resting_heart_rate", ["maximum_hr", "resting_hr"], "use_intensity"),
    "threshold_power_to_weight": ("threshold W/kg", "threshold_power_w / body_mass_kg", ["threshold_power", "weight"], "use_threshold"),
    "training_load_7d": ("rolling Banister TRIMP", "Σ(workout_Banister_TRIMP over previous 7 days)", ["workout_trimp", "history"], "use_load"),
    "training_load_28d": ("rolling Banister TRIMP", "Σ(workout_Banister_TRIMP over previous 28 days)", ["workout_trimp", "history"], "use_load"),
    "training_load_42d": ("rolling Banister TRIMP", "Σ(workout_Banister_TRIMP over previous 42 days)", ["workout_trimp", "history"], "use_load"),
}


def sensor_explanation(
    language: str | None,
    kind: str,
    metric: str,
    *,
    calculated: bool = True,
) -> dict:
    """Return fixed localized explanatory attributes for a sensor."""
    code = str(language or "en").lower().split("-")[0].split("_")[0]
    text = _LANGUAGE_TEXT.get(code, _LANGUAGE_TEXT["en"])

    method = _METHODS.get(metric)
    if method:
        method_name, calculation, inputs, useful_key = method
        result = {
            "method": method_name,
            "calculation": calculation,
            "inputs": inputs,
            "useful_for": text[useful_key],
            "explanation": text["calculated"],
        }
    else:
        result = {
            "method": (
                "Provider / imported metric"
                if kind == "workout"
                else "Fitness deterministic evaluation"
            ),
            "calculation": (
                text["provider"]
                if kind == "workout"
                else text["calculated"]
            ),
            "inputs": [],
            "useful_for": text["use_general"],
            "explanation": (
                text["provider"]
                if kind == "workout"
                else text["calculated"]
            ),
        }

    if kind == "live" and metric.startswith("live_"):
        result["update_policy"] = text["periodic"]

    return result
