"""Tests for services/meta_ad_library.py — Meta Ad Library API service."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from services.meta_ad_library import MetaAdLibraryService


# ─── Properties ──────────────────────────────────────────────────

class TestProperties:
    def test_is_configured_true(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "meta_token", property(lambda s: "token")):
            assert svc.is_configured is True

    def test_is_configured_false(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "meta_token", property(lambda s: "")):
            assert svc.is_configured is False


# ─── search_page ─────────────────────────────────────────────────

class TestSearchPage:
    @pytest.mark.asyncio
    async def test_with_meta_token(self):
        svc = MetaAdLibraryService()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"page_id": "123", "page_name": "Test Page"},
                {"page_id": "123", "page_name": "Test Page"},  # duplicate
                {"page_id": "456", "page_name": "Other Page"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(type(svc), "meta_token", property(lambda s: "token")):
            with patch("services.meta_ad_library.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await svc.search_page("Test")
        assert len(result) == 2  # deduplicated
        assert result[0]["page_id"] == "123"

    @pytest.mark.asyncio
    async def test_fallback_to_searchapi(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "meta_token", property(lambda s: "")):
            with patch.object(svc, "_searchapi_page_search", new_callable=AsyncMock, return_value=[{"page_id": "789"}]):
                result = await svc.search_page("Test")
        assert len(result) == 1
        assert result[0]["page_id"] == "789"

    @pytest.mark.asyncio
    async def test_error_falls_back(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "meta_token", property(lambda s: "token")):
            with patch("services.meta_ad_library.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(side_effect=Exception("Network error"))
                mock_cls.return_value = mock_client

                with patch.object(svc, "_searchapi_page_search", new_callable=AsyncMock, return_value=[]):
                    result = await svc.search_page("Test")
        assert result == []


# ─── enrich_ad_details ───────────────────────────────────────────

class TestEnrichAdDetails:
    @pytest.mark.asyncio
    async def test_no_searchapi_key(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "searchapi_key", property(lambda s: "")):
            result = await svc.enrich_ad_details("123")
        assert result is None

    @pytest.mark.asyncio
    async def test_success(self):
        svc = MetaAdLibraryService()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "aaa_info": {
                "payer_beneficiary_data": [
                    {"payer": "Agency X", "beneficiary": "Brand Y"}
                ],
                "eu_total_reach": 50000,
                "age_country_gender_reach_breakdown": [{"age": "25-34"}],
                "location_audience": [{"name": "Paris"}],
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(type(svc), "searchapi_key", property(lambda s: "key")):
            with patch("services.meta_ad_library.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await svc.enrich_ad_details("123")
        assert result is not None
        assert result["payer"] == "Agency X"
        assert result["eu_total_reach"] == 50000

    @pytest.mark.asyncio
    async def test_error_returns_none(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "searchapi_key", property(lambda s: "key")):
            with patch("services.meta_ad_library.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(side_effect=Exception("API error"))
                mock_cls.return_value = mock_client

                result = await svc.enrich_ad_details("123")
        assert result is None


# ─── enrich_payers ───────────────────────────────────────────────

class TestEnrichPayers:
    @pytest.mark.asyncio
    async def test_no_searchapi_key(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "searchapi_key", property(lambda s: "")):
            result = await svc.enrich_payers([{"id": "1"}])
        assert result["payers"] == {}

    @pytest.mark.asyncio
    async def test_success(self):
        svc = MetaAdLibraryService()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "aaa_info": {
                "payer_beneficiary_data": [{"payer": "Agency", "beneficiary": "Brand"}],
                "eu_total_reach": 1000,
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(type(svc), "searchapi_key", property(lambda s: "key")):
            with patch("services.meta_ad_library.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                with patch("services.meta_ad_library.asyncio.sleep", new_callable=AsyncMock):
                    result = await svc.enrich_payers([{"id": "ad1"}], sample_size=1)
        assert result["sampled"] == 1
        assert result["payers"][0]["payer"] == "Agency"


# ─── get_page_summary ───────────────────────────────────────────

class TestGetPageSummary:
    @pytest.mark.asyncio
    async def test_success(self):
        svc = MetaAdLibraryService()
        fake_ads = [
            {
                "page_name": "Test Page",
                "eu_total_reach": 10000,
                "publisher_platforms": ["facebook", "instagram"],
                "target_locations": [{"name": "Paris, France"}],
            },
            {
                "page_name": "Test Page",
                "eu_total_reach": 20000,
                "publisher_platforms": ["facebook"],
                "target_locations": [{"name": "Lyon, France"}],
            },
        ]
        with patch.object(svc, "get_active_ads", new_callable=AsyncMock, return_value=fake_ads):
            result = await svc.get_page_summary("123")
        assert result["active_ads"] == 2
        assert result["eu_total_reach"] == 30000
        assert result["platforms"]["facebook"] == 2
        assert result["platforms"]["instagram"] == 1

    @pytest.mark.asyncio
    async def test_empty_ads(self):
        svc = MetaAdLibraryService()
        with patch.object(svc, "get_active_ads", new_callable=AsyncMock, return_value=[]):
            result = await svc.get_page_summary("123")
        assert result["active_ads"] == 0
        assert result["eu_total_reach"] == 0
        assert result["page_name"] == ""


# ─── refresh_long_lived_token ────────────────────────────────────

class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_no_token(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "meta_token", property(lambda s: "")):
            result = await svc.refresh_long_lived_token()
        assert result["success"] is False
        assert "No current" in result["error"]

    @pytest.mark.asyncio
    async def test_no_app_credentials(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "meta_token", property(lambda s: "token")):
            with patch("services.meta_ad_library.settings") as mock_s:
                mock_s.META_APP_ID = ""
                mock_s.META_APP_SECRET = ""
                result = await svc.refresh_long_lived_token()
        assert result["success"] is False
        assert "missing" in result["error"]

    @pytest.mark.asyncio
    async def test_success(self):
        svc = MetaAdLibraryService()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_token_123",
            "expires_in": 5184000,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(type(svc), "meta_token", property(lambda s: "old_token")):
            with patch("services.meta_ad_library.settings") as mock_s:
                mock_s.META_APP_ID = "app_id"
                mock_s.META_APP_SECRET = "app_secret"
                with patch("services.meta_ad_library.httpx.AsyncClient") as mock_cls:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=False)
                    mock_client.get = AsyncMock(return_value=mock_response)
                    mock_cls.return_value = mock_client

                    with patch.object(svc, "_update_ssm_token", new_callable=AsyncMock):
                        result = await svc.refresh_long_lived_token()
        assert result["success"] is True
        assert result["expires_in"] == 5184000
        assert result["expires_days"] == 60


# ─── _searchapi_page_search ─────────────────────────────────────

class TestSearchAPIPageSearch:
    @pytest.mark.asyncio
    async def test_no_key(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "searchapi_key", property(lambda s: "")):
            result = await svc._searchapi_page_search("Test")
        assert result == []

    @pytest.mark.asyncio
    async def test_success(self):
        svc = MetaAdLibraryService()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "page_results": [
                {"page_id": "111", "name": "Page A", "likes": 1000},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(type(svc), "searchapi_key", property(lambda s: "key")):
            with patch("services.meta_ad_library.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await svc._searchapi_page_search("Test")
        assert len(result) == 1
        assert result[0]["page_id"] == "111"


# ─── _searchapi_ads ──────────────────────────────────────────────

class TestSearchAPIAds:
    @pytest.mark.asyncio
    async def test_no_key(self):
        svc = MetaAdLibraryService()
        with patch.object(type(svc), "searchapi_key", property(lambda s: "")):
            result = await svc._searchapi_ads("123")
        assert result == []


# ─── Singleton ───────────────────────────────────────────────────

class TestSingleton:
    def test_singleton_exists(self):
        from services.meta_ad_library import meta_ad_library
        assert meta_ad_library is not None
