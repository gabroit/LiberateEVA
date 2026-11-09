from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LiberateEVA"
    app_env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8000

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-2.0-flash-001"

    webhook_secret: str = "change-me"

    vector_db_path: str = "./data/chroma"
    sqlite_path: str = "./data/runtime.db"
    instance_registry_path: str = "./data/instance_registry.db"
    state_export_path: str = "./data/state"

    browser_headless: bool = True
    browser_timeout: int = 30000

    log_level: str = "INFO"
    agent_context_path: str = "agent_context.txt"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


def get_settings() -> Settings:
    return Settings()
