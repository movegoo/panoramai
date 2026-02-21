"""
Creative Analyzer Service.
Uses Anthropic Claude Vision API to analyze ad creative images.
Extracts: concept, hook, tone, colors, text overlay, score, tags.
"""
import asyncio
import base64
import json
import logging
import os
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """Tu es un expert en analyse créative publicitaire et en grande distribution/retail en France.
Analyse ce visuel publicitaire et retourne UNIQUEMENT un JSON valide (pas de markdown, pas de commentaire, pas de ```).
TOUTES les valeurs doivent être en FRANÇAIS.

Contexte : plateforme={platform}, texte de la pub="{ad_text}"

JSON attendu :
{{
  "concept": "<UNE valeur parmi : photo-produit, mise-en-scène, ugc, promo, témoignage, avant-après, tutoriel, saisonnier, événement, comparatif, storytelling, influenceur, recette, catalogue, jeu-concours, engagement-RSE>",
  "hook": "<1 phrase en français : ce qui capte l'attention en premier>",
  "tone": "<UNE valeur parmi : urgence, aspiration, humour, confiance, fomo, communauté, premium, bon-plan, pédagogique, émotion, ludique, audacieux, minimaliste, festif, familial, écologique>",
  "text_overlay": "<tout le texte visible sur le visuel, verbatim, séparé par des |>",
  "dominant_colors": ["#HEX1", "#HEX2", "#HEX3"],
  "has_product": true ou false,
  "has_face": true ou false,
  "has_logo": true ou false,
  "has_price": true ou false,
  "layout": "<UNE valeur parmi : image-unique, split, collage, plein-écran, texte-dominant, minimaliste, avant-après, grille-produits, hero, carrousel, vidéo-cover>",
  "cta_style": "<UNE valeur parmi : bouton, texte, flèche, badge, aucun>",
  "score": <entier 0-100>,
  "tags": ["mot-clé1", "mot-clé2", "mot-clé3", "mot-clé4", "mot-clé5"],
  "summary": "<1-2 phrases en français décrivant l'approche créative et son efficacité probable>",
  "product_category": "<UNE valeur parmi : Épicerie, Boissons, Frais, Surgelés, Fruits & Légumes, Boucherie & Volaille, Poissonnerie, Boulangerie, DPH, Beauté & Parfumerie, Hygiène, Entretien, Textile & Mode, Électroménager, Multimédia & High-Tech, Jouets & Loisirs, Sport, Bricolage & Jardin, Ameublement & Déco, Auto & Mobilité, Animalerie, Bio & Écologie, Services, Fidélité & Programme, Marque Employeur, Corporate & RSE, Multi-rayons, Autre>",
  "product_subcategory": "<sous-catégorie plus précise, en français, ex: Yaourts, Café, Bières, Lessive, Smartphones, Literie, Drive, Carte fidélité...>",
  "ad_objective": "<UNE valeur parmi : notoriété, trafic, conversion, fidélisation, recrutement, RSE, lancement-produit, promotion, saisonnier, drive-to-store>"
}}

Critères de score :
- Impact visuel (30%) : contraste, composition, accroche
- Clarté du message (25%) : compréhension immédiate de l'offre
- Exécution professionnelle (25%) : qualité graphique, cohérence
- Persuasion (20%) : incitation à l'action, urgence, désirabilité

IMPORTANT : Si la pub concerne plusieurs rayons (ex: catalogue général), utilise "Multi-rayons" comme product_category."""

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


class CreativeAnalyzer:
    """Analyze ad creatives using Anthropic Claude Vision API."""

    @property
    def api_key(self) -> str:
        """Read API key from env vars or database (Railway env var workaround)."""
        key = (
            os.getenv("ANTHROPIC_API_KEY", "")
            or os.getenv("CLAUDE_KEY", "")
            or settings.ANTHROPIC_API_KEY
        )
        if key:
            return key
        # Fallback: read from database
        try:
            from database import SessionLocal, SystemSetting
            db = SessionLocal()
            row = db.query(SystemSetting).filter(SystemSetting.key == "ANTHROPIC_API_KEY").first()
            db.close()
            return row.value if row else ""
        except Exception:
            return ""

    async def analyze_creative(
        self,
        creative_url: str,
        ad_text: str = "",
        platform: str = "meta",
        ad_id: str = "",
    ) -> Optional[dict]:
        """Analyze a single ad creative image with Claude Vision.

        Returns parsed analysis dict or None on failure.
        """
        if not self.api_key:
            logger.error("Cannot analyze: ANTHROPIC_API_KEY not set")
            return None

        if not creative_url:
            logger.error("Cannot analyze: empty creative_url")
            return None

        image_data = None
        media_type = ""

        # For fbcdn URLs (which expire), always fetch fresh URL from ScrapeCreators first
        if ad_id and "fbcdn" in creative_url:
            image_data, media_type = await self._fetch_fresh_image(ad_id)

        # If ScrapeCreators didn't work or not fbcdn, try the stored URL
        if not image_data:
            image_data, media_type = await self._download_image(creative_url)

        # Last resort: try ScrapeCreators if we haven't already
        if not image_data and ad_id and "fbcdn" not in creative_url:
            image_data, media_type = await self._fetch_fresh_image(ad_id)

        if not image_data:
            logger.error(f"Image download failed for: {creative_url[:100]}")
            return None

        # Encode to base64
        b64_image = base64.standard_b64encode(image_data).decode("utf-8")

        # Load prompt from DB (fallback to hardcoded)
        db_prompt_text = ANALYSIS_PROMPT
        db_model_id = "claude-sonnet-4-5-20250929"
        db_max_tokens = 1024
        try:
            from database import SessionLocal, PromptTemplate
            _db = SessionLocal()
            row = _db.query(PromptTemplate).filter(PromptTemplate.key == "creative_analysis").first()
            if row:
                db_prompt_text = row.prompt_text
                db_model_id = row.model_id or db_model_id
                db_max_tokens = row.max_tokens or db_max_tokens
            _db.close()
        except Exception:
            pass

        # Build prompt
        prompt = db_prompt_text.format(
            platform=platform,
            ad_text=(ad_text or "")[:500],
        )

        # Call Claude API with retry for rate limits
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        CLAUDE_API_URL,
                        headers={
                            "x-api-key": self.api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": db_model_id,
                            "max_tokens": db_max_tokens,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": media_type,
                                                "data": b64_image,
                                            },
                                        },
                                        {
                                            "type": "text",
                                            "text": prompt,
                                        },
                                    ],
                                }
                            ],
                        },
                    )

                if response.status_code == 429:
                    wait = 10 * (attempt + 1)
                    logger.warning(f"Claude rate limit (429), waiting {wait}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait)
                    continue

                if response.status_code != 200:
                    logger.error(f"Claude API error {response.status_code}: {response.text[:300]}")
                    return None

                result = response.json()
                text_content = result.get("content", [{}])[0].get("text", "")

                from core.langfuse_client import trace_generation
                usage = result.get("usage", {})
                trace_generation(
                    name="creative_analyzer",
                    model=db_model_id,
                    input=prompt,
                    output=text_content,
                    usage={"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")},
                )

                return self._parse_analysis(text_content)

            except httpx.TimeoutException:
                logger.error(f"Claude API timeout for {creative_url[:80]}")
                return None
            except Exception as e:
                logger.error(f"Claude API error: {e}")
                return None

        logger.error(f"Claude: max retries reached for {creative_url[:80]}")
        return None

    async def _download_image(self, url: str) -> tuple[Optional[bytes], str]:
        """Download image from URL. Returns (bytes, media_type) or (None, '')."""
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url)

            if response.status_code != 200:
                logger.error(f"Image download HTTP {response.status_code}: {url[:100]}")
                return None, ""

            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                if ".png" in url.lower():
                    content_type = "image/png"
                elif ".webp" in url.lower():
                    content_type = "image/webp"
                elif ".gif" in url.lower():
                    content_type = "image/gif"
                else:
                    content_type = "image/jpeg"

            media_type = content_type.split(";")[0].strip()
            if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
                media_type = "image/jpeg"

            data = response.content
            if len(data) > MAX_IMAGE_SIZE:
                logger.error(f"Image too large ({len(data)} bytes): {url[:80]}")
                return None, ""

            if len(data) < 1000:
                logger.error(f"Image too small ({len(data)} bytes), likely broken: {url[:80]}")
                return None, ""

            logger.info(f"Image OK: {len(data)} bytes, {media_type}: {url[:80]}")
            return data, media_type

        except httpx.TimeoutException:
            logger.error(f"Image download TIMEOUT: {url[:100]}")
            return None, ""
        except Exception as e:
            logger.error(f"Image download exception ({type(e).__name__}): {e} - {url[:100]}")
            return None, ""

    async def _fetch_fresh_image(self, ad_id: str) -> tuple[Optional[bytes], str]:
        """Fetch a fresh image URL from ScrapeCreators or SearchAPI and download it."""
        # Try ScrapeCreators first
        try:
            from services.scrapecreators import scrapecreators
            logger.info(f"Fetching fresh image URL from ScrapeCreators for ad {ad_id}")
            detail = await scrapecreators.get_facebook_ad_detail_raw(ad_id)
            snapshot = detail.get("snapshot", {})
            cards = snapshot.get("cards", [])
            images = snapshot.get("images", [])
            fresh_url = ""
            if cards:
                fresh_url = cards[0].get("original_image_url") or cards[0].get("resized_image_url", "")
            if not fresh_url and images:
                fresh_url = images[0].get("original_image_url") or images[0].get("resized_image_url", "")
            if not fresh_url:
                fresh_url = detail.get("original_image_url") or detail.get("resized_image_url", "")
            if fresh_url:
                data, mt = await self._download_image(fresh_url)
                if data:
                    logger.info(f"Fresh URL worked (ScrapeCreators) for ad {ad_id}")
                    return data, mt
            else:
                logger.warning(f"No image URL in ScrapeCreators response for ad {ad_id}")
        except Exception as e:
            logger.warning(f"ScrapeCreators fetch failed for {ad_id}: {e}")

        # Fallback: SearchAPI.io
        try:
            from services.searchapi import searchapi
            if searchapi.is_configured:
                logger.info(f"Trying SearchAPI for image URL of ad {ad_id}")
                result = await searchapi.get_ad_details(ad_id)
                raw = result.get("raw", {})
                # SearchAPI returns snapshot with image URLs
                snapshot = raw.get("snapshot", {})
                images = snapshot.get("images", [])
                cards = snapshot.get("cards", [])
                fresh_url = ""
                if images:
                    fresh_url = images[0].get("original_image_url") or images[0].get("resized_image_url", "")
                if not fresh_url and cards:
                    fresh_url = cards[0].get("original_image_url") or cards[0].get("resized_image_url", "")
                if fresh_url:
                    data, mt = await self._download_image(fresh_url)
                    if data:
                        logger.info(f"Fresh URL worked (SearchAPI) for ad {ad_id}")
                        return data, mt
        except Exception as e:
            logger.warning(f"SearchAPI fetch failed for {ad_id}: {e}")

        return None, ""

    def _parse_analysis(self, text: str) -> Optional[dict]:
        """Parse Claude's JSON response into a validated dict."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end])
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse analysis JSON: {text[:200]}")
                    return None
            else:
                logger.error(f"No JSON found in response: {text[:200]}")
                return None

        # Validate and clamp score
        score = data.get("score", 0)
        if isinstance(score, (int, float)):
            data["score"] = max(0, min(100, int(score)))
        else:
            data["score"] = 0

        # Ensure arrays
        if not isinstance(data.get("dominant_colors"), list):
            data["dominant_colors"] = []
        if not isinstance(data.get("tags"), list):
            data["tags"] = []

        # Ensure strings
        for key in ("concept", "hook", "tone", "text_overlay", "layout", "cta_style", "summary",
                     "product_category", "product_subcategory", "ad_objective"):
            if key not in data or not isinstance(data[key], str):
                data[key] = ""

        # Ensure booleans
        for key in ("has_product", "has_face", "has_logo", "has_price"):
            data[key] = bool(data.get(key, False))

        return data


# Singleton
creative_analyzer = CreativeAnalyzer()
