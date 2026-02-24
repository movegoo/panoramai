"""
Social Content Analyzer Service.
Uses Gemini Flash + Mistral to analyze social media post/video text content.
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

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


class SocialContentAnalyzer:
    """Analyze social media post content using Gemini Flash + Mistral."""

    @property
    def gemini_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "") or settings.GEMINI_API_KEY

    @property
    def mistral_key(self) -> str:
        return os.getenv("MISTRAL_API_KEY", "") or settings.MISTRAL_API_KEY

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
        """Analyze a single social post with Gemini + Mistral (parallel), fuse results."""
        if not self.gemini_key and not self.mistral_key:
            logger.error("Cannot analyze: neither GEMINI_API_KEY nor MISTRAL_API_KEY set")
            return None

        text_content = f"{title} {description}".strip()
        if not text_content:
            logger.warning("No text content to analyze")
            return None

        # Load prompt from DB (fallback to hardcoded)
        db_prompt_text = ANALYSIS_PROMPT
        try:
            from database import SessionLocal, PromptTemplate
            _db = SessionLocal()
            row = _db.query(PromptTemplate).filter(PromptTemplate.key == "social_content").first()
            if row:
                db_prompt_text = row.prompt_text
            _db.close()
        except Exception:
            pass

        prompt = db_prompt_text.format(
            platform=platform,
            competitor_name=(competitor_name or "")[:100],
            title=(title or "")[:500],
            description=(description or "")[:1000],
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
        )

        # Run Gemini + Mistral in parallel
        gemini_task = self._call_gemini(prompt)
        mistral_task = self._call_mistral(prompt)

        results = await asyncio.gather(gemini_task, mistral_task, return_exceptions=True)

        gemini_result = results[0] if not isinstance(results[0], Exception) else None
        mistral_result = results[1] if not isinstance(results[1], Exception) else None

        if isinstance(results[0], Exception):
            logger.warning(f"Gemini error for social content: {results[0]}")
        if isinstance(results[1], Exception):
            logger.warning(f"Mistral error for social content: {results[1]}")

        return self._fuse_results(gemini_result, mistral_result)

    async def _call_gemini(self, prompt: str, model: str = "gemini-2.0-flash") -> Optional[dict]:
        if not self.gemini_key:
            return None
        url = GEMINI_API_URL.format(model=model) + f"?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 1024,
                "temperature": 0.3,
                "responseMimeType": "application/json",
            },
        }
        return await self._call_api("Gemini", url, payload, is_gemini=True)

    async def _call_mistral(self, prompt: str, model: str = "mistral-small-latest") -> Optional[dict]:
        if not self.mistral_key:
            return None
        headers = {
            "Authorization": f"Bearer {self.mistral_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        return await self._call_api("Mistral", MISTRAL_API_URL, payload, is_gemini=False, headers=headers)

    async def _call_api(
        self,
        label: str,
        url: str,
        payload: dict,
        is_gemini: bool = True,
        headers: dict | None = None,
    ) -> Optional[dict]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)

                if resp.status_code == 429:
                    wait = 10 * (attempt + 1)
                    logger.warning(f"{label} rate limit (429), waiting {wait}s")
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code not in (200,):
                    logger.error(f"{label} API error {resp.status_code}: {resp.text[:300]}")
                    return None

                body = resp.json()
                if is_gemini:
                    candidates = body.get("candidates", [])
                    if not candidates:
                        logger.error(f"{label}: no candidates in response")
                        return None
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                else:
                    text = body.get("choices", [{}])[0].get("message", {}).get("content", "")

                from core.langfuse_client import trace_generation
                usage = body.get("usage", body.get("usageMetadata", {}))
                trace_generation(
                    name=f"social_content_{label.lower()}",
                    model=payload.get("model", "gemini-2.0-flash"),
                    input=payload.get("contents", [{}])[0].get("parts", [{}])[0].get("text", "")
                        if is_gemini else payload.get("messages", [{}])[0].get("content", ""),
                    output=text,
                    usage={"input_tokens": usage.get("input_tokens", usage.get("promptTokenCount")),
                           "output_tokens": usage.get("output_tokens", usage.get("candidatesTokenCount"))},
                )

                return self._parse_analysis(text)

            except httpx.TimeoutException:
                logger.error(f"{label} API timeout for social content analysis")
                return None
            except Exception as e:
                logger.error(f"{label} API error: {e}")
                return None

        logger.error(f"{label}: max retries reached for social content analysis")
        return None

    def _fuse_results(self, gemini: Optional[dict], mistral: Optional[dict]) -> Optional[dict]:
        """Fuse Gemini + Mistral results. Gemini wins on disagreement."""
        if gemini and not mistral:
            return gemini
        if mistral and not gemini:
            return mistral
        if not gemini and not mistral:
            return None

        fused = dict(gemini)

        # Numeric score: average
        g_score = gemini.get("engagement_score", 0)
        m_score = mistral.get("engagement_score", 0)
        if g_score and m_score:
            fused["engagement_score"] = round((g_score + m_score) / 2)

        # Merge hashtags
        g_tags = set(gemini.get("hashtags", []))
        m_tags = set(mistral.get("hashtags", []))
        fused["hashtags"] = list(g_tags | m_tags)[:10]

        # Merge virality factors
        g_vf = set(gemini.get("virality_factors", []))
        m_vf = set(mistral.get("virality_factors", []))
        fused["virality_factors"] = list(g_vf | m_vf)[:5]

        # Use longer summary
        if len(mistral.get("summary", "")) > len(gemini.get("summary", "")):
            fused["summary"] = mistral["summary"]

        # Use longer hook
        if len(mistral.get("hook", "")) > len(gemini.get("hook", "")):
            fused["hook"] = mistral["hook"]

        return fused

    def _parse_analysis(self, text: str) -> Optional[dict]:
        """Parse JSON response into a validated dict."""
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
