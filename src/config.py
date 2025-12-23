from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from pydantic import BaseSettings, HttpUrl, PositiveInt, conint


class Settings(BaseSettings):
    """Runtime configuration for the knowledge system."""

    base_url: HttpUrl
    allowed_domains: list[str]
    user_agent: str = "ai-knowledge-bot/1.0"
    max_depth: conint(ge=1, le=8) = 3
    max_pages: Optional[PositiveInt] = 500
    request_timeout: float = 10.0
    rate_limit_per_second: float = 1.5
    content_chunk_size: PositiveInt = 750
    content_chunk_overlap: conint(ge=0, le=400) = 100
    embed_model: str = "all-MiniLM-L6-v2"
    chroma_path: Path = Path(".chroma")
    metadata_db_path: Path = Path("data/metadata.db")
    slack_webhook: Optional[str] = None

    class Config:
        env_file = ".env"
        env_prefix = "AIKB_"


DEFAULT_SETTINGS = Settings(  # type: ignore[arg-type]
    base_url="https://example.com",
    allowed_domains=["example.com"],
)


def settings_from_env(overrides: Optional[dict] = None) -> Settings:
    """Load settings while allowing test overrides."""

    values = overrides or {}
    return Settings(**values)


def allowed_domain(url: str, allowed: Iterable[str]) -> bool:
    return any(domain in url for domain in allowed)
