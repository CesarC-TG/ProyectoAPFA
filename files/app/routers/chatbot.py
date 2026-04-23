"""
Router Chatbot IA — conversación con historial persistente
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import uuid, httpx, os

from google import genai
from google.genai import types

from app.database import get_db
from app.models import Usuario, MensajeChat
from app.schemas import MensajeChatEnviar, MensajeChatRespuesta, HistorialChatRespuesta
from app.service.auth_service import get_current_user

router = APIRouter()

SYSTEM_PROMPT = SYSTEM_PROMPT = """Eres KAI, el asistente de bienestar emocional de la FES Acatlán (UNAM).
Tu objetivo es brindar apoyo empático, cálido y sin prejuicios a la comunidad estudiantil.

Estás capacitado para escuchar, validar y orientar sobre temas como: 
estrés, ansiedad, depresión, duelo, adicciones, TDAH, espectro autista (TEA) y trastornos alimenticios (TCA).

REGLAS ESTRICTAS E INQUEBRANTABLES:
1. LÍMITE CLÍNICO: NO eres médico. Jamás diagnostiques, ni des indicaciones médicas, ni recetes absolutamente nada.
2. PROTOCOLO DE CRISIS: Si detectas cualquier mención de autolesión, suicidio, sobredosis o violencia inminente, ABANDONA la conversación normal y deriva INMEDIATAMENTE con este texto: "Por favor, busca ayuda urgente. No estás solo/a. Llama a SAPTEL: 800 290 0024 (24hrs) o acude a Psicopedagogía FES: 55 5623 1666."
3. ESTILO: Responde en español de México (tono cercano y respetuoso), sé conversacional, no uses listas largas y limítate a máximo 150-200 palabras. 

Cierra tus respuestas con una pregunta suave para invitar a la reflexión."""

@router.post("/mensaje", response_model=MensajeChatRespuesta)
async def enviar_mensaje(
    datos: MensajeChatEnviar,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    sesion_id = datos.sesion_id or str(uuid.uuid4())

    # Historial de la sesión (últimos 20 mensajes)
    result = await db.execute(
        select(MensajeChat)
        .where(MensajeChat.usuario_id == usuario.id, MensajeChat.sesion_chat_id == sesion_id)
        .order_by(MensajeChat.creado_en.asc())
        .limit(20)
    )
    historial = result.scalars().all()

    mensajes_api = [{"role": m.rol, "content": m.contenido} for m in historial]
    mensajes_api.append({"role": "user", "content": datos.contenido})

    respuesta_texto = await _llamar_ia(mensajes_api)

    msg_usuario = MensajeChat(
        id=str(uuid.uuid4()), usuario_id=usuario.id,
        sesion_chat_id=sesion_id, rol="user", contenido=datos.contenido,
    )
    msg_asistente = MensajeChat(
        id=str(uuid.uuid4()), usuario_id=usuario.id,
        sesion_chat_id=sesion_id, rol="assistant", contenido=respuesta_texto,
    )
    db.add(msg_usuario)
    db.add(msg_asistente)
    await db.commit()
    await db.refresh(msg_asistente)

    # Adaptar a schema (sesion_id en lugar de sesion_chat_id)
    msg_asistente.sesion_id = sesion_id
    return msg_asistente


@router.get("/historial/{sesion_id}", response_model=HistorialChatRespuesta)
async def obtener_historial(
    sesion_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    result = await db.execute(
        select(MensajeChat)
        .where(MensajeChat.usuario_id == usuario.id, MensajeChat.sesion_chat_id == sesion_id)
        .order_by(MensajeChat.creado_en.asc())
    )
    mensajes = result.scalars().all()
    return {"sesion_id": sesion_id, "mensajes": mensajes}


@router.get("/sesiones", response_model=list)
async def listar_sesiones(
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    result = await db.execute(
        select(
            MensajeChat.sesion_chat_id,
            func.min(MensajeChat.creado_en).label("inicio"),
            func.max(MensajeChat.creado_en).label("ultimo_mensaje"),
            func.count(MensajeChat.id).label("total_mensajes"),
        )
        .where(MensajeChat.usuario_id == usuario.id)
        .group_by(MensajeChat.sesion_chat_id)
        .order_by(func.max(MensajeChat.creado_en).desc())
        .limit(20)
    )
    return [
        {"sesion_id": r.sesion_chat_id, "inicio": r.inicio,
         "ultimo_mensaje": r.ultimo_mensaje, "total_mensajes": r.total_mensajes}
        for r in result.all()
    ]


async def _llamar_ia(mensajes: list) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return _fallback(mensajes[-1]["content"] if mensajes else "")

    try:
        # 1. Inicializamos el NUEVO cliente oficial de Google
        client = genai.Client(api_key=api_key)

        # 2. Traducimos tu historial al formato de la nueva librería
        historial = []
        for msg in mensajes:
            rol = "model" if msg["role"] == "assistant" else "user"
            historial.append({
                "role": rol,
                "parts": [{"text": msg["content"]}]
            })

        # 3. Disparamos la petición asíncrona (.aio) al modelo nuevecito
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=historial,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            )
        )
        
        return response.text
            
    except Exception as e:
        print(f"🚨 ERROR CON GOOGLE GENAI (EL NUEVO): {e}")
        return "Estoy teniendo dificultades técnicas. Si necesitas ayuda urgente llama a SAPTEL: 800 290 0024 (24hrs)."
    
        

def _fallback(msg: str) -> str:
    lower = msg.lower()
    if any(w in lower for w in ["suicid", "matarme", "no quiero vivir", "hacerme daño", "sobredosis", "lastimarme", "quitarme la vida", "cortarme", "ahorcarme", "veneno", "dormir para siempre"]):
        return "Gracias por confiar en mí. Llama AHORA a SAPTEL: 800 290 0024 (24hrs). No estás solo/a. 💙"
    if any(w in lower for w in ["ansios", "pánico", "angustia", "nervios", "estres", "preocup", "agobio", "sobrecarg"]):
        return "Prueba respiración 4-7-8: inhala 4s, retén 7s, exhala 8s. ¿Quieres que te guíe?"
    if any(w in lower for w in ["triste", "solo", "llorar", "mal", "deprim", "decai", "pesim", "desanim", "desesper", "sin ganas"]):
        return "Está bien no estar bien. ¿Quieres contarme más sobre lo que sientes? Estoy aquí. 💙"
    return "Hola, soy KAI 👋 ¿Cómo te sientes hoy?"
