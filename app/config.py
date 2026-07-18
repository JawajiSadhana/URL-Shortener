from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    base_url: str
    admin_api_key: str = ""
    db_url: str = "sqlite:///./url_shortener.db"
    cors_origins: str = ""
    slug_length: int = 7
    approval_store_backend: str = "sqlite"
    redis_url: str = "redis://localhost:6379/0"
    approval_ttl_seconds: int = 3600
    default_search_model: str = "gpt-3.5-cheap"
    default_reasoning_model: str = "gpt-4-expensive"
    cost_per_1k_tokens: float = 0.002
    expensive_model_multiplier: float = 10.0
    max_task_retries: int = 3
    execution_budget_limit: float = 10.0
    enable_cost_controls: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
