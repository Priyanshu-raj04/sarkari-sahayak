"""Typed application settings loaded from environment variables / .env."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Profile(StrEnum):
    LOCAL = "local"  # Mac: ParadeDB + Ollama + full models
    CI = "ci"  # GitHub Actions: replayed LLM calls, small models
    HOSTED = "hosted"  # Render: Neon + bm25s + ONNX e5 + Groq
    CODESPACES = "codespaces"  # like LOCAL but CPU-only, API LLMs


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SAHAYAK_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    profile: Profile = Profile.LOCAL
    log_level: str = "INFO"
    log_json: bool = False

    database_url: str = "postgresql://sahayak:sahayak@localhost:5432/sahayak"

    ollama_base_url: str = "http://localhost:11434"
    agent_model: str = "ollama_chat/qwen3:4b-instruct"
    fallback_models: list[str] = Field(default_factory=list)

    groq_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    embed_model: str = "intfloat/multilingual-e5-small"
    onnx_model_dir: str = "models/e5-small-onnx"  # hosted profile (S6)
    top_k: int = Field(default=8, ge=1, le=50)

    rate_limit_per_minute: int = Field(default=10, ge=1)
    daily_request_budget: int = Field(default=800, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
