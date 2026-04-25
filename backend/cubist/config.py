from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    anthropic_api_key: str = ""

    strategist_model: str = "claude-opus-4-6"
    player_model: str = "claude-sonnet-4-6"
    builder_model: str = "claude-sonnet-4-6"

    database_url: str = "sqlite:///./cubist.db"

    time_per_move_ms: int = 20_000
    games_per_pairing: int = 2
    max_moves_per_game: int = 120

    api_host: str = "127.0.0.1"
    api_port: int = 8000


settings = Settings()
