from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, field_validator


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

    @field_validator("user_input")
    @classmethod
    def validate_user_input(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("user_input must not be empty")
        if len(v) > 500:
            raise ValueError("user_input must be 500 characters or fewer")
        # Strip control characters (except normal whitespace)
        import re
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        return v


class NLScreenerResponse(BaseModel):
    success: bool
    config: dict | None = None
    missing_criteria: list[str] = []
    message: str
