"""
Social Content Analysis Router.
Collect social posts, analyze with AI, aggregate insights.
"""
import asyncio
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from database import get_db, Competitor, User, SocialPost, Advertiser
from services.scrapecreators import scrapecreators
from services.social_content_analyzer import social_content_analyzer
from core.auth import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/collect-all")
async def collect_all_social_posts(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    x_advertiser_id: str | None = Header(None),
):
    """Collect recent posts/videos from TikTok, YouTube, Instagram for all active competitors."""
    query = db.query(Competitor).filter(Competitor.is_active == True)
    if user:
        query = query.filter(Competitor.user_id == user.id)
    if x_advertiser_id:
        query = query.filter(Competitor.advertiser_id == int(x_advertiser_id))
    competitors = query.all()

    if not competitors:
        return {"message": "No competitors found", "new": 0, "updated": 0, "total_in_db": 0, "by_competitor": [], "errors": []}

    total_new = 0
    total_updated = 0
    results = []
    errors_list = []

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
                errors_list.append(f"TikTok/{comp.name}: {str(e)[:100]}")

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
                errors_list.append(f"YouTube/{comp.name}: {str(e)[:100]}")

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
                errors_list.append(f"Instagram/{comp.name}: {str(e)[:100]}")

        results.append(comp_result)

    db.commit()

    total_posts = db.query(SocialPost).count()
    if user:
        total_posts_query = db.query(SocialPost).join(Competitor).filter(Competitor.user_id == user.id)
        if x_advertiser_id:
            total_posts_query = total_posts_query.filter(Competitor.advertiser_id == int(x_advertiser_id))
        total_posts = total_posts_query.count()

    return {
        "message": f"Collected {total_new} new posts, updated {total_updated}",
        "new": total_new,
        "updated": total_updated,
        "total_in_db": total_posts,
        "by_competitor": results,
        "errors": errors_list,
        "competitors_scanned": len(competitors),
    }


@router.post("/analyze-all")
async def analyze_all_content(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    x_advertiser_id: str | None = Header(None),
):
    """Batch-analyze social posts that haven't been analyzed yet."""
    # Auto-reset previous failures (score=0)
    reset_query = db.query(SocialPost).join(Competitor, SocialPost.competitor_id == Competitor.id).filter(
        SocialPost.content_analyzed_at.isnot(None),
        SocialPost.content_engagement_score == 0,
    )
    if user:
        reset_query = reset_query.filter(Competitor.user_id == user.id)
    if x_advertiser_id:
        reset_query = reset_query.filter(Competitor.advertiser_id == int(x_advertiser_id))
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
    if x_advertiser_id:
        query = query.filter(Competitor.advertiser_id == int(x_advertiser_id))

    posts_to_analyze = query.limit(limit).all()

    remaining_query = db.query(SocialPost).filter(SocialPost.content_analyzed_at.is_(None))
    if user:
        remaining_query = remaining_query.join(Competitor).filter(Competitor.user_id == user.id)
    if x_advertiser_id:
        remaining_query = remaining_query.filter(Competitor.advertiser_id == int(x_advertiser_id))

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
    MAX_TIME = 90  # Max 90 seconds per batch to avoid hanging requests
    start_time = asyncio.get_event_loop().time()
    timed_out = False

    for post in posts_to_analyze:
        # Check time budget before each post
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= MAX_TIME:
            timed_out = True
            break

        try:
            result = await asyncio.wait_for(
                social_content_analyzer.analyze_content(
                    title=post.title or "",
                    description=post.description or "",
                    platform=post.platform or "tiktok",
                    competitor_name=comp_names.get(post.competitor_id, ""),
                    views=post.views or 0,
                    likes=post.likes or 0,
                    comments=post.comments or 0,
                    shares=post.shares or 0,
                ),
                timeout=30,
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

        except asyncio.TimeoutError:
            logger.warning(f"Timeout analyzing post {post.post_id}, skipping")
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
    if x_advertiser_id:
        remaining_query = remaining_query.filter(Competitor.advertiser_id == int(x_advertiser_id))

    remaining = remaining_query.count()
    return {
        "message": f"Analyzed {analyzed} social posts" + (f" (time limit reached, {remaining} remaining)" if timed_out else ""),
        "analyzed": analyzed,
        "errors": errors,
        "remaining": remaining,
        "timed_out": timed_out,
    }


@router.get("/insights")
async def get_content_insights(
    platform: str | None = Query(None, description="Filter by platform: tiktok, youtube, instagram"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    x_advertiser_id: str | None = Header(None),
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
    if x_advertiser_id:
        query = query.filter(Competitor.advertiser_id == int(x_advertiser_id))
    if platform:
        query = query.filter(SocialPost.platform == platform.lower())

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

        # Parse hashtags (strip leading # to avoid double ##)
        try:
            tags = json.loads(post.content_hashtags) if post.content_hashtags else []
            for t in tags:
                if t:
                    hashtag_counter[t.lstrip("#")] += 1
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

    # --- Best tone by engagement ---
    tone_engagement = defaultdict(list)
    for post, _ in rows:
        if post.content_tone and post.content_engagement_score:
            tone_engagement[post.content_tone].append(post.content_engagement_score)
    best_tone_engagement = None
    if tone_engagement:
        best = max(tone_engagement.items(), key=lambda x: sum(x[1]) / len(x[1]))
        best_tone_engagement = {
            "tone": best[0],
            "avg_score": round(sum(best[1]) / len(best[1]), 1),
            "count": len(best[1]),
        }

    # --- Posting frequency & timing analysis ---
    posting_frequency = _build_posting_frequency(rows)
    posting_timing = _build_posting_timing(rows)

    # Get brand name for recommendations
    brand_query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        brand_query = brand_query.filter(Advertiser.user_id == user.id)
    if x_advertiser_id:
        brand_query = brand_query.filter(Advertiser.id == int(x_advertiser_id))
    brand = brand_query.first()
    brand_name = brand.company_name if brand else "Ma marque"

    # Recommendations
    recommendations = _generate_recommendations(
        themes=theme_counter,
        tones=tone_counter,
        formats=format_counter,
        competitor_stats=competitor_stats,
        platform_stats=platform_stats,
        avg_score=avg_score,
        total=total,
        posting_timing=posting_timing,
        posting_frequency=posting_frequency,
        brand_name=brand_name,
        all_posts_data=all_posts_data,
        rows=rows,
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
        "posting_frequency": posting_frequency,
        "posting_timing": posting_timing,
        "best_tone_engagement": best_tone_engagement,
        "recommendations": recommendations,
    }


def _build_posting_frequency(rows) -> dict:
    """Compute posting frequency stats: avg per month, per week, by competitor."""
    DAY_LABELS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    by_competitor = defaultdict(list)
    for post, comp_name in rows:
        if post.published_at:
            by_competitor[comp_name].append(post.published_at)

    competitor_freq = []
    for comp, dates in by_competitor.items():
        if len(dates) < 2:
            competitor_freq.append({
                "competitor": comp,
                "total_posts": len(dates),
                "avg_per_week": 0,
                "avg_per_month": 0,
            })
            continue

        dates_sorted = sorted(dates)
        span_days = max((dates_sorted[-1] - dates_sorted[0]).days, 1)
        span_weeks = max(span_days / 7, 1)
        span_months = max(span_days / 30, 1)

        competitor_freq.append({
            "competitor": comp,
            "total_posts": len(dates),
            "avg_per_week": round(len(dates) / span_weeks, 1),
            "avg_per_month": round(len(dates) / span_months, 1),
        })

    competitor_freq.sort(key=lambda c: c["avg_per_week"], reverse=True)

    # Day of week distribution across all posts
    day_counts = Counter()
    for post, _ in rows:
        if post.published_at:
            day_counts[post.published_at.weekday()] += 1

    day_distribution = [
        {"day": DAY_LABELS[i], "day_index": i, "count": day_counts.get(i, 0)}
        for i in range(7)
    ]

    return {
        "by_competitor": competitor_freq,
        "day_distribution": day_distribution,
    }


def _build_posting_timing(rows) -> dict:
    """Analyze posting hours and find best day/hour for engagement."""
    DAY_LABELS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    hour_counts = Counter()
    hour_engagement = defaultdict(list)
    day_hour_engagement = defaultdict(list)
    by_competitor_hours = defaultdict(lambda: Counter())

    for post, comp_name in rows:
        if not post.published_at:
            continue

        hour = post.published_at.hour
        day = post.published_at.weekday()
        engagement = (post.likes or 0) + (post.comments or 0) * 2 + (post.shares or 0) * 3

        hour_counts[hour] += 1
        hour_engagement[hour].append(engagement)
        day_hour_engagement[(day, hour)].append(engagement)
        by_competitor_hours[comp_name][hour] += 1

    # Hour distribution
    hour_distribution = []
    for h in range(24):
        engs = hour_engagement.get(h, [])
        hour_distribution.append({
            "hour": h,
            "label": f"{h:02d}h",
            "count": hour_counts.get(h, 0),
            "avg_engagement": round(sum(engs) / len(engs)) if engs else 0,
        })

    # Best day/hour combos by engagement
    best_slots = []
    for (day, hour), engs in day_hour_engagement.items():
        if len(engs) >= 1:
            best_slots.append({
                "day": DAY_LABELS[day],
                "day_index": day,
                "hour": hour,
                "label": f"{DAY_LABELS[day]} {hour:02d}h",
                "posts": len(engs),
                "avg_engagement": round(sum(engs) / len(engs)),
            })
    best_slots.sort(key=lambda s: s["avg_engagement"], reverse=True)

    # Peak hours by competitor
    competitor_peak_hours = []
    for comp, hours in by_competitor_hours.items():
        if hours:
            peak_hour = hours.most_common(1)[0][0]
            competitor_peak_hours.append({
                "competitor": comp,
                "peak_hour": peak_hour,
                "peak_label": f"{peak_hour:02d}h",
                "posts_at_peak": hours[peak_hour],
            })

    return {
        "hour_distribution": hour_distribution,
        "best_slots": best_slots[:10],
        "competitor_peak_hours": competitor_peak_hours,
    }


def _generate_recommendations(
    themes: Counter,
    tones: Counter,
    formats: Counter,
    competitor_stats: list,
    platform_stats: list,
    avg_score: float,
    total: int,
    posting_timing: dict = None,
    posting_frequency: dict = None,
    brand_name: str = "Auchan",
    all_posts_data: list = None,
    rows: list = None,
) -> list[str]:
    """Generate expert community management recommendations based on engagement data."""
    recs = []

    if not total:
        return recs

    # --- 1. High-engagement competitor strategy to replicate ---
    if competitor_stats and len(competitor_stats) >= 2:
        leader = competitor_stats[0]
        # Find brand stats
        brand_stats = next((c for c in competitor_stats if c["competitor"].lower() == brand_name.lower()), None)

        if leader["avg_score"] >= 60:
            recs.append(
                f"{leader['competitor']} obtient le meilleur engagement ({leader['avg_score']}/100) "
                f"avec un ton \"{leader['top_tone']}\" sur le theme \"{leader['top_theme']}\". "
                f"Inspirez-vous de cette approche pour vos prochains contenus."
            )

        # Brand gap
        if brand_stats and leader["competitor"].lower() != brand_name.lower():
            gap = leader["avg_score"] - brand_stats["avg_score"]
            if gap > 10:
                recs.append(
                    f"Ecart d'engagement de {gap:.0f} points entre {leader['competitor']} et {brand_name}. "
                    f"Analysez leurs posts les plus performants et adaptez leur strategie "
                    f"(\"{leader['top_theme']}\" / \"{leader['top_tone']}\") a votre marque."
                )

    # --- 2. Best posting time recommendation ---
    if posting_timing and posting_timing.get("best_slots"):
        best = posting_timing["best_slots"][0]
        recs.append(
            f"Le creneau {best['label']} genere le plus d'engagement (moy. {best['avg_engagement']:,} interactions). "
            f"Planifiez vos publications cles sur ce creneau pour maximiser la visibilite."
        )

    # --- 3. Posting frequency benchmark ---
    if posting_frequency and posting_frequency.get("by_competitor"):
        freq_list = posting_frequency["by_competitor"]
        most_active = freq_list[0] if freq_list else None
        brand_freq = next((f for f in freq_list if f["competitor"].lower() == brand_name.lower()), None)

        if most_active and brand_freq and most_active["competitor"].lower() != brand_name.lower():
            if most_active["avg_per_week"] > brand_freq["avg_per_week"] * 1.5:
                recs.append(
                    f"{most_active['competitor']} publie {most_active['avg_per_week']:.1f}x/semaine "
                    f"contre {brand_freq['avg_per_week']:.1f}x pour {brand_name}. "
                    f"Augmentez la cadence a au moins {max(most_active['avg_per_week'] * 0.8, brand_freq['avg_per_week'] + 1):.0f} posts/semaine."
                )
        elif most_active and not brand_freq:
            recs.append(
                f"{most_active['competitor']} est le plus actif avec {most_active['avg_per_week']:.1f} posts/semaine. "
                f"Visez au minimum ce rythme pour rester competitif."
            )

    # --- 4. High-engagement content to replicate ---
    if all_posts_data:
        high_eng = [p for p in all_posts_data if p["score"] >= 70]
        if high_eng:
            top_themes_eng = Counter(p["theme"] for p in high_eng if p["theme"])
            if top_themes_eng:
                best_theme, best_count = top_themes_eng.most_common(1)[0]
                pct = round(best_count / len(high_eng) * 100)
                recs.append(
                    f"{pct}% des contenus a fort engagement (score 70+) portent sur le theme \"{best_theme}\". "
                    f"Doublez la production sur cette thematique."
                )

    # --- 5. Tone that drives engagement ---
    if rows and tones:
        tone_engagement = defaultdict(list)
        for post, _ in rows:
            if post.content_tone and post.content_engagement_score:
                tone_engagement[post.content_tone].append(post.content_engagement_score)
        if tone_engagement:
            best_tone = max(tone_engagement.items(), key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0)
            avg_eng = round(sum(best_tone[1]) / len(best_tone[1]), 1)
            if avg_eng > avg_score:
                recs.append(
                    f"Le ton \"{best_tone[0]}\" genere un score moyen de {avg_eng}/100, "
                    f"au-dessus de la moyenne ({avg_score}/100). Privilegiez ce ton dans vos publications."
                )

    # --- 6. Platform-specific insight ---
    if platform_stats:
        best_plat = max(platform_stats, key=lambda p: p["avg_score"])
        worst_plat = min(platform_stats, key=lambda p: p["avg_score"]) if len(platform_stats) >= 2 else None
        if best_plat["count"] >= 3:
            recs.append(
                f"{best_plat['platform'].title()} obtient le meilleur engagement moyen "
                f"({best_plat['avg_score']}/100). "
                + (f"A l'inverse, {worst_plat['platform'].title()} est en retrait ({worst_plat['avg_score']}/100) — "
                   f"revoyez votre strategie sur cette plateforme."
                   if worst_plat and worst_plat["avg_score"] < best_plat["avg_score"] - 10 else
                   "Renforcez votre presence sur ce canal.")
            )

    # --- 7. Day of week insight ---
    if posting_frequency and posting_frequency.get("day_distribution"):
        days = posting_frequency["day_distribution"]
        if any(d["count"] > 0 for d in days):
            best_day = max(days, key=lambda d: d["count"])
            recs.append(
                f"La majorite des publications tombent le {best_day['day']}. "
                f"Testez d'autres jours pour eviter la saturation et capter l'attention."
            )

    return recs[:7]
