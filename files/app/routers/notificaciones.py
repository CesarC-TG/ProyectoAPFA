"""
Router Notificaciones — in-app notifications para el usuario
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Usuario, Notificacion
from app.service.auth_service import get_current_user

router = APIRouter()


@router.get("/mis")
async def mis_notificaciones(
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Devuelve las últimas 30 notificaciones del usuario, más recientes primero."""
    result = await db.execute(
        select(Notificacion)
        .where(Notificacion.usuario_id == usuario.id)
        .order_by(Notificacion.creada_en.desc())
        .limit(30)
    )
    notifs = result.scalars().all()
    return {
        "notificaciones": [
            {
                "id": n.id,
                "titulo": n.titulo,
                "mensaje": n.mensaje,
                "tipo": n.tipo,
                "leida": n.leida,
                "url_accion": n.url_accion,
                "creada_en": n.creada_en,
            }
            for n in notifs
        ],
        "sin_leer": sum(1 for n in notifs if not n.leida),
    }


@router.patch("/{notif_id}/leer")
async def marcar_leida(
    notif_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Marca una notificación como leída."""
    notif = await db.get(Notificacion, notif_id)
    if notif and notif.usuario_id == usuario.id:
        notif.leida = True
        await db.commit()
    return {"ok": True}


@router.patch("/leer-todas")
async def marcar_todas_leidas(
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Marca todas las notificaciones del usuario como leídas."""
    result = await db.execute(
        select(Notificacion).where(
            Notificacion.usuario_id == usuario.id,
            Notificacion.leida == False,
        )
    )
    for n in result.scalars().all():
        n.leida = True
    await db.commit()
    return {"ok": True}
