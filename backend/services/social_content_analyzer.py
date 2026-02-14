"""
Social Content Analyzer Service.
Uses Anthropic Claude Haiku to analyze social media post/video text content.
Extracts: theme, hook, tone, format, CTA, hashtags, engagement score, summary.
"""
import asyncio
import json
import logging
import os
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """Tu es un expert en strategie social media pour la grande distribution et le retail en France.
Analyse ce contenu de post/video social media et retourne UNIQUEMENT un JSON valide (pas de markdown, pas de commentaire, pas de ```).

Contexte : plateforme={platform}, concurrent="{competitor_name}"
Titre : "{title}"
Description : "{description}"
Engagement : {views} vues, {likes} likes, {comments} commentaires, {shares} partages

JSON attendu :
{{
  "theme": "<UNE valeur parmi : promo, recette, lifestyle, tuto, behind-scenes, event, concours, produit, actu, humour, collab, saison, fidelite, rse>",
  "hook": "<1 phrase : ce qui capte l'attention dans les 1eres secondes/lignes>",
  "tone": "<UNE valeur parmi : fun, informatif, promotionnel, inspirant, urgence, communautaire, premium, educatif, emotionnel, authentique>",
  "format": "<UNE valeur parmi : short-form, long-form, carousel, reel, tutorial, unboxing, challenge, trend, interview>",
  "cta": "<appel a l'action identifie, ou 'none'>",
  "hashtags": ["hashtag1", "hashtag2"],
  "mentions": ["@mention1"],
  "virality_factors": ["facteur1", "facteur2"],
  "engagement_score": <entier 0-100>,
  "summary": "<1-2 phrases decrivant la strategie du contenu et son efficacite>"
}}

Criteres de score engagement_score :
- Hook / accroche (30%) : capacite a capter l'attention immediatement
- Alignement audience (25%) : pertinence pour la cible grande distribution
- Optimisation plateforme (25%) : adaptation au format et codes de la plateforme
- CTA / incitation (20%) : clarte de l'appel a l'action"""

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"


class SocialContentAnalyzer:
    """Analyze social media post content using Anthropic Claude Haiku."""

    @property
    def api_key(self) -> str:
        """Read API key from env vars or database."""
        key = (
            os.getenv("ANTHROPIC_API_KEY", "")
            or os.getenv("CLAUDE_KEY", "")
            or settings.ANTHROPIC_API_KEY
        )
        if key:
            return key
        try:
            from database import SessionLocal, SystemSetting
            db = SessionLocal()
            row = db.query(SystemSetting).filter(SystemSetting.key == "ANTHROPIC_API_KEY").first()
            db.close()
            return row.value if row else ""
        except Exception:
            return ""

    async def analyze_content(
        self,
        title: str = "",
        description: str = "",
        platform: str = "tiktok",
        competitor_name: str = "",
        views: int = 0,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
    ) -> Optional[dict]:
        """Analyze a single social post's text content with Claude Haiku.

        Returns parsed analysis dict or None on failure.
        """
        if not self.api_key:
            logger.error("Cannot analyze: ANTHROPIC_API_KEY not set")
            return None

        text_content = f"{title} {description}".strip()
        if not text_content:
            logger.warning("No text content to analyze")
            return None

        prompt = ANALYSIS_PROMPT.format(
            platform=platform,
            competitor_name=(competitor_name or "")[:100],
            title=(title or "")[:500],
            description=(description or "")[:1000],
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        CLAUDE_API_URL,
                        headers={
                            "x-api-key": self.api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-haiku-4-5-20251001",
                            "max_tokens": 512,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": prompt,
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
                text_response = result.get("content", [{}])[0].get("text", "")
                return self._parse_analysis(text_response)

            except httpx.TimeoutException:
                logger.error("Claude API timeout for social content analysis")
                return None
            except Exception as e:
                logger.error(f"Claude API error: {e}")
                return None

        logger.error("Claude: max retries reached for social content analysis")
        return None

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
        score = data.get("engagement_score", 0)
        if isinstance(score, (int, float)):
            data["engagement_score"] = max(0, min(100, int(score)))
        else:
            data["engagement_score"] = 0

        # Ensure arrays
        for key in ("hashtags", "mentions", "virality_factors"):
            if not isinstance(data.get(key), list):
                data[key] = []

        # Ensure strings
        for key in ("theme", "hook", "tone", "format", "cta", "summary"):
            if key not in data or not isinstance(data[key], str):
                data[key] = ""

        return data


# Singleton
social_content_analyzer = SocialContentAnalyzer()
