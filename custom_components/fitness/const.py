"""Constants for Fitness."""

DOMAIN = "fitness"

CONF_PROFILE_NAME = "profile_name"
CONF_DATE_OF_BIRTH = "date_of_birth"
CONF_SEX = "sex"
CONF_BIRTH_DAY = "birth_day"
CONF_BIRTH_MONTH = "birth_month"
CONF_BIRTH_YEAR = "birth_year"

# A value or entity ID.
CONF_WEIGHT = "weight"
CONF_RESTING_HR = "resting_hr"
CONF_HEIGHT = "height"
CONF_MAX_HR = "max_hr"
CONF_VO2MAX = "vo2max"
CONF_THRESHOLD_HR = "threshold_hr"
CONF_THRESHOLD_PACE = "threshold_pace"
CONF_THRESHOLD_POWER = "threshold_power"

CONF_LIVE_DEVICE_IDS = "live_device_ids"
CONF_WORKOUT_DEVICE_IDS = "workout_device_ids"

CONF_AI_ENABLED = "ai_enabled"
CONF_AI_ENTITY = "ai_entity"

CONF_FEEDBACK_AREA_IDS = "feedback_area_ids"
CONF_FEEDBACK_LIGHT_IDS = "feedback_light_ids"
CONF_NOTIFY_ENTITY_IDS = "notify_entity_ids"
CONF_TTS_ENTITY_ID = "tts_entity_id"
CONF_TTS_MEDIA_PLAYER_IDS = "tts_media_player_ids"
CONF_PERIODIC_LIVE_ANNOUNCEMENTS = "periodic_live_announcements"
CONF_PERIODIC_LIVE_INTERVAL_MINUTES = "periodic_live_interval_minutes"

ANTPLUS_DOMAINS = ("antplus", "ant_plus")

METRIC_HEART_RATE = "heart_rate"
METRIC_POWER = "power"
METRIC_CADENCE = "cadence"
METRIC_SPEED = "speed"
METRIC_DISTANCE = "distance"
METRIC_ALTITUDE = "altitude"

LIVE_METRICS = (
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_CADENCE,
    METRIC_SPEED,
    METRIC_DISTANCE,
    METRIC_ALTITUDE,
)

SOURCE_USER = "user"
SOURCE_ENTITY = "entity"
SOURCE_ESTIMATED = "estimated"
SOURCE_WORKOUT = "workout"
SOURCE_PROVIDER = "provider"

METHOD_TANAKA_2001 = "tanaka_2001"
METHOD_UTH_2004 = "uth_2004"
METHOD_FRIEND_2017 = "friend_2017"
METHOD_HRR = "heart_rate_reserve"
METHOD_PERSONAL_HRV_BASELINE = "personal_hrv_baseline"
METHOD_ACUTE_CHRONIC_RATIO = "acute_chronic_ratio_context"
METHOD_ACSM_HRR_INTENSITY = "acsm_hrr_intensity_2011"
METHOD_THRESHOLD_RELATIVE = "threshold_relative_intensity"

# Engineering validity gate for locally captured sessions. This is deliberately
# not presented as a physiological threshold.
MIN_LOCAL_WORKOUT_SECONDS = 180
MIN_LOCAL_WORKOUT_SAMPLES = 20

STORE_VERSION = 1
STORE_KEY_PREFIX = "fitness_history"
MAX_STORED_WORKOUTS = 200
