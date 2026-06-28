from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "Nova Earns"
    app_env: str = "production"
    secret_key: str = ""
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./test.db"

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Email
    resend_api_key: str 
    email_from: str = "Nova Earns <onboarding@onboarding.novaearns.online>"

    # CORS
    allowed_origins: str = "http://localhost:8000"

    # Rate Limiting
    rate_limit_per_minute: int = 60
    login_rate_limit_per_minute: int = 5

    # Security
    max_failed_login_attempts: int = 5
    account_lockout_minutes: int = 15

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
