"""
Admin backoffice router.
Platform stats accessible to all authenticated users (scoped to their data).
User management restricted to admins.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    get_db, User, Advertiser, Competitor,
    Ad, InstagramData, TikTokData, YouTubeData, AppData, StoreLocation,
)
from core.auth import get_current_user, get_admin_user
from services.scheduler import scheduler

router = APIRouter()


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Platform statistics scoped to the current user."""
    # User's competitors
    user_comp_ids = [
        row[0] for row in
        db.query(Competitor.id).filter(
            Competitor.user_id == user.id, Competitor.is_active == True
        ).all()
    ]

    total_brands = db.query(func.count(Advertiser.id)).filter(
        Advertiser.user_id == user.id, Advertiser.is_active == True
    ).scalar()
    total_competitors = len(user_comp_ids)

    # Data volume scoped to user's competitors
    if user_comp_ids:
        total_ads = db.query(func.count(Ad.id)).filter(Ad.competitor_id.in_(user_comp_ids)).scalar()
        total_instagram = db.query(func.count(InstagramData.id)).filter(InstagramData.competitor_id.in_(user_comp_ids)).scalar()
        total_tiktok = db.query(func.count(TikTokData.id)).filter(TikTokData.competitor_id.in_(user_comp_ids)).scalar()
        total_youtube = db.query(func.count(YouTubeData.id)).filter(YouTubeData.competitor_id.in_(user_comp_ids)).scalar()
        total_apps = db.query(func.count(AppData.id)).filter(AppData.competitor_id.in_(user_comp_ids)).scalar()
        total_stores = db.query(func.count(StoreLocation.id)).filter(StoreLocation.competitor_id.in_(user_comp_ids)).scalar()
    else:
        total_ads = total_instagram = total_tiktok = total_youtube = total_apps = total_stores = 0

    return {
        "brands": total_brands,
        "competitors": total_competitors,
        "data_volume": {
            "ads": total_ads,
            "instagram_records": total_instagram,
            "tiktok_records": total_tiktok,
            "youtube_records": total_youtube,
            "app_records": total_apps,
            "store_locations": total_stores,
        },
        "scheduler": scheduler.get_status(),
    }


@router.get("/users")
async def list_users(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """List all users with their brand/competitor info."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        brand = db.query(Advertiser).filter(
            Advertiser.user_id == u.id, Advertiser.is_active == True
        ).first()
        competitors_count = db.query(func.count(Competitor.id)).filter(
            Competitor.user_id == u.id, Competitor.is_active == True
        ).scalar()
        result.append({
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "has_brand": brand is not None,
            "brand_name": brand.company_name if brand else None,
            "competitors_count": competitors_count,
        })
    return result
