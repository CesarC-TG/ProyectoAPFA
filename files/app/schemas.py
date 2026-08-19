"""
Schemas Pydantic — Validación de entrada y salida
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.models import RolUsuario, TipoRecurso, EstadoCita, EstadoCola, PrioridadCola


# ── Base con convención camelCase ─────────────────────────
# Todo el JSON de la API sale en camelCase (numeroCuenta, enCrisis, …).
# populate_by_name=True permite aceptar snake_case Y camelCase en la entrada
# durante la transición, para no romper el frontend de golpe.


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ── Usuario ───────────────────────────────────────────────

class UsuarioBase(CamelModel):
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
    en_crisis:        bool = False
    creado_en:        datetime
    ultimo_acceso:    Optional[datetime]

    

class UsuarioActualizar(CamelModel):
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

class LoginRequest(CamelModel):
    email:    EmailStr
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, v: str) -> str:
        return v.strip().lower()


class GoogleAuthRequest(CamelModel):
    token: str


class TokenResponse(CamelModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int
    usuario:       UsuarioRespuesta


class RefreshTokenRequest(CamelModel):
    refresh_token: str


# ── Recursos ──────────────────────────────────────────────

class RecursoRespuesta(CamelModel):
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

    

class RecursoCrear(CamelModel):
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

class EventoSOSCrear(CamelModel):
    tipo_accion: str        = Field(..., pattern="^(llamada|sms|ubicacion|chatbot|fes)$")
    descripcion: Optional[str] = None
    latitud:     Optional[float] = None
    longitud:    Optional[float] = None


class EventoSOSRespuesta(CamelModel):
    id:          str
    tipo_accion: str
    descripcion: Optional[str]
    latitud:     Optional[float]
    longitud:    Optional[float]
    atendido:    bool
    creado_en:   datetime

    

# ── Chatbot ───────────────────────────────────────────────

class MensajeChatEnviar(CamelModel):
    contenido: str      = Field(..., min_length=1, max_length=2_000)
    sesion_id: Optional[str] = None


class MensajeChatRespuesta(CamelModel):
    id:        str
    sesion_id: str
    rol:       str
    contenido: str
    creado_en: datetime

    

class HistorialChatRespuesta(CamelModel):
    sesion_id: str
    mensajes:  List[MensajeChatRespuesta]


# ── Citas ─────────────────────────────────────────────────

class CitaCrear(CamelModel):
    # BUG FIX: el schema original solo tenía psicologo_id y lo usaba
    # como estudiante_id en admin.py — ahora cada campo tiene su semántica correcta.
    psicologo_id:   str
    estudiante_id:  Optional[str] = None   # usado por psicólogos al crear citas
    fecha_hora:     datetime
    modalidad:      str = Field(default="presencial", pattern="^(presencial|videollamada)$")
    motivo:         Optional[str] = Field(None, max_length=500)


class CitaRespuesta(CamelModel):
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

    

# ── Notificaciones ────────────────────────────────────────

class NotificacionRespuesta(CamelModel):
    id:         str
    titulo:     str
    mensaje:    str
    tipo:       str
    leida:      bool
    url_accion: Optional[str]
    creada_en:  datetime

    

# ── Eventos del Psicólogo ─────────────────────────────────

class EventoPsicologoCrear(CamelModel):
    titulo:      str            = Field(..., min_length=3, max_length=200)
    tipo:        str            = Field(default="platica")
    descripcion: Optional[str] = None
    fecha_hora:  datetime
    modalidad:   str            = Field(default="presencial")
    lugar:       Optional[str] = Field(None, max_length=200)
    link_evento: Optional[str] = Field(None, max_length=500)
    capacidad:   Optional[int] = Field(None, ge=1)


class EventoPsicologoRespuesta(CamelModel):
    id:          str
    titulo:      str
    tipo:        str
    descripcion: Optional[str]
    fecha_hora:  datetime
    modalidad:   str
    lugar:       Optional[str]
    link_evento: Optional[str]
    capacidad:   Optional[int]
    activo:      bool
    creado_en:   datetime

    

# ── Genéricos ─────────────────────────────────────────────

class MensajeRespuesta(CamelModel):
    mensaje: str
    exito:   bool = True


class PaginacionParams(CamelModel):
    pagina:     int = Field(default=1,  ge=1)
    por_pagina: int = Field(default=20, ge=1, le=100)

# ── Recuperación de contraseña ────────────────────────────

class LoginTelefonoRequest(CamelModel):
    telefono: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=1)

class PasswordResetRequest(CamelModel):
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

class AsignacionCrear(CamelModel):
    psicologo_id:  str
    estudiante_id: str
    notas:         Optional[str] = None

class AsignacionRespuesta(CamelModel):
    id:            str
    psicologo_id:  str
    estudiante_id: str
    activa:        bool
    notas:         Optional[str]
    creada_en:     datetime

    
# Alias para compatibilidad
PasswordResetEmailRequest = PasswordResetRequest

class SolicitarVerificacionRequest(CamelModel):
    email: str
    nombre: str

class VerificarCodigoRequest(CamelModel):
    email: str
    codigo: str


# ── Cola de atención ───────────────────────────────────────

class ColaReasignar(CamelModel):
    """Reasignar un caso a otro psicólogo."""
    psicologo_id: str = Field(..., min_length=1)


class ColaAsignar(CamelModel):
    """Asignar manualmente un estudiante a un psicólogo."""
    estudiante_id: str = Field(..., min_length=1)
    psicologo_id:  str = Field(..., min_length=1)
    motivo:        Optional[str] = Field(None, max_length=500)
    prioridad:     PrioridadCola = PrioridadCola.MEDIA


class ColaRespuesta(CamelModel):
    id:             str
    estudiante_id:  str
    psicologo_id:   Optional[str]
    estado:         EstadoCola
    prioridad:      PrioridadCola
    origen:         str
    motivo:         Optional[str]
    creada_en:      Optional[datetime]
    tomada_en:      Optional[datetime]
    resuelta_en:    Optional[datetime]

    class Config:
        from_attributes = True
 
