"""Tests for VGEO (Video GEO) analyzer and endpoints."""
import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from database import VgeoReport


# ---------------------------------------------------------------------------
# Unit tests: score calculation
# ---------------------------------------------------------------------------

class TestVgeoScoreCalculation:
    """Test the _calculate_score method of VgeoAnalyzer."""

    def _get_analyzer(self):
        from services.vgeo_analyzer import VgeoAnalyzer
        return VgeoAnalyzer()

    def test_score_all_help_videos(self):
        """Brand with 100% HELP videos should have high alignment."""
        analyzer = self._get_analyzer()
        brand_videos = [
            {"video_id": "1", "classification": "HELP", "keywords": []},
            {"video_id": "2", "classification": "HELP", "keywords": []},
            {"video_id": "3", "classification": "HELP", "keywords": []},
        ]
        all_videos = [
            {"id": "1", "published_at": "2026-02-01T00:00:00Z"},
            {"id": "2", "published_at": "2026-01-15T00:00:00Z"},
            {"id": "3", "published_at": "2025-12-01T00:00:00Z"},
        ]
        citations = {"claude": [], "gemini": [], "chatgpt": [], "mistral": []}

        scores = analyzer._calculate_score(
            brand_videos=brand_videos,
            all_videos=all_videos,
            citations=citations,
            brand_name="TestBrand",
            competitors=[],
            all_classifications={},
        )

        assert scores["alignment"] >= 80
        assert 0 <= scores["total"] <= 100
        assert all(0 <= scores[k] <= 100 for k in ["alignment", "freshness", "presence", "competitivity"])

    def test_score_no_videos(self):
        """Empty channel should get low scores."""
        analyzer = self._get_analyzer()
        scores = analyzer._calculate_score(
            brand_videos=[],
            all_videos=[],
            citations={"claude": [], "gemini": [], "chatgpt": [], "mistral": []},
            brand_name="TestBrand",
            competitors=[],
            all_classifications={},
        )

        assert scores["total"] >= 0
        assert scores["total"] <= 50  # Should be relatively low

    def test_score_with_citations(self):
        """Brand cited by LLMs should have higher presence score."""
        analyzer = self._get_analyzer()
        citations = {
            "claude": [
                {"brand": "TestBrand", "query": "q1", "recommended": True, "sentiment": "positif", "context": ""},
                {"brand": "TestBrand", "query": "q2", "recommended": False, "sentiment": "neutre", "context": ""},
            ],
            "gemini": [
                {"brand": "TestBrand", "query": "q1", "recommended": True, "sentiment": "positif", "context": ""},
            ],
            "chatgpt": [],
            "mistral": [],
        }

        scores = analyzer._calculate_score(
            brand_videos=[{"video_id": "1", "classification": "HELP", "keywords": []}],
            all_videos=[{"id": "1", "published_at": "2026-02-01T00:00:00Z"}],
            citations=citations,
            brand_name="TestBrand",
            competitors=["Competitor1"],
            all_classifications={},
        )

        assert scores["presence"] > 0

    def test_score_balanced_mix(self):
        """Balanced HELP/HUB/HERO mix should get bonus."""
        analyzer = self._get_analyzer()
        brand_videos = [
            {"video_id": "1", "classification": "HELP", "keywords": []},
            {"video_id": "2", "classification": "HELP", "keywords": []},
            {"video_id": "3", "classification": "HUB", "keywords": []},
            {"video_id": "4", "classification": "HERO", "keywords": []},
        ]

        scores = analyzer._calculate_score(
            brand_videos=brand_videos,
            all_videos=[{"id": str(i), "published_at": "2026-02-01T00:00:00Z"} for i in range(4)],
            citations={"claude": [], "gemini": [], "chatgpt": [], "mistral": []},
            brand_name="TestBrand",
            competitors=[],
            all_classifications={},
        )

        # Should get alignment bonus for balanced mix
        assert scores["alignment"] > 50


# ---------------------------------------------------------------------------
# Unit tests: classification
# ---------------------------------------------------------------------------

class TestVgeoClassification:
    """Test video classification HELP/HUB/HERO."""

    @pytest.mark.asyncio
    @patch("services.vgeo_analyzer.settings")
    async def test_classify_no_gemini_key(self, mock_settings):
        """Without Gemini key, should return UNKNOWN for all videos."""
        mock_settings.GEMINI_API_KEY = ""
        from services.vgeo_analyzer import VgeoAnalyzer
        analyzer = VgeoAnalyzer()

        videos = [{"id": "v1", "title": "Tutorial cooking"}, {"id": "v2", "title": "Big event"}]
        result = await analyzer._classify_videos(videos)

        assert len(result) == 2
        assert all(v["classification"] == "UNKNOWN" for v in result)

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    @patch("services.vgeo_analyzer.settings")
    async def test_classify_with_gemini(self, mock_settings, mock_post):
        """With Gemini key, should parse classification response."""
        mock_settings.GEMINI_API_KEY = "test-key"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps([
                            {"video_id": "v1", "classification": "HELP", "keywords": ["tutorial"]},
                            {"video_id": "v2", "classification": "HERO", "keywords": ["event"]},
                        ])
                    }]
                }
            }]
        }
        mock_post.return_value = mock_response

        from services.vgeo_analyzer import VgeoAnalyzer
        analyzer = VgeoAnalyzer()

        videos = [{"id": "v1", "title": "Tutorial cooking"}, {"id": "v2", "title": "Big event"}]
        result = await analyzer._classify_videos(videos)

        assert len(result) == 2
        assert result[0]["classification"] == "HELP"
        assert result[1]["classification"] == "HERO"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestVgeoEndpoints:
    """Test VGEO API endpoints."""

    def test_get_report_no_data(self, client, adv_headers):
        """GET /api/vgeo/report should return has_report=False when no report exists."""
        resp = client.get("/api/vgeo/report", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_report"] is False

    def test_get_report_with_data(self, client, db, adv_headers, test_advertiser):
        """GET /api/vgeo/report should return the latest report."""
        report = VgeoReport(
            advertiser_id=test_advertiser.id,
            score_total=72.0,
            score_alignment=80.0,
            score_freshness=65.0,
            score_presence=70.0,
            score_competitivity=68.0,
            report_data={
                "score": {"total": 72, "alignment": 80, "freshness": 65, "presence": 70, "competitivity": 68},
                "brand_channel": {"channel_id": "UC123", "video_count": 15},
                "competitors": [],
                "videos": [],
                "citations": {},
                "diagnostic": "Test diagnostic",
                "forces": ["Force 1"],
                "faiblesses": ["Faiblesse 1"],
                "strategy": [],
                "actions": [],
            },
        )
        db.add(report)
        db.commit()

        resp = client.get("/api/vgeo/report", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_report"] is True
        assert data["score"]["total"] == 72
        assert data["diagnostic"] == "Test diagnostic"

    def test_get_comparison_no_data(self, client, adv_headers):
        """GET /api/vgeo/comparison should return has_data=False when no report exists."""
        resp = client.get("/api/vgeo/comparison", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_data"] is False

    def test_get_comparison_with_data(self, client, db, adv_headers, test_advertiser):
        """GET /api/vgeo/comparison should return competitor data from latest report."""
        report = VgeoReport(
            advertiser_id=test_advertiser.id,
            score_total=72.0,
            score_alignment=80.0,
            score_freshness=65.0,
            score_presence=70.0,
            score_competitivity=68.0,
            report_data={
                "score": {"total": 72, "alignment": 80, "freshness": 65, "presence": 70, "competitivity": 68},
                "competitors": [
                    {"name": "Carrefour", "score": {"total": 65}, "video_count": 10, "citations": 5},
                ],
            },
        )
        db.add(report)
        db.commit()

        resp = client.get("/api/vgeo/comparison", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_data"] is True
        assert len(data["competitors"]) == 1
        assert data["competitors"][0]["name"] == "Carrefour"

    def test_report_requires_auth(self, client):
        """Endpoints should require authentication."""
        resp = client.get("/api/vgeo/report")
        assert resp.status_code in (401, 403, 422)

    def test_analyze_requires_advertiser_id(self, client, auth_headers):
        """POST /api/vgeo/analyze should require X-Advertiser-Id."""
        resp = client.post("/api/vgeo/analyze", headers=auth_headers)
        assert resp.status_code == 400

    @patch("services.vgeo_analyzer.vgeo_analyzer.analyze")
    def test_analyze_saves_report(self, mock_analyze, client, db, adv_headers, test_advertiser):
        """POST /api/vgeo/analyze should save a VgeoReport in DB."""
        mock_analyze.return_value = {
            "score": {"total": 75, "alignment": 80, "freshness": 70, "presence": 72, "competitivity": 65},
            "brand_channel": {"channel_id": "UC123", "video_count": 20},
            "competitors": [],
            "videos": [],
            "citations": {},
            "diagnostic": "Good strategy",
            "forces": [],
            "faiblesses": [],
            "strategy": [],
            "actions": [],
        }

        resp = client.post("/api/vgeo/analyze", headers=adv_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"]["total"] == 75
        assert "report_id" in data

        # Verify saved in DB
        report = db.query(VgeoReport).filter(VgeoReport.advertiser_id == test_advertiser.id).first()
        assert report is not None
        assert report.score_total == 75


# ---------------------------------------------------------------------------
# DB model tests
# ---------------------------------------------------------------------------

class TestVgeoReportModel:
    """Test VgeoReport model."""

    def test_create_report(self, db, test_advertiser):
        """Should create a VgeoReport with all fields."""
        report = VgeoReport(
            advertiser_id=test_advertiser.id,
            score_total=72.0,
            score_alignment=80.0,
            score_freshness=65.0,
            score_presence=70.0,
            score_competitivity=68.0,
            report_data={"test": True},
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        assert report.id is not None
        assert report.advertiser_id == test_advertiser.id
        assert report.score_total == 72.0
        assert report.report_data == {"test": True}
        assert report.created_at is not None

    def test_multiple_reports_per_advertiser(self, db, test_advertiser):
        """Should allow multiple reports per advertiser (history)."""
        for i in range(3):
            report = VgeoReport(
                advertiser_id=test_advertiser.id,
                score_total=70.0 + i,
                report_data={"iteration": i},
            )
            db.add(report)
        db.commit()

        reports = db.query(VgeoReport).filter(
            VgeoReport.advertiser_id == test_advertiser.id
        ).order_by(VgeoReport.created_at.desc()).all()

        assert len(reports) == 3
