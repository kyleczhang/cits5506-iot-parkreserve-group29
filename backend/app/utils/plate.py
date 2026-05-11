"""Licence-plate string normalisation and format validation.

The DB-level CHECK ``licence_plates_format`` enforces the canonical regex,
but we normalise application-side first so user input like ``"abc 123"`` /
``"abc-123"`` is accepted as ``"ABC123"``.
"""

from __future__ import annotations

import re

from app.models import PLATE_FORMAT_REGEX

_NORMALISE_STRIP_RE = re.compile(r"[\s\-_]+")
_VALID_RE = re.compile(PLATE_FORMAT_REGEX)


def normalise(plate: str) -> str:
    return _NORMALISE_STRIP_RE.sub("", plate).upper()


def is_valid(plate: str) -> bool:
    return _VALID_RE.match(plate) is not None
