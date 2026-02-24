"""Tests for the social content analyzer (Gemini + Mistral)."""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.social_content_analyzer import SocialContentAnalyzer


@pytest.fixture
def analyzer():
    a = SocialContentAnalyzer()
    return a


VALID_RESPONSE = {
    "theme": "promo",
    "hook": "Jusqu'a -50% sur tout le rayon frais",
    "tone": "promotionnel",
    "format": "short-form",
    "cta": "Rendez-vous en magasin",
    "hashtags": ["#promo", "#frais"],
    "mentions": ["@auchan"],
    "virality_factors": ["prix choc", "urgence"],
    "engagement_score": 72,
    "summary": "Post promotionnel classique axe sur les prix bas.",
}


class TestParseAnalysis:
    def test_valid_json(self, analyzer):
        result = analyzer._parse_analysis(json.dumps(VALID_RESPONSE))
        assert result["theme"] == "promo"
        assert result["engagement_score"] == 72

    def test_json_in_markdown_block(self, analyzer):
        text = f"```json\n{json.dumps(VALID_RESPONSE)}\n```"
        result = analyzer._parse_analysis(text)
        assert result is not None
        assert result["theme"] == "promo"

    def test_score_clamped(self, analyzer):
        data = {**VALID_RESPONSE, "engagement_score": 150}
        result = analyzer._parse_analysis(json.dumps(data))
        assert result["engagement_score"] == 100

    def test_score_negative_clamped(self, analyzer):
        data = {**VALID_RESPONSE, "engagement_score": -10}
        result = analyzer._parse_analysis(json.dumps(data))
        assert result["engagement_score"] == 0

    def test_missing_arrays_default(self, analyzer):
        data = {**VALID_RESPONSE}
        del data["hashtags"]
        data["mentions"] = "not_a_list"
        result = analyzer._parse_analysis(json.dumps(data))
        assert result["hashtags"] == []
        assert result["mentions"] == []

    def test_invalid_json(self, analyzer):
        result = analyzer._parse_analysis("this is not json at all")
        assert result is None


class TestFuseResults:
    def test_gemini_only(self, analyzer):
        result = analyzer._fuse_results(VALID_RESPONSE, None)
        assert result == VALID_RESPONSE

    def test_mistral_only(self, analyzer):
        result = analyzer._fuse_results(None, VALID_RESPONSE)
        assert result == VALID_RESPONSE

    def test_both_none(self, analyzer):
        result = analyzer._fuse_results(None, None)
        assert result is None

    def test_fuses_scores(self, analyzer):
        g = {**VALID_RESPONSE, "engagement_score": 80}
        m = {**VALID_RESPONSE, "engagement_score": 60}
        result = analyzer._fuse_results(g, m)
        assert result["engagement_score"] == 70

    def test_merges_hashtags(self, analyzer):
        g = {**VALID_RESPONSE, "hashtags": ["#a", "#b"]}
        m = {**VALID_RESPONSE, "hashtags": ["#b", "#c"]}
        result = analyzer._fuse_results(g, m)
        assert set(result["hashtags"]) == {"#a", "#b", "#c"}

    def test_uses_longer_summary(self, analyzer):
        g = {**VALID_RESPONSE, "summary": "Short."}
        m = {**VALID_RESPONSE, "summary": "A much longer and more detailed summary of the content."}
        result = analyzer._fuse_results(g, m)
        assert result["summary"] == m["summary"]


@pytest.mark.asyncio
async def test_analyze_no_keys(analyzer):
    with patch.object(type(analyzer), "gemini_key", new_callable=lambda: property(lambda self: "")), \
         patch.object(type(analyzer), "mistral_key", new_callable=lambda: property(lambda self: "")):
        result = await analyzer.analyze_content(title="Test", description="Desc")
        assert result is None


@pytest.mark.asyncio
async def test_analyze_empty_content(analyzer):
    result = await analyzer.analyze_content(title="", description="")
    assert result is None
