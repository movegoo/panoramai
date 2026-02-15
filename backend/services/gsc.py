"""
Google Search Console service.
Uses httpx to call Google APIs directly (no google-api-python-client needed).
"""
import httpx
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from core.config import settings
from database import GoogleOAuthToken

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GSC_API_BASE = "https://www.googleapis.com/webmasters/v3"
SCOPES = "https://www.googleapis.com/auth/webmasters.readonly"


def generate_auth_url(state: str) -> str:
    """Generate Google OAuth consent URL."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    """Exchange authorization code for tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "refresh_token": refresh_token,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        return resp.json()


async def _ensure_token(db: Session, user_id: int) -> str:
    """Get a valid access token, refreshing if expired."""
    token_row = db.query(GoogleOAuthToken).filter(
        GoogleOAuthToken.user_id == user_id
    ).first()
    if not token_row:
        raise ValueError("Google Search Console non connecte")

    # Check if token is expired (with 5min buffer)
    if token_row.token_expiry and token_row.token_expiry < datetime.utcnow() + timedelta(minutes=5):
        if not token_row.refresh_token:
            raise ValueError("Refresh token manquant, reconnectez GSC")
        try:
            data = await refresh_access_token(token_row.refresh_token)
            token_row.access_token = data["access_token"]
            token_row.token_expiry = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
            token_row.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Refreshed GSC token for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to refresh GSC token: {e}")
            raise ValueError("Impossible de rafraichir le token GSC, reconnectez-vous")

    return token_row.access_token


async def list_sites(db: Session, user_id: int) -> list[dict]:
    """List all GSC properties for the user."""
    access_token = await _ensure_token(db, user_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GSC_API_BASE}/sites",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
    return data.get("siteEntry", [])


async def get_search_analytics(
    db: Session,
    user_id: int,
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str],
    row_limit: int = 1000,
) -> list[dict]:
    """Query Search Analytics API."""
    access_token = await _ensure_token(db, user_id)
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": row_limit,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GSC_API_BASE}/sites/{site_url}/searchAnalytics/query",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
    return data.get("rows", [])


async def get_performance_overview(db: Session, user_id: int, site_url: str, period: str = "28d") -> dict:
    """Get KPIs + daily data for a period."""
    days = {"7d": 7, "28d": 28, "3m": 90}.get(period, 28)
    end = datetime.utcnow().date() - timedelta(days=2)  # GSC data has ~2 day lag
    start = end - timedelta(days=days)

    start_str = start.isoformat()
    end_str = end.isoformat()

    # Daily data
    daily_rows = await get_search_analytics(
        db, user_id, site_url, start_str, end_str, dimensions=["date"]
    )

    # Totals (no dimensions = aggregated)
    access_token = await _ensure_token(db, user_id)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GSC_API_BASE}/sites/{site_url}/searchAnalytics/query",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"startDate": start_str, "endDate": end_str},
        )
        resp.raise_for_status()
        totals = resp.json()

    total_clicks = 0
    total_impressions = 0
    avg_ctr = 0.0
    avg_position = 0.0
    if totals.get("rows"):
        row = totals["rows"][0]
        total_clicks = row.get("clicks", 0)
        total_impressions = row.get("impressions", 0)
        avg_ctr = row.get("ctr", 0)
        avg_position = row.get("position", 0)

    daily = []
    for r in daily_rows:
        daily.append({
            "date": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 1),
        })

    return {
        "period": period,
        "start_date": start_str,
        "end_date": end_str,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "avg_ctr": round(avg_ctr * 100, 2),
        "avg_position": round(avg_position, 1),
        "daily": sorted(daily, key=lambda x: x["date"]),
    }


async def get_top_queries(db: Session, user_id: int, site_url: str, period: str = "28d", limit: int = 20) -> list[dict]:
    """Get top queries by clicks."""
    days = {"7d": 7, "28d": 28, "3m": 90}.get(period, 28)
    end = datetime.utcnow().date() - timedelta(days=2)
    start = end - timedelta(days=days)

    rows = await get_search_analytics(
        db, user_id, site_url, start.isoformat(), end.isoformat(),
        dimensions=["query"], row_limit=limit,
    )

    return [
        {
            "query": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 1),
        }
        for r in rows
    ]


async def get_top_pages(db: Session, user_id: int, site_url: str, period: str = "28d", limit: int = 20) -> list[dict]:
    """Get top pages by clicks."""
    days = {"7d": 7, "28d": 28, "3m": 90}.get(period, 28)
    end = datetime.utcnow().date() - timedelta(days=2)
    start = end - timedelta(days=days)

    rows = await get_search_analytics(
        db, user_id, site_url, start.isoformat(), end.isoformat(),
        dimensions=["page"], row_limit=limit,
    )

    return [
        {
            "page": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 1),
        }
        for r in rows
    ]
