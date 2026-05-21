# ParkReserve `parking_node`

`parking_node` is primarily the ESP32 edge-node subsystem for ParkReserve.

This directory also contains one small HTTP receiver stub used for isolated local testing, but the normal system boundary is:

- `parking_node`: ESP32 node only
- `raspberry`: Pi-side gateway and orchestration

Contents in this directory:

- `esp32/esp32.ino`: firmware for the Seeed XIAO ESP32S3 Sense parking node
- `pictureTestServer/server.py`: lightweight local test stub for image upload compatibility
- `API.md`: protocol notes for HTTP and MQTT

This README focuses on the ESP32 node and only mentions gateway-side pieces where the edge node must integrate with them.

## What The Current Code Does

### ESP32 node

The firmware connects to Wi-Fi, subscribes to MQTT LED commands, samples an ultrasonic sensor, and publishes parking occupancy changes.

It also captures a camera image and uploads it to the gateway when all of the following are true:

- the bay transitions from `available` to `occupied`
- the LED state is `reserved` or `pending_check_in`
- the vehicle remains stable for 3 seconds

Current runtime behaviour in code:

- Occupied threshold: `<= 100 cm`
- Available threshold: `>= 150 cm`
- Sensor sampling interval: `200 ms`
- State confirmation filter: `10` consecutive readings, about `2 s`
- MQTT heartbeat: every `2 s`
- Retry loop for pending uploads: every `10 s`

### Local test stub

`pictureTestServer/server.py` is not the main Pi subsystem. It is only a small compatibility server for isolated testing of the ESP32 upload path.

It exposes one upload endpoint:

- `POST /api/v1/bays/<int:bay_id>/image`

It expects:

- header `X-API-Key`
- header `X-Timestamp`
- raw JPEG bytes in the request body

On success it saves the image into `pictureTestServer/incoming_plates/` and returns `202 Accepted`.

## Directory Layout

```text
parking_node/
├── API.md
├── esp32/
│   └── esp32.ino
├── pictureTestServer/      # optional local test stub, not the main Pi gateway
│   └── server.py
└── README.md
```

## Hardware Wiring

| Component | ESP32 Pin | Notes |
| :-- | :-- | :-- |
| Red LED | `D0` | Solid red for `occupied` / `reserved_checked_in`; blinking for conflict |
| Yellow LED | `D1` | Solid for `reserved`; blinking for `pending_check_in` |
| Green LED | `D2` | Solid for `available` |
| Buzzer | `D3` | Enabled during `conflict_strong` and `conflict_weak` |
| Ultrasonic `TRIG` | `D4` | Output |
| Ultrasonic `ECHO` | `D5` | Input |
| TF / MicroSD `CS` | `D21` | SPI chip select |

Camera pins are hard-coded in `esp32/esp32.ino` for the Seeed XIAO ESP32S3 Sense.

## Required Configuration Before You Test

Update the constants at the top of [esp32/esp32.ino](./esp32/esp32.ino):

```cpp
const char* ssid = "...";
const char* password = "...";
const char* gateway_ip = "...";
const int   gateway_port = 5000;
const char* api_path = "/api/v1/bays/1/image";

const char* api_secret_key = "ParkReserve-Group29-SuperSecret";

const char* mqtt_server = "...";
const int   mqtt_port = 1883;
const char* mqtt_topic_led    = "bay/A1/led";
const char* mqtt_topic_status = "bay/A1/status";
```

Important:

- `api_secret_key` must exactly match `SECRET_KEY` in [pictureTestServer/server.py](./pictureTestServer/server.py).
- The current Flask route only accepts an integer `bay_id`, so `api_path` must use a numeric segment such as `/api/v1/bays/1/image`.
- MQTT topics in the current firmware use bay label `A1`, while the HTTP route uses numeric bay IDs. That inconsistency is in the current implementation and must be handled manually.

## External Dependencies

The ESP32 firmware does not start MQTT or HTTP services.

For normal integration it expects the Pi side to already provide:

- a local MQTT broker running on the Raspberry Pi and reachable at `mqtt_server:mqtt_port`
- an HTTP image receiver reachable at `http://gateway_ip:gateway_port + api_path`

MQTT deployment model for this subsystem:

- ESP32 <-> Raspberry Pi uses the Pi's local MQTT broker
- Raspberry Pi <-> backend uses HiveMQ on the cloud side
- the ESP32 does not connect directly to HiveMQ

In this repository, the main Pi-side subsystem is documented in `raspberry/`.

`pictureTestServer/server.py` exists only for isolated edge-node testing when the full Pi gateway is not being used.

From `parking_node/pictureTestServer`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask
python server.py
```

The stub listens on `0.0.0.0:5000` and creates `incoming_plates/` automatically.

## ESP32 Build Notes

Open `esp32/esp32.ino` in Arduino IDE and use:

- Board: `Seeed XIAO ESP32S3`
- PSRAM: `OPI PSRAM`

Without PSRAM, camera initialization may fail or fall back to reduced capability.

## MQTT Topics And Payloads

### Pi / Gateway -> ESP32

Topic:

```text
bay/A1/led
```

Recognized payloads in the current firmware:

- `available`
- `reserved`
- `occupied`
- `reserved_checked_in`
- `pending_check_in`
- `conflict_strong`
- `conflict_weak`

### ESP32 -> Pi / Gateway

Topic:

```text
bay/A1/status
```

Published payloads:

- `available`
- `occupied`

The firmware publishes immediately on edge transitions and also sends a heartbeat every 2 seconds.

## HTTP Upload Contract

Current stub endpoint:

```text
POST /api/v1/bays/<int:bay_id>/image
```

Required headers:

```text
Content-Type: image/jpeg
X-API-Key: ParkReserve-Group29-SuperSecret
X-Timestamp: YYYYMMDD_HHMMSS
```

Example:

```bash
curl -X POST "http://127.0.0.1:5000/api/v1/bays/1/image" \
  -H "Content-Type: image/jpeg" \
  -H "X-API-Key: ParkReserve-Group29-SuperSecret" \
  -H "X-Timestamp: 20260518_120000" \
  --data-binary "@test.jpg"
```

Success response:

```json
{
  "message": "Image securely received",
  "file": "bay_1_20260518_120000.jpg"
}
```

## ESP32-Focused Test Flow

For an edge-node test, first make sure the Pi side already exposes MQTT and an upload endpoint.

If you only want to test the ESP32 upload path without the full Pi subsystem, you can use `pictureTestServer/server.py` as the HTTP stub.

1. Ensure the Pi-side local MQTT broker is reachable from the ESP32.
2. If needed for isolated testing, start `pictureTestServer/server.py`.
3. Update and upload `esp32.ino`.
4. From the Pi side or another MQTT client, publish a reservation command:

```bash
mosquitto_pub -h <broker-ip> -t bay/A1/led -m reserved
```

1. Place an object within `100 cm` of the ultrasonic sensor and keep it there for at least `~5 s`.

Expected sequence:

- the node confirms `occupied` after about 2 seconds
- it waits another 3 seconds before capture
- it stores `/img_<timestamp>.jpg` on the SD card
- it tries an HTTP upload
- the Pi-side receiver stores the uploaded image

To test release:

```bash
mosquitto_pub -h <broker-ip> -t bay/A1/led -m available
```

Then remove the object until the measured distance stays above `150 cm` for about 2 seconds.

## Boundary Notes

- ESP32 is only an MQTT client and HTTP client.
- ESP32 does not host or start an MQTT broker.
- ESP32 does not host the HTTP receiver.
- The MQTT broker used by ESP32 belongs to the Pi-side subsystem in normal deployment.
- HiveMQ is used on the separate Pi/backend cloud link, not on the ESP32/Pi local link.
- The image receiver belongs to the Pi-side subsystem in normal deployment.
- `pictureTestServer/server.py` is only a local compatibility stub for edge-node testing.

## Current Limitations And Known Mismatches

These are not documentation issues; they are properties of the current code:

- The default firmware `api_path` is `/api/v1/bays/A1/image`, but the Flask route only accepts `/api/v1/bays/<int:bay_id>/image`. You must change one side before upload can succeed.
- MQTT uses bay key `A1`, while the Flask upload route and saved filenames use numeric bay IDs.
- `cleanupSD()` deletes existing `.jpg` and `.jpeg` files on startup, including previously queued images.
- Pending image retry is not truly durable. In `processPendingUploads()`, files older than 10 seconds are deleted instead of retried indefinitely.
- There is no `requirements.txt`; the server currently only imports `flask` and `os`.

## Related Files

- [esp32/esp32.ino](./esp32/esp32.ino)
- [pictureTestServer/server.py](./pictureTestServer/server.py)
- [API.md](./API.md)
