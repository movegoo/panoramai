"""
Google My Business enrichment service.
Fetches real ratings/reviews for store locations via SearchAPI Google Maps
with Google Places API as fallback.
"""
import asyncio
import json
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


def compute_gmb_score(
    rating: Optional[float] = None,
    reviews_count: Optional[int] = None,
    phone: Optional[str] = None,
    website: Optional[str] = None,
    hours: Optional[str] = None,
    thumbnail: Optional[str] = None,
    gtype: Optional[str] = None,
    open_state: Optional[str] = None,
) -> int:
    """
    Compute a composite GMB score (0-100) based on:
    - Rating (0-30 pts)
    - Volume of reviews (0-25 pts)
    - Profile completeness (0-25 pts)
    - Open status (0-20 pts)
    """
    score = 0

    # Rating (0-30)
    if rating is not None:
        if rating >= 4.5:
            score += 30
        elif rating >= 4.0:
            score += 22
        elif rating >= 3.5:
            score += 15
        else:
            score += 5

    # Reviews volume (0-25)
    if reviews_count is not None:
        if reviews_count >= 200:
            score += 25
        elif reviews_count >= 100:
            score += 18
        elif reviews_count >= 50:
            score += 12
        elif reviews_count >= 10:
            score += 6
        else:
            score += 2

    # Profile completeness (0-25): 5 pts each
    if phone:
        score += 5
    if website:
        score += 5
    if hours:
        score += 5
    if thumbnail:
        score += 5
    if gtype:
        score += 5

    # Open status (0-20)
    if open_state:
        state_lower = open_state.lower()
        if "ouvert" in state_lower or "open" in state_lower:
            score += 20
        elif "fermé temporairement" in state_lower or "temporarily closed" in state_lower:
            score += 5
        else:
            score += 10
    else:
        score += 10  # No data = neutral

    return min(score, 100)


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
        Returns {rating, reviews_count, place_id, phone, website, type,
                 thumbnail, open_state, hours, price} or {error}.
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

            # Extract extended fields from SearchAPI local_results
            hours_json = None
            hours_data = best.get("operating_hours") or best.get("hours")
            if hours_data:
                hours_json = json.dumps(hours_data, ensure_ascii=False) if isinstance(hours_data, (dict, list)) else str(hours_data)

            return {
                "success": True,
                "rating": best.get("rating"),
                "reviews_count": best.get("reviews"),
                "place_id": best.get("place_id"),
                "title": best.get("title"),
                "address": best.get("address"),
                "phone": best.get("phone"),
                "website": best.get("website"),
                "type": best.get("type"),
                "thumbnail": best.get("thumbnail"),
                "open_state": best.get("open_state"),
                "hours": hours_json,
                "price": best.get("price"),
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
            "fields": "place_id,name,rating,user_ratings_total,formatted_address,geometry,"
                      "formatted_phone_number,website,types,opening_hours,photos,business_status,price_level",
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

            # Map price_level to symbols
            price_level = place.get("price_level")
            price_str = None
            if price_level is not None:
                price_str = "$" * max(1, price_level)

            # Opening hours
            hours_json = None
            opening_hours = place.get("opening_hours")
            if opening_hours:
                hours_json = json.dumps(opening_hours.get("weekday_text", []), ensure_ascii=False)

            # Business status -> open_state
            biz_status = place.get("business_status")
            open_state = None
            if biz_status == "OPERATIONAL":
                open_state = "Ouvert"
            elif biz_status == "TEMPORARILY_CLOSED":
                open_state = "Fermé temporairement"
            elif biz_status == "CLOSED_PERMANENTLY":
                open_state = "Fermé définitivement"

            # Thumbnail from photos
            thumbnail = None
            photos = place.get("photos")
            if photos and self.google_places_key:
                ref = photos[0].get("photo_reference")
                if ref:
                    thumbnail = f"{GOOGLE_PLACES_BASE}/photo?maxwidth=400&photo_reference={ref}&key={self.google_places_key}"

            # Types -> primary type
            types = place.get("types", [])
            primary_type = types[0] if types else None

            return {
                "success": True,
                "rating": place.get("rating"),
                "reviews_count": place.get("user_ratings_total"),
                "place_id": place.get("place_id"),
                "title": place.get("name"),
                "address": place.get("formatted_address"),
                "phone": place.get("formatted_phone_number"),
                "website": place.get("website"),
                "type": primary_type,
                "thumbnail": thumbnail,
                "open_state": open_state,
                "hours": hours_json,
                "price": price_str,
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
