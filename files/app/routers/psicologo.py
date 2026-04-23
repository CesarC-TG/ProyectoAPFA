"""
Router del Psicólogo — panel, usuarios asignados, diario compartido, citas
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional

from app.database import get_db
from app.models import Usuario, EntradaDiario, Cita, RolUsuario, EstadoCita
from app.service.auth_service import get_current_psicologo

router = APIRouter()


@router.get("/perfil")
async def mi_perfil_psicologo(
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """Datos del psicólogo autenticado."""
    return {
        "id":         psicologo.id,
        "nombre":     psicologo.nombre,
        "apellidos":  psicologo.apellidos,
        "email":      psicologo.email,
        "carrera":    psicologo.carrera,
        "semestre":   psicologo.semestre,
        "avatar_url": psicologo.avatar_url,
        "rol":        psicologo.rol,
    }


@router.get("/mis-estudiantes")
async def listar_mis_estudiantes(
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """
    Lista estudiantes asignados a este psicólogo:
    - Tienen una cita (cualquier estado) con este psicólogo, O
    - Han compartido una entrada de diario específicamente con este psicólogo.
    """
    # IDs de estudiantes con cita con este psicólogo
    res_citas = await db.execute(
        select(Usuario)
        .join(Cita, Cita.estudiante_id == Usuario.id)
        .where(
            Cita.psicologo_id == psicologo.id,
            Usuario.activo == True,
        )
        .distinct()
    )
    mapa = {u.id: u for u in res_citas.scalars().all()}

    # IDs de estudiantes que asignaron entradas ESPECÍFICAMENTE a este psicólogo
    res_diario = await db.execute(
        select(Usuario)
        .join(EntradaDiario, EntradaDiario.usuario_id == Usuario.id)
        .where(
            EntradaDiario.compartida == True,
            EntradaDiario.psicologo_id == psicologo.id,
        )
        .distinct()
    )
    for u in res_diario.scalars().all():
        mapa[u.id] = u

    return [
        {
            "id":         u.id,
            "nombre":     u.nombre,
            "apellidos":  u.apellidos,
            "email":      u.email,
            "carrera":    u.carrera,
            "semestre":   u.semestre,
            "avatar_url": u.avatar_url,
        }
        for u in mapa.values()
    ]


@router.get("/diarios")
async def ver_diarios_compartidos(
    estudiante_id: Optional[str] = None,
    solo_crisis:   bool          = False,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """
    Entradas del diario que los estudiantes han compartido.
    Solo muestra entradas de estudiantes asignados a este psicólogo
    (con cita o con psicologo_id apuntando a este psicólogo).
    Si se pasa estudiante_id, filtra solo ese estudiante.
    """
    # Sub-query: IDs de estudiantes de este psicólogo
    sub_citas = select(Cita.estudiante_id).where(
        Cita.psicologo_id == psicologo.id
    )
    sub_diarios = select(EntradaDiario.usuario_id).where(
        EntradaDiario.psicologo_id == psicologo.id,
        EntradaDiario.compartida == True,
    )

    filtros = [
        EntradaDiario.compartida == True,
        or_(
            EntradaDiario.usuario_id.in_(sub_citas),
            EntradaDiario.usuario_id.in_(sub_diarios),
        )
    ]

    if estudiante_id:
        filtros.append(EntradaDiario.usuario_id == estudiante_id)
    if solo_crisis:
        filtros.append(EntradaDiario.alerta_crisis == True)

    result = await db.execute(
        select(EntradaDiario, Usuario)
        .join(Usuario, EntradaDiario.usuario_id == Usuario.id)
        .where(and_(*filtros))
        .order_by(EntradaDiario.creada_en.desc())
        .limit(200)
    )

    return [
        {
            "id":            e.id,
            "texto":         e.texto,
            "estado_animo":  e.estado_animo,
            "etiquetas":     e.etiquetas,
            "alerta_crisis": e.alerta_crisis,
            "creada_en":     e.creada_en.isoformat(),
            "estudiante": {
                "id":      u.id,
                "nombre":  u.nombre,
                "email":   u.email,
                "carrera": u.carrera,
            },
        }
        for e, u in result.all()
    ]


@router.get("/citas")
async def mis_citas(
    estado: Optional[EstadoCita] = None,
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """Citas de este psicólogo con sus estudiantes."""
    filtros = [Cita.psicologo_id == psicologo.id]
    if estado:
        filtros.append(Cita.estado == estado)

    result = await db.execute(
        select(Cita, Usuario)
        .join(Usuario, Cita.estudiante_id == Usuario.id)
        .where(and_(*filtros))
        .order_by(Cita.fecha_hora.asc())
        .limit(100)
    )
    return [
        {
            "id":           c.id,
            "fecha_hora":   c.fecha_hora.isoformat(),
            "modalidad":    c.modalidad,
            "estado":       c.estado,
            "motivo":       c.motivo,
            "estudiante": {
                "id":     u.id,
                "nombre": u.nombre,
                "email":  u.email,
            },
        }
        for c, u in result.all()
    ]


@router.get("/stats")
async def stats_psicologo(
    db: AsyncSession = Depends(get_db),
    psicologo: Usuario = Depends(get_current_psicologo),
):
    """Estadísticas propias del psicólogo."""
    # Estudiantes únicos (por citas O por diario compartido)
    res_citas_ids = await db.execute(
        select(Cita.estudiante_id.distinct())
        .where(Cita.psicologo_id == psicologo.id)
    )
    est_ids_cita = set(res_citas_ids.scalars().all())

    res_diario_ids = await db.execute(
        select(EntradaDiario.usuario_id.distinct())
        .where(
            EntradaDiario.psicologo_id == psicologo.id,
            EntradaDiario.compartida == True,
        )
    )
    est_ids_diario = set(res_diario_ids.scalars().all())
    total_estudiantes = len(est_ids_cita | est_ids_diario)

    citas_pendientes = (await db.execute(
        select(func.count()).select_from(Cita)
        .where(
            Cita.psicologo_id == psicologo.id,
            Cita.estado == EstadoCita.PENDIENTE,
        )
    )).scalar() or 0

    diarios_compartidos = (await db.execute(
        select(func.count()).select_from(EntradaDiario)
        .where(
            EntradaDiario.compartida == True,
            or_(
                EntradaDiario.usuario_id.in_(
                    select(Cita.estudiante_id).where(Cita.psicologo_id == psicologo.id)
                ),
                EntradaDiario.psicologo_id == psicologo.id,
            )
        )
    )).scalar() or 0

    alertas_crisis = (await db.execute(
        select(func.count()).select_from(EntradaDiario)
        .where(
            EntradaDiario.compartida == True,
            EntradaDiario.alerta_crisis == True,
            or_(
                EntradaDiario.usuario_id.in_(
                    select(Cita.estudiante_id).where(Cita.psicologo_id == psicologo.id)
                ),
                EntradaDiario.psicologo_id == psicologo.id,
            )
        )
    )).scalar() or 0

    return {
        "total_estudiantes_asignados": total_estudiantes,
        "citas_pendientes":            citas_pendientes,
        "diarios_compartidos":         diarios_compartidos,
        "alertas_crisis":              alertas_crisis,
    }