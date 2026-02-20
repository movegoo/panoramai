"""
Part de Voix Publicitaire — agrégation par annonceur (page_name), pas par concurrent.
Chaque page Facebook/Instagram/TikTok est un annonceur distinct.
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
    """Agrégation part de voix publicitaire par annonceur (page_name)."""
    # Period
    if end_date:
        period_end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        period_end = datetime.utcnow()

    if start_date:
        period_start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        period_start = period_end - timedelta(days=90)

    # Get competitor IDs to scope ads (we only have ads for tracked competitors)
    competitors = get_user_competitors(db, user)
    if not competitors:
        return {"period": {"start": period_start.strftime("%Y-%m-%d"), "end": period_end.strftime("%Y-%m-%d")},
                "advertisers": [], "timeline": [], "totals": {}}

    comp_map = {c.id: c for c in competitors}
    comp_ids = list(comp_map.keys())

    # Load all ads in period
    ads = (
        db.query(Ad)
        .filter(Ad.competitor_id.in_(comp_ids))
        .filter((Ad.start_date >= period_start) | (Ad.is_active == True))
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

    # Group by advertiser (page_name)
    ads_by_advertiser: dict[str, list[Ad]] = defaultdict(list)
    for a in filtered_ads:
        advertiser_name = a.page_name or comp_map.get(a.competitor_id, None)
        if advertiser_name is None:
            advertiser_name = "Inconnu"
        elif not isinstance(advertiser_name, str):
            advertiser_name = advertiser_name.name
        ads_by_advertiser[advertiser_name].append(a)

    # Build page_id → logo/profile pic mapping
    page_logos: dict[str, str | None] = {}
    for a in filtered_ads:
        pname = a.page_name
        if pname and pname not in page_logos:
            page_logos[pname] = a.page_profile_picture_url

    # Also map competitor logos as fallback
    comp_name_to_logo: dict[str, str | None] = {}
    for c in competitors:
        comp_name_to_logo[c.name] = c.logo_url

    grand_total_ads = len(filtered_ads)
    grand_active = 0
    grand_spend_min = 0.0
    grand_spend_max = 0.0
    grand_reach = 0

    adv_results = []

    for adv_name, adv_ads in ads_by_advertiser.items():
        active_count = sum(1 for a in adv_ads if a.is_active)
        grand_active += active_count

        by_platform: dict[str, dict] = defaultdict(lambda: {"ads": 0, "spend_min": 0.0, "spend_max": 0.0, "reach": 0})
        by_type: dict[str, int] = defaultdict(int)
        by_format: dict[str, int] = defaultdict(int)

        adv_spend_min = 0.0
        adv_spend_max = 0.0
        adv_reach = 0

        for a in adv_ads:
            s_min, s_max = _estimate_spend(a)
            adv_spend_min += s_min
            adv_spend_max += s_max
            reach = a.eu_total_reach or 0
            adv_reach += reach

            platforms = _parse_platforms(a)
            for plat in platforms:
                by_platform[plat]["ads"] += 1
                by_platform[plat]["spend_min"] += s_min / max(len(platforms), 1)
                by_platform[plat]["spend_max"] += s_max / max(len(platforms), 1)
                by_platform[plat]["reach"] += reach // max(len(platforms), 1)

            ad_type = a.ad_type or "unknown"
            by_type[ad_type] += 1

            fmt = (a.display_format or "unknown").upper()
            by_format[fmt] += 1

        grand_spend_min += adv_spend_min
        grand_spend_max += adv_spend_max
        grand_reach += adv_reach

        # Logo: prefer page profile picture, fallback to competitor logo
        logo = page_logos.get(adv_name) or comp_name_to_logo.get(adv_name)

        # Find which competitor this advertiser belongs to (if any)
        parent_competitor = None
        if adv_ads:
            cid = adv_ads[0].competitor_id
            comp = comp_map.get(cid)
            if comp:
                parent_competitor = comp.name

        adv_results.append({
            "name": adv_name,
            "logo_url": logo,
            "parent_competitor": parent_competitor,
            "total_ads": len(adv_ads),
            "active_ads": active_count,
            "sov_pct": 0,  # calculated below
            "spend_min": round(adv_spend_min),
            "spend_max": round(adv_spend_max),
            "reach": adv_reach,
            "by_platform": {k: {"ads": v["ads"], "spend_min": round(v["spend_min"]), "spend_max": round(v["spend_max"]), "reach": v["reach"]} for k, v in by_platform.items()},
            "by_type": dict(by_type),
            "by_format": dict(by_format),
        })

    # Calculate SOV %
    for a in adv_results:
        a["sov_pct"] = round(a["total_ads"] / grand_total_ads * 100, 1) if grand_total_ads > 0 else 0

    # Sort by total_ads desc
    adv_results.sort(key=lambda x: x["total_ads"], reverse=True)

    # Timeline: weekly aggregation by advertiser
    timeline: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"ads_started": 0, "spend_min": 0.0}))
    for a in filtered_ads:
        if not a.start_date:
            continue
        week = a.start_date.strftime("%G-W%V")
        adv_name = a.page_name
        if not adv_name:
            comp = comp_map.get(a.competitor_id)
            adv_name = comp.name if comp else "Inconnu"
        s_min, _ = _estimate_spend(a)
        timeline[week][adv_name]["ads_started"] += 1
        timeline[week][adv_name]["spend_min"] += s_min

    timeline_list = []
    for week in sorted(timeline.keys()):
        entry: dict = {"week": week}
        for adv_name_str, vals in timeline[week].items():
            entry[adv_name_str] = vals["ads_started"]
            entry[f"{adv_name_str}_spend"] = round(vals["spend_min"])
        timeline_list.append(entry)

    return {
        "period": {
            "start": period_start.strftime("%Y-%m-%d"),
            "end": period_end.strftime("%Y-%m-%d"),
        },
        "advertisers": adv_results,
        "timeline": timeline_list,
        "totals": {
            "total_ads": grand_total_ads,
            "active_ads": grand_active,
            "spend_min": round(grand_spend_min),
            "spend_max": round(grand_spend_max),
            "reach": grand_reach,
            "advertisers_count": len(adv_results),
        },
    }
