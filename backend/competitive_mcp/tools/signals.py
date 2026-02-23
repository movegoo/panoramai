"""Tool: get_signals — Alertes et anomalies détectées."""
from sqlalchemy import desc

from competitive_mcp.db import (
    get_session, get_all_competitors,
    Competitor, Signal,
)
from competitive_mcp.formatting import format_number, format_percent, format_date


def get_signals(
    severity: str | None = None,
    platform: str | None = None,
    days: int | None = None,
) -> str:
    """Alertes et anomalies détectées (signaux de veille)."""
    from datetime import datetime, timedelta
    db = get_session()
    try:
        competitors = get_all_competitors(db)
        comp_ids = [c.id for c in competitors]
        comp_names = {c.id: c.name for c in competitors}

        if not comp_ids:
            return "Aucun concurrent configuré."

        query = db.query(Signal).filter(Signal.competitor_id.in_(comp_ids))

        if severity:
            query = query.filter(Signal.severity.ilike(severity))

        if platform:
            query = query.filter(Signal.platform.ilike(f"%{platform}%"))

        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(Signal.detected_at >= cutoff)

        signals = query.order_by(desc(Signal.detected_at)).all()

        if not signals:
            return "Aucun signal détecté." + (" Filtres appliqués : " + ", ".join(
                f for f in [severity, platform] if f
            ) if (severity or platform) else "")

        severity_icons = {"critical": "🔴", "warning": "🟠", "info": "🔵"}

        lines = [f"# {len(signals)} Signaux de Veille", ""]

        for s in signals:
            icon = severity_icons.get(s.severity, "⚪")
            name = comp_names.get(s.competitor_id, "?")
            brand_tag = " (marque)" if s.is_brand else ""

            lines.append(f"### {icon} {s.title}")
            lines.append(f"**{name}**{brand_tag} — {s.platform or 'N/A'} — {format_date(s.detected_at)}")

            if s.description:
                lines.append(s.description)

            if s.metric_name and s.current_value is not None:
                parts = [f"{s.metric_name} : {format_number(s.current_value)}"]
                if s.previous_value is not None:
                    parts.append(f"avant : {format_number(s.previous_value)}")
                if s.change_percent is not None:
                    sign = "+" if s.change_percent >= 0 else ""
                    parts.append(f"variation : {sign}{s.change_percent:.1f}%")
                lines.append(" | ".join(parts))

            lines.append("")

        return "\n".join(lines)
    finally:
        db.close()
