from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized environment configuration.
    Populate a `.env` file at /backend/.env — never commit real secrets.
    """

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://ddm_user:ddm_pass@localhost:5432/deadhead_minimizer"

    # --- DAT Data Ingestion ---
    DAT_API_BASE_URL: str = "https://api.dat.com"
    DAT_API_KEY: str = ""
    DAT_EXTENSION_BRIDGE_WS_URL: str = "ws://localhost:8765/dat-bridge"

    # --- Twilio / Voice Negotiation ---
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_SIP_TRUNK_SID: str = ""
    TWILIO_OUTBOUND_CALLER_ID: str = ""

    # --- OpenAI Realtime API (voice negotiation agent) ---
    OPENAI_API_KEY: str = ""
    OPENAI_REALTIME_MODEL: str = "gpt-4o-realtime-preview"

    # --- App behavior defaults ---
    DEFAULT_DEADHEAD_RADIUS_MILES: float = 150.0
    MAX_DEADHEAD_RADIUS_MILES: float = 300.0
    RATE_NEGOTIATION_MIN_MARGIN_PCT: float = 5.0  # floor margin below asking RPM the AI won't cross

    # Comma-separated in the actual env var, e.g. "https://ddm-frontend.onrender.com,http://localhost:3000"
    # Kept as a plain string (not list[str]) — pydantic-settings tries to JSON-decode
    # env vars typed as complex types like lists before any validator runs, and a
    # plain comma-separated string like "http://localhost:3000" isn't valid JSON,
    # which crashes startup. Splitting it ourselves via the property below avoids that.
    CORS_ORIGINS: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """
        Railway (and most hosts) hand you a DATABASE_URL that starts with
        'postgres://' or 'postgresql://'. Our app uses the async driver, which
        needs 'postgresql+asyncpg://'. Rather than requiring every deploy to
        remember to edit the string, normalize it here.
        """
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
