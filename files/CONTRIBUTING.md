# CONTRIBUTING — APFA / KAI

Reglas de trabajo en equipo para este backend. **No negociables.**

## 1. Flujo de trabajo

- **Nunca** se edita código directo en producción.
- Todo cambio: `commit local → push → git pull` en el servidor de despliegue.
- Migraciones de BD **siempre vía Alembic** (`alembic revision` → `alembic upgrade head`).
- Nada se mergea sin pasar por los tests / verificación correspondiente.

## 2. Convenciones de código

- **JSON de la API en `camelCase`** (convención heredada, ver DECISION_LOG #8).
- **Código Python interno en `snake_case`**.
- Validación con **Pydantic v2**; los schemas heredan de `CamelModel` (pendiente de migrar).
- **Ningún campo calculado server-side** se acepta en el body de un request.
- SQLAlchemy 2.0 en modo **async** (`async def`, `AsyncSession`).

## 3. Seguridad

- **El JWT solo lleva el ID del usuario**, nunca rol/permisos; el rol se resuelve consultando la BD en cada request.
  > ⚠️ Pendiente: `crear_access_token` aún incluye `rol` en el payload (corregir en fase F).
- **Nunca** confiar en rol/tenant que venga del cliente.
- **Credenciales/secretos propios y nuevos** para este servicio; nunca reutilizar los de otro entorno.
- `.env` **nunca** se commitea (solo `.env.example`).
- Postgres y Redis **nunca** exponen puerto a internet (ver `docs/PORTS.md`).
- Acceso a expedientes de estudiantes queda **auditado** (`auditoria_acceso`).

## 4. Base de datos

- PostgreSQL 16 + asyncpg. **Sin SQLite** (ver DECISION_LOG #7).
- Desarrollo local: `docker compose up -d` (Postgres + Redis).
- Migraciones: `docker compose --profile migrate up migrate` o `alembic upgrade head`.

## 5. Documentación

- Decisiones de diseño → `docs/DECISION_LOG.md`.
- Esquema de BD → `docs/SCHEMA_PROPUESTO.md`.
- Contrato de API → `docs/API_PROPUESTA.md`.
- Puertos → `docs/PORTS.md` (actualizar antes de desplegar).
