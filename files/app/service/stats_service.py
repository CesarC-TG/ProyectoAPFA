"""
Servicio de estadísticas y reportes — desacoplado de los routers.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import Usuario, EntradaDiario, EventoSOS, MensajeChat, RolUsuario


async def resumen_general(db: AsyncSession) -> Dict[str, Any]:
    hoy        = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    hace_7dias = hoy - timedelta(days=7)

    async def count(q):
        return (await db.execute(q)).scalar() or 0

    return {
        "total_estudiantes":    await count(select(func.count()).select_from(Usuario).where(Usuario.rol == RolUsuario.ESTUDIANTE, Usuario.activo == True)),
        "total_psicologos":     await count(select(func.count()).select_from(Usuario).where(Usuario.rol == RolUsuario.PSICOLOGO, Usuario.activo == True)),
        "entradas_hoy":         await count(select(func.count()).select_from(EntradaDiario).where(EntradaDiario.creada_en >= hoy)),
        "alertas_activas":      await count(select(func.count()).select_from(EventoSOS).where(EventoSOS.atendido == False)),
        "entradas_compartidas": await count(select(func.count()).select_from(EntradaDiario).where(EntradaDiario.compartida == True)),
        "sesiones_chat_semana": await count(select(func.count(MensajeChat.sesion_chat_id.distinct())).where(MensajeChat.creado_en >= hace_7dias)),
        "timestamp":            datetime.now(timezone.utc).isoformat(),
    }


async def actividad_usuarios(db: AsyncSession, dias: int = 30) -> List[Dict[str, Any]]:
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    ahora = datetime.now(timezone.utc)

    result = await db.execute(
        select(Usuario)
        .where(Usuario.rol == RolUsuario.ESTUDIANTE, Usuario.activo == True)
        .order_by(Usuario.ultimo_acceso.desc().nullslast())
    )
    estudiantes = result.scalars().all()

    datos = []
    for u in estudiantes:
        ua = u.ultimo_acceso
        if ua and ua.tzinfo is None:
            ua = ua.replace(tzinfo=timezone.utc)
        dias_sin = (ahora - ua).days if ua else None

        sos = (await db.execute(
            select(func.count()).select_from(EventoSOS)
            .where(EventoSOS.usuario_id == u.id, EventoSOS.creado_en >= desde)
        )).scalar() or 0

        entradas = (await db.execute(
            select(func.count()).select_from(EntradaDiario)
            .where(EntradaDiario.usuario_id == u.id, EntradaDiario.creada_en >= desde)
        )).scalar() or 0

        datos.append({
            "id":               u.id,
            "nombre":           u.nombre,
            "apellidos":        u.apellidos,
            "email":            u.email,
            "carrera":          u.carrera,
            "ultimo_acceso":    ua.isoformat() if ua else None,
            "dias_sin_entrar":  dias_sin,
            "sos_periodo":      sos,
            "entradas_periodo": entradas,
            "estado": (
                "sin_registro" if dias_sin is None else
                "critico"      if dias_sin >= 14 else
                "alerta"       if dias_sin >= 7  else
                "activo"
            ),
        })
    return datos


async def actividad_sos(db: AsyncSession, dias: int = 30) -> List[Dict[str, Any]]:
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    result = await db.execute(
        select(EventoSOS, Usuario)
        .outerjoin(Usuario, EventoSOS.usuario_id == Usuario.id)
        .where(EventoSOS.creado_en >= desde)
        .order_by(EventoSOS.creado_en.desc())
        .limit(200)
    )
    return [
        {
            "id":          e.id,
            "tipo":        e.tipo_accion,
            "descripcion": e.descripcion,
            "atendido":    e.atendido,
            "creado_en":   e.creado_en.isoformat(),
            "usuario": {
                "id":     u.id     if u else None,
                "nombre": u.nombre if u else "Anónimo",
                "email":  u.email  if u else None,
            },
        }
        for e, u in result.all()
    ]


async def estados_animo(db: AsyncSession, dias: int = 30) -> List[Dict[str, Any]]:
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    result = await db.execute(
        select(EntradaDiario.estado_animo, func.count(EntradaDiario.id).label("total"))
        .where(EntradaDiario.creada_en >= desde)
        .group_by(EntradaDiario.estado_animo)
    )
    return [{"estado": r.estado_animo, "total": r.total} for r in result.all()]
