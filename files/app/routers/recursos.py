"""
Router de Recursos de Bienestar
- GET / es público (no requiere auth) para que funcione sin sesión
- POST/PATCH/DELETE requieren admin
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional
import uuid

from app.database import get_db
from app.models import Usuario, Recurso, TipoRecurso
from app.schemas import RecursoRespuesta, RecursoCrear, MensajeRespuesta
from app.service.auth_service import get_current_user_optional, get_current_admin

router = APIRouter()


@router.get("/", response_model=list[RecursoRespuesta])
async def listar_recursos(
    tipo:           Optional[TipoRecurso] = None,
    disponible_24h: Optional[bool]        = None,
    buscar:         Optional[str]         = None,
    pagina:         int = Query(default=1,  ge=1),
    por_pagina:     int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    # Público — no requiere login
):
    """Lista recursos de bienestar. Endpoint público."""
    filtros = [Recurso.activo == True]

    if tipo:
        filtros.append(Recurso.tipo == tipo)
    if disponible_24h is not None:
        filtros.append(Recurso.disponible_24h == disponible_24h)
    if buscar:
        like = f"%{buscar}%"
        filtros.append(
            Recurso.titulo.ilike(like) | Recurso.descripcion.ilike(like)
        )

    result = await db.execute(
        select(Recurso)
        .where(and_(*filtros))
        .order_by(Recurso.orden.asc(), Recurso.titulo.asc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    )
    return result.scalars().all()


@router.get("/tipos", response_model=list[str])
async def listar_tipos():
    """Lista todos los tipos de recurso. Público."""
    return [t.value for t in TipoRecurso]


@router.get("/{recurso_id}", response_model=RecursoRespuesta)
async def obtener_recurso(
    recurso_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Obtiene un recurso por ID e incrementa vistas. Público."""
    recurso = await db.get(Recurso, recurso_id)
    if not recurso or not recurso.activo:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    recurso.vistas = (recurso.vistas or 0) + 1
    await db.commit()
    return recurso


# ── Admin ──────────────────────────────────────────────────

@router.post("/", response_model=RecursoRespuesta, status_code=201)
async def crear_recurso(
    datos: RecursoCrear,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    recurso = Recurso(
        id               = str(uuid.uuid4()),
        titulo           = datos.titulo,
        descripcion      = datos.descripcion,
        tipo             = datos.tipo,
        contenido        = datos.contenido,
        duracion_minutos = datos.duracion_minutos,
        telefono         = datos.telefono,
        direccion        = datos.direccion,
        horario          = datos.horario,
        disponible_24h   = datos.disponible_24h,
    )
    db.add(recurso)
    await db.commit()
    await db.refresh(recurso)
    return recurso


@router.patch("/{recurso_id}", response_model=RecursoRespuesta)
async def actualizar_recurso(
    recurso_id: str,
    datos: RecursoCrear,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    recurso = await db.get(Recurso, recurso_id)
    if not recurso:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(recurso, campo, valor)
    await db.commit()
    await db.refresh(recurso)
    return recurso


@router.delete("/{recurso_id}", response_model=MensajeRespuesta)
async def eliminar_recurso(
    recurso_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    recurso = await db.get(Recurso, recurso_id)
    if not recurso:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    recurso.activo = False
    await db.commit()
    return {"mensaje": "Recurso desactivado correctamente"}