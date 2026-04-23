# ── Etapa 1: dependencias ────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Instalar dependencias del sistema para asyncpg y bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Etapa 2: imagen de producción ────────────────────────
FROM python:3.12-slim AS production

# Usuario no-root para seguridad
RUN useradd --create-home --shell /bin/bash apoyofes
WORKDIR /app

# Copiar dependencias instaladas
COPY --from=builder /install /usr/local

# Copiar código de la aplicación
COPY --chown=apoyofes:apoyofes . .

# Crear directorio de uploads con permisos correctos
RUN mkdir -p uploads && chown apoyofes:apoyofes uploads

USER apoyofes

# Variables de entorno base (se sobreescriben en docker-compose o el orquestador)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    PORT=8000

EXPOSE 8000

# Health check para orquestadores (Kubernetes, ECS, etc.)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Gunicorn + Uvicorn workers para producción
# Ajusta --workers según los núcleos disponibles: (2 * CPU) + 1
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--no-access-log"]
