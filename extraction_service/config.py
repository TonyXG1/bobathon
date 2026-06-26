"""Configuration management using pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database
    database_url: str = Field(
        default="sqlite:///./regulatory_radar.db",
        description="Database connection URL (SQLite or PostgreSQL)"
    )
    
    # CELLAR/EUR-Lex
    cellar_sparql_endpoint: str = Field(
        default="http://publications.europa.eu/webapi/rdf/sparql",
        description="CELLAR SPARQL endpoint URL"
    )
    cellar_rest_base_url: str = Field(
        default="https://eur-lex.europa.eu/legal-content/EN/TXT/",
        description="CELLAR REST API base URL for Formex XML"
    )
    cellar_max_connections: int = Field(
        default=5,
        description="Maximum concurrent connections to CELLAR"
    )
    cellar_timeout: int = Field(
        default=60,
        description="Request timeout in seconds for CELLAR"
    )
    cellar_page_size: int = Field(
        default=100,
        description="Number of results per SPARQL query page"
    )
    
    # ECHA
    echa_candidate_list_url: str = Field(
        default="https://echa.europa.eu/candidate-list-table",
        description="ECHA SVHC Candidate List URL"
    )
    echa_cache_ttl_hours: int = Field(
        default=24,
        description="Cache TTL for ECHA data in hours"
    )
    echa_timeout: int = Field(
        default=30,
        description="Request timeout in seconds for ECHA"
    )
    
    # HTTP Client
    user_agent: str = Field(
        default="RegulatoryRadar/1.0 (contact: team@example.com)",
        description="User-Agent header for polite client behavior"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed requests"
    )
    retry_backoff_factor: float = Field(
        default=2.0,
        description="Exponential backoff factor for retries"
    )
    
    # Taxonomy
    taxonomy_path: str = Field(
        default="dataset/taxonomy.json",
        description="Path to taxonomy.json file"
    )
    
    # Feature Flags
    enable_cellar_sparql: bool = Field(
        default=True,
        description="Enable CELLAR SPARQL discovery"
    )
    enable_echa_fetch: bool = Field(
        default=True,
        description="Enable ECHA SVHC list fetching"
    )
    
    # API
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )
    api_port: int = Field(
        default=8081,
        description="API server port"
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:8501", "http://localhost:5173"],
        description="Allowed CORS origins"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )


# Global settings instance
settings = Settings()
