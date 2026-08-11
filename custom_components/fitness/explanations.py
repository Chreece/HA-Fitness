"""Localized deterministic explanations for Fitness sensor calculations.

This module is intentionally AI-free. Entity metadata must remain fast, stable,
reproducible, and independent of any LLM/provider response.
"""

from __future__ import annotations

# Method names remain scientific/protocol names. User-facing prose is localized.
_LANGUAGE_TEXT = {
    "en": {
        "calculated": "Calculated by Fitness from the listed inputs.",
        "provider": "Imported from the selected fitness integration. The concrete Home Assistant source is listed below; Fitness does not invent a formula for a provider-proprietary metric.",
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
        "calculated": "Υπολογίζεται ντετερμινιστικά από το Fitness. Παρακάτω εμφανίζονται ο τύπος και οι συγκεκριμένες πηγές δεδομένων που χρησιμοποιήθηκαν.",
        "provider": "Εισάγεται από την επιλεγμένη ενσωμάτωση fitness. Η συγκεκριμένη πηγή Home Assistant εμφανίζεται παρακάτω και το Fitness δεν επινοεί τύπο για ιδιόκτητο υπολογισμό παρόχου.",
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
        "calculated": "Wird von Fitness deterministisch berechnet. Die Formel und die tatsächlich verwendeten Eingabequellen sind unten aufgeführt.",
        "provider": "Wird aus der gewählten Fitness-Integration importiert. Die konkrete Home-Assistant-Quelle ist unten aufgeführt; Fitness erfindet keine Formel für proprietäre Anbieterberechnungen.",
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
    "training_load_change_7_vs_28": ("recent load vs 28-day baseline", "(TRIMP_7d/7 − TRIMP_28d/28) / (TRIMP_28d/28) × 100", ["workout_trimp", "history"], "use_load"),
    "hrr_60s_vs_90d": ("HRR personal baseline comparison", "latest_HRR60 − prior_90d_mean_HRR60", ["last_workout_hrr_60s", "history"], "use_recovery"),
    "sleep_duration_7d_mean": ("rolling sleep duration mean", "mean(merged sleep duration over previous 7 days; minimum 3 nights)", ["merged_sleep_duration", "sleep_history"], "use_baseline"),
    "sleep_duration_28d_mean": ("rolling sleep duration mean", "mean(merged sleep duration over previous 28 days; minimum 7 nights)", ["merged_sleep_duration", "sleep_history"], "use_baseline"),
    "sleep_duration_vs_28d": ("sleep duration personal baseline comparison", "last_sleep_duration − 28d_mean_sleep_duration", ["last_sleep_duration", "sleep_history"], "use_baseline"),
    "sleep_duration_shortfall": ("AASM/SRS adult sleep-duration minimum", "max(0, 420 min − last_sleep_duration_min)", ["last_sleep_duration", "age"], "use_general"),
    "sleep_midpoint_variability_14d": ("sleep timing variability", "population standard deviation of sleep midpoints over 14 days; minimum 5 timed nights", ["sleep_start", "sleep_end", "sleep_history"], "use_baseline"),
    "sleep_hrv_7d_mean": ("rolling nightly HRV mean", "mean(merged nightly HRV over previous 7 days; minimum 3 nights)", ["sleep_hrv", "sleep_history"], "use_baseline"),
    "sleep_hrv_28d_mean": ("rolling nightly HRV mean", "mean(merged nightly HRV over previous 28 days; minimum 7 nights)", ["sleep_hrv", "sleep_history"], "use_baseline"),
    "sleep_hrv_vs_28d": ("nightly HRV personal baseline comparison", "(last_sleep_HRV − 28d_mean_HRV) / 28d_mean_HRV × 100", ["sleep_hrv", "sleep_history"], "use_baseline"),
    "resting_hr_7d_mean": ("Recorder resting-HR trend", "mean(daily resting-HR statistics over up to 7 days)", ["resting_hr_entity", "recorder_statistics"], "use_baseline"),
    "resting_hr_28d_mean": ("Recorder resting-HR baseline", "mean(daily resting-HR statistics over up to 28 days)", ["resting_hr_entity", "recorder_statistics"], "use_baseline"),
    "resting_hr_vs_28d": ("resting-HR personal baseline comparison", "current_resting_HR − 28d_mean_resting_HR", ["resting_hr", "recorder_statistics"], "use_baseline"),
    "vo2max_28d_mean": ("Recorder VO₂max trend", "mean(daily provider/user VO₂max statistics over up to 28 days)", ["vo2max_entity", "recorder_statistics"], "use_general"),
    "vo2max_trend_14_vs_previous_14": ("VO₂max longitudinal trend", "(mean(last14d) − mean(previous14d)) / mean(previous14d) × 100", ["vo2max_entity", "recorder_statistics"], "use_general"),
    "training_load_42d": ("rolling Banister TRIMP", "Σ(workout_Banister_TRIMP over previous 42 days)", ["workout_trimp", "history"], "use_load"),
    "age": ("Profile age", "current_date − configured_date_of_birth", ["birth_day", "birth_month", "birth_year"], "use_general"),
    "weight": ("Direct profile/provider body mass", "No Fitness formula; normalized source value is used directly.", ["weight_source"], "use_general"),
    "resting_hr": ("Direct profile/provider resting HR", "No Fitness formula; normalized source value is used directly.", ["resting_hr_source"], "use_general"),
    "max_hr": ("Maximum heart-rate selection", "configured_max_hr; otherwise Tanaka_2001(208 − 0.7 × age); an observed workout peak may replace a lower estimate", ["configured_max_hr", "age", "latest_workout_max_hr"], "use_intensity"),
    "vo2max": ("VO₂max source selection", "provider_or_configured_vo2max; otherwise Uth_2004 = 15.3 × maximum_hr / resting_hr", ["vo2max_source", "maximum_hr", "resting_hr"], "use_general"),
    "cardiorespiratory_status": ("Percent-predicted VO₂max display classification", "classify(vo2max / FRIEND_predicted_vo2max × 100) into display bands", ["vo2max", "friend_predicted_vo2max"], "use_general"),
    "hrv_weekly": ("Provider HRV weekly value", "No Fitness formula; provider value is used directly.", ["provider_hrv_weekly_entity"], "use_baseline"),
    "hrv_last_night": ("Provider nightly HRV value", "No Fitness formula; provider value is used directly.", ["provider_hrv_last_night_entity"], "use_baseline"),
    "hrv_status": ("Personal HRV baseline comparison", "nightly_hrv compared with provider baseline_low and baseline_high", ["hrv_last_night", "hrv_baseline_low", "hrv_baseline_high"], "use_baseline"),
    "threshold_hr": ("Heart-rate threshold source", "No Fitness physiological estimation; exact configured/provider threshold HR is used.", ["threshold_hr_source"], "use_threshold"),
    "threshold_pace": ("Threshold pace source/conversion", "configured_pace; otherwise 1000 / provider_threshold_speed_m_s / 60", ["threshold_pace_source_or_threshold_speed_entity"], "use_threshold"),
    "threshold_power": ("Threshold power source", "No Fitness physiological estimation; configured threshold power or provider running FTP is used.", ["threshold_power_source"], "use_threshold"),
    "power_to_weight": ("Threshold power-to-weight", "threshold_power_w / body_mass_kg unless provider supplies an explicit running power-to-weight value", ["threshold_power", "weight"], "use_threshold"),
    "fitness_age": ("Provider fitness age", "No Fitness formula; provider fitness-age value is used directly.", ["provider_fitness_age_entity"], "use_general"),
    "fitness_age_difference": ("Fitness-age difference", "provider_fitness_age − chronological_profile_age", ["fitness_age", "age"], "use_general"),
    "training_readiness": ("Provider training readiness", "No Fitness formula; provider value is exposed as context.", ["provider_training_readiness_entity"], "use_general"),
    "sleep_score": ("Provider sleep score", "No Fitness formula; provider value is exposed as context.", ["provider_sleep_score_entity"], "use_general"),
    "acute_load": ("Provider acute training load", "No Fitness formula when supplied by provider; value is read from provider training-status data.", ["provider_training_status_entity"], "use_load"),
    "chronic_load": ("Provider chronic training load", "No Fitness formula when supplied by provider; value is read from provider training-status data.", ["provider_training_status_entity"], "use_load"),
    "acute_chronic_ratio": ("Acute:chronic workload ratio", "provider_ratio; otherwise acute_training_load / chronic_training_load", ["acute_load", "chronic_load"], "use_load"),
    "provider_training_status": ("Provider training status", "No Fitness formula; provider status text is exposed as context.", ["provider_training_status_entity"], "use_general"),
    "training_days_28d": ("Active training days", "count(unique calendar days containing a completed workout during previous 28 days)", ["fitness_workout_history"], "use_load"),
}


_PROVENANCE_TEXT = {'en': {'calculated': 'Calculated by Fitness', 'direct': 'Direct source value', 'provider': 'Provider value', 'history': 'Workout-history calculation', 'profile': 'Profile configuration', 'sources': 'Data sources used', 'why': 'Why this is useful', 'caveat': 'Scientific note', 'provider_note': "This value comes from the fitness provider. Fitness does not recreate or claim the provider's internal algorithm.", 'history_note': 'This value is calculated from completed workout history.', 'direct_note': 'This value is used directly after unit normalization; Fitness does not estimate it.'}, 'el': {'calculated': 'Υπολογισμός από το Fitness', 'direct': 'Άμεση τιμή πηγής', 'provider': 'Τιμή παρόχου', 'history': 'Υπολογισμός από το ιστορικό προπονήσεων', 'profile': 'Ρύθμιση προφίλ', 'sources': 'Πηγές δεδομένων που χρησιμοποιήθηκαν', 'why': 'Γιατί είναι χρήσιμο', 'caveat': 'Επιστημονική σημείωση', 'provider_note': 'Η τιμή προέρχεται από τον πάροχο fitness. Το Fitness δεν αναπαράγει ούτε ισχυρίζεται ότι γνωρίζει τον εσωτερικό αλγόριθμο του παρόχου.', 'history_note': 'Η τιμή υπολογίζεται από το ιστορικό ολοκληρωμένων προπονήσεων.', 'direct_note': 'Η τιμή χρησιμοποιείται άμεσα μετά την κανονικοποίηση της μονάδας· το Fitness δεν την εκτιμά.'}, 'de': {'calculated': 'Von Fitness berechnet', 'direct': 'Direkter Quellwert', 'provider': 'Anbieterwert', 'history': 'Berechnung aus dem Trainingsverlauf', 'profile': 'Profilkonfiguration', 'sources': 'Verwendete Datenquellen', 'why': 'Warum dieser Wert nützlich ist', 'caveat': 'Wissenschaftlicher Hinweis', 'provider_note': 'Dieser Wert stammt vom Fitness-Anbieter. Fitness bildet dessen internen Algorithmus nicht nach und erhebt keinen Anspruch darauf.', 'history_note': 'Dieser Wert wird aus dem Verlauf abgeschlossener Trainings berechnet.', 'direct_note': 'Dieser Wert wird nach der Einheiten-Normalisierung direkt verwendet; Fitness schätzt ihn nicht.'}, 'fr': {'calculated': 'Calculé par Fitness', 'direct': 'Valeur directe de la source', 'provider': 'Valeur du fournisseur', 'history': 'Calcul à partir de l’historique des entraînements', 'profile': 'Configuration du profil', 'sources': 'Sources de données utilisées', 'why': 'Pourquoi cette valeur est utile', 'caveat': 'Note scientifique', 'provider_note': 'Cette valeur provient du fournisseur fitness. Fitness ne reproduit pas et ne prétend pas connaître son algorithme interne.', 'history_note': 'Cette valeur est calculée à partir de l’historique des entraînements terminés.', 'direct_note': 'Cette valeur est utilisée directement après normalisation de l’unité ; Fitness ne l’estime pas.'}, 'es': {'calculated': 'Calculado por Fitness', 'direct': 'Valor directo de la fuente', 'provider': 'Valor del proveedor', 'history': 'Cálculo del historial de entrenamientos', 'profile': 'Configuración del perfil', 'sources': 'Fuentes de datos utilizadas', 'why': 'Por qué es útil', 'caveat': 'Nota científica', 'provider_note': 'Este valor procede del proveedor de fitness. Fitness no reproduce ni afirma conocer el algoritmo interno del proveedor.', 'history_note': 'Este valor se calcula a partir del historial de entrenamientos completados.', 'direct_note': 'Este valor se usa directamente tras normalizar la unidad; Fitness no lo estima.'}, 'it': {'calculated': 'Calcolato da Fitness', 'direct': 'Valore diretto della fonte', 'provider': 'Valore del provider', 'history': 'Calcolo dallo storico degli allenamenti', 'profile': 'Configurazione del profilo', 'sources': 'Fonti dati utilizzate', 'why': 'Perché è utile', 'caveat': 'Nota scientifica', 'provider_note': 'Questo valore proviene dal provider fitness. Fitness non ricrea né dichiara di conoscere l’algoritmo interno del provider.', 'history_note': 'Questo valore viene calcolato dallo storico degli allenamenti completati.', 'direct_note': 'Questo valore viene usato direttamente dopo la normalizzazione dell’unità; Fitness non lo stima.'}, 'pt': {'calculated': 'Calculado pelo Fitness', 'direct': 'Valor direto da fonte', 'provider': 'Valor do fornecedor', 'history': 'Cálculo do histórico de treinos', 'profile': 'Configuração do perfil', 'sources': 'Fontes de dados utilizadas', 'why': 'Por que é útil', 'caveat': 'Nota científica', 'provider_note': 'Este valor vem do fornecedor de fitness. O Fitness não recria nem afirma conhecer o algoritmo interno do fornecedor.', 'history_note': 'Este valor é calculado a partir do histórico de treinos concluídos.', 'direct_note': 'Este valor é usado diretamente após a normalização da unidade; o Fitness não o estima.'}, 'nl': {'calculated': 'Berekend door Fitness', 'direct': 'Directe bronwaarde', 'provider': 'Waarde van provider', 'history': 'Berekening uit trainingsgeschiedenis', 'profile': 'Profielconfiguratie', 'sources': 'Gebruikte gegevensbronnen', 'why': 'Waarom dit nuttig is', 'caveat': 'Wetenschappelijke opmerking', 'provider_note': 'Deze waarde komt van de fitnessprovider. Fitness reconstrueert de interne algoritmen van de provider niet en claimt deze niet te kennen.', 'history_note': 'Deze waarde wordt berekend uit de geschiedenis van voltooide trainingen.', 'direct_note': 'Deze waarde wordt na eenheidsnormalisatie direct gebruikt; Fitness schat deze niet.'}, 'pl': {'calculated': 'Obliczone przez Fitness', 'direct': 'Bezpośrednia wartość źródłowa', 'provider': 'Wartość dostawcy', 'history': 'Obliczenie z historii treningów', 'profile': 'Konfiguracja profilu', 'sources': 'Użyte źródła danych', 'why': 'Dlaczego jest przydatne', 'caveat': 'Uwaga naukowa', 'provider_note': 'Ta wartość pochodzi od dostawcy fitness. Fitness nie odtwarza ani nie twierdzi, że zna jego wewnętrzny algorytm.', 'history_note': 'Ta wartość jest obliczana na podstawie historii ukończonych treningów.', 'direct_note': 'Ta wartość jest używana bezpośrednio po normalizacji jednostki; Fitness jej nie szacuje.'}, 'ru': {'calculated': 'Рассчитано Fitness', 'direct': 'Прямое значение источника', 'provider': 'Значение провайдера', 'history': 'Расчёт по истории тренировок', 'profile': 'Настройка профиля', 'sources': 'Использованные источники данных', 'why': 'Для чего это полезно', 'caveat': 'Научное примечание', 'provider_note': 'Это значение получено от фитнес-провайдера. Fitness не воспроизводит и не заявляет о знании внутреннего алгоритма провайдера.', 'history_note': 'Это значение рассчитывается по истории завершённых тренировок.', 'direct_note': 'Это значение используется напрямую после нормализации единиц; Fitness его не оценивает.'}, 'uk': {'calculated': 'Розраховано Fitness', 'direct': 'Пряме значення джерела', 'provider': 'Значення провайдера', 'history': 'Розрахунок з історії тренувань', 'profile': 'Налаштування профілю', 'sources': 'Використані джерела даних', 'why': 'Чому це корисно', 'caveat': 'Наукова примітка', 'provider_note': 'Це значення надходить від фітнес-провайдера. Fitness не відтворює і не стверджує, що знає внутрішній алгоритм провайдера.', 'history_note': 'Це значення розраховується з історії завершених тренувань.', 'direct_note': 'Це значення використовується безпосередньо після нормалізації одиниці; Fitness його не оцінює.'}, 'tr': {'calculated': 'Fitness tarafından hesaplandı', 'direct': 'Doğrudan kaynak değeri', 'provider': 'Sağlayıcı değeri', 'history': 'Antrenman geçmişinden hesaplama', 'profile': 'Profil yapılandırması', 'sources': 'Kullanılan veri kaynakları', 'why': 'Neden yararlıdır', 'caveat': 'Bilimsel not', 'provider_note': 'Bu değer fitness sağlayıcısından gelir. Fitness sağlayıcının dahili algoritmasını yeniden oluşturmaz veya bildiğini iddia etmez.', 'history_note': 'Bu değer tamamlanmış antrenman geçmişinden hesaplanır.', 'direct_note': 'Bu değer birim normalizasyonundan sonra doğrudan kullanılır; Fitness tarafından tahmin edilmez.'}, 'zh': {'calculated': '由 Fitness 计算', 'direct': '直接来源值', 'provider': '提供商值', 'history': '基于训练历史的计算', 'profile': '个人资料配置', 'sources': '使用的数据来源', 'why': '为什么有用', 'caveat': '科学说明', 'provider_note': '此值来自健身数据提供商。Fitness 不会重建或声称了解提供商的内部算法。', 'history_note': '此值根据已完成的训练历史计算。', 'direct_note': '此值在单位标准化后直接使用；Fitness 不对其进行估算。'}, 'ja': {'calculated': 'Fitness による計算', 'direct': '直接のソース値', 'provider': 'プロバイダー値', 'history': 'ワークアウト履歴からの計算', 'profile': 'プロフィール設定', 'sources': '使用したデータソース', 'why': 'この値が役立つ理由', 'caveat': '科学的注記', 'provider_note': 'この値はフィットネスプロバイダーから取得されます。Fitness はプロバイダー内部のアルゴリズムを再現したり、把握していると主張したりしません。', 'history_note': 'この値は完了したワークアウト履歴から計算されます。', 'direct_note': 'この値は単位を正規化した後に直接使用され、Fitness が推定するものではありません。'}, 'ko': {'calculated': 'Fitness에서 계산', 'direct': '직접 소스 값', 'provider': '제공자 값', 'history': '운동 기록 기반 계산', 'profile': '프로필 설정', 'sources': '사용된 데이터 소스', 'why': '이 값이 유용한 이유', 'caveat': '과학적 참고', 'provider_note': '이 값은 피트니스 제공자에서 가져옵니다. Fitness는 제공자의 내부 알고리즘을 재현하거나 알고 있다고 주장하지 않습니다.', 'history_note': '이 값은 완료된 운동 기록을 기반으로 계산됩니다.', 'direct_note': '이 값은 단위 정규화 후 직접 사용되며 Fitness가 추정하지 않습니다.'}}


def provenance_text(language: str, key: str) -> str:
    """Return deterministic localized evaluation provenance text."""
    lang = language if language in _PROVENANCE_TEXT else "en"
    return _PROVENANCE_TEXT[lang].get(key, _PROVENANCE_TEXT["en"].get(key, key))


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
