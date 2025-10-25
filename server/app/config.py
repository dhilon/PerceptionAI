from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # .../server
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    # fish
    FISH_API_KEY: str = ""
    # set mode: "asr_rest" (recommended MVP), "realtime_ws" (later), or "mock"
    FISH_MODE: str = "asr_rest"
    FISH_ASR_URL: str = "https://api.fish.audio/v1/asr"
    FISH_REALTIME_WS: str = (
        "wss://api.fish.audio/v1/realtime"  # if/when you try WS again
    )

    # db (optional)
    PG_DB: str = "empathai"
    PG_USER: str = "postgres"
    PG_PASS: str = "postgres"
    PG_HOST: str = "127.0.0.1"
    PG_PORT: int = 5432

    model_config = SettingsConfigDict(env_file=str(ENV_PATH), env_file_encoding="utf-8")
