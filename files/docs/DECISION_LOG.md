# DECISION_LOG — APFA / KAI

Registro de decisiones de diseño. Cada entrada documenta el **porqué**, no solo el qué,
para no rediscutir lo ya decidido. Convención: la decisión más reciente va **arriba**.

---

## 8. Convención camelCase en la API (JSON)

- **Fecha:** 2026-08-18
- **Estado:** Decidida — **pendiente de implementar** (fase E).

**Decisión:** Todo el JSON de la API responde en `camelCase` (`numeroCuenta`, `emergenciaNombre`,
`enCrisis`, `categoriaProblema`, …). Internamente el código Python sigue en `snake_case`.

**Implementación prevista:** clase base `CamelModel` (Pydantic v2) con
`alias_generator=to_camel` y `populate_by_name=True`, para que la entrada acepte ambos
casos durante la transición y el front migre sin romper.

**Motivo:** es una convención no negociable heredada del stack del equipo (mismo patrón en
`admin-panel-j2ec-backend`). El código actual aún responde `snake_case` — se migra en la fase E.

---

## 7. PostgreSQL como única base de datos (sin SQLite)

- **Fecha:** 2026-08-18
- **Estado:** Implementada.

**Decisión:** PostgreSQL es la única BD del backend. Se eliminó la rama SQLite de
`database.py`, el default de `config.py` apunta a Postgres, se quitó `aiosqlite` de
`requirements.txt` y el archivo local `apoyofes.db` fue eliminado.

**Motivo:** el stack de referencia (`READMEBACKENDSTACK.md`) exige PostgreSQL con `asyncpg`,
mismo patrón que el resto de los backends del equipo. SQLite era solo un atajo de desarrollo.

**Consecuencia:** el desarrollo local requiere Docker (`docker compose up -d` levanta
Postgres + Redis) o un PostgreSQL accesible en `localhost:5432`.

---

## 6. Roles: solo 3 (estudiante / psicólogo / admin)

- **Fecha:** 2026-08-18
- **Estado:** Implementada (parcial — se difiere el rol `tutor`).

**Decisión:** Por ahora se trabaja con los roles existentes `RolUsuario`: `estudiante`,
`psicologo` y `admin`. El rol `tutor` que propone `READMEBACKENDSTACK.md` (§4.4) queda
**diferido** hasta que el equipo defina su alcance.

**Motivo:** el cliente no ha definido qué acciones concretas hace la vista de tutores;
no tiene sentido crear el rol y sus endpoints sin ese alcance.

---

## 5. Reasignación de casos entre psicólogos

- **Fecha:** 2026-08-18
- **Estado:** Implementada.

**Decisión:** Un psicólogo puede asignar un estudiante a otro psicólogo, y si ya "tomó el
caso" puede **reasignarlo** a otro o **liberarlo** a `pendiente` para que otro lo tome.
Flujo de la cola: `pendiente → tomada → resuelta`, con `reasignar` (cambia dueño) y
`liberar` (vuelve a `pendiente`).

**Motivo:** la oferta de psicólogos es mucho menor que la demanda de estudiantes; se
necesita flexibilidad para distribuir carga sin duplicar trabajo.

**Implementación:** tabla `ColaAtencion` + endpoints `tomar` / `reasignar` / `liberar` /
`resolver` / `asignar`. El claim usa `SELECT … FOR UPDATE` (atómico, evita que dos
psicólogos tomen el mismo caso). Cada acción queda en `AuditoriaAcceso`.

---

## 4. Visibilidad total de estudiantes, SIN fuga de datos

- **Fecha:** 2026-08-18
- **Estado:** Implementada.

**Decisión:** Todos los psicólogos ven a todos los estudiantes (porque oferta << demanda),
pero separando **dos capas**:

1. **Roster** (`GET /api/psicologo/todos-estudiantes`): lista paginada/filtrable con datos
   **no sensibles** (nombre, carrera, semestre, categoría, señal de crisis). **Sin** email,
   teléfono ni contacto de emergencia.
2. **Expediente** (`GET /api/psicologo/estudiantes/{id}/expediente`): datos completos, pero
   **cada acceso queda registrado** en `AuditoriaAcceso` (quién, a quién, cuándo, desde qué IP).

**Motivo:** el cliente quiere que todos los psicólogos vean a todos los pacientes, pero hay
que evitar saturación (paginación/priorización) y fuga de datos (auditoría + PII mínima en el roster).

---

## 3. Cola de atención de psicólogos

- **Fecha:** 2026-08-18
- **Estado:** Implementada.

**Decisión:** Se crea una **cola de trabajo** (`ColaAtencion`) que los psicólogos consultan
priorizada (alta → media → baja). Se alimenta automáticamente desde el **SOS** (prioridad
alta) y desde **asignación manual** (`origen=manual`). La inactividad queda como origen
pendiente de conectar.

**Motivo:** con más demanda que oferta, el psicólogo debe atender primero al que más lo
necesita, no recorrer una lista plana.

---

## 2. Señal de crisis → `Usuario.en_crisis`

- **Fecha:** 2026-08-18
- **Estado:** Implementada.

**Decisión:** La señal de crisis que antes vivía en `EntradaDiario.alerta_crisis` se mueve a
un flag persistente **`Usuario.en_crisis`** (indexado). Se activa al registrar un SOS y se
apaga al **resolver** el caso en la cola.

**Motivo:** al eliminar el diario (decisión #1), la señal de crisis se perdía. El SOS es la
fuente de crisis natural que queda, y el flag persistente permite ordenar el roster y los
stats sin hacer JOIN a eventos en cada query.

---

## 1. Eliminación del diario

- **Fecha:** 2026-08-18
- **Estado:** Implementada.

**Decisión:** Se elimina el módulo "Diario" por **petición del cliente**. Se borran
`EntradaDiario`, el enum `EstadoAnimo`, el router `diario.py`, el servicio
`ia_service.py` y todas sus referencias (frontend y backend). La baja de tabla es
**reversible** vía migración Alembic (`b8e2a1f4c5d7.downgrade()`).

**Motivo:** el cliente ya no quiere el diario en la plataforma.

**Consecuencia:** `alerta_crisis` desaparece con él → se reemplaza por `Usuario.en_crisis`
(decisión #2).

---

## Migraciones Alembic (referencia)

```
base → a376f6ad6ab3 (telefono + password_reset_token)
     → 07e9db670b45 (verificacion_registro)
     → b8e2a1f4c5d7 (elimina diario + agrega en_crisis)  ← reversible
     → d3f7c9e2a1b4 (cola_atencion + auditoria_acceso)   [HEAD]
```
