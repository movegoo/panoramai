"""
Creative Analyzer Service.
Uses Anthropic Claude Vision API to analyze ad creative images.
Extracts: concept, hook, tone, colors, text overlay, score, tags.
"""
import base64
import json
import logging
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """Tu es un expert en analyse créative publicitaire pour la grande distribution et le retail.
Analyse ce visuel publicitaire et retourne UNIQUEMENT un JSON valide (pas de markdown, pas de commentaire).

Contexte : plateforme={platform}, texte de la pub="{ad_text}"

JSON attendu :
{{
  "concept": "<UNE valeur parmi : product-shot, lifestyle, ugc-style, promo, testimonial, before-after, tutorial, seasonal, event, comparison, story, influencer, recipe, catalogue>",
  "hook": "<1 phrase : ce qui capte l'attention en premier>",
  "tone": "<UNE valeur parmi : urgency, aspiration, humor, trust, fomo, community, premium, value, educational, emotional, playful, bold, minimalist, festive>",
  "text_overlay": "<tout le texte visible sur le visuel, verbatim, séparé par des |>",
  "dominant_colors": ["#HEX1", "#HEX2", "#HEX3"],
  "has_product": true ou false,
  "has_face": true ou false,
  "has_logo": true ou false,
  "layout": "<UNE valeur parmi : single-image, split, collage, full-bleed, text-heavy, minimal, before-after, product-grid, hero-image>",
  "cta_style": "<UNE valeur parmi : button, text, arrow, badge, none>",
  "score": <entier 0-100>,
  "tags": ["mot-clé1", "mot-clé2", "mot-clé3", "mot-clé4", "mot-clé5"],
  "summary": "<1-2 phrases décrivant l'approche créative et son efficacité probable>"
}}

Critères de score :
- Impact visuel (30%) : contraste, composition, accroche
- Clarté du message (25%) : compréhension immédiate de l'offre
- Exécution professionnelle (25%) : qualité graphique, cohérence
- Persuasion (20%) : incitation à l'action, urgence, désirabilité"""

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


class CreativeAnalyzer:
    """Analyze ad creatives using Claude Vision API."""

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured. Creative analysis disabled.")

    async def analyze_creative(
        self,
        creative_url: str,
        ad_text: str = "",
        platform: str = "meta",
    ) -> Optional[dict]:
        """Analyze a single ad creative image with Claude Vision.

        Returns parsed analysis dict or None on failure.
        """
        if not self.api_key:
            logger.error("Cannot analyze: ANTHROPIC_API_KEY not set")
            return None

        if not creative_url:
            return None

        # Download image
        image_data, media_type = await self._download_image(creative_url)
        if not image_data:
            return None

        # Encode to base64
        b64_image = base64.standard_b64encode(image_data).decode("utf-8")

        # Build prompt
        prompt = ANALYSIS_PROMPT.format(
            platform=platform,
            ad_text=(ad_text or "")[:500],
        )

        # Call Claude API
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-5-20250929",
                        "max_tokens": 1024,
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

            if response.status_code != 200:
                logger.error(f"Claude API error {response.status_code}: {response.text[:300]}")
                return None

            result = response.json()
            text_content = result.get("content", [{}])[0].get("text", "")
            return self._parse_analysis(text_content)

        except httpx.TimeoutException:
            logger.error(f"Claude API timeout for {creative_url[:80]}")
            return None
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    async def _download_image(self, url: str) -> tuple[Optional[bytes], str]:
        """Download image from URL. Returns (bytes, media_type) or (None, '')."""
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url)

            if response.status_code != 200:
                logger.warning(f"Image download failed ({response.status_code}): {url[:80]}")
                return None, ""

            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                # Try to infer from URL
                if ".png" in url.lower():
                    content_type = "image/png"
                elif ".webp" in url.lower():
                    content_type = "image/webp"
                elif ".gif" in url.lower():
                    content_type = "image/gif"
                else:
                    content_type = "image/jpeg"

            # Normalize media type
            media_type = content_type.split(";")[0].strip()
            if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
                media_type = "image/jpeg"

            data = response.content
            if len(data) > MAX_IMAGE_SIZE:
                logger.warning(f"Image too large ({len(data)} bytes): {url[:80]}")
                return None, ""

            if len(data) < 1000:
                logger.warning(f"Image too small ({len(data)} bytes), likely broken: {url[:80]}")
                return None, ""

            return data, media_type

        except Exception as e:
            logger.warning(f"Image download error: {e}")
            return None, ""

    def _parse_analysis(self, text: str) -> Optional[dict]:
        """Parse Claude's JSON response into a validated dict."""
        # Strip markdown code blocks if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
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
        for key in ("concept", "hook", "tone", "text_overlay", "layout", "cta_style", "summary"):
            if key not in data or not isinstance(data[key], str):
                data[key] = ""

        # Ensure booleans
        for key in ("has_product", "has_face", "has_logo"):
            data[key] = bool(data.get(key, False))

        return data


# Singleton
creative_analyzer = CreativeAnalyzer()
