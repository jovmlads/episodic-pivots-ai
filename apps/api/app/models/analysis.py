from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class AIAnalysis(BaseModel):
    id: str | None = None
    result_id: str
    user_id: str
    news_url: str | None = None
    news_title: str | None = None
    catalyst_type: str | None = None
    sentiment: str | None = None          # bullish | bearish | neutral
    trading_signal: str | None = None     # strong_buy | buy | watch | skip | short | strong_short
    analysis_text: str
    web_search_used: bool = False
    tokens_input: int = 0
    tokens_output: int = 0
    created_at: datetime | None = None


class SimilarResult(BaseModel):
    analysis_id: str
    ticker: str
    analysis_text: str
    catalyst_type: str | None
    trading_signal: str | None
    similarity_score: float
    scanned_at: datetime | None


class NLScreenerRequest(BaseModel):
    user_input: str


class NLScreenerResponse(BaseModel):
    success: bool
    config: dict | None = None
    missing_criteria: list[str] = []
    message: str
