from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from app.database import get_supabase

router = APIRouter()


class NotificationSettingsBody(BaseModel):
    email: str
    notify_on_scan_complete: bool = True
    notify_on_budget_warning: bool = True


def _require_user(x_user_id: str | None) -> str:
    if not x_user_id:
        raise HTTPException(401, "Missing X-User-Id header")
    return x_user_id


@router.post("/notification-settings")
async def upsert_notification_settings(
    body: NotificationSettingsBody,
    x_user_id: str | None = Header(default=None),
):
    user_id = _require_user(x_user_id)
    db = get_supabase()
    existing = (
        db.table("notification_settings")
        .select("id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    data = {
        "user_id": user_id,
        "email": body.email,
        "notify_on_scan_complete": body.notify_on_scan_complete,
        "notify_on_budget_warning": body.notify_on_budget_warning,
    }
    if existing.data:
        db.table("notification_settings").update(data).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("notification_settings").insert(data).execute()
    return {"ok": True}


@router.get("/notification-settings")
async def get_notification_settings(x_user_id: str | None = Header(default=None)):
    user_id = _require_user(x_user_id)
    db = get_supabase()
    row = (
        db.table("notification_settings")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return row.data[0] if row.data else {}


@router.get("/token-usage")
async def get_token_usage(x_user_id: str | None = Header(default=None)):
    user_id = _require_user(x_user_id)
    from app.services.token_tracker import get_usage, get_budget, current_month_year
    used = get_usage(user_id).get("tokens_total", 0)
    budget = get_budget(user_id)
    return {
        "tokens_total": used,
        "budget": budget,
        "month_year": current_month_year(),
        "pct_used": round((used / budget) * 100, 1) if budget else 0,
    }
