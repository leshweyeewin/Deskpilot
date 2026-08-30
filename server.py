"""Cloud Run entrypoint for Deskpilot.

Serves the ADK web UI + REST API (/run, /run_sse, /list-apps, plus the dev UI at
/dev-ui) for the agents discovered under this directory. The ``deskpilot``
package exposes ``root_agent``, so ADK finds it as app name "deskpilot".

Run locally:
    py -3.14 server.py
Then open http://localhost:8080/dev-ui/
"""
from __future__ import annotations

import os

import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

# The agents directory is this file's directory: it contains the ``deskpilot``
# package (an importable agent module exposing root_agent).
AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Optional: persist ADK sessions in Cloud SQL / Firestore by setting
# DESKPILOT_SESSION_URI (e.g. a Cloud SQL connection string). Defaults to
# in-memory sessions, which is fine for the demo.
SESSION_URI = os.getenv("DESKPILOT_SESSION_URI") or None

app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    session_service_uri=SESSION_URI,
    web=True,
    allow_origins=["*"],
)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
