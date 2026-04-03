"""Constants for the Zephyr Hood integration."""

DOMAIN = "zephyr_hood"
MANUFACTURER = "Zephyr"

# Config entry keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# API - to be populated after traffic analysis
API_BASE_URL = "https://api.zephyronline.com"  # placeholder
API_LOGIN_ENDPOINT = "/api/v1/login"           # placeholder
API_DEVICES_ENDPOINT = "/api/v1/devices"       # placeholder
API_STATUS_ENDPOINT = "/api/v1/device/status"  # placeholder
API_CONTROL_ENDPOINT = "/api/v1/device/control" # placeholder

# Update interval
SCAN_INTERVAL_SECONDS = 30

# Fan speeds (Zephyr has 6 speeds)
FAN_SPEED_OFF = 0
FAN_SPEED_MIN = 1
FAN_SPEED_MAX = 6
FAN_SPEEDS = [1, 2, 3, 4, 5, 6]

# Light levels (Zephyr has 3 levels)
LIGHT_LEVEL_OFF = 0
LIGHT_LEVEL_LOW = 1
LIGHT_LEVEL_MED = 2
LIGHT_LEVEL_HIGH = 3
LIGHT_LEVELS = [1, 2, 3]

# Platforms
PLATFORMS = ["fan", "light", "sensor"]
