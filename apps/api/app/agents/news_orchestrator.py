"""
News Orchestrator agent.
Phase 1: stream screener results immediately.
Phase 2: parallel AI analysis, stream updates as they complete.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator

from app.config import settings
from app.database import get_supabase
from app.models.scan import ScreenerConfig, ScanResult
from app.services.screener import run_screener
from app.services.token_tracker import check_budget, record_usage, budget_warning_threshold
from app.services.email import send_scan_report, send_budget_warning

logger = logging.getLogger(__name__)


async def run_orchestrator(
    config: ScreenerConfig,
    user_id: str,
    triggered_by: str = "manual",
) -> AsyncGenerator[dict, None]:
    db = get_supabase()

    run_row = db.table("scan_runs").insert({
        "user_id": user_id,
        "config_id": config.id,
        "status": "running",
        "triggered_by": triggered_by,
        "started_at": datetime.now().isoformat(),
    }).execute()
    run_id = run_row.data[0]["id"]

    try:
        loop = asyncio.get_running_loop()
        candidates: list[ScanResult] = await loop.run_in_executor(
            None, run_screener, config
        )
        candidates = candidates[: settings.max_tickers_per_scan]

        if not candidates:
            yield {"type": "no_results", "message": "No stocks matched the scanning criteria."}
            _update_run(db, run_id, status="completed", result_count=0)
            return

        yield {"type": "start", "total": len(candidates), "run_id": run_id}

        # Phase 1 — stream screener data immediately so UI populates right away
        for c in candidates:
            yield {
                "type": "ticker",
                "ticker": c.ticker,
                "company_name": c.company_name,
                "premarket_change_pct": c.premarket_change_pct,
            }

        # Persist scan results
        result_ids = _insert_scan_results(db, run_id, user_id, candidates)

        # Fetch all news URLs and headlines in parallel (HTTP only, fast)
        news_map = await _fetch_news_urls_parallel(candidates)

        # Phase 2 — parallel AI analysis (Semaphore caps concurrency to avoid rate limits)
        sem = asyncio.Semaphore(5)
        total_input = 0
        total_output = 0
        report_lines = []
        completed = 0

        async def _run_one(idx: int, candidate) -> tuple:
            async with sem:
                nurl, ntitle = news_map.get(candidate.ticker, (None, None))
                return idx, candidate, await _analyse_one(candidate, nurl, ntitle, user_id)

        tasks = [asyncio.create_task(_run_one(i, c)) for i, c in enumerate(candidates)]

        for fut in asyncio.as_completed(tasks):
            idx, candidate, analysis = await fut
            result_id = result_ids[idx]
            completed += 1

            if isinstance(analysis, Exception):
                logger.error("Analysis failed for %s: %s", candidate.ticker, analysis)
                yield {"type": "error", "ticker": candidate.ticker, "message": str(analysis)}
            else:
                total_input += analysis.tokens_input
                total_output += analysis.tokens_output

                analysis_row = _insert_analysis(db, result_id, user_id, candidate, analysis)
                asyncio.create_task(
                    _generate_and_store_embedding(analysis_row["id"], analysis.analysis_text)
                )

                yield {
                    "type": "result",
                    "result_id": result_id,
                    "ticker": candidate.ticker,
                    "company_name": candidate.company_name,
                    "premarket_change_pct": candidate.premarket_change_pct,
                    "news_url": analysis.news_url,
                    "news_title": analysis.news_title,
                    "catalyst_type": analysis.catalyst_type,
                    "sentiment": analysis.sentiment,
                    "trading_signal": analysis.trading_signal,
                    "analysis_text": analysis.analysis_text,
                    "web_search_used": analysis.web_search_used,
                }
                signal_label = analysis.trading_signal.replace("_", " ").title() if analysis.trading_signal else ""
                report_lines.append(
                    f"<tr><td>{candidate.ticker}</td><td>{candidate.company_name}</td>"
                    f"<td>{candidate.premarket_change_pct:+.1f}%</td>"
                    f"<td>{signal_label}</td>"
                    f"<td>{analysis.analysis_text}</td></tr>"
                )

        try:
            if total_input or total_output:
                record_usage(user_id, total_input, total_output)
        except Exception:
            logger.exception("Failed to record token usage for user %s", user_id)
        _update_run(
            db, run_id,
            status="completed",
            result_count=completed,
            tokens_used=total_input + total_output,
        )

        yield {
            "type": "complete",
            "run_id": run_id,
            "total_results": completed,
            "total_tokens": total_input + total_output,
        }

        _post_scan_notifications(user_id, report_lines, run_id, config.name)

    except Exception as exc:
        logger.exception("Orchestrator failed for run %s", run_id)
        _update_run(db, run_id, status="failed", error_message=str(exc))
        yield {"type": "error", "message": f"Scan failed: {exc}"}


async def _analyse_one(candidate: ScanResult, news_url: str | None, news_title: str | None, user_id: str):
    from app.agents.news_analyser import analyse_ticker
    has_budget, _, _ = check_budget(user_id)
    if not has_budget:
        return Exception("Token budget exhausted")
    return await analyse_ticker(
        ticker=candidate.ticker,
        company_name=candidate.company_name or candidate.ticker,
        premarket_change_pct=candidate.premarket_change_pct,
        news_url=news_url,
        news_title=news_title,
    )


async def _fetch_news_urls_parallel(
    candidates: list[ScanResult],
) -> dict[str, tuple[str | None, str | None]]:
    """Fetch news URLs and headlines for all tickers in parallel."""
    from tradingview_scraper.symbols.news import NewsScraper  # type: ignore

    scraper = NewsScraper()
    loop = asyncio.get_running_loop()

    async def fetch_one(candidate: ScanResult) -> tuple[str, tuple[str | None, str | None]]:
        try:
            items = await loop.run_in_executor(
                None,
                lambda t=candidate.ticker, ex=candidate.exchange or "NASDAQ":
                    scraper.scrape_headlines(symbol=t, exchange=ex)
            )
            if items:
                path = items[0].get("storyPath")
                title = items[0].get("title") or items[0].get("headline")
                url = f"https://www.tradingview.com{path}" if path else None
                return candidate.ticker, (url, title)
        except Exception:
            pass
        return candidate.ticker, (None, None)

    results = await asyncio.gather(*[fetch_one(c) for c in candidates])
    return dict(results)


def _insert_scan_results(db, run_id: str, user_id: str, candidates: list[ScanResult]) -> list[str]:
    rows = [
        {
            "run_id": run_id, "user_id": user_id,
            "ticker": c.ticker, "company_name": c.company_name,
            "exchange": c.exchange, "sector": c.sector,
            "prev_close": c.prev_close, "premarket_price": c.premarket_price,
            "premarket_change_pct": c.premarket_change_pct,
            "premarket_change_abs": c.premarket_change_abs,
            "premarket_volume": c.premarket_volume, "avg_volume": c.avg_volume,
            "relative_volume": c.relative_volume, "float_shares": c.float_shares,
            "market_cap": c.market_cap, "raw_data": c.raw_data,
        }
        for c in candidates
    ]
    result = db.table("scan_results").insert(rows).execute()
    return [row["id"] for row in result.data]


def _insert_analysis(db, result_id: str, user_id: str, candidate: ScanResult, analysis) -> dict:
    row = db.table("ai_analyses").insert({
        "result_id": result_id, "user_id": user_id,
        "news_url": analysis.news_url, "news_title": analysis.news_title,
        "catalyst_type": analysis.catalyst_type, "sentiment": analysis.sentiment,
        "trading_signal": analysis.trading_signal, "analysis_text": analysis.analysis_text,
        "web_search_used": analysis.web_search_used,
        "tokens_input": analysis.tokens_input, "tokens_output": analysis.tokens_output,
    }).execute()
    return row.data[0]


async def _generate_and_store_embedding(analysis_id: str, text: str) -> None:
    from app.agents.rag_similarity import embed_text
    try:
        vector = await embed_text(text)
        db = get_supabase()
        db.table("ai_analyses").update({"embedding": vector}).eq("id", analysis_id).execute()
    except Exception:
        logger.exception("Failed to generate embedding for analysis %s", analysis_id)


def _update_run(db, run_id: str, **kwargs) -> None:
    kwargs["completed_at"] = datetime.now().isoformat()
    db.table("scan_runs").update(kwargs).eq("id", run_id).execute()


def _post_scan_notifications(user_id: str, report_lines: list[str], run_id: str, screener_name: str = "") -> None:
    try:
        db = get_supabase()
        notif = (
            db.table("notification_settings")
            .select("email, notify_on_scan_complete, notify_on_budget_warning")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not notif.data:
            return
        s = notif.data[0]
        if s.get("notify_on_scan_complete") and report_lines:
            header = f"<h2 style='font-family:sans-serif'>Screener: {screener_name}</h2>" if screener_name else ""
            table_html = (
                header
                + "<table border='1' cellpadding='6' style='border-collapse:collapse;font-family:sans-serif'>"
                + "<tr><th>Ticker</th><th>Company</th><th>PM Change</th>"
                + "<th>Signal</th><th>Analysis</th></tr>"
                + "".join(report_lines) + "</table>"
            )
            send_scan_report(s["email"], table_html, datetime.now().strftime("%Y-%m-%d"))
        if s.get("notify_on_budget_warning") and budget_warning_threshold(user_id):
            from app.services.token_tracker import get_usage, get_budget
            used = get_usage(user_id).get("tokens_total", 0)
            budget = get_budget(user_id)
            send_budget_warning(s["email"], used, budget)
    except Exception:
        logger.exception("Post-scan notifications failed for user %s", user_id)
