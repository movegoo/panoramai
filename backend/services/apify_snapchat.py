"""
Apify Snapchat Ads scraper service.
Uses the lexis-solutions~snapchat-ads-scraper actor to fetch ads from adsgallery.snap.com.
"""
import asyncio
import logging
from datetime import datetime

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

ACTOR_ID = "lexis-solutions~snapchat-ads-scraper"
APIFY_BASE = "https://api.apify.com/v2"
POLL_INTERVAL = 5  # seconds
POLL_TIMEOUT = 120  # seconds


class ApifySnapchatService:
    """Fetch Snapchat ads via Apify actor."""

    async def search_snapchat_ads(self, query: str, country: str = "FR") -> dict:
        """Run the Snapchat ads scraper actor and return parsed ads."""
        token = settings.APIFY_API_KEY
        if not token:
            return {"success": False, "error": "APIFY_API_KEY not configured"}

        try:
            async with httpx.AsyncClient(timeout=180) as client:
                # 1. Start the actor run
                run_url = f"{APIFY_BASE}/acts/{ACTOR_ID}/runs?token={token}"
                run_resp = await client.post(run_url, json={
                    "search": query,
                    "country": country,
                })
                if run_resp.status_code != 201:
                    return {"success": False, "error": f"Apify start failed: {run_resp.status_code} {run_resp.text[:200]}"}

                run_data = run_resp.json().get("data", {})
                run_id = run_data.get("id")
                if not run_id:
                    return {"success": False, "error": "No run ID returned"}

                # 2. Poll until completion
                status_url = f"{APIFY_BASE}/actor-runs/{run_id}?token={token}"
                elapsed = 0
                while elapsed < POLL_TIMEOUT:
                    await asyncio.sleep(POLL_INTERVAL)
                    elapsed += POLL_INTERVAL

                    status_resp = await client.get(status_url)
                    if status_resp.status_code != 200:
                        continue
                    status = status_resp.json().get("data", {}).get("status")
                    if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                        break

                if status != "SUCCEEDED":
                    return {"success": False, "error": f"Actor run ended with status: {status}"}

                # 3. Get dataset items
                dataset_id = status_resp.json().get("data", {}).get("defaultDatasetId")
                if not dataset_id:
                    return {"success": False, "error": "No dataset ID"}

                items_url = f"{APIFY_BASE}/datasets/{dataset_id}/items?token={token}"
                items_resp = await client.get(items_url)
                if items_resp.status_code != 200:
                    return {"success": False, "error": f"Dataset fetch failed: {items_resp.status_code}"}

                raw_items = items_resp.json() if isinstance(items_resp.json(), list) else []

                # 4. Map to internal format
                ads = [self._map_ad(item) for item in raw_items]
                ads = [a for a in ads if a is not None]

                return {
                    "success": True,
                    "ads": ads,
                    "ads_count": len(ads),
                    "total_results": len(raw_items),
                }

        except Exception as e:
            logger.error(f"Apify Snapchat error: {e}")
            return {"success": False, "error": str(e)}

    def _map_ad(self, item: dict) -> dict | None:
        """Map Apify item to internal ad format."""
        ad_id = item.get("id")
        if not ad_id:
            return None

        # Parse start date
        start_date = None
        raw_date = item.get("startDate")
        if raw_date:
            try:
                start_date = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return {
            "snap_id": f"snap_{ad_id}",
            "page_name": item.get("brandName") or item.get("profileName") or "",
            "ad_text": item.get("adName") or "",
            "title": item.get("headline") or item.get("adName") or "",
            "creative_url": item.get("mediaDownloadLink") or "",
            "display_format": item.get("snapMediaType") or "SNAP",
            "impressions": item.get("totalImpressions") or 0,
            "start_date": start_date,
            "is_active": (item.get("adStatus") or "").upper() == "ACTIVE",
            "raw": item,
        }


    async def discover_entity_names(self, query: str, country: str = "FR") -> dict:
        """Search Snapchat ads and extract unique brand/profile names.

        Returns a list of discovered entity names from ad results,
        useful for auto-populating snapchat_entity_name.
        """
        result = await self.search_snapchat_ads(query=query, country=country)
        if not result.get("success"):
            return result

        # Extract unique brand/profile names from ads
        entity_counts: dict[str, int] = {}
        for ad in result.get("ads", []):
            name = ad.get("page_name", "").strip()
            if name:
                entity_counts[name] = entity_counts.get(name, 0) + 1

        # Sort by frequency (most ads = most likely the right entity)
        entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            "success": True,
            "query": query,
            "entities": [{"name": name, "ads_count": count} for name, count in entities],
            "total_ads": result.get("ads_count", 0),
        }


apify_snapchat = ApifySnapchatService()
