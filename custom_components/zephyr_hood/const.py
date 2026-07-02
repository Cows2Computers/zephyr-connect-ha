"""Constants for the Zephyr Hood integration."""

DOMAIN = "zephyr_hood"
MANUFACTURER = "Zephyr"

# Config entry keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# --- Zephyr Connect cloud (AWS Amplify backend) ---------------------------------
# These identifiers are *baked into the public Zephyr Connect Android app*
# (com.zephyr.rangehood) and are identical for every user — they only identify
# the shared Zephyr/Gemtek backend, not any individual account. Authentication
# uses YOUR Zephyr Connect email + password, entered during setup and never
# stored in this repo. (Discovered by decompiling the public app's
# res/raw/awsconfiguration.json + RangeHoodAPPClient.)
AWS_REGION = "us-west-2"
COGNITO_USER_POOL_ID = "us-west-2_McuoKpkna"
COGNITO_APP_CLIENT_ID = "5a2qiskdvvu7gre1jvbjnunu20"
COGNITO_APP_CLIENT_SECRET = "3b085l2fkgph4kt734k5e26tirb9hjasgb4rn8sjpp4mheo5kga"  # noqa: S105 (public app client secret, required for Cognito SECRET_HASH)
COGNITO_IDENTITY_POOL_ID = "us-west-2:fb4c1b66-12c2-414b-83a1-a1902f7d98e3"
IOT_ENDPOINT = "a1nqxu0hki9zw3-ats.iot.us-west-2.amazonaws.com"
APP_API_BASE_URL = "https://zephyr-prod-app.gemteks.com/prod"

# --- Device shadow control field names ------------------------------------------
# The app sends commands by writing the shadow's `reported` block directly:
#   { "state": { "reported": { "<field>": <value> } } }
# Field names taken from the app's domain/executors/command/Set*.java classes.
CTRL_POWER = "power"
CTRL_FAN = "fan"
CTRL_LIGHT = "light"
CTRL_TRUHUE = "truhuelevel"
CTRL_DELAY_TIMER = "setdelaytimer"
CTRL_RECIRCULATING = "setrecirculating"
CTRL_CLEANAIR = "setcleanairfunction"
CTRL_RESET_GREASE = "resetgreasefilter"
CTRL_RESET_CHARCOAL = "resetcharcoalfilter"

# Capability fallbacks. The real per-device maxes come from the /discoverdevice
# API (maxFanSpeed/maxLightLevel/maxGreasefilterTimer/maxCharcoalfilterTimer) and
# are merged onto each device dict at setup; these apply only if that call fails.
DEFAULT_MAX_FAN = 6
DEFAULT_MAX_LIGHT = 3
DEFAULT_MAX_DELAY = 10  # minutes
DEFAULT_MAX_GREASE_HOURS = 60
DEFAULT_MAX_CHARCOAL_HOURS = 200

# Device-detail keys (from /discoverdevice) merged onto the device dict.
KEY_MAX_FAN = "maxFanSpeed"
KEY_MAX_LIGHT = "maxLightLevel"
KEY_MAX_GREASE = "maxGreasefilterTimer"
KEY_MAX_CHARCOAL = "maxCharcoalfilterTimer"

# The app flags a filter as "needs cleaning" once usage reaches this fraction of
# its max life (Hood.isGreaseFilterNeedReplace / isCharcoalFilterNeedReplace).
FILTER_REPLACE_FRACTION = 0.85

PLATFORMS = ["fan", "light", "switch", "number", "sensor", "binary_sensor", "button"]
