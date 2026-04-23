"""
News Analyser agent.
Reads a news URL, classifies the catalyst, returns structured result.
Falls back to web search if no news URL is provided.
Logic mirrors catalyst_analyzer.py from episodic-pivots-ai.
"""
from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass

import anthropic
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

POSITIVE_CATALYSTS = [
    "earnings_beat", "guidance_raise", "contract_win", "partnership",
    "analyst_upgrade", "fda_approval", "merger_acquisition_target",
    "buyback", "dividend_initiation", "product_launch",
]
NEGATIVE_CATALYSTS = [
    "earnings_miss", "guidance_cut", "dilution", "legal_issue",
    "analyst_downgrade", "fda_rejection", "ceo_resignation",
    "accounting_irregularity",
]
ALL_CATALYSTS = POSITIVE_CATALYSTS + NEGATIVE_CATALYSTS + ["none"]

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "catalyst_type": {"type": "string", "enum": ALL_CATALYSTS},
        "sentiment": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "trading_signal": {
            "type": "string",
            "enum": ["strong_buy", "buy", "watch", "skip", "short", "strong_short"],
        },
        "analysis_text": {"type": "string"},
        "news_title": {"type": "string"},
    },
    "required": ["catalyst_type", "sentiment", "trading_signal", "analysis_text"],
}

SYSTEM_PROMPT = """You are a professional stock analyst specialising in gap-and-go and pre-market momentum plays.

Analyse the provided news/context and determine:
1. The primary catalyst type driving the gap
2. Whether the catalyst is a genuine fundamental driver (not just noise)
3. The likely direction of sustained price movement

Rules:
- Dilution (ATM offering, shelf registration, direct offering) → trading_signal: skip (for longs)
- Takeover/buyout target → trading_signal: skip (gap already priced in)
- Genuine earnings beat with raised guidance → strong_buy
- Revenue miss even if EPS beat → watch or skip
- FDA approval of major drug → strong_buy
- FDA rejection → strong_short
- Analyst upgrade alone (no fundamental change) → watch
- No clear catalyst found → catalyst_type: none, trading_signal: skip

Response must be JSON matching the provided schema.
Analysis text: 1-3 sentences max, professional analyst tone, no fluff."""


@dataclass
class AnalysisResult:
    catalyst_type: str
    sentiment: str
    trading_signal: str
    analysis_text: str
    news_title: str | None
    news_url: str | None
    web_search_used: bool
    tokens_input: int
    tokens_output: int


async def analyse_ticker(
    ticker: str,
    company_name: str,
    premarket_change_pct: float,
    news_url: str | None,
) -> AnalysisResult:
    """Main entry point. Returns structured analysis for one ticker."""
    news_content = None
    web_search_used = False

    if news_url:
        news_content = await _fetch_url(news_url)

    if not news_content:
        news_content, web_search_used = await _web_search_fallback(ticker, company_name)

    return await _call_claude(
        ticker=ticker,
        company_name=company_name,
        premarket_change_pct=premarket_change_pct,
        news_url=news_url,
        news_content=news_content,
        web_search_used=web_search_used,
    )


async def _fetch_url(url: str) -> str | None:
    """Fetch news article text from URL."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            resp = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            text = resp.text
            # Strip HTML tags naively — good enough for news articles
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:8000]  # cap context
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


async def _web_search_fallback(ticker: str, company_name: str) -> tuple[str, bool]:
    """Use Claude's web_search tool to find why ticker is gapping."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": (
                    f"Search for why {ticker} ({company_name}) stock is moving significantly "
                    f"in pre-market today. Look for news, earnings, FDA decisions, commodity moves, "
                    f"geopolitical events, or any catalyst. Return the key findings."
                ),
            }],
        )
        result_text = _extract_text(response)
        return result_text, True
    except Exception as exc:
        logger.warning("Web search fallback failed for %s: %s", ticker, exc)
        return f"No news found for {ticker}.", False


async def _call_claude(
    ticker: str,
    company_name: str,
    premarket_change_pct: float,
    news_url: str | None,
    news_content: str | None,
    web_search_used: bool,
) -> AnalysisResult:
    direction = "up" if premarket_change_pct >= 0 else "down"
    prompt = (
        f"Stock: {ticker} ({company_name})\n"
        f"Pre-market move: {premarket_change_pct:+.1f}% ({direction})\n"
        f"News URL: {news_url or 'N/A'}\n\n"
        f"News/Context:\n{news_content or 'No news available.'}\n\n"
        f"Analyse this catalyst and return JSON matching the schema."
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            tools=[{
                "name": "report_analysis",
                "description": "Report the catalyst analysis result",
                "input_schema": ANALYSIS_SCHEMA,
            }],
            tool_choice={"type": "tool", "name": "report_analysis"},
            messages=[{"role": "user", "content": prompt}],
        )

        data = _extract_tool_input(response)
        return AnalysisResult(
            catalyst_type=data.get("catalyst_type", "none"),
            sentiment=data.get("sentiment", "neutral"),
            trading_signal=data.get("trading_signal", "skip"),
            analysis_text=data.get("analysis_text", "Unable to determine catalyst."),
            news_title=data.get("news_title"),
            news_url=news_url,
            web_search_used=web_search_used,
            tokens_input=response.usage.input_tokens,
            tokens_output=response.usage.output_tokens,
        )
    except Exception as exc:
        logger.exception("Claude analysis failed for %s", ticker)
        return AnalysisResult(
            catalyst_type="none",
            sentiment="neutral",
            trading_signal="skip",
            analysis_text=f"Analysis failed: {exc}",
            news_title=None,
            news_url=news_url,
            web_search_used=web_search_used,
            tokens_input=0,
            tokens_output=0,
        )


def _extract_tool_input(response) -> dict:
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    return {}


def _extract_text(response) -> str:
    parts = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
        elif block.type == "tool_result":
            parts.append(str(block.content))
    return " ".join(parts)
