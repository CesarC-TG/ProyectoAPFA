"""
Modelos de base de datos — ApoYo FES Acatlán
"""

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float,
    DateTime, ForeignKey, Enum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum
import uuid


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ────────────────────────────────────────────────

class RolUsuario(str, enum.Enum):
    ESTUDIANTE = "estudiante"
    PSICOLOGO  = "psicologo"
    ADMIN      = "admin"


class TipoRecurso(str, enum.Enum):
    RESPIRACION  = "respiracion"
    MEDITACION   = "meditacion"
    EJERCICIO    = "ejercicio"
    LECTURA      = "lectura"
    VIDEO        = "video"
    CLINICA      = "clinica"
    LINEA_CRISIS = "linea_crisis"


class EstadoCita(str, enum.Enum):
    PENDIENTE   = "pendiente"
    CONFIRMADA  = "confirmada"
    CANCELADA   = "cancelada"
    COMPLETADA  = "completada"


class EstadoCola(str, enum.Enum):
    PENDIENTE = "pendiente"
    TOMADA    = "tomada"
    RESUELTA  = "resuelta"


class PrioridadCola(str, enum.Enum):
    ALTA  = "alta"
    MEDIA = "media"
    BAJA  = "baja"


# ── Modelos ───────────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"
   
    
    # El resto de tus columnas se quedan igual...

    id              = Column(String(36),  primary_key=True, default=gen_uuid)
    nombre          = Column(String(120), nullable=False)
    apellidos       = Column(String(120), nullable=True)
    email           = Column(String(200), unique=True, nullable=False, index=True)
    # BUG FIX: campo faltante — sin este campo el registro local nunca almacenaba la contraseña
    password_hash   = Column(String(255), nullable=True)   # NULL para usuarios OAuth-only
    numero_cuenta   = Column(String(20),  unique=True, nullable=True)
    carrera         = Column(String(100), nullable=True)
    semestre        = Column(Integer,     nullable=True)
    avatar_url      = Column(String(500), nullable=True)

    rol             = Column(Enum(RolUsuario), default=RolUsuario.ESTUDIANTE, nullable=False)
    activo          = Column(Boolean, default=True)
    email_verificado = Column(Boolean, default=False)
    # Señal de crisis persistente — reemplaza alerta_crisis del diario (eliminado).
    # Se activa al disparar SOS y se apaga al resolver el caso en la cola.
    en_crisis       = Column(Boolean, default=False, nullable=False, index=True)

    telefono        = Column(String(20),  unique=True, nullable=True, index=True)
    password_reset_token = Column(String(100), nullable=True)

    # ── Contacto de emergencia ────────────────────────────
    emergencia_nombre   = Column(String(120), nullable=True)
    emergencia_telefono = Column(String(20),  nullable=True)
    emergencia_email    = Column(String(200), nullable=True)

    # ── Categoría problemática (asignada por psicólogo) ───
    categoria_problema  = Column(String(50),  nullable=True)

    # Google OAuth
    google_id       = Column(String(100), unique=True, nullable=True)

    # Seguridad: intentos fallidos de login
    intentos_fallidos   = Column(Integer, default=0)
    bloqueado_hasta     = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    creado_en       = Column(DateTime(timezone=True), server_default=func.now())
    actualizado_en  = Column(DateTime(timezone=True), onupdate=func.now())
    ultimo_acceso   = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    sesiones        = relationship("SesionUsuario",  back_populates="usuario",
                                   cascade="all, delete-orphan")
    citas           = relationship("Cita", back_populates="estudiante",
                                   foreign_keys="Cita.estudiante_id")
    mensajes_chat   = relationship("MensajeChat",   back_populates="usuario")
    notificaciones  = relationship("Notificacion",  back_populates="usuario")
    eventos_sos     = relationship("EventoSOS",     back_populates="usuario",
                                   foreign_keys="EventoSOS.usuario_id")

    __table_args__ = (
        Index("ix_usuario_email", "email"),
        Index("ix_usuario_rol",   "rol"),
    )

    def __repr__(self) -> str:
        return f"<Usuario {self.email} [{self.rol}]>"


class SesionUsuario(Base):
    """Refresh tokens para JWT — un registro por dispositivo/sesión."""
    __tablename__ = "sesiones_usuario"

    id            = Column(String(36),  primary_key=True, default=gen_uuid)
    usuario_id    = Column(String(36),  ForeignKey("usuarios.id"), nullable=False)
    refresh_token = Column(String(500), unique=True, nullable=False)
    user_agent    = Column(String(500), nullable=True)
    ip_address    = Column(String(50),  nullable=True)
    activa        = Column(Boolean, default=True)
    expira_en     = Column(DateTime(timezone=True), nullable=False)
    creada_en     = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="sesiones")

    __table_args__ = (
        Index("ix_sesion_token", "refresh_token"),
        Index("ix_sesion_usuario", "usuario_id"),
    )


class Recurso(Base):
    __tablename__ = "recursos"

    id                = Column(String(36),  primary_key=True, default=gen_uuid)
    titulo            = Column(String(200), nullable=False)
    descripcion       = Column(Text,        nullable=True)
    tipo              = Column(Enum(TipoRecurso), nullable=False)

    contenido         = Column(JSON,        nullable=True)
    duracion_minutos  = Column(Integer,     nullable=True)
    imagen_url        = Column(String(500), nullable=True)
    url_externo       = Column(String(500), nullable=True)

    telefono          = Column(String(30),  nullable=True)
    direccion         = Column(String(300), nullable=True)
    horario           = Column(String(200), nullable=True)
    disponible_24h    = Column(Boolean,     default=False)

    activo            = Column(Boolean, default=True)
    orden             = Column(Integer, default=0)
    vistas            = Column(Integer, default=0)

    creado_en         = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_recurso_tipo",  "tipo"),
        Index("ix_recurso_activo","activo"),
    )


class EventoSOS(Base):
    """Registro inmutable de eventos de emergencia."""
    __tablename__ = "eventos_sos"

    id           = Column(String(36), primary_key=True, default=gen_uuid)
    usuario_id   = Column(String(36), ForeignKey("usuarios.id"), nullable=True)

    tipo_accion  = Column(String(50),  nullable=False)
    descripcion  = Column(String(200), nullable=True)
    latitud      = Column(Float,  nullable=True)
    longitud     = Column(Float,  nullable=True)
    ip_address   = Column(String(50), nullable=True)

    atendido        = Column(Boolean, default=False)
    atendido_por    = Column(String(36), ForeignKey("usuarios.id"), nullable=True)
    notas_atencion  = Column(Text, nullable=True)

    creado_en    = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="eventos_sos",
                           foreign_keys=[usuario_id])

    __table_args__ = (
        Index("ix_sos_atendido", "atendido"),
        Index("ix_sos_usuario",  "usuario_id"),
    )


class MensajeChat(Base):
    """Historial de conversaciones con el chatbot — ordenado por creado_en."""
    __tablename__ = "mensajes_chat"

    id             = Column(String(36), primary_key=True, default=gen_uuid)
    usuario_id     = Column(String(36), ForeignKey("usuarios.id"), nullable=False)
    sesion_chat_id = Column(String(36), nullable=False)

    rol            = Column(String(20), nullable=False)   # "user" | "assistant"
    contenido      = Column(Text, nullable=False)
    metadata_ia    = Column(JSON, nullable=True)

    creado_en      = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="mensajes_chat")

    __table_args__ = (
        Index("ix_chat_sesion",  "sesion_chat_id"),
        Index("ix_chat_usuario", "usuario_id"),
    )


class Cita(Base):
    """Citas agendadas entre estudiantes y psicólogos."""
    __tablename__ = "citas"

    id                  = Column(String(36), primary_key=True, default=gen_uuid)
    estudiante_id       = Column(String(36), ForeignKey("usuarios.id"), nullable=False)
    psicologo_id        = Column(String(36), ForeignKey("usuarios.id"), nullable=False)

    fecha_hora          = Column(DateTime(timezone=True), nullable=False)
    duracion_minutos    = Column(Integer, default=50)
    modalidad           = Column(String(20), default="presencial")
    estado              = Column(Enum(EstadoCita), default=EstadoCita.PENDIENTE)

    motivo              = Column(Text,        nullable=True)
    notas_psicologo     = Column(Text,        nullable=True)
    link_videollamada   = Column(String(500), nullable=True)

    recordatorio_enviado = Column(Boolean, default=False)
    creada_en           = Column(DateTime(timezone=True), server_default=func.now())

    estudiante = relationship("Usuario", foreign_keys=[estudiante_id],
                              back_populates="citas")
    psicologo  = relationship("Usuario", foreign_keys=[psicologo_id])

    __table_args__ = (
        Index("ix_cita_psicologo", "psicologo_id"),
        Index("ix_cita_estado",    "estado"),
    )


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id         = Column(String(36),  primary_key=True, default=gen_uuid)
    usuario_id = Column(String(36),  ForeignKey("usuarios.id"), nullable=False)

    titulo     = Column(String(200), nullable=False)
    mensaje    = Column(Text,        nullable=False)
    tipo       = Column(String(50),  default="info")
    leida      = Column(Boolean,     default=False)
    url_accion = Column(String(300), nullable=True)

    creada_en  = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="notificaciones")

    __table_args__ = (
        Index("ix_notif_usuario", "usuario_id"),
        Index("ix_notif_leida",   "leida"),
    )

class AsignacionPsicologo(Base):
    """Asignación explícita de estudiantes a un psicólogo."""
    __tablename__ = "asignaciones_psicologo"

    id            = Column(String(36), primary_key=True, default=gen_uuid)
    psicologo_id  = Column(String(36), ForeignKey("usuarios.id"), nullable=False)
    estudiante_id = Column(String(36), ForeignKey("usuarios.id"), nullable=False)
    activa        = Column(Boolean, default=True)
    notas         = Column(Text, nullable=True)
    creada_en     = Column(DateTime(timezone=True), server_default=func.now())

    psicologo  = relationship("Usuario", foreign_keys=[psicologo_id])
    estudiante = relationship("Usuario", foreign_keys=[estudiante_id])

    __table_args__ = (
        Index("ix_asig_psicologo",  "psicologo_id"),
        Index("ix_asig_estudiante", "estudiante_id"),
    )

class EventoPsicologo(Base):
    """Eventos (pláticas, talleres) creados por un psicólogo."""
    __tablename__ = "eventos_psicologo"

    id           = Column(String(36), primary_key=True, default=gen_uuid)
    psicologo_id = Column(String(36), ForeignKey("usuarios.id"), nullable=False)

    titulo       = Column(String(200), nullable=False)
    tipo         = Column(String(30),  default="platica")   # platica | taller | otro
    descripcion  = Column(Text,        nullable=True)
    fecha_hora   = Column(DateTime(timezone=True), nullable=False)
    modalidad    = Column(String(20),  default="presencial")  # presencial | en_linea
    lugar        = Column(String(200), nullable=True)
    link_evento  = Column(String(500), nullable=True)
    capacidad    = Column(Integer,     nullable=True)
    activo       = Column(Boolean,     default=True)
    creado_en    = Column(DateTime(timezone=True), server_default=func.now())

    psicologo = relationship("Usuario", foreign_keys=[psicologo_id])

    __table_args__ = (Index("ix_evento_psicologo", "psicologo_id"),)


class VerificacionRegistro(Base):
     """Token de 6 dígitos para verificar el correo antes de completar el registro."""
     __tablename__ = "verificaciones_registro"

     id         = Column(String(36), primary_key=True, default=gen_uuid)
     email      = Column(String(200), nullable=False, index=True)
     codigo     = Column(String(6),   nullable=False)
     expira_en  = Column(DateTime(timezone=True), nullable=False)
     usado      = Column(Boolean, default=False)
     creado_en  = Column(DateTime(timezone=True), server_default=func.now())

     __table_args__ = (Index("ix_verif_email", "email"),)


class ColaAtencion(Base):
    """Cola de trabajo para psicólogos — estado y dueño de cada caso."""
    __tablename__ = "cola_atencion"

    id            = Column(String(36), primary_key=True, default=gen_uuid)
    estudiante_id = Column(String(36), ForeignKey("usuarios.id"), nullable=False)
    psicologo_id  = Column(String(36), ForeignKey("usuarios.id"), nullable=True)

    estado        = Column(Enum(EstadoCola), default=EstadoCola.PENDIENTE, nullable=False)
    prioridad     = Column(Enum(PrioridadCola), default=PrioridadCola.MEDIA, nullable=False)
    origen        = Column(String(30), default="manual")   # sos | inactividad | manual
    motivo        = Column(Text, nullable=True)

    creada_en     = Column(DateTime(timezone=True), server_default=func.now())
    tomada_en     = Column(DateTime(timezone=True), nullable=True)
    resuelta_en   = Column(DateTime(timezone=True), nullable=True)

    estudiante = relationship("Usuario", foreign_keys=[estudiante_id])
    psicologo  = relationship("Usuario", foreign_keys=[psicologo_id])

    __table_args__ = (
        Index("ix_cola_estado",     "estado"),
        Index("ix_cola_prioridad",  "prioridad"),
        Index("ix_cola_estudiante", "estudiante_id"),
        Index("ix_cola_psicologo",  "psicologo_id"),
    )


class AuditoriaAcceso(Base):
    """Registro inmutable de accesos a expedientes y acciones sobre la cola."""
    __tablename__ = "auditoria_acceso"

    id            = Column(String(36), primary_key=True, default=gen_uuid)
    psicologo_id  = Column(String(36), ForeignKey("usuarios.id"), nullable=True)
    estudiante_id = Column(String(36), ForeignKey("usuarios.id"), nullable=True)

    accion        = Column(String(40), nullable=False)  # ver_expediente | tomar_caso | reasignar | liberar | resolver | asignar
    detalle       = Column(Text, nullable=True)
    ip_address    = Column(String(50), nullable=True)

    creado_en     = Column(DateTime(timezone=True), server_default=func.now())

    psicologo  = relationship("Usuario", foreign_keys=[psicologo_id])
    estudiante = relationship("Usuario", foreign_keys=[estudiante_id])

    __table_args__ = (
        Index("ix_auditoria_psicologo",  "psicologo_id"),
        Index("ix_auditoria_estudiante", "estudiante_id"),
        Index("ix_auditoria_accion",     "accion"),
    )
 
