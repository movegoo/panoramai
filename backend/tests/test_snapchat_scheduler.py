"""Tests for Snapchat integration in scheduler and watch dashboard."""
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from database import Competitor, Ad, SnapchatData, AdvertiserCompetitor


class TestSchedulerFetchSnapchat:
    """Test _fetch_snapchat is called and stores ads correctly."""

    @pytest.mark.asyncio
    async def test_fetch_snapchat_stores_ads(self, db, test_competitor):
        """_fetch_snapchat should store new Snapchat ads."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_entity_name = "Carrefour France"
        db.commit()

        mock_result = {
            "success": True,
            "ads": [
                {
                    "snap_id": "snap_abc123",
                    "page_name": "Carrefour France",
                    "ad_text": "Promo snap",
                    "title": "Snap Ad",
                    "creative_url": "https://example.com/snap.jpg",
                    "display_format": "SNAP",
                    "impressions": 5000,
                    "start_date": None,
                    "is_active": True,
                },
                {
                    "snap_id": "snap_def456",
                    "page_name": "Carrefour France",
                    "ad_text": "Autre pub",
                    "title": "Snap Ad 2",
                    "creative_url": "https://example.com/snap2.jpg",
                    "display_format": "SNAP",
                    "impressions": 3000,
                    "start_date": None,
                    "is_active": True,
                },
            ],
            "ads_count": 2,
        }

        with patch(
            "services.apify_snapchat.apify_snapchat.search_snapchat_ads",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from services.scheduler import scheduler
            await scheduler._fetch_snapchat(db, comp, comp.name)

        ads = db.query(Ad).filter(Ad.platform == "snapchat", Ad.competitor_id == comp.id).all()
        assert len(ads) == 2
        assert ads[0].ad_id in ("snap_abc123", "snap_def456")
        assert ads[0].platform == "snapchat"
        assert ads[0].impressions_min == 5000 or ads[0].impressions_min == 3000

    @pytest.mark.asyncio
    async def test_fetch_snapchat_skips_duplicates(self, db, test_competitor):
        """_fetch_snapchat should not store duplicate ads."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_entity_name = "Carrefour France"
        db.commit()

        # Pre-insert an ad
        existing = Ad(
            competitor_id=comp.id,
            ad_id="snap_abc123",
            platform="snapchat",
        )
        db.add(existing)
        db.commit()

        mock_result = {
            "success": True,
            "ads": [
                {"snap_id": "snap_abc123", "page_name": "Carrefour France", "ad_text": "Old", "impressions": 5000, "is_active": True},
                {"snap_id": "snap_new999", "page_name": "Carrefour France", "ad_text": "New", "impressions": 1000, "is_active": True},
            ],
            "ads_count": 2,
        }

        with patch(
            "services.apify_snapchat.apify_snapchat.search_snapchat_ads",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from services.scheduler import scheduler
            await scheduler._fetch_snapchat(db, comp, comp.name)

        ads = db.query(Ad).filter(Ad.platform == "snapchat", Ad.competitor_id == comp.id).all()
        assert len(ads) == 2  # existing + 1 new

    @pytest.mark.asyncio
    async def test_fetch_snapchat_handles_failure(self, db, test_competitor):
        """_fetch_snapchat should handle API failures gracefully."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_entity_name = "Carrefour France"
        db.commit()

        mock_result = {"success": False, "error": "API timeout"}

        with patch(
            "services.apify_snapchat.apify_snapchat.search_snapchat_ads",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            from services.scheduler import scheduler
            # Should not raise
            await scheduler._fetch_snapchat(db, comp, comp.name)

        ads = db.query(Ad).filter(Ad.platform == "snapchat", Ad.competitor_id == comp.id).all()
        assert len(ads) == 0

    @pytest.mark.asyncio
    async def test_fetch_competitor_data_calls_snapchat(self, db, test_competitor):
        """_fetch_competitor_data should call _fetch_snapchat when entity_name is set."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_entity_name = "Carrefour France"
        db.commit()

        from services.scheduler import scheduler

        with patch.object(scheduler, "_fetch_ads", new_callable=AsyncMock) as mock_ads, \
             patch.object(scheduler, "_fetch_snapchat", new_callable=AsyncMock) as mock_snap, \
             patch.object(scheduler, "_fetch_google_ads", new_callable=AsyncMock):
            await scheduler._fetch_competitor_data(db, comp)

        mock_snap.assert_called_once_with(db, comp, comp.name)

    @pytest.mark.asyncio
    async def test_fetch_competitor_data_skips_snapchat_without_entity(self, db, test_competitor):
        """_fetch_competitor_data should skip Snapchat when no entity_name."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        assert comp.snapchat_entity_name is None

        from services.scheduler import scheduler

        with patch.object(scheduler, "_fetch_ads", new_callable=AsyncMock), \
             patch.object(scheduler, "_fetch_snapchat", new_callable=AsyncMock) as mock_snap, \
             patch.object(scheduler, "_fetch_google_ads", new_callable=AsyncMock):
            await scheduler._fetch_competitor_data(db, comp)

        mock_snap.assert_not_called()


class TestDashboardSnapchat:
    """Test Snapchat data appears in watch dashboard."""

    def test_dashboard_includes_snapchat_field(self, client, adv_headers, test_competitor, db):
        """Dashboard should include snapchat field for each competitor."""
        resp = client.get("/api/watch/dashboard", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()

        # Brand and competitors should have snapchat key
        if data.get("brand"):
            assert "snapchat" in data["brand"]
        for comp in data["competitors"]:
            assert "snapchat" in comp

    def test_dashboard_snapchat_with_ads(self, client, adv_headers, test_competitor, db):
        """Dashboard should show Snapchat data when ads exist."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_entity_name = "Carrefour France"
        db.commit()

        # Insert some Snapchat ads
        for i in range(3):
            ad = Ad(
                competitor_id=comp.id,
                ad_id=f"snap_test_{i}",
                platform="snapchat",
                impressions_min=1000 * (i + 1),
                is_active=True,
            )
            db.add(ad)
        db.commit()

        resp = client.get("/api/watch/dashboard", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()

        # Find competitor in response
        all_entries = data["competitors"] + ([data["brand"]] if data.get("brand") else [])
        comp_entry = next((c for c in all_entries if c["id"] == comp.id), None)
        assert comp_entry is not None
        assert comp_entry["snapchat"] is not None
        assert comp_entry["snapchat"]["ads_count"] == 3
        assert comp_entry["snapchat"]["total_impressions"] == 6000
        assert comp_entry["snapchat"]["entity_name"] == "Carrefour France"

    def test_platform_leaders_includes_snapchat(self, client, adv_headers, test_competitor, db):
        """Platform leaders should include Snapchat when ads exist."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        db.add(Ad(competitor_id=comp.id, ad_id="snap_leader", platform="snapchat", impressions_min=5000, is_active=True))
        db.commit()

        resp = client.get("/api/watch/dashboard", headers=adv_headers)
        data = resp.json()
        assert "snapchat" in data["platform_leaders"]
        assert data["platform_leaders"]["snapchat"]["leader"] == comp.name

    def test_rankings_includes_snapchat(self, client, adv_headers, test_competitor, db):
        """Rankings should include Snapchat Ads ranking when ads exist."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        db.add(Ad(competitor_id=comp.id, ad_id="snap_rank", platform="snapchat", impressions_min=2000, is_active=True))
        db.commit()

        resp = client.get("/api/watch/dashboard", headers=adv_headers)
        data = resp.json()
        snap_ranking = next((r for r in data["rankings"] if r["id"] == "snapchat"), None)
        assert snap_ranking is not None
        assert snap_ranking["label"] == "Snapchat Ads"
        assert len(snap_ranking["entries"]) == 1
        assert snap_ranking["entries"][0]["value"] == 1


class TestSnapchatComparison:
    """Test /snapchat/comparison endpoint."""

    def test_comparison_empty(self, client, adv_headers, test_competitor, db):
        """Comparison returns empty when no Snapchat data."""
        resp = client.get("/api/snapchat/comparison", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_comparison_with_ads(self, client, adv_headers, test_competitor, db):
        """Comparison returns ads count and impressions."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_entity_name = "Test Entity"
        db.commit()

        for i in range(3):
            db.add(Ad(
                competitor_id=comp.id,
                ad_id=f"snap_comp_{i}",
                platform="snapchat",
                impressions_min=1000 * (i + 1),
                is_active=True,
            ))
        db.commit()

        resp = client.get("/api/snapchat/comparison", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        entry = next(c for c in data if c["competitor_id"] == comp.id)
        assert entry["ads_count"] == 3
        assert entry["impressions_total"] == 6000
        assert entry["entity_name"] == "Test Entity"


class TestTrendsSnapchat:
    """Test Snapchat data in trends API."""

    def test_timeseries_includes_snapchat(self, client, adv_headers, test_competitor, db):
        """Timeseries should include snapchat field for each competitor."""
        resp = client.get("/api/trends/timeseries?date_from=2025-01-01&date_to=2026-12-31", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        for comp_id, comp_data in data["competitors"].items():
            assert "snapchat" in comp_data
            assert "ads_count" in comp_data["snapchat"]
            assert "impressions" in comp_data["snapchat"]

    def test_summary_includes_snap_metrics(self, client, adv_headers, test_competitor, db):
        """Summary should include snap_ads metric when ads exist."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        db.add(Ad(
            competitor_id=comp.id,
            ad_id="snap_trend_1",
            platform="snapchat",
            impressions_min=5000,
            is_active=True,
        ))
        db.commit()

        resp = client.get("/api/trends/summary?date_from=2025-01-01&date_to=2026-12-31", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        comp_entry = next(c for c in data["competitors"] if c["competitor_id"] == comp.id)
        assert "snap_ads" in comp_entry["metrics"]
        assert comp_entry["metrics"]["snap_ads"]["value"] == 1


class TestSchedulerFetchSnapchatProfile:
    """Test _fetch_snapchat_profile stores SnapchatData correctly."""

    MOCK_PROFILE = {
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

    @pytest.mark.asyncio
    async def test_fetch_profile_stores_data(self, db, test_competitor):
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_username = "carrefourfrance"
        db.commit()

        with patch(
            "services.scrapecreators.scrapecreators.fetch_snapchat_profile",
            new_callable=AsyncMock,
            return_value=self.MOCK_PROFILE,
        ):
            from services.scheduler import scheduler
            await scheduler._fetch_snapchat_profile(db, comp, comp.name)

        data = db.query(SnapchatData).filter(SnapchatData.competitor_id == comp.id).first()
        assert data is not None
        assert data.subscribers == 125000
        assert data.spotlight_count == 8
        assert data.engagement_rate == 401.2

    @pytest.mark.asyncio
    async def test_fetch_profile_skips_without_username(self, db, test_competitor):
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        assert comp.snapchat_username is None

        from services.scheduler import scheduler

        with patch.object(scheduler, "_fetch_ads", new_callable=AsyncMock), \
             patch.object(scheduler, "_fetch_snapchat", new_callable=AsyncMock), \
             patch.object(scheduler, "_fetch_snapchat_profile", new_callable=AsyncMock) as mock_prof, \
             patch.object(scheduler, "_fetch_google_ads", new_callable=AsyncMock):
            await scheduler._fetch_competitor_data(db, comp)

        mock_prof.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_profile_rate_limiting(self, db, test_competitor):
        """Should skip fetch if data less than 1 hour old."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_username = "carrefourfrance"
        db.commit()

        # Insert recent data
        db.add(SnapchatData(
            competitor_id=comp.id,
            subscribers=100000,
            recorded_at=datetime.utcnow() - timedelta(minutes=30),
        ))
        db.commit()

        with patch(
            "services.scrapecreators.scrapecreators.fetch_snapchat_profile",
            new_callable=AsyncMock,
        ) as mock_fetch:
            from services.scheduler import scheduler
            await scheduler._fetch_snapchat_profile(db, comp, comp.name)

        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_profile_allows_after_1h(self, db, test_competitor):
        """Should fetch if data is more than 1 hour old."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_username = "carrefourfrance"
        db.commit()

        # Insert old data
        db.add(SnapchatData(
            competitor_id=comp.id,
            subscribers=100000,
            recorded_at=datetime.utcnow() - timedelta(hours=2),
        ))
        db.commit()

        with patch(
            "services.scrapecreators.scrapecreators.fetch_snapchat_profile",
            new_callable=AsyncMock,
            return_value=self.MOCK_PROFILE,
        ):
            from services.scheduler import scheduler
            await scheduler._fetch_snapchat_profile(db, comp, comp.name)

        data = db.query(SnapchatData).filter(SnapchatData.competitor_id == comp.id).order_by(SnapchatData.recorded_at.desc()).first()
        assert data.subscribers == 125000

    @pytest.mark.asyncio
    async def test_fetch_competitor_data_calls_profile(self, db, test_competitor):
        """_fetch_competitor_data should call _fetch_snapchat_profile when username set."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_username = "carrefourfrance"
        db.commit()

        from services.scheduler import scheduler

        with patch.object(scheduler, "_fetch_ads", new_callable=AsyncMock), \
             patch.object(scheduler, "_fetch_snapchat", new_callable=AsyncMock), \
             patch.object(scheduler, "_fetch_snapchat_profile", new_callable=AsyncMock) as mock_prof, \
             patch.object(scheduler, "_fetch_google_ads", new_callable=AsyncMock):
            await scheduler._fetch_competitor_data(db, comp)

        mock_prof.assert_called_once_with(db, comp, comp.name)


class TestDashboardSnapchatProfile:
    """Test Snapchat profile data appears in watch dashboard."""

    def test_dashboard_includes_subscribers(self, client, adv_headers, test_competitor, db):
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_username = "carrefourfrance"
        db.commit()

        db.add(SnapchatData(
            competitor_id=comp.id,
            subscribers=125000,
            engagement_rate=5.2,
            spotlight_count=10,
        ))
        db.commit()

        resp = client.get("/api/watch/dashboard", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()

        all_entries = data["competitors"] + ([data["brand"]] if data.get("brand") else [])
        comp_entry = next((c for c in all_entries if c["id"] == comp.id), None)
        assert comp_entry is not None
        assert comp_entry["snapchat"]["subscribers"] == 125000
        assert comp_entry["snapchat"]["engagement_rate"] == 5.2
        assert comp_entry["snapchat"]["spotlight_count"] == 10
