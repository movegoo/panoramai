"""Tests for the e-reputation service (KPI computation, sentiment parsing)."""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.ereputation_service import EReputationService


@pytest.fixture
def service():
    return EReputationService()


def _make_comment(sentiment="positive", categories=None, source_type="owned", platform="youtube", likes=5, replies=1):
    return {
        "platform": platform,
        "comment_id": f"yt_{id(object())}",
        "source_type": source_type,
        "text": "Test comment",
        "author": "User",
        "likes": likes,
        "replies": replies,
        "sentiment": sentiment,
        "sentiment_score": 0.8 if sentiment == "positive" else (-0.8 if sentiment == "negative" else 0.0),
        "categories": categories or [],
        "is_alert": False,
        "alert_reason": "",
    }


class TestComputeKPIs:
    def test_all_positive(self, service):
        comments = [_make_comment("positive") for _ in range(10)]
        kpis = service.compute_kpis(comments)
        # 1.0*50 + (1-0)*25 + (1-0)*25 = 100
        assert kpis["reputation_score"] == 100.0
        assert kpis["nps"] == 100.0
        assert kpis["sav_rate"] == 0.0
        assert kpis["financial_risk_rate"] == 0.0
        assert kpis["total_comments"] == 10
        assert kpis["sentiment_breakdown"]["positive"] == 10
        assert kpis["sentiment_breakdown"]["negative"] == 0

    def test_all_negative(self, service):
        comments = [_make_comment("negative") for _ in range(10)]
        kpis = service.compute_kpis(comments)
        # 0.0*50 + (1-0)*25 + (1-0)*25 = 50
        assert kpis["reputation_score"] == 50.0
        assert kpis["nps"] == -100.0
        assert kpis["sentiment_breakdown"]["negative"] == 10

    def test_mixed_sentiment(self, service):
        comments = (
            [_make_comment("positive") for _ in range(6)]
            + [_make_comment("negative") for _ in range(2)]
            + [_make_comment("neutral") for _ in range(2)]
        )
        kpis = service.compute_kpis(comments)
        # 0.6*50 + (1-0)*25 + (1-0)*25 = 30+25+25 = 80
        assert kpis["reputation_score"] == 80.0
        assert kpis["nps"] == 40.0  # (60% - 20%) * 100
        assert kpis["total_comments"] == 10

    def test_empty_comments(self, service):
        kpis = service.compute_kpis([])
        assert kpis["reputation_score"] == 0.0
        assert kpis["nps"] == 0.0
        assert kpis["total_comments"] == 0
        assert kpis["sentiment_breakdown"]["positive"] == 0

    def test_sav_rate(self, service):
        comments = [
            _make_comment("negative", categories=["sav"]),
            _make_comment("negative", categories=["livraison"]),
            _make_comment("negative", categories=["service"]),
            _make_comment("positive", categories=["qualite"]),
            _make_comment("neutral"),
        ]
        kpis = service.compute_kpis(comments)
        assert kpis["sav_rate"] == 60.0  # 3 out of 5

    def test_financial_risk_rate(self, service):
        comments = [
            _make_comment("negative", categories=["prix"]),
            _make_comment("negative", categories=["prix"]),
            _make_comment("positive", categories=["prix"]),  # not negative, not counted
            _make_comment("neutral"),
            _make_comment("positive"),
        ]
        kpis = service.compute_kpis(comments)
        assert kpis["financial_risk_rate"] == 40.0  # 2 negative+prix out of 5

    def test_earned_ratio(self, service):
        comments = [
            _make_comment(source_type="owned"),
            _make_comment(source_type="owned"),
            _make_comment(source_type="earned"),
        ]
        kpis = service.compute_kpis(comments)
        assert abs(kpis["earned_ratio"] - 33.3) < 0.5

    def test_engagement_rate(self, service):
        comments = [
            _make_comment(likes=10, replies=2),
            _make_comment(likes=20, replies=8),
        ]
        kpis = service.compute_kpis(comments)
        # total interactions = (10+2) + (20+8) = 40, avg = 20
        assert kpis["engagement_rate"] == 20.0

    def test_platform_breakdown(self, service):
        comments = [
            _make_comment(platform="youtube", sentiment="positive"),
            _make_comment(platform="youtube", sentiment="negative"),
            _make_comment(platform="tiktok", sentiment="neutral"),
        ]
        kpis = service.compute_kpis(comments)
        assert kpis["platform_breakdown"]["youtube"]["total"] == 2
        assert kpis["platform_breakdown"]["youtube"]["positive"] == 1
        assert kpis["platform_breakdown"]["youtube"]["negative"] == 1
        assert kpis["platform_breakdown"]["tiktok"]["total"] == 1

    def test_nps_capped(self, service):
        """NPS should be capped between -100 and +100."""
        # All positive
        comments = [_make_comment("positive") for _ in range(5)]
        kpis = service.compute_kpis(comments)
        assert kpis["nps"] <= 100

        # All negative
        comments = [_make_comment("negative") for _ in range(5)]
        kpis = service.compute_kpis(comments)
        assert kpis["nps"] >= -100


class TestSentimentBatch:
    @pytest.mark.asyncio
    async def test_analyze_no_key(self, service):
        """Without API key, comments should get default neutral sentiment."""
        with patch.object(type(service), "gemini_key", new_callable=lambda: property(lambda s: "")):
            comments = [_make_comment("positive")]
            result = await service.analyze_sentiment_batch(comments, "TestBrand")
            # Should return comments unchanged
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_analyze_gemini_error(self, service):
        """On Gemini API error, comments get default neutral."""
        with patch.object(type(service), "gemini_key", new_callable=lambda: property(lambda s: "fake-key")):
            with patch("httpx.AsyncClient.post", side_effect=Exception("API Error")):
                comments = [{"text": "Good product", "platform": "youtube"}]
                result = await service.analyze_sentiment_batch(comments, "TestBrand")
                assert len(result) == 1
                assert result[0]["sentiment"] == "neutral"
                assert result[0]["is_alert"] is False

    @pytest.mark.asyncio
    async def test_analyze_valid_response(self, service):
        """Valid Gemini response should enrich comments."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps([{
                            "index": 0,
                            "sentiment": "positive",
                            "sentiment_score": 0.9,
                            "categories": ["qualite"],
                            "is_alert": False,
                            "alert_reason": "",
                        }])
                    }]
                }
            }]
        }

        with patch.object(type(service), "gemini_key", new_callable=lambda: property(lambda s: "fake-key")):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
                comments = [{"text": "Excellent product!", "platform": "youtube"}]
                result = await service.analyze_sentiment_batch(comments, "TestBrand")
                assert result[0]["sentiment"] == "positive"
                assert result[0]["sentiment_score"] == 0.9
                assert "qualite" in result[0]["categories"]
