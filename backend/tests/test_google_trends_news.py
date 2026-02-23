"""Tests for Google Trends & News (SearchAPI + endpoints)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from database import GoogleTrendsData, GoogleNewsArticle


# ─── SearchAPI Service Tests ─────────────────────────────────────────


class TestSearchAPIGoogleMethods:
    """Test the 3 new SearchAPI methods."""

    @pytest.mark.asyncio
    async def test_fetch_trends_not_configured(self):
        """Should return error when API key is not set."""
        from services.searchapi import SearchAPIService

        svc = SearchAPIService()
        svc.api_key = ""
        result = await svc.fetch_google_trends(["Carrefour", "Leclerc"])
        assert result["success"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_fetch_news_not_configured(self):
        """Should return error when API key is not set."""
        from services.searchapi import SearchAPIService

        svc = SearchAPIService()
        svc.api_key = ""
        result = await svc.fetch_google_news("Carrefour")
        assert result["success"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_fetch_trends_related_not_configured(self):
        """Should return error when API key is not set."""
        from services.searchapi import SearchAPIService

        svc = SearchAPIService()
        svc.api_key = ""
        result = await svc.fetch_google_trends_related("Carrefour")
        assert result["success"] is False

    @pytest.mark.asyncio
    @patch("services.searchapi.httpx.AsyncClient")
    async def test_fetch_trends_success(self, mock_client_class):
        """Should parse Google Trends TIMESERIES response."""
        from services.searchapi import SearchAPIService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "interest_over_time": {
                "timeline_data": [
                    {
                        "date": "2026-01-01",
                        "values": [
                            {"query": "Carrefour", "extracted_value": 75},
                            {"query": "Leclerc", "extracted_value": 60},
                        ],
                    },
                    {
                        "date": "2026-01-08",
                        "values": [
                            {"query": "Carrefour", "extracted_value": 80},
                            {"query": "Leclerc", "extracted_value": 55},
                        ],
                    },
                ]
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        svc = SearchAPIService()
        svc.api_key = "test-key"
        svc._last_request_at = 0

        result = await svc.fetch_google_trends(["Carrefour", "Leclerc"])
        assert result["success"] is True
        assert len(result["timeline_data"]) == 2
        assert result["timeline_data"][0]["values"]["Carrefour"] == 75

    @pytest.mark.asyncio
    @patch("services.searchapi.httpx.AsyncClient")
    async def test_fetch_news_success(self, mock_client_class):
        """Should parse Google News response."""
        from services.searchapi import SearchAPIService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "news_results": [
                {
                    "title": "Carrefour opens new store",
                    "link": "https://example.com/article1",
                    "source": {"name": "Le Monde"},
                    "date": "2 hours ago",
                    "snippet": "Carrefour has opened...",
                    "thumbnail": "https://example.com/thumb.jpg",
                },
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        svc = SearchAPIService()
        svc.api_key = "test-key"
        svc._last_request_at = 0

        result = await svc.fetch_google_news("Carrefour")
        assert result["success"] is True
        assert len(result["articles"]) == 1
        assert result["articles"][0]["title"] == "Carrefour opens new store"
        assert result["articles"][0]["source"] == "Le Monde"


# ─── Endpoint Tests ──────────────────────────────────────────────────


class TestGoogleTrendsEndpoints:
    """Test /api/google/trends/* endpoints."""

    def test_trends_interest_returns_data(self, client, db, adv_headers, test_competitor):
        """Should return trends data from DB."""
        # Seed some trends data
        for i, date in enumerate(["2026-02-20", "2026-02-21", "2026-02-22"]):
            db.add(GoogleTrendsData(
                competitor_id=test_competitor.id,
                keyword=test_competitor.name,
                date=date,
                value=50 + i * 10,
            ))
        db.commit()

        resp = client.get("/api/google/trends/interest", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "competitors" in data
        comp_data = data["competitors"].get(str(test_competitor.id))
        assert comp_data is not None
        assert len(comp_data["data"]) == 3

    def test_trends_related_invalid_competitor(self, client, adv_headers):
        """Should return 404 for non-existent competitor."""
        resp = client.get("/api/google/trends/related/99999", headers=adv_headers)
        assert resp.status_code == 404


class TestGoogleNewsEndpoints:
    """Test /api/google/news/* endpoints."""

    def test_news_returns_articles(self, client, db, adv_headers, test_competitor):
        """Should return seeded news articles."""
        db.add(GoogleNewsArticle(
            competitor_id=test_competitor.id,
            title="Test Article",
            link="https://example.com/test1",
            source="Test Source",
            date="1 hour ago",
            snippet="Some snippet",
        ))
        db.commit()

        resp = client.get("/api/google/news", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["articles"][0]["title"] == "Test Article"

    def test_news_deduplicates_by_link(self, client, db, adv_headers, test_competitor):
        """Duplicate links should be rejected by unique constraint."""
        db.add(GoogleNewsArticle(
            competitor_id=test_competitor.id,
            title="Article 1",
            link="https://example.com/same-link",
            source="Source",
        ))
        db.commit()

        # Try adding duplicate
        from sqlalchemy.exc import IntegrityError
        db.add(GoogleNewsArticle(
            competitor_id=test_competitor.id,
            title="Article 2",
            link="https://example.com/same-link",
            source="Source 2",
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # Only 1 article should exist
        count = db.query(GoogleNewsArticle).count()
        assert count == 1

    def test_news_latest_limit(self, client, db, adv_headers, test_competitor):
        """Should respect the limit parameter."""
        for i in range(10):
            db.add(GoogleNewsArticle(
                competitor_id=test_competitor.id,
                title=f"Article {i}",
                link=f"https://example.com/article-{i}",
                source="Source",
            ))
        db.commit()

        resp = client.get("/api/google/news/latest?limit=3", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) == 3

    @patch("routers.google_trends_news.searchapi")
    def test_news_refresh(self, mock_searchapi, client, db, adv_headers, test_competitor):
        """Should call searchapi and store articles."""
        mock_searchapi.fetch_google_news = AsyncMock(return_value={
            "success": True,
            "articles": [
                {
                    "title": "Fresh Article",
                    "link": "https://example.com/fresh",
                    "source": "Le Figaro",
                    "date": "1 min ago",
                    "snippet": "Fresh news",
                    "thumbnail": "",
                },
            ],
        })

        resp = client.post("/api/google/news/refresh", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["added"] >= 1
        assert data["competitors"] >= 1
