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
- A web-based reservation system allows users to secure a bay before arrival, improving convenience and predictability.
- LED indicators with a multi-state colour/blink scheme (green = available, yellow = reserved, red = occupied, plus blinking variants for *pending check-in* and *conflict*) provide immediate at-a-glance status visible from a distance, and act as a soft social cue to respect reservations.
- Automated conflict detection identifies when an unauthorised vehicle occupies a reserved bay and alerts both the reserving user and facility staff, closing the gap that pure occupancy-only systems leave open.

**Expected Impact:**

- Reduced traffic congestion and fuel consumption in parking areas. Studies estimate that 30% of urban traffic is caused by parking searches [2].
- Improved user satisfaction through a seamless reserve-and-park workflow, with conflict detection giving reservations teeth without the cost and safety trade-offs of physical barriers (see §5.6).
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
| Reservation conflict detection | ✗ | ✗ | ✗ | ✗ | **✓** |
| Visual LED indicators | ✗ | ✗ | ✗ | ✓ | **✓** |
| Low-cost / accessible | ✓ | ✗ | ✗ | ✗ | **✓** |

Our project uniquely combines real-time sensing, web-based reservation, a multi-state LED visual-feedback scheme, and automated conflict detection with alerting in a low-cost, ESP32-based system.

---

## 5. Methodology and System Design

### 5.1 Design Approach

The system uses a **three-tier architecture**: a cloud-hosted backend for business logic and user access, a Raspberry Pi edge gateway for local device control and state management, and ESP32 sensor/indicator nodes at each parking bay.

The deployment target is an **indoor parking facility** (e.g., a multi-storey car park or undercover building car park). Indoor conditions provide controlled lighting, stable temperature, and protection from rain/debris, which yields more accurate and easier-to-calibrate ultrasonic distance measurement and reduces false positive/negative rates. The system also assumes a **casual-parking-allowed** facility: reservation is an optional convenience feature, not a mandatory access requirement, and users without a reservation can still park in any non-reserved bay.

1. **Sensor Integration:** Mount ultrasonic distance sensors (RCWL-1601) at each parking bay to continuously measure the distance to the ground. A vehicle presence is detected when the measured distance drops below a calibrated threshold.

2. **Status Indication:** Each bay has three LEDs (red, green, yellow) that display one of six states via solid or blinking patterns (see §5.4 for the full state machine):
   - **Green (solid)** — available
   - **Yellow (solid)** — reserved, not yet occupied
   - **Yellow (blinking)** — vehicle detected in a reserved bay, awaiting check-in confirmation
   - **Red (solid)** — occupied (casual user, or checked-in reservation holder)
   - **Red (blinking)** — conflict: reserved bay occupied but no valid check-in after grace period

3. **Reservation State Management:** Reservation is treated as an **informational/priority service**, not a physical enforcement mechanism (see §5.6 for the rationale). The Raspberry Pi gateway runs a per-bay state machine that merges sensor readings with reservation records to drive LED output and emit events (`pending_check_in`, `conflict_detected`, `no_show`) that the cloud backend uses to notify the reserving user and the facility administrator.

4. **Local Processing (ESP32):** Each ESP32 node reads its ultrasonic sensor and drives its LEDs based on state commands from the gateway. It connects to the Raspberry Pi gateway via local WiFi using MQTT, publishing occupancy status and subscribing to LED state commands.

5. **Edge Gateway (Raspberry Pi):** A Raspberry Pi on the same local network as the ESP32 nodes runs:
   - A local Mosquitto MQTT broker for fast, reliable communication with ESP32 devices.
   - A control logic service (Python) that owns the per-bay state machine, merges sensor data with reservation state, drives LED commands locally, and bridges events and commands to/from the cloud backend via a cloud MQTT broker (HiveMQ Cloud).
   - This ensures low-latency local control (sensor → LED response stays on the LAN) and continued operation even if the cloud connection is temporarily interrupted.

6. **Cloud Backend (AWS):** A Flask (Python) web application deployed on AWS EC2 that:
   - Connects to the cloud MQTT broker to receive bay status and events from the Raspberry Pi and to publish reservation updates.
   - Manages reservation business logic (booking window, grace period, breach accounting — see §5.5) and persists state in a PostgreSQL database.
   - Pushes notifications to the reserving user and facility administrators on `pending_check_in` and `conflict_detected` events.
   - Serves the web dashboard over a public URL, accessible from anywhere with internet access.

7. **Web Dashboard:** A React.js application accessible remotely where users can:
   - View real-time occupancy and reservation status of all bays (colour-coded map), with live updates via WebSocket or polling.
   - Reserve an available bay (booking window and breach rules per §5.5) or cancel a reservation.
   - Check-in on arrival (via QR code scan at the bay, with a manual "I'm here" button as fallback — see §5.5).
   - (Admin view) See conflict alerts with bay ID and timestamp.

8. **System Integration and Testing:** Connect all three tiers, test end-to-end flows (detection → state machine → cloud sync → dashboard notification; reservation → LED → check-in → conflict detection), and calibrate sensor thresholds.

### 5.2 System Architecture (Block Diagram)

```
╔═══════════════════════════════════════════════════════════════════════╗
║                      CLOUD TIER (AWS)                                 ║
║                                                                       ║
║  ┌────────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ║
║  │  Web Dashboard     │  │  Flask Backend    │  │  PostgreSQL /    │  ║
║  │  (React.js SPA)    │◄─┤  (Reservation,    │──┤  SQLite Database │  ║
║  │  Public URL        │  │  Notifications,   │  │ (Reservations,   │  ║
║  │                    │  │   REST API)       │  │  Breach Records) │  ║
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
║  │  - Per-bay state machine (merges sensor + reservation)         │    ║
║  │  - Bridges local MQTT ↔ cloud MQTT                            │    ║
║  │  - Emits pending_check_in / conflict_detected / no_show events │    ║
║  │  - Drives LED state commands locally                           │    ║
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
       │   (Bay 1)    │    │   (Bay 2)    │      │   (Bay N)    │
       │              │    │              │      │              │
       │ ┌──────────┐ │    │ ┌──────────┐ │      │ ┌──────────┐ │
       │ │ RCWL-    │ │    │ │ RCWL-    │ │      │ │ RCWL-    │ │
       │ │ 1601     │ │    │ │ 1601     │ │      │ │ 1601     │ │
       │ └──────────┘ │    │ └──────────┘ │      │ └──────────┘ │
       │ ┌──────────┐ │    │ ┌──────────┐ │      │ ┌──────────┐ │
       │ │ R/G/Y    │ │    │ │ R/G/Y    │ │      │ │ R/G/Y    │ │
       │ │ LEDs     │ │    │ │ LEDs     │ │      │ │ LEDs     │ │
       │ └──────────┘ │    │ └──────────┘ │      │ └──────────┘ │
       └──────────────┘    └──────────────┘      └──────────────┘
```

**Data Flow:**

- **Uplink (Sensor → Cloud):** ESP32 reads RCWL-1601 distance → publishes `occupied`/`available` to local MQTT topic `bay/<id>/status` → Raspberry Pi control service feeds the reading into the per-bay state machine, updates the LED command locally, and forwards the bay state and any derived events (`pending_check_in`, `conflict_detected`, `no_show`) to the cloud MQTT broker → Flask backend updates the database and dashboard and pushes notifications.
- **Downlink (Reservation → LED):** User reserves, cancels, or checks in on the web dashboard → Flask publishes a reservation update to cloud MQTT topic `bay/<id>/reservation` → Raspberry Pi state machine updates its view of reservation state → Pi publishes an LED state command to local MQTT topic `bay/<id>/led` → ESP32 drives the LEDs accordingly.

### 5.3 Subsystem Description

#### Subsystem A: Sensing Unit (Hardware + Firmware)

- **Hardware:** RCWL-1601 ultrasonic distance sensor per bay (3–5V compatible), connected to ESP32 GPIO pins (trigger + echo).
- **Software:** Arduino C++ firmware on ESP32. Periodically triggers an ultrasonic pulse, measures echo time, calculates distance. If distance < threshold (e.g., 15 cm for a scale model), the bay is occupied.
- **Output:** Publishes `occupied` or `available` status to the local MQTT broker (on Raspberry Pi) every 2 seconds.

#### Subsystem B: Indicator Unit (Hardware + Firmware)

- **Hardware:** Three individual 5mm LEDs (red, green, yellow) per bay, each driven through a 220Ω current-limiting resistor from an ESP32 GPIO pin.
- **Software:** LED output is set based on a state command received from the gateway:
    - `available` → green solid
    - `reserved` → yellow solid
    - `pending_check_in` → yellow blinking (~1 Hz)
    - `occupied` / `reserved_checked_in` → red solid
    - `conflict` → red blinking (~2 Hz)
- **Interdependence:** Depends on state commands from Subsystem C relayed via Subsystem D.

#### Subsystem C: Reservation State Management & Conflict Detection (Software)

- **Runs on:** The Raspberry Pi (primary control loop) with a mirrored state view in the cloud backend for dashboard and notifications.
- **Responsibility:** Owns the per-bay state machine defined in §5.4. For each bay, it combines the latest sensor reading (Subsystem A) with the current reservation record (held in the cloud DB, mirrored over cloud MQTT) to compute the next state, drive the appropriate LED command (Subsystem B), and emit events (`pending_check_in`, `check_in_confirmed`, `conflict_detected`, `no_show`) that flow back to Subsystem F for user/administrator notification and breach accounting.
- **Key logic:**
    - On `reservation_created`, set bay state to `reserved` (yellow solid).
    - If the sensor reports `occupied` while the bay is `reserved` and no check-in has occurred, transition to `pending_check_in` (yellow blinking) and emit `pending_check_in` so the backend can push a "please check in to confirm it's you" notification to the reserving user.
    - If the user confirms check-in within the check-in grace period (default 5 min from vehicle detection), transition to `reserved_checked_in` (red solid).
    - If that grace period expires without check-in, transition to `conflict` (red blinking) and emit `conflict_detected` for an admin alert.
    - If the user never arrives (bay remains empty at arrival time + 5 min), auto-release: transition to `available` and emit `no_show` so the backend can record a breach.
- **Interdependence:** Consumes Subsystem A (sensor status via local MQTT), drives Subsystem B (LED commands via local MQTT), and exchanges reservation state / events with Subsystem F via cloud MQTT.

#### Subsystem D: Communication Layer (Software)

- **Local MQTT (ESP32 ↔ Raspberry Pi):** Each ESP32 connects to the Mosquitto broker running on the Raspberry Pi over local WiFi.
    - `bay/<id>/status`: published by ESP32 (sensor data uplink)
    - `bay/<id>/led`: published by Raspberry Pi control service (LED state command downlink)
- **Cloud MQTT (Raspberry Pi ↔ AWS):** The Raspberry Pi's control service connects to a cloud MQTT broker (HiveMQ Cloud) over a TLS-encrypted internet connection.
    - `cloud/bay/<id>/state`: bay state forwarded by Pi to cloud (uplink)
    - `cloud/bay/<id>/event`: state-machine events (`pending_check_in`, `conflict_detected`, `no_show`, etc.) forwarded by Pi to cloud
    - `cloud/bay/<id>/reservation`: reservation updates published by Flask backend (downlink)
- **QoS:** Level 1 (at least once delivery) on both local and cloud MQTT to ensure commands and events are not lost.
- **Interdependence:** Bridges Subsystems A/B (ESP32 devices) with Subsystem F (cloud backend) through Subsystem E (Raspberry Pi gateway).

#### Subsystem E: Edge Gateway (Raspberry Pi, Hardware + Software)

- **Hardware:** Raspberry Pi 4 (or 3B+) connected to the same local WiFi network as ESP32 nodes, and to the internet.
- **Software:** Runs two services:
    1. **Mosquitto MQTT broker** — handles all local ESP32 communication.
    2. **Control logic service (Python)** — hosts Subsystem C (state machine + conflict detection), subscribes to local `bay/+/status` topics, publishes LED commands on `bay/<id>/led`, and bridges messages to/from the cloud MQTT broker.
- **Key benefit:** Local control loop (sensor → state machine → LED) operates with low latency on the LAN (~milliseconds). If the cloud connection drops, the Pi continues to manage bay detection and LED updates locally; reservation updates queue until connectivity resumes.
- **Interdependence:** Hosts Subsystem C. Acts as the central bridge between the device layer (Subsystems A/B) and the cloud layer (Subsystem F).

#### Subsystem F: Cloud Backend and Dashboard (Software, AWS)

- **Backend:** Python Flask application deployed on AWS EC2. Connects to the cloud MQTT broker via the `paho-mqtt` library. Receives bay state and state-machine events, manages reservation business logic (booking window, cancellation rules, breach accounting — §5.5), and exposes REST API endpoints.
- **Frontend:** React.js dashboard. Displays a colour-coded parking map with real-time updates (via WebSocket or periodic polling). Users can view availability, reserve/cancel bays, and perform check-in. An admin view surfaces conflict alerts.
- **Database:** PostgreSQL (AWS RDS) or SQLite stores bay states, reservation records (user, bay, arrival time, check-in time, status), and breach records.
- **Notifications:** On `pending_check_in` the backend pushes a notification to the reserving user ("a vehicle has been detected at your reserved bay — please check in to confirm"). On `conflict_detected` it alerts facility administrators.
- **Interdependence:** Depends on Subsystem D (cloud MQTT) for real-time bay state and events from the Raspberry Pi. Sends reservation updates back through Subsystem D → Subsystem E → Subsystem C.

### 5.4 Reservation State Machine

Each parking bay is represented by a state machine that merges real-time sensor input with reservation records. The six possible states and their LED representations are:

| State | Meaning | LED |
|-------|---------|-----|
| **Available** | No active reservation, no vehicle detected | Green solid |
| **Reserved** | Reservation active, no vehicle yet | Yellow solid |
| **Occupied (casual)** | Vehicle present, no active reservation | Red solid |
| **Pending Check-in** | Vehicle detected in reserved bay, awaiting user check-in | Yellow blinking |
| **Reserved + Checked-in** | Reserving user has confirmed presence | Red solid |
| **Conflict** | Reserved bay occupied but no check-in after grace period | Red blinking |

Key transitions (grace period defaults: 5 min after expected arrival time for auto-release; 5 min after vehicle detection for check-in):

```
                reserve                         vehicle_detected
 Available ──────────────▶ Reserved ─────────────────────────────▶ Pending Check-in
     ▲                        │                                           │
     │ cancel                 │ arrival_time + 5min                       │ check_in OK
     │ OR no-show             │ (bay empty): auto-release + breach        │
     │ (arrival+5min)         ▼                                           ▼
     │                    Available                           Reserved + Checked-in
     │                                                                    │
     │                                       vehicle_leaves               │
     └────────────────────────────────────────────────────────────────────┘

 Pending Check-in ─────────────────────────▶ Conflict  ───▶ Available
                    check-in grace expired            vehicle_leaves
                    (no check-in)

 Available ─────────────────▶ Occupied (casual) ─────────────▶ Available
                vehicle_detected                 vehicle_leaves
                (no reservation)
```

### 5.5 Reservation Rules and Check-in Mechanism

**Booking window.** Users may reserve a bay up to **one hour in advance**. This short window maximises bay utilisation and matches the typical "I'm about to drive there" use case; longer-horizon reservations are out of scope for this prototype.

**Check-in.** When the user arrives at the reserved bay, they perform a check-in to transition the bay to `Reserved + Checked-in`:

1. **Primary — QR code at the bay.** Each bay has a printed QR code encoding its bay ID. The user scans it from the dashboard, which authenticates them and calls the check-in endpoint. This is robust because the user physically has to be at the bay to scan.
2. **Fallback — manual button on the dashboard.** An "I'm here" button on the active reservation view, used if the QR code is damaged or unreadable.

**Grace periods.**

- *Arrival grace (no-show):* if the user has not arrived by `expected_arrival_time + 5 min` and the bay is still empty, the reservation is auto-released to `Available` and a breach is recorded.
- *Check-in grace:* once a vehicle is detected in a reserved bay, the reserving user has 5 min to confirm check-in before the bay transitions to `Conflict`.

**Breach accounting.**

| Event | Counted as breach? |
|-------|-------------------|
| User cancels **≥ 15 minutes** before expected arrival time | No |
| User cancels **< 15 minutes** before expected arrival time | Yes |
| User never arrives (no-show; bay empty at arrival + 5 min) | Yes |
| User's vehicle is detected but check-in never occurs within grace period (bay transitions to Conflict) | Yes |

> The 15-minute cancellation cutoff is measured against *expected arrival time*, not *booking time*, so even a late booking (e.g., reserving 20 min in advance) still offers a safe cancellation window.

**Sanction.** If a user accrues **more than two breaches in a rolling calendar month**, their reservation privilege is suspended for the remainder of the month. They can still park casually at non-reserved bays. Thresholds (breach count, grace periods, booking window) are configurable per facility; the values above are prototype defaults.

### 5.6 Design Decisions

Several design decisions were made during the proposal phase to better reflect real-world deployment constraints. We document them explicitly because they shape subsequent scope.

**Removal of physical barriers (servo-controlled gate arms).** An earlier version of the design included a per-bay servo barrier that would physically block unauthorised vehicles from entering a reserved bay. We chose to remove this for the following reasons:

- **Cost and maintenance.** Per-bay mechanical actuators significantly raise bill-of-materials cost and create ongoing maintenance load (motor wear, alignment drift).
- **Safety and liability.** Small barrier arms can damage vehicles or injure pedestrians if they fail-closed or close on an obstruction; the facility operator then carries liability.
- **Failure modes.** Mechanical or power failure either leaves the barrier stuck up (bay unusable) or stuck down (no enforcement) — both operationally disruptive.
- **Emergency access.** Emergency vehicles and pedestrians must always be able to pass freely; a physical barrier creates a hard constraint at odds with this.

Instead, the system treats reservations as an **informational/priority signal backed by detection and alerting**, which is consistent with how many real-world operators (e.g., shopping-centre "disabled" / "parent with pram" bays) handle soft enforcement.

**Indoor deployment scope.** The system is scoped for indoor parking facilities. Outdoor deployment is not a design target because:

- Outdoor ultrasonic readings suffer from temperature-induced sound-speed drift, wind-carried debris, and rain; calibration is harder and false positive/negative rates rise.
- Outdoor LEDs need weatherproofing and higher brightness to be visible in direct sunlight, which complicates the BoM.
- Indoor WiFi coverage is typically more consistent, simplifying networking assumptions.

**Payment out of scope.** The target facility is assumed to allow casual parking; reservation is an optional convenience, not a mandatory access requirement. Payment integration is not part of this prototype, but the system exposes a reservation / check-in / conflict event stream that an external payment system could consume.

**Enforcement boundary.** The system's role ends at *detecting* and *alerting*. Direct enforcement (boot-locks, fines, gate integration) is delegated to facility operators or to an external payment system (where the facility has one). Our scope is providing reliable evidence (bay state, timestamps, and optionally plate images — see §5.7) and timely alerts.

### 5.7 Optional Extensions

The following are **not in the core scope**. They are documented to show the architecture can accommodate them if time permits or in a follow-up.

**Licence-plate recognition (LPR).** A single overhead camera covering the demo bays could run plate recognition (e.g., OpenALPR or a cloud LPR API) to record the plate of any vehicle occupying a `Conflict`-state bay. Paired with a timestamped image, this would give facility staff evidence for a fine or for a payment-system-integrated penalty. The component would run on the Raspberry Pi (or on a second Pi dedicated to vision) and publish results over MQTT. Because LPR adds significant complexity and is not required for the core reserve / detect / alert flow, it is explicitly scoped as optional.

---

## 6. Distribution of Work

| Name | Primary Subsystem | Integration / Testing / Docs Role | Reason for the Assignment |
|------|-------------------|-----------------------------------|---------------------------|
| Yuan Cong Yuan | **Subsystem A + B:** Ultrasonic sensor integration, multi-state LED control (including blinking patterns), ESP32 firmware for sensing and display | **Device-level testing lead:** sensor calibration, full six-state LED coverage, hardware ↔ firmware bring-up; also compiles final report and demo script | Strong debugging and system-level thinking skills; device layer (A+B) is tightly coupled (LED state derives from sensor readings) so a single owner is more efficient than two |
| Nyx Chen | **Subsystem C + D + E:** Per-bay reservation state machine and conflict-detection service on the Raspberry Pi, MQTT communication setup (local + cloud brokers), edge gateway control logic | **Cross-tier integration lead:** owns end-to-end data-flow bring-up across device ↔ gateway ↔ cloud (natural fit since C+D+E already sits in the middle) | Experience with networking protocols, state-machine design, and microcontroller programming |
| Cheng Zhang | **Subsystem F (Backend):** Flask server, REST API, reservation business logic (booking window, breach accounting, push notifications), database, cloud MQTT client integration, AWS deployment | Backend unit/integration tests; API and deployment documentation | Background in Python and server-side programming; familiarity with cloud services |
| Riya Sakhiya | **Subsystem F (Frontend):** React.js parking map UI, real-time status updates, reservation / cancel / check-in interface (including QR scan flow) | Frontend unit tests; UI/UX documentation and demo screen captures | Experience in web development (React, HTML/CSS/JS); strong UI/UX design skills |

> *Note: This is an initial distribution based on team discussion. Week 5 integration, Week 6 end-to-end testing, and Week 7 demo preparation are shared responsibilities across all members, coordinated by the two integration/testing leads above. Roles may be adjusted during the project as needed.*

---

## 7. Project Timeline

The project spans **7 weeks** from proposal submission to final demonstration (due **May 22**). Tasks are assigned to sub-teams with sequential and parallel dependencies shown.

| Week | Dates | Task | Sub-Team | Dependencies |
|------|-------|------|----------|-------------|
| 1 | Apr 7 – Apr 13 | Environment setup: install Arduino IDE, Flask, Mosquitto on Raspberry Pi; configure ESP32 WiFi; set up HiveMQ Cloud account and AWS account | All members | None (parallel) |
| 2 | Apr 14 – Apr 20 | **Subsystem A:** RCWL-1601 sensor reading and distance calibration on ESP32 | Yuan Cong | Week 1 complete |
| 2 | Apr 14 – Apr 20 | **Subsystem D+E:** Set up Mosquitto on Raspberry Pi; ESP32 ↔ Pi local MQTT publish/subscribe test; connect Pi to HiveMQ Cloud broker | Nyx | Week 1 complete |
| 2 | Apr 14 – Apr 20 | **Subsystem F (Backend):** Flask project scaffold, database schema, basic REST API; deploy to AWS EC2 | Cheng | Week 1 complete |
| 3 | Apr 21 – Apr 27 | **Subsystem A+D:** Sensor data published to local MQTT → Pi forwards to cloud → Flask backend receives and stores | Yuan Cong + Nyx | Week 2 Subsystem A + D + E |
| 3 | Apr 21 – Apr 27 | **Subsystem B:** Multi-state LED control (solid + blinking patterns) driven by Pi control logic | Yuan Cong | Week 2 Subsystem A |
| 3 | Apr 21 – Apr 27 | **Subsystem F (Frontend):** React.js project scaffold (Vite / CRA), component layout, real-time bay status display via Flask REST API | Riya | Week 2 Backend API |
| 4 | Apr 28 – May 4 | **Subsystem C:** Per-bay state machine + conflict detection logic on Raspberry Pi; event emission over cloud MQTT | Nyx | Week 3 MQTT integration |
| 4 | Apr 28 – May 4 | **Subsystem F:** Reservation logic (booking window, cancel, check-in, breach accounting) in backend; React components for reservation / check-in flow (including QR scan); cloud MQTT command publishing; push notifications | Riya + Cheng | Week 3 Frontend + Backend |
| 5 | May 5 – May 11 | **Integration:** End-to-end flow across all three tiers — dashboard reservation → cloud MQTT → Pi state machine → ESP32 LED; sensor → state machine → cloud events → dashboard notifications | Nyx (lead) + All | Week 4 all subsystems |
| 6 | May 12 – May 18 | **Testing:** End-to-end testing of all scenarios (detect, reserve, cancel, check-in, conflict handling, breach accounting, cloud disconnection resilience); bug fixes | Yuan Cong (lead) + All | Week 5 integration |
| 6 | May 12 – May 18 | **Physical build:** Assemble scale-model indoor parking lot; mount sensors and LEDs; final calibration (runs in parallel with testing) | All members | Week 5 integration |
| 7 | May 19 – May 22 | **Documentation and demo preparation:** Final report, demo script, presentation slides | All members | Week 6 testing + build |

### 7.1 Gantt Chart

```
Task / Sub-Team               Wk1     Wk2     Wk3     Wk4     Wk5     Wk6     Wk7
                              Apr7    Apr14   Apr21   Apr28   May5    May12   May19–22
─────────────────────────────────────────────────────────────────────────────────────
Environment Setup (All)       ██████
                                    ▲ M1
Sensor (A) — Yuan Cong                ██████  ───────
LED (B) — Yuan Cong                           ██████
MQTT + Gateway (D+E) — Nyx            ██████  ██████
State Machine (C) — Nyx                               ██████
                                                              ▲ M2
Backend (F) — Cheng                   ██████  ──────  ██████
Frontend (F) — Riya                           ██████  ██████
                                                                      ▲ M3
Integration — Nyx (lead) + All                                ██████
Testing — Yuan Cong (lead) + All                                      ██████
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
| **M2:** Subsystems Individually Working | 4 | May 4 | Sensor detects vehicles; LEDs cycle through all six states; state machine produces correct events under a scripted test harness; dashboard shows bays; reservation / check-in API functional |
| **M3:** End-to-End Integration Complete | 5 | May 11 | Full data flow works: sensor → state machine → cloud events → dashboard notifications; reservation + check-in → LED state changes |
| **M4:** Testing Passed + Physical Demo Ready | 6 | May 18 | All metrics meet target thresholds (see §7.3); scale-model indoor parking lot assembled and calibrated |
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

**Indicator Reliability (Subsystem B):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **LED Correctness** | LED pattern (solid / blink colour) matches commanded state | 100% | Verify LED output across all six states × 20 cycles |

**State Machine & Conflict Detection (Subsystem C):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **State Transition Correctness** | System transitions to the correct state given sensor/reservation inputs | 100% | Scripted harness drives every transition in §5.4 diagram 10× each; verify resulting state |
| **Conflict Detection** | System correctly identifies conflict and emits `conflict_detected` when a reserved bay is occupied without a valid check-in | 100% | Simulate unauthorised occupancy on a reserved bay 10 times; verify conflict event + admin alert |
| **No-show / Auto-release** | System auto-releases an unclaimed reservation after the arrival grace and records a breach | 100% | Create reservation, never arrive; verify auto-release and breach record after arrival + 5 min, 10 trials |

**Communication and End-to-End (Subsystems D + E + F):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **MQTT Message Delivery Rate** | % of messages successfully delivered (local + cloud) | ≥ 99% | Log published vs received messages over 200 message exchanges |
| **End-to-End Latency** | Time from user reservation click to LED state change | < 5 seconds | Timestamp reservation request on dashboard vs LED update; repeat 20 times |
| **Cloud Disconnection Resilience** | Local control (sensor → LED) continues during cloud outage | Pass/Fail | Disconnect Pi from internet; verify local sensor → LED still works; reconnect and verify cloud re-sync |
| **Dashboard Accuracy** | Dashboard bay state matches physical bay state | 100% | Compare dashboard display vs physical LED states across all 3 bays over 10 state changes |

**Reservation Logic (Subsystem F):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **Reservation Correctness** | Reserve, cancel, and check-in operations produce correct DB state, events, and LED transitions | 100% | Execute each operation 10 times; verify database state, events emitted, and LED state |
| **Breach Accounting** | Breach counter increments correctly per §5.5 rules; monthly ban triggers after threshold | 100% | Simulate each breach scenario (late cancel, no-show, never-check-in) 5× per user; verify counts and ban behaviour |

> **Note:** If any metric falls below its target, the team will diagnose the root cause, adjust sensor thresholds or firmware / control logic, and re-test. Results will be documented in the final report.

### 7.4 Dependency Summary

- Subsystems A, D+E (gateway), and F (cloud backend) start in parallel in Week 2.
- Subsystem B depends on Subsystem A (sensor readings drive LED state) and Subsystem E (Pi relays commands).
- Subsystem C depends on Subsystem D+E (state machine consumes sensor + reservation events via MQTT) and on Subsystem F (for reservation records).
- Frontend depends on Backend API and cloud MQTT being ready.
- Integration (Week 5) requires all three tiers (cloud, gateway, devices) to be individually functional.
- Evaluation & Testing and Physical Build (both Week 6) run in parallel; testing results inform final hardware calibration.
- Documentation & Demo Prep (Week 7, May 19–22) requires testing and build to be complete by May 18.

---

## 8. Hardware Required

Budget: **$100 AUD** (excluding items available at UWA). Cloud services (AWS free tier, HiveMQ Cloud free tier) are used at no cost.

| S.Nr | Item | Description | Available at UWA (Yes/No) | Cost (AUD) | Web Address | Delivery Time |
|------|------|-------------|--------------------------|------------|-------------|---------------|
| 1 | ESP32 Development Board (×3) | FireBeetle Board ESP32-E (Arduino Compatible). One per parking bay node. Lab stocks 37 units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/firebeetle-board-esp32-e-arduino-compatible.html) | — |
| 2 | Raspberry Pi 3B+ (×1) | Edge gateway running Mosquitto MQTT broker, control logic service, and per-bay state machine. Requires WiFi and internet connectivity. Lab stocks 33 units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/raspberry-pi-3-model-b-plus.html) | — |
| 3 | Ultrasonic Sensor Module (×3) | RCWL-1601 Ultrasonic Distance Sensor (3–5V). Range 2–450 cm. One per bay for vehicle detection. Lab stocks 39 units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/33v-ultrasonic-distance-sensor.html) | — |
| 4 | 5mm LEDs — Red, Green, Yellow (×3 sets) | Individual 5mm LEDs (one red, one green, one yellow per bay) for multi-state status indication including blinking patterns. Lab stocks 20+ of each colour. | Yes | $0.00 | — | — |
| 5 | Breadboard (×3) | 830-point solderless breadboard for prototyping each node. Lab stocks 27 units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/solderless-breadboard-830-tie-point-zy-102.html) | — |
| 6 | Jumper Wires Kit | Male-to-male and male-to-female jumper leads for wiring. Multiple types available in lab. | Yes | $0.00 | — | — |
| 7 | USB Micro-B Cables (×3) | For programming and powering ESP32 boards. Lab stocks 48 units. | Yes | $0.00 | [Core Electronics](https://core-electronics.com.au/usb-cable-type-a-to-micro-b-1m.html) | — |
| 8 | 220Ω Resistors (×9) | Current-limiting resistors for LED wiring (one per LED, 3 LEDs × 3 bays). | Yes | $0.00 | — | — |
| 9 | MicroSD Card (×1) | For Raspberry Pi OS. 16 GB or larger. | Yes | $0.00 | — | — |

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

> All hardware items are available from the UWA lab. We will confirm borrowing/allocation of all items with Lab Technician Andy Burrell (<andrew.burrell@uwa.edu.au>) before the project begins. If we pursue the optional LPR extension (§5.7), a single Raspberry Pi Camera Module could be borrowed from the lab at no additional cost.

---

## 9. References

[1] A. Khanna and R. Anand, "IoT based smart parking system," in *Proc. Int. Conf. Internet of Things and Applications (IOTA)*, Pune, India, 2016, pp. 266–270.

[2] D. Shoup, "Cruising for parking," *Transport Policy*, vol. 13, no. 6, pp. 479–486, 2006.

[3] L. Mainetti, L. Patrono, and R. Vergallo, "IDA-Pay: An innovative micro-payment system based on NFC technology for Android mobile devices," in *Proc. 22nd Int. Conf. Software, Telecommunications and Computer Networks (SoftCOM)*, 2014, pp. 104–108.

[4] G. Amato, F. Carrara, F. Falchi, C. Gennaro, C. Meghini, and C. Vairo, "Deep learning for decentralized parking lot occupancy detection," *Expert Systems with Applications*, vol. 72, pp. 327–334, 2017.

[5] Park Assist, "Smart parking guidance system," [Online]. Available: <https://www.parkassist.com>. [Accessed: Mar. 30, 2026].

[6] A. Banks, E. Briggs, K. Borgendale, and R. Gupta, "MQTT Version 5.0," OASIS Standard, Mar. 2019. [Online]. Available: <https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html>.

[7] Espressif Systems, "ESP32 Series Datasheet," v4.3, 2023. [Online]. Available: <https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf>.
