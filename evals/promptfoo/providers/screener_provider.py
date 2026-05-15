"""
promptfoo Python provider — screener_config_producer agent.
Called per test case by promptfoo 0.105.
Returns JSON string of the final streamed response.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "apps", "api"))

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, "apps", "api", ".env"))

os.environ.setdefault("SUPABASE_DB_URL", "postgresql://placeholder")
os.environ.setdefault("TRADINGVIEW_COOKIE", "")
os.environ.setdefault("API_SECRET_KEY", "test")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")


def call_api(prompt: str, options: dict, context: dict) -> dict:
    """promptfoo provider entry point."""
    vars_ = context.get("vars", {})
    user_input = str(vars_.get("prompt", prompt))

    async def _run() -> str:
        from app.agents.screener_config_producer import produce_config_stream
        final = None
        async with asyncio.timeout(30):
            async for event in produce_config_stream(user_input):
                if event["type"] == "final":
                    final = event
        return json.dumps(final or {"success": False, "message": "No final event received"})

    try:
        output = asyncio.run(_run())
        return {"output": output}
    except Exception as exc:
        return {"error": str(exc), "output": "{}"}
