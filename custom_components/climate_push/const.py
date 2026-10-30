"""Konstanten fuer die Climate-Push-Integration."""

DOMAIN = "climate_push"

# Kopplung (aus dem Dashboard kopierter Code)
CONF_PAIRING_CODE = "pairing_code"
PAIRING_PREFIX = "CLIMATE1"

# Aus dem Kopplungscode abgeleitet + persistiert
CONF_URL = "url"
CONF_TOKEN = "token"
CONF_SECRET = "secret"

# Vom Nutzer gewaehlte Sensoren
CONF_TEMPERATURE_ENTITY = "temperature_entity"
CONF_HUMIDITY_ENTITY = "humidity_entity"
CONF_SOIL_ENTITY = "soil_moisture_entity"

# Sendeintervall
CONF_INTERVAL = "interval_minutes"
DEFAULT_INTERVAL = 10
MIN_INTERVAL = 5
MAX_INTERVAL = 120

PAYLOAD_VERSION = 1
SIGNATURE_HEADER = "X-Climate-Signature"
HTTP_TIMEOUT = 15
