"""Push alerts through ntfy.sh — free, no account, no API key.

Publish: POST https://ntfy.sh/<topic> with the message body.
"""
from __future__ import annotations

import requests


class NotifierError(Exception):
    pass


def send_ntfy(topic: str, title: str, message: str, timeout: int = 15) -> None:
    """POST a notification to ntfy.sh. Raises NotifierError on failure."""
    if not topic or "/" in topic.strip("/"):
        raise NotifierError(f"invalid ntfy topic {topic!r} (must be a single path segment)")
    try:
        resp = requests.post(
            f"https://ntfy.sh/{topic.strip()}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8", "replace").decode("ascii", "replace"),
                "Tags": "car",
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise NotifierError(f"ntfy POST failed: {exc}") from exc
    if resp.status_code >= 300:
        raise NotifierError(f"ntfy POST -> HTTP {resp.status_code}: {resp.text[:200]}")
