"""Tests for services/scrapecreators.py — ScrapeCreators API client."""
import os
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


# ─── Singleton ───────────────────────────────────────────────────

class TestSingleton:
    def test_singleton_exists(self):
        from services.scrapecreators import scrapecreators
        assert scrapecreators is not None
