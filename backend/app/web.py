"""Single-process runtime entrypoint.

Runs HTTP + Socket.IO and also starts inbound MQTT plus APScheduler jobs
inside the same process.
"""

from __future__ import annotations

import os

from app import create_wsgi_app, stop_runtime_services
from app.extensions import socketio


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
