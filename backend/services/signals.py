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


def _fmt_pct(pct: float) -> str:
    """Format a percentage smartly: avoid '-0.0%' by using enough decimals."""
    if pct == 0:
        return "0%"
    abs_pct = abs(pct)
    if abs_pct >= 1:
        return f"{pct:+.1f}%"
    if abs_pct >= 0.01:
        return f"{pct:+.2f}%"
    return f"{pct:+.3f}%"


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
        # Trend-based intelligence (multi-day patterns)
        new_signals.extend(_detect_growth_trends(db, comp))
        new_signals.extend(_detect_review_velocity(db, comp))
        new_signals.extend(_detect_engagement_trends(db, comp))
        new_signals.extend(_detect_posting_frequency(db, comp))

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
    """Create a signal and return its dict representation.

    Brand signals (is_brand=True) are always downgraded to 'info' severity
    since changes in our own brand are expected, not alarming.
    """
    is_brand = getattr(comp, "is_brand", False) or False
    severity = kwargs.get("severity", "info")
    if is_brand:
        severity = "info"  # Own brand signals are never critical/warning
    kwargs["severity"] = severity

    signal = Signal(
        competitor_id=comp.id,
        advertiser_id=comp.advertiser_id,
        is_brand=is_brand,
        **kwargs,
    )
    db.add(signal)
    db.commit()
    return {
        "competitor": comp.name,
        "type": kwargs.get("signal_type"),
        "severity": severity,
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
                title=f"Instagram: {direction} de {_fmt_pct(abs(pct)).lstrip('+')} des followers pour {comp.name}",
                description=f"Passage de {prev.followers:,} à {latest.followers:,} followers ({_fmt_pct(pct)})",
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
                title=f"TikTok: {direction} de {_fmt_pct(abs(pct)).lstrip('+')} des followers pour {comp.name}",
                description=f"Passage de {prev.followers:,} à {latest.followers:,} followers ({_fmt_pct(pct)})",
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
                title=f"YouTube: {direction} de {_fmt_pct(abs(pct)).lstrip('+')} des abonnés pour {comp.name}",
                description=f"Passage de {prev.subscribers:,} à {latest.subscribers:,} abonnés ({_fmt_pct(pct)})",
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


# =============================================================================
# Trend-based intelligence (multi-day pattern analysis)
# =============================================================================

def _get_series(db: Session, model, competitor_id: int, days: int = 7):
    """Get the last N days of records for a competitor."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    return db.query(model).filter(
        model.competitor_id == competitor_id,
        model.recorded_at >= cutoff,
    ).order_by(model.recorded_at).all()


def _already_signaled(db: Session, comp_id: int, signal_type: str, hours: int = 24) -> bool:
    """Check if we already created this type of signal recently."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    return db.query(Signal).filter(
        Signal.competitor_id == comp_id,
        Signal.signal_type == signal_type,
        Signal.detected_at >= cutoff,
    ).first() is not None


def _linear_slope(values: list[float]) -> float:
    """Simple linear regression slope (growth rate per day)."""
    n = len(values)
    if n < 3:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


def _detect_growth_trends(db: Session, comp: Competitor) -> list:
    """
    Detect growth acceleration / deceleration over 7 days.
    Compare first-half slope vs second-half slope.
    If growth accelerates by 3x → signal.
    """
    signals = []

    sources = [
        (InstagramData, "followers", "instagram", "followers Instagram", THRESHOLDS["min_followers"]),
        (TikTokData, "followers", "tiktok", "followers TikTok", THRESHOLDS["min_followers"]),
        (YouTubeData, "subscribers", "youtube", "abonnes YouTube", THRESHOLDS["min_followers"]),
    ]

    for model, field, platform, label, min_val in sources:
        sig_type = f"growth_trend_{platform}"
        if _already_signaled(db, comp.id, sig_type):
            continue

        records = _get_series(db, model, comp.id, days=7)
        values = [getattr(r, field) or 0 for r in records]
        if len(values) < 5 or values[0] < min_val:
            continue

        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]

        slope_first = _linear_slope(first_half)
        slope_second = _linear_slope(second_half)

        # Growth acceleration: second half growing 3x faster
        if slope_first > 0 and slope_second > slope_first * 3 and slope_second > 10:
            total_gain = values[-1] - values[0]
            pct_gain = (total_gain / values[0]) * 100 if values[0] > 0 else 0
            signals.append(_create_signal(db, comp,
                signal_type=sig_type,
                severity="warning",
                platform=platform,
                title=f"{platform.title()}: acceleration de croissance des {label} pour {comp.name}",
                description=(
                    f"Croissance en acceleration sur 7 jours: +{total_gain:,.0f} ({_fmt_pct(pct_gain)}). "
                    f"Rythme x{slope_second / slope_first:.1f} vs semaine precedente."
                ),
                metric_name=field,
                previous_value=values[0],
                current_value=values[-1],
                change_percent=round(pct_gain, 2),
            ))

        # Growth deceleration / decline trend
        elif slope_first > 0 and slope_second < -abs(slope_first) * 0.5:
            total_change = values[-1] - values[0]
            pct = (total_change / values[0]) * 100 if values[0] > 0 else 0
            signals.append(_create_signal(db, comp,
                signal_type=sig_type,
                severity="warning",
                platform=platform,
                title=f"{platform.title()}: retournement de tendance des {label} pour {comp.name}",
                description=(
                    f"Apres une croissance, les {label} sont en baisse. "
                    f"Variation totale: {total_change:+,.0f} ({_fmt_pct(pct)}) sur 7 jours."
                ),
                metric_name=field,
                previous_value=values[0],
                current_value=values[-1],
                change_percent=round(pct, 2),
            ))

        # Sustained decline: losing followers every day for 5+ days
        if len(values) >= 5:
            consecutive_drops = 0
            for i in range(1, len(values)):
                if values[i] < values[i - 1]:
                    consecutive_drops += 1
                else:
                    consecutive_drops = 0
            if consecutive_drops >= 5 and not _already_signaled(db, comp.id, f"sustained_decline_{platform}"):
                total_loss = values[-1] - values[-consecutive_drops - 1]
                pct = (total_loss / values[-consecutive_drops - 1]) * 100 if values[-consecutive_drops - 1] > 0 else 0
                signals.append(_create_signal(db, comp,
                    signal_type=f"sustained_decline_{platform}",
                    severity="critical",
                    platform=platform,
                    title=f"{platform.title()}: baisse continue des {label} ({consecutive_drops}j) pour {comp.name}",
                    description=(
                        f"Les {label} baissent depuis {consecutive_drops} jours consecutifs. "
                        f"Perte totale: {total_loss:+,.0f} ({_fmt_pct(pct)})."
                    ),
                    metric_name=field,
                    previous_value=values[-consecutive_drops - 1],
                    current_value=values[-1],
                    change_percent=round(pct, 2),
                ))

    return signals


def _detect_review_velocity(db: Session, comp: Competitor) -> list:
    """
    Detect sudden surges in app reviews (campaign or crisis indicator).
    """
    signals = []

    for store in ["playstore", "appstore"]:
        sig_type = f"review_surge_{store}"
        if _already_signaled(db, comp.id, sig_type):
            continue

        records = _get_series(db, AppData, comp.id, days=7)
        store_records = [r for r in records if r.store == store and r.reviews_count]
        if len(store_records) < 3:
            continue

        review_counts = [r.reviews_count for r in store_records]
        daily_gains = [review_counts[i] - review_counts[i - 1] for i in range(1, len(review_counts))]

        if not daily_gains or len(daily_gains) < 2:
            continue

        avg_daily = sum(daily_gains[:-1]) / len(daily_gains[:-1]) if len(daily_gains) > 1 else daily_gains[0]
        latest_gain = daily_gains[-1]

        # 3x normal daily review gain
        if avg_daily > 0 and latest_gain > avg_daily * 3 and latest_gain > 50:
            store_label = "Play Store" if store == "playstore" else "App Store"
            signals.append(_create_signal(db, comp,
                signal_type=sig_type,
                severity="warning",
                platform=store,
                title=f"{store_label}: afflux d'avis anormal pour {comp.name}",
                description=(
                    f"+{latest_gain} avis en 1 jour (moyenne: {avg_daily:.0f}/jour). "
                    f"Velocite x{latest_gain / avg_daily:.1f}. Total: {review_counts[-1]:,} avis."
                ),
                metric_name="reviews_count",
                previous_value=review_counts[-2],
                current_value=review_counts[-1],
                change_percent=round((latest_gain / avg_daily) * 100, 2) if avg_daily > 0 else 0,
            ))

        # Rating + reviews: detect review bombing (sudden bad reviews + rating drop)
        ratings = [r.rating for r in store_records if r.rating]
        if len(ratings) >= 3:
            rating_drop = ratings[0] - ratings[-1]
            if rating_drop >= 0.3 and latest_gain > avg_daily * 2:
                store_label = "Play Store" if store == "playstore" else "App Store"
                if not _already_signaled(db, comp.id, f"review_bombing_{store}"):
                    signals.append(_create_signal(db, comp,
                        signal_type=f"review_bombing_{store}",
                        severity="critical",
                        platform=store,
                        title=f"{store_label}: possible review bombing pour {comp.name}",
                        description=(
                            f"Note en baisse ({ratings[0]:.1f} → {ratings[-1]:.1f}) "
                            f"accompagnee d'un afflux d'avis ({latest_gain}/jour vs {avg_daily:.0f}/jour normal). "
                            f"Possible campagne d'avis negatifs."
                        ),
                        metric_name="rating",
                        previous_value=ratings[0],
                        current_value=ratings[-1],
                        change_percent=round(-rating_drop, 2),
                    ))

    return signals


def _detect_engagement_trends(db: Session, comp: Competitor) -> list:
    """Detect sustained engagement changes on Instagram over 5+ days."""
    signals = []
    sig_type = "engagement_trend_instagram"
    if _already_signaled(db, comp.id, sig_type):
        return signals

    records = _get_series(db, InstagramData, comp.id, days=7)
    rates = [r.engagement_rate for r in records if r.engagement_rate is not None]
    if len(rates) < 5:
        return signals

    rising = sum(1 for i in range(1, len(rates)) if rates[i] > rates[i - 1])
    falling = sum(1 for i in range(1, len(rates)) if rates[i] < rates[i - 1])

    total_change = rates[-1] - rates[0]

    if rising >= len(rates) - 2 and total_change > 0.5:
        signals.append(_create_signal(db, comp,
            signal_type=sig_type,
            severity="info",
            platform="instagram",
            title=f"Instagram: engagement en hausse continue pour {comp.name}",
            description=(
                f"Taux d'engagement en hausse sur {len(rates)} jours: "
                f"{rates[0]:.2f}% → {rates[-1]:.2f}% ({total_change:+.2f}pts). "
                f"Contenu performant."
            ),
            metric_name="engagement_rate",
            previous_value=rates[0],
            current_value=rates[-1],
            change_percent=round(total_change, 2),
        ))
    elif falling >= len(rates) - 2 and total_change < -0.5:
        signals.append(_create_signal(db, comp,
            signal_type=sig_type,
            severity="warning",
            platform="instagram",
            title=f"Instagram: engagement en baisse continue pour {comp.name}",
            description=(
                f"Taux d'engagement en baisse sur {len(rates)} jours: "
                f"{rates[0]:.2f}% → {rates[-1]:.2f}% ({total_change:+.2f}pts). "
                f"Contenu moins performant ou changement d'algorithme."
            ),
            metric_name="engagement_rate",
            previous_value=rates[0],
            current_value=rates[-1],
            change_percent=round(total_change, 2),
        ))

    return signals


def _detect_posting_frequency(db: Session, comp: Competitor) -> list:
    """Detect changes in social media posting frequency."""
    signals = []

    # Instagram: posts_count delta over 14 days
    sig_type = "posting_surge_instagram"
    if not _already_signaled(db, comp.id, sig_type):
        records = _get_series(db, InstagramData, comp.id, days=14)
        posts = [(r.recorded_at, r.posts_count) for r in records if r.posts_count]
        if len(posts) >= 7:
            mid = len(posts) // 2
            first_half_rate = (posts[mid][1] - posts[0][1]) / max(mid, 1)
            second_half_rate = (posts[-1][1] - posts[mid][1]) / max(len(posts) - mid, 1)

            if first_half_rate > 0 and second_half_rate > first_half_rate * 2.5 and second_half_rate > 0.5:
                total_new = posts[-1][1] - posts[0][1]
                signals.append(_create_signal(db, comp,
                    signal_type=sig_type,
                    severity="info",
                    platform="instagram",
                    title=f"Instagram: rythme de publication accelere pour {comp.name}",
                    description=(
                        f"+{total_new} publications en {len(posts)} jours. "
                        f"Rythme x{second_half_rate / first_half_rate:.1f} vs periode precedente. "
                        f"Possible campagne de contenu en cours."
                    ),
                    metric_name="posts_count",
                    previous_value=posts[0][1],
                    current_value=posts[-1][1],
                    change_percent=round((total_new / posts[0][1]) * 100 if posts[0][1] > 0 else 0, 2),
                ))

    # TikTok: videos_count delta
    sig_type = "posting_surge_tiktok"
    if not _already_signaled(db, comp.id, sig_type):
        records = _get_series(db, TikTokData, comp.id, days=14)
        videos = [(r.recorded_at, r.videos_count) for r in records if r.videos_count]
        if len(videos) >= 7:
            mid = len(videos) // 2
            first_half_rate = (videos[mid][1] - videos[0][1]) / max(mid, 1)
            second_half_rate = (videos[-1][1] - videos[mid][1]) / max(len(videos) - mid, 1)

            if first_half_rate > 0 and second_half_rate > first_half_rate * 2.5 and second_half_rate > 0.3:
                total_new = videos[-1][1] - videos[0][1]
                signals.append(_create_signal(db, comp,
                    signal_type=sig_type,
                    severity="info",
                    platform="tiktok",
                    title=f"TikTok: rythme de publication accelere pour {comp.name}",
                    description=(
                        f"+{total_new} videos en {len(videos)} jours. "
                        f"Rythme x{second_half_rate / first_half_rate:.1f} vs periode precedente."
                    ),
                    metric_name="videos_count",
                    previous_value=videos[0][1],
                    current_value=videos[-1][1],
                    change_percent=round((total_new / videos[0][1]) * 100 if videos[0][1] > 0 else 0, 2),
                ))

    return signals
