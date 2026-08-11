
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application Settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    PROJECT_NAME: str = "FastAPI MongoDB AI Chatbot"
    VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"

    # MongoDB Settings
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "ai_chat_db"

    # LLM & OpenRouter Settings
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    HTTP_TIMEOUT_SECONDS: float = 30.0


settings = Settings()
