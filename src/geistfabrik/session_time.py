"""Canonical calendar-day semantics for reproducible sessions."""

from datetime import datetime


def normalise_session_date(value: datetime) -> datetime:
    """Return the naive midnight representing ``value``'s calendar date.

    A GeistFabrik session is identified by ``YYYY-MM-DD`` in SQLite and in the
    journal. Keeping time-of-day or timezone offsets in random seeds would make
    two invocations of that same session produce different output.
    """
    return datetime(value.year, value.month, value.day)


def session_seed(value: datetime) -> int:
    """Return the stable integer seed for a session calendar date."""
    canonical = normalise_session_date(value)
    return canonical.year * 10_000 + canonical.month * 100 + canonical.day
