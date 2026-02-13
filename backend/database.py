from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, ForeignKey, Boolean, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "") or "sqlite:///./competitive.db"

# Render/Railway generate postgres:// URLs but SQLAlchemy 2.0 requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False; PostgreSQL doesn't use connect_args
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """User account."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100))
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    advertiser = relationship("Advertiser", back_populates="user", uselist=False)
    competitors = relationship("Competitor", back_populates="user")


class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    website = Column(String(500))
    facebook_page_id = Column(String(100))
    instagram_username = Column(String(100))
    playstore_app_id = Column(String(255))
    appstore_app_id = Column(String(100))
    tiktok_username = Column(String(100))
    youtube_channel_id = Column(String(100))
    logo_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="competitors")

    ads = relationship("Ad", back_populates="competitor")
    instagram_data = relationship("InstagramData", back_populates="competitor")
    app_data = relationship("AppData", back_populates="competitor")
    tiktok_data = relationship("TikTokData", back_populates="competitor")
    youtube_data = relationship("YouTubeData", back_populates="competitor")


class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    ad_id = Column(String(100), unique=True)
    platform = Column(String(50))  # facebook, instagram
    creative_url = Column(String(1000))
    ad_text = Column(Text)
    cta = Column(String(100))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    estimated_spend_min = Column(Float)
    estimated_spend_max = Column(Float)
    impressions_min = Column(Integer)
    impressions_max = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Enriched fields
    publisher_platforms = Column(String(500))    # JSON: ["FACEBOOK","INSTAGRAM","AUDIENCE_NETWORK"]
    page_id = Column(String(100))               # Facebook page ID
    page_name = Column(String(500))             # Advertiser page name
    page_categories = Column(String(500))       # JSON: ["Retail","Shopping"]
    page_like_count = Column(Integer)           # Page likes count
    page_profile_uri = Column(String(1000))     # Facebook page URL
    page_profile_picture_url = Column(String(1000))
    link_url = Column(String(1000))             # Landing page / destination URL
    display_format = Column(String(50))         # DCO, VIDEO, IMAGE, CAROUSEL
    targeted_countries = Column(String(500))    # JSON: ["FR","BE","CH"]
    ad_categories = Column(String(500))         # JSON: ["EMPLOYMENT","HOUSING"]
    contains_ai_content = Column(Boolean)       # AI-generated content flag
    ad_library_url = Column(String(1000))       # Direct Ad Library link
    title = Column(String(1000))                # Ad title
    link_description = Column(Text)             # Full ad description
    byline = Column(String(500))                # EU transparency: "Paid for by" entity
    disclaimer_label = Column(String(500))      # EU disclaimer label (payer/beneficiary)

    # EU Transparency / Audience targeting (from ad detail endpoint)
    age_min = Column(Integer)                    # Minimum target age (e.g. 18)
    age_max = Column(Integer)                    # Maximum target age (e.g. 65)
    gender_audience = Column(String(50))         # "All", "Male", "Female"
    location_audience = Column(Text)             # JSON: [{"name":"France: 3664 ZIP codes","type":"...","excluded":false}]
    eu_total_reach = Column(BigInteger)          # Total EU reach (unique accounts)
    age_country_gender_reach = Column(Text)      # JSON: full breakdown by age/gender/country

    competitor = relationship("Competitor", back_populates="ads")


class InstagramData(Base):
    __tablename__ = "instagram_data"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    followers = Column(Integer)
    following = Column(Integer)
    posts_count = Column(Integer)
    avg_likes = Column(Float)
    avg_comments = Column(Float)
    engagement_rate = Column(Float)
    bio = Column(Text)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    competitor = relationship("Competitor", back_populates="instagram_data")


class AppData(Base):
    __tablename__ = "app_data"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    store = Column(String(20))  # playstore, appstore
    app_id = Column(String(255))
    app_name = Column(String(255))
    rating = Column(Float)
    reviews_count = Column(Integer)
    downloads = Column(String(50))  # "1M+", "10K+", etc.
    downloads_numeric = Column(BigInteger)  # Parsed numeric value for comparisons
    version = Column(String(50))
    last_updated = Column(DateTime)
    description = Column(Text)
    changelog = Column(Text)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    competitor = relationship("Competitor", back_populates="app_data")


class TikTokData(Base):
    __tablename__ = "tiktok_data"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    username = Column(String(100))
    followers = Column(BigInteger)
    following = Column(Integer)
    likes = Column(BigInteger)
    videos_count = Column(Integer)
    bio = Column(Text)
    verified = Column(Boolean, default=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    competitor = relationship("Competitor", back_populates="tiktok_data")


class YouTubeData(Base):
    __tablename__ = "youtube_data"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    channel_id = Column(String(100))
    channel_name = Column(String(255))
    subscribers = Column(BigInteger)
    total_views = Column(BigInteger)
    videos_count = Column(Integer)
    avg_views = Column(Integer)
    avg_likes = Column(Integer)
    avg_comments = Column(Integer)
    engagement_rate = Column(Float)
    description = Column(Text)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    competitor = relationship("Competitor", back_populates="youtube_data")


class StoreLocation(Base):
    """Store location data from BANCO database."""
    __tablename__ = "store_locations"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=True, index=True)
    name = Column(String(255))
    brand_name = Column(String(255), index=True)
    category = Column(String(100))
    category_code = Column(String(20))
    address = Column(String(500))
    postal_code = Column(String(10))
    city = Column(String(100))
    department = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)
    siret = Column(String(20))
    source = Column(String(100))
    google_rating = Column(Float, nullable=True)
    google_reviews_count = Column(Integer, nullable=True)
    google_place_id = Column(String(255), nullable=True)
    rating_fetched_at = Column(DateTime, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    competitor = relationship("Competitor", backref="store_locations")


class MarketIndicator(Base):
    """Market activity indicators from INSEE/data.gouv.fr."""
    __tablename__ = "market_indicators"

    id = Column(Integer, primary_key=True, index=True)
    indicator_name = Column(String(255))
    sector = Column(String(100))
    value = Column(Float)
    variation_monthly = Column(Float)
    variation_yearly = Column(Float)
    period = Column(String(20))  # "2024-01", "2024-Q1", "2024"
    source = Column(String(100))
    recorded_at = Column(DateTime, default=datetime.utcnow)


class ConsumptionData(Base):
    """Household consumption data from INSEE."""
    __tablename__ = "consumption_data"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(255))
    category_code = Column(String(10))
    value = Column(Float)  # In millions of euros
    year = Column(Integer)
    variation = Column(Float)  # Year-over-year change
    source = Column(String(100))
    recorded_at = Column(DateTime, default=datetime.utcnow)


class Advertiser(Base):
    """Advertiser account for competitive intelligence."""
    __tablename__ = "advertisers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    company_name = Column(String(255), nullable=False)
    sector = Column(String(100))  # supermarche, mode, beaute, etc.
    website = Column(String(500))
    playstore_app_id = Column(String(255))
    appstore_app_id = Column(String(100))
    instagram_username = Column(String(100))
    tiktok_username = Column(String(100))
    youtube_channel_id = Column(String(100))
    logo_url = Column(String(500))
    contact_email = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="advertiser")
    stores = relationship("Store", back_populates="advertiser")


class Store(Base):
    """Magasin physique de l'enseigne."""
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.id"))
    store_code = Column(String(50))  # Code interne du magasin
    name = Column(String(255), nullable=False)
    address = Column(String(500))
    postal_code = Column(String(10), index=True)
    city = Column(String(100))
    department = Column(String(10), index=True)
    region = Column(String(100))
    latitude = Column(Float, index=True)
    longitude = Column(Float, index=True)
    store_type = Column(String(50))  # hypermarche, supermarche, proximite
    surface_m2 = Column(Integer)
    opening_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    advertiser = relationship("Advertiser", back_populates="stores")


class CommuneData(Base):
    """Données par commune (INSEE, loyers, etc.)."""
    __tablename__ = "commune_data"

    id = Column(Integer, primary_key=True, index=True)
    code_commune = Column(String(10), index=True)  # Code INSEE
    code_postal = Column(String(10), index=True)
    nom_commune = Column(String(255))
    department = Column(String(10), index=True)
    region = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)

    # Population
    population = Column(Integer)
    population_year = Column(Integer)
    densite = Column(Float)  # hab/km²

    # Revenus et loyers
    revenu_median = Column(Float)
    loyer_moyen_m2 = Column(Float)
    loyer_year = Column(Integer)

    # Emploi
    taux_chomage = Column(Float)
    emplois_total = Column(Integer)

    # Mobilité
    distance_domicile_travail_km = Column(Float)
    part_voiture = Column(Float)  # % utilisant la voiture
    part_transport_commun = Column(Float)

    # Équipements
    nb_commerces = Column(Integer)
    nb_services = Column(Integer)
    nb_equipements_sport = Column(Integer)
    nb_equipements_sante = Column(Integer)

    updated_at = Column(DateTime, default=datetime.utcnow)


class ZoneAnalysis(Base):
    """Analyse de zone de chalandise pré-calculée."""
    __tablename__ = "zone_analyses"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    radius_km = Column(Float)  # 5, 10, 15, 20 km

    # Population dans la zone
    population_zone = Column(Integer)
    nb_communes = Column(Integer)

    # Données agrégées
    revenu_median_moyen = Column(Float)
    loyer_moyen_m2 = Column(Float)
    distance_domicile_travail_moyenne = Column(Float)

    # Concurrence
    nb_concurrents = Column(Integer)
    concurrents_list = Column(Text)  # JSON array

    # Potentiel
    score_potentiel = Column(Float)  # 0-100

    calculated_at = Column(DateTime, default=datetime.utcnow)


def _run_migrations(engine):
    """Add missing columns and indexes to existing tables."""
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        migrations = [
            ("users", "is_admin", "BOOLEAN DEFAULT FALSE"),
            ("competitors", "logo_url", "VARCHAR(500)"),
            ("advertisers", "logo_url", "VARCHAR(500)"),
        ]
        existing_tables = inspector.get_table_names()
        for table, column, col_type in migrations:
            if table in existing_tables:
                existing = [c["name"] for c in inspector.get_columns(table)]
                if column not in existing:
                    with engine.begin() as conn:
                        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}'))

        # Add missing indexes on FK and temporal columns
        indexes_to_add = [
            ("ads", "competitor_id"),
            ("instagram_data", "competitor_id"),
            ("instagram_data", "recorded_at"),
            ("app_data", "competitor_id"),
            ("app_data", "recorded_at"),
            ("tiktok_data", "competitor_id"),
            ("tiktok_data", "recorded_at"),
            ("youtube_data", "competitor_id"),
            ("youtube_data", "recorded_at"),
        ]
        existing_indexes = {}
        for table in existing_tables:
            existing_indexes[table] = {
                col
                for idx in inspector.get_indexes(table)
                for col in idx.get("column_names", [])
            }
        for table, column in indexes_to_add:
            if table in existing_tables and column not in existing_indexes.get(table, set()):
                idx_name = f"ix_{table}_{column}"
                with engine.begin() as conn:
                    conn.execute(text(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ("{column}")'))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Migration warning: {e}")


def _backfill_logos(engine):
    """Backfill logo_url for existing competitors/advertisers with websites."""
    try:
        from sqlalchemy import text
        from core.utils import get_logo_url
        with engine.begin() as conn:
            for table in ("competitors", "advertisers"):
                rows = conn.execute(text(
                    f'SELECT id, website FROM "{table}" WHERE logo_url IS NULL AND website IS NOT NULL'
                )).fetchall()
                for row in rows:
                    logo = get_logo_url(row[1])
                    if logo:
                        conn.execute(text(
                            f'UPDATE "{table}" SET logo_url = :logo WHERE id = :id'
                        ), {"logo": logo, "id": row[0]})
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Logo backfill warning: {e}")


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations(engine)
    _backfill_logos(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
