"""
Smart Filter Service.
Translates natural language queries into structured JSON filters
for client-side filtering, using Gemini Flash.
Supports multiple page contexts with different filter schemas.
"""
import json
import logging
import os
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# ---------------------------------------------------------------------------
# Per-page system prompts
# ---------------------------------------------------------------------------

_COMMON_RULES = """
RÈGLES :
1. Retourne UNIQUEMENT un JSON valide : {"filters": {...}, "interpretation": "..."}
2. "interpretation" = résumé en français de ce que tu as compris (1 phrase courte)
3. N'inclus QUE les champs pertinents (pas de champs vides ou null)
4. Pour les champs textuels, utilise des mots-clés en minuscules
5. Sois flexible avec les synonymes et variations linguistiques
6. Si la requête mentionne un concurrent, ajoute competitor_name
7. Si tu ne comprends pas la requête, retourne : {"filters": {"text_search": "<la requête>"}, "interpretation": "Recherche textuelle"}"""

PAGE_PROMPTS: dict[str, str] = {
    "ads": """Tu es un assistant qui traduit des requêtes en langage naturel en filtres JSON structurés pour filtrer des publicités.

CHAMPS FILTRABLES (retourne UNIQUEMENT ceux qui sont pertinents) :

- "products_contain": [str] — mots-clés dans products_detected (ex: ["fruit", "yaourt"])
- "tags_contain": [str] — mots-clés dans creative_tags (ex: ["promo", "famille"])
- "product_category": [str] — catégories exactes (ex: ["Fruits & Légumes", "Boissons", "Hygiène & Beauté", "Surgelés", "Épicerie", "Boulangerie", "Viandes & Poissons", "Produits laitiers", "Snacking", "Bio & Santé", "Bébé & Enfants", "Animalerie", "Électroménager", "Textile", "Maison & Déco"])
- "creative_concept": [str] — concepts créatifs (ex: ["promo-prix", "lifestyle", "produit-hero", "témoignage", "comparaison", "humour", "recette", "tutoriel", "UGC", "brand-story"])
- "creative_tone": [str] — tons créatifs (ex: ["promotionnel", "informatif", "humoristique", "inspirant", "urgence", "communautaire", "premium", "familial", "écologique"])
- "ad_objective": [str] — objectifs pub (ex: ["awareness", "consideration", "conversion", "traffic", "engagement", "app_install"])
- "display_format": [str] — formats d'affichage, EN MAJUSCULES (ex: ["VIDEO", "IMAGE", "CAROUSEL", "DPA", "DCO"])
- "platform": [str] — plateformes sources (ex: ["meta", "tiktok", "google"])
- "seasonal_event": [str] — événements saisonniers (ex: ["noel", "soldes_hiver", "soldes_ete", "saint_valentin", "paques", "rentree", "black_friday", "halloween", "fete_des_meres", "fete_des_peres"])
- "promo_type": [str] — types de promo (ex: ["pourcentage", "prix_barre", "lot", "carte_fidelite", "code_promo", "livraison_gratuite", "aucune"])
- "creative_has_face": bool — présence d'un visage humain
- "creative_has_product": bool — présence d'un produit visible
- "price_visible": bool — prix affiché dans le visuel
- "creative_score_min": int — score créatif minimum (0-100)
- "competitor_name": [str] — noms de concurrents (ex: ["Leclerc", "Carrefour", "Auchan", "Lidl", "Intermarché"])
- "text_search": str — recherche texte libre dans le titre/texte de la pub
- "target_audience_contains": [str] — mots-clés dans target_audience (ex: ["jeunes", "familles", "seniors"])
- "is_active": bool — pub encore active

RÈGLES SPÉCIFIQUES :
- Pour display_format, utilise TOUJOURS les majuscules
- "vidéos" → display_format: ["VIDEO"], "drôle" → creative_tone: ["humoristique"]
""" + _COMMON_RULES,

    "social": """Tu es un assistant qui traduit des requêtes en langage naturel en filtres JSON structurés pour filtrer des données de réseaux sociaux.

CHAMPS FILTRABLES (retourne UNIQUEMENT ceux qui sont pertinents) :

- "platform": [str] — plateformes (ex: ["instagram", "tiktok", "youtube", "snapchat"])
- "metric": str — métrique principale à mettre en avant (ex: "followers", "engagement", "growth")
- "competitor_name": [str] — noms de concurrents
- "growth_direction": str — direction de croissance ("up" ou "down")
- "text_search": str — recherche textuelle libre
""" + _COMMON_RULES,

    "apps": """Tu es un assistant qui traduit des requêtes en langage naturel en filtres JSON structurés pour filtrer des données d'applications mobiles.

CHAMPS FILTRABLES (retourne UNIQUEMENT ceux qui sont pertinents) :

- "store": str — magasin d'applications ("playstore" ou "appstore")
- "metric": str — métrique principale (ex: "rating", "reviews", "downloads")
- "competitor_name": [str] — noms de concurrents
- "rating_min": float — note minimale (ex: 4.0)
- "rating_max": float — note maximale
- "text_search": str — recherche textuelle libre
""" + _COMMON_RULES,

    "geo": """Tu es un assistant qui traduit des requêtes en langage naturel en filtres JSON structurés pour filtrer des données géographiques (magasins, scores GMB).

CHAMPS FILTRABLES (retourne UNIQUEMENT ceux qui sont pertinents) :

- "competitor_name": [str] — noms de concurrents
- "score_min": float — score GMB minimum
- "rating_min": float — note Google minimum
- "department": [str] — départements (ex: ["75", "92", "69"])
- "region": [str] — régions (ex: ["Île-de-France", "Auvergne-Rhône-Alpes"])
- "text_search": str — recherche textuelle libre
""" + _COMMON_RULES,

    "seo": """Tu es un assistant qui traduit des requêtes en langage naturel en filtres JSON structurés pour filtrer des données SEO (positionnement SERP).

CHAMPS FILTRABLES (retourne UNIQUEMENT ceux qui sont pertinents) :

- "keyword": [str] — mots-clés SEO spécifiques
- "competitor_name": [str] — noms de concurrents
- "position_max": int — position maximale dans les résultats (ex: 3, 10)
- "text_search": str — recherche textuelle libre
""" + _COMMON_RULES,

    "signals": """Tu es un assistant qui traduit des requêtes en langage naturel en filtres JSON structurés pour filtrer des signaux et alertes concurrentiels.

CHAMPS FILTRABLES (retourne UNIQUEMENT ceux qui sont pertinents) :

- "severity": [str] — niveaux de sévérité (ex: ["critical", "warning", "info"])
- "platform": [str] — plateformes (ex: ["instagram", "tiktok", "youtube", "playstore", "appstore", "meta", "google"])
- "competitor_name": [str] — noms de concurrents
- "text_search": str — recherche textuelle libre
""" + _COMMON_RULES,

    "tendances": """Tu es un assistant qui traduit des requêtes en langage naturel en filtres JSON structurés pour filtrer des tendances et évolutions.

CHAMPS FILTRABLES (retourne UNIQUEMENT ceux qui sont pertinents) :

- "platform": [str] — plateformes (ex: ["instagram", "tiktok", "youtube", "meta", "google"])
- "metric_category": str — catégorie de métrique ("social", "apps", "ads", "google_trends", "presse")
- "competitor_name": [str] — noms de concurrents
- "growth_direction": str — direction de tendance ("up" ou "down")
- "text_search": str — recherche textuelle libre
""" + _COMMON_RULES,

    "overview": """Tu es un assistant qui traduit des requêtes en langage naturel en filtres JSON structurés pour filtrer le tableau de bord global.

CHAMPS FILTRABLES (retourne UNIQUEMENT ceux qui sont pertinents) :

- "competitor_name": [str] — noms de concurrents
- "platform": [str] — plateformes (ex: ["instagram", "tiktok", "youtube", "meta", "google", "playstore", "appstore"])
- "text_search": str — recherche textuelle libre
""" + _COMMON_RULES,

    "geo-tracking": """Tu es un assistant qui traduit des requêtes en langage naturel en filtres JSON structurés pour filtrer des données de visibilité IA (GEO tracking).

CHAMPS FILTRABLES (retourne UNIQUEMENT ceux qui sont pertinents) :

- "platform": [str] — moteurs IA (ex: ["claude", "gemini", "chatgpt", "mistral"])
- "competitor_name": [str] — noms de concurrents
- "keyword": [str] — mots-clés / requêtes trackées
- "sentiment": [str] — sentiments (ex: ["positif", "neutre", "négatif"])
- "recommended": bool — uniquement les marques recommandées
- "text_search": str — recherche textuelle libre
""" + _COMMON_RULES,

    "vgeo": """Tu es un assistant qui traduit des requetes en langage naturel en filtres JSON structures pour filtrer des donnees VGEO (Video GEO — strategie YouTube pour visibilite IA).

CHAMPS FILTRABLES (retourne UNIQUEMENT ceux qui sont pertinents) :

- "classification": [str] — classification video HELP/HUB/HERO (ex: ["HELP", "HUB", "HERO"])
- "competitor_name": [str] — noms de concurrents
- "platform": [str] — moteurs IA (ex: ["claude", "gemini", "chatgpt", "mistral"])
- "keyword": [str] — mots-cles dans les titres ou requetes
- "text_search": str — recherche textuelle libre
""" + _COMMON_RULES,
}

# Legacy constant for backwards compatibility
FILTER_SYSTEM_PROMPT = PAGE_PROMPTS["ads"]


class SmartFilterService:
    """Translates natural language queries to structured filters via Gemini."""

    @property
    def gemini_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "") or settings.GEMINI_API_KEY

    async def parse_query(self, query: str, page: str = "ads") -> dict[str, Any]:
        """Parse a natural language query into structured filters for the given page context."""
        if not self.gemini_key:
            logger.warning("No Gemini API key configured, falling back to text_search")
            return {
                "filters": {"text_search": query},
                "interpretation": "Recherche textuelle (clé API Gemini manquante)",
            }

        system_prompt = PAGE_PROMPTS.get(page, PAGE_PROMPTS["ads"])

        try:
            result = await self._call_gemini(query, system_prompt)
            if result:
                parsed = self._parse_json(result)
                if parsed:
                    return parsed
        except Exception as e:
            logger.error(f"Smart filter error (page={page}): {e}")

        # Fallback
        return {
            "filters": {"text_search": query},
            "interpretation": f"Recherche textuelle : {query}",
        }

    async def _call_gemini(self, query: str, system_prompt: str) -> str:
        """Call Gemini Flash for fast structured output."""
        url = GEMINI_API_URL.format(model="gemini-3-flash-preview") + f"?key={self.gemini_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"[Instructions système]\n{system_prompt}"},
                        {"text": f"[Utilisateur]\n{query}"},
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 512,
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
            candidates = body.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            return parts[0].get("text", "") if parts else ""

    def _parse_json(self, raw: str) -> dict[str, Any] | None:
        """Parse and validate the JSON response from Gemini."""
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"Smart filter: failed to parse JSON: {text[:200]}")
            return None

        # Validate structure
        if not isinstance(data, dict):
            return None

        filters = data.get("filters", data)
        interpretation = data.get("interpretation", "")

        # If the parsed data doesn't have a "filters" key, treat the whole thing as filters
        if "filters" not in data and not interpretation:
            filters = data
            interpretation = "Filtres appliqués"

        # Clean empty values
        cleaned = {}
        for key, value in filters.items():
            if value is None:
                continue
            if isinstance(value, list) and len(value) == 0:
                continue
            if isinstance(value, str) and value == "":
                continue
            cleaned[key] = value

        if not cleaned:
            return None

        return {"filters": cleaned, "interpretation": interpretation}


smart_filter_service = SmartFilterService()
