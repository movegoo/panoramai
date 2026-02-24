"""
Google My Business enrichment service.
Fetches real ratings/reviews for store locations via SearchAPI Google Maps
with Google Places API as fallback.
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

SEARCHAPI_BASE = "https://www.searchapi.io/api/v1/search"
GOOGLE_PLACES_BASE = "https://maps.googleapis.com/maps/api/place"


class GMBService:
    """Enrich store locations with real Google ratings and reviews."""

    @property
    def searchapi_key(self) -> str:
        return os.getenv("SEARCHAPI_KEY", "") or settings.SEARCHAPI_KEY

    @property
    def google_places_key(self) -> str:
        return os.getenv("GOOGLE_PLACES_API_KEY", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.searchapi_key or self.google_places_key)

    async def enrich_store(
        self,
        store_name: str,
        brand_name: str,
        city: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> dict:
        """
        Fetch GMB data for a single store.
        Tries SearchAPI first, then Google Places API as fallback.
        Returns {rating, reviews_count, place_id} or {error}.
        """
        # Try SearchAPI Google Maps first
        if self.searchapi_key:
            result = await self._searchapi_lookup(store_name, brand_name, city, latitude, longitude)
            if result.get("success"):
                return result

        # Fallback: Google Places API
        if self.google_places_key:
            result = await self._google_places_lookup(store_name, brand_name, city, latitude, longitude)
            if result.get("success"):
                return result

        return {"success": False, "error": "No API configured or lookup failed"}

    async def enrich_stores_batch(
        self,
        stores: list[dict],
        max_per_run: int = 100,
        cache_days: int = 30,
    ) -> dict:
        """
        Enrich a batch of stores with GMB data.
        Skips stores already enriched within cache_days.
        Returns stats {enriched, skipped, errors}.
        """
        enriched = 0
        skipped = 0
        errors = 0
        results = []

        for store in stores[:max_per_run]:
            # Skip if recently enriched
            if store.get("rating_fetched_at"):
                fetched_at = store["rating_fetched_at"]
                if isinstance(fetched_at, str):
                    fetched_at = datetime.fromisoformat(fetched_at)
                if datetime.utcnow() - fetched_at < timedelta(days=cache_days):
                    skipped += 1
                    continue

            result = await self.enrich_store(
                store_name=store.get("name", ""),
                brand_name=store.get("brand_name", ""),
                city=store.get("city", ""),
                latitude=store.get("latitude"),
                longitude=store.get("longitude"),
            )

            if result.get("success"):
                enriched += 1
                results.append({
                    "store_id": store.get("id"),
                    "google_rating": result.get("rating"),
                    "google_reviews_count": result.get("reviews_count"),
                    "google_place_id": result.get("place_id"),
                })
            else:
                errors += 1

            # Rate limit
            await asyncio.sleep(1.1)

        return {
            "enriched": enriched,
            "skipped": skipped,
            "errors": errors,
            "results": results,
        }

    # ── SearchAPI Google Maps ────────────────────────────────────────

    async def _searchapi_lookup(
        self,
        store_name: str,
        brand_name: str,
        city: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> dict:
        query = f"{brand_name} {city}" if brand_name else f"{store_name} {city}"
        params: dict = {
            "engine": "google_maps",
            "q": query,
            "hl": "fr",
            "gl": "fr",
            "api_key": self.searchapi_key,
        }
        if latitude and longitude:
            params["ll"] = f"@{latitude},{longitude},14z"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(SEARCHAPI_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()

            results = data.get("local_results", [])
            if not results:
                return {"success": False, "error": "No results"}

            # Find best match — prefer exact brand name match
            best = self._find_best_match(results, brand_name, store_name, latitude, longitude)
            if not best:
                return {"success": False, "error": "No matching result"}

            return {
                "success": True,
                "rating": best.get("rating"),
                "reviews_count": best.get("reviews"),
                "place_id": best.get("place_id"),
                "title": best.get("title"),
                "address": best.get("address"),
                "source": "searchapi",
            }
        except Exception as e:
            logger.warning(f"SearchAPI Google Maps error for '{query}': {e}")
            return {"success": False, "error": str(e)}

    # ── Google Places API (fallback) ─────────────────────────────────

    async def _google_places_lookup(
        self,
        store_name: str,
        brand_name: str,
        city: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> dict:
        query = f"{brand_name} {city}" if brand_name else f"{store_name} {city}"

        params: dict = {
            "input": query,
            "inputtype": "textquery",
            "fields": "place_id,name,rating,user_ratings_total,formatted_address,geometry",
            "key": self.google_places_key,
        }
        if latitude and longitude:
            params["locationbias"] = f"circle:5000@{latitude},{longitude}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{GOOGLE_PLACES_BASE}/findplacefromtext/json",
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()

            candidates = data.get("candidates", [])
            if not candidates:
                return {"success": False, "error": "No candidates"}

            place = candidates[0]
            return {
                "success": True,
                "rating": place.get("rating"),
                "reviews_count": place.get("user_ratings_total"),
                "place_id": place.get("place_id"),
                "title": place.get("name"),
                "address": place.get("formatted_address"),
                "source": "google_places",
            }
        except Exception as e:
            logger.warning(f"Google Places API error for '{query}': {e}")
            return {"success": False, "error": str(e)}

    # ── Matching helpers ─────────────────────────────────────────────

    def _find_best_match(
        self,
        results: list[dict],
        brand_name: str,
        store_name: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Optional[dict]:
        """Find the best matching result from Google Maps results."""
        brand_lower = brand_name.lower() if brand_name else ""
        store_lower = store_name.lower() if store_name else ""

        scored = []
        for r in results:
            title = (r.get("title") or "").lower()
            score = 0

            # Brand name match
            if brand_lower and brand_lower in title:
                score += 10
            # Store name match
            if store_lower and store_lower in title:
                score += 5

            # Distance bonus if we have coords
            if latitude and longitude:
                coords = r.get("gps_coordinates", {})
                rlat = coords.get("latitude")
                rlon = coords.get("longitude")
                if rlat and rlon:
                    dist = ((rlat - latitude) ** 2 + (rlon - longitude) ** 2) ** 0.5
                    if dist < 0.01:  # ~1km
                        score += 8
                    elif dist < 0.05:  # ~5km
                        score += 4

            # Has rating = better result
            if r.get("rating"):
                score += 2

            scored.append((score, r))

        scored.sort(key=lambda x: -x[0])
        return scored[0][1] if scored and scored[0][0] >= 5 else None


gmb_service = GMBService()
