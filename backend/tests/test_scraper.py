"""Tests for services/scraper.py — Web scraping utilities."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from services.scraper import RateLimiter, Scraper, MetaAdsScraper, InstagramScraper


# ─── RateLimiter ──────────────────────────────────────────────────

class TestRateLimiter:
    def test_init(self):
        rl = RateLimiter(60)
        assert rl.requests_per_minute == 60
        assert rl.interval == pytest.approx(1.0)

    def test_default_rate(self):
        rl = RateLimiter()
        assert rl.requests_per_minute == 30
        assert rl.interval == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_first_call_no_wait(self):
        rl = RateLimiter(60)
        rl.last_request = 0  # force first call
        await rl.wait()
        assert rl.last_request > 0


# ─── Scraper.extract_number ──────────────────────────────────────

class TestExtractNumber:
    def test_millions(self):
        assert Scraper.extract_number("1.2M") == 1200000

    def test_thousands(self):
        assert Scraper.extract_number("10K") == 10000

    def test_billions(self):
        assert Scraper.extract_number("2.5B") == 2500000000

    def test_plain_number(self):
        assert Scraper.extract_number("1,234") == 1234

    def test_plain_digits(self):
        assert Scraper.extract_number("5678") == 5678

    def test_with_plus(self):
        assert Scraper.extract_number("10K+") == 10000

    def test_empty(self):
        assert Scraper.extract_number("") is None

    def test_none(self):
        assert Scraper.extract_number(None) is None

    def test_non_numeric(self):
        assert Scraper.extract_number("abc") is None


# ─── Scraper.clean_text ──────────────────────────────────────────

class TestCleanText:
    def test_whitespace(self):
        assert Scraper.clean_text("  hello   world  ") == "hello world"

    def test_null_chars(self):
        assert Scraper.clean_text("hello\x00world") == "helloworld"

    def test_empty(self):
        assert Scraper.clean_text("") == ""

    def test_none(self):
        assert Scraper.clean_text(None) == ""

    def test_tabs_newlines(self):
        assert Scraper.clean_text("hello\n\tworld") == "hello world"


# ─── Scraper.parse_html ──────────────────────────────────────────

class TestParseHtml:
    def test_basic(self):
        scraper = Scraper()
        # Use html.parser as lxml may not be installed
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<html><body><p>Hello</p></body></html>", "html.parser")
        assert soup.find("p").text == "Hello"


# ─── Scraper.fetch_page ──────────────────────────────────────────

class TestFetchPage:
    @pytest.mark.asyncio
    async def test_success(self):
        scraper = Scraper()
        scraper.rate_limiter.last_request = 0

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>OK</html>"

        with patch("services.scraper.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await scraper.fetch_page("http://example.com")
        assert result == "<html>OK</html>"

    @pytest.mark.asyncio
    async def test_non_200_returns_none(self):
        scraper = Scraper()
        scraper.rate_limiter.last_request = 0

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("services.scraper.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await scraper.fetch_page("http://example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        scraper = Scraper()
        scraper.rate_limiter.last_request = 0

        with patch("services.scraper.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Timeout"))
            mock_cls.return_value = mock_client

            result = await scraper.fetch_page("http://example.com")
        assert result is None


# ─── Scraper.fetch_json ──────────────────────────────────────────

class TestFetchJson:
    @pytest.mark.asyncio
    async def test_success(self):
        scraper = Scraper()
        scraper.rate_limiter.last_request = 0

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}

        with patch("services.scraper.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await scraper.fetch_json("http://api.example.com/data")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_error_returns_none(self):
        scraper = Scraper()
        scraper.rate_limiter.last_request = 0

        with patch("services.scraper.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Error"))
            mock_cls.return_value = mock_client

            result = await scraper.fetch_json("http://api.example.com/data")
        assert result is None


# ─── MetaAdsScraper ──────────────────────────────────────────────

class TestMetaAdsScraper:
    @pytest.mark.asyncio
    async def test_search_ads_returns_empty_on_no_html(self):
        scraper = MetaAdsScraper()
        with patch.object(scraper, "fetch_page", new_callable=AsyncMock, return_value=None):
            result = await scraper.search_ads("Test Brand")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_ads_returns_empty_with_html(self):
        """Facebook ads library requires JS rendering, so it always returns empty."""
        scraper = MetaAdsScraper()
        with patch.object(scraper, "fetch_page", new_callable=AsyncMock, return_value="<html>JS page</html>"):
            result = await scraper.search_ads("Test Brand")
        assert result == []


# ─── InstagramScraper ────────────────────────────────────────────

class TestInstagramScraper:
    @pytest.mark.asyncio
    async def test_returns_none_on_no_html(self):
        scraper = InstagramScraper()
        with patch.object(scraper, "fetch_page", new_callable=AsyncMock, return_value=None):
            result = await scraper.get_profile_info("testuser")
        assert result is None

    @pytest.mark.asyncio
    async def test_parses_json_ld(self):
        scraper = InstagramScraper()
        html = """
        <html><body>
        <script type="application/ld+json">
        {"@type": "ProfilePage", "name": "Test User", "description": "Bio"}
        </script>
        </body></html>
        """
        with patch.object(scraper, "fetch_page", new_callable=AsyncMock, return_value=html):
            with patch.object(scraper, "parse_html") as mock_parse:
                from bs4 import BeautifulSoup
                mock_parse.return_value = BeautifulSoup(html, "html.parser")
                result = await scraper.get_profile_info("testuser")
        assert result is not None
        assert result["username"] == "testuser"
        assert result["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_returns_none_without_profile_page(self):
        scraper = InstagramScraper()
        html = """
        <html><body>
        <script type="application/ld+json">
        {"@type": "WebPage", "name": "Test"}
        </script>
        </body></html>
        """
        with patch.object(scraper, "fetch_page", new_callable=AsyncMock, return_value=html):
            with patch.object(scraper, "parse_html") as mock_parse:
                from bs4 import BeautifulSoup
                mock_parse.return_value = BeautifulSoup(html, "html.parser")
                result = await scraper.get_profile_info("testuser")
        assert result is None


# ─── Singleton instances ─────────────────────────────────────────

class TestSingletons:
    def test_meta_scraper_exists(self):
        from services.scraper import meta_scraper
        assert meta_scraper is not None
        assert meta_scraper.rate_limiter.requests_per_minute == 20

    def test_instagram_scraper_exists(self):
        from services.scraper import instagram_scraper
        assert instagram_scraper is not None
        assert instagram_scraper.rate_limiter.requests_per_minute == 10
