from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "GoMarg API"
    VERSION: str = "0.1.0"
    
    POSTGRES_USER: str = "gomarg"
    POSTGRES_PASSWORD: str = "gomarg_password"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "gomarg_db"

    GEMINI_API_KEY: str = ""
    
    SECRET_KEY: str = "gomarg_super_secret_key_change_in_prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    BREVO_API_KEY: str = ""
    BREVO_SENDER_EMAIL: str = "hello@gomarg.com"
    
    APOLLO_API_KEY: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
