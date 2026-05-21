# ParkReserve `raspberry`

`raspberry` is the Python gateway service that sits between the ESP32 parking nodes and the cloud/backend side of ParkReserve.

It currently does four jobs:

- subscribes to local MQTT occupancy updates from ESP32 nodes
- publishes local MQTT LED commands back to ESP32 nodes
- receives uploaded parking images over HTTP and runs plate recognition
- mirrors bay state and events to the cloud MQTT broker

MQTT deployment model:

- Raspberry Pi <-> ESP32 uses a local MQTT broker running on the Pi side
- Raspberry Pi <-> backend uses a separate cloud-side broker running on HiveMQ

This README describes the code that is currently in `raspberry/`.

System boundary for this subsystem:

- Pi side hosts the gateway-side services
- ESP32 side only acts as an MQTT client and HTTP uploader
- ESP32 does not run an MQTT broker or HTTP server

## Directory Layout

```text
raspberry/
├── config/
│   └── settings.py
├── services/
│   ├── control_service.py
│   ├── image_receiver.py
│   └── state_machine.py
├── tests/
│   └── test_state_machine.py
└── main.py
```

## Main Components

### `main.py`

Entry point for the gateway process.

- creates `./tmp/parkReserve/images`
- configures console and file logging
- starts `ControlService`
- handles `SIGINT` and `SIGTERM`

### `services/control_service.py`

Main orchestrator. It owns:

- local MQTT client for ESP32 communication
- cloud MQTT client for backend communication
- per-bay state machines
- HTTP image receiver
- license plate recognition service

### `services/state_machine.py`

Implements the per-bay reservation lifecycle.

Current state values:

- `available`
- `reserved`
- `occupied`
- `pending_check_in`
- `reserved_checked_in`
- `conflict`
- `offline`

The state machine sends plain string LED commands, not JSON payloads.

### `services/image_receiver.py`

Runs a FastAPI server for image uploads.

Current routes:

- `POST /api/v1/bays/{bay_id}/image`
- `GET /health`
- `GET /status`

Unlike the older Flask prototype in `parking_node/`, this receiver accepts both:

- numeric bay IDs like `1`
- bay codes like `A1`

## Runtime Architecture

### Local side: ESP32 <-> Raspberry Pi

Local MQTT topics used by the gateway:

- subscribe: `bay/+/status`
- publish: `bay/{code}/led`

Accepted occupancy payloads from ESP32:

- plain string: `occupied` or `available`
- JSON: `{"occupied": true, "distance_cm": 42.0}`

Published LED payloads are plain strings such as:

- `available`
- `reserved`
- `pending_check_in`
- `reserved_checked_in`
- `conflict_strong`

The broker itself is expected to run on the Pi side as infrastructure. The Python gateway connects to it; it does not embed an MQTT broker in-process.

### Cloud side: Raspberry Pi <-> Backend

Cloud MQTT topics from `config/settings.py`:

- publish state: `cloud/bay/{code}/state`
- publish event: `cloud/bay/{code}/event`
- publish heartbeat: `cloud/system/heartbeat`
- subscribe reservation commands: `cloud/bay/+/reservation`
- subscribe resync: `cloud/system/resync`

This cloud-side broker is configured in `config/settings.py` and is the HiveMQ broker used for Pi/backend communication, separate from the Pi's local Mosquitto instance.

Supported reservation actions in the current code:

- `create`
- `cancel`
- `check_in`
- `update_plates`
- `release`
- `expire_check_in`

### Image upload and LPR

The receiver stores uploaded files under:

```text
./tmp/parkReserve/images
```

After saving an image, it asynchronously calls the LPR pipeline:

1. map `bay_id` to `A1` / `A2` / `A3`
2. save JPEG locally
3. run EasyOCR if available
4. fall back to mock LPR in test mode or when EasyOCR is unavailable
5. push the result into the bay state machine

## Dependencies

There is currently no `requirements.txt` in `raspberry/`, so dependencies have to be inferred from imports.

Core runtime dependencies:

- `paho-mqtt`
- `fastapi`
- `uvicorn`

Optional runtime dependency:

- `easyocr`

Test dependency:

- `pytest`

Recommended setup:

```bash
cd raspberry
python3 -m venv .venv
source .venv/bin/activate
pip install paho-mqtt fastapi uvicorn easyocr pytest
```

If you do not want real OCR during development, you can still run without `easyocr` by enabling `TEST_MODE` or letting the mock fallback path run.

## Configuration

All runtime configuration is currently in [config/settings.py](./config/settings.py).

Important fields:

- `TEST_MODE`
- local MQTT host, port and topic templates
- cloud MQTT host, port, username and password
- image receiver host and port
- `ALPR_MIN_CONFIDENCE`
- timeout settings
- `PI_ID`
- `BAY_CODES`

Important operational note:

- `raspberry/.gitignore` ignores `config/settings.py`, so this file is being treated like local environment configuration.
- The current working copy contains real-looking cloud MQTT credentials in that file. Those should be rotated and moved to environment-based configuration if this code is used beyond coursework or local testing.

## How To Run

### 1. Start a local MQTT broker

The code expects Mosquitto or another broker on the Pi side for ESP32 communication:

```text
localhost:1883
```

### 2. Review `config/settings.py`

At minimum, verify:

- `LOCAL_MQTT_HOST`
- `CLOUD_MQTT_HOST`
- `CLOUD_MQTT_USERNAME`
- `CLOUD_MQTT_PASSWORD`
- `CLOUD_MQTT_PORT`
- `IMAGE_RECEIVER_PORT`
- `BAY_CODES`
- `TEST_MODE`

### 3. Start the gateway

From `raspberry/`:

```bash
python main.py
```

On startup, the service should:

- start the FastAPI image receiver on port `8080`
- connect to local MQTT
- connect to cloud MQTT over TLS
- publish a resync request to `cloud/system/resync`
- start a heartbeat loop every 10 seconds

## HTTP Interface

### `POST /api/v1/bays/{bay_id}/image`

Request:

```text
Content-Type: image/jpeg
X-API-Key: ParkReserve-Group29-SuperSecret
X-Timestamp: YYYYMMDD_HHMMSS   # optional
```

Body:

- raw JPEG bytes

Example:

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/bays/1/image" \
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

Debug endpoints:

- `GET /health`
- `GET /status`

## State Machine Behaviour

Important current behaviour in `services/state_machine.py`:

- `available -> reserved` when a reservation is created
- `reserved -> pending_check_in` when a vehicle arrives
- `pending_check_in -> reserved_checked_in` when LPR matches or backend sends `check_in`
- `pending_check_in -> conflict` on LPR mismatch
- `available -> occupied` for an unreserved arrival
- `reserved_checked_in -> available` when the checked-in vehicle leaves

Timeout behaviour:

- no-show timeout is driven by `expected_arrival_time + no_show_grace`
- manual check-in timeout moves `pending_check_in` to `conflict`
- the current timeout handlers report state changes, but intentionally do not emit separate event messages for some backend-only concepts

## Logs And Files

Generated files:

- images: `./tmp/parkReserve/images/`
- gateway log: `./tmp/parkReserve/gateway.log`

These paths are created automatically by `main.py`.

## Known Issues And Gaps

These reflect the current repository state:

- There is no `requirements.txt` or `pyproject.toml` in `raspberry/`.
- `tests/test_state_machine.py` does not match the current state machine implementation. It still expects older LED callback payloads and event names that no longer exist.
- `python3 -m pytest raspberry/tests/test_state_machine.py` currently cannot run in this workspace because `pytest` is not installed.
- The configuration file currently mixes test flags, topic definitions, and broker credentials in one module.
- Secrets are hard-coded in `config/settings.py` and the image receiver API key is hard-coded separately in `services/image_receiver.py`.

## Related Files

- [main.py](./main.py)
- [config/settings.py](./config/settings.py)
- [services/control_service.py](./services/control_service.py)
- [services/state_machine.py](./services/state_machine.py)
- [services/image_receiver.py](./services/image_receiver.py)
