"""Tests for the Smart Filter service."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from services.smart_filter import SmartFilterService


@pytest.fixture
def service():
    return SmartFilterService()


class TestParseJson:
    """Test JSON parsing and validation."""

    def test_valid_json_with_filters(self, service):
        raw = json.dumps({
            "filters": {"products_contain": ["fruit"], "display_format": ["VIDEO"]},
            "interpretation": "Vidéos avec des fruits",
        })
        result = service._parse_json(raw)
        assert result is not None
        assert result["filters"]["products_contain"] == ["fruit"]
        assert result["filters"]["display_format"] == ["VIDEO"]
        assert result["interpretation"] == "Vidéos avec des fruits"

    def test_valid_json_with_markdown_fences(self, service):
        raw = '```json\n{"filters": {"text_search": "test"}, "interpretation": "Recherche"}\n```'
        result = service._parse_json(raw)
        assert result is not None
        assert result["filters"]["text_search"] == "test"

    def test_empty_filters_returns_none(self, service):
        raw = json.dumps({"filters": {}, "interpretation": ""})
        result = service._parse_json(raw)
        assert result is None

    def test_null_values_stripped(self, service):
        raw = json.dumps({
            "filters": {"products_contain": ["yaourt"], "display_format": None, "text_search": ""},
            "interpretation": "Yaourts",
        })
        result = service._parse_json(raw)
        assert result is not None
        assert "display_format" not in result["filters"]
        assert "text_search" not in result["filters"]
        assert result["filters"]["products_contain"] == ["yaourt"]

    def test_empty_lists_stripped(self, service):
        raw = json.dumps({
            "filters": {"products_contain": [], "competitor_name": ["Leclerc"]},
            "interpretation": "Leclerc",
        })
        result = service._parse_json(raw)
        assert result is not None
        assert "products_contain" not in result["filters"]
        assert result["filters"]["competitor_name"] == ["Leclerc"]

    def test_invalid_json_returns_none(self, service):
        result = service._parse_json("not json at all")
        assert result is None

    def test_flat_dict_treated_as_filters(self, service):
        raw = json.dumps({"creative_tone": ["humoristique"], "display_format": ["VIDEO"]})
        result = service._parse_json(raw)
        assert result is not None
        assert result["filters"]["creative_tone"] == ["humoristique"]
        assert result["interpretation"] == "Filtres appliqués"


@pytest.mark.asyncio
class TestParseQuery:
    """Test the full parse_query flow."""

    async def test_fallback_when_no_api_key(self):
        service = SmartFilterService()
        with patch.object(type(service), "gemini_key", new_callable=lambda: property(lambda self: "")):
            result = await service.parse_query("pubs avec des fruits")
        assert result["filters"]["text_search"] == "pubs avec des fruits"
        assert "manquante" in result["interpretation"]

    async def test_successful_gemini_call(self):
        service = SmartFilterService()
        mock_response = json.dumps({
            "filters": {"products_contain": ["fruit"], "product_category": ["Fruits & Légumes"]},
            "interpretation": "Publicités contenant des fruits",
        })
        with patch.object(service, "_call_gemini", new_callable=AsyncMock, return_value=mock_response):
            with patch.object(type(service), "gemini_key", new_callable=lambda: property(lambda self: "fake-key")):
                result = await service.parse_query("pubs avec des fruits")
        assert result["filters"]["products_contain"] == ["fruit"]
        assert "fruits" in result["interpretation"].lower()

    async def test_fallback_on_gemini_error(self):
        service = SmartFilterService()
        with patch.object(service, "_call_gemini", new_callable=AsyncMock, side_effect=Exception("API error")):
            with patch.object(type(service), "gemini_key", new_callable=lambda: property(lambda self: "fake-key")):
                result = await service.parse_query("test query")
        assert result["filters"]["text_search"] == "test query"

    async def test_fallback_on_unparseable_response(self):
        service = SmartFilterService()
        with patch.object(service, "_call_gemini", new_callable=AsyncMock, return_value="garbage output"):
            with patch.object(type(service), "gemini_key", new_callable=lambda: property(lambda self: "fake-key")):
                result = await service.parse_query("test query")
        assert result["filters"]["text_search"] == "test query"
