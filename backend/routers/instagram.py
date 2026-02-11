from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime, timedelta

from database import get_db, Competitor, InstagramData
from models.schemas import InstagramDataResponse
from services.scrapecreators import scrapecreators

router = APIRouter()


@router.get("/data/{competitor_id}", response_model=List[InstagramDataResponse])
async def get_instagram_history(
    competitor_id: int,
    limit: int = 30,
    db: Session = Depends(get_db)
):
    """Get historical Instagram data for a competitor"""
    return db.query(InstagramData).filter(
        InstagramData.competitor_id == competitor_id
    ).order_by(desc(InstagramData.recorded_at)).limit(limit).all()


@router.get("/latest/{competitor_id}", response_model=InstagramDataResponse)
async def get_latest_instagram_data(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """Get the latest Instagram data for a competitor"""
    data = db.query(InstagramData).filter(
        InstagramData.competitor_id == competitor_id
    ).order_by(desc(InstagramData.recorded_at)).first()

    if not data:
        raise HTTPException(status_code=404, detail="No Instagram data found")
    return data


@router.post("/fetch/{competitor_id}")
async def fetch_instagram_data(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """Fetch and store current Instagram data for a competitor"""
    competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    if not competitor.instagram_username:
        raise HTTPException(
            status_code=400,
            detail="Competitor has no Instagram username configured"
        )

    # Check rate limiting - don't fetch more than once per hour
    last_fetch = db.query(InstagramData).filter(
        InstagramData.competitor_id == competitor_id
    ).order_by(desc(InstagramData.recorded_at)).first()

    if last_fetch and (datetime.utcnow() - last_fetch.recorded_at) < timedelta(hours=1):
        return {
            "message": "Data was fetched recently. Please wait before fetching again.",
            "last_fetch": last_fetch.recorded_at.isoformat(),
            "cached": True
        }

    result = await scrapecreators.fetch_instagram_profile(competitor.instagram_username)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch Instagram data: {result.get('error')}"
        )

    instagram_data = InstagramData(
        competitor_id=competitor_id,
        followers=result["followers"],
        following=result["following"],
        posts_count=result["posts_count"],
        avg_likes=result["avg_likes"],
        avg_comments=result["avg_comments"],
        engagement_rate=result["engagement_rate"],
        bio=result["bio"]
    )
    db.add(instagram_data)
    db.commit()
    db.refresh(instagram_data)

    return {
        "message": "Instagram data fetched successfully",
        "data": {
            "followers": instagram_data.followers,
            "following": instagram_data.following,
            "posts_count": instagram_data.posts_count,
            "engagement_rate": instagram_data.engagement_rate
        }
    }


@router.get("/comparison")
async def compare_instagram_accounts(db: Session = Depends(get_db)):
    """Compare Instagram metrics across all tracked competitors"""
    competitors = db.query(Competitor).filter(
        Competitor.instagram_username.isnot(None),
        Competitor.is_active == True
    ).all()

    comparison = []
    for competitor in competitors:
        latest = db.query(InstagramData).filter(
            InstagramData.competitor_id == competitor.id
        ).order_by(desc(InstagramData.recorded_at)).first()

        if latest:
            # Get data from 7 days ago for growth calculation
            week_ago = datetime.utcnow() - timedelta(days=7)
            old_data = db.query(InstagramData).filter(
                InstagramData.competitor_id == competitor.id,
                InstagramData.recorded_at <= week_ago
            ).order_by(desc(InstagramData.recorded_at)).first()

            follower_growth = 0
            if old_data and old_data.followers > 0:
                follower_growth = ((latest.followers - old_data.followers) / old_data.followers) * 100

            comparison.append({
                "competitor_id": competitor.id,
                "competitor_name": competitor.name,
                "username": competitor.instagram_username,
                "followers": latest.followers,
                "engagement_rate": latest.engagement_rate,
                "posts_count": latest.posts_count,
                "follower_growth_7d": round(follower_growth, 2),
                "last_updated": latest.recorded_at.isoformat()
            })

    # Sort by followers descending
    comparison.sort(key=lambda x: x["followers"], reverse=True)
    return comparison
