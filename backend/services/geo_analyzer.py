"""
GEO (Generative Engine Optimization) Analyzer.
Queries Claude and Gemini with retail-focused questions, then analyses
which brands are mentioned, recommended, and in what order.
"""
import asyncio
import json
import logging
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

GEO_QUERIES = [
    {"keyword": "courses en ligne", "query": "Quel est le meilleur service de courses en ligne en France ?"},
    {"keyword": "drive supermarché", "query": "Quel supermarché propose le meilleur service drive en France ?"},
    {"keyword": "livraison courses domicile", "query": "Quel service de livraison de courses à domicile recommandes-tu en France ?"},
    {"keyword": "promo supermarché", "query": "Quel supermarché propose les meilleures promotions en France ?"},
    {"keyword": "carte fidélité supermarché", "query": "Quelle est la meilleure carte de fidélité de supermarché en France ?"},
    {"keyword": "supermarché pas cher", "query": "Quel est le supermarché le moins cher en France ?"},
    {"keyword": "application courses", "query": "Quelle est la meilleure application pour faire ses courses en France ?"},
    {"keyword": "produits bio supermarché", "query": "Quel supermarché a le meilleur rayon bio en France ?"},
    {"keyword": "click and collect courses", "query": "Quel supermarché propose le meilleur click and collect en France ?"},
    {"keyword": "meilleur supermarché", "query": "Quel est le meilleur supermarché en France en 2026 ?"},
    {"keyword": "comparatif prix supermarché", "query": "Comparatif des prix entre Carrefour, Leclerc, Lidl et Auchan : lequel est le moins cher ?"},
    {"keyword": "marque distributeur", "query": "Quel supermarché a les meilleures marques distributeur en France ?"},
]

SYSTEM_PROMPT = (
    "Tu es un assistant qui aide les consommateurs français à choisir "
    "le meilleur supermarché ou service de courses. Réponds de façon concise "
    "et factuelle, en citant les enseignes par leur nom."
)

ANALYSIS_PROMPT = """Analyse cette réponse d'un moteur IA à la question "{query}".
Identifie les marques de grande distribution mentionnées parmi : {brand_names}.

Réponds UNIQUEMENT avec du JSON valide, sans markdown ni texte autour.
JSON attendu :
{{
  "brands_mentioned": [
    {{
      "name": "NomMarque",
      "position": 1,
      "recommended": true,
      "sentiment": "positif",
      "context": "cité comme leader du drive"
    }}
  ],
  "total_brands_mentioned": 3,
  "primary_recommendation": "NomMarque",
  "answer_quality": "comparative",
  "key_criteria": ["prix", "réseau", "qualité"]
}}

Réponse à analyser :
{answer}"""


class GeoAnalyzer:
    """Queries AI engines and analyses brand visibility in their responses."""

    async def _query_claude(self, query: str) -> str:
        """Query Claude Haiku via Anthropic API."""
        if not settings.ANTHROPIC_API_KEY:
            return ""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 1000,
                        "system": SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": query}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]
        except Exception as e:
            logger.error(f"Claude query error: {e}")
            return ""

    async def _query_gemini(self, query: str) -> str:
        """Query Gemini via Google AI REST API."""
        if not settings.GEMINI_API_KEY:
            return ""
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}"
            )
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    headers={"content-type": "application/json"},
                    json={
                        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                        "contents": [{"parts": [{"text": query}]}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error(f"Gemini query error: {e}")
            return ""

    async def _analyze_response(self, query: str, answer: str, brand_names: list[str]) -> dict | None:
        """Use Claude Haiku to extract structured brand mentions from a raw AI answer."""
        if not answer or not settings.ANTHROPIC_API_KEY:
            return None
        prompt = ANALYSIS_PROMPT.format(
            query=query,
            brand_names=", ".join(brand_names),
            answer=answer,
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 1000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                text = resp.json()["content"][0]["text"]
                # Strip possible markdown code fences
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text.rsplit("```", 1)[0]
                return json.loads(text.strip())
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return None

    async def run_full_analysis(
        self, brand_names: list[str]
    ) -> list[dict[str, Any]]:
        """Run all GEO queries against Claude + Gemini and return structured results.

        Returns a list of dicts, one per (keyword, platform, brand_mention).
        """
        results: list[dict[str, Any]] = []

        for i, q in enumerate(GEO_QUERIES):
            keyword = q["keyword"]
            query = q["query"]

            # Query both engines
            claude_answer = await self._query_claude(query)
            await asyncio.sleep(0.5)

            gemini_answer = await self._query_gemini(query)
            await asyncio.sleep(0.5)

            # Analyse both responses
            for platform, answer in [("claude", claude_answer), ("gemini", gemini_answer)]:
                if not answer:
                    continue

                analysis = await self._analyze_response(query, answer, brand_names)
                await asyncio.sleep(0.3)

                if not analysis:
                    continue

                primary_rec = analysis.get("primary_recommendation", "")
                brands_mentioned = analysis.get("brands_mentioned", [])

                for mention in brands_mentioned:
                    results.append({
                        "keyword": keyword,
                        "query": query,
                        "platform": platform,
                        "raw_answer": answer,
                        "analysis": json.dumps(analysis, ensure_ascii=False),
                        "brand_name": mention.get("name", ""),
                        "position_in_answer": mention.get("position"),
                        "recommended": mention.get("recommended", False),
                        "sentiment": mention.get("sentiment", "neutre"),
                        "context_snippet": mention.get("context", ""),
                        "primary_recommendation": primary_rec,
                        "key_criteria": analysis.get("key_criteria", []),
                    })

            logger.info(f"GEO [{i+1}/{len(GEO_QUERIES)}] done: {keyword}")

        return results


geo_analyzer = GeoAnalyzer()
