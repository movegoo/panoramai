"""
Centralized permission helpers for multi-tenant access control.
Reused across ALL routers to enforce ownership checks.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from database import Competitor, Advertiser, User


def verify_competitor_ownership(db: Session, competitor_id: int, user: User) -> Competitor:
    """Verify that competitor_id belongs to the current user.

    Returns the Competitor if ownership checks pass.
    Raises 404 if not found or not owned by user.
    """
    comp = db.query(Competitor).filter(
        Competitor.id == competitor_id,
        Competitor.is_active == True,
    ).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")
    if comp.user_id and comp.user_id != user.id:
        raise HTTPException(status_code=404, detail="Concurrent non trouvé")
    return comp


def get_user_competitor_ids(db: Session, user: User) -> list[int]:
    """Return all active competitor IDs owned by user."""
    rows = db.query(Competitor.id).filter(
        Competitor.user_id == user.id,
        Competitor.is_active == True,
    ).all()
    return [r[0] for r in rows]


def get_user_competitors(
    db: Session,
    user: User,
    advertiser_id: int | None = None,
) -> list[Competitor]:
    """Return all active competitors for user, optionally filtered by advertiser_id."""
    from core.auth import claim_orphans
    claim_orphans(db, user)

    query = db.query(Competitor).filter(
        Competitor.user_id == user.id,
        Competitor.is_active == True,
    )
    if advertiser_id is not None:
        query = query.filter(Competitor.advertiser_id == advertiser_id)
    return query.all()


def verify_advertiser_ownership(db: Session, advertiser_id: int, user: User) -> Advertiser:
    """Verify that advertiser belongs to the current user."""
    adv = db.query(Advertiser).filter(
        Advertiser.id == advertiser_id,
        Advertiser.is_active == True,
    ).first()
    if not adv:
        raise HTTPException(status_code=404, detail="Enseigne non trouvée")
    if adv.user_id and adv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Enseigne non trouvée")
    return adv
