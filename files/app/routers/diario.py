"""
Router del Diario Personal — con análisis de IA y compartir con psicólogo
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional
import uuid

from app.database import get_db
from app.models import Usuario, EntradaDiario
from app.schemas import (
    EntradaDiarioCrear, EntradaDiarioActualizar,
    EntradaDiarioRespuesta, EntradaDiarioListaRespuesta,
    MensajeRespuesta,
)
from app.service.auth_service import get_current_user, get_current_psicologo
from app.service.ia_service import analizar_entrada_diario

router = APIRouter()


@router.get("/", response_model=EntradaDiarioListaRespuesta)
async def listar_entradas(
    pagina:          int = Query(default=1, ge=1),
    por_pagina:      int = Query(default=20, ge=1, le=100),
    estado_animo:    Optional[str] = None,
    solo_compartidas: bool = False,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    filtros = [EntradaDiario.usuario_id == usuario.id]
    if estado_animo:
        filtros.append(EntradaDiario.estado_animo == estado_animo)
    if solo_compartidas:
        filtros.append(EntradaDiario.compartida == True)

    count_q = await db.execute(
        select(func.count()).select_from(EntradaDiario).where(and_(*filtros))
    )
    total = count_q.scalar()

    result = await db.execute(
        select(EntradaDiario)
        .where(and_(*filtros))
        .order_by(EntradaDiario.creada_en.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    )
    entradas = result.scalars().all()

    return {"entradas": entradas, "total": total, "pagina": pagina, "por_pagina": por_pagina}


@router.post("/", response_model=EntradaDiarioRespuesta, status_code=201)
async def crear_entrada(
    datos: EntradaDiarioCrear,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    entrada = EntradaDiario(
        id          = str(uuid.uuid4()),
        usuario_id  = usuario.id,
        texto       = datos.texto,
        estado_animo= datos.estado_animo,
        etiquetas   = datos.etiquetas,
        compartida  = datos.compartida,
    )

    try:
        analisis = await analizar_entrada_diario(datos.texto)
        entrada.analisis_ia   = analisis
        entrada.alerta_crisis = analisis.get("alerta_crisis", False)
    except Exception:
        pass

    db.add(entrada)
    await db.commit()
    await db.refresh(entrada)
    return entrada


@router.get("/{entrada_id}", response_model=EntradaDiarioRespuesta)
async def obtener_entrada(
    entrada_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    result = await db.execute(
        select(EntradaDiario).where(
            EntradaDiario.id == entrada_id,
            EntradaDiario.usuario_id == usuario.id,
        )
    )
    entrada = result.scalar_one_or_none()
    if not entrada:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    return entrada


@router.patch("/{entrada_id}", response_model=EntradaDiarioRespuesta)
async def actualizar_entrada(
    entrada_id: str,
    datos: EntradaDiarioActualizar,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    result = await db.execute(
        select(EntradaDiario).where(
            EntradaDiario.id == entrada_id,
            EntradaDiario.usuario_id == usuario.id,
        )
    )
    entrada = result.scalar_one_or_none()
    if not entrada:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")

    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(entrada, campo, valor)

    await db.commit()
    await db.refresh(entrada)
    return entrada


@router.delete("/{entrada_id}", response_model=MensajeRespuesta)
async def eliminar_entrada(
    entrada_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    result = await db.execute(
        select(EntradaDiario).where(
            EntradaDiario.id == entrada_id,
            EntradaDiario.usuario_id == usuario.id,
        )
    )
    entrada = result.scalar_one_or_none()
    if not entrada:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")

    await db.delete(entrada)
    await db.commit()
    return {"mensaje": "Entrada eliminada correctamente"}


@router.patch("/{entrada_id}/compartir", response_model=EntradaDiarioRespuesta)
async def compartir_entrada(
    entrada_id: str,
    compartir: bool,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    result = await db.execute(
        select(EntradaDiario).where(
            EntradaDiario.id == entrada_id,
            EntradaDiario.usuario_id == usuario.id,
        )
    )
    entrada = result.scalar_one_or_none()
    if not entrada:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")

    entrada.compartida = compartir
    await db.commit()
    await db.refresh(entrada)
    return entrada


@router.get("/psicologo/estudiantes", response_model=list)
async def listar_entradas_estudiantes(
    estudiante_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    filtros = [EntradaDiario.compartida == True]
    if estudiante_id:
        filtros.append(EntradaDiario.usuario_id == estudiante_id)

    result = await db.execute(
        select(EntradaDiario, Usuario)
        .join(Usuario, EntradaDiario.usuario_id == Usuario.id)
        .where(and_(*filtros))
        .order_by(EntradaDiario.creada_en.desc())
        .limit(100)
    )
    return [
        {
            **{c.key: getattr(e, c.key) for c in EntradaDiario.__table__.columns},
            "estudiante": {"nombre": u.nombre, "email": u.email, "carrera": u.carrera}
        }
        for e, u in result.all()
    ]
