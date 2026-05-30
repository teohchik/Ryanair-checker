"""Admin Telegram alerts for every error/critical log event.

Architecture:
  - admin_alert_processor  — structlog processor; catches every log.error() call
  - set_alert_sink()       — wired to notifier.notify_admin at startup
  - dispatch()             — sync; schedules the send as an asyncio task
  - _in_alert ContextVar   — recursion guard so a failed send doesn't loop
  - _last_sent + cooldown  — 300 s per-event throttle to avoid floods
"""
from __future__ import annotations

import asyncio
import html
import time
import traceback as tb
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

_sink: Callable[[str], Awaitable[None]] | None = None
_in_alert: ContextVar[bool] = ContextVar("_in_alert", default=False)
_last_sent: dict[str, float] = {}
_COOLDOWN = 300  # seconds


def set_alert_sink(fn: Callable[[str], Awaitable[None]]) -> None:
    """Call once at startup with notifier.notify_admin."""
    global _sink
    _sink = fn


async def _run(text: str) -> None:
    token = _in_alert.set(True)
    try:
        if _sink is not None:
            await _sink(text[:4000])
    except Exception:
        pass  # never let alerting crash anything
    finally:
        _in_alert.reset(token)


def dispatch(text: str, dedupe_key: str) -> None:
    """Schedule an admin alert, respecting throttle and recursion guard."""
    if _sink is None or _in_alert.get():
        return
    now = time.monotonic()
    if now - _last_sent.get(dedupe_key, 0) < _COOLDOWN:
        return
    _last_sent[dedupe_key] = now
    # Prune to avoid unbounded growth
    if len(_last_sent) > 500:
        oldest_key = min(_last_sent, key=lambda k: _last_sent[k])
        del _last_sent[oldest_key]
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # no loop yet (startup logging) — silently skip
    loop.create_task(_run(text))


def admin_alert_processor(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Structlog processor: sends Telegram alert on error/critical events."""
    if event_dict.get("level") not in ("error", "critical") or _in_alert.get():
        return event_dict

    level = event_dict["level"].upper()
    event = html.escape(str(event_dict.get("event", "")))

    # Extra fields (skip internal structlog keys and the raw exception object)
    skip = {"level", "event", "timestamp", "_record", "exc_info", "exception"}
    extras = "\n".join(
        f"  {html.escape(str(k))}: <code>{html.escape(str(v))}</code>"
        for k, v in event_dict.items()
        if k not in skip
    )

    # Traceback — structlog.processors.format_exc_info converts exc_info into
    # an "exception" string field before this processor runs.
    exc_text = event_dict.get("exception", "")
    if exc_text:
        tail = "\n".join(exc_text.splitlines()[-12:])
        exc_block = f"\n<pre>{html.escape(tail)}</pre>"
    else:
        exc_block = ""

    parts = [f"🚨 <b>Bot {level}</b>", f"<b>{event}</b>"]
    if extras:
        parts.append(extras)
    if exc_block:
        parts.append(exc_block)

    text = "\n".join(parts)
    dedupe_key = f"{event_dict.get('event', '')}:{str(event_dict.get('error', ''))[:50]}"
    dispatch(text, dedupe_key)

    return event_dict
