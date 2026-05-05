"""
News Analyser agent.
Reads a news URL, classifies the catalyst, returns structured result.
Falls back to web search if no news URL is provided.
Logic mirrors catalyst_analyzer.py from episodic-pivots-ai.
"""
from __future__ import annotations
import asyncio
import base64
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import anthropic
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# max_retries=0: we handle retries ourselves with proper backoff
client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=0)

SIGNAL_SCORES = {
    "strong_buy": 1.0, "buy": 0.75, "watch": 0.5,
    "skip": 0.0, "short": 0.25, "strong_short": 0.0,
}

POSITIVE_CATALYSTS = [
    "earnings_beat", "guidance_raise", "contract_win", "new_order", "partnership",
    "analyst_upgrade", "fda_approval", "drug_marketing_tieup",
    "merger_acquisition_target", "buyback", "dividend_initiation", "product_launch",
    "sector_momentum", "regulatory_change", "natural_disaster_beneficiary",
    "commodity_shortage", "commodity_price_move", "rate_increase_beneficiary",
    "mining_exploration", "oil_gas_resource",
]
NEGATIVE_CATALYSTS = [
    "earnings_miss", "guidance_cut", "dilution", "legal_issue",
    "analyst_downgrade", "fda_rejection", "ceo_resignation",
    "accounting_irregularity",
]
NEUTRAL_CATALYSTS = ["media_story"]
ALL_CATALYSTS = POSITIVE_CATALYSTS + NEGATIVE_CATALYSTS + NEUTRAL_CATALYSTS + ["none"]

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

=== GENERAL RULES ===
- Dilution (ATM offering, shelf registration, direct offering) → trading_signal: skip
- Takeover/buyout target → trading_signal: skip (gap already priced in)
- Buyout rumour (unconfirmed) → trading_signal: skip
- Analyst upgrade alone (no fundamental change) → watch
- Media story (Barron's, Cramer, Forbes etc.) → catalyst_type: media_story, trading_signal: watch (low success rate)
- No clear catalyst found → catalyst_type: none, trading_signal: skip

=== PRICE RUN-UP WARNING ===
If the stock has advanced 20%+ over the prior 1–3 months BEFORE the news, treat with caution regardless of how positive the catalyst appears. A large prior run means the news may be an exit liquidity event — insiders who knew about the news in advance could be distributing shares to retail buyers on the positive headline.
Ideal setup: stock has trended DOWN for ~1 month OR been sideways for 3–6 months before the catalyst.
If a 20%+ prior run is indicated: note the caution explicitly in analysis_text and bias signal toward watch rather than buy.

=== EARNINGS BEATS ===
A genuine earnings beat must show BIG growth numbers:
- Require mid/high or triple-digit EPS and revenue growth YoY
- Must show a significant beat to analyst consensus (not just 1–2% beat)
- Raised full-year guidance amplifies the signal → strong_buy
- Revenue miss even if EPS beat → watch or skip
- Modest EPS beat (<10% beat, low single-digit growth) → watch, not strong_buy

=== NON-EARNINGS EPISODE TYPES (EPs) ===
new_order: Common in defense, heavy construction, aeronautics, heavy engineering. Large order or series of orders trigger big moves; current financials do not matter.

sector_momentum: Happens in later stages of a sector-wide bull run when almost all stocks in the sector break out. Very profitable short-term but exit before they crash. Look for top sectors by IBD relative strength or MDT top-11 sectors.

regulatory_change: Government policy change driving EP (e.g. subsidy announcement for a sector). Current earnings/financials do not matter.

fda_approval: Extremely volatile; stocks can double/triple/10x. Developmental stage companies. Require 10x+ average volume surge; first 30 min or pre-market volume should be 4–5x 100-day average → strong_buy but caution on position size.

drug_marketing_tieup: Small developmental company ties up with large pharma for joint marketing/rights deal. Deals with $250M+ upfront payments tend to produce strong EPs. Require 10x+ average volume surge. Upfront payment of ~$10M with large biobucks = weak deal → watch.

natural_disaster_beneficiary: Natural disaster / war / disease creates EP in companies likely to benefit. Often speculative. Require high volume confirmation.

commodity_shortage: Shortage in commodity markets (coal, metals, grains) leads to EPs in related stocks. Can produce very large moves.

commodity_price_move: Sharp move in underlying commodity price drives related equities (e.g. Baltic Dry Index spike → shipping stocks; metal spot price surge → miners).

rate_increase_beneficiary: Sharp rate/price increases in commodity or freight sectors (e.g. shipping rates, energy prices) drive EP in related companies.

media_story: Barron's, Business Week, Forbes, Cramer recommendations → low success rate → trading_signal: watch at best.

=== MINING EXPLORATION RESULTS ===
When news announces drill or exploration results, evaluate grade quality using this reference:

GRADE REFERENCE (pre-processing, in-ground grades):
  Cobalt (Co):               Low <1%        Medium 1–2%          High >2%
  Copper (Cu):               Low <0.5%      Medium 0.5–1.5%      High >1.5%     Bonanza 10%
  Gold (Au):                 Low <1.5 g/t   Medium 1.5–5 g/t     High >5 g/t    Bonanza >30 g/t
  Graphite-Flake (Cg):       Low <8%Cg/<85%C  Medium 8–12%Cg/85–95%C  High >12%Cg/>95%C
  Graphite-Lump/Vein (Cg):   High >90%Cg/>95%C
  Iron Ore (Fe):             Low <55%       Medium 56–62%         High >63%
  Lead (Pb):                 Low <2.5%      Medium 2.5–10%        High >10%
  Lithium-Brine (Li):        Extreme 1700 ppm
  Lithium-Hard Rock (Li):    Low <0.9%      Medium 0.9–1.8%       High >1.8%
  Molybdenum (Mo):           Low <0.15%     Medium 0.15–0.5%      High >0.5%
  Nickel (Ni):               Low <1%        Medium 1–2%           High >2%       Bonanza 12%
  Palladium (Pd):            Low <1.5 g/t   Medium 1.5–5 g/t      High >5 g/t
  Phosphate (PO):            Low 4%         High 40%
  Platinum (Pt):             Low <1 g/t     Medium 1.5–5 g/t      High >5 g/t
  Potash (K2O):              Low <20%       Medium 20–25%         High >25%
  Silver (Ag):               Low <10 g/t    Medium 10–50 g/t      High >50 g/t
  Uranium (U3O8):            Low <0.15%     Medium 0.15–0.8%      High >0.8%     Extreme 17%
  Zinc (Zn):                 Low <2.5%      Medium 2.5–10%        High >10%

UNIT CONVERSIONS:
- MoS2 reported → divide by 1.6681 to get Mo equivalent grade
- Uranium reported in ppm → divide by 10,000 to convert to percentage

DEPTH GUIDANCE:
- Preferred open pit depth: 0–70m (cheapest to develop)
- Max viable open pit: 200–400m (bulk tonnage deposits)
- Below 100–150m is deep and expensive; requires high commodity prices to be financially viable
- Shallow lower grades can be more valuable than deeper higher grades — always factor depth into grade assessment

DEPOSIT VALUE ESTIMATION (rough back-of-envelope):
1. Tonnage = Strike Length (m) × Depth (m) × Width (m) × Specific Gravity
2. Contained metal = Tonnage × Grade
3. Convert: copper → ×2,204.62 to pounds; gold → ÷34.2857 to troy oz
4. Gross metal value = Contained metal × spot commodity price
5. Adjusted deposit value ≈ 5% of gross value (conservative; accounts for overburden, tailings, ore irregularity)
6. Mining companies typically trade at 5–10% of adjusted mineral deposit value at acquisition

=== OIL AND GAS RESOURCE ANNOUNCEMENTS ===
If news announces oil or gas resources after seismic/drilling data:

Formula: RCMHIP = A × NP × P × RF × HS × SF
  A = Area of structure (sq meters)
  NP = Net Pay (meters — average vertical thickness holding hydrocarbons)
  P = Porosity (fraction; typical 15–30%)
  RF = Recovery Factor (fraction; oil 10–40%, gas 50–80%)
  HS = Hydrocarbon Saturation (fraction; typical 50–90%)
  SF = Shrinkage Factor for oil (fraction; typical 0.50–0.95)
  For gas: replace SF with FVF (Formation Volume Factor — inverse of SF; gas expands 50–350× at surface)

Conversions: ROIP (barrels) = RCMHIP × 6.29 | RGIP (cubic feet) = RCMHIP × 35.3
Apply 20% discount to any company-provided estimates for conservatism.
Production quality: Fair onshore 300–1,000 bbl/day, offshore 2,000–5,000 bbl/day; Good onshore 1,000–3,000, offshore 5,000–8,000.
Production decline: 15–20% p.a.; 20–30% of reserves produced in first 12–18 months.

=== BIOTECH CHECKLIST ===
For fda_approval, drug_marketing_tieup, partnership, fda_rejection:

POSITIVE signals:
- Control group in early trials (Phase 1/2) → management confidence
- Primary efficacy p-values << 0.001 (multiple zeros after decimal)
- Large pharma partner willing to fund development
- $150M+ upfront cash plus equity stake → strong confidence signal
- 10x+ average volume on FDA news; 4–5x volume in first 30 min pre-market

NEGATIVE / AVOID signals:
- Clinical-stage with no backup programs (single program risk)
- Big pipeline but no partners → equity dilution ahead
- Modest upfront (~$10M) with large biobucks for a "platform" → weak deal
- Pooled data analyses combining separate trials → usually failure
- CRL (Complete Response Letter) from FDA → usually lethal for drug program
- Biotech ignoring FDA recommendations to save time/money → red flag
- Secondary efficacy p-value of 0.048 → skip
- Long Phase 2 without control group → management lacks confidence in drug

STAGE RISK: Clinical-stage = very risky/volatile (small positions); Commercial-stage = growth stock; FCF > R&D + dividends + buybacks = least risky.

Response must be JSON matching the provided schema.
Analysis text: 2–4 sentences, professional analyst tone. For mining news state the grade classification and depth assessment. For non-earnings EPs state the EP type and volume confirmation. Flag any prior run-up caution explicitly."""


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
    news_title: str | None = None,
    price_trend_1m_pct: float | None = None,
    run_id: str = "",
    user_id: str = "",
) -> AnalysisResult:
    """Main entry point. Returns structured analysis for one ticker.

    price_trend_1m_pct: optional 1-month price change prior to today's news.
    If >=20, a run-up caution warning is injected into the analysis prompt.
    """
    news_content = None
    web_search_used = False

    if news_title:
        # Headline from scraper is reliable even when article body is paywalled/JS-only.
        # Try to fetch full article for more detail; fall back to headline alone.
        news_content = f"News headline: {news_title}"
        if news_url:
            full_text = await _fetch_url(news_url)
            if full_text:
                news_content = full_text
    elif news_url:
        news_content = await _fetch_url(news_url)
        if not news_content:
            news_content = f"Article URL: {news_url}"

    if not news_content:
        news_content, web_search_used = await _web_search_fallback(ticker, company_name)

    result = await _call_claude(
        ticker=ticker,
        company_name=company_name,
        premarket_change_pct=premarket_change_pct,
        news_url=news_url,
        news_title=news_title,
        news_content=news_content,
        web_search_used=web_search_used,
        price_trend_1m_pct=price_trend_1m_pct,
    )
    asyncio.create_task(_langfuse_trace(ticker, premarket_change_pct, result, run_id=run_id, user_id=user_id))
    return result


async def _langfuse_trace(
    ticker: str,
    premarket_change_pct: float,
    result: "AnalysisResult",
    run_id: str = "",
    user_id: str = "",
) -> None:
    """Fire-and-forget: send trace + generation + scores to Langfuse. Never raises."""
    if not settings.langfuse_public_key:
        logger.warning("Langfuse trace skipped: langfuse_public_key not set")
        return
    try:
        credentials = base64.b64encode(
            f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
        ).decode()
        now = datetime.now(timezone.utc).isoformat()
        trace_id = str(uuid.uuid4())
        generation_id = str(uuid.uuid4())

        output = {
            "trading_signal": result.trading_signal,
            "catalyst_type": result.catalyst_type,
            "sentiment": result.sentiment,
            "analysis_text": result.analysis_text,
        }
        batch = [
            {
                "id": str(uuid.uuid4()),
                "type": "trace-create",
                "timestamp": now,
                "body": {
                    "id": trace_id,
                    "name": "analyse_ticker",
                    "timestamp": now,
                    "sessionId": run_id or None,
                    "userId": user_id or None,
                    "input": {"ticker": ticker, "premarket_change_pct": premarket_change_pct},
                    "output": output,
                    "metadata": {"web_search_used": result.web_search_used},
                },
            },
            {
                "id": str(uuid.uuid4()),
                "type": "generation-create",
                "timestamp": now,
                "body": {
                    "id": generation_id,
                    "traceId": trace_id,
                    "name": "claude_analysis",
                    "model": "claude-haiku-4-5-20251001",
                    "modelParameters": {"max_tokens": 512},
                    "input": {
                        "ticker": ticker,
                        "premarket_change_pct": premarket_change_pct,
                        "news_title": result.news_title,
                        "web_search_used": result.web_search_used,
                    },
                    "output": output,
                    "usage": {
                        "input": result.tokens_input,
                        "output": result.tokens_output,
                        "unit": "TOKENS",
                    },
                    "promptName": "news_analyser",
                },
            },
            {
                "id": str(uuid.uuid4()),
                "type": "score-create",
                "timestamp": now,
                "body": {
                    "traceId": trace_id,
                    "observationId": generation_id,
                    "name": "signal_strength",
                    "value": SIGNAL_SCORES.get(result.trading_signal, 0.0),
                    "dataType": "NUMERIC",
                    "comment": result.trading_signal,
                },
            },
            {
                "id": str(uuid.uuid4()),
                "type": "score-create",
                "timestamp": now,
                "body": {
                    "traceId": trace_id,
                    "name": "web_search_fallback",
                    "value": 1.0 if result.web_search_used else 0.0,
                    "dataType": "NUMERIC",
                },
            },
        ]

        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.post(
                f"{settings.langfuse_base_url}/api/public/ingestion",
                json={"batch": batch},
                headers={
                    "Authorization": f"Basic {credentials}",
                    "x-langfuse-ingestion-version": "4",
                },
            )
            if resp.status_code >= 400:
                logger.warning("Langfuse ingestion error %s: %s", resp.status_code, resp.text[:200])
            else:
                logger.info("Langfuse trace sent for %s (status %s)", ticker, resp.status_code)
    except Exception as exc:
        logger.warning("Langfuse trace failed for %s: %s", ticker, exc)


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
            return text[:3000]  # cap context
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


async def _web_search_fallback(ticker: str, company_name: str) -> tuple[str, bool]:
    """Use Claude's web_search tool to find why ticker is gapping."""
    try:
        async with asyncio.timeout(25):
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
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
    news_title: str | None,
    news_content: str | None,
    web_search_used: bool,
    price_trend_1m_pct: float | None = None,
) -> AnalysisResult:
    direction = "up" if premarket_change_pct >= 0 else "down"
    run_up_line = ""
    if price_trend_1m_pct is not None and price_trend_1m_pct >= 20:
        run_up_line = f"Prior 1-month price change: {price_trend_1m_pct:+.1f}% ⚠️ PRIOR RUN-UP WARNING\n"
    prompt = (
        f"Stock: {ticker} ({company_name})\n"
        f"Pre-market move: {premarket_change_pct:+.1f}% ({direction})\n"
        f"{run_up_line}"
        f"News headline: {news_title or 'N/A'}\n"
        f"News URL: {news_url or 'N/A'}\n\n"
        f"News/Context:\n{news_content or 'No news available.'}\n\n"
        f"Analyse this catalyst and return JSON matching the schema."
    )

    for attempt in range(2):
        try:
            async with asyncio.timeout(30):
                response = await client.messages.create(
                    model="claude-haiku-4-5-20251001",
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
        except anthropic.RateLimitError:
            wait = 5 * (2 ** attempt)  # 5s, 10s
            logger.warning("Rate limited on %s, retrying in %ds (attempt %d/2)", ticker, wait, attempt + 1)
            await asyncio.sleep(wait)
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

    return AnalysisResult(
        catalyst_type="none", sentiment="neutral", trading_signal="skip",
        analysis_text="Rate limited. Please retry the scan shortly.",
        news_title=None, news_url=news_url, web_search_used=web_search_used,
        tokens_input=0, tokens_output=0,
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
