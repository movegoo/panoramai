"""MCP API key management: generate, view, revoke."""
import os
import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import get_db, User

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
    # Update via direct query to avoid detached instance issues
    db.query(User).filter(User.id == user.id).update({"mcp_api_key": key})
    db.commit()
    return {
        "api_key": key,
        "message": "Cle API MCP generee avec succes",
    }


@router.get("/keys")
def get_mcp_key(
    user: User = Depends(get_current_user),
):
    """Return masked key + Claude Desktop config JSON."""
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


@router.get("/keys/debug")
def debug_mcp_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Debug: check if key is stored and findable."""
    from database import SessionLocal
    # Check via same path as MCPAuthMiddleware
    direct_db = SessionLocal()
    try:
        stored_key = user.mcp_api_key
        found = direct_db.query(User).filter(
            User.mcp_api_key == stored_key,
            User.is_active == True,
        ).first()
        # Also count how many users have any key at all
        any_keys = direct_db.query(User).filter(
            User.mcp_api_key.isnot(None),
        ).count()
        return {
            "user_id": user.id,
            "has_key": bool(stored_key),
            "key_prefix": stored_key[:12] + "..." if stored_key else None,
            "key_length": len(stored_key) if stored_key else 0,
            "findable_by_middleware": found is not None,
            "found_user_id": found.id if found else None,
            "users_with_any_key": any_keys,
        }
    finally:
        direct_db.close()


@router.get("/keys/check/{api_key}")
def check_mcp_key(api_key: str):
    """Public debug: check if a specific key exists in DB (no auth required)."""
    from database import SessionLocal
    direct_db = SessionLocal()
    try:
        user = direct_db.query(User).filter(
            User.mcp_api_key == api_key,
            User.is_active == True,
        ).first()
        # Also check without is_active filter
        user_any = direct_db.query(User).filter(
            User.mcp_api_key == api_key,
        ).first()
        return {
            "key_found_active": user is not None,
            "key_found_any": user_any is not None,
            "user_id": user.id if user else (user_any.id if user_any else None),
            "is_active": user_any.is_active if user_any else None,
        }
    finally:
        direct_db.close()


@router.delete("/keys")
def revoke_mcp_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the MCP API key."""
    user.mcp_api_key = None
    db.commit()
    return {"message": "Cle API MCP revoquee"}
