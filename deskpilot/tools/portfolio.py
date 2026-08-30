"""Portfolio snapshot tool.

Deskpilot reads the current book from a **published Google Sheet** (read as CSV
over its public link) when ``DESKPILOT_PORTFOLIO_CSV_URL`` is set. No credentials
are needed, so anyone -- including a judge with their own sheet -- can point
Deskpilot at their data by setting that one env var. When it's unset, the loader
falls back to a JSON snapshot so tests and offline demos run with no network.
Deskpilot only ever *reads*.

Expected sheet columns (first row = header). One row per holding; the ``kind``
column selects how the row is read:
  kind=position : broker | ticker | qty | avg_cost | market_price | currency
  kind=option   : broker | ticker(=underlying) | type | strike | expiry | qty | action | premium | currency
  kind=cash     : currency | amount
Unused cells in a row can be left blank.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.request
from datetime import date, timedelta
from typing import Any

from ..config import BASE_CURRENCY, PORTFOLIO_CSV_URL, PORTFOLIO_SNAPSHOT


def load_portfolio() -> dict[str, Any]:
    """Load the current consolidated portfolio snapshot.

    Use this first when the user asks anything about their book: positions,
    exposure, cash, unrealized P/L, or options expiring soon. Returns holdings
    across all brokers, normalized to one schema.

    Returns:
        A dict with ``as_of``, ``base_currency``, ``cash``, a list of
        ``positions`` (ticker, qty, avg_cost, market_price, unrealized_pl), and
        a list of ``options`` (underlying, type, strike, expiry, qty,
        days_to_expiry). On failure, an ``error`` key.
    """
    snapshot = _load_from_csv(PORTFOLIO_CSV_URL) if PORTFOLIO_CSV_URL else _load_from_json()
    if "error" in snapshot:
        return snapshot
    _derive_days_to_expiry(snapshot)
    return snapshot


# --- JSON fallback ---------------------------------------------------------

def _load_from_json() -> dict[str, Any]:
    try:
        with open(PORTFOLIO_SNAPSHOT, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"error": f"no snapshot at {PORTFOLIO_SNAPSHOT}"}
    except json.JSONDecodeError as exc:
        return {"error": f"snapshot is not valid JSON: {exc}"}


# --- Published-CSV (Google Sheet) source -----------------------------------

def _load_from_csv(url: str) -> dict[str, Any]:
    """Fetch a published-sheet CSV and assemble a snapshot. Never raises."""
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310 - user-configured URL
            text = resp.read().decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
        return build_snapshot_from_rows(rows)
    except Exception as exc:  # noqa: BLE001 - surface any failure to the agent
        return {"error": f"could not read portfolio CSV: {type(exc).__name__}: {exc}"}


def build_snapshot_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Split flat CSV rows (by ``kind``) into a normalized snapshot (pure/testable)."""
    positions, options, cash = [], [], []
    for r in rows:
        kind = (r.get("kind") or "").strip().lower()
        if kind == "position":
            positions.append(r)
        elif kind == "option":
            options.append({**r, "underlying": r.get("ticker")})
        elif kind == "cash":
            cash.append(r)
    return build_snapshot(positions, options, cash)


def build_snapshot(
    positions: list[dict[str, Any]],
    options: list[dict[str, Any]],
    cash: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the normalized snapshot from parsed rows (pure/testable)."""
    pos_out = []
    for r in positions:
        qty = _int(r.get("qty"))
        avg = _float(r.get("avg_cost"))
        mkt = _float(r.get("market_price"))
        upl = r.get("unrealized_pl")
        unrealized = _float(upl) if upl not in (None, "") else (
            round((mkt - avg) * qty, 2) if None not in (qty, avg, mkt) else None
        )
        pos_out.append({
            "broker": (r.get("broker") or "").strip(),
            "ticker": (r.get("ticker") or "").strip().upper(),
            "qty": qty,
            "avg_cost": avg,
            "market_price": mkt,
            "currency": (r.get("currency") or "USD").strip().upper(),
            "unrealized_pl": unrealized,
        })

    opt_out = []
    for r in options:
        opt_out.append({
            "broker": (r.get("broker") or "").strip(),
            "underlying": (r.get("underlying") or "").strip().upper(),
            "type": (r.get("type") or "").strip().upper(),
            "strike": _float(r.get("strike")),
            "expiry": (r.get("expiry") or "").strip(),
            "qty": _int(r.get("qty")),
            "action": (r.get("action") or "").strip(),
            "premium": _float(r.get("premium")),
            "currency": (r.get("currency") or "USD").strip().upper(),
        })

    cash_out: dict[str, float] = {}
    for r in cash:
        cur = (r.get("currency") or "").strip().upper()
        amt = _float(r.get("amount"))
        if cur and amt is not None:
            cash_out[cur] = amt

    return {
        "as_of": date.today().isoformat(),
        "base_currency": BASE_CURRENCY,
        "cash": cash_out,
        "positions": pos_out,
        "options": opt_out,
    }


def _derive_days_to_expiry(snapshot: dict[str, Any]) -> None:
    """Add days_to_expiry to each option relative to today (in place)."""
    today = date.today()
    for opt in snapshot.get("options", []):
        exp = opt.get("expiry")
        if exp:
            try:
                opt["days_to_expiry"] = (date.fromisoformat(exp) - today).days
            except ValueError:
                opt["days_to_expiry"] = None


def _float(x: Any) -> float | None:
    try:
        return round(float(str(x).replace(",", "").strip()), 4)
    except (TypeError, ValueError):
        return None


def _int(x: Any) -> int | None:
    f = _float(x)
    return int(f) if f is not None else None


def _sample_snapshot() -> dict[str, Any]:
    """Generate a realistic sample snapshot (used to seed data/ on first run)."""
    today = date.today()
    return {
        "as_of": today.isoformat(),
        "base_currency": BASE_CURRENCY,
        "cash": {"SGD": 12450.00, "USD": 3120.55},
        "positions": [
            {"broker": "Longbridge", "ticker": "NVDA", "qty": 40, "avg_cost": 118.20,
             "market_price": 217.55, "currency": "USD", "unrealized_pl": 3974.0},
            {"broker": "Tiger", "ticker": "AAPL", "qty": 60, "avg_cost": 214.10,
             "market_price": 319.70, "currency": "USD", "unrealized_pl": 6336.0},
            {"broker": "MooMoo", "ticker": "GOOGL", "qty": 25, "avg_cost": 168.90,
             "market_price": 346.59, "currency": "USD", "unrealized_pl": 4442.25},
        ],
        "options": [
            {"broker": "Tiger", "underlying": "NVDA", "type": "PUT", "strike": 220,
             "expiry": (today + timedelta(days=4)).isoformat(), "qty": -2,
             "action": "sell-to-open", "premium": 6.50, "currency": "USD"},
            {"broker": "Longbridge", "underlying": "AAPL", "type": "CALL", "strike": 330,
             "expiry": (today + timedelta(days=24)).isoformat(), "qty": -1,
             "action": "sell-to-open", "premium": 5.20, "currency": "USD"},
        ],
    }
