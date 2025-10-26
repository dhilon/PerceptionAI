from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

BASE_DIR = Path(__file__).resolve().parent.parent  # .../server
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    # fish
    FISH_API_KEY: str = ""
    # set mode: "asr_rest" (recommended MVP), "realtime_ws" (later), or "mock"
    FISH_MODE: str = os.getenv("FISH_MODE")
    FISH_ASR_URL: str = os.getenv("FISH_ASR_URL")
    FISH_REALTIME_WS: str = os.getenv("FISH_REALTIME_WS")

    # db (optional)
    PG_DB: str = "perceptionai"
    PG_USER: str = "postgres"
    PG_PASS: str = "postgres"
    PG_HOST: str = "127.0.0.1"
    PG_PORT: int = 5432

    model_config = SettingsConfigDict(env_file=str(ENV_PATH), env_file_encoding="utf-8")
