from __future__ import annotations
import logging
from datetime import datetime

from app.database import get_supabase
from app.config import settings

logger = logging.getLogger(__name__)


def current_month_year() -> str:
    return datetime.now().strftime("%Y-%m")


def get_usage(user_id: str) -> dict:
    """Return token usage for the current month."""
    month = current_month_year()
    db = get_supabase()
    row = (
        db.table("token_usage")
        .select("tokens_total")
        .eq("user_id", user_id)
        .eq("month_year", month)
        .maybe_single()
        .execute()
    )
    return row.data or {"tokens_total": 0}


def get_budget(user_id: str) -> int:
    """Return the user's monthly token budget."""
    db = get_supabase()
    row = (
        db.table("profiles")
        .select("monthly_token_budget")
        .eq("id", user_id)
        .single()
        .execute()
    )
    return row.data.get("monthly_token_budget", settings.default_monthly_token_budget)


def check_budget(user_id: str) -> tuple[bool, int, int]:
    """
    Check if the user has remaining token budget.
    Returns (has_budget, tokens_used, budget).
    """
    used = get_usage(user_id).get("tokens_total", 0)
    budget = get_budget(user_id)
    return used < budget, used, budget


def record_usage(user_id: str, tokens_input: int, tokens_output: int) -> None:
    """Upsert token usage for the current month."""
    month = current_month_year()
    total = tokens_input + tokens_output
    db = get_supabase()
    existing = (
        db.table("token_usage")
        .select("id, tokens_input, tokens_output, tokens_total")
        .eq("user_id", user_id)
        .eq("month_year", month)
        .maybe_single()
        .execute()
    )
    if existing.data:
        db.table("token_usage").update({
            "tokens_input": existing.data["tokens_input"] + tokens_input,
            "tokens_output": existing.data["tokens_output"] + tokens_output,
            "tokens_total": existing.data["tokens_total"] + total,
            "updated_at": datetime.now().isoformat(),
        }).eq("id", existing.data["id"]).execute()
    else:
        db.table("token_usage").insert({
            "user_id": user_id,
            "month_year": month,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tokens_total": total,
        }).execute()
    logger.debug("Recorded %d tokens for user %s", total, user_id)


def budget_warning_threshold(user_id: str) -> bool:
    """Return True if user has used >= 80% of their budget."""
    used = get_usage(user_id).get("tokens_total", 0)
    budget = get_budget(user_id)
    return budget > 0 and (used / budget) >= 0.8
