"""
Router de Administración — stats, usuarios, roles, asignaciones psicólogo↔estudiante
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from typing import Optional
from datetime import datetime, timedelta, timezone
import uuid

from app.database import get_db
from app.models import (
    Usuario, EntradaDiario, EventoSOS, Cita,
    RolUsuario, EstadoCita, MensajeChat, AsignacionPsicologo,
)
from app.schemas import (
    CitaCrear, CitaRespuesta, MensajeRespuesta,
    UsuarioRespuesta, AsignacionCrear, AsignacionRespuesta,
)
from app.service.auth_service import get_current_psicologo, get_current_admin

router = APIRouter()


# ── Dashboard Stats ────────────────────────────────────────

@router.get("/stats")
async def obtener_estadisticas(
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_psicologo),
):
    hoy        = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    hace_7dias = hoy - timedelta(days=7)

    total_estudiantes = (await db.execute(
        select(func.count()).select_from(Usuario)
        .where(Usuario.rol == RolUsuario.ESTUDIANTE, Usuario.activo == True)
    )).scalar() or 0

    total_psicologos = (await db.execute(
        select(func.count()).select_from(Usuario)
        .where(Usuario.rol == RolUsuario.PSICOLOGO, Usuario.activo == True)
    )).scalar() or 0

    entradas_hoy = (await db.execute(
        select(func.count()).select_from(EntradaDiario)
        .where(EntradaDiario.creada_en >= hoy)
    )).scalar() or 0

    alertas_activas = (await db.execute(
        select(func.count()).select_from(EventoSOS)
        .where(EventoSOS.atendido == False)
    )).scalar() or 0

    entradas_compartidas = (await db.execute(
        select(func.count()).select_from(EntradaDiario)
        .where(EntradaDiario.compartida == True)
    )).scalar() or 0

    sesiones_chat_semana = (await db.execute(
        select(func.count(MensajeChat.sesion_chat_id.distinct()))
        .where(MensajeChat.creado_en >= hace_7dias)
    )).scalar() or 0

    return {
        "total_estudiantes":    total_estudiantes,
        "total_psicologos":     total_psicologos,
        "entradas_hoy":         entradas_hoy,
        "alertas_activas":      alertas_activas,
        "entradas_compartidas": entradas_compartidas,
        "sesiones_chat_semana": sesiones_chat_semana,
        "timestamp":            datetime.now(timezone.utc).isoformat(),
    }


# ── Gestión de usuarios ────────────────────────────────────

@router.get("/usuarios", response_model=list)
async def listar_usuarios(
    rol:        Optional[str]  = None,
    activo:     Optional[bool] = None,
    buscar:     Optional[str]  = None,
    pagina:     int = Query(default=1,  ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    filtros = []
    if rol:
        filtros.append(Usuario.rol == rol)
    if activo is not None:
        filtros.append(Usuario.activo == activo)
    if buscar:
        like = f"%{buscar}%"
        filtros.append(
            Usuario.nombre.ilike(like)
            | Usuario.email.ilike(like)
            | Usuario.numero_cuenta.ilike(like)
        )

    query = (
        select(Usuario)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
        .order_by(Usuario.creado_en.desc())
    )
    if filtros:
        query = query.where(and_(*filtros))

    result = await db.execute(query)
    usuarios = result.scalars().all()
    return [
        {
            "id":         u.id,
            "nombre":     u.nombre,
            "apellidos":  u.apellidos,
            "email":      u.email,
            "telefono":   u.telefono,
            "carrera":    u.carrera,
            "semestre":   u.semestre,
            "rol":        u.rol,
            "activo":     u.activo,
            "creado_en":  u.creado_en.isoformat() if u.creado_en else None,
        }
        for u in usuarios
    ]


@router.patch("/usuarios/{usuario_id}/rol", response_model=MensajeRespuesta)
async def cambiar_rol_usuario(
    usuario_id: str,
    nuevo_rol:  RolUsuario,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    if usuario_id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes cambiar tu propio rol")

    usuario = await db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    usuario.rol = nuevo_rol
    await db.commit()
    return {"mensaje": f"Rol actualizado a {nuevo_rol}"}


@router.patch("/usuarios/{usuario_id}/activar", response_model=MensajeRespuesta)
async def activar_desactivar_usuario(
    usuario_id: str,
    activo: bool,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    if usuario_id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo")

    usuario = await db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    usuario.activo = activo
    await db.commit()
    estado = "activado" if activo else "desactivado"
    return {"mensaje": f"Usuario {estado} correctamente"}


# ── Asignaciones psicólogo ↔ estudiante ────────────────────

@router.get("/asignaciones", response_model=list)
async def listar_asignaciones(
    psicologo_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    """Lista todas las asignaciones activas, opcionalmente filtradas por psicólogo."""
    filtros = [AsignacionPsicologo.activa == True]
    if psicologo_id:
        filtros.append(AsignacionPsicologo.psicologo_id == psicologo_id)

    result = await db.execute(
        select(AsignacionPsicologo).where(and_(*filtros))
        .order_by(AsignacionPsicologo.creada_en.desc())
    )
    asigs = result.scalars().all()

    out = []
    for a in asigs:
        psico = await db.get(Usuario, a.psicologo_id)
        est   = await db.get(Usuario, a.estudiante_id)
        out.append({
            "id":           a.id,
            "psicologo_id": a.psicologo_id,
            "psicologo":    {"nombre": psico.nombre, "email": psico.email} if psico else {},
            "estudiante_id":a.estudiante_id,
            "estudiante":   {"nombre": est.nombre,   "email": est.email}   if est   else {},
            "notas":        a.notas,
            "creada_en":    a.creada_en.isoformat() if a.creada_en else None,
        })
    return out


@router.post("/asignaciones", status_code=201)
async def crear_asignacion(
    datos: AsignacionCrear,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    """Asignar un estudiante a un psicólogo."""
    psico = await db.get(Usuario, datos.psicologo_id)
    if not psico or psico.rol not in (RolUsuario.PSICOLOGO, RolUsuario.ADMIN):
        raise HTTPException(status_code=404, detail="Psicólogo no encontrado")

    est = await db.get(Usuario, datos.estudiante_id)
    if not est or est.rol != RolUsuario.ESTUDIANTE:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    # Verificar que no exista ya
    existing = await db.execute(
        select(AsignacionPsicologo).where(
            AsignacionPsicologo.psicologo_id  == datos.psicologo_id,
            AsignacionPsicologo.estudiante_id == datos.estudiante_id,
            AsignacionPsicologo.activa == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Esta asignación ya existe")

    asig = AsignacionPsicologo(
        id            = str(uuid.uuid4()),
        psicologo_id  = datos.psicologo_id,
        estudiante_id = datos.estudiante_id,
        notas         = datos.notas,
    )
    db.add(asig)
    await db.commit()
    await db.refresh(asig)
    return {"mensaje": f"Estudiante {est.nombre} asignado a {psico.nombre}", "id": asig.id}


@router.delete("/asignaciones/{asig_id}", response_model=MensajeRespuesta)
async def eliminar_asignacion(
    asig_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    asig = await db.get(AsignacionPsicologo, asig_id)
    if not asig:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    asig.activa = False
    await db.commit()
    return {"mensaje": "Asignación eliminada"}


@router.get("/psicologos-disponibles")
async def psicologos_con_disponibilidad(
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    """Lista psicólogos con conteo de estudiantes asignados."""
    result = await db.execute(
        select(Usuario).where(Usuario.rol == RolUsuario.PSICOLOGO, Usuario.activo == True)
    )
    psicologos = result.scalars().all()
    out = []
    for p in psicologos:
        count = (await db.execute(
            select(func.count()).select_from(AsignacionPsicologo)
            .where(AsignacionPsicologo.psicologo_id == p.id, AsignacionPsicologo.activa == True)
        )).scalar() or 0
        out.append({
            "id":                  p.id,
            "nombre":              p.nombre,
            "apellidos":           p.apellidos,
            "email":               p.email,
            "carrera":             p.carrera,
            "estudiantes_actuales":count,
        })
    return out


# ── Gestión de citas ───────────────────────────────────────

@router.post("/citas", response_model=CitaRespuesta, status_code=201)
async def crear_cita(
    datos: CitaCrear,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    estudiante = await db.get(Usuario, datos.estudiante_id)
    if not estudiante or estudiante.rol != RolUsuario.ESTUDIANTE:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    conflicto = await db.execute(
        select(Cita).where(
            Cita.psicologo_id == psicologo.id,
            Cita.fecha_hora   == datos.fecha_hora,
            Cita.estado.in_([EstadoCita.PENDIENTE, EstadoCita.CONFIRMADA]),
        )
    )
    if conflicto.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya tienes una cita agendada en ese horario")

    cita = Cita(
        id            = str(uuid.uuid4()),
        estudiante_id = datos.estudiante_id,
        psicologo_id  = psicologo.id,
        fecha_hora    = datos.fecha_hora,
        modalidad     = datos.modalidad,
        motivo        = datos.motivo,
    )
    db.add(cita)
    await db.commit()
    await db.refresh(cita)
    return cita


@router.get("/citas", response_model=list)
async def listar_citas_psicologo(
    estado: Optional[EstadoCita] = None,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    filtros = [Cita.psicologo_id == psicologo.id]
    if estado:
        filtros.append(Cita.estado == estado)

    result = await db.execute(
        select(Cita).where(and_(*filtros)).order_by(Cita.fecha_hora.asc())
    )
    return result.scalars().all()


@router.patch("/citas/{cita_id}/estado", response_model=MensajeRespuesta)
async def actualizar_estado_cita(
    cita_id: str,
    estado:  EstadoCita,
    notas:   Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    cita = await db.get(Cita, cita_id)
    if not cita or cita.psicologo_id != psicologo.id:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    cita.estado = estado
    if notas:
        cita.notas_psicologo = notas
    await db.commit()
    return {"mensaje": f"Cita actualizada a estado: {estado}"}


# ── Reportes ───────────────────────────────────────────────

@router.get("/reportes/estados-animo")
async def reporte_estados_animo(
    dias: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_psicologo),
):
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    result = await db.execute(
        select(EntradaDiario.estado_animo, func.count(EntradaDiario.id).label("total"))
        .where(EntradaDiario.creada_en >= desde)
        .group_by(EntradaDiario.estado_animo)
    )
    return [{"estado": r.estado_animo, "total": r.total} for r in result.all()]