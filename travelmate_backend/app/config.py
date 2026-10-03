from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    OPENAI_API_KEY: str = None
    PINECONE_API_KEY: str = None
    huggingfacehub_api_token: str = ""
    LLM_PROVIDER: str = "groq"          
    GROQ_API_KEY: str = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    OPENAI_MODEL: str = "gpt-4o-mini"
    RAZORPAY_KEY_ID: str = None
    RAZORPAY_KEY_SECRET: str = None
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins(self) -> list:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"
settings = Settings()
