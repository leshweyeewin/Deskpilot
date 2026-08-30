"""Portfolio snapshot tool.

In production the daily portfolio snapshot is produced by the
`broker-portfolio-sync` pipeline (three brokers -> common schema -> FIFO P/L ->
Google Sheet), exported to JSON. Deskpilot only *reads* it. For local demos a
sample snapshot ships under data/.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from ..config import PORTFOLIO_SNAPSHOT


def load_portfolio() -> dict[str, Any]:
    """Load the current consolidated portfolio snapshot.

    Use this first when the user asks anything about their book: positions,
    exposure, cash, unrealized P/L, or options expiring soon. Returns holdings
    across all linked brokers already normalized to one schema and one currency.

    Returns:
        A dict with ``as_of``, ``base_currency``, ``cash``, a list of
        ``positions`` (ticker, qty, avg_cost, market_price, unrealized_pl), and
        a list of ``options`` (underlying, type, strike, expiry, qty,
        days_to_expiry). On failure, an ``error`` key.
    """
    try:
        with open(PORTFOLIO_SNAPSHOT, "r", encoding="utf-8") as fh:
            snapshot = json.load(fh)
    except FileNotFoundError:
        return {"error": f"no snapshot at {PORTFOLIO_SNAPSHOT}"}
    except json.JSONDecodeError as exc:
        return {"error": f"snapshot is not valid JSON: {exc}"}

    # Derive days_to_expiry for each option relative to today so the RiskOfficer
    # can flag near-term expiries without the snapshot needing to be regenerated.
    today = date.today()
    for opt in snapshot.get("options", []):
        exp = opt.get("expiry")
        if exp:
            try:
                dte = (date.fromisoformat(exp) - today).days
                opt["days_to_expiry"] = dte
            except ValueError:
                opt["days_to_expiry"] = None
    return snapshot


def _sample_snapshot() -> dict[str, Any]:
    """Generate a realistic sample snapshot (used to seed data/ on first run)."""
    today = date.today()
    return {
        "as_of": today.isoformat(),
        "base_currency": "SGD",
        "cash": {"SGD": 12450.00, "USD": 3120.55},
        "positions": [
            {"broker": "Longbridge", "ticker": "NVDA", "qty": 40, "avg_cost": 118.20,
             "market_price": 172.40, "currency": "USD", "unrealized_pl": 2168.0},
            {"broker": "Tiger", "ticker": "AAPL", "qty": 60, "avg_cost": 214.10,
             "market_price": 229.85, "currency": "USD", "unrealized_pl": 945.0},
            {"broker": "MooMoo", "ticker": "GOOGL", "qty": 25, "avg_cost": 168.90,
             "market_price": 201.30, "currency": "USD", "unrealized_pl": 810.0},
        ],
        "options": [
            {"broker": "Tiger", "underlying": "NVDA", "type": "PUT", "strike": 160,
             "expiry": (today + timedelta(days=4)).isoformat(), "qty": -2,
             "action": "sell-to-open", "premium": 3.10, "currency": "USD"},
            {"broker": "Longbridge", "underlying": "AAPL", "type": "CALL", "strike": 240,
             "expiry": (today + timedelta(days=25)).isoformat(), "qty": -1,
             "action": "sell-to-open", "premium": 4.55, "currency": "USD"},
        ],
    }
