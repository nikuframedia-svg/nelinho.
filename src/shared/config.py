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
        default="postgresql+asyncpg://prodplan:prodplan@localhost:5432/prodplan_one",
        description="PostgreSQL connection URL (async). Override via DATABASE_URL env var.",
    )
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=100)
    database_echo: bool = Field(default=False)

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL. Override via REDIS_URL env var.",
    )
    redis_pool_size: int = Field(default=10, ge=1, le=100)

    # Kafka
    kafka_bootstrap_servers: str = Field(
        default="localhost:29092",
        description="Kafka bootstrap servers (comma-separated)",
    )
    kafka_consumer_group: str = Field(default="prodplan-one")
    kafka_auto_offset_reset: str = Field(default="earliest")

    # Nelo SQL Server ERP (Sprint B.3 — read-only adapter)
    # The factory ERP lives on a separate server on the Nelo LAN.
    # Leave `sqlserver_enabled=False` (the default) to skip the adapter —
    # the rest of the system keeps working on the curated Excel ingest.
    sqlserver_enabled: bool = Field(
        default=False,
        description="Flip to True once the Nelo ERP adapter is configured",
    )
    sqlserver_url: Optional[str] = Field(
        default=None,
        description=(
            "Async SQLAlchemy URL for the Nelo ERP. Example: "
            "'mssql+aioodbc://user:pass@nelo-erp.lan:1433/NELO_ERP"
            "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'"
        ),
    )
    sqlserver_pool_size: int = Field(default=5, ge=1, le=20)
    sqlserver_query_timeout_s: int = Field(default=30, ge=1, le=300)

    # Security
    secret_key: str = Field(
        default="dev-only-insecure-key-override-in-production-via-env",
        min_length=32,
    )
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    algorithm: str = Field(default="HS256")
    jwt_issuer: Optional[str] = Field(
        default=None,
        description="Expected `iss` claim. If set, tokens missing/mismatching are rejected.",
    )
    jwt_audience: Optional[str] = Field(
        default=None,
        description="Expected `aud` claim. If set, tokens missing/mismatching are rejected.",
    )

    @field_validator("algorithm")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        """Reject `none` algorithm — JWTs must be signed."""
        if v.strip().lower() in ("none", ""):
            raise ValueError(
                "JWT algorithm 'none' is forbidden. Use HS256/RS256/ES256 etc."
            )
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        """Block insecure default secrets in production."""
        insecure_markers = ["dev-only", "change_in_production", "_secret_2026", "insecure"]
        env = info.data.get("environment", "development") if info.data else "development"
        if env.lower() in ("production", "prod"):
            if any(marker in v.lower() for marker in insecure_markers):
                raise ValueError(
                    "SECRET_KEY contains insecure default value. "
                    "Set a strong secret via SECRET_KEY env var for production."
                )
        return v
    
    # Environment
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Sprint Q.18.A.2 — global RBAC enforcement.
    # Off by default in dev so the existing test client and admin pages
    # don't have to wear roles in every fixture. main.py forces it on
    # whenever environment == "production". Flip via env to opt-in
    # locally: ``PRODPLAN_RBAC_STRICT=true``.
    rbac_strict: bool = Field(
        default=False,
        description=(
            "Enforce ROUTE_PREFIX_REQUIREMENTS via RBACMiddleware on every "
            "request. Auto-enabled in production."
        ),
    )
    
    # CORS — Windows/Vite serve em 127.0.0.1 por defeito quando arrancado via
    # --host 127.0.0.1; browsers tratam localhost ≠ 127.0.0.1 como origens
    # distintas para CORS. Permitir ambas evita "Failed to fetch" silencioso
    # no boot loader (CapabilitiesProvider).
    cors_origins: str = Field(
        default=(
            "http://localhost:3000,http://localhost:5173,"
            "http://127.0.0.1:3000,http://127.0.0.1:5173"
        )
    )
    
    # COPILOT
    copilot_enabled: bool = Field(default=True)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="gemma4:e4b")
    ollama_num_ctx: int = Field(default=4096, ge=2048, le=131072, description="Context window size")
    ollama_keep_alive: str = Field(default="30m", description="How long to keep model in VRAM")
    ollama_temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="LLM temperature (low = deterministic)")
    ollama_num_predict: int = Field(default=512, ge=64, le=8192, description="Max tokens to generate")
    copilot_embeddings_model: str = Field(default="nomic-embed-text")
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










