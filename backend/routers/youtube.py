"""
YouTube API router.
Endpoints for fetching and analyzing YouTube channel data.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime, timedelta

from database import get_db, Competitor, YouTubeData, User
from models.schemas import YouTubeDataResponse, TrendResponse
from services.youtube_api import youtube_api
from core.trends import calculate_trend
from core.auth import get_current_user
from core.permissions import verify_competitor_ownership, get_user_competitors, parse_advertiser_header

router = APIRouter()


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/data/{competitor_id}")
async def get_youtube_history(
    competitor_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get historical YouTube data for a competitor."""
    verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))
    return (
        db.query(YouTubeData)
        .filter(YouTubeData.competitor_id == competitor_id)
        .order_by(desc(YouTubeData.recorded_at))
        .limit(limit)
        .all()
    )


@router.get("/latest/{competitor_id}")
async def get_latest_youtube_data(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get the latest YouTube data for a competitor."""
    verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))
    data = (
        db.query(YouTubeData)
        .filter(YouTubeData.competitor_id == competitor_id)
        .order_by(desc(YouTubeData.recorded_at))
        .first()
    )
    if not data:
        raise HTTPException(status_code=404, detail="No YouTube data found")
    return data


@router.post("/fetch/{competitor_id}")
async def fetch_youtube_data(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Fetch and store current YouTube data for a competitor."""
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))

    if not competitor.youtube_channel_id:
        raise HTTPException(status_code=400, detail="No YouTube channel ID configured")

    result = await youtube_api.get_channel_analytics(competitor.youtube_channel_id)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Fetch failed: {result.get('error')}")

    analytics = result.get("analytics", {})

    youtube_data = YouTubeData(
        competitor_id=competitor_id,
        channel_id=competitor.youtube_channel_id,
        channel_name=result.get("channel_name"),
        subscribers=result.get("subscribers", 0),
        total_views=result.get("total_views", 0),
        videos_count=result.get("videos_count", 0),
        avg_views=analytics.get("avg_views", 0),
        avg_likes=analytics.get("avg_likes", 0),
        avg_comments=analytics.get("avg_comments", 0),
        engagement_rate=analytics.get("engagement_rate", 0),
        description=result.get("description")
    )
    db.add(youtube_data)
    db.commit()
    db.refresh(youtube_data)

    return {
        "message": "YouTube data fetched successfully",
        "data": {
            "channel_name": youtube_data.channel_name,
            "subscribers": youtube_data.subscribers,
            "total_views": youtube_data.total_views,
            "videos_count": youtube_data.videos_count,
            "engagement_rate": youtube_data.engagement_rate
        }
    }


@router.get("/comparison")
async def compare_youtube_channels(
    days: int = 7,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Compare YouTube metrics across all tracked competitors."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = [
        c for c in get_user_competitors(db, user, advertiser_id=adv_id)
        if c.youtube_channel_id or getattr(c, "is_brand", False)
    ]

    comparison = []
    for competitor in competitors:
        latest = (
            db.query(YouTubeData)
            .filter(YouTubeData.competitor_id == competitor.id)
            .order_by(desc(YouTubeData.recorded_at))
            .first()
        )

        if latest:
            # Get data from N days ago for growth calculation
            week_ago = datetime.utcnow() - timedelta(days=days)
            old_data = (
                db.query(YouTubeData)
                .filter(
                    YouTubeData.competitor_id == competitor.id,
                    YouTubeData.recorded_at <= week_ago,
                )
                .order_by(desc(YouTubeData.recorded_at))
                .first()
            )

            subscriber_growth = None
            if old_data and old_data.subscribers and old_data.subscribers > 0:
                subscriber_growth = round(((latest.subscribers - old_data.subscribers) / old_data.subscribers) * 100, 2)

            comparison.append({
                "competitor_id": competitor.id,
                "competitor_name": competitor.name,
                "channel_id": competitor.youtube_channel_id,
                "channel_name": latest.channel_name,
                "subscribers": latest.subscribers,
                "total_views": latest.total_views,
                "videos_count": latest.videos_count,
                "avg_views": latest.avg_views,
                "avg_likes": latest.avg_likes,
                "avg_comments": latest.avg_comments,
                "engagement_rate": latest.engagement_rate,
                "subscriber_growth_7d": subscriber_growth,
                "recorded_at": latest.recorded_at.isoformat(),
            })
        elif getattr(competitor, "is_brand", False):
            # Always include the brand even without data
            comparison.append({
                "competitor_id": competitor.id,
                "competitor_name": competitor.name,
                "channel_id": competitor.youtube_channel_id,
                "channel_name": competitor.name,
                "subscribers": 0,
                "total_views": 0,
                "videos_count": 0,
                "avg_views": 0,
                "avg_likes": 0,
                "avg_comments": 0,
                "engagement_rate": 0,
                "subscriber_growth_7d": 0,
                "recorded_at": None,
            })

    comparison.sort(key=lambda x: x["subscribers"] or 0, reverse=True)
    return comparison


@router.get("/trends/{competitor_id}")
async def get_youtube_trends(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get YouTube trends and variations for a competitor."""
    verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))
    recent_data = (
        db.query(YouTubeData)
        .filter(YouTubeData.competitor_id == competitor_id)
        .order_by(desc(YouTubeData.recorded_at))
        .limit(2)
        .all()
    )

    if not recent_data:
        raise HTTPException(status_code=404, detail="No YouTube data found")

    current = recent_data[0]
    previous = recent_data[1] if len(recent_data) > 1 else None

    current_data = {
        "subscribers": current.subscribers,
        "total_views": current.total_views,
        "videos_count": current.videos_count
    }

    if previous:
        previous_data = {
            "subscribers": previous.subscribers,
            "total_views": previous.total_views,
            "videos_count": previous.videos_count
        }
        trends = {
            "subscribers": calculate_trend(current.subscribers, previous.subscribers),
            "views": calculate_trend(current.total_views, previous.total_views),
            "videos": calculate_trend(current.videos_count, previous.videos_count)
        }
    else:
        previous_data = None
        trends = {
            "subscribers": calculate_trend(None, None),
            "views": calculate_trend(None, None),
            "videos": calculate_trend(None, None)
        }

    return TrendResponse(current=current_data, previous=previous_data, trends=trends)


@router.get("/videos/{competitor_id}")
async def get_recent_videos(
    competitor_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get recent YouTube videos for a competitor."""
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))

    if not competitor.youtube_channel_id:
        raise HTTPException(status_code=400, detail="No YouTube channel ID configured")

    result = await youtube_api.fetch_recent_videos(
        competitor.youtube_channel_id,
        max_results=limit
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Fetch failed: {result.get('error')}")

    return result


@router.get("/search")
async def search_youtube_channels(
    query: str,
    limit: int = 10,
    user: User = Depends(get_current_user),
):
    """Search for YouTube channels."""
    result = await youtube_api.search_channels(query, max_results=limit)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Search failed: {result.get('error')}")

    return result


@router.get("/channel/{channel_id}")
async def get_channel_info(
    channel_id: str,
    user: User = Depends(get_current_user),
):
    """Get detailed information about a YouTube channel."""
    result = await youtube_api.get_channel_analytics(channel_id)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Fetch failed: {result.get('error')}")

    return result
