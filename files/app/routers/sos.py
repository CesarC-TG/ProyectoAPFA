"""
Router SOS — Registro de eventos de emergencia (con auth opcional)
"""

from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid

from app.database import get_db
from app.models import Usuario, EventoSOS
from app.schemas import EventoSOSCrear, EventoSOSRespuesta, MensajeRespuesta
from app.service.auth_service import (
    get_current_user,
    get_current_user_optional,   # BUG FIX: usar la versión opcional
    get_current_psicologo,
)
from app.service.notificacion_service import notificar_sos_a_admin

router = APIRouter()

# Líneas de crisis precargadas
LINEAS_CRISIS = [
    {
        "id": "saptel",
        "nombre": "SAPTEL — Línea de Crisis",
        "telefono": "800-290-0024",
        "telefono_href": "tel:8002900024",
        "disponible_24h": True,
        "descripcion": "Apoyo emocional y crisis, 24/7 los 365 días del año",
        "icono": "🆘",
    },
    {
        "id": "imss",
        "nombre": "IMSS — Salud Mental Urgencias",
        "telefono": "800 911 2000",
        "telefono_href": "tel:8009112000",
        "disponible_24h": True,
        "descripcion": "Orientación en crisis de salud mental",
        "icono": "🏥",
    },
    {
        "id": "capa",
        "nombre": "CAPA — Centro de Atención al Paciente",
        "telefono": "800-290-0024",
        "telefono_href": "tel:8002900024",
        "disponible_24h": False,
        "descripcion": "CDMX · Salud mental pública",
        "icono": "👁",
    },
    {
        "id": "911",
        "nombre": "Emergencias CDMX",
        "telefono": "911",
        "telefono_href": "tel:911",
        "disponible_24h": True,
        "descripcion": "Policía / Ambulancias / Bomberos",
        "icono": "🚨",
    },
    {
        "id": "fes",
        "nombre": "FES Acatlán — Psicopedagogía",
        "telefono": "55 5623 1666",
        "telefono_href": "tel:5556231666",
        "disponible_24h": False,
        "descripcion": "Lun–Vie 8am–8pm · Edificio D, Planta Baja",
        "icono": "🏛",
    },
]


@router.get("/lineas", response_model=list)
async def obtener_lineas_crisis():
    """Lista de líneas de crisis disponibles — endpoint público, sin autenticación."""
    return LINEAS_CRISIS


@router.post("/evento", response_model=EventoSOSRespuesta, status_code=201)
async def registrar_evento_sos(
    datos: EventoSOSCrear,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    # BUG FIX: el original usaba get_current_user (obligatorio) pero el endpoint
    # debe funcionar incluso sin sesión activa (usuario en crisis puede no estar logueado).
    usuario: Optional[Usuario] = Depends(get_current_user_optional),
):
    """
    Registra un evento de emergencia.
    Funciona con o sin sesión iniciada — la privacidad del usuario
    nunca debe ser una barrera en un momento de crisis.
    """
    evento = EventoSOS(
        id          = str(uuid.uuid4()),
        usuario_id  = usuario.id if usuario else None,
        tipo_accion = datos.tipo_accion,
        descripcion = datos.descripcion,
        latitud     = datos.latitud,
        longitud    = datos.longitud,
        ip_address  = request.client.host if request.client else None,
    )
    db.add(evento)
    await db.commit()
    await db.refresh(evento)

    # Notificar a administradores en background (no bloquea la respuesta)
    background_tasks.add_task(notificar_sos_a_admin, evento, usuario)

    return evento


@router.get("/eventos", response_model=list)
async def listar_mis_eventos(
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Historial de eventos SOS del usuario autenticado."""
    result = await db.execute(
        select(EventoSOS)
        .where(EventoSOS.usuario_id == usuario.id)
        .order_by(EventoSOS.creado_en.desc())
        .limit(50)
    )
    return result.scalars().all()


# ── Endpoints de gestión para psicólogos/admin ────────────

@router.get("/admin/eventos", response_model=list)
async def listar_todos_eventos(
    atendido: Optional[bool] = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_psicologo),
):
    """Psicólogo / Admin: ver todos los eventos SOS con filtro opcional."""
    query = select(EventoSOS).order_by(EventoSOS.creado_en.desc()).limit(limit)
    if atendido is not None:
        query = query.where(EventoSOS.atendido == atendido)

    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/admin/eventos/{evento_id}/atender", response_model=MensajeRespuesta)
async def marcar_evento_atendido(
    evento_id: str,
    notas: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """Marca un evento SOS como atendido con notas opcionales."""
    evento = await db.get(EventoSOS, evento_id)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    evento.atendido       = True
    evento.atendido_por   = psicologo.id
    evento.notas_atencion = notas
    await db.commit()

    return {"mensaje": "Evento marcado como atendido"}
