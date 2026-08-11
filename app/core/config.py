import os

from pydantic import field_validator
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
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-lite-preview-02-05:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    HTTP_TIMEOUT_SECONDS: float = 30.0

    @field_validator("OPENROUTER_API_KEY", mode="before")
    @classmethod
    def clean_api_key(cls, v: str | None) -> str | None:
        """Strip whitespace and treat empty strings or unset keys as None."""
        if isinstance(v, str):
            cleaned = v.strip()
            if cleaned and not cleaned.startswith("#"):
                return cleaned
        if os.path.exists(".env"):
            try:
                with open(".env", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("OPENROUTER_API_KEY="):
                            val = line.split("=", 1)[1].strip()
                            if val and not val.startswith("#"):
                                return val
            except Exception:
                pass
        return None


settings = Settings()
