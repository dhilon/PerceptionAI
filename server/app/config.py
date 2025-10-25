from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    FISH_API_KEY: str = ""
    FISH_REALTIME_WS: str = "wss://api.fish.audio/v1/realtime"
    PG_DB: str = "empathai"
    PG_USER: str = "postgres"
    PG_PASS: str = "postgres"
    PG_HOST: str = "127.0.0.1"
    PG_PORT: int = 5432

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
