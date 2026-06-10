from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "AITrading"
    app_version: str = "0.1.0"
    debug: bool = False

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    trader_password: str

    # Database
    database_url: str  # postgresql+asyncpg://user:pass@localhost:5432/aitrading
    postgres_db: str = "aitrading"
    postgres_user: str = "aitrading"
    postgres_password: str

    # Redis
    redis_url: str  # redis://:password@localhost:6379/0
    redis_password: str

    # MT5
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    trading_mode: str = "demo"  # "demo" | "live"
    mt5_mock: bool = False  # set true in CI

    # TradingView
    tradingview_webhook_secret: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Symbols to track
    symbols: list[str] = ["XAUUSD", "EURUSD", "BTCUSD"]


settings = Settings()  # type: ignore[call-arg]
