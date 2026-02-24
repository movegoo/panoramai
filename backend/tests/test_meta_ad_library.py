"""Tests for Meta Ad Library service."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.meta_ad_library import MetaAdLibraryService


class TestMetaAdLibraryService:
    def setup_method(self):
        self.service = MetaAdLibraryService()

    def test_is_configured_false(self):
        with patch.object(type(self.service), "meta_token", new_callable=lambda: property(lambda self: "")):
            assert self.service.is_configured is False

    def test_is_configured_true(self):
        with patch.object(type(self.service), "meta_token", new_callable=lambda: property(lambda self: "test_token")):
            assert self.service.is_configured is True

    @pytest.mark.asyncio
    async def test_get_active_ads_fallback_to_searchapi(self):
        """When Meta token missing, falls back to SearchAPI."""
        with patch.object(type(self.service), "meta_token", new_callable=lambda: property(lambda self: "")):
            with patch.object(self.service, "_searchapi_ads", new_callable=AsyncMock) as mock:
                mock.return_value = [{"id": "123", "page_name": "Test"}]
                result = await self.service.get_active_ads("123456")
        mock.assert_called_once_with("123456", "FR")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_page_fallback_to_searchapi(self):
        """When Meta token missing, falls back to SearchAPI page search."""
        with patch.object(type(self.service), "meta_token", new_callable=lambda: property(lambda self: "")):
            with patch.object(self.service, "_searchapi_page_search", new_callable=AsyncMock) as mock:
                mock.return_value = [{"page_id": "111", "name": "Test Page"}]
                result = await self.service.search_page("test")
        mock.assert_called_once_with("test")
        assert result[0]["name"] == "Test Page"

    @pytest.mark.asyncio
    async def test_enrich_payers_no_searchapi_key(self):
        """Returns error when SearchAPI key not configured."""
        with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "")):
            result = await self.service.enrich_payers([{"id": "1"}])
        assert "error" in result

    @pytest.mark.asyncio
    async def test_enrich_payers_returns_raw_data(self):
        """Payer data is raw, no extrapolation."""
        ads = [{"id": str(i)} for i in range(10)]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "aaa_info": {
                "eu_total_reach": 1000,
                "payer_beneficiary_data": [{"payer": "Agence X", "beneficiary": "Brand Y"}],
            }
        }

        with patch.object(type(self.service), "searchapi_key", new_callable=lambda: property(lambda self: "test_key")):
            with patch("httpx.AsyncClient.__aenter__", return_value=MagicMock(get=AsyncMock(return_value=mock_response))):
                result = await self.service.enrich_payers(ads, sample_size=3)

        assert "payers" in result
        assert result["total_ads"] == 10
        # No 'estimated_total' key — raw data only
        for p in result["payers"]:
            assert "estimated_total" not in p
            assert "count" in p

    @pytest.mark.asyncio
    async def test_get_page_summary_structure(self):
        """Summary returns expected keys."""
        mock_ads = [
            {
                "page_name": "Test Page",
                "eu_total_reach": 5000,
                "publisher_platforms": ["facebook", "instagram"],
                "target_locations": [{"name": "Paris, France"}],
            },
            {
                "page_name": "Test Page",
                "eu_total_reach": 3000,
                "publisher_platforms": ["facebook"],
                "target_locations": [{"name": "Lyon, France"}],
            },
        ]
        with patch.object(self.service, "get_active_ads", new_callable=AsyncMock, return_value=mock_ads):
            result = await self.service.get_page_summary("123")

        assert result["active_ads"] == 2
        assert result["eu_total_reach"] == 8000
        assert result["platforms"]["facebook"] == 2
        assert result["platforms"]["instagram"] == 1
        assert len(result["top_cities"]) == 2
