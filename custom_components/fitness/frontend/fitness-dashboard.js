const FITNESS_DASHBOARD_VERSION = "2026.8.11.13";


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
const PICKER_LANG = (document.documentElement.lang || navigator.language || "en").toLowerCase().split(/[-_]/)[0];

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

class FitnessRouteCard extends HTMLElement {
  setConfig(config) {
    if (!config) throw new Error("fitness-route-card requires a configuration");
    this.config = config;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
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
    let encoded = "";
    try { encoded = JSON.stringify(value); } catch (_err) { encoded = String(value ?? ""); }

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
    const coords = [];
    let index = 0, lat = 0, lon = 0;
    while (index < str.length) {
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

  _extractPoints(value) {
    if (!value) return [];
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!trimmed) return [];
      try { return this._extractPoints(JSON.parse(trimmed)); } catch (_err) {}
      if (/^[A-Za-z0-9_?@`~\\\[\]{}|^]+$/.test(trimmed) || trimmed.length > 20) {
        try { return this._decodeEncodedPolyline(trimmed); } catch (_err) {}
      }
      return [];
    }
    if (Array.isArray(value)) {
      const out = [];
      for (const item of value) {
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
          else out.push(...this._extractPoints(item));
        }
      }
      return out;
    }
    if (value && typeof value === "object") {
      for (const key of ["polyline", "route", "coordinates", "track", "points", "gps_points", "geometry"]) {
        if (key in value) {
          const points = this._extractPoints(value[key]);
          if (points.length) return points;
        }
      }
    }
    return [];
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
      const metric = _fitnessWorkoutSourceMetric(this._profile, this._hass, key);
      if (!metric || metric.value === null || metric.value === undefined || metric.value === "") continue;
      if (running && key === "last_workout_average_speed") {
        if (runPace) items.push({name:this._profile?.labels?.pace || "Pace", value:runPace, entityId:metric.entityId});
        continue;
      }
      items.push({
        name: key === "last_workout" ? (_fitnessWorkoutSourceLabel(this._profile, this._hass, key, metric) || "Workout") : _fitnessWorkoutSourceLabel(this._profile, this._hass, key, metric),
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
    const points = this._extractPoints(value);
    const labels = this._profile?.labels || {};
    const title = this.config.title || labels.route || (entityId ? entityName(this._hass, entityId) : "Workout route");
    const height = Number(this.config.height || 340);
    if (points.length < 2) {
      this.shadowRoot.innerHTML = "";
      return;
    }

    const width = Math.max(this.clientWidth || 600, 300);
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
        <div class="map" style="height:${height}px" title="Drag to move · pinch or wheel to zoom · double tap to fit route">
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
        .map{position:relative;overflow:hidden;background:var(--secondary-background-color);touch-action:none;cursor:grab;overscroll-behavior:contain}.map:active{cursor:grabbing}.map-scene{position:absolute;inset:0;will-change:transform}.tile{position:absolute;width:256px;height:256px;user-select:none;-webkit-user-drag:none;pointer-events:none}svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.start{fill:#2e7d32;stroke:white;stroke-width:2}.end{fill:#c62828;stroke:white;stroke-width:2}.workout-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;padding:12px 16px 14px}.summary-item{background:var(--secondary-background-color);border-radius:12px;padding:9px 11px;min-width:0}.summary-item span{display:block;color:var(--secondary-text-color);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.summary-item strong{display:block;margin-top:3px;font-size:14px}.attribution{position:absolute;right:4px;bottom:3px;background:rgba(255,255,255,.78);font-size:10px;padding:1px 4px;border-radius:3px;color:#333}.attribution a{color:#333}.privacy{padding:8px 16px 12px;font-size:11px;color:var(--secondary-text-color)}
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
              <span>${this._escape(labels.baseline || "Baseline")} <b>${absolute(baseline)}</b></span>
              <span>${this._escape(labels.current || "Current")} <b class="hot">${absolute(current)}</b></span>
              <span>${this._escape(labels.difference || "Difference")} <b class="hot">${signed(value)}</b></span>
            </div>
            <div class="axis heat-axis">
              <i class="baseline-marker"></i>
              <em class="baseline-number">${absolute(baseline)}</em>
              <i class="current-marker" style="left:${currentMarker}%"></i>
            </div>
            <div class="axis-values"><span>${absolute(baseline-max)}</span><b>${_fitnessEscape(labels.baseline || "Baseline")}: ${absolute(baseline)}</b><span>${absolute(baseline+max)}</span></div>
          </div>`;
        }
      }
      return `<div class="row entity-link" style="--baseline-tone:${baselineTone}" data-more-info="${this._escape(metric.entity)}"><div class="line"><span>${this._escape(metric.name || entityName(this._hass, metric.entity))}</span><strong>${signed(value)}</strong></div><div class="axis"><div class="zero"></div><div class="bar" style="left:${left}%;width:${pct}%"></div><i class="current-marker" style="left:${marker}%"></i></div><div class="axis-values"><span>${signed(-max)}</span><b>${signed(value)}</b><span>${signed(max)}</span></div></div>`;
    }).filter(Boolean).join("");
    const title = this.config.title || labels.workout_comparison || "Compared with your baseline";
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
      awakeRouteItem = routeItem("last_sleep_awake", labels.awake || "Awake");
      stageItems = [
        routeItem("last_sleep_light", labels.light_sleep || "Light sleep"),
        routeItem("last_sleep_deep", labels.deep_sleep || "Deep sleep"),
        routeItem("last_sleep_rem", labels.rem_sleep || "REM sleep"),
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
    const title = this.config.title || labels.latest_sleep || "Latest sleep";
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
      const label = scoreMetric.route?.source_type === "fitness_calculated" ? (labels.fitness_sleep_score || "Fitness sleep score") : (labels.sleep_score || "Sleep score");
      summaries.push(`<div class="sleep-summary-metric entity-link" data-more-info="${this._escape(scoreMetric.moreInfoEntityId || "")}"><span>${this._escape(label)}</span><strong>${Math.max(0,Math.min(100,scoreMetric.canonicalValue)).toFixed(0)}%</strong></div>`);
    }
    if (hrvMetric?.canonicalValue != null) summaries.push(`<div class="sleep-summary-metric entity-link" data-more-info="${this._escape(hrvMetric.moreInfoEntityId || "")}"><span>${this._escape(labels.sleep_hrv || "Sleep HRV")}</span><strong>${hrvMetric.canonicalValue.toFixed(1)} ms</strong></div>`);
    if (deficitState && !["unknown","unavailable"].includes(String(deficitState.state).toLowerCase())) summaries.push(`<div class="sleep-summary-metric entity-link" data-more-info="${this._escape(deficitId)}"><span>${this._escape(labels.sleep_deficit || "7-day sleep deficit")}</span><strong>${this._escape(_fitnessSleepDuration(deficitState))}</strong></div>`);
    const summaryMetrics = summaries.join("");
    this.shadowRoot.innerHTML = `<ha-card><div class="title">${this._escape(title)}</div><div class="body"><div class="sleep-overview"><div class="donut entity-link" data-more-info="${this._escape(durationMetric?.moreInfoEntityId || this._profile?.data_entities?.recovery || "")}" style="background:conic-gradient(${stops})"><div class="hole"><strong>${displayTotal}</strong></div></div>${summaryMetrics ? `<div class="sleep-summary">${summaryMetrics}</div>` : ""}</div><div class="legend">${legend}</div>${awakeRow ? `<div class="awake-wrap">${awakeRow}</div>` : ""}</div></ha-card><style>.title{font-size:18px;font-weight:600;padding:16px 16px 6px}.body{display:flex;flex-direction:column;align-items:center;gap:14px;padding:10px 16px 18px;min-width:0}.sleep-overview{width:100%;display:grid;grid-template-columns:minmax(124px,auto) minmax(0,1fr);gap:14px;align-items:center}.donut{width:124px;height:124px;border-radius:50%;display:grid;place-items:center;justify-self:center}.hole{width:76px;height:76px;border-radius:50%;background:var(--ha-card-background,var(--card-background-color));display:flex;flex-direction:column;align-items:center;justify-content:center}.hole strong{font-size:18px;text-align:center;line-height:1.15;padding:4px}.legend{width:100%;min-width:0}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.legend-row{display:grid;grid-template-columns:10px minmax(0,1fr) minmax(72px,max-content) 38px;column-gap:10px;align-items:center;min-width:0;padding:7px 0;font-size:12px}.dot{width:9px;height:9px;border-radius:50%}.label{color:var(--secondary-text-color);min-width:0;white-space:normal;overflow-wrap:normal;word-break:normal;hyphens:auto}.legend-row strong{text-align:right;white-space:nowrap}.pct{text-align:right;white-space:nowrap;color:var(--secondary-text-color)}.awake-wrap{width:100%;padding-top:2px}.awake-row{display:grid;grid-template-columns:20px minmax(0,1fr) max-content;gap:8px;align-items:center;padding:8px 10px;border-radius:11px;background:var(--card-background-color);font-size:11px}.awake-row ha-icon{--mdc-icon-size:16px;color:var(--secondary-text-color)}.awake-row span{color:var(--secondary-text-color)}.sleep-summary{display:grid;grid-template-columns:1fr;gap:8px;min-width:0}.sleep-summary-metric{min-width:0;padding:10px 11px;border-radius:12px;background:var(--secondary-background-color)}.sleep-summary-metric span{display:block;font-size:9px;color:var(--secondary-text-color)}.sleep-summary-metric strong{display:block;margin-top:3px;font-size:14px}@media(max-width:430px){.sleep-overview{grid-template-columns:1fr}.sleep-summary{grid-template-columns:repeat(3,minmax(0,1fr));width:100%}.sleep-summary-metric{padding:8px}.sleep-summary-metric strong{font-size:12px}}</style>`;
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

const _fitnessWorkoutSourceLabel = (profile, hass, key, metric) => {
  if (!metric) return "";
  if (metric.entityId && !["inline","fallback"].includes(metric.route?.transform)) return entityName(hass, metric.entityId);
  const attribute = String(metric.route?.attribute || "");
  if (attribute) {
    return attribute
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .replaceAll("_", " ")
      .replace(/\b\w/g, (ch) => ch.toUpperCase());
  }
  return key.replace(/^last_workout_?/, "").replaceAll("_", " ").replace(/\b\w/g, (ch) => ch.toUpperCase()) || "Workout";
};

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
        const ui = String(this._hass?.language || "en").toLowerCase().split("-")[0];
        this._profile = {...this._profile, labels: this._profile.labels_by_language[ui] || this._profile.labels_by_language.en || this._profile.labels};
      }
    } catch (_err) {
      this._profile = null;
    } finally {
      this._resolving = false;
      this._render();
    }
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
    for (const [key,label,decimals] of [["last_sleep_score",l.sleep_score||"Sleep score",0],["last_sleep_duration",l.latest_sleep||"Sleep duration",0],["last_sleep_hrv",l.sleep_hrv||"Sleep HRV",1]]) {
      const metric = _fitnessSleepSourceMetric(this._profile,this._hass,key,decimals);
      if (metric?.canonicalValue == null) continue;
      const value = key === "last_sleep_duration" ? _fitnessSleepDuration({state:String(metric.canonicalValue),attributes:{unit_of_measurement:"min"}}) : `${metric.canonicalValue.toFixed(decimals)}${metric.route?.unit ? ` ${metric.route.unit}` : ""}`;
      itemsList.push(`<div class="today-item entity-link" data-more-info="${_fitnessEscape(metric.moreInfoEntityId||"")}"><span>${_fitnessEscape(label)}</span><strong>${_fitnessEscape(value)}</strong></div>`);
    }
    const vo2 = _fitnessEvaluationSourceMetric(this._profile,this._hass,"vo2max",1);
    if (vo2?.canonicalValue != null) itemsList.push(`<div class="today-item entity-link" data-more-info="${_fitnessEscape(vo2.moreInfoEntityId||"")}"><span>${_fitnessEscape(l.current_vo2max||"Current VO₂max")}</span><strong>${vo2.canonicalValue.toFixed(1)} mL/kg/min</strong></div>`);
    const items = itemsList.join("");
    this.shadowRoot.innerHTML = `<ha-card><div class="today-head"><div><strong>${_fitnessEscape(this.config.title || l.overview || "Today")}</strong><span>${_fitnessEscape(this._profile?.profile_name || "")}</span></div><ha-icon icon="mdi:heart-pulse"></ha-icon></div><div class="today-grid">${items || `<small>No current Fitness data is available yet.</small>`}</div></ha-card><style>
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
      const metric = _fitnessWorkoutSourceMetric(this._profile, this._hass, key);
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
        displayLabel = l.pace || "Pace";
      }
      candidates.push({
        key, priority: _fitnessWorkoutPriority(sport, key),
        html: `<div class="hi entity-link" data-more-info="${_fitnessEscape(metric.moreInfoEntityId || "")}"><span>${_fitnessEscape(displayLabel)}</span><strong>${_fitnessEscape(display)}</strong></div>`,
      });
    }

    const rpeId = e.session_rpe;
    const rpeState = rpeId ? this._hass.states[rpeId] : null;
    if (rpeState && !["unknown","unavailable"].includes(String(rpeState.state).toLowerCase())) {
      candidates.push({key:"session_rpe", priority:_fitnessWorkoutPriority(sport,"session_rpe"), html:`<div class="hi entity-link" data-more-info="${_fitnessEscape(rpeId)}"><span>${_fitnessEscape(entityName(this._hass,rpeId))}</span><strong>${_fitnessEscape(_fitnessDisplay(rpeState,0))}</strong></div>`});
    }

    for (const key of fitnessKeys) {
      const id = e[key];
      const state = id ? this._hass.states[id] : null;
      if (!state || ["unknown","unavailable"].includes(String(state.state).toLowerCase())) continue;
      const numeric = Number(state.state);
      if (zeroIsMissing.has(key) && Number.isFinite(numeric) && Math.abs(numeric) < 1e-12) continue;
      candidates.push({key, priority:_fitnessWorkoutPriority(sport,key), html:`<div class="hi entity-link" data-more-info="${_fitnessEscape(id)}"><span>${_fitnessEscape(entityName(this._hass,id))}</span><strong>${_fitnessEscape(_fitnessDisplay(state,1))}</strong></div>`});
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
      <div class="baseline-head"><span>HR ${_fitnessEscape(l.baseline || "Baseline")}</span><strong>${hrDelta >= 0 ? "+" : ""}${hrDelta.toFixed(1)} bpm</strong></div>
      <div class="baseline-values three">
        <span>${_fitnessEscape(l.baseline || "Baseline")}<b>${hrBaseline.toFixed(1)} bpm</b></span>
        <span>${_fitnessEscape(l.current || "Current")}<b>${hrCurrent.toFixed(1)} bpm</b></span>
        <span>${_fitnessEscape(l.difference || "Difference")}<b style="color:var(--hr-tone)">${hrDelta >= 0 ? "+" : ""}${hrDelta.toFixed(1)} bpm</b></span>
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
      .hi-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px;min-width:0}
      .hi{padding:10px;border-radius:12px;background:var(--secondary-background-color);min-width:0;max-width:100%;overflow:hidden}
      .hi span{display:block;font-size:10px;line-height:1.25;color:var(--secondary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .hi strong{display:block;font-size:14px;line-height:1.3;margin-top:4px;min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere;word-break:normal}
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
        <div class="strength-main"><strong>${_fitnessEscape(ex?.name || ex?.id || "Exercise")}</strong><span>${_fitnessEscape(bestText)}</span></div>
        <div class="strength-stat"><span>e1RM</span><strong>${e1rm == null ? "—" : `${e1rm.toFixed(1)} kg`}</strong></div>
        <div class="strength-stat"><span>Volume</span><strong>${volume == null ? "—" : `${volume.toFixed(0)} kg`}</strong></div>
        <div class="strength-trend ${change > 0 ? "up" : change < 0 ? "down" : ""}">${_fitnessEscape(trend)}</div>
      </div>`;
    }).join("");
    const totalSets = _fitnessNumber(details?.total_sets);
    const totalReps = _fitnessNumber(details?.total_reps);
    const totalVolume = _fitnessNumber(details?.volume_kg);
    this.shadowRoot.innerHTML = `<ha-card>
      <div class="strength-head entity-link" data-more-info="${_fitnessEscape(source?.entity_id || e.last_workout_strength_sets || e.last_workout_estimated_1rm || e.last_workout_strength_progression || "")}"><div><strong>Strength progression</strong><span>${exercises.length} exercises${totalSets != null ? ` · ${totalSets.toFixed(0)} sets` : ""}${totalReps != null ? ` · ${totalReps.toFixed(0)} reps` : ""}</span></div><ha-icon icon="mdi:dumbbell"></ha-icon></div>
      ${totalVolume != null ? `<div class="volume-hero entity-link" data-more-info="${_fitnessEscape(source?.entity_id || e.last_workout_strength_sets || "")}"><span>Total volume</span><strong>${totalVolume.toFixed(0)} kg</strong></div>` : ""}
      <div class="strength-list entity-link" data-more-info="${_fitnessEscape(source?.entity_id || e.last_workout_strength_sets || e.last_workout_estimated_1rm || e.last_workout_strength_progression || "")}">${rows}</div>
      <small class="method">Estimated 1RM uses the Epley formula from valid 1–12 rep sets; it is not a measured 1RM.</small>
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
    const predictedAbsolute = _fitnessNumber(_fitnessAttr(predicted, "predicted_vo2max_ml_kg_min"))
      ?? (current != null && pctPred != null && pctPred > 0 ? current / (pctPred / 100) : null);
    const status = slope == null ? "" : slope > 0.35 ? (l.improving || "Improving") : slope < -0.35 ? (l.declining || "Declining") : (l.stable || "Stable");
    const arrow = slope == null ? "→" : slope > 0.35 ? "↗" : slope < -0.35 ? "↘" : "→";
    const delta28 = current != null && mean28 ? ((current - mean28) / mean28 * 100) : null;
    const useAbsoluteVo2Scale = current != null && current > 0 && predictedAbsolute != null && predictedAbsolute > 0;
    const progressMin = useAbsoluteVo2Scale
      ? Math.max(0, Math.floor(Math.min(current, predictedAbsolute) * 0.8 * 10) / 10)
      : 50;
    const progressMax = useAbsoluteVo2Scale
      ? Math.max(progressMin + 1, Math.ceil(Math.max(current, predictedAbsolute) * 1.2 * 10) / 10)
      : Math.max(130, Math.ceil((pctPred ?? 100) / 10) * 10);
    const progressSpan = Math.max(progressMax - progressMin, 0.1);
    const currentMarker = useAbsoluteVo2Scale
      ? Math.max(0, Math.min(100, ((current - progressMin) / progressSpan) * 100))
      : pctPred == null ? null : Math.max(0, Math.min(100, ((pctPred - progressMin) / progressSpan) * 100));
    const predictedMarker = useAbsoluteVo2Scale
      ? Math.max(0, Math.min(100, ((predictedAbsolute - progressMin) / progressSpan) * 100))
      : Math.max(0, Math.min(100, ((100 - progressMin) / progressSpan) * 100));
    const progressLeftLabel = useAbsoluteVo2Scale ? progressMin.toFixed(1) : `${progressMin}%`;
    const progressRightLabel = useAbsoluteVo2Scale ? progressMax.toFixed(1) : `${progressMax}%`;
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
      this._metric(l.mean_28d || "28-day mean", mean28, "mL/kg/min", false, e.cardiorespiratory_fitness_trend),
      this._metric(l.mean_90d || "90-day mean", mean90, "mL/kg/min", false, e.cardiorespiratory_fitness_trend),
      this._metric(l.predicted_percent || "% of predicted", pctPred, "%", false, e.vo2max_percent_predicted),
      this._metric("Δ 28d", delta28, "%", true, e.cardiorespiratory_fitness_trend),
    ].filter(Boolean).join("");

    let history = "";
    this._vo2HistoryPoints = [];
    this._vo2HistoryPredicted = predictedAbsolute;
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
      const allVals = [...series.map(x=>x.v), trendStart, trendEnd, ...(predictedAbsolute == null ? [] : [predictedAbsolute])];
      let lo = Math.min(...allVals), hi = Math.max(...allVals);
      const pad = Math.max((hi-lo)*0.12, 0.5); lo -= pad; hi += pad;
      const span = Math.max(hi-lo, 0.1);
      const y = value => 34-((value-lo)/span)*28;
      const xPos = t => ((t-startT)/timeSpan)*100;
      const actualPts = series.map((x)=>`${xPos(x.t).toFixed(2)},${y(x.v).toFixed(2)}`).join(" ");
      const trendPts = `0,${y(trendStart).toFixed(2)} 100,${y(trendEnd).toFixed(2)}`;
      const predictedY = predictedAbsolute == null ? null : y(predictedAbsolute);
      this._vo2HistoryPoints = series.map((x,i) => ({
        x:xPos(x.t), y:y(x.v), v:x.v, d:x.d, t:x.t,
        trend:regIntercept + regSlope*xs[i],
      }));
      history = `<div class="history">
        <div class="history-head"><span>${_fitnessEscape(l.history || "History")}</span><small>${series.length} measurements</small></div>
        <div class="history-plot">
          <svg class="vo2-history-svg entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || "")}" viewBox="0 0 100 38" preserveAspectRatio="none" aria-label="VO2max history">
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
        <div class="history-legend">
          <span class="entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || "")}"><i class="actual-dot"></i>Actual</span>
          <span class="entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || "")}"><i class="trend-dot"></i>Trend</span>
          ${predictedAbsolute == null ? "" : `<span class="entity-link" data-more-info="${_fitnessEscape(e.vo2max_percent_predicted || "")}"><i class="predicted-dot"></i>Predicted ${predictedAbsolute.toFixed(1)}</span>`}
        </div>
        <div class="history-values"><span>${series[0].v.toFixed(1)}</span><b>${current == null ? series[n-1].v.toFixed(1) : current.toFixed(1)} mL/kg/min</b></div>
      </div>`;
    }

    this.shadowRoot.innerHTML = `<ha-card style="--vo2-tone:${vo2Tone}">
      <div class="head"><div><div class="title">${_fitnessEscape(this.config.title || l.progress_snapshot || "Fitness progress")}</div><div class="sub">${_fitnessEscape(status)}</div></div><div class="trend entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || "")}">${arrow}${slope == null ? "" : ` ${slope > 0 ? "+" : ""}${slope.toFixed(2)}%`}</div></div>
      <div class="hero entity-link" data-more-info="${_fitnessEscape(currentSource?.moreInfoEntityId || e.cardiorespiratory_fitness_trend || "")}"><strong>${current == null ? "—" : current.toFixed(1)}</strong><span>mL/kg/min</span><small>${_fitnessEscape(l.current_vo2max || "Current VO₂max")}</small></div>
      <div class="progress entity-link" data-more-info="${_fitnessEscape(e.vo2max_percent_predicted || "")}">
        ${predictedAbsolute == null && !useAbsoluteVo2Scale ? `<i class="vo2-reference" style="left:${predictedMarker}%" title="100% predicted"></i>` : `<i class="vo2-reference" style="left:${predictedMarker}%" title="Predicted ${predictedAbsolute == null ? "100%" : `${predictedAbsolute.toFixed(1)} mL/kg/min`}"></i>`}
        ${currentMarker == null ? "" : `<i class="vo2-marker" style="left:${currentMarker}%" title="Current ${current == null ? `${pctPred.toFixed(1)}% of predicted` : `${current.toFixed(1)} mL/kg/min`}"></i>`}
      </div>
      <div class="progress-values entity-link" data-more-info="${_fitnessEscape(e.vo2max_percent_predicted || "")}"><span>${progressLeftLabel}</span><b>${pctPred == null ? "—" : `${pctPred.toFixed(1)}%`}</b><span>${progressRightLabel}</span></div>
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
      const language = this._hass?.language || undefined;
      const date = new Intl.DateTimeFormat(language, {year:"numeric",month:"short",day:"numeric"}).format(new Date(point.t));
      const bits = [`<strong>${point.v.toFixed(1)} mL/kg/min</strong>`, `<span>${_fitnessEscape(date)}</span>`];
      if (point.trend != null) bits.push(`<small>Trend ${point.trend.toFixed(1)}</small>`);
      if (this._vo2HistoryPredicted != null) bits.push(`<small>Predicted ${this._vo2HistoryPredicted.toFixed(1)}</small>`);
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
      .history{margin-top:16px;padding:10px 12px;border-radius:12px;background:var(--secondary-background-color)}.history-head{display:flex;justify-content:space-between;color:var(--secondary-text-color);font-size:11px}.history-plot{position:relative;margin-top:7px;min-width:0}.history svg{width:100%;height:88px;display:block;overflow:visible;touch-action:none}.actual-line{fill:none;stroke:var(--primary-color);stroke-width:1.8;vector-effect:non-scaling-stroke;stroke-linecap:round;stroke-linejoin:round}.trend-line{fill:none;stroke:var(--vo2-tone);stroke-width:1.5;stroke-dasharray:5 3;vector-effect:non-scaling-stroke}.predicted-line{stroke:var(--secondary-text-color);stroke-width:1.2;stroke-dasharray:2.5 2.5;vector-effect:non-scaling-stroke;opacity:.8}.cursor-line{stroke:var(--primary-text-color);stroke-width:1;stroke-dasharray:2 2;opacity:.7;vector-effect:non-scaling-stroke}.cursor-dot{fill:var(--primary-color);stroke:var(--card-background-color);stroke-width:1;vector-effect:non-scaling-stroke}.history-tooltip{position:absolute;z-index:3;min-width:132px;max-width:154px;padding:6px 8px;border-radius:9px;background:color-mix(in srgb,var(--card-background-color) 94%,black 6%);box-shadow:0 3px 12px rgba(0,0,0,.28);pointer-events:none;font-size:9px;line-height:1.3}.history-tooltip strong,.history-tooltip span,.history-tooltip small{display:block}.history-tooltip strong{font-size:11px;color:var(--primary-text-color)}.history-tooltip span{color:var(--secondary-text-color);margin-top:1px}.history-tooltip small{color:var(--secondary-text-color);margin-top:2px}.history-legend{display:flex;flex-wrap:wrap;gap:8px 14px;margin-top:3px;font-size:9px;color:var(--secondary-text-color)}.history-legend span{display:flex;align-items:center;gap:5px}.history-legend i{width:13px;height:3px;border-radius:3px}.actual-dot{background:var(--primary-color)}.trend-dot{background:var(--vo2-tone)}.predicted-dot{background:var(--secondary-text-color)}
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
    const ui = String(this._hass?.language || "en").toLowerCase().split("-")[0];
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
      muscular_recovery: l.limiter_muscular_recovery || "Muscular recovery",
      autonomic_recovery: l.limiter_autonomic_recovery || "Autonomic recovery",
      sleep_recovery: l.limiter_sleep_recovery || "Sleep recovery",
      overall_readiness: l.limiter_overall_readiness || "Overall readiness",
      workout_dose: l.limiter_workout_dose || "Workout demand",
    };
    const limitingFactorText = limiterLabels[limitingFactor] || limitingFactor.replaceAll("_", " ");

    const readyAt = readyAtRaw ? new Date(readyAtRaw) : null;
    const readyAtText = (() => {
      if (!readyAt || Number.isNaN(readyAt.getTime())) return "—";
      const language = this._hass.language || undefined;
      const timeText = new Intl.DateTimeFormat(language, {hour:"2-digit", minute:"2-digit"}).format(readyAt);
      const now = new Date();
      const sameDay = (a,b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
      const tomorrow = new Date(now); tomorrow.setDate(now.getDate()+1);
      const at = String(l.at_time || "at").trim();
      if (sameDay(readyAt, now)) return [at, timeText].filter(Boolean).join(" ");
      if (sameDay(readyAt, tomorrow)) {
        const day = new Intl.RelativeTimeFormat(language, {numeric:"auto"}).format(1, "day");
        return [day, at, timeText].filter(Boolean).join(" ");
      }
      const day = new Intl.DateTimeFormat(language, {weekday:"short", month:"short", day:"numeric"}).format(readyAt);
      return [day, at, timeText].filter(Boolean).join(" ");
    })();
    const fullyRecovered = remaining != null && remaining <= 0;
    const recoveryDisplay = remaining == null ? "—"
      : fullyRecovered ? (l.total_recovery || "Total recovery")
      : remaining < 1 ? `~${Math.max(1, Math.round(remaining * 60))} min`
      : `~${Math.round(remaining)} ${l.hours_short || "h"}`;
    const recoveryIcon = fullyRecovered ? "mdi:check-circle" : "mdi:timer-sand-complete";

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
        <div><i style="width:${Math.max(0, Math.min(100, value))}%"></i></div>
      </div>`;
    }).filter(Boolean).join("");

    const trainingRecovery = _fitnessNumber(components?.training?.score);
    const trainingEvidence = components?.training?.evidence || {};
    const trainingHours = _fitnessNumber(trainingEvidence.hours_since_last_workout);
    const trainingLoadRatio = _fitnessNumber(trainingEvidence.recent_to_baseline_load_ratio);
    const trainingTone = trainingRecovery == null ? "#78909c"
      : trainingRecovery >= 85 ? "#2e7d32"
      : trainingRecovery >= 70 ? "#00897b"
      : trainingRecovery >= 50 ? "#f9a825"
      : trainingRecovery >= 30 ? "#ef6c00"
      : "#c62828";
    const scoreBar = ({kind, label, value, tone, detail = ""}) => value == null ? "" : `<div class="recovery-score recovery-score-${kind} entity-link" data-more-info="${_fitnessEscape(e.readiness || "")}" style="--score-tone:${tone}">
      <div class="recovery-score-head"><span>${_fitnessEscape(label)}</span><strong>${Math.max(0, Math.min(100, value)).toFixed(0)} <small>/ 100</small></strong></div>
      <div class="recovery-score-track"><i style="width:${Math.max(0, Math.min(100, value))}%"></i></div>
      ${detail ? `<div class="recovery-score-detail">${detail}</div>` : ""}
    </div>`;
    const readinessDetail = [
      levelText ? `<b>${_fitnessEscape(levelText)}</b>` : "",
      confidence == null ? "" : `${confidence.toFixed(0)}% ${_fitnessEscape(rtext.confidence)}`,
    ].filter(Boolean).join(" · ");
    const readinessScoreBar = scoreBar({
      kind:"readiness", label:readinessName, value:score, tone:readinessTone, detail:readinessDetail,
    });
    const trainingDetail = [
      trainingHours == null ? "" : `${trainingHours.toFixed(1)} h ${_fitnessEscape(l.since_last_workout || "since last workout")}`,
      trainingLoadRatio == null ? "" : `${trainingLoadRatio.toFixed(2)}× ${_fitnessEscape(l.baseline || "baseline")}`,
    ].filter(Boolean).join(" · ");
    const trainingRecoveryBar = scoreBar({
      kind:"training", label:rtext.training, value:trainingRecovery, tone:trainingTone, detail:trainingDetail,
    });
    const readinessTrainingStack = (readinessScoreBar || trainingRecoveryBar)
      ? `<div class="recovery-score-stack">${readinessScoreBar}${trainingRecoveryBar}</div>`
      : "";

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
      <div class="hrv-head"><span>HRV ${_fitnessEscape(l.baseline || "Baseline")}</span><strong>${hrvVs >= 0 ? "+" : ""}${hrvVs.toFixed(1)}%</strong></div>
      <div class="hrv-values three">
        <span>${_fitnessEscape(l.baseline || "Baseline")} <b>${hrvBaseline.toFixed(1)} ms</b></span>
        <span class="entity-link" data-more-info="${_fitnessEscape(hrvSource?.moreInfoEntityId || "")}">${_fitnessEscape(l.current || "Current")} <b>${hrvLatest.toFixed(1)} ms</b></span>
        <span>${_fitnessEscape(l.difference || "Difference")} <b style="color:var(--hrv-tone)">${hrvVs >= 0 ? "+" : ""}${hrvVs.toFixed(1)}%</b></span>
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
      <div class="title">${_fitnessEscape(this.config.title || l.recovery_snapshot || "Recovery snapshot")}</div>

      <section class="recovery-readiness-panel">
        <div class="section-label">${_fitnessEscape(l.recovery_readiness || "Recovery & readiness")}</div>
        ${!recoveryTime ? readinessTrainingStack : ""}

        ${recoveryTime ? `<div class="next-workout entity-link" data-more-info="${_fitnessEscape(e.estimated_recovery_time || "")}">
        <div class="next-main">
          <div class="next-icon"><ha-icon icon="${recoveryIcon}"></ha-icon></div>
          <div class="next-copy">
            <small>${_fitnessEscape(l.recovery_from_last_workout || "Time to recover from last workout")}</small>
            <strong>${_fitnessEscape(recoveryDisplay)}</strong>
            ${remaining != null && remaining > 0
              ? `<span>${_fitnessEscape(l.ready_at || "Ready around")} <b>${_fitnessEscape(readyAtText)}</b></span>`
              : ""}
          </div>
          <div class="next-confidence">${recoveryConfidence == null ? "" : `${recoveryConfidence.toFixed(0)}%<small>${_fitnessEscape(l.confidence_short || "confidence")}</small>`}</div>
        </div>

        <div class="progress-head">
          <span>${_fitnessEscape(l.recovery_progress_label || "Recovery progress")}</span>
          <strong>${recoveryPct.toFixed(0)}%</strong>
        </div>
        <div class="recovery-progress"><i style="width:${recoveryPct}%"></i></div>

        ${readinessTrainingStack}

        <div class="recovery-grid">
          <div class="entity-link" data-more-info="${_fitnessEscape(e.estimated_recovery_time || "")}">
            <span>${_fitnessEscape(l.broader_recovery_window || "Broader physiological recovery window")}</span>
            <strong>${recoveryLow == null || recoveryHigh == null
              ? "—"
              : `~${Math.round(recoveryLow)}–${Math.round(recoveryHigh)} ${_fitnessEscape(l.hours_short || "h")}`}</strong>
          </div>
          ${limitingFactor ? `<div class="entity-link" data-more-info="${_fitnessEscape(e.estimated_recovery_time || "")}"><span>${_fitnessEscape(l.recovery_limiting_factor || "Main recovery limiter")}</span><strong>${_fitnessEscape(limitingFactorText)}</strong></div>` : ""}
        </div>

        ${signalRows ? `<div class="signal-head">${_fitnessEscape(l.recovery_signals_label || "Recovery signals")}</div><div class="signals">${signalRows}</div>` : ""}
        <div class="physio-note">${_fitnessEscape(l.physio_note || "Available physiological markers may recover at different rates.")}</div>
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
      .next-main{
        display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:12px;align-items:center;min-width:0
      }
      .next-icon{
        width:46px;height:46px;border-radius:14px;display:grid;place-items:center;
        background:color-mix(in srgb,var(--recovery) 16%,transparent);color:var(--recovery)
      }
      .next-icon ha-icon{--mdc-icon-size:27px}
      .next-copy{min-width:0}
      .next-copy small{display:block;color:var(--secondary-text-color);font-size:10px;line-height:1.25}
      .next-copy strong{display:block;color:var(--recovery);font-size:22px;line-height:1.1;margin-top:2px;overflow-wrap:anywhere}
      .next-copy span{display:block;color:var(--secondary-text-color);font-size:11px;line-height:1.35;margin-top:5px;overflow-wrap:anywhere}
      .next-copy b{color:var(--primary-text-color)}
      .next-confidence{font-size:17px;font-weight:700;color:var(--recovery);text-align:right;white-space:nowrap}
      .next-confidence small{display:block;font-size:8px;font-weight:400;color:var(--secondary-text-color)}

      .progress-head{display:flex;justify-content:space-between;gap:12px;margin-top:13px;font-size:10px;color:var(--secondary-text-color)}
      .progress-head strong{color:var(--primary-text-color);font-size:12px}
      .recovery-progress{height:7px;border-radius:999px;background:var(--divider-color);overflow:hidden;margin-top:6px}
      .recovery-progress i{display:block;height:100%;border-radius:999px;background:var(--recovery)}
      .recovery-score-stack{display:grid;gap:7px;margin-top:8px}
      .recovery-score{padding:8px 9px;border-radius:10px;background:linear-gradient(135deg,color-mix(in srgb,var(--score-tone) 10%,var(--card-background-color)),var(--card-background-color));border-left:3px solid var(--score-tone);min-width:0}
      .recovery-score-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.recovery-score-head span{font-size:10px;color:var(--secondary-text-color);font-weight:650;overflow-wrap:anywhere}.recovery-score-head strong{font-size:18px;color:var(--score-tone);white-space:nowrap}.recovery-score-head strong small{font-size:9px;color:var(--secondary-text-color);font-weight:500}
      .recovery-score-track{height:7px;border-radius:999px;margin-top:6px;background:color-mix(in srgb,var(--score-tone) 13%,var(--divider-color));overflow:hidden}.recovery-score-track i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,color-mix(in srgb,var(--score-tone) 38%,transparent),var(--score-tone))}
      .recovery-score-detail{margin-top:4px;font-size:9px;line-height:1.3;color:var(--secondary-text-color);overflow-wrap:anywhere}.recovery-score-detail b{color:var(--score-tone);font-weight:650}

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

      @media(max-width:520px){
        .readiness-panel{grid-template-columns:88px minmax(0,1fr);gap:12px;padding:14px}
        .readiness-ring{width:82px;height:82px}
        .readiness-ring>div{width:60px;height:60px}
        .readiness-ring strong{font-size:24px;line-height:60px}
        .readiness-copy strong{font-size:21px}
        .next-main{grid-template-columns:40px minmax(0,1fr)}
        .next-icon{width:38px;height:38px}
        .next-confidence{grid-column:2;text-align:left;margin-top:-4px}
        .recovery-grid{grid-template-columns:1fr}
        .components{grid-template-columns:1fr}
      }
      @media(max-width:350px){
        .readiness-panel{grid-template-columns:1fr;text-align:center}
        .readiness-ring{margin:auto}
        .next-main{grid-template-columns:1fr;text-align:center}
        .next-icon{margin:auto}
        .next-confidence{grid-column:1;text-align:center}
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

    const recoveryBits = [];
    if (hrv != null) recoveryBits.push(`HRV ${hrv >= 0 ? "+" : ""}${hrv.toFixed(1)}%`);
    if (rhr != null) recoveryBits.push(`RHR ${rhr >= 0 ? "+" : ""}${rhr.toFixed(1)} bpm`);
    if (readiness != null) recoveryBits.push(`${readiness.toFixed(0)}/100`);

    this.shadowRoot.innerHTML = `<ha-card style="--adapt:${tone}">
      <div class="hero entity-link" data-more-info="${_fitnessEscape(entityId || "")}">
        <div class="icon"><ha-icon icon="${icon}"></ha-icon></div>
        <div class="copy">
          <small>${_fitnessEscape(l.training_adaptation_card || "Training adaptation")}</small>
          <strong>${_fitnessEscape(state.state)}</strong>
          <span>${_fitnessEscape(l.training_adaptation_subtitle || "How recent training is affecting you")}</span>
        </div>
      </div>
      <div class="metrics entity-link" data-more-info="${_fitnessEscape(entityId || "")}">
        <div><span>${_fitnessEscape(l.adaptation_load_ratio || "Recent / baseline load")}</span><strong>${ratio == null ? "—" : `${ratio.toFixed(2)}×`}</strong></div>
        <div><span>${_fitnessEscape(l.adaptation_fitness_trend || "Fitness trend")}</span><strong>${vo2 == null ? "—" : `${vo2 >= 0 ? "+" : ""}${vo2.toFixed(1)}% / 30d`}</strong></div>
        <div><span>${_fitnessEscape(l.adaptation_recovery_signal || "Recovery signal")}</span><strong>${_fitnessEscape(recoveryBits.length ? recoveryBits.join(" · ") : "—")}</strong></div>
      </div>
      ${evidence != null ? `<div class="evidence">${evidence.toFixed(0)} evidence signal${evidence === 1 ? "" : "s"}</div>` : ""}
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
      building: l.baseline_building || "Building personal baseline",
      low: l.load_low || "Low",
      balanced: l.load_balanced || "Balanced",
      elevated: l.load_elevated || "Elevated",
      high: l.load_high || "High",
      excessive: l.load_excessive || "Excessive",
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
      [l.baseline_28d || "28-day weekly baseline", baseline, value => value.toFixed(1)],
      [l.workouts_7d || "Workouts / 7 days", workouts7, value => value.toFixed(0)],
      [l.active_days_7d || "Active days / 7 days", days7, value => value.toFixed(0)],
      [l.training_minutes_7d || "Training / 7 days", mins7, value => `${Math.round(value)} min`],
    ].filter(([, value]) => value != null).map(([label, value, formatter]) =>
      `<div><span>${_fitnessEscape(label)}</span><strong>${formatter(value)}</strong></div>`
    ).join("");

    this.shadowRoot.innerHTML = `<ha-card>
      <div class="header">
        <div>
          <h3>${_fitnessEscape(l.training_load_snapshot || "Training load")}</h3>
          ${hasAdaptationData ? `<div class="adapt-summary entity-link" style="--adapt:${adaptationTone}" data-more-info="${_fitnessEscape(e.training_adaptation_status || "")}">
            <div class="adapt-title"><span>${_fitnessEscape(l.training_adaptation_card || "Training adaptation")}</span><strong>${_fitnessEscape(adaptationLabel)}</strong></div>
            ${adaptationStatus === "insufficient_data"
              ? `<p>${_fitnessEscape(l.adaptation_building || "Building enough history for a reliable adaptation assessment")}</p>`
              : `<div class="adapt-evidence">
                  <span>${_fitnessEscape(l.adaptation_baseline || "Load balance")} <b>${baselineReliable && ratio != null ? `${ratio.toFixed(2)}×` : "—"}</b></span>
                  <span>${_fitnessEscape(l.adaptation_fitness || "Fitness trend")} <b>${adaptationVo2 == null ? "—" : `${adaptationVo2 >= 0 ? "+" : ""}${adaptationVo2.toFixed(1)}%`}</b></span>
                  <span>${_fitnessEscape(l.adaptation_recovery || "Recovery")} <b>${adaptationReadiness == null ? "—" : `${adaptationReadiness.toFixed(0)}/100`}</b></span>
                </div>`}
            ${adaptationEvidence == null ? "" : `<small>${_fitnessEscape(l.adaptation_evidence || "Evidence")}: ${adaptationEvidence.toFixed(0)}</small>`}
          </div>` : ""}
        </div>
        ${ratio != null ? `<div class="ratio ${zone}">${ratio.toFixed(2)}×</div>` : ""}
      </div>

      ${baselineReliable && ratio != null ? `<div class="load-scale entity-link" data-more-info="${_fitnessEscape(entityId)}"><div class="scale"></div><i style="left:${position}%"></i></div><div class="load-scale-values"><span>0×</span><b>${ratio.toFixed(2)}×</b><span>2.40×</span></div>` : ""}

      ${ratio != null ? `<div class="status-row"><div><span>${_fitnessEscape(l.load_ratio || "Load vs baseline")}</span><strong class="${zone}">${_fitnessEscape(zoneText)}</strong></div>${!baselineReliable ? `<p>${_fitnessEscape(l.baseline_building_hint || "More comparable workouts are needed before load balance can be judged reliably.")}</p>` : ""}</div>` : ""}

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
    const language = String(hass?.language || "en").toLowerCase().split("-")[0];

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
    this._compositeLanguage = String(this._hass?.language || "en").toLowerCase().split("-")[0];
    this._compositeSignatureValue = this._compositeSignature();
  }
}

class FitnessLiveWorkoutCard extends FitnessAutoProfileCard {
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
      return `<div class="live-metric entity-link" data-more-info="${_fitnessEscape(id)}"><span>${_fitnessEscape(entityName(this._hass,id))}</span><strong>${_fitnessEscape(_fitnessDisplay(state,1))}</strong></div>`;
    }).filter(Boolean).join("");
    const controls = controlKeys.map((key) => {
      const id = e[key];
      const state = id ? this._hass.states[id] : null;
      if (!id || !state || state.state === "unavailable") return "";
      return `<button class="live-control" data-entity="${_fitnessEscape(id)}"><ha-icon icon="${
        key === "start_workout" ? "mdi:play" : key === "pause_workout" ? "mdi:pause" : key === "resume_workout" ? "mdi:play-pause" : "mdi:stop"
      }"></ha-icon><span>${_fitnessEscape(entityName(this._hass,id))}</span></button>`;
    }).filter(Boolean).join("");

    this.shadowRoot.innerHTML = `<ha-card>
      <div class="live-head"><ha-icon icon="mdi:run-fast"></ha-icon><div><strong>${_fitnessEscape(this.config.title || l.live || l.current || "Live workout")}</strong><span>${_fitnessEscape(this._profile.profile_name || "")}</span></div></div>
      <div class="live-grid">${metrics || `<div class="live-empty">${_fitnessEscape(l.no_live_data || "No live workout data is available yet.")}</div>`}</div>
      ${controls ? `<div class="live-controls">${controls}</div>` : ""}
    </ha-card><style>
      ha-card{
        --fitness-card-accent:var(--success-color,#43a047);
        padding:10px;overflow:hidden;box-shadow:none;border:0;border-radius:20px;
        background:var(--secondary-background-color)
      }
      .live-grid,.live-controls{padding:0;background:transparent}
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
      .live-control span{min-width:0;font-size:11px;font-weight:600;line-height:1.2;overflow-wrap:anywhere}
      .live-control:active{transform:scale(.98)}
      @media(max-width:420px){
        ha-card{padding:7px}
        .live-grid,.live-controls{grid-template-columns:1fr 1fr;padding:0}
        .live-head>ha-icon{width:28px;height:28px}
      }
    </style>`;
    for (const button of this.shadowRoot.querySelectorAll(".live-control")) {
      button.addEventListener("click", () => {
        const entityId = button.dataset.entity;
        if (!entityId || button.disabled) return;
        button.disabled = true;
        Promise.resolve(this._hass.callService("button", "press", {entity_id: entityId}))
          .catch(() => {})
          .finally(() => { button.disabled = false; });
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
      <div class="head entity-link" data-more-info="${_fitnessEscape(rpeId)}"><div class="icon"><ha-icon icon="mdi:gauge"></ha-icon></div><div class="title"><strong>${_fitnessEscape(l.rpe_title || "Perceived effort")}</strong><span>${_fitnessEscape(l.rpe_hint || "How hard did this workout feel? Choose a whole number from 1 to 10.")}</span></div><div class="score"><strong>${rpeValue == null ? "—" : Math.round(rpeValue)}</strong><span>/ 10</span></div></div>
      <div class="rpe-scale">${choices}</div>
      <div class="foot"><span>${_fitnessEscape(l.rpe_saved || "Saved to this workout. Changing it recalculates RPE-based load and comparisons.")}</span>${meta ? `<div class="meta">${meta}</div>` : ""}</div>
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
    this._shell(this.config.title || l.latest_workout || "Latest workout", "mdi:run", children, "var(--primary-color)");
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
    this._shell(this.config.title || l.recovery || "Recovery & sleep", "mdi:heart-pulse", children, "var(--warning-color,#f9a825)");
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
    this._shell(this.config.title || l.evaluation || "Evaluation", "mdi:chart-line", children, "var(--primary-color)");
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
      return { title: config?.title || "Fitness", views: [{ title: "Fitness", path: "fitness", cards: [{ type: "markdown", content: "# Fitness\n\nNo configured Fitness profile is currently available." }] }] };
    }
    const multi = profiles.length > 1;
    const views = [];
    for (const profile of profiles) {
      views.push(...this._profileViews(hass, profile, multi));
    }
    return { title: config?.title || profiles[0].labels.dashboard || "Fitness", views };
  }

  static _profileViews(hass, profile, multi) {
    const e = profile.entities || {};
    const ui = String(hass?.language || "en").toLowerCase().split("-")[0];
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
        title: `${prefix}${l.overview || "Overview"}`,
        path: `${slug}-overview`,
        icon: "mdi:view-dashboard-outline",
        type: "sections",
        max_columns: 3,
        sections: summarySections,
      },
      {
        title: `${prefix}${l.live || l.current || "Live workout"}`,
        path: `${slug}-live`,
        icon: "mdi:run-fast",
        type: "sections",
        max_columns: 2,
        sections: liveSections,
      },
    ];
  }
}


const _FITNESS_TAB_PANEL_BASE = `
  ha-card{
    padding:10px !important;
    border:0 !important;
    border-radius:20px !important;
    box-shadow:none !important;
    overflow:hidden !important;
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
  .hi-grid{gap:6px !important;margin-top:0 !important}
  .hi{
    padding:8px 9px !important;border-radius:11px !important;
    background:var(--card-background-color) !important;
  }
  .hi span{font-size:9px !important}
  .hi strong{font-size:13px !important;margin-top:2px !important}
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
if (!customElements.get("ll-strategy-dashboard-fitness")) customElements.define("ll-strategy-dashboard-fitness", FitnessDashboardStrategy);

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
    name: "Fitness live workout",
    preview: false,
    description: "Current workout metrics and Fitness session controls in one adaptive card.",
    documentationURL: "https://github.com/Chreece/HA-Fitness#fitness-dashboard",
  },
  {
    type: "fitness-workout-card",
    name: "Fitness workout",
    preview: false,
    description: "Latest workout metrics, route and personal-baseline comparison in one adaptive card.",
    documentationURL: "https://github.com/Chreece/HA-Fitness#fitness-dashboard",
  },
  {
    type: "fitness-sleep-recovery-card",
    name: "Fitness sleep & recovery",
    preview: false,
    description: "Sleep stages, duration, HRV and recovery context in one adaptive card.",
    documentationURL: "https://github.com/Chreece/HA-Fitness#fitness-dashboard",
  },
  {
    type: "fitness-evaluation-card",
    name: "Fitness evaluation",
    preview: false,
    description: "Fitness progress and training-load evaluation in one adaptive card.",
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
