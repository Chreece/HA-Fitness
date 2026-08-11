"""User-facing scientific details for Fitness-calculated live workout metrics."""
from __future__ import annotations

from .research.references import REFERENCES

CALCULATED_LIVE_METRICS = {
    "session_duration",
    "heart_rate_percent_max", "heart_rate_reserve_percent", "heart_rate_intensity",
    "heart_rate_relative_threshold", "current_power_to_weight",
    "power_relative_threshold", "current_pace", "speed_relative_threshold",
    "live_average_hr", "live_maximum_hr", "live_average_power", "live_maximum_power",
    "live_average_cadence", "live_average_speed", "live_banister_trimp",
    "live_mechanical_work", "live_aerobic_efficiency", "live_aerobic_decoupling",
    "live_time_moderate", "live_time_vigorous", "live_time_near_maximal",
}

_STUDY = {
    "heart_rate_percent_max": "acsm_hrr_intensity_2011",
    "heart_rate_reserve_percent": "acsm_hrr_intensity_2011",
    "heart_rate_intensity": "acsm_hrr_intensity_2011",
    "live_time_moderate": "acsm_hrr_intensity_2011",
    "live_time_vigorous": "acsm_hrr_intensity_2011",
    "live_time_near_maximal": "acsm_hrr_intensity_2011",
    "live_banister_trimp": "banister_trimp_validation_2014",
    "live_aerobic_decoupling": "cardiovascular_drift_2001",
}

_FORMULA = {
    "session_duration": "now − workout start time",
    "heart_rate_percent_max": "current HR / maximum HR × 100",
    "heart_rate_reserve_percent": "(current HR − resting HR) / (maximum HR − resting HR) × 100",
    "heart_rate_intensity": "ACSM HR-reserve bands: <30 very light; 30–39 light; 40–59 moderate; 60–89 vigorous; ≥90 near-maximal",
    "heart_rate_relative_threshold": "current HR / configured threshold HR × 100",
    "current_power_to_weight": "current power (W) / body mass (kg)",
    "power_relative_threshold": "current power / configured threshold power × 100",
    "current_pace": "60 / speed (km/h)",
    "speed_relative_threshold": "current speed / threshold speed × 100; threshold speed = 60 / threshold pace",
    "live_average_hr": "arithmetic mean of valid heart-rate samples collected in this session",
    "live_maximum_hr": "maximum valid heart-rate sample collected in this session",
    "live_average_power": "arithmetic mean of valid power samples collected in this session",
    "live_maximum_power": "maximum valid power sample collected in this session",
    "live_average_cadence": "arithmetic mean of valid cadence samples collected in this session",
    "live_average_speed": "arithmetic mean of valid speed samples collected in this session",
    "live_banister_trimp": "duration(min) × HR reserve fraction × sex-specific exponential weighting",
    "live_mechanical_work": "Σ ((P₁ + P₂) / 2) × Δt / 1000, integrating power samples to kJ",
    "live_aerobic_efficiency": "mean external work / HR; power/HR is preferred, otherwise speed/HR",
    "live_aerobic_decoupling": "(mean efficiency first half − mean efficiency second half) / first-half mean × 100",
    "live_time_moderate": "Σ sample intervals where HR reserve is 40–59%",
    "live_time_vigorous": "Σ sample intervals where HR reserve is 60–89%",
    "live_time_near_maximal": "Σ sample intervals where HR reserve is ≥90%",
}

_EN = {
    "session_duration": ("Elapsed time since Fitness detected the start of the live workout.", "Useful for session timing and all duration-dependent live calculations."),
    "heart_rate_percent_max": ("Shows current heart rate as a percentage of your configured/derived maximum heart rate.", "Useful as simple cardiovascular-intensity context, although personal thresholds are more individual."),
    "heart_rate_reserve_percent": ("Expresses current heart rate relative to your usable heart-rate reserve between resting and maximum HR.", "Useful for individualized exercise-intensity classification when resting and maximum HR are available."),
    "heart_rate_intensity": ("Classifies the current heart-rate-reserve percentage into ACSM exercise-intensity bands.", "Useful for understanding the approximate cardiovascular intensity of the current effort."),
    "heart_rate_relative_threshold": ("Compares current heart rate with the threshold HR configured in Fitness.", "Useful for seeing how close the current effort is to your own threshold rather than a population cutoff."),
    "current_power_to_weight": ("Normalizes current mechanical power by body mass.", "Useful for comparing power output across changes in body mass and between efforts."),
    "power_relative_threshold": ("Compares current power with the threshold/FTP value configured in Fitness.", "Useful for pacing an effort relative to your own performance threshold."),
    "current_pace": ("Converts the active speed measurement into running pace.", "Useful when the source reports speed but pace in min/km is easier to interpret."),
    "speed_relative_threshold": ("Compares current speed with the speed corresponding to your configured threshold pace.", "Useful for pacing running effort relative to your personal threshold."),
    "live_average_hr": ("Average of the heart-rate samples Fitness has collected in the current workout.", "Useful for following the session's overall cardiovascular demand."),
    "live_maximum_hr": ("Highest heart-rate sample Fitness has collected in the current workout.", "Useful for identifying the peak cardiovascular response reached so far."),
    "live_average_power": ("Average of the power samples Fitness has collected in the current workout.", "Useful for tracking the overall external power demand of the session."),
    "live_maximum_power": ("Highest power sample Fitness has collected in the current workout.", "Useful for identifying the peak power reached so far."),
    "live_average_cadence": ("Average cadence of valid samples collected during the current workout.", "Useful for following movement/running/cycling rhythm across the session."),
    "live_average_speed": ("Average speed of valid samples collected during the current workout.", "Useful for following overall movement speed rather than a single instantaneous sample."),
    "live_banister_trimp": ("Estimates internal training load from session duration and heart-rate reserve using Banister TRIMP.", "Useful for comparing accumulated cardiovascular training load across sessions."),
    "live_mechanical_work": ("Integrates measured power over elapsed time to estimate mechanical work in kilojoules.", "Useful for quantifying accumulated external work when a power source is available."),
    "live_aerobic_efficiency": ("Tracks external output relative to heart rate, using power/HR when possible or speed/HR otherwise.", "Useful for within-person comparison of cardiovascular cost for a given external output."),
    "live_aerobic_decoupling": ("Compares external-output/HR efficiency between the first and second halves of a sufficiently long workout.", "Useful for observing cardiovascular drift during steady endurance work; it is descriptive, not a universal pass/fail threshold."),
    "live_time_moderate": ("Accumulated session time in the ACSM moderate HR-reserve band.", "Useful for understanding how much of the current workout has been spent at moderate cardiovascular intensity."),
    "live_time_vigorous": ("Accumulated session time in the ACSM vigorous HR-reserve band.", "Useful for understanding how much of the current workout has been spent at vigorous cardiovascular intensity."),
    "live_time_near_maximal": ("Accumulated session time in the ACSM near-maximal HR-reserve band.", "Useful for identifying how much high cardiovascular-intensity exposure has accumulated."),
}

_EL = {
    "session_duration": ("Ο χρόνος που έχει περάσει από τη στιγμή που το Fitness εντόπισε την έναρξη της ζωντανής προπόνησης.", "Χρήσιμο για τη χρονομέτρηση και όλους τους υπολογισμούς που εξαρτώνται από τη διάρκεια."),
    "heart_rate_percent_max": ("Δείχνει τους τρέχοντες παλμούς ως ποσοστό των μέγιστων παλμών σου.", "Χρήσιμο ως απλό πλαίσιο καρδιαγγειακής έντασης, αν και τα προσωπικά κατώφλια είναι πιο εξατομικευμένα."),
    "heart_rate_reserve_percent": ("Εκφράζει τους τρέχοντες παλμούς σε σχέση με το καρδιακό απόθεμα μεταξύ παλμών ηρεμίας και μέγιστων παλμών.", "Χρήσιμο για πιο εξατομικευμένη ταξινόμηση της έντασης όταν υπάρχουν παλμοί ηρεμίας και μέγιστοι παλμοί."),
    "heart_rate_intensity": ("Κατατάσσει το ποσοστό καρδιακού αποθέματος στις ζώνες έντασης άσκησης του ACSM.", "Χρήσιμο για να καταλαβαίνεις κατά προσέγγιση την καρδιαγγειακή ένταση της τρέχουσας προσπάθειας."),
    "heart_rate_relative_threshold": ("Συγκρίνει τους τρέχοντες παλμούς με το κατώφλι καρδιακού ρυθμού που έχεις ορίσει.", "Χρήσιμο για να βλέπεις πόσο κοντά βρίσκεσαι στο προσωπικό σου κατώφλι."),
    "current_power_to_weight": ("Κανονικοποιεί την τρέχουσα ισχύ με βάση το σωματικό βάρος.", "Χρήσιμο για σύγκριση της ισχύος όταν αλλάζει το βάρος ή μεταξύ διαφορετικών προσπαθειών."),
    "power_relative_threshold": ("Συγκρίνει την τρέχουσα ισχύ με την ισχύ κατωφλίου/FTP που έχεις ορίσει.", "Χρήσιμο για ρύθμιση της προσπάθειας σε σχέση με το προσωπικό σου κατώφλι απόδοσης."),
    "current_pace": ("Μετατρέπει την ενεργή μέτρηση ταχύτητας σε ρυθμό τρεξίματος.", "Χρήσιμο όταν η πηγή δίνει ταχύτητα αλλά ο ρυθμός σε λεπτά/χλμ είναι πιο εύκολος στην ερμηνεία."),
    "speed_relative_threshold": ("Συγκρίνει την τρέχουσα ταχύτητα με την ταχύτητα που αντιστοιχεί στον ρυθμό κατωφλίου σου.", "Χρήσιμο για ρύθμιση της δρομικής προσπάθειας σε σχέση με το προσωπικό σου κατώφλι."),
    "live_average_hr": ("Ο μέσος όρος των έγκυρων δειγμάτων καρδιακού ρυθμού που έχει συλλέξει το Fitness στην τρέχουσα προπόνηση.", "Χρήσιμο για την παρακολούθηση της συνολικής καρδιαγγειακής επιβάρυνσης της συνεδρίας."),
    "live_maximum_hr": ("Το υψηλότερο δείγμα καρδιακού ρυθμού που έχει συλλεχθεί μέχρι τώρα.", "Χρήσιμο για να βλέπεις τη μέγιστη καρδιαγγειακή απόκριση που επιτεύχθηκε."),
    "live_average_power": ("Ο μέσος όρος των έγκυρων δειγμάτων ισχύος της τρέχουσας προπόνησης.", "Χρήσιμο για την παρακολούθηση της συνολικής εξωτερικής απαίτησης ισχύος."),
    "live_maximum_power": ("Το υψηλότερο δείγμα ισχύος που έχει συλλεχθεί μέχρι τώρα.", "Χρήσιμο για να βλέπεις τη μέγιστη ισχύ που επιτεύχθηκε."),
    "live_average_cadence": ("Ο μέσος ρυθμός βημάτων/πεταλιών από τα έγκυρα δείγματα της τρέχουσας προπόνησης.", "Χρήσιμο για να παρακολουθείς τον ρυθμό κίνησης σε όλη τη συνεδρία."),
    "live_average_speed": ("Η μέση ταχύτητα από τα έγκυρα δείγματα της τρέχουσας προπόνησης.", "Χρήσιμο για να παρακολουθείς τη συνολική ταχύτητα αντί για μία στιγμιαία μέτρηση."),
    "live_banister_trimp": ("Εκτιμά το εσωτερικό προπονητικό φορτίο από τη διάρκεια και το καρδιακό απόθεμα με τη μέθοδο Banister TRIMP.", "Χρήσιμο για σύγκριση της συσσωρευμένης καρδιαγγειακής επιβάρυνσης μεταξύ προπονήσεων."),
    "live_mechanical_work": ("Ολοκληρώνει την μετρημένη ισχύ ως προς τον χρόνο για να υπολογίσει το μηχανικό έργο σε kJ.", "Χρήσιμο για την ποσοτικοποίηση του συσσωρευμένου εξωτερικού έργου όταν υπάρχει αισθητήρας ισχύος."),
    "live_aerobic_efficiency": ("Παρακολουθεί την εξωτερική απόδοση σε σχέση με τους παλμούς, προτιμώντας ισχύ/HR και εναλλακτικά ταχύτητα/HR.", "Χρήσιμο για προσωπική σύγκριση του καρδιαγγειακού κόστους για παρόμοια εξωτερική απόδοση."),
    "live_aerobic_decoupling": ("Συγκρίνει την αποδοτικότητα εξωτερικής απόδοσης/HR μεταξύ του πρώτου και δεύτερου μισού μιας αρκετά μεγάλης προπόνησης.", "Χρήσιμο για την παρατήρηση καρδιαγγειακής μετατόπισης σε σταθερή άσκηση αντοχής· είναι περιγραφικό και όχι καθολικό όριο επιτυχίας/αποτυχίας."),
    "live_time_moderate": ("Ο συσσωρευμένος χρόνος στη μέτρια ζώνη καρδιακού αποθέματος του ACSM.", "Χρήσιμο για να βλέπεις πόσο χρόνο έχεις περάσει σε μέτρια καρδιαγγειακή ένταση."),
    "live_time_vigorous": ("Ο συσσωρευμένος χρόνος στην έντονη ζώνη καρδιακού αποθέματος του ACSM.", "Χρήσιμο για να βλέπεις πόσο χρόνο έχεις περάσει σε έντονη καρδιαγγειακή ένταση."),
    "live_time_near_maximal": ("Ο συσσωρευμένος χρόνος στη σχεδόν μέγιστη ζώνη καρδιακού αποθέματος του ACSM.", "Χρήσιμο για να βλέπεις πόση έκθεση πολύ υψηλής καρδιαγγειακής έντασης έχει συσσωρευτεί."),
}

# Fully localized generic wording for supported languages. Metric names/formulas remain
# technically precise; the explanatory prose does not fall back to English.
_OTHER = {
    "de": ("Von Fitness aus den während des aktuellen Trainings erfassten Messwerten deterministisch berechnet.", "Hilft, den aktuellen Trainingsverlauf und die Belastung im persönlichen Kontext zu verstehen."),
    "fr": ("Calculé de façon déterministe par Fitness à partir des mesures recueillies pendant l'entraînement en cours.", "Aide à comprendre l'évolution et l'intensité de l'entraînement actuel dans ton contexte personnel."),
    "es": ("Calculado de forma determinista por Fitness a partir de las mediciones recogidas durante el entrenamiento actual.", "Ayuda a interpretar la evolución y la carga del entrenamiento actual en tu contexto personal."),
    "it": ("Calcolato in modo deterministico da Fitness dai dati raccolti durante l'allenamento corrente.", "Aiuta a interpretare andamento e carico dell'allenamento corrente nel tuo contesto personale."),
    "pt": ("Calculado deterministicamente pelo Fitness a partir das medições recolhidas durante o treino atual.", "Ajuda a interpretar a evolução e a carga do treino atual no teu contexto pessoal."),
    "nl": ("Deterministisch door Fitness berekend uit metingen die tijdens de huidige training zijn verzameld.", "Helpt het verloop en de belasting van de huidige training in je persoonlijke context te begrijpen."),
    "pl": ("Obliczane deterministycznie przez Fitness z pomiarów zebranych podczas bieżącego treningu.", "Pomaga zrozumieć przebieg i obciążenie bieżącego treningu w osobistym kontekście."),
    "ru": ("Детерминированно рассчитывается Fitness по измерениям текущей тренировки.", "Помогает оценивать ход и нагрузку текущей тренировки в личном контексте."),
    "uk": ("Детерміновано розраховується Fitness за вимірюваннями поточного тренування.", "Допомагає оцінювати перебіг і навантаження поточного тренування у власному контексті."),
    "tr": ("Fitness tarafından mevcut antrenman sırasında toplanan ölçümlerden deterministik olarak hesaplanır.", "Mevcut antrenmanın gidişini ve yükünü kişisel bağlamında anlamana yardımcı olur."),
    "zh": ("由 Fitness 根据当前训练期间采集的测量值进行确定性计算。", "帮助你结合个人情况理解当前训练的进展和负荷。"),
    "ja": ("現在のワークアウト中に収集した測定値から Fitness が決定論的に計算します。", "現在のワークアウトの推移と負荷を個人の状況に合わせて理解するのに役立ちます。"),
    "ko": ("현재 운동 중 수집된 측정값을 바탕으로 Fitness가 결정론적으로 계산합니다.", "현재 운동의 진행과 부하를 개인 맥락에서 이해하는 데 도움이 됩니다."),
}

def _code(language):
    return str(language or "en").lower().split("-")[0].split("_")[0]

def _citation(metric):
    ref=REFERENCES.get(_STUDY.get(metric, ""))
    if not ref: return None
    bits=[str(ref.get("title") or "").strip()]
    if ref.get("year"): bits.append(str(ref["year"]))
    if ref.get("pmid"): bits.append(f"PMID {ref['pmid']}")
    elif ref.get("doi"): bits.append(f"DOI {ref['doi']}")
    return " — ".join(x for x in bits if x)

def live_user_details(language, metric, data_used):
    code=_code(language)
    meaning, benefit = (_EL.get(metric) if code == "el" else _EN.get(metric) if code == "en" else _OTHER.get(code, _EN.get(metric, ("", ""))))
    out={"calculated_by_fitness": True}
    citation=_citation(metric)
    if citation: out["scientific_basis"]=citation
    formula=_FORMULA.get(metric)
    if formula: out["formula"]=formula
    if data_used: out["data_used"]=data_used
    if meaning: out["what_it_means"]=meaning
    if benefit: out["why_useful"]=benefit
    return out
