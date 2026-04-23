import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_supabase():
    with patch("app.database.get_supabase") as mock:
        db = MagicMock()
        mock.return_value = db
        yield db


@pytest.fixture
def client(mock_supabase):
    from main import app
    return TestClient(app)
