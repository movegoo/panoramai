"""Tests for Snapchat integration in scheduler and watch dashboard."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from database import Competitor, Ad, AdvertiserCompetitor


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
