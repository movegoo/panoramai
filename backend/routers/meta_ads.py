"""
Meta Ad Library API router.
Uses official Meta Graph API (free) + SearchAPI fallback for payer data.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from core.auth import get_current_user

from services.meta_ad_library import meta_ad_library

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
