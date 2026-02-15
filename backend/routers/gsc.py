"""
Google Search Console API endpoints.
OAuth flow + Search Analytics data.
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, GoogleOAuthToken
from core.config import settings
from core.auth import get_current_user, create_access_token, decode_token
from services import gsc

logger = logging.getLogger(__name__)
router = APIRouter()


class SelectSiteRequest(BaseModel):
    site_url: str


# ── OAuth Flow ──────────────────────────────────────────────────────────────


@router.get("/auth/url")
async def get_auth_url(user=Depends(get_current_user)):
    """Generate Google OAuth URL. State = JWT so we identify the user on callback."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(400, "GOOGLE_CLIENT_ID non configure")
    state = create_access_token(user.id)
    auth_url = gsc.generate_auth_url(state)
    return {"auth_url": auth_url}


@router.get("/auth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Google OAuth callback. Exchanges code for tokens and redirects to frontend."""
    # Decode state to get user_id
    try:
        payload = decode_token(state)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("No user_id in state")
    except Exception as e:
        logger.error(f"GSC callback: invalid state token: {e}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/account?gsc=error&reason=invalid_state")

    # Exchange code for tokens
    try:
        token_data = await gsc.exchange_code(code)
    except Exception as e:
        logger.error(f"GSC callback: token exchange failed: {e}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/account?gsc=error&reason=token_exchange")

    # Store tokens
    existing = db.query(GoogleOAuthToken).filter(GoogleOAuthToken.user_id == user_id).first()
    if existing:
        existing.access_token = token_data["access_token"]
        existing.refresh_token = token_data.get("refresh_token", existing.refresh_token)
        existing.token_expiry = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
        existing.scopes = token_data.get("scope", "")
        existing.updated_at = datetime.utcnow()
    else:
        new_token = GoogleOAuthToken(
            user_id=user_id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", ""),
            token_expiry=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600)),
            scopes=token_data.get("scope", ""),
            connected_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(new_token)
    db.commit()

    logger.info(f"GSC connected for user {user_id}")
    return RedirectResponse(f"{settings.FRONTEND_URL}/account?gsc=connected")


# ── Status & Configuration ──────────────────────────────────────────────────


@router.get("/status")
async def get_status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Check GSC connection status."""
    token_row = db.query(GoogleOAuthToken).filter(
        GoogleOAuthToken.user_id == user.id
    ).first()
    if not token_row:
        return {"connected": False, "selected_site": None}
    return {
        "connected": True,
        "selected_site": token_row.selected_site_url,
        "connected_at": token_row.connected_at.isoformat() if token_row.connected_at else None,
    }


@router.get("/sites")
async def list_sites(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """List available GSC properties."""
    try:
        sites = await gsc.list_sites(db, user.id)
        return {"sites": sites}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/select-site")
async def select_site(
    body: SelectSiteRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Select which GSC property to use."""
    token_row = db.query(GoogleOAuthToken).filter(
        GoogleOAuthToken.user_id == user.id
    ).first()
    if not token_row:
        raise HTTPException(400, "GSC non connecte")
    token_row.selected_site_url = body.site_url
    token_row.updated_at = datetime.utcnow()
    db.commit()
    return {"selected_site": body.site_url}


@router.post("/disconnect")
async def disconnect(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove GSC connection."""
    token_row = db.query(GoogleOAuthToken).filter(
        GoogleOAuthToken.user_id == user.id
    ).first()
    if token_row:
        db.delete(token_row)
        db.commit()
    return {"disconnected": True}


# ── Data Endpoints ──────────────────────────────────────────────────────────


@router.get("/performance")
async def get_performance(
    period: str = Query("28d", regex="^(7d|28d|3m)$"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get performance overview: KPIs + daily chart data."""
    token_row = db.query(GoogleOAuthToken).filter(
        GoogleOAuthToken.user_id == user.id
    ).first()
    if not token_row or not token_row.selected_site_url:
        raise HTTPException(400, "Selectionnez d'abord une propriete GSC")
    try:
        return await gsc.get_performance_overview(db, user.id, token_row.selected_site_url, period)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"GSC performance error: {e}")
        raise HTTPException(500, f"Erreur GSC: {e}")


@router.get("/queries")
async def get_queries(
    period: str = Query("28d", regex="^(7d|28d|3m)$"),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get top queries by clicks."""
    token_row = db.query(GoogleOAuthToken).filter(
        GoogleOAuthToken.user_id == user.id
    ).first()
    if not token_row or not token_row.selected_site_url:
        raise HTTPException(400, "Selectionnez d'abord une propriete GSC")
    try:
        queries = await gsc.get_top_queries(db, user.id, token_row.selected_site_url, period, limit)
        return {"queries": queries, "period": period}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"GSC queries error: {e}")
        raise HTTPException(500, f"Erreur GSC: {e}")


@router.get("/pages")
async def get_pages(
    period: str = Query("28d", regex="^(7d|28d|3m)$"),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get top pages by clicks."""
    token_row = db.query(GoogleOAuthToken).filter(
        GoogleOAuthToken.user_id == user.id
    ).first()
    if not token_row or not token_row.selected_site_url:
        raise HTTPException(400, "Selectionnez d'abord une propriete GSC")
    try:
        pages = await gsc.get_top_pages(db, user.id, token_row.selected_site_url, period, limit)
        return {"pages": pages, "period": period}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"GSC pages error: {e}")
        raise HTTPException(500, f"Erreur GSC: {e}")
