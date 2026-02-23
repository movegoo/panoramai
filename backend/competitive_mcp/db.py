"""Connexion DB et import des modèles SQLAlchemy du backend."""
import os
import sys

# Ajouter le backend au path pour importer les modèles
_backend_dir = os.environ.get(
    "COMPETITIVE_BACKEND_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "backend"),
)
_backend_dir = os.path.abspath(_backend_dir)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import des modèles backend
from database import (  # noqa: E402
    Competitor,
    Ad,
    InstagramData,
    TikTokData,
    YouTubeData,
    SnapchatData,
    AppData,
    StoreLocation,
    SerpResult,
    GeoResult,
    Signal,
    SocialPost,
    AdSnapshot,
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./competitive.db",
)

# SQLite needs check_same_thread=False
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """Crée une session DB. À utiliser avec un context manager."""
    return SessionLocal()


def get_scoped_competitor_ids() -> list[int] | None:
    """Return competitor IDs from MCP SSE context, or None if running in stdio mode."""
    try:
        from core.mcp_context import mcp_user_context
        ctx = mcp_user_context.get(None)
        return ctx.competitor_ids if ctx else None
    except ImportError:
        return None  # stdio mode — no scoping


def find_competitor(db, name: str):
    """Recherche un concurrent par nom (insensible à la casse, fuzzy)."""
    scoped_ids = get_scoped_competitor_ids()

    # Exact match (case-insensitive)
    query = db.query(Competitor).filter(
        Competitor.is_active == True,
        Competitor.name.ilike(name),
    )
    if scoped_ids is not None:
        query = query.filter(Competitor.id.in_(scoped_ids))
    comp = query.first()
    if comp:
        return comp

    # Partial match
    query = db.query(Competitor).filter(
        Competitor.is_active == True,
        Competitor.name.ilike(f"%{name}%"),
    )
    if scoped_ids is not None:
        query = query.filter(Competitor.id.in_(scoped_ids))
    return query.first()


def get_all_competitors(db, include_brand: bool = True):
    """Retourne tous les concurrents actifs."""
    scoped_ids = get_scoped_competitor_ids()

    query = db.query(Competitor).filter(Competitor.is_active == True)
    if not include_brand:
        query = query.filter(Competitor.is_brand == False)
    if scoped_ids is not None:
        query = query.filter(Competitor.id.in_(scoped_ids))
    return query.all()
