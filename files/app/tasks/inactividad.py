"""
Tarea periódica — Notificaciones de inactividad
Corre cada hora. Si un usuario no ha accedido en 2+ días y no tiene
ya una notificación de recordatorio sin leer, se le crea una.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_, not_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Usuario, Notificacion, RolUsuario
from app.service.notificacion_service import notificacion_inactividad


async def verificar_usuarios_inactivos(db: AsyncSession) -> int:
    """
    Revisa todos los estudiantes activos. Si llevan 2+ dias sin acceder
    y no tienen ya una notificacion de recordatorio pendiente de leer,
    crea la notificacion.
    Devuelve el numero de notificaciones generadas.
    """
    limite = datetime.now(timezone.utc) - timedelta(days=2)
    generadas = 0

    result = await db.execute(
        select(Usuario).where(
            and_(
                Usuario.activo == True,
                Usuario.rol == RolUsuario.ESTUDIANTE,
                (Usuario.ultimo_acceso == None) | (Usuario.ultimo_acceso < limite),
                not_(
                    exists().where(
                        and_(
                            Notificacion.usuario_id == Usuario.id,
                            Notificacion.tipo == "recordatorio",
                            Notificacion.leida == False,
                        )
                    )
                ),
            )
        )
    )
    usuarios = result.scalars().all()

    for usuario in usuarios:
        await notificacion_inactividad(db, usuario)
        generadas += 1

    return generadas
