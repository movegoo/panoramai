"""
App Store API router.
Endpoints for fetching and analyzing Apple App Store data.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime, timedelta
import httpx

from database import get_db, Competitor, AppData, User
from models.schemas import AppDataResponse, TrendResponse
from core.trends import calculate_trend
from core.auth import get_optional_user

router = APIRouter()

ITUNES_LOOKUP_API = "https://itunes.apple.com/lookup"
ITUNES_REVIEWS_API = "https://itunes.apple.com/fr/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"


# =============================================================================
# Data Fetching
# =============================================================================

async def fetch_appstore_app(app_id: str) -> dict:
    """Fetch app data from App Store using iTunes API."""
    try:
        async with httpx.AsyncClient() as client:
            # Fetch app details
            response = await client.get(ITUNES_LOOKUP_API, params={"id": app_id, "country": "fr"})
            data = response.json()

            if not data.get("results"):
                return {"success": False, "error": "App not found"}

            app_info = data["results"][0]

            # Fetch reviews
            reviews_response = await client.get(ITUNES_REVIEWS_API.format(app_id=app_id))
            reviews_data = reviews_response.json()

            reviews = []
            if "feed" in reviews_data and "entry" in reviews_data["feed"]:
                for entry in reviews_data["feed"]["entry"][:10]:
                    if isinstance(entry, dict) and "im:rating" in entry:
                        reviews.append({
                            "score": int(entry.get("im:rating", {}).get("label", 0)),
                            "title": entry.get("title", {}).get("label", ""),
                            "content": entry.get("content", {}).get("label", ""),
                            "author": entry.get("author", {}).get("name", {}).get("label", "")
                        })

            last_updated = None
            if app_info.get("currentVersionReleaseDate"):
                try:
                    last_updated = datetime.fromisoformat(
                        app_info["currentVersionReleaseDate"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            return {
                "success": True,
                "app_name": app_info.get("trackName"),
                "rating": app_info.get("averageUserRating"),
                "reviews_count": app_info.get("userRatingCount"),
                "version": app_info.get("version"),
                "last_updated": last_updated,
                "description": app_info.get("description"),
                "changelog": app_info.get("releaseNotes"),
                "developer": app_info.get("artistName"),
                "genre": app_info.get("primaryGenreName"),
                "price": app_info.get("price"),
                "recent_reviews": reviews
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/data/{competitor_id}")
async def get_appstore_history(
    competitor_id: int,
    limit: int = 30,
    db: Session = Depends(get_db)
):
    """Get historical App Store data for a competitor."""
    return (
        db.query(AppData)
        .filter(AppData.competitor_id == competitor_id, AppData.store == "appstore")
        .order_by(desc(AppData.recorded_at))
        .limit(limit)
        .all()
    )


@router.get("/latest/{competitor_id}")
async def get_latest_appstore_data(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """Get the latest App Store data for a competitor."""
    data = (
        db.query(AppData)
        .filter(AppData.competitor_id == competitor_id, AppData.store == "appstore")
        .order_by(desc(AppData.recorded_at))
        .first()
    )
    if not data:
        raise HTTPException(status_code=404, detail="No App Store data found")
    return data


@router.post("/fetch/{competitor_id}")
async def fetch_appstore_data(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """Fetch and store current App Store data for a competitor."""
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    if not competitor.appstore_app_id:
        raise HTTPException(status_code=400, detail="No App Store app ID configured")

    result = await fetch_appstore_app(competitor.appstore_app_id)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Fetch failed: {result.get('error')}")

    app_data = AppData(
        competitor_id=competitor_id,
        store="appstore",
        app_id=competitor.appstore_app_id,
        app_name=result["app_name"],
        rating=result["rating"],
        reviews_count=result["reviews_count"],
        downloads=None,  # App Store doesn't expose download counts
        version=result["version"],
        last_updated=result["last_updated"],
        description=result["description"],
        changelog=result["changelog"]
    )
    db.add(app_data)
    db.commit()
    db.refresh(app_data)

    return {
        "message": "App Store data fetched successfully",
        "data": {
            "app_name": app_data.app_name,
            "rating": app_data.rating,
            "reviews_count": app_data.reviews_count,
            "version": app_data.version
        }
    }


@router.get("/comparison")
async def compare_appstore_apps(
    days: int = 7,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Compare App Store metrics across all tracked competitors."""
    query = (
        db.query(Competitor)
        .filter(Competitor.appstore_app_id.isnot(None), Competitor.is_active == True)
    )
    if user:
        query = query.filter(Competitor.user_id == user.id)
    competitors = query.all()

    comparison = []
    for competitor in competitors:
        latest = (
            db.query(AppData)
            .filter(AppData.competitor_id == competitor.id, AppData.store == "appstore")
            .order_by(desc(AppData.recorded_at))
            .first()
        )

        if latest:
            cutoff = datetime.utcnow() - timedelta(days=days)
            old = (
                db.query(AppData)
                .filter(AppData.competitor_id == competitor.id, AppData.store == "appstore", AppData.recorded_at <= cutoff)
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
                "app_id": competitor.appstore_app_id,
                "app_name": latest.app_name,
                "rating": latest.rating,
                "reviews_count": latest.reviews_count,
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
    db: Session = Depends(get_db)
):
    """Get recent reviews for a competitor's App Store app."""
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    if not competitor.appstore_app_id:
        raise HTTPException(status_code=400, detail="No App Store app ID configured")

    result = await fetch_appstore_app(competitor.appstore_app_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Fetch failed: {result.get('error')}")

    return {
        "app_name": result["app_name"],
        "reviews": result.get("recent_reviews", [])
    }


@router.get("/search")
async def search_appstore(query: str, limit: int = 10):
    """Search for apps on the App Store."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://itunes.apple.com/search",
                params={"term": query, "country": "fr", "media": "software", "limit": limit}
            )
            data = response.json()

            return [
                {
                    "app_id": app.get("trackId"),
                    "app_name": app.get("trackName"),
                    "developer": app.get("artistName"),
                    "rating": app.get("averageUserRating"),
                    "icon_url": app.get("artworkUrl100"),
                    "genre": app.get("primaryGenreName")
                }
                for app in data.get("results", [])
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends/{competitor_id}")
async def get_appstore_trends(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """
    Get App Store trends and variations for a competitor.

    Returns current metrics, previous metrics, and trend indicators.
    """
    recent_data = (
        db.query(AppData)
        .filter(AppData.competitor_id == competitor_id, AppData.store == "appstore")
        .order_by(desc(AppData.recorded_at))
        .limit(2)
        .all()
    )

    if not recent_data:
        raise HTTPException(status_code=404, detail="No App Store data found")

    current = recent_data[0]
    previous = recent_data[1] if len(recent_data) > 1 else None

    current_data = {
        "rating": current.rating,
        "reviews_count": current.reviews_count,
        "version": current.version
    }

    if previous:
        previous_data = {
            "rating": previous.rating,
            "reviews_count": previous.reviews_count,
            "version": previous.version
        }

        trends = {
            "rating": calculate_trend(current.rating, previous.rating),
            "reviews": calculate_trend(current.reviews_count, previous.reviews_count)
        }
    else:
        previous_data = None
        trends = {
            "rating": calculate_trend(None, None),
            "reviews": calculate_trend(None, None)
        }

    return TrendResponse(current=current_data, previous=previous_data, trends=trends)
