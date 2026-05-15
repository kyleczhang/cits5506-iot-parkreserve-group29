"""``python -m app`` is no longer the dev entrypoint.

``eventlet.monkey_patch()`` has to run before the ``app`` package is
imported — see [run_dev.py](../run_dev.py) for the rationale. Going
through ``python -m app`` (or ``python -m app.web``) is too late: by the
time this module executes, ``app/__init__.py`` has already pulled in
Flask/werkzeug/etc., and the patcher leaves stdlib RLocks un-greened.

Run ``python run_dev.py`` instead (``make dev`` already does this).
"""

from __future__ import annotations

import sys


def _refuse() -> None:
    sys.stderr.write(
        "python -m app is no longer supported as a runtime entrypoint;\n"
        "use `python run_dev.py` (or `make dev`) so eventlet.monkey_patch()\n"
        "runs before the app package is imported.\n"
    )
    raise SystemExit(2)


if __name__ == "__main__":
    _refuse()
