"""Shared date/datetime formatting helpers for FHIR resource builders."""

from __future__ import annotations

from datetime import date, datetime


def fhir_datetime(value: date | datetime) -> str:
    """
    Format a `date` or `datetime` as a FHIR R4 `dateTime` string.

    FHIR R4 requires a timezone whenever a time component is present. Naive
    datetimes are treated as UTC (Z suffix); tz-aware datetimes keep their
    offset. Bare `date` values are emitted as a plain ISO date.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat() + "Z"
        return value.isoformat()
    return value.isoformat()
