"""Tests for Snapchat profile endpoints and ScrapeCreators integration."""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from database import Competitor, SnapchatData, AdvertiserCompetitor


MOCK_PROFILE_RESULT = {
    "success": True,
    "subscribers": 125000,
    "title": "Carrefour France",
    "story_count": 5,
    "spotlight_count": 8,
    "total_views": 500000,
    "total_shares": 1200,
    "total_comments": 300,
    "engagement_rate": 401.2,
    "profile_picture_url": "https://example.com/avatar.jpg",
}


class TestFetchSnapchatProfile:
    """Test POST /snapchat/profile/fetch endpoint."""

    def test_fetch_profile_stores_data(self, client, adv_headers, test_competitor, db):
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_username = "carrefourfrance"
        db.commit()

        with patch(
            "routers.snapchat.scrapecreators.fetch_snapchat_profile",
            new_callable=AsyncMock,
            return_value=MOCK_PROFILE_RESULT,
        ):
            resp = client.post(
                f"/api/snapchat/profile/fetch?competitor_id={test_competitor.id}",
                headers=adv_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subscribers"] == 125000
        assert data["spotlight_count"] == 8

        # Verify stored in DB
        stored = db.query(SnapchatData).filter(SnapchatData.competitor_id == test_competitor.id).first()
        assert stored is not None
        assert stored.subscribers == 125000
        assert stored.engagement_rate == 401.2

    def test_fetch_profile_no_username(self, client, adv_headers, test_competitor, db):
        """Should return 400 when no snapchat_username configured."""
        resp = client.post(
            f"/api/snapchat/profile/fetch?competitor_id={test_competitor.id}",
            headers=adv_headers,
        )
        assert resp.status_code == 400

    def test_fetch_profile_api_failure(self, client, adv_headers, test_competitor, db):
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_username = "carrefourfrance"
        db.commit()

        with patch(
            "routers.snapchat.scrapecreators.fetch_snapchat_profile",
            new_callable=AsyncMock,
            return_value={"success": False, "error": "Not found"},
        ):
            resp = client.post(
                f"/api/snapchat/profile/fetch?competitor_id={test_competitor.id}",
                headers=adv_headers,
            )
        assert resp.status_code == 503

    def test_fetch_profile_unauthenticated(self, client, test_competitor):
        resp = client.post(f"/api/snapchat/profile/fetch?competitor_id={test_competitor.id}")
        assert resp.status_code == 401


class TestProfileComparison:
    """Test GET /snapchat/profile/comparison endpoint."""

    def test_comparison_returns_subscribers(self, client, adv_headers, test_competitor, db):
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_username = "carrefourfrance"
        db.commit()

        db.add(SnapchatData(
            competitor_id=comp.id,
            subscribers=125000,
            title="Carrefour France",
            story_count=5,
            spotlight_count=8,
            total_views=500000,
            total_shares=1200,
            total_comments=300,
            engagement_rate=401.2,
        ))
        db.commit()

        resp = client.get("/api/snapchat/profile/comparison", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        entry = next(c for c in data if c["competitor_id"] == comp.id)
        assert entry["subscribers"] == 125000
        assert entry["engagement_rate"] == 401.2
        assert entry["spotlight_count"] == 8

    def test_comparison_empty_without_data(self, client, adv_headers, test_competitor):
        resp = client.get("/api/snapchat/profile/comparison", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Without any SnapchatData, list should be empty
        assert isinstance(data, list)
        entry = next((c for c in data if c["competitor_id"] == test_competitor.id), None)
        assert entry is None

    def test_comparison_unauthenticated(self, client):
        resp = client.get("/api/snapchat/profile/comparison")
        assert resp.status_code == 401


class TestEnrichedSnapchatComparison:
    """Test that GET /snapchat/comparison includes profile data."""

    def test_comparison_includes_profile_data(self, client, adv_headers, test_competitor, db):
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_entity_name = "Carrefour France"
        comp.snapchat_username = "carrefourfrance"
        db.commit()

        db.add(SnapchatData(
            competitor_id=comp.id,
            subscribers=125000,
            engagement_rate=5.2,
            spotlight_count=10,
            story_count=3,
        ))
        db.commit()

        resp = client.get("/api/snapchat/comparison", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        entry = next(c for c in data if c["competitor_id"] == comp.id)
        assert entry["subscribers"] == 125000
        assert entry["engagement_rate"] == 5.2
        assert entry["spotlight_count"] == 10
        assert entry["story_count"] == 3


class TestScrapeCreatorsSnapchatProfile:
    """Unit tests for ScrapeCreators.fetch_snapchat_profile."""

    @pytest.mark.asyncio
    async def test_parse_profile_data(self):
        from services.scrapecreators import ScrapeCreatorsAPI

        svc = ScrapeCreatorsAPI.__new__(ScrapeCreatorsAPI)
        svc.api_key = "test"
        svc.base_url = "https://api.test.com"

        mock_response = {
            "success": True,
            "subscriberCount": 50000,
            "title": "Test Brand",
            "profilePictureUrl": "https://example.com/pic.jpg",
            "curatedHighlights": [{"id": "1"}, {"id": "2"}],
            "spotlightHighlights": [
                {"viewCount": 10000, "shareCount": 50, "commentCount": 10},
                {"viewCount": 20000, "shareCount": 100, "commentCount": 20},
            ],
        }

        with patch.object(svc, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await svc.fetch_snapchat_profile("testbrand")

        assert result["success"] is True
        assert result["subscribers"] == 50000
        assert result["title"] == "Test Brand"
        assert result["story_count"] == 2
        assert result["spotlight_count"] == 2
        assert result["total_views"] == 30000
        assert result["total_shares"] == 150
        assert result["total_comments"] == 30
        assert result["engagement_rate"] == 60.36  # (30000+150+30)/50000 * 100

    @pytest.mark.asyncio
    async def test_parse_empty_profile(self):
        from services.scrapecreators import ScrapeCreatorsAPI

        svc = ScrapeCreatorsAPI.__new__(ScrapeCreatorsAPI)
        svc.api_key = "test"
        svc.base_url = "https://api.test.com"

        mock_response = {"success": True, "subscriberCount": 0}

        with patch.object(svc, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await svc.fetch_snapchat_profile("unknown")

        assert result["success"] is True
        assert result["subscribers"] == 0
        assert result["story_count"] == 0
        assert result["engagement_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_strips_at_sign(self):
        from services.scrapecreators import ScrapeCreatorsAPI

        svc = ScrapeCreatorsAPI.__new__(ScrapeCreatorsAPI)
        svc.api_key = "test"
        svc.base_url = "https://api.test.com"

        with patch.object(svc, "_get", new_callable=AsyncMock, return_value={"success": True}) as mock_get:
            await svc.fetch_snapchat_profile("@testbrand")

        mock_get.assert_called_once_with("/v1/snapchat/profile", {"handle": "testbrand"})


class TestSectorsSnapchatUsername:
    """Verify sectors.py has snapchat_username for key brands."""

    def test_grande_distribution_has_snapchat_username(self):
        from core.sectors import SECTORS

        supermarche = SECTORS["supermarche"]["competitors"]
        names_with_snap = [c["name"] for c in supermarche if c.get("snapchat_username")]
        assert "Carrefour" in names_with_snap
        assert "Leclerc" in names_with_snap
        assert "Auchan" in names_with_snap
        assert "Lidl" in names_with_snap
        assert "Intermarché" in names_with_snap

    def test_autopatch_includes_snapchat_username(self):
        """The auto-patch field list should include snapchat_username."""
        import inspect
        from routers.competitors import list_competitors

        source = inspect.getsource(list_competitors)
        assert "snapchat_username" in source
