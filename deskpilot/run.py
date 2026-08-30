"""Local CLI runner for Deskpilot.

    py -3.14 -m deskpilot.run "Run today's desk plan"
    py -3.14 -m deskpilot.run            # uses the default daily-run prompt

Streams tool calls and agent transfers to the console, then prints the final
plan. Requires a valid Gemini model + credentials in the environment (.env).
"""
from __future__ import annotations

import asyncio
import sys

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .agent import root_agent
from .config import APP_NAME, MODEL

DEFAULT_PROMPT = (
    "Run today's daily desk routine: review my book, check the names that need a "
    "decision, and give me one prioritized plan for today. Save the plan when done."
)


async def _run(prompt: str) -> None:
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    await session_service.create_session(app_name=APP_NAME, user_id="local", session_id="cli")

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


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip() or DEFAULT_PROMPT
    print(f"Deskpilot :: model={MODEL}\nPrompt: {prompt}\n")
    asyncio.run(_run(prompt))


if __name__ == "__main__":
    main()
