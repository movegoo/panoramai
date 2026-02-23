"""Tools: search_ads, get_ad_intelligence."""
import json
from sqlalchemy import func, desc
from datetime import datetime, timedelta

from competitive_mcp.db import (
    get_session, find_competitor, get_all_competitors,
    Competitor, Ad,
)
from competitive_mcp.formatting import format_number, format_euros, format_date, truncate


def search_ads(
    competitor_name: str | None = None,
    platform: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> str:
    """Recherche et filtre les publicités."""
    db = get_session()
    try:
        query = db.query(Ad, Competitor.name).join(
            Competitor, Ad.competitor_id == Competitor.id
        ).filter(Competitor.is_active == True)

        if competitor_name:
            comp = find_competitor(db, competitor_name)
            if not comp:
                return f"Concurrent « {competitor_name} » non trouvé."
            query = query.filter(Ad.competitor_id == comp.id)

        if platform:
            query = query.filter(Ad.platform.ilike(f"%{platform}%"))

        if category:
            query = query.filter(Ad.product_category.ilike(f"%{category}%"))

        ads = query.order_by(desc(Ad.start_date)).limit(min(limit, 100)).all()

        if not ads:
            return "Aucune publicité trouvée avec ces critères."

        lines = [f"# {len(ads)} Publicités trouvées", ""]

        for ad, comp_name in ads:
            status = "🟢 Active" if ad.is_active else "🔴 Inactive"
            lines.append(f"### {comp_name} — {ad.display_format or 'N/A'} ({status})")

            parts = []
            if ad.start_date:
                parts.append(f"Début : {format_date(ad.start_date)}")
            if ad.platform:
                parts.append(f"Plateforme : {ad.platform}")
            if ad.product_category:
                parts.append(f"Catégorie : {ad.product_category}")
            if ad.eu_total_reach:
                parts.append(f"Reach : {format_number(ad.eu_total_reach)}")
            if ad.estimated_spend_min:
                parts.append(f"Budget : {format_euros(ad.estimated_spend_min)} – {format_euros(ad.estimated_spend_max)}")
            lines.append(" | ".join(parts))

            if ad.ad_text:
                lines.append(f"> {truncate(ad.ad_text)}")

            if ad.creative_summary:
                lines.append(f"*{truncate(ad.creative_summary)}*")

            lines.append("")

        return "\n".join(lines)
    finally:
        db.close()


def get_ad_intelligence(days: int = 30) -> str:
    """Analyse macro des publicités : formats, plateformes, dépenses estimées."""
    db = get_session()
    try:
        competitors = get_all_competitors(db)
        comp_ids = [c.id for c in competitors]
        comp_names = {c.id: c.name for c in competitors}

        if not comp_ids:
            return "Aucun concurrent configuré."

        all_ads = db.query(Ad).filter(Ad.competitor_id.in_(comp_ids)).all()
        if not all_ads:
            return "Aucune publicité en base."

        # Global stats
        active = [a for a in all_ads if a.is_active]
        format_counts = {}
        platform_counts = {}
        comp_ad_counts = {}

        total_spend_min = 0
        total_spend_max = 0

        for ad in all_ads:
            fmt = ad.display_format or "AUTRE"
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

            try:
                pps = json.loads(ad.publisher_platforms) if ad.publisher_platforms else []
            except (json.JSONDecodeError, TypeError):
                pps = []
            if not pps and ad.platform:
                pps = [ad.platform.upper()]
            for pp in pps:
                platform_counts[pp] = platform_counts.get(pp, 0) + 1

            cid = ad.competitor_id
            if cid not in comp_ad_counts:
                comp_ad_counts[cid] = {"total": 0, "active": 0, "spend_min": 0, "spend_max": 0}
            comp_ad_counts[cid]["total"] += 1
            if ad.is_active:
                comp_ad_counts[cid]["active"] += 1

            spend = _estimate_spend(ad)
            comp_ad_counts[cid]["spend_min"] += spend[0]
            comp_ad_counts[cid]["spend_max"] += spend[1]
            total_spend_min += spend[0]
            total_spend_max += spend[1]

        lines = ["# Intelligence Publicitaire", ""]
        lines.append(f"**Total** : {len(all_ads)} pubs ({len(active)} actives)")
        lines.append(f"**Budget estimé total** : {format_euros(total_spend_min)} – {format_euros(total_spend_max)}")
        lines.append("")

        # Format breakdown
        lines.append("## Répartition par format")
        for fmt, count in sorted(format_counts.items(), key=lambda x: -x[1]):
            pct = round(count / len(all_ads) * 100, 1)
            lines.append(f"- {fmt} : {count} ({pct}%)")

        lines.append("")
        lines.append("## Répartition par plateforme")
        for plat, count in sorted(platform_counts.items(), key=lambda x: -x[1]):
            pct = round(count / len(all_ads) * 100, 1)
            lines.append(f"- {plat} : {count} ({pct}%)")

        lines.append("")
        lines.append("## Par concurrent")
        sorted_comps = sorted(comp_ad_counts.items(), key=lambda x: -x[1]["total"])
        for cid, data in sorted_comps:
            name = comp_names.get(cid, f"ID {cid}")
            lines.append(
                f"- **{name}** : {data['total']} pubs ({data['active']} actives) | "
                f"Budget estimé : {format_euros(data['spend_min'])} – {format_euros(data['spend_max'])}"
            )

        return "\n".join(lines)
    finally:
        db.close()


def _estimate_spend(ad):
    """Estime le budget d'une pub."""
    if ad.estimated_spend_min and ad.estimated_spend_min > 0:
        return (ad.estimated_spend_min, ad.estimated_spend_max or ad.estimated_spend_min)
    cpm = 3.0
    if ad.impressions_min and ad.impressions_min > 0:
        return (
            (ad.impressions_min / 1000) * cpm,
            ((ad.impressions_max or ad.impressions_min) / 1000) * cpm,
        )
    if ad.eu_total_reach and ad.eu_total_reach > 100:
        return (
            (ad.eu_total_reach / 1000) * cpm * 0.7,
            (ad.eu_total_reach / 1000) * cpm * 1.3,
        )
    return (0, 0)
