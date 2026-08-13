# Science & methods

Fitness deliberately separates **measurements**, **established calculations**, **personal statistical context**, and **Fitness-owned interpretations**.

It is a training/wellness integration, not a medical device. A scientific reference for one metric does not make the complete Fitness evaluation a clinically validated score.

## Session RPE and session-RPE load

Fitness uses whole-session RPE on a 1–10 scale and derives session-RPE load from perceived effort and session duration. Foster et al. described the session-RPE approach for quantifying training across exercise types, and a later review found good validity/reliability across multiple sports and populations.

- Foster C, et al. *A new approach to monitoring exercise training.* J Strength Cond Res. 2001;15(1):109–115. PMID 11708692: https://pubmed.ncbi.nlm.nih.gov/11708692/
- Haddad M, et al. *Session-RPE Method for Training Load Monitoring: Validity, Ecological Usefulness, and Influencing Factors.* Front Neurosci. 2017. PMID 29163016: https://pubmed.ncbi.nlm.nih.gov/29163016/

Fitness treats RPE as subjective evidence, not as a value that should be reverse-engineered from heart rate or a vendor's unrelated training-effect score.

## Heart-rate recovery

Post-exercise HR recovery reflects autonomic recovery and is protocol-sensitive. Fitness can retain several recovery checkpoints and compare them with the user's own validated history rather than applying a universal consumer-facing verdict.

- Cole CR, et al. *Heart-rate recovery immediately after exercise as a predictor of mortality.* N Engl J Med. 1999. PMID 10536127: https://pubmed.ncbi.nlm.nih.gov/10536127/
- Savonen KP, et al. *Two-minute heart rate recovery after cycle ergometer exercise and all-cause mortality in middle-aged men.* J Intern Med. 2011. PMID 21801244: https://pubmed.ncbi.nlm.nih.gov/21801244/
- Watanabe J, et al. *Heart rate recovery: validation and methodologic issues.* J Am Coll Cardiol. 2001. PMID 11738304: https://pubmed.ncbi.nlm.nih.gov/11738304/

These clinical/prognostic studies support HRR as a meaningful physiological signal; Fitness does **not** use them to diagnose disease.

## HRV and personal recovery context

HRV is useful as a longitudinal autonomic signal, but methodology and baseline handling matter. Reviews of HRV-guided endurance training suggest potential benefits while also showing that performance effects are not universally large. Fitness therefore emphasizes personal baselines and evidence availability.

- Manresa-Rocamora A, et al. *Heart Rate Variability-Guided Training for Enhancing Cardiac-Vagal Modulation, Aerobic Fitness, and Endurance Performance: A Methodological Systematic Review with Meta-Analysis.* PMID 34639599: https://pubmed.ncbi.nlm.nih.gov/34639599/
- Düking P, et al. *Monitoring and adapting endurance training on the basis of heart rate variability monitored by wearable technologies: A systematic review with meta-analysis.* PMID 34489178: https://pubmed.ncbi.nlm.nih.gov/34489178/

## Sleep and recovery

Sleep is relevant to recovery and performance, but wearable sleep-stage estimates and individual responses are imperfect. Fitness merges available sleep evidence conservatively and keeps source provenance instead of pretending every sleep field is equally reliable.

- Bonnar D, et al. *Sleep Interventions Designed to Improve Athletic Performance and Recovery: A Systematic Review of Current Approaches.* Sports Med. 2018. PMID 29352373: https://pubmed.ncbi.nlm.nih.gov/29352373/
- Cunha LA, et al. *The Impact of Sleep Interventions on Athletic Performance: A Systematic Review.* Sports Med Open. 2023. PMID 37462808: https://pubmed.ncbi.nlm.nih.gov/37462808/
- Kong Y, et al. *Effects of sleep deprivation on sports performance and perceived exertion in athletes and non-athletes: a systematic review and meta-analysis.* Front Physiol. 2025. PMID 40236824: https://pubmed.ncbi.nlm.nih.gov/40236824/

## Training Readiness

Fitness Training Readiness is **not copied from Garmin, Oura, WHOOP or another vendor**. It is a transparent Fitness-owned composite of available personal recovery domains. The current model uses autonomic recovery, sleep, training recovery and post-exercise recovery response; missing domains are omitted and weights are renormalized. It requires multiple independent domains before returning a score.

The component choices are informed by the literature above, but the combined 0–100 score itself is a Fitness heuristic and is not presented as a clinically validated instrument.

## Strength progression and estimated 1RM

When detailed strength analysis is enabled, Fitness can calculate volume and estimate 1RM from suitable working sets. An estimated 1RM is explicitly marked as an estimate and retains its formula/input context; it is not treated as a measured maximal lift. Exercise matching is conservative so materially different exercises are not silently combined.

## Aerobic / high-intensity load decomposition

Fitness may expose a Fitness-owned intensity decomposition from available validated intensity evidence. It is intentionally distinct from proprietary vendor training-effect algorithms and must not be interpreted as a direct measurement of aerobic/anaerobic energy-system contribution.

## Design rules

1. Never fabricate a missing measurement.
2. Preserve provider/source provenance where it matters.
3. Prefer personal baselines for longitudinal interpretation.
4. Validate historical records before they influence a result.
5. Keep formulas and evidence inspectable.
6. Keep AI downstream of deterministic data — AI may explain; it does not become the measurement engine.
7. Leave a result unavailable when the evidence is insufficient.

## Personal HRV baseline

Fitness treats HRV as a **within-person trend**, not a universal score. Night-to-night HRV is noisy, so the recovery signal uses a rolling recent average rather than reacting to one isolated night. Research in athlete monitoring has found weekly averaging/rolling averages useful for interpreting HRV trends and training adaptation.

Fitness therefore uses:

- a recent **7-night mean HRV** when at least 5 valid nights are available;
- a **preceding 28-day personal baseline**, excluding the newest night from its own reference distribution;
- at least **14 prior HRV nights** before the Fitness-owned 28-day baseline is considered available;
- both the recent-average deviation and the latest-night deviation are exposed for inspection.

This is a transparent monitoring heuristic, not a medical threshold. Provider-supplied HRV baseline ranges are retained separately when an adapter exposes them. Relevant methodological literature includes Plews et al. (2013, PMID 23852425), Plews et al. (2014, PMID 24334285), and Plews et al. (2012, PMID 22367011).

## Seven-day sleep deficit

For adults, Fitness uses the AASM/SRS consensus minimum of 7 hours as a **reference floor**, not as a personalized diagnosis of sleep need. The 7-day deficit is the sum of `max(0, 7 h − nightly sleep)` over observed main sleeps in the rolling window. To avoid double-counting the same physical night when multiple providers synchronize at different times, only one main validated sleep is counted per local wake date. The per-night calculation is exposed in the entity attributes for auditing.

## Training adaptation status

Fitness classifies recent training adaptation from multiple Fitness-owned longitudinal signals rather than copying a provider status. The classification combines recent training exposure relative to the person's own baseline, VO2max trend, 7-day HRV relative to the preceding personal baseline, resting-HR deviation, and Fitness training readiness. It is deliberately a monitoring classification, not a diagnosis of overtraining syndrome.

Scientific rationale: the 2017 consensus on monitoring athlete training loads recommends a multidisciplinary approach rather than relying on one load metric (Bourdon et al., PMID 28463642). A systematic review/meta-analysis of autonomic heart-rate regulation found that HRV and HRR can change with both positive adaptation and overreaching, so additional measures of training tolerance are required (Bellenger et al., 2016, PMID 26888648). The ECSS/ACSM consensus further distinguishes functional overload from prolonged maladaptation and emphasizes the balance between overload and recovery (Meeusen et al., PMID 23247672).

The labels Productive, Maintaining, Insufficient stimulus, High load, Excessive load, Strained, Unproductive, No recent training and Insufficient data are therefore explainable Fitness classifications. They are not medical diagnoses and do not claim that a single workload ratio predicts injury or overtraining.

## Estimated recovery time

Fitness exposes an **estimated recovery time** after the latest completed workout. It is an evidence-informed planning heuristic, not a direct measurement of complete physiological recovery and not a medical recommendation. Recovery is multidimensional and varies substantially within and between people. The model combines workout dose (duration, session RPE/session-RPE load, TRIMP and high-intensity time when available) with personal recovery evidence (Training Readiness, rolling HRV versus the user's own baseline, resting-HR deviation and HRR versus personal baseline). It uses the largest workout-dose estimate, applies only a bounded recovery modifier, subtracts elapsed time, and reports confidence/evidence rather than pretending a precise biological finish time.

The model is intentionally conservative for resistance exercise because studies of demanding resistance sessions show that neuromuscular performance can require roughly 24–48 h to recover, with slower recovery after training to failure. More generally, sport-science consensus emphasizes that recovery is multifactorial and should be monitored with multiple internal/external signals rather than one universal clock.

Scientific basis: Kellmann et al., *Recovery and Performance in Sport: Consensus Statement* (2018, PMID 29345524); González-Badillo et al. (2016, PMID 26667923); Pareja-Blanco et al. (2017, PMID 28965198); Michael et al. review of post-exercise autonomic recovery (2017, PMID 28611675).
