"""
Schemas Pydantic — Validación de entrada y salida
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.models import RolUsuario, EstadoAnimo, TipoRecurso, EstadoCita


# ── Usuario ───────────────────────────────────────────────

class UsuarioBase(BaseModel):
    nombre:        str      = Field(..., min_length=2, max_length=120)
    apellidos:     Optional[str] = None
    email:         EmailStr
    numero_cuenta: Optional[str] = None
    carrera:       Optional[str] = None
    semestre:      Optional[int] = Field(None, ge=1, le=12)
    telefono:      Optional[str]  = None

    # Contacto de emergencia
    emergencia_nombre:   Optional[str]     = Field(None, max_length=120)
    emergencia_telefono: Optional[str]     = Field(None, max_length=20)
    emergencia_email:    Optional[EmailStr] = None

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, v: str) -> str:
        return v.strip().lower()


class UsuarioCrear(UsuarioBase):
    password:     Optional[str] = Field(None, min_length=8)
    google_token: Optional[str] = None


class UsuarioRespuesta(UsuarioBase):
    id:               str
    rol:              RolUsuario
    activo:           bool
    avatar_url:       Optional[str]
    email_verificado: bool
    creado_en:        datetime
    ultimo_acceso:    Optional[datetime]

    class Config:
        from_attributes = True


class UsuarioActualizar(BaseModel):
    nombre:     Optional[str] = Field(None, min_length=2, max_length=120)
    apellidos:  Optional[str] = None
    carrera:    Optional[str] = None
    semestre:   Optional[int] = Field(None, ge=1, le=12)
    avatar_url: Optional[str] = None
    telefono:   Optional[str] = None
    # Contacto de emergencia
    emergencia_nombre:   Optional[str]     = Field(None, max_length=120)
    emergencia_telefono: Optional[str]     = Field(None, max_length=20)
    emergencia_email:    Optional[EmailStr] = None


# ── Autenticación ─────────────────────────────────────────

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, v: str) -> str:
        return v.strip().lower()


class GoogleAuthRequest(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int
    usuario:       UsuarioRespuesta


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ── Diario ────────────────────────────────────────────────

class EntradaDiarioCrear(BaseModel):
    texto:        str   = Field(..., min_length=1, max_length=10_000)
    estado_animo: Optional[EstadoAnimo] = None
    etiquetas:    List[str] = []
    compartida:   bool = False

    @field_validator("etiquetas")
    @classmethod
    def limpiar_etiquetas(cls, v: List[str]) -> List[str]:
        return [t.strip().lower() for t in v if t.strip()][:20]


class EntradaDiarioActualizar(BaseModel):
    texto:        Optional[str]            = None
    estado_animo: Optional[EstadoAnimo]    = None
    etiquetas:    Optional[List[str]]      = None
    compartida:   Optional[bool]           = None


class EntradaDiarioRespuesta(BaseModel):
    id:           str
    texto:        str
    estado_animo: Optional[str]
    etiquetas:    List[str]
    compartida:   bool
    alerta_crisis: bool
    analisis_ia:  Optional[Dict[str, Any]]
    creada_en:    datetime
    actualizada_en: Optional[datetime]

    class Config:
        from_attributes = True


class EntradaDiarioListaRespuesta(BaseModel):
    entradas:   List[EntradaDiarioRespuesta]
    total:      int
    pagina:     int
    por_pagina: int


# ── Recursos ──────────────────────────────────────────────

class RecursoRespuesta(BaseModel):
    id:               str
    titulo:           str
    descripcion:      Optional[str]
    tipo:             str
    contenido:        Optional[Dict[str, Any]]
    duracion_minutos: Optional[int]
    imagen_url:       Optional[str]
    url_externo:      Optional[str]
    telefono:         Optional[str]
    direccion:        Optional[str]
    horario:          Optional[str]
    disponible_24h:   bool
    vistas:           int = 0

    class Config:
        from_attributes = True


class RecursoCrear(BaseModel):
    titulo:           str = Field(..., min_length=3, max_length=200)
    descripcion:      Optional[str] = None
    tipo:             TipoRecurso
    contenido:        Optional[Dict[str, Any]] = None
    duracion_minutos: Optional[int]            = None
    telefono:         Optional[str]            = None
    direccion:        Optional[str]            = None
    horario:          Optional[str]            = None
    disponible_24h:   bool = False


# ── SOS ──────────────────────────────────────────────────

class EventoSOSCrear(BaseModel):
    tipo_accion: str        = Field(..., pattern="^(llamada|sms|ubicacion|chatbot|fes)$")
    descripcion: Optional[str] = None
    latitud:     Optional[float] = None
    longitud:    Optional[float] = None


class EventoSOSRespuesta(BaseModel):
    id:          str
    tipo_accion: str
    descripcion: Optional[str]
    latitud:     Optional[float]
    longitud:    Optional[float]
    atendido:    bool
    creado_en:   datetime

    class Config:
        from_attributes = True


# ── Chatbot ───────────────────────────────────────────────

class MensajeChatEnviar(BaseModel):
    contenido: str      = Field(..., min_length=1, max_length=2_000)
    sesion_id: Optional[str] = None


class MensajeChatRespuesta(BaseModel):
    id:        str
    sesion_id: str
    rol:       str
    contenido: str
    creado_en: datetime

    class Config:
        from_attributes = True


class HistorialChatRespuesta(BaseModel):
    sesion_id: str
    mensajes:  List[MensajeChatRespuesta]


# ── Citas ─────────────────────────────────────────────────

class CitaCrear(BaseModel):
    # BUG FIX: el schema original solo tenía psicologo_id y lo usaba
    # como estudiante_id en admin.py — ahora cada campo tiene su semántica correcta.
    psicologo_id:   str
    estudiante_id:  Optional[str] = None   # usado por psicólogos al crear citas
    fecha_hora:     datetime
    modalidad:      str = Field(default="presencial", pattern="^(presencial|videollamada)$")
    motivo:         Optional[str] = Field(None, max_length=500)


class CitaRespuesta(BaseModel):
    id:                str
    estudiante_id:     str
    psicologo_id:      str
    fecha_hora:        datetime
    duracion_minutos:  int
    modalidad:         str
    estado:            str
    motivo:            Optional[str]
    link_videollamada: Optional[str]
    creada_en:         datetime

    class Config:
        from_attributes = True


# ── Notificaciones ────────────────────────────────────────

class NotificacionRespuesta(BaseModel):
    id:         str
    titulo:     str
    mensaje:    str
    tipo:       str
    leida:      bool
    url_accion: Optional[str]
    creada_en:  datetime

    class Config:
        from_attributes = True


# ── Genéricos ─────────────────────────────────────────────

class MensajeRespuesta(BaseModel):
    mensaje: str
    exito:   bool = True


class PaginacionParams(BaseModel):
    pagina:     int = Field(default=1,  ge=1)
    por_pagina: int = Field(default=20, ge=1, le=100)

# ── Recuperación de contraseña ────────────────────────────

class LoginTelefonoRequest(BaseModel):
    telefono: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=1)

class PasswordResetRequest(BaseModel):
    """Acepta { email } O { telefono } — al menos uno es requerido."""
    email:    Optional[str] = None
    telefono: Optional[str] = Field(None, min_length=10, max_length=15)

    @field_validator('email', mode='before')
    @classmethod
    def normalizar_email_reset(cls, v):
        return v.strip().lower() if v else v

    def model_post_init(self, __context):
        if not self.email and not self.telefono:
            raise ValueError('Debes proporcionar email o teléfono')

# ── Asignación psicólogo ──────────────────────────────────

class AsignacionCrear(BaseModel):
    psicologo_id:  str
    estudiante_id: str
    notas:         Optional[str] = None

class AsignacionRespuesta(BaseModel):
    id:            str
    psicologo_id:  str
    estudiante_id: str
    activa:        bool
    notas:         Optional[str]
    creada_en:     datetime

    class Config:
        from_attributes = True

# Alias para compatibilidad
PasswordResetEmailRequest = PasswordResetRequest

class SolicitarVerificacionRequest(BaseModel):
    email: str
    nombre: str

class VerificarCodigoRequest(BaseModel):
    email: str
    codigo: str
 
