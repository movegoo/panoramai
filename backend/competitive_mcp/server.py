"""Entry point MCP — Registration des 12 tools."""
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "Veille Concurrentielle",
    instructions=(
        "Serveur MCP de veille concurrentielle pour la grande distribution. "
        "Interroge les données concurrentielles : réseaux sociaux, publicités, apps, SEO, magasins. "
        "Les résultats sont en français."
    ),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "localhost:*",
            "127.0.0.1:*",
            "panoramai-api.onrender.com:*",
            "panoramai-api.onrender.com",
        ],
    ),
)


# ─── 1. Dashboard ────────────────────────────────────────────────
@mcp.tool()
def get_dashboard_overview(days: int = 7) -> str:
    """Vue d'ensemble de la veille : classement, scores, KPIs vs concurrents.

    Args:
        days: Nombre de jours pour le calcul de tendances (défaut: 7)
    """
    from competitive_mcp.tools.dashboard import get_dashboard_overview as _impl
    return _impl(days=days)


# ─── 2. List Competitors ─────────────────────────────────────────
@mcp.tool()
def list_competitors(include_brand: bool = True) -> str:
    """Liste tous les concurrents suivis avec leurs métriques clés.

    Args:
        include_brand: Inclure votre propre marque dans la liste (défaut: True)
    """
    from competitive_mcp.tools.competitors import list_competitors as _impl
    return _impl(include_brand=include_brand)


# ─── 3. Competitor Detail ────────────────────────────────────────
@mcp.tool()
def get_competitor_detail(competitor_name: str) -> str:
    """Profil détaillé d'un concurrent : tous les canaux (Instagram, TikTok, YouTube, apps, pubs).

    Args:
        competitor_name: Nom du concurrent (ex: "Carrefour", "Lidl")
    """
    from competitive_mcp.tools.competitors import get_competitor_detail as _impl
    return _impl(competitor_name=competitor_name)


# ─── 4. Compare Competitors ──────────────────────────────────────
@mcp.tool()
def compare_competitors(names: list[str], channel: str | None = None) -> str:
    """Compare 2 à 5 concurrents côte à côte sur tous les canaux.

    Args:
        names: Liste de noms de concurrents à comparer (2 à 5)
        channel: Filtrer par canal : "instagram", "tiktok", "youtube", "apps", "ads" (optionnel)
    """
    from competitive_mcp.tools.competitors import compare_competitors as _impl
    return _impl(names=names, channel=channel)


# ─── 5. Search Ads ───────────────────────────────────────────────
@mcp.tool()
def search_ads(
    competitor_name: str | None = None,
    platform: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> str:
    """Recherche et filtre les publicités des concurrents.

    Args:
        competitor_name: Filtrer par concurrent (optionnel)
        platform: Filtrer par plateforme : "facebook", "instagram", "google", "snapchat" (optionnel)
        category: Filtrer par catégorie produit (optionnel)
        limit: Nombre max de résultats (défaut: 50, max: 100)
    """
    from competitive_mcp.tools.ads import search_ads as _impl
    return _impl(competitor_name=competitor_name, platform=platform, category=category, limit=limit)


# ─── 6. Ad Intelligence ──────────────────────────────────────────
@mcp.tool()
def get_ad_intelligence(days: int = 30) -> str:
    """Analyse macro des publicités : formats, plateformes, dépenses estimées par concurrent.

    Args:
        days: Période d'analyse en jours (défaut: 30)
    """
    from competitive_mcp.tools.ads import get_ad_intelligence as _impl
    return _impl(days=days)


# ─── 7. Creative Insights ────────────────────────────────────────
@mcp.tool()
def get_creative_insights(
    competitor_name: str | None = None,
    min_score: int | None = None,
    concept: str | None = None,
) -> str:
    """Insights créatifs IA : concepts visuels, tons, hooks, top performers.

    Args:
        competitor_name: Filtrer par concurrent (optionnel)
        min_score: Score minimum des créatifs 0-100 (optionnel)
        concept: Filtrer par concept créatif : "product-shot", "lifestyle", "promo" (optionnel)
    """
    from competitive_mcp.tools.creative import get_creative_insights as _impl
    return _impl(competitor_name=competitor_name, min_score=min_score, concept=concept)


# ─── 8. Social Metrics ───────────────────────────────────────────
@mcp.tool()
def get_social_metrics(
    competitor_name: str | None = None,
    platform: str | None = None,
    days: int = 7,
) -> str:
    """Métriques réseaux sociaux (followers, engagement, croissance) par concurrent.

    Args:
        competitor_name: Filtrer par concurrent (optionnel)
        platform: Filtrer par plateforme : "instagram", "tiktok", "youtube", "snapchat" (optionnel)
        days: Période pour le calcul de croissance (défaut: 7)
    """
    from competitive_mcp.tools.social import get_social_metrics as _impl
    return _impl(competitor_name=competitor_name, platform=platform, days=days)


# ─── 9. Top Social Posts ─────────────────────────────────────────
@mcp.tool()
def get_top_social_posts(
    competitor_name: str | None = None,
    platform: str | None = None,
    sort_by: str = "views",
) -> str:
    """Posts sociaux les plus performants (TikTok, YouTube, Instagram).

    Args:
        competitor_name: Filtrer par concurrent (optionnel)
        platform: Filtrer par plateforme : "tiktok", "youtube", "instagram" (optionnel)
        sort_by: Trier par : "views", "likes", "comments", "engagement" (défaut: "views")
    """
    from competitive_mcp.tools.social import get_top_social_posts as _impl
    return _impl(competitor_name=competitor_name, platform=platform, sort_by=sort_by)


# ─── 10. SEO Rankings ────────────────────────────────────────────
@mcp.tool()
def get_seo_rankings(
    keyword: str | None = None,
    competitor_name: str | None = None,
    include_geo: bool = False,
) -> str:
    """Positions Google SERP et visibilité IA (GEO) des concurrents.

    Args:
        keyword: Filtrer par mot-clé (optionnel)
        competitor_name: Filtrer par concurrent (optionnel)
        include_geo: Inclure les données de visibilité IA / GEO (défaut: False)
    """
    from competitive_mcp.tools.seo_geo import get_seo_rankings as _impl
    return _impl(keyword=keyword, competitor_name=competitor_name, include_geo=include_geo)


# ─── 11. Signals ─────────────────────────────────────────────────
@mcp.tool()
def get_signals(
    severity: str | None = None,
    platform: str | None = None,
    limit: int = 20,
) -> str:
    """Alertes et anomalies détectées : pics de followers, baisses de notes, nouvelles campagnes.

    Args:
        severity: Filtrer par sévérité : "critical", "warning", "info" (optionnel)
        platform: Filtrer par plateforme (optionnel)
        limit: Nombre max de signaux (défaut: 20, max: 100)
    """
    from competitive_mcp.tools.signals import get_signals as _impl
    return _impl(severity=severity, platform=platform, limit=limit)


# ─── 12. Store Locations ─────────────────────────────────────────
@mcp.tool()
def get_store_locations(
    competitor_name: str | None = None,
    department: str | None = None,
) -> str:
    """Magasins physiques des concurrents avec notes Google.

    Args:
        competitor_name: Filtrer par concurrent (optionnel)
        department: Filtrer par département (ex: "75", "59", "13") (optionnel)
    """
    from competitive_mcp.tools.stores import get_store_locations as _impl
    return _impl(competitor_name=competitor_name, department=department)


def main():
    """Point d'entrée CLI."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
