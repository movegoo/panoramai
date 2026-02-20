"""
Part de Voix Publicitaire — agrégation ads par concurrent, plateforme, type, timeline.
"""
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import SessionLocal, Ad, User, Competitor
from core.auth import get_current_user
from core.permissions import get_user_competitors

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _estimate_spend(ad: Ad) -> tuple[float, float]:
    """Estimated spend (priority: declared > impressions×CPM > reach×CPM)."""
    if ad.estimated_spend_min and ad.estimated_spend_min > 0:
        return ad.estimated_spend_min, ad.estimated_spend_max or ad.estimated_spend_min
    if ad.impressions_min and ad.impressions_min > 0:
        cpm = 3.0
        return (ad.impressions_min / 1000) * cpm, ((ad.impressions_max or ad.impressions_min) / 1000) * cpm
    if ad.eu_total_reach and ad.eu_total_reach > 100:
        cpm = 3.0
        return (ad.eu_total_reach / 1000) * cpm * 0.7, (ad.eu_total_reach / 1000) * cpm * 1.3
    return 0.0, 0.0


def _parse_platforms(ad: Ad) -> list[str]:
    """Parse publisher_platforms JSON, normalise AUDIENCE_NETWORK/MESSENGER → facebook."""
    pps: list[str] = []
    if ad.publisher_platforms:
        try:
            pps = json.loads(ad.publisher_platforms)
        except (json.JSONDecodeError, TypeError):
            pps = []
    if not pps and ad.platform:
        pps = [ad.platform.upper()]

    normalised = []
    for p in pps:
        p_lower = p.lower()
        if p_lower in ("audience_network", "messenger"):
            p_lower = "facebook"
        normalised.append(p_lower)
    return list(set(normalised))


@router.get("/overview")
async def ads_overview(
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    user: User = Depends(get_current_user),
    db: Session = Depends(_get_db),
):
    """Agrégation part de voix publicitaire par concurrent."""
    # Period
    if end_date:
        period_end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        period_end = datetime.utcnow()

    if start_date:
        period_start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        period_start = period_end - timedelta(days=90)

    # Competitors
    competitors = get_user_competitors(db, user)
    if not competitors:
        return {"period": {"start": period_start.strftime("%Y-%m-%d"), "end": period_end.strftime("%Y-%m-%d")},
                "competitors": [], "timeline": [], "totals": {}}

    comp_map = {c.id: c for c in competitors}
    comp_ids = list(comp_map.keys())

    # Load ads in period (started in period OR still active)
    ads = (
        db.query(Ad)
        .filter(
            Ad.competitor_id.in_(comp_ids),
        )
        .filter(
            (Ad.start_date >= period_start) | (Ad.is_active == True)
        )
        .all()
    )

    # Filter: only ads that overlap with the period
    filtered_ads = []
    for a in ads:
        if a.start_date and a.start_date > period_end:
            continue
        if a.end_date and a.end_date < period_start:
            continue
        filtered_ads.append(a)

    # Group by competitor
    ads_by_comp: dict[int, list[Ad]] = defaultdict(list)
    for a in filtered_ads:
        ads_by_comp[a.competitor_id].append(a)

    # Build per-competitor stats
    comp_results = []
    grand_total_ads = len(filtered_ads)
    grand_active = 0
    grand_spend_min = 0.0
    grand_spend_max = 0.0
    grand_reach = 0

    for cid in comp_ids:
        comp = comp_map[cid]
        c_ads = ads_by_comp.get(cid, [])

        active_count = sum(1 for a in c_ads if a.is_active)
        grand_active += active_count

        # By platform
        by_platform: dict[str, dict] = defaultdict(lambda: {"ads": 0, "spend_min": 0.0, "spend_max": 0.0, "reach": 0})
        # By ad type
        by_type: dict[str, int] = defaultdict(int)
        # By format
        by_format: dict[str, int] = defaultdict(int)

        comp_spend_min = 0.0
        comp_spend_max = 0.0
        comp_reach = 0

        for a in c_ads:
            s_min, s_max = _estimate_spend(a)
            comp_spend_min += s_min
            comp_spend_max += s_max
            reach = a.eu_total_reach or 0
            comp_reach += reach

            # Platform breakdown
            platforms = _parse_platforms(a)
            for plat in platforms:
                by_platform[plat]["ads"] += 1
                by_platform[plat]["spend_min"] += s_min / max(len(platforms), 1)
                by_platform[plat]["spend_max"] += s_max / max(len(platforms), 1)
                by_platform[plat]["reach"] += reach // max(len(platforms), 1)

            # Ad type
            ad_type = a.ad_type or "unknown"
            by_type[ad_type] += 1

            # Format
            fmt = (a.display_format or "unknown").upper()
            by_format[fmt] += 1

        grand_spend_min += comp_spend_min
        grand_spend_max += comp_spend_max
        grand_reach += comp_reach

        sov_pct = (len(c_ads) / grand_total_ads * 100) if grand_total_ads > 0 else 0

        comp_results.append({
            "id": cid,
            "name": comp.name,
            "logo_url": comp.logo_url,
            "total_ads": len(c_ads),
            "active_ads": active_count,
            "sov_pct": round(sov_pct, 1),
            "spend_min": round(comp_spend_min),
            "spend_max": round(comp_spend_max),
            "reach": comp_reach,
            "by_platform": {k: {"ads": v["ads"], "spend_min": round(v["spend_min"]), "spend_max": round(v["spend_max"]), "reach": v["reach"]} for k, v in by_platform.items()},
            "by_type": dict(by_type),
            "by_format": dict(by_format),
        })

    # Recalculate SOV % now that we have the true grand total
    for c in comp_results:
        c["sov_pct"] = round(c["total_ads"] / grand_total_ads * 100, 1) if grand_total_ads > 0 else 0

    # Sort by total_ads desc
    comp_results.sort(key=lambda x: x["total_ads"], reverse=True)

    # Timeline: weekly aggregation
    timeline: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"ads_started": 0, "spend_min": 0.0}))
    for a in filtered_ads:
        if not a.start_date:
            continue
        week = a.start_date.strftime("%G-W%V")
        comp_name = comp_map.get(a.competitor_id)
        if comp_name:
            s_min, _ = _estimate_spend(a)
            timeline[week][comp_name.name]["ads_started"] += 1
            timeline[week][comp_name.name]["spend_min"] += s_min

    timeline_list = []
    for week in sorted(timeline.keys()):
        entry: dict = {"week": week}
        for comp_name_str, vals in timeline[week].items():
            entry[comp_name_str] = vals["ads_started"]
            entry[f"{comp_name_str}_spend"] = round(vals["spend_min"])
        timeline_list.append(entry)

    return {
        "period": {
            "start": period_start.strftime("%Y-%m-%d"),
            "end": period_end.strftime("%Y-%m-%d"),
        },
        "competitors": comp_results,
        "timeline": timeline_list,
        "totals": {
            "total_ads": grand_total_ads,
            "active_ads": grand_active,
            "spend_min": round(grand_spend_min),
            "spend_max": round(grand_spend_max),
            "reach": grand_reach,
        },
    }
