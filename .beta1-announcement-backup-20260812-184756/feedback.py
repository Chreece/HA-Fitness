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





_SESSION_MESSAGES = {
    "en": {
        "waiting_live": "Workout started. Waiting for live sensor data before the workout timer starts.",
        "started_with_live": "Workout started. Live data is available from {sensors}; the timer has started.",
        "live_available": "Live data is now available from {sensors}. The workout timer has started. You can begin your workout.",
        "stopped_without_live": "Workout stopped before live sensor data became available. No live workout was recorded.",
        "recovery_wait": "Workout ended. Please wait while post-exercise heart-rate recovery is collected for the next 120 seconds.",
        "recovery_checkpoint": "{seconds}-second heart-rate recovery data collected. {remaining} seconds remaining.",
        "recovery_checkpoint_missing": "No heart-rate value was available at the {seconds}-second recovery checkpoint. Continuing; {remaining} seconds remaining.",
        "recovery_complete": "Post-exercise heart-rate recovery collection is complete. All available recovery data has been saved. Everything is ready.",
        "no_recovery": "Workout ended. Post-exercise heart-rate recovery could not be collected because no usable heart-rate data was available.",
    },
    "el": {
        "waiting_live": "Η προπόνηση ξεκίνησε. Περιμένω ζωντανά δεδομένα από τους αισθητήρες πριν ξεκινήσει το χρονόμετρο.",
        "started_with_live": "Η προπόνηση ξεκίνησε. Υπάρχουν ζωντανά δεδομένα από {sensors} και το χρονόμετρο ξεκίνησε.",
        "live_available": "Τα ζωντανά δεδομένα από {sensors} είναι τώρα διαθέσιμα. Το χρονόμετρο ξεκίνησε. Μπορείς να αρχίσεις την προπόνησή σου.",
        "stopped_without_live": "Η προπόνηση σταμάτησε πριν εμφανιστούν ζωντανά δεδομένα αισθητήρων. Δεν καταγράφηκε ζωντανή προπόνηση.",
        "recovery_wait": "Η προπόνηση τελείωσε. Περίμενε ενώ συλλέγεται η αποκατάσταση καρδιακού ρυθμού μετά την άσκηση για τα επόμενα 120 δευτερόλεπτα.",
        "recovery_checkpoint": "Συλλέχθηκαν τα δεδομένα αποκατάστασης καρδιακού ρυθμού στα {seconds} δευτερόλεπτα. Απομένουν {remaining} δευτερόλεπτα.",
        "recovery_checkpoint_missing": "Δεν υπήρχε διαθέσιμη τιμή καρδιακού ρυθμού στο σημείο των {seconds} δευτερολέπτων. Η συλλογή συνεχίζεται και απομένουν {remaining} δευτερόλεπτα.",
        "recovery_complete": "Η συλλογή αποκατάστασης καρδιακού ρυθμού μετά την άσκηση ολοκληρώθηκε. Όλα τα διαθέσιμα δεδομένα αποθηκεύτηκαν. Όλα είναι έτοιμα.",
        "no_recovery": "Η προπόνηση τελείωσε. Δεν ήταν δυνατή η συλλογή αποκατάστασης καρδιακού ρυθμού επειδή δεν υπήρχαν έγκυρα δεδομένα καρδιακού ρυθμού.",
    },
    "de": {
        "waiting_live": "Training gestartet. Ich warte auf Live-Sensordaten, bevor der Trainingstimer startet.",
        "started_with_live": "Training gestartet. Live-Daten von {sensors} sind verfügbar und der Timer läuft.",
        "live_available": "Live-Daten von {sensors} sind jetzt verfügbar. Der Trainingstimer läuft. Du kannst mit dem Training beginnen.",
        "stopped_without_live": "Das Training wurde beendet, bevor Live-Sensordaten verfügbar waren. Es wurde kein Live-Training aufgezeichnet.",
        "recovery_wait": "Training beendet. Bitte warte, während die Herzfrequenzerholung nach dem Training in den nächsten 120 Sekunden erfasst wird.",
        "recovery_checkpoint": "Herzfrequenzerholung nach {seconds} Sekunden erfasst. Noch {remaining} Sekunden.",
        "recovery_checkpoint_missing": "Am {seconds}-Sekunden-Messpunkt war keine Herzfrequenz verfügbar. Die Erfassung läuft weiter; noch {remaining} Sekunden.",
        "recovery_complete": "Die Erfassung der Herzfrequenzerholung ist abgeschlossen. Alle verfügbaren Erholungsdaten wurden gespeichert. Alles ist bereit.",
        "no_recovery": "Training beendet. Die Herzfrequenzerholung konnte nicht erfasst werden, weil keine nutzbaren Herzfrequenzdaten verfügbar waren.",
    },
    "fr": {
        "waiting_live": "Entraînement démarré. J’attends les données en direct des capteurs avant de lancer le chronomètre.",
        "started_with_live": "Entraînement démarré. Les données en direct de {sensors} sont disponibles et le chronomètre a commencé.",
        "live_available": "Les données en direct de {sensors} sont maintenant disponibles. Le chronomètre a commencé. Tu peux commencer ton entraînement.",
        "stopped_without_live": "L’entraînement a été arrêté avant la disponibilité des données en direct. Aucun entraînement en direct n’a été enregistré.",
        "recovery_wait": "Entraînement terminé. Patiente pendant la mesure de la récupération de fréquence cardiaque pendant les 120 prochaines secondes.",
        "recovery_checkpoint": "Données de récupération cardiaque à {seconds} secondes collectées. Il reste {remaining} secondes.",
        "recovery_checkpoint_missing": "Aucune fréquence cardiaque n’était disponible au point de {seconds} secondes. La collecte continue; il reste {remaining} secondes.",
        "recovery_complete": "La collecte de récupération cardiaque est terminée. Toutes les données disponibles ont été enregistrées. Tout est prêt.",
        "no_recovery": "Entraînement terminé. La récupération cardiaque n’a pas pu être mesurée faute de données de fréquence cardiaque utilisables.",
    },
    "es": {
        "waiting_live": "Entrenamiento iniciado. Estoy esperando datos en vivo de los sensores antes de iniciar el temporizador.",
        "started_with_live": "Entrenamiento iniciado. Hay datos en vivo de {sensors} y el temporizador ha comenzado.",
        "live_available": "Los datos en vivo de {sensors} ya están disponibles. El temporizador ha comenzado. Puedes empezar tu entrenamiento.",
        "stopped_without_live": "El entrenamiento se detuvo antes de que hubiera datos en vivo. No se registró un entrenamiento en vivo.",
        "recovery_wait": "Entrenamiento terminado. Espera mientras se recopila la recuperación de frecuencia cardíaca durante los próximos 120 segundos.",
        "recovery_checkpoint": "Datos de recuperación cardíaca de {seconds} segundos recopilados. Quedan {remaining} segundos.",
        "recovery_checkpoint_missing": "No había frecuencia cardíaca disponible en el punto de {seconds} segundos. La recopilación continúa; quedan {remaining} segundos.",
        "recovery_complete": "La recopilación de recuperación cardíaca ha terminado. Se guardaron todos los datos disponibles. Todo está listo.",
        "no_recovery": "Entrenamiento terminado. No se pudo recopilar la recuperación cardíaca porque no había datos de frecuencia cardíaca utilizables.",
    },
    "it": {
        "waiting_live": "Allenamento avviato. Attendo i dati live dei sensori prima di avviare il timer.",
        "started_with_live": "Allenamento avviato. I dati live di {sensors} sono disponibili e il timer è partito.",
        "live_available": "I dati live di {sensors} sono ora disponibili. Il timer è partito. Puoi iniziare l’allenamento.",
        "stopped_without_live": "L’allenamento è stato fermato prima che fossero disponibili dati live. Nessun allenamento live è stato registrato.",
        "recovery_wait": "Allenamento terminato. Attendi mentre viene raccolto il recupero della frequenza cardiaca per i prossimi 120 secondi.",
        "recovery_checkpoint": "Dati di recupero cardiaco a {seconds} secondi raccolti. Restano {remaining} secondi.",
        "recovery_checkpoint_missing": "Nessuna frequenza cardiaca disponibile al punto di {seconds} secondi. La raccolta continua; restano {remaining} secondi.",
        "recovery_complete": "La raccolta del recupero cardiaco è completa. Tutti i dati disponibili sono stati salvati. È tutto pronto.",
        "no_recovery": "Allenamento terminato. Non è stato possibile raccogliere il recupero cardiaco perché mancavano dati di frequenza cardiaca utilizzabili.",
    },
    "pt": {
        "waiting_live": "Treino iniciado. Estou à espera de dados em direto dos sensores antes de iniciar o temporizador.",
        "started_with_live": "Treino iniciado. Há dados em direto de {sensors} e o temporizador começou.",
        "live_available": "Os dados em direto de {sensors} estão agora disponíveis. O temporizador começou. Podes iniciar o treino.",
        "stopped_without_live": "O treino foi parado antes de existirem dados em direto. Nenhum treino em direto foi registado.",
        "recovery_wait": "Treino terminado. Aguarda enquanto a recuperação da frequência cardíaca é recolhida durante os próximos 120 segundos.",
        "recovery_checkpoint": "Dados de recuperação cardíaca aos {seconds} segundos recolhidos. Faltam {remaining} segundos.",
        "recovery_checkpoint_missing": "Não havia frequência cardíaca disponível aos {seconds} segundos. A recolha continua; faltam {remaining} segundos.",
        "recovery_complete": "A recolha da recuperação cardíaca terminou. Todos os dados disponíveis foram guardados. Está tudo pronto.",
        "no_recovery": "Treino terminado. Não foi possível recolher a recuperação cardíaca porque não havia dados utilizáveis de frequência cardíaca.",
    },
    "nl": {
        "waiting_live": "Training gestart. Ik wacht op live sensorgegevens voordat de trainingstimer start.",
        "started_with_live": "Training gestart. Live gegevens van {sensors} zijn beschikbaar en de timer loopt.",
        "live_available": "Live gegevens van {sensors} zijn nu beschikbaar. De timer loopt. Je kunt met je training beginnen.",
        "stopped_without_live": "De training is gestopt voordat live sensorgegevens beschikbaar waren. Er is geen live training opgeslagen.",
        "recovery_wait": "Training beëindigd. Wacht terwijl de hartslagherstelgegevens gedurende de komende 120 seconden worden verzameld.",
        "recovery_checkpoint": "Hartslagherstel na {seconds} seconden verzameld. Nog {remaining} seconden.",
        "recovery_checkpoint_missing": "Op het meetpunt van {seconds} seconden was geen hartslag beschikbaar. De meting gaat door; nog {remaining} seconden.",
        "recovery_complete": "De hartslagherstelmeting is voltooid. Alle beschikbare herstelgegevens zijn opgeslagen. Alles is klaar.",
        "no_recovery": "Training beëindigd. Hartslagherstel kon niet worden verzameld omdat er geen bruikbare hartslaggegevens waren.",
    },
    "pl": {
        "waiting_live": "Trening rozpoczęty. Czekam na dane na żywo z czujników przed uruchomieniem czasu treningu.",
        "started_with_live": "Trening rozpoczęty. Dane na żywo z {sensors} są dostępne i czas treningu ruszył.",
        "live_available": "Dane na żywo z {sensors} są już dostępne. Czas treningu ruszył. Możesz rozpocząć trening.",
        "stopped_without_live": "Trening zatrzymano przed pojawieniem się danych na żywo. Trening na żywo nie został zapisany.",
        "recovery_wait": "Trening zakończony. Poczekaj, trwa pomiar regeneracji tętna przez następne 120 sekund.",
        "recovery_checkpoint": "Zebrano dane regeneracji tętna po {seconds} sekundach. Pozostało {remaining} sekund.",
        "recovery_checkpoint_missing": "W punkcie {seconds} sekund nie było dostępnej wartości tętna. Pomiar trwa dalej; pozostało {remaining} sekund.",
        "recovery_complete": "Pomiar regeneracji tętna został zakończony. Wszystkie dostępne dane zapisano. Wszystko gotowe.",
        "no_recovery": "Trening zakończony. Nie udało się zebrać regeneracji tętna, ponieważ nie było użytecznych danych tętna.",
    },
    "ru": {
        "waiting_live": "Тренировка запущена. Ожидаю данные датчиков в реальном времени перед запуском таймера.",
        "started_with_live": "Тренировка запущена. Данные от {sensors} доступны, таймер запущен.",
        "live_available": "Данные от {sensors} теперь доступны. Таймер тренировки запущен. Можно начинать тренировку.",
        "stopped_without_live": "Тренировка остановлена до появления данных датчиков. Тренировка в реальном времени не была записана.",
        "recovery_wait": "Тренировка завершена. Подожди, пока в течение следующих 120 секунд собираются данные восстановления пульса.",
        "recovery_checkpoint": "Данные восстановления пульса на {seconds}-й секунде собраны. Осталось {remaining} секунд.",
        "recovery_checkpoint_missing": "На отметке {seconds} секунд значение пульса было недоступно. Сбор продолжается; осталось {remaining} секунд.",
        "recovery_complete": "Сбор данных восстановления пульса завершён. Все доступные данные сохранены. Всё готово.",
        "no_recovery": "Тренировка завершена. Восстановление пульса не удалось измерить из-за отсутствия пригодных данных.",
    },
    "uk": {
        "waiting_live": "Тренування запущено. Очікую живі дані датчиків перед запуском таймера.",
        "started_with_live": "Тренування запущено. Живі дані від {sensors} доступні, таймер запущено.",
        "live_available": "Живі дані від {sensors} тепер доступні. Таймер запущено. Можна починати тренування.",
        "stopped_without_live": "Тренування зупинено до появи живих даних. Живе тренування не було записано.",
        "recovery_wait": "Тренування завершено. Зачекай, поки протягом наступних 120 секунд збираються дані відновлення пульсу.",
        "recovery_checkpoint": "Дані відновлення пульсу на {seconds}-й секунді зібрано. Залишилося {remaining} секунд.",
        "recovery_checkpoint_missing": "На позначці {seconds} секунд значення пульсу було недоступне. Збір триває; залишилося {remaining} секунд.",
        "recovery_complete": "Збір даних відновлення пульсу завершено. Усі доступні дані збережено. Усе готово.",
        "no_recovery": "Тренування завершено. Відновлення пульсу не вдалося виміряти через відсутність придатних даних.",
    },
    "tr": {
        "waiting_live": "Antrenman başlatıldı. Sayaç başlamadan önce canlı sensör verileri bekleniyor.",
        "started_with_live": "Antrenman başlatıldı. {sensors} üzerinden canlı veri mevcut ve sayaç başladı.",
        "live_available": "{sensors} üzerinden canlı veri artık mevcut. Antrenman sayacı başladı. Antrenmana başlayabilirsin.",
        "stopped_without_live": "Canlı sensör verisi gelmeden antrenman durduruldu. Canlı antrenman kaydedilmedi.",
        "recovery_wait": "Antrenman sona erdi. Önümüzdeki 120 saniye boyunca egzersiz sonrası kalp hızı toparlanma verileri toplanırken bekle.",
        "recovery_checkpoint": "{seconds} saniyelik kalp hızı toparlanma verisi toplandı. {remaining} saniye kaldı.",
        "recovery_checkpoint_missing": "{seconds} saniyelik noktada kalp hızı verisi yoktu. Toplama sürüyor; {remaining} saniye kaldı.",
        "recovery_complete": "Kalp hızı toparlanma verilerinin toplanması tamamlandı. Mevcut tüm veriler kaydedildi. Her şey hazır.",
        "no_recovery": "Antrenman sona erdi. Kullanılabilir kalp hızı verisi olmadığı için toparlanma verileri toplanamadı.",
    },
    "zh": {
        "waiting_live": "训练已开始。正在等待实时传感器数据，收到数据后训练计时器才会启动。",
        "started_with_live": "训练已开始。已收到来自 {sensors} 的实时数据，计时器已经启动。",
        "live_available": "现在已收到来自 {sensors} 的实时数据。训练计时器已经启动，可以开始训练。",
        "stopped_without_live": "在实时传感器数据可用之前训练已停止，因此没有记录实时训练。",
        "recovery_wait": "训练结束。请等待接下来的120秒，以收集运动后的心率恢复数据。",
        "recovery_checkpoint": "已收集运动后 {seconds} 秒的心率恢复数据。还剩 {remaining} 秒。",
        "recovery_checkpoint_missing": "在运动后 {seconds} 秒时没有可用的心率值。继续收集，还剩 {remaining} 秒。",
        "recovery_complete": "运动后心率恢复数据收集已完成。所有可用数据都已保存，一切就绪。",
        "no_recovery": "训练结束。由于没有可用的心率数据，无法收集运动后的心率恢复数据。",
    },
    "ja": {
        "waiting_live": "ワークアウトを開始しました。ライブセンサーデータを待っています。データが届くとタイマーが始まります。",
        "started_with_live": "ワークアウトを開始しました。{sensors} からライブデータを受信しており、タイマーも開始しました。",
        "live_available": "{sensors} からライブデータを受信しました。ワークアウトタイマーが開始しました。運動を始められます。",
        "stopped_without_live": "ライブセンサーデータが届く前にワークアウトを停止しました。ライブワークアウトは記録されませんでした。",
        "recovery_wait": "ワークアウトが終了しました。これから120秒間、運動後の心拍回復データを収集するのでお待ちください。",
        "recovery_checkpoint": "運動後 {seconds} 秒の心拍回復データを収集しました。残り {remaining} 秒です。",
        "recovery_checkpoint_missing": "運動後 {seconds} 秒の時点では心拍数を取得できませんでした。収集を続けます。残り {remaining} 秒です。",
        "recovery_complete": "運動後の心拍回復データ収集が完了しました。利用可能なデータはすべて保存されました。準備完了です。",
        "no_recovery": "ワークアウトが終了しました。利用可能な心拍データがなかったため、心拍回復データは収集できませんでした。",
    },
    "ko": {
        "waiting_live": "운동을 시작했습니다. 실시간 센서 데이터를 기다리고 있으며 데이터가 들어오면 운동 타이머가 시작됩니다.",
        "started_with_live": "운동을 시작했습니다. {sensors}에서 실시간 데이터가 들어오고 있으며 타이머가 시작되었습니다.",
        "live_available": "{sensors}에서 실시간 데이터가 들어왔습니다. 운동 타이머가 시작되었습니다. 운동을 시작할 수 있습니다.",
        "stopped_without_live": "실시간 센서 데이터가 들어오기 전에 운동을 중지했습니다. 실시간 운동은 기록되지 않았습니다.",
        "recovery_wait": "운동이 끝났습니다. 앞으로 120초 동안 운동 후 심박 회복 데이터를 수집하니 기다려 주세요.",
        "recovery_checkpoint": "운동 후 {seconds}초 심박 회복 데이터를 수집했습니다. {remaining}초 남았습니다.",
        "recovery_checkpoint_missing": "운동 후 {seconds}초 지점에 심박 값이 없었습니다. 수집을 계속하며 {remaining}초 남았습니다.",
        "recovery_complete": "운동 후 심박 회복 데이터 수집이 완료되었습니다. 사용 가능한 모든 데이터가 저장되었습니다. 준비가 끝났습니다.",
        "no_recovery": "운동이 끝났습니다. 사용 가능한 심박 데이터가 없어 심박 회복 데이터를 수집할 수 없었습니다.",
    },
}


def static_session_message(
    language: str | None,
    event: str,
    *,
    sensors: list[str] | None = None,
    seconds: int | None = None,
    remaining: int | None = None,
) -> str | None:
    """Return localized deterministic live-session/recovery guidance."""
    code = language_code(language)
    messages = _SESSION_MESSAGES.get(code, _SESSION_MESSAGES["en"])
    template = messages.get(event) or _SESSION_MESSAGES["en"].get(event)
    if not template:
        return None

    sensor_text = ", ".join(sensors or [])
    if not sensor_text:
        sensor_text = {
            "el": "τους διαθέσιμους αισθητήρες",
            "de": "den verfügbaren Sensoren",
            "fr": "les capteurs disponibles",
            "es": "los sensores disponibles",
            "it": "i sensori disponibili",
            "pt": "os sensores disponíveis",
            "nl": "de beschikbare sensoren",
            "pl": "dostępne czujniki",
            "ru": "доступных датчиков",
            "uk": "доступних датчиків",
            "tr": "kullanılabilir sensörler",
            "zh": "可用传感器",
            "ja": "利用可能なセンサー",
            "ko": "사용 가능한 센서",
        }.get(code, "the available sensors")

    return template.format(
        sensors=sensor_text,
        seconds=seconds if seconds is not None else 0,
        remaining=remaining if remaining is not None else 0,
    )

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
