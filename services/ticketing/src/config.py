import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "ticketing-service")
    PORT: int = int(os.getenv("PORT", 8005))
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://ticketing_user:ticketing_pass@postgres:5432/ticketing_db"
    )
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
