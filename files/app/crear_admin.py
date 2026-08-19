"""
Script standalone — crea (o fuerza) el usuario administrador en PostgreSQL.
Uso:  python -m app.crear_admin
"""
import asyncio
import uuid

from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.service.auth_service import hashear_password

EMAIL    = "admin@pcpuma.acatlan.unam.mx"
PASSWORD = "Admin12345!"


async def forzar_creacion_admin() -> None:
    hashed = hashear_password(PASSWORD)
    user_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text(
                    """
                    INSERT INTO usuarios (id, nombre, apellidos, email, password_hash, rol, activo, email_verificado)
                    VALUES (:id, :nom, :ape, :email, :hash, :rol, :act, :ver)
                    ON CONFLICT (email) DO NOTHING
                    """
                ),
                {
                    "id": user_id,
                    "nom": "Admin",
                    "ape": "Acatlán",
                    "email": EMAIL,
                    "hash": hashed,
                    "rol": "admin",
                    "act": True,
                    "ver": True,
                },
            )
            await session.commit()
            print(f"✅ Admin listo: {EMAIL}")
        except Exception as e:
            print(f"❌ ERROR: {e}")
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(forzar_creacion_admin())
