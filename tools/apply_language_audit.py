#!/usr/bin/env python3
"""Fill audited English leaks in every shipped Home Assistant locale.

Run from anywhere in the repository. Reviewed values are applied to the exact
audited paths, including partly translated hybrid strings. The script also
maintains the service catalog and validates placeholders/shape.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import runpy

ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "custom_components" / "fitness"
LANGUAGES = (
    "en", "el", "de", "fr", "es", "it", "pt", "nl",
    "pl", "ru", "uk", "tr", "zh", "ja", "ko",
)


def _row(*values: str) -> dict[str, str]:
    if len(values) != len(LANGUAGES):
        raise RuntimeError(f"Expected {len(LANGUAGES)} translations, got {len(values)}")
    return dict(zip(LANGUAGES, values, strict=True))


TEXT = {
    "adapters_already_configured": _row(
        "All Fitness live adapters are already configured. Enable or disable them from their adapter devices.",
        "Όλοι οι προσαρμογείς ζωντανών δεδομένων Fitness έχουν ήδη ρυθμιστεί. Ενεργοποίησέ τους ή απενεργοποίησέ τους από τις συσκευές προσαρμογέα.",
        "Alle Fitness-Live-Adapter sind bereits eingerichtet. Aktiviere oder deaktiviere sie über ihre Adaptergeräte.",
        "Tous les adaptateurs Fitness en direct sont déjà configurés. Activez-les ou désactivez-les depuis leurs appareils adaptateurs.",
        "Todos los adaptadores en vivo de Fitness ya están configurados. Actívalos o desactívalos desde sus dispositivos adaptadores.",
        "Tutti gli adattatori live Fitness sono già configurati. Abilitali o disabilitali dai relativi dispositivi adattatore.",
        "Todos os adaptadores de dados em direto do Fitness já estão configurados. Ativa-os ou desativa-os nos respetivos dispositivos.",
        "Alle Fitness-liveadapters zijn al geconfigureerd. Schakel ze in of uit via hun adapterapparaten.",
        "Wszystkie adaptery danych na żywo Fitness są już skonfigurowane. Włączaj lub wyłączaj je na urządzeniach adapterów.",
        "Все адаптеры Fitness для данных в реальном времени уже настроены. Включайте или отключайте их на устройствах адаптеров.",
        "Усі адаптери Fitness для даних наживо вже налаштовані. Вмикайте або вимикайте їх на пристроях адаптерів.",
        "Tüm Fitness canlı adaptörleri zaten yapılandırılmış. Bunları adaptör cihazlarından etkinleştir veya devre dışı bırak.",
        "所有 Fitness 实时适配器均已配置。请在相应适配器设备中启用或停用它们。",
        "Fitness ライブアダプターはすべて設定済みです。各アダプターデバイスから有効または無効にしてください。",
        "모든 Fitness 실시간 어댑터가 이미 구성되었습니다. 각 어댑터 기기에서 활성화하거나 비활성화하세요.",
    ),
    "adapters_managed_on_devices": _row(
        "Local sensor adapters are configured from the ANT+ and Bluetooth adapter devices.",
        "Οι τοπικοί προσαρμογείς αισθητήρων ρυθμίζονται από τις συσκευές προσαρμογέα ANT+ και Bluetooth.",
        "Lokale Sensoradapter werden über die ANT+- und Bluetooth-Adaptergeräte eingerichtet.",
        "Les adaptateurs de capteurs locaux se configurent depuis les appareils adaptateurs ANT+ et Bluetooth.",
        "Los adaptadores de sensores locales se configuran desde los dispositivos adaptadores ANT+ y Bluetooth.",
        "Gli adattatori dei sensori locali si configurano dai dispositivi adattatore ANT+ e Bluetooth.",
        "Os adaptadores de sensores locais são configurados nos dispositivos adaptadores ANT+ e Bluetooth.",
        "Lokale sensoradapters worden ingesteld via de ANT+- en Bluetooth-adapterapparaten.",
        "Lokalne adaptery czujników konfiguruje się na urządzeniach adapterów ANT+ i Bluetooth.",
        "Локальные адаптеры датчиков настраиваются на устройствах адаптеров ANT+ и Bluetooth.",
        "Локальні адаптери датчиків налаштовуються на пристроях адаптерів ANT+ і Bluetooth.",
        "Yerel sensör adaptörleri ANT+ ve Bluetooth adaptör cihazlarından yapılandırılır.",
        "本地传感器适配器通过 ANT+ 和蓝牙适配器设备进行配置。",
        "ローカルセンサーアダプターは ANT+ および Bluetooth アダプターデバイスから設定します。",
        "로컬 센서 어댑터는 ANT+ 및 Bluetooth 어댑터 기기에서 구성합니다.",
    ),
    "profile_already_configured": _row(
        "A Fitness profile with this name already exists.",
        "Υπάρχει ήδη προφίλ Fitness με αυτό το όνομα.",
        "Ein Fitness-Profil mit diesem Namen ist bereits vorhanden.",
        "Un profil Fitness portant ce nom existe déjà.",
        "Ya existe un perfil de Fitness con este nombre.",
        "Esiste già un profilo Fitness con questo nome.",
        "Já existe um perfil Fitness com este nome.",
        "Er bestaat al een Fitness-profiel met deze naam.",
        "Profil Fitness o tej nazwie już istnieje.",
        "Профиль Fitness с таким именем уже существует.",
        "Профіль Fitness із такою назвою вже існує.",
        "Bu ada sahip bir Fitness profili zaten var.",
        "已存在同名的 Fitness 个人资料。",
        "同じ名前の Fitness プロフィールがすでに存在します。",
        "같은 이름의 Fitness 프로필이 이미 있습니다.",
    ),
    "invalid_discovery": _row(
        "The fitness sensor discovery data was invalid.",
        "Τα δεδομένα εντοπισμού του αισθητήρα fitness δεν ήταν έγκυρα.",
        "Die Erkennungsdaten des Fitness-Sensors waren ungültig.",
        "Les données de découverte du capteur de fitness étaient invalides.",
        "Los datos de descubrimiento del sensor de fitness no eran válidos.",
        "I dati di rilevamento del sensore fitness non erano validi.",
        "Os dados de descoberta do sensor fitness eram inválidos.",
        "De ontdekkingsgegevens van de fitnesssensor waren ongeldig.",
        "Dane wykrywania czujnika fitness były nieprawidłowe.",
        "Данные обнаружения фитнес-датчика недействительны.",
        "Дані виявлення фітнес-датчика недійсні.",
        "Fitness sensörü keşif verileri geçersizdi.",
        "健身传感器发现数据无效。",
        "フィットネスセンサーの検出データが無効です。",
        "피트니스 센서 검색 데이터가 올바르지 않습니다.",
    ),
    "live_sensor_assigned": _row(
        "The fitness sensor was assigned successfully.",
        "Ο αισθητήρας fitness αντιστοιχίστηκε με επιτυχία.",
        "Der Fitness-Sensor wurde erfolgreich zugewiesen.",
        "Le capteur de fitness a été attribué.",
        "El sensor de fitness se asignó correctamente.",
        "Il sensore fitness è stato assegnato correttamente.",
        "O sensor fitness foi atribuído com sucesso.",
        "De fitnesssensor is toegewezen.",
        "Czujnik fitness został przypisany.",
        "Фитнес-датчик успешно назначен.",
        "Фітнес-датчик успішно призначено.",
        "Fitness sensörü başarıyla atandı.",
        "健身传感器已成功分配。",
        "フィットネスセンサーを割り当てました。",
        "피트니스 센서를 할당했습니다.",
    ),
    "create_profile_first": _row(
        "Create a Fitness user before assigning this sensor.",
        "Δημιούργησε χρήστη Fitness πριν αντιστοιχίσεις αυτόν τον αισθητήρα.",
        "Erstelle zuerst einen Fitness-Benutzer, bevor du diesen Sensor zuweist.",
        "Créez un utilisateur Fitness avant d’attribuer ce capteur.",
        "Crea un usuario de Fitness antes de asignar este sensor.",
        "Crea un utente Fitness prima di assegnare questo sensore.",
        "Cria um utilizador Fitness antes de atribuir este sensor.",
        "Maak een Fitness-gebruiker voordat je deze sensor toewijst.",
        "Utwórz użytkownika Fitness przed przypisaniem tego czujnika.",
        "Создайте пользователя Fitness перед назначением этого датчика.",
        "Створіть користувача Fitness перед призначенням цього датчика.",
        "Bu sensörü atamadan önce bir Fitness kullanıcısı oluştur.",
        "分配此传感器前，请先创建 Fitness 用户。",
        "このセンサーを割り当てる前に Fitness ユーザーを作成してください。",
        "이 센서를 할당하기 전에 Fitness 사용자를 만드세요.",
    ),
    "sensor_unavailable": _row(
        "The discovered fitness sensor is no longer available.",
        "Ο αισθητήρας fitness που εντοπίστηκε δεν είναι πλέον διαθέσιμος.",
        "Der erkannte Fitness-Sensor ist nicht mehr verfügbar.",
        "Le capteur de fitness découvert n’est plus disponible.",
        "El sensor de fitness detectado ya no está disponible.",
        "Il sensore fitness rilevato non è più disponibile.",
        "O sensor fitness descoberto já não está disponível.",
        "De gevonden fitnesssensor is niet meer beschikbaar.",
        "Wykryty czujnik fitness nie jest już dostępny.",
        "Обнаруженный фитнес-датчик больше недоступен.",
        "Виявлений фітнес-датчик більше недоступний.",
        "Keşfedilen fitness sensörü artık kullanılamıyor.",
        "发现的健身传感器已不可用。",
        "検出したフィットネスセンサーは利用できなくなりました。",
        "검색된 피트니스 센서를 더 이상 사용할 수 없습니다.",
    ),
    "invalid_date": _row(
        "Enter a valid date of birth in the past.",
        "Εισαγάγετε έγκυρη ημερομηνία γέννησης στο παρελθόν.",
        "Gib ein gültiges Geburtsdatum in der Vergangenheit ein.",
        "Saisissez une date de naissance valide située dans le passé.",
        "Introduce una fecha de nacimiento válida del pasado.",
        "Inserisci una data di nascita valida nel passato.",
        "Introduz uma data de nascimento válida no passado.",
        "Voer een geldige geboortedatum in het verleden in.",
        "Wprowadź prawidłową datę urodzenia z przeszłości.",
        "Введите корректную дату рождения в прошлом.",
        "Введіть коректну дату народження в минулому.",
        "Geçmişte olan geçerli bir doğum tarihi gir.",
        "请输入有效且早于今天的出生日期。",
        "過去の有効な生年月日を入力してください。",
        "과거의 올바른 생년월일을 입력하세요.",
    ),
    "invalid_number_or_entity": _row(
        "Enter a valid numeric value or Home Assistant entity ID.",
        "Εισαγάγετε έγκυρη αριθμητική τιμή ή αναγνωριστικό οντότητας Home Assistant.",
        "Gib einen gültigen Zahlenwert oder eine Home-Assistant-Entitäts-ID ein.",
        "Saisissez une valeur numérique valide ou un identifiant d’entité Home Assistant.",
        "Introduce un valor numérico válido o un ID de entidad de Home Assistant.",
        "Inserisci un valore numerico valido o un ID entità Home Assistant.",
        "Introduz um valor numérico válido ou um ID de entidade do Home Assistant.",
        "Voer een geldige numerieke waarde of Home Assistant-entiteits-ID in.",
        "Wprowadź prawidłową wartość liczbową lub identyfikator encji Home Assistant.",
        "Введите корректное число или идентификатор сущности Home Assistant.",
        "Введіть коректне число або ідентифікатор сутності Home Assistant.",
        "Geçerli bir sayı veya Home Assistant varlık kimliği gir.",
        "请输入有效数值或 Home Assistant 实体 ID。",
        "有効な数値または Home Assistant エンティティ ID を入力してください。",
        "올바른 숫자 값 또는 Home Assistant 엔티티 ID를 입력하세요.",
    ),
    "select_profile": _row(
        "Select at least one Fitness user.", "Επίλεξε τουλάχιστον έναν χρήστη Fitness.",
        "Wähle mindestens einen Fitness-Benutzer aus.", "Sélectionnez au moins un utilisateur Fitness.",
        "Selecciona al menos un usuario de Fitness.", "Seleziona almeno un utente Fitness.",
        "Seleciona pelo menos um utilizador Fitness.", "Selecteer minstens één Fitness-gebruiker.",
        "Wybierz co najmniej jednego użytkownika Fitness.", "Выберите хотя бы одного пользователя Fitness.",
        "Виберіть принаймні одного користувача Fitness.", "En az bir Fitness kullanıcısı seç.",
        "请至少选择一个 Fitness 用户。", "Fitness ユーザーを1人以上選択してください。", "Fitness 사용자를 한 명 이상 선택하세요.",
    ),
    "ai_enabled": _row(
        "Generate AI fitness assessments", "Δημιουργία αξιολογήσεων fitness με AI",
        "KI-Fitnessbewertungen erstellen", "Générer des évaluations Fitness par IA",
        "Generar evaluaciones de fitness con IA", "Genera valutazioni fitness con IA",
        "Gerar avaliações fitness com IA", "AI-fitnessbeoordelingen genereren",
        "Generuj oceny fitness przez AI", "Создавать фитнес-оценки с помощью ИИ",
        "Створювати фітнес-оцінки за допомогою ШІ", "Yapay zekâ fitness değerlendirmeleri oluştur",
        "生成 AI 健身评估", "AI フィットネス評価を生成", "AI 피트니스 평가 생성",
    ),
    "fitness_users": _row(
        "Fitness users", "Χρήστες Fitness", "Fitness-Benutzer", "Utilisateurs Fitness",
        "Usuarios de Fitness", "Utenti Fitness", "Utilizadores Fitness", "Fitness-gebruikers",
        "Użytkownicy Fitness", "Пользователи Fitness", "Користувачі Fitness", "Fitness kullanıcıları",
        "Fitness 用户", "Fitness ユーザー", "Fitness 사용자",
    ),
    "sensor_shared": _row(
        "One physical sensor can be shared by multiple Fitness profiles.",
        "Ένας φυσικός αισθητήρας μπορεί να χρησιμοποιείται από πολλά προφίλ Fitness.",
        "Ein physischer Sensor kann von mehreren Fitness-Profilen gemeinsam genutzt werden.",
        "Un même capteur physique peut être partagé par plusieurs profils Fitness.",
        "Un sensor físico puede compartirse entre varios perfiles de Fitness.",
        "Un sensore fisico può essere condiviso da più profili Fitness.",
        "Um sensor físico pode ser partilhado por vários perfis Fitness.",
        "Eén fysieke sensor kan door meerdere Fitness-profielen worden gedeeld.",
        "Jeden fizyczny czujnik może być współdzielony przez wiele profili Fitness.",
        "Один физический датчик можно использовать в нескольких профилях Fitness.",
        "Один фізичний датчик можна використовувати в кількох профілях Fitness.",
        "Bir fiziksel sensör birden çok Fitness profiliyle paylaşılabilir.",
        "一个物理传感器可由多个 Fitness 个人资料共享。",
        "1つの物理センサーを複数の Fitness プロフィールで共有できます。",
        "하나의 물리 센서를 여러 Fitness 프로필에서 공유할 수 있습니다.",
    ),
    "sensor_discovered_description": _row(
        "{sensor} was discovered. Choose every Fitness user who may use this physical sensor for live workouts.",
        "Εντοπίστηκε ο αισθητήρας {sensor}. Επίλεξε όλους τους χρήστες Fitness που μπορούν να τον χρησιμοποιούν σε ζωντανές προπονήσεις.",
        "{sensor} wurde erkannt. Wähle alle Fitness-Benutzer aus, die diesen physischen Sensor für Live-Trainings verwenden dürfen.",
        "{sensor} a été découvert. Sélectionnez tous les utilisateurs Fitness autorisés à utiliser ce capteur physique pour les entraînements en direct.",
        "Se detectó {sensor}. Selecciona todos los usuarios de Fitness que puedan usar este sensor físico en entrenamientos en vivo.",
        "È stato rilevato {sensor}. Seleziona tutti gli utenti Fitness che possono usare questo sensore fisico negli allenamenti live.",
        "Foi descoberto {sensor}. Seleciona todos os utilizadores Fitness que podem usar este sensor físico em treinos em direto.",
        "{sensor} is gevonden. Selecteer alle Fitness-gebruikers die deze fysieke sensor voor live trainingen mogen gebruiken.",
        "Wykryto {sensor}. Wybierz wszystkich użytkowników Fitness, którzy mogą używać tego fizycznego czujnika w treningach na żywo.",
        "Обнаружен датчик {sensor}. Выберите всех пользователей Fitness, которые могут использовать этот физический датчик для тренировок в реальном времени.",
        "Виявлено датчик {sensor}. Виберіть усіх користувачів Fitness, які можуть використовувати цей фізичний датчик для тренувань наживо.",
        "{sensor} keşfedildi. Bu fiziksel sensörü canlı antrenmanlarda kullanabilecek tüm Fitness kullanıcılarını seç.",
        "已发现 {sensor}。请选择可在实时训练中使用此物理传感器的所有 Fitness 用户。",
        "{sensor} を検出しました。ライブワークアウトでこの物理センサーを使用できる Fitness ユーザーをすべて選択してください。",
        "{sensor} 센서를 발견했습니다. 실시간 운동에서 이 물리 센서를 사용할 수 있는 모든 Fitness 사용자를 선택하세요.",
    ),
    "sensor_discovered_title": _row(
        "New fitness sensor discovered", "Εντοπίστηκε νέος αισθητήρας fitness",
        "Neuer Fitness-Sensor erkannt", "Nouveau capteur de fitness découvert",
        "Nuevo sensor de fitness detectado", "Rilevato nuovo sensore fitness",
        "Novo sensor fitness descoberto", "Nieuwe fitnesssensor gevonden",
        "Wykryto nowy czujnik fitness", "Обнаружен новый фитнес-датчик",
        "Виявлено новий фітнес-датчик", "Yeni fitness sensörü keşfedildi",
        "发现新的健身传感器", "新しいフィットネスセンサーを検出", "새 피트니스 센서 발견",
    ),
    "feedback_areas": _row(
        "Rooms for intensity light feedback", "Χώροι για φωτεινή ανατροφοδότηση έντασης",
        "Räume für intensitätsabhängiges Lichtfeedback", "Pièces pour le retour lumineux d’intensité",
        "Habitaciones para información luminosa de intensidad", "Stanze per il feedback luminoso dell’intensità",
        "Divisões para feedback luminoso de intensidade", "Ruimtes voor lichtfeedback op intensiteit",
        "Pomieszczenia dla świetlnej informacji o intensywności", "Комнаты для световой индикации интенсивности",
        "Кімнати для світлової індикації інтенсивності", "Yoğunluk ışığı geri bildirimi için odalar",
        "用于强度灯光反馈的房间", "強度照明フィードバックを使う部屋", "강도 조명 피드백을 사용할 공간",
    ),
    "feedback_lights": _row(
        "Additional / explicit lights for intensity feedback", "Πρόσθετα / συγκεκριμένα φώτα για ανατροφοδότηση έντασης",
        "Zusätzliche/ausdrückliche Lichter für Intensitätsfeedback", "Éclairages supplémentaires/explicites pour le retour d’intensité",
        "Luces adicionales/explícitas para información de intensidad", "Luci aggiuntive/esplicite per il feedback dell’intensità",
        "Luzes adicionais/explícitas para feedback de intensidade", "Extra/expliciete lampen voor intensiteitsfeedback",
        "Dodatkowe/jawnie wybrane światła dla informacji o intensywności", "Дополнительные/явно выбранные лампы для индикации интенсивности",
        "Додаткові/явно вибрані лампи для індикації інтенсивності", "Yoğunluk geri bildirimi için ek/açıkça seçilmiş ışıklar",
        "用于强度反馈的其他/明确指定灯光", "強度フィードバック用の追加/明示指定した照明", "강도 피드백용 추가/직접 지정 조명",
    ),
}

TEXT.update(
    {
        "feedback_description": _row(
            "Choose rooms and/or explicit light entities for five-second intensity color feedback. Every available color-capable light in the selected rooms is included automatically. You can also select notification entities, a TTS provider and media players for announcements.",
            "Επίλεξε χώρους ή/και συγκεκριμένες οντότητες φωτισμού για έγχρωμη ανατροφοδότηση έντασης πέντε δευτερολέπτων. Κάθε διαθέσιμο έγχρωμο φως στους επιλεγμένους χώρους συμπεριλαμβάνεται αυτόματα. Μπορείς επίσης να επιλέξεις οντότητες ειδοποιήσεων, πάροχο TTS και συσκευές αναπαραγωγής για ανακοινώσεις.",
            "Wähle Räume und/oder bestimmte Lichtentitäten für fünfsekündiges farbiges Intensitätsfeedback. Alle verfügbaren farbfähigen Lichter in den gewählten Räumen werden automatisch einbezogen. Zusätzlich kannst du Benachrichtigungsentitäten, einen TTS-Anbieter und Mediaplayer für Ansagen auswählen.",
            "Choisissez des pièces et/ou des entités d’éclairage précises pour un retour coloré de cinq secondes selon l’intensité. Tous les éclairages couleur disponibles des pièces choisies sont inclus automatiquement. Vous pouvez aussi choisir des entités de notification, un fournisseur TTS et des lecteurs multimédias pour les annonces.",
            "Elige habitaciones o entidades de luz específicas para una indicación de color de cinco segundos según la intensidad. Todas las luces compatibles con color de las habitaciones elegidas se incluyen automáticamente. También puedes elegir entidades de notificación, un proveedor TTS y reproductores multimedia para anuncios.",
            "Scegli stanze e/o entità luce esplicite per un feedback a colori di cinque secondi sull’intensità. Tutte le luci a colori disponibili nelle stanze selezionate vengono incluse automaticamente. Puoi anche scegliere entità di notifica, un provider TTS e lettori multimediali per gli annunci.",
            "Escolhe divisões e/ou entidades de luz explícitas para feedback de cor da intensidade durante cinco segundos. Todas as luzes com cor disponíveis nas divisões escolhidas são incluídas automaticamente. Também podes escolher entidades de notificação, um fornecedor TTS e leitores multimédia para anúncios.",
            "Kies ruimtes en/of expliciete lampentiteiten voor vijf seconden kleurfeedback over de intensiteit. Alle beschikbare kleurlampen in de gekozen ruimtes worden automatisch opgenomen. Je kunt ook meldingsentiteiten, een TTS-provider en mediaspelers voor aankondigingen kiezen.",
            "Wybierz pomieszczenia lub konkretne encje światła do pięciosekundowej kolorowej informacji o intensywności. Wszystkie dostępne kolorowe światła w wybranych pomieszczeniach są dodawane automatycznie. Możesz też wybrać encje powiadomień, dostawcę TTS i odtwarzacze do komunikatów.",
            "Выберите комнаты и/или конкретные сущности света для пятисекундной цветовой индикации интенсивности. Все доступные цветные лампы в выбранных комнатах включаются автоматически. Также можно выбрать сущности уведомлений, провайдера TTS и медиаплееры для объявлений.",
            "Виберіть кімнати та/або конкретні сутності світла для п’ятисекундної кольорової індикації інтенсивності. Усі доступні кольорові лампи у вибраних кімнатах додаються автоматично. Також можна вибрати сутності сповіщень, постачальника TTS і медіаплеєри для оголошень.",
            "Beş saniyelik yoğunluk rengi geri bildirimi için odaları ve/veya açıkça seçilmiş ışık varlıklarını belirle. Seçilen odalardaki renk destekli tüm ışıklar otomatik eklenir. Duyurular için bildirim varlıkları, TTS sağlayıcısı ve medya oynatıcılar da seçebilirsin.",
            "选择房间和/或明确指定的灯光实体，以提供五秒钟的强度颜色反馈。所选房间中所有可用的彩色灯光会自动包含。你还可以选择通知实体、TTS 提供商和用于播报的媒体播放器。",
            "5秒間の強度カラー表示に使用する部屋や照明エンティティを選びます。選択した部屋にある利用可能なカラー対応照明は自動的に含まれます。通知エンティティ、TTS プロバイダー、アナウンス用メディアプレーヤーも選択できます。",
            "5초 동안 강도 색상 피드백을 표시할 공간 또는 특정 조명 엔티티를 선택합니다. 선택한 공간의 사용 가능한 색상 조명은 자동으로 포함됩니다. 알림 엔티티, TTS 제공자, 안내용 미디어 플레이어도 선택할 수 있습니다.",
        ),
        "live_devices_hint": _row(
            "Optional Home Assistant devices exposing compatible live heart-rate, power, cadence, speed, distance or altitude entities.",
            "Προαιρετικές συσκευές Home Assistant που παρέχουν συμβατές οντότητες ζωντανού καρδιακού ρυθμού, ισχύος, ρυθμού, ταχύτητας, απόστασης ή υψομέτρου.",
            "Optionale Home-Assistant-Geräte mit kompatiblen Live-Entitäten für Herzfrequenz, Leistung, Kadenz, Geschwindigkeit, Distanz oder Höhe.",
            "Appareils Home Assistant facultatifs exposant des entités en direct compatibles de fréquence cardiaque, puissance, cadence, vitesse, distance ou altitude.",
            "Dispositivos opcionales de Home Assistant con entidades en vivo compatibles de frecuencia cardíaca, potencia, cadencia, velocidad, distancia o altitud.",
            "Dispositivi Home Assistant facoltativi che espongono entità live compatibili per frequenza cardiaca, potenza, cadenza, velocità, distanza o altitudine.",
            "Dispositivos opcionais do Home Assistant com entidades em direto compatíveis de frequência cardíaca, potência, cadência, velocidade, distância ou altitude.",
            "Optionele Home Assistant-apparaten met geschikte live-entiteiten voor hartslag, vermogen, cadans, snelheid, afstand of hoogte.",
            "Opcjonalne urządzenia Home Assistant udostępniające zgodne encje tętna, mocy, kadencji, prędkości, dystansu lub wysokości na żywo.",
            "Необязательные устройства Home Assistant с совместимыми сущностями пульса, мощности, каденса, скорости, дистанции или высоты в реальном времени.",
            "Необов’язкові пристрої Home Assistant із сумісними сутностями пульсу, потужності, каденсу, швидкості, відстані або висоти наживо.",
            "Uyumlu canlı nabız, güç, kadans, hız, mesafe veya irtifa varlıkları sunan isteğe bağlı Home Assistant cihazları.",
            "可选的 Home Assistant 设备，用于提供兼容的实时心率、功率、踏频、速度、距离或海拔实体。",
            "対応するライブ心拍数、パワー、ケイデンス、速度、距離、高度エンティティを公開する任意の Home Assistant デバイス。",
            "호환되는 실시간 심박수, 파워, 케이던스, 속도, 거리 또는 고도 엔티티를 제공하는 선택형 Home Assistant 기기입니다.",
        ),
        "live_sensors_hint": _row(
            "Physical sensors discovered by Fitness. ANT+ and Bluetooth identities are merged into one device when they refer to the same sensor; ANT+ is preferred for live measurements.",
            "Φυσικοί αισθητήρες που εντοπίστηκαν από το Fitness. Οι ταυτότητες ANT+ και Bluetooth συγχωνεύονται σε μία συσκευή όταν αφορούν τον ίδιο αισθητήρα· το ANT+ προτιμάται για ζωντανές μετρήσεις.",
            "Von Fitness erkannte physische Sensoren. ANT+- und Bluetooth-Identitäten werden zu einem Gerät zusammengeführt, wenn sie denselben Sensor bezeichnen; für Live-Messungen wird ANT+ bevorzugt.",
            "Capteurs physiques découverts par Fitness. Les identités ANT+ et Bluetooth sont fusionnées en un appareil lorsqu’elles désignent le même capteur ; ANT+ est privilégié pour les mesures en direct.",
            "Sensores físicos detectados por Fitness. Las identidades ANT+ y Bluetooth se fusionan en un dispositivo si corresponden al mismo sensor; se prefiere ANT+ para mediciones en vivo.",
            "Sensori fisici rilevati da Fitness. Le identità ANT+ e Bluetooth vengono unite in un dispositivo quando indicano lo stesso sensore; ANT+ è preferito per le misurazioni live.",
            "Sensores físicos descobertos pelo Fitness. As identidades ANT+ e Bluetooth são unidas num dispositivo quando correspondem ao mesmo sensor; o ANT+ tem preferência nas medições em direto.",
            "Door Fitness gevonden fysieke sensoren. ANT+- en Bluetooth-identiteiten worden samengevoegd als ze dezelfde sensor zijn; ANT+ heeft de voorkeur voor live metingen.",
            "Fizyczne czujniki wykryte przez Fitness. Tożsamości ANT+ i Bluetooth są łączone w jedno urządzenie, gdy dotyczą tego samego czujnika; pomiary na żywo preferują ANT+.",
            "Физические датчики, обнаруженные Fitness. Идентификаторы ANT+ и Bluetooth объединяются в одно устройство, если относятся к одному датчику; для измерений в реальном времени предпочтителен ANT+.",
            "Фізичні датчики, виявлені Fitness. Ідентифікатори ANT+ і Bluetooth об’єднуються в один пристрій, якщо стосуються одного датчика; для вимірювань наживо перевага надається ANT+.",
            "Fitness tarafından keşfedilen fiziksel sensörler. ANT+ ve Bluetooth kimlikleri aynı sensöre aitse tek cihazda birleştirilir; canlı ölçümlerde ANT+ tercih edilir.",
            "Fitness 发现的物理传感器。当 ANT+ 和蓝牙标识指向同一传感器时，会合并为一个设备；实时测量优先使用 ANT+。",
            "Fitness が検出した物理センサー。同じセンサーを示す ANT+ と Bluetooth の識別情報は1つのデバイスに統合され、ライブ測定では ANT+ を優先します。",
            "Fitness가 발견한 물리 센서입니다. ANT+와 Bluetooth 식별자가 같은 센서를 나타내면 하나의 기기로 병합하며, 실시간 측정에는 ANT+를 우선합니다.",
        ),
        "optional_values": _row(
            "Optional initial / calculable values", "Προαιρετικές αρχικές / υπολογίσιμες τιμές",
            "Optionale Anfangs-/berechenbare Werte", "Valeurs initiales/calculables facultatives",
            "Valores iniciales/calculables opcionales", "Valori iniziali/calcolabili facoltativi",
            "Valores iniciais/calculáveis opcionais", "Optionele begin-/berekenbare waarden",
            "Opcjonalne wartości początkowe/obliczalne", "Необязательные исходные/расчётные значения",
            "Необов’язкові початкові/розрахункові значення", "İsteğe bağlı başlangıç/hesaplanabilir değerler",
            "可选的初始/可计算值", "任意の初期値/計算可能な値", "선택형 초기값/계산 가능 값",
        ),
        "vo2max_value": _row(
            "VO₂max (mL/kg/min or entity)", "VO₂max (mL/kg/min ή οντότητα)",
            "VO₂max (mL/kg/min oder Entität)", "VO₂max (mL/kg/min ou entité)",
            "VO₂máx (mL/kg/min o entidad)", "VO₂max (mL/kg/min o entità)",
            "VO₂máx (mL/kg/min ou entidade)", "VO₂max (mL/kg/min of entiteit)",
            "VO₂max (mL/kg/min lub encja)", "МПК (мл/кг/мин или сущность)",
            "МСК (мл/кг/хв або сутність)", "VO₂maks (mL/kg/dk veya varlık)",
            "最大摄氧量（mL/kg/min 或实体）", "VO₂max（mL/kg/min またはエンティティ）", "VO₂max(mL/kg/min 또는 엔티티)",
        ),
        "ytdlp_enabled": _row(
            "Enable yt-dlp music adapter (experimental)", "Ενεργοποίηση προσαρμογέα μουσικής yt-dlp (πειραματικό)",
            "yt-dlp-Musikadapter aktivieren (experimentell)", "Activer l’adaptateur musical yt-dlp (expérimental)",
            "Activar el adaptador de música yt-dlp (experimental)", "Abilita adattatore musicale yt-dlp (sperimentale)",
            "Ativar adaptador de música yt-dlp (experimental)", "yt-dlp-muziekadapter inschakelen (experimenteel)",
            "Włącz adapter muzyki yt-dlp (eksperymentalny)", "Включить музыкальный адаптер yt-dlp (экспериментальный)",
            "Увімкнути музичний адаптер yt-dlp (експериментальний)", "yt-dlp müzik adaptörünü etkinleştir (deneysel)",
            "启用 yt-dlp 音乐适配器（实验性）", "yt-dlp 音楽アダプターを有効にする（試験的）", "yt-dlp 음악 어댑터 활성화(실험적)",
        ),
        "workout_devices": _row(
            "Devices providing workout / fitness history data", "Συσκευές που παρέχουν ιστορικό προπόνησης / fitness",
            "Geräte mit Trainings-/Fitnessverlaufsdaten", "Appareils fournissant l’historique des entraînements/de la condition physique",
            "Dispositivos que proporcionan historial de entrenamientos/fitness", "Dispositivi che forniscono dati storici di allenamento/fitness",
            "Dispositivos que fornecem histórico de treino/fitness", "Apparaten met trainings-/fitnesshistorie",
            "Urządzenia udostępniające historię treningów/fitness", "Устройства с историей тренировок/физической формы",
            "Пристрої з історією тренувань/фізичної форми", "Antrenman/fitness geçmişi sağlayan cihazlar",
            "提供训练/健身历史数据的设备", "ワークアウト/フィットネス履歴データを提供するデバイス", "운동/피트니스 기록 데이터를 제공하는 기기",
        ),
        "workout_devices_config_hint": _row(
            "Select devices providing completed workouts or long-term fitness/recovery data, such as Garmin Connect or Strava.",
            "Επίλεξε συσκευές που παρέχουν ολοκληρωμένες προπονήσεις ή μακροχρόνια δεδομένα fitness/αποκατάστασης, όπως Garmin Connect ή Strava.",
            "Wähle Geräte mit abgeschlossenen Trainings oder langfristigen Fitness-/Erholungsdaten, etwa Garmin Connect oder Strava.",
            "Sélectionnez les appareils fournissant des entraînements terminés ou des données de condition physique/récupération à long terme, comme Garmin Connect ou Strava.",
            "Selecciona dispositivos que proporcionen entrenamientos completados o datos de fitness/recuperación a largo plazo, como Garmin Connect o Strava.",
            "Seleziona dispositivi che forniscono allenamenti completati o dati fitness/recupero a lungo termine, come Garmin Connect o Strava.",
            "Seleciona dispositivos que fornecem treinos concluídos ou dados de fitness/recuperação a longo prazo, como Garmin Connect ou Strava.",
            "Selecteer apparaten met voltooide trainingen of langetermijngegevens over fitness/herstel, zoals Garmin Connect of Strava.",
            "Wybierz urządzenia dostarczające ukończone treningi lub długoterminowe dane fitness/regeneracji, np. Garmin Connect lub Strava.",
            "Выберите устройства с завершёнными тренировками или долгосрочными данными о форме/восстановлении, например Garmin Connect или Strava.",
            "Виберіть пристрої із завершеними тренуваннями або довгостроковими даними про форму/відновлення, наприклад Garmin Connect або Strava.",
            "Garmin Connect veya Strava gibi tamamlanmış antrenman ya da uzun dönem fitness/toparlanma verisi sağlayan cihazları seç.",
            "选择可提供已完成训练或长期健身/恢复数据的设备，例如 Garmin Connect 或 Strava。",
            "Garmin Connect や Strava など、完了したワークアウトまたは長期的なフィットネス/回復データを提供するデバイスを選びます。",
            "Garmin Connect 또는 Strava처럼 완료된 운동이나 장기 피트니스/회복 데이터를 제공하는 기기를 선택하세요.",
        ),
        "workout_devices_options_hint": _row(
            "Select devices providing completed workouts or long-term fitness/recovery values.",
            "Επίλεξε συσκευές που παρέχουν ολοκληρωμένες προπονήσεις ή μακροχρόνιες τιμές fitness/αποκατάστασης.",
            "Wähle Geräte mit abgeschlossenen Trainings oder langfristigen Fitness-/Erholungswerten.",
            "Sélectionnez les appareils fournissant des entraînements terminés ou des valeurs de condition physique/récupération à long terme.",
            "Selecciona dispositivos que proporcionen entrenamientos completados o valores de fitness/recuperación a largo plazo.",
            "Seleziona dispositivi che forniscono allenamenti completati o valori fitness/recupero a lungo termine.",
            "Seleciona dispositivos que fornecem treinos concluídos ou valores de fitness/recuperação a longo prazo.",
            "Selecteer apparaten met voltooide trainingen of langetermijnwaarden voor fitness/herstel.",
            "Wybierz urządzenia dostarczające ukończone treningi lub długoterminowe wartości fitness/regeneracji.",
            "Выберите устройства с завершёнными тренировками или долгосрочными показателями формы/восстановления.",
            "Виберіть пристрої із завершеними тренуваннями або довгостроковими показниками форми/відновлення.",
            "Tamamlanmış antrenman veya uzun dönem fitness/toparlanma değerleri sağlayan cihazları seç.",
            "选择可提供已完成训练或长期健身/恢复数值的设备。",
            "完了したワークアウトまたは長期的なフィットネス/回復値を提供するデバイスを選びます。",
            "완료된 운동 또는 장기 피트니스/회복 값을 제공하는 기기를 선택하세요.",
        ),
        "profile_description": _row(
            "Edit the person's profile information.", "Επεξεργάσου τα στοιχεία προφίλ του ατόμου.",
            "Bearbeite die Profilangaben der Person.", "Modifiez les informations de profil de la personne.",
            "Edita la información del perfil de la persona.", "Modifica le informazioni del profilo della persona.",
            "Edita as informações do perfil da pessoa.", "Bewerk de profielgegevens van de persoon.",
            "Edytuj informacje profilu tej osoby.", "Измените данные профиля человека.",
            "Змініть дані профілю людини.", "Kişinin profil bilgilerini düzenle.",
            "编辑此人的个人资料信息。", "個人のプロフィール情報を編集します。", "사용자의 프로필 정보를 편집합니다.",
        ),
        "device_antplus_adapter": _row(
            "ANT+ Adapter", "Προσαρμογέας ANT+", "ANT+-Adapter", "Adaptateur ANT+",
            "Adaptador ANT+", "Adattatore ANT+", "Adaptador ANT+", "ANT+-adapter",
            "Adapter ANT+", "Адаптер ANT+", "Адаптер ANT+", "ANT+ adaptörü",
            "ANT+ 适配器", "ANT+ アダプター", "ANT+ 어댑터",
        ),
        "device_bluetooth_adapter": _row(
            "Bluetooth Adapter", "Προσαρμογέας Bluetooth", "Bluetooth-Adapter", "Adaptateur Bluetooth",
            "Adaptador Bluetooth", "Adattatore Bluetooth", "Adaptador Bluetooth", "Bluetooth-adapter",
            "Adapter Bluetooth", "Адаптер Bluetooth", "Адаптер Bluetooth", "Bluetooth adaptörü",
            "蓝牙适配器", "Bluetooth アダプター", "Bluetooth 어댑터",
        ),
        "device_sensors": _row(
            "Sensors", "Αισθητήρες", "Sensoren", "Capteurs", "Sensores", "Sensori",
            "Sensores", "Sensoren", "Czujniki", "Датчики", "Датчики", "Sensörler",
            "传感器", "センサー", "센서",
        ),
        "device_sensors_adapters": _row(
            "Sensors & Adapters", "Αισθητήρες και προσαρμογείς", "Sensoren & Adapter", "Capteurs et adaptateurs",
            "Sensores y adaptadores", "Sensori e adattatori", "Sensores e adaptadores", "Sensoren en adapters",
            "Czujniki i adaptery", "Датчики и адаптеры", "Датчики й адаптери", "Sensörler ve adaptörler",
            "传感器和适配器", "センサーとアダプター", "센서 및 어댑터",
        ),
        "live_average_cadence": _row(
            "Live average cadence", "Ζωντανός μέσος ρυθμός", "Live-Durchschnittskadenz", "Cadence moyenne en direct",
            "Cadencia media en vivo", "Cadenza media live", "Cadência média em direto", "Live gemiddelde cadans",
            "Średnia kadencja na żywo", "Средний каденс в реальном времени", "Середній каденс наживо", "Canlı ortalama kadans",
            "实时平均踏频", "ライブ平均ケイデンス", "실시간 평균 케이던스",
        ),
        "live_banister_trimp": _row(
            "Live Banister TRIMP", "Ζωντανό Banister TRIMP", "Live-Banister-TRIMP", "TRIMP de Banister en direct",
            "TRIMP de Banister en vivo", "TRIMP Banister live", "TRIMP de Banister em direto", "Live Banister-TRIMP",
            "Banister TRIMP na żywo", "Banister TRIMP в реальном времени", "Banister TRIMP наживо", "Canlı Banister TRIMP",
            "实时 Banister TRIMP", "ライブ Banister TRIMP", "실시간 Banister TRIMP",
        ),
        "live_mechanical_work": _row(
            "Live mechanical work", "Ζωντανό μηχανικό έργο", "Mechanische Live-Arbeit", "Travail mécanique en direct",
            "Trabajo mecánico en vivo", "Lavoro meccanico live", "Trabalho mecânico em direto", "Live mechanische arbeid",
            "Praca mechaniczna na żywo", "Механическая работа в реальном времени", "Механічна робота наживо", "Canlı mekanik iş",
            "实时机械功", "ライブ機械的仕事", "실시간 기계적 일",
        ),
        "trimp_28d_weekly": _row(
            "28-day weekly-equivalent TRIMP", "Εβδομαδιαίο ισοδύναμο TRIMP 28 ημερών", "28-Tage-TRIMP als Wochenäquivalent", "TRIMP équivalent hebdomadaire sur 28 jours",
            "TRIMP equivalente semanal de 28 días", "TRIMP equivalente settimanale su 28 giorni", "TRIMP equivalente semanal de 28 dias", "28-daagse TRIMP als weekequivalent",
            "Tygodniowy odpowiednik TRIMP z 28 dni", "Недельный эквивалент TRIMP за 28 дней", "Тижневий еквівалент TRIMP за 28 днів", "28 günlük haftalık eşdeğer TRIMP",
            "28 天周等效 TRIMP", "28日間の週換算 TRIMP", "28일 주간 환산 TRIMP",
        ),
        "trimp_7d": _row(
            "TRIMP / 7 days", "TRIMP / 7 ημέρες", "TRIMP / 7 Tage", "TRIMP / 7 jours",
            "TRIMP / 7 días", "TRIMP / 7 giorni", "TRIMP / 7 dias", "TRIMP / 7 dagen",
            "TRIMP / 7 dni", "TRIMP / 7 дней", "TRIMP / 7 днів", "TRIMP / 7 gün",
            "TRIMP / 7 天", "TRIMP / 7日", "TRIMP / 7일",
        ),
    }
)

_dashboard_catalog = runpy.run_path(
    str(FITNESS / "dashboard_translations.py")
)["DASHBOARD_LANGUAGE_AUDIT_TEXT"]


def _dashboard_music_base() -> dict[str, dict[str, str]]:
    """Read the dependency-free literal part of the dashboard music catalog."""

    tree = ast.parse((FITNESS / "dashboard.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_TV_DASHBOARD_MUSIC_TEXT"
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError("Dashboard music translation catalog was not found")


_dashboard_music = _dashboard_music_base()
_ytdlp_source = (
    "yt-dlp is an optional third-party adapter and is not affiliated with or endorsed by "
    "YouTube or other services. By enabling it, you acknowledge that you are solely "
    "responsible for how you use it, including complying with applicable law, service "
    "terms, copyright/licensing rules, and obtaining all necessary rights or permissions. "
    "Fitness does not provide account cookies, does not authorize circumvention, "
    "unauthorized downloading, or redistribution, and provides this adapter without "
    "warranty. You accept sole responsibility for your conduct and, to the maximum extent "
    "permitted by applicable law, for resulting legal, contractual, financial, account, "
    "copyright, licensing, or other consequences, claims, fees, fines, or penalties. The "
    "Fitness developers and contributors do not assume responsibility for a user's unlawful "
    "or unauthorized use. This notice is not legal advice and does not override rights or "
    "liabilities that cannot lawfully be excluded."
)
TEXT["ytdlp_disclaimer"] = {
    language: (
        _ytdlp_source
        if language == "en"
        else _dashboard_catalog[language]["ytdlp_disclaimer"]
        if "ytdlp_disclaimer" in _dashboard_catalog[language]
        else _dashboard_music[language]["ytdlp_disclaimer"]
    )
    for language in LANGUAGES
}

TEXT["optional_description"] = _row(
    "Each field accepts a numeric value or entity ID. Direct values use the field's documented unit; entity values are automatically converted from their unit_of_measurement. Leave unknown fields empty.",
    "Κάθε πεδίο δέχεται αριθμητική τιμή ή αναγνωριστικό οντότητας. Οι άμεσες τιμές χρησιμοποιούν την τεκμηριωμένη μονάδα του πεδίου· οι τιμές οντοτήτων μετατρέπονται αυτόματα από το unit_of_measurement. Άφησε κενά τα άγνωστα πεδία.",
    "Jedes Feld akzeptiert einen Zahlenwert oder eine Entitäts-ID. Direkte Werte verwenden die dokumentierte Einheit des Feldes; Entitätswerte werden automatisch aus ihrem unit_of_measurement umgerechnet. Unbekannte Felder leer lassen.",
    "Chaque champ accepte une valeur numérique ou un identifiant d’entité. Les valeurs directes utilisent l’unité documentée du champ ; les valeurs d’entité sont automatiquement converties depuis leur unit_of_measurement. Laissez les champs inconnus vides.",
    "Cada campo acepta un valor numérico o un ID de entidad. Los valores directos usan la unidad documentada del campo; los valores de entidad se convierten automáticamente desde su unit_of_measurement. Deja vacíos los campos desconocidos.",
    "Ogni campo accetta un valore numerico o un ID entità. I valori diretti usano l’unità documentata del campo; i valori delle entità vengono convertiti automaticamente dal relativo unit_of_measurement. Lascia vuoti i campi sconosciuti.",
    "Cada campo aceita um valor numérico ou um ID de entidade. Os valores diretos usam a unidade documentada do campo; os valores das entidades são convertidos automaticamente a partir do respetivo unit_of_measurement. Deixa vazios os campos desconhecidos.",
    "Elk veld accepteert een getal of entiteits-ID. Directe waarden gebruiken de gedocumenteerde eenheid van het veld; entiteitswaarden worden automatisch omgerekend vanuit hun unit_of_measurement. Laat onbekende velden leeg.",
    "Każde pole przyjmuje wartość liczbową lub identyfikator encji. Wartości bezpośrednie używają udokumentowanej jednostki pola; wartości encji są automatycznie przeliczane z ich unit_of_measurement. Nieznane pola pozostaw puste.",
    "Каждое поле принимает число или идентификатор сущности. Прямые значения используют указанную для поля единицу; значения сущностей автоматически преобразуются из их unit_of_measurement. Неизвестные поля оставьте пустыми.",
    "Кожне поле приймає число або ідентифікатор сутності. Прямі значення використовують зазначену для поля одиницю; значення сутностей автоматично перетворюються з їх unit_of_measurement. Невідомі поля залиште порожніми.",
    "Her alan sayısal bir değer veya varlık kimliği kabul eder. Doğrudan değerler alanın belgelenen birimini kullanır; varlık değerleri kendi unit_of_measurement değerinden otomatik dönüştürülür. Bilinmeyen alanları boş bırak.",
    "每个字段都可接受数值或实体 ID。直接数值使用该字段注明的单位；实体值会根据其 unit_of_measurement 自动换算。未知字段请留空。",
    "各フィールドには数値またはエンティティ ID を指定できます。直接入力した値には各フィールド記載の単位が使われ、エンティティ値は unit_of_measurement から自動変換されます。不明なフィールドは空欄にしてください。",
    "각 필드는 숫자 값 또는 엔티티 ID를 받습니다. 직접 입력한 값에는 필드에 명시된 단위를 사용하며 엔티티 값은 unit_of_measurement를 기준으로 자동 변환됩니다. 알 수 없는 필드는 비워 두세요.",
)

_entity_audit = runpy.run_path(str(ROOT / "tools" / "language_audit_entity_names.py"))
if tuple(_entity_audit["LANGUAGES"]) != LANGUAGES:
    raise RuntimeError("Entity audit language set does not match the native catalog")
ENTITY_NAMES = _entity_audit["ENTITY_NAMES"]

PATHS = {
    "adapters_already_configured": [("config", "abort", "adapters_already_configured")],
    "adapters_managed_on_devices": [("config", "abort", "adapters_managed_on_devices")],
    "profile_already_configured": [("config", "abort", "already_configured")],
    "invalid_discovery": [("config", "abort", "invalid_discovery")],
    "live_sensor_assigned": [("config", "abort", "live_sensor_assigned")],
    "create_profile_first": [
        ("config", "abort", "no_fitness_profiles"),
        ("options", "abort", "no_fitness_profiles"),
    ],
    "sensor_unavailable": [
        ("config", "abort", "sensor_unavailable"),
        ("options", "abort", "sensor_unavailable"),
        ("options", "error", "sensor_unavailable"),
    ],
    "invalid_date": [("config", "error", "invalid_date")],
    "invalid_number_or_entity": [("config", "error", "invalid_number_or_entity")],
    "select_profile": [("config", "error", "select_profile")],
    "ai_enabled": [
        ("config", "step", "ai", "data", "ai_enabled"),
        ("options", "step", "ai", "data", "ai_enabled"),
    ],
    "fitness_users": [("config", "step", "assign_live_sensor", "data", "fitness_profile_ids")],
    "sensor_shared": [("config", "step", "assign_live_sensor", "data_description", "fitness_profile_ids")],
    "sensor_discovered_description": [("config", "step", "assign_live_sensor", "description")],
    "sensor_discovered_title": [("config", "step", "assign_live_sensor", "title")],
    "feedback_areas": [
        ("config", "step", "feedback", "data", "feedback_area_ids"),
        ("options", "step", "feedback", "data", "feedback_area_ids"),
    ],
    "feedback_lights": [
        ("config", "step", "feedback", "data", "feedback_light_ids"),
        ("options", "step", "feedback", "data", "feedback_light_ids"),
    ],
    "feedback_description": [
        ("config", "step", "feedback", "description"),
        ("options", "step", "feedback", "description"),
    ],
    "live_devices_hint": [
        ("config", "step", "live_devices", "data_description", "live_device_ids"),
        ("options", "step", "live_devices", "data_description", "live_device_ids"),
    ],
    "live_sensors_hint": [
        ("config", "step", "live_devices", "data_description", "live_sensor_ids"),
        ("options", "step", "live_devices", "data_description", "live_sensor_ids"),
    ],
    "optional_values": [("config", "step", "optional", "title")],
    "optional_description": [("config", "step", "optional", "description")],
    "vo2max_value": [
        ("config", "step", "optional", "data", "vo2max"),
        ("options", "step", "fitness_inputs", "data", "vo2max"),
    ],
    "ytdlp_enabled": [
        ("config", "step", "tv_dashboard", "data", "tv_dashboard_ytdlp_enabled"),
        ("options", "step", "tv_dashboard", "data", "tv_dashboard_ytdlp_enabled"),
    ],
    "ytdlp_disclaimer": [
        ("config", "step", "tv_dashboard", "data_description", "tv_dashboard_ytdlp_enabled"),
        ("options", "step", "tv_dashboard", "data_description", "tv_dashboard_ytdlp_enabled"),
    ],
    "workout_devices": [
        ("config", "step", "workout_devices", "data", "workout_device_ids"),
        ("options", "step", "workout_devices", "data", "workout_device_ids"),
    ],
    "workout_devices_config_hint": [("config", "step", "workout_devices", "description")],
    "workout_devices_options_hint": [("options", "step", "workout_devices", "description")],
    "profile_description": [("options", "step", "profile", "description")],
    "device_antplus_adapter": [("device", "antplus_adapter", "name")],
    "device_bluetooth_adapter": [("device", "bluetooth_adapter", "name")],
    "device_sensors": [("device", "sensors", "name")],
    "device_sensors_adapters": [("device", "sensors_adapters", "name")],
    "live_average_cadence": [("entity", "sensor", "live_average_cadence", "name")],
    "live_banister_trimp": [("entity", "sensor", "live_banister_trimp", "name")],
    "live_mechanical_work": [("entity", "sensor", "live_mechanical_work", "name")],
    "trimp_28d_weekly": [
        ("entity", "sensor", "training_adaptation_status", "state_attributes", "trimp_28d_weekly_equivalent", "name")
    ],
    "trimp_7d": [
        ("entity", "sensor", "training_adaptation_status", "state_attributes", "trimp_7d", "name")
    ],
}

SERVICE_TEXT = {
    "name": _row(
        "Delete old Fitness workouts", "Διαγραφή παλιών προπονήσεων Fitness", "Alte Fitness-Trainings löschen",
        "Supprimer les anciens entraînements Fitness", "Eliminar entrenamientos antiguos de Fitness", "Elimina vecchi allenamenti Fitness",
        "Eliminar treinos Fitness antigos", "Oude Fitness-trainingen verwijderen", "Usuń stare treningi Fitness",
        "Удалить старые тренировки Fitness", "Видалити старі тренування Fitness", "Eski Fitness antrenmanlarını sil",
        "删除旧 Fitness 训练", "古い Fitness ワークアウトを削除", "오래된 Fitness 운동 삭제",
    ),
    "description": _row(
        "Permanently deletes stored Fitness workout history older than the selected number of days.",
        "Διαγράφει οριστικά το αποθηκευμένο ιστορικό προπονήσεων Fitness που είναι παλαιότερο από τον επιλεγμένο αριθμό ημερών.",
        "Löscht gespeicherte Fitness-Trainings dauerhaft, die älter als die gewählte Anzahl von Tagen sind.",
        "Supprime définitivement l’historique Fitness enregistré antérieur au nombre de jours choisi.",
        "Elimina permanentemente el historial de entrenamientos de Fitness anterior al número de días seleccionado.",
        "Elimina definitivamente la cronologia degli allenamenti Fitness più vecchia del numero di giorni selezionato.",
        "Elimina permanentemente o histórico de treinos Fitness com mais dias do que o limite escolhido.",
        "Verwijdert opgeslagen Fitness-trainingsgeschiedenis die ouder is dan het gekozen aantal dagen definitief.",
        "Trwale usuwa zapisaną historię treningów Fitness starszą niż wybrana liczba dni.",
        "Навсегда удаляет сохранённую историю тренировок Fitness старше выбранного числа дней.",
        "Назавжди видаляє збережену історію тренувань Fitness, старішу за вибрану кількість днів.",
        "Seçilen gün sayısından eski kayıtlı Fitness antrenman geçmişini kalıcı olarak siler.",
        "永久删除早于所选天数的已存储 Fitness 训练历史。",
        "選択した日数より古い保存済み Fitness ワークアウト履歴を完全に削除します。",
        "선택한 일수보다 오래된 저장된 Fitness 운동 기록을 영구 삭제합니다.",
    ),
    "profile_name": _row(
        "Fitness profile", "Προφίλ Fitness", "Fitness-Profil", "Profil Fitness", "Perfil de Fitness",
        "Profilo Fitness", "Perfil Fitness", "Fitness-profiel", "Profil Fitness", "Профиль Fitness",
        "Профіль Fitness", "Fitness profili", "Fitness 个人资料", "Fitness プロフィール", "Fitness 프로필",
    ),
    "profile_description": _row(
        "Fitness profile whose stored workout history should be cleaned up.",
        "Προφίλ Fitness του οποίου θα καθαριστεί το αποθηκευμένο ιστορικό προπονήσεων.",
        "Fitness-Profil, dessen gespeicherter Trainingsverlauf bereinigt werden soll.",
        "Profil Fitness dont l’historique d’entraînement enregistré doit être nettoyé.",
        "Perfil de Fitness cuyo historial de entrenamientos almacenado se limpiará.",
        "Profilo Fitness di cui eliminare la cronologia degli allenamenti memorizzata.",
        "Perfil Fitness cujo histórico de treinos guardado será limpo.",
        "Fitness-profiel waarvan de opgeslagen trainingsgeschiedenis moet worden opgeschoond.",
        "Profil Fitness, którego zapisana historia treningów ma zostać wyczyszczona.",
        "Профиль Fitness, для которого нужно очистить сохранённую историю тренировок.",
        "Профіль Fitness, для якого потрібно очистити збережену історію тренувань.",
        "Kayıtlı antrenman geçmişi temizlenecek Fitness profili.",
        "要清理已存储训练历史的 Fitness 个人资料。",
        "保存済みワークアウト履歴を整理する Fitness プロフィール。",
        "저장된 운동 기록을 정리할 Fitness 프로필입니다.",
    ),
    "days_name": _row(
        "Keep days", "Ημέρες διατήρησης", "Aufbewahrungstage", "Jours à conserver", "Días a conservar",
        "Giorni da conservare", "Dias a manter", "Dagen bewaren", "Liczba dni do zachowania", "Дней хранения",
        "Днів зберігання", "Saklanacak gün", "保留天数", "保持日数", "보관 일수",
    ),
    "days_description": _row(
        "Keep workouts from this many most recent days; delete anything older.",
        "Διατήρησε τις προπονήσεις των πιο πρόσφατων ημερών και διέγραψε οτιδήποτε παλαιότερο.",
        "Behält Trainings aus dieser Anzahl der jüngsten Tage und löscht alles Ältere.",
        "Conserve les entraînements des jours les plus récents indiqués et supprime tout ce qui est plus ancien.",
        "Conserva los entrenamientos de este número de días recientes y elimina los anteriores.",
        "Conserva gli allenamenti di questo numero di giorni recenti ed elimina quelli più vecchi.",
        "Mantém os treinos deste número de dias mais recentes e elimina os mais antigos.",
        "Bewaar trainingen van dit aantal meest recente dagen en verwijder alles wat ouder is.",
        "Zachowaj treningi z tylu ostatnich dni, a starsze usuń.",
        "Сохранить тренировки за указанное число последних дней, а более старые удалить.",
        "Зберегти тренування за вказану кількість останніх днів, а старіші видалити.",
        "Bu sayıdaki en son güne ait antrenmanları tut; daha eskileri sil.",
        "保留最近这些天的训练，并删除更早的记录。",
        "直近の指定日数のワークアウトを保持し、それより古いものを削除します。",
        "최근 지정한 일수의 운동을 보관하고 그보다 오래된 기록은 삭제합니다.",
    ),
}


def _get(data: dict, path: tuple[str, ...]):
    value = data
    for part in path:
        value = value[part]
    return value


def _set(data: dict, path: tuple[str, ...], value) -> None:
    target = data
    for part in path[:-1]:
        target = target.setdefault(part, {})
    target[path[-1]] = value


def _leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, (*path, key))
    else:
        yield path, value


def _service(language: str) -> dict:
    return {
        "name": SERVICE_TEXT["name"][language],
        "description": SERVICE_TEXT["description"][language],
        "fields": {
            "config_entry_id": {
                "name": SERVICE_TEXT["profile_name"][language],
                "description": SERVICE_TEXT["profile_description"][language],
            },
            "days": {
                "name": SERVICE_TEXT["days_name"][language],
                "description": SERVICE_TEXT["days_description"][language],
            },
        },
    }


def main() -> None:
    files = {"strings": FITNESS / "strings.json"}
    files.update({language: FITNESS / "translations" / f"{language}.json" for language in LANGUAGES})

    documents: dict[str, dict] = {}
    for key, path in files.items():
        language = "en" if key == "strings" else key
        data = json.loads(path.read_text(encoding="utf-8"))
        for concept, paths in PATHS.items():
            native = TEXT[concept][language]
            for value_path in paths:
                # These paths are the explicit audit scope. Applying the
                # reviewed native value unconditionally also fixes hybrid
                # strings such as "Live average cadence" with only the first
                # word translated, which an equality-only English leak check
                # cannot detect.
                _set(data, value_path, native)
        for value_path, translations in ENTITY_NAMES.items():
            _set(data, value_path, translations[language])
        data.setdefault("services", {})["delete_workouts_before"] = _service(language)
        documents[key] = data

    canonical = documents["strings"]
    canonical_shape = {path for path, _value in _leaves(canonical)}
    canonical_values = dict(_leaves(canonical))
    for key, data in documents.items():
        shape = {path for path, _value in _leaves(data)}
        if shape != canonical_shape:
            raise RuntimeError(f"Translation shape mismatch after audit: {key}")
        for path, value in _leaves(data):
            if isinstance(value, str):
                expected = set(re.findall(r"\{[^}]+\}", str(canonical_values[path])))
                actual = set(re.findall(r"\{[^}]+\}", value))
                if actual != expected:
                    raise RuntimeError(f"Placeholder mismatch: {key} {'.'.join(path)}")
                if not value.strip():
                    raise RuntimeError(f"Empty translation: {key} {'.'.join(path)}")

    if documents["en"] != canonical:
        raise RuntimeError("English translation does not match strings.json")

    for key, path in files.items():
        path.write_text(
            json.dumps(documents[key], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
