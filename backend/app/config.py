from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/parking"
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MIN: int = 60
    REFRESH_TOKEN_TTL_DAYS: int = 30

    HEADSCALE_URL: str = ""
    HEADSCALE_API_KEY: str = ""

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    N8N_WEBHOOK_URL: str = ""

    PING_INTERVAL_SEC: int = 30
    PING_TIMEOUT_SEC: int = 2
    PING_FAIL_THRESHOLD: int = 3
    ONLINE_FRESHNESS_SECONDS: int = 90
    DEGRADED_LATENCY_MS: int = 150
    OFFLINE_AFTER_SECONDS: int = 120
    TELEMETRY_FRESHNESS_SECONDS: int = 300

    ACTIVATION_TOKEN_TTL_MINUTES: int = 15
    PUBLIC_WEB_URL: str = "http://13.140.180.178:3002"

    CORS_ORIGINS: str = "http://localhost:5173"
    PRESENCE_ONLINE_MINUTES: int = 5
    PRESENCE_RECENT_MINUTES: int = 30
    PRESENCE_WRITE_THROTTLE_SECONDS: int = 45
    TELEGRAM_WORKFLOW_ABANDON_MINUTES: int = 30


settings = Settings()
