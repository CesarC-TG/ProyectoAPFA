"""
Servicio de autenticación — JWT + Google OAuth + bloqueo de cuenta
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt
import bcrypt
import httpx
import uuid

from app.database import get_db
from app.models import Usuario, SesionUsuario, RolUsuario
from app.config import settings

security          = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)   # para endpoints públicos


# ── Hashing de contraseñas ────────────────────────────────

def hashear_password(password: str) -> str:
    """Genera un hash bcrypt con factor de coste 12."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def verificar_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ───────────────────────────────────────────────────

def crear_access_token(data: Dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"]  = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload["iat"]  = datetime.now(timezone.utc)
    payload["type"] = "access"
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def crear_refresh_token(usuario_id: str) -> str:
    payload = {
        "sub":  usuario_id,
        "jti":  str(uuid.uuid4()),
        "exp":  datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "iat":  datetime.now(timezone.utc),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decodificar_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


# ── Dependencias FastAPI ──────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """Requiere autenticación. Lanza 401 si no hay token válido."""
    payload = decodificar_token(credentials.credentials)

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Token de tipo incorrecto")

    usuario_id: Optional[str] = payload.get("sub")
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Token inválido")

    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    usuario = result.scalar_one_or_none()

    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")

    # BUG FIX: actualizar último acceso sin hacer commit en cada request.
    # Usamos update() directo para no cargar el ORM y luego hacemos flush
    # perezoso — el commit lo maneja la dependencia get_db.
    usuario.ultimo_acceso = datetime.now(timezone.utc)

    return usuario


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[Usuario]:
    """
    Autenticación opcional — devuelve None si no hay token.
    Usado en endpoints públicos que enriquecen la respuesta cuando el
    usuario está logueado (ej. registro SOS anónimo vs autenticado).
    """
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


async def get_current_psicologo(
    usuario: Usuario = Depends(get_current_user),
) -> Usuario:
    if usuario.rol not in (RolUsuario.PSICOLOGO, RolUsuario.ADMIN):
        raise HTTPException(status_code=403, detail="Acceso restringido a psicólogos")
    return usuario


async def get_current_admin(
    usuario: Usuario = Depends(get_current_user),
) -> Usuario:
    if usuario.rol != RolUsuario.ADMIN:
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores")
    return usuario


# ── Bloqueo de cuenta (brute-force) ──────────────────────

async def verificar_bloqueo(usuario: Usuario) -> None:
    """Lanza 429 si la cuenta está temporalmente bloqueada."""
    if usuario.bloqueado_hasta and usuario.bloqueado_hasta > datetime.now(timezone.utc):
        segundos = int((usuario.bloqueado_hasta - datetime.now(timezone.utc)).total_seconds())
        raise HTTPException(
            status_code=429,
            detail=f"Cuenta bloqueada. Intenta de nuevo en {segundos} segundos.",
            headers={"Retry-After": str(segundos)},
        )


async def registrar_intento_fallido(usuario: Usuario, db: AsyncSession) -> None:
    usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
    if usuario.intentos_fallidos >= settings.MAX_LOGIN_ATTEMPTS:
        usuario.bloqueado_hasta = datetime.now(timezone.utc) + timedelta(
            minutes=settings.LOCKOUT_MINUTES
        )
        usuario.intentos_fallidos = 0
    await db.commit()


async def limpiar_intentos_fallidos(usuario: Usuario, db: AsyncSession) -> None:
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta   = None
    await db.commit()


# ── Google OAuth ──────────────────────────────────────────

async def verificar_google_token(token: str) -> Dict[str, Any]:
    """Verifica un ID token de Google y retorna los claims del usuario."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": token},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Token de Google inválido")

    data = resp.json()

    if settings.GOOGLE_CLIENT_ID and data.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Token no corresponde a esta aplicación")

    email = data.get("email", "")
    if settings.ALLOWED_EMAIL_DOMAIN and not email.endswith(f"@{settings.ALLOWED_EMAIL_DOMAIN}"):
        raise HTTPException(
            status_code=403,
            detail=f"Solo se permiten correos @{settings.ALLOWED_EMAIL_DOMAIN}",
        )

    return data


async def login_o_registro_google(
    google_data: Dict[str, Any],
    db: AsyncSession,
    request_info: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Crea o actualiza un usuario a partir de datos de Google OAuth."""
    request_info = request_info or {}
    email     = google_data["email"]
    google_id = google_data["sub"]

    result = await db.execute(
        select(Usuario).where(
            (Usuario.email == email) | (Usuario.google_id == google_id)
        )
    )
    usuario = result.scalar_one_or_none()

    if not usuario:
        partes = google_data.get("name", "").split(" ", 1)
        usuario = Usuario(
            nombre           = partes[0],
            apellidos        = partes[1] if len(partes) > 1 else None,
            email            = email,
            google_id        = google_id,
            avatar_url       = google_data.get("picture"),
            email_verificado = bool(google_data.get("email_verified", False)),
            rol              = RolUsuario.ESTUDIANTE,
        )
        db.add(usuario)
        await db.flush()
    else:
        usuario.google_id        = google_id
        usuario.avatar_url       = google_data.get("picture", usuario.avatar_url)
        usuario.email_verificado = True

    return await _emitir_tokens_y_sesion(usuario, db, request_info)


async def _emitir_tokens_y_sesion(
    usuario: Usuario,
    db: AsyncSession,
    request_info: Dict[str, str],
) -> Dict[str, Any]:
    """Crea tokens JWT y persiste la sesión. Uso interno."""
    access_token  = crear_access_token({"sub": usuario.id, "rol": usuario.rol})
    refresh_token = crear_refresh_token(usuario.id)

    sesion = SesionUsuario(
        usuario_id    = usuario.id,
        refresh_token = refresh_token,
        user_agent    = request_info.get("user_agent"),
        ip_address    = request_info.get("ip"),
        expira_en     = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        ),
    )
    db.add(sesion)
    await db.commit()
    await db.refresh(usuario)

    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "bearer",
        "expires_in":    settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "usuario":       usuario,
    }
