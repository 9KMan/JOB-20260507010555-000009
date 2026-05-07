from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Vehicle Intelligence Platform"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/vehicle_intel"
    redis_url: str = "redis://localhost:6379/0"
    scraper_interval: int = 300
    playwright_headless: bool = True
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
