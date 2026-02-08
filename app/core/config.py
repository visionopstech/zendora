from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database
    database_url: str
    
    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Stripe
    stripe_secret_key: str
    stripe_publishable_key: str
    stripe_webhook_secret: str
    
    # SendGrid
    sendgrid_api_key: str
    sendgrid_from_email: str
    
    # Third-Party Auth
    third_party_auth_url: Optional[str] = None
    third_party_auth_token: Optional[str] = None
    
    # Frontend
    frontend_url: str = "http://localhost:3000"
    
    # Redis & Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None
    
    # Admin Panel
    admin_username: str = "admin"
    admin_password: str = "changeme"
    
    # Environment
    environment: str = "development"
    
    # CORS
    cors_origins: list[str] = ["*"]
    
    @property
    def get_celery_broker_url(self) -> str:
        """Get Celery broker URL, defaults to redis_url if not set."""
        return self.celery_broker_url or self.redis_url
    
    @property
    def get_celery_result_backend(self) -> str:
        """Get Celery result backend URL, defaults to redis_url if not set."""
        return self.celery_result_backend or self.redis_url
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Global settings instance
settings = Settings()
