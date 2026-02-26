"""
Smart Filter Service.
Translates natural language queries into structured JSON filters
for client-side ad filtering, using Gemini Flash.
"""
import json
import logging
import os
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

FILTER_SYSTEM_PROMPT = """Tu es un assistant qui traduit des requêtes en langage naturel en filtres JSON structurés pour filtrer des publicités.

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

RÈGLES :
1. Retourne UNIQUEMENT un JSON valide : {"filters": {...}, "interpretation": "..."}
2. "interpretation" = résumé en français de ce que tu as compris (1 phrase courte)
3. N'inclus QUE les champs pertinents (pas de champs vides ou null)
4. Pour les champs textuels, utilise des mots-clés en minuscules
5. Pour display_format, utilise TOUJOURS les majuscules
6. Sois flexible : "vidéos" → display_format: ["VIDEO"], "drôle" → creative_tone: ["humoristique"]
7. Si la requête mentionne un concurrent, ajoute competitor_name
8. Si tu ne comprends pas la requête, retourne : {"filters": {"text_search": "<la requête>"}, "interpretation": "Recherche textuelle"}"""


class SmartFilterService:
    """Translates natural language queries to structured ad filters via Gemini."""

    @property
    def gemini_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "") or settings.GEMINI_API_KEY

    async def parse_query(self, query: str) -> dict[str, Any]:
        """Parse a natural language query into structured filters."""
        if not self.gemini_key:
            logger.warning("No Gemini API key configured, falling back to text_search")
            return {
                "filters": {"text_search": query},
                "interpretation": "Recherche textuelle (clé API Gemini manquante)",
            }

        try:
            result = await self._call_gemini(query)
            if result:
                parsed = self._parse_json(result)
                if parsed:
                    return parsed
        except Exception as e:
            logger.error(f"Smart filter error: {e}")

        # Fallback
        return {
            "filters": {"text_search": query},
            "interpretation": f"Recherche textuelle : {query}",
        }

    async def _call_gemini(self, query: str) -> str:
        """Call Gemini Flash for fast structured output."""
        url = GEMINI_API_URL.format(model="gemini-2.0-flash") + f"?key={self.gemini_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"[Instructions système]\n{FILTER_SYSTEM_PROMPT}"},
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
