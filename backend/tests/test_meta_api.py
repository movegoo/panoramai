"""Tests for services/meta_api.py — Meta Marketing/Ads Library/Instagram Graph API."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from services.meta_api import MetaAPIService, MetaAdStatus, MetaPlatform


# ─── Enums ────────────────────────────────────────────────────────

class TestEnums:
    def test_ad_status_values(self):
        assert MetaAdStatus.ACTIVE == "ACTIVE"
        assert MetaAdStatus.PAUSED == "PAUSED"
        assert MetaAdStatus.DELETED == "DELETED"
        assert MetaAdStatus.ARCHIVED == "ARCHIVED"

    def test_platform_values(self):
        assert MetaPlatform.FACEBOOK == "facebook"
        assert MetaPlatform.INSTAGRAM == "instagram"


# ─── Configuration ────────────────────────────────────────────────

class TestConfiguration:
    def test_not_configured_without_token(self):
        with patch.dict(os.environ, {"META_ACCESS_TOKEN": ""}, clear=False):
            svc = MetaAPIService()
            svc.access_token = ""
            assert svc.is_configured is False

    def test_configured_with_token(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        assert svc.is_configured is True


# ─── Utility methods ─────────────────────────────────────────────

class TestParseAdSpend:
    def test_normal(self):
        svc = MetaAPIService()
        result = svc.parse_ad_spend({"lower_bound": "100", "upper_bound": "500"})
        assert result == {"min": 100.0, "max": 500.0}

    def test_empty(self):
        svc = MetaAPIService()
        result = svc.parse_ad_spend({})
        assert result == {"min": 0.0, "max": 0.0}

    def test_none(self):
        svc = MetaAPIService()
        result = svc.parse_ad_spend(None)
        assert result == {"min": 0, "max": 0}


class TestParseImpressions:
    def test_normal(self):
        svc = MetaAPIService()
        result = svc.parse_impressions({"lower_bound": "1000", "upper_bound": "5000"})
        assert result == {"min": 1000, "max": 5000}

    def test_none(self):
        svc = MetaAPIService()
        result = svc.parse_impressions(None)
        assert result == {"min": 0, "max": 0}


class TestExtractTargeting:
    def test_full_data(self):
        svc = MetaAPIService()
        ad = {
            "target_ages": "18-35",
            "target_gender": "all",
            "target_locations": [{"name": "France"}],
            "languages": ["fr"],
        }
        result = svc.extract_targeting(ad)
        assert result["ages"] == "18-35"
        assert result["gender"] == "all"
        assert result["locations"] == [{"name": "France"}]
        assert result["languages"] == ["fr"]

    def test_missing_fields(self):
        svc = MetaAPIService()
        result = svc.extract_targeting({})
        assert result["ages"] is None
        assert result["gender"] is None
        assert result["locations"] == []
        assert result["languages"] == []


class TestCalculateEngagementScore:
    def test_normal(self):
        svc = MetaAPIService()
        result = svc.calculate_engagement_score(10000, 500, 100.0)
        assert result["ctr"] == 5.0
        assert result["cpc"] == 0.2
        assert result["cpm"] == 10.0

    def test_zero_impressions(self):
        svc = MetaAPIService()
        result = svc.calculate_engagement_score(0, 0, 0)
        assert result["ctr"] == 0
        assert result["cpc"] == 0
        assert result["cpm"] == 0

    def test_zero_clicks(self):
        svc = MetaAPIService()
        result = svc.calculate_engagement_score(1000, 0, 50.0)
        assert result["ctr"] == 0
        assert result["cpc"] == 0
        assert result["cpm"] == 50.0


# ─── Async API methods ───────────────────────────────────────────

class TestSearchAdsLibrary:
    @pytest.mark.asyncio
    async def test_not_configured_raises(self):
        svc = MetaAPIService()
        svc.access_token = ""
        with pytest.raises(ValueError, match="META_ACCESS_TOKEN"):
            await svc.search_ads_library()

    @pytest.mark.asyncio
    async def test_success(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "1"}]}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.search_ads_library(page_id="123", search_terms="test")
        assert result["data"] == [{"id": "1"}]

    @pytest.mark.asyncio
    async def test_api_error(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {"error": "bad"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.search_ads_library()
        assert result["data"] == []
        assert "error" in result


class TestGetPageAds:
    @pytest.mark.asyncio
    async def test_filters_active_only(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"

        ads = [
            {"id": "1", "ad_delivery_stop_time": None},
            {"id": "2", "ad_delivery_stop_time": "2024-01-01"},
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": ads}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.get_page_ads("123", active_only=True)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_returns_all_when_not_active_only(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"

        ads = [
            {"id": "1", "ad_delivery_stop_time": None},
            {"id": "2", "ad_delivery_stop_time": "2024-01-01"},
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": ads}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.get_page_ads("123", active_only=False)
        assert len(result) == 2


class TestGetMyAdAccounts:
    @pytest.mark.asyncio
    async def test_not_configured(self):
        svc = MetaAPIService()
        svc.access_token = ""
        with pytest.raises(ValueError):
            await svc.get_my_ad_accounts()

    @pytest.mark.asyncio
    async def test_success(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "act_123"}]}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.get_my_ad_accounts()
        assert len(result) == 1
        assert result[0]["id"] == "act_123"


class TestGetAdAccountInsights:
    @pytest.mark.asyncio
    async def test_not_configured(self):
        svc = MetaAPIService()
        svc.access_token = ""
        with pytest.raises(ValueError):
            await svc.get_ad_account_insights("act_123")

    @pytest.mark.asyncio
    async def test_success(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"impressions": "10000"}]}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.get_ad_account_insights("act_123", breakdown="age")
        assert "data" in result


class TestGetCampaigns:
    @pytest.mark.asyncio
    async def test_success(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "camp1"}]}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.get_campaigns("act_123")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_error_returns_empty(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Error"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.get_campaigns("act_123")
        assert result == []


class TestInstagramGraphAPI:
    @pytest.mark.asyncio
    async def test_get_business_account_success(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "instagram_business_account": {"id": "ig_123", "username": "test"}
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.get_instagram_business_account("page_123")
        assert result["id"] == "ig_123"

    @pytest.mark.asyncio
    async def test_get_business_account_not_found(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.get_instagram_business_account("page_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_media_insights_success(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "post_1"}]}
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.get_instagram_media_insights("ig_123")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_media_insights_error(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Error"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.get_instagram_media_insights("ig_123")
        assert result == []

    @pytest.mark.asyncio
    async def test_discover_business(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "business_discovery": {"username": "competitor", "followers_count": 50000}
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.discover_instagram_business("ig_123", "competitor")
        assert result["username"] == "competitor"

    @pytest.mark.asyncio
    async def test_discover_business_error(self):
        svc = MetaAPIService()
        svc.access_token = "test-token"
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc._client = mock_client

        result = await svc.discover_instagram_business("ig_123", "competitor")
        assert result is None


class TestClientLifecycle:
    @pytest.mark.asyncio
    async def test_close(self):
        svc = MetaAPIService()
        mock_client = AsyncMock()
        svc._client = mock_client
        await svc.close()
        mock_client.aclose.assert_called_once()
        assert svc._client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client(self):
        svc = MetaAPIService()
        await svc.close()  # should not raise
