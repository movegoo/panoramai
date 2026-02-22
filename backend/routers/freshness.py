"""
Freshness router — exposes data freshness (last updated timestamps) per source.
"""
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    get_db, User, Competitor, AdvertiserCompetitor, UserAdvertiser,
    InstagramData, TikTokData, YouTubeData, AppData, Ad,
)
from core.auth import get_current_user
from core.permissions import parse_advertiser_header

router = APIRouter()


def _get_competitor_ids(db: Session, user: User, x_advertiser_id: str | None) -> list[int]:
    """Get competitor IDs scoped to the user/advertiser."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    if adv_id:
        rows = (
            db.query(AdvertiserCompetitor.competitor_id)
            .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
            .filter(AdvertiserCompetitor.advertiser_id == adv_id, Competitor.is_active == True)
            .all()
        )
    else:
        user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(UserAdvertiser.user_id == user.id).all()]
        if not user_adv_ids:
            return []
        rows = (
            db.query(AdvertiserCompetitor.competitor_id)
            .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
            .filter(AdvertiserCompetitor.advertiser_id.in_(user_adv_ids), Competitor.is_active == True)
            .all()
        )
    return [r[0] for r in rows]


@router.get("")
async def get_freshness(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_advertiser_id: str | None = Header(None),
):
    """Return the latest recorded_at per data source for the user's competitors."""
    comp_ids = _get_competitor_ids(db, user, x_advertiser_id)
    if not comp_ids:
        return {
            "instagram": None,
            "tiktok": None,
            "youtube": None,
            "playstore": None,
            "appstore": None,
            "ads_meta": None,
            "ads_google": None,
            "ads_snapchat": None,
        }

    def _max_ts(model, extra_filter=None):
        q = db.query(func.max(model.recorded_at)).filter(model.competitor_id.in_(comp_ids))
        if extra_filter is not None:
            q = q.filter(extra_filter)
        val = q.scalar()
        return val.isoformat() if val else None

    # Ads don't have recorded_at — use created_at
    def _max_ad_ts(platform_filter):
        val = (
            db.query(func.max(Ad.created_at))
            .filter(Ad.competitor_id.in_(comp_ids))
            .filter(platform_filter)
            .scalar()
        )
        return val.isoformat() if val else None

    return {
        "instagram": _max_ts(InstagramData),
        "tiktok": _max_ts(TikTokData),
        "youtube": _max_ts(YouTubeData),
        "playstore": _max_ts(AppData, AppData.store == "playstore"),
        "appstore": _max_ts(AppData, AppData.store == "appstore"),
        "ads_meta": _max_ad_ts(Ad.platform.in_(["facebook", "instagram"])),
        "ads_google": _max_ad_ts(Ad.platform == "google"),
        "ads_snapchat": _max_ad_ts(Ad.platform == "snapchat"),
    }
