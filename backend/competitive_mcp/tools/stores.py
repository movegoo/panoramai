"""Tool: get_store_locations — Magasins physiques."""
from sqlalchemy import func

from competitive_mcp.db import (
    get_session, find_competitor, get_all_competitors,
    Competitor, StoreLocation,
)
from competitive_mcp.formatting import format_number, format_rating


def get_store_locations(
    competitor_name: str | None = None,
    department: str | None = None,
) -> str:
    """Magasins physiques avec notes Google."""
    db = get_session()
    try:
        query = db.query(StoreLocation)

        if competitor_name:
            comp = find_competitor(db, competitor_name)
            if comp:
                query = query.filter(StoreLocation.competitor_id == comp.id)
            else:
                # Fallback: search by brand_name
                query = query.filter(StoreLocation.brand_name.ilike(f"%{competitor_name}%"))

        if department:
            query = query.filter(StoreLocation.department == department)

        # Get aggregate stats first
        total_count = query.count()

        if total_count == 0:
            return f"Aucun magasin trouvé" + (f" pour « {competitor_name} »" if competitor_name else "") + "."

        # Aggregates
        avg_rating = query.with_entities(
            func.avg(StoreLocation.google_rating)
        ).filter(StoreLocation.google_rating.isnot(None)).scalar()

        avg_reviews = query.with_entities(
            func.avg(StoreLocation.google_reviews_count)
        ).filter(StoreLocation.google_reviews_count.isnot(None)).scalar()

        # Department breakdown
        dept_stats = query.with_entities(
            StoreLocation.department,
            func.count(StoreLocation.id),
            func.avg(StoreLocation.google_rating),
        ).group_by(StoreLocation.department).order_by(
            func.count(StoreLocation.id).desc()
        ).limit(20).all()

        lines = [f"# Magasins Physiques ({total_count} magasins)", ""]

        if avg_rating:
            lines.append(f"**Note Google moyenne** : {format_rating(avg_rating)}")
        if avg_reviews:
            lines.append(f"**Avis Google moyens** : {format_number(avg_reviews)} par magasin")
        lines.append("")

        if dept_stats and not department:
            lines.append("## Par département")
            for dept, count, rating in dept_stats:
                rating_str = f" — Note {format_rating(rating)}" if rating else ""
                lines.append(f"- **{dept or 'N/A'}** : {count} magasins{rating_str}")
            lines.append("")

        # Show individual stores
        stores = query.order_by(
            StoreLocation.google_rating.desc().nullslast()
        ).all()

        # GMB score stats
        avg_score = query.with_entities(
            func.avg(StoreLocation.gmb_score)
        ).filter(StoreLocation.gmb_score.isnot(None)).scalar()
        if avg_score:
            lines.append(f"**Score GMB moyen** : {avg_score:.0f}/100")
            lines.append("")

        if stores:
            lines.append(f"## Détail ({len(stores)} magasins)")
            for s in stores:
                rating_str = f" — {format_rating(s.google_rating)}" if s.google_rating else ""
                reviews_str = f" ({s.google_reviews_count} avis)" if s.google_reviews_count else ""
                score_str = f" [Score GMB: {s.gmb_score}/100]" if s.gmb_score else ""
                lines.append(f"- **{s.name}** — {s.city or 'N/A'} ({s.department or 'N/A'}){rating_str}{reviews_str}{score_str}")

        return "\n".join(lines)
    finally:
        db.close()
