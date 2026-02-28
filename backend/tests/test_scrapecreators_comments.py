"""Tests for ScrapeCreators comment fetching methods."""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.scrapecreators import ScrapeCreatorsAPI


@pytest.fixture
def api():
    return ScrapeCreatorsAPI(api_key="test-key")


class TestFetchYouTubeComments:
    @pytest.mark.asyncio
    async def test_success(self, api):
        """Successful YouTube comment fetch."""
        mock_response = {
            "success": True,
            "comments": [
                {
                    "commentId": "abc123",
                    "authorText": "User1",
                    "textDisplay": "Great video!",
                    "likeCount": 5,
                    "replyCount": 1,
                    "publishedTimeText": "2 days ago",
                },
                {
                    "commentId": "def456",
                    "authorText": "User2",
                    "textDisplay": "Very helpful",
                    "likeCount": 2,
                    "replyCount": 0,
                    "publishedTimeText": "1 day ago",
                },
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await api.fetch_youtube_comments("video123", limit=50)
            assert result["success"] is True
            assert result["count"] == 2
            assert result["comments"][0]["comment_id"] == "abc123"
            assert result["comments"][0]["author"] == "User1"
            assert result["comments"][0]["text"] == "Great video!"
            assert result["comments"][0]["likes"] == 5

    @pytest.mark.asyncio
    async def test_error(self, api):
        """YouTube comments API error."""
        mock_response = {"success": False, "error": "Video not found"}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await api.fetch_youtube_comments("invalid_id")
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_empty_comments(self, api):
        """YouTube video with no comments."""
        mock_response = {"success": True, "comments": []}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await api.fetch_youtube_comments("video_no_comments")
            assert result["success"] is True
            assert result["count"] == 0
            assert result["comments"] == []


class TestFetchTikTokComments:
    @pytest.mark.asyncio
    async def test_success(self, api):
        """Successful TikTok comment fetch."""
        mock_response = {
            "success": True,
            "comments": [
                {
                    "cid": "tt_001",
                    "user": {"nickname": "TikToker", "unique_id": "tiktoker1"},
                    "text": "Love this!",
                    "digg_count": 10,
                    "reply_comment_total": 3,
                    "create_time": "1700000000",
                },
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await api.fetch_tiktok_comments("video789", limit=50)
            assert result["success"] is True
            assert result["count"] == 1
            assert result["comments"][0]["comment_id"] == "tt_001"
            assert result["comments"][0]["author"] == "TikToker"
            assert result["comments"][0]["likes"] == 10

    @pytest.mark.asyncio
    async def test_error(self, api):
        """TikTok comments API error."""
        mock_response = {"success": False, "error": "Rate limited"}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await api.fetch_tiktok_comments("invalid")
            assert result["success"] is False


class TestFetchInstagramComments:
    @pytest.mark.asyncio
    async def test_success(self, api):
        """Successful Instagram comment fetch."""
        mock_response = {
            "success": True,
            "comments": [
                {
                    "id": "ig_001",
                    "owner": {"username": "user1"},
                    "text": "Beautiful post!",
                    "edge_liked_by": {"count": 7},
                    "edge_threaded_comments": {"count": 2},
                    "created_at": "2024-01-15T10:00:00Z",
                },
                {
                    "id": "ig_002",
                    "owner": {"username": "user2"},
                    "text": "Where can I buy this?",
                    "edge_liked_by": {"count": 1},
                    "edge_threaded_comments": {"count": 0},
                },
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await api.fetch_instagram_comments("ABC123", limit=50)
            assert result["success"] is True
            assert result["count"] == 2
            assert result["comments"][0]["comment_id"] == "ig_001"
            assert result["comments"][0]["author"] == "user1"
            assert result["comments"][0]["likes"] == 7
            assert result["comments"][1]["text"] == "Where can I buy this?"

    @pytest.mark.asyncio
    async def test_error(self, api):
        """Instagram comments API error."""
        mock_response = {"success": False, "error": "Post not found"}
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await api.fetch_instagram_comments("invalid_shortcode")
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_nested_node_format(self, api):
        """Instagram comments in nested node format (edges)."""
        mock_response = {
            "success": True,
            "comments": [
                {
                    "node": {
                        "id": "ig_nested",
                        "owner": {"username": "nested_user"},
                        "text": "Nested comment",
                        "edge_liked_by": {"count": 3},
                        "edge_threaded_comments": {"count": 1},
                    }
                },
            ],
        }
        with patch.object(api, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await api.fetch_instagram_comments("POST123")
            assert result["success"] is True
            assert result["count"] == 1
            assert result["comments"][0]["comment_id"] == "ig_nested"
            assert result["comments"][0]["author"] == "nested_user"
