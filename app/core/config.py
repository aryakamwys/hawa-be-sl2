from functools import lru_cache
import os

from pydantic import BaseModel


class Settings(BaseModel):
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    admin_secret_key: str = os.getenv("ADMIN_SECRET_KEY", "change-admin-secret-in-production")
    access_token_expire_minutes: int = 60 * 24  # 1 day
    algorithm: str = "HS256"
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    google_sheets_id: str | None = os.getenv("GOOGLE_SHEETS_ID", "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA")
    openweather_api_key: str | None = os.getenv("OPENWEATHER_API_KEY")
    
    # Rate Limiting Configuration
    iot_data_rate_limit: int = int(os.getenv("IOT_DATA_RATE_LIMIT", "50"))  # requests per minute
    ai_recommendation_rate_limit: int = int(os.getenv("AI_RECOMMENDATION_RATE_LIMIT", "30"))  # requests per minute
    
    # Cache Configuration
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "1"))  # 1 second for realtime
    realtime_window_seconds: int = int(os.getenv("REALTIME_WINDOW_SECONDS", "60"))  # 60 second window


@lru_cache
def get_settings() -> Settings:
    return Settings()


