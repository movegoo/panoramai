"""Tests for multi-page smart filter service and router."""
import os
import pytest
from unittest.mock import patch, AsyncMock

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from services.smart_filter import SmartFilterService, PAGE_PROMPTS
from routers.smart_filter import SmartFilterRequest


class TestPagePrompts:
    """Verify all expected page prompts exist."""

    EXPECTED_PAGES = [
        "ads", "social", "apps", "geo", "seo",
        "signals", "tendances", "overview", "geo-tracking", "vgeo",
    ]

    def test_all_pages_have_prompts(self):
        for page in self.EXPECTED_PAGES:
            assert page in PAGE_PROMPTS, f"Missing prompt for page: {page}"

    def test_each_prompt_contains_rules(self):
        for page, prompt in PAGE_PROMPTS.items():
            assert "RÈGLES" in prompt, f"Page '{page}' prompt missing RÈGLES section"
            assert "JSON" in prompt, f"Page '{page}' prompt missing JSON instruction"

    def test_ads_prompt_has_ad_fields(self):
        prompt = PAGE_PROMPTS["ads"]
        assert "display_format" in prompt
        assert "creative_concept" in prompt
        assert "platform" in prompt

    def test_social_prompt_has_social_fields(self):
        prompt = PAGE_PROMPTS["social"]
        assert "platform" in prompt
        assert "growth_direction" in prompt
        assert "competitor_name" in prompt

    def test_geo_tracking_prompt_has_ai_fields(self):
        prompt = PAGE_PROMPTS["geo-tracking"]
        assert "sentiment" in prompt
        assert "recommended" in prompt
        assert "claude" in prompt or "chatgpt" in prompt


class TestSmartFilterService:
    """Test SmartFilterService logic."""

    def test_parse_json_valid(self):
        svc = SmartFilterService()
        result = svc._parse_json('{"filters": {"competitor_name": ["Leclerc"]}, "interpretation": "Pubs Leclerc"}')
        assert result is not None
        assert result["filters"]["competitor_name"] == ["Leclerc"]
        assert result["interpretation"] == "Pubs Leclerc"

    def test_parse_json_with_markdown_fences(self):
        svc = SmartFilterService()
        raw = '```json\n{"filters": {"platform": ["meta"]}, "interpretation": "Meta"}\n```'
        result = svc._parse_json(raw)
        assert result is not None
        assert result["filters"]["platform"] == ["meta"]

    def test_parse_json_empty_filters_returns_none(self):
        svc = SmartFilterService()
        result = svc._parse_json('{"filters": {}, "interpretation": "Rien"}')
        assert result is None

    def test_parse_json_cleans_nulls(self):
        svc = SmartFilterService()
        raw = '{"filters": {"competitor_name": ["Auchan"], "platform": null, "text_search": ""}, "interpretation": "Test"}'
        result = svc._parse_json(raw)
        assert result is not None
        assert "platform" not in result["filters"]
        assert "text_search" not in result["filters"]
        assert result["filters"]["competitor_name"] == ["Auchan"]

    def test_parse_json_invalid_json(self):
        svc = SmartFilterService()
        result = svc._parse_json("not json at all")
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_query_no_api_key(self):
        svc = SmartFilterService()
        with patch.object(type(svc), "gemini_key", new_callable=lambda: property(lambda self: "")):
            result = await svc.parse_query("test query", page="social")
        assert result["filters"]["text_search"] == "test query"
        assert "manquante" in result["interpretation"]

    @pytest.mark.asyncio
    async def test_parse_query_calls_gemini_with_page_prompt(self):
        svc = SmartFilterService()
        with patch.object(type(svc), "gemini_key", new_callable=lambda: property(lambda self: "fake-key")):
            with patch.object(svc, "_call_gemini", new_callable=AsyncMock) as mock_gemini:
                mock_gemini.return_value = '{"filters": {"platform": ["instagram"]}, "interpretation": "Instagram"}'
                result = await svc.parse_query("show Instagram data", page="social")
                # Verify the social prompt was passed
                call_args = mock_gemini.call_args
                assert "social" in call_args[0][1].lower() or "réseaux" in call_args[0][1].lower()
                assert result["filters"]["platform"] == ["instagram"]

    @pytest.mark.asyncio
    async def test_parse_query_fallback_on_error(self):
        svc = SmartFilterService()
        with patch.object(type(svc), "gemini_key", new_callable=lambda: property(lambda self: "fake-key")):
            with patch.object(svc, "_call_gemini", new_callable=AsyncMock) as mock_gemini:
                mock_gemini.side_effect = Exception("API Error")
                result = await svc.parse_query("test", page="ads")
        assert result["filters"]["text_search"] == "test"

    @pytest.mark.asyncio
    async def test_parse_query_unknown_page_defaults_to_ads(self):
        svc = SmartFilterService()
        with patch.object(type(svc), "gemini_key", new_callable=lambda: property(lambda self: "fake-key")):
            with patch.object(svc, "_call_gemini", new_callable=AsyncMock) as mock_gemini:
                mock_gemini.return_value = '{"filters": {"text_search": "test"}, "interpretation": "Test"}'
                result = await svc.parse_query("test", page="nonexistent_page")
                # Should use ads prompt (default)
                call_args = mock_gemini.call_args
                assert "publicités" in call_args[0][1].lower() or "display_format" in call_args[0][1]


class TestSmartFilterRequest:
    """Test the request model."""

    def test_default_page_is_ads(self):
        req = SmartFilterRequest(query="test")
        assert req.page == "ads"

    def test_custom_page(self):
        req = SmartFilterRequest(query="test", page="social")
        assert req.page == "social"


class TestSmartFilterEndpoint:
    """Test the /api/smart-filter endpoint."""

    def test_endpoint_exists(self):
        from main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with patch("routers.smart_filter.smart_filter_service") as mock_svc:
            mock_svc.parse_query = AsyncMock(return_value={
                "filters": {"competitor_name": ["Leclerc"]},
                "interpretation": "Pubs Leclerc",
            })
            response = client.post("/api/smart-filter", json={"query": "Leclerc", "page": "ads"})
            assert response.status_code == 200
            data = response.json()
            assert "filters" in data
            assert "interpretation" in data

    def test_endpoint_with_page_param(self):
        from main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with patch("routers.smart_filter.smart_filter_service") as mock_svc:
            mock_svc.parse_query = AsyncMock(return_value={
                "filters": {"platform": ["instagram"]},
                "interpretation": "Instagram",
            })
            response = client.post("/api/smart-filter", json={"query": "Instagram", "page": "social"})
            assert response.status_code == 200
            mock_svc.parse_query.assert_called_once_with("Instagram", page="social")

    def test_legacy_endpoint_still_works(self):
        """The old /api/creative/smart-filter should still work."""
        from main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with patch("routers.creative_analysis.smart_filter_service") as mock_svc:
            mock_svc.parse_query = AsyncMock(return_value={
                "filters": {"text_search": "test"},
                "interpretation": "Test",
            })
            response = client.post("/api/creative/smart-filter", json={"query": "test"})
            assert response.status_code == 200
