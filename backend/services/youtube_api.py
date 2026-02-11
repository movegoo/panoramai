"""
YouTube data service.
Uses ScrapeCreators API for channel and video metrics.
"""
import logging
from typing import Dict, Optional
from services.scrapecreators import scrapecreators

logger = logging.getLogger(__name__)


class YouTubeAPI:
    """Service for fetching YouTube data via ScrapeCreators."""

    async def fetch_channel(self, channel_id: str) -> Dict:
        """Fetch YouTube channel data by channel ID."""
        return await scrapecreators.fetch_youtube_channel(channel_id=channel_id)

    async def fetch_channel_by_username(self, username: str) -> Dict:
        """Fetch YouTube channel by handle."""
        return await scrapecreators.fetch_youtube_channel(handle=username)

    async def fetch_recent_videos(self, channel_id: str, max_results: int = 10) -> Dict:
        """Fetch recent videos from a YouTube channel."""
        return await scrapecreators.fetch_youtube_videos(
            channel_id=channel_id, limit=max_results
        )

    async def search_channels(self, query: str, max_results: int = 10) -> Dict:
        """Search for YouTube channels (not supported via ScrapeCreators, returns empty)."""
        return {
            "success": True,
            "query": query,
            "results": [],
            "count": 0,
            "message": "Search not available via ScrapeCreators"
        }

    async def get_channel_analytics(self, channel_id: str) -> Dict:
        """
        Calculate analytics for a YouTube channel.
        Fetches channel data and recent videos for engagement metrics.
        """
        channel_data = await self.fetch_channel(channel_id)
        if not channel_data.get("success"):
            return channel_data

        # Fetch recent videos for analytics
        videos_data = await self.fetch_recent_videos(channel_id, max_results=20)
        videos = videos_data.get("videos", []) if videos_data.get("success") else []

        if not videos:
            return {
                **channel_data,
                "analytics": {
                    "avg_views": 0,
                    "avg_likes": 0,
                    "avg_comments": 0,
                    "engagement_rate": 0,
                    "videos_analyzed": 0
                }
            }

        total_views = sum(v.get("views", 0) for v in videos)
        total_likes = sum(v.get("likes", 0) for v in videos)
        total_comments = sum(v.get("comments", 0) for v in videos)

        count = len(videos)
        avg_views = total_views / count
        avg_likes = total_likes / count
        avg_comments = total_comments / count

        engagement_rate = 0
        if total_views > 0:
            engagement_rate = ((total_likes + total_comments) / total_views) * 100

        return {
            **channel_data,
            "analytics": {
                "avg_views": round(avg_views),
                "avg_likes": round(avg_likes),
                "avg_comments": round(avg_comments),
                "engagement_rate": round(engagement_rate, 2),
                "videos_analyzed": count,
                "total_views_recent": total_views
            }
        }


# Singleton instance
youtube_api = YouTubeAPI()
