"""
Middlewares personalizados — rate limiting, CSRF, seguridad y logging
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
import time
import logging

from app.config import settings

logger = logging.getLogger("apoyofes")


# ── Rate Limiting (en memoria — usar Redis en producción) ─────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiter simple basado en IP.

    En producción reemplaza este store en memoria por Redis:
        import redis.asyncio as redis
        r = redis.from_url(settings.REDIS_URL)
        count = await r.incr(key)
        await r.expire(key, 60)

    Esto garantiza que el límite se respete incluso con múltiples workers.
    """

    def __init__(self, app, calls: int = 60, period: int = 60):
        super().__init__(app)
        self.calls  = calls     # máximo de llamadas
        self.period = period    # segundos de ventana
        # {ip: [(timestamp, count)]}
        self._store: Dict[str, list] = defaultdict(list)

    def _limpiar(self, ip: str) -> None:
        """Elimina entradas vencidas del store."""
        ahora     = time.time()
        ventana   = ahora - self.period
        self._store[ip] = [ts for ts in self._store[ip] if ts > ventana]

    async def dispatch(self, request: Request, call_next):
        # Saltar rutas de health-check y documentación
        if request.url.path in ("/health", "/api/docs", "/api/redoc", "/openapi.json"):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        self._limpiar(ip)

        if len(self._store[ip]) >= self.calls:
            return JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas solicitudes. Intenta en un momento."},
                headers={"Retry-After": str(self.period)},
            )

        self._store[ip].append(time.time())
        return await call_next(request)


# ── CSRF — Validación de Origin ───────────────────────────

class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Protección CSRF mediante validación del header Origin/Referer.

    Funcionamiento:
    - Las peticiones GET/HEAD/OPTIONS son de solo lectura → se dejan pasar.
    - Las peticiones que modifican estado (POST, PUT, PATCH, DELETE) deben
      incluir un header Origin o Referer cuyo host coincida con un origen
      permitido en settings.ALLOWED_ORIGINS.
    - Las peticiones sin Origin ni Referer desde el exterior son bloqueadas.
    - Las peticiones de localhost en entorno de desarrollo se permiten siempre
      para no entorpecer el flujo de trabajo.

    Por qué funciona con JWT Bearer:
    Los ataques CSRF solo funcionan si el navegador envía credenciales
    automáticamente (cookies). Como esta app usa Authorization: Bearer
    en los headers, el JS del atacante no puede inyectarlos desde otro origen.
    Este middleware añade una segunda capa que bloquea hasta los endpoints
    de login/registro en caso de origen sospechoso.
    """

    # Métodos que modifican estado — los únicos que requieren validación
    METODOS_MUTABLES = {"POST", "PUT", "PATCH", "DELETE"}

    # Rutas que aceptan peticiones sin Origin (ej. apps móviles, Swagger)
    RUTAS_EXCLUIDAS = {
        "/api/docs",
        "/api/redoc",
        "/openapi.json",
        "/health",
    }

    def __init__(self, app, allowed_origins: list[str]):
        super().__init__(app)
        # Extrae solo los hosts (sin esquema ni puerto) para comparación flexible
        self._hosts_permitidos: set[str] = set()
        for origin in allowed_origins:
            host = origin.replace("https://", "").replace("http://", "").split(":")[0]
            self._hosts_permitidos.add(host)

    def _origen_permitido(self, request: Request) -> bool:
        """Devuelve True si el origen de la petición es de confianza."""
        # Extraer el host del header Origin o Referer
        origin  = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")

        raw = origin or referer
        if not raw:
            # Sin cabecera de origen → solo permitir si viene de localhost en dev
            client_host = request.client.host if request.client else ""
            return client_host in ("127.0.0.1", "::1", "localhost") or settings.is_development

        # Limpiar y extraer el host
        host = raw.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
        return host in self._hosts_permitidos

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in self.METODOS_MUTABLES:
            if request.url.path not in self.RUTAS_EXCLUIDAS:
                if not self._origen_permitido(request):
                    logger.warning(
                        "CSRF bloqueado: método=%s path=%s origin=%s ip=%s",
                        request.method,
                        request.url.path,
                        request.headers.get("origin", "—"),
                        request.client.host if request.client else "—",
                    )
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Solicitud bloqueada por política de seguridad."},
                    )
        return await call_next(request)


# ── Security Headers ──────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega cabeceras de seguridad a todas las respuestas HTTP."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Previene que el navegador adivine el Content-Type
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Bloquea clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Fuerza HTTPS en producción
        if not settings.is_development:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        # Content-Security-Policy
        # Se permiten los CDN externos que usa el frontend:
        #   - unpkg.com       → Boxicons (CSS + fuentes)
        #   - googleapis.com  → Google Fonts (CSS)
        #   - gstatic.com     → Google Fonts (archivos de fuente)
        #   - accounts.google.com → Google OAuth
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://accounts.google.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
            "font-src 'self' https://fonts.gstatic.com https://unpkg.com; "
            "img-src 'self' data: https:; "
            "frame-ancestors 'none';"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"

        return response


# ── Request logging ───────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log estructurado de cada solicitud con su duración."""

    async def dispatch(self, request: Request, call_next) -> Response:
        inicio = time.perf_counter()
        response = await call_next(request)
        duracion_ms = round((time.perf_counter() - inicio) * 1000, 2)

        # No loguear paths ruidosos
        if request.url.path not in ("/health", "/favicon.ico"):
            logger.info(
                "%s %s %s %.2fms ip=%s",
                request.method,
                request.url.path,
                response.status_code,
                duracion_ms,
                request.client.host if request.client else "-",
            )

        # Exponer duración en cabecera (útil para debugging)
        response.headers["X-Process-Time"] = f"{duracion_ms}ms"
        return response
