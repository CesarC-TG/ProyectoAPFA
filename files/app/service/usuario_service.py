"""
Servicio de Usuario — lógica de negocio aislada del router.
Los routers solo llaman funciones de aquí; no tocan la DB directamente.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from fastapi import HTTPException

from app.models import Usuario, RolUsuario
from app.schemas import UsuarioActualizar, UsuarioCrear
from app.service.auth_service import hashear_password


# ── Lookup ────────────────────────────────────────────────

async def obtener_por_id(db: AsyncSession, usuario_id: str) -> Usuario:
    u = await db.get(Usuario, usuario_id)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    return u


async def obtener_por_email(db: AsyncSession, email: str) -> Optional[Usuario]:
    r = await db.execute(select(Usuario).where(Usuario.email == email.strip().lower()))
    return r.scalar_one_or_none()


async def obtener_por_telefono(db: AsyncSession, telefono: str) -> Optional[Usuario]:
    tel = telefono.strip().replace(" ", "").replace("-", "")
    r = await db.execute(select(Usuario).where(Usuario.telefono == tel))
    return r.scalar_one_or_none()


# ── Escritura ─────────────────────────────────────────────

async def actualizar_campos(
    db: AsyncSession,
    usuario: Usuario,
    datos: UsuarioActualizar,
) -> Usuario:
    """Aplica solo los campos no-None del schema de actualización."""
    for campo, valor in datos.model_dump(exclude_none=True).items():
        setattr(usuario, campo, valor)
    await db.commit()
    await db.refresh(usuario)
    return usuario


async def cambiar_password(db: AsyncSession, usuario: Usuario, nueva: str) -> None:
    if len(nueva) < 8:
        raise HTTPException(400, "La contraseña debe tener al menos 8 caracteres")
    usuario.password_hash     = hashear_password(nueva)
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta   = None
    await db.commit()


async def cambiar_rol(
    db: AsyncSession,
    admin: Usuario,
    usuario: Usuario,
    nuevo_rol: RolUsuario,
) -> None:
    if usuario.id == admin.id:
        raise HTTPException(400, "No puedes cambiar tu propio rol")
    usuario.rol = nuevo_rol
    await db.commit()


async def activar_desactivar(
    db: AsyncSession,
    admin: Usuario,
    usuario: Usuario,
    activo: bool,
) -> None:
    if usuario.id == admin.id:
        raise HTTPException(400, "No puedes desactivarte a ti mismo")
    usuario.activo = activo
    await db.commit()


async def eliminar(
    db: AsyncSession,
    admin: Usuario,
    usuario: Usuario,
    permanente: bool = False,
) -> str:
    if usuario.id == admin.id:
        raise HTTPException(400, "No puedes eliminarte a ti mismo")
    if permanente:
        await db.delete(usuario)
        await db.commit()
        return "Usuario eliminado permanentemente"
    usuario.activo = False
    await db.commit()
    return "Usuario desactivado correctamente"


# ── Consultas para admin ──────────────────────────────────

async def listar(
    db: AsyncSession,
    *,
    rol: Optional[str] = None,
    activo: Optional[bool] = None,
    buscar: Optional[str] = None,
    pagina: int = 1,
    por_pagina: int = 50,
) -> List[Dict[str, Any]]:
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
    q = (
        select(Usuario)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
        .order_by(Usuario.creado_en.desc())
    )
    if filtros:
        q = q.where(and_(*filtros))
    result = await db.execute(q)
    return [_to_dict(u) for u in result.scalars().all()]


def _to_dict(u: Usuario) -> Dict[str, Any]:
    return {
        "id":            u.id,
        "nombre":        u.nombre,
        "apellidos":     u.apellidos,
        "email":         u.email,
        "telefono":      u.telefono,
        "carrera":       u.carrera,
        "semestre":      u.semestre,
        "rol":           u.rol,
        "activo":        u.activo,
        "creado_en":     u.creado_en.isoformat() if u.creado_en else None,
        "ultimo_acceso": u.ultimo_acceso.isoformat() if u.ultimo_acceso else None,
    }
