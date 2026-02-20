"""
Part de Voix Publicitaire — agrégation par bénéficiaire.
Priorité: beneficiary > page_name > competitor name.
Un payeur (ex: Mobsuccess) achète pour le compte de bénéficiaires (ex: Carrefour).
"""
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from database import SessionLocal, Ad, User, Competitor
from core.auth import get_current_user
from core.permissions import get_user_competitors, parse_advertiser_header

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
    x_advertiser_id: str | None = Header(None),
):
    """Agrégation part de voix publicitaire par bénéficiaire."""
    adv_id = parse_advertiser_header(x_advertiser_id)

    # Period
    if end_date:
        period_end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        period_end = datetime.utcnow()

    if start_date:
        period_start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        period_start = period_end - timedelta(days=90)

    # Get competitor IDs scoped to current advertiser
    competitors = get_user_competitors(db, user, advertiser_id=adv_id)
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

    # Resolve beneficiary name: beneficiary > page_name > competitor name
    def _resolve_beneficiary(ad: Ad) -> str:
        if ad.beneficiary:
            return ad.beneficiary.strip()
        if ad.page_name:
            return ad.page_name.strip()
        comp = comp_map.get(ad.competitor_id)
        return comp.name if comp else "Inconnu"

    # Group by beneficiary
    ads_by_beneficiary: dict[str, list[Ad]] = defaultdict(list)
    for a in filtered_ads:
        ads_by_beneficiary[_resolve_beneficiary(a)].append(a)

    # Build logo mapping: page profile pic by beneficiary name
    beneficiary_logos: dict[str, str | None] = {}
    for a in filtered_ads:
        bname = _resolve_beneficiary(a)
        if bname not in beneficiary_logos and a.page_profile_picture_url:
            beneficiary_logos[bname] = a.page_profile_picture_url

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

    for adv_name, adv_ads in ads_by_beneficiary.items():
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
        logo = beneficiary_logos.get(adv_name) or comp_name_to_logo.get(adv_name)

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

    # Timeline: weekly aggregation by beneficiary
    timeline: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"ads_started": 0, "spend_min": 0.0}))
    for a in filtered_ads:
        if not a.start_date:
            continue
        week = a.start_date.strftime("%G-W%V")
        bname = _resolve_beneficiary(a)
        s_min, _ = _estimate_spend(a)
        timeline[week][bname]["ads_started"] += 1
        timeline[week][bname]["spend_min"] += s_min

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
