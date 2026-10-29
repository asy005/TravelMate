from pathlib import Path
from pydantic_settings import BaseSettings

_ENV_FILE = str(Path(__file__).resolve().parent.parent / ".env")

class Settings(BaseSettings):
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "travelmate"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    SECRET_KEY: str = "default_secret_key_for_tests"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    OPENAI_API_KEY: str = ""
    PINECONE_API_KEY: str = ""
    huggingfacehub_api_token: str = ""
    LLM_PROVIDER: str = "groq"          
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    OPENAI_MODEL: str = "gpt-4o-mini"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    ENVIRONMENT: str = "development"
    ENABLE_DEMO_PAYMENT: bool = False
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    EXCHANGE_RATE_API_KEY: str = ""
    EXCHANGE_RATE_CACHE_TTL_SECONDS: int = 3600
    GOOGLE_VISION_API_KEY: str = ""

    @property
    def cors_origins(self) -> list:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = _ENV_FILE
        extra = "ignore"

settings = Settings()
