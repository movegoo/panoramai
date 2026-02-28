"""Tests for routers/brand.py — Brand management endpoints."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from database import Advertiser, Competitor, AdvertiserCompetitor, UserAdvertiser
from routers.brand import (
    count_configured_channels,
    _brand_to_dict,
    _is_safe_url,
    _detect_socials_from_website,
    _IG_NON_PROFILES,
)


# ─── count_configured_channels ───────────────────────────────────

class TestCountConfiguredChannels:
    def test_no_channels(self):
        brand = MagicMock()
        brand.playstore_app_id = None
        brand.appstore_app_id = None
        brand.instagram_username = None
        brand.tiktok_username = None
        brand.youtube_channel_id = None
        assert count_configured_channels(brand) == 0

    def test_all_channels(self):
        brand = MagicMock()
        brand.playstore_app_id = "com.test"
        brand.appstore_app_id = "123456"
        brand.instagram_username = "test"
        brand.tiktok_username = "test"
        brand.youtube_channel_id = "UCxxx"
        assert count_configured_channels(brand) == 5

    def test_partial_channels(self):
        brand = MagicMock()
        brand.playstore_app_id = "com.test"
        brand.appstore_app_id = None
        brand.instagram_username = "test"
        brand.tiktok_username = None
        brand.youtube_channel_id = None
        assert count_configured_channels(brand) == 2

    def test_empty_string_not_counted(self):
        brand = MagicMock()
        brand.playstore_app_id = ""
        brand.appstore_app_id = ""
        brand.instagram_username = ""
        brand.tiktok_username = ""
        brand.youtube_channel_id = ""
        assert count_configured_channels(brand) == 0


# ─── _is_safe_url ────────────────────────────────────────────────

class TestIsSafeUrl:
    def test_localhost_blocked(self):
        assert _is_safe_url("http://localhost/secret") is False

    def test_metadata_blocked(self):
        assert _is_safe_url("http://metadata.google.internal/computeMetadata") is False

    def test_169_254_blocked(self):
        assert _is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    def test_internal_suffix_blocked(self):
        assert _is_safe_url("http://my-service.internal/api") is False

    def test_public_url_allowed(self):
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            assert _is_safe_url("https://example.com") is True

    def test_private_ip_blocked(self):
        with patch("socket.gethostbyname", return_value="10.0.0.1"):
            assert _is_safe_url("http://internal-service.example.com") is False

    def test_dns_failure_allowed(self):
        """If DNS fails, allow (the HTTP request will fail anyway)."""
        import socket
        with patch("socket.gethostbyname", side_effect=socket.gaierror):
            assert _is_safe_url("https://nonexistent.example.com") is True


# ─── _detect_socials_from_website ────────────────────────────────

class TestDetectSocials:
    @pytest.mark.asyncio
    async def test_detects_instagram(self):
        html = '<a href="https://www.instagram.com/testbrand/">Follow us</a>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch("routers.brand._is_safe_url", return_value=True):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await _detect_socials_from_website("https://testbrand.com")
        assert result["instagram_username"] == "testbrand"

    @pytest.mark.asyncio
    async def test_detects_tiktok(self):
        html = '<a href="https://www.tiktok.com/@testbrand">TikTok</a>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch("routers.brand._is_safe_url", return_value=True):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await _detect_socials_from_website("https://testbrand.com")
        assert result["tiktok_username"] == "testbrand"

    @pytest.mark.asyncio
    async def test_detects_youtube_channel(self):
        html = '<a href="https://www.youtube.com/channel/UCxyz123">YouTube</a>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch("routers.brand._is_safe_url", return_value=True):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await _detect_socials_from_website("https://testbrand.com")
        assert result["youtube_channel_id"] == "UCxyz123"

    @pytest.mark.asyncio
    async def test_detects_youtube_handle(self):
        html = '<a href="https://www.youtube.com/@testbrand">YouTube</a>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch("routers.brand._is_safe_url", return_value=True):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await _detect_socials_from_website("https://testbrand.com")
        assert result["youtube_channel_id"] == "@testbrand"

    @pytest.mark.asyncio
    async def test_detects_playstore(self):
        html = '<a href="https://play.google.com/store/apps/details?id=com.test.app">Play Store</a>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch("routers.brand._is_safe_url", return_value=True):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await _detect_socials_from_website("https://testbrand.com")
        assert result["playstore_app_id"] == "com.test.app"

    @pytest.mark.asyncio
    async def test_detects_appstore(self):
        html = '<a href="https://apps.apple.com/fr/app/test-app/id123456789">App Store</a>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch("routers.brand._is_safe_url", return_value=True):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await _detect_socials_from_website("https://testbrand.com")
        assert result["appstore_app_id"] == "123456789"

    @pytest.mark.asyncio
    async def test_filters_ig_non_profiles(self):
        html = '<a href="https://www.instagram.com/explore/">Explore</a><a href="https://www.instagram.com/reels/">Reels</a>'
        mock_response = MagicMock()
        mock_response.text = html

        with patch("routers.brand._is_safe_url", return_value=True):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await _detect_socials_from_website("https://testbrand.com")
        assert "instagram_username" not in result

    @pytest.mark.asyncio
    async def test_unsafe_url_returns_empty(self):
        with patch("routers.brand._is_safe_url", return_value=False):
            result = await _detect_socials_from_website("http://localhost")
        assert result == {}

    @pytest.mark.asyncio
    async def test_request_error_returns_empty(self):
        with patch("routers.brand._is_safe_url", return_value=True):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
                mock_cls.return_value = mock_client

                result = await _detect_socials_from_website("https://testbrand.com")
        assert result == {}


# ─── _brand_to_dict ──────────────────────────────────────────────

class TestBrandToDict:
    def test_serialization(self):
        brand = MagicMock()
        brand.id = 1
        brand.company_name = "Test Brand"
        brand.sector = "supermarche"
        brand.website = "https://test.com"
        brand.playstore_app_id = "com.test"
        brand.appstore_app_id = "123"
        brand.instagram_username = "test"
        brand.tiktok_username = "test"
        brand.youtube_channel_id = "UCxxx"
        brand.snapchat_entity_name = None
        brand.created_at = None

        result = _brand_to_dict(brand, competitors_count=5)
        assert result["id"] == 1
        assert result["company_name"] == "Test Brand"
        assert result["competitors_tracked"] == 5
        assert result["channels_configured"] == 5  # snapchat not in count_configured_channels


# ─── IG non-profile paths ───────────────────────────────────────

class TestIGNonProfiles:
    def test_contains_expected(self):
        assert "explore" in _IG_NON_PROFILES
        assert "reel" in _IG_NON_PROFILES
        assert "accounts" in _IG_NON_PROFILES

    def test_does_not_contain_profiles(self):
        assert "testbrand" not in _IG_NON_PROFILES


# ─── Router endpoint tests (integration) ────────────────────────

class TestBrandEndpoints:
    def test_get_sectors(self, client, auth_headers):
        resp = client.get("/api/brand/sectors", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_profile(self, client, db, test_user, test_advertiser, adv_headers):
        resp = client.get("/api/brand/profile", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_name"] == "Test Brand"

    def test_list_brands(self, client, db, test_user, test_advertiser, auth_headers):
        resp = client.get("/api/brand/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["company_name"] == "Test Brand"

    def test_get_suggestions(self, client, db, test_user, test_advertiser, adv_headers):
        resp = client.get("/api/brand/suggestions", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_suggest_socials_sector_fallback(self, client, db, test_user, auth_headers):
        resp = client.post(
            "/api/brand/suggest-socials",
            json={"company_name": "Carrefour", "website": None},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected"] >= 0

    def test_suggest_socials_unknown(self, client, db, test_user, auth_headers):
        resp = client.post(
            "/api/brand/suggest-socials",
            json={"company_name": "UnknownBrand12345"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["detected"] == 0
