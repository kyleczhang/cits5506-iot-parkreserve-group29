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
- For **paid indoor facilities** specifically (shopping centres, hospitals, office towers, multi-storey car parks), reservation without financial commitment leaves the operator absorbing the cost of every no-show, late cancel, and conflict — a reserved bay sitting empty earns nothing, and existing systems do not translate misuse into a tangible cost. The result is poor utilisation and weak ROI on any "smart parking" investment.

**Benefits of the Solution:**

- Real-time occupancy detection using IoT sensors eliminates the need for drivers to manually search, reducing average parking search time significantly.
- A web-based reservation system allows users to secure a bay before arrival, improving convenience and predictability. Users bind one or more licence plates to their account; any bound plate counts as a valid match for their reservation.
- LED indicators with a multi-state colour/blink scheme (green = available, yellow = reserved, red = occupied, plus blinking variants for *pending check-in* and *conflict*) provide immediate at-a-glance status visible from a distance, and act as a soft social cue to respect reservations.
- Automatic licence-plate recognition (LPR) at each bay triggers when a vehicle arrives in a reserved bay; if the recognised plate matches a plate bound to the reserving user, the system performs check-in automatically without any user action.
- Plate-evidence conflict detection distinguishes between *strong evidence* (recognised plate does not belong to the reserving user) and *weak evidence* (LPR could not return a confident result and no manual check-in occurred within the grace period). Both cases raise a per-bay audible alarm in addition to LED indication and admin notification.
- **Reservation-bound deposit.** At booking, the user enters card details that are validated against an internal mock-bank database and held via a mock pre-authorization **deposit**. The deposit is purely a reservation-honour mechanism: on a normal session (check-in + exit) the deposit is released in full and the user is not charged anything by our system. The actual time-based parking fee is the facility's exit-side concern (gate / kiosk) and is **out of scope** for this prototype (see §5.6). On late cancel, no-show, or weak conflict, a configurable penalty is captured from the deposit and the remainder released; on a strong-evidence conflict the reserving user is treated as a victim and the deposit is refunded in full. This converts every reservation from a soft promise into a financial commitment without us having to build a parking-billing system. The payment provider is *mocked* in the prototype — see §5.6 for the rationale and the production-deployment caveat.

**Expected Impact:**

- Reduced traffic congestion and fuel consumption in parking areas. Studies estimate that 30% of urban traffic is caused by parking searches [2].
- Improved user satisfaction through a seamless reserve-park-and-leave workflow where the typical case requires no manual check-in step. The combination of LPR-driven evidence and an audible alarm gives reservations real teeth while still avoiding the cost and safety trade-offs of physical barriers (see §5.6).
- **Direct operator ROI.** Every reservation that breaks the contract — late cancel, no-show, or weak conflict — produces a direct penalty capture rather than just an alert. Strong-evidence conflicts log the offending plate for out-of-band billing of the misusing party. This converts reservation enforcement into recovered revenue, which is what makes the system commercially viable for paid indoor facilities — without it the operator has no funding model for deploying reservation infrastructure on top of their existing parking-fee billing.
- Demonstrates a practical, scalable three-tier IoT architecture (cloud backend, edge gateway, device layer) integrating sensing, state management, wireless communication, web-based user interaction, and a payment-flow boundary. This architecture is applicable to paid indoor facilities such as shopping centres, hospitals, office towers, and multi-storey car parks.
- Remote access via a cloud-hosted dashboard means users can reserve, pay, and manage a bay from anywhere with internet access, not just within the parking facility's local network.

---

## 4. Literature Review

Several IoT-based smart parking systems have been proposed in the literature. We review key works below and identify their strengths and gaps relative to our project.

**1. Sensor-Based Occupancy Detection Systems**

Khanna and Anand [1] proposed an IoT-based smart parking system using ultrasonic sensors connected to a Raspberry Pi, with data transmitted to a cloud server and displayed on a mobile app.

- **Strength:** Demonstrated real-time occupancy detection with reasonable accuracy.
- **Gap:** The system only monitors occupancy and does not support reservations or detect misuse, so a free spot may be taken before a driver arrives.

**2. Smart-Parking Architectures and Design-Space Surveys**

Lin, Rivano and Le Mouël [3] surveyed smart-parking solutions across sensor technologies (ultrasonic, magnetometer, computer vision, RFID), communication stacks, and architectural patterns, mapping the trade-offs faced by any new deployment.

- **Strength:** Comprehensive coverage of the design space; cited widely as the canonical reference for sensor-and-architecture choices in IoT parking systems. Informs our sensor + comms stack directly (ultrasonic + MQTT + cloud bridge).
- **Gap:** As a survey it provides no reference implementation, and it explicitly identifies *reservation logic* and *misuse / conflict detection* as open areas where most fielded systems stop at occupancy display — the gap our project sets out to close.

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

| Feature | [1] Khanna | [3] Lin et al. | [4] Amato | Commercial [5] | **Ours** |
|---------|-----------|-------------|----------|----------------|----------|
| Real-time detection | ✓ | ✓ | ✓ | ✓ | **✓** |
| Web/mobile dashboard | ✓ | ✓ | ✗ | ✓ | **✓** |
| Online reservation | ✗ | ✗ | ✗ | ✗ | **✓** |
| Licence-plate recognition (auto check-in) | ✗ | ✗ | ✗ | ✗ | **✓** |
| Plate-evidence conflict detection (strong + weak) | ✗ | ✗ | ✗ | ✗ | **✓** |
| Visual LED indicators | ✗ | ✗ | ✗ | ✓ | **✓** |
| Audible per-bay alarm on misuse | ✗ | ✗ | ✗ | ✗ | **✓** |
| Reservation-bound deposit (pre-auth + automatic penalty / refund) | ✗ | ✗ | ✗ | partial (gate/kiosk only) | **✓** |
| Low-cost / accessible | ✓ | ✗ | ✗ | ✗ | **✓** |

Our project uniquely combines real-time sensing, web-based reservation with multi-plate accounts, automatic LPR-based check-in, a multi-state LED visual-feedback scheme, per-bay audible alarms tied to plate-evidence conflict detection, and reservation-bound payment with automatic penalty enforcement — all in a low-cost, ESP32-CAM based system. Commercial systems (e.g., ParkAssist) provide payment at the *facility* level (entry/exit gates and kiosks) but not at the *reservation* level, so a no-show under those systems still costs the operator a wasted bay; our pre-authorization model closes that gap.

---

## 5. Methodology and System Design

### 5.1 Design Approach

The system uses a **three-tier architecture**: a cloud-hosted backend for business logic, account/plate management, reservation-bound payment, and user access; a Raspberry Pi 5 edge gateway that hosts local device control, the per-bay state machine, and the on-device licence-plate recognition (LPR) service; and ESP32-CAM nodes at each parking bay that handle ultrasonic detection, multi-state LED + buzzer indication, and on-trigger image capture.

The deployment target is a **paid indoor parking facility** (e.g., a shopping-centre car park, a hospital or office-tower car park, or a multi-storey car park). Indoor conditions provide controlled lighting, stable temperature, and protection from rain/debris, which yields more accurate and easier-to-calibrate ultrasonic distance measurement, more reliable LPR recognition, and reduces false positive/negative rates. We target paid facilities because reservation only has clear ROI when it is backed by money: a free-parking facility has no incentive to deploy reservation infrastructure, but a paid operator gains directly from cutting no-shows and from automatically billing both normal usage and misuse. The system **focuses payment integration on the reservation path** — users entering a non-reserved (casual) bay are not charged by our system in the prototype; in production, casual parkers go through the facility's existing gate/kiosk payment path, which is out of scope (see §5.6).

The prototype demonstrates **three parking bays**, each instrumented with one ESP32-CAM node.

1. **Sensor Integration:** Mount an ultrasonic distance sensor (RCWL-1601) at each parking bay to continuously measure the distance to the ground. A vehicle presence is detected when the measured distance drops below a calibrated threshold. **For *reserved* bays only**, crossing the threshold also acts as a *trigger* for the on-board ESP32-CAM camera to capture an image of the vehicle's licence plate (proposal §5.5: LPR runs only when the bay state is `reserved`; casual occupancy never captures an image — see also the privacy framing in §5.6).

2. **Status Indication:** Each bay has three LEDs (red, green, yellow) plus an active buzzer. The LEDs display one of six states via solid or blinking patterns; the buzzer is on only in the `Conflict` state (see §5.4 for the full state machine):
   - **Green (solid)** — available
   - **Yellow (solid)** — reserved, not yet occupied
   - **Yellow (blinking)** — vehicle detected in a reserved bay, awaiting auto/manual check-in
   - **Red (solid)** — occupied (casual user, or checked-in reservation holder)
   - **Red (blinking) + buzzer** — conflict: reserved bay misused

3. **Plate Management and Account Binding:** Each user account binds one or more licence plates. A reservation does not pin a specific plate — *any* of the reserving user's currently bound plates counts as a valid match. Plate ownership is not verified in the prototype (plates are taken as user-supplied and assumed correct; see §5.6).

4. **Licence-Plate Recognition (LPR) and Auto Check-in:** When a vehicle is detected in a *reserved* bay, the ESP32-CAM captures a JPEG image and uploads it to the Raspberry Pi over HTTP. The Pi runs **OpenALPR** locally to extract the plate string. If the recognised plate (with confidence above the configured threshold) belongs to the reserving user's bound plates, the system performs check-in automatically. If the plate does not match, the system raises a *strong-evidence* conflict immediately. If LPR fails to return a confident result, the bay falls back to the manual check-in flow with the existing grace period (see §5.5).

5. **Reservation State Management:** Reservation is treated as an **informational/priority service** with active deterrence (alarm), not a physical enforcement mechanism (see §5.6 for the rationale). The Raspberry Pi gateway runs a per-bay state machine that merges sensor readings, LPR results, and reservation records to drive LED + buzzer output and emit events (`pending_check_in`, `auto_check_in`, `check_in_confirmed`, `conflict_strong`, `conflict_weak`, `no_show`) that the cloud backend uses to notify the reserving user and the facility administrator.

6. **Local Processing (ESP32-CAM):** Each ESP32-CAM node reads its ultrasonic sensor, drives its LEDs and buzzer based on state commands from the gateway, and on trigger captures and uploads a JPEG image to the Pi. It connects to the Raspberry Pi gateway via local WiFi using MQTT (for status/commands) and HTTP (for image upload).

7. **Edge Gateway (Raspberry Pi 5, 16 GB):** A Pi 5 on the same local network as the ESP32-CAM nodes runs:
   - A local Mosquitto MQTT broker for fast, reliable communication with ESP32-CAM devices.
   - A small image-receiver HTTP service that accepts captured JPEGs from the nodes.
   - **OpenALPR** for local licence-plate recognition.
   - A control logic service (Python) that owns the per-bay state machine, merges sensor data, LPR results, and reservation state, drives LED + buzzer commands locally, and bridges events and commands to/from the cloud backend via a cloud MQTT broker (HiveMQ Cloud).
   - This ensures low-latency local control (sensor → LPR → LED response stays on the LAN) and continued operation even if the cloud connection is temporarily interrupted.

8. **Cloud Backend (AWS):** A Flask (Python) web application deployed on AWS EC2 that:
   - Connects to the cloud MQTT broker to receive bay status, LPR results, and state-machine events from the Raspberry Pi and to publish reservation updates and the per-user bound-plate list.
   - Manages account/plate management and reservation business logic (booking window, grace period, fee + penalty capture — see §5.5), and persists state in a PostgreSQL database.
   - Hosts a **mock-payment service** that validates user-supplied card details against an internal mock-bank database, places a pre-authorization deposit hold at booking, **releases the full deposit on normal exit** (parking-fee billing is the facility's exit-side concern, out of scope — see §5.6), captures penalty fees on late-cancel / no-show / weak-conflict events (releasing the remainder), and refunds strong-conflict victims in full. The provider is mocked end-to-end inside the Flask process — see §5.6 for the rationale.
   - Pushes notifications to the reserving user (auto check-in success, please-check-in prompt, deposit-released receipt on completion, refund confirmation, penalty notice) and to facility administrators (strong/weak conflict alerts).
   - Serves the web dashboard over a public URL, accessible from anywhere with internet access.

9. **Web Dashboard:** A React.js application accessible remotely where users can:
   - View real-time occupancy and reservation status of all three bays (colour-coded map), with live updates via WebSocket or polling.
   - Manage their bound licence plates (add, remove, list).
   - Reserve an available bay (booking window, deposit + penalty rules per §5.5) by **completing a payment form** (mock card number, CVV, expiry, holder name). The form shows a clear "MOCK PAYMENT — DO NOT ENTER REAL CARD DETAILS" banner; on submit, the dashboard displays the pre-authorization confirmation (deposit held; will be released in full on a normal session, partially captured as a penalty on a contract breach, or refunded in full on a strong-conflict victim path — see §5.5).
   - Cancel a reservation, with the dashboard showing whether the cancel falls within the free window or will trigger a late-cancel penalty before the user confirms.
   - Manually check in on arrival as a fallback when LPR did not auto-resolve (via QR code scan at the bay, with a manual "I'm here" button as further fallback — see §5.5).
   - View their **transaction history** (deposit holds, releases, refunds, penalty captures) with per-reservation receipts.
   - (Admin view) See strong/weak conflict alerts with bay ID, plate evidence (if any), timestamp, and the resulting refund/penalty actions on the affected reservations.

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
║  │                    │  │  Notifications,     │  │  Payments,       │   ║
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
- **Responsibility:** Owns the per-bay state machine defined in §5.4. For each bay, it combines the latest sensor reading (Subsystem A), the latest LPR result (from the local OpenALPR service), and the current reservation record (with the reserving user's bound-plate list, held in the cloud DB and mirrored over cloud MQTT) to compute the next state, drive the appropriate LED + buzzer command (Subsystem B), and emit events (`auto_check_in`, `pending_check_in`, `check_in_confirmed`, `conflict_strong`, `conflict_weak`, `no_show`) that flow back to Subsystem F for notification, fee + penalty capture, and incident logging. The `check_in_confirmed` event is the Pi's echo of a successful manual (QR or button) check-in pushed down by the cloud — purely an audit acknowledgement so the cloud log and the Pi's local state stay aligned.
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
    - `cloud/bay/<id>/event`: state-machine events (`auto_check_in`, `pending_check_in`, `check_in_confirmed`, `conflict_strong`, `conflict_weak`, `no_show`) forwarded by Pi to cloud, including recognised plate string for conflict events
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

- **Backend:** Python Flask application deployed on AWS EC2. Connects to the cloud MQTT broker via the `paho-mqtt` library. Receives bay state, LPR-derived events, and conflict evidence; manages account / plate / reservation business logic (booking window, cancellation rules, deposit + penalty accounting — §5.5); exposes REST API endpoints.
- **Mock-payment service (module within Subsystem F):** Holds two internal tables — a *mock-bank database* (simulated card records: number, CVV, expiry, holder name, available balance) populated for the demo, and a *transactions* log (pre-auth deposits, releases, refunds, penalty captures). The interface mirrors a real payment gateway: `validate_card`, `preauthorize`, `release`, `charge_penalty`, `refund`. **The service intentionally does *not* expose a `capture` operation** — the prototype handles only the reservation-honour deposit; per-time parking-fee capture is the facility's exit-side billing system, which is out of scope (see §5.6). Every call is keyed by `(reservation_id, action)` so retries, sweeper-replayed events, and MQTT redeliveries cannot double-charge. Endpoints are not exposed to any external bank — everything runs in-process. This boundary lets the prototype run without real money while keeping the integration shape compatible with a future real-provider swap (see §5.6 and §5.7).
- **Frontend:** React.js dashboard. Displays a colour-coded parking map with real-time updates (via WebSocket or periodic polling). Users can manage their bound plates, view availability, reserve/cancel bays, complete a (mock) card-entry payment form at booking, view their transaction history, and perform manual check-in (QR or "I'm here" button) when LPR did not auto-resolve. An admin view surfaces strong/weak conflict alerts with plate evidence and the resulting refund/penalty actions.
- **Database:** PostgreSQL 16 (AWS RDS or EC2-colocated) stores users, bound plates, bay states, reservation records (user, bay, arrival time, check-in time, status, check-in mechanism, recognised plate when checked in via LPR), conflict log (bay, evidence plate, captured-image reference, timestamp), the mock-bank table, and the transactions log (one row per pre-auth / release / refund / penalty_capture, with idempotency key — there is no `capture` action because per-time billing is out of scope, see §5.6).
- **Notifications:** On `auto_check_in` the backend pushes a confirmation to the reserving user ("you're checked in at Bay X"). On `pending_check_in` it pushes a "vehicle detected — please check in" prompt. On a normal exit (deposit released in full) it pushes a "your deposit of $X.YZ has been released — see receipt" message. On a strong-conflict refund it pushes a "your reservation was disrupted — full refund issued" message. On a penalty capture it pushes a "penalty captured: …" notification. On `conflict_strong` / `conflict_weak` it alerts facility administrators (with the recognised plate string when available, plus the resulting refund/penalty action).
- **Interdependence:** Depends on Subsystem D (cloud MQTT) for real-time bay state and events from the Raspberry Pi. Sends reservation updates and bound-plate lists back through Subsystem D → Subsystem E → Subsystem C. The mock-payment service is invoked by the reservation business logic only — Subsystems A–E are payment-agnostic.

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
     │ OR no-show             │ (bay empty): auto-release + penalty       │ │              │
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
- **Financial outcome:** strong triggers a **full refund** of the reserving user's pre-auth hold (the user is a victim, not at fault) plus a *facility incident* log of the recognised plate; weak triggers a **weak-conflict penalty capture** against the reserving user (they could have manually checked in if it was them). See §5.5.

### 5.5 Reservation Rules and Check-in Mechanism

**Plate binding.** Each user account binds one or more licence plates (1–5 in the prototype). Plates are added or removed from the dashboard. Plate ownership is **not** verified in the prototype — the user-supplied plate string is taken as authoritative (see §5.6 for the rationale and the production-deployment caveat).

**Reservation matching policy.** A reservation does not pin a specific plate. *Any* of the reserving user's currently bound plates counts as a valid match for that reservation. This keeps the user flow simple — they don't need to specify which car they will arrive in — and accommodates same-day vehicle changes.

**Booking window.** Users may reserve a bay up to **one hour in advance**. This short window maximises bay utilisation and matches the typical "I'm about to drive there" use case; longer-horizon reservations are out of scope for this prototype.

**Payment flow (mock).** The backend's payment integration is **scoped to the reservation deposit only**. Per-minute parking-fee billing is the facility's exit-side concern (gate / kiosk) and is **out of scope** for this prototype — see §5.6. Reservation creation is gated on a successful card validation against the backend's mock-bank database. The flow is:

1. **At booking** — the user submits the reservation form together with mock card details (number, CVV, expiry, holder name). The backend `validate_card`s against the mock-bank table; on success it `preauthorize`s a deposit hold of $10 (the prototype default; sized to comfortably exceed the largest single penalty so a partial-penalty + remainder-release flow is always demonstrable). The reservation is only created if the hold succeeds. The held amount is decremented from the mock card's available balance and a `pre_auth` row is written to the transactions log.
2. **On normal exit** — when the bay state transitions from `Reserved + Checked-in` to `Available` (vehicle_leaves), the backend `release`s the **full** deposit back to the user's mock card and pushes a "deposit released" receipt. Our system does **not** charge anything for the parking session itself; that billing happens at the facility's exit gate / kiosk in production and is outside this prototype's scope.
3. **On cancel ≥ 15 min before expected arrival** — the backend `release`s the hold; the mock card balance is fully restored and no charge is recorded against the user.
4. **On late cancel, no-show, or weak conflict** — the backend `charge_penalty`s a flat penalty (defaults: late-cancel $5, no-show $10, weak-conflict $10) from the deposit, releases the remainder (which may be $0 when the penalty equals the deposit), and pushes a "penalty captured: …" notification.
5. **On strong-evidence conflict** — the reserving user is the victim. The backend `refund`s the deposit in full, restores the mock card balance, and pushes a "your reservation was disrupted — full refund issued" notification. The recognised plate (LPR evidence) is logged for the operator to bill / sanction the misusing party out-of-band; that out-of-band step is outside the prototype's scope.

> **Weak conflict followed by a late check-in.** If a user does a manual late check-in *after* the weak-conflict penalty has already been captured (proposal §5.5 alarm rules allow this), the reservation transitions back to `Reserved + Checked-in` and the conflict alarm clears, but the penalty is **not** refunded — the user's failure to verify within the grace stands. When the vehicle later leaves, the completion handler is a no-op for payment (the deposit is already gone) and the reservation is marked `COMPLETED`.

Every payment-service call is keyed by `(reservation_id, action)` so retries from MQTT redeliveries, sweeper-replayed events, or user double-clicks cannot double-charge. **Default values** (configurable per facility via `Settings`): pre-auth deposit $10; late-cancel penalty $5; no-show penalty $10; weak-conflict penalty $10. All amounts are AUD in the prototype.

**Check-in mechanisms (in order of preference).**

1. **Primary — automatic via LPR.** When a vehicle is detected in a reserved bay, the ESP32-CAM captures an image and the Pi runs OpenALPR. If the recognised plate (confidence ≥ threshold) is in the reserving user's bound-plate list, the bay automatically transitions to `Reserved + Checked-in`. **No user action is required in the typical case.** The user receives a confirmation notification.
2. **Fallback — QR code at the bay.** Each bay has a printed QR code encoding its bay ID. If LPR did not auto-resolve (failure, low confidence, dirty plate, etc.), the user scans the QR from the dashboard, which authenticates them and calls the check-in endpoint.
3. **Further fallback — manual "I'm here" button on the dashboard.** Used if the QR code is damaged or unreadable.

**Grace periods.**

- *Arrival grace (no-show):* if the user has not arrived by `expected_arrival_time + 5 min` and the bay is still empty, the reservation is auto-released to `Available` and a no-show penalty is captured against the held card (see "Fee + penalty schedule" below).
- *Check-in grace:* once a vehicle is detected in a reserved bay, the LPR auto-check-in attempt happens immediately. If LPR returns a confident *mismatch*, the bay enters `Conflict (strong)` straight away and the user is refunded. If LPR fails or returns low confidence, the reserving user has 5 min from vehicle detection to perform a manual check-in (QR or button) before the bay transitions to `Conflict (weak)` and a weak-conflict penalty is captured.

**Conflict alarm.** The per-bay buzzer is activated together with red blinking LEDs whenever the bay enters `Conflict`, regardless of whether the trigger was strong (plate mismatch) or weak (no check-in after grace). The alarm stops when the bay leaves `Conflict` — either the vehicle leaves (`vehicle_leaves`) or, in the weak case only, a late manual check-in succeeds. Strong-evidence conflicts cannot be cleared by manual check-in (the recognised plate is provably not the user's), and the bay must be cleared by the vehicle leaving (or an admin override).

**Penalty schedule.** All amounts are captured automatically from the pre-authorization deposit; the user does not perform a separate payment step at any point after booking. Per-minute parking-fee billing is the facility's exit-side responsibility and is out of scope (§5.6).

| Event | Action against the held card |
|-------|------------------------------|
| User cancels **≥ 15 minutes** before expected arrival | `release` the deposit in full; no charge. |
| User cancels **< 15 minutes** before expected arrival | `charge_penalty` (default $5 late-cancel fee); release remainder. |
| User no-shows (bay empty at arrival + 5 min) | `charge_penalty` (default $10 no-show fee); release remainder ($0 when penalty equals the full deposit). |
| User checks in normally and the vehicle later leaves | `release` the deposit in full; **no parking-fee capture** — that is the facility's exit-side concern, outside this prototype. The mock-payment service emits a "deposit released" receipt. |
| Strong-evidence conflict (LPR plate ∉ user's bound plates) | **`refund` the deposit in full** — the reserving user is a victim, not at fault. The bay is logged as a *facility incident* with the recognised plate as evidence; the operator is expected to bill / sanction the misusing party out-of-band. |
| Weak-evidence conflict (vehicle in reserved bay, LPR did not auto-resolve, no manual check-in within 5 min grace) | `charge_penalty` (default $10 weak-conflict fee); release remainder. The user could have checked in manually if it was them, so the loss is theirs. A subsequent late manual check-in clears the alarm but does **not** refund the penalty (proposal §5.5 alarm rules). |

> The 15-minute cancellation cutoff is measured against *expected arrival time*, not *booking time*, so even a late booking (e.g., reserving 20 min in advance) still offers a safe cancellation window.

**Sanction.** Direct financial consequence (penalty fees) replaces the previous "breach counter + monthly suspension" model — the user is billed each time they break the contract, so a separate suspension mechanism is unnecessary. The backend still maintains a per-user reliability log (event type, reservation id, captured amount) for analytics and for facility admins to review repeat offenders manually; an admin can suspend a user out-of-band via the admin view, but no automatic suspension is triggered. All thresholds (penalty amounts, grace periods, booking window, LPR confidence, hourly rate) are configurable per facility; the values in the schedule above are prototype defaults.

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

**Mock payment via in-process bank simulator.** The prototype includes a payment flow tied to the reservation deposit: pre-authorization at booking, full release on normal completion, penalty captures on contract breach, and full refund on strong-evidence conflict (§5.5). **Per-time parking-fee billing is intentionally out of scope** — it is the facility's exit-side concern (gate / kiosk) and would force a parallel time-based capture flow that doesn't add to what the prototype is demonstrating. Real payment-gateway integration (Stripe, Adyen, Worldpay) is also out of scope because (i) it requires a real merchant account and a PCI-DSS posture, and (ii) it would force the prototype to handle real money during demo runs. Instead, the backend hosts a mock-bank database that we populate with test card numbers; the payment-service interface (`validate_card`, `preauthorize`, `release`, `charge_penalty`, `refund` — note that no `capture` method is exposed, by design) is shape-compatible with what a real gateway exposes minus the time-based capture, so swapping to a real provider in a production deployment is an isolated single-module change (the production deployment would *also* add a `capture` method on the gateway side and a corresponding exit-billing path). The card-entry form on the dashboard shows a clear "MOCK PAYMENT — DO NOT ENTER REAL CARD DETAILS" banner. We acknowledge that real PCI-compliant systems never handle raw card numbers in their own backend — they tokenize at the browser via the gateway's hosted fields (e.g., Stripe Elements). The mock backend explicitly accepts raw card details only because no real money flows; this is called out in the production-deployment section of the final report.

**Idempotent payment endpoints.** Every payment action is keyed by `(reservation_id, action)` (e.g., `preauthorize:res-123`, `capture:res-123`) so that retries from network blips, MQTT redeliveries, sweeper-replayed events, or user double-clicks do not double-charge. The `payments` table has a unique partial index per the project's existing event-replay conventions.

**Reservation deposit only — per-time parking-fee billing is out of scope.** A real paid facility bills *every* parking session by time, typically at the exit gate / kiosk. Our system handles only the **reservation deposit**: the user's card is pre-authorized at booking, and the deposit is either released in full (normal completion or clean cancel), captured-as-penalty (late cancel / no-show / weak conflict, with the remainder released), or refunded in full (strong-conflict victim). We deliberately do **not** charge the user for the parking session itself, because (i) per-time billing is naturally the facility's exit-side responsibility (gate / kiosk / monthly-pass system) and is already solved infrastructure for paid car parks, (ii) building it would force us to track entry timestamps for casual parkers we don't otherwise see, and (iii) it cleanly separates the *reservation enforcement* concern (our scope) from the *parking-fee billing* concern (out of scope). This decision is what makes the mock-payment surface small enough to be tractable for the prototype while still demonstrating end-to-end flows for every reservation outcome.

**Casual (non-reserved) parking is not billed by our system in the prototype.** Same reasoning as above — casual parkers go through the facility's existing gate/kiosk payment path, which is out of scope. Our system has no entry/exit gates and no entry-side LPR, and casual users park at non-reserved bays and leave with no interaction from us.

**Entry / exit gate integration is out of scope.** Real paid facilities pair payment with physical gates (entry ticket dispenser, exit pay-and-go). Our system operates at the bay level only; gate integration is not implemented. Architecturally, the existing event stream is gate-friendly: the backend emits bay state, reservation, and deposit-released events that a future gate-controller subsystem could subscribe to and use to drive entry/exit gate hardware. We mention this explicitly so the architectural extension path is clear; we are not building it.

**Plate ownership not verified.** In the prototype, when a user adds a plate to their account, we **trust the user's input** — there is no verification that the plate actually belongs to them. This is appropriate for a class prototype but would be unsafe in production: a malicious user could bind another driver's plate, then exploit auto check-in to "consume" reservations associated with that plate. A production deployment would need a verification step, e.g., uploading a copy of the vehicle registration document with OCR + manual review, or integration with a vehicle-registry API.

**Enforcement boundary.** The system's role at the bay level ends at *detecting*, *alerting*, *deterring* (via the alarm), and *charging the reserving user's pre-auth* (capture or penalty per §5.5). Enforcement *against the misusing party* on a strong-evidence conflict (boot-locks, fines, gate-side blocking) is delegated to facility operators, who use the recognised plate logged by our incident record as evidence. Our scope is providing reliable evidence (bay state, timestamps, recognised plate, captured image), timely alerts, and automatic billing of the reserving user — not gate-side enforcement of the misusing vehicle.

**Privacy / image retention.** Recognised plates and captured images are PII and are retained only as long as needed for their intended purpose (see the retention policy in §5.5). Indoor placement and per-bay framing minimise incidental capture of bystanders.

### 5.7 Future Work

The following extensions are **not in the core scope** but the architecture is designed to accommodate them.

**Plate ownership verification.** Add a verification step at plate-binding time (registration document upload with OCR + manual review, or integration with a vehicle-registry API). Closes the abuse vector noted in §5.6.

**Real payment-gateway integration.** Replace the in-process mock-bank simulator with a real provider (Stripe, Adyen, or Worldpay) using their tokenized hosted-field SDKs at the browser. The current payment-service interface (`validate_card`, `preauthorize`, `capture`, `release`, `charge_penalty`, `refund`) is intentionally provider-agnostic — this is a single-module swap, with the rest of the reservation business logic untouched.

**Entry / exit gate integration.** Add a gate-controller subsystem that subscribes to the bay state stream and the successful-charge events (already emitted by the backend) to auto-open the entry gate on a confirmed reservation arrival and the exit gate on a successful capture. Closes the loop between the bay-level system and a full facility access-control deployment.

**Casual-parking billing.** Extend the payment flow to non-reserved bays via integration with the facility's gate-side LPR or ticket system, so casual parkers are also billed automatically on exit. Required before the system can replace (rather than complement) a facility's existing payment path.

**Mobile push notifications.** A native or PWA mobile client wired to the existing notification stream (auto check-in confirmations, please-check-in prompts, charge receipts, conflict alerts), giving lower-friction alerts than email/dashboard.

**Outdoor deployment hardening.** Weatherproof enclosures, IR-illuminated cameras (for night operation), temperature-compensated ultrasonic distance, and high-brightness LEDs for direct sunlight. Required to extend the system to open-air car parks.

**Admin override and conflict resolution UI.** A workflow for admins to clear strong-evidence conflicts (e.g., when the misusing vehicle is moved by staff), to issue out-of-band fines tied to logged plate evidence, and to manually suspend repeat-offender accounts.

---

## 6. Distribution of Work

| Name | Primary Subsystem | Integration / Testing / Docs Role | Reason for the Assignment |
|------|-------------------|-----------------------------------|---------------------------|
| Yuan Cong Yuan | **Subsystem A + B:** Ultrasonic sensor integration, ESP32-CAM image-capture firmware (sensor-triggered) + HTTP image upload, multi-state LED control (including blinking patterns), buzzer driver | **Device-level testing lead:** sensor calibration, full six-state LED + buzzer coverage, camera trigger / upload bring-up, hardware ↔ firmware bring-up; also compiles final report and demo script | Strong debugging and system-level thinking skills; the device layer (A+B) is tightly coupled (camera trigger and LED/buzzer state both derive from sensor readings + commands) so a single owner is more efficient than two |
| Nyx Chen | **Subsystem C + D + E:** Per-bay reservation state machine and conflict-detection service on the Raspberry Pi, **OpenALPR setup and integration** (image-receiver service, plate-matching against bound-plate lists), MQTT communication setup (local + cloud brokers), edge gateway control logic | **Cross-tier integration lead:** owns end-to-end data-flow bring-up across device ↔ gateway ↔ cloud (natural fit since C+D+E already sits in the middle, and LPR runs on the Pi inside Subsystem C's control loop) | Experience with networking protocols, state-machine design, and microcontroller programming; LPR integration sits on the same Pi as the state machine, so co-locating ownership avoids hand-off seams |
| Cheng Zhang | **Subsystem F (Backend):** Flask server, REST API, **account & plate management** (CRUD on bound plates, plate-list publish over cloud MQTT), reservation business logic (booking window, fee + penalty capture, push notifications), conflict-evidence log, **mock-payment service** (mock-bank database seeding, idempotent `validate_card` / `preauthorize` / `capture` / `release` / `charge_penalty` / `refund` endpoints, transactions log), database, cloud MQTT client integration, AWS deployment | Backend unit/integration tests; API and deployment documentation | Background in Python and server-side programming; familiarity with cloud services; payment service is co-located with reservation logic so single ownership avoids cross-module hand-offs |
| Riya Sakhiya | **Subsystem F (Frontend):** React.js parking map UI, real-time status updates, **plate-management UI** (add/remove/list bound plates), reservation / cancel / manual-check-in interface (including QR scan fallback flow), **mock payment form** (card-entry with the "MOCK PAYMENT" banner) and **transaction-history view**, admin conflict-alert view with plate evidence and resulting refund/penalty | Frontend unit tests; UI/UX documentation and demo screen captures | Experience in web development (React, HTML/CSS/JS); strong UI/UX design skills |

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
| 4 | Apr 28 – May 4 | **Subsystem F (backend):** Account / plate management API; reservation logic (booking window, cancel, manual check-in fallback, deposit + penalty accounting); **mock-payment service** (mock-bank seed data, idempotent `validate_card` / `preauthorize` / `release` / `charge_penalty` / `refund`, transactions log; **no `capture` action** — per-time billing out of scope, see §5.6); cloud MQTT publish of reservation + bound-plate list; push notifications (auto check-in, please check-in, deposit released, refund issued, penalty captured, strong/weak conflict) | Cheng | Week 3 Backend |
| 4 | Apr 28 – May 4 | **Subsystem F (frontend):** Reservation / cancel / manual-check-in flows; **mock payment form** with the "MOCK PAYMENT" banner; transaction-history view; admin conflict-alert view with refund/penalty actions | Riya | Week 3 Frontend + Backend payment endpoints |
| 5 | May 5 – May 11 | **Integration:** End-to-end flow across all three tiers — plate binding → reservation **with mock card pre-auth deposit** → cloud MQTT → Pi state machine → ESP32-CAM LED/buzzer; arrival → camera trigger → LPR → auto check-in OR strong/weak conflict + alarm → dashboard notifications; **vehicle leaves → deposit released in full (or penalty / refund on the contract-breach paths)** → receipt | Nyx (lead) + All | Week 4 all subsystems |
| 6 | May 12 – May 18 | **Testing:** End-to-end testing of all scenarios (detect, reserve, cancel, auto/manual check-in, strong/weak conflict + alarm, no-show, **fee + penalty capture, refund on strong conflict, idempotency under retries**, LPR accuracy/latency, cloud disconnection resilience); bug fixes | Yuan Cong (lead) + All | Week 5 integration |
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
| **M2:** Subsystems Individually Working | 4 | May 4 | Sensor detects vehicles; ESP32-CAM captures and uploads images on trigger; OpenALPR returns plate strings; LEDs + buzzer cycle through all six states; state machine produces correct events (including auto check-in and strong/weak conflicts) under a scripted test harness; dashboard shows bays and supports plate management; reservation / manual check-in API functional; **mock-payment service answers `validate_card` / `preauthorize` / `release` / `charge_penalty` / `refund` correctly under unit tests** |
| **M3:** End-to-End Integration Complete | 5 | May 11 | Full data flow works: plate binding → reservation **with card pre-auth deposit** → LED; arrival → camera trigger → LPR → auto check-in OR strong/weak conflict + alarm → dashboard notifications; **vehicle leaves → deposit released in full (penalty / refund on the contract-breach paths) → receipt visible in transaction history** |
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
| **No-show / Auto-release** | System auto-releases an unclaimed reservation after the arrival grace and captures a no-show penalty | 100% | Create reservation, never arrive; verify auto-release and no-show penalty capture (transactions log + card balance) after arrival + 5 min, 10 trials |

**Communication and End-to-End (Subsystems D + E + F):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **MQTT Message Delivery Rate** | % of messages successfully delivered (local + cloud) | ≥ 99% | Log published vs received messages over 200 message exchanges |
| **Image Upload Success Rate** | % of camera-triggered images successfully delivered to the Pi image-receiver | ≥ 99% | Trigger 100 captures; count successful uploads |
| **End-to-End Latency** | Time from user reservation click to LED state change | < 5 seconds | Timestamp reservation request on dashboard vs LED update; repeat 20 times |
| **Auto-Check-in Round-trip Latency** | Time from vehicle detection to dashboard "you're checked in" notification | < 8 seconds | Timestamp sensor falling-edge vs notification arrival; 20 trials |
| **Cloud Disconnection Resilience** | Local control (sensor + LPR → LED + buzzer) continues during cloud outage | Pass/Fail | Disconnect Pi from internet; verify local sensor → LPR → indicator still works; reconnect and verify cloud re-sync |
| **Dashboard Accuracy** | Dashboard bay state matches physical bay state | 100% | Compare dashboard display vs physical LED states across all 3 bays over 10 state changes |

**Reservation & Plate Logic (Subsystem F):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **Plate Management Correctness** | Add / remove / list plate operations produce correct DB state and the bound-plate list reaches the Pi for matching | 100% | Execute each operation 10×; verify DB and that the Pi's view updates within 5 s |
| **Reservation Correctness** | Reserve, cancel, manual check-in operations produce correct DB state, events, and LED transitions | 100% | Execute each operation 10 times; verify database state, events emitted, and LED state |

**Mock Payment Correctness (Subsystem F — payment service):**

| Metric | Definition | Target | Test Method |
|--------|-----------|--------|-------------|
| **Card Validation** | Valid mock cards (number, CVV, expiry, sufficient balance) are accepted; invalid cards (wrong CVV, expired, insufficient balance, unknown number) are rejected with the correct error code | 100% | Drive each acceptance and rejection path 10× via the API; verify response codes and that no transaction row is written for rejected cards |
| **Pre-auth at Booking** | On a successful booking, exactly one `pre_auth` payment row is written with `amount = $10` (deposit default); the mock card balance is decremented by exactly $10 | 100% | Create 10 reservations across varied cards; verify `pre_auth` rows and resulting card balances |
| **Deposit Release on Completion** | On normal exit (vehicle leaves after `Reserved + Checked-in`), the full deposit is released back to the card; no parking-fee capture occurs (out of scope for this prototype — see §5.6); final card balance equals pre-booking balance | 100% | Simulate 10 reservations of varied durations (short, medium, long); verify exactly one `release` row with `amount = $10`, no `capture` row, and final card balance restored |
| **Penalty Capture** | Late-cancel ($5), no-show ($10), and weak-conflict ($10) penalties capture exactly the configured amount; the remainder of the deposit is released (which is $0 when penalty equals deposit, $5 when penalty is $5) | 100% | Trigger each penalty path 5× per user; verify transactions-log entries (penalty + release rows) and final card balance |
| **Strong-Conflict Refund** | On `conflict_strong`, the reserving user's deposit is refunded in full; mock card balance returns to its pre-booking value; the bay logs a facility incident with the recognised plate | 100% | Trigger 10 strong-conflict scenarios; verify refund row, restored balance, incident log entry, and that the user receives the refund notification |
| **Idempotency** | Repeated calls to the same payment action with the same `(reservation_id, action)` key produce exactly one transaction; the mock card balance reflects a single application of the action | 100% | Replay 50 randomly-selected payment actions 3× each (simulating MQTT redelivery); verify transactions log has exactly one row per key and the balance is correct |
| **Free-cancel Window** | Cancel ≥ 15 min before expected arrival fully releases the deposit and writes no penalty | 100% | Create 10 reservations, cancel each at varied lead times within the free window; verify no penalty captured and full deposit released |
| **Weak-Conflict + Late Check-in** | A late manual check-in after the weak-conflict penalty has been captured clears the alarm and transitions the reservation back to `CHECKED_IN`, but the penalty is **not** refunded; on subsequent vehicle-leaves the completion path is a no-op for payment (no double-charge, no spurious release) | 100% | Trigger weak conflict + late check-in + vehicle-leaves on 10 reservations; verify exactly one penalty row, no extra release/refund row at completion, and the reservation status timeline matches |

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

[3] T. Lin, H. Rivano, and F. Le Mouël, "A Survey of Smart Parking Solutions," *IEEE Transactions on Intelligent Transportation Systems*, vol. 18, no. 12, pp. 3229–3253, Dec. 2017.

[4] G. Amato, F. Carrara, F. Falchi, C. Gennaro, C. Meghini, and C. Vairo, "Deep learning for decentralized parking lot occupancy detection," *Expert Systems with Applications*, vol. 72, pp. 327–334, 2017.

[5] Park Assist, "Smart parking guidance system," [Online]. Available: <https://www.parkassist.com>. [Accessed: Mar. 30, 2026].

[6] A. Banks, E. Briggs, K. Borgendale, and R. Gupta, "MQTT Version 5.0," OASIS Standard, Mar. 2019. [Online]. Available: <https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html>.

[7] Espressif Systems, "ESP32 Series Datasheet," v4.3, 2023. [Online]. Available: <https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf>.
