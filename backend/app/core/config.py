import secrets
from urllib.parse import quote_plus
# pyrefly: ignore [missing-import]
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "attendance_management"
    DB_SSL_VERIFY: bool = False
    
    APP_ENV: str = "development"
    APP_PORT: int = 8000

    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    INIT_ADMIN_USERNAME: str = "admin"
    INIT_ADMIN_EMAIL: str = "admin@attendance.com"
    INIT_ADMIN_PASSWORD: str = ""
    SEED_TEACHER_PASSWORD: str = ""
    SEED_STUDENT_PASSWORD: str = ""

    DATABASE_URL_OVERRIDE: str = ""
    ALLOWED_ORIGINS: str = "*"

    REQUIRED_ATTENDANCE_PERCENTAGE: float = Field(default=75.0, ge=0.0, le=100.0)
    ATTENDANCE_QR_TOKEN_TTL_SECONDS: int = 45
    ATTENDANCE_QR_REFRESH_INTERVAL_SECONDS: int = 30
    ATTENDANCE_GAP_MEDIUM: float = 5.0
    ATTENDANCE_GAP_HIGH: float = 15.0
    CURRICULUM_GAP_MEDIUM: float = 10.0
    CURRICULUM_GAP_HIGH: float = 25.0
    PENDING_ASSIGNMENTS_MEDIUM: int = 1
    PENDING_ASSIGNMENTS_HIGH: int = 3
    PERFORMANCE_TARGET_PERCENTAGE: float = 50.0
    PERFORMANCE_HIGH_RISK_PERCENTAGE: float = 35.0

    PDF_MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    PDF_MAX_PAGES: int = 200
    RAG_CHUNK_SIZE: int = 1200
    RAG_CHUNK_OVERLAP: int = 150
    RAG_EMBEDDING_BATCH_SIZE: int = Field(default=32, ge=1, le=128)
    RAG_MAX_CHUNKS_PER_DOCUMENT: int = Field(default=2000, ge=1, le=10000)
    RAG_MIN_SIMILARITY_SCORE: float = Field(default=0.25, ge=0.0, le=1.0)
    EMBEDDING_API_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = ""
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "academic_documents"
    LLM_API_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_MAX_OUTPUT_TOKENS: int = Field(default=800, ge=1, le=8192)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def configure_jwt_secret(self) -> "Settings":
        is_production = self.APP_ENV.lower() in {"production", "prod"}
        if self.ATTENDANCE_QR_TOKEN_TTL_SECONDS <= 0:
            raise ValueError("ATTENDANCE_QR_TOKEN_TTL_SECONDS must be positive")
        if not 0 < self.ATTENDANCE_QR_REFRESH_INTERVAL_SECONDS < self.ATTENDANCE_QR_TOKEN_TTL_SECONDS:
            raise ValueError(
                "ATTENDANCE_QR_REFRESH_INTERVAL_SECONDS must be positive and less than the QR token TTL"
            )
        if not self.JWT_SECRET_KEY:
            if is_production:
                raise ValueError("JWT_SECRET_KEY must be configured in production")
            self.JWT_SECRET_KEY = secrets.token_urlsafe(32)
        if is_production:
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must contain at least 32 characters in production")
            if "*" in self.allowed_origins_list:
                raise ValueError("ALLOWED_ORIGINS must list explicit origins in production")
        return self

    @property
    def allowed_origins_list(self) -> list[str]:
        """
        Parse comma-separated ALLOWED_ORIGINS string into a list of origins.
        """
        if not self.ALLOWED_ORIGINS or self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        """
        Construct SQLAlchemy MySQL connection URL using PyMySQL driver.
        Supports DATABASE_URL_OVERRIDE for direct cloud DB strings.
        Escapes password to handle special characters cleanly.
        """
        if self.DATABASE_URL_OVERRIDE:
            url = self.DATABASE_URL_OVERRIDE
            if url.startswith("mysql://"):
                url = url.replace("mysql://", "mysql+pymysql://", 1)
            return url

        encoded_password = quote_plus(self.DB_PASSWORD)
        return (
            f"mysql+pymysql://{self.DB_USER}:{encoded_password}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
