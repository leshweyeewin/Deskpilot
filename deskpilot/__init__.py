"""Deskpilot: an autonomous operator for a personal, multi-broker trading desk.

Built on Google ADK + Gemini, deployed on Cloud Run with a Firestore memory
bank. Read-only decision support only -- never places orders.
"""
from . import agent  # noqa: F401  (ADK discovers root_agent via this import)

__all__ = ["agent"]
