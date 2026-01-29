"""
ProdPlan ONE - Configuration Management
========================================

Centralized configuration using pydantic-settings.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://prodplan:prodplan_secret_2026@localhost:5432/prodplan_one",
        description="PostgreSQL connection URL (async)",
    )
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=100)
    database_echo: bool = Field(default=False)
    
    # Redis
    redis_url: str = Field(
        default="redis://:redis_secret_2026@localhost:6379/0",
        description="Redis connection URL",
    )
    redis_pool_size: int = Field(default=10, ge=1, le=100)
    
    # Kafka
    kafka_bootstrap_servers: str = Field(
        default="localhost:29092",
        description="Kafka bootstrap servers (comma-separated)",
    )
    kafka_consumer_group: str = Field(default="prodplan-one")
    kafka_auto_offset_reset: str = Field(default="earliest")
    
    # Security
    secret_key: str = Field(
        default="prodplan_jwt_secret_key_2026_change_in_production",
        min_length=32,
    )
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    algorithm: str = Field(default="HS256")
    
    # Environment
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # CORS
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5173")
    
    # COPILOT
    copilot_enabled: bool = Field(default=True)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3:8b")  # Usar modelo disponível (pode ser override via .env)
    copilot_embeddings_model: str = Field(default="all-minilm")
    copilot_rate_limit_per_hour: int = Field(default=60, ge=1)
    copilot_rate_limit_per_day: int = Field(default=300, ge=1)
    copilot_trust_index_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() in ("development", "dev", "local")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() in ("production", "prod")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return upper_v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience export
settings = get_settings()










