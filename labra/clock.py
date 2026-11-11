"""A single source of 'today', so tests can freeze it."""
from __future__ import annotations

from datetime import date, datetime, timezone


def today_utc() -> date:
    return datetime.now(timezone.utc).date()
