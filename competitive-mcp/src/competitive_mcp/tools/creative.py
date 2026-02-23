"""Tool: get_creative_insights — Insights créatifs IA."""
import json
from collections import Counter
from sqlalchemy import func

from competitive_mcp.db import (
    get_session, find_competitor, get_all_competitors,
    Competitor, Ad,
)
from competitive_mcp.formatting import truncate


def get_creative_insights(
    competitor_name: str | None = None,
    min_score: int | None = None,
    concept: str | None = None,
) -> str:
    """Insights créatifs IA : concepts, tons, hooks, top performers."""
    db = get_session()
    try:
        query = db.query(Ad, Competitor.name).join(
            Competitor, Ad.competitor_id == Competitor.id
        ).filter(
            Competitor.is_active == True,
            Ad.creative_analyzed_at.isnot(None),
            Ad.creative_score > 0,
        )

        if competitor_name:
            comp = find_competitor(db, competitor_name)
            if not comp:
                return f"Concurrent « {competitor_name} » non trouvé."
            query = query.filter(Ad.competitor_id == comp.id)

        if min_score:
            query = query.filter(Ad.creative_score >= min_score)

        if concept:
            query = query.filter(Ad.creative_concept.ilike(f"%{concept}%"))

        rows = query.all()

        if not rows:
            return "Aucune publicité analysée trouvée avec ces critères."

        # Aggregate
        scores = []
        concept_counter = Counter()
        tone_counter = Counter()
        category_counter = Counter()
        hooks = []
        by_competitor = {}

        for ad, comp_name in rows:
            score = ad.creative_score or 0
            scores.append(score)
            if ad.creative_concept:
                concept_counter[ad.creative_concept] += 1
            if ad.creative_tone:
                tone_counter[ad.creative_tone] += 1
            if ad.product_category:
                category_counter[ad.product_category] += 1
            if ad.creative_hook and score > 0:
                hooks.append({"hook": ad.creative_hook, "score": score, "comp": comp_name})

            if comp_name not in by_competitor:
                by_competitor[comp_name] = []
            by_competitor[comp_name].append(score)

        total = len(scores)
        avg_score = round(sum(scores) / total, 1)

        lines = [f"# Insights Créatifs ({total} pubs analysées)", ""]
        lines.append(f"**Score moyen** : {avg_score}/100")
        lines.append("")

        # Top concepts
        if concept_counter:
            lines.append("## Top Concepts")
            for c, n in concept_counter.most_common(8):
                pct = round(n / total * 100, 1)
                lines.append(f"- {c} : {n} pubs ({pct}%)")
            lines.append("")

        # Top tones
        if tone_counter:
            lines.append("## Top Tons")
            for t, n in tone_counter.most_common(8):
                pct = round(n / total * 100, 1)
                lines.append(f"- {t} : {n} pubs ({pct}%)")
            lines.append("")

        # Top hooks
        top_hooks = sorted(hooks, key=lambda h: h["score"], reverse=True)[:5]
        if top_hooks:
            lines.append("## Meilleurs Hooks")
            for h in top_hooks:
                lines.append(f"- **{h['comp']}** (score {h['score']}/100) : « {truncate(h['hook'], 120)} »")
            lines.append("")

        # By competitor
        if by_competitor:
            lines.append("## Par concurrent")
            comp_stats = []
            for comp, comp_scores in by_competitor.items():
                avg = round(sum(comp_scores) / len(comp_scores), 1)
                comp_stats.append((comp, len(comp_scores), avg))
            comp_stats.sort(key=lambda x: -x[2])
            for comp, count, avg in comp_stats:
                lines.append(f"- **{comp}** : {count} pubs, score moyen {avg}/100")

        # Categories
        if category_counter:
            lines.append("")
            lines.append("## Catégories produit")
            for c, n in category_counter.most_common(8):
                lines.append(f"- {c} : {n} pubs")

        return "\n".join(lines)
    finally:
        db.close()
