"""Tests for Moby AI chatbot."""
import pytest
from unittest.mock import patch, AsyncMock

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
        assert "non autorisée" in err

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


class TestFormatResults:
    def setup_method(self):
        self.service = MobyService()

    def test_empty_results(self):
        result = self.service.format_results([], "Test")
        assert "Aucun résultat" in result

    def test_single_value(self):
        result = self.service.format_results([{"count": 42}], "Nombre de pubs")
        assert "42" in result

    def test_table_format(self):
        rows = [
            {"name": "Carrefour", "followers": 100000},
            {"name": "Lidl", "followers": 80000},
        ]
        result = self.service.format_results(rows, "Followers Instagram")
        assert "Carrefour" in result
        assert "Lidl" in result
        assert "|" in result


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


@pytest.mark.skipif(True, reason="PyJWT sub-as-int regression in newer versions")
def test_ask_with_auth(client, auth_headers):
    """Ask endpoint works with auth and returns mocked response."""
    with patch("routers.moby.moby_service.process_question", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = {
            "answer": "Il y a 42 pubs Carrefour.",
            "sql": "SELECT COUNT(*) FROM ads",
            "row_count": 1,
            "error": None,
        }
        response = client.post(
            "/api/moby/ask",
            json={"question": "Combien de pubs a Carrefour ?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "42" in data["answer"]
        assert data["sql"] is not None


@pytest.mark.skipif(True, reason="PyJWT sub-as-int regression in newer versions")
def test_ask_with_history(client, auth_headers):
    """Ask endpoint forwards history to the service."""
    with patch("routers.moby.moby_service.process_question", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = {
            "answer": "Voici les détails.",
            "sql": None,
            "row_count": 0,
            "error": None,
        }
        response = client.post(
            "/api/moby/ask",
            json={
                "question": "Et pour Lidl ?",
                "history": [
                    {"role": "user", "content": "Combien de pubs a Carrefour ?"},
                    {"role": "assistant", "content": "42 pubs."},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        mock_process.assert_called_once()
