from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://candlecore:candlecore@localhost:5432/candlecore"
    delta_rest_base_url: str = "https://api.india.delta.exchange"
    delta_ws_url: str = "wss://public-socket.india.delta.exchange"
    symbols: str = "BTCUSD,ETHUSD,SOLUSD"
    default_timeframe: str = "3m"
    log_level: str = "INFO"
    log_format: str = "json"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def symbol_list(self) -> list[str]:
        return [s.strip() for s in self.symbols.split(",")]

@lru_cache
def get_settings() -> Settings:
    return Settings()
