import os
os.environ["DATABASE_URL"] = "postgresql://railway:123@postgres.railway.internal:5432/railway"
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str | None = None

s = Settings()
print(s.DATABASE_URL)
