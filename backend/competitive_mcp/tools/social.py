"""Tools: get_social_metrics, get_top_social_posts."""
from sqlalchemy import func, desc
from datetime import datetime, timedelta

from competitive_mcp.db import (
    get_session, find_competitor, get_all_competitors,
    Competitor, InstagramData, TikTokData, YouTubeData, SnapchatData, SocialPost,
)
from competitive_mcp.formatting import format_number, format_percent, format_date, truncate
from competitive_mcp.tools.dashboard import _batch_latest


def get_social_metrics(
    competitor_name: str | None = None,
    platform: str | None = None,
    days: int = 7,
) -> str:
    """Métriques réseaux sociaux avec croissance."""
    db = get_session()
    try:
        if competitor_name:
            comp = find_competitor(db, competitor_name)
            if not comp:
                return f"Concurrent « {competitor_name} » non trouvé."
            competitors = [comp]
        else:
            competitors = get_all_competitors(db)

        if not competitors:
            return "Aucun concurrent configuré."

        comp_ids = [c.id for c in competitors]
        week_ago = datetime.utcnow() - timedelta(days=days)

        lines = ["# Métriques Réseaux Sociaux", ""]

        for comp in competitors:
            lines.append(f"## {comp.name}" + (" (marque)" if comp.is_brand else ""))
            has_data = False

            if platform is None or platform == "instagram":
                ig = db.query(InstagramData).filter(
                    InstagramData.competitor_id == comp.id
                ).order_by(InstagramData.recorded_at.desc()).first()
                ig_old = db.query(InstagramData).filter(
                    InstagramData.competitor_id == comp.id,
                    InstagramData.recorded_at <= week_ago,
                ).order_by(InstagramData.recorded_at.desc()).first()

                if ig and ig.followers:
                    has_data = True
                    growth = ""
                    if ig_old and ig_old.followers and ig_old.followers > 0:
                        g = ((ig.followers - ig_old.followers) / ig_old.followers) * 100
                        growth = f" ({'+' if g >= 0 else ''}{g:.1f}% / {days}j)"
                    lines.append(f"- **Instagram** : {format_number(ig.followers)} followers{growth}")
                    lines.append(f"  Engagement : {format_percent(ig.engagement_rate)} | Posts : {ig.posts_count or 'N/A'}")

            if platform is None or platform == "tiktok":
                tt = db.query(TikTokData).filter(
                    TikTokData.competitor_id == comp.id
                ).order_by(TikTokData.recorded_at.desc()).first()
                tt_old = db.query(TikTokData).filter(
                    TikTokData.competitor_id == comp.id,
                    TikTokData.recorded_at <= week_ago,
                ).order_by(TikTokData.recorded_at.desc()).first()

                if tt and tt.followers:
                    has_data = True
                    growth = ""
                    if tt_old and tt_old.followers and tt_old.followers > 0:
                        g = ((tt.followers - tt_old.followers) / tt_old.followers) * 100
                        growth = f" ({'+' if g >= 0 else ''}{g:.1f}% / {days}j)"
                    lines.append(f"- **TikTok** : {format_number(tt.followers)} followers{growth}")
                    lines.append(f"  Likes : {format_number(tt.likes)} | Vidéos : {tt.videos_count or 'N/A'}")

            if platform is None or platform == "youtube":
                yt = db.query(YouTubeData).filter(
                    YouTubeData.competitor_id == comp.id
                ).order_by(YouTubeData.recorded_at.desc()).first()
                yt_old = db.query(YouTubeData).filter(
                    YouTubeData.competitor_id == comp.id,
                    YouTubeData.recorded_at <= week_ago,
                ).order_by(YouTubeData.recorded_at.desc()).first()

                if yt and yt.subscribers:
                    has_data = True
                    growth = ""
                    if yt_old and yt_old.subscribers and yt_old.subscribers > 0:
                        g = ((yt.subscribers - yt_old.subscribers) / yt_old.subscribers) * 100
                        growth = f" ({'+' if g >= 0 else ''}{g:.1f}% / {days}j)"
                    lines.append(f"- **YouTube** : {format_number(yt.subscribers)} abonnés{growth}")
                    lines.append(f"  Vues : {format_number(yt.total_views)} | Vidéos : {yt.videos_count or 'N/A'}")

            if platform is None or platform == "snapchat":
                snap = db.query(SnapchatData).filter(
                    SnapchatData.competitor_id == comp.id
                ).order_by(SnapchatData.recorded_at.desc()).first()

                if snap and snap.subscribers:
                    has_data = True
                    lines.append(f"- **Snapchat** : {format_number(snap.subscribers)} abonnés")
                    lines.append(f"  Engagement : {format_percent(snap.engagement_rate)} | Spotlights : {snap.spotlight_count or 'N/A'}")

            if not has_data:
                lines.append("- Aucune donnée sociale disponible")
            lines.append("")

        return "\n".join(lines)
    finally:
        db.close()


def get_top_social_posts(
    competitor_name: str | None = None,
    platform: str | None = None,
    sort_by: str = "views",
    days: int | None = None,
) -> str:
    """Posts sociaux les plus performants."""
    from datetime import datetime, timedelta
    db = get_session()
    try:
        query = db.query(SocialPost, Competitor.name).join(
            Competitor, SocialPost.competitor_id == Competitor.id
        ).filter(Competitor.is_active == True)

        if competitor_name:
            comp = find_competitor(db, competitor_name)
            if not comp:
                return f"Concurrent « {competitor_name} » non trouvé."
            query = query.filter(SocialPost.competitor_id == comp.id)

        if platform:
            query = query.filter(SocialPost.platform.ilike(f"%{platform}%"))

        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(SocialPost.posted_at >= cutoff)

        # Sort
        sort_col = {
            "views": SocialPost.views,
            "likes": SocialPost.likes,
            "comments": SocialPost.comments,
            "engagement": SocialPost.content_engagement_score,
        }.get(sort_by, SocialPost.views)

        posts = query.order_by(desc(sort_col)).all()

        if not posts:
            return "Aucun post social trouvé avec ces critères."

        lines = [f"# Top {len(posts)} Posts (trié par {sort_by})", ""]

        for i, (post, comp_name) in enumerate(posts, 1):
            lines.append(f"### {i}. {comp_name} — {post.platform}")
            if post.title:
                lines.append(f"**{truncate(post.title, 100)}**")
            lines.append(
                f"👁 {format_number(post.views)} vues | "
                f"❤ {format_number(post.likes)} likes | "
                f"💬 {post.comments or 0} commentaires"
            )
            if post.content_theme:
                lines.append(f"Thème : {post.content_theme} | Ton : {post.content_tone or 'N/A'}")
            if post.content_summary:
                lines.append(f"*{truncate(post.content_summary, 120)}*")
            if post.url:
                lines.append(f"[Voir]({post.url})")
            lines.append("")

        return "\n".join(lines)
    finally:
        db.close()
