"""
WebSockets — Notificaciones + Chat psicólogo↔usuario en tiempo real
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Set
from datetime import datetime
import json

from app.database import get_db
from app.models import Notificacion, MensajeChat
from app.service.auth_service import decodificar_token

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        # usuario_id -> set of WebSockets (para notificaciones)
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # usuario_id -> WebSocket (para chat directo)
        self.chat_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, usuario_id: str):
        await websocket.accept()
        if usuario_id not in self.active_connections:
            self.active_connections[usuario_id] = set()
        self.active_connections[usuario_id].add(websocket)

    def disconnect(self, websocket: WebSocket, usuario_id: str):
        if usuario_id in self.active_connections:
            self.active_connections[usuario_id].discard(websocket)
            if not self.active_connections[usuario_id]:
                del self.active_connections[usuario_id]

    async def connect_chat(self, websocket: WebSocket, usuario_id: str):
        await websocket.accept()
        self.chat_connections[usuario_id] = websocket

    def disconnect_chat(self, usuario_id: str):
        self.chat_connections.pop(usuario_id, None)

    async def send_to_user(self, usuario_id: str, data: dict):
        if usuario_id in self.active_connections:
            dead = set()
            for ws in self.active_connections[usuario_id].copy():
                try:
                    await ws.send_json(data)
                except Exception:
                    dead.add(ws)
            for ws in dead:
                self.active_connections[usuario_id].discard(ws)

    async def send_chat(self, usuario_id: str, data: dict) -> bool:
        """Enviar mensaje de chat a un usuario específico. Retorna True si se entregó."""
        ws = self.chat_connections.get(usuario_id)
        if ws:
            try:
                await ws.send_json(data)
                return True
            except Exception:
                self.chat_connections.pop(usuario_id, None)
        return False

    def is_online(self, usuario_id: str) -> bool:
        return usuario_id in self.chat_connections

    async def broadcast_to_role(self, role: str, data: dict):
        for conns in self.active_connections.values():
            for ws in conns.copy():
                try:
                    await ws.send_json(data)
                except Exception:
                    pass


manager = ConnectionManager()


# ── WebSocket de notificaciones generales ─────────────────

@router.websocket("/notificaciones")
async def websocket_notificaciones(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decodificar_token(token)
        usuario_id = payload.get("sub")
        if not usuario_id:
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, usuario_id)

    # Enviar notificaciones no leídas al conectar
    try:
        result = await db.execute(
            select(Notificacion)
            .where(Notificacion.usuario_id == usuario_id, Notificacion.leida == False)
            .order_by(Notificacion.creada_en.desc())
            .limit(10)
        )
        pendientes = result.scalars().all()
        if pendientes:
            await websocket.send_json({
                "tipo": "notificaciones_pendientes",
                "datos": [
                    {"id": n.id, "titulo": n.titulo, "mensaje": n.mensaje,
                     "tipo": n.tipo, "creada_en": n.creada_en.isoformat()}
                    for n in pendientes
                ],
            })
    except Exception:
        pass

    try:
        while True:
            data = await websocket.receive_text()
            try:
                mensaje = json.loads(data)
                tipo = mensaje.get("tipo")

                if tipo == "ping":
                    await websocket.send_json({"tipo": "pong", "timestamp": datetime.utcnow().isoformat()})

                elif tipo == "marcar_leida":
                    notif_id = mensaje.get("notificacion_id")
                    if notif_id:
                        notif = await db.get(Notificacion, notif_id)
                        if notif and notif.usuario_id == usuario_id:
                            notif.leida = True
                            await db.commit()
                            await websocket.send_json({"tipo": "notificacion_leida", "id": notif_id})
            except json.JSONDecodeError:
                await websocket.send_json({"tipo": "error", "mensaje": "JSON inválido"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, usuario_id)


# ── WebSocket de chat directo usuario↔psicólogo ───────────

@router.websocket("/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Chat en tiempo real entre usuario y psicólogo.
    Ambos se conectan con su token JWT.
    El frontend envía: { "tipo": "mensaje", "destinatario_id": "...", "contenido": "..." }
    """
    try:
        payload = decodificar_token(token)
        usuario_id = payload.get("sub")
        rol = payload.get("rol", "")
        if not usuario_id:
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await manager.connect_chat(websocket, usuario_id)

    # Notificar al otro lado que el usuario está en línea
    await websocket.send_json({
        "tipo": "conectado",
        "usuario_id": usuario_id,
        "timestamp": datetime.utcnow().isoformat(),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                tipo = data.get("tipo")

                if tipo == "ping":
                    await websocket.send_json({"tipo": "pong"})

                elif tipo == "mensaje":
                    destinatario_id = data.get("destinatario_id")
                    contenido = (data.get("contenido") or "").strip()
                    if not destinatario_id or not contenido:
                        continue

                    ts = datetime.utcnow().isoformat()
                    paquete = {
                        "tipo": "mensaje",
                        "remitente_id": usuario_id,
                        "contenido": contenido,
                        "timestamp": ts,
                    }

                    # Intentar entregar en tiempo real
                    entregado = await manager.send_chat(destinatario_id, paquete)

                    # Confirmar al remitente
                    await websocket.send_json({
                        "tipo": "mensaje_enviado",
                        "contenido": contenido,
                        "timestamp": ts,
                        "entregado": entregado,
                    })

                elif tipo == "estado":
                    # Consultar si un usuario está en línea
                    uid = data.get("usuario_id")
                    await websocket.send_json({
                        "tipo": "estado_usuario",
                        "usuario_id": uid,
                        "en_linea": manager.is_online(uid) if uid else False,
                    })

            except json.JSONDecodeError:
                await websocket.send_json({"tipo": "error", "mensaje": "JSON inválido"})

    except WebSocketDisconnect:
        manager.disconnect_chat(usuario_id)


# ── Helpers para notificar desde otros routers ─────────────

async def notificar_usuario(usuario_id: str, titulo: str, mensaje: str, tipo: str = "info"):
    await manager.send_to_user(usuario_id, {
        "tipo": "nueva_notificacion",
        "datos": {"titulo": titulo, "mensaje": mensaje, "tipo_notif": tipo,
                  "timestamp": datetime.utcnow().isoformat()},
    })


async def notificar_sos_en_vivo(evento_data: dict):
    await manager.broadcast_to_role("psicologo", {
        "tipo": "alerta_sos",
        "datos": evento_data,
        "timestamp": datetime.utcnow().isoformat(),
    })