const FITNESS_DASHBOARD_VERSION = "unreleased-82";
const FITNESS_TV_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card-v75";
const FITNESS_TV_SETUP_CARD_TAG = "fitness-tv-setup-card-v75";
const FITNESS_TV_LOVELACE_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card";
const FITNESS_TV_LOVELACE_SETUP_CARD_TAG = "fitness-tv-setup-card";
const FITNESS_BRAND_ICON_PATH = "/fitness/brand/icon.png";
const FITNESS_BRAND_ICON_SVG_PATH = "M14 2.1a1.7 1.7 0 1 1-3.4 0 1.7 1.7 0 0 1 3.4 0M9.2 5.2c1-.9 2.2-1.2 3.4-.7l2.1.9 2.5-1.5 1 1.5-3.1 2c-.5.3-1 .3-1.5.1l-1.2-.5-1.5 3 2 1.2 1.8 4.1-1.8.8-1.5-3.2-2.1-1.1-1.3 2.5-3.1 2.9-1.3-1.4 2.7-2.6 2.9-6.1-1.1 1-2.4 1.6-3.8 1.7V6.8c1.1-.1 2.3-.6 3.2-1.6M18.5 9.6c1.7-1.8 4.7.7 2.3 3.1l-2.3 2.2-2.3-2.2c-2.4-2.4.6-4.9 2.3-3.1M2 7h3.7v1.2H2zm1 3h3v1.2H3zm1 3h2v1.2H4z";
window.customIconsets = window.customIconsets || {};
window.customIconsets.fitness = window.customIconsets.fitness || (async (name) => name === "logo" ? {path:FITNESS_BRAND_ICON_SVG_PATH,viewBox:"0 0 24 24"} : {});
const _fitnessBrandIconUrl = (hass) => {
  try { if (typeof hass?.hassUrl === "function") return hass.hassUrl(FITNESS_BRAND_ICON_PATH); } catch (_err) {}
  return FITNESS_BRAND_ICON_PATH;
};

const _fitnessAccessCopy = (labels = {}) => ({
  denied:labels.access_denied,
  denied_hint:labels.access_denied_hint,
  view_only:labels.view_only,
  view_only_hint:labels.view_only_hint,
  own:labels.own_profile,
});

const _fitnessEnsureFrontendVersion = (serverVersion) => {
  const expected = String(serverVersion || "");
  if (!expected || expected === FITNESS_DASHBOARD_VERSION) return false;
  const key = "fitness-tv-frontend-reload";
  const marker = `${expected}:${location.pathname}`;
  if (sessionStorage.getItem(key) === marker) return false;
  sessionStorage.setItem(key, marker);
  location.reload();
  return true;
};

const _fitnessOpenExternal = (target) => {
  const url = String(target || "").trim();
  if (!/^https?:\/\//i.test(url)) return false;
  // Using window.open(..., "noopener") can legally return null even when a
  // browser did open the new tab, which caused Fitness to also navigate its own
  // tab as a false popup-blocker fallback. A real anchor has deterministic
  // target=_blank semantics and never destroys the Fitness TV route.
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  return true;
};


const FITNESS_READINESS_TEXT = {
  en:{confidence:"confidence from available evidence",sleep:"Sleep",training:"Training recovery",response:"Recovery response",vs28:"vs 28d"},
  el:{confidence:"βεβαιότητα από τα διαθέσιμα δεδομένα",sleep:"Ύπνος",training:"Αποκατάσταση προπόνησης",response:"Απόκριση αποκατάστασης",vs28:"έναντι 28 ημ."},
  de:{confidence:"Konfidenz aus verfügbaren Daten",sleep:"Schlaf",training:"Trainingserholung",response:"Erholungsreaktion",vs28:"vs. 28 T."},
  fr:{confidence:"confiance selon les données disponibles",sleep:"Sommeil",training:"Récupération d’entraînement",response:"Réponse de récupération",vs28:"vs 28 j"},
  es:{confidence:"confianza según los datos disponibles",sleep:"Sueño",training:"Recuperación del entrenamiento",response:"Respuesta de recuperación",vs28:"vs 28 d"},
  it:{confidence:"affidabilità dai dati disponibili",sleep:"Sonno",training:"Recupero dall’allenamento",response:"Risposta di recupero",vs28:"vs 28 g"},
  pt:{confidence:"confiança com os dados disponíveis",sleep:"Sono",training:"Recuperação do treino",response:"Resposta de recuperação",vs28:"vs 28 d"},
  nl:{confidence:"betrouwbaarheid op basis van beschikbare gegevens",sleep:"Slaap",training:"Trainingsherstel",response:"Herstelrespons",vs28:"t.o.v. 28 d"},
  pl:{confidence:"pewność na podstawie dostępnych danych",sleep:"Sen",training:"Regeneracja po treningu",response:"Odpowiedź regeneracyjna",vs28:"vs 28 dni"},
  ru:{confidence:"уверенность по доступным данным",sleep:"Сон",training:"Восстановление после тренировки",response:"Восстановительная реакция",vs28:"к 28 дн."},
  uk:{confidence:"впевненість за доступними даними",sleep:"Сон",training:"Відновлення після тренування",response:"Відновна реакція",vs28:"до 28 дн."},
  tr:{confidence:"mevcut verilere dayalı güven",sleep:"Uyku",training:"Antrenman toparlanması",response:"Toparlanma yanıtı",vs28:"28 güne göre"},
  zh:{confidence:"基于可用数据的置信度",sleep:"睡眠",training:"训练恢复",response:"恢复反应",vs28:"相比28天"},
  ja:{confidence:"利用可能なデータに基づく信頼度",sleep:"睡眠",training:"トレーニング回復",response:"回復反応",vs28:"28日比"},
  ko:{confidence:"사용 가능한 데이터 기반 신뢰도",sleep:"수면",training:"훈련 회복",response:"회복 반응",vs28:"28일 대비"},
};

const FITNESS_READINESS_LEVELS = {
  en:{excellent:"Excellent",high:"High",moderate:"Moderate",low:"Low",very_low:"Very low",insufficient_data:"Insufficient data"},
  el:{excellent:"Εξαιρετική",high:"Υψηλή",moderate:"Μέτρια",low:"Χαμηλή",very_low:"Πολύ χαμηλή",insufficient_data:"Ανεπαρκή δεδομένα"},
  de:{excellent:"Ausgezeichnet",high:"Hoch",moderate:"Mittel",low:"Niedrig",very_low:"Sehr niedrig",insufficient_data:"Unzureichende Daten"},
  fr:{excellent:"Excellente",high:"Élevée",moderate:"Modérée",low:"Faible",very_low:"Très faible",insufficient_data:"Données insuffisantes"},
  es:{excellent:"Excelente",high:"Alta",moderate:"Moderada",low:"Baja",very_low:"Muy baja",insufficient_data:"Datos insuficientes"},
  it:{excellent:"Eccellente",high:"Alta",moderate:"Moderata",low:"Bassa",very_low:"Molto bassa",insufficient_data:"Dati insufficienti"},
  pt:{excellent:"Excelente",high:"Alta",moderate:"Moderada",low:"Baixa",very_low:"Muito baixa",insufficient_data:"Dados insuficientes"},
  nl:{excellent:"Uitstekend",high:"Hoog",moderate:"Gemiddeld",low:"Laag",very_low:"Zeer laag",insufficient_data:"Onvoldoende gegevens"},
  pl:{excellent:"Doskonała",high:"Wysoka",moderate:"Umiarkowana",low:"Niska",very_low:"Bardzo niska",insufficient_data:"Za mało danych"},
  ru:{excellent:"Отличная",high:"Высокая",moderate:"Умеренная",low:"Низкая",very_low:"Очень низкая",insufficient_data:"Недостаточно данных"},
  uk:{excellent:"Відмінна",high:"Висока",moderate:"Помірна",low:"Низька",very_low:"Дуже низька",insufficient_data:"Недостатньо даних"},
  tr:{excellent:"Mükemmel",high:"Yüksek",moderate:"Orta",low:"Düşük",very_low:"Çok düşük",insufficient_data:"Yetersiz veri"},
  zh:{excellent:"极佳",high:"高",moderate:"中等",low:"低",very_low:"很低",insufficient_data:"数据不足"},
  ja:{excellent:"非常に良い",high:"高い",moderate:"中程度",low:"低い",very_low:"非常に低い",insufficient_data:"データ不足"},
  ko:{excellent:"매우 좋음",high:"높음",moderate:"보통",low:"낮음",very_low:"매우 낮음",insufficient_data:"데이터 부족"},
};

const PICKER_DESCRIPTIONS = {
  en: "Workouts, sleep, recovery and fitness progress in one adaptive dashboard.",
  el: "Προπονήσεις, ύπνος, αποκατάσταση και πρόοδος φυσικής κατάστασης σε έναν προσαρμοζόμενο πίνακα.",
  de: "Training, Schlaf, Erholung und Fitnessfortschritt in einem adaptiven Dashboard.",
  fr: "Entraînements, sommeil, récupération et progression dans un tableau adaptatif.",
  es: "Entrenamientos, sueño, recuperación y progreso físico en un panel adaptativo.",
  it: "Allenamenti, sonno, recupero e progressi in una dashboard adattiva.",
  pt: "Treinos, sono, recuperação e progresso físico num painel adaptativo.",
  nl: "Trainingen, slaap, herstel en fitnessvoortgang in één adaptief dashboard.",
  pl: "Treningi, sen, regeneracja i postęp kondycji w jednym adaptacyjnym panelu.",
  ru: "Тренировки, сон, восстановление и прогресс в одной адаптивной панели.",
  uk: "Тренування, сон, відновлення та прогрес в одній адаптивній панелі.",
  tr: "Antrenman, uyku, toparlanma ve fitness ilerlemesi tek uyarlanabilir panelde.",
  zh: "在一个自适应仪表板中查看训练、睡眠、恢复和体能进步。",
  ja: "ワークアウト、睡眠、回復、フィットネスの進歩を1つの適応型ダッシュボードにまとめます。",
  ko: "운동, 수면, 회복 및 체력 향상을 하나의 적응형 대시보드에서 확인합니다.",
};
const PICKER_ENGLISH_LIVE_CARD = {name: "Fitness live workout"};
const PICKER_CARD_NAMES = {
  en:{live:PICKER_ENGLISH_LIVE_CARD.name,workout:"Fitness workout",sleep:"Fitness sleep & recovery",evaluation:"Fitness evaluation"},
  el:{live:"Fitness ζωντανή προπόνηση",workout:"Fitness προπόνηση",sleep:"Fitness ύπνος & αποκατάσταση",evaluation:"Fitness αξιολόγηση"},
  de:{live:"Fitness Live-Training",workout:"Fitness Training",sleep:"Fitness Schlaf & Erholung",evaluation:"Fitness Auswertung"},
  fr:{live:"Fitness – entraînement en direct",workout:"Fitness – entraînement",sleep:"Fitness – sommeil et récupération",evaluation:"Fitness – évaluation"},
  es:{live:"Fitness: entrenamiento en vivo",workout:"Fitness: entrenamiento",sleep:"Fitness: sueño y recuperación",evaluation:"Fitness: evaluación"},
  it:{live:"Fitness: allenamento live",workout:"Fitness: allenamento",sleep:"Fitness: sonno e recupero",evaluation:"Fitness: valutazione"},
  pt:{live:"Fitness: treino em direto",workout:"Fitness: treino",sleep:"Fitness: sono e recuperação",evaluation:"Fitness: avaliação"},
  nl:{live:"Fitness live training",workout:"Fitness training",sleep:"Fitness slaap & herstel",evaluation:"Fitness evaluatie"},
  pl:{live:"Fitness – trening na żywo",workout:"Fitness – trening",sleep:"Fitness – sen i regeneracja",evaluation:"Fitness – ocena"},
  ru:{live:"Fitness: тренировка в реальном времени",workout:"Fitness: тренировка",sleep:"Fitness: сон и восстановление",evaluation:"Fitness: оценка"},
  uk:{live:"Fitness: тренування наживо",workout:"Fitness: тренування",sleep:"Fitness: сон і відновлення",evaluation:"Fitness: оцінка"},
  tr:{live:"Fitness canlı antrenman",workout:"Fitness antrenman",sleep:"Fitness uyku ve toparlanma",evaluation:"Fitness değerlendirme"},
  zh:{live:"Fitness 实时训练",workout:"Fitness 训练",sleep:"Fitness 睡眠与恢复",evaluation:"Fitness 评估"},
  ja:{live:"Fitness ライブワークアウト",workout:"Fitness ワークアウト",sleep:"Fitness 睡眠と回復",evaluation:"Fitness 評価"},
  ko:{live:"Fitness 실시간 운동",workout:"Fitness 운동",sleep:"Fitness 수면 및 회복",evaluation:"Fitness 평가"},
};
const PICKER_LANG = (document.documentElement.lang || navigator.language || "en").toLowerCase().split(/[-_]/)[0];
const PICKER_CARD_COPY = PICKER_CARD_NAMES[PICKER_LANG] || PICKER_CARD_NAMES.en;
const PICKER_DESCRIPTION = PICKER_DESCRIPTIONS[PICKER_LANG] || PICKER_DESCRIPTIONS.en;

const entityName = (hass, entityId) => {
  if (!entityId) return "";
  const stateObj = hass.states[entityId];
  try {
    if (stateObj && typeof hass.formatEntityName === "function") {
      return hass.formatEntityName(stateObj, { type: "entity" });
    }
  } catch (_err) {}
  return stateObj?.attributes?.friendly_name || entityId;
};

const tile = (entity, extra = {}) => ({
  type: "tile",
  entity,
  vertical: false,
  ...extra,
});

const heading = (text, icon, badges = []) => ({
  type: "heading",
  heading: text,
  icon,
  ...(badges.length ? { badges } : {}),
});

const entityBadge = (entity) => ({ type: "entity", entity, show_state: true });

const only = (_hass, entities, keys) => keys.map((key) => entities[key]).filter(Boolean);

const tileGrid = (hass, ids, columns = 2) => {
  const cards = ids.filter(Boolean).map((id) => tile(id));
  if (!cards.length) return null;
  return { type: "grid", columns, square: false, cards };
};

const statisticGraph = (hass, ids, title, days = 90) => {
  const entities = ids.filter(Boolean);
  if (!entities.length) return null;
  return {
    type: "statistics-graph",
    title,
    entities,
    days_to_show: days,
    period: "day",
    stat_types: ["mean"],
    hide_legend: entities.length === 1,
    chart_type: "line",
  };
};

const markdownAI = (entity, title) => entity ? {
  type: "markdown",
  title,
  content: `{% set text = state_attr('${entity}', 'text') %}\n{{ text if text else states('${entity}') }}`,
} : null;

const section = (cards) => ({ type: "grid", cards: cards.filter(Boolean) });

const FITNESS_ROUTE_MAX_INPUT_CHARS = 250000;
const FITNESS_ROUTE_MAX_EXTRACTED_POINTS = 20000;
const FITNESS_ROUTE_MAX_RENDER_POINTS = 5000;
const FITNESS_ROUTE_MAX_DEPTH = 8;

class FitnessRouteCard extends HTMLElement {
  setConfig(config) {
    if (!config) throw new Error("fitness-route-card requires a configuration");
    this.config = config;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.hidden = true;
    _fitnessBindMoreInfo(this);
    if (this._zoomDelta === undefined) this._zoomDelta = 0;
    if (this._panX === undefined) this._panX = 0;
    if (this._panY === undefined) this._panY = 0;
    this._resizeObserver = this._resizeObserver || new ResizeObserver((entries) => {
      const width = Math.round(entries?.[0]?.contentRect?.width || this.clientWidth || 0);
      if (!width || width === this._lastRenderedWidth) return;
      this._lastRenderedWidth = width;
      this._render();
    });
  }

  static getConfigElement() {
    return document.createElement("fitness-route-card-editor");
  }

  static getStubConfig() {
    return {};
  }

  set hass(hass) {
    this._hass = hass;

    // Resolve the provider entity only when the card/profile configuration
    // changes. Home Assistant updates `hass` very frequently; doing a WS
    // lookup on every state update caused needless work and map flicker.
    const resolveKey = `${this.config?.profile_entry_id || ""}|${this.config?.entity || ""}|${this.config?.attribute || ""}`;
    if (resolveKey !== this._resolvedConfigKey && !this._resolvingSource) {
      this._resolvedConfigKey = resolveKey;
      this._resolveSource();
      return;
    }

    // Once resolved, redraw only when the actual route payload changes.
    const signature = this._routeSignature();
    if (signature !== this._lastRouteSignature) {
      this._lastRouteSignature = signature;
      this._render();
    }
  }

  _routeSignature() {
    if (!this._hass || !this.config) return "";
    const entityId = this._resolved?.entity_id || this.config.entity;
    const attribute = this._resolved?.attribute || this.config.attribute || "polyline";
    const state = entityId ? this._hass.states[entityId] : null;
    const value = state?.attributes?.[attribute];
    // Never run JSON.stringify(value) on provider-controlled route payloads.
    if (state !== this._routeStateReference) {
      this._routeStateReference = state;
      this._routeStateRevision = (this._routeStateRevision || 0) + 1;
    }
    let encoded = `${this._routeStateRevision || 0}|${state?.state || ""}|${typeof value}`;
    if (typeof value === "string") {
      encoded += `|${value.length}|${value.slice(0, 64)}|${value.slice(-64)}`;
    } else if (Array.isArray(value)) {
      encoded += `|${value.length}|${String(value[0] ?? "").slice(0, 64)}|${String(value[value.length - 1] ?? "").slice(0, 64)}`;
    } else if (value && typeof value === "object") {
      encoded += `|${Object.keys(value).sort().slice(0, 32).join(",")}`;
    }

    const summary = _fitnessWorkoutSourceSignature(this._profile, this._hass);

    // Manual gesture zoom/pan intentionally do not participate in this
    // signature: gestures commit their own render and must not trigger a second
    // redraw on the next unrelated Home Assistant state update.
    return `${entityId || ""}|${attribute}|${encoded}|${summary}`;
  }

  async _resolveSource() {
    if (!this._hass || !this.config) return;
    this._resolvingSource = true;
    try {
      if (this.config.entity) {
        this._resolved = { entity_id: this.config.entity, attribute: this.config.attribute || "polyline" };
      } else {
        const data = await this._hass.callWS({ type: "fitness/dashboard/config" });
        const profiles = data?.profiles || [];
        const profile = profiles.find((item) => item.entry_id === this.config.profile_entry_id) || (profiles.length === 1 ? profiles[0] : null);
        this._profile = profile;
        this._resolved = (profile?.route_candidates || [])[0] || null;
      }
    } catch (_err) {
      this._resolved = null;
    } finally {
      this._resolvingSource = false;
    }
    this._lastRouteSignature = this._routeSignature();
    this._render();
  }

  connectedCallback() {
    this._resizeObserver?.observe(this);
  }

  disconnectedCallback() {
    this._resizeObserver?.disconnect();
  }

  getCardSize() { return 6; }

  _decodeEncodedPolyline(str) {
    str = String(str || "").slice(0, FITNESS_ROUTE_MAX_INPUT_CHARS);
    const coords = [];
    let index = 0, lat = 0, lon = 0;
    while (index < str.length && coords.length < FITNESS_ROUTE_MAX_EXTRACTED_POINTS) {
      let b, shift = 0, result = 0;
      do { b = str.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20 && index <= str.length);
      lat += (result & 1) ? ~(result >> 1) : (result >> 1);
      shift = 0; result = 0;
      do { b = str.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20 && index <= str.length);
      lon += (result & 1) ? ~(result >> 1) : (result >> 1);
      coords.push([lat / 1e5, lon / 1e5]);
    }
    return coords;
  }

  _extractPoints(value, depth = 0) {
    if (!value || depth > FITNESS_ROUTE_MAX_DEPTH) return [];
    if (typeof value === "string") {
      const trimmed = value.trim().slice(0, FITNESS_ROUTE_MAX_INPUT_CHARS);
      if (!trimmed) return [];
      try { return this._extractPoints(JSON.parse(trimmed), depth + 1); } catch (_err) {}
      if (/^[A-Za-z0-9_?@`~\\\[\]{}|^]+$/.test(trimmed) || trimmed.length > 20) {
        try { return this._decodeEncodedPolyline(trimmed); } catch (_err) {}
      }
      return [];
    }
    if (Array.isArray(value)) {
      const out = [];
      for (const item of value) {
        if (out.length >= FITNESS_ROUTE_MAX_EXTRACTED_POINTS) break;
        if (Array.isArray(item) && item.length >= 2) {
          const a = Number(item[0]), b = Number(item[1]);
          if (Number.isFinite(a) && Number.isFinite(b)) {
            if (Math.abs(a) <= 90 && Math.abs(b) <= 180) out.push([a, b]);
            else if (Math.abs(b) <= 90 && Math.abs(a) <= 180) out.push([b, a]);
          }
        } else if (item && typeof item === "object") {
          const lat = Number(item.lat ?? item.latitude ?? item.y);
          const lon = Number(item.lon ?? item.lng ?? item.longitude ?? item.x);
          if (Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180) out.push([lat, lon]);
          else out.push(...this._extractPoints(item, depth + 1).slice(0, FITNESS_ROUTE_MAX_EXTRACTED_POINTS - out.length));
        }
      }
      return out;
    }
    if (value && typeof value === "object") {
      for (const key of ["polyline", "route", "coordinates", "track", "points", "gps_points", "geometry"]) {
        if (key in value) {
          const points = this._extractPoints(value[key], depth + 1);
          if (points.length) return points;
        }
      }
    }
    return [];
  }

  _renderPoints(points) {
    if (points.length <= FITNESS_ROUTE_MAX_RENDER_POINTS) return points;
    const result = [];
    const last = points.length - 1;
    for (let index = 0; index < FITNESS_ROUTE_MAX_RENDER_POINTS; index++) {
      result.push(points[Math.round(index * last / (FITNESS_ROUTE_MAX_RENDER_POINTS - 1))]);
    }
    return result;
  }

  _mercator(lat, lon, zoom) {
    const scale = 256 * (2 ** zoom);
    const x = (lon + 180) / 360 * scale;
    const sin = Math.sin(lat * Math.PI / 180);
    const y = (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale;
    return [x, y];
  }

  _fit(points, width, height) {
    const pad = 12;
    let baseZoom = 2;
    for (let zoom = 18; zoom >= 2; zoom--) {
      const projected = points.map(([lat, lon]) => this._mercator(lat, lon, zoom));
      const xs = projected.map((p) => p[0]), ys = projected.map((p) => p[1]);
      if ((Math.max(...xs)-Math.min(...xs)) <= width-pad*2 && (Math.max(...ys)-Math.min(...ys)) <= height-pad*2) {
        baseZoom = zoom;
        break;
      }
    }
    const zoom = Math.max(2, Math.min(19, baseZoom + (this._zoomDelta || 0)));
    const projected = points.map(([lat, lon]) => this._mercator(lat, lon, zoom));
    const xs = projected.map((p) => p[0]), ys = projected.map((p) => p[1]);
    return { zoom, projected, minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
  }

  _isRunningWorkout() {
    return this._profile?.latest_workout?.sport === "running";
  }

  _workoutSummary() {
    const e = this._profile?.entities || {};
    const running = this._isRunningWorkout();
    const runPace = running ? _fitnessRunPace(this._profile, this._hass) : null;
    const sourceKeys = [
      "last_workout", "last_workout_distance", "last_workout_duration",
      "last_workout_average_speed", "last_workout_avg_hr", "last_workout_max_hr",
      "last_workout_avg_power", "last_workout_weighted_power",
      "last_workout_avg_cadence", "last_workout_elevation_gain",
      "last_workout_calories", "last_workout_training_load", "last_workout_vo2max"
    ];
    const items = [];
    for (const key of sourceKeys) {
      const metric = _fitnessWorkoutSourceMetric(this._profile, this._hass, key, _fitnessWorkoutMetricDecimals(key));
      if (!metric || metric.value === null || metric.value === undefined || metric.value === "") continue;
      if (running && key === "last_workout_average_speed") {
        if (runPace) items.push({name:this._profile?.labels?.pace, value:runPace, entityId:metric.entityId});
        continue;
      }
      items.push({
        name: key === "last_workout" ? (_fitnessWorkoutSourceLabel(this._profile, this._hass, key, metric) || this._profile?.labels?.workout) : _fitnessWorkoutSourceLabel(this._profile, this._hass, key, metric),
        value: metric.display,
        entityId: metric.entityId,
      });
    }
    const fitnessKeys = [
      "last_workout_hrr_60s", "last_workout_banister_trimp",
      "last_workout_aerobic_efficiency", "last_workout_aerobic_decoupling"
    ];
    for (const key of fitnessKeys) {
      const entityId = e[key];
      const state = entityId ? this._hass.states[entityId] : null;
      if (!state || ["unknown","unavailable"].includes(String(state.state).toLowerCase())) continue;
      items.push({name:entityName(this._hass, entityId), value:_fitnessDisplay(state,1), entityId});
    }
    return items;
  }

  _resetGestureTransform() {
    const scene = this.shadowRoot?.querySelector(".map-scene");
    if (!scene) return;
    scene.style.transform = "";
    scene.style.transformOrigin = "";
  }

  _bindMapGestures() {
    const map = this.shadowRoot?.querySelector(".map");
    const scene = this.shadowRoot?.querySelector(".map-scene");
    if (!map || !scene) return;

    const pointers = new Map();
    let dragStart = null;
    let dragLast = null;
    let pinchStart = null;
    let lastTapAt = 0;

    const point = (event) => {
      const rect = map.getBoundingClientRect();
      return {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      };
    };

    const midpoint = (a, b) => ({
      x: (a.x + b.x) / 2,
      y: (a.y + b.y) / 2,
    });

    const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

    const beginPinch = () => {
      const values = [...pointers.values()];
      if (values.length < 2) return;
      const a = values[0];
      const b = values[1];
      const mid = midpoint(a, b);
      pinchStart = {
        distance: Math.max(1, distance(a, b)),
        midpoint: mid,
        zoomDelta: this._zoomDelta || 0,
      };
      dragStart = null;
      dragLast = null;
    };

    const commitDrag = () => {
      if (!dragStart || !dragLast) return false;
      const dx = dragLast.x - dragStart.x;
      const dy = dragLast.y - dragStart.y;
      if (Math.abs(dx) < 2 && Math.abs(dy) < 2) return false;
      // Dragging the visible map right means the map origin moves left.
      this._panX = (this._panX || 0) - dx;
      this._panY = (this._panY || 0) - dy;
      this._resetGestureTransform();
      this._render();
      return true;
    };

    const commitPinch = () => {
      if (!pinchStart) return false;
      const values = [...pointers.values()];
      // When one finger has already lifted, use the last scale recorded by
      // pointermove. This avoids losing the final pinch amount.
      const scale = this._gestureScale || 1;
      const steps = Math.round(Math.log2(Math.max(0.25, Math.min(4, scale))));
      this._resetGestureTransform();
      this._gestureScale = 1;
      if (!steps) {
        pinchStart = null;
        return false;
      }

      const previousZoom = this._zoomDelta || 0;
      const nextZoom = Math.max(-5, Math.min(5, previousZoom + steps));
      const appliedSteps = nextZoom - previousZoom;
      if (!appliedSteps) {
        pinchStart = null;
        return false;
      }

      // Keep the geographical point below the pinch midpoint approximately
      // stationary after switching to the new OSM tile zoom level.
      const factor = 2 ** appliedSteps;
      const cx = map.clientWidth / 2;
      const cy = map.clientHeight / 2;
      const focus = pinchStart.midpoint;
      this._panX = (this._panX || 0) + (focus.x - cx) * (1 - 1 / factor);
      this._panY = (this._panY || 0) + (focus.y - cy) * (1 - 1 / factor);
      this._zoomDelta = nextZoom;
      pinchStart = null;
      this._render();
      return true;
    };

    map.onpointerdown = (event) => {
      // Primary mouse button only; touch/pen have button 0 as well.
      if (event.pointerType === "mouse" && event.button !== 0) return;
      const p = point(event);
      pointers.set(event.pointerId, p);
      map.setPointerCapture?.(event.pointerId);

      if (pointers.size === 1) {
        dragStart = p;
        dragLast = p;
        pinchStart = null;
      } else if (pointers.size === 2) {
        beginPinch();
      }
      event.preventDefault();
    };

    map.onpointermove = (event) => {
      if (!pointers.has(event.pointerId)) return;
      const p = point(event);
      pointers.set(event.pointerId, p);

      if (pointers.size >= 2) {
        if (!pinchStart) beginPinch();
        const values = [...pointers.values()];
        const a = values[0], b = values[1];
        const mid = midpoint(a, b);
        const scale = Math.max(0.4, Math.min(2.5, distance(a, b) / Math.max(1, pinchStart.distance)));
        this._gestureScale = scale;
        const translateX = mid.x - pinchStart.midpoint.x;
        const translateY = mid.y - pinchStart.midpoint.y;
        scene.style.transformOrigin = `${pinchStart.midpoint.x}px ${pinchStart.midpoint.y}px`;
        scene.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
      } else if (dragStart) {
        dragLast = p;
        const dx = p.x - dragStart.x;
        const dy = p.y - dragStart.y;
        scene.style.transform = `translate(${dx}px, ${dy}px)`;
      }
      event.preventDefault();
    };

    const finishPointer = (event) => {
      const wasPinching = pointers.size >= 2 || Boolean(pinchStart);
      pointers.delete(event.pointerId);
      try { map.releasePointerCapture?.(event.pointerId); } catch (_err) {}

      if (wasPinching) {
        if (pointers.size < 2) {
          commitPinch();
          const remaining = [...pointers.values()][0];
          dragStart = remaining || null;
          dragLast = remaining || null;
        }
      } else if (pointers.size === 0) {
        const moved = commitDrag();
        this._resetGestureTransform();
        dragStart = null;
        dragLast = null;

        // Double tap/click fits the whole route without requiring a button.
        if (!moved) {
          const now = Date.now();
          if (now - lastTapAt < 350) {
            this._zoomDelta = 0;
            this._panX = 0;
            this._panY = 0;
            lastTapAt = 0;
            this._render();
          } else {
            lastTapAt = now;
          }
        }
      }
      event.preventDefault();
    };

    map.onpointerup = finishPointer;
    map.onpointercancel = finishPointer;

    // Desktop mouse wheel and trackpad zoom. One wheel gesture changes one
    // discrete OSM zoom step and keeps the cursor location as the focus.
    let wheelTimer = null;
    let wheelAccum = 0;
    map.onwheel = (event) => {
      event.preventDefault();
      wheelAccum += event.deltaY;
      clearTimeout(wheelTimer);
      wheelTimer = setTimeout(() => {
        if (Math.abs(wheelAccum) < 20) {
          wheelAccum = 0;
          return;
        }
        const step = wheelAccum < 0 ? 1 : -1;
        wheelAccum = 0;
        const previousZoom = this._zoomDelta || 0;
        const nextZoom = Math.max(-5, Math.min(5, previousZoom + step));
        if (nextZoom === previousZoom) return;

        const p = point(event);
        const factor = 2 ** (nextZoom - previousZoom);
        const cx = map.clientWidth / 2;
        const cy = map.clientHeight / 2;
        this._panX = (this._panX || 0) + (p.x - cx) * (1 - 1 / factor);
        this._panY = (this._panY || 0) + (p.y - cy) * (1 - 1 / factor);
        this._zoomDelta = nextZoom;
        this._render();
      }, 55);
    };

    map.ondblclick = (event) => {
      event.preventDefault();
      this._zoomDelta = 0;
      this._panX = 0;
      this._panY = 0;
      this._render();
    };
  }

  _render() {
    if (!this.shadowRoot || !this._hass || !this.config) return;
    const entityId = this._resolved?.entity_id || this.config.entity;
    const attribute = this._resolved?.attribute || this.config.attribute || "polyline";
    const state = entityId ? this._hass.states[entityId] : null;
    const value = state?.attributes?.[attribute];
    const points = this._renderPoints(this._extractPoints(value));
    const labels = this._profile?.labels || {};
    const title = this.config.title || labels.route || (entityId ? entityName(this._hass, entityId) : "");
    const configuredHeight = Number(this.config.height || 340);
    const height = Number.isFinite(configuredHeight)
      ? Math.max(180, Math.min(1200, configuredHeight))
      : 340;
    if (points.length < 2) {
      this.shadowRoot.innerHTML = "";
      this.hidden = true;
      const slot = this.closest?.(".tv-card-slot");
      if (slot) slot.hidden = true;
      return;
    }
    this.hidden = false;
    const slot = this.closest?.(".tv-card-slot");
    if (slot) slot.hidden = false;

    const width = Math.max(300, Math.min(8192, this.clientWidth || 600));
    this._lastRenderedWidth = Math.round(width);
    const fit = this._fit(points, width, height);
    const centerX = (fit.minX + fit.maxX) / 2;
    const centerY = (fit.minY + fit.maxY) / 2;
    const originX = centerX - width / 2 + (this._panX || 0);
    const originY = centerY - height / 2 + (this._panY || 0);
    const tileMinX = Math.floor(originX / 256), tileMaxX = Math.floor((originX + width) / 256);
    const tileMinY = Math.floor(originY / 256), tileMaxY = Math.floor((originY + height) / 256);
    const maxTile = 2 ** fit.zoom;
    const tiles = [];
    for (let y = tileMinY; y <= tileMaxY; y++) {
      if (y < 0 || y >= maxTile) continue;
      for (let x = tileMinX; x <= tileMaxX; x++) {
        const wrappedX = ((x % maxTile) + maxTile) % maxTile;
        tiles.push(`<img class="tile" draggable="false" src="https://tile.openstreetmap.org/${fit.zoom}/${wrappedX}/${y}.png" style="left:${x * 256 - originX}px;top:${y * 256 - originY}px">`);
      }
    }
    const route = fit.projected.map(([x, y]) => `${(x - originX).toFixed(1)},${(y - originY).toFixed(1)}`).join(" ");
    const start = fit.projected[0], end = fit.projected[fit.projected.length - 1];
    const summary = this._workoutSummary();
    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="header entity-link" data-more-info="${this._escape(entityId || "")}"><div class="title">${this._escape(title)}</div><div class="meta">${points.length} GPS</div></div>
        <div class="map" style="height:${height}px" title="${this._escape(labels.map_interaction_hint)}">
          <div class="map-scene">
            ${tiles.join("")}
            <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
              <polyline points="${route}" fill="none" stroke="var(--primary-color)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
              <circle cx="${start[0]-originX}" cy="${start[1]-originY}" r="6" class="start"/>
              <circle cx="${end[0]-originX}" cy="${end[1]-originY}" r="6" class="end"/>
            </svg>
          </div>
          <div class="attribution">© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a></div>
        </div>
        ${summary.length ? `<div class="workout-summary">${summary.map((item) => `<div class="summary-item entity-link" data-more-info="${this._escape(item.entityId || "")}"><span>${this._escape(item.name)}</span><strong>${this._escape(item.value)}</strong></div>`).join("")}</div>` : ""}
      </ha-card>
      <style>
        ha-card{overflow:hidden}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.header{display:flex;align-items:center;justify-content:space-between;padding:16px 16px 12px}.title{font-size:18px;font-weight:600}.meta{font-size:12px;color:var(--secondary-text-color)}
        .map{position:relative;overflow-x:clip;overflow-y:visible;background:var(--secondary-background-color);touch-action:none;cursor:grab;overscroll-behavior:contain}.map:active{cursor:grabbing}.map-scene{position:absolute;inset:0;will-change:transform}.tile{position:absolute;width:256px;height:256px;user-select:none;-webkit-user-drag:none;pointer-events:none}svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.start{fill:#2e7d32;stroke:white;stroke-width:2}.end{fill:#c62828;stroke:white;stroke-width:2}.workout-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;padding:12px 16px 14px}.summary-item{background:var(--secondary-background-color);border-radius:12px;padding:9px 11px;min-width:0}.summary-item span{display:block;color:var(--secondary-text-color);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.summary-item strong{display:block;margin-top:3px;font-size:14px}.attribution{position:absolute;right:4px;bottom:3px;background:rgba(255,255,255,.78);font-size:10px;padding:1px 4px;border-radius:3px;color:#333}.attribution a{color:#333}.privacy{padding:8px 16px 12px;font-size:11px;color:var(--secondary-text-color)}
      </style>`;
    this._bindMapGestures();
  }

  _escape(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
  }
}

class FitnessRouteCardEditor extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._load();
  }

  async _load() {
    if (!this._hass) return;
    try {
      const data = await this._hass.callWS({ type: "fitness/dashboard/config" });
      this._profiles = data?.profiles || [];
      if (!this.config?.profile_entry_id && this._profiles.length === 1) {
        this._changed(this._profiles[0].entry_id, false);
      }
    } catch (_err) {
      this._profiles = [];
    }
    this._render();
  }

  _changed(value, fire = true) {
    this.config = { ...this.config, profile_entry_id: value || undefined };
    if (fire) this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this.config }, bubbles: true, composed: true }));
  }

  _render() {
    if (!this.shadowRoot) return;
    const profiles = this._profiles || [];
    const lang = (document.documentElement.lang || navigator.language || "en").toLowerCase().split(/[-_]/)[0];
    const copy = {
      en:["Fitness user","Choose the Fitness user. The route source and compatible GPS entity are selected automatically.","Select a user"],
      el:["Χρήστης Fitness","Επίλεξε τον χρήστη Fitness. Η πηγή διαδρομής και η συμβατή οντότητα GPS επιλέγονται αυτόματα.","Επίλεξε χρήστη"],
      de:["Fitness-Benutzer","Wähle den Fitness-Benutzer. Routenquelle und kompatible GPS-Entität werden automatisch ausgewählt.","Benutzer auswählen"],
      fr:["Utilisateur Fitness","Choisissez l’utilisateur Fitness. La source d’itinéraire et l’entité GPS compatible sont sélectionnées automatiquement.","Choisir un utilisateur"],
      es:["Usuario de Fitness","Elige el usuario de Fitness. La fuente de ruta y la entidad GPS compatible se seleccionan automáticamente.","Elegir usuario"],
      it:["Utente Fitness","Scegli l’utente Fitness. La sorgente del percorso e l’entità GPS compatibile vengono selezionate automaticamente.","Scegli utente"],
      pt:["Utilizador Fitness","Escolha o utilizador Fitness. A origem da rota e a entidade GPS compatível são selecionadas automaticamente.","Escolher utilizador"],
      nl:["Fitness-gebruiker","Kies de Fitness-gebruiker. De routebron en compatibele GPS-entiteit worden automatisch geselecteerd.","Kies gebruiker"],
      pl:["Użytkownik Fitness","Wybierz użytkownika Fitness. Źródło trasy i zgodna encja GPS zostaną wybrane automatycznie.","Wybierz użytkownika"],
      ru:["Пользователь Fitness","Выберите пользователя Fitness. Источник маршрута и совместимая GPS-сущность будут выбраны автоматически.","Выберите пользователя"],
      uk:["Користувач Fitness","Виберіть користувача Fitness. Джерело маршруту та сумісна GPS-сутність вибираються автоматично.","Виберіть користувача"],
      tr:["Fitness kullanıcısı","Fitness kullanıcısını seçin. Rota kaynağı ve uyumlu GPS varlığı otomatik seçilir.","Kullanıcı seçin"],
      zh:["Fitness 用户","选择 Fitness 用户。路线来源和兼容的 GPS 实体会自动选择。","选择用户"],
      ja:["Fitness ユーザー","Fitness ユーザーを選択してください。ルート元と互換性のある GPS エンティティは自動選択されます。","ユーザーを選択"],
      ko:["Fitness 사용자","Fitness 사용자를 선택하세요. 경로 소스와 호환 GPS 엔티티가 자동으로 선택됩니다.","사용자 선택"],
    }[lang] || ["Fitness user","Choose the Fitness user. The route source and compatible GPS entity are selected automatically.","Select a user"];
    const options = profiles.map((p) => `<option value="${this._escape(p.entry_id)}" ${p.entry_id === this.config?.profile_entry_id ? "selected" : ""}>${this._escape(p.profile_name)}</option>`).join("");
    this.shadowRoot.innerHTML = `<div class="editor"><label>${this._escape(copy[0])}</label><select><option value="">${this._escape(copy[2])}</option>${options}</select><p>${this._escape(copy[1])}</p></div><style>.editor{padding:8px 0}label{display:block;font-weight:500;margin-bottom:8px}select{box-sizing:border-box;width:100%;padding:12px;border:1px solid var(--divider-color);border-radius:10px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit}p{color:var(--secondary-text-color);font-size:13px;line-height:1.4;margin:8px 2px 0}</style>`;
    this.shadowRoot.querySelector("select")?.addEventListener("change", (ev) => this._changed(ev.target.value));
  }
  _escape(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }
}


const VISUAL_EDITOR_COPY = {
  en: ["Fitness user", "Select a Fitness user. Compatible entities are selected automatically.", "Select a user"],
  el: ["Χρήστης Fitness", "Επίλεξε έναν χρήστη Fitness. Οι συμβατές οντότητες επιλέγονται αυτόματα.", "Επίλεξε χρήστη"],
  de: ["Fitness-Benutzer", "Wähle einen Fitness-Benutzer. Kompatible Entitäten werden automatisch ausgewählt.", "Benutzer auswählen"],
  fr: ["Utilisateur Fitness", "Choisissez un utilisateur Fitness. Les entités compatibles sont sélectionnées automatiquement.", "Choisir un utilisateur"],
  es: ["Usuario de Fitness", "Elige un usuario de Fitness. Las entidades compatibles se seleccionan automáticamente.", "Elegir usuario"],
  it: ["Utente Fitness", "Scegli un utente Fitness. Le entità compatibili vengono selezionate automaticamente.", "Scegli utente"],
  pt: ["Utilizador Fitness", "Escolha um utilizador Fitness. As entidades compatíveis são selecionadas automaticamente.", "Escolher utilizador"],
  nl: ["Fitness-gebruiker", "Kies een Fitness-gebruiker. Compatibele entiteiten worden automatisch geselecteerd.", "Kies gebruiker"],
  pl: ["Użytkownik Fitness", "Wybierz użytkownika Fitness. Zgodne encje zostaną wybrane automatycznie.", "Wybierz użytkownika"],
  ru: ["Пользователь Fitness", "Выберите пользователя Fitness. Совместимые сущности будут выбраны автоматически.", "Выберите пользователя"],
  uk: ["Користувач Fitness", "Виберіть користувача Fitness. Сумісні сутності вибираються автоматично.", "Виберіть користувача"],
  tr: ["Fitness kullanıcısı", "Bir Fitness kullanıcısı seçin. Uyumlu varlıklar otomatik seçilir.", "Kullanıcı seçin"],
  zh: ["Fitness 用户", "选择 Fitness 用户。兼容实体会自动选择。", "选择用户"],
  ja: ["Fitness ユーザー", "Fitness ユーザーを選択してください。互換性のあるエンティティは自動選択されます。", "ユーザーを選択"],
  ko: ["Fitness 사용자", "Fitness 사용자를 선택하세요. 호환 엔티티가 자동으로 선택됩니다.", "사용자 선택"],
};

class FitnessProfileCardEditor extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._load();
  }

  async _load() {
    if (!this._hass) return;
    try {
      const data = await this._hass.callWS({ type: "fitness/dashboard/config" });
      this._profiles = data?.profiles || [];
      if (!this.config?.profile_entry_id && this._profiles.length === 1) {
        this.config = { ...this.config, profile_entry_id: this._profiles[0].entry_id };
        this._fireChanged();
      }
    } catch (_err) {
      this._profiles = [];
    }
    this._render();
  }

  _fireChanged() {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this.config }, bubbles: true, composed: true }));
  }

  _render() {
    if (!this.shadowRoot) return;
    const lang = (document.documentElement.lang || navigator.language || "en").toLowerCase().split(/[-_]/)[0];
    const copy = VISUAL_EDITOR_COPY[lang] || VISUAL_EDITOR_COPY.en;
    const profiles = this._profiles || [];
    const options = profiles.map((profile) => `<option value="${this._escape(profile.entry_id)}" ${profile.entry_id === this.config?.profile_entry_id ? "selected" : ""}>${this._escape(profile.profile_name)}</option>`).join("");
    this.shadowRoot.innerHTML = `<div class="editor"><label>${this._escape(copy[0])}</label><select><option value="">${this._escape(copy[2])}</option>${options}</select><p>${this._escape(copy[1])}</p></div><style>.editor{padding:8px 0}label{display:block;font-weight:500;margin-bottom:8px}select{box-sizing:border-box;width:100%;padding:12px;border:1px solid var(--divider-color);border-radius:10px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit}p{color:var(--secondary-text-color);font-size:13px;line-height:1.4;margin:8px 2px 0}</style>`;
    this.shadowRoot.querySelector("select")?.addEventListener("change", (ev) => {
      this.config = { ...this.config, profile_entry_id: ev.target.value || undefined };
      this._fireChanged();
    });
  }

  _escape(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }
}

class FitnessComparisonCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    _fitnessBindMoreInfo(this);
  }

  static getConfigElement() { return document.createElement("fitness-comparison-card-editor"); }
  static getStubConfig() { return {}; }

  set hass(hass) {
    this._hass = hass;
    this._resolveMetrics();
  }

  async _resolveMetrics() {
    if (!this._hass || !this.config) return;
    if (Array.isArray(this.config.metrics) && this.config.metrics.length) {
      this._resolvedMetrics = this.config.metrics;
      this._render();
      return;
    }
    try {
      const data = await this._hass.callWS({ type: "fitness/dashboard/config" });
      const profiles = data?.profiles || [];
      const profile = profiles.find((item) => item.entry_id === this.config.profile_entry_id) || (profiles.length === 1 ? profiles[0] : null);
      this._profile = profile;
      const e = profile?.entities || {};
      this._resolvedMetrics = [
        ["last_workout_efficiency_vs_baseline", 20],
        ["last_workout_decoupling_vs_baseline", 20],
        ["last_workout_power_vs_baseline", 30],
        ["last_workout_speed_vs_baseline", 30],
        ["last_workout_trimp_vs_recent", 50],
      ].filter(([key]) => Boolean(e[key])).map(([key, max]) => ({ key, entity: e[key], max }));
    } catch (_err) {
      this._resolvedMetrics = [];
    }
    this._render();
  }

  getCardSize() { return 4; }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const labels = this._profile?.labels || {};
    const profileEntities = this._profile?.entities || {};
    const comparableCount = _fitnessNumber(
      profileEntities.last_workout_comparable_count
        ? this._hass.states[profileEntities.last_workout_comparable_count]?.state
        : null
    );
    const baselineKeys = new Set([
      "last_workout_efficiency_vs_baseline",
      "last_workout_decoupling_vs_baseline",
      "last_workout_hr_vs_baseline",
      "last_workout_power_vs_baseline",
      "last_workout_speed_vs_baseline",
      "last_workout_trimp_vs_recent",
    ]);
    const metrics = (this._resolvedMetrics || this.config.metrics || []).filter((metric) => {
      const key = String(metric.key || "");
      return !baselineKeys.has(key) || (comparableCount != null && comparableCount >= 3);
    });
    const rows = metrics.map((metric) => {
      const state = this._hass.states[metric.entity];
      if (!state || state.state === "unknown" || state.state === "unavailable") return "";
      const value = Number(state.state);
      if (!Number.isFinite(value)) return "";
      const max = Number(metric.max || 30);
      const pct = Math.min(50, Math.abs(value) / max * 50);
      const left = value < 0 ? 50 - pct : 50;
      const marker = Math.max(0, Math.min(100, 50 + (value / Math.max(max, 0.001)) * 50));
      const unit = state.attributes.unit_of_measurement || metric.unit || "";
      const decimals = metric.decimals ?? 1;
      const signed = (number) => `${number > 0 ? "+" : ""}${number.toFixed(decimals)}${unit ? ` ${this._escape(unit)}` : ""}`;
      const isHrBaseline = metric.key === "last_workout_hr_vs_baseline"
        || String(metric.entity).includes("hr_vs_baseline");
      const distance = Math.abs(value);
      const baselineTone = !isHrBaseline ? "var(--primary-color)"
        : distance <= 2 ? "#43a047"
        : distance <= 5 ? "#f9a825"
        : distance <= 8 ? "#ef6c00"
        : "#e53935";
      if (isHrBaseline) {
        let current = Number(state.attributes?.current_average_hr_bpm);
        if (!Number.isFinite(current)) {
          const currentId = this._profile?.entities?.last_workout_avg_hr;
          current = Number(currentId ? this._hass.states[currentId]?.state : NaN);
        }
        let baseline = Number(state.attributes?.personal_baseline_average_hr_bpm);
        if (!Number.isFinite(baseline) && Number.isFinite(current)) {
          baseline = current - value;
        }
        if (Number.isFinite(baseline) && Number.isFinite(current)) {
          const absolute = (number) => `${number.toFixed(decimals)}${unit ? ` ${this._escape(unit)}` : ""}`;
          const currentMarker = Math.max(
            0, Math.min(100, 50 + ((current - baseline) / Math.max(max, 0.001)) * 50)
          );
          return `<div class="row hr-baseline entity-link" style="--baseline-tone:${baselineTone}" data-more-info="${this._escape(metric.entity)}">
            <div class="line"><span>${this._escape(metric.name || entityName(this._hass, metric.entity))}</span><strong class="delta">Δ ${signed(value)}</strong></div>
            <div class="baseline-readout three">
              <span>${this._escape(labels.baseline)} <b>${absolute(baseline)}</b></span>
              <span>${this._escape(labels.current)} <b class="hot">${absolute(current)}</b></span>
              <span>${this._escape(labels.difference)} <b class="hot">${signed(value)}</b></span>
            </div>
            <div class="axis heat-axis">
              <i class="baseline-marker"></i>
              <em class="baseline-number">${absolute(baseline)}</em>
              <i class="current-marker" style="left:${currentMarker}%"></i>
            </div>
            <div class="axis-values"><span>${absolute(baseline-max)}</span><b>${_fitnessEscape(labels.baseline)}: ${absolute(baseline)}</b><span>${absolute(baseline+max)}</span></div>
          </div>`;
        }
      }
      return `<div class="row entity-link" style="--baseline-tone:${baselineTone}" data-more-info="${this._escape(metric.entity)}"><div class="line"><span>${this._escape(metric.name || entityName(this._hass, metric.entity))}</span><strong>${signed(value)}</strong></div><div class="axis"><div class="zero"></div><div class="bar" style="left:${left}%;width:${pct}%"></div><i class="current-marker" style="left:${marker}%"></i></div><div class="axis-values"><span>${signed(-max)}</span><b>${signed(value)}</b><span>${signed(max)}</span></div></div>`;
    }).filter(Boolean).join("");
    const title = this.config.title || labels.workout_comparison;
    if (!rows) {
      this.shadowRoot.innerHTML = "";
      return;
    }
    this.shadowRoot.innerHTML = `<ha-card><div class="title">${this._escape(title)}</div><div class="rows">${rows}</div></ha-card><style>.title{font-size:18px;font-weight:600;padding:16px 16px 8px}.rows{padding:0 16px 16px}.row{margin:12px 0}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.line{display:flex;justify-content:space-between;gap:16px;font-size:13px}.line span{color:var(--secondary-text-color)}.baseline-readout{display:flex;justify-content:space-between;gap:10px;margin-top:5px;font-size:10px;color:var(--secondary-text-color)}.baseline-readout.three{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.baseline-readout.three span{padding:6px 7px;border-radius:9px;background:var(--secondary-background-color)}.baseline-readout.three b{display:block;margin-top:2px}.baseline-readout b{color:var(--primary-text-color)}.baseline-readout b.hot,.line .delta{color:var(--baseline-tone)}.axis{height:8px;position:relative;background:var(--secondary-background-color);border-radius:5px;margin-top:6px;overflow:visible}.heat-axis{height:10px;background:linear-gradient(90deg,#e53935 0%,#ef6c00 18%,#f9a825 34%,#43a047 44%,#43a047 56%,#f9a825 66%,#ef6c00 82%,#e53935 100%)}.zero,.baseline-marker{position:absolute;left:50%;top:-2px;bottom:-2px;width:2px;background:var(--primary-text-color);transform:translateX(-1px)}.baseline-number{position:absolute;left:50%;top:-20px;transform:translateX(-50%);font-size:9px;font-style:normal;font-weight:700;color:var(--primary-text-color);background:var(--card-background-color);padding:1px 4px;border-radius:6px;white-space:nowrap}.bar{position:absolute;top:0;bottom:0;background:var(--baseline-tone);border-radius:5px}.current-marker{position:absolute;top:-3px;width:3px;height:16px;border-radius:2px;background:var(--baseline-tone);box-shadow:0 0 0 1px var(--card-background-color);transform:translateX(-1px)}.axis-values{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;margin-top:4px;font-size:9px;color:var(--secondary-text-color)}.axis-values span:last-child{text-align:right}.axis-values b{padding:1px 5px;border-radius:999px;color:var(--baseline-tone);background:var(--secondary-background-color);font-weight:650}</style>`;
  }

  _escape(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }
}

class FitnessSleepStageCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    _fitnessBindMoreInfo(this);
  }

  static getConfigElement() { return document.createElement("fitness-sleep-stage-card-editor"); }
  static getStubConfig() { return {}; }

  set hass(hass) {
    this._hass = hass;
    if (!this._profile && !this._resolving) this._resolveEntities();
    else this._render();
  }

  async _resolveEntities() {
    if (!this._hass || !this.config) return;
    if (Array.isArray(this.config.entities) && this.config.entities.length) {
      this._resolvedEntities = this.config.entities;
      this._render();
      return;
    }
    this._resolving = true;
    try {
      const data = await this._hass.callWS({ type: "fitness/dashboard/config" });
      const profiles = data?.profiles || [];
      this._profile = profiles.find((item) => item.entry_id === this.config.profile_entry_id) || (profiles.length === 1 ? profiles[0] : null);
      this._resolvedEntities = [];
    } catch (_err) {
      this._profile = null;
      this._resolvedEntities = [];
    } finally {
      this._resolving = false;
      this._render();
    }
  }

  getCardSize() { return 4; }

  _formatMinutes(value, unit = "min") {
    const number = Number(value);
    const normalized = String(unit || "").toLowerCase();
    if (!Number.isFinite(number)) return "—";
    if (!["min", "minute", "minutes"].includes(normalized) || number < 60) {
      return `${number.toFixed(0)}${unit ? ` ${this._escape(unit)}` : ""}`;
    }
    const total = Math.round(number);
    const hours = Math.floor(total / 60);
    const minutes = total % 60;
    return `${hours} h${minutes ? ` ${minutes} min` : ""}`;
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const labels = this._profile?.labels || {};
    const sleepPalette = ["#42a5f5", "#5c6bc0", "#ab47bc"];

    // Explicit manual entity config remains supported, but the automatic
    // Fitness dashboard uses upstream source routes and never mirrored Fitness
    // latest-sleep entities.
    let stageItems = [];
    let awakeRouteItem = null;
    let durationMinutes = null;
    let durationMetric = null;
    let scoreMetric = null;
    let hrvMetric = null;
    if (Array.isArray(this.config.entities) && this.config.entities.length) {
      const raw = this.config.entities.map((entity) => {
        const state = this._hass.states[entity];
        const value = _fitnessMinutesFromState(state);
        return value == null ? null : {entityId: entity, value, label: entityName(this._hass, entity)};
      }).filter(Boolean);
      awakeRouteItem = raw.find((item) => String(item.entityId).toLowerCase().includes("awake")) || null;
      stageItems = raw.filter((item) => item !== awakeRouteItem);
    } else {
      const routeItem = (key, fallbackLabel) => {
        const metric = _fitnessSleepSourceMetric(this._profile, this._hass, key);
        if (!metric || metric.canonicalValue == null || metric.canonicalValue < 0) return null;
        return {
          key,
          entityId: metric.moreInfoEntityId || metric.entityId,
          value: metric.canonicalValue,
          label: metric.route?.attribute ? fallbackLabel : (metric.entityId ? entityName(this._hass, metric.entityId) : fallbackLabel),
          metric,
        };
      };
      awakeRouteItem = routeItem("last_sleep_awake", labels.awake);
      stageItems = [
        routeItem("last_sleep_light", labels.light_sleep),
        routeItem("last_sleep_deep", labels.deep_sleep),
        routeItem("last_sleep_rem", labels.rem_sleep),
      ].filter(Boolean);
      durationMetric = _fitnessSleepSourceMetric(this._profile, this._hass, "last_sleep_duration");
      durationMinutes = durationMetric?.canonicalValue ?? null;
      scoreMetric = _fitnessSleepSourceMetric(this._profile, this._hass, "last_sleep_score");
      hrvMetric = _fitnessSleepSourceMetric(this._profile, this._hass, "last_sleep_hrv");
    }

    const rawValues = [awakeRouteItem, ...stageItems].filter(Boolean);
    const awakeItem = rawValues.find((item) => item === awakeRouteItem) || null;
    const asleepStageTotal = stageItems.reduce((sum, item) => sum + item.value, 0);
    const values = stageItems.map((item, index) => ({...item, unit: "min", color: sleepPalette[index % sleepPalette.length]}));
    const total = asleepStageTotal;
    if (!values.length || total <= 0) {
      this.shadowRoot.innerHTML = "";
      return;
    }
    const effectiveTotalMinutes = asleepStageTotal > 0 ? asleepStageTotal : (durationMinutes || 0);
    const displayTotal = this._formatMinutes(effectiveTotalMinutes, "min");
    const title = this.config.title || labels.latest_sleep;
    let cursor = 0;
    const stops = values.map((item) => {
      const start = cursor; cursor += item.value / total * 100;
      return `${item.color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
    }).join(",");
    const legend = values.map((item) => {
      const pct = item.value / total * 100;
      const unit = item.unit || "min";
      return `<div class="legend-row entity-link" data-more-info="${this._escape(item.entityId || "")}"><span class="dot" style="background:${item.color}"></span><span class="label">${this._escape(item.label)}</span><strong>${this._formatMinutes(item.value, unit)}</strong><span class="pct">${pct.toFixed(0)}%</span></div>`;
    }).join("");
    const awakeRow = awakeItem ? `<div class="awake-row entity-link" data-more-info="${this._escape(awakeItem.entityId || "")}"><ha-icon icon="mdi:eye-outline"></ha-icon><span>${this._escape(awakeItem.label)}</span><strong>${this._formatMinutes(awakeItem.value, "min")}</strong></div>` : "";
    const summary = this._profile?.sleep_source_metrics || {};
    const deficitId = this._profile?.entities?.sleep_deficit_7d || "";
    const deficitState = deficitId ? this._hass.states[deficitId] : null;
    const summaries = [];
    if (scoreMetric?.canonicalValue != null) {
      const label = scoreMetric.route?.source_type === "fitness_calculated" ? (labels.fitness_sleep_score) : (labels.sleep_score);
      summaries.push(`<div class="sleep-summary-metric entity-link" data-more-info="${this._escape(scoreMetric.moreInfoEntityId || "")}"><span>${this._escape(label)}</span><strong>${Math.max(0,Math.min(100,scoreMetric.canonicalValue)).toFixed(0)}%</strong></div>`);
    }
    if (hrvMetric?.canonicalValue != null) summaries.push(`<div class="sleep-summary-metric entity-link" data-more-info="${this._escape(hrvMetric.moreInfoEntityId || "")}"><span>${this._escape(labels.sleep_hrv)}</span><strong>${hrvMetric.canonicalValue.toFixed(1)} ms</strong></div>`);
    if (deficitState && !["unknown","unavailable"].includes(String(deficitState.state).toLowerCase())) summaries.push(`<div class="sleep-summary-metric entity-link" data-more-info="${this._escape(deficitId)}"><span>${this._escape(labels.sleep_deficit)}</span><strong>${this._escape(_fitnessSleepDuration(deficitState))}</strong></div>`);
    const summaryMetrics = summaries.join("");
    this.shadowRoot.innerHTML = `<ha-card><div class="title">${this._escape(title)}</div><div class="body"><div class="sleep-overview"><div class="donut entity-link" data-more-info="${this._escape(durationMetric?.moreInfoEntityId || this._profile?.data_entities?.recovery || "")}" style="background:conic-gradient(${stops})"><div class="hole"><strong>${displayTotal}</strong></div></div>${summaryMetrics ? `<div class="sleep-summary">${summaryMetrics}</div>` : ""}</div><div class="legend">${legend}</div>${awakeRow ? `<div class="awake-wrap">${awakeRow}</div>` : ""}</div></ha-card><style>.title{font-size:18px;font-weight:600;padding:16px 16px 6px}.body{display:flex;flex-direction:column;align-items:center;gap:14px;padding:10px 16px 18px;min-width:0}.sleep-overview{width:100%;display:grid;grid-template-columns:minmax(124px,auto) minmax(0,1fr);gap:14px;align-items:center}.donut{width:124px;height:124px;border-radius:50%;display:grid;place-items:center;justify-self:center}.hole{width:76px;height:76px;border-radius:50%;background:var(--ha-card-background,var(--card-background-color));display:flex;flex-direction:column;align-items:center;justify-content:center}.hole strong{font-size:18px;text-align:center;line-height:1.15;padding:4px}.legend{width:100%;min-width:0}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.legend-row{display:grid;grid-template-columns:10px minmax(0,1fr) minmax(72px,max-content) 38px;column-gap:10px;align-items:center;min-width:0;padding:7px 0;font-size:12px}.dot{width:9px;height:9px;border-radius:50%}.label{color:var(--secondary-text-color);min-width:0;white-space:normal;overflow-wrap:normal;word-break:normal;hyphens:auto}.legend-row strong{text-align:right;white-space:nowrap}.pct{text-align:right;white-space:nowrap;color:var(--secondary-text-color)}.awake-wrap{width:100%;padding-top:2px}.awake-row{display:grid;grid-template-columns:20px minmax(0,1fr) max-content;gap:8px;align-items:center;padding:8px 10px;border-radius:11px;background:var(--card-background-color);font-size:11px}.awake-row ha-icon{--mdc-icon-size:16px;color:var(--secondary-text-color)}.awake-row span{color:var(--secondary-text-color)}.sleep-summary{display:grid;grid-template-columns:1fr;gap:8px;min-width:0}.sleep-summary-metric{min-width:0;padding:10px 11px;border-radius:12px;background:var(--secondary-background-color)}.sleep-summary-metric span{display:block;font-size:9px;color:var(--secondary-text-color)}.sleep-summary-metric strong{display:block;margin-top:3px;font-size:14px} :host([fitness-motion]) .donut{animation:fitness-sleep-orbit 8.4s ease-in-out infinite;will-change:transform,filter}:host([fitness-motion]) .donut .hole{animation:fitness-sleep-counterfloat 8.4s ease-in-out infinite}@keyframes fitness-sleep-orbit{0%,100%{transform:rotate(-1.5deg) scale(1);filter:brightness(.98)}35%{transform:rotate(3deg) scale(1.025);filter:brightness(1.07)}68%{transform:rotate(-2deg) scale(.995);filter:brightness(1.02)}}@keyframes fitness-sleep-counterfloat{0%,100%{transform:translateY(1px)}50%{transform:translateY(-2px)}}@media(prefers-reduced-motion:reduce){:host([fitness-motion]) .donut,:host([fitness-motion]) .donut .hole{animation:none!important}}@media(max-width:430px){.sleep-overview{grid-template-columns:1fr}.sleep-summary{grid-template-columns:repeat(3,minmax(0,1fr));width:100%}.sleep-summary-metric{padding:8px}.sleep-summary-metric strong{font-size:12px}}</style>`;
  }

  _escape(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }
}

const _fitnessNumber = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};
const _fitnessUsableState = (hass, entityId) => {
  if (!entityId) return false;
  const state = hass?.states?.[entityId];
  if (!state) return false;
  const value = String(state.state ?? "").toLowerCase();
  return value !== "" && !["unknown", "unavailable", "none", "null"].includes(value);
};
const _fitnessAttr = (state, ...keys) => {
  for (const key of keys) {
    const value = state?.attributes?.[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return null;
};
const _fitnessEscape = (value) => String(value ?? "").replace(
  /[&<>"']/g,
  (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]),
);
const _fitnessFormatLabel = (value, replacements = {}) => String(value ?? "").replace(
  /\{([A-Za-z0-9_]+)\}/g,
  (match, key) => Object.prototype.hasOwnProperty.call(replacements, key)
    ? String(replacements[key])
    : match,
);
const _fitnessMusicAdapterHint = (labels, adapter = {}) => (
  labels?.[String(adapter.setup_hint_key || "")] || ""
);
const _fitnessMusicProviderName = (labels, provider = {}) => {
  const providerName = String(provider.provider_name || provider.name || provider.id || "");
  return provider.kind === "provider_source"
    ? _fitnessFormatLabel(labels?.music_provider_via_ma, {provider:providerName})
    : providerName;
};
const _fitnessMusicProviderDescription = (labels, provider = {}) => _fitnessFormatLabel(
  labels?.[String(provider.description_key || "")],
  {provider:String(provider.provider_name || provider.name || provider.id || "")},
);

const _fitnessOpenMoreInfo = (host, entityId) => {
  if (!host || !entityId || !host._hass?.states?.[entityId]) return;
  host.dispatchEvent(new CustomEvent("hass-more-info", {
    bubbles: true,
    composed: true,
    detail: { entityId },
  }));
};

const _fitnessBindMoreInfo = (host) => {
  if (!host?.shadowRoot || host._fitnessMoreInfoBound) return;
  host._fitnessMoreInfoBound = true;
  host.shadowRoot.addEventListener("click", (event) => {
    const node = event.composedPath().find((item) => item?.dataset?.moreInfo);
    if (!node) return;
    if (event.composedPath().some((item) => item?.tagName === "BUTTON")) return;
    _fitnessOpenMoreInfo(host, node.dataset.moreInfo);
  });
};

const _fitnessDisplay = (state, decimals = 1) => {
  if (!state || state.state === "unknown" || state.state === "unavailable") return "—";
  const n = Number(state.state);
  const unit = state.attributes?.unit_of_measurement || "";
  if (!Number.isFinite(n)) return _fitnessEscape(state.state);
  return `${n.toFixed(decimals)}${unit ? ` ${_fitnessEscape(unit)}` : ""}`;
};

const _fitnessWorkoutAttributeValue = (state, attribute) => {
  if (!state || !attribute) return null;
  const value = state.attributes?.[attribute];
  return value === undefined || value === null || value === "" ? null : value;
};

// Profile data-map sensors are the routing contract between HA-Fitness and the
// dashboard. Source-owned metrics remain entity/attribute pointers. Inline
// values are restricted to low-frequency facts with no authoritative scalar
// entity: Fitness substitute calculations, exact source reconstructions, or
// canonical source normalizations. The websocket snapshot remains only a
// startup/event-history fallback.
const _fitnessProfileDataRoutes = (profile, hass, kind, fallback = {}) => {
  const entityId = profile?.data_entities?.[kind] || "";
  const state = entityId ? hass?.states?.[entityId] : null;
  const attrs = state?.attributes || {};
  const keys = Array.isArray(attrs.mapped_keys) ? attrs.mapped_keys : [];
  if (!keys.length) return fallback || {};
  const routes = {};
  for (const rawKey of keys) {
    const key = String(rawKey);
    const route = {};
    const source = attrs[`${key}_source`];
    if (source) route.entity_id = source;
    for (const [suffix, field] of [
      ["attribute","attribute"], ["transform","transform"],
      ["unit","unit"], ["field","field"],
      ["source_type","source_type"], ["configured_value","configured_value"],
      ["method","method"], ["value","value"],
    ]) {
      const value = attrs[`${key}_${suffix}`];
      if (value !== undefined && value !== null) route[field] = value;
    }
    if (route.transform === "configured" && route.configured_value !== undefined) {
      route.value = route.configured_value;
    }
    // Recorder/event carriers can own a field without exposing it directly as
    // state/attribute. Only that route type may borrow the websocket's canonical
    // display fallback. Direct and inline map routes are fully authoritative.
    if (route.transform === "fallback" && route.value === undefined) {
      const bootstrap = fallback?.[key];
      if (bootstrap?.value !== undefined) route.value = bootstrap.value;
    }
    routes[key] = route;
  }
  return routes;
};

const _fitnessProfileDataEntities = (profile, hass, kind) => {
  const routes = _fitnessProfileDataRoutes(profile, hass, kind, {});
  const entities = {};
  for (const [key, route] of Object.entries(routes)) {
    if (route?.entity_id) entities[key] = route.entity_id;
  }
  return entities;
};

const _fitnessKmhFromState = (state) => {
  if (!state || ["unknown", "unavailable"].includes(String(state.state).toLowerCase())) return null;
  const value = Number(state.state);
  if (!Number.isFinite(value)) return null;
  const unit = String(state.attributes?.unit_of_measurement || "").toLowerCase().replace(/\s/g, "");
  if (["km/h", "kmh", "kph"].includes(unit)) return value;
  if (["m/s", "mps", "m·s⁻¹"].includes(unit)) return value * 3.6;
  if (["mph", "mi/h"].includes(unit)) return value * 1.609344;
  return null;
};

const _fitnessWorkoutSourceMetric = (profile, hass, key, decimals = 1) => {
  const route = _fitnessProfileDataRoutes(
    profile, hass, "workout", profile?.workout_source_metrics || {}
  )?.[key];
  if (!route) return null;
  const entityId = route.entity_id || "";
  const state = entityId ? hass?.states?.[entityId] : null;
  const field = route.field || "";
  let value = route.value;
  let canonicalValue = Number(route.value);
  if (!Number.isFinite(canonicalValue)) canonicalValue = null;
  let unit = route.unit || "";
  let direct = false;

  if (["state","wh_to_kj"].includes(route.transform) && state && !["unknown","unavailable","none","null",""] .includes(String(state.state ?? "").toLowerCase())) {
    value = state.state;
    unit = state.attributes?.unit_of_measurement || route.unit || "";
    direct = true;
    if (route.transform === "wh_to_kj") {
      const n = Number(state.state);
      canonicalValue = Number.isFinite(n) ? n * 3.6 : null;
      value = canonicalValue;
      unit = route.unit || "kJ";
    } else if (["duration_s","moving_time_s","elapsed_time_s"].includes(field)) canonicalValue = _fitnessMinutesFromState(state);
    else if (field === "distance_m") canonicalValue = _fitnessKmFromState(state);
    else if (["average_speed_m_s","max_speed_m_s"].includes(field)) canonicalValue = _fitnessKmhFromState(state);
    else {
      const n = Number(state.state);
      canonicalValue = Number.isFinite(n) ? n : null;
    }
  } else if (route.attribute && state) {
    const raw = _fitnessWorkoutAttributeValue(state, route.attribute);
    if (raw !== null) {
      value = raw;
      direct = true;
      const n = Number(raw);
      if (Number.isFinite(n)) {
        canonicalValue = route.transform === "seconds_to_minutes" ? n / 60
          : route.transform === "meters_to_km" ? n / 1000
          : route.transform === "mps_to_kmh" ? n * 3.6
          : route.transform === "rpe_0_100_to_1_10" && n > 10 ? n / 10
          : n;
        value = canonicalValue;
        unit = route.unit || "";
      }
    }
  }

  const numeric = Number(value);
  const display = Number.isFinite(numeric)
    ? `${numeric.toFixed(decimals)}${unit ? ` ${unit}` : ""}`
    : String(value ?? "");
  const moreInfoEntityId = entityId || profile?.data_entities?.workout || "";
  return {route, entityId, moreInfoEntityId, state, value, canonicalValue, unit, display, direct};
};

const _FITNESS_WORKOUT_METRIC_LABEL_KEYS = Object.freeze({
  last_workout:"workout",
  last_workout_duration:"metric_duration", last_workout_moving_time:"metric_moving_time",
  last_workout_elapsed_time:"metric_elapsed_time", last_workout_distance:"metric_distance",
  last_workout_average_speed:"metric_speed", last_workout_avg_hr:"metric_avg_hr",
  last_workout_max_hr:"metric_max_hr", last_workout_avg_power:"metric_avg_power",
  last_workout_max_power:"metric_max_power", last_workout_weighted_power:"metric_weighted_power",
  last_workout_avg_cadence:"metric_avg_cadence", last_workout_max_cadence:"metric_max_cadence",
  last_workout_elevation_gain:"metric_elevation_gain", last_workout_elevation_loss:"metric_elevation_loss",
  last_workout_calories:"metric_calories", last_workout_training_load:"metric_training_load",
  last_workout_vo2max:"metric_vo2max", last_workout_total_reps:"metric_total_reps",
  last_workout_exercise_count:"metric_exercises", last_workout_volume:"metric_volume",
  last_workout_rpe:"metric_rpe", session_rpe:"metric_rpe", last_workout_banister_trimp:"metric_trimp",
  last_workout_session_rpe_load:"metric_session_load", last_workout_fitness_aerobic_load:"metric_aerobic_load",
  last_workout_fitness_high_intensity_load:"metric_high_intensity_load",
  last_workout_strength_sets:"metric_strength_sets", last_workout_estimated_1rm:"metric_estimated_1rm",
  last_workout_strength_progression:"metric_strength_progression", last_workout_hrr_60s:"metric_hrr_60s",
  last_workout_aerobic_efficiency:"metric_aerobic_efficiency",
  last_workout_aerobic_decoupling:"metric_aerobic_decoupling",
});

const _FITNESS_WORKOUT_METRIC_ICONS = Object.freeze({
  last_workout_duration:"mdi:timer-outline", last_workout_moving_time:"mdi:motion-play-outline",
  last_workout_elapsed_time:"mdi:clock-outline", last_workout_distance:"mdi:map-marker-distance",
  last_workout_average_speed:"mdi:speedometer", last_workout_avg_hr:"mdi:heart-pulse",
  last_workout_max_hr:"mdi:heart-flash", last_workout_avg_power:"mdi:lightning-bolt-outline",
  last_workout_max_power:"mdi:lightning-bolt", last_workout_weighted_power:"mdi:flash-triangle-outline",
  last_workout_avg_cadence:"mdi:rotate-right", last_workout_max_cadence:"mdi:sync-circle",
  last_workout_elevation_gain:"mdi:elevation-rise", last_workout_elevation_loss:"mdi:elevation-decline",
  last_workout_calories:"mdi:fire", last_workout_training_load:"mdi:chart-bell-curve-cumulative",
  last_workout_vo2max:"mdi:lungs", last_workout_total_reps:"mdi:counter",
  last_workout_exercise_count:"mdi:dumbbell", last_workout_volume:"mdi:weight-kilogram",
  last_workout_rpe:"mdi:gauge", session_rpe:"mdi:gauge", last_workout_banister_trimp:"mdi:heart-cog-outline",
  last_workout_session_rpe_load:"mdi:chart-bell-curve-cumulative",
  last_workout_fitness_aerobic_load:"mdi:run-fast", last_workout_fitness_high_intensity_load:"mdi:fire-circle",
  last_workout_strength_sets:"mdi:dumbbell", last_workout_estimated_1rm:"mdi:weight-lifter",
  last_workout_strength_progression:"mdi:trending-up", last_workout_hrr_60s:"mdi:heart-clock",
  last_workout_aerobic_efficiency:"mdi:chart-line", last_workout_aerobic_decoupling:"mdi:chart-timeline-variant-shimmer",
});

const _FITNESS_WORKOUT_METRIC_DECIMALS = Object.freeze({
  last_workout_duration:1, last_workout_moving_time:1, last_workout_elapsed_time:1,
  last_workout_distance:2, last_workout_average_speed:1, last_workout_avg_hr:0, last_workout_max_hr:0,
  last_workout_avg_power:0, last_workout_max_power:0, last_workout_weighted_power:0,
  last_workout_avg_cadence:0, last_workout_max_cadence:0, last_workout_elevation_gain:0,
  last_workout_elevation_loss:0, last_workout_calories:0, last_workout_vo2max:1,
  last_workout_total_reps:0, last_workout_exercise_count:0, last_workout_volume:0,
});

const _fitnessWorkoutSemanticLabel = (profile, key, fallback = "") => {
  const labelKey = _FITNESS_WORKOUT_METRIC_LABEL_KEYS[key];
  const translated = labelKey ? profile?.labels?.[labelKey] : "";
  return translated || fallback || key.replace(/^last_workout_?/, "").replaceAll("_", " ").replace(/\b\w/g, (ch) => ch.toUpperCase());
};

const _fitnessWorkoutMetricIcon = (key) => _FITNESS_WORKOUT_METRIC_ICONS[key] || "mdi:chart-box-outline";
const _fitnessWorkoutMetricDecimals = (key) => _FITNESS_WORKOUT_METRIC_DECIMALS[key] ?? 1;

const _fitnessWorkoutSourceLabel = (profile, hass, key, metric) => {
  if (!metric) return "";
  const semantic = _fitnessWorkoutSemanticLabel(profile, key);
  if (semantic) return semantic;
  const attribute = String(metric.route?.attribute || "");
  if (attribute) {
    return attribute
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .replaceAll("_", " ")
      .replace(/\b\w/g, (ch) => ch.toUpperCase());
  }
  if (metric.entityId && !["inline","fallback"].includes(metric.route?.transform)) return entityName(hass, metric.entityId);
  return profile?.labels?.workout;
};

const _fitnessWorkoutMetricTile = (profile, key, label, value, entityId) => `
  <div class="hi entity-link" data-more-info="${_fitnessEscape(entityId || "")}">
    <div class="hi-head">
      <span class="hi-icon"><ha-icon icon="${_fitnessEscape(_fitnessWorkoutMetricIcon(key))}"></ha-icon></span>
      <span class="hi-label">${_fitnessEscape(label)}</span>
    </div>
    <strong class="hi-value">${_fitnessEscape(value)}</strong>
  </div>`;

const _fitnessWorkoutSourceSignature = (profile, hass) => Object.entries(
  _fitnessProfileDataRoutes(profile, hass, "workout", profile?.workout_source_metrics || {})
).map(([key, route]) => {
  const state = route?.entity_id ? hass?.states?.[route.entity_id] : null;
  let attr = "";
  if (route?.attribute && state) {
    try { attr = JSON.stringify(state.attributes?.[route.attribute]); } catch (_err) { attr = String(state.attributes?.[route.attribute] ?? ""); }
  }
  return `source:${key}:${route?.entity_id || ""}:${state?.state || ""}:${state?.last_updated || ""}:${attr}:${route?.value ?? ""}`;
}).join("|");

const _fitnessSourceMetric = (route, hass, decimals = 1, kind = "generic") => {
  if (!route) return null;
  const entityId = route.entity_id || "";
  const state = entityId ? hass?.states?.[entityId] : null;
  let value = route.value;
  let canonicalValue = Number(route.value);
  if (!Number.isFinite(canonicalValue)) canonicalValue = null;
  let unit = route.unit || "";
  let direct = false;
  if (route.transform === "state" && state && !["unknown","unavailable","none","null",""] .includes(String(state.state ?? "").toLowerCase())) {
    value = state.state;
    unit = state.attributes?.unit_of_measurement || route.unit || "";
    direct = true;
    if (kind === "sleep_duration") canonicalValue = _fitnessMinutesFromState(state);
    else {
      const n = Number(state.state);
      canonicalValue = Number.isFinite(n) ? n : null;
    }
  } else if (route.attribute && state) {
    const raw = state.attributes?.[route.attribute];
    if (raw !== undefined && raw !== null && raw !== "") {
      value = raw;
      direct = true;
      const n = Number(raw);
      if (Number.isFinite(n)) {
        canonicalValue = route.transform === "seconds_to_minutes" ? n / 60
          : route.transform === "hours_to_minutes" ? n * 60
          : n;
        value = canonicalValue;
        unit = route.unit || "";
      } else {
        canonicalValue = null;
      }
    }
  }
  const numeric = Number(value);
  const display = Number.isFinite(numeric)
    ? `${numeric.toFixed(decimals)}${unit ? ` ${unit}` : ""}`
    : String(value ?? "");
  return {route, entityId, state, value, canonicalValue, unit, display, direct};
};

const _fitnessSleepSourceMetric = (profile, hass, key, decimals = 1) => {
  const route = _fitnessProfileDataRoutes(
    profile, hass, "recovery", profile?.sleep_source_metrics || {}
  )?.[key];
  const durationFields = new Set([
    "duration_s","time_in_bed_s","awake_s","light_sleep_s","deep_sleep_s","rem_sleep_s",
  ]);
  const metric = _fitnessSourceMetric(route, hass, decimals, durationFields.has(route?.field) ? "sleep_duration" : "generic");
  return metric ? {...metric, moreInfoEntityId: metric.entityId || profile?.data_entities?.recovery || ""} : null;
};

const _fitnessEvaluationSourceMetric = (profile, hass, key, decimals = 1) => {
  const metric = _fitnessSourceMetric(
    _fitnessProfileDataRoutes(
      profile, hass, "evaluation", profile?.evaluation_source_metrics || {}
    )?.[key],
    hass, decimals, "generic"
  );
  return metric ? {...metric, moreInfoEntityId: metric.entityId || profile?.data_entities?.evaluation || ""} : null;
};

const _fitnessSourceMetricSignature = (routes, hass, prefix) => Object.entries(routes || {}).map(([key, route]) => {
  const state = route?.entity_id ? hass?.states?.[route.entity_id] : null;
  let attr = "";
  if (route?.attribute && state) {
    try { attr = JSON.stringify(state.attributes?.[route.attribute]); } catch (_err) { attr = String(state.attributes?.[route.attribute] ?? ""); }
  }
  return `${prefix}:${key}:${route?.entity_id || ""}:${state?.state || ""}:${state?.last_updated || ""}:${attr}:${route?.value ?? ""}`;
}).join("|");


const _fitnessSleepDuration = (state) => {
  if (!state || state.state === "unknown" || state.state === "unavailable") return "—";
  const value = Number(state.state);
  const unit = String(state.attributes?.unit_of_measurement || "").toLowerCase();
  if (!Number.isFinite(value)) return _fitnessEscape(state.state);
  const isMinutes = unit === "min" || unit === "minute" || unit === "minutes";
  if (!isMinutes || value < 60) return `${value.toFixed(0)}${unit ? ` ${_fitnessEscape(state.attributes?.unit_of_measurement)}` : ""}`;
  const totalMinutes = Math.round(value);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours} h${minutes ? ` ${minutes} min` : ""}`;
};

const _fitnessPaceFromSpeed = (state) => {
  if (!state || ["unknown", "unavailable"].includes(state.state)) return null;
  let speed = Number(state.state);
  if (!Number.isFinite(speed) || speed <= 0) return null;
  const unit = String(state.attributes?.unit_of_measurement || "").toLowerCase().replace(/\s/g, "");
  if (["m/s", "mps", "m·s⁻¹"].includes(unit)) speed *= 3.6;
  else if (["mph", "mi/h"].includes(unit)) speed *= 1.609344;
  else if (!["km/h", "kmh", "kph"].includes(unit)) return null;
  const paceMinutes = 60 / speed;
  const mins = Math.floor(paceMinutes);
  let secs = Math.round((paceMinutes - mins) * 60);
  let outMins = mins;
  if (secs === 60) { outMins += 1; secs = 0; }
  return `${outMins}:${String(secs).padStart(2, "0")} min/km`;
};

const _fitnessMinutesFromState = (state) => {
  if (!state || ["unknown", "unavailable"].includes(state.state)) return null;
  const value = Number(state.state);
  if (!Number.isFinite(value) || value <= 0) return null;
  const unit = String(state.attributes?.unit_of_measurement || "").toLowerCase();
  if (["min", "minute", "minutes"].includes(unit)) return value;
  if (["s", "sec", "second", "seconds"].includes(unit)) return value / 60;
  if (["h", "hr", "hour", "hours"].includes(unit)) return value * 60;
  return null;
};

const _fitnessKmFromState = (state) => {
  if (!state || ["unknown", "unavailable"].includes(state.state)) return null;
  const value = Number(state.state);
  if (!Number.isFinite(value) || value <= 0) return null;
  const unit = String(state.attributes?.unit_of_measurement || "").toLowerCase();
  if (["km", "kilometer", "kilometers"].includes(unit)) return value;
  if (["m", "meter", "meters"].includes(unit)) return value / 1000;
  if (["mi", "mile", "miles"].includes(unit)) return value * 1.609344;
  return null;
};

const _fitnessSymmetricHeatTone = (delta, green = 3, yellow = 7, orange = 12) => {
  const distance = Math.abs(Number(delta));
  if (!Number.isFinite(distance)) return "#78909c";
  if (distance <= green) return "#2e7d32";
  if (distance <= yellow) return "#f9a825";
  if (distance <= orange) return "#ef6c00";
  return "#c62828";
};

const _fitnessVo2Tone = (percentPredicted) => {
  const value = Number(percentPredicted);
  if (!Number.isFinite(value)) return "var(--primary-color)";
  if (value >= 100) return "#2e7d32";
  if (value >= 90) return "#7cb342";
  if (value >= 80) return "#f9a825";
  if (value >= 70) return "#ef6c00";
  return "#c62828";
};

const _fitnessWorkoutPriority = (sport, key) => {
  const normalized = String(sport || "").toLowerCase();
  const isStrength = /(strength|weight|resistance|functional|traditional)/.test(normalized);
  const isRunning = /(run|running|jog)/.test(normalized);
  const isCycling = /(cycl|bike|biking)/.test(normalized);
  const isWalkHike = /(walk|hik|trek)/.test(normalized);
  const common = {
    last_workout_duration: 10, last_workout_avg_hr: 30, last_workout_max_hr: 55,
    last_workout_calories: 65, last_workout_banister_trimp: 70,
    session_rpe: 72, last_workout_session_rpe_load: 74,
  };
  const profiles = isStrength ? {
    last_workout_exercise_count: 12, last_workout_total_reps: 14, last_workout_volume: 16,
    last_workout_strength_sets: 18, last_workout_estimated_1rm: 20,
    last_workout_strength_progression: 22, last_workout_avg_hr: 38, last_workout_calories: 44,
    last_workout_distance: 999, last_workout_average_speed: 999, last_workout_avg_cadence: 999,
    last_workout_elevation_gain: 999, last_workout_vo2max: 999,
  } : isRunning ? {
    last_workout_distance: 11, last_workout_average_speed: 12, last_workout_avg_hr: 20,
    last_workout_avg_cadence: 22, last_workout_avg_power: 25, last_workout_max_hr: 30,
    last_workout_elevation_gain: 35, last_workout_calories: 45, last_workout_vo2max: 50,
  } : isCycling ? {
    last_workout_distance: 11, last_workout_average_speed: 12, last_workout_avg_power: 18,
    last_workout_avg_cadence: 20, last_workout_avg_hr: 24, last_workout_max_power: 28,
    last_workout_elevation_gain: 32, last_workout_calories: 42,
  } : isWalkHike ? {
    last_workout_distance: 11, last_workout_average_speed: 14, last_workout_avg_hr: 22,
    last_workout_elevation_gain: 25, last_workout_calories: 35,
  } : {
    last_workout_distance: 18, last_workout_average_speed: 24, last_workout_avg_hr: 20,
    last_workout_avg_power: 30, last_workout_avg_cadence: 32, last_workout_calories: 40,
  };
  return profiles[key] ?? common[key] ?? 80;
};

const _fitnessFormatPace = (minutesPerKm) => {
  if (!Number.isFinite(minutesPerKm) || minutesPerKm <= 0 || minutesPerKm > 60) return null;
  let mins = Math.floor(minutesPerKm);
  let secs = Math.round((minutesPerKm - mins) * 60);
  if (secs === 60) { mins += 1; secs = 0; }
  return `${mins}:${String(secs).padStart(2, "0")} min/km`;
};

const _fitnessRunPace = (profile, hass) => {
  if (profile?.latest_workout?.sport !== "running") return null;
  const speed = _fitnessWorkoutSourceMetric(profile, hass, "last_workout_average_speed");
  if (speed?.canonicalValue && speed.canonicalValue > 0) {
    return _fitnessFormatPace(60 / speed.canonicalValue);
  }
  const distance = _fitnessWorkoutSourceMetric(profile, hass, "last_workout_distance");
  const moving = _fitnessWorkoutSourceMetric(profile, hass, "last_workout_moving_time");
  const duration = _fitnessWorkoutSourceMetric(profile, hass, "last_workout_duration");
  const distanceKm = distance?.canonicalValue;
  const timeMinutes = moving?.canonicalValue ?? duration?.canonicalValue;
  return distanceKm && timeMinutes
    ? _fitnessFormatPace(timeMinutes / distanceKm)
    : null;
};


class FitnessAutoProfileCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    if (!this.shadowRoot) this.attachShadow({mode:"open"});
    this.hidden = true;
    if (!this._fitnessContentObserver && globalThis.MutationObserver) {
      this._fitnessContentObserver = new MutationObserver(() => this._syncInformationVisibility());
      this._fitnessContentObserver.observe(this.shadowRoot, {childList:true,subtree:true});
    }
    _fitnessBindMoreInfo(this);
    this._resolvedKey = null;
  }
  static getConfigElement() { return document.createElement("fitness-profile-card-editor"); }
  static getStubConfig() { return {}; }

  set hass(hass) {
    this._hass = hass;
    const key = this.config?.profile_entry_id || "";
    if (key !== this._resolvedKey && !this._resolving) {
      this._resolvedKey = key;
      this._resolveProfile();
      return;
    }
    this._render();
  }

  async _resolveProfile() {
    if (!this._hass) return;
    this._resolving = true;
    try {
      const data = await this._hass.callWS({type:"fitness/dashboard/config"});
      const profiles = data?.profiles || [];
      this._profile = profiles.find((p) => p.entry_id === this.config?.profile_entry_id)
        || (profiles.length === 1 ? profiles[0] : null);
      if (this._profile?.labels_by_language) {
        const ui = String(this._profile?.language || this._hass?.language || "en").toLowerCase().split("-")[0];
        this._profile = {...this._profile, labels: this._profile.labels_by_language[ui] || this._profile.labels_by_language.en || this._profile.labels};
      }
    } catch (_err) {
      this._profile = null;
    } finally {
      this._resolving = false;
      this._render();
    }
  }

  _syncInformationVisibility() {
    const hasInformation = Boolean(this.shadowRoot?.querySelector("ha-card"));
    this.toggleAttribute("fitness-has-information", hasInformation);
    this.hidden = !hasInformation;
    const slot = this.closest?.(".tv-card-slot");
    if (slot) slot.hidden = !hasInformation;
  }

  getCardSize() { return 4; }
  getGridOptions() { return {columns: 12, min_columns: 6}; }
}


class FitnessTodayCard extends FitnessAutoProfileCard {
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const e = this._profile?.entities || {};
    const l = this._profile?.labels || {};
    const itemsList = [];
    for (const id of [e.session_status, e.training_load].filter(Boolean)) {
      const state = this._hass.states[id];
      if (state && !["unknown","unavailable"].includes(state.state)) itemsList.push(`<div class="today-item entity-link" data-more-info="${_fitnessEscape(id)}"><span>${_fitnessEscape(entityName(this._hass,id))}</span><strong>${_fitnessDisplay(state,1)}</strong></div>`);
    }
    for (const [key,label,decimals] of [["last_sleep_score",l.sleep_score,0],["last_sleep_duration",l.latest_sleep,0],["last_sleep_hrv",l.sleep_hrv,1]]) {
      const metric = _fitnessSleepSourceMetric(this._profile,this._hass,key,decimals);
      if (metric?.canonicalValue == null) continue;
      const value = key === "last_sleep_duration" ? _fitnessSleepDuration({state:String(metric.canonicalValue),attributes:{unit_of_measurement:"min"}}) : `${metric.canonicalValue.toFixed(decimals)}${metric.route?.unit ? ` ${metric.route.unit}` : ""}`;
      itemsList.push(`<div class="today-item entity-link" data-more-info="${_fitnessEscape(metric.moreInfoEntityId||"")}"><span>${_fitnessEscape(label)}</span><strong>${_fitnessEscape(value)}</strong></div>`);
    }
    const vo2 = _fitnessEvaluationSourceMetric(this._profile,this._hass,"vo2max",1);
    if (vo2?.canonicalValue != null) itemsList.push(`<div class="today-item entity-link" data-more-info="${_fitnessEscape(vo2.moreInfoEntityId||"")}"><span>${_fitnessEscape(l.current_vo2max)}</span><strong>${vo2.canonicalValue.toFixed(1)} mL/kg/min</strong></div>`);
    const items = itemsList.join("");
    if (!items) { this.shadowRoot.innerHTML = ""; return; }
    this.shadowRoot.innerHTML = `<ha-card><div class="today-head"><div><strong>${_fitnessEscape(this.config.title || l.overview)}</strong><span>${_fitnessEscape(this._profile?.profile_name || "")}</span></div><ha-icon icon="mdi:heart-pulse"></ha-icon></div><div class="today-grid">${items}</div></ha-card><style>
      ha-card{padding:18px}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.today-head{display:flex;justify-content:space-between;align-items:center}.today-head strong{font-size:20px}.today-head span{display:block;color:var(--secondary-text-color);font-size:12px;margin-top:3px}.today-head ha-icon{color:var(--primary-color);--mdc-icon-size:30px}.today-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:16px}.today-item{padding:11px 12px;border-radius:13px;background:var(--secondary-background-color)}.today-item span{display:block;font-size:10px;color:var(--secondary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.today-item strong{display:block;margin-top:4px;font-size:15px}@media(max-width:420px){.today-grid{grid-template-columns:1fr}}</style>`;
  }
}

class FitnessWorkoutHighlightsCard extends FitnessAutoProfileCard {
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const e = this._profile?.entities || {};
    const l = this._profile?.labels || {};
    const sport = this._profile?.latest_workout?.sport || "";
    const running = String(sport).toLowerCase() === "running" || /run|jog/.test(String(sport).toLowerCase());
    const zeroIsMissing = new Set([
      "last_workout_distance","last_workout_average_speed","last_workout_avg_power",
      "last_workout_avg_cadence","last_workout_elevation_gain","last_workout_calories",
      "last_workout_total_reps","last_workout_exercise_count","last_workout_volume",
      "last_workout_strength_sets","last_workout_estimated_1rm"
    ]);
    const sourceKeys = [
      "last_workout_duration","last_workout_distance","last_workout_average_speed",
      "last_workout_avg_hr","last_workout_max_hr","last_workout_avg_power","last_workout_max_power",
      "last_workout_avg_cadence","last_workout_elevation_gain","last_workout_calories","last_workout_vo2max",
      "last_workout_total_reps","last_workout_exercise_count","last_workout_volume"
    ];
    const fitnessKeys = [
      "last_workout_banister_trimp","last_workout_session_rpe_load",
      "last_workout_fitness_aerobic_load","last_workout_fitness_high_intensity_load",
      "last_workout_strength_sets","last_workout_estimated_1rm","last_workout_strength_progression"
    ];
    const runPace = running ? _fitnessRunPace(this._profile, this._hass) : null;
    const workoutMetric = _fitnessWorkoutSourceMetric(this._profile, this._hass, "last_workout", 0);
    const workoutName = workoutMetric?.value || this._profile?.latest_workout?.name || null;

    const candidates = [];
    for (const key of sourceKeys) {
      const metric = _fitnessWorkoutSourceMetric(this._profile, this._hass, key, _fitnessWorkoutMetricDecimals(key));
      if (!metric || metric.value === null || metric.value === undefined || metric.value === "") continue;
      const numeric = Number(metric.canonicalValue ?? metric.value);
      if (zeroIsMissing.has(key) && Number.isFinite(numeric) && Math.abs(numeric) < 1e-12) continue;
      const label = _fitnessWorkoutSourceLabel(this._profile, this._hass, key, metric);
      const lowerLabel = String(label || "").toLowerCase();
      if (/(sleep|awake|time in bed|bedtime|rem sleep|deep sleep|light sleep|sleep hrv|sleep score)/.test(lowerLabel)) continue;
      let display = metric.display;
      let displayLabel = label;
      if (running && key === "last_workout_average_speed") {
        if (!runPace) continue;
        display = runPace;
        displayLabel = l.pace;
      }
      candidates.push({
        key, priority: _fitnessWorkoutPriority(sport, key),
        html: _fitnessWorkoutMetricTile(this._profile, key, displayLabel, display, metric.moreInfoEntityId),
      });
    }

    const rpeId = e.session_rpe;
    const rpeState = rpeId ? this._hass.states[rpeId] : null;
    if (rpeState && !["unknown","unavailable"].includes(String(rpeState.state).toLowerCase())) {
      const rpeLabel = _fitnessWorkoutSemanticLabel(this._profile, "session_rpe", entityName(this._hass, rpeId));
      candidates.push({key:"session_rpe", priority:_fitnessWorkoutPriority(sport,"session_rpe"), html:_fitnessWorkoutMetricTile(this._profile, "session_rpe", rpeLabel, _fitnessDisplay(rpeState,0), rpeId)});
    }

    for (const key of fitnessKeys) {
      const id = e[key];
      const state = id ? this._hass.states[id] : null;
      if (!state || ["unknown","unavailable"].includes(String(state.state).toLowerCase())) continue;
      const numeric = Number(state.state);
      if (zeroIsMissing.has(key) && Number.isFinite(numeric) && Math.abs(numeric) < 1e-12) continue;
      const metricLabel = _fitnessWorkoutSemanticLabel(this._profile, key, entityName(this._hass, id));
      candidates.push({key, priority:_fitnessWorkoutPriority(sport,key), html:_fitnessWorkoutMetricTile(this._profile, key, metricLabel, _fitnessDisplay(state, _fitnessWorkoutMetricDecimals(key)), id)});
    }

    candidates.sort((a,b) => a.priority - b.priority);
    const items = candidates.filter((item) => item.priority < 900).slice(0, 9).map((item) => item.html).join("");

    const comparableId = e.last_workout_comparable_count || "";
    const comparableCount = _fitnessNumber(comparableId ? this._hass.states[comparableId]?.state : null);
    const hrBaselineId = e.last_workout_hr_vs_baseline || "";
    const hrState = hrBaselineId ? this._hass.states[hrBaselineId] : null;
    const hrDelta = _fitnessNumber(hrState?.state);
    const hrCurrent = _fitnessNumber(hrState?.attributes?.current_average_hr_bpm);
    const hrBaseline = _fitnessNumber(hrState?.attributes?.personal_baseline_average_hr_bpm);
    const hrReady = comparableCount != null && comparableCount >= 3 && hrDelta != null && hrCurrent != null && hrBaseline != null;
    const hrTone = _fitnessSymmetricHeatTone(hrDelta, 2, 5, 8);
    const hrRange = 20;
    const hrPosition = hrReady ? Math.max(1, Math.min(99, 50 + (hrDelta / hrRange) * 50)) : 50;
    const hrBar = hrReady ? `<div class="workout-hr-baseline entity-link" style="--hr-tone:${hrTone}" data-more-info="${_fitnessEscape(hrBaselineId)}">
      <div class="baseline-head"><span>HR ${_fitnessEscape(l.baseline)}</span><strong>${hrDelta >= 0 ? "+" : ""}${hrDelta.toFixed(1)} bpm</strong></div>
      <div class="baseline-values three">
        <span>${_fitnessEscape(l.baseline)}<b>${hrBaseline.toFixed(1)} bpm</b></span>
        <span>${_fitnessEscape(l.current)}<b>${hrCurrent.toFixed(1)} bpm</b></span>
        <span>${_fitnessEscape(l.difference)}<b style="color:var(--hr-tone)">${hrDelta >= 0 ? "+" : ""}${hrDelta.toFixed(1)} bpm</b></span>
      </div>
      <div class="baseline-axis heat-axis"><i class="baseline-marker"></i><i class="current-marker" style="left:${hrPosition}%"></i></div>
      <div class="baseline-scale"><span>${(hrBaseline-hrRange).toFixed(0)}</span><b>${hrBaseline.toFixed(1)} bpm · n=${comparableCount.toFixed(0)}</b><span>${(hrBaseline+hrRange).toFixed(0)}</span></div>
    </div>` : "";

    if (!workoutName && !items && !hrBar) {
      this.shadowRoot.innerHTML = "";
      return;
    }
    this.shadowRoot.innerHTML = `<ha-card>
      ${workoutName ? `<div class="workout-name entity-link" data-more-info="${_fitnessEscape(workoutMetric?.moreInfoEntityId || "")}">${_fitnessEscape(workoutName)}</div>` : ""}
      ${items ? `<div class="hi-grid">${items}</div>` : ""}
      ${hrBar}
    </ha-card><style>
      ha-card{padding:18px;min-width:0;overflow:hidden}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}
      .workout-name{font-size:20px;font-weight:700;line-height:1.25;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:normal;white-space:normal}
      .hi-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:14px;min-width:0}
      .hi{
        position:relative;padding:11px 12px 12px;border-radius:14px;min-width:0;max-width:100%;overflow:hidden;
        background:linear-gradient(145deg,color-mix(in srgb,var(--primary-color) 9%,var(--card-background-color)),var(--card-background-color) 72%);
        border:1px solid color-mix(in srgb,var(--primary-color) 16%,var(--divider-color));
        box-shadow:0 4px 14px color-mix(in srgb,var(--primary-text-color) 4%,transparent);
        transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease;
      }
      .hi:hover{transform:translateY(-1px);border-color:color-mix(in srgb,var(--primary-color) 38%,var(--divider-color));box-shadow:0 7px 18px color-mix(in srgb,var(--primary-color) 10%,transparent)}
      .hi-head{display:flex;align-items:center;gap:7px;min-width:0}
      .hi-icon{display:grid!important;place-items:center;flex:0 0 26px;width:26px;height:26px;border-radius:9px;background:color-mix(in srgb,var(--primary-color) 14%,transparent);color:var(--primary-color);overflow:visible!important}
      .hi-icon ha-icon{--mdc-icon-size:16px}
      .hi-label{display:block;font-size:10px;line-height:1.2;color:var(--secondary-text-color);white-space:normal;overflow-wrap:anywhere;min-width:0}
      .hi-value{display:block;font-size:17px;line-height:1.2;margin-top:8px;min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere;word-break:normal;font-weight:750;letter-spacing:-.01em}
      .workout-hr-baseline{margin-top:12px;padding:11px 12px;border-radius:13px;background:var(--secondary-background-color)}
      .baseline-head{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:11px}.baseline-head span{color:var(--secondary-text-color)}.baseline-head strong{color:var(--hr-tone);font-size:13px}
      .baseline-values{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:8px}.baseline-values span{padding:7px 8px;border-radius:9px;background:var(--card-background-color);font-size:9px;color:var(--secondary-text-color)}.baseline-values b{display:block;margin-top:3px;color:var(--primary-text-color);font-size:11px}
      .baseline-axis{height:10px;position:relative;margin-top:12px;border-radius:999px}.heat-axis{background:linear-gradient(90deg,#c62828 0%,#ef6c00 18%,#f9a825 34%,#2e7d32 44%,#2e7d32 56%,#f9a825 66%,#ef6c00 82%,#c62828 100%)}.baseline-marker{position:absolute;left:50%;top:-2px;bottom:-2px;width:2px;background:var(--primary-text-color);transform:translateX(-1px)}.current-marker{position:absolute;top:-3px;width:3px;height:16px;border-radius:2px;background:var(--hr-tone);box-shadow:0 0 0 1px var(--card-background-color);transform:translateX(-1px)}
      .baseline-scale{display:grid;grid-template-columns:1fr auto 1fr;margin-top:4px;font-size:9px;color:var(--secondary-text-color)}.baseline-scale span:last-child{text-align:right}.baseline-scale b{color:var(--primary-text-color);font-weight:650}
      @media(max-width:520px){.hi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.baseline-values{grid-template-columns:1fr 1fr}.baseline-values span:last-child{grid-column:1/-1}}
    </style>`;
  }
}

class FitnessStrengthDetailsCard extends FitnessAutoProfileCard {
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const e = this._profile?.entities || {};
    const l = this._profile?.labels || {};
    const source = this._hass.states[e.last_workout_strength_sets]
      || this._hass.states[e.last_workout_estimated_1rm]
      || this._hass.states[e.last_workout_strength_progression];
    const details = source?.attributes?.strength_analysis;
    const exercises = Array.isArray(details?.exercises) ? details.exercises : [];
    if (!exercises.length) {
      this.shadowRoot.innerHTML = "";
      return;
    }
    const rows = exercises.map((ex) => {
      const best = ex?.best_set;
      const bestText = best?.weight_kg != null && best?.reps != null
        ? `${Number(best.weight_kg).toFixed(1)} kg × ${best.reps}` : "—";
      const e1rm = _fitnessNumber(ex?.estimated_1rm_kg);
      const change = _fitnessNumber(ex?.e1rm_change_percent);
      const trend = change == null ? "" : `${change > 0 ? "↗" : change < 0 ? "↘" : "→"} ${change > 0 ? "+" : ""}${change.toFixed(1)}%`;
      const volume = _fitnessNumber(ex?.volume_kg);
      return `<div class="strength-row">
        <div class="strength-main"><strong>${_fitnessEscape(ex?.name || ex?.id || l.exercise)}</strong><span>${_fitnessEscape(bestText)}</span></div>
        <div class="strength-stat"><span>e1RM</span><strong>${e1rm == null ? "—" : `${e1rm.toFixed(1)} kg`}</strong></div>
        <div class="strength-stat"><span>${_fitnessEscape(l.volume)}</span><strong>${volume == null ? "—" : `${volume.toFixed(0)} kg`}</strong></div>
        <div class="strength-trend ${change > 0 ? "up" : change < 0 ? "down" : ""}">${_fitnessEscape(trend)}</div>
      </div>`;
    }).join("");
    const totalSets = _fitnessNumber(details?.total_sets);
    const totalReps = _fitnessNumber(details?.total_reps);
    const totalVolume = _fitnessNumber(details?.volume_kg);
    this.shadowRoot.innerHTML = `<ha-card>
      <div class="strength-head entity-link" data-more-info="${_fitnessEscape(source?.entity_id || e.last_workout_strength_sets || e.last_workout_estimated_1rm || e.last_workout_strength_progression || "")}"><div><strong>${_fitnessEscape(l.strength_progression)}</strong><span>${exercises.length} ${_fitnessEscape(l.exercises)}${totalSets != null ? ` · ${totalSets.toFixed(0)} ${_fitnessEscape(l.sets)}` : ""}${totalReps != null ? ` · ${totalReps.toFixed(0)} ${_fitnessEscape(l.reps)}` : ""}</span></div><ha-icon icon="mdi:dumbbell"></ha-icon></div>
      ${totalVolume != null ? `<div class="volume-hero entity-link" data-more-info="${_fitnessEscape(source?.entity_id || e.last_workout_strength_sets || "")}"><span>${_fitnessEscape(l.total_volume)}</span><strong>${totalVolume.toFixed(0)} kg</strong></div>` : ""}
      <div class="strength-list entity-link" data-more-info="${_fitnessEscape(source?.entity_id || e.last_workout_strength_sets || e.last_workout_estimated_1rm || e.last_workout_strength_progression || "")}">${rows}</div>
      <small class="method">${_fitnessEscape(l.estimated_1rm_method)}</small>
    </ha-card><style>
      ha-card{padding:18px}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.strength-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.strength-head strong{display:block;font-size:18px}.strength-head span{display:block;margin-top:3px;color:var(--secondary-text-color);font-size:11px}.strength-head ha-icon{color:var(--primary-color);--mdc-icon-size:28px}.volume-hero{display:flex;justify-content:space-between;align-items:end;margin:14px 0;padding:12px 14px;border-radius:13px;background:color-mix(in srgb,var(--primary-color) 10%,var(--secondary-background-color))}.volume-hero span{color:var(--secondary-text-color);font-size:11px}.volume-hero strong{font-size:20px}.strength-list{display:grid;gap:7px;margin-top:12px}.strength-row{display:grid;grid-template-columns:minmax(125px,1.6fr) minmax(72px,.7fr) minmax(72px,.7fr) minmax(58px,.55fr);gap:8px;align-items:center;padding:10px 11px;border-radius:12px;background:var(--secondary-background-color)}.strength-main{min-width:0}.strength-main strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.strength-main span,.strength-stat span{display:block;color:var(--secondary-text-color);font-size:10px;margin-top:2px}.strength-stat strong{display:block;font-size:12px;margin-top:2px}.strength-trend{text-align:right;font-weight:700;color:var(--secondary-text-color)}.strength-trend.up{color:var(--success-color,#43a047)}.strength-trend.down{color:var(--error-color,#db4437)}.method{display:block;margin-top:11px;color:var(--secondary-text-color);font-size:10px;line-height:1.4}@media(max-width:520px){.strength-row{grid-template-columns:minmax(120px,1fr) 1fr}.strength-trend{text-align:left}.strength-stat:nth-of-type(3){display:none}}
    </style>`;
  }
}

class FitnessProgressCard extends FitnessAutoProfileCard {
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const e = this._profile?.entities || {};
    const l = this._profile?.labels || {};
    const trend = this._hass.states[e.cardiorespiratory_fitness_trend];
    const predicted = this._hass.states[e.vo2max_percent_predicted];
    if (!trend && !predicted) { this.shadowRoot.innerHTML = ""; return; }
    const currentSource = _fitnessEvaluationSourceMetric(this._profile, this._hass, "vo2max", 1);
    const current = currentSource?.canonicalValue ?? _fitnessNumber(_fitnessAttr(trend, "current_vo2max_ml_kg_min")) ?? null;
    const mean28 = _fitnessNumber(_fitnessAttr(trend, "vo2max_28d_mean_ml_kg_min"));
    const mean90 = _fitnessNumber(_fitnessAttr(trend, "vo2max_90d_mean_ml_kg_min"));
    const slope = _fitnessNumber(_fitnessAttr(trend, "slope_percent_per_30d"));
    const pctPred = _fitnessNumber(_fitnessAttr(trend, "percent_predicted")) ?? _fitnessNumber(predicted?.state);
    const predictedAttr = _fitnessNumber(_fitnessAttr(predicted, "predicted_vo2max_ml_kg_min"));
    // A few provider/evaluation paths can expose a placeholder 0 here.  Zero is
    // not a physiologically usable predicted VO2max, so treat it as missing and
    // reconstruct the absolute prediction from the valid percent-of-predicted.
    const predictedAbsolute = predictedAttr != null && predictedAttr > 0
      ? predictedAttr
      : (current != null && current > 0 && pctPred != null && pctPred > 0 ? current / (pctPred / 100) : null);
    const status = slope == null ? "" : slope > 0.35 ? (l.improving) : slope < -0.35 ? (l.declining) : (l.stable);
    const arrow = slope == null ? "→" : slope > 0.35 ? "↗" : slope < -0.35 ? "↘" : "→";
    const delta28 = current != null && mean28 ? ((current - mean28) / mean28 * 100) : null;
    const useAbsoluteVo2Scale = current != null && current > 0 && predictedAbsolute != null && predictedAbsolute > 0;
    // The predicted value is the visual reference, so keep it exactly in the
    // middle of the bar.  Use +/-10% of the larger current/predicted value as
    // the normal window, expanding symmetrically only when needed to keep the
    // current marker inside the bar.
    const vo2ScaleMagnitude = useAbsoluteVo2Scale ? Math.max(current, predictedAbsolute) : null;
    const vo2ScaleHalfSpan = useAbsoluteVo2Scale
      ? Math.max(vo2ScaleMagnitude * 0.10, Math.abs(current - predictedAbsolute) * 1.05, 0.5)
      : null;
    const progressMin = useAbsoluteVo2Scale
      ? Math.max(0, predictedAbsolute - vo2ScaleHalfSpan)
      : 50;
    const progressMax = useAbsoluteVo2Scale
      ? predictedAbsolute + vo2ScaleHalfSpan
      : Math.max(130, Math.ceil((pctPred ?? 100) / 10) * 10);
    const progressSpan = Math.max(progressMax - progressMin, 0.1);
    const currentMarker = useAbsoluteVo2Scale
      ? Math.max(0, Math.min(100, ((current - progressMin) / progressSpan) * 100))
      : pctPred == null ? null : Math.max(0, Math.min(100, ((pctPred - progressMin) / progressSpan) * 100));
    const predictedMarker = useAbsoluteVo2Scale
      ? 50
      : Math.max(0, Math.min(100, ((100 - progressMin) / progressSpan) * 100));
    const progressLeftLabel = useAbsoluteVo2Scale ? `${progressMin.toFixed(1)}` : `${progressMin}%`;
    const progressMidLabel = useAbsoluteVo2Scale ? `${predictedAbsolute.toFixed(1)} ${l.predicted}` : (pctPred == null ? "—" : `${pctPred.toFixed(1)}%`);
    const progressRightLabel = useAbsoluteVo2Scale ? `${progressMax.toFixed(1)}` : `${progressMax}%`;
    const vo2Tone = _fitnessVo2Tone(pctPred);
    const rawSeries = Array.isArray(_fitnessAttr(trend, "daily_series")) ? _fitnessAttr(trend, "daily_series") : [];
    // VO2 history is sparse by nature. Keep only real positive measurements
    // with a usable timestamp, and position them on the chart by actual time
    // rather than by array index. Missing days therefore remain genuine gaps.
    const series = rawSeries.map((x) => {
      const v = _fitnessNumber(x?.value);
      const d = String(x?.start || x?.date || "");
      const t = Date.parse(d);
      return {v, d, t};
    }).filter((x) => x.v != null && x.v > 0 && Number.isFinite(x.t))
      .sort((a,b) => a.t - b.t)
      .slice(-90);
    if ([current, mean28, mean90, slope, pctPred].every(value => value == null) && !series.length) { this.shadowRoot.innerHTML = ""; return; }

    const metricCards = [
      this._metric(l.mean_28d, mean28, "mL/kg/min", false, e.cardiorespiratory_fitness_trend),
      this._metric(l.mean_90d, mean90, "mL/kg/min", false, e.cardiorespiratory_fitness_trend),
      this._metric(l.predicted_percent, pctPred, "%", false, e.vo2max_percent_predicted),
      this._metric("Δ 28d", delta28, "%", true, e.cardiorespiratory_fitness_trend),
    ].filter(Boolean).join("");

    let history = "";
    this._vo2HistoryPoints = [];
    this._vo2HistoryPredicted = predictedAbsolute;
    this._vo2HistoryLabels = l;
    if (!Number.isFinite(this._vo2HistoryZoom)) this._vo2HistoryZoom = 1;
    if (!Number.isFinite(this._vo2HistoryYExpand)) this._vo2HistoryYExpand = 1;
    if (series.length >= 5) {
      const n = series.length;
      const startT = series[0].t;
      const endT = series[n-1].t;
      const timeSpan = Math.max(endT - startT, 1);
      const xs = series.map((x)=>(x.t-startT)/86400000);
      const meanX = xs.reduce((sum,x)=>sum+x,0)/n;
      const meanY = series.reduce((sum,x)=>sum+x.v,0)/n;
      const denom = xs.reduce((sum,x)=>sum+((x-meanX)**2),0) || 1;
      const regSlope = series.reduce((sum,x,i)=>sum+((xs[i]-meanX)*(x.v-meanY)),0)/denom;
      const regIntercept = meanY - regSlope*meanX;
      const trendStart = regIntercept + regSlope*xs[0];
      const trendEnd = regIntercept + regSlope*xs[n-1];
      // Zoom the y-axis to the *measured* VO2max range.  Do not let a distant
      // predicted/reference value flatten real changes into an almost straight
      // line.  The predicted reference is drawn only when it falls in the zoomed
      // viewport; its numeric value remains in the legend/hover either way.
      const measuredVals = [...series.map(x=>x.v), trendStart, trendEnd];
      let lo = Math.min(...measuredVals), hi = Math.max(...measuredVals);
      const measuredRange = Math.max(hi - lo, 0);
      const pad = Math.max(measuredRange * 0.18, 0.15);
      if (measuredRange < 0.30) {
        const center = (lo + hi) / 2;
        lo = center - 0.30;
        hi = center + 0.30;
      } else {
        lo -= pad;
        hi += pad;
      }
      // Horizontal zoom magnifies time. Once horizontal zoom is back at 1x,
      // additional zoom-out expands the vertical VO2 range instead. This lets a
      // user bring a distant predicted/reference line into view without giving
      // up the tight default view of small real-world VO2 changes.
      const baseCenter = (lo + hi) / 2;
      const baseHalfSpan = Math.max((hi - lo) / 2, 0.05);
      const yExpand = Math.max(1, Math.min(32, this._vo2HistoryYExpand || 1));
      lo = Math.max(0, baseCenter - baseHalfSpan * yExpand);
      hi = baseCenter + baseHalfSpan * yExpand;
      const span = Math.max(hi-lo, 0.1);
      const y = value => 34-((value-lo)/span)*28;
      const xPos = t => ((t-startT)/timeSpan)*100;
      const actualPts = series.map((x)=>`${xPos(x.t).toFixed(2)},${y(x.v).toFixed(2)}`).join(" ");
      const trendPts = `0,${y(trendStart).toFixed(2)} 100,${y(trendEnd).toFixed(2)}`;
      const predictedInViewport = predictedAbsolute != null && predictedAbsolute >= lo && predictedAbsolute <= hi;
      const predictedY = predictedInViewport ? y(predictedAbsolute) : null;
      const predictedRangeHint = predictedAbsolute == null ? ""
        : predictedAbsolute < lo ? ` (${l.below_zoom})`
        : predictedAbsolute > hi ? ` (${l.above_zoom})` : "";
      this._vo2HistoryPoints = series.map((x,i) => ({
        x:xPos(x.t), y:y(x.v), v:x.v, d:x.d, t:x.t,
        trend:regIntercept + regSlope*xs[i],
      }));
      const locale = this._profile?.language || this._hass?.language || undefined;
      const tickFormatter = new Intl.DateTimeFormat(locale, {month:"short", day:"numeric"});
      const tickCount = Math.min(6, Math.max(2, Math.ceil(timeSpan / (14 * 86400000)) + 1));
      const ticks = Array.from({length:tickCount}, (_, index) => {
        const ratio = tickCount === 1 ? 0 : index / (tickCount - 1);
        const timestamp = startT + timeSpan * ratio;
        return `<span style="left:${(ratio*100).toFixed(2)}%">${_fitnessEscape(tickFormatter.format(new Date(timestamp)))}</span>`;
      }).join("");
      const historyDisplayZoom = (this._vo2HistoryZoom || 1) > 1.001
        ? (this._vo2HistoryZoom || 1)
        : 1 / Math.max(1, this._vo2HistoryYExpand || 1);
      history = `<div class="history">
        <div class="history-head">
          <span>${_fitnessEscape(l.history)}</span>
          <div class="history-head-tools"><small>${series.length} ${_fitnessEscape(l.measurements)}</small>
            <button class="history-zoom-out" type="button" title="${_fitnessEscape(l.zoom_out)}" aria-label="${_fitnessEscape(l.zoom_out)}">−</button>
            <button class="history-zoom-reset" type="button" title="${_fitnessEscape(l.reset_zoom)}" aria-label="${_fitnessEscape(l.reset_zoom)}">${historyDisplayZoom.toFixed(historyDisplayZoom < 1 || historyDisplayZoom % 1 ? 1 : 0)}×</button>
            <button class="history-zoom-in" type="button" title="${_fitnessEscape(l.zoom_in)}" aria-label="${_fitnessEscape(l.zoom_in)}">+</button>
          </div>
        </div>
        <div class="history-scroll">
          <div class="history-canvas" style="width:${Math.max(100, this._vo2HistoryZoom * 100)}%">
            <div class="history-plot">
              <svg class="vo2-history-svg entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || "")}" viewBox="0 0 100 38" preserveAspectRatio="none" aria-label="${_fitnessEscape(l.history)}">
                ${predictedY == null ? "" : `<line class="predicted-line" x1="0" y1="${predictedY.toFixed(2)}" x2="100" y2="${predictedY.toFixed(2)}"></line>`}
                <polyline class="actual-line" points="${actualPts}"></polyline>
                <polyline class="trend-line" points="${trendPts}"></polyline>
                <g class="history-cursor" visibility="hidden">
                  <line class="cursor-line" x1="0" y1="4" x2="0" y2="36"></line>
                  <circle class="cursor-dot" cx="0" cy="0" r="1.7"></circle>
                </g>
              </svg>
              <div class="history-tooltip" hidden></div>
            </div>
            <div class="history-x-axis" aria-label="${_fitnessEscape(l.date_axis)}">${ticks}</div>
          </div>
        </div>
        <div class="history-pan-hint">${_fitnessEscape(l.pan_hint)}</div>
        <div class="history-legend">
          <span class="entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || "")}"><i class="actual-dot"></i>${_fitnessEscape(l.actual)}</span>
          <span class="entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || "")}"><i class="trend-dot"></i>${_fitnessEscape(l.trend)}</span>
          ${predictedAbsolute == null ? "" : `<span class="entity-link" data-more-info="${_fitnessEscape(e.vo2max_percent_predicted || "")}"><i class="predicted-dot"></i>${_fitnessEscape(l.predicted)} ${predictedAbsolute.toFixed(1)}${_fitnessEscape(predictedRangeHint)}</span>`}
        </div>
        <div class="history-values"><span>${series[0].v.toFixed(1)}</span><b>${current == null ? series[n-1].v.toFixed(1) : current.toFixed(1)} mL/kg/min</b></div>
      </div>`;
    }

    this.shadowRoot.innerHTML = `<ha-card style="--vo2-tone:${vo2Tone}">
      <div class="head"><div><div class="title">${_fitnessEscape(this.config.title || l.progress_snapshot)}</div><div class="sub">${_fitnessEscape(status)}</div></div><div class="trend entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || "")}">${arrow}${slope == null ? "" : ` ${slope > 0 ? "+" : ""}${slope.toFixed(2)}%`}</div></div>
      <div class="hero entity-link" data-more-info="${_fitnessEscape(currentSource?.moreInfoEntityId || e.cardiorespiratory_fitness_trend || "")}"><strong>${current == null ? "—" : current.toFixed(1)}</strong><span>mL/kg/min</span><small>${_fitnessEscape(l.current_vo2max)}</small></div>
      <div class="progress entity-link" data-more-info="${_fitnessEscape(e.vo2max_percent_predicted || "")}">
        ${predictedAbsolute == null && !useAbsoluteVo2Scale ? `<i class="vo2-reference" style="left:${predictedMarker}%" title="100% ${_fitnessEscape(l.predicted_marker)}"></i>` : `<i class="vo2-reference" style="left:${predictedMarker}%" title="${_fitnessEscape(l.predicted_marker)} ${predictedAbsolute == null ? "100%" : `${predictedAbsolute.toFixed(1)} mL/kg/min`}"></i>`}
        ${currentMarker == null ? "" : `<i class="vo2-marker" style="left:${currentMarker}%" title="${_fitnessEscape(l.current_marker)} ${current == null ? `${pctPred.toFixed(1)}%` : `${current.toFixed(1)} mL/kg/min`}"></i>`}
      </div>
      <div class="progress-values entity-link" data-more-info="${_fitnessEscape(e.vo2max_percent_predicted || "")}"><span>${progressLeftLabel}</span><b>${progressMidLabel}</b><span>${progressRightLabel}</span></div>
      ${history}
      ${metricCards ? `<div class="metrics">${metricCards}</div>` : ""}
    </ha-card>${this._style()}`;
    this._bindVo2History();
  }
  _bindVo2History() {
    const svg = this.shadowRoot?.querySelector(".vo2-history-svg");
    const cursor = this.shadowRoot?.querySelector(".history-cursor");
    const cursorLine = this.shadowRoot?.querySelector(".cursor-line");
    const cursorDot = this.shadowRoot?.querySelector(".cursor-dot");
    const tooltip = this.shadowRoot?.querySelector(".history-tooltip");
    const points = Array.isArray(this._vo2HistoryPoints) ? this._vo2HistoryPoints : [];
    if (!svg || !cursor || !cursorLine || !cursorDot || !tooltip || !points.length) return;
    const move = (event) => {
      const rect = svg.getBoundingClientRect();
      if (!rect.width) return;
      const x = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100));
      let point = points[0];
      for (const candidate of points) {
        if (Math.abs(candidate.x - x) < Math.abs(point.x - x)) point = candidate;
      }
      cursor.setAttribute("visibility", "visible");
      cursorLine.setAttribute("x1", point.x.toFixed(2));
      cursorLine.setAttribute("x2", point.x.toFixed(2));
      cursorDot.setAttribute("cx", point.x.toFixed(2));
      cursorDot.setAttribute("cy", point.y.toFixed(2));
      const language = this._profile?.language || this._hass?.language || undefined;
      const date = new Intl.DateTimeFormat(language, {year:"numeric",month:"short",day:"numeric"}).format(new Date(point.t));
      const bits = [`<strong>${point.v.toFixed(1)} mL/kg/min</strong>`, `<span>${_fitnessEscape(date)}</span>`];
      const labels = this._vo2HistoryLabels || {};
      if (point.trend != null) bits.push(`<small>${_fitnessEscape(labels.trend)} ${point.trend.toFixed(1)}</small>`);
      if (this._vo2HistoryPredicted != null) bits.push(`<small>${_fitnessEscape(labels.predicted)} ${this._vo2HistoryPredicted.toFixed(1)}</small>`);
      tooltip.innerHTML = bits.join("");
      tooltip.hidden = false;
      const tooltipWidth = 154;
      const pixelX = (point.x / 100) * rect.width;
      tooltip.style.left = `${Math.max(4, Math.min(rect.width - tooltipWidth - 4, pixelX + 9))}px`;
      tooltip.style.top = `${Math.max(2, (point.y / 38) * rect.height - 48)}px`;
    };
    const hide = () => {
      cursor.setAttribute("visibility", "hidden");
      tooltip.hidden = true;
    };
    svg.addEventListener("pointermove", move);
    svg.addEventListener("pointerdown", move);
    svg.addEventListener("pointerleave", hide);

    const scroller = this.shadowRoot?.querySelector(".history-scroll");
    const canvas = this.shadowRoot?.querySelector(".history-canvas");
    const zoomIn = this.shadowRoot?.querySelector(".history-zoom-in");
    const zoomOut = this.shadowRoot?.querySelector(".history-zoom-out");
    const zoomReset = this.shadowRoot?.querySelector(".history-zoom-reset");
    if (!scroller || !canvas) return;

    const applyHorizontalZoom = (nextZoom, anchorClientX = null) => {
      const previousWidth = Math.max(canvas.getBoundingClientRect().width, 1);
      const viewportWidth = Math.max(scroller.clientWidth, 1);
      const scrollerRect = scroller.getBoundingClientRect();
      const anchorViewportX = anchorClientX == null
        ? viewportWidth / 2
        : Math.max(0, Math.min(viewportWidth, anchorClientX - scrollerRect.left));
      const anchorContentX = scroller.scrollLeft + anchorViewportX;
      const anchorRatio = Math.max(0, Math.min(1, anchorContentX / previousWidth));
      const zoom = Math.max(1, Math.min(8, Number(nextZoom) || 1));
      this._vo2HistoryZoom = zoom;
      canvas.style.width = `${zoom * 100}%`;
      if (zoomReset) zoomReset.textContent = `${zoom.toFixed(zoom % 1 ? 1 : 0)}×`;
      requestAnimationFrame(() => {
        const nextWidth = Math.max(canvas.getBoundingClientRect().width, 1);
        scroller.scrollLeft = Math.max(0, anchorRatio * nextWidth - anchorViewportX);
      });
    };

    const zoomOutOneStep = (anchorClientX = null) => {
      const horizontal = this._vo2HistoryZoom || 1;
      if (horizontal > 1.001) {
        applyHorizontalZoom(Math.max(1, horizontal / 1.35), anchorClientX);
        return;
      }
      this._vo2HistoryYExpand = Math.min(32, (this._vo2HistoryYExpand || 1) * 1.35);
      this._render();
    };
    const zoomInOneStep = (anchorClientX = null) => {
      const yExpand = this._vo2HistoryYExpand || 1;
      if (yExpand > 1.001) {
        const next = yExpand / 1.35;
        this._vo2HistoryYExpand = next < 1.02 ? 1 : next;
        this._render();
        return;
      }
      applyHorizontalZoom((this._vo2HistoryZoom || 1) * 1.35, anchorClientX);
    };

    zoomIn?.addEventListener("click", (event) => { event.stopPropagation(); zoomInOneStep(); });
    zoomOut?.addEventListener("click", (event) => { event.stopPropagation(); zoomOutOneStep(); });
    zoomReset?.addEventListener("click", (event) => {
      event.stopPropagation();
      this._vo2HistoryZoom = 1;
      this._vo2HistoryYExpand = 1;
      this._render();
    });
    scroller.addEventListener("wheel", (event) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      event.preventDefault();
      if (event.deltaY < 0) zoomInOneStep(event.clientX);
      else zoomOutOneStep(event.clientX);
    }, {passive:false});

    // Drag-to-pan complements native touch/trackpad horizontal scrolling. Keep it
    // independent from the hover cursor so inspection still works while zoomed.
    let dragStart = null;
    scroller.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.target?.closest?.("button")) return;
      dragStart = {x:event.clientX, left:scroller.scrollLeft};
    });
    scroller.addEventListener("pointermove", (event) => {
      if (!dragStart || !(event.buttons & 1)) return;
      const delta = event.clientX - dragStart.x;
      if (Math.abs(delta) > 3) scroller.scrollLeft = dragStart.left - delta;
    });
    const endDrag = () => { dragStart = null; };
    scroller.addEventListener("pointerup", endDrag);
    scroller.addEventListener("pointercancel", endDrag);
    scroller.addEventListener("pointerleave", endDrag);
  }
  _metric(label, value, unit, signed=false, entityId="") {
    if (value == null) return "";
    const formatted = `${signed && value > 0 ? "+" : ""}${value.toFixed(1)}${unit ? ` ${unit}` : ""}`;
    return `<div class="metric entity-link" data-more-info="${_fitnessEscape(entityId)}"><span>${_fitnessEscape(label)}</span><strong>${formatted}</strong></div>`;
  }
  _style() {
    return `<style>
      ha-card{padding:18px}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.head{display:flex;justify-content:space-between;align-items:flex-start}.title{font-size:19px;font-weight:650}.sub{font-size:12px;color:var(--secondary-text-color);margin-top:3px}.trend{font-size:16px;font-weight:700;color:var(--vo2-tone)}
      .hero{display:grid;grid-template-columns:auto auto 1fr;align-items:end;gap:6px;margin:20px 0 10px}.hero strong{font-size:40px;line-height:1;color:var(--vo2-tone)}.hero span{font-size:12px;color:var(--secondary-text-color);padding-bottom:4px}.hero small{text-align:right;color:var(--secondary-text-color)}
      .progress{height:10px;background:linear-gradient(90deg,#c62828 0%,#ef6c00 27%,#f9a825 45%,#7cb342 62%,#2e7d32 78%,#2e7d32 100%);border-radius:999px;overflow:visible;position:relative}.vo2-reference{position:absolute;top:-4px;width:2px;height:18px;border-radius:2px;background:#fff;box-shadow:0 0 0 1px rgba(0,0,0,.18);transform:translateX(-1px);z-index:2}.vo2-marker{position:absolute;top:-4px;width:3px;height:18px;border-radius:2px;background:var(--vo2-tone);box-shadow:0 0 0 1px var(--card-background-color),0 0 5px color-mix(in srgb,var(--vo2-tone) 60%,transparent);transform:translateX(-1.5px);z-index:3}.vo2-marker:after{content:"";position:absolute;top:50%;left:50%;width:8px;height:8px;border-radius:50%;background:var(--vo2-tone);border:2px solid var(--card-background-color);transform:translate(-50%,-50%)}.progress-values{display:grid;grid-template-columns:1fr auto 1fr;margin-top:5px;font-size:9px;color:var(--secondary-text-color)}.progress-values span:last-child{text-align:right}.progress-values b{color:var(--vo2-tone);font-weight:700}.history-values{display:flex;justify-content:space-between;gap:10px;margin-top:3px;font-size:9px;color:var(--secondary-text-color)}.history-values b{color:var(--primary-text-color);font-weight:650}
      .history{margin-top:16px;padding:10px 12px;border-radius:12px;background:var(--secondary-background-color)}.history-head{display:flex;justify-content:space-between;align-items:center;gap:8px;color:var(--secondary-text-color);font-size:11px}.history-head-tools{display:flex;align-items:center;gap:5px}.history-head-tools small{margin-right:3px}.history-head-tools button{appearance:none;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);border-radius:8px;min-width:28px;height:25px;padding:0 7px;font:inherit;cursor:pointer}.history-head-tools button:hover{filter:brightness(1.08)}.history-scroll{overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain;scrollbar-width:thin;touch-action:pan-x pan-y}.history-canvas{position:relative;min-width:100%;transition:width .12s ease}.history-plot{position:relative;margin-top:7px;min-width:0}.history svg{width:100%;height:88px;display:block;overflow:visible;touch-action:none}.history-x-axis{position:relative;height:18px;margin:1px 2px 0;border-top:1px solid color-mix(in srgb,var(--divider-color) 70%,transparent);font-size:9px;color:var(--secondary-text-color)}.history-x-axis span{position:absolute;top:4px;transform:translateX(-50%);white-space:nowrap}.history-x-axis span:first-child{transform:none}.history-x-axis span:last-child{transform:translateX(-100%)}.history-pan-hint{margin-top:3px;font-size:8px;color:var(--secondary-text-color);opacity:.82}.actual-line{fill:none;stroke:var(--primary-color);stroke-width:1.8;vector-effect:non-scaling-stroke;stroke-linecap:round;stroke-linejoin:round}.trend-line{fill:none;stroke:var(--vo2-tone);stroke-width:1.5;stroke-dasharray:5 3;vector-effect:non-scaling-stroke}.predicted-line{stroke:var(--secondary-text-color);stroke-width:1.2;stroke-dasharray:2.5 2.5;vector-effect:non-scaling-stroke;opacity:.8}.cursor-line{stroke:var(--primary-text-color);stroke-width:1;stroke-dasharray:2 2;opacity:.7;vector-effect:non-scaling-stroke}.cursor-dot{fill:var(--primary-color);stroke:var(--card-background-color);stroke-width:1;vector-effect:non-scaling-stroke}.history-tooltip{position:absolute;z-index:3;min-width:132px;max-width:154px;padding:6px 8px;border-radius:9px;background:color-mix(in srgb,var(--card-background-color) 94%,black 6%);box-shadow:0 3px 12px rgba(0,0,0,.28);pointer-events:none;font-size:9px;line-height:1.3}.history-tooltip strong,.history-tooltip span,.history-tooltip small{display:block}.history-tooltip strong{font-size:11px;color:var(--primary-text-color)}.history-tooltip span{color:var(--secondary-text-color);margin-top:1px}.history-tooltip small{color:var(--secondary-text-color);margin-top:2px}.history-legend{display:flex;flex-wrap:wrap;gap:8px 14px;margin-top:3px;font-size:9px;color:var(--secondary-text-color)}.history-legend span{display:flex;align-items:center;gap:5px}.history-legend i{width:13px;height:3px;border-radius:3px}.actual-dot{background:var(--primary-color)}.trend-dot{background:var(--vo2-tone)}.predicted-dot{background:var(--secondary-text-color)}
      .metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:16px}.metric{padding:10px 12px;border-radius:12px;background:var(--secondary-background-color)}.metric span{display:block;color:var(--secondary-text-color);font-size:11px;margin-bottom:3px}.metric strong{font-size:14px}.empty{padding:6px}.empty small{display:block;color:var(--secondary-text-color);margin-top:8px}
    </style>`;
  }
}

class FitnessRecoveryCard extends FitnessAutoProfileCard {
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const e = this._profile?.entities || {};
    const l = this._profile?.labels || {};
    const readiness = this._hass.states[e.readiness];
    const autonomic = this._hass.states[e.autonomic_recovery_trend];
    const recoveryTime = this._hass.states[e.estimated_recovery_time];

    const score = _fitnessNumber(readiness?.state);
    const level = String(_fitnessAttr(readiness, "level") || "insufficient_data");
    const confidence = _fitnessNumber(_fitnessAttr(readiness, "confidence_percent"));
    const components = _fitnessAttr(readiness, "components") || {};
    const ui = String(this._profile?.language || this._hass?.language || "en").toLowerCase().split("-")[0];
    const rtext = FITNESS_READINESS_TEXT[ui] || FITNESS_READINESS_TEXT.en;
    const levelText = (FITNESS_READINESS_LEVELS[ui] || FITNESS_READINESS_LEVELS.en)[level]
      || FITNESS_READINESS_LEVELS.en[level] || level;
    const readinessName = e.readiness ? entityName(this._hass, e.readiness) : "Readiness";
    const bounded = score == null ? 0 : Math.max(0, Math.min(100, score));
    const readinessTone = score == null ? "#78909c"
      : score >= 85 ? "#2e7d32"
      : score >= 70 ? "#00897b"
      : score >= 50 ? "#f9a825"
      : score >= 30 ? "#ef6c00"
      : "#c62828";

    const remaining = _fitnessNumber(recoveryTime?.state);
    const readyAtRaw = _fitnessAttr(recoveryTime, "ready_for_next_workout_at");
    const recoveryLow = _fitnessNumber(_fitnessAttr(recoveryTime, "estimated_recovery_low_hours"));
    const recoveryHigh = _fitnessNumber(_fitnessAttr(recoveryTime, "estimated_recovery_high_hours"));
    const recoveryProgress = _fitnessNumber(_fitnessAttr(recoveryTime, "recovery_progress_percent"));
    const recoveryConfidence = _fitnessNumber(_fitnessAttr(recoveryTime, "confidence_percent"));
    const recoveryLevel = String(_fitnessAttr(recoveryTime, "level") || "recovering");
    const recoverySignals = _fitnessAttr(recoveryTime, "recovery_signals") || {};
    const limitingFactor = String(_fitnessAttr(recoveryTime, "limiting_factor") || "");
    const limiterLabels = {
      muscular_recovery: l.limiter_muscular_recovery,
      autonomic_recovery: l.limiter_autonomic_recovery,
      sleep_recovery: l.limiter_sleep_recovery,
      overall_readiness: l.limiter_overall_readiness,
      workout_dose: l.limiter_workout_dose,
    };
    const limitingFactorText = limiterLabels[limitingFactor] || limitingFactor.replaceAll("_", " ");

    const readyAt = readyAtRaw ? new Date(readyAtRaw) : null;
    const readyAtText = (() => {
      if (!readyAt || Number.isNaN(readyAt.getTime())) return "—";
      const language = this._profile?.language || this._hass?.language || undefined;
      const timeText = new Intl.DateTimeFormat(language, {hour:"2-digit", minute:"2-digit"}).format(readyAt);
      const now = new Date();
      const sameDay = (a,b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
      const tomorrow = new Date(now); tomorrow.setDate(now.getDate()+1);
      if (sameDay(readyAt, now)) {
        const day = new Intl.RelativeTimeFormat(language, {numeric:"auto"}).format(0, "day");
        return `${day} ${timeText}`;
      }
      if (sameDay(readyAt, tomorrow)) {
        const day = new Intl.RelativeTimeFormat(language, {numeric:"auto"}).format(1, "day");
        return `${day} ${timeText}`;
      }
      const day = new Intl.DateTimeFormat(language, {weekday:"short", month:"short", day:"numeric"}).format(readyAt);
      return `${day} ${timeText}`;
    })();
    const fullyRecovered = remaining != null && remaining <= 0;

    const recoveryTones = {
      ready: "#2e7d32",
      nearly_ready: "#7cb342",
      recovering: "#f9a825",
      substantial_recovery: "#ef6c00",
      high_recovery_demand: "#c62828",
    };
    const recoveryTone = recoveryTones[recoveryLevel] || recoveryTones.recovering;
    const recoveryPct = recoveryProgress == null ? 0 : Math.max(0, Math.min(100, recoveryProgress));

    const componentRows = [
      ["autonomic", "mdi:heart-pulse", "HRV / RHR"],
      ["sleep", "mdi:sleep", rtext.sleep],
      ["recovery_response", "mdi:heart-sync", e.heart_rate_recovery ? entityName(this._hass,e.heart_rate_recovery) : rtext.response],
    ].map(([key, icon, label]) => {
      const value = _fitnessNumber(components?.[key]?.score);
      if (value == null) return "";
      const componentTone = value >= 85 ? "#2e7d32"
        : value >= 70 ? "#00897b"
        : value >= 50 ? "#f9a825"
        : value >= 30 ? "#ef6c00"
        : "#c62828";
      return `<div class="component entity-link" data-more-info="${_fitnessEscape(e.readiness || "")}" style="--component-tone:${componentTone}">
        <ha-icon icon="${icon}"></ha-icon>
        <span title="${_fitnessEscape(label)}">${_fitnessEscape(label)}</span>
        <strong>${value.toFixed(0)}</strong>
        <div><i data-fitness-bar style="width:${Math.max(0, Math.min(100, value))}%"></i></div>
      </div>`;
    }).filter(Boolean).join("");

    const scoreBar = ({kind, label, value, tone, detail = "", entityId = e.readiness || ""}) => value == null ? "" : `<div class="recovery-score recovery-score-${kind} entity-link" data-more-info="${_fitnessEscape(entityId)}" style="--score-tone:${tone}">
      <div class="recovery-score-head"><span>${_fitnessEscape(label)}</span><strong>${Math.max(0, Math.min(100, value)).toFixed(0)} <small>/ 100</small></strong></div>
      <div class="recovery-score-track"><i data-fitness-bar style="width:${Math.max(0, Math.min(100, value))}%"></i></div>
      ${detail ? `<div class="recovery-score-detail">${detail}</div>` : ""}
    </div>`;
    const compactText = (template, values = {}) => {
      let result = String(template || "");
      for (const [key, value] of Object.entries(values)) {
        result = result.replaceAll(`{${key}}`, String(value));
      }
      return result;
    };
    const readinessCertainty = confidence == null ? "" : compactText(
      l.certain_compact,
      {percent:confidence.toFixed(0)},
    );
    const readinessDetail = [
      levelText ? `<b>${_fitnessEscape(levelText)}</b>` : "",
      readinessCertainty ? _fitnessEscape(readinessCertainty) : "",
    ].filter(Boolean).join(" · ");
    const readinessScoreBar = scoreBar({
      kind:"readiness", label:readinessName, value:score, tone:readinessTone, detail:readinessDetail,
    });
    const readinessStack = readinessScoreBar
      ? `<div class="recovery-score-stack">${readinessScoreBar}</div>`
      : "";
    const unitGap = ["zh", "ja", "ko"].includes(ui) ? "" : " ";
    const recoveryRemainingText = (() => {
      if (remaining == null || remaining <= 0) return "";
      const totalMinutes = Math.max(1, Math.round(remaining * 60));
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;
      return [
        hours ? `${hours}${unitGap}${l.hours_short}` : "",
        minutes ? `${minutes}${unitGap}${l.minutes_short}` : "",
      ].filter(Boolean).join(" ");
    })();
    const recoveryComplete = fullyRecovered || (recoveryProgress != null && Math.round(recoveryPct) >= 100);
    const recoveryCertainty = recoveryConfidence == null ? "" : compactText(
      l.certain_compact,
      {percent:recoveryConfidence.toFixed(0)},
    );
    const recoveryProgressDetail = recoveryComplete
      ? [
          `<b>${_fitnessEscape(l.recovery_done_short)}</b>`,
          recoveryCertainty ? _fitnessEscape(recoveryCertainty) : "",
        ].filter(Boolean).join(" · ")
      : [
          readyAtRaw && readyAtText !== "—" ? _fitnessEscape(compactText(
            l.ready_at_compact,
            {time:readyAtText},
          )) : "",
          recoveryRemainingText ? _fitnessEscape(compactText(
            l.remaining_compact,
            {time:recoveryRemainingText},
          )) : "",
          recoveryCertainty ? _fitnessEscape(recoveryCertainty) : "",
        ].filter(Boolean).join(", ");
    const recoveryProgressBar = scoreBar({
      kind:"progress",
      label:l.recovery_progress_label,
      value:recoveryProgress,
      tone:recoveryTone,
      detail:recoveryProgressDetail,
      entityId:e.estimated_recovery_time || "",
    });

    const signalLabels = {
      hrv: "HRV",
      resting_hr: "RHR",
      hrr: "HRR",
      sleep: rtext.sleep,
    };
    const signalIcons = {
      supportive: "✓",
      near_baseline: "✓",
      above_baseline: "↑",
      slightly_below_baseline: "↘",
      below_baseline: "↓",
      slightly_above_baseline: "↗",
      reduced: "↓",
      neutral: "•",
      insufficient_data: "?",
    };
    const signalRows = Object.entries(recoverySignals).map(([key, value]) => {
      const code = String(value || "insufficient_data");
      return `<span class="signal entity-link signal-${_fitnessEscape(code)}" data-more-info="${_fitnessEscape(e.estimated_recovery_time || e.readiness || "")}">
        <b>${_fitnessEscape(signalIcons[code] || "•")}</b>
        ${_fitnessEscape(signalLabels[key] || key)}
      </span>`;
    }).join("");

    const hrvVs = _fitnessNumber(_fitnessAttr(autonomic, "sleep_hrv_latest_vs_28d_percent"));
    const hrvSource = _fitnessSleepSourceMetric(this._profile, this._hass, "last_sleep_hrv", 1);
    const hrvLatest = hrvSource?.canonicalValue ?? _fitnessNumber(_fitnessAttr(autonomic, "sleep_hrv_latest_ms")) ?? null;
    const hrvBaseline = _fitnessNumber(_fitnessAttr(autonomic, "sleep_hrv_28d_mean_ms"));
    const hrvBaselineNights = _fitnessNumber(_fitnessAttr(autonomic, "sleep_hrv_baseline_nights"));
    const rhrVs = _fitnessNumber(_fitnessAttr(autonomic, "resting_hr_vs_28d_bpm"));
    const hrvBaselineReady = hrvVs != null && hrvLatest != null && hrvBaseline != null && hrvBaseline > 0 && hrvBaselineNights != null && hrvBaselineNights >= 14;
    const hrvPosition = hrvBaselineReady ? Math.max(1, Math.min(99, 50 + (hrvVs / 20) * 50)) : 50;
    const hrvTone = _fitnessSymmetricHeatTone(hrvVs, 3, 7, 12);
    const hrvBaselineBar = hrvBaselineReady ? `<div class="hrv-baseline entity-link" style="--hrv-tone:${hrvTone}" data-more-info="${_fitnessEscape(e.autonomic_recovery_trend || hrvSource?.moreInfoEntityId || "")}">
      <div class="hrv-head"><span>HRV ${_fitnessEscape(l.baseline)}</span><strong>${hrvVs >= 0 ? "+" : ""}${hrvVs.toFixed(1)}%</strong></div>
      <div class="hrv-values three">
        <span>${_fitnessEscape(l.baseline)} <b>${hrvBaseline.toFixed(1)} ms</b></span>
        <span class="entity-link" data-more-info="${_fitnessEscape(hrvSource?.moreInfoEntityId || "")}">${_fitnessEscape(l.current)} <b>${hrvLatest.toFixed(1)} ms</b></span>
        <span>${_fitnessEscape(l.difference)} <b style="color:var(--hrv-tone)">${hrvVs >= 0 ? "+" : ""}${hrvVs.toFixed(1)}%</b></span>
      </div>
      <div class="hrv-axis"><i class="hrv-baseline-marker"></i><i class="hrv-current-marker" style="left:${hrvPosition}%"></i></div>
      <div class="hrv-axis-values"><span>-20%</span><b>${hrvBaseline.toFixed(1)} ms · n=${hrvBaselineNights.toFixed(0)}</b><span>+20%</span></div>
    </div>` : "";
    const hasRecoveryInfo = Boolean(
      score != null
      || remaining != null
      || componentRows
      || signalRows
      || hrvVs != null
      || rhrVs != null
      || limitingFactor
    );
    if (!hasRecoveryInfo) {
      this.shadowRoot.innerHTML = "";
      return;
    }

    this.shadowRoot.innerHTML = `<ha-card style="--readiness:${readinessTone};--recovery:${recoveryTone}">
      <div class="title">${_fitnessEscape(this.config.title || l.recovery_snapshot)}</div>

      <section class="recovery-readiness-panel">
        <div class="section-label">${_fitnessEscape(l.recovery_readiness)}</div>
        ${!recoveryTime ? readinessStack : ""}

        ${recoveryTime ? `<div class="next-workout entity-link" data-more-info="${_fitnessEscape(e.estimated_recovery_time || "")}">
        ${recoveryProgressBar ? `<div class="recovery-score-stack recovery-progress-stack">${recoveryProgressBar}</div>` : ""}

        ${readinessStack}

        <div class="recovery-grid">
          <div class="entity-link" data-more-info="${_fitnessEscape(e.estimated_recovery_time || "")}">
            <span>${_fitnessEscape(l.broader_recovery_window)}</span>
            <strong>${recoveryLow == null || recoveryHigh == null
              ? "—"
              : `~${Math.round(recoveryLow)}–${Math.round(recoveryHigh)} ${_fitnessEscape(l.hours_short)}`}</strong>
          </div>
          ${limitingFactor ? `<div class="entity-link" data-more-info="${_fitnessEscape(e.estimated_recovery_time || "")}"><span>${_fitnessEscape(l.recovery_limiting_factor)}</span><strong>${_fitnessEscape(limitingFactorText)}</strong></div>` : ""}
        </div>

        ${signalRows ? `<div class="signal-head">${_fitnessEscape(l.recovery_signals_label)}</div><div class="signals">${signalRows}</div>` : ""}
        <div class="physio-note">${_fitnessEscape(l.physio_note)}</div>
        </div>` : ""}
      </section>

      ${componentRows ? `<div class="components entity-link" data-more-info="${_fitnessEscape(e.readiness || "")}">${componentRows}</div>` : ""}
      ${hrvBaselineBar}

      <div class="context">
        ${hrvBaselineBar || hrvVs == null ? "" : `<span class="entity-link" data-more-info="${_fitnessEscape(e.autonomic_recovery_trend || "")}">HRV ${hrvVs > 0 ? "+" : ""}${hrvVs.toFixed(1)}% ${_fitnessEscape(rtext.vs28)}</span>`}
        ${rhrVs == null ? "" : `<span class="entity-link" data-more-info="${_fitnessEscape(e.autonomic_recovery_trend || "")}">RHR ${rhrVs > 0 ? "+" : ""}${rhrVs.toFixed(1)} bpm ${_fitnessEscape(rtext.vs28)}</span>`}
      </div>

    </ha-card><style>
      ha-card{padding:18px;overflow:hidden}
      .entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}
      .title{font-size:19px;font-weight:650}

      .recovery-readiness-panel{margin-top:10px;padding:9px;border-radius:16px;background:var(--secondary-background-color);overflow:hidden}
      .section-label{font-size:10px;font-weight:650;color:var(--secondary-text-color);padding:0 4px 8px}
      .readiness-panel{
        display:grid;grid-template-columns:112px minmax(0,1fr);align-items:center;
        gap:18px;padding:15px;border-radius:16px;
        background:linear-gradient(135deg,color-mix(in srgb,var(--readiness) 15%,transparent),var(--card-background-color));
        min-width:0
      }
      .readiness-ring{
        width:104px;height:104px;border-radius:50%;display:grid;place-items:center;
        background:conic-gradient(var(--readiness) var(--p),color-mix(in srgb,var(--readiness) 15%,var(--secondary-background-color)) 0)
      }
      .readiness-ring>div{
        width:76px;height:76px;border-radius:50%;background:var(--ha-card-background,var(--card-background-color));
        display:flex;align-items:baseline;justify-content:center
      }
      .readiness-ring strong{font-size:30px;line-height:76px;color:var(--readiness)}
      .readiness-ring span{font-size:10px;color:var(--secondary-text-color);margin-left:2px}
      .readiness-copy{min-width:0}
      .readiness-copy small{display:block;color:var(--secondary-text-color);font-size:11px}
      .readiness-copy strong{display:block;color:var(--readiness);font-size:25px;line-height:1.15;margin-top:4px;overflow-wrap:anywhere}
      .readiness-copy span{display:block;color:var(--secondary-text-color);font-size:11px;margin-top:6px}

      .next-workout{
        margin-top:5px;padding:10px 11px;border-radius:13px;
        background:linear-gradient(135deg,color-mix(in srgb,var(--recovery) 12%,transparent),var(--card-background-color));
        border-left:4px solid var(--recovery);min-width:0
      }
      .recovery-score-stack{display:grid;gap:7px;margin-top:8px}
      .recovery-progress-stack{margin-top:0}
      .recovery-score{padding:8px 9px;border-radius:10px;background:var(--card-background-color);background:linear-gradient(135deg,color-mix(in srgb,var(--score-tone) 10%,var(--card-background-color)),var(--card-background-color));border-left:3px solid var(--score-tone);min-width:0}
      .recovery-score-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.recovery-score-head span{font-size:10px;color:var(--secondary-text-color);font-weight:650;overflow-wrap:anywhere}.recovery-score-head strong{font-size:18px;color:var(--score-tone);white-space:nowrap}.recovery-score-head strong small{font-size:9px;color:var(--secondary-text-color);font-weight:500}
      .recovery-score-track{height:7px;border-radius:999px;margin-top:6px;background:var(--divider-color);background:color-mix(in srgb,var(--score-tone) 13%,var(--divider-color));overflow:hidden}.recovery-score-track i{display:block;height:100%;border-radius:inherit;background:var(--score-tone);background:linear-gradient(90deg,color-mix(in srgb,var(--score-tone) 38%,transparent),var(--score-tone))}
      .recovery-score-detail{margin-top:4px;font-size:9px;line-height:1.3;color:var(--secondary-text-color);overflow-wrap:anywhere}.recovery-score-detail b{color:var(--score-tone);font-weight:650}.recovery-score-progress .recovery-score-detail{white-space:nowrap;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;overscroll-behavior-x:contain}.recovery-score-progress .recovery-score-detail::-webkit-scrollbar{display:none}

      .recovery-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:11px}
      .recovery-grid>div{min-width:0;padding:9px 10px;border-radius:11px;background:var(--card-background-color)}
      .recovery-grid span{display:block;font-size:9px;line-height:1.25;color:var(--secondary-text-color);overflow-wrap:anywhere}
      .recovery-grid strong{display:block;font-size:12px;line-height:1.3;margin-top:3px;overflow-wrap:anywhere}

      .signal-head{font-size:9px;color:var(--secondary-text-color);margin-top:10px}
      .signals{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
      .signal{display:inline-flex;align-items:center;gap:4px;font-size:10px;padding:5px 7px;border-radius:999px;background:var(--card-background-color)}
      .signal b{font-size:11px}
      .signal-supportive,.signal-near_baseline,.signal-above_baseline{color:#2e7d32}
      .signal-reduced,.signal-below_baseline{color:#c62828}
      .signal-slightly_below_baseline,.signal-slightly_above_baseline{color:#ef6c00}
      .hrv-baseline{margin-top:8px;padding:9px 10px;border-radius:12px;background:var(--card-background-color)}.hrv-head{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:11px}.hrv-head span{color:var(--secondary-text-color)}.hrv-head strong{color:var(--hrv-tone);font-size:12px}.hrv-values{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:7px}.hrv-values span{padding:6px 7px;border-radius:9px;background:var(--secondary-background-color);font-size:9px;color:var(--secondary-text-color)}.hrv-values b{display:block;margin-top:2px;color:var(--primary-text-color);font-size:11px}.hrv-values.three{grid-template-columns:repeat(3,minmax(0,1fr))}.hrv-axis{height:10px;position:relative;margin-top:10px;border-radius:5px;background:linear-gradient(90deg,#c62828 0%,#ef6c00 18%,#f9a825 34%,#2e7d32 44%,#2e7d32 56%,#f9a825 66%,#ef6c00 82%,#c62828 100%)}.hrv-baseline-marker{position:absolute;left:50%;top:-2px;bottom:-2px;width:2px;background:var(--primary-text-color);transform:translateX(-1px)}.hrv-current-marker{position:absolute;top:-3px;width:3px;height:15px;border-radius:2px;background:var(--hrv-tone);box-shadow:0 0 0 1px var(--card-background-color);transform:translateX(-1px)}.hrv-axis-values{display:grid;grid-template-columns:1fr auto 1fr;margin-top:4px;font-size:9px;color:var(--secondary-text-color)}.hrv-axis-values span:last-child{text-align:right}.hrv-axis-values b{font-weight:700;color:var(--primary-text-color)}
      .physio-note{margin-top:8px;font-size:9px;line-height:1.35;color:var(--secondary-text-color);overflow-wrap:anywhere}

      .components{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:11px}
      .component{
        display:grid;grid-template-columns:22px minmax(0,1fr) auto;align-items:center;
        column-gap:7px;padding:9px 10px;border-radius:12px;background:var(--secondary-background-color);min-width:0
      }
      .component ha-icon{--mdc-icon-size:18px;color:var(--component-tone)}
      .component span{font-size:10px;line-height:1.2;color:var(--secondary-text-color);min-width:0;white-space:normal;overflow-wrap:anywhere}
      .component strong{font-size:13px}
      .component>div{grid-column:2/4;height:4px;border-radius:999px;background:var(--divider-color);overflow:hidden;margin-top:5px}
      .component i{display:block;height:100%;border-radius:999px;background:var(--component-tone)}

      .context{display:flex;flex-wrap:wrap;gap:6px 12px;margin-top:10px}
      .context span{font-size:10px;color:var(--secondary-text-color)}
      .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:8px;margin-top:12px}
      .metric{background:var(--secondary-background-color);padding:10px;border-radius:12px;min-width:0;overflow:hidden}
      .metric span{display:block;color:var(--secondary-text-color);font-size:10px;line-height:1.3;margin-bottom:4px;overflow-wrap:anywhere}
      .metric strong{display:block;font-size:13px;line-height:1.35;overflow-wrap:anywhere}

      :host([fitness-motion]) .recovery-score-readiness .recovery-score-track i{transform-origin:left center;animation:fitness-readiness-breathe 3.8s cubic-bezier(.4,0,.2,1) infinite;will-change:filter,transform}
      :host([fitness-motion]) .recovery-score-progress .recovery-score-track{position:relative;overflow:hidden}
      :host([fitness-motion]) .recovery-score-progress .recovery-score-track i{position:relative;animation:fitness-recovery-flow 5.2s ease-in-out infinite;will-change:filter,transform}
      :host([fitness-motion]) .recovery-score-progress .recovery-score-track i::after{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent 0%,rgba(255,255,255,.48) 48%,transparent 72%);transform:translateX(-140%);animation:fitness-recovery-sheen 3.1s ease-in-out infinite}
      @keyframes fitness-readiness-breathe{0%,100%{transform:scaleY(.82);filter:brightness(.96)}45%{transform:scaleY(1.32);filter:brightness(1.22)}62%{transform:scaleY(1.04);filter:brightness(1.08)}}
      @keyframes fitness-recovery-flow{0%,100%{transform:translateX(0) scaleY(.9);filter:saturate(.92)}50%{transform:translateX(1.5px) scaleY(1.22);filter:saturate(1.2) brightness(1.12)}}
      @keyframes fitness-recovery-sheen{0%,18%{transform:translateX(-140%);opacity:0}45%{opacity:.85}72%,100%{transform:translateX(180%);opacity:0}}
      @media(prefers-reduced-motion:reduce){:host([fitness-motion]) .recovery-score-track i,:host([fitness-motion]) .recovery-score-track i::after{animation:none!important}}
      @media(max-width:520px){
        .readiness-panel{grid-template-columns:88px minmax(0,1fr);gap:12px;padding:14px}
        .readiness-ring{width:82px;height:82px}
        .readiness-ring>div{width:60px;height:60px}
        .readiness-ring strong{font-size:24px;line-height:60px}
        .readiness-copy strong{font-size:21px}
        .recovery-grid{grid-template-columns:1fr}
        .components{grid-template-columns:1fr}
      }
      @media(max-width:350px){
        .readiness-panel{grid-template-columns:1fr;text-align:center}
        .readiness-ring{margin:auto}
      }
    </style>`;
  }

  _sleepScoreMetric(label, state, entityId = "") {
    const value = _fitnessNumber(state?.state);
    const display = value == null ? "—" : `${Math.max(0, Math.min(100, value)).toFixed(0)}%`;
    return `<div class="metric sleep-score entity-link" data-more-info="${_fitnessEscape(entityId)}"><span>${_fitnessEscape(label)}</span><strong>${display}</strong></div>`;
  }

  _metric(label, state, sleepDuration = false, entityId = "") {
    const value = sleepDuration ? _fitnessSleepDuration(state) : _fitnessDisplay(state, 1);
    return `<div class="metric entity-link" data-more-info="${_fitnessEscape(entityId)}"><span>${_fitnessEscape(label)}</span><strong>${_fitnessEscape(value)}</strong></div>`;
  }
}

class FitnessTrainingAdaptationCard extends FitnessAutoProfileCard {
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const e = this._profile?.entities || {};
    const l = this._profile?.labels || {};
    const entityId = e.training_adaptation_status;
    const state = entityId ? this._hass.states[entityId] : null;
    if (!state) {
      this.shadowRoot.innerHTML = "";
      return;
    }

    const status = String(_fitnessAttr(state, "status") || "insufficient_data");
    const tones = {
      productive: ["#2e7d32", "mdi:trending-up"],
      maintaining: ["#00897b", "mdi:equal"],
      insufficient_stimulus: ["#5c6bc0", "mdi:signal-cellular-1"],
      absent: ["#78909c", "mdi:power-sleep"],
      high_load: ["#f9a825", "mdi:chart-bell-curve-cumulative"],
      excessive: ["#ef6c00", "mdi:alert"],
      strained: ["#d84315", "mdi:heart-pulse"],
      unproductive: ["#c62828", "mdi:trending-down"],
      insufficient_data: ["#78909c", "mdi:help-circle-outline"],
    };
    const [tone, icon] = tones[status] || tones.insufficient_data;

    const ratio = _fitnessNumber(_fitnessAttr(state, "recent_to_baseline_load_ratio"));
    const vo2 = _fitnessNumber(_fitnessAttr(state, "vo2max_slope_percent_per_30d"));
    const hrv = _fitnessNumber(_fitnessAttr(state, "hrv_7d_vs_baseline_percent"));
    const rhr = _fitnessNumber(_fitnessAttr(state, "resting_hr_vs_28d_bpm"));
    const readiness = _fitnessNumber(_fitnessAttr(state, "readiness_score"));
    const evidence = _fitnessNumber(_fitnessAttr(state, "evidence_count"));
    const stateUnavailable = ["unknown", "unavailable", "none", "null", ""].includes(String(state.state || "").toLowerCase());
    const hasAdaptationInformation = !stateUnavailable && (
      status !== "insufficient_data"
      || [ratio, vo2, hrv, rhr, readiness].some((value) => value != null)
      || (evidence != null && evidence > 0)
    );
    if (!hasAdaptationInformation) {
      this.shadowRoot.innerHTML = "";
      return;
    }

    const recoveryBits = [];
    if (hrv != null) recoveryBits.push(`HRV ${hrv >= 0 ? "+" : ""}${hrv.toFixed(1)}%`);
    if (rhr != null) recoveryBits.push(`RHR ${rhr >= 0 ? "+" : ""}${rhr.toFixed(1)} bpm`);
    if (readiness != null) recoveryBits.push(`${readiness.toFixed(0)}/100`);

    this.shadowRoot.innerHTML = `<ha-card style="--adapt:${tone}">
      <div class="hero entity-link" data-more-info="${_fitnessEscape(entityId || "")}">
        <div class="icon"><ha-icon icon="${icon}"></ha-icon></div>
        <div class="copy">
          <small>${_fitnessEscape(l.training_adaptation_card)}</small>
          <strong>${_fitnessEscape(state.state)}</strong>
          <span>${_fitnessEscape(l.training_adaptation_subtitle)}</span>
        </div>
      </div>
      <div class="metrics entity-link" data-more-info="${_fitnessEscape(entityId || "")}">
        <div><span>${_fitnessEscape(l.adaptation_load_ratio)}</span><strong>${ratio == null ? "—" : `${ratio.toFixed(2)}×`}</strong></div>
        <div><span>${_fitnessEscape(l.adaptation_fitness_trend)}</span><strong>${vo2 == null ? "—" : `${vo2 >= 0 ? "+" : ""}${vo2.toFixed(1)}% / 30d`}</strong></div>
        <div><span>${_fitnessEscape(l.adaptation_recovery_signal)}</span><strong>${_fitnessEscape(recoveryBits.length ? recoveryBits.join(" · ") : "—")}</strong></div>
      </div>
      ${evidence != null ? `<div class="evidence">${_fitnessEscape(l.adaptation_evidence)}: ${evidence.toFixed(0)}</div>` : ""}
    </ha-card><style>
      ha-card{padding:18px;overflow:hidden;border-left:4px solid var(--adapt)}
      .entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}
      .hero{display:grid;grid-template-columns:58px minmax(0,1fr);gap:14px;align-items:center;padding:14px;border-radius:18px;background:linear-gradient(135deg,color-mix(in srgb,var(--adapt) 18%,var(--card-background-color)),var(--secondary-background-color))}
      .icon{width:54px;height:54px;border-radius:16px;display:grid;place-items:center;background:color-mix(in srgb,var(--adapt) 18%,transparent);color:var(--adapt)}
      .icon ha-icon{--mdc-icon-size:30px}
      .copy{min-width:0}.copy small{display:block;color:var(--secondary-text-color);font-size:11px}.copy strong{display:block;color:var(--adapt);font-size:25px;line-height:1.15;margin:3px 0;overflow-wrap:anywhere}.copy span{display:block;color:var(--secondary-text-color);font-size:11px;line-height:1.35;overflow-wrap:anywhere}
      .metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}.metrics>div{min-width:0;padding:10px;border-radius:12px;background:var(--secondary-background-color);overflow:hidden}.metrics span{display:block;color:var(--secondary-text-color);font-size:10px;line-height:1.3;margin-bottom:4px;overflow-wrap:anywhere}.metrics strong{display:block;font-size:13px;line-height:1.35;overflow-wrap:anywhere}
      .evidence{margin-top:8px;color:var(--secondary-text-color);font-size:10px;text-align:right}
      @media(max-width:480px){.metrics{grid-template-columns:1fr}.copy strong{font-size:22px}}
    </style>`;
  }
}

class FitnessTrainingLoadCard extends FitnessAutoProfileCard {
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const e = this._profile?.entities || {};
    const l = this._profile?.labels || {};
    const load = e.training_load ? this._hass.states[e.training_load] : null;
    const adaptation = e.training_adaptation_status ? this._hass.states[e.training_adaptation_status] : null;
    if (!load) {
      this.shadowRoot.innerHTML = "";
      return;
    }

    const recent = _fitnessNumber(load.state);
    const baseline = _fitnessNumber(_fitnessAttr(load, "baseline_28d_weekly_equivalent"));
    const ratio = _fitnessNumber(_fitnessAttr(load, "recent_to_baseline_ratio"));
    const workouts7 = _fitnessNumber(_fitnessAttr(load, "workouts_7d"));
    const days7 = _fitnessNumber(_fitnessAttr(load, "active_days_7d"));
    const mins7 = _fitnessNumber(_fitnessAttr(load, "workout_minutes_7d"));

    const adaptationStatus = String(_fitnessAttr(adaptation, "status") || "insufficient_data");
    const baselineReliable = adaptation
      ? Boolean(_fitnessAttr(adaptation, "baseline_reliable"))
      : (ratio != null && baseline != null && baseline > 0);

    let zone = "building";
    if (baselineReliable && ratio != null) {
      if (ratio < 0.70) zone = "low";
      else if (ratio <= 1.30) zone = "balanced";
      else if (ratio <= 1.60) zone = "elevated";
      else if (ratio <= 2.00) zone = "high";
      else zone = "excessive";
    }

    const zoneText = {
      building: l.baseline_building,
      low: l.load_low,
      balanced: l.load_balanced,
      elevated: l.load_elevated,
      high: l.load_high,
      excessive: l.load_excessive,
    }[zone];

    const position = !baselineReliable || ratio == null
      ? 50
      : Math.max(1, Math.min(99, (ratio / 2.4) * 100));

    const adaptationLabel = adaptation?.state || "";
    const adaptationEvidence = _fitnessNumber(_fitnessAttr(adaptation, "evidence_count"));
    const adaptationVo2 = _fitnessNumber(_fitnessAttr(adaptation, "vo2max_slope_percent_per_30d"));
    const adaptationHrv = _fitnessNumber(_fitnessAttr(adaptation, "hrv_7d_vs_baseline_percent"));
    const adaptationReadiness = _fitnessNumber(_fitnessAttr(adaptation, "readiness_score"));
    const hasLoadData = Boolean(
      baselineReliable
      && recent != null && recent > 0
      && baseline != null && baseline > 0
      && ratio != null && ratio > 0
      && workouts7 != null && workouts7 >= 2
    );
    const hasAdaptationData = Boolean(
      hasLoadData
      && adaptation
      && adaptationStatus !== "insufficient_data"
      && adaptationEvidence != null
      && adaptationEvidence >= 3
    );
    if (!hasLoadData) {
      this.shadowRoot.innerHTML = "";
      return;
    }
    const adaptationTones = {
      productive:"#2e7d32", maintaining:"#00897b",
      insufficient_stimulus:"#5c6bc0", absent:"#78909c",
      high_load:"#f9a825", excessive:"#ef6c00",
      strained:"#d84315", unproductive:"#c62828",
      insufficient_data:"#78909c",
    };
    const adaptationTone = adaptationTones[adaptationStatus] || adaptationTones.insufficient_data;
    const entityId = e.training_load || "";
    const loadMetrics = [
      ["TRIMP 7d", recent, value => value.toFixed(1)],
      [l.baseline_load, baseline, value => value.toFixed(1)],
      [l.workouts_7d, workouts7, value => value.toFixed(0)],
      [l.active_days_7d, days7, value => value.toFixed(0)],
      [l.training_minutes_7d, mins7, value => `${Math.round(value)} min`],
    ].filter(([, value]) => value != null).map(([label, value, formatter]) =>
      `<div><span>${_fitnessEscape(label)}</span><strong>${formatter(value)}</strong></div>`
    ).join("");

    this.shadowRoot.innerHTML = `<ha-card>
      <div class="header">
        <div>
          <h3>${_fitnessEscape(l.training_load_snapshot)}</h3>
          ${hasAdaptationData ? `<div class="adapt-summary entity-link" style="--adapt:${adaptationTone}" data-more-info="${_fitnessEscape(e.training_adaptation_status || "")}">
            <div class="adapt-title"><span>${_fitnessEscape(l.training_adaptation_card)}</span><strong>${_fitnessEscape(adaptationLabel)}</strong></div>
            ${adaptationStatus === "insufficient_data"
              ? `<p>${_fitnessEscape(l.adaptation_building)}</p>`
              : `<div class="adapt-evidence">
                  <span>${_fitnessEscape(l.adaptation_baseline)} <b>${baselineReliable && ratio != null ? `${ratio.toFixed(2)}×` : "—"}</b></span>
                  <span>${_fitnessEscape(l.adaptation_fitness)} <b>${adaptationVo2 == null ? "—" : `${adaptationVo2 >= 0 ? "+" : ""}${adaptationVo2.toFixed(1)}%`}</b></span>
                  <span>${_fitnessEscape(l.adaptation_recovery)} <b>${adaptationReadiness == null ? "—" : `${adaptationReadiness.toFixed(0)}/100`}</b></span>
                </div>`}
            ${adaptationEvidence == null ? "" : `<small>${_fitnessEscape(l.adaptation_evidence)}: ${adaptationEvidence.toFixed(0)}</small>`}
          </div>` : ""}
        </div>
        ${ratio != null ? `<div class="ratio ${zone}">${ratio.toFixed(2)}×</div>` : ""}
      </div>

      ${baselineReliable && ratio != null ? `<div class="load-scale entity-link" data-more-info="${_fitnessEscape(entityId)}"><div class="scale"></div><i style="left:${position}%"></i></div><div class="load-scale-values"><span>0×</span><b>${ratio.toFixed(2)}×</b><span>2.40×</span></div>` : ""}

      ${ratio != null ? `<div class="status-row"><div><span>${_fitnessEscape(l.load_ratio)}</span><strong class="${zone}">${_fitnessEscape(zoneText)}</strong></div>${!baselineReliable ? `<p>${_fitnessEscape(l.baseline_building_hint)}</p>` : ""}</div>` : ""}

      ${loadMetrics ? `<div class="metrics entity-link" data-more-info="${_fitnessEscape(entityId)}">${loadMetrics}</div>` : ""}
    </ha-card><style>
      ha-card{padding:16px;overflow:hidden}
      .entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}
      .header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
      h3{margin:0;font-size:20px;line-height:1.2}
      .adapt-summary{margin-top:9px;padding:9px 10px;border-radius:12px;background:linear-gradient(135deg,color-mix(in srgb,var(--adapt) 12%,transparent),var(--secondary-background-color));border-left:3px solid var(--adapt);max-width:560px;min-width:0}
      .adapt-title{display:flex;align-items:center;justify-content:space-between;gap:10px;min-width:0}.adapt-title span{font-size:10px;color:var(--secondary-text-color)}.adapt-title strong{font-size:12px;color:var(--adapt);overflow-wrap:anywhere;text-align:right}
      .adapt-summary p{margin:6px 0 0;font-size:9px;line-height:1.35;color:var(--secondary-text-color);overflow-wrap:anywhere}
      .adapt-evidence{display:flex;flex-wrap:wrap;gap:5px 10px;margin-top:6px}.adapt-evidence span{font-size:9px;color:var(--secondary-text-color)}.adapt-evidence b{color:var(--primary-text-color);font-weight:650}
      .adapt-summary small{display:block;margin-top:5px;font-size:8px;color:var(--secondary-text-color)}
      .ratio{font-size:21px;font-weight:750;white-space:nowrap}
      .ratio.building{color:var(--secondary-text-color)}.ratio.low{color:#42a5f5}.ratio.balanced{color:#43a047}.ratio.elevated{color:#c0ca33}.ratio.high{color:#fb8c00}.ratio.excessive{color:#e53935}
      .load-scale{position:relative;margin-top:14px;height:16px;padding:3px 0}
      .scale{height:9px;border-radius:999px;background:linear-gradient(90deg,#42a5f5 0%,#26c6da 16%,#43a047 34%,#c0ca33 52%,#fdd835 66%,#fb8c00 80%,#e53935 100%)}
      .load-scale i{position:absolute;top:0;width:4px;height:16px;border-radius:3px;background:var(--primary-text-color);box-shadow:0 0 0 1px var(--card-background-color);transform:translateX(-2px)}.load-scale-values{display:grid;grid-template-columns:1fr auto 1fr;margin-top:2px;font-size:9px;color:var(--secondary-text-color)}.load-scale-values span:last-child{text-align:right}.load-scale-values b{color:var(--primary-text-color);font-weight:650}
      .status-row{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-top:7px}
      .status-row>div{min-width:0}.status-row span{display:block;font-size:10px;color:var(--secondary-text-color)}.status-row strong{display:block;font-size:13px;margin-top:2px}
      .status-row strong.building{color:var(--secondary-text-color)}.status-row strong.low{color:#42a5f5}.status-row strong.balanced{color:#43a047}.status-row strong.elevated{color:#c0ca33}.status-row strong.high{color:#fb8c00}.status-row strong.excessive{color:#e53935}
      .status-row p{margin:0;max-width:55%;font-size:9px;line-height:1.35;color:var(--secondary-text-color);text-align:right;overflow-wrap:anywhere}
      .metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:13px}
      .metrics>div{min-width:0;padding:10px;border-radius:12px;background:var(--secondary-background-color)}
      .metrics>div:nth-child(n+3){grid-column:auto}
      .metrics span{display:block;font-size:10px;line-height:1.3;color:var(--secondary-text-color);overflow-wrap:anywhere;margin-bottom:4px}
      .metrics strong{font-size:15px;line-height:1.2;overflow-wrap:anywhere}
      @media(min-width:540px){.metrics{grid-template-columns:repeat(6,minmax(0,1fr))}.metrics>div:nth-child(1),.metrics>div:nth-child(2){grid-column:span 3}.metrics>div:nth-child(n+3){grid-column:span 2}}
      @media(max-width:390px){.header{align-items:center}.adapt{display:flex}.status-row{display:block}.status-row p{max-width:none;text-align:left;margin-top:7px}.metrics{grid-template-columns:1fr 1fr}.metrics>div:last-child{grid-column:1/-1}}
    </style>`;
  }
}

class FitnessCompositeCard extends FitnessAutoProfileCard {
  setConfig(config) {
    super.setConfig(config);
    this._compositeBuilt = false;
    this._compositeChildren = [];
    this._compositeSignatureValue = null;
    this._compositeLanguage = null;
  }

  set hass(hass) {
    this._hass = hass;
    const key = this.config?.profile_entry_id || "";
    const language = String(this._profile?.language || hass?.language || "en").toLowerCase().split("-")[0];

    if (key !== this._resolvedKey && !this._resolving) {
      this._resolvedKey = key;
      this._resolveProfile();
      return;
    }

    // UI-language changes are rare and are the one case where rebuilding the
    // card is desirable because headings/labels really changed.
    if (this._profile?.labels_by_language && language !== this._compositeLanguage) {
      this._compositeLanguage = language;
      this._profile = {
        ...this._profile,
        labels:
          this._profile.labels_by_language[language]
          || this._profile.labels_by_language.en
          || this._profile.labels,
      };
      this._compositeBuilt = false;
    }

    if (!this._profile) return;

    const signature = this._compositeSignature();
    if (!this._compositeBuilt) {
      this._compositeSignatureValue = signature;
      this._render();
      return;
    }

    // Do absolutely nothing for unrelated Home Assistant state changes.
    if (signature === this._compositeSignatureValue) return;
    this._compositeSignatureValue = signature;

    // Keep the existing nodes alive: this prevents maps, SVGs, OSM tiles and
    // child cards from visually blinking when their values update.
    for (const child of this._compositeChildren || []) {
      child.hass = hass;
    }
  }

  _relevantEntityKeys() {
    return [];
  }

  _extraSignatureParts() {
    return [];
  }

  _compositeSignature() {
    const e = this._profile?.entities || {};
    const parts = [];
    for (const key of this._relevantEntityKeys()) {
      const id = e[key];
      const state = id ? this._hass?.states?.[id] : null;
      if (!id || !state) {
        parts.push(`${key}:`);
        continue;
      }
      let attrs = "";
      // Attributes can contain the actual evaluated context while the state
      // remains stable, so include them only for Fitness entities used here.
      try { attrs = JSON.stringify(state.attributes || {}); } catch (_err) {}
      parts.push(`${key}:${state.state}:${state.last_updated || ""}:${attrs}`);
    }
    parts.push(...this._extraSignatureParts());
    return parts.join("|");
  }

  _mount(type, config = {}) {
    const el = document.createElement(type);
    el.setConfig({
      profile_entry_id: this._profile?.entry_id,
      embedded: true,
      ...config,
    });
    el.hass = this._hass;
    return el;
  }

  _shell(title, icon, children, accent = "var(--primary-color)") {
    this.shadowRoot.innerHTML = `<ha-card style="--fitness-card-accent:${accent}">
      <div class="composite-head">
        <div class="composite-icon"><ha-icon icon="${icon}"></ha-icon></div>
        <strong>${_fitnessEscape(title)}</strong>
      </div>
      <div class="composite-body"></div>
    </ha-card><style>
      ha-card{
        padding:8px;overflow:hidden;
        box-shadow:none;
        border:0;
        background:var(--ha-card-background,var(--card-background-color))
      }
      .composite-head{
        display:flex;align-items:center;gap:8px;min-width:0;
        margin:0 0 6px;padding:3px 4px;font-size:15px
      }
      .composite-head strong{min-width:0;line-height:1.2;overflow-wrap:anywhere}
      .composite-icon{
        width:30px;height:30px;flex:0 0 30px;border-radius:9px;display:grid;place-items:center;
        color:var(--fitness-card-accent);
        background:color-mix(in srgb,var(--fitness-card-accent) 12%,transparent)
      }
      .composite-icon ha-icon{--mdc-icon-size:18px}
      .composite-body{
        display:grid;gap:7px;
        padding:0;
        background:transparent
      }
      .composite-body>*{
        --ha-card-background:transparent;
        --ha-card-border-width:0px;
        --ha-card-box-shadow:none
      }
      .modal-actions,.settings-actions{display:flex!important;align-items:center;gap:8px;flex-wrap:nowrap!important;min-width:0}.modal-actions>button,.settings-actions>button{flex:1 1 0;min-width:0;max-width:100%}.modal-actions>button span,.settings-actions>button span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      @media(prefers-reduced-motion:reduce){.heart-orb,.heart-orb::after,.run-orb i{animation:none!important}}
      @media(max-width:420px){
        ha-card{padding:7px}
        .composite-head{font-size:14px;margin-bottom:5px}
        .composite-icon{width:28px;height:28px;flex-basis:28px}
        .composite-body{padding:0}
      }
    </style>`;
    const body = this.shadowRoot.querySelector(".composite-body");
    this._compositeChildren = children.filter(Boolean);
    for (const child of this._compositeChildren) body.appendChild(child);
    this._compositeBuilt = true;
    this._compositeLanguage = String(this._profile?.language || this._hass?.language || "en").toLowerCase().split("-")[0];
    this._compositeSignatureValue = this._compositeSignature();
  }
}

class FitnessLiveWorkoutCard extends FitnessAutoProfileCard {
  set hass(hass) {
    this._hass = hass;
    const key = this.config?.profile_entry_id || "";
    if (key !== this._resolvedKey && !this._resolving) {
      this._resolvedKey = key;
      this._liveRenderSignature = null;
      this._resolveProfile();
      return;
    }
    if (!this._profile) {
      this._render();
      return;
    }
    const signature = this._liveStateSignature(hass);
    if (signature === this._liveRenderSignature) return;
    this._liveRenderSignature = signature;
    this._render();
  }

  _liveStateSignature(hass) {
    const entities = {
      ...(this._profile?.entities || {}),
      ..._fitnessProfileDataEntities(this._profile, hass, "live"),
    };
    const parts = [String(this._profile?.language || hass?.language || "")];
    for (const key of this._relevantEntityKeys()) {
      const entityId = entities[key];
      const state = entityId ? hass?.states?.[entityId] : null;
      parts.push(`${key}:${entityId || ""}:${state?.state || ""}:${state?.last_updated || ""}`);
    }
    for (const item of this._profile?.live_sensor_metrics || []) {
      const state = item?.entity_id ? hass?.states?.[item.entity_id] : null;
      const owner = item?.owner_entity_id ? hass?.states?.[item.owner_entity_id] : null;
      parts.push(`sensor:${item?.entity_id || ""}:${state?.state || ""}:${state?.last_updated || ""}:${owner?.attributes?.owner_entry_id || ""}:${owner?.last_updated || ""}`);
    }
    return parts.join("|");
  }

  _relevantEntityKeys() {
    return this._profile?.live_entity_keys || [
      "session_status","session_duration","current_heart_rate","current_power",
      "current_cadence","current_speed","current_pace","current_distance",
      "start_workout","pause_workout","resume_workout","stop_workout",
    ];
  }

  _render() {
    if (!this.shadowRoot || !this._hass || !this._profile) return;
    const e = {
      ...(this._profile.entities || {}),
      ..._fitnessProfileDataEntities(this._profile, this._hass, "live"),
    };
    const l = this._profile.labels || {};
    const sessionEntityId = e.session_status;
    const rawSessionState = sessionEntityId ? String(this._hass.states?.[sessionEntityId]?.state || "") : "";
    const sessionState = ["waiting_for_live_data", "active", "paused", "recovery"].includes(rawSessionState)
      ? rawSessionState
      : "idle";
    const controlKeys = ["start_workout","pause_workout","resume_workout","stop_workout"];
    const liveKeys = this._profile.live_entity_keys || [];
    const metricKeys = liveKeys.length
      ? liveKeys.filter((key) => !controlKeys.includes(key) && key !== "workout_room")
      : [
          "session_status","session_duration","current_heart_rate","current_power",
          "current_cadence","current_speed","current_pace","current_distance",
        ];
    const metrics = metricKeys.map((key) => {
      const id = e[key];
      const state = id ? this._hass.states[id] : null;
      if (!id || !state || ["unavailable","unknown"].includes(state.state)) return "";
      const display = key === "session_status"
        ? (l[`session_status_${state.state}`] || String(state.state).replaceAll("_", " "))
        : _fitnessDisplay(state,1);
      return `<div class="live-metric entity-link" data-more-info="${_fitnessEscape(id)}"><span>${_fitnessEscape(entityName(this._hass,id))}</span><strong>${_fitnessEscape(display)}</strong></div>`;
    }).filter(Boolean);
    const canonicalMetricEntities = new Set(metricKeys.map((key) => e[key]).filter(Boolean));
    const sensorMetrics = (this._profile.live_sensor_metrics || []).map((item) => {
      const id = String(item?.entity_id || "");
      if (!id || canonicalMetricEntities.has(id)) return "";
      const ownerState = item?.owner_entity_id ? this._hass.states[item.owner_entity_id] : null;
      const ownerEntryId = String(ownerState?.attributes?.owner_entry_id || "");
      if (ownerEntryId && ownerEntryId !== String(this._profile.entry_id || "")) return "";
      const state = this._hass.states[id];
      if (!state || ["unavailable","unknown"].includes(state.state)) return "";
      const numeric = Number(state.state);
      if (!Number.isFinite(numeric) || Math.abs(numeric) < 1e-9) return "";
      return `<div class="live-metric live-sensor-metric entity-link" data-more-info="${_fitnessEscape(id)}"><span>${_fitnessEscape(entityName(this._hass,id))}</span><strong>${_fitnessEscape(_fitnessDisplay(state,1))}</strong></div>`;
    }).filter(Boolean);
    const allMetrics = [...metrics, ...sensorMetrics].join("");

    const heartState = e.current_heart_rate ? this._hass.states[e.current_heart_rate] : null;
    const heartRate = Number(heartState?.state);
    const heartVisual = Number.isFinite(heartRate) && heartRate > 0
      ? `<div class="live-motion-card live-heart" style="--heart-beat:${Math.max(.34,Math.min(1.5,60/heartRate)).toFixed(3)}s"><span class="heart-orb"><ha-icon icon="mdi:heart-pulse"></ha-icon></span><span><small>${_fitnessEscape(entityName(this._hass,e.current_heart_rate))}</small><strong>${_fitnessEscape(_fitnessDisplay(heartState,0))}</strong></span></div>`
      : "";
    const speedState = e.current_speed ? this._hass.states[e.current_speed] : null;
    const speedValue = Number(speedState?.state);
    const runVisual = Number.isFinite(speedValue) && speedValue > 0
      ? `<div class="live-motion-card live-speed" style="--run-flow:${Math.max(.34,Math.min(2.3,3.2/Math.max(.35,speedValue))).toFixed(3)}s"><span class="run-orb"><ha-icon icon="mdi:run-fast"></ha-icon><i></i><i></i><i></i></span><span><small>${_fitnessEscape(entityName(this._hass,e.current_speed))}</small><strong>${_fitnessEscape(_fitnessDisplay(speedState,1))}</strong></span></div>`
      : "";
    const motion = heartVisual || runVisual ? `<div class="live-motion">${heartVisual}${runVisual}</div>` : "";
    const controls = controlKeys.map((key) => {
      const id = e[key];
      const state = id ? this._hass.states[id] : null;
      if (!id || !state || state.state === "unavailable") return "";
      return `<button class="live-control" data-entity="${_fitnessEscape(id)}"><ha-icon icon="${
        key === "start_workout" ? "mdi:play" : key === "pause_workout" ? "mdi:pause" : key === "resume_workout" ? "mdi:play-pause" : "mdi:stop"
      }"></ha-icon><span>${_fitnessEscape(entityName(this._hass,id))}</span></button>`;
    }).filter(Boolean).join("");

    this.shadowRoot.innerHTML = `<ha-card data-session-state="${sessionState}">
      <div class="live-head"><ha-icon icon="mdi:run-fast"></ha-icon><div><strong>${_fitnessEscape(this.config.title || l.live || l.current)}</strong><span>${_fitnessEscape(this._profile.profile_name || "")}</span></div></div>
      ${motion}
      <div class="live-grid">${allMetrics || `<div class="live-empty">${_fitnessEscape(l.no_live_data)}</div>`}</div>
      ${controls ? `<div class="live-controls">${controls}</div>` : ""}
    </ha-card><style>
      ha-card{
        --fitness-card-accent:var(--success-color,#43a047);
        padding:10px;overflow:hidden;box-shadow:none;border:0;border-radius:20px;
        background:var(--secondary-background-color);transition:background .32s ease,color .22s ease
      }
      ha-card[data-session-state="waiting_for_live_data"]{--fitness-card-accent:#42a5f5;background:linear-gradient(135deg,color-mix(in srgb,#42a5f5 17%,var(--secondary-background-color)),var(--secondary-background-color))}
      ha-card[data-session-state="active"]{background:linear-gradient(135deg,color-mix(in srgb,var(--fitness-card-accent) 24%,var(--secondary-background-color)),var(--secondary-background-color))}
      ha-card[data-session-state="paused"]{--fitness-card-accent:#ff9800;background:linear-gradient(135deg,color-mix(in srgb,#ff9800 19%,var(--secondary-background-color)),var(--secondary-background-color))}
      ha-card[data-session-state="recovery"]{--fitness-card-accent:#26a69a;background:linear-gradient(135deg,color-mix(in srgb,#26a69a 19%,var(--secondary-background-color)),var(--secondary-background-color))}
      .live-grid,.live-controls{padding:0;background:transparent}
      .live-motion{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:6px;margin:0 0 6px}
      .live-motion-card{display:grid;grid-template-columns:38px minmax(0,1fr);align-items:center;gap:8px;padding:7px 9px;border-radius:12px;background:color-mix(in srgb,var(--fitness-card-accent) 7%,var(--card-background-color));border:1px solid color-mix(in srgb,var(--fitness-card-accent) 18%,var(--divider-color));overflow:hidden}
      .live-motion-card>span:last-child{min-width:0}.live-motion-card small,.live-motion-card strong{display:block}.live-motion-card small{font-size:9px;color:var(--secondary-text-color);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.live-motion-card strong{font-size:15px;margin-top:1px}.heart-orb,.run-orb{position:relative;width:34px;height:34px;display:grid;place-items:center;border-radius:50%;color:var(--fitness-card-accent);background:color-mix(in srgb,var(--fitness-card-accent) 14%,transparent)}
      .heart-orb{animation:fitness-heart-beat var(--heart-beat,.75s) ease-in-out infinite}.heart-orb::after{content:"";position:absolute;inset:-2px;border-radius:50%;border:1px solid color-mix(in srgb,var(--fitness-card-accent) 55%,transparent);animation:fitness-heart-ring var(--heart-beat,.75s) ease-out infinite}.heart-orb ha-icon,.run-orb ha-icon{--mdc-icon-size:21px;z-index:2}@keyframes fitness-heart-beat{0%,100%{transform:scale(.92)}18%{transform:scale(1.12)}34%{transform:scale(.97)}48%{transform:scale(1.06)}68%{transform:scale(.94)}}@keyframes fitness-heart-ring{0%{transform:scale(.78);opacity:.7}78%,100%{transform:scale(1.42);opacity:0}}
      .run-orb{overflow:hidden}.run-orb i{position:absolute;left:-12px;width:18px;height:1px;background:currentColor;opacity:.3;animation:fitness-run-flow var(--run-flow,1s) linear infinite}.run-orb i:nth-of-type(1){top:9px}.run-orb i:nth-of-type(2){top:17px;animation-delay:-.22s}.run-orb i:nth-of-type(3){top:25px;animation-delay:-.44s}@keyframes fitness-run-flow{from{transform:translateX(-4px);opacity:0}25%{opacity:.55}to{transform:translateX(52px);opacity:0}}
      .live-sensor-metric{border:1px solid color-mix(in srgb,var(--fitness-card-accent) 14%,var(--divider-color))}
      .entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}
      .live-head{display:flex;align-items:center;gap:8px;margin:0 0 6px;padding:3px 4px;min-width:0}
      .live-head>ha-icon{
        width:30px;height:30px;padding:6px;box-sizing:border-box;border-radius:9px;
        color:var(--fitness-card-accent);--mdc-icon-size:18px;
        background:color-mix(in srgb,var(--fitness-card-accent) 12%,transparent)
      }
      .live-head>div{min-width:0}.live-head strong{display:block;font-size:15px;line-height:1.2;overflow-wrap:anywhere}.live-head span{display:block;color:var(--secondary-text-color);font-size:10px;margin-top:1px;overflow-wrap:anywhere}
      .live-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:6px}
      .live-metric{min-width:0;padding:8px 9px;border-radius:10px;background:var(--card-background-color);overflow:hidden}
      .live-metric span{display:block;color:var(--secondary-text-color);font-size:9px;line-height:1.25;overflow-wrap:anywhere}
      .live-metric strong{display:block;font-size:14px;line-height:1.2;margin-top:2px;overflow-wrap:anywhere}
      .live-empty{grid-column:1/-1;color:var(--secondary-text-color);padding:8px 2px}
      .live-controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:6px;margin-top:6px}
      .live-control{
        appearance:none;border:1px solid color-mix(in srgb,var(--fitness-card-accent) 25%,var(--divider-color));
        background:var(--card-background-color);
        color:var(--primary-text-color);border-radius:10px;min-height:38px;padding:6px 8px;
        display:flex;align-items:center;justify-content:center;gap:6px;font:inherit;cursor:pointer;min-width:0
      }
      .live-control ha-icon{color:var(--fitness-card-accent);--mdc-icon-size:18px}
      .live-control span{display:block;min-width:0;max-width:100%;font-size:clamp(10px,2.8vw,11px);font-weight:600;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;word-break:normal;overflow-wrap:normal}
      .live-control:active{transform:scale(.98)}.live-control.pending{opacity:.65}.live-control.pressed{box-shadow:0 0 0 2px color-mix(in srgb,var(--fitness-card-accent) 55%,transparent)}.live-control.failed{border-color:var(--error-color,#db4437);color:var(--error-color,#db4437)}
      @media(max-width:420px){
        ha-card{padding:7px}
        .live-grid,.live-controls{grid-template-columns:1fr 1fr;padding:0}
        .live-head>ha-icon{width:28px;height:28px}
      }
    </style>`;
    for (const metric of this.shadowRoot.querySelectorAll(".live-metric[data-more-info]")) {
      metric.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        _fitnessOpenMoreInfo(this, metric.dataset.moreInfo);
      });
    }
    for (const button of this.shadowRoot.querySelectorAll(".live-control")) {
      button.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        const entityId = button.dataset.entity;
        if (!entityId || button.disabled || !this._hass) return;
        button.disabled = true;
        button.classList.add("pending");
        try {
          if (typeof this._hass.callService === "function") {
            await this._hass.callService("button", "press", {}, {entity_id:entityId});
          } else {
            await this._hass.callWS({
              type:"call_service",
              domain:"button",
              service:"press",
              target:{entity_id:entityId},
            });
          }
          button.classList.add("pressed");
          setTimeout(() => button.classList.remove("pressed"), 500);
        } catch (err) {
          console.error("HA-Fitness live control failed", entityId, err);
          button.classList.add("failed");
          setTimeout(() => button.classList.remove("failed"), 1200);
        } finally {
          button.classList.remove("pending");
          button.disabled = false;
        }
      });
    }
  }
}

class FitnessWorkoutRpeCard extends FitnessAutoProfileCard {
  _relevantEntityKeys() {
    return ["session_rpe","last_workout_session_rpe_load","last_workout_rpe_load_vs_baseline"];
  }

  _render() {
    if (!this.shadowRoot || !this._hass || !this._profile) return;
    const e = this._profile.entities || {};
    const l = this._profile.labels || {};
    const rpeId = e.session_rpe;
    const rpeState = rpeId ? this._hass.states[rpeId] : null;
    if (!rpeId || !rpeState || !this._profile?.latest_workout?.available) {
      this.shadowRoot.innerHTML = "";
      return;
    }

    const rpeValue = _fitnessNumber(rpeState.state);
    const loadState = e.last_workout_session_rpe_load ? this._hass.states[e.last_workout_session_rpe_load] : null;
    const compareState = e.last_workout_rpe_load_vs_baseline ? this._hass.states[e.last_workout_rpe_load_vs_baseline] : null;
    const load = _fitnessNumber(loadState?.state);
    const compare = _fitnessNumber(compareState?.state);
    const choices = Array.from({length:10}, (_,i) => i+1).map((value) =>
      `<button type="button" class="rpe-choice${Math.round(rpeValue || 0) === value ? " selected" : ""}" data-rpe="${value}" aria-label="${value}" style="--rpe-hue:${Math.round(205 - (value - 1) * (205 / 9))}">${value}</button>`
    ).join("");
    const meta = [
      load == null ? "" : `<span class="entity-link" data-more-info="${_fitnessEscape(e.last_workout_session_rpe_load || "")}"><ha-icon icon="mdi:chart-bell-curve-cumulative"></ha-icon>${_fitnessEscape(_fitnessDisplay(loadState,1))}</span>`,
      compare == null ? "" : `<span class="entity-link ${compare > 0 ? "up" : compare < 0 ? "down" : ""}" data-more-info="${_fitnessEscape(e.last_workout_rpe_load_vs_baseline || "")}"><ha-icon icon="mdi:compare-horizontal"></ha-icon>${compare > 0 ? "+" : ""}${compare.toFixed(0)}%</span>`,
    ].filter(Boolean).join("");

    this.shadowRoot.innerHTML = `<ha-card>
      <div class="head entity-link" data-more-info="${_fitnessEscape(rpeId)}"><div class="icon"><ha-icon icon="mdi:gauge"></ha-icon></div><div class="title"><strong>${_fitnessEscape(l.rpe_title)}</strong><span>${_fitnessEscape(l.rpe_hint)}</span></div><div class="score"><strong>${rpeValue == null ? "—" : Math.round(rpeValue)}</strong><span>/ 10</span></div></div>
      <div class="rpe-scale">${choices}</div>
      <div class="foot"><span>${_fitnessEscape(l.rpe_saved)}</span>${meta ? `<div class="meta">${meta}</div>` : ""}</div>
    </ha-card><style>
      ha-card{padding:14px 16px;overflow:hidden}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}ha-card{background:linear-gradient(135deg,color-mix(in srgb,var(--primary-color) 7%,var(--ha-card-background,var(--card-background-color))),var(--ha-card-background,var(--card-background-color)) 58%)}
      .head{display:grid;grid-template-columns:38px minmax(0,1fr) auto;gap:10px;align-items:center;min-width:0}.icon{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;background:color-mix(in srgb,var(--primary-color) 14%,transparent);color:var(--primary-color)}.icon ha-icon{--mdc-icon-size:22px}.title{min-width:0}.title strong{display:block;font-size:15px;line-height:1.25}.title span{display:block;margin-top:3px;color:var(--secondary-text-color);font-size:11px;line-height:1.35;overflow-wrap:break-word}.score{display:flex;align-items:baseline;gap:3px;white-space:nowrap}.score strong{font-size:25px;line-height:1}.score span{font-size:11px;color:var(--secondary-text-color)}
      .rpe-scale{display:grid;grid-template-columns:repeat(auto-fit,minmax(38px,1fr));gap:6px;margin-top:13px}.rpe-choice{appearance:none;border:1px solid hsl(var(--rpe-hue) 78% 52% / .38);border-radius:11px;min-height:40px;background:hsl(var(--rpe-hue) 78% 52% / .10);color:var(--primary-text-color);font:inherit;font-size:14px;font-weight:700;cursor:pointer;touch-action:manipulation;transition:transform .08s ease,background .15s ease,border-color .15s ease,box-shadow .15s ease}.rpe-choice:hover{border-color:hsl(var(--rpe-hue) 82% 52% / .82);background:hsl(var(--rpe-hue) 82% 52% / .22)}.rpe-choice:active{transform:scale(.95)}.rpe-choice.selected{border-color:hsl(var(--rpe-hue) 88% 48%);background:hsl(var(--rpe-hue) 88% 48%);color:#fff;box-shadow:0 0 0 1px hsl(var(--rpe-hue) 88% 48% / .35)}
      .foot{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-top:10px;min-width:0}.foot>span{min-width:0;color:var(--secondary-text-color);font-size:10px;line-height:1.35;overflow-wrap:break-word}.meta{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.meta span{display:flex;align-items:center;gap:3px;white-space:nowrap;font-size:10px;font-weight:600}.meta ha-icon{--mdc-icon-size:14px;color:var(--primary-color)}.meta .up{color:var(--success-color,#43a047)}.meta .down{color:var(--warning-color,#fb8c00)}
      @media(max-width:460px){.head{grid-template-columns:34px minmax(0,1fr) auto}.icon{width:34px;height:34px}.rpe-scale{grid-template-columns:repeat(5,minmax(0,1fr))}.foot{flex-direction:column}.meta{justify-content:flex-start}.title span{font-size:10px}}
    </style>`;

    for (const button of this.shadowRoot.querySelectorAll(".rpe-choice")) {
      button.addEventListener("click", async () => {
        if (!rpeId || button.disabled) return;
        const value = Number(button.dataset.rpe);
        if (!Number.isInteger(value) || value < 1 || value > 10) return;
        for (const item of this.shadowRoot.querySelectorAll(".rpe-choice")) item.disabled = true;
        button.classList.add("selected");
        try {
          await this._hass.callService("number", "set_value", {entity_id:rpeId, value});
        } finally {
          for (const item of this.shadowRoot.querySelectorAll(".rpe-choice")) item.disabled = false;
        }
      });
    }
  }
}

class FitnessWorkoutCard extends FitnessCompositeCard {
  _relevantEntityKeys() {
    return [
      "last_workout_hrr_60s","last_workout_banister_trimp",
      "last_workout_aerobic_efficiency","last_workout_aerobic_decoupling",
      "last_workout_efficiency_vs_baseline","last_workout_decoupling_vs_baseline",
      "last_workout_hr_vs_baseline","last_workout_power_vs_baseline",
      "last_workout_speed_vs_baseline","last_workout_trimp_vs_recent",
      "session_rpe","last_workout_session_rpe_load","last_workout_rpe_load_vs_baseline",
      "last_workout_fitness_aerobic_load","last_workout_fitness_high_intensity_load",
      "last_workout_strength_sets","last_workout_estimated_1rm","last_workout_strength_progression",
    ];
  }

  _extraSignatureParts() {
    const sourceSignature = _fitnessWorkoutSourceSignature(this._profile, this._hass);
    return [sourceSignature, ...(this._profile?.route_candidates || []).map((route) => {
      const state = this._hass?.states?.[route.entity_id];
      const value = state?.attributes?.[route.attribute];
      let encoded = "";
      try { encoded = JSON.stringify(value); } catch (_err) { encoded = String(value ?? ""); }
      return `route:${route.entity_id}:${route.attribute}:${encoded}`;
    })];
  }

  _render() {
    if (!this.shadowRoot || !this._hass || !this._profile) return;
    const l = this._profile.labels || {};
    const meaningful = (value) => {
      if (value === null || value === undefined) return false;
      const text = String(value).trim();
      if (!text || ["unknown","unavailable","none","null","nan"].includes(text.toLowerCase())) return false;
      const number = Number(text);
      return Number.isFinite(number) ? Math.abs(number) > 1e-9 : true;
    };
    const sourceRoutes = this._profile?.workout_source_metrics || {};
    const hasWorkout = Boolean(this._profile?.latest_workout?.available) || Object.values(sourceRoutes).some((route) => {
      if (!route || typeof route !== "object") return false;
      if (meaningful(route.value ?? route.configured_value)) return true;
      const state = route.entity_id ? this._hass.states?.[route.entity_id] : null;
      return meaningful(state?.state);
    });
    if (!hasWorkout) {
      this.shadowRoot.innerHTML = "";
      this._compositeChildren = [];
      this._compositeBuilt = true;
      this._compositeSignatureValue = this._compositeSignature();
      return;
    }
    const hasRoute = (this._profile.route_candidates || []).length > 0;
    const children = [this._mount("fitness-workout-highlights-card")];
    if (hasRoute) {
      children.push(this._mount("fitness-route-card", {height: Number(this.config.map_height || 330)}));
    }
    const e = this._profile.entities || {};
    if (e.session_rpe && this._profile?.latest_workout?.available) {
      children.push(this._mount("fitness-workout-rpe-card"));
    }
    if (["last_workout_efficiency_vs_baseline","last_workout_decoupling_vs_baseline","last_workout_power_vs_baseline","last_workout_speed_vs_baseline","last_workout_trimp_vs_recent"].some(k => e[k])) {
      children.push(this._mount("fitness-comparison-card"));
    }
    if (e.last_workout_strength_sets && this._hass.states[e.last_workout_strength_sets]?.attributes?.strength_analysis) {
      children.push(this._mount("fitness-strength-details-card"));
    }
    this._shell(this.config.title || l.latest_workout, "mdi:run", children, "var(--primary-color)");
  }
}

class FitnessSleepRecoveryCard extends FitnessCompositeCard {
  _relevantEntityKeys() {
    return [
      "readiness","sleep_consistency","sleep_deficit_7d","autonomic_recovery_trend",
      "heart_rate_recovery","estimated_recovery_time","training_recovery_relationship",
    ];
  }
  _extraSignatureParts() {
    return [_fitnessSourceMetricSignature(
      _fitnessProfileDataRoutes(
        this._profile, this._hass, "recovery", this._profile?.sleep_source_metrics || {}
      ),
      this._hass, "sleep-source"
    )];
  }

  _render() {
    if (!this.shadowRoot || !this._hass || !this._profile) return;
    const l = this._profile.labels || {};
    const e = this._profile.entities || {};
    const children = [];
    if (_fitnessUsableState(this._hass, e.readiness) || _fitnessUsableState(this._hass, e.estimated_recovery_time) || _fitnessUsableState(this._hass, e.autonomic_recovery_trend)) {
      children.push(this._mount("fitness-recovery-card"));
    }
    if (["last_sleep_light","last_sleep_deep","last_sleep_rem"].some(k => _fitnessSleepSourceMetric(this._profile, this._hass, k)?.canonicalValue != null)) {
      children.push(this._mount("fitness-sleep-stage-card"));
    }
    if (!children.length) {
      this.shadowRoot.innerHTML = "";
      this._compositeChildren = [];
      this._compositeBuilt = true;
      this._compositeSignatureValue = this._compositeSignature();
      return;
    }
    this._shell(this.config.title || l.recovery, "mdi:heart-pulse", children, "var(--warning-color,#f9a825)");
  }
}

class FitnessEvaluationCard extends FitnessCompositeCard {
  _relevantEntityKeys() {
    return [
      "cardiorespiratory_fitness_trend","vo2max_percent_predicted",
      "training_load","training_adaptation_status","autonomic_recovery_trend","heart_rate_recovery",
      "training_recovery_relationship","sleep_consistency","sleep_deficit_7d",
      "ai_general_evaluation",
    ];
  }
  _extraSignatureParts() {
    return [_fitnessSourceMetricSignature(
      _fitnessProfileDataRoutes(
        this._profile, this._hass, "evaluation", this._profile?.evaluation_source_metrics || {}
      ),
      this._hass, "evaluation-source"
    )];
  }

  _render() {
    if (!this.shadowRoot || !this._hass || !this._profile) return;
    const l = this._profile.labels || {};
    const e = this._profile.entities || {};
    const children = [];
    const hasProgress = _fitnessEvaluationSourceMetric(this._profile, this._hass, "vo2max")?.canonicalValue != null
      || _fitnessUsableState(this._hass, e.cardiorespiratory_fitness_trend)
      || _fitnessUsableState(this._hass, e.vo2max_percent_predicted);
    const loadState = e.training_load ? this._hass.states[e.training_load] : null;
    const adaptationState = e.training_adaptation_status ? this._hass.states[e.training_adaptation_status] : null;
    const loadRecent = _fitnessNumber(loadState?.state);
    const loadBaseline = _fitnessNumber(_fitnessAttr(loadState, "baseline_28d_weekly_equivalent"));
    const loadRatio = _fitnessNumber(_fitnessAttr(loadState, "recent_to_baseline_ratio"));
    const loadWorkouts = _fitnessNumber(_fitnessAttr(loadState, "workouts_7d"));
    const loadMinutes = _fitnessNumber(_fitnessAttr(loadState, "workout_minutes_7d"));
    const adaptationStatus = String(_fitnessAttr(adaptationState, "status") || "insufficient_data");
    const adaptationEvidence = _fitnessNumber(_fitnessAttr(adaptationState, "evidence_count"));
    const baselineReliable = Boolean(
      _fitnessAttr(adaptationState, "baseline_reliable")
      ?? (loadRatio != null && loadBaseline != null && loadBaseline > 0)
    );
    const hasLoad = Boolean(
      baselineReliable
      && loadRecent != null && loadRecent > 0
      && loadBaseline != null && loadBaseline > 0
      && loadRatio != null && loadRatio > 0
      && loadWorkouts != null && loadWorkouts >= 2
    );
    if (hasProgress) children.push(this._mount("fitness-progress-card"));
    if (hasLoad) children.push(this._mount("fitness-training-load-card"));
    if (!children.length) {
      this.shadowRoot.innerHTML = "";
      this._compositeChildren = [];
      this._compositeBuilt = true;
      this._compositeSignatureValue = this._compositeSignature();
      return;
    }
    this._shell(this.config.title || l.evaluation, "mdi:chart-line", children, "var(--primary-color)");
  }
}

class FitnessDashboardStrategy extends HTMLElement {
  static getCreateSuggestions(hass) {
    return { title: "Fitness", icon: "mdi:run-fast" };
  }

  static async generate(config, hass) {
    const data = await hass.callWS({ type: "fitness/dashboard/config" });
    const requested = config?.profile_entry_id;
    const profiles = (data?.profiles || []).filter((profile) => !requested || profile.entry_id === requested);
    if (!profiles.length) {
      const labels = data?.labels || {};
      return { title: config?.title || "Fitness", views: [{ title: "Fitness", path: "fitness", cards: [{ type: "markdown", content: `# Fitness\n\n${labels.no_fitness_profiles}` }] }] };
    }
    const multi = profiles.length > 1;
    const views = [];
    for (const profile of profiles) {
      views.push(...this._profileViews(hass, profile, multi));
    }
    return { title: config?.title || profiles[0].labels.dashboard, views };
  }

  static _profileViews(hass, profile, multi) {
    const e = profile.entities || {};
    const ui = String(profile?.language || hass?.language || "en").toLowerCase().split("-")[0];
    const l = profile.labels_by_language?.[ui]
      || profile.labels_by_language?.en
      || profile.labels
      || {};
    const prefix = multi ? `${profile.profile_name} · ` : "";
    const slug = profile.entry_id.slice(0, 8);

    const liveCore = only(hass, e, [
      "session_status","session_duration","current_heart_rate","current_power",
      "current_cadence","current_speed","current_pace","current_distance",
    ]);
    const controls = only(hass, e, [
      "start_workout","pause_workout","resume_workout","stop_workout",
    ]);

    const summarySections = [
      section([{ type: "custom:fitness-workout-card", profile_entry_id: profile.entry_id }]),
      section([{ type: "custom:fitness-sleep-recovery-card", profile_entry_id: profile.entry_id }]),
      section([{ type: "custom:fitness-evaluation-card", profile_entry_id: profile.entry_id }]),
    ];

    const liveSections = [
      section([
        { type: "custom:fitness-live-workout-card", profile_entry_id: profile.entry_id },
      ]),
    ];

    return [
      {
        title: `${prefix}${l.overview}`,
        path: `${slug}-overview`,
        icon: "mdi:view-dashboard-outline",
        type: "sections",
        max_columns: 3,
        sections: summarySections,
      },
      {
        title: `${prefix}${l.live || l.current}`,
        path: `${slug}-live`,
        icon: "mdi:run-fast",
        type: "sections",
        max_columns: 2,
        sections: liveSections,
      },
    ];
  }
}


const FITNESS_TV_CARD_CATALOG = Object.freeze([
  {id:"today", element:"fitness-today-card", label:"card_today", icon:"mdi:calendar-today"},
  {id:"live_workout", element:"fitness-live-workout-card", label:"card_live_workout", icon:"mdi:run-fast"},
  {id:"workout", element:"fitness-workout-card", label:"card_workout", icon:"mdi:dumbbell"},
  {id:"workout_highlights", element:"fitness-workout-highlights-card", label:"card_workout_highlights", icon:"mdi:star-outline"},
  {id:"workout_rpe", element:"fitness-workout-rpe-card", label:"card_workout_rpe", icon:"mdi:gauge"},
  {id:"strength_details", element:"fitness-strength-details-card", label:"card_strength_details", icon:"mdi:weight-lifter"},
  {id:"sleep_recovery", element:"fitness-sleep-recovery-card", label:"card_sleep_recovery", icon:"mdi:sleep"},
  {id:"sleep_stages", element:"fitness-sleep-stage-card", label:"card_sleep_stages", icon:"mdi:chart-donut"},
  {id:"recovery", element:"fitness-recovery-card", label:"card_recovery", icon:"mdi:battery-heart-variant"},
  {id:"evaluation", element:"fitness-evaluation-card", label:"card_evaluation", icon:"mdi:chart-line"},
  {id:"progress", element:"fitness-progress-card", label:"card_progress", icon:"mdi:trending-up"},
  {id:"training_adaptation", element:"fitness-training-adaptation-card", label:"card_training_adaptation", icon:"mdi:chart-timeline-variant-shimmer"},
  {id:"training_load", element:"fitness-training-load-card", label:"card_training_load", icon:"mdi:chart-bell-curve-cumulative"},
  {id:"route", element:"fitness-route-card", label:"card_route", icon:"mdi:map-marker-path"},
  {id:"comparison", element:"fitness-comparison-card", label:"card_comparison", icon:"mdi:compare-horizontal"},
]);
const FITNESS_TV_DEFAULT_CARDS = Object.freeze(["live_workout","workout","sleep_recovery","evaluation"]);
const FITNESS_TV_AUDIO_EVENT = "fitness_tv_audio";
const FITNESS_TV_MEDIA_EVENT = "fitness_tv_media";
const FITNESS_TV_MEDIA_STATE_EVENT = "fitness_tv_media_state";
const FITNESS_TV_SETTINGS_EVENT = "fitness_tv_settings";
const FITNESS_TV_PROFILE_STORAGE = "fitness.tv.profile";
const FITNESS_TV_PROFILE_TAB_STORAGE = "fitness.tv.profile.tab";
const FITNESS_TV_CAST_APP_ID = "A078F6B0";
const FITNESS_TV_OVERVIEW_LOCAL_CAST_TAB_STORAGE = "fitness-tv-overview-local-cast";
const FITNESS_MUSIC_PREFIXES = Object.freeze({
  radio:"fitness-radio://",
  url:"fitness-url://",
  spotify:"fitness-spotify://", // legacy saved favorites only; new direct links reject Spotify
  soundcloud:"fitness-soundcloud://",
  youtube:"fitness-youtube://",
  ytdlp:"fitness-ytdlp://",
  music_assistant:"fitness-ma://",
});
const FITNESS_MUSIC_SEARCH_TYPES = Object.freeze([
  {id:"track",label:"music_type_tracks",icon:"mdi:music-note"},
  {id:"album",label:"music_type_albums",icon:"mdi:album"},
  {id:"playlist",label:"music_type_playlists",icon:"mdi:playlist-music"},
  {id:"artist",label:"music_type_artists",icon:"mdi:account-music"},
  {id:"radio",label:"music_type_radio",icon:"mdi:radio"},
  {id:"podcast",label:"music_type_podcasts",icon:"mdi:podcast"},
  {id:"audiobook",label:"music_type_audiobooks",icon:"mdi:book-music"},
]);
const FITNESS_SENDSPIN_MODULE_URL = "https://cdn.jsdelivr.net/npm/@sendspin/sendspin-js@3.2.0/+esm";
const FITNESS_TV_CAST_RECEIVER = (() => {
  const host = String(globalThis.location?.hostname || "").toLowerCase();
  return host === "cast.home-assistant.io";
})();
const FITNESS_TV_CLIENT_ID = (() => {
  if (window.__fitnessTvClientId) return window.__fitnessTvClientId;
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  window.__fitnessTvClientId = `fitness-tv-${random}`;
  return window.__fitnessTvClientId;
})();
const FITNESS_REMOTE_GATEWAY_STORAGE = "fitness.remote.gateway_id";
const FITNESS_TV_BACK_CONFIRM_MS = 2800;
const FITNESS_TV_BACK_DISTINCT_PRESS_MS = 280;
const FITNESS_TV_BACK_GUARDED_RECENT_INPUT_MS = 4000;
const FITNESS_TV_CAST_EXIT_STARTUP_GRACE_MS = 12000;
const FITNESS_TV_TEXT_ENTRY_BACK_SUPPRESS_MS = 900;
const FITNESS_TV_NATIVE_CONTROL_BACK_SUPPRESS_MS = 900;
const FITNESS_TV_NAV_HISTORY_SUPPRESS_MS = 550;
const FITNESS_TV_REMOTE_MEDIA_DEDUPE_MS = 180;
const FITNESS_TV_FOCUS_TOOLTIP_DELAY_MS = 1600;
const FITNESS_TV_FOCUS_TOOLTIP_VISIBLE_MS = 2600;
// Cast receivers run on several TV/runtime families. Modern engines normally
// expose standard KeyboardEvent.key names, while Android TV, Samsung/Tizen,
// LG/webOS and older CE-HTML runtimes can expose only legacy numeric codes.
// Keep this table data-driven so vendor quirks never leak into navigation code.
const FITNESS_TV_REMOTE_KEY_ACTIONS = Object.freeze({
  ArrowLeft:"left", Left:"left", NavigatePrevious:"left",
  ArrowRight:"right", Right:"right", NavigateNext:"right",
  ArrowUp:"up", Up:"up",
  ArrowDown:"down", Down:"down",
  Enter:"activate", NumpadEnter:"activate", Select:"activate", Accept:"activate", OK:"activate", NavigateIn:"activate", " ":"activate", Spacebar:"activate",
  Back:"back", BrowserBack:"back", GoBack:"back", NavigateOut:"back", Escape:"cancel", Esc:"cancel", Backspace:"back", XF86Back:"back",
  MediaPlayPause:"media_toggle", MediaPlay:"media_play", MediaPause:"media_pause", MediaStop:"media_stop",
  MediaTrackNext:"media_next", MediaTrackPrevious:"media_previous", MediaFastForward:"media_forward", MediaRewind:"media_rewind",
});
const FITNESS_TV_REMOTE_CODE_ACTIONS = Object.freeze({
  // Common DOM / CE-HTML navigation.
  13:"activate", 23:"activate", 66:"activate",
  37:"left", 38:"up", 39:"right", 40:"down",
  // Android/Chrome, desktop-browser and TV-vendor Back variants.
  4:"back", 8:"back", 27:"cancel", 166:"back", 461:"back", 10009:"back",
  // Standard browser + Samsung/LG/CE-HTML media key variants.
  19:"media_pause", 176:"media_next", 177:"media_previous", 178:"media_stop", 179:"media_toggle",
  412:"media_rewind", 413:"media_stop", 415:"media_play", 417:"media_forward",
  10232:"media_previous", 10233:"media_next", 10252:"media_toggle",
});
const FITNESS_REMOTE_PROFILE_STORAGE_PREFIX = "fitness.remote.profile.";
const FITNESS_TV_CAST_NAMESPACE = "urn:x-cast:com.nabucasa.hast";
const FITNESS_REMOTE_BLE_SERVICES = Object.freeze([
  "0000180d-0000-1000-8000-00805f9b34fb",
  "00001818-0000-1000-8000-00805f9b34fb",
  "00001816-0000-1000-8000-00805f9b34fb",
  "00001814-0000-1000-8000-00805f9b34fb",
  "00001826-0000-1000-8000-00805f9b34fb",
]);
const FITNESS_REMOTE_BLE_BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb";
const FITNESS_REMOTE_BLE_BATTERY_CHARACTERISTIC = "00002a19-0000-1000-8000-00805f9b34fb";
const FITNESS_REMOTE_BLE_DEVICE_INFO_SERVICE = "0000180a-0000-1000-8000-00805f9b34fb";
const FITNESS_REMOTE_BLE_CONNECT_SERVICES = Object.freeze([
  ...FITNESS_REMOTE_BLE_SERVICES,
  FITNESS_REMOTE_BLE_BATTERY_SERVICE,
]);
const FITNESS_REMOTE_BLE_OPTIONAL_SERVICES = Object.freeze([
  ...FITNESS_REMOTE_BLE_CONNECT_SERVICES,
  FITNESS_REMOTE_BLE_DEVICE_INFO_SERVICE,
]);
const FITNESS_REMOTE_BLE_IDENTITY_CHARACTERISTICS = Object.freeze({
  "00002a24-0000-1000-8000-00805f9b34fb":"model",
  "00002a25-0000-1000-8000-00805f9b34fb":"serial_number",
  "00002a26-0000-1000-8000-00805f9b34fb":"firmware_version",
  "00002a27-0000-1000-8000-00805f9b34fb":"hw_version",
  "00002a28-0000-1000-8000-00805f9b34fb":"sw_version",
  "00002a29-0000-1000-8000-00805f9b34fb":"manufacturer",
});
const FITNESS_REMOTE_BLE_CHARACTERISTICS = Object.freeze([
  FITNESS_REMOTE_BLE_BATTERY_CHARACTERISTIC,
  "00002a37-0000-1000-8000-00805f9b34fb",
  "00002a63-0000-1000-8000-00805f9b34fb",
  "00002a5b-0000-1000-8000-00805f9b34fb",
  "00002a53-0000-1000-8000-00805f9b34fb",
  "00002ad2-0000-1000-8000-00805f9b34fb",
  "00002acd-0000-1000-8000-00805f9b34fb",
]);
const FITNESS_ANT_USB_FILTERS = Object.freeze([
  {vendorId:0x0fcf,productId:0x1008},
  {vendorId:0x0fcf,productId:0x1009},
]);
const FITNESS_ANT_USB_PRODUCT_IDS = new Set([0x1008,0x1009]);
const FITNESS_ANT_PLUS_NETWORK_KEY = Object.freeze([0xB9,0xA5,0x21,0xFB,0xBD,0x72,0xC3,0x45]);

class FitnessTvDashboardCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    if (FITNESS_TV_CAST_RECEIVER) this.setAttribute("fitness-cast-receiver", "");
    else this.removeAttribute("fitness-cast-receiver");
    if (this._layoutEditing === undefined) this._layoutEditing = false;
    if (!this.shadowRoot) this.attachShadow({mode:"open"});
    if (!this._musicAudio) {
      this._musicAudio = new Audio();
      this._musicAudio.preload = "auto";
      this._musicMetadata = {artist:"",thumbnail:"",details:"",position:0,duration:0};
      this._lastProgressSyncAt = 0;
      this._embeddedPosition = 0;
      this._embeddedDuration = 0;
      this._musicAudio.addEventListener("loadedmetadata", () => this._captureLocalMediaProgress(true));
      this._musicAudio.addEventListener("durationchange", () => this._captureLocalMediaProgress(true));
      this._musicAudio.addEventListener("timeupdate", () => this._captureLocalMediaProgress(false));
      this._musicAudio.addEventListener("seeked", () => this._captureLocalMediaProgress(true));
      this._musicAudio.addEventListener("play", () => {
        this._syncMediaState({playing:true,error:false});
        this._updateMediaControls();
      });
      this._musicAudio.addEventListener("pause", () => {
        if (this._musicElementStateSuppressed()) { this._updateMediaControls(); return; }
        this._syncMediaState({playing:false,error:false});
        this._updateMediaControls();
      });
      this._musicAudio.addEventListener("ended", () => {
        if (this._musicElementStateSuppressed()) { this._updateMediaControls(); return; }
        if (this._activePlaylistContext?.kind === "user" && !this._isMAItem({media_content_id:this._currentMediaContentId})) {
          void this._playlistTransport("next", {automatic:true});
          return;
        }
        this._syncMediaState({playing:false,error:false});
        this._updateMediaControls();
      });
      this._musicAudio.addEventListener("error", () => {
        // Clearing src/load() during an intentional stop can emit an HTMLAudio
        // error.  With no source attached that is teardown, not playback failure.
        if (!String(this._musicAudio?.getAttribute("src") || "").trim()) return;
        const mediaContentId = String(this._currentMediaContentId || this._sharedMediaState?.media_content_id || "");
        if (!mediaContentId) {
          this._syncMediaState({title:"",media_content_id:"",playing:false,error:false});
          this._updateMediaControls(false);
          return;
        }
        if (FITNESS_TV_CAST_RECEIVER) {
          this._castFailedMediaContentId = mediaContentId;
          console.warn("[Fitness TV] receiver audio playback failed", {
            media_content_id:mediaContentId,
            code:Number(this._musicAudio?.error?.code || 0),
            message:String(this._musicAudio?.error?.message || ""),
          });
        }
        this._syncMediaState({playing:false,error:true});
        this._updateMediaControls(true);
      });
      this._ttsAudio = new Audio();
      this._ttsAudio.preload = "auto";
      this._ttsQueue = Promise.resolve();
      this._embeddedProvider = "";
      this._embeddedController = null;
      this._embeddedPlaying = false;
      this._embeddedVolume = 100;
      this._maSendspinPlayer = null;
      this._maSendspinRelayPath = "";
      this._maSendspinRelayClientId = "";
      this._maSendspinModule = null;
      this._maSendspinModulePromise = null;
      this._maSendspinConnected = false;
      this._maSendspinPlayerId = "";
      this._maQueueProgress = null;
      this._maProgressTimer = null;
      this._maProgressSyncInFlight = false;
      this._embeddedProgressTimer = null;
      this._mediaProgressScrubbing = false;
      this._localCastRearmInFlight = false;
      this._serverCastRearmInFlight = false;
      this._localCastRearmUntil = 0;
      this._serverCastRearmUntil = 0;
      this._userPlaylists = [];
      this._musicResultSelection = new Set();
      this._activePlaylistContext = null;
      this._fitnessPlaylistIndex = 0;
      this._fitnessPlaylistShuffle = false;
      this._fitnessPlaylistRepeat = "off";
      this._youtubePlaylistShuffle = false;
      this._youtubePlaylistRepeat = "off";
      this._suppressMusicElementStateUntil = 0;
      this._castRemoteMode = "outer";
      this._castRemoteSection = null;
      this._castRemoteLastInnerFocus = new WeakMap();
      this._castRemoteFocusTrail = [];
      this._castRemoteSectionTrail = [];
      this._castFocusTooltipElement = null;
      this._castFocusTooltipTimer = null;
      this._castFocusTooltipDismissTimer = null;
      this._castRemoteBackLastEventAt = 0;
      this._castRemoteLastPhysicalBackAt = 0;
      this._castRemoteLastNonBackInputAt = 0;
      this._castRemoteBackUnreliable = false;
      this._castRemoteExitAuthorization = "";
      this._castRemoteExitArmedUntil = 0;
      this._castRemoteExitAllowedAfter = FITNESS_TV_CAST_RECEIVER ? performance.now() + FITNESS_TV_CAST_EXIT_STARTUP_GRACE_MS : 0;
      this._castRemoteUserEngaged = false;
      this._castRemoteTextEntryActive = false;
      this._castRemoteTextEntryElement = null;
      this._castRemoteTextEntryBackSuppressUntil = 0;
      this._castRemoteTextEntryReleaseTimer = null;
      this._castRemoteQuitInFlight = false;
      this._castBackGuardInstalled = false;
      this._castRemoteCapabilities = {sources:new Set(), actions:new Set(), keyCodes:new Set(), caf:false, pointer:false};
      this._castRemoteMediaLastAction = "";
      this._castRemoteMediaLastSource = "";
      this._castRemoteMediaLastAt = 0;
      this._castCafRemoteBindings = [];
      this._castCafRemoteTimers = [];
      this._castCafRemoteDetected = false;
      this._castFailedMediaContentId = "";
      // Preserve a requested HTML-audio resume target while metadata/timeupdate
      // events fire during source attachment. Without this barrier those early
      // zero-second events can overwrite persisted progress before seek runs.
      this._pendingHtmlAudioResumePosition = 0;
      this._animationsEnabled = true;
      this._conditionalCardVisibilityKey = "";
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loaded && !this._loading) {
      this._load();
      return;
    }
    const visibilityKey = this._conditionalCardVisibilitySignature(hass);
    if (this._profile && visibilityKey !== this._conditionalCardVisibilityKey) {
      this._conditionalCardVisibilityKey = visibilityKey;
      this._mountSelectedCards();
    } else {
      for (const card of this._mountedCards || []) card.hass = hass;
    }
    this._applyAmbientBackground();
    this._reconcileScreenWakeLock();
    if (this._activeCastTarget) {
      this._refreshCastUiState();
      this._updateMediaControls();
    }
  }

  connectedCallback() {
    if (this._hass && !this._loaded && !this._loading) this._load();
    else if (this._hass && this._loaded && !this._loading) void this._resumeRuntimeConnection();
    if (!this._boundFullscreenChange) this._boundFullscreenChange = () => this._updateFullscreenButton();
    document.addEventListener("fullscreenchange", this._boundFullscreenChange);
    if (FITNESS_TV_CAST_RECEIVER) {
      if (!this._boundCastKeydown) this._boundCastKeydown = (event) => this._handleCastKeydown(event);
      if (!this._boundCastKeyup) this._boundCastKeyup = (event) => this._handleCastKeyup(event);
      if (!this._boundCastPopstate) this._boundCastPopstate = (event) => this._handleCastPopstate(event);
      if (!this._boundCastPointerClick) this._boundCastPointerClick = (event) => this._handleCastPointerClick(event);
      if (!this._boundCastPointerOver) this._boundCastPointerOver = (event) => this._handleCastPointerHover(event, true);
      if (!this._boundCastPointerOut) this._boundCastPointerOut = (event) => this._handleCastPointerHover(event, false);
      if (!this._boundCastTextInput) this._boundCastTextInput = (event) => this._handleCastTextInput(event);
      if (!this._boundCastFocusOut) this._boundCastFocusOut = (event) => this._handleCastFocusOut(event);
      window.addEventListener("keydown", this._boundCastKeydown, true);
      window.addEventListener("keyup", this._boundCastKeyup, true);
      window.addEventListener("popstate", this._boundCastPopstate, true);
      window.addEventListener("click", this._boundCastPointerClick, true);
      window.addEventListener("pointerover", this._boundCastPointerOver, true);
      window.addEventListener("pointerout", this._boundCastPointerOut, true);
      window.addEventListener("input", this._boundCastTextInput, true);
      window.addEventListener("focusout", this._boundCastFocusOut, true);
      this._castRemoteExitAllowedAfter = Math.max(
        Number(this._castRemoteExitAllowedAfter || 0),
        performance.now() + FITNESS_TV_CAST_EXIT_STARTUP_GRACE_MS,
      );
      if (!this._boundWakeVisibility) this._boundWakeVisibility = () => {
        if (document.visibilityState !== "visible") {
          this._endCastRemoteTextEntry("hidden");
          this._clearCastExitConfirmation();
          return;
        }
        this._reconcileScreenWakeLock();
        this._ensureCastBackGuard();
        setTimeout(() => this._ensureCastRemoteOuterFocus(), 0);
      };
      document.addEventListener("visibilitychange", this._boundWakeVisibility);
      this._ensureCastBackGuard();
      this._scheduleCastFrameworkRemoteAdapter();
      this._bindBrowserMediaSessionAdapter();
      this._reconcileScreenWakeLock();
    }
  }

  disconnectedCallback() {
    if (this._boundFullscreenChange) document.removeEventListener("fullscreenchange", this._boundFullscreenChange);
    if (this._boundCastKeydown) window.removeEventListener("keydown", this._boundCastKeydown, true);
    if (this._boundCastKeyup) window.removeEventListener("keyup", this._boundCastKeyup, true);
    if (this._boundCastPopstate) window.removeEventListener("popstate", this._boundCastPopstate, true);
    if (this._boundCastPointerClick) window.removeEventListener("click", this._boundCastPointerClick, true);
    if (this._boundCastPointerOver) window.removeEventListener("pointerover", this._boundCastPointerOver, true);
    if (this._boundCastPointerOut) window.removeEventListener("pointerout", this._boundCastPointerOut, true);
    if (this._boundCastTextInput) window.removeEventListener("input", this._boundCastTextInput, true);
    if (this._boundCastFocusOut) window.removeEventListener("focusout", this._boundCastFocusOut, true);
    if (this._boundWakeVisibility) document.removeEventListener("visibilitychange", this._boundWakeVisibility);
    this._unbindCastFrameworkRemoteAdapter();
    this._unbindBrowserMediaSessionAdapter();
    this._endCastRemoteTextEntry("disconnect");
    this._clearCastExitConfirmation();
    this._hideCastFocusTooltip();
    this._clearCastRemoteFocus();
    this._clearCastRemoteSectionMarks();
    this._releaseScreenWakeLock();
    this._suspendRemoteGatewaysForNavigation();
    // Route changes remove this Lovelace card from the DOM.  Preserve the current
    // media id/position as a *paused* shared session before destroying local
    // browser players.  When the user returns, Play can resolve the media again
    // and continue from the stored position instead of inheriting a stale
    // "playing" state whose Audio/iframe no longer exists.
    this._suspendMusicForNavigation();
    this._hardStopAudio(this._ttsAudio);
    this._audioOwner = false;
    this._releaseWindowController();
    this._cardResizeObserver?.disconnect?.();
    this._cardResizeObserver = null;
    this._stopOledProtection();
    if (this._heartbeatTimer) clearInterval(this._heartbeatTimer);
    this._heartbeatTimer = null;
    if (this._unsubscribeTvAudio) {
      Promise.resolve(this._unsubscribeTvAudio).then((unsub) => {
        if (typeof unsub === "function") unsub();
      }).catch(() => {});
      this._unsubscribeTvAudio = null;
    }
    if (this._unsubscribeTvMedia) {
      Promise.resolve(this._unsubscribeTvMedia).then((unsub) => {
        if (typeof unsub === "function") unsub();
      }).catch(() => {});
      this._unsubscribeTvMedia = null;
    }
    if (this._unsubscribeTvMediaState) {
      Promise.resolve(this._unsubscribeTvMediaState).then((unsub) => {
        if (typeof unsub === "function") unsub();
      }).catch(() => {});
      this._unsubscribeTvMediaState = null;
    }
    if (this._unsubscribeTvSettings) {
      Promise.resolve(this._unsubscribeTvSettings).then((unsub) => {
        if (typeof unsub === "function") unsub();
      }).catch(() => {});
      this._unsubscribeTvSettings = null;
    }
  }

  async _resumeRuntimeConnection() {
    if (!this.isConnected || !this._hass || !this._profile) return;
    this._canControlProfile = Boolean(this._access?.is_admin || this._profile?.access?.can_control);
    if (this._canControlProfile) {
      this._claimWindowController();
      await this._subscribeTvAudio();
    }
    await this._subscribeTvMedia();
    await this._subscribeTvSettings();
    if (this._canControlProfile) {
      this._startHeartbeat();
      if (!FITNESS_TV_CAST_RECEIVER) void this._resumeRemoteGateways();
      await this._heartbeat();
    }
  }

  _sessionState() {
    const entityId = this._profile?.entities?.session_status;
    const state = entityId ? String(this._hass?.states?.[entityId]?.state || "") : "";
    return ["waiting_for_live_data", "active", "paused", "recovery"].includes(state) ? state : "idle";
  }

  _sessionOpen() {
    return this._sessionState() !== "idle";
  }

  _musicPlaying() {
    return Boolean(
      this._sharedMediaState?.playing
      || (this._musicAudio && !this._musicAudio.paused)
      || this._embeddedPlaying
    );
  }

  _shouldKeepScreenAwake() {
    return FITNESS_TV_CAST_RECEIVER && (this._sessionOpen() || this._musicPlaying());
  }

  async _startScreenWakeLock() {
    if (!this._shouldKeepScreenAwake() || document.visibilityState === "hidden") return;
    if (!navigator?.wakeLock?.request) return;
    if (this._screenWakeLock && !this._screenWakeLock.released) return;
    try {
      const lock = await navigator.wakeLock.request("screen");
      this._screenWakeLock = lock;
      lock.addEventListener?.("release", () => {
        if (this._screenWakeLock === lock) this._screenWakeLock = null;
        if (this._shouldKeepScreenAwake() && document.visibilityState === "visible") {
          setTimeout(() => this._startScreenWakeLock(), 1000);
        }
      });
    } catch (_err) {
      this._screenWakeLock = null;
    }
  }

  _reconcileScreenWakeLock() {
    if (this._shouldKeepScreenAwake()) this._startScreenWakeLock();
    else this._releaseScreenWakeLock();
  }

  _releaseScreenWakeLock() {
    const lock = this._screenWakeLock;
    this._screenWakeLock = null;
    try { lock?.release?.(); } catch (_err) {}
  }

  _deepActiveElement() {
    let active = document.activeElement;
    while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
    return active;
  }

  _clearCastExitConfirmation() {
    this._castRemoteExitArmedUntil = 0;
    this._castRemoteExitAuthorization = "";
    if (this._castRemoteExitTimer) clearTimeout(this._castRemoteExitTimer);
    this._castRemoteExitTimer = null;
    const notice = this.shadowRoot?.getElementById("cast-exit-confirm");
    if (notice) notice.hidden = true;
  }

  _showCastExitConfirmation() {
    if (!FITNESS_TV_CAST_RECEIVER) return;
    const l = this._labels();
    const notice = this.shadowRoot?.getElementById("cast-exit-confirm");
    if (notice) {
      notice.textContent = String(l.cast_exit_confirm);
      notice.hidden = false;
    }
    this._castRemoteExitArmedUntil = performance.now() + FITNESS_TV_BACK_CONFIRM_MS;
    if (this._castRemoteExitTimer) clearTimeout(this._castRemoteExitTimer);
    this._castRemoteExitTimer = setTimeout(() => this._clearCastExitConfirmation(), FITNESS_TV_BACK_CONFIRM_MS);
  }

  _recordCastRemoteDiagnostic(kind, detail = "") {
    // Keep remote diagnostics off the TV UI. Console logging remains available
    // for browser/receiver debugging without covering workout information.
    if (!FITNESS_TV_CAST_RECEIVER) return;
    try { console.debug(`[Fitness TV remote] ${String(kind || "event")}`, String(detail || "")); } catch (_err) {}
  }

  _ensureCastBackGuard() {
    if (!FITNESS_TV_CAST_RECEIVER) return;
    try {
      if (history.state?.__fitnessTvBackGuard) {
        this._castBackGuardInstalled = true;
        return;
      }
      history.pushState({...((history.state && typeof history.state === "object") ? history.state : {}), __fitnessTvBackGuard:true}, "", location.href);
      this._castBackGuardInstalled = true;
      this._recordCastRemoteDiagnostic("back-guard", "history armed");
    } catch (err) {
      this._castBackGuardInstalled = false;
      this._recordCastRemoteDiagnostic("back-guard", `failed ${err?.name || "error"}`);
    }
  }

  _castRemoteInputAction(event) {
    const key = String(event?.key || "");
    const codeName = String(event?.code || "");
    const numericCode = Number(event?.keyCode ?? event?.which ?? 0);
    return FITNESS_TV_REMOTE_KEY_ACTIONS[key]
      || FITNESS_TV_REMOTE_KEY_ACTIONS[codeName]
      || FITNESS_TV_REMOTE_CODE_ACTIONS[numericCode]
      || "";
  }

  _castRemoteTextEntryControl(element) {
    if (!element) return null;
    const tag = String(element.tagName || "").toUpperCase();
    if (tag === "TEXTAREA") return element;
    if (element.isContentEditable || String(element.getAttribute?.("contenteditable") || "").toLowerCase() === "true") return element;
    if (tag !== "INPUT") return null;
    const type = String(element.type || "text").toLowerCase();
    if (["button","checkbox","radio","range","submit","reset","file","color","hidden","image"].includes(type)) return null;
    return element;
  }

  _castRemoteTextEntryFromEvent(event) {
    const path = typeof event?.composedPath === "function" ? event.composedPath() : [];
    for (const node of path) {
      const editable = this._castRemoteTextEntryControl(node);
      if (editable) return editable;
    }
    return this._castRemoteTextEntryControl(this._deepActiveElement());
  }

  _castRemoteNativePickerFromEvent(event, includeActive = false) {
    const path = typeof event?.composedPath === "function" ? event.composedPath() : [];
    for (const node of path) {
      if (String(node?.tagName || "").toUpperCase() === "SELECT") return node;
    }
    if (!includeActive) return null;
    const active = this._deepActiveElement();
    return String(active?.tagName || "").toUpperCase() === "SELECT" ? active : null;
  }

  _yieldCastRemoteKeyToNativePicker(event, action = "") {
    if (!["back","cancel"].includes(String(action || ""))) return false;
    // Escape is a common native picker-close signal, so active SELECT focus is
    // enough for cancel. A real BrowserBack must target the SELECT itself; this
    // keeps the user's deliberate Back available after a picker has closed.
    const picker = this._castRemoteNativePickerFromEvent(event, action === "cancel");
    if (!picker) return false;
    // Native TV select/picker UIs often emit Escape/Back while closing. Let the
    // picker own that event and quarantine any follow-up key/history event so
    // closing a selector can never become the first/second Cast-exit Back.
    this._castRemoteNativeControlBackSuppressUntil = performance.now() + FITNESS_TV_NATIVE_CONTROL_BACK_SUPPRESS_MS;
    this._castRemoteBackLastEventAt = 0;
    this._clearCastExitConfirmation();
    this._recordCastRemoteDiagnostic("native-picker", `yield ${action}`);
    return true;
  }

  _castRemoteBackspaceKey(event) {
    const key = String(event?.key || "");
    const code = String(event?.code || "");
    const numericCode = Number(event?.keyCode ?? event?.which ?? 0);
    return key === "Backspace" || code === "Backspace" || numericCode === 8;
  }

  _beginCastRemoteTextEntry(element, source = "activate") {
    const editable = this._castRemoteTextEntryControl(element);
    if (!editable) return false;
    if (this._castRemoteTextEntryReleaseTimer) clearTimeout(this._castRemoteTextEntryReleaseTimer);
    this._castRemoteTextEntryReleaseTimer = null;
    this._castRemoteTextEntryActive = true;
    this._castRemoteTextEntryElement = editable;
    this._castRemoteTextEntryBackSuppressUntil = 0;
    this._castRemoteBackLastEventAt = 0;
    this._clearCastExitConfirmation();
    this._recordCastRemoteDiagnostic("text-entry", `begin · ${source}`);
    return true;
  }

  _endCastRemoteTextEntry(source = "done") {
    if (this._castRemoteTextEntryReleaseTimer) clearTimeout(this._castRemoteTextEntryReleaseTimer);
    this._castRemoteTextEntryReleaseTimer = null;
    const wasActive = Boolean(this._castRemoteTextEntryActive || this._castRemoteTextEntryElement);
    this._castRemoteTextEntryActive = false;
    this._castRemoteTextEntryElement = null;
    this._castRemoteBackLastEventAt = 0;
    if (wasActive) this._recordCastRemoteDiagnostic("text-entry", `end · ${source}`);
  }

  _releaseCastRemoteTextEntrySoon(source = "keyboard-back", delay = 220) {
    if (this._castRemoteTextEntryReleaseTimer) clearTimeout(this._castRemoteTextEntryReleaseTimer);
    this._castRemoteTextEntryReleaseTimer = setTimeout(() => this._endCastRemoteTextEntry(source), Math.max(0, Number(delay) || 0));
  }

  _handleCastTextInput(event) {
    if (!FITNESS_TV_CAST_RECEIVER) return;
    const editable = this._castRemoteTextEntryFromEvent(event);
    if (editable) this._beginCastRemoteTextEntry(editable, "input");
  }

  _handleCastFocusOut(event) {
    if (!FITNESS_TV_CAST_RECEIVER || !this._castRemoteTextEntryActive) return;
    const editable = this._castRemoteTextEntryControl(event?.target) || this._castRemoteTextEntryElement;
    if (!editable) return;
    this._castRemoteTextEntryBackSuppressUntil = Math.max(
      Number(this._castRemoteTextEntryBackSuppressUntil || 0),
      performance.now() + FITNESS_TV_TEXT_ENTRY_BACK_SUPPRESS_MS,
    );
    this._clearCastExitConfirmation();
    this._releaseCastRemoteTextEntrySoon("focusout", 0);
  }

  _yieldCastRemoteKeyToTextEntry(event, action = "") {
    const editable = this._castRemoteTextEntryFromEvent(event) || this._castRemoteTextEntryElement;
    const backspace = this._castRemoteBackspaceKey(event);
    // Backspace is a text-editing key first. Keep numeric code 8 as a legacy TV
    // Back fallback only when no editable control owns the event.
    if (backspace && editable) {
      this._beginCastRemoteTextEntry(editable, "backspace");
      return true;
    }
    if (!this._castRemoteTextEntryActive || !editable || String(action || "").startsWith("media_")) return false;
    this._clearCastExitConfirmation();
    this._castRemoteBackLastEventAt = 0;
    if (action === "back") {
      // Let the TV/IME consume its own dismissal Back. Quarantine any popstate
      // emitted by that same physical press so it cannot become dashboard Back.
      this._castRemoteTextEntryBackSuppressUntil = performance.now() + FITNESS_TV_TEXT_ENTRY_BACK_SUPPRESS_MS;
      this._releaseCastRemoteTextEntrySoon("keyboard-back");
      this._recordCastRemoteDiagnostic("text-entry", "yield Back to keyboard");
    } else if (action === "activate" && String(editable.tagName || "").toUpperCase() === "INPUT") {
      // A single-line IME may use Enter/Done to dismiss itself without blur.
      this._releaseCastRemoteTextEntrySoon("keyboard-done", 320);
    }
    // Do not preventDefault/stopPropagation: the native TV keyboard must receive
    // cursor, delete, select and dismissal events before Fitness navigation.
    return true;
  }

  _registerCastRemoteCapability(source, action = "", event = null) {
    if (!FITNESS_TV_CAST_RECEIVER) return;
    const capabilities = this._castRemoteCapabilities || (this._castRemoteCapabilities = {sources:new Set(),actions:new Set(),keyCodes:new Set(),caf:false,pointer:false});
    if (source) capabilities.sources.add(String(source));
    if (action) capabilities.actions.add(String(action));
    const numericCode = Number(event?.keyCode ?? event?.which ?? 0);
    if (Number.isFinite(numericCode) && numericCode > 0) capabilities.keyCodes.add(numericCode);
    if (source === "cast-caf") capabilities.caf = true;
    if (source === "pointer") capabilities.pointer = true;
    const snapshot = {
      sources:[...capabilities.sources],
      actions:[...capabilities.actions],
      key_codes:[...capabilities.keyCodes],
      caf:Boolean(capabilities.caf),
      pointer:Boolean(capabilities.pointer),
      user_agent:String(globalThis.navigator?.userAgent || ""),
    };
    globalThis.__fitnessTvRemoteCapabilities = snapshot;
  }

  _castRemoteSectionFromEvent(event) {
    const path = typeof event?.composedPath === "function" ? event.composedPath() : [];
    for (const node of path) {
      if (node?.classList?.contains?.("tv-toolbar") || node?.classList?.contains?.("tv-card-slot")) return node;
    }
    let node = event?.target || null;
    while (node) {
      if (node?.classList?.contains?.("tv-toolbar") || node?.classList?.contains?.("tv-card-slot")) return node;
      node = node.parentElement || node.getRootNode?.()?.host || null;
      if (node === this) break;
    }
    return null;
  }

  _handleCastPointerClick(event) {
    if (!FITNESS_TV_CAST_RECEIVER || event?.isTrusted === false) return;
    const section = this._castRemoteSectionFromEvent(event);
    if (!section) return;
    this._registerCastRemoteCapability("pointer", "click", event);
    this._castRemoteUserEngaged = true;
    this._castRemoteLastNonBackInputAt = performance.now();
    this._clearCastExitConfirmation();
    this._castRemoteSection = section;
    const controls = this._castRemoteInnerElements(section);
    const path = typeof event?.composedPath === "function" ? event.composedPath() : [];
    const control = controls.find((item) => path.includes(item)) || null;
    if (control) {
      this._castRemoteMode = "inner";
      this._castRemoteLastInnerFocus.set(section, control);
      this._markCastRemoteSection(section, true);
      this._markCastRemoteFocus(control);
      if (this._castRemoteTextEntryControl(control)) this._beginCastRemoteTextEntry(control, "pointer");
      else this._endCastRemoteTextEntry("pointer-control");
    } else if (this._castRemoteMode !== "inner") {
      this._castRemoteMode = "outer";
      this._markCastRemoteSection(section, false);
    }
  }

  _castSelectableFromEvent(event) {
    const path = typeof event?.composedPath === "function" ? event.composedPath() : [];
    return path.find((item) => item?.matches?.(
      "button,select,input,textarea,a[href],[role='button'],[tabindex]:not([tabindex='-1']),.entity-link[data-more-info]"
    )) || null;
  }

  _castFocusTooltipText(element) {
    if (!element || element.disabled) return "";
    // A tooltip is fallback copy for icon-only/unlabelled controls. Never
    // duplicate text that is already readable on the Cast screen.
    if (this._castElementHasVisibleText(element)) return "";
    const labels = this._labels();
    if (element.matches?.(".entity-link[data-more-info]")) {
      const name = String(
        element.querySelector?.("span,strong,.title,.label")?.textContent
        || element.getAttribute?.("aria-label")
        || element.getAttribute?.("title")
        || ""
      ).trim();
      return name ? _fitnessFormatLabel(labels.cast_entity_details_hint, {name}) : "";
    }
    if (element.matches?.("input[type='range']")) {
      return String(labels.cast_progress_navigation_hint).trim();
    }
    const labelElement = element.querySelector?.("span");
    return String(
      labelElement?.textContent
      || element.getAttribute?.("aria-label")
      || element.getAttribute?.("title")
      || ""
    ).trim();
  }

  _castElementHasVisibleText(element) {
    if (!element) return false;
    const tag = String(element.tagName || "").toUpperCase();
    if (tag === "SELECT") {
      return Boolean(String(
        element.selectedOptions?.[0]?.textContent
        || element.options?.[Number(element.selectedIndex || 0)]?.textContent
        || element.value
        || ""
      ).trim());
    }
    if (["INPUT", "TEXTAREA"].includes(tag)) {
      const type = String(element.type || "").toLowerCase();
      if (!["button", "submit", "reset", "checkbox", "radio", "range", "color", "file"].includes(type)) {
        return Boolean(String(element.value || element.placeholder || "").trim());
      }
    }
    const textParents = [];
    const collectTextParents = (node) => {
      for (const child of node?.childNodes || []) {
        if (Number(child.nodeType) === 3 && String(child.textContent || "").trim()) textParents.push(node);
        else if (Number(child.nodeType) === 1 && !["SCRIPT", "STYLE"].includes(String(child.tagName || "").toUpperCase())) collectTextParents(child);
      }
    };
    collectTextParents(element);
    return [...new Set(textParents)].some((candidate) => {
      if (candidate.closest?.('[aria-hidden="true"]')) return false;
      const style = globalThis.getComputedStyle?.(candidate);
      if (style?.display === "none" || style?.visibility === "hidden" || Number(style?.opacity ?? 1) <= 0) return false;
      const rect = candidate.getBoundingClientRect?.();
      return !rect || (rect.width > 1 && rect.height > 1);
    });
  }

  _positionCastFocusTooltip(tooltip, element) {
    const target = element?.getBoundingClientRect?.();
    if (!tooltip || !target) return;
    tooltip.style.visibility = "hidden";
    tooltip.hidden = false;
    const viewportWidth = Math.max(1, Number(globalThis.innerWidth || document.documentElement?.clientWidth || 1));
    const viewportHeight = Math.max(1, Number(globalThis.innerHeight || document.documentElement?.clientHeight || 1));
    const bubbleWidth = Math.max(1, Number(tooltip.offsetWidth || tooltip.getBoundingClientRect?.().width || 1));
    const bubbleHeight = Math.max(1, Number(tooltip.offsetHeight || tooltip.getBoundingClientRect?.().height || 1));
    const targetCenter = target.left + target.width / 2;
    const left = Math.max(8, Math.min(viewportWidth - bubbleWidth - 8, targetCenter - bubbleWidth / 2));
    const belowTop = target.bottom + 10;
    const belowFits = belowTop + bubbleHeight <= viewportHeight - 8;
    const top = belowFits ? belowTop : Math.max(8, target.top - bubbleHeight - 10);
    const arrowLeft = Math.max(14, Math.min(bubbleWidth - 14, targetCenter - left));
    tooltip.style.left = `${Math.round(left)}px`;
    tooltip.style.top = `${Math.round(top)}px`;
    tooltip.style.setProperty("--cast-tooltip-arrow-left", `${Math.round(arrowLeft)}px`);
    tooltip.dataset.placement = belowFits ? "below" : "above";
    tooltip.style.visibility = "visible";
  }

  _hideCastFocusTooltip() {
    if (this._castFocusTooltipTimer) clearTimeout(this._castFocusTooltipTimer);
    if (this._castFocusTooltipDismissTimer) clearTimeout(this._castFocusTooltipDismissTimer);
    this._castFocusTooltipTimer = null;
    this._castFocusTooltipDismissTimer = null;
    this._castFocusTooltipElement = null;
    const tooltip = this.shadowRoot?.getElementById("cast-focus-tooltip");
    if (tooltip) {
      tooltip.hidden = true;
      tooltip.textContent = "";
      tooltip.style.removeProperty("left");
      tooltip.style.removeProperty("top");
      tooltip.style.removeProperty("visibility");
      tooltip.style.removeProperty("--cast-tooltip-arrow-left");
      delete tooltip.dataset.placement;
    }
  }

  _scheduleCastFocusTooltip(element) {
    if (!FITNESS_TV_CAST_RECEIVER || !element) return;
    if (this._castFocusTooltipElement === element && (this._castFocusTooltipTimer || this._castFocusTooltipDismissTimer)) return;
    this._hideCastFocusTooltip();
    const message = this._castFocusTooltipText(element);
    if (!message) return;
    this._castFocusTooltipElement = element;
    this._castFocusTooltipTimer = setTimeout(() => {
      this._castFocusTooltipTimer = null;
      if (this._castFocusTooltipElement !== element || !this._visibleCastRemoteElement(element)) return;
      const tooltip = this.shadowRoot?.getElementById("cast-focus-tooltip");
      if (!tooltip) return;
      tooltip.textContent = message;
      this._positionCastFocusTooltip(tooltip, element);
      this._castFocusTooltipDismissTimer = setTimeout(() => {
        if (this._castFocusTooltipElement === element) this._hideCastFocusTooltip();
      }, FITNESS_TV_FOCUS_TOOLTIP_VISIBLE_MS);
    }, FITNESS_TV_FOCUS_TOOLTIP_DELAY_MS);
  }

  _handleCastPointerHover(event, entering) {
    if (!FITNESS_TV_CAST_RECEIVER || event?.pointerType === "touch") return;
    const element = this._castSelectableFromEvent(event);
    if (entering) {
      if (element) this._scheduleCastFocusTooltip(element);
      return;
    }
    if (!element || this._castFocusTooltipElement !== element) return;
    const related = event?.relatedTarget;
    if (related && (related === element || element.contains?.(related))) return;
    this._hideCastFocusTooltip();
  }

  _scheduleCastFrameworkRemoteAdapter() {
    if (!FITNESS_TV_CAST_RECEIVER) return;
    this._unbindCastFrameworkRemoteAdapter();
    const delays = [0, 250, 1000, 3000];
    this._castCafRemoteTimers = delays.map((delay) => setTimeout(() => {
      if (!this.isConnected || this._castCafRemoteDetected) return;
      this._bindCastFrameworkRemoteAdapter();
    }, delay));
  }

  _bindCastFrameworkRemoteAdapter() {
    if (!FITNESS_TV_CAST_RECEIVER || this._castCafRemoteDetected) return false;
    try {
      // Fitness runs inside Home Assistant's Lovelace Cast receiver and owns its
      // music through the dashboard Audio/MA transports. Detect CAF so we can
      // report receiver capabilities, but do not subscribe to PlayerManager
      // CAF play/pause/stop/seek requests belong to the framework's own media
      // pipeline and mirroring them into Fitness can create a play/error/retry
      // feedback loop while our independent HTML audio element is active.
      const framework = globalThis.cast?.framework;
      const context = framework?.CastReceiverContext?.getInstance?.();
      if (!context) return false;
      this._castCafRemoteDetected = true;
      this._registerCastRemoteCapability("cast-caf", "receiver_context");
      this._recordCastRemoteDiagnostic("adapter", "Cast CAF receiver detected");
      return true;
    } catch (err) {
      this._recordCastRemoteDiagnostic("adapter", `Cast CAF unavailable · ${err?.name || "error"}`);
      return false;
    }
  }

  _unbindCastFrameworkRemoteAdapter() {
    for (const timer of this._castCafRemoteTimers || []) clearTimeout(timer);
    this._castCafRemoteTimers = [];
    this._castCafRemoteBindings = [];
    this._castCafRemoteDetected = false;
  }

  _bindBrowserMediaSessionAdapter() {
    if (!FITNESS_TV_CAST_RECEIVER || !globalThis.navigator?.mediaSession?.setActionHandler) return false;
    const mediaSession = globalThis.navigator.mediaSession;
    const definitions = [
      ["play", "media_play"], ["pause", "media_pause"], ["stop", "media_stop"],
      ["previoustrack", "media_previous"], ["nexttrack", "media_next"],
      ["seekbackward", "media_rewind"], ["seekforward", "media_forward"], ["seekto", "media_seek"],
    ];
    this._browserMediaSessionActions = [];
    for (const [browserAction, remoteAction] of definitions) {
      try {
        mediaSession.setActionHandler(browserAction, (details = {}) => {
          this._registerCastRemoteCapability("media-session", remoteAction);
          if (remoteAction === "media_seek") {
            void this._dispatchCastRemoteMediaAction(remoteAction, "media-session", {position:this._mediaSeconds(details.seekTime)});
          } else if (remoteAction === "media_forward" || remoteAction === "media_rewind") {
            void this._dispatchCastRemoteMediaAction(remoteAction, "media-session", {offset:this._mediaSeconds(details.seekOffset)});
          } else {
            void this._dispatchCastRemoteMediaAction(remoteAction, "media-session");
          }
        });
        this._browserMediaSessionActions.push(browserAction);
      } catch (_err) {}
    }
    if (this._browserMediaSessionActions.length) {
      this._registerCastRemoteCapability("media-session", "media_controls");
      this._recordCastRemoteDiagnostic("adapter", `Media Session · ${this._browserMediaSessionActions.length}`);
    }
    return Boolean(this._browserMediaSessionActions.length);
  }

  _unbindBrowserMediaSessionAdapter() {
    const mediaSession = globalThis.navigator?.mediaSession;
    if (!mediaSession?.setActionHandler) return;
    for (const action of this._browserMediaSessionActions || []) {
      try { mediaSession.setActionHandler(action, null); } catch (_err) {}
    }
    this._browserMediaSessionActions = [];
  }

  async _dispatchCastRemoteMediaAction(action, source = "key", data = {}) {
    if (!FITNESS_TV_CAST_RECEIVER || !this._canControlProfile) return false;
    const now = performance.now();
    if (action === this._castRemoteMediaLastAction
      && source !== this._castRemoteMediaLastSource
      && now - Number(this._castRemoteMediaLastAt || 0) < FITNESS_TV_REMOTE_MEDIA_DEDUPE_MS) return true;
    this._castRemoteMediaLastAction = action;
    this._castRemoteMediaLastSource = source;
    this._castRemoteMediaLastAt = now;
    this._castRemoteUserEngaged = true;
    this._castRemoteLastNonBackInputAt = now;
    this._clearCastExitConfirmation();
    this._markOledInteraction();
    this._recordCastRemoteDiagnostic("media", `${action} · ${source}`);
    try {
      if (action === "media_toggle") {
        if (this._musicPlaying()) await this._pauseMusic();
        else await this._playMusic();
      } else if (action === "media_play") {
        if (!this._musicPlaying()) await this._playMusic();
      } else if (action === "media_pause") {
        if (this._musicPlaying()) await this._pauseMusic();
      } else if (action === "media_stop") {
        const result = await this._sendMediaCommand("stop", {reason:"tv_remote_media_key"});
        if (!result?.sent) await this._heartbeat();
      } else if (action === "media_next") {
        await this._playlistTransport("next");
      } else if (action === "media_previous") {
        await this._playlistTransport("previous");
      } else if (["media_forward","media_rewind","media_seek"].includes(action)) {
        const snapshot = this._mediaProgressSnapshot();
        const duration = this._mediaSeconds(snapshot?.duration);
        let position = this._mediaSeconds(snapshot?.position);
        const seekOffset = this._mediaSeconds(data.offset) || 10;
        if (action === "media_forward") position += seekOffset;
        else if (action === "media_rewind") position -= seekOffset;
        else position = this._mediaSeconds(data.position);
        position = Math.max(0, duration > 0 ? Math.min(duration, position) : position);
        if (duration > 0 || action === "media_seek") await this._sendMediaCommand("seek", {position});
      }
      return true;
    } catch (err) {
      this._recordCastRemoteDiagnostic("media-error", err?.message || "failed");
      return false;
    }
  }

  _castRemoteBackKey(event) {
    return this._castRemoteInputAction(event) === "back";
  }

  _consumeCastRemoteEvent(event) {
    try { event?.preventDefault?.(); } catch (_err) {}
    try { event?.stopPropagation?.(); } catch (_err) {}
    try { event?.stopImmediatePropagation?.(); } catch (_err) {}
  }

  _visibleCastRemoteElement(element) {
    if (!element?.getBoundingClientRect) return false;
    const rect = element.getBoundingClientRect();
    if (rect.width <= 2 || rect.height <= 2) return false;
    const style = globalThis.getComputedStyle?.(element);
    return style?.display !== "none" && style?.visibility !== "hidden" && style?.opacity !== "0";
  }

  _castRemoteSections() {
    const sections = [];
    const toolbar = this.shadowRoot?.querySelector(".tv-toolbar");
    if (this._visibleCastRemoteElement(toolbar)) sections.push(toolbar);
    for (const slot of this.shadowRoot?.querySelectorAll(".tv-card-slot") || []) {
      if (this._visibleCastRemoteElement(slot)) sections.push(slot);
    }
    return sections;
  }

  _castRemoteSectionName(section) {
    const labels = this._labels();
    if (!section) return "";
    if (section.classList?.contains("tv-toolbar")) return String(labels.cast_top_bar);
    const cardId = String(section.dataset?.cardId || "").trim();
    if (!cardId) return String(labels.cast_card);
    const item = FITNESS_TV_CARD_CATALOG.find((entry) => entry.id === cardId);
    const labelKey = String(item?.label || "");
    return String(labels[labelKey]);
  }

  _castRemoteSectionIdentity(section) {
    if (!section) return "";
    if (section.classList?.contains("tv-toolbar")) return "toolbar";
    const cardId = String(section.dataset?.cardId || "");
    return cardId ? `card:${cardId}` : "";
  }

  _castRemoteFocusSnapshot() {
    if (!FITNESS_TV_CAST_RECEIVER || !this._castRemoteSection) return null;
    return {
      mode:this._castRemoteMode,
      section:this._castRemoteSectionIdentity(this._castRemoteSection),
      focus:this._castRemoteFocusIdentity(this._castRemoteFocusElement || this._deepActiveElement()),
      previous:(this._castRemoteFocusTrail || [])
        .filter((item) => item?.section === this._castRemoteSection)
        .map((item) => String(item?.identity || this._castRemoteFocusIdentity(item?.element)))
        .filter(Boolean),
    };
  }

  _restoreCastRemoteFocusSnapshot(snapshot) {
    if (!snapshot || !FITNESS_TV_CAST_RECEIVER) {
      this._ensureCastRemoteOuterFocus();
      return;
    }
    const sections = this._castRemoteSections();
    const section = sections.find((item) => this._castRemoteSectionIdentity(item) === snapshot.section) || sections[0];
    if (!section) return;
    this._castRemoteSection = section;
    if (snapshot.mode !== "inner") {
      this._castRemoteMode = "outer";
      this._clearCastRemoteFocus();
      this._markCastRemoteSection(section, false);
      return;
    }
    const controls = this._castRemoteInnerElements(section);
    if (!controls.length) {
      this._castRemoteMode = "outer";
      this._markCastRemoteSection(section, false);
      return;
    }
    const identities = [snapshot.focus, ...(snapshot.previous || []).slice().reverse()].filter(Boolean);
    let target = null;
    for (const identity of identities) {
      target = controls.find((item) => this._castRemoteFocusIdentity(item) === identity) || null;
      if (target) break;
    }
    target ||= controls[0];
    this._castRemoteMode = "inner";
    this._castRemoteFocusTrail = [];
    this._markCastRemoteSection(section, true);
    target.focus?.({preventScroll:true});
    this._castRemoteLastInnerFocus.set(section, target);
    this._markCastRemoteFocus(target, false, false);
  }

  _castFocusableElements() {
    return this._castFocusableElementsWithin(this.shadowRoot);
  }

  _castFocusableElementsWithin(root = this.shadowRoot) {
    const found = [];
    const scan = (node) => {
      if (!node?.querySelectorAll) return;
      for (const entity of node.querySelectorAll(".entity-link[data-more-info]")) {
        if (!entity.hasAttribute("tabindex")) entity.tabIndex = 0;
        if (!entity.hasAttribute("role")) entity.setAttribute("role", "button");
      }
      for (const element of node.querySelectorAll("button:not([disabled]),select:not([disabled]),input:not([disabled]),textarea:not([disabled]),a[href],[role='button'],[tabindex]:not([tabindex='-1'])")) {
        if (this._visibleCastRemoteElement(element) && !element.closest?.(".layout-tools")) found.push(element);
      }
      for (const host of node.querySelectorAll("*")) {
        if (host.shadowRoot) scan(host.shadowRoot);
      }
    };
    scan(root);
    return [...new Set(found)];
  }

  _castRemoteInnerElements(section = this._castRemoteSection) {
    const modalRoot = this.shadowRoot?.getElementById("modal-root");
    if (modalRoot?.children?.length && this._visibleCastRemoteElement(modalRoot.firstElementChild)) {
      const modalControls = this._castFocusableElementsWithin(modalRoot);
      if (modalControls.length) return modalControls;
    }
    return section ? this._castFocusableElementsWithin(section) : [];
  }

  _clearCastRemoteSectionMarks() {
    this.shadowRoot?.querySelectorAll(".fitness-remote-section-selected,.fitness-remote-section-active").forEach((element) => {
      element.classList.remove("fitness-remote-section-selected", "fitness-remote-section-active");
    });
  }

  _markCastRemoteSection(section, active = false) {
    if (!section) return;
    this._clearCastRemoteSectionMarks();
    section.classList.add(active ? "fitness-remote-section-active" : "fitness-remote-section-selected");
    section.scrollIntoView?.({block:"nearest", inline:"nearest"});
    this._animateRemoteSectionInterior(section, active);
  }

  _clearCastRemoteFocus() {
    if (this._castRemotePressTimer) clearTimeout(this._castRemotePressTimer);
    this._castRemotePressTimer = null;
    const element = this._castRemoteFocusElement;
    const saved = element && this._castRemoteFocusStyles?.get?.(element);
    if (element?.style && saved) {
      for (const [property, value] of Object.entries(saved)) element.style[property] = value;
    }
    this._castRemoteFocusElement = null;
    this._hideCastFocusTooltip();
  }

  _castRemoteFocusIdentity(element) {
    if (!element) return "";
    const data = element.dataset || {};
    return [
      String(element.id || ""),
      String(data.entity || data.moreInfo || data.cardId || data.action || ""),
      String(element.getAttribute?.("aria-label") || element.getAttribute?.("title") || ""),
      String(element.tagName || ""),
    ].join("|");
  }

  _markCastRemoteFocus(element, pressed = false, record = true) {
    if (!element?.style) return;
    if (this._castRemoteFocusElement !== element) {
      const previous = this._castRemoteFocusElement;
      if (record && previous && this._visibleCastRemoteElement(previous)) {
        this._castRemoteFocusTrail ||= [];
        this._castRemoteFocusTrail.push({
          section:this._castRemoteSection,
          element:previous,
          identity:this._castRemoteFocusIdentity(previous),
        });
        if (this._castRemoteFocusTrail.length > 40) this._castRemoteFocusTrail.shift();
      }
      this._clearCastRemoteFocus();
      this._castRemoteFocusStyles ||= new WeakMap();
      this._castRemoteFocusStyles.set(element, {
        outline:element.style.outline,
        outlineOffset:element.style.outlineOffset,
        boxShadow:element.style.boxShadow,
        transform:element.style.transform,
        transformOrigin:element.style.transformOrigin,
        transition:element.style.transition,
        zIndex:element.style.zIndex,
        filter:element.style.filter,
        borderColor:element.style.borderColor,
        backgroundColor:element.style.backgroundColor,
        accentColor:element.style.accentColor,
      });
      this._castRemoteFocusElement = element;
    }
    const isRange = element.matches?.("input[type='range']");
    const isField = element.matches?.("select,input:not([type='button']):not([type='submit']):not([type='reset']),textarea");
    element.style.outline = "2px solid color-mix(in srgb,var(--primary-color,#03a9f4) 92%,white 8%)";
    element.style.outlineOffset = "4px";
    element.style.borderColor = "color-mix(in srgb,var(--primary-color,#03a9f4) 90%,white 10%)";
    element.style.boxShadow = pressed
      ? "0 0 0 3px color-mix(in srgb,var(--primary-color,#03a9f4) 40%,transparent),0 5px 12px rgba(0,0,0,.25)"
      : "0 0 0 4px color-mix(in srgb,var(--primary-color,#03a9f4) 46%,transparent),0 7px 16px rgba(0,0,0,.28)";
    element.style.transition = "transform .10s ease-out, box-shadow .10s ease-out, outline-color .10s ease-out, border-color .10s ease-out, background-color .10s ease-out";
    element.style.transformOrigin = "center center";
    element.style.zIndex = "90";
    element.style.filter = "none";
    element.style.transform = pressed ? "translate3d(0,0,0) scale(.985)" : "translate3d(0,-1px,0) scale(1.018)";
    if (isRange) {
      element.style.accentColor = "var(--primary-color,#03a9f4)";
    } else if (isField) {
      element.style.backgroundColor = "color-mix(in srgb,var(--primary-color,#03a9f4) 18%,var(--secondary-background-color))";
    } else {
      element.style.backgroundColor = "color-mix(in srgb,var(--primary-color,#03a9f4) 24%,var(--secondary-background-color))";
    }
    element.scrollIntoView?.({block:"nearest",inline:"nearest"});
    this._scheduleCastFocusTooltip(element);
    if (pressed) {
      if (this._castRemotePressTimer) clearTimeout(this._castRemotePressTimer);
      this._castRemotePressTimer = setTimeout(() => {
        if (this._castRemoteFocusElement === element) {
          element.style.transform = "translate3d(0,-1px,0) scale(1.018)";
          element.style.filter = "none";
          element.style.boxShadow = "0 0 0 4px color-mix(in srgb,var(--primary-color,#03a9f4) 46%,transparent),0 7px 16px rgba(0,0,0,.28)";
        }
      }, 90);
    }
  }

  _restoreCastRemotePreviousFocus() {
    const controls = this._castRemoteInnerElements(this._castRemoteSection);
    while (this._castRemoteFocusTrail?.length) {
      const previous = this._castRemoteFocusTrail.pop();
      if (previous?.section !== this._castRemoteSection) continue;
      let element = previous?.element;
      if (!controls.includes(element) || element?.disabled || !this._visibleCastRemoteElement(element)) {
        const identity = String(previous?.identity || "");
        element = identity
          ? controls.find((candidate) => this._castRemoteFocusIdentity(candidate) === identity)
          : null;
      }
      if (!element || element.disabled || !this._visibleCastRemoteElement(element)) continue;
      this._endCastRemoteTextEntry("restore-focus");
      element.focus?.({preventScroll:true});
      this._castRemoteLastInnerFocus.set(this._castRemoteSection, element);
      this._markCastRemoteFocus(element, false, false);
      return true;
    }
    return false;
  }

  _ensureCastRemoteOuterFocus() {
    if (!FITNESS_TV_CAST_RECEIVER || this._castRemoteMode === "inner") return;
    const sections = this._castRemoteSections();
    if (!sections.length) return;
    if (!sections.includes(this._castRemoteSection)) this._castRemoteSection = sections[0];
    this._castRemoteMode = "outer";
    this._clearCastRemoteFocus();
    this._markCastRemoteSection(this._castRemoteSection, false);
  }

  _enterCastRemoteSection(section = this._castRemoteSection) {
    if (!section) return false;
    this._clearCastExitConfirmation();
    const controls = this._castRemoteInnerElements(section);
    if (!controls.length) {
      this._recordCastRemoteDiagnostic("enter", `${this._castRemoteSectionName(section)} has no controls`);
      this._markCastRemoteSection(section, false);
      return false;
    }
    this._castRemoteMode = "inner";
    this._castRemoteSection = section;
    this._castRemoteFocusTrail = [];
    this._markCastRemoteSection(section, true);
    let target = this._castRemoteLastInnerFocus.get(section);
    if (!controls.includes(target)) target = controls[0];
    target.focus?.({preventScroll:true});
    this._markCastRemoteFocus(target);
    this._recordCastRemoteDiagnostic("enter", this._castRemoteSectionName(section));
    return true;
  }

  _leaveCastRemoteSection(source = "back") {
    this._endCastRemoteTextEntry(`leave-${source}`);
    this._clearCastExitConfirmation();
    const section = this._castRemoteSection;
    const active = this._deepActiveElement();
    if (section && active) this._castRemoteLastInnerFocus.set(section, active);
    const modalRoot = this.shadowRoot?.getElementById("modal-root");
    if (modalRoot?.children?.length) modalRoot.replaceChildren();
    this._castRemoteMode = "outer";
    this._castRemoteFocusTrail = [];
    this._clearCastRemoteFocus();
    const sections = this._castRemoteSections();
    if (!sections.includes(section)) this._castRemoteSection = sections[0] || null;
    this._markCastRemoteSection(this._castRemoteSection, false);
    this._recordCastRemoteDiagnostic("back", `leave section via ${source}`);
  }

  _moveCastRemoteSpatial(items, current, key, {outer = false} = {}) {
    if (!items.length) return null;
    if (!items.includes(current)) return items[0];
    const toolbar = outer ? this.shadowRoot?.querySelector(".tv-toolbar") : null;
    if (outer) {
      const cards = items.filter((item) => item !== toolbar);
      if (current === toolbar) {
        if (key !== "ArrowDown") return current;
        cards.sort((a, b) => {
          const ar = a.getBoundingClientRect();
          const br = b.getBoundingClientRect();
          return Math.abs(ar.top - br.top) > 8 ? ar.top - br.top : ar.left - br.left;
        });
        return cards[0] || current;
      }
      if (cards.includes(current)) {
        // Once navigation has entered the card grid, Left/Right/Down are card
        // only. Up first looks for a card above; only a top-row card with no
        // upper card can return to the toolbar. This prevents diagonal spatial
        // scoring from unexpectedly jumping back into the upper bar.
        const cardTarget = this._moveCastRemoteSpatial(cards, current, key);
        if (key === "ArrowUp" && cardTarget === current) return toolbar || current;
        return cardTarget || current;
      }
    }
    const origin = current.getBoundingClientRect();
    const ox = origin.left + origin.width / 2;
    const oy = origin.top + origin.height / 2;
    const horizontal = key === "ArrowLeft" || key === "ArrowRight";
    const sign = (key === "ArrowLeft" || key === "ArrowUp") ? -1 : 1;
    let best = null;
    let bestScore = Infinity;
    for (const candidate of items) {
      if (candidate === current) continue;
      const rect = candidate.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const primary = horizontal ? (cx - ox) : (cy - oy);
      if (primary * sign <= 2) continue;
      const secondary = horizontal ? Math.abs(cy - oy) : Math.abs(cx - ox);
      const score = Math.abs(primary) + secondary * 2.2;
      if (score < bestScore) { bestScore = score; best = candidate; }
    }
    return best || current;
  }

  _handleCastRemoteArrow(event, action = this._castRemoteInputAction(event)) {
    const rawKey = String(event?.key || "");
    const key = ({left:"ArrowLeft",right:"ArrowRight",up:"ArrowUp",down:"ArrowDown"})[action]
      || (["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(rawKey) ? rawKey : "");
    if (!key) return false;
    this._registerCastRemoteCapability("keyboard", action, event);
    this._consumeCastRemoteEvent(event);
    this._castRemoteUserEngaged = true;
    this._markOledInteraction();
    this._clearCastExitConfirmation();
    if (this._castRemoteMode !== "inner") {
      const sections = this._castRemoteSections();
      if (!sections.length) return true;
      const current = sections.includes(this._castRemoteSection) ? this._castRemoteSection : sections[0];
      const next = this._moveCastRemoteSpatial(sections, current, key, {outer:true});
      if (next && next !== current) {
        this._castRemoteSectionTrail ||= [];
        this._castRemoteSectionTrail.push(current);
        if (this._castRemoteSectionTrail.length > 24) this._castRemoteSectionTrail.shift();
      }
      this._castRemoteSection = next || current;
      this._markCastRemoteSection(this._castRemoteSection, false);
      this._recordCastRemoteDiagnostic("nav", `${key} · ${this._castRemoteSectionName(this._castRemoteSection)}`);
      return true;
    }
    const controls = this._castRemoteInnerElements();
    if (!controls.length) {
      this._leaveCastRemoteSection("empty");
      return true;
    }
    let active = this._deepActiveElement();
    if (!controls.includes(active)) active = controls[0];
    const tag = String(active?.tagName || "").toUpperCase();
    const type = String(active?.type || "").toLowerCase();
    if (tag === "INPUT" && String(active?.type || "").toLowerCase() === "range" && ["ArrowLeft","ArrowRight"].includes(key)) {
      if (key === "ArrowLeft") active.stepDown?.(); else active.stepUp?.();
      active.dispatchEvent?.(new Event("input", {bubbles:true,composed:true}));
      active.dispatchEvent?.(new Event("change", {bubbles:true,composed:true}));
      this._markCastRemoteFocus(active, true);
      return true;
    }
    if (tag === "INPUT" && type === "range" && ["ArrowUp","ArrowDown"].includes(key)) {
      if (!this._restoreCastRemotePreviousFocus()) this._leaveCastRemoteSection("range-exit");
      return true;
    }
    if (tag === "SELECT" && ["ArrowUp","ArrowDown"].includes(key)) {
      const delta = key === "ArrowUp" ? -1 : 1;
      const max = Math.max(0, Number(active.options?.length || 1) - 1);
      let nextIndex = Number(active.selectedIndex || 0);
      do {
        nextIndex = Math.max(0, Math.min(max, nextIndex + delta));
      } while (active.options?.[nextIndex]?.disabled && nextIndex > 0 && nextIndex < max);
      if (!active.options?.[nextIndex]?.disabled) active.selectedIndex = nextIndex;
      active.dispatchEvent?.(new Event("change", {bubbles:true,composed:true}));
      this._markCastRemoteFocus(active, true);
      return true;
    }
    const best = this._moveCastRemoteSpatial(controls, active, key);
    if (best) {
      this._endCastRemoteTextEntry("navigate");
      best.focus?.({preventScroll:true});
      this._castRemoteLastInnerFocus.set(this._castRemoteSection, best);
      this._markCastRemoteFocus(best);
    }
    return true;
  }

  _handleCastRemoteActivate(event, action = this._castRemoteInputAction(event)) {
    const legacyActivate = ["Enter","NumpadEnter","Select","Accept"," "].includes(String(event?.key || ""));
    if (action !== "activate" && !legacyActivate) return false;
    this._registerCastRemoteCapability("keyboard", action, event);
    this._consumeCastRemoteEvent(event);
    this._markOledInteraction();
    this._clearCastExitConfirmation();
    if (this._castRemoteMode !== "inner") {
      this._enterCastRemoteSection();
      return true;
    }
    const controls = this._castRemoteInnerElements();
    if (!controls.length) return true;
    let target = this._deepActiveElement();
    if (!controls.includes(target)) target = controls[0];
    target.focus?.({preventScroll:true});
    this._castRemoteLastInnerFocus.set(this._castRemoteSection, target);
    this._markCastRemoteFocus(target, true);
    if (this._castRemoteTextEntryControl(target)) this._beginCastRemoteTextEntry(target, "activate");
    else this._endCastRemoteTextEntry("activate-control");
    target.click?.();
    this._recordCastRemoteDiagnostic("ok", target.id || target.getAttribute?.("aria-label") || target.tagName || "control");
    setTimeout(() => {
      if (this._castRemoteMode !== "inner") return;
      const refreshed = this._castRemoteInnerElements();
      const focused = this._deepActiveElement();
      if (refreshed.length && !refreshed.includes(focused)) {
        if (!this._restoreCastRemotePreviousFocus()) {
          refreshed[0].focus?.({preventScroll:true});
          this._markCastRemoteFocus(refreshed[0], false, false);
        }
      }
    }, 60);
    return true;
  }

  _handleCastRemoteCancel(event, source = "cancel") {
    if (!FITNESS_TV_CAST_RECEIVER) return false;
    this._registerCastRemoteCapability("keyboard", "cancel", event);
    this._consumeCastRemoteEvent(event);
    this._markOledInteraction();
    this._clearCastExitConfirmation();
    this._castRemoteBackLastEventAt = 0;
    // Escape is used by native TV widgets and browser chrome. It may back out
    // of an entered Fitness section, but it must never arm or finish Cast exit.
    if (this._castRemoteMode === "inner") this._leaveCastRemoteSection(source);
    else this._ensureCastRemoteOuterFocus();
    this._ensureCastBackGuard();
    return true;
  }

  _castRemoteBackSignature(event) {
    if (!event) return "";
    return [
      String(event.key || ""),
      String(event.code || ""),
      String(Number(event.keyCode ?? event.which ?? 0) || 0),
    ].join("|");
  }

  _castRemoteCanArmGuardedExit(now) {
    if (!this._castRemoteBackUnreliable) return true;
    const lastInput = Number(this._castRemoteLastNonBackInputAt || 0);
    return lastInput > 0 && now - lastInput <= FITNESS_TV_BACK_GUARDED_RECENT_INPUT_MS;
  }

  _handleCastRemoteBackPress(event, source = "key") {
    if (event) this._registerCastRemoteCapability(source === "history" ? "history" : "keyboard", "back", event);
    else if (source) this._registerCastRemoteCapability(source, "back");
    this._consumeCastRemoteEvent(event);
    const now = performance.now();
    const physicalBack = source === "keydown" && !!event;
    if (Number(this._castRemoteNativeControlBackSuppressUntil || 0) > now) {
      this._clearCastExitConfirmation();
      this._castRemoteBackLastEventAt = 0;
      this._ensureCastBackGuard();
      this._recordCastRemoteDiagnostic("back", `suppressed after native picker · ${source}`);
      return true;
    }
    if (Number(this._castRemoteTextEntryBackSuppressUntil || 0) > now) {
      this._clearCastExitConfirmation();
      this._castRemoteBackLastEventAt = 0;
      this._ensureCastBackGuard();
      this._recordCastRemoteDiagnostic("back", `suppressed after text input · ${source}`);
      return true;
    }
    const previousEventAt = Number(this._castRemoteBackLastEventAt || 0);
    this._castRemoteBackLastEventAt = now;
    // Treat rapid Back events as one physical press. This covers keydown +
    // popstate duplicates and, importantly, auto-repeat while the button is
    // held. A Cast exit therefore requires release/idle and a genuinely second
    // press; holding Back can never satisfy the confirmation by itself.
    if (previousEventAt && now - previousEventAt < FITNESS_TV_BACK_DISTINCT_PRESS_MS) {
      this._ensureCastBackGuard();
      return true;
    }
    this._markOledInteraction();

    if (this._castRemoteMode === "inner") {
      this._clearCastExitConfirmation();
      // Back always exits the entered section in one step. Focus history is
      // reserved for range navigation and recovery after a control disables;
      // walking it here makes Back appear to dismiss tooltip text instead.
      this._leaveCastRemoteSection(source);
      if (physicalBack) {
        this._castRemoteLastPhysicalBackAt = now;
        this._castRemoteUserEngaged = true;
      }
      this._ensureCastBackGuard();
      return true;
    }

    this._ensureCastRemoteOuterFocus();
    while (this._castRemoteSectionTrail?.length) {
      const previousSection = this._castRemoteSectionTrail.pop();
      if (!this._castRemoteSections().includes(previousSection) || !this._visibleCastRemoteElement(previousSection)) continue;
      this._castRemoteSection = previousSection;
      this._markCastRemoteSection(previousSection, false);
      this._ensureCastBackGuard();
      this._recordCastRemoteDiagnostic("back", `restore ${this._castRemoteSectionName(previousSection)}`);
      return true;
    }
    // Browser history is only a containment/fallback mechanism. Cast runtimes
    // can emit popstate while booting or replacing their receiver route, so a
    // history event must never arm or complete the destructive double-Back
    // action. Only an actual remote Back keydown is eligible to exit Cast.
    if (!physicalBack) {
      this._ensureCastBackGuard();
      this._recordCastRemoteDiagnostic("back", `non-physical top-level Back ignored · ${source}`);
      return true;
    }
    this._castRemoteLastPhysicalBackAt = now;

    // During receiver bootstrap some TV/browser combinations emit stray Back
    // key events while Cast swaps from the HA splash/connection route to the
    // dashboard. Do not let startup noise arm an exit. A real D-pad/OK/media
    // interaction proves the user has taken control and lifts the grace early.
    if (!this._castRemoteUserEngaged && now < Number(this._castRemoteExitAllowedAfter || 0)) {
      // A Back arriving before the user has touched D-pad/OK/media controls is
      // receiver/system noise on several TV runtimes. Remember that this
      // session needs guarded exit semantics instead of ever trusting idle
      // top-level Back events.
      this._castRemoteBackUnreliable = true;
      this._clearCastExitConfirmation();
      this._castRemoteBackLastEventAt = 0;
      this._ensureCastBackGuard();
      this._recordCastRemoteDiagnostic("back", "startup/system Back detected; guarded exit enabled");
      return true;
    }

    const signature = this._castRemoteBackSignature(event);
    if (Number(this._castRemoteExitArmedUntil || 0) > now) {
      const authorized = String(this._castRemoteExitAuthorization || "");
      if (authorized && authorized === signature) {
        const quitAuthorization = authorized;
        this._castRemoteExitArmedUntil = 0;
        if (this._castRemoteExitTimer) clearTimeout(this._castRemoteExitTimer);
        this._castRemoteExitTimer = null;
        const notice = this.shadowRoot?.getElementById("cast-exit-confirm");
        if (notice) notice.hidden = true;
        void this._quitCastFromRemote("double back", quitAuthorization);
        return true;
      }
      // A different/synthetic Back event can dismiss the prompt but can never
      // complete an exit that another key source armed.
      this._clearCastExitConfirmation();
      this._ensureCastBackGuard();
      return true;
    }

    if (!this._castRemoteCanArmGuardedExit(now)) {
      this._clearCastExitConfirmation();
      this._castRemoteBackLastEventAt = 0;
      this._ensureCastBackGuard();
      this._recordCastRemoteDiagnostic("back", "idle/system Back ignored by guarded exit");
      return true;
    }

    this._castRemoteExitAuthorization = signature;
    this._showCastExitConfirmation();
    // _showCastExitConfirmation does not own authorization; restore the exact
    // physical-key signature after it updates the visible timer.
    this._castRemoteExitAuthorization = signature;
    this._ensureCastBackGuard();
    return true;
  }

  _beginCastRemoteBack(event, source = "keydown") {
    return this._handleCastRemoteBackPress(event, source);
  }

  _handleCastKeyup(event) {
    if (!FITNESS_TV_CAST_RECEIVER || !this._castRemoteBackKey(event)) return;
    if (this._castRemoteTextEntryActive || (this._castRemoteBackspaceKey(event) && this._castRemoteTextEntryFromEvent(event))) return;
    // Sony/Android TV does not reliably deliver keyup. When it does, consume it
    // but never use it to distinguish short vs long presses.
    this._consumeCastRemoteEvent(event);
  }

  _handleCastRemoteShortBack(source = "key") {
    return this._handleCastRemoteBackPress(null, source);
  }

  _handleCastPopstate(event) {
    if (!FITNESS_TV_CAST_RECEIVER) return;
    this._castBackGuardInstalled = false;
    const now = performance.now();
    if (Number(this._castRemoteNativeControlBackSuppressUntil || 0) > now || Number(this._castRemoteNavigationHistorySuppressUntil || 0) > now) {
      this._clearCastExitConfirmation();
      this._castRemoteBackLastEventAt = 0;
      this._ensureCastBackGuard();
      this._recordCastRemoteDiagnostic("back", "swallowed native-picker/navigation history Back");
      return;
    }
    if (this._castRemoteTextEntryActive || Number(this._castRemoteTextEntryBackSuppressUntil || 0) > now) {
      this._clearCastExitConfirmation();
      this._castRemoteBackLastEventAt = 0;
      this._castRemoteTextEntryBackSuppressUntil = Math.max(
        Number(this._castRemoteTextEntryBackSuppressUntil || 0),
        now + FITNESS_TV_TEXT_ENTRY_BACK_SUPPRESS_MS,
      );
      this._releaseCastRemoteTextEntrySoon("history-back");
      this._ensureCastBackGuard();
      this._recordCastRemoteDiagnostic("text-entry", "swallowed keyboard/history Back");
      return;
    }
    // Never feed popstate into the Cast-exit confirmation state machine.
    // Some Cast/TV runtimes generate history transitions during receiver
    // startup and route replacement without any user Back press. History may
    // still act as a best-effort one-level Back when a platform exposes no
    // keyboard Back event, but it can never terminate Cast.
    const recentPhysicalBack = now - Number(this._castRemoteLastPhysicalBackAt || 0) < FITNESS_TV_BACK_DISTINCT_PRESS_MS;
    if (this._castRemoteMode === "inner" && !recentPhysicalBack) {
      this._clearCastExitConfirmation();
      this._leaveCastRemoteSection("history-fallback");
    }
    this._ensureCastBackGuard();
    this._recordCastRemoteDiagnostic("back", recentPhysicalBack ? "history duplicate ignored" : "history fallback contained");
  }

  async _quitCastFromRemote(source = "double back", authorization = "") {
    if (!FITNESS_TV_CAST_RECEIVER || this._castRemoteQuitInFlight) return;
    // Destructive receiver shutdown is permitted only by the exact Back-key
    // signature that armed the visible confirmation. Never let lifecycle,
    // history, timers or a future caller stop Cast by reaching this method.
    if (!authorization || authorization !== String(this._castRemoteExitAuthorization || "")) return;
    this._clearCastExitConfirmation();
    this._castRemoteQuitInFlight = true;
    this._recordCastRemoteDiagnostic("QUIT CAST", source);
    try {
      this._captureLocalMediaProgress?.(true);
      if (String(this._currentMediaContentId || this._sharedMediaState?.media_content_id || "").trim()) {
        await this._syncMediaState({playing:false, error:false});
      }
    } catch (_err) {}
    try {
      const target = String(this._activeCastTarget || "").trim();
      if (target && this._profile?.entry_id && this._hass) {
        await this._hass.callService("fitness", "stop_tv_dashboard", {
          config_entry_id:this._profile.entry_id,
          entity_id:target,
        });
      } else if (this._profile?.entry_id && this._hass) {
        await this._hass.callWS({
          type:"fitness/tv/local_cast_stopped",
          profile_entry_id:this._profile.entry_id,
          reason:"tv_remote_double_back",
        }).catch(() => {});
      }
    } catch (err) {
      this._recordCastRemoteDiagnostic("quit-backend", err?.message || "failed");
    }
    try {
      const receiverContext = globalThis.cast?.framework?.CastReceiverContext?.getInstance?.();
      if (receiverContext?.stop) {
        this._recordCastRemoteDiagnostic("quit-receiver", "CastReceiverContext.stop()");
        receiverContext.stop();
        return;
      }
    } catch (err) {
      this._recordCastRemoteDiagnostic("quit-receiver", err?.message || "stop failed");
    }
    try { globalThis.close?.(); } catch (_err) {}
    setTimeout(() => { this._castRemoteQuitInFlight = false; }, 1500);
  }

  _handleCastKeydown(event) {
    if (!FITNESS_TV_CAST_RECEIVER) return;
    const action = this._castRemoteInputAction(event);
    if (!action) return;
    if (this._yieldCastRemoteKeyToTextEntry(event, action)) return;
    if (this._yieldCastRemoteKeyToNativePicker(event, action)) return;
    if (action === "cancel") { this._handleCastRemoteCancel(event, "native-cancel"); return; }
    if (action === "back") {
      this._beginCastRemoteBack(event, "keydown");
      return;
    }
    this._castRemoteUserEngaged = true;
    this._castRemoteLastNonBackInputAt = performance.now();
    if (action === "activate") { this._handleCastRemoteActivate(event, action); return; }
    if (["left","right","up","down"].includes(action)) {
      this._castRemoteNavigationHistorySuppressUntil = performance.now() + FITNESS_TV_NAV_HISTORY_SUPPRESS_MS;
      this._handleCastRemoteArrow(event, action);
      return;
    }
    if (action.startsWith("media_")) {
      this._registerCastRemoteCapability("keyboard", action, event);
      this._consumeCastRemoteEvent(event);
      void this._dispatchCastRemoteMediaAction(action, "keyboard");
    }
  }


  _claimWindowController() {
    const profileId = String(this._profile?.entry_id || "");
    if (!profileId) return;
    const registry = window.__fitnessTvControllers || (window.__fitnessTvControllers = new Map());
    const previous = registry.get(profileId);
    if (previous && previous !== this) {
      previous._hardStopMusic?.();
      previous._hardStopAudio?.(previous._ttsAudio);
      previous._audioOwner = false;
    }
    registry.set(profileId, this);
  }

  _isWindowController() {
    const profileId = String(this._profile?.entry_id || "");
    if (!profileId) return false;
    return window.__fitnessTvControllers?.get(profileId) === this;
  }

  _releaseWindowController() {
    const profileId = String(this._profile?.entry_id || "");
    if (!profileId) return;
    if (window.__fitnessTvControllers?.get(profileId) === this) {
      window.__fitnessTvControllers.delete(profileId);
    }
  }

  _labels(profile = this._profile || this._fallbackProfile) {
    const language = String(profile?.language || this._access?.language || this._hass?.language || "en").toLowerCase().split("-")[0];
    return profile?.labels_by_language?.[language]
      || profile?.labels_by_language?.en
      || profile?.labels
      || this._rootLabelsByLanguage?.[language]
      || this._rootLabelsByLanguage?.en
      || this._rootLabels
      || {};
  }

  async _load() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    try {
      const data = await this._hass.callWS({type:"fitness/dashboard/config"});
      if (_fitnessEnsureFrontendVersion(data?.frontend_version)) return;
      this._allProfiles = data?.profiles || [];
      this._access = data?.access || {role:"none",is_admin:false,session_allowed:false};
      this._rootLabels = data?.labels || {};
      this._rootLabelsByLanguage = data?.labels_by_language || {};
      this._castTargets = Array.isArray(data?.cast_targets) ? data.cast_targets : [];
      this._intensityColors = data?.intensity_colors || {};
      this._fallbackProfile = this._allProfiles[0] || null;
      this._profiles = this._allProfiles.filter((profile) => profile.tv_dashboard?.enabled);
      const configuredProfile = String(this.config?.profile_entry_id || "");
      if (configuredProfile && !this._profiles.some((item) => item.entry_id === configuredProfile)) {
        this._accessDenied = true;
        this._profile = null;
        this._canControlProfile = false;
        this._loaded = true;
        this._render();
        return;
      }
      this._accessDenied = false;
      if (!this._profiles.length) {
        this._profile = null;
        this._canControlProfile = false;
        this._loaded = true;
        this._render();
        return;
      }
      let rememberedTab = "";
      let rememberedBrowser = "";
      try { rememberedTab = String(sessionStorage.getItem(FITNESS_TV_PROFILE_TAB_STORAGE) || ""); } catch (_err) {}
      try { rememberedBrowser = String(localStorage.getItem(FITNESS_TV_PROFILE_STORAGE) || ""); } catch (_err) {}
      this._profile = this._profiles.find((item) => item.entry_id === configuredProfile)
        || this._profiles.find((item) => item.entry_id === rememberedTab)
        || this._profiles.find((item) => item.entry_id === rememberedBrowser)
        || this._profiles[0];
      try { sessionStorage.setItem(FITNESS_TV_PROFILE_TAB_STORAGE, this._profile.entry_id); } catch (_err) {}
      this._canControlProfile = Boolean(this._access?.is_admin || this._profile?.access?.can_control);
      if (this._canControlProfile) this._claimWindowController();
      await this._loadPreferences();
      if (this._canControlProfile) await this._subscribeTvAudio();
      await this._subscribeTvMedia();
      await this._subscribeTvSettings();
      this._loaded = true;
      this._render();
      if (this._canControlProfile) this._startHeartbeat();
      if (!FITNESS_TV_CAST_RECEIVER && this._canControlProfile) {
        void this._resumeRemoteGateways();
        // Load the sender framework without opening a chooser so an existing
        // local Cast session can be detected after navigation/reload and its
        // Stop Cast control remains truthful.
        void this._prepareLocalCastContext().then(async (context) => {
          this._localCastContext = context;
          if (context.getCurrentSession?.()) this._localCastActive = true;
          this._updateMediaControls();
        }).catch(() => {});
      }
    } catch (err) {
      console.error("[Fitness TV] dashboard load failed", err);
      this._loadError = this._labels().flow_error_unknown;
      this._loaded = true;
      this._render();
    } finally {
      this._loading = false;
    }
  }

  async _loadPreferences() {
    if (!this._profile) return;
    try {
      const prefs = await this._hass.callWS({
        type:"fitness/tv/preferences",
        profile_entry_id:this._profile.entry_id,
      });
      this._selectedCards = Array.isArray(prefs?.cards) ? prefs.cards : [...FITNESS_TV_DEFAULT_CARDS];
      this._mediaFavorites = Array.isArray(prefs?.favorites) ? prefs.favorites : [];
      this._userPlaylists = Array.isArray(prefs?.user_playlists) ? prefs.user_playlists : [];
      this._lastMediaSnapshot = prefs?.last_media || this._profile?.tv_dashboard?.last_media || {};
      this._restorePlaylistContext(this._lastMediaSnapshot?.playlist_context || {});
      if (!this._currentMediaContentId && this._lastMediaSnapshot?.media_content_id) {
        this._currentMediaContentId = String(this._lastMediaSnapshot.media_content_id);
        this._musicTitle = String(this._lastMediaSnapshot.title || this._currentMediaContentId);
        this._musicMetadata = this._normalizedMediaMetadata(this._lastMediaSnapshot);
        this._sharedMediaState = {
          title:this._musicTitle,
          ...this._musicMetadata,
          media_content_id:this._currentMediaContentId,
          playing:false,
          error:false,
          position:this._mediaSeconds(this._lastMediaSnapshot.position),
          playlist_context:this._playlistContextSnapshot(),
        };
      }
      this._tvScalePercent = Math.max(10, Math.min(150, Number(prefs?.tv_scale_percent ?? this._profile?.tv_dashboard?.tv_scale_percent ?? 70)));
      this._oledProtection = Boolean(prefs?.oled_protection ?? this._profile?.tv_dashboard?.oled_protection ?? false);
      this._animationsEnabled = Boolean(prefs?.animations_enabled ?? this._profile?.tv_dashboard?.animations_enabled ?? true);
      this._audioOutputId = String(prefs?.audio_output_id || this._profile?.tv_dashboard?.audio_output_id || "__fitness_browser__");
      this._applyTvDisplayPreferences();
    } catch (_err) {
      this._selectedCards = [...FITNESS_TV_DEFAULT_CARDS];
      this._mediaFavorites = [];
      this._userPlaylists = [];
      this._tvScalePercent = Number(this._profile?.tv_dashboard?.tv_scale_percent ?? 70);
      this._oledProtection = Boolean(this._profile?.tv_dashboard?.oled_protection ?? false);
      this._animationsEnabled = Boolean(this._profile?.tv_dashboard?.animations_enabled ?? true);
      this._audioOutputId = String(this._profile?.tv_dashboard?.audio_output_id || "__fitness_browser__");
      this._applyTvDisplayPreferences();
    }
  }

  async _savePreferences(cards) {
    if (!this._profile || !this._canControlProfile) return;
    const allowed = new Set(FITNESS_TV_CARD_CATALOG.map((item) => item.id));
    this._selectedCards = (cards || []).filter((id, index, all) => allowed.has(id) && all.indexOf(id) === index);
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/preferences/save",
        profile_entry_id:this._profile.entry_id,
        cards:this._selectedCards,
      });
      if (Array.isArray(result?.cards)) this._selectedCards = result.cards;
      if (Array.isArray(result?.favorites)) this._mediaFavorites = result.favorites;
      if (result?.tv_scale_percent != null) this._tvScalePercent = Number(result.tv_scale_percent);
      if (result?.oled_protection != null) this._oledProtection = Boolean(result.oled_protection);
      if (result?.animations_enabled != null) this._animationsEnabled = Boolean(result.animations_enabled);
      this._applyTvDisplayPreferences();
    } catch (_err) {}
    this._mountSelectedCards();
  }

  async _saveFavorites(favorites) {
    if (!this._profile || !this._hass || !this._canControlProfile) return;
    const seen = new Set();
    this._mediaFavorites = (favorites || []).filter((item) => {
      const id = String(item?.media_content_id || "");
      if (!id || seen.has(id)) return false;
      seen.add(id);
      return true;
    }).slice(0, 100).map((item) => this._playlistItemSnapshot(item));
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/preferences/save",
        profile_entry_id:this._profile.entry_id,
        favorites:this._mediaFavorites,
      });
      if (Array.isArray(result?.favorites)) this._mediaFavorites = result.favorites;
    } catch (_err) {}
  }

  _playlistItemSnapshot(item = {}) {
    const metadata = this._normalizedMediaMetadata(item);
    return {
      media_content_id:String(item.media_content_id || ""),
      title:String(item.title || item.media_content_id || this._labels().media_browser),
      artist:String(metadata.artist || item.artist || ""),
      album:String(metadata.album || item.album || ""),
      thumbnail:String(metadata.thumbnail || item.thumbnail || ""),
      details:String(metadata.details || item.details || ""),
      provider:String(metadata.provider || item.provider || ""),
      provider_name:String(metadata.provider_name || item.provider_name || ""),
      provider_origin:String(metadata.provider_origin || item.provider_origin || ""),
      provider_instance:String(item.provider_instance || ""),
      year:String(metadata.year || item.year || ""),
      duration:this._mediaSeconds(metadata.duration || item.duration),
      media_class:String(item.media_class || item.children_media_class || "track"),
      adapter_id:String(item.adapter_id || ""),
      adapter_name:String(item.adapter_name || ""),
      external_url:String(item.external_url || ""),
      can_play:item.can_play !== false,
      can_expand:Boolean(item.can_expand),
      is_live:Boolean(item.is_live || metadata.is_live),
    };
  }

  _playlistContextSnapshot(context = this._activePlaylistContext) {
    if (!context?.kind) return {};
    const kind = String(context.kind || "");
    let index = Math.max(0, Number(context.index ?? this._fitnessPlaylistIndex ?? 0) || 0);
    if (["provider","selection","user"].includes(kind) && Number.isFinite(Number(this._maQueueProgress?.current_index))) {
      index = Math.max(0, Number(this._maQueueProgress.current_index));
    } else if (kind === "youtube_playlist" && this._embeddedProvider === "youtube" && this._embeddedController) {
      try { index = Math.max(0, Number(this._embeddedController.getPlaylistIndex?.() ?? index) || 0); } catch (_err) {}
    }
    const snapshot = {
      kind,
      title:String(context.title || ""),
      index,
      shuffle:kind === "youtube_playlist"
        ? Boolean(this._youtubePlaylistShuffle)
        : (kind === "user" && !(context.items || []).every((item) => this._isMAItem(item))
          ? Boolean(this._fitnessPlaylistShuffle)
          : Boolean(this._maQueueProgress?.shuffle_enabled)),
      repeat:kind === "youtube_playlist"
        ? String(this._youtubePlaylistRepeat || "off")
        : (kind === "user" && !(context.items || []).every((item) => this._isMAItem(item))
          ? String(this._fitnessPlaylistRepeat || "off")
          : String(this._maQueueProgress?.repeat_mode || "off")),
    };
    if (context.id) snapshot.id = String(context.id);
    if (context.item) snapshot.item = this._playlistItemSnapshot(context.item);
    if (kind === "selection") snapshot.items = (context.items || []).slice(0,100).map((item) => this._playlistItemSnapshot(item));
    return snapshot;
  }

  _restorePlaylistContext(raw = {}) {
    const kind = String(raw?.kind || "");
    if (!kind) { this._activePlaylistContext = null; return null; }
    let context = null;
    if (kind === "user") {
      const playlist = this._userPlaylist(raw.id);
      if (playlist) context = {kind:"user",id:playlist.id,title:playlist.name,items:playlist.items || [],thumbnail:playlist.thumbnail || ""};
    } else if (["provider","youtube_playlist"].includes(kind) && raw.item?.media_content_id) {
      context = {kind,title:String(raw.title || raw.item.title || this._labels().music_playlist),item:this._playlistItemSnapshot(raw.item)};
    } else if (kind === "selection" && Array.isArray(raw.items) && raw.items.length) {
      context = {kind:"selection",title:String(raw.title || this._labels().music_selected_items),items:raw.items.map((item) => this._playlistItemSnapshot(item)).filter((item) => item.media_content_id)};
    }
    if (!context) { this._activePlaylistContext = null; return null; }
    const index = Math.max(0, Number(raw.index || 0) || 0);
    context.index = index;
    this._activePlaylistContext = context;
    this._fitnessPlaylistIndex = index;
    this._fitnessPlaylistShuffle = Boolean(raw.shuffle);
    this._fitnessPlaylistRepeat = ["one","all"].includes(String(raw.repeat || "")) ? String(raw.repeat) : "off";
    this._youtubePlaylistShuffle = Boolean(raw.shuffle);
    this._youtubePlaylistRepeat = String(raw.repeat || "") === "all" ? "all" : "off";
    return context;
  }

  _newUserPlaylistId() {
    try { return `fitness-${crypto.randomUUID()}`; } catch (_err) { return `fitness-${Date.now()}-${Math.random().toString(36).slice(2,9)}`; }
  }

  async _saveUserPlaylists(playlists = this._userPlaylists || []) {
    if (!this._profile || !this._hass || !this._canControlProfile) return;
    this._userPlaylists = (playlists || []).slice(0, 50).map((playlist) => ({
      id:String(playlist.id || this._newUserPlaylistId()),
      name:String(playlist.name || this._labels().music_playlist).trim(),
      thumbnail:String(playlist.thumbnail || playlist.items?.find?.((item) => item?.thumbnail)?.thumbnail || ""),
      items:(playlist.items || []).slice(0, 500).map((item) => this._playlistItemSnapshot(item)).filter((item) => item.media_content_id),
    }));
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/preferences/save",
        profile_entry_id:this._profile.entry_id,
        user_playlists:this._userPlaylists,
      });
      if (Array.isArray(result?.user_playlists)) this._userPlaylists = result.user_playlists;
    } catch (err) { console.error("[Fitness TV] save playlists failed", err); }
  }

  _userPlaylist(id) {
    return (this._userPlaylists || []).find((playlist) => String(playlist.id || "") === String(id || "")) || null;
  }

  _applyTvDisplayPreferences() {
    const scale = Math.max(10, Math.min(150, Number(this._tvScalePercent || 70))) / 100;
    this.style.setProperty("--fitness-tv-card-scale", String(scale));
    this.toggleAttribute("oled-protection", Boolean(this._oledProtection));
    this.toggleAttribute("fitness-animations", Boolean(this._animationsEnabled));
    if (!this._motionEnabled()) this._cancelDashboardMotion();
    if (FITNESS_TV_CAST_RECEIVER && this._oledProtection) this._startOledProtection();
    else this._stopOledProtection();
    this.shadowRoot?.querySelectorAll(".tv-card-slot").forEach((wrapper, index) => {
      wrapper.style.setProperty("--fitness-card-delay", `${-(index % 7) * 0.73}s`);
      const card = wrapper.querySelector(".tv-mounted-card");
      if (card) {
        card.toggleAttribute("fitness-animations", Boolean(this._animationsEnabled));
        card.toggleAttribute("fitness-live-workout", this.hasAttribute("fitness-live-ambient"));
        this._syncCardGridSpan(card, wrapper);
      }
    });
  }

  _startOledProtection() {
    if (!FITNESS_TV_CAST_RECEIVER || !this._oledProtection) return;
    this._stopOledProtection();
    this._oledShiftIndex = Number(this._oledShiftIndex || 0);
    const shifts = [[0,0],[2,1],[-2,2],[1,-2],[-1,-1],[2,-2],[-2,0]];
    const shift = () => {
      const [x,y] = shifts[this._oledShiftIndex % shifts.length];
      this.style.setProperty("--fitness-oled-x", `${x}px`);
      this.style.setProperty("--fitness-oled-y", `${y}px`);
      this._oledShiftIndex += 1;
    };
    shift();
    this._oledShiftTimer = setInterval(shift, 75000);
    this._oledLastInteraction = Date.now();
    this._oledDimTimer = setInterval(() => {
      const idle = Date.now() - Number(this._oledLastInteraction || Date.now());
      this.toggleAttribute("oled-idle", idle > 120000);
    }, 15000);
  }

  _stopOledProtection() {
    if (this._oledShiftTimer) clearInterval(this._oledShiftTimer);
    if (this._oledDimTimer) clearInterval(this._oledDimTimer);
    this._oledShiftTimer = null;
    this._oledDimTimer = null;
    this.removeAttribute("oled-idle");
    this.style.removeProperty("--fitness-oled-x");
    this.style.removeProperty("--fitness-oled-y");
  }

  _markOledInteraction() {
    if (!this._oledProtection) return;
    this._oledLastInteraction = Date.now();
    this.removeAttribute("oled-idle");
  }

  async _subscribeTvAudio() {
    if (this._unsubscribeTvAudio || !this._hass?.connection) return;
    this._unsubscribeTvAudio = this._hass.connection.subscribeEvents((event) => {
      const data = event?.data || {};
      if (data.client_id !== FITNESS_TV_CLIENT_ID) return;
      if (data.profile_entry_id !== this._profile?.entry_id) return;
      if (!this._isWindowController()) return;
      this._audioOwner = true;
      this._ttsQueue = this._ttsQueue.then(() => this._playTvTts(data)).catch(() => {});
    }, FITNESS_TV_AUDIO_EVENT);
  }

  async _subscribeTvMedia() {
    if (!this._hass?.connection) return;
    if (!this._unsubscribeTvMedia) {
      this._unsubscribeTvMedia = this._hass.connection.subscribeEvents((event) => {
        const payload = event?.data || {};
        if (payload.client_id !== FITNESS_TV_CLIENT_ID) return;
        if (payload.profile_entry_id !== this._profile?.entry_id) return;
        if (!this._isWindowController()) return;
        this._audioOwner = true;
        this._handleMediaCommand(payload.command, payload.data || {});
      }, FITNESS_TV_MEDIA_EVENT);
    }
    if (!this._unsubscribeTvMediaState) {
      this._unsubscribeTvMediaState = this._hass.connection.subscribeEvents((event) => {
        const payload = event?.data || {};
        if (payload.profile_entry_id !== this._profile?.entry_id) return;
        this._applySharedMediaState(payload);
      }, FITNESS_TV_MEDIA_STATE_EVENT);
    }
  }

  async _subscribeTvSettings() {
    if (this._unsubscribeTvSettings || !this._hass?.connection) return;
    this._unsubscribeTvSettings = this._hass.connection.subscribeEvents((event) => {
      const payload = event?.data || {};
      if (payload.profile_entry_id !== this._profile?.entry_id) return;
      this._profile = {
        ...this._profile,
        tv_dashboard:{...(this._profile?.tv_dashboard || {}), ...payload},
      };
      if (payload.tv_scale_percent != null) this._tvScalePercent = Number(payload.tv_scale_percent);
      if (payload.oled_protection != null) this._oledProtection = Boolean(payload.oled_protection);
      if (payload.animations_enabled != null) this._animationsEnabled = Boolean(payload.animations_enabled);
      this._applyTvDisplayPreferences();
      this._updateMediaControls();
    }, FITNESS_TV_SETTINGS_EVENT);
  }

  _refreshCastUiState() {
    const target = String(this._activeCastTarget || "");
    const state = target ? this._hass?.states?.[target] : null;
    const targetAvailable = Boolean(
      state && !["off", "standby", "unknown", "unavailable"].includes(String(state.state || ""))
    );
    const active = Boolean(
      target && this._serverCastActive && targetAvailable
      && String(state?.attributes?.app_id || "") === FITNESS_TV_CAST_APP_ID
    );
    this._castActive = active;
    return active;
  }

  async _ensureCastMusicPlayback(state = {}) {
    if (!FITNESS_TV_CAST_RECEIVER || !this._audioOwner || this._ownerResumeInFlight) return;
    const mediaContentId = String(state.media_content_id || "");
    if (!state.playing || state.error || !mediaContentId) return;
    // A stale playing heartbeat must never turn one real receiver playback
    // error into an endless resolve -> play -> error -> ready loop. Only an
    // explicit Play/select command (or a different media ID) clears this latch.
    if (this._castFailedMediaContentId === mediaContentId) return;
    if (String(this._musicAudio?.getAttribute?.("src") || "").trim() && this._currentMediaContentId === mediaContentId && !this._musicAudio.paused) return;
    this._ownerResumeInFlight = true;
    try {
      await this._playResolvedMedia(mediaContentId, String(state.title || this._musicTitle || ""), state);
    } catch (_err) {
      this._updateMediaControls(true);
    } finally {
      this._ownerResumeInFlight = false;
    }
  }

  _startHeartbeat() {
    if (!this._canControlProfile) return;
    if (this._heartbeatTimer) clearInterval(this._heartbeatTimer);
    this._heartbeat();
    this._heartbeatTimer = setInterval(() => this._heartbeat(), FITNESS_TV_CAST_RECEIVER ? 5000 : 10000);
  }

  _isFitnessAccessDenied(err) {
    const code = String(err?.code || "").toLowerCase();
    const message = String(err?.message || err || "").toLowerCase();
    return code === "unauthorized" || code === "auth_required" || message.includes("unauthorized") || message.includes("not authorized");
  }

  _handleFitnessAccessDenied() {
    if (this._fitnessAccessRevoked) return;
    this._fitnessAccessRevoked = true;
    if (this._heartbeatTimer) clearInterval(this._heartbeatTimer);
    this._heartbeatTimer = null;
    this._hardStopMusic();
    this._hardStopAudio(this._ttsAudio);
    try {
      history.replaceState(null, "", "/fitness-tv/main");
      window.location.reload();
    } catch (_err) {
      window.location.href = "/fitness-tv/main";
    }
  }

  async _rearmExistingCastAfterReconnect(result = {}, previousTarget = "") {
    if (FITNESS_TV_CAST_RECEIVER || !this._profile || !this._hass) return false;
    // Browser-local Google Cast sessions survive an HA backend restart. Re-arm
    // backend ownership so the first Play after reconnect routes to the TV.
    if (this._localCastSessionActive() && !Boolean(result?.local_cast_active)
        && performance.now() >= Number(this._localCastRearmUntil || 0)
        && !this._localCastRearmInFlight) {
      this._localCastRearmInFlight = true;
      try {
        const armed = await this._armLocalCastHandoff("ha_backend_reconnected");
        if (armed) {
          this._localCastActive = true;
          this._localCastServerActive = true;
          this._localCastRearmUntil = performance.now() + 8000;
          setTimeout(() => void this._heartbeat(), 900);
          return true;
        }
      } finally {
        this._localCastRearmInFlight = false;
      }
    }
    // Server-side HA Cast can also keep the Lovelace receiver alive while the
    // Fitness hub is recreated. Reattach only when HA still reports our Cast app.
    const configured = String(this._profile?.tv_dashboard?.cast_media_player_id || "");
    const target = String(previousTarget || configured || "").trim();
    const targetState = target ? this._hass?.states?.[target] : null;
    const appId = String(targetState?.attributes?.app_id || "");
    if (!result?.cast_target && target && appId === FITNESS_TV_CAST_APP_ID
        && performance.now() >= Number(this._serverCastRearmUntil || 0)
        && !this._serverCastRearmInFlight) {
      this._serverCastRearmInFlight = true;
      try {
        const rearmed = await this._hass.callWS({
          type:"fitness/tv/cast/rearm",
          profile_entry_id:this._profile.entry_id,
          entity_id:target,
        });
        if (rearmed?.armed) {
          this._activeCastTarget = target;
          this._serverCastActive = true;
          this._serverCastRearmUntil = performance.now() + 8000;
          setTimeout(() => void this._heartbeat(), 900);
          return true;
        }
      } catch (_err) {
      } finally {
        this._serverCastRearmInFlight = false;
      }
    }
    return false;
  }

  async _heartbeat() {
    if (!this._canControlProfile) return;
    if (!this._profile || !this._hass || !this._isWindowController()) return;
    try {
      const previousCastTarget = String(this._activeCastTarget || "");
      const result = await this._hass.callWS({
        type:"fitness/tv/heartbeat",
        profile_entry_id:this._profile.entry_id,
        client_id:FITNESS_TV_CLIENT_ID,
        is_cast_receiver:FITNESS_TV_CAST_RECEIVER,
      });
      this._audioOwner = Boolean(result?.audio_owner);
      this._activeCastTarget = String(result?.cast_target || "");
      this._serverCastActive = Boolean(result?.cast_active);
      this._localCastServerActive = Boolean(result?.local_cast_active);
      if (result?.local_cast_active) this._localCastRearmUntil = 0;
      if (result?.cast_target) this._serverCastRearmUntil = 0;
      await this._rearmExistingCastAfterReconnect(result, previousCastTarget);
      if (this._localCastServerActive) this._localCastActive = true;
      else if (!this._localCastSessionActive()) this._localCastActive = false;
      this._refreshCastUiState();
      if (!this._audioOwner) {
        this._hardStopMusic();
        this._hardStopAudio(this._ttsAudio);
      }
      if (result?.media_state) {
        this._applySharedMediaState(result.media_state);
        if (this._audioOwner && FITNESS_TV_CAST_RECEIVER) {
          this._ensureCastMusicPlayback(result.media_state);
        }
      }
      this._updateMediaControls();
      this._reconcileScreenWakeLock();
      this._applyAmbientBackground();
    } catch (err) {
      if (this._isFitnessAccessDenied(err)) this._handleFitnessAccessDenied();
    }
  }

  async _sendMediaCommand(command, data = {}) {
    if (!this._canControlProfile) return;
    if (!this._profile || !this._hass) return {sent:false};
    try {
      return await this._hass.callWS({
        type:"fitness/tv/media_command",
        profile_entry_id:this._profile.entry_id,
        source_client_id:FITNESS_TV_CLIENT_ID,
        command,
        data,
      });
    } catch (_err) {
      return {sent:false};
    }
  }

  _mediaSeconds(value) {
    const number = Number(value ?? 0);
    return Number.isFinite(number) && number >= 0 ? number : 0;
  }

  _normalizedMediaMetadata(value = {}) {
    const rawYear = value?.year ?? value?.release_year ?? value?.release_date ?? "";
    const yearText = String(rawYear || "").trim();
    const year = /^\d{4}/.test(yearText) ? yearText.slice(0,4) : yearText;
    return {
      artist:String(value?.artist || value?.media_artist || value?.author || value?.uploader || ""),
      album:String(value?.album || value?.media_album_name || ""),
      year,
      thumbnail:String(value?.thumbnail || value?.image || value?.artwork_url || ""),
      details:String(value?.details || value?.subtitle || ""),
      provider:String(value?.provider || ""),
      provider_name:String(value?.provider_name || ""),
      provider_origin:String(value?.provider_origin || value?.source_label || value?.adapter_name || value?.provider_name || value?.provider || ""),
      position:this._mediaSeconds(value?.position),
      duration:this._mediaSeconds(value?.duration ?? value?.media_duration),
      is_live:Boolean(value?.is_live),
    };
  }

  _mediaProviderLabel(value = {}) {
    const metadata = this._normalizedMediaMetadata(value);
    const origin = String(metadata.provider_origin || "").trim();
    if (origin) return origin;
    const adapter = String(value?.adapter_name || "").trim();
    const provider = String(metadata.provider_name || metadata.provider || "").trim();
    if (adapter && provider && adapter.toLocaleLowerCase() !== provider.toLocaleLowerCase()) return `${adapter} · ${provider}`;
    return adapter || provider;
  }

  _compactMediaDetails(providerLabel, details) {
    let value = String(details || "").trim();
    if (!value) return "";
    const normalize = (text) => String(text || "").toLocaleLowerCase().replace(/[^a-z0-9]+/g, "");
    const detailKey = normalize(value);
    const providerKey = normalize(providerLabel);
    if (detailKey && providerKey.includes(detailKey)) return "";
    const providerParts = String(providerLabel || "").split(/[·|›]/).map((part) => part.trim()).filter(Boolean);
    for (const part of providerParts.sort((a,b) => b.length - a.length)) {
      const escaped = part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const match = value.match(new RegExp(`^${escaped}(?:\\s*[-–—:·|]\\s*|\\s+)`, "i"));
      if (!match) continue;
      value = value.slice(match[0].length).trim();
      break;
    }
    return value;
  }

  _formatMediaTime(value) {
    const total = Math.max(0, Math.floor(this._mediaSeconds(value)));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const seconds = total % 60;
    return hours > 0
      ? `${hours}:${String(minutes).padStart(2,"0")}:${String(seconds).padStart(2,"0")}`
      : `${minutes}:${String(seconds).padStart(2,"0")}`;
  }

  _captureLocalMediaProgress(force = false) {
    const audio = this._musicAudio;
    if (!audio || !this._currentMediaContentId) return;
    let position = this._mediaSeconds(audio.currentTime);
    let duration = Number.isFinite(Number(audio.duration)) && Number(audio.duration) > 0
      ? Number(audio.duration)
      : this._mediaSeconds(this._musicMetadata?.duration);
    if (duration > 0) position = Math.min(position, duration);
    const pendingResume = this._mediaSeconds(this._pendingHtmlAudioResumePosition);
    if (pendingResume > 0 && position + 1 < pendingResume) {
      // loadedmetadata/durationchange/timeupdate commonly report 0 before the
      // requested seek has completed. Keep the persisted target authoritative
      // until _resumeHtmlAudio finishes instead of broadcasting a false reset.
      this._musicMetadata = {
        ...this._normalizedMediaMetadata(this._musicMetadata),
        position:duration > 0 ? Math.min(pendingResume, duration) : pendingResume,
        duration,
      };
      this._updateMediaControls();
      return;
    }
    this._musicMetadata = {...this._normalizedMediaMetadata(this._musicMetadata), position, duration};
    this._updateMediaControls();
    const now = Date.now();
    if (this._audioOwner && (force || now - Number(this._lastProgressSyncAt || 0) >= 1500)) {
      this._lastProgressSyncAt = now;
      this._syncMediaState({position,duration});
    }
  }

  async _resumeHtmlAudio(position) {
    const requested = this._mediaSeconds(position);
    const audio = this._musicAudio;
    if (!audio || requested <= 0) return {position:0,duration:this._mediaSeconds(this._musicMetadata?.duration)};
    if (audio.readyState < 1) {
      await new Promise((resolve) => {
        let settled = false;
        const done = () => { if (settled) return; settled = true; cleanup(); resolve(); };
        const cleanup = () => { audio.removeEventListener("loadedmetadata", done); audio.removeEventListener("canplay", done); clearTimeout(timer); };
        const timer = setTimeout(done, 1800);
        audio.addEventListener("loadedmetadata", done, {once:true});
        audio.addEventListener("canplay", done, {once:true});
      });
    }
    try {
      return await this._seekHtmlAudio(requested);
    } catch (_err) {
      return {
        position:this._mediaSeconds(audio.currentTime),
        duration:(Number.isFinite(Number(audio.duration)) && Number(audio.duration) > 0)
          ? Number(audio.duration)
          : this._mediaSeconds(this._musicMetadata?.duration),
      };
    }
  }

  async _seekHtmlAudio(requestedPosition) {
    const audio = this._musicAudio;
    if (!audio || !String(audio.getAttribute?.("src") || "").trim()) throw new Error("No seekable audio is loaded");
    const requested = this._mediaSeconds(requestedPosition);
    const duration = Number.isFinite(Number(audio.duration)) && Number(audio.duration) > 0
      ? Number(audio.duration)
      : this._mediaSeconds(this._musicMetadata?.duration);
    let target = duration > 0 ? Math.min(requested, duration) : requested;
    if (audio.seekable?.length) {
      let chosen = target;
      let found = false;
      for (let index = 0; index < audio.seekable.length; index += 1) {
        const start = Number(audio.seekable.start(index));
        const end = Number(audio.seekable.end(index));
        if (target >= start && target <= end) { found = true; chosen = target; break; }
        if (target < start) { found = true; chosen = start; break; }
        chosen = end;
      }
      if (found || Number.isFinite(chosen)) target = chosen;
    }
    const before = this._mediaSeconds(audio.currentTime);
    const completed = new Promise((resolve) => {
      let settled = false;
      const done = () => { if (settled) return; settled = true; cleanup(); resolve(true); };
      const cleanup = () => { audio.removeEventListener("seeked", done); audio.removeEventListener("timeupdate", done); clearTimeout(timer); };
      const timer = setTimeout(() => { if (settled) return; settled = true; cleanup(); resolve(false); }, 2500);
      audio.addEventListener("seeked", done, {once:true});
      audio.addEventListener("timeupdate", done, {once:true});
    });
    try {
      if (typeof audio.fastSeek === "function") audio.fastSeek(target);
      else audio.currentTime = target;
    } catch (_err) {
      audio.currentTime = target;
    }
    await completed;
    const actual = this._mediaSeconds(audio.currentTime);
    const tolerance = Math.max(1.5, Math.min(5, duration * 0.01));
    if (Math.abs(actual - target) > tolerance && Math.abs(actual - before) < 0.5) {
      throw new Error("This stream did not accept the seek request");
    }
    this._musicMetadata = {...this._normalizedMediaMetadata(this._musicMetadata), position:actual, duration};
    this._captureLocalMediaProgress(true);
    return {position:actual,duration};
  }

  async _seekEmbeddedMedia(provider, requestedPosition) {
    const requested = this._mediaSeconds(requestedPosition);
    const controller = this._embeddedController;
    if (!controller) throw new Error("No embedded player is loaded");
    if (provider === "youtube") {
      controller.seekTo?.(requested, true);
      await new Promise((resolve) => setTimeout(resolve, 180));
      const actual = this._mediaSeconds(controller.getCurrentTime?.() ?? requested);
      const duration = this._mediaSeconds(controller.getDuration?.() ?? this._embeddedDuration);
      this._updateEmbeddedProgress(actual, duration, true);
      return {position:actual,duration};
    }
    if (provider === "soundcloud") {
      controller.seekTo?.(requested * 1000);
      const actualMs = await new Promise((resolve) => {
        let settled = false;
        const done = (value) => { if (settled) return; settled = true; clearTimeout(timer); resolve(Number(value || requested * 1000)); };
        const timer = setTimeout(() => done(requested * 1000), 800);
        try { controller.getPosition?.(done); } catch (_err) { done(requested * 1000); }
      });
      const durationMs = await new Promise((resolve) => {
        let settled = false;
        const done = (value) => { if (settled) return; settled = true; clearTimeout(timer); resolve(Number(value || this._embeddedDuration * 1000)); };
        const timer = setTimeout(() => done(this._embeddedDuration * 1000), 500);
        try { controller.getDuration?.(done); } catch (_err) { done(this._embeddedDuration * 1000); }
      });
      const actual = this._mediaSeconds(Number(actualMs) / 1000);
      const duration = this._mediaSeconds(Number(durationMs) / 1000);
      this._updateEmbeddedProgress(actual, duration, true);
      return {position:actual,duration};
    }
    throw new Error("This embedded provider does not support seeking");
  }

  _updateEmbeddedProgress(position, duration = 0, force = false) {
    this._embeddedPosition = this._mediaSeconds(position);
    this._embeddedDuration = this._mediaSeconds(duration || this._embeddedDuration);
    const bounded = this._embeddedDuration > 0
      ? Math.min(this._embeddedPosition, this._embeddedDuration)
      : this._embeddedPosition;
    this._musicMetadata = {
      ...this._normalizedMediaMetadata(this._musicMetadata),
      position:bounded,
      duration:this._embeddedDuration,
    };
    this._updateMediaControls();
    const now = Date.now();
    if (this._audioOwner && (force || now - Number(this._lastProgressSyncAt || 0) >= 1500)) {
      this._lastProgressSyncAt = now;
      this._syncMediaState({position:bounded,duration:this._embeddedDuration});
    }
  }

  async _syncMediaState(partial = {}) {
    if (!this._profile || !this._hass) return;
    const metadata = this._normalizedMediaMetadata({
      ...(this._sharedMediaState || {}),
      ...(this._musicMetadata || {}),
      ...partial,
    });
    const state = {
      title: partial.title ?? this._musicTitle ?? this._sharedMediaState?.title ?? "",
      artist: metadata.artist,
      album: metadata.album,
      year: metadata.year,
      thumbnail: metadata.thumbnail,
      details: metadata.details,
      provider: metadata.provider,
      provider_name: metadata.provider_name,
      provider_origin: metadata.provider_origin,
      playlist_context:this._playlistContextSnapshot(),
      position: metadata.position,
      duration: metadata.duration,
      media_content_id: partial.media_content_id ?? this._currentMediaContentId ?? this._sharedMediaState?.media_content_id ?? "",
      playing: partial.playing ?? Boolean((this._musicAudio && !this._musicAudio.paused) || this._embeddedPlaying),
      error: partial.error ?? false,
    };
    if (!String(state.media_content_id || "").trim()) {
      Object.assign(state, {
        title:"",artist:"",album:"",year:"",thumbnail:"",details:"",provider:"",provider_name:"",provider_origin:"",media_content_id:"",playlist_context:{},
        playing:false,error:false,position:0,duration:0,
      });
    }
    this._musicMetadata = this._normalizedMediaMetadata(state);
    this._sharedMediaState = state;
    this._reconcileScreenWakeLock();
    try {
      await this._hass.callWS({
        type:"fitness/tv/media_state",
        profile_entry_id:this._profile.entry_id,
        source_client_id:FITNESS_TV_CLIENT_ID,
        state,
      });
    } catch (_err) {}
  }

  _applySharedMediaState(state = {}) {
    const incomingMediaContentId = String(state.media_content_id || "");
    if (incomingMediaContentId && incomingMediaContentId !== String(this._currentMediaContentId || "")) {
      this._castFailedMediaContentId = "";
    }
    const metadata = this._normalizedMediaMetadata(state);
    if (state.playlist_context !== undefined) this._restorePlaylistContext(state.playlist_context || {});
    this._sharedMediaState = {
      title: String(state.title || ""),
      ...metadata,
      playlist_context:this._playlistContextSnapshot(),
      media_content_id: String(state.media_content_id || ""),
      playing: Boolean(state.playing),
      error: Boolean(state.error),
    };
    this._mediaVolumeLevel = 1;
    if (this._musicAudio && !this._ttsDuckingActive) this._musicAudio.volume = 1;
    if (this._ttsAudio) this._ttsAudio.volume = 1;
    this._musicTitle = this._sharedMediaState.title;
    this._musicMetadata = metadata;
    this._currentMediaContentId = this._sharedMediaState.media_content_id;
    this._updateMediaControls(Boolean(this._sharedMediaState.error));
  }

  _resolvedMediaUrl(url) {
    const raw = String(url || "").trim();
    if (!raw) return "";
    if (/^https?:\/\//i.test(raw)) return raw;
    try {
      if (typeof this._hass?.hassUrl === "function") return this._hass.hassUrl(raw);
    } catch (_err) {}
    try {
      const base = this._hass?.auth?.data?.hassUrl || globalThis.location?.origin || "";
      return new URL(raw, base).href;
    } catch (_err) {
      return raw;
    }
  }

  _musicElementStateSuppressed() {
    return performance.now() < Number(this._suppressMusicElementStateUntil || 0);
  }

  _hardStopAudio(audio) {
    if (!audio) return;
    // Intentional teardown (cast handoff, owner replacement, source replacement)
    // must not publish a transient paused/Selected state. The explicit command
    // path owns shared-state changes; native pause/ended events are ignored for
    // a short teardown window only for the music element.
    if (audio === this._musicAudio) {
      this._suppressMusicElementStateUntil = performance.now() + 750;
      this._pendingHtmlAudioResumePosition = 0;
    }
    try { audio.pause(); } catch (_err) {}
    try { audio.currentTime = 0; } catch (_err) {}
    try { audio.removeAttribute("src"); } catch (_err) {}
    // Setting audio.src = "" makes the DOM property resolve to the current
    // dashboard URL, which later looks like a playable source.
    try { audio.load(); } catch (_err) {}
  }

  _suspendMusicForNavigation() {
    if (!this._isWindowController()) {
      this._hardStopMusic();
      return;
    }
    const mediaContentId = String(this._currentMediaContentId || this._sharedMediaState?.media_content_id || "").trim();
    if (!mediaContentId) {
      this._hardStopMusic();
      return;
    }
    let position = this._mediaSeconds(this._musicMetadata?.position ?? this._sharedMediaState?.position);
    let duration = this._mediaSeconds(this._musicMetadata?.duration ?? this._sharedMediaState?.duration);
    const audio = this._musicAudio;
    if (audio && String(audio.getAttribute?.("src") || "").trim()) {
      position = this._mediaSeconds(audio.currentTime || position);
      if (Number.isFinite(Number(audio.duration)) && Number(audio.duration) > 0) duration = Number(audio.duration);
      try { audio.pause(); } catch (_err) {}
    } else if (this._embeddedProvider === "youtube" && this._embeddedController) {
      try { position = this._mediaSeconds(this._embeddedController.getCurrentTime?.() ?? position); } catch (_err) {}
      try { duration = this._mediaSeconds(this._embeddedController.getDuration?.() ?? duration); } catch (_err) {}
      try { this._embeddedController.pauseVideo?.(); } catch (_err) {}
    } else if (this._embeddedProvider === "soundcloud" && this._embeddedController) {
      try { this._embeddedController.pause?.(); } catch (_err) {}
    }
    this._embeddedPlaying = false;
    this._musicMetadata = {...this._normalizedMediaMetadata(this._musicMetadata), position, duration};
    // _syncMediaState builds its payload synchronously before awaiting the WS call,
    // so it is safe to start it while disconnectedCallback continues cleanup.
    void this._syncMediaState({media_content_id:mediaContentId, playing:false, error:false, position, duration});
    this._hardStopMusic();
  }

  _hardStopMusic() {
    this._hardStopAudio(this._musicAudio);
    this._stopEmbeddedMusic();
  }

  _embedHost() {
    return this.shadowRoot?.getElementById("fitness-embed-host") || null;
  }

  _stopEmbeddedMusic() {
    const provider = this._embeddedProvider;
    const controller = this._embeddedController;
    if (this._embeddedProgressTimer) clearInterval(this._embeddedProgressTimer);
    this._embeddedProgressTimer = null;
    try {
      if (provider === "soundcloud") controller?.pause?.();
      else if (provider === "youtube") controller?.stopVideo?.();
      else if (provider === "music_assistant") {
        controller?.sendCommand?.("pause");
        controller?.disconnect?.("fitness_player_released");
      }
    } catch (_err) {}
    if (provider === "music_assistant") {
      this._stopMAProgressSync();
      this._maQueueProgress = null;
      this._maSendspinPlayer = null;
      this._maSendspinConnected = false;
      this._maSendspinPlayerId = "";
      this._maSendspinRelayPath = "";
      this._maSendspinRelayClientId = "";
      // Prepare a fresh one-shot relay ticket for the next explicit Play click.
      void this._primeMASendspinRelay().catch(() => {});
    }
    this._embeddedProvider = "";
    this._embeddedController = null;
    this._embeddedPlaying = false;
    const host = this._embedHost();
    if (host) host.replaceChildren();
  }

  async _loadExternalScript(key, src, readyCheck, callbackName = "") {
    window.__fitnessExternalScripts = window.__fitnessExternalScripts || new Map();
    if (readyCheck?.()) return readyCheck();
    if (window.__fitnessExternalScripts.has(key)) return window.__fitnessExternalScripts.get(key);
    const promise = new Promise((resolve, reject) => {
      let timeout = null;
      const finish = () => {
        if (timeout) clearTimeout(timeout);
        const ready = readyCheck?.();
        if (ready) resolve(ready);
        else reject(new Error(`${key} API did not become ready`));
      };
      if (callbackName) {
        const previous = window[callbackName];
        window[callbackName] = (...args) => {
          try { if (typeof previous === "function") previous(...args); } catch (_err) {}
          finish();
        };
      }
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.addEventListener("load", () => { if (!callbackName) finish(); });
      script.addEventListener("error", () => reject(new Error(`Unable to load ${key} player`)));
      document.head.appendChild(script);
      timeout = setTimeout(() => reject(new Error(`${key} player timed out`)), 12000);
    });
    window.__fitnessExternalScripts.set(key, promise);
    promise.catch(() => window.__fitnessExternalScripts?.delete?.(key));
    return promise;
  }

  async _soundCloudApi() {
    return this._loadExternalScript(
      "soundcloud",
      "https://w.soundcloud.com/player/api.js",
      () => window.SC?.Widget || null,
    );
  }

  async _youtubeApi() {
    return this._loadExternalScript(
      "youtube",
      "https://www.youtube.com/iframe_api",
      () => window.YT?.Player || null,
      "onYouTubeIframeAPIReady",
    );
  }

  _sendspinModule() {
    if (this._maSendspinModule) return Promise.resolve(this._maSendspinModule);
    if (!this._maSendspinModulePromise) {
      this._maSendspinModulePromise = import(FITNESS_SENDSPIN_MODULE_URL).then((module) => {
        this._maSendspinModule = module;
        return module;
      }).catch((err) => {
        this._maSendspinModulePromise = null;
        throw err;
      });
    }
    return this._maSendspinModulePromise;
  }

  async _primeMASendspinRelay() {
    if (!this._hass || !this._profile?.entry_id) return "";
    if (this._maSendspinRelayPath && this._maSendspinRelayClientId) return this._maSendspinRelayPath;
    // Search is metadata-only. Prepare playback prerequisites in parallel but
    // never let Sendspin connectivity decide whether MA search can run.
    void this._sendspinModule().catch(() => {});
    const result = await this._hass.callWS({
      type:"fitness/tv/music/ma/sendspin",
      profile_entry_id:this._profile.entry_id,
      client_id:String(FITNESS_TV_CLIENT_ID || ""),
    });
    this._maSendspinRelayPath = String(result?.url || "");
    this._maSendspinRelayClientId = String(result?.client_id || FITNESS_TV_CLIENT_ID || "");
    return this._maSendspinRelayPath;
  }

  _maRelayWebSocketUrl(path) {
    const raw = String(path || "").trim();
    if (!raw) return "";
    const hassBase = String(this._hass?.auth?.data?.hassUrl || globalThis.location?.origin || "").replace(/\/$/, "");
    try {
      const url = new URL(raw, `${hassBase}/`);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      return url.toString();
    } catch (_err) {
      return "";
    }
  }

  _maProgressSnapshot() {
    const state = this._maQueueProgress;
    if (!state) return null;
    const duration = this._mediaSeconds(state.duration);
    let position = this._mediaSeconds(state.position);
    if (state.playing && Number(state.synced_at || 0) > 0) {
      position += Math.max(0, performance.now() - Number(state.synced_at)) / 1000;
    }
    if (duration > 0) position = Math.min(position, duration);
    return {...state, position, duration};
  }

  _applyMAQueueProgress(result, broadcast = true) {
    if (!result || result.available === false) return false;
    const duration = this._mediaSeconds(result.duration);
    const position = duration > 0
      ? Math.min(this._mediaSeconds(result.position), duration)
      : this._mediaSeconds(result.position);
    this._maQueueProgress = {
      ...result,
      position,
      duration,
      synced_at:performance.now(),
    };
    const queueIndex = Number(result.current_index);
    if (this._activePlaylistContext && Number.isFinite(queueIndex) && queueIndex >= 0) {
      this._activePlaylistContext.index = queueIndex;
      const queueItems = this._activePlaylistContext.items || [];
      const currentItem = queueItems[queueIndex];
      if (currentItem?.media_content_id && ["user","selection"].includes(String(this._activePlaylistContext.kind || ""))) {
        this._currentMediaContentId = String(currentItem.media_content_id);
      }
    }
    this._embeddedDuration = duration;
    this._embeddedPosition = position;
    this._musicMetadata = {
      ...this._normalizedMediaMetadata(this._musicMetadata),
      position,
      duration,
    };
    this._updateMediaControls();
    if (broadcast && this._audioOwner && this._currentMediaContentId) {
      void this._syncMediaState({position,duration});
    }
    return true;
  }

  async _syncMAQueueProgress() {
    if (this._maProgressSyncInFlight || !this._hass || !this._profile?.entry_id || !this._maSendspinPlayerId) return;
    if (!String(this._currentMediaContentId || "").startsWith(FITNESS_MUSIC_PREFIXES.music_assistant)) return;
    this._maProgressSyncInFlight = true;
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/music/ma/state",
        profile_entry_id:this._profile.entry_id,
        player_id:this._maSendspinPlayerId,
      });
      this._applyMAQueueProgress(result, true);
    } catch (_err) {
      // Queue registration can lag the Sendspin connection briefly. The next
      // scheduled sync will retry without disturbing audio playback.
    } finally {
      this._maProgressSyncInFlight = false;
    }
  }

  _startMAProgressSync() {
    if (this._maProgressTimer) clearInterval(this._maProgressTimer);
    void this._syncMAQueueProgress();
    this._maProgressTimer = setInterval(() => {
      void this._syncMAQueueProgress();
    }, 1000);
  }

  _stopMAProgressSync() {
    if (this._maProgressTimer) clearInterval(this._maProgressTimer);
    this._maProgressTimer = null;
    this._maProgressSyncInFlight = false;
  }

  _handleMASendspinState(state) {
    // Only the local Sendspin player's stream state proves that this browser is
    // actually rendering audio. MA group playback can be "playing" while this
    // browser has received metadata/queue state but no stream at all.
    const playing = Boolean(state?.isPlaying);
    this._embeddedPlaying = playing;
    this._maSendspinLastState = state || null;
    if (Number.isFinite(Number(state?.volume))) this._embeddedVolume = Math.max(0, Math.min(1, Number(state.volume) / 100));
    const meta = state?.serverState?.metadata || {};
    const progress = meta?.progress && typeof meta.progress === "object" ? meta.progress : {};
    const current = this._normalizedMediaMetadata(this._musicMetadata);
    const title = String(meta?.title || this._musicTitle || "");
    const artist = String(meta?.artist || meta?.album_artist || current.artist || "");
    const album = String(meta?.album || meta?.album_name || current.album || "");
    const yearRaw = String(meta?.year || meta?.release_year || meta?.release_date || current.year || "");
    const year = /^\d{4}/.test(yearRaw) ? yearRaw.slice(0,4) : yearRaw;
    const thumbnail = String(meta?.artwork_url || meta?.image_url || meta?.image || current.thumbnail || "");
    const queueProgress = this._maProgressSnapshot();
    const duration = queueProgress
      ? queueProgress.duration
      : this._mediaSeconds(progress?.track_duration ?? meta?.duration ?? meta?.duration_seconds ?? this._embeddedDuration);
    const position = queueProgress
      ? queueProgress.position
      : this._mediaSeconds(progress?.track_progress ?? meta?.position ?? meta?.elapsed ?? this._embeddedPosition);
    if (title) this._musicTitle = title;
    this._embeddedDuration = duration || this._embeddedDuration;
    this._embeddedPosition = position || this._embeddedPosition;
    this._musicMetadata = {
      ...current,
      artist,
      album,
      year,
      thumbnail,
      details:current.details || this._labels().music_type_tracks,
      provider_origin:current.provider_origin || "Music Assistant",
      position:this._embeddedPosition,
      duration:this._embeddedDuration,
    };
    if (this._currentMediaContentId && !this._ttsDuckingActive) {
      void this._syncMediaState({
        title:this._musicTitle,
        media_content_id:this._currentMediaContentId,
        playing,
        error:false,
        ...this._musicMetadata,
      });
      this._updateMediaControls();
    }
  }

  _createMASendspinPlayer() {
    if (this._maSendspinPlayer) return this._maSendspinPlayer;
    const SendspinPlayer = this._maSendspinModule?.SendspinPlayer;
    if (!SendspinPlayer) throw new Error("Music Assistant browser player is still preparing; press Play again");
    const socketUrl = this._maRelayWebSocketUrl(this._maSendspinRelayPath);
    if (!socketUrl) throw new Error("Music Assistant browser relay is still preparing; press Play again");
    const playerId = String(this._maSendspinRelayClientId || FITNESS_TV_CLIENT_ID || "").trim();
    if (!playerId) throw new Error("Music Assistant browser player id is unavailable");
    const socket = new WebSocket(socketUrl);
    // Use a dedicated HTMLAudioElement output and PCM for the Fitness browser
    // player. This avoids depending on optional compressed-codec decoders and
    // gives Chrome/Android TV a normal media element as the final audio sink.
    this._maAudioElement = this._maAudioElement || new Audio();
    this._maAudioElement.preload = "auto";
    const player = new SendspinPlayer({
      playerId,
      clientName:`Fitness TV - ${String(this._profile?.profile_name || this._labels().tv_profile)}`,
      correctionMode:"quality-local",
      codecs:["pcm"],
      requiredLeadTimeMs:250,
      minBufferMs:2500,
      audioElement:this._maAudioElement,
      webSocket:socket,
      onStateChange:(state) => this._handleMASendspinState(state),
    });
    this._maSendspinPlayer = player;
    this._maSendspinPlayerId = playerId;
    return player;
  }

  async _connectMASendspinPlayer(player = this._maSendspinPlayer) {
    if (player && this._maSendspinConnected) return player;
    if (!player) throw new Error("Music Assistant browser player is unavailable");
    try {
      await player.connect();
      if (player.isConnected === false) throw new Error("Music Assistant browser player did not connect");
      this._maSendspinConnected = true;
      return player;
    } catch (err) {
      try { player.disconnect?.("fitness_connect_failed"); } catch (_err) {}
      this._maSendspinPlayer = null;
      this._maSendspinConnected = false;
      this._maSendspinPlayerId = "";
      this._maSendspinRelayPath = "";
      this._maSendspinRelayClientId = "";
      void this._primeMASendspinRelay().catch(() => {});
      throw err;
    }
  }

  async _ensureMASendspinPlayer() {
    if (this._maSendspinPlayer && this._maSendspinConnected) return this._maSendspinPlayer;
    if (!this._maSendspinRelayPath || !this._maSendspinRelayClientId) await this._primeMASendspinRelay();
    if (!this._maSendspinModule) await this._sendspinModule();
    const player = this._createMASendspinPlayer();
    return this._connectMASendspinPlayer(player);
  }

  async _playMusicAssistant(mediaContentId, title, metadata = {}) {
    this._hardStopAudio(this._musicAudio);
    if (this._embeddedProvider && this._embeddedProvider !== "music_assistant") this._stopEmbeddedMusic();
    const player = await this._ensureMASendspinPlayer();
    // AudioContext.unlock() must remain in the originating user gesture.  The
    // media command arrives here asynchronously after that gesture, so never
    // attempt a second unlock from this handler.
    this._embeddedProvider = "music_assistant";
    this._embeddedController = player;
    this._currentMediaContentId = String(mediaContentId || "");
    this._musicTitle = String(title || this._musicTitle || "Music Assistant");
    const selectedMetadata = this._normalizedMediaMetadata(metadata);
    this._musicMetadata = {
      ...selectedMetadata,
      provider_origin:selectedMetadata.provider_origin
        || (selectedMetadata.provider_name ? `Music Assistant · ${selectedMetadata.provider_name}` : "Music Assistant"),
    };
    this._embeddedPlaying = false;
    const playlistContext = this._activePlaylistContext;
    const playlistItems = Array.isArray(playlistContext?.items) ? playlistContext.items : [];
    const contextItems = playlistItems.filter((item) => this._isMAItem(item) && item?.media_content_id);
    const rebuildContextQueue = ["user","selection"].includes(String(playlistContext?.kind || ""))
      && contextItems.length > 0
      && contextItems.length === playlistItems.length;
    const playPayload = {
      type:"fitness/tv/music/ma/play",
      profile_entry_id:this._profile.entry_id,
      player_id:this._maSendspinPlayerId,
      provider_instance:String(metadata?.provider_instance || ""),
    };
    if (rebuildContextQueue) playPayload.media_content_ids = contextItems.map((item) => String(item.media_content_id));
    else playPayload.media_content_id = this._currentMediaContentId;
    await this._hass.callWS(playPayload);
    this._maQueueProgress = null;
    this._startMAProgressSync();
    // Do not report a successful Play merely because MA accepted the queue
    // command. Wait until Sendspin itself reports that the browser is playing.
    const deadline = performance.now() + 10000;
    while (!this._embeddedPlaying && performance.now() < deadline) {
      if (!this._maSendspinConnected) throw new Error("Music Assistant browser player disconnected");
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    if (!this._embeddedPlaying) {
      throw new Error("Music Assistant accepted the media but Sendspin did not start playback");
    }
    const resumeIndex = Math.max(0, Number(playlistContext?.index || 0) || 0);
    if (resumeIndex > 0) {
      const maxSteps = rebuildContextQueue ? Math.min(resumeIndex, Math.max(0, contextItems.length - 1)) : Math.min(resumeIndex, 100);
      for (let step = 0; step < maxSteps; step += 1) {
        await this._hass.callWS({
          type:"fitness/tv/music/ma/queue",
          profile_entry_id:this._profile.entry_id,
          player_id:this._maSendspinPlayerId,
          action:"next",
        });
      }
      if (playlistContext) playlistContext.index = maxSteps;
      if (rebuildContextQueue && contextItems[maxSteps]?.media_content_id) {
        this._currentMediaContentId = String(contextItems[maxSteps].media_content_id);
      }
    }
    if (selectedMetadata.position > 0) {
      const moved = await this._hass.callWS({
        type:"fitness/tv/music/ma/seek",
        profile_entry_id:this._profile.entry_id,
        player_id:this._maSendspinPlayerId,
        position:selectedMetadata.position,
      });
      this._applyMAQueueProgress(moved, false);
    }
    await this._syncMediaState({
      title:this._musicTitle,
      media_content_id:this._currentMediaContentId,
      playing:true,
      error:false,
      ...this._musicMetadata,
    });
  }

  async _resolveFitnessMedia(mediaContentId) {
    return this._hass.callWS({
      type:"fitness/tv/music/resolve",
      profile_entry_id:this._profile.entry_id,
      media_content_id:mediaContentId,
    });
  }

  async _playSoundCloud(target, mediaContentId, title, metadata = {}) {
    await this._soundCloudApi();
    const host = this._embedHost();
    if (!host) throw new Error("SoundCloud host unavailable");
    this._hardStopAudio(this._musicAudio);
    this._stopEmbeddedMusic();
    const iframe = document.createElement("iframe");
    iframe.allow = "autoplay";
    iframe.src = `https://w.soundcloud.com/player/?url=${encodeURIComponent(target)}&auto_play=true&show_artwork=false&visual=false`;
    host.appendChild(iframe);
    const widget = window.SC.Widget(iframe);
    this._embeddedProvider = "soundcloud";
    this._embeddedController = widget;
    this._embeddedPlaying = false;
    const resumePosition = this._mediaSeconds(metadata?.position ?? this._musicMetadata?.position);
    widget.bind(window.SC.Widget.Events.READY, () => {
      try {
        widget.getCurrentSound?.((sound) => {
          const titleValue = String(sound?.title || "").trim();
          const artistValue = String(sound?.user?.username || sound?.publisher_metadata?.artist || "").trim();
          const thumbValue = String(sound?.artwork_url || sound?.user?.avatar_url || "").trim();
          if (titleValue) this._musicTitle = titleValue;
          this._musicMetadata = {
            ...this._normalizedMediaMetadata(this._musicMetadata),
            artist:artistValue || this._musicMetadata?.artist || "",
            thumbnail:thumbValue || this._musicMetadata?.thumbnail || "",
            details:"SoundCloud",
          };
          this._syncMediaState({title:this._musicTitle,...this._musicMetadata});
          this._updateMediaControls();
        });
        widget.getDuration?.((milliseconds) => this._updateEmbeddedProgress(resumePosition, Number(milliseconds || 0) / 1000, true));
        if (resumePosition > 0) widget.seekTo?.(resumePosition * 1000);
      } catch (_err) {}
      widget.play();
    });
    widget.bind(window.SC.Widget.Events.PLAY_PROGRESS, (event) => {
      this._updateEmbeddedProgress(Number(event?.currentPosition || 0) / 1000, this._embeddedDuration, false);
    });
    widget.bind(window.SC.Widget.Events.PLAY, () => {
      this._embeddedPlaying = true;
      if (!this._ttsDuckingActive) {
        this._syncMediaState({title,media_content_id:mediaContentId,playing:true,error:false});
        this._updateMediaControls();
      }
    });
    widget.bind(window.SC.Widget.Events.PAUSE, () => {
      this._embeddedPlaying = false;
      if (!this._ttsDuckingActive) {
        this._syncMediaState({title,media_content_id:mediaContentId,playing:false,error:false});
        this._updateMediaControls();
      }
    });
    widget.bind(window.SC.Widget.Events.FINISH, () => {
      this._embeddedPlaying = false;
      this._syncMediaState({title,media_content_id:mediaContentId,playing:false,error:false});
      this._updateMediaControls();
    });
    widget.bind(window.SC.Widget.Events.ERROR, () => {
      this._embeddedPlaying = false;
      this._syncMediaState({title,media_content_id:mediaContentId,playing:false,error:true});
      this._updateMediaControls(true);
    });
  }

  _youtubeTarget(target) {
    try {
      const url = new URL(target);
      const host = url.hostname.toLowerCase();
      let videoId = "";
      if (host === "youtu.be") videoId = url.pathname.split("/").filter(Boolean)[0] || "";
      else videoId = url.searchParams.get("v") || "";
      const playlistId = url.searchParams.get("list") || "";
      return {videoId,playlistId};
    } catch (_err) {
      return {videoId:String(target || "").trim(),playlistId:""};
    }
  }

  _startYouTubeProgressSync(player = this._embeddedController) {
    if (this._embeddedProgressTimer) clearInterval(this._embeddedProgressTimer);
    this._embeddedProgressTimer = null;
    if (!player) return;
    const sync = () => {
      if (this._embeddedProvider !== "youtube" || this._embeddedController !== player) return;
      try {
        const position = this._mediaSeconds(player.getCurrentTime?.() ?? this._embeddedPosition);
        const duration = this._mediaSeconds(player.getDuration?.() ?? this._embeddedDuration);
        this._updateEmbeddedProgress(position, duration, false);
      } catch (_err) {}
    };
    sync();
    this._embeddedProgressTimer = setInterval(sync, 500);
  }

  async _playYouTube(target, mediaContentId, title, metadata = {}) {
    await this._youtubeApi();
    const host = this._embedHost();
    if (!host) throw new Error("YouTube host unavailable");
    this._hardStopAudio(this._musicAudio);
    this._stopEmbeddedMusic();
    const slot = document.createElement("div");
    host.appendChild(slot);
    const parsed = this._youtubeTarget(target);
    if (!parsed.videoId && !parsed.playlistId) throw new Error("Invalid YouTube URL");
    const resumePosition = this._mediaSeconds(metadata?.position ?? this._musicMetadata?.position);
    const playerVars = {autoplay:1,playsinline:1};
    if (resumePosition > 0) playerVars.start = Math.floor(resumePosition);
    if (parsed.playlistId) {
      playerVars.listType = "playlist";
      playerVars.list = parsed.playlistId;
      const playlistIndex = Math.max(0, Number(this._activePlaylistContext?.index || 0) || 0);
      if (playlistIndex > 0) playerVars.index = playlistIndex;
    }
    const player = await new Promise((resolve, reject) => {
      let created = null;
      created = new window.YT.Player(slot, {
        width:320,height:180,videoId:parsed.videoId || undefined,playerVars,
        events:{
          onReady:(event) => {
            if (resumePosition > 0) { try { event.target.seekTo?.(resumePosition, true); } catch (_err) {} }
            resolve(created || event.target);
            event.target.playVideo();
          },
          onError:() => reject(new Error("YouTube playback failed")),
          onStateChange:(event) => {
            const playing = event.data === window.YT.PlayerState.PLAYING;
            const paused = event.data === window.YT.PlayerState.PAUSED || event.data === window.YT.PlayerState.ENDED;
            if (playing || paused) {
              this._embeddedPlaying = playing;
              if (!this._ttsDuckingActive) {
                this._syncMediaState({title,media_content_id:mediaContentId,playing,error:false});
                this._updateMediaControls();
              }
            }
          },
        },
      });
    });
    this._embeddedProvider = "youtube";
    this._embeddedController = player;
    this._startYouTubeProgressSync(player);
  }

  async _playFitnessNativeMedia(mediaContentId, title, metadata = {}) {
    const resolved = await this._resolveFitnessMedia(mediaContentId);
    const kind = String(resolved?.kind || "");
    const target = String(resolved?.url || "");
    if (!target) throw new Error("Media target could not be resolved");
    const selectedMetadata = this._normalizedMediaMetadata(metadata);
    const resolvedMetadata = this._normalizedMediaMetadata(resolved);
    const resumePosition = this._mediaSeconds(selectedMetadata.position || resolvedMetadata.position || 0);
    this._musicMetadata = {
      artist:resolvedMetadata.artist || selectedMetadata.artist,
      album:resolvedMetadata.album || selectedMetadata.album,
      year:resolvedMetadata.year || selectedMetadata.year,
      thumbnail:resolvedMetadata.thumbnail || selectedMetadata.thumbnail,
      details:resolvedMetadata.details || selectedMetadata.details,
      provider:resolvedMetadata.provider || selectedMetadata.provider,
      provider_name:resolvedMetadata.provider_name || selectedMetadata.provider_name,
      provider_origin:resolvedMetadata.provider_origin || selectedMetadata.provider_origin,
      position:selectedMetadata.position || resolvedMetadata.position || 0,
      duration:resolvedMetadata.duration || selectedMetadata.duration,
    };
    this._currentMediaContentId = mediaContentId;
    this._musicTitle = String(resolved?.title || title || target);
    if (kind === "audio") {
      this._hardStopMusic();
      this._pendingHtmlAudioResumePosition = resumePosition;
      this._musicAudio.src = this._resolvedMediaUrl(target);
      this._musicAudio.volume = 1;
      this._musicAudio.currentTime = 0;
      try {
        await this._musicAudio.play();
        if (resumePosition > 0) {
          const resumed = await this._resumeHtmlAudio(resumePosition);
          this._musicMetadata = {...this._musicMetadata, ...resumed};
        }
      } catch (err) {
        if (String(resolved?.fallback_kind || "") === "youtube" && resolved?.fallback_url) {
          this._hardStopMusic();
          return this._playYouTube(String(resolved.fallback_url), mediaContentId, this._musicTitle, {...this._musicMetadata, position:resumePosition});
        }
        throw err;
      } finally {
        this._pendingHtmlAudioResumePosition = 0;
      }
      await this._syncMediaState({title:this._musicTitle,media_content_id:mediaContentId,playing:true,error:false,...this._musicMetadata});
      return;
    }
    if (kind === "soundcloud") return this._playSoundCloud(target, mediaContentId, this._musicTitle, this._musicMetadata);
    if (kind === "youtube") return this._playYouTube(target, mediaContentId, this._musicTitle, this._musicMetadata);
    throw new Error("Unsupported Fitness music provider");
  }

  async _playResolvedMedia(mediaContentId, title, metadata = {}) {
    const l = this._labels();
    if (String(mediaContentId || "").startsWith(FITNESS_MUSIC_PREFIXES.music_assistant)) {
      return this._playMusicAssistant(String(mediaContentId || ""), title, metadata);
    }
    if (Object.values(FITNESS_MUSIC_PREFIXES).some((prefix) => String(mediaContentId || "").startsWith(prefix))) {
      return this._playFitnessNativeMedia(String(mediaContentId || ""), title, metadata);
    }
    this._stopEmbeddedMusic();
    let resolved = null;
    let lastError = null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        resolved = await this._hass.callWS({
          type:"media_source/resolve_media",
          media_content_id:mediaContentId,
        });
        if (resolved?.url) break;
      } catch (err) {
        lastError = err;
      }
      await new Promise((resolve) => setTimeout(resolve, 450));
    }
    const mime = String(resolved?.mime_type || "").toLowerCase();
    const audioLike = !mime || mime.startsWith("audio/") || mime.includes("mpegurl") || mime.includes("playlist") || mime === "application/octet-stream";
    const mediaUrl = this._resolvedMediaUrl(resolved?.url);
    if (!mediaUrl || !audioLike) throw (lastError || new Error(l.music_only));
    this._hardStopMusic();
    this._musicMetadata = this._normalizedMediaMetadata(metadata);
    const resumePosition = this._mediaSeconds(this._musicMetadata.position);
    this._pendingHtmlAudioResumePosition = resumePosition;
    this._musicAudio.src = mediaUrl;
    this._musicAudio.volume = 1;
    this._musicAudio.currentTime = 0;
    this._currentMediaContentId = mediaContentId;
    this._musicTitle = title || l.now_playing;
    try {
      await this._musicAudio.play();
      if (resumePosition > 0) {
        const resumed = await this._resumeHtmlAudio(resumePosition);
        this._musicMetadata = {...this._musicMetadata, ...resumed};
      }
    } finally {
      this._pendingHtmlAudioResumePosition = 0;
    }
    await this._syncMediaState({
      title:this._musicTitle,
      media_content_id:this._currentMediaContentId,
      playing:true,
      error:false,
      ...this._musicMetadata,
    });
  }

  async _handleMediaCommand(command, data = {}) {
    const l = this._labels();
    try {
      if (data.playlist_context !== undefined) this._restorePlaylistContext(data.playlist_context || {});
      if (["select","play"].includes(String(command || ""))) this._castFailedMediaContentId = "";
      if (command === "select") {
        await this._playResolvedMedia(String(data.media_content_id || ""), String(data.title || ""), data);
      } else if (command === "play") {
        const requestedId = String(data.media_content_id || this._currentMediaContentId || this._sharedMediaState?.media_content_id || "");
        const attachedSrc = String(this._musicAudio?.getAttribute?.("src") || "").trim();
        const canResumeAttached = !data.fresh_resolve && attachedSrc && requestedId && this._currentMediaContentId === requestedId;
        const canResumeEmbedded = !data.fresh_resolve && this._embeddedController && requestedId && this._currentMediaContentId === requestedId;
        if (canResumeAttached) {
          await this._musicAudio.play();
          await this._syncMediaState({playing:true,error:false});
        } else if (canResumeEmbedded) {
          if (this._embeddedProvider === "soundcloud") {
            this._embeddedController.play?.();
            this._embeddedPlaying = true;
            await this._syncMediaState({playing:true,error:false});
          } else if (this._embeddedProvider === "youtube") {
            this._embeddedController.playVideo?.();
            this._embeddedPlaying = true;
            await this._syncMediaState({playing:true,error:false});
          } else if (this._embeddedProvider === "music_assistant") {
            this._embeddedController.sendCommand?.("play");
            const deadline = performance.now() + 10000;
            while (!this._embeddedPlaying && performance.now() < deadline) {
              if (!this._maSendspinConnected) throw new Error("Music Assistant browser player disconnected");
              await new Promise((resolve) => setTimeout(resolve, 100));
            }
            if (!this._embeddedPlaying) throw new Error("Music Assistant did not deliver an audio stream to this browser");
            await this._syncMediaState({playing:true,error:false,...this._musicMetadata});
          }
        } else if (requestedId) {
          await this._playResolvedMedia(
            requestedId,
            String(data.title || this._musicTitle || this._sharedMediaState?.title || ""),
            {...(this._sharedMediaState || {}), ...data},
          );
        }
      } else if (command === "seek") {
        const requested = this._mediaSeconds(data.position);
        if (String(this._musicAudio?.getAttribute?.("src") || "").trim()) {
          const moved = await this._seekHtmlAudio(requested);
          await this._syncMediaState(moved);
        } else if (["soundcloud","youtube"].includes(this._embeddedProvider)) {
          const moved = await this._seekEmbeddedMedia(this._embeddedProvider, requested);
          await this._syncMediaState(moved);
        } else if (this._embeddedProvider === "music_assistant" && this._maSendspinPlayerId) {
          const moved = await this._hass.callWS({
            type:"fitness/tv/music/ma/seek",
            profile_entry_id:this._profile.entry_id,
            player_id:this._maSendspinPlayerId,
            position:requested,
          });
          this._applyMAQueueProgress(moved, false);
          await this._syncMediaState({
            position:this._mediaSeconds(moved?.position),
            duration:this._mediaSeconds(moved?.duration),
          });
        }
      } else if (command === "pause") {
        this._musicAudio?.pause();
        try {
          if (this._embeddedProvider === "soundcloud") this._embeddedController?.pause?.();
          else if (this._embeddedProvider === "youtube") this._embeddedController?.pauseVideo?.();
          else if (this._embeddedProvider === "music_assistant") this._embeddedController?.sendCommand?.("pause");
        } catch (_err) {}
        this._embeddedPlaying = false;
        await this._syncMediaState({playing:false,error:false});
      } else if (command === "stop") {
        this._hardStopMusic();
        this._hardStopAudio(this._ttsAudio);
        this._audioOwner = false;
        if (!["session_replaced","cast_handoff"].includes(String(data.reason || ""))) {
          await this._syncMediaState({playing:false,error:false});
        }
      }
      this._updateMediaControls();
    } catch (err) {
      console.error("[Fitness TV] media command failed", err);
      const failedMediaContentId = String(data.media_content_id || this._currentMediaContentId || this._sharedMediaState?.media_content_id || "");
      const failedTitle = String(data.title || this._musicTitle || this._sharedMediaState?.title || "");
      const details = this._labels().media_error;
      await this._syncMediaState({
        media_content_id:failedMediaContentId,
        title:failedTitle,
        details,
        playing:false,
        error:Boolean(failedMediaContentId),
      });
      this._updateMediaControls(Boolean(failedMediaContentId));
    }
  }

  async _ackTts(data, success) {
    try {
      await this._hass.callWS({
        type:"fitness/tv/ack",
        profile_entry_id:this._profile?.entry_id,
        announcement_id:data.announcement_id,
        client_id:FITNESS_TV_CLIENT_ID,
        success:Boolean(success),
      });
    } catch (_err) {}
  }

  async _rampMusicVolume(target, duration = 350) {
    const audio = this._musicAudio;
    if (!audio || audio.paused) return;
    const from = Number(audio.volume ?? 1);
    const to = Math.max(0, Math.min(1, Number(target)));
    if (Math.abs(from - to) < 0.01) {
      audio.volume = to;
      return;
    }
    const start = performance.now();
    await new Promise((resolve) => {
      const step = (now) => {
        const progress = Math.min(1, (now - start) / Math.max(1, duration));
        audio.volume = from + ((to - from) * progress);
        if (progress >= 1) resolve();
        else requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }

  async _duckEmbeddedForTts(duck) {
    if (!this._embeddedController || !this._embeddedPlaying) return async () => {};
    const provider = this._embeddedProvider;
    const controller = this._embeddedController;
    if (provider === "youtube") {
      const original = Number(controller.getVolume?.() ?? 100);
      controller.setVolume?.(Math.max(0, Math.min(100, Math.round(original * duck))));
      return async () => { controller.setVolume?.(original); };
    }
    if (provider === "soundcloud") {
      const original = await new Promise((resolve) => {
        let settled = false;
        const done = (value) => { if (!settled) { settled = true; resolve(Number(value ?? 100)); } };
        const timer = setTimeout(() => done(100), 600);
        try { controller.getVolume?.((value) => { clearTimeout(timer); done(value); }); }
        catch (_err) { clearTimeout(timer); done(100); }
      });
      controller.setVolume?.(Math.max(0, Math.min(100, Math.round(original * duck))));
      return async () => { controller.setVolume?.(original); };
    }
    if (provider === "music_assistant") {
      const original = Number(this._embeddedVolume ?? 100);
      controller.setVolume?.(Math.max(0, Math.min(100, Math.round(original * duck))));
      return async () => { controller.setVolume?.(original); };
    }
    return async () => {};
  }

  async _playTvTts(data) {
    const musicWasPlaying = Boolean(this._musicAudio && !this._musicAudio.paused);
    const embeddedWasPlaying = Boolean(this._embeddedController && this._embeddedPlaying);
    const originalVolume = Number(this._musicAudio?.volume ?? this._mediaVolumeLevel ?? 1);
    this._ttsDuckingActive = musicWasPlaying || embeddedWasPlaying;
    const duck = Math.max(0, Math.min(100, Number(data.ducking_percent ?? this._profile?.tv_dashboard?.ducking_percent ?? 25))) / 100;
    let restoreEmbedded = async () => {};
    let success = false;
    try {
      if (musicWasPlaying) await this._rampMusicVolume(originalVolume * duck, 300);
      if (embeddedWasPlaying) restoreEmbedded = await this._duckEmbeddedForTts(duck);
      const resolved = await this._hass.callWS({
        type:"media_source/resolve_media",
        media_content_id:data.media_content_id,
      });
      const ttsUrl = this._resolvedMediaUrl(resolved?.url);
      if (!ttsUrl) throw new Error("TTS media could not be resolved");
      this._ttsAudio.pause();
      this._ttsAudio.volume = 1;
      this._ttsAudio.src = ttsUrl;
      this._ttsAudio.currentTime = 0;
      const finished = new Promise((resolve, reject) => {
        const onEnded = () => { cleanup(); resolve(); };
        const onError = () => { cleanup(); reject(new Error("TTS playback failed")); };
        const cleanup = () => {
          this._ttsAudio.removeEventListener("ended", onEnded);
          this._ttsAudio.removeEventListener("error", onError);
        };
        this._ttsAudio.addEventListener("ended", onEnded, {once:true});
        this._ttsAudio.addEventListener("error", onError, {once:true});
      });
      await this._ttsAudio.play();
      await finished;
      success = true;
    } catch (_err) {
      success = false;
    } finally {
      if (musicWasPlaying) await this._rampMusicVolume(originalVolume, 500);
      if (embeddedWasPlaying) {
        try { await restoreEmbedded(); } catch (_err) {}
      }
      this._ttsDuckingActive = false;
      if (embeddedWasPlaying) {
        await this._syncMediaState({playing:true,error:false});
        this._updateMediaControls();
      }
      await this._ackTts(data, success);
    }
  }

  _fitnessAmbientRgb() {
    const colors = this._intensityColors || {};
    const fallbackRgb = Array.isArray(colors.light) ? colors.light
      : Array.isArray(colors.moderate) ? colors.moderate
      : [3,169,244];
    const sessionState = this._sessionState();
    if (sessionState === "active") {
      const intensityEntity = this._profile?.entities?.heart_rate_intensity;
      const intensity = intensityEntity ? String(this._hass?.states?.[intensityEntity]?.state || "") : "";
      const key = ["very_light","light","moderate","vigorous","near_maximal"].includes(intensity) ? intensity : "moderate";
      const liveRgb = colors[key];
      return {rgb:Array.isArray(liveRgb) && liveRgb.length >= 3 ? liveRgb : fallbackRgb, live:true, intensity:key, state:sessionState};
    }
    if (sessionState === "waiting_for_live_data") return {rgb:[66,165,245],live:true,intensity:"light",state:sessionState};
    if (sessionState === "paused") return {rgb:[255,152,0],live:true,intensity:"moderate",state:sessionState};
    if (sessionState === "recovery") return {rgb:[38,166,154],live:true,intensity:"very_light",state:sessionState};

    const fitnessEntity = this._profile?.entities?.vo2max_percent_predicted;
    const fitness = fitnessEntity ? Number(this._hass?.states?.[fitnessEntity]?.state) : NaN;
    const key = Number.isFinite(fitness)
      ? (fitness >= 110 ? "very_light"
        : fitness >= 100 ? "light"
        : fitness >= 90 ? "moderate"
        : fitness >= 75 ? "vigorous"
        : "near_maximal")
      : "light";
    const rgb = colors[key];
    return {rgb:Array.isArray(rgb) && rgb.length >= 3 ? rgb : fallbackRgb, live:false, intensity:key, state:"idle", fallback:!Number.isFinite(fitness)};
  }

  _applyAmbientBackground() {
    const tone = this._fitnessAmbientRgb();
    const [r,g,b] = (tone?.rgb || [3,169,244]).map((value) => Math.max(0, Math.min(255, Number(value) || 0)));
    const alpha = tone?.live ? 0.44 : 0.27;
    const motion = {
      very_light:{speed:8.8,lift:1.8,energy:.18,breath:1.005,flow:.82},
      light:{speed:7.4,lift:2.1,energy:.22,breath:1.006,flow:.90},
      moderate:{speed:5.9,lift:2.6,energy:.28,breath:1.008,flow:1.00},
      vigorous:{speed:4.5,lift:3.2,energy:.36,breath:1.010,flow:1.12},
      near_maximal:{speed:3.35,lift:3.8,energy:.46,breath:1.012,flow:1.24},
    }[tone?.intensity] || {speed:7.4,lift:2.1,energy:.22,breath:1.006,flow:.90};
    this.style.setProperty("--fitness-tv-ambient-rgb", `${r},${g},${b}`);
    this.style.setProperty("--fitness-tv-ambient-alpha", String(alpha));
    this.style.setProperty("--fitness-tv-ambient-core-alpha", String(alpha * 0.82));
    this.style.setProperty("--fitness-tv-ambient-soft-alpha", String(alpha * 0.38));
    const stateSpeed = tone?.state === "waiting_for_live_data" ? 8.4
      : tone?.state === "paused" ? 9.2
      : tone?.state === "recovery" ? 7.8
      : motion.speed;
    this.style.setProperty("--fitness-motion-speed", `${tone?.live ? stateSpeed : 10.5}s`);
    this.style.setProperty("--fitness-motion-lift", `${tone?.live ? motion.lift : 1.05}px`);
    this.style.setProperty("--fitness-energy-alpha", String(tone?.live ? motion.energy : .14));
    this.style.setProperty("--fitness-card-breath-scale", String(tone?.live ? motion.breath : 1.0055));
    this.style.setProperty("--fitness-ambient-flow", String(tone?.live ? motion.flow : .82));
    this.style.setProperty(
      "--fitness-tv-ambient",
      `linear-gradient(145deg, rgba(${r},${g},${b},${alpha}) 0%, var(--primary-background-color) 78%)`
    );
    this.toggleAttribute("fitness-live-ambient", Boolean(tone?.live));
    this.setAttribute("fitness-workout-zone", String(tone?.intensity || "light"));
    this.setAttribute("fitness-session-state", String(tone?.state || "idle"));
    this.shadowRoot?.querySelectorAll(".tv-card-slot>.tv-mounted-card").forEach((card, index) => {
      card.toggleAttribute("fitness-animations", Boolean(this._animationsEnabled));
      card.toggleAttribute("fitness-live-workout", Boolean(tone?.live));
      card.setAttribute("fitness-workout-zone", String(tone?.intensity || "light"));
      card.setAttribute("fitness-session-state", String(tone?.state || "idle"));
      if (this._motionEnabled()) this._ensureCardLivingMotion(card, index);
    });
  }

  _render() {
    if (!this.shadowRoot) return;
    const castFocusSnapshot = this._castRemoteFocusSnapshot();
    const accessCopy = _fitnessAccessCopy(this._labels());
    if (this._loadError) {
      this.shadowRoot.innerHTML = `<ha-card><div class="fatal">${_fitnessEscape(this._loadError)}</div></ha-card>${this._style()}`;
      return;
    }
    if (this._accessDenied) {
      this.shadowRoot.innerHTML = `<ha-card class="tv-shell"><div class="access-denied"><ha-icon icon="mdi:shield-lock-outline"></ha-icon><div><strong>${_fitnessEscape(accessCopy.denied)}</strong><span>${_fitnessEscape(accessCopy.denied_hint)}</span></div></div></ha-card>${this._style()}`;
      return;
    }
    if (!this._profile) {
      const l = this._labels();
      const noRights = !this._access?.is_admin && !(this._allProfiles || []).length;
      this.shadowRoot.innerHTML = noRights
        ? `<ha-card class="tv-shell"><div class="access-denied"><ha-icon icon="mdi:shield-lock-outline"></ha-icon><div><strong>${_fitnessEscape(accessCopy.denied)}</strong><span>${_fitnessEscape(accessCopy.denied_hint)}</span></div></div></ha-card>${this._style()}`
        : `<ha-card><div class="fatal">${_fitnessEscape(l.tv_no_profiles)}</div></ha-card>${this._style()}`;
      return;
    }
    const l = this._labels();
    const fixedProfile = Boolean(this.config?.profile_entry_id);
    const canControl = Boolean(this._access?.is_admin || this._profile?.access?.can_control);
    const canNavigateProfiles = Boolean(this._access?.is_admin || (this._profiles || []).length > 1);
    this._canControlProfile = canControl;
    const profileOptions = this._profiles.map((profile) => `<option value="${_fitnessEscape(profile.entry_id)}" ${profile.entry_id === this._profile.entry_id ? "selected" : ""}>${_fitnessEscape(profile.profile_name)}${profile.access?.can_control ? "" : ` · ${_fitnessEscape(accessCopy.view_only)}`}</option>`).join("");
    const accessBadge = canControl ? "" : `<span class="view-only-badge"><ha-icon icon="mdi:eye-outline"></ha-icon>${_fitnessEscape(accessCopy.view_only)}</span>`;
    const profileIdentity = fixedProfile
      ? `<div class="tv-profile-identity" title="${_fitnessEscape(this._profile.profile_name)}"><ha-icon icon="mdi:account-circle-outline"></ha-icon><span>${_fitnessEscape(this._profile.profile_name)}</span>${accessBadge}</div>`
      : `<label class="profile-control"><span>${_fitnessEscape(l.tv_profile)}</span><select id="profile">${profileOptions}</select></label>`;
    const profileNavTool = !FITNESS_TV_CAST_RECEIVER && fixedProfile && canNavigateProfiles
      ? `<button class="tool profile-tool" id="profiles" title="${_fitnessEscape(l.tv_profiles)}"><ha-icon icon="mdi:account-multiple-outline"></ha-icon><span>${_fitnessEscape(l.tv_profiles)}</span></button>`
      : "";
    const profileActions = profileNavTool + (FITNESS_TV_CAST_RECEIVER
      ? (canControl ? [
          `<button class="tool backend-tool" id="backend-config" title="${_fitnessEscape(l.configure_account || l.backend_settings)}"><ha-icon icon="mdi:account-cog-outline"></ha-icon><span>${_fitnessEscape(l.configure_account || l.backend_settings)}</span></button>`,
          `<button class="tool configure-tool" id="configure" title="${_fitnessEscape(l.configure_tv || l.reconfigure)}"><ha-icon icon="mdi:cog-outline"></ha-icon><span>${_fitnessEscape(l.configure_tv || l.reconfigure)}</span></button>`,
          `<button class="tool cast-profile-toggle ${this._profile?.tv_dashboard?.light_feedback_enabled !== false ? "active" : ""}" id="light-feedback-toggle" aria-pressed="${this._profile?.tv_dashboard?.light_feedback_enabled !== false ? "true" : "false"}" title="${_fitnessEscape(this._profile?.tv_dashboard?.light_feedback_enabled !== false ? (l.light_feedback_on) : (l.light_feedback_off))}"><ha-icon icon="${this._profile?.tv_dashboard?.light_feedback_enabled !== false ? "mdi:lightbulb-on-outline" : "mdi:lightbulb-off-outline"}"></ha-icon><span>${_fitnessEscape(this._profile?.tv_dashboard?.light_feedback_enabled !== false ? (l.light_feedback_on) : (l.light_feedback_off))}</span></button>`,
          `<button class="tool cast-profile-toggle ${this._profile?.tv_dashboard?.tts_announcements_enabled !== false ? "active" : ""}" id="tts-announcements-toggle" aria-pressed="${this._profile?.tv_dashboard?.tts_announcements_enabled !== false ? "true" : "false"}" title="${_fitnessEscape(this._profile?.tv_dashboard?.tts_announcements_enabled !== false ? (l.tts_announcements_on) : (l.tts_announcements_off))}"><ha-icon icon="${this._profile?.tv_dashboard?.tts_announcements_enabled !== false ? "mdi:account-voice" : "mdi:account-voice-off"}"></ha-icon><span>${_fitnessEscape(this._profile?.tv_dashboard?.tts_announcements_enabled !== false ? (l.tts_announcements_on) : (l.tts_announcements_off))}</span></button>`,
        ].join("") : "")
      : (canControl ? [
          `<button class="tool backend-tool" id="backend-config" title="${_fitnessEscape(l.backend_settings)}"><ha-icon icon="mdi:account-cog-outline"></ha-icon><span>${_fitnessEscape(l.backend_settings)}</span></button>`,
          `<button class="tool configure-tool" id="configure" title="${_fitnessEscape(l.reconfigure)}"><ha-icon icon="mdi:cog-outline"></ha-icon><span>${_fitnessEscape(l.reconfigure)}</span></button>`,
          `<button class="tool" id="cards" title="${_fitnessEscape(l.add_cards)}"><ha-icon icon="mdi:view-grid-plus-outline"></ha-icon><span>${_fitnessEscape(l.add_cards)}</span></button>`,
          `<button class="tool arrange-tool" id="arrange" title="${_fitnessEscape(l.arrange_cards)}" aria-pressed="${this._layoutEditing ? "true" : "false"}"><ha-icon icon="mdi:drag"></ha-icon><span>${_fitnessEscape(l.arrange_cards)}</span></button>`,
          `<button class="tool" id="remote-sensors" title="${_fitnessEscape(l.remote_sensors)}"><ha-icon icon="mdi:access-point"></ha-icon><span>${_fitnessEscape(l.remote_sensors)}</span></button>`,
          `<button class="tool" id="fullscreen" title="${_fitnessEscape(l.fullscreen)}"><ha-icon icon="mdi:fullscreen"></ha-icon><span>${_fitnessEscape(l.fullscreen)}</span></button>`,
          `<button class="tool" id="cast" title="${_fitnessEscape(l.cast_dashboard)}"><ha-icon icon="mdi:cast"></ha-icon><span>${_fitnessEscape(l.cast_dashboard)}</span></button>`,
          `<button class="tool" id="stop-cast" title="${_fitnessEscape(l.cast_stop)}" hidden><ha-icon icon="mdi:cast-off"></ha-icon><span>${_fitnessEscape(l.cast_stop)}</span></button>`,
        ].join("") : ""));
    const musicTools = canControl ? `<button class="icon-tool playlist-control" id="playlist-prev" title="${_fitnessEscape(l.previous)}" hidden><ha-icon icon="mdi:skip-previous"></ha-icon></button>
            <button class="icon-tool" id="play" title="${_fitnessEscape(l.play)}"><ha-icon icon="mdi:play"></ha-icon></button>
            <button class="icon-tool" id="pause" title="${_fitnessEscape(l.pause)}"><ha-icon icon="mdi:pause"></ha-icon></button>
            <button class="icon-tool playlist-control" id="playlist-next" title="${_fitnessEscape(l.next)}" hidden><ha-icon icon="mdi:skip-next"></ha-icon></button>
            <button class="tool media-tool" id="browse" title="${_fitnessEscape(l.media_browser)}"><ha-icon icon="mdi:folder-music-outline"></ha-icon><span>${_fitnessEscape(l.media_browser)}</span></button>
            <button class="icon-tool playlist-control" id="playlist-shuffle" title="${_fitnessEscape(l.shuffle)}" hidden><ha-icon icon="mdi:shuffle"></ha-icon></button>
            <button class="icon-tool playlist-control" id="playlist-repeat" title="${_fitnessEscape(l.repeat)}" hidden><ha-icon icon="mdi:repeat"></ha-icon></button>
            <button class="icon-tool playlist-control" id="playlist-open" title="${_fitnessEscape(l.music_open_playlist)}" hidden><ha-icon icon="mdi:playlist-edit"></ha-icon></button>` : "";
    this.shadowRoot.innerHTML = `
      <ha-card class="tv-shell ${canControl ? "" : "view-only-shell"}">
        <div class="fitness-ambient-layer" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
        <div class="tv-oled-stage">
        <div class="tv-toolbar ${fixedProfile ? "fixed-profile" : ""}">
          <div class="tv-brand"><img class="fitness-brand-icon" src="${_fitnessEscape(_fitnessBrandIconUrl(this._hass))}" alt=""><strong>${_fitnessEscape(l.tv_dashboard)}</strong></div>
          ${profileIdentity}
          <div class="tv-actions">${profileActions}</div>
          <div class="music-controls ${canControl ? "" : "read-only-media"}">
            ${canControl ? `<div class="music-button-strip">${musicTools}</div>` : ""}
            <div class="media-now">
              <div class="media-art"><img id="media-thumb" alt="" hidden><ha-icon id="media-thumb-fallback" icon="mdi:album"></ha-icon></div>
              <div class="media-now-main">
                <div class="media-copy"><small id="media-status"></small><div class="media-scroll-line"><strong id="media-title">${_fitnessEscape(this._musicTitle || l.nothing_playing)}</strong></div><div class="media-scroll-line"><span id="media-artist"></span></div></div>
                <div class="media-progress-wrap">
                  <input id="media-progress" type="range" min="0" max="1" step="0.25" value="0" ${canControl ? "" : "disabled"} aria-label="${_fitnessEscape(l.music_progress)}">
                  <div class="media-time-row"><span id="media-current">0:00</span><span id="media-remaining">—</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
        ${canControl ? "" : `<div class="view-only-notice"><ha-icon icon="mdi:eye-outline"></ha-icon><span>${_fitnessEscape(accessCopy.view_only)} — ${_fitnessEscape(accessCopy.view_only_hint)}</span></div>`}
        <div class="tv-grid" id="grid"></div>
        </div>
        <div id="modal-root"></div>
        <div id="cast-exit-confirm" class="cast-exit-confirm" role="status" aria-live="assertive" hidden></div>
        <div id="cast-focus-tooltip" class="cast-focus-tooltip" role="tooltip" aria-live="polite" hidden></div>
        <div id="fitness-embed-host" class="fitness-embed-host" aria-hidden="true"></div>
      </ha-card>
      ${this._style()}`;
    if (FITNESS_TV_CAST_RECEIVER) {
      this.shadowRoot.querySelectorAll(".tv-toolbar button[title]").forEach((button) => {
        const label = String(button.title || "").trim();
        if (!button.getAttribute("aria-label")) button.setAttribute("aria-label", label);
        button.removeAttribute("title");
      });
    }
    this.shadowRoot.getElementById("profile")?.addEventListener("change", (ev) => this._changeProfile(ev.target.value));
    this.shadowRoot.getElementById("profiles")?.addEventListener("click", () => {
      if (this._access?.is_admin) this._navigateTv("/fitness-tv/main");
      else this._openVisibleProfilesPicker();
    });
    this.shadowRoot.getElementById("backend-config")?.addEventListener("click", () => this._openBackendFlow("options", this._profile.entry_id, this._profile.profile_name));
    this.shadowRoot.getElementById("configure")?.addEventListener("click", () => this._openProfileConfigure());
    this.shadowRoot.getElementById("light-feedback-toggle")?.addEventListener("click", () => void this._toggleProfileTvPreference("light_feedback_enabled"));
    this.shadowRoot.getElementById("tts-announcements-toggle")?.addEventListener("click", () => void this._toggleProfileTvPreference("tts_announcements_enabled"));
    this.shadowRoot.getElementById("cards")?.addEventListener("click", () => this._openCardPicker());
    this.shadowRoot.getElementById("arrange")?.addEventListener("click", () => this._setLayoutEditing(!this._layoutEditing));
    this.shadowRoot.getElementById("remote-sensors")?.addEventListener("click", () => this._openRemoteGateway());
    this.shadowRoot.getElementById("fullscreen")?.addEventListener("click", () => this._toggleFullscreen());
    this._updateFullscreenButton();
    this.shadowRoot.getElementById("cast")?.addEventListener("click", () => {
      if (this._localCastActive || this._localCastServerActive || this._localCastSessionActive()) { void this._stopLocalCast(); return; }
      const activeTarget = String(this._activeCastTarget || "");
      if (this._serverCastActive && activeTarget) { void this._stopCastDashboard(activeTarget); return; }
      this._openCastPicker();
    });
    this.shadowRoot.getElementById("stop-cast")?.addEventListener("click", () => {
      if (this._localCastActive || this._localCastServerActive || this._localCastSessionActive()) { void this._stopLocalCast(); return; }
      const activeTarget = String(this._activeCastTarget || "");
      if (activeTarget) this._stopCastDashboard(activeTarget);
      else this._openCastPicker();
    });
    this.shadowRoot.getElementById("browse")?.addEventListener("click", () => this._openMediaBrowser());
    this.shadowRoot.getElementById("play")?.addEventListener("click", () => this._playMusic());
    this.shadowRoot.getElementById("pause")?.addEventListener("click", () => this._pauseMusic());
    this.shadowRoot.getElementById("playlist-prev")?.addEventListener("click", () => this._playlistTransport("previous"));
    this.shadowRoot.getElementById("playlist-next")?.addEventListener("click", () => this._playlistTransport("next"));
    this.shadowRoot.getElementById("playlist-shuffle")?.addEventListener("click", () => this._playlistTransport("shuffle"));
    this.shadowRoot.getElementById("playlist-repeat")?.addEventListener("click", () => this._playlistTransport("repeat"));
    this.shadowRoot.getElementById("playlist-open")?.addEventListener("click", () => this._openActivePlaylist());
    const progress = this.shadowRoot.getElementById("media-progress");
    if (canControl) {
      progress?.addEventListener("pointerdown", () => { this._mediaProgressScrubbing = true; });
      progress?.addEventListener("input", () => {
        this._mediaProgressScrubbing = true;
        const current = this.shadowRoot?.getElementById("media-current");
        const remaining = this.shadowRoot?.getElementById("media-remaining");
        const value = this._mediaSeconds(progress.value);
        const duration = this._mediaSeconds(progress.max);
        if (current) current.textContent = this._formatMediaTime(value);
        if (remaining) remaining.textContent = duration > 0 ? this._formatMediaTime(duration) : "—";
        clearTimeout(this._seekPreviewTimer);
        this._seekPreviewTimer = setTimeout(() => this._sendMediaCommand("seek", {position:value}), 220);
      });
      progress?.addEventListener("change", () => {
        clearTimeout(this._seekPreviewTimer);
        const requested = this._mediaSeconds(progress.value);
        Promise.resolve(this._sendMediaCommand("seek", {position:requested})).finally(() => {
          this._mediaProgressScrubbing = false;
          if (String(this._currentMediaContentId || "").startsWith(FITNESS_MUSIC_PREFIXES.music_assistant)) {
            void this._syncMAQueueProgress();
          }
        });
      });
      progress?.addEventListener("pointercancel", () => { this._mediaProgressScrubbing = false; });
    }
    this.shadowRoot.querySelector(".tv-shell")?.addEventListener("pointerdown", () => this._markOledInteraction(), {passive:true});
    this.shadowRoot.querySelector(".tv-shell")?.addEventListener("keydown", () => this._markOledInteraction());
    this._mountSelectedCards();
    if (FITNESS_TV_CAST_RECEIVER) {
      setTimeout(() => this._restoreCastRemoteFocusSnapshot(castFocusSnapshot), 0);
    }
    this._setLayoutEditing(canControl && this._layoutEditing);
    this._applyTvDisplayPreferences();
    this._updateMediaControls();
    this._applyAmbientBackground();
    this._reconcileScreenWakeLock();
  }

  async _toggleFullscreen() {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen?.();
      } else {
        const target = this.shadowRoot?.querySelector(".tv-shell") || this;
        await target.requestFullscreen?.();
      }
    } catch (_err) {}
    this._updateFullscreenButton();
  }

  _updateFullscreenButton() {
    const button = this.shadowRoot?.getElementById("fullscreen");
    if (!button) return;
    const l = this._labels();
    const active = Boolean(document.fullscreenElement);
    const label = active ? (l.exit_fullscreen) : (l.fullscreen);
    button.title = label;
    button.querySelector("ha-icon")?.setAttribute("icon", active ? "mdi:fullscreen-exit" : "mdi:fullscreen");
    const span = button.querySelector("span");
    if (span) span.textContent = label;
  }

  _navigateTv(path) {
    const target = String(path || "").trim();
    if (!target) return;
    if (_fitnessOpenExternal(target)) return;
    try {
      history.pushState(null, "", target);
      window.dispatchEvent(new Event("location-changed"));
    } catch (_err) {
      window.location.href = target;
    }
  }

  async _changeProfile(entryId) {
    const next = this._profiles.find((profile) => profile.entry_id === entryId);
    if (!next || next === this._profile) return;
    this._releaseWindowController();
    this._profile = next;
    this._canControlProfile = Boolean(this._access?.is_admin || next?.access?.can_control);
    if (this._canControlProfile) this._claimWindowController();
    try { sessionStorage.setItem(FITNESS_TV_PROFILE_TAB_STORAGE, next.entry_id); } catch (_err) {}
    try { localStorage.setItem(FITNESS_TV_PROFILE_STORAGE, next.entry_id); } catch (_err) {}
    await this._loadPreferences();
    this._render();
    if (this._canControlProfile) await this._heartbeat();
  }

  _setLayoutEditing(enabled) {
    if (!this._canControlProfile) enabled = false;
    this._layoutEditing = Boolean(enabled);
    this.toggleAttribute("layout-editing", this._layoutEditing);
    const button = this.shadowRoot?.getElementById("arrange");
    if (button) button.setAttribute("aria-pressed", this._layoutEditing ? "true" : "false");
    this.shadowRoot?.querySelectorAll(".tv-card-slot").forEach((slot) => {
      slot.draggable = this._layoutEditing;
    });
  }

  async _moveCard(cardId, delta) {
    if (!this._canControlProfile) return;
    const cards = [...(this._selectedCards || [])];
    const index = cards.indexOf(cardId);
    const next = index + Number(delta || 0);
    if (index < 0 || next < 0 || next >= cards.length) return;
    [cards[index], cards[next]] = [cards[next], cards[index]];
    await this._savePreferences(cards);
    this._setLayoutEditing(true);
  }

  async _reorderCard(sourceId, targetId, after = false) {
    if (!this._canControlProfile) return;
    if (!sourceId || !targetId || sourceId === targetId) return;
    const cards = [...(this._selectedCards || [])];
    const sourceIndex = cards.indexOf(sourceId);
    if (sourceIndex < 0 || !cards.includes(targetId)) return;
    cards.splice(sourceIndex, 1);
    let targetIndex = cards.indexOf(targetId);
    if (targetIndex < 0) return;
    if (after) targetIndex += 1;
    cards.splice(targetIndex, 0, sourceId);
    await this._savePreferences(cards);
    this._setLayoutEditing(true);
  }

  _syncCardGridSpan(card, wrapper) {
    if (!card || !wrapper) return;
    const scale = FITNESS_TV_CAST_RECEIVER ? Math.max(0.10, Math.min(1.50, Number(this._tvScalePercent || 70) / 100)) : 1;
    const rowHeight = 4;
    const gap = FITNESS_TV_CAST_RECEIVER ? 6 : 12;
    const rectHeight = Number(card.getBoundingClientRect?.().height || 0);
    const rawHeight = Number(card.offsetHeight || card.scrollHeight || (rectHeight ? rectHeight / scale : 0));
    const visualHeight = Math.max(1, Math.ceil(rawHeight * scale));
    wrapper.style.setProperty("--tv-card-visual-height", `${visualHeight}px`);
    wrapper.style.gridRowEnd = `span ${Math.max(1, Math.ceil((visualHeight + gap) / rowHeight))}`;
  }

  _wireCardReorder(wrapper, cardId) {
    const l = this._labels();
    wrapper.addEventListener("dragstart", (ev) => {
      if (!this._layoutEditing) {
        ev.preventDefault();
        return;
      }
      this._draggedCardId = cardId;
      wrapper.classList.add("dragging");
      if (ev.dataTransfer) {
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", cardId);
      }
    });
    wrapper.addEventListener("dragend", () => {
      this._draggedCardId = "";
      wrapper.classList.remove("dragging");
      this.shadowRoot?.querySelectorAll(".drop-target").forEach((node) => node.classList.remove("drop-target"));
    });
    wrapper.addEventListener("dragover", (ev) => {
      if (!this._layoutEditing || !this._draggedCardId || this._draggedCardId === cardId) return;
      ev.preventDefault();
      if (ev.dataTransfer) ev.dataTransfer.dropEffect = "move";
      wrapper.classList.add("drop-target");
    });
    wrapper.addEventListener("dragleave", () => wrapper.classList.remove("drop-target"));
    wrapper.addEventListener("drop", (ev) => {
      if (!this._layoutEditing) return;
      ev.preventDefault();
      wrapper.classList.remove("drop-target");
      const sourceId = this._draggedCardId || ev.dataTransfer?.getData("text/plain") || "";
      const rect = wrapper.getBoundingClientRect();
      const after = ev.clientY > rect.top + rect.height / 2
        || (Math.abs(ev.clientY - (rect.top + rect.height / 2)) < rect.height * 0.18 && ev.clientX > rect.left + rect.width / 2);
      this._reorderCard(sourceId, cardId, after);
    });
    wrapper.querySelector('[data-move="-1"]')?.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      this._moveCard(cardId, -1);
    });
    wrapper.querySelector('[data-move="1"]')?.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      this._moveCard(cardId, 1);
    });
    wrapper.querySelector(".layout-tools")?.setAttribute("aria-label", l.arrange_cards);
  }

  _profileHasLastWorkoutData(hass = this._hass) {
    if (this._profile?.latest_workout?.available) return true;
    const meaningful = (value) => {
      if (value === null || value === undefined) return false;
      const text = String(value).trim();
      if (!text || ["unknown", "unavailable", "none", "null", "nan"].includes(text.toLowerCase())) return false;
      const number = Number(text);
      // Numeric source metrics at zero do not represent a populated previous
      // workout. Non-numeric values (sport/name/date) still count as content.
      return Number.isFinite(number) ? Math.abs(number) > 1e-9 : true;
    };
    const routes = this._profile?.workout_source_metrics || {};
    for (const route of Object.values(routes)) {
      if (!route || typeof route !== "object") continue;
      if (meaningful(route.value ?? route.configured_value)) return true;
      const entityId = String(route.entity_id || "");
      const state = entityId ? hass?.states?.[entityId] : null;
      if (state && meaningful(state.state)) return true;
    }
    return false;
  }

  _profileOwnsLiveSensor(hass = this._hass) {
    // Assignment, rather than current workout ownership or metric-entity
    // materialization, controls whether the Live Workout card is available.
    // The metric fallback keeps this frontend compatible with an older backend
    // during a rolling Home Assistant/browser cache refresh.
    const assigned = this._profile?.assigned_live_sensor_ids || [];
    return Boolean(String(this._profile?.entry_id || ""))
      && (this._profile?.has_assigned_live_sensor === true
        || assigned.length > 0
        || (this._profile?.live_sensor_metrics || []).some((item) => Boolean(item?.sensor_id || item?.entity_id)));
  }

  _conditionalCardVisibilitySignature(hass = this._hass) {
    if (!this._profile) return "";
    const owners = (this._profile.live_sensor_metrics || []).map((item) => {
      const owner = item?.owner_entity_id ? hass?.states?.[item.owner_entity_id] : null;
      return `${item?.sensor_id || item?.entity_id || ""}:${owner?.attributes?.owner_entry_id || ""}:${owner?.last_updated || ""}`;
    }).join("|");
    const assigned = (this._profile.assigned_live_sensor_ids || []).join(",");
    return `${this._profileHasLastWorkoutData(hass) ? 1 : 0}:${this._profileOwnsLiveSensor(hass) ? 1 : 0}:${assigned}:${owners}`;
  }

  _shouldMountTvCard(cardId, hass = this._hass) {
    if (cardId === "workout") return this._profileHasLastWorkoutData(hass);
    if (cardId === "live_workout") return this._profileOwnsLiveSensor(hass);
    return true;
  }

  _mountSelectedCards() {
    const grid = this.shadowRoot?.getElementById("grid");
    if (!grid || !this._profile) return;
    this._cardResizeObserver?.disconnect?.();
    this._cardResizeObserver = null;
    grid.replaceChildren();
    this._mountedCards = [];
    const catalog = new Map(FITNESS_TV_CARD_CATALOG.map((item) => [item.id, item]));
    const selectedIds = (this._selectedCards || []).filter((id, index, all) => catalog.has(id) && all.indexOf(id) === index && this._shouldMountTvCard(id));
    this._conditionalCardVisibilityKey = this._conditionalCardVisibilitySignature(this._hass);
    const l = this._labels();
    if (globalThis.ResizeObserver) {
      this._cardResizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const card = entry.target;
          const wrapper = card.closest?.(".tv-card-slot") || card.parentElement;
          if (!wrapper?.classList?.contains("tv-card-slot")) continue;
          this._syncCardGridSpan(card, wrapper);
        }
      });
    }
    for (const cardId of selectedIds) {
      const item = catalog.get(cardId);
      if (!item) continue;
      const wrapper = document.createElement("div");
      wrapper.className = `tv-card-slot${this._canControlProfile ? "" : " read-only-card"}`;
      wrapper.style.setProperty("--fitness-card-delay", `${-(this._mountedCards.length % 7) * 0.73}s`);
      if (!this._canControlProfile) {
        // Explicitly granted additional profiles are display-only. Suppress all
        // card interaction (including more-info/entity links and custom-card
        // controls), not merely form controls.
        for (const eventName of ["click", "dblclick", "change", "input", "submit", "contextmenu", "pointerdown", "pointerup", "touchstart", "keydown"]) {
          wrapper.addEventListener(eventName, (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
          }, true);
        }
      }
      wrapper.dataset.cardId = item.id;
      wrapper.draggable = this._layoutEditing;
      const tools = document.createElement("div");
      tools.className = "layout-tools";
      tools.innerHTML = `<ha-icon class="drag-grip" icon="mdi:drag"></ha-icon><button type="button" data-move="-1" title="${_fitnessEscape(l.move_earlier)}" aria-label="${_fitnessEscape(l.move_earlier)}"><ha-icon icon="mdi:arrow-left"></ha-icon></button><button type="button" data-move="1" title="${_fitnessEscape(l.move_later)}" aria-label="${_fitnessEscape(l.move_later)}"><ha-icon icon="mdi:arrow-right"></ha-icon></button>`;
      const card = document.createElement(item.element);
      card.classList.add("tv-mounted-card");
      try {
        card.setConfig?.({profile_entry_id:this._profile.entry_id});
      } catch (_err) {
        continue;
      }
      card.hass = this._hass;
      wrapper.appendChild(tools);
      wrapper.appendChild(card);
      grid.appendChild(wrapper);
      requestAnimationFrame(() => this._syncCardGridSpan(card, wrapper));
      setTimeout(() => this._syncCardGridSpan(card, wrapper), 140);
      this._cardResizeObserver?.observe(card);
      this._wireCardReorder(wrapper, item.id);
      this._mountedCards.push(card);
    }
    this._scheduleDashboardEntryMotion();
  }

  _motionEnabled() {
    return Boolean(this._animationsEnabled)
      && !globalThis.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  }

  _cancelDashboardMotion() {
    for (const animation of this._livingAnimations || []) {
      try { animation?.cancel?.(); } catch (_err) {}
    }
    this._livingAnimations = [];
    for (const card of this._mountedCards || []) {
      card.__fitnessLivingMotion = false;
      card.__fitnessLivingMode = "";
      for (const animation of card.__fitnessLivingAnimations || []) { try { animation?.cancel?.(); } catch (_err) {} }
      card.__fitnessLivingAnimations = [];
      for (const observer of card.__fitnessMotionObservers || []) { try { observer?.disconnect?.(); } catch (_err) {} }
      card.__fitnessMotionObservers = [];
      if (card.__fitnessMotionRebindTimer) clearTimeout(card.__fitnessMotionRebindTimer);
      card.__fitnessMotionRebindTimer = null;
    }
    if (this._dashboardEntryTimer) clearTimeout(this._dashboardEntryTimer);
    this._dashboardEntryTimer = null;
  }

  _rememberLivingAnimation(animation) {
    if (!animation) return animation;
    this._livingAnimations ||= [];
    this._livingAnimations.push(animation);
    return animation;
  }

  _scheduleDashboardEntryMotion() {
    this._cancelDashboardMotion();
    if (!this._motionEnabled()) return;
    this._dashboardEntryTimer = setTimeout(() => this._startDashboardEntryMotion(), 45);
  }

  _startDashboardEntryMotion() {
    if (!this._motionEnabled()) return;
    const wrappers = Array.from(this.shadowRoot?.querySelectorAll?.(".tv-card-slot") || []);
    if (!wrappers.length) return;
    // Card frames are intentionally stationary. Modern motion happens inside
    // each card: title -> charts -> values/entities. This avoids the whole
    // dashboard looking as if its layout is floating or stalling.
    this._dashboardEntryTimer = setTimeout(() => {
      wrappers.forEach((wrapper, index) => {
        const card = wrapper.querySelector?.(".tv-mounted-card");
        if (card) this._animateCardContents(card, index, "entry");
      });
    }, 90);
  }

  _cardMotionRoot(card) {
    return card?.shadowRoot || card || null;
  }

  _cardMotionRoots(card) {
    const first = this._cardMotionRoot(card);
    if (!first?.querySelectorAll) return first ? [first] : [];
    const roots = [];
    const seen = new Set();
    const visit = (root, depth = 0) => {
      if (!root?.querySelectorAll || seen.has(root) || depth > 3) return;
      seen.add(root);
      roots.push(root);
      for (const element of root.querySelectorAll("*")) {
        const tag = String(element?.localName || "");
        if (element?.shadowRoot && tag.startsWith("fitness-")) visit(element.shadowRoot, depth + 1);
      }
    };
    visit(first, 0);
    return roots;
  }

  _cardMotionElements(card, selector) {
    const elements = [];
    const seen = new Set();
    for (const root of this._cardMotionRoots(card)) {
      for (const element of root.querySelectorAll?.(selector) || []) {
        if (seen.has(element)) continue;
        seen.add(element);
        elements.push(element);
      }
    }
    return elements;
  }

  _trackCardAnimation(card, animation) {
    if (!animation) return animation;
    card.__fitnessLivingAnimations ||= [];
    card.__fitnessLivingAnimations.push(animation);
    this._rememberLivingAnimation(animation);
    return animation;
  }

  _finishTransientMotion(animation) {
    if (!animation) return;
    animation.finished?.finally?.(() => {
      try { animation.cancel(); } catch (_err) {}
    });
  }

  _animateChartReveal(root, delay = 0) {
    if (!root || !this._motionEnabled()) return;
    const transient = (animation) => { this._finishTransientMotion(animation); return animation; };
    if (FITNESS_TV_CAST_RECEIVER) {
      const lineSelector = "svg polyline:not(.cursor-line),svg path.actual-line,svg path.trend-line,svg .actual-line,svg .trend-line";
      Array.from(root.querySelectorAll?.(lineSelector) || []).slice(0, 2).forEach((line, index) => {
        transient(line.animate([
          {opacity:.35,transform:"translate3d(-2px,0,0)"},
          {opacity:1,transform:"translate3d(0,0,0)"},
        ], {duration:220,delay:delay + index * 28,easing:"ease-out",fill:"both"}));
      });
      const barSelector = ".axis .bar,.bar-chart .bar,[class*='bar-value'],[data-fitness-bar],.load-fill,.progress-fill,.score-fill,.zone-fill,.recovery-score-track i,.component i";
      Array.from(root.querySelectorAll?.(barSelector) || []).slice(0, 6).forEach((bar, index) => {
        bar.style.transformOrigin = "left center";
        transient(bar.animate([
          {transform:"scaleX(.72)",opacity:.55},
          {transform:"scaleX(1)",opacity:1},
        ], {duration:240,delay:delay + 35 + index * 24,easing:"ease-out",fill:"both"}));
      });
      Array.from(root.querySelectorAll?.(".donut,.pie,.pie-chart,[class*='donut'],[data-fitness-pie]") || []).slice(0, 2).forEach((pie, index) => {
        transient(pie.animate([
          {transform:"scale(.88)",opacity:.45},
          {transform:"scale(1)",opacity:1},
        ], {duration:260,delay:delay + 45 + index * 35,easing:"ease-out",fill:"both"}));
      });
      return;
    }
    const lineSelector = [
      "svg polyline:not(.cursor-line)",
      "svg path.actual-line", "svg path.trend-line",
      "svg .actual-line", "svg .trend-line",
    ].join(",");
    let lineIndex = 0;
    for (const line of root.querySelectorAll?.(lineSelector) || []) {
      try {
        const length = Number(line.getTotalLength?.() || 0);
        if (!(length > 0)) continue;
        const animation = line.animate([
          {strokeDasharray:`${length} ${length}`, strokeDashoffset:length, opacity:.08, filter:"drop-shadow(0 0 0 transparent)"},
          {strokeDasharray:`${length} ${length}`, strokeDashoffset:length * .58, opacity:.68, offset:.42},
          {strokeDasharray:`${length} ${length}`, strokeDashoffset:0, opacity:1, filter:"drop-shadow(0 0 3px color-mix(in srgb,var(--primary-color) 44%,transparent))"},
        ], {duration:980, delay:delay + lineIndex * 90, easing:"cubic-bezier(.16,1,.3,1)", fill:"both"});
        transient(animation);
        lineIndex += 1;
      } catch (_err) {}
    }
    let barIndex = 0;
    const bars = root.querySelectorAll?.([
      ".axis .bar", ".bar-chart .bar", "[class*='bar-value']", "[data-fitness-bar]",
      ".load-fill", ".progress-fill", ".score-fill", ".zone-fill",
    ].join(",")) || [];
    for (const bar of bars) {
      const rect = bar.getBoundingClientRect?.();
      const vertical = Number(rect?.height || 0) > Number(rect?.width || 0) * 1.15;
      bar.style.transformOrigin = vertical ? "center bottom" : "left center";
      const animation = bar.animate(vertical
        ? [
            {transform:"scaleY(0)", opacity:.12, filter:"brightness(.82)"},
            {transform:"scaleY(1.045)", opacity:1, filter:"brightness(1.12)", offset:.82},
            {transform:"scaleY(1)", opacity:1, filter:"brightness(1)"},
          ]
        : [
            {transform:"scaleX(0)", opacity:.12, filter:"brightness(.82)"},
            {transform:"scaleX(1.025)", opacity:1, filter:"brightness(1.12)", offset:.84},
            {transform:"scaleX(1)", opacity:1, filter:"brightness(1)"},
          ],
        {duration:760, delay:delay + 110 + barIndex * 72, easing:"cubic-bezier(.16,1,.3,1)", fill:"both"});
      transient(animation);
      barIndex += 1;
    }
    let pieIndex = 0;
    for (const pie of root.querySelectorAll?.(".donut,.pie,.pie-chart,[class*='donut'],[data-fitness-pie]") || []) {
      const animation = pie.animate([
        {clipPath:"circle(0% at 50% 50%)", transform:"rotate(-24deg) scale(.74)", opacity:.05, filter:"brightness(.78)"},
        {clipPath:"circle(47% at 50% 50%)", transform:"rotate(-5deg) scale(.97)", opacity:.8, offset:.64},
        {clipPath:"circle(72% at 50% 50%)", transform:"rotate(0deg) scale(1)", opacity:1, filter:"brightness(1)"},
      ], {duration:900, delay:delay + 80 + pieIndex * 110, easing:"cubic-bezier(.16,1,.3,1)", fill:"both"});
      transient(animation);
      pieIndex += 1;
    }
    for (const marker of root.querySelectorAll?.(".current-marker,.baseline-marker,.vo2-marker,.cursor-dot") || []) {
      const animation = marker.animate([
        {opacity:0, scale:.35, filter:"brightness(.8)"},
        {opacity:1, scale:1.28, filter:"brightness(1.3)", offset:.72},
        {opacity:1, scale:1, filter:"brightness(1)"},
      ], {duration:520, delay:delay + 620, easing:"cubic-bezier(.16,1,.3,1)", fill:"both"});
      transient(animation);
    }
  }

  _cardRevealElements(root) {
    if (!root?.querySelectorAll) return [];
    const selector = [
      ".entity-link", ".live-metric", ".sleep-summary-metric", ".legend-row",
      ".strength-row", ".metric", ".metric-row", ".stat", ".row", ".signal",
      ".summary-item", ".chip", ".tile", ".value", ".hero-metric", ".rpe-choice",
      ".score", ".hero", ".current", ".recovery-signal", ".adaptation-item",
    ].join(",");
    const candidates = Array.from(root.querySelectorAll(selector)).filter((element) => {
      if (element.closest?.("button") && !element.matches?.("button,.rpe-choice")) return false;
      const rect = element.getBoundingClientRect?.();
      return !rect || (rect.width > 0 && rect.height > 0);
    });
    const selected = [];
    for (const element of candidates) {
      if (selected.some((parent) => parent.contains?.(element))) continue;
      selected.push(element);
      if (selected.length >= 24) break;
    }
    return selected;
  }

  _animateCardContents(card, index = 0, mode = "entry") {
    if (!this._motionEnabled()) return;
    const attempt = Number(card.__fitnessMotionAttempt || 0);
    const roots = this._cardMotionRoots(card);
    if ((!roots.length || !roots.some((root) => root.querySelector?.("ha-card"))) && attempt < 10) {
      card.__fitnessMotionAttempt = attempt + 1;
      setTimeout(() => this._animateCardContents(card, index, mode), 70);
      return;
    }
    card.__fitnessMotionAttempt = 0;
    for (const root of roots) this._installCardMotionSkin(card, root);
    const baseDelay = mode === "entry" ? index * 38 : 0;
    if (FITNESS_TV_CAST_RECEIVER) {
      const title = this._cardMotionElements(card, ".title,.card-title,.composite-head,.live-head,.head,h2,h3")[0];
      if (title) this._finishTransientMotion(title.animate([
        {opacity:.55,transform:"translate3d(-4px,2px,0)"},
        {opacity:1,transform:"translate3d(0,0,0)"},
      ], {duration:180,delay:baseDelay,easing:"ease-out",fill:"both"}));
      roots.forEach((root, rootIndex) => this._animateChartReveal(root, baseDelay + 15 + rootIndex * 12));
      const reveal = this._cardMotionElements(card, ".entity-link,.live-metric,.sleep-summary-metric,.metric,.summary-item,.strength-row,.signal,.legend-row,.value,.hero-metric,.score,.hero,.current").slice(0, 8);
      reveal.forEach((element, elementIndex) => this._finishTransientMotion(element.animate([
        {opacity:.65,transform:"translate3d(0,4px,0)"},
        {opacity:1,transform:"translate3d(0,0,0)"},
      ], {duration:180,delay:baseDelay + 30 + elementIndex * 18,easing:"ease-out",fill:"both"})));
      this._ensureCardLivingMotion(card, index);
      return;
    }
    const title = this._cardMotionElements(card, ".title,.card-title,.composite-head,.live-head,.head,h2,h3")[0];
    if (title) {
      const titleAnimation = title.animate([
        {opacity:0, transform:"translate3d(-12px,8px,0) scale(.94)"},
        {opacity:1, transform:"translate3d(2px,-1px,0) scale(1.018)", offset:.72},
        {opacity:1, transform:"translate3d(0,0,0) scale(1)"},
      ], {duration:460, delay:baseDelay, easing:"cubic-bezier(.16,1,.3,1)", fill:"both"});
      this._finishTransientMotion(titleAnimation);
    }
    roots.forEach((root, rootIndex) => this._animateChartReveal(root, baseDelay + 50 + rootIndex * 26));
    const reveal = [];
    const seen = new Set();
    for (const root of roots) {
      for (const element of this._cardRevealElements(root)) {
        if (seen.has(element)) continue;
        seen.add(element);
        reveal.push(element);
      }
    }
    reveal.slice(0, 32).forEach((element, elementIndex) => {
      const animation = element.animate([
        {opacity:0, transform:"translate3d(0,18px,0) scale(.68)", filter:"blur(3px) brightness(.88)"},
        {opacity:1, transform:"translate3d(0,-2px,0) scale(1.055)", filter:"blur(0) brightness(1.08)", offset:.72},
        {opacity:1, transform:"translate3d(0,0,0) scale(1)", filter:"blur(0) brightness(1)"},
      ], {duration:500, delay:baseDelay + 120 + elementIndex * 42, easing:"cubic-bezier(.16,1,.3,1)", fill:"both"});
      this._finishTransientMotion(animation);
    });
    this._ensureCardLivingMotion(card, index);
  }

  _installCardMotionSkin(card, root) {
    if (!root?.querySelector) return;
    root.host?.toggleAttribute?.("fitness-motion", true);
    root.host?.toggleAttribute?.("fitness-motion-live", this.hasAttribute("fitness-live-ambient"));
    root.host?.toggleAttribute?.("fitness-cast-motion", FITNESS_TV_CAST_RECEIVER);
    if (root.querySelector("style[data-fitness-motion-skin]")) return;
    const style = document.createElement("style");
    style.dataset.fitnessMotionSkin = "1";
    style.textContent = `
      :host([fitness-motion]) .entity-link:not(button),
      :host([fitness-motion]) .live-metric,
      :host([fitness-motion]) .metric,
      :host([fitness-motion]) .sleep-summary-metric,
      :host([fitness-motion]) .summary-item,
      :host([fitness-motion]) .strength-row,
      :host([fitness-motion]) .signal,
      :host([fitness-motion]) .legend-row{
        transform-origin:center;will-change:transform,filter,box-shadow;
      }
      :host([fitness-motion]) .axis,
      :host([fitness-motion]) .progress,
      :host([fitness-motion]) .baseline-scale,
      :host([fitness-motion]) .load-scale{
        position:relative;overflow-x:clip;overflow-y:visible;
      }
      :host([fitness-motion]) .axis::after,
      :host([fitness-motion]) .progress::after,
      :host([fitness-motion]) .baseline-scale::after,
      :host([fitness-motion]) .load-scale::after{
        content:"";position:absolute;inset:-55% auto -55% -34%;width:26%;pointer-events:none;
        background:linear-gradient(100deg,transparent,rgba(255,255,255,.20),transparent);
        transform:skewX(-16deg);opacity:0;
      }
      :host([fitness-motion]) .donut{will-change:transform,filter}
      :host([fitness-motion]) .actual-line,
      :host([fitness-motion]) .trend-line,
      :host([fitness-motion]) svg polyline{will-change:filter,opacity}
      :host([fitness-motion]) .current-marker,
      :host([fitness-motion]) .baseline-marker,
      :host([fitness-motion]) .vo2-marker{will-change:filter,opacity}
      :host([fitness-motion]) .axis::after,
      :host([fitness-motion]) .progress::after,
      :host([fitness-motion]) .baseline-scale::after,
      :host([fitness-motion]) .load-scale::after{
        animation:fitness-data-sheen 2.75s cubic-bezier(.4,0,.2,1) infinite;
        animation-delay:var(--fitness-motion-sheen-delay,-.6s);
      }
      :host([fitness-motion-live]) .axis::after,
      :host([fitness-motion-live]) .progress::after,
      :host([fitness-motion-live]) .baseline-scale::after,
      :host([fitness-motion-live]) .load-scale::after{animation-duration:1.65s}
      @keyframes fitness-data-sheen{
        0%,14%{left:-34%;opacity:0}
        24%{opacity:.08}
        50%{opacity:.5}
        74%{opacity:.10}
        86%,100%{left:116%;opacity:0}
      }
      @media(prefers-reduced-motion:reduce){
        :host([fitness-motion]) *{animation:none!important}
      }
      :host([fitness-cast-motion]) .axis::after,
      :host([fitness-cast-motion]) .progress::after,
      :host([fitness-cast-motion]) .baseline-scale::after,
      :host([fitness-cast-motion]) .load-scale::after{display:none!important;animation:none!important}
    `;
    root.appendChild(style);
  }

  _ensureChartTracer(card, root, index = 0) {
    const svgLines = Array.from(root?.querySelectorAll?.("svg polyline.actual-line,svg .actual-line,svg polyline:not(.trend-line):not(.cursor-line)") || []);
    const line = svgLines.find((candidate) => Number(candidate.getTotalLength?.() || 0) > 10);
    if (!line) return;
    const svg = line.ownerSVGElement;
    if (!svg || svg.querySelector(".fitness-motion-tracer")) return;
    // A moving SVG marker must never enlarge the browser's scrollable area at
    // the final data point. Keep the tracer painted inside the chart viewport.
    svg.style.overflow = "hidden";
    svg.style.overflowClipMargin = "0px";
    let motionPath = "";
    if (String(line.tagName || "").toLowerCase() === "polyline") {
      const points = String(line.getAttribute("points") || "").trim().split(/\s+/).filter(Boolean);
      if (points.length > 1) motionPath = `M ${points[0]} L ${points.slice(1).join(" L ")}`;
    } else {
      motionPath = String(line.getAttribute("d") || "");
    }
    if (!motionPath) return;
    const live = this.hasAttribute("fitness-live-ambient");
    const duration = (live ? 1.8 + (index % 3) * .17 : 3.2 + (index % 4) * .26).toFixed(2);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("class", "fitness-motion-tracer");
    circle.setAttribute("r", live ? "2.1" : "1.7");
    circle.setAttribute("fill", "var(--primary-color)");
    circle.setAttribute("stroke", "var(--card-background-color)");
    circle.setAttribute("stroke-width", ".8");
    circle.setAttribute("opacity", ".95");
    circle.style.filter = "drop-shadow(0 0 3px color-mix(in srgb,var(--primary-color) 72%,transparent))";
    circle.style.pointerEvents = "none";
    const animateMotion = document.createElementNS("http://www.w3.org/2000/svg", "animateMotion");
    animateMotion.setAttribute("path", motionPath);
    animateMotion.setAttribute("dur", `${duration}s`);
    animateMotion.setAttribute("repeatCount", "indefinite");
    animateMotion.setAttribute("calcMode", "linear");
    circle.appendChild(animateMotion);
    svg.appendChild(circle);
  }

  _animateCardStateRefresh(card) {
    if (!this._motionEnabled()) return;
    const values = this._cardMotionElements(card, ".live-metric strong,.metric strong,.score strong,.hero strong,.value strong,.current strong").slice(0, FITNESS_TV_CAST_RECEIVER ? 4 : 10);
    values.forEach((value, index) => {
      const frames = FITNESS_TV_CAST_RECEIVER ? [
        {transform:"translateY(1px) scale(.98)",opacity:.7},
        {transform:"translateY(0) scale(1)",opacity:1},
      ] : [
        {transform:"translateY(2px) scale(.94)", opacity:.58, filter:"brightness(.94)"},
        {transform:"translateY(-1px) scale(1.055)", opacity:1, filter:"brightness(1.16)", offset:.68},
        {transform:"translateY(0) scale(1)", opacity:1, filter:"brightness(1)"},
      ];
      const animation = value.animate(frames, {duration:FITNESS_TV_CAST_RECEIVER ? 150 : 320, delay:index * 24, easing:"ease-out"});
      this._finishTransientMotion(animation);
    });
  }

  _armCardMotionObservers(card, index = 0) {
    for (const observer of card.__fitnessMotionObservers || []) { try { observer?.disconnect?.(); } catch (_err) {} }
    card.__fitnessMotionObservers = [];
    if (!this._motionEnabled() || typeof MutationObserver === "undefined") return;
    const rebind = () => {
      if (!this._motionEnabled()) return;
      if (card.__fitnessMotionRebindTimer) clearTimeout(card.__fitnessMotionRebindTimer);
      card.__fitnessMotionRebindTimer = setTimeout(() => {
        for (const observer of card.__fitnessMotionObservers || []) { try { observer?.disconnect?.(); } catch (_err) {} }
        card.__fitnessMotionObservers = [];
        for (const animation of card.__fitnessLivingAnimations || []) { try { animation?.cancel?.(); } catch (_err) {} }
        card.__fitnessLivingAnimations = [];
        card.__fitnessLivingMotion = false;
        card.__fitnessLivingMode = "";
        this._ensureCardLivingMotion(card, index);
        this._animateCardStateRefresh(card);
      }, FITNESS_TV_CAST_RECEIVER ? 180 : 72);
    };
    for (const root of this._cardMotionRoots(card)) {
      const observer = new MutationObserver((mutations) => {
        const meaningful = mutations.some((mutation) => {
          const changed = [...(mutation.addedNodes || []), ...(mutation.removedNodes || [])];
          return changed.some((node) => {
            if (node?.nodeType !== 1) return true;
            if (node.matches?.("style[data-fitness-motion-skin],.fitness-motion-tracer")) return false;
            return true;
          });
        });
        if (meaningful) rebind();
      });
      observer.observe(root, {childList:true, subtree:false});
      card.__fitnessMotionObservers.push(observer);
    }
  }

  _ensureCastCardLivingMotion(card, index = 0) {
    const roots = this._cardMotionRoots(card);
    if (!roots.length) return;
    const state = String(this.getAttribute("fitness-session-state") || "idle");
    const profile = {
      active:{duration:1450,lift:2.2,scale:1.035,low:.82},
      waiting_for_live_data:{duration:2300,lift:1.5,scale:1.022,low:.74},
      paused:{duration:3200,lift:.7,scale:1.012,low:.84},
      recovery:{duration:2700,lift:1.2,scale:1.025,low:.80},
      idle:{duration:3600,lift:.8,scale:1.014,low:.86},
    }[state] || {duration:3600,lift:.8,scale:1.014,low:.86};
    const mode = `cast:${state}`;
    const activeAnimations = (card.__fitnessLivingAnimations || []).some((animation) => animation?.playState === "running");
    if (card.__fitnessLivingMotion && card.__fitnessLivingMode === mode && activeAnimations) return;
    for (const animation of card.__fitnessLivingAnimations || []) { try { animation?.cancel?.(); } catch (_err) {} }
    card.__fitnessLivingAnimations = [];
    card.__fitnessLivingMotion = true;
    card.__fitnessLivingMode = mode;
    card.toggleAttribute("fitness-motion", true);
    card.toggleAttribute("fitness-motion-live", state !== "idle");
    card.setAttribute("fitness-motion-state", state);
    for (const root of roots) this._installCardMotionSkin(card, root);

    const animate = (element, frames, duration = profile.duration, delay = 0) => {
      if (!element?.animate) return;
      this._trackCardAnimation(card, element.animate(frames, {
        duration,delay,iterations:Infinity,easing:"ease-in-out",
      }));
    };
    const icons = this._cardMotionElements(card, ".title ha-icon,.card-title ha-icon,.composite-icon ha-icon,.live-head>ha-icon,.icon ha-icon,.entity-link ha-icon,.summary-item ha-icon,ha-icon").slice(0, 4);
    icons.forEach((icon, iconIndex) => {
      const name = String(icon.getAttribute?.("icon") || "").toLowerCase();
      const frames = /heart|pulse|cardio/.test(name)
        ? [{transform:"scale(1)",opacity:.9},{transform:`scale(${state === "active" ? 1.09 : 1.045})`,opacity:1,offset:.22},{transform:"scale(1)",opacity:.9}]
        : /run|walk|bike|swim|rowing|motion/.test(name)
          ? [{transform:"translate3d(-1px,0,0) rotate(-1deg)",opacity:.9},{transform:`translate3d(${profile.lift}px,-${profile.lift}px,0) rotate(2deg)`,opacity:1,offset:.5},{transform:"translate3d(-1px,0,0) rotate(-1deg)",opacity:.9}]
          : /sleep|bed|moon|recovery/.test(name)
            ? [{transform:"translate3d(0,1px,0) scale(1)",opacity:.82},{transform:`translate3d(0,-${profile.lift}px,0) scale(${profile.scale})`,opacity:1,offset:.5},{transform:"translate3d(0,1px,0) scale(1)",opacity:.82}]
            : [{transform:"translate3d(0,0,0) scale(1)",opacity:.88},{transform:`translate3d(0,-${profile.lift}px,0) scale(${profile.scale})`,opacity:1,offset:.5},{transform:"translate3d(0,0,0) scale(1)",opacity:.88}];
      animate(icon, frames, profile.duration + iconIndex * 140, -(index * 110 + iconIndex * 260));
    });

    const values = this._cardMotionElements(card, ".live-metric strong,.metric strong,.sleep-summary-metric strong,.summary-item strong,.strength-row strong,.signal strong,.legend-row strong,.score strong,.hero strong,.current strong,.value strong,[data-fitness-value]").slice(0, 6);
    values.forEach((value, valueIndex) => animate(value, [
      {transform:"translate3d(0,0,0) scale(1)",opacity:profile.low},
      {transform:`translate3d(0,-${profile.lift * .55}px,0) scale(${1 + (profile.scale - 1) * .62})`,opacity:1,offset:.5},
      {transform:"translate3d(0,0,0) scale(1)",opacity:profile.low},
    ], profile.duration + 420 + valueIndex * 110, -(valueIndex * 290 + index * 90)));

    const fills = this._cardMotionElements(card, ".bar,.load-fill,.progress-fill,.score-fill,.zone-fill,[data-fitness-bar],.recovery-score-track i,.component i").slice(0, 6);
    fills.forEach((fill, fillIndex) => {
      fill.style.transformOrigin = "left center";
      animate(fill, [
        {transform:"scaleX(.985)",opacity:.86},
        {transform:`scaleX(${state === "active" ? 1.018 : 1.008})`,opacity:1,offset:.5},
        {transform:"scaleX(.985)",opacity:.86},
      ], profile.duration + 520 + fillIndex * 120, -(fillIndex * 310));
    });

    this._cardMotionElements(card, ".donut,.pie,.pie-chart,[class*='donut'],[data-fitness-pie]").slice(0, 2).forEach((pie, pieIndex) => animate(pie, [
      {transform:"scale(.992) rotate(-.4deg)",opacity:.88},
      {transform:`scale(${profile.scale}) rotate(.4deg)`,opacity:1,offset:.5},
      {transform:"scale(.992) rotate(-.4deg)",opacity:.88},
    ], profile.duration + 650 + pieIndex * 180, -(pieIndex * 420 + index * 120)));

    this._cardMotionElements(card, "svg .actual-line,svg .trend-line,svg polyline:not(.cursor-line)").slice(0, 2).forEach((line, lineIndex) => animate(line, [
      {opacity:.72},{opacity:1,offset:.5},{opacity:.72},
    ], profile.duration + 780 + lineIndex * 160, -(lineIndex * 370)));
    this._armCardMotionObservers(card, index);
  }

  _ensureCardLivingMotion(card, index = 0) {
    if (!this._motionEnabled()) return;
    if (FITNESS_TV_CAST_RECEIVER) {
      this._ensureCastCardLivingMotion(card, index);
      return;
    }
    const roots = this._cardMotionRoots(card);
    if (!roots.length) return;
    const live = this.hasAttribute("fitness-live-ambient");
    const mode = live ? `live:${this.getAttribute("fitness-workout-zone") || "light"}` : "idle";
    const skinPresent = roots.every((root) => root.querySelector?.("style[data-fitness-motion-skin]"));
    const activeAnimations = (card.__fitnessLivingAnimations || []).some((animation) => animation?.playState === "running");
    if (card.__fitnessLivingMotion && card.__fitnessLivingMode === mode && skinPresent && activeAnimations) return;
    for (const animation of card.__fitnessLivingAnimations || []) { try { animation?.cancel?.(); } catch (_err) {} }
    card.__fitnessLivingAnimations = [];
    card.__fitnessLivingMotion = true;
    card.__fitnessLivingMode = mode;
    card.toggleAttribute("fitness-motion", true);
    card.toggleAttribute("fitness-motion-live", live);
    for (const root of roots) this._installCardMotionSkin(card, root);

    const icons = this._cardMotionElements(card, ".title ha-icon,.card-title ha-icon,.composite-icon ha-icon,.live-head>ha-icon,.icon ha-icon,.entity-link ha-icon,.metric ha-icon,.summary-item ha-icon,ha-icon").slice(0, 12);
    icons.forEach((icon, iconIndex) => {
      const name = String(icon.getAttribute?.("icon") || "").toLowerCase();
      const duration = (live ? 1350 : 2600) + (iconIndex % 5) * 130;
      let frames;
      if (/heart|pulse|cardio/.test(name)) {
        frames = [
          {transform:"scale(1)",filter:"brightness(1)"},
          {transform:"scale(1.16)",filter:"brightness(1.26)",offset:.18},
          {transform:"scale(.98)",filter:"brightness(1.04)",offset:.34},
          {transform:"scale(1.08)",filter:"brightness(1.16)",offset:.48},
          {transform:"scale(1)",filter:"brightness(1)"},
        ];
      } else if (/run|walk|shoe|bike|bicycle|rowing|swim|motion/.test(name)) {
        frames = [
          {transform:"translate3d(-1px,0,0) rotate(-2deg) scale(1)"},
          {transform:`translate3d(${live ? 4 : 2.5}px,-2px,0) rotate(3deg) scale(${live ? 1.11 : 1.07})`,filter:"brightness(1.16)",offset:.5},
          {transform:"translate3d(-1px,0,0) rotate(-2deg) scale(1)",filter:"brightness(1)"},
        ];
      } else if (/sleep|bed|moon|weather-night/.test(name)) {
        frames = [
          {transform:"translate3d(0,1px,0) rotate(-1deg) scale(1)",opacity:.92},
          {transform:"translate3d(0,-3px,0) rotate(2deg) scale(1.07)",opacity:1,filter:"brightness(1.12)",offset:.5},
          {transform:"translate3d(0,1px,0) rotate(-1deg) scale(1)",opacity:.92,filter:"brightness(1)"},
        ];
      } else if (/flash|lightning|fire|battery|power/.test(name)) {
        frames = [
          {transform:"scale(.98)",filter:"brightness(.94) drop-shadow(0 0 0 transparent)",opacity:.85},
          {transform:"scale(1.11)",filter:"brightness(1.32) drop-shadow(0 0 5px currentColor)",opacity:1,offset:.42},
          {transform:"scale(1)",filter:"brightness(1) drop-shadow(0 0 0 transparent)",opacity:.92},
        ];
      } else {
        frames = [
          {transform:"translate3d(0,0,0) scale(1)",filter:"brightness(1)"},
          {transform:`translate3d(0,${live ? -2.6 : -1.5}px,0) scale(${live ? 1.095 : 1.055})`,filter:"brightness(1.12)",offset:.5},
          {transform:"translate3d(0,0,0) scale(1)",filter:"brightness(1)"},
        ];
      }
      const animation = icon.animate(frames, {duration,delay:-(index * 130 + iconIndex * 270),iterations:Infinity,easing:"cubic-bezier(.45,.05,.55,.95)"});
      this._trackCardAnimation(card, animation);
    });

    // Values are the primary living surface. Each gets a staggered micro-motion
    // instead of moving the entity row/card that contains it.
    const values = this._cardMotionElements(card, [
      ".live-metric strong", ".metric strong", ".sleep-summary-metric strong",
      ".summary-item strong", ".strength-row strong", ".signal strong",
      ".legend-row strong", ".legend-row .pct", ".score strong", ".hero strong",
      ".current strong", ".value strong", ".hi-value", ".metric-value",
      "[data-fitness-value]",
    ].join(",")).slice(0, 30);
    values.forEach((value, valueIndex) => {
      const owner = value.closest?.(".entity-link,.live-metric,.metric,.sleep-summary-metric,.summary-item,.strength-row,.signal,.legend-row,.score,.hero,.current,.value") || value.parentElement;
      const iconName = String(owner?.querySelector?.("ha-icon")?.getAttribute?.("icon") || "").toLowerCase();
      const stateText = String(owner?.textContent || value.textContent || "").trim().toLowerCase();
      const rawValue = String(value.textContent || "").trim().toLowerCase();
      const numeric = Number.parseFloat(rawValue.replace(",", "."));
      const dormant = Number.isFinite(numeric) && Math.abs(numeric) < .0001 && !live;
      let semantic = "value";
      if (/heart|pulse|cardio|bpm|heart rate|heartrate/.test(`${iconName} ${stateText}`)) semantic = "heart";
      else if (/run|walk|shoe|bike|bicycle|rowing|swim|speed|pace|cadence|km\/h|min\/km/.test(`${iconName} ${stateText}`)) semantic = "motion";
      else if (/sleep|bed|moon|recovery|rest|hrv/.test(`${iconName} ${stateText}`)) semantic = "recovery";
      else if (/flash|lightning|fire|battery|power|load|calor|energy|watt/.test(`${iconName} ${stateText}`)) semantic = "energy";
      else if (/%|score|vo2|max|readiness|fitness|progress/.test(stateText)) semantic = "score";
      else if (/time|duration|timer|hour|minute|second|\bms\b/.test(`${iconName} ${stateText}`)) semantic = "time";
      else if (/ready|active|connected|on\b|available|good|optimal/.test(stateText)) semantic = "status";
      const duration = (live ? 1500 : 2850) + (valueIndex % 5) * 125;
      let frames;
      if (dormant) {
        frames = [
          {transform:"scale(1)",opacity:.82,filter:"brightness(.94)"},
          {transform:"scale(1.012)",opacity:.92,filter:"brightness(1.01)",offset:.5},
          {transform:"scale(1)",opacity:.82,filter:"brightness(.94)"},
        ];
      } else if (semantic === "heart") {
        frames = [
          {transform:"scale(1)",filter:"brightness(1)"},
          {transform:`scale(${live ? 1.085 : 1.052})`,filter:"brightness(1.22)",offset:.16},
          {transform:"scale(.992)",filter:"brightness(1.04)",offset:.29},
          {transform:`scale(${live ? 1.045 : 1.026})`,filter:"brightness(1.12)",offset:.42},
          {transform:"scale(1)",filter:"brightness(1)"},
        ];
      } else if (semantic === "motion") {
        frames = [
          {transform:"translate3d(-.8px,0,0) scale(.997)",filter:"brightness(.98)"},
          {transform:`translate3d(${live ? 2.8 : 1.5}px,-1px,0) scale(${live ? 1.04 : 1.022})`,filter:"brightness(1.14)",offset:.5},
          {transform:"translate3d(-.8px,0,0) scale(.997)",filter:"brightness(.98)"},
        ];
      } else if (semantic === "recovery") {
        frames = [
          {transform:"translateY(.7px) scale(.994)",opacity:.9,filter:"brightness(.97)"},
          {transform:`translateY(${live ? -1.8 : -1.15}px) scale(${live ? 1.035 : 1.018})`,opacity:1,filter:"brightness(1.09)",offset:.5},
          {transform:"translateY(.7px) scale(.994)",opacity:.9,filter:"brightness(.97)"},
        ];
      } else if (semantic === "energy") {
        frames = [
          {transform:"scale(.992)",filter:"brightness(.94) saturate(.98) drop-shadow(0 0 0 transparent)",opacity:.9},
          {transform:`scale(${live ? 1.055 : 1.03})`,filter:"brightness(1.24) saturate(1.12) drop-shadow(0 0 4px color-mix(in srgb,var(--primary-color) 48%,transparent))",opacity:1,offset:.43},
          {transform:"scale(1)",filter:"brightness(1) saturate(1) drop-shadow(0 0 0 transparent)",opacity:.95},
        ];
      } else if (semantic === "score") {
        frames = [
          {transform:"translateY(0) scale(.996)",filter:"brightness(.98)"},
          {transform:`translateY(${live ? -2 : -1.15}px) scale(${live ? 1.052 : 1.026})`,filter:"brightness(1.15) saturate(1.08)",offset:.48},
          {transform:"translateY(0) scale(1)",filter:"brightness(1) saturate(1)"},
        ];
      } else if (semantic === "time") {
        frames = [
          {transform:"translateY(0)",opacity:.9},
          {transform:`translateY(${live ? -1.6 : -.8}px)`,opacity:1,filter:"brightness(1.12)",offset:.46},
          {transform:"translateY(0)",opacity:.9,filter:"brightness(1)"},
        ];
      } else if (semantic === "status") {
        frames = [
          {transform:"scale(.995)",filter:"brightness(.98) drop-shadow(0 0 0 transparent)",opacity:.88},
          {transform:`scale(${live ? 1.045 : 1.022})`,filter:"brightness(1.16) drop-shadow(0 0 4px color-mix(in srgb,var(--primary-color) 38%,transparent))",opacity:1,offset:.5},
          {transform:"scale(.995)",filter:"brightness(.98) drop-shadow(0 0 0 transparent)",opacity:.88},
        ];
      } else {
        const variant = valueIndex % 3;
        frames = variant === 0 ? [
          {transform:"translateY(0) scale(1)",filter:"brightness(1)",opacity:.94},
          {transform:`translateY(${live ? -1.9 : -1}px) scale(${live ? 1.045 : 1.023})`,filter:"brightness(1.13)",opacity:1,offset:.5},
          {transform:"translateY(0) scale(1)",filter:"brightness(1)",opacity:.94},
        ] : variant === 1 ? [
          {transform:"scale(1)",filter:"brightness(.98) saturate(.98)"},
          {transform:`scale(${live ? 1.042 : 1.021})`,filter:"brightness(1.11) saturate(1.06)",offset:.54},
          {transform:"scale(1)",filter:"brightness(.98) saturate(.98)"},
        ] : [
          {transform:"translateX(0)",filter:"drop-shadow(0 0 0 transparent) brightness(1)"},
          {transform:`translateX(${live ? 1.5 : .8}px)`,filter:"drop-shadow(0 0 3px color-mix(in srgb,var(--primary-color) 34%,transparent)) brightness(1.1)",offset:.5},
          {transform:"translateX(0)",filter:"drop-shadow(0 0 0 transparent) brightness(1)"},
        ];
      }
      const animation = value.animate(frames, {duration,delay:-(valueIndex * 223 + index * 137),iterations:Infinity,easing:"ease-in-out"});
      this._trackCardAnimation(card, animation);
    });

    // Bar/fill elements get a subtle charge motion of their own. The container
    // never moves, so this reads as live data rather than a floating section.
    const fills = this._cardMotionElements(card, ".bar,.load-fill,.progress-fill,.score-fill,.zone-fill,[data-fitness-bar]").slice(0, 18);
    fills.forEach((fill, fillIndex) => {
      const rect = fill.getBoundingClientRect?.();
      const vertical = Number(rect?.height || 0) > Number(rect?.width || 0) * 1.15;
      fill.style.transformOrigin = vertical ? "center bottom" : "left center";
      const animation = fill.animate(vertical ? [
        {transform:"scaleY(1)",filter:"brightness(.98)"},
        {transform:`scaleY(${live ? 1.055 : 1.025})`,filter:"brightness(1.14)",offset:.48},
        {transform:"scaleY(1)",filter:"brightness(.98)"},
      ] : [
        {transform:"scaleX(1)",filter:"brightness(.98)"},
        {transform:`scaleX(${live ? 1.025 : 1.012})`,filter:"brightness(1.14)",offset:.48},
        {transform:"scaleX(1)",filter:"brightness(.98)"},
      ], {duration:(live ? 1500 : 2850)+(fillIndex%4)*160,delay:-(fillIndex*251),iterations:Infinity,easing:"ease-in-out"});
      this._trackCardAnimation(card, animation);
    });

    const sheenTargets = this._cardMotionElements(card, ".axis,.progress,.baseline-scale,.load-scale").slice(0, 12);
    sheenTargets.forEach((element, targetIndex) => {
      element.style.setProperty("--fitness-motion-sheen-delay", `${-(targetIndex * .31 + index * .17).toFixed(2)}s`);
      const pulse = element.animate([
        {filter:"brightness(.96) saturate(.98)", opacity:.94},
        {filter:`brightness(${live ? 1.17 : 1.09}) saturate(${live ? 1.12 : 1.04})`, opacity:1, offset:.48},
        {filter:"brightness(.96) saturate(.98)", opacity:.94},
      ], {duration:(live ? 1450 : 2250) + targetIndex * 80, delay:-(targetIndex * 280), iterations:Infinity, easing:"ease-in-out"});
      this._trackCardAnimation(card, pulse);
    });

    for (const marker of this._cardMotionElements(card, ".current-marker,.baseline-marker,.vo2-marker,.cursor-dot")) {
      const markerPulse = marker.animate([
        {filter:"brightness(1) drop-shadow(0 0 0 transparent)", opacity:.84},
        {filter:"brightness(1.42) drop-shadow(0 0 5px currentColor)", opacity:1, offset:.44},
        {filter:"brightness(1) drop-shadow(0 0 0 transparent)", opacity:.84},
      ], {duration:live ? 1100 : 1850, delay:-(index * 220), iterations:Infinity, easing:"ease-in-out"});
      this._trackCardAnimation(card, markerPulse);
    }

    for (const pie of this._cardMotionElements(card, ".donut,.pie,.pie-chart,[class*='donut']")) {
      const pieBreath = pie.animate([
        {transform:"scale(1)", filter:"brightness(1) saturate(1)"},
        {transform:`scale(${live ? 1.04 : 1.024})`, filter:`brightness(${live ? 1.12 : 1.06}) saturate(${live ? 1.14 : 1.06})`, offset:.5},
        {transform:"scale(1)", filter:"brightness(1) saturate(1)"},
      ], {duration:live ? 1650 : 2550, delay:-(index * 250), iterations:Infinity, easing:"ease-in-out"});
      this._trackCardAnimation(card, pieBreath);
    }

    for (const line of this._cardMotionElements(card, "svg .actual-line,svg .trend-line,svg polyline:not(.cursor-line)")) {
      const linePulse = line.animate([
        {filter:"drop-shadow(0 0 0 transparent)", opacity:.82},
        {filter:`drop-shadow(0 0 ${live ? 4.5 : 2.5}px color-mix(in srgb,var(--primary-color) ${live ? 78 : 50}%,transparent))`, opacity:1, offset:.5},
        {filter:"drop-shadow(0 0 0 transparent)", opacity:.82},
      ], {duration:live ? 1350 : 2150, delay:-(index * 290), iterations:Infinity, easing:"ease-in-out"});
      this._trackCardAnimation(card, linePulse);
    }
    roots.forEach((root, rootIndex) => this._ensureChartTracer(card, root, index + rootIndex));
    this._armCardMotionObservers(card, index);
  }

  _animateRemoteSectionInterior(section, active = false) {
    if (!section || !this._motionEnabled()) return;
    if (FITNESS_TV_CAST_RECEIVER) {
      const animation = section.animate([
        {opacity:.88,transform:"translate3d(0,1px,0)"},
        {opacity:1,transform:"translate3d(0,0,0)"},
      ], {duration:active ? 105 : 125,easing:"ease-out"});
      this._finishTransientMotion(animation);
      return;
    }
    const card = section.querySelector?.(".tv-mounted-card");
    if (card) {
      this._animateCardContents(card, 0, active ? "remote-active" : "remote-select");
      const accents = this._cardMotionElements(card, ".live-metric strong,.metric strong,.sleep-summary-metric strong,.summary-item strong,.strength-row strong,.signal strong,.legend-row strong,.legend-row .pct,.hero strong,.score strong,.current-marker,.baseline-marker,.vo2-marker,.donut,.pie,.progress-fill,.load-fill,ha-icon").slice(0, 16);
      accents.forEach((element, index) => {
        const animation = element.animate([
          {transform:"translate3d(0,0,0) scale(1)", filter:"brightness(1)"},
          {transform:`translate3d(0,-${active ? 2.5 : 1.5}px,0) scale(${active ? 1.09 : 1.055})`, filter:"brightness(1.18)", offset:.58},
          {transform:"translate3d(0,0,0) scale(1)", filter:"brightness(1)"},
        ], {duration:360, delay:index * 28, easing:"cubic-bezier(.16,1,.3,1)"});
        this._finishTransientMotion(animation);
      });
      return;
    }
    const targets = Array.from(section.querySelectorAll?.("button,.tv-brand,.tv-profile-identity,.media-art,.media-copy,.media-progress-wrap") || []).filter((element) => !element.hidden).slice(0, 10);
    targets.forEach((element, index) => {
      const animation = element.animate([
        {opacity:.72, transform:"translateY(7px) scale(.92)", filter:"brightness(.92)"},
        {opacity:1, transform:"translateY(-2px) scale(1.06)", filter:"brightness(1.13)", offset:.7},
        {opacity:1, transform:"translateY(0) scale(1)", filter:"brightness(1)"},
      ], {duration:360, delay:index * 34, easing:"cubic-bezier(.16,1,.3,1)"});
      this._finishTransientMotion(animation);
    });
  }

  _previewTvScale(value) {
    if (!this._profile?.entry_id || !this._hass || !this._canControlProfile) return;
    const scale = Math.max(10, Math.min(150, Number(value || 70)));
    this._tvScalePercent = scale;
    this._applyTvDisplayPreferences();
    clearTimeout(this._tvScalePreviewTimer);
    this._tvScalePreviewTimer = setTimeout(() => {
      void this._hass.callWS({
        type:"fitness/tv/preferences/save",
        profile_entry_id:this._profile.entry_id,
        tv_scale_percent:scale,
      }).catch(() => {});
    }, 140);
  }

  async _toggleProfileTvPreference(key) {
    if (!this._profile?.entry_id || !this._hass || !this._canControlProfile) return;
    if (!["light_feedback_enabled", "tts_announcements_enabled"].includes(String(key))) return;
    const current = this._profile?.tv_dashboard?.[key] !== false;
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/preferences/save",
        profile_entry_id:this._profile.entry_id,
        [key]:!current,
      });
      this._profile.tv_dashboard ||= {};
      this._profile.tv_dashboard[key] = Boolean(result?.[key] ?? !current);
      this._render();
    } catch (err) {
      console.error("[Fitness TV] preference toggle failed", key, err);
    }
  }

  _openVisibleProfilesPicker() {
    const profiles = (this._profiles || []).filter((profile) => profile?.access?.can_view !== false);
    if (!profiles.length) return;
    const l = this._labels();
    const accessCopy = _fitnessAccessCopy(this._labels());
    const rows = profiles.map((profile) => `<button class="media-row visible-profile-row" data-visible-profile="${_fitnessEscape(profile.entry_id)}"><ha-icon icon="${profile.access?.can_control ? "mdi:account-circle" : "mdi:eye-outline"}"></ha-icon><span><strong>${_fitnessEscape(profile.profile_name)}</strong><small>${_fitnessEscape(profile.access?.can_control ? accessCopy.own : accessCopy.view_only)}</small></span><ha-icon icon="mdi:chevron-right"></ha-icon></button>`).join("");
    this._showModal(`<div class="modal-card picker-modal"><div class="modal-head"><strong class="modal-title-with-icon"><ha-icon icon="mdi:account-multiple-outline"></ha-icon>${_fitnessEscape(l.tv_profiles)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="picker-list">${rows}</div></div>`);
    const root = this.shadowRoot?.getElementById("tv-modal");
    root?.querySelectorAll(".visible-profile-row").forEach((button) => button.addEventListener("click", () => {
      const entryId = String(button.dataset.visibleProfile || "");
      if (entryId) this._navigateTv(`/fitness-tv/profile-${entryId}`);
    }));
  }

  async _openProfileConfigure() {
    if (!this._profile || !this._canControlProfile) return;
    const l = this._labels();
    try {
      const data = await this._hass?.callWS({type:"fitness/dashboard/config"});
      if (Array.isArray(data?.cast_targets)) this._castTargets = data.cast_targets;
      if (Array.isArray(data?.audio_outputs)) this._audioOutputs = data.audio_outputs;
      const refreshed = (data?.profiles || []).find((item) => item.entry_id === this._profile.entry_id);
      if (refreshed) this._profile = refreshed;
    } catch (_err) {}
    try { await this._loadMusicAdapters(); } catch (_err) { this._musicAdapters = []; }
    const current = this._profile?.tv_dashboard || {};
    const isAdmin = Boolean(this._access?.is_admin);
    const preferred = String(current.cast_media_player_id || "");
    const targets = Array.isArray(this._castTargets) ? this._castTargets : [];
    const targetOptions = [
      `<option value="">${_fitnessEscape(l.no_default_tv)}</option>`,
      ...targets.map((target) => {
        const unavailable = target?.available === false;
        const suffix = unavailable ? ` (${l.cast_unavailable})` : "";
        return `<option value="${_fitnessEscape(target.entity_id)}" ${target.entity_id === preferred ? "selected" : ""} ${unavailable ? "disabled" : ""}>${_fitnessEscape(target.name || target.entity_id)}${_fitnessEscape(suffix)}</option>`;
      }),
    ].join("");
    const audioOutputId = String(this._audioOutputId || current.audio_output_id || "__fitness_browser__");
    const audioOutputs = (Array.isArray(this._audioOutputs) ? this._audioOutputs : []).filter((output) => String(output?.entity_id || "") !== preferred);
    const audioOutputOptions = [
      `<option value="__fitness_browser__" ${audioOutputId === "__fitness_browser__" || audioOutputId === preferred ? "selected" : ""}>${_fitnessEscape(l.audio_output_browser)}</option>`,
      ...audioOutputs.map((output) => {
        const stateSuffix = ["unavailable","unknown"].includes(String(output?.state || "")) ? ` · ${l.unavailable}` : "";
        const maSuffix = output.music_assistant ? " · Music Assistant" : "";
        return `<option value="${_fitnessEscape(output.entity_id)}" ${output.entity_id === audioOutputId ? "selected" : ""}>${_fitnessEscape(output.name || output.entity_id)}${_fitnessEscape(maSuffix + stateSuffix)}</option>`;
      }),
    ].join("");
    const scale = Math.max(10, Math.min(150, Number(this._tvScalePercent ?? current.tv_scale_percent ?? 70)));
    const duck = Math.max(0, Math.min(100, Number(current.ducking_percent ?? 25)));
    const oled = Boolean(this._oledProtection ?? current.oled_protection);
    const animations = Boolean(this._animationsEnabled ?? current.animations_enabled ?? true);
    const ignoreLightsWhenCastActive = Boolean(current.ignore_lights_when_cast_active ?? true);
    const adapterRows = (this._musicAdapters || []).filter((adapter) => adapter?.available !== false).map((adapter) => {
      const checked = Boolean(adapter.selected);
      const hint = _fitnessMusicAdapterHint(l, adapter);
      const accounts = Array.isArray(adapter.account_options) ? adapter.account_options : [];
      const savedAccount = String(this._musicAdapterOptions?.[adapter.id]?.account_id || adapter.selected_account_id || "");
      const accountMarkup = accounts.length ? `<select class="adapter-account" data-config-music-account="${_fitnessEscape(adapter.id)}" title="${_fitnessEscape(l.music_account)}">${accounts.map((account) => `<option value="${_fitnessEscape(account.id)}" ${String(account.id) === savedAccount ? "selected" : ""}>${_fitnessEscape(account.name || account.id)}</option>`).join("")}</select>` : "";
      const setupMarkup = adapter.setup_path ? `<button type="button" class="adapter-setup" data-adapter-setup="${_fitnessEscape(adapter.setup_path)}"><span>${_fitnessEscape(l.music_configure_provider)}</span></button>` : "";
      return `<div class="music-adapter-row"><input type="checkbox" data-config-music-adapter="${_fitnessEscape(adapter.id)}" ${checked ? "checked" : ""}><ha-icon icon="${String(adapter.icon || "mdi:music-note").startsWith("mdi:") ? _fitnessEscape(adapter.icon) : "mdi:music-note"}"></ha-icon><span><strong>${_fitnessEscape(adapter.name || adapter.id)}</strong>${hint ? `<small>${_fitnessEscape(hint)}</small>` : ""}</span><div class="adapter-actions">${accountMarkup}${setupMarkup}<button type="button" class="adapter-setup adapter-remove" data-remove-music-adapter="${_fitnessEscape(adapter.id)}" title="${_fitnessEscape(l.remove)}"><ha-icon icon="mdi:minus-circle-outline"></ha-icon><span>${_fitnessEscape(l.remove)}</span></button></div></div>`;
    }).join("");
    const searchLimit = Math.max(10, Math.min(100, Number(this._musicSearchLimit || 50)));
    this._showModal(`
      <div class="modal-card configure-modal">
        <div class="modal-head"><strong>${_fitnessEscape(l.reconfigure_profile)}: ${_fitnessEscape(this._profile.profile_name)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        <div class="profile-settings">
          ${isAdmin ? `<label class="setting-toggle"><span><strong class="setting-title"><ha-icon icon="mdi:monitor-dashboard"></ha-icon>${_fitnessEscape(l.enable_tv_view)}</strong><small>${_fitnessEscape(l.enable_tv_view_hint)}</small></span><input id="cfg-enabled" type="checkbox" ${current.enabled ? "checked" : ""}></label>` : ""}
          <div class="setting-adapters"><div class="setting-adapters-head"><span><strong>${_fitnessEscape(l.music_adapters)}</strong><small>${_fitnessEscape(l.music_adapters_hint)}</small></span><button type="button" class="adapter-setup" id="cfg-add-provider"><ha-icon icon="mdi:plus"></ha-icon><span>${_fitnessEscape(l.music_add_provider)}</span></button></div><div class="music-adapter-list">${adapterRows || `<div class="browser-empty">${_fitnessEscape(l.music_no_adapters)}</div>`}</div></div>
          <label class="setting-range"><span><strong>${_fitnessEscape(l.music_search_result_count)}</strong><small>${_fitnessEscape(l.music_search_result_count_hint)}</small></span><input id="cfg-search-limit" type="range" min="10" max="100" step="10" value="${searchLimit}"><output id="cfg-search-limit-value">${searchLimit}</output></label>
          ${isAdmin ? `<label class="setting-field"><span>${_fitnessEscape(l.default_tv)}</span><select id="cfg-target">${targetOptions}</select></label>` : ""}
          <label class="setting-field audio-output-field"><span><strong>${_fitnessEscape(l.audio_output)}</strong><small>${_fitnessEscape(l.audio_output_hint)}</small></span><select id="cfg-audio-output">${audioOutputOptions}</select></label>
          <label class="setting-range"><span><strong>${_fitnessEscape(l.tts_ducking)}</strong><small>${_fitnessEscape(l.tts_ducking_hint)}</small></span><input id="cfg-duck" type="range" min="0" max="100" step="5" value="${duck}"><output id="cfg-duck-value">${duck}%</output></label>
          <label class="setting-range"><span><strong>${_fitnessEscape(l.tv_scale)}</strong><small>${_fitnessEscape(l.tv_scale_hint)}</small></span><input id="cfg-scale" type="range" min="10" max="150" step="5" value="${scale}"><output id="cfg-scale-value">${scale}%</output></label>
          <label class="setting-toggle"><span><strong>${_fitnessEscape(l.ignore_lights_when_cast_active)}</strong><small>${_fitnessEscape(l.ignore_lights_when_cast_active_hint)}</small></span><input id="cfg-ignore-lights" type="checkbox" ${ignoreLightsWhenCastActive ? "checked" : ""}></label>
          <label class="setting-toggle"><span><strong>${_fitnessEscape(l.dashboard_animations)}</strong><small>${_fitnessEscape(l.dashboard_animations_hint)}</small></span><input id="cfg-animations" type="checkbox" ${animations ? "checked" : ""}></label>
          <label class="setting-toggle"><span><strong>${_fitnessEscape(l.oled_protection)}</strong><small>${_fitnessEscape(l.oled_protection_hint)}</small></span><input id="cfg-oled" type="checkbox" ${oled ? "checked" : ""}></label>
        </div>
        <div class="settings-actions"><button class="tool" id="cfg-save"><ha-icon icon="mdi:content-save-outline"></ha-icon><span>${_fitnessEscape(l.save)}</span></button><span class="settings-status" id="cfg-status"></span></div>
      </div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    const duckInput = root?.querySelector("#cfg-duck");
    const scaleInput = root?.querySelector("#cfg-scale");
    duckInput?.addEventListener("input", () => { const out = root.querySelector("#cfg-duck-value"); if (out) out.textContent = `${duckInput.value}%`; });
    scaleInput?.addEventListener("input", () => {
      const out = root.querySelector("#cfg-scale-value");
      if (out) out.textContent = `${scaleInput.value}%`;
      this._previewTvScale(scaleInput.value);
    });
    const searchLimitInput = root?.querySelector("#cfg-search-limit");
    searchLimitInput?.addEventListener("input", () => { const out = root.querySelector("#cfg-search-limit-value"); if (out) out.textContent = searchLimitInput.value; });
    root?.querySelectorAll("[data-adapter-setup]").forEach((button) => button.addEventListener("click", () => this._navigateTv(String(button.dataset.adapterSetup || "/config/integrations"))));
    root?.querySelector("#cfg-add-provider")?.addEventListener("click", () => this._openMusicProviderCatalog());
    root?.querySelectorAll("[data-remove-music-adapter]").forEach((button) => button.addEventListener("click", () => {
      const adapterId = String(button.dataset.removeMusicAdapter || "");
      const row = button.closest(".music-adapter-row");
      const checkbox = row?.querySelector("input[data-config-music-adapter]");
      if (checkbox) checkbox.checked = false;
      row?.classList.add("profile-adapter-removed");
      button.disabled = true;
    }));
    root?.querySelector("#cfg-save")?.addEventListener("click", () => this._saveProfileConfigure(root));
  }

  _openMusicProviderCatalog() {
    const l = this._labels();
    const providers = Array.isArray(this._musicProviderCatalog) ? this._musicProviderCatalog : [];
    const rows = providers.map((provider) => {
      const isYtdlp = provider.id === "yt_dlp" || provider.kind === "fitness_optional_adapter";
      const icon = String(provider.icon || "mdi:music-note").startsWith("mdi:") ? String(provider.icon || "mdi:music-note") : "mdi:music-note";
      const action = isYtdlp
        ? `<button type="button" class="adapter-setup" data-ytdlp-toggle="${provider.enabled ? "disable" : "enable"}"><span>${_fitnessEscape(provider.enabled ? (l.disable) : (l.music_enable_provider))}</span></button>`
        : `<button type="button" class="adapter-setup" data-provider-path="${_fitnessEscape(provider.setup_path || "/config/integrations")}"><span>${_fitnessEscape(provider.installed ? (l.music_configure_provider) : (l.music_install_provider))}</span></button>`;
      return `<div class="provider-catalog-row ${isYtdlp ? "provider-catalog-ytdlp" : ""}"><ha-icon icon="${_fitnessEscape(icon)}"></ha-icon><span><strong>${_fitnessEscape(_fitnessMusicProviderName(l, provider))}</strong><small>${_fitnessEscape(_fitnessMusicProviderDescription(l, provider))}</small></span>${action}</div>`;
    }).join("");
    this._showModal(`<div class="modal-card provider-catalog-modal"><div class="modal-head"><strong>${_fitnessEscape(l.music_add_provider)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="provider-catalog-list">${rows || `<div class="browser-empty">${_fitnessEscape(l.music_no_provider_catalog)}</div>`}</div></div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    root?.querySelectorAll("[data-provider-path]").forEach((button) => button.addEventListener("click", () => this._navigateTv(String(button.dataset.providerPath || "/config/integrations"))));
    root?.querySelectorAll("[data-ytdlp-toggle]").forEach((button) => button.addEventListener("click", () => {
      const enable = String(button.dataset.ytdlpToggle || "") === "enable";
      if (enable) this._openYtdlpAcknowledgement();
      else void this._setYtdlpEnabled(false, true);
    }));
  }

  _openYtdlpAcknowledgement() {
    const l = this._labels();
    const disclaimer = l.ytdlp_disclaimer;
    this._showModal(`<div class="modal-card ytdlp-legal-modal"><div class="modal-head"><div class="browser-title"><button class="icon-tool ytdlp-back"><ha-icon icon="mdi:arrow-left"></ha-icon></button><strong>${_fitnessEscape(l.ytdlp_enabled)}</strong></div><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="modal-scroll-body ytdlp-legal-body"><div class="browser-warning"><ha-icon icon="mdi:shield-alert-outline"></ha-icon><span>${_fitnessEscape(disclaimer)}</span></div><label class="setting-toggle ytdlp-accept"><span><strong>${_fitnessEscape(l.ytdlp_accept)}</strong><small>${_fitnessEscape(l.ytdlp_accept_hint)}</small></span><input type="checkbox" id="ytdlp-accept"></label></div><div class="modal-actions"><button class="primary-tool ytdlp-enable" disabled><ha-icon icon="mdi:check"></ha-icon><span>${_fitnessEscape(l.music_enable_provider)}</span></button></div></div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    const accept = root?.querySelector("#ytdlp-accept");
    const enable = root?.querySelector(".ytdlp-enable");
    accept?.addEventListener("change", () => { if (enable) enable.disabled = !accept.checked; });
    root?.querySelector(".ytdlp-back")?.addEventListener("click", () => this._openMusicProviderCatalog());
    enable?.addEventListener("click", () => void this._setYtdlpEnabled(true, Boolean(accept?.checked)));
  }

  async _setYtdlpEnabled(enabled, acknowledged = false) {
    const l = this._labels();
    try {
      await this._hass.callWS({
        type:"fitness/tv/music/ytdlp",
        profile_entry_id:this._profile.entry_id,
        enabled:Boolean(enabled),
        acknowledged:Boolean(acknowledged),
      });
      this._ytdlpEnabled = Boolean(enabled);
      if (this._profile?.tv_dashboard) this._profile.tv_dashboard.ytdlp_enabled = Boolean(enabled);
      await this._loadMusicAdapters();
      this._openMusicProviderCatalog();
    } catch (err) {
      console.error("[Fitness TV] yt-dlp setting update failed", err);
      const root = this.shadowRoot?.getElementById("modal-root");
      const status = root?.querySelector(".browser-warning") || root?.querySelector(".provider-catalog-list");
      if (status) status.setAttribute("data-error", l.save_failed);
    }
  }

  async _saveProfileConfigure(root) {
    if (!this._profile || !root) return;
    const l = this._labels();
    const button = root.querySelector("#cfg-save");
    const status = root.querySelector("#cfg-status");
    const enabled = root.querySelector("#cfg-enabled") ? Boolean(root.querySelector("#cfg-enabled")?.checked) : Boolean(this._profile?.tv_dashboard?.enabled);
    const castTarget = root.querySelector("#cfg-target") ? String(root.querySelector("#cfg-target")?.value || "") : String(this._profile?.tv_dashboard?.cast_media_player_id || "");
    const previousAudioOutput = String(this._audioOutputId || this._profile?.tv_dashboard?.audio_output_id || "__fitness_browser__");
    const audioOutputId = String(root.querySelector("#cfg-audio-output")?.value || "__fitness_browser__");
    const ducking = Number(root.querySelector("#cfg-duck")?.value || 25);
    const scale = Number(root.querySelector("#cfg-scale")?.value || 70);
    const oled = Boolean(root.querySelector("#cfg-oled")?.checked);
    const animations = Boolean(root.querySelector("#cfg-animations")?.checked);
    const ignoreLightsWhenCastActive = Boolean(root.querySelector("#cfg-ignore-lights")?.checked);
    const musicAdapters = [...root.querySelectorAll('input[data-config-music-adapter]:checked')].map((input) => String(input.dataset.configMusicAdapter || "")).filter(Boolean);
    const musicSearchLimit = Math.max(10, Math.min(100, Number(root.querySelector("#cfg-search-limit")?.value || 50)));
    const musicAdapterOptions = {...(this._musicAdapterOptions || {})};
    const removedMusicAdapters = new Set(
      [...root.querySelectorAll(".music-adapter-row.profile-adapter-removed [data-remove-music-adapter]")]
        .map((control) => String(control.dataset.removeMusicAdapter || ""))
        .filter(Boolean),
    );
    for (const adapterId of removedMusicAdapters) delete musicAdapterOptions[adapterId];
    root.querySelectorAll("select[data-config-music-account]").forEach((select) => {
      const adapterId = String(select.dataset.configMusicAccount || "");
      if (adapterId && !removedMusicAdapters.has(adapterId)) {
        musicAdapterOptions[adapterId] = {...(musicAdapterOptions[adapterId] || {}), account_id:String(select.value || "")};
      }
    });
    if (button) button.disabled = true;
    if (status) status.textContent = l.saving;
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/profile/configure",
        profile_entry_id:this._profile.entry_id,
        enabled,
        cast_media_player_id:castTarget,
        ducking_percent:ducking,
        ignore_lights_when_cast_active:ignoreLightsWhenCastActive,
        tv_scale_percent:scale,
        oled_protection:oled,
      });
      const prefs = await this._hass.callWS({
        type:"fitness/tv/preferences/save",
        profile_entry_id:this._profile.entry_id,
        audio_output_id:audioOutputId,
        animations_enabled:animations,
        music_adapters:musicAdapters,
        music_adapter_options:musicAdapterOptions,
        music_search_limit:musicSearchLimit,
      });
      this._musicSearchLimit = Number(prefs?.music_search_limit || musicSearchLimit);
      this._musicAdapterOptions = prefs?.music_adapter_options || musicAdapterOptions;
      this._audioOutputId = String(prefs?.audio_output_id || audioOutputId);
      this._animationsEnabled = Boolean(prefs?.animations_enabled ?? animations);
      this._musicAdapters = (this._musicAdapters || []).map((adapter) => ({...adapter, selected:musicAdapters.includes(adapter.id)}));
      this._profile = {...this._profile, tv_dashboard:{...(this._profile.tv_dashboard || {}), ...result, music_adapters:prefs?.music_adapters || musicAdapters, music_adapter_options:prefs?.music_adapter_options || musicAdapterOptions, music_search_limit:Number(prefs?.music_search_limit || musicSearchLimit), audio_output_id:this._audioOutputId, animations_enabled:this._animationsEnabled}};
      if (previousAudioOutput !== this._audioOutputId && Boolean(this._sharedMediaState?.playing) && String(this._sharedMediaState?.media_content_id || "")) {
        void this._sendMediaCommand("play", {
          ...this._sharedMediaState,
          media_content_id:String(this._sharedMediaState.media_content_id),
          title:String(this._sharedMediaState.title || ""),
          playlist_context:this._playlistContextSnapshot(),
          fresh_resolve:true,
        });
      }
      this._tvScalePercent = Number(result?.tv_scale_percent ?? scale);
      this._oledProtection = Boolean(result?.oled_protection ?? oled);
      this._applyTvDisplayPreferences();
      if (status) status.textContent = l.saved;
      if (!enabled) {
        setTimeout(() => this._navigateTv("/fitness-tv/main"), 500);
      } else {
        setTimeout(() => this.shadowRoot?.getElementById("modal-root")?.replaceChildren(), 450);
      }
    } catch (_err) {
      if (status) status.textContent = l.save_failed;
      if (button) button.disabled = false;
    }
  }

  _remoteGatewayId() {
    let gatewayId = "";
    try { gatewayId = String(localStorage.getItem(FITNESS_REMOTE_GATEWAY_STORAGE) || ""); } catch (_err) {}
    if (!gatewayId) {
      gatewayId = globalThis.crypto?.randomUUID?.() || `browser-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      try { localStorage.setItem(FITNESS_REMOTE_GATEWAY_STORAGE, gatewayId); } catch (_err) {}
    }
    return gatewayId;
  }

  _remoteProfileStorageKey(kind) {
    return `${FITNESS_REMOTE_PROFILE_STORAGE_PREFIX}${String(this._profile?.entry_id || "")}.${kind}`;
  }

  _remoteStoredBleIds() {
    try {
      const parsed = JSON.parse(localStorage.getItem(this._remoteProfileStorageKey("ble")) || "[]");
      return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
    } catch (_err) { return []; }
  }

  _saveRemoteBleIds(ids) {
    try { localStorage.setItem(this._remoteProfileStorageKey("ble"), JSON.stringify([...new Set(ids.map(String).filter(Boolean))])); } catch (_err) {}
  }

  async _remoteGatewayHello(transports = []) {
    if (!this._hass || !this._profile) throw new Error("Fitness profile is not ready");
    return this._hass.callWS({
      type:"fitness/remote_gateway/hello",
      profile_entry_id:this._profile.entry_id,
      gateway_id:this._remoteGatewayId(),
      client_name:navigator.userAgentData?.platform || navigator.platform || "browser",
      platform:"browser",
      transports,
    });
  }

  _remoteBleSupport() {
    return Boolean(globalThis.isSecureContext && navigator.bluetooth?.requestDevice);
  }

  async _openRemoteGateway() {
    if (!this._canControlProfile) return;
    const l = this._labels();
    const bleSupported = this._remoteBleSupport();
    const antSupported = Boolean(globalThis.isSecureContext && navigator.usb?.requestDevice);
    this._showModal(`
      <div class="modal-card remote-gateway-modal">
        <div class="modal-head"><strong class="modal-title-with-icon"><ha-icon icon="mdi:access-point"></ha-icon>${_fitnessEscape(l.remote_gateway_title)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        <div class="remote-gateway-body">
          <div class="remote-gateway-intro"><ha-icon icon="mdi:shield-lock-outline"></ha-icon><div><strong>${_fitnessEscape(l.remote_gateway_browser)}</strong><small>${_fitnessEscape(l.remote_gateway_hint)}</small></div></div>
          <section class="remote-radio-card">
            <div class="remote-radio-head"><ha-icon icon="mdi:bluetooth"></ha-icon><div><strong>${_fitnessEscape(l.remote_ble)}</strong><small>${_fitnessEscape(l.remote_ble_hint)}</small></div><span class="remote-state" id="remote-ble-state"></span></div>
            <div class="remote-actions">
              <button class="tool" id="remote-ble-connect" ${bleSupported ? "" : "disabled"}><ha-icon icon="mdi:bluetooth-connect"></ha-icon><span>${_fitnessEscape(l.remote_ble_connect)}</span></button>
              <button class="tool" id="remote-ble-reconnect" ${bleSupported ? "" : "disabled"}><ha-icon icon="mdi:refresh"></ha-icon><span>${_fitnessEscape(l.remote_ble_reconnect)}</span></button>
            </div>
            ${bleSupported ? "" : `<div class="remote-warning">${_fitnessEscape(l.remote_ble_unavailable)}</div>`}
            <div class="remote-device-list" id="remote-ble-devices"></div>
          </section>
          <section class="remote-radio-card">
            <div class="remote-radio-head"><ha-icon icon="mdi:usb-port"></ha-icon><div><strong>${_fitnessEscape(l.remote_ant)}</strong><small>${_fitnessEscape(l.remote_ant_experimental)}</small></div><span class="remote-state" id="remote-ant-state"></span></div>
            <div class="remote-actions">
              <button class="tool" id="remote-ant-connect" ${antSupported ? "" : "disabled"}><ha-icon icon="mdi:usb"></ha-icon><span>${_fitnessEscape(l.remote_ant_connect)}</span></button>
              <button class="tool" id="remote-ant-disconnect" ${this._remoteAntDevice ? "" : "disabled"}><ha-icon icon="mdi:usb-off"></ha-icon><span>${_fitnessEscape(l.remote_ant_disconnect)}</span></button>
            </div>
            ${antSupported ? "" : `<div class="remote-warning">${_fitnessEscape(l.remote_ant_unavailable)}</div>`}
          </section>
          <div class="remote-protocol"><ha-icon icon="mdi:lan-connect"></ha-icon><span>${_fitnessEscape(_fitnessFormatLabel(l.remote_gateway_protocol, {version:"1"}))}</span></div>
        </div>
      </div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    root?.querySelector("#remote-ble-connect")?.addEventListener("click", () => void this._pairRemoteBleDevice());
    root?.querySelector("#remote-ble-reconnect")?.addEventListener("click", () => void this._reconnectRemoteBleDevices(true));
    root?.querySelector("#remote-ant-connect")?.addEventListener("click", () => void this._connectRemoteAntUsb(true));
    root?.querySelector("#remote-ant-disconnect")?.addEventListener("click", () => void this._disconnectRemoteAntUsb());
    this._renderRemoteGatewayStatus();
  }

  _renderRemoteGatewayStatus(message = "") {
    const root = this.shadowRoot?.getElementById("modal-root");
    const l = this._labels();
    const bleState = root?.querySelector("#remote-ble-state");
    const antState = root?.querySelector("#remote-ant-state");
    const list = root?.querySelector("#remote-ble-devices");
    const connectedBle = [...(this._remoteBleDevices?.values?.() || [])].filter((item) => item?.device?.gatt?.connected);
    if (bleState) bleState.textContent = message || (connectedBle.length ? `${connectedBle.length} ${l.remote_connected}` : (l.remote_idle));
    if (antState) antState.textContent = this._remoteAntDevice?.opened ? (l.remote_ant_scanning) : (l.remote_idle);
    if (list) {
      list.innerHTML = connectedBle.map((item) => `<div class="remote-device"><ha-icon icon="mdi:heart-pulse"></ha-icon><span><strong>${_fitnessEscape(item.device.name || item.device.id)}</strong><small>${_fitnessEscape(_fitnessFormatLabel(l.notification_channels, {count:(item.characteristics || []).length}))}</small></span><ha-icon icon="mdi:check-circle" class="ok"></ha-icon><button class="icon-tool remote-ble-disconnect" data-remote-ble-disconnect="${_fitnessEscape(item.device.id)}" title="${_fitnessEscape(l.remote_ble_disconnect)}"><ha-icon icon="mdi:bluetooth-off"></ha-icon></button></div>`).join("") || `<div class="remote-empty">${_fitnessEscape(l.remote_no_sensors)}</div>`;
      list.querySelectorAll("[data-remote-ble-disconnect]").forEach((button) => button.addEventListener("click", () => void this._disconnectRemoteBleDevice(String(button.dataset.remoteBleDisconnect || ""))));
    }
    const antDisconnect = root?.querySelector("#remote-ant-disconnect");
    if (antDisconnect) antDisconnect.disabled = !this._remoteAntDevice?.opened;
  }

  async _pairRemoteBleDevice() {
    const l = this._labels();
    if (!this._remoteBleSupport()) return;
    try {
      this._renderRemoteGatewayStatus(l.remote_pairing);
      const device = await navigator.bluetooth.requestDevice({
        // Only advertise standard fitness sensors that Fitness can decode
        // natively. The filters are ORed by Web Bluetooth, so HR, cycling
        // power/CSC, RSC and FTMS devices remain independently selectable.
        filters:[...FITNESS_REMOTE_BLE_SERVICES].map((service) => ({services:[service]})),
        optionalServices:[...FITNESS_REMOTE_BLE_OPTIONAL_SERVICES],
      });
      await this._connectRemoteBleDevice(device);
      const ids = this._remoteStoredBleIds();
      if (!ids.includes(device.id)) ids.push(device.id);
      this._saveRemoteBleIds(ids);
    } catch (err) {
      if (String(err?.name || "") !== "NotFoundError") {
        console.error("[Fitness TV] Bluetooth sensor connection failed", err);
        this._renderRemoteGatewayStatus(l.remote_failed);
      }
    }
  }

  async _disconnectRemoteBleDevice(deviceId, forget = true) {
    const id = String(deviceId || "");
    const record = this._remoteBleDevices?.get?.(id);
    if (!id || !record) return;
    for (const item of record.listeners || []) {
      try { item.characteristic?.removeEventListener?.("characteristicvaluechanged", item.listener); } catch (_err) {}
      try { await item.characteristic?.stopNotifications?.(); } catch (_err) {}
    }
    try { if (record.disconnectListener) record.device?.removeEventListener?.("gattserverdisconnected", record.disconnectListener); } catch (_err) {}
    try { if (record.device?.gatt?.connected) record.device.gatt.disconnect(); } catch (_err) {}
    this._remoteBleDevices.delete(id);
    for (const key of [...(this._remoteBleQueues?.keys?.() || [])]) {
      if (key.endsWith(`:${id}`)) this._remoteBleQueues.delete(key);
    }
    if (forget) this._saveRemoteBleIds(this._remoteStoredBleIds().filter((item) => item !== id));
    try {
      await this._hass?.callWS({
        type:"fitness/remote_gateway/ble_disconnect",
        profile_entry_id:record.profileEntryId || this._profile?.entry_id,
        gateway_id:this._remoteGatewayId(),
        device_id:id,
      });
    } catch (_err) {}
    this._renderRemoteGatewayStatus();
  }

  async _reconnectRemoteBleDevices(showStatus = false) {
    if (!this.isConnected || !this._profile || !navigator.bluetooth?.getDevices || !globalThis.isSecureContext) return;
    if (this._remoteBleReconnectBusy) return;
    this._remoteBleReconnectBusy = true;
    try {
      const wanted = new Set(this._remoteStoredBleIds());
      if (!wanted.size) return;
      if (showStatus) this._renderRemoteGatewayStatus(this._labels().remote_reconnecting);
      const devices = await navigator.bluetooth.getDevices();
      for (const device of devices.filter((item) => wanted.has(String(item.id)))) {
        try { await this._connectRemoteBleDevice(device); } catch (_err) {}
      }
    } catch (_err) {
    } finally {
      this._remoteBleReconnectBusy = false;
      this._renderRemoteGatewayStatus();
    }
  }

  async _connectRemoteBleDevice(device) {
    if (!device?.gatt || !this._profile) throw new Error("Bluetooth device is unavailable");
    this._remoteBleDevices = this._remoteBleDevices || new Map();
    const old = this._remoteBleDevices.get(device.id);
    if (old?.device?.gatt?.connected && old.profileEntryId === this._profile.entry_id) return old;
    const server = device.gatt.connected ? device.gatt : await device.gatt.connect();
    const serviceUuids = [];
    const characteristics = [];
    const listeners = [];
    const initialFrames = [];
    let liveCharacteristicCount = 0;
    for (const serviceUuid of FITNESS_REMOTE_BLE_CONNECT_SERVICES) {
      let service;
      try { service = await server.getPrimaryService(serviceUuid); } catch (_err) { continue; }
      serviceUuids.push(service.uuid || serviceUuid);
      for (const charUuid of FITNESS_REMOTE_BLE_CHARACTERISTICS) {
        let characteristic;
        try { characteristic = await service.getCharacteristic(charUuid); } catch (_err) { continue; }
        const normalizedUuid = String(characteristic.uuid || charUuid).toLowerCase();
        const isBattery = normalizedUuid === FITNESS_REMOTE_BLE_BATTERY_CHARACTERISTIC;
        let usable = false;
        if (isBattery && characteristic?.properties?.read) {
          try {
            const view = await characteristic.readValue();
            initialFrames.push({
              characteristicUuid:normalizedUuid,
              payload:Array.from(new Uint8Array(view.buffer, view.byteOffset, view.byteLength)),
            });
            usable = true;
          } catch (_err) {}
        }
        if (characteristic?.properties?.notify || characteristic?.properties?.indicate) {
          await characteristic.startNotifications();
          const listener = (event) => {
            const view = event.target?.value;
            if (!view) return;
            const payload = Array.from(new Uint8Array(view.buffer, view.byteOffset, view.byteLength));
            this._queueRemoteBleFrame(device.id, normalizedUuid, payload);
          };
          characteristic.addEventListener("characteristicvaluechanged", listener);
          listeners.push({characteristic, listener});
          usable = true;
        }
        if (!usable) continue;
        if (!characteristics.includes(normalizedUuid)) characteristics.push(normalizedUuid);
        if (!isBattery) liveCharacteristicCount += 1;
      }
    }
    if (!liveCharacteristicCount) {
      try { device.gatt.disconnect(); } catch (_err) {}
      throw new Error(this._labels().remote_ble_unsupported);
    }
    const identity = {};
    try {
      const infoService = await server.getPrimaryService(FITNESS_REMOTE_BLE_DEVICE_INFO_SERVICE);
      for (const [charUuid, key] of Object.entries(FITNESS_REMOTE_BLE_IDENTITY_CHARACTERISTICS)) {
        try {
          const characteristic = await infoService.getCharacteristic(charUuid);
          const value = await characteristic.readValue();
          const text = new TextDecoder("utf-8").decode(new Uint8Array(value.buffer, value.byteOffset, value.byteLength)).replace(/\0/g, "").trim();
          if (text) identity[key] = text;
        } catch (_err) {}
      }
    } catch (_err) {}
    await this._remoteGatewayHello(["bluetooth"]);
    await this._hass.callWS({
      type:"fitness/remote_gateway/ble_device",
      profile_entry_id:this._profile.entry_id,
      gateway_id:this._remoteGatewayId(),
      device_id:device.id,
      name:device.name || this._labels().remote_ble_sensor,
      service_uuids:serviceUuids,
      characteristic_uuids:characteristics,
      identity,
    });
    for (const frame of initialFrames) {
      this._queueRemoteBleFrame(device.id, frame.characteristicUuid, frame.payload);
    }
    const record = {device, listeners, characteristics, profileEntryId:this._profile.entry_id};
    this._remoteBleDevices.set(device.id, record);
    if (!record.disconnectListener) {
      record.disconnectListener = () => this._renderRemoteGatewayStatus();
      device.addEventListener?.("gattserverdisconnected", record.disconnectListener);
    }
    this._renderRemoteGatewayStatus();
    return record;
  }

  _queueRemoteBleFrame(deviceId, characteristicUuid, payload) {
    if (!this._profile || !this._hass) return;
    this._remoteBleQueues = this._remoteBleQueues || new Map();
    const key = `${this._profile.entry_id}:${deviceId}`;
    const queue = this._remoteBleQueues.get(key) || [];
    queue.push({characteristic_uuid:characteristicUuid,payload});
    if (queue.length > 64) queue.splice(0, queue.length - 64);
    this._remoteBleQueues.set(key, queue);
    if (queue.length >= 16) void this._flushRemoteBleFrames(key, deviceId);
    else if (!this._remoteBleFlushTimer) this._remoteBleFlushTimer = setTimeout(() => {
      this._remoteBleFlushTimer = null;
      for (const [queuedKey] of this._remoteBleQueues || []) {
        const split = queuedKey.indexOf(":");
        void this._flushRemoteBleFrames(queuedKey, queuedKey.slice(split + 1));
      }
    }, 80);
  }

  async _flushRemoteBleFrames(key, deviceId) {
    const queue = this._remoteBleQueues?.get(key);
    if (!queue?.length || !this._profile || !this._hass) return;
    const frames = queue.splice(0, 64);
    if (!queue.length) this._remoteBleQueues.delete(key);
    try {
      await this._hass.callWS({
        type:"fitness/remote_gateway/ble_frames",
        profile_entry_id:this._profile.entry_id,
        gateway_id:this._remoteGatewayId(),
        device_id:deviceId,
        frames,
      });
    } catch (_err) {}
  }

  _antSerialFrame(messageId, payload = []) {
    const frame = [0xA4, payload.length & 0xFF, messageId & 0xFF, ...payload.map((value) => value & 0xFF)];
    let checksum = 0;
    for (const value of frame) checksum ^= value;
    frame.push(checksum & 0xFF);
    return new Uint8Array(frame);
  }

  async _antTransferOut(messageId, payload = []) {
    const record = this._remoteAntDevice;
    if (!record?.device?.opened || record.outEndpoint == null) throw new Error("ANT+ USB is not connected");
    await record.device.transferOut(record.outEndpoint, this._antSerialFrame(messageId, payload));
  }

  async _configureRemoteAntUsb() {
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    await this._antTransferOut(0x4A, [0x00]);
    await sleep(650);
    await this._antTransferOut(0x46, [0x00, ...FITNESS_ANT_PLUS_NETWORK_KEY]);
    await sleep(90);
    await this._antTransferOut(0x42, [0x00, 0x00, 0x00]);
    await sleep(90);
    await this._antTransferOut(0x51, [0x00, 0x00, 0x00, 0x00, 0x00]);
    await sleep(90);
    await this._antTransferOut(0x45, [0x00, 57]);
    await sleep(90);
    await this._antTransferOut(0x66, [0x00, 0x01]);
    await sleep(90);
    await this._antTransferOut(0x5B, [0x00]);
  }

  async _connectRemoteAntUsb(requestPermission = true) {
    if (!globalThis.isSecureContext || !navigator.usb) return;
    if (this._remoteAntConnectBusy) return;
    this._remoteAntConnectBusy = true;
    const l = this._labels();
    try {
      let device = null;
      if (requestPermission) {
        device = await navigator.usb.requestDevice({filters:FITNESS_ANT_USB_FILTERS});
      } else {
        const allowed = await navigator.usb.getDevices();
        device = allowed.find((item) => item.vendorId === 0x0fcf && FITNESS_ANT_USB_PRODUCT_IDS.has(item.productId));
        if (!device) return;
      }
      this._renderRemoteGatewayStatus(l.remote_ant_connecting);
      if (!device.opened) await device.open();
      if (!device.configuration) await device.selectConfiguration(1);
      let selected = null;
      for (const iface of device.configuration?.interfaces || []) {
        for (const alternate of iface.alternates || []) {
          const input = (alternate.endpoints || []).find((ep) => ep.direction === "in");
          const output = (alternate.endpoints || []).find((ep) => ep.direction === "out");
          if (input && output) { selected = {iface, alternate, input, output}; break; }
        }
        if (selected) break;
      }
      if (!selected) throw new Error("No ANT+ USB endpoints were found");
      await device.claimInterface(selected.iface.interfaceNumber);
      if (selected.alternate.alternateSetting != null) {
        try { await device.selectAlternateInterface(selected.iface.interfaceNumber, selected.alternate.alternateSetting); } catch (_err) {}
      }
      this._remoteAntDevice = {
        device,
        interfaceNumber:selected.iface.interfaceNumber,
        inEndpoint:selected.input.endpointNumber,
        outEndpoint:selected.output.endpointNumber,
        readBuffer:[],
        profileEntryId:this._profile?.entry_id || "",
      };
      try { localStorage.setItem(this._remoteProfileStorageKey("antplus"), "1"); } catch (_err) {}
      await this._remoteGatewayHello(["antplus"]);
      await this._hass.callWS({
        type:"fitness/remote_gateway/status",
        profile_entry_id:this._profile?.entry_id,
        gateway_id:this._remoteGatewayId(),
        antplus_connected:true,
        antplus_product_id:Number(device.productId || 0).toString(16).padStart(4,"0").toUpperCase(),
      });
      await this._configureRemoteAntUsb();
      this._renderRemoteGatewayStatus();
      void this._remoteAntReadLoop(this._remoteAntDevice);
    } catch (err) {
      if (String(err?.name || "") !== "NotFoundError") {
        console.error("[Fitness TV] ANT+ sensor connection failed", err);
        this._renderRemoteGatewayStatus(l.remote_failed);
      }
      if (this._remoteAntDevice) await this._disconnectRemoteAntUsb(false);
    } finally {
      this._remoteAntConnectBusy = false;
    }
  }

  async _reconnectRemoteAntUsb() {
    let enabled = false;
    try { enabled = localStorage.getItem(this._remoteProfileStorageKey("antplus")) === "1"; } catch (_err) {}
    if (!enabled || this._remoteAntDevice?.device?.opened || !navigator.usb?.getDevices || !globalThis.isSecureContext) return;
    await this._connectRemoteAntUsb(false);
  }

  async _disconnectRemoteAntUsb(clearPreference = true) {
    const record = this._remoteAntDevice;
    this._remoteAntDevice = null;
    if (clearPreference) {
      try { localStorage.removeItem(this._remoteProfileStorageKey("antplus")); } catch (_err) {}
    }
    try {
      await this._hass?.callWS({type:"fitness/remote_gateway/status",profile_entry_id:this._profile?.entry_id,gateway_id:this._remoteGatewayId(),antplus_connected:false});
    } catch (_err) {}
    if (record?.device?.opened) {
      try { await record.device.releaseInterface(record.interfaceNumber); } catch (_err) {}
      try { await record.device.close(); } catch (_err) {}
    }
    this._renderRemoteGatewayStatus();
  }

  async _remoteAntReadLoop(record) {
    while (this._remoteAntDevice === record && record?.device?.opened) {
      try {
        const result = await record.device.transferIn(record.inEndpoint, 64);
        if (!result?.data?.byteLength) continue;
        const chunk = Array.from(new Uint8Array(result.data.buffer, result.data.byteOffset, result.data.byteLength));
        record.readBuffer.push(...chunk);
        const packets = [];
        while (record.readBuffer.length >= 4) {
          const sync = record.readBuffer.indexOf(0xA4);
          if (sync < 0) { record.readBuffer.length = 0; break; }
          if (sync) record.readBuffer.splice(0, sync);
          if (record.readBuffer.length < 4) break;
          const payloadLength = record.readBuffer[1];
          const frameLength = payloadLength + 4;
          if (frameLength > 260) { record.readBuffer.shift(); continue; }
          if (record.readBuffer.length < frameLength) break;
          const frame = record.readBuffer.splice(0, frameLength);
          let checksum = 0;
          for (const value of frame) checksum ^= value;
          if (checksum !== 0) continue;
          const messageId = frame[2];
          if (![0x4E,0x4F,0x50].includes(messageId)) continue;
          const payload = frame.slice(3, -1);
          if (payload.length < 14 || !(payload[9] & 0x80)) continue;
          const deviceId = payload[10] | (payload[11] << 8);
          const deviceType = payload[12] & 0x7F;
          const transmissionType = payload[13] & 0xFF;
          if (!deviceId || !deviceType) continue;
          packets.push({device_id:deviceId,device_type:deviceType,transmission_type:transmissionType,payload:payload.slice(1,9),adapter_id:`webusb:${this._remoteGatewayId()}`});
        }
        if (packets.length && this._profile && this._hass) {
          await this._hass.callWS({
            type:"fitness/remote_gateway/ant_packets",
            profile_entry_id:this._profile.entry_id,
            gateway_id:this._remoteGatewayId(),
            packets,
          });
        }
      } catch (_err) {
        if (this._remoteAntDevice === record) await this._disconnectRemoteAntUsb(false);
        break;
      }
    }
  }

  _suspendRemoteGatewaysForNavigation() {
    for (const record of this._remoteBleDevices?.values?.() || []) {
      for (const item of record.listeners || []) {
        try { item.characteristic?.removeEventListener?.("characteristicvaluechanged", item.listener); } catch (_err) {}
      }
      try { if (record.device?.gatt?.connected) record.device.gatt.disconnect(); } catch (_err) {}
    }
    this._remoteBleDevices?.clear?.();
    if (this._remoteBleFlushTimer) clearTimeout(this._remoteBleFlushTimer);
    this._remoteBleFlushTimer = null;
    this._remoteBleQueues?.clear?.();
    if (this._remoteAntDevice) void this._disconnectRemoteAntUsb(false);
  }

  async _resumeRemoteGateways() {
    if (!this.isConnected || !this._profile || FITNESS_TV_CAST_RECEIVER) return;
    await Promise.allSettled([this._reconnectRemoteBleDevices(false), this._reconnectRemoteAntUsb()]);
  }

  async _googleCastSenderApi() {
    return this._loadExternalScript(
      "google-cast-sender",
      "https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1",
      () => globalThis.cast?.framework?.CastContext || null,
      "__onGCastApiAvailable",
    );
  }

  _localCastSessionActive(context = this._localCastContext) {
    try { return Boolean(context?.getCurrentSession?.()); } catch (_err) { return false; }
  }

  _syncLocalCastButtons() {
    const active = Boolean(this._localCastActive || this._localCastServerActive || this._localCastSessionActive());
    const anyCastActive = FITNESS_TV_CAST_RECEIVER || active || this._refreshCastUiState();
    const toolbarStop = this.shadowRoot?.getElementById("stop-cast");
    if (toolbarStop) { toolbarStop.hidden = !FITNESS_TV_CAST_RECEIVER || !anyCastActive; toolbarStop.disabled = !anyCastActive; }
    const modalRoot = this.shadowRoot?.getElementById("modal-root");
    const localToggle = modalRoot?.querySelector?.("#cast-local");
    if (localToggle) {
      localToggle.querySelector("ha-icon")?.setAttribute("icon", active ? "mdi:cast-off" : "mdi:cast-connected");
      const label = localToggle.querySelector("span");
      const l = this._labels();
      if (label) label.textContent = active ? (l.local_cast_stop) : (l.local_cast_choose);
    }
    const modalStop = modalRoot?.querySelector?.("#cast-local-stop");
    if (modalStop) { modalStop.hidden = true; modalStop.disabled = !active; }
  }

  async _armLocalCastHandoff(reason = "local_cast_started") {
    if (!this._profile || !this._hass || FITNESS_TV_CAST_RECEIVER) return false;
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/local_cast_handoff",
        profile_entry_id:this._profile.entry_id,
        source_client_id:FITNESS_TV_CLIENT_ID,
        reason,
      });
      return Boolean(result?.armed);
    } catch (_err) {
      return false;
    }
  }

  async _releaseLocalCastHandoff(reason = "local_cast_stopped") {
    if (this._localCastReleaseInFlight || !this._profile || !this._hass || FITNESS_TV_CAST_RECEIVER) return;
    this._localCastReleaseInFlight = true;
    try {
      await this._hass.callWS({
        type:"fitness/tv/local_cast_stopped",
        profile_entry_id:this._profile.entry_id,
        reason,
      });
    } catch (_err) {
      // The Cast session has already ended locally; backend heartbeat/pruning is
      // still able to recover if the HA connection disappears at the same time.
    } finally {
      this._localCastReleaseInFlight = false;
    }
  }

  async _prepareLocalCastContext() {
    await this._googleCastSenderApi();
    const context = cast.framework.CastContext.getInstance();
    context.setOptions({
      receiverApplicationId:FITNESS_TV_CAST_APP_ID,
      // Keep a browser tab bound only to the Cast session it started.
      // ORIGIN_SCOPED makes a second Fitness profile tab auto-join another
      // tab's receiver, which mixes otherwise profile-isolated sessions.
      autoJoinPolicy:globalThis.chrome?.cast?.AutoJoinPolicy?.TAB_AND_ORIGIN_SCOPED
        || globalThis.chrome?.cast?.AutoJoinPolicy?.PAGE_SCOPED
        || "tab_and_origin_scoped",
      resumeSavedSession:true,
    });
    if (!this._boundLocalCastSessionState) {
      this._boundLocalCastSessionState = (event) => {
        const state = String(event?.sessionState || "");
        if (state.includes("STARTED") || state.includes("RESUMED") || state.includes("STARTING") || state.includes("RESUMING")) {
          this._localCastActive = true;
        }
        if (state.includes("ENDED") || state.includes("START_FAILED")) {
          this._localCastActive = false;
          this._localCastServerActive = false;
          void this._releaseLocalCastHandoff("sender_session_ended");
        }
        this._syncLocalCastButtons();
        this._updateMediaControls();
      };
      context.addEventListener(cast.framework.CastContextEventType.SESSION_STATE_CHANGED, this._boundLocalCastSessionState);
    }
    if (context.getCurrentSession?.()) {
      this._localCastActive = true;
      // Ask the backend for truth immediately. If HA itself restarted and lost
      // the in-memory local-Cast handoff, _heartbeat() will re-arm it. During
      // ordinary navigation an already-valid handoff is left completely alone.
      if (this._canControlProfile) setTimeout(() => void this._heartbeat(), 0);
    }
    this._syncLocalCastButtons();
    return context;
  }

  _localCastReceiverError(payload) {
    const code = Number(payload?.error_code ?? payload?.errorCode ?? 0);
    const detail = String(payload?.error_message || payload?.errorMessage || "").trim();
    const labels = {
      1:"Home Assistant Cast could not reach Home Assistant. Check the external HTTPS URL from the TV network.",
      2:"Home Assistant Cast rejected the logged-in browser session credentials. Reload Home Assistant and sign in again, then retry local Cast.",
      3:"The Cast receiver lost its connection to Home Assistant.",
      4:"The Cast receiver did not receive a Home Assistant URL.",
      5:"Home Assistant Cast requires HTTPS.",
      20:"The Cast receiver is connected to a different Home Assistant instance.",
      21:"The Cast receiver is not connected to Home Assistant yet.",
      22:"The Cast receiver connected but could not load the Home Assistant configuration.",
    };
    return detail || labels[code] || `Home Assistant Cast receiver error${code ? ` (${code})` : ""}.`;
  }

  async _castLocalDashboard() {
    const l = this._labels();
    const root = this.shadowRoot?.getElementById("modal-root");
    const status = root?.querySelector("#cast-status");
    const button = root?.querySelector("#cast-local");
    if (!this._profile || !this._hass || FITNESS_TV_CAST_RECEIVER) return;
    const context = this._localCastContext;
    if (!context) {
      if (status) status.textContent = l.local_cast_unsupported;
      return;
    }
    let credentials = null;
    let handoffArmed = false;
    if (button) button.disabled = true;
    try {
      // Keep requestSession directly on the click path so Chrome permits the
      // chooser. Authentication is prepared only after the local receiver starts.
      if (status) status.textContent = l.local_cast_connecting;
      await context.requestSession();
      const session = context.getCurrentSession();
      if (!session) throw new Error(l.local_cast_cancelled);
      if (status) status.textContent = l.local_cast_authenticating;
      credentials = await this._hass.callWS({
        type:"fitness/tv/local_cast_credentials",
        profile_entry_id:this._profile.entry_id,
        browser_origin:String(globalThis.location?.origin || ""),
      });
      const namespace = String(credentials.namespace || FITNESS_TV_CAST_NAMESPACE);

      let listener = null;
      let retryOne = null;
      let retryTwo = null;
      let timeout = null;
      const receiverReady = new Promise((resolve, reject) => {
        let settled = false;
        const finish = (ok, err = null) => {
          if (settled) return;
          settled = true;
          if (timeout) clearTimeout(timeout);
          if (retryOne) clearTimeout(retryOne);
          if (retryTwo) clearTimeout(retryTwo);
          try { if (listener) session.removeMessageListener?.(namespace, listener); } catch (_err) {}
          if (err) reject(err); else resolve(ok);
        };
        timeout = setTimeout(() => finish(false, new Error(l.local_cast_receiver_failed)), 22000);
        listener = (_namespace, message) => {
          let payload = message;
          if (typeof payload === "string") { try { payload = JSON.parse(payload); } catch (_err) { return; } }
          if (payload?.type === "receiver_status" && payload?.connected
              && String(payload?.hassUrl || "").replace(/\/$/, "") === String(credentials.hass_url || "").replace(/\/$/, "")) {
            finish(true);
          } else if (payload?.type === "receiver_error") {
            finish(false, new Error(this._localCastReceiverError(payload)));
          }
        };
        try { session.addMessageListener(namespace, listener); }
        catch (err) { finish(false, err instanceof Error ? err : new Error(String(err || "Unable to listen to the Cast receiver."))); }
      });

      // Mirror the official HA browser Web Sender protocol: send the current
      // browser session refresh token together with its matching OAuth client id
      // and the externally reachable HA URL. A couple of delayed retries make the
      // launch robust on Android/Google TV receivers whose namespace comes up just
      // after requestSession resolves.
      const authMessage = {
        type:"connect",
        refreshToken:credentials.refresh_token,
        clientId:credentials.client_id ?? null,
        hassUrl:credentials.hass_url,
      };
      const sendAuth = () => session.sendMessage(namespace, authMessage).catch(() => undefined);
      await sendAuth();
      retryOne = setTimeout(() => void sendAuth(), 1400);
      retryTwo = setTimeout(() => void sendAuth(), 4200);
      await receiverReady;
      if (retryOne) { clearTimeout(retryOne); retryOne = null; }
      if (retryTwo) { clearTimeout(retryTwo); retryTwo = null; }

      // The receiver is authenticated now. Hand all Fitness TV audio/TTS routing
      // to the fresh Cast browser before loading the view, exactly as server-side
      // Fitness Cast does. The laptop stays a controller and is silenced.
      handoffArmed = await this._armLocalCastHandoff("local_cast_receiver_authenticated");
      if (!handoffArmed) throw new Error(l.cast_failed);

      if (status) status.textContent = l.local_cast_loading;
      await session.sendMessage(namespace, {
        type:"show_lovelace_view",
        hassUrl:credentials.hass_url,
        viewPath:credentials.view_path,
        urlPath:credentials.dashboard_path,
      });
      this._localCastActive = true;
      this._localCastServerActive = true;
      this._localCastDeviceName = String(session.getCastDevice?.()?.friendlyName || "Google Cast");
      this._syncLocalCastButtons();
      if (status) status.textContent = `${l.local_cast_connected}: ${this._localCastDeviceName}`;
      void this._autoplaySelectionAfterLocalCast();
    } catch (err) {
      this._localCastActive = false;
      this._localCastServerActive = false;
      if (handoffArmed) await this._releaseLocalCastHandoff("local_cast_start_failed");
      if (credentials) { try { await context.endCurrentSession(true); } catch (_err) {} }
      const message = String(err?.message || err || "");
      console.error("[Fitness TV] local Cast start failed", err);
      if (status) status.textContent = message.includes("external_https_required")
        ? (l.local_cast_no_https)
        : (l.cast_failed);
    } finally {
      if (button) button.disabled = false;
    }
  }

  async _autoplaySelectionAfterLocalCast() {
    if (FITNESS_TV_CAST_RECEIVER || !this._profile || !this._hass) return false;
    const snapshot = this._sharedMediaState?.media_content_id ? this._sharedMediaState : (this._lastMediaSnapshot || {});
    const mediaContentId = String(this._currentMediaContentId || snapshot.media_content_id || "").trim();
    if (!mediaContentId) return false;
    // If playback was already active before the handoff, the fresh Cast
    // receiver resumes it from the shared playing state on its first heartbeat.
    // Sending another fresh-resolve Play here would tear that source down and
    // produce a visible/audible play -> gap -> play cycle.
    if (Boolean(snapshot.playing)) return true;
    const metadata = this._normalizedMediaMetadata(snapshot || this._musicMetadata || {});
    const payload = {
      media_content_id:mediaContentId,
      title:String(this._musicTitle || snapshot.title || mediaContentId),
      playlist_context:this._playlistContextSnapshot() || snapshot.playlist_context || {},
      position:this._mediaSeconds(snapshot.position),
      fresh_resolve:true,
      ...metadata,
    };
    for (const delay of [350, 900, 1600]) {
      await new Promise((resolve) => setTimeout(resolve, delay));
      const result = await this._sendMediaCommand("play", payload);
      if (result?.sent) return true;
    }
    return false;
  }

  async _stopLocalCast() {
    const l = this._labels();
    const status = this.shadowRoot?.getElementById("modal-root")?.querySelector?.("#cast-status");
    if (status) status.textContent = l.cast_stopping;
    try {
      if (globalThis.cast?.framework?.CastContext) await cast.framework.CastContext.getInstance().endCurrentSession(true);
    } catch (_err) {}
    await this._releaseLocalCastHandoff("local_cast_stopped_by_sender");
    this._localCastActive = false;
    this._localCastServerActive = false;
    this._syncLocalCastButtons();
    this._updateMediaControls();
    if (status) status.textContent = l.cast_stopped;
  }

  async _openCastPicker() {
    const l = this._labels();
    try {
      const data = await this._hass?.callWS({type:"fitness/dashboard/config"});
      if (Array.isArray(data?.cast_targets)) this._castTargets = data.cast_targets;
    } catch (_err) {}
    const targets = Array.isArray(this._castTargets) ? this._castTargets : [];
    const preferred = String(this._profile?.tv_dashboard?.cast_media_player_id || "");
    const ordered = [...targets].sort((a, b) => {
      if (a.entity_id === preferred && b.entity_id !== preferred) return -1;
      if (b.entity_id === preferred && a.entity_id !== preferred) return 1;
      return String(a.name || a.entity_id).localeCompare(String(b.name || b.entity_id));
    });
    const availableTargets = ordered.filter((target) => target?.available !== false);
    const selectedTarget = availableTargets.find((target) => target.entity_id === preferred) || availableTargets[0] || null;
    const options = ordered.map((target) => {
      const suffix = [target.entity_id === preferred ? (l.cast_default) : "", target.available === false ? (l.cast_unavailable) : ""].filter(Boolean).join(", ");
      const label = `${target.name || target.entity_id}${suffix ? ` (${suffix})` : ""}`;
      return `<option value="${_fitnessEscape(target.entity_id)}" ${target.entity_id === selectedTarget?.entity_id ? "selected" : ""} ${target.available === false ? "disabled" : ""}>${_fitnessEscape(label)}</option>`;
    }).join("");
    const localCastVisible = !FITNESS_TV_CAST_RECEIVER;
    const haCastActive = this._refreshCastUiState();
    this._showModal(`
      <div class="modal-card cast-modal">
        <div class="modal-head"><strong>${_fitnessEscape(l.cast_dashboard_title)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        <div class="cast-picker">
          ${localCastVisible ? `<section class="cast-section local-cast-section"><div class="cast-section-copy"><ha-icon icon="mdi:wifi-marker"></ha-icon><span><strong>${_fitnessEscape(l.local_cast)}</strong><small>${_fitnessEscape(l.local_cast_hint)}</small></span></div><div class="cast-section-actions"><button class="tool cast-now" id="cast-local" disabled><ha-icon icon="${(this._localCastActive || this._localCastServerActive || this._localCastSessionActive()) ? "mdi:cast-off" : "mdi:cast-connected"}"></ha-icon><span>${_fitnessEscape((this._localCastActive || this._localCastServerActive || this._localCastSessionActive()) ? (l.local_cast_stop) : (l.local_cast_choose))}</span></button><button class="tool" id="cast-local-stop" hidden><ha-icon icon="mdi:cast-off"></ha-icon><span>${_fitnessEscape(l.local_cast_stop)}</span></button></div></section>` : ""}
          <section class="cast-section ha-cast-section"><div class="cast-section-copy"><ha-icon icon="mdi:home-assistant"></ha-icon><span><strong>${_fitnessEscape(l.cast_ha_devices)}</strong><small>${_fitnessEscape(l.cast_ha_devices_hint)}</small></span></div>${ordered.length ? `<label class="cast-target-control"><span>${_fitnessEscape(l.cast_to)}</span><select id="cast-target">${options}</select></label><div class="cast-section-actions"><button class="tool cast-now" id="cast-now" ${selectedTarget ? "" : "disabled"}><ha-icon icon="${haCastActive && String(this._activeCastTarget || "") === String(selectedTarget?.entity_id || "") ? "mdi:cast-off" : "mdi:cast-connected"}"></ha-icon><span>${_fitnessEscape(haCastActive && String(this._activeCastTarget || "") === String(selectedTarget?.entity_id || "") ? (l.cast_stop) : (l.cast_now))}</span></button><button class="tool cast-stop" id="cast-stop" hidden><ha-icon icon="mdi:cast-off"></ha-icon><span>${_fitnessEscape(l.cast_stop)}</span></button></div>` : `<div class="browser-empty">${_fitnessEscape(l.cast_no_targets)}</div>`}</section>
          <div class="cast-status" id="cast-status" aria-live="polite"></div>
        </div>
      </div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    root?.querySelector("#cast-local")?.addEventListener("click", () => {
      if (this._localCastActive || this._localCastServerActive || this._localCastSessionActive()) void this._stopLocalCast();
      else void this._castLocalDashboard();
    });
    root?.querySelector("#cast-local-stop")?.addEventListener("click", () => void this._stopLocalCast());
    if (localCastVisible) {
      const localButton = root?.querySelector("#cast-local");
      const status = root?.querySelector("#cast-status");
      void this._prepareLocalCastContext().then((context) => {
        this._localCastContext = context;
        if (localButton) localButton.disabled = false;
        this._syncLocalCastButtons();
      }).catch((err) => {
        console.error("[Fitness TV] local Cast setup failed", err);
        if (status) status.textContent = l.local_cast_unsupported;
      });
    }
    root?.querySelector("#cast-now")?.addEventListener("click", () => {
      const target = String(root.querySelector("#cast-target")?.value || "");
      if (this._serverCastActive && target && target === String(this._activeCastTarget || "")) void this._stopCastDashboard(target);
      else void this._castDashboard(target);
    });
    root?.querySelector("#cast-target")?.addEventListener("change", () => {
      const target = String(root.querySelector("#cast-target")?.value || "");
      const button = root.querySelector("#cast-now");
      const available = availableTargets.some((item) => String(item.entity_id || "") === target);
      const stopping = Boolean(this._serverCastActive && target && target === String(this._activeCastTarget || ""));
      if (button) button.disabled = !available;
      button?.querySelector("ha-icon")?.setAttribute("icon", stopping ? "mdi:cast-off" : "mdi:cast-connected");
      const span = button?.querySelector("span"); if (span) span.textContent = stopping ? (l.cast_stop) : (l.cast_now);
    });
    root?.querySelector("#cast-stop")?.addEventListener("click", () => this._stopCastDashboard(String(this._activeCastTarget || root.querySelector("#cast-target")?.value || "")));
  }

  async _castDashboard(entityId) {
    const l = this._labels();
    const root = this.shadowRoot?.getElementById("modal-root");
    const status = root?.querySelector("#cast-status");
    const button = root?.querySelector("#cast-now");
    const target = (this._castTargets || []).find((item) => String(item?.entity_id || "") === String(entityId || ""));
    if (!entityId || target?.available === false || !this._profile || !this._hass) return;
    if (button) button.disabled = true;
    if (status) status.textContent = "";
    try {
      // A Cast media_player can report off/idle while the physical TV is fully
      // awake and ready. Do not infer TV power/readiness from that entity state.
      if (status) status.textContent = l.cast_connecting;
      await this._hass.callService("fitness", "cast_tv_dashboard", {
        config_entry_id:this._profile.entry_id,
        entity_id:entityId,
      });
      this._activeCastTarget = entityId;
      await this._heartbeat();
      this._updateMediaControls();
      const modalStop = root?.querySelector("#cast-stop");
      if (modalStop) { modalStop.hidden = !this._castActive; modalStop.disabled = !this._castActive; }
      if (status) status.textContent = this._castActive
        ? (l.cast_sent)
        : (l.cast_failed);
    } catch (_err) {
      if (status) status.textContent = l.cast_failed;
    } finally {
      if (button) button.disabled = false;
    }
  }

  async _stopCastDashboard(entityId) {
    const l = this._labels();
    const root = this.shadowRoot?.getElementById("modal-root");
    const status = root?.querySelector("#cast-status");
    const castButton = root?.querySelector("#cast-now");
    const stopButton = root?.querySelector("#cast-stop");
    if (!entityId || !this._profile || !this._hass) return;
    if (castButton) castButton.disabled = true;
    if (stopButton) stopButton.disabled = true;
    try {
      if (status) status.textContent = l.cast_stopping;
      await this._hass.callService("fitness", "stop_tv_dashboard", {
        config_entry_id:this._profile.entry_id,
        entity_id:entityId,
      });
      this._activeCastTarget = "";
      this._serverCastActive = false;
      this._castActive = false;
      this._updateMediaControls();
      if (stopButton) stopButton.hidden = true;
      if (status) status.textContent = l.cast_stopped;
    } catch (_err) {
      if (status) status.textContent = l.cast_stop_failed;
    } finally {
      if (castButton) castButton.disabled = false;
      if (stopButton) stopButton.disabled = !this._refreshCastUiState();
    }
  }

  _openBackendFlow(mode, entryId = "", profileName = "") {
    this._showModal(`<div class="modal-card backend-flow-modal"><div id="backend-flow-host" class="backend-flow-host"></div></div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    const host = root?.querySelector("#backend-flow-host");
    if (!host) return;
    const flow = document.createElement("fitness-backend-flow");
    flow.hass = this._hass;
    flow.addEventListener("fitness-flow-close", () => {
      root.replaceChildren();
      this._loaded = false;
      setTimeout(() => this._load(), 100);
    });
    flow.addEventListener("fitness-flow-complete", () => {
      // Do not redraw the parent while an options flow is returning to its
      // settings menu: replacing the shadow DOM here destroys the modal.
      // Refresh the dashboard only after the user explicitly closes it.
      this._loaded = false;
    });
    host.replaceChildren(flow);
    flow.start({mode, entryId, profileName, uiLabels:this._labels(), language:String(this._profile?.language || this._access?.language || this._hass?.language || "en")});
  }

  _openCardPicker() {
    const l = this._labels();
    const selected = new Set(this._selectedCards || []);
    const rows = FITNESS_TV_CARD_CATALOG.map((item) => `
      <label class="picker-row">
        <input type="checkbox" value="${item.id}" ${selected.has(item.id) ? "checked" : ""}>
        <ha-icon icon="${item.icon}"></ha-icon>
        <span>${_fitnessEscape(l[item.label] || item.id)}</span>
      </label>`).join("");
    this._showModal(`
      <div class="modal-card picker-modal">
        <div class="modal-head"><strong>${_fitnessEscape(l.card_picker)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        <div class="picker-list">${rows}</div>
      </div>`);
    const root = this.shadowRoot.getElementById("modal-root");
    root?.querySelectorAll('input[type="checkbox"]').forEach((input) => input.addEventListener("change", () => {
      const checked = new Set([...root.querySelectorAll('input[type="checkbox"]:checked')].map((node) => node.value));
      const cards = (this._selectedCards || []).filter((id) => checked.has(id));
      for (const item of FITNESS_TV_CARD_CATALOG) {
        if (checked.has(item.id) && !cards.includes(item.id)) cards.push(item.id);
      }
      this._savePreferences(cards);
    }));
  }

  _showModal(content) {
    const root = this.shadowRoot?.getElementById("modal-root");
    if (!root) return;
    const toolbar = this.shadowRoot?.querySelector(".tv-toolbar");
    toolbar?.scrollIntoView?.({block:"nearest"});
    const toolbarRect = toolbar?.getBoundingClientRect?.();
    const top = Math.max(6, Math.round((toolbarRect?.bottom || 64) + 4));
    root.innerHTML = `<div class="modal-backdrop" style="--modal-top:${top}px">${content}</div>`;
    const modalLabels = this._labels();
    const closeButton = root.querySelector(".modal-close");
    closeButton?.setAttribute("title", modalLabels.close);
    closeButton?.setAttribute("aria-label", modalLabels.close);
    root.querySelectorAll(".ytdlp-back,.browser-back").forEach((button) => {
      button.setAttribute("title", modalLabels.back);
      button.setAttribute("aria-label", modalLabels.back);
    });
    const modalCard = root.querySelector(".modal-card");
    const backendFlowModal = Boolean(modalCard?.classList?.contains("backend-flow-modal"));
    const scrollSelector = ":scope > .profile-settings,:scope > .picker-list,:scope > .media-list,:scope > .cast-picker,:scope > .remote-gateway-body,:scope > .provider-catalog-list,:scope > .music-search-form,:scope > .modal-scroll-body,:scope > .playlist-list,:scope > .playlist-edit-list,:scope > .music-source-list,:scope > .access-admin-body,:scope > .add-profile-list,:scope > .modal-auto-scroll-body";
    if (modalCard && !backendFlowModal) {
      if (!modalCard.querySelector(scrollSelector)) {
        const middle = [...modalCard.children].filter((node) => !node.classList.contains("modal-head") && !node.classList.contains("modal-actions") && !node.classList.contains("settings-actions"));
        if (middle.length) {
          const body = document.createElement("div");
          body.className = "modal-auto-scroll-body";
          modalCard.insertBefore(body, middle[0]);
          middle.forEach((node) => body.appendChild(node));
        }
      }
    }
    const scrollBody = backendFlowModal ? null : modalCard?.querySelector(scrollSelector);
    modalCard?.addEventListener("wheel", (ev) => {
      if (backendFlowModal) return;
      if (!scrollBody) { ev.stopPropagation(); return; }
      if (scrollBody.contains(ev.target)) { ev.stopPropagation(); return; }
      if (Math.abs(Number(ev.deltaY || 0)) > 0) {
        scrollBody.scrollTop += Number(ev.deltaY || 0);
        ev.preventDefault();
      }
      ev.stopPropagation();
    }, {passive:false});
    root.querySelector(".modal-backdrop")?.addEventListener("click", (ev) => {
      if (ev.target.classList.contains("modal-backdrop")) root.replaceChildren();
    });
    root.querySelector(".modal-close")?.addEventListener("click", () => root.replaceChildren());
  }

  async _openMediaBrowser() {
    this._mediaHistory = [];
    this._mediaSearch = "";
    this._browseFavoritesMode = false;
    this._browseNativeProvider = "";
    this._radioCountryCode = this._radioCountryCode || "";
    this._renderMusicSources();
  }

  _renderMusicSources() {
    const l = this._labels();
    this._showModal(`
      <div class="modal-card browser-modal">
        <div class="modal-head"><strong>${_fitnessEscape(l.music_sources)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        <div class="music-source-list">
          <button class="music-source" data-source="favorites"><ha-icon icon="mdi:star"></ha-icon><span><strong>${_fitnessEscape(l.media_favorites)}</strong><small>${_fitnessEscape(l.music_favorites_hint)}</small></span></button>
          <button class="music-source" data-source="playlists"><ha-icon icon="mdi:playlist-music"></ha-icon><span><strong>${_fitnessEscape(l.music_playlists)}</strong><small>${_fitnessEscape(l.music_playlists_hint)} ${this._userPlaylists?.length ? `(${this._userPlaylists.length})` : ""}</small></span></button>
          <button class="music-source" data-source="search"><ha-icon icon="mdi:magnify"></ha-icon><span><strong>${_fitnessEscape(l.music_search)}</strong><small>${_fitnessEscape(l.music_search_hint)}</small></span></button>
          <button class="music-source" data-source="radio"><ha-icon icon="mdi:radio-tower"></ha-icon><span><strong>${_fitnessEscape(l.music_internet_radio)}</strong><small>${_fitnessEscape(l.music_internet_radio_hint)}</small></span></button>
          <button class="music-source" data-source="ha"><ha-icon icon="mdi:home-assistant"></ha-icon><span><strong>${_fitnessEscape(l.music_ha_sources)}</strong><small>${_fitnessEscape(l.music_ha_sources_hint)}</small></span></button>
          <button class="music-source" data-source="link"><ha-icon icon="mdi:link-variant-plus"></ha-icon><span><strong>${_fitnessEscape(l.music_add_link)}</strong><small>${_fitnessEscape(l.music_add_link_hint_v2)}</small></span></button>
        </div>
      </div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    root?.querySelector('[data-source="favorites"]')?.addEventListener("click", () => this._openMediaFavorites(true));
    root?.querySelector('[data-source="playlists"]')?.addEventListener("click", () => this._openUserPlaylists());
    root?.querySelector('[data-source="search"]')?.addEventListener("click", () => this._openMusicSearch());
    root?.querySelector('[data-source="radio"]')?.addEventListener("click", () => this._browseFitnessRadio(""));
    root?.querySelector('[data-source="ha"]')?.addEventListener("click", () => this._browseMedia(""));
    root?.querySelector('[data-source="link"]')?.addEventListener("click", () => this._openMusicLink());
  }

  _openUserPlaylists() {
    const l = this._labels();
    const playlists = this._userPlaylists || [];
    const rows = playlists.map((playlist) => `
      <div class="playlist-row" data-playlist-id="${_fitnessEscape(playlist.id)}">
        <button class="playlist-open">${this._mediaItemVisual({thumbnail:playlist.thumbnail,media_class:"playlist"})}<span><strong>${_fitnessEscape(playlist.name || l.music_playlist)}</strong><small>${playlist.items?.length || 0} ${_fitnessEscape(l.music_items)}</small></span></button>
        <button class="icon-tool playlist-play" title="${_fitnessEscape(l.play)}" ${playlist.items?.length ? "" : "disabled"}><ha-icon icon="mdi:play"></ha-icon></button>
        ${this._canControlProfile ? `<button class="icon-tool playlist-edit" title="${_fitnessEscape(l.edit)}"><ha-icon icon="mdi:pencil"></ha-icon></button>` : ""}
      </div>`).join("");
    this._showModal(`
      <div class="modal-card browser-modal playlist-modal">
        <div class="modal-head"><div class="browser-title"><button class="icon-tool playlists-back"><ha-icon icon="mdi:arrow-left"></ha-icon></button><strong>${_fitnessEscape(l.music_playlists)}</strong></div><div class="browser-head-actions">${this._canControlProfile ? `<button class="tool playlist-new"><ha-icon icon="mdi:playlist-plus"></ha-icon><span>${_fitnessEscape(l.music_new_playlist)}</span></button>` : ""}<button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div></div>
        <div class="playlist-list">${rows || `<div class="browser-empty">${_fitnessEscape(l.music_no_playlists)}</div>`}</div>
      </div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    root?.querySelector(".playlists-back")?.addEventListener("click", () => this._renderMusicSources());
    root?.querySelector(".playlist-new")?.addEventListener("click", () => this._editUserPlaylist(""));
    root?.querySelectorAll(".playlist-row").forEach((row) => {
      const id = String(row.dataset.playlistId || "");
      row.querySelector(".playlist-open")?.addEventListener("click", () => this._openUserPlaylist(id));
      row.querySelector(".playlist-play")?.addEventListener("click", () => this._playUserPlaylist(id));
      row.querySelector(".playlist-edit")?.addEventListener("click", () => this._editUserPlaylist(id));
    });
  }

  _openUserPlaylist(id) {
    const playlist = this._userPlaylist(id);
    if (!playlist) return;
    this._browseNativeProvider = "user_playlist";
    this._browseFavoritesMode = false;
    this._activeBrowsePlaylistId = playlist.id;
    this._browseData = {
      title:playlist.name,
      media_content_id:`fitness-playlist://${playlist.id}`,
      media_class:"playlist",
      thumbnail:playlist.thumbnail || "",
      children:(playlist.items || []).map((item) => ({...item,can_play:item.can_play !== false,can_expand:false})),
    };
    this._mediaSearch = "";
    this._renderMediaBrowser();
  }

  _editUserPlaylist(id = "") {
    const l = this._labels();
    const existing = id ? this._userPlaylist(id) : null;
    const clone = (value) => globalThis.structuredClone ? structuredClone(value) : JSON.parse(JSON.stringify(value));
    const playlist = existing ? clone(existing) : {id:this._newUserPlaylistId(),name:"",items:[],thumbnail:""};
    const rows = () => (playlist.items || []).map((item, index) => `
      <div class="playlist-edit-row" data-index="${index}">${this._mediaItemVisual(item)}<span><strong>${_fitnessEscape(item.title || this._labels().generic_media)}</strong><small>${_fitnessEscape([item.artist,item.album].filter(Boolean).join(" · "))}</small></span><button class="icon-tool playlist-up" ${index === 0 ? "disabled" : ""}><ha-icon icon="mdi:arrow-up"></ha-icon></button><button class="icon-tool playlist-down" ${index === playlist.items.length - 1 ? "disabled" : ""}><ha-icon icon="mdi:arrow-down"></ha-icon></button><button class="icon-tool playlist-remove"><ha-icon icon="mdi:delete-outline"></ha-icon></button></div>`).join("");
    const render = () => {
      this._showModal(`
        <div class="modal-card browser-modal playlist-modal">
          <div class="modal-head"><strong>${_fitnessEscape(existing ? (l.music_edit_playlist) : (l.music_new_playlist))}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
          <label class="field-label">${_fitnessEscape(l.name)}<input id="playlist-name" value="${_fitnessEscape(playlist.name || "")}" maxlength="160"></label>
          <div class="playlist-edit-list">${rows() || `<div class="browser-empty">${_fitnessEscape(l.music_playlist_empty)}</div>`}</div>
          <div class="modal-actions"><button class="primary-tool playlist-save"><ha-icon icon="mdi:content-save"></ha-icon><span>${_fitnessEscape(l.save)}</span></button>${existing ? `<button class="tool playlist-delete"><ha-icon icon="mdi:delete-outline"></ha-icon><span>${_fitnessEscape(l.delete)}</span></button>` : ""}</div>
        </div>`);
      const root = this.shadowRoot?.getElementById("modal-root");
      root?.querySelector("#playlist-name")?.addEventListener("input", (ev) => { playlist.name = String(ev.target?.value || ""); });
      root?.querySelectorAll(".playlist-edit-row").forEach((row) => {
        const index = Number(row.dataset.index);
        row.querySelector(".playlist-remove")?.addEventListener("click", () => { playlist.items.splice(index,1); render(); });
        row.querySelector(".playlist-up")?.addEventListener("click", () => { [playlist.items[index-1],playlist.items[index]]=[playlist.items[index],playlist.items[index-1]]; render(); });
        row.querySelector(".playlist-down")?.addEventListener("click", () => { [playlist.items[index+1],playlist.items[index]]=[playlist.items[index],playlist.items[index+1]]; render(); });
      });
      root?.querySelector(".playlist-save")?.addEventListener("click", async () => {
        playlist.name = String(root.querySelector("#playlist-name")?.value || "").trim() || (l.music_playlist);
        const next = [...(this._userPlaylists || [])];
        const at = next.findIndex((item) => String(item.id) === String(playlist.id));
        if (at >= 0) next[at] = playlist; else next.push(playlist);
        await this._saveUserPlaylists(next);
        this._openUserPlaylists();
      });
      root?.querySelector(".playlist-delete")?.addEventListener("click", async () => {
        await this._saveUserPlaylists((this._userPlaylists || []).filter((item) => String(item.id) !== String(playlist.id)));
        this._openUserPlaylists();
      });
    };
    render();
  }

  async _playUserPlaylist(id) {
    const playlist = this._userPlaylist(id);
    const items = (playlist?.items || []).filter((item) => item?.media_content_id);
    if (!playlist || !items.length) return;
    this._activePlaylistContext = {kind:"user",id:playlist.id,title:playlist.name,items,thumbnail:playlist.thumbnail || ""};
    this._fitnessPlaylistIndex = 0;
    this._fitnessPlaylistShuffle = false;
    this._fitnessPlaylistRepeat = "off";
    const allMA = items.every((item) => String(item.media_content_id || "").startsWith(FITNESS_MUSIC_PREFIXES.music_assistant));
    if (allMA) {
      await this._playSelectedMAItems(items);
      return;
    }
    await this._selectMusic(items[0], {keepPlaylist:true});
  }

  _radioCountryName(code) {
    const region = String(code || "").trim().toUpperCase();
    if (!region) return "";
    try {
      const language = String(this._profile?.language || this._access?.language || this._hass?.language || navigator.language || "en").replace("_", "-");
      const names = new Intl.DisplayNames([language], {type:"region"});
      return names.of(region) || region;
    } catch (_err) {
      return region;
    }
  }

  _sortedRadioCountries() {
    const language = String(this._profile?.language || this._access?.language || this._hass?.language || navigator.language || "en").replace("_", "-");
    let collator = null;
    try { collator = new Intl.Collator([language], {sensitivity:"base", numeric:true}); } catch (_err) {}
    return [...(this._radioCountries || [])]
      .map((country) => ({...country, display_name:this._radioCountryName(country.code) || country.name || country.code}))
      .sort((a, b) => collator ? collator.compare(a.display_name, b.display_name) : String(a.display_name).localeCompare(String(b.display_name)));
  }

  async _browseFitnessRadio(query = "", countryCode = this._radioCountryCode || "") {
    const l = this._labels();
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/music/browse",
        profile_entry_id:this._profile.entry_id,
        provider:"radio",
        query:String(query || "").trim(),
        country_code:String(countryCode || "").trim().toUpperCase(),
      });
      this._browseNativeProvider = "radio";
      this._browseFavoritesMode = false;
      this._radioCountries = Array.isArray(result?.countries) ? result.countries : (this._radioCountries || []);
      this._radioCountryCode = String(result?.country_code || countryCode || "").toUpperCase();
      this._browseData = {
        ...result,
        title:String(query || "").trim() || l.music_internet_radio,
        media_content_id:"__fitness_radio__",
      };
      this._mediaSearch = String(query || "");
      this._renderMediaBrowser();
    } catch (_err) {
      this._showModal(`<div class="modal-card"><div class="modal-head"><strong>${_fitnessEscape(l.music_internet_radio)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="browser-empty">${_fitnessEscape(l.music_radio_error)}</div></div>`);
    }
  }

  async _loadMusicAdapters() {
    const result = await this._hass.callWS({
      type:"fitness/tv/music/adapters",
      profile_entry_id:this._profile.entry_id,
      ma_player_id:String(this._maSendspinPlayerId || ""),
    });
    this._musicAdapters = Array.isArray(result?.adapters) ? result.adapters.filter((adapter) => adapter?.available !== false) : [];
    this._musicProviderCatalog = Array.isArray(result?.provider_catalog) ? result.provider_catalog : [];
    this._musicAdapterOptions = result?.music_adapter_options && typeof result.music_adapter_options === "object" ? result.music_adapter_options : {};
    this._musicSearchLimit = Math.max(10, Math.min(100, Number(result?.music_search_limit || this._musicSearchLimit || 50)));
    this._musicSearchSavedAdapters = Array.isArray(result?.music_search_adapters) ? result.music_search_adapters.map(String) : [];
    this._musicSearchConfigured = Boolean(result?.music_search_configured);
    this._musicSearchSavedScopes = result?.music_search_scopes && typeof result.music_search_scopes === "object" ? result.music_search_scopes : {};
    this._musicSearchSavedTypes = Array.isArray(result?.music_search_types)
      ? result.music_search_types.map((value) => String(value || "").trim()).filter(Boolean)
      : FITNESS_MUSIC_SEARCH_TYPES.map((item) => item.id);
    this._musicSearchTypesConfigured = Boolean(result?.music_search_types_configured);
    this._ytdlpEnabled = Boolean(result?.ytdlp_enabled);
    if (this._musicAdapters.some((adapter) => adapter?.id === "music_assistant")) {
      void this._primeMASendspinRelay().catch(() => {});
    }
    return this._musicAdapters;
  }

  _musicSearchSelection(root) {
    const selected = [...(root?.querySelectorAll?.('input[data-adapter]:checked') || [])]
      .map((input) => String(input.dataset.adapter || "")).filter(Boolean);
    const scopes = {};
    for (const adapterId of selected) {
      const scopeInputs = [...(root?.querySelectorAll?.(`input[data-adapter-scope="${CSS.escape(adapterId)}"]`) || [])];
      if (scopeInputs.length) {
        scopes[adapterId] = scopeInputs
          .filter((input) => input.checked && !input.disabled)
          .map((input) => String(input.value || "")).filter(Boolean);
      }
    }
    const types = [...(root?.querySelectorAll?.('input[data-music-type]:checked') || [])]
      .map((input) => String(input.dataset.musicType || "").trim()).filter(Boolean);
    return {selected, scopes, types};
  }

  async _saveMusicSearchPreferences(root) {
    if (!root || !this._profile?.entry_id) return;
    const {selected, scopes, types} = this._musicSearchSelection(root);
    this._musicSearchConfigured = true;
    this._musicSearchTypesConfigured = true;
    this._musicSearchSavedAdapters = [...selected];
    this._musicSearchSavedScopes = Object.fromEntries(
      Object.entries(scopes).map(([key, value]) => [String(key), [...value]])
    );
    this._musicSearchSavedTypes = [...types];
    const save = async () => this._hass.callWS({
      type:"fitness/tv/preferences/save",
      profile_entry_id:this._profile.entry_id,
      music_search_adapters:selected,
      music_search_scopes:scopes,
      music_search_types:types,
    });
    // Serialize rapid checkbox changes so an older request can never overwrite
    // a newer per-profile selection on the backend.
    const previous = this._musicSearchSavePromise || Promise.resolve();
    this._musicSearchSavePromise = previous.catch(() => {}).then(save);
    try { await this._musicSearchSavePromise; } catch (_err) {}
  }

  async _openMusicSearch() {
    const l = this._labels();
    this._showModal(`
      <div class="modal-card music-search-modal">
        <div class="modal-head"><div class="browser-title"><button class="icon-tool music-sources-back" title="${_fitnessEscape(l.media_browser_back)}"><ha-icon icon="mdi:arrow-left"></ha-icon></button><strong>${_fitnessEscape(l.music_search)}</strong></div><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        <div class="music-search-form">
          <label class="field-label">${_fitnessEscape(l.music_search_query) }<input id="music-search-query" type="search" autocomplete="off" placeholder="${_fitnessEscape(l.music_search_placeholder)}"></label>
          <div class="music-type-filter"><span class="music-type-filter-title">${_fitnessEscape(l.music_search_types)}</span><div class="music-type-options"></div></div>
          <div class="music-search-status music-search-working" hidden><ha-icon icon="mdi:loading" class="spin"></ha-icon><span>${_fitnessEscape(l.music_search_working)}</span></div>
          <div class="music-adapter-picker"><div class="browser-working"><ha-icon icon="mdi:loading" class="spin"></ha-icon><span>${_fitnessEscape(l.music_loading_adapters)}</span></div></div>
          <div class="modal-actions"><button class="primary-tool run-music-search" disabled><ha-icon icon="mdi:magnify"></ha-icon><span>${_fitnessEscape(l.music_search)}</span></button></div>
          <div class="browser-empty music-search-error" hidden></div>
        </div>
      </div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    root?.querySelector(".music-sources-back")?.addEventListener("click", () => this._renderMusicSources());
    try {
      const adapters = await this._loadMusicAdapters();
      if (!root?.isConnected) return;
      const searchable = adapters.filter((adapter) => adapter?.can_search && adapter?.available !== false && adapter?.profile_enabled);
      const savedTypes = this._musicSearchTypesConfigured
        ? (Array.isArray(this._musicSearchSavedTypes) ? this._musicSearchSavedTypes : [])
        : FITNESS_MUSIC_SEARCH_TYPES.map((item) => item.id);
      const typeOptions = root.querySelector(".music-type-options");
      if (typeOptions) typeOptions.innerHTML = FITNESS_MUSIC_SEARCH_TYPES.map((item) => {
        const checked = savedTypes.includes(item.id);
        const label = l[item.label];
        return `<label class="music-type-option"><input type="checkbox" data-music-type="${_fitnessEscape(item.id)}" ${checked ? "checked" : ""}><ha-icon icon="${_fitnessEscape(item.icon)}"></ha-icon><span>${_fitnessEscape(label)}</span></label>`;
      }).join("");
      const rows = searchable.map((adapter) => {
        const savedAdapters = Array.isArray(this._musicSearchSavedAdapters) ? this._musicSearchSavedAdapters : [];
        const selected = this._musicSearchConfigured ? savedAdapters.includes(String(adapter.id)) : Boolean(adapter.selected);
        const hint = _fitnessMusicAdapterHint(l, adapter);
        const icon = String(adapter.icon || "mdi:music-note");
        const iconMarkup = icon.startsWith("/") ? `<img src="${_fitnessEscape(icon)}" alt="">` : `<ha-icon icon="${_fitnessEscape(icon)}"></ha-icon>`;
        const scopes = Array.isArray(adapter.search_scopes) ? adapter.search_scopes : [];
        const availableScopes = scopes.filter((scope) => scope?.available !== false);
        const busyCount = Math.max(0, scopes.length - availableScopes.length);
        const scopeMarkup = availableScopes.length ? `<div class="music-provider-scopes">${availableScopes.map((scope) => {
          const scopeIcon = String(scope.icon || "mdi:music-note");
          const scopeIconMarkup = scopeIcon.startsWith("mdi:") ? `<ha-icon icon="${_fitnessEscape(scopeIcon)}"></ha-icon>` : `<ha-icon icon="mdi:music-note"></ha-icon>`;
          const hasSavedScopes = Object.prototype.hasOwnProperty.call(this._musicSearchSavedScopes || {}, adapter.id);
          const savedScopes = Array.isArray(this._musicSearchSavedScopes?.[adapter.id]) ? this._musicSearchSavedScopes[adapter.id].map(String) : [];
          const scopeSelected = hasSavedScopes ? savedScopes.includes(String(scope.id)) : selected;
          return `<label class="music-provider-scope-row">${scopeIconMarkup}<input type="checkbox" data-adapter-scope="${_fitnessEscape(adapter.id)}" value="${_fitnessEscape(scope.id)}" ${scopeSelected ? "checked" : ""}><span><strong>${_fitnessEscape(scope.name || scope.domain || scope.id)}</strong><small>${_fitnessEscape(scope.domain || "Music Assistant")}</small></span></label>`;
        }).join("")}</div>` : "";
        const busyMarkup = busyCount ? `<div class="music-provider-busy-note"><ha-icon icon="mdi:account-lock-outline"></ha-icon><span>${_fitnessEscape(_fitnessFormatLabel(l.music_provider_busy_hidden, {count:busyCount}))}</span></div>` : "";
        const scopeLocked = scopes.length > 0 && availableScopes.length === 0;
        return `<div class="music-adapter-search-group"><label class="music-adapter-row ${scopeLocked ? "unavailable" : ""}"><input type="checkbox" data-adapter="${_fitnessEscape(adapter.id)}" ${selected && !scopeLocked ? "checked" : ""} ${scopeLocked ? "disabled" : ""}>${iconMarkup}<span><strong>${_fitnessEscape(adapter.name || adapter.id)}</strong>${hint ? `<small>${_fitnessEscape(hint)}</small>` : ""}</span></label>${scopeMarkup}${busyMarkup}</div>`;
      }).join("");
      const picker = root.querySelector(".music-adapter-picker");
      if (picker) picker.innerHTML = `<label class="music-adapter-row all-adapters"><input id="music-search-all" type="checkbox"><ha-icon icon="mdi:select-all"></ha-icon><span><strong>${_fitnessEscape(l.music_all_adapters)}</strong><small>${_fitnessEscape(l.music_all_adapters_hint)}</small></span></label>${rows || `<div class="browser-empty">${_fitnessEscape(l.music_no_search_adapters)}</div>`}`;
      const run = root.querySelector(".run-music-search");
      const enabledAdapters = [...root.querySelectorAll('input[data-adapter]:not(:disabled)')];
      const all = root.querySelector("#music-search-all");
      if (all) all.checked = enabledAdapters.length > 0 && enabledAdapters.every((node) => node.checked);
      if (run) run.disabled = searchable.length === 0;
      all?.addEventListener("change", () => {
        root.querySelectorAll('input[data-adapter]:not(:disabled)').forEach((input) => { input.checked = Boolean(all.checked); });
        root.querySelectorAll('input[data-adapter-scope]:not(:disabled)').forEach((input) => { input.checked = Boolean(all.checked); });
        void this._saveMusicSearchPreferences(root);
      });
      root.querySelectorAll('input[data-adapter]').forEach((input) => input.addEventListener("change", () => {
        const id = String(input.dataset.adapter || "");
        root.querySelectorAll(`input[data-adapter-scope="${CSS.escape(id)}"]`).forEach((scope) => { scope.checked = Boolean(input.checked); });
        const enabled = [...root.querySelectorAll('input[data-adapter]:not(:disabled)')];
        if (all) all.checked = enabled.length > 0 && enabled.every((node) => node.checked);
        void this._saveMusicSearchPreferences(root);
      }));
      root.querySelectorAll('input[data-adapter-scope]').forEach((input) => input.addEventListener("change", () => {
        const id = String(input.dataset.adapterScope || "");
        const parent = root.querySelector(`input[data-adapter="${CSS.escape(id)}"]`);
        const scopes = [...root.querySelectorAll(`input[data-adapter-scope="${CSS.escape(id)}"]`)].filter((node) => !node.disabled);
        if (parent) parent.checked = scopes.some((node) => node.checked);
        const enabled = [...root.querySelectorAll('input[data-adapter]:not(:disabled)')];
        if (all) all.checked = enabled.length > 0 && enabled.every((node) => node.checked);
        void this._saveMusicSearchPreferences(root);
      }));
      root.querySelectorAll('input[data-music-type]').forEach((input) => input.addEventListener("change", () => {
        void this._saveMusicSearchPreferences(root);
      }));
      run?.addEventListener("click", () => this._runMusicSearch(root));
      root.querySelector("#music-search-query")?.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); this._runMusicSearch(root); } });
      root.querySelector("#music-search-query")?.focus?.();
    } catch (err) {
      console.error("[Fitness TV] music adapter load failed", err);
      const picker = root?.querySelector(".music-adapter-picker");
      if (picker) picker.innerHTML = `<div class="browser-empty">${_fitnessEscape(l.music_adapter_error)}</div>`;
    }
  }

  async _runMusicSearch(root) {
    const l = this._labels();
    if (!root) return;
    const query = String(root.querySelector("#music-search-query")?.value || "").trim();
    const error = root.querySelector(".music-search-error");
    const working = root.querySelector(".music-search-working");
    const button = root.querySelector(".run-music-search");
    if (!query) { if (error) { error.textContent = l.music_search_enter_query; error.hidden = false; } return; }
    const all = Boolean(root.querySelector("#music-search-all")?.checked);
    const {selected, scopes, types} = this._musicSearchSelection(root);
    if (!all && !selected.length) { if (error) { error.textContent = l.music_search_select_adapter; error.hidden = false; } return; }
    if (!types.length) { if (error) { error.textContent = l.music_search_select_type; error.hidden = false; } return; }
    if (error) error.hidden = true;
    await this._saveMusicSearchPreferences(root);
    if (working) working.hidden = false;
    if (button) button.disabled = true;
    try {
      const wantsMusicAssistant = all
        ? this._musicAdapters.some((adapter) => adapter?.id === "music_assistant")
        : selected.includes("music_assistant");
      if (wantsMusicAssistant) {
        void Promise.all([this._sendspinModule(), this._primeMASendspinRelay()]).catch(() => {});
      }
      const result = await this._hass.callWS({
        type:"fitness/tv/music/search",
        profile_entry_id:this._profile.entry_id,
        query,
        adapters:all ? ["all"] : selected,
        scopes,
        media_types:types,
        ma_player_id:String(this._maSendspinPlayerId || ""),
      });
      this._musicSearchAdapterIds = all ? ["all"] : selected;
      this._musicSearchMediaTypes = [...types];
      this._browseNativeProvider = "music_search";
      this._browseFavoritesMode = false;
      this._browseData = {
        ...result,
        title:l.music_search_results,
        media_content_id:"__fitness_music_search__",
      };
      this._mediaSearch = "";
      this._musicResultSelection = new Set();
      this._renderMediaBrowser();
    } catch (err) {
      console.error("[Fitness TV] music search failed", err);
      if (working) working.hidden = true;
      if (button) button.disabled = false;
      if (error) { error.textContent = l.music_search_error; error.hidden = false; }
    }
  }

  _musicLinkId(target) {
    const raw = String(target || "").trim();
    const lower = raw.toLowerCase();
    if (!raw) return "";
    if (lower.includes("soundcloud.com/")) return FITNESS_MUSIC_PREFIXES.soundcloud + encodeURIComponent(raw);
    if (lower.includes("youtube.com/") || lower.includes("music.youtube.com/") || lower.includes("youtu.be/")) return FITNESS_MUSIC_PREFIXES.youtube + encodeURIComponent(raw);
    if (lower.startsWith("http://") || lower.startsWith("https://") || raw.startsWith("/")) return FITNESS_MUSIC_PREFIXES.url + encodeURIComponent(raw);
    return "";
  }

  _openMusicLink() {
    const l = this._labels();
    this._showModal(`
      <div class="modal-card music-link-modal">
        <div class="modal-head"><div class="browser-title"><button class="icon-tool music-sources-back" title="${_fitnessEscape(l.media_browser_back)}"><ha-icon icon="mdi:arrow-left"></ha-icon></button><strong>${_fitnessEscape(l.music_add_link)}</strong></div><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        <label class="field-label">${_fitnessEscape(l.music_link)}<input id="music-link" type="text" autocomplete="off" placeholder="https://…"></label>
        <label class="field-label">${_fitnessEscape(l.music_title_optional)}<input id="music-link-title" type="text" autocomplete="off"></label>
        <div class="music-link-support">${_fitnessEscape(l.music_link_supported_v2)}<div class="music-link-examples"><span>https://…/stream.mp3</span><span>youtube.com/…</span><span>soundcloud.com/…</span></div></div>
        <div class="modal-actions"><button class="primary-tool use-music-link"><ha-icon icon="mdi:play-circle-outline"></ha-icon><span>${_fitnessEscape(l.music_use_link)}</span></button></div>
        <div class="browser-empty music-link-error" hidden></div>
      </div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    root?.querySelector(".music-sources-back")?.addEventListener("click", () => this._renderMusicSources());
    root?.querySelector(".use-music-link")?.addEventListener("click", async () => {
      const target = String(root.querySelector("#music-link")?.value || "").trim();
      const lower = target.toLowerCase();
      const error = root.querySelector(".music-link-error");
      const showError = (message) => { if (error) { error.textContent = message; error.hidden = false; } };
      if (lower.startsWith("spotify:") || lower.includes("open.spotify.com/")) {
        showError(l.music_spotify_requires_provider);
        return;
      }
      const id = this._musicLinkId(target);
      if (!id) { showError(l.music_invalid_link); return; }
      if (error) error.hidden = true;
      const title = String(root.querySelector("#music-link-title")?.value || "").trim() || this._musicLinkDefaultTitle(target);
      await this._selectMusic({title,media_content_id:id,can_play:true,can_expand:false});
    });
  }

  _musicLinkDefaultTitle(target) {
    const value = String(target || "");
    const lower = value.toLowerCase();
    if (lower.startsWith("spotify:") || lower.includes("open.spotify.com/")) return "Spotify";
    if (lower.includes("soundcloud.com/")) return "SoundCloud";
    if (lower.includes("youtube.com/") || lower.includes("youtu.be/") || lower.includes("music.youtube.com/")) return "YouTube";
    try { return new URL(value, window.location.origin).hostname || value; } catch (_err) { return value; }
  }

  async _browseMedia(mediaContentId, pushCurrent = false) {
    const l = this._labels();
    try {
      if (pushCurrent && this._browseData) this._mediaHistory.push(this._browseData.media_content_id || "");
      const result = await this._hass.callWS({
        type:"media_source/browse_media",
        media_content_id:mediaContentId || "",
      });
      this._browseFavoritesMode = false;
      this._browseNativeProvider = "";
      this._browseData = result;
      this._renderMediaBrowser();
    } catch (_err) {
      this._showModal(`
        <div class="modal-card"><div class="modal-head"><strong>${_fitnessEscape(l.media_browser)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        <div class="browser-empty">${_fitnessEscape(l.media_error)}</div></div>`);
    }
  }

  _favoriteMediaItems() {
    const l = this._labels();
    return (this._mediaFavorites || []).map((item) => ({
      title:String(item.title || item.media_content_id || l.media_browser),
      ...this._normalizedMediaMetadata(item),
      media_content_id:String(item.media_content_id || ""),
      can_play:true,
      can_expand:false,
    })).filter((item) => item.media_content_id);
  }

  _isMediaFavorite(item) {
    const id = String(item?.media_content_id || "");
    return Boolean(id && (this._mediaFavorites || []).some((fav) => String(fav.media_content_id || "") === id));
  }

  async _toggleMediaFavorite(item, button = null) {
    const id = String(item?.media_content_id || "");
    if (!id) return;
    const l = this._labels();
    const favorites = [...(this._mediaFavorites || [])];
    const index = favorites.findIndex((fav) => String(fav.media_content_id || "") === id);
    const adding = index < 0;
    if (index >= 0) favorites.splice(index, 1);
    else favorites.push({
      media_content_id:id,
      title:String(item.title || id),
      ...this._normalizedMediaMetadata(item),
    });

    // Optimistic UI feedback: the star changes the instant it is pressed.
    // Persistence follows in the background so a slow HA storage write never
    // makes the button feel unresponsive.
    this._mediaFavorites = favorites;
    if (button) {
      button.classList.add("favorite-pulse");
      button.setAttribute("aria-pressed", adding ? "true" : "false");
      button.title = adding ? (l.remove_favorite) : (l.add_favorite);
      const icon = button.querySelector("ha-icon");
      if (icon) icon.setAttribute("icon", adding ? "mdi:star" : "mdi:star-outline");
      setTimeout(() => button.classList.remove("favorite-pulse"), 220);
    }
    await this._saveFavorites(favorites);
    if (this._browseFavoritesMode) {
      this._browseData = {title:l.media_favorites,media_content_id:"__fitness_favorites__",children:this._favoriteMediaItems()};
      this._renderMediaBrowser();
    }
  }

  _openMediaFavorites(fromSources = false) {
    const l = this._labels();
    if (!this._browseFavoritesMode) {
      this._browseBeforeFavorites = fromSources ? null : this._browseData;
      this._browseBeforeFavoritesProvider = fromSources ? "" : this._browseNativeProvider;
    }
    this._browseNativeProvider = "";
    this._browseFavoritesMode = true;
    this._browseData = {
      title:l.media_favorites,
      media_content_id:"__fitness_favorites__",
      children:this._favoriteMediaItems(),
    };
    this._mediaSearch = "";
    this._renderMediaBrowser();
  }

  _filterMediaRows(query) {
    const normalized = String(query || "").trim().toLocaleLowerCase();
    const root = this.shadowRoot?.getElementById("modal-root");
    let visible = 0;
    root?.querySelectorAll(".media-row").forEach((row) => {
      const match = !normalized || String(row.dataset.search || "").includes(normalized);
      row.hidden = !match;
      if (match) visible += 1;
    });
    const empty = root?.querySelector(".media-filter-empty");
    if (empty) empty.hidden = visible > 0;
  }

  _mediaItemIcon(item = {}) {
    const explicit = String(item.icon || "").trim();
    if (explicit.startsWith("mdi:")) return explicit;
    const mediaClass = String(item.media_class || item.children_media_class || "").toLowerCase();
    const icons = {
      album:"mdi:album", artist:"mdi:account-music", track:"mdi:music-note",
      music:"mdi:music", playlist:"mdi:playlist-music", podcast:"mdi:podcast",
      audiobook:"mdi:book-music", directory:"mdi:folder-music-outline",
      app:"mdi:apps", channel:"mdi:radio", video:"mdi:video", image:"mdi:image"
    };
    return icons[mediaClass] || (item.can_expand ? "mdi:folder-music-outline" : "mdi:music-note");
  }

  _mediaItemVisual(item = {}) {
    const thumbnail = String(item.thumbnail || "").trim();
    const explicitIcon = String(item.icon || "").trim();
    const image = thumbnail || (/^(https?:\/\/|\/)/i.test(explicitIcon) ? explicitIcon : "");
    if (image) return `<img class="media-thumb" src="${_fitnessEscape(this._resolvedMediaUrl(image))}" alt="" loading="lazy">`;
    return `<ha-icon class="media-source-icon" icon="${_fitnessEscape(this._mediaItemIcon(item))}"></ha-icon>`;
  }

  _mediaResultMetadata(item = {}) {
    const metadata = this._normalizedMediaMetadata(item);
    const provider = this._mediaProviderLabel(item);
    const labels = this._labels();
    const primary = [...new Set([metadata.artist, metadata.album].map((value) => String(value || "").trim()).filter(Boolean))];
    const secondary = [];
    if (metadata.year) secondary.push(metadata.year);
    if (metadata.duration > 0) secondary.push(this._formatMediaTime(metadata.duration));
    if (provider) secondary.push(provider);
    const mediaType = FITNESS_MUSIC_SEARCH_TYPES.find(
      (candidate) => candidate.id === String(item.media_class || "").toLowerCase(),
    );
    const typeLabel = mediaType ? String(labels?.[mediaType.label] || "").trim() : "";
    if (typeLabel && !secondary.some((value) => value.toLocaleLowerCase() === typeLabel.toLocaleLowerCase())) secondary.push(typeLabel);
    return {primary, secondary};
  }

  _isMAItem(item = {}) {
    return String(item.media_content_id || "").startsWith(FITNESS_MUSIC_PREFIXES.music_assistant);
  }

  _isMAPlaylistItem(item = {}) {
    return this._isMAItem(item) && String(item.media_class || "").toLowerCase() === "playlist";
  }

  _selectedMusicResults(children = []) {
    this._musicResultSelection ||= new Set();
    const selected = this._musicResultSelection;
    return children.filter((item) => item?.can_play && selected.has(String(item.media_content_id || "")));
  }

  _updateMusicSelectionBar(root, children) {
    const l = this._labels();
    const items = this._selectedMusicResults(children);
    const count = root?.querySelector(".music-selection-count");
    const play = root?.querySelector(".music-selection-play");
    const add = root?.querySelector(".music-selection-add");
    const clear = root?.querySelector(".music-selection-clear");
    if (count) count.textContent = _fitnessFormatLabel(l.selected_count, {count:items.length});
    if (play) play.disabled = !items.length || !items.every((item) => this._isMAItem(item));
    if (add) add.disabled = !items.length;
    if (clear) clear.disabled = !items.length;
  }

  async _playSelectedMAItems(items = []) {
    const selected = items.filter((item) => this._isMAItem(item) && item?.media_content_id);
    if (!selected.length) return;
    const player = this._maSendspinPlayer || this._createMASendspinPlayer();
    await player.unlock?.();
    if (!this._maSendspinConnected) await this._connectMASendspinPlayer(player);
    const result = await this._hass.callWS({
      type:"fitness/tv/music/ma/play",
      profile_entry_id:this._profile.entry_id,
      player_id:this._maSendspinPlayerId,
      media_content_ids:selected.map((item) => String(item.media_content_id)),
    });
    if (!result?.playing) throw new Error("Music Assistant did not start the selected queue");
    const first = selected[0];
    this._currentMediaContentId = String(first.media_content_id);
    this._musicTitle = String(first.title || this._labels().music_sources);
    this._musicMetadata = this._normalizedMediaMetadata(first);
    if (!this._activePlaylistContext) {
      this._activePlaylistContext = {kind:"selection",title:this._labels().music_selected_items,items:selected};
    }
    this._activePlaylistContext.index = 0;
    this._fitnessPlaylistIndex = 0;
    this._startMAProgressSync();
    this.shadowRoot?.getElementById("modal-root")?.replaceChildren();
    this._updateMediaControls();
  }

  _openAddToPlaylist(items = []) {
    const l = this._labels();
    const selected = items.map((item) => this._playlistItemSnapshot(item)).filter((item) => item.media_content_id);
    if (!selected.length) return;
    const options = (this._userPlaylists || []).map((playlist) => `<option value="${_fitnessEscape(playlist.id)}">${_fitnessEscape(playlist.name)} (${playlist.items?.length || 0})</option>`).join("");
    this._showModal(`
      <div class="modal-card playlist-add-modal">
        <div class="modal-head"><strong>${_fitnessEscape(l.music_add_to_playlist)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        <div class="playlist-add-summary">${selected.length} ${_fitnessEscape(l.music_selected_items)}</div>
        <label class="field-label">${_fitnessEscape(l.music_playlist)}<select id="playlist-target"><option value="">${_fitnessEscape(l.music_new_playlist)}</option>${options}</select></label>
        <label class="field-label playlist-new-name">${_fitnessEscape(l.name)}<input id="playlist-new-name" maxlength="160" placeholder="${_fitnessEscape(l.music_new_playlist)}"></label>
        <div class="modal-actions"><button class="primary-tool playlist-add-confirm"><ha-icon icon="mdi:playlist-plus"></ha-icon><span>${_fitnessEscape(l.add)}</span></button></div>
      </div>`);
    const root = this.shadowRoot?.getElementById("modal-root");
    const target = root?.querySelector("#playlist-target");
    const nameField = root?.querySelector(".playlist-new-name");
    const sync = () => { if (nameField) nameField.hidden = Boolean(target?.value); };
    target?.addEventListener("change", sync); sync();
    root?.querySelector(".playlist-add-confirm")?.addEventListener("click", async () => {
      let playlist = target?.value ? this._userPlaylist(target.value) : null;
      const next = [...(this._userPlaylists || [])];
      if (!playlist) {
        const name = String(root.querySelector("#playlist-new-name")?.value || "").trim() || (l.music_playlist);
        playlist = {id:this._newUserPlaylistId(),name,items:[],thumbnail:""};
        next.push(playlist);
      } else {
        playlist = globalThis.structuredClone ? structuredClone(playlist) : JSON.parse(JSON.stringify(playlist));
        const at = next.findIndex((item) => String(item.id) === String(playlist.id));
        if (at >= 0) next[at] = playlist;
      }
      playlist.items = [...(playlist.items || []), ...selected].slice(0, 500);
      playlist.thumbnail = String(playlist.thumbnail || selected.find((item) => item.thumbnail)?.thumbnail || "");
      await this._saveUserPlaylists(next);
      this._musicResultSelection = new Set();
      this._renderMediaBrowser();
    });
  }

  async _openMAPlaylist(item) {
    if (!this._isMAPlaylistItem(item)) return;
    const current = {data:this._browseData,provider:this._browseNativeProvider,search:this._mediaSearch};
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/music/ma/playlist",
        profile_entry_id:this._profile.entry_id,
        media_content_id:String(item.media_content_id),
        provider_instance:String(item.provider_instance || ""),
      });
      this._playlistBrowseReturn = current;
      this._providerPlaylistData = {...result, source_item:this._playlistItemSnapshot(item)};
      this._browseNativeProvider = "ma_playlist";
      this._browseData = result;
      this._mediaSearch = "";
      this._renderMediaBrowser();
    } catch (err) {
      console.error("[Fitness TV] open MA playlist failed", err);
    }
  }

  async _removeMAPlaylistPosition(position) {
    const data = this._providerPlaylistData || {};
    if (!data.is_editable || !data.library_id) return;
    const previousReturn = this._playlistBrowseReturn;
    await this._hass.callWS({
      type:"fitness/tv/music/ma/playlist/remove",
      profile_entry_id:this._profile.entry_id,
      library_id:String(data.library_id),
      positions:[Number(position)],
    });
    await this._openMAPlaylist(data.source_item || {media_content_id:data.media_content_id,media_class:"playlist",provider_instance:data.provider_instance});
    this._playlistBrowseReturn = previousReturn;
  }

  _renderMediaBrowser() {
    const l = this._labels();
    const data = this._browseData || {};
    const children = Array.isArray(data.children) ? data.children : [];
    const selectable = this._browseNativeProvider === "music_search" && this._canControlProfile;
    const providerPlaylist = this._browseNativeProvider === "ma_playlist";
    const userPlaylist = this._browseNativeProvider === "user_playlist";
    const rows = children.map((item, index) => {
      const favorite = this._isMediaFavorite(item);
      const meta = this._mediaResultMetadata(item);
      const searchText = `${String(item.title || "")} ${String(item.artist || "")} ${String(item.album || "")} ${String(item.year || "")} ${String(item.provider_origin || item.provider_name || item.provider || "")} ${String(item.details || "")} ${String(item.media_content_id || "")}`.toLocaleLowerCase();
      const itemId = String(item.media_content_id || "");
      const checked = this._musicResultSelection?.has(itemId);
      const canOpenPlaylist = this._isMAPlaylistItem(item);
      return `
      <div class="media-row ${selectable ? "media-row-selectable" : ""}" data-index="${index}" data-search="${_fitnessEscape(searchText)}">
        ${selectable && item.can_play ? `<label class="media-select"><input type="checkbox" ${checked ? "checked" : ""} aria-label="${_fitnessEscape(l.select_item)}"><span></span></label>` : ""}
        <button class="media-open" ${(item.can_expand || canOpenPlaylist) ? "" : "disabled"}>
          ${this._mediaItemVisual(item)}
          <span class="media-result-copy"><strong>${_fitnessEscape(item.title || item.media_content_id || this._labels().generic_media)}</strong>${meta.primary.length ? `<small class="media-result-primary">${_fitnessEscape(meta.primary.join(" · "))}</small>` : ""}${meta.secondary.length ? `<small class="media-result-secondary">${_fitnessEscape(meta.secondary.join(" · "))}</small>` : ""}</span>
        </button>
        ${item.external_url ? `<button class="icon-tool media-external" title="${_fitnessEscape(l.music_open_provider)}"><ha-icon icon="mdi:open-in-new"></ha-icon></button>` : ""}
        ${item.can_play ? `<button class="icon-tool media-favorite" title="${_fitnessEscape(favorite ? (l.remove_favorite) : (l.add_favorite))}"><ha-icon icon="${favorite ? "mdi:star" : "mdi:star-outline"}"></ha-icon></button><button class="icon-tool media-play" title="${_fitnessEscape(l.play)}"><ha-icon icon="mdi:play"></ha-icon></button>` : ""}
        ${providerPlaylist && data.is_editable && this._canControlProfile && item.playlist_position ? `<button class="icon-tool media-remove" title="${_fitnessEscape(l.remove)}"><ha-icon icon="mdi:playlist-remove"></ha-icon></button>` : ""}
      </div>`;
    }).join("");
    const selectionBar = selectable ? `<div class="music-selection-bar"><strong class="music-selection-count">${_fitnessEscape(_fitnessFormatLabel(l.selected_count, {count:0}))}</strong><button class="tool music-selection-all"><ha-icon icon="mdi:select-all"></ha-icon><span>${_fitnessEscape(l.select_all)}</span></button><button class="tool music-selection-clear" disabled><ha-icon icon="mdi:select-off"></ha-icon><span>${_fitnessEscape(l.clear)}</span></button><button class="tool music-selection-add" disabled><ha-icon icon="mdi:playlist-plus"></ha-icon><span>${_fitnessEscape(l.music_add_to_playlist)}</span></button><button class="primary-tool music-selection-play" disabled><ha-icon icon="mdi:play"></ha-icon><span>${_fitnessEscape(l.play_selected)}</span></button></div>` : "";
    const headerExtra = userPlaylist && this._canControlProfile
      ? `<button class="tool user-playlist-play"><ha-icon icon="mdi:play"></ha-icon><span>${_fitnessEscape(l.play)}</span></button><button class="tool user-playlist-edit"><ha-icon icon="mdi:pencil"></ha-icon><span>${_fitnessEscape(l.edit)}</span></button>`
      : providerPlaylist
        ? `<button class="tool provider-playlist-play"><ha-icon icon="mdi:play"></ha-icon><span>${_fitnessEscape(l.play)}</span></button>${data.is_editable && this._canControlProfile ? `<span class="playlist-editable-badge"><ha-icon icon="mdi:pencil"></ha-icon>${_fitnessEscape(l.edit)}</span>` : ""}`
        : "";
    this._showModal(`
      <div class="modal-card browser-modal">
        <div class="modal-head">
          <div class="browser-title"><button class="icon-tool media-back" title="${_fitnessEscape(l.media_browser_back)}"><ha-icon icon="mdi:arrow-left"></ha-icon></button><strong>${_fitnessEscape(data.title || l.media_browser)}</strong></div>
          <div class="browser-head-actions">${headerExtra}<button class="tool media-favorites" title="${_fitnessEscape(l.media_favorites)}"><ha-icon icon="mdi:star"></ha-icon><span>${_fitnessEscape(l.media_favorites)}</span></button><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        </div>
        ${this._browseNativeProvider === "radio" ? `<label class="media-country"><span>${_fitnessEscape(l.music_country)}</span><select id="media-country"><option value="">${_fitnessEscape(l.music_all_countries)}</option>${this._sortedRadioCountries().map((country) => `<option value="${_fitnessEscape(country.code)}" ${String(country.code || "").toUpperCase() === String(this._radioCountryCode || "").toUpperCase() ? "selected" : ""}>${_fitnessEscape(country.display_name || country.code)}</option>`).join("")}</select></label>` : ""}
        <label class="media-search"><ha-icon icon="mdi:magnify"></ha-icon><input id="media-search" type="search" autocomplete="off" placeholder="${_fitnessEscape(l.media_search)}" value="${_fitnessEscape(this._mediaSearch || "")}"></label>
        ${selectionBar}
        <div class="media-list">${rows || `<div class="browser-empty">${_fitnessEscape(this._browseFavoritesMode ? (l.no_favorites) : (l.media_browser_empty))}</div>`}<div class="browser-empty media-filter-empty" hidden>${_fitnessEscape(l.media_search_empty)}</div></div>
      </div>`);
    const root = this.shadowRoot.getElementById("modal-root");
    root?.querySelector(".media-back")?.addEventListener("click", async () => {
      if (providerPlaylist && this._playlistBrowseReturn) {
        const previous = this._playlistBrowseReturn;
        this._playlistBrowseReturn = null;
        this._providerPlaylistData = null;
        this._browseData = previous.data;
        this._browseNativeProvider = previous.provider;
        this._mediaSearch = previous.search || "";
        this._renderMediaBrowser();
        return;
      }
      if (userPlaylist) { this._browseNativeProvider = ""; this._openUserPlaylists(); return; }
      if (this._browseFavoritesMode) {
        const previous = this._browseBeforeFavorites;
        const previousProvider = this._browseBeforeFavoritesProvider || "";
        this._browseFavoritesMode = false; this._browseBeforeFavorites = null; this._browseBeforeFavoritesProvider = ""; this._mediaSearch = "";
        if (previous) { this._browseData = previous; this._browseNativeProvider = previousProvider; this._renderMediaBrowser(); }
        else { this._browseNativeProvider = ""; this._renderMusicSources(); }
        return;
      }
      if (["radio","music_search"].includes(this._browseNativeProvider) || !this._mediaHistory?.length) { this._browseNativeProvider = ""; this._mediaSearch = ""; this._renderMusicSources(); return; }
      const previous = this._mediaHistory.pop() ?? ""; await this._browseMedia(previous, false);
    });
    root?.querySelector(".media-favorites")?.addEventListener("click", () => this._openMediaFavorites());
    root?.querySelector(".user-playlist-play")?.addEventListener("click", () => this._playUserPlaylist(this._activeBrowsePlaylistId));
    root?.querySelector(".user-playlist-edit")?.addEventListener("click", () => this._editUserPlaylist(this._activeBrowsePlaylistId));
    root?.querySelector(".provider-playlist-play")?.addEventListener("click", () => {
      const source = this._providerPlaylistData?.source_item;
      if (source) void this._selectMusic(source);
    });
    root?.querySelector("#media-country")?.addEventListener("change", (ev) => { this._radioCountryCode = String(ev.target?.value || "").toUpperCase(); this._browseFitnessRadio(this._mediaSearch || "", this._radioCountryCode); });
    const search = root?.querySelector("#media-search");
    search?.addEventListener("input", () => { this._mediaSearch = search.value || ""; if (this._browseNativeProvider === "radio") { clearTimeout(this._radioSearchTimer); this._radioSearchTimer = setTimeout(() => this._browseFitnessRadio(this._mediaSearch, this._radioCountryCode || ""), 450); } else this._filterMediaRows(this._mediaSearch); });
    if (this._browseNativeProvider !== "radio") this._filterMediaRows(this._mediaSearch || "");
    else requestAnimationFrame(() => { const input = this.shadowRoot?.getElementById("modal-root")?.querySelector("#media-search"); input?.focus?.(); try { input?.setSelectionRange?.(input.value.length, input.value.length); } catch (_err) {} });
    root?.querySelectorAll(".media-row").forEach((row) => {
      const item = children[Number(row.dataset.index)];
      row.querySelector(".media-open")?.addEventListener("click", () => {
        if (this._isMAPlaylistItem(item)) { void this._openMAPlaylist(item); return; }
        if (item?.can_expand) { this._mediaSearch = ""; this._browseMedia(item.media_content_id, true); }
      });
      row.querySelector(".media-select input")?.addEventListener("change", (ev) => {
        this._musicResultSelection ||= new Set();
        const id = String(item?.media_content_id || "");
        if (ev.target.checked) this._musicResultSelection.add(id); else this._musicResultSelection.delete(id);
        this._updateMusicSelectionBar(root, children);
      });
      row.querySelector(".media-favorite")?.addEventListener("click", (ev) => this._toggleMediaFavorite(item, ev.currentTarget));
      row.querySelector(".media-play")?.addEventListener("click", () => this._selectMusic(item));
      row.querySelector(".media-external")?.addEventListener("click", () => this._navigateTv(String(item?.external_url || "")));
      row.querySelector(".media-remove")?.addEventListener("click", () => this._removeMAPlaylistPosition(item.playlist_position));
    });
    if (selectable) {
      root?.querySelector(".music-selection-all")?.addEventListener("click", () => { children.filter((item) => item?.can_play).forEach((item) => this._musicResultSelection.add(String(item.media_content_id || ""))); this._renderMediaBrowser(); });
      root?.querySelector(".music-selection-clear")?.addEventListener("click", () => { this._musicResultSelection = new Set(); this._renderMediaBrowser(); });
      root?.querySelector(".music-selection-add")?.addEventListener("click", () => this._openAddToPlaylist(this._selectedMusicResults(children)));
      root?.querySelector(".music-selection-play")?.addEventListener("click", () => { this._activePlaylistContext = {kind:"selection",title:l.music_selected_items,items:this._selectedMusicResults(children)}; void this._playSelectedMAItems(this._selectedMusicResults(children)); });
      this._updateMusicSelectionBar(root, children);
    }
  }

  async _selectMusic(item, options = {}) {
    const l = this._labels();
    if (!item?.media_content_id) return;
    const isMusicAssistant = String(item.media_content_id || "").startsWith(FITNESS_MUSIC_PREFIXES.music_assistant);
    const isYtdlpPlaylist = String(item.media_content_id || "").startsWith(FITNESS_MUSIC_PREFIXES.ytdlp)
      && String(item.media_class || "").toLowerCase() === "playlist";
    if (!options.keepPlaylist) {
      this._activePlaylistContext = this._isMAPlaylistItem(item)
        ? {kind:"provider",title:String(item.title || l.music_playlist),item:this._playlistItemSnapshot(item)}
        : (isYtdlpPlaylist
          ? {kind:"youtube_playlist",title:String(item.title || l.music_playlist),item:this._playlistItemSnapshot(item)}
          : null);
      this._fitnessPlaylistIndex = 0;
      if (this._activePlaylistContext) this._activePlaylistContext.index = 0;
      if (isYtdlpPlaylist) { this._youtubePlaylistShuffle = false; this._youtubePlaylistRepeat = "off"; }
    }
    try {
      // Sendspin requires unlock() to be the first awaited work of the user's
      // click/tap. Search warms the module + relay without connecting; construct
      // synchronously, unlock first, and only then register the MA player.
      if (isMusicAssistant) {
        const player = this._maSendspinPlayer || this._createMASendspinPlayer();
        await player.unlock?.();
        if (!this._maSendspinConnected) await this._connectMASendspinPlayer(player);
      }
      const metadata = this._normalizedMediaMetadata(item);
      const result = await this._sendMediaCommand("select", {
        media_content_id:item.media_content_id,
        title:item.title || l.now_playing,
        provider_instance:String(item.provider_instance || ""),
        playlist_context:this._playlistContextSnapshot(),
        await_result:true,
        ...metadata,
      });
      if (!result?.sent) throw new Error(result?.reason || "No active Fitness TV player");
      if (result?.error) {
        throw new Error(String(result?.state?.details || l.media_error));
      }
      if (!result?.playing) throw new Error("Playback did not start");
      this._musicTitle = item.title || l.now_playing;
      this._musicMetadata = isMusicAssistant
        ? {...metadata, provider_origin:metadata.provider_origin || (metadata.provider_name ? `Music Assistant · ${metadata.provider_name}` : "Music Assistant")}
        : metadata;
      this._currentMediaContentId = item.media_content_id;
      this.shadowRoot.getElementById("modal-root")?.replaceChildren();
      this._updateMediaControls();
    } catch (err) {
      console.error("[Fitness TV] music selection failed", err);
      const title = this.shadowRoot?.querySelector(".browser-title strong");
      const message = l.media_error || l.music_only;
      if (title) title.textContent = message;
    }
  }

  async _playlistTransport(action, options = {}) {
    const context = this._activePlaylistContext;
    if (!context) return;
    if (context.kind === "youtube_playlist" && this._embeddedProvider === "youtube" && this._embeddedController) {
      try {
        if (action === "next") this._embeddedController.nextVideo?.();
        else if (action === "previous") this._embeddedController.previousVideo?.();
        else if (action === "shuffle") {
          this._youtubePlaylistShuffle = !this._youtubePlaylistShuffle;
          this._embeddedController.setShuffle?.(this._youtubePlaylistShuffle);
        } else if (action === "repeat") {
          this._youtubePlaylistRepeat = this._youtubePlaylistRepeat === "off" ? "all" : "off";
          this._embeddedController.setLoop?.(this._youtubePlaylistRepeat === "all");
        }
      } catch (_err) {}
      this._updateMediaControls();
      return;
    }
    const maQueue = Boolean(this._maSendspinPlayerId) && (
      this._isMAItem({media_content_id:this._currentMediaContentId})
      || context.kind === "provider"
      || context.kind === "selection"
      || (context.kind === "user" && (context.items || []).every((item) => this._isMAItem(item)))
    );
    if (maQueue) {
      let payload = {type:"fitness/tv/music/ma/queue",profile_entry_id:this._profile.entry_id,player_id:this._maSendspinPlayerId,action};
      if (action === "shuffle") payload.enabled = !Boolean(this._maQueueProgress?.shuffle_enabled);
      if (action === "repeat") {
        const current = String(this._maQueueProgress?.repeat_mode || "off").toLowerCase();
        payload.repeat_mode = current === "off" ? "all" : (current === "all" ? "one" : "off");
      }
      try {
        const result = await this._hass.callWS(payload);
        this._applyMAQueueProgress(result, true);
      } catch (err) { console.error("[Fitness TV] playlist transport failed", err); }
      return;
    }
    if (context.kind !== "user") return;
    const items = context.items || [];
    if (!items.length) return;
    if (action === "shuffle") { this._fitnessPlaylistShuffle = !this._fitnessPlaylistShuffle; this._updateMediaControls(); return; }
    if (action === "repeat") { this._fitnessPlaylistRepeat = this._fitnessPlaylistRepeat === "off" ? "all" : (this._fitnessPlaylistRepeat === "all" ? "one" : "off"); this._updateMediaControls(); return; }
    let index = Number(this._fitnessPlaylistIndex || 0);
    if (options.automatic && this._fitnessPlaylistRepeat === "one") {
      await this._selectMusic(items[index], {keepPlaylist:true});
      return;
    }
    if (this._fitnessPlaylistShuffle && items.length > 1) {
      let next = index;
      while (next === index) next = Math.floor(Math.random() * items.length);
      index = next;
    } else {
      index += action === "previous" ? -1 : 1;
    }
    if (index < 0 || index >= items.length) {
      if (this._fitnessPlaylistRepeat === "all") index = index < 0 ? items.length - 1 : 0;
      else {
        if (options.automatic) { await this._syncMediaState({playing:false,error:false}); this._updateMediaControls(); }
        return;
      }
    }
    this._fitnessPlaylistIndex = index;
    context.index = index;
    await this._selectMusic(items[index], {keepPlaylist:true});
  }

  _openActivePlaylist() {
    const context = this._activePlaylistContext;
    if (!context) return;
    if (context.kind === "user") { this._openUserPlaylist(context.id); return; }
    if (context.kind === "provider" && context.item) { void this._openMAPlaylist(context.item); return; }
    if (context.kind === "youtube_playlist" && context.item?.external_url) this._navigateTv(String(context.item.external_url));
  }

  async _playMusic() {
    const mediaContentId = this._currentMediaContentId || this._sharedMediaState?.media_content_id || "";
    const title = this._musicTitle || this._sharedMediaState?.title || "";
    if (String(mediaContentId || "").startsWith(FITNESS_MUSIC_PREFIXES.music_assistant)) {
      const player = this._maSendspinPlayer || this._createMASendspinPlayer();
      await player.unlock?.();
      if (!this._maSendspinConnected) await this._connectMASendspinPlayer(player);
    }
    if (!mediaContentId && !this._musicAudio?.src) {
      await this._openMediaBrowser();
      return;
    }
    const result = await this._sendMediaCommand("play", {
      media_content_id:mediaContentId,
      title,
      playlist_context:this._playlistContextSnapshot(),
      ...this._normalizedMediaMetadata(this._sharedMediaState || this._musicMetadata || {}),
    });
    if (!result?.sent) await this._heartbeat();
    this._updateMediaControls();
  }

  async _pauseMusic() {
    const result = await this._sendMediaCommand("pause", {});
    if (!result?.sent) await this._heartbeat();
    this._updateMediaControls();
  }

  _mediaProgressSnapshot(mediaContentId = this._currentMediaContentId) {
    const id = String(mediaContentId || "");
    // Music Assistant is authoritative for MA queues (Spotify, MA RadioBrowser,
    // provider playlists, etc.). Never apply MA queue time to another adapter.
    if (id.startsWith(FITNESS_MUSIC_PREFIXES.music_assistant)) {
      return this._maProgressSnapshot() || {
        position:this._mediaSeconds(this._musicMetadata?.position),
        duration:this._mediaSeconds(this._musicMetadata?.duration),
        source:"music_assistant",
      };
    }
    // Direct RadioBrowser/HA/yt-dlp audio uses the browser media element. This
    // is the only clock that follows the actual resolved stream/file playback.
    const audio = this._musicAudio;
    if (audio && String(audio.getAttribute?.("src") || "").trim()) {
      const duration = Number.isFinite(Number(audio.duration)) && Number(audio.duration) > 0
        ? Number(audio.duration)
        : this._mediaSeconds(this._musicMetadata?.duration);
      return {
        position:this._mediaSeconds(audio.currentTime),
        duration,
        source:"html_audio",
      };
    }
    // Active yt-dlp live streams use YouTube's player but are not finite tracks.
    // Treat them as LIVE rather than interpreting YouTube's moving live-window
    // duration as a seekable song duration.
    if (id.startsWith(FITNESS_MUSIC_PREFIXES.ytdlp) && this._musicMetadata?.is_live) {
      return {position:0,duration:0,source:"youtube_live"};
    }
    // yt-dlp can deliberately fall back to the YouTube iframe; SoundCloud has
    // its own PLAY_PROGRESS events. Both keep their own embedded clock.
    if (["youtube","soundcloud"].includes(this._embeddedProvider)) {
      return {
        position:this._mediaSeconds(this._embeddedPosition),
        duration:this._mediaSeconds(this._embeddedDuration || this._musicMetadata?.duration),
        source:this._embeddedProvider,
      };
    }
    return {
      position:this._mediaSeconds(this._musicMetadata?.position),
      duration:this._mediaSeconds(this._musicMetadata?.duration),
      source:"metadata",
    };
  }

  _updateMediaMarquee() {
    requestAnimationFrame(() => {
      for (const id of ["media-title","media-artist"]) {
        const element = this.shadowRoot?.getElementById(id);
        const line = element?.parentElement;
        if (!element || !line || element.hidden || line.clientWidth <= 0) continue;
        element.classList.remove("media-marquee");
        element.style.removeProperty("--media-scroll-distance");
        element.style.removeProperty("--media-scroll-duration");
        const overflow = Math.ceil(Math.max(0, element.scrollWidth - line.clientWidth));
        if (overflow <= 6) continue;
        element.style.setProperty("--media-scroll-distance", `${overflow}px`);
        element.style.setProperty("--media-scroll-duration", `${Math.max(6, Math.min(18, 5 + overflow / 28))}s`);
        element.classList.add("media-marquee");
      }
    });
  }

  _updateMediaControls(error = false) {
    const l = this._labels();
    const title = this.shadowRoot?.getElementById("media-title");
    const artist = this.shadowRoot?.getElementById("media-artist");
    const status = this.shadowRoot?.getElementById("media-status");
    const thumb = this.shadowRoot?.getElementById("media-thumb");
    const thumbFallback = this.shadowRoot?.getElementById("media-thumb-fallback");
    const progress = this.shadowRoot?.getElementById("media-progress");
    const current = this.shadowRoot?.getElementById("media-current");
    const remaining = this.shadowRoot?.getElementById("media-remaining");
    const shared = this._sharedMediaState || {};
    const metadata = this._normalizedMediaMetadata({...shared, ...(this._musicMetadata || {})});
    const mediaContentId = String(this._currentMediaContentId || shared.media_content_id || "");
    const hasSelection = Boolean(mediaContentId);
    const displayTitle = hasSelection
      ? (this._musicTitle || shared.title || l.nothing_playing)
      : (l.nothing_playing);
    const failed = hasSelection && Boolean(error || shared.error);
    const playing = hasSelection && !failed && Boolean(shared.playing || (this._musicAudio && !this._musicAudio.paused) || this._embeddedPlaying);
    const providerLabel = this._mediaProviderLabel({...shared, ...(this._musicMetadata || {}), ...metadata});
    metadata.details = this._compactMediaDetails(providerLabel, metadata.details);
    const displayArtist = [...new Set([metadata.artist, metadata.album, metadata.year, providerLabel, metadata.details]
      .map((value) => String(value || "").trim()).filter(Boolean))].join(" · ");
    if (title) title.textContent = displayTitle;
    if (artist) {
      artist.textContent = displayArtist;
      artist.hidden = !displayArtist;
    }
    this._updateMediaMarquee();
    if (status) status.textContent = !hasSelection
      ? ""
      : (failed
          ? (l.media_error)
          : (playing ? (l.now_playing) : (l.media_selected)));

    const playlistContext = this._activePlaylistContext;
    const playlistActive = Boolean(playlistContext && ((playlistContext.items?.length || 0) > 1 || ["provider","youtube_playlist"].includes(playlistContext.kind) || Number(this._maQueueProgress?.items || 0) > 1));
    const shuffleOn = playlistContext?.kind === "youtube_playlist"
      ? Boolean(this._youtubePlaylistShuffle)
      : (playlistContext?.kind === "user" && !(playlistContext.items || []).every((item) => this._isMAItem(item))
        ? Boolean(this._fitnessPlaylistShuffle)
        : Boolean(this._maQueueProgress?.shuffle_enabled));
    const repeatMode = playlistContext?.kind === "youtube_playlist"
      ? String(this._youtubePlaylistRepeat || "off")
      : (playlistContext?.kind === "user" && !(playlistContext.items || []).every((item) => this._isMAItem(item))
        ? String(this._fitnessPlaylistRepeat || "off")
        : String(this._maQueueProgress?.repeat_mode || "off"));
    for (const id of ["playlist-prev","playlist-next","playlist-shuffle","playlist-repeat"]) {
      const button = this.shadowRoot?.getElementById(id);
      if (button) button.hidden = !playlistActive;
    }
    const playlistOpen = this.shadowRoot?.getElementById("playlist-open");
    if (playlistOpen) playlistOpen.hidden = !Boolean(playlistContext && ["user","provider","youtube_playlist"].includes(playlistContext.kind));
    const shuffleButton = this.shadowRoot?.getElementById("playlist-shuffle");
    shuffleButton?.classList.toggle("active", shuffleOn);
    const repeatButton = this.shadowRoot?.getElementById("playlist-repeat");
    repeatButton?.classList.toggle("active", repeatMode !== "off");
    repeatButton?.querySelector("ha-icon")?.setAttribute("icon", repeatMode === "one" ? "mdi:repeat-once" : "mdi:repeat");

    const thumbnail = String(metadata.thumbnail || "");
    if (thumb) {
      if (thumbnail) {
        const resolvedThumb = this._resolvedMediaUrl(thumbnail);
        if (thumb.getAttribute("src") !== resolvedThumb) thumb.setAttribute("src", resolvedThumb);
        thumb.hidden = false;
      } else {
        thumb.hidden = true;
        thumb.removeAttribute("src");
      }
    }
    if (thumbFallback) thumbFallback.hidden = Boolean(thumbnail);

    const playbackProgress = this._mediaProgressSnapshot(mediaContentId);
    const duration = this._mediaSeconds(playbackProgress?.duration);
    const rawPosition = this._mediaSeconds(playbackProgress?.position);
    const position = duration > 0 ? Math.min(rawPosition, duration) : rawPosition;
    if (current) current.textContent = hasSelection ? this._formatMediaTime(position) : "0:00";
    if (remaining) remaining.textContent = hasSelection && duration > 0
      ? this._formatMediaTime(duration)
      : (playing ? (l.music_live) : "—");
    if (progress) {
      progress.min = "0";
      progress.max = String(duration > 0 ? duration : 1);
      if (!this._mediaProgressScrubbing) progress.value = String(duration > 0 ? position : 0);
      progress.disabled = !hasSelection || duration <= 0;
      progress.setAttribute("aria-valuetext", duration > 0
        ? `${this._formatMediaTime(position)} / ${this._formatMediaTime(duration)}`
        : (playing ? (l.music_live) : ""));
    }

    const play = this.shadowRoot?.getElementById("play");
    const pause = this.shadowRoot?.getElementById("pause");
    if (play) play.disabled = playing || !hasSelection;
    if (pause) pause.disabled = !playing;
    const serverCastActive = this._refreshCastUiState();
    const localCastActive = Boolean(this._localCastActive || this._localCastServerActive || this._localCastSessionActive());
    const anyCastActive = serverCastActive || localCastActive;
    const castToggle = this.shadowRoot?.getElementById("cast");
    if (castToggle) {
      castToggle.querySelector("ha-icon")?.setAttribute("icon", anyCastActive ? "mdi:cast-off" : "mdi:cast");
      const castLabel = castToggle.querySelector("span");
      if (castLabel) castLabel.textContent = anyCastActive ? (l.cast_stop) : (l.cast_dashboard);
      castToggle.title = anyCastActive ? (l.cast_stop) : (l.cast_dashboard);
    }
    const stopCast = this.shadowRoot?.getElementById("stop-cast");
    if (stopCast) {
      stopCast.hidden = !FITNESS_TV_CAST_RECEIVER || !anyCastActive;
      stopCast.disabled = !anyCastActive;
    }
    const modalHaStop = this.shadowRoot?.getElementById("modal-root")?.querySelector?.("#cast-stop");
    if (modalHaStop) {
      modalHaStop.hidden = !serverCastActive;
      modalHaStop.disabled = !serverCastActive;
    }
  }

  _style() {
    return `<style>
      :host{display:block;width:100%;max-width:none;min-height:0;position:relative;margin:0;background:var(--fitness-tv-ambient,var(--primary-background-color));color:var(--primary-text-color);overflow-x:hidden;transition:background .8s ease}
      :host([fitness-cast-receiver]){position:fixed;inset:0;left:0;z-index:1;width:100vw;height:100vh;max-width:none;margin:0;overflow:auto;overscroll-behavior:none}
      :host([fitness-cast-receiver]) ha-card.tv-shell{width:100%;min-height:100%;margin:0}
      *{box-sizing:border-box}
      ha-card.tv-shell{min-height:0;width:100%;border:0;border-radius:0;box-shadow:none;background:var(--fitness-tv-ambient,var(--primary-background-color));padding:14px;overflow:visible;transition:background .8s ease;position:relative;isolation:isolate}
      .fitness-ambient-layer{position:absolute;inset:-8%;z-index:0;overflow:hidden;pointer-events:none;opacity:.94;transition:opacity .8s ease,filter .8s ease}.fitness-ambient-layer i{position:absolute;border-radius:50%;filter:blur(62px);background:radial-gradient(circle at 44% 40%,rgba(var(--fitness-tv-ambient-rgb,3,169,244),calc(var(--fitness-tv-ambient-core-alpha,.22) * var(--fitness-ambient-flow,.82))) 0%,rgba(var(--fitness-tv-ambient-rgb,3,169,244),var(--fitness-tv-ambient-soft-alpha,.10)) 42%,transparent 74%);will-change:transform,opacity}.fitness-ambient-layer i:nth-child(1){width:74vmax;height:74vmax;left:-31vmax;top:-35vmax}.fitness-ambient-layer i:nth-child(2){width:70vmax;height:70vmax;right:-32vmax;bottom:-38vmax;opacity:.88}.fitness-ambient-layer i:nth-child(3){left:27%;top:18%;width:54vmax;height:54vmax;opacity:.52;background:radial-gradient(circle,rgba(var(--fitness-tv-ambient-rgb,3,169,244),calc(var(--fitness-tv-ambient-soft-alpha,.10) * .88)) 0%,rgba(255,255,255,.025) 44%,transparent 73%)}.fitness-ambient-layer i:nth-child(4){left:9%;bottom:-12vmax;width:72vmax;height:30vmax;border-radius:48%;opacity:.34;filter:blur(78px);background:linear-gradient(108deg,transparent 4%,rgba(var(--fitness-tv-ambient-rgb,3,169,244),calc(var(--fitness-tv-ambient-soft-alpha,.10) * 1.4)) 42%,rgba(255,255,255,.024) 61%,transparent 95%)}:host([fitness-animations]) .fitness-ambient-layer i:nth-child(1){animation:fitness-ambient-drift-a 16s cubic-bezier(.45,.05,.3,.96) infinite alternate}:host([fitness-animations]) .fitness-ambient-layer i:nth-child(2){animation:fitness-ambient-drift-b 20s cubic-bezier(.45,.05,.3,.96) infinite alternate}:host([fitness-animations]) .fitness-ambient-layer i:nth-child(3){animation:fitness-ambient-breathe 10.5s ease-in-out infinite alternate}:host([fitness-animations]) .fitness-ambient-layer i:nth-child(4){animation:fitness-ambient-ribbon 19s ease-in-out infinite alternate}:host([fitness-live-ambient]) .fitness-ambient-layer{opacity:1;filter:saturate(1.1) contrast(1.02)}:host([fitness-live-ambient][fitness-animations]) .fitness-ambient-layer i:nth-child(1){animation-duration:calc(var(--fitness-motion-speed,6s) * 1.85)}:host([fitness-live-ambient][fitness-animations]) .fitness-ambient-layer i:nth-child(2){animation-duration:calc(var(--fitness-motion-speed,6s) * 2.25)}:host([fitness-live-ambient][fitness-animations]) .fitness-ambient-layer i:nth-child(3){animation-duration:calc(var(--fitness-motion-speed,6s) * 1.18)}:host([fitness-live-ambient][fitness-animations]) .fitness-ambient-layer i:nth-child(4){animation-duration:calc(var(--fitness-motion-speed,6s) * 2);opacity:.48}@keyframes fitness-ambient-drift-a{0%{transform:translate3d(-3%,-3%,0) scale(.94);opacity:.72}55%{opacity:1}100%{transform:translate3d(24%,18%,0) scale(1.13);opacity:.82}}@keyframes fitness-ambient-drift-b{0%{transform:translate3d(8%,11%,0) scale(1.05);opacity:.82}100%{transform:translate3d(-25%,-17%,0) scale(.91);opacity:1}}@keyframes fitness-ambient-breathe{0%{transform:translate3d(-10%,-6%,0) scale(.82);opacity:.34}50%{opacity:.62}100%{transform:translate3d(14%,11%,0) scale(1.2);opacity:.4}}@keyframes fitness-ambient-ribbon{0%{transform:translate3d(-12%,4%,0) rotate(-4deg) scaleX(.9);opacity:.22}48%{opacity:.44}100%{transform:translate3d(18%,-12%,0) rotate(5deg) scaleX(1.14);opacity:.3}}
      .tv-toolbar{position:sticky;top:0;z-index:60;display:grid;grid-template-columns:auto minmax(140px,220px) auto minmax(260px,1fr);gap:10px;align-items:center;margin-bottom:12px;padding:10px 12px;border-radius:18px;background:var(--card-background-color);box-shadow:var(--ha-card-box-shadow,0 2px 8px rgba(0,0,0,.12));min-width:0}
      .tv-brand{display:flex;align-items:center;gap:8px;font-size:20px;white-space:nowrap}.tv-brand .fitness-brand-icon{width:30px;height:30px;flex:0 0 30px;object-fit:contain}.tv-brand ha-icon{color:var(--primary-color)}
      :host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile{grid-template-columns:auto auto minmax(0,1fr);grid-template-areas:"brand identity actions" "music music music";align-items:center;row-gap:8px}
      :host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile .tv-brand{grid-area:brand}
      :host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile .tv-profile-identity{grid-area:identity}
      :host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile .tv-actions{grid-area:actions;justify-content:flex-end;overflow:visible;min-width:0}:host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile .tv-actions>.tool{min-width:88px;max-width:none}:host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile .tv-actions>.tool span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      :host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile .music-controls{grid-area:music;min-width:0;width:100%;grid-template-columns:auto minmax(280px,1fr);border-top:1px solid var(--divider-color);padding-top:8px}
      .profile-control{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:8px;min-width:0}.profile-control span{font-size:12px;color:var(--secondary-text-color)}.tv-profile-identity{display:flex;align-items:center;gap:6px;min-width:0;color:var(--secondary-text-color)}.tv-profile-identity ha-icon{--mdc-icon-size:18px}.tv-profile-identity span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}
      .tv-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(88px,1fr));align-items:stretch;gap:7px;min-width:0;overflow:visible}.tv-actions>.tool{width:100%;min-width:0;padding-inline:clamp(7px,1vw,12px)}.tv-actions>.tool span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      select,.tool,.icon-tool{font:inherit;color:var(--primary-text-color);background:var(--secondary-background-color);border:1px solid var(--divider-color);border-radius:12px;min-height:42px}
      select{width:100%;min-width:0;padding:0 10px}.tool,.icon-tool{cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:5px 12px;min-width:0;line-height:1.2}.icon-tool{width:42px;min-width:42px;padding:0}.tool>span,.primary-tool>span,.adapter-setup>span,.flow-home>span{display:block;min-width:0;max-width:100%;font-size:clamp(11px,.76vw,13px);line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;word-break:normal;overflow-wrap:normal}.tool:disabled,.icon-tool:disabled{opacity:.45;cursor:default}
      .music-controls{display:grid;grid-template-columns:auto minmax(280px,1fr);gap:10px;align-items:center;min-width:0}.music-button-strip{display:flex;align-items:center;gap:7px;flex-wrap:nowrap;min-width:0}.music-button-strip>.tool{flex:1 1 auto;min-width:0}.music-button-strip>.tool span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.media-now{min-width:0;display:grid;grid-template-columns:44px minmax(0,1fr);gap:8px;align-items:center;padding-left:3px}.media-art{width:44px;height:44px;display:grid;place-items:center;overflow:hidden;border-radius:9px;background:var(--secondary-background-color);color:var(--secondary-text-color)}.media-art img{width:100%;height:100%;object-fit:cover}.media-art ha-icon{--mdc-icon-size:25px}.media-now-main{min-width:0;width:min(420px,100%);max-width:420px}.media-copy{min-width:0;width:100%;max-width:420px;overflow:hidden}.media-copy small{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--secondary-text-color);font-size:9px}.media-scroll-line{min-width:0;max-width:100%;overflow:hidden;white-space:nowrap}.media-scroll-line strong,.media-scroll-line span{display:inline-block;white-space:nowrap;min-width:0;will-change:transform}.media-copy strong{font-size:13px}.media-copy span{margin-top:1px;color:var(--secondary-text-color);font-size:10px}.media-scroll-line .media-marquee{animation:fitness-media-marquee var(--media-scroll-duration,8s) ease-in-out 1s infinite alternate}@keyframes fitness-media-marquee{from{transform:translateX(0)}to{transform:translateX(calc(-1 * var(--media-scroll-distance,0px)))}}.media-progress-wrap{display:grid;grid-template-columns:minmax(0,1fr);gap:1px;align-items:center;margin-top:3px;color:var(--secondary-text-color);font-size:9px;font-variant-numeric:tabular-nums;min-width:0;width:min(420px,100%);max-width:420px;justify-self:start}.media-progress-wrap input{grid-column:1;width:100%;height:14px;min-width:0;margin:0;accent-color:var(--primary-color)}.media-progress-wrap input:disabled{opacity:.45}.playlist-control.active{color:var(--primary-color);border-color:color-mix(in srgb,var(--primary-color) 65%,var(--divider-color));background:color-mix(in srgb,var(--primary-color) 12%,var(--secondary-background-color))}.media-time-row{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0;line-height:1}.media-time-row span{white-space:nowrap}
      .tv-oled-stage{min-width:0;position:relative;z-index:1}.tv-grid{--tv-columns:4;--tv-row:4px;display:grid;grid-template-columns:repeat(var(--tv-columns),minmax(0,1fr));grid-auto-rows:var(--tv-row);grid-auto-flow:dense;column-gap:12px;row-gap:0;width:100%;align-items:start}.tv-card-slot{min-width:0;position:relative;overflow:visible;min-height:var(--tv-card-visual-height,1px);border-radius:14px}.tv-card-slot>.tv-mounted-card{display:block;width:100%;max-width:none}.tv-card-slot.read-only-card{cursor:default}.tv-card-slot.read-only-card>.tv-mounted-card{user-select:text}.layout-tools{display:none;position:absolute;z-index:80;top:5px;right:5px;align-items:center;gap:3px;padding:3px;border-radius:10px;background:color-mix(in srgb,var(--card-background-color) 92%,transparent);border:1px solid var(--divider-color);box-shadow:0 2px 8px rgba(0,0,0,.18)}.fitness-remote-section-selected,.fitness-remote-section-active{position:relative;z-index:72!important;transform-origin:center center;will-change:transform,box-shadow,filter;transition:transform .19s cubic-bezier(.2,.85,.2,1),outline-color .16s ease,box-shadow .19s ease,filter .16s ease}.fitness-remote-section-selected{outline:2px solid color-mix(in srgb,var(--primary-color,#03a9f4) 92%,white 8%)!important;outline-offset:3px!important;transform:scale(1.028);box-shadow:0 0 0 2px rgba(255,255,255,.10),0 0 0 5px color-mix(in srgb,var(--primary-color,#03a9f4) 36%,transparent),0 0 24px 8px color-mix(in srgb,var(--primary-color,#03a9f4) 29%,transparent),0 18px 42px rgba(0,0,0,.30)!important;filter:brightness(1.07) saturate(1.055)}.tv-toolbar.fitness-remote-section-selected{transform:scale(1.012)}.fitness-remote-section-active{outline:1px solid color-mix(in srgb,var(--primary-color,#03a9f4) 72%,transparent)!important;outline-offset:3px!important;transform:scale(1.012);box-shadow:0 0 0 3px color-mix(in srgb,var(--primary-color,#03a9f4) 16%,transparent),0 0 16px 4px color-mix(in srgb,var(--primary-color,#03a9f4) 14%,transparent),0 10px 28px rgba(0,0,0,.18)!important;filter:brightness(1.035) saturate(1.025)}.tv-toolbar.fitness-remote-section-active{transform:scale(1.006)}.cast-exit-confirm[hidden]{display:none!important}:host([fitness-cast-receiver]) .cast-exit-confirm{position:fixed;left:9vw;right:9vw;bottom:28px;z-index:9999;margin:0 auto;max-width:760px;padding:13px 20px;border-radius:14px;background:rgba(0,0,0,.86);color:#fff;font:700 15px/1.3 system-ui,sans-serif;text-align:center;pointer-events:none;box-shadow:0 8px 28px rgba(0,0,0,.38);border:1px solid rgba(255,255,255,.24)}.layout-tools .drag-grip{--mdc-icon-size:18px;color:var(--secondary-text-color);padding:0 3px}.layout-tools button{width:28px;height:28px;border:0;border-radius:7px;display:grid;place-items:center;background:var(--secondary-background-color);color:var(--primary-text-color);cursor:pointer}.layout-tools button ha-icon{--mdc-icon-size:16px}:host([layout-editing]) .layout-tools{display:flex}:host([layout-editing]) .tv-card-slot{outline:2px dashed color-mix(in srgb,var(--primary-color) 65%,transparent);outline-offset:-2px;cursor:grab}:host([layout-editing]) .tv-card-slot>.tv-mounted-card{pointer-events:none;user-select:none}:host([layout-editing]) .tv-card-slot.dragging{opacity:.42}:host([layout-editing]) .tv-card-slot.drop-target{outline:3px solid var(--primary-color);background:color-mix(in srgb,var(--primary-color) 7%,transparent)}.arrange-tool[aria-pressed="true"]{border-color:var(--primary-color);background:color-mix(in srgb,var(--primary-color) 16%,var(--secondary-background-color))}
      :host([fitness-cast-receiver]) .fitness-remote-section-selected,:host([fitness-cast-receiver]) .fitness-remote-section-active{will-change:transform;transition:transform .11s ease-out,outline-color .11s ease-out,box-shadow .11s ease-out;filter:none!important}
      :host([fitness-cast-receiver]) .fitness-remote-section-selected{transform:translate3d(0,-1px,0) scale(1.012);box-shadow:0 0 0 3px color-mix(in srgb,var(--primary-color,#03a9f4) 27%,transparent),0 8px 18px rgba(0,0,0,.24)!important}
      :host([fitness-cast-receiver]) .tv-toolbar.fitness-remote-section-selected{transform:translate3d(0,-1px,0) scale(1.004)}
      :host([fitness-cast-receiver]) .fitness-remote-section-active{transform:translate3d(0,0,0) scale(1.006);box-shadow:0 0 0 2px color-mix(in srgb,var(--primary-color,#03a9f4) 18%,transparent),0 6px 14px rgba(0,0,0,.18)!important}
      :host([fitness-cast-receiver]) .tv-toolbar.fitness-remote-section-active{transform:translate3d(0,0,0) scale(1.002)}
      .cast-focus-tooltip[hidden]{display:none!important}:host([fitness-cast-receiver]) .cast-focus-tooltip{position:fixed;z-index:9999;width:max-content;max-width:min(300px,calc(100vw - 24px));margin:0;padding:8px 12px;border-radius:10px;background:rgba(0,0,0,.90);color:#fff;font:600 12px/1.3 system-ui,sans-serif;text-align:center;white-space:normal;pointer-events:none;box-shadow:0 6px 18px rgba(0,0,0,.34);border:1px solid rgba(255,255,255,.22);animation:fitness-tooltip-in .14s ease-out both}:host([fitness-cast-receiver]) .cast-focus-tooltip::before{content:"";position:absolute;left:var(--cast-tooltip-arrow-left,50%);top:-7px;transform:translateX(-50%);border-left:7px solid transparent;border-right:7px solid transparent;border-bottom:7px solid rgba(0,0,0,.90)}:host([fitness-cast-receiver]) .cast-focus-tooltip[data-placement="above"]::before{top:auto;bottom:-7px;border-bottom:0;border-top:7px solid rgba(0,0,0,.90)}@keyframes fitness-tooltip-in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
      .fatal{padding:30px;font-size:18px}
      .access-denied{min-height:280px;display:flex;align-items:center;justify-content:center;gap:16px;padding:36px;text-align:left;color:var(--secondary-text-color)}.access-denied>ha-icon{--mdc-icon-size:38px;color:var(--error-color)}.access-denied strong,.access-denied span{display:block}.access-denied strong{font-size:20px;color:var(--primary-text-color);margin-bottom:5px}.access-denied span{max-width:620px;line-height:1.45}.view-only-badge,.view-only-notice{display:inline-flex;align-items:center;gap:6px;color:var(--secondary-text-color)}.view-only-badge{padding:3px 8px;border-radius:999px;background:var(--secondary-background-color);font-size:10px}.view-only-badge ha-icon,.view-only-notice ha-icon{--mdc-icon-size:16px}.view-only-notice{margin:-2px 0 10px;padding:9px 12px;border-radius:12px;background:color-mix(in srgb,var(--primary-color) 7%,var(--secondary-background-color));font-size:11px}.read-only-media{grid-template-columns:minmax(180px,1fr)!important}.read-only-card .layout-tools{display:none!important}
      .modal-backdrop{position:fixed;z-index:9999;top:var(--modal-top,68px);left:0;right:0;bottom:0;background:rgba(0,0,0,.42);display:grid;place-items:start center;padding:4px 18px 18px;overflow:hidden;overscroll-behavior:none}
      .modal-card{width:min(760px,calc(100vw - 16px));max-width:calc(100vw - 16px);max-height:calc(100dvh - var(--modal-top,68px) - 12px);overflow:hidden;display:flex;flex-direction:column;border-radius:20px;background:var(--card-background-color);box-shadow:0 20px 70px rgba(0,0,0,.42);border:1px solid var(--divider-color)}
      .modal-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;border-bottom:1px solid var(--divider-color);font-size:17px}.browser-title,.browser-head-actions{display:flex;align-items:center;gap:8px;min-width:0}.browser-title strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.media-country{margin:8px 10px 0;display:grid;grid-template-columns:auto minmax(160px,1fr);align-items:center;gap:9px;color:var(--secondary-text-color);font-size:12px}.media-country select{width:100%;padding:0 9px}.media-search{margin:8px 10px 0;display:grid;grid-template-columns:24px minmax(0,1fr);align-items:center;gap:6px;padding:7px 10px;border:1px solid var(--divider-color);border-radius:12px;background:var(--secondary-background-color)}.media-search ha-icon{--mdc-icon-size:19px;color:var(--secondary-text-color)}.media-search input{min-width:0;border:0;outline:0;background:transparent;color:var(--primary-text-color);font:inherit}.media-row[hidden]{display:none}.media-favorite.favorite-pulse{transform:scale(1.13);border-color:var(--primary-color);background:color-mix(in srgb,var(--primary-color) 18%,var(--secondary-background-color));transition:transform .12s ease,background .12s ease}.backend-flow-modal{height:min(900px,calc(100dvh - var(--modal-top,68px) - 26px));max-height:calc(100dvh - var(--modal-top,68px) - 26px);overflow:hidden!important}.backend-flow-modal .backend-flow-host{display:block;flex:1 1 auto;min-height:0;overflow:hidden!important}.backend-flow-modal .backend-flow-host>fitness-backend-flow{display:block;height:100%;min-height:0;overflow:hidden}
      .picker-list,.media-list{overflow:auto;padding:8px}.picker-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
      .cast-picker{padding:14px;display:grid;gap:12px;overflow-y:auto;min-height:0}.cast-section{display:grid;gap:11px;padding:14px;border-radius:20px;background:var(--secondary-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 68%,transparent)}.cast-section-copy{display:grid;grid-template-columns:30px minmax(0,1fr);gap:10px;align-items:start}.cast-section-copy>ha-icon{color:var(--primary-color);--mdc-icon-size:24px}.cast-section-copy strong,.cast-section-copy small{display:block}.cast-section-copy small{margin-top:4px;color:var(--secondary-text-color);font-size:11px;line-height:1.4}.cast-section-actions{display:flex;gap:8px;flex-wrap:nowrap;min-width:0}.cast-section-actions>button{flex:1 1 0;min-width:0}.cast-target-control{display:grid;gap:6px}.cast-target-control span{font-size:12px;color:var(--secondary-text-color)}.cast-now{min-width:140px}.cast-status{min-height:20px;color:var(--secondary-text-color);font-size:12px}.remote-gateway-modal{height:min(820px,calc(100dvh - var(--modal-top,68px) - 26px));max-height:calc(100dvh - var(--modal-top,68px) - 26px)}.remote-gateway-body{padding:14px;display:grid;gap:12px;overflow-y:auto;min-height:0}.remote-gateway-intro,.remote-radio-card,.remote-protocol{border:1px solid color-mix(in srgb,var(--divider-color) 68%,transparent);background:var(--secondary-background-color);border-radius:20px}.remote-gateway-intro{display:grid;grid-template-columns:30px minmax(0,1fr);gap:10px;padding:14px}.remote-gateway-intro>ha-icon,.remote-radio-head>ha-icon,.remote-protocol>ha-icon{color:var(--primary-color)}.remote-gateway-intro strong,.remote-gateway-intro small,.remote-radio-head strong,.remote-radio-head small{display:block}.remote-gateway-intro small,.remote-radio-head small{margin-top:4px;color:var(--secondary-text-color);font-size:11px;line-height:1.4}.remote-radio-card{padding:14px;display:grid;gap:11px}.remote-radio-head{display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:10px;align-items:start}.remote-state{font-size:11px;color:var(--secondary-text-color);white-space:nowrap}.remote-actions{display:flex;gap:8px;flex-wrap:nowrap;min-width:0}.remote-actions>button{flex:1 1 0;min-width:0}.remote-warning{padding:10px 12px;border-radius:14px;background:color-mix(in srgb,var(--warning-color,#ff9800) 12%,transparent);color:var(--secondary-text-color);font-size:11px}.remote-device-list{display:grid;gap:7px}.remote-device{display:grid;grid-template-columns:24px minmax(0,1fr) 20px 34px;gap:8px;align-items:center;padding:9px 10px;border-radius:14px;background:color-mix(in srgb,var(--card-background-color) 70%,transparent)}.remote-device .remote-ble-disconnect{width:32px;min-width:32px;min-height:32px;height:32px;border-radius:9px}.remote-device strong,.remote-device small{display:block}.remote-device small,.remote-empty{color:var(--secondary-text-color);font-size:10px}.remote-device .ok{color:var(--success-color,#4caf50);--mdc-icon-size:18px}.remote-protocol{display:flex;gap:8px;align-items:center;padding:11px 13px;color:var(--secondary-text-color);font-size:11px}.tool>span,.primary-tool>span,.adapter-setup>span,.flow-home>span{font-size:clamp(11px,.76vw,13px);line-height:1.2;min-width:0;word-break:normal;overflow-wrap:normal}.profile-assign{display:grid;grid-template-columns:20px minmax(92px,1fr);align-items:center;gap:5px;min-width:0;padding:0 7px;border:1px solid var(--divider-color);border-radius:10px;background:var(--secondary-background-color)}.profile-assign ha-icon{--mdc-icon-size:18px;color:var(--primary-color)}.profile-assign select{min-width:0;width:100%;height:34px;border:0;background:transparent;color:var(--primary-text-color);font:inherit;font-size:clamp(11px,.72vw,12px)}.profile-adapter-removed{opacity:.58}.profile-adapter-removed>span strong{text-decoration:line-through}.profile-settings{display:grid;gap:10px;padding:14px}.configure-modal{height:min(860px,calc(100dvh - var(--modal-top,68px) - 26px));max-height:calc(100dvh - var(--modal-top,68px) - 26px);overflow:hidden!important;display:flex;flex-direction:column}.configure-modal .profile-settings{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch}.configure-modal>.settings-actions{flex:0 0 auto;position:relative;bottom:auto;z-index:4;padding:11px 14px;background:color-mix(in srgb,var(--card-background-color) 97%,transparent);border-top:1px solid color-mix(in srgb,var(--divider-color) 68%,transparent)}.setting-toggle,.setting-field,.setting-range{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;padding:11px;border-radius:12px;background:var(--secondary-background-color)}.setting-field{grid-template-columns:180px minmax(0,1fr)}.setting-field select{width:100%}.setting-range{grid-template-columns:minmax(0,1fr) minmax(180px,280px) 48px}.setting-toggle small,.setting-range small,.setting-info small{display:block;margin-top:3px;color:var(--secondary-text-color);font-size:10px}.setting-title,.modal-title-with-icon{display:inline-flex;align-items:center;gap:7px}.setting-title ha-icon,.modal-title-with-icon ha-icon{--mdc-icon-size:20px;color:var(--primary-color)}.setting-info{display:grid;grid-template-columns:28px minmax(0,1fr);gap:10px;align-items:center;padding:13px;border-radius:18px;background:var(--secondary-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 70%,transparent)}.setting-info ha-icon{color:var(--primary-color)}.setting-adapters{display:grid;gap:10px;padding:13px;border-radius:18px;background:var(--secondary-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 70%,transparent)}.setting-adapters-head>span{min-width:0}.setting-adapters-head>span>strong,.setting-adapters-head>span>small{display:block}.setting-adapters-head>span>small{margin-top:4px;color:var(--secondary-text-color);font-size:10px;line-height:1.4}.music-adapter-list,.music-adapter-picker{display:grid;gap:7px}.music-adapter-row{display:grid;grid-template-columns:22px 24px minmax(0,1fr) auto;gap:9px;align-items:center;padding:10px;border-radius:16px;background:color-mix(in srgb,var(--card-background-color) 72%,transparent);border:1px solid color-mix(in srgb,var(--divider-color) 64%,transparent)}.music-adapter-row input{width:18px;height:18px}.music-adapter-row ha-icon{--mdc-icon-size:20px}.music-adapter-row img{width:20px;height:20px;object-fit:contain}.music-adapter-row small,.music-adapter-row strong{display:block}.music-adapter-row small{color:var(--secondary-text-color);font-size:10px;margin-top:2px}.music-adapter-row.unavailable{opacity:.58}.adapter-actions{display:flex;align-items:center;justify-content:flex-end;gap:6px;flex-wrap:nowrap;min-width:0}.adapter-actions>*{flex:0 1 auto;min-width:104px;max-width:190px}.adapter-actions>.adapter-account{flex:1 1 140px;min-width:120px}.adapter-actions>.adapter-setup{min-width:112px;min-height:36px}.adapter-actions>.adapter-remove{min-width:102px}.adapter-account{font:inherit;max-width:190px;min-height:32px;padding:0 6px;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:9px}.adapter-setup{font:inherit;font-size:11px;color:var(--primary-color);background:transparent;border:1px solid var(--divider-color);border-radius:9px;padding:6px 8px;cursor:pointer}.adapter-actions>.adapter-setup>span,.provider-catalog-row>.adapter-setup>span,.setting-adapters-head>.adapter-setup>span{white-space:normal;overflow:visible;text-overflow:clip;word-break:normal;overflow-wrap:normal}.music-adapter-picker .music-adapter-row{grid-template-columns:22px 24px minmax(0,1fr)}.music-search-modal{overflow:hidden!important;display:flex;flex-direction:column;height:min(820px,calc(100dvh - var(--modal-top,68px) - 26px));max-height:calc(100dvh - var(--modal-top,68px) - 26px);min-height:0}.provider-catalog-modal{overflow:hidden!important;display:flex;flex-direction:column;height:min(820px,calc(100dvh - 32px));max-height:calc(100dvh - 32px);min-height:0}.provider-catalog-list{flex:1 1 auto;min-height:0;max-height:100%;overflow-y:auto!important;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch}.music-search-form{display:flex;flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch;flex-direction:column;gap:12px;padding:14px}.music-search-form>.field-label,.music-search-form>.music-search-status,.music-search-form>.music-search-error,.music-search-form>.modal-actions{flex:0 0 auto}.music-search-form>.music-adapter-picker{flex:0 0 auto;min-height:auto;overflow:visible}.music-type-filter{display:grid;gap:7px;padding:10px 11px;border-radius:14px;background:var(--secondary-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 64%,transparent)}.music-type-filter-title{font-size:11px;font-weight:700;color:var(--secondary-text-color)}.music-type-options{display:flex;gap:7px;flex-wrap:wrap}.music-type-option{display:inline-flex;align-items:center;gap:6px;padding:7px 9px;border-radius:11px;background:var(--card-background-color);border:1px solid var(--divider-color);cursor:pointer;white-space:nowrap}.music-type-option input{width:16px;height:16px;margin:0}.music-type-option ha-icon{--mdc-icon-size:18px;color:var(--primary-color)}.music-type-option span{font-size:11px}.provider-catalog-list{display:grid;gap:9px;padding:14px}.provider-catalog-row{display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:10px;align-items:center;padding:12px;border-radius:18px;background:var(--secondary-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 70%,transparent)}.provider-catalog-row ha-icon{color:var(--primary-color)}.provider-catalog-row span strong,.provider-catalog-row span small{display:block}.provider-catalog-row span small{margin-top:3px;color:var(--secondary-text-color);font-size:10px}.provider-catalog-row>.adapter-setup{min-width:clamp(132px,16vw,190px);min-height:40px;white-space:normal}.setting-adapters-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.setting-adapters-head .adapter-setup{flex:0 0 auto;min-width:clamp(132px,18vw,190px);min-height:40px;white-space:normal}.browser-working{display:flex;gap:9px;align-items:center;padding:12px;border-radius:11px;background:var(--secondary-background-color);color:var(--secondary-text-color)}.spin{animation:fitness-spin 1s linear infinite}@keyframes fitness-spin{to{transform:rotate(360deg)}}.setting-range input{width:100%}.setting-range output{text-align:right;font-weight:700}.setting-toggle input{width:20px;height:20px}.settings-actions{display:flex;align-items:center;justify-content:flex-end;gap:9px}.settings-status{font-size:12px;color:var(--secondary-text-color)}
      .picker-row{display:grid;grid-template-columns:24px 28px minmax(0,1fr);gap:9px;align-items:center;padding:11px;border-radius:12px;background:var(--secondary-background-color);cursor:pointer}.picker-row input{width:18px;height:18px}
      .music-source:disabled{opacity:.58;cursor:not-allowed}.browser-warning{display:flex;align-items:flex-start;gap:8px;margin:0 14px 10px;padding:10px 12px;border-radius:11px;background:var(--warning-color,rgba(255,152,0,.14));font-size:11px}.browser-warning ha-icon{--mdc-icon-size:18px;flex:0 0 auto}.media-thumb{width:52px;height:52px;object-fit:cover;border-radius:9px;flex:0 0 52px;background:var(--card-background-color)}.media-source-icon{width:52px;--mdc-icon-size:28px;color:var(--primary-color);justify-self:center}.media-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:7px;align-items:center;margin-bottom:6px}.media-open{min-width:0;min-height:66px;display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;text-align:left;gap:10px;padding:7px 10px;border:0;border-radius:12px;color:var(--primary-text-color);background:var(--secondary-background-color);cursor:pointer}.media-open:disabled{cursor:default}.media-open span{display:grid;gap:2px;min-width:0;overflow:hidden}.media-open strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:650}.media-open small,.music-source small,.music-link-support{color:var(--secondary-text-color);font-size:12px;line-height:1.35;white-space:normal}.media-result-primary,.media-result-secondary{overflow:hidden;text-overflow:ellipsis;white-space:nowrap!important}.media-result-primary{color:var(--primary-text-color)!important;font-size:11px!important}.media-result-secondary{font-size:10px!important;opacity:.9}.browser-empty{padding:24px;text-align:center;color:var(--secondary-text-color)}.media-row-selectable{grid-template-columns:auto minmax(0,1fr) auto auto auto}.media-select{display:grid;place-items:center;width:30px;height:100%;cursor:pointer}.media-select input{width:18px;height:18px;accent-color:var(--primary-color)}.music-selection-bar{position:sticky;top:0;z-index:3;display:flex;align-items:center;flex-wrap:wrap;gap:7px;margin:0 12px 8px;padding:8px 10px;border:1px solid var(--divider-color);border-radius:14px;background:var(--card-background-color);box-shadow:0 5px 16px rgba(0,0,0,.12)}.music-selection-count{margin-right:auto;font-size:12px}.playlist-list,.playlist-edit-list{display:grid;gap:8px;padding:12px;overflow:auto}.playlist-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:7px;align-items:center}.playlist-open{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:10px;min-width:0;padding:8px 10px;border:1px solid var(--divider-color);border-radius:14px;background:var(--secondary-background-color);color:var(--primary-text-color);text-align:left;cursor:pointer}.playlist-open span,.playlist-edit-row span{min-width:0;display:grid;gap:2px}.playlist-open strong,.playlist-open small,.playlist-edit-row strong,.playlist-edit-row small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.playlist-open small,.playlist-edit-row small{font-size:11px;color:var(--secondary-text-color)}.playlist-edit-row{display:grid;grid-template-columns:52px minmax(0,1fr) auto auto auto;gap:7px;align-items:center;padding:7px;border:1px solid var(--divider-color);border-radius:12px}.playlist-add-summary{margin:12px 14px;color:var(--secondary-text-color)}.field-label select{box-sizing:border-box;width:100%;padding:12px 13px;border:1px solid var(--divider-color);border-radius:15px;background:var(--secondary-background-color);color:var(--primary-text-color);font:inherit;outline:none}.playlist-editable-badge{display:inline-flex;align-items:center;gap:5px;padding:7px 9px;border:1px solid var(--divider-color);border-radius:12px;color:var(--secondary-text-color);font-size:11px}.playlist-editable-badge ha-icon{--mdc-icon-size:16px}.playlist-modal .modal-actions,.playlist-add-modal .modal-actions{padding:0 14px 14px}
      .music-source-list{display:grid;gap:10px;padding:12px}.music-source{display:flex;align-items:center;gap:14px;width:100%;padding:14px 16px;border:1px solid var(--divider-color);border-radius:18px;background:var(--secondary-background-color);color:var(--primary-text-color);text-align:left;cursor:pointer;transition:transform .16s ease,border-color .16s ease,background .16s ease,box-shadow .16s ease}.music-source:hover{transform:translateY(-1px);border-color:color-mix(in srgb,var(--primary-color) 38%,var(--divider-color));background:color-mix(in srgb,var(--primary-color) 7%,var(--secondary-background-color));box-shadow:0 8px 22px rgba(0,0,0,.12)}.music-source>ha-icon{--mdc-icon-size:28px;color:var(--primary-color);flex:0 0 auto}.music-source span{display:grid;gap:4px;min-width:0}.music-source strong{font-size:15px}.field-label{display:grid;gap:6px;margin:12px 14px;color:var(--secondary-text-color);font-size:12px}.field-label input{box-sizing:border-box;width:100%;padding:12px 13px;border:1px solid var(--divider-color);border-radius:15px;background:var(--secondary-background-color);color:var(--primary-text-color);font:inherit;outline:none;transition:border-color .16s ease,box-shadow .16s ease}.field-label input:focus{border-color:var(--primary-color);box-shadow:0 0 0 3px color-mix(in srgb,var(--primary-color) 18%,transparent)}.music-link-support{margin:4px 14px 12px}.music-link-examples{display:grid;gap:3px;margin-top:8px;font-family:monospace;font-size:10px}.music-link-modal .modal-actions{padding:0 14px 14px}.primary-tool{min-height:42px;display:inline-flex;align-items:center;justify-content:center;gap:7px;border:1px solid var(--primary-color);border-radius:15px;padding:0 14px;background:var(--primary-color);color:var(--text-primary-color,#fff);cursor:pointer;transition:transform .16s ease,box-shadow .16s ease}.primary-tool:hover{transform:translateY(-1px);box-shadow:0 8px 20px color-mix(in srgb,var(--primary-color) 25%,transparent)}.fitness-embed-host{position:fixed;left:-10000px;top:-10000px;width:320px;height:180px;opacity:.01;pointer-events:none;overflow:hidden}.fitness-embed-host iframe{width:320px;height:180px;border:0}
      /* Modern Fitness TV surface: every mounted dashboard card gets the same rounded visual language. */
      .tv-toolbar{border-radius:24px;border:1px solid color-mix(in srgb,var(--divider-color) 74%,transparent);background:color-mix(in srgb,var(--card-background-color) 94%,transparent);box-shadow:0 12px 34px rgba(0,0,0,.14);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}
      .tv-card-slot{border-radius:22px;--ha-card-border-radius:22px;--ha-card-border-width:0px;filter:drop-shadow(0 8px 18px rgba(0,0,0,.08))}.tv-card-slot>.tv-mounted-card{border-radius:22px;--ha-card-border-radius:22px;--ha-card-border-width:0px;overflow:hidden}
      
      
      
      
      
      
      
      
      :host([fitness-animations]) .tv-toolbar .tool ha-icon,:host([fitness-animations]) .tv-toolbar .icon-tool ha-icon{animation:fitness-tool-icon-alive 3.9s ease-in-out infinite;transform-origin:center}
      :host([fitness-animations]) .tv-actions .tool:nth-child(2n) ha-icon,:host([fitness-animations]) .music-button-strip>*:nth-child(2n) ha-icon{animation-delay:-2.1s}
      :host([fitness-animations]) .tv-actions .tool:nth-child(3n) ha-icon,:host([fitness-animations]) .music-button-strip>*:nth-child(3n) ha-icon{animation-delay:-4.0s}
      :host([fitness-live-ambient][fitness-animations]) .tv-toolbar .tool ha-icon,:host([fitness-live-ambient][fitness-animations]) .tv-toolbar .icon-tool ha-icon{animation-duration:calc(var(--fitness-motion-speed,6s) * 1.04)}
      :host([fitness-animations]) .fitness-brand-icon{animation:fitness-brand-breathe 5.4s ease-in-out infinite;transform-origin:center}
      :host([fitness-animations]) .media-art{animation:fitness-media-alive 4.5s ease-in-out infinite}
      :host([fitness-live-ambient][fitness-animations]) .media-art{animation-duration:calc(var(--fitness-motion-speed,6s) * .82);box-shadow:0 0 16px rgba(var(--fitness-tv-ambient-rgb,3,169,244),var(--fitness-energy-alpha,.28))}
      :host([fitness-live-ambient][fitness-animations]) .media-progress-wrap input{filter:drop-shadow(0 0 5px rgba(var(--fitness-tv-ambient-rgb,3,169,244),.45));animation:fitness-progress-energy calc(var(--fitness-motion-speed,6s) * .74) ease-in-out infinite}
      @keyframes fitness-card-breathe{0%,100%{translate:0 0;scale:1}42%{translate:0 calc(-.72 * var(--fitness-motion-lift,2px));scale:calc(1 + ((var(--fitness-card-breath-scale,1.009) - 1) * .64))}56%{translate:0 calc(-1 * var(--fitness-motion-lift,2px));scale:var(--fitness-card-breath-scale,1.009)}74%{translate:0 calc(-.28 * var(--fitness-motion-lift,2px));scale:calc(1 + ((var(--fitness-card-breath-scale,1.009) - 1) * .28))}}@keyframes fitness-card-life-pulse{0%,9%{transform:translateX(-55%) scaleX(.4);opacity:0}20%{opacity:.18}49%{opacity:.56}77%{opacity:.17}91%,100%{transform:translateX(390%) scaleX(.78);opacity:0}}@keyframes fitness-card-aura{0%,100%{opacity:.18;filter:saturate(.92)}50%{opacity:.54;filter:saturate(1.16)}}@keyframes fitness-toolbar-alive{0%,100%{translate:0 0;scale:1;filter:brightness(1)}50%{translate:0 -1px;scale:1.001;filter:brightness(1.022)}}@keyframes fitness-tool-icon-alive{0%,100%{transform:translateY(0) scale(1);filter:brightness(1)}48%{transform:translateY(-1px) scale(1.045);filter:brightness(1.07)}60%{transform:translateY(-.35px) scale(1.018);filter:brightness(1.025)}}@keyframes fitness-brand-breathe{0%,100%{transform:scale(1);filter:brightness(1)}50%{transform:scale(1.035);filter:brightness(1.055)}}@keyframes fitness-media-alive{0%,100%{scale:1;translate:0 0;filter:brightness(1)}50%{scale:1.028;translate:0 -1px;filter:brightness(1.055)}}@keyframes fitness-progress-energy{0%,100%{opacity:.88}50%{opacity:1}}
      @media(prefers-reduced-motion:reduce){.fitness-ambient-layer i{animation:none!important}:host([fitness-animations]) .tv-toolbar ha-icon,:host([fitness-animations]) .fitness-brand-icon,:host([fitness-animations]) .media-art,:host([fitness-animations]) .media-progress-wrap input{animation:none!important;translate:none!important;scale:1!important;transform:none!important}}
      .tool,.icon-tool,.media-tool,.adapter-setup,.cast-now,.cast-stop{border-radius:15px;transition:border-color .13s ease,background .13s ease,box-shadow .13s ease}.tool:hover,.icon-tool:hover,.media-tool:hover,.adapter-setup:hover,.cast-now:hover,.cast-stop:hover{transform:none;border-color:color-mix(in srgb,var(--primary-color) 40%,var(--divider-color));box-shadow:0 3px 10px rgba(0,0,0,.10)}
      .tool>span,.primary-tool>span,.adapter-setup>span,.flow-home>span{font-size:clamp(11px,.76vw,13px);line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;word-break:normal;overflow-wrap:normal}
      .modal-backdrop{background:rgba(0,0,0,.54);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}.modal-card{border-radius:28px;border-color:color-mix(in srgb,var(--divider-color) 72%,transparent);box-shadow:0 28px 90px rgba(0,0,0,.48)}.modal-head{padding:16px 18px;background:color-mix(in srgb,var(--card-background-color) 96%,transparent);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}
      .picker-row,.media-open,.provider-catalog-row,.music-adapter-row,.setting-toggle,.setting-field,.setting-range,.setting-info,.setting-adapters,.browser-working,.browser-warning{border-radius:18px;border:1px solid color-mix(in srgb,var(--divider-color) 72%,transparent);background:color-mix(in srgb,var(--secondary-background-color) 94%,var(--card-background-color));transition:transform .16s ease,border-color .16s ease,background .16s ease,box-shadow .16s ease}.picker-row:hover,.media-open:not(:disabled):hover,.provider-catalog-row:hover,.music-adapter-row:hover{transform:translateY(-1px);border-color:color-mix(in srgb,var(--primary-color) 34%,var(--divider-color));box-shadow:0 8px 20px rgba(0,0,0,.09)}
      .media-art,.media-thumb{border-radius:14px}.adapter-account,select{border-radius:14px}.layout-tools{border-radius:15px}
      /* Every Fitness TV menu keeps its controls visible while its body scrolls. */
      .modal-card{overflow:hidden!important;display:flex;flex-direction:column;min-height:0;overscroll-behavior:contain}
      .configure-modal{height:min(860px,calc(100dvh - var(--modal-top,68px) - 26px));max-height:calc(100dvh - var(--modal-top,68px) - 26px)}
      .configure-modal>.profile-settings{flex:1 1 auto;min-height:0;overflow-y:auto!important;overflow-x:hidden!important;scrollbar-gutter:stable;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
      .configure-modal>.settings-actions{flex:0 0 auto;position:relative!important;bottom:auto!important}
      .modal-auto-scroll-body{flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch}
      .modal-card.music-search-modal{display:flex;flex-direction:column;min-height:0;height:min(820px,calc(100dvh - var(--modal-top,68px) - 26px));max-height:calc(100dvh - var(--modal-top,68px) - 26px);overflow:hidden!important}
      .modal-card.music-search-modal .music-search-form{display:flex;flex:1 1 auto;min-height:0;overflow-y:auto!important;overflow-x:hidden!important;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch;flex-direction:column}
      .modal-card.music-search-modal .music-adapter-picker{flex:0 0 auto;min-height:auto;overflow:visible!important;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;touch-action:pan-y;-webkit-overflow-scrolling:touch}
      .modal-head{position:sticky!important;top:0;z-index:30;flex:0 0 auto;border-bottom:1px solid color-mix(in srgb,var(--divider-color) 72%,transparent)}
      .modal-actions,.settings-actions{position:sticky;bottom:0;z-index:24;padding:12px 14px;background:color-mix(in srgb,var(--card-background-color) 96%,transparent);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border-top:1px solid color-mix(in srgb,var(--divider-color) 68%,transparent)}
      .modal-scroll-body{min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;padding:14px}
      .remote-gateway-modal>.remote-gateway-body,.configure-modal>.profile-settings,.picker-modal>.picker-list,.cast-modal>.cast-picker,.provider-catalog-modal>.provider-catalog-list,.access-admin-modal>.access-admin-body{flex:1 1 auto;min-height:0;overflow-y:auto!important;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch}
      .browser-working[hidden],.browser-empty[hidden],.music-search-working[hidden],[hidden]{display:none!important}
      .music-search-status{display:flex;align-items:center;gap:7px;margin:-7px 14px 2px;padding:4px 2px!important;border:0!important;background:transparent!important;font-size:11px;color:var(--secondary-text-color)}.music-search-status ha-icon{--mdc-icon-size:16px;color:var(--primary-color)}
      .music-adapter-search-group{display:grid;gap:6px}.music-provider-scopes{display:grid;gap:5px;margin:0 0 4px 34px;padding-left:10px;border-left:2px solid color-mix(in srgb,var(--primary-color) 28%,var(--divider-color))}.music-provider-scope-row{display:grid;grid-template-columns:22px 20px minmax(0,1fr);gap:8px;align-items:center;padding:8px 10px;border-radius:14px;background:color-mix(in srgb,var(--card-background-color) 74%,transparent);border:1px solid color-mix(in srgb,var(--divider-color) 60%,transparent)}.music-provider-scope-row ha-icon{--mdc-icon-size:19px;color:var(--primary-color)}.music-provider-scope-row input{width:17px;height:17px}.music-provider-scope-row strong,.music-provider-scope-row small{display:block}.music-provider-scope-row small{font-size:9px;color:var(--secondary-text-color);margin-top:2px}.music-provider-busy-note{display:flex;gap:6px;align-items:center;margin:0 0 4px 44px;font-size:10px;color:var(--secondary-text-color)}.music-provider-busy-note ha-icon{--mdc-icon-size:15px;color:var(--warning-color,#ff9800)}
      .ytdlp-legal-modal{height:min(760px,calc(100dvh - 32px))}.ytdlp-legal-body{display:grid;gap:12px}.ytdlp-legal-body .browser-warning{display:grid;grid-template-columns:26px minmax(0,1fr);gap:10px;line-height:1.5}.provider-catalog-ytdlp{border-color:color-mix(in srgb,var(--warning-color,#ff9800) 28%,var(--divider-color))}
      .overview-cast-target.unavailable{opacity:.48;filter:grayscale(.82);cursor:not-allowed}.overview-cast-target.unavailable:hover{transform:none;box-shadow:none;border-color:var(--divider-color)}
      :host([fitness-cast-receiver]) ha-card.tv-shell{padding:5px 7px 7px}
      :host([fitness-cast-receiver]) .fitness-ambient-layer i{filter:blur(46px);will-change:opacity}:host([fitness-cast-receiver]) .fitness-ambient-layer i:nth-child(3),:host([fitness-cast-receiver]) .fitness-ambient-layer i:nth-child(4){display:none}:host([fitness-cast-receiver][fitness-animations]) .fitness-ambient-layer i:nth-child(1),:host([fitness-cast-receiver][fitness-animations]) .fitness-ambient-layer i:nth-child(2){animation:fitness-cast-ambient-pulse 7s ease-in-out infinite alternate}:host([fitness-cast-receiver][fitness-animations]) .fitness-ambient-layer i:nth-child(2){animation-delay:-3.5s}@keyframes fitness-cast-ambient-pulse{from{opacity:.68}to{opacity:.93}}
      :host([fitness-cast-receiver][fitness-animations]) .tv-toolbar .tool ha-icon,:host([fitness-cast-receiver][fitness-animations]) .tv-toolbar .icon-tool ha-icon,:host([fitness-cast-receiver][fitness-animations]) .fitness-brand-icon,:host([fitness-cast-receiver][fitness-animations]) .media-art{animation:none!important;transform:none!important;filter:none!important}
      :host([fitness-cast-receiver]) .tv-toolbar{grid-template-columns:auto minmax(76px,120px) auto minmax(180px,1fr);gap:5px;margin-bottom:11px;padding:5px 7px;border-radius:13px;transition:opacity .35s ease;overflow:visible}
      :host([fitness-cast-receiver]) .tv-brand{font-size:13px;gap:3px}
      :host([fitness-cast-receiver]) .tv-brand .fitness-brand-icon{width:18px;height:18px;flex-basis:18px}
      :host([fitness-cast-receiver]) .tv-profile-identity{gap:3px;max-width:120px}
      :host([fitness-cast-receiver]) .tv-profile-identity ha-icon{display:none}
      :host([fitness-cast-receiver]) .tv-profile-identity span{font-size:9px;font-weight:650;color:var(--primary-text-color)}
      :host([fitness-cast-receiver]) .profile-control{gap:3px}
      :host([fitness-cast-receiver]) .profile-control span{display:none}
      :host([fitness-cast-receiver]) .tv-actions{grid-column:auto;grid-template-columns:repeat(4,34px);justify-content:flex-start;gap:4px;overflow:visible}
      :host([fitness-cast-receiver]) select,:host([fitness-cast-receiver]) .tool,:host([fitness-cast-receiver]) .icon-tool{min-height:34px;border-radius:8px;font-size:10px}
      :host([fitness-cast-receiver]) .tv-toolbar .tool{width:34px;min-width:34px;max-width:34px;padding:0;gap:0}
      :host([fitness-cast-receiver]) .icon-tool{width:34px;min-width:34px;padding:0;gap:0}
      :host([fitness-cast-receiver]) .tv-toolbar button>span{display:none!important}
      :host([fitness-cast-receiver]) .tool ha-icon,:host([fitness-cast-receiver]) .icon-tool ha-icon{--mdc-icon-size:18px}
      :host([fitness-cast-receiver]) .music-controls{grid-column:auto;grid-template-columns:auto minmax(90px,1fr);gap:4px}:host([fitness-cast-receiver]) .music-button-strip{gap:3px;flex-wrap:wrap}
      :host([fitness-cast-receiver]) .media-now{grid-template-columns:28px minmax(0,1fr);gap:4px;padding-left:1px}
      :host([fitness-cast-receiver]) .media-art{width:28px;height:28px;border-radius:5px}
      :host([fitness-cast-receiver]) .media-art ha-icon{--mdc-icon-size:16px}
      :host([fitness-cast-receiver]) .media-copy small{font-size:8px}
      :host([fitness-cast-receiver]) .media-copy strong{font-size:10px}
      :host([fitness-cast-receiver]) .media-copy span{font-size:8px}
      :host([fitness-cast-receiver]) .media-now-main,:host([fitness-cast-receiver]) .media-copy{width:min(300px,100%);max-width:300px}
      :host([fitness-cast-receiver]) .media-progress-wrap{gap:3px;margin-top:1px;font-size:8px;width:min(300px,100%);max-width:300px}
      :host([fitness-cast-receiver]) .media-progress-wrap input{height:12px}
      :host([fitness-cast-receiver]) .tv-oled-stage{width:calc(100% - 4px);margin:2px;transition:transform .8s ease;will-change:transform}
      :host([fitness-cast-receiver]) .tv-grid{--tv-columns:3;column-gap:6px}
      :host([fitness-cast-receiver]) .tv-card-slot>.tv-mounted-card{position:absolute;top:0;left:0;width:calc(100% / var(--fitness-tv-card-scale,.70));transform:scale(var(--fitness-tv-card-scale,.70));transform-origin:top left}
      :host([oled-protection][fitness-cast-receiver]) .tv-oled-stage{transform:translate3d(var(--fitness-oled-x,0),var(--fitness-oled-y,0),0)}
      :host([oled-idle][fitness-cast-receiver]) .tv-toolbar{opacity:.34}
      @media(max-width:1600px){:host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile .tv-actions{grid-template-columns:repeat(auto-fit,minmax(94px,1fr))}:host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile .tv-actions .tool{width:auto;padding:5px 8px}}
      @media(max-width:1500px){:host(:not([fitness-cast-receiver])) .tv-grid{--tv-columns:3}}
      @media(max-width:1250px){:host(:not([fitness-cast-receiver])) .tv-toolbar:not(.fixed-profile){grid-template-columns:auto minmax(180px,260px) 1fr}:host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile{grid-template-columns:auto minmax(0,1fr);grid-template-areas:"brand identity" "actions actions" "music music"}:host(:not([fitness-cast-receiver])) .tv-toolbar.fixed-profile .tv-actions{justify-content:flex-start}.music-controls{grid-column:1/-1}:host(:not([fitness-cast-receiver])) .tv-grid{--tv-columns:2}}
      @media(max-width:900px){:host([fitness-cast-receiver]) .tv-grid{--tv-columns:2}:host([fitness-cast-receiver]) .tv-toolbar{grid-template-columns:auto minmax(110px,160px) 1fr}}
      @media(max-width:760px){:host(:not([fitness-cast-receiver])) .tv-grid{--tv-columns:1}:host(:not([fitness-cast-receiver])) .tv-toolbar{grid-template-columns:1fr;gap:8px}.profile-control,.tv-actions,.music-controls{grid-column:1}.music-controls{grid-template-columns:1fr}.music-button-strip{grid-column:1;flex-wrap:wrap}.media-now{grid-column:1}.picker-list{grid-template-columns:1fr}.cast-picker{grid-template-columns:1fr}.cast-now,.cast-stop{width:100%}.setting-field,.setting-range{grid-template-columns:1fr}.setting-range output{text-align:left}.access-intro{align-items:stretch;flex-direction:column}.access-domain-row,.access-user-row{grid-template-columns:1fr}.access-user-actions,.access-url{grid-column:1}}
      /* Cross-device reliability overrides. Keep the existing card breakpoints and DOM order above. */
      :host([fitness-cast-receiver]){height:100dvh}
      .tool:focus-visible,.icon-tool:focus-visible,.primary-tool:focus-visible,.adapter-setup:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
      .modal-backdrop{--modal-effective-top:min(var(--modal-top,68px),max(6px,calc(100dvh - 180px)));top:var(--modal-effective-top);padding-left:max(8px,env(safe-area-inset-left));padding-right:max(8px,env(safe-area-inset-right));padding-bottom:max(12px,env(safe-area-inset-bottom))}
      .modal-card{max-height:calc(100dvh - var(--modal-effective-top) - max(12px,env(safe-area-inset-bottom)))}
      .backend-flow-modal,.remote-gateway-modal,.configure-modal,.music-search-modal{max-height:calc(100dvh - var(--modal-effective-top) - max(12px,env(safe-area-inset-bottom)))}
      @media(max-width:900px){
        :host([fitness-cast-receiver]) .tv-toolbar{grid-template-columns:auto minmax(110px,160px) minmax(0,1fr);grid-template-areas:"brand profile actions" "music music music"}
        :host([fitness-cast-receiver]) .tv-brand{grid-area:brand}
        :host([fitness-cast-receiver]) .profile-control,:host([fitness-cast-receiver]) .tv-profile-identity{grid-area:profile}
        :host([fitness-cast-receiver]) .tv-actions{grid-area:actions}
        :host([fitness-cast-receiver]) .music-controls{grid-area:music;width:100%;grid-template-columns:auto minmax(90px,1fr)}
      }
      @media(max-width:760px){
        :host(:not([fitness-cast-receiver])) .tv-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(44px,1fr));gap:6px;width:100%}
        :host(:not([fitness-cast-receiver])) .tool,:host(:not([fitness-cast-receiver])) .icon-tool,:host(:not([fitness-cast-receiver])) .primary-tool{min-height:44px}
        :host(:not([fitness-cast-receiver])) input:not([type="checkbox"]):not([type="range"]),:host(:not([fitness-cast-receiver])) select{font-size:16px}
        .setting-adapters-head{display:grid;grid-template-columns:1fr}.setting-adapters-head .adapter-setup{width:100%;max-width:none;white-space:normal;min-height:44px}
        .music-adapter-row{grid-template-columns:22px 24px minmax(0,1fr)}
        .adapter-actions{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}
        .adapter-actions>*{width:100%;min-width:0;max-width:none;min-height:44px}.adapter-actions .adapter-account{grid-column:1/-1;min-width:0;max-width:none}
        .provider-catalog-row{grid-template-columns:30px minmax(0,1fr)}.provider-catalog-row>.adapter-setup{grid-column:1/-1;width:100%;max-width:none;min-width:0;min-height:44px}
        :host([fitness-cast-receiver]) .tv-brand{grid-area:brand}
        :host([fitness-cast-receiver]) .profile-control,:host([fitness-cast-receiver]) .tv-profile-identity{grid-area:profile;grid-column:auto}
        :host([fitness-cast-receiver]) .tv-actions{grid-area:actions;grid-column:auto}
        :host([fitness-cast-receiver]) .music-controls{grid-area:music;grid-column:auto}
      }
      @media(max-width:520px){
        :host([fitness-cast-receiver]) .tv-toolbar{grid-template-columns:auto minmax(0,1fr);grid-template-areas:"brand profile" "actions actions" "music music"}
        :host([fitness-cast-receiver]) .tv-actions{justify-content:flex-start;flex-wrap:wrap}
        .setting-adapters-head{display:grid;grid-template-columns:1fr}.setting-adapters-head .adapter-setup{width:100%;white-space:normal;min-height:44px}
        .music-adapter-row{grid-template-columns:22px 24px minmax(0,1fr)}
        .adapter-actions{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}
        .adapter-actions>*{width:100%;max-width:none;min-height:44px}.adapter-actions .adapter-account{grid-column:1/-1;max-width:none}
        .provider-catalog-row{grid-template-columns:30px minmax(0,1fr)}.provider-catalog-row>.adapter-setup{grid-column:1/-1;width:100%;min-height:44px}
      }
    </style>`;
  }
}


const FITNESS_FLOW_MENU_ICONS = Object.freeze({
  profile:"mdi:account-edit-outline",
  fitness_inputs:"mdi:heart-pulse",
  live_devices:"mdi:access-point",
  workout_devices:"mdi:run-fast",
  sleep_devices:"mdi:sleep",
  ai:"mdi:robot-outline",
  feedback:"mdi:message-bulleted",
  tv_dashboard:"mdi:television",
  sensor_assignments:"mdi:transit-connection-variant",
});

class FitnessBackendFlow extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this._flow = null;
    this._formData = {};
    this._busy = false;
    this._returnToMenuAfterSave = false;
    this._fitnessOptionsFlow = false;
  }

  set hass(hass) { this._hass = hass; }

  async start({mode = "options", entryId = "", profileName = "", uiLabels = {}, language = ""} = {}) {
    this._mode = mode;
    this._entryId = entryId;
    this._profileName = profileName;
    this._uiLabels = uiLabels || {};
    this._language = String(language || this._hass?.language || "en");
    this._renderLoading();
    try {
      try {
        this._flowTranslations = await this._hass.callWS({
          type:"fitness/dashboard/flow_translations",
          language:this._language,
        });
      } catch (_err) {
        this._flowTranslations = {};
      }
      this._fitnessOptionsFlow = mode !== "add";
      if (mode === "add") {
        this._flowBase = "config/config_entries/flow";
        this._flow = await this._hass.callApi("POST", this._flowBase, {
          handler:"fitness",
          show_advanced_options:false,
        });
      } else {
        this._flowBase = "";
        this._flow = await this._hass.callWS({
          type:"fitness/dashboard/options_flow/start",
          profile_entry_id:entryId,
        });
      }
      await this._renderFlow();
    } catch (err) {
      console.error("[Fitness] unable to open settings flow", err);
      this._renderError(this._uiLabels?.error_open_fitness_settings);
    }
  }

  async cancel() {
    const flowId = this._flow?.flow_id;
    if (flowId) {
      try {
        if (this._fitnessOptionsFlow) {
          await this._hass?.callWS?.({
            type:"fitness/dashboard/options_flow/cancel",
            profile_entry_id:this._entryId,
            flow_id:flowId,
          });
        } else if (this._flowBase) {
          await this._hass?.callApi?.("DELETE", `${this._flowBase}/${flowId}`);
        }
      } catch (_err) {}
    }
    this.dispatchEvent(new CustomEvent("fitness-flow-close", {bubbles:true, composed:true}));
  }

  _localize(key, fallback, replacements = undefined) {
    try {
      const prefix = "component.fitness.";
      const parts = String(key || "").startsWith(prefix)
        ? String(key).slice(prefix.length).split(".")
        : [];
      let value = this._flowTranslations;
      for (const part of parts) value = value?.[part];
      if (typeof value === "string" && value) {
        if (replacements && typeof replacements === "object") {
          return value.replace(/\{([^}]+)\}/g, (_m, name) => replacements[name] ?? `{${name}}`);
        }
        return value;
      }
    } catch (_err) {}
    // Only fall back to Home Assistant's own localizer when the requested
    // profile language is the current frontend language. Otherwise that would
    // silently replace the user's Fitness language with the browser/UI language.
    const requested = String(this._language || "en").toLowerCase().split("-")[0];
    const ui = String(this._hass?.language || "en").toLowerCase().split("-")[0];
    if (requested === ui) {
      try {
        const value = this._hass?.localize?.(key, replacements);
        if (value && value !== key) return value;
      } catch (_err) {}
    }
    return fallback;
  }

  _flowNamespace() {
    return this._mode === "add" ? "config" : "options";
  }

  _stepTitle(step) {
    const section = this._flowNamespace();
    const id = String(step?.step_id || "user");
    const fallback = this._mode === "add"
      ? this._uiLabels?.add_fitness_user
      : (this._profileName ? `${this._uiLabels?.backend_settings} · ${this._profileName}` : this._uiLabels?.backend_settings);
    return this._localize(`component.fitness.${section}.step.${id}.title`, fallback, step?.description_placeholders);
  }

  _stepDescription(step) {
    const section = this._flowNamespace();
    const id = String(step?.step_id || "user");
    return this._localize(`component.fitness.${section}.step.${id}.description`, "", step?.description_placeholders);
  }

  _fieldLabel(step, schema) {
    const section = this._flowNamespace();
    const id = String(step?.step_id || "user");
    const name = String(schema?.name || "");
    return this._localize(
      `component.fitness.${section}.step.${id}.data.${name}`,
      name.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    );
  }

  _fieldHelper(step, schema) {
    const section = this._flowNamespace();
    const id = String(step?.step_id || "user");
    const name = String(schema?.name || "");
    return this._localize(`component.fitness.${section}.step.${id}.data_description.${name}`, "");
  }

  _errorText(step) {
    const errors = step?.errors || {};
    const keys = Object.entries(errors);
    if (!keys.length) return "";
    const section = this._flowNamespace();
    const stepId = String(step?.step_id || "user");
    return keys.map(([field, code]) => {
      const base = field === "base";
      const translated = this._localize(
        `component.fitness.${section}.error.${code}`,
        this._localize(`component.fitness.${section}.step.${stepId}.error.${code}`, String(code)),
      );
      return base ? translated : `${this._fieldLabel(step, {name:field})}: ${translated}`;
    }).join(" · ");
  }

  _initialFormData(step) {
    const result = {};
    for (const field of step?.data_schema || []) {
      if (!field?.name) continue;
      if (field.default !== undefined) result[field.name] = field.default;
      else if (field.description?.suggested_value !== undefined) result[field.name] = field.description.suggested_value;
    }
    return result;
  }

  _localizedSchema(step) {
    return (step?.data_schema || []).map((raw) => {
      const field = globalThis.structuredClone ? structuredClone(raw) : JSON.parse(JSON.stringify(raw));
      const select = field?.selector?.select;
      const translationKey = String(select?.translation_key || "");
      const translated = this._flowTranslations?.selector?.[translationKey]?.options || {};
      if (translationKey && Array.isArray(select?.options)) {
        select.options = select.options.map((option) => {
          const value = typeof option === "object" && option !== null ? String(option.value ?? "") : String(option);
          const result = typeof option === "object" && option !== null ? {...option} : {value};
          if (translated?.[value]) result.label = translated[value];
          return result;
        });
      }
      return field;
    });
  }

  _shell(body, {title = "", description = "", error = ""} = {}) {
    const showMain = this._mode !== "add" && String(this._flow?.step_id || "init") !== "init";
    const mainLabel = this._uiLabels?.settings_main_menu;
    const closeLabel = this._uiLabels?.close;
    this.shadowRoot.innerHTML = `<div class="flow-shell">
      <div class="flow-head"><div><strong>${_fitnessEscape(title)}</strong>${description ? `<p>${_fitnessEscape(description)}</p>` : ""}</div><div class="flow-head-actions">${showMain ? `<button class="flow-home" title="${_fitnessEscape(mainLabel)}"><ha-icon icon="mdi:view-dashboard-outline"></ha-icon><span>${_fitnessEscape(mainLabel)}</span></button>` : ""}<button class="flow-close" title="${_fitnessEscape(closeLabel)}" aria-label="${_fitnessEscape(closeLabel)}"><ha-icon icon="mdi:close"></ha-icon></button></div></div>
      ${error ? `<div class="flow-error">${_fitnessEscape(error)}</div>` : ""}
      <div class="flow-body">${body}</div>
    </div>${this._style()}`;
    this.shadowRoot.querySelector(".flow-close")?.addEventListener("click", () => this.cancel());
    this.shadowRoot.querySelector(".flow-home")?.addEventListener("click", () => this._saveAndReturnToMenu());
    const shell = this.shadowRoot.querySelector(".flow-shell");
    const flowBody = this.shadowRoot.querySelector(".flow-body");
    shell?.addEventListener("wheel", (event) => {
      if (!flowBody || flowBody.contains(event.target)) return;
      if (Math.abs(Number(event.deltaY || 0)) > 0) {
        flowBody.scrollTop += Number(event.deltaY || 0);
        event.preventDefault();
      }
      event.stopPropagation();
    }, {passive:false});
  }

  async _restartOptionsFlow() {
    if (this._mode === "add") return;
    const flowId = this._flow?.flow_id;
    if (flowId) {
      try {
        if (this._fitnessOptionsFlow) {
          await this._hass?.callWS?.({
            type:"fitness/dashboard/options_flow/cancel",
            profile_entry_id:this._entryId,
            flow_id:flowId,
          });
        } else if (this._flowBase) {
          await this._hass?.callApi?.("DELETE", `${this._flowBase}/${flowId}`);
        }
      } catch (_err) {}
    }
    await this.start({
      mode:"options",
      entryId:this._entryId,
      profileName:this._profileName,
      uiLabels:this._uiLabels,
      language:this._language,
    });
  }

  async _saveAndReturnToMenu() {
    if (this._mode === "add" || this._busy) return;
    if (String(this._flow?.type || "") === "form") {
      this._returnToMenuAfterSave = true;
      await this._submit(this._formData);
      return;
    }
    await this._restartOptionsFlow();
  }

  _renderLoading() {
    this._shell(`<div class="flow-loading"><ha-circular-progress active></ha-circular-progress><span>${_fitnessEscape(this._uiLabels?.loading)}</span></div>`, {
      title:this._mode === "add"
        ? (this._uiLabels?.add_fitness_user)
        : (this._uiLabels?.backend_settings),
    });
  }

  _renderError(message) {
    this._shell(`<div class="flow-message"><ha-icon icon="mdi:alert-circle-outline"></ha-icon><span>${_fitnessEscape(message)}</span></div>`, {
      title:this._mode === "add"
        ? (this._uiLabels?.add_fitness_user)
        : (this._uiLabels?.backend_settings),
    });
  }

  async _submit(data) {
    if (this._busy || !this._flow?.flow_id) return;
    this._busy = true;
    const submit = this.shadowRoot.querySelector("#flow-submit");
    if (submit) submit.disabled = true;
    try {
      if (this._fitnessOptionsFlow) {
        this._flow = await this._hass.callWS({
          type:"fitness/dashboard/options_flow/step",
          profile_entry_id:this._entryId,
          flow_id:this._flow.flow_id,
          user_input:data || {},
        });
      } else {
        this._flow = await this._hass.callApi("POST", `${this._flowBase}/${this._flow.flow_id}`, data || {});
      }
      await this._renderFlow();
    } catch (err) {
      console.error("[Fitness] unable to save settings flow", err);
      this._renderError(this._uiLabels?.error_save_fitness_settings);
    } finally {
      this._busy = false;
    }
  }

  async _refreshProgress() {
    if (!this._flow?.flow_id) return;
    await new Promise((resolve) => setTimeout(resolve, 750));
    try {
      if (this._fitnessOptionsFlow) {
        this._flow = await this._hass.callWS({
          type:"fitness/dashboard/options_flow/step",
          profile_entry_id:this._entryId,
          flow_id:this._flow.flow_id,
        });
      } else {
        this._flow = await this._hass.callApi("GET", `${this._flowBase}/${this._flow.flow_id}`);
      }
      await this._renderFlow();
    } catch (err) {
      console.error("[Fitness] unable to continue settings flow", err);
      this._renderError(this._uiLabels?.error_continue_fitness_setup);
    }
  }

  async _renderFlow() {
    const step = this._flow || {};
    const type = String(step.type || "");
    const title = this._stepTitle(step);
    const description = this._stepDescription(step);
    const error = this._errorText(step);

    if (type === "menu") {
      const section = this._flowNamespace();
      const stepId = String(step.step_id || "init");
      const rows = (step.menu_options || []).map((option) => {
        const label = this._localize(`component.fitness.${section}.step.${stepId}.menu_options.${option}`, String(option).replaceAll("_", " "));
        const icon = FITNESS_FLOW_MENU_ICONS[option] || "mdi:cog-outline";
        return `<button class="flow-menu" data-next="${_fitnessEscape(option)}"><ha-icon class="flow-menu-icon" icon="${_fitnessEscape(icon)}"></ha-icon><span>${_fitnessEscape(label)}</span><ha-icon icon="mdi:chevron-right"></ha-icon></button>`;
      }).join("");
      this._shell(rows || `<div class="flow-message">${_fitnessEscape(this._uiLabels?.no_settings_available)}</div>`, {title, description, error});
      this.shadowRoot.querySelectorAll(".flow-menu").forEach((button) => button.addEventListener("click", () => this._submit({next_step_id:button.dataset.next})));
      return;
    }

    if (type === "form") {
      this._formData = this._initialFormData(step);
      const submitLabel = this._mode === "options" || step.last_step ? (this._uiLabels?.save) : (this._uiLabels?.next);
      this._shell(`<ha-form id="flow-form"></ha-form><div class="flow-actions"><button class="flow-submit" id="flow-submit"><span>${_fitnessEscape(submitLabel)}</span></button></div>`, {title, description, error});
      const form = this.shadowRoot.querySelector("#flow-form");
      if (form) {
        form.hass = this._hass;
        form.schema = this._localizedSchema(step);
        form.data = {...this._formData};
        form.error = step.errors || {};
        form.computeLabel = (schema) => this._fieldLabel(step, schema);
        form.computeHelper = (schema) => this._fieldHelper(step, schema);
        form.addEventListener("value-changed", (ev) => { this._formData = {...(ev.detail?.value || {})}; });
      }
      this.shadowRoot.querySelector("#flow-submit")?.addEventListener("click", () => this._submit(this._formData));
      return;
    }

    if (type === "create_entry") {
      if (this._mode === "options" && this._returnToMenuAfterSave) {
        this._returnToMenuAfterSave = false;
        await this._restartOptionsFlow();
        return;
      }
      const successText = this._mode === "add"
        ? (this._uiLabels?.add_fitness_user)
        : (this._uiLabels?.saved);
      this._shell(`<div class="flow-success"><ha-icon icon="mdi:check-circle-outline"></ha-icon><strong>${_fitnessEscape(successText)}</strong></div>`, {title});
      this.dispatchEvent(new CustomEvent("fitness-flow-complete", {detail:{mode:this._mode, result:step.result || null}, bubbles:true, composed:true}));
      if (this._mode === "options") {
        setTimeout(() => this._restartOptionsFlow(), 350);
      } else {
        setTimeout(() => this.dispatchEvent(new CustomEvent("fitness-flow-close", {bubbles:true, composed:true})), 650);
      }
      return;
    }

    if (type === "abort") {
      const reason = String(step.reason || "unknown");
      const section = this._flowNamespace();
      const message = this._localize(`component.fitness.${section}.abort.${reason}`, this._uiLabels?.flow_error_unknown, step.description_placeholders);
      this._shell(`<div class="flow-message"><ha-icon icon="mdi:information-outline"></ha-icon><span>${_fitnessEscape(message)}</span></div>`, {title});
      return;
    }

    if (type === "progress" || type === "progress_done") {
      this._shell(`<div class="flow-loading"><ha-circular-progress active></ha-circular-progress><span>${_fitnessEscape(description || this._uiLabels?.working)}</span></div>`, {title});
      this._refreshProgress();
      return;
    }

    if (type === "external") {
      this._shell(`<div class="flow-message"><ha-icon icon="mdi:open-in-new"></ha-icon><a href="${_fitnessEscape(step.url || "#")}" target="_blank" rel="noopener">${_fitnessEscape(this._uiLabels?.continue_setup)}</a></div>`, {title, description});
      return;
    }

    this._renderError(_fitnessFormatLabel(this._uiLabels?.unsupported_flow_step, {type:type || "—"}));
  }

  _style() {
    return `<style>
      .flow-home>span,.flow-submit>span,.flow-menu>span{display:block!important;min-width:0;max-width:100%;font-size:clamp(11px,1vw,13px)!important;line-height:1.2!important;white-space:nowrap!important;overflow:hidden;text-overflow:ellipsis;word-break:normal;overflow-wrap:normal!important}
      .flow-menu{grid-template-columns:auto minmax(0,1fr) auto!important;min-height:44px}
      @media(max-width:620px){.flow-head{align-items:flex-start!important;flex-wrap:wrap}.flow-head>div:first-child{flex:1 1 180px}.flow-home{width:auto!important;min-width:112px!important;padding:0 10px!important}.flow-home span{display:block!important}}
      :host{display:block;color:var(--primary-text-color);height:100%;max-height:100%;min-height:0;overflow:hidden}*{box-sizing:border-box}.flow-shell{width:100%;height:100%;max-height:100%;min-height:0;display:flex;flex-direction:column;overflow:hidden}.flow-head{flex:0 0 auto;position:sticky;top:0;z-index:3;display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:14px 16px;background:var(--card-background-color);border-bottom:1px solid var(--divider-color)}.flow-head strong{font-size:18px}.flow-head p{margin:5px 0 0;color:var(--secondary-text-color);font-size:12px;max-width:620px}.flow-head-actions{display:flex;align-items:center;gap:7px;flex:0 0 auto}.flow-close,.flow-home{min-height:40px;display:inline-flex;align-items:center;justify-content:center;gap:6px;border:1px solid var(--divider-color);border-radius:11px;background:var(--secondary-background-color);color:var(--primary-text-color);cursor:pointer}.flow-close{width:40px;min-width:40px;flex:0 0 40px}.flow-home{min-width:126px;max-width:min(240px,45vw);padding:0 11px;font:inherit;white-space:nowrap;line-height:1}.flow-home ha-icon{--mdc-icon-size:20px;flex:0 0 auto}.flow-home>span,.flow-submit>span,.flow-menu>span{font-size:clamp(11px,1vw,13px);line-height:1.2;min-width:0;word-break:normal;overflow-wrap:normal}.flow-body{display:grid;gap:9px;padding:15px;overflow-y:auto;overflow-x:hidden;min-height:0;flex:1 1 auto;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch}.flow-error{flex:0 0 auto;margin:12px 15px 0;padding:10px 12px;border-radius:11px;background:color-mix(in srgb,var(--error-color) 12%,transparent);color:var(--error-color);font-size:12px}.flow-menu{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;width:100%;min-height:44px;padding:13px 14px;border:0;border-radius:12px;background:var(--secondary-background-color);color:var(--primary-text-color);font:inherit;text-align:left;cursor:pointer}.flow-menu-icon{--mdc-icon-size:21px;color:var(--primary-color)}.flow-menu:hover{background:color-mix(in srgb,var(--primary-color) 12%,var(--secondary-background-color))}.flow-actions{display:flex;justify-content:flex-end;gap:8px;padding-top:8px;flex-wrap:nowrap;min-width:0}.flow-actions>button{flex:1 1 0;min-width:0;max-width:100%}.flow-submit{min-width:110px;min-height:42px;border:0;border-radius:11px;padding:0 18px;background:var(--primary-color);color:var(--text-primary-color,#fff);font:inherit;font-weight:700;cursor:pointer}.flow-submit:disabled{opacity:.55}.flow-loading,.flow-message,.flow-success{min-height:100px;display:flex;align-items:center;justify-content:center;gap:10px;color:var(--secondary-text-color)}.flow-success{color:var(--success-color,#2e7d32)}.flow-success ha-icon{--mdc-icon-size:30px}.flow-message a{color:var(--primary-color)}ha-form{display:block}.flow-close:focus-visible,.flow-home:focus-visible,.flow-submit:focus-visible,.flow-menu:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}@media(max-width:620px){.flow-head{padding:12px}.flow-head>div:first-child{min-width:0}.flow-head strong{font-size:16px}.flow-home span{display:block}.flow-home,.flow-close,.flow-submit{min-height:44px}.flow-close{width:44px;min-width:44px;flex-basis:44px;padding:0}.flow-home{width:auto;min-width:112px;padding:0 10px}.flow-body{padding:12px}.flow-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.flow-actions>button{width:100%}}
    </style>`;
  }
}

if (!customElements.get("fitness-backend-flow")) customElements.define("fitness-backend-flow", FitnessBackendFlow);

class FitnessTvSetupCard extends HTMLElement {
  setConfig(config) {
    const previousProfile = String(this.config?.profile_entry_id || "");
    this.config = config || {};
    if (!this.shadowRoot) this.attachShadow({mode:"open"});
    const nextProfile = String(this.config?.profile_entry_id || "");
    if (previousProfile !== nextProfile) this._profileWrapperCard = null;
    if (this._hass && nextProfile) this._renderProfileWrapper();
  }

  set hass(hass) {
    this._hass = hass;
    if (String(this.config?.profile_entry_id || "")) {
      this._renderProfileWrapper();
      return;
    }
    if (!this._loaded && !this._loading) this._load();
  }

  _renderProfileWrapper() {
    if (!this.shadowRoot || !this._hass) return;
    const profileEntryId = String(this.config?.profile_entry_id || "");
    if (!profileEntryId) return;
    let card = this._profileWrapperCard;
    if (!card || card.dataset?.profileEntryId !== profileEntryId) {
      card = document.createElement(FITNESS_TV_DASHBOARD_CARD_TAG);
      card.dataset.profileEntryId = profileEntryId;
      card.setConfig({type:`custom:${FITNESS_TV_DASHBOARD_CARD_TAG}`, profile_entry_id:profileEntryId});
      this._profileWrapperCard = card;
      this.shadowRoot.replaceChildren(card);
    }
    card.hass = this._hass;
  }

  _labels(profile = this._profiles?.[0]) {
    const language = String(profile?.language || this._access?.language || this._hass?.language || "en").toLowerCase().split("-")[0];
    return profile?.labels_by_language?.[language]
      || profile?.labels_by_language?.en
      || profile?.labels
      || this._rootLabelsByLanguage?.[language]
      || this._rootLabelsByLanguage?.en
      || this._rootLabels
      || {};
  }

  _navigate(path) {
    const target = String(path || "").trim();
    if (!target) return;
    if (_fitnessOpenExternal(target)) return;
    try {
      history.pushState(null, "", target);
      window.dispatchEvent(new Event("location-changed"));
    } catch (_err) {
      window.location.href = target;
    }
  }

  async _load() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    try {
      const data = await this._hass.callWS({type:"fitness/dashboard/config"});
      if (_fitnessEnsureFrontendVersion(data?.frontend_version)) return;
      this._profiles = data?.profiles || [];
      this._access = data?.access || {role:"none",is_admin:false,session_allowed:false};
      this._rootLabels = data?.labels || {};
      this._rootLabelsByLanguage = data?.labels_by_language || {};
      this._castTargets = data?.cast_targets || [];
      this._overviewCast = data?.overview_cast || {active:false,target:null};
      this._audioOutputs = data?.audio_outputs || [];
      this._adminAccess = null;
      if (this._access?.is_admin) {
        try { this._adminAccess = await this._hass.callWS({type:"fitness/access/admin"}); } catch (_err) {}
      }
      this._error = "";
    } catch (err) {
      console.error("[Fitness TV] setup overview load failed", err);
      this._error = this._labels().flow_error_unknown;
    } finally {
      this._loading = false;
      this._loaded = true;
      this._render();
    }
  }

  _targetName(entityId) {
    if (!entityId) return "";
    return this._castTargets?.find((target) => target.entity_id === entityId)?.name || entityId;
  }

  _render() {
    if (!this.shadowRoot) return;
    const l = this._labels();
    const accessCopy = _fitnessAccessCopy(l);
    if (this._error) {
      this.shadowRoot.innerHTML = `<ha-card class="setup-shell"><div class="empty">${_fitnessEscape(this._error)}</div></ha-card>${this._style()}`;
      return;
    }
    const profiles = (this._profiles || []).filter((profile) => profile?.tv_dashboard?.enabled || this._access?.is_admin);
    const isAdmin = Boolean(this._access?.is_admin);

    if (!isAdmin) {
      if (!profiles.length) {
        this.shadowRoot.innerHTML = `<ha-card class="setup-shell"><div class="setup-access-denied"><ha-icon icon="mdi:shield-lock-outline"></ha-icon><div><strong>${_fitnessEscape(accessCopy.denied)}</strong><span>${_fitnessEscape(accessCopy.denied_hint)}</span></div></div></ha-card>${this._style()}`;
        return;
      }
      // The Fitness overview is an administrator surface. Non-admin users never
      // receive a list of other profiles here: sidebar navigation goes directly
      // to their own profile, or to the first explicitly granted view-only
      // profile when they do not own a Fitness profile. Additional view-only
      // profiles remain reachable only through their explicit profile URL.
      const destination = profiles.find((profile) => profile?.access?.is_own) || profiles[0];
      this.shadowRoot.innerHTML = `<ha-card class="setup-shell"><div class="setup-access-denied"><ha-icon icon="mdi:loading" class="spin"></ha-icon><div><strong>${_fitnessEscape(destination?.profile_name || l.tv_dashboard)}</strong><span>${_fitnessEscape(destination?.access?.can_control ? accessCopy.own : accessCopy.view_only)}</span></div></div></ha-card>${this._style()}`;
      if (!this._nonAdminRedirectPending && destination?.entry_id) {
        this._nonAdminRedirectPending = true;
        queueMicrotask(() => this._navigate(`/fitness-tv/profile-${destination.entry_id}`));
      }
      return;
    }

    const rows = profiles.map((profile) => {
      const tv = profile.tv_dashboard || {};
      const enabled = Boolean(tv.enabled);
      const target = this._targetName(tv.cast_media_player_id);
      const accessProfile = (this._adminAccess?.profiles || []).find((item) => String(item?.entry_id || "") === String(profile.entry_id || ""));
      const boundUserId = String(accessProfile?.bound_user_id || "");
      const assignOptions = [`<option value="">${_fitnessEscape(l.account_unassigned)}</option>`, ...(this._adminAccess?.users || []).filter((user) => user?.is_active !== false).map((user) => `<option value="${_fitnessEscape(user.user_id)}" ${String(user.user_id) === boundUserId ? "selected" : ""}>${_fitnessEscape(user.name || user.user_id)}</option>`)].join("");
      return `<div class="profile-row admin-profile-link ${enabled ? "tv-enabled" : "tv-disabled"}" data-entry="${_fitnessEscape(profile.entry_id)}" role="link" tabindex="0" aria-label="${_fitnessEscape(profile.profile_name)}">
        <div class="profile-avatar"><ha-icon icon="mdi:account-circle-outline"></ha-icon></div>
        <div class="profile-copy"><strong>${_fitnessEscape(profile.profile_name)}</strong><span>${_fitnessEscape(enabled ? (target || l.no_default_tv) : (l.tv_view_disabled))}</span>${enabled ? `<small class="profile-process-status" aria-live="polite"></small>` : ""}</div>
        <div class="profile-badges">
          ${enabled ? `<span>${_fitnessEscape(l.tts_ducking_short)} ${Number(tv.ducking_percent ?? 25)}%</span><span>${_fitnessEscape(l.tv_scale_short)} ${Number(tv.tv_scale_percent ?? 70)}%</span>${tv.oled_protection ? `<span><ha-icon icon="mdi:television-shimmer"></ha-icon>${_fitnessEscape(l.oled_short)}</span>` : ""}` : `<span>${_fitnessEscape(l.backend_profile)}</span>`}
        </div>
        <div class="profile-actions">
          ${enabled ? `<button class="tool start-tv-workout"><ha-icon icon="mdi:run-fast"></ha-icon><span>${_fitnessEscape(l.start_tv_workout)}</span></button><button class="tool open-profile"><ha-icon icon="mdi:television-play"></ha-icon><span>${_fitnessEscape(l.open)}</span></button><button class="tool configure-profile"><ha-icon icon="mdi:cog-outline"></ha-icon><span>${_fitnessEscape(l.reconfigure)}</span></button>` : `<button class="tool backend-profile"><ha-icon icon="mdi:cog-outline"></ha-icon><span>${_fitnessEscape(l.reconfigure)}</span></button><button class="tool enable-profile"><ha-icon icon="mdi:television-play"></ha-icon><span>${_fitnessEscape(l.enable_tv_view)}</span></button>`}
          ${enabled ? `<button class="tool backend-profile"><ha-icon icon="mdi:account-cog-outline"></ha-icon><span>${_fitnessEscape(l.backend_settings)}</span></button>` : ""}
          <label class="profile-assign"><ha-icon icon="mdi:account-arrow-right-outline"></ha-icon><select data-profile-assign aria-label="${_fitnessEscape(l.assign_user)}">${assignOptions}</select></label>
          ${enabled ? `<button class="tool danger complete-remove-profile"><ha-icon icon="mdi:account-remove-outline"></ha-icon><span>${_fitnessEscape(l.complete_remove)}</span></button><button class="icon-tool remove-profile" title="${_fitnessEscape(l.disable_tv_view)}"><ha-icon icon="mdi:minus-circle-outline"></ha-icon></button>` : `<button class="tool danger delete-backend-profile"><ha-icon icon="mdi:delete-outline"></ha-icon><span>${_fitnessEscape(l.delete)}</span></button>`}
        </div>
      </div>`;
    }).join("");
    this.shadowRoot.innerHTML = `<ha-card class="setup-shell">
      <div class="setup-head">
        <div><div class="setup-title"><img class="fitness-brand-icon" src="${_fitnessEscape(_fitnessBrandIconUrl(this._hass))}" alt=""><strong>${_fitnessEscape(l.tv_setup)}</strong></div><p>${_fitnessEscape(l.tv_setup_hint)}</p></div>
        <div class="setup-actions"><button class="tool" id="overview-cast-toggle"><ha-icon icon="${(this._overviewCast?.active || this._overviewLocalCastSessionActive()) ? "mdi:cast-off" : "mdi:cast-connected"}"></ha-icon><span>${_fitnessEscape((this._overviewCast?.active || this._overviewLocalCastSessionActive()) ? (l.cast_stop) : (l.cast_dashboard))}</span></button><button class="tool" id="manage-access"><ha-icon icon="mdi:account-lock-outline"></ha-icon><span>${_fitnessEscape(l.fitness_accounts)}</span></button><button class="tool" id="add-profile"><ha-icon icon="mdi:plus-circle-outline"></ha-icon><span>${_fitnessEscape(l.add_tv_profile)}</span></button><button class="tool" id="add-backend-profile"><ha-icon icon="mdi:account-plus-outline"></ha-icon><span>${_fitnessEscape(l.add_fitness_user)}</span></button><button class="tool" id="manage-profiles"><ha-icon icon="mdi:account-cog-outline"></ha-icon><span>${_fitnessEscape(l.manage_profiles)}</span></button></div>
      </div>
      <div class="profiles-list">${rows || `<div class="empty">${_fitnessEscape(l.no_fitness_profiles)}</div>`}</div>
      <div id="setup-modal"></div>
    </ha-card>${this._style()}`;
    const openAdminProfileRow = (row, event = null) => {
      if (!row) return;
      if (event?.target?.closest?.("button,a,input,select,textarea,[role=button]")) return;
      const entryId = String(row.dataset?.entry || "");
      if (entryId) this._navigate(`/fitness-tv/profile-${entryId}`);
    };
    this.shadowRoot.querySelectorAll(".admin-profile-link").forEach((row) => {
      row.addEventListener("click", (event) => openAdminProfileRow(row, event));
      row.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        if (event.target !== row) return;
        event.preventDefault();
        openAdminProfileRow(row);
      });
    });
    this.shadowRoot.getElementById("overview-cast-toggle")?.addEventListener("click", () => void this._toggleOverviewCast());
    this.shadowRoot.getElementById("manage-access")?.addEventListener("click", () => this._openAccessAdmin());
    this.shadowRoot.getElementById("add-profile")?.addEventListener("click", () => this._openAddProfile());
    this.shadowRoot.getElementById("add-backend-profile")?.addEventListener("click", () => this._openBackendFlow("add"));
    this.shadowRoot.getElementById("manage-profiles")?.addEventListener("click", () => this._navigate("/config/integrations/integration/fitness"));
    this.shadowRoot.querySelectorAll(".profile-row").forEach((row) => {
      const entryId = row.dataset.entry;
      const profile = this._profiles.find((item) => item.entry_id === entryId);
      row.querySelector(".start-tv-workout")?.addEventListener("click", () => this._startTvWorkout(profile, row));
      row.querySelector(".open-profile")?.addEventListener("click", () => this._navigate(`/fitness-tv/profile-${entryId}`));
      row.querySelector(".configure-profile")?.addEventListener("click", () => this._openConfigure(profile));
      row.querySelector(".enable-profile")?.addEventListener("click", () => this._openConfigure(profile, true));
      row.querySelector(".backend-profile")?.addEventListener("click", () => this._openBackendFlow("options", entryId, profile?.profile_name || ""));
      row.querySelector("[data-profile-assign]")?.addEventListener("change", (event) => void this._assignProfileUser(entryId, String(event.target?.value || "")));
      row.querySelector(".delete-backend-profile")?.addEventListener("click", () => void this._deleteBackendProfile(profile, false));
      row.querySelector(".complete-remove-profile")?.addEventListener("click", () => void this._deleteBackendProfile(profile, true));
      row.querySelector(".remove-profile")?.addEventListener("click", () => this._saveProfile(profile, {...profile.tv_dashboard, enabled:false}));
    });
  }

  async _assignProfileUser(profileEntryId, userId) {
    if (!this._hass || !this._access?.is_admin) return;
    const snapshot = this._adminAccess || {};
    const profile = (snapshot.profiles || []).find((item) => String(item?.entry_id || "") === String(profileEntryId || ""));
    const previousUserId = String(profile?.bound_user_id || "");
    try {
      if (previousUserId && previousUserId !== userId) {
        const previous = (snapshot.users || []).find((item) => String(item?.user_id || "") === previousUserId);
        if (previous?.fitness_profile_entry_id === profileEntryId) {
          if (previous?.is_admin) {
            await this._hass.callWS({
              type:"fitness/access/account/save",
              user_id:previousUserId, role:"admin", profile_entry_id:"",
              view_profile_entry_ids:Array.isArray(previous.view_profile_entry_ids) ? previous.view_profile_entry_ids : [],
              language:String(previous.language || "en"),
            });
          } else {
            await this._hass.callWS({type:"fitness/access/account/delete",user_id:previousUserId});
          }
        }
      }
      if (userId) {
        const user = (snapshot.users || []).find((item) => String(item?.user_id || "") === userId) || {};
        await this._hass.callWS({
          type:"fitness/access/account/save",
          user_id:userId,
          role:user.is_admin ? "admin" : (user.fitness_role && user.fitness_role !== "none" ? user.fitness_role : "local"),
          profile_entry_id:profileEntryId,
          remote_slug:String(user.remote_slug || ""),
          view_profile_entry_ids:Array.isArray(user.view_profile_entry_ids) ? user.view_profile_entry_ids : [],
          language:String(user.language || "en"),
        });
      }
      this._loaded = false;
      await this._load();
    } catch (err) {
      console.error("[Fitness TV] profile assignment failed", err);
      this._error = this._labels().save_failed;
      this._render();
    }
  }

  async _deleteBackendProfile(profile, complete = false) {
    if (!this._hass || !profile?.entry_id || !this._access?.is_admin) return;
    const l = this._labels(profile);
    const message = complete
      ? l.complete_remove_confirm
      : l.delete_backend_profile_confirm;
    if (!window.confirm(message)) return;
    try {
      await this._hass.callWS({type:"fitness/access/profile/delete",profile_entry_id:profile.entry_id});
      this._loaded = false;
      await this._load();
    } catch (err) {
      console.error("[Fitness TV] profile deletion failed", err);
      this._error = l.save_failed;
      this._render();
    }
  }

  async _overviewGoogleCastSenderApi() {
    if (globalThis.cast?.framework?.CastContext) return globalThis.cast.framework.CastContext;
    window.__fitnessExternalScripts = window.__fitnessExternalScripts || new Map();
    const key = "google-cast-sender";
    if (!window.__fitnessExternalScripts.has(key)) {
      const promise = new Promise((resolve, reject) => {
        let timeout = null;
        const finish = () => {
          if (timeout) clearTimeout(timeout);
          if (globalThis.cast?.framework?.CastContext) resolve(globalThis.cast.framework.CastContext);
          else reject(new Error("Google Cast API did not become ready"));
        };
        const previous = window.__onGCastApiAvailable;
        window.__onGCastApiAvailable = (...args) => {
          try { if (typeof previous === "function") previous(...args); } catch (_err) {}
          finish();
        };
        const existing = document.querySelector('script[data-fitness-google-cast-sender]');
        if (!existing) {
          const script = document.createElement("script");
          script.dataset.fitnessGoogleCastSender = "1";
          script.src = "https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1";
          script.async = true;
          script.addEventListener("error", () => reject(new Error("Unable to load Google Cast sender")));
          document.head.appendChild(script);
        }
        timeout = setTimeout(() => reject(new Error("Google Cast sender timed out")), 12000);
      });
      window.__fitnessExternalScripts.set(key, promise);
    }
    await window.__fitnessExternalScripts.get(key);
    return globalThis.cast?.framework?.CastContext || null;
  }

  _overviewLocalCastSessionMarked() {
    try { return sessionStorage.getItem(FITNESS_TV_OVERVIEW_LOCAL_CAST_TAB_STORAGE) === "1"; } catch (_err) { return false; }
  }

  _markOverviewLocalCast(active) {
    try {
      if (active) sessionStorage.setItem(FITNESS_TV_OVERVIEW_LOCAL_CAST_TAB_STORAGE, "1");
      else sessionStorage.removeItem(FITNESS_TV_OVERVIEW_LOCAL_CAST_TAB_STORAGE);
    } catch (_err) {}
  }

  _overviewLocalCastSessionActive(context = this._overviewLocalCastContext) {
    if (!this._overviewLocalCastSessionMarked()) return false;
    try { return Boolean(this._overviewLocalCastActive || context?.getCurrentSession?.()); } catch (_err) { return Boolean(this._overviewLocalCastActive); }
  }

  async _prepareOverviewLocalCastContext() {
    await this._overviewGoogleCastSenderApi();
    const context = globalThis.cast?.framework?.CastContext?.getInstance?.();
    if (!context) throw new Error("Google Cast is not available in this browser.");
    context.setOptions({
      receiverApplicationId:FITNESS_TV_CAST_APP_ID,
      autoJoinPolicy:globalThis.chrome?.cast?.AutoJoinPolicy?.TAB_AND_ORIGIN_SCOPED
        || globalThis.chrome?.cast?.AutoJoinPolicy?.PAGE_SCOPED
        || "tab_and_origin_scoped",
      resumeSavedSession:true,
    });
    if (!this._overviewLocalCastSessionListener) {
      this._overviewLocalCastSessionListener = (event) => {
        const state = String(event?.sessionState || "");
        const active = state.includes("STARTED") || state.includes("RESUMED") || state.includes("STARTING") || state.includes("RESUMING");
        const ended = state.includes("ENDED") || state.includes("START_FAILED");
        if (active) this._overviewLocalCastActive = true;
        if (ended) {
          this._overviewLocalCastActive = false;
          this._markOverviewLocalCast(false);
        }
        // Do not redraw the setup page while Google Cast is opening its native
        // chooser/auth flow: replacing the modal here destroys the picker state.
        // Successful local Cast redraws explicitly after receiver authentication;
        // only terminal session changes need an asynchronous UI refresh.
        if (ended && this._loaded) this._render();
      };
      context.addEventListener(globalThis.cast.framework.CastContextEventType.SESSION_STATE_CHANGED, this._overviewLocalCastSessionListener);
    }
    this._overviewLocalCastContext = context;
    this._overviewLocalCastActive = this._overviewLocalCastSessionMarked() && Boolean(context.getCurrentSession?.());
    return context;
  }

  async _castOverviewLocal(root) {
    if (!this._hass || !this._access?.is_admin) return;
    const l = this._labels();
    const status = root?.querySelector?.(".overview-cast-status");
    const button = root?.querySelector?.("#overview-cast-local");
    if (button) button.disabled = true;
    let credentials = null;
    try {
      const context = await this._prepareOverviewLocalCastContext();
      if (status) status.textContent = l.local_cast_connecting;
      await context.requestSession();
      const session = context.getCurrentSession?.();
      if (!session) throw new Error(l.local_cast_cancelled);
      credentials = await this._hass.callWS({
        type:"fitness/tv/local_cast_credentials",
        overview:true,
        browser_origin:String(globalThis.location?.origin || ""),
      });
      const namespace = String(credentials.namespace || FITNESS_TV_CAST_NAMESPACE);
      if (status) status.textContent = l.local_cast_authenticating;
      let listener = null;
      let timeout = null;
      const receiverReady = new Promise((resolve, reject) => {
        let settled = false;
        const finish = (err = null) => {
          if (settled) return;
          settled = true;
          if (timeout) clearTimeout(timeout);
          try { if (listener) session.removeMessageListener?.(namespace, listener); } catch (_err) {}
          if (err) reject(err); else resolve(true);
        };
        timeout = setTimeout(() => finish(new Error(l.local_cast_receiver_failed)), 22000);
        listener = (_namespace, message) => {
          let payload = message;
          if (typeof payload === "string") { try { payload = JSON.parse(payload); } catch (_err) { return; } }
          if (payload?.type === "receiver_status" && payload?.connected
              && String(payload?.hassUrl || "").replace(/\/$/, "") === String(credentials.hass_url || "").replace(/\/$/, "")) finish();
          else if (payload?.type === "receiver_error") finish(new Error(String(payload?.error_message || payload?.errorMessage || l.cast_failed)));
        };
        session.addMessageListener(namespace, listener);
      });
      const authMessage = {
        type:"connect",
        refreshToken:credentials.refresh_token,
        clientId:credentials.client_id ?? null,
        hassUrl:credentials.hass_url,
      };
      await session.sendMessage(namespace, authMessage);
      setTimeout(() => void session.sendMessage(namespace, authMessage).catch(() => undefined), 1400);
      setTimeout(() => void session.sendMessage(namespace, authMessage).catch(() => undefined), 4200);
      await receiverReady;
      await session.sendMessage(namespace, {
        type:"show_lovelace_view",
        hassUrl:credentials.hass_url,
        viewPath:credentials.view_path,
        urlPath:credentials.dashboard_path,
      });
      this._overviewLocalCastActive = true;
      this._markOverviewLocalCast(true);
      this._overviewLocalCastContext = context;
      root?.replaceChildren();
      this._render();
    } catch (err) {
      this._overviewLocalCastActive = false;
      this._markOverviewLocalCast(false);
      if (credentials) { try { await this._overviewLocalCastContext?.endCurrentSession?.(true); } catch (_err) {} }
      console.error("[Fitness TV] overview local Cast failed", err);
      if (status) { status.textContent = l.cast_failed; status.classList.add("error"); }
      if (button) button.disabled = false;
    }
  }

  async _stopOverviewLocalCast() {
    try { await this._overviewLocalCastContext?.endCurrentSession?.(true); } catch (_err) {}
    this._overviewLocalCastActive = false;
    this._markOverviewLocalCast(false);
    this._render();
  }

  async _toggleOverviewCast() {
    if (!this._hass || !this._access?.is_admin) return;
    const l = this._labels();
    if (this._overviewLocalCastSessionActive()) {
      await this._stopOverviewLocalCast();
      return;
    }
    if (this._overviewCast?.active) {
      const button = this.shadowRoot?.getElementById("overview-cast-toggle");
      if (button) button.disabled = true;
      try {
        this._overviewCast = await this._hass.callWS({
          type:"fitness/tv/overview/stop",
          entity_id:String(this._overviewCast?.target || ""),
        });
        this._loaded = false;
        await this._load();
      } catch (err) {
        if (button) button.disabled = false;
        console.error("[Fitness TV] overview Cast stop failed", err);
        this._showOverviewCastError(l.cast_stop_failed || l.cast_failed);
      }
      return;
    }
    this._openOverviewCastPicker();
  }

  _openOverviewCastPicker() {
    const l = this._labels();
    const rows = (this._castTargets || []).map((target) => {
      const unavailable = target?.available === false;
      const state = unavailable ? l.cast_unavailable : (target.state || "");
      return `<button class="add-profile-row overview-cast-target ${unavailable ? "unavailable" : ""}" data-cast-target="${_fitnessEscape(target.entity_id)}" ${unavailable ? "disabled aria-disabled=\"true\"" : ""}><ha-icon icon="mdi:television"></ha-icon><span><strong>${_fitnessEscape(target.name || target.entity_id)}</strong><small>${_fitnessEscape(state)}</small></span><ha-icon icon="${unavailable ? "mdi:cast-off" : "mdi:cast"}"></ha-icon></button>`;
    }).join("");
    this._modal(`<div class="modal-card overview-cast-modal"><div class="modal-head"><strong class="modal-title-with-icon"><ha-icon icon="mdi:cast"></ha-icon>${_fitnessEscape(l.cast_dashboard)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="modal-scroll-body overview-cast-body"><section class="overview-cast-section"><div><strong>${_fitnessEscape(l.local_cast)}</strong><small>${_fitnessEscape(l.local_cast_hint)}</small></div><button class="tool" id="overview-cast-local" disabled><ha-icon icon="mdi:cast-connected"></ha-icon><span>${_fitnessEscape(l.local_cast_choose)}</span></button></section><section class="overview-cast-section"><div><strong>${_fitnessEscape(l.cast_ha_devices)}</strong><small>${_fitnessEscape(l.cast_ha_devices_hint)}</small></div><div class="overview-cast-targets">${rows || `<div class="empty">${_fitnessEscape(l.cast_no_devices)}</div>`}</div></section><div class="access-status overview-cast-status" aria-live="polite"></div></div></div>`);
    const root = this.shadowRoot?.getElementById("setup-modal");
    root?.querySelectorAll(".overview-cast-target").forEach((button) => button.addEventListener("click", () => void this._castOverviewToTarget(String(button.dataset.castTarget || ""), root)));
    const localButton = root?.querySelector("#overview-cast-local");
    void this._prepareOverviewLocalCastContext().then(() => {
      if (localButton) localButton.disabled = false;
    }).catch((err) => {
      if (localButton) localButton.disabled = true;
      const status = root?.querySelector(".overview-cast-status");
      console.error("[Fitness TV] overview local Cast setup failed", err);
      if (status) status.textContent = l.local_cast_unsupported;
    });
    localButton?.addEventListener("click", () => void this._castOverviewLocal(root));
  }

  async _castOverviewToTarget(target, root) {
    if (!this._hass || !target) return;
    const selectedTarget = (this._castTargets || []).find((item) => String(item?.entity_id || "") === String(target));
    if (selectedTarget?.available === false) return;
    const l = this._labels();
    const status = root?.querySelector?.(".overview-cast-status");
    const buttons = [...(root?.querySelectorAll?.(".overview-cast-target") || [])];
    buttons.forEach((button) => { button.disabled = true; });
    if (status) status.textContent = l.cast_connecting;
    try {
      this._overviewCast = await this._hass.callWS({type:"fitness/tv/overview/cast",entity_id:target});
      root?.replaceChildren();
      this._loaded = false;
      await this._load();
    } catch (err) {
      buttons.forEach((button) => { button.disabled = button.classList.contains("unavailable"); });
      console.error("[Fitness TV] overview Cast start failed", err);
      if (status) { status.textContent = l.cast_failed; status.classList.add("error"); }
    }
  }

  _showOverviewCastError(message) {
    const root = this.shadowRoot?.getElementById("setup-modal");
    if (!root) return;
    this._modal(`<div class="modal-card"><div class="modal-head"><strong>${_fitnessEscape(this._labels().cast_dashboard)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="modal-scroll-body"><div class="empty">${_fitnessEscape(message)}</div></div></div>`);
  }

  _modal(content) {
    const root = this.shadowRoot?.getElementById("setup-modal");
    if (!root) return;
    root.innerHTML = `<div class="modal-backdrop">${content}</div>`;
    const modalLabels = this._labels();
    const closeButton = root.querySelector(".modal-close");
    closeButton?.setAttribute("title", modalLabels.close);
    closeButton?.setAttribute("aria-label", modalLabels.close);
    const modalCard = root.querySelector(".modal-card");
    const backendFlowModal = Boolean(modalCard?.classList?.contains("backend-flow-modal"));
    const scrollSelector = ":scope > .profile-settings,:scope > .add-profile-list,:scope > .access-admin-body,:scope > .modal-scroll-body,:scope > .modal-auto-scroll-body";
    if (modalCard && !backendFlowModal && !modalCard.querySelector(scrollSelector)) {
      const middle = [...modalCard.children].filter((node) => !node.classList.contains("modal-head") && !node.classList.contains("modal-actions") && !node.classList.contains("settings-actions"));
      if (middle.length) {
        const body = document.createElement("div");
        body.className = "modal-auto-scroll-body";
        modalCard.insertBefore(body, middle[0]);
        middle.forEach((node) => body.appendChild(node));
      }
    }
    const scrollBody = backendFlowModal ? null : modalCard?.querySelector(scrollSelector);
    modalCard?.addEventListener("wheel", (ev) => {
      if (backendFlowModal) return;
      if (!scrollBody) { ev.stopPropagation(); return; }
      if (scrollBody.contains(ev.target)) { ev.stopPropagation(); return; }
      if (Math.abs(Number(ev.deltaY || 0)) > 0) {
        scrollBody.scrollTop += Number(ev.deltaY || 0);
        ev.preventDefault();
      }
      ev.stopPropagation();
    }, {passive:false});
    root.querySelector(".modal-backdrop")?.addEventListener("click", (ev) => { if (ev.target.classList.contains("modal-backdrop")) root.replaceChildren(); });
    root.querySelector(".modal-close")?.addEventListener("click", () => root.replaceChildren());
  }

  _openBackendFlow(mode, entryId = "", profileName = "") {
    this._modal(`<div class="modal-card backend-flow-modal"><div id="backend-flow-host" class="backend-flow-host"></div></div>`);
    const root = this.shadowRoot?.getElementById("setup-modal");
    const host = root?.querySelector("#backend-flow-host");
    if (!host) return;
    const flow = document.createElement("fitness-backend-flow");
    flow.hass = this._hass;
    flow.addEventListener("fitness-flow-close", () => {
      root.replaceChildren();
      this._loaded = false;
      setTimeout(() => this._load(), 100);
    });
    flow.addEventListener("fitness-flow-complete", () => {
      // Do not redraw the parent while an options flow is returning to its
      // settings menu: replacing the shadow DOM here destroys the modal.
      // Refresh the dashboard only after the user explicitly closes it.
      this._loaded = false;
    });
    host.replaceChildren(flow);
    const profile = this._profiles?.find?.((item) => String(item.entry_id) === String(entryId)) || this._profiles?.[0];
    flow.start({mode, entryId, profileName, uiLabels:this._labels(profile), language:String(profile?.language || this._access?.language || this._hass?.language || "en")});
  }

  _openAddProfile() {
    const l = this._labels();
    const available = (this._profiles || []).filter((profile) => !profile.tv_dashboard?.enabled);
    const rows = available.map((profile) => `<button class="add-profile-row" data-entry="${_fitnessEscape(profile.entry_id)}"><ha-icon icon="mdi:account-circle-outline"></ha-icon><span>${_fitnessEscape(profile.profile_name)}</span><ha-icon icon="mdi:plus"></ha-icon></button>`).join("");
    this._modal(`<div class="modal-card"><div class="modal-head"><strong class="modal-title-with-icon"><ha-icon icon="mdi:plus-circle-outline"></ha-icon>${_fitnessEscape(l.add_tv_profile)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="add-profile-list">${rows || `<div class="empty">${_fitnessEscape(l.all_profiles_enabled)}</div>`}</div></div>`);
    const root = this.shadowRoot.getElementById("setup-modal");
    root?.querySelectorAll(".add-profile-row").forEach((button) => button.addEventListener("click", () => {
      const profile = this._profiles.find((item) => item.entry_id === button.dataset.entry);
      if (profile) this._openConfigure(profile, true);
    }));
  }

  async _startTvWorkout(profile, row) {
    if (!profile || !this._hass) return;
    const l = this._labels(profile);
    const button = row?.querySelector?.(".start-tv-workout");
    const status = row?.querySelector?.(".profile-process-status");
    if (button) button.disabled = true;
    // Cast entity state is receiver/app state, not a trustworthy physical-TV
    // power signal. Let the backend prepare/wake the selected target and only
    // report the result it actually observes.
    if (status) status.textContent = l.start_tv_workout_preparing;
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/start_workout",
        profile_entry_id:profile.entry_id,
        entity_id:String(profile?.tv_dashboard?.cast_media_player_id || ""),
      });
      if (!result?.cast || !result?.workout_started) {
        if (status) status.textContent = l.start_tv_workout_failed;
      } else if (result?.music_error) {
        if (status) status.textContent = l.start_tv_workout_music_failed;
      } else {
        if (status) status.textContent = l.start_tv_workout_ready;
      }
    } catch (_err) {
      if (status) status.textContent = l.start_tv_workout_failed;
    } finally {
      if (button) button.disabled = false;
    }
  }

  async _openConfigure(profile, enableByDefault = false) {
    if (!profile) return;
    const l = this._labels(profile);
    const tv = profile.tv_dashboard || {};
    const options = [`<option value="">${_fitnessEscape(l.no_default_tv)}</option>`, ...(this._castTargets || []).map((target) => {
      const unavailable = target?.available === false;
      const suffix = unavailable ? ` (${l.cast_unavailable})` : "";
      return `<option value="${_fitnessEscape(target.entity_id)}" ${target.entity_id === tv.cast_media_player_id ? "selected" : ""} ${unavailable ? "disabled" : ""}>${_fitnessEscape(target.name || target.entity_id)}${_fitnessEscape(suffix)}</option>`;
    })].join("");
    const preferred = String(tv.cast_media_player_id || "");
    const audioOutputId = String(tv.audio_output_id || "__fitness_browser__");
    const audioOutputs = (Array.isArray(this._audioOutputs) ? this._audioOutputs : []).filter((output) => String(output?.entity_id || "") !== preferred);
    const effectiveAudioOutput = audioOutputId === preferred ? "__fitness_browser__" : audioOutputId;
    const audioOutputOptions = [
      `<option value="__fitness_browser__" ${effectiveAudioOutput === "__fitness_browser__" ? "selected" : ""}>${_fitnessEscape(l.audio_output_browser)}</option>`,
      ...audioOutputs.map((output) => {
        const entityId = String(output?.entity_id || "");
        const ma = output?.music_assistant ? ` · ${_fitnessEscape("Music Assistant")}` : "";
        const unavailable = ["unavailable", "unknown"].includes(String(output?.state || "")) ? ` · ${_fitnessEscape(l.unavailable)}` : "";
        return `<option value="${_fitnessEscape(entityId)}" ${entityId === effectiveAudioOutput ? "selected" : ""}>${_fitnessEscape(output?.name || entityId)}${ma}${unavailable}</option>`;
      }),
    ].join("");
    const enabled = enableByDefault ? true : Boolean(tv.enabled);
    let musicAdapters = [];
    let providerCatalog = [];
    let musicAdapterOptions = {};
    let musicSearchLimit = 50;
    try {
      const adapterData = await this._hass.callWS({type:"fitness/tv/music/adapters",profile_entry_id:profile.entry_id});
      musicAdapters = Array.isArray(adapterData?.adapters) ? adapterData.adapters.filter((adapter) => adapter?.available !== false) : [];
      providerCatalog = Array.isArray(adapterData?.provider_catalog) ? adapterData.provider_catalog : [];
      musicAdapterOptions = adapterData?.music_adapter_options && typeof adapterData.music_adapter_options === "object" ? adapterData.music_adapter_options : {};
      musicSearchLimit = Math.max(10, Math.min(100, Number(adapterData?.music_search_limit || 50)));
    } catch (_err) {}
    const adapterRows = musicAdapters.filter((adapter) => adapter?.available !== false).map((adapter) => {
      const checked = Boolean(adapter.selected);
      const hint = _fitnessMusicAdapterHint(l, adapter);
      const accounts = Array.isArray(adapter.account_options) ? adapter.account_options : [];
      const savedAccount = String(musicAdapterOptions?.[adapter.id]?.account_id || adapter.selected_account_id || "");
      const accountMarkup = accounts.length ? `<select class="adapter-account" data-config-music-account="${_fitnessEscape(adapter.id)}" title="${_fitnessEscape(l.music_account)}">${accounts.map((account) => `<option value="${_fitnessEscape(account.id)}" ${String(account.id) === savedAccount ? "selected" : ""}>${_fitnessEscape(account.name || account.id)}</option>`).join("")}</select>` : "";
      const setupMarkup = adapter.setup_path ? `<button type="button" class="adapter-setup" data-adapter-setup="${_fitnessEscape(adapter.setup_path)}"><span>${_fitnessEscape(l.music_configure_provider)}</span></button>` : "";
      return `<div class="music-adapter-row"><input type="checkbox" data-config-music-adapter="${_fitnessEscape(adapter.id)}" ${checked ? "checked" : ""}><ha-icon icon="${String(adapter.icon || "mdi:music-note").startsWith("mdi:") ? _fitnessEscape(adapter.icon) : "mdi:music-note"}"></ha-icon><span><strong>${_fitnessEscape(adapter.name || adapter.id)}</strong>${hint ? `<small>${_fitnessEscape(hint)}</small>` : ""}</span><div class="adapter-actions">${accountMarkup}${setupMarkup}<button type="button" class="adapter-setup adapter-remove" data-remove-music-adapter="${_fitnessEscape(adapter.id)}" title="${_fitnessEscape(l.remove)}"><ha-icon icon="mdi:minus-circle-outline"></ha-icon><span>${_fitnessEscape(l.remove)}</span></button></div></div>`;
    }).join("");
    const duck = Number(tv.ducking_percent ?? 25);
    const scale = Number(tv.tv_scale_percent ?? 70);
    const animations = Boolean(tv.animations_enabled ?? true);
    this._modal(`<div class="modal-card configure-modal"><div class="modal-head"><strong>${_fitnessEscape(l.reconfigure_profile)}: ${_fitnessEscape(profile.profile_name)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="profile-settings">
      <label class="setting-toggle"><span><strong class="setting-title"><ha-icon icon="mdi:monitor-dashboard"></ha-icon>${_fitnessEscape(l.enable_tv_view)}</strong><small>${_fitnessEscape(l.enable_tv_view_hint)}</small></span><input id="cfg-enabled" type="checkbox" ${enabled ? "checked" : ""}></label>
      <div class="setting-adapters"><div class="setting-adapters-head"><span><strong>${_fitnessEscape(l.music_adapters)}</strong><small>${_fitnessEscape(l.music_adapters_hint)}</small></span><button type="button" class="adapter-setup" id="cfg-add-provider"><ha-icon icon="mdi:plus"></ha-icon><span>${_fitnessEscape(l.music_add_provider)}</span></button></div><div class="music-adapter-list">${adapterRows || `<div class="browser-empty">${_fitnessEscape(l.music_no_adapters)}</div>`}</div></div>
      <label class="setting-range"><span><strong>${_fitnessEscape(l.music_search_result_count)}</strong><small>${_fitnessEscape(l.music_search_result_count_hint)}</small></span><input id="cfg-search-limit" type="range" min="10" max="100" step="10" value="${musicSearchLimit}"><output id="cfg-search-limit-value">${musicSearchLimit}</output></label>
      <label class="setting-field"><span>${_fitnessEscape(l.default_tv)}</span><select id="cfg-target">${options}</select></label>
      <label class="setting-field audio-output-field"><span><strong>${_fitnessEscape(l.audio_output)}</strong><small>${_fitnessEscape(l.audio_output_hint)}</small></span><select id="cfg-audio-output">${audioOutputOptions}</select></label>
      <label class="setting-range"><span><strong>${_fitnessEscape(l.tts_ducking)}</strong><small>${_fitnessEscape(l.tts_ducking_hint)}</small></span><input id="cfg-duck" type="range" min="0" max="100" step="5" value="${duck}"><output id="cfg-duck-value">${duck}%</output></label>
      <label class="setting-range"><span><strong>${_fitnessEscape(l.tv_scale)}</strong><small>${_fitnessEscape(l.tv_scale_hint)}</small></span><input id="cfg-scale" type="range" min="10" max="150" step="5" value="${scale}"><output id="cfg-scale-value">${scale}%</output></label>
      <label class="setting-toggle"><span><strong>${_fitnessEscape(l.ignore_lights_when_cast_active)}</strong><small>${_fitnessEscape(l.ignore_lights_when_cast_active_hint)}</small></span><input id="cfg-ignore-lights" type="checkbox" ${Boolean(tv.ignore_lights_when_cast_active ?? true) ? "checked" : ""}></label>
      <label class="setting-toggle"><span><strong>${_fitnessEscape(l.dashboard_animations)}</strong><small>${_fitnessEscape(l.dashboard_animations_hint)}</small></span><input id="cfg-animations" type="checkbox" ${animations ? "checked" : ""}></label>
      <label class="setting-toggle"><span><strong>${_fitnessEscape(l.oled_protection)}</strong><small>${_fitnessEscape(l.oled_protection_hint)}</small></span><input id="cfg-oled" type="checkbox" ${tv.oled_protection ? "checked" : ""}></label>
      <div class="setting-info"><ha-icon icon="mdi:television-shimmer"></ha-icon><span><strong>${_fitnessEscape(l.keep_awake)}</strong><small>${_fitnessEscape(l.keep_awake_hint)}</small></span></div>
    </div><div class="settings-actions"><button class="tool" id="cfg-save"><ha-icon icon="mdi:content-save-outline"></ha-icon><span>${_fitnessEscape(l.save)}</span></button><span class="settings-status" id="cfg-status"></span></div></div>`);
    const root = this.shadowRoot.getElementById("setup-modal");
    const duckInput = root?.querySelector("#cfg-duck");
    const scaleInput = root?.querySelector("#cfg-scale");
    duckInput?.addEventListener("input", () => { const out=root.querySelector("#cfg-duck-value"); if(out) out.textContent=`${duckInput.value}%`; });
    scaleInput?.addEventListener("input", () => {
      const out=root.querySelector("#cfg-scale-value");
      if(out) out.textContent=`${scaleInput.value}%`;
      this._previewProfileScale(profile, scaleInput.value);
    });
    const searchLimitInput = root?.querySelector("#cfg-search-limit");
    searchLimitInput?.addEventListener("input", () => { const out=root.querySelector("#cfg-search-limit-value"); if(out) out.textContent=searchLimitInput.value; });
    root?.querySelectorAll("[data-adapter-setup]").forEach((button) => button.addEventListener("click", () => this._navigate(String(button.dataset.adapterSetup || "/config/integrations"))));
    root?.querySelector("#cfg-add-provider")?.addEventListener("click", () => this._openMusicProviderCatalog(providerCatalog, profile));
    root?.querySelectorAll("[data-remove-music-adapter]").forEach((button) => button.addEventListener("click", () => {
      const adapterId = String(button.dataset.removeMusicAdapter || "");
      const checkbox = [...root.querySelectorAll("input[data-config-music-adapter]")].find((input) => String(input.dataset.configMusicAdapter || "") === adapterId);
      if (checkbox) checkbox.checked = false;
      delete musicAdapterOptions[adapterId];
      button.closest(".music-adapter-row")?.classList.add("profile-adapter-removed");
      button.disabled = true;
    }));
    root?.querySelector("#cfg-save")?.addEventListener("click", () => {
      const selectedAdapterOptions = {...musicAdapterOptions};
      root.querySelectorAll("select[data-config-music-account]").forEach((select) => {
        const adapterId = String(select.dataset.configMusicAccount || "");
        if (adapterId && !select.closest(".profile-adapter-removed")) {
          selectedAdapterOptions[adapterId] = {...(selectedAdapterOptions[adapterId] || {}), account_id:String(select.value || "")};
        }
      });
      this._saveProfile(profile, {
      enabled:Boolean(root.querySelector("#cfg-enabled")?.checked),
      music_adapters:[...new Set(
        [...root.querySelectorAll('input[data-config-music-adapter]:checked')]
          .map((input) => String(input.dataset.configMusicAdapter || ""))
          .filter(Boolean),
      )],
      music_adapter_options:selectedAdapterOptions,
      music_search_limit:Number(root.querySelector("#cfg-search-limit")?.value || 50),
      cast_media_player_id:String(root.querySelector("#cfg-target")?.value || ""),
      audio_output_id:String(root.querySelector("#cfg-audio-output")?.value || "__fitness_browser__"),
      animations_enabled:Boolean(root.querySelector("#cfg-animations")?.checked),
      ducking_percent:Number(duckInput?.value || 25),
      ignore_lights_when_cast_active:Boolean(root.querySelector("#cfg-ignore-lights")?.checked),
      tv_scale_percent:Number(scaleInput?.value || 70),
      oled_protection:Boolean(root.querySelector("#cfg-oled")?.checked),
    }, root);
    });
  }

  _openMusicProviderCatalog(providers = [], profile = null) {
    const l = this._labels(profile);
    const rows = (Array.isArray(providers) ? providers : []).map((provider) => {
      const isYtdlp = provider.id === "yt_dlp" || provider.kind === "fitness_optional_adapter";
      const icon = String(provider.icon || "mdi:music-note").startsWith("mdi:") ? String(provider.icon || "mdi:music-note") : "mdi:music-note";
      const action = isYtdlp
        ? `<button type="button" class="adapter-setup" data-setup-ytdlp="${provider.enabled ? "disable" : "enable"}"><span>${_fitnessEscape(provider.enabled ? (l.disable) : (l.music_enable_provider))}</span></button>`
        : `<button type="button" class="adapter-setup" data-provider-path="${_fitnessEscape(provider.setup_path || "/config/integrations")}"><span>${_fitnessEscape(provider.installed ? (l.music_configure_provider) : (l.music_install_provider))}</span></button>`;
      return `<div class="provider-catalog-row ${isYtdlp ? "provider-catalog-ytdlp" : ""}"><ha-icon icon="${_fitnessEscape(icon)}"></ha-icon><span><strong>${_fitnessEscape(_fitnessMusicProviderName(l, provider))}</strong><small>${_fitnessEscape(_fitnessMusicProviderDescription(l, provider))}</small></span>${action}</div>`;
    }).join("");
    this._modal(`<div class="modal-card provider-catalog-modal"><div class="modal-head"><strong>${_fitnessEscape(l.music_add_provider)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="provider-catalog-list">${rows || `<div class="browser-empty">${_fitnessEscape(l.music_no_provider_catalog)}</div>`}</div></div>`);
    const root = this.shadowRoot?.getElementById("setup-modal");
    root?.querySelectorAll("[data-provider-path]").forEach((button) => button.addEventListener("click", () => this._navigate(String(button.dataset.providerPath || "/config/integrations"))));
    root?.querySelectorAll("[data-setup-ytdlp]").forEach((button) => button.addEventListener("click", () => {
      const enable = String(button.dataset.setupYtdlp || "") === "enable";
      if (enable) this._openSetupYtdlpAcknowledgement(providers, profile);
      else void this._setSetupYtdlp(profile, false, true);
    }));
  }

  _openSetupYtdlpAcknowledgement(providers = [], profile = null) {
    if (!profile) return;
    const l = this._labels(profile);
    const provider = (Array.isArray(providers) ? providers : []).find((item) => item?.id === "yt_dlp") || {};
    const disclaimer = String(l.ytdlp_disclaimer);
    this._modal(`<div class="modal-card ytdlp-legal-modal"><div class="modal-head"><strong class="modal-title-with-icon"><ha-icon icon="mdi:youtube"></ha-icon>${_fitnessEscape(provider.name || "yt-dlp")}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="modal-scroll-body ytdlp-legal-body"><div class="setting-info legal-warning"><ha-icon icon="mdi:scale-balance"></ha-icon><span><strong>${_fitnessEscape(l.legal_notice)}</strong><small>${_fitnessEscape(disclaimer)}</small></span></div><label class="setting-toggle ytdlp-accept"><span><strong>${_fitnessEscape(l.ytdlp_accept)}</strong><small>${_fitnessEscape(l.ytdlp_accept_hint)}</small></span><input id="setup-ytdlp-accept" type="checkbox"></label></div><div class="modal-actions"><button class="tool setup-ytdlp-back"><ha-icon icon="mdi:arrow-left"></ha-icon><span>${_fitnessEscape(l.back)}</span></button><button class="primary-tool setup-ytdlp-enable" disabled><ha-icon icon="mdi:check"></ha-icon><span>${_fitnessEscape(l.music_enable_provider)}</span></button></div></div>`);
    const root = this.shadowRoot?.getElementById("setup-modal");
    const accept = root?.querySelector("#setup-ytdlp-accept");
    const enable = root?.querySelector(".setup-ytdlp-enable");
    accept?.addEventListener("change", () => { if (enable) enable.disabled = !accept.checked; });
    root?.querySelector(".setup-ytdlp-back")?.addEventListener("click", () => this._openMusicProviderCatalog(providers, profile));
    enable?.addEventListener("click", () => void this._setSetupYtdlp(profile, true, Boolean(accept?.checked)));
  }

  async _setSetupYtdlp(profile, enabled, acknowledged) {
    if (!this._hass || !profile?.entry_id) return;
    try {
      const result = await this._hass.callWS({type:"fitness/tv/music/ytdlp",profile_entry_id:profile.entry_id,enabled:Boolean(enabled),acknowledged:Boolean(acknowledged)});
      profile.tv_dashboard = {...(profile.tv_dashboard || {}),ytdlp_enabled:Boolean(result?.enabled)};
      await this._openConfigure(profile);
    } catch (err) {
      console.error("[Fitness TV] setup yt-dlp update failed", err);
      const l = this._labels(profile);
      const root = this.shadowRoot?.getElementById("setup-modal");
      const body = root?.querySelector(".ytdlp-legal-body") || root?.querySelector(".provider-catalog-list");
      if (body) body.insertAdjacentHTML("beforeend", `<div class="browser-empty">${_fitnessEscape(l.save_failed)}</div>`);
    }
  }

  _previewProfileScale(profile, value) {
    if (!profile?.entry_id || !this._hass) return;
    const scale = Math.max(10, Math.min(150, Number(value || 70)));
    profile.tv_dashboard = {...(profile.tv_dashboard || {}), tv_scale_percent:scale};
    clearTimeout(this._tvScalePreviewTimer);
    this._tvScalePreviewTimer = setTimeout(() => {
      void this._hass.callWS({
        type:"fitness/tv/preferences/save",
        profile_entry_id:profile.entry_id,
        tv_scale_percent:scale,
      }).catch(() => {});
    }, 140);
  }

  async _saveProfile(profile, settings, root = null) {
    if (!profile || !this._hass) return;
    const l = this._labels(profile);
    const status = root?.querySelector?.("#cfg-status");
    const button = root?.querySelector?.("#cfg-save");
    if (button) button.disabled = true;
    if (status) status.textContent = l.saving;
    try {
      const result = await this._hass.callWS({
        type:"fitness/tv/profile/configure",
        profile_entry_id:profile.entry_id,
        enabled:Boolean(settings.enabled),
        cast_media_player_id:String(settings.cast_media_player_id || ""),
        ducking_percent:Number(settings.ducking_percent ?? 25),
        ignore_lights_when_cast_active:Boolean(settings.ignore_lights_when_cast_active ?? true),
        tv_scale_percent:Number(settings.tv_scale_percent ?? 70),
        oled_protection:Boolean(settings.oled_protection),
      });
      const prefs = await this._hass.callWS({
        type:"fitness/tv/preferences/save",
        profile_entry_id:profile.entry_id,
        music_adapters:Array.isArray(settings.music_adapters) ? settings.music_adapters : [],
        music_adapter_options:settings.music_adapter_options && typeof settings.music_adapter_options === "object" ? settings.music_adapter_options : {},
        music_search_limit:Number(settings.music_search_limit || 50),
        audio_output_id:String(settings.audio_output_id || "__fitness_browser__"),
        animations_enabled:Boolean(settings.animations_enabled ?? true),
      });
      profile.tv_dashboard = {...(profile.tv_dashboard || {}), ...result, music_adapters:prefs?.music_adapters || settings.music_adapters || [], music_adapter_options:prefs?.music_adapter_options || settings.music_adapter_options || {}, music_search_limit:Number(prefs?.music_search_limit || settings.music_search_limit || 50), audio_output_id:String(prefs?.audio_output_id || settings.audio_output_id || "__fitness_browser__"), animations_enabled:Boolean(prefs?.animations_enabled ?? settings.animations_enabled ?? true)};
      if (status) status.textContent = l.saved;
      setTimeout(() => {
        this.shadowRoot?.getElementById("setup-modal")?.replaceChildren();
        this._render();
        this._loaded = false;
        this._load();
      }, 350);
    } catch (_err) {
      if (status) status.textContent = l.save_failed;
      if (button) button.disabled = false;
    }
  }

  async _openAccessAdmin() {
    if (!this._hass || !this._access?.is_admin) return;
    const l = this._labels();
    this._modal(`<div class="modal-card access-admin-modal"><div class="modal-head"><strong class="modal-title-with-icon"><ha-icon icon="mdi:account-lock-outline"></ha-icon>${_fitnessEscape(l.fitness_accounts)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="access-admin-body"><div class="browser-working"><ha-icon class="spin" icon="mdi:loading"></ha-icon><span>${_fitnessEscape(l.loading)}</span></div></div></div>`);
    try {
      const snapshot = await this._hass.callWS({type:"fitness/access/admin"});
      this._renderAccessAdmin(snapshot || {});
    } catch (err) {
      console.error("[Fitness TV] access settings load failed", err);
      const root = this.shadowRoot?.getElementById("setup-modal");
      const body = root?.querySelector(".access-admin-body");
      if (body) body.innerHTML = `<div class="empty">${_fitnessEscape(l.access_save_failed)}</div>`;
    }
  }

  _renderAccessAdmin(snapshot) {
    if (!this._hass || !this._access?.is_admin) return;
    const l = this._labels();
    const users = Array.isArray(snapshot?.users) ? snapshot.users : [];
    const profiles = Array.isArray(snapshot?.profiles) ? snapshot.profiles : [];
    const baseDomain = String(snapshot?.remote_base_domain || "");
    const suffix = baseDomain ? `.${baseDomain}` : "";
    const supportedLanguages = snapshot?.supported_languages && typeof snapshot.supported_languages === "object" ? snapshot.supported_languages : {en:"English"};
    const profileOptions = (selected = "") => [`<option value="">${_fitnessEscape(l.account_unassigned)}</option>`, ...profiles.map((profile) => `<option value="${_fitnessEscape(profile.entry_id)}" ${String(profile.entry_id) === String(selected || "") ? "selected" : ""}>${_fitnessEscape(profile.name || profile.entry_id)}</option>`)].join("");
    const languageOptions = (selected = "en") => Object.entries(supportedLanguages).map(([code, name]) => `<option value="${_fitnessEscape(code)}" ${String(code) === String(selected || "en") ? "selected" : ""}>${_fitnessEscape(name || code)}</option>`).join("");
    const userRows = users.map((user) => {
      const role = String(user.fitness_role || "none");
      const selectedProfile = String(user.fitness_profile_entry_id || "");
      const selectedViewProfiles = new Set(Array.isArray(user.view_profile_entry_ids) ? user.view_profile_entry_ids.map(String) : []);
      const slug = String(user.remote_slug || "");
      const roleOptions = [
        ["none", l.role_none, false],
        ["admin", l.role_admin, !user.is_admin],
        ["local", l.role_local, Boolean(user.is_admin)],
        ["remote", l.role_remote, Boolean(user.is_admin)],
      ].map(([value, text, disabled]) => `<option value="${value}" ${role === value ? "selected" : ""} ${disabled ? "disabled" : ""}>${_fitnessEscape(text)}</option>`).join("");
      const profileMeta = profiles.find((profile) => String(profile.entry_id) === selectedProfile) || null;
      const profileName = profileMeta?.name || selectedProfile;
      const language = String(user.language || profileMeta?.language || "en");
      const remoteUrl = role === "remote" && baseDomain && slug && selectedProfile ? `https://${slug}.${baseDomain}/fitness-tv/profile-${selectedProfile}` : "";
      const badge = user.is_owner
        ? ` · ${l.ha_owner_badge}`
        : (user.is_admin ? ` · ${l.ha_admin_badge}` : "");
      const viewOptions = profiles.filter((item) => String(item.entry_id) !== selectedProfile).map((item) => `<label class="access-view-option"><input type="checkbox" data-access-view-profile value="${_fitnessEscape(item.entry_id)}" ${selectedViewProfiles.has(String(item.entry_id)) ? "checked" : ""} ${user.is_admin ? "disabled" : ""}><span>${_fitnessEscape(item.name || item.entry_id)}</span></label>`).join("");
      return `<div class="access-user-row" data-access-user="${_fitnessEscape(user.user_id)}">
        <div class="access-user-head"><ha-icon icon="${role === "admin" ? "mdi:shield-account" : role === "remote" ? "mdi:web-account" : role === "local" ? "mdi:home-account" : "mdi:account-outline"}"></ha-icon><span><strong>${_fitnessEscape(user.name || user.user_id)}</strong><small>${_fitnessEscape(`${user.is_active ? (l.account_active) : (l.account_inactive)}${badge}`)}</small></span></div>
        <label class="access-role-field"><span>${_fitnessEscape(l.account_role)}</span><select data-access-role>${roleOptions}</select><small data-access-role-hint></small></label>
        <label class="access-profile-field ${role === "none" ? "hidden" : ""}"><span>${_fitnessEscape(l.account_profile)}</span><select data-access-profile>${profileOptions(selectedProfile)}</select><small>${_fitnessEscape(role === "admin" ? (l.admin_own_profile) : (l.account_profile_hint))}</small></label>
        <label class="access-language-field ${role === "none" ? "hidden" : ""}"><span>${_fitnessEscape(l.account_language)}</span><select data-access-language>${languageOptions(language)}</select><small>${_fitnessEscape(l.account_language_hint)}</small></label>
        <label class="access-slug-field ${role === "remote" ? "" : "hidden"}"><span>${_fitnessEscape(l.remote_slug)}</span><div class="access-slug-input"><input data-access-slug value="${_fitnessEscape(slug)}" placeholder="${_fitnessEscape((user.name || "user").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"") || "user")}"><span>${_fitnessEscape(suffix || ".fitness.example.com")}</span></div></label>
        <div class="access-view-field ${role === "none" ? "hidden" : ""}"><span>${_fitnessEscape(l.view_only_profiles)}</span><small>${_fitnessEscape(user.is_admin ? (l.ha_admin_global_access) : (l.view_only_profiles_hint))}</small><div class="access-view-options">${viewOptions || `<em>${_fitnessEscape(l.no_other_profiles)}</em>`}</div></div>
        <div class="access-url">${remoteUrl ? `${_fitnessEscape(l.remote_url)}: <code>${_fitnessEscape(remoteUrl)}</code>` : (role === "local" ? _fitnessEscape(l.local_only_own_profile) : role === "remote" ? _fitnessEscape(l.remote_only_own_profile) : profileName ? _fitnessEscape(profileName) : "")}</div>
        <div class="access-user-actions"><button class="tool" data-access-save><ha-icon icon="mdi:content-save-outline"></ha-icon><span>${_fitnessEscape(l.save_account)}</span></button>${role !== "none" ? `<button class="tool danger" data-access-remove><ha-icon icon="mdi:account-remove-outline"></ha-icon><span>${_fitnessEscape(l.remove_account)}</span></button>` : ""}</div>
      </div>`;
    }).join("");

    this._modal(`<div class="modal-card access-admin-modal"><div class="modal-head"><strong class="modal-title-with-icon"><ha-icon icon="mdi:account-lock-outline"></ha-icon>${_fitnessEscape(l.fitness_accounts)}</strong><button class="icon-tool modal-close"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="access-admin-body">
      <div class="access-intro"><div><strong>${_fitnessEscape(l.fitness_accounts)}</strong><p>${_fitnessEscape(l.fitness_accounts_hint)}</p></div><a class="tool" id="access-ha-users" href="/config/person"><ha-icon icon="mdi:account-cog-outline"></ha-icon><span>${_fitnessEscape(l.manage_ha_users)}</span></a></div>
      <section class="access-section"><div class="access-section-title"><ha-icon icon="mdi:web"></ha-icon><span><strong>${_fitnessEscape(l.remote_base_domain)}</strong><small>${_fitnessEscape(l.remote_base_domain_hint)}</small></span></div><div class="access-domain-row"><input id="access-base-domain" value="${_fitnessEscape(baseDomain)}" placeholder="fitness.example.com"><button class="tool" id="access-save-domain"><ha-icon icon="mdi:content-save-outline"></ha-icon><span>${_fitnessEscape(l.save_domain)}</span></button></div><div class="setting-info"><ha-icon icon="mdi:certificate-outline"></ha-icon><span><strong>${_fitnessEscape(l.wildcard_setup)}</strong><small>${_fitnessEscape(l.wildcard_setup_hint)}</small></span></div></section>
      <section class="access-section"><div class="access-section-title"><ha-icon icon="mdi:account-multiple-outline"></ha-icon><span><strong>${_fitnessEscape(l.fitness_accounts)}</strong><small>${_fitnessEscape(l.fitness_accounts_hint)}</small></span></div><div class="access-user-list">${userRows || `<div class="empty">${_fitnessEscape(l.no_users)}</div>`}</div></section>
      <div class="access-status" id="access-status" aria-live="polite"></div>
    </div></div>`);

    const root = this.shadowRoot?.getElementById("setup-modal");
    if (!root) return;
    const status = root.querySelector("#access-status");
    const setStatus = (message, error = false) => { if (!status) return; status.textContent = String(message || ""); status.classList.toggle("error", Boolean(error)); };
    const refresh = (next) => this._renderAccessAdmin(next || snapshot);

    root.querySelector("#access-save-domain")?.addEventListener("click", async () => {
      const button = root.querySelector("#access-save-domain");
      if (button) button.disabled = true;
      setStatus(l.saving);
      try {
        const next = await this._hass.callWS({type:"fitness/access/settings/save",remote_base_domain:String(root.querySelector("#access-base-domain")?.value || "").trim()});
        refresh(next);
      } catch (err) {
        if (button) button.disabled = false;
        console.error("[Fitness TV] access domain save failed", err);
        setStatus(l.access_save_failed, true);
      }
    });

    root.querySelectorAll("[data-access-user]").forEach((row) => {
      const role = row.querySelector("[data-access-role]");
      const profile = row.querySelector("[data-access-profile]");
      const slug = row.querySelector("[data-access-slug]");
      const language = row.querySelector("[data-access-language]");
      const profileField = row.querySelector(".access-profile-field");
      const languageField = row.querySelector(".access-language-field");
      const viewField = row.querySelector(".access-view-field");
      const roleHint = row.querySelector("[data-access-role-hint]");
      const slugField = row.querySelector(".access-slug-field");
      const url = row.querySelector(".access-url");
      const updateRole = () => {
        const current = String(role?.value || "none");
        const withoutProfile = current === "none";
        if (profile) profile.disabled = withoutProfile;
        profileField?.classList.toggle("hidden", withoutProfile);
        languageField?.classList.toggle("hidden", withoutProfile);
        viewField?.classList.toggle("hidden", withoutProfile);
        slugField?.classList.toggle("hidden", current !== "remote");
        if (roleHint) roleHint.textContent = current === "admin"
          ? (l.role_admin_hint)
          : current === "local"
            ? (l.role_local_hint)
            : current === "remote"
              ? (l.role_remote_hint)
              : (l.role_none_hint);
        if (url) {
          if (current === "local") url.textContent = l.local_only_own_profile;
          else if (current === "remote") {
            const slugValue = String(slug?.value || "").trim().toLowerCase();
            const profileValue = String(profile?.value || "");
            url.innerHTML = baseDomain && slugValue && profileValue ? `${_fitnessEscape(l.remote_url)}: <code>${_fitnessEscape(`https://${slugValue}.${baseDomain}/fitness-tv/profile-${profileValue}`)}</code>` : _fitnessEscape(l.remote_only_own_profile);
          } else if (current === "admin") {
            const profileValue = String(profile?.value || "");
            url.textContent = profileValue
              ? (l.admin_own_profile)
              : (l.admin_profile_optional);
          } else url.textContent = "";
        }
      };
      role?.addEventListener("change", updateRole);
      profile?.addEventListener("change", updateRole);
      slug?.addEventListener("input", updateRole);
      updateRole();
      row.querySelector("[data-access-save]")?.addEventListener("click", async () => {
        const button = row.querySelector("[data-access-save]");
        if (button) button.disabled = true;
        setStatus(l.saving);
        try {
          const selectedRole = String(role?.value || "none");
          let next;
          if (selectedRole === "none") {
            next = await this._hass.callWS({type:"fitness/access/account/delete",user_id:String(row.dataset.accessUser || "")});
          } else {
            next = await this._hass.callWS({
              type:"fitness/access/account/save",
              user_id:String(row.dataset.accessUser || ""),
              role:selectedRole,
              profile_entry_id:String(profile?.value || ""),
              remote_slug:String(slug?.value || "").trim(),
              language:String(language?.value || "en"),
              view_profile_entry_ids:Array.from(row.querySelectorAll("[data-access-view-profile]:checked")).map((input) => String(input.value || "")).filter(Boolean),
            });
          }
          refresh(next);
        } catch (err) {
          if (button) button.disabled = false;
          console.error("[Fitness TV] access account save failed", err);
          setStatus(l.access_save_failed, true);
        }
      });
      row.querySelector("[data-access-remove]")?.addEventListener("click", async () => {
        if (!confirm(l.remove_account_confirm)) return;
        try {
          const next = await this._hass.callWS({type:"fitness/access/account/delete",user_id:String(row.dataset.accessUser || "")});
          refresh(next);
        } catch (err) {
          console.error("[Fitness TV] access account removal failed", err);
          setStatus(l.access_save_failed, true);
        }
      });
    });

  }

  _style() {
    return `<style>
      .tool>span,.primary-tool>span,.adapter-setup>span,.add-profile-row>span{display:block!important;min-width:0;max-width:100%;font-size:clamp(11px,.8vw,13px)!important;line-height:1.2!important;white-space:nowrap!important;overflow:hidden;text-overflow:ellipsis;word-break:normal;overflow-wrap:normal!important}
      .overview-cast-target.unavailable{opacity:.48;filter:grayscale(.82);cursor:not-allowed}.overview-cast-target.unavailable:hover{transform:none;box-shadow:none;border-color:var(--divider-color)}
      :host{display:block;width:100%;max-width:none;background:var(--primary-background-color);color:var(--primary-text-color)}*{box-sizing:border-box}.setup-shell{border:0;border-radius:0;box-shadow:none;background:var(--primary-background-color);padding:20px;min-height:100vh}.setup-head{display:flex;justify-content:space-between;gap:18px;align-items:center;padding:20px;border-radius:26px;background:var(--card-background-color);margin-bottom:16px;border:1px solid color-mix(in srgb,var(--divider-color) 72%,transparent);box-shadow:0 12px 34px rgba(0,0,0,.12)}.setup-title{display:flex;align-items:center;gap:9px;font-size:23px}.setup-title .fitness-brand-icon{width:30px;height:30px;object-fit:contain;flex:0 0 30px}.setup-head p{margin:6px 0 0;color:var(--secondary-text-color);max-width:760px}.setup-actions,.profile-actions{display:flex;align-items:center;gap:8px;flex-wrap:nowrap;min-width:0}.setup-actions>.tool,.profile-actions>.tool{flex:1 1 0;min-width:0}.setup-actions>.tool span,.profile-actions>.tool span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.profiles-list{display:grid;gap:10px}.profile-row{display:grid;grid-template-columns:46px minmax(170px,1fr) auto auto;gap:12px;align-items:center;padding:15px 17px;border-radius:22px;background:var(--card-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 74%,transparent);box-shadow:0 8px 24px rgba(0,0,0,.08);transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease}.profile-row:hover{transform:translateY(-1px);border-color:color-mix(in srgb,var(--primary-color) 32%,var(--divider-color));box-shadow:0 12px 30px rgba(0,0,0,.11)}.admin-profile-link{cursor:pointer}.admin-profile-link:focus-visible{outline:2px solid var(--primary-color);outline-offset:3px}.profile-row.tv-disabled{opacity:.78}.profile-row.tv-disabled .profile-avatar{filter:saturate(.35)}.profile-avatar{width:42px;height:42px;display:grid;place-items:center;border-radius:16px;background:color-mix(in srgb,var(--primary-color) 14%,transparent);color:var(--primary-color)}.profile-avatar ha-icon{--mdc-icon-size:25px}.profile-copy{min-width:0}.profile-copy strong,.profile-copy span,.profile-copy small{display:block}.profile-copy strong{font-size:17px}.profile-copy span{font-size:12px;color:var(--secondary-text-color);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.profile-copy small{font-size:10px;color:var(--secondary-text-color);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.profile-process-status:not(:empty){color:var(--primary-color);font-weight:600}.profile-badges{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.profile-badges span{display:inline-flex;align-items:center;gap:3px;padding:5px 7px;border-radius:9px;background:var(--secondary-background-color);font-size:10px;color:var(--secondary-text-color)}.profile-badges ha-icon{--mdc-icon-size:13px}.tool,.icon-tool,select{font:inherit;color:var(--primary-text-color);background:var(--secondary-background-color);border:1px solid var(--divider-color);border-radius:15px;min-height:40px}.tool,.icon-tool{cursor:pointer;transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease;display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:0 11px}.icon-tool{width:40px;padding:0}.empty{padding:28px;text-align:center;color:var(--secondary-text-color);border-radius:16px;background:var(--card-background-color)}.modal-backdrop{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.54);display:grid;place-items:center;padding:clamp(8px,2.5vh,24px);overflow:hidden;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}.modal-card{width:min(820px,calc(100vw - 16px));max-width:calc(100vw - 16px);height:auto;max-height:calc(100dvh - 16px);overflow:hidden;display:flex;flex-direction:column;min-height:0;border-radius:28px;background:var(--card-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 72%,transparent);box-shadow:0 28px 90px rgba(0,0,0,.48)}.modal-auto-scroll-body{flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch}.add-profile-list{flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch}#backend-flow-host{display:block;flex:1 1 auto;min-height:0;overflow:hidden!important}.configure-modal{overflow:hidden!important;display:flex;flex-direction:column;height:min(860px,calc(100dvh - 16px));max-height:calc(100dvh - 16px)}.configure-modal .profile-settings{min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch;flex:1 1 auto}.configure-modal>.settings-actions{flex:0 0 auto;position:relative;bottom:auto;z-index:4;padding:11px 15px;background:color-mix(in srgb,var(--card-background-color) 97%,transparent);border-top:1px solid color-mix(in srgb,var(--divider-color) 68%,transparent)}.modal-head{position:sticky;top:0;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:13px 15px;background:var(--card-background-color);border-bottom:1px solid var(--divider-color)}.add-profile-list{display:grid;gap:7px;padding:12px}.add-profile-row{display:grid;grid-template-columns:30px 1fr 24px;gap:9px;align-items:center;padding:13px;border:1px solid color-mix(in srgb,var(--divider-color) 70%,transparent);border-radius:18px;background:var(--secondary-background-color);color:var(--primary-text-color);text-align:left;cursor:pointer}.profile-settings{display:grid;gap:12px;padding:15px}.setting-toggle,.setting-field,.setting-range{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center;padding:13px;border-radius:18px;background:var(--secondary-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 70%,transparent)}.setting-field{grid-template-columns:180px minmax(0,1fr)}.setting-field select{width:100%;padding:0 10px}.setting-range{grid-template-columns:minmax(0,1fr) minmax(180px,280px) 48px}.setting-toggle small,.setting-range small,.setting-info small{display:block;margin-top:3px;color:var(--secondary-text-color);font-size:10px}.setting-title,.modal-title-with-icon{display:inline-flex;align-items:center;gap:7px}.setting-title ha-icon,.modal-title-with-icon ha-icon{--mdc-icon-size:20px;color:var(--primary-color)}.setting-info{display:grid;grid-template-columns:28px minmax(0,1fr);gap:10px;align-items:center;padding:12px;border-radius:13px;background:var(--secondary-background-color)}.setting-info ha-icon{color:var(--primary-color)}.setting-adapters{display:grid;gap:10px;padding:12px;border-radius:13px;background:var(--secondary-background-color)}.setting-adapters>div>small{display:block;margin-top:3px;color:var(--secondary-text-color);font-size:10px}.music-adapter-list,.music-adapter-picker{display:grid;gap:7px}.music-adapter-row{display:grid;grid-template-columns:22px 24px minmax(0,1fr) auto;gap:9px;align-items:center;padding:9px;border-radius:10px;background:color-mix(in srgb,var(--card-background-color) 65%,transparent)}.music-adapter-row input{width:18px;height:18px}.music-adapter-row ha-icon{--mdc-icon-size:20px}.music-adapter-row img{width:20px;height:20px;object-fit:contain}.music-adapter-row small,.music-adapter-row strong{display:block}.music-adapter-row small{color:var(--secondary-text-color);font-size:10px;margin-top:2px}.music-adapter-row.unavailable{opacity:.58}.adapter-actions{display:flex;align-items:center;justify-content:flex-end;gap:6px;flex-wrap:nowrap;min-width:0}.adapter-actions>*{flex:1 1 0;min-width:0;max-width:190px}.adapter-account{font:inherit;max-width:190px;min-height:32px;padding:0 6px;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:9px}.adapter-setup{font:inherit;font-size:11px;color:var(--primary-color);background:transparent;border:1px solid var(--divider-color);border-radius:9px;padding:6px 8px;cursor:pointer}.music-adapter-picker .music-adapter-row{grid-template-columns:22px 24px minmax(0,1fr)}.music-search-modal{overflow:hidden!important;display:flex;flex-direction:column;height:min(820px,calc(100dvh - var(--modal-top,68px) - 26px));max-height:calc(100dvh - var(--modal-top,68px) - 26px);min-height:0}.provider-catalog-modal{overflow:hidden!important;display:flex;flex-direction:column;height:min(820px,calc(100dvh - 32px));max-height:calc(100dvh - 32px);min-height:0}.provider-catalog-list{flex:1 1 auto;min-height:0;max-height:100%;overflow-y:auto!important;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch}.music-search-form{display:flex;flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch;flex-direction:column;gap:12px;padding:14px}.music-search-form>.field-label,.music-search-form>.music-search-status,.music-search-form>.music-search-error,.music-search-form>.modal-actions{flex:0 0 auto}.music-search-form>.music-adapter-picker{flex:0 0 auto;min-height:auto;overflow:visible}.music-type-filter{display:grid;gap:7px;padding:10px 11px;border-radius:14px;background:var(--secondary-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 64%,transparent)}.music-type-filter-title{font-size:11px;font-weight:700;color:var(--secondary-text-color)}.music-type-options{display:flex;gap:7px;flex-wrap:wrap}.music-type-option{display:inline-flex;align-items:center;gap:6px;padding:7px 9px;border-radius:11px;background:var(--card-background-color);border:1px solid var(--divider-color);cursor:pointer;white-space:nowrap}.music-type-option input{width:16px;height:16px;margin:0}.music-type-option ha-icon{--mdc-icon-size:18px;color:var(--primary-color)}.music-type-option span{font-size:11px}.provider-catalog-list{display:grid;gap:9px;padding:14px}.provider-catalog-row{display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:10px;align-items:center;padding:11px;border-radius:12px;background:var(--secondary-background-color)}.provider-catalog-row ha-icon{color:var(--primary-color)}.provider-catalog-row span strong,.provider-catalog-row span small{display:block}.provider-catalog-row span small{margin-top:3px;color:var(--secondary-text-color);font-size:10px}.setting-adapters-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.setting-adapters-head .adapter-setup{white-space:nowrap}.browser-working{display:flex;gap:9px;align-items:center;padding:12px;border-radius:11px;background:var(--secondary-background-color);color:var(--secondary-text-color)}.spin{animation:fitness-spin 1s linear infinite}@keyframes fitness-spin{to{transform:rotate(360deg)}}.setting-range input{width:100%}.setting-range output{text-align:right;font-weight:700}.setting-toggle input{width:20px;height:20px}.settings-actions{display:flex;align-items:center;gap:10px;justify-content:flex-end;flex-wrap:nowrap;min-width:0}.settings-actions>button{flex:1 1 0;min-width:0}.settings-actions>button span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.settings-status{font-size:12px;color:var(--secondary-text-color)}.access-admin-modal{overflow:hidden;display:flex;flex-direction:column;width:min(980px,calc(100vw - 16px));height:min(900px,calc(100dvh - 16px));max-height:calc(100dvh - 16px)}.access-admin-body{min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;padding:16px;display:grid;gap:14px}.access-intro{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px;border-radius:20px;background:color-mix(in srgb,var(--primary-color) 8%,var(--secondary-background-color));border:1px solid color-mix(in srgb,var(--primary-color) 20%,var(--divider-color))}.access-intro p{margin:0;color:var(--secondary-text-color);max-width:680px}.access-section{display:grid;gap:12px;padding:15px;border-radius:22px;background:var(--secondary-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 72%,transparent)}.access-section-title{display:flex;gap:10px;align-items:flex-start}.access-section-title>ha-icon{color:var(--primary-color);margin-top:2px}.access-section-title strong,.access-section-title small{display:block}.access-section-title small{margin-top:3px;color:var(--secondary-text-color);font-size:11px}.access-domain-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px}.access-domain-row input,.access-user-row input,.access-user-row select{width:100%;min-height:40px;border-radius:13px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);padding:0 11px;font:inherit}.access-user-list{display:grid;gap:10px}.access-user-row{display:grid;grid-template-columns:minmax(170px,1.2fr) minmax(180px,.9fr) minmax(230px,1.15fr);gap:10px;align-items:end;padding:14px;border-radius:18px;background:var(--card-background-color);border:1px solid color-mix(in srgb,var(--divider-color) 72%,transparent)}.access-user-head{display:flex;align-items:center;gap:9px;align-self:center}.access-user-head>ha-icon{color:var(--primary-color)}.access-user-head strong,.access-user-head small{display:block}.access-user-head small{margin-top:2px;color:var(--secondary-text-color);font-size:10px}.access-user-row label>span{display:block;margin:0 0 5px;font-size:11px;color:var(--secondary-text-color)}.access-role-field,.access-profile-field,.access-language-field{display:block;min-width:0;align-self:stretch}.access-role-field select,.access-profile-field select,.access-language-field select{width:100%;min-height:40px;border-radius:13px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);padding:0 11px;font:inherit}.access-role-field small,.access-profile-field small,.access-language-field small{display:block;margin-top:5px;color:var(--secondary-text-color);font-size:10px;line-height:1.3}.access-view-field{grid-column:1/-1}.access-view-field>span{display:block;margin:0 0 4px;font-size:11px;color:var(--secondary-text-color)}.access-view-field>small{display:block;margin-bottom:7px;color:var(--secondary-text-color);font-size:10px;line-height:1.35}.access-view-options{display:flex;gap:7px;flex-wrap:wrap}.access-view-option{display:inline-flex!important;align-items:center;gap:6px;padding:7px 9px;border:1px solid var(--divider-color);border-radius:11px;background:var(--secondary-background-color)}.access-view-option input{margin:0}.access-view-option span{margin:0!important;color:var(--primary-text-color)!important}.access-view-options em{color:var(--secondary-text-color);font-size:11px}.access-slug-field{grid-column:2/4}.access-slug-input{display:flex;align-items:center;border:1px solid var(--divider-color);border-radius:13px;background:var(--card-background-color);overflow:hidden}.access-slug-input input{border:0;border-radius:0;min-width:80px}.access-slug-input span{padding:0 9px;color:var(--secondary-text-color);font-size:11px;white-space:nowrap}.access-url{grid-column:1/-1;min-height:16px;font-size:11px;color:var(--secondary-text-color);overflow-wrap:anywhere}.access-url code{color:var(--primary-text-color)}.access-user-actions{grid-column:1/-1;display:flex;justify-content:flex-end;gap:8px;flex-wrap:nowrap;min-width:0}.access-user-actions>button{flex:1 1 0;min-width:0}.access-user-actions>button span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tool.danger{color:var(--error-color);border-color:color-mix(in srgb,var(--error-color) 35%,var(--divider-color))}.modal-card{max-height:calc(100dvh - 16px);overflow:hidden;display:flex;flex-direction:column;min-height:0;overscroll-behavior:contain}.configure-modal,.browser-modal,.picker-modal,.cast-modal,.remote-gateway-modal,.provider-catalog-modal,.music-search-modal,.ytdlp-legal-modal,.access-admin-modal{overflow:hidden!important;display:flex;flex-direction:column;min-height:0}.configure-modal{height:min(860px,calc(100dvh - 16px));max-height:calc(100dvh - 16px)}.configure-modal>.profile-settings{flex:1 1 auto;min-height:0;overflow-y:auto!important;overflow-x:hidden!important}.backend-flow-modal{height:min(900px,calc(100dvh - 16px));max-height:calc(100dvh - 16px);overflow:hidden!important}.backend-flow-host{display:block;flex:1 1 auto;min-height:0;overflow:hidden!important}.backend-flow-host>fitness-backend-flow{display:block;height:100%;min-height:0;overflow:hidden}.profile-settings,.picker-list,.media-list,.cast-picker,.remote-gateway-body,.provider-catalog-list,.music-search-form,.modal-scroll-body,.playlist-list,.playlist-edit-list,.music-source-list,.access-admin-body,.add-profile-list{min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;-webkit-overflow-scrolling:touch}.browser-modal>.media-list,.browser-modal>.playlist-list,.browser-modal>.music-source-list,.picker-modal>.picker-list,.cast-modal>.cast-picker,.remote-gateway-modal>.remote-gateway-body,.provider-catalog-modal>.provider-catalog-list,.access-admin-modal>.access-admin-body{flex:1 1 auto}.modal-head{position:sticky!important;top:0;z-index:30;flex:0 0 auto;background:color-mix(in srgb,var(--card-background-color) 96%,transparent);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}.modal-actions,.settings-actions{position:sticky;bottom:0;z-index:24;flex:0 0 auto;padding:12px 14px;background:color-mix(in srgb,var(--card-background-color) 96%,transparent);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border-top:1px solid color-mix(in srgb,var(--divider-color) 68%,transparent)}.configure-modal>.settings-actions{position:relative;bottom:auto}.modal-scroll-body{padding:14px}.hidden,[hidden]{display:none!important}.access-status{position:sticky;bottom:0;min-height:18px;padding:5px 2px;background:var(--card-background-color);color:var(--secondary-text-color);font-size:12px}.access-status.error{color:var(--error-color)}.setup-actions,.profile-actions,.settings-actions,.modal-actions,.access-user-actions,.flow-actions{flex-wrap:nowrap!important;min-width:0}.setup-actions>button,.profile-actions>button,.settings-actions>button,.modal-actions>button,.access-user-actions>button,.flow-actions>button{flex:1 1 0;min-width:0;max-width:100%}.setup-actions>button span,.profile-actions>button span,.settings-actions>button span,.modal-actions>button span,.access-user-actions>button span,.flow-actions>button span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}@media(max-width:800px){.setup-head{align-items:flex-start;flex-direction:column}.profile-row{grid-template-columns:42px 1fr}.profile-badges,.profile-actions{grid-column:2}.setting-field,.setting-range{grid-template-columns:1fr}.setting-range output{text-align:left}.access-intro{align-items:stretch;flex-direction:column}.access-domain-row,.access-user-row{grid-template-columns:1fr}.access-user-actions,.access-url{grid-column:1}}
      /* Keep translated modal actions intrinsic and readable; inline-size containment makes label-bearing buttons collapse. */
      .setting-adapters-head>span{min-width:0}.setting-adapters-head>span>strong,.setting-adapters-head>span>small{display:block}.setting-adapters-head>span>small{margin-top:4px;color:var(--secondary-text-color);font-size:10px;line-height:1.4}
      .setting-adapters-head{gap:12px}.setting-adapters-head .adapter-setup{flex:0 0 auto;min-width:clamp(132px,18vw,190px);min-height:40px;white-space:normal}
      .adapter-actions>*{flex:0 1 auto;min-width:104px;max-width:190px}.adapter-actions>.adapter-account{flex:1 1 140px;min-width:120px}.adapter-actions>.adapter-setup{min-width:112px;min-height:36px}.adapter-actions>.adapter-remove{min-width:102px}
      .adapter-actions>.adapter-setup>span,.provider-catalog-row>.adapter-setup>span,.setting-adapters-head>.adapter-setup>span{white-space:normal!important;overflow:visible!important;text-overflow:clip!important;word-break:normal;overflow-wrap:normal!important}
      .provider-catalog-row>.adapter-setup{min-width:clamp(132px,16vw,190px);min-height:40px;white-space:normal}
      /* Cross-device setup reliability: safe areas, full-width mobile rows and touch targets. */
      .setup-shell{min-height:100dvh}
      .modal-backdrop{padding-top:max(clamp(8px,2.5vh,24px),env(safe-area-inset-top));padding-right:max(clamp(8px,2.5vh,24px),env(safe-area-inset-right));padding-bottom:max(clamp(8px,2.5vh,24px),env(safe-area-inset-bottom));padding-left:max(clamp(8px,2.5vh,24px),env(safe-area-inset-left))}
      .tool:focus-visible,.icon-tool:focus-visible,.primary-tool:focus-visible,.adapter-setup:focus-visible,.add-profile-row:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
      @media(max-width:800px){
        .setup-shell{padding:12px}.setup-head{padding:15px}.setup-title{font-size:20px;min-width:0}
        .setup-actions,.profile-actions{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}
        .profile-badges,.profile-actions{grid-column:1/-1}.profile-actions>.profile-assign{grid-column:1/-1}.profile-actions>.icon-tool{width:100%}
        .access-slug-field,.access-view-field,.access-user-actions,.access-url{grid-column:1}
        .tool,.icon-tool,.primary-tool,.adapter-setup,.add-profile-row,.access-domain-row input,.access-user-row input,.access-user-row select{min-height:44px}
        input:not([type="checkbox"]):not([type="range"]),select{font-size:16px}
        .setting-adapters-head{display:grid;grid-template-columns:1fr}.setting-adapters-head .adapter-setup{width:100%;max-width:none;white-space:normal}
        .music-adapter-row{grid-template-columns:22px 24px minmax(0,1fr)}
        .adapter-actions{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}
        .adapter-actions>*{width:100%;min-width:0;max-width:none;min-height:44px}.adapter-actions .adapter-account{grid-column:1/-1;min-width:0;max-width:none}
        .provider-catalog-row{grid-template-columns:30px minmax(0,1fr)}.provider-catalog-row>.adapter-setup{grid-column:1/-1;width:100%;max-width:none;min-width:0}
      }
      @media(max-width:520px){
        .setting-adapters-head{display:grid;grid-template-columns:1fr}.setting-adapters-head .adapter-setup{width:100%;white-space:normal}
        .music-adapter-row{grid-template-columns:22px 24px minmax(0,1fr)}
        .adapter-actions{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}
        .adapter-actions>*{width:100%;max-width:none;min-height:44px}.adapter-actions .adapter-account{grid-column:1/-1;max-width:none}
        .provider-catalog-row{grid-template-columns:30px minmax(0,1fr)}.provider-catalog-row>.adapter-setup{grid-column:1/-1;width:100%}
        .access-user-actions,.settings-actions,.modal-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}
      }
    </style>`;
  }
}

class FitnessTvDashboardStrategy extends HTMLElement {
  static getCreateSuggestions() {
    return {title:"Fitness TV", icon:"mdi:television-play"};
  }

  static async generate(config, hass) {
    const data = await hass.callWS({type:"fitness/dashboard/config"});
    const allProfiles = data?.profiles || [];
    const profiles = allProfiles.filter((profile) => profile.tv_dashboard?.enabled);
    const labelProfile = profiles[0] || allProfiles[0];
    const ui = String(labelProfile?.language || hass?.language || "en").toLowerCase().split("-")[0];
    const labels = labelProfile?.labels_by_language?.[ui] || labelProfile?.labels_by_language?.en || labelProfile?.labels || {};
    const title = config?.title || labels.tv_dashboard;
    const isAdmin = Boolean(data?.access?.is_admin);
    if (!isAdmin) {
      // Never generate the administrator overview for ordinary users. The
      // sidebar lands directly on the user's own Fitness profile (or the first
      // explicitly granted view-only profile when no owned profile exists).
      const primary = profiles.find((profile) => profile?.access?.is_own) || profiles[0];
      if (!primary) {
        return {title, views:[{title,path:"main",panel:true,cards:[{type:`custom:${FITNESS_TV_LOVELACE_SETUP_CARD_TAG}`}]}]};
      }
      const views = [{
        title:primary.profile_name || title,
        path:"main",
        panel:true,
        cards:[{type:`custom:${FITNESS_TV_LOVELACE_SETUP_CARD_TAG}`, profile_entry_id:primary.entry_id}],
      }];
      for (const profile of profiles) {
        if (profile.entry_id === primary.entry_id) continue;
        views.push({
          title:profile.profile_name || title,
          path:`profile-${profile.entry_id}`,
          subview:true,
          back_path:"/fitness-tv/main",
          cards:[{type:`custom:${FITNESS_TV_LOVELACE_SETUP_CARD_TAG}`, profile_entry_id:profile.entry_id}],
        });
      }
      return {title, views};
    }
    const views = [{
      title,
      path:"main",
      panel:true,
      cards:[{type:`custom:${FITNESS_TV_LOVELACE_SETUP_CARD_TAG}`}],
    }];
    for (const profile of profiles) {
      views.push({
        title:profile.profile_name || title,
        path:`profile-${profile.entry_id}`,
        subview:true,
        back_path:"/fitness-tv/main",
        cards:[{
          type:`custom:${FITNESS_TV_LOVELACE_SETUP_CARD_TAG}`,
          profile_entry_id:profile.entry_id,
        }],
      });
    }
    return {title, views};
  }
}


const _FITNESS_TAB_PANEL_BASE = `
  ha-card{
    padding:10px !important;
    border:0 !important;
    border-radius:22px !important;
    box-shadow:0 8px 22px rgba(0,0,0,.08) !important;
    overflow:hidden !important;
    border:1px solid color-mix(in srgb,var(--divider-color) 68%,transparent) !important;
    background:var(--secondary-background-color) !important;
  }
  .title,h3{
    margin:0 !important;
    padding:2px 4px 7px !important;
    font-size:15px !important;
    line-height:1.2 !important;
    font-weight:650 !important;
  }
  .empty{
    padding:10px !important;
    border-radius:14px !important;
    background:var(--card-background-color) !important;
  }
`;

const _fitnessInstallTabPanelTheme = (CardClass, extraCss = "") => {
  if (!CardClass?.prototype?._render || CardClass.prototype._fitnessTabPanelTheme) return;
  const original = CardClass.prototype._render;
  CardClass.prototype._render = function (...args) {
    const result = original.apply(this, args);
    const root = this.shadowRoot;
    if (root && !root.querySelector("style[data-fitness-tab-panel]")) {
      const style = document.createElement("style");
      style.dataset.fitnessTabPanel = "1";
      style.textContent = _FITNESS_TAB_PANEL_BASE + extraCss;
      root.appendChild(style);
    }
    return result;
  };
  CardClass.prototype._fitnessTabPanelTheme = true;
};

_fitnessInstallTabPanelTheme(FitnessWorkoutHighlightsCard, `
  .workout-name{
    padding:3px 4px 8px !important;
    font-size:16px !important;
  }
  .hi-grid{gap:7px !important;margin-top:0 !important}
  .hi{padding:9px 10px 10px !important;border-radius:12px !important}
  .hi-icon{width:24px !important;height:24px !important;flex-basis:24px !important}
  .hi-icon ha-icon{--mdc-icon-size:15px !important}
  .hi-label{font-size:9px !important}
  .hi-value{font-size:14px !important;margin-top:6px !important}
`);

_fitnessInstallTabPanelTheme(FitnessRouteCard, `
  .head{padding:2px 4px 7px !important}
  .map{border-radius:14px !important;overflow:hidden !important}
  .workout-summary{
    gap:6px !important;padding:7px 0 0 !important;
  }
  .summary-item{
    padding:8px 9px !important;border-radius:11px !important;
    background:var(--card-background-color) !important;
  }
  .privacy{padding:6px 3px 1px !important}
`);

_fitnessInstallTabPanelTheme(FitnessWorkoutRpeCard, `
  .head{
    padding:9px !important;border-radius:14px !important;
    background:var(--card-background-color) !important;
  }
  .rpe-scale{
    padding:8px !important;border-radius:14px !important;
    background:var(--card-background-color) !important;
    margin-top:7px !important;
  }
  .foot{
    padding:7px 8px !important;border-radius:12px !important;
    background:var(--card-background-color) !important;
    margin-top:7px !important;
  }
`);

_fitnessInstallTabPanelTheme(FitnessComparisonCard, `
  .rows{padding:0 !important;display:grid !important;gap:6px !important}
  .row{
    margin:0 !important;padding:9px 10px !important;border-radius:12px !important;
    background:var(--card-background-color) !important;
  }
  .axis-values b{background:var(--secondary-background-color) !important}
`);

_fitnessInstallTabPanelTheme(FitnessStrengthDetailsCard, `
  .strength-head{padding:3px 4px 7px !important}
  .volume-hero{
    margin:0 0 6px !important;padding:9px 10px !important;border-radius:12px !important;
    background:var(--card-background-color) !important;
  }
  .strength-list{gap:6px !important;margin-top:0 !important}
  .strength-row{
    padding:9px 10px !important;border-radius:12px !important;
    background:var(--card-background-color) !important;
  }
`);

_fitnessInstallTabPanelTheme(FitnessRecoveryCard, `
  .title{padding:2px 4px 7px !important}
  .recovery-readiness-panel{
    margin-top:0 !important;padding:0 !important;border-radius:0 !important;
    background:transparent !important;
  }
  .section-label{padding:0 4px 6px !important}
  .readiness-panel,.next-workout{
    border-radius:14px !important;
  }
  .readiness-panel{
    padding:10px !important;
    background:linear-gradient(
      135deg,
      color-mix(in srgb,var(--readiness) 12%,transparent),
      var(--card-background-color)
    ) !important;
  }
  .next-workout{
    margin-top:6px !important;padding:10px !important;
    border-left:0 !important;
    background:linear-gradient(
      135deg,
      color-mix(in srgb,var(--recovery) 10%,transparent),
      var(--card-background-color)
    ) !important;
  }
  .recovery-grid{gap:6px !important;margin-top:7px !important}
  .recovery-grid>div{
    padding:8px 9px !important;border-radius:11px !important;
    background:var(--card-background-color) !important;
  }
  .components{gap:6px !important;margin-top:7px !important}
  .component{
    padding:8px 9px !important;border-radius:11px !important;
    background:var(--card-background-color) !important;
  }
  .context{
    padding:7px 8px !important;border-radius:11px !important;
    background:var(--card-background-color) !important;
    margin-top:7px !important;
  }
`);

_fitnessInstallTabPanelTheme(FitnessSleepStageCard, `
  .body{gap:10px !important;padding:3px 0 0 !important}
  .donut{
    margin:0 auto !important;
    box-shadow:0 0 0 8px var(--card-background-color) !important;
  }
  .legend{
    padding:7px 9px !important;border-radius:14px !important;
    background:var(--card-background-color) !important;
  }
  .legend-row{padding:5px 0 !important}
  .sleep-summary{
    gap:6px !important;padding-top:7px !important;border-top:0 !important;
  }
  .sleep-summary-metric{
    padding:8px 9px !important;border-radius:11px !important;
    background:var(--card-background-color) !important;
  }
`);

_fitnessInstallTabPanelTheme(FitnessProgressCard, `
  .hero,.current,.summary,.history,.progress-wrap{
    border-radius:14px !important;
  }
  .hero,.current,.summary,.history{
    background:var(--card-background-color) !important;
  }
  .metrics{
    gap:6px !important;margin-top:7px !important;
  }
  .metric{
    padding:8px 9px !important;border-radius:11px !important;
    background:var(--card-background-color) !important;
  }
`);

_fitnessInstallTabPanelTheme(FitnessTrainingAdaptationCard, `
  .hero{
    padding:10px !important;border-radius:14px !important;
    background:linear-gradient(
      135deg,
      color-mix(in srgb,var(--adapt) 12%,transparent),
      var(--card-background-color)
    ) !important;
  }
  .metrics{gap:6px !important;margin-top:6px !important}
  .metrics>div{
    padding:8px 9px !important;border-radius:11px !important;
    background:var(--card-background-color) !important;
  }
  .evidence{
    padding:6px 8px !important;border-radius:10px !important;
    background:var(--card-background-color) !important;
  }
`);

_fitnessInstallTabPanelTheme(FitnessTrainingLoadCard, `
  .header{
    padding:9px 10px !important;border-radius:14px !important;
    background:var(--card-background-color) !important;
  }
  .adapt-summary{
    border-left:0 !important;
    background:color-mix(in srgb,var(--adapt) 8%,var(--secondary-background-color)) !important;
  }
  .load-scale,.status-row{
    padding:8px 9px !important;border-radius:12px !important;
    background:var(--card-background-color) !important;
  }
  .load-scale{margin-top:6px !important;height:auto !important}
  .status-row{margin-top:6px !important}
  .metrics{gap:6px !important;margin-top:6px !important}
  .metrics>div{
    padding:8px 9px !important;border-radius:11px !important;
    background:var(--card-background-color) !important;
  }
`);

_fitnessInstallTabPanelTheme(FitnessTodayCard, `
  .today-head{padding:3px 4px 7px !important}
  .today-grid{gap:6px !important;margin-top:0 !important}
  .today-item{
    padding:8px 9px !important;border-radius:11px !important;
    background:var(--card-background-color) !important;
  }
`);

class FitnessComparisonCardEditor extends FitnessProfileCardEditor {}
class FitnessSleepStageCardEditor extends FitnessProfileCardEditor {}

if (!customElements.get("fitness-profile-card-editor")) customElements.define("fitness-profile-card-editor", FitnessProfileCardEditor);
if (!customElements.get("fitness-today-card")) customElements.define("fitness-today-card", FitnessTodayCard);
if (!customElements.get("fitness-workout-card")) customElements.define("fitness-workout-card", FitnessWorkoutCard);
if (!customElements.get("fitness-live-workout-card")) customElements.define("fitness-live-workout-card", FitnessLiveWorkoutCard);
if (!customElements.get("fitness-sleep-recovery-card")) customElements.define("fitness-sleep-recovery-card", FitnessSleepRecoveryCard);
if (!customElements.get("fitness-evaluation-card")) customElements.define("fitness-evaluation-card", FitnessEvaluationCard);
if (!customElements.get("fitness-workout-highlights-card")) customElements.define("fitness-workout-highlights-card", FitnessWorkoutHighlightsCard);
if (!customElements.get("fitness-workout-rpe-card")) customElements.define("fitness-workout-rpe-card", FitnessWorkoutRpeCard);
if (!customElements.get("fitness-strength-details-card")) customElements.define("fitness-strength-details-card", FitnessStrengthDetailsCard);
if (!customElements.get("fitness-progress-card")) customElements.define("fitness-progress-card", FitnessProgressCard);
if (!customElements.get("fitness-recovery-card")) customElements.define("fitness-recovery-card", FitnessRecoveryCard);
if (!customElements.get("fitness-training-adaptation-card")) customElements.define("fitness-training-adaptation-card", FitnessTrainingAdaptationCard);
if (!customElements.get("fitness-training-load-card")) customElements.define("fitness-training-load-card", FitnessTrainingLoadCard);
if (!customElements.get("fitness-route-card-editor")) customElements.define("fitness-route-card-editor", FitnessRouteCardEditor);
if (!customElements.get("fitness-comparison-card-editor")) customElements.define("fitness-comparison-card-editor", FitnessComparisonCardEditor);
if (!customElements.get("fitness-sleep-stage-card-editor")) customElements.define("fitness-sleep-stage-card-editor", FitnessSleepStageCardEditor);
if (!customElements.get("fitness-route-card")) customElements.define("fitness-route-card", FitnessRouteCard);
if (!customElements.get("fitness-comparison-card")) customElements.define("fitness-comparison-card", FitnessComparisonCard);
if (!customElements.get("fitness-sleep-stage-card")) customElements.define("fitness-sleep-stage-card", FitnessSleepStageCard);
const _fitnessDefineCustomElement = (tag, BaseClass) => {
  if (customElements.get(tag)) return;
  // A CustomElementRegistry may not register the same constructor under more
  // than one tag. Each compatibility alias therefore receives its own
  // lightweight subclass instead of reusing BaseClass directly.
  customElements.define(tag, class extends BaseClass {});
};

for (const tag of [FITNESS_TV_DASHBOARD_CARD_TAG, "fitness-tv-dashboard-card", "fitness-tv-dashboard-card-v70", "fitness-tv-dashboard-card-v71", "fitness-tv-dashboard-card-v72", "fitness-tv-dashboard-card-v73", "fitness-tv-dashboard-card-v74", "fitness-tv-dashboard-card-v75"]) {
  _fitnessDefineCustomElement(tag, FitnessTvDashboardCard);
}
for (const tag of [FITNESS_TV_SETUP_CARD_TAG, "fitness-tv-setup-card", "fitness-tv-setup-card-v70", "fitness-tv-setup-card-v71", "fitness-tv-setup-card-v72", "fitness-tv-setup-card-v73", "fitness-tv-setup-card-v74", "fitness-tv-setup-card-v75"]) {
  _fitnessDefineCustomElement(tag, FitnessTvSetupCard);
}
if (!customElements.get("ll-strategy-dashboard-fitness")) customElements.define("ll-strategy-dashboard-fitness", FitnessDashboardStrategy);
if (!customElements.get("ll-strategy-dashboard-fitness-tv")) customElements.define("ll-strategy-dashboard-fitness-tv", FitnessTvDashboardStrategy);

window.customStrategies = window.customStrategies || [];
if (!window.customStrategies.some((item) => item.type === "fitness" && item.strategyType === "dashboard")) {
  window.customStrategies.push({
    type: "fitness",
    strategyType: "dashboard",
    name: "Fitness",
    description: PICKER_DESCRIPTIONS[PICKER_LANG] || PICKER_DESCRIPTIONS.en,
    documentationURL: "https://github.com/Chreece/HA-Fitness#fitness-dashboard",
  });
}

window.customCards = window.customCards || [];
const FITNESS_PUBLIC_CARDS = [
  {
    type: "fitness-live-workout-card",
    name: PICKER_CARD_COPY.live,
    preview: false,
    description: PICKER_DESCRIPTION,
    documentationURL: "https://github.com/Chreece/HA-Fitness#fitness-dashboard",
  },
  {
    type: "fitness-workout-card",
    name: PICKER_CARD_COPY.workout,
    preview: false,
    description: PICKER_DESCRIPTION,
    documentationURL: "https://github.com/Chreece/HA-Fitness#fitness-dashboard",
  },
  {
    type: "fitness-sleep-recovery-card",
    name: PICKER_CARD_COPY.sleep,
    preview: false,
    description: PICKER_DESCRIPTION,
    documentationURL: "https://github.com/Chreece/HA-Fitness#fitness-dashboard",
  },
  {
    type: "fitness-evaluation-card",
    name: PICKER_CARD_COPY.evaluation,
    preview: false,
    description: PICKER_DESCRIPTION,
    documentationURL: "https://github.com/Chreece/HA-Fitness#fitness-dashboard",
  },
];

// Keep the original window.customCards Array object alive. Home Assistant may
// already hold a reference to it; replacing the Array can make newly registered
// cards disappear from the Add Card picker until a full frontend reload.
const publicTypes = new Set(FITNESS_PUBLIC_CARDS.map((card) => card.type));
for (let index = window.customCards.length - 1; index >= 0; index--) {
  const type = String(window.customCards[index]?.type || "");
  if (type.startsWith("fitness-") && !publicTypes.has(type)) {
    window.customCards.splice(index, 1);
  }
}
for (const card of FITNESS_PUBLIC_CARDS) {
  const index = window.customCards.findIndex((item) => item.type === card.type);
  if (index >= 0) {
    Object.assign(window.customCards[index], card);
  } else {
    window.customCards.push(card);
  }
}

console.info(`%c HA-Fitness dashboard ${FITNESS_DASHBOARD_VERSION} `, "background:#41BDF5;color:#fff;font-weight:600;padding:3px 6px;border-radius:4px");
