from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class FilterRule(BaseModel):
    left: str
    operation: str
    right: Any


class ScreenerConfig(BaseModel):
    id: str | None = None
    user_id: str | None = None
    name: str
    description: str | None = None
    market: str = "america"
    scan_type: str  # premarket_gainers | premarket_losers | gap_up | gap_down
    filters: list[FilterRule] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    sort_by: str = "premarket_change"
    sort_order: str = "desc"
    result_limit: int = Field(default=20, ge=1, le=50)
    is_active: bool = True
    schedule_cron: str | None = None


class ScreenerConfigCreate(BaseModel):
    name: str
    description: str | None = None
    market: str = "america"
    scan_type: str
    filters: list[FilterRule] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    sort_by: str = "premarket_change"
    sort_order: str = "desc"
    result_limit: int = Field(default=20, ge=1, le=50)
    schedule_cron: str | None = None


class ScanResult(BaseModel):
    ticker: str
    company_name: str | None = None
    exchange: str | None = None
    sector: str | None = None
    prev_close: float = 0.0
    premarket_price: float = 0.0
    premarket_change_pct: float = 0.0
    premarket_change_abs: float = 0.0
    premarket_volume: int = 0
    avg_volume: int = 0
    relative_volume: float = 0.0
    float_shares: int | None = None
    market_cap: float | None = None
    raw_data: dict[str, Any] | None = None


class ScanRun(BaseModel):
    id: str
    user_id: str
    config_id: str | None
    status: str
    result_count: int
    tokens_used: int
    triggered_by: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class TriggerScanRequest(BaseModel):
    config_id: str
