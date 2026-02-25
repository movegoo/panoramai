"""
Creative Analyzer Service — Multi-model strategy.
- Images: Gemini 2.5 Flash (vision)
- Text-only: Gemini 2.0 Flash + Mistral Small 3.2 (double analysis with fusion)
Extracts: concept, hook, tone, colors, text overlay, score, tags, etc.
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

# ── Shared prompt (works for both vision and text models) ────────────

ANALYSIS_PROMPT = """Tu es un expert senior en analyse créative publicitaire, spécialisé en retail/grande distribution en France.
Analyse ce visuel publicitaire EN PROFONDEUR et retourne UNIQUEMENT un JSON valide (pas de markdown, pas de ```, pas de commentaire).
TOUTES les valeurs doivent être en FRANÇAIS. Sois EXHAUSTIF et PRÉCIS.

Contexte : plateforme={platform}, texte de la pub="{ad_text}"

JSON attendu :
{{
  "concept": "<UNE valeur parmi : photo-produit, mise-en-scène, ugc, promo, témoignage, avant-après, tutoriel, saisonnier, événement, comparatif, storytelling, influenceur, recette, catalogue, jeu-concours, engagement-RSE, vidéo-teaser, démonstration, unboxing, avis-client>",
  "hook": "<1 phrase en français : ce qui capte l'attention en premier>",
  "tone": "<UNE valeur parmi : urgence, aspiration, humour, confiance, fomo, communauté, premium, bon-plan, pédagogique, émotion, ludique, audacieux, minimaliste, festif, familial, écologique, provocation, nostalgie, exclusivité>",
  "text_overlay": "<TOUT le texte visible sur le visuel, verbatim, séparé par des |>",
  "dominant_colors": ["#HEX1", "#HEX2", "#HEX3"],
  "has_product": true ou false,
  "has_face": true ou false,
  "has_logo": true ou false,
  "has_price": true ou false,
  "layout": "<UNE valeur parmi : image-unique, split, collage, plein-écran, texte-dominant, minimaliste, avant-après, grille-produits, hero, carrousel, vidéo-cover, story-format>",
  "cta_style": "<UNE valeur parmi : bouton, texte, flèche, badge, swipe-up, lien, aucun>",
  "score": <entier 0-100>,
  "tags": ["mot-clé1", "mot-clé2", "mot-clé3", "mot-clé4", "mot-clé5"],
  "summary": "<2-3 phrases en français : description détaillée de l'approche créative, forces, faiblesses, et efficacité probable>",
  "product_category": "<UNE valeur parmi : Épicerie, Boissons, Frais, Surgelés, Fruits & Légumes, Boucherie & Volaille, Poissonnerie, Boulangerie, DPH, Beauté & Parfumerie, Hygiène, Entretien, Textile & Mode, Électroménager, Multimédia & High-Tech, Jouets & Loisirs, Sport, Bricolage & Jardin, Ameublement & Déco, Auto & Mobilité, Animalerie, Bio & Écologie, Services, Fidélité & Programme, Marque Employeur, Corporate & RSE, Multi-rayons, Voyages & Tourisme, Banque & Assurance, Télécom, Restauration, Pharmacie & Santé, Optique, Luxe, Autre>",
  "product_subcategory": "<sous-catégorie PRÉCISE, en français, ex: Yaourts bio, Café capsules, Bières artisanales, Lessive liquide, iPhone 16, Matelas mémoire de forme, Drive express, Carte fidélité premium...>",
  "ad_objective": "<UNE valeur parmi : notoriété, trafic, conversion, fidélisation, recrutement, RSE, lancement-produit, promotion, saisonnier, drive-to-store, app-install, engagement, lead-generation>",
  "promo_type": "<UNE valeur parmi : prix-barré, pourcentage, lot, offre-spéciale, carte-fidélité, code-promo, gratuit, vente-flash, cashback, essai-gratuit, aucune>",
  "creative_format": "<UNE valeur parmi : catalogue, produit-unique, multi-produits, ambiance, événement, recrutement, vidéo, carrousel, story, avant-après, infographie>",
  "price_visible": true ou false,
  "price_value": "<le prix EXACT si visible, ex: 2,99€, sinon vide>",
  "seasonal_event": "<UNE valeur parmi : noël, rentrée, été, soldes, black-friday, saint-valentin, pâques, fête-des-mères, fête-des-pères, halloween, nouvel-an, printemps, aucun>",
  "brand_visible": "<nom de la marque/enseigne visible sur la pub, ou vide>",
  "target_audience": "<public cible probable, ex: Familles avec enfants, Jeunes actifs 25-35, Seniors, Sportifs, Femmes 30-50...>",
  "emotional_trigger": "<le levier émotionnel principal utilisé, ex: peur de manquer, sentiment d'appartenance, fierté, envie, curiosité, nostalgie, surprise>",
  "competitive_angle": "<si la pub se positionne vs la concurrence, décrire comment, sinon vide>",
  "media_type": "<image, vidéo-preview, carrousel, gif, texte-seul>",
  "copy_quality": "<note 1-10 sur la qualité du texte publicitaire (accroche, clarté, persuasion)>",
  "visual_quality": "<note 1-10 sur la qualité visuelle (composition, lumière, professionnalisme)>",
  "brand_consistency": "<note 1-10 sur la cohérence avec l'image de marque de l'enseigne>"
}}

Critères de score global (0-100) :
- Impact visuel (25%) : contraste, composition, accroche immédiate
- Clarté du message (25%) : compréhension de l'offre en moins de 3 secondes
- Exécution professionnelle (25%) : qualité graphique, cohérence marque, finition
- Persuasion (25%) : incitation à l'action, urgence, désirabilité, différenciation

IMPORTANT :
- Si la pub concerne plusieurs rayons (ex: catalogue général), utilise "Multi-rayons".
- Si c'est une vidéo (preview/thumbnail), analyse le frame visible et indique "vidéo-preview" en media_type.
- Sois GÉNÉREUX dans le summary : donne le maximum de contexte utile pour un analyste concurrentiel."""

TEXT_ANALYSIS_PROMPT = """Tu es un expert senior en analyse publicitaire digitale en France, spécialisé en Google Ads (Search, Display, YouTube) et publicité textuelle.
Analyse ce TEXTE publicitaire ({platform}) EN PROFONDEUR et retourne UNIQUEMENT un JSON valide.
TOUTES les valeurs doivent être en FRANÇAIS. Sois EXHAUSTIF.

Texte de la pub : "{ad_text}"

JSON attendu :
{{
  "concept": "<UNE valeur parmi : photo-produit, mise-en-scène, ugc, promo, témoignage, avant-après, tutoriel, saisonnier, événement, comparatif, storytelling, influenceur, recette, catalogue, jeu-concours, engagement-RSE, vidéo-teaser, démonstration, avis-client, branding>",
  "hook": "<1 phrase : ce qui capte l'attention en premier>",
  "tone": "<UNE valeur parmi : urgence, aspiration, humour, confiance, fomo, communauté, premium, bon-plan, pédagogique, émotion, ludique, audacieux, minimaliste, festif, familial, écologique, provocation, nostalgie, exclusivité>",
  "text_overlay": "<le texte intégral de la pub, verbatim>",
  "dominant_colors": [],
  "has_product": false,
  "has_face": false,
  "has_logo": false,
  "has_price": true ou false,
  "layout": "texte-dominant",
  "cta_style": "<UNE valeur parmi : bouton, texte, lien, swipe-up, aucun>",
  "score": <entier 0-100>,
  "tags": ["mot-clé1", "mot-clé2", "mot-clé3", "mot-clé4", "mot-clé5"],
  "summary": "<2-3 phrases : analyse détaillée de la stratégie textuelle, forces, faiblesses, et efficacité probable pour le public cible>",
  "product_category": "<catégorie parmi : Épicerie, Boissons, Frais, Surgelés, Fruits & Légumes, DPH, Beauté & Parfumerie, Textile & Mode, Électroménager, Multimédia & High-Tech, Sport, Bricolage & Jardin, Ameublement & Déco, Services, Fidélité & Programme, Marque Employeur, Corporate & RSE, Multi-rayons, Voyages & Tourisme, Banque & Assurance, Télécom, Restauration, Pharmacie & Santé, Optique, Luxe, Autre>",
  "product_subcategory": "<sous-catégorie PRÉCISE, ex: Forfait mobile 5G, Crédit immobilier, Cuisine équipée, Pneus été...>",
  "ad_objective": "<UNE valeur parmi : notoriété, trafic, conversion, fidélisation, recrutement, RSE, lancement-produit, promotion, saisonnier, drive-to-store, app-install, engagement, lead-generation>",
  "promo_type": "<UNE valeur parmi : prix-barré, pourcentage, lot, offre-spéciale, carte-fidélité, code-promo, gratuit, vente-flash, cashback, essai-gratuit, aucune>",
  "creative_format": "texte",
  "price_visible": true ou false,
  "price_value": "<prix EXACT si visible, sinon vide>",
  "seasonal_event": "<UNE valeur parmi : noël, rentrée, été, soldes, black-friday, saint-valentin, pâques, fête-des-mères, fête-des-pères, halloween, nouvel-an, printemps, aucun>",
  "brand_visible": "<nom de la marque/enseigne mentionnée dans le texte, ou vide>",
  "target_audience": "<public cible probable déduit du texte, ex: Propriétaires, Étudiants, Parents, Professionnels...>",
  "emotional_trigger": "<levier émotionnel principal, ex: économie, peur de manquer, curiosité, fierté, confort, sécurité>",
  "competitive_angle": "<si le texte se positionne vs la concurrence, décrire comment, sinon vide>",
  "media_type": "texte-seul",
  "copy_quality": "<note 1-10 sur la qualité rédactionnelle (accroche, clarté, persuasion, CTA)>",
  "visual_quality": 0,
  "brand_consistency": "<note 1-10 sur la cohérence avec l'image de marque>"
}}

Critères de score (0-100) :
- Accroche (30%) : le titre/hook capte-t-il l'attention immédiatement ?
- Clarté (25%) : l'offre est-elle compréhensible en 3 secondes ?
- Persuasion (25%) : le texte donne-t-il envie d'agir ?
- Professionnalisme (20%) : orthographe, structure, cohérence

IMPORTANT : Analyse aussi les extensions (sitelinks, callouts) si présentes dans le texte."""""

# ── API endpoints ────────────────────────────────────────────────────

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# Categorical fields where we use "stronger model wins" on disagreement
CATEGORICAL_FIELDS = (
    "concept", "tone", "layout", "cta_style", "product_category",
    "product_subcategory", "ad_objective", "promo_type", "creative_format",
    "seasonal_event",
)


class CreativeAnalyzer:
    """Multi-model ad creative analyzer."""

    # ── API key helpers ──────────────────────────────────────────────

    @property
    def gemini_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "") or settings.GEMINI_API_KEY

    @property
    def mistral_key(self) -> str:
        return os.getenv("MISTRAL_API_KEY", "") or settings.MISTRAL_API_KEY

    @property
    def api_key(self) -> str:
        """Anthropic key — kept as fallback."""
        return (
            os.getenv("ANTHROPIC_API_KEY", "")
            or os.getenv("CLAUDE_KEY", "")
            or settings.ANTHROPIC_API_KEY
        )

    # ── Public analysis methods ──────────────────────────────────────

    async def analyze_creative(
        self,
        creative_url: str,
        ad_text: str = "",
        platform: str = "meta",
        ad_id: str = "",
    ) -> Optional[dict]:
        """Analyze an ad creative image with Gemini 2.5 Flash vision."""
        if not self.gemini_key:
            logger.error("Cannot analyze: GEMINI_API_KEY not set")
            return None
        if not creative_url:
            return None

        # Download image — tries Meta API (free), ScrapeCreators, SearchAPI
        image_data, media_type, fresh_url = await self._get_image(creative_url, ad_id)
        if not image_data:
            logger.error(f"Image download failed for: {creative_url[:100]}")
            return None

        b64_image = base64.standard_b64encode(image_data).decode("utf-8")

        prompt = ANALYSIS_PROMPT.format(
            platform=platform,
            ad_text=(ad_text or "")[:500],
        )

        result = await self._call_gemini_vision(
            b64_image, media_type, prompt,
            model="gemini-3-flash-preview",
            ad_id=ad_id,
        )

        # Attach fresh URL so caller can persist it in DB
        if result and fresh_url:
            result["_fresh_url"] = fresh_url

        return result

    async def analyze_text_only(
        self,
        ad_text: str,
        platform: str = "google",
        ad_id: str = "",
    ) -> Optional[dict]:
        """Double analysis: Gemini 2.0 Flash + Mistral Small, then fuse."""
        if not ad_text or len(ad_text.strip()) < 10:
            return None

        prompt = TEXT_ANALYSIS_PROMPT.format(
            platform=platform,
            ad_text=ad_text[:1000],
        )

        # Run both models in parallel
        gemini_task = self._call_gemini_text(prompt, model="gemini-3-flash-preview")
        mistral_task = self._call_mistral(prompt, model="mistral-small-latest")

        results = await asyncio.gather(gemini_task, mistral_task, return_exceptions=True)

        gemini_result = results[0] if not isinstance(results[0], Exception) else None
        mistral_result = results[1] if not isinstance(results[1], Exception) else None

        if isinstance(results[0], Exception):
            logger.warning(f"Gemini text error for {ad_id}: {results[0]}")
        if isinstance(results[1], Exception):
            logger.warning(f"Mistral text error for {ad_id}: {results[1]}")

        # Fuse results
        return self._fuse_text_results(gemini_result, mistral_result, ad_id)

    # ── Gemini Vision API ────────────────────────────────────────────

    async def _call_gemini_vision(
        self,
        b64_image: str,
        media_type: str,
        prompt: str,
        model: str = "gemini-3-flash-preview",
        ad_id: str = "",
    ) -> Optional[dict]:
        url = GEMINI_API_URL.format(model=model) + f"?key={self.gemini_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": media_type, "data": b64_image}},
                    {"text": prompt},
                ],
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
            },
        }
        return await self._call_api("Gemini-Vision", url, payload, ad_id, is_gemini=True)

    # ── Gemini Text API ──────────────────────────────────────────────

    async def _call_gemini_text(
        self,
        prompt: str,
        model: str = "gemini-3-flash-preview",
    ) -> Optional[dict]:
        if not self.gemini_key:
            return None
        url = GEMINI_API_URL.format(model=model) + f"?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
            },
        }
        return await self._call_api("Gemini-Text", url, payload, "", is_gemini=True)

    # ── Mistral API ──────────────────────────────────────────────────

    async def _call_mistral(
        self,
        prompt: str,
        model: str = "mistral-small-latest",
    ) -> Optional[dict]:
        if not self.mistral_key:
            return None
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.mistral_key}",
            "Content-Type": "application/json",
        }
        return await self._call_api(
            "Mistral", MISTRAL_API_URL, payload, "",
            is_gemini=False, headers=headers,
        )

    # ── Unified API caller with retries ──────────────────────────────

    async def _call_api(
        self,
        label: str,
        url: str,
        payload: dict,
        ad_id: str,
        is_gemini: bool = True,
        headers: dict | None = None,
    ) -> Optional[dict]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        url,
                        json=payload,
                        headers=headers or {"Content-Type": "application/json"},
                    )

                if resp.status_code == 429:
                    wait = 10 * (attempt + 1)
                    logger.warning(f"{label} rate limit (429), waiting {wait}s")
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code != 200:
                    logger.error(f"{label} API error {resp.status_code}: {resp.text[:300]}")
                    return None

                # Extract text content
                body = resp.json()
                if is_gemini:
                    candidates = body.get("candidates", [])
                    if not candidates:
                        logger.error(f"{label}: no candidates in response")
                        return None
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text_content = parts[0].get("text", "") if parts else ""
                else:
                    # Mistral / OpenAI format
                    choices = body.get("choices", [])
                    text_content = choices[0]["message"]["content"] if choices else ""

                return self._parse_analysis(text_content)

            except httpx.TimeoutException:
                logger.error(f"{label} timeout for {ad_id or 'text'}")
                return None
            except Exception as e:
                logger.error(f"{label} error: {e}")
                return None

        logger.error(f"{label}: max retries reached for {ad_id or 'text'}")
        return None

    # ── Fusion logic for double text analysis ────────────────────────

    def _fuse_text_results(
        self,
        gemini: Optional[dict],
        mistral: Optional[dict],
        ad_id: str = "",
    ) -> Optional[dict]:
        """Fuse Gemini + Mistral text results. Gemini wins on disagreement."""
        if gemini and not mistral:
            logger.info(f"Text fusion {ad_id}: Gemini only (Mistral failed)")
            return gemini
        if mistral and not gemini:
            logger.info(f"Text fusion {ad_id}: Mistral only (Gemini failed)")
            return mistral
        if not gemini and not mistral:
            return None

        fused = dict(gemini)  # Start with Gemini as base (stronger model)
        disagreements = 0

        # Categorical fields: Gemini wins on disagreement
        for field in CATEGORICAL_FIELDS:
            g_val = gemini.get(field, "")
            m_val = mistral.get(field, "")
            if g_val and m_val and g_val != m_val:
                disagreements += 1
                # Keep Gemini value (already in fused)

        # Numeric score: average of both
        g_score = gemini.get("score", 0)
        m_score = mistral.get("score", 0)
        if g_score and m_score:
            fused["score"] = round((g_score + m_score) / 2)

        # Merge tags from both (deduplicated)
        g_tags = set(gemini.get("tags", []))
        m_tags = set(mistral.get("tags", []))
        fused["tags"] = list(g_tags | m_tags)[:7]

        # Use longer summary
        g_summary = gemini.get("summary", "")
        m_summary = mistral.get("summary", "")
        if len(m_summary) > len(g_summary):
            fused["summary"] = m_summary

        # Use longer/richer hook
        g_hook = gemini.get("hook", "")
        m_hook = mistral.get("hook", "")
        if len(m_hook) > len(g_hook):
            fused["hook"] = m_hook

        total_fields = len(CATEGORICAL_FIELDS)
        pct = round(disagreements / total_fields * 100) if total_fields else 0
        if disagreements > 0:
            logger.info(
                f"Text fusion {ad_id}: {disagreements}/{total_fields} disagreements ({pct}%), "
                f"scores G={g_score}/M={m_score}→{fused['score']}"
            )

        return fused

    # ── Image download helpers (unchanged) ───────────────────────────

    async def _get_image(self, creative_url: str, ad_id: str) -> tuple[Optional[bytes], str, str]:
        """Download image with ScrapeCreators/SearchAPI fallback.
        Returns (image_data, media_type, fresh_url) — fresh_url is set when
        ScrapeCreators provided a new URL (caller should persist it in DB).
        """
        image_data = None
        media_type = ""
        fresh_url = ""

        # Always try ScrapeCreators first when we have an ad_id — gets a fresh
        # fbcdn URL and avoids wasting time on broken render_ad / expired URLs.
        if ad_id:
            image_data, media_type, fresh_url = await self._fetch_fresh_image(ad_id)

        # Fallback: try the stored URL directly
        if not image_data:
            image_data, media_type = await self._download_image(creative_url)

        return image_data, media_type, fresh_url

    async def _download_image(self, url: str) -> tuple[Optional[bytes], str]:
        """Download image from URL. Returns (bytes, media_type) or (None, '')."""
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url)

            if response.status_code != 200:
                logger.error(f"Image download HTTP {response.status_code}: {url[:100]}")
                return None, ""

            data = response.content
            media_type = self._detect_media_type(data)
            if not media_type:
                content_type = response.headers.get("content-type", "")
                media_type = content_type.split(";")[0].strip()
                if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
                    media_type = "image/jpeg"

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

    @staticmethod
    def _detect_media_type(data: bytes) -> str:
        """Detect image media type from magic bytes."""
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        if data[:2] == b'\xff\xd8':
            return "image/jpeg"
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return "image/webp"
        if data[:6] in (b'GIF87a', b'GIF89a'):
            return "image/gif"
        return ""

    async def _fetch_fresh_image(self, ad_id: str) -> tuple[Optional[bytes], str, str]:
        """Fetch a fresh image URL and download it.
        Tries Meta Graph API (free) first, then ScrapeCreators, then SearchAPI.
        Returns (image_data, media_type, fresh_url).
        """
        # 1) Meta Graph API — FREE: get ad_snapshot_url with valid access_token
        try:
            import os
            meta_token = os.getenv("META_ACCESS_TOKEN", "")
            if meta_token:
                import httpx as _httpx
                snapshot_url = (
                    f"https://graph.facebook.com/v19.0/ads_archive"
                    f"?access_token={meta_token}"
                    f"&search_terms="
                    f"&ad_type=ALL"
                    f"&fields=ad_snapshot_url"
                    f"&search_page_ids="
                    f"&ad_reached_countries=FR"
                    f"&limit=1"
                )
                # The ads_archive endpoint doesn't support lookup by ad_id directly,
                # but ad_snapshot_url = render_ad URL with fresh token.
                # Build the snapshot URL directly:
                fresh_snapshot = f"https://www.facebook.com/ads/archive/render_ad/?id={ad_id}&access_token={meta_token}"
                logger.info(f"Trying Meta snapshot URL for ad {ad_id}")
                async with _httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                    resp = await client.get(fresh_snapshot)
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "")
                    # If it returns an image directly
                    if ct.startswith("image/"):
                        data = resp.content
                        mt = self._detect_media_type(data) or ct.split(";")[0].strip()
                        if len(data) >= 1000:
                            logger.info(f"Meta snapshot returned image for ad {ad_id}: {len(data)} bytes")
                            return data, mt, fresh_snapshot
                    # If it returns HTML, try to extract the image src
                    elif "text/html" in ct:
                        html = resp.text
                        import re
                        img_match = re.search(r'<img[^>]+src="([^"]+fbcdn[^"]+)"', html)
                        if img_match:
                            img_url = img_match.group(1).replace("&amp;", "&")
                            data, mt = await self._download_image(img_url)
                            if data:
                                logger.info(f"Meta snapshot HTML -> fbcdn image for ad {ad_id}")
                                return data, mt, img_url
        except Exception as e:
            logger.warning(f"Meta snapshot fetch failed for {ad_id}: {e}")

        # 2) ScrapeCreators — gets fbcdn URL from ad detail
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
                    logger.info(f"Fresh URL worked (ScrapeCreators) for ad {ad_id}: {fresh_url[:80]}")
                    return data, mt, fresh_url
            else:
                logger.warning(f"No image URL in ScrapeCreators response for ad {ad_id}")
        except Exception as e:
            logger.warning(f"ScrapeCreators fetch failed for {ad_id}: {e}")

        # 3) SearchAPI fallback
        try:
            from services.searchapi import searchapi
            if searchapi.is_configured:
                logger.info(f"Trying SearchAPI for image URL of ad {ad_id}")
                result = await searchapi.get_ad_details(ad_id)
                raw = result.get("raw", {})
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
                        logger.info(f"Fresh URL worked (SearchAPI) for ad {ad_id}: {fresh_url[:80]}")
                        return data, mt, fresh_url
        except Exception as e:
            logger.warning(f"SearchAPI fetch failed for {ad_id}: {e}")

        return None, "", ""

    # ── JSON parser (shared across all models) ───────────────────────

    def _parse_analysis(self, text: str) -> Optional[dict]:
        """Parse model JSON response into a validated dict."""
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
                # Try to fix truncated JSON by closing brackets
                if start >= 0:
                    truncated = text[start:]
                    # Count unmatched braces/brackets and close them
                    open_braces = truncated.count("{") - truncated.count("}")
                    open_brackets = truncated.count("[") - truncated.count("]")
                    fixed = truncated + "]" * open_brackets + "}" * open_braces
                    try:
                        data = json.loads(fixed)
                        logger.warning(f"Fixed truncated JSON (added {open_braces}}} {open_brackets}])")
                    except json.JSONDecodeError:
                        logger.error(f"No JSON found in response: {text[:300]}")
                        return None
                else:
                    logger.error(f"No JSON found in response: {text[:300]}")
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
                     "product_category", "product_subcategory", "ad_objective",
                     "promo_type", "creative_format", "price_value", "seasonal_event"):
            if key not in data or not isinstance(data[key], str):
                data[key] = ""

        # Ensure booleans
        for key in ("has_product", "has_face", "has_logo", "has_price", "price_visible"):
            data[key] = bool(data.get(key, False))

        return data


# Singleton
creative_analyzer = CreativeAnalyzer()
