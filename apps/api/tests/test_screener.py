"""Tests for screener service."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.screener import run_screener, _parse_rows
from app.models.scan import ScreenerConfig, FilterRule


def make_config(**kwargs):
    defaults = dict(
        name="test",
        scan_type="premarket_gainers",
        market="america",
        filters=[FilterRule(left="premarket_change", operation="greater", right=3)],
        columns=[],
        sort_by="premarket_change",
        sort_order="desc",
        result_limit=10,
    )
    defaults.update(kwargs)
    return ScreenerConfig(**defaults)


def test_parse_rows_basic():
    rows = [{
        "symbol": "NASDAQ:AAPL",
        "name": "AAPL",
        "description": "Apple Inc",
        "close": 150.0,
        "premarket_close": 155.0,
        "premarket_change": 3.33,
        "premarket_change_abs": 5.0,
        "premarket_volume": 500000,
        "volume": 80000000,
        "relative_volume": 2.5,
        "float_shares_outstanding": 15000000000,
        "market_cap_basic": 2400000000000,
        "exchange": "NASDAQ",
        "sector": "Technology",
    }]
    results = _parse_rows(rows)
    assert len(results) == 1
    assert results[0].ticker == "AAPL"
    assert results[0].premarket_change_pct == 3.33
    assert results[0].exchange == "NASDAQ"


def test_parse_rows_empty():
    assert _parse_rows([]) == []


def test_parse_rows_malformed():
    results = _parse_rows(["not a dict", None, 42])
    assert results == []


@patch("app.services.screener.Screener")
def test_run_screener_success(mock_screener_cls):
    mock_screener = MagicMock()
    mock_screener_cls.return_value = mock_screener
    mock_screener.screen.return_value = {
        "status": "success",
        "data": [{
            "symbol": "NASDAQ:TEST",
            "name": "TEST",
            "description": "Test Corp",
            "close": 10.0,
            "premarket_close": 11.0,
            "premarket_change": 10.0,
            "premarket_change_abs": 1.0,
            "premarket_volume": 100000,
            "volume": 500000,
            "relative_volume": 3.0,
            "float_shares_outstanding": 5000000,
            "market_cap_basic": 50000000,
            "exchange": "NASDAQ",
            "sector": "Technology",
        }],
    }
    config = make_config()
    results = run_screener(config)
    assert len(results) == 1
    assert results[0].ticker == "TEST"


@patch("app.services.screener.Screener")
def test_run_screener_failure(mock_screener_cls):
    mock_screener = MagicMock()
    mock_screener_cls.return_value = mock_screener
    mock_screener.screen.return_value = {"status": "error", "error": "rate limited"}
    with pytest.raises(RuntimeError, match="rate limited"):
        run_screener(make_config())
