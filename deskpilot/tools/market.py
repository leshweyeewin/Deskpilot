"""Market-data tools exposed to the Deskpilot agents.

These wrap public market data (yfinance) into small, deterministic, LLM-callable
functions. They never place or modify orders — everything here is read-only
decision support. Each function is defensive: on any data/network failure it
returns a dict with an ``error`` key rather than raising, so the agent can
reason about the failure instead of crashing the run.
"""
from __future__ import annotations

from typing import Any


def _rsi(closes: list[float], period: int = 14) -> float | None:
    """Classic Wilder RSI over a list of closing prices."""
    if len(closes) <= period:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains += max(diff, 0.0)
        losses += max(-diff, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(diff, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-diff, 0.0)) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 1)


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return round(sum(values[-window:]) / window, 2)


def get_quote(ticker: str) -> dict[str, Any]:
    """Return a technical snapshot for one ticker.

    Use this to judge trend, momentum and where price sits in its yearly range
    before proposing any trade. Covers the technical read a swing trader needs.

    Args:
        ticker: The stock symbol, e.g. "NVDA" or "AAPL".

    Returns:
        A dict with price, SMA20/50/200, RSI(14), ATR%, the 52-week high/low
        position, and a plain-language ``trend`` label. On failure the dict
        contains an ``error`` key describing what went wrong.
    """
    symbol = ticker.strip().upper()
    try:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=True)
        if hist is None or hist.empty:
            return {"ticker": symbol, "error": "no price history returned"}

        closes = [float(c) for c in hist["Close"].tolist()]
        highs = [float(h) for h in hist["High"].tolist()]
        lows = [float(low) for low in hist["Low"].tolist()]
        price = round(closes[-1], 2)

        sma20, sma50, sma200 = _sma(closes, 20), _sma(closes, 50), _sma(closes, 200)
        rsi = _rsi(closes)

        # ATR% (14): mean true range over last 14 bars, as a % of price.
        trs: list[float] = []
        for i in range(max(1, len(closes) - 14), len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        atr_pct = round((sum(trs) / len(trs)) / price * 100, 2) if trs and price else None

        hi_52 = round(max(highs), 2)
        lo_52 = round(min(lows), 2)
        rng = hi_52 - lo_52
        pos_52 = round((price - lo_52) / rng * 100, 1) if rng else None

        # Plain-language trend label from the MA stack + RSI.
        trend = "undefined"
        if sma20 and sma50 and sma200:
            if sma20 > sma50 > sma200 and price > sma20:
                trend = "strong uptrend"
            elif sma20 > sma50 and price > sma50:
                trend = "uptrend"
            elif price < sma20 < sma50:
                trend = "downtrend"
            else:
                trend = "range / base"
        if rsi is not None and rsi > 75:
            trend += " (overbought)"

        return {
            "ticker": symbol,
            "price": price,
            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,
            "rsi14": rsi,
            "atr_pct": atr_pct,
            "high_52w": hi_52,
            "low_52w": lo_52,
            "pct_of_52w_range": pos_52,
            "trend": trend,
        }
    except Exception as exc:  # noqa: BLE001 - surface any failure to the agent
        return {"ticker": symbol, "error": f"{type(exc).__name__}: {exc}"}


def get_expected_move(ticker: str) -> dict[str, Any]:
    """Estimate the options-implied expected move for the nearest expiry.

    Use this before earnings or event-driven trades to size a credit spread or
    judge whether premium is rich. The estimate is the at-the-money straddle
    price as a percentage of spot (a standard ~1 sigma expected-move proxy).

    Args:
        ticker: The stock symbol, e.g. "NVDA".

    Returns:
        A dict with the expiry used, spot, ATM straddle price, and the expected
        move in dollars and percent. On failure, an ``error`` key.
    """
    symbol = ticker.strip().upper()
    try:
        import yfinance as yf

        tk = yf.Ticker(symbol)
        expiries = tk.options
        if not expiries:
            return {"ticker": symbol, "error": "no option expiries available"}
        expiry = expiries[0]
        chain = tk.option_chain(expiry)

        spot_hist = tk.history(period="1d")
        if spot_hist is None or spot_hist.empty:
            return {"ticker": symbol, "error": "no spot price"}
        spot = float(spot_hist["Close"].iloc[-1])

        calls, puts = chain.calls, chain.puts
        if calls.empty or puts.empty:
            return {"ticker": symbol, "error": "empty option chain"}

        atm_call = calls.iloc[(calls["strike"] - spot).abs().argsort().iloc[0]]
        atm_put = puts.iloc[(puts["strike"] - spot).abs().argsort().iloc[0]]
        straddle = float(atm_call["lastPrice"]) + float(atm_put["lastPrice"])
        move_pct = round(straddle / spot * 100, 2) if spot else None

        return {
            "ticker": symbol,
            "expiry": expiry,
            "spot": round(spot, 2),
            "atm_strike": round(float(atm_call["strike"]), 2),
            "straddle_price": round(straddle, 2),
            "expected_move_usd": round(straddle, 2),
            "expected_move_pct": move_pct,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ticker": symbol, "error": f"{type(exc).__name__}: {exc}"}
