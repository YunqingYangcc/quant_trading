"""赛道量化系统 — 精简配置"""
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "track_quant"
    DEBUG: bool = True
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///" + str(Path(__file__).resolve().parent.parent / "track_quant.db"),
        description="数据库连接 URL",
    )
    DB_AUTO_CREATE_SCHEMA: bool = True
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    SQL_ECHO: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=(".env", str(Path(__file__).resolve().parents[1] / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )


_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
