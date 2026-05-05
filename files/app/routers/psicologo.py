"""
Router del Psicólogo — panel, estudiantes, diarios, citas, actividad, stats SOS
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models import Usuario, EntradaDiario, Cita, RolUsuario, EstadoCita, EventoSOS, AsignacionPsicologo, EventoPsicologo
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
            "categoria_problema": u.categoria_problema,
        })
    return out


@router.get("/todos-estudiantes")
async def todos_los_estudiantes(
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """Devuelve TODOS los estudiantes activos del sistema para visibilidad del psicólogo."""
    result = await db.execute(
        select(Usuario).where(
            Usuario.rol == RolUsuario.ESTUDIANTE,
            Usuario.activo == True,
        ).order_by(Usuario.nombre)
    )
    ahora = datetime.now(timezone.utc)
    out = []
    for u in result.scalars().all():
        if u.ultimo_acceso:
            ua = u.ultimo_acceso if u.ultimo_acceso.tzinfo else u.ultimo_acceso.replace(tzinfo=timezone.utc)
            dias_sin = (ahora - ua).days
        else:
            dias_sin = None
        out.append({
            "id": u.id, "nombre": u.nombre, "apellidos": u.apellidos,
            "email": u.email, "carrera": u.carrera, "semestre": u.semestre,
            "avatar_url": u.avatar_url,
            "ultimo_acceso": u.ultimo_acceso.isoformat() if u.ultimo_acceso else None,
            "dias_sin_entrar": dias_sin,
            "categoria_problema": u.categoria_problema,
        })
    return out


@router.patch("/estudiantes/{estudiante_id}/categoria")
async def asignar_categoria(
    estudiante_id: str,
    datos: dict,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """El psicólogo asigna o actualiza la categoría de problemática de un estudiante."""
    estudiante = await db.get(Usuario, estudiante_id)
    if not estudiante or not estudiante.activo:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    categorias_validas = {"ansiedad","depresion","estres","adicciones","crisis","duelo","otro",""}
    cat = (datos.get("categoria") or "").lower().strip()
    if cat not in categorias_validas:
        raise HTTPException(status_code=400, detail=f"Categoría inválida: '{cat}'")

    estudiante.categoria_problema = cat or None
    await db.commit()
    return {"mensaje": "Categoría actualizada", "categoria": estudiante.categoria_problema}


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
            "notas_psicologo": c.notas_psicologo,
            "link_videollamada": c.link_videollamada,
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
    background_tasks: BackgroundTasks,
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
    estudiante = await db.get(Usuario, estudiante_id)
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    db.add(cita)
    await db.commit()
    await db.refresh(cita)

    from app.service.notificacion_service import enviar_email_cita
    background_tasks.add_task(
        enviar_email_cita,
        estudiante_email  = estudiante.email,
        estudiante_nombre = estudiante.nombre,
        psicologo_email   = psicologo.email,
        psicologo_nombre  = psicologo.nombre + (f" {psicologo.apellidos}" if psicologo.apellidos else ""),
        fecha_hora        = cita.fecha_hora,
        duracion_min      = cita.duracion_minutos,
        modalidad         = cita.modalidad,
        motivo            = cita.motivo or "",
        tipo              = "nueva",
    )

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
    background_tasks: BackgroundTasks,
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

    if cita.estado == EstadoCita.CONFIRMADA:
        estudiante = await db.get(Usuario, cita.estudiante_id)
        if estudiante:
            from app.service.notificacion_service import enviar_email_cita
            background_tasks.add_task(
                enviar_email_cita,
                estudiante_email  = estudiante.email,
                estudiante_nombre = estudiante.nombre,
                psicologo_email   = psicologo.email,
                psicologo_nombre  = psicologo.nombre + (f" {psicologo.apellidos}" if psicologo.apellidos else ""),
                fecha_hora        = cita.fecha_hora,
                duracion_min      = cita.duracion_minutos,
                modalidad         = cita.modalidad,
                motivo            = cita.motivo or "",
                tipo              = "confirmada",
            )

    return {"mensaje": f"Cita actualizada a '{estado}'"}


@router.patch("/citas/{cita_id}/notas")
async def guardar_notas_cita(
    cita_id: str,
    datos: dict,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """El psicólogo guarda o actualiza sus observaciones privadas sobre una cita."""
    result = await db.execute(
        select(Cita).where(Cita.id == cita_id, Cita.psicologo_id == psicologo.id)
    )
    cita = result.scalar_one_or_none()
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada o no autorizada")

    cita.notas_psicologo = datos.get("notas", "").strip() or None
    await db.commit()
    return {"mensaje": "Observaciones guardadas"}


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


# ── Eventos del Psicólogo ─────────────────────────────────

def _evento_dict(e: EventoPsicologo) -> dict:
    return {
        "id":          e.id,
        "titulo":      e.titulo,
        "tipo":        e.tipo,
        "descripcion": e.descripcion,
        "fecha_hora":  e.fecha_hora.isoformat() if e.fecha_hora else None,
        "modalidad":   e.modalidad,
        "lugar":       e.lugar,
        "link_evento": e.link_evento,
        "capacidad":   e.capacidad,
        "activo":      e.activo,
        "creado_en":   e.creado_en.isoformat() if e.creado_en else None,
    }


@router.get("/eventos")
async def listar_eventos(
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    result = await db.execute(
        select(EventoPsicologo)
        .where(EventoPsicologo.psicologo_id == psicologo.id)
        .order_by(EventoPsicologo.fecha_hora.asc())
    )
    return [_evento_dict(e) for e in result.scalars().all()]


@router.post("/eventos", status_code=201)
async def crear_evento(
    datos: dict,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    titulo = (datos.get("titulo") or "").strip()
    if not titulo:
        raise HTTPException(400, "El título es requerido")
    fecha_str = datos.get("fecha_hora") or ""
    if not fecha_str:
        raise HTTPException(400, "La fecha y hora son requeridas")
    try:
        from datetime import datetime as dt
        fecha = dt.fromisoformat(fecha_str.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(400, "Formato de fecha inválido (ISO 8601)")

    evento = EventoPsicologo(
        psicologo_id = psicologo.id,
        titulo       = titulo,
        tipo         = (datos.get("tipo") or "platica").lower(),
        descripcion  = datos.get("descripcion") or None,
        fecha_hora   = fecha,
        modalidad    = (datos.get("modalidad") or "presencial").lower(),
        lugar        = datos.get("lugar") or None,
        link_evento  = datos.get("link_evento") or None,
        capacidad    = int(datos["capacidad"]) if datos.get("capacidad") else None,
        activo       = True,
    )
    db.add(evento)
    await db.commit()
    await db.refresh(evento)
    return _evento_dict(evento)


@router.put("/eventos/{evento_id}")
async def actualizar_evento(
    evento_id: str,
    datos: dict,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    result = await db.execute(
        select(EventoPsicologo)
        .where(EventoPsicologo.id == evento_id, EventoPsicologo.psicologo_id == psicologo.id)
    )
    evento = result.scalar_one_or_none()
    if not evento:
        raise HTTPException(404, "Evento no encontrado o no autorizado")

    if datos.get("titulo"):
        evento.titulo = datos["titulo"].strip()
    if "tipo" in datos:
        evento.tipo = datos["tipo"] or "platica"
    if "descripcion" in datos:
        evento.descripcion = datos["descripcion"] or None
    if datos.get("fecha_hora"):
        from datetime import datetime as dt
        evento.fecha_hora = dt.fromisoformat(datos["fecha_hora"].replace("Z", "+00:00"))
    if "modalidad" in datos:
        evento.modalidad = datos["modalidad"] or "presencial"
    if "lugar" in datos:
        evento.lugar = datos["lugar"] or None
    if "link_evento" in datos:
        evento.link_evento = datos["link_evento"] or None
    if "capacidad" in datos:
        evento.capacidad = int(datos["capacidad"]) if datos["capacidad"] else None
    if "activo" in datos:
        evento.activo = bool(datos["activo"])

    await db.commit()
    await db.refresh(evento)
    return _evento_dict(evento)


@router.delete("/eventos/{evento_id}", status_code=204)
async def eliminar_evento(
    evento_id: str,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    result = await db.execute(
        select(EventoPsicologo)
        .where(EventoPsicologo.id == evento_id, EventoPsicologo.psicologo_id == psicologo.id)
    )
    evento = result.scalar_one_or_none()
    if not evento:
        raise HTTPException(404, "Evento no encontrado")
    await db.delete(evento)
    await db.commit()