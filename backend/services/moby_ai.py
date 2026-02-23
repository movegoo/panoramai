"""
Moby AI Assistant Service.
Translates natural language questions into SQL queries using Claude Haiku,
executes them safely, and returns formatted answers.
"""
import json
import logging
import os
import re
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# Tables that Moby is NOT allowed to query
BLOCKED_TABLES = {"users", "system_settings", "prompt_templates", "user_advertisers"}

# SQL statements that are NOT allowed
BLOCKED_KEYWORDS = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|EXEC|EXECUTE|MERGE)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """Tu es Moby, un assistant IA expert en veille concurrentielle pour le retail en France.
Tu traduis les questions en langage naturel en requêtes SQL SELECT sur la base de données.

SCHEMA DE LA BASE DE DONNEES :

-- Concurrents surveillés
competitors(id, name, website, facebook_page_id, instagram_username, tiktok_username, youtube_channel_id, playstore_app_id, appstore_app_id, is_brand BOOLEAN, is_active BOOLEAN)

-- Publicités Meta (Facebook/Instagram)
ads(id, competitor_id FK competitors, ad_id, platform, ad_text, cta, start_date, end_date, is_active BOOLEAN, estimated_spend_min FLOAT, estimated_spend_max FLOAT, impressions_min INT, impressions_max INT, page_name, display_format, creative_concept, creative_tone, creative_score INT 0-100, product_category, product_subcategory, ad_objective, ad_type, promo_type, creative_format, price_visible BOOLEAN, price_value, seasonal_event, eu_total_reach BIGINT)

-- Instagram
instagram_data(id, competitor_id FK, followers INT, following INT, posts_count INT, avg_likes FLOAT, avg_comments FLOAT, engagement_rate FLOAT, bio TEXT, recorded_at DATETIME)

-- TikTok
tiktok_data(id, competitor_id FK, username, followers BIGINT, following INT, likes BIGINT, videos_count INT, bio TEXT, verified BOOLEAN, recorded_at DATETIME)

-- YouTube
youtube_data(id, competitor_id FK, channel_id, channel_name, subscribers BIGINT, total_views BIGINT, videos_count INT, avg_views INT, avg_likes INT, avg_comments INT, engagement_rate FLOAT, recorded_at DATETIME)

-- Snapchat
snapchat_data(id, competitor_id FK, subscribers BIGINT, title, story_count INT, spotlight_count INT, total_views BIGINT, engagement_rate FLOAT, recorded_at DATETIME)

-- Applications mobiles (Play Store / App Store)
app_data(id, competitor_id FK, store VARCHAR 'playstore'|'appstore', app_id, app_name, rating FLOAT, reviews_count INT, downloads VARCHAR, downloads_numeric BIGINT, version, last_updated DATETIME, recorded_at DATETIME)

-- Posts sociaux individuels
social_posts(id, competitor_id FK, platform VARCHAR 'tiktok'|'youtube'|'instagram', post_id, title, url, views BIGINT, likes BIGINT, comments INT, shares INT, published_at DATETIME, content_theme, content_tone, content_engagement_score INT 0-100)

-- Magasins physiques
store_locations(id, competitor_id FK, name, brand_name, category, address, postal_code, city, department, latitude FLOAT, longitude FLOAT, google_rating FLOAT, google_reviews_count INT)

-- Signaux & alertes
signals(id, competitor_id FK, signal_type, severity VARCHAR 'info'|'warning'|'critical', platform, title, description, metric_name, previous_value FLOAT, current_value FLOAT, change_percent FLOAT, is_brand BOOLEAN, is_read BOOLEAN, detected_at DATETIME)

-- SERP Google
serp_results(id, keyword, position INT, competitor_id FK, title, url, domain, recorded_at DATETIME)

REGLES :
1. Retourne UNIQUEMENT un JSON valide, sans markdown, sans ```.
2. La requête SQL doit être un SELECT uniquement.
3. Ne JAMAIS accéder aux tables : users, system_settings, prompt_templates, user_advertisers.
4. Utilise des JOINs avec competitors pour afficher les noms au lieu des IDs.
5. Ajoute LIMIT 50 si la requête pourrait retourner beaucoup de résultats.
6. Pour les données temporelles (instagram_data, tiktok_data, etc.), prends le dernier enregistrement par competitor (MAX(recorded_at)).
7. Réponds toujours en français.

FORMAT DE REPONSE :
{"sql": "SELECT ...", "explanation": "Explication de ce que fait la requête en français"}

Si la question ne concerne pas les données de la base, retourne :
{"sql": null, "explanation": "Réponse directe à la question"}"""


class MobyService:
    """Service for Moby AI assistant."""

    @property
    def api_key(self) -> str:
        key = (
            os.getenv("ANTHROPIC_API_KEY", "")
            or os.getenv("CLAUDE_KEY", "")
            or getattr(settings, "ANTHROPIC_API_KEY", "")
        )
        if key:
            return key
        try:
            from database import SessionLocal, SystemSetting
            db = SessionLocal()
            row = db.query(SystemSetting).filter(SystemSetting.key == "anthropic_api_key").first()
            db.close()
            return row.value if row else ""
        except Exception:
            return ""

    def sanitize_sql(self, sql: str) -> tuple[bool, str]:
        """Validate SQL query. Returns (is_safe, error_message)."""
        if not sql or not sql.strip():
            return False, "Requête SQL vide"

        stripped = sql.strip().rstrip(";")

        # Must start with SELECT
        if not re.match(r"^\s*SELECT\b", stripped, re.IGNORECASE):
            return False, "Seules les requêtes SELECT sont autorisées"

        # Check for comments (potential SQL injection)
        if "--" in stripped or "/*" in stripped:
            return False, "Commentaires SQL non autorisés"

        # Check for blocked keywords
        if BLOCKED_KEYWORDS.search(stripped):
            return False, "Opération non autorisée détectée"

        # Check for blocked tables
        sql_lower = stripped.lower()
        for table in BLOCKED_TABLES:
            # Match table name as a whole word (not substring)
            if re.search(rf"\b{table}\b", sql_lower):
                return False, f"Accès à la table '{table}' non autorisé"

        return True, ""

    def ensure_limit(self, sql: str, max_limit: int = 50) -> str:
        """Add LIMIT if not present."""
        if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
            sql = sql.rstrip().rstrip(";")
            sql += f" LIMIT {max_limit}"
        return sql

    async def ask_claude(
        self,
        question: str,
        history: list[dict] | None = None,
    ) -> dict:
        """Send question to Claude and get SQL + explanation."""
        if not self.api_key:
            return {"sql": None, "explanation": "Clé API Anthropic non configurée. Contactez l'administrateur."}

        messages = []
        if history:
            for msg in history[-10:]:  # Max 10 messages of context
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})

        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                response = await client.post(CLAUDE_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get("content", [{}])[0].get("text", "")
                if not content:
                    return {"sql": None, "explanation": "Pas de réponse de l'IA."}

                # Parse JSON response
                # Try to extract JSON from the response (handle markdown wrapping)
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return {"sql": None, "explanation": content}

            except httpx.HTTPStatusError as e:
                logger.error(f"Moby Claude API error: {e.response.status_code} - {e.response.text}")
                return {"sql": None, "explanation": "Erreur de communication avec l'IA."}
            except json.JSONDecodeError:
                return {"sql": None, "explanation": content if content else "Réponse invalide de l'IA."}
            except Exception as e:
                logger.error(f"Moby error: {e}")
                return {"sql": None, "explanation": "Erreur interne du service Moby."}

    def execute_sql(self, sql: str) -> tuple[list[dict], int]:
        """Execute a sanitized SQL query and return results."""
        from database import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            result = db.execute(text(sql))
            columns = list(result.keys())
            rows = []
            for row in result.fetchall():
                rows.append(dict(zip(columns, row)))
            return rows, len(rows)
        finally:
            db.close()

    def format_results(self, rows: list[dict], explanation: str) -> str:
        """Format SQL results into a readable answer."""
        if not rows:
            return f"{explanation}\n\nAucun résultat trouvé."

        # For single-value results
        if len(rows) == 1 and len(rows[0]) == 1:
            key = list(rows[0].keys())[0]
            value = rows[0][key]
            return f"{explanation}\n\n**{key}** : {value}"

        # For tabular results
        if len(rows) <= 20:
            lines = [explanation, ""]
            # Header
            cols = list(rows[0].keys())
            lines.append("| " + " | ".join(str(c) for c in cols) + " |")
            lines.append("| " + " | ".join("---" for _ in cols) + " |")
            for row in rows:
                vals = []
                for c in cols:
                    v = row[c]
                    if v is None:
                        vals.append("-")
                    elif isinstance(v, float):
                        vals.append(f"{v:,.2f}")
                    elif isinstance(v, int) and abs(v) > 9999:
                        vals.append(f"{v:,}")
                    else:
                        vals.append(str(v))
                lines.append("| " + " | ".join(vals) + " |")
            return "\n".join(lines)

        # Too many rows: summarize
        lines = [explanation, "", f"{len(rows)} résultats trouvés. Voici les 10 premiers :", ""]
        cols = list(rows[0].keys())
        lines.append("| " + " | ".join(str(c) for c in cols) + " |")
        lines.append("| " + " | ".join("---" for _ in cols) + " |")
        for row in rows[:10]:
            vals = [str(row.get(c, "-")) for c in cols]
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines)

    async def process_question(
        self,
        question: str,
        history: list[dict] | None = None,
    ) -> dict:
        """Full pipeline: question → Claude → SQL → results → formatted answer."""
        # Step 1: Ask Claude
        claude_response = await self.ask_claude(question, history)
        sql = claude_response.get("sql")
        explanation = claude_response.get("explanation", "")

        # No SQL needed (direct answer)
        if not sql:
            return {
                "answer": explanation,
                "sql": None,
                "row_count": 0,
                "error": None,
            }

        # Step 2: Sanitize
        is_safe, error_msg = self.sanitize_sql(sql)
        if not is_safe:
            return {
                "answer": f"Je ne peux pas exécuter cette requête : {error_msg}",
                "sql": sql,
                "row_count": 0,
                "error": error_msg,
            }

        # Step 3: Ensure LIMIT
        sql = self.ensure_limit(sql)

        # Step 4: Execute
        try:
            rows, count = self.execute_sql(sql)
        except Exception as e:
            logger.error(f"Moby SQL execution error: {e}")
            return {
                "answer": f"Erreur lors de l'exécution de la requête : {str(e)}",
                "sql": sql,
                "row_count": 0,
                "error": str(e),
            }

        # Step 5: Format
        answer = self.format_results(rows, explanation)

        return {
            "answer": answer,
            "sql": sql,
            "row_count": count,
            "error": None,
        }


# Global instance
moby_service = MobyService()
