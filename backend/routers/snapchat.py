"""
Snapchat Ads router.
Endpoints for fetching and viewing Snapchat ads via Apify scraper.
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db, Competitor, Ad, User
from services.apify_snapchat import apify_snapchat
from core.auth import get_current_user
from core.permissions import verify_competitor_ownership, get_user_competitors, parse_advertiser_header

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_json_safe(value):
    if not value:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _serialize_snap_ad(ad: Ad) -> dict:
    """Serialize a Snapchat ad to JSON-friendly dict."""
    return {
        "id": ad.id,
        "competitor_id": ad.competitor_id,
        "ad_id": ad.ad_id,
        "platform": "snapchat",
        "creative_url": ad.creative_url,
        "ad_text": ad.ad_text,
        "title": ad.title,
        "start_date": ad.start_date.isoformat() if ad.start_date else None,
        "is_active": ad.is_active,
        "impressions_min": ad.impressions_min or 0,
        "impressions_max": ad.impressions_max or 0,
        "page_name": ad.page_name,
        "display_format": ad.display_format,
        "ad_library_url": ad.ad_library_url,
        # Creative Analysis
        "creative_concept": ad.creative_concept,
        "creative_hook": ad.creative_hook,
        "creative_tone": ad.creative_tone,
        "creative_dominant_colors": _parse_json_safe(ad.creative_dominant_colors),
        "creative_has_product": ad.creative_has_product,
        "creative_has_face": ad.creative_has_face,
        "creative_has_logo": ad.creative_has_logo,
        "creative_layout": ad.creative_layout,
        "creative_cta_style": ad.creative_cta_style,
        "creative_score": ad.creative_score,
        "creative_tags": _parse_json_safe(ad.creative_tags),
        "creative_summary": ad.creative_summary,
        "creative_analyzed_at": ad.creative_analyzed_at.isoformat() if ad.creative_analyzed_at else None,
    }


@router.get("/ads/all")
async def get_all_snapchat_ads(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get all Snapchat ads stored in the database."""
    competitors = {c.id: c.name for c in get_user_competitors(db, user, advertiser_id=int(x_advertiser_id) if x_advertiser_id else None)}
    ads = (
        db.query(Ad)
        .filter(Ad.platform == "snapchat", Ad.competitor_id.in_(competitors.keys()))
        .order_by(desc(Ad.start_date))
        .all()
    )
    return [
        {**_serialize_snap_ad(ad), "competitor_name": competitors.get(ad.competitor_id, "?")}
        for ad in ads
    ]


@router.get("/ads/{competitor_id}")
async def get_snapchat_ads(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get Snapchat ads for a specific competitor."""
    verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))
    ads = (
        db.query(Ad)
        .filter(Ad.competitor_id == competitor_id, Ad.platform == "snapchat")
        .order_by(desc(Ad.start_date))
        .all()
    )
    return [_serialize_snap_ad(ad) for ad in ads]


@router.post("/ads/fetch/{competitor_id}")
async def fetch_snapchat_ads(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Fetch Snapchat ads for a competitor via Apify."""
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))

    result = await apify_snapchat.search_snapchat_ads(query=competitor.name)

    if not result.get("success"):
        raise HTTPException(
            status_code=503,
            detail=f"Snapchat ads fetch error: {result.get('error', 'Unknown')}"
        )

    ads_data = result.get("ads", [])
    new_count = 0
    updated_count = 0

    for ad in ads_data:
        ad_id = ad.get("snap_id", "")
        if not ad_id:
            continue

        existing = db.query(Ad).filter(Ad.ad_id == ad_id).first()

        enriched = dict(
            platform="snapchat",
            creative_url=ad.get("creative_url", ""),
            ad_text=ad.get("ad_text", ""),
            title=ad.get("title", "")[:200] if ad.get("title") else None,
            start_date=ad.get("start_date"),
            is_active=ad.get("is_active", False),
            impressions_min=ad.get("impressions", 0),
            impressions_max=ad.get("impressions", 0),
            publisher_platforms=json.dumps(["SNAPCHAT"]),
            page_name=ad.get("page_name", ""),
            display_format=ad.get("display_format", "SNAP"),
            ad_library_url=f"https://adsgallery.snap.com/",
        )

        if existing:
            for k, v in enriched.items():
                setattr(existing, k, v)
            updated_count += 1
        else:
            new_ad = Ad(competitor_id=competitor_id, ad_id=ad_id, **enriched)
            db.add(new_ad)
            new_count += 1

    db.commit()

    return {
        "message": f"Found {result.get('ads_count', 0)} Snapchat ads for {competitor.name}",
        "total_searched": result.get("total_results", 0),
        "ads_detected": result.get("ads_count", 0),
        "new_stored": new_count,
        "updated": updated_count,
    }


@router.post("/ads/fetch-all")
async def fetch_all_snapchat_ads(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Fetch Snapchat ads for all active competitors."""
    from core.permissions import get_user_competitors, parse_advertiser_header
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)
    results = []
    for comp in competitors:
        try:
            result = await apify_snapchat.search_snapchat_ads(query=comp.name)
            if not result.get("success"):
                results.append({"competitor": comp.name, "error": result.get("error")})
                continue

            new_count = 0
            for ad in result.get("ads", []):
                ad_id = ad.get("snap_id", "")
                if not ad_id:
                    continue
                if db.query(Ad).filter(Ad.ad_id == ad_id).first():
                    continue

                new_ad = Ad(
                    competitor_id=comp.id,
                    ad_id=ad_id,
                    platform="snapchat",
                    creative_url=ad.get("creative_url", ""),
                    ad_text=ad.get("ad_text", ""),
                    title=ad.get("title", "")[:200] if ad.get("title") else None,
                    start_date=ad.get("start_date"),
                    is_active=ad.get("is_active", False),
                    impressions_min=ad.get("impressions", 0),
                    impressions_max=ad.get("impressions", 0),
                    publisher_platforms=json.dumps(["SNAPCHAT"]),
                    page_name=ad.get("page_name", ""),
                    display_format=ad.get("display_format", "SNAP"),
                    ad_library_url=f"https://adsgallery.snap.com/",
                )
                db.add(new_ad)
                new_count += 1

            db.commit()
            results.append({
                "competitor": comp.name,
                "ads_detected": result.get("ads_count", 0),
                "new_stored": new_count,
            })
        except Exception as e:
            results.append({"competitor": comp.name, "error": str(e)})

    return {
        "message": "Snapchat ads fetch complete",
        "results": results,
    }
