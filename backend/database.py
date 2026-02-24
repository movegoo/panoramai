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
    ms_user_id = Column(Integer, unique=True, nullable=True, index=True)
    mcp_api_key = Column(String(64), unique=True, nullable=True, index=True)

    advertisers = relationship("Advertiser", back_populates="user")
    competitors = relationship("Competitor", back_populates="user")


class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    website = Column(String(500))
    facebook_page_id = Column(String(100))
    instagram_username = Column(String(100))
    playstore_app_id = Column(String(255))
    appstore_app_id = Column(String(100))
    tiktok_username = Column(String(100))
    youtube_channel_id = Column(String(100))
    snapchat_entity_name = Column(String(255))
    snapchat_username = Column(String(100))
    logo_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_brand = Column(Boolean, default=False)
    child_page_ids = Column(Text)  # JSON array of child Facebook page IDs

    user = relationship("User", back_populates="competitors")

    ads = relationship("Ad", back_populates="competitor")
    instagram_data = relationship("InstagramData", back_populates="competitor")
    app_data = relationship("AppData", back_populates="competitor")
    tiktok_data = relationship("TikTokData", back_populates="competitor")
    youtube_data = relationship("YouTubeData", back_populates="competitor")
    snapchat_data = relationship("SnapchatData", back_populates="competitor")


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
    payer = Column(String(500))                 # Payer entity (from SearchAPI.io / EU transparency)
    beneficiary = Column(String(500))           # Beneficiary entity (from SearchAPI.io / EU transparency)

    # EU Transparency / Audience targeting (from ad detail endpoint)
    age_min = Column(Integer)                    # Minimum target age (e.g. 18)
    age_max = Column(Integer)                    # Maximum target age (e.g. 65)
    gender_audience = Column(String(50))         # "All", "Male", "Female"
    location_audience = Column(Text)             # JSON: [{"name":"France: 3664 ZIP codes","type":"...","excluded":false}]
    eu_total_reach = Column(BigInteger)          # Total EU reach (unique accounts)
    age_country_gender_reach = Column(Text)      # JSON: full breakdown by age/gender/country

    # Creative Analysis (AI-powered visual intelligence via Claude Vision)
    creative_analysis = Column(Text)               # JSON: full analysis result
    creative_concept = Column(String(100))         # product-shot, lifestyle, ugc-style, promo...
    creative_hook = Column(String(500))            # What grabs attention first
    creative_tone = Column(String(100))            # urgency, aspiration, humor, trust, fomo...
    creative_text_overlay = Column(Text)           # All visible text on creative
    creative_dominant_colors = Column(String(100)) # JSON: ["#FF5733","#3498DB","#1ABC9C"]
    creative_has_product = Column(Boolean)
    creative_has_face = Column(Boolean)
    creative_has_logo = Column(Boolean)
    creative_layout = Column(String(50))           # single-image, split, text-heavy, minimal...
    creative_cta_style = Column(String(50))        # button, text, arrow, badge, none
    creative_score = Column(Integer)               # 0-100 quality/impact score
    creative_tags = Column(Text)                   # JSON: ["promo","lifestyle","bold-text"]
    creative_summary = Column(Text)                # 1-2 sentence AI description
    creative_analyzed_at = Column(DateTime)
    # Product classification (AI-powered, LSA taxonomy)
    product_category = Column(String(100))      # Épicerie, Frais, DPH, Non-alimentaire, Services...
    product_subcategory = Column(String(100))    # Boissons, Boucherie, Beauté, Multimédia...
    ad_objective = Column(String(50))            # notoriété, trafic, conversion, fidélisation, recrutement

    # Ad type segmentation
    ad_type = Column(String(20))  # branding, performance, dts

    # Enriched creative fields (AI-powered)
    promo_type = Column(String(50))        # prix-barré, pourcentage, lot, offre-spéciale, carte-fidélité, code-promo, gratuit, aucune
    creative_format = Column(String(50))   # catalogue, produit-unique, multi-produits, ambiance, événement, recrutement
    price_visible = Column(Boolean)
    price_value = Column(String(20))
    seasonal_event = Column(String(50))    # noël, rentrée, été, soldes, black-friday, saint-valentin, pâques, aucun

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


class SnapchatData(Base):
    __tablename__ = "snapchat_data"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    subscribers = Column(BigInteger)
    title = Column(String(255))
    story_count = Column(Integer)
    spotlight_count = Column(Integer)
    total_views = Column(BigInteger)
    total_shares = Column(Integer)
    total_comments = Column(Integer)
    engagement_rate = Column(Float)
    profile_picture_url = Column(String(1000))
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    competitor = relationship("Competitor", back_populates="snapchat_data")


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
    snapchat_entity_name = Column(String(255))
    snapchat_username = Column(String(100))
    logo_url = Column(String(500))
    contact_email = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="advertisers")
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
    gps_verified = Column(Boolean, default=False)
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


class SocialPost(Base):
    """Individual social media post/video with AI content analysis."""
    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    platform = Column(String(20), index=True)  # tiktok, youtube, instagram
    post_id = Column(String(200), unique=True)  # prefixed: tt_/yt_/ig_
    title = Column(String(1000))
    description = Column(Text)
    url = Column(String(1000))
    thumbnail_url = Column(String(1000))
    published_at = Column(DateTime)
    duration = Column(String(50))
    views = Column(BigInteger, default=0)
    likes = Column(BigInteger, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    collected_at = Column(DateTime, default=datetime.utcnow)

    # AI Content Analysis
    content_analysis = Column(Text)  # JSON: full analysis result
    content_theme = Column(String(100), index=True)
    content_hook = Column(String(500))
    content_tone = Column(String(100), index=True)
    content_format = Column(String(100))
    content_cta = Column(String(500))
    content_hashtags = Column(Text)  # JSON array
    content_mentions = Column(Text)  # JSON array
    content_engagement_score = Column(Integer, index=True)  # 0-100
    content_virality_factors = Column(Text)  # JSON array
    content_summary = Column(Text)
    content_analyzed_at = Column(DateTime)

    competitor = relationship("Competitor", backref="social_posts")


class SerpResult(Base):
    """Google SERP tracking result."""
    __tablename__ = "serp_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.id"), nullable=True, index=True)
    keyword = Column(String(255), nullable=False, index=True)
    position = Column(Integer, nullable=False)  # 1-10
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=True, index=True)
    title = Column(String(1000))
    url = Column(String(1000))
    snippet = Column(Text)
    domain = Column(String(255), index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    competitor = relationship("Competitor", backref="serp_results")


class GeoResult(Base):
    """GEO (Generative Engine Optimization) tracking result."""
    __tablename__ = "geo_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.id"), nullable=True, index=True)
    keyword = Column(String(255), nullable=False, index=True)
    query = Column(Text)
    platform = Column(String(50), index=True)  # "claude", "gemini"

    raw_answer = Column(Text)
    analysis = Column(Text)  # JSON

    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=True, index=True)
    mentioned = Column(Boolean, default=False)
    position_in_answer = Column(Integer)
    recommended = Column(Boolean, default=False)
    sentiment = Column(String(20))  # positif, neutre, négatif
    context_snippet = Column(Text)
    primary_recommendation = Column(String(100))

    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    competitor = relationship("Competitor", backref="geo_results")


class AdSnapshot(Base):
    """Daily snapshot of active ad metrics for trend tracking."""
    __tablename__ = "ad_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    ad_id = Column(String(100), index=True)  # References ads.ad_id
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    platform = Column(String(50))
    is_active = Column(Boolean, default=True)
    impressions_min = Column(Integer)
    impressions_max = Column(Integer)
    estimated_spend_min = Column(Float)
    estimated_spend_max = Column(Float)
    eu_total_reach = Column(BigInteger)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    competitor = relationship("Competitor", backref="ad_snapshots")


class GoogleTrendsData(Base):
    """Google Trends interest score (0-100) per competitor per day."""
    __tablename__ = "google_trends_data"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    keyword = Column(String(255), index=True)
    date = Column(String(20), index=True)  # "2026-02-23"
    value = Column(Integer)  # 0-100
    recorded_at = Column(DateTime, default=datetime.utcnow)

    competitor = relationship("Competitor", backref="google_trends_data")


class GoogleNewsArticle(Base):
    """News article collected via Google News."""
    __tablename__ = "google_news_articles"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    title = Column(String(1000))
    link = Column(String(1000), unique=True)
    source = Column(String(255))
    date = Column(String(100))  # raw string from Google News
    published_at = Column(DateTime, nullable=True)
    snippet = Column(Text)
    thumbnail = Column(String(1000))
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)

    competitor = relationship("Competitor", backref="google_news_articles")


class Signal(Base):
    """Detected signal (anomaly, trend change, competitive move)."""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), index=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.id"), nullable=True, index=True)
    signal_type = Column(String(50), index=True)       # follower_spike, rating_drop, new_campaign, engagement_anomaly, etc.
    severity = Column(String(20), index=True)           # info, warning, critical
    platform = Column(String(50))                       # instagram, tiktok, youtube, playstore, appstore, meta_ads, google_ads
    title = Column(String(500))                         # Human-readable title
    description = Column(Text)                          # Detailed explanation
    metric_name = Column(String(100))                   # followers, rating, engagement_rate, ad_count, etc.
    previous_value = Column(Float)                      # Value before change
    current_value = Column(Float)                       # Value after change
    change_percent = Column(Float)                      # Percentage change
    is_brand = Column(Boolean, default=False)           # Signal about own brand vs competitor
    is_read = Column(Boolean, default=False, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)

    competitor = relationship("Competitor", backref="signals")


class UserAdvertiser(Base):
    """Many-to-many: users ↔ advertisers."""
    __tablename__ = "user_advertisers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.id"), nullable=False, index=True)
    role = Column(String(20), default="owner")  # owner, member
    added_at = Column(DateTime, default=datetime.utcnow)


class AdvertiserCompetitor(Base):
    """Many-to-many: advertisers ↔ competitors."""
    __tablename__ = "advertiser_competitors"

    id = Column(Integer, primary_key=True, index=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.id"), nullable=False, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False, index=True)
    is_brand = Column(Boolean, default=False)
    added_at = Column(DateTime, default=datetime.utcnow)


class SystemSetting(Base):
    """Key-value store for system settings (API keys, etc.)."""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PromptTemplate(Base):
    """Editable AI prompt templates for creative/social analysis."""
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, index=True)
    label = Column(String(100))
    prompt_text = Column(Text, nullable=False)
    model_id = Column(String(100))
    max_tokens = Column(Integer, default=1024)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def _run_migrations(engine):
    """Add missing columns and indexes to existing tables."""
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        migrations = [
            ("users", "is_admin", "BOOLEAN DEFAULT FALSE"),
            ("competitors", "logo_url", "VARCHAR(500)"),
            ("advertisers", "logo_url", "VARCHAR(500)"),
            ("store_locations", "google_rating", "FLOAT"),
            ("store_locations", "google_reviews_count", "INTEGER"),
            ("store_locations", "google_place_id", "VARCHAR(255)"),
            ("store_locations", "rating_fetched_at", "TIMESTAMP"),
            # Creative Analysis columns
            ("geo_results", "user_id", "INTEGER REFERENCES users(id)"),
            ("serp_results", "user_id", "INTEGER REFERENCES users(id)"),
            ("competitors", "advertiser_id", "INTEGER REFERENCES advertisers(id)"),
            ("ads", "creative_analysis", "TEXT"),
            ("ads", "creative_concept", "VARCHAR(100)"),
            ("ads", "creative_hook", "VARCHAR(500)"),
            ("ads", "creative_tone", "VARCHAR(100)"),
            ("ads", "creative_text_overlay", "TEXT"),
            ("ads", "creative_dominant_colors", "VARCHAR(100)"),
            ("ads", "creative_has_product", "BOOLEAN"),
            ("ads", "creative_has_face", "BOOLEAN"),
            ("ads", "creative_has_logo", "BOOLEAN"),
            ("ads", "creative_layout", "VARCHAR(50)"),
            ("ads", "creative_cta_style", "VARCHAR(50)"),
            ("ads", "creative_score", "INTEGER"),
            ("ads", "creative_tags", "TEXT"),
            ("ads", "creative_summary", "TEXT"),
            ("ads", "creative_analyzed_at", "TIMESTAMP"),
            ("competitors", "is_brand", "BOOLEAN DEFAULT FALSE"),
            # Advertiser scoping for GEO/SEO results
            ("geo_results", "advertiser_id", "INTEGER REFERENCES advertisers(id)"),
            ("serp_results", "advertiser_id", "INTEGER REFERENCES advertisers(id)"),
            ("stores", "gps_verified", "BOOLEAN DEFAULT FALSE"),
            ("ads", "ad_type", "VARCHAR(20)"),
            ("competitors", "child_page_ids", "TEXT"),
            ("ads", "payer", "VARCHAR(500)"),
            ("ads", "beneficiary", "VARCHAR(500)"),
            # Product classification (AI-powered, LSA taxonomy)
            ("ads", "product_category", "VARCHAR(100)"),
            ("ads", "product_subcategory", "VARCHAR(100)"),
            ("ads", "ad_objective", "VARCHAR(50)"),
            ("competitors", "snapchat_entity_name", "VARCHAR(255)"),
            ("advertisers", "snapchat_entity_name", "VARCHAR(255)"),
            ("competitors", "snapchat_username", "VARCHAR(100)"),
            ("advertisers", "snapchat_username", "VARCHAR(100)"),
            # Enriched creative fields
            ("ads", "promo_type", "VARCHAR(50)"),
            ("ads", "creative_format", "VARCHAR(50)"),
            ("ads", "price_visible", "BOOLEAN"),
            ("ads", "price_value", "VARCHAR(20)"),
            ("ads", "seasonal_event", "VARCHAR(50)"),
            # MCP API key
            ("users", "mcp_api_key", "VARCHAR(64)"),
            # Mobsuccess auth
            ("users", "ms_user_id", "INTEGER"),
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
            ("ads", "creative_concept"),
            ("ads", "creative_tone"),
            ("ads", "creative_score"),
            ("ads", "product_category"),
            ("ads", "ad_objective"),
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


def _backfill_competitor_advertiser(engine):
    """Backfill advertiser_id on competitors that have user_id but no advertiser_id."""
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            # For each competitor with user_id but no advertiser_id,
            # assign the user's first active advertiser
            rows = conn.execute(text(
                'SELECT c.id, c.user_id FROM competitors c '
                'WHERE c.user_id IS NOT NULL AND c.advertiser_id IS NULL'
            )).fetchall()
            for comp_id, uid in rows:
                adv = conn.execute(text(
                    'SELECT id FROM advertisers WHERE user_id = :uid AND is_active = 1 ORDER BY id LIMIT 1'
                ), {"uid": uid}).fetchone()
                if adv:
                    conn.execute(text(
                        'UPDATE competitors SET advertiser_id = :aid WHERE id = :cid'
                    ), {"aid": adv[0], "cid": comp_id})
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Competitor advertiser backfill warning: {e}")


def _backfill_is_brand(engine):
    """Mark competitor mirror entries that represent the brand itself."""
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            # A competitor is a brand mirror if its name matches the advertiser's company_name
            rows = conn.execute(text(
                'SELECT c.id FROM competitors c '
                'JOIN advertisers a ON c.advertiser_id = a.id '
                'WHERE LOWER(c.name) = LOWER(a.company_name) '
                'AND c.is_active = 1 AND (c.is_brand IS NULL OR c.is_brand = 0)'
            )).fetchall()
            for (comp_id,) in rows:
                conn.execute(text(
                    'UPDATE competitors SET is_brand = 1 WHERE id = :cid'
                ), {"cid": comp_id})
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"is_brand backfill warning: {e}")


def deduplicate_competitors(engine) -> int:
    """Merge duplicate competitors (by facebook_page_id then by name). Returns count of merged."""
    from sqlalchemy import text

    is_pg = DATABASE_URL.startswith("postgresql")
    agg_fn = "STRING_AGG(id::text, ',')" if is_pg else "GROUP_CONCAT(id)"
    true_val = "true" if is_pg else "1"

    merged_ids: set[int] = set()

    with engine.begin() as conn:
        # 1. Find duplicates by facebook_page_id
        dupes_by_fbid = conn.execute(text(
            f'SELECT LOWER(facebook_page_id), {agg_fn} as ids '
            'FROM competitors '
            f"WHERE facebook_page_id IS NOT NULL AND facebook_page_id != '' AND is_active = {true_val} "
            'GROUP BY LOWER(facebook_page_id) HAVING COUNT(*) > 1'
        )).fetchall()

        for row in dupes_by_fbid:
            ids = [int(x) for x in row[1].split(",")]
            _merge_competitor_group(conn, ids, merged_ids)

        # 2. Find duplicates by exact lowercase name (skip already merged)
        dupes_by_name = conn.execute(text(
            f'SELECT LOWER(name), {agg_fn} as ids '
            'FROM competitors '
            f'WHERE is_active = {true_val} '
            'GROUP BY LOWER(name) HAVING COUNT(*) > 1'
        )).fetchall()

        for row in dupes_by_name:
            ids = [int(x) for x in row[1].split(",")]
            ids = [i for i in ids if i not in merged_ids]
            if len(ids) > 1:
                _merge_competitor_group(conn, ids, merged_ids)

    return len(merged_ids)


def _migrate_join_tables(engine):
    """Populate user_advertisers and advertiser_competitors from legacy FK columns, then deduplicate competitors."""
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        if "user_advertisers" not in existing_tables or "advertiser_competitors" not in existing_tables:
            return  # Tables not yet created (create_all hasn't run)

        is_pg = DATABASE_URL.startswith("postgresql")
        true_val = "true" if is_pg else "1"

        # --- 1 & 2: Populate join tables (separate transaction so dedup failure can't roll this back) ---
        with engine.begin() as conn:
            conn.execute(text(
                'INSERT INTO user_advertisers (user_id, advertiser_id, role) '
                "SELECT user_id, id, 'owner' FROM advertisers "
                'WHERE user_id IS NOT NULL '
                'AND NOT EXISTS (SELECT 1 FROM user_advertisers ua '
                '  WHERE ua.user_id = advertisers.user_id AND ua.advertiser_id = advertisers.id)'
            ))

            false_val = "false" if is_pg else "0"
            true_val = "true" if is_pg else "1"
            conn.execute(text(
                'INSERT INTO advertiser_competitors (advertiser_id, competitor_id, is_brand) '
                f'SELECT advertiser_id, id, COALESCE(is_brand, {false_val}) FROM competitors '
                f'WHERE advertiser_id IS NOT NULL AND is_active = {true_val} '
                'AND NOT EXISTS (SELECT 1 FROM advertiser_competitors ac '
                '  WHERE ac.advertiser_id = competitors.advertiser_id AND ac.competitor_id = competitors.id)'
            ))

        # --- 3: Deduplicate competitors ---
        try:
            deduplicate_competitors(engine)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Dedup warning: {e}")

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Join table migration warning: {e}")


def _merge_competitor_group(conn, ids: list[int], merged_ids: set[int]):
    """Merge a group of duplicate competitors into the canonical one (most ads)."""
    from sqlalchemy import text

    # Find canonical: the one with the most ads
    best_id = ids[0]
    best_count = 0
    for cid in ids:
        count = conn.execute(text(
            'SELECT COUNT(*) FROM ads WHERE competitor_id = :cid'
        ), {"cid": cid}).scalar() or 0
        if count > best_count:
            best_count = count
            best_id = cid

    others = [i for i in ids if i != best_id]
    if not others:
        return

    for other_id in others:
        # Re-point all FK references to canonical
        for fk_table in ("ads", "instagram_data", "app_data", "tiktok_data", "youtube_data",
                         "store_locations", "social_posts", "serp_results", "geo_results",
                         "ad_snapshots", "signals", "google_trends_data", "google_news_articles"):
            try:
                conn.execute(text(
                    f'UPDATE "{fk_table}" SET competitor_id = :canonical WHERE competitor_id = :old'
                ), {"canonical": best_id, "old": other_id})
            except Exception:
                pass  # Table might not exist

        # Move advertiser_competitors links to canonical (avoid duplicates)
        # First delete links that would cause duplicates
        conn.execute(text(
            'DELETE FROM advertiser_competitors WHERE competitor_id = :old '
            'AND advertiser_id IN (SELECT advertiser_id FROM advertiser_competitors WHERE competitor_id = :canonical)'
        ), {"canonical": best_id, "old": other_id})
        # Then move remaining links
        conn.execute(text(
            'UPDATE advertiser_competitors SET competitor_id = :canonical '
            'WHERE competitor_id = :old'
        ), {"canonical": best_id, "old": other_id})

        # Soft-delete the duplicate
        conn.execute(text(
            'UPDATE competitors SET is_active = 0 WHERE id = :old'
        ), {"old": other_id})

        # Complement canonical with missing fields from duplicate
        canonical = conn.execute(text(
            'SELECT website, facebook_page_id, instagram_username, playstore_app_id, '
            'appstore_app_id, tiktok_username, youtube_channel_id, snapchat_entity_name, snapchat_username, logo_url '
            'FROM competitors WHERE id = :cid'
        ), {"cid": best_id}).fetchone()
        donor = conn.execute(text(
            'SELECT website, facebook_page_id, instagram_username, playstore_app_id, '
            'appstore_app_id, tiktok_username, youtube_channel_id, snapchat_entity_name, snapchat_username, logo_url '
            'FROM competitors WHERE id = :cid'
        ), {"cid": other_id}).fetchone()

        fields = ["website", "facebook_page_id", "instagram_username", "playstore_app_id",
                   "appstore_app_id", "tiktok_username", "youtube_channel_id", "snapchat_entity_name", "snapchat_username", "logo_url"]
        for i, field in enumerate(fields):
            if not canonical[i] and donor[i]:
                conn.execute(text(
                    f'UPDATE competitors SET "{field}" = :val WHERE id = :cid'
                ), {"val": donor[i], "cid": best_id})

        merged_ids.add(other_id)


def _add_unique_constraints(engine):
    """Add unique constraints on join tables (idempotent)."""
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        for table, cols, idx_name in [
            ("user_advertisers", ["user_id", "advertiser_id"], "uq_user_advertiser"),
            ("advertiser_competitors", ["advertiser_id", "competitor_id"], "uq_advertiser_competitor"),
        ]:
            if table not in existing_tables:
                continue
            existing_idx = {idx["name"] for idx in inspector.get_indexes(table)}
            if idx_name not in existing_idx:
                col_list = ", ".join(f'"{c}"' for c in cols)
                with engine.begin() as conn:
                    conn.execute(text(
                        f'CREATE UNIQUE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ({col_list})'
                    ))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Unique constraint warning: {e}")


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations(engine)
    _add_unique_constraints(engine)
    _backfill_logos(engine)
    _backfill_competitor_advertiser(engine)
    _backfill_is_brand(engine)
    _migrate_join_tables(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
