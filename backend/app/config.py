from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Later files win: a backend/.env overrides the repo-root .env, and the process environment
    # overrides both.
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"), extra="ignore"
    )

    gemini_api_key: str = ""
    gemini_model: str = ""
    allowed_origins: str = "http://localhost:5173"
    max_upload_mb: int = 5
    max_rows: int = 500
    # Deploy commit shown by /health. Render sets RENDER_GIT_COMMIT itself.
    git_sha: str = Field("unknown", validation_alias=AliasChoices("GIT_SHA", "RENDER_GIT_COMMIT"))

    # Optional Langfuse tracing for the agent; off unless both keys are set (app/agent/tracing.py).
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""
    price_ttl_seconds: int = 900

    # Abuse protection for the AI endpoints (see app/ratelimit.py).
    ai_requests_per_minute: int = 6  # per client
    ai_requests_per_day: int = 100  # per client
    ai_model_calls_per_day: int = 500  # all clients together
    trusted_proxy_hops: int = 1  # proxies in front of the app; 0 if exposed directly

    trading_days: int = 252
    risk_free_inr: float = 0.07
    risk_free_usd: float = 0.04
    min_history_days: int = 60
    max_ffill_days: int = 5

    snapshot_dir: Path = BACKEND_DIR / "data" / "price_snapshot"
    cache_dir: Path = BACKEND_DIR / "data" / "price_cache"
    sector_map_path: Path = BACKEND_DIR / "data" / "sector_map.csv"
    offline: bool = False  # when true, services never touch the network

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
