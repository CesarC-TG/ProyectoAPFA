"""
Router de Usuarios — perfil propio, citas del estudiante, notificaciones
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional
import uuid, os, shutil

from app.database import get_db
from app.models import Usuario, Cita, Notificacion, EstadoCita
from app.schemas import (
    UsuarioActualizar, UsuarioRespuesta,
    CitaCrear, CitaRespuesta,
    NotificacionRespuesta, MensajeRespuesta,
)
from app.service.auth_service import get_current_user
from app.config import settings

router = APIRouter()


# ── Perfil ────────────────────────────────────────────────

@router.get("/me", response_model=UsuarioRespuesta)
async def obtener_perfil(usuario: Usuario = Depends(get_current_user)):
    """Datos completos del usuario autenticado."""
    return usuario


@router.patch("/me", response_model=UsuarioRespuesta)
async def actualizar_perfil(
    datos: UsuarioActualizar,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Actualiza campos editables del perfil propio."""
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(usuario, campo, valor)
    await db.commit()
    await db.refresh(usuario)
    return usuario




# Alias para el frontend (/usuarios/mi-perfil en lugar de /usuarios/me)
@router.patch("/mi-perfil", response_model=UsuarioRespuesta)
async def actualizar_mi_perfil(
    datos: UsuarioActualizar,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Alias de PATCH /me — actualiza perfil incluyendo contacto de emergencia."""
    return await actualizar_perfil(datos, db, usuario)
@router.post("/me/avatar", response_model=UsuarioRespuesta)
async def subir_avatar(
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Sube o reemplaza el avatar del usuario."""
    # Validar tipo y tamaño
    if archivo.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=415, detail="Solo se aceptan imágenes JPEG, PNG o WebP")

    contenido = await archivo.read()
    if len(contenido) > settings.MAX_FILE_SIZE_MB * 1_000_000:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el límite de {settings.MAX_FILE_SIZE_MB} MB",
        )

    # Guardar en disco
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext      = archivo.filename.rsplit(".", 1)[-1].lower()
    nombre   = f"avatar_{usuario.id}.{ext}"
    ruta     = os.path.join(settings.UPLOAD_DIR, nombre)

    with open(ruta, "wb") as f:
        f.write(contenido)

    usuario.avatar_url = f"/static/uploads/{nombre}"
    await db.commit()
    await db.refresh(usuario)
    return usuario


# ── Citas del estudiante ──────────────────────────────────

@router.get("/me/citas", response_model=list[CitaRespuesta])
async def mis_citas(
    estado: Optional[EstadoCita] = None,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Lista las citas del estudiante autenticado."""
    filtros = [Cita.estudiante_id == usuario.id]
    if estado:
        filtros.append(Cita.estado == estado)

    result = await db.execute(
        select(Cita)
        .where(and_(*filtros))
        .order_by(Cita.fecha_hora.desc())
    )
    return result.scalars().all()


@router.post("/me/citas", response_model=CitaRespuesta, status_code=201)
async def solicitar_cita(
    datos: CitaCrear,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Estudiante solicita una cita con un psicólogo."""
    # Verificar que el psicólogo existe y tiene el rol correcto
    from app.models import RolUsuario
    psicologo = await db.get(Usuario, datos.psicologo_id)
    if not psicologo or psicologo.rol not in (RolUsuario.PSICOLOGO, RolUsuario.ADMIN):
        raise HTTPException(status_code=404, detail="Psicólogo no encontrado")

    cita = Cita(
        id            = str(uuid.uuid4()),
        estudiante_id = usuario.id,
        psicologo_id  = datos.psicologo_id,
        fecha_hora    = datos.fecha_hora,
        modalidad     = datos.modalidad,
        motivo        = datos.motivo,
    )
    db.add(cita)
    await db.commit()
    await db.refresh(cita)
    return cita


@router.delete("/me/citas/{cita_id}", response_model=MensajeRespuesta)
async def cancelar_cita(
    cita_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Estudiante cancela una cita pendiente."""
    cita = await db.get(Cita, cita_id)
    if not cita or cita.estudiante_id != usuario.id:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    if cita.estado not in (EstadoCita.PENDIENTE, EstadoCita.CONFIRMADA):
        raise HTTPException(status_code=400, detail="Solo puedes cancelar citas pendientes o confirmadas")

    cita.estado = EstadoCita.CANCELADA
    await db.commit()
    return {"mensaje": "Cita cancelada correctamente"}


# ── Notificaciones ────────────────────────────────────────

@router.get("/me/notificaciones", response_model=list[NotificacionRespuesta])
async def mis_notificaciones(
    solo_no_leidas: bool = False,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Lista notificaciones del usuario, opcionalmente solo las no leídas."""
    filtros = [Notificacion.usuario_id == usuario.id]
    if solo_no_leidas:
        filtros.append(Notificacion.leida == False)

    result = await db.execute(
        select(Notificacion)
        .where(and_(*filtros))
        .order_by(Notificacion.creada_en.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.patch("/me/notificaciones/{notif_id}/leer", response_model=MensajeRespuesta)
async def marcar_notificacion_leida(
    notif_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Marca una notificación como leída."""
    notif = await db.get(Notificacion, notif_id)
    if not notif or notif.usuario_id != usuario.id:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    notif.leida = True
    await db.commit()
    return {"mensaje": "Notificación marcada como leída"}


@router.post("/me/notificaciones/leer-todas", response_model=MensajeRespuesta)
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
    notifs = result.scalars().all()
    for n in notifs:
        n.leida = True
    await db.commit()
    return {"mensaje": f"{len(notifs)} notificación(es) marcada(s) como leídas"}


# ── Directorio de psicólogos (para agendar citas) ─────────

@router.get("/psicologos", response_model=list[UsuarioRespuesta])
async def listar_psicologos(
    db: AsyncSession = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
):
    """Lista psicólogos disponibles para agendar citas."""
    from app.models import RolUsuario
    result = await db.execute(
        select(Usuario).where(
            Usuario.rol == RolUsuario.PSICOLOGO,
            Usuario.activo == True,
        )
    )
    return result.scalars().all()


@router.get("/", response_model=list[UsuarioRespuesta])
async def listar_usuarios_sistema(
    db: AsyncSession = Depends(get_db),
    usuario_admin: Usuario = Depends(get_current_user)
):
    """Retorna todos los usuarios si el que pide es ADMIN."""
    from app.models import RolUsuario
    
    # Verificación de seguridad
    if usuario_admin.rol != RolUsuario.ADMIN:
        raise HTTPException(status_code=403, detail="No autorizado")

    result = await db.execute(select(Usuario).order_by(Usuario.nombre))
    return result.scalars().all()