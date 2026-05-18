#include <WiFi.h>
#include <PubSubClient.h>
#include "esp_camera.h"
#include <HTTPClient.h>
#include "FS.h"
#include "SD.h"
#include "SPI.h"
#include "time.h" 

// =========================================================
// [1] Configuration Area - Centralized parameters
// =========================================================
// Network & Gateway Configuration
const char* ssid = "Kong";
const char* password = "55555555"; // Reminder: Replace with actual password
const char* gateway_ip = "10.52.64.37";  // Gateway IP (e.g., your PC or Raspberry Pi)
const int   gateway_port = 5000;
const char* api_path = "/api/v1/bays/A1/image"; // RESTful API path

// 🛡️ Security Key (Must match the server.py configuration)
const char* api_secret_key = "ParkReserve-Group29-SuperSecret";

// MQTT Configuration
const char* mqtt_server = "10.52.64.37"; 
const int   mqtt_port = 1883;
const char* mqtt_topic_led    = "bay/A1/led";     
const char* mqtt_topic_status = "bay/A1/status";  

// NTP Time Configuration (AWST: UTC+8 for Perth, Western Australia)
const char* ntpServer = "pool.ntp.org";
const long  gmtOffset_sec = 8 * 3600; 
const int   daylightOffset_sec = 0;

// Hardware Pin Definitions
const int PIN_RED = D0;
const int PIN_YELLOW = D1;
const int PIN_GREEN = D2;
const int PIN_BUZZER = D3;
const int PIN_TRIG = D4;
const int PIN_ECHO = D5;
const int SD_CS_PIN = 21;

// Camera Pin Definitions (Fixed for XIAO ESP32S3 Sense)
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39
#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

WiFiClient espClient;
PubSubClient client(espClient);

// =========================================================
// [2] State Management & Global Variables
// =========================================================
String currentLedState = "available";  
unsigned long previousBlinkMillis = 0;   
bool blinkState = false;            

// --- Advanced Sensor Variables (Hysteresis Logic) ---
const float DIST_OCCUPIED = 100.0;  // Threshold for parking IN (< 1.0 meter)
const float DIST_AVAILABLE = 150.0; // Threshold for driving OUT (> 1.5 meters)

String currentBayStatus = "available"; 
String lastBayStatus = "available";    

int occupiedCount = 0;  
int availableCount = 0; 
// Filter Limit: Read every 200ms. 10 times = 2 seconds of continuous confirmation.
const int FILTER_LIMIT = 10; 

unsigned long lastSensorReadMillis = 0; 
const long SENSOR_INTERVAL = 200; 

unsigned long lastPublishMillis = 0;
const long PUBLISH_INTERVAL = 2000; 

unsigned long lastRetryMillis = 0;
const long RETRY_INTERVAL = 10000; // Check for failed uploads every 10 seconds

// =========================================================
// [新增] 异步拍照定时器变量
// =========================================================
bool isWaitingToCapture = false;          // 是否正在等待拍照
unsigned long captureWaitStartMillis = 0; // 开始等待的时间戳
const unsigned long CAPTURE_DELAY = 3000; // 停稳后等待 3 秒再拍

// =========================================================
// [3] Time & Network Module
// =========================================================
void setup_wifi() {
  delay(10);
  Serial.print("\nConnecting to WiFi: ");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected! IP: " + WiFi.localIP().toString());
  
  // Sync NTP time immediately after WiFi connection
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  Serial.println("NTP Time synchronized.");
}

// Get formatted timestamp: YYYYMMDD_HHMMSS
String getTimestamp() {
  struct tm timeinfo;
  if(!getLocalTime(&timeinfo)){
    return String(millis()); // Fallback to system millis if NTP fails
  }
  char timeStringBuff[50];
  strftime(timeStringBuff, sizeof(timeStringBuff), "%Y%m%d_%H%M%S", &timeinfo);
  return String(timeStringBuff);
}

// Dynamically construct RESTful URL
String getUploadUrl() {
  return "http://" + String(gateway_ip) + ":" + String(gateway_port) + String(api_path);
}

// =========================================================
// [4] Storage & Retry Module (Blackbox Mechanism)
// =========================================================

void cleanupSD() {
  Serial.println("🧹 Starting SD Card cleanup...");
  File root = SD.open("/");
  if (!root) return;

  File file = root.openNextFile();
  while (file) {
    String fileName = file.name();
    if (!file.isDirectory() && (fileName.endsWith(".jpg") || fileName.endsWith(".jpeg"))) {
      String path = "/" + fileName;
      if (SD.remove(path)) {
        Serial.println("   Deleted old image: " + path);
      }
    }
    file = root.openNextFile();
  }
  Serial.println("✅ Cleanup finished. config.txt preserved.");
}

time_t getFileTime(String filename) {
  if (filename.length() < 20) return 0;
  
  struct tm t;
  String ts = filename.substring(5, 20); 
  
  t.tm_year = ts.substring(0, 4).toInt() - 1900;
  t.tm_mon  = ts.substring(4, 6).toInt() - 1;
  t.tm_mday = ts.substring(6, 8).toInt();
  t.tm_hour = ts.substring(9, 11).toInt();
  t.tm_min  = ts.substring(11, 13).toInt();
  t.tm_sec  = ts.substring(13, 15).toInt();
  t.tm_isdst = -1;

  return mktime(&t);
}

bool uploadImageFromSD(String filepath) {
  if (WiFi.status() != WL_CONNECTED) return false;

  File file = SD.open(filepath.c_str(), FILE_READ);
  if (!file) {
    Serial.println("❌ Failed to open file for upload: " + filepath);
    return false;
  }

  HTTPClient http;
  http.begin(getUploadUrl());
  http.addHeader("Content-Type", "image/jpeg");
  
  http.addHeader("X-API-Key", api_secret_key);
  String timestamp = filepath.substring(5, 20); 
  http.addHeader("X-Timestamp", timestamp);

  Serial.println("📤 Uploading: " + filepath + " to " + getUploadUrl());
  
  int httpResponseCode = http.sendRequest("POST", &file, file.size());
  file.close();

  bool success = false;
  if (httpResponseCode > 0) {
    if (httpResponseCode == 200 || httpResponseCode == 202) {
      Serial.printf("✅ Upload success! HTTP Response: %d\n", httpResponseCode);
      success = true;
    } else {
      Serial.printf("⚠️ Server rejected the request! HTTP Code: %d\n", httpResponseCode);
      String responseBody = http.getString();
      Serial.println("🔍 Server error details: " + responseBody);
    }
  } else {
    Serial.printf("❌ TCP Connection failed! Internal Error Code: %d\n", httpResponseCode);
    Serial.printf("🔍 Detailed Reason: %s\n", http.errorToString(httpResponseCode).c_str());
  }
  http.end();
  
  return success;
}

void processPendingUploads() {
  if (WiFi.status() != WL_CONNECTED) return;

  time_t now;
  time(&now);

  File root = SD.open("/");
  File file = root.openNextFile();
  
  while (file) {
    String filename = file.name();
    if (!file.isDirectory() && filename.startsWith("img_")) {
      String filepath = "/" + filename;
      time_t fileTime = getFileTime(filename);
      double diff = difftime(now, fileTime);

      if (diff > 10.0) {
        Serial.printf("🗑️ Expired (%.1fs old): %s. Deleting...\n", diff, filename.c_str());
        file.close(); 
        SD.remove(filepath);
      } 
      else {
        Serial.printf("🔄 Valid for retry (%.1fs old): %s\n", diff, filename.c_str());
        if (uploadImageFromSD(filepath)) {
          String newPath = "/uploaded_" + filename.substring(4);
          SD.rename(filepath.c_str(), newPath.c_str());
        }
      }
      break; 
    }
    file = root.openNextFile();
  }
}

// =========================================================
// [5] Business Logic Module
// =========================================================

// Core Action: Capture -> Save locally -> Trigger Upload
void captureAndUpload() {
  Serial.println("📸 Waking up camera and flushing old frames...");
  
  // =========================================================
  // 🌟 核心修复：连拍并丢弃旧帧，清空底层硬件的缓存队列
  // 丢弃前 1~2 帧足以清空陈旧画面，让传感器重新曝光对焦
  // =========================================================
  camera_fb_t * fb = NULL;
  for (int i = 0; i < 2; i++) {
    fb = esp_camera_fb_get();
    if (fb) {
      esp_camera_fb_return(fb); // 拿到后立刻丢弃释放
    }
  }

  Serial.println("📸 Capturing FRESH image for LPR...");
  // 这一次拿到的，绝对是最新、曝光最准确的当下画面！
  fb = esp_camera_fb_get(); 
  
  if(!fb) {
    Serial.println("❌ Camera capture failed!");
    return;
  }

  // 1. Get real time and save to TF card
  String timestamp = getTimestamp();
  String filepath = "/img_" + timestamp + ".jpg";
  
  File file = SD.open(filepath.c_str(), FILE_WRITE);
  if(file){
    file.write(fb->buf, fb->len); 
    file.close();
    Serial.println("💾 Fresh image saved locally: " + filepath);
  }
  
  // 务必记得释放这最后一张有用的帧内存
  esp_camera_fb_return(fb); 

  // 2. Attempt immediate upload
  if (uploadImageFromSD(filepath)) {
    // Archive immediately if upload is successful
    String newFilepath = "/uploaded_" + timestamp + ".jpg";
    SD.rename(filepath.c_str(), newFilepath.c_str());
  } else {
    Serial.println("⚠️ Upload failed or offline. File queued for background retry.");
  }
}

// =========================================================
// [6] Hardware Initialization
// =========================================================
bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  config.frame_size = FRAMESIZE_SVGA; 
  config.jpeg_quality = 10; 
  config.fb_count = 1;

  if (psramFound()) {
    config.fb_location = CAMERA_FB_IN_PSRAM;
  } else {
    config.fb_location = CAMERA_FB_IN_DRAM;
    config.frame_size = FRAMESIZE_QVGA; 
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) return false;
  
  sensor_t * s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_hmirror(s, 1);  
    Serial.println("✅ Camera hardware mirror enabled.");
  }
  return true;
}

float getDistance() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  long duration = pulseIn(PIN_ECHO, HIGH, 30000); 
  if (duration == 0) return 999.0; 
  return (duration * 0.034 / 2.0); 
}

// =========================================================
// [7] MQTT Callback & Reconnect
// =========================================================
void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.printf("message: %s\n", message);
  Serial.printf("Topic: %s\n", String(topic));
  if (String(topic) == mqtt_topic_led && message != currentLedState) {
    currentLedState = message;
    previousBlinkMillis = millis();
    blinkState = true; 
    
    digitalWrite(PIN_RED, LOW);
    digitalWrite(PIN_YELLOW, LOW);
    digitalWrite(PIN_GREEN, LOW);
    noTone(PIN_BUZZER);
  }
}

void reconnect() {
  while (!client.connected()) {
    String clientId = "ESP32Client-BayA1-";
    clientId += String(random(0xffff), HEX);
    if (client.connect(clientId.c_str())) {
      client.subscribe(mqtt_topic_led); 
    } else {
      delay(5000);
    }
  }
}

// =========================================================
// [8] Main Setup & Loop
// =========================================================
void setup() {
  Serial.begin(115200);
  
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_YELLOW, OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);

  digitalWrite(PIN_RED, LOW);
  digitalWrite(PIN_YELLOW, LOW);
  digitalWrite(PIN_GREEN, LOW);
  noTone(PIN_BUZZER);

  setup_wifi();
  
  if(initCamera()) Serial.println("✅ Camera Init OK");
  if (SD.begin(SD_CS_PIN)) {
    Serial.println("✅ SD Card Mounted");
    cleanupSD(); 
    Serial.println("✅ SD Card Cleaned");
  }
  
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}
void loop() {
  if (!client.connected()) reconnect();
  client.loop(); 

  unsigned long currentMillis = millis();

  // ---------------------------------------------------------
  // Task 1: Background Daemon - Retry failed uploads (Every 10s)
  // ---------------------------------------------------------
  if (currentMillis - lastRetryMillis >= RETRY_INTERVAL) {
    lastRetryMillis = currentMillis;
    processPendingUploads();
  }

  // ---------------------------------------------------------
  // Task 2: Non-blocking Hysteresis Edge Detection (Every 200ms)
  // ---------------------------------------------------------
  if (currentMillis - lastSensorReadMillis >= SENSOR_INTERVAL) {
    lastSensorReadMillis = currentMillis;
    float dist = getDistance();
    
    // 🆕 [DEBUG LOG 1] 每 1 秒打印一次传感器状态和距离心跳
    static unsigned long lastDebugPrintMillis = 0;
    if (currentMillis - lastDebugPrintMillis >= 1000) {
        Serial.printf("📊 [Sensor] Dist: %.1f cm | OccCnt: %d | AvailCnt: %d | Bay: %s | LED: %s\n", 
                      dist, occupiedCount, availableCount, currentBayStatus.c_str(), currentLedState.c_str());
        lastDebugPrintMillis = currentMillis;
    }

    if (dist > 0) {
      if (dist <= DIST_OCCUPIED) {
        occupiedCount++;
        availableCount = 0; 
      } 
      else if (dist >= DIST_AVAILABLE || dist == 999.0) {
        availableCount++;
        occupiedCount = 0;  
      }
      else {
        // 🆕 [DEBUG LOG 2] 车辆处于死区 (100cm ~ 150cm)，重置计数器
        if (occupiedCount > 0 || availableCount > 0) {
            Serial.printf("⚠️ [Sensor] Distance in deadzone (%.1f cm). Resetting counts.\n", dist);
        }
        occupiedCount = 0;
        availableCount = 0;
      }

      if (occupiedCount >= FILTER_LIMIT && currentBayStatus != "occupied") {
        // 🆕 [DEBUG LOG 3] 确认连续 10 次检测达标
        Serial.println("🔒 [State Change] 10 consecutive reads < 100cm. Bay is now OCCUPIED.");
        currentBayStatus = "occupied";
        occupiedCount = 0; 
      } 
      else if (availableCount >= FILTER_LIMIT && currentBayStatus != "available") {
        // 🆕 [DEBUG LOG 3] 确认连续 10 次检测达标
        Serial.println("🔓 [State Change] 10 consecutive reads > 150cm. Bay is now AVAILABLE.");
        currentBayStatus = "available";
        availableCount = 0; 
      }

      // 🌟 FALLING EDGE TRIGGER: Vehicle successfully parked!
      if (currentBayStatus == "occupied" && lastBayStatus == "available") {
        Serial.println("\n>>> EVENT: Vehicle Entering... <<<");
        
        client.publish(mqtt_topic_status, "occupied");
        lastPublishMillis = currentMillis; 
        
        // 🆕 [DEBUG LOG 4] 打印当前 LED 状态，判断是否满足拍照条件
        Serial.printf("🔍 Checking Capture Conditions -> Current LED State: %s\n", currentLedState.c_str());

        if (currentLedState == "reserved" || currentLedState == "pending_check_in") {
          Serial.println("⏳ Valid state! Waiting 3 seconds for vehicle to stabilize...");
          isWaitingToCapture = true;
          captureWaitStartMillis = currentMillis; 
        } else {
          // 💡 很多时候是因为这里没通过，导致看起来“卡住”了
          Serial.println("⏭️ Skipping camera capture: LED state is NOT 'reserved' or 'pending_check_in'.");
        }
      }

      // 🆕 [DEBUG LOG 5] RISING EDGE TRIGGER: 车辆离开事件
      if (currentBayStatus == "available" && lastBayStatus == "occupied") {
        Serial.println("\n<<< EVENT: Vehicle Leaving... <<<");
        client.publish(mqtt_topic_status, "available");
        lastPublishMillis = currentMillis; 
        isWaitingToCapture = false; // 如果还在倒计时拍照，立刻取消
      }
      
      lastBayStatus = currentBayStatus; 
    }
  }

  // ---------------------------------------------------------
  // 🌟 Task 3: Asynchronous Capture Execution (稳车延时抓拍)
  // ---------------------------------------------------------
  if (isWaitingToCapture) {
    // 🆕 [DEBUG LOG] 打印 3 秒倒计时，证明程序没死机，正在等待
    static unsigned long lastWaitLogMillis = 0;
    if (currentMillis - lastWaitLogMillis >= 1000) {
        long remaining = CAPTURE_DELAY - (currentMillis - captureWaitStartMillis);
        if (remaining > 0) {
            Serial.printf("⏱️ Capture countdown: %ld ms remaining...\n", remaining);
        }
        lastWaitLogMillis = currentMillis;
    }

    if (currentMillis - captureWaitStartMillis >= CAPTURE_DELAY) {
      // 终极安全检查：车还在吗？(防止假动作)
      if (currentBayStatus == "occupied") {
        Serial.println("📸 Vehicle stabilized! Executing capture...");
        captureAndUpload();
      } else {
        Serial.println("🚫 Vehicle left before capture. Action cancelled.");
      }
      isWaitingToCapture = false; // 任务结束，重置状态
    }
  }

  // ---------------------------------------------------------
  // Task 4: MQTT Heartbeat Publish
  // ---------------------------------------------------------
  if (currentMillis - lastPublishMillis >= PUBLISH_INTERVAL) {
    lastPublishMillis = currentMillis;
    client.publish(mqtt_topic_status, currentBayStatus.c_str());
  }

  // ---------------------------------------------------------
  // Task 5: Indicator State Machine
  // ---------------------------------------------------------
  if (currentLedState == "available") { 
    digitalWrite(PIN_GREEN, HIGH);
    digitalWrite(PIN_YELLOW, LOW);
    digitalWrite(PIN_RED, LOW);
    noTone(PIN_BUZZER);
  } else if (currentLedState == "reserved") {
    digitalWrite(PIN_GREEN, LOW);
    digitalWrite(PIN_YELLOW, HIGH);
    digitalWrite(PIN_RED, LOW);
    noTone(PIN_BUZZER); 
  } else if (currentLedState == "occupied" || currentLedState == "reserved_checked_in") {
    digitalWrite(PIN_GREEN, LOW);
    digitalWrite(PIN_YELLOW, LOW);
    digitalWrite(PIN_RED, HIGH);
    noTone(PIN_BUZZER); 
  } else if (currentLedState == "pending_check_in") {
    digitalWrite(PIN_GREEN, LOW);
    digitalWrite(PIN_RED, LOW);
    noTone(PIN_BUZZER); 
    if (currentMillis - previousBlinkMillis >= 500) {
      previousBlinkMillis = currentMillis;
      blinkState = !blinkState;
      digitalWrite(PIN_YELLOW, blinkState ? HIGH : LOW);
    }
  } else if (currentLedState == "conflict_strong" || currentLedState == "conflict_weak") {
    digitalWrite(PIN_GREEN, LOW);
    digitalWrite(PIN_YELLOW, LOW);
    if (currentMillis - previousBlinkMillis >= 250) {
      previousBlinkMillis = currentMillis;
      blinkState = !blinkState;
      digitalWrite(PIN_RED, blinkState ? HIGH : LOW);
      if (blinkState) tone(PIN_BUZZER, 2000); 
      else noTone(PIN_BUZZER);     
    }
  }
}