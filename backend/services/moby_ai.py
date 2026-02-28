"""
Moby AI Assistant Service.
Translates natural language questions into SQL queries using Gemini + Mistral,
executes them safely, and returns business-friendly answers.
"""
import asyncio
import json
import logging
import os
import re
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

# Tables that Moby is NOT allowed to query
BLOCKED_TABLES = {"users", "system_settings", "prompt_templates", "user_advertisers"}

# SQL statements that are NOT allowed
BLOCKED_KEYWORDS = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|"
    r"EXEC|EXECUTE|MERGE|COPY|LOAD|INTO\s+OUTFILE|INTO\s+DUMPFILE|"
    r"pg_read_file|pg_write_file|pg_ls_dir|lo_import|lo_export|"
    r"UNION\s+ALL\s+SELECT|;\s*SELECT)\b",
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
    """Service for Moby AI assistant — powered by Gemini + Mistral."""

    @property
    def gemini_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "") or settings.GEMINI_API_KEY

    @property
    def mistral_key(self) -> str:
        return os.getenv("MISTRAL_API_KEY", "") or settings.MISTRAL_API_KEY

    @property
    def has_keys(self) -> bool:
        return bool(self.gemini_key or self.mistral_key)

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

    async def _call_gemini(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
    ) -> str:
        """Gemini API call. Returns raw text content."""
        if not self.gemini_key:
            return ""
        # Build prompt: system + messages
        parts = [{"text": f"[Instructions système]\n{system}"}]
        for msg in messages:
            role_label = "Utilisateur" if msg["role"] == "user" else "Assistant"
            parts.append({"text": f"[{role_label}]\n{msg['content']}"})

        url = GEMINI_API_URL.format(model="gemini-3-flash-preview") + f"?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.2,
            },
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
            candidates = body.get("candidates", [])
            if not candidates:
                return ""
            return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

    async def _call_mistral(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
    ) -> str:
        """Mistral API call. Returns raw text content."""
        if not self.mistral_key:
            return ""
        api_messages = [{"role": "system", "content": system}]
        api_messages.extend(messages)

        headers = {
            "Authorization": f"Bearer {self.mistral_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "mistral-small-latest",
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(MISTRAL_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
            return body.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def _call_llm(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
    ) -> str:
        """Call Gemini (primary) with Mistral fallback."""
        # Try Gemini first
        if self.gemini_key:
            try:
                result = await self._call_gemini(system, messages, max_tokens)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Moby Gemini error, trying Mistral: {e}")

        # Fallback to Mistral
        if self.mistral_key:
            try:
                result = await self._call_mistral(system, messages, max_tokens)
                if result:
                    return result
            except Exception as e:
                logger.error(f"Moby Mistral error: {e}")

        return ""

    async def generate_sql(
        self,
        question: str,
        history: list[dict] | None = None,
    ) -> str | None:
        """Step 1: Generate SQL from the question."""
        # Load prompt from DB if available
        db_prompt = SQL_SYSTEM_PROMPT
        try:
            from database import SessionLocal, PromptTemplate
            _db = SessionLocal()
            row = _db.query(PromptTemplate).filter(PromptTemplate.key == "moby_sql").first()
            if row:
                db_prompt = row.prompt_text
            _db.close()
        except Exception:
            pass

        messages = []
        if history:
            for msg in history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})

        try:
            content = await self._call_llm(db_prompt, messages, max_tokens=512)
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
        """Step 2: Synthesize a business answer from the data."""
        # Load prompt from DB if available
        db_prompt = ANSWER_SYSTEM_PROMPT
        try:
            from database import SessionLocal, PromptTemplate
            _db = SessionLocal()
            row = _db.query(PromptTemplate).filter(PromptTemplate.key == "moby_answer").first()
            if row:
                db_prompt = row.prompt_text
            _db.close()
        except Exception:
            pass

        # Truncate data for the prompt (max ~3000 chars)
        data_str = json.dumps(rows[:30], ensure_ascii=False, default=str)
        if len(data_str) > 3000:
            data_str = data_str[:3000] + "..."

        user_prompt = f"""Question de l'utilisateur : "{question}"

Donnees ({row_count} resultats) :
{data_str}

Reponds a la question de l'utilisateur en analysant ces donnees. Sois strategique et actionnable."""

        try:
            content = await self._call_llm(
                db_prompt,
                [{"role": "user", "content": user_prompt}],
                max_tokens=1024,
            )
            return content or "Je n'ai pas pu analyser les donnees."
        except Exception as e:
            logger.error(f"Moby synthesis error: {e}")
            return "Erreur lors de l'analyse des donnees."

    def execute_sql(self, sql: str) -> tuple[list[dict], int]:
        """Execute a sanitized SQL query with safety limits."""
        from database import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            # Set query timeout to prevent DoS (5 seconds max)
            db.execute(text("SET statement_timeout = '5s'"))
            result = db.execute(text(sql))
            columns = list(result.keys())
            rows = []
            # Hard limit on returned rows to prevent memory exhaustion
            MAX_ROWS = 500
            for i, row in enumerate(result.fetchall()):
                if i >= MAX_ROWS:
                    break
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
        if not self.has_keys:
            return {
                "answer": "Cle API non configuree (Gemini/Mistral). Contactez l'administrateur.",
                "sql": None,
                "row_count": 0,
                "error": None,
            }

        # Step 1: Generate SQL
        sql = await self.generate_sql(question, history)

        # No SQL = direct conversational answer
        if not sql:
            try:
                content = await self._call_llm(
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
