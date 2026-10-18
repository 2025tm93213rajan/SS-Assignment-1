import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "inventory-service")
    PORT: int = int(os.getenv("PORT", 8002))
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://inventory_user:inventory_pass@postgres:5432/inventory_db"
    )
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
