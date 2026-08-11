"""Research registry for every implemented deterministic scientific method."""

REFERENCES = {
    "banister_trimp_validation_2014": {
        "title": "Training load quantification in elite swimmers using a modified version of the training impulse method",
        "year": 2014,
        "pmid": "24942164",
        "limitation": "Banister TRIMP is an internal-load estimate based on heart rate and duration; it should be interpreted longitudinally and is not a diagnosis.",
    },
    "cardiovascular_drift_2001": {
        "title": "Cardiovascular drift during prolonged exercise: new perspectives",
        "year": 2001,
        "pmid": "11337829",
        "limitation": "Cardiovascular drift depends on exercise duration, heat, hydration and workload; Fitness reports decoupling descriptively rather than as a universal cutoff.",
    },
    "cardiorespiratory_fitness_meta_2024": {
        "title": "Cardiorespiratory fitness and mortality: systematic review and meta-analysis",
        "year": 2024,
        "pmid": "39271056",
        "limitation": "Fitness reports measured/provider VO₂max trends descriptively and does not infer mortality risk for an individual.",
    },
    "exercise_sleep_meta_2024": {
        "title": "Exercise and sleep outcomes: systematic review and meta-analysis",
        "year": 2024,
        "pmid": "39556996",
        "limitation": "Population evidence does not establish causation in a user's short-term personal correlations; Fitness labels these as descriptive associations only.",
    },
    "hrr_training_status_review_2012": {
        "title": "Heart rate recovery after exercise: a systematic review of training-status applications",
        "year": 2012,
        "pmid": "22357753",
        "limitation": "HRR depends on exercise intensity, duration, environmental conditions and individual context; Fitness emphasizes longitudinal comparison.",
    },
    "heart_rate_recovery_1999": {
        "title": "Heart-rate recovery immediately after exercise as a predictor of mortality",
        "year": 1999,
        "doi": "10.1056/NEJM199910283411804",
        "pmid": "10536127",
        "limitation": "Interpret longitudinally and in context; Fitness does not use HRR as a diagnosis or mortality-risk prediction.",
    },
    "adult_sleep_duration_consensus_2015": {
        "title": "Recommended Amount of Sleep for a Healthy Adult: A Joint Consensus Statement of the AASM and SRS",
        "year": 2015,
        "doi": "10.5664/jcsm.4758",
        "pmid": "25979105",
        "limitation": "Population guidance; individual sleep need varies and longer sleep can be appropriate in several circumstances.",
    },
    "hrv_guided_training_review_2021": {
        "title": "Monitoring and adapting endurance training on the basis of heart rate variability monitored by wearable technologies: A systematic review with meta-analysis",
        "year": 2021,
        "doi": "10.1016/j.jsams.2021.04.012",
        "pmid": "34489178",
        "limitation": "HRV is most useful longitudinally with standardized measurements; Fitness does not convert a single HRV value into a proprietary readiness score.",
    },
    "hrv_training_status_meta_2016": {
        "title": "Monitoring Athletic Training Status Through Autonomic Heart Rate Regulation: A Systematic Review and Meta-Analysis",
        "year": 2016,
        "pmid": "26888648",
        "limitation": "Measurement conditions and within-person longitudinal interpretation matter; no single-night proprietary readiness score is inferred.",
    },
    "sleep_regularity_metrics_2021": {
        "title": "Sleep regularity: theoretical properties and practical usage of existing metrics",
        "year": 2021,
        "pmid": "33864369",
        "limitation": "Fitness reports timing variability descriptively; it does not label a specific variability value as diagnostic or universally healthy/unhealthy.",
    },
    "hr_monitoring_training_status_2014": {
        "title": "Monitoring training status with HR measures: do all roads lead to Rome?",
        "year": 2014,
        "pmid": "24578692",
        "limitation": "Resting/recovery HR trends are contextual monitoring tools and should not be interpreted as a diagnosis or standalone readiness score.",
    },
    "acsm_hrr_intensity_2011": {
        "title": "Quantity and Quality of Exercise for Developing and Maintaining Cardiorespiratory, Musculoskeletal, and Neuromotor Fitness in Apparently Healthy Adults",
        "organization": "American College of Sports Medicine",
        "year": 2011,
        "doi": "10.1249/MSS.0b013e318213fefb",
        "pmid": "21694556",
        "ranges_hrr_percent": {
            "very_light": "<30",
            "light": "30-39",
            "moderate": "40-59",
            "vigorous": "60-89",
            "near_maximal": ">=90"
        },
        "limitation": "Population percentage ranges can misclassify individual physiological intensity domains; measured ventilatory/metabolic thresholds are preferable when available."
    },
    "tanaka_2001": {
        "title": "Age-predicted maximal heart rate revisited",
        "year": 2001,
        "doi": "10.1016/S0735-1097(00)01054-8",
        "pmid": "11153730",
    },
    "uth_2004": {
        "title": "Estimation of VO2max from the ratio between HRmax and HRrest",
        "year": 2004,
        "doi": "10.1007/s00421-003-0988-y",
        "pmid": "14624296",
        "limitation": "Originally validated in well-trained men.",
    },
    "friend_2017": {
        "title": "A Reference Equation for Normal Standards for VO2 Max",
        "year": 2017,
        "pmid": "28377168",
    },
    "training_load_consensus_2017": {
        "title": "Monitoring Athlete Training Loads: Consensus Statement",
        "year": 2017,
        "pmid": "28463642",
    },
    "recovery_consensus_2018": {
        "title": "Recovery and Performance in Sport: Consensus Statement",
        "year": 2018,
        "pmid": "29345524",
    },
}
