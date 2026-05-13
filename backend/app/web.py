"""Single-process runtime entrypoint.

Runs HTTP + Socket.IO and also starts inbound MQTT plus APScheduler jobs
inside the same process.

``eventlet.monkey_patch()`` MUST run before anything imports ``threading``
or ``paho.mqtt`` — otherwise paho's ``loop_start()`` spins up a real OS
thread whose ``socketio.emit`` calls can't reach connected clients (no
message queue is configured). Keep this import at the very top.
"""

from __future__ import annotations

import eventlet

eventlet.monkey_patch()

import os  # noqa: E402

from app import create_wsgi_app, stop_runtime_services  # noqa: E402
from app.extensions import socketio  # noqa: E402


def main() -> None:
    # This entrypoint uses create_wsgi_app(), so running `make dev` starts the
    # full backend runtime: HTTP/Socket.IO plus MQTT and scheduler services.
    app = create_wsgi_app()
    try:
        socketio.run(
            app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), allow_unsafe_werkzeug=True
        )
    finally:
        stop_runtime_services(app)


if __name__ == "__main__":
    main()
