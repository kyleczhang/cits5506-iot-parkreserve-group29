"""Dev / single-process runtime entrypoint.

Lives outside the ``app/`` package on purpose: ``eventlet.monkey_patch()``
must run before *any* module from ``app`` (or its transitive imports such
as Flask, werkzeug, flask-jwt-extended, paho-mqtt) is imported, otherwise
eventlet's "upgrade existing instances" pass trips over LocalProxy objects
that need an app/request context and leaves stdlib RLocks un-greened.
That in turn means ``socketio.emit()`` calls from paho's background thread
(which is exactly the MQTT → ``bay.updated`` path) silently fail to reach
connected WebSocket clients.

So: run this file, not ``python -m app.web``.
"""

from __future__ import annotations

import eventlet

eventlet.monkey_patch()

from app.web import main  # noqa: E402

if __name__ == "__main__":
    main()
