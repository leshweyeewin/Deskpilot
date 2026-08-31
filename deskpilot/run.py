"""Local CLI runner for Deskpilot.

    py -3.14 -m deskpilot.run "Run today's desk plan"
    py -3.14 -m deskpilot.run            # uses the default daily-run prompt

Streams tool calls and agent transfers to the console, then prints the final
plan. Requires a valid Gemini model + credentials in the environment (.env).
"""
from __future__ import annotations

import asyncio
import sys
import time

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import errors as genai_errors
from google.genai import types

from .agent import root_agent
from .config import APP_NAME, MODEL

DEFAULT_PROMPT = (
    "Run today's daily desk routine: review my book, check the names that need a "
    "decision, and give me one prioritized plan for today. Save the plan when done."
)

# A daily run makes many Gemini calls (orchestrator + each specialist), so under
# load any one can return a transient 503 ("high demand"). Retry the whole run
# with exponential backoff. Only *transient* failures are retried; a real config
# error (e.g. 403 PERMISSION_DENIED) fails fast.
_MAX_ATTEMPTS = 5
_RETRYABLE = ("503", "unavailable", "overloaded", "high demand", "resource_exhausted", "429")


def _is_transient(exc: BaseException) -> bool:
    """A 5xx/overload we should retry — not a config/auth error we shouldn't."""
    if isinstance(exc, genai_errors.ServerError):
        return True
    return any(s in str(exc).lower() for s in _RETRYABLE)


async def _run(prompt: str) -> bool:
    """Run one daily routine. Returns True if a final plan was produced."""
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    await session_service.create_session(app_name=APP_NAME, user_id="local", session_id="cli")

    produced = False
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for event in runner.run_async(user_id="local", session_id="cli", new_message=message):
        author = getattr(event, "author", "?")
        for part in (event.content.parts if event.content else []):
            if getattr(part, "function_call", None):
                print(f"  [{author} -> tool] {part.function_call.name}({dict(part.function_call.args or {})})")
            elif getattr(part, "function_response", None):
                print(f"  [tool -> {author}] {part.function_response.name} returned")
        if event.is_final_response() and event.content and event.content.parts:
            text = event.content.parts[0].text
            if text:
                print("\n=== Deskpilot daily plan ===\n")
                print(text)
                produced = True
    return produced


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip() or DEFAULT_PROMPT
    print(f"Deskpilot :: model={MODEL}\nPrompt: {prompt}\n")
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        # A mid-run 503 can surface either as a raised error or as a run that ends
        # without a plan (ADK swallows it as a "node failure") -- retry both.
        try:
            if asyncio.run(_run(prompt)):
                return
            failure = "run ended without a final plan (likely a transient model error)"
        except Exception as exc:  # noqa: BLE001
            if not _is_transient(exc):
                raise  # config/auth error -> fail fast, don't mask it
            failure = f"{type(exc).__name__}: {exc}"

        if attempt == _MAX_ATTEMPTS:
            print(f"\nGave up after {_MAX_ATTEMPTS} attempts. Last: {failure}", file=sys.stderr)
            sys.exit(1)
        wait = 2 ** attempt  # 2s, 4s, 8s, 16s
        print(f"\n{failure}\nRetrying in {wait}s (attempt {attempt}/{_MAX_ATTEMPTS})...",
              file=sys.stderr)
        time.sleep(wait)


if __name__ == "__main__":
    main()
