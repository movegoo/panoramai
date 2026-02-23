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


@router.get("/keys/diag")
def diag_mcp_keys():
    """Temporary diagnostic: check all MCP keys in DB (no auth, remove after fix)."""
    db = SessionLocal()
    try:
        users_with_keys = db.query(
            User.id, User.email, User.mcp_api_key, User.is_active,
        ).filter(User.mcp_api_key.isnot(None)).all()

        all_users = db.query(User.id, User.email, User.is_active).all()

        return {
            "total_users": len(all_users),
            "users_with_keys": [
                {
                    "user_id": u.id,
                    "email": u.email,
                    "key_prefix": u.mcp_api_key[:12] + "..." if u.mcp_api_key else None,
                    "key_length": len(u.mcp_api_key) if u.mcp_api_key else 0,
                    "is_active": u.is_active,
                }
                for u in users_with_keys
            ],
            "all_user_ids": [u.id for u in all_users],
        }
    finally:
        db.close()


@router.get("/keys/diag/check/{api_key}")
def diag_check_key(api_key: str):
    """Temporary diagnostic: check specific key lookup (same as middleware)."""
    db = SessionLocal()
    try:
        # Exact same query as MCPAuthMiddleware
        user = db.query(User).filter(
            User.mcp_api_key == api_key,
            User.is_active == True,
        ).first()

        # Also try without is_active filter
        user_any = db.query(User).filter(
            User.mcp_api_key == api_key,
        ).first()

        # Check column exists
        from sqlalchemy import text, inspect
        inspector = inspect(db.bind)
        columns = [c["name"] for c in inspector.get_columns("users")]

        return {
            "key_found_active": user is not None,
            "key_found_any": user_any is not None,
            "user_id": user.id if user else (user_any.id if user_any else None),
            "is_active": user_any.is_active if user_any else None,
            "mcp_api_key_column_exists": "mcp_api_key" in columns,
            "users_table_columns": columns,
        }
    finally:
        db.close()


@router.post("/keys/diag/raw-test")
def diag_raw_test():
    """Temporary: test raw SQL write+read to confirm PostgreSQL persistence."""
    from sqlalchemy import text
    from database import engine
    steps = []

    # Step 1: Read current state of all users' mcp_api_key
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, email, mcp_api_key FROM users")).fetchall()
        steps.append({
            "step": "initial_read",
            "users": [{"id": r[0], "email": r[1], "has_key": r[2] is not None, "key_prefix": r[2][:12] + "..." if r[2] else None} for r in rows],
        })

    # Step 2: Write a test key to user id=15 using raw SQL with autocommit
    test_key = f"pnrm_{secrets.token_hex(16)}"
    with engine.begin() as conn:  # engine.begin() auto-commits
        result = conn.execute(
            text("UPDATE users SET mcp_api_key = :key WHERE id = 15"),
            {"key": test_key},
        )
        steps.append({
            "step": "raw_update",
            "rowcount": result.rowcount,
            "test_key_prefix": test_key[:12] + "...",
        })

    # Step 3: Read back with fresh connection
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, mcp_api_key FROM users WHERE id = 15"),
        ).fetchone()
        saved_key = row[1] if row else None
        steps.append({
            "step": "read_back",
            "found": saved_key is not None,
            "match": saved_key == test_key,
            "saved_prefix": saved_key[:12] + "..." if saved_key else None,
        })

    # Step 4: Also verify via ORM SessionLocal
    verify_db = SessionLocal()
    try:
        user = verify_db.query(User).filter(User.id == 15).first()
        orm_key = user.mcp_api_key if user else None
        steps.append({
            "step": "orm_verify",
            "found": orm_key is not None,
            "match": orm_key == test_key,
        })
    finally:
        verify_db.close()

    return {"test_key": test_key, "steps": steps}


@router.delete("/keys")
def revoke_mcp_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the MCP API key."""
    user.mcp_api_key = None
    db.commit()
    return {"message": "Cle API MCP revoquee"}
