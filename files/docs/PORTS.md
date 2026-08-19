# PORTS — APFA / KAI

Puertos asignados al proyecto. **Actualiza este archivo antes de desplegar** si el backend
comparte servidor con otros proyectos, para no repetir incidentes de conflicto de puertos.

## Servicios

| Puerto | Servicio | Bind | Notas |
|---|---|---|---|
| `8000` | API FastAPI (uvicorn) | `0.0.0.0` | Frontend servido estáticamente en `/` |
| `5432` | PostgreSQL 16 | `127.0.0.1` | solo localhost, **nunca** expuesto a internet |
| `6379` | Redis (cache + rate-limiting) | `127.0.0.1` | solo localhost |

## Referencias de conexión

- Base de datos local: `postgresql+asyncpg://apoyofes:devpassword@localhost:5432/apoyofes_db`
- Redis: `redis://localhost:6379/0`
- Docs API: `http://localhost:8000/api/docs`

## Reglas

1. Los servicios de datos (Postgres, Redis) **nunca** exponen puerto a internet; bind a `127.0.0.1`.
2. Si se cambia el puerto del API, actualizar aquí **y** en `config.py` / `docker-compose.yml`.
3. Si este backend comparte máquina con otro proyecto del equipo, registrar el puerto en el
   `PORTS.md` compartido del equipo (convención heredada de `admin-panel-j2ec`).
