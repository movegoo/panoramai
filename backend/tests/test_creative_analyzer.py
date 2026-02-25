"""Tests for CreativeAnalyzer — _get_image, _fetch_fresh_image, analyze_creative."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

from services.creative_analyzer import CreativeAnalyzer


# ── Helpers ──────────────────────────────────────────────────────────

FAKE_JPEG = b'\xff\xd8' + b'\x00' * 2000   # valid JPEG magic + enough bytes
FAKE_PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 2000


def _make_response(status_code=200, content=FAKE_JPEG, headers=None):
    """Build a fake httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.text = content.decode("latin-1") if isinstance(content, bytes) else content
    resp.headers = headers or {"content-type": "image/jpeg"}
    return resp


# ── _detect_media_type ───────────────────────────────────────────────

class TestDetectMediaType:
    def test_jpeg(self):
        assert CreativeAnalyzer._detect_media_type(FAKE_JPEG) == "image/jpeg"

    def test_png(self):
        assert CreativeAnalyzer._detect_media_type(FAKE_PNG) == "image/png"

    def test_webp(self):
        data = b'RIFF' + b'\x00' * 4 + b'WEBP' + b'\x00' * 100
        assert CreativeAnalyzer._detect_media_type(data) == "image/webp"

    def test_gif(self):
        assert CreativeAnalyzer._detect_media_type(b'GIF89a' + b'\x00' * 100) == "image/gif"
        assert CreativeAnalyzer._detect_media_type(b'GIF87a' + b'\x00' * 100) == "image/gif"

    def test_unknown(self):
        assert CreativeAnalyzer._detect_media_type(b'\x00\x00\x00\x00') == ""


# ── _get_image ───────────────────────────────────────────────────────

class TestGetImage:
    """Tests for _get_image orchestration."""

    @pytest.mark.asyncio
    async def test_calls_fetch_fresh_when_ad_id_provided(self):
        """When ad_id is given, _fetch_fresh_image is called first."""
        analyzer = CreativeAnalyzer()
        with patch.object(analyzer, "_fetch_fresh_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg", "https://fresh.url/img.jpg")) as mock_fresh:
            data, mt, url = await analyzer._get_image("https://old.url/img.jpg", "123456")

        mock_fresh.assert_awaited_once_with("123456")
        assert data == FAKE_JPEG
        assert mt == "image/jpeg"
        assert url == "https://fresh.url/img.jpg"

    @pytest.mark.asyncio
    async def test_skips_fetch_fresh_when_no_ad_id(self):
        """When ad_id is empty, _fetch_fresh_image is NOT called."""
        analyzer = CreativeAnalyzer()
        with patch.object(analyzer, "_fetch_fresh_image", new_callable=AsyncMock) as mock_fresh, \
             patch.object(analyzer, "_download_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg")) as mock_dl:
            data, mt, url = await analyzer._get_image("https://old.url/img.jpg", "")

        mock_fresh.assert_not_awaited()
        mock_dl.assert_awaited_once_with("https://old.url/img.jpg")
        assert data == FAKE_JPEG
        assert url == ""

    @pytest.mark.asyncio
    async def test_falls_back_to_download_when_fresh_fails(self):
        """When _fetch_fresh_image returns None, falls back to _download_image."""
        analyzer = CreativeAnalyzer()
        with patch.object(analyzer, "_fetch_fresh_image", new_callable=AsyncMock,
                          return_value=(None, "", "")) as mock_fresh, \
             patch.object(analyzer, "_download_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg")) as mock_dl:
            data, mt, url = await analyzer._get_image("https://old.url/img.jpg", "ad999")

        mock_fresh.assert_awaited_once_with("ad999")
        mock_dl.assert_awaited_once_with("https://old.url/img.jpg")
        assert data == FAKE_JPEG
        assert mt == "image/jpeg"
        assert url == ""  # no fresh URL since fresh fetch failed

    @pytest.mark.asyncio
    async def test_returns_none_when_both_fail(self):
        """When both fresh fetch and download fail, returns (None, '', '')."""
        analyzer = CreativeAnalyzer()
        with patch.object(analyzer, "_fetch_fresh_image", new_callable=AsyncMock,
                          return_value=(None, "", "")), \
             patch.object(analyzer, "_download_image", new_callable=AsyncMock,
                          return_value=(None, "")):
            data, mt, url = await analyzer._get_image("https://old.url/img.jpg", "ad999")

        assert data is None
        assert mt == ""
        assert url == ""


# ── _fetch_fresh_image ───────────────────────────────────────────────

class TestFetchFreshImage:
    """Tests for the 3-tier fresh image fetching (Meta -> ScrapeCreators -> SearchAPI)."""

    @pytest.mark.asyncio
    async def test_meta_api_returns_image_directly(self):
        """When Meta snapshot returns an image (content-type: image/*), use it."""
        analyzer = CreativeAnalyzer()
        resp = _make_response(content=FAKE_JPEG, headers={"content-type": "image/jpeg"})

        with patch.dict("os.environ", {"META_ACCESS_TOKEN": "tok123"}), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            data, mt, url = await analyzer._fetch_fresh_image("111222")

        assert data == FAKE_JPEG
        assert mt == "image/jpeg"
        assert "111222" in url
        assert "access_token=tok123" in url

    @pytest.mark.asyncio
    async def test_meta_api_returns_html_with_fbcdn(self):
        """When Meta snapshot returns HTML containing an fbcdn img src, extract and download it."""
        analyzer = CreativeAnalyzer()
        html = '<html><body><img src="https://scontent.fbcdn.net/v/image.jpg&amp;token=abc" /></body></html>'
        html_resp = MagicMock()
        html_resp.status_code = 200
        html_resp.headers = {"content-type": "text/html; charset=utf-8"}
        html_resp.text = html

        with patch.dict("os.environ", {"META_ACCESS_TOKEN": "tok123"}), \
             patch("httpx.AsyncClient") as mock_client_cls, \
             patch.object(analyzer, "_download_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg")) as mock_dl:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=html_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            data, mt, url = await analyzer._fetch_fresh_image("111222")

        assert data == FAKE_JPEG
        assert mt == "image/jpeg"
        # The extracted URL should have &amp; replaced with &
        mock_dl.assert_awaited_once()
        called_url = mock_dl.call_args[0][0]
        assert "fbcdn" in called_url
        assert "&amp;" not in called_url

    @pytest.mark.asyncio
    async def test_meta_api_skipped_when_no_token(self):
        """When META_ACCESS_TOKEN is not set, skip Meta and try ScrapeCreators."""
        analyzer = CreativeAnalyzer()

        mock_sc = AsyncMock()
        mock_sc.get_facebook_ad_detail_raw = AsyncMock(return_value={
            "snapshot": {
                "cards": [{"original_image_url": "https://fbcdn.net/fresh.jpg"}],
                "images": [],
            }
        })

        with patch.dict("os.environ", {"META_ACCESS_TOKEN": ""}, clear=False), \
             patch("services.creative_analyzer.httpx.AsyncClient") as mock_httpx, \
             patch("services.scrapecreators.scrapecreators", mock_sc), \
             patch.object(analyzer, "_download_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg")):
            # Meta path should not be attempted (no token)
            data, mt, url = await analyzer._fetch_fresh_image("ad555")

        assert data == FAKE_JPEG
        assert url == "https://fbcdn.net/fresh.jpg"

    @pytest.mark.asyncio
    async def test_scrapecreators_fallback_after_meta_fails(self):
        """When Meta fails (e.g. 403), fall back to ScrapeCreators."""
        analyzer = CreativeAnalyzer()

        # Meta returns 403
        meta_resp = _make_response(status_code=403, content=b"Forbidden")

        mock_sc = AsyncMock()
        mock_sc.get_facebook_ad_detail_raw = AsyncMock(return_value={
            "snapshot": {
                "cards": [],
                "images": [{"original_image_url": "https://fbcdn.net/sc_img.jpg"}],
            }
        })

        with patch.dict("os.environ", {"META_ACCESS_TOKEN": "tok123"}), \
             patch("httpx.AsyncClient") as mock_client_cls, \
             patch("services.scrapecreators.scrapecreators", mock_sc), \
             patch.object(analyzer, "_download_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg")):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=meta_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            data, mt, url = await analyzer._fetch_fresh_image("ad777")

        assert data == FAKE_JPEG
        assert url == "https://fbcdn.net/sc_img.jpg"

    @pytest.mark.asyncio
    async def test_scrapecreators_cards_priority(self):
        """ScrapeCreators: cards[0] is used before images[0]."""
        analyzer = CreativeAnalyzer()

        mock_sc = AsyncMock()
        mock_sc.get_facebook_ad_detail_raw = AsyncMock(return_value={
            "snapshot": {
                "cards": [{"original_image_url": "https://fbcdn.net/card.jpg"}],
                "images": [{"original_image_url": "https://fbcdn.net/image.jpg"}],
            }
        })

        with patch.dict("os.environ", {"META_ACCESS_TOKEN": ""}, clear=False), \
             patch("services.scrapecreators.scrapecreators", mock_sc), \
             patch.object(analyzer, "_download_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg")):
            data, mt, url = await analyzer._fetch_fresh_image("ad888")

        assert url == "https://fbcdn.net/card.jpg"

    @pytest.mark.asyncio
    async def test_scrapecreators_resized_fallback(self):
        """ScrapeCreators: resized_image_url used when original is absent."""
        analyzer = CreativeAnalyzer()

        mock_sc = AsyncMock()
        mock_sc.get_facebook_ad_detail_raw = AsyncMock(return_value={
            "snapshot": {
                "cards": [{"resized_image_url": "https://fbcdn.net/resized.jpg"}],
                "images": [],
            }
        })

        with patch.dict("os.environ", {"META_ACCESS_TOKEN": ""}, clear=False), \
             patch("services.scrapecreators.scrapecreators", mock_sc), \
             patch.object(analyzer, "_download_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg")):
            data, mt, url = await analyzer._fetch_fresh_image("ad888")

        assert url == "https://fbcdn.net/resized.jpg"

    @pytest.mark.asyncio
    async def test_searchapi_fallback_after_scrapecreators_fails(self):
        """When both Meta and ScrapeCreators fail, SearchAPI is tried."""
        analyzer = CreativeAnalyzer()

        # Meta: no token
        # ScrapeCreators: raises
        mock_sc = AsyncMock()
        mock_sc.get_facebook_ad_detail_raw = AsyncMock(side_effect=Exception("SC down"))

        mock_search = MagicMock()
        mock_search.is_configured = True
        mock_search.get_ad_details = AsyncMock(return_value={
            "raw": {
                "snapshot": {
                    "images": [{"original_image_url": "https://fbcdn.net/search.jpg"}],
                    "cards": [],
                }
            }
        })

        with patch.dict("os.environ", {"META_ACCESS_TOKEN": ""}, clear=False), \
             patch("services.scrapecreators.scrapecreators", mock_sc), \
             patch("services.searchapi.searchapi", mock_search), \
             patch.object(analyzer, "_download_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg")):
            data, mt, url = await analyzer._fetch_fresh_image("ad999")

        assert data == FAKE_JPEG
        assert url == "https://fbcdn.net/search.jpg"

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_none(self):
        """When all three sources fail, return (None, '', '')."""
        analyzer = CreativeAnalyzer()

        mock_sc = AsyncMock()
        mock_sc.get_facebook_ad_detail_raw = AsyncMock(side_effect=Exception("SC down"))

        mock_search = MagicMock()
        mock_search.is_configured = True
        mock_search.get_ad_details = AsyncMock(side_effect=Exception("Search down"))

        with patch.dict("os.environ", {"META_ACCESS_TOKEN": ""}, clear=False), \
             patch("services.scrapecreators.scrapecreators", mock_sc), \
             patch("services.searchapi.searchapi", mock_search):
            data, mt, url = await analyzer._fetch_fresh_image("ad000")

        assert data is None
        assert mt == ""
        assert url == ""

    @pytest.mark.asyncio
    async def test_searchapi_skipped_when_not_configured(self):
        """When SearchAPI is not configured, it's skipped gracefully."""
        analyzer = CreativeAnalyzer()

        mock_sc = AsyncMock()
        mock_sc.get_facebook_ad_detail_raw = AsyncMock(return_value={"snapshot": {"cards": [], "images": []}})

        mock_search = MagicMock()
        mock_search.is_configured = False

        with patch.dict("os.environ", {"META_ACCESS_TOKEN": ""}, clear=False), \
             patch("services.scrapecreators.scrapecreators", mock_sc), \
             patch("services.searchapi.searchapi", mock_search):
            data, mt, url = await analyzer._fetch_fresh_image("ad111")

        mock_search.get_ad_details.assert_not_called()
        assert data is None


# ── analyze_creative ─────────────────────────────────────────────────

class TestAnalyzeCreative:
    """Tests for the top-level analyze_creative method."""

    @pytest.mark.asyncio
    async def test_attaches_fresh_url_to_result(self):
        """When _get_image returns a fresh_url, it's attached as _fresh_url."""
        analyzer = CreativeAnalyzer()
        mock_result = {"concept": "promo", "score": 80, "tags": ["test"]}

        with patch.object(type(analyzer), "gemini_key", new_callable=PropertyMock, return_value="key123"), \
             patch.object(analyzer, "_get_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg", "https://fresh.url/img.jpg")), \
             patch.object(analyzer, "_call_gemini_vision", new_callable=AsyncMock,
                          return_value=mock_result):
            result = await analyzer.analyze_creative(
                "https://old.url/img.jpg", ad_text="promo", ad_id="ad123"
            )

        assert result is not None
        assert result["_fresh_url"] == "https://fresh.url/img.jpg"
        assert result["concept"] == "promo"

    @pytest.mark.asyncio
    async def test_no_fresh_url_when_empty(self):
        """When fresh_url is empty, _fresh_url is NOT attached."""
        analyzer = CreativeAnalyzer()
        mock_result = {"concept": "promo", "score": 80, "tags": ["test"]}

        with patch.object(type(analyzer), "gemini_key", new_callable=PropertyMock, return_value="key123"), \
             patch.object(analyzer, "_get_image", new_callable=AsyncMock,
                          return_value=(FAKE_JPEG, "image/jpeg", "")), \
             patch.object(analyzer, "_call_gemini_vision", new_callable=AsyncMock,
                          return_value=mock_result):
            result = await analyzer.analyze_creative(
                "https://old.url/img.jpg", ad_text="promo", ad_id="ad123"
            )

        assert result is not None
        assert "_fresh_url" not in result

    @pytest.mark.asyncio
    async def test_returns_none_when_image_download_fails(self):
        """When image download fails completely, returns None."""
        analyzer = CreativeAnalyzer()

        with patch.object(type(analyzer), "gemini_key", new_callable=PropertyMock, return_value="key123"), \
             patch.object(analyzer, "_get_image", new_callable=AsyncMock,
                          return_value=(None, "", "")):
            result = await analyzer.analyze_creative(
                "https://old.url/img.jpg", ad_text="promo", ad_id="ad123"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_gemini_key(self):
        """Without GEMINI_API_KEY, analyze_creative returns None."""
        analyzer = CreativeAnalyzer()

        with patch.object(type(analyzer), "gemini_key", new_callable=PropertyMock, return_value=""):
            result = await analyzer.analyze_creative("https://old.url/img.jpg")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_url(self):
        """Without a creative_url, analyze_creative returns None."""
        analyzer = CreativeAnalyzer()

        with patch.object(type(analyzer), "gemini_key", new_callable=PropertyMock, return_value="key123"):
            result = await analyzer.analyze_creative("")

        assert result is None


# ── _download_image ──────────────────────────────────────────────────

class TestDownloadImage:
    """Tests for _download_image edge cases."""

    @pytest.mark.asyncio
    async def test_rejects_too_small_image(self):
        """Images under 1000 bytes are rejected as broken."""
        analyzer = CreativeAnalyzer()
        tiny = b'\xff\xd8' + b'\x00' * 10  # only 12 bytes

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            resp = _make_response(content=tiny)
            mock_client.get = AsyncMock(return_value=resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            data, mt = await analyzer._download_image("https://example.com/tiny.jpg")

        assert data is None

    @pytest.mark.asyncio
    async def test_rejects_too_large_image(self):
        """Images over 5MB are rejected."""
        analyzer = CreativeAnalyzer()
        huge = b'\xff\xd8' + b'\x00' * (6 * 1024 * 1024)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            resp = _make_response(content=huge)
            mock_client.get = AsyncMock(return_value=resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            data, mt = await analyzer._download_image("https://example.com/huge.jpg")

        assert data is None

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        """Non-200 responses return (None, '')."""
        analyzer = CreativeAnalyzer()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            resp = _make_response(status_code=404, content=b"Not Found")
            mock_client.get = AsyncMock(return_value=resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            data, mt = await analyzer._download_image("https://example.com/missing.jpg")

        assert data is None
        assert mt == ""


# ── _parse_analysis ──────────────────────────────────────────────────

class TestParseAnalysis:
    """Tests for JSON parsing and validation."""

    def test_valid_json(self):
        analyzer = CreativeAnalyzer()
        raw = '{"concept": "promo", "score": 85, "tags": ["a"], "dominant_colors": ["#FFF"]}'
        result = analyzer._parse_analysis(raw)
        assert result["concept"] == "promo"
        assert result["score"] == 85

    def test_strips_markdown_fences(self):
        analyzer = CreativeAnalyzer()
        raw = '```json\n{"concept": "promo", "score": 50}\n```'
        result = analyzer._parse_analysis(raw)
        assert result["concept"] == "promo"

    def test_clamps_score_to_100(self):
        analyzer = CreativeAnalyzer()
        raw = '{"score": 150}'
        result = analyzer._parse_analysis(raw)
        assert result["score"] == 100

    def test_clamps_score_to_0(self):
        analyzer = CreativeAnalyzer()
        raw = '{"score": -10}'
        result = analyzer._parse_analysis(raw)
        assert result["score"] == 0

    def test_invalid_json_returns_none(self):
        analyzer = CreativeAnalyzer()
        assert analyzer._parse_analysis("not json at all") is None
