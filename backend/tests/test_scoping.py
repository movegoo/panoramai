"""Integration tests for cross-user isolation and data sharing."""
from database import Advertiser, Competitor, UserAdvertiser, AdvertiserCompetitor
from core.auth import create_access_token


class TestUserIsolation:
    def test_user_sees_only_own_competitors(self, client, db, test_user, second_user):
        """User A can't see User B's competitors."""
        user_a, _ = test_user
        user_b, token_b = second_user

        # User A: advertiser + competitor
        adv_a = Advertiser(company_name="Brand A", is_active=True)
        db.add(adv_a)
        db.commit()
        db.refresh(adv_a)
        db.add(UserAdvertiser(user_id=user_a.id, advertiser_id=adv_a.id))
        comp_a = Competitor(name="Comp A", is_active=True)
        db.add(comp_a)
        db.commit()
        db.refresh(comp_a)
        db.add(AdvertiserCompetitor(advertiser_id=adv_a.id, competitor_id=comp_a.id))

        # User B: advertiser + competitor
        adv_b = Advertiser(company_name="Brand B", is_active=True)
        db.add(adv_b)
        db.commit()
        db.refresh(adv_b)
        db.add(UserAdvertiser(user_id=user_b.id, advertiser_id=adv_b.id))
        comp_b = Competitor(name="Comp B", is_active=True)
        db.add(comp_b)
        db.commit()
        db.refresh(comp_b)
        db.add(AdvertiserCompetitor(advertiser_id=adv_b.id, competitor_id=comp_b.id))
        db.commit()

        # User B sees only their competitor
        headers_b = {
            "Authorization": f"Bearer {token_b}",
            "X-Advertiser-Id": str(adv_b.id),
        }
        resp = client.get("/api/competitors/", headers=headers_b)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "Comp B" in names
        assert "Comp A" not in names

    def test_shared_competitor_visible_to_both(self, client, db, test_user, second_user):
        """Same competitor linked to 2 advertisers → both see it."""
        user_a, token_a = test_user
        user_b, token_b = second_user

        adv_a = Advertiser(company_name="Brand A", is_active=True)
        adv_b = Advertiser(company_name="Brand B", is_active=True)
        db.add_all([adv_a, adv_b])
        db.commit()
        db.refresh(adv_a)
        db.refresh(adv_b)
        db.add(UserAdvertiser(user_id=user_a.id, advertiser_id=adv_a.id))
        db.add(UserAdvertiser(user_id=user_b.id, advertiser_id=adv_b.id))

        shared = Competitor(name="SharedComp", is_active=True)
        db.add(shared)
        db.commit()
        db.refresh(shared)
        db.add(AdvertiserCompetitor(advertiser_id=adv_a.id, competitor_id=shared.id))
        db.add(AdvertiserCompetitor(advertiser_id=adv_b.id, competitor_id=shared.id))
        db.commit()

        # User A sees it
        headers_a = {
            "Authorization": f"Bearer {token_a}",
            "X-Advertiser-Id": str(adv_a.id),
        }
        resp_a = client.get("/api/competitors/", headers=headers_a)
        assert any(c["name"] == "SharedComp" for c in resp_a.json())

        # User B sees it too
        headers_b = {
            "Authorization": f"Bearer {token_b}",
            "X-Advertiser-Id": str(adv_b.id),
        }
        resp_b = client.get("/api/competitors/", headers=headers_b)
        assert any(c["name"] == "SharedComp" for c in resp_b.json())


class TestCompetitorDedup:
    def test_create_duplicate_name_blocked(self, client, adv_headers, test_competitor):
        """Creating same competitor name twice under same advertiser → 400."""
        resp = client.post(
            "/api/competitors/",
            json={"name": "Carrefour", "website": "https://carrefour.fr"},
            headers=adv_headers,
        )
        assert resp.status_code == 400
        assert "existe déjà" in resp.json()["detail"]


class TestDeleteCompetitor:
    def test_delete_removes_link_only(self, client, db, test_user, adv_headers, test_advertiser):
        """DELETE removes AdvertiserCompetitor link; competitor stays if other links exist."""
        user, _ = test_user

        comp = Competitor(name="MultiLinked", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        # Link to test_advertiser
        db.add(AdvertiserCompetitor(advertiser_id=test_advertiser.id, competitor_id=comp.id))
        # Link to another advertiser
        adv2 = Advertiser(company_name="Other Brand", is_active=True)
        db.add(adv2)
        db.commit()
        db.refresh(adv2)
        db.add(AdvertiserCompetitor(advertiser_id=adv2.id, competitor_id=comp.id))
        db.commit()

        resp = client.delete(f"/api/competitors/{comp.id}", headers=adv_headers)
        assert resp.status_code == 200

        # Competitor still active (linked to adv2)
        db.refresh(comp)
        assert comp.is_active is True

    def test_delete_soft_deletes_if_orphaned(self, client, db, adv_headers, test_advertiser):
        """DELETE soft-deletes competitor if no links remain."""
        comp = Competitor(name="Orphanable", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)
        db.add(AdvertiserCompetitor(advertiser_id=test_advertiser.id, competitor_id=comp.id))
        db.commit()

        resp = client.delete(f"/api/competitors/{comp.id}", headers=adv_headers)
        assert resp.status_code == 200

        db.refresh(comp)
        assert comp.is_active is False


class TestListAndGetScoping:
    def test_list_returns_only_linked(self, client, db, adv_headers, test_advertiser):
        """GET /competitors/ returns only linked competitors."""
        linked = Competitor(name="Linked", is_active=True)
        unlinked = Competitor(name="Unlinked", is_active=True)
        db.add_all([linked, unlinked])
        db.commit()
        db.refresh(linked)
        db.add(AdvertiserCompetitor(advertiser_id=test_advertiser.id, competitor_id=linked.id))
        db.commit()

        resp = client.get("/api/competitors/", headers=adv_headers)
        names = [c["name"] for c in resp.json()]
        assert "Linked" in names
        assert "Unlinked" not in names

    def test_get_competitor_not_linked_returns_404(self, client, db, adv_headers):
        """GET /competitors/{id} returns 404 for unlinked competitor."""
        comp = Competitor(name="NotMine", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)

        resp = client.get(f"/api/competitors/{comp.id}", headers=adv_headers)
        assert resp.status_code == 404
