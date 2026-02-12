"""
Competitive Intelligence API
Pour une tête de réseau retail supervisant le digital de ses enseignes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import logging
from datetime import datetime

from database import init_db, engine, User, Advertiser, Competitor
from database import SessionLocal

import os
# Load .env from parent dir (local dev) or current dir (deployed)
load_dotenv(dotenv_path="../.env")
load_dotenv(dotenv_path=".env")

# Routers
from routers import auth, brand, watch, competitors, geo, layers, admin
from routers import facebook, playstore, appstore, instagram, tiktok, youtube
from services.scheduler import scheduler

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def _enrich_missing_stores():
    """Background: enrich competitors that have 0 BANCO store locations."""
    try:
        from database import SessionLocal, Competitor, StoreLocation
        from services.banco import banco_service
        from sqlalchemy import func

        db = SessionLocal()
        try:
            competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
            if not competitors:
                return

            # Find which competitors already have stores
            existing = dict(
                db.query(StoreLocation.competitor_id, func.count(StoreLocation.id))
                .filter(StoreLocation.source == "BANCO")
                .group_by(StoreLocation.competitor_id)
                .all()
            )

            missing = [c for c in competitors if existing.get(c.id, 0) == 0]
            if not missing:
                return

            logger.info(f"BANCO startup: enriching {len(missing)} competitors without stores")
            for comp in missing:
                try:
                    count = await banco_service.search_and_store(comp.id, comp.name, db)
                    logger.info(f"BANCO: {count} stores for '{comp.name}'")
                except Exception as e:
                    logger.error(f"BANCO enrich failed for '{comp.name}': {e}")

            # Free memory after enrichment
            banco_service._data = None
        finally:
            db.close()
    except Exception as e:
        logger.error(f"BANCO startup enrichment error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    init_db()
    logger.info("Database initialized")

    await scheduler.start()
    logger.info("Scheduler started")

    # BANCO enrichment disabled - exceeds Render free tier 512MB memory limit
    # import asyncio
    # asyncio.create_task(_enrich_missing_stores())

    yield

    await scheduler.stop()
    logger.info("Scheduler stopped")


app = FastAPI(
    title="Competitive Intelligence API",
    description="""
    API de veille concurrentielle pour les enseignes retail.

    ## Fonctionnalités

    - **Mon Enseigne** (`/api/brand`): Configuration de votre enseigne
    - **Veille** (`/api/watch`): Dashboard et alertes concurrentielles
    - **Concurrents** (`/api/competitors`): Gestion et analyse des concurrents
    - **Canaux** (`/api/playstore`, `/api/appstore`, etc.): Données par canal

    ## Getting Started

    1. Configurez votre enseigne: `POST /api/brand/setup`
    2. Ajoutez des concurrents: `POST /api/brand/suggestions/add`
    3. Lancez la collecte: `POST /api/playstore/fetch/{competitor_id}`
    4. Consultez le dashboard: `GET /api/watch/overview`
    """,
    version="2.0.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://panoramai-eight.vercel.app",
]
# Add custom origins from env
extra_origins = os.getenv("CORS_ORIGINS", "")
if extra_origins:
    ALLOWED_ORIGINS.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Routers
# =============================================================================

# Auth
app.include_router(auth.router, prefix="/api/auth", tags=["Authentification"])

# Admin
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

# Core (nouvelle architecture)
app.include_router(brand.router, prefix="/api/brand", tags=["Mon Enseigne"])
app.include_router(watch.router, prefix="/api/watch", tags=["Veille Concurrentielle"])
app.include_router(competitors.router, prefix="/api/competitors", tags=["Concurrents"])
app.include_router(geo.router, prefix="/api/geo", tags=["Géographie & Magasins"])
app.include_router(layers.router, tags=["Layers Cartographiques"])

# Canaux (data collection)
app.include_router(facebook.router, prefix="/api/facebook", tags=["Meta Ads"])
app.include_router(playstore.router, prefix="/api/playstore", tags=["Play Store"])
app.include_router(appstore.router, prefix="/api/appstore", tags=["App Store"])
app.include_router(instagram.router, prefix="/api/instagram", tags=["Instagram"])
app.include_router(tiktok.router, prefix="/api/tiktok", tags=["TikTok"])
app.include_router(youtube.router, prefix="/api/youtube", tags=["YouTube"])


# =============================================================================
# Root endpoints
# =============================================================================

@app.get("/")
async def root():
    """Point d'entrée de l'API."""
    db = SessionLocal()
    try:
        brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()
        competitors_count = db.query(Competitor).filter(Competitor.is_active == True).count()
    finally:
        db.close()

    return {
        "name": "Competitive Intelligence API",
        "version": "2.0.0",
        "brand_configured": brand is not None,
        "brand_name": brand.company_name if brand else None,
        "competitors_tracked": competitors_count,
        "endpoints": {
            "setup": "/api/brand/setup",
            "dashboard": "/api/watch/overview",
            "alerts": "/api/watch/alerts",
            "rankings": "/api/watch/rankings",
            "competitors": "/api/competitors",
            "stores": "/api/geo/stores",
            "zone_analysis": "/api/geo/zone/analyze",
            "map": "/api/geo/map/data",
            "retailers_db": "/api/geo/retailers",
        }
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    db = SessionLocal()
    try:
        brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()
        competitors_count = db.query(Competitor).filter(Competitor.is_active == True).count()
    finally:
        db.close()

    return {
        "status": "healthy",
        "version": "2.0.0",
        "brand_configured": brand is not None,
        "competitors_count": competitors_count,
        "scheduler_status": scheduler.get_status(),
    }


@app.get("/api/scheduler/status")
async def get_scheduler_status():
    """Statut du scheduler de collecte automatique."""
    return scheduler.get_status()


@app.get("/api/debug/db")
async def debug_db():
    """Debug database connectivity."""
    results = {"deploy_version": "v5-memfix"}
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            row = conn.execute(text("SELECT COUNT(*) FROM users")).fetchone()
            results["raw_user_count"] = row[0]
    except Exception as e:
        results["raw_error"] = str(e)

    try:
        db = SessionLocal()
        users = db.query(User).all()
        results["orm_user_count"] = len(users)
        db.close()
    except Exception as e:
        results["orm_error"] = str(e)
        try:
            db.close()
        except:
            pass

    return results


@app.get("/api/debug/auth-test")
async def debug_auth_test():
    """Test each step of registration to find the error."""
    results = {}

    # Step 1: Test bcrypt
    try:
        import bcrypt
        results["bcrypt_version"] = getattr(bcrypt, '__version__', 'unknown')
        pw_hash = bcrypt.hashpw(b"test123456", bcrypt.gensalt())
        results["bcrypt_hash"] = "OK"
        results["bcrypt_verify"] = bcrypt.checkpw(b"test123456", pw_hash)
    except Exception as e:
        results["bcrypt_error"] = f"{type(e).__name__}: {e}"

    # Step 2: Test hash_password from core.auth
    try:
        from core.auth import hash_password
        h = hash_password("test123456")
        results["hash_password"] = "OK"
        results["hash_result_type"] = type(h).__name__
    except Exception as e:
        results["hash_password_error"] = f"{type(e).__name__}: {e}"

    # Step 3: Test User creation (without commit)
    try:
        db = SessionLocal()
        user = User(
            email="debugtest@test.com",
            name="debugtest",
            password_hash="fakehash",
        )
        results["user_create"] = "OK"
        results["user_is_admin"] = repr(getattr(user, 'is_admin', 'MISSING'))
        db.close()
    except Exception as e:
        results["user_create_error"] = f"{type(e).__name__}: {e}"

    # Step 4: Test JWT
    try:
        from core.auth import create_access_token
        token = create_access_token(999)
        results["jwt"] = "OK"
    except Exception as e:
        results["jwt_error"] = f"{type(e).__name__}: {e}"

    # Step 5: Test JSONResponse
    try:
        from fastapi.responses import JSONResponse
        resp = JSONResponse(content={"test": True, "is_admin": False})
        results["jsonresponse"] = "OK"
    except Exception as e:
        results["jsonresponse_error"] = f"{type(e).__name__}: {e}"

    return results


@app.post("/api/migrate")
async def run_migration():
    """Run pending database migrations."""
    from sqlalchemy import text
    results = []

    migrations = [
        ("users.is_admin", "SELECT is_admin FROM users LIMIT 1",
         "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"),
        ("advertisers.user_id", "SELECT user_id FROM advertisers LIMIT 1",
         "ALTER TABLE advertisers ADD COLUMN user_id INTEGER REFERENCES users(id)"),
        ("competitors.user_id", "SELECT user_id FROM competitors LIMIT 1",
         "ALTER TABLE competitors ADD COLUMN user_id INTEGER REFERENCES users(id)"),
    ]

    for name, check_sql, alter_sql in migrations:
        try:
            with engine.begin() as conn:
                conn.execute(text(check_sql))
                results.append(f"{name}: already exists")
        except Exception:
            try:
                with engine.begin() as conn:
                    conn.execute(text(alter_sql))
                    results.append(f"{name}: added")
            except Exception as e:
                results.append(f"{name}: error - {e}")

    return {"migrations": results}


@app.post("/api/scheduler/run-now")
async def trigger_manual_collection():
    """Déclenche une collecte manuelle de toutes les données."""
    try:
        await scheduler.daily_data_collection()
        return {"message": "Collecte terminée", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"message": f"Erreur: {str(e)}", "error": True}
