"""Deterministic unit tests for Deskpilot tools and memory (no network, no LLM)."""
from __future__ import annotations

import json
import os

import pytest

from deskpilot.tools import market, portfolio
from deskpilot.tools.market import _num, _rsi, _sma


def test_num_sanitizes_nan_inf_and_none():
    # NaN/inf are invalid JSON and must become None (else Gemini 400s).
    assert _num(float("nan")) is None
    assert _num(float("inf")) is None
    assert _num(None) is None
    assert _num("x") is None
    assert _num(12.3456) == 12.35


def test_rsi_all_gains_saturates_to_100():
    assert _rsi(list(range(1, 30))) == 100.0


def test_rsi_needs_enough_data():
    assert _rsi([1, 2, 3]) is None


def test_sma_basic_and_insufficient():
    assert _sma([10, 20, 30], 3) == 20.0
    assert _sma([10, 20], 3) is None


def test_get_quote_handles_bad_ticker_without_raising(monkeypatch):
    # Force yfinance to blow up; the tool must return an error dict, not raise.
    import yfinance as yf

    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("network down")

    monkeypatch.setattr(yf, "Ticker", _Boom)
    result = market.get_quote("NVDA")
    assert result["ticker"] == "NVDA"
    assert "error" in result


def test_load_portfolio_reads_sample_and_derives_dte():
    snap = portfolio.load_portfolio()
    assert "error" not in snap
    assert snap["base_currency"] == "SGD"
    assert any(p["ticker"] == "NVDA" for p in snap["positions"])
    # days_to_expiry is derived at read time for every option.
    assert all("days_to_expiry" in o for o in snap["options"])


def test_load_portfolio_missing_file_returns_error(monkeypatch, tmp_path):
    monkeypatch.setattr(portfolio, "PORTFOLIO_SNAPSHOT", tmp_path / "nope.json")
    result = portfolio.load_portfolio()
    assert "error" in result


def test_build_snapshot_from_rows_splits_by_kind_and_coerces_types():
    # Simulates rows parsed from a published Google Sheet CSV.
    rows = [
        {"kind": "position", "broker": "Tiger", "ticker": "nvda", "qty": "40",
         "avg_cost": "118.2", "market_price": "217.55", "currency": "usd"},
        {"kind": "option", "broker": "Tiger", "ticker": "nvda", "type": "put",
         "strike": "220", "expiry": "2026-09-04", "qty": "-2",
         "action": "sell-to-open", "premium": "6.5", "currency": "usd"},
        {"kind": "cash", "currency": "sgd", "amount": "12,450"},
    ]
    snap = portfolio.build_snapshot_from_rows(rows)

    p = snap["positions"][0]
    assert p["ticker"] == "NVDA" and p["qty"] == 40 and p["currency"] == "USD"
    # unrealized_pl computed when not supplied
    assert p["unrealized_pl"] == round((217.55 - 118.2) * 40, 2)

    o = snap["options"][0]
    assert o["underlying"] == "NVDA" and o["type"] == "PUT"
    assert o["qty"] == -2 and o["strike"] == 220.0

    # comma-formatted amount parses; currency upper-cased
    assert snap["cash"]["SGD"] == 12450.0


def test_memory_roundtrip_local_backend(monkeypatch, tmp_path):
    # Rebuild the bank against a temp file with no GCP project -> local backend.
    from deskpilot.memory import store

    monkeypatch.setattr(store, "GCP_PROJECT", None)
    monkeypatch.setattr(store, "LOCAL_MEMORY_FILE", tmp_path / "mem.json")
    store._bank = store._MemoryBank()
    assert store._bank.backend == "local"

    assert store.remember("NVDA", "holding through earnings")["stored"] is True
    got = store.recall("NVDA")
    assert got["found"] is True and got["note"] == "holding through earnings"

    assert store.recall("UNKNOWN")["found"] is False

    store.save_daily_plan("watch NVDA, roll AAPL call")
    last = store.get_last_plan()
    assert last["found"] is True and "NVDA" in last["plan"]
