import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from passlib.context import CryptContext

# Configuración directa para evitar importaciones conflictivas
DATABASE_URL = "sqlite+aiosqlite:///./apoyofes.db"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def forzar_creacion_admin():
    email = "admin@pcpuma.acatlan.unam.mx"
    password = "Admin12345!"
    
    # Generar hash manualmente
    hashed_password = pwd_context.hash(password)
    user_id = str(uuid.uuid4())

    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"--- Forzando entrada de: {email} ---")
    
    async with async_session() as session:
        try:
            # SQL puro: la vieja confiable que no falla con metadatos
            sql = text("""
                INSERT INTO usuarios (id, nombre, apellidos, email, password_hash, rol, activo, email_verificado)
                VALUES (:id, :nom, :ape, :email, :hash, :rol, :act, :ver)
            """)
            
            await session.execute(sql, {
                "id": user_id,
                "nom": "Admin",
                "ape": "Acatlán",
                "email": email,
                "hash": hashed_password,
                "rol": "ADMIN",
                "act": 1,      # En SQLite True es 1
                "ver": 1
            })
            await session.commit()
            print(f"✅ ¡POR FIN! Admin creado exitosamente.")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            if "UNIQUE constraint failed" in str(e):
                print("⚠️ Nota: El usuario ya existe. Intenta loguearte.")
            await session.rollback()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(forzar_creacion_admin())