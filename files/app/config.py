"""
Configuración centralizada — todas las variables sensibles vienen del entorno.

En desarrollo copia `.env.example` → `.env` y completa los valores.
NUNCA hagas commit del archivo `.env`.
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import secrets


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────
    APP_NAME: str    = "ApoYo FES Acatlán"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool      = False
    ENVIRONMENT: str = "production"   # development | staging | production

    # BUG FIX: usar secrets.token_urlsafe() como *default* hace que la clave
    # cambie en cada reinicio, invalidando todos los tokens JWT activos.
    # En producción SIEMPRE define estas variables en el entorno.
    SECRET_KEY:     str = "CHANGE_ME_IN_PRODUCTION"
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_JWT"

    # ── Base de datos ─────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://apoyofes:devpassword@localhost:5432/apoyofes_db"

    DB_POOL_SIZE:    int = 10
    DB_MAX_OVERFLOW: int = 20

    # ── JWT ───────────────────────────────────────────────
    JWT_ALGORITHM:                str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:  int = 60
    REFRESH_TOKEN_EXPIRE_DAYS:    int = 30

    # ── Bloqueo de cuenta (brute-force) ──────────────────
    MAX_LOGIN_ATTEMPTS: int = 5          # intentos antes de bloquear
    LOCKOUT_MINUTES:    int = 15         # minutos bloqueado

    # ── OAuth Google (UNAM Institucional) ─────────────────
    GOOGLE_CLIENT_ID:     str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI:  str = "http://localhost:8000/api/auth/google/callback"
    ALLOWED_EMAIL_DOMAIN: str = "comunidad.unam.mx"
    VERIFICATION_EMAIL_DOMAIN: str = "pcpuma.acatlan.unam.mx"  # dominio para registro con verificación

    # ── Email (notificaciones) ────────────────────────────
    SMTP_HOST:       str = "smtp.gmail.com"
    SMTP_PORT:       int = 587
    SMTP_USER:       str = ""
    SMTP_PASSWORD:   str = ""
    EMAIL_FROM:      str = "apoyofes@unam.mx"
    EMAIL_FROM_NAME: str = "ApoYo FES Acatlán"

    # ── CORS ──────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://192.168.0.25:8000",
        "http://192.168.0.23:8000",
        "https://apoyofes.unam.mx",
    ]

    # ── Almacenamiento ────────────────────────────────────
    UPLOAD_DIR:       str = "uploads"
    MAX_FILE_SIZE_MB: int = 10

    # ── Redis (caché + rate-limiting) ─────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Rate limiting ─────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST:      int = 20   # ráfaga permitida

    # ── Resend (email transaccional) ──────────────────────
    RESEND_API_KEY: str = ""   # obtener en resend.com

    # ── IA ────────────────────────────────────────────────
    # ── Configuración de LM Studio (IA Local) ──
    LMS_BASE_URL: str = "http://10.110.0.28:1234/v1"
    LMS_MODEL: str = "google/gemma-4-e4b"
    
# ── Alertas internas ──────────────────────────────────
    ADMIN_ALERT_EMAIL: str = ""   # email que recibe alertas SOS

    @field_validator("SECRET_KEY", "JWT_SECRET_KEY", mode="before")
    @classmethod
    def no_defaults_en_produccion(cls, v: str, info) -> str:
        """
        Reglas de seguridad para las claves secretas:
        1. Nunca pueden ser el placeholder 'CHANGE_ME_IN_PRODUCTION*'.
        2. Deben tener al menos 32 caracteres para resistir fuerza bruta.
        Si alguna regla falla la app NO arranca — es intencional.
        """
        PLACEHOLDERS = {
            "CHANGE_ME_IN_PRODUCTION",
            "CHANGE_ME_IN_PRODUCTION_JWT",
            "",
        }
        if v in PLACEHOLDERS:
            raise ValueError(
                f"\n\n🔐  SEGURIDAD: La variable '{info.field_name}' usa el valor por defecto inseguro.\n"
                "   Define un secreto real en tu archivo .env antes de iniciar la app.\n"
                "   Puedes generar uno con:  python -c \"import secrets; print(secrets.token_urlsafe(64))\"\n"
            )
        if len(v) < 32:
            raise ValueError(
                f"\n\n🔐  SEGURIDAD: '{info.field_name}' es demasiado corta ({len(v)} chars).\n"
                "   Usa al menos 32 caracteres. Genera una con:\n"
                "   python -c \"import secrets; print(secrets.token_urlsafe(64))\"\n"
            )
        return v

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    class Config:
        env_file          = ".env"
        env_file_encoding = "utf-8"
        case_sensitive    = True


settings = Settings()
