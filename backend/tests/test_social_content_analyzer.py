"""Tests for services/social_content_analyzer.py — Social Content Analyzer."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from services.social_content_analyzer import SocialContentAnalyzer


# ─── _detect_media_type ──────────────────────────────────────────

class TestDetectMediaType:
    def test_png(self):
        data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        assert SocialContentAnalyzer._detect_media_type(data) == "image/png"

    def test_jpeg(self):
        data = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        assert SocialContentAnalyzer._detect_media_type(data) == "image/jpeg"

    def test_gif(self):
        data = b'GIF89a' + b'\x00' * 100
        assert SocialContentAnalyzer._detect_media_type(data) == "image/gif"

    def test_webp(self):
        data = b'RIFF\x00\x00\x00\x00WEBP' + b'\x00' * 100
        assert SocialContentAnalyzer._detect_media_type(data) == "image/webp"

    def test_unknown(self):
        data = b'\x00\x00\x00\x00' + b'\x00' * 100
        assert SocialContentAnalyzer._detect_media_type(data) == ""


# ─── _parse_analysis ─────────────────────────────────────────────

class TestParseAnalysis:
    def setup_method(self):
        self.analyzer = SocialContentAnalyzer()

    def test_valid_json(self):
        text = '{"theme": "promo", "engagement_score": 75, "hook": "Accroche", "tone": "fun", "format": "reel", "cta": "Achetez", "summary": "Bon contenu", "hashtags": ["#promo"], "mentions": [], "virality_factors": [], "visual_elements": "", "thumbnail_quality": "bon"}'
        result = self.analyzer._parse_analysis(text)
        assert result is not None
        assert result["theme"] == "promo"
        assert result["engagement_score"] == 75

    def test_json_with_markdown_fences(self):
        text = '```json\n{"theme": "promo", "engagement_score": 50}\n```'
        result = self.analyzer._parse_analysis(text)
        assert result is not None
        assert result["theme"] == "promo"

    def test_json_embedded_in_text(self):
        text = 'Here is the analysis: {"theme": "promo", "engagement_score": 80} end.'
        result = self.analyzer._parse_analysis(text)
        assert result is not None
        assert result["theme"] == "promo"

    def test_invalid_json(self):
        result = self.analyzer._parse_analysis("not json at all")
        assert result is None

    def test_score_clamped(self):
        text = '{"theme": "promo", "engagement_score": 150}'
        result = self.analyzer._parse_analysis(text)
        assert result["engagement_score"] == 100

    def test_negative_score_clamped(self):
        text = '{"theme": "promo", "engagement_score": -10}'
        result = self.analyzer._parse_analysis(text)
        assert result["engagement_score"] == 0

    def test_non_numeric_score(self):
        text = '{"theme": "promo", "engagement_score": "high"}'
        result = self.analyzer._parse_analysis(text)
        assert result["engagement_score"] == 0

    def test_missing_arrays_defaulted(self):
        text = '{"theme": "promo", "engagement_score": 50, "hashtags": "not_an_array"}'
        result = self.analyzer._parse_analysis(text)
        assert result["hashtags"] == []
        assert result["mentions"] == []
        assert result["virality_factors"] == []

    def test_missing_strings_defaulted(self):
        text = '{"engagement_score": 50}'
        result = self.analyzer._parse_analysis(text)
        assert result["theme"] == ""
        assert result["hook"] == ""
        assert result["tone"] == ""
        assert result["summary"] == ""


# ─── _extract_prompt ─────────────────────────────────────────────

class TestExtractPrompt:
    def test_gemini_payload(self):
        payload = {"contents": [{"parts": [{"text": "Analyze this"}]}]}
        assert SocialContentAnalyzer._extract_prompt(payload, is_gemini=True) == "Analyze this"

    def test_gemini_payload_with_image(self):
        payload = {"contents": [{"parts": [{"inline_data": {}}, {"text": "Analyze this"}]}]}
        assert SocialContentAnalyzer._extract_prompt(payload, is_gemini=True) == "Analyze this"

    def test_mistral_payload(self):
        payload = {"messages": [{"role": "user", "content": "Analyze this"}]}
        assert SocialContentAnalyzer._extract_prompt(payload, is_gemini=False) == "Analyze this"

    def test_empty_gemini(self):
        payload = {"contents": [{"parts": []}]}
        assert SocialContentAnalyzer._extract_prompt(payload, is_gemini=True) == ""

    def test_empty_mistral(self):
        payload = {"messages": [{}]}
        assert SocialContentAnalyzer._extract_prompt(payload, is_gemini=False) == ""


# ─── _fuse_results ───────────────────────────────────────────────

class TestFuseResults:
    def setup_method(self):
        self.analyzer = SocialContentAnalyzer()

    def test_gemini_only(self):
        gemini = {"theme": "promo", "engagement_score": 70, "hashtags": ["#a"], "virality_factors": [], "summary": "G", "hook": "G"}
        result = self.analyzer._fuse_results(gemini, None)
        assert result == gemini

    def test_mistral_only(self):
        mistral = {"theme": "promo", "engagement_score": 80, "hashtags": ["#b"], "virality_factors": [], "summary": "M", "hook": "M"}
        result = self.analyzer._fuse_results(None, mistral)
        assert result == mistral

    def test_both_none(self):
        result = self.analyzer._fuse_results(None, None)
        assert result is None

    def test_both_present_averages_score(self):
        gemini = {"theme": "promo", "engagement_score": 60, "hashtags": ["#a"], "virality_factors": ["factor1"], "summary": "Short", "hook": "Short"}
        mistral = {"theme": "lifestyle", "engagement_score": 80, "hashtags": ["#b"], "virality_factors": ["factor2"], "summary": "A longer summary text", "hook": "A longer hook text"}
        result = self.analyzer._fuse_results(gemini, mistral)
        assert result["engagement_score"] == 70  # average
        assert "#a" in result["hashtags"]
        assert "#b" in result["hashtags"]
        assert "factor1" in result["virality_factors"]
        assert "factor2" in result["virality_factors"]
        assert result["summary"] == "A longer summary text"
        assert result["hook"] == "A longer hook text"
        assert result["theme"] == "promo"  # Gemini wins

    def test_merge_hashtags_limit(self):
        gemini = {"engagement_score": 50, "hashtags": [f"#g{i}" for i in range(8)], "virality_factors": [], "summary": "", "hook": ""}
        mistral = {"engagement_score": 50, "hashtags": [f"#m{i}" for i in range(8)], "virality_factors": [], "summary": "", "hook": ""}
        result = self.analyzer._fuse_results(gemini, mistral)
        assert len(result["hashtags"]) <= 10

    def test_merge_virality_factors_limit(self):
        gemini = {"engagement_score": 50, "hashtags": [], "virality_factors": [f"vg{i}" for i in range(4)], "summary": "", "hook": ""}
        mistral = {"engagement_score": 50, "hashtags": [], "virality_factors": [f"vm{i}" for i in range(4)], "summary": "", "hook": ""}
        result = self.analyzer._fuse_results(gemini, mistral)
        assert len(result["virality_factors"]) <= 5


# ─── _download_image ─────────────────────────────────────────────

class TestDownloadImage:
    @pytest.mark.asyncio
    async def test_success(self):
        analyzer = SocialContentAnalyzer()
        fake_jpeg = b'\xff\xd8\xff\xe0' + b'\x00' * 1000

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_jpeg
        mock_response.headers = {"content-type": "image/jpeg"}

        with patch("services.social_content_analyzer.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            data, media_type = await analyzer._download_image("http://example.com/img.jpg")
        assert data == fake_jpeg
        assert media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_too_small(self):
        analyzer = SocialContentAnalyzer()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'\xff\xd8' + b'\x00' * 10
        mock_response.headers = {"content-type": "image/jpeg"}

        with patch("services.social_content_analyzer.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            data, media_type = await analyzer._download_image("http://example.com/img.jpg")
        assert data is None

    @pytest.mark.asyncio
    async def test_http_error(self):
        analyzer = SocialContentAnalyzer()
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("services.social_content_analyzer.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            data, media_type = await analyzer._download_image("http://example.com/img.jpg")
        assert data is None

    @pytest.mark.asyncio
    async def test_timeout(self):
        import httpx
        analyzer = SocialContentAnalyzer()

        with patch("services.social_content_analyzer.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_cls.return_value = mock_client

            data, media_type = await analyzer._download_image("http://example.com/img.jpg")
        assert data is None


# ─── analyze_content ─────────────────────────────────────────────

class TestAnalyzeContent:
    @pytest.mark.asyncio
    async def test_no_keys(self):
        analyzer = SocialContentAnalyzer()
        with patch.object(type(analyzer), "gemini_key", property(lambda s: "")):
            with patch.object(type(analyzer), "mistral_key", property(lambda s: "")):
                result = await analyzer.analyze_content(title="Test")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_content(self):
        analyzer = SocialContentAnalyzer()
        with patch.object(type(analyzer), "gemini_key", property(lambda s: "key")):
            result = await analyzer.analyze_content(title="", description="", thumbnail_url="")
        assert result is None


# ─── Singleton ───────────────────────────────────────────────────

class TestSingleton:
    def test_singleton_exists(self):
        from services.social_content_analyzer import social_content_analyzer
        assert social_content_analyzer is not None
        assert isinstance(social_content_analyzer, SocialContentAnalyzer)
