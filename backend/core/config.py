"""
Application configuration.
Centralized settings loaded from environment variables.
"""
import os
from pathlib import Path
from functools import lru_cache


class Settings:
    """Application settings."""

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./competitive.db")

    # Meta/Facebook API
    META_APP_ID: str = os.getenv("META_APP_ID", "")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")
    META_ACCESS_TOKEN: str = os.getenv("META_ACCESS_TOKEN", "")

    # YouTube API
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")

    # ScrapeCreators API
    SCRAPECREATORS_API_KEY: str = os.getenv("SCRAPECREATORS_API_KEY", "")

    # Anthropic Claude API (for AI creative analysis)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Google Gemini API (for GEO tracking)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # OpenAI API (for GEO tracking - ChatGPT)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Mistral API (for GEO tracking - Le Chat)
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")

    # Scheduler
    SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    SCHEDULER_HOUR: int = int(os.getenv("SCHEDULER_HOUR", "2"))
    SCHEDULER_MINUTE: int = int(os.getenv("SCHEDULER_MINUTE", "0"))

    # Data.gouv.fr cache
    DATAGOUV_CACHE_DIR: Path = Path(os.getenv("DATAGOUV_CACHE_DIR", "./cache/datagouv"))
    DATAGOUV_CACHE_DAYS: int = int(os.getenv("DATAGOUV_CACHE_DAYS", "7"))

    # Auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    JWT_EXPIRATION_DAYS: int = int(os.getenv("JWT_EXPIRATION_DAYS", "7"))

    # Rate limiting
    MIN_FETCH_INTERVAL_HOURS: int = 1


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
