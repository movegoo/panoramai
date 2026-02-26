"""Tool: get_gmb_scoring — Scoring Google My Business des concurrents."""
from sqlalchemy import func

from competitive_mcp.db import (
    get_session, get_all_competitors, find_competitor,
    Competitor, StoreLocation,
)
from competitive_mcp.formatting import format_number, format_rating, format_percent


def get_gmb_scoring(
    competitor_name: str | None = None,
    department: str | None = None,
) -> str:
    """Scoring GMB national : note moyenne, avis, score composite, classement."""
    db = get_session()
    try:
        if competitor_name:
            competitors = []
            comp = find_competitor(db, competitor_name)
            if comp:
                competitors = [comp]
            else:
                return f"Concurrent « {competitor_name} » non trouvé."
        else:
            competitors = get_all_competitors(db, include_brand=True)

        if not competitors:
            return "Aucun concurrent configuré."

        rankings = []

        for comp in competitors:
            query = db.query(StoreLocation).filter(StoreLocation.competitor_id == comp.id)
            if department:
                query = query.filter(StoreLocation.department == department)

            total = query.count()
            if total == 0:
                continue

            with_rating = query.filter(StoreLocation.google_rating.isnot(None)).count()
            with_score = query.filter(StoreLocation.gmb_score.isnot(None)).count()

            avg_rating = db.query(func.avg(StoreLocation.google_rating)).filter(
                StoreLocation.competitor_id == comp.id,
                StoreLocation.google_rating.isnot(None),
                *([StoreLocation.department == department] if department else []),
            ).scalar()

            avg_reviews = db.query(func.avg(StoreLocation.google_reviews_count)).filter(
                StoreLocation.competitor_id == comp.id,
                StoreLocation.google_reviews_count.isnot(None),
                *([StoreLocation.department == department] if department else []),
            ).scalar()

            avg_score = db.query(func.avg(StoreLocation.gmb_score)).filter(
                StoreLocation.competitor_id == comp.id,
                StoreLocation.gmb_score.isnot(None),
                *([StoreLocation.department == department] if department else []),
            ).scalar()

            total_reviews = db.query(func.sum(StoreLocation.google_reviews_count)).filter(
                StoreLocation.competitor_id == comp.id,
                StoreLocation.google_reviews_count.isnot(None),
                *([StoreLocation.department == department] if department else []),
            ).scalar() or 0

            # Completeness: count stores with extended GMB fields
            completeness_fields = [
                StoreLocation.google_phone,
                StoreLocation.google_website,
                StoreLocation.google_hours,
                StoreLocation.google_thumbnail,
                StoreLocation.google_type,
            ]
            field_counts = []
            for field in completeness_fields:
                cnt = query.filter(field.isnot(None)).count()
                field_counts.append(cnt)
            completeness_pct = round(sum(field_counts) / (len(completeness_fields) * total) * 100, 1) if total > 0 else 0

            rankings.append({
                "name": comp.name,
                "is_brand": bool(comp.is_brand),
                "total_stores": total,
                "stores_with_rating": with_rating,
                "stores_with_score": with_score,
                "avg_rating": round(avg_rating, 2) if avg_rating else None,
                "avg_reviews": round(avg_reviews, 1) if avg_reviews else None,
                "total_reviews": total_reviews,
                "avg_score": round(avg_score, 1) if avg_score else None,
                "completeness_pct": completeness_pct,
            })

        # Sort by avg_score descending, then avg_rating
        rankings.sort(key=lambda x: (x["avg_score"] or 0, x["avg_rating"] or 0), reverse=True)

        if not rankings:
            return "Aucune donnée de magasin disponible."

        scope = f" (département {department})" if department else " (national)"
        lines = [f"# Scoring Google My Business{scope}", ""]

        # Market averages
        all_ratings = [r["avg_rating"] for r in rankings if r["avg_rating"]]
        all_scores = [r["avg_score"] for r in rankings if r["avg_score"]]
        if all_ratings:
            market_avg_rating = sum(all_ratings) / len(all_ratings)
            lines.append(f"**Note moyenne du marché** : {format_rating(market_avg_rating)}")
        if all_scores:
            market_avg_score = sum(all_scores) / len(all_scores)
            lines.append(f"**Score GMB moyen du marché** : {market_avg_score:.0f}/100")
        lines.append("")

        # Ranking table
        lines.append("## Classement")
        for i, r in enumerate(rankings):
            marker = " ⭐" if r["is_brand"] else ""
            score_str = f"Score {r['avg_score']:.0f}/100" if r["avg_score"] else "Score N/A"
            rating_str = format_rating(r["avg_rating"])
            lines.append(
                f"{i + 1}. **{r['name']}**{marker} — {score_str} | "
                f"Note {rating_str} | {format_number(r['total_reviews'])} avis | "
                f"{r['total_stores']} magasins | Complétude {r['completeness_pct']:.0f}%"
            )

        # Top / Flop if multiple competitors
        if len(rankings) > 1:
            lines.append("")
            leader = rankings[0]
            lines.append(f"**Leader GMB** : {leader['name']} ({format_rating(leader['avg_rating'])}, {format_number(leader['total_reviews'])} avis)")

            # Find brand position
            brand = next((r for r in rankings if r["is_brand"]), None)
            if brand:
                brand_rank = next(i + 1 for i, r in enumerate(rankings) if r["is_brand"])
                lines.append(f"**Votre position** : #{brand_rank}/{len(rankings)}")
                if brand["avg_rating"] and leader["avg_rating"]:
                    gap = leader["avg_rating"] - brand["avg_rating"]
                    if gap > 0:
                        lines.append(f"**Écart avec le leader** : {gap:+.2f} pts de note")

        return "\n".join(lines)
    finally:
        db.close()
