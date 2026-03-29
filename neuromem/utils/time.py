"""
Time and temporal utilities for NeuroMem.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC). Treats naive datetimes as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def format_relative_time(dt: datetime) -> str:
    """
    Format a datetime as relative time (e.g., "2 hours ago").

    Args:
        dt: Datetime to format

    Returns:
        Relative time string
    """
    now = datetime.now(timezone.utc)
    delta = now - ensure_utc(dt)

    seconds = delta.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    else:
        months = int(seconds / 2592000)
        return f"{months} month{'s' if months != 1 else ''} ago"


def parse_time_window(window: str) -> Optional[datetime]:
    """
    Parse a time window string to a datetime threshold.

    Args:
        window: Time window (e.g., "1h", "2d", "1w", "1m")

    Returns:
        Datetime threshold or None if invalid
    """
    now = datetime.now(timezone.utc)

    if not window:
        return None

    try:
        value = int(window[:-1])
        unit = window[-1].lower()

        if unit == "h":
            return now - timedelta(hours=value)
        elif unit == "d":
            return now - timedelta(days=value)
        elif unit == "w":
            return now - timedelta(weeks=value)
        elif unit == "m":
            return now - timedelta(days=value * 30)
        else:
            return None

    except Exception:
        return None
