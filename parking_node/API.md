# ParkReserve: Edge-to-Gateway API Reference

This document defines the communication protocols between the Edge Node (ESP32-S3 Sensor/Camera) and the Local Gateway (Raspberry Pi/Python Server) within the ParkReserve system.

The system employs a **Dual-Track Communication Architecture**:

1. **HTTP RESTful API**: Used for transmitting heavy, non-real-time binary payloads (e.g., High-resolution JPEG images for ALPR).
2. **MQTT Protocol**: Used for high-frequency, lightweight state synchronization and low-latency hardware control.

---

## 1. HTTP Image Upload API

This endpoint is actively called by the ESP32 edge node when a vehicle arrival is detected (Falling Edge) AND the bay is currently in a reserved state. It transmits the captured license plate image to the Gateway for OpenALPR verification.

* **Endpoint:** `/api/v1/bays/<bay_id>/image`
* **Method:** `POST`
* **Description:** Receives a raw JPEG binary stream from the edge node, strictly validated via a static API key and tagged with an exact NTP timestamp.

### 1.1 Request Parameters

**Path Parameters:**

| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `bay_id` | Integer | Yes | The unique identifier of the parking bay triggering the capture. | `1` |

**Headers:**

| Header Key | Example Value | Required | Description |
| :--- | :--- | :--- | :--- |
| `Content-Type` | `image/jpeg` | Yes | Declares the request body as pure binary image data. |
| `X-API-Key` | `ParkReserve-Group29-SuperSecret` | Yes | **[Security]** Static pre-shared key to prevent unauthorized spoofed image uploads within the local network. |
| `X-Timestamp` | `20260510_180126` | Yes | **[Telemetry]** Exact capture time synchronized via NTP on the ESP32. Prevents temporal discrepancies caused by network latency or offline retries. |

**Body:**

* Raw binary data stream of the `.jpg` image (VGA resolution).

### 1.2 Response Handling

**✅ Success Response (202 Accepted):**

* **Code:** `202 Accepted`
* **Content (JSON):** `{"message": "Image securely received", "file": "bay_1_20260510_180126.jpg"}`
* **Note:** A `202` status informs the ESP32 that the file is safely stored, allowing the microcontroller to resume its main loop while the Gateway asynchronously processes the ALPR script in the background.

**❌ Error Responses:**

* **`401 Unauthorized`**: Missing or incorrect `X-API-Key`. The request is dropped immediately.
* **`400 Bad Request`**: No image data provided in the body.

### 1.3 Example cURL Usage

To simulate an edge node upload from your terminal:

```bash
curl -X POST "[http://192.168.](http://192.168.)x.x:5000/api/v1/bays/1/image" \
     -H "Content-Type: image/jpeg" \
     -H "X-API-Key: ParkReserve-Group29-SuperSecret" \
     -H "X-Timestamp: 20260510_120000" \
     --data-binary "@test_plate.jpg"

```

---

## 2. MQTT Communication Protocol

The MQTT broker acts as the nervous system for real-time state management. Default port: `1883`.

### 2.1 Edge Node Telemetry (ESP32 -> Gateway)

The ESP32 publishes its ultrasonic sensor status to the gateway.

* **Topic:** `bay/<bay_id>/status` (e.g., `bay/1/status`)
* **Frequency:** 2-second heartbeat, OR immediate publish upon state change (debounced).
* **Payloads:**
* `available`: No vehicle detected (Distance > 1.2m).
* `occupied`: Vehicle securely detected (Distance < 1.2m for 3 consecutive reads).

### 2.2 Actuator Control (Gateway -> ESP32)

The Gateway publishes commands to control the bay's LED indicators and buzzer.

* **Topic:** `bay/<bay_id>/led` (e.g., `bay/1/led`)
* **Frequency:** Triggered by Gateway business logic (e.g., app booking, ALPR results).
* **Payload Commands:**
* `available`: **Solid Green** (Bay is open for parking).
* `reserved`: **Solid Yellow** (Bay is booked, waiting for the assigned user).
* `pending_check_in`: **Blinking Yellow** (Vehicle arrived, ALPR processing in progress).
* `reserved_checked_in`: **Solid Red** (ALPR verified, valid user parked).
* `conflict_strong`: **Blinking Red + Buzzer** (Unauthorized vehicle parked or ALPR mismatch).

---

## 3. System Interaction Flow (How They Work Together)

To fully understand the Edge-to-Gateway architecture, here is the chronological sequence of a complete parking event:

1. **Reservation Made (MQTT):** A user books Bay 1 via the web app. The Gateway publishes `reserved` to `bay/1/led`. The ESP32 receives this and turns the LED **Solid Yellow**.
2. **Vehicle Arrives (MQTT):** The ultrasonic sensor detects a vehicle. The ESP32 immediately publishes `occupied` to `bay/1/status`.
3. **Evidence Capture (HTTP):** Because the bay is `reserved` and just became `occupied`, the ESP32 captures an image, saves it to its local TF card (for offline resilience), and sends a **POST request** to `/api/v1/bays/1/image`.
4. **Processing State (MQTT):**
To indicate the system is "thinking", the Gateway publishes `pending_check_in` to `bay/1/led`. The ESP32 LED begins **Blinking Yellow**.
5. **ALPR Verification & Resolution (MQTT):**
The Gateway finishes OpenALPR processing.

* *If Match:* Gateway publishes `reserved_checked_in`. ESP32 LED turns **Solid Red**.
* *If Mismatch:* Gateway publishes `conflict_strong`. ESP32 LED turns **Blinking Red** and the **Buzzer** sounds to alert the unauthorized driver.
