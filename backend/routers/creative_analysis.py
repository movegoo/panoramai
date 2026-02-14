"""
Creative Analysis Router.
AI-powered visual analysis of ad creatives using Claude Vision.
"""
import asyncio
import json
import logging
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db, Ad, Competitor, User
from services.creative_analyzer import creative_analyzer
from core.auth import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter()

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
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Batch-analyze ad creatives that haven't been analyzed yet."""
    # Auto-reset previous failures (score=0) so they can be retried
    reset_query = db.query(Ad).join(Competitor, Ad.competitor_id == Competitor.id).filter(
        Ad.creative_analyzed_at.isnot(None),
        Ad.creative_score == 0,
    )
    if user:
        reset_query = reset_query.filter(Competitor.user_id == user.id)
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

    # Skip VIDEO format (no static image)
    ads_to_analyze = []
    candidates = query.limit(limit * 2).all()
    for ad in candidates:
        fmt = (ad.display_format or "").upper()
        if fmt != "VIDEO" and len(ads_to_analyze) < limit:
            ads_to_analyze.append(ad)

    # Count remaining for this user
    remaining_query = db.query(Ad).filter(Ad.creative_analyzed_at.is_(None))
    if user:
        remaining_query = remaining_query.join(Competitor).filter(Competitor.user_id == user.id)

    if not ads_to_analyze:
        return {"message": "No ads to analyze", "analyzed": 0, "errors": 0, "remaining": remaining_query.count()}

    analyzed = 0
    errors = 0
    error_details = []

    for ad in ads_to_analyze:
        try:
            result = await creative_analyzer.analyze_creative(
                creative_url=ad.creative_url,
                ad_text=ad.ad_text or "",
                platform=_normalize_platform(ad.platform),
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
                ad.creative_analyzed_at = datetime.utcnow()
                analyzed += 1
            else:
                # Mark as processed to avoid retry loop
                ad.creative_analyzed_at = datetime.utcnow()
                ad.creative_score = 0
                errors += 1
                error_details.append(f"{ad.ad_id}: returned None (url={ad.creative_url[:80] if ad.creative_url else 'empty'})")

        except Exception as e:
            logger.error(f"Error analyzing ad {ad.ad_id}: {e}")
            ad.creative_analyzed_at = datetime.utcnow()
            ad.creative_score = 0
            errors += 1
            error_details.append(f"{ad.ad_id}: {str(e)[:120]}")

        # Rate limiting
        await asyncio.sleep(1.0)

    db.commit()

    remaining_query = db.query(Ad).filter(Ad.creative_analyzed_at.is_(None))
    if user:
        remaining_query = remaining_query.join(Competitor).filter(Competitor.user_id == user.id)
    remaining = remaining_query.count()

    return {
        "message": f"Analyzed {analyzed} ad creatives",
        "analyzed": analyzed,
        "errors": errors,
        "remaining": remaining,
        "error_details": error_details[:10] if error_details else [],
    }


@router.post("/reset-failed")
async def reset_failed_analyses(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Reset ads that were marked as analyzed but have score=0 (failed analyses)."""
    query = db.query(Ad).join(Competitor, Ad.competitor_id == Competitor.id).filter(
        Ad.creative_analyzed_at.isnot(None),
        Ad.creative_score == 0,
    )

    if user:
        query = query.filter(Competitor.user_id == user.id)

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
    user: User | None = Depends(get_optional_user),
):
    """Aggregated creative intelligence across all analyzed ads."""
    query = db.query(Ad, Competitor.name).join(
        Competitor, Ad.competitor_id == Competitor.id
    ).filter(
        Ad.creative_analyzed_at.isnot(None),
        Ad.creative_score > 0,
    )

    if user:
        query = query.filter(Competitor.user_id == user.id)

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
        }

    # Aggregate data
    scores = []
    concept_counter = Counter()
    tone_counter = Counter()
    color_counter = Counter()
    layout_counter = Counter()
    cta_counter = Counter()
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

    return {
        "total_analyzed": total,
        "avg_score": avg_score,
        "concepts": concepts,
        "tones": tones,
        "top_hooks": top_hooks,
        "colors": colors,
        "top_performers": top_performers,
        "by_competitor": competitor_stats,
        "recommendations": recommendations,
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
        underused = [t for t in ("humor", "ugc-style", "educational", "community")
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
        if top_layout == "text-heavy":
            recs.append(
                "La majorité des visuels sont chargés en texte. "
                "Des visuels plus épurés (minimal, hero-image) pourraient mieux performer."
            )
        elif top_layout in ("single-image", "minimal"):
            recs.append(
                "Les visuels minimalistes dominent. Testez des formats plus riches "
                "(collage, split, before-after) pour vous démarquer."
            )

    # Face/product insight
    # (would need aggregate data — keep simple for now)
    if len(recs) < 3:
        recs.append(
            "Analysez les hooks des pubs les mieux notées pour identifier "
            "les accroches visuelles les plus efficaces de votre secteur."
        )

    return recs[:5]
