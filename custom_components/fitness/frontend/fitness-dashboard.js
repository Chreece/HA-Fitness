const FITNESS_DASHBOARD_VERSION = "2026.8.4";


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
    if (!config?.entity) throw new Error("fitness-route-card requires an entity");
    this.config = config;
    this.attachShadow({ mode: "open" });
    this._resizeObserver = new ResizeObserver(() => this._render());
  }

  set hass(hass) {
    this._hass = hass;
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
    const pad = 28;
    for (let zoom = 17; zoom >= 2; zoom--) {
      const projected = points.map(([lat, lon]) => this._mercator(lat, lon, zoom));
      const xs = projected.map((p) => p[0]), ys = projected.map((p) => p[1]);
      const spanX = Math.max(...xs) - Math.min(...xs);
      const spanY = Math.max(...ys) - Math.min(...ys);
      if (spanX <= width - pad * 2 && spanY <= height - pad * 2) {
        return { zoom, projected, minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
      }
    }
    const projected = points.map(([lat, lon]) => this._mercator(lat, lon, 2));
    const xs = projected.map((p) => p[0]), ys = projected.map((p) => p[1]);
    return { zoom: 2, projected, minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
  }

  _render() {
    if (!this.shadowRoot || !this._hass || !this.config) return;
    const state = this._hass.states[this.config.entity];
    const value = state?.attributes?.[this.config.attribute || "polyline"];
    const points = this._extractPoints(value);
    const title = this.config.title || entityName(this._hass, this.config.entity);
    const height = Number(this.config.height || 340);
    if (points.length < 2) {
      this.shadowRoot.innerHTML = `<ha-card><div class="empty"><strong>${this._escape(title)}</strong><div>${this._escape(this.config.empty_text || "No GPS route available")}</div></div></ha-card><style>.empty{padding:24px;color:var(--secondary-text-color)}strong{display:block;color:var(--primary-text-color);margin-bottom:8px}</style>`;
      return;
    }

    const width = Math.max(this.clientWidth || 600, 300);
    const fit = this._fit(points, width, height);
    const centerX = (fit.minX + fit.maxX) / 2;
    const centerY = (fit.minY + fit.maxY) / 2;
    const originX = centerX - width / 2;
    const originY = centerY - height / 2;
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
    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="header"><div class="title">${this._escape(title)}</div><div class="meta">${points.length} GPS</div></div>
        <div class="map" style="height:${height}px">
          ${tiles.join("")}
          <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <polyline points="${route}" fill="none" stroke="var(--primary-color)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
            <circle cx="${start[0]-originX}" cy="${start[1]-originY}" r="6" class="start"/>
            <circle cx="${end[0]-originX}" cy="${end[1]-originY}" r="6" class="end"/>
          </svg>
          <div class="attribution">© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a></div>
        </div>
        ${this.config.privacy_text ? `<div class="privacy">${this._escape(this.config.privacy_text)}</div>` : ""}
      </ha-card>
      <style>
        ha-card{overflow:hidden}.header{display:flex;align-items:center;justify-content:space-between;padding:16px 16px 12px}.title{font-size:18px;font-weight:600}.meta{font-size:12px;color:var(--secondary-text-color)}
        .map{position:relative;overflow:hidden;background:var(--secondary-background-color)}.tile{position:absolute;width:256px;height:256px;user-select:none}svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.start{fill:#2e7d32;stroke:white;stroke-width:2}.end{fill:#c62828;stroke:white;stroke-width:2}.attribution{position:absolute;right:4px;bottom:3px;background:rgba(255,255,255,.78);font-size:10px;padding:1px 4px;border-radius:3px;color:#333}.attribution a{color:#333}.privacy{padding:8px 16px 12px;font-size:11px;color:var(--secondary-text-color)}
      </style>`;
  }

  _escape(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
  }
}

class FitnessComparisonCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this.attachShadow({ mode: "open" });
  }
  set hass(hass) { this._hass = hass; this._render(); }
  getCardSize() { return 4; }
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const rows = (this.config.metrics || []).map((metric) => {
      const state = this._hass.states[metric.entity];
      if (!state || state.state === "unknown" || state.state === "unavailable") return "";
      const value = Number(state.state);
      if (!Number.isFinite(value)) return "";
      const max = Number(metric.max || 30);
      const pct = Math.min(50, Math.abs(value) / max * 50);
      const left = value < 0 ? 50 - pct : 50;
      const unit = state.attributes.unit_of_measurement || metric.unit || "";
      return `<div class="row"><div class="line"><span>${this._escape(metric.name || entityName(this._hass, metric.entity))}</span><strong>${value > 0 ? "+" : ""}${value.toFixed(metric.decimals ?? 1)}${unit ? ` ${this._escape(unit)}` : ""}</strong></div><div class="axis"><div class="zero"></div><div class="bar" style="left:${left}%;width:${pct}%"></div></div></div>`;
    }).filter(Boolean).join("");
    if (!rows) { this.shadowRoot.innerHTML = ""; return; }
    this.shadowRoot.innerHTML = `<ha-card><div class="title">${this._escape(this.config.title || "Comparison")}</div><div class="rows">${rows}</div></ha-card><style>.title{font-size:18px;font-weight:600;padding:16px 16px 8px}.rows{padding:0 16px 16px}.row{margin:12px 0}.line{display:flex;justify-content:space-between;gap:16px;font-size:13px}.line span{color:var(--secondary-text-color)}.axis{height:8px;position:relative;background:var(--secondary-background-color);border-radius:5px;margin-top:6px;overflow:hidden}.zero{position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--divider-color)}.bar{position:absolute;top:0;bottom:0;background:var(--primary-color);border-radius:5px}</style>`;
  }
  _escape(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }
}


class FitnessSleepStageCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; this.attachShadow({ mode: "open" }); }
  set hass(hass) { this._hass = hass; this._render(); }
  getCardSize() { return 4; }
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const palette = ["#78909c", "#42a5f5", "#5c6bc0", "#ab47bc"];
    const values = (this.config.entities || []).map((entity, index) => {
      const state = this._hass.states[entity];
      const value = Number(state?.state);
      return Number.isFinite(value) && value >= 0 ? { entity, value, color: palette[index % palette.length] } : null;
    }).filter(Boolean);
    const total = values.reduce((sum, item) => sum + item.value, 0);
    if (!values.length || total <= 0) { this.shadowRoot.innerHTML = ""; return; }
    let cursor = 0;
    const stops = values.map((item) => {
      const start = cursor; cursor += item.value / total * 100;
      return `${item.color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
    }).join(",");
    const legend = values.map((item) => {
      const state = this._hass.states[item.entity];
      const unit = state?.attributes?.unit_of_measurement || "";
      const pct = item.value / total * 100;
      return `<div class="legend-row"><span class="dot" style="background:${item.color}"></span><span class="label">${this._escape(entityName(this._hass, item.entity))}</span><strong>${item.value.toFixed(0)}${unit ? ` ${this._escape(unit)}` : ""}</strong><span class="pct">${pct.toFixed(0)}%</span></div>`;
    }).join("");
    this.shadowRoot.innerHTML = `<ha-card><div class="title">${this._escape(this.config.title || "Sleep stages")}</div><div class="body"><div class="donut" style="background:conic-gradient(${stops})"><div class="hole"><strong>${total.toFixed(0)}</strong><span>min</span></div></div><div class="legend">${legend}</div></div></ha-card><style>.title{font-size:18px;font-weight:600;padding:16px 16px 6px}.body{display:grid;grid-template-columns:140px 1fr;align-items:center;gap:18px;padding:10px 16px 18px}.donut{width:124px;height:124px;border-radius:50%;display:grid;place-items:center}.hole{width:76px;height:76px;border-radius:50%;background:var(--ha-card-background,var(--card-background-color));display:flex;flex-direction:column;align-items:center;justify-content:center}.hole strong{font-size:22px}.hole span{font-size:11px;color:var(--secondary-text-color)}.legend-row{display:grid;grid-template-columns:10px 1fr auto 38px;gap:8px;align-items:center;margin:8px 0;font-size:12px}.dot{width:9px;height:9px;border-radius:50%}.label{color:var(--secondary-text-color)}.pct{text-align:right;color:var(--secondary-text-color)}@media(max-width:480px){.body{grid-template-columns:1fr}.donut{margin:auto}}</style>`;
  }
  _escape(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }
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
    const l = profile.labels || {};
    const prefix = multi ? `${profile.profile_name} · ` : "";
    const slug = profile.entry_id.slice(0, 8);

    const overviewBadges = only(hass, e, ["session_status", "last_sleep_duration", "cardiorespiratory_fitness_trend"]).map(entityBadge);
    const liveCore = only(hass, e, ["session_status", "session_duration", "current_heart_rate", "current_power", "current_cadence", "current_speed", "current_pace", "current_distance"]);
    const workoutCore = only(hass, e, ["last_workout", "last_workout_duration", "last_workout_distance", "last_workout_avg_hr", "last_workout_avg_power", "last_workout_calories"]);
    const sleepCore = only(hass, e, ["last_sleep_duration", "last_sleep_score", "last_sleep_hrv", "last_sleep_average_hr", "last_sleep_deep", "last_sleep_rem"]);
    const evalCore = only(hass, e, ["cardiorespiratory_fitness_trend", "vo2max_percent_predicted", "autonomic_recovery_trend", "sleep_deficit_7d", "training_load", "heart_rate_recovery"]);
    const controls = only(hass, e, ["start_workout", "pause_workout", "resume_workout", "stop_workout"]);

    const overviewSections = [
      section([heading(l.current || "Current workout", "mdi:run-fast", overviewBadges), tileGrid(hass, liveCore, 2), controls.length ? tileGrid(hass, controls, 2) : null]),
      section([heading(l.evaluation || "Evaluation", "mdi:chart-line"), tileGrid(hass, evalCore, 2), markdownAI(e.ai_general_evaluation, l.ai_summary || "AI evaluation")]),
      section([heading(l.latest_workout || "Latest workout", "mdi:shoe-print"), tileGrid(hass, workoutCore, 2)]),
      section([heading(l.latest_sleep || "Latest sleep", "mdi:sleep"), tileGrid(hass, sleepCore, 2)]),
    ];

    const fitnessTrend = statisticGraph(hass, only(hass, e, ["cardiorespiratory_fitness_trend", "vo2max_percent_predicted"]), l.fitness_progress || "Fitness progress", 90);
    const recoveryTrend = statisticGraph(hass, only(hass, e, ["autonomic_recovery_trend", "heart_rate_recovery"]), l.recovery_progress || "Recovery progress", 90);
    const trainingTrend = statisticGraph(hass, only(hass, e, ["training_load"]), l.training_progress || "Training progress", 90);
    const sleepTrend = statisticGraph(hass, only(hass, e, ["last_sleep_duration", "sleep_consistency", "sleep_deficit_7d", "last_sleep_hrv"]), l.sleep_progress || "Sleep progress", 90);

    const progressSections = [
      section([heading(l.fitness_progress || "Fitness progress", "mdi:heart-pulse"), fitnessTrend, tileGrid(hass, only(hass, e, ["cardiorespiratory_fitness_trend", "vo2max_percent_predicted"]), 2)]),
      section([heading(l.recovery_progress || "Recovery progress", "mdi:heart-cog"), recoveryTrend, tileGrid(hass, only(hass, e, ["autonomic_recovery_trend", "heart_rate_recovery", "training_recovery_relationship"]), 2)]),
      section([heading(l.training_progress || "Training progress", "mdi:chart-timeline-variant"), trainingTrend, tileGrid(hass, only(hass, e, ["training_load"]), 2)]),
      section([heading(l.sleep_progress || "Sleep progress", "mdi:power-sleep"), sleepTrend, tileGrid(hass, only(hass, e, ["sleep_consistency", "sleep_deficit_7d"]), 2)]),
    ];

    const route = (profile.route_candidates || [])[0];
    const routeCard = route ? {
      type: "custom:fitness-route-card",
      entity: route.entity_id,
      attribute: route.attribute,
      title: l.route || "Workout route",
      empty_text: l.no_route || "No GPS route is available for the latest workout.",
      privacy_text: l.route_privacy || "",
      height: 360,
    } : null;

    const comparisonMetrics = [
      ["last_workout_efficiency_vs_baseline", 20], ["last_workout_decoupling_vs_baseline", 20],
      ["last_workout_hr_vs_baseline", 20], ["last_workout_power_vs_baseline", 30],
      ["last_workout_speed_vs_baseline", 30], ["last_workout_trimp_vs_recent", 50],
    ].filter(([key]) => Boolean(e[key])).map(([key, max]) => ({ entity: e[key], max }));

    const workoutDetail = only(hass, e, [
      "last_workout", "last_workout_duration", "last_workout_distance", "last_workout_moving_time", "last_workout_calories",
      "last_workout_avg_hr", "last_workout_max_hr", "last_workout_hrr_60s", "last_workout_avg_power", "last_workout_weighted_power",
      "last_workout_avg_cadence", "last_workout_average_speed", "last_workout_elevation_gain", "last_workout_banister_trimp",
      "last_workout_aerobic_efficiency", "last_workout_aerobic_decoupling", "last_workout_training_load", "last_workout_vo2max",
    ]);
    const workoutSections = [
      section([heading(l.latest_workout || "Latest workout", "mdi:shoe-print"), tileGrid(hass, workoutDetail, 2), markdownAI(e.ai_workout_evaluation, l.ai_summary || "AI evaluation")]),
      ...(routeCard ? [section([heading(l.route || "Workout route", "mdi:map-marker-path"), routeCard])] : []),
      ...(comparisonMetrics.length ? [section([heading(l.workout_comparison || "Compared with your baseline", "mdi:compare-horizontal"), { type: "custom:fitness-comparison-card", title: l.workout_comparison || "Compared with your baseline", metrics: comparisonMetrics }])] : []),
    ];

    const sleepStages = only(hass, e, ["last_sleep_awake", "last_sleep_light", "last_sleep_deep", "last_sleep_rem"]);
    const recoverySections = [
      section([heading(l.latest_sleep || "Latest sleep", "mdi:sleep"), tileGrid(hass, sleepCore, 2), sleepStages.length ? { type: "custom:fitness-sleep-stage-card", title: l.latest_sleep || "Latest sleep", entities: sleepStages } : null]),
      section([heading(l.recovery_progress || "Recovery progress", "mdi:heart-cog"), recoveryTrend, tileGrid(hass, only(hass, e, ["autonomic_recovery_trend", "heart_rate_recovery", "training_recovery_relationship"]), 2)]),
      section([heading(l.sleep_progress || "Sleep progress", "mdi:chart-bell-curve-cumulative"), sleepTrend, tileGrid(hass, only(hass, e, ["sleep_consistency", "sleep_deficit_7d"]), 2)]),
    ];

    return [
      { title: `${prefix}${l.overview || "Overview"}`, path: `${slug}-overview`, icon: "mdi:view-dashboard-outline", type: "sections", max_columns: 4, sections: overviewSections },
      { title: `${prefix}${l.progress || "Progress"}`, path: `${slug}-progress`, icon: "mdi:chart-line", type: "sections", max_columns: 4, sections: progressSections },
      { title: `${prefix}${l.workouts || "Workouts"}`, path: `${slug}-workouts`, icon: "mdi:run", type: "sections", max_columns: 4, sections: workoutSections },
      { title: `${prefix}${l.recovery || "Recovery & sleep"}`, path: `${slug}-recovery`, icon: "mdi:sleep", type: "sections", max_columns: 4, sections: recoverySections },
    ];
  }
}

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
for (const card of [
  { type: "fitness-route-card", name: "Fitness workout route", description: "Display a GPS workout route." },
  { type: "fitness-comparison-card", name: "Fitness baseline comparison", description: "Visualize workout changes versus personal baseline." },
  { type: "fitness-sleep-stage-card", name: "Fitness sleep stages", description: "Visualize the latest sleep-stage distribution." },
]) {
  if (!window.customCards.some((item) => item.type === card.type)) window.customCards.push(card);
}

console.info(`%c HA-Fitness dashboard ${FITNESS_DASHBOARD_VERSION} `, "background:#41BDF5;color:#fff;font-weight:600;padding:3px 6px;border-radius:4px");
