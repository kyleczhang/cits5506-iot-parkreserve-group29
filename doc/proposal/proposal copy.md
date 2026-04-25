# Project Proposal CITS5506: Internet of Things

**Unit:** CITS5506 The Internet of Things | **Semester:** 1, 2026 | **Group:** 29

| Name | Student Number |
|------|---------------|
| Nyx Chen | 24290498 |
| Riya Sakhiya | 24601375 |
| Yuan Cong Yuan | 25003723 |
| Cheng Zhang | 24878502 |

---

## 1. Name of Project

**ParkReserve: IoT-Based Parking Reservation with Real-Time Conflict Detection**

---

## 2. Team Members

| Name | Student Number |
|------|---------------|
| Nyx Chen | 24290498 |
| Riya Sakhiya | 24601375 |
| Yuan Cong Yuan | 25003723 |
| Cheng Zhang | 24878502 |

**Group Number:** 29

---

## 3. Problem, Benefits, and Impact

**Problem:**

- In urban parking facilities, drivers spend an average of 15–20 minutes searching for available spots, contributing to traffic congestion, wasted fuel, and driver frustration [1].
- Existing parking lots typically lack real-time occupancy visibility. Drivers must physically inspect each spot, which is inefficient and time-consuming.
- Even where real-time availability data exists, most systems do not support reservation. A driver may see a spot marked "available" on a dashboard but find it taken upon arrival.
- Without any reservation mechanism or conflict detection, reserved bays (where the concept exists) are frequently occupied by unauthorised vehicles and facility operators have no automated way to be alerted.

**Benefits of the Solution:**

- Real-time occupancy detection using IoT sensors eliminates the need for drivers to manually search, reducing average parking search time significantly.
- A web-based reservation system allows users to secure a bay before arrival, improving convenience and predictability. Users bind one or more licence plates to their account; any bound plate counts as a valid match for their reservation.
- LED indicators with a multi-state colour/blink scheme (green = available, yellow = reserved, red = occupied, plus blinking variants for *pending check-in* and *conflict*) provide immediate at-a-glance status visible from a distance, and act as a soft social cue to respect reservations.
- Automatic licence-plate recognition (LPR) at each bay triggers when a vehicle arrives in a reserved bay; if the recognised plate matches a plate bound to the reserving user, the system performs check-in automatically without any user action.
- Plate-evidence conflict detection distinguishes between *strong evidence* (recognised plate does not belong to the reserving user) and *weak evidence* (LPR could not return a confident result and no manual check-in occurred within the grace period). Both cases raise a per-bay audible alarm in addition to LED indication and admin notification.

**Expected Impact:**

- Reduced traffic congestion and fuel consumption in parking areas. Studies estimate that 30% of urban traffic is caused by parking searches [2].
- Improved user satisfaction through a seamless reserve-and-park workflow where the typical case requires no manual check-in step. The combination of LPR-driven evidence and an audible alarm gives reservations real teeth while still avoiding the cost and safety trade-offs of physical barriers (see §5.6).
- Demonstrates a practical, scalable three-tier IoT architecture (cloud backend, edge gateway, device layer) integrating sensing, state management, wireless communication, and web-based user interaction. This architecture is applicable to university campuses, shopping centres, and hospital car parks.
- Remote access via a cloud-hosted dashboard means users can reserve a bay from anywhere with internet access, not just within the parking facility's local network.

---

## 4. Literature Review

Several IoT-based smart parking systems have been proposed in the literature. We review key works below and identify their strengths and gaps relative to our project.

**1. Sensor-Based Occupancy Detection Systems**

Khanna and Anand [1] proposed an IoT-based smart parking system using ultrasonic sensors connected to a Raspberry Pi, with data transmitted to a cloud server and displayed on a mobile app.

- **Strength:** Demonstrated real-time occupancy detection with reasonable accuracy.
- **Gap:** The system only monitors occupancy and does not support reservations or detect misuse, so a free spot may be taken before a driver arrives.

**2. IoT Smart Parking with Cloud Integration**

Mainetti et al. [3] developed an IoT-aware smart parking system using RFID and ZigBee sensor networks with a cloud-based backend.

- **Strength:** Comprehensive architecture integrating heterogeneous sensor networks with scalable cloud storage and analytics.
- **Gap:** Relies on RFID for vehicle identification, requiring each vehicle to carry a tag, which limits adoption. No reservation or conflict detection is included.

**3. Computer Vision Approaches**

Amato et al. [4] used deep learning-based image classification to detect parking occupancy from overhead cameras.

- **Strength:** Does not require per-spot sensors, reducing hardware deployment cost at scale.
- **Gap:** Requires significant computational resources for image processing, is sensitive to lighting and weather conditions, and does not support reservation.

**4. Commercial Products: ParkAssist and Guidance Systems**

Commercial parking guidance systems such as ParkAssist use overhead sensors and LED indicators to guide drivers to available bays in multi-storey car parks [5].

- **Strength:** Deployed at scale in airports and shopping centres with proven reliability.
- **Gap:** These are proprietary, high-cost systems designed for large operators and not accessible for small-to-medium facilities. They provide guidance only, without reservation or conflict detection.

**5. MQTT-Based IoT Communication**

The MQTT protocol [6] is widely adopted in IoT systems for lightweight publish/subscribe messaging. It is well-suited for constrained devices like ESP32 due to its low bandwidth overhead and support for Quality of Service (QoS) levels.

**Summary of Gaps Addressed by Our Project:**

| Feature | [1] Khanna | [3] Mainetti | [4] Amato | Commercial [5] | **Ours** |
|---------|-----------|-------------|----------|----------------|----------|
| Real-time detection | ✓ | ✓ | ✓ | ✓ | **✓** |
| Web/mobile dashboard | ✓ | ✓ | ✗ | ✓ | **✓** |
| Online reservation | ✗ | ✗ | ✗ | ✗ | **✓** |
| Licence-plate recognition (auto check-in) | ✗ | ✗ | ✗ | ✗ | **✓** |
| Plate-evidence conflict detection (strong + weak) | ✗ | ✗ | ✗ | ✗ | **✓** |
| Visual LED indicators | ✗ | ✗ | ✗ | ✓ | **✓** |
| Audible per-bay alarm on misuse | ✗ | ✗ | ✗ | ✗ | **✓** |
| Low-cost / accessible | ✓ | ✗ | ✗ | ✗ | **✓** |

Our project uniquely combines real-time sensing, web-based reservation with multi-plate accounts, automatic LPR-based check-in, a multi-state LED visual-feedback scheme, and per-bay audible alarms tied to plate-evidence conflict detection — all in a low-cost, ESP32-CAM based system.

---

## 5. Methodology and System Design

### 5.1 Design Approach

The system uses a **three-tier architecture**: a cloud-hosted backend for business logic, account/plate management, and user access; a Raspberry Pi 5 edge gateway that hosts local device control, the per-bay state machine, and the on-device licence-plate recognition (LPR) service; and ESP32-CAM nodes at each parking bay that handle ultrasonic detection, multi-state LED + buzzer indication, and on-trigger image capture.

The deployment target is an **indoor parking facility** (e.g., a multi-storey car park or undercover building car park). Indoor conditions provide controlled lighting, stable temperature, and protection from rain/debris, which yields more accurate and easier-to-calibrate ultrasonic distance measurement, more reliable LPR recognition, and reduces false positive/negative rates. The system also assumes a **casual-parking-allowed** facility: reservation is an optional convenience feature, not a mandatory access requirement, and users without a reservation can still park in any non-reserved bay.

The prototype demonstrates **three parking bays**, each instrumented with one ESP32-CAM node.

1. **Sensor Integration:** Mount an ultrasonic distance sensor (RCWL-1601) at each parking bay to continuously measure the distance to the ground. A vehicle presence is detected when the measured distance drops below a calibrated threshold. Crossing the threshold also acts as a *trigger* for the on-board ESP32-CAM camera to capture an image of the vehicle's licence plate.

2. **Status Indication:** Each bay has three LEDs (red, green, yellow) plus an active buzzer. The LEDs display one of six states via solid or blinking patterns; the buzzer is on only in the `Conflict` state (see §5.4 for the full state machine):
   - **Green (solid)** — available
   - **Yellow (solid)** — reserved, not yet occupied
   - **Yellow (blinking)** — vehicle detected in a reserved bay, awaiting auto/manual check-in
   - **Red (solid)** — occupied (casual user, or checked-in reservation holder)
   - **Red (blinking) + buzzer** — conflict: reserved bay misused

3. **Plate Management and Account Binding:** Each user account binds one or more licence plates. A reservation does not pin a specific plate — *any* of the reserving user's currently bound plates counts as a valid match. Plate ownership is not verified in the prototype (plates are taken as user-supplied and assumed correct; see §5.6).

4. **Licence-Plate Recognition (LPR) and Auto Check-in:** When a vehicle is detected in a *reserved* bay, the ESP32-CAM captures a JPEG image and uploads it to the Raspberry Pi over HTTP. The Pi runs **OpenALPR** locally to extract the plate string. If the recognised plate (with confidence above the configured threshold) belongs to the reserving user's bound plates, the system performs check-in automatically. If the plate does not match, the system raises a *strong-evidence* conflict immediately. If LPR fails to return a confident result, the bay falls back to the manual check-in flow with the existing grace period (see §5.5).

5. **Reservation State Management:** Reservation is treated as an **informational/priority service** with active deterrence (alarm), not a physical enforcement mechanism (see §5.6 for the rationale). The Raspberry Pi gateway runs a per-bay state machine that merges sensor readings, LPR results, and reservation records to drive LED + buzzer output and emit events (`pending_check_in`, `auto_check_in`, `conflict_strong`, `conflict_weak`, `no_show`) that the cloud backend uses to notify the reserving user and the facility administrator.

6. **Local Processing (ESP32-CAM):** Each ESP32-CAM node reads its ultrasonic sensor, drives its LEDs and buzzer based on state commands from the gateway, and on trigger captures and uploads a JPEG image to the Pi. It connects to the Raspberry Pi gateway via local WiFi using MQTT (for status/commands) and HTTP (for image upload).

7. **Edge Gateway (Raspberry Pi 5, 16 GB):** A Pi 5 on the same local network as the ESP32-CAM nodes runs:
   - A local Mosquitto MQTT broker for fast, reliable communication with ESP32-CAM devices.
   - A small image-receiver HTTP service that accepts captured JPEGs from the nodes.
   - **OpenALPR** for local licence-plate recognition.
   - A control logic service (Python) that owns the per-bay state machine, merges sensor data, LPR results, and reservation state, drives LED + buzzer commands locally, and bridges events and commands to/from the cloud backend via a cloud MQTT broker (HiveMQ Cloud).
   - This ensures low-latency local control (sensor → LPR → LED response stays on the LAN) and continued operation even if the cloud connection is temporarily interrupted.

8. **Cloud Backend (AWS):** A Flask (Python) web application deployed on AWS EC2 that:
   - Connects to the cloud MQTT broker to receive bay status, LPR results, and state-machine events from the Raspberry Pi and to publish reservation updates and the per-user bound-plate list.
   - Manages account/plate management, reservation business logic (booking window, grace period, breach accounting — see §5.5), and persists state in a PostgreSQL database.
   - Pushes notifications to the reserving user (auto check-in success, please-check-in prompt) and to facility administrators (strong/weak conflict alerts).
   - Serves the web dashboard over a public URL, accessible from anywhere with internet access.

9. **Web Dashboard:** A React.js application accessible remotely where users can:
   - View real-time occupancy and reservation status of all three bays (colour-coded map), with live updates via WebSocket or polling.
   - Manage their bound licence plates (add, remove, list).
   - Reserve an available bay (booking window and breach rules per §5.5) or cancel a reservation.
   - Manually check in on arrival as a fallback when LPR did not auto-resolve (via QR code scan at the bay, with a manual "I'm here" button as further fallback — see §5.5).
   - (Admin view) See strong/weak conflict alerts with bay ID, plate evidence (if any), and timestamp.

10. **System Integration and Testing:** Connect all three tiers, test end-to-end flows (detection → camera trigger → LPR → state machine → cloud sync → dashboard notification; reservation → LED → auto/manual check-in → strong/weak conflict + alarm), and calibrate sensor thresholds and LPR confidence thresholds.

### 5.2 System Architecture (Block Diagram)

```
╔══════════════════════════════════════════════════════════════════════════╗
║                       CLOUD TIER (AWS)                                   ║
║                                                                          ║
║  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────┐   ║
║  │  Web Dashboard     │  │  Flask Backend      │  │  PostgreSQL DB   │   ║
║  │  (React.js SPA)    │◄─┤  (Accounts, Plates, │──┤ (Users, Plates,  │   ║
║  │  Public URL        │  │  Reservations,      │  │  Reservations,   │   ║
║  │                    │  │  Notifications,     │  │  Breaches,       │   ║
║  │                    │  │  REST API)          │  │  Conflict log)   │   ║
║  └────────────────────┘  └─────────┬──────────┘  └──────────────────┘   ║
║                                    │                                      ║
║                          ┌─────────┴──────────┐                          ║
║                          │  Cloud MQTT Broker  │                          ║
║                          │  (HiveMQ Cloud)     │                          ║
║                          └─────────┬──────────┘                          ║
╚════════════════════════════════════╪══════════════════════════════════════╝
                                     │ Internet (MQTT over TLS)
                                     │
╔════════════════════════════════════╪══════════════════════════════════════╗
║              EDGE GATEWAY (Raspberry Pi 5, 16 GB)                          ║
║                                    │                                       ║
║  ┌─────────────────────────────────┴────────────────────────────────┐    ║
║  │  Control Logic Service (Python)                                   │    ║
║  │  - Per-bay state machine (merges sensor + LPR + reservation)      │    ║
║  │  - Bridges local MQTT ↔ cloud MQTT                                │    ║
║  │  - Emits auto_check_in / pending_check_in / conflict_strong /     │    ║
║  │    conflict_weak / no_show events                                 │    ║
║  │  - Drives LED + buzzer commands locally                           │    ║
║  └────┬──────────────────────────────────────────────────────┬──────┘    ║
║       │                                                       │           ║
║  ┌────┴─────────┐    ┌──────────────────┐    ┌───────────────┴──────┐   ║
║  │ Local MQTT    │    │  Image Receiver   │    │  OpenALPR Service    │   ║
║  │ (Mosquitto)   │    │  (HTTP, JPEG in)  │───▶│  (plate extraction)  │   ║
║  └────┬─────────┘    └────────┬─────────┘    └──────────────────────┘   ║
╚═══════╪══════════════════════╪══════════════════════════════════════════╝
        │ Local WiFi (MQTT)    │ Local WiFi (HTTP image upload)
        │                      │
        ├──────────────────────┴──────────────────────┐
        │                      │                       │
        ▼                      ▼                       ▼
 ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
 │   ESP32-CAM Node     │ │   ESP32-CAM Node     │ │   ESP32-CAM Node     │
 │       (Bay 1)        │ │       (Bay 2)        │ │       (Bay 3)        │
 │                      │ │                      │ │                      │
 │ ┌──────────────────┐ │ │ ┌──────────────────┐ │ │ ┌──────────────────┐ │
 │ │ RCWL-1601        │ │ │ │ RCWL-1601        │ │ │ │ RCWL-1601        │ │
 │ │ (ultrasonic)     │ │ │ │ (ultrasonic)     │ │ │ │ (ultrasonic)     │ │
 │ └──────────────────┘ │ │ └──────────────────┘ │ │ └──────────────────┘ │
 │ ┌──────────────────┐ │ │ ┌──────────────────┐ │ │ ┌──────────────────┐ │
 │ │ Camera (OV2640)  │ │ │ │ Camera (OV2640)  │ │ │ │ Camera (OV2640)  │ │
 │ └──────────────────┘ │ │ └──────────────────┘ │ │ └──────────────────┘ │
 │ ┌──────────────────┐ │ │ ┌──────────────────┐ │ │ ┌──────────────────┐ │
 │ │ R / G / Y LEDs   │ │ │ │ R / G / Y LEDs   │ │ │ │ R / G / Y LEDs   │ │
 │ └──────────────────┘ │ │ └──────────────────┘ │ │ └──────────────────┘ │
 │ ┌──────────────────┐ │ │ ┌──────────────────┐ │ │ ┌──────────────────┐ │
 │ │ Active Buzzer    │ │ │ │ Active Buzzer    │ │ │ │ Active Buzzer    │ │
 │ └──────────────────┘ │ │ └──────────────────┘ │ │ └──────────────────┘ │
 └──────────────────────┘ └──────────────────────┘ └──────────────────────┘
```

**Data Flow:**

- **Uplink (Sensor + Image → Cloud):** ESP32-CAM reads RCWL-1601 distance → publishes `occupied`/`available` to local MQTT topic `bay/<id>/status`. On a falling-edge transition (vehicle just arrived) in a reserved bay, the node also captures a JPEG and HTTP-POSTs it to the Pi's image-receiver. The Pi feeds sensor + reservation + LPR result into the per-bay state machine, updates the LED + buzzer command locally, and forwards bay state and derived events (`auto_check_in`, `pending_check_in`, `conflict_strong`, `conflict_weak`, `no_show`) — including the recognised plate string for conflict events — to the cloud MQTT broker. Flask updates the database and dashboard and pushes notifications.
- **Downlink (Reservation / Plate List → Bay):** User manages plates, reserves, cancels, or manually checks in on the web dashboard → Flask publishes a reservation update (with the reserving user's bound-plate list) to cloud MQTT topic `bay/<id>/reservation` → Raspberry Pi state machine updates its view → Pi publishes an LED + buzzer state command to local MQTT topic `bay/<id>/led` → ESP32-CAM drives the LEDs and buzzer accordingly.

### 5.3 Subsystem Description

#### Subsystem A: Sensing & Capture Unit (Hardware + Firmware)

- **Hardware:** Per bay, an RCWL-1601 ultrasonic distance sensor (3–5V compatible) and the on-board OV2640 camera of an ESP32-CAM. The ultrasonic sensor connects to two GPIO pins (trigger + echo); the camera uses the ESP32-CAM's dedicated camera bus.
- **Software:** Arduino C++ firmware on ESP32-CAM. Periodically triggers an ultrasonic pulse, measures echo time, calculates distance. If distance < threshold (e.g., 15 cm for a scale model), the bay is `occupied`. On a falling-edge transition (transition from `available` to `occupied`) where the bay is currently `reserved`, the firmware additionally captures a JPEG image at VGA/SVGA resolution and uploads it to the Pi's image-receiver service over HTTP.
- **Output:** Publishes `occupied` / `available` status to the local MQTT broker every 2 seconds; on a relevant arrival event, also pushes a JPEG image to `http://<pi>/upload?bay=<id>`.

#### Subsystem B: Indicator & Alarm Unit (Hardware + Firmware)

- **Hardware:** Three individual 5mm LEDs (red, green, yellow) per bay, each driven through a 220 Ω current-limiting resistor from an ESP32-CAM GPIO pin; one active piezo buzzer per bay driven from a GPIO pin.
- **Software:** LED + buzzer output is set based on a state command received from the gateway:
    - `available` → green solid; buzzer off
    - `reserved` → yellow solid; buzzer off
    - `pending_check_in` → yellow blinking (~1 Hz); buzzer off
    - `occupied` / `reserved_checked_in` → red solid; buzzer off
    - `conflict_strong` / `conflict_weak` → red blinking (~2 Hz); **buzzer on** (intermittent ~2 Hz, mirrors the LED)
- **Interdependence:** Depends on state commands from Subsystem C relayed via Subsystem D.

#### Subsystem C: Reservation State Management, LPR & Conflict Detection (Software)

- **Runs on:** The Raspberry Pi 5 (primary control loop) with a mirrored state view in the cloud backend for dashboard and notifications.
- **Responsibility:** Owns the per-bay state machine defined in §5.4. For each bay, it combines the latest sensor reading (Subsystem A), the latest LPR result (from the local OpenALPR service), and the current reservation record (with the reserving user's bound-plate list, held in the cloud DB and mirrored over cloud MQTT) to compute the next state, drive the appropriate LED + buzzer command (Subsystem B), and emit events (`auto_check_in`, `pending_check_in`, `conflict_strong`, `conflict_weak`, `no_show`) that flow back to Subsystem F for notification and breach/incident accounting.
- **Key logic:**
    - On `reservation_created`, set bay state to `reserved` (yellow solid).
    - When the sensor reports `occupied` for a `reserved` bay, transition to `pending_check_in` (yellow blinking) and request an LPR run on the just-uploaded image. While LPR is in flight, the bay remains `pending_check_in`.
    - **LPR result handling:**
        - *Match* (recognised plate ∈ reserving user's bound plates, confidence ≥ threshold): transition to `reserved_checked_in` (red solid) and emit `auto_check_in`.
        - *Mismatch* (recognised plate ∉ bound plates, confidence ≥ threshold): transition immediately to `conflict_strong` (red blinking + buzzer) and emit `conflict_strong` with the recognised plate string as evidence.
        - *Failure / low confidence:* stay in `pending_check_in`. The reserving user is prompted to check in manually (notification). If they confirm check-in within the 5 min check-in grace from vehicle detection → `reserved_checked_in`. If grace expires with no manual check-in → transition to `conflict_weak` (red blinking + buzzer) and emit `conflict_weak`.
    - If the user never arrives (bay remains empty at arrival_time + 5 min), auto-release: transition to `available` and emit `no_show`.
- **Interdependence:** Consumes Subsystem A (sensor status via local MQTT, image via the local image-receiver), invokes the local OpenALPR service, drives Subsystem B (LED + buzzer commands via local MQTT), and exchanges reservation state / events with Subsystem F via cloud MQTT.

#### Subsystem D: Communication Layer (Software)

- **Local MQTT (ESP32-CAM ↔ Raspberry Pi):** Each ESP32-CAM connects to the Mosquitto broker running on the Raspberry Pi over local WiFi.
    - `bay/<id>/status`: published by ESP32-CAM (sensor data uplink)
    - `bay/<id>/led`: published by Raspberry Pi control service (LED + buzzer state command downlink)
- **Local HTTP (ESP32-CAM → Raspberry Pi):** Image upload uses a dedicated HTTP endpoint on the Pi (`POST /upload?bay=<id>`) rather than MQTT, since JPEG payloads are too large to be a good fit for the broker.
- **Cloud MQTT (Raspberry Pi ↔ AWS):** The Raspberry Pi's control service connects to a cloud MQTT broker (HiveMQ Cloud) over a TLS-encrypted internet connection.
    - `cloud/bay/<id>/state`: bay state forwarded by Pi to cloud (uplink)
    - `cloud/bay/<id>/event`: state-machine events (`auto_check_in`, `pending_check_in`, `conflict_strong`, `conflict_weak`, `no_show`) forwarded by Pi to cloud, including recognised plate string for conflict events
    - `cloud/bay/<id>/reservation`: reservation updates (and the reserving user's bound-plate list) published by Flask backend (downlink)
- **QoS:** Level 1 (at least once delivery) on both local and cloud MQTT to ensure commands and events are not lost.
- **Interdependence:** Bridges Subsystems A/B (ESP32-CAM devices) with Subsystem F (cloud backend) through Subsystem E (Raspberry Pi gateway).

#### Subsystem E: Edge Gateway (Raspberry Pi 5, Hardware + Software)

- **Hardware:** Raspberry Pi 5 (16 GB) connected to the same local WiFi network as the ESP32-CAM nodes, and to the internet. The 16 GB RAM and quad-core ARM Cortex-A76 give comfortable headroom for OpenALPR alongside the broker and control service.
- **Software:** Runs four services:
    1. **Mosquitto MQTT broker** — handles all local ESP32-CAM communication.
    2. **Image-receiver HTTP service (Python, e.g., FastAPI)** — accepts uploaded JPEGs and stages them for LPR.
    3. **OpenALPR service** — extracts plate strings from staged images; returns `(plate, confidence)`.
    4. **Control logic service (Python)** — hosts Subsystem C (state machine + LPR-driven check-in / conflict detection), subscribes to local `bay/+/status` topics, publishes LED + buzzer commands on `bay/<id>/led`, invokes the OpenALPR service on new images, and bridges messages to/from the cloud MQTT broker.
- **Key benefit:** Local control loop (sensor + image → LPR → state machine → LED/buzzer) operates entirely on the LAN with low latency. If the cloud connection drops, the Pi continues to manage detection, LPR, and indicator updates locally; reservation updates queue until connectivity resumes.
- **Interdependence:** Hosts Subsystem C. Acts as the central bridge between the device layer (Subsystems A/B) and the cloud layer (Subsystem F).

#### Subsystem F: Cloud Backend and Dashboard (Software, AWS)

- **Backend:** Python Flask application deployed on AWS EC2. Connects to the cloud MQTT broker via the `paho-mqtt` library. Receives bay state, LPR-derived events, and conflict evidence; manages account / plate / reservation business logic (booking window, cancellation rules, breach and incident accounting — §5.5); exposes REST API endpoints.
- **Frontend:** React.js dashboard. Displays a colour-coded parking map with real-time updates (via WebSocket or periodic polling). Users can manage their bound plates, view availability, reserve/cancel bays, and perform manual check-in (QR or "I'm here" button) when LPR did not auto-resolve. An admin view surfaces strong/weak conflict alerts with plate evidence.
- **Database:** PostgreSQL (AWS RDS) or SQLite stores users, bound plates, bay states, reservation records (user, bay, arrival time, check-in time, status, check-in mechanism), conflict log (bay, evidence plate, captured-image reference, timestamp), and breach records.
- **Notifications:** On `auto_check_in` the backend pushes a confirmation to the reserving user ("you're checked in at Bay X"). On `pending_check_in` it pushes a "vehicle detected — please check in" prompt. On `conflict_strong` / `conflict_weak` it alerts facility administrators (with the recognised plate string when available).
- **Interdependence:** Depends on Subsystem D (cloud MQTT) for real-time bay state and events from the Raspberry Pi. Sends reservation updates and bound-plate lists back through Subsystem D → Subsystem E → Subsystem C.

### 5.4 Reservation State Machine

Each parking bay is represented by a state machine that merges real-time sensor input, the latest LPR result, and reservation records (including the reserving user's bound-plate list). The six possible states and their LED + buzzer representations are:

| State | Meaning | LED | Buzzer |
|-------|---------|-----|--------|
| **Available** | No active reservation, no vehicle detected | Green solid | Off |
| **Reserved** | Reservation active, no vehicle yet | Yellow solid | Off |
| **Occupied (casual)** | Vehicle present, no active reservation (no LPR run) | Red solid | Off |
| **Pending Check-in** | Vehicle detected in reserved bay; LPR running, failed, or low confidence; awaiting auto/manual check-in | Yellow blinking | Off |
| **Reserved + Checked-in** | Reserving user confirmed (auto via LPR match, or manual) | Red solid | Off |
| **Conflict** | Reserved bay misused — strong evidence (LPR plate mismatch) or weak evidence (no check-in after grace) | Red blinking | **On** (~2 Hz) |

Key transitions (defaults: 5 min after expected arrival time for no-show auto-release; 5 min after vehicle detection for the check-in grace; LPR confidence threshold 80%):

```
                reserve                          vehicle_detected
 Available ──────────────▶ Reserved ─────────────────────────────▶ Pending Check-in
     ▲                        │                                           │
     │ cancel                 │ arrival_time + 5min                       │ ┌─ LPR result ─┐
     │ OR no-show             │ (bay empty): auto-release + breach        │ │              │
     │ (arrival+5min)         ▼                                           │ ▼              │
     │                    Available                                       │ match (auto)   │
     │                                                                    │ │              │
     │                                                                    │ ▼              │
     │                                              Reserved + Checked-in │                │
     │                                                       ▲            │                │
     │                                                       │ manual     │                │
     │                                                       │ check-in   │                │
     │                                                       │ OK         │                │
     │                                                       └────────────┘                │
     │                                                                                     │
     │                                                                                     ▼
     │                                                                     ┌─ mismatch (strong) ─┐
     │                                                                     │                     │
     │                                                                     │  OR grace expired   │
     │                                                                     │  with no manual     │
     │                                                                     │  check-in (weak)    │
     │                                                                     ▼                     │
     │                                                                  Conflict                 │
     │                                                              (red blink + buzzer)         │
     │                                                                     │                     │
     │                                       vehicle_leaves                │                     │
     └─────────────────────────────────────────────────────────────────────┴─────────────────────┘

 Reserved + Checked-in ───────────────▶ Available
                       vehicle_leaves

 Available ─────────────────▶ Occupied (casual) ─────────────▶ Available
                vehicle_detected                 vehicle_leaves
                (no reservation; no LPR run)
```

Both *strong* and *weak* conflicts share the same `Conflict` state (red blinking + buzzer), but they differ in:

- **Trigger timing:** strong fires immediately on LPR plate mismatch; weak fires only after the 5 min check-in grace expires with no manual check-in.
- **Evidence:** strong includes a recognised plate string (and the captured image, retained for the conflict log); weak does not.
- **Breach accounting:** strong is logged as a *facility incident* (the reserving user is a victim, not at fault); weak is counted as a breach against the reserving user. See §5.5.

### 5.5 Reservation Rules and Check-in Mechanism

**Plate binding.** Each user account binds one or more licence plates (1–5 in the prototype). Plates are added or removed from the dashboard. Plate ownership is **not** verified in the prototype — the user-supplied plate string is taken as authoritative (see §5.6 for the rationale and the production-deployment caveat).

**Reservation matching policy.** A reservation does not pin a specific plate. *Any* of the reserving user's currently bound plates counts as a valid match for that reservation. This keeps the user flow simple — they don't need to specify which car they will arrive in — and accommodates same-day vehicle changes.

**Booking window.** Users may reserve a bay up to **one hour in advance**. This short window maximises bay utilisation and matches the typical "I'm about to drive there" use case; longer-horizon reservations are out of scope for this prototype.

**Check-in mechanisms (in order of preference).**

1. **Primary — automatic via LPR.** When a vehicle is detected in a reserved bay, the ESP32-CAM captures an image and the Pi runs OpenALPR. If the recognised plate (confidence ≥ threshold) is in the reserving user's bound-plate list, the bay automatically transitions to `Reserved + Checked-in`. **No user action is required in the typical case.** The user receives a confirmation notification.
2. **Fallback — QR code at the bay.** Each bay has a printed QR code encoding its bay ID. If LPR did not auto-resolve (failure, low confidence, dirty plate, etc.), the user scans the QR from the dashboard, which authenticates them and calls the check-in endpoint.
3. **Further fallback — manual "I'm here" button on the dashboard.** Used if the QR code is damaged or unreadable.

**Grace periods.**

- *Arrival grace (no-show):* if the user has not arrived by `expected_arrival_time + 5 min` and the bay is still empty, the reservation is auto-released to `Available` and a breach is recorded.
- *Check-in grace:* once a vehicle is detected in a reserved bay, the LPR auto-check-in attempt happens immediately. If LPR returns a confident *mismatch*, the bay enters `Conflict (strong)` straight away. If LPR fails or returns low confidence, the reserving user has 5 min from vehicle detection to perform a manual check-in (QR or button) before the bay transitions to `Conflict (weak)`.

**Conflict alarm.** The per-bay buzzer is activated together with red blinking LEDs whenever the bay enters `Conflict`, regardless of whether the trigger was strong (plate mismatch) or weak (no check-in after grace). The alarm stops when the bay leaves `Conflict` — either the vehicle leaves (`vehicle_leaves`) or, in the weak case only, a late manual check-in succeeds. Strong-evidence conflicts cannot be cleared by manual check-in (the recognised plate is provably not the user's), and the bay must be cleared by the vehicle leaving (or an admin override).

**Breach and incident accounting.**

| Event | Counted as breach against reserving user? |
|-------|-------|
| User cancels **≥ 15 minutes** before expected arrival time | No |
| User cancels **< 15 minutes** before expected arrival time | Yes |
| User never arrives (no-show; bay empty at arrival + 5 min) | Yes |
| Strong-evidence conflict (LPR plate ∉ user's bound plates) | **No** — logged as a *facility incident* against the bay, with the recognised plate as evidence. The reserving user is a victim, not at fault. |
| Weak-evidence conflict (vehicle detected, LPR did not auto-resolve, and no manual check-in within 5 min grace) | Yes — the user could have checked in manually if it was them. |

> The 15-minute cancellation cutoff is measured against *expected arrival time*, not *booking time*, so even a late booking (e.g., reserving 20 min in advance) still offers a safe cancellation window.

**Sanction.** If a user accrues **more than two breaches in a rolling calendar month**, their reservation privilege is suspended for the remainder of the month. They can still park casually at non-reserved bays. Thresholds (breach count, grace periods, booking window, LPR confidence) are configurable per facility; the values above are prototype defaults.

**Privacy and image retention.** Captured images and recognised plate strings are personally identifiable information. The prototype's default policy:

- On *successful auto check-in*, the image is discarded immediately; only the recognised plate is logged with the reservation record.
- On *strong-evidence conflict*, the image and recognised plate are retained for **30 days** as evidence in the conflict log, then purged.
- On *weak-evidence conflict*, no image is retained (LPR didn't return a confident result, so there is no usable evidence).
- For *casual occupancy* (no active reservation), no image is captured at all — LPR runs only when the bay state is `reserved`.

### 5.6 Design Decisions

Several design decisions were made during the proposal phase to better reflect real-world deployment constraints. We document them explicitly because they shape subsequent scope.

**Removal of physical barriers (servo-controlled gate arms).** An earlier version of the design included a per-bay servo barrier that would physically block unauthorised vehicles from entering a reserved bay. We chose to remove this for the following reasons:

- **Cost and maintenance.** Per-bay mechanical actuators significantly raise bill-of-materials cost and create ongoing maintenance load (motor wear, alignment drift).
- **Safety and liability.** Small barrier arms can damage vehicles or injure pedestrians if they fail-closed or close on an obstruction; the facility operator then carries liability.
- **Failure modes.** Mechanical or power failure either leaves the barrier stuck up (bay unusable) or stuck down (no enforcement) — both operationally disruptive.
- **Emergency access.** Emergency vehicles and pedestrians must always be able to pass freely; a physical barrier creates a hard constraint at odds with this.

Instead, the system treats reservations as an **informational/priority signal backed by LPR-derived evidence, an audible per-bay alarm, and admin alerting**. This is consistent with how many real-world operators (e.g., shopping-centre "disabled" / "parent with pram" bays) handle soft enforcement, while still giving misuse a tangible cost (an alarm sounds, an image is logged, an admin is notified).

**Indoor deployment scope.** The system is scoped for indoor parking facilities. Outdoor deployment is not a design target because:

- Outdoor ultrasonic readings suffer from temperature-induced sound-speed drift, wind-carried debris, and rain; calibration is harder and false positive/negative rates rise.
- Outdoor LEDs need weatherproofing and higher brightness to be visible in direct sunlight, which complicates the BoM.
- Indoor WiFi coverage is typically more consistent, simplifying networking assumptions.

**Payment out of scope.** The target facility is assumed to allow casual parking; reservation is an optional convenience, not a mandatory access requirement. Payment integration is not part of this prototype, but the system exposes a reservation / check-in / conflict event stream (with plate evidence on strong-evidence conflicts) that an external payment system could consume.

**Plate ownership not verified.** In the prototype, when a user adds a plate to their account, we **trust the user's input** — there is no verification that the plate actually belongs to them. This is appropriate for a class prototype but would be unsafe in production: a malicious user could bind another driver's plate, then exploit auto check-in to "consume" reservations associated with that plate. A production deployment would need a verification step, e.g., uploading a copy of the vehicle registration document with OCR + manual review, or integration with a vehicle-registry API.

**Enforcement boundary.** The system's role ends at *detecting*, *alerting*, and *deterring* (via the alarm). Direct enforcement (boot-locks, fines, gate integration) is delegated to facility operators or to an external payment system (where the facility has one). Our scope is providing reliable evidence (bay state, timestamps, recognised plate, captured image) and timely alerts.

**Privacy / image retention.** Recognised plates and captured images are PII and are retained only as long as needed for their intended purpose (see the retention policy in §5.5). Indoor placement and per-bay framing minimise incidental capture of bystanders.

### 5.7 Future Work

The following extensions are **not in the core scope** but the architecture is designed to accommodate them.

**Plate ownership verification.** Add a verification step at plate-binding time (registration document upload with OCR + manual review, or integration with a vehicle-registry API). Closes the abuse vector noted in §5.6.

**Mobile push notifications.** A native or PWA mobile client wired to the existing notification stream (auto check-in confirmations, please-check-in prompts, conflict alerts), giving lower-friction alerts than email/dashboard.

**Outdoor deployment hardening.** Weatherproof enclosures, IR-illuminated cameras (for night operation), temperature-compensated ultrasonic distance, and high-brightness LEDs for direct sunlight. Required to extend the system to open-air car parks.

**Admin override and conflict resolution UI.** A workflow for admins to clear strong-evidence conflicts (e.g., when the misusing vehicle is moved by staff) and to issue out-of-band fines or warnings tied to logged plate evidence.

---

## 6. Distribution of Work

| Name | Primary Subsystem | Integration / Testing / Docs Role | Reason for the Assignment |
|------|-------------------|-----------------------------------|---------------------------|
| Yuan Cong Yuan | **Subsystem A + B:** Ultrasonic sensor integration, ESP32-CAM image-capture firmware (sensor-triggered) + HTTP image upload, multi-state LED control (including blinking patterns), buzzer driver | **Device-level testing lead:** sensor calibration, full six-state LED + buzzer coverage, camera trigger / upload bring-up, hardware ↔ firmware bring-up; also compiles final report and demo script | Strong debugging and system-level thinking skills; the device layer (A+B) is tightly coupled (camera trigger and LED/buzzer state both derive from sensor readings + commands) so a single owner is more efficient than two |
| Nyx Chen | **Subsystem C + D + E:** Per-bay reservation state machine and conflict-detection service on the Raspberry Pi, **OpenALPR setup and integration** (image-receiver service, plate-matching against bound-plate lists), MQTT communication setup (local + cloud brokers), edge gateway control logic | **Cross-tier integration lead:** owns end-to-end data-flow bring-up across device ↔ gateway ↔ cloud (natural fit since C+D+E already sits in the middle, and LPR runs on the Pi inside Subsystem C's control loop) | Experience with networking protocols, state-machine design, and microcontroller programming; LPR integration sits on the same Pi as the state machine, so co-locating ownership avoids hand-off seams |
| Cheng Zhang | **Subsystem F (Backend):** Flask server, REST API, **account & plate management** (CRUD on bound plates, plate-list publish over cloud MQTT), reservation business logic (booking window, breach + incident accounting, push notifications), conflict-evidence log, database, cloud MQTT client integration, AWS deployment | Backend unit/integration tests; API and deployment documentation | Background in Python and server-side programming; familiarity with cloud services |
| Riya Sakhiya | **Subsystem F (Frontend):** React.js parking map UI, real-time status updates, **plate-management UI** (add/remove/list bound plates), reservation / cancel / manual-check-in interface (including QR scan fallback flow), admin conflict-alert view with plate evidence | Frontend unit tests; UI/UX documentation and demo screen captures | Experience in web development (React, HTML/CSS/JS); strong UI/UX design skills |

> *Note: This is an initial distribution based on team discussion. Week 5 integration, Week 6 end-to-end testing, and Week 7 demo preparation are shared responsibilities across all members, coordinated by the two integration/testing leads above. Roles may be adjusted during the project as needed.*

---

## 7. Project Timeline

The project spans **7 weeks** from proposal submission to final demonstration (due **May 22**). Tasks are assigned to sub-teams with sequential and parallel dependencies shown.

| Week | Dates | Task | Sub-Team | Dependencies |
|------|-------|------|----------|-------------|
| 1 | Apr 7 – Apr 13 | Environment setup: install Arduino IDE (with ESP32-CAM board package), Flask, Mosquitto and OpenALPR on Raspberry Pi 5; configure ESP32-CAM WiFi; set up HiveMQ Cloud account and AWS account | All members | None (parallel) |
| 2 | Apr 14 – Apr 20 | **Subsystem A (sensor):** RCWL-1601 sensor reading and distance calibration on ESP32-CAM | Yuan Cong | Week 1 complete |
| 2 | Apr 14 – Apr 20 | **Subsystem D+E:** Set up Mosquitto on Pi 5; ESP32-CAM ↔ Pi local MQTT publish/subscribe test; image-receiver HTTP service skeleton; OpenALPR install + smoke test on stock plate images; connect Pi to HiveMQ Cloud broker | Nyx | Week 1 complete |
| 2 | Apr 14 – Apr 20 | **Subsystem F (Backend):** Flask project scaffold, database schema (users, bound plates, reservations, conflict log), basic REST API; deploy to AWS EC2 | Cheng | Week 1 complete |
| 3 | Apr 21 – Apr 27 | **Subsystem A (camera):** ESP32-CAM image capture on sensor falling-edge trigger; JPEG HTTP upload to Pi image-receiver | Yuan Cong | Week 2 Subsystem A sensor |
| 3 | Apr 21 – Apr 27 | **Subsystem A+D end-to-end:** Sensor data published to local MQTT → Pi forwards to cloud → Flask backend receives and stores; uploaded images flow into OpenALPR and produce `(plate, confidence)` results | Yuan Cong + Nyx | Week 2 Subsystem A + D + E |
| 3 | Apr 21 – Apr 27 | **Subsystem B:** Multi-state LED control (solid + blinking) and buzzer driver, driven by Pi control logic | Yuan Cong | Week 2 Subsystem A sensor |
| 3 | Apr 21 – Apr 27 | **Subsystem F (Frontend):** React.js project scaffold (Vite / CRA), component layout, real-time bay status display via Flask REST API; **plate-management UI** (add/remove/list) | Riya | Week 2 Backend API |
| 4 | Apr 28 – May 4 | **Subsystem C:** Per-bay state machine on Pi 5 — merges sensor + LPR + reservation; LPR-driven auto check-in; strong/weak conflict detection and buzzer activation; event emission over cloud MQTT | Nyx | Week 3 MQTT + LPR + LED/buzzer ready |
| 4 | Apr 28 – May 4 | **Subsystem F:** Account / plate management API; reservation logic (booking window, cancel, manual check-in fallback, breach + incident accounting); cloud MQTT publish of reservation + bound-plate list; push notifications (auto check-in, please check-in, strong/weak conflict) | Riya + Cheng | Week 3 Frontend + Backend |
| 5 | May 5 – May 11 | **Integration:** End-to-end flow across all three tiers — plate binding → reservation → cloud MQTT → Pi state machine → ESP32-CAM LED/buzzer; arrival → camera trigger → LPR → auto check-in OR strong/weak conflict + alarm → dashboard notifications | Nyx (lead) + All | Week 4 all subsystems |
| 6 | May 12 – May 18 | **Testing:** End-to-end testing of all scenarios (detect, reserve, cancel, auto/manual check-in, strong/weak conflict + alarm, no-show, breach accounting, LPR accuracy/latency, cloud disconnection resilience); bug fixes | Yuan Cong (lead) + All | Week 5 integration |
| 6 | May 12 – May 18 | **Physical build:** Assemble scale-model indoor parking lot (3 bays); mount sensors, cameras, LEDs, and buzzers; final sensor + LPR calibration (runs in parallel with testing) | All members | Week 5 integration |
| 7 | May 19 – May 22 | **Documentation and demo preparation:** Final report, demo script, presentation slides | All members | Week 6 testing + build |

### 7.1 Gantt Chart

```
Task / Sub-Team                       Wk1     Wk2     Wk3     Wk4     Wk5     Wk6     Wk7
                                      Apr7    Apr14   Apr21   Apr28   May5    May12   May19–22
─────────────────────────────────────────────────────────────────────────────────────────────
Environment Setup (All)               ██████
                                            ▲ M1
Sensor (A-sensor) — Yuan Cong                 ██████
Camera + Upload (A-cam) — Yuan Cong                   ██████
LED + Buzzer (B) — Yuan Cong                          ██████
MQTT + Gateway + OpenALPR (D+E) — Nyx         ██████  ██████
State Machine + LPR pipeline (C) — Nyx                        ██████
                                                                      ▲ M2
Backend + Plate Mgmt (F) — Cheng              ██████  ──────  ██████
Frontend + Plate UI (F) — Riya                        ██████  ██████
                                                                              ▲ M3
Integration — Nyx (lead) + All                                        ██████
Testing — Yuan Cong (lead) + All                                              ██████
Physical Build — All                                                          ██████
                                                                                     ▲ M4
Docs & Demo Prep — All                                                                ████
                                                                                          ▲ M5
─────────────────────────────────────────────────────────────────────────────────────────────
██████ = active work    ─────── = ongoing/support    ████ = partial week (4 days)    ▲ = milestone
```

### 7.2 Milestones

| Milestone | Week | Date | Deliverable |
|-----------|------|------|-------------|
| **M1:** Environment Ready | 1 | Apr 13 | All tools installed; ESP32-CAM connects to WiFi; OpenALPR runs a smoke test on stock plate images on the Pi 5; AWS and HiveMQ accounts created |
| **M2:** Subsystems Individually Working | 4 | May 4 | Sensor detects vehicles; ESP32-CAM captures and uploads images on trigger; OpenALPR returns plate strings; LEDs + buzzer cycle through all six states; state machine produces correct events (including auto check-in and strong/weak conflicts) under a scripted test harness; dashboard shows bays and supports plate management; reservation / manual check-in API functional |
| **M3:** End-to-End Integration Complete | 5 | May 11 | Full data flow works: plate binding → reservation → LED; arrival → camera trigger → LPR → auto check-in OR strong/weak conflict + alarm → dashboard notifications |
| **M4:** Testing Passed + Physical Demo Ready | 6 | May 18 | All metrics meet target thresholds (see §7.3); scale-model indoor parking lot (3 bays) assembled and calibrated |
| **M5:** Final Submission | 7 | May 22 | Report, demo video, presentation slides completed |

### 7.3 Evaluation and Testing Plan

Dedicated testing is scheduled in **Week 6**, with specific metrics and target thresholds:

**Sensor Accuracy and Reliability (Subsystem A):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **Detection Accuracy** | % of correct occupied/available classifications over N trials | ≥ 95% | Place/remove a scale-model vehicle 50 times; record sensor output vs ground truth |
| **False Alarm Rate (False Positive)** | % of times sensor reports "occupied" when bay is actually empty | ≤ 3% | Run sensor for 30 min on an empty bay; count false "occupied" readings |
| **Missed Detection Rate (False Negative)** | % of times sensor reports "available" when a vehicle is present | ≤ 2% | Place vehicle in bay for 30 min; count false "available" readings |
| **Detection Latency** | Time from vehicle arrival/departure to correct status update on ESP32 | < 3 seconds | Timestamp sensor trigger vs status change over 20 trials |

**Indicator & Alarm Reliability (Subsystem B):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **LED Correctness** | LED pattern (solid / blink colour) matches commanded state | 100% | Verify LED output across all six states × 20 cycles |
| **Buzzer Correctness** | Buzzer activates if and only if state is `Conflict` (strong or weak) | 100% | Drive each of the six states 20× via scripted harness; verify buzzer audio output matches expected on/off |

**Licence-Plate Recognition (Subsystem C — LPR pipeline):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **LPR Recognition Accuracy** | % of correct plate-string extractions under indoor lighting on a fixed test set | ≥ 90% | Run OpenALPR on 30 captured images covering both demo plates + 10 distractor plates; compare to ground truth |
| **LPR End-to-End Latency** | Time from camera trigger (sensor falling-edge) to LPR result available on Pi | < 5 seconds | Timestamp the trigger vs the OpenALPR result over 20 trials |
| **Plate Match Correctness** | Recognised plate is correctly classified as match / mismatch / low-confidence against the bound-plate list | 100% | Reserve under user A (plates P1, P2); present plates P1, P2, P_other, and a low-quality image 10× each; verify classification |

**State Machine & Conflict Detection (Subsystem C):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **State Transition Correctness** | System transitions to the correct state given sensor / LPR / reservation inputs | 100% | Scripted harness drives every transition in §5.4 diagram 10× each; verify resulting state |
| **Auto Check-in Correctness** | LPR-match events produce `auto_check_in` and transition the bay to `Reserved + Checked-in` without user action | 100% | Simulate 20 arrivals with bound plates; verify auto check-in fires and dashboard reflects it |
| **Strong-Evidence Conflict** | LPR plate-mismatch produces immediate `conflict_strong`, red blinking LED, and active buzzer; recognised plate logged | 100% | Simulate 10 arrivals with non-bound plates; verify alarm and evidence within 5 s of vehicle settling |
| **Weak-Evidence Conflict** | If LPR fails / low confidence and no manual check-in occurs within 5 min, bay transitions to `conflict_weak` with alarm | 100% | Simulate 10 arrivals with deliberately unreadable images and no manual check-in; verify alarm fires after grace |
| **No-show / Auto-release** | System auto-releases an unclaimed reservation after the arrival grace and records a breach | 100% | Create reservation, never arrive; verify auto-release and breach record after arrival + 5 min, 10 trials |

**Communication and End-to-End (Subsystems D + E + F):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **MQTT Message Delivery Rate** | % of messages successfully delivered (local + cloud) | ≥ 99% | Log published vs received messages over 200 message exchanges |
| **Image Upload Success Rate** | % of camera-triggered images successfully delivered to the Pi image-receiver | ≥ 99% | Trigger 100 captures; count successful uploads |
| **End-to-End Latency** | Time from user reservation click to LED state change | < 5 seconds | Timestamp reservation request on dashboard vs LED update; repeat 20 times |
| **Auto-Check-in Round-trip Latency** | Time from vehicle detection to dashboard "you're checked in" notification | < 8 seconds | Timestamp sensor falling-edge vs notification arrival; 20 trials |
| **Cloud Disconnection Resilience** | Local control (sensor + LPR → LED + buzzer) continues during cloud outage | Pass/Fail | Disconnect Pi from internet; verify local sensor → LPR → indicator still works; reconnect and verify cloud re-sync |
| **Dashboard Accuracy** | Dashboard bay state matches physical bay state | 100% | Compare dashboard display vs physical LED states across all 3 bays over 10 state changes |

**Reservation, Plate & Breach Logic (Subsystem F):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **Plate Management Correctness** | Add / remove / list plate operations produce correct DB state and the bound-plate list reaches the Pi for matching | 100% | Execute each operation 10×; verify DB and that the Pi's view updates within 5 s |
| **Reservation Correctness** | Reserve, cancel, manual check-in operations produce correct DB state, events, and LED transitions | 100% | Execute each operation 10 times; verify database state, events emitted, and LED state |
| **Breach + Incident Accounting** | Breach counter increments correctly per §5.5 rules; strong-evidence conflicts log as facility incidents (not user breaches); monthly ban triggers after threshold | 100% | Simulate each scenario (late cancel, no-show, weak conflict, strong conflict) 5× per user; verify counts, ban behaviour, and incident log |

> **Note:** If any metric falls below its target, the team will diagnose the root cause, adjust sensor thresholds or firmware / control logic, and re-test. Results will be documented in the final report.

### 7.4 Dependency Summary

- Subsystems A (sensor), D+E (gateway + OpenALPR), and F (cloud backend) start in parallel in Week 2.
- Subsystem A (camera + upload) depends on Subsystem A (sensor) being ready (the falling-edge trigger drives capture).
- Subsystem B depends on Subsystem A (sensor readings drive LED state) and Subsystem E (Pi relays commands).
- Subsystem C depends on Subsystem D+E (state machine consumes sensor + LPR + reservation events) and on Subsystem F (for reservation records and bound-plate lists).
- Frontend depends on Backend API and cloud MQTT being ready; the plate-management UI depends on the corresponding backend endpoints.
- Integration (Week 5) requires all three tiers (cloud, gateway with LPR, devices) to be individually functional.
- Evaluation & Testing and Physical Build (both Week 6) run in parallel; testing results inform final hardware and LPR-threshold calibration.
- Documentation & Demo Prep (Week 7, May 19–22) requires testing and build to be complete by May 18.

---

## 8. Hardware Required

Budget: **$100 AUD** (excluding items available at UWA). Cloud services (AWS free tier, HiveMQ Cloud free tier) are used at no cost.

| S.Nr | Item | Description | Available at UWA (Yes/No) | Cost (AUD) | Web Address | Delivery Time |
|------|------|-------------|--------------------------|------------|-------------|---------------|
| 1 | XIAO ESP32S3 Sense (with camera) (×3) | Seeed Studio XIAO ESP32S3 Sense - 2.4GHz Wi-Fi, BLE 5.0, OV2640 camera sensor, digital microphone, 8MB PSRAM, 8MB FLASH, battery charge supported, rich Interface, IoT, embedded ML | Yes | $13.90 × 3 | [Seeed Studio](https://www.seeedstudio.com/XIAO-ESP32S3-Sense-p-5639.html) | — |
| 2 | Raspberry Pi 5 (16 GB) (×1) | Edge gateway running Mosquitto MQTT broker, image-receiver HTTP service, OpenALPR licence-plate recognition, and the per-bay state-machine control service. The 16 GB RAM and Cortex-A76 cores comfortably support OpenALPR alongside the broker and control loop. Confirmed available with technician. | Yes | $497.84 × 1 | [Core Electronics](https://core-electronics.com.au/raspberry-pi-5-model-b-16gb.html) | — |
| 3 | Ultrasonic Sensor Module (×3) | RCWL-1601 Ultrasonic Distance Sensor (3–5V). Range 2–450 cm. One per bay for vehicle detection and camera-trigger source. | Yes | $2.70 × 3 | [Core Electronics](https://core-electronics.com.au/33v-ultrasonic-distance-sensor.html) | — |
| 4 | 5mm LEDs — Red, Green, Yellow (×3 sets) | 5mm LED Kit 500pcs (100x Red Green Blue Yellow White) used as the source of the red, green, and yellow indicators for the three-bay prototype. | Yes | $19.95 × 1 kit | [Core Electronics](https://core-electronics.com.au/5mm-led-kit-500pcs-100x-red-green-blue-yellow-white.html) | — |
| 5 | Piezo Buzzer (×3) | Buzzer 5V - Breadboard friendly | Yes | N/A (the product in the hardware-list Excel link has expired, so no live price is available from that linked page) | [Core Electronics](https://core-electronics.com.au/buzzer-5v-breadboard-friendly.html) | — |
| 6 | Breadboard (×3) | 830-point solderless breadboard for prototyping each node. | Yes | $3.95 × 3 | [Core Electronics](https://core-electronics.com.au/solderless-breadboard-830-tie-point-zy-102.html) | — |
| 7 | Jumper Wires Kit | Male-to-male and male-to-female jumper leads for wiring. Multiple types available in lab. | Yes | $3.20 × 1 pack | [Core Electronics](https://core-electronics.com.au/male-to-female-dupont-line-40-pin-10cm-24awg.html) | — |

**Cloud Services (No Cost):**

| Service | Purpose | Cost |
|---------|---------|------|
| AWS EC2 (free tier) | Host Flask backend and dashboard | $0.00 (12-month free tier) |
| HiveMQ Cloud (free tier) | Cloud MQTT broker bridging Pi ↔ AWS | $0.00 (free up to 100 connections) |

**Cost Summary:**

| Category | Cost |
|----------|------|
| All hardware (sourced from UWA lab) | $0.00 |
| Cloud services | $0.00 |
| **Total to purchase** | **$0.00** |
| **Remaining budget** | **$100.00** |

> All hardware items are available from the UWA lab. The Pi 5 (16 GB) was confirmed by the lab technician as available for this project. We will confirm borrowing/allocation of the remaining items with Lab Technician Andy Burrell (<andrew.burrell@uwa.edu.au>) before the project begins. The prototype is scoped to three bays for the demo; the architecture scales to N bays simply by adding more ESP32-CAM nodes.

---

## 9. References

[1] A. Khanna and R. Anand, "IoT based smart parking system," in *Proc. Int. Conf. Internet of Things and Applications (IOTA)*, Pune, India, 2016, pp. 266–270.

[2] D. Shoup, "Cruising for parking," *Transport Policy*, vol. 13, no. 6, pp. 479–486, 2006.

[3] L. Mainetti, L. Patrono, and R. Vergallo, "IDA-Pay: An innovative micro-payment system based on NFC technology for Android mobile devices," in *Proc. 22nd Int. Conf. Software, Telecommunications and Computer Networks (SoftCOM)*, 2014, pp. 104–108.

[4] G. Amato, F. Carrara, F. Falchi, C. Gennaro, C. Meghini, and C. Vairo, "Deep learning for decentralized parking lot occupancy detection," *Expert Systems with Applications*, vol. 72, pp. 327–334, 2017.

[5] Park Assist, "Smart parking guidance system," [Online]. Available: <https://www.parkassist.com>. [Accessed: Mar. 30, 2026].

[6] A. Banks, E. Briggs, K. Borgendale, and R. Gupta, "MQTT Version 5.0," OASIS Standard, Mar. 2019. [Online]. Available: <https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html>.

[7] Espressif Systems, "ESP32 Series Datasheet," v4.3, 2023. [Online]. Available: <https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf>.
