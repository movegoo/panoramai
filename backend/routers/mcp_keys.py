"""MCP API key management: generate, view, revoke."""
import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import get_db, User, SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()

MCP_BASE_URL = os.getenv(
    "MCP_BASE_URL",
    "https://panoramai-api.onrender.com",
)


@router.post("/keys/generate")
def generate_mcp_key(
    user: User = Depends(get_current_user),
):
    """Generate (or regenerate) an MCP API key for the current user."""
    from sqlalchemy import text
    from database import engine

    key = f"pnrm_{secrets.token_hex(16)}"

    # Use engine.begin() for guaranteed auto-commit (ORM db.commit() doesn't
    # persist reliably on Render PostgreSQL for unknown reasons)
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE users SET mcp_api_key = :key WHERE id = :uid"),
            {"key": key, "uid": user.id},
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=500, detail="Erreur: utilisateur non trouve")

    # Verify with fresh session
    verify_db = SessionLocal()
    try:
        found = verify_db.query(User).filter(
            User.mcp_api_key == key,
            User.is_active == True,
        ).first()
        verified = found is not None
    finally:
        verify_db.close()

    if not verified:
        logger.error(f"MCP key NOT persisted for user {user.id} after engine.begin()")
        raise HTTPException(
            status_code=500,
            detail="Erreur: la cle n'a pas ete persistee en base",
        )

    logger.info(f"MCP key generated and verified for user {user.id}: {key[:12]}...")

    # Clear middleware cache so new key is picked up
    from core.mcp_auth import _key_contexts
    _key_contexts.clear()

    return {
        "api_key": key,
        "verified": True,
        "message": "Cle API MCP generee avec succes",
    }


@router.get("/keys")
def get_mcp_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return masked key + Claude Desktop config JSON."""
    # Refresh from DB to get latest value
    db.refresh(user)

    if not user.mcp_api_key:
        return {"has_key": False, "api_key_masked": None, "claude_config": None}

    key = user.mcp_api_key
    masked = f"{key[:9]}...{key[-4:]}"  # pnrm_xxxx...yyyy

    return {
        "has_key": True,
        "api_key_masked": masked,
        "claude_config": {
            "mcpServers": {
                "panoramai": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "mcp-remote",
                        f"{MCP_BASE_URL}/mcp/sse?api_key={key}",
                    ],
                }
            }
        },
    }


@router.post("/keys/force-generate")
def force_generate_mcp_key(
    user_id: int,
):
    """Admin: force-generate an MCP key for a user (no auth, remove after use)."""
    from sqlalchemy import text
    from database import engine

    key = f"pnrm_{secrets.token_hex(16)}"

    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE users SET mcp_api_key = :key WHERE id = :uid"),
            {"key": key, "uid": user_id},
        )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Verify
    verify_db = SessionLocal()
    try:
        found = verify_db.query(User).filter(User.mcp_api_key == key).first()
        verified = found is not None
    finally:
        verify_db.close()

    # Clear cache
    from core.mcp_auth import _key_contexts
    _key_contexts.clear()

    return {
        "api_key": key,
        "user_id": user_id,
        "verified": verified,
    }


@router.get("/keys/diag")
def diag_mcp_keys():
    """Temporary diagnostic: check all data for all users (remove after fix)."""
    from database import UserAdvertiser, AdvertiserCompetitor, Competitor, Advertiser
    from core.permissions import get_advertiser_competitor_ids

    db = SessionLocal()
    try:
        all_users = db.query(User).all()

        users_detail = []
        for u in all_users:
            user_advs = db.query(UserAdvertiser).filter(
                UserAdvertiser.user_id == u.id,
            ).order_by(UserAdvertiser.id).all()

            advs_info = []
            all_comp_ids = set()
            for ua in user_advs:
                adv = db.query(Advertiser).filter(Advertiser.id == ua.advertiser_id).first()
                cids = get_advertiser_competitor_ids(db, ua.advertiser_id)
                all_comp_ids.update(cids)
                advs_info.append({
                    "id": ua.advertiser_id,
                    "name": adv.company_name if adv else None,
                    "is_active": adv.is_active if adv else None,
                    "competitor_count": len(cids),
                    "competitor_ids": cids,
                })

            all_comp_ids = list(all_comp_ids)
            comps = db.query(Competitor).filter(Competitor.id.in_(all_comp_ids)).all() if all_comp_ids else []

            users_detail.append({
                "user_id": u.id,
                "email": u.email,
                "has_mcp_key": u.mcp_api_key is not None,
                "key_prefix": u.mcp_api_key[:12] + "..." if u.mcp_api_key else None,
                "is_active": u.is_active,
                "advertiser_count": len(user_advs),
                "advertisers": advs_info,
                "total_competitor_ids": all_comp_ids,
                "competitors": [{"id": c.id, "name": c.name} for c in comps],
            })

        # Dump all tables for debugging
        all_advs = db.query(Advertiser).all()
        all_ua = db.query(UserAdvertiser).all()
        all_ac = db.query(AdvertiserCompetitor).all()
        all_comps = db.query(Competitor).filter(Competitor.is_active == True).all()

        return {
            "total_users": len(all_users),
            "users": users_detail,
            "all_advertisers": [
                {"id": a.id, "name": a.company_name, "user_id": a.user_id, "is_active": a.is_active}
                for a in all_advs
            ],
            "all_competitors": [
                {"id": c.id, "name": c.name, "user_id": c.user_id, "advertiser_id": c.advertiser_id, "is_brand": c.is_brand}
                for c in all_comps
            ],
            "all_user_advertisers": [
                {"id": ua.id, "user_id": ua.user_id, "advertiser_id": ua.advertiser_id, "role": ua.role}
                for ua in all_ua
            ],
            "all_advertiser_competitors": [
                {"advertiser_id": ac.advertiser_id, "competitor_id": ac.competitor_id, "is_brand": ac.is_brand}
                for ac in all_ac
            ],
        }
    finally:
        db.close()


@router.delete("/keys")
def revoke_mcp_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the MCP API key."""
    user.mcp_api_key = None
    db.commit()
    return {"message": "Cle API MCP revoquee"}
