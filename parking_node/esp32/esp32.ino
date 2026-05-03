#include <WiFi.h>
#include <PubSubClient.h>

// ================= Configuration Area =================
const char* ssid = "8299";           // Replace with your WiFi SSID
const char* password = "zaxfsubavf";   // Replace with your WiFi password
const char* mqtt_server = "192.168.20.16";       // Replace with the Raspberry Pi's local IP address
const int mqtt_port = 1883;
const char* mqtt_topic_led = "bay/1/led";      // Topic to subscribe to (assuming Bay 1)

// Hardware pin definitions (Adjust according to actual XIAO ESP32S3 wiring)
const int PIN_RED = D0;
const int PIN_YELLOW = D1;
const int PIN_GREEN = D2;
const int PIN_BUZZER = D3;

WiFiClient espClient;
PubSubClient client(espClient);

// ================= State Machine Variables =================
String currentState = "available";  // Default state
unsigned long previousMillis = 0;   // Variable for non-blocking timing
bool blinkState = false;            // High/Low state for blinking

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

// Callback function when an MQTT message is received
void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");
  Serial.println(message);

  // If a new state is received, update the global variable and reset the blink timer 
  // to ensure clean state transitions
  if (message != currentState) {
    currentState = message;
    previousMillis = millis();
    blinkState = true; 
    
    // Turn everything off first when switching states to prevent residual states
    digitalWrite(PIN_RED, LOW);
    digitalWrite(PIN_YELLOW, LOW);
    digitalWrite(PIN_GREEN, LOW);
    digitalWrite(PIN_BUZZER, LOW);
  }
}

// MQTT auto-reconnect mechanism
void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Create a random Client ID
    String clientId = "ESP32Client-Bay1-";
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
      // Subscribe to the topic upon successful connection
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
  
  // Initialize pins as output mode
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_YELLOW, OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  
  // Turn everything off initially
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
  client.loop(); // Maintain MQTT heartbeat and receive messages

  // ================= Non-blocking Hardware State Machine =================
  unsigned long currentMillis = millis();

  if (currentState == "available") {
    digitalWrite(PIN_GREEN, HIGH);
    digitalWrite(PIN_YELLOW, LOW);
    digitalWrite(PIN_RED, LOW);
    noTone(PIN_BUZZER); // Turn off sound

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
      
      // Core modification: Use state toggling to control buzzer active/inactive
      if (blinkState) {
        tone(PIN_BUZZER, 2000); // 2000Hz frequency (higher number = sharper pitch)
      } else {
        noTone(PIN_BUZZER);     // Stop sound
      }
    }
  }
}