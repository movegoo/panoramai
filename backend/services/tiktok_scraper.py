"""
TikTok scraping service.
Uses ScrapeCreators API for reliable data extraction.
"""
import logging
from typing import Dict
from services.scrapecreators import scrapecreators

logger = logging.getLogger(__name__)


class TikTokScraper:
    """Scraper for TikTok profile data via ScrapeCreators."""

    async def fetch_profile(self, username: str) -> Dict:
        """Fetch TikTok profile data for a username."""
        return await scrapecreators.fetch_tiktok_profile(username)

    async def fetch_recent_videos(self, username: str, limit: int = 10) -> Dict:
        """Fetch recent videos for a TikTok user."""
        return await scrapecreators.fetch_tiktok_videos(username, limit)


# Singleton instance
tiktok_scraper = TikTokScraper()
