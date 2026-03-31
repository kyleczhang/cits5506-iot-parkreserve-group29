# Project Proposal CITS5506: Internet of Things

---

## 1. Name of Project

**ParkReserve: IoT-Based Parking Reservation with Automated Barrier Control**

---

## 2. Group Number, Names and Student Numbers of Team Members

| Name | Student Number |
|------|---------------|
| Nyx Chen | 24290498 |
| Fahim Abrar | 24435912 |
| Riya Sakhiya | 24601375 |
| Yuan Cong Yuan | 25003723 |
| Cheng Zhang | 24878502 |

**Group Number:** 29

---

## 3. Why Do You Want to Do This Project? What Is the Problem? What Is the Benefit of Its Solution? What Is the Impact of the Solution?

**Problem:**

- In urban parking facilities, drivers spend an average of 15–20 minutes searching for available spots, contributing to traffic congestion, wasted fuel, and driver frustration [1].
- Existing parking lots typically lack real-time occupancy visibility — drivers must physically inspect each spot, which is inefficient and time-consuming.
- Even where real-time availability data exists, most systems do not support reservation — a driver may see a spot marked "available" on a dashboard but find it taken upon arrival.
- Without physical enforcement (e.g., barriers), reserved spots are frequently occupied by unauthorized vehicles, making reservations unreliable.

**Benefits of the Solution:**

- Real-time occupancy detection using IoT sensors eliminates the need for drivers to manually search, reducing average parking search time significantly.
- A web-based reservation system allows users to secure a spot before arrival, improving convenience and predictability.
- Colour-coded LED indicators (green = available, red = occupied, yellow = reserved) provide immediate, at-a-glance status visible from a distance.
- Automated barriers physically enforce reservations, preventing unauthorized occupation of reserved spots.

**Expected Impact:**

- Reduced traffic congestion and fuel consumption in parking areas — studies estimate that 30% of urban traffic is caused by parking searches [2].
- Improved user satisfaction through a seamless reserve-and-park workflow.
- Demonstrates a practical, scalable IoT system integrating sensing, actuation, wireless communication, and web-based user interaction — applicable to university campuses, shopping centres, and hospital facilities.

---

## 4. What Are the Existing Solutions? (Literature Review)

Several IoT-based smart parking systems have been proposed in the literature. We review key works below and identify their strengths and gaps relative to our project.

**1. Sensor-Based Occupancy Detection Systems**

Khanna and Anand [1] proposed an IoT-based smart parking system using ultrasonic sensors connected to a Raspberry Pi, with data transmitted to a cloud server and displayed on a mobile app. **Strength:** Demonstrated real-time occupancy detection with reasonable accuracy. **Gap:** The system only monitors occupancy — it does not support reservations or provide any physical enforcement mechanism, so a "free" spot may be taken before a driver arrives.

**2. IoT Smart Parking with Cloud Integration**

Mainetti et al. [3] developed an IoT-aware smart parking system using RFID and ZigBee sensor networks with a cloud-based backend. **Strength:** Comprehensive architecture integrating heterogeneous sensor networks with scalable cloud storage and analytics. **Gap:** Relies on RFID for vehicle identification, requiring each vehicle to carry a tag, which limits adoption. No barrier-based reservation enforcement is included.

**3. Computer Vision Approaches**

Amato et al. [4] used deep learning-based image classification to detect parking occupancy from overhead cameras. **Strength:** Does not require per-spot sensors, reducing hardware deployment cost at scale. **Gap:** Requires significant computational resources for image processing, is sensitive to lighting and weather conditions, and does not support reservation or physical actuation.

**4. Commercial Products — ParkAssist and Guidance Systems**

Commercial parking guidance systems such as ParkAssist use overhead sensors and LED indicators to guide drivers to available spots in multi-storey car parks [5]. **Strength:** Deployed at scale in airports and shopping centres with proven reliability. **Gap:** These are proprietary, high-cost systems designed for large operators — not accessible for small-to-medium facilities. They provide guidance only, without reservation or barrier control.

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

## 5. How Will You Do It? Methodology and System Design

### 5.1 Design Approach (Step-by-Step)

1. **Sensor Integration:** Mount ultrasonic distance sensors (HC-SR04) at each parking spot to continuously measure the distance to the ground. A vehicle presence is detected when the measured distance drops below a calibrated threshold.

2. **Status Indication:** Each spot has an RGB LED module that displays:
   - **Green** — spot is available
   - **Red** — spot is occupied (vehicle detected)
   - **Yellow** — spot is reserved via the web dashboard

3. **Barrier Actuation:** A servo motor at each reservable spot controls a miniature barrier arm. When a reservation is made, the barrier rises (servo rotates to blocking position). When the reserved user arrives and checks in via the dashboard, the barrier lowers.

4. **Local Processing (ESP32):** Each ESP32 node reads its ultrasonic sensor, drives its RGB LED, and controls its servo motor. It connects to the central server via WiFi using the MQTT protocol, publishing occupancy status and subscribing to reservation commands.

5. **Central Server (MQTT Broker + Web Backend):** A Raspberry Pi or laptop runs:
   - An MQTT broker (Mosquitto) to relay messages between ESP32 nodes and the backend.
   - A Flask (Python) web application that serves the dashboard, manages reservation logic, and stores spot states in an SQLite database.

6. **Web Dashboard:** A browser-based interface where users can:
   - View real-time occupancy status of all spots (colour-coded map).
   - Reserve an available spot (changes LED to yellow, raises barrier).
   - Cancel a reservation (barrier lowers, LED returns to green).

7. **System Integration and Testing:** Connect all subsystems, test end-to-end flows (detection → display → reservation → barrier actuation), and calibrate sensor thresholds.

### 5.2 System Architecture (Block Diagram)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WEB DASHBOARD (Flask)                        │
│   ┌──────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│   │ Real-Time Map │  │ Reservation Mgmt │  │ SQLite Database     │  │
│   └──────┬───────┘  └────────┬─────────┘  └──────────┬──────────┘  │
│          └───────────────────┼────────────────────────┘             │
│                              │ HTTP                                  │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                    MQTT BROKER (Mosquitto)                           │
│            Topics: spot/+/status, spot/+/command                     │
└──────┬───────────────────────┼──────────────────────────┬───────────┘
       │ WiFi/MQTT             │ WiFi/MQTT                │ WiFi/MQTT
       ▼                       ▼                          ▼
┌──────────────┐     ┌──────────────┐            ┌──────────────┐
│  ESP32 Node  │     │  ESP32 Node  │    ...     │  ESP32 Node  │
│   (Spot 1)   │     │   (Spot 2)   │            │   (Spot N)   │
│              │     │              │            │              │
│ ┌──────────┐ │     │ ┌──────────┐ │            │ ┌──────────┐ │
│ │ HC-SR04  │ │     │ │ HC-SR04  │ │            │ │ HC-SR04  │ │
│ │ Sensor   │ │     │ │ Sensor   │ │            │ │ Sensor   │ │
│ └──────────┘ │     │ └──────────┘ │            │ └──────────┘ │
│ ┌──────────┐ │     │ ┌──────────┐ │            │ ┌──────────┐ │
│ │ RGB LED  │ │     │ │ RGB LED  │ │            │ │ RGB LED  │ │
│ └──────────┘ │     │ └──────────┘ │            │ └──────────┘ │
│ ┌──────────┐ │     │ ┌──────────┐ │            │ ┌──────────┐ │
│ │ Servo    │ │     │ │ Servo    │ │            │ │ Servo    │ │
│ │ Barrier  │ │     │ │ Barrier  │ │            │ │ Barrier  │ │
│ └──────────┘ │     │ └──────────┘ │            │ └──────────┘ │
└──────────────┘     └──────────────┘            └──────────────┘
```

**Data Flow:**

- **Uplink (Sensor → Server):** ESP32 reads HC-SR04 distance → determines occupied/available → publishes to MQTT topic `spot/<id>/status`.
- **Downlink (Server → Actuator):** Web backend sends reservation command → MQTT topic `spot/<id>/command` → ESP32 sets LED to yellow and raises servo barrier.

### 5.3 Subsystem Description

#### Subsystem A: Sensing Unit (Hardware + Firmware)

- **Hardware:** HC-SR04 ultrasonic sensor per spot, connected to ESP32 GPIO pins (trigger + echo).
- **Software:** Arduino C++ firmware on ESP32. Periodically triggers ultrasonic pulse, measures echo time, calculates distance. If distance < threshold (e.g., 15 cm for a scale model), spot is occupied.
- **Output:** Publishes `occupied` or `available` status to MQTT broker every 2 seconds.

#### Subsystem B: Indicator Unit (Hardware + Firmware)

- **Hardware:** WS2812 RGB LED module per spot, driven by a single data pin on the ESP32.
- **Software:** LED colour is set based on the current spot state held in the ESP32's local state machine:
    - `available` → green
    - `occupied` → red
    - `reserved` → yellow
- **Interdependence:** Depends on Subsystem A (sensor reading) and Subsystem D (reservation commands from server).

#### Subsystem C: Barrier Unit (Hardware + Firmware)

- **Hardware:** SG90 micro servo motor per reservable spot. Servo arm acts as a miniature barrier gate.
- **Software:** On receiving a `reserve` command via MQTT, the ESP32 rotates the servo to 90° (barrier up). On `cancel` or `check-in`, it rotates to 0° (barrier down).
- **Interdependence:** Triggered by Subsystem D (server commands). Must coordinate with Subsystem A — if a vehicle is detected while barrier is up, alert the server of a conflict.

#### Subsystem D: Communication Layer (Software)

- **Protocol:** MQTT over WiFi. The ESP32 connects to the local WiFi network and communicates with the Mosquitto broker running on the server.
- **Topics:**
    - `spot/<id>/status` — published by ESP32 (sensor data uplink)
    - `spot/<id>/command` — published by server (reservation commands downlink)
- **QoS:** Level 1 (at least once delivery) to ensure reservation commands are not lost.
- **Interdependence:** Bridges Subsystems A/B/C (edge devices) with Subsystem E (server).

#### Subsystem E: Web Backend and Dashboard (Software)

- **Backend:** Python Flask application. Receives MQTT messages via the `paho-mqtt` library, updates spot states in an SQLite database, and exposes REST API endpoints for the frontend.
- **Frontend:** HTML/CSS/JavaScript dashboard served by Flask. Displays a colour-coded parking map with real-time updates (via periodic polling or WebSocket). Users can click a spot to reserve or cancel.
- **Database:** SQLite stores spot states, reservation records (user, spot, timestamp, status).
- **Interdependence:** Depends on Subsystem D (MQTT) for real-time sensor data. Sends commands back through Subsystem D to control Subsystems B and C.

---

## 6. Distribution of Work Among Team Members

| Name | Work Assigned | Reason for the Assignment |
|------|--------------|--------------------------|
| Nyx Chen | **Subsystem E (Frontend):** Web dashboard UI, real-time parking map, reservation interface | Experience in web development (HTML/CSS/JS); strong UI/UX design skills |
| Fahim Abrar | **Subsystem E (Backend):** Flask server, REST API, SQLite database, MQTT client integration | Background in Python and server-side programming |
| Riya Sakhiya | **Subsystem A + B:** Ultrasonic sensor integration, RGB LED control, ESP32 firmware for sensing and display | Interest and coursework experience in embedded systems and Arduino programming |
| Yuan Cong Yuan | **Subsystem C + D:** Servo barrier control, MQTT communication setup (broker + ESP32 client) | Experience with networking protocols and microcontroller programming |
| Cheng Zhang | **System Integration + Testing:** End-to-end integration of all subsystems, calibration, testing, and project documentation | Strong debugging and system-level thinking skills; coordinates across sub-teams |

> *Note: This is an initial distribution based on team discussion. Roles may be adjusted during the project as needed.*

---

## 7. Project Timeline

The project spans **8 weeks** from proposal approval to final demonstration. Tasks are assigned to sub-teams with sequential and parallel dependencies shown.

| Week | Dates | Task | Sub-Team | Dependencies |
|------|-------|------|----------|-------------|
| 1 | Apr 7 – Apr 13 | Environment setup: install Arduino IDE, Flask, Mosquitto; configure ESP32 WiFi connectivity | All members | None (parallel) |
| 2 | Apr 14 – Apr 20 | **Subsystem A:** HC-SR04 sensor reading and distance calibration on ESP32 | Riya | Week 1 complete |
| 2 | Apr 14 – Apr 20 | **Subsystem D:** Set up Mosquitto MQTT broker; ESP32 MQTT publish/subscribe test | Yuan Cong | Week 1 complete |
| 2 | Apr 14 – Apr 20 | **Subsystem E (Backend):** Flask project scaffold, SQLite schema, basic REST API | Fahim | Week 1 complete |
| 3 | Apr 21 – Apr 27 | **Subsystem A+D:** Sensor data published to MQTT and received by backend | Riya + Yuan Cong | Week 2 Subsystem A + D |
| 3 | Apr 21 – Apr 27 | **Subsystem B:** RGB LED control based on sensor state | Riya | Week 2 Subsystem A |
| 3 | Apr 21 – Apr 27 | **Subsystem E (Frontend):** Dashboard layout, real-time spot status display | Nyx | Week 2 Backend API |
| 4 | Apr 28 – May 4 | **Subsystem C:** Servo barrier control via MQTT commands | Yuan Cong | Week 3 MQTT integration |
| 4 | Apr 28 – May 4 | **Subsystem E:** Reservation logic (reserve, cancel, check-in) in backend + frontend | Nyx + Fahim | Week 3 Frontend + Backend |
| 5 | May 5 – May 11 | **Integration:** Connect dashboard reservation to ESP32 barrier/LED via MQTT end-to-end | Cheng + All | Week 4 all subsystems |
| 6 | May 12 – May 18 | **Testing:** End-to-end testing of all scenarios (detect, reserve, cancel, conflict handling); bug fixes | Cheng + All | Week 5 integration |
| 7 | May 19 – May 25 | **Physical build:** Assemble scale-model parking lot; mount sensors, LEDs, and servo barriers; final calibration | All members | Week 6 testing |
| 8 | May 26 – Jun 1 | **Documentation and demo preparation:** Final report, demo script, presentation slides | All members | Week 7 build complete |

**Dependency Summary:**

- Subsystems A, D, and E (Backend) start in parallel in Week 2.
- Subsystem B depends on Subsystem A (sensor readings drive LED state).
- Subsystem C depends on Subsystem D (barrier controlled via MQTT commands).
- Frontend depends on Backend API being ready.
- Integration (Week 5) requires all subsystems to be individually functional.

---

## 8. Hardware Required

Budget: **$50 AUD** (excluding items available at UWA).

| S.Nr | Item | Description | Available at UWA (Yes/No) | Cost (AUD) | Web Address | Delivery Time |
|------|------|-------------|--------------------------|------------|-------------|---------------|
| 1 | ESP32 Development Board (×3) | Duinotech ESP32 Main Board with WiFi and Bluetooth (XC3800). One per parking spot node. | Yes | $0.00 | [Jaycar XC3800](https://www.jaycar.com.au/duinotech-esp32-main-board-with-wi-fi-and-bluetooth/p/XC3800) | — |
| 2 | Ultrasonic Sensor Module (×3) | HC-SR04 compatible dual ultrasonic distance sensor (XC4442). Range 2–450 cm. One per spot for vehicle detection. | No | $9.95 × 3 = **$29.85** | [Jaycar XC4442](https://www.jaycar.com.au/arduino-compatible-dual-ultrasonic-sensor-module/p/XC4442) | 1–3 business days |
| 3 | Micro Servo Motor (×2) | 9G Micro Servo Motor (YM2758). Barrier actuation for reserved spots. | No | $11.95 × 2 = **$23.90** | [Jaycar YM2758](https://www.jaycar.com.au/arduino-compatible-9g-micro-servo-motor/p/YM2758) | 1–3 business days |
| 4 | WS2812 RGB LED Module (×3) | Addressable RGB LED (ZD0272). One per spot for status indication (green/red/yellow). | No | $4.95 × 3 = **$14.85** | [Jaycar ZD0272](https://www.jaycar.com.au/ws2812-rgb-led-module/p/ZD0272) | 1–3 business days |
| 5 | Breadboard (×3) | 400-point solderless breadboard for prototyping each node. | Yes | $0.00 | [Jaycar PB8820](https://www.jaycar.com.au/arduino-compatible-breadboard-with-400-tie-points/p/PB8820) | — |
| 6 | Jumper Wires Kit | Male-to-male and male-to-female jumper leads for wiring. | Yes | $0.00 | [Jaycar WC6027](https://www.jaycar.com.au/jumper-lead-mixed-pack-100-pieces/p/WC6027) | — |
| 7 | USB Micro-B Cables (×3) | For programming and powering ESP32 boards. | Yes | $0.00 | — | — |
| 8 | 220Ω Resistors (×10) | Current-limiting resistors (if needed for LED wiring). | Yes | $0.00 | — | — |

**Cost Summary:**

| Category | Cost |
|----------|------|
| Items available at UWA | $0.00 |
| Ultrasonic sensors (×3) | $29.85 |
| Servo motors (×2) | $23.90 |
| RGB LED modules (×3) | $14.85 |
| **Total to purchase** | **$68.60** |

> **Note:** Total exceeds the $50 budget by $18.60. To stay within budget, we propose the following options (to be confirmed with Lab Technician Andy Burrell at <andrew.burrell@uwa.edu.au>):
>
> - Check if ultrasonic sensors or servo motors are available at UWA — if 1 ultrasonic sensor is available, this saves $9.95.
> - Reduce the demo to 2 spots instead of 3 (saving one sensor + one LED = $14.90), bringing the total to **$53.70**.
> - Use individual coloured LEDs (red, green, yellow) instead of WS2812 RGB modules — basic LEDs are typically available at UWA, saving $14.85 and bringing the total to **$53.75** (or within budget with 2-spot reduction).
>
> We will finalise the hardware list after consulting Andy.

---

## 9. References

[1] A. Khanna and R. Anand, "IoT based smart parking system," in *Proc. Int. Conf. Internet of Things and Applications (IOTA)*, Pune, India, 2016, pp. 266–270.

[2] D. Shoup, "Cruising for parking," *Transport Policy*, vol. 13, no. 6, pp. 479–486, 2006.

[3] L. Mainetti, L. Patrono, and R. Vergallo, "IDA-Pay: An innovative micro-payment system based on NFC technology for Android mobile devices," in *Proc. 22nd Int. Conf. Software, Telecommunications and Computer Networks (SoftCOM)*, 2014, pp. 104–108.

[4] G. Amato, F. Carrara, F. Falchi, C. Gennaro, C. Meghini, and C. Vairo, "Deep learning for decentralized parking lot occupancy detection," *Expert Systems with Applications*, vol. 72, pp. 327–334, 2017.

[5] Park Assist, "Smart parking guidance system," [Online]. Available: <https://www.parkassist.com>. [Accessed: Mar. 30, 2026].

[6] A. Banks, E. Briggs, K. Borgendale, and R. Gupta, "MQTT Version 5.0," OASIS Standard, Mar. 2019. [Online]. Available: <https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html>.

[7] Espressif Systems, "ESP32 Series Datasheet," v4.3, 2023. [Online]. Available: <https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf>.
