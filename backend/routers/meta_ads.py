"""
Meta Ad Library API router.
Uses official Meta Graph API (free) + SearchAPI fallback for payer data.
"""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.auth import get_current_user
from database import get_db, Ad, Competitor

from services.meta_ad_library import meta_ad_library

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search-page")
async def search_page(
    q: str = Query(..., min_length=2, description="Page name to search"),
    _user=Depends(get_current_user),
):
    """Search for a Facebook page by name."""
    results = await meta_ad_library.search_page(q)
    return {"pages": results}


@router.get("/page/{page_id}/ads")
async def get_page_ads(
    page_id: str,
    country: str = Query("FR"),
    limit: int = Query(0, description="0 = all"),
    _user=Depends(get_current_user),
):
    """Get all active ads for a Facebook page."""
    ads = await meta_ad_library.get_active_ads(page_id, country, limit)
    return {
        "page_id": page_id,
        "count": len(ads),
        "ads": ads,
    }


@router.get("/page/{page_id}/summary")
async def get_page_summary(
    page_id: str,
    country: str = Query("FR"),
    _user=Depends(get_current_user),
):
    """Full summary: ad count, reach, platforms, targeting."""
    summary = await meta_ad_library.get_page_summary(page_id, country)
    return summary


@router.post("/page/{page_id}/payers")
async def get_page_payers(
    page_id: str,
    country: str = Query("FR"),
    sample_size: int = Query(50, ge=1, le=200),
    _user=Depends(get_current_user),
):
    """
    Get payer breakdown for a page's ads.
    Uses Meta API for listing + SearchAPI for payer details (EU transparency).
    Raw data only, no extrapolation.
    """
    ads = await meta_ad_library.get_active_ads(page_id, country)
    if not ads:
        return {"page_id": page_id, "total_ads": 0, "sampled": 0, "payers": []}

    result = await meta_ad_library.enrich_payers(ads, sample_size)
    result["page_id"] = page_id
    result["page_name"] = ads[0].get("page_name", "") if ads else ""
    return result


class FetchPagesRequest(BaseModel):
    pages: dict[str, str]  # {brand_name: page_id}
    country: str = "FR"


@router.post("/fetch-and-store")
async def fetch_and_store_ads(
    req: FetchPagesRequest,
    db: Session = Depends(get_db),
):
    """
    Fetch active ads from Meta API for given pages and store them in DB.
    Maps pages to competitors by name match.
    """
    results = {}
    total_new = 0
    total_updated = 0

    for brand_name, page_id in req.pages.items():
        # Find competitor by name (case-insensitive)
        competitor = db.query(Competitor).filter(
            Competitor.name.ilike(f"%{brand_name}%"),
            Competitor.is_active == True,
        ).first()

        if not competitor:
            results[brand_name] = {"error": f"Competitor not found for '{brand_name}'"}
            continue

        # Update facebook_page_id if not set
        if not competitor.facebook_page_id:
            competitor.facebook_page_id = page_id
            db.commit()

        # Fetch ads from Meta API
        ads = await meta_ad_library.get_active_ads(page_id, req.country)
        new_count = 0
        updated_count = 0

        for ad in ads:
            ad_id = str(ad.get("id", ""))
            if not ad_id:
                continue

            existing = db.query(Ad).filter(Ad.ad_id == ad_id).first()

            platforms = ad.get("publisher_platforms", [])
            if not isinstance(platforms, list):
                platforms = [platforms] if platforms else []
            platforms_upper = [p.upper() for p in platforms]

            platform = "facebook"
            for p in platforms_upper:
                if "INSTAGRAM" in p.upper():
                    platform = "instagram"
                    break

            bodies = ad.get("ad_creative_bodies", [])
            ad_text = bodies[0] if bodies else ""
            titles = ad.get("ad_creative_link_titles", [])
            title_val = titles[0] if titles else ""
            descs = ad.get("ad_creative_link_descriptions", [])
            desc_val = descs[0][:2000] if descs else ""

            start_date = None
            if ad.get("ad_delivery_start_time"):
                try:
                    start_date = datetime.fromisoformat(ad["ad_delivery_start_time"])
                except (ValueError, TypeError):
                    pass

            end_date = None
            if ad.get("ad_delivery_stop_time"):
                try:
                    end_date = datetime.fromisoformat(ad["ad_delivery_stop_time"])
                except (ValueError, TypeError):
                    pass

            reach = ad.get("eu_total_reach")
            target_locs = ad.get("target_locations", [])
            targeted_countries = list({loc.get("country") for loc in target_locs if loc.get("country")}) if target_locs else ["FR"]

            fields = dict(
                competitor_id=competitor.id,
                platform=platform,
                ad_text=ad_text[:5000] if ad_text else None,
                title=title_val or None,
                link_description=desc_val or None,
                start_date=start_date,
                end_date=end_date,
                is_active=True,
                publisher_platforms=json.dumps(platforms_upper) if platforms_upper else None,
                page_id=page_id,
                page_name=ad.get("page_name", brand_name),
                targeted_countries=json.dumps(targeted_countries),
                ad_library_url=ad.get("ad_snapshot_url"),
                creative_url=ad.get("ad_snapshot_url"),
            )

            if existing:
                for k, v in fields.items():
                    if v is not None:
                        setattr(existing, k, v)
                updated_count += 1
            else:
                new_ad = Ad(ad_id=ad_id, **fields)
                db.add(new_ad)
                new_count += 1

        db.commit()
        total_new += new_count
        total_updated += updated_count
        results[brand_name] = {
            "competitor_id": competitor.id,
            "page_id": page_id,
            "fetched": len(ads),
            "new": new_count,
            "updated": updated_count,
        }
        logger.info(f"Meta ads stored for {brand_name}: {new_count} new, {updated_count} updated")

    return {
        "total_new": total_new,
        "total_updated": total_updated,
        "details": results,
    }
