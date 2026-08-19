# API_PROPUESTA — APFA / KAI

Contrato de API del backend. Frontend (dashboard, estudiantes, psicólogos) consume todo por aquí.
Base URL local: `http://localhost:8000`. Docs interactivos: `/api/docs` (Swagger), `/api/redoc`.

> ⚠️ **Convención de campos:** el estándar del equipo es **camelCase** en el JSON
> (`numeroCuenta`, `enCrisis`, `categoriaProblema`). El código actual aún responde
> **snake_case** (`numero_cuenta`, `en_crisis`, …); la migración a camelCase es la **fase E**
> (pendiente). Mientras tanto, los nombres de abajo están en snake_case tal como responde hoy.

## Autenticación
Todos los endpoints protegidos requieren `Authorization: Bearer <access_token>`.
El JWT lleva el ID del usuario; el rol se resuelve consultando la BD (no se confía en el cliente).

## Endpoints por prefijo

### `/api/auth` — Autenticación
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/registro` | Registro estudiante (email + contraseña) |
| POST | `/login` | Login email + contraseña |
| POST | `/login-telefono` | Login teléfono + contraseña |
| POST | `/google` | Login/registro OAuth Google (dominio UNAM) |
| POST | `/refresh` | Rotar access + refresh token |
| POST | `/logout` | Cierra una sesión |
| POST | `/logout-all` | Cierra todas las sesiones |
| GET | `/me` | Perfil del usuario autenticado |
| POST | `/recuperar-password` | Genera contraseña temporal (email/teléfono) |
| POST | `/solicitar-verificacion` | Envía código de verificación de 6 dígitos |
| POST | `/verificar-codigo` | Valida el código de verificación |

### `/api/users` — Usuarios (perfil propio)
Edición de perfil del estudiante autenticado.

### `/api/recursos` — Recursos
CRUD de recursos (técnicas, clínicas, líneas de crisis). Listado público de recursos activos.

### `/api/sos` — SOS / emergencias
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/lineas` | Líneas de crisis (público) |
| POST | `/evento` | Registra un evento SOS (con o sin sesión) |
| GET | `/eventos` | Historial SOS del usuario |
| GET | `/admin/eventos` | Todos los eventos SOS (psicólogo/admin) |
| PATCH | `/admin/eventos/{id}/atender` | Marca evento atendido |

### `/api/notificaciones` — Notificaciones in-app
Listado y marcado de leídas para el usuario autenticado.

### `/api/chatbot` — Chatbot IA (KAI / LM Studio)
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/mensaje` | Envía mensaje y obtiene respuesta IA |
| GET | `/historial/{sesion_id}` | Historial de una sesión |
| GET | `/sesiones` | Lista sesiones de chat |

### `/api/admin` — Administración (rol `admin`)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/stats` | Totales (estudiantes, psicólogos, alertas SOS, en crisis, chats) |
| GET | `/actividad-usuarios` | Actividad + días sin entrar + SOS por usuario |
| GET | `/sos-actividad` | Detalle de eventos SOS |
| GET/POST/PATCH/DELETE | `/usuarios` | CRUD de usuarios (crear con cualquier rol, editar, soft/hard delete) |
| PATCH | `/usuarios/{id}/rol` | Cambia el rol |
| PATCH | `/usuarios/{id}/activar` | Activa/desactiva |
| GET/POST/DELETE | `/asignaciones` | Asignaciones estudiante↔psicólogo |
| GET | `/psicologos-disponibles` | Psicólogos con conteo de estudiantes asignados |
| POST/GET/PATCH | `/citas` | CRUD de citas (psicólogo) |

### `/api/psicologo` — Vista del psicólogo (roles `psicologo` y `admin`)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/perfil` | Perfil del psicólogo |
| GET | `/mis-estudiantes` | Estudiantes vinculados (citas/asignación) |
| GET | `/todos-estudiantes` | **Roster** paginado de todos los estudiantes (sin PII) · `pagina`, `por_pagina`, `buscar`, `categoria`, `solo_crisis` |
| GET | `/estudiantes/{id}/expediente` | **Expediente completo** (auditado) |
| PATCH | `/estudiantes/{id}/categoria` | Asigna categoría de problemática |
| GET | `/intervenciones` | Intervenciones con conteo de citas |
| GET | `/diarios` — **eliminado** | (el diario fue removido) |
| GET/POST | `/citas` | Citas del psicólogo |
| PATCH | `/citas/{id}/estado` | Cambia estado de cita |
| PATCH | `/citas/{id}/notas` | Guarda observaciones privadas |
| GET | `/actividad` | Reporte de actividad de estudiantes asignados |
| GET | `/stats` | Totales del psicólogo (asignados, citas pendientes, en crisis, SOS 30d) |
| GET/POST/PUT/DELETE | `/eventos` | Pláticas/talleres del psicólogo |

### `/api/psicologo/cola` — Cola de atención ⭐ (nueva)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/cola` | Cola priorizada (alta→baja), paginada, filtrable por `estado`, `prioridad`, `origen`, `buscar` |
| POST | `/cola/{id}/tomar` | Toma el caso (claim atómico) |
| POST | `/cola/{id}/reasignar` | Reasigna a otro psicólogo |
| POST | `/cola/{id}/liberar` | Libera a `pendiente` para que otro lo tome |
| POST | `/cola/{id}/resolver` | Resuelve el caso (apaga `en_crisis`) |
| POST | `/asignar` | Asignación manual directa (crea/reabre caso en `tomada`) |

### `/ws` — WebSockets
Notificaciones/tiempo real (chat con psicólogo, presencia).

## Reglas de negocio importantes

- **Roster sin PII**: `todos-estudiantes` nunca expone email/teléfono/emergencia.
- **Expediente auditado**: cada acceso a `expediente` deja fila en `auditoria_acceso`.
- **Claim atómico**: `tomar` usa `FOR UPDATE`; dos psicólogos no pueden tomar el mismo caso.
- **SOS → cola**: registrar un SOS activa `en_crisis` y encola el caso (origen `sos`, prioridad `alta`).
- **Ningún campo calculado server-side** se acepta en el body de un request.
