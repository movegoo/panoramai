"""
Feature access control registry and helpers.
Manages per-advertiser feature toggles (pages & blocks).
"""

# Registry: feature_key -> French label
FEATURE_REGISTRY: dict[str, str] = {
    # Overview
    "overview": "Vue d'ensemble",
    "overview.hero": "Hero metrics",
    "overview.recommendations": "Recommandations",
    "overview.rankings": "Classements",
    "overview.ad_intelligence": "Intelligence publicitaire",
    # Competitors
    "competitors": "Concurrents",
    "competitors.list": "Liste concurrents",
    "competitors.add": "Ajout concurrent",
    "competitors.edit": "Edition concurrent",
    # Ads
    "ads": "Publicites",
    "ads.gallery": "Galerie creatives",
    "ads.creative_intelligence": "Intelligence creative",
    "ads.filters": "Filtres avances",
    # Ads Overview
    "ads_overview": "Part de Voix",
    "ads_overview.sov_chart": "Graphique PdV",
    "ads_overview.budget_breakdown": "Repartition budgets",
    "ads_overview.timeline": "Timeline",
    # Social
    "social": "Reseaux sociaux",
    "social.platform_metrics": "Metriques plateformes",
    "social.content_feed": "Feed contenu",
    # Apps
    "apps": "Applications",
    "apps.store_metrics": "Metriques stores",
    "apps.ranking_table": "Tableau classement",
    # Geo
    "geo": "Carte & Zones",
    "geo.france_map": "Carte France",
    "geo.gmb_scoring": "Scoring GMB",
    "geo.store_distribution": "Distribution magasins",
    "geo.catchment": "Zone de chalandise",
    # SEO
    "seo": "SEO",
    "seo.serp_rankings": "Classements SERP",
    "seo.sov_chart": "Graphique PdV SEO",
    "seo.missing_keywords": "Mots-cles manquants",
    # GEO Tracking
    "geo_tracking": "GEO",
    "geo_tracking.tracking_table": "Tableau suivi",
    "geo_tracking.sov_chart": "Graphique PdV GEO",
    "geo_tracking.insights": "Insights GEO",
    # VGEO
    "vgeo": "VGEO",
    "vgeo.score_gauge": "Jauge score",
    "vgeo.classification": "Classification",
    "vgeo.citations": "Citations",
    "vgeo.comparison": "Comparaison",
    "vgeo.diagnostic": "Diagnostic",
    "vgeo.actions": "Actions",
    # Tendances
    "tendances": "Tendances",
    "tendances.timeseries": "Series temporelles",
    "tendances.news_feed": "Fil actualites",
    "tendances.summary_cards": "Cartes resume",
    # Signals
    "signals": "Signaux",
    "signals.signal_list": "Liste signaux",
    "signals.severity_summary": "Resume severite",
}

# Page-level keys (no dot)
PAGES = [k for k in FEATURE_REGISTRY if "." not in k]

# Map page -> its block keys
_PAGE_BLOCKS: dict[str, list[str]] = {}
for _key in FEATURE_REGISTRY:
    if "." in _key:
        _page = _key.split(".")[0]
        _PAGE_BLOCKS.setdefault(_page, []).append(_key)


def resolve_features(features_json: dict | None) -> dict[str, bool]:
    """Resolve features JSON to a full dict of booleans.

    NULL or empty → all True (full access).
    Explicit False on a page cascades to all its blocks.
    """
    result: dict[str, bool] = {k: True for k in FEATURE_REGISTRY}
    if not features_json:
        return result

    for key, value in features_json.items():
        if key not in FEATURE_REGISTRY:
            continue
        result[key] = bool(value)

    # Cascade: if page is False, all its blocks are False
    for page in PAGES:
        if not result.get(page, True):
            for block_key in _PAGE_BLOCKS.get(page, []):
                result[block_key] = False

    return result


def has_feature(features_json: dict | None, key: str) -> bool:
    """Quick check: is a single feature enabled?"""
    if not features_json:
        return True
    # Check page-level cascade
    page = key.split(".")[0]
    if page != key and features_json.get(page) is False:
        return False
    return features_json.get(key) is not False


def get_registry_grouped() -> dict[str, dict]:
    """Return the registry grouped by page for the admin UI."""
    grouped: dict[str, dict] = {}
    for page in PAGES:
        blocks = {}
        for block_key in _PAGE_BLOCKS.get(page, []):
            block_name = block_key.split(".", 1)[1]
            blocks[block_key] = FEATURE_REGISTRY[block_key]
        grouped[page] = {
            "label": FEATURE_REGISTRY[page],
            "blocks": blocks,
        }
    return grouped
