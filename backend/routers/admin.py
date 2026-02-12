"""
Admin backoffice router.
Platform stats and user management, restricted to admins.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    get_db, User, Advertiser, Competitor,
    Ad, InstagramData, TikTokData, YouTubeData, AppData, StoreLocation,
)
from core.auth import get_admin_user
from services.scheduler import scheduler

router = APIRouter()


@router.get("/stats")
async def get_stats(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Global platform statistics."""
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()
    total_brands = db.query(func.count(Advertiser.id)).filter(Advertiser.is_active == True).scalar()
    total_competitors = db.query(func.count(Competitor.id)).filter(Competitor.is_active == True).scalar()

    total_ads = db.query(func.count(Ad.id)).scalar()
    total_instagram = db.query(func.count(InstagramData.id)).scalar()
    total_tiktok = db.query(func.count(TikTokData.id)).scalar()
    total_youtube = db.query(func.count(YouTubeData.id)).scalar()
    total_apps = db.query(func.count(AppData.id)).scalar()
    total_stores = db.query(func.count(StoreLocation.id)).scalar()

    return {
        "users": {"total": total_users, "active": active_users},
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
