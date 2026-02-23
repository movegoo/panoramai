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
                    "url": f"{MCP_BASE_URL}/mcp/sse?api_key={key}",
                }
            }
        },
    }


@router.delete("/keys")
def revoke_mcp_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the MCP API key."""
    user.mcp_api_key = None
    db.commit()
    return {"message": "Cle API MCP revoquee"}
