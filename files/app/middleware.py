"""
Middlewares personalizados — rate limiting, seguridad y logging
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
        # Content-Security-Policy básica
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://accounts.google.com; "
            "style-src 'self' 'unsafe-inline'; "
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
