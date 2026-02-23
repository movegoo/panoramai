"""Tools: list_competitors, get_competitor_detail, compare_competitors."""
from sqlalchemy import func

from competitive_mcp.db import (
    get_session, get_all_competitors, find_competitor,
    Competitor, Ad, InstagramData, TikTokData, YouTubeData, SnapchatData, AppData,
)
from competitive_mcp.formatting import format_number, format_rating, format_percent, format_date
from competitive_mcp.tools.dashboard import _batch_latest, _calc_score


def list_competitors(include_brand: bool = True) -> str:
    """Liste tous les concurrents avec scores et métriques clés."""
    db = get_session()
    try:
        competitors = get_all_competitors(db, include_brand=include_brand)
        if not competitors:
            return "Aucun concurrent configuré."

        comp_ids = [c.id for c in competitors]
        ig_map = _batch_latest(db, InstagramData, comp_ids)
        tt_map = _batch_latest(db, TikTokData, comp_ids)
        yt_map = _batch_latest(db, YouTubeData, comp_ids)
        ps_map = _batch_latest(db, AppData, comp_ids, AppData.store == "playstore")
        as_map = _batch_latest(db, AppData, comp_ids, AppData.store == "appstore")

        ad_counts = dict(
            db.query(Ad.competitor_id, func.count(Ad.id))
            .filter(Ad.competitor_id.in_(comp_ids))
            .group_by(Ad.competitor_id).all()
        )

        lines = [f"# {len(competitors)} Concurrents", ""]
        for comp in competitors:
            ig = ig_map.get(comp.id)
            tt = tt_map.get(comp.id)
            yt = yt_map.get(comp.id)
            ps = ps_map.get(comp.id)
            aps = as_map.get(comp.id)

            marker = " (votre marque)" if comp.is_brand else ""
            lines.append(f"## {comp.name}{marker}")

            parts = []
            if ig and ig.followers:
                parts.append(f"Instagram: {format_number(ig.followers)} followers")
            if tt and tt.followers:
                parts.append(f"TikTok: {format_number(tt.followers)} followers")
            if yt and yt.subscribers:
                parts.append(f"YouTube: {format_number(yt.subscribers)} abonnés")
            if ps and ps.rating:
                parts.append(f"Play Store: {format_rating(ps.rating)}")
            if aps and aps.rating:
                parts.append(f"App Store: {format_rating(aps.rating)}")

            ads = ad_counts.get(comp.id, 0)
            parts.append(f"Publicités: {ads}")

            if comp.website:
                parts.append(f"Site: {comp.website}")

            lines.append(" | ".join(parts))
            lines.append("")

        return "\n".join(lines)
    finally:
        db.close()


def get_competitor_detail(competitor_name: str) -> str:
    """Profil détaillé d'un concurrent (tous canaux)."""
    db = get_session()
    try:
        comp = find_competitor(db, competitor_name)
        if not comp:
            return f"Concurrent « {competitor_name} » non trouvé. Utilisez list_competitors pour voir les noms disponibles."

        lines = [f"# {comp.name}" + (" (votre marque)" if comp.is_brand else ""), ""]

        # Info générale
        if comp.website:
            lines.append(f"**Site** : {comp.website}")

        # Instagram
        ig = db.query(InstagramData).filter(
            InstagramData.competitor_id == comp.id
        ).order_by(InstagramData.recorded_at.desc()).first()
        if ig:
            lines.append("")
            lines.append("## Instagram")
            lines.append(f"- Followers : {format_number(ig.followers)}")
            lines.append(f"- Posts : {ig.posts_count or 'N/A'}")
            lines.append(f"- Engagement : {format_percent(ig.engagement_rate)}")
            lines.append(f"- Avg likes : {format_number(ig.avg_likes)}")
            lines.append(f"- Dernière collecte : {format_date(ig.recorded_at)}")

        # TikTok
        tt = db.query(TikTokData).filter(
            TikTokData.competitor_id == comp.id
        ).order_by(TikTokData.recorded_at.desc()).first()
        if tt:
            lines.append("")
            lines.append("## TikTok")
            lines.append(f"- Followers : {format_number(tt.followers)}")
            lines.append(f"- Likes : {format_number(tt.likes)}")
            lines.append(f"- Vidéos : {tt.videos_count or 'N/A'}")

        # YouTube
        yt = db.query(YouTubeData).filter(
            YouTubeData.competitor_id == comp.id
        ).order_by(YouTubeData.recorded_at.desc()).first()
        if yt:
            lines.append("")
            lines.append("## YouTube")
            lines.append(f"- Abonnés : {format_number(yt.subscribers)}")
            lines.append(f"- Vues totales : {format_number(yt.total_views)}")
            lines.append(f"- Vidéos : {yt.videos_count or 'N/A'}")
            lines.append(f"- Engagement : {format_percent(yt.engagement_rate)}")

        # Snapchat
        snap = db.query(SnapchatData).filter(
            SnapchatData.competitor_id == comp.id
        ).order_by(SnapchatData.recorded_at.desc()).first()
        if snap:
            lines.append("")
            lines.append("## Snapchat")
            lines.append(f"- Abonnés : {format_number(snap.subscribers)}")
            lines.append(f"- Spotlights : {snap.spotlight_count or 'N/A'}")
            lines.append(f"- Engagement : {format_percent(snap.engagement_rate)}")

        # Apps
        ps = db.query(AppData).filter(
            AppData.competitor_id == comp.id, AppData.store == "playstore"
        ).order_by(AppData.recorded_at.desc()).first()
        aps = db.query(AppData).filter(
            AppData.competitor_id == comp.id, AppData.store == "appstore"
        ).order_by(AppData.recorded_at.desc()).first()

        if ps or aps:
            lines.append("")
            lines.append("## Applications")
            if ps:
                lines.append(f"- **Play Store** : {ps.app_name or comp.name}")
                lines.append(f"  Note {format_rating(ps.rating)} | {format_number(ps.reviews_count)} avis | {ps.downloads or 'N/A'} téléchargements")
            if aps:
                lines.append(f"- **App Store** : {aps.app_name or comp.name}")
                lines.append(f"  Note {format_rating(aps.rating)} | {format_number(aps.reviews_count)} avis")

        # Ads summary
        ad_count = db.query(func.count(Ad.id)).filter(Ad.competitor_id == comp.id).scalar() or 0
        active_count = db.query(func.count(Ad.id)).filter(
            Ad.competitor_id == comp.id, Ad.is_active == True
        ).scalar() or 0
        if ad_count:
            lines.append("")
            lines.append(f"## Publicités")
            lines.append(f"- Total : {ad_count} ({active_count} actives)")

        return "\n".join(lines)
    finally:
        db.close()


def compare_competitors(names: list[str], channel: str | None = None) -> str:
    """Comparaison côte à côte de 2 à 5 concurrents."""
    db = get_session()
    try:
        comps = []
        for name in names[:5]:
            comp = find_competitor(db, name)
            if comp:
                comps.append(comp)

        if len(comps) < 2:
            return f"Il faut au moins 2 concurrents pour comparer. Trouvés : {len(comps)}. Vérifiez les noms avec list_competitors."

        comp_ids = [c.id for c in comps]
        comp_names = [c.name for c in comps]

        lines = [f"# Comparaison : {' vs '.join(comp_names)}", ""]

        if channel is None or channel == "instagram":
            ig_map = _batch_latest(db, InstagramData, comp_ids)
            lines.append("## Instagram")
            for comp in comps:
                ig = ig_map.get(comp.id)
                if ig:
                    lines.append(f"- **{comp.name}** : {format_number(ig.followers)} followers | Engagement {format_percent(ig.engagement_rate)} | {ig.posts_count or 0} posts")
                else:
                    lines.append(f"- **{comp.name}** : Pas de données Instagram")
            lines.append("")

        if channel is None or channel == "tiktok":
            tt_map = _batch_latest(db, TikTokData, comp_ids)
            lines.append("## TikTok")
            for comp in comps:
                tt = tt_map.get(comp.id)
                if tt:
                    lines.append(f"- **{comp.name}** : {format_number(tt.followers)} followers | {format_number(tt.likes)} likes | {tt.videos_count or 0} vidéos")
                else:
                    lines.append(f"- **{comp.name}** : Pas de données TikTok")
            lines.append("")

        if channel is None or channel == "youtube":
            yt_map = _batch_latest(db, YouTubeData, comp_ids)
            lines.append("## YouTube")
            for comp in comps:
                yt = yt_map.get(comp.id)
                if yt:
                    lines.append(f"- **{comp.name}** : {format_number(yt.subscribers)} abonnés | {format_number(yt.total_views)} vues | {yt.videos_count or 0} vidéos")
                else:
                    lines.append(f"- **{comp.name}** : Pas de données YouTube")
            lines.append("")

        if channel is None or channel == "apps":
            ps_map = _batch_latest(db, AppData, comp_ids, AppData.store == "playstore")
            as_map = _batch_latest(db, AppData, comp_ids, AppData.store == "appstore")
            lines.append("## Applications")
            for comp in comps:
                ps = ps_map.get(comp.id)
                aps = as_map.get(comp.id)
                parts = [f"**{comp.name}**"]
                if ps:
                    parts.append(f"Play Store {format_rating(ps.rating)}")
                if aps:
                    parts.append(f"App Store {format_rating(aps.rating)}")
                if not ps and not aps:
                    parts.append("Pas de données apps")
                lines.append(f"- {' | '.join(parts)}")
            lines.append("")

        if channel is None or channel == "ads":
            ad_counts = dict(
                db.query(Ad.competitor_id, func.count(Ad.id))
                .filter(Ad.competitor_id.in_(comp_ids))
                .group_by(Ad.competitor_id).all()
            )
            active_counts = dict(
                db.query(Ad.competitor_id, func.count(Ad.id))
                .filter(Ad.competitor_id.in_(comp_ids), Ad.is_active == True)
                .group_by(Ad.competitor_id).all()
            )
            lines.append("## Publicités")
            for comp in comps:
                total = ad_counts.get(comp.id, 0)
                active = active_counts.get(comp.id, 0)
                lines.append(f"- **{comp.name}** : {total} pubs ({active} actives)")

        return "\n".join(lines)
    finally:
        db.close()
