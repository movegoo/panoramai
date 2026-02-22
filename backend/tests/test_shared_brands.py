"""Tests for shared brands base (anti-duplication)."""
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from database import Competitor, AdvertiserCompetitor, UserAdvertiser, Advertiser, InstagramData


def test_find_brand_in_sectors():
    """find_brand_in_sectors finds known brands case-insensitively."""
    from core.sectors import find_brand_in_sectors
    result = find_brand_in_sectors("carrefour")
    assert result is not None
    assert result["name"] == "Carrefour"
    assert "sector" in result

    result2 = find_brand_in_sectors("CARREFOUR")
    assert result2 is not None

    assert find_brand_in_sectors("nonexistent_brand_xyz") is None


def test_reuse_existing_competitor(client, db, auth_headers, test_advertiser, test_competitor):
    """Creating a competitor that already exists reuses the same row."""
    with patch("routers.competitors._auto_enrich_competitor", new_callable=AsyncMock, return_value={}):
        # Create a second advertiser + user to simulate another user
        adv2 = Advertiser(company_name="Brand2", sector="supermarche", is_active=True)
        db.add(adv2)
        db.flush()

        from core.auth import hash_password, create_access_token
        from database import User
        user2 = User(email="user2@test.com", name="User2", password_hash=hash_password("pass"))
        db.add(user2)
        db.flush()
        db.add(UserAdvertiser(user_id=user2.id, advertiser_id=adv2.id, role="owner"))
        db.commit()

        token2 = create_access_token(user2.id)
        headers2 = {"Authorization": f"Bearer {token2}", "X-Advertiser-Id": str(adv2.id)}

        # Create same competitor name for second user
        resp = client.post("/api/competitors/", headers=headers2, json={"name": "Carrefour"})
        assert resp.status_code == 200

        # Should reuse the same competitor id
        assert resp.json()["id"] == test_competitor.id

        # Both advertisers should be linked
        links = db.query(AdvertiserCompetitor).filter(AdvertiserCompetitor.competitor_id == test_competitor.id).count()
        assert links == 2


def test_skip_enrichment_if_fresh(client, db, auth_headers, test_advertiser, test_competitor):
    """Enrichment is skipped if data is recent (< 24h)."""
    # Add recent Instagram data
    db.add(InstagramData(
        competitor_id=test_competitor.id,
        followers=1000, following=100, posts_count=50,
        recorded_at=datetime.utcnow(),
    ))
    db.commit()

    # Create second advertiser
    adv2 = Advertiser(company_name="Brand3", sector="supermarche", is_active=True)
    db.add(adv2)
    db.flush()

    from core.auth import hash_password, create_access_token
    from database import User
    user2 = User(email="user3@test.com", name="User3", password_hash=hash_password("pass"))
    db.add(user2)
    db.flush()
    db.add(UserAdvertiser(user_id=user2.id, advertiser_id=adv2.id, role="owner"))
    db.commit()

    token2 = create_access_token(user2.id)
    headers2 = {"Authorization": f"Bearer {token2}", "X-Advertiser-Id": str(adv2.id)}

    with patch("routers.competitors._auto_enrich_competitor", new_callable=AsyncMock, return_value={}) as mock_enrich:
        resp = client.post("/api/competitors/", headers=headers2, json={"name": "Carrefour"})
        assert resp.status_code == 200
        # Enrichment should NOT have been called (data is fresh)
        mock_enrich.assert_not_called()


def test_sectors_complement_fields(client, db, auth_headers, test_advertiser):
    """New competitor gets fields complemented from sectors database."""
    with patch("routers.competitors._auto_enrich_competitor", new_callable=AsyncMock, return_value={}):
        resp = client.post(
            "/api/competitors/",
            headers={**auth_headers, "X-Advertiser-Id": str(test_advertiser.id)},
            json={"name": "Lidl"},  # Known in sectors DB
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should have been complemented from sectors
        assert data.get("playstore_app_id") == "com.lidl.eci.lidlplus"
        assert data.get("instagram_username") is not None
