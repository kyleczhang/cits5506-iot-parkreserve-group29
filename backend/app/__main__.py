"""``python -m app`` shim — delegates to the web entrypoint.

This module exists so that ``python -m app`` starts the single long-lived
backend process.
"""

from __future__ import annotations

from app.web import main

if __name__ == "__main__":
    main()
