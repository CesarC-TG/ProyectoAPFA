"""
Router de Administración — stats, CRUD usuarios, asignaciones, emergencias, actividad
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update, delete
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import uuid

from app.database import get_db
from app.models import (
    Usuario, EntradaDiario, EventoSOS, Cita, MensajeChat,
    RolUsuario, EstadoCita, AsignacionPsicologo,
)
from app.schemas import (
    CitaCrear, CitaRespuesta, MensajeRespuesta,
    UsuarioRespuesta, AsignacionCrear,
)
from app.service.auth_service import (
    get_current_psicologo, get_current_admin, hashear_password
)

router = APIRouter()


# ── Stats ──────────────────────────────────────────────────

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


# ── Actividad de usuarios (para psicólogo y admin) ────────

@router.get("/actividad-usuarios")
async def reporte_actividad_usuarios(
    dias: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_psicologo),
):
    """Reporte de actividad: último acceso, eventos SOS, días sin entrar."""
    desde = datetime.now(timezone.utc) - timedelta(days=dias)

    result = await db.execute(
        select(Usuario)
        .where(Usuario.rol == RolUsuario.ESTUDIANTE, Usuario.activo == True)
        .order_by(Usuario.ultimo_acceso.desc().nullslast())
    )
    estudiantes = result.scalars().all()
    ahora = datetime.now(timezone.utc)

    datos = []
    for u in estudiantes:
        # Días sin entrar
        if u.ultimo_acceso:
            ua = u.ultimo_acceso
            if ua.tzinfo is None:
                ua = ua.replace(tzinfo=timezone.utc)
            dias_sin_entrar = (ahora - ua).days
        else:
            dias_sin_entrar = None

        # Eventos SOS del usuario
        sos_count = (await db.execute(
            select(func.count()).select_from(EventoSOS)
            .where(EventoSOS.usuario_id == u.id, EventoSOS.creado_en >= desde)
        )).scalar() or 0

        # Entradas diario últimos N días
        entradas_count = (await db.execute(
            select(func.count()).select_from(EntradaDiario)
            .where(EntradaDiario.usuario_id == u.id, EntradaDiario.creada_en >= desde)
        )).scalar() or 0

        datos.append({
            "id":              u.id,
            "nombre":          u.nombre,
            "apellidos":       u.apellidos,
            "email":           u.email,
            "carrera":         u.carrera,
            "ultimo_acceso":   u.ultimo_acceso.isoformat() if u.ultimo_acceso else None,
            "dias_sin_entrar": dias_sin_entrar,
            "sos_periodo":     sos_count,
            "entradas_periodo":entradas_count,
            "estado": (
                "sin_registro" if dias_sin_entrar is None else
                "critico"      if dias_sin_entrar >= 14  else
                "alerta"       if dias_sin_entrar >= 7   else
                "activo"
            ),
        })

    return datos


@router.get("/sos-actividad")
async def actividad_sos(
    dias: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_psicologo),
):
    """Detalle de todos los eventos SOS en los últimos N días."""
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


# ── CRUD Usuarios ──────────────────────────────────────────

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
    if rol:      filtros.append(Usuario.rol == rol)
    if activo is not None: filtros.append(Usuario.activo == activo)
    if buscar:
        like = f"%{buscar}%"
        filtros.append(
            Usuario.nombre.ilike(like) | Usuario.email.ilike(like) | Usuario.numero_cuenta.ilike(like)
        )
    query = (
        select(Usuario).offset((pagina - 1) * por_pagina).limit(por_pagina)
        .order_by(Usuario.creado_en.desc())
    )
    if filtros: query = query.where(and_(*filtros))
    result = await db.execute(query)
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
            "ultimo_acceso": u.ultimo_acceso.isoformat() if u.ultimo_acceso else None,
        }
        for u in result.scalars().all()
    ]


@router.post("/usuarios", status_code=201)
async def crear_usuario_admin(
    datos: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    """Admin crea un usuario con cualquier rol."""
    email = datos.get("email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="El correo es obligatorio")

    existe = await db.execute(select(Usuario).where(Usuario.email == email))
    if existe.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    password_raw = datos.get("password", "")
    if len(password_raw) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    rol_str = datos.get("rol", "estudiante").lower()
    try:
        rol = RolUsuario(rol_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Rol inválido: {rol_str}")

    nuevo = Usuario(
        nombre        = datos.get("nombre", "").strip(),
        apellidos     = datos.get("apellidos", "").strip() or None,
        email         = email,
        telefono      = datos.get("telefono") or None,
        carrera       = datos.get("carrera") or None,
        semestre      = datos.get("semestre") or None,
        password_hash = hashear_password(password_raw),
        rol           = rol,
        activo        = True,
    )
    db.add(nuevo)
    await db.commit()
    await db.refresh(nuevo)
    return {"mensaje": f"Usuario {nuevo.nombre} creado", "id": nuevo.id}


@router.patch("/usuarios/{usuario_id}", response_model=MensajeRespuesta)
async def editar_usuario_admin(
    usuario_id: str,
    datos: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    """Admin edita cualquier campo de un usuario."""
    usuario = await db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    campos_editables = ["nombre", "apellidos", "carrera", "semestre", "telefono", "activo"]
    for campo in campos_editables:
        if campo in datos:
            setattr(usuario, campo, datos[campo])

    if "rol" in datos and usuario_id != admin.id:
        try:
            usuario.rol = RolUsuario(datos["rol"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Rol inválido")

    if "password" in datos and datos["password"]:
        if len(datos["password"]) < 8:
            raise HTTPException(status_code=400, detail="Contraseña muy corta (mín. 8)")
        usuario.password_hash = hashear_password(datos["password"])

    await db.commit()
    return {"mensaje": "Usuario actualizado correctamente"}


@router.delete("/usuarios/{usuario_id}", response_model=MensajeRespuesta)
async def eliminar_usuario_admin(
    usuario_id: str,
    permanente: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    """Admin elimina un usuario. Por defecto hace soft-delete (desactiva)."""
    if usuario_id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")

    usuario = await db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if permanente:
        await db.delete(usuario)
        await db.commit()
        return {"mensaje": "Usuario eliminado permanentemente"}
    else:
        usuario.activo = False
        await db.commit()
        return {"mensaje": "Usuario desactivado correctamente"}


@router.patch("/usuarios/{usuario_id}/rol", response_model=MensajeRespuesta)
async def cambiar_rol_usuario(
    usuario_id: str,
    nuevo_rol: RolUsuario,
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
    return {"mensaje": f"Usuario {'activado' if activo else 'desactivado'}"}


# ── Asignaciones ───────────────────────────────────────────

@router.get("/asignaciones", response_model=list)
async def listar_asignaciones(
    psicologo_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    filtros = [AsignacionPsicologo.activa == True]
    if psicologo_id:
        filtros.append(AsignacionPsicologo.psicologo_id == psicologo_id)
    result = await db.execute(
        select(AsignacionPsicologo).where(and_(*filtros))
        .order_by(AsignacionPsicologo.creada_en.desc())
    )
    out = []
    for a in result.scalars().all():
        psico = await db.get(Usuario, a.psicologo_id)
        est   = await db.get(Usuario, a.estudiante_id)
        out.append({
            "id": a.id, "psicologo_id": a.psicologo_id, "estudiante_id": a.estudiante_id,
            "psicologo":  {"nombre": psico.nombre, "email": psico.email} if psico else {},
            "estudiante": {"nombre": est.nombre,   "email": est.email}   if est   else {},
            "notas": a.notas, "creada_en": a.creada_en.isoformat() if a.creada_en else None,
        })
    return out


@router.post("/asignaciones", status_code=201)
async def crear_asignacion(
    datos: AsignacionCrear,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    psico = await db.get(Usuario, datos.psicologo_id)
    if not psico or psico.rol not in (RolUsuario.PSICOLOGO, RolUsuario.ADMIN):
        raise HTTPException(status_code=404, detail="Psicólogo no encontrado")
    est = await db.get(Usuario, datos.estudiante_id)
    if not est or est.rol != RolUsuario.ESTUDIANTE:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
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
        id=str(uuid.uuid4()), psicologo_id=datos.psicologo_id,
        estudiante_id=datos.estudiante_id, notas=datos.notas,
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
    result = await db.execute(
        select(Usuario).where(Usuario.rol == RolUsuario.PSICOLOGO, Usuario.activo == True)
    )
    out = []
    for p in result.scalars().all():
        count = (await db.execute(
            select(func.count()).select_from(AsignacionPsicologo)
            .where(AsignacionPsicologo.psicologo_id == p.id, AsignacionPsicologo.activa == True)
        )).scalar() or 0
        out.append({
            "id": p.id, "nombre": p.nombre, "apellidos": p.apellidos,
            "email": p.email, "carrera": p.carrera, "estudiantes_actuales": count,
        })
    return out


# ── Citas ──────────────────────────────────────────────────

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
            Cita.psicologo_id == psicologo.id, Cita.fecha_hora == datos.fecha_hora,
            Cita.estado.in_([EstadoCita.PENDIENTE, EstadoCita.CONFIRMADA]),
        )
    )
    if conflicto.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya tienes una cita en ese horario")
    cita = Cita(
        id=str(uuid.uuid4()), estudiante_id=datos.estudiante_id,
        psicologo_id=psicologo.id, fecha_hora=datos.fecha_hora,
        modalidad=datos.modalidad, motivo=datos.motivo,
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
    if estado: filtros.append(Cita.estado == estado)
    result = await db.execute(
        select(Cita).where(and_(*filtros)).order_by(Cita.fecha_hora.asc())
    )
    return result.scalars().all()


@router.patch("/citas/{cita_id}/estado", response_model=MensajeRespuesta)
async def actualizar_estado_cita(
    cita_id: str, estado: EstadoCita, notas: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    cita = await db.get(Cita, cita_id)
    if not cita or cita.psicologo_id != psicologo.id:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    cita.estado = estado
    if notas: cita.notas_psicologo = notas
    await db.commit()
    return {"mensaje": f"Cita actualizada a {estado}"}


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