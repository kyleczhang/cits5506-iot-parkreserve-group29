"""Single-process runtime entrypoint.

Runs HTTP + Socket.IO and also starts inbound MQTT plus APScheduler jobs
inside the same process.

Note: ``eventlet.monkey_patch()`` MUST run **before** anything imports
the ``app`` package — otherwise werkzeug/flask LocalProxy objects already
created during ``app/__init__.py`` blow up eventlet's
"upgrade existing instances" pass, and at least one RLock ends up
un-greened. Use [run_dev.py](../run_dev.py) (top-level entrypoint) to
launch the dev server; importing this module directly via
``python -m app.web`` is no longer supported.
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
