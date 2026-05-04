"""
Screener Config Producer agent.
Converts natural language screening criteria into a ScreenerConfig.
Streams chunks back to the client.
"""
from __future__ import annotations
import json
import logging
from typing import AsyncGenerator

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)
client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=0)

# Embedded field reference extracted from tradingview-scraper + TradingView API
SCREENER_FIELD_REFERENCE = """
AVAILABLE SCREENER FIELDS (tradingview-scraper):

Filters use: {"left": "<field>", "operation": "<op>", "right": <value>}

Operations: greater, less, equal, nequal, egreater, eless, in_range, not_in_range,
            crosses, crosses_above, crosses_below, above, below, has, has_none_of

PRICE & VOLUME:
  close                     — Previous close price (USD)
  premarket_close           — Current pre-market price
  premarket_change          — Pre-market change % (e.g. 5 = 5%)
  premarket_change_abs      — Pre-market change absolute ($)
  premarket_volume          — Pre-market volume (shares)
  volume                    — Previous session volume
  relative_volume           — Relative volume vs 20-day avg (e.g. 5 = 5x)
  average_volume_10d_calc   — 10-day avg volume
  average_volume_30d_calc   — 30-day avg volume
  gap                       — Gap % at open vs prev close

FUNDAMENTALS:
  market_cap_basic          — Market cap (raw, in USD)
  market_cap_calc           — Market cap calculated
  float_shares_outstanding  — Share float (shares, not millions)
  shares_outstanding        — Total shares outstanding
  price_earnings_ttm        — P/E ratio TTM
  earnings_per_share_basic_ttm — EPS TTM
  revenue_per_employee      — Revenue per employee

CLASSIFICATION:
  type                      — Asset type: "stock", "dr", "fund"
  exchange                  — Exchange: "NASDAQ", "NYSE", "AMEX", etc.
  sector                    — Sector string (e.g. "Technology")
  country                   — Country code (e.g. "US")

TECHNICAL:
  Recommend.All             — Overall technical rating (-1 to 1)
  RSI                       — RSI(14)
  MACD.macd                 — MACD line

MARKETS: america, australia, canada, germany, india, uk, crypto, forex

SORT FIELDS: same as filter fields above

RESULT COLUMNS: same as filter fields above, plus:
  name, description, exchange, sector

EXAMPLE CONFIG:
{
  "name": "PM Gainers >3% Small Cap",
  "scan_type": "premarket_gainers",
  "market": "america",
  "filters": [
    {"left": "premarket_change", "operation": "greater", "right": 3},
    {"left": "market_cap_basic", "operation": "less", "right": 1000000000},
    {"left": "type", "operation": "equal", "right": "stock"},
    {"left": "exchange", "operation": "equal", "right": "NASDAQ"}
  ],
  "sort_by": "premarket_change",
  "sort_order": "desc",
  "result_limit": 20
}
"""

SYSTEM_PROMPT = f"""You are a screener configuration assistant for a stock gap/pre-market scanning app.

{SCREENER_FIELD_REFERENCE}

Your job:
1. Parse the user's natural language screening criteria
2. Map each criterion to available fields
3. If ALL criteria can be expressed → return a valid JSON config
4. If some criteria CANNOT be expressed → explain what is missing/unsupported

IMPORTANT RULES:
- market_cap under $1B → "right": 1000000000 (use raw USD, not millions)
- float shares → always in raw shares (e.g. 20M float = 20000000)
- Only use fields from the reference above
- Include "type": "stock" filter unless user explicitly wants ETFs/warrants too
- respond with a JSON block for the config OR a clear explanation of what's missing

Response format when config is buildable:
{{
  "success": true,
  "config": {{ ...ScreenerConfig fields... }},
  "message": "Config ready — review and confirm to save."
}}

Response format when not fully buildable:
{{
  "success": false,
  "missing_criteria": ["...", "..."],
  "message": "Some criteria cannot be expressed: ..."
}}"""


async def produce_config_stream(user_input: str) -> AsyncGenerator[dict, None]:
    """Stream the NL → config conversion."""
    full_text = ""
    try:
        async with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_input}],
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        ) as stream:
            async for text in stream.text_stream:
                full_text += text
                yield {"type": "chunk", "text": text}

        # Parse final JSON from streamed text
        result = _extract_json(full_text)
        yield {"type": "final", **result}

    except Exception as exc:
        logger.exception("Screener config producer failed")
        yield {"type": "error", "message": str(exc)}


def _extract_json(text: str) -> dict:
    """Extract JSON block from Claude's response."""
    try:
        # Try to find JSON in code block
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Try bare JSON
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except json.JSONDecodeError:
        pass
    return {"success": False, "message": text, "missing_criteria": []}
