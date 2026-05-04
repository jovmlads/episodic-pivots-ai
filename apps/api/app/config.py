import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_service_role_key: str
    supabase_db_url: str

    # AI
    anthropic_api_key: str
    openai_api_key: str

    # TradingView
    tradingview_cookie: str = ""

    # Langfuse (optional — omit to disable AI observability)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    # Email
    resend_api_key: str = ""
    resend_from_email: str = "noreply@example.com"

    # API
    api_secret_key: str
    allowed_origins: str = "http://localhost:3000"

    # Token limits
    default_monthly_token_budget: int = 1_000_000
    max_tickers_per_scan: int = 20
    min_scan_interval_minutes: int = 15

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()

# Bridge .env Langfuse keys into os.environ so the Langfuse SDK auto-detects them.
# pydantic-settings reads .env but does not set os.environ, so we do it here.
if settings.langfuse_public_key:
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_base_url)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_base_url)
