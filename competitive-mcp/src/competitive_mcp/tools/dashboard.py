"""Tool: get_dashboard_overview — Vue d'ensemble de la veille."""
from sqlalchemy import func
from datetime import datetime, timedelta

from competitive_mcp.db import (
    get_session, get_all_competitors,
    Competitor, Ad, InstagramData, TikTokData, YouTubeData, SnapchatData, AppData,
)
from competitive_mcp.formatting import format_number, format_rating, format_percent


def _batch_latest(db, model, comp_ids, extra_filter=None):
    """Charge le dernier enregistrement par concurrent."""
    if not comp_ids:
        return {}
    sub = db.query(
        model.competitor_id,
        func.max(model.recorded_at).label("max_at"),
    ).filter(model.competitor_id.in_(comp_ids))
    if extra_filter is not None:
        sub = sub.filter(extra_filter)
    sub = sub.group_by(model.competitor_id).subquery()

    rows = db.query(model).join(
        sub,
        (model.competitor_id == sub.c.competitor_id) & (model.recorded_at == sub.c.max_at),
    )
    if extra_filter is not None:
        rows = rows.filter(extra_filter)
    return {r.competitor_id: r for r in rows.all()}


def get_dashboard_overview(days: int = 7) -> str:
    """Vue d'ensemble : classement, scores, KPIs vs concurrents."""
    db = get_session()
    try:
        competitors = get_all_competitors(db, include_brand=True)
        if not competitors:
            return "Aucun concurrent configuré."

        comp_ids = [c.id for c in competitors]

        ps_map = _batch_latest(db, AppData, comp_ids, AppData.store == "playstore")
        as_map = _batch_latest(db, AppData, comp_ids, AppData.store == "appstore")
        ig_map = _batch_latest(db, InstagramData, comp_ids)
        tt_map = _batch_latest(db, TikTokData, comp_ids)
        yt_map = _batch_latest(db, YouTubeData, comp_ids)

        # Ads count per competitor
        ad_counts = dict(
            db.query(Ad.competitor_id, func.count(Ad.id))
            .filter(Ad.competitor_id.in_(comp_ids))
            .group_by(Ad.competitor_id).all()
        )

        actors = []
        for comp in competitors:
            ps = ps_map.get(comp.id)
            aps = as_map.get(comp.id)
            ig = ig_map.get(comp.id)
            tt = tt_map.get(comp.id)
            yt = yt_map.get(comp.id)

            ratings = [x.rating for x in [ps, aps] if x and x.rating]
            avg_rating = sum(ratings) / len(ratings) if ratings else None

            total_social = 0
            if ig and ig.followers:
                total_social += ig.followers
            if tt and tt.followers:
                total_social += tt.followers
            if yt and yt.subscribers:
                total_social += yt.subscribers

            score = _calc_score(avg_rating, ps.downloads_numeric if ps else None, total_social or None)

            actors.append({
                "name": comp.name,
                "is_brand": bool(comp.is_brand),
                "score": score,
                "rating": avg_rating,
                "social": total_social,
                "ads": ad_counts.get(comp.id, 0),
                "ig": ig.followers if ig else None,
                "tt": tt.followers if tt else None,
                "yt": yt.subscribers if yt else None,
            })

        actors.sort(key=lambda x: x["score"], reverse=True)

        lines = ["# Dashboard Veille Concurrentielle", ""]

        # Brand summary
        brand = next((a for a in actors if a["is_brand"]), None)
        if brand:
            rank = next(i + 1 for i, a in enumerate(actors) if a["is_brand"])
            lines.append(f"**{brand['name']}** (votre marque) — Rang #{rank}/{len(actors)}, Score {brand['score']:.0f}/100")
            lines.append("")

        lines.append("## Classement")
        for i, a in enumerate(actors):
            marker = " ⭐" if a["is_brand"] else ""
            lines.append(
                f"{i + 1}. **{a['name']}**{marker} — Score {a['score']:.0f}/100 | "
                f"Note {format_rating(a['rating'])} | Social {format_number(a['social'])} | "
                f"{a['ads']} pubs"
            )

        lines.append("")
        lines.append("## Détail par plateforme")

        # Instagram leader
        ig_actors = [a for a in actors if a["ig"]]
        if ig_actors:
            leader = max(ig_actors, key=lambda x: x["ig"])
            lines.append(f"- **Instagram** : {leader['name']} ({format_number(leader['ig'])} followers)")

        # TikTok leader
        tt_actors = [a for a in actors if a["tt"]]
        if tt_actors:
            leader = max(tt_actors, key=lambda x: x["tt"])
            lines.append(f"- **TikTok** : {leader['name']} ({format_number(leader['tt'])} followers)")

        # YouTube leader
        yt_actors = [a for a in actors if a["yt"]]
        if yt_actors:
            leader = max(yt_actors, key=lambda x: x["yt"])
            lines.append(f"- **YouTube** : {leader['name']} ({format_number(leader['yt'])} abonnés)")

        # Ads leader
        ads_actors = [a for a in actors if a["ads"]]
        if ads_actors:
            leader = max(ads_actors, key=lambda x: x["ads"])
            lines.append(f"- **Publicités** : {leader['name']} ({leader['ads']} pubs)")

        return "\n".join(lines)
    finally:
        db.close()


def _calc_score(app_rating, downloads, social_followers):
    score = 0.0
    if app_rating:
        score += (app_rating / 5.0) * 40
    if social_followers:
        score += min(social_followers / 1_000_000, 1.0) * 40
    if downloads:
        score += min(downloads / 10_000_000, 1.0) * 20
    return round(score, 1)
