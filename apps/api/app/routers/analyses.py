"""
AI analysis routes.
GET  /analyses          — list analyses for user
GET  /analyses/similar  — RAG similarity search
POST /analyses/screener-nl — NL screener config producer (SSE stream)
"""
from __future__ import annotations
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.database import get_supabase
from app.models.analysis import NLScreenerRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_user(x_user_id: str | None) -> str:
    if not x_user_id:
        raise HTTPException(401, "Missing X-User-Id header")
    return x_user_id


@router.get("/analyses")
async def list_analyses(
    limit: int = 50,
    offset: int = 0,
    x_user_id: str | None = Header(default=None),
):
    user_id = _require_user(x_user_id)
    db = get_supabase()
    rows = (
        db.table("ai_analyses")
        .select("*, scan_results(ticker, company_name, premarket_change_pct, scanned_at)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return rows.data or []


@router.get("/analyses/similar")
async def similar_analyses(
    result_id: str = Query(...),
    limit: int = Query(default=5, le=20),
    x_user_id: str | None = Header(default=None),
):
    user_id = _require_user(x_user_id)
    from app.agents.rag_similarity import find_similar
    results = await find_similar(result_id, user_id, limit=limit)
    return results


@router.post("/analyses/screener-nl")
async def screener_nl(
    body: NLScreenerRequest,
    x_user_id: str | None = Header(default=None),
):
    """Stream NL → screener config conversion."""
    _require_user(x_user_id)
    from app.agents.screener_config_producer import produce_config_stream

    async def event_stream():
        async for chunk in produce_config_stream(body.user_input):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
