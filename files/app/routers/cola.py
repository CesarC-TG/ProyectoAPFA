"""
Router de Cola de Atención — cola de trabajo de psicólogos + asignación/reasignación.

Flujo de estados:
    pendiente → tomada → resuelta
                ↳ reasignar (cambia dueño, sigue tomada)
                ↳ liberar   (vuelve a pendiente para que otro psicólogo la tome)

Cada acción sobre un caso y cada acceso a expediente queda en AuditoriaAcceso.
"""
import uuid
from datetime import timezone as _tz
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, update, case, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Usuario, ColaAtencion, AuditoriaAcceso, AsignacionPsicologo,
    RolUsuario, EstadoCola, PrioridadCola,
)
from app.schemas import ColaReasignar, ColaAsignar
from app.service.auth_service import get_current_psicologo
from app.utils import ahora_utc, camelize

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────

def _ahora() -> datetime:
    return datetime.now(_tz.utc)


async def _auditar(
    db: AsyncSession,
    psicologo: Usuario,
    estudiante_id: Optional[str],
    accion: str,
    detalle: Optional[str] = None,
    ip: Optional[str] = None,
) -> None:
    """Registra una entrada inmutable en el log de auditoría."""
    db.add(AuditoriaAcceso(
        id            = str(uuid.uuid4()),
        psicologo_id  = psicologo.id,
        estudiante_id = estudiante_id,
        accion        = accion,
        detalle       = detalle,
        ip_address    = ip,
    ))


async def _desvincular_asignaciones(db: AsyncSession, estudiante_id: str) -> None:
    """Desactiva todas las asignaciones activas de un estudiante."""
    await db.execute(
        update(AsignacionPsicologo)
        .where(
            AsignacionPsicologo.estudiante_id == estudiante_id,
            AsignacionPsicologo.activa == True,
        )
        .values(activa=False)
    )


async def _vincular_asignacion(db: AsyncSession, estudiante_id: str, psicologo_id: str) -> None:
    """Desactiva las previas y crea la asignación activa estudiante→psicólogo."""
    await _desvincular_asignaciones(db, estudiante_id)
    db.add(AsignacionPsicologo(
        id            = str(uuid.uuid4()),
        psicologo_id  = psicologo_id,
        estudiante_id = estudiante_id,
        activa        = True,
    ))


def _cola_dict(cola: ColaAtencion, estudiante: Optional[Usuario]) -> dict:
    return {
        "id":           cola.id,
        "estado":       cola.estado.value if isinstance(cola.estado, EstadoCola) else cola.estado,
        "prioridad":    cola.prioridad.value if isinstance(cola.prioridad, PrioridadCola) else cola.prioridad,
        "origen":       cola.origen,
        "motivo":       cola.motivo,
        "psicologo_id": cola.psicologo_id,
        "creada_en":    cola.creada_en.isoformat() if cola.creada_en else None,
        "tomada_en":    cola.tomada_en.isoformat() if cola.tomada_en else None,
        "resuelta_en":  cola.resuelta_en.isoformat() if cola.resuelta_en else None,
        "estudiante": {
            "id":                 estudiante.id if estudiante else cola.estudiante_id,
            "nombre":             estudiante.nombre if estudiante else None,
            "apellidos":          estudiante.apellidos if estudiante else None,
            "carrera":            estudiante.carrera if estudiante else None,
            "semestre":           estudiante.semestre if estudiante else None,
            "categoria_problema": estudiante.categoria_problema if estudiante else None,
            "en_crisis":          estudiante.en_crisis if estudiante else None,
        },
    }


# ── Listar cola ───────────────────────────────────────────

@router.get("/cola")
async def listar_cola(
    estado:    Optional[EstadoCola]    = None,
    prioridad: Optional[PrioridadCola] = None,
    origen:    Optional[str]           = None,
    buscar:    Optional[str]           = None,
    pagina:    int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """
    Cola de atención priorizada. Todos los psicólogos ven todos los casos,
    pero SIN PII sensible (sin email/teléfono): solo nombre, carrera, señal de crisis.
    """
    filtros = []
    if estado:    filtros.append(ColaAtencion.estado == estado)
    if prioridad: filtros.append(ColaAtencion.prioridad == prioridad)
    if origen:    filtros.append(ColaAtencion.origen == origen)

    base = (
        select(ColaAtencion, Usuario)
        .join(Usuario, ColaAtencion.estudiante_id == Usuario.id)
        .where(and_(*filtros)) if filtros else
        select(ColaAtencion, Usuario).join(Usuario, ColaAtencion.estudiante_id == Usuario.id)
    )

    if buscar:
        like = f"%{buscar}%"
        base = base.where(
            or_(
                Usuario.nombre.ilike(like),
                Usuario.apellidos.ilike(like),
                Usuario.carrera.ilike(like),
            )
        )

    orden_prioridad = case(
        (ColaAtencion.prioridad == PrioridadCola.ALTA, 0),
        (ColaAtencion.prioridad == PrioridadCola.MEDIA, 1),
        else_=2,
    )
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0

    result = await db.execute(
        base.order_by(orden_prioridad, ColaAtencion.creada_en.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    )
    return camelize({
        "casos": [_cola_dict(c, u) for c, u in result.all()],
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
    })


# ── Tomar caso (claim atómico) ────────────────────────────

@router.post("/cola/{cola_id}/tomar")
async def tomar_caso(
    cola_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    result = await db.execute(
        select(ColaAtencion).where(ColaAtencion.id == cola_id).with_for_update()
    )
    cola = result.scalar_one_or_none()
    if not cola:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    if cola.estado == EstadoCola.RESUELTA:
        raise HTTPException(status_code=409, detail="Este caso ya fue resuelto")

    if cola.estado == EstadoCola.TOMADA:
        if cola.psicologo_id == psicologo.id:
            return camelize({"mensaje": "Ya tienes este caso", **_cola_dict(cola, await db.get(Usuario, cola.estudiante_id))})
        raise HTTPException(status_code=409, detail="Este caso ya lo tomó otro psicólogo")

    cola.estado       = EstadoCola.TOMADA
    cola.psicologo_id = psicologo.id
    cola.tomada_en    = _ahora()
    await _vincular_asignacion(db, cola.estudiante_id, psicologo.id)
    await _auditar(db, psicologo, cola.estudiante_id, "tomar_caso",
                   detalle=f"Tomó el caso {cola.id}", ip=request.client.host if request.client else None)
    await db.commit()

    return camelize({"mensaje": "Caso tomado", **_cola_dict(cola, await db.get(Usuario, cola.estudiante_id))})


# ── Reasignar a otro psicólogo ────────────────────────────

@router.post("/cola/{cola_id}/reasignar")
async def reasignar_caso(
    cola_id: str,
    datos: ColaReasignar,
    request: Request,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    result = await db.execute(
        select(ColaAtencion).where(ColaAtencion.id == cola_id).with_for_update()
    )
    cola = result.scalar_one_or_none()
    if not cola:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    if cola.psicologo_id != psicologo.id and psicologo.rol != RolUsuario.ADMIN:
        raise HTTPException(status_code=403, detail="Solo quien tiene el caso (o un admin) puede reasignarlo")

    nuevo = await db.get(Usuario, datos.psicologo_id)
    if not nuevo or nuevo.rol not in (RolUsuario.PSICOLOGO, RolUsuario.ADMIN):
        raise HTTPException(status_code=404, detail="Psicólogo destino no encontrado")

    anterior = cola.psicologo_id
    cola.psicologo_id = nuevo.id
    cola.estado       = EstadoCola.TOMADA
    await _vincular_asignacion(db, cola.estudiante_id, nuevo.id)
    await _auditar(db, psicologo, cola.estudiante_id, "reasignar",
                   detalle=f"Reasignó el caso {cola.id} de {anterior} a {nuevo.id}",
                   ip=request.client.host if request.client else None)
    await db.commit()

    return camelize({"mensaje": "Caso reasignado", **_cola_dict(cola, await db.get(Usuario, cola.estudiante_id))})


# ── Liberar (volver a pendiente) ──────────────────────────

@router.post("/cola/{cola_id}/liberar")
async def liberar_caso(
    cola_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    result = await db.execute(
        select(ColaAtencion).where(ColaAtencion.id == cola_id).with_for_update()
    )
    cola = result.scalar_one_or_none()
    if not cola:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    if cola.psicologo_id != psicologo.id and psicologo.rol != RolUsuario.ADMIN:
        raise HTTPException(status_code=403, detail="Solo quien tiene el caso (o un admin) puede liberarlo")

    cola.estado       = EstadoCola.PENDIENTE
    cola.psicologo_id = None
    cola.tomada_en    = None
    await _desvincular_asignaciones(db, cola.estudiante_id)
    await _auditar(db, psicologo, cola.estudiante_id, "liberar",
                   detalle=f"Liberó el caso {cola.id} para que otro psicólogo lo tome",
                   ip=request.client.host if request.client else None)
    await db.commit()

    return camelize({"mensaje": "Caso liberado a pendiente", **_cola_dict(cola, await db.get(Usuario, cola.estudiante_id))})


# ── Resolver (cerrar caso) ────────────────────────────────

@router.post("/cola/{cola_id}/resolver")
async def resolver_caso(
    cola_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    result = await db.execute(
        select(ColaAtencion).where(ColaAtencion.id == cola_id).with_for_update()
    )
    cola = result.scalar_one_or_none()
    if not cola:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    if cola.psicologo_id != psicologo.id and psicologo.rol != RolUsuario.ADMIN:
        raise HTTPException(status_code=403, detail="Solo quien tiene el caso (o un admin) puede resolverlo")

    cola.estado      = EstadoCola.RESUELTA
    cola.resuelta_en = _ahora()

    estudiante = await db.get(Usuario, cola.estudiante_id)
    if estudiante:
        estudiante.en_crisis = False  # se apaga la señal de crisis al cerrar el caso

    await _auditar(db, psicologo, cola.estudiante_id, "resolver",
                   detalle=f"Resolvió el caso {cola.id}", ip=request.client.host if request.client else None)
    await db.commit()

    return camelize({"mensaje": "Caso resuelto", **_cola_dict(cola, estudiante)})


# ── Asignar manualmente (sin pasar por cola pendiente) ────

@router.post("/asignar", status_code=201)
async def asignar_estudiante(
    datos: ColaAsignar,
    request: Request,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    est = await db.get(Usuario, datos.estudiante_id)
    if not est or est.rol != RolUsuario.ESTUDIANTE:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    dest = await db.get(Usuario, datos.psicologo_id)
    if not dest or dest.rol not in (RolUsuario.PSICOLOGO, RolUsuario.ADMIN):
        raise HTTPException(status_code=404, detail="Psicólogo destino no encontrado")

    # Reabrir caso abierto si existe, o crear uno nuevo en estado tomada
    abierta = (await db.execute(
        select(ColaAtencion).where(
            ColaAtencion.estudiante_id == datos.estudiante_id,
            ColaAtencion.estado != EstadoCola.RESUELTA,
        )
    )).scalar_one_or_none()

    if abierta:
        cola = abierta
        cola.psicologo_id = dest.id
        cola.estado       = EstadoCola.TOMADA
        cola.tomada_en    = _ahora()
        if datos.motivo:
            cola.motivo = datos.motivo
    else:
        cola = ColaAtencion(
            id            = str(uuid.uuid4()),
            estudiante_id = datos.estudiante_id,
            psicologo_id  = dest.id,
            estado        = EstadoCola.TOMADA,
            prioridad     = datos.prioridad,
            origen        = "manual",
            motivo        = datos.motivo,
            tomada_en     = _ahora(),
        )
        db.add(cola)

    await _vincular_asignacion(db, datos.estudiante_id, dest.id)
    await _auditar(db, psicologo, datos.estudiante_id, "asignar",
                   detalle=f"Asignó a {dest.id} el estudiante {datos.estudiante_id}",
                   ip=request.client.host if request.client else None)
    await db.commit()

    return camelize({"mensaje": "Estudiante asignado", **_cola_dict(cola, est)})
