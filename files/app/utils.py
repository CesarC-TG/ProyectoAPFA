"""
Utilidades compartidas — helpers reutilizables en toda la app.

Importar desde aquí en lugar de duplicar lógica en routers y servicios.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic.alias_generators import to_camel

logger = logging.getLogger("apoyofes")

# ── Datetime ──────────────────────────────────────────────────────────────────

def ahora_utc() -> datetime:
    """Devuelve el instante actual con zona UTC (aware)."""
    return datetime.now(timezone.utc)


def asegurar_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Garantiza que un datetime sea UTC-aware.
    Si ya tiene tzinfo lo deja intacto; si es naive lo marca como UTC.
    Devuelve None si dt es None.
    """
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def dias_desde(dt: Optional[datetime]) -> Optional[int]:
    """
    Días transcurridos desde *dt* hasta ahora.
    Devuelve None si dt es None (sin registro previo).
    """
    aware = asegurar_utc(dt)
    if aware is None:
        return None
    return (ahora_utc() - aware).days


def estado_actividad(dias: Optional[int]) -> str:
    """
    Etiqueta de actividad basada en días sin acceder.

    Returns:
        "sin_registro" | "critico" | "alerta" | "activo"
    """
    if dias is None:
        return "sin_registro"
    if dias >= 14:
        return "critico"
    if dias >= 7:
        return "alerta"
    return "activo"


# ── Base de datos ─────────────────────────────────────────────────────────────

ModelT = TypeVar("ModelT")


async def contar(
    db: AsyncSession,
    modelo: Any,
    *filtros: Any,
) -> int:
    """
    Ejecuta un COUNT sobre *modelo* aplicando los *filtros* dados.

    Ejemplo:
        total = await contar(db, Usuario, Usuario.rol == RolUsuario.ESTUDIANTE)
    """
    q = select(func.count()).select_from(modelo)
    if filtros:
        q = q.where(*filtros)
    result = await db.execute(q)
    return result.scalar() or 0


async def paginar(
    db: AsyncSession,
    query: Any,
    *,
    pagina: int,
    por_pagina: int,
) -> tuple[Sequence[Any], int]:
    """
    Ejecuta *query* con paginación y devuelve (filas, total).

    Ejemplo:
        filas, total = await paginar(db, select(Recurso).where(...),
                                      pagina=1, por_pagina=20)
    """
    # Contar total sin OFFSET/LIMIT
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Aplicar paginación
    paginado = query.offset((pagina - 1) * por_pagina).limit(por_pagina)
    filas = (await db.execute(paginado)).scalars().all()

    return filas, total


# ── Logging helpers ───────────────────────────────────────────────────────────

def log_excepcion(mensaje: str, exc: Exception, **contexto: Any) -> None:
    """Loguea una excepción con contexto adicional usando el logger global."""
    extra = "  ".join(f"{k}={v!r}" for k, v in contexto.items())
    logger.error("%s — %s: %s  %s", mensaje, type(exc).__name__, exc, extra)


# ── camelCase helpers ─────────────────────────────────────────────────────────

def camelize(obj: Any) -> Any:
    """
    Convierte recursivamente las claves de dicts (y listas) de snake_case
    a camelCase, para los endpoints que devuelven dicts manuales sin
    response_model. Los valores se dejan intactos (los serializa FastAPI).
    """
    if isinstance(obj, dict):
        return {
            (to_camel(k) if isinstance(k, str) else k): camelize(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [camelize(x) for x in obj]
    return obj
