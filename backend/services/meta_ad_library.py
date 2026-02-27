"""
Meta Ad Library API service.
Uses the official Graph API for ad listing (free, fast, paginated)
with SearchAPI fallback for EU transparency payer data.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Fields available on the official Meta Ad Library API
AD_FIELDS = ",".join([
    "id",
    "ad_creation_time",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "page_id",
    "page_name",
    "bylines",
    "publisher_platforms",
    "ad_snapshot_url",
    "eu_total_reach",
    "target_ages",
    "target_gender",
    "target_locations",
    "languages",
    "estimated_audience_size",
    "impressions",
    "spend",
    "currency",
    "ad_creative_bodies",
    "ad_creative_link_titles",
    "ad_creative_link_captions",
    "ad_creative_link_descriptions",
    "beneficiary_payers",
])


class MetaAdLibraryService:
    """Official Meta Ad Library API + SearchAPI fallback for payer data."""

    @property
    def meta_token(self) -> str:
        return os.getenv("META_AD_LIBRARY_TOKEN", "") or settings.META_AD_LIBRARY_TOKEN

    @property
    def searchapi_key(self) -> str:
        return os.getenv("SEARCHAPI_KEY", "") or settings.SEARCHAPI_KEY

    @property
    def is_configured(self) -> bool:
        return bool(self.meta_token)

    async def search_page(self, query: str) -> list[dict]:
        """Search for a Facebook page by name. Returns list of {page_id, name, likes}."""
        if not self.is_configured:
            # Fallback to SearchAPI
            return await self._searchapi_page_search(query)

        url = f"{GRAPH_API_BASE}/ads_archive"
        params = {
            "access_token": self.meta_token,
            "search_terms": query,
            "ad_reached_countries": "FR",
            "ad_active_status": "ACTIVE",
            "fields": "page_id,page_name",
            "limit": 25,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            # Deduplicate pages
            pages = {}
            for ad in data.get("data", []):
                pid = ad.get("page_id")
                if pid and pid not in pages:
                    pages[pid] = {"page_id": pid, "name": ad.get("page_name", "")}
            return list(pages.values())
        except Exception as e:
            logger.error(f"Meta API page search error: {e}")
            return await self._searchapi_page_search(query)

    async def get_active_ads(
        self,
        page_id: str,
        country: str = "FR",
        limit: int = 0,
    ) -> list[dict]:
        """
        Get all active ads for a page via Meta API.
        limit=0 means fetch all (paginated).
        Returns list of ad dicts with reach, targeting, platforms.
        """
        if not self.is_configured:
            return await self._searchapi_ads(page_id, country)

        all_ads = []
        url = f"{GRAPH_API_BASE}/ads_archive"
        params = {
            "access_token": self.meta_token,
            "search_terms": "*",
            "ad_reached_countries": country,
            "ad_active_status": "ACTIVE",
            "search_page_ids": page_id,
            "fields": AD_FIELDS,
            "limit": 100,
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                # First page
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                all_ads.extend(data.get("data", []))

                # Paginate
                while True:
                    next_url = data.get("paging", {}).get("next")
                    if not next_url:
                        break
                    if limit and len(all_ads) >= limit:
                        all_ads = all_ads[:limit]
                        break
                    resp = await client.get(next_url)
                    resp.raise_for_status()
                    data = resp.json()
                    ads = data.get("data", [])
                    if not ads:
                        break
                    all_ads.extend(ads)

        except Exception as e:
            logger.error(f"Meta API ads error for page {page_id}: {e}")
            if not all_ads:
                return await self._searchapi_ads(page_id, country)

        return all_ads

    async def get_all_ads(
        self,
        page_id: str,
        country: str = "FR",
        active_only: bool = True,
        limit: int = 0,
    ) -> list[dict]:
        """
        Get ads for a page via Meta API.
        active_only=True returns only active ads, False returns all (active + inactive).
        """
        if active_only:
            return await self.get_active_ads(page_id, country, limit)

        if not self.is_configured:
            return await self._searchapi_ads(page_id, country)

        all_ads = []
        url = f"{GRAPH_API_BASE}/ads_archive"
        params = {
            "access_token": self.meta_token,
            "search_terms": "*",
            "ad_reached_countries": country,
            "ad_active_status": "ALL",
            "search_page_ids": page_id,
            "fields": AD_FIELDS,
            "limit": 100,
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                all_ads.extend(data.get("data", []))

                while True:
                    next_url = data.get("paging", {}).get("next")
                    if not next_url:
                        break
                    if limit and len(all_ads) >= limit:
                        all_ads = all_ads[:limit]
                        break
                    resp = await client.get(next_url)
                    resp.raise_for_status()
                    data = resp.json()
                    ads = data.get("data", [])
                    if not ads:
                        break
                    all_ads.extend(ads)

        except Exception as e:
            logger.error(f"Meta API all ads error for page {page_id}: {e}")
            if not all_ads:
                return await self._searchapi_ads(page_id, country)

        return all_ads

    async def enrich_ad_details(
        self,
        ad_id: str,
    ) -> dict | None:
        """
        Enrich a single ad with EU transparency data via SearchAPI ad_details.
        Returns dict with payer, beneficiary, eu_total_reach, age/gender data, or None on failure.
        """
        if not self.searchapi_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://www.searchapi.io/api/v1/search",
                    params={
                        "engine": "meta_ad_library_ad_details",
                        "ad_archive_id": ad_id,
                        "api_key": self.searchapi_key,
                    },
                )
                resp.raise_for_status()
                detail = resp.json()

            aaa = detail.get("aaa_info", {})
            pb_list = aaa.get("payer_beneficiary_data", [])
            eu_reach = aaa.get("eu_total_reach", 0) or 0

            payer = None
            beneficiary = None
            if pb_list:
                payer = pb_list[0].get("payer")
                beneficiary = pb_list[0].get("beneficiary")

            return {
                "eu_total_reach": eu_reach,
                "payer": payer,
                "beneficiary": beneficiary,
                "age_gender_data": aaa.get("age_country_gender_reach_breakdown", []),
                "location_data": aaa.get("location_audience", []),
            }
        except Exception as e:
            logger.warning(f"SearchAPI ad_details error for {ad_id}: {e}")
            return None

    async def enrich_payers(
        self,
        ads: list[dict],
        sample_size: int = 50,
    ) -> dict:
        """
        Enrich ads with payer info via SearchAPI ad_details (EU transparency).
        Samples `sample_size` ads, returns payer breakdown.
        Falls back gracefully if SearchAPI not configured.
        """
        if not self.searchapi_key:
            return {"error": "SEARCHAPI_KEY not configured", "payers": {}}

        import random
        import time

        sample = random.sample(ads, min(sample_size, len(ads)))
        payers = {}

        async with httpx.AsyncClient(timeout=30) as client:
            for i, ad in enumerate(sample):
                ad_id = ad.get("id")
                if not ad_id:
                    continue
                try:
                    resp = await client.get(
                        "https://www.searchapi.io/api/v1/search",
                        params={
                            "engine": "meta_ad_library_ad_details",
                            "ad_archive_id": ad_id,
                            "api_key": self.searchapi_key,
                        },
                    )
                    resp.raise_for_status()
                    detail = resp.json()
                    aaa = detail.get("aaa_info", {})
                    pb_list = aaa.get("payer_beneficiary_data", [])
                    reach = aaa.get("eu_total_reach", 0) or 0

                    if pb_list:
                        for pb in pb_list:
                            payer = pb.get("payer", "Non renseigné")
                            beneficiary = pb.get("beneficiary", "-")
                            payers.setdefault(payer, {"count": 0, "reach": 0, "beneficiary": beneficiary})
                            payers[payer]["count"] += 1
                            payers[payer]["reach"] += reach
                    else:
                        payers.setdefault("Non renseigné", {"count": 0, "reach": 0, "beneficiary": "-"})
                        payers["Non renseigné"]["count"] += 1
                        payers["Non renseigné"]["reach"] += reach
                except Exception as e:
                    logger.warning(f"SearchAPI ad_details error for {ad_id}: {e}")
                    continue

                # Rate limit: 1 req/sec
                await asyncio.sleep(1.1)

        total_sampled = sum(v["count"] for v in payers.values())

        result = []
        for payer_name, data in sorted(payers.items(), key=lambda x: -x[1]["count"]):
            pct = round(data["count"] / total_sampled * 100) if total_sampled else 0
            result.append({
                "payer": payer_name,
                "beneficiary": data["beneficiary"],
                "count": data["count"],
                "pct": pct,
                "reach": data["reach"],
            })

        return {
            "total_ads": len(ads),
            "sampled": total_sampled,
            "payers": result,
        }

    async def get_page_summary(self, page_id: str, country: str = "FR") -> dict:
        """
        Full summary for a page: ad count, reach, platforms, targeting, payers.
        """
        ads = await self.get_active_ads(page_id, country)

        total_reach = sum(ad.get("eu_total_reach", 0) or 0 for ad in ads)

        platforms = {}
        cities = {}
        for ad in ads:
            for p in ad.get("publisher_platforms", []):
                platforms[p] = platforms.get(p, 0) + 1
            for loc in ad.get("target_locations", []):
                city = loc.get("name", "?").split(",")[0]
                cities[city] = cities.get(city, 0) + 1

        top_cities = [
            {"city": k, "ads_count": v}
            for k, v in sorted(cities.items(), key=lambda x: -x[1])[:20]
        ]

        return {
            "page_id": page_id,
            "page_name": ads[0].get("page_name", "") if ads else "",
            "active_ads": len(ads),
            "eu_total_reach": total_reach,
            "platforms": platforms,
            "top_cities": top_cities,
        }

    # ── Token refresh ────────────────────────────────────────────────

    async def refresh_long_lived_token(self) -> dict:
        """
        Exchange the current long-lived token for a new one via Facebook's
        token exchange endpoint. Updates the environment variable and AWS SSM.

        Returns dict with 'success', 'expires_in', and optionally 'error'.
        """
        current_token = self.meta_token
        app_id = settings.META_APP_ID
        app_secret = settings.META_APP_SECRET

        if not current_token:
            logger.error("Meta token refresh: no current token available")
            return {"success": False, "error": "No current META_AD_LIBRARY_TOKEN"}
        if not app_id or not app_secret:
            logger.error("Meta token refresh: META_APP_ID or META_APP_SECRET not configured")
            return {"success": False, "error": "META_APP_ID or META_APP_SECRET missing"}

        url = f"{GRAPH_API_BASE}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": current_token,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            new_token = data.get("access_token")
            expires_in = data.get("expires_in", 0)

            if not new_token:
                logger.error(f"Meta token refresh: no access_token in response: {data}")
                return {"success": False, "error": "No access_token in response"}

            # Update environment variable so the running process uses the new token
            os.environ["META_AD_LIBRARY_TOKEN"] = new_token

            # Update AWS SSM Parameter Store
            await self._update_ssm_token(new_token)

            expiry_days = expires_in // 86400
            expiry_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            logger.info(
                f"Meta token refreshed successfully. "
                f"New token expires in {expiry_days} days (~{expires_in}s). "
                f"Refreshed at {expiry_date}"
            )

            return {"success": True, "expires_in": expires_in, "expires_days": expiry_days}

        except httpx.HTTPStatusError as e:
            error_body = e.response.text if e.response else str(e)
            logger.error(f"Meta token refresh HTTP error: {e.response.status_code} - {error_body}")
            return {"success": False, "error": f"HTTP {e.response.status_code}: {error_body}"}
        except Exception as e:
            logger.error(f"Meta token refresh failed: {e}")
            return {"success": False, "error": str(e)}

    async def _update_ssm_token(self, new_token: str) -> None:
        """Update the META_AD_LIBRARY_TOKEN in AWS SSM Parameter Store."""
        try:
            import boto3
            ssm = boto3.client("ssm", region_name="eu-central-1")
            ssm.put_parameter(
                Name="/panoramai/prod/META_AD_LIBRARY_TOKEN",
                Value=new_token,
                Type="SecureString",
                Overwrite=True,
            )
            logger.info("Meta token updated in AWS SSM Parameter Store")
        except Exception as e:
            logger.error(f"Failed to update Meta token in SSM: {e}")
            raise

    # ── SearchAPI fallbacks ──────────────────────────────────────────

    async def _searchapi_page_search(self, query: str) -> list[dict]:
        if not self.searchapi_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://www.searchapi.io/api/v1/search",
                    params={
                        "engine": "meta_ad_library_page_search",
                        "q": query,
                        "api_key": self.searchapi_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            return [
                {"page_id": p["page_id"], "name": p.get("name", ""), "likes": p.get("likes", 0)}
                for p in data.get("page_results", [])
            ]
        except Exception as e:
            logger.error(f"SearchAPI page search error: {e}")
            return []

    async def _searchapi_ads(self, page_id: str, country: str = "FR") -> list[dict]:
        if not self.searchapi_key:
            return []
        try:
            import urllib.parse
            all_ads = []
            next_token = None
            async with httpx.AsyncClient(timeout=30) as client:
                for _ in range(50):  # Max 50 pages
                    params = {
                        "engine": "meta_ad_library",
                        "page_id": page_id,
                        "active_status": "active",
                        "country": country,
                        "api_key": self.searchapi_key,
                    }
                    if next_token:
                        params["next_page_token"] = next_token
                    resp = await client.get(
                        "https://www.searchapi.io/api/v1/search",
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    ads = data.get("ads", [])
                    if not ads:
                        break
                    all_ads.extend(ads)
                    next_token = data.get("pagination", {}).get("next_page_token")
                    if not next_token:
                        break
                    await asyncio.sleep(1.1)
            return all_ads
        except Exception as e:
            logger.error(f"SearchAPI ads error: {e}")
            return []


meta_ad_library = MetaAdLibraryService()
