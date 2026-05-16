from urllib.parse import quote

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    ENV: str = "development"

    # Base application settings
    PROJECT_NAME: str = "职启智评 API"
    API_V1_STR: str = "/api/v1"
    API_PORT: int = 8001
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_CORS_ORIGINS: str = ""
    UVICORN_WORKERS: int = 4

    # Optional docker/dev ports
    REDIS_EXTERNAL_PORT: int = 6386
    NGINX_HTTP_PORT: int = 8086
    NGINX_HTTPS_PORT: int = 8446
    FLOWER_PORT: int = 5556

    # Database
    POSTGRES_USER: str = "demo"
    POSTGRES_PASSWORD: str = "demo123"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "demo"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_SCHEDULER_POOL_SIZE: int = 2
    DB_SCHEDULER_MAX_OVERFLOW: int = 3

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # Celery
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    # HTTP proxy, used only when explicitly enabled
    USE_HTTP_PROXY: bool = False
    HTTP_PROXY: str = "http://127.0.0.1:7890"
    HTTPS_PROXY: str = "http://127.0.0.1:7890"

    # Mail
    MAIL_MAILER: str = "smtp"
    MAIL_HOST: str = "localhost"
    MAIL_PORT: int = 1025
    MAIL_USERNAME: str = "user"
    MAIL_PASSWORD: str = "password"
    MAIL_FROM_ADDRESS: str = "noreply@example.com"
    MAIL_FROM_NAME: str = "Seiki"
    MAIL_ENCRYPTION: str = "none"

    # Brevo
    BREVO_API_KEY: str = "dummy-api-key"
    BREVO_EMAIL_FROM: str = "noreply@example.com"
    BREVO_EMAIL_FROM_NAME: str = "Seiki"

    # Admin contact
    ADMIN_EMAIL: str = "dev@zetos.fr"

    # Resume extraction
    ENABLE_RESUME_OCR: bool = False

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    USER_LLM_CREDENTIAL_SECRET: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Client registration mode
    AUTH_REQUIRE_EMAIL_VERIFICATION: bool = False

    # S3
    AWS_ACCESS_KEY_ID: str = "your-access-key"
    AWS_SECRET_ACCESS_KEY: str = "your-secret-key"
    AWS_REGION: str = "us-east-1"
    AWS_BUCKET_NAME: str = "your-bucket-name"
    AWS_ENDPOINT: str = "https://s3.amazonaws.com"

    # OpenAI
    OPENAI_API_KEY: str = "your-openai-api-key"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-5.2-chat-latest"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_FINE_TUNE_BASE_MODEL: str = ""
    OPENAI_FINE_TUNE_SUFFIX: str = "zhiqi-sft"

    # DeepSeek
    DEEPSEEK_API_KEY: str = "your-deepseek-api-key"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    DEEPSEEK_EMBEDDING_MODEL: str = ""
    DEEPSEEK_THINKING: str = "disabled"
    DEEPSEEK_REASONING_EFFORT: str = "high"

    @field_validator("MAIL_PORT", mode="before")
    @classmethod
    def normalize_mail_port(cls, value):
        # If MAIL_PORT is set to an empty string in .env, fall back to a safe integer.
        if value is None:
            return 1025
        if isinstance(value, str) and not value.strip():
            return 1025
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.REDIS_PASSWORD:
            redis_url = f"redis://:{quote(self.REDIS_PASSWORD, safe='')}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        else:
            redis_url = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        self.CELERY_BROKER_URL = redis_url
        self.CELERY_RESULT_BACKEND = redis_url

    def get_cors_origins(self) -> list[str]:
        if self.ENV in {"development", "preview"}:
            return ["*"]
        if not self.BACKEND_CORS_ORIGINS.strip():
            return []
        return [
            origin.strip()
            for origin in self.BACKEND_CORS_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()
