"""Tests for the e-reputation router endpoints."""
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

# We need to mock auth before importing the app
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.email = "test@test.com"
    user.is_admin = False
    return user


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_user, mock_db):
    """Create test client with mocked auth and DB."""
    from database import Base, get_db
    from core.auth import get_current_user

    # Lazy import to avoid circular deps
    from main import app

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    yield TestClient(app)

    app.dependency_overrides.clear()


class TestDashboard:
    def test_dashboard_empty(self, client, mock_db):
        """Dashboard with no competitors returns empty."""
        with patch("routers.ereputation.get_user_competitor_ids", return_value=[]):
            resp = client.get("/api/ereputation/dashboard")
            assert resp.status_code == 200
            data = resp.json()
            assert data["competitors"] == []
            assert data["summary"] == {}

    def test_dashboard_with_data(self, client, mock_db):
        """Dashboard with audited competitors returns data."""
        from database import EReputationAudit, EReputationComment, Competitor

        mock_comp = MagicMock(spec=Competitor)
        mock_comp.id = 1
        mock_comp.name = "TestBrand"
        mock_comp.logo_url = "https://example.com/logo.png"

        mock_audit = MagicMock(spec=EReputationAudit)
        mock_audit.id = 1
        mock_audit.competitor_id = 1
        mock_audit.reputation_score = 75.0
        mock_audit.nps = 40.0
        mock_audit.sav_rate = 10.0
        mock_audit.financial_risk_rate = 5.0
        mock_audit.engagement_rate = 15.5
        mock_audit.earned_ratio = 20.0
        mock_audit.sentiment_breakdown = json.dumps({"positive": 30, "negative": 10, "neutral": 10})
        mock_audit.platform_breakdown = json.dumps({"youtube": {"total": 50, "positive": 30, "negative": 10, "neutral": 10}})
        mock_audit.ai_synthesis = json.dumps({"insights": ["test"], "recommendations": ["rec"]})
        mock_audit.total_comments = 50
        mock_audit.created_at = datetime(2026, 1, 1)

        # Mock the query chain
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_order.first.return_value = mock_audit
        mock_filter.order_by.return_value = mock_order
        mock_query.filter.return_value = mock_filter

        mock_comp_query = MagicMock()
        mock_comp_filter = MagicMock()
        mock_comp_filter.first.return_value = mock_comp
        mock_comp_query.filter.return_value = mock_comp_filter

        def mock_db_query(model):
            if model == EReputationAudit:
                return mock_query
            if model == Competitor:
                return mock_comp_query
            if model == EReputationComment:
                count_mock = MagicMock()
                count_mock.filter.return_value = MagicMock(count=MagicMock(return_value=2))
                return count_mock
            return MagicMock()

        mock_db.query = mock_db_query

        with patch("routers.ereputation.get_user_competitor_ids", return_value=[1]):
            resp = client.get("/api/ereputation/dashboard")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["competitors"]) == 1
            assert data["competitors"][0]["competitor_name"] == "TestBrand"
            assert data["competitors"][0]["audit"]["reputation_score"] == 75.0


class TestAlerts:
    def test_alerts_empty(self, client, mock_db):
        """Alerts endpoint with no alerts."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_order.limit.return_value = MagicMock(all=MagicMock(return_value=[]))
        mock_filter.order_by.return_value = mock_order
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with patch("routers.ereputation.get_user_competitor_ids", return_value=[1]):
            resp = client.get("/api/ereputation/alerts")
            assert resp.status_code == 200
            data = resp.json()
            assert data["alerts"] == []
            assert data["total"] == 0


class TestComments:
    def test_comments_endpoint_returns_200(self, client, mock_db):
        """Comments endpoint returns 200 with filters."""
        # Build a deep mock chain that handles all the chained calls
        mock_query = MagicMock()
        # .filter() returns itself for further chaining
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        with patch("routers.ereputation.get_user_competitor_ids", return_value=[1]):
            resp = client.get("/api/ereputation/comments?platform=youtube&sentiment=positive&page=1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
            assert data["page"] == 1


class TestScopingIsolation:
    def test_competitor_not_in_scope(self, client, mock_db):
        """Accessing a competitor not in user's scope returns 404."""
        with patch("routers.ereputation.get_user_competitor_ids", return_value=[1, 2]):
            resp = client.get("/api/ereputation/competitor/999")
            assert resp.status_code == 404
