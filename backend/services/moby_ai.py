"""
Moby AI Assistant Service.
Translates natural language questions into SQL queries using Claude Haiku,
executes them safely, and returns business-friendly answers.
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

# Step 1: Generate SQL from natural language
SQL_SYSTEM_PROMPT = """Tu es un expert SQL. Tu traduis des questions business en requêtes SQL SELECT.

SCHEMA :
competitors(id, name, website, facebook_page_id, instagram_username, tiktok_username, youtube_channel_id, playstore_app_id, appstore_app_id, is_brand BOOLEAN, is_active BOOLEAN)
ads(id, competitor_id FK competitors, ad_id, platform, ad_text, cta, start_date, end_date, is_active BOOLEAN, estimated_spend_min FLOAT, estimated_spend_max FLOAT, impressions_min INT, impressions_max INT, page_name, display_format, creative_concept, creative_tone, creative_score INT 0-100, product_category, product_subcategory, ad_objective, ad_type, promo_type, creative_format, price_visible BOOLEAN, price_value, seasonal_event, eu_total_reach BIGINT)
instagram_data(id, competitor_id FK, followers INT, following INT, posts_count INT, avg_likes FLOAT, avg_comments FLOAT, engagement_rate FLOAT, bio TEXT, recorded_at DATETIME)
tiktok_data(id, competitor_id FK, username, followers BIGINT, following INT, likes BIGINT, videos_count INT, bio TEXT, verified BOOLEAN, recorded_at DATETIME)
youtube_data(id, competitor_id FK, channel_id, channel_name, subscribers BIGINT, total_views BIGINT, videos_count INT, avg_views INT, avg_likes INT, avg_comments INT, engagement_rate FLOAT, recorded_at DATETIME)
snapchat_data(id, competitor_id FK, subscribers BIGINT, title, story_count INT, spotlight_count INT, total_views BIGINT, engagement_rate FLOAT, recorded_at DATETIME)
app_data(id, competitor_id FK, store VARCHAR 'playstore'|'appstore', app_id, app_name, rating FLOAT, reviews_count INT, downloads VARCHAR, downloads_numeric BIGINT, version, last_updated DATETIME, recorded_at DATETIME)
social_posts(id, competitor_id FK, platform VARCHAR 'tiktok'|'youtube'|'instagram', post_id, title, url, views BIGINT, likes BIGINT, comments INT, shares INT, published_at DATETIME, content_theme, content_tone, content_engagement_score INT 0-100)
store_locations(id, competitor_id FK, name, brand_name, category, address, postal_code, city, department, latitude FLOAT, longitude FLOAT, google_rating FLOAT, google_reviews_count INT)
signals(id, competitor_id FK, signal_type, severity VARCHAR 'info'|'warning'|'critical', platform, title, description, metric_name, previous_value FLOAT, current_value FLOAT, change_percent FLOAT, is_brand BOOLEAN, is_read BOOLEAN, detected_at DATETIME)
serp_results(id, keyword, position INT, competitor_id FK, title, url, domain, recorded_at DATETIME)

REGLES :
1. Retourne UNIQUEMENT un JSON valide : {"sql": "SELECT ..."}
2. SELECT uniquement. Jamais DROP/DELETE/INSERT/UPDATE.
3. Ne JAMAIS acceder aux tables : users, system_settings, prompt_templates, user_advertisers.
4. JOIN avec competitors pour afficher les noms.
5. LIMIT 50 max.
6. Pour les donnees temporelles, prends le dernier enregistrement par competitor (MAX(recorded_at) via subquery ou window).
7. Si la question ne concerne pas la base, retourne : {"sql": null}"""

# Step 2: Synthesize business answer from data
ANSWER_SYSTEM_PROMPT = """Tu es Moby, un assistant IA de veille concurrentielle pour le retail en France.
Tu analyses des donnees et reponds de maniere claire, strategique et actionnable.

REGLES :
- Reponds en francais, de maniere conversationnelle et professionnelle.
- Sois concis : 2-5 phrases d'analyse + les donnees cles.
- Utilise des tableaux markdown UNIQUEMENT si la question demande une comparaison ou un classement avec 3+ items.
- Mets en **gras** les chiffres importants et les noms de concurrents.
- Donne des insights business, pas juste des chiffres : tendances, forces/faiblesses, recommandations.
- Si les donnees sont vides, dis-le simplement et suggere une action (ex: "Lancez une collecte").
- Ne mentionne JAMAIS SQL, requetes, base de donnees, tables, colonnes. Tu ne fais que de l'analyse business.
- Utilise des emojis avec parcimonie (1-2 max par reponse) pour rendre la lecture agreable.
- Formate les grands nombres : 1.2M, 45K, etc."""


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
            return False, "Requete SQL vide"

        stripped = sql.strip().rstrip(";")

        if not re.match(r"^\s*SELECT\b", stripped, re.IGNORECASE):
            return False, "Seules les requetes SELECT sont autorisees"

        if "--" in stripped or "/*" in stripped:
            return False, "Commentaires SQL non autorises"

        if BLOCKED_KEYWORDS.search(stripped):
            return False, "Operation non autorisee detectee"

        sql_lower = stripped.lower()
        for table in BLOCKED_TABLES:
            if re.search(rf"\b{table}\b", sql_lower):
                return False, f"Acces a la table '{table}' non autorise"

        return True, ""

    def ensure_limit(self, sql: str, max_limit: int = 50) -> str:
        """Add LIMIT if not present."""
        if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
            sql = sql.rstrip().rstrip(";")
            sql += f" LIMIT {max_limit}"
        return sql

    async def _call_claude(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
    ) -> str:
        """Low-level Claude API call. Returns raw text content."""
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(CLAUDE_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("content", [{}])[0].get("text", "")

    async def generate_sql(
        self,
        question: str,
        history: list[dict] | None = None,
    ) -> str | None:
        """Step 1: Ask Claude to generate SQL from the question."""
        messages = []
        if history:
            for msg in history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})

        try:
            content = await self._call_claude(SQL_SYSTEM_PROMPT, messages, max_tokens=512)
            if not content:
                return None
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return parsed.get("sql")
            return None
        except Exception as e:
            logger.error(f"Moby SQL generation error: {e}")
            return None

    async def synthesize_answer(
        self,
        question: str,
        rows: list[dict],
        row_count: int,
    ) -> str:
        """Step 2: Ask Claude to synthesize a business answer from the data."""
        # Truncate data for the prompt (max ~3000 chars)
        data_str = json.dumps(rows[:30], ensure_ascii=False, default=str)
        if len(data_str) > 3000:
            data_str = data_str[:3000] + "..."

        user_prompt = f"""Question de l'utilisateur : "{question}"

Donnees ({row_count} resultats) :
{data_str}

Reponds a la question de l'utilisateur en analysant ces donnees. Sois strategique et actionnable."""

        try:
            content = await self._call_claude(
                ANSWER_SYSTEM_PROMPT,
                [{"role": "user", "content": user_prompt}],
                max_tokens=1024,
            )
            return content or "Je n'ai pas pu analyser les donnees."
        except Exception as e:
            logger.error(f"Moby synthesis error: {e}")
            return "Erreur lors de l'analyse des donnees."

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

    async def process_question(
        self,
        question: str,
        history: list[dict] | None = None,
    ) -> dict:
        """Full pipeline: question -> SQL -> execute -> synthesize answer."""
        if not self.api_key:
            return {
                "answer": "Cle API Anthropic non configuree. Contactez l'administrateur.",
                "sql": None,
                "row_count": 0,
                "error": None,
            }

        # Step 1: Generate SQL
        sql = await self.generate_sql(question, history)

        # No SQL = direct conversational answer
        if not sql:
            try:
                content = await self._call_claude(
                    ANSWER_SYSTEM_PROMPT,
                    [{"role": "user", "content": question}],
                    max_tokens=512,
                )
                return {
                    "answer": content or "Je ne suis pas sur de comprendre la question.",
                    "sql": None,
                    "row_count": 0,
                    "error": None,
                }
            except Exception as e:
                logger.error(f"Moby direct answer error: {e}")
                return {
                    "answer": "Desole, je n'ai pas pu traiter votre question.",
                    "sql": None,
                    "row_count": 0,
                    "error": str(e),
                }

        # Step 2: Sanitize
        is_safe, error_msg = self.sanitize_sql(sql)
        if not is_safe:
            return {
                "answer": f"Je ne peux pas repondre a cette question pour des raisons de securite.",
                "sql": None,
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
                "answer": "Desole, je n'ai pas pu recuperer les donnees. Essayez de reformuler votre question.",
                "sql": None,
                "row_count": 0,
                "error": str(e),
            }

        # Step 5: Synthesize business answer
        if count == 0:
            answer = "Aucune donnee trouvee pour cette question. Verifiez que les donnees ont ete collectees (onglet Vue d'ensemble > Synchroniser)."
        else:
            answer = await self.synthesize_answer(question, rows, count)

        return {
            "answer": answer,
            "sql": None,  # Never expose SQL to the user
            "row_count": count,
            "error": None,
        }


# Global instance
moby_service = MobyService()
