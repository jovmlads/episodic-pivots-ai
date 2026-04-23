"""Tests for token usage tracking."""
import pytest
from unittest.mock import patch, MagicMock
from app.services import token_tracker


@patch("app.services.token_tracker.get_supabase")
def test_check_budget_has_budget(mock_get_db):
    db = MagicMock()
    mock_get_db.return_value = db
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"tokens_total": 100_000}
    db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {"monthly_token_budget": 1_000_000}
    has_budget, used, budget = token_tracker.check_budget("user-1")
    assert has_budget is True
    assert used == 100_000
    assert budget == 1_000_000


@patch("app.services.token_tracker.get_supabase")
def test_check_budget_exhausted(mock_get_db):
    db = MagicMock()
    mock_get_db.return_value = db
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"tokens_total": 1_000_001}
    db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {"monthly_token_budget": 1_000_000}
    has_budget, used, budget = token_tracker.check_budget("user-1")
    assert has_budget is False


@patch("app.services.token_tracker.get_supabase")
def test_budget_warning_threshold(mock_get_db):
    db = MagicMock()
    mock_get_db.return_value = db
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"tokens_total": 850_000}
    db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {"monthly_token_budget": 1_000_000}
    assert token_tracker.budget_warning_threshold("user-1") is True
