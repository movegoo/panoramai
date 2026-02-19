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


searchapi = SearchAPIService()
