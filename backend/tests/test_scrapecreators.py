"""Tests for services/scrapecreators.py — ScrapeCreators API client."""
import os
import time
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from services.scrapecreators import ScrapeCreatorsAPI


# ─── __init__ / _headers ─────────────────────────────────────────

class TestInit:
    def test_custom_key(self):
        api = ScrapeCreatorsAPI(api_key="test-key")
        assert api.api_key == "test-key"
        assert api._headers == {"x-api-key": "test-key"}

    def test_no_key_warning(self):
        with patch("services.scrapecreators.settings") as mock_s:
            mock_s.SCRAPECREATORS_API_KEY = ""
            api = ScrapeCreatorsAPI(api_key="")
            assert api.api_key == ""


# ─── _get ────────────────────────────────────────────────────────

class TestGet:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}
        mock_response.raise_for_status = MagicMock()

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await api._get("/v1/test", {"key": "val"})
        assert result["success"] is True
        assert result["data"] == "value"

    @pytest.mark.asyncio
    async def test_explicit_success_false(self):
        api = ScrapeCreatorsAPI(api_key="test")
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": False, "message": "Bad request"}
        mock_response.raise_for_status = MagicMock()

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await api._get("/v1/test")
        assert result["success"] is False
        assert "Bad request" in result["error"]

    @pytest.mark.asyncio
    async def test_timeout(self):
        import httpx
        api = ScrapeCreatorsAPI(api_key="test")

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_cls.return_value = mock_client

            result = await api._get("/v1/test")
        assert result["success"] is False
        assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_http_status_error(self):
        import httpx
        api = ScrapeCreatorsAPI(api_key="test")

        mock_resp = MagicMock()
        mock_resp.status_code = 403

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=mock_resp)
            )
            mock_cls.return_value = mock_client

            result = await api._get("/v1/test")
        assert result["success"] is False
        assert "HTTP 403" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_exception(self):
        api = ScrapeCreatorsAPI(api_key="test")

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_cls.return_value = mock_client

            result = await api._get("/v1/test")
        assert result["success"] is False


# ─── _parse_tiktok_video_item ────────────────────────────────────

class TestParseTiktokVideoItem:
    def setup_method(self):
        self.api = ScrapeCreatorsAPI(api_key="test")

    def test_aweme_format(self):
        item = {
            "aweme_id": "123",
            "desc": "Test video",
            "create_time": 1700000000,
            "statistics": {
                "play_count": 10000,
                "digg_count": 500,
                "comment_count": 50,
                "share_count": 20,
            },
        }
        result = self.api._parse_tiktok_video_item(item)
        assert result["id"] == "123"
        assert result["views"] == 10000
        assert result["likes"] == 500
        assert result["comments"] == 50
        assert result["shares"] == 20

    def test_legacy_format(self):
        item = {
            "id": "456",
            "description": "Legacy video",
            "createTime": 1700000000,
            "stats": {
                "playCount": 5000,
                "diggCount": 200,
                "commentCount": 30,
                "shareCount": 10,
            },
        }
        result = self.api._parse_tiktok_video_item(item)
        assert result["id"] == "456"
        assert result["views"] == 5000

    def test_empty_stats(self):
        item = {"aweme_id": "789", "desc": ""}
        result = self.api._parse_tiktok_video_item(item)
        assert result["id"] == "789"
        assert result["views"] == 0
        assert result["likes"] == 0


# ─── _parse_youtube_video_item ───────────────────────────────────

class TestParseYoutubeVideoItem:
    def setup_method(self):
        self.api = ScrapeCreatorsAPI(api_key="test")

    def test_standard_format(self):
        item = {
            "id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "description": "A test",
            "publishedTimeText": "2 days ago",
            "viewCountInt": 1000000,
            "likeCountInt": 50000,
            "commentCountInt": 3000,
            "lengthText": "3:32",
        }
        result = self.api._parse_youtube_video_item(item)
        assert result["video_id"] == "dQw4w9WgXcQ"
        assert result["views"] == 1000000
        assert result["title"] == "Test Video"

    def test_thumbnail_as_dict(self):
        item = {
            "id": "abc",
            "title": "T",
            "thumbnail": {"url": "http://img.youtube.com/vi/abc/0.jpg"},
        }
        result = self.api._parse_youtube_video_item(item)
        assert result["thumbnail_url"] == "http://img.youtube.com/vi/abc/0.jpg"

    def test_thumbnail_as_string(self):
        item = {
            "id": "abc",
            "title": "T",
            "thumbnail": "http://img.youtube.com/vi/abc/0.jpg",
        }
        result = self.api._parse_youtube_video_item(item)
        assert result["thumbnail_url"] == "http://img.youtube.com/vi/abc/0.jpg"

    def test_long_title_truncated(self):
        item = {"id": "abc", "title": "A" * 2000}
        result = self.api._parse_youtube_video_item(item)
        assert len(result["title"]) <= 1000


# ─── fetch_instagram_profile ────────────────────────────────────

class TestFetchInstagramProfile:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "data": {
                "user": {
                    "edge_followed_by": {"count": 100000},
                    "edge_follow": {"count": 500},
                    "edge_owner_to_timeline_media": {
                        "count": 200,
                        "edges": [
                            {"node": {"edge_liked_by": {"count": 1000}, "edge_media_to_comment": {"count": 50}}},
                            {"node": {"edge_liked_by": {"count": 2000}, "edge_media_to_comment": {"count": 100}}},
                        ],
                    },
                    "biography": "Test bio",
                    "is_verified": True,
                    "is_business_account": True,
                    "full_name": "Test Brand",
                    "profile_pic_url_hd": "http://pic.url",
                },
            },
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_instagram_profile("@testbrand")
        assert result["success"] is True
        assert result["followers"] == 100000
        assert result["engagement_rate"] > 0

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "Not found"}):
            result = await api.fetch_instagram_profile("unknown")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_parse_error(self):
        api = ScrapeCreatorsAPI(api_key="test")
        # Missing "data" key triggers KeyError
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": True}):
            result = await api.fetch_instagram_profile("bad")
        assert result["success"] is False
        assert "Parse error" in result["error"]


# ─── fetch_tiktok_profile ───────────────────────────────────────

class TestFetchTiktokProfile:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "user": {"uniqueId": "testbrand", "nickname": "Test", "signature": "Bio", "verified": True},
            "stats": {"followerCount": 50000, "followingCount": 100, "heartCount": 500000, "videoCount": 200},
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_tiktok_profile("@testbrand")
        assert result["success"] is True
        assert result["followers"] == 50000
        assert result["likes"] == 500000

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.fetch_tiktok_profile("unknown")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_parse_error(self):
        api = ScrapeCreatorsAPI(api_key="test")
        # Force TypeError by making stats return non-int for heartCount
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={
            "success": True, "user": {"uniqueId": "x"}, "stats": MagicMock(get=MagicMock(side_effect=TypeError("bad")))
        }):
            result = await api.fetch_tiktok_profile("bad")
        assert result["success"] is False
        assert "Parse error" in result["error"]


# ─── fetch_tiktok_videos ──────────────────────────────────────

class TestFetchTiktokVideos:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "aweme_list": [
                {"aweme_id": "v1", "desc": "Video 1", "create_time": 1700000000,
                 "statistics": {"play_count": 1000, "digg_count": 100, "comment_count": 10, "share_count": 5}},
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_tiktok_videos("testuser")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["videos"][0]["id"] == "v1"

    @pytest.mark.asyncio
    async def test_fallback_to_profile(self):
        api = ScrapeCreatorsAPI(api_key="test")
        # First call (videos endpoint) returns success but no items
        videos_resp = {"success": True}
        # Second call (profile fallback) returns items
        profile_resp = {
            "success": True,
            "items": [
                {"aweme_id": "v2", "desc": "Fallback", "statistics": {"play_count": 500, "digg_count": 50, "comment_count": 5, "share_count": 2}},
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, side_effect=[videos_resp, profile_resp]):
            result = await api.fetch_tiktok_videos("testuser")
        assert result["success"] is True
        assert result["videos"][0]["id"] == "v2"

    @pytest.mark.asyncio
    async def test_both_fail(self):
        api = ScrapeCreatorsAPI(api_key="test")
        fail = {"success": False, "error": "Not found"}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=fail):
            result = await api.fetch_tiktok_videos("unknown")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_success_no_items_returns_empty(self):
        api = ScrapeCreatorsAPI(api_key="test")
        # Both endpoints succeed but have no video items
        empty_resp = {"success": True}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=empty_resp):
            result = await api.fetch_tiktok_videos("testuser")
        assert result["success"] is True
        assert result["videos"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_parse_error_primary(self):
        """Parse error on primary endpoint falls back to profile."""
        api = ScrapeCreatorsAPI(api_key="test")
        # Primary has items but they cause parse error; fallback has no items
        bad_items = {"success": True, "aweme_list": [None]}  # None causes AttributeError
        fallback_empty = {"success": True}
        with patch.object(api, "_get", new_callable=AsyncMock, side_effect=[bad_items, fallback_empty]):
            result = await api.fetch_tiktok_videos("test")
        assert result["success"] is True
        assert result["videos"] == []

    @pytest.mark.asyncio
    async def test_parse_error_fallback(self):
        """Parse error on fallback endpoint returns empty."""
        api = ScrapeCreatorsAPI(api_key="test")
        # Primary has no items; fallback has items that cause parse error
        primary_empty = {"success": True}
        bad_fallback = {"success": True, "items": [None]}
        with patch.object(api, "_get", new_callable=AsyncMock, side_effect=[primary_empty, bad_fallback]):
            result = await api.fetch_tiktok_videos("test")
        assert result["success"] is True
        assert result["videos"] == []


# ─── fetch_youtube_channel ──────────────────────────────────────

class TestFetchYoutubeChannel:
    @pytest.mark.asyncio
    async def test_no_params(self):
        api = ScrapeCreatorsAPI(api_key="test")
        result = await api.fetch_youtube_channel()
        assert result["success"] is False
        assert "Provide" in result["error"]

    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "channelId": "UCxxx",
            "name": "Test Channel",
            "subscriberCount": 100000,
            "viewCount": 5000000,
            "videoCount": 500,
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_youtube_channel(channel_id="UCxxx")
        assert result["success"] is True
        assert result["subscribers"] == 100000

    @pytest.mark.asyncio
    async def test_success_with_handle(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {"success": True, "channelId": "UCyyy", "name": "Handle Channel", "subscriberCount": 5000}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_youtube_channel(handle="@TestHandle")
        assert result["success"] is True
        assert result["channel_id"] == "UCyyy"

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.fetch_youtube_channel(channel_id="UCxxx")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_parse_error(self):
        api = ScrapeCreatorsAPI(api_key="test")

        class FailingDict(dict):
            """Dict that raises on the second .get() call."""
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self._call_count = 0
            def get(self, key, default=None):
                self._call_count += 1
                if self._call_count > 1:
                    raise TypeError("simulated parse error")
                return super().get(key, default)

        resp = FailingDict({"success": True, "channelId": "UCxxx"})
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=resp):
            result = await api.fetch_youtube_channel(channel_id="UCxxx")
        assert result["success"] is False
        assert "Parse error" in result["error"]


# ─── fetch_youtube_videos ─────────────────────────────────────

class TestFetchYoutubeVideos:
    @pytest.mark.asyncio
    async def test_no_params(self):
        api = ScrapeCreatorsAPI(api_key="test")
        result = await api.fetch_youtube_videos()
        assert result["success"] is False
        assert "Provide" in result["error"]

    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "videos": [
                {"id": "vid1", "title": "Test", "viewCountInt": 5000, "likeCountInt": 100},
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_youtube_videos(handle="TestChannel")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["videos"][0]["video_id"] == "vid1"

    @pytest.mark.asyncio
    async def test_success_with_channel_id(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "videos": [{"id": "vid2", "title": "T", "viewCountInt": 100}],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_youtube_videos(channel_id="UCxxx")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fallback_to_channel(self):
        api = ScrapeCreatorsAPI(api_key="test")
        # First call (channel-videos) returns success but no items
        videos_resp = {"success": True}
        # Second call (channel fallback) returns latestVideos
        channel_resp = {
            "success": True,
            "latestVideos": [
                {"id": "fb1", "title": "Fallback", "viewCountInt": 200},
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, side_effect=[videos_resp, channel_resp]):
            result = await api.fetch_youtube_videos(handle="Test")
        assert result["success"] is True
        assert result["videos"][0]["video_id"] == "fb1"

    @pytest.mark.asyncio
    async def test_both_empty_returns_empty(self):
        api = ScrapeCreatorsAPI(api_key="test")
        empty = {"success": True}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=empty):
            result = await api.fetch_youtube_videos(handle="Test")
        assert result["success"] is True
        assert result["videos"] == []

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        fail = {"success": False, "error": "err"}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=fail):
            result = await api.fetch_youtube_videos(handle="Test")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_parse_error_primary(self):
        """Parse error on primary endpoint falls back to channel."""
        api = ScrapeCreatorsAPI(api_key="test")
        bad_items = {"success": True, "videos": [None]}  # None causes AttributeError
        fallback_empty = {"success": True}
        with patch.object(api, "_get", new_callable=AsyncMock, side_effect=[bad_items, fallback_empty]):
            result = await api.fetch_youtube_videos(handle="Test")
        assert result["success"] is True
        assert result["videos"] == []

    @pytest.mark.asyncio
    async def test_parse_error_fallback(self):
        """Parse error on fallback endpoint returns empty."""
        api = ScrapeCreatorsAPI(api_key="test")
        primary_empty = {"success": True}
        bad_fallback = {"success": True, "latestVideos": [None]}
        with patch.object(api, "_get", new_callable=AsyncMock, side_effect=[primary_empty, bad_fallback]):
            result = await api.fetch_youtube_videos(handle="Test")
        assert result["success"] is True
        assert result["videos"] == []


# ─── fetch_snapchat_profile ─────────────────────────────────────

class TestFetchSnapchatProfile:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "userProfile": {"subscriberCount": 25000, "title": "Test Snap"},
            "curatedHighlights": [{"id": "1"}, {"id": "2"}],
            "spotlightHighlights": [
                {"viewCount": 1000, "shareCount": 50, "commentCount": 10, "snapList": []},
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_snapchat_profile("testsnap")
        assert result["success"] is True
        assert result["subscribers"] == 25000
        assert result["story_count"] == 2
        assert result["spotlight_count"] == 1
        assert result["engagement_rate"] > 0

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.fetch_snapchat_profile("unknown")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_snap_list_fallback_views(self):
        """When viewCount is 0, snap_list length is used as fallback."""
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "userProfile": {"subscriberCount": 1000, "title": "Test"},
            "curatedHighlights": [],
            "spotlightHighlights": [
                {"viewCount": 0, "shareCount": 0, "commentCount": 0, "snapList": [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}]},
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_snapchat_profile("test")
        assert result["success"] is True
        assert result["total_views"] == 3  # 3 snaps in list

    @pytest.mark.asyncio
    async def test_parse_error(self):
        api = ScrapeCreatorsAPI(api_key="test")
        # Force TypeError by making subscriberCount trigger int() on a non-convertible
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={
            "success": True,
            "userProfile": MagicMock(get=MagicMock(side_effect=TypeError("bad"))),
            "curatedHighlights": [],
            "spotlightHighlights": [],
        }):
            result = await api.fetch_snapchat_profile("bad")
        assert result["success"] is False
        assert "Parse error" in result["error"]


# ─── fetch_facebook_profile ─────────────────────────────────────

class TestFetchFacebookProfile:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "pageId": "12345",
            "name": "Test Page",
            "followerCount": 500000,
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_facebook_profile("https://facebook.com/test")
        assert result["success"] is True
        assert result["page_id"] == "12345"

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.fetch_facebook_profile("https://facebook.com/bad")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_parse_error(self):
        api = ScrapeCreatorsAPI(api_key="test")

        class FailingDict(dict):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self._call_count = 0
            def get(self, key, default=None):
                self._call_count += 1
                if self._call_count > 1:
                    raise Exception("simulated parse error")
                return super().get(key, default)

        resp = FailingDict({"success": True, "pageId": "123"})
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=resp):
            result = await api.fetch_facebook_profile("https://facebook.com/bad")
        assert result["success"] is False


# ─── get_facebook_ad_detail ────────────────────────────────────

class TestGetFacebookAdDetail:
    @pytest.mark.asyncio
    async def test_success_with_eu_data(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "adArchiveID": "123456",
            "byline": "Test Advertiser",
            "eu_transparency": {
                "age_audience": {"min": 18, "max": 65},
                "gender_audience": "all",
                "location_audience": ["France", "Germany"],
                "eu_total_reach": 50000,
                "age_country_gender_reach_breakdown": [{"country": "FR"}],
                "targets_eu": True,
            },
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.get_facebook_ad_detail("123456")
        assert result["success"] is True
        assert result["ad_archive_id"] == "123456"
        assert result["byline"] == "Test Advertiser"
        assert result["age_min"] == 18
        assert result["age_max"] == 65
        assert result["gender_audience"] == "all"
        assert result["eu_total_reach"] == 50000
        assert result["targets_eu"] is True

    @pytest.mark.asyncio
    async def test_byline_fallback_to_fev_info(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "adArchiveID": "789",
            "fevInfo": {"payer_name": "Payer Corp"},
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.get_facebook_ad_detail("789")
        assert result["success"] is True
        assert result["byline"] == "Payer Corp"

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.get_facebook_ad_detail("bad")
        assert result["success"] is False


# ─── get_facebook_ad_detail_raw ────────────────────────────────

class TestGetFacebookAdDetailRaw:
    @pytest.mark.asyncio
    async def test_returns_raw(self):
        api = ScrapeCreatorsAPI(api_key="test")
        raw = {"success": True, "raw_data": "value"}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=raw):
            result = await api.get_facebook_ad_detail_raw("123")
        assert result == raw


# ─── search_facebook_companies ──────────────────────────────────

class TestSearchFacebookCompanies:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "searchResults": [{"pageId": "1", "name": "Test"}],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.search_facebook_companies("Test")
        assert result["success"] is True
        assert len(result["companies"]) == 1

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.search_facebook_companies("Bad")
        assert result["success"] is False


# ─── fetch_facebook_company_ads ────────────────────────────────

class TestFetchFacebookCompanyAds:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "results": [{"adArchiveID": "a1"}, {"adArchiveID": "a2"}],
            "cursor": "next_page",
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_facebook_company_ads("page123")
        assert result["success"] is True
        assert result["count"] == 2
        assert result["cursor"] == "next_page"

    @pytest.mark.asyncio
    async def test_with_country_and_cursor(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {"success": True, "results": [{"adArchiveID": "a1"}]}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response) as mock_get:
            result = await api.fetch_facebook_company_ads("page123", country="FR", cursor="abc")
        assert result["success"] is True
        call_params = mock_get.call_args[0][1]
        assert call_params["country"] == "FR"
        assert call_params["cursor"] == "abc"

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.fetch_facebook_company_ads("bad")
        assert result["success"] is False


# ─── search_facebook_ads ──────────────────────────────────────

class TestSearchFacebookAds:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "searchResults": [{"adArchiveID": "ad1"}],
            "searchResultsCount": 100,
            "cursor": "next",
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.search_facebook_ads("TestCo")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["total_available"] == 100
        assert result["cursor"] == "next"

    @pytest.mark.asyncio
    async def test_with_cursor(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {"success": True, "searchResults": []}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response) as mock_get:
            await api.search_facebook_ads("TestCo", cursor="xyz")
        call_params = mock_get.call_args[0][1]
        assert call_params["cursor"] == "xyz"

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.search_facebook_ads("Bad")
        assert result["success"] is False


# ─── search_google_ads ────────────────────────────────────────

class TestSearchGoogleAds:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "ads": [{"id": "g1", "format": "text"}],
            "cursor": "gn",
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.search_google_ads("example.com")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["cursor"] == "gn"

    @pytest.mark.asyncio
    async def test_with_cursor(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {"success": True, "ads": []}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response) as mock_get:
            await api.search_google_ads("example.com", cursor="c1")
        call_params = mock_get.call_args[0][1]
        assert call_params["cursor"] == "c1"

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.search_google_ads("bad.com")
        assert result["success"] is False


# ─── search_google ────────────────────────────────────────────

class TestSearchGoogle:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "results": [{"title": "Test", "url": "https://example.com"}],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.search_google("test query")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["results"][0]["title"] == "Test"

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.search_google("bad")
        assert result["success"] is False


# ─── search_tiktok_ads (additional) ──────────────────────────

class TestSearchTiktokAdsExtra:
    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.search_tiktok_ads("bad")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_parse_error(self):
        api = ScrapeCreatorsAPI(api_key="test")
        # search_item_list contains non-dict items to trigger exception
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={
            "success": True, "search_item_list": [None],
        }):
            result = await api.search_tiktok_ads("bad")
        assert result["success"] is False


# ─── get_credits ──────────────────────────────────────────────

class TestGetCredits:
    @pytest.mark.asyncio
    async def test_returns_credits(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": True, "credits_remaining": 42}):
            result = await api.get_credits()
        assert result == 42

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.get_credits()
        assert result is None


# ─── Comments endpoints ─────────────────────────────────────────

class TestYoutubeComments:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "comments": [
                {"commentId": "c1", "authorText": "User1", "textDisplay": "Great!", "likeCount": 5, "replyCount": 1},
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_youtube_comments("video123")
        assert result["success"] is True
        assert result["comments"][0]["comment_id"] == "c1"
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "Not found"}):
            result = await api.fetch_youtube_comments("invalid")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_parse_error(self):
        api = ScrapeCreatorsAPI(api_key="test")
        # comments contains non-dict to trigger exception
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": True, "comments": [None]}):
            result = await api.fetch_youtube_comments("bad")
        assert result["success"] is False


class TestTiktokComments:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "comments": [
                {"cid": "c1", "user": {"nickname": "User1"}, "text": "Nice!", "digg_count": 10, "reply_comment_total": 2},
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_tiktok_comments("video123")
        assert result["success"] is True
        assert result["comments"][0]["author"] == "User1"

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.fetch_tiktok_comments("bad")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_parse_error(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": True, "comments": [None]}):
            result = await api.fetch_tiktok_comments("bad")
        assert result["success"] is False


class TestInstagramComments:
    @pytest.mark.asyncio
    async def test_success(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "comments": [
                {"node": {"id": "c1", "owner": {"username": "user1"}, "text": "Love it!", "edge_liked_by": {"count": 3}}},
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.fetch_instagram_comments("ABC123")
        assert result["success"] is True
        assert result["comments"][0]["author"] == "user1"

    @pytest.mark.asyncio
    async def test_failure(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": False, "error": "err"}):
            result = await api.fetch_instagram_comments("bad")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_parse_error(self):
        api = ScrapeCreatorsAPI(api_key="test")
        with patch.object(api, "_get", new_callable=AsyncMock, return_value={"success": True, "comments": [None]}):
            result = await api.fetch_instagram_comments("bad")
        assert result["success"] is False


# ─── search_tiktok_ads ──────────────────────────────────────────

class TestSearchTiktokAds:
    @pytest.mark.asyncio
    async def test_finds_ads(self):
        api = ScrapeCreatorsAPI(api_key="test")
        api_response = {
            "success": True,
            "search_item_list": [
                {
                    "aweme_info": {
                        "aweme_id": "ad1",
                        "is_ads": True,
                        "commerce_info": {},
                        "author": {"uid": "u1", "uniqueId": "brand"},
                        "statistics": {"play_count": 10000, "digg_count": 500},
                        "video": {"duration": 15, "origin_cover": {"url_list": ["http://cover.jpg"]}},
                        "desc": "Ad content",
                        "text_extra": [{"hashtag_name": "ad"}],
                        "create_time": 1700000000,
                    },
                },
                {
                    "aweme_info": {
                        "aweme_id": "org1",
                        "is_ads": False,
                        "commerce_info": {},
                        "author": {},
                        "statistics": {},
                        "video": {},
                        "desc": "Organic",
                        "text_extra": [],
                    },
                },
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=api_response):
            result = await api.search_tiktok_ads("brand")
        assert result["success"] is True
        assert result["ads_count"] == 1
        assert result["total_results"] == 2


# ─── Cache ────────────────────────────────────────────────────────

def _make_mock_client(mock_response):
    """Helper: create a patched httpx.AsyncClient that returns mock_response."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


def _make_mock_response(data: dict):
    """Helper: create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


class TestCache:
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Two identical calls → only 1 HTTP request."""
        api = ScrapeCreatorsAPI(api_key="test")
        mock_response = _make_mock_response({"data": "value"})

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = _make_mock_client(mock_response)
            mock_cls.return_value = mock_client

            result1 = await api._get("/v1/test/profile", {"handle": "foo"})
            result2 = await api._get("/v1/test/profile", {"handle": "foo"})

        assert result1["success"] is True
        assert result2["success"] is True
        assert result1["data"] == "value"
        # HTTP client.get should have been called exactly once
        assert mock_client.get.call_count == 1
        assert api.cache_stats["hits"] == 1
        assert api.cache_stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_cache_miss_after_ttl(self):
        """After TTL expires, a new HTTP call is made."""
        api = ScrapeCreatorsAPI(api_key="test")
        mock_response = _make_mock_response({"data": "value"})

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = _make_mock_client(mock_response)
            mock_cls.return_value = mock_client

            await api._get("/v1/test/profile", {"handle": "foo"})

            # Expire the cache entry by backdating the timestamp
            for key in api._cache:
                data, ts = api._cache[key]
                api._cache[key] = (data, ts - 100_000)  # shift 100k seconds back

            await api._get("/v1/test/profile", {"handle": "foo"})

        assert mock_client.get.call_count == 2
        assert api.cache_stats["misses"] == 2

    @pytest.mark.asyncio
    async def test_error_not_cached(self):
        """Error responses (success: False) should NOT be cached."""
        api = ScrapeCreatorsAPI(api_key="test")
        error_response = _make_mock_response({"success": False, "message": "Bad request"})
        ok_response = _make_mock_response({"data": "ok"})

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            # First call returns error, second returns success
            mock_client.get = AsyncMock(side_effect=[error_response, ok_response])
            mock_cls.return_value = mock_client

            result1 = await api._get("/v1/test", {"q": "bad"})
            result2 = await api._get("/v1/test", {"q": "bad"})

        assert result1["success"] is False
        assert result2["success"] is True
        assert mock_client.get.call_count == 2
        assert api.cache_stats["size"] == 1  # only the success is cached

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """After clear_cache(), same call triggers new HTTP request."""
        api = ScrapeCreatorsAPI(api_key="test")
        mock_response = _make_mock_response({"data": "value"})

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = _make_mock_client(mock_response)
            mock_cls.return_value = mock_client

            await api._get("/v1/test/profile", {"handle": "foo"})
            assert api.cache_stats["size"] == 1

            api.clear_cache()
            assert api.cache_stats["size"] == 0
            assert api.cache_stats["hits"] == 0

            await api._get("/v1/test/profile", {"handle": "foo"})

        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Verify hits/misses are tracked correctly."""
        api = ScrapeCreatorsAPI(api_key="test")
        mock_response = _make_mock_response({"data": "v"})

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = _make_mock_client(mock_response)
            mock_cls.return_value = mock_client

            await api._get("/v1/x", {"a": "1"})  # miss
            await api._get("/v1/x", {"a": "1"})  # hit
            await api._get("/v1/x", {"a": "1"})  # hit
            await api._get("/v1/y", {"b": "2"})  # miss

        stats = api.cache_stats
        assert stats["misses"] == 2
        assert stats["hits"] == 2
        assert stats["size"] == 2

    @pytest.mark.asyncio
    async def test_different_params_different_cache(self):
        """Different params for same path → separate cache entries."""
        api = ScrapeCreatorsAPI(api_key="test")
        resp_a = _make_mock_response({"data": "a"})
        resp_b = _make_mock_response({"data": "b"})

        with patch("services.scrapecreators.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=[resp_a, resp_b])
            mock_cls.return_value = mock_client

            result_a = await api._get("/v1/test/profile", {"handle": "alice"})
            result_b = await api._get("/v1/test/profile", {"handle": "bob"})

        assert result_a["data"] == "a"
        assert result_b["data"] == "b"
        assert mock_client.get.call_count == 2
        assert api.cache_stats["size"] == 2
        assert api.cache_stats["misses"] == 2
        assert api.cache_stats["hits"] == 0


class TestGetTTL:
    def setup_method(self):
        self.api = ScrapeCreatorsAPI(api_key="test")

    def test_profile_ttl(self):
        assert self.api._get_ttl("/v1/instagram/profile") == 6 * 3600
        assert self.api._get_ttl("/v1/tiktok/profile") == 6 * 3600

    def test_channel_ttl(self):
        assert self.api._get_ttl("/v1/youtube/channel") == 6 * 3600

    def test_videos_ttl(self):
        assert self.api._get_ttl("/v1/tiktok/profile/videos") == 2 * 3600
        assert self.api._get_ttl("/v1/youtube/channel-videos") == 2 * 3600

    def test_comments_ttl(self):
        assert self.api._get_ttl("/v1/youtube/video/comments") == 3600

    def test_adlibrary_ttl(self):
        assert self.api._get_ttl("/v1/facebook/adLibrary/search/ads") == 3600

    def test_google_ttl(self):
        assert self.api._get_ttl("/v1/google/company/ads") == 3600

    def test_search_ttl(self):
        assert self.api._get_ttl("/v1/tiktok/search/keyword") == 1800

    def test_default_ttl(self):
        assert self.api._get_ttl("/v1/unknown/endpoint") == 3600


# ─── Singleton ───────────────────────────────────────────────────

class TestSingleton:
    def test_singleton_exists(self):
        from services.scrapecreators import scrapecreators
        assert scrapecreators is not None
