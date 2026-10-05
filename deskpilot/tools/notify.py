"""Notification tool: deliver the finished daily plan to Telegram.

A small, outbound-only helper so a Deskpilot run can end by pushing the plan to
the user's phone — the last step that makes the daily routine truly hands-off.
It reuses the user's existing Telegram bot via its token; only config (token +
chat id) is shared, no other code.

Read-only decision support: this sends a text message and nothing else. It never
places, modifies, or cancels an order. Like the market tools, it is defensive —
on any failure (or when unconfigured) it returns a dict with a status/error key
rather than raising, so a flaky network or a missing token never crashes a run.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Telegram caps a single message at 4096 characters.
_TELEGRAM_MAX = 4096


def _split(text: str, limit: int = _TELEGRAM_MAX) -> list[str]:
    """Break text into <=limit-char pieces, preferring paragraph/line breaks.

    A long plan is delivered as several messages instead of being truncated, so
    the user never loses the tail. Splits land on a blank line where possible,
    then any newline, and only hard-cut mid-line as a last resort.
    """
    parts: list[str] = []
    rest = text.strip()
    while len(rest) > limit:
        window = rest[:limit]
        cut = window.rfind("\n\n")
        if cut < limit // 2:
            cut = window.rfind("\n")
        if cut <= 0:
            cut = limit
        parts.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        parts.append(rest)
    return parts


def _post(payload: dict[str, Any]) -> tuple[bool, int | None, str]:
    """POST one sendMessage call. Returns (ok, http_code_or_None, detail)."""
    data = json.dumps(payload).encode("utf-8")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed api host
            ok = json.loads(resp.read().decode("utf-8")).get("ok", False)
        return (bool(ok), None, "" if ok else "telegram api rejected")
    except urllib.error.HTTPError as exc:
        # Telegram puts the real reason in the JSON body (e.g. "Forbidden: bot
        # can't initiate conversation with a user"); surface it, not just the code.
        try:
            desc = json.loads(exc.read().decode("utf-8")).get("description", "")
        except Exception:  # noqa: BLE001
            desc = ""
        return (False, exc.code, desc or exc.reason)
    except Exception as exc:  # noqa: BLE001 - a notification must never crash a run
        return (False, None, f"{type(exc).__name__}: {exc}")


def notify_plan(plan: str) -> dict[str, Any]:
    """Send the finished daily plan to the configured Telegram chat.

    Call this once at the very end of a daily run, after save_daily_plan, to
    deliver the plan to the user. If Telegram isn't configured, it is a no-op and
    the run still succeeds.

    The plan is rendered with Telegram Markdown (so ``*bold*`` headers and ``•``
    bullets display as formatting, not raw characters) and split across several
    messages when it exceeds Telegram's 4096-char limit. If a chunk's Markdown
    doesn't parse (a stray ``*``/``_`` in a ticker or number), it is resent as
    plain text so delivery still succeeds.

    Args:
        plan: The full daily plan text to deliver.

    Returns:
        A dict describing the outcome: ``{"sent": True, "messages": N}`` on
        success, ``{"sent": False, "skipped": ...}`` when unconfigured, or
        ``{"sent": False, "error": ...}`` on a delivery failure.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"sent": False, "skipped": "telegram not configured"}

    chunks = _split(plan)
    for chunk in chunks:
        base = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        ok, code, detail = _post({**base, "parse_mode": "Markdown"})
        if not ok and code == 400:
            # Markdown didn't parse; resend this chunk unformatted so the plan
            # still lands rather than failing the whole delivery.
            ok, code, detail = _post(base)
        if not ok:
            return {"sent": False, "error": f"HTTP {code}: {detail}" if code else detail}
    return {"sent": True, "messages": len(chunks)}
