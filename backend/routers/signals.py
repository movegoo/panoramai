"""
Signals router.
Exposes detected signals (anomalies, trends, competitive moves) to the frontend.
"""
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional

from database import get_db, Signal, AdSnapshot, User
from core.auth import get_current_user
from core.permissions import get_user_competitor_ids, parse_advertiser_header

router = APIRouter()


@router.get("/")
async def list_signals(
    limit: int = 50,
    severity: Optional[str] = None,
    platform: Optional[str] = None,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """List recent signals for the current advertiser's competitors."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)

    query = db.query(Signal).filter(Signal.competitor_id.in_(comp_ids))

    if severity:
        query = query.filter(Signal.severity == severity)
    if platform:
        query = query.filter(Signal.platform == platform)
    if unread_only:
        query = query.filter(Signal.is_read == False)

    signals = query.order_by(desc(Signal.detected_at)).limit(limit).all()

    return [
        {
            "id": s.id,
            "competitor_id": s.competitor_id,
            "signal_type": s.signal_type,
            "severity": s.severity,
            "platform": s.platform,
            "title": s.title,
            "description": s.description,
            "metric_name": s.metric_name,
            "previous_value": s.previous_value,
            "current_value": s.current_value,
            "change_percent": s.change_percent,
            "is_brand": s.is_brand,
            "is_read": s.is_read,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        }
        for s in signals
    ]


@router.get("/summary")
async def signals_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Summary counts by severity and platform."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)

    signals = db.query(Signal).filter(Signal.competitor_id.in_(comp_ids)).all()

    by_severity = {}
    by_platform = {}
    unread = 0
    brand_signals = 0

    for s in signals:
        by_severity[s.severity] = by_severity.get(s.severity, 0) + 1
        by_platform[s.platform] = by_platform.get(s.platform, 0) + 1
        if not s.is_read:
            unread += 1
        if s.is_brand:
            brand_signals += 1

    return {
        "total": len(signals),
        "unread": unread,
        "brand_signals": brand_signals,
        "by_severity": by_severity,
        "by_platform": by_platform,
    }


@router.post("/mark-read/{signal_id}")
async def mark_signal_read(
    signal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a signal as read."""
    signal = db.query(Signal).filter(Signal.id == signal_id).first()
    if signal:
        signal.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/mark-all-read")
async def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Mark all signals as read for current advertiser."""
    adv_id = parse_advertiser_header(x_advertiser_id)
    comp_ids = get_user_competitor_ids(db, user, advertiser_id=adv_id)

    db.query(Signal).filter(
        Signal.competitor_id.in_(comp_ids),
        Signal.is_read == False,
    ).update({Signal.is_read: True}, synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.post("/detect")
async def run_detection(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Manually trigger signal detection."""
    from services.signals import detect_all_signals, snapshot_active_ads

    adv_id = parse_advertiser_header(x_advertiser_id)

    snap_count = snapshot_active_ads(db)
    signals = detect_all_signals(db, advertiser_id=adv_id)

    return {
        "message": f"Detection complete: {len(signals)} new signals, {snap_count} ad snapshots",
        "signals": signals,
        "snapshots": snap_count,
    }


@router.get("/ad-trends/{competitor_id}")
async def get_ad_trends(
    competitor_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get daily ad activity trends for a competitor from snapshots."""
    from datetime import datetime, timedelta
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Group snapshots by day
    daily = db.query(
        func.date(AdSnapshot.recorded_at).label("day"),
        func.count(AdSnapshot.id).label("active_ads"),
        func.sum(AdSnapshot.estimated_spend_min).label("spend_min"),
        func.sum(AdSnapshot.estimated_spend_max).label("spend_max"),
        func.sum(AdSnapshot.eu_total_reach).label("total_reach"),
    ).filter(
        AdSnapshot.competitor_id == competitor_id,
        AdSnapshot.recorded_at >= cutoff,
    ).group_by(func.date(AdSnapshot.recorded_at)).order_by("day").all()

    return [
        {
            "date": str(d.day),
            "active_ads": d.active_ads,
            "spend_min": d.spend_min or 0,
            "spend_max": d.spend_max or 0,
            "total_reach": d.total_reach or 0,
        }
        for d in daily
    ]
