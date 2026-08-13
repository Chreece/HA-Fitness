const FITNESS_DASHBOARD_VERSION = "2026.8.10.7";


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

    const e = this._profile?.entities || {};
    const summaryKeys = [
      "last_workout","last_workout_distance","last_workout_duration",
      "last_workout_moving_time","last_workout_average_speed",
      "last_workout_avg_hr","last_workout_avg_power","last_workout_avg_cadence",
      "last_workout_elevation_gain","last_workout_calories",
    ];
    const summary = summaryKeys.map((key) => {
      const item = e[key] ? this._hass.states[e[key]] : null;
      return `${key}:${item?.state || ""}`;
    }).join("|");

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
    if (this._profile?.latest_workout?.sport === "running") return true;
    const e = this._profile?.entities || {};
    const state = this._hass.states[e.last_workout];
    const sport = String(state?.attributes?.sport || "").toLowerCase();
    return sport === "running";
  }

  _workoutSummary() {
    const e = this._profile?.entities || {};
    const running = this._isRunningWorkout();
    const runPace = running ? _fitnessRunPace(this._profile, this._hass) : null;
    const keys = [
      "last_workout", "last_workout_distance", "last_workout_duration",
      "last_workout_average_speed", "last_workout_avg_hr", "last_workout_max_hr",
      "last_workout_hrr_60s", "last_workout_avg_power", "last_workout_weighted_power",
      "last_workout_avg_cadence", "last_workout_elevation_gain",
      "last_workout_calories", "last_workout_banister_trimp",
      "last_workout_aerobic_efficiency", "last_workout_aerobic_decoupling",
      "last_workout_training_load", "last_workout_vo2max"
    ];
    const items = keys.map((key) => ({key, entityId: e[key]})).filter((item) => item.entityId).map(({key, entityId}) => {
      const state = this._hass.states[entityId];
      if (!state || ["unknown","unavailable"].includes(state.state)) return null;
      if (running && key === "last_workout_average_speed") {
        if (!runPace) return null;
        return {
          name: this._profile?.labels?.pace || "Pace",
          value: runPace,
          entityId,
        };
      }
      const unit = state.attributes?.unit_of_measurement || "";
      return {
        name: entityName(this._hass, entityId),
        value: `${state.state}${unit ? ` ${unit}` : ""}`,
        entityId,
      };
    }).filter(Boolean);
    if (running && runPace && !e.last_workout_average_speed) {
      const insertAt = Math.min(3, items.length);
      items.splice(insertAt, 0, {
        name: this._profile?.labels?.pace || "Pace",
        value: runPace,
        entityId: e.last_workout_average_speed || e.last_workout_distance || e.last_workout_duration,
      });
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
      this.shadowRoot.innerHTML = `<ha-card><div class="empty"><strong>${this._escape(title)}</strong><div>${this._escape(this.config.empty_text || labels.no_route || "No GPS route available")}</div></div></ha-card><style>.empty{padding:24px;color:var(--secondary-text-color)}strong{display:block;color:var(--primary-text-color);margin-bottom:8px}</style>`;
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
        ["last_workout_hr_vs_baseline", 20],
        ["last_workout_power_vs_baseline", 30],
        ["last_workout_speed_vs_baseline", 30],
        ["last_workout_trimp_vs_recent", 50],
      ].filter(([key]) => Boolean(e[key])).map(([key, max]) => ({ entity: e[key], max }));
    } catch (_err) {
      this._resolvedMetrics = [];
    }
    this._render();
  }

  getCardSize() { return 4; }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const metrics = this._resolvedMetrics || this.config.metrics || [];
    const rows = metrics.map((metric) => {
      const state = this._hass.states[metric.entity];
      if (!state || state.state === "unknown" || state.state === "unavailable") return "";
      const value = Number(state.state);
      if (!Number.isFinite(value)) return "";
      const max = Number(metric.max || 30);
      const pct = Math.min(50, Math.abs(value) / max * 50);
      const left = value < 0 ? 50 - pct : 50;
      const unit = state.attributes.unit_of_measurement || metric.unit || "";
      return `<div class="row entity-link" data-more-info="${this._escape(metric.entity)}"><div class="line"><span>${this._escape(metric.name || entityName(this._hass, metric.entity))}</span><strong>${value > 0 ? "+" : ""}${value.toFixed(metric.decimals ?? 1)}${unit ? ` ${this._escape(unit)}` : ""}</strong></div><div class="axis"><div class="zero"></div><div class="bar" style="left:${left}%;width:${pct}%"></div></div></div>`;
    }).filter(Boolean).join("");
    const labels = this._profile?.labels || {};
    const title = this.config.title || labels.workout_comparison || "Compared with your baseline";
    if (!rows) {
      this.shadowRoot.innerHTML = `<ha-card><div class="empty"><strong>${this._escape(title)}</strong><div>${this._escape(labels.no_comparison || "No compatible baseline comparison data is currently available.")}</div></div></ha-card><style>.empty{padding:24px;color:var(--secondary-text-color)}strong{display:block;color:var(--primary-text-color);margin-bottom:8px}</style>`;
      return;
    }
    this.shadowRoot.innerHTML = `<ha-card><div class="title">${this._escape(title)}</div><div class="rows">${rows}</div></ha-card><style>.title{font-size:18px;font-weight:600;padding:16px 16px 8px}.rows{padding:0 16px 16px}.row{margin:12px 0}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.line{display:flex;justify-content:space-between;gap:16px;font-size:13px}.line span{color:var(--secondary-text-color)}.axis{height:8px;position:relative;background:var(--secondary-background-color);border-radius:5px;margin-top:6px;overflow:hidden}.zero{position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--divider-color)}.bar{position:absolute;top:0;bottom:0;background:var(--primary-color);border-radius:5px}</style>`;
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
    this._resolveEntities();
  }

  async _resolveEntities() {
    if (!this._hass || !this.config) return;
    if (Array.isArray(this.config.entities) && this.config.entities.length) {
      this._resolvedEntities = this.config.entities;
      this._render();
      return;
    }
    try {
      const data = await this._hass.callWS({ type: "fitness/dashboard/config" });
      const profiles = data?.profiles || [];
      const profile = profiles.find((item) => item.entry_id === this.config.profile_entry_id) || (profiles.length === 1 ? profiles[0] : null);
      this._profile = profile;
      const e = profile?.entities || {};
      this._durationEntity = e.last_sleep_duration || null;
      this._resolvedEntities = ["last_sleep_awake", "last_sleep_light", "last_sleep_deep", "last_sleep_rem"].map((key) => e[key]).filter(Boolean);
    } catch (_err) {
      this._resolvedEntities = [];
    }
    this._render();
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
    const palette = ["#78909c", "#42a5f5", "#5c6bc0", "#ab47bc"];
    const entities = this._resolvedEntities || this.config.entities || [];
    const values = entities.map((entity, index) => {
      const state = this._hass.states[entity];
      const value = Number(state?.state);
      return Number.isFinite(value) && value >= 0 ? { entity, value, color: palette[index % palette.length] } : null;
    }).filter(Boolean);
    const stageTotal = values.reduce((sum, item) => sum + item.value, 0);
    const durationState = this._durationEntity ? this._hass.states[this._durationEntity] : null;
    const durationValue = Number(durationState?.state);
    const total = stageTotal;
    const durationUnit = durationState?.attributes?.unit_of_measurement || "min";
    const normalizedDurationMinutes = Number.isFinite(durationValue) && durationValue > 0
      ? (
          ["h", "hr", "hour", "hours"].includes(String(durationUnit).toLowerCase())
            ? durationValue * 60
            : ["s", "sec", "second", "seconds"].includes(String(durationUnit).toLowerCase())
              ? durationValue / 60
              : durationValue
        )
      : 0;
    const effectiveTotalMinutes = Math.max(stageTotal, normalizedDurationMinutes);
    const displayTotal = this._formatMinutes(effectiveTotalMinutes, "min");
    const labels = this._profile?.labels || {};
    const title = this.config.title || labels.latest_sleep || "Latest sleep";
    if (!values.length || total <= 0) {
      this.shadowRoot.innerHTML = `<ha-card><div class="empty"><strong>${this._escape(title)}</strong><div>${this._escape(labels.no_sleep_stages || "No compatible sleep-stage data is currently available.")}</div></div></ha-card><style>.empty{padding:24px;color:var(--secondary-text-color)}strong{display:block;color:var(--primary-text-color);margin-bottom:8px}</style>`;
      return;
    }
    let cursor = 0;
    const stops = values.map((item) => {
      const start = cursor; cursor += item.value / total * 100;
      return `${item.color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
    }).join(",");
    const legend = values.map((item) => {
      const state = this._hass.states[item.entity];
      const unit = state?.attributes?.unit_of_measurement || "";
      const pct = item.value / total * 100;
      return `<div class="legend-row entity-link" data-more-info="${this._escape(item.entity)}"><span class="dot" style="background:${item.color}"></span><span class="label">${this._escape(entityName(this._hass, item.entity))}</span><strong>${this._formatMinutes(item.value, unit)}</strong><span class="pct">${pct.toFixed(0)}%</span></div>`;
    }).join("");
    this.shadowRoot.innerHTML = `<ha-card><div class="title">${this._escape(title)}</div><div class="body"><div class="donut" style="background:conic-gradient(${stops})"><div class="hole"><strong>${displayTotal}</strong></div></div><div class="legend">${legend}</div></div></ha-card><style>.title{font-size:18px;font-weight:600;padding:16px 16px 6px}.body{display:flex;flex-direction:column;align-items:center;gap:16px;padding:10px 16px 18px;min-width:0}.donut{width:124px;height:124px;border-radius:50%;display:grid;place-items:center}.hole{width:76px;height:76px;border-radius:50%;background:var(--ha-card-background,var(--card-background-color));display:flex;flex-direction:column;align-items:center;justify-content:center}.hole strong{font-size:18px;text-align:center;line-height:1.15;padding:4px}.hole span{font-size:11px;color:var(--secondary-text-color)}.legend{width:100%;min-width:0}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.legend-row{display:grid;grid-template-columns:10px minmax(0,1fr) minmax(72px,max-content) 38px;column-gap:10px;align-items:center;min-width:0;padding:7px 0;font-size:12px}.dot{width:9px;height:9px;border-radius:50%}.label{color:var(--secondary-text-color);min-width:0;white-space:normal;overflow-wrap:normal;word-break:normal;hyphens:auto}.legend-row strong{text-align:right;white-space:nowrap;line-height:1.3}.pct{text-align:right;white-space:nowrap;color:var(--secondary-text-color)}</style>`;
  }

  _escape(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }
}


const _fitnessNumber = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
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

const _fitnessFormatPace = (minutesPerKm) => {
  if (!Number.isFinite(minutesPerKm) || minutesPerKm <= 0 || minutesPerKm > 60) return null;
  let mins = Math.floor(minutesPerKm);
  let secs = Math.round((minutesPerKm - mins) * 60);
  if (secs === 60) { mins += 1; secs = 0; }
  return `${mins}:${String(secs).padStart(2, "0")} min/km`;
};

const _fitnessRunPace = (profile, hass) => {
  if (profile?.latest_workout?.sport !== "running") return null;
  const e = profile?.entities || {};

  // Prefer the normalized average-speed metric when present.
  const fromSpeed = _fitnessPaceFromSpeed(hass.states[e.last_workout_average_speed]);
  if (fromSpeed) return fromSpeed;

  // Otherwise derive pace deterministically from merged Fitness distance/time.
  const distanceKm = _fitnessKmFromState(hass.states[e.last_workout_distance]);
  const timeMinutes =
    _fitnessMinutesFromState(hass.states[e.last_workout_moving_time])
    ?? _fitnessMinutesFromState(hass.states[e.last_workout_duration]);
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
    const ids = [
      e.session_status, e.last_sleep_score, e.last_sleep_duration,
      e.last_sleep_hrv, e.training_load, e.cardiorespiratory_fitness_trend
    ].filter(Boolean);
    const items = ids.map((id) => {
      const state = this._hass.states[id];
      if (!state || ["unknown","unavailable"].includes(state.state)) return "";
      return `<div class="today-item entity-link" data-more-info="${_fitnessEscape(id)}"><span>${_fitnessEscape(entityName(this._hass,id))}</span><strong>${_fitnessDisplay(state,1)}</strong></div>`;
    }).filter(Boolean).join("");
    this.shadowRoot.innerHTML = `<ha-card><div class="today-head"><div><strong>${_fitnessEscape(this.config.title || l.overview || "Today")}</strong><span>${_fitnessEscape(this._profile?.profile_name || "")}</span></div><ha-icon icon="mdi:heart-pulse"></ha-icon></div><div class="today-grid">${items || `<small>No current Fitness data is available yet.</small>`}</div></ha-card><style>
      ha-card{padding:18px}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.today-head{display:flex;justify-content:space-between;align-items:center}.today-head strong{font-size:20px}.today-head span{display:block;color:var(--secondary-text-color);font-size:12px;margin-top:3px}.today-head ha-icon{color:var(--primary-color);--mdc-icon-size:30px}.today-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:16px}.today-item{padding:11px 12px;border-radius:13px;background:var(--secondary-background-color)}.today-item span{display:block;font-size:10px;color:var(--secondary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.today-item strong{display:block;margin-top:4px;font-size:15px}@media(max-width:420px){.today-grid{grid-template-columns:1fr}}</style>`;
  }
}

class FitnessWorkoutHighlightsCard extends FitnessAutoProfileCard {
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const e = this._profile?.entities || {};
    const l = this._profile?.labels || {};
    const zeroIsMissing = new Set([
      "last_workout_distance","last_workout_average_speed","last_workout_avg_power",
      "last_workout_avg_cadence","last_workout_elevation_gain","last_workout_calories",
      "last_workout_strength_sets","last_workout_estimated_1rm"
    ]);
    const keys = [
      "last_workout_distance","last_workout_duration","last_workout_average_speed",
      "last_workout_avg_hr","last_workout_max_hr","last_workout_avg_power","last_workout_avg_cadence",
      "last_workout_elevation_gain","last_workout_calories","last_workout_banister_trimp","last_workout_vo2max",
      "last_workout_rpe","last_workout_session_rpe_load","last_workout_fitness_aerobic_load","last_workout_fitness_high_intensity_load",
      "last_workout_strength_sets","last_workout_estimated_1rm","last_workout_strength_progression"
    ];
    const running = this._profile?.latest_workout?.sport === "running";
    const runPace = running ? _fitnessRunPace(this._profile, this._hass) : null;
    const workoutState = e.last_workout ? this._hass.states[e.last_workout] : null;
    const workoutName = workoutState && !["unknown","unavailable"].includes(workoutState.state)
      ? workoutState.state : null;
    const itemList = keys.map((key) => ({key, id:e[key]})).filter((item) => item.id).map(({key,id}) => {
      const state = this._hass.states[id];
      if (!state || ["unknown","unavailable"].includes(state.state)) return "";
      const numeric = Number(state.state);
      if (zeroIsMissing.has(key) && Number.isFinite(numeric) && Math.abs(numeric) < 1e-12) return "";
      if (running && key === "last_workout_average_speed") {
        return runPace
          ? `<div class="hi entity-link" data-more-info="${_fitnessEscape(id)}"><span>${_fitnessEscape(l.pace || "Pace")}</span><strong>${_fitnessEscape(runPace)}</strong></div>`
          : "";
      }
      return `<div class="hi entity-link" data-more-info="${_fitnessEscape(id)}"><span>${_fitnessEscape(entityName(this._hass,id))}</span><strong>${_fitnessEscape(_fitnessDisplay(state,1))}</strong></div>`;
    }).filter(Boolean);
    if (running && runPace && !e.last_workout_average_speed) {
      itemList.splice(Math.min(2, itemList.length), 0,
        `<div class="hi entity-link" data-more-info="${_fitnessEscape(id)}"><span>${_fitnessEscape(l.pace || "Pace")}</span><strong>${_fitnessEscape(runPace)}</strong></div>`);
    }
    const items = itemList.join("");
    this.shadowRoot.innerHTML = `<ha-card>
      ${workoutName ? `<div class="workout-name entity-link" data-more-info="${_fitnessEscape(e.last_workout || "")}">${_fitnessEscape(workoutName)}</div>` : ""}
      <div class="hi-grid">${items || `<small>${_fitnessEscape(l.no_workout_data || "No completed workout data is available yet.")}</small>`}</div>
    </ha-card><style>
      ha-card{padding:18px;min-width:0;overflow:hidden}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}
      .workout-name{font-size:20px;font-weight:700;line-height:1.25;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:normal;white-space:normal}
      .hi-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px;min-width:0}
      .hi{padding:10px;border-radius:12px;background:var(--secondary-background-color);min-width:0;max-width:100%;overflow:hidden}
      .hi span{display:block;font-size:10px;line-height:1.25;color:var(--secondary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .hi strong{display:block;font-size:14px;line-height:1.3;margin-top:4px;min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere;word-break:normal}
      .hi-grid>small{grid-column:1/-1;color:var(--secondary-text-color);line-height:1.4;overflow-wrap:anywhere}
      @media(max-width:520px){.hi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
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
      ${totalVolume != null ? `<div class="volume-hero"><span>Total volume</span><strong>${totalVolume.toFixed(0)} kg</strong></div>` : ""}
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
    if (!trend && !predicted) {
      this.shadowRoot.innerHTML = `<ha-card><div class="empty">${_fitnessEscape(l.progress_snapshot || "Fitness progress")}<small>No compatible fitness-progress data is available yet.</small></div></ha-card>${this._style()}`;
      return;
    }
    const current = _fitnessNumber(_fitnessAttr(trend, "current_vo2max_ml_kg_min")) ?? _fitnessNumber(trend?.state);
    const mean28 = _fitnessNumber(_fitnessAttr(trend, "vo2max_28d_mean_ml_kg_min"));
    const mean90 = _fitnessNumber(_fitnessAttr(trend, "vo2max_90d_mean_ml_kg_min"));
    const slope = _fitnessNumber(_fitnessAttr(trend, "slope_percent_per_30d"));
    const pctPred = _fitnessNumber(_fitnessAttr(trend, "percent_predicted")) ?? _fitnessNumber(predicted?.state);
    const status = slope == null ? "" : slope > 0.35 ? (l.improving || "Improving") : slope < -0.35 ? (l.declining || "Declining") : (l.stable || "Stable");
    const arrow = slope == null ? "→" : slope > 0.35 ? "↗" : slope < -0.35 ? "↘" : "→";
    const delta28 = current != null && mean28 ? ((current - mean28) / mean28 * 100) : null;
    const bar = Math.max(0, Math.min(100, pctPred ?? 0));
    const rawSeries = Array.isArray(_fitnessAttr(trend, "daily_series")) ? _fitnessAttr(trend, "daily_series") : [];
    const series = rawSeries.map(x => ({v:_fitnessNumber(x?.value), d:String(x?.start || "")})).filter(x => x.v != null).slice(-90);
    let spark = "";
    if (series.length >= 5) {
      const vals = series.map(x => x.v), lo = Math.min(...vals), hi = Math.max(...vals), span = Math.max(hi-lo, 0.1);
      const pts = series.map((x,i) => `${(i/(series.length-1)*100).toFixed(2)},${(34-((x.v-lo)/span)*28).toFixed(2)}`).join(" ");
      spark = `<div class="history entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || "")}"><div class="history-head"><span>${_fitnessEscape(l.history || "History")}</span><small>${series.length} ${_fitnessEscape(l.days_90 || "days")}</small></div><svg viewBox="0 0 100 38" preserveAspectRatio="none" aria-label="VO2max history"><polyline points="${pts}"/></svg></div>`;
    }

    this.shadowRoot.innerHTML = `<ha-card>
      <div class="head"><div><div class="title">${_fitnessEscape(this.config.title || l.progress_snapshot || "Fitness progress")}</div><div class="sub">${_fitnessEscape(status)}</div></div><div class="trend">${arrow}${slope == null ? "" : ` ${slope > 0 ? "+" : ""}${slope.toFixed(2)}%`}</div></div>
      <div class="hero entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || e.vo2max_percent_predicted || "")}"><strong>${current == null ? "—" : current.toFixed(1)}</strong><span>mL/kg/min</span><small>${_fitnessEscape(l.current_vo2max || "Current VO₂max")}</small></div>
      <div class="progress"><div style="width:${bar}%"></div></div>
      ${spark}
      <div class="metrics entity-link" data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || e.vo2max_percent_predicted || "")}">
        ${this._metric(l.mean_28d || "28-day mean", mean28, "mL/kg/min")}
        ${this._metric(l.mean_90d || "90-day mean", mean90, "mL/kg/min")}
        ${this._metric(l.predicted_percent || "% of predicted", pctPred, "%")}
        ${this._metric("Δ 28d", delta28, "%", true)}
      </div>
    </ha-card>${this._style()}`;
  }
  _metric(label, value, unit, signed=false) {
    const formatted = value == null ? "—" : `${signed && value > 0 ? "+" : ""}${value.toFixed(1)}${unit ? ` ${unit}` : ""}`;
    return `<div class="metric"><span>${_fitnessEscape(label)}</span><strong>${formatted}</strong></div>`;
  }
  _style() {
    return `<style>
      ha-card{padding:18px}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.head{display:flex;justify-content:space-between;align-items:flex-start}.title{font-size:19px;font-weight:650}.sub{font-size:12px;color:var(--secondary-text-color);margin-top:3px}.trend{font-size:16px;font-weight:700;color:var(--primary-color)}
      .hero{display:grid;grid-template-columns:auto auto 1fr;align-items:end;gap:6px;margin:20px 0 10px}.hero strong{font-size:40px;line-height:1}.hero span{font-size:12px;color:var(--secondary-text-color);padding-bottom:4px}.hero small{text-align:right;color:var(--secondary-text-color)}
      .progress{height:8px;background:var(--secondary-background-color);border-radius:999px;overflow:hidden}.progress div{height:100%;background:var(--primary-color);border-radius:999px}
      .history{margin-top:16px;padding:10px 12px;border-radius:12px;background:var(--secondary-background-color)}.history-head{display:flex;justify-content:space-between;color:var(--secondary-text-color);font-size:11px}.history svg{width:100%;height:76px;margin-top:7px;overflow:visible}.history polyline{fill:none;stroke:var(--primary-color);stroke-width:1.8;vector-effect:non-scaling-stroke;stroke-linecap:round;stroke-linejoin:round}
      .metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:16px}.metric{padding:10px 12px;border-radius:12px;background:var(--secondary-background-color)}.metric span{display:block;color:var(--secondary-text-color);font-size:11px;margin-bottom:3px}.metric strong{font-size:14px}
      .empty{padding:6px}.empty small{display:block;color:var(--secondary-text-color);margin-top:8px}
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
    const sleepDuration = this._hass.states[e.last_sleep_duration];
    const sleepHrv = this._hass.states[e.last_sleep_hrv];
    const sleepScore = this._hass.states[e.last_sleep_score];
    const deficit = this._hass.states[e.sleep_deficit_7d];
    const recoveryTime = this._hass.states[e.estimated_recovery_time];
    const classifiedSleepMinutes = [
      e.last_sleep_light, e.last_sleep_deep, e.last_sleep_rem,
    ].map((entityId) => _fitnessMinutesFromState(this._hass.states[entityId]))
      .filter((value) => Number.isFinite(value))
      .reduce((sum, value) => sum + value, 0);
    const providerSleepMinutes = _fitnessMinutesFromState(sleepDuration) || 0;
    const effectiveSleepMinutes = Math.max(providerSleepMinutes, classifiedSleepMinutes);
    const effectiveSleepDuration = effectiveSleepMinutes > 0
      ? {state: String(effectiveSleepMinutes), attributes: {unit_of_measurement: "min"}}
      : sleepDuration;

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
    const tone = score == null ? "none" : score >= 85 ? "excellent" : score >= 70 ? "high" : score >= 50 ? "moderate" : score >= 30 ? "low" : "very-low";
    const componentRows = [
      ["autonomic", "mdi:heart-pulse", "HRV / RHR"],
      ["sleep", "mdi:sleep", rtext.sleep],
      ["training", "mdi:dumbbell", rtext.training],
      ["recovery_response", "mdi:heart-sync", e.heart_rate_recovery ? entityName(this._hass,e.heart_rate_recovery) : rtext.response],
    ].map(([key,icon,label]) => {
      const value = _fitnessNumber(components?.[key]?.score);
      if (value == null) return "";
      return `<div class="component"><ha-icon icon="${icon}"></ha-icon><span>${_fitnessEscape(label)}</span><strong>${value.toFixed(0)}</strong><div><i style="width:${Math.max(0,Math.min(100,value))}%"></i></div></div>`;
    }).filter(Boolean).join("");

    const hrvVs = _fitnessNumber(_fitnessAttr(autonomic, "sleep_hrv_vs_28d_percent"));
    const rhrVs = _fitnessNumber(_fitnessAttr(autonomic, "resting_hr_vs_28d_bpm"));

    this.shadowRoot.innerHTML = `<ha-card class="tone-${tone}">
      <div class="title">${_fitnessEscape(this.config.title || l.recovery_snapshot || "Recovery snapshot")}</div>
      <div class="readiness-hero entity-link" data-more-info="${_fitnessEscape(e.readiness || "")}">
        <div class="readiness-ring" style="--p:${bounded * 3.6}deg"><div><strong>${score == null ? "—" : score.toFixed(0)}</strong><span>/ 100</span></div></div>
        <div class="readiness-copy"><small>${_fitnessEscape(readinessName)}</small><strong>${_fitnessEscape(levelText)}</strong>${confidence == null ? "" : `<span>${confidence.toFixed(0)}% ${_fitnessEscape(rtext.confidence)}</span>`}</div>
      </div>
      ${componentRows ? `<div class="components entity-link" data-more-info="${_fitnessEscape(e.readiness || "")}">${componentRows}</div>` : ""}
      <div class="context">
        ${hrvVs == null ? "" : `<span>HRV ${hrvVs > 0 ? "+" : ""}${hrvVs.toFixed(1)}% ${_fitnessEscape(rtext.vs28)}</span>`}
        ${rhrVs == null ? "" : `<span>RHR ${rhrVs > 0 ? "+" : ""}${rhrVs.toFixed(1)} bpm ${_fitnessEscape(rtext.vs28)}</span>`}
      </div>
      <div class="metrics">
        ${this._sleepScoreMetric(l.sleep_score || "Sleep score", sleepScore, e.last_sleep_score)}
        ${this._metric(l.sleep_duration || "Sleep duration", effectiveSleepDuration, true, e.last_sleep_duration)}
        ${this._metric(l.sleep_hrv || "Sleep HRV", sleepHrv, false, e.last_sleep_hrv)}
        ${recoveryTime ? this._metric(entityName(this._hass, e.estimated_recovery_time), recoveryTime, false, e.estimated_recovery_time) : ""}
        ${this._metric(l.sleep_deficit || "7-day sleep deficit", deficit, true, e.sleep_deficit_7d)}
      </div>
    </ha-card><style>
      ha-card{padding:18px;--readiness:#78909c;--readiness-soft:color-mix(in srgb,var(--readiness) 14%,transparent)}
      ha-card.tone-excellent{--readiness:#2e7d32}ha-card.tone-high{--readiness:#00897b}ha-card.tone-moderate{--readiness:#f9a825}ha-card.tone-low{--readiness:#ef6c00}ha-card.tone-very-low{--readiness:#c62828}
      .entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}
      .title{font-size:19px;font-weight:650}.readiness-hero{display:grid;grid-template-columns:116px minmax(0,1fr);align-items:center;gap:18px;margin-top:16px;padding:14px;border-radius:18px;background:linear-gradient(135deg,var(--readiness-soft),var(--secondary-background-color))}
      .readiness-ring{width:104px;height:104px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--readiness) var(--p),color-mix(in srgb,var(--readiness) 16%,var(--secondary-background-color)) 0);box-shadow:0 0 0 1px color-mix(in srgb,var(--readiness) 25%,transparent)}.readiness-ring>div{width:76px;height:76px;border-radius:50%;background:var(--ha-card-background,var(--card-background-color));display:flex;align-items:baseline;justify-content:center}.readiness-ring strong{font-size:31px;line-height:76px;color:var(--readiness)}.readiness-ring span{font-size:10px;color:var(--secondary-text-color);margin-left:2px}
      .readiness-copy{min-width:0}.readiness-copy small{display:block;color:var(--secondary-text-color);font-size:11px}.readiness-copy strong{display:block;color:var(--readiness);font-size:24px;line-height:1.15;margin-top:3px;overflow-wrap:normal;word-break:normal}.readiness-copy span{display:block;color:var(--secondary-text-color);font-size:11px;line-height:1.35;margin-top:7px}
      .components{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}.component{display:grid;grid-template-columns:22px minmax(0,1fr) auto;align-items:center;column-gap:7px;padding:9px 10px;border-radius:12px;background:var(--secondary-background-color);min-width:0}.component ha-icon{--mdc-icon-size:18px;color:var(--readiness)}.component span{font-size:10px;color:var(--secondary-text-color);min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.component strong{font-size:13px}.component>div{grid-column:2/4;height:4px;border-radius:999px;background:var(--divider-color);overflow:hidden;margin-top:5px}.component i{display:block;height:100%;border-radius:999px;background:var(--readiness)}
      .context{display:flex;flex-wrap:wrap;gap:6px 12px;margin-top:10px}.context span{font-size:10px;color:var(--secondary-text-color)}
      .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:8px;margin-top:12px}.metric{background:var(--secondary-background-color);padding:10px;border-radius:12px;min-width:0;overflow:hidden}.metric span{display:block;color:var(--secondary-text-color);font-size:10px;line-height:1.3;margin-bottom:4px;overflow-wrap:anywhere}.metric strong{display:block;font-size:13px;line-height:1.35;overflow-wrap:anywhere}
      @media(max-width:430px){.readiness-hero{grid-template-columns:92px minmax(0,1fr);gap:12px;padding:12px}.readiness-ring{width:84px;height:84px}.readiness-ring>div{width:62px;height:62px}.readiness-ring strong{font-size:26px;line-height:62px}.readiness-copy strong{font-size:20px}.components{grid-template-columns:1fr}}
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
    const load = this._hass.states[e.training_load];
    const adaptation = e.training_adaptation_status ? this._hass.states[e.training_adaptation_status] : null;
    if (!load) {
      this.shadowRoot.innerHTML = `<ha-card><div class="empty">${_fitnessEscape(l.training_load_snapshot || "Training load")}<small>No compatible training-load data is available yet.</small></div></ha-card><style>.empty{padding:18px}.empty small{display:block;color:var(--secondary-text-color);margin-top:8px}</style>`;
      return;
    }
    const recent = _fitnessNumber(_fitnessAttr(load, "trimp_7d")) ?? _fitnessNumber(load.state);
    const baseline = _fitnessNumber(_fitnessAttr(load, "trimp_28d_weekly_equivalent"));
    const workouts = _fitnessNumber(_fitnessAttr(load, "workouts_7d"));
    const activeDays = _fitnessNumber(_fitnessAttr(load, "active_days_7d"));
    const duration = _fitnessNumber(_fitnessAttr(load, "training_duration_7d_min"));
    const baselineReliable = adaptation ? _fitnessAttr(adaptation, "baseline_reliable") === true : false;
    const ratio = baselineReliable && recent != null && baseline && baseline > 0 ? recent / baseline : null;
    const ratioPct = ratio == null ? 0 : Math.max(0, Math.min(180, ratio * 100));
    const adaptCode = String(_fitnessAttr(adaptation, "status") || "insufficient_data");
    const adaptTones = {productive:"#2e7d32",maintaining:"#00897b",insufficient_stimulus:"#5c6bc0",absent:"#78909c",high_load:"#f9a825",excessive:"#ef6c00",strained:"#d84315",unproductive:"#c62828",insufficient_data:"#78909c"};
    const adaptTone = adaptTones[adaptCode] || adaptTones.insufficient_data;

    this.shadowRoot.innerHTML = `<ha-card style="--adapt:${adaptTone}">
      ${adaptation ? `<div class="adapt entity-link" data-more-info="${_fitnessEscape(e.training_adaptation_status || "")}"><span>${_fitnessEscape(l.training_adaptation_card || "Training adaptation")}</span><strong>${_fitnessEscape(adaptation.state)}</strong></div>` : ""}
      <div class="head entity-link" data-more-info="${_fitnessEscape(e.training_load || "")}"><div class="title">${_fitnessEscape(this.config.title || l.training_load_snapshot || "Training load")}</div><div class="ratio">${ratio == null ? "—" : `${ratio.toFixed(2)}×`}</div></div>
      <div class="scale"><div class="zone"></div><div class="marker" style="left:${Math.min(100, ratioPct / 1.8)}%"></div></div>
      <div class="pair entity-link" data-more-info="${_fitnessEscape(e.training_load || "")}">
        <div><span>${_fitnessEscape(l.recent_load || "7-day TRIMP")}</span><strong>${recent == null ? "—" : recent.toFixed(1)}</strong></div>
        <div><span>${_fitnessEscape(l.baseline_load || "28-day weekly baseline")}</span><strong>${baseline == null ? "—" : baseline.toFixed(1)}</strong></div>
      </div>
      <div class="metrics entity-link" data-more-info="${_fitnessEscape(e.training_load || "")}">
        ${this._metric(l.workouts_7d || "Workouts / 7 days", workouts, "")}
        ${this._metric(l.active_days_7d || "Active days / 7 days", activeDays, "")}
        ${this._metric(l.duration_7d || "Training / 7 days", duration, "min")}
      </div>
    </ha-card><style>
      ha-card{padding:18px}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.adapt{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 11px;margin-bottom:12px;border-radius:12px;background:color-mix(in srgb,var(--adapt) 14%,var(--secondary-background-color));border-left:3px solid var(--adapt)}.adapt span{font-size:10px;color:var(--secondary-text-color)}.adapt strong{font-size:14px;color:var(--adapt);text-align:right;overflow-wrap:anywhere}.head{display:flex;justify-content:space-between;align-items:center}.title{font-size:19px;font-weight:650}.ratio{font-size:22px;font-weight:700;color:var(--primary-color)}
      .scale{height:12px;background:linear-gradient(90deg,var(--secondary-background-color),var(--primary-color),var(--secondary-background-color));border-radius:999px;margin:18px 0 10px;position:relative;opacity:.9}.marker{position:absolute;top:-4px;width:3px;height:20px;background:var(--primary-text-color);border-radius:2px;transform:translateX(-1px)}
      .pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}.pair>div,.metrics>div{background:var(--secondary-background-color);padding:10px 12px;border-radius:12px}.pair span,.metrics span{display:block;color:var(--secondary-text-color);font-size:10px;margin-bottom:4px}.pair strong{font-size:18px}
      .metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px}.metrics strong{font-size:13px}.empty{padding:18px}
      @media(max-width:480px){.metrics{grid-template-columns:1fr}.pair{grid-template-columns:1fr}}
    </style>`;
  }
  _metric(label, value, unit) {
    return `<div><span>${_fitnessEscape(label)}</span><strong>${value == null ? "—" : `${value.toFixed(0)}${unit ? ` ${unit}` : ""}`}</strong></div>`;
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

  _shell(title, icon, children) {
    this.shadowRoot.innerHTML = `<ha-card><div class="composite-head"><ha-icon icon="${icon}"></ha-icon><strong>${_fitnessEscape(title)}</strong></div><div class="composite-body"></div></ha-card><style>
      ha-card{padding:16px}.composite-head{display:flex;align-items:center;gap:10px;font-size:20px;margin:2px 2px 12px}.composite-head ha-icon{color:var(--primary-color)}
      .composite-body{display:grid;gap:12px}.composite-body>*{--ha-card-background:transparent;--ha-card-border-width:0px;--ha-card-box-shadow:none}
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
    const e = this._profile.entities || {};
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
      ha-card{padding:16px;overflow:hidden}.entity-link{cursor:pointer}.entity-link:hover{filter:brightness(1.04)}.live-head{display:flex;align-items:center;gap:10px;margin:2px 2px 14px;min-width:0}.live-head>ha-icon{color:var(--primary-color);--mdc-icon-size:28px}.live-head>div{min-width:0}.live-head strong{display:block;font-size:20px;line-height:1.25;overflow-wrap:anywhere}.live-head span{display:block;color:var(--secondary-text-color);font-size:11px;margin-top:2px;overflow-wrap:anywhere}
      .live-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:8px}.live-metric{min-width:0;padding:11px 12px;border-radius:12px;background:var(--secondary-background-color);overflow:hidden}.live-metric span{display:block;color:var(--secondary-text-color);font-size:10px;line-height:1.3;overflow-wrap:anywhere}.live-metric strong{display:block;font-size:15px;line-height:1.3;margin-top:4px;overflow-wrap:anywhere}.live-empty{grid-column:1/-1;color:var(--secondary-text-color);padding:12px 2px}
      .live-controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-top:12px}.live-control{appearance:none;border:1px solid var(--divider-color);background:var(--secondary-background-color);color:var(--primary-text-color);border-radius:12px;min-height:46px;padding:8px 10px;display:flex;align-items:center;justify-content:center;gap:7px;font:inherit;cursor:pointer;min-width:0}.live-control ha-icon{color:var(--primary-color);--mdc-icon-size:21px}.live-control span{min-width:0;font-size:12px;font-weight:600;line-height:1.25;overflow-wrap:anywhere}.live-control:active{transform:scale(.98)}
      @media(max-width:420px){.live-grid,.live-controls{grid-template-columns:1fr 1fr}}
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
    return ["session_rpe","last_workout","last_workout_rpe","last_workout_session_rpe_load","last_workout_rpe_load_vs_baseline"];
  }

  _render() {
    if (!this.shadowRoot || !this._hass || !this._profile) return;
    const e = this._profile.entities || {};
    const l = this._profile.labels || {};
    const rpeId = e.session_rpe;
    const workoutId = e.last_workout;
    const workout = workoutId ? this._hass.states[workoutId] : null;
    const rpeState = rpeId ? this._hass.states[rpeId] : null;
    if (!rpeId || !rpeState || !workout || workout.state === "unavailable") {
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
      "last_workout","last_workout_distance","last_workout_duration",
      "last_workout_moving_time","last_workout_average_speed",
      "last_workout_avg_hr","last_workout_max_hr","last_workout_hrr_60s",
      "last_workout_avg_power","last_workout_weighted_power",
      "last_workout_avg_cadence","last_workout_elevation_gain",
      "last_workout_calories","last_workout_banister_trimp",
      "last_workout_aerobic_efficiency","last_workout_aerobic_decoupling",
      "last_workout_training_load","last_workout_vo2max",
      "last_workout_efficiency_vs_baseline","last_workout_decoupling_vs_baseline",
      "last_workout_hr_vs_baseline","last_workout_power_vs_baseline",
      "last_workout_speed_vs_baseline","last_workout_trimp_vs_recent",
      "session_rpe","last_workout_rpe","last_workout_session_rpe_load","last_workout_rpe_load_vs_baseline",
      "last_workout_fitness_aerobic_load","last_workout_fitness_high_intensity_load",
      "last_workout_strength_sets","last_workout_estimated_1rm","last_workout_strength_progression",
    ];
  }

  _extraSignatureParts() {
    return (this._profile?.route_candidates || []).map((route) => {
      const state = this._hass?.states?.[route.entity_id];
      const value = state?.attributes?.[route.attribute];
      let encoded = "";
      try { encoded = JSON.stringify(value); } catch (_err) { encoded = String(value ?? ""); }
      return `route:${route.entity_id}:${route.attribute}:${encoded}`;
    });
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
    if (e.session_rpe && e.last_workout) {
      children.push(this._mount("fitness-workout-rpe-card"));
    }
    if (["last_workout_efficiency_vs_baseline","last_workout_decoupling_vs_baseline","last_workout_hr_vs_baseline","last_workout_power_vs_baseline","last_workout_speed_vs_baseline","last_workout_trimp_vs_recent"].some(k => e[k])) {
      children.push(this._mount("fitness-comparison-card"));
    }
    if (e.last_workout_strength_sets && this._hass.states[e.last_workout_strength_sets]?.attributes?.strength_analysis) {
      children.push(this._mount("fitness-strength-details-card"));
    }
    this._shell(this.config.title || l.latest_workout || "Latest workout", "mdi:run", children);
  }
}

class FitnessSleepRecoveryCard extends FitnessCompositeCard {
  _relevantEntityKeys() {
    return [
      "last_sleep_duration","last_sleep_time_in_bed","last_sleep_awake",
      "last_sleep_light","last_sleep_deep","last_sleep_rem","last_sleep_score",
      "last_sleep_hrv","last_sleep_average_hr","last_sleep_respiratory_rate",
      "last_sleep_spo2","last_sleep_efficiency","readiness","sleep_consistency",
      "sleep_deficit_7d","autonomic_recovery_trend","heart_rate_recovery",
      "training_recovery_relationship",
    ];
  }

  _render() {
    if (!this.shadowRoot || !this._hass || !this._profile) return;
    const l = this._profile.labels || {};
    const e = this._profile.entities || {};
    const children = [this._mount("fitness-recovery-card")];
    if (["last_sleep_awake","last_sleep_light","last_sleep_deep","last_sleep_rem"].some(k => e[k] && this._hass.states[e[k]])) {
      children.push(this._mount("fitness-sleep-stage-card"));
    }
    this._shell(this.config.title || l.recovery || "Recovery & sleep", "mdi:heart-pulse", children);
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

  _render() {
    if (!this.shadowRoot || !this._hass || !this._profile) return;
    const l = this._profile.labels || {};
    const e = this._profile.entities || {};
    const children = [];
    if (e.cardiorespiratory_fitness_trend || e.vo2max_percent_predicted) children.push(this._mount("fitness-progress-card"));
    if (e.training_load) children.push(this._mount("fitness-training-load-card"));
    this._shell(this.config.title || l.evaluation || "Evaluation", "mdi:chart-line", children);
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
        heading(l.current || "Current workout", "mdi:run-fast"),
        tileGrid(hass, liveCore, 2),
        controls.length ? tileGrid(hass, controls, 2) : null,
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
