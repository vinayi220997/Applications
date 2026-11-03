"""Freshness classification. Publication date and discovery date are never mixed up."""
from .normalize import parse_date, now_utc

CATEGORIES = {
    "24h": "Published within the last 24 hours",
    "3d": "Published within the last 3 days",
    "7d": "Published within the last 7 days",
    "older_active": "Older but still active",
    "unknown": "Publication date unknown",
}


def classify(published_at, now=None, window_days=7):
    """Rolling windows from the source's own publication timestamp."""
    pub = parse_date(published_at)
    if pub is None:
        return "unknown"
    now = now or now_utc()
    hours = (now - pub).total_seconds() / 3600
    if hours < -24:            # a timestamp in the future is not trustworthy
        return "unknown"
    if hours <= 24:
        return "24h"
    if hours <= 72:
        return "3d"
    if hours <= 24 * window_days:
        return "7d"
    return "older_active"


def recently_discovered(first_seen_at, now=None):
    fs = parse_date(first_seen_at)
    return bool(fs and ((now or now_utc()) - fs).total_seconds() <= 24 * 3600)
