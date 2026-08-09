"""Research registry for every implemented deterministic scientific method."""

REFERENCES = {
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
