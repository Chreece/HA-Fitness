"""Constants for Fitness."""

DOMAIN = "fitness"

CONF_PROFILE_NAME = "profile_name"
CONF_DATE_OF_BIRTH = "date_of_birth"
CONF_SEX = "sex"
CONF_LANGUAGE = "language"

SUPPORTED_LANGUAGES = {
    "en": "English",
    "el": "Ελληνικά",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "nl": "Nederlands",
    "pl": "Polski",
    "ru": "Русский",
    "uk": "Українська",
    "tr": "Türkçe",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
}

CONF_BIRTH_DAY = "birth_day"
CONF_BIRTH_MONTH = "birth_month"
CONF_BIRTH_YEAR = "birth_year"

# Current confirmed/manual body weight in kg. Shared scale input is configured separately.
CONF_WEIGHT = "weight"
CONF_WEIGHT_SCALE_ENTITY = "weight_scale_entity"
CONF_RESTING_HR = "resting_hr"
CONF_HEIGHT = "height"
CONF_MAX_HR = "max_hr"
CONF_VO2MAX = "vo2max"
CONF_THRESHOLD_HR = "threshold_hr"
CONF_THRESHOLD_PACE = "threshold_pace"
CONF_THRESHOLD_POWER = "threshold_power"

CONF_LIVE_DEVICE_IDS = "live_device_ids"
CONF_LIVE_SENSOR_IDS = "live_sensor_ids"
CONF_BLUETOOTH_ENABLED = "bluetooth_fitness_enabled"
CONF_ANTPLUS_ENABLED = "antplus_enabled"
LIVE_ADAPTER_STORE_VERSION = 1
LIVE_ADAPTER_STORE_KEY = "fitness.live_adapters"
CYCPLUS_SYNC_STORE_VERSION = 1
CYCPLUS_SYNC_STORE_KEY = "fitness.cycplus_m1_sync"
GARMIN_LOCAL_SYNC_STORE_VERSION = 1
GARMIN_LOCAL_SYNC_STORE_KEY = "fitness.garmin_local_sync"
CONF_WORKOUT_DEVICE_IDS = "workout_device_ids"
CONF_DETAILED_STRENGTH_ANALYSIS = "detailed_strength_analysis"
CONF_WORKOUT_RETENTION_DAYS = "workout_retention_days"
CONF_SLEEP_DEVICE_IDS = "sleep_device_ids"

CONF_AI_ENABLED = "ai_enabled"
CONF_AI_ENTITY = "ai_entity"
AI_ENTITY_SYSTEM_DEFAULT = "__home_assistant_default__"

CONF_FEEDBACK_AREA_IDS = "feedback_area_ids"
CONF_FEEDBACK_LIGHT_IDS = "feedback_light_ids"
CONF_NOTIFY_ENTITY_IDS = "notify_entity_ids"
CONF_TTS_ENTITY_ID = "tts_entity_id"
CONF_TTS_MEDIA_PLAYER_IDS = "tts_media_player_ids"
CONF_PERIODIC_LIVE_ANNOUNCEMENTS = "periodic_live_announcements"
CONF_PERIODIC_LIVE_INTERVAL_MINUTES = "periodic_live_interval_minutes"

# Optional full-screen Fitness TV dashboard. Audio is rendered inside the
# dashboard browser so music and TTS can coexist without replacing HA Cast.
CONF_TV_DASHBOARD_ENABLED = "tv_dashboard_enabled"
CONF_TV_MEDIA_PLAYER_ID = "tv_dashboard_media_player_id"
CONF_TV_DUCKING_PERCENT = "tv_dashboard_ducking_percent"
CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE = "tv_dashboard_ignore_lights_when_cast_active"
CONF_TV_YTDLP_ENABLED = "tv_dashboard_ytdlp_enabled"

# Optional profile dashboard composition. These settings only change presentation;
# they never start network polling or background jobs. External dashboard modules
# render existing Home Assistant entities selected by the user.
CONF_DASHBOARD_THEME = "dashboard_theme"
CONF_DASHBOARD_MODULES = "dashboard_modules"
CONF_DASHBOARD_RSS_ENTITY_IDS = "dashboard_rss_entity_ids"
CONF_DASHBOARD_MUSIC_ENTITY_IDS = "dashboard_music_entity_ids"
CONF_DASHBOARD_LIGHT_ENTITY_IDS = "dashboard_light_entity_ids"
CONF_DASHBOARD_VIDEO_ENTITY_IDS = "dashboard_video_entity_ids"
CONF_DASHBOARD_WEATHER_ENTITY_ID = "dashboard_weather_entity_id"
DEFAULT_DASHBOARD_MODULES = ["core"]
DASHBOARD_MODULES = (
    "core",
    "training_ai",
    "body_composition",
    "workout_browser",
    "rss",
    "music",
    "tts",
    "lights",
    "video",
    "weather",
)
DEFAULT_TV_DUCKING_PERCENT = 25
DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE = True
SERVICE_CAST_TV_DASHBOARD = "cast_tv_dashboard"
SERVICE_STOP_TV_DASHBOARD = "stop_tv_dashboard"
SERVICE_START_TV_WORKOUT = "start_tv_workout"
SERVICE_TEST_TTS = "test_tts"
SERVICE_AI_TTS = "ai_tts"
TV_DASHBOARD_PATH = "fitness-tv"


METRIC_HEART_RATE = "heart_rate"
METRIC_POWER = "power"
METRIC_CADENCE = "cadence"
METRIC_SPEED = "speed"
METRIC_DISTANCE = "distance"
METRIC_ALTITUDE = "altitude"

# Non-live physical-device capabilities share the same discovery and profile
# assignment model without pretending that they publish real-time telemetry.
CAPABILITY_WORKOUT_HISTORY = "workout_history"

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
DEFAULT_WORKOUT_RETENTION_DAYS = 3650
MAX_WORKOUT_RETENTION_DAYS = 36500
SERVICE_DELETE_WORKOUTS_BEFORE = "delete_workouts_before"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_DAYS = "days"
