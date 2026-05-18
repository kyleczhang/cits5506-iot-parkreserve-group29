# =============================================================================
# config/settings.py  —  ParkReserve Raspberry Pi Gateway Configuration
# =============================================================================

# ── Test Mode Switch ──────────────────────────────────────────────────────────
# True  → Mock LPR (no real image needed, returns MOCK_PLATE directly) + short timeouts
# False → Real EasyOCR recognition + production timeouts
TEST_MODE = False

# Mock LPR configuration (active when TEST_MODE=True)
# Scenario 1: test auto_check_in  → MOCK_PLATE matches a plate in bound_plates
# Scenario 2: test conflict_strong → MOCK_PLATE does not match any plate in bound_plates
# Scenario 3: test pending (low confidence) → set MOCK_CONFIDENCE to 0.50
MOCK_PLATE      = "CZH5506"
MOCK_CONFIDENCE = 0.95

# ── Local MQTT (Mosquitto, running locally) ───────────────────────────────────
LOCAL_MQTT_HOST      = "localhost"
LOCAL_MQTT_PORT      = 1883
LOCAL_MQTT_CLIENT_ID = "pi-gateway-local"

LOCAL_TOPIC_STATUS = "bay/+/status"
LOCAL_TOPIC_LED    = "bay/{code}/led"

# ── Cloud MQTT (HiveMQ Cloud) ─────────────────────────────────────────────────
CLOUD_MQTT_HOST      = "b57eba64e4174cb38be14e7225b632fa.s1.eu.hivemq.cloud"
CLOUD_MQTT_PORT      = 8883
CLOUD_MQTT_USERNAME  = "yuancong"
CLOUD_MQTT_PASSWORD  = "Yuancong29!"
CLOUD_MQTT_CLIENT_ID = "pi-gateway-cloud"

CLOUD_TOPIC_STATE       = "cloud/bay/{code}/state"
CLOUD_TOPIC_EVENT       = "cloud/bay/{code}/event"
CLOUD_TOPIC_HEARTBEAT   = "cloud/system/heartbeat"
CLOUD_TOPIC_RESERVATION = "cloud/bay/+/reservation"
CLOUD_TOPIC_RESYNC      = "cloud/system/resync"

# ── Local HTTP Image Receiver Service ─────────────────────────────────────────
IMAGE_RECEIVER_HOST = "0.0.0.0"
IMAGE_RECEIVER_PORT = 8080
IMAGE_UPLOAD_DIR    = "./tmp/parkReserve/images"

# ── LPR Confidence Threshold ──────────────────────────────────────────────────
ALPR_MIN_CONFIDENCE = 0.80

# ── State Machine Timing ──────────────────────────────────────────────────────
# TEST_MODE=True  → 30s (convenient for testing)
# TEST_MODE=False → 300s (production value)
PI_NO_SHOW_TIMEOUT_SECONDS        = 3000
PI_CHECKIN_WAIT_TIMEOUT_SECONDS = 3000

# ── Heartbeat Interval ────────────────────────────────────────────────────────
HEARTBEAT_INTERVAL_SECONDS = 10

# ── Pi Identifier ─────────────────────────────────────────────────────────────
PI_ID = "pi-01"

# ── Bay Code List ─────────────────────────────────────────────────────────────
BAY_CODES = ["A1", "A2", "A3"]
