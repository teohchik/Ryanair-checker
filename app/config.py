from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str
    admin_id: int
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"
    check_interval_hours: int = Field(default=6, ge=1, le=24)
    currency: str = "EUR"
    log_level: str = "INFO"
    log_json: bool = False


settings = Settings()
