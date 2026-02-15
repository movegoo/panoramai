"""
Play Store API router.
Endpoints for fetching and analyzing Google Play Store app data.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime, timedelta
import asyncio

from database import get_db, Competitor, AppData, User
from models.schemas import AppDataResponse, TrendResponse
from core.trends import calculate_trend, parse_download_count
from core.auth import get_current_user
from core.permissions import verify_competitor_ownership, get_user_competitors, parse_advertiser_header

router = APIRouter()


def _auto_patch_from_db(competitor, db):
    """Auto-fill missing fields from the built-in competitor database."""
    from routers.advertiser import COMPETITORS_BY_SECTOR
    for comps in COMPETITORS_BY_SECTOR.values():
        for ref in comps:
            if ref["name"].lower() == competitor.name.lower():
                changed = False
                for f in ["playstore_app_id", "appstore_app_id", "instagram_username",
                          "tiktok_username", "youtube_channel_id", "website"]:
                    if ref.get(f) and not getattr(competitor, f, None):
                        setattr(competitor, f, ref[f])
                        changed = True
                if changed:
                    db.commit()
                return
    return


# =============================================================================
# Data Fetching
# =============================================================================

def fetch_playstore_app(app_id: str) -> dict:
    """Fetch app data from Google Play Store."""
    try:
        from google_play_scraper import app, reviews

        result = app(app_id, lang='fr', country='fr')
        app_reviews, _ = reviews(app_id, lang='fr', country='fr', count=100)

        last_updated = None
        if result.get('updated'):
            try:
                last_updated = datetime.fromtimestamp(result['updated'])
            except (ValueError, TypeError):
                pass

        return {
            "success": True,
            "app_name": result.get('title'),
            "rating": result.get('score'),
            "reviews_count": result.get('ratings'),
            "downloads": result.get('installs'),
            "version": result.get('version'),
            "last_updated": last_updated,
            "description": result.get('description'),
            "changelog": result.get('recentChanges'),
            "developer": result.get('developer'),
            "genre": result.get('genre'),
            "recent_reviews": [
                {
                    "score": r.get('score'),
                    "content": r.get('content'),
                    "date": r.get('at').isoformat() if r.get('at') else None
                }
                for r in app_reviews[:10]
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def async_fetch_playstore(app_id: str) -> dict:
    """Run the synchronous Play Store fetch in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fetch_playstore_app, app_id)


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/data/{competitor_id}")
async def get_playstore_history(
    competitor_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get historical Play Store data for a competitor."""
    verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))
    return (
        db.query(AppData)
        .filter(AppData.competitor_id == competitor_id, AppData.store == "playstore")
        .order_by(desc(AppData.recorded_at))
        .limit(limit)
        .all()
    )


@router.get("/latest/{competitor_id}")
async def get_latest_playstore_data(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get the latest Play Store data for a competitor."""
    verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))
    data = (
        db.query(AppData)
        .filter(AppData.competitor_id == competitor_id, AppData.store == "playstore")
        .order_by(desc(AppData.recorded_at))
        .first()
    )
    if not data:
        raise HTTPException(status_code=404, detail="No Play Store data found")
    return data


@router.post("/fetch/{competitor_id}")
async def fetch_playstore_data(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Fetch and store current Play Store data for a competitor."""
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))

    if not competitor.playstore_app_id:
        _auto_patch_from_db(competitor, db)

    if not competitor.playstore_app_id:
        raise HTTPException(status_code=400, detail="No Play Store app ID configured")

    result = await async_fetch_playstore(competitor.playstore_app_id)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Fetch failed: {result.get('error')}")

    downloads_numeric = parse_download_count(result["downloads"])

    app_data = AppData(
        competitor_id=competitor_id,
        store="playstore",
        app_id=competitor.playstore_app_id,
        app_name=result["app_name"],
        rating=result["rating"],
        reviews_count=result["reviews_count"],
        downloads=result["downloads"],
        downloads_numeric=downloads_numeric,
        version=result["version"],
        last_updated=result["last_updated"],
        description=result["description"],
        changelog=result["changelog"]
    )
    db.add(app_data)
    db.commit()
    db.refresh(app_data)

    return {
        "message": "Play Store data fetched successfully",
        "data": {
            "app_name": app_data.app_name,
            "rating": app_data.rating,
            "reviews_count": app_data.reviews_count,
            "downloads": app_data.downloads,
            "version": app_data.version
        }
    }


@router.get("/comparison")
async def compare_playstore_apps(
    days: int = 7,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Compare Play Store metrics across all tracked competitors."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = [
        c for c in get_user_competitors(db, user, advertiser_id=adv_id)
        if c.playstore_app_id is not None and c.is_active
    ]

    comparison = []
    for competitor in competitors:
        latest = (
            db.query(AppData)
            .filter(AppData.competitor_id == competitor.id, AppData.store == "playstore")
            .order_by(desc(AppData.recorded_at))
            .first()
        )

        if latest:
            # Growth calculation over N days
            cutoff = datetime.utcnow() - timedelta(days=days)
            old = (
                db.query(AppData)
                .filter(AppData.competitor_id == competitor.id, AppData.store == "playstore", AppData.recorded_at <= cutoff)
                .order_by(desc(AppData.recorded_at))
                .first()
            )
            rating_growth = None
            reviews_growth = None
            if old and old.rating and latest.rating:
                rating_growth = round(latest.rating - old.rating, 2)
            if old and old.reviews_count and latest.reviews_count:
                reviews_growth = latest.reviews_count - old.reviews_count

            comparison.append({
                "competitor_id": competitor.id,
                "competitor_name": competitor.name,
                "app_id": competitor.playstore_app_id,
                "app_name": latest.app_name,
                "rating": latest.rating,
                "reviews_count": latest.reviews_count,
                "downloads": latest.downloads,
                "downloads_numeric": latest.downloads_numeric,
                "version": latest.version,
                "last_updated": latest.last_updated.isoformat() if latest.last_updated else None,
                "recorded_at": latest.recorded_at.isoformat(),
                "rating_growth": rating_growth,
                "reviews_growth": reviews_growth,
            })

    comparison.sort(key=lambda x: x["rating"] or 0, reverse=True)
    return comparison


@router.get("/reviews/{competitor_id}")
async def get_recent_reviews(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Get recent reviews for a competitor's Play Store app."""
    competitor = verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))

    if not competitor.playstore_app_id:
        _auto_patch_from_db(competitor, db)

    if not competitor.playstore_app_id:
        raise HTTPException(status_code=400, detail="No Play Store app ID configured")

    result = await async_fetch_playstore(competitor.playstore_app_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Fetch failed: {result.get('error')}")

    return {
        "app_name": result["app_name"],
        "reviews": result.get("recent_reviews", [])
    }


@router.get("/trends/{competitor_id}")
async def get_playstore_trends(
    competitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Get Play Store trends and variations for a competitor.

    Returns current metrics, previous metrics, and trend indicators.
    """
    verify_competitor_ownership(db, competitor_id, user, advertiser_id=parse_advertiser_header(x_advertiser_id))
    recent_data = (
        db.query(AppData)
        .filter(AppData.competitor_id == competitor_id, AppData.store == "playstore")
        .order_by(desc(AppData.recorded_at))
        .limit(2)
        .all()
    )

    if not recent_data:
        raise HTTPException(status_code=404, detail="No Play Store data found")

    current = recent_data[0]
    previous = recent_data[1] if len(recent_data) > 1 else None

    current_downloads = current.downloads_numeric or parse_download_count(current.downloads)

    current_data = {
        "rating": current.rating,
        "reviews_count": current.reviews_count,
        "downloads": current.downloads,
        "downloads_numeric": current_downloads
    }

    if previous:
        previous_downloads = previous.downloads_numeric or parse_download_count(previous.downloads)

        previous_data = {
            "rating": previous.rating,
            "reviews_count": previous.reviews_count,
            "downloads": previous.downloads,
            "downloads_numeric": previous_downloads
        }

        trends = {
            "rating": calculate_trend(current.rating, previous.rating),
            "reviews": calculate_trend(current.reviews_count, previous.reviews_count),
            "downloads": calculate_trend(current_downloads, previous_downloads)
        }
    else:
        previous_data = None
        trends = {
            "rating": calculate_trend(None, None),
            "reviews": calculate_trend(None, None),
            "downloads": calculate_trend(None, None)
        }

    return TrendResponse(current=current_data, previous=previous_data, trends=trends)
