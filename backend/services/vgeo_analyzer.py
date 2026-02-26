"""
VGEO (Video Generative Engine Optimization) Analyzer.
Analyses YouTube video strategy for AI engine visibility (ChatGPT, Claude, Gemini, Mistral).

Framework HELP / HUB / HERO:
- HELP: tutorials, FAQ, practical guides (highest LLM citation impact)
- HUB: recurring content, series (builds topical authority)
- HERO: events, campaigns (punctual visibility)

VGEO Score /100 (4 axes):
- Alignment (35%): do videos match LLM user queries?
- Freshness (30%): recent content in the niche?
- Presence (20%): is the brand actually cited by LLMs for video?
- Competitivity (15%): position vs competitors?
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from core.config import settings
from services.youtube_api import youtube_api
from services.geo_analyzer import GeoAnalyzer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Video-oriented LLM queries by sector
# ---------------------------------------------------------------------------

VGEO_QUERIES: dict[str, list[str]] = {
    "supermarche": [
        "Quelle chaine YouTube recommandes-tu pour les bons plans courses en France ?",
        "Quelles sont les meilleures videos YouTube sur les promotions supermarche ?",
        "Recommande-moi des contenus video pour bien faire ses courses en France",
        "Quelle enseigne de supermarche a la meilleure chaine YouTube ?",
        "Quelles videos YouTube regarder pour comparer les prix en supermarche ?",
        "Quel YouTubeur parle le mieux des produits de grande distribution ?",
    ],
    "mode": [
        "Quelle chaine YouTube recommandes-tu pour la mode abordable en France ?",
        "Quelles sont les meilleures videos YouTube sur les tendances mode ?",
        "Recommande-moi des contenus video pour s'habiller pas cher en France",
        "Quelle marque de mode a la meilleure chaine YouTube ?",
        "Quels YouTubeurs mode recommandes-tu en France ?",
        "Quelles videos YouTube regarder pour les hauls mode ?",
    ],
    "beaute": [
        "Quelle chaine YouTube recommandes-tu pour la beaute en France ?",
        "Quelles sont les meilleures videos YouTube sur les soins visage ?",
        "Recommande-moi des contenus video beaute et maquillage en France",
        "Quelle enseigne de beaute a la meilleure chaine YouTube ?",
        "Quels YouTubeurs beaute recommandes-tu en France ?",
        "Quelles videos YouTube regarder pour les tutoriels maquillage ?",
    ],
    "bricolage": [
        "Quelle chaine YouTube recommandes-tu pour le bricolage en France ?",
        "Quelles sont les meilleures videos YouTube de tutoriels bricolage ?",
        "Recommande-moi des contenus video pour renover sa maison",
        "Quelle enseigne de bricolage a la meilleure chaine YouTube ?",
        "Quels YouTubeurs bricolage recommandes-tu en France ?",
        "Quelles videos YouTube regarder pour apprendre le bricolage ?",
    ],
    "sport": [
        "Quelle chaine YouTube recommandes-tu pour le sport en France ?",
        "Quelles sont les meilleures videos YouTube sur les equipements sportifs ?",
        "Recommande-moi des contenus video pour choisir son materiel de sport",
        "Quelle enseigne de sport a la meilleure chaine YouTube ?",
        "Quels YouTubeurs sport recommandes-tu en France ?",
        "Quelles videos YouTube regarder pour les tests d'equipements sportifs ?",
    ],
}


def _generate_vgeo_queries(sector_label: str) -> list[str]:
    """Generate generic video queries for unknown sectors."""
    return [
        f"Quelle chaine YouTube recommandes-tu pour le {sector_label} en France ?",
        f"Quelles sont les meilleures videos YouTube sur le {sector_label} ?",
        f"Recommande-moi des contenus video pour le {sector_label}",
        f"Quelle enseigne de {sector_label} a la meilleure chaine YouTube ?",
        f"Quels YouTubeurs {sector_label} recommandes-tu en France ?",
        f"Quelles videos YouTube regarder pour le {sector_label} ?",
    ]


CLASSIFICATION_PROMPT = """Tu es un expert en strategie YouTube. Classifie ces videos en 3 categories :
- HELP : tutoriels, FAQ, guides pratiques, how-to, conseils — contenu evergreen que les gens cherchent
- HUB : series recurrentes, formats reguliers, rendez-vous — construit l'audience fidele
- HERO : evenements, campagnes, lancements, buzz — visibilite ponctuelle massive

Videos a classifier :
{videos_json}

Retourne UNIQUEMENT un JSON valide (pas de markdown) :
[{{"video_id": "...", "classification": "HELP|HUB|HERO", "keywords": ["mot1", "mot2"]}}]"""


DIAGNOSTIC_PROMPT = """Tu es un expert VGEO (Video Generative Engine Optimization) pour le retail en France.
Analyse ces donnees de strategie YouTube et visibilite IA :

Marque : {brand_name} (secteur : {sector})
Score VGEO : {score_total}/100

Scores detailles :
- Alignement (videos vs requetes LLM) : {score_alignment}/100
- Fraicheur (contenu recent) : {score_freshness}/100
- Presence (citations LLM) : {score_presence}/100
- Competitivite (vs concurrents) : {score_competitivity}/100

Repartition videos marque :
- HELP : {help_count} videos
- HUB : {hub_count} videos
- HERO : {hero_count} videos

Concurrents :
{competitors_summary}

Citations LLM :
{citations_summary}

Retourne UNIQUEMENT un JSON valide (pas de markdown) :
{{
  "diagnostic": "<3-5 phrases de synthese strategique VGEO>",
  "forces": ["<force 1>", "<force 2>"],
  "faiblesses": ["<faiblesse 1>", "<faiblesse 2>"],
  "strategy": [
    {{"action": "<action>", "impact": "high|medium|low", "effort": "high|medium|low", "detail": "<explication>"}}
  ],
  "actions": [
    {{"title": "<action rapide>", "description": "<detail>", "priority": "quick_win|moyen_terme|long_terme", "impact_estimate": "<estimation>"}}
  ]
}}"""


class VgeoAnalyzer:
    """Analyses YouTube video strategy for AI engine visibility."""

    def __init__(self):
        self.geo_analyzer = GeoAnalyzer()

    async def analyze(self, advertiser_id: int, db) -> dict:
        """Run a full VGEO analysis for an advertiser."""
        from database import Advertiser, Competitor, AdvertiserCompetitor

        # 1. Get brand + competitors with youtube_channel_id
        advertiser = db.query(Advertiser).filter(Advertiser.id == advertiser_id).first()
        if not advertiser:
            raise ValueError(f"Advertiser {advertiser_id} not found")

        sector = advertiser.sector or "supermarche"
        brand_name = advertiser.company_name

        # Get competitors linked to this advertiser
        comp_links = db.query(AdvertiserCompetitor).filter(
            AdvertiserCompetitor.advertiser_id == advertiser_id
        ).all()
        comp_ids = [link.competitor_id for link in comp_links]
        competitors = db.query(Competitor).filter(
            Competitor.id.in_(comp_ids),
            Competitor.is_active == True,
        ).all() if comp_ids else []

        # Brand competitor (is_brand=True)
        brand_comp = next((c for c in competitors if c.is_brand), None)
        brand_channel_id = advertiser.youtube_channel_id or (brand_comp.youtube_channel_id if brand_comp else None)

        # All channels to analyze (brand + competitors with YouTube)
        channels: list[dict] = []
        if brand_channel_id:
            channels.append({
                "name": brand_name,
                "channel_id": brand_channel_id,
                "is_brand": True,
            })

        for comp in competitors:
            if comp.youtube_channel_id and not comp.is_brand:
                channels.append({
                    "name": comp.name,
                    "channel_id": comp.youtube_channel_id,
                    "is_brand": False,
                })

        # 2. Fetch recent videos for each channel (parallel)
        all_videos: dict[str, list[dict]] = {}
        video_tasks = []
        for ch in channels:
            video_tasks.append(self._fetch_channel_videos(ch["channel_id"], ch["name"]))

        video_results = await asyncio.gather(*video_tasks, return_exceptions=True)
        for ch, result in zip(channels, video_results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch videos for {ch['name']}: {result}")
                all_videos[ch["name"]] = []
            else:
                all_videos[ch["name"]] = result

        # 3. Classify videos HELP/HUB/HERO
        classifications: dict[str, list[dict]] = {}
        for name, videos in all_videos.items():
            if videos:
                classified = await self._classify_videos(videos)
                classifications[name] = classified
            else:
                classifications[name] = []

        # 4. Query LLMs with video-oriented questions
        queries = VGEO_QUERIES.get(sector, _generate_vgeo_queries(sector))
        brand_names = [brand_name] + [c.name for c in competitors if not c.is_brand]

        citations: dict[str, list[dict]] = {"claude": [], "gemini": [], "chatgpt": [], "mistral": []}
        for query in queries:
            query_results = await self._query_llms_for_video(query, brand_names)
            for platform, mentions in query_results.items():
                citations[platform].extend(mentions)

        # 5. Calculate VGEO score
        brand_videos = classifications.get(brand_name, [])
        scores = self._calculate_score(
            brand_videos=brand_videos,
            all_videos=all_videos.get(brand_name, []),
            citations=citations,
            brand_name=brand_name,
            competitors=[c["name"] for c in channels if not c["is_brand"]],
            all_classifications=classifications,
        )

        # 6. Build competitor comparison
        competitor_scores = []
        for ch in channels:
            if ch["is_brand"]:
                continue
            comp_videos = classifications.get(ch["name"], [])
            comp_score = self._calculate_score(
                brand_videos=comp_videos,
                all_videos=all_videos.get(ch["name"], []),
                citations=citations,
                brand_name=ch["name"],
                competitors=[],
                all_classifications=classifications,
            )
            competitor_scores.append({
                "name": ch["name"],
                "channel_id": ch["channel_id"],
                "score": comp_score,
                "video_count": len(all_videos.get(ch["name"], [])),
                "citations": sum(
                    1 for plat in citations.values()
                    for m in plat if m.get("brand") == ch["name"]
                ),
            })

        # 7. Generate diagnostic via Gemini
        diagnostic = await self._generate_diagnostic(
            brand_name=brand_name,
            sector=sector,
            scores=scores,
            brand_classifications=brand_videos,
            competitor_scores=competitor_scores,
            citations=citations,
        )

        # Build brand channel info
        brand_channel_info = None
        if brand_channel_id:
            brand_vids = all_videos.get(brand_name, [])
            brand_classified = classifications.get(brand_name, [])
            help_count = sum(1 for v in brand_classified if v.get("classification") == "HELP")
            hub_count = sum(1 for v in brand_classified if v.get("classification") == "HUB")
            hero_count = sum(1 for v in brand_classified if v.get("classification") == "HERO")
            brand_channel_info = {
                "channel_id": brand_channel_id,
                "video_count": len(brand_vids),
                "help_count": help_count,
                "hub_count": hub_count,
                "hero_count": hero_count,
            }

        # Build videos list with classifications
        videos_list = []
        for name, vids in all_videos.items():
            classified = {v.get("video_id"): v for v in classifications.get(name, [])}
            for v in vids:
                vid_id = v.get("id") or v.get("video_id", "")
                cl = classified.get(vid_id, {})
                videos_list.append({
                    "channel_name": name,
                    "is_brand": name == brand_name,
                    "title": v.get("title", ""),
                    "video_id": vid_id,
                    "views": v.get("views", 0),
                    "likes": v.get("likes", 0),
                    "published_at": v.get("published_at") or v.get("publishedAt", ""),
                    "classification": cl.get("classification", "UNKNOWN"),
                    "keywords": cl.get("keywords", []),
                })

        return {
            "score": scores,
            "brand_channel": brand_channel_info,
            "competitors": competitor_scores,
            "videos": videos_list,
            "citations": citations,
            "diagnostic": diagnostic.get("diagnostic", ""),
            "forces": diagnostic.get("forces", []),
            "faiblesses": diagnostic.get("faiblesses", []),
            "strategy": diagnostic.get("strategy", []),
            "actions": diagnostic.get("actions", []),
        }

    async def _fetch_channel_videos(self, channel_id: str, name: str) -> list[dict]:
        """Fetch recent videos from a YouTube channel."""
        try:
            result = await youtube_api.fetch_recent_videos(channel_id, max_results=20)
            videos = result.get("videos", []) if result.get("success") else []
            logger.info(f"VGEO: fetched {len(videos)} videos for {name}")
            return videos
        except Exception as e:
            logger.error(f"VGEO: failed to fetch videos for {name}: {e}")
            return []

    async def _classify_videos(self, videos: list[dict]) -> list[dict]:
        """Classify videos into HELP/HUB/HERO using Gemini."""
        if not settings.GEMINI_API_KEY or not videos:
            return [{"video_id": v.get("id", ""), "classification": "UNKNOWN", "keywords": []} for v in videos]

        videos_for_prompt = [
            {
                "video_id": v.get("id") or v.get("video_id", ""),
                "title": v.get("title", ""),
                "description": (v.get("description") or "")[:200],
            }
            for v in videos[:20]
        ]

        prompt = CLASSIFICATION_PROMPT.format(videos_json=json.dumps(videos_for_prompt, ensure_ascii=False))

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 2000,
                        "temperature": 0.1,
                        "responseMimeType": "application/json",
                    },
                })
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text.rsplit("```", 1)[0]
                result = json.loads(text.strip())
                if isinstance(result, list):
                    return result
                return []
        except Exception as e:
            logger.error(f"VGEO classification error: {e}")
            return [{"video_id": v.get("id", ""), "classification": "UNKNOWN", "keywords": []} for v in videos]

    async def _query_llms_for_video(self, query: str, brand_names: list[str]) -> dict[str, list[dict]]:
        """Query all LLMs with a video-oriented question and analyze mentions."""
        # Query all platforms in parallel
        tasks = [
            self.geo_analyzer._query_claude(query),
            self.geo_analyzer._query_gemini(query),
            self.geo_analyzer._query_chatgpt(query),
            self.geo_analyzer._query_mistral(query),
        ]
        answers = await asyncio.gather(*tasks, return_exceptions=True)
        platform_names = ["claude", "gemini", "chatgpt", "mistral"]

        results: dict[str, list[dict]] = {}
        for platform, answer in zip(platform_names, answers):
            if isinstance(answer, Exception) or not answer:
                results[platform] = []
                continue

            # Analyze which brands are mentioned
            analysis = await self.geo_analyzer._analyze_response(query, answer, brand_names, platform=platform)
            mentions = []
            if analysis:
                for brand_mention in analysis.get("brands_mentioned", []):
                    mentions.append({
                        "brand": brand_mention.get("name", ""),
                        "query": query,
                        "recommended": brand_mention.get("recommended", False),
                        "sentiment": brand_mention.get("sentiment", "neutre"),
                        "context": brand_mention.get("context", ""),
                    })
            results[platform] = mentions

        return results

    def _calculate_score(
        self,
        brand_videos: list[dict],
        all_videos: list[dict],
        citations: dict[str, list[dict]],
        brand_name: str,
        competitors: list[str],
        all_classifications: dict[str, list[dict]],
    ) -> dict:
        """Calculate VGEO score /100 with 4 axes."""

        # Alignment (35%): % of HELP videos (most cited by LLMs)
        help_count = sum(1 for v in brand_videos if v.get("classification") == "HELP")
        total_classified = len(brand_videos) or 1
        alignment_raw = (help_count / total_classified) * 100
        # Bonus for balanced mix (HELP > HUB > HERO)
        hub_count = sum(1 for v in brand_videos if v.get("classification") == "HUB")
        hero_count = sum(1 for v in brand_videos if v.get("classification") == "HERO")
        balance_bonus = min(15, (hub_count + hero_count) * 3) if help_count > 0 else 0
        alignment = min(100, alignment_raw + balance_bonus)

        # Freshness (30%): % of videos published < 3 months
        three_months_ago = datetime.utcnow() - timedelta(days=90)
        recent_count = 0
        for v in all_videos:
            pub = v.get("published_at") or v.get("publishedAt", "")
            if pub:
                try:
                    pub_date = datetime.fromisoformat(pub.replace("Z", "+00:00").replace("+00:00", ""))
                    if pub_date > three_months_ago:
                        recent_count += 1
                except (ValueError, TypeError):
                    pass
        total_videos = len(all_videos) or 1
        freshness = min(100, (recent_count / total_videos) * 100 + (min(recent_count, 10) * 3))

        # Presence (20%): % of LLM queries where brand is cited
        total_queries = 0
        brand_cited_queries = set()
        for platform, mentions in citations.items():
            for m in mentions:
                query_key = m.get("query", "")
                total_queries += 1
                if m.get("brand", "").lower() == brand_name.lower():
                    brand_cited_queries.add(f"{platform}:{query_key}")
        unique_total = max(total_queries, 1)
        presence = min(100, (len(brand_cited_queries) / max(unique_total // 4, 1)) * 100)

        # Competitivity (15%): relative position vs competitors
        brand_total_citations = sum(
            1 for plat in citations.values()
            for m in plat if m.get("brand", "").lower() == brand_name.lower()
        )
        comp_citations = {}
        for comp_name in competitors:
            comp_citations[comp_name] = sum(
                1 for plat in citations.values()
                for m in plat if m.get("brand", "").lower() == comp_name.lower()
            )
        all_citation_counts = [brand_total_citations] + list(comp_citations.values())
        max_citations = max(all_citation_counts) if all_citation_counts else 1
        competitivity = (brand_total_citations / max(max_citations, 1)) * 100 if max_citations > 0 else 50

        # Weighted total
        total = round(
            alignment * 0.35 +
            freshness * 0.30 +
            presence * 0.20 +
            competitivity * 0.15
        )

        return {
            "total": min(100, max(0, total)),
            "alignment": round(min(100, max(0, alignment))),
            "freshness": round(min(100, max(0, freshness))),
            "presence": round(min(100, max(0, presence))),
            "competitivity": round(min(100, max(0, competitivity))),
        }

    async def _generate_diagnostic(
        self,
        brand_name: str,
        sector: str,
        scores: dict,
        brand_classifications: list[dict],
        competitor_scores: list[dict],
        citations: dict[str, list[dict]],
    ) -> dict:
        """Generate AI diagnostic via Gemini."""
        if not settings.GEMINI_API_KEY:
            return {"diagnostic": "Cle API Gemini manquante", "forces": [], "faiblesses": [], "strategy": [], "actions": []}

        help_count = sum(1 for v in brand_classifications if v.get("classification") == "HELP")
        hub_count = sum(1 for v in brand_classifications if v.get("classification") == "HUB")
        hero_count = sum(1 for v in brand_classifications if v.get("classification") == "HERO")

        comp_summary = "\n".join(
            f"- {c['name']}: score {c['score']['total']}/100, {c['video_count']} videos, {c['citations']} citations"
            for c in competitor_scores
        ) or "Aucun concurrent avec chaine YouTube"

        cit_summary_parts = []
        for platform, mentions in citations.items():
            brand_mentions = [m for m in mentions if m.get("brand", "").lower() == brand_name.lower()]
            cit_summary_parts.append(f"- {platform}: {len(brand_mentions)} mentions de {brand_name}")
        cit_summary = "\n".join(cit_summary_parts)

        prompt = DIAGNOSTIC_PROMPT.format(
            brand_name=brand_name,
            sector=sector,
            score_total=scores["total"],
            score_alignment=scores["alignment"],
            score_freshness=scores["freshness"],
            score_presence=scores["presence"],
            score_competitivity=scores["competitivity"],
            help_count=help_count,
            hub_count=hub_count,
            hero_count=hero_count,
            competitors_summary=comp_summary,
            citations_summary=cit_summary,
        )

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}"
            async with httpx.AsyncClient(timeout=45) as client:
                resp = await client.post(url, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 2000,
                        "temperature": 0.2,
                        "responseMimeType": "application/json",
                    },
                })
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text.rsplit("```", 1)[0]
                return json.loads(text.strip())
        except Exception as e:
            logger.error(f"VGEO diagnostic generation error: {e}")
            return {"diagnostic": "Erreur lors de la generation du diagnostic", "forces": [], "faiblesses": [], "strategy": [], "actions": []}


vgeo_analyzer = VgeoAnalyzer()
