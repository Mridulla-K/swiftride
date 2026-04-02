"""Shared configuration loader — reads from environment / .env file."""

from __future__ import annotations

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class CommonSettings(BaseSettings):
    """Settings shared by every service."""

    # PostgreSQL
    postgres_user: str = "swiftride"
    postgres_password: str = "swiftride_secret"
    postgres_db: str = "swiftride"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "swiftride-group"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> CommonSettings:
    return CommonSettings()
