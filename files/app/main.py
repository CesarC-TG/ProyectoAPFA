"""
ApoYo FES Acatlán — Backend Principal
FastAPI + SQLAlchemy + JWT + WebSockets
"""
from dotenv import load_dotenv
load_dotenv() # Esto inyecta tu llave de Anthropic a la matriz de entorno, asegurando que esté disponible para la aplicación sin exponerla en el código fuente.

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import uvicorn, logging, os

from app.config import settings
from app.database import engine, Base
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware, RequestLoggingMiddleware, CSRFMiddleware

from app.routers.auth      import router as auth_router
from app.routers.users     import router as users_router
from app.routers.recursos  import router as recursos_router
from app.routers.sos           import router as sos_router
from app.routers.notificaciones import router as notif_router
from app.routers.chatbot   import router as chatbot_router
from app.routers.admin     import router as admin_router
from app.routers.websocket  import router as websocket_router
from app.routers.psicologo  import router as psicologo_router
from app.routers.cola       import router as cola_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("apoyofes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Asegurar que la carpeta del proyecto esté en el path de trabajo
    import os
    os.chdir(Path(__file__).resolve().parent.parent)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Base de datos inicializada")
    from app.routers.recursos_seed import seed as seed_recursos
    await seed_recursos()
    logger.info("✅ Recursos inicializados")
    # ── Scheduler de tareas periódicas ────────────────────
    from app.database import get_db as _get_db
    from app.tasks.inactividad import verificar_usuarios_inactivos

    scheduler = AsyncIOScheduler()

    async def _tarea_inactividad():
        async for db in _get_db():
            try:
                n = await verificar_usuarios_inactivos(db)
                if n:
                    logger.info(f"📬 {n} notificaciones de inactividad generadas")
            except Exception as e:
                logger.error(f"Error en tarea de inactividad: {e}")

    scheduler.add_job(
        _tarea_inactividad,
        trigger=IntervalTrigger(hours=1),
        id="inactividad",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.start()
    logger.info("⏰ Scheduler iniciado — verificación de inactividad cada hora")

    yield

    scheduler.shutdown(wait=False)
    logger.info("🔴 Servidor apagado")


app = FastAPI(
    title       = "KAI Acatlán API",
    description = "API de bienestar emocional para estudiantes de FES Acatlán, UNAM",
    version     = settings.APP_VERSION,
    docs_url    = "/api/docs",
    redoc_url   = "/api/redoc",
    lifespan    = lifespan,
)
# ── CORS — solo orígenes conocidos ───────────────────────
# FIX: antes era allow_origins=["*"] (cualquier origen). Ahora usa la
# lista definida en settings.ALLOWED_ORIGINS para restringir el acceso.
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers     = ["Authorization", "Content-Type", "X-Requested-With"],
)

# ── CSRF — valida el origen de peticiones mutables ───────
app.add_middleware(CSRFMiddleware, allowed_origins=settings.ALLOWED_ORIGINS)

# ── Otros middlewares ─────────────────────────────────────
app.add_middleware(RateLimitMiddleware, calls=settings.RATE_LIMIT_PER_MINUTE)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1_000)

# ── Archivos estáticos ────────────────────────────────────
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ── Routers API ───────────────────────────────────────────
app.include_router(auth_router,      prefix="/api/auth",     tags=["Autenticación"])
app.include_router(users_router, prefix="/api/users", tags=["Usuarios"])
app.include_router(recursos_router,  prefix="/api/recursos", tags=["Recursos"])
app.include_router(sos_router,       prefix="/api/sos",      tags=["SOS"])
app.include_router(notif_router,      prefix="/api/notificaciones", tags=["Notificaciones"])
app.include_router(chatbot_router,   prefix="/api/chatbot",  tags=["Chatbot IA"])
app.include_router(admin_router,     prefix="/api/admin",    tags=["Administración"])
app.include_router(websocket_router,  prefix="/ws",            tags=["WebSockets"])
app.include_router(psicologo_router,  prefix="/api/psicologo", tags=["Psicólogo"])
app.include_router(cola_router,       prefix="/api/psicologo", tags=["Cola de atención"])

# ── Manejadores de error globales ────────────────────────
# FIX: evita que excepciones internas filtren stack traces o mensajes
# técnicos al cliente. Solo los HTTPException controlados pasan su
# 'detail'; cualquier otro error produce un mensaje genérico.

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Re-emite HTTPExceptions con el mismo status pero sin datos internos extras."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Errores de validación Pydantic: devuelve los campos con error sin exponer internos."""
    errores = [
        {"campo": " → ".join(str(loc) for loc in e["loc"]), "mensaje": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": "Datos inválidos.", "errores": errores},
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Captura cualquier excepción no controlada.
    - Loguea el error completo (con traceback) en el servidor.
    - Devuelve al cliente solo un mensaje genérico 500.
    Esto evita filtrar rutas internas, versiones de librerías o lógica de negocio.
    """
    logger.exception(
        "Error no controlado: %s %s — %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor. Por favor intenta más tarde."},
    )


# ── Health check ──────────────────────────────────────────
@app.get("/health", tags=["Sistema"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}

# ── Frontend — sirve los HTML del directorio static ──────
@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str = ""):
    from fastapi import HTTPException

    # Dejar pasar rutas de API/WS al manejador correcto
    if full_path.startswith(("api/", "ws/", "static/")):
        raise HTTPException(status_code=404)

    BASE_DIR = Path(__file__).resolve().parent / "static"

    # Si la ruta termina en .html, intentar servir ese archivo específico
    if full_path.endswith(".html"):
        target = BASE_DIR / full_path
        if target.is_file():
            return FileResponse(str(target))
        raise HTTPException(status_code=404)

    # Para rutas vacías o SPA (/, /perfil, etc.) servir index.html
    index = BASE_DIR / "index.html"
    if index.is_file():
        return FileResponse(str(index))

    raise HTTPException(status_code=404, detail=f"Frontend no encontrado en: {BASE_DIR}")

if __name__ == "__main__":
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    print("\n" + "=" * 52)
    print("  KAI — ApoYo FES Acatlan")
    print("=" * 52)
    print(f"  Local  -> http://localhost:8000")
    print(f"  Red    -> http://{local_ip}:8000")
    print(f"  Docs   -> http://localhost:8000/api/docs")
    print("  Ctrl+C para detener el servidor")
    print("=" * 52 + "\n")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="warning",
    )
