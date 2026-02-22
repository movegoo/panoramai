"""Tests for admin tools: re-enrich, data-health."""
from unittest.mock import patch, AsyncMock


def test_re_enrich_calls_enrichment(client, db, auth_headers, test_competitor):
    """Re-enrich endpoint calls _auto_enrich_competitor."""
    from database import User
    user = db.query(User).first()
    user.is_admin = True
    db.commit()

    with patch("routers.competitors._auto_enrich_competitor", new_callable=AsyncMock, return_value={"stores": 5}) as mock_enrich:
        resp = client.post(f"/api/admin/re-enrich/{test_competitor.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert "terminé" in resp.json()["message"]
        mock_enrich.assert_called_once()


def test_re_enrich_non_admin_403(client, auth_headers, test_competitor):
    """Non-admin gets 403 on re-enrich."""
    resp = client.post(f"/api/admin/re-enrich/{test_competitor.id}", headers=auth_headers)
    assert resp.status_code == 403


def test_re_enrich_all_non_admin_403(client, auth_headers):
    """Non-admin gets 403 on re-enrich-all."""
    resp = client.post("/api/admin/re-enrich-all", headers=auth_headers)
    assert resp.status_code == 403


def test_data_health_returns_structure(client, db, auth_headers):
    """Data-health returns the expected structure."""
    from database import User
    user = db.query(User).first()
    user.is_admin = True
    db.commit()

    resp = client.get("/api/admin/data-health", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_competitors" in data
    assert "never_enriched" in data
    assert "stale" in data
    assert "coverage" in data
    assert "report" in data


def test_data_health_identifies_stale(client, db, auth_headers, test_competitor):
    """Data-health identifies competitors with no data as never_enriched."""
    from database import User
    user = db.query(User).first()
    user.is_admin = True
    db.commit()

    resp = client.get("/api/admin/data-health", headers=auth_headers)
    data = resp.json()
    never_ids = [c["id"] for c in data["never_enriched"]]
    assert test_competitor.id in never_ids


def test_data_health_non_admin_403(client, auth_headers):
    """Non-admin gets 403 on data-health."""
    resp = client.get("/api/admin/data-health", headers=auth_headers)
    assert resp.status_code == 403
