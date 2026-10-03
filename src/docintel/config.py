from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCINTEL_", env_file=".env", extra="ignore")

    store_dir: Path = Path("var/store")
    max_attempts: int = 3
    review_confidence: float = 0.55
    api_key: str = ""
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
