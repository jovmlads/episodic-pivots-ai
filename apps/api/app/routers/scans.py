"""
Scan management routes.
POST /scans/trigger  — run a scan now (SSE stream)
GET  /scans          — list recent scan runs
GET  /scans/{run_id} — get a single run with results
POST /configs        — create screener config
GET  /configs        — list user's configs
PUT  /configs/{id}   — update config
DELETE /configs/{id} — delete config
"""
from __future__ import annotations
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.database import get_supabase
from app.models.scan import ScreenerConfig, ScreenerConfigCreate, FilterRule, TriggerScanRequest
from app.services.scheduler import register_job, remove_job
from app.services.token_tracker import check_budget

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_user(x_user_id: str | None) -> str:
    if not x_user_id:
        raise HTTPException(401, "Missing X-User-Id header")
    return x_user_id


# ── Screener configs ──────────────────────────────────────────────────────────

@router.post("/configs", status_code=201)
async def create_config(
    body: ScreenerConfigCreate,
    x_user_id: str | None = Header(default=None),
):
    user_id = _require_user(x_user_id)
    db = get_supabase()
    row = db.table("screener_configs").insert({
        "user_id": user_id,
        "name": body.name,
        "description": body.description,
        "market": body.market,
        "scan_type": body.scan_type,
        "filters": [f.model_dump() for f in body.filters],
        "columns": body.columns,
        "sort_by": body.sort_by,
        "sort_order": body.sort_order,
        "result_limit": body.result_limit,
        "schedule_cron": body.schedule_cron,
    }).execute()
    config_id = row.data[0]["id"]
    if body.schedule_cron:
        register_job(config_id, user_id, body.schedule_cron)
    return row.data[0]


@router.get("/configs")
async def list_configs(x_user_id: str | None = Header(default=None)):
    user_id = _require_user(x_user_id)
    db = get_supabase()
    rows = (
        db.table("screener_configs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return rows.data or []


@router.put("/configs/{config_id}")
async def update_config(
    config_id: str,
    body: ScreenerConfigCreate,
    x_user_id: str | None = Header(default=None),
):
    user_id = _require_user(x_user_id)
    db = get_supabase()
    update_data = {
        "name": body.name,
        "description": body.description,
        "market": body.market,
        "scan_type": body.scan_type,
        "filters": [f.model_dump() for f in body.filters],
        "columns": body.columns,
        "sort_by": body.sort_by,
        "sort_order": body.sort_order,
        "result_limit": body.result_limit,
        "schedule_cron": body.schedule_cron,
        "updated_at": datetime.now().isoformat(),
    }
    row = (
        db.table("screener_configs")
        .update(update_data)
        .eq("id", config_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "Config not found")
    if body.schedule_cron:
        register_job(config_id, user_id, body.schedule_cron)
    else:
        remove_job(config_id)
    return row.data[0]


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(
    config_id: str,
    x_user_id: str | None = Header(default=None),
):
    user_id = _require_user(x_user_id)
    db = get_supabase()
    db.table("screener_configs").delete().eq("id", config_id).eq("user_id", user_id).execute()
    remove_job(config_id)


# ── Scan execution ────────────────────────────────────────────────────────────

@router.post("/scans/trigger")
async def trigger_scan(
    body: TriggerScanRequest,
    x_user_id: str | None = Header(default=None),
):
    """Trigger a scan and stream SSE results back."""
    user_id = _require_user(x_user_id)

    has_budget, used, budget = check_budget(user_id)
    if not has_budget:
        raise HTTPException(
            429,
            f"Monthly token budget exhausted ({used:,}/{budget:,}). Contact support to increase limit.",
        )

    db = get_supabase()
    row = (
        db.table("screener_configs")
        .select("*")
        .eq("id", body.config_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "Config not found")

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

    from app.agents.news_orchestrator import run_orchestrator

    async def event_stream():
        async for event in run_orchestrator(config, user_id, triggered_by="manual"):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/scans")
async def list_scans(
    limit: int = 20,
    x_user_id: str | None = Header(default=None),
):
    user_id = _require_user(x_user_id)
    db = get_supabase()
    rows = (
        db.table("scan_runs")
        .select("*, screener_configs(name)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return rows.data or []


@router.get("/scans/{run_id}")
async def get_scan(
    run_id: str,
    x_user_id: str | None = Header(default=None),
):
    user_id = _require_user(x_user_id)
    db = get_supabase()
    run = (
        db.table("scan_runs")
        .select("*")
        .eq("id", run_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not run.data:
        raise HTTPException(404, "Scan run not found")
    results = (
        db.table("scan_results")
        .select("*, ai_analyses(*)")
        .eq("run_id", run_id)
        .execute()
    )
    return {"run": run.data, "results": results.data or []}
