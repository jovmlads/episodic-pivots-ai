"""
Standalone AI agent eval harness.
Run from apps/api/: py -m tests.eval_agents
Measures real latency, token counts, schema compliance, and signal accuracy.
"""
from __future__ import annotations
import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Load .env from api directory
load_dotenv(Path(__file__).parent.parent / ".env")

# Minimal settings shim so app.config resolves without all Railway vars
os.environ.setdefault("SUPABASE_DB_URL", os.environ.get("SUPABASE_DB_URL", "postgresql://placeholder"))
os.environ.setdefault("TRADINGVIEW_COOKIE", "")
os.environ.setdefault("API_SECRET_KEY", "test")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
import openai as _openai

# ─── Fixtures ────────────────────────────────────────────────────────────────

NEWS_FIXTURES = [
    {
        "id": "F01",
        "ticker": "NVDA",
        "company": "NVIDIA Corporation",
        "pct": 9.4,
        "title": "NVIDIA Q3 Revenue $18.1B Beats $17.0B Estimate; Data Center Sales Triple YoY; FY2025 Guidance Raised",
        "text": (
            "NVIDIA Corporation reported third-quarter revenue of $18.12 billion, surpassing analyst "
            "estimates of $17.01 billion by 6.5%. Data center revenue reached $14.51 billion, up 279% "
            "year-over-year. Adjusted EPS of $0.81 beat the consensus of $0.74. Management raised "
            "full-year guidance to $125 billion, above the previous $120 billion street estimate. "
            "CEO Jensen Huang cited accelerating demand for AI infrastructure from hyperscalers."
        ),
        "expected_catalyst": "earnings_beat",
        "expected_signal": "strong_buy",
    },
    {
        "id": "F02",
        "ticker": "SMCI",
        "company": "Super Micro Computer Inc",
        "pct": -5.2,
        "title": "Super Micro Prices $1.5B At-the-Market Offering at $500/share; 3M New Shares to Fund Expansion",
        "text": (
            "Super Micro Computer announced a $1.5 billion at-the-market equity offering, issuing "
            "approximately 3 million new common shares at $500 per share to fund capacity expansion "
            "and working capital needs. The offering represents roughly 5% dilution to existing shareholders. "
            "No changes to revenue guidance were provided alongside the announcement."
        ),
        "expected_catalyst": "dilution",
        "expected_signal": "skip",
    },
    {
        "id": "F03",
        "ticker": "MRNA",
        "company": "Moderna Inc",
        "pct": 14.1,
        "title": "FDA Approves Moderna mRESVIA RSV Vaccine for Adults 60+; Expected $3B Peak Annual Revenue",
        "text": (
            "The U.S. Food and Drug Administration has granted approval to Moderna's mRESVIA, an mRNA-based "
            "respiratory syncytial virus vaccine for adults 60 years and older. This marks the second approved "
            "RSV vaccine in the US market. Analysts project peak annual revenue of $2.8–3.2 billion. "
            "Commercial launch is expected within 60 days. Moderna CEO Stephane Bancel called it "
            "a pivotal validation of the mRNA platform beyond COVID."
        ),
        "expected_catalyst": "fda_approval",
        "expected_signal": "strong_buy",
    },
    {
        "id": "F04",
        "ticker": "COIN",
        "company": "Coinbase Global Inc",
        "pct": -8.3,
        "title": "Coinbase Q3 Miss: Revenue $1.13B vs $1.26B Est; Trading Volume Falls 30% QoQ; Lays Off 20% Staff",
        "text": (
            "Coinbase reported third-quarter revenue of $1.13 billion, missing analyst estimates of $1.26 billion "
            "by 10.3%. Net trading volume fell 30% quarter-over-quarter to $185 billion as crypto market volatility "
            "decreased. The company simultaneously announced a 20% workforce reduction affecting approximately "
            "1,000 employees. Adjusted EBITDA swung to a loss of $124 million. Management cited a challenging "
            "macro environment and declining retail trading activity."
        ),
        "expected_catalyst": "earnings_miss",
        "expected_signal": "skip",
    },
    {
        "id": "F05",
        "ticker": "GOOG",
        "company": "Alphabet Inc",
        "pct": 3.8,
        "title": "Alphabet Announces $70B Stock Buyback Program, First-Ever Quarterly Dividend of $0.20/share",
        "text": (
            "Alphabet announced a $70 billion stock repurchase program and its first-ever quarterly cash dividend "
            "of $0.20 per share, payable June 17 to holders of record June 10. The buyback is in addition to the "
            "$61 billion already deployed under the prior authorization. CFO Ruth Porat said the capital returns "
            "reflect confidence in long-term cash generation. Q1 revenue of $80.5 billion beat estimates of $79.0 billion."
        ),
        "expected_catalyst": "buyback",
        "expected_signal": "buy",
    },
    {
        "id": "F06",
        "ticker": "PLTR",
        "company": "Palantir Technologies Inc",
        "pct": 2.1,
        "title": "JPMorgan Upgrades Palantir to Overweight, Raises Price Target from $22 to $28",
        "text": (
            "JPMorgan analyst Joe Gallo upgraded Palantir Technologies from Neutral to Overweight "
            "and raised the 12-month price target from $22 to $28. The analyst cited improved government "
            "contract pipeline and accelerating commercial AI adoption. No changes to consensus revenue estimates "
            "or company guidance accompanied the upgrade."
        ),
        "expected_catalyst": "analyst_upgrade",
        "expected_signal": "watch",
    },
    {
        "id": "F07",
        "ticker": "SAVA",
        "company": "Cassava Sciences Inc",
        "pct": -31.0,
        "title": "FDA Issues Complete Response Letter for Simufilam Alzheimer's Drug; Phase 3 Trial Fails Primary Endpoint",
        "text": (
            "Cassava Sciences received a Complete Response Letter from the FDA regarding its BLA submission "
            "for simufilam for Alzheimer's disease. The Phase 3 RETHINK-ALZ trial failed its primary endpoint "
            "of cognitive improvement at 52 weeks versus placebo. The FDA cited insufficient evidence of "
            "clinical benefit and requested an additional Phase 3 trial before approval could be considered. "
            "This represents Cassava's primary pipeline asset."
        ),
        "expected_catalyst": "fda_rejection",
        "expected_signal": "strong_short",
    },
    {
        "id": "F08",
        "ticker": "TSLA",
        "company": "Tesla Inc",
        "pct": -2.4,
        "title": "Tesla Q3 EPS $0.72 Misses $0.73 Estimate by $0.01; Deliveries 462K Above 460K Forecast",
        "text": (
            "Tesla reported third-quarter earnings per share of $0.72, marginally below the analyst consensus "
            "of $0.73. Total vehicle deliveries of 462,890 units edged above the 460,000 estimate. "
            "Automotive gross margin excluding credits was 17.1%, below the 17.6% estimate. "
            "Energy storage deployments hit a record 6.9 GWh. Management maintained its 2024 delivery growth "
            "guidance of 'slight' growth over 2023."
        ),
        "expected_catalyst": "earnings_miss",
        "expected_signal": "watch",
    },
    {
        "id": "F09",
        "ticker": "PTON",
        "company": "Peloton Interactive Inc",
        "pct": 0.8,
        "title": "Peloton Q2 Revenue $744M In Line; Subscriber Count Flat; No New Product Announcements",
        "text": (
            "Peloton reported second-quarter revenue of $744 million, in line with the $742 million consensus. "
            "Connected fitness subscribers held flat at 3.06 million versus the prior quarter. "
            "Average net monthly churn improved slightly to 1.4%. No new product launches or strategic updates "
            "were provided. The company reiterated existing fiscal year guidance."
        ),
        "expected_catalyst": "none",
        "expected_signal": "skip",
    },
    {
        "id": "F10",
        "ticker": "AMGN",
        "company": "Amgen Inc",
        "pct": 5.2,
        "title": "Amgen Wins $4.2B Pentagon Contract for Biologic Manufacturing Facility",
        "text": (
            "Amgen announced a $4.2 billion contract with the U.S. Department of Defense to build and operate "
            "a domestic biologic drug manufacturing facility under the BARDA strategic partnership program. "
            "The 15-year contract includes milestone-based payments tied to production capacity benchmarks. "
            "Management said the contract has no impact on existing commercial product guidance."
        ),
        "expected_catalyst": "contract_win",
        "expected_signal": "buy",
    },
]

SCREENER_FIXTURES = [
    {
        "id": "S01",
        "prompt": "NASDAQ small caps under $300M market cap with pre-market gain over 5% and volume above 500K shares",
        "expect_success": True,
        "expect_fields": ["premarket_change", "market_cap_basic", "premarket_volume", "exchange"],
    },
    {
        "id": "S02",
        "prompt": "Biotech stocks gapping up more than 10% pre-market with float under 20 million shares",
        "expect_success": True,
        "expect_fields": ["premarket_change", "float_shares_outstanding"],
    },
    {
        "id": "S03",
        "prompt": "Stocks with relative volume over 5x previous average, pre-market change between 3% and 15%",
        "expect_success": True,
        "expect_fields": ["relative_volume", "premarket_change"],
    },
    {
        "id": "S04",
        "prompt": "NYSE and NASDAQ stocks priced between $2 and $20, pre-market up more than 8%, type stock only",
        "expect_success": True,
        "expect_fields": ["close", "premarket_change", "exchange", "type"],
    },
    {
        "id": "S05",
        "prompt": "Momentum plays with RSI under 30 and pre-market volume over 1 million",
        "expect_success": True,
        "expect_fields": ["RSI", "premarket_volume"],
    },
    {
        "id": "S06",
        "prompt": "Tech sector stocks on NASDAQ with earnings beat yesterday and price over $50",
        "expect_success": False,  # earnings_beat is not a screener field
        "expect_fields": [],
    },
]

# ─── Results container ────────────────────────────────────────────────────────

@dataclass
class AnalyserResult:
    fixture_id: str
    ticker: str
    expected_catalyst: str
    expected_signal: str
    got_catalyst: str
    got_signal: str
    catalyst_correct: bool
    signal_correct: bool
    schema_valid: bool
    latency_ms: float
    tokens_in: int
    tokens_out: int
    error: str | None = None

@dataclass
class ProducerResult:
    fixture_id: str
    prompt: str
    expect_success: bool
    got_success: bool
    json_valid: bool
    fields_present: list[str]
    missing_expected: list[str]
    latency_ms: float
    error: str | None = None

@dataclass
class EmbedResult:
    latency_ms: float
    dims: int
    correct_dims: bool

# ─── news_analyser eval ───────────────────────────────────────────────────────

async def run_analyser_eval() -> list[AnalyserResult]:
    from app.agents.news_analyser import _call_claude, ALL_CATALYSTS

    results = []
    for fx in NEWS_FIXTURES:
        t0 = time.perf_counter()
        try:
            res = await _call_claude(
                ticker=fx["ticker"],
                company_name=fx["company"],
                premarket_change_pct=fx["pct"],
                news_url=None,
                news_title=fx["title"],
                news_content=fx["text"],
                web_search_used=False,
            )
            latency = (time.perf_counter() - t0) * 1000
            schema_valid = (
                res.catalyst_type in ALL_CATALYSTS
                and res.trading_signal in ("strong_buy", "buy", "watch", "skip", "short", "strong_short")
                and res.sentiment in ("bullish", "bearish", "neutral")
            )
            results.append(AnalyserResult(
                fixture_id=fx["id"],
                ticker=fx["ticker"],
                expected_catalyst=fx["expected_catalyst"],
                expected_signal=fx["expected_signal"],
                got_catalyst=res.catalyst_type,
                got_signal=res.trading_signal,
                catalyst_correct=res.catalyst_type == fx["expected_catalyst"],
                signal_correct=res.trading_signal == fx["expected_signal"],
                schema_valid=schema_valid,
                latency_ms=latency,
                tokens_in=res.tokens_input,
                tokens_out=res.tokens_output,
            ))
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1000
            results.append(AnalyserResult(
                fixture_id=fx["id"],
                ticker=fx["ticker"],
                expected_catalyst=fx["expected_catalyst"],
                expected_signal=fx["expected_signal"],
                got_catalyst="ERROR",
                got_signal="ERROR",
                catalyst_correct=False,
                signal_correct=False,
                schema_valid=False,
                latency_ms=latency,
                tokens_in=0,
                tokens_out=0,
                error=str(exc),
            ))
        print(f"  [{fx['id']}] {fx['ticker']} done ({latency:.0f}ms)")
    return results

# ─── screener_config_producer eval ───────────────────────────────────────────

async def run_producer_eval() -> tuple[list[ProducerResult], float, float]:
    from app.agents.screener_config_producer import produce_config_stream

    results = []
    # Run S01 twice to capture cache hit latency
    cache_miss_ms = None
    cache_hit_ms = None

    for run_idx, fx in enumerate(SCREENER_FIXTURES):
        t0 = time.perf_counter()
        chunks = []
        final = None
        try:
            async with asyncio.timeout(30):
                async for event in produce_config_stream(fx["prompt"]):
                    if event["type"] == "chunk":
                        chunks.append(event.get("text", ""))
                    elif event["type"] == "final":
                        final = event
            latency = (time.perf_counter() - t0) * 1000

            got_success = final.get("success", False) if final else False
            json_valid = final is not None and "success" in final

            # Check expected fields appear in filter left values
            config = final.get("config", {}) if final else {}
            filters = config.get("filters", [])
            filter_lefts = [f.get("left", "") for f in filters]
            fields_present = [f for f in fx["expect_fields"] if f in filter_lefts]
            missing = [f for f in fx["expect_fields"] if f not in filter_lefts]

            results.append(ProducerResult(
                fixture_id=fx["id"],
                prompt=fx["prompt"][:60] + "...",
                expect_success=fx["expect_success"],
                got_success=got_success,
                json_valid=json_valid,
                fields_present=fields_present,
                missing_expected=missing,
                latency_ms=latency,
            ))

            # Track S01 cache miss/hit
            if fx["id"] == "S01" and cache_miss_ms is None:
                cache_miss_ms = latency
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1000
            results.append(ProducerResult(
                fixture_id=fx["id"],
                prompt=fx["prompt"][:60] + "...",
                expect_success=fx["expect_success"],
                got_success=False,
                json_valid=False,
                fields_present=[],
                missing_expected=fx["expect_fields"],
                latency_ms=latency,
                error=str(exc),
            ))
        print(f"  [{fx['id']}] done ({latency:.0f}ms)")

    # Cache hit: re-run S01
    print("  [S01-cache] re-running for cache hit measurement...")
    t0 = time.perf_counter()
    async with asyncio.timeout(30):
        async for event in produce_config_stream(SCREENER_FIXTURES[0]["prompt"]):
            pass
    cache_hit_ms = (time.perf_counter() - t0) * 1000
    print(f"  [S01-cache] done ({cache_hit_ms:.0f}ms)")

    return results, cache_miss_ms, cache_hit_ms

# ─── rag_similarity embed eval ───────────────────────────────────────────────

async def run_embed_eval() -> list[EmbedResult]:
    # Call OpenAI directly — bypasses the supabase import in rag_similarity.py
    from openai import AsyncOpenAI
    oai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def embed_text(text: str) -> list[float]:
        resp = await oai.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000],
            dimensions=1536,
        )
        return resp.data[0].embedding

    sample_texts = [
        "NVIDIA Q3 revenue $18.1B beats $17.0B estimate. Data center sales triple YoY driven by H100 GPU demand from hyperscalers. EPS $0.81 beats $0.74 consensus. FY guidance raised. Strong buy signal — genuine fundamental catalyst with accelerating demand.",
        "FDA approves Moderna mRESVIA RSV vaccine for adults 60+. First mRNA-based RSV approval. Commercial launch in 60 days. Peak revenue $3B annually. Bullish catalyst — expands addressable market and validates platform.",
        "Coinbase Q3 revenue miss: $1.13B vs $1.26B estimate. Trading volume -30% QoQ. 20% workforce reduction. EBITDA loss $124M. Bearish — structural headwind from reduced retail crypto trading activity.",
    ]
    results = []
    for i, text in enumerate(sample_texts):
        t0 = time.perf_counter()
        vector = await embed_text(text)
        latency = (time.perf_counter() - t0) * 1000
        results.append(EmbedResult(
            latency_ms=latency,
            dims=len(vector),
            correct_dims=len(vector) == 1536,
        ))
        print(f"  [E{i+1}] {len(vector)} dims, {latency:.0f}ms")
    return results

# ─── Print helpers ────────────────────────────────────────────────────────────

def print_analyser(results: list[AnalyserResult]):
    print("\n" + "="*90)
    print("NEWS ANALYSER — RESULTS")
    print("="*90)
    hdr = f"{'ID':<4} {'Ticker':<6} {'Catalyst OK':<12} {'Signal OK':<10} {'Schema':<8} {'Lat ms':<8} {'Tok in':<7} {'Tok out':<8} Got catalyst -> signal"
    print(hdr)
    print("-"*90)
    for r in results:
        cat_ok = "OK" if r.catalyst_correct else "FAIL"
        sig_ok = "OK" if r.signal_correct else "FAIL"
        sch_ok = "OK" if r.schema_valid else "FAIL"
        err = f" ERR:{r.error[:40]}" if r.error else f" {r.got_catalyst} -> {r.got_signal}"
        print(f"{r.fixture_id:<4} {r.ticker:<6} {cat_ok:<12} {sig_ok:<10} {sch_ok:<8} {r.latency_ms:<8.0f} {r.tokens_in:<7} {r.tokens_out:<8}{err}")

    cat_acc = sum(r.catalyst_correct for r in results) / len(results) * 100
    sig_acc = sum(r.signal_correct for r in results) / len(results) * 100
    schema_rate = sum(r.schema_valid for r in results) / len(results) * 100
    latencies = [r.latency_ms for r in results if not r.error]
    latencies.sort()
    p50 = latencies[len(latencies)//2]
    p95 = latencies[int(len(latencies)*0.95)] if len(latencies) > 1 else latencies[-1]
    avg_in = sum(r.tokens_in for r in results) / len(results)
    avg_out = sum(r.tokens_out for r in results) / len(results)
    cost_per = (avg_in * 0.00000025) + (avg_out * 0.00000125)

    print("-"*90)
    print(f"Catalyst accuracy : {cat_acc:.0f}%  (target ≥85%)")
    print(f"Signal accuracy   : {sig_acc:.0f}%  (target ≥80%)")
    print(f"Schema compliance : {schema_rate:.0f}%  (target 100%)")
    print(f"Latency p50       : {p50:.0f}ms")
    print(f"Latency p95       : {p95:.0f}ms  (target <12 000ms)")
    print(f"Avg tokens in/out : {avg_in:.0f} / {avg_out:.0f}")
    print(f"Cost per analysis : ${cost_per:.6f}")
    return {
        "cat_acc": cat_acc, "sig_acc": sig_acc, "schema_rate": schema_rate,
        "p50_ms": p50, "p95_ms": p95,
        "avg_tokens_in": avg_in, "avg_tokens_out": avg_out, "cost_per": cost_per,
        "results": results,
    }

def print_producer(results: list[ProducerResult], miss_ms, hit_ms):
    print("\n" + "="*90)
    print("SCREENER CONFIG PRODUCER — RESULTS")
    print("="*90)
    hdr = f"{'ID':<4} {'Expect':<8} {'Got':<6} {'JSON':<6} {'Fields OK':<10} {'Missing':<25} {'Lat ms':<8}"
    print(hdr)
    print("-"*90)
    for r in results:
        exp = "ok" if r.expect_success else "fail"
        got = "ok" if r.got_success else "fail"
        match = "OK" if r.expect_success == r.got_success else "FAIL"
        json_ok = "OK" if r.json_valid else "FAIL"
        fields = f"{len(r.fields_present)}/{len(r.fields_present)+len(r.missing_expected)}"
        missing = ",".join(r.missing_expected) if r.missing_expected else "-"
        print(f"{r.fixture_id:<4} {exp:<8} {match}{got:<5} {json_ok:<6} {fields:<10} {missing:<25} {r.latency_ms:<8.0f}")

    success_acc = sum(r.expect_success == r.got_success for r in results) / len(results) * 100
    json_rate = sum(r.json_valid for r in results) / len(results) * 100
    print("-"*90)
    print(f"Success/fail correct : {success_acc:.0f}%  (target ≥95%)")
    print(f"JSON parse rate      : {json_rate:.0f}%  (target ≥98%)")
    print(f"Cache miss latency   : {miss_ms:.0f}ms")
    print(f"Cache hit latency    : {hit_ms:.0f}ms")
    print(f"Cache speedup        : {miss_ms/hit_ms:.1f}x" if hit_ms else "N/A")
    return {
        "success_acc": success_acc, "json_rate": json_rate,
        "cache_miss_ms": miss_ms, "cache_hit_ms": hit_ms,
        "results": results,
    }

def print_embed(results: list[EmbedResult]):
    print("\n" + "="*90)
    print("RAG SIMILARITY — EMBEDDING RESULTS")
    print("="*90)
    for i, r in enumerate(results):
        dims_ok = "OK" if r.correct_dims else "FAIL"
        print(f"  Sample {i+1}: {r.dims} dims {dims_ok}  {r.latency_ms:.0f}ms")
    latencies = [r.latency_ms for r in results]
    latencies.sort()
    p50 = latencies[len(latencies)//2]
    print(f"\nDimensions correct : {'100' if all(r.correct_dims for r in results) else 'FAIL'}%  (target 100%, expect 1536)")
    print(f"Embed latency p50  : {p50:.0f}ms  (target <200ms)")
    return {"p50_ms": p50, "all_correct_dims": all(r.correct_dims for r in results)}

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("\n" + "="*90)
    print("AI AGENT EVAL HARNESS")
    print("="*90)

    print("\n[1/3] Running news_analyser eval (10 fixtures)...")
    a_results = await run_analyser_eval()
    a_summary = print_analyser(a_results)

    print("\n[2/3] Running screener_config_producer eval (6 fixtures + cache test)...")
    p_results, miss_ms, hit_ms = await run_producer_eval()
    p_summary = print_producer(p_results, miss_ms, hit_ms)

    print("\n[3/3] Running rag_similarity embedding eval (3 samples)...")
    e_results = await run_embed_eval()
    e_summary = print_embed(e_results)

    print("\n" + "="*90)
    print("SUMMARY")
    print("="*90)
    print(f"news_analyser    catalyst acc={a_summary['cat_acc']:.0f}%  signal acc={a_summary['sig_acc']:.0f}%  schema={a_summary['schema_rate']:.0f}%  p50={a_summary['p50_ms']:.0f}ms  p95={a_summary['p95_ms']:.0f}ms  cost/call=${a_summary['cost_per']:.6f}")
    print(f"config_producer  success acc={p_summary['success_acc']:.0f}%  json valid={p_summary['json_rate']:.0f}%  cache miss={p_summary['cache_miss_ms']:.0f}ms  cache hit={p_summary['cache_hit_ms']:.0f}ms")
    print(f"rag_similarity   embed p50={e_summary['p50_ms']:.0f}ms  dims_correct={e_summary['all_correct_dims']}")
    print()

if __name__ == "__main__":
    asyncio.run(main())
