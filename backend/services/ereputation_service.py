"""
E-Reputation Service.
Scrapes comments from YouTube/TikTok/Instagram, analyzes sentiment via Gemini,
computes KPIs, and generates AI synthesis.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from core.config import settings
from database import EReputationAudit, EReputationComment, Competitor

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent"

SENTIMENT_PROMPT = """Tu es un expert en analyse de sentiment pour des commentaires sur les réseaux sociaux.
Analyse chaque commentaire ci-dessous pour la marque "{competitor_name}".

Pour chaque commentaire, détermine :
- sentiment : "positive", "negative", ou "neutral"
- sentiment_score : un nombre entre -1.0 (très négatif) et +1.0 (très positif)
- categories : liste parmi ["sav", "prix", "qualite", "livraison", "experience", "produit", "service", "communication", "innovation", "rse", "emploi"]
- is_alert : true si le commentaire nécessite une attention urgente (plainte grave, menace légale, viral négatif, risque financier)
- alert_reason : raison de l'alerte si is_alert=true, sinon ""

Commentaires à analyser :
{comments_json}

Retourne UNIQUEMENT un JSON valide (pas de markdown, pas de ```) :
[
  {{
    "index": 0,
    "sentiment": "positive",
    "sentiment_score": 0.8,
    "categories": ["qualite", "prix"],
    "is_alert": false,
    "alert_reason": ""
  }}
]"""

SYNTHESIS_PROMPT = """Tu es un expert en e-réputation et stratégie digitale pour le retail en France.
Analyse les KPIs et commentaires ci-dessous pour "{competitor_name}" et génère des insights actionnables.

KPIs :
{kpis_json}

Top commentaires positifs :
{positive_comments}

Top commentaires négatifs :
{negative_comments}

Alertes :
{alert_comments}

Retourne UNIQUEMENT un JSON valide (pas de markdown, pas de ```) :
{{
  "insights": [
    "<insight 1 : observation clé sur la réputation>",
    "<insight 2 : tendance identifiée>",
    "<insight 3 : comparaison avec les standards du secteur>"
  ],
  "recommendations": [
    "<recommandation 1 : action concrète et prioritaire>",
    "<recommandation 2 : amélioration à moyen terme>",
    "<recommandation 3 : opportunité à saisir>"
  ],
  "risk_summary": "<1-2 phrases sur les risques principaux identifiés>",
  "strength_summary": "<1-2 phrases sur les points forts de la marque>"
}}"""


class EReputationService:
    """E-Reputation analysis service."""

    @property
    def gemini_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "") or settings.GEMINI_API_KEY

    async def scrape_owned_comments(self, competitor: Competitor, db: Session) -> list[dict]:
        """Scrape comments from competitor's own social accounts."""
        from services.scrapecreators import scrapecreators

        all_comments = []

        # YouTube: fetch recent videos then comments
        if competitor.youtube_channel_id:
            try:
                videos_data = await scrapecreators.fetch_youtube_videos(
                    channel_id=competitor.youtube_channel_id, limit=5
                )
                if videos_data.get("success"):
                    for video in videos_data.get("videos", [])[:5]:
                        vid_id = video.get("video_id", "")
                        if not vid_id:
                            continue
                        await asyncio.sleep(0.3)
                        comments_data = await scrapecreators.fetch_youtube_comments(vid_id, limit=50)
                        if comments_data.get("success"):
                            for c in comments_data.get("comments", []):
                                all_comments.append({
                                    "platform": "youtube",
                                    "comment_id": f"yt_{c.get('comment_id', '')}",
                                    "source_type": "owned",
                                    "source_url": f"https://youtube.com/watch?v={vid_id}",
                                    "source_title": video.get("title", ""),
                                    "author": c.get("author", ""),
                                    "text": c.get("text", ""),
                                    "likes": c.get("likes", 0),
                                    "replies": c.get("replies", 0),
                                    "published_at": c.get("published_at", ""),
                                })
            except Exception as e:
                logger.error(f"YouTube comments error for {competitor.name}: {e}")

        # TikTok: fetch recent videos then comments
        if competitor.tiktok_username:
            try:
                videos_data = await scrapecreators.fetch_tiktok_videos(
                    competitor.tiktok_username, limit=5
                )
                if videos_data.get("success"):
                    for video in videos_data.get("videos", [])[:5]:
                        vid_id = video.get("id", "")
                        if not vid_id:
                            continue
                        await asyncio.sleep(0.3)
                        comments_data = await scrapecreators.fetch_tiktok_comments(vid_id, limit=50)
                        if comments_data.get("success"):
                            for c in comments_data.get("comments", []):
                                all_comments.append({
                                    "platform": "tiktok",
                                    "comment_id": f"tt_{c.get('comment_id', '')}",
                                    "source_type": "owned",
                                    "source_url": f"https://tiktok.com/@{competitor.tiktok_username}/video/{vid_id}",
                                    "source_title": video.get("description", "")[:200],
                                    "author": c.get("author", ""),
                                    "text": c.get("text", ""),
                                    "likes": c.get("likes", 0),
                                    "replies": c.get("replies", 0),
                                    "published_at": c.get("published_at", ""),
                                })
            except Exception as e:
                logger.error(f"TikTok comments error for {competitor.name}: {e}")

        # Instagram: fetch profile (recent posts) then comments
        if competitor.instagram_username:
            try:
                profile_data = await scrapecreators.fetch_instagram_profile(
                    competitor.instagram_username
                )
                if profile_data.get("success"):
                    # Instagram profile returns recent posts in the raw data
                    # We need to get shortcodes from posts
                    await asyncio.sleep(0.3)
                    # Try fetching via raw profile data for post shortcodes
                    raw = await scrapecreators._get("/v1/instagram/profile", {
                        "handle": competitor.instagram_username.lstrip("@")
                    })
                    if raw.get("success"):
                        user_data = raw.get("data", {}).get("user", {})
                        edges = user_data.get("edge_owner_to_timeline_media", {}).get("edges", [])
                        for edge in edges[:5]:
                            node = edge.get("node", {})
                            shortcode = node.get("shortcode", "")
                            if not shortcode:
                                continue
                            await asyncio.sleep(0.3)
                            comments_data = await scrapecreators.fetch_instagram_comments(shortcode, limit=50)
                            if comments_data.get("success"):
                                caption = ""
                                caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
                                if caption_edges:
                                    caption = caption_edges[0].get("node", {}).get("text", "")[:200]
                                for c in comments_data.get("comments", []):
                                    all_comments.append({
                                        "platform": "instagram",
                                        "comment_id": f"ig_{c.get('comment_id', '')}",
                                        "source_type": "owned",
                                        "source_url": f"https://instagram.com/p/{shortcode}",
                                        "source_title": caption,
                                        "author": c.get("author", ""),
                                        "text": c.get("text", ""),
                                        "likes": c.get("likes", 0),
                                        "replies": c.get("replies", 0),
                                        "published_at": c.get("published_at", ""),
                                    })
            except Exception as e:
                logger.error(f"Instagram comments error for {competitor.name}: {e}")

        logger.info(f"Scraped {len(all_comments)} owned comments for {competitor.name}")
        return all_comments

    async def scrape_earned_comments(self, competitor: Competitor, db: Session) -> list[dict]:
        """Scrape earned mentions (brand mentions across platforms)."""
        from services.scrapecreators import scrapecreators

        all_comments = []
        search_query = f"{competitor.name} avis"

        # Search YouTube for brand mentions
        try:
            data = await scrapecreators.search_google(f"{search_query} site:youtube.com", limit=5)
            if data.get("success"):
                for result in data.get("results", [])[:5]:
                    url = result.get("url", result.get("link", ""))
                    # Extract video ID from YouTube URL
                    vid_id = ""
                    if "youtube.com/watch?v=" in url:
                        vid_id = url.split("v=")[1].split("&")[0]
                    elif "youtu.be/" in url:
                        vid_id = url.split("youtu.be/")[1].split("?")[0]
                    if vid_id:
                        await asyncio.sleep(0.3)
                        comments_data = await scrapecreators.fetch_youtube_comments(vid_id, limit=30)
                        if comments_data.get("success"):
                            for c in comments_data.get("comments", []):
                                all_comments.append({
                                    "platform": "youtube",
                                    "comment_id": f"yt_{c.get('comment_id', '')}",
                                    "source_type": "earned",
                                    "source_url": url,
                                    "source_title": result.get("title", ""),
                                    "author": c.get("author", ""),
                                    "text": c.get("text", ""),
                                    "likes": c.get("likes", 0),
                                    "replies": c.get("replies", 0),
                                    "published_at": c.get("published_at", ""),
                                })
        except Exception as e:
            logger.error(f"Earned YouTube scrape error for {competitor.name}: {e}")

        logger.info(f"Scraped {len(all_comments)} earned comments for {competitor.name}")
        return all_comments

    async def analyze_sentiment_batch(self, comments: list[dict], competitor_name: str) -> list[dict]:
        """Analyze sentiment for a batch of comments using Gemini."""
        if not self.gemini_key:
            logger.error("Cannot analyze sentiment: GEMINI_API_KEY not set")
            return comments

        batch_size = 20
        analyzed = []

        for i in range(0, len(comments), batch_size):
            batch = comments[i:i + batch_size]
            comments_for_prompt = [
                {"index": j, "text": c.get("text", "")[:500], "platform": c.get("platform", "")}
                for j, c in enumerate(batch)
            ]

            prompt = SENTIMENT_PROMPT.format(
                competitor_name=competitor_name,
                comments_json=json.dumps(comments_for_prompt, ensure_ascii=False),
            )

            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{GEMINI_API_URL}?key={self.gemini_key}",
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
                        },
                        timeout=60.0,
                    )
                    resp.raise_for_status()
                    result = resp.json()

                text_out = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                # Clean markdown fences if present
                text_out = text_out.strip()
                if text_out.startswith("```"):
                    text_out = text_out.split("\n", 1)[1] if "\n" in text_out else text_out[3:]
                if text_out.endswith("```"):
                    text_out = text_out[:-3]
                text_out = text_out.strip()

                sentiments = json.loads(text_out)

                for s in sentiments:
                    idx = s.get("index", 0)
                    if idx < len(batch):
                        batch[idx]["sentiment"] = s.get("sentiment", "neutral")
                        batch[idx]["sentiment_score"] = s.get("sentiment_score", 0.0)
                        batch[idx]["categories"] = s.get("categories", [])
                        batch[idx]["is_alert"] = s.get("is_alert", False)
                        batch[idx]["alert_reason"] = s.get("alert_reason", "")

            except Exception as e:
                logger.error(f"Gemini sentiment batch error: {e}")
                # Default to neutral for failed batch
                for c in batch:
                    c.setdefault("sentiment", "neutral")
                    c.setdefault("sentiment_score", 0.0)
                    c.setdefault("categories", [])
                    c.setdefault("is_alert", False)
                    c.setdefault("alert_reason", "")

            analyzed.extend(batch)

            if i + batch_size < len(comments):
                await asyncio.sleep(0.5)

        return analyzed

    def compute_kpis(self, comments: list[dict]) -> dict:
        """Compute e-reputation KPIs from analyzed comments."""
        if not comments:
            return {
                "reputation_score": 0.0,
                "nps": 0.0,
                "sav_rate": 0.0,
                "financial_risk_rate": 0.0,
                "engagement_rate": 0.0,
                "earned_ratio": 0.0,
                "sentiment_breakdown": {"positive": 0, "negative": 0, "neutral": 0},
                "platform_breakdown": {},
                "total_comments": 0,
            }

        total = len(comments)
        positive = sum(1 for c in comments if c.get("sentiment") == "positive")
        negative = sum(1 for c in comments if c.get("sentiment") == "negative")
        neutral = total - positive - negative

        # SAV rate: comments with "sav" or "livraison" or "service" category
        sav_categories = {"sav", "livraison", "service"}
        sav_count = sum(
            1 for c in comments
            if any(cat in sav_categories for cat in (c.get("categories") or []))
        )
        sav_rate = (sav_count / total) * 100 if total > 0 else 0.0

        # Financial risk rate: comments with "prix" category AND negative sentiment
        financial_count = sum(
            1 for c in comments
            if "prix" in (c.get("categories") or []) and c.get("sentiment") == "negative"
        )
        financial_risk_rate = (financial_count / total) * 100 if total > 0 else 0.0

        # Earned ratio
        earned_count = sum(1 for c in comments if c.get("source_type") == "earned")
        earned_ratio = (earned_count / total) * 100 if total > 0 else 0.0

        # Engagement rate: avg likes + replies per comment
        total_interactions = sum(c.get("likes", 0) + c.get("replies", 0) for c in comments)
        engagement_rate = total_interactions / total if total > 0 else 0.0

        # Positive ratio for reputation score
        positive_ratio = positive / total if total > 0 else 0.0

        # Reputation score = 50% positive ratio + 25% (1-sav_rate%) + 25% (1-financial_risk_rate%)
        reputation_score = (
            positive_ratio * 50
            + (1 - sav_rate / 100) * 25
            + (1 - financial_risk_rate / 100) * 25
        )

        # NPS = (positive% - negative%) * 100, capped at -100/+100
        nps = ((positive / total) - (negative / total)) * 100 if total > 0 else 0.0
        nps = max(-100, min(100, nps))

        # Platform breakdown
        platform_stats = {}
        for c in comments:
            p = c.get("platform", "unknown")
            if p not in platform_stats:
                platform_stats[p] = {"total": 0, "positive": 0, "negative": 0, "neutral": 0}
            platform_stats[p]["total"] += 1
            sentiment = c.get("sentiment", "neutral")
            if sentiment in platform_stats[p]:
                platform_stats[p][sentiment] += 1

        return {
            "reputation_score": round(reputation_score, 1),
            "nps": round(nps, 1),
            "sav_rate": round(sav_rate, 1),
            "financial_risk_rate": round(financial_risk_rate, 1),
            "engagement_rate": round(engagement_rate, 2),
            "earned_ratio": round(earned_ratio, 1),
            "sentiment_breakdown": {"positive": positive, "negative": negative, "neutral": neutral},
            "platform_breakdown": platform_stats,
            "total_comments": total,
        }

    async def generate_synthesis(self, kpis: dict, comments: list[dict], competitor_name: str) -> dict:
        """Generate AI synthesis from KPIs and comments using Gemini."""
        if not self.gemini_key:
            return {"insights": [], "recommendations": [], "risk_summary": "", "strength_summary": ""}

        # Prepare top comments for prompt
        positive_comments = sorted(
            [c for c in comments if c.get("sentiment") == "positive"],
            key=lambda x: x.get("likes", 0), reverse=True
        )[:10]
        negative_comments = sorted(
            [c for c in comments if c.get("sentiment") == "negative"],
            key=lambda x: x.get("likes", 0), reverse=True
        )[:10]
        alert_comments = [c for c in comments if c.get("is_alert")][:10]

        def _format_comments(clist):
            return "\n".join(
                f"- [{c.get('platform')}] {c.get('text', '')[:200]} (likes: {c.get('likes', 0)})"
                for c in clist
            ) or "Aucun"

        prompt = SYNTHESIS_PROMPT.format(
            competitor_name=competitor_name,
            kpis_json=json.dumps(kpis, ensure_ascii=False),
            positive_comments=_format_comments(positive_comments),
            negative_comments=_format_comments(negative_comments),
            alert_comments=_format_comments(alert_comments),
        )

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{GEMINI_API_URL}?key={self.gemini_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
                    },
                    timeout=60.0,
                )
                resp.raise_for_status()
                result = resp.json()

            text_out = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            text_out = text_out.strip()
            if text_out.startswith("```"):
                text_out = text_out.split("\n", 1)[1] if "\n" in text_out else text_out[3:]
            if text_out.endswith("```"):
                text_out = text_out[:-3]
            text_out = text_out.strip()

            return json.loads(text_out)
        except Exception as e:
            logger.error(f"Gemini synthesis error: {e}")
            return {"insights": [], "recommendations": [], "risk_summary": "", "strength_summary": ""}

    async def run_audit(self, competitor: Competitor, db: Session) -> Optional[EReputationAudit]:
        """Run a full e-reputation audit for a competitor."""
        logger.info(f"Starting e-reputation audit for {competitor.name}")

        # 1. Scrape owned comments
        owned_comments = await self.scrape_owned_comments(competitor, db)

        # 2. Scrape earned comments
        earned_comments = await self.scrape_earned_comments(competitor, db)

        # 3. Merge and deduplicate by comment_id
        all_comments = owned_comments + earned_comments
        seen_ids = set()
        deduped = []
        for c in all_comments:
            cid = c.get("comment_id", "")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                deduped.append(c)

        if not deduped:
            logger.warning(f"No comments found for {competitor.name}")
            # Still create an empty audit
            audit = EReputationAudit(
                competitor_id=competitor.id,
                reputation_score=0,
                nps=0,
                sav_rate=0,
                financial_risk_rate=0,
                engagement_rate=0,
                earned_ratio=0,
                sentiment_breakdown=json.dumps({"positive": 0, "negative": 0, "neutral": 0}),
                platform_breakdown=json.dumps({}),
                ai_synthesis=json.dumps({"insights": [], "recommendations": []}),
                total_comments=0,
            )
            db.add(audit)
            db.commit()
            db.refresh(audit)
            return audit

        # 4. Analyze sentiment
        analyzed = await self.analyze_sentiment_batch(deduped, competitor.name)

        # 5. Compute KPIs
        kpis = self.compute_kpis(analyzed)

        # 6. Generate synthesis
        synthesis = await self.generate_synthesis(kpis, analyzed, competitor.name)

        # 7. Create audit record
        audit = EReputationAudit(
            competitor_id=competitor.id,
            reputation_score=kpis["reputation_score"],
            nps=kpis["nps"],
            sav_rate=kpis["sav_rate"],
            financial_risk_rate=kpis["financial_risk_rate"],
            engagement_rate=kpis["engagement_rate"],
            earned_ratio=kpis["earned_ratio"],
            sentiment_breakdown=json.dumps(kpis["sentiment_breakdown"]),
            platform_breakdown=json.dumps(kpis["platform_breakdown"]),
            ai_synthesis=json.dumps(synthesis),
            total_comments=kpis["total_comments"],
        )
        db.add(audit)
        db.flush()

        # 8. Bulk insert comments
        for c in analyzed:
            # Parse published_at
            pub_at = None
            if c.get("published_at"):
                try:
                    if isinstance(c["published_at"], (int, float)):
                        pub_at = datetime.fromtimestamp(c["published_at"])
                    elif isinstance(c["published_at"], str) and c["published_at"].isdigit():
                        pub_at = datetime.fromtimestamp(int(c["published_at"]))
                except Exception:
                    pass

            comment = EReputationComment(
                audit_id=audit.id,
                competitor_id=competitor.id,
                platform=c.get("platform", ""),
                comment_id=c.get("comment_id", ""),
                source_type=c.get("source_type", "owned"),
                source_url=c.get("source_url", ""),
                source_title=(c.get("source_title") or "")[:1000],
                author=(c.get("author") or "")[:200],
                text=c.get("text", ""),
                likes=c.get("likes", 0),
                replies=c.get("replies", 0),
                published_at=pub_at,
                collected_at=datetime.utcnow(),
                sentiment=c.get("sentiment", "neutral"),
                sentiment_score=c.get("sentiment_score", 0.0),
                categories=json.dumps(c.get("categories", [])),
                is_alert=c.get("is_alert", False),
                alert_reason=c.get("alert_reason", ""),
            )
            db.merge(comment)  # merge to handle dedup on comment_id

        db.commit()
        db.refresh(audit)

        logger.info(
            f"E-reputation audit complete for {competitor.name}: "
            f"score={kpis['reputation_score']}, NPS={kpis['nps']}, "
            f"{kpis['total_comments']} comments"
        )
        return audit


# Singleton
ereputation_service = EReputationService()
