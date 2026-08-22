"""Canonical planned workouts and built-in fitness tests for Fitness."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

MAX_STEPS = 64
MAX_TEXT = 500

_AEROBIC_SPORTS = {
    "cycling", "indoor_cycling", "running", "treadmill", "walking", "hiking",
    "rowing", "swimming", "elliptical", "cardio", "cross_country_skiing",
}
_ZONE_FOR_INTENSITY = {
    "recovery": "zone_1",
    "very_light": "zone_1",
    "light": "zone_2",
    "moderate": "zone_3",
    "vigorous": "zone_4",
    "near_maximal": "zone_5",
}


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    return str(value or "").strip()[:limit]


def _canonical_intensity(value: Any) -> str:
    """Return one stable intensity token from AI/manual target wording."""
    text = _text(value, 80).lower().replace("-", "_").replace(" ", "_")
    if not text:
        return ""
    if text in {"recovery", "very_light", "light", "moderate", "vigorous", "near_maximal"}:
        return text
    if any(token in text for token in ("recovery", "recover", "cool_down", "cooldown", "very_easy")):
        return "recovery"
    if any(token in text for token in ("near_max", "maximal", "max_sustainable", "sprint", "all_out")):
        return "near_maximal"
    if any(token in text for token in ("vigorous", "threshold", "hard", "vo2", "interval")):
        return "vigorous"
    if any(token in text for token in ("moderate", "tempo", "steady", "aerobic")):
        return "moderate"
    if any(token in text for token in ("light", "easy", "warm_up", "warmup")):
        return "light"
    return text[:80]


def _canonical_zone(value: Any) -> str:
    """Normalize Zone 1..5 representations without inventing a zone."""
    text = _text(value, 40).lower().replace("-", "_").replace(" ", "_")
    if not text:
        return ""
    if text in {f"zone_{index}" for index in range(1, 6)}:
        return text
    if text.isdigit() and 1 <= int(text) <= 5:
        return f"zone_{int(text)}"
    for index in range(1, 6):
        if f"zone{index}" in text or f"zone_{index}" in text:
            return f"zone_{index}"
    return ""


def _normalize_training_target(
    target: dict[str, Any],
    *,
    sport: str,
    step_name: str,
    instruction: str,
    workout_intensity: str,
) -> dict[str, Any]:
    """Preserve target details while adding canonical intensity/zone metadata."""
    result = deepcopy(target)
    explicit_zone = _canonical_zone(result.get("training_zone") or result.get("zone"))
    intensity = _canonical_intensity(result.get("intensity") or result.get("effort"))
    hint = f"{step_name} {instruction}".lower()
    if not intensity:
        hinted = _canonical_intensity(hint)
        intensity = hinted if hinted in _ZONE_FOR_INTENSITY else ""
    # Warm-up/cool-down wording is more specific than an overall workout level.
    if not intensity:
        intensity = workout_intensity
    if intensity:
        result["intensity"] = intensity
    if explicit_zone:
        result["training_zone"] = explicit_zone
    elif sport in _AEROBIC_SPORTS and intensity in _ZONE_FOR_INTENSITY:
        result["training_zone"] = _ZONE_FOR_INTENSITY[intensity]
    result.pop("zone", None)
    return result


def normalize_prescription(raw: dict[str, Any], *, source: str = "fitness") -> dict[str, Any]:
    """Normalize an AI/manual/test workout into one bounded executable model."""
    if not isinstance(raw, dict):
        raise ValueError("prescription must be an object")
    sport = _text(raw.get("sport") or "other", 64).lower()
    workout_intensity = _canonical_intensity(raw.get("intensity"))
    workout_zone = _canonical_zone(raw.get("training_zone") or raw.get("zone"))
    if not workout_zone and sport in _AEROBIC_SPORTS and workout_intensity in _ZONE_FOR_INTENSITY:
        workout_zone = _ZONE_FOR_INTENSITY[workout_intensity]
    steps = []
    for index, item in enumerate(raw.get("steps") or []):
        if not isinstance(item, dict):
            continue
        duration = item.get("duration_seconds")
        try:
            duration = max(0, min(86400, int(duration))) if duration is not None else None
        except (TypeError, ValueError):
            duration = None
        reps = item.get("repetitions")
        try:
            reps = max(1, min(100, int(reps))) if reps is not None else None
        except (TypeError, ValueError):
            reps = None
        step_name = _text(item.get("name") or item.get("instruction") or f"Step {index + 1}", 120)
        instruction = _text(item.get("instruction") or item.get("name"), 500)
        target = _normalize_training_target(
            item.get("target") if isinstance(item.get("target"), dict) else {},
            sport=sport,
            step_name=step_name,
            instruction=instruction,
            workout_intensity=workout_intensity,
        )
        steps.append({
            "index": index,
            "name": step_name,
            "instruction": instruction,
            "duration_seconds": duration,
            "distance_m": item.get("distance_m"),
            "repetitions": reps,
            "target": target,
            "recovery_seconds": item.get("recovery_seconds"),
        })
        if len(steps) >= MAX_STEPS:
            break
    return {
        "schema_version": 1,
        "id": _text(raw.get("id"), 128),
        "source": _text(raw.get("source") or source, 64),
        "name": _text(raw.get("name") or raw.get("recommendation") or "Workout", 160),
        "sport": sport,
        "intensity": workout_intensity,
        "training_zone": workout_zone,
        "goal": _text(raw.get("goal"), 300),
        "notes": _text(raw.get("notes"), 1000),
        "duration_minutes": raw.get("duration_minutes"),
        "steps": steps,
    }


FITNESS_TESTS = {
    "running_cooper_12min": {
        "id": "running_cooper_12min", "name": "Cooper 12-minute run", "sport": "running",
        "goal": "Estimate aerobic running fitness from maximum sustainable distance in 12 minutes.",
        "steps": [
            {"name": "Warm up", "instruction": "Run easily and prepare for a hard continuous effort.", "duration_seconds": 600, "target": {"effort": "easy"}},
            {"name": "12-minute test", "instruction": "Cover as much distance as you safely can at an even hard effort.", "duration_seconds": 720, "target": {"effort": "max_sustainable"}},
            {"name": "Cool down", "instruction": "Walk or jog easily.", "duration_seconds": 600, "target": {"effort": "easy"}},
        ],
    },
    "cycling_ftp_20min": {
        "id": "cycling_ftp_20min", "name": "Cycling 20-minute FTP test", "sport": "cycling",
        "goal": "Record a controlled maximal 20-minute power effort for FTP estimation.",
        "steps": [
            {"name": "Warm up", "instruction": "Ride progressively from easy to moderate.", "duration_seconds": 900, "target": {"effort": "easy_to_moderate"}},
            {"name": "Openers", "instruction": "Ride three short hard efforts with easy recovery.", "duration_seconds": 360, "repetitions": 3, "target": {"effort": "hard"}},
            {"name": "Recovery", "instruction": "Ride easily before the test.", "duration_seconds": 300, "target": {"effort": "easy"}},
            {"name": "20-minute test", "instruction": "Hold the highest even power you can sustain for the full 20 minutes.", "duration_seconds": 1200, "target": {"metric": "power", "effort": "max_sustainable"}},
            {"name": "Cool down", "instruction": "Ride easily.", "duration_seconds": 600, "target": {"effort": "easy"}},
        ],
    },
    "strength_submax_1rm": {
        "id": "strength_submax_1rm", "name": "Submaximal strength test", "sport": "strength",
        "goal": "Estimate strength from a controlled submaximal set without requiring a true one-repetition maximum.",
        "steps": [
            {"name": "Specific warm up", "instruction": "Warm up the selected exercise with progressively heavier comfortable sets.", "duration_seconds": 600},
            {"name": "Test set", "instruction": "Perform one technically clean set with a known load, stopping before form breaks. Record load and repetitions.", "target": {"effort": "hard_submaximal"}},
            {"name": "Recovery", "instruction": "Finish the test and recover. Do not repeat a maximal set solely to improve the score.", "duration_seconds": 300},
        ],
    },
    "walking_6min": {
        "id": "walking_6min", "name": "6-minute walk test", "sport": "walking",
        "goal": "Track how much distance you can cover during a controlled six-minute brisk walk.",
        "steps": [
            {"name": "Warm up", "instruction": "Walk easily for five minutes and choose a flat, safe route where you can continue without stopping.", "duration_seconds": 300, "target": {"effort": "easy"}},
            {"name": "6-minute test", "instruction": "Walk as far as you comfortably can for six minutes. Keep walking; slow down if needed rather than sprinting.", "duration_seconds": 360, "target": {"effort": "hard_sustainable"}},
            {"name": "Cool down", "instruction": "Walk easily until breathing and heart rate settle.", "duration_seconds": 300, "target": {"effort": "easy"}},
        ],
    },
    "running_5k_time_trial": {
        "id": "running_5k_time_trial", "name": "5 km running time trial", "sport": "running",
        "goal": "Measure current 5 km running performance with an evenly paced maximal sustainable effort.",
        "steps": [
            {"name": "Warm up", "instruction": "Run easily, then include three short relaxed accelerations before the test.", "duration_seconds": 900, "target": {"effort": "easy"}},
            {"name": "5 km test", "instruction": "Run 5 km as evenly and quickly as you can sustain. Avoid an all-out sprint at the start.", "distance_m": 5000, "target": {"effort": "max_sustainable"}},
            {"name": "Cool down", "instruction": "Walk or jog easily after finishing the 5 km effort.", "duration_seconds": 600, "target": {"effort": "easy"}},
        ],
    },
    "cycling_5min_power": {
        "id": "cycling_5min_power", "name": "Cycling 5-minute power test", "sport": "cycling",
        "goal": "Track high aerobic cycling power with a repeatable five-minute maximal sustainable effort.",
        "steps": [
            {"name": "Warm up", "instruction": "Ride progressively from easy to moderate for fifteen minutes.", "duration_seconds": 900, "target": {"effort": "easy_to_moderate"}},
            {"name": "Openers", "instruction": "Complete three 20-second hard accelerations with easy riding between them.", "duration_seconds": 20, "repetitions": 3, "recovery_seconds": 100, "target": {"effort": "hard"}},
            {"name": "Recovery", "instruction": "Ride very easily before the test effort.", "duration_seconds": 300, "target": {"effort": "recovery"}},
            {"name": "5-minute test", "instruction": "Hold the highest even power you can sustain for the full five minutes.", "duration_seconds": 300, "target": {"metric": "power", "effort": "max_sustainable"}},
            {"name": "Cool down", "instruction": "Ride easily for at least ten minutes.", "duration_seconds": 600, "target": {"effort": "easy"}},
        ],
    },
    "rowing_2k": {
        "id": "rowing_2k", "name": "2 km rowing time trial", "sport": "rowing",
        "goal": "Measure repeatable 2 km rowing performance using time, pace, cadence and heart-rate data when available.",
        "steps": [
            {"name": "Warm up", "instruction": "Row easily, gradually increasing stroke rate and include three short firm efforts.", "duration_seconds": 900, "target": {"effort": "easy_to_moderate"}},
            {"name": "2 km test", "instruction": "Row 2000 m at the fastest pace you can sustain with controlled technique from start to finish.", "distance_m": 2000, "target": {"effort": "max_sustainable"}},
            {"name": "Cool down", "instruction": "Row very easily until breathing settles.", "duration_seconds": 600, "target": {"effort": "easy"}},
        ],
    },
    "swimming_css": {
        "id": "swimming_css", "name": "Swimming CSS test", "sport": "swimming",
        "goal": "Collect separate 400 m and 200 m time trials that can be used to track critical swim speed.",
        "steps": [
            {"name": "Warm up", "instruction": "Swim easily with a few short technique drills and relaxed accelerations.", "duration_seconds": 900, "target": {"effort": "easy"}},
            {"name": "400 m test", "instruction": "Swim 400 m as fast as you can sustain evenly. Record the total time.", "distance_m": 400, "target": {"effort": "max_sustainable"}},
            {"name": "Recovery", "instruction": "Swim very easily and recover fully before the shorter test.", "duration_seconds": 600, "target": {"effort": "recovery"}},
            {"name": "200 m test", "instruction": "Swim 200 m as fast as you can sustain with good technique. Record the total time.", "distance_m": 200, "target": {"effort": "max_sustainable"}},
            {"name": "Cool down", "instruction": "Swim easily for several minutes.", "duration_seconds": 600, "target": {"effort": "easy"}},
        ],
    },
    "strength_pushups_2min": {
        "id": "strength_pushups_2min", "name": "2-minute push-up test", "sport": "strength",
        "goal": "Track upper-body muscular endurance with consistent push-up technique.",
        "steps": [
            {"name": "Warm up", "instruction": "Warm shoulders, wrists and upper body, then perform a few easy practice repetitions.", "duration_seconds": 300},
            {"name": "2-minute test", "instruction": "Perform controlled push-ups for two minutes. Count only repetitions completed with the same full range of motion.", "duration_seconds": 120, "target": {"metric": "repetitions", "effort": "max_sustainable"}},
            {"name": "Recovery", "instruction": "Stop the test, record the valid repetition count and recover.", "duration_seconds": 300},
        ],
    },
    "strength_plank_hold": {
        "id": "strength_plank_hold", "name": "Plank hold test", "sport": "strength",
        "goal": "Track trunk endurance using a repeatable strict plank position.",
        "steps": [
            {"name": "Set up", "instruction": "Warm up briefly, then set elbows under shoulders with a straight line from shoulders through heels.", "duration_seconds": 180},
            {"name": "Hold test", "instruction": "Hold the strict plank as long as good form is maintained. End the test when posture can no longer be held correctly.", "target": {"metric": "duration", "effort": "max_sustainable"}},
            {"name": "Recovery", "instruction": "Stop the timer, record the completed hold duration and recover.", "duration_seconds": 180},
        ],
    },
}


_TEST_LOCALIZATION: dict[str, dict[str, dict[str, Any]]] = {
    "de": {
        "running_cooper_12min": {"name":"Cooper-12-Minuten-Lauf","goal":"Schätze die aerobe Laufleistung anhand der maximal nachhaltig zurückgelegten Distanz in 12 Minuten.","steps":[("Aufwärmen","Laufe locker und bereite dich auf eine harte, gleichmäßige Belastung vor."),("12-Minuten-Test","Lege in 12 Minuten so viel Strecke wie sicher möglich zurück und halte die Belastung möglichst gleichmäßig."),("Abkühlen","Gehe oder jogge locker.")]},
        "cycling_ftp_20min": {"name":"20-Minuten-FTP-Test Radfahren","goal":"Erfasse eine kontrollierte maximale 20-Minuten-Leistung zur FTP-Schätzung.","steps":[("Aufwärmen","Fahre progressiv von locker bis moderat."),("Aktivierungen","Fahre drei kurze harte Belastungen mit lockerer Erholung dazwischen."),("Erholung","Fahre locker vor dem Test."),("20-Minuten-Test","Halte die höchste gleichmäßige Leistung, die du über die gesamten 20 Minuten aufrechterhalten kannst."),("Abkühlen","Fahre locker.")]},
        "strength_submax_1rm": {"name":"Submaximaler Krafttest","goal":"Schätze die Kraft aus einem kontrollierten submaximalen Satz, ohne ein echtes Ein-Wiederholungs-Maximum zu benötigen.","steps":[("Spezifisches Aufwärmen","Wärme die gewählte Übung mit zunehmend schwereren, aber komfortablen Sätzen auf."),("Testsatz","Führe einen technisch sauberen Satz mit bekanntem Gewicht aus und stoppe, bevor die Technik nachlässt. Gewicht und Wiederholungen notieren."),("Erholung","Beende den Test und erhole dich. Wiederhole keinen Maximalsatz nur, um das Ergebnis zu verbessern.")]},
        "walking_6min": {"name":"6-Minuten-Gehtest","goal":"Verfolge, welche Distanz du in sechs Minuten zügigem, kontrolliertem Gehen zurücklegen kannst.","steps":[("Aufwärmen","Gehe fünf Minuten locker und wähle eine flache, sichere Strecke, auf der du ohne Unterbrechung weitergehen kannst."),("6-Minuten-Test","Gehe sechs Minuten so weit, wie es dir angenehm möglich ist. Gehe weiter und reduziere bei Bedarf das Tempo, statt zu sprinten."),("Abkühlen","Gehe locker, bis sich Atmung und Herzfrequenz beruhigen.")]},
        "running_5k_time_trial": {"name":"5-km-Lauf-Zeitfahren","goal":"Miss deine aktuelle 5-km-Leistung mit einer gleichmäßig eingeteilten maximal nachhaltigen Belastung.","steps":[("Aufwärmen","Laufe locker und baue anschließend drei kurze, entspannte Steigerungen ein."),("5-km-Test","Laufe 5 km so gleichmäßig und schnell, wie du es durchhalten kannst. Vermeide einen Vollsprint direkt am Start."),("Abkühlen","Gehe oder jogge nach dem 5-km-Lauf locker aus.")]},
        "cycling_5min_power": {"name":"5-Minuten-Leistungstest Radfahren","goal":"Verfolge die hohe aerobe Radleistung mit einer wiederholbaren fünfminütigen maximal nachhaltigen Belastung.","steps":[("Aufwärmen","Fahre 15 Minuten progressiv von locker bis moderat."),("Aktivierungen","Fahre drei harte Beschleunigungen über 20 Sekunden mit lockerer Fahrt dazwischen."),("Erholung","Fahre vor dem Test sehr locker."),("5-Minuten-Test","Halte die höchste gleichmäßige Leistung, die du über die vollen fünf Minuten aufrechterhalten kannst."),("Abkühlen","Fahre mindestens zehn Minuten locker.")]},
        "rowing_2k": {"name":"2-km-Ruder-Zeitfahren","goal":"Miss eine wiederholbare 2-km-Ruderleistung anhand von Zeit, Pace, Schlagfrequenz und Herzfrequenz, sofern verfügbar.","steps":[("Aufwärmen","Rudere locker, erhöhe schrittweise die Schlagfrequenz und baue drei kurze kräftige Belastungen ein."),("2-km-Test","Rudere 2000 m mit dem schnellsten Tempo, das du vom Start bis zum Ziel mit kontrollierter Technik halten kannst."),("Abkühlen","Rudere sehr locker, bis sich die Atmung beruhigt.")]},
        "swimming_css": {"name":"Schwimm-CSS-Test","goal":"Erfasse getrennte 400-m- und 200-m-Zeitfahren, um die kritische Schwimmgeschwindigkeit zu verfolgen.","steps":[("Aufwärmen","Schwimme locker mit einigen kurzen Technikübungen und entspannten Beschleunigungen."),("400-m-Test","Schwimme 400 m so schnell wie möglich bei gleichmäßiger Belastung. Gesamtzeit notieren."),("Erholung","Schwimme sehr locker und erhole dich vollständig vor dem kürzeren Test."),("200-m-Test","Schwimme 200 m so schnell wie möglich mit guter Technik. Gesamtzeit notieren."),("Abkühlen","Schwimme einige Minuten locker.")]},
        "strength_pushups_2min": {"name":"2-Minuten-Liegestütztest","goal":"Verfolge die Kraftausdauer des Oberkörpers mit gleichbleibender Liegestütztechnik.","steps":[("Aufwärmen","Wärme Schultern, Handgelenke und Oberkörper auf und mache einige lockere Probewiederholungen."),("2-Minuten-Test","Führe zwei Minuten lang kontrollierte Liegestütze aus. Zähle nur Wiederholungen mit derselben vollständigen Bewegungsamplitude."),("Erholung","Beende den Test, notiere die gültigen Wiederholungen und erhole dich.")]},
        "strength_plank_hold": {"name":"Unterarmstütz-Haltetest","goal":"Verfolge die Rumpfausdauer mit einer wiederholbaren, sauberen Plank-Position.","steps":[("Vorbereitung","Wärme dich kurz auf und positioniere die Ellbogen unter den Schultern; halte eine gerade Linie von den Schultern bis zu den Fersen."),("Haltetest","Halte die saubere Plank-Position so lange, wie du die korrekte Form bewahren kannst. Beende den Test, sobald die Haltung nicht mehr sauber gehalten werden kann."),("Erholung","Stoppe die Zeit, notiere die erreichte Haltedauer und erhole dich.")]},
    },
    "el": {
        "running_cooper_12min": {"name":"Τεστ Cooper 12 λεπτών","goal":"Εκτίμησε την αερόβια δρομική ικανότητα από τη μέγιστη βιώσιμη απόσταση σε 12 λεπτά.","steps":[("Ζέσταμα","Τρέξε χαλαρά και προετοιμάσου για μια έντονη συνεχόμενη προσπάθεια."),("Τεστ 12 λεπτών","Κάλυψε όσο μεγαλύτερη απόσταση μπορείς με ασφάλεια σε 12 λεπτά, με όσο γίνεται σταθερή ένταση."),("Αποθεραπεία","Περπάτησε ή τρέξε πολύ χαλαρά.")]},
        "cycling_ftp_20min": {"name":"Τεστ FTP ποδηλασίας 20 λεπτών","goal":"Κατέγραψε μια ελεγχόμενη μέγιστη προσπάθεια 20 λεπτών για εκτίμηση FTP.","steps":[("Ζέσταμα","Ποδηλάτησε προοδευτικά από χαλαρά έως μέτρια."),("Ανοίγματα","Κάνε τρεις σύντομες δυνατές προσπάθειες με χαλαρή αποκατάσταση ανάμεσά τους."),("Αποκατάσταση","Ποδηλάτησε χαλαρά πριν από το τεστ."),("Τεστ 20 λεπτών","Κράτησε την υψηλότερη ομοιόμορφη ισχύ που μπορείς να διατηρήσεις για ολόκληρα τα 20 λεπτά."),("Αποθεραπεία","Ποδηλάτησε χαλαρά.")]},
        "strength_submax_1rm": {"name":"Υπομέγιστο τεστ δύναμης","goal":"Εκτίμησε τη δύναμη από ένα ελεγχόμενο υπομέγιστο σετ χωρίς πραγματική προσπάθεια μίας μέγιστης επανάληψης.","steps":[("Ειδικό ζέσταμα","Ζεστάσου στην επιλεγμένη άσκηση με προοδευτικά βαρύτερα αλλά άνετα σετ."),("Σετ τεστ","Κάνε ένα τεχνικά καθαρό σετ με γνωστό φορτίο και σταμάτησε πριν χαλάσει η τεχνική. Κατέγραψε βάρος και επαναλήψεις."),("Αποκατάσταση","Ολοκλήρωσε το τεστ και αναρρώσε. Μην επαναλάβεις μέγιστο σετ μόνο για να βελτιώσεις το σκορ.")]},
        "walking_6min": {"name":"Τεστ βάδισης 6 λεπτών","goal":"Παρακολούθησε πόση απόσταση καλύπτεις σε έξι λεπτά ελεγχόμενου γρήγορου βαδίσματος.","steps":[("Ζέσταμα","Περπάτησε χαλαρά για πέντε λεπτά και διάλεξε επίπεδη ασφαλή διαδρομή χωρίς αναγκαστικές στάσεις."),("Τεστ 6 λεπτών","Περπάτησε όσο πιο μακριά μπορείς άνετα για έξι λεπτά. Συνέχισε να περπατάς και μείωσε ρυθμό αν χρειάζεται αντί να σπριντάρεις."),("Αποθεραπεία","Περπάτησε χαλαρά μέχρι να ηρεμήσουν αναπνοή και καρδιακός ρυθμός.")]},
        "running_5k_time_trial": {"name":"Χρονομέτρηση τρεξίματος 5 km","goal":"Μέτρησε την τρέχουσα επίδοση στα 5 km με ομοιόμορφα κατανεμημένη μέγιστη βιώσιμη προσπάθεια.","steps":[("Ζέσταμα","Τρέξε χαλαρά και πρόσθεσε τρεις σύντομες άνετες επιταχύνσεις πριν από το τεστ."),("Τεστ 5 km","Τρέξε 5 km όσο πιο ομοιόμορφα και γρήγορα μπορείς να διατηρήσεις. Απόφυγε το απόλυτο σπριντ στην εκκίνηση."),("Αποθεραπεία","Περπάτησε ή τρέξε χαλαρά μετά την ολοκλήρωση των 5 km.")]},
        "cycling_5min_power": {"name":"Τεστ ισχύος ποδηλασίας 5 λεπτών","goal":"Παρακολούθησε υψηλή αερόβια ισχύ ποδηλασίας με επαναλήψιμη μέγιστη βιώσιμη προσπάθεια πέντε λεπτών.","steps":[("Ζέσταμα","Ποδηλάτησε προοδευτικά από χαλαρά έως μέτρια για 15 λεπτά."),("Ανοίγματα","Κάνε τρεις δυνατές επιταχύνσεις 20 δευτερολέπτων με χαλαρή ποδηλασία ανάμεσά τους."),("Αποκατάσταση","Ποδηλάτησε πολύ χαλαρά πριν από την προσπάθεια τεστ."),("Τεστ 5 λεπτών","Κράτησε την υψηλότερη ομοιόμορφη ισχύ που μπορείς να διατηρήσεις για ολόκληρα τα πέντε λεπτά."),("Αποθεραπεία","Ποδηλάτησε χαλαρά για τουλάχιστον δέκα λεπτά.")]},
        "rowing_2k": {"name":"Χρονομέτρηση κωπηλασίας 2 km","goal":"Μέτρησε επαναλήψιμη επίδοση 2 km με χρόνο, ρυθμό, συχνότητα κουπιών και καρδιακό ρυθμό όπου είναι διαθέσιμα.","steps":[("Ζέσταμα","Κωπηλάτησε χαλαρά, αύξησε σταδιακά τη συχνότητα και πρόσθεσε τρεις σύντομες δυνατές προσπάθειες."),("Τεστ 2 km","Κωπηλάτησε 2000 m στον ταχύτερο ρυθμό που μπορείς να διατηρήσεις με ελεγχόμενη τεχνική από την αρχή ως το τέλος."),("Αποθεραπεία","Κωπηλάτησε πολύ χαλαρά μέχρι να ηρεμήσει η αναπνοή.")]},
        "swimming_css": {"name":"Τεστ CSS κολύμβησης","goal":"Κατέγραψε ξεχωριστές χρονομετρήσεις 400 m και 200 m για παρακολούθηση της κρίσιμης ταχύτητας κολύμβησης.","steps":[("Ζέσταμα","Κολύμπησε χαλαρά με μερικές σύντομες ασκήσεις τεχνικής και άνετες επιταχύνσεις."),("Τεστ 400 m","Κολύμπησε 400 m όσο πιο γρήγορα μπορείς με ομοιόμορφη προσπάθεια. Κατέγραψε τον συνολικό χρόνο."),("Αποκατάσταση","Κολύμπησε πολύ χαλαρά και αναρρώσε πλήρως πριν από το μικρότερο τεστ."),("Τεστ 200 m","Κολύμπησε 200 m όσο πιο γρήγορα μπορείς με καλή τεχνική. Κατέγραψε τον συνολικό χρόνο."),("Αποθεραπεία","Κολύμπησε χαλαρά για μερικά λεπτά.")]},
        "strength_pushups_2min": {"name":"Τεστ κάμψεων 2 λεπτών","goal":"Παρακολούθησε τη μυϊκή αντοχή του άνω σώματος με σταθερή τεχνική κάμψεων.","steps":[("Ζέσταμα","Ζέστανε ώμους, καρπούς και άνω σώμα και κάνε μερικές εύκολες δοκιμαστικές επαναλήψεις."),("Τεστ 2 λεπτών","Κάνε ελεγχόμενες κάμψεις για δύο λεπτά. Μέτρα μόνο επαναλήψεις με το ίδιο πλήρες εύρος κίνησης."),("Αποκατάσταση","Σταμάτησε το τεστ, κατέγραψε τις έγκυρες επαναλήψεις και αναρρώσε.")]},
        "strength_plank_hold": {"name":"Τεστ σανίδας","goal":"Παρακολούθησε την αντοχή του κορμού με επαναλήψιμη αυστηρή θέση σανίδας.","steps":[("Προετοιμασία","Ζεστάσου σύντομα και τοποθέτησε τους αγκώνες κάτω από τους ώμους, κρατώντας ευθεία γραμμή από τους ώμους μέχρι τις φτέρνες."),("Τεστ κράτησης","Κράτησε την αυστηρή σανίδα όσο διατηρείται σωστή τεχνική. Τερμάτισε το τεστ όταν δεν μπορείς πλέον να κρατήσεις σωστή θέση."),("Αποκατάσταση","Σταμάτησε το χρονόμετρο, κατέγραψε τη διάρκεια και αναρρώσε.")]},
    },
}


def _localized_test(raw: dict[str, Any], language: str | None) -> dict[str, Any]:
    result = deepcopy(raw)
    code = str(language or "en").lower().split("-")[0].split("_")[0]
    copy = _TEST_LOCALIZATION.get(code, {}).get(str(result.get("id") or ""))
    if not copy:
        return result
    result["name"] = copy.get("name", result.get("name"))
    result["goal"] = copy.get("goal", result.get("goal"))
    translated_steps = list(copy.get("steps") or [])
    for index, step in enumerate(result.get("steps") or []):
        if index >= len(translated_steps):
            break
        name, instruction = translated_steps[index]
        step["name"] = name
        step["instruction"] = instruction
    return result


def fitness_test_catalog(language: str | None = None) -> list[dict[str, Any]]:
    return [normalize_prescription({**_localized_test(value, language), "source": "fitness_test"}) for value in FITNESS_TESTS.values()]


def fitness_test(test_id: str, language: str | None = None) -> dict[str, Any]:
    raw = FITNESS_TESTS.get(str(test_id))
    if raw is None:
        raise KeyError(test_id)
    return normalize_prescription({**_localized_test(raw, language), "source": "fitness_test"})
