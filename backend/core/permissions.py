"""
Centralized permission helpers for multi-tenant access control.
Advertiser-scoped via join tables (user_advertisers, advertiser_competitors).
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from database import Competitor, Advertiser, User, UserAdvertiser, AdvertiserCompetitor


def verify_advertiser_access(db: Session, advertiser_id: int, user: User) -> Advertiser:
    """Verify user has access to this advertiser via user_advertisers join table."""
    adv = db.query(Advertiser).filter(
        Advertiser.id == advertiser_id,
        Advertiser.is_active == True,
    ).first()
    if not adv:
        raise HTTPException(status_code=404, detail="Enseigne non trouvée")
    link = db.query(UserAdvertiser).filter(
        UserAdvertiser.user_id == user.id,
        UserAdvertiser.advertiser_id == advertiser_id,
    ).first()
    if not link:
        raise HTTPException(status_code=403, detail="Accès refusé à cet annonceur")
    return adv


def get_advertiser_competitor_ids(db: Session, advertiser_id: int) -> list[int]:
    """Return all active competitor IDs linked to this advertiser."""
    rows = (
        db.query(AdvertiserCompetitor.competitor_id)
        .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
        .filter(
            AdvertiserCompetitor.advertiser_id == advertiser_id,
            Competitor.is_active == True,
        )
        .all()
    )
    return [r[0] for r in rows]


def get_advertiser_competitors(db: Session, advertiser_id: int) -> list[Competitor]:
    """Return all active competitors linked to this advertiser."""
    return (
        db.query(Competitor)
        .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
        .filter(
            AdvertiserCompetitor.advertiser_id == advertiser_id,
            Competitor.is_active == True,
        )
        .all()
    )


def verify_competitor_access(db: Session, competitor_id: int, advertiser_id: int) -> Competitor:
    """Verify that competitor is linked to this advertiser."""
    comp = db.query(Competitor).filter(
        Competitor.id == competitor_id,
        Competitor.is_active == True,
    ).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")
    link = db.query(AdvertiserCompetitor).filter(
        AdvertiserCompetitor.advertiser_id == advertiser_id,
        AdvertiserCompetitor.competitor_id == competitor_id,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")
    return comp


# --- Backward-compatible aliases (used by many routers during transition) ---

def verify_competitor_ownership(
    db: Session,
    competitor_id: int,
    user: User,
    advertiser_id: int | None = None,
) -> Competitor:
    """Backward-compatible wrapper. Uses advertiser-scoped check if advertiser_id given,
    otherwise falls back to checking all user's advertisers."""
    if advertiser_id is not None:
        return verify_competitor_access(db, competitor_id, advertiser_id)
    # Check across all user's advertisers
    comp = db.query(Competitor).filter(
        Competitor.id == competitor_id,
        Competitor.is_active == True,
    ).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(
        UserAdvertiser.user_id == user.id
    ).all()]
    if not user_adv_ids:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")
    link = db.query(AdvertiserCompetitor).filter(
        AdvertiserCompetitor.competitor_id == competitor_id,
        AdvertiserCompetitor.advertiser_id.in_(user_adv_ids),
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")
    return comp


def get_user_competitors(
    db: Session,
    user: User,
    advertiser_id: int | None = None,
) -> list[Competitor]:
    """Backward-compatible: return competitors via join tables."""
    if advertiser_id is not None:
        return get_advertiser_competitors(db, advertiser_id)
    # All competitors across all user's advertisers
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(
        UserAdvertiser.user_id == user.id
    ).all()]
    if not user_adv_ids:
        return []
    return (
        db.query(Competitor)
        .join(AdvertiserCompetitor, AdvertiserCompetitor.competitor_id == Competitor.id)
        .filter(
            AdvertiserCompetitor.advertiser_id.in_(user_adv_ids),
            Competitor.is_active == True,
        )
        .distinct()
        .all()
    )


def get_user_competitor_ids(
    db: Session,
    user: User,
    advertiser_id: int | None = None,
) -> list[int]:
    """Backward-compatible: return competitor IDs via join tables."""
    if advertiser_id is not None:
        return get_advertiser_competitor_ids(db, advertiser_id)
    user_adv_ids = [r[0] for r in db.query(UserAdvertiser.advertiser_id).filter(
        UserAdvertiser.user_id == user.id
    ).all()]
    if not user_adv_ids:
        return []
    rows = (
        db.query(AdvertiserCompetitor.competitor_id)
        .join(Competitor, Competitor.id == AdvertiserCompetitor.competitor_id)
        .filter(
            AdvertiserCompetitor.advertiser_id.in_(user_adv_ids),
            Competitor.is_active == True,
        )
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def verify_advertiser_ownership(db: Session, advertiser_id: int, user: User) -> Advertiser:
    """Alias for verify_advertiser_access (backward compat)."""
    return verify_advertiser_access(db, advertiser_id, user)


def parse_advertiser_header(x_advertiser_id: str | None) -> int | None:
    """Parse X-Advertiser-Id header to int, or None."""
    if x_advertiser_id:
        try:
            return int(x_advertiser_id)
        except (ValueError, TypeError):
            pass
    return None
