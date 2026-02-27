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

from database import init_db, engine, User, Advertiser, Competitor, PromptTemplate
from database import SessionLocal
from fastapi import Depends, HTTPException
from core.auth import get_current_user

import os
# Load .env from parent dir (local dev) or current dir (deployed)
load_dotenv(dotenv_path="../.env")
load_dotenv(dotenv_path=".env")

# Routers
from routers import auth, brand, watch, competitors, geo, layers, admin, advertiser, freshness
from routers import facebook, playstore, appstore, aso, instagram, tiktok, youtube, google_ads, snapchat, creative_analysis, social_analysis, seo, geo_tracking, enrichment, signals, trends, ads_overview
from routers import google_trends_news
from routers import moby
from routers import mcp_keys
from routers import meta_ads
from routers import smart_filter
from routers import vgeo
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
    from core.sectors import SECTORS as SECTORS_DB
    known = {}
    for sector_data in SECTORS_DB.values():
        for comp in sector_data.get("competitors", []):
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
                          "playstore_app_id", "appstore_app_id", "snapchat_entity_name",
                          "facebook_page_id"]:
                current = getattr(comp, field, None)
                new_val = ref.get(field)
                if new_val and (not current or current != new_val):
                    setattr(comp, field, new_val)
                    changed = True
            if changed:
                patched += 1
        # Also patch advertisers (brand) with correct IDs
        advertisers = db.query(Advertiser).filter(Advertiser.is_active == True).all()
        for adv in advertisers:
            ref = known.get(adv.company_name.lower())
            if not ref:
                continue
            for field in ["playstore_app_id", "appstore_app_id", "instagram_username",
                          "tiktok_username", "youtube_channel_id", "snapchat_entity_name",
                          "facebook_page_id"]:
                current = getattr(adv, field, None)
                new_val = ref.get(field)
                if new_val and (not current or current != new_val):
                    setattr(adv, field, new_val)
                    patched += 1
        if patched:
            db.commit()
            logger.info(f"Patched {patched} competitors/advertisers with correct handles")
    finally:
        db.close()


async def _enrich_empty_competitors():
    """Auto-enrich competitors that have social handles configured but zero data records.

    Fixes the case where:
    1. Brand was created without handles
    2. Handles were patched later by _patch_missing_social_handles()
    3. But enrichment never re-ran because it only triggers on creation
    """
    from database import InstagramData, TikTokData, YouTubeData, AppData

    db = SessionLocal()
    try:
        competitors = db.query(Competitor).filter(Competitor.is_active == True).all()
        to_enrich = []

        for comp in competitors:
            has_any_handle = any([
                comp.instagram_username,
                comp.tiktok_username,
                comp.youtube_channel_id,
                comp.playstore_app_id,
                comp.appstore_app_id,
            ])
            if not has_any_handle:
                continue

            # Check if competitor has ANY data records at all
            has_data = (
                db.query(InstagramData.id).filter(InstagramData.competitor_id == comp.id).first() is not None
                or db.query(TikTokData.id).filter(TikTokData.competitor_id == comp.id).first() is not None
                or db.query(YouTubeData.id).filter(YouTubeData.competitor_id == comp.id).first() is not None
                or db.query(AppData.id).filter(AppData.competitor_id == comp.id).first() is not None
            )
            if not has_data:
                to_enrich.append(comp)

        if not to_enrich:
            logger.info("All competitors with handles already have data")
            return

        logger.info(f"Auto-enriching {len(to_enrich)} competitors with handles but no data: "
                     f"{[c.name for c in to_enrich]}")

        from routers.competitors import _auto_enrich_competitor
        for comp in to_enrich:
            try:
                results = await _auto_enrich_competitor(comp.id, comp)
                logger.info(f"Auto-enriched '{comp.name}': {results}")
            except Exception as e:
                logger.error(f"Auto-enrichment failed for '{comp.name}': {e}")
    finally:
        db.close()


SEO_ANALYSIS_PROMPT = """Tu es un expert SEO pour le retail et la grande distribution en France.
A partir des donnees SEO ci-dessous, genere un diagnostic strategique et des recommandations actionnables.

Contexte : enseigne="{brand_name}", secteur="{sector}"

Donnees SEO :
{seo_data}

Retourne UNIQUEMENT un JSON valide (pas de markdown, pas de ```) :
{{
  "diagnostic": "<3-5 phrases de synthese strategique : positionnement SEO de l'enseigne vs concurrents, forces et faiblesses>",
  "priorities": [
    {{
      "action": "<action concrete a mener>",
      "impact": "<high|medium|low>",
      "effort": "<high|medium|low>",
      "detail": "<1-2 phrases expliquant pourquoi et comment>"
    }}
  ],
  "quick_wins": ["<action rapide 1>", "<action rapide 2>", "<action rapide 3>"],
  "benchmark_insight": "<1 phrase sur ce que le leader fait mieux>"
}}"""


GEO_ANALYSIS_PROMPT = """Tu es un expert en GEO (Generative Engine Optimization) et visibilite IA pour le retail en France.
A partir des donnees de visibilite IA ci-dessous, genere un diagnostic strategique et des recommandations actionnables.

Contexte : enseigne="{brand_name}", secteur="{sector}"

Donnees GEO (visibilite dans les reponses IA) :
{geo_data}

Retourne UNIQUEMENT un JSON valide (pas de markdown, pas de ```) :
{{
  "diagnostic": "<3-5 phrases de synthese strategique : visibilite IA de l'enseigne vs concurrents, forces et faiblesses>",
  "priorities": [
    {{
      "action": "<action concrete a mener>",
      "impact": "<high|medium|low>",
      "effort": "<high|medium|low>",
      "detail": "<1-2 phrases expliquant pourquoi et comment>"
    }}
  ],
  "quick_wins": ["<action rapide 1>", "<action rapide 2>", "<action rapide 3>"],
  "benchmark_insight": "<1 phrase sur ce que le leader fait mieux en GEO>"
}}"""


ASO_ANALYSIS_PROMPT = """Tu es un expert ASO (App Store Optimization) pour les apps retail et grande distribution en France.
A partir des scores ASO ci-dessous, genere un diagnostic strategique et des recommandations actionnables.

Contexte : enseigne="{brand_name}", secteur="{sector}"

Donnees ASO par concurrent :
{aso_data}

Retourne UNIQUEMENT un JSON valide (pas de markdown, pas de ```) :
{{
  "diagnostic": "<3-5 phrases de synthese strategique : positionnement ASO de l'enseigne vs concurrents, forces et faiblesses>",
  "priorities": [
    {{
      "action": "<action concrete a mener>",
      "impact": "<high|medium|low>",
      "effort": "<high|medium|low>",
      "store": "<playstore|appstore|both>",
      "detail": "<1-2 phrases expliquant pourquoi et comment>"
    }}
  ],
  "quick_wins": ["<action rapide 1>", "<action rapide 2>", "<action rapide 3>"],
  "benchmark_insight": "<1 phrase sur ce que le leader fait mieux>"
}}"""


def _seed_prompt_templates():
    """Seed default AI prompt templates if not already in DB (by key)."""
    from services.creative_analyzer import ANALYSIS_PROMPT as CREATIVE_PROMPT
    from services.social_content_analyzer import ANALYSIS_PROMPT as SOCIAL_PROMPT
    from services.moby_ai import SQL_SYSTEM_PROMPT as MOBY_SQL_PROMPT
    from services.moby_ai import ANSWER_SYSTEM_PROMPT as MOBY_ANSWER_PROMPT

    defaults = [
        {
            "key": "creative_analysis",
            "label": "Analyse creative publicitaire",
            "prompt_text": CREATIVE_PROMPT,
            "model_id": "gemini-3-flash-preview",
            "max_tokens": 1024,
        },
        {
            "key": "social_content",
            "label": "Analyse contenu social media",
            "prompt_text": SOCIAL_PROMPT,
            "model_id": "gemini-3-flash-preview",
            "max_tokens": 1024,
        },
        {
            "key": "aso_analysis",
            "label": "Diagnostic ASO (App Store Optimization)",
            "prompt_text": ASO_ANALYSIS_PROMPT,
            "model_id": "gemini-3-flash-preview",
            "max_tokens": 1024,
        },
        {
            "key": "seo_analysis",
            "label": "Diagnostic SEO (positionnement Google)",
            "prompt_text": SEO_ANALYSIS_PROMPT,
            "model_id": "gemini-3-flash-preview",
            "max_tokens": 1024,
        },
        {
            "key": "geo_analysis",
            "label": "Diagnostic GEO (visibilite IA)",
            "prompt_text": GEO_ANALYSIS_PROMPT,
            "model_id": "gemini-3-flash-preview",
            "max_tokens": 1024,
        },
        {
            "key": "moby_sql",
            "label": "Moby - Generation SQL",
            "prompt_text": MOBY_SQL_PROMPT,
            "model_id": "gemini-3-flash-preview",
            "max_tokens": 512,
        },
        {
            "key": "moby_answer",
            "label": "Moby - Synthese business",
            "prompt_text": MOBY_ANSWER_PROMPT,
            "model_id": "gemini-3-flash-preview",
            "max_tokens": 1024,
        },
    ]

    db = SessionLocal()
    try:
        existing = {p.key: p for p in db.query(PromptTemplate).all()}
        added = 0
        updated = 0
        for d in defaults:
            if d["key"] not in existing:
                db.add(PromptTemplate(**d))
                added += 1
            else:
                # Update prompt text and model_id if changed
                row = existing[d["key"]]
                changed = False
                if row.prompt_text != d["prompt_text"]:
                    row.prompt_text = d["prompt_text"]
                    changed = True
                if row.model_id != d.get("model_id"):
                    row.model_id = d["model_id"]
                    changed = True
                if row.max_tokens != d.get("max_tokens"):
                    row.max_tokens = d["max_tokens"]
                    changed = True
                if changed:
                    updated += 1
        if added or updated:
            db.commit()
            logger.info(f"Prompt templates: {added} added, {updated} updated")
    except Exception as e:
        logger.warning(f"Prompt template seed warning: {e}")
    finally:
        db.close()


def _backfill_ad_types():
    """Classify existing ads that have no ad_type."""
    from database import Ad
    from routers.facebook import _classify_ad_type

    db = SessionLocal()
    try:
        ads = db.query(Ad).filter(Ad.ad_type.is_(None)).all()
        if not ads:
            return
        for ad in ads:
            ad.ad_type = _classify_ad_type(ad.link_url, ad.creative_concept, ad.cta, ad.display_format)
        db.commit()
        logger.info(f"Backfilled ad_type for {len(ads)} ads")
    except Exception as e:
        logger.warning(f"Ad type backfill warning: {e}")
    finally:
        db.close()


async def _deferred_startup():
    """Run slow startup tasks in background so healthcheck passes fast."""
    import asyncio
    await asyncio.sleep(2)  # Let the server start first

    try:
        _backfill_ad_types()
    except Exception as e:
        logger.error(f"Ad type backfill failed (non-fatal): {e}")

    try:
        _refresh_logo_urls()
    except Exception as e:
        logger.error(f"Logo refresh failed (non-fatal): {e}")

    try:
        _patch_missing_social_handles()
    except Exception as e:
        logger.error(f"Social handles patch failed (non-fatal): {e}")

    # Auto-enrich moved to daily scheduler to avoid burning API credits on every deploy
    # The scheduler runs at 02:00 and handles enrichment there

    try:
        await scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler start failed (non-fatal): {e}")

    # Store enrichment moved to daily scheduler to avoid API calls on every deploy


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    import asyncio

    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed (non-fatal): {e}")

    # Auto-promote first user to admin if no admin exists
    try:
        _db = SessionLocal()
        admin_exists = _db.query(User).filter(User.is_admin == True).first()
        if not admin_exists:
            first_user = _db.query(User).order_by(User.id).first()
            if first_user:
                first_user.is_admin = True
                _db.commit()
                logger.info(f"Auto-promoted '{first_user.email}' to admin (first user)")
        _db.close()
    except Exception as e:
        logger.warning(f"Admin auto-promote warning: {e}")

    try:
        _seed_prompt_templates()
    except Exception as e:
        logger.warning(f"Prompt seed failed (non-fatal): {e}")

    # Defer slow tasks so the server starts responding immediately
    asyncio.create_task(_deferred_startup())

    yield

    try:
        from core.langfuse_client import flush as langfuse_flush
        langfuse_flush()
        logger.info("Langfuse flushed")
    except Exception:
        pass

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
    "https://panoramai.vercel.app",
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
app.include_router(google_trends_news.router, prefix="/api/google", tags=["Google Trends & News"])
app.include_router(snapchat.router, prefix="/api/snapchat", tags=["Snapchat Ads"])
app.include_router(creative_analysis.router, prefix="/api/creative", tags=["Creative Analysis"])
app.include_router(social_analysis.router, prefix="/api/social-content", tags=["Social Content Analysis"])
app.include_router(seo.router, prefix="/api/seo", tags=["SEO / SERP Tracking"])
app.include_router(geo_tracking.router, prefix="/api/geo-tracking", tags=["GEO / AI Visibility"])
app.include_router(enrichment.router, prefix="/api/enrich", tags=["Enrichissement Global"])
app.include_router(signals.router, prefix="/api/signals", tags=["Signaux & Alertes"])
app.include_router(trends.router, prefix="/api/trends", tags=["Tendances & Evolution"])
app.include_router(ads_overview.router, prefix="/api/ads", tags=["Ads Overview"])
app.include_router(freshness.router, prefix="/api/freshness", tags=["Fraîcheur des données"])
app.include_router(moby.router, prefix="/api/moby", tags=["Moby AI Assistant"])
app.include_router(mcp_keys.router, prefix="/api/mcp", tags=["MCP Integration"])
app.include_router(meta_ads.router, prefix="/api/meta-ads", tags=["Meta Ad Library"])
app.include_router(smart_filter.router, prefix="/api/smart-filter", tags=["Smart Filter IA"])
app.include_router(vgeo.router, prefix="/api/vgeo", tags=["VGEO (Video GEO)"])

# Mount MCP SSE server (non-fatal if competitive-mcp not available)
try:
    from competitive_mcp.server import mcp as mcp_server
    from core.mcp_auth import MCPAuthMiddleware
    app.mount("/mcp", MCPAuthMiddleware(mcp_server.sse_app()))
    logger.info("MCP SSE server mounted at /mcp")
except Exception as e:
    logger.warning(f"MCP SSE mount skipped: {e}")


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


@app.get("/api/health/data-depth")
async def data_depth():
    """Data depth diagnostic — no auth required."""
    from sqlalchemy import text
    from database import InstagramData, TikTokData, YouTubeData, Ad, StoreLocation
    try:
        db = SessionLocal()
        rows = db.execute(text("""
            SELECT 'instagram_data' as tbl, count(*) as rows, min(recorded_at)::date::text as oldest, max(recorded_at)::date::text as newest FROM instagram_data
            UNION ALL SELECT 'tiktok_data', count(*), min(recorded_at)::date::text, max(recorded_at)::date::text FROM tiktok_data
            UNION ALL SELECT 'youtube_data', count(*), min(recorded_at)::date::text, max(recorded_at)::date::text FROM youtube_data
            UNION ALL SELECT 'ads', count(*), min(created_at)::date::text, max(created_at)::date::text FROM ads
            UNION ALL SELECT 'store_locations', count(*), null, null FROM store_locations
            ORDER BY 1
        """)).fetchall()
        db.close()
        return {r[0]: {"rows": r[1], "oldest": r[2], "newest": r[3]} for r in rows}
    except Exception as e:
        return {"error": str(e)}



@app.get("/api/scheduler/status")
async def get_scheduler_status():
    """Statut du scheduler de collecte automatique."""
    return scheduler.get_status()


@app.get("/api/debug/data-check")
async def debug_data_check():
    """Quick data check per advertiser. Temporary debug endpoint."""
    from sqlalchemy import text
    db = SessionLocal()
    result = {}
    try:
        advs = db.execute(text("SELECT id, company_name FROM advertisers WHERE is_active = true ORDER BY id")).fetchall()
        for adv_id, name in advs:
            checks = {}
            # Get competitor IDs via join table (advertiser_competitors)
            comp_ids = [r[0] for r in db.execute(text(
                "SELECT c.id FROM competitors c "
                "JOIN advertiser_competitors ac ON ac.competitor_id = c.id "
                "WHERE ac.advertiser_id = :a AND c.is_active = true"
            ), {"a": adv_id}).fetchall()]
            checks["competitors"] = len(comp_ids)
            if comp_ids:
                placeholders = ",".join(str(c) for c in comp_ids)
                for tbl, q in [
                    ("ads", f"SELECT COUNT(*) FROM ads WHERE competitor_id IN ({placeholders})"),
                    ("store_locations", f"SELECT COUNT(*) FROM store_locations WHERE competitor_id IN ({placeholders})"),
                    ("instagram", f"SELECT COUNT(*) FROM instagram_data WHERE competitor_id IN ({placeholders})"),
                    ("tiktok", f"SELECT COUNT(*) FROM tiktok_data WHERE competitor_id IN ({placeholders})"),
                    ("youtube", f"SELECT COUNT(*) FROM youtube_data WHERE competitor_id IN ({placeholders})"),
                    ("app_data", f"SELECT COUNT(*) FROM app_data WHERE competitor_id IN ({placeholders})"),
                    ("social_posts", f"SELECT COUNT(*) FROM social_posts WHERE competitor_id IN ({placeholders})"),
                    ("social_posts_analyzed", f"SELECT COUNT(*) FROM social_posts WHERE competitor_id IN ({placeholders}) AND content_analyzed_at IS NOT NULL AND content_engagement_score > 0"),
                ]:
                    try:
                        checks[tbl] = db.execute(text(q)).scalar()
                    except Exception:
                        checks[tbl] = "table missing"
                        db.rollback()
            # Advertiser-scoped tables
            for tbl, q in [
                ("seo_keywords", "SELECT COUNT(DISTINCT keyword) FROM serp_results WHERE advertiser_id = :a"),
                ("seo_results", "SELECT COUNT(*) FROM serp_results WHERE advertiser_id = :a"),
                ("geo_results", "SELECT COUNT(*) FROM geo_results WHERE advertiser_id = :a"),
                ("vgeo_reports", "SELECT COUNT(*) FROM vgeo_reports WHERE advertiser_id = :a"),
                ("signals", "SELECT COUNT(*) FROM signals WHERE advertiser_id = :a"),
                ("google_trends", "SELECT COUNT(*) FROM google_trends_data WHERE competitor_id IN (SELECT c.id FROM competitors c JOIN advertiser_competitors ac ON ac.competitor_id = c.id WHERE ac.advertiser_id = :a)"),
                ("google_news", "SELECT COUNT(*) FROM google_news_articles WHERE competitor_id IN (SELECT c.id FROM competitors c JOIN advertiser_competitors ac ON ac.competitor_id = c.id WHERE ac.advertiser_id = :a)"),
                ("ad_snapshots", "SELECT COUNT(*) FROM ad_snapshots WHERE competitor_id IN (SELECT c.id FROM competitors c JOIN advertiser_competitors ac ON ac.competitor_id = c.id WHERE ac.advertiser_id = :a)"),
            ]:
                try:
                    checks[tbl] = db.execute(text(q), {"a": adv_id}).scalar()
                except Exception:
                    checks[tbl] = "table missing"
                    db.rollback()
            result[f"{adv_id}:{name}"] = checks
    finally:
        db.close()
    return result


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


@app.post("/api/scheduler/run-creative-analysis")
async def trigger_creative_analysis():
    """Déclenche l'analyse créative Gemini sur les pubs non analysées."""
    import asyncio
    asyncio.create_task(scheduler.daily_creative_analysis())
    return {"message": "Analyse créative lancée en background", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/scheduler/run-social-analysis")
async def trigger_social_analysis():
    """Déclenche la collecte + analyse IA des posts sociaux."""
    import asyncio
    asyncio.create_task(scheduler.daily_social_analysis())
    return {"message": "Collecte + analyse sociale lancée en background", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/scheduler/run-seo")
async def trigger_seo_tracking():
    """Déclenche le tracking SEO SERP pour toutes les enseignes."""
    import asyncio
    asyncio.create_task(scheduler.daily_seo_tracking())
    return {"message": "SEO tracking lancé en background", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/scheduler/run-geo")
async def trigger_geo_tracking():
    """Déclenche le tracking GEO (visibilité IA) pour toutes les enseignes."""
    import asyncio
    asyncio.create_task(scheduler.daily_geo_tracking())
    return {"message": "GEO tracking lancé en background", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/scheduler/run-vgeo")
async def trigger_vgeo_analysis():
    """Déclenche l'analyse VGEO (Video GEO) pour toutes les enseignes."""
    import asyncio
    asyncio.create_task(scheduler.daily_vgeo_analysis())
    return {"message": "VGEO analysis lancée en background", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/scheduler/run-trends")
async def trigger_google_trends():
    """Déclenche la collecte Google Trends pour toutes les enseignes."""
    import asyncio
    asyncio.create_task(scheduler.daily_google_trends())
    return {"message": "Google Trends lancé en background", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/scheduler/run-news")
async def trigger_google_news():
    """Déclenche la collecte Google News pour toutes les enseignes."""
    import asyncio
    asyncio.create_task(scheduler.daily_google_news())
    return {"message": "Google News lancé en background", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/scheduler/run-aso")
async def trigger_aso_analysis():
    """Déclenche l'analyse ASO (App Store Optimization) pour toutes les enseignes."""
    import asyncio
    asyncio.create_task(scheduler.daily_aso_analysis())
    return {"message": "ASO analysis lancée en background", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/scheduler/run-gmb")
async def trigger_gmb_enrichment():
    """Déclenche l'enrichissement GMB (Google My Business) pour tous les magasins."""
    import asyncio
    asyncio.create_task(scheduler.weekly_gmb_enrichment())
    return {"message": "GMB enrichment lancé en background", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/scheduler/run-all")
async def trigger_all_enrichment():
    """Déclenche TOUT : collecte + signaux + creative + social + SEO + GEO + VGEO + trends + news + ASO."""
    import asyncio

    async def _run_all():
        await scheduler.daily_data_collection()
        await scheduler.daily_snapshots_and_signals()
        await scheduler.daily_creative_analysis()
        await scheduler.daily_social_analysis()
        await scheduler.daily_seo_tracking()
        await scheduler.daily_geo_tracking()
        await scheduler.daily_vgeo_analysis()
        await scheduler.daily_google_trends()
        await scheduler.daily_google_news()
        await scheduler.daily_aso_analysis()

    asyncio.create_task(_run_all())
    return {"message": "Enrichissement complet lancé en background (collecte + signaux + creative + social + SEO + GEO + VGEO + trends + news + ASO)", "timestamp": datetime.utcnow().isoformat()}
