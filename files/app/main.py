"""
ApoYo FES Acatlán — Backend Principal
FastAPI + SQLAlchemy + JWT + WebSockets
"""
from dotenv import load_dotenv
load_dotenv() # Esto inyecta tu llave de Anthropic a la matriz de entorno, asegurando que esté disponible para la aplicación sin exponerla en el código fuente.

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import uvicorn, logging, os

from app.config import settings
from app.database import engine, Base

from app.routers.auth      import router as auth_router
from app.routers.users     import router as users_router
from app.routers.diario    import router as diario_router
from app.routers.recursos  import router as recursos_router
from app.routers.sos       import router as sos_router
from app.routers.chatbot   import router as chatbot_router
from app.routers.admin     import router as admin_router
from app.routers.websocket  import router as websocket_router
from app.routers.psicologo  import router as psicologo_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("apoyofes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Base de datos inicializada")
    yield
    logger.info("🔴 Servidor apagado")


app = FastAPI(
    title       = "KAI Acatlán API",
    description = "API de bienestar emocional para estudiantes de FES Acatlán, UNAM",
    version     = settings.APP_VERSION,
    docs_url    = "/api/docs",
    redoc_url   = "/api/redoc",
    lifespan    = lifespan,
)
# ── CORS — permite cualquier origen en desarrollo ─────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = False,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1_000)

# ── Archivos estáticos ────────────────────────────────────
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ── Routers API ───────────────────────────────────────────
app.include_router(auth_router,      prefix="/api/auth",     tags=["Autenticación"])
app.include_router(users_router, prefix="/api/users", tags=["Usuarios"])
app.include_router(diario_router,    prefix="/api/diario",   tags=["Diario"])
app.include_router(recursos_router,  prefix="/api/recursos", tags=["Recursos"])
app.include_router(sos_router,       prefix="/api/sos",      tags=["SOS"])
app.include_router(chatbot_router,   prefix="/api/chatbot",  tags=["Chatbot IA"])
app.include_router(admin_router,     prefix="/api/admin",    tags=["Administración"])
app.include_router(websocket_router,  prefix="/ws",            tags=["WebSockets"])
app.include_router(psicologo_router,  prefix="/api/psicologo", tags=["Psicólogo"])

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
    # Obtener IP local automáticamente para mostrarla al arrancar
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "tu-ip-local"

    print("\n" + "═" * 52)
    print("  🐱 KAI — ApoYo FES Acatlán")
    print("═" * 52)
    print(f"  Local  → http://localhost:8000")
    print(f"  Red    → http://{local_ip}:8000")
    print(f"  Docs   → http://localhost:8000/api/docs")
    print("  (Comparte la URL de Red con otros dispositivos)")
    print("═" * 52 + "\n")

    uvicorn.run(
        "app.main:app",
        host      = "0.0.0.0",   # escucha en TODAS las interfaces (LAN incluida)
        port      = 8000,
        reload    = settings.DEBUG,
        log_level = "warning",
    )