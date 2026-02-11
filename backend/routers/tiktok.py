"""
TikTok API router.
Endpoints for fetching and analyzing TikTok profile data + TikTok Ads.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime, timedelta
import json

from database import get_db, Competitor, TikTokData, Ad

from models.schemas import TikTokDataResponse, TrendResponse
from services.tiktok_scraper import tiktok_scraper
from services.scrapecreators import scrapecreators
from core.trends import calculate_trend
from core.config import settings

router = APIRouter()


# =============================================================================
# Helpers
# =============================================================================

def calculate_engagement_rate(data: TikTokData) -> float:
    """Calculate TikTok engagement rate."""
    if not data.followers or data.followers == 0:
        return 0.0

    if data.likes and data.videos_count and data.videos_count > 0:
        avg_likes_per_video = data.likes / data.videos_count
        return round((avg_likes_per_video / data.followers) * 100, 2)

    return 0.0


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/data/{competitor_id}", response_model=List[TikTokDataResponse])
async def get_tiktok_history(
    competitor_id: int,
    limit: int = 30,
    db: Session = Depends(get_db)
):
    """Get historical TikTok data for a competitor."""
    return (
        db.query(TikTokData)
        .filter(TikTokData.competitor_id == competitor_id)
        .order_by(desc(TikTokData.recorded_at))
        .limit(limit)
        .all()
    )


@router.get("/latest/{competitor_id}", response_model=TikTokDataResponse)
async def get_latest_tiktok_data(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """Get the latest TikTok data for a competitor."""
    data = (
        db.query(TikTokData)
        .filter(TikTokData.competitor_id == competitor_id)
        .order_by(desc(TikTokData.recorded_at))
        .first()
    )
    if not data:
        raise HTTPException(status_code=404, detail="No TikTok data found")
    return data


@router.post("/fetch/{competitor_id}")
async def fetch_tiktok_data(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """Fetch and store current TikTok data for a competitor."""
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    if not competitor.tiktok_username:
        raise HTTPException(status_code=400, detail="No TikTok username configured")

    # Rate limiting
    last_fetch = (
        db.query(TikTokData)
        .filter(TikTokData.competitor_id == competitor_id)
        .order_by(desc(TikTokData.recorded_at))
        .first()
    )

    if last_fetch:
        time_since_last = datetime.utcnow() - last_fetch.recorded_at
        min_interval = timedelta(hours=settings.MIN_FETCH_INTERVAL_HOURS)
        if time_since_last < min_interval:
            minutes_remaining = int((min_interval - time_since_last).total_seconds() / 60)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limited. Wait {minutes_remaining} minutes."
            )

    result = await tiktok_scraper.fetch_profile(competitor.tiktok_username)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Fetch failed: {result.get('error')}")

    tiktok_data = TikTokData(
        competitor_id=competitor_id,
        username=competitor.tiktok_username,
        followers=result.get("followers", 0),
        following=result.get("following", 0),
        likes=result.get("likes", 0),
        videos_count=result.get("videos_count", 0),
        bio=result.get("bio"),
        verified=result.get("verified", False)
    )
    db.add(tiktok_data)
    db.commit()
    db.refresh(tiktok_data)

    return {
        "message": "TikTok data fetched successfully",
        "data": {
            "username": tiktok_data.username,
            "followers": tiktok_data.followers,
            "following": tiktok_data.following,
            "likes": tiktok_data.likes,
            "videos_count": tiktok_data.videos_count
        }
    }


@router.get("/comparison")
async def compare_tiktok_accounts(db: Session = Depends(get_db)):
    """Compare TikTok metrics across all tracked competitors."""
    competitors = (
        db.query(Competitor)
        .filter(Competitor.tiktok_username.isnot(None), Competitor.is_active == True)
        .all()
    )

    comparison = []
    for competitor in competitors:
        latest = (
            db.query(TikTokData)
            .filter(TikTokData.competitor_id == competitor.id)
            .order_by(desc(TikTokData.recorded_at))
            .first()
        )

        if latest:
            # Get data from 7 days ago for growth calculation
            week_ago = datetime.utcnow() - timedelta(days=7)
            old_data = (
                db.query(TikTokData)
                .filter(
                    TikTokData.competitor_id == competitor.id,
                    TikTokData.recorded_at <= week_ago,
                )
                .order_by(desc(TikTokData.recorded_at))
                .first()
            )

            follower_growth = 0
            if old_data and old_data.followers and old_data.followers > 0:
                follower_growth = ((latest.followers - old_data.followers) / old_data.followers) * 100

            comparison.append({
                "competitor_id": competitor.id,
                "competitor_name": competitor.name,
                "username": competitor.tiktok_username,
                "followers": latest.followers,
                "following": latest.following,
                "likes": latest.likes,
                "videos_count": latest.videos_count,
                "engagement_rate": calculate_engagement_rate(latest),
                "follower_growth_7d": round(follower_growth, 2),
                "recorded_at": latest.recorded_at.isoformat(),
            })

    comparison.sort(key=lambda x: x["followers"] or 0, reverse=True)
    return comparison


@router.get("/trends/{competitor_id}", response_model=TrendResponse)
async def get_tiktok_trends(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """Get TikTok trends and variations for a competitor."""
    recent_data = (
        db.query(TikTokData)
        .filter(TikTokData.competitor_id == competitor_id)
        .order_by(desc(TikTokData.recorded_at))
        .limit(2)
        .all()
    )

    if not recent_data:
        raise HTTPException(status_code=404, detail="No TikTok data found")

    current = recent_data[0]
    previous = recent_data[1] if len(recent_data) > 1 else None

    current_data = {
        "followers": current.followers,
        "likes": current.likes,
        "videos_count": current.videos_count
    }

    if previous:
        previous_data = {
            "followers": previous.followers,
            "likes": previous.likes,
            "videos_count": previous.videos_count
        }
        trends = {
            "followers": calculate_trend(current.followers, previous.followers),
            "likes": calculate_trend(current.likes, previous.likes),
            "videos": calculate_trend(current.videos_count, previous.videos_count)
        }
    else:
        previous_data = None
        trends = {
            "followers": calculate_trend(None, None),
            "likes": calculate_trend(None, None),
            "videos": calculate_trend(None, None)
        }

    return TrendResponse(current=current_data, previous=previous_data, trends=trends)


@router.get("/videos/{competitor_id}")
async def get_recent_videos(
    competitor_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get recent TikTok videos for a competitor."""
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    if not competitor.tiktok_username:
        raise HTTPException(status_code=400, detail="No TikTok username configured")

    result = await tiktok_scraper.fetch_recent_videos(competitor.tiktok_username, limit)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Fetch failed: {result.get('error')}")

    return result


# =============================================================================
# TikTok Ads (via keyword search + is_ads detection)
# =============================================================================

@router.get("/ads/all")
async def get_all_tiktok_ads(
    db: Session = Depends(get_db),
):
    """Get all TikTok ads stored in the database."""
    ads = (
        db.query(Ad)
        .filter(Ad.platform == "tiktok")
        .order_by(desc(Ad.start_date))
        .all()
    )
    competitors = {c.id: c.name for c in db.query(Competitor).all()}
    return [
        {**_serialize_tiktok_ad(ad), "competitor_name": competitors.get(ad.competitor_id, "?")}
        for ad in ads
    ]


@router.get("/ads/{competitor_id}")
async def get_tiktok_ads(
    competitor_id: int,
    db: Session = Depends(get_db),
):
    """Get TikTok ads for a specific competitor."""
    ads = (
        db.query(Ad)
        .filter(Ad.competitor_id == competitor_id, Ad.platform == "tiktok")
        .order_by(desc(Ad.start_date))
        .all()
    )
    return [_serialize_tiktok_ad(ad) for ad in ads]


@router.post("/ads/fetch/{competitor_id}")
async def fetch_tiktok_ads(
    competitor_id: int,
    db: Session = Depends(get_db),
):
    """
    Fetch TikTok ads/sponsored content for a competitor via ScrapeCreators.
    Searches by competitor name and stores detected ads.
    """
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    result = await scrapecreators.search_tiktok_ads(query=competitor.name, limit=30)

    if not result.get("success"):
        raise HTTPException(
            status_code=503,
            detail=f"TikTok search error: {result.get('error', 'Unknown')}"
        )

    ads_data = result.get("ads", [])
    new_count = 0
    updated_count = 0

    for ad in ads_data:
        aweme_id = ad.get("aweme_id", "")
        if not aweme_id:
            continue

        ad_id = f"tt_{aweme_id}"

        # Check if ad already exists
        existing = db.query(Ad).filter(Ad.ad_id == ad_id).first()

        create_time = ad.get("create_time", 0)
        start_date = datetime.fromtimestamp(create_time) if create_time else None

        enriched = dict(
            platform="tiktok",
            creative_url=ad.get("cover_url", ""),
            ad_text=ad.get("description", ""),
            start_date=start_date,
            is_active=True,
            impressions_min=ad.get("play_count", 0),
            impressions_max=ad.get("play_count", 0),
            publisher_platforms=json.dumps(["TIKTOK"]),
            page_name=ad.get("author_nickname", ""),
            page_id=ad.get("author_id", ""),
            page_profile_uri=f"https://www.tiktok.com/@{ad.get('author_username', '')}",
            page_profile_picture_url=ad.get("author_avatar", ""),
            display_format="VIDEO",
            targeted_countries=None,
            ad_library_url=f"https://www.tiktok.com/@{ad.get('author_username', '')}/video/{aweme_id}",
            title=ad.get("description", "")[:200] if ad.get("description") else None,
            contains_ai_content=False,
            # Store extra TikTok metrics in existing fields
            estimated_spend_min=ad.get("like_count", 0),  # likes as proxy
            estimated_spend_max=ad.get("share_count", 0),  # shares as proxy
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
        "message": f"Found {result.get('ads_count', 0)} TikTok ads for {competitor.name}",
        "total_searched": result.get("total_results", 0),
        "ads_detected": result.get("ads_count", 0),
        "new_stored": new_count,
        "updated": updated_count,
        "credits_remaining": result.get("credits_remaining"),
    }


@router.post("/ads/fetch-all")
async def fetch_all_tiktok_ads(db: Session = Depends(get_db)):
    """Fetch TikTok ads for all active competitors."""
    competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
    results = []
    for comp in competitors:
        try:
            result = await scrapecreators.search_tiktok_ads(query=comp.name, limit=30)
            if not result.get("success"):
                results.append({"competitor": comp.name, "error": result.get("error")})
                continue

            new_count = 0
            for ad in result.get("ads", []):
                aweme_id = ad.get("aweme_id", "")
                if not aweme_id:
                    continue
                ad_id = f"tt_{aweme_id}"
                if db.query(Ad).filter(Ad.ad_id == ad_id).first():
                    continue

                create_time = ad.get("create_time", 0)
                start_date = datetime.fromtimestamp(create_time) if create_time else None

                new_ad = Ad(
                    competitor_id=comp.id,
                    ad_id=ad_id,
                    platform="tiktok",
                    creative_url=ad.get("cover_url", ""),
                    ad_text=ad.get("description", ""),
                    start_date=start_date,
                    is_active=True,
                    impressions_min=ad.get("play_count", 0),
                    impressions_max=ad.get("play_count", 0),
                    publisher_platforms=json.dumps(["TIKTOK"]),
                    page_name=ad.get("author_nickname", ""),
                    page_id=ad.get("author_id", ""),
                    page_profile_uri=f"https://www.tiktok.com/@{ad.get('author_username', '')}",
                    page_profile_picture_url=ad.get("author_avatar", ""),
                    display_format="VIDEO",
                    ad_library_url=f"https://www.tiktok.com/@{ad.get('author_username', '')}/video/{aweme_id}",
                    title=ad.get("description", "")[:200] if ad.get("description") else None,
                    estimated_spend_min=ad.get("like_count", 0),
                    estimated_spend_max=ad.get("share_count", 0),
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
        "message": "TikTok ads fetch complete",
        "results": results,
    }


def _serialize_tiktok_ad(ad: Ad) -> dict:
    """Serialize a TikTok ad to JSON-friendly dict."""
    return {
        "id": ad.id,
        "competitor_id": ad.competitor_id,
        "ad_id": ad.ad_id,
        "platform": "tiktok",
        "creative_url": ad.creative_url,
        "ad_text": ad.ad_text,
        "title": ad.title,
        "start_date": ad.start_date.isoformat() if ad.start_date else None,
        "is_active": ad.is_active,
        "views": ad.impressions_min or 0,
        "likes": int(ad.estimated_spend_min or 0),
        "shares": int(ad.estimated_spend_max or 0),
        "page_name": ad.page_name,
        "page_id": ad.page_id,
        "page_profile_uri": ad.page_profile_uri,
        "page_profile_picture_url": ad.page_profile_picture_url,
        "display_format": ad.display_format,
        "ad_library_url": ad.ad_library_url,
    }
