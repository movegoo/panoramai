"""Tests for Moby AI chatbot."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.moby_ai import MobyService


class TestSQLSanitization:
    """Test SQL query sanitization."""

    def setup_method(self):
        self.service = MobyService()

    def test_valid_select(self):
        ok, err = self.service.sanitize_sql("SELECT name FROM competitors")
        assert ok is True
        assert err == ""

    def test_valid_select_with_join(self):
        ok, err = self.service.sanitize_sql(
            "SELECT c.name, COUNT(a.id) FROM competitors c JOIN ads a ON a.competitor_id = c.id GROUP BY c.name"
        )
        assert ok is True

    def test_reject_empty(self):
        ok, err = self.service.sanitize_sql("")
        assert ok is False

    def test_reject_drop(self):
        ok, err = self.service.sanitize_sql("DROP TABLE competitors")
        assert ok is False
        assert "SELECT" in err

    def test_reject_delete(self):
        ok, err = self.service.sanitize_sql("SELECT 1; DELETE FROM competitors")
        assert ok is False

    def test_reject_insert(self):
        ok, err = self.service.sanitize_sql("INSERT INTO competitors (name) VALUES ('test')")
        assert ok is False

    def test_reject_update(self):
        ok, err = self.service.sanitize_sql("UPDATE competitors SET name = 'x'")
        assert ok is False

    def test_reject_alter(self):
        ok, err = self.service.sanitize_sql("ALTER TABLE competitors ADD COLUMN x TEXT")
        assert ok is False

    def test_reject_users_table(self):
        ok, err = self.service.sanitize_sql("SELECT * FROM users")
        assert ok is False
        assert "users" in err

    def test_reject_system_settings_table(self):
        ok, err = self.service.sanitize_sql("SELECT * FROM system_settings")
        assert ok is False

    def test_reject_prompt_templates_table(self):
        ok, err = self.service.sanitize_sql("SELECT * FROM prompt_templates")
        assert ok is False

    def test_reject_sql_comments(self):
        ok, err = self.service.sanitize_sql("SELECT * FROM competitors -- drop table")
        assert ok is False
        assert "Commentaires" in err

    def test_reject_block_comments(self):
        ok, err = self.service.sanitize_sql("SELECT * FROM competitors /* evil */")
        assert ok is False

    def test_case_insensitive_block(self):
        ok, err = self.service.sanitize_sql("select * from Users")
        assert ok is False

    def test_select_with_subquery(self):
        ok, err = self.service.sanitize_sql(
            "SELECT name FROM competitors WHERE id IN (SELECT competitor_id FROM ads)"
        )
        assert ok is True


class TestEnsureLimit:
    def setup_method(self):
        self.service = MobyService()

    def test_adds_limit_when_missing(self):
        result = self.service.ensure_limit("SELECT * FROM competitors")
        assert "LIMIT 50" in result

    def test_keeps_existing_limit(self):
        result = self.service.ensure_limit("SELECT * FROM competitors LIMIT 10")
        assert "LIMIT 10" in result
        assert result.count("LIMIT") == 1

    def test_custom_max_limit(self):
        result = self.service.ensure_limit("SELECT * FROM ads", max_limit=100)
        assert "LIMIT 100" in result


@pytest.mark.asyncio
async def test_process_question_no_api_key():
    """Returns error message when no API keys configured."""
    service = MobyService()
    with patch.object(type(service), "has_keys", new_callable=lambda: property(lambda self: False)):
        result = await service.process_question("test")
    assert "Cle API" in result["answer"]
    assert result["sql"] is None


@pytest.mark.asyncio
async def test_process_question_sql_never_exposed():
    """SQL is never returned in the response (hidden from users)."""
    service = MobyService()

    with patch.object(service, "generate_sql", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "SELECT name FROM competitors"
        with patch.object(service, "execute_sql") as mock_exec:
            mock_exec.return_value = ([{"name": "Carrefour"}], 1)
            with patch.object(service, "synthesize_answer", new_callable=AsyncMock) as mock_synth:
                mock_synth.return_value = "**Carrefour** est le leader."
                with patch.object(type(service), "has_keys", new_callable=lambda: property(lambda self: True)):
                    result = await service.process_question("Qui est le leader ?")

    assert result["sql"] is None  # SQL must NEVER be exposed
    assert "Carrefour" in result["answer"]
    assert result["row_count"] == 1


@pytest.mark.asyncio
async def test_process_question_no_sql_needed():
    """When no SQL is needed, returns a direct conversational answer."""
    service = MobyService()

    with patch.object(service, "generate_sql", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = None  # No SQL needed
        with patch.object(service, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "Bonjour ! Je suis Moby, votre assistant."
            with patch.object(type(service), "has_keys", new_callable=lambda: property(lambda self: True)):
                result = await service.process_question("Bonjour")

    assert "Moby" in result["answer"]
    assert result["sql"] is None


@pytest.mark.asyncio
async def test_process_question_unsafe_sql():
    """Unsafe SQL is rejected without exposing it."""
    service = MobyService()

    with patch.object(service, "generate_sql", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "SELECT * FROM users"  # Blocked table
        with patch.object(type(service), "has_keys", new_callable=lambda: property(lambda self: True)):
            result = await service.process_question("Show me users")

    assert result["sql"] is None  # Don't expose the SQL
    assert "securite" in result["answer"]


@pytest.mark.asyncio
async def test_process_question_empty_results():
    """Empty results give a helpful message."""
    service = MobyService()

    with patch.object(service, "generate_sql", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "SELECT name FROM competitors WHERE name = 'Inexistant'"
        with patch.object(service, "execute_sql") as mock_exec:
            mock_exec.return_value = ([], 0)
            with patch.object(type(service), "has_keys", new_callable=lambda: property(lambda self: True)):
                result = await service.process_question("Trouve Inexistant")

    assert "Aucune donnee" in result["answer"]
    assert result["row_count"] == 0


@pytest.mark.asyncio
async def test_synthesize_answer_called_with_data():
    """Synthesize is called with the question and data rows."""
    service = MobyService()
    rows = [{"name": "Carrefour", "followers": 500000}, {"name": "Lidl", "followers": 300000}]

    with patch.object(service, "generate_sql", new_callable=AsyncMock, return_value="SELECT ..."):
        with patch.object(service, "execute_sql", return_value=(rows, 2)):
            with patch.object(service, "synthesize_answer", new_callable=AsyncMock) as mock_synth:
                mock_synth.return_value = "Carrefour domine avec 500K followers."
                with patch.object(type(service), "has_keys", new_callable=lambda: property(lambda self: True)):
                    result = await service.process_question("Compare Instagram")

    mock_synth.assert_called_once_with("Compare Instagram", rows, 2)
    assert "Carrefour" in result["answer"]


def test_config_default(client):
    """Config returns defaults when no settings exist."""
    response = client.get("/api/moby/config")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["position"] == "bottom-right"


def test_ask_requires_auth(client):
    """Ask endpoint requires authentication."""
    response = client.post("/api/moby/ask", json={"question": "test"})
    assert response.status_code in (401, 403)
