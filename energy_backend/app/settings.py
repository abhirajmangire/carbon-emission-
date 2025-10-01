from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    cors_allow_origins: list[str] = ["*"]
    data_path: str = "energy_backend_data.json"


settings = AppSettings()

