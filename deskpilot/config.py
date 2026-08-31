"""Central configuration for Deskpilot.

All knobs are environment-driven so the same code runs locally, in tests, and on
Cloud Run without edits. Values are read once at import time.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load a local .env when present (no-op in Cloud Run, where env is injected).
load_dotenv()

# --- Model -----------------------------------------------------------------
# The hackathon requires Gemini 3.5 or newer. Override with DESKPILOT_MODEL to
# match whatever model id your project has access to (Gemini API or Vertex AI).
MODEL: str = os.getenv("DESKPILOT_MODEL", "gemini-3.5-flash")

# ADK/GenAI pick Vertex vs. API key from these standard env vars:
#   GOOGLE_GENAI_USE_VERTEXAI=TRUE  + GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION
#   GOOGLE_GENAI_USE_VERTEXAI=FALSE + GOOGLE_API_KEY
USE_VERTEX: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
GCP_PROJECT: str | None = os.getenv("GOOGLE_CLOUD_PROJECT")

# --- App identity ----------------------------------------------------------
APP_NAME: str = "deskpilot"

# --- Data / memory ---------------------------------------------------------
ROOT_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = Path(os.getenv("DESKPILOT_DATA_DIR", ROOT_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Firestore collection for the agent memory bank. When Firestore is unavailable
# (no project / package), the memory layer falls back to a local JSON file.
FIRESTORE_COLLECTION: str = os.getenv("DESKPILOT_FIRESTORE_COLLECTION", "deskpilot_memory")
LOCAL_MEMORY_FILE: Path = DATA_DIR / "memory_fallback.json"

# --- Portfolio source ------------------------------------------------------
# Preferred source: a published Google Sheet, read as CSV over its public link
# (File -> Share -> Publish to web -> CSV). No credentials required, so anyone --
# including a judge with their own sheet -- can point Deskpilot at their data by
# setting just this one env var. When unset, load_portfolio uses the JSON sample.
PORTFOLIO_CSV_URL: str | None = os.getenv("DESKPILOT_PORTFOLIO_CSV_URL")

# Base reporting currency for the snapshot (positions stay in their own currency).
BASE_CURRENCY: str = os.getenv("DESKPILOT_BASE_CURRENCY", "SGD")

# Offline fallback: a JSON snapshot. Used when no CSV URL is configured (tests,
# local demos with no network). A sample ships under data/.
PORTFOLIO_SNAPSHOT: Path = Path(
    os.getenv("DESKPILOT_PORTFOLIO_SNAPSHOT", DATA_DIR / "portfolio_snapshot.sample.json")
)

# --- Notifications (optional) ----------------------------------------------
# Deliver the finished daily plan to a Telegram chat via the Bot API. Both are
# optional: when unset, notify_plan is a graceful no-op, so the agent still runs
# everywhere. The token is a secret (Secret Manager in prod); the chat id is not.
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str | None = os.getenv("TELEGRAM_CHAT_ID")
