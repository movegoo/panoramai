"""
Creative Analysis Router.
AI-powered visual analysis of ad creatives using Claude Vision.
"""
import asyncio
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from database import get_db, Ad, Competitor, User, SystemSetting
from services.creative_analyzer import creative_analyzer
from core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/debug-db")
async def debug_creative_db(db: Session = Depends(get_db)):
    """Temporary debug endpoint — check creative analysis state in DB."""
    from sqlalchemy import func
    total = db.query(Ad).count()
    analyzed = db.query(Ad).filter(Ad.creative_analyzed_at.isnot(None)).count()
    with_score = db.query(Ad).filter(Ad.creative_score > 0).count()
    # Which competitors have analyzed ads?
    analyzed_by_comp = db.query(
        Competitor.id, Competitor.name, Competitor.user_id, func.count(Ad.id)
    ).join(Ad, Ad.competitor_id == Competitor.id).filter(
        Ad.creative_score > 0
    ).group_by(Competitor.id).all()
    comp_analysis = [{"id": c[0], "name": c[1], "user_id": c[2], "analyzed_count": c[3]} for c in analyzed_by_comp]
    # Users
    users = db.query(User).all()
    user_info = [{"id": u.id, "email": u.email} for u in users]
    # Advertisers
    from database import Advertiser
    advertisers = db.query(Advertiser).all()
    adv_info = [{"id": a.id, "name": a.name, "user_id": a.user_id} for a in advertisers]
    # Competitors with advertiser_id
    all_comps = db.query(Competitor).filter(Competitor.user_id == 1).all()
    comp_adv = [{"id": c.id, "name": c.name, "advertiser_id": c.advertiser_id} for c in all_comps]
    return {
        "total_ads": total,
        "analyzed": analyzed,
        "with_score": with_score,
        "users": user_info,
        "analyzed_by_competitor": comp_analysis,
        "advertisers": adv_info,
        "user1_competitors_advertiser_id": comp_adv,
    }

# Formats that have a static image to analyze
ANALYZABLE_FORMATS = {"IMAGE", "CAROUSEL", "DPA", "DCO", "", None}


def _normalize_platform(platform: str | None) -> str:
    if platform in ("tiktok",):
        return "tiktok"
    if platform in ("google",):
        return "google"
    return "meta"


@router.post("/analyze-all")
async def analyze_all_creatives(
    limit: int = Query(10, ge=1, le=200),
    force: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Batch-analyze ad creatives. Use force=true to re-analyze already analyzed ads."""
    if force:
        # Reset ALL analyzed ads so they get re-analyzed with current prompt
        reset_query = db.query(Ad).join(Competitor, Ad.competitor_id == Competitor.id).filter(
            Ad.creative_analyzed_at.isnot(None),
        )
        if user:
            reset_query = reset_query.filter(Competitor.user_id == user.id)
        if x_advertiser_id:
            reset_query = reset_query.filter(Competitor.advertiser_id == int(x_advertiser_id))
        reset_count = 0
        for ad in reset_query.all():
            ad.creative_analyzed_at = None
            ad.creative_score = None
            ad.creative_analysis = None
            ad.creative_concept = None
            ad.creative_tone = None
            ad.creative_hook = None
            ad.creative_summary = None
            ad.product_category = None
            ad.product_subcategory = None
            ad.ad_objective = None
            reset_count += 1
        db.commit()
        logger.info(f"Force mode: reset {reset_count} previously analyzed ads")
    else:
        # Auto-reset previous failures (score=0) so they can be retried
        reset_query = db.query(Ad).join(Competitor, Ad.competitor_id == Competitor.id).filter(
            Ad.creative_analyzed_at.isnot(None),
            Ad.creative_score == 0,
        )
        if user:
            reset_query = reset_query.filter(Competitor.user_id == user.id)
        if x_advertiser_id:
            reset_query = reset_query.filter(Competitor.advertiser_id == int(x_advertiser_id))
        for ad in reset_query.all():
            ad.creative_analyzed_at = None
            ad.creative_score = None
            ad.creative_analysis = None
        db.commit()

    query = db.query(Ad).join(Competitor, Ad.competitor_id == Competitor.id).filter(
        Ad.creative_analyzed_at.is_(None),
        Ad.creative_url.isnot(None),
        Ad.creative_url != "",
    )

    if user:
        query = query.filter(Competitor.user_id == user.id)
    if x_advertiser_id:
        query = query.filter(Competitor.advertiser_id == int(x_advertiser_id))

    # Skip VIDEO format and non-image URLs (Google Ads syndication, etc.)
    SKIP_URL_PATTERNS = ["googlesyndication.com", "2mdn.net", "doubleclick.net"]
    ads_to_analyze = []
    candidates = query.limit(limit * 3).all()
    for ad in candidates:
        fmt = (ad.display_format or "").upper()
        url = ad.creative_url or ""
        if fmt == "VIDEO":
            continue
        if any(p in url for p in SKIP_URL_PATTERNS):
            # Mark as analyzed with score=0 so we don't retry
            ad.creative_analyzed_at = datetime.utcnow()
            ad.creative_score = 0
            ad.creative_summary = "URL non analysable (réseau publicitaire)"
            continue
        if len(ads_to_analyze) < limit:
            ads_to_analyze.append(ad)
    db.commit()

    # Count remaining for this user
    remaining_query = db.query(Ad).filter(Ad.creative_analyzed_at.is_(None))
    if user:
        remaining_query = remaining_query.join(Competitor).filter(Competitor.user_id == user.id)
    if x_advertiser_id:
        remaining_query = remaining_query.filter(Competitor.advertiser_id == int(x_advertiser_id))

    if not ads_to_analyze:
        return {"message": "No ads to analyze", "analyzed": 0, "errors": 0, "remaining": remaining_query.count()}

    analyzed = 0
    errors = 0
    error_details = []
    MAX_TIME = 90  # Max 90 seconds per batch
    start_time = asyncio.get_event_loop().time()
    timed_out = False

    for ad in ads_to_analyze:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= MAX_TIME:
            timed_out = True
            break

        try:
            result = await asyncio.wait_for(
                creative_analyzer.analyze_creative(
                    creative_url=ad.creative_url,
                    ad_text=ad.ad_text or "",
                    platform=_normalize_platform(ad.platform),
                    ad_id=ad.ad_id or "",
                ),
                timeout=60,
            )

            if result:
                ad.creative_analysis = json.dumps(result, ensure_ascii=False)
                ad.creative_concept = result.get("concept", "")[:100]
                ad.creative_hook = result.get("hook", "")[:500]
                ad.creative_tone = result.get("tone", "")[:100]
                ad.creative_text_overlay = result.get("text_overlay", "")
                ad.creative_dominant_colors = json.dumps(result.get("dominant_colors", []))
                ad.creative_has_product = result.get("has_product", False)
                ad.creative_has_face = result.get("has_face", False)
                ad.creative_has_logo = result.get("has_logo", False)
                ad.creative_layout = result.get("layout", "")[:50]
                ad.creative_cta_style = result.get("cta_style", "")[:50]
                ad.creative_score = result.get("score", 0)
                ad.creative_tags = json.dumps(result.get("tags", []), ensure_ascii=False)
                ad.creative_summary = result.get("summary", "")
                ad.product_category = result.get("product_category", "")[:100]
                ad.product_subcategory = result.get("product_subcategory", "")[:100]
                ad.ad_objective = result.get("ad_objective", "")[:50]
                ad.creative_analyzed_at = datetime.utcnow()
                analyzed += 1
            else:
                ad.creative_analyzed_at = datetime.utcnow()
                ad.creative_score = 0
                errors += 1
                error_details.append(f"{ad.ad_id}: returned None (url={ad.creative_url[:80] if ad.creative_url else 'empty'})")

        except asyncio.TimeoutError:
            logger.warning(f"Timeout analyzing ad {ad.ad_id}, skipping")
            errors += 1
            error_details.append(f"{ad.ad_id}: timeout")
        except Exception as e:
            logger.error(f"Error analyzing ad {ad.ad_id}: {e}")
            ad.creative_analyzed_at = datetime.utcnow()
            ad.creative_score = 0
            errors += 1
            error_details.append(f"{ad.ad_id}: {str(e)[:120]}")

        await asyncio.sleep(1.0)

    db.commit()

    remaining_query = db.query(Ad).filter(Ad.creative_analyzed_at.is_(None))
    if user:
        remaining_query = remaining_query.join(Competitor).filter(Competitor.user_id == user.id)
    if x_advertiser_id:
        remaining_query = remaining_query.filter(Competitor.advertiser_id == int(x_advertiser_id))
    remaining = remaining_query.count()

    return {
        "message": f"Analyzed {analyzed} ad creatives" + (f" (time limit reached, {remaining} remaining)" if timed_out else ""),
        "analyzed": analyzed,
        "errors": errors,
        "remaining": remaining,
        "timed_out": timed_out,
        "error_details": error_details[:10] if error_details else [],
    }


@router.post("/set-key")
async def set_api_key(
    key: str = Query(..., min_length=10),
    db: Session = Depends(get_db),
):
    """Store the Anthropic API key in the database (Railway env var workaround)."""
    row = db.query(SystemSetting).filter(SystemSetting.key == "ANTHROPIC_API_KEY").first()
    if row:
        row.value = key
        row.updated_at = datetime.utcnow()
    else:
        db.add(SystemSetting(key="ANTHROPIC_API_KEY", value=key))
    db.commit()
    return {"message": "API key saved", "key_preview": f"{key[:12]}...{key[-4:]}"}


@router.post("/reset-failed")
async def reset_failed_analyses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Reset ads that were marked as analyzed but have score=0 (failed analyses)."""
    query = db.query(Ad).join(Competitor, Ad.competitor_id == Competitor.id).filter(
        Ad.creative_analyzed_at.isnot(None),
        Ad.creative_score == 0,
    )

    if user:
        query = query.filter(Competitor.user_id == user.id)
    if x_advertiser_id:
        query = query.filter(Competitor.advertiser_id == int(x_advertiser_id))

    ads = query.all()
    count = 0
    for ad in ads:
        ad.creative_analyzed_at = None
        ad.creative_score = None
        ad.creative_analysis = None
        count += 1

    db.commit()
    return {"reset": count, "message": f"{count} failed analyses reset, ready for re-analysis"}


@router.get("/insights")
async def get_creative_insights(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """Aggregated creative intelligence across all analyzed ads."""
    try:
        return _compute_insights(db, user, x_advertiser_id)
    except Exception as e:
        logger.error(f"Error computing creative insights: {e}", exc_info=True)
        return {
            "total_analyzed": 0,
            "avg_score": 0,
            "concepts": [],
            "tones": [],
            "top_hooks": [],
            "colors": [],
            "top_performers": [],
            "by_competitor": [],
            "categories": [],
            "subcategories": [],
            "objectives": [],
            "recommendations": [],
            "signals": [],
            "geo_analysis": [],
            "error": str(e),
        }


def _compute_insights(db: Session, user: User | None, x_advertiser_id: str | None):
    query = db.query(Ad, Competitor.name).join(
        Competitor, Ad.competitor_id == Competitor.id
    ).filter(
        Ad.creative_analyzed_at.isnot(None),
        Ad.creative_score > 0,
    )

    if user:
        query = query.filter(Competitor.user_id == user.id)
    if x_advertiser_id:
        query = query.filter(Competitor.advertiser_id == int(x_advertiser_id))

    rows = query.all()

    if not rows:
        return {
            "total_analyzed": 0,
            "avg_score": 0,
            "concepts": [],
            "tones": [],
            "top_hooks": [],
            "colors": [],
            "top_performers": [],
            "by_competitor": [],
            "recommendations": [],
            "signals": [],
            "geo_analysis": [],
        }

    # Aggregate data
    scores = []
    concept_counter = Counter()
    tone_counter = Counter()
    color_counter = Counter()
    layout_counter = Counter()
    cta_counter = Counter()
    category_counter = Counter()
    subcategory_counter = Counter()
    objective_counter = Counter()
    hooks = []
    by_competitor: dict[str, list] = {}
    all_ads_data = []

    for ad, comp_name in rows:
        score = ad.creative_score or 0
        scores.append(score)

        if ad.creative_concept:
            concept_counter[ad.creative_concept] += 1
        if ad.creative_tone:
            tone_counter[ad.creative_tone] += 1
        if ad.creative_layout:
            layout_counter[ad.creative_layout] += 1
        if ad.creative_cta_style:
            cta_counter[ad.creative_cta_style] += 1
        if ad.product_category:
            category_counter[ad.product_category] += 1
        if ad.product_subcategory:
            subcategory_counter[ad.product_subcategory] += 1
        if ad.ad_objective:
            objective_counter[ad.ad_objective] += 1

        # Parse colors
        try:
            colors = json.loads(ad.creative_dominant_colors) if ad.creative_dominant_colors else []
            for c in colors:
                color_counter[c] += 1
        except (json.JSONDecodeError, TypeError):
            pass

        # Hooks with scores
        if ad.creative_hook and score > 0:
            hooks.append({
                "hook": ad.creative_hook,
                "score": score,
                "concept": ad.creative_concept or "",
                "competitor": comp_name,
            })

        # By competitor
        if comp_name not in by_competitor:
            by_competitor[comp_name] = []
        by_competitor[comp_name].append({
            "score": score,
            "concept": ad.creative_concept,
            "tone": ad.creative_tone,
        })

        # For top performers
        all_ads_data.append({
            "ad_id": ad.ad_id,
            "competitor_name": comp_name,
            "creative_url": ad.creative_url,
            "score": score,
            "concept": ad.creative_concept or "",
            "tone": ad.creative_tone or "",
            "summary": ad.creative_summary or "",
            "hook": ad.creative_hook or "",
            "layout": ad.creative_layout or "",
            "has_face": ad.creative_has_face,
            "has_product": ad.creative_has_product,
            "product_category": ad.product_category or "",
            "product_subcategory": ad.product_subcategory or "",
            "ad_objective": ad.ad_objective or "",
        })

    total = len(scores)
    avg_score = round(sum(scores) / total, 1) if total else 0

    # Top concepts
    concepts = [
        {"concept": c, "count": n, "pct": round(n / total * 100, 1)}
        for c, n in concept_counter.most_common(10)
    ]

    # Top tones
    tones = [
        {"tone": t, "count": n, "pct": round(n / total * 100, 1)}
        for t, n in tone_counter.most_common(10)
    ]

    # Top hooks (by score)
    top_hooks = sorted(hooks, key=lambda h: h["score"], reverse=True)[:10]

    # Top colors
    colors = [
        {"color": c, "count": n}
        for c, n in color_counter.most_common(15)
    ]

    # Top performers
    top_performers = sorted(all_ads_data, key=lambda a: a["score"], reverse=True)[:10]

    # By competitor stats
    competitor_stats = []
    for comp, ads_list in by_competitor.items():
        comp_scores = [a["score"] for a in ads_list]
        comp_concepts = Counter(a["concept"] for a in ads_list if a["concept"])
        top_concept = comp_concepts.most_common(1)[0][0] if comp_concepts else ""
        comp_tones = Counter(a["tone"] for a in ads_list if a["tone"])
        top_tone = comp_tones.most_common(1)[0][0] if comp_tones else ""
        competitor_stats.append({
            "competitor": comp,
            "count": len(ads_list),
            "avg_score": round(sum(comp_scores) / len(comp_scores), 1),
            "top_concept": top_concept,
            "top_tone": top_tone,
        })
    competitor_stats.sort(key=lambda c: c["avg_score"], reverse=True)

    # Generate recommendations
    recommendations = _generate_recommendations(
        concepts=concept_counter,
        tones=tone_counter,
        layouts=layout_counter,
        competitor_stats=competitor_stats,
        avg_score=avg_score,
        total=total,
    )

    # Product categories
    categories = [
        {"category": c, "count": n, "pct": round(n / total * 100, 1)}
        for c, n in category_counter.most_common(20)
    ]

    # Sub-categories
    subcategories = [
        {"subcategory": s, "count": n, "pct": round(n / total * 100, 1)}
        for s, n in subcategory_counter.most_common(20)
    ]

    # Ad objectives
    objectives = [
        {"objective": o, "count": n, "pct": round(n / total * 100, 1)}
        for o, n in objective_counter.most_common(10)
    ]

    # Generate JARVIS signals
    signals = _generate_signals(
        all_ads_data=all_ads_data,
        competitor_stats=competitor_stats,
        category_counter=category_counter,
        tone_counter=tone_counter,
        total=total,
        rows=rows,
    )

    # Build geo analysis
    geo_analysis = _build_geo_analysis(rows)

    return {
        "total_analyzed": total,
        "avg_score": avg_score,
        "concepts": concepts,
        "tones": tones,
        "top_hooks": top_hooks,
        "colors": colors,
        "top_performers": top_performers,
        "by_competitor": competitor_stats,
        "categories": categories,
        "subcategories": subcategories,
        "objectives": objectives,
        "recommendations": recommendations,
        "signals": signals,
        "geo_analysis": geo_analysis,
    }


def _generate_recommendations(
    concepts: Counter,
    tones: Counter,
    layouts: Counter,
    competitor_stats: list,
    avg_score: float,
    total: int,
) -> list[str]:
    """Generate strategic creative recommendations based on analysis data."""
    recs = []

    if not total:
        return recs

    # Top concept insight
    if concepts:
        top_concept, top_count = concepts.most_common(1)[0]
        pct = round(top_count / total * 100)
        recs.append(
            f"Le concept \"{top_concept}\" domine avec {pct}% des visuels. "
            f"Testez des approches alternatives pour vous différencier."
        )

    # Tone gap
    if tones:
        top_tones = [t for t, _ in tones.most_common(3)]
        underused = [t for t in ("humour", "ugc", "pédagogique", "communauté")
                     if t not in top_tones]
        if underused:
            recs.append(
                f"Les tons \"{underused[0]}\" et \"{underused[1] if len(underused) > 1 else 'bold'}\" "
                f"sont sous-exploités par vos concurrents — une opportunité de différenciation."
            )

    # Score leader
    if competitor_stats and len(competitor_stats) >= 2:
        leader = competitor_stats[0]
        recs.append(
            f"{leader['competitor']} a le meilleur score créatif moyen ({leader['avg_score']}/100) "
            f"avec une stratégie axée \"{leader['top_concept']}\" / \"{leader['top_tone']}\"."
        )

    # Layout insight
    if layouts:
        top_layout = layouts.most_common(1)[0][0]
        if top_layout in ("text-heavy", "texte-dominant"):
            recs.append(
                "La majorité des visuels sont chargés en texte. "
                "Des visuels plus épurés (minimaliste, hero) pourraient mieux performer."
            )
        elif top_layout in ("single-image", "minimal", "image-unique", "minimaliste"):
            recs.append(
                "Les visuels minimalistes dominent. Testez des formats plus riches "
                "(collage, split, avant-après) pour vous démarquer."
            )

    # Face/product insight
    # (would need aggregate data — keep simple for now)
    if len(recs) < 3:
        recs.append(
            "Analysez les hooks des pubs les mieux notées pour identifier "
            "les accroches visuelles les plus efficaces de votre secteur."
        )

    return recs[:5]


def _generate_signals(
    all_ads_data: list[dict],
    competitor_stats: list[dict],
    category_counter: Counter,
    tone_counter: Counter,
    total: int,
    rows: list,
) -> list[dict]:
    """Generate JARVIS intelligence signals from competitive analysis data."""
    signals = []
    if not total or not competitor_stats:
        return signals

    # Build per-competitor breakdowns
    comp_categories: dict[str, Counter] = defaultdict(Counter)
    comp_formats: dict[str, Counter] = defaultdict(Counter)
    comp_tones: dict[str, Counter] = defaultdict(Counter)
    comp_prices: dict[str, dict] = defaultdict(lambda: {"total": 0, "with_price": 0})
    comp_recent: dict[str, int] = defaultdict(int)
    comp_locations: dict[str, Counter] = defaultdict(Counter)

    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    for ad, comp_name in rows:
        # Categories
        if ad.product_category:
            comp_categories[comp_name][ad.product_category] += 1

        # Formats
        fmt = (ad.display_format or "IMAGE").upper()
        comp_formats[comp_name][fmt] += 1

        # Tones
        if ad.creative_tone:
            comp_tones[comp_name][ad.creative_tone] += 1

        # Price detection (from creative analysis)
        comp_prices[comp_name]["total"] += 1
        try:
            analysis = json.loads(ad.creative_analysis) if ad.creative_analysis else {}
            if analysis.get("has_price"):
                comp_prices[comp_name]["with_price"] += 1
        except (json.JSONDecodeError, TypeError):
            pass

        # Recent surge
        if ad.ad_delivery_start_time:
            try:
                start = datetime.fromisoformat(str(ad.ad_delivery_start_time).replace("Z", "+00:00")).replace(tzinfo=None)
                if start >= seven_days_ago:
                    comp_recent[comp_name] += 1
            except (ValueError, TypeError):
                pass

        # Geo (location_audience)
        if ad.location_audience:
            try:
                locations = json.loads(ad.location_audience) if isinstance(ad.location_audience, str) else ad.location_audience
                if isinstance(locations, list):
                    for loc in locations:
                        name = loc.get("name", "") if isinstance(loc, dict) else str(loc)
                        if name:
                            comp_locations[comp_name][name] += 1
            except (json.JSONDecodeError, TypeError):
                pass

    # Signal: category_push (≥30% in one category)
    for comp_name, cats in comp_categories.items():
        comp_total = sum(cats.values())
        if comp_total < 3:
            continue
        top_cat, top_count = cats.most_common(1)[0]
        pct = round(top_count / comp_total * 100)
        if pct >= 30:
            signals.append({
                "type": "category_push",
                "icon": "Target",
                "title": f"{comp_name} concentre {pct}% sur {top_cat}",
                "description": f"{comp_name} consacre {pct}% de ses publicités à la catégorie \"{top_cat}\" ({top_count} pubs sur {comp_total}). Une stratégie de positionnement claire.",
                "competitor": comp_name,
                "metric": f"{pct}%",
                "severity": "high" if pct >= 50 else "medium",
            })

    # Signal: score_leader (avg_score ≥ 75)
    if competitor_stats:
        leader = competitor_stats[0]
        if leader["avg_score"] >= 75:
            signals.append({
                "type": "score_leader",
                "icon": "Trophy",
                "title": f"{leader['competitor']} domine en qualité créative",
                "description": f"{leader['competitor']} a le meilleur score créatif moyen ({leader['avg_score']}/100) sur {leader['count']} publicités analysées. Stratégie : {leader['top_concept']} / {leader['top_tone']}.",
                "competitor": leader["competitor"],
                "metric": f"{leader['avg_score']}/100",
                "severity": "high",
            })

    # Signal: format_dominant (≥50% one format)
    for comp_name, fmts in comp_formats.items():
        fmt_total = sum(fmts.values())
        if fmt_total < 3:
            continue
        top_fmt, top_count = fmts.most_common(1)[0]
        pct = round(top_count / fmt_total * 100)
        if pct >= 50:
            fmt_label = {"VIDEO": "la vidéo", "IMAGE": "l'image statique", "CAROUSEL": "le carrousel"}.get(top_fmt, top_fmt)
            signals.append({
                "type": "format_dominant",
                "icon": "Layers",
                "title": f"{comp_name} mise sur {fmt_label} ({pct}%)",
                "description": f"{comp_name} utilise {fmt_label} dans {pct}% de ses créatifs ({top_count}/{fmt_total}). Un choix de format assumé.",
                "competitor": comp_name,
                "metric": f"{pct}%",
                "severity": "medium",
            })

    # Signal: tone_shift (dominant tone different from market)
    if len(comp_tones) >= 2:
        market_top_tones = set(t for t, _ in tone_counter.most_common(2))
        for comp_name, tones in comp_tones.items():
            if sum(tones.values()) < 3:
                continue
            top_tone = tones.most_common(1)[0][0]
            if top_tone not in market_top_tones:
                signals.append({
                    "type": "tone_shift",
                    "icon": "Palette",
                    "title": f"{comp_name} se démarque avec un ton {top_tone}",
                    "description": f"Alors que le marché privilégie {', '.join(market_top_tones)}, {comp_name} adopte un ton \"{top_tone}\" différenciateur.",
                    "competitor": comp_name,
                    "metric": top_tone,
                    "severity": "medium",
                })

    # Signal: price_strategy (≥40% with price)
    for comp_name, price_data in comp_prices.items():
        if price_data["total"] < 3:
            continue
        pct = round(price_data["with_price"] / price_data["total"] * 100)
        if pct >= 40:
            signals.append({
                "type": "price_strategy",
                "icon": "Tag",
                "title": f"{comp_name} affiche des prix ({pct}% des pubs)",
                "description": f"{comp_name} intègre des prix dans {pct}% de ses visuels. Une stratégie agressive de conversion directe.",
                "competitor": comp_name,
                "metric": f"{pct}%",
                "severity": "high" if pct >= 60 else "medium",
            })

    # Signal: recent_surge (≥5 new ads in 7 days)
    for comp_name, count in comp_recent.items():
        if count >= 5:
            signals.append({
                "type": "recent_surge",
                "icon": "TrendingUp",
                "title": f"{comp_name} a lancé {count} pubs cette semaine",
                "description": f"{comp_name} a démarré {count} nouvelles publicités dans les 7 derniers jours. Une campagne en cours ou un temps fort commercial.",
                "competitor": comp_name,
                "metric": str(count),
                "severity": "high" if count >= 10 else "medium",
            })

    # Signal: geo_concentration
    for comp_name, locs in comp_locations.items():
        loc_total = sum(locs.values())
        if loc_total < 3:
            continue
        top_loc, top_count = locs.most_common(1)[0]
        pct = round(top_count / loc_total * 100)
        if pct >= 40:
            signals.append({
                "type": "geo_concentration",
                "icon": "MapPin",
                "title": f"{comp_name} concentre ses pubs sur {top_loc}",
                "description": f"{comp_name} cible {top_loc} dans {pct}% de ses publicités géo-ciblées ({top_count}/{loc_total}).",
                "competitor": comp_name,
                "metric": f"{pct}%",
                "severity": "medium",
            })

    # Sort by severity (high first), then limit
    severity_order = {"high": 0, "medium": 1, "low": 2}
    signals.sort(key=lambda s: severity_order.get(s["severity"], 2))
    return signals[:7]


def _build_geo_analysis(rows: list) -> list[dict]:
    """Build geographic analysis from location_audience data."""
    location_stats: dict[str, dict] = {}

    for ad, comp_name in rows:
        if not ad.location_audience:
            continue
        try:
            locations = json.loads(ad.location_audience) if isinstance(ad.location_audience, str) else ad.location_audience
            if not isinstance(locations, list):
                continue
            for loc in locations:
                name = loc.get("name", "") if isinstance(loc, dict) else str(loc)
                if not name:
                    continue
                if name not in location_stats:
                    location_stats[name] = {"ad_count": 0, "competitors": set(), "categories": Counter()}
                location_stats[name]["ad_count"] += 1
                location_stats[name]["competitors"].add(comp_name)
                if ad.product_category:
                    location_stats[name]["categories"][ad.product_category] += 1
        except (json.JSONDecodeError, TypeError):
            pass

    # Convert to list, sort by ad_count
    geo = []
    for loc_name, data in location_stats.items():
        top_cat = data["categories"].most_common(1)[0][0] if data["categories"] else ""
        geo.append({
            "location": loc_name,
            "ad_count": data["ad_count"],
            "competitors": sorted(data["competitors"]),
            "top_category": top_cat,
        })

    geo.sort(key=lambda g: g["ad_count"], reverse=True)
    return geo[:15]
