"""
promptfoo Python provider — news_analyser agent.
Called per test case by promptfoo 0.105.
Returns JSON string of the agent's structured output.
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

    async def _run() -> str:
        from app.agents.news_analyser import _call_claude
        result = await _call_claude(
            ticker=str(vars_.get("ticker", "UNKNOWN")),
            company_name=str(vars_.get("company", "Unknown Company")),
            premarket_change_pct=float(vars_.get("pct", 0)),
            news_url=None,
            news_title=str(vars_.get("title", "")),
            news_content=str(vars_.get("text", "")),
            web_search_used=False,
        )
        return json.dumps({
            "catalyst_type": result.catalyst_type,
            "sentiment": result.sentiment,
            "trading_signal": result.trading_signal,
            "analysis_text": result.analysis_text,
        })

    try:
        output = asyncio.run(_run())
        return {"output": output}
    except Exception as exc:
        return {"error": str(exc), "output": "{}"}
