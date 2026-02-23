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
    db: Session = Depends(get_db),
):
    """Generate (or regenerate) an MCP API key for the current user."""
    key = f"pnrm_{secrets.token_hex(16)}"

    # Use ORM assignment (same pattern as revoke_mcp_key)
    user.mcp_api_key = key
    db.commit()
    db.refresh(user)

    # Verify with a completely independent session
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
        logger.error(f"MCP key NOT persisted for user {user.id} after commit+refresh")
        raise HTTPException(
            status_code=500,
            detail="Erreur: la cle n'a pas ete persistee en base",
        )

    logger.info(f"MCP key generated and verified for user {user.id}: {key[:12]}...")

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


@router.get("/keys/diag")
def diag_mcp_keys():
    """Temporary diagnostic: check all MCP keys in DB (no auth, remove after fix)."""
    db = SessionLocal()
    try:
        users_with_keys = db.query(
            User.id, User.email, User.mcp_api_key, User.is_active,
        ).filter(User.mcp_api_key.isnot(None)).all()

        all_users = db.query(User.id, User.email, User.is_active).all()

        # Also get advertiser + competitor context for users with keys
        from database import UserAdvertiser, AdvertiserCompetitor, Competitor, Advertiser
        from core.permissions import get_advertiser_competitor_ids

        users_detail = []
        for u in users_with_keys:
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
                    "competitor_count": len(cids),
                })

            all_comp_ids = list(all_comp_ids)
            comps = db.query(Competitor).filter(Competitor.id.in_(all_comp_ids)).all() if all_comp_ids else []

            users_detail.append({
                "user_id": u.id,
                "email": u.email,
                "key_prefix": u.mcp_api_key[:12] + "..." if u.mcp_api_key else None,
                "is_active": u.is_active,
                "advertisers": advs_info,
                "total_competitor_ids": all_comp_ids,
                "competitors": [{"id": c.id, "name": c.name} for c in comps],
            })

        return {
            "total_users": len(all_users),
            "users_with_keys": users_detail,
            "all_user_ids": [u.id for u in all_users],
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
