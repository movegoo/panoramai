"""Tests for services/vgeo_analyzer.py — VGEO (Video GEO) Analyzer."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from services.vgeo_analyzer import (
    VgeoAnalyzer,
    _generate_vgeo_queries,
    VGEO_QUERIES,
)


# ─── _generate_vgeo_queries ─────────────────────────────────────

class TestGenerateVgeoQueries:
    def test_returns_6_queries(self):
        queries = _generate_vgeo_queries("jardinage")
        assert len(queries) == 6

    def test_sector_in_queries(self):
        queries = _generate_vgeo_queries("jardinage")
        assert all("jardinage" in q for q in queries)

    def test_known_sector_in_dict(self):
        assert "supermarche" in VGEO_QUERIES
        assert len(VGEO_QUERIES["supermarche"]) == 6


# ─── _calculate_score ────────────────────────────────────────────

class TestCalculateScore:
    def setup_method(self):
        with patch("services.vgeo_analyzer.GeoAnalyzer"):
            self.analyzer = VgeoAnalyzer()

    def test_all_help_videos(self):
        """All HELP videos → high alignment score."""
        brand_videos = [
            {"classification": "HELP", "video_id": f"v{i}"} for i in range(10)
        ]
        all_videos = [
            {"id": f"v{i}", "published_at": (datetime.utcnow() - timedelta(days=10)).isoformat()}
            for i in range(10)
        ]
        citations = {"claude": [], "gemini": [], "chatgpt": [], "mistral": []}
        scores = self.analyzer._calculate_score(
            brand_videos=brand_videos,
            all_videos=all_videos,
            citations=citations,
            brand_name="TestBrand",
            competitors=[],
            all_classifications={},
        )
        assert scores["alignment"] == 100
        assert 0 <= scores["total"] <= 100

    def test_no_videos(self):
        """No videos → low scores but no crash."""
        scores = self.analyzer._calculate_score(
            brand_videos=[],
            all_videos=[],
            citations={"claude": [], "gemini": [], "chatgpt": [], "mistral": []},
            brand_name="TestBrand",
            competitors=[],
            all_classifications={},
        )
        assert scores["total"] >= 0
        assert scores["alignment"] == 0

    def test_mixed_classification(self):
        """Mixed HELP/HUB/HERO → bonus for balance."""
        brand_videos = [
            {"classification": "HELP", "video_id": "v1"},
            {"classification": "HELP", "video_id": "v2"},
            {"classification": "HUB", "video_id": "v3"},
            {"classification": "HERO", "video_id": "v4"},
        ]
        all_videos = [
            {"id": f"v{i}", "published_at": (datetime.utcnow() - timedelta(days=5)).isoformat()}
            for i in range(1, 5)
        ]
        citations = {"claude": [], "gemini": [], "chatgpt": [], "mistral": []}
        scores = self.analyzer._calculate_score(
            brand_videos=brand_videos,
            all_videos=all_videos,
            citations=citations,
            brand_name="TestBrand",
            competitors=[],
            all_classifications={},
        )
        assert scores["alignment"] > 50  # HELP ratio + balance bonus

    def test_freshness_recent_videos(self):
        """All recent videos → high freshness."""
        brand_videos = []
        all_videos = [
            {"id": f"v{i}", "published_at": (datetime.utcnow() - timedelta(days=10)).isoformat()}
            for i in range(5)
        ]
        citations = {"claude": [], "gemini": [], "chatgpt": [], "mistral": []}
        scores = self.analyzer._calculate_score(
            brand_videos=brand_videos,
            all_videos=all_videos,
            citations=citations,
            brand_name="TestBrand",
            competitors=[],
            all_classifications={},
        )
        assert scores["freshness"] == 100

    def test_freshness_old_videos(self):
        """All old videos → low freshness."""
        all_videos = [
            {"id": f"v{i}", "published_at": (datetime.utcnow() - timedelta(days=200)).isoformat()}
            for i in range(5)
        ]
        citations = {"claude": [], "gemini": [], "chatgpt": [], "mistral": []}
        scores = self.analyzer._calculate_score(
            brand_videos=[],
            all_videos=all_videos,
            citations=citations,
            brand_name="TestBrand",
            competitors=[],
            all_classifications={},
        )
        assert scores["freshness"] == 0

    def test_presence_with_citations(self):
        """Brand cited in LLM responses → presence score."""
        citations = {
            "claude": [{"brand": "TestBrand", "query": "q1", "recommended": True}],
            "gemini": [{"brand": "TestBrand", "query": "q2", "recommended": True}],
            "chatgpt": [{"brand": "Other", "query": "q1", "recommended": True}],
            "mistral": [],
        }
        scores = self.analyzer._calculate_score(
            brand_videos=[],
            all_videos=[],
            citations=citations,
            brand_name="TestBrand",
            competitors=["Other"],
            all_classifications={},
        )
        assert scores["presence"] > 0

    def test_competitivity_brand_vs_competitors(self):
        """Brand with more citations than competitors → high competitivity."""
        citations = {
            "claude": [
                {"brand": "TestBrand", "query": "q1"},
                {"brand": "TestBrand", "query": "q2"},
            ],
            "gemini": [{"brand": "Rival", "query": "q1"}],
            "chatgpt": [],
            "mistral": [],
        }
        scores = self.analyzer._calculate_score(
            brand_videos=[],
            all_videos=[],
            citations=citations,
            brand_name="TestBrand",
            competitors=["Rival"],
            all_classifications={},
        )
        assert scores["competitivity"] == 100

    def test_scores_clamped_0_100(self):
        """All scores should be between 0 and 100."""
        scores = self.analyzer._calculate_score(
            brand_videos=[{"classification": "HELP"}] * 50,
            all_videos=[{"id": "v", "published_at": datetime.utcnow().isoformat()}] * 50,
            citations={
                "claude": [{"brand": "TestBrand", "query": f"q{i}"} for i in range(50)],
                "gemini": [], "chatgpt": [], "mistral": [],
            },
            brand_name="TestBrand",
            competitors=[],
            all_classifications={},
        )
        for key in ("total", "alignment", "freshness", "presence", "competitivity"):
            assert 0 <= scores[key] <= 100


# ─── _fetch_channel_videos ──────────────────────────────────────

class TestFetchChannelVideos:
    @pytest.mark.asyncio
    async def test_success(self):
        with patch("services.vgeo_analyzer.GeoAnalyzer"):
            analyzer = VgeoAnalyzer()
        with patch("services.vgeo_analyzer.youtube_api") as mock_yt:
            mock_yt.fetch_recent_videos = AsyncMock(return_value={
                "success": True,
                "videos": [{"id": "v1", "title": "Test"}],
            })
            result = await analyzer._fetch_channel_videos("UCxxx", "TestChannel")
        assert len(result) == 1
        assert result[0]["id"] == "v1"

    @pytest.mark.asyncio
    async def test_failure_returns_empty(self):
        with patch("services.vgeo_analyzer.GeoAnalyzer"):
            analyzer = VgeoAnalyzer()
        with patch("services.vgeo_analyzer.youtube_api") as mock_yt:
            mock_yt.fetch_recent_videos = AsyncMock(side_effect=Exception("API error"))
            result = await analyzer._fetch_channel_videos("UCxxx", "TestChannel")
        assert result == []

    @pytest.mark.asyncio
    async def test_api_returns_failure(self):
        with patch("services.vgeo_analyzer.GeoAnalyzer"):
            analyzer = VgeoAnalyzer()
        with patch("services.vgeo_analyzer.youtube_api") as mock_yt:
            mock_yt.fetch_recent_videos = AsyncMock(return_value={"success": False})
            result = await analyzer._fetch_channel_videos("UCxxx", "TestChannel")
        assert result == []


# ─── _classify_videos ────────────────────────────────────────────

class TestClassifyVideos:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_unknown(self):
        with patch("services.vgeo_analyzer.GeoAnalyzer"):
            analyzer = VgeoAnalyzer()
        with patch("services.vgeo_analyzer.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = ""
            videos = [{"id": "v1", "title": "Test"}]
            result = await analyzer._classify_videos(videos)
        assert len(result) == 1
        assert result[0]["classification"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_empty_videos(self):
        with patch("services.vgeo_analyzer.GeoAnalyzer"):
            analyzer = VgeoAnalyzer()
        with patch("services.vgeo_analyzer.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "key"
            result = await analyzer._classify_videos([])
        assert result == []


# ─── _generate_diagnostic ───────────────────────────────────────

class TestGenerateDiagnostic:
    @pytest.mark.asyncio
    async def test_no_api_key(self):
        with patch("services.vgeo_analyzer.GeoAnalyzer"):
            analyzer = VgeoAnalyzer()
        with patch("services.vgeo_analyzer.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = ""
            result = await analyzer._generate_diagnostic(
                brand_name="Test",
                sector="supermarche",
                scores={"total": 50, "alignment": 50, "freshness": 50, "presence": 50, "competitivity": 50},
                brand_classifications=[],
                competitor_scores=[],
                citations={"claude": [], "gemini": [], "chatgpt": [], "mistral": []},
            )
        assert "manquante" in result["diagnostic"]
        assert result["forces"] == []
