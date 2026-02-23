"""Tool: get_seo_rankings — Positions Google SERP + visibilité IA."""
from sqlalchemy import func, desc

from competitive_mcp.db import (
    get_session, find_competitor, get_all_competitors,
    Competitor, SerpResult, GeoResult,
)
from competitive_mcp.formatting import truncate


def get_seo_rankings(
    keyword: str | None = None,
    competitor_name: str | None = None,
    include_geo: bool = False,
) -> str:
    """Positions Google SERP et visibilité IA (GEO)."""
    db = get_session()
    try:
        competitors = get_all_competitors(db)
        comp_ids = [c.id for c in competitors]
        comp_names = {c.id: c.name for c in competitors}

        if not comp_ids:
            return "Aucun concurrent configuré."

        # SERP Results
        serp_query = db.query(SerpResult).filter(
            SerpResult.competitor_id.in_(comp_ids)
        )
        if keyword:
            serp_query = serp_query.filter(SerpResult.keyword.ilike(f"%{keyword}%"))
        if competitor_name:
            comp = find_competitor(db, competitor_name)
            if comp:
                serp_query = serp_query.filter(SerpResult.competitor_id == comp.id)

        serp_results = serp_query.order_by(SerpResult.keyword, SerpResult.position).limit(100).all()

        lines = ["# SEO & Visibilité IA", ""]

        if serp_results:
            lines.append("## Positions Google SERP")
            # Group by keyword
            by_keyword = {}
            for r in serp_results:
                if r.keyword not in by_keyword:
                    by_keyword[r.keyword] = []
                by_keyword[r.keyword].append(r)

            for kw, results in list(by_keyword.items())[:15]:
                lines.append(f"### « {kw} »")
                for r in results[:10]:
                    name = comp_names.get(r.competitor_id, r.domain or "?")
                    lines.append(f"  {r.position}. **{name}** — {r.domain or 'N/A'}")
                    if r.title:
                        lines.append(f"     {truncate(r.title, 80)}")
                lines.append("")
        else:
            lines.append("Aucun résultat SERP trouvé.")
            lines.append("")

        # GEO Results
        if include_geo:
            geo_query = db.query(GeoResult).filter(
                GeoResult.competitor_id.in_(comp_ids)
            )
            if keyword:
                geo_query = geo_query.filter(GeoResult.keyword.ilike(f"%{keyword}%"))
            if competitor_name:
                comp = find_competitor(db, competitor_name)
                if comp:
                    geo_query = geo_query.filter(GeoResult.competitor_id == comp.id)

            geo_results = geo_query.order_by(desc(GeoResult.recorded_at)).limit(50).all()

            if geo_results:
                lines.append("## Visibilité IA (GEO)")
                for r in geo_results[:15]:
                    name = comp_names.get(r.competitor_id, "?")
                    mentioned = "✅ Mentionné" if r.mentioned else "❌ Absent"
                    rec = f" | Recommandé" if r.recommended else ""
                    sentiment = f" | Sentiment : {r.sentiment}" if r.sentiment else ""
                    lines.append(f"- **{name}** sur « {r.keyword} » ({r.platform or 'IA'}) : {mentioned}{rec}{sentiment}")
                    if r.context_snippet:
                        lines.append(f"  > {truncate(r.context_snippet, 120)}")
                lines.append("")

        return "\n".join(lines)
    finally:
        db.close()
