"""Tests for Snapchat endpoints and discovery."""
from unittest.mock import AsyncMock, patch

from database import Competitor, AdvertiserCompetitor


class TestDiscoverEntity:
    def test_discover_stores_entity_name(self, client, adv_headers, test_competitor):
        """Discover endpoint should auto-store the best entity name."""
        mock_result = {
            "success": True,
            "query": "Carrefour",
            "entities": [
                {"name": "Carrefour France", "ads_count": 15},
                {"name": "Carrefour Bio", "ads_count": 3},
            ],
            "total_ads": 18,
        }
        with patch(
            "routers.snapchat.apify_snapchat.discover_entity_names",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post(
                f"/api/snapchat/discover-entity/{test_competitor.id}",
                headers=adv_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stored"] is True
        assert data["snapchat_entity_name"] == "Carrefour France"
        assert len(data["entities"]) == 2

    def test_discover_skips_if_already_set(self, client, adv_headers, test_competitor, db):
        """Should not overwrite existing snapchat_entity_name."""
        # Pre-set the entity name
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_entity_name = "Already Set"
        db.commit()

        mock_result = {
            "success": True,
            "query": "Carrefour",
            "entities": [{"name": "Carrefour France", "ads_count": 15}],
            "total_ads": 15,
        }
        with patch(
            "routers.snapchat.apify_snapchat.discover_entity_names",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post(
                f"/api/snapchat/discover-entity/{test_competitor.id}",
                headers=adv_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stored"] is False
        assert data["snapchat_entity_name"] == "Already Set"

    def test_discover_unauthenticated(self, client, test_competitor):
        resp = client.post(f"/api/snapchat/discover-entity/{test_competitor.id}")
        assert resp.status_code == 401


class TestDiscoverAllEntities:
    def test_discover_all(self, client, adv_headers, test_competitor):
        mock_result = {
            "success": True,
            "query": "Carrefour",
            "entities": [{"name": "Carrefour France", "ads_count": 10}],
            "total_ads": 10,
        }
        with patch(
            "routers.snapchat.apify_snapchat.discover_entity_names",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post("/api/snapchat/discover-entities", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1
        assert data["results"][0]["status"] == "discovered"

    def test_discover_all_already_set(self, client, adv_headers, test_competitor, db):
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_entity_name = "Pre-Set"
        db.commit()

        resp = client.post("/api/snapchat/discover-entities", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["status"] == "already_set"


class TestFetchSnapchatAds:
    def test_fetch_uses_entity_name(self, client, adv_headers, test_competitor, db):
        """Fetch should use snapchat_entity_name when available."""
        comp = db.query(Competitor).filter(Competitor.id == test_competitor.id).first()
        comp.snapchat_entity_name = "Carrefour France"
        db.commit()

        mock_result = {
            "success": True,
            "ads": [
                {
                    "snap_id": "snap_123",
                    "page_name": "Carrefour France",
                    "ad_text": "Promo test",
                    "title": "Test Ad",
                    "creative_url": "https://example.com/snap.jpg",
                    "display_format": "SNAP",
                    "impressions": 5000,
                    "start_date": None,
                    "is_active": True,
                    "raw": {},
                }
            ],
            "ads_count": 1,
            "total_results": 1,
        }
        with patch(
            "routers.snapchat.apify_snapchat.search_snapchat_ads",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_search:
            resp = client.post(
                f"/api/snapchat/ads/fetch/{test_competitor.id}",
                headers=adv_headers,
            )
            mock_search.assert_called_once_with(query="Carrefour France")

        assert resp.status_code == 200
        data = resp.json()
        assert data["new_stored"] == 1


class TestApifySnapchatService:
    """Unit tests for the ApifySnapchatService."""

    def test_map_ad_extracts_brand_name(self):
        from services.apify_snapchat import ApifySnapchatService

        svc = ApifySnapchatService()
        item = {
            "id": "abc123",
            "brandName": "Test Brand",
            "adName": "Summer Sale",
            "snapMediaType": "VIDEO",
            "totalImpressions": 10000,
            "adStatus": "ACTIVE",
            "startDate": "2026-01-15T00:00:00Z",
        }
        result = svc._map_ad(item)
        assert result is not None
        assert result["page_name"] == "Test Brand"
        assert result["snap_id"] == "snap_abc123"
        assert result["is_active"] is True

    def test_map_ad_fallback_profile_name(self):
        from services.apify_snapchat import ApifySnapchatService

        svc = ApifySnapchatService()
        item = {"id": "xyz", "profileName": "Fallback Name"}
        result = svc._map_ad(item)
        assert result["page_name"] == "Fallback Name"

    def test_map_ad_no_id(self):
        from services.apify_snapchat import ApifySnapchatService

        svc = ApifySnapchatService()
        assert svc._map_ad({}) is None


class TestSectorsSnapchat:
    """Verify sectors.py has snapchat_entity_name for key brands."""

    def test_grande_distribution_has_snapchat(self):
        from core.sectors import SECTORS

        supermarche = SECTORS["supermarche"]["competitors"]
        names_with_snap = [c["name"] for c in supermarche if c.get("snapchat_entity_name")]
        assert "Carrefour" in names_with_snap
        assert "Leclerc" in names_with_snap
        assert "Auchan" in names_with_snap
        assert "Lidl" in names_with_snap
        assert "Intermarché" in names_with_snap

    def test_autopatch_includes_snapchat(self):
        """The auto-patch field list should include snapchat_entity_name."""
        import inspect
        from routers.competitors import list_competitors

        source = inspect.getsource(list_competitors)
        assert "snapchat_entity_name" in source
