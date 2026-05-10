# ParkReserve: Intelligent IoT Parking Management System
**CITS5506 Internet of Things - Group 29**

ParkReserve is a comprehensive, end-to-end Internet of Things (IoT) solution designed to automate parking bay reservations, monitor real-time occupancy, and enforce security via Automatic License Plate Recognition (ALPR). 

This repository contains the firmware for the **Edge Node** (Subsystem A & B: Camera & Sensors) and the **Local Gateway Server** (Subsystem C: HTTP/MQTT endpoints).

---

## 🌟 Core Engineering Features

The system has been designed with industrial-grade reliability, fault tolerance, and security in mind:

* **Industrial-Grade Sensor Debouncing:** Implements a non-blocking, consecutive-read filtering algorithm (requires 3 consecutive readings within the 1.2m threshold) to eliminate false positives caused by ultrasonic multi-path reflections or air disturbances.
* **Offline Resilience & Auto-Retry (Blackbox Mode):** Integrates NTP (Network Time Protocol) to timestamp images accurately. In the event of network failure, images are safely buffered to the onboard TF/MicroSD card. A non-blocking background daemon checks network status every 10 seconds and automatically pushes queued images to the gateway once connectivity is restored.
* **Deep Security Integration:** Employs a static API Key (`X-API-Key`) authorization header to prevent unauthorized payload spoofing within the local network. 
* **Asynchronous Dual-Track Communication:** * **MQTT (Port 1883):** Handles high-frequency, low-latency telemetry (occupancy status) and actuator control (LEDs/Buzzer).
    * **HTTP RESTful API (Port 5000):** Handles heavy binary payloads (JPEG images) independently without choking the MQTT broker.

---

## 🏗️ System Architecture

### 1. Edge Node (Seeed Studio XIAO ESP32S3 Sense)
* **Inputs:** Ultrasonic Distance Sensor, OV2640 Camera module.
* **Outputs:** Red/Yellow/Green Indicator LEDs, Active Buzzer.
* **Storage:** 32GB TF/MicroSD Card (SPI interface).
* **Role:** Continuously monitors the parking bay. Detects "Falling Edge" vehicle arrivals. Captures high-quality VGA images and publishes state changes.

### 2. Local Gateway (Raspberry Pi / Simulated on PC)
* **MQTT Broker (Mosquitto):** Routes commands and status updates between the web backend and edge nodes.
* **Python Flask Server:** Exposes a RESTful endpoint (`/api/v1/bays/<id>/image`) to securely receive, validate, and store images for downstream OpenALPR processing.

---

## 🔌 Hardware Setup & Wiring

| Component | ESP32 Pin | Note |
| :--- | :--- | :--- |
| Red LED | `D0` | Solid: Occupied/Checked-in. Blinking: Conflict. |
| Yellow LED | `D1` | Solid: Reserved. Blinking: Pending ALPR check. |
| Green LED | `D2` | Solid: Bay is available. |
| Buzzer | `D3` | Sounds during strong conflicts. |
| Ultrasonic `TRIG`| `D4` | Output signal. |
| Ultrasonic `ECHO`| `D5` | Input signal. |
| TF Card `CS` | `D21`| Standard SPI interface. |

---

## 💻 Software Installation & Configuration

### Part 1: Gateway / Server Environment Setup
The server acts as the local brain, receiving images and coordinating MQTT messages.

1.  **Start the MQTT Broker:**
    * Ensure Mosquitto is installed (v2.0+).
    * Configure `mosquitto.conf` to allow local network access:
        ```text
        listener 1883 0.0.0.0
        allow_anonymous true
        ```
    * Run the broker: `mosquitto -c mosquitto.conf -v`

2.  **Start the Python Flask API:**
    * Open a terminal in the `parking_node/pictureTestServer/` directory.
    * Set up a virtual environment:
        ```bash
        python -m venv venv
        # Windows: .\venv\Scripts\activate
        # macOS/Linux: source venv/bin/activate
        ```
    * Install dependencies and run:
        ```bash
        pip install flask
        python server.py
        ```
    * *Note: The server will listen on port `5000` and automatically create an `incoming_plates` directory.*

### Part 2: Edge Node Firmware Setup
1.  Open `esp32.ino` in the Arduino IDE.
2.  **Configure Network Parameters:**
    Update the following variables at the top of the file to match your local environment:
    ```cpp
    const char* ssid = "YOUR_WIFI_SSID";
    const char* password = "YOUR_WIFI_PASSWORD";
    const char* gateway_ip = "192.168.x.x"; // IP of the machine running Flask & Mosquitto
    ```
3.  **Critical IDE Settings:**
    Navigate to `Tools` in the top menu and ensure the following are set:
    * **Board:** `Seeed XIAO ESP32S3`
    * **PSRAM:** **`OPI PSRAM`** *(Crucial: Camera initialization will fail if disabled).*
4.  Compile and upload to the ESP32.

---

## 🧪 Testing & Verification

Once the system is powered on and connected to WiFi, follow these steps to verify functionality:

### 1. Test MQTT Control (Actuators)
Open a new terminal and publish MQTT messages to change the bay's state:
* Set to Reserved (Yellow LED): 
    `mosquitto_pub -h <gateway_ip> -t bay/1/led -m "reserved"`
* Trigger Conflict Alarm (Red LED flash + Buzzer):
    `mosquitto_pub -h <gateway_ip> -t bay/1/led -m "conflict_strong"`

### 2. Test the Business Loop (Capture & Upload)
1.  Set the bay to reserved state using the MQTT command above.
2.  Place an object within **1.2 meters** of the ultrasonic sensor to simulate a vehicle arriving (Falling Edge).
3.  **Expected Behavior:**
    * ESP32 terminal prints: `>>> EVENT: Vehicle Detected (Falling Edge) <<<`
    * Image is snapped and saved to the local TF card with an NTP timestamp.
    * Image is pushed via HTTP POST to the Gateway.
    * Python terminal logs: `✅ [Security Passed] Successfully received image for bay 1...`

### 3. Test Offline Resilience (Network Drop)
1.  Kill the `server.py` Flask process (`Ctrl+C`).
2.  Trigger the sensor again.
3.  **Expected Behavior:** The ESP32 will fail the upload, log a warning, and queue the file.
4.  Restart `server.py`. Within 10 seconds, the ESP32 background daemon will detect the connection, automatically retry the upload, and rename the file on the SD card to `uploaded_*.jpg`.

---
*Developed for CITS5506 - The University of Western Australia*