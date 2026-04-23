"""
APScheduler-based scan scheduler.
Jobs are persisted in memory for now; config is loaded from DB on startup.
For production scale, swap MemoryJobStore for SQLAlchemyJobStore.
"""
from __future__ import annotations
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import get_supabase

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()


def get_scheduler() -> AsyncIOScheduler:
    return _scheduler


def start_scheduler() -> None:
    if not _scheduler.running:
        _scheduler.start()
        logger.info("Scheduler started")
        _load_active_jobs()


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


def _load_active_jobs() -> None:
    """Load all active scheduled configs from DB on startup."""
    try:
        db = get_supabase()
        rows = (
            db.table("screener_configs")
            .select("id, user_id, schedule_cron")
            .eq("is_active", True)
            .not_.is_("schedule_cron", "null")
            .execute()
        )
        for config in rows.data or []:
            register_job(config["id"], config["user_id"], config["schedule_cron"])
    except Exception:
        logger.exception("Failed to load scheduled jobs from DB")


def register_job(config_id: str, user_id: str, cron_expr: str) -> None:
    """Register or replace a scan job for a screener config."""
    job_id = f"scan_{config_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)

    _scheduler.add_job(
        _run_scan_job,
        trigger=CronTrigger.from_crontab(cron_expr),
        id=job_id,
        args=[config_id, user_id],
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("Registered scan job %s cron=%s", job_id, cron_expr)


def remove_job(config_id: str) -> None:
    job_id = f"scan_{config_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
        logger.info("Removed scan job %s", job_id)


async def _run_scan_job(config_id: str, user_id: str) -> None:
    """Triggered by scheduler — runs a full scan + AI analysis pipeline."""
    from app.agents.news_orchestrator import run_orchestrator
    from app.database import get_supabase
    from app.models.scan import ScreenerConfig, FilterRule

    logger.info("Scheduled scan starting | config=%s user=%s", config_id, user_id)
    db = get_supabase()

    row = (
        db.table("screener_configs")
        .select("*")
        .eq("id", config_id)
        .single()
        .execute()
    )
    if not row.data:
        logger.error("Config %s not found", config_id)
        return

    data = row.data
    config = ScreenerConfig(
        id=data["id"],
        user_id=data["user_id"],
        name=data["name"],
        market=data["market"],
        scan_type=data["scan_type"],
        filters=[FilterRule(**f) for f in (data["filters"] or [])],
        columns=data["columns"] or [],
        sort_by=data["sort_by"],
        sort_order=data["sort_order"],
        result_limit=data["result_limit"],
        schedule_cron=data["schedule_cron"],
    )

    # Collect streamed results (scheduler doesn't stream to browser)
    results = []
    async for event in run_orchestrator(config, user_id, triggered_by="scheduled"):
        results.append(event)

    logger.info("Scheduled scan complete | config=%s events=%d", config_id, len(results))
