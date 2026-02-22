"""
Pydantic schemas - Product-First Design
Pour une tête de réseau retail supervisant le digital de ses enseignes.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    RATING_CHANGE = "rating_change"
    FOLLOWER_SPIKE = "follower_spike"
    APP_UPDATE = "app_update"
    NEW_AD = "new_ad"
    RANKING_CHANGE = "ranking_change"


class Channel(str, Enum):
    PLAYSTORE = "playstore"
    APPSTORE = "appstore"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


# =============================================================================
# Core Building Blocks
# =============================================================================

class Trend(BaseModel):
    """Indicateur de tendance."""
    direction: TrendDirection
    value: float = Field(description="Variation absolue")
    percent: float = Field(description="Variation en %")
    period: str = Field(default="7d", description="Période de comparaison")


class MetricValue(BaseModel):
    """Valeur d'une métrique avec tendance optionnelle."""
    value: float
    label: str
    trend: Optional[Trend] = None
    rank: Optional[int] = Field(default=None, description="Position vs concurrents")


# =============================================================================
# Brand (Mon Enseigne)
# =============================================================================

class BrandSetup(BaseModel):
    """Onboarding initial de l'enseigne."""
    company_name: str = Field(description="Nom de l'enseigne")
    sector: str = Field(description="Secteur d'activité")
    website: Optional[str] = None
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None


class BrandProfile(BaseModel):
    """Profil complet de mon enseigne."""
    id: int
    company_name: str
    sector: str
    sector_label: str
    website: Optional[str] = None

    # Identifiants des canaux
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None

    # Stats actuelles
    channels_configured: int = Field(description="Nombre de canaux configurés")
    competitors_tracked: int = Field(description="Nombre de concurrents suivis")

    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Watch (Veille Concurrentielle)
# =============================================================================

class MarketPosition(BaseModel):
    """Position de mon enseigne dans le marché."""
    global_rank: int = Field(description="Rang global parmi les concurrents")
    total_players: int = Field(description="Nombre total d'acteurs suivis")
    global_score: float = Field(description="Score composite 0-100")
    score_trend: Optional[Trend] = None


class KeyMetric(BaseModel):
    """Métrique clé pour le dashboard."""
    id: str
    label: str
    my_value: Optional[float] = None
    my_formatted: str = Field(description="Valeur formatée (ex: '4.2M')")
    best_competitor: Optional[str] = None
    best_value: Optional[float] = None
    best_formatted: Optional[str] = None
    my_rank: int
    trend: Optional[Trend] = None


class WatchOverview(BaseModel):
    """Vue d'ensemble de la veille concurrentielle."""
    brand_name: str
    sector: str
    last_updated: datetime

    # Position dans le marché
    position: MarketPosition

    # KPIs clés (les 4-6 plus importants)
    key_metrics: List[KeyMetric]

    # Résumé textuel
    summary: str = Field(description="Ex: 'Vous êtes 2ème sur les apps, mais 4ème sur Instagram'")

    # Alertes récentes (preview)
    alerts_count: int
    critical_alerts: int


class Alert(BaseModel):
    """Alerte de veille concurrentielle."""
    id: str
    type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    competitor_name: Optional[str] = None
    channel: Optional[Channel] = None
    metric_change: Optional[Trend] = None
    detected_at: datetime
    is_read: bool = False


class AlertsList(BaseModel):
    """Liste paginée d'alertes."""
    total: int
    unread: int
    critical: int
    alerts: List[Alert]


class RankingEntry(BaseModel):
    """Entrée dans un classement."""
    rank: int
    competitor_name: str
    value: float
    formatted_value: str
    is_my_brand: bool = False
    trend: Optional[Trend] = None


class ChannelRanking(BaseModel):
    """Classement pour un canal donné."""
    channel: str
    channel_label: str
    metric: str
    metric_label: str
    my_rank: int
    total: int
    leaderboard: List[RankingEntry]


class Rankings(BaseModel):
    """Tous les classements."""
    updated_at: datetime
    rankings: List[ChannelRanking]


# =============================================================================
# Competitors
# =============================================================================

# =============================================================================
# Advertiser
# =============================================================================

class AdvertiserCreate(BaseModel):
    """Création d'un annonceur."""
    company_name: str
    sector: str
    website: Optional[str] = None
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None
    contact_email: Optional[str] = None


class AdvertiserUpdate(BaseModel):
    """Mise à jour d'un annonceur (tous les champs optionnels)."""
    company_name: Optional[str] = None
    sector: Optional[str] = None
    website: Optional[str] = None
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None
    contact_email: Optional[str] = None


class AdvertiserResponse(BaseModel):
    """Réponse annonceur."""
    id: int
    company_name: str
    sector: Optional[str] = None
    website: Optional[str] = None
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdvertiserOnboarding(BaseModel):
    """Onboarding complet d'un annonceur."""
    company_name: str
    sector: str
    website: Optional[str] = None
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None
    contact_email: Optional[str] = None
    selected_competitors: Optional[List[str]] = None


# =============================================================================
# Competitors
# =============================================================================

class CompetitorCreate(BaseModel):
    """Création d'un concurrent."""
    name: str
    website: Optional[str] = None
    facebook_page_id: Optional[str] = None
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None


class CompetitorUpdate(BaseModel):
    """Mise à jour d'un concurrent (tous les champs optionnels)."""
    name: Optional[str] = None
    website: Optional[str] = None
    facebook_page_id: Optional[str] = None
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None
    child_page_ids: Optional[str] = None  # JSON array of child Facebook page IDs


class CompetitorCard(BaseModel):
    """Carte synthétique d'un concurrent."""
    id: int
    name: str
    website: Optional[str] = None
    logo_url: Optional[str] = None

    # Identifiants des canaux
    facebook_page_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None

    # Score et position
    global_score: float = Field(description="Score composite 0-100")
    rank: int

    # Métriques principales (les plus récentes)
    app_rating: Optional[float] = None
    app_downloads: Optional[str] = None
    instagram_followers: Optional[int] = None
    tiktok_followers: Optional[int] = None
    youtube_subscribers: Optional[int] = None

    # Tendance globale
    trend: Optional[Trend] = None

    # Canaux actifs
    active_channels: List[str]

    # Date d'ajout
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChannelData(BaseModel):
    """Données d'un canal pour un concurrent."""
    channel: str
    is_configured: bool
    last_updated: Optional[datetime] = None
    metrics: Dict[str, MetricValue]


class CompetitorDetail(BaseModel):
    """Profil détaillé d'un concurrent."""
    id: int
    name: str
    website: Optional[str] = None

    # Identifiants
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None

    # Score
    global_score: float
    rank: int

    # Données par canal
    channels: Dict[str, ChannelData]

    # Historique récent
    recent_changes: List[Alert]

    created_at: datetime

    class Config:
        from_attributes = True


class CompetitorSuggestion(BaseModel):
    """Suggestion de concurrent."""
    name: str
    website: Optional[str] = None
    sector: str
    playstore_app_id: Optional[str] = None
    appstore_app_id: Optional[str] = None
    instagram_username: Optional[str] = None
    tiktok_username: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    snapchat_entity_name: Optional[str] = None
    snapchat_username: Optional[str] = None
    already_tracked: bool = False


# =============================================================================
# Channels (Détail par canal)
# =============================================================================

class AppMetrics(BaseModel):
    """Métriques apps (Play Store + App Store)."""
    competitor_id: int
    competitor_name: str

    # Play Store
    playstore_rating: Optional[float] = None
    playstore_reviews: Optional[int] = None
    playstore_downloads: Optional[str] = None
    playstore_version: Optional[str] = None
    playstore_updated: Optional[datetime] = None

    # App Store
    appstore_rating: Optional[float] = None
    appstore_reviews: Optional[int] = None
    appstore_version: Optional[str] = None
    appstore_updated: Optional[datetime] = None

    # Combiné
    avg_rating: Optional[float] = None
    total_reviews: Optional[int] = None


class SocialMetrics(BaseModel):
    """Métriques social (Instagram + TikTok + YouTube)."""
    competitor_id: int
    competitor_name: str

    # Instagram
    instagram_followers: Optional[int] = None
    instagram_engagement: Optional[float] = None

    # TikTok
    tiktok_followers: Optional[int] = None
    tiktok_likes: Optional[int] = None

    # YouTube
    youtube_subscribers: Optional[int] = None
    youtube_views: Optional[int] = None

    # Combiné
    total_social_reach: Optional[int] = None


class ChannelComparison(BaseModel):
    """Comparaison multi-concurrents pour un canal."""
    channel: str
    channel_label: str
    metrics: List[str]
    data: List[Dict[str, Any]]
    my_brand_id: Optional[int] = None


# =============================================================================
# Sectors
# =============================================================================

class Sector(BaseModel):
    """Secteur d'activité."""
    code: str
    name: str
    competitors_count: int = Field(description="Nombre de concurrents pré-configurés")


# =============================================================================
# API Responses
# =============================================================================

class SetupResponse(BaseModel):
    """Réponse après onboarding."""
    brand: BrandProfile
    suggested_competitors: List[CompetitorSuggestion]
    message: str


class HealthCheck(BaseModel):
    """Statut de l'API."""
    status: str
    version: str
    brand_configured: bool
    competitors_count: int
    last_data_refresh: Optional[datetime] = None


# =============================================================================
# Legacy Schemas (pour compatibilité avec anciens routers)
# =============================================================================

class AdResponse(BaseModel):
    """Réponse pour les publicités."""
    id: int
    competitor_id: int
    ad_id: str
    platform: str
    creative_url: Optional[str] = None
    ad_text: Optional[str] = None
    cta: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class InstagramDataResponse(BaseModel):
    """Réponse données Instagram."""
    id: int
    competitor_id: int
    followers: int
    following: int
    posts_count: int
    avg_likes: Optional[float] = None
    avg_comments: Optional[float] = None
    engagement_rate: Optional[float] = None
    bio: Optional[str] = None
    recorded_at: datetime

    class Config:
        from_attributes = True


class AppDataResponse(BaseModel):
    """Réponse données App Store/Play Store."""
    id: int
    competitor_id: int
    store: str
    app_id: str
    app_name: str
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    downloads: Optional[str] = None
    downloads_numeric: Optional[int] = None
    version: Optional[str] = None
    last_updated: Optional[datetime] = None
    description: Optional[str] = None
    changelog: Optional[str] = None
    recorded_at: datetime

    class Config:
        from_attributes = True


class TikTokDataResponse(BaseModel):
    """Réponse données TikTok."""
    id: int
    competitor_id: int
    username: str
    followers: int
    following: int
    likes: int
    videos_count: int
    bio: Optional[str] = None
    verified: bool = False
    recorded_at: datetime

    class Config:
        from_attributes = True


class YouTubeDataResponse(BaseModel):
    """Réponse données YouTube."""
    id: int
    competitor_id: int
    channel_id: str
    channel_name: str
    subscribers: int
    total_views: int
    videos_count: int
    avg_views: Optional[int] = None
    avg_likes: Optional[int] = None
    avg_comments: Optional[int] = None
    engagement_rate: Optional[float] = None
    description: Optional[str] = None
    recorded_at: datetime

    class Config:
        from_attributes = True


# Alias pour compatibilité
TrendValue = Trend


class TrendResponse(BaseModel):
    """Réponse de tendance pour les endpoints /trends."""
    current: Dict[str, Any]
    previous: Optional[Dict[str, Any]] = None
    trends: Dict[str, Any]
