"""
Signal detection engine.
Analyzes daily data to detect significant changes, anomalies, and competitive moves.
Runs after each daily data collection.
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database import (
    Competitor, InstagramData, TikTokData, YouTubeData,
    AppData, Ad, Signal, AdSnapshot,
)

logger = logging.getLogger(__name__)

# Thresholds for signal detection
THRESHOLDS = {
    # Social followers: % change triggers
    "followers_warning": 5.0,    # ±5% = warning
    "followers_critical": 15.0,  # ±15% = critical

    # Engagement rate: absolute change triggers
    "engagement_warning": 1.0,   # ±1pt = warning
    "engagement_critical": 3.0,  # ±3pt = critical

    # App rating: absolute change triggers
    "rating_warning": 0.2,       # ±0.2 stars = warning
    "rating_critical": 0.5,      # ±0.5 stars = critical

    # Ad activity: % change in active ad count
    "ads_warning": 30.0,         # +30% more ads = warning
    "ads_critical": 100.0,       # +100% more ads = critical (doubled)

    # Minimum values to avoid noise on small accounts
    "min_followers": 100,
    "min_ads": 3,
}


def detect_all_signals(db: Session, advertiser_id: int = None) -> list[dict]:
    """Run all signal detections. Returns list of new signals created."""
    competitors = db.query(Competitor).filter(Competitor.is_active == True)
    if advertiser_id:
        competitors = competitors.filter(Competitor.advertiser_id == advertiser_id)
    competitors = competitors.all()

    new_signals = []
    for comp in competitors:
        new_signals.extend(_detect_instagram_signals(db, comp))
        new_signals.extend(_detect_tiktok_signals(db, comp))
        new_signals.extend(_detect_youtube_signals(db, comp))
        new_signals.extend(_detect_app_signals(db, comp))
        new_signals.extend(_detect_ad_signals(db, comp))

    logger.info(f"Signal detection complete: {len(new_signals)} new signals")
    return new_signals


def snapshot_active_ads(db: Session):
    """Take a daily snapshot of all active ads metrics."""
    active_ads = db.query(Ad).filter(Ad.is_active == True).all()
    count = 0
    for ad in active_ads:
        snapshot = AdSnapshot(
            ad_id=ad.ad_id,
            competitor_id=ad.competitor_id,
            platform=ad.platform,
            is_active=ad.is_active,
            impressions_min=ad.impressions_min,
            impressions_max=ad.impressions_max,
            estimated_spend_min=ad.estimated_spend_min,
            estimated_spend_max=ad.estimated_spend_max,
            eu_total_reach=ad.eu_total_reach,
        )
        db.add(snapshot)
        count += 1
    db.commit()
    logger.info(f"Ad snapshots: {count} active ads snapshotted")
    return count


def _create_signal(db: Session, comp: Competitor, **kwargs) -> dict:
    """Create a signal and return its dict representation."""
    signal = Signal(
        competitor_id=comp.id,
        advertiser_id=comp.advertiser_id,
        is_brand=getattr(comp, "is_brand", False) or False,
        **kwargs,
    )
    db.add(signal)
    db.commit()
    return {
        "competitor": comp.name,
        "type": kwargs.get("signal_type"),
        "severity": kwargs.get("severity"),
        "title": kwargs.get("title"),
    }


def _get_two_latest(db: Session, model, competitor_id: int, min_gap_hours: int = 6):
    """Get the two most recent records with minimum time gap."""
    records = db.query(model).filter(
        model.competitor_id == competitor_id
    ).order_by(desc(model.recorded_at)).limit(10).all()

    if len(records) < 2:
        return None, None

    latest = records[0]
    # Find the previous record with enough time gap
    for prev in records[1:]:
        if (latest.recorded_at - prev.recorded_at) > timedelta(hours=min_gap_hours):
            return latest, prev

    return latest, records[1] if len(records) > 1 else None


def _pct_change(new_val, old_val):
    """Calculate percentage change, handling None and zero."""
    if not new_val or not old_val or old_val == 0:
        return 0
    return ((new_val - old_val) / old_val) * 100


def _severity(pct: float, warning_threshold: float, critical_threshold: float) -> str | None:
    """Determine severity based on percentage change."""
    abs_pct = abs(pct)
    if abs_pct >= critical_threshold:
        return "critical"
    if abs_pct >= warning_threshold:
        return "warning"
    return None


# =============================================================================
# Platform-specific detectors
# =============================================================================

def _detect_instagram_signals(db: Session, comp: Competitor) -> list:
    signals = []
    latest, prev = _get_two_latest(db, InstagramData, comp.id)
    if not latest or not prev:
        return signals

    # Follower change
    if (prev.followers or 0) >= THRESHOLDS["min_followers"]:
        pct = _pct_change(latest.followers, prev.followers)
        sev = _severity(pct, THRESHOLDS["followers_warning"], THRESHOLDS["followers_critical"])
        if sev:
            direction = "hausse" if pct > 0 else "baisse"
            signals.append(_create_signal(db, comp,
                signal_type=f"follower_{'spike' if pct > 0 else 'drop'}",
                severity=sev,
                platform="instagram",
                title=f"Instagram: {direction} de {abs(pct):.1f}% des followers pour {comp.name}",
                description=f"Passage de {prev.followers:,} à {latest.followers:,} followers ({pct:+.1f}%)",
                metric_name="followers",
                previous_value=prev.followers,
                current_value=latest.followers,
                change_percent=round(pct, 2),
            ))

    # Engagement rate change
    if prev.engagement_rate and latest.engagement_rate:
        diff = (latest.engagement_rate or 0) - (prev.engagement_rate or 0)
        sev = _severity(diff, THRESHOLDS["engagement_warning"], THRESHOLDS["engagement_critical"])
        if sev:
            direction = "hausse" if diff > 0 else "baisse"
            signals.append(_create_signal(db, comp,
                signal_type=f"engagement_{'spike' if diff > 0 else 'drop'}",
                severity=sev,
                platform="instagram",
                title=f"Instagram: {direction} d'engagement pour {comp.name}",
                description=f"Taux d'engagement: {prev.engagement_rate:.2f}% → {latest.engagement_rate:.2f}% ({diff:+.2f}pts)",
                metric_name="engagement_rate",
                previous_value=prev.engagement_rate,
                current_value=latest.engagement_rate,
                change_percent=round(diff, 2),
            ))

    return signals


def _detect_tiktok_signals(db: Session, comp: Competitor) -> list:
    signals = []
    latest, prev = _get_two_latest(db, TikTokData, comp.id)
    if not latest or not prev:
        return signals

    if (prev.followers or 0) >= THRESHOLDS["min_followers"]:
        pct = _pct_change(latest.followers, prev.followers)
        sev = _severity(pct, THRESHOLDS["followers_warning"], THRESHOLDS["followers_critical"])
        if sev:
            direction = "hausse" if pct > 0 else "baisse"
            signals.append(_create_signal(db, comp,
                signal_type=f"follower_{'spike' if pct > 0 else 'drop'}",
                severity=sev,
                platform="tiktok",
                title=f"TikTok: {direction} de {abs(pct):.1f}% des followers pour {comp.name}",
                description=f"Passage de {prev.followers:,} à {latest.followers:,} followers ({pct:+.1f}%)",
                metric_name="followers",
                previous_value=prev.followers,
                current_value=latest.followers,
                change_percent=round(pct, 2),
            ))

    return signals


def _detect_youtube_signals(db: Session, comp: Competitor) -> list:
    signals = []
    latest, prev = _get_two_latest(db, YouTubeData, comp.id)
    if not latest or not prev:
        return signals

    if (prev.subscribers or 0) >= THRESHOLDS["min_followers"]:
        pct = _pct_change(latest.subscribers, prev.subscribers)
        sev = _severity(pct, THRESHOLDS["followers_warning"], THRESHOLDS["followers_critical"])
        if sev:
            direction = "hausse" if pct > 0 else "baisse"
            signals.append(_create_signal(db, comp,
                signal_type=f"subscriber_{'spike' if pct > 0 else 'drop'}",
                severity=sev,
                platform="youtube",
                title=f"YouTube: {direction} de {abs(pct):.1f}% des abonnés pour {comp.name}",
                description=f"Passage de {prev.subscribers:,} à {latest.subscribers:,} abonnés ({pct:+.1f}%)",
                metric_name="subscribers",
                previous_value=prev.subscribers,
                current_value=latest.subscribers,
                change_percent=round(pct, 2),
            ))

    return signals


def _detect_app_signals(db: Session, comp: Competitor) -> list:
    signals = []
    for store in ["playstore", "appstore"]:
        records = db.query(AppData).filter(
            AppData.competitor_id == comp.id,
            AppData.store == store,
        ).order_by(desc(AppData.recorded_at)).limit(5).all()

        if len(records) < 2:
            continue

        latest, prev = records[0], records[1]

        # Rating change
        if latest.rating and prev.rating:
            diff = latest.rating - prev.rating
            sev = _severity(diff, THRESHOLDS["rating_warning"], THRESHOLDS["rating_critical"])
            if sev:
                store_label = "Play Store" if store == "playstore" else "App Store"
                direction = "hausse" if diff > 0 else "baisse"
                signals.append(_create_signal(db, comp,
                    signal_type=f"rating_{'up' if diff > 0 else 'drop'}",
                    severity=sev,
                    platform=store,
                    title=f"{store_label}: {direction} de note pour {comp.name}",
                    description=f"Note: {prev.rating:.1f} → {latest.rating:.1f} ({diff:+.2f} étoiles)",
                    metric_name="rating",
                    previous_value=prev.rating,
                    current_value=latest.rating,
                    change_percent=round(diff, 2),
                ))

    return signals


def _detect_ad_signals(db: Session, comp: Competitor) -> list:
    """Detect significant changes in advertising activity."""
    signals = []

    # Compare active ads count: now vs 7 days ago
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    current_active = db.query(func.count(Ad.id)).filter(
        Ad.competitor_id == comp.id,
        Ad.is_active == True,
    ).scalar() or 0

    # Count ads that were active a week ago (started before week_ago and not ended)
    prev_active = db.query(func.count(Ad.id)).filter(
        Ad.competitor_id == comp.id,
        Ad.start_date <= week_ago,
        (Ad.end_date.is_(None) | (Ad.end_date >= week_ago)),
    ).scalar() or 0

    if prev_active >= THRESHOLDS["min_ads"]:
        pct = _pct_change(current_active, prev_active)
        sev = _severity(pct, THRESHOLDS["ads_warning"], THRESHOLDS["ads_critical"])
        if sev and pct > 0:  # Only alert on increases (new campaigns)
            signals.append(_create_signal(db, comp,
                signal_type="ad_surge",
                severity=sev,
                platform="meta_ads",
                title=f"Ads: forte hausse d'activité publicitaire pour {comp.name}",
                description=f"Pubs actives: {prev_active} → {current_active} ({pct:+.1f}% en 7 jours)",
                metric_name="active_ads",
                previous_value=prev_active,
                current_value=current_active,
                change_percent=round(pct, 2),
            ))

    # Detect new high-reach campaigns (eu_total_reach > 1M in last 3 days)
    three_days_ago = now - timedelta(days=3)
    big_ads = db.query(Ad).filter(
        Ad.competitor_id == comp.id,
        Ad.created_at >= three_days_ago,
        Ad.eu_total_reach > 1_000_000,
    ).all()

    for ad in big_ads:
        # Check if we already signaled this ad
        existing = db.query(Signal).filter(
            Signal.competitor_id == comp.id,
            Signal.signal_type == "high_reach_campaign",
            Signal.metric_name == ad.ad_id,
        ).first()
        if not existing:
            signals.append(_create_signal(db, comp,
                signal_type="high_reach_campaign",
                severity="warning",
                platform=ad.platform or "meta_ads",
                title=f"Campagne massive détectée pour {comp.name}",
                description=f"Nouvelle pub avec {ad.eu_total_reach:,} de reach EU. Texte: {(ad.ad_text or '')[:100]}",
                metric_name=ad.ad_id,
                current_value=ad.eu_total_reach,
                change_percent=0,
            ))

    return signals
