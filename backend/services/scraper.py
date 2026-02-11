"""
Generic scraping utilities and helpers
"""
import httpx
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any
import asyncio
from datetime import datetime
import re


class RateLimiter:
    """Simple rate limiter for scraping operations"""

    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self.last_request = 0

    async def wait(self):
        """Wait if necessary to respect rate limit"""
        now = datetime.now().timestamp()
        elapsed = now - self.last_request
        if elapsed < self.interval:
            await asyncio.sleep(self.interval - elapsed)
        self.last_request = datetime.now().timestamp()


class Scraper:
    """Base scraper class with common functionality"""

    def __init__(self, rate_limit: int = 30):
        self.rate_limiter = RateLimiter(rate_limit)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    async def fetch_page(self, url: str, params: Optional[Dict] = None) -> Optional[str]:
        """Fetch a web page with rate limiting"""
        await self.rate_limiter.wait()

        try:
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
                response = await client.get(url, params=params, timeout=30.0)
                if response.status_code == 200:
                    return response.text
                return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    async def fetch_json(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Fetch JSON from an API endpoint"""
        await self.rate_limiter.wait()

        try:
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
                response = await client.get(url, params=params, timeout=30.0)
                if response.status_code == 200:
                    return response.json()
                return None
        except Exception as e:
            print(f"Error fetching JSON from {url}: {e}")
            return None

    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content"""
        return BeautifulSoup(html, "lxml")

    @staticmethod
    def extract_number(text: str) -> Optional[int]:
        """Extract a number from text like '1.2M', '10K', '1,234'"""
        if not text:
            return None

        text = text.strip().upper().replace(",", "").replace(" ", "")

        multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}

        for suffix, multiplier in multipliers.items():
            if suffix in text:
                try:
                    number = float(text.replace(suffix, "").replace("+", ""))
                    return int(number * multiplier)
                except ValueError:
                    pass

        try:
            return int(re.sub(r"[^\d]", "", text))
        except ValueError:
            return None

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        # Remove extra whitespace
        text = " ".join(text.split())
        # Remove special characters that might cause issues
        text = text.replace("\x00", "")
        return text.strip()


class MetaAdsScraper(Scraper):
    """Scraper for Meta Ads Library (fallback when API not available)"""

    BASE_URL = "https://www.facebook.com/ads/library/"

    async def search_ads(self, page_name: str, country: str = "FR") -> list:
        """
        Search for ads by page name in the Ads Library.
        Note: This is a basic implementation. The official API is recommended.
        """
        # The ads library requires JavaScript rendering, so this is limited
        # In production, use the official Meta Ads Library API
        params = {
            "active_status": "all",
            "ad_type": "all",
            "country": country,
            "q": page_name,
        }

        html = await self.fetch_page(self.BASE_URL, params)
        if not html:
            return []

        # Parse would go here, but Facebook's ads library requires JS
        # This is why the API is strongly recommended
        return []


class InstagramScraper(Scraper):
    """
    Basic Instagram profile scraper.
    Note: For production use, instaloader library is recommended.
    """

    BASE_URL = "https://www.instagram.com"

    async def get_profile_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get basic profile info from Instagram.
        Note: Instagram aggressively blocks scrapers.
        Use the instaloader library for better results.
        """
        url = f"{self.BASE_URL}/{username}/"
        html = await self.fetch_page(url)

        if not html:
            return None

        soup = self.parse_html(html)

        # Try to extract data from JSON in page
        # Instagram embeds profile data in a script tag
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                import json
                data = json.loads(script.string)
                if data.get("@type") == "ProfilePage":
                    return {
                        "username": username,
                        "name": data.get("name"),
                        "description": data.get("description"),
                    }
            except:
                pass

        return None


# Singleton instances for reuse
meta_scraper = MetaAdsScraper(rate_limit=20)
instagram_scraper = InstagramScraper(rate_limit=10)
