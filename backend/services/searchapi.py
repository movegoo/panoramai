"""
SearchAPI.io service — complementary enrichment for Meta Ad Library.
Used ONLY for payer/beneficiary data that ScrapeCreators doesn't return.
"""
import asyncio
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

SEARCHAPI_BASE = "https://www.searchapi.io/api/v1/search"


class SearchAPIService:
    """Thin wrapper around SearchAPI.io meta_ad_library_ad_details."""

    def __init__(self):
        self.api_key = os.getenv("SEARCHAPI_KEY", "")
        self._last_request_at = 0.0  # rate-limit: 1 req/sec

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def _rate_limit(self):
        """Enforce minimum 1 second between requests."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        self._last_request_at = time.monotonic()

    async def get_ad_details(self, ad_archive_id: str) -> dict:
        """
        Fetch a single Meta ad's details via SearchAPI.io.
        Returns payer_beneficiary_data, eu_total_reach, aaa_info if available.
        """
        if not self.is_configured:
            return {"success": False, "error": "SEARCHAPI_KEY not configured"}

        await self._rate_limit()

        params = {
            "engine": "meta_ad_library_ad_details",
            "ad_archive_id": ad_archive_id,
            "api_key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(SEARCHAPI_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()

            # Extract payer/beneficiary
            pb_data = data.get("payer_beneficiary_data") or {}
            payer = pb_data.get("payer") or None
            beneficiary = pb_data.get("beneficiary") or None

            # Extract eu_total_reach as fallback
            eu_total_reach = data.get("eu_total_reach")

            # Extract aaa_info (age/gender/location audience)
            aaa_info = data.get("aaa_info") or {}

            return {
                "success": True,
                "payer": payer,
                "beneficiary": beneficiary,
                "eu_total_reach": eu_total_reach,
                "aaa_info": aaa_info,
                "raw": data,
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"SearchAPI HTTP error for ad {ad_archive_id}: {e.response.status_code}")
            return {"success": False, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            logger.error(f"SearchAPI error for ad {ad_archive_id}: {e}")
            return {"success": False, "error": str(e)}


    # ─── Google Trends ────────────────────────────────────────────────

    async def fetch_google_trends(
        self, keywords: list[str], geo: str = "FR", timeframe: str = "today 3-m"
    ) -> dict:
        """
        Compare search interest for multiple keywords via Google Trends.
        Returns timeline_data with date + value per keyword.
        """
        if not self.is_configured:
            return {"success": False, "error": "SEARCHAPI_KEY not configured"}

        await self._rate_limit()

        params = {
            "engine": "google_trends",
            "q": ",".join(keywords),
            "geo": geo,
            "data_type": "TIMESERIES",
            "date": timeframe,
            "api_key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(SEARCHAPI_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()

            timeline_data = []
            for point in data.get("interest_over_time", {}).get("timeline_data", []):
                date_str = point.get("date", "")
                values = {}
                for val in point.get("values", []):
                    query = val.get("query", "")
                    extracted = val.get("extracted_value", 0)
                    values[query] = extracted
                timeline_data.append({"date": date_str, "values": values})

            return {"success": True, "timeline_data": timeline_data}
        except httpx.HTTPStatusError as e:
            logger.error(f"SearchAPI Trends HTTP error: {e.response.status_code}")
            return {"success": False, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            logger.error(f"SearchAPI Trends error: {e}")
            return {"success": False, "error": str(e)}

    async def fetch_google_trends_related(
        self, keyword: str, geo: str = "FR"
    ) -> dict:
        """
        Fetch related queries (rising + top) for a single keyword.
        """
        if not self.is_configured:
            return {"success": False, "error": "SEARCHAPI_KEY not configured"}

        await self._rate_limit()

        params = {
            "engine": "google_trends",
            "q": keyword,
            "geo": geo,
            "data_type": "RELATED_QUERIES",
            "api_key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(SEARCHAPI_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()

            related = data.get("related_queries", {})
            rising = [
                {"query": q.get("query", ""), "value": q.get("extracted_value", 0)}
                for q in related.get("rising", [])
            ]
            top = [
                {"query": q.get("query", ""), "value": q.get("extracted_value", 0)}
                for q in related.get("top", [])
            ]

            return {"success": True, "rising": rising, "top": top}
        except httpx.HTTPStatusError as e:
            logger.error(f"SearchAPI Trends Related HTTP error: {e.response.status_code}")
            return {"success": False, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            logger.error(f"SearchAPI Trends Related error: {e}")
            return {"success": False, "error": str(e)}

    # ─── Google News ──────────────────────────────────────────────────

    async def fetch_google_news(
        self, query: str, gl: str = "fr", hl: str = "fr"
    ) -> dict:
        """
        Fetch latest news articles for a query via Google News.
        """
        if not self.is_configured:
            return {"success": False, "error": "SEARCHAPI_KEY not configured"}

        await self._rate_limit()

        params = {
            "engine": "google_news",
            "q": query,
            "gl": gl,
            "hl": hl,
            "api_key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(SEARCHAPI_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()

            articles = []
            for item in data.get("news_results", []):
                articles.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "source": item.get("source", {}).get("name", ""),
                    "date": item.get("date", ""),
                    "snippet": item.get("snippet", ""),
                    "thumbnail": item.get("thumbnail", ""),
                })

            return {"success": True, "articles": articles}
        except httpx.HTTPStatusError as e:
            logger.error(f"SearchAPI News HTTP error: {e.response.status_code}")
            return {"success": False, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            logger.error(f"SearchAPI News error: {e}")
            return {"success": False, "error": str(e)}


searchapi = SearchAPIService()
