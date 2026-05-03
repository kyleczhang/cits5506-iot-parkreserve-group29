#include <WiFi.h>
#include <PubSubClient.h>

// ================= 配置区 =================
const char* ssid = "8299";           // 替换为你的WiFi名称
const char* password = "zaxfsubavf";   // 替换为你的WiFi密码
const char* mqtt_server = "192.168.20.16";       // 替换为树莓派的局域网IP地址
const int mqtt_port = 1883;
const char* mqtt_topic_led = "bay/1/led";      // 监听的Topic（假设是1号车位）

// 硬件引脚定义 (请根据 XIAO ESP32S3 实际接线修改)
const int PIN_RED = D0;
const int PIN_YELLOW = D1;
const int PIN_GREEN = D2;
const int PIN_BUZZER = D3;

WiFiClient espClient;
PubSubClient client(espClient);

// ================= 状态机变量 =================
String currentState = "available";  // 默认状态
unsigned long previousMillis = 0;   // 用于非阻塞计时的变量
bool blinkState = false;            // 闪烁时的亮灭状态

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

// MQTT 接收到消息时的回调函数
void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");
  Serial.println(message);

  // 如果收到了新的状态，更新全局变量，并重置闪烁计时器，确保状态切换瞬间是清晰的
  if (message != currentState) {
    currentState = message;
    previousMillis = millis();
    blinkState = true; 
    
    // 切换状态时先全部熄灭，防止状态残留
    digitalWrite(PIN_RED, LOW);
    digitalWrite(PIN_YELLOW, LOW);
    digitalWrite(PIN_GREEN, LOW);
    digitalWrite(PIN_BUZZER, LOW);
  }
}

// MQTT 自动重连机制
void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // 创建一个随机的Client ID
    String clientId = "ESP32Client-Bay1-";
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
      // 连接成功后订阅Topic
      client.subscribe(mqtt_topic_led);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  
  // 初始化引脚为输出模式
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_YELLOW, OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  
  // 初始状态全部关闭
  digitalWrite(PIN_RED, LOW);
  digitalWrite(PIN_YELLOW, LOW);
  digitalWrite(PIN_GREEN, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop(); // 维持MQTT心跳和接收消息

  // ================= 非阻塞硬件状态机 =================
  unsigned long currentMillis = millis();

  if (currentState == "available") {
    digitalWrite(PIN_GREEN, HIGH);
    digitalWrite(PIN_YELLOW, LOW);
    digitalWrite(PIN_RED, LOW);
    noTone(PIN_BUZZER); // 关闭声音

  } else if (currentState == "reserved") {
    digitalWrite(PIN_GREEN, LOW);
    digitalWrite(PIN_YELLOW, HIGH);
    digitalWrite(PIN_RED, LOW);
    noTone(PIN_BUZZER); 

  } else if (currentState == "occupied" || currentState == "reserved_checked_in") {
    digitalWrite(PIN_GREEN, LOW);
    digitalWrite(PIN_YELLOW, LOW);
    digitalWrite(PIN_RED, HIGH);
    noTone(PIN_BUZZER); 

  } else if (currentState == "pending_check_in") {
    digitalWrite(PIN_GREEN, LOW);
    digitalWrite(PIN_RED, LOW);
    noTone(PIN_BUZZER); 
    
    if (currentMillis - previousMillis >= 500) {
      previousMillis = currentMillis;
      blinkState = !blinkState;
      digitalWrite(PIN_YELLOW, blinkState ? HIGH : LOW);
    }

  } else if (currentState == "conflict_strong" || currentState == "conflict_weak") {
    digitalWrite(PIN_GREEN, LOW);
    digitalWrite(PIN_YELLOW, LOW);
    
    if (currentMillis - previousMillis >= 250) {
      previousMillis = currentMillis;
      blinkState = !blinkState;
      
      digitalWrite(PIN_RED, blinkState ? HIGH : LOW);
      
      // 核心修改：利用状态翻转来控制蜂鸣器的发声与停止
      if (blinkState) {
        tone(PIN_BUZZER, 2000); // 2000Hz 频率（你可以改这个数字，数字越大声音越尖锐）
      } else {
        noTone(PIN_BUZZER);     // 停止发声
      }
    }
  }
}