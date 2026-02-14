"""
Social Content Analysis Router.
Collect social posts, analyze with AI, aggregate insights.
"""
import asyncio
import json
import logging
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db, Competitor, User, SocialPost
from services.scrapecreators import scrapecreators
from services.social_content_analyzer import social_content_analyzer
from core.auth import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/collect-all")
async def collect_all_social_posts(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Collect recent posts/videos from TikTok, YouTube, Instagram for all active competitors."""
    query = db.query(Competitor).filter(Competitor.is_active == True)
    if user:
        query = query.filter(Competitor.user_id == user.id)
    competitors = query.all()

    if not competitors:
        return {"message": "No competitors found", "collected": 0}

    total_new = 0
    total_updated = 0
    results = []

    for comp in competitors:
        comp_result = {"competitor": comp.name, "tiktok": 0, "youtube": 0, "instagram": 0}

        # TikTok videos
        if comp.tiktok_username:
            try:
                data = await scrapecreators.fetch_tiktok_videos(comp.tiktok_username, limit=10)
                if data.get("success"):
                    for video in data.get("videos", []):
                        post_id = f"tt_{video.get('id', '')}"
                        if not post_id or post_id == "tt_":
                            continue
                        existing = db.query(SocialPost).filter(SocialPost.post_id == post_id).first()
                        published = None
                        ct = video.get("create_time")
                        if ct and isinstance(ct, (int, float)):
                            try:
                                published = datetime.utcfromtimestamp(ct)
                            except (ValueError, OSError):
                                pass

                        fields = dict(
                            competitor_id=comp.id,
                            platform="tiktok",
                            title="",
                            description=video.get("description", "")[:2000],
                            url=f"https://tiktok.com/@{comp.tiktok_username}/video/{video.get('id', '')}",
                            published_at=published,
                            views=video.get("views", 0) or 0,
                            likes=video.get("likes", 0) or 0,
                            comments=video.get("comments", 0) or 0,
                            shares=video.get("shares", 0) or 0,
                        )
                        if existing:
                            for k, v in fields.items():
                                setattr(existing, k, v)
                            total_updated += 1
                        else:
                            db.add(SocialPost(post_id=post_id, collected_at=datetime.utcnow(), **fields))
                            total_new += 1
                            comp_result["tiktok"] += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"TikTok collect error for {comp.name}: {e}")

        # YouTube videos
        if comp.youtube_channel_id:
            try:
                data = await scrapecreators.fetch_youtube_videos(
                    channel_id=comp.youtube_channel_id, limit=10
                )
                if data.get("success"):
                    for video in data.get("videos", []):
                        vid = video.get("video_id", "")
                        post_id = f"yt_{vid}"
                        if not vid:
                            continue
                        existing = db.query(SocialPost).filter(SocialPost.post_id == post_id).first()

                        fields = dict(
                            competitor_id=comp.id,
                            platform="youtube",
                            title=video.get("title", "")[:1000],
                            description=video.get("description", "")[:2000],
                            url=f"https://youtube.com/watch?v={vid}",
                            thumbnail_url=video.get("thumbnail_url", ""),
                            duration=video.get("duration", ""),
                            views=video.get("views", 0) or 0,
                            likes=video.get("likes", 0) or 0,
                            comments=video.get("comments", 0) or 0,
                        )
                        if existing:
                            for k, v in fields.items():
                                setattr(existing, k, v)
                            total_updated += 1
                        else:
                            db.add(SocialPost(post_id=post_id, collected_at=datetime.utcnow(), **fields))
                            total_new += 1
                            comp_result["youtube"] += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"YouTube collect error for {comp.name}: {e}")

        # Instagram posts (from profile endpoint)
        if comp.instagram_username:
            try:
                data = await scrapecreators._get("/v1/instagram/profile", {"handle": comp.instagram_username.lstrip("@")})
                if data.get("success"):
                    user_data = data.get("data", {}).get("user", {})
                    edges = user_data.get("edge_owner_to_timeline_media", {}).get("edges", [])
                    for edge in edges[:10]:
                        node = edge.get("node", {})
                        ig_id = node.get("id", "")
                        post_id = f"ig_{ig_id}"
                        if not ig_id:
                            continue
                        existing = db.query(SocialPost).filter(SocialPost.post_id == post_id).first()

                        caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
                        caption = caption_edges[0].get("node", {}).get("text", "") if caption_edges else ""

                        published = None
                        ts = node.get("taken_at_timestamp")
                        if ts:
                            try:
                                published = datetime.utcfromtimestamp(ts)
                            except (ValueError, OSError):
                                pass

                        shortcode = node.get("shortcode", "")
                        thumbnail = node.get("thumbnail_src", "") or node.get("display_url", "")

                        fields = dict(
                            competitor_id=comp.id,
                            platform="instagram",
                            title="",
                            description=caption[:2000],
                            url=f"https://instagram.com/p/{shortcode}/" if shortcode else "",
                            thumbnail_url=thumbnail,
                            published_at=published,
                            views=node.get("video_view_count", 0) or 0,
                            likes=node.get("edge_liked_by", {}).get("count", 0) or 0,
                            comments=node.get("edge_media_to_comment", {}).get("count", 0) or 0,
                        )
                        if existing:
                            for k, v in fields.items():
                                setattr(existing, k, v)
                            total_updated += 1
                        else:
                            db.add(SocialPost(post_id=post_id, collected_at=datetime.utcnow(), **fields))
                            total_new += 1
                            comp_result["instagram"] += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Instagram collect error for {comp.name}: {e}")

        results.append(comp_result)

    db.commit()

    total_posts = db.query(SocialPost).count()
    return {
        "message": f"Collected {total_new} new posts, updated {total_updated}",
        "new": total_new,
        "updated": total_updated,
        "total_in_db": total_posts,
        "by_competitor": results,
    }


@router.post("/analyze-all")
async def analyze_all_content(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Batch-analyze social posts that haven't been analyzed yet."""
    # Auto-reset previous failures (score=0)
    reset_query = db.query(SocialPost).join(Competitor, SocialPost.competitor_id == Competitor.id).filter(
        SocialPost.content_analyzed_at.isnot(None),
        SocialPost.content_engagement_score == 0,
    )
    if user:
        reset_query = reset_query.filter(Competitor.user_id == user.id)
    for post in reset_query.all():
        post.content_analyzed_at = None
        post.content_engagement_score = None
        post.content_analysis = None
    db.commit()

    # Get unanalyzed posts
    query = db.query(SocialPost).join(Competitor, SocialPost.competitor_id == Competitor.id).filter(
        SocialPost.content_analyzed_at.is_(None),
    )
    if user:
        query = query.filter(Competitor.user_id == user.id)

    posts_to_analyze = query.limit(limit).all()

    remaining_query = db.query(SocialPost).filter(SocialPost.content_analyzed_at.is_(None))
    if user:
        remaining_query = remaining_query.join(Competitor).filter(Competitor.user_id == user.id)

    if not posts_to_analyze:
        return {"message": "No posts to analyze", "analyzed": 0, "errors": 0, "remaining": remaining_query.count()}

    # Need competitor names for analysis
    comp_names = {}
    for post in posts_to_analyze:
        if post.competitor_id not in comp_names:
            comp = db.query(Competitor).get(post.competitor_id)
            comp_names[post.competitor_id] = comp.name if comp else ""

    analyzed = 0
    errors = 0

    for post in posts_to_analyze:
        try:
            result = await social_content_analyzer.analyze_content(
                title=post.title or "",
                description=post.description or "",
                platform=post.platform or "tiktok",
                competitor_name=comp_names.get(post.competitor_id, ""),
                views=post.views or 0,
                likes=post.likes or 0,
                comments=post.comments or 0,
                shares=post.shares or 0,
            )

            if result:
                post.content_analysis = json.dumps(result, ensure_ascii=False)
                post.content_theme = result.get("theme", "")[:100]
                post.content_hook = result.get("hook", "")[:500]
                post.content_tone = result.get("tone", "")[:100]
                post.content_format = result.get("format", "")[:100]
                post.content_cta = result.get("cta", "")[:500]
                post.content_hashtags = json.dumps(result.get("hashtags", []), ensure_ascii=False)
                post.content_mentions = json.dumps(result.get("mentions", []), ensure_ascii=False)
                post.content_engagement_score = result.get("engagement_score", 0)
                post.content_virality_factors = json.dumps(result.get("virality_factors", []), ensure_ascii=False)
                post.content_summary = result.get("summary", "")
                post.content_analyzed_at = datetime.utcnow()
                analyzed += 1
            else:
                post.content_analyzed_at = datetime.utcnow()
                post.content_engagement_score = 0
                errors += 1

        except Exception as e:
            logger.error(f"Error analyzing post {post.post_id}: {e}")
            post.content_analyzed_at = datetime.utcnow()
            post.content_engagement_score = 0
            errors += 1

        await asyncio.sleep(0.5)

    db.commit()

    remaining_query = db.query(SocialPost).filter(SocialPost.content_analyzed_at.is_(None))
    if user:
        remaining_query = remaining_query.join(Competitor).filter(Competitor.user_id == user.id)

    return {
        "message": f"Analyzed {analyzed} social posts",
        "analyzed": analyzed,
        "errors": errors,
        "remaining": remaining_query.count(),
    }


@router.get("/insights")
async def get_content_insights(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Aggregated content intelligence across all analyzed social posts."""
    query = db.query(SocialPost, Competitor.name).join(
        Competitor, SocialPost.competitor_id == Competitor.id
    ).filter(
        SocialPost.content_analyzed_at.isnot(None),
        SocialPost.content_engagement_score > 0,
    )
    if user:
        query = query.filter(Competitor.user_id == user.id)

    rows = query.all()

    if not rows:
        return {
            "total_analyzed": 0,
            "avg_score": 0,
            "themes": [],
            "tones": [],
            "formats": [],
            "top_hooks": [],
            "top_hashtags": [],
            "top_performers": [],
            "by_competitor": [],
            "by_platform": [],
            "recommendations": [],
        }

    scores = []
    theme_counter = Counter()
    tone_counter = Counter()
    format_counter = Counter()
    hashtag_counter = Counter()
    hooks = []
    by_competitor: dict[str, list] = {}
    by_platform: dict[str, list] = {}
    all_posts_data = []

    for post, comp_name in rows:
        score = post.content_engagement_score or 0
        scores.append(score)

        if post.content_theme:
            theme_counter[post.content_theme] += 1
        if post.content_tone:
            tone_counter[post.content_tone] += 1
        if post.content_format:
            format_counter[post.content_format] += 1

        # Parse hashtags
        try:
            tags = json.loads(post.content_hashtags) if post.content_hashtags else []
            for t in tags:
                if t:
                    hashtag_counter[t] += 1
        except (json.JSONDecodeError, TypeError):
            pass

        # Hooks with scores
        if post.content_hook and score > 0:
            hooks.append({
                "hook": post.content_hook,
                "score": score,
                "theme": post.content_theme or "",
                "competitor": comp_name,
                "platform": post.platform or "",
            })

        # By competitor
        if comp_name not in by_competitor:
            by_competitor[comp_name] = []
        by_competitor[comp_name].append({
            "score": score,
            "theme": post.content_theme,
            "tone": post.content_tone,
            "views": post.views or 0,
            "likes": post.likes or 0,
        })

        # By platform
        plat = post.platform or "unknown"
        if plat not in by_platform:
            by_platform[plat] = []
        by_platform[plat].append({
            "score": score,
            "views": post.views or 0,
        })

        # For top performers
        all_posts_data.append({
            "post_id": post.post_id,
            "competitor_name": comp_name,
            "platform": post.platform or "",
            "title": post.title or "",
            "description": (post.description or "")[:150],
            "url": post.url or "",
            "thumbnail_url": post.thumbnail_url or "",
            "score": score,
            "theme": post.content_theme or "",
            "tone": post.content_tone or "",
            "hook": post.content_hook or "",
            "summary": post.content_summary or "",
            "views": post.views or 0,
            "likes": post.likes or 0,
        })

    total = len(scores)
    avg_score = round(sum(scores) / total, 1) if total else 0

    # Top themes
    themes = [
        {"theme": t, "count": n, "pct": round(n / total * 100, 1)}
        for t, n in theme_counter.most_common(10)
    ]

    # Top tones
    tones = [
        {"tone": t, "count": n, "pct": round(n / total * 100, 1)}
        for t, n in tone_counter.most_common(10)
    ]

    # Top formats
    formats = [
        {"format": f, "count": n, "pct": round(n / total * 100, 1)}
        for f, n in format_counter.most_common(10)
    ]

    # Top hooks (by score)
    top_hooks = sorted(hooks, key=lambda h: h["score"], reverse=True)[:10]

    # Top hashtags
    top_hashtags = [
        {"hashtag": h, "count": n}
        for h, n in hashtag_counter.most_common(20)
    ]

    # Top performers
    top_performers = sorted(all_posts_data, key=lambda p: p["score"], reverse=True)[:10]

    # By competitor stats
    competitor_stats = []
    for comp, posts_list in by_competitor.items():
        comp_scores = [p["score"] for p in posts_list]
        comp_themes = Counter(p["theme"] for p in posts_list if p["theme"])
        top_theme = comp_themes.most_common(1)[0][0] if comp_themes else ""
        comp_tones = Counter(p["tone"] for p in posts_list if p["tone"])
        top_tone = comp_tones.most_common(1)[0][0] if comp_tones else ""
        total_views = sum(p["views"] for p in posts_list)
        total_likes = sum(p["likes"] for p in posts_list)
        competitor_stats.append({
            "competitor": comp,
            "count": len(posts_list),
            "avg_score": round(sum(comp_scores) / len(comp_scores), 1),
            "top_theme": top_theme,
            "top_tone": top_tone,
            "total_views": total_views,
            "total_likes": total_likes,
        })
    competitor_stats.sort(key=lambda c: c["avg_score"], reverse=True)

    # By platform stats
    platform_stats = []
    for plat, posts_list in by_platform.items():
        plat_scores = [p["score"] for p in posts_list]
        total_views = sum(p["views"] for p in posts_list)
        platform_stats.append({
            "platform": plat,
            "count": len(posts_list),
            "avg_score": round(sum(plat_scores) / len(plat_scores), 1),
            "total_views": total_views,
        })
    platform_stats.sort(key=lambda p: p["count"], reverse=True)

    # Recommendations
    recommendations = _generate_recommendations(
        themes=theme_counter,
        tones=tone_counter,
        formats=format_counter,
        competitor_stats=competitor_stats,
        platform_stats=platform_stats,
        avg_score=avg_score,
        total=total,
    )

    return {
        "total_analyzed": total,
        "avg_score": avg_score,
        "themes": themes,
        "tones": tones,
        "formats": formats,
        "top_hooks": top_hooks,
        "top_hashtags": top_hashtags,
        "top_performers": top_performers,
        "by_competitor": competitor_stats,
        "by_platform": platform_stats,
        "recommendations": recommendations,
    }


def _generate_recommendations(
    themes: Counter,
    tones: Counter,
    formats: Counter,
    competitor_stats: list,
    platform_stats: list,
    avg_score: float,
    total: int,
) -> list[str]:
    """Generate strategic content recommendations based on analysis data."""
    recs = []

    if not total:
        return recs

    # Top theme insight
    if themes:
        top_theme, top_count = themes.most_common(1)[0]
        pct = round(top_count / total * 100)
        recs.append(
            f"Le theme \"{top_theme}\" domine avec {pct}% des contenus. "
            f"Diversifiez vos themes pour toucher de nouvelles audiences."
        )

    # Tone gap
    if tones:
        top_tones = [t for t, _ in tones.most_common(3)]
        underused = [t for t in ("authentique", "communautaire", "educatif", "humour")
                     if t not in top_tones]
        if underused:
            recs.append(
                f"Les tons \"{underused[0]}\" et \"{underused[1] if len(underused) > 1 else 'inspirant'}\" "
                f"sont sous-exploites — une opportunite de differenciation sur les reseaux."
            )

    # Score leader
    if competitor_stats and len(competitor_stats) >= 2:
        leader = competitor_stats[0]
        recs.append(
            f"{leader['competitor']} a le meilleur score contenu moyen ({leader['avg_score']}/100) "
            f"avec une strategie axee \"{leader['top_theme']}\" / \"{leader['top_tone']}\"."
        )

    # Format insight
    if formats:
        top_format = formats.most_common(1)[0][0]
        if top_format == "short-form":
            recs.append(
                "Le format short-form domine. Testez des formats plus longs "
                "(tutorials, interviews) pour approfondir l'engagement."
            )
        elif top_format in ("long-form", "tutorial"):
            recs.append(
                "Les formats longs dominent. Integrez plus de contenus courts "
                "(reels, challenges) pour maximiser la portee."
            )

    # Platform insight
    if platform_stats:
        best_plat = max(platform_stats, key=lambda p: p["avg_score"])
        if best_plat["count"] >= 3:
            recs.append(
                f"La plateforme {best_plat['platform']} obtient le meilleur score moyen "
                f"({best_plat['avg_score']}/100). Renforcez votre presence sur ce canal."
            )

    return recs[:5]
