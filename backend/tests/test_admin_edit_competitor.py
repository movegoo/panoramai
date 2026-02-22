"""Tests for admin competitor editing."""


def test_admin_can_update_handles(client, db, auth_headers, test_competitor):
    """Admin can modify competitor handles."""
    from database import User
    user = db.query(User).first()
    user.is_admin = True
    db.commit()

    resp = client.put(
        f"/api/admin/competitors/{test_competitor.id}",
        headers=auth_headers,
        json={"instagram_username": "new_handle"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "instagram_username" in data["updated_fields"]
    assert data["competitor"]["instagram_username"] == "new_handle"


def test_admin_can_update_name(client, db, auth_headers, test_competitor):
    """Admin can modify competitor name."""
    from database import User
    user = db.query(User).first()
    user.is_admin = True
    db.commit()

    resp = client.put(
        f"/api/admin/competitors/{test_competitor.id}",
        headers=auth_headers,
        json={"name": "Carrefour Market"},
    )
    assert resp.status_code == 200
    assert resp.json()["competitor"]["name"] == "Carrefour Market"


def test_non_admin_gets_403(client, auth_headers, test_competitor):
    """Non-admin user gets 403."""
    resp = client.put(
        f"/api/admin/competitors/{test_competitor.id}",
        headers=auth_headers,
        json={"name": "Hack"},
    )
    assert resp.status_code == 403


def test_missing_competitor_gets_404(client, db, auth_headers):
    """Non-existent competitor returns 404."""
    from database import User
    user = db.query(User).first()
    user.is_admin = True
    db.commit()

    resp = client.put(
        "/api/admin/competitors/99999",
        headers=auth_headers,
        json={"name": "Ghost"},
    )
    assert resp.status_code == 404


def test_partial_update(client, db, auth_headers, test_competitor):
    """Only provided fields are updated."""
    from database import User
    user = db.query(User).first()
    user.is_admin = True
    db.commit()

    resp = client.put(
        f"/api/admin/competitors/{test_competitor.id}",
        headers=auth_headers,
        json={"tiktok_username": "carrefour_tk"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated_fields"] == ["tiktok_username"]
    # Name should be unchanged
    assert data["competitor"]["name"] == "Carrefour"
