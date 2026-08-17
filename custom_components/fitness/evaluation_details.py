"""Localized, user-facing scientific details for Evaluation entities."""

from __future__ import annotations

from .research.references import REFERENCES
from .scientific_translations import EVALUATION_FORMULAS

_LABELS = {
    "en": {"study":"Scientific basis","formula":"Formula","data":"Data used","meaning":"What this means","benefit":"Why this is useful"},
    "el": {"study":"Επιστημονική βάση","formula":"Τύπος","data":"Δεδομένα που χρησιμοποιήθηκαν","meaning":"Τι σημαίνει","benefit":"Γιατί είναι χρήσιμο"},
    "de": {"study":"Wissenschaftliche Grundlage","formula":"Formel","data":"Verwendete Daten","meaning":"Was das bedeutet","benefit":"Warum das nützlich ist"},
    "fr": {"study":"Base scientifique","formula":"Formule","data":"Données utilisées","meaning":"Ce que cela signifie","benefit":"Pourquoi c’est utile"},
    "es": {"study":"Base científica","formula":"Fórmula","data":"Datos utilizados","meaning":"Qué significa","benefit":"Por qué es útil"},
    "it": {"study":"Base scientifica","formula":"Formula","data":"Dati utilizzati","meaning":"Cosa significa","benefit":"Perché è utile"},
    "pt": {"study":"Base científica","formula":"Fórmula","data":"Dados utilizados","meaning":"O que significa","benefit":"Porque é útil"},
    "nl": {"study":"Wetenschappelijke basis","formula":"Formule","data":"Gebruikte gegevens","meaning":"Wat dit betekent","benefit":"Waarom dit nuttig is"},
    "pl": {"study":"Podstawa naukowa","formula":"Wzór","data":"Użyte dane","meaning":"Co to oznacza","benefit":"Dlaczego to jest przydatne"},
    "ru": {"study":"Научная основа","formula":"Формула","data":"Использованные данные","meaning":"Что это означает","benefit":"Чем это полезно"},
    "uk": {"study":"Наукова основа","formula":"Формула","data":"Використані дані","meaning":"Що це означає","benefit":"Чому це корисно"},
    "tr": {"study":"Bilimsel dayanak","formula":"Formül","data":"Kullanılan veriler","meaning":"Bu ne anlama gelir","benefit":"Neden faydalıdır"},
    "zh": {"study":"科学依据","formula":"公式","data":"使用的数据","meaning":"这意味着什么","benefit":"为什么有用"},
    "ja": {"study":"科学的根拠","formula":"計算式","data":"使用したデータ","meaning":"この指標の意味","benefit":"役立つ理由"},
    "ko": {"study":"과학적 근거","formula":"계산식","data":"사용한 데이터","meaning":"이 지표의 의미","benefit":"유용한 이유"},
}

# Concise domain explanations. Published study titles remain in their canonical
# bibliographic language; the explanation and practical value are localized.
_TEXT = {
    "en": {
        "sleep_consistency": ("Describes how stable your sleep duration and timing are across recent nights.", "Helps distinguish a repeatable sleep routine from large night-to-night variation without treating variability as a diagnosis."),
        "sleep_deficit_7d": ("Adds each night’s shortfall below the adult consensus minimum of 7 hours across the last 7 days. Longer nights do not mathematically erase a shorter night.", "Makes repeated insufficient sleep visible while avoiding the unsupported assumption that extra sleep repays sleep loss hour-for-hour."),
        "autonomic_recovery_trend": ("Compares recent nightly HRV and resting heart rate with your own recent baseline.", "Helps monitor within-person recovery trends while avoiding a proprietary readiness score."),
        "cardiorespiratory_fitness_trend": ("Shows the direction of your measured/provider VO₂max over time and its position relative to an age/sex/weight reference equation.", "Helps separate a real longer-term fitness trend from normal day-to-day measurement variation."),
        "training_load": ("Summarizes recent training exposure using workout duration, frequency, distance and heart-rate-based TRIMP when available.", "Helps compare recent exercise stress with your own longer baseline without claiming an injury-risk percentage."),
        "heart_rate_recovery": ("Measures how many beats per minute heart rate falls after exercise, especially after 60 seconds.", "Helps follow post-exercise autonomic recovery over time using comparable workouts and your personal baseline."),
        "training_recovery_relationship": ("Looks for a personal statistical association between workout load and the following sleep/recovery observations.", "Can reveal patterns worth noticing, but the relationship is descriptive and does not prove that training caused the change."),
        "vo2max_percent_predicted": ("Compares your measured/provider VO₂max with the FRIEND reference equation for age, sex and body mass.", "Provides population-reference context while keeping your actual measured VO₂max separate from the reference estimate."),
        "readiness": ("Combines your personal autonomic recovery, recent sleep, training recovery and post-exercise recovery response into one transparent readiness estimate.", "Helps decide how prepared you appear for training now while keeping every contributing Fitness signal inspectable."),
        "training_adaptation_status": ("Classifies the recent training response from personal load exposure, cardiorespiratory trend and recovery evidence. Load alone cannot establish productive adaptation or overtraining.", "Helps distinguish improving, maintaining, insufficient, high-load and recovery-strained patterns without presenting the result as a medical diagnosis."),
    },
    "el": {
        "sleep_consistency": ("Περιγράφει πόσο σταθερά είναι η διάρκεια και το ωράριο του ύπνου σου στις πρόσφατες νύχτες.", "Σε βοηθά να ξεχωρίζεις μια σταθερή ρουτίνα ύπνου από μεγάλες διακυμάνσεις χωρίς να αντιμετωπίζει τη μεταβλητότητα ως διάγνωση."),
        "sleep_deficit_7d": ("Αθροίζει για τις τελευταίες 7 ημέρες την έλλειψη κάθε νύχτας κάτω από την ελάχιστη σύσταση των 7 ωρών για ενήλικες. Οι μεγαλύτερες νύχτες δεν διαγράφουν μαθηματικά μια μικρότερη νύχτα.", "Κάνει ορατό τον επαναλαμβανόμενο ανεπαρκή ύπνο χωρίς να υποθέτει ότι ο επιπλέον ύπνος αποπληρώνει την απώλεια ύπνου ώρα προς ώρα."),
        "autonomic_recovery_trend": ("Συγκρίνει το πρόσφατο νυχτερινό HRV και τους καρδιακούς παλμούς ηρεμίας με το δικό σου πρόσφατο σημείο αναφοράς.", "Βοηθά να παρακολουθείς την προσωπική τάση αποκατάστασης χωρίς να επινοεί έναν ιδιόκτητο δείκτη ετοιμότητας."),
        "cardiorespiratory_fitness_trend": ("Δείχνει την πορεία του μετρημένου ή παρεχόμενου VO₂max με τον χρόνο και τη σχέση του με εξίσωση αναφοράς βάσει ηλικίας, φύλου και βάρους.", "Σε βοηθά να ξεχωρίζεις μια πραγματική μακροχρόνια αλλαγή φυσικής κατάστασης από τις φυσιολογικές διακυμάνσεις των μετρήσεων."),
        "training_load": ("Συνοψίζει την πρόσφατη προπονητική επιβάρυνση από διάρκεια, συχνότητα, απόσταση και καρδιοσυχνομετρικό TRIMP όταν υπάρχουν τα απαραίτητα δεδομένα.", "Σε βοηθά να συγκρίνεις την πρόσφατη επιβάρυνση με το δικό σου ιστορικό χωρίς να παρουσιάζει αυθαίρετο ποσοστό κινδύνου τραυματισμού."),
        "heart_rate_recovery": ("Μετρά πόσους παλμούς ανά λεπτό πέφτει ο καρδιακός ρυθμός μετά το τέλος της άσκησης, ιδιαίτερα στα 60 δευτερόλεπτα.", "Σε βοηθά να παρακολουθείς την αποκατάσταση μετά την άσκηση διαχρονικά και σε σύγκριση με το προσωπικό σου σημείο αναφοράς."),
        "training_recovery_relationship": ("Αναζητά προσωπική στατιστική συσχέτιση ανάμεσα στο προπονητικό φορτίο και στον επόμενο ύπνο ή στις μετρήσεις αποκατάστασης.", "Μπορεί να αναδείξει χρήσιμα προσωπικά μοτίβα, αλλά η συσχέτιση είναι περιγραφική και δεν αποδεικνύει ότι η προπόνηση προκάλεσε την αλλαγή."),
        "vo2max_percent_predicted": ("Συγκρίνει το μετρημένο ή παρεχόμενο VO₂max με την εξίσωση αναφοράς FRIEND για ηλικία, φύλο και σωματικό βάρος.", "Δίνει πλαίσιο σύγκρισης με πληθυσμιακή τιμή αναφοράς χωρίς να αντικαθιστά το πραγματικό μετρημένο VO₂max."),
        "readiness": ("Συνδυάζει την προσωπική αυτόνομη αποκατάσταση, τον πρόσφατο ύπνο, την αποκατάσταση από την προπόνηση και την απόκριση μετά την άσκηση σε έναν διαφανή δείκτη ετοιμότητας.", "Σε βοηθά να εκτιμήσεις πόσο έτοιμος φαίνεσαι για προπόνηση τώρα, με όλα τα επιμέρους δεδομένα του Fitness διαθέσιμα για έλεγχο."),
        "training_adaptation_status": ("Ταξινομεί την πρόσφατη απόκριση στην προπόνηση από το προσωπικό φορτίο, την τάση καρδιοαναπνευστικής ικανότητας και τα δεδομένα αποκατάστασης. Το φορτίο μόνο του δεν αποδεικνύει παραγωγική προσαρμογή ή υπερπροπόνηση.", "Βοηθά να ξεχωρίζεις μοτίβα βελτίωσης, διατήρησης, ανεπαρκούς ερεθίσματος, υψηλού φορτίου και καταπόνησης χωρίς να παρουσιάζει το αποτέλεσμα ως ιατρική διάγνωση."),
    },
}

# Other supported languages use concise native domain wording. This keeps the
# UI localized while canonical study titles/formulas remain scientifically exact.
_OTHER = {
    "de": ("Beschreibt die wissenschaftlich abgeleitete Entwicklung dieses Fitnessbereichs aus deinen verfügbaren Messungen.", "Hilft, Veränderungen mit deiner eigenen Historie einzuordnen, ohne daraus eine Diagnose abzuleiten."),
    "fr": ("Décrit l’évolution scientifiquement dérivée de ce domaine à partir de tes mesures disponibles.", "Aide à interpréter les changements par rapport à ton propre historique sans en faire un diagnostic."),
    "es": ("Describe la evolución de este ámbito de fitness derivada científicamente a partir de tus mediciones disponibles.", "Ayuda a interpretar los cambios frente a tu propio historial sin convertirlos en un diagnóstico."),
    "it": ("Descrive l'andamento di quest'area fitness derivato scientificamente dai dati disponibili.", "Aiuta a interpretare i cambiamenti rispetto alla tua storia personale senza trasformarli in una diagnosi."),
    "pt": ("Descreve a evolução cientificamente derivada desta área de fitness a partir das medições disponíveis.", "Ajuda a interpretar alterações face ao teu próprio histórico sem as transformar num diagnóstico."),
    "nl": ("Beschrijft de wetenschappelijk afgeleide ontwikkeling van dit fitnessdomein op basis van je beschikbare metingen.", "Helpt veranderingen tegenover je eigen historie te begrijpen zonder er een diagnose van te maken."),
    "pl": ("Opisuje naukowo wyprowadzony trend tego obszaru na podstawie dostępnych pomiarów.", "Pomaga oceniać zmiany względem własnej historii bez traktowania ich jako diagnozy."),
    "ru": ("Показывает научно обоснованную динамику этого аспекта физической формы по доступным измерениям.", "Помогает оценивать изменения относительно вашей собственной истории, не превращая их в диагноз."),
    "uk": ("Показує науково обґрунтовану динаміку цього аспекту фізичної форми за доступними вимірюваннями.", "Допомагає оцінювати зміни відносно власної історії, не перетворюючи їх на діагноз."),
    "tr": ("Mevcut ölçümlerinden bu fitness alanının bilimsel olarak türetilmiş eğilimini gösterir.", "Değişimleri kendi geçmişinle karşılaştırmana yardımcı olur; tanı koymaz."),
    "zh": ("根据可用测量数据，以有科学依据的方法描述这一体能领域的变化趋势。", "帮助你与自己的历史数据比较变化，而不是把结果当作诊断。"),
    "ja": ("利用可能な測定値から、このフィットネス領域の変化を科学的根拠に基づいて示します。", "診断を行わず、自分自身の履歴と比較して変化を理解するのに役立ちます。"),
    "ko": ("사용 가능한 측정값을 바탕으로 이 피트니스 영역의 변화를 과학적 근거에 따라 보여 줍니다.", "진단으로 해석하지 않고 자신의 과거 데이터와 비교해 변화를 이해하는 데 도움이 됩니다."),
}

_STUDY = {
    "sleep_consistency": "sleep_regularity_metrics_2021",
    "sleep_deficit_7d": "adult_sleep_duration_consensus_2015",
    "autonomic_recovery_trend": "hrv_training_status_meta_2016",
    "cardiorespiratory_fitness_trend": "cardiorespiratory_fitness_meta_2024",
    "training_load": "training_load_consensus_2017",
    "heart_rate_recovery": "heart_rate_recovery_1999",
    "training_recovery_relationship": "exercise_sleep_meta_2024",
    "vo2max_percent_predicted": "friend_2017",
    "readiness": "hrv_training_status_meta_2016",
    "training_adaptation_status": "training_load_consensus_2017",
}

def _code(language: str | None) -> str:
    code = str(language or "en").lower().split("-")[0].split("_")[0]
    return code if code in _LABELS else "en"


def study_citation(metric: str) -> str | None:
    ref = REFERENCES.get(_STUDY.get(metric, ""))
    if not ref:
        return None
    bits = [str(ref.get("title") or "").strip()]
    if ref.get("year"):
        bits.append(str(ref["year"]))
    if ref.get("pmid"):
        bits.append(f"PMID {ref['pmid']}")
    elif ref.get("doi"):
        bits.append(f"DOI {ref['doi']}")
    return " — ".join(bit for bit in bits if bit)


def evaluation_user_details(language: str | None, metric: str, data_used: list[str]) -> dict:
    """Return stable-key scientific metadata; HA translates attribute labels."""
    code = _code(language)
    if code in _TEXT and metric in _TEXT[code]:
        meaning, benefit = _TEXT[code][metric]
    else:
        meaning, benefit = _OTHER.get(code, _TEXT["en"].get(metric, ("", "")))
    result = {}
    citation = study_citation(metric)
    if citation:
        result["scientific_basis"] = citation
    if metric == "readiness":
        additional = []
        for key in ("adult_sleep_duration_consensus_2015", "training_load_consensus_2017", "heart_rate_recovery_1999"):
            ref = REFERENCES.get(key)
            if not ref:
                continue
            bits = [str(ref.get("title") or "").strip()]
            if ref.get("year"):
                bits.append(str(ref["year"]))
            if ref.get("pmid"):
                bits.append(f"PMID {ref['pmid']}")
            elif ref.get("doi"):
                bits.append(f"DOI {ref['doi']}")
            additional.append(" — ".join(bit for bit in bits if bit))
        if additional:
            result["additional_scientific_basis"] = additional
    formula = EVALUATION_FORMULAS[code].get(metric)
    if formula:
        result["formula"] = formula
    if data_used:
        result["data_used"] = data_used
    if meaning:
        result["what_it_means"] = meaning
    if benefit:
        result["why_useful"] = benefit
    return result
