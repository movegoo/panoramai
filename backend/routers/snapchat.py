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

from sqlalchemy import func

from database import get_db, Competitor, Ad, User, SnapchatData
from services.apify_snapchat import apify_snapchat
from services.scrapecreators import scrapecreators
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


@router.post("/profile/fetch")
async def fetch_snapchat_profile(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Fetch and store Snapchat profile data for a competitor."""
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))

    username = competitor.snapchat_username
    if not username:
        raise HTTPException(status_code=400, detail="No snapchat_username configured for this competitor")

    result = await scrapecreators.fetch_snapchat_profile(username)
    if not result.get("success"):
        raise HTTPException(status_code=503, detail=f"Snapchat profile fetch error: {result.get('error', 'Unknown')}")

    snap_data = SnapchatData(
        competitor_id=competitor_id,
        subscribers=result.get("subscribers", 0),
        title=result.get("title", ""),
        story_count=result.get("story_count", 0),
        spotlight_count=result.get("spotlight_count", 0),
        total_views=result.get("total_views", 0),
        total_shares=result.get("total_shares", 0),
        total_comments=result.get("total_comments", 0),
        engagement_rate=result.get("engagement_rate", 0),
        profile_picture_url=result.get("profile_picture_url", ""),
    )
    db.add(snap_data)
    db.commit()

    return {
        "message": f"Snapchat profile fetched for {competitor.name}",
        "subscribers": result.get("subscribers", 0),
        "story_count": result.get("story_count", 0),
        "spotlight_count": result.get("spotlight_count", 0),
        "engagement_rate": result.get("engagement_rate", 0),
    }


@router.get("/profile/comparison")
async def compare_snapchat_profiles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Compare Snapchat profile metrics across all tracked competitors."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)
    comp_ids = [c.id for c in competitors]

    # Get latest SnapchatData per competitor
    from sqlalchemy import func as sqlfunc
    sub = db.query(
        SnapchatData.competitor_id,
        sqlfunc.max(SnapchatData.recorded_at).label("max_at"),
    ).filter(SnapchatData.competitor_id.in_(comp_ids)).group_by(SnapchatData.competitor_id).subquery()

    rows = db.query(SnapchatData).join(
        sub,
        (SnapchatData.competitor_id == sub.c.competitor_id) & (SnapchatData.recorded_at == sub.c.max_at),
    ).all()
    snap_map = {r.competitor_id: r for r in rows}

    result = []
    for c in competitors:
        sd = snap_map.get(c.id)
        if sd:
            result.append({
                "competitor_id": c.id,
                "competitor_name": c.name,
                "subscribers": sd.subscribers,
                "engagement_rate": sd.engagement_rate,
                "spotlight_count": sd.spotlight_count,
                "story_count": sd.story_count,
                "total_views": sd.total_views,
            })

    result.sort(key=lambda x: x["subscribers"] or 0, reverse=True)
    return result


@router.get("/comparison")
async def compare_snapchat(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Compare Snapchat ads metrics across all tracked competitors."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)

    rows = (
        db.query(
            Ad.competitor_id,
            func.count(Ad.id).label("ads_count"),
            func.coalesce(func.sum(Ad.impressions_min), 0).label("impressions_total"),
        )
        .filter(
            Ad.competitor_id.in_([c.id for c in competitors]),
            Ad.platform == "snapchat",
        )
        .group_by(Ad.competitor_id)
        .all()
    )
    snap_map = {r.competitor_id: {"ads_count": r.ads_count, "impressions_total": int(r.impressions_total)} for r in rows}

    # Also load latest profile data
    comp_ids = [c.id for c in competitors]
    profile_map = {}
    if comp_ids:
        from sqlalchemy import func as sqlfunc
        sub = db.query(
            SnapchatData.competitor_id,
            sqlfunc.max(SnapchatData.recorded_at).label("max_at"),
        ).filter(SnapchatData.competitor_id.in_(comp_ids)).group_by(SnapchatData.competitor_id).subquery()
        profile_rows = db.query(SnapchatData).join(
            sub,
            (SnapchatData.competitor_id == sub.c.competitor_id) & (SnapchatData.recorded_at == sub.c.max_at),
        ).all()
        profile_map = {r.competitor_id: r for r in profile_rows}

    return [
        {
            "competitor_id": c.id,
            "competitor_name": c.name,
            "ads_count": snap_map.get(c.id, {}).get("ads_count", 0),
            "impressions_total": snap_map.get(c.id, {}).get("impressions_total", 0),
            "entity_name": c.snapchat_entity_name,
            "subscribers": profile_map[c.id].subscribers if c.id in profile_map else None,
            "engagement_rate": profile_map[c.id].engagement_rate if c.id in profile_map else None,
            "spotlight_count": profile_map[c.id].spotlight_count if c.id in profile_map else None,
            "story_count": profile_map[c.id].story_count if c.id in profile_map else None,
        }
        for c in competitors
        if snap_map.get(c.id) or c.snapchat_entity_name or c.id in profile_map
    ]


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

    result = await apify_snapchat.search_snapchat_ads(query=competitor.snapchat_entity_name or competitor.name)

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


@router.post("/discover-entity/{competitor_id}")
async def discover_snapchat_entity(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Discover the Snapchat entity name for a competitor via Apify.

    Searches Snapchat ads by competitor name, extracts brand/profile names
    from results, and optionally stores the best match.
    """
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))

    result = await apify_snapchat.discover_entity_names(query=competitor.name)
    if not result.get("success"):
        raise HTTPException(
            status_code=503,
            detail=f"Snapchat discovery error: {result.get('error', 'Unknown')}",
        )

    entities = result.get("entities", [])

    # Auto-store the best match if not already set
    stored = False
    if entities and not competitor.snapchat_entity_name:
        best = entities[0]["name"]
        competitor.snapchat_entity_name = best
        db.commit()
        stored = True

    return {
        "competitor_id": competitor_id,
        "competitor_name": competitor.name,
        "entities": entities,
        "total_ads": result.get("total_ads", 0),
        "stored": stored,
        "snapchat_entity_name": competitor.snapchat_entity_name,
    }


@router.post("/discover-entities")
async def discover_all_snapchat_entities(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Discover Snapchat entity names for all competitors missing one."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)

    results = []
    for comp in competitors:
        if comp.snapchat_entity_name:
            results.append({
                "competitor": comp.name,
                "status": "already_set",
                "snapchat_entity_name": comp.snapchat_entity_name,
            })
            continue

        try:
            result = await apify_snapchat.discover_entity_names(query=comp.name)
            if not result.get("success"):
                results.append({"competitor": comp.name, "status": "error", "error": result.get("error")})
                continue

            entities = result.get("entities", [])
            if entities:
                best = entities[0]["name"]
                comp.snapchat_entity_name = best
                db.commit()
                results.append({
                    "competitor": comp.name,
                    "status": "discovered",
                    "snapchat_entity_name": best,
                    "alternatives": [e["name"] for e in entities[1:4]],
                })
            else:
                results.append({"competitor": comp.name, "status": "not_found"})
        except Exception as e:
            results.append({"competitor": comp.name, "status": "error", "error": str(e)})

    return {"message": "Snapchat entity discovery complete", "results": results}


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
            result = await apify_snapchat.search_snapchat_ads(query=comp.snapchat_entity_name or comp.name)
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
