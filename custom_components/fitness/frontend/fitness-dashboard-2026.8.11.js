/*
 * HA-Fitness dashboard refinements for 2026.8.11.
 *
 * Keep the established dashboard implementation as the base, then enhance
 * selected cards after their normal render. This minimizes duplication while
 * preserving Home Assistant's normal editor/card registration.
 */
import "./fitness-dashboard.js?v=2026.8.10.11";

const FITNESS_811_VERSION = "2026.8.11.1";

const number = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const minutesFromState = (state) => {
  const value = number(state?.state);
  if (value == null || value < 0) return null;
  const unit = String(state?.attributes?.unit_of_measurement || "min").toLowerCase();
  if (["h", "hr", "hour", "hours"].includes(unit)) return value * 60;
  if (["s", "sec", "second", "seconds"].includes(unit)) return value / 60;
  return value;
};

const formatMinutes = (minutes) => {
  const value = number(minutes);
  if (value == null) return "—";
  const total = Math.max(0, Math.round(value));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  if (!hours) return `${mins} min`;
  return `${hours} h${mins ? ` ${mins} min` : ""}`;
};

const appendStyle = (root, css, id) => {
  if (!root || root.querySelector(`style[data-fitness-811="${id}"]`)) return;
  const style = document.createElement("style");
  style.dataset.fitness811 = id;
  style.textContent = css;
  root.appendChild(style);
};

const patchRender = (tag, decorator) => {
  const Card = customElements.get(tag);
  if (!Card?.prototype?._render || Card.prototype._fitness811Patched) return;
  const original = Card.prototype._render;
  Card.prototype._render = function (...args) {
    const result = original.apply(this, args);
    try {
      decorator.call(this);
    } catch (err) {
      console.debug(`[HA-Fitness ${FITNESS_811_VERSION}] ${tag} refinement skipped`, err);
    }
    return result;
  };
  Card.prototype._fitness811Patched = true;
};

/* -------------------------------------------------------------------------
 * Recovery/readiness: move readiness into "Ready for next workout" and make
 * the whole recovery block denser. If recovery-time data is unavailable,
 * preserve the original standalone readiness presentation.
 * ---------------------------------------------------------------------- */
patchRender("fitness-recovery-card", function () {
  const root = this.shadowRoot;
  const next = root?.querySelector(".next-workout");
  const readiness = root?.querySelector(".readiness-panel");
  if (!root || !next || !readiness) return;

  const score = readiness.querySelector(".readiness-ring strong")?.textContent?.trim() || "—";
  const name = readiness.querySelector(".readiness-copy small")?.textContent?.trim() || "Training readiness";
  const level = readiness.querySelector(".readiness-copy strong")?.textContent?.trim() || "";
  const confidence = readiness.querySelector(".readiness-copy span")?.textContent?.trim() || "";
  const entityId = readiness.dataset.moreInfo || "";

  const inline = document.createElement("div");
  inline.className = "readiness-inline entity-link";
  if (entityId) inline.dataset.moreInfo = entityId;
  inline.innerHTML = `
    <div class="readiness-inline-copy">
      <small>${name}</small>
      <strong>${level}</strong>
      ${confidence ? `<span>${confidence}</span>` : ""}
    </div>
    <div class="readiness-inline-score">
      <strong>${score}</strong><span>/100</span>
    </div>`;

  const progress = next.querySelector(".recovery-progress");
  if (progress) progress.insertAdjacentElement("afterend", inline);
  else next.appendChild(inline);
  readiness.remove();

  appendStyle(root, `
    .recovery-readiness-panel{margin-top:10px;padding:8px;border-radius:16px}
    .section-label{padding:0 3px 5px}
    .next-workout{margin-top:0;padding:10px 11px;border-radius:13px}
    .next-main{grid-template-columns:40px minmax(0,1fr) auto;gap:9px}
    .next-icon{width:38px;height:38px;border-radius:11px}
    .next-icon ha-icon{--mdc-icon-size:23px}
    .next-copy strong{font-size:22px}
    .next-copy span{margin-top:3px}
    .next-confidence{font-size:15px}
    .progress-head{margin-top:9px}
    .recovery-progress{margin-top:4px}
    .readiness-inline{
      display:flex;align-items:center;justify-content:space-between;gap:12px;
      margin-top:8px;padding:7px 9px;border-radius:10px;
      background:color-mix(in srgb,var(--readiness) 10%,var(--card-background-color));
      border-left:3px solid var(--readiness)
    }
    .readiness-inline-copy{min-width:0}
    .readiness-inline-copy small{display:block;color:var(--secondary-text-color);font-size:9px}
    .readiness-inline-copy strong{display:block;color:var(--readiness);font-size:13px;line-height:1.2;margin-top:2px}
    .readiness-inline-copy span{display:block;color:var(--secondary-text-color);font-size:9px;margin-top:2px;overflow-wrap:anywhere}
    .readiness-inline-score{display:flex;align-items:baseline;white-space:nowrap}
    .readiness-inline-score strong{font-size:20px;color:var(--readiness)}
    .readiness-inline-score span{font-size:9px;color:var(--secondary-text-color);margin-left:2px}
    .recovery-grid{gap:6px;margin-top:8px}
    .recovery-grid>div{padding:7px 8px}
    .signal-head{margin-top:8px}
    .signals{gap:4px;margin-top:4px}
    .signal{padding:4px 6px}
    .physio-note{display:none}
    .components{gap:6px;margin-top:8px}
    .component{padding:7px 8px}
    .context{margin-top:7px}
    @media(max-width:520px){
      .next-main{grid-template-columns:36px minmax(0,1fr)}
      .next-icon{width:34px;height:34px}
      .next-confidence{grid-column:2}
      .recovery-grid{grid-template-columns:1fr 1fr}
      .components{grid-template-columns:repeat(2,minmax(0,1fr))}
    }
    @media(max-width:390px){
      .recovery-grid,.components{grid-template-columns:1fr}
    }
  `, "recovery");
});

/* -------------------------------------------------------------------------
 * Sleep stages: the donut may show awake + sleep-stage composition, but the
 * center must represent actual sleep. Never include Awake in Total Sleep.
 * Prefer the canonical duration sensor, with light+deep+REM as a lower bound.
 * ---------------------------------------------------------------------- */
patchRender("fitness-sleep-stage-card", function () {
  const root = this.shadowRoot;
  if (!root || !this._hass) return;

  const entities = this._resolvedEntities || this.config?.entities || [];
  if (!entities.length) return;

  const awakeId = this._profile?.entities?.last_sleep_awake || entities[0] || null;
  const asleepStageMinutes = entities
    .filter((entityId) => entityId && entityId !== awakeId)
    .map((entityId) => minutesFromState(this._hass.states[entityId]))
    .filter((value) => value != null)
    .reduce((sum, value) => sum + value, 0);

  const canonicalDuration = this._durationEntity
    ? minutesFromState(this._hass.states[this._durationEntity])
    : null;

  const actualSleepMinutes = canonicalDuration != null && canonicalDuration > 0
    ? Math.max(canonicalDuration, asleepStageMinutes)
    : asleepStageMinutes;

  const centerValue =
    root.querySelector(".hole strong")
    || root.querySelector(".donut strong")
    || root.querySelector(".center strong");
  if (centerValue && actualSleepMinutes > 0) {
    centerValue.textContent = formatMinutes(actualSleepMinutes);
  }

  // Expose the corrected arithmetic for diagnostics/tests without changing
  // the visible stage percentages (which intentionally describe the full
  // sleep period, including awake time).
  const card = root.querySelector("ha-card");
  if (card) {
    card.dataset.actualSleepMinutes = String(Math.round(actualSleepMinutes || 0));
    card.dataset.awakeEntity = awakeId || "";
  }
});

/* -------------------------------------------------------------------------
 * Workout-vs-baseline gauges: show numeric endpoints and current position.
 * HR uses distance-from-baseline colors, not a simplistic "lower is better"
 * assumption, because context/comparable workout matters.
 * ---------------------------------------------------------------------- */
patchRender("fitness-comparison-card", function () {
  const root = this.shadowRoot;
  if (!root || !this._hass) return;
  const metrics = this._resolvedMetrics || this.config?.metrics || [];
  const rows = [...root.querySelectorAll(".row")];

  rows.forEach((row, index) => {
    const metric = metrics[index];
    if (!metric?.entity) return;
    const state = this._hass.states[metric.entity];
    const value = number(state?.state);
    if (value == null) return;

    const max = Math.abs(number(metric.max) ?? 30);
    const unit = state?.attributes?.unit_of_measurement || metric.unit || "";
    const decimals = metric.decimals ?? 1;
    const signed = (v) => `${v > 0 ? "+" : ""}${v.toFixed(decimals)}${unit ? ` ${unit}` : ""}`;

    const labels = document.createElement("div");
    labels.className = "axis-values";
    labels.innerHTML = `<span>${signed(-max)}</span><b>${signed(value)}</b><span>${signed(max)}</span>`;
    row.appendChild(labels);

    const axis = row.querySelector(".axis");
    if (axis) {
      const marker = document.createElement("i");
      marker.className = "current-marker";
      const pos = 50 + Math.max(-50, Math.min(50, value / Math.max(max, 0.001) * 50));
      marker.style.left = `${pos}%`;
      axis.appendChild(marker);
    }

    const isHr = String(metric.entity).includes("hr_vs_baseline");
    if (isHr) {
      const distance = Math.abs(value);
      const tone = distance <= 2
        ? "var(--success-color,#43a047)"
        : distance <= 5
          ? "#f9a825"
          : distance <= 8
            ? "#ef6c00"
            : "var(--error-color,#db4437)";
      row.style.setProperty("--fitness-baseline-tone", tone);
      row.classList.add("hr-baseline-row");
    }
  });

  appendStyle(root, `
    .axis-values{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;margin-top:4px;font-size:9px;color:var(--secondary-text-color)}
    .axis-values span:last-child{text-align:right}
    .axis-values b{padding:1px 5px;border-radius:999px;color:var(--primary-text-color);background:var(--secondary-background-color);font-weight:600}
    .axis{overflow:visible}
    .current-marker{position:absolute;top:-3px;width:2px;height:14px;border-radius:2px;background:var(--primary-text-color);transform:translateX(-1px)}
    .hr-baseline-row .bar{background:var(--fitness-baseline-tone)}
    .hr-baseline-row .current-marker{background:var(--fitness-baseline-tone)}
    .hr-baseline-row .axis-values b{color:var(--fitness-baseline-tone)}
  `, "comparison");
});

/* -------------------------------------------------------------------------
 * VO2max progress: numeric gauge range/current value and history endpoints.
 * ---------------------------------------------------------------------- */
patchRender("fitness-progress-card", function () {
  const root = this.shadowRoot;
  if (!root || !this._hass) return;
  const e = this._profile?.entities || {};
  const trend = this._hass.states[e.cardiorespiratory_fitness_trend];
  const predicted = this._hass.states[e.vo2max_percent_predicted];

  const pct = number(trend?.attributes?.percent_predicted) ?? number(predicted?.state);
  const progress = root.querySelector(".progress");
  if (progress && pct != null) {
    const low = 50;
    const high = Math.max(130, Math.ceil(pct / 10) * 10);
    const position = Math.max(0, Math.min(100, (pct - low) / Math.max(high - low, 1) * 100));
    const fill = progress.querySelector("div");
    if (fill) fill.style.width = `${position}%`;

    const labels = document.createElement("div");
    labels.className = "progress-values";
    labels.innerHTML = `<span>${low}%</span><b>${pct.toFixed(1)}%</b><span>${high}%</span>`;
    progress.insertAdjacentElement("afterend", labels);
  }

  const raw = Array.isArray(trend?.attributes?.daily_series)
    ? trend.attributes.daily_series
    : [];
  const series = raw
    .map((item) => number(item?.value))
    .filter((value) => value != null)
    .slice(-90);
  const history = root.querySelector(".history");
  if (history && series.length >= 2) {
    const values = document.createElement("div");
    values.className = "history-values";
    values.innerHTML = `<span>${series[0].toFixed(1)}</span><b>${series[series.length - 1].toFixed(1)} mL/kg/min</b>`;
    history.appendChild(values);
  }

  appendStyle(root, `
    .progress{overflow:visible;position:relative}
    .progress-values{display:grid;grid-template-columns:1fr auto 1fr;margin-top:5px;font-size:9px;color:var(--secondary-text-color)}
    .progress-values span:last-child{text-align:right}
    .progress-values b{color:var(--primary-text-color);font-weight:600}
    .history-values{display:flex;justify-content:space-between;gap:10px;margin-top:2px;font-size:9px;color:var(--secondary-text-color)}
    .history-values b{color:var(--primary-text-color);font-weight:600}
  `, "progress");
});

/* -------------------------------------------------------------------------
 * Training-load/adaptation gauge: numeric scale start/current/end.
 * ---------------------------------------------------------------------- */
patchRender("fitness-training-load-card", function () {
  const root = this.shadowRoot;
  if (!root) return;
  const scale = root.querySelector(".load-scale");
  if (!scale) return;

  const state =
    (this._profile?.entities?.training_load
      ? this._hass?.states?.[this._profile.entities.training_load]
      : null);
  const ratio =
    number(state?.attributes?.recent_to_baseline_load_ratio)
    ?? number(root.querySelector(".ratio strong")?.textContent?.replace("×", ""));

  const labels = document.createElement("div");
  labels.className = "load-scale-values";
  labels.innerHTML = `<span>0×</span><b>${ratio == null ? "—" : `${ratio.toFixed(2)}×`}</b><span>2.40×</span>`;
  scale.insertAdjacentElement("afterend", labels);

  appendStyle(root, `
    .load-scale-values{display:grid;grid-template-columns:1fr auto 1fr;margin-top:4px;font-size:9px;color:var(--secondary-text-color)}
    .load-scale-values span:last-child{text-align:right}
    .load-scale-values b{color:var(--primary-text-color);font-weight:600}
  `, "training-load");
});

console.info(
  `%c HA-Fitness dashboard refinements ${FITNESS_811_VERSION} `,
  "background:#41BDF5;color:#fff;font-weight:600;padding:3px 6px;border-radius:4px",
);
