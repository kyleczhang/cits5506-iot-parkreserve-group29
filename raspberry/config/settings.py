# =============================================================================
# config/settings.py  —  ParkReserve Raspberry Pi Gateway 配置
# =============================================================================

# ── 测试模式开关 ───────────────────────────────────────────────────────────────
# True  → Mock LPR（不需要真实图片，直接返回 MOCK_PLATE）+ 短超时时间
# False → 真实 EasyOCR 识别 + 生产超时时间
TEST_MODE = True

# Mock LPR 配置（TEST_MODE=True 时生效）
# 场景1：测试 auto_check_in  → MOCK_PLATE 和 bound_plates 里的车牌一致
# 场景2：测试 conflict_strong → MOCK_PLATE 和 bound_plates 里的车牌不一致
# 场景3：测试 pending（低置信度）→ MOCK_CONFIDENCE 改为 0.50
MOCK_PLATE      = "CZH5506"
MOCK_CONFIDENCE = 0.95

# ── 本地 MQTT（Mosquitto，运行在本机）─────────────────────────────────────────
LOCAL_MQTT_HOST      = "localhost"
LOCAL_MQTT_PORT      = 1883
LOCAL_MQTT_CLIENT_ID = "pi-gateway-local"

LOCAL_TOPIC_STATUS = "bay/+/status"
LOCAL_TOPIC_LED    = "bay/{code}/led"

# ── 云端 MQTT（HiveMQ Cloud）─────────────────────────────────────────────────
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

# ── 本地 HTTP 图像接收服务 ─────────────────────────────────────────────────────
IMAGE_RECEIVER_HOST = "0.0.0.0"
IMAGE_RECEIVER_PORT = 8080
IMAGE_UPLOAD_DIR    = "./tmp/parkReserve/images"

# ── LPR 置信度阈值 ─────────────────────────────────────────────────────────────
ALPR_MIN_CONFIDENCE = 0.80

# ── 状态机时序 ─────────────────────────────────────────────────────────────────
# TEST_MODE=True  → 30秒（方便测试）
# TEST_MODE=False → 300秒（生产值）
PI_NO_SHOW_TIMEOUT_SECONDS        = 3000   
PI_CHECKIN_WAIT_TIMEOUT_SECONDS = 3000   

# ── 心跳间隔 ──────────────────────────────────────────────────────────────────
HEARTBEAT_INTERVAL_SECONDS = 10

# ── Pi 标识 ───────────────────────────────────────────────────────────────────
PI_ID = "pi-01"

# ── 车位 Code 列表 ─────────────────────────────────────────────────────────────
BAY_CODES = ["A1", "A2", "A3"]