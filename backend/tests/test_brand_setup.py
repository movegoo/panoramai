"""Tests for brand setup onboarding endpoint (duplicate handling)."""
from unittest.mock import patch, AsyncMock
from database import Advertiser, UserAdvertiser


def test_setup_brand_new(client, db, test_user):
    """Setup creates a new brand when none exists."""
    user, token = test_user
    headers = {"Authorization": f"Bearer {token}"}

    with patch("routers.brand._sync_brand_competitor", return_value=None):
        resp = client.post("/api/brand/setup", headers=headers, json={
            "company_name": "Leroy Merlin",
            "sector": "bricolage",
            "website": "https://www.leroymerlin.fr",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["brand"]["company_name"] == "Leroy Merlin"
    assert data["brand"]["sector"] == "bricolage"
    assert "suggested_competitors" in data

    # Verify user-advertiser link was created as owner
    link = db.query(UserAdvertiser).filter(
        UserAdvertiser.user_id == user.id,
        UserAdvertiser.advertiser_id == data["brand"]["id"],
    ).first()
    assert link is not None
    assert link.role == "owner"


def test_setup_brand_reuses_existing_global(client, db, test_user, second_user):
    """Setup reuses an existing advertiser created by another user."""
    user1, token1 = test_user
    user2, token2 = second_user

    # User 1 creates the brand
    with patch("routers.brand._sync_brand_competitor", return_value=None):
        resp1 = client.post("/api/brand/setup", headers={"Authorization": f"Bearer {token1}"}, json={
            "company_name": "Castorama",
            "sector": "bricolage",
        })
    assert resp1.status_code == 200
    brand_id = resp1.json()["brand"]["id"]

    # User 2 tries to create the same brand name
    with patch("routers.brand._sync_brand_competitor", return_value=None):
        resp2 = client.post("/api/brand/setup", headers={"Authorization": f"Bearer {token2}"}, json={
            "company_name": "Castorama",
            "sector": "bricolage",
        })
    assert resp2.status_code == 200
    # Should reuse the same advertiser
    assert resp2.json()["brand"]["id"] == brand_id

    # User 2 should be linked as member
    link = db.query(UserAdvertiser).filter(
        UserAdvertiser.user_id == user2.id,
        UserAdvertiser.advertiser_id == brand_id,
    ).first()
    assert link is not None
    assert link.role == "member"


def test_setup_brand_already_linked_returns_400(client, db, test_user):
    """Setup returns 400 if the user already has this brand linked."""
    user, token = test_user
    headers = {"Authorization": f"Bearer {token}"}

    with patch("routers.brand._sync_brand_competitor", return_value=None):
        resp1 = client.post("/api/brand/setup", headers=headers, json={
            "company_name": "Brico Depot",
            "sector": "bricolage",
        })
    assert resp1.status_code == 200

    # Same user tries again with same name
    resp2 = client.post("/api/brand/setup", headers=headers, json={
        "company_name": "Brico Depot",
        "sector": "bricolage",
    })
    assert resp2.status_code == 400
    assert "déjà configurée" in resp2.json()["detail"]


def test_setup_brand_case_insensitive(client, db, test_user, second_user):
    """Duplicate detection is case-insensitive."""
    _, token1 = test_user
    _, token2 = second_user

    with patch("routers.brand._sync_brand_competitor", return_value=None):
        resp1 = client.post("/api/brand/setup", headers={"Authorization": f"Bearer {token1}"}, json={
            "company_name": "Leroy Merlin",
            "sector": "bricolage",
        })
    assert resp1.status_code == 200
    brand_id = resp1.json()["brand"]["id"]

    # Different case → should still reuse
    with patch("routers.brand._sync_brand_competitor", return_value=None):
        resp2 = client.post("/api/brand/setup", headers={"Authorization": f"Bearer {token2}"}, json={
            "company_name": "leroy merlin",
            "sector": "bricolage",
        })
    assert resp2.status_code == 200
    assert resp2.json()["brand"]["id"] == brand_id


def test_setup_brand_invalid_sector(client, test_user):
    """Setup returns 400 for invalid sector."""
    _, token = test_user
    resp = client.post("/api/brand/setup", headers={"Authorization": f"Bearer {token}"}, json={
        "company_name": "Test",
        "sector": "invalid_sector",
    })
    assert resp.status_code == 400
    assert "Secteur invalide" in resp.json()["detail"]
