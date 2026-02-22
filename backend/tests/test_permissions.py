"""Tests for core/permissions.py — advertiser-scoped access control."""
import pytest
from database import Advertiser, Competitor, UserAdvertiser, AdvertiserCompetitor, User
from core.auth import hash_password
from core.permissions import (
    verify_advertiser_access,
    get_advertiser_competitor_ids,
    get_advertiser_competitors,
    verify_competitor_access,
    verify_competitor_ownership,
    get_user_competitors,
    get_user_competitor_ids,
    parse_advertiser_header,
)
from fastapi import HTTPException


class TestVerifyAdvertiserAccess:
    def test_ok(self, db, test_user, test_advertiser):
        user, _ = test_user
        result = verify_advertiser_access(db, test_advertiser.id, user)
        assert result.id == test_advertiser.id

    def test_no_link(self, db, test_advertiser, second_user):
        other_user, _ = second_user
        with pytest.raises(HTTPException) as exc_info:
            verify_advertiser_access(db, test_advertiser.id, other_user)
        assert exc_info.value.status_code == 403

    def test_inactive_advertiser(self, db, test_user):
        user, _ = test_user
        adv = Advertiser(company_name="Inactive", is_active=False)
        db.add(adv)
        db.commit()
        db.refresh(adv)
        link = UserAdvertiser(user_id=user.id, advertiser_id=adv.id)
        db.add(link)
        db.commit()
        with pytest.raises(HTTPException) as exc_info:
            verify_advertiser_access(db, adv.id, user)
        assert exc_info.value.status_code == 404


class TestGetAdvertiserCompetitorIds:
    def test_returns_linked_ids(self, db, test_advertiser, test_competitor):
        ids = get_advertiser_competitor_ids(db, test_advertiser.id)
        assert test_competitor.id in ids

    def test_excludes_inactive(self, db, test_advertiser):
        comp = Competitor(name="Dead", is_active=False)
        db.add(comp)
        db.commit()
        db.refresh(comp)
        link = AdvertiserCompetitor(advertiser_id=test_advertiser.id, competitor_id=comp.id)
        db.add(link)
        db.commit()
        ids = get_advertiser_competitor_ids(db, test_advertiser.id)
        assert comp.id not in ids


class TestGetAdvertiserCompetitors:
    def test_returns_objects(self, db, test_advertiser, test_competitor):
        comps = get_advertiser_competitors(db, test_advertiser.id)
        assert len(comps) == 1
        assert comps[0].name == "Carrefour"


class TestVerifyCompetitorAccess:
    def test_ok(self, db, test_advertiser, test_competitor):
        result = verify_competitor_access(db, test_competitor.id, test_advertiser.id)
        assert result.id == test_competitor.id

    def test_no_link(self, db, test_advertiser):
        comp = Competitor(name="Unlinked", is_active=True)
        db.add(comp)
        db.commit()
        db.refresh(comp)
        with pytest.raises(HTTPException) as exc_info:
            verify_competitor_access(db, comp.id, test_advertiser.id)
        assert exc_info.value.status_code == 404


class TestVerifyCompetitorOwnership:
    def test_with_adv_id(self, db, test_user, test_advertiser, test_competitor):
        user, _ = test_user
        result = verify_competitor_ownership(db, test_competitor.id, user, advertiser_id=test_advertiser.id)
        assert result.id == test_competitor.id

    def test_without_adv_id(self, db, test_user, test_advertiser, test_competitor):
        user, _ = test_user
        result = verify_competitor_ownership(db, test_competitor.id, user)
        assert result.id == test_competitor.id

    def test_no_access(self, db, second_user, test_competitor):
        other_user, _ = second_user
        with pytest.raises(HTTPException) as exc_info:
            verify_competitor_ownership(db, test_competitor.id, other_user)
        assert exc_info.value.status_code == 404


class TestGetUserCompetitors:
    def test_with_adv_id(self, db, test_user, test_advertiser, test_competitor):
        user, _ = test_user
        comps = get_user_competitors(db, user, advertiser_id=test_advertiser.id)
        assert len(comps) == 1
        assert comps[0].name == "Carrefour"

    def test_without_adv_id(self, db, test_user, test_advertiser, test_competitor):
        user, _ = test_user
        comps = get_user_competitors(db, user)
        assert len(comps) == 1

    def test_no_advertisers(self, db, second_user):
        other_user, _ = second_user
        comps = get_user_competitors(db, other_user)
        assert comps == []


class TestGetUserCompetitorIds:
    def test_returns_ids(self, db, test_user, test_advertiser, test_competitor):
        user, _ = test_user
        ids = get_user_competitor_ids(db, user)
        assert test_competitor.id in ids

    def test_no_advertisers(self, db, second_user):
        other_user, _ = second_user
        ids = get_user_competitor_ids(db, other_user)
        assert ids == []


class TestParseAdvertiserHeader:
    def test_valid(self):
        assert parse_advertiser_header("5") == 5

    def test_none(self):
        assert parse_advertiser_header(None) is None

    def test_invalid(self):
        assert parse_advertiser_header("abc") is None
