from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILES = (
    str(_BACKEND_DIR / ".env"),
    ".env",
)


class Settings(BaseSettings):
    # ============================================================
    # Email / SMTP
    # ============================================================

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

        # SMTP security
    smtp_use_tls: bool = True


    # Frontend URL used when generating activation links.
    frontend_url: str = "http://localhost:5173"

    # ============================================================
    # Environment configuration
    # ============================================================

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        extra="ignore",
    )

    # ============================================================
    # Database
    # ============================================================

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/coresight"
    )

    # ============================================================
    # Supabase
    # ============================================================

    # Supabase project config.
    #
    # IMPORTANT:
    # supabase_service_role_key must NEVER be exposed to the frontend.

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""
    supabase_storage_bucket: str = "coresight-media"

    # ============================================================
    # Authentication
    # ============================================================

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12

    # ============================================================
    # Google Forms / Sheets
    # ============================================================

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_refresh_token: str = ""

    # ============================================================
    # CORS
    # ============================================================

    cors_allow_origins: str = "http://localhost:5173"

    # ============================================================
    # Face recognition
    # ============================================================

    face_embedding_dim: int = 512

    face_device: str = "auto"

    scrfd_model_path: str = ""
    adaface_model_path: str = ""
    minifas_model_path: str = ""

    face_similarity_threshold: float = 0.45
    liveness_threshold: float = 0.85
    face_detection_threshold: float = 0.5
    face_quality_threshold: float = 0.5

    # ============================================================
    # Google Form response sync
    # ============================================================

    enable_sync_scheduler: bool = False
    google_form_sync_interval_seconds: int = 300

    # ============================================================
    # Helpers
    # ============================================================

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]

    @property
    def google_forms_configured(self) -> bool:
        return bool(
            self.google_oauth_client_id
            and self.google_oauth_client_secret
            and self.google_oauth_refresh_token
        )

    @property
    def smtp_configured(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_username
            and self.smtp_password
            and self.smtp_from_email
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()