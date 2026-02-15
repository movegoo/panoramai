"""
GEO (Generative Engine Optimization) Tracking.
Track brand visibility in AI engine responses (Claude, Gemini, ChatGPT).
"""
import json
import logging
from datetime import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Competitor, GeoResult, Advertiser, SerpResult, User
from services.geo_analyzer import geo_analyzer, get_geo_queries
from core.auth import get_optional_user
from core.sectors import get_sector_label

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_user_competitors(db: Session, user: User | None) -> list[Competitor]:
    query = db.query(Competitor).filter(Competitor.is_active == True)
    if user:
        query = query.filter(Competitor.user_id == user.id)
    return query.all()


def _get_user_brand(db: Session, user: User | None) -> Advertiser | None:
    query = db.query(Advertiser).filter(Advertiser.is_active == True)
    if user:
        query = query.filter(Advertiser.user_id == user.id)
    return query.first()


@router.post("/track")
async def track_geo(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Run GEO tracking: query Claude + Gemini + ChatGPT, analyse brand mentions."""
    competitors = _get_user_competitors(db, user)
    if not competitors:
        return {"error": "No competitors configured", "tracked_queries": 0}

    brand = _get_user_brand(db, user)
    sector = brand.sector if brand else "supermarche"
    sector_label = get_sector_label(sector) if brand else "Grande Distribution"

    comp_map = {c.name.lower(): c for c in competitors}
    brand_names = [c.name for c in competitors]

    results, errors = await geo_analyzer.run_full_analysis(brand_names, sector=sector, sector_label=sector_label)

    now = datetime.utcnow()
    total_mentions = 0
    matched = set()

    # Determine active platforms
    active_platforms = set()

    for r in results:
        active_platforms.add(r["platform"])
        # Match brand name to competitor
        name_lower = r["brand_name"].lower()
        comp = comp_map.get(name_lower)
        if not comp:
            # Fuzzy: check if brand name is contained in any competitor name
            for cname, c in comp_map.items():
                if name_lower in cname or cname in name_lower:
                    comp = c
                    break

        geo = GeoResult(
            keyword=r["keyword"],
            query=r["query"],
            platform=r["platform"],
            raw_answer=r["raw_answer"],
            analysis=r["analysis"],
            competitor_id=comp.id if comp else None,
            mentioned=True,
            position_in_answer=r["position_in_answer"],
            recommended=r["recommended"],
            sentiment=r["sentiment"],
            context_snippet=r["context_snippet"],
            primary_recommendation=r["primary_recommendation"],
            recorded_at=now,
        )
        db.add(geo)
        total_mentions += 1
        if comp:
            matched.add(comp.id)

    db.commit()

    queries = get_geo_queries(sector, sector_label, brand_names)

    # Report which platforms are configured
    available = geo_analyzer.get_available_platforms()

    response = {
        "tracked_queries": len(queries),
        "platforms": sorted(active_platforms) if active_platforms else [],
        "platforms_configured": available,
        "total_mentions": total_mentions,
        "matched_competitors": len(matched),
    }
    if errors:
        response["errors"] = errors
    if total_mentions == 0 and not any(available.values()):
        response["warning"] = "Aucune cle API configuree (ANTHROPIC_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, MISTRAL_API_KEY). Ajoutez-les dans les variables d'environnement."
    elif total_mentions == 0:
        response["warning"] = "Les API ont ete appelees mais aucune mention n'a ete detectee. Verifiez les erreurs ci-dessus."

    return response


@router.get("/results")
async def get_results(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Get latest GEO tracking results grouped by keyword + platform."""
    competitors = _get_user_competitors(db, user)
    comp_names = {c.id: c.name for c in competitors}

    latest = db.query(func.max(GeoResult.recorded_at)).scalar()
    if not latest:
        return {"queries": [], "last_tracked": None}

    rows = (
        db.query(GeoResult)
        .filter(GeoResult.recorded_at == latest)
        .order_by(GeoResult.keyword, GeoResult.platform, GeoResult.position_in_answer)
        .all()
    )

    grouped: dict[str, dict] = {}
    for r in rows:
        key = r.keyword
        if key not in grouped:
            grouped[key] = {
                "keyword": r.keyword,
                "query": r.query,
                "platforms": {"claude": [], "gemini": [], "chatgpt": [], "mistral": []},
            }

        mention = {
            "competitor_name": comp_names.get(r.competitor_id, r.context_snippet[:30] if r.context_snippet else "Inconnu"),
            "competitor_id": r.competitor_id,
            "position_in_answer": r.position_in_answer,
            "recommended": r.recommended,
            "sentiment": r.sentiment,
            "context": r.context_snippet,
        }

        if r.platform in grouped[key]["platforms"]:
            grouped[key]["platforms"][r.platform].append(mention)

    return {
        "queries": list(grouped.values()),
        "last_tracked": latest.isoformat() if latest else None,
    }


@router.get("/insights")
async def get_insights(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Aggregated GEO insights: share of voice, recommendations, platform comparison."""
    competitors = _get_user_competitors(db, user)
    valid_ids = {c.id for c in competitors}
    comp_names = {c.id: c.name for c in competitors}

    brand = _get_user_brand(db, user)
    brand_comp = None
    if brand:
        brand_comp = next((c for c in competitors if c.name == brand.company_name), None)

    latest = db.query(func.max(GeoResult.recorded_at)).scalar()
    if not latest:
        return {
            "total_queries": 0, "platforms": [], "last_tracked": None,
            "brand_name": brand.company_name if brand else None,
            "brand_competitor_id": brand_comp.id if brand_comp else None,
            "share_of_voice": [], "avg_position": [], "recommendation_rate": [],
            "sentiment": [], "platform_comparison": [], "key_criteria": [],
            "missing_keywords": [], "seo_vs_geo": [], "recommendations": [],
        }

    rows = (
        db.query(GeoResult)
        .filter(GeoResult.recorded_at == latest, GeoResult.mentioned == True)
        .all()
    )

    # Unique keyword-platform combos = total possible slots
    all_keywords = sorted(set(r.keyword for r in rows))
    total_queries = len(all_keywords)

    # Detect active platforms
    active_platforms = sorted(set(r.platform for r in rows))

    # --- Share of Voice ---
    mentions_by_comp = defaultdict(int)
    for r in rows:
        if r.competitor_id and r.competitor_id in valid_ids:
            mentions_by_comp[r.competitor_id] += 1

    total_mentions = sum(mentions_by_comp.values()) or 1
    share_of_voice = sorted([
        {
            "competitor": comp_names[cid],
            "competitor_id": cid,
            "mentions": count,
            "pct": round(count / total_mentions * 100, 1),
        }
        for cid, count in mentions_by_comp.items()
    ], key=lambda x: -x["mentions"])

    # --- Average Position ---
    positions_by_comp = defaultdict(list)
    for r in rows:
        if r.competitor_id and r.competitor_id in valid_ids and r.position_in_answer:
            positions_by_comp[r.competitor_id].append(r.position_in_answer)

    avg_position = sorted([
        {
            "competitor": comp_names[cid],
            "competitor_id": cid,
            "avg_pos": round(sum(ps) / len(ps), 1),
        }
        for cid, ps in positions_by_comp.items()
    ], key=lambda x: x["avg_pos"])

    # --- Recommendation Rate ---
    rec_by_comp = defaultdict(lambda: {"total": 0, "recommended": 0})
    for r in rows:
        if r.competitor_id and r.competitor_id in valid_ids:
            rec_by_comp[r.competitor_id]["total"] += 1
            if r.recommended:
                rec_by_comp[r.competitor_id]["recommended"] += 1

    recommendation_rate = sorted([
        {
            "competitor": comp_names[cid],
            "competitor_id": cid,
            "rate": round(d["recommended"] / d["total"] * 100, 1) if d["total"] else 0,
            "recommended_count": d["recommended"],
        }
        for cid, d in rec_by_comp.items()
    ], key=lambda x: -x["rate"])

    # --- Sentiment ---
    sent_by_comp = defaultdict(lambda: {"positif": 0, "neutre": 0, "negatif": 0})
    for r in rows:
        if r.competitor_id and r.competitor_id in valid_ids:
            s = r.sentiment or "neutre"
            if s in sent_by_comp[r.competitor_id]:
                sent_by_comp[r.competitor_id][s] += 1

    sentiment = [
        {
            "competitor": comp_names[cid],
            "competitor_id": cid,
            "positive": d["positif"],
            "neutral": d["neutre"],
            "negative": d["negatif"],
        }
        for cid, d in sent_by_comp.items()
    ]

    # --- Platform Comparison ---
    plat_by_comp = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r.competitor_id and r.competitor_id in valid_ids:
            plat_by_comp[r.competitor_id][r.platform] += 1

    # Count total mentions per platform for percentage
    platform_totals = defaultdict(int)
    for r in rows:
        platform_totals[r.platform] += 1

    platform_comparison = []
    for cid, plats in plat_by_comp.items():
        entry = {
            "competitor": comp_names[cid],
            "competitor_id": cid,
        }
        for p in active_platforms:
            entry[f"{p}_mentions"] = plats.get(p, 0)
            entry[f"{p}_pct"] = round(plats.get(p, 0) / platform_totals[p] * 100, 1) if platform_totals.get(p) else 0
        platform_comparison.append(entry)

    # --- Key Criteria ---
    criteria_counts = defaultdict(int)
    seen_analyses = set()
    for r in rows:
        if r.analysis and r.analysis not in seen_analyses:
            seen_analyses.add(r.analysis)
            try:
                a = json.loads(r.analysis)
                for c in a.get("key_criteria", []):
                    criteria_counts[c] += 1
            except Exception:
                pass

    key_criteria = sorted([
        {"criterion": c, "count": n}
        for c, n in criteria_counts.items()
    ], key=lambda x: -x["count"])

    # --- Missing Keywords ---
    present_keywords = defaultdict(set)
    for r in rows:
        if r.competitor_id and r.competitor_id in valid_ids:
            present_keywords[r.competitor_id].add(r.keyword)

    all_kw_set = set(all_keywords)
    missing_keywords = []
    for cid, name in comp_names.items():
        missing = sorted(all_kw_set - present_keywords.get(cid, set()))
        if missing:
            missing_keywords.append({
                "competitor": name,
                "competitor_id": cid,
                "keywords": missing,
            })
    missing_keywords.sort(key=lambda x: -len(x["keywords"]))

    # --- SEO vs GEO comparison ---
    seo_vs_geo = []
    seo_latest = db.query(func.max(SerpResult.recorded_at)).scalar()
    if seo_latest:
        seo_rows = db.query(SerpResult).filter(SerpResult.recorded_at == seo_latest).all()
        seo_total = len(seo_rows) or 1
        seo_appearances = defaultdict(int)
        for sr in seo_rows:
            if sr.competitor_id and sr.competitor_id in valid_ids:
                seo_appearances[sr.competitor_id] += 1

        for cid, name in comp_names.items():
            seo_pct = round(seo_appearances.get(cid, 0) / seo_total * 100, 1)
            geo_pct = round(mentions_by_comp.get(cid, 0) / total_mentions * 100, 1)
            seo_vs_geo.append({
                "competitor": name,
                "competitor_id": cid,
                "seo_pct": seo_pct,
                "geo_pct": geo_pct,
                "gap": round(geo_pct - seo_pct, 1),
            })

    # --- Recommendations ---
    recommendations = _generate_recommendations(
        brand_comp, comp_names, share_of_voice, avg_position,
        recommendation_rate, missing_keywords, seo_vs_geo,
    )

    return {
        "total_queries": total_queries,
        "platforms": active_platforms or ["claude", "gemini", "chatgpt", "mistral"],
        "last_tracked": latest.isoformat(),
        "brand_name": brand.company_name if brand else None,
        "brand_competitor_id": brand_comp.id if brand_comp else None,
        "share_of_voice": share_of_voice,
        "avg_position": avg_position,
        "recommendation_rate": recommendation_rate,
        "sentiment": sentiment,
        "platform_comparison": platform_comparison,
        "key_criteria": key_criteria,
        "missing_keywords": missing_keywords,
        "seo_vs_geo": seo_vs_geo,
        "recommendations": recommendations,
    }


def _generate_recommendations(
    brand_comp, comp_names, sov, avg_pos, rec_rate, missing_kw, seo_geo
) -> list[str]:
    recs = []
    brand_name = brand_comp.name if brand_comp else None
    brand_id = brand_comp.id if brand_comp else None

    if not brand_name:
        return []

    brand_sov = next((s for s in sov if s["competitor_id"] == brand_id), None)
    leader_sov = sov[0] if sov else None

    # Missing keywords
    brand_missing = next((m for m in missing_kw if m["competitor_id"] == brand_id), None)
    if brand_missing and brand_missing["keywords"]:
        kws = ", ".join(brand_missing["keywords"][:3])
        recs.append(
            f"{brand_name} n'est pas mentionne par les IA sur {len(brand_missing['keywords'])} requete(s) : {kws}. "
            f"Creer du contenu de reference (guides, comparatifs) sur ces sujets pour influencer les reponses IA."
        )

    # Share of voice gap
    if brand_sov and leader_sov and leader_sov["competitor_id"] != brand_id:
        gap = leader_sov["pct"] - brand_sov["pct"]
        if gap > 5:
            recs.append(
                f"{leader_sov['competitor']} domine la visibilite IA avec {leader_sov['pct']}% de part de voix "
                f"contre {brand_sov['pct']}% pour {brand_name}. Renforcer la presence editoriale et les mentions web."
            )

    # Recommendation rate
    brand_rec = next((r for r in rec_rate if r["competitor_id"] == brand_id), None)
    leader_rec = rec_rate[0] if rec_rate else None
    if brand_rec and leader_rec and leader_rec["competitor_id"] != brand_id:
        if leader_rec["rate"] - brand_rec["rate"] > 10:
            recs.append(
                f"{leader_rec['competitor']} est recommande dans {leader_rec['rate']}% des reponses IA "
                f"contre {brand_rec['rate']}% pour {brand_name}. Travailler le positionnement prix et service."
            )

    # SEO vs GEO gap
    brand_gap = next((g for g in seo_geo if g["competitor_id"] == brand_id), None)
    if brand_gap and brand_gap["gap"] < -10:
        recs.append(
            f"Ecart SEO/GEO pour {brand_name} : {brand_gap['seo_pct']}% en SEO vs {brand_gap['geo_pct']}% en GEO. "
            f"La visibilite IA est en retard sur le SEO classique — optimiser le contenu pour les moteurs generatifs."
        )

    # Average position
    brand_avg = next((a for a in avg_pos if a["competitor_id"] == brand_id), None)
    if brand_avg and brand_avg["avg_pos"] > 2.5:
        recs.append(
            f"Position moyenne de {brand_name} dans les reponses IA : {brand_avg['avg_pos']:.1f}. "
            f"Viser la 1ere mention en renforcant l'autorite de marque et les sources citables."
        )

    if not brand_sov:
        recs.append(
            f"{brand_name} n'est mentionne dans aucune reponse IA. "
            f"Urgence GEO : creer une strategie de contenu ciblee pour apparaitre dans les reponses des moteurs generatifs."
        )

    return recs[:5]
