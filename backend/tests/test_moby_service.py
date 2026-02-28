"""Tests for services/moby_ai.py — Moby AI SQL assistant."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

from services.moby_ai import MobyService, BLOCKED_TABLES, BLOCKED_KEYWORDS


# ─── sanitize_sql ─────────────────────────────────────────────────

class TestSanitizeSQL:
    def setup_method(self):
        self.svc = MobyService()

    def test_valid_select(self):
        ok, err = self.svc.sanitize_sql("SELECT name FROM competitors LIMIT 10")
        assert ok is True
        assert err == ""

    def test_empty_query(self):
        ok, err = self.svc.sanitize_sql("")
        assert ok is False
        assert "vide" in err

    def test_none_query(self):
        ok, err = self.svc.sanitize_sql(None)
        assert ok is False

    def test_drop_blocked(self):
        ok, err = self.svc.sanitize_sql("DROP TABLE competitors")
        assert ok is False

    def test_delete_blocked(self):
        ok, err = self.svc.sanitize_sql("DELETE FROM competitors WHERE id = 1")
        assert ok is False

    def test_insert_blocked(self):
        ok, err = self.svc.sanitize_sql("INSERT INTO competitors (name) VALUES ('x')")
        assert ok is False

    def test_update_blocked(self):
        ok, err = self.svc.sanitize_sql("UPDATE competitors SET name = 'x'")
        assert ok is False

    def test_alter_blocked(self):
        ok, err = self.svc.sanitize_sql("ALTER TABLE competitors ADD COLUMN x TEXT")
        assert ok is False

    def test_create_blocked(self):
        ok, err = self.svc.sanitize_sql("CREATE TABLE evil (id INT)")
        assert ok is False

    def test_truncate_blocked(self):
        ok, err = self.svc.sanitize_sql("TRUNCATE competitors")
        assert ok is False

    def test_copy_blocked(self):
        ok, err = self.svc.sanitize_sql("SELECT 1; COPY competitors TO '/tmp/x'")
        assert ok is False

    def test_pg_read_file_blocked(self):
        ok, err = self.svc.sanitize_sql("SELECT pg_read_file('/etc/passwd')")
        assert ok is False

    def test_union_all_select_blocked(self):
        ok, err = self.svc.sanitize_sql("SELECT 1 UNION ALL SELECT * FROM users")
        assert ok is False

    def test_semicolon_select_blocked(self):
        ok, err = self.svc.sanitize_sql("SELECT 1; SELECT * FROM users")
        assert ok is False

    def test_sql_comment_blocked(self):
        ok, err = self.svc.sanitize_sql("SELECT 1 -- comment")
        assert ok is False
        assert "Commentaires" in err

    def test_block_comment_blocked(self):
        ok, err = self.svc.sanitize_sql("SELECT /* evil */ 1")
        assert ok is False

    def test_users_table_blocked(self):
        ok, err = self.svc.sanitize_sql("SELECT * FROM users")
        assert ok is False
        assert "users" in err

    def test_system_settings_blocked(self):
        ok, err = self.svc.sanitize_sql("SELECT * FROM system_settings")
        assert ok is False

    def test_into_outfile_blocked(self):
        ok, err = self.svc.sanitize_sql("SELECT * INTO OUTFILE '/tmp/x' FROM competitors")
        assert ok is False

    def test_grant_blocked(self):
        ok, err = self.svc.sanitize_sql("GRANT ALL ON competitors TO evil")
        assert ok is False

    def test_execute_blocked(self):
        ok, err = self.svc.sanitize_sql("EXECUTE sp_evil")
        assert ok is False

    def test_lo_import_blocked(self):
        ok, err = self.svc.sanitize_sql("SELECT lo_import('/etc/passwd')")
        assert ok is False


# ─── ensure_limit ─────────────────────────────────────────────────

class TestEnsureLimit:
    def setup_method(self):
        self.svc = MobyService()

    def test_adds_limit(self):
        result = self.svc.ensure_limit("SELECT * FROM competitors")
        assert "LIMIT 50" in result

    def test_preserves_existing_limit(self):
        result = self.svc.ensure_limit("SELECT * FROM competitors LIMIT 10")
        assert "LIMIT 10" in result
        assert "LIMIT 50" not in result

    def test_strips_trailing_semicolon(self):
        result = self.svc.ensure_limit("SELECT * FROM competitors;")
        assert result.endswith("LIMIT 50")
        assert ";" not in result


# ─── has_keys property ────────────────────────────────────────────

class TestHasKeys:
    def test_no_keys(self):
        svc = MobyService()
        with patch.object(type(svc), "gemini_key", property(lambda s: "")):
            with patch.object(type(svc), "mistral_key", property(lambda s: "")):
                assert svc.has_keys is False

    def test_gemini_key(self):
        svc = MobyService()
        with patch.object(type(svc), "gemini_key", property(lambda s: "key")):
            assert svc.has_keys is True


# ─── _call_gemini ─────────────────────────────────────────────────

class TestCallGemini:
    @pytest.mark.asyncio
    async def test_no_key_returns_empty(self):
        svc = MobyService()
        with patch.object(type(svc), "gemini_key", property(lambda s: "")):
            result = await svc._call_gemini("system", [{"role": "user", "content": "test"}])
        assert result == ""

    @pytest.mark.asyncio
    async def test_success(self):
        svc = MobyService()
        with patch.object(type(svc), "gemini_key", property(lambda s: "fake-key")):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": '{"sql": "SELECT 1"}'}]}}]
            }
            mock_response.raise_for_status = MagicMock()

            with patch("services.moby_ai.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await svc._call_gemini("system", [{"role": "user", "content": "test"}])
        assert "SELECT" in result

    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        svc = MobyService()
        with patch.object(type(svc), "gemini_key", property(lambda s: "fake-key")):
            mock_response = MagicMock()
            mock_response.json.return_value = {"candidates": []}
            mock_response.raise_for_status = MagicMock()

            with patch("services.moby_ai.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_client

                result = await svc._call_gemini("system", [{"role": "user", "content": "test"}])
        assert result == ""


# ─── _call_mistral ────────────────────────────────────────────────

class TestCallMistral:
    @pytest.mark.asyncio
    async def test_no_key_returns_empty(self):
        svc = MobyService()
        with patch.object(type(svc), "mistral_key", property(lambda s: "")):
            result = await svc._call_mistral("system", [{"role": "user", "content": "test"}])
        assert result == ""


# ─── _call_llm fallback ──────────────────────────────────────────

class TestCallLLM:
    @pytest.mark.asyncio
    async def test_gemini_first(self):
        svc = MobyService()
        with patch.object(svc, "_call_gemini", new_callable=AsyncMock, return_value="gemini result"):
            with patch.object(type(svc), "gemini_key", property(lambda s: "key")):
                result = await svc._call_llm("sys", [{"role": "user", "content": "q"}])
        assert result == "gemini result"

    @pytest.mark.asyncio
    async def test_mistral_fallback(self):
        svc = MobyService()
        with patch.object(svc, "_call_gemini", new_callable=AsyncMock, side_effect=Exception("fail")):
            with patch.object(svc, "_call_mistral", new_callable=AsyncMock, return_value="mistral result"):
                with patch.object(type(svc), "gemini_key", property(lambda s: "key")):
                    with patch.object(type(svc), "mistral_key", property(lambda s: "key")):
                        result = await svc._call_llm("sys", [{"role": "user", "content": "q"}])
        assert result == "mistral result"

    @pytest.mark.asyncio
    async def test_all_fail(self):
        svc = MobyService()
        with patch.object(svc, "_call_gemini", new_callable=AsyncMock, side_effect=Exception("fail")):
            with patch.object(svc, "_call_mistral", new_callable=AsyncMock, side_effect=Exception("fail")):
                with patch.object(type(svc), "gemini_key", property(lambda s: "key")):
                    with patch.object(type(svc), "mistral_key", property(lambda s: "key")):
                        result = await svc._call_llm("sys", [{"role": "user", "content": "q"}])
        assert result == ""


# ─── generate_sql ─────────────────────────────────────────────────

class TestGenerateSQL:
    @pytest.mark.asyncio
    async def test_parses_json(self):
        svc = MobyService()
        with patch.object(svc, "_call_llm", new_callable=AsyncMock, return_value='{"sql": "SELECT name FROM competitors LIMIT 10"}'):
            with patch("database.SessionLocal") as mock_sl:
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = None
                mock_sl.return_value = mock_db
                result = await svc.generate_sql("Quels sont les concurrents ?")
        assert result == "SELECT name FROM competitors LIMIT 10"

    @pytest.mark.asyncio
    async def test_returns_none_on_empty(self):
        svc = MobyService()
        with patch.object(svc, "_call_llm", new_callable=AsyncMock, return_value=""):
            with patch("database.SessionLocal") as mock_sl:
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = None
                mock_sl.return_value = mock_db
                result = await svc.generate_sql("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_null_sql(self):
        svc = MobyService()
        with patch.object(svc, "_call_llm", new_callable=AsyncMock, return_value='{"sql": null}'):
            with patch("database.SessionLocal") as mock_sl:
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = None
                mock_sl.return_value = mock_db
                result = await svc.generate_sql("What's the weather?")
        assert result is None


# ─── process_question (integration) ──────────────────────────────

class TestProcessQuestion:
    @pytest.mark.asyncio
    async def test_no_keys(self):
        svc = MobyService()
        with patch.object(type(svc), "has_keys", property(lambda s: False)):
            result = await svc.process_question("test")
        assert "non configuree" in result["answer"]

    @pytest.mark.asyncio
    async def test_no_sql_generated(self):
        svc = MobyService()
        with patch.object(type(svc), "has_keys", property(lambda s: True)):
            with patch.object(svc, "generate_sql", new_callable=AsyncMock, return_value=None):
                with patch.object(svc, "_call_llm", new_callable=AsyncMock, return_value="Reponse directe"):
                    result = await svc.process_question("Bonjour")
        assert result["answer"] == "Reponse directe"
        assert result["sql"] is None

    @pytest.mark.asyncio
    async def test_unsafe_sql_blocked(self):
        svc = MobyService()
        with patch.object(type(svc), "has_keys", property(lambda s: True)):
            with patch.object(svc, "generate_sql", new_callable=AsyncMock, return_value="DROP TABLE competitors"):
                result = await svc.process_question("Delete everything")
        assert "securite" in result["answer"]

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        svc = MobyService()
        with patch.object(type(svc), "has_keys", property(lambda s: True)):
            with patch.object(svc, "generate_sql", new_callable=AsyncMock, return_value="SELECT name FROM competitors LIMIT 10"):
                with patch.object(svc, "execute_sql", return_value=([{"name": "Leclerc"}], 1)):
                    with patch.object(svc, "synthesize_answer", new_callable=AsyncMock, return_value="Leclerc est le principal concurrent."):
                        result = await svc.process_question("Quels concurrents ?")
        assert result["answer"] == "Leclerc est le principal concurrent."
        assert result["row_count"] == 1
        assert result["sql"] is None  # never exposed

    @pytest.mark.asyncio
    async def test_execution_error(self):
        svc = MobyService()
        with patch.object(type(svc), "has_keys", property(lambda s: True)):
            with patch.object(svc, "generate_sql", new_callable=AsyncMock, return_value="SELECT * FROM competitors"):
                with patch.object(svc, "execute_sql", side_effect=Exception("DB error")):
                    result = await svc.process_question("test")
        assert "reformuler" in result["answer"]

    @pytest.mark.asyncio
    async def test_zero_results(self):
        svc = MobyService()
        with patch.object(type(svc), "has_keys", property(lambda s: True)):
            with patch.object(svc, "generate_sql", new_callable=AsyncMock, return_value="SELECT * FROM competitors WHERE id = 999"):
                with patch.object(svc, "execute_sql", return_value=([], 0)):
                    result = await svc.process_question("Un concurrent inexistant")
        assert "Aucune donnee" in result["answer"]
