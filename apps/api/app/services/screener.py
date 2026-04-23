"""
TradingView screener service.
Wraps tradingview-scraper with user-defined config from DB.
"""
from __future__ import annotations
import logging
from typing import Any

from app.models.scan import ScanResult, ScreenerConfig

logger = logging.getLogger(__name__)

DEFAULT_COLUMNS = [
    "name",
    "description",
    "close",
    "premarket_close",
    "premarket_change",
    "premarket_change_abs",
    "premarket_volume",
    "volume",
    "relative_volume",
    "float_shares_outstanding",
    "market_cap_basic",
    "exchange",
    "sector",
]


def run_screener(config: ScreenerConfig) -> list[ScanResult]:
    """Execute screener and return parsed results."""
    from tradingview_scraper.symbols.screener import Screener

    columns = list(config.columns) if config.columns else DEFAULT_COLUMNS
    filters = [f.model_dump() for f in config.filters]

    logger.info(
        "Running screener | market=%s scan_type=%s filters=%d",
        config.market,
        config.scan_type,
        len(filters),
    )

    screener = Screener()
    result = screener.screen(
        market=config.market,
        filters=filters,
        sort_by=config.sort_by,
        sort_order=config.sort_order,
        columns=columns,
        limit=config.result_limit,
    )

    if result.get("status") != "success":
        raise RuntimeError(f"Screener failed: {result.get('error', 'unknown')}")

    rows: list[dict] = result.get("data", [])
    candidates = _parse_rows(rows)
    logger.info("Screener returned %d result(s)", len(candidates))
    return candidates


def _parse_rows(rows: list[dict]) -> list[ScanResult]:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_symbol = row.get("symbol", "")
        ticker = row.get("name") or (
            raw_symbol.split(":")[-1] if ":" in raw_symbol else raw_symbol
        )
        exchange = row.get("exchange") or (
            raw_symbol.split(":")[0] if ":" in raw_symbol else ""
        )
        float_shares = _safe_int(row.get("float_shares_outstanding"))
        out.append(
            ScanResult(
                ticker=ticker,
                company_name=row.get("description") or ticker,
                exchange=exchange,
                sector=row.get("sector", ""),
                prev_close=_safe_float(row.get("close")),
                premarket_price=_safe_float(row.get("premarket_close")),
                premarket_change_pct=_safe_float(row.get("premarket_change")),
                premarket_change_abs=_safe_float(row.get("premarket_change_abs")),
                premarket_volume=_safe_int(row.get("premarket_volume")),
                avg_volume=_safe_int(row.get("volume")),
                relative_volume=_safe_float(row.get("relative_volume")),
                float_shares=float_shares or None,
                market_cap=_safe_float(row.get("market_cap_basic")) or None,
                raw_data=row,
            )
        )
    return out


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default
