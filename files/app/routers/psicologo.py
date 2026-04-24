"""
Router del Psicólogo — panel, estudiantes, diarios, citas, actividad, stats SOS
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models import Usuario, EntradaDiario, Cita, RolUsuario, EstadoCita, EventoSOS, AsignacionPsicologo
from app.service.auth_service import get_current_psicologo

router = APIRouter()


@router.get("/perfil")
async def mi_perfil_psicologo(psicologo: Usuario = Depends(get_current_psicologo)):
    return {
        "id": psicologo.id, "nombre": psicologo.nombre, "apellidos": psicologo.apellidos,
        "email": psicologo.email, "carrera": psicologo.carrera,
        "semestre": psicologo.semestre, "avatar_url": psicologo.avatar_url, "rol": psicologo.rol,
    }


@router.get("/mis-estudiantes")
async def listar_mis_estudiantes(
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    mapa = {}

    # Por citas
    res = await db.execute(
        select(Usuario).join(Cita, Cita.estudiante_id == Usuario.id)
        .where(Cita.psicologo_id == psicologo.id, Usuario.activo == True).distinct()
    )
    for u in res.scalars().all(): mapa[u.id] = u

    # Por asignación directa
    res2 = await db.execute(
        select(Usuario).join(AsignacionPsicologo, AsignacionPsicologo.estudiante_id == Usuario.id)
        .where(AsignacionPsicologo.psicologo_id == psicologo.id, AsignacionPsicologo.activa == True).distinct()
    )
    for u in res2.scalars().all(): mapa[u.id] = u

    # Por diario compartido
    res3 = await db.execute(
        select(Usuario).join(EntradaDiario, EntradaDiario.usuario_id == Usuario.id)
        .where(EntradaDiario.compartida == True, EntradaDiario.psicologo_id == psicologo.id).distinct()
    )
    for u in res3.scalars().all(): mapa[u.id] = u

    ahora = datetime.now(timezone.utc)
    out = []
    for u in mapa.values():
        # Días sin entrar
        if u.ultimo_acceso:
            ua = u.ultimo_acceso
            if ua.tzinfo is None: ua = ua.replace(tzinfo=timezone.utc)
            dias_sin = (ahora - ua).days
        else:
            dias_sin = None

        out.append({
            "id": u.id, "nombre": u.nombre, "apellidos": u.apellidos,
            "email": u.email, "carrera": u.carrera, "semestre": u.semestre,
            "avatar_url": u.avatar_url,
            "ultimo_acceso": u.ultimo_acceso.isoformat() if u.ultimo_acceso else None,
            "dias_sin_entrar": dias_sin,
        })
    return out


@router.get("/diarios")
async def ver_diarios_compartidos(
    estudiante_id: Optional[str] = None,
    solo_crisis: bool = False,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    sub_asig = select(AsignacionPsicologo.estudiante_id).where(
        AsignacionPsicologo.psicologo_id == psicologo.id, AsignacionPsicologo.activa == True
    )
    sub_citas = select(Cita.estudiante_id).where(Cita.psicologo_id == psicologo.id)
    sub_diario_directo = select(EntradaDiario.usuario_id).where(
        EntradaDiario.psicologo_id == psicologo.id, EntradaDiario.compartida == True
    )

    filtros = [
        EntradaDiario.compartida == True,
        or_(
            EntradaDiario.usuario_id.in_(sub_asig),
            EntradaDiario.usuario_id.in_(sub_citas),
            EntradaDiario.usuario_id.in_(sub_diario_directo),
        )
    ]
    if estudiante_id: filtros.append(EntradaDiario.usuario_id == estudiante_id)
    if solo_crisis:   filtros.append(EntradaDiario.alerta_crisis == True)

    result = await db.execute(
        select(EntradaDiario, Usuario)
        .join(Usuario, EntradaDiario.usuario_id == Usuario.id)
        .where(and_(*filtros))
        .order_by(EntradaDiario.creada_en.desc()).limit(200)
    )
    return [
        {
            "id": e.id, "texto": e.texto, "estado_animo": e.estado_animo,
            "etiquetas": e.etiquetas, "alerta_crisis": e.alerta_crisis,
            "creada_en": e.creada_en.isoformat(),
            "estudiante": {"id": u.id, "nombre": u.nombre, "email": u.email, "carrera": u.carrera},
        }
        for e, u in result.all()
    ]


@router.get("/citas")
async def mis_citas(
    estado: Optional[EstadoCita] = None,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    filtros = [Cita.psicologo_id == psicologo.id]
    if estado: filtros.append(Cita.estado == estado)
    result = await db.execute(
        select(Cita, Usuario)
        .join(Usuario, Cita.estudiante_id == Usuario.id)
        .where(and_(*filtros)).order_by(Cita.fecha_hora.asc()).limit(100)
    )
    return [
        {
            "id": c.id, "fecha_hora": c.fecha_hora.isoformat(), "modalidad": c.modalidad,
            "estado": c.estado, "motivo": c.motivo,
            "estudiante": {"id": u.id, "nombre": u.nombre, "email": u.email},
        }
        for c, u in result.all()
    ]


@router.get("/actividad")
async def actividad_mis_estudiantes(
    dias: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """Reporte de actividad de los estudiantes asignados a este psicólogo."""
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    ahora = datetime.now(timezone.utc)

    # Obtener IDs de estudiantes asignados
    sub_asig  = select(AsignacionPsicologo.estudiante_id).where(
        AsignacionPsicologo.psicologo_id == psicologo.id, AsignacionPsicologo.activa == True
    )
    sub_citas = select(Cita.estudiante_id).where(Cita.psicologo_id == psicologo.id)

    result = await db.execute(
        select(Usuario).where(
            Usuario.rol == RolUsuario.ESTUDIANTE, Usuario.activo == True,
            or_(Usuario.id.in_(sub_asig), Usuario.id.in_(sub_citas))
        )
    )
    estudiantes = result.scalars().all()

    out = []
    for u in estudiantes:
        if u.ultimo_acceso:
            ua = u.ultimo_acceso.replace(tzinfo=timezone.utc) if u.ultimo_acceso.tzinfo is None else u.ultimo_acceso
            dias_sin = (ahora - ua).days
        else:
            dias_sin = None

        sos = (await db.execute(
            select(func.count()).select_from(EventoSOS)
            .where(EventoSOS.usuario_id == u.id, EventoSOS.creado_en >= desde)
        )).scalar() or 0

        entradas = (await db.execute(
            select(func.count()).select_from(EntradaDiario)
            .where(EntradaDiario.usuario_id == u.id, EntradaDiario.creada_en >= desde)
        )).scalar() or 0

        # Eventos SOS detalle
        sos_eventos = await db.execute(
            select(EventoSOS).where(EventoSOS.usuario_id == u.id, EventoSOS.creado_en >= desde)
            .order_by(EventoSOS.creado_en.desc()).limit(5)
        )

        out.append({
            "id": u.id, "nombre": u.nombre, "apellidos": u.apellidos,
            "email": u.email, "carrera": u.carrera,
            "ultimo_acceso":   u.ultimo_acceso.isoformat() if u.ultimo_acceso else None,
            "dias_sin_entrar": dias_sin,
            "sos_periodo":     sos,
            "entradas_periodo":entradas,
            "sos_eventos": [
                {"tipo": e.tipo_accion, "fecha": e.creado_en.isoformat(), "atendido": e.atendido}
                for e in sos_eventos.scalars().all()
            ],
            "estado": (
                "sin_registro" if dias_sin is None else
                "critico"      if dias_sin >= 14  else
                "alerta"       if dias_sin >= 7   else
                "activo"
            ),
        })
    return out


@router.post("/citas", status_code=201)
async def crear_cita_psicologo(
    datos: dict,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """El psicólogo agenda una cita con uno de sus estudiantes."""
    estudiante_id = datos.get("estudiante_id")
    if not estudiante_id:
        raise HTTPException(status_code=400, detail="Se requiere estudiante_id")

    fecha_str = datos.get("fecha_hora")
    if not fecha_str:
        raise HTTPException(status_code=400, detail="Se requiere fecha_hora")

    try:
        from datetime import datetime as dt
        fecha = dt.fromisoformat(fecha_str.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido (usa ISO 8601)")

    modalidad = (datos.get("modalidad") or "presencial").lower()

    cita = Cita(
        estudiante_id = estudiante_id,
        psicologo_id  = psicologo.id,
        fecha_hora    = fecha,
        modalidad     = modalidad,
        motivo        = datos.get("motivo", ""),
        estado        = EstadoCita.PENDIENTE,
    )
    db.add(cita)
    await db.commit()
    await db.refresh(cita)

    return {
        "id":            cita.id,
        "fecha_hora":    cita.fecha_hora.isoformat(),
        "modalidad":     cita.modalidad,
        "estado":        cita.estado,
        "motivo":        cita.motivo,
        "estudiante_id": cita.estudiante_id,
        "psicologo_id":  cita.psicologo_id,
    }


@router.patch("/citas/{cita_id}/estado")
async def actualizar_estado_cita(
    cita_id: str,
    estado: str,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """El psicólogo actualiza el estado de una cita (confirmada, cancelada, completada)."""
    result = await db.execute(
        select(Cita).where(Cita.id == cita_id, Cita.psicologo_id == psicologo.id)
    )
    cita = result.scalar_one_or_none()
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada o no autorizada")

    try:
        cita.estado = EstadoCita(estado.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Estado inválido: '{estado}'. Usa: pendiente, confirmada, completada, cancelada")

    await db.commit()
    return {"mensaje": f"Cita actualizada a '{estado}'"}


@router.get("/stats")
async def stats_psicologo(
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    sub_asig  = select(AsignacionPsicologo.estudiante_id).where(
        AsignacionPsicologo.psicologo_id == psicologo.id, AsignacionPsicologo.activa == True
    )
    sub_citas_ids = select(Cita.estudiante_id).where(Cita.psicologo_id == psicologo.id)

    res_asig  = await db.execute(sub_asig)
    res_citas = await db.execute(sub_citas_ids)
    ids = set(res_asig.scalars().all()) | set(res_citas.scalars().all())
    total_estudiantes = len(ids)

    citas_pendientes = (await db.execute(
        select(func.count()).select_from(Cita)
        .where(Cita.psicologo_id == psicologo.id, Cita.estado == EstadoCita.PENDIENTE)
    )).scalar() or 0

    diarios_comp = (await db.execute(
        select(func.count()).select_from(EntradaDiario)
        .where(
            EntradaDiario.compartida == True,
            or_(EntradaDiario.usuario_id.in_(sub_asig), EntradaDiario.psicologo_id == psicologo.id)
        )
    )).scalar() or 0

    alertas = (await db.execute(
        select(func.count()).select_from(EntradaDiario)
        .where(
            EntradaDiario.compartida == True, EntradaDiario.alerta_crisis == True,
            or_(EntradaDiario.usuario_id.in_(sub_asig), EntradaDiario.psicologo_id == psicologo.id)
        )
    )).scalar() or 0

    # SOS de estudiantes asignados (últimos 30 días)
    desde = datetime.now(timezone.utc) - timedelta(days=30)
    sos_reciente = 0
    if ids:
        sos_reciente = (await db.execute(
            select(func.count()).select_from(EventoSOS)
            .where(EventoSOS.usuario_id.in_(list(ids)), EventoSOS.creado_en >= desde)
        )).scalar() or 0

    return {
        "total_estudiantes_asignados": total_estudiantes,
        "citas_pendientes":            citas_pendientes,
        "diarios_compartidos":         diarios_comp,
        "alertas_crisis":              alertas,
        "sos_reciente_30d":            sos_reciente,
    }