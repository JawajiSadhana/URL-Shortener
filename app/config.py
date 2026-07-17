from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    base_url: str
    admin_api_key: str = ""
    db_url: str = "sqlite:///./url_shortener.db"
    cors_origins: str = ""
    slug_length: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
