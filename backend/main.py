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
from fastapi import Depends, HTTPException
from core.auth import get_current_user

import os
# Load .env from parent dir (local dev) or current dir (deployed)
load_dotenv(dotenv_path="../.env")
load_dotenv(dotenv_path=".env")

# Routers
from routers import auth, brand, watch, competitors, geo, layers, admin, advertiser
from routers import facebook, playstore, appstore, aso, instagram, tiktok, youtube, google_ads, creative_analysis, social_analysis, seo, geo_tracking, enrichment
from services.scheduler import scheduler

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def _enrich_missing_stores():
    """Background: enrich competitors that have 0 BANCO store locations.
    Uses streaming disk-based import (~5MB peak memory)."""
    try:
        from database import SessionLocal, Competitor
        from services.banco import banco_service

        db = SessionLocal()
        try:
            competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
            if not competitors:
                return

            # bulk_import checks existing data internally, downloads once, streams once
            counts = await banco_service.bulk_import(competitors, db)
            if counts:
                total = sum(counts.values())
                logger.info(f"BANCO startup: imported {total} stores for {len(counts)} competitors")
            else:
                logger.info("BANCO startup: all competitors already have store data")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"BANCO startup enrichment error: {e}")


def _refresh_logo_urls():
    """Re-generate logo URLs for all competitors/advertisers (replace dead Clearbit)."""
    from core.utils import get_logo_url
    db = SessionLocal()
    try:
        for comp in db.query(Competitor).all():
            new_url = get_logo_url(comp.website)
            if new_url and comp.logo_url != new_url:
                comp.logo_url = new_url
        for adv in db.query(Advertiser).all():
            new_url = get_logo_url(adv.website)
            if new_url and adv.logo_url != new_url:
                adv.logo_url = new_url
        db.commit()
        logger.info("Logo URLs refreshed")
    except Exception as e:
        logger.error(f"Logo refresh error: {e}")
    finally:
        db.close()


def _patch_missing_social_handles():
    """Auto-patch competitors with missing social handles from the sector database."""
    from routers.advertiser import COMPETITORS_BY_SECTOR
    known = {}
    for sector_comps in COMPETITORS_BY_SECTOR.values():
        for comp in sector_comps:
            known[comp["name"].lower()] = comp

    db = SessionLocal()
    try:
        competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
        patched = 0
        for comp in competitors:
            ref = known.get(comp.name.lower())
            if not ref:
                continue
            changed = False
            for field in ["tiktok_username", "instagram_username", "youtube_channel_id",
                          "playstore_app_id", "appstore_app_id"]:
                current = getattr(comp, field, None)
                new_val = ref.get(field)
                if new_val and (not current or current != new_val):
                    setattr(comp, field, new_val)
                    changed = True
            if changed:
                patched += 1
        if patched:
            db.commit()
            logger.info(f"Patched {patched} competitors with missing social handles")
    finally:
        db.close()


async def _deferred_startup():
    """Run slow startup tasks in background so healthcheck passes fast."""
    import asyncio
    await asyncio.sleep(2)  # Let the server start first

    try:
        _refresh_logo_urls()
    except Exception as e:
        logger.error(f"Logo refresh failed (non-fatal): {e}")

    try:
        _patch_missing_social_handles()
    except Exception as e:
        logger.error(f"Social handles patch failed (non-fatal): {e}")

    try:
        await scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler start failed (non-fatal): {e}")

    # BANCO: now streams from disk (~5MB peak), safe for Railway
    asyncio.create_task(_enrich_missing_stores())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    import asyncio

    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed (non-fatal): {e}")

    # Defer slow tasks so the server starts responding immediately
    asyncio.create_task(_deferred_startup())

    yield

    try:
        await scheduler.stop()
        logger.info("Scheduler stopped")
    except Exception:
        pass


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
app.include_router(advertiser.router, prefix="/api/advertiser", tags=["Annonceurs"])
app.include_router(watch.router, prefix="/api/watch", tags=["Veille Concurrentielle"])
app.include_router(competitors.router, prefix="/api/competitors", tags=["Concurrents"])
app.include_router(geo.router, prefix="/api/geo", tags=["Géographie & Magasins"])
app.include_router(layers.router, tags=["Layers Cartographiques"])

# Canaux (data collection)
app.include_router(facebook.router, prefix="/api/facebook", tags=["Meta Ads"])
app.include_router(playstore.router, prefix="/api/playstore", tags=["Play Store"])
app.include_router(appstore.router, prefix="/api/appstore", tags=["App Store"])
app.include_router(aso.router, prefix="/api/aso", tags=["ASO"])
app.include_router(instagram.router, prefix="/api/instagram", tags=["Instagram"])
app.include_router(tiktok.router, prefix="/api/tiktok", tags=["TikTok"])
app.include_router(youtube.router, prefix="/api/youtube", tags=["YouTube"])
app.include_router(google_ads.router, prefix="/api/google", tags=["Google Ads"])
app.include_router(creative_analysis.router, prefix="/api/creative", tags=["Creative Analysis"])
app.include_router(social_analysis.router, prefix="/api/social-content", tags=["Social Content Analysis"])
app.include_router(seo.router, prefix="/api/seo", tags=["SEO / SERP Tracking"])
app.include_router(geo_tracking.router, prefix="/api/geo-tracking", tags=["GEO / AI Visibility"])
app.include_router(enrichment.router, prefix="/api/enrich", tags=["Enrichissement Global"])


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
    """Health check endpoint (lightweight, no DB required)."""
    result = {
        "status": "healthy",
        "version": "2.0.0",
    }
    try:
        db = SessionLocal()
        brand = db.query(Advertiser).filter(Advertiser.is_active == True).first()
        competitors_count = db.query(Competitor).filter(Competitor.is_active == True).count()
        db.close()
        result["brand_configured"] = brand is not None
        result["competitors_count"] = competitors_count
        result["scheduler_status"] = scheduler.get_status()
    except Exception:
        result["db"] = "unavailable"
    return result


@app.get("/api/scheduler/status")
async def get_scheduler_status():
    """Statut du scheduler de collecte automatique."""
    return scheduler.get_status()


@app.get("/api/debug/db")
async def debug_db(user: User = Depends(get_current_user)):
    """Debug database connectivity. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")
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


@app.post("/api/migrate")
async def run_migration(user: User = Depends(get_current_user)):
    """Run pending database migrations. Admin only."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin uniquement")
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
