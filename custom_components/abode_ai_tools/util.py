"""Small pure helpers shared by the tool modules.

This module imports nothing from Home Assistant so it can be unit-tested
without the HA test harness.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit


def short(value: Any, limit: int) -> str:
    """Return value as a string of at most ``limit`` characters."""
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return f"{text[: limit - 3]}..."


def bound_json(value: Any, limit: int, *, max_items: int = 10) -> Any:
    """Return value with strings, list items and dict entries bounded.

    Used for Paperless custom fields, which are arbitrary JSON and are not
    covered by the document text cap.
    """
    if isinstance(value, str):
        return short(value, limit)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {
            short(key, limit): bound_json(item, limit, max_items=max_items)
            for key, item in list(value.items())[:max_items]
        }
    if isinstance(value, (list, tuple)):
        return [
            bound_json(item, limit, max_items=max_items)
            for item in value[:max_items]
        ]
    return short(value, limit)


def safe_url(url: str) -> str:
    """Return scheme://host:port for logs, without userinfo, path or query."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<invalid url>"

    try:
        host = parts.hostname or "<unknown>"
    except ValueError:
        return "<invalid url>"

    try:
        port = parts.port
    except ValueError:
        port = None
    if port is not None:
        host = f"{host}:{port}"
    return f"{parts.scheme or '?'}://{host}"
