# Deskpilot

**An autonomous operator for your personal, multi-broker trading desk.**

Deskpilot turns a synced multi-broker portfolio into one prioritized daily plan.
Every morning it recalls yesterday's intent, reviews the live book for risk,
reads the technicals on the names that need a decision, sizes any options-income
setups, and writes a single plan back to its memory — unattended.

> **Read-only decision support.** Deskpilot never places, modifies, or cancels an
> order and gives no personalized buy/sell advice. It surfaces setups and
> reasoning; you decide and execute.

Built for the **All Things Agentic Hackathon** (Taskmaster category — "bring your
own friction": the daily desk routine).

---

## What it is (the agentic part)

Deskpilot is a **Google ADK** multi-agent system. An Orchestrator delegates to
three specialists via ADK agent-transfer, all running on **Gemini (≥ 3.5)**:

| Agent | Role | Tools |
|---|---|---|
| **deskpilot** (Orchestrator) | Runs the daily routine, delegates, synthesizes the plan | `load_portfolio`, `remember`, `recall`, `save_daily_plan`, `get_last_plan` |
| **RiskOfficer** | Reviews the live book: near-term expiries, concentration, P/L | `load_portfolio` |
| **MarketAnalyst** | Technical read per ticker (trend, RSI, ATR%, 52w position) | `get_quote` |
| **OptionsStrategist** | Sizes wheel / credit-spread income using implied expected move | `get_quote`, `get_expected_move` |

State persists in a **Firestore** memory bank (with a local-JSON fallback for
offline demos). Served on **Cloud Run** via ADK's FastAPI app.

## Mandatory tech (all three satisfied)

- **Gemini 3.5+** — every agent's model (`DESKPILOT_MODEL`), via Gemini API or Vertex AI.
- **Google Agent Framework** — Google ADK (`google-adk`), multi-agent orchestration.
- **Google Cloud infra** — Cloud Run (serving) + Firestore (memory bank).

## How it relates to broker-portfolio-sync

Deskpilot is the **agentic brain**; the deterministic
[`broker-portfolio-sync`](../broker-portfolio-sync) pipeline is the **data
backend**. That pipeline consolidates Longbridge + Tiger + MooMoo into one
normalized snapshot (common schema → FIFO P/L → FX → SGD); Deskpilot reads that
snapshot via `load_portfolio` and reasons over it. See
[SUBMISSION.md](SUBMISSION.md) for the incorporated-code disclosure.

```
broker-portfolio-sync  →  portfolio_snapshot.json  →  Deskpilot (ADK + Gemini)  →  daily plan (Firestore)
   (deterministic sync)         (data contract)            (agentic reasoning)
```

## Quickstart (local)

```bash
cd D:/Learn/Google/Deskpilot
py -3.14 -m pip install -r requirements.txt
cp .env.example .env        # then fill in GOOGLE_API_KEY + DESKPILOT_MODEL
py -3.14 -m pytest -q       # tools + memory tests (no key needed)
py -3.14 -m deskpilot.run "Run today's desk plan"   # needs a valid Gemini key
```

Or use the ADK dev UI:

```bash
py -3.14 server.py          # http://localhost:8080/dev-ui/
```

## Layout

```
Deskpilot/
├─ deskpilot/
│  ├─ agent.py         # ADK Orchestrator + 3 specialists (root_agent)
│  ├─ config.py        # env-driven config (model, auth, paths)
│  ├─ run.py           # CLI runner (streams tool calls + final plan)
│  ├─ tools/
│  │  ├─ market.py     # get_quote, get_expected_move (yfinance)
│  │  └─ portfolio.py  # load_portfolio (snapshot from broker-portfolio-sync)
│  └─ memory/store.py  # Firestore memory bank + local fallback
├─ server.py           # Cloud Run entrypoint (ADK FastAPI app)
├─ data/               # sample portfolio snapshot
├─ tests/              # deterministic unit tests
├─ Dockerfile
├─ DEPLOY.md           # Cloud Run + Firestore deploy
├─ SUBMISSION.md       # hackathon deliverables + disclosures
└─ docs/architecture.md
```

## License / disclosure

Personal hackathon project. Incorporates prior work by the same author
(`broker-portfolio-sync`, `nexus-concierge`) — disclosed in
[SUBMISSION.md](SUBMISSION.md). No credentials are committed; see `.gitignore`.
