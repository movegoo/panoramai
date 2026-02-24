"""Tests for GMB (Google My Business) enrichment service."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.gmb_service import GMBService


class TestGMBService:
    def setup_method(self):
        self.service = GMBService()

    # ── Configuration ────────────────────────────────────────────

    def test_is_configured_false(self):
        with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "")):
            with patch.object(type(self.service), "google_places_key", new_callable=lambda: property(lambda self: "")):
                assert self.service.is_configured is False

    def test_is_configured_with_searchapi(self):
        with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "test_key")):
            assert self.service.is_configured is True

    def test_is_configured_with_google_places(self):
        with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "")):
            with patch.object(type(self.service), "google_places_key", new_callable=lambda: property(lambda self: "gp_key")):
                assert self.service.is_configured is True

    # ── enrich_store ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_enrich_store_searchapi_success(self):
        """SearchAPI success returns data without calling Google Places."""
        searchapi_result = {
            "success": True,
            "rating": 4.2,
            "reviews_count": 150,
            "place_id": "ChIJ123",
            "source": "searchapi",
        }
        with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "test_key")):
            with patch.object(self.service, "_searchapi_lookup", new_callable=AsyncMock, return_value=searchapi_result):
                with patch.object(self.service, "_google_places_lookup", new_callable=AsyncMock) as gp_mock:
                    result = await self.service.enrich_store("Store", "Brand", "Paris")
        assert result["success"] is True
        assert result["rating"] == 4.2
        gp_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrich_store_fallback_to_google_places(self):
        """When SearchAPI fails, falls back to Google Places."""
        with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "key")):
            with patch.object(self.service, "_searchapi_lookup", new_callable=AsyncMock, return_value={"success": False}):
                with patch.object(type(self.service), "google_places_key", new_callable=lambda: property(lambda self: "gp_key")):
                    gp_result = {"success": True, "rating": 3.8, "reviews_count": 80, "place_id": "ChIJ456", "source": "google_places"}
                    with patch.object(self.service, "_google_places_lookup", new_callable=AsyncMock, return_value=gp_result):
                        result = await self.service.enrich_store("Store", "Brand", "Lyon")
        assert result["success"] is True
        assert result["source"] == "google_places"

    @pytest.mark.asyncio
    async def test_enrich_store_no_api_configured(self):
        """Returns error when no API is configured."""
        with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "")):
            with patch.object(type(self.service), "google_places_key", new_callable=lambda: property(lambda self: "")):
                result = await self.service.enrich_store("Store", "Brand", "Paris")
        assert result["success"] is False
        assert "error" in result

    # ── _searchapi_lookup ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_searchapi_lookup_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "local_results": [
                {
                    "title": "Decathlon Paris",
                    "rating": 4.3,
                    "reviews": 520,
                    "place_id": "ChIJabc",
                    "address": "123 Rue Test",
                    "gps_coordinates": {"latitude": 48.85, "longitude": 2.35},
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.gmb_service.httpx.AsyncClient", return_value=mock_client):
            with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "test_key")):
                result = await self.service._searchapi_lookup("Decathlon", "Decathlon", "Paris", 48.85, 2.35)

        assert result["success"] is True
        assert result["rating"] == 4.3
        assert result["reviews_count"] == 520
        assert result["source"] == "searchapi"

    @pytest.mark.asyncio
    async def test_searchapi_lookup_no_results(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"local_results": []}
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.gmb_service.httpx.AsyncClient", return_value=mock_client):
            with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "test_key")):
                result = await self.service._searchapi_lookup("Unknown Store", "Unknown", "Nowhere")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_searchapi_lookup_http_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.gmb_service.httpx.AsyncClient", return_value=mock_client):
            with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "test_key")):
                result = await self.service._searchapi_lookup("Store", "Brand", "City")

        assert result["success"] is False
        assert "Connection error" in result["error"]

    # ── _google_places_lookup ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_google_places_lookup_success(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "candidates": [
                {
                    "name": "Decathlon Lyon",
                    "rating": 4.1,
                    "user_ratings_total": 310,
                    "place_id": "ChIJxyz",
                    "formatted_address": "45 Rue Lyon",
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.gmb_service.httpx.AsyncClient", return_value=mock_client):
            with patch.object(type(self.service), "google_places_key", new_callable=lambda: property(lambda self: "gp_key")):
                result = await self.service._google_places_lookup("Decathlon", "Decathlon", "Lyon", 45.75, 4.85)

        assert result["success"] is True
        assert result["rating"] == 4.1
        assert result["reviews_count"] == 310
        assert result["source"] == "google_places"

    @pytest.mark.asyncio
    async def test_google_places_lookup_no_candidates(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"candidates": []}
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.gmb_service.httpx.AsyncClient", return_value=mock_client):
            with patch.object(type(self.service), "google_places_key", new_callable=lambda: property(lambda self: "gp_key")):
                result = await self.service._google_places_lookup("Unknown", "Unknown", "Nowhere")

        assert result["success"] is False

    # ── _find_best_match ─────────────────────────────────────────

    def test_find_best_match_brand_name(self):
        results = [
            {"title": "Random Shop", "rating": 4.0},
            {"title": "Decathlon Paris Bercy", "rating": 4.3},
        ]
        best = self.service._find_best_match(results, "Decathlon", "Decathlon Paris")
        assert best is not None
        assert best["title"] == "Decathlon Paris Bercy"

    def test_find_best_match_with_coords(self):
        results = [
            {"title": "Decathlon Marseille", "rating": 4.0, "gps_coordinates": {"latitude": 43.30, "longitude": 5.37}},
            {"title": "Decathlon Lyon", "rating": 4.2, "gps_coordinates": {"latitude": 45.75, "longitude": 4.85}},
        ]
        best = self.service._find_best_match(results, "Decathlon", "", 45.75, 4.85)
        assert best is not None
        assert best["title"] == "Decathlon Lyon"

    def test_find_best_match_no_match(self):
        results = [
            {"title": "Random Shop", "rating": 3.5},
        ]
        best = self.service._find_best_match(results, "Decathlon", "Decathlon")
        assert best is None  # Score < 5

    def test_find_best_match_empty_results(self):
        best = self.service._find_best_match([], "Brand", "Store")
        assert best is None

    # ── enrich_stores_batch ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_batch_skips_recently_enriched(self):
        from datetime import datetime
        stores = [
            {"id": 1, "name": "Store 1", "brand_name": "Brand", "city": "Paris", "rating_fetched_at": datetime.utcnow().isoformat()},
        ]
        result = await self.service.enrich_stores_batch(stores, cache_days=30)
        assert result["skipped"] == 1
        assert result["enriched"] == 0

    @pytest.mark.asyncio
    async def test_batch_respects_max_per_run(self):
        stores = [{"id": i, "name": f"Store {i}", "brand_name": "Brand", "city": "Paris"} for i in range(10)]
        with patch.object(self.service, "enrich_store", new_callable=AsyncMock, return_value={"success": True, "rating": 4.0, "reviews_count": 100, "place_id": "ChIJ"}):
            result = await self.service.enrich_stores_batch(stores, max_per_run=3)
        assert result["enriched"] == 3
