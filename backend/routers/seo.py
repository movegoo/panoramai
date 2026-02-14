"""
SEO / SERP Tracking — Track Google organic positions for competitors.
Uses ScrapeCreators /v1/google/search endpoint.
Only matches against the current user's own competitors.
"""
import asyncio
import logging
from datetime import datetime
from urllib.parse import urlparse
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Competitor, SerpResult, Advertiser, User
from services.scrapecreators import scrapecreators
from core.auth import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_KEYWORDS = [
    "courses en ligne",
    "drive supermarché",
    "livraison courses domicile",
    "promo supermarché",
    "carte fidélité supermarché",
    "supermarché pas cher",
    "courses en ligne drive",
    "catalogue promotion supermarché",
    "application courses",
    "drive retrait gratuit",
    "produits bio supermarché",
    "marque distributeur",
    "click and collect courses",
    "meilleur supermarché",
    "comparatif prix supermarché",
]

# Extra domain aliases for matching
DOMAIN_ALIASES = {
    "leclercdrive.fr": "leclerc.fr",
    "e-leclerc.com": "leclerc.fr",
    "e.leclerc": "leclerc.fr",
}


def _extract_domain(url: str) -> str:
    """Extract clean domain from a URL."""
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _get_user_competitors(db: Session, user: User | None) -> list[Competitor]:
    """Get active competitors scoped to user."""
    query = db.query(Competitor).filter(Competitor.is_active == True)
    if user:
        query = query.filter(Competitor.user_id == user.id)
    return query.all()


def _build_domain_map(competitors: list[Competitor]) -> dict[str, int]:
    """Build domain -> competitor_id mapping from user's competitors only."""
    domain_map = {}
    for c in competitors:
        if c.website:
            d = _extract_domain(c.website)
            if d:
                domain_map[d] = c.id
    # Add known aliases
    for alias, canonical in DOMAIN_ALIASES.items():
        if canonical in domain_map:
            domain_map[alias] = domain_map[canonical]
    return domain_map


def _match_competitor(domain: str, domain_map: dict[str, int]) -> int | None:
    """Match a result domain to a competitor_id."""
    if not domain:
        return None
    if domain in domain_map:
        return domain_map[domain]
    for known_domain, cid in domain_map.items():
        if domain.endswith("." + known_domain):
            return cid
    return None


@router.post("/track")
async def track_serp(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Run SERP tracking for default keywords. Only matches user's own competitors."""
    competitors = _get_user_competitors(db, user)
    if not competitors:
        return {"error": "No competitors configured", "tracked_keywords": 0, "total_results": 0}

    domain_map = _build_domain_map(competitors)
    valid_ids = {c.id for c in competitors}

    now = datetime.utcnow()
    total_results = 0
    matched_count = 0
    errors = []
    credits = None

    for i, keyword in enumerate(DEFAULT_KEYWORDS):
        try:
            data = await scrapecreators.search_google(keyword, country="FR", limit=10)
            if not data.get("success"):
                errors.append({"keyword": keyword, "error": data.get("error", "Unknown")})
                continue

            credits = data.get("credits_remaining")

            results = data.get("results", [])
            for pos_idx, result in enumerate(results[:10], start=1):
                url = result.get("url", "")
                domain = _extract_domain(url)
                cid = _match_competitor(domain, domain_map)

                # Only assign competitor_id if it belongs to this user
                if cid and cid not in valid_ids:
                    cid = None

                serp = SerpResult(
                    keyword=keyword,
                    position=pos_idx,
                    competitor_id=cid,
                    title=result.get("title", "")[:1000],
                    url=url[:1000],
                    snippet=result.get("description", ""),
                    domain=domain,
                    recorded_at=now,
                )
                db.add(serp)
                total_results += 1
                if cid:
                    matched_count += 1

        except Exception as e:
            logger.error(f"SERP track error for '{keyword}': {e}")
            errors.append({"keyword": keyword, "error": str(e)})

        if i < len(DEFAULT_KEYWORDS) - 1:
            await asyncio.sleep(0.3)

    db.commit()

    return {
        "tracked_keywords": len(DEFAULT_KEYWORDS) - len(errors),
        "total_results": total_results,
        "matched_competitors": matched_count,
        "errors": errors if errors else None,
        "credits_remaining": credits,
    }


@router.get("/rankings")
async def get_rankings(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Get latest SERP rankings. Only shows user's own competitors."""
    competitors = _get_user_competitors(db, user)
    valid_ids = {c.id for c in competitors}
    comp_names = {c.id: c.name for c in competitors}

    latest = db.query(func.max(SerpResult.recorded_at)).scalar()
    if not latest:
        return {"keywords": [], "last_tracked": None}

    results = (
        db.query(SerpResult)
        .filter(SerpResult.recorded_at == latest)
        .order_by(SerpResult.keyword, SerpResult.position)
        .all()
    )

    keywords_data = defaultdict(list)
    for r in results:
        # Only label as competitor if it's one of the user's
        cid = r.competitor_id if r.competitor_id and r.competitor_id in valid_ids else None
        keywords_data[r.keyword].append({
            "position": r.position,
            "competitor_name": comp_names.get(cid) if cid else None,
            "competitor_id": cid,
            "domain": r.domain,
            "title": r.title,
            "url": r.url,
        })

    keywords = [
        {"keyword": kw, "results": res}
        for kw, res in sorted(keywords_data.items())
    ]

    return {
        "keywords": keywords,
        "last_tracked": latest.isoformat() if latest else None,
    }


@router.get("/insights")
async def get_insights(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Aggregated SEO insights. Scoped to user's own competitors."""
    competitors = _get_user_competitors(db, user)
    valid_ids = {c.id for c in competitors}
    comp_names = {c.id: c.name for c in competitors}

    brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()
    brand_comp = None
    if brand:
        brand_comp = next((c for c in competitors if c.name == brand.company_name), None)

    latest = db.query(func.max(SerpResult.recorded_at)).scalar()
    if not latest:
        return {
            "total_keywords": 0, "last_tracked": None,
            "share_of_voice": [], "avg_position": [], "best_keywords": [],
            "missing_keywords": [], "top_domains": [], "recommendations": [],
        }

    results = (
        db.query(SerpResult)
        .filter(SerpResult.recorded_at == latest)
        .all()
    )

    all_keywords = sorted(set(r.keyword for r in results))
    total_keywords = len(all_keywords)
    total_slots = len(results)

    # --- Share of Voice (user's competitors only) ---
    appearances = defaultdict(int)
    for r in results:
        cid = r.competitor_id
        if cid and cid in valid_ids:
            appearances[cid] += 1

    share_of_voice = sorted([
        {
            "competitor": comp_names[cid],
            "competitor_id": cid,
            "appearances": count,
            "pct": round(count / total_slots * 100, 1) if total_slots else 0,
        }
        for cid, count in appearances.items()
    ], key=lambda x: -x["appearances"])

    # --- Average Position ---
    positions_by_comp = defaultdict(list)
    for r in results:
        if r.competitor_id and r.competitor_id in valid_ids:
            positions_by_comp[r.competitor_id].append(r.position)

    avg_position = sorted([
        {
            "competitor": comp_names[cid],
            "competitor_id": cid,
            "avg_pos": round(sum(pos_list) / len(pos_list), 1),
            "keywords_in_top10": len(pos_list),
        }
        for cid, pos_list in positions_by_comp.items()
    ], key=lambda x: x["avg_pos"])

    # --- Best Keywords (position 1-3) ---
    best_keywords = []
    for r in results:
        if r.competitor_id and r.competitor_id in valid_ids and r.position <= 3:
            best_keywords.append({
                "competitor": comp_names[r.competitor_id],
                "competitor_id": r.competitor_id,
                "keyword": r.keyword,
                "position": r.position,
            })
    best_keywords.sort(key=lambda x: x["position"])

    # --- Missing Keywords ---
    present_keywords = defaultdict(set)
    for r in results:
        if r.competitor_id and r.competitor_id in valid_ids:
            present_keywords[r.competitor_id].add(r.keyword)

    missing_keywords = []
    for cid, name in comp_names.items():
        missing = sorted(set(all_keywords) - present_keywords.get(cid, set()))
        if missing:
            missing_keywords.append({
                "competitor": name,
                "competitor_id": cid,
                "keywords": missing,
            })
    missing_keywords.sort(key=lambda x: -len(x["keywords"]))

    # --- Top Domains ---
    domain_counts = defaultdict(int)
    for r in results:
        if r.domain:
            domain_counts[r.domain] += 1

    top_domains = sorted([
        {"domain": d, "count": c}
        for d, c in domain_counts.items()
    ], key=lambda x: -x["count"])[:15]

    # --- Recommendations ---
    recommendations = _generate_recommendations(
        brand_comp, comp_names, share_of_voice, avg_position,
        best_keywords, missing_keywords, top_domains
    )

    return {
        "total_keywords": total_keywords,
        "last_tracked": latest.isoformat(),
        "share_of_voice": share_of_voice,
        "avg_position": avg_position,
        "best_keywords": best_keywords,
        "missing_keywords": missing_keywords,
        "top_domains": top_domains,
        "recommendations": recommendations,
    }


def _generate_recommendations(
    brand_comp, comp_names, sov, avg_pos, best_kw, missing_kw, top_domains
) -> list[str]:
    """Generate actionable SEO recommendations."""
    recs = []
    brand_name = brand_comp.name if brand_comp else "Auchan"
    brand_id = brand_comp.id if brand_comp else None

    brand_sov = next((s for s in sov if s["competitor_id"] == brand_id), None)
    leader_sov = sov[0] if sov else None

    # 1. Missing keywords alert
    brand_missing = next((m for m in missing_kw if m["competitor_id"] == brand_id), None)
    if brand_missing and brand_missing["keywords"]:
        kws = ", ".join(brand_missing["keywords"][:3])
        recs.append(
            f"{brand_name} est absent du top 10 sur {len(brand_missing['keywords'])} mot(s)-clé(s) : {kws}. "
            f"Prioriser la création de contenu SEO sur ces requêtes."
        )

    # 2. Share of voice gap
    if brand_sov and leader_sov and leader_sov["competitor_id"] != brand_id:
        gap = leader_sov["pct"] - brand_sov["pct"]
        if gap > 5:
            recs.append(
                f"{leader_sov['competitor']} domine la visibilité SEO avec {leader_sov['pct']}% de part de voix "
                f"contre {brand_sov['pct']}% pour {brand_name}. Écart de {gap:.0f} points à combler."
            )

    # 3. Average position
    brand_avg = next((a for a in avg_pos if a["competitor_id"] == brand_id), None)
    if brand_avg and brand_avg["avg_pos"] > 5:
        recs.append(
            f"Position moyenne de {brand_name} : {brand_avg['avg_pos']:.1f}/10. "
            f"Optimiser les pages existantes (balises title, meta description, contenu) pour remonter dans le top 5."
        )

    # 4. Competitors in top 3
    for entry in best_kw[:5]:
        if entry["competitor_id"] != brand_id and entry["position"] == 1:
            recs.append(
                f"{entry['competitor']} est en position 1 sur \"{entry['keyword']}\". "
                f"Analyser leur page et créer un contenu plus complet pour les dépasser."
            )
            break

    # 5. Generic if no brand data
    if not brand_sov:
        recs.append(
            f"{brand_name} n'apparaît dans aucun résultat du top 10. "
            f"Urgence SEO : auditer le site et lancer une stratégie de contenu ciblée."
        )

    return recs[:5]
