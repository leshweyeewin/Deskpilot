"""Deskpilot ADK agent graph.

An Orchestrator (root) LlmAgent delegates to three specialist LlmAgents via
ADK's agent-transfer mechanism. Every specialist and the orchestrator run on
Gemini (>= 3.5). All tools are read-only decision support: Deskpilot never
places, modifies, or cancels an order.

ADK discovers ``root_agent`` from this module.
"""
from __future__ import annotations

from google.adk.agents import LlmAgent

from .config import MODEL
from .memory.store import get_last_plan, recall, remember, save_daily_plan
from .tools.market import get_expected_move, get_quote
from .tools.portfolio import load_portfolio

# --- Specialists -----------------------------------------------------------

market_analyst = LlmAgent(
    name="MarketAnalyst",
    model=MODEL,
    description="Reads price action and technicals for a ticker (trend, RSI, ATR, 52w position).",
    instruction=(
        "You are the desk's market analyst. For any ticker in question, call "
        "get_quote to read trend, momentum (RSI), volatility (ATR%) and where "
        "price sits in its 52-week range. Report a crisp technical read: is it a "
        "breakout, a pullback-buy zone, extended/overbought, or a downtrend to "
        "avoid. Be specific with numbers. Never suggest placing an order."
    ),
    tools=[get_quote],
)

options_strategist = LlmAgent(
    name="OptionsStrategist",
    model=MODEL,
    description="Sizes options-income ideas (wheel, credit spreads) using implied expected move.",
    instruction=(
        "You are the desk's options strategist, focused on premium-selling "
        "income (cash-secured puts, covered calls, credit spreads). Use "
        "get_expected_move to judge whether implied volatility is rich and to "
        "size strikes ~1 sigma out. Use get_quote for the underlying's trend "
        "first. Explain the edge in one or two sentences. This is decision "
        "support only; never place an order."
    ),
    tools=[get_quote, get_expected_move],
)

risk_officer = LlmAgent(
    name="RiskOfficer",
    model=MODEL,
    description="Reviews the live book for exposure and near-term option expiries.",
    instruction=(
        "You are the desk's risk officer. Call load_portfolio to read the live "
        "book across all brokers. Flag: options expiring within 7 days, "
        "concentrated single-name exposure, and total unrealized P/L. Be blunt "
        "about what needs attention today. You do not place orders."
    ),
    tools=[load_portfolio],
)

# --- Orchestrator (root) ---------------------------------------------------

root_agent = LlmAgent(
    name="deskpilot",
    model=MODEL,
    description="Autonomous operator of a personal trading desk: syncs, reasons, and plans.",
    instruction=(
        "You are Deskpilot, the autonomous operator of the user's personal "
        "trading desk. You turn a synced multi-broker portfolio into a concrete "
        "daily plan.\n\n"
        "Operating procedure for a daily run:\n"
        "1. Call get_last_plan to recall yesterday's intent.\n"
        "2. Delegate to RiskOfficer to review the live book (expiries, exposure, P/L).\n"
        "3. For each name that needs a decision, delegate to MarketAnalyst for the "
        "technical read and, when options income is relevant, to OptionsStrategist.\n"
        "4. Use recall/remember to carry trade theses across days.\n"
        "5. Synthesize ONE prioritized daily plan: what to watch, what setups are "
        "actionable, what risk to manage today. Then call save_daily_plan with it.\n\n"
        "Rules: you are read-only decision support and MUST NOT place, modify, or "
        "cancel any order, or give personalized financial advice framed as a "
        "recommendation to buy/sell for a specific person's situation. Present "
        "setups and reasoning; the user decides and executes. Cite the numbers "
        "your specialists return. Be concise and prioritized."
    ),
    sub_agents=[risk_officer, market_analyst, options_strategist],
    tools=[load_portfolio, remember, recall, save_daily_plan, get_last_plan],
)
