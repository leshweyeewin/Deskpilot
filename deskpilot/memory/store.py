"""Deskpilot memory bank.

A thin persistence layer the agent uses to remember trade theses, watch items
and the last daily plan across runs. Backed by **Firestore** in production; when
Firestore is unavailable (no GCP project, package not installed, offline) it
falls back to a local JSON file so the agent still works in a demo.

Exposed as agent tools: ``remember``, ``recall``, ``save_daily_plan``,
``get_last_plan``.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..config import FIRESTORE_COLLECTION, GCP_PROJECT, LOCAL_MEMORY_FILE


class _MemoryBank:
    """Firestore-backed key/value memory with a local JSON fallback."""

    def __init__(self) -> None:
        self._client = None
        self._backend = "local"
        if GCP_PROJECT:
            try:
                from google.cloud import firestore  # type: ignore

                self._client = firestore.Client(project=GCP_PROJECT)
                self._backend = "firestore"
            except Exception:  # noqa: BLE001 - any failure -> local fallback
                self._client = None
                self._backend = "local"

    @property
    def backend(self) -> str:
        return self._backend

    # --- local JSON helpers ---
    def _read_local(self) -> dict[str, Any]:
        try:
            with open(LOCAL_MEMORY_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write_local(self, data: dict[str, Any]) -> None:
        with open(LOCAL_MEMORY_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    # --- public API ---
    def set(self, key: str, value: dict[str, Any]) -> None:
        value = {**value, "updated_at": datetime.now(timezone.utc).isoformat()}
        if self._client is not None:
            self._client.collection(FIRESTORE_COLLECTION).document(key).set(value)
        else:
            data = self._read_local()
            data[key] = value
            self._write_local(data)

    def get(self, key: str) -> dict[str, Any] | None:
        if self._client is not None:
            doc = self._client.collection(FIRESTORE_COLLECTION).document(key).get()
            return doc.to_dict() if doc.exists else None
        return self._read_local().get(key)


# Singleton so all tool calls share one backend within a process.
_bank = _MemoryBank()


def remember(topic: str, note: str) -> dict[str, Any]:
    """Persist a note under a topic so it survives to future runs.

    Use this to record a trade thesis, a watch item, or a decision the user made
    ("holding NVDA through earnings"), so tomorrow's Deskpilot run has context.

    Args:
        topic: Short key, e.g. "NVDA" or "watchlist" or "risk_rules".
        note: The free-text note to store.

    Returns:
        A dict confirming what was stored and which backend was used.
    """
    _bank.set(f"note::{topic}", {"topic": topic, "note": note})
    return {"stored": True, "topic": topic, "backend": _bank.backend}


def recall(topic: str) -> dict[str, Any]:
    """Retrieve the note previously stored for a topic.

    Args:
        topic: The key used with ``remember``, e.g. "NVDA".

    Returns:
        The stored note, or a ``found: false`` dict if nothing is stored.
    """
    doc = _bank.get(f"note::{topic}")
    if not doc:
        return {"found": False, "topic": topic}
    return {"found": True, **doc}


def save_daily_plan(plan: str) -> dict[str, Any]:
    """Persist today's finished daily desk plan.

    Call this once at the end of a daily run with the final plan text, so it can
    be recalled tomorrow to compare intent vs. what actually happened.

    Args:
        plan: The full daily plan text.

    Returns:
        A dict confirming the save and the date key used.
    """
    key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _bank.set(f"plan::{key}", {"date": key, "plan": plan})
    _bank.set("plan::latest", {"date": key, "plan": plan})
    return {"saved": True, "date": key, "backend": _bank.backend}


def get_last_plan() -> dict[str, Any]:
    """Retrieve the most recent saved daily plan.

    Use this at the start of a run to recall yesterday's plan before writing
    today's.

    Returns:
        The last plan dict, or a ``found: false`` dict if none is stored yet.
    """
    doc = _bank.get("plan::latest")
    if not doc:
        return {"found": False}
    return {"found": True, **doc}
