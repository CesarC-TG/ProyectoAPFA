# SCHEMA_PROPUESTO — APFA / KAI (PostgreSQL)

Mapa del esquema de base de datos actual. Motor: **PostgreSQL 16** vía SQLAlchemy 2.0 async + asyncpg.
IDs: `String(36)` con UUID generados por la app. Timestamps en UTC (`timezone=True`).

## Enums

| Enum | Valores |
|---|---|
| `RolUsuario` | `estudiante`, `psicologo`, `admin` |
| `TipoRecurso` | `respiracion`, `meditacion`, `ejercicio`, `lectura`, `video`, `clinica`, `linea_crisis` |
| `EstadoCita` | `pendiente`, `confirmada`, `cancelada`, `completada` |
| `EstadoCola` | `pendiente`, `tomada`, `resuelta` |
| `PrioridadCola` | `alta`, `media`, `baja` |

> `EstadoAnimo` fue **eliminado** junto con el diario (ver DECISION_LOG #1).

## Tablas

### `usuarios` — Usuario (identidad central, 3 roles)
| Columna | Tipo | Notas |
|---|---|---|
| id | String(36) PK | uuid |
| nombre / apellidos | String(120) | |
| email | String(200) unique, index | normalizado a minúsculas |
| password_hash | String(255) nullable | NULL para OAuth-only |
| numero_cuenta | String(20) unique nullable | |
| carrera / semestre | String(100) / Integer | |
| avatar_url | String(500) nullable | |
| rol | Enum(RolUsuario) | default `estudiante` |
| activo | Boolean | soft-delete |
| email_verificado | Boolean | |
| **en_crisis** | Boolean, index | señal de crisis (reemplaza `alerta_crisis` del diario) |
| telefono | String(20) unique nullable | |
| password_reset_token | String(100) nullable | |
| emergencia_nombre / telefono / email | String | contacto de emergencia |
| categoria_problema | String(50) nullable | asignada por psicólogo |
| google_id | String(100) unique nullable | OAuth |
| intentos_fallidos / bloqueado_hasta | Integer / DateTime | brute-force |
| creado_en / actualizado_en / ultimo_acceso | DateTime(tz) | |

### `sesiones_usuario` — SesionUsuario (refresh tokens JWT)
`id`, `usuario_id` FK, `refresh_token` unique, `user_agent`, `ip_address`, `activa`, `expira_en`, `creada_en`.

### `recursos` — Recurso (técnicas/clínicas/líneas de crisis)
`id`, `titulo`, `descripcion`, `tipo` enum, `contenido` JSON, `duracion_minutos`, `imagen_url`,
`url_externo`, `telefono`, `direccion`, `horario`, `disponible_24h`, `activo`, `orden`, `vistas`, `creado_en`.

### `eventos_sos` — EventoSOS (registro inmutable de emergencias)
`id`, `usuario_id` FK nullable, `tipo_accion`, `descripcion`, `latitud`, `longitud`, `ip_address`,
`atendido`, `atendido_por` FK, `notas_atencion`, `creado_en`.

### `mensajes_chat` — MensajeChat (historial del chatbot)
`id`, `usuario_id` FK, `sesion_chat_id`, `rol` (`user`/`assistant`), `contenido`, `metadata_ia` JSON, `creado_en`.

### `citas` — Cita (estudiante ↔ psicólogo)
`id`, `estudiante_id` FK, `psicologo_id` FK, `fecha_hora`, `duracion_minutos`, `modalidad`,
`estado` enum, `motivo`, `notas_psicologo`, `link_videollamada`, `recordatorio_enviado`, `creada_en`.

### `notificaciones` — Notificacion (in-app)
`id`, `usuario_id` FK, `titulo`, `mensaje`, `tipo`, `leida`, `url_accion`, `creada_en`.

### `asignaciones_psicologo` — AsignacionPsicologo (vínculo estudiante→psicólogo)
`id`, `psicologo_id` FK, `estudiante_id` FK, `activa`, `notas`, `creada_en`.
Un estudiante tiene **a lo sumo una asignación activa** (se desactivan las previas al reasignar).

### `eventos_psicologo` — EventoPsicologo (pláticas/talleres)
`id`, `psicologo_id` FK, `titulo`, `tipo`, `descripcion`, `fecha_hora`, `modalidad`, `lugar`,
`link_evento`, `capacidad`, `activo`, `creado_en`.

### `verificaciones_registro` — VerificacionRegistro (código de 6 dígitos)
`id`, `email`, `codigo`, `expira_en`, `usado`, `creado_en`.

### `cola_atencion` — ColaAtencion ⭐ (nueva)
| Columna | Tipo | Notas |
|---|---|---|
| id | String(36) PK | |
| estudiante_id | String(36) FK → usuarios | |
| psicologo_id | String(36) FK → usuarios, nullable | dueño actual |
| estado | Enum(EstadoCola) | `pendiente` → `tomada` → `resuelta` |
| prioridad | Enum(PrioridadCola) | ordena la cola (alta primero) |
| origen | String(30) | `sos` \| `inactividad` \| `manual` |
| motivo | Text nullable | razón de ingreso |
| creada_en / tomada_en / resuelta_en | DateTime(tz) | |

### `auditoria_acceso` — AuditoriaAcceso ⭐ (nueva, inmutable)
`id`, `psicologo_id` FK nullable, `estudiante_id` FK nullable, `accion`
(`ver_expediente` \| `tomar_caso` \| `reasignar` \| `liberar` \| `resolver` \| `asignar`),
`detalle`, `ip_address`, `creado_en`.

## Relaciones clave

- `Usuario` → `sesiones`, `citas` (como estudiante), `mensajes_chat`, `notificaciones`, `eventos_sos`.
- `ColaAtencion` → `estudiante` (Usuario) y `psicologo` (Usuario).
- `AsignacionPsicologo` → un `estudiante` y un `psicologo` (historial de vínculos, `activa` marca el actual).
- `AuditoriaAcceso` → registra quién (psicólogo) accedió a qué (estudiante) y qué acción hizo.

## Notas de diseño

- **Sin multi-tenant**: un solo cliente (FES Acatlán); no hay columna de tenant.
- La señal de crisis es `usuarios.en_crisis`, alimentada por SOS y apagada al resolver el caso.
- El diario (`entradas_diario`) fue eliminado; su baja es reversible vía migración.
