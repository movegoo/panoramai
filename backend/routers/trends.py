"""
Trends API — Time-series data for all metrics across competitors.
Powers the Tendances dashboard with historical evolution data.
"""
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, cast, Float
from typing import Optional
from datetime import datetime, timedelta
import json
import logging

from database import (
    get_db, Competitor, Ad, InstagramData, TikTokData,
    YouTubeData, AppData, AdSnapshot, User,
)
from core.auth import get_current_user
from core.permissions import get_user_competitors, get_user_competitor_ids, parse_advertiser_header

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_date(d: str | None) -> datetime | None:
    if not d:
        return None
    try:
        return datetime.fromisoformat(d)
    except (ValueError, TypeError):
        return None


@router.get("/timeseries")
async def get_timeseries(
    date_from: Optional[str] = Query(None, description="ISO date start"),
    date_to: Optional[str] = Query(None, description="ISO date end"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Return all time-series metrics for every competitor.
    Each competitor gets arrays of {date, value} for every tracked metric.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)
    comp_ids = [c.id for c in competitors]
    comp_map = {c.id: {"name": c.name, "is_brand": c.is_brand, "logo_url": c.logo_url} for c in competitors}

    start = _parse_date(date_from) or (datetime.utcnow() - timedelta(days=30))
    end = _parse_date(date_to) or datetime.utcnow()

    result = {}

    for comp_id, info in comp_map.items():
        comp_data = {
            "name": info["name"],
            "is_brand": info["is_brand"],
            "logo_url": info["logo_url"],
            "instagram": _get_instagram_series(db, comp_id, start, end),
            "tiktok": _get_tiktok_series(db, comp_id, start, end),
            "youtube": _get_youtube_series(db, comp_id, start, end),
            "playstore": _get_app_series(db, comp_id, "playstore", start, end),
            "appstore": _get_app_series(db, comp_id, "appstore", start, end),
            "ads": _get_ads_series(db, comp_id, start, end),
            "snapchat": _get_snapchat_series(db, comp_id, start, end),
        }
        result[str(comp_id)] = comp_data

    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "competitors": result,
    }


@router.get("/summary")
async def get_trends_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Compact summary: latest values + deltas for each competitor/metric.
    Designed for the overview cards (no full timeseries).
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)
    comp_ids = [c.id for c in competitors]

    end = _parse_date(date_to) or datetime.utcnow()
    start = _parse_date(date_from) or (end - timedelta(days=7))

    summaries = []
    for comp in competitors:
        metrics = _compute_deltas(db, comp.id, start, end)
        summaries.append({
            "competitor_id": comp.id,
            "name": comp.name,
            "is_brand": comp.is_brand,
            "logo_url": comp.logo_url,
            "metrics": metrics,
        })

    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "competitors": summaries,
    }


# ─── Time-series builders ───────────────────────────────────────────

def _get_instagram_series(db: Session, comp_id: int, start: datetime, end: datetime) -> dict:
    rows = (
        db.query(InstagramData)
        .filter(
            InstagramData.competitor_id == comp_id,
            InstagramData.recorded_at >= start,
            InstagramData.recorded_at <= end,
        )
        .order_by(InstagramData.recorded_at)
        .all()
    )
    return {
        "followers": [{"date": r.recorded_at.isoformat(), "value": r.followers} for r in rows],
        "engagement_rate": [{"date": r.recorded_at.isoformat(), "value": r.engagement_rate} for r in rows],
        "posts_count": [{"date": r.recorded_at.isoformat(), "value": r.posts_count} for r in rows],
        "avg_likes": [{"date": r.recorded_at.isoformat(), "value": r.avg_likes} for r in rows],
        "avg_comments": [{"date": r.recorded_at.isoformat(), "value": r.avg_comments} for r in rows],
    }


def _get_tiktok_series(db: Session, comp_id: int, start: datetime, end: datetime) -> dict:
    rows = (
        db.query(TikTokData)
        .filter(
            TikTokData.competitor_id == comp_id,
            TikTokData.recorded_at >= start,
            TikTokData.recorded_at <= end,
        )
        .order_by(TikTokData.recorded_at)
        .all()
    )
    return {
        "followers": [{"date": r.recorded_at.isoformat(), "value": r.followers} for r in rows],
        "likes": [{"date": r.recorded_at.isoformat(), "value": r.likes} for r in rows],
        "videos_count": [{"date": r.recorded_at.isoformat(), "value": r.videos_count} for r in rows],
    }


def _get_youtube_series(db: Session, comp_id: int, start: datetime, end: datetime) -> dict:
    rows = (
        db.query(YouTubeData)
        .filter(
            YouTubeData.competitor_id == comp_id,
            YouTubeData.recorded_at >= start,
            YouTubeData.recorded_at <= end,
        )
        .order_by(YouTubeData.recorded_at)
        .all()
    )
    return {
        "subscribers": [{"date": r.recorded_at.isoformat(), "value": r.subscribers} for r in rows],
        "total_views": [{"date": r.recorded_at.isoformat(), "value": r.total_views} for r in rows],
        "videos_count": [{"date": r.recorded_at.isoformat(), "value": r.videos_count} for r in rows],
        "engagement_rate": [{"date": r.recorded_at.isoformat(), "value": r.engagement_rate} for r in rows],
    }


def _get_app_series(db: Session, comp_id: int, store: str, start: datetime, end: datetime) -> dict:
    rows = (
        db.query(AppData)
        .filter(
            AppData.competitor_id == comp_id,
            AppData.store == store,
            AppData.recorded_at >= start,
            AppData.recorded_at <= end,
        )
        .order_by(AppData.recorded_at)
        .all()
    )
    return {
        "rating": [{"date": r.recorded_at.isoformat(), "value": r.rating} for r in rows],
        "reviews_count": [{"date": r.recorded_at.isoformat(), "value": r.reviews_count} for r in rows],
        "downloads": [{"date": r.recorded_at.isoformat(), "value": r.downloads_numeric} for r in rows if r.downloads_numeric],
    }


def _get_snapchat_series(db: Session, comp_id: int, start: datetime, end: datetime) -> dict:
    """Snapchat ads count timeseries from Ad table (platform=snapchat)."""
    rows = (
        db.query(
            func.date(Ad.start_date).label("day"),
            func.count(Ad.id).label("ads_count"),
            func.coalesce(func.sum(Ad.impressions_min), 0).label("impressions"),
        )
        .filter(
            Ad.competitor_id == comp_id,
            Ad.platform == "snapchat",
            Ad.start_date >= start,
            Ad.start_date <= end,
        )
        .group_by(func.date(Ad.start_date))
        .order_by(func.date(Ad.start_date))
        .all()
    )
    return {
        "ads_count": [{"date": str(r.day), "value": r.ads_count} for r in rows],
        "impressions": [{"date": str(r.day), "value": int(r.impressions)} for r in rows],
    }


def _get_ads_series(db: Session, comp_id: int, start: datetime, end: datetime) -> dict:
    """Ad metrics from daily snapshots."""
    rows = (
        db.query(
            func.date(AdSnapshot.recorded_at).label("day"),
            func.count(AdSnapshot.id).label("active_count"),
            func.sum(AdSnapshot.estimated_spend_min).label("spend_min"),
            func.sum(AdSnapshot.estimated_spend_max).label("spend_max"),
            func.sum(AdSnapshot.eu_total_reach).label("total_reach"),
        )
        .filter(
            AdSnapshot.competitor_id == comp_id,
            AdSnapshot.recorded_at >= start,
            AdSnapshot.recorded_at <= end,
        )
        .group_by(func.date(AdSnapshot.recorded_at))
        .order_by(func.date(AdSnapshot.recorded_at))
        .all()
    )
    return {
        "active_count": [{"date": str(r.day), "value": r.active_count} for r in rows],
        "spend_min": [{"date": str(r.day), "value": float(r.spend_min or 0)} for r in rows],
        "spend_max": [{"date": str(r.day), "value": float(r.spend_max or 0)} for r in rows],
        "total_reach": [{"date": str(r.day), "value": int(r.total_reach or 0)} for r in rows],
    }


# ─── Delta computation ──────────────────────────────────────────────

def _compute_deltas(db: Session, comp_id: int, start: datetime, end: datetime) -> dict:
    """Compute latest value + delta for each metric."""
    metrics = {}

    # Instagram
    ig_latest = db.query(InstagramData).filter(
        InstagramData.competitor_id == comp_id,
        InstagramData.recorded_at <= end,
    ).order_by(InstagramData.recorded_at.desc()).first()

    ig_prev = db.query(InstagramData).filter(
        InstagramData.competitor_id == comp_id,
        InstagramData.recorded_at <= start,
    ).order_by(InstagramData.recorded_at.desc()).first()

    if ig_latest:
        metrics["ig_followers"] = _delta(ig_latest.followers, ig_prev.followers if ig_prev else None)
        metrics["ig_engagement"] = _delta(ig_latest.engagement_rate, ig_prev.engagement_rate if ig_prev else None)
        metrics["ig_posts"] = _delta(ig_latest.posts_count, ig_prev.posts_count if ig_prev else None)

    # TikTok
    tt_latest = db.query(TikTokData).filter(
        TikTokData.competitor_id == comp_id,
        TikTokData.recorded_at <= end,
    ).order_by(TikTokData.recorded_at.desc()).first()

    tt_prev = db.query(TikTokData).filter(
        TikTokData.competitor_id == comp_id,
        TikTokData.recorded_at <= start,
    ).order_by(TikTokData.recorded_at.desc()).first()

    if tt_latest:
        metrics["tt_followers"] = _delta(tt_latest.followers, tt_prev.followers if tt_prev else None)
        metrics["tt_likes"] = _delta(tt_latest.likes, tt_prev.likes if tt_prev else None)

    # YouTube
    yt_latest = db.query(YouTubeData).filter(
        YouTubeData.competitor_id == comp_id,
        YouTubeData.recorded_at <= end,
    ).order_by(YouTubeData.recorded_at.desc()).first()

    yt_prev = db.query(YouTubeData).filter(
        YouTubeData.competitor_id == comp_id,
        YouTubeData.recorded_at <= start,
    ).order_by(YouTubeData.recorded_at.desc()).first()

    if yt_latest:
        metrics["yt_subscribers"] = _delta(yt_latest.subscribers, yt_prev.subscribers if yt_prev else None)
        metrics["yt_views"] = _delta(yt_latest.total_views, yt_prev.total_views if yt_prev else None)
        metrics["yt_engagement"] = _delta(yt_latest.engagement_rate, yt_prev.engagement_rate if yt_prev else None)

    # App Store
    for store in ["playstore", "appstore"]:
        prefix = "ps" if store == "playstore" else "as"
        app_latest = db.query(AppData).filter(
            AppData.competitor_id == comp_id,
            AppData.store == store,
            AppData.recorded_at <= end,
        ).order_by(AppData.recorded_at.desc()).first()

        app_prev = db.query(AppData).filter(
            AppData.competitor_id == comp_id,
            AppData.store == store,
            AppData.recorded_at <= start,
        ).order_by(AppData.recorded_at.desc()).first()

        if app_latest:
            metrics[f"{prefix}_rating"] = _delta(app_latest.rating, app_prev.rating if app_prev else None)
            metrics[f"{prefix}_reviews"] = _delta(app_latest.reviews_count, app_prev.reviews_count if app_prev else None)
            if app_latest.downloads_numeric:
                metrics[f"{prefix}_downloads"] = _delta(
                    app_latest.downloads_numeric,
                    app_prev.downloads_numeric if app_prev else None
                )

    # Ads (from snapshots — latest day vs first day in range)
    ad_latest = (
        db.query(
            func.count(AdSnapshot.id).label("cnt"),
            func.sum(AdSnapshot.estimated_spend_min).label("spend_min"),
            func.sum(AdSnapshot.estimated_spend_max).label("spend_max"),
            func.sum(AdSnapshot.eu_total_reach).label("reach"),
        )
        .filter(
            AdSnapshot.competitor_id == comp_id,
            AdSnapshot.recorded_at >= end - timedelta(days=1),
            AdSnapshot.recorded_at <= end,
        )
        .first()
    )

    ad_prev = (
        db.query(
            func.count(AdSnapshot.id).label("cnt"),
            func.sum(AdSnapshot.estimated_spend_min).label("spend_min"),
            func.sum(AdSnapshot.estimated_spend_max).label("spend_max"),
            func.sum(AdSnapshot.eu_total_reach).label("reach"),
        )
        .filter(
            AdSnapshot.competitor_id == comp_id,
            AdSnapshot.recorded_at >= start,
            AdSnapshot.recorded_at <= start + timedelta(days=1),
        )
        .first()
    )

    if ad_latest and ad_latest.cnt:
        metrics["ads_active"] = _delta(ad_latest.cnt, ad_prev.cnt if ad_prev else None)
        metrics["ads_spend_max"] = _delta(
            float(ad_latest.spend_max or 0),
            float(ad_prev.spend_max or 0) if ad_prev else None
        )
        metrics["ads_reach"] = _delta(
            int(ad_latest.reach or 0),
            int(ad_prev.reach or 0) if ad_prev else None
        )

    # Snapchat Ads
    snap_latest_count = db.query(func.count(Ad.id)).filter(
        Ad.competitor_id == comp_id,
        Ad.platform == "snapchat",
    ).scalar() or 0

    snap_impressions = db.query(func.coalesce(func.sum(Ad.impressions_min), 0)).filter(
        Ad.competitor_id == comp_id,
        Ad.platform == "snapchat",
    ).scalar() or 0

    if snap_latest_count > 0:
        metrics["snap_ads"] = {"value": snap_latest_count, "previous": None, "delta": None, "delta_pct": None}
        metrics["snap_impressions"] = {"value": int(snap_impressions), "previous": None, "delta": None, "delta_pct": None}

    return metrics


def _delta(current, previous) -> dict:
    """Build a metric object with value, previous, delta, delta_pct."""
    if current is None:
        return {"value": None, "previous": previous, "delta": None, "delta_pct": None}
    if previous is None or previous == 0:
        return {"value": current, "previous": None, "delta": None, "delta_pct": None}
    d = current - previous
    pct = (d / previous) * 100 if previous != 0 else 0
    return {
        "value": current,
        "previous": previous,
        "delta": d,
        "delta_pct": round(pct, 2),
    }
