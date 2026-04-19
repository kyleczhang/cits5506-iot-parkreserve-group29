# Project Proposal CITS5506: Internet of Things

**Unit:** CITS5506 The Internet of Things | **Semester:** 1, 2026 | **Group:** 29

| Name | Student Number |
|------|---------------|
| Nyx Chen | 24290498 |
| Fahim Abrar | 24435912 |
| Riya Sakhiya | 24601375 |
| Yuan Cong Yuan | 25003723 |
| Cheng Zhang | 24878502 |

---

## 1. Name of Project

**ParkReserve: IoT-Based Parking Reservation with Automated Barrier Control**

---

## 2. Team Members

| Name | Student Number |
|------|---------------|
| Nyx Chen | 24290498 |
| Fahim Abrar | 24435912 |
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
- Without physical enforcement (e.g., barriers), reserved spots are frequently occupied by unauthorized vehicles, making reservations unreliable.

**Benefits of the Solution:**

- Real-time occupancy detection using IoT sensors eliminates the need for drivers to manually search, reducing average parking search time significantly.
- A web-based reservation system allows users to secure a spot before arrival, improving convenience and predictability.
- LED indicators (green = available, red = occupied, yellow = reserved) provide immediate, at-a-glance status visible from a distance.
- Automated barriers physically enforce reservations, preventing unauthorized occupation of reserved spots.

**Expected Impact:**

- Reduced traffic congestion and fuel consumption in parking areas. Studies estimate that 30% of urban traffic is caused by parking searches [2].
- Improved user satisfaction through a seamless reserve-and-park workflow.
- Demonstrates a practical, scalable three-tier IoT architecture (cloud backend, edge gateway, device layer) integrating sensing, actuation, wireless communication, and web-based user interaction. This architecture is applicable to university campuses, shopping centres, and hospital facilities.
- Remote access via a cloud-hosted dashboard means users can reserve a spot from anywhere with internet access, not just within the parking facility's local network.

---

## 4. Literature Review

Several IoT-based smart parking systems have been proposed in the literature. We review key works below and identify their strengths and gaps relative to our project.

**1. Sensor-Based Occupancy Detection Systems**

Khanna and Anand [1] proposed an IoT-based smart parking system using ultrasonic sensors connected to a Raspberry Pi, with data transmitted to a cloud server and displayed on a mobile app.

- **Strength:** Demonstrated real-time occupancy detection with reasonable accuracy.
- **Gap:** The system only monitors occupancy and does not support reservations or provide any physical enforcement mechanism, so a free spot may be taken before a driver arrives.

**2. IoT Smart Parking with Cloud Integration**

Mainetti et al. [3] developed an IoT-aware smart parking system using RFID and ZigBee sensor networks with a cloud-based backend.

- **Strength:** Comprehensive architecture integrating heterogeneous sensor networks with scalable cloud storage and analytics.
- **Gap:** Relies on RFID for vehicle identification, requiring each vehicle to carry a tag, which limits adoption. No barrier-based reservation enforcement is included.

**3. Computer Vision Approaches**

Amato et al. [4] used deep learning-based image classification to detect parking occupancy from overhead cameras.

- **Strength:** Does not require per-spot sensors, reducing hardware deployment cost at scale.
- **Gap:** Requires significant computational resources for image processing, is sensitive to lighting and weather conditions, and does not support reservation or physical actuation.

**4. Commercial Products: ParkAssist and Guidance Systems**

Commercial parking guidance systems such as ParkAssist use overhead sensors and LED indicators to guide drivers to available spots in multi-storey car parks [5].

- **Strength:** Deployed at scale in airports and shopping centres with proven reliability.
- **Gap:** These are proprietary, high-cost systems designed for large operators and not accessible for small-to-medium facilities. They provide guidance only, without reservation or barrier control.

**5. MQTT-Based IoT Communication**

The MQTT protocol [6] is widely adopted in IoT systems for lightweight publish/subscribe messaging. It is well-suited for constrained devices like ESP32 due to its low bandwidth overhead and support for Quality of Service (QoS) levels.

**Summary of Gaps Addressed by Our Project:**

| Feature | [1] Khanna | [3] Mainetti | [4] Amato | Commercial [5] | **Ours** |
|---------|-----------|-------------|----------|----------------|----------|
| Real-time detection | ✓ | ✓ | ✓ | ✓ | **✓** |
| Web/mobile dashboard | ✓ | ✓ | ✗ | ✓ | **✓** |
| Online reservation | ✗ | ✗ | ✗ | ✗ | **✓** |
| Physical barrier enforcement | ✗ | ✗ | ✗ | ✗ | **✓** |
| Visual LED indicators | ✗ | ✗ | ✗ | ✓ | **✓** |
| Low-cost / accessible | ✓ | ✗ | ✗ | ✗ | **✓** |

Our project uniquely combines real-time sensing, web-based reservation, LED visual feedback, and automated barrier actuation in a low-cost, ESP32-based system.

---

## 5. Methodology and System Design

### 5.1 Design Approach

The system uses a **three-tier architecture**: a cloud-hosted backend for business logic and user access, a Raspberry Pi edge gateway for local device control, and ESP32 sensor/actuator nodes at each parking spot.

1. **Sensor Integration:** Mount ultrasonic distance sensors (RCWL-1601) at each parking spot to continuously measure the distance to the ground. A vehicle presence is detected when the measured distance drops below a calibrated threshold.

2. **Status Indication:** Each spot has an RGB LED module that displays:
   - **Green**: spot is available
   - **Red**: spot is occupied (vehicle detected)
   - **Yellow**: spot is reserved via the web dashboard

3. **Barrier Actuation:** A servo motor at each spot controls a miniature barrier arm. When a reservation is made, the barrier rises (servo rotates to blocking position). When the reserved user arrives and checks in via the dashboard, the barrier lowers.

4. **Local Processing (ESP32):** Each ESP32 node reads its ultrasonic sensor, drives its RGB LED, and controls its servo motor. It connects to the Raspberry Pi gateway via local WiFi using MQTT, publishing occupancy status and subscribing to control commands.

5. **Edge Gateway (Raspberry Pi):** A Raspberry Pi on the same local network as the ESP32 nodes runs:
   - A local Mosquitto MQTT broker for fast, reliable communication with ESP32 devices.
   - A control logic service (Python) that processes sensor data from ESP32 nodes, drives LED/barrier commands locally, and bridges data to/from the cloud backend via a cloud MQTT broker (HiveMQ Cloud).
   - This ensures low-latency local control (sensor → LED/barrier response stays on the LAN) and continued operation even if the cloud connection is temporarily interrupted.

6. **Cloud Backend (AWS):** A Flask (Python) web application deployed on AWS EC2 that:
   - Connects to the cloud MQTT broker to receive spot status updates forwarded by the Raspberry Pi and to publish reservation commands.
   - Manages reservation business logic and persists state in a PostgreSQL database.
   - Serves the web dashboard over a public URL, accessible from anywhere with internet access.

7. **Web Dashboard:** A React.js application accessible remotely where users can:
   - View real-time occupancy status of all spots (color-coded map), with live updates via WebSocket or polling.
   - Reserve an available spot: command flows from cloud → Raspberry Pi → ESP32 (LED turns yellow, barrier rises).
   - Cancel a reservation (barrier lowers, LED returns to green).

8. **System Integration and Testing:** Connect all three tiers, test end-to-end flows (detection → local control → cloud sync → remote reservation → barrier actuation), and calibrate sensor thresholds.

### 5.2 System Architecture (Block Diagram)

```
╔═══════════════════════════════════════════════════════════════════════╗
║                      CLOUD TIER (AWS)                                 ║
║                                                                       ║
║  ┌────────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ║
║  │  Web Dashboard     │  │  Flask Backend    │  │  PostgreSQL /    │  ║
║  │  (React.js SPA)    │◄─┤  (Business Logic, │──┤  SQLite Database │  ║
║  │  Public URL        │  │   REST API)       │  │  (Reservations)  │  ║
║  └────────────────────┘  └────────┬─────────┘  └──────────────────┘  ║
║                                   │                                    ║
║                          ┌────────┴─────────┐                         ║
║                          │  Cloud MQTT       │                         ║
║                          │  Broker (HiveMQ)  │                         ║
║                          └────────┬──────────┘                         ║
╚═══════════════════════════════════╪════════════════════════════════════╝
                                    │ Internet (MQTT over TLS)
                                    │
╔═══════════════════════════════════╪════════════════════════════════════╗
║              EDGE GATEWAY (Raspberry Pi)                               ║
║                                   │                                    ║
║  ┌────────────────────────────────┴──────────────────────────────┐    ║
║  │  Control Logic Service (Python)                                │    ║
║  │  - Bridges local MQTT ↔ cloud MQTT                            │    ║
║  │  - Processes sensor data, drives LED/barrier commands locally  │    ║
║  │  - Forwards status to cloud; receives reservation commands     │    ║
║  └────────────────────────────────┬──────────────────────────────┘    ║
║                                   │                                    ║
║                          ┌────────┴──────────┐                         ║
║                          │  Local MQTT Broker │                         ║
║                          │  (Mosquitto)       │                         ║
║                          └────────┬──────────┘                         ║
╚═══════════════════════════════════╪════════════════════════════════════╝
                                    │ Local WiFi (MQTT)
               ┌────────────────────┼────────────────────┐
               │                    │                     │
               ▼                    ▼                     ▼
       ┌──────────────┐    ┌──────────────┐      ┌──────────────┐
       │  ESP32 Node  │    │  ESP32 Node  │ ...  │  ESP32 Node  │
       │   (Spot 1)   │    │   (Spot 2)   │      │   (Spot N)   │
       │              │    │              │      │              │
       │ ┌──────────┐ │    │ ┌──────────┐ │      │ ┌──────────┐ │
       │ │ HC-SR04  │ │    │ │ HC-SR04  │ │      │ │ HC-SR04  │ │
       │ │ Sensor   │ │    │ │ Sensor   │ │      │ │ Sensor   │ │
       │ └──────────┘ │    │ └──────────┘ │      │ └──────────┘ │
       │ ┌──────────┐ │    │ ┌──────────┐ │      │ ┌──────────┐ │
       │ │ RGB LED  │ │    │ │ RGB LED  │ │      │ │ RGB LED  │ │
       │ └──────────┘ │    │ └──────────┘ │      │ └──────────┘ │
       │ ┌──────────┐ │    │ ┌──────────┐ │      │ ┌──────────┐ │
       │ │ Servo    │ │    │ │ Servo    │ │      │ │ Servo    │ │
       │ │ Barrier  │ │    │ │ Barrier  │ │      │ │ Barrier  │ │
       │ └──────────┘ │    │ └──────────┘ │      │ └──────────┘ │
       └──────────────┘    └──────────────┘      └──────────────┘
```

**Data Flow:**

- **Uplink (Sensor → Cloud):** ESP32 reads HC-SR04 distance → publishes `occupied`/`available` to local MQTT topic `spot/<id>/status` → Raspberry Pi control service receives it, updates LED/barrier locally, and forwards status to cloud MQTT broker → Flask backend updates database and dashboard.
- **Downlink (Reservation → Actuator):** User reserves a spot on the web dashboard → Flask publishes command to cloud MQTT topic `spot/<id>/command` → Raspberry Pi receives command via cloud MQTT → Raspberry Pi publishes to local MQTT → ESP32 sets LED to yellow and raises servo barrier.

### 5.3 Subsystem Description

#### Subsystem A: Sensing Unit (Hardware + Firmware)

- **Hardware:** RCWL-1601 ultrasonic distance sensor per spot (3–5V compatible), connected to ESP32 GPIO pins (trigger + echo).
- **Software:** Arduino C++ firmware on ESP32. Periodically triggers ultrasonic pulse, measures echo time, calculates distance. If distance < threshold (e.g., 15 cm for a scale model), spot is occupied.
- **Output:** Publishes `occupied` or `available` status to the local MQTT broker (on Raspberry Pi) every 2 seconds.

#### Subsystem B: Indicator Unit (Hardware + Firmware)

- **Hardware:** Three individual 5mm LEDs (red, green, yellow) per spot, each driven through a 220Ω current-limiting resistor from an ESP32 GPIO pin.
- **Software:** LED color is set based on the current spot state held in the ESP32's local state machine:
    - `available` → green
    - `occupied` → red
    - `reserved` → yellow
- **Interdependence:** Depends on Subsystem A (sensor reading) and commands from Subsystem D (relayed by the Raspberry Pi gateway).

#### Subsystem C: Barrier Unit (Hardware + Firmware)

- **Hardware:** Feetech FS90 9g micro servo motor per spot. Servo arm acts as a miniature barrier gate.
- **Software:** On receiving a `reserve` command via local MQTT (from Raspberry Pi), the ESP32 rotates the servo to 90° (barrier up). On `cancel` or `check-in`, it rotates to 0° (barrier down).
- **Interdependence:** Triggered by Subsystem D (commands originating from cloud, relayed by Raspberry Pi). Must coordinate with Subsystem A: if a vehicle is detected while barrier is up, alert the gateway of a conflict.

#### Subsystem D: Communication Layer (Software)

- **Local MQTT (ESP32 ↔ Raspberry Pi):** Each ESP32 connects to the Mosquitto broker running on the Raspberry Pi over local WiFi.
    - `spot/<id>/status`: published by ESP32 (sensor data uplink)
    - `spot/<id>/command`: published by Raspberry Pi control service (actuator commands downlink)
- **Cloud MQTT (Raspberry Pi ↔ AWS):** The Raspberry Pi's control service connects to a cloud MQTT broker (HiveMQ Cloud) over TLS-encrypted internet connection.
    - `cloud/spot/<id>/status`: forwarded by Pi to cloud (status uplink)
    - `cloud/spot/<id>/command`: published by Flask backend (reservation commands downlink)
- **QoS:** Level 1 (at least once delivery) on both local and cloud MQTT to ensure commands are not lost.
- **Interdependence:** Bridges Subsystems A/B/C (ESP32 devices) with Subsystem F (cloud backend) through Subsystem E (Raspberry Pi gateway).

#### Subsystem E: Edge Gateway (Raspberry Pi, Hardware + Software)

- **Hardware:** Raspberry Pi 4 (or 3B+) connected to the same local WiFi network as ESP32 nodes, and to the internet.
- **Software:** Runs two services:
    1. **Mosquitto MQTT broker**: handles all local ESP32 communication.
    2. **Control logic service (Python)**: subscribes to local `spot/+/status` topics, processes sensor data, publishes LED/barrier commands to local `spot/<id>/command` topics, and bridges messages to/from the cloud MQTT broker.
- **Key benefit:** Local control loop (sensor → LED/barrier) operates with low latency on the LAN (~milliseconds). If the cloud connection drops, the Pi continues to manage spot detection and LED updates locally; reservations queue until connectivity resumes.
- **Interdependence:** Acts as the central bridge between the device layer (Subsystems A/B/C) and the cloud layer (Subsystem F).

#### Subsystem F: Cloud Backend and Dashboard (Software, AWS)

- **Backend:** Python Flask application deployed on AWS EC2. Connects to the cloud MQTT broker via the `paho-mqtt` library. Receives spot status updates, manages reservation business logic, and exposes REST API endpoints.
- **Frontend:** React.js dashboard. Displays a color-coded parking map with real-time updates (via WebSocket or periodic polling). Users can view availability and reserve/cancel spots from anywhere with internet access.
- **Database:** PostgreSQL (AWS RDS) or SQLite stores spot states, reservation records (user, spot, timestamp, status).
- **Interdependence:** Depends on Subsystem D (cloud MQTT) for real-time sensor data from the Raspberry Pi. Sends reservation commands back through Subsystem D → Subsystem E → ESP32 nodes.

---

## 6. Distribution of Work

| Name | Work Assigned | Reason for the Assignment |
|------|--------------|--------------------------|
|Riya Sakhiya | **Subsystem F (Frontend):** React.js parking map UI, real-time status updates, reservation/cancel interface | Experience in web development (React, HTML/CSS/JS); strong UI/UX design skills |
| Cheng Zhang | **Subsystem F (Backend):** Flask server, REST API, database, cloud MQTT client integration, AWS deployment | Background in Python and server-side programming; familiarity with cloud services |
| Fahim Abrar | **Subsystem A + B:** Ultrasonic sensor integration, RGB LED control, ESP32 firmware for sensing and display | Interest and coursework experience in embedded systems and Arduino programming |
| Nyx Chen | **Subsystem C + D + E:** Servo barrier control, MQTT communication setup (local + cloud brokers), Raspberry Pi gateway control logic | Experience with networking protocols and microcontroller programming |
| Yuan Cong Yuan | **System Integration + Testing:** End-to-end integration across all three tiers (cloud ↔ gateway ↔ devices), calibration, testing, and project documentation | Strong debugging and system-level thinking skills; coordinates across sub-teams |

> *Note: This is an initial distribution based on team discussion. Roles may be adjusted during the project as needed.*

---

## 7. Project Timeline

The project spans **7 weeks** from proposal submitted to final demonstration (due **May 22**). Tasks are assigned to sub-teams with sequential and parallel dependencies shown.

| Week | Dates | Task | Sub-Team | Dependencies |
|------|-------|------|----------|-------------|
| 1 | Apr 7 – Apr 13 | Environment setup: install Arduino IDE, Flask, Mosquitto on Raspberry Pi; configure ESP32 WiFi; set up HiveMQ Cloud account and AWS account | All members | None (parallel) |
| 2 | Apr 14 – Apr 20 | **Subsystem A:** RCWL-1601 sensor reading and distance calibration on ESP32 | Fahim | Week 1 complete |
| 2 | Apr 14 – Apr 20 | **Subsystem D+E:** Set up Mosquitto on Raspberry Pi; ESP32 ↔ Pi local MQTT publish/subscribe test; connect Pi to HiveMQ Cloud broker | Nyx | Week 1 complete |
| 2 | Apr 14 – Apr 20 | **Subsystem F (Backend):** Flask project scaffold, database schema, basic REST API; deploy to AWS EC2 | Cheng | Week 1 complete |
| 3 | Apr 21 – Apr 27 | **Subsystem A+D:** Sensor data published to local MQTT → Pi forwards to cloud → Flask backend receives and stores | Fahim + Nyx | Week 2 Subsystem A + D + E |
| 3 | Apr 21 – Apr 27 | **Subsystem B:** RGB LED control based on sensor state (driven by Pi control logic) | Fahim | Week 2 Subsystem A |
| 3 | Apr 21 – Apr 27 | **Subsystem F (Frontend):** React.js project scaffold (Create React App / Vite), component layout, real-time spot status display via Flask REST API | Riya | Week 2 Backend API |
| 4 | Apr 28 – May 4 | **Subsystem C:** Servo barrier control via local MQTT commands from Raspberry Pi | Nyx | Week 3 MQTT integration |
| 4 | Apr 28 – May 4 | **Subsystem F:** Reservation logic (reserve, cancel, check-in) in backend; React components for reservation flow (Axios calls, state management); cloud MQTT command publishing | Riya + Cheng | Week 3 Frontend + Backend |
| 5 | May 5 – May 11 | **Integration:** End-to-end flow across all three tiers: dashboard reservation → cloud MQTT → Pi → ESP32 barrier/LED; and sensor → Pi → cloud → dashboard | Yuan Cong + All | Week 4 all subsystems |
| 6 | May 12 – May 18 | **Testing:** End-to-end testing of all scenarios (detect, reserve, cancel, conflict handling, cloud disconnection resilience); bug fixes | Yuan Cong + All | Week 5 integration |
| 6 | May 12 – May 18 | **Physical build:** Assemble scale-model parking lot; mount sensors, LEDs, and servo barriers; final calibration (runs in parallel with testing) | All members | Week 5 integration |
| 7 | May 19 – May 22 | **Documentation and demo preparation:** Final report, demo script, presentation slides | All members | Week 6 testing + build |

### 7.1 Gantt Chart

```
Task / Sub-Team               Wk1     Wk2     Wk3     Wk4     Wk5     Wk6     Wk7
                              Apr7    Apr14   Apr21   Apr28   May5    May12   May19–22
─────────────────────────────────────────────────────────────────────────────────────
Environment Setup (All)       ██████
                                    ▲ M1
Sensor (A) — Fahim                    ██████  ───────
LED (B) — Fahim                               ██████
MQTT + Gateway (D+E) — Nyx            ██████  ██████
Barrier (C) — Nyx                                     ██████
                                                              ▲ M2
Backend (F) — Cheng                   ██████  ──────  ██████
Frontend (F) — Riya                           ██████  ██████
                                                                      ▲ M3
Integration — Yuan Cong + All                                 ██████
Evaluation & Testing — All                                            ██████
Physical Build — All                                                  ██████
                                                                             ▲ M4
Docs & Demo Prep — All                                                        ████
                                                                                  ▲ M5
─────────────────────────────────────────────────────────────────────────────────────
██████ = active work    ─────── = ongoing/support    ████ = partial week (4 days)    ▲ = milestone
```

### 7.2 Milestones

| Milestone | Week | Date | Deliverable |
|-----------|------|------|-------------|
| **M1:** Environment Ready | 1 | Apr 13 | All tools installed; ESP32 connects to WiFi; AWS and HiveMQ accounts created |
| **M2:** Subsystems Individually Working | 4 | May 4 | Sensor detects vehicles; LEDs change color; barrier raises/lowers; dashboard shows spots; reservation API functional |
| **M3:** End-to-End Integration Complete | 5 | May 11 | Full data flow works: sensor → Pi → cloud → dashboard; reservation → Pi → ESP32 barrier/LED |
| **M4:** Testing Passed + Physical Demo Ready | 6 | May 18 | All metrics meet target thresholds (see Section 7.3); scale-model parking lot assembled and calibrated |
| **M5:** Final Submission | 7 | May 22 | Report, demo video, presentation slides completed |

### 7.3 Evaluation and Testing Plan

Dedicated testing is scheduled in **Week 6**, with specific metrics and target thresholds:

**Sensor Accuracy and Reliability (Subsystem A):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **Detection Accuracy** | % of correct occupied/available classifications over N trials | ≥ 95% | Place/remove a scale-model vehicle 50 times; record sensor output vs ground truth |
| **False Alarm Rate (False Positive)** | % of times sensor reports "occupied" when spot is actually empty | ≤ 3% | Run sensor for 30 min on empty spot; count false "occupied" readings |
| **Missed Detection Rate (False Negative)** | % of times sensor reports "available" when a vehicle is present | ≤ 2% | Place vehicle in spot for 30 min; count false "available" readings |
| **Detection Latency** | Time from vehicle arrival/departure to correct status update on ESP32 | < 3 seconds | Timestamp sensor trigger vs status change over 20 trials |

**Actuator Reliability (Subsystems B + C):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **LED Correctness** | LED displays correct color for current spot state | 100% | Verify LED color across all state transitions (available → reserved → occupied → available) × 20 cycles |
| **Barrier Actuation Success** | Servo moves to correct position on command | 100% | Send reserve/cancel commands 30 times; verify barrier position |

**Communication and End-to-End (Subsystems D + E + F):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **MQTT Message Delivery Rate** | % of messages successfully delivered (local + cloud) | ≥ 99% | Log published vs received messages over 200 message exchanges |
| **End-to-End Latency** | Time from user reservation click to barrier raising | < 5 seconds | Timestamp reservation request on dashboard vs barrier movement; repeat 20 times |
| **Cloud Disconnection Resilience** | Local control (sensor → LED) continues during cloud outage | Pass/Fail | Disconnect Pi from internet; verify local sensor → LED still works; reconnect and verify cloud re-sync |
| **Dashboard Accuracy** | Dashboard spot status matches physical spot state | 100% | Compare dashboard display vs physical LED colors across all 3 spots over 10 state changes |

**Reservation Logic (Subsystem F):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **Reservation Correctness** | Reserve, cancel, and check-in operations produce correct state transitions | 100% | Execute each operation 10 times; verify database state, LED color, and barrier position |
| **Conflict Handling** | System correctly detects and alerts when an unreserved vehicle occupies a reserved spot | 100% | Place vehicle at reserved spot 10 times; verify conflict alert is generated |

> **Note:** If any metric falls below its target, the team will diagnose the root cause, adjust sensor thresholds or firmware logic, and re-test. Results will be documented in the final report.

### 7.4 Dependency Summary

- Subsystems A, D+E (gateway), and F (cloud backend) start in parallel in Week 2.
- Subsystem B depends on Subsystem A (sensor readings drive LED state) and Subsystem E (Pi relays commands).
- Subsystem C depends on Subsystem D+E (barrier controlled via MQTT commands from Pi).
- Frontend depends on Backend API and cloud MQTT being ready.
- Integration (Week 5) requires all three tiers (cloud, gateway, devices) to be individually functional.
- Evaluation & Testing and Physical Build (both Week 6) run in parallel; testing results inform final hardware calibration.
- Documentation & Demo Prep (Week 7, May 19–22) requires testing and build to be complete by May 18.

---

## 8. Hardware Required

Budget: **$100 AUD** (excluding items available at UWA). Cloud services (AWS free tier, HiveMQ Cloud free tier) are used at no cost.

| S.Nr | Item | Description | Available at UWA (Yes/No) | Cost (AUD) | Web Address | Delivery Time |
|------|------|-------------|--------------------------|------------|-------------|---------------|
| 1 | ESP32 Development Board (×3) | FireBeetle Board ESP32-E (Arduino Compatible). One per parking spot node. Lab stocks 37 units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/firebeetle-board-esp32-e-arduino-compatible.html) | — |
| 2 | Raspberry Pi 3B+ (×1) | Edge gateway running Mosquitto MQTT broker and control logic service. Requires WiFi and internet connectivity. Lab stocks 33 units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/raspberry-pi-3-model-b-plus.html) | — |
| 3 | Ultrasonic Sensor Module (×3) | RCWL-1601 Ultrasonic Distance Sensor (3–5V). Range 2–450 cm. One per spot for vehicle detection. Lab stocks 39 units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/33v-ultrasonic-distance-sensor.html) | — |
| 4 | Micro Servo Motor (×3) | Feetech FS90 9g Micro Servo (180°, 1.5 kg/cm). One per spot for barrier actuation. Lab stocks 15+ units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/feetech-fs90-1-5kgcm-micro-servo-9g.html) | — |
| 5 | 5mm LEDs — Red, Green, Yellow (×3 sets) | Individual 5mm LEDs (one red, one green, one yellow per spot) for status indication. Lab stocks 20+ of each colour. | Yes | $0.00 | — | — |
| 6 | Breadboard (×3) | 830-point solderless breadboard for prototyping each node. Lab stocks 27 units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/solderless-breadboard-830-tie-point-zy-102.html) | — |
| 7 | Jumper Wires Kit | Male-to-male and male-to-female jumper leads for wiring. Multiple types available in lab. | Yes | $0.00 | — | — |
| 8 | USB Micro-B Cables (×3) | For programming and powering ESP32 boards. Lab stocks 48 units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/usb-cable-type-a-to-micro-b-1m.html) | — |
| 9 | 220Ω Resistors (×9) | Current-limiting resistors for LED wiring (one per LED, 3 LEDs × 3 spots). | Yes | $0.00 | — | — |
| 10 | MicroSD Card (×1) | For Raspberry Pi OS. 16 GB or larger. | Yes | $0.00 | — | — |

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

> All hardware items are available from the UWA lab. We will confirm borrowing/allocation of all items with Lab Technician Andy Burrell (<andrew.burrell@uwa.edu.au>) before the project begins.

---

## 9. References

[1] A. Khanna and R. Anand, "IoT based smart parking system," in *Proc. Int. Conf. Internet of Things and Applications (IOTA)*, Pune, India, 2016, pp. 266–270.

[2] D. Shoup, "Cruising for parking," *Transport Policy*, vol. 13, no. 6, pp. 479–486, 2006.

[3] L. Mainetti, L. Patrono, and R. Vergallo, "IDA-Pay: An innovative micro-payment system based on NFC technology for Android mobile devices," in *Proc. 22nd Int. Conf. Software, Telecommunications and Computer Networks (SoftCOM)*, 2014, pp. 104–108.

[4] G. Amato, F. Carrara, F. Falchi, C. Gennaro, C. Meghini, and C. Vairo, "Deep learning for decentralized parking lot occupancy detection," *Expert Systems with Applications*, vol. 72, pp. 327–334, 2017.

[5] Park Assist, "Smart parking guidance system," [Online]. Available: <https://www.parkassist.com>. [Accessed: Mar. 30, 2026].

[6] A. Banks, E. Briggs, K. Borgendale, and R. Gupta, "MQTT Version 5.0," OASIS Standard, Mar. 2019. [Online]. Available: <https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html>.

[7] Espressif Systems, "ESP32 Series Datasheet," v4.3, 2023. [Online]. Available: <https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf>.
