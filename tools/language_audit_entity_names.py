#!/usr/bin/env python3
"""Reviewed native names for compound Fitness entities.

The original catalogs contained partly translated combinations such as
``Letztes Training elevation gain``.  Keeping the metric and context wording
separate avoids repeating that failure when more compound entities are added.
"""

from __future__ import annotations

LANGUAGES = (
    "en", "el", "de", "fr", "es", "it", "pt", "nl",
    "pl", "ru", "uk", "tr", "zh", "ja", "ko",
)


def _row(*values: str) -> dict[str, str]:
    if len(values) != len(LANGUAGES):
        raise RuntimeError(f"Expected {len(LANGUAGES)} translations, got {len(values)}")
    if any(not value.strip() for value in values):
        raise RuntimeError("Entity translations must not be empty")
    return dict(zip(LANGUAGES, values, strict=True))


LAST_WORKOUT = _row(
    "Last workout {metric}", "{metric} της τελευταίας προπόνησης",
    "{metric} des letzten Trainings", "{metric} du dernier entraînement",
    "{metric} del último entrenamiento", "{metric} dell’ultimo allenamento",
    "{metric} do último treino", "{metric} van de laatste training",
    "{metric} z ostatniego treningu", "{metric} последней тренировки",
    "{metric} останнього тренування", "Son antrenman: {metric}",
    "上次训练：{metric}", "前回のワークアウト：{metric}", "마지막 운동: {metric}",
)

LIVE = _row(
    "Live {metric}", "Ζωντανά: {metric}", "Live: {metric}",
    "En direct : {metric}", "En vivo: {metric}", "In tempo reale: {metric}",
    "Em direto: {metric}", "Live: {metric}", "Na żywo: {metric}",
    "В реальном времени: {metric}", "Наживо: {metric}", "Canlı: {metric}",
    "实时：{metric}", "ライブ：{metric}", "실시간: {metric}",
)

LAST_SLEEP = _row(
    "Last sleep {metric}", "{metric} του τελευταίου ύπνου",
    "{metric} des letzten Schlafs", "{metric} du dernier sommeil",
    "{metric} del último sueño", "{metric} dell’ultimo sonno",
    "{metric} do último sono", "{metric} van de laatste slaap",
    "{metric} z ostatniego snu", "{metric} последнего сна",
    "{metric} останнього сну", "Son uyku: {metric}",
    "上次睡眠：{metric}", "前回の睡眠：{metric}", "마지막 수면: {metric}",
)


METRICS = {
    "distance": _row(
        "distance", "απόσταση", "Distanz", "distance", "distancia", "distanza",
        "distância", "afstand", "dystans", "дистанция", "дистанція", "mesafe",
        "距离", "距離", "거리",
    ),
    "average_heart_rate": _row(
        "average heart rate", "μέσος καρδιακός ρυθμός", "durchschnittliche Herzfrequenz",
        "fréquence cardiaque moyenne", "frecuencia cardíaca media", "frequenza cardiaca media",
        "frequência cardíaca média", "gemiddelde hartslag", "średnie tętno",
        "средний пульс", "середній пульс", "ortalama kalp hızı",
        "平均心率", "平均心拍数", "평균 심박수",
    ),
    "maximum_heart_rate": _row(
        "maximum heart rate", "μέγιστος καρδιακός ρυθμός", "maximale Herzfrequenz",
        "fréquence cardiaque maximale", "frecuencia cardíaca máxima", "frequenza cardiaca massima",
        "frequência cardíaca máxima", "maximale hartslag", "maksymalne tętno",
        "максимальный пульс", "максимальний пульс", "maksimum kalp hızı",
        "最大心率", "最大心拍数", "최대 심박수",
    ),
    "average_power": _row(
        "average power", "μέση ισχύς", "durchschnittliche Leistung", "puissance moyenne",
        "potencia media", "potenza media", "potência média", "gemiddeld vermogen",
        "średnia moc", "средняя мощность", "середня потужність", "ortalama güç",
        "平均功率", "平均パワー", "평균 파워",
    ),
    "maximum_power": _row(
        "maximum power", "μέγιστη ισχύς", "maximale Leistung", "puissance maximale",
        "potencia máxima", "potenza massima", "potência máxima", "maximaal vermogen",
        "maksymalna moc", "максимальная мощность", "максимальна потужність", "maksimum güç",
        "最大功率", "最大パワー", "최대 파워",
    ),
    "average_cadence": _row(
        "average cadence", "μέσος ρυθμός πεταλιάς", "durchschnittliche Kadenz", "cadence moyenne",
        "cadencia media", "cadenza media", "cadência média", "gemiddelde cadans",
        "średnia kadencja", "средний каденс", "середній каденс", "ortalama kadans",
        "平均踏频", "平均ケイデンス", "평균 케이던스",
    ),
    "maximum_cadence": _row(
        "maximum cadence", "μέγιστος ρυθμός πεταλιάς", "maximale Kadenz", "cadence maximale",
        "cadencia máxima", "cadenza massima", "cadência máxima", "maximale cadans",
        "maksymalna kadencja", "максимальный каденс", "максимальний каденс", "maksimum kadans",
        "最大踏频", "最大ケイデンス", "최대 케이던스",
    ),
    "elevation_gain": _row(
        "elevation gain", "υψομετρική ανάβαση", "Höhengewinn", "dénivelé positif",
        "desnivel positivo", "dislivello positivo", "ganho de elevação", "hoogtemeters",
        "przewyższenie", "набор высоты", "набір висоти", "irtifa kazanımı",
        "累计爬升", "獲得標高", "누적 상승고도",
    ),
    "elevation_loss": _row(
        "elevation loss", "υψομετρική κατάβαση", "Höhenverlust", "dénivelé négatif",
        "desnivel negativo", "dislivello negativo", "perda de elevação", "hoogteverlies",
        "utrata wysokości", "снижение высоты", "втрата висоти", "irtifa kaybı",
        "累计下降", "下降標高", "누적 하강고도",
    ),
    "moving_time": _row(
        "moving time", "χρόνος κίνησης", "Bewegungszeit", "temps en mouvement",
        "tiempo en movimiento", "tempo in movimento", "tempo em movimento", "beweegtijd",
        "czas ruchu", "время в движении", "час у русі", "hareket süresi",
        "移动时间", "移動時間", "이동 시간",
    ),
    "elapsed_time": _row(
        "elapsed time", "συνολικός χρόνος", "verstrichene Zeit", "temps écoulé",
        "tiempo transcurrido", "tempo trascorso", "tempo decorrido", "verstreken tijd",
        "czas całkowity", "общее время", "загальний час", "geçen süre",
        "总用时", "経過時間", "경과 시간",
    ),
    "average_speed": _row(
        "average speed", "μέση ταχύτητα", "durchschnittliche Geschwindigkeit", "vitesse moyenne",
        "velocidad media", "velocità media", "velocidade média", "gemiddelde snelheid",
        "średnia prędkość", "средняя скорость", "середня швидкість", "ortalama hız",
        "平均速度", "平均速度", "평균 속도",
    ),
    "maximum_speed": _row(
        "maximum speed", "μέγιστη ταχύτητα", "maximale Geschwindigkeit", "vitesse maximale",
        "velocidad máxima", "velocità massima", "velocidade máxima", "maximale snelheid",
        "maksymalna prędkość", "максимальная скорость", "максимальна швидкість", "maksimum hız",
        "最高速度", "最高速度", "최고 속도",
    ),
    "weighted_power": _row(
        "weighted / normalized power", "σταθμισμένη / κανονικοποιημένη ισχύς",
        "gewichtete / normalisierte Leistung", "puissance pondérée / normalisée",
        "potencia ponderada / normalizada", "potenza ponderata / normalizzata",
        "potência ponderada / normalizada", "gewogen / genormaliseerd vermogen",
        "moc ważona / znormalizowana", "взвешенная / нормализованная мощность",
        "зважена / нормалізована потужність", "ağırlıklı / normalize güç",
        "加权 / 标准化功率", "加重 / 正規化パワー", "가중 / 정규화 파워",
    ),
    "aerobic_training_effect": _row(
        "aerobic training effect", "αερόβια επίδραση προπόνησης", "aerober Trainingseffekt",
        "effet d’entraînement aérobie", "efecto aeróbico del entrenamiento",
        "effetto aerobico dell’allenamento", "efeito aeróbico do treino",
        "aeroob trainingseffect", "aerobowy efekt treningu", "аэробный эффект тренировки",
        "аеробний ефект тренування", "aerobik antrenman etkisi",
        "有氧训练效果", "有酸素トレーニング効果", "유산소 훈련 효과",
    ),
    "anaerobic_training_effect": _row(
        "anaerobic training effect", "αναερόβια επίδραση προπόνησης", "anaerober Trainingseffekt",
        "effet d’entraînement anaérobie", "efecto anaeróbico del entrenamiento",
        "effetto anaerobico dell’allenamento", "efeito anaeróbico do treino",
        "anaeroob trainingseffect", "beztlenowy efekt treningu", "анаэробный эффект тренировки",
        "анаеробний ефект тренування", "anaerobik antrenman etkisi",
        "无氧训练效果", "無酸素トレーニング効果", "무산소 훈련 효과",
    ),
    "training_effect": _row(
        "training effect", "επίδραση προπόνησης", "Trainingseffekt", "effet d’entraînement",
        "efecto del entrenamiento", "effetto dell’allenamento", "efeito do treino",
        "trainingseffect", "efekt treningu", "эффект тренировки", "ефект тренування",
        "antrenman etkisi", "训练效果", "トレーニング効果", "훈련 효과",
    ),
    "relative_effort": _row(
        "relative effort", "σχετική προσπάθεια", "relative Anstrengung", "effort relatif",
        "esfuerzo relativo", "sforzo relativo", "esforço relativo", "relatieve inspanning",
        "względny wysiłek", "относительная нагрузка", "відносне навантаження", "göreli efor",
        "相对努力程度", "相対エフォート", "상대 운동량",
    ),
    "energy": _row(
        "energy", "ενέργεια", "Energie", "énergie", "energía", "energia", "energia",
        "energie", "energia", "энергия", "енергія", "enerji", "能量", "エネルギー", "에너지",
    ),
    "total_repetitions": _row(
        "total repetitions", "συνολικές επαναλήψεις", "Wiederholungen gesamt", "répétitions totales",
        "repeticiones totales", "ripetizioni totali", "repetições totais", "totaal herhalingen",
        "łączna liczba powtórzeń", "всего повторений", "усього повторень", "toplam tekrar",
        "总次数", "合計レップ数", "총 반복 횟수",
    ),
    "exercise_count": _row(
        "exercise count", "αριθμός ασκήσεων", "Anzahl Übungen", "nombre d’exercices",
        "número de ejercicios", "numero di esercizi", "número de exercícios", "aantal oefeningen",
        "liczba ćwiczeń", "количество упражнений", "кількість вправ", "egzersiz sayısı",
        "动作数量", "種目数", "운동 종목 수",
    ),
    "training_volume": _row(
        "training volume", "όγκος προπόνησης", "Trainingsvolumen", "volume d’entraînement",
        "volumen de entrenamiento", "volume di allenamento", "volume de treino", "trainingsvolume",
        "objętość treningowa", "тренировочный объём", "тренувальний обсяг", "antrenman hacmi",
        "训练容量", "トレーニング量", "훈련 볼륨",
    ),
    "device": _row(
        "device", "συσκευή", "Gerät", "appareil", "dispositivo", "dispositivo", "dispositivo",
        "apparaat", "urządzenie", "устройство", "пристрій", "cihaz", "设备", "デバイス", "기기",
    ),
    "gear": _row(
        "gear", "εξοπλισμός", "Ausrüstung", "équipement", "equipamiento", "attrezzatura",
        "equipamento", "uitrusting", "sprzęt", "экипировка", "спорядження", "ekipman",
        "装备", "ギア", "장비",
    ),
    "data_sources": _row(
        "data sources", "πηγές δεδομένων", "Datenquellen", "sources de données",
        "fuentes de datos", "fonti dati", "fontes de dados", "gegevensbronnen",
        "źródła danych", "источники данных", "джерела даних", "veri kaynakları",
        "数据源", "データソース", "데이터 소스",
    ),
    "trimp_per_hour": _row(
        "TRIMP per hour", "TRIMP ανά ώρα", "TRIMP pro Stunde", "TRIMP par heure",
        "TRIMP por hora", "TRIMP all’ora", "TRIMP por hora", "TRIMP per uur",
        "TRIMP na godzinę", "TRIMP в час", "TRIMP за годину", "saatlik TRIMP",
        "每小时 TRIMP", "1時間あたりの TRIMP", "시간당 TRIMP",
    ),
    "mechanical_work": _row(
        "mechanical work", "μηχανικό έργο", "mechanische Arbeit", "travail mécanique",
        "trabajo mecánico", "lavoro meccanico", "trabalho mecânico", "mechanische arbeid",
        "praca mechaniczna", "механическая работа", "механічна робота", "mekanik iş",
        "机械功", "機械的仕事", "기계적 일",
    ),
    "aerobic_efficiency": _row(
        "aerobic efficiency", "αερόβια αποδοτικότητα", "aerobe Effizienz", "efficacité aérobie",
        "eficiencia aeróbica", "efficienza aerobica", "eficiência aeróbica", "aerobe efficiëntie",
        "wydolność aerobowa", "аэробная эффективность", "аеробна ефективність", "aerobik verimlilik",
        "有氧效率", "有酸素効率", "유산소 효율",
    ),
    "aerobic_decoupling": _row(
        "aerobic decoupling", "αερόβια αποσύζευξη", "aerobe Entkopplung", "découplage aérobie",
        "desacoplamiento aeróbico", "disaccoppiamento aerobico", "desacoplamento aeróbico",
        "aerobe ontkoppeling", "rozsprzężenie aerobowe", "аэробное рассогласование",
        "аеробне розузгодження", "aerobik ayrışma", "有氧解耦", "有酸素デカップリング", "유산소 디커플링",
    ),
    "moderate_intensity_time": _row(
        "moderate-intensity time", "χρόνος μέτριας έντασης", "Zeit bei mittlerer Intensität",
        "temps à intensité modérée", "tiempo a intensidad moderada", "tempo a intensità moderata",
        "tempo em intensidade moderada", "tijd op matige intensiteit", "czas umiarkowanej intensywności",
        "время умеренной интенсивности", "час помірної інтенсивності", "orta yoğunluk süresi",
        "中等强度时间", "中強度時間", "중강도 시간",
    ),
    "vigorous_intensity_time": _row(
        "vigorous-intensity time", "χρόνος υψηλής έντασης", "Zeit bei hoher Intensität",
        "temps à intensité soutenue", "tiempo a intensidad vigorosa", "tempo a intensità vigorosa",
        "tempo em intensidade vigorosa", "tijd op hoge intensiteit", "czas wysokiej intensywności",
        "время высокой интенсивности", "час високої інтенсивності", "yüksek yoğunluk süresi",
        "高强度时间", "高強度時間", "고강도 시간",
    ),
    "near_maximal_time": _row(
        "near-maximal time", "χρόνος σχεδόν μέγιστης έντασης", "Zeit bei nahezu maximaler Intensität",
        "temps à intensité quasi maximale", "tiempo a intensidad casi máxima",
        "tempo a intensità quasi massima", "tempo em intensidade quase máxima",
        "tijd op bijna maximale intensiteit", "czas niemal maksymalnej intensywności",
        "время почти максимальной интенсивности", "час майже максимальної інтенсивності",
        "maksimale yakın yoğunluk süresi", "接近最大强度时间", "最大強度付近の時間", "최대 근접 강도 시간",
    ),
    "time_in_bed": _row(
        "time in bed", "χρόνος στο κρεβάτι", "Bettzeit", "temps au lit", "tiempo en cama",
        "tempo a letto", "tempo na cama", "tijd in bed", "czas w łóżku", "время в постели",
        "час у ліжку", "yatakta geçirilen süre", "卧床时间", "就床時間", "침대에 있던 시간",
    ),
}


LAST_WORKOUT_METRICS = {
    "last_workout_distance": "distance",
    "last_workout_avg_hr": "average_heart_rate",
    "last_workout_max_hr": "maximum_heart_rate",
    "last_workout_avg_power": "average_power",
    "last_workout_max_power": "maximum_power",
    "last_workout_avg_cadence": "average_cadence",
    "last_workout_elevation_gain": "elevation_gain",
    "last_workout_moving_time": "moving_time",
    "last_workout_elapsed_time": "elapsed_time",
    "last_workout_average_speed": "average_speed",
    "last_workout_max_speed": "maximum_speed",
    "last_workout_weighted_power": "weighted_power",
    "last_workout_max_cadence": "maximum_cadence",
    "last_workout_elevation_loss": "elevation_loss",
    "last_workout_aerobic_effect": "aerobic_training_effect",
    "last_workout_anaerobic_effect": "anaerobic_training_effect",
    "last_workout_training_effect": "training_effect",
    "last_workout_relative_effort": "relative_effort",
    "last_workout_kilojoules": "energy",
    "last_workout_total_reps": "total_repetitions",
    "last_workout_exercise_count": "exercise_count",
    "last_workout_volume": "training_volume",
    "last_workout_device": "device",
    "last_workout_gear": "gear",
    "last_workout_sources": "data_sources",
    "last_workout_trimp_per_hour": "trimp_per_hour",
    "last_workout_mechanical_work": "mechanical_work",
    "last_workout_aerobic_efficiency": "aerobic_efficiency",
    "last_workout_aerobic_decoupling": "aerobic_decoupling",
    "last_workout_time_moderate": "moderate_intensity_time",
    "last_workout_time_vigorous": "vigorous_intensity_time",
    "last_workout_time_near_maximal": "near_maximal_time",
}

LIVE_METRICS = {
    "live_average_heart_rate": "average_heart_rate",
    "live_maximum_heart_rate": "maximum_heart_rate",
    "live_average_power": "average_power",
    "live_maximum_power": "maximum_power",
    "live_average_cadence": "average_cadence",
    "live_average_speed": "average_speed",
    "live_mechanical_work": "mechanical_work",
    "live_aerobic_efficiency": "aerobic_efficiency",
    "live_aerobic_decoupling": "aerobic_decoupling",
}

LAST_SLEEP_METRICS = {
    "last_sleep_time_in_bed": "time_in_bed",
    "last_sleep_average_hr": "average_heart_rate",
}


DIRECT = {
    "current_heart_rate": _row(
        "Current heart rate", "Τρέχων καρδιακός ρυθμός", "Aktuelle Herzfrequenz",
        "Fréquence cardiaque actuelle", "Frecuencia cardíaca actual", "Frequenza cardiaca attuale",
        "Frequência cardíaca atual", "Huidige hartslag", "Bieżące tętno",
        "Текущий пульс", "Поточний пульс", "Mevcut kalp hızı",
        "当前心率", "現在の心拍数", "현재 심박수",
    ),
    "current_power": _row(
        "Current power", "Τρέχουσα ισχύς", "Aktuelle Leistung", "Puissance actuelle",
        "Potencia actual", "Potenza attuale", "Potência atual", "Huidig vermogen",
        "Bieżąca moc", "Текущая мощность", "Поточна потужність", "Mevcut güç",
        "当前功率", "現在のパワー", "현재 파워",
    ),
    "current_cadence": _row(
        "Current cadence", "Τρέχων ρυθμός πεταλιάς", "Aktuelle Kadenz", "Cadence actuelle",
        "Cadencia actual", "Cadenza attuale", "Cadência atual", "Huidige cadans",
        "Bieżąca kadencja", "Текущий каденс", "Поточний каденс", "Mevcut kadans",
        "当前踏频", "現在のケイデンス", "현재 케이던스",
    ),
    "current_speed": _row(
        "Current speed", "Τρέχουσα ταχύτητα", "Aktuelle Geschwindigkeit", "Vitesse actuelle",
        "Velocidad actual", "Velocità attuale", "Velocidade atual", "Huidige snelheid",
        "Bieżąca prędkość", "Текущая скорость", "Поточна швидкість", "Mevcut hız",
        "当前速度", "現在の速度", "현재 속도",
    ),
    "current_distance": _row(
        "Current distance", "Τρέχουσα απόσταση", "Aktuelle Distanz", "Distance actuelle",
        "Distancia actual", "Distanza attuale", "Distância atual", "Huidige afstand",
        "Bieżący dystans", "Текущая дистанция", "Поточна дистанція", "Mevcut mesafe",
        "当前距离", "現在の距離", "현재 거리",
    ),
    "current_altitude": _row(
        "Current altitude", "Τρέχον υψόμετρο", "Aktuelle Höhe", "Altitude actuelle",
        "Altitud actual", "Altitudine attuale", "Altitude atual", "Huidige hoogte",
        "Bieżąca wysokość", "Текущая высота", "Поточна висота", "Mevcut irtifa",
        "当前海拔", "現在の高度", "현재 고도",
    ),
    "vo2max_percent_predicted": _row(
        "VO₂max percent predicted", "Προβλεπόμενο ποσοστό VO₂max", "Vorhergesagter VO₂max-Prozentwert",
        "Pourcentage de VO₂max prédit", "Porcentaje de VO₂máx predicho", "Percentuale di VO₂max prevista",
        "Percentagem de VO₂máx prevista", "Voorspeld VO₂max-percentage", "Przewidywany procent VO₂max",
        "Прогнозируемый процент МПК", "Прогнозований відсоток МСК", "Tahmini VO₂maks yüzdesi",
        "预测最大摄氧量百分比", "予測 VO₂max の割合", "예측 VO₂max 백분율",
    ),
    "cardiorespiratory_status": _row(
        "Cardiorespiratory fitness status", "Κατάσταση καρδιοαναπνευστικής φυσικής κατάστασης",
        "Status der kardiorespiratorischen Fitness", "État de la condition cardiorespiratoire",
        "Estado de la capacidad cardiorrespiratoria", "Stato della forma cardiorespiratoria",
        "Estado da aptidão cardiorrespiratória", "Cardiorespiratoire fitnessstatus",
        "Stan wydolności krążeniowo-oddechowej", "Состояние кардиореспираторной формы",
        "Стан кардіореспіраторної форми", "Kardiyorespiratuvar uygunluk durumu",
        "心肺适能状态", "心肺フィットネス状態", "심폐 체력 상태",
    ),
    "threshold_hr": _row(
        "Threshold heart rate", "Καρδιακός ρυθμός κατωφλίου", "Schwellenherzfrequenz",
        "Fréquence cardiaque au seuil", "Frecuencia cardíaca umbral", "Frequenza cardiaca di soglia",
        "Frequência cardíaca no limiar", "Drempelhartslag", "Tętno progowe",
        "Пороговый пульс", "Пороговий пульс", "Eşik kalp hızı", "阈值心率", "閾値心拍数", "역치 심박수",
    ),
    "threshold_pace": _row(
        "Threshold pace", "Ρυθμός κατωφλίου", "Schwellentempo", "Allure au seuil",
        "Ritmo umbral", "Passo di soglia", "Ritmo no limiar", "Drempeltempo",
        "Tempo progowe", "Пороговый темп", "Пороговий темп", "Eşik tempo",
        "阈值配速", "閾値ペース", "역치 페이스",
    ),
    "threshold_power": _row(
        "Threshold power", "Ισχύς κατωφλίου", "Schwellenleistung", "Puissance au seuil",
        "Potencia umbral", "Potenza di soglia", "Potência no limiar", "Drempelvermogen",
        "Moc progowa", "Пороговая мощность", "Порогова потужність", "Eşik güç",
        "阈值功率", "閾値パワー", "역치 파워",
    ),
    "threshold_power_to_weight": _row(
        "Threshold power-to-weight", "Αναλογία ισχύος κατωφλίου προς βάρος",
        "Schwellenleistung pro Gewicht", "Rapport puissance/poids au seuil",
        "Relación potencia-peso umbral", "Rapporto potenza/peso di soglia",
        "Relação potência/peso no limiar", "Drempelvermogen per gewicht",
        "Progowy stosunek mocy do masy", "Пороговая удельная мощность",
        "Порогова питома потужність", "Eşik güç/ağırlık oranı",
        "阈值功率体重比", "閾値パワーウェイトレシオ", "역치 파워 대 체중비",
    ),
    "training_readiness_context": _row(
        "Training readiness context", "Πλαίσιο ετοιμότητας προπόνησης", "Kontext der Trainingsbereitschaft",
        "Contexte de préparation à l’entraînement", "Contexto de preparación para entrenar",
        "Contesto della preparazione all’allenamento", "Contexto da prontidão para treino",
        "Context van trainingsgereedheid", "Kontekst gotowości treningowej",
        "Контекст готовности к тренировке", "Контекст готовності до тренування",
        "Antrenmana hazır olma bağlamı", "训练准备度上下文", "トレーニング準備度の状況", "훈련 준비도 맥락",
    ),
    "provider_training_status": _row(
        "Provider training status", "Κατάσταση προπόνησης παρόχου", "Trainingsstatus des Anbieters",
        "État d’entraînement du fournisseur", "Estado de entrenamiento del proveedor",
        "Stato di allenamento del provider", "Estado de treino do fornecedor",
        "Trainingsstatus van provider", "Stan treningu od dostawcy",
        "Статус тренировки от провайдера", "Статус тренування від постачальника",
        "Sağlayıcı antrenman durumu", "提供商训练状态", "プロバイダーのトレーニング状態", "제공자 훈련 상태",
    ),
    "heart_rate_percent_max": _row(
        "Heart rate as % of maximum", "Καρδιακός ρυθμός ως % του μέγιστου",
        "Herzfrequenz in % des Maximums", "Fréquence cardiaque en % du maximum",
        "Frecuencia cardíaca como % del máximo", "Frequenza cardiaca come % del massimo",
        "Frequência cardíaca como % do máximo", "Hartslag als % van maximum",
        "Tętno jako % maksimum", "Пульс в % от максимума", "Пульс у % від максимуму",
        "Maksimumun yüzdesi olarak kalp hızı", "心率占最大值百分比", "最大心拍数に対する割合", "최대 심박수 대비 백분율",
    ),
    "heart_rate_relative_threshold": _row(
        "Heart rate relative to threshold", "Καρδιακός ρυθμός σε σχέση με το κατώφλι",
        "Herzfrequenz relativ zur Schwelle", "Fréquence cardiaque par rapport au seuil",
        "Frecuencia cardíaca respecto al umbral", "Frequenza cardiaca rispetto alla soglia",
        "Frequência cardíaca relativa ao limiar", "Hartslag ten opzichte van drempel",
        "Tętno względem progu", "Пульс относительно порога", "Пульс відносно порога",
        "Eşiğe göre kalp hızı", "心率相对阈值", "閾値に対する心拍数", "역치 대비 심박수",
    ),
    "power_relative_threshold": _row(
        "Power relative to threshold", "Ισχύς σε σχέση με το κατώφλι", "Leistung relativ zur Schwelle",
        "Puissance par rapport au seuil", "Potencia respecto al umbral", "Potenza rispetto alla soglia",
        "Potência relativa ao limiar", "Vermogen ten opzichte van drempel", "Moc względem progu",
        "Мощность относительно порога", "Потужність відносно порога", "Eşiğe göre güç",
        "功率相对阈值", "閾値に対するパワー", "역치 대비 파워",
    ),
    "speed_relative_threshold": _row(
        "Speed relative to threshold", "Ταχύτητα σε σχέση με το κατώφλι", "Geschwindigkeit relativ zur Schwelle",
        "Vitesse par rapport au seuil", "Velocidad respecto al umbral", "Velocità rispetto alla soglia",
        "Velocidade relativa ao limiar", "Snelheid ten opzichte van drempel", "Prędkość względem progu",
        "Скорость относительно порога", "Швидкість відносно порога", "Eşiğe göre hız",
        "速度相对阈值", "閾値に対する速度", "역치 대비 속도",
    ),
    "last_workout_trimp_vs_recent": _row(
        "TRIMP vs comparable recent workouts", "TRIMP έναντι συγκρίσιμων πρόσφατων προπονήσεων",
        "TRIMP im Vergleich zu ähnlichen letzten Trainings", "TRIMP par rapport aux entraînements récents comparables",
        "TRIMP frente a entrenamientos recientes comparables", "TRIMP rispetto ad allenamenti recenti comparabili",
        "TRIMP face a treinos recentes comparáveis", "TRIMP versus vergelijkbare recente trainingen",
        "TRIMP względem porównywalnych ostatnich treningów", "TRIMP относительно сопоставимых недавних тренировок",
        "TRIMP відносно порівнюваних останніх тренувань", "Benzer son antrenmanlara göre TRIMP",
        "TRIMP 与近期同类训练对比", "最近の同等ワークアウトに対する TRIMP", "유사한 최근 운동 대비 TRIMP",
    ),
    "last_workout_load_context": _row(
        "Workout load context", "Πλαίσιο προπονητικού φορτίου", "Kontext der Trainingsbelastung",
        "Contexte de charge d’entraînement", "Contexto de carga del entrenamiento",
        "Contesto del carico di allenamento", "Contexto da carga de treino",
        "Context van trainingsbelasting", "Kontekst obciążenia treningowego",
        "Контекст тренировочной нагрузки", "Контекст тренувального навантаження",
        "Antrenman yükü bağlamı", "训练负荷上下文", "ワークアウト負荷の状況", "운동 부하 맥락",
    ),
    "last_workout_personal_context": _row(
        "Workout personal context", "Προσωπικό πλαίσιο προπόνησης", "Persönlicher Trainingskontext",
        "Contexte personnel de l’entraînement", "Contexto personal del entrenamiento",
        "Contesto personale dell’allenamento", "Contexto pessoal do treino",
        "Persoonlijke trainingscontext", "Osobisty kontekst treningu",
        "Личный контекст тренировки", "Особистий контекст тренування",
        "Kişisel antrenman bağlamı", "训练个人上下文", "ワークアウトの個人状況", "개인 운동 맥락",
    ),
    "sleep_score_context": _row(
        "Sleep score context", "Πλαίσιο βαθμολογίας ύπνου", "Kontext der Schlafbewertung",
        "Contexte du score de sommeil", "Contexto de la puntuación del sueño",
        "Contesto del punteggio del sonno", "Contexto da pontuação do sono",
        "Context van slaapscore", "Kontekst wyniku snu", "Контекст оценки сна",
        "Контекст оцінки сну", "Uyku puanı bağlamı", "睡眠评分上下文",
        "睡眠スコアの状況", "수면 점수 맥락",
    ),
    "hrr_60s_vs_90d": _row(
        "Latest 60 s heart-rate recovery vs 90-day baseline",
        "Τελευταία αποκατάσταση καρδιακού ρυθμού 60 δ. έναντι βάσης 90 ημερών",
        "Letzte 60-s-Herzfrequenzerholung gegenüber 90-Tage-Basis",
        "Dernière récupération cardiaque à 60 s par rapport à la référence sur 90 jours",
        "Última recuperación cardíaca a 60 s frente a la referencia de 90 días",
        "Ultimo recupero della frequenza cardiaca a 60 s rispetto alla base di 90 giorni",
        "Última recuperação da frequência cardíaca aos 60 s face à referência de 90 dias",
        "Laatste hartslagherstel na 60 s versus 90-daagse basis",
        "Najnowszy 60-sekundowy spadek tętna względem bazy z 90 dni",
        "Последнее восстановление пульса за 60 с относительно базы за 90 дней",
        "Останнє відновлення пульсу за 60 с відносно бази за 90 днів",
        "Son 60 sn kalp hızı toparlanmasının 90 günlük tabana göre durumu",
        "最近 60 秒心率恢复与 90 天基线对比", "最新の60秒心拍回復と90日基準の比較",
        "최근 60초 심박수 회복과 90일 기준 비교",
    ),
    "sleep_duration_shortfall": _row(
        "Sleep duration shortfall vs 7 h adult minimum", "Έλλειμμα διάρκειας ύπνου έναντι ελάχιστου 7 ωρών για ενήλικες",
        "Schlafdefizit gegenüber dem Erwachsenenminimum von 7 Std.", "Déficit de sommeil par rapport au minimum adulte de 7 h",
        "Déficit de sueño frente al mínimo adulto de 7 h", "Deficit di sonno rispetto al minimo adulto di 7 ore",
        "Défice de sono face ao mínimo de 7 h para adultos", "Slaaptekort ten opzichte van minimaal 7 uur voor volwassenen",
        "Niedobór snu względem minimum 7 godzin dla dorosłych", "Дефицит сна относительно минимума 7 ч для взрослых",
        "Дефіцит сну відносно мінімуму 7 год для дорослих", "Yetişkinler için 7 saatlik asgariye göre uyku açığı",
        "睡眠时长低于成人最低 7 小时的差值", "成人の最低7時間に対する睡眠不足", "성인 최소 7시간 대비 수면 부족",
    ),
    "sleep_midpoint_variability_14d": _row(
        "Sleep midpoint variability (14 days)", "Μεταβλητότητα μέσου σημείου ύπνου (14 ημέρες)",
        "Variabilität der Schlafmitte (14 Tage)", "Variabilité du milieu du sommeil (14 jours)",
        "Variabilidad del punto medio del sueño (14 días)", "Variabilità del punto medio del sonno (14 giorni)",
        "Variabilidade do ponto médio do sono (14 dias)", "Variatie in slaapmiddelpunt (14 dagen)",
        "Zmienność środka snu (14 dni)", "Вариабельность середины сна (14 дней)",
        "Варіабельність середини сну (14 днів)", "Uyku orta noktası değişkenliği (14 gün)",
        "睡眠中点变异性（14 天）", "睡眠中間時刻の変動（14日間）", "수면 중간 시각 변동성(14일)",
    ),
    "sleep_hrv_vs_28d_percent": _row(
        "Latest sleep HRV vs 28-day baseline", "Τελευταία HRV ύπνου έναντι βάσης 28 ημερών",
        "Letzte Schlaf-HRV gegenüber 28-Tage-Basis", "Dernière VFC du sommeil par rapport à la référence sur 28 jours",
        "Última VFC del sueño frente a la referencia de 28 días", "Ultima HRV del sonno rispetto alla base di 28 giorni",
        "Última VFC do sono face à referência de 28 dias", "Laatste slaap-HRV versus 28-daagse basis",
        "Najnowsza HRV podczas snu względem bazy z 28 dni", "Последняя ВСР сна относительно базы за 28 дней",
        "Остання ВСР сну відносно бази за 28 днів", "Son uyku HRV'sinin 28 günlük tabana göre durumu",
        "最近睡眠 HRV 与 28 天基线对比", "最新の睡眠 HRV と28日基準の比較", "최근 수면 HRV와 28일 기준 비교",
    ),
    "last_recovery_interval_h": _row(
        "Last recovery interval", "Τελευταίο διάστημα αποκατάστασης", "Letztes Erholungsintervall",
        "Dernier intervalle de récupération", "Último intervalo de recuperación", "Ultimo intervallo di recupero",
        "Último intervalo de recuperação", "Laatste herstelinterval", "Ostatni okres regeneracji",
        "Последний интервал восстановления", "Останній інтервал відновлення", "Son toparlanma aralığı",
        "上次恢复间隔", "前回の回復間隔", "마지막 회복 간격",
    ),
    "sleep_duration_pairs": _row(
        "Workout–sleep duration pairs", "Ζεύγη προπόνησης–διάρκειας ύπνου", "Paare aus Training und Schlafdauer",
        "Paires entraînement–durée de sommeil", "Pares entrenamiento–duración del sueño",
        "Coppie allenamento–durata del sonno", "Pares treino–duração do sono",
        "Paren training–slaapduur", "Pary trening–długość snu", "Пары тренировка–длительность сна",
        "Пари тренування–тривалість сну", "Antrenman–uyku süresi çiftleri",
        "训练–睡眠时长数据对", "ワークアウト–睡眠時間のペア", "운동–수면 시간 쌍",
    ),
    "sleep_hrv_pairs": _row(
        "Workout–sleep HRV pairs", "Ζεύγη προπόνησης–HRV ύπνου", "Paare aus Training und Schlaf-HRV",
        "Paires entraînement–VFC du sommeil", "Pares entrenamiento–VFC del sueño",
        "Coppie allenamento–HRV del sonno", "Pares treino–VFC do sono",
        "Paren training–slaap-HRV", "Pary trening–HRV podczas snu", "Пары тренировка–ВСР сна",
        "Пари тренування–ВСР сну", "Antrenman–uyku HRV çiftleri",
        "训练–睡眠 HRV 数据对", "ワークアウト–睡眠 HRV のペア", "운동–수면 HRV 쌍",
    ),
}

DIRECT["maximum_hr"] = {
    language: value[:1].upper() + value[1:]
    for language, value in METRICS["maximum_heart_rate"].items()
}


def _compound(template: dict[str, str], metric: dict[str, str]) -> dict[str, str]:
    return {
        language: template[language].format(metric=metric[language])
        for language in LANGUAGES
    }


ENTITY_NAMES: dict[tuple[str, ...], dict[str, str]] = {}
_NESTED_DIRECT_KEYS = {
    "sleep_hrv_vs_28d_percent", "last_recovery_interval_h",
    "sleep_duration_pairs", "sleep_hrv_pairs",
}

for entity_key, metric_key in LAST_WORKOUT_METRICS.items():
    ENTITY_NAMES[("entity", "sensor", entity_key, "name")] = _compound(
        LAST_WORKOUT, METRICS[metric_key]
    )

for entity_key, metric_key in LIVE_METRICS.items():
    ENTITY_NAMES[("entity", "sensor", entity_key, "name")] = _compound(
        LIVE, METRICS[metric_key]
    )

for entity_key, metric_key in LAST_SLEEP_METRICS.items():
    ENTITY_NAMES[("entity", "sensor", entity_key, "name")] = _compound(
        LAST_SLEEP, METRICS[metric_key]
    )

for entity_key, translations in DIRECT.items():
    if entity_key not in _NESTED_DIRECT_KEYS:
        ENTITY_NAMES[("entity", "sensor", entity_key, "name")] = translations

ENTITY_NAMES.update(
    {
        (
            "entity", "sensor", "autonomic_recovery_trend", "state_attributes",
            "sleep_hrv_vs_28d_percent", "name",
        ): DIRECT["sleep_hrv_vs_28d_percent"],
        (
            "entity", "sensor", "training_load", "state_attributes",
            "last_recovery_interval_h", "name",
        ): DIRECT["last_recovery_interval_h"],
        (
            "entity", "sensor", "training_recovery_relationship", "state_attributes",
            "sleep_duration_pairs", "name",
        ): DIRECT["sleep_duration_pairs"],
        (
            "entity", "sensor", "training_recovery_relationship", "state_attributes",
            "sleep_hrv_pairs", "name",
        ): DIRECT["sleep_hrv_pairs"],
    }
)

if set(DIRECT) - {
    path[2] for path in ENTITY_NAMES if len(path) == 4 and path[:2] == ("entity", "sensor")
} - _NESTED_DIRECT_KEYS:
    raise RuntimeError("A direct entity translation is not routed to a catalog path")
