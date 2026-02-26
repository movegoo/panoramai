"""Tests for GEO Analyzer: platform querying, response analysis, retry logic."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.geo_analyzer import GeoAnalyzer, get_geo_queries


class TestGetGeoQueries:
    """Test sector-specific query generation."""

    def test_supermarche_returns_queries(self):
        queries = get_geo_queries("supermarche", "Grande Distribution", ["Carrefour", "Leclerc"])
        assert len(queries) >= 10
        assert all("keyword" in q and "query" in q for q in queries)

    def test_unknown_sector_generates_fallback(self):
        queries = get_geo_queries("unknown_sector", "Unknown", ["BrandA", "BrandB"])
        assert len(queries) >= 5
        assert any("BrandA" in q["query"] or "Unknown" in q["query"] for q in queries)

    def test_known_sectors_exist(self):
        for sector in ["supermarche", "mode", "beaute", "electromenager", "bricolage", "sport"]:
            queries = get_geo_queries(sector, sector, ["Test"])
            assert len(queries) == 12, f"{sector} should have 12 queries"


class TestGeoAnalyzerPlatforms:
    """Test platform availability checks."""

    def test_get_available_platforms(self):
        analyzer = GeoAnalyzer()
        with patch("services.geo_analyzer.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = "key1"
            mock_settings.GEMINI_API_KEY = ""
            mock_settings.OPENAI_API_KEY = "key3"
            mock_settings.MISTRAL_API_KEY = None
            platforms = analyzer.get_available_platforms()
        assert platforms["claude"] is True
        assert platforms["gemini"] is False
        assert platforms["chatgpt"] is True
        assert platforms["mistral"] is False


class TestQueryPlatforms:
    """Test individual platform query methods."""

    def setup_method(self):
        self.analyzer = GeoAnalyzer()

    @pytest.mark.asyncio
    async def test_claude_missing_key(self):
        with patch("services.geo_analyzer.settings") as s:
            s.ANTHROPIC_API_KEY = ""
            result = await self.analyzer._query_claude("test")
        assert result == ""
        assert any("ANTHROPIC_API_KEY" in e for e in self.analyzer.errors)

    @pytest.mark.asyncio
    async def test_chatgpt_missing_key(self):
        with patch("services.geo_analyzer.settings") as s:
            s.OPENAI_API_KEY = ""
            result = await self.analyzer._query_chatgpt("test")
        assert result == ""
        assert any("OPENAI_API_KEY" in e for e in self.analyzer.errors)

    @pytest.mark.asyncio
    async def test_gemini_missing_key(self):
        with patch("services.geo_analyzer.settings") as s:
            s.GEMINI_API_KEY = ""
            result = await self.analyzer._query_gemini("test")
        assert result == ""
        assert any("GEMINI_API_KEY" in e for e in self.analyzer.errors)

    @pytest.mark.asyncio
    async def test_mistral_missing_key(self):
        with patch("services.geo_analyzer.settings") as s:
            s.MISTRAL_API_KEY = ""
            result = await self.analyzer._query_mistral("test")
        assert result == ""
        assert any("MISTRAL_API_KEY" in e for e in self.analyzer.errors)

    @pytest.mark.asyncio
    async def test_claude_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"text": "Carrefour est le meilleur supermarche."}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.geo_analyzer.httpx.AsyncClient", return_value=mock_client):
            with patch("services.geo_analyzer.settings") as s:
                s.ANTHROPIC_API_KEY = "test-key"
                result = await self.analyzer._query_claude("Quel supermarche ?")

        assert "Carrefour" in result

    @pytest.mark.asyncio
    async def test_chatgpt_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Leclerc est recommande."}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.geo_analyzer.httpx.AsyncClient", return_value=mock_client):
            with patch("services.geo_analyzer.settings") as s:
                s.OPENAI_API_KEY = "test-key"
                result = await self.analyzer._query_chatgpt("Quel supermarche ?")

        assert "Leclerc" in result


class TestAnalyzeResponse:
    """Test the Gemini Flash analysis with retry logic."""

    def setup_method(self):
        self.analyzer = GeoAnalyzer()

    @pytest.mark.asyncio
    async def test_analyze_empty_answer_returns_none(self):
        with patch("services.geo_analyzer.settings") as s:
            s.GEMINI_API_KEY = "key"
            result = await self.analyzer._analyze_response("query", "", ["Brand"], platform="test")
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_missing_key_returns_none(self):
        with patch("services.geo_analyzer.settings") as s:
            s.GEMINI_API_KEY = ""
            result = await self.analyzer._analyze_response("query", "answer", ["Brand"], platform="test")
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_success(self):
        analysis_result = {
            "primary_recommendation": "Carrefour",
            "brands_mentioned": [
                {"name": "Carrefour", "position": 1, "recommended": True, "sentiment": "positif", "context": "Le meilleur"},
            ],
            "key_criteria": ["prix", "qualite"],
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": json.dumps(analysis_result)}]}}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.geo_analyzer.httpx.AsyncClient", return_value=mock_client):
            with patch("services.geo_analyzer.settings") as s:
                s.GEMINI_API_KEY = "key"
                result = await self.analyzer._analyze_response(
                    "Quel supermarche ?", "Carrefour est super.", ["Carrefour"], platform="chatgpt"
                )

        assert result is not None
        assert result["primary_recommendation"] == "Carrefour"
        assert len(result["brands_mentioned"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_retries_on_failure(self):
        """Should retry once on failure before giving up."""
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary failure")
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": '{"brands_mentioned": [], "primary_recommendation": ""}'}]}}],
                "usageMetadata": {},
            }
            return resp

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.geo_analyzer.httpx.AsyncClient", return_value=mock_client):
            with patch("services.geo_analyzer.settings") as s:
                s.GEMINI_API_KEY = "key"
                result = await self.analyzer._analyze_response(
                    "query", "answer", ["Brand"], platform="claude"
                )

        assert call_count == 2  # First failed, second succeeded
        assert result is not None


class TestProcessSingleQuery:
    """Test the full query processing pipeline."""

    def setup_method(self):
        self.analyzer = GeoAnalyzer()

    @pytest.mark.asyncio
    async def test_all_platforms_fail_returns_empty(self):
        with patch.object(self.analyzer, "_query_claude", return_value=""):
            with patch.object(self.analyzer, "_query_gemini", return_value=""):
                with patch.object(self.analyzer, "_query_chatgpt", return_value=""):
                    with patch.object(self.analyzer, "_query_mistral", return_value=""):
                        results = await self.analyzer._process_single_query(
                            "test_kw", "Test query?", ["Brand"]
                        )
        assert results == []

    @pytest.mark.asyncio
    async def test_partial_platform_success(self):
        """When only some platforms respond, results should still be generated."""
        analysis = {
            "primary_recommendation": "Carrefour",
            "brands_mentioned": [
                {"name": "Carrefour", "position": 1, "recommended": True, "sentiment": "positif", "context": "Numero 1"},
            ],
            "key_criteria": ["prix"],
        }

        with patch.object(self.analyzer, "_query_claude", return_value=""):
            with patch.object(self.analyzer, "_query_gemini", return_value=""):
                with patch.object(self.analyzer, "_query_chatgpt", return_value="ChatGPT says Carrefour"):
                    with patch.object(self.analyzer, "_query_mistral", return_value=""):
                        with patch.object(self.analyzer, "_analyze_response", return_value=analysis):
                            results = await self.analyzer._process_single_query(
                                "test_kw", "Test query?", ["Carrefour"]
                            )

        assert len(results) == 1
        assert results[0]["platform"] == "chatgpt"
        assert results[0]["brand_name"] == "Carrefour"
