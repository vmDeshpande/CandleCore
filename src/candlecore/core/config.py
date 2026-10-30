from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://candlecore:candlecore@localhost:5432/candlecore"
    candlecore_test_database_url: str | None = None

    # Delta Exchange India - public endpoints only, no credentials required for CC-M1
    delta_rest_base_url: str = "https://api.india.delta.exchange"
    delta_ws_url: str = "wss://public-socket.india.delta.exchange"

    # CC-M1 collection scope (not a platform-wide primary timeframe)
    cc_m1_symbols: str = "BTCUSD,ETHUSD,SOLUSD"
    cc_m1_timeframes: str = "3m"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # HTTP retry settings (applied to safe, idempotent GET requests)
    http_max_retries: int = Field(default=5, ge=0, le=20)
    http_base_delay: float = Field(default=1.0, ge=0.0, le=60.0)
    http_max_delay: float = Field(default=60.0, ge=0.0, le=600.0)

    # HTTP timeout settings (seconds)
    http_timeout: float = Field(default=30.0, ge=1.0, le=300.0)

    # WebSocket reconnect settings
    ws_max_reconnect_delay: float = Field(default=60.0, ge=1.0, le=600.0)

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("database_url is required")
        return value.strip()

    @field_validator("delta_rest_base_url")
    @classmethod
    def _validate_rest_url(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("delta_rest_base_url is required")
        if not value.strip().startswith(("http://", "https://")):
            raise ValueError("delta_rest_base_url must be an HTTP(S) URL")
        return value.strip().rstrip("/")

    @field_validator("delta_ws_url")
    @classmethod
    def _validate_ws_url(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("delta_ws_url is required")
        if not value.strip().startswith(("ws://", "wss://")):
            raise ValueError("delta_ws_url must be a WebSocket WS(S) URL")
        return value.strip().rstrip("/")

    @field_validator("cc_m1_symbols")
    @classmethod
    def _validate_symbols(cls, value: str) -> str:
        symbols = [s.strip().upper() for s in value.split(",") if s.strip()]
        if not symbols:
            raise ValueError("at least one cc_m1 symbol is required")
        return ",".join(symbols)

    @field_validator("cc_m1_timeframes")
    @classmethod
    def _validate_timeframes(cls, value: str) -> str:
        timeframes = [t.strip() for t in value.split(",") if t.strip()]
        if not timeframes:
            raise ValueError("at least one cc_m1 timeframe is required")
        return ",".join(timeframes)

    @field_validator("api_port")
    @classmethod
    def _validate_api_port(cls, value: int) -> int:
        if value < 1 or value > 65535:
            raise ValueError("api_port must be a valid TCP port")
        return value

    @model_validator(mode="after")
    def _validate_retry_and_timeout(self) -> "Settings":
        if self.http_max_delay < self.http_base_delay:
            raise ValueError("http_max_delay must be >= http_base_delay")
        return self

    @property
    def symbol_list(self) -> list[str]:
        return [symbol.strip() for symbol in self.cc_m1_symbols.split(",") if symbol.strip()]

    @property
    def timeframe_list(self) -> list[str]:
        return [
            timeframe.strip() for timeframe in self.cc_m1_timeframes.split(",") if timeframe.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
