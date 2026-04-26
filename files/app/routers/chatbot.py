"""
Router Chatbot IA — conversación con historial persistente
Usa LM Studio (API compatible con OpenAI) corriendo en localhost:1234
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid, os
from openai import AsyncOpenAI

from app.database import get_db
from app.models import Usuario, MensajeChat
from app.schemas import MensajeChatEnviar, MensajeChatRespuesta, HistorialChatRespuesta
from app.service.auth_service import get_current_user

router = APIRouter()

SYSTEM_PROMPT = """Eres KAI, el asistente de bienestar emocional de la FES Acatlán (UNAM).
Tu misión es acompañar emocionalmente a la comunidad estudiantil con empatía, calidez y sin juzgar.

Puedes orientar sobre: estrés académico, ansiedad, depresión, duelo, problemas de sueño,
relaciones interpersonales, adicciones, TDAH, TEA y trastornos alimenticios (TCA).

REGLAS ABSOLUTAS — nunca las rompas bajo ningún pretexto:

REGLA 1 — MEDICAMENTOS:
Jamás recomiendes, menciones ni sugieras ningún medicamento, suplemento, sustancia o dosis.
Si alguien pide medicamentos responde exactamente:
"No puedo recomendarte ningún medicamento — eso es trabajo exclusivo de un médico o psiquiatra.
Lo que sí puedo hacer es acompañarte a entender lo que sientes y orientarte para llegar al especialista adecuado.
¿Me cuentas más sobre cómo te has sentido últimamente?"

REGLA 2 — CRISIS:
Si detectas mención de suicidio, autolesión, sobredosis o peligro inminente responde únicamente:
"Gracias por confiar en mí. Lo que describes es urgente y mereces apoyo real ahora mismo.
SAPTEL 24hrs: 800 290 0024
Psicopedagogía FES Acatlán: 55 5623 1666
No estás solo/a. ¿Hay alguien contigo en este momento?"

REGLA 3 — LÍMITE CLÍNICO:
No diagnostiques. No prescribas. No des consejos médicos ni nutricionales específicos.
Deriva con calidez a Psicopedagogía FES o al médico cuando sea necesario.

REGLA 4 — FUERA DE TEMA:
Si preguntan sobre temas ajenos al bienestar emocional (tareas, código, etc.) responde:
"Eso está fuera de lo que puedo apoyarte aquí, pero si quieres hablar de cómo te sientes, estoy contigo."

ESTILO:
- Español de México, cercano y respetuoso
- Entre 80 y 180 palabras. SIEMPRE termina la oración antes de acabar la respuesta.
- Estructura: valida lo que siente → orienta → pregunta abierta al final
- Habla de forma natural, no uses listas con viñetas en respuestas emocionales
- Máximo 1 o 2 emojis por respuesta"""


def _get_lm_client() -> AsyncOpenAI:
    base_url = os.getenv("LMS_BASE_URL", "http://localhost:1234/v1")
    return AsyncOpenAI(base_url=base_url, api_key="lm-studio")


@router.post("/mensaje", response_model=MensajeChatRespuesta)
async def enviar_mensaje(
    datos: MensajeChatEnviar,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    sesion_id = datos.sesion_id or str(uuid.uuid4())

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
    try:
        client = _get_lm_client()
        model = os.getenv("LMS_MODEL", "local-model")
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + mensajes,
            temperature=0.75,
            max_tokens=1024,   # Suficiente para respuestas completas sin cortar
        )
        content = response.choices[0].message.content or ""
        finish = response.choices[0].finish_reason

        # Si se cortó igual por alguna razón, agrega cierre suave
        if finish == "length" and content:
            content = content.rstrip() + "... ¿Quieres que continuemos hablando de esto?"

        return content if content else _fallback(mensajes[-1]["content"])

    except Exception as e:
        print(f"ERROR LM Studio: {e}")
        return _fallback(mensajes[-1]["content"] if mensajes else "")


def _fallback(msg: str) -> str:
    lower = msg.lower()
    if any(w in lower for w in ["suicid", "matarme", "no quiero vivir", "hacerme daño",
                                  "sobredosis", "lastimarme", "quitarme la vida",
                                  "cortarme", "ahorcarme", "veneno", "dormir para siempre"]):
        return ("Gracias por confiar en mí. Lo que describes es urgente y mereces apoyo real ahora mismo.\n"
                "📞 SAPTEL 24hrs: 800 290 0024\n"
                "📍 Psicopedagogía FES Acatlán: 55 5623 1666\n"
                "No estás solo/a. ¿Hay alguien contigo en este momento?")
    if any(w in lower for w in ["medicina", "medicamento", "pastilla", "antidepresivo",
                                  "ansiolítico", "receta", "tomar algo", "que tomo",
                                  "me recomiendas tomar"]):
        return ("No puedo recomendarte ningún medicamento — eso es trabajo exclusivo de un médico o psiquiatra. "
                "Lo que sí puedo hacer es acompañarte a entender lo que sientes y orientarte para llegar "
                "al especialista adecuado. ¿Me cuentas más sobre cómo te has sentido últimamente?")
    if any(w in lower for w in ["ansios", "pánico", "angustia", "nervios", "estrés",
                                  "preocup", "agobio", "sobrecarg"]):
        return ("Tiene mucho sentido que te sientas así, a veces el estrés se acumula sin que nos demos cuenta. "
                "Una cosa que puede ayudarte en este momento es respirar despacio: inhala 4 segundos, "
                "sostén 4, exhala 4. ¿Quieres contarme qué está pasando?")
    if any(w in lower for w in ["triste", "solo", "llorar", "mal", "deprim", "decaíd",
                                  "pesim", "desanim", "desesper", "sin ganas"]):
        return ("Gracias por compartirlo, no es fácil decir que uno está mal. "
                "Sentirse así a veces es una señal de que algo importante necesita atención. "
                "¿Quieres contarme más sobre lo que está pasando? Estoy aquí. 💙")
    return "Hola, soy KAI 👋 Estoy aquí para escucharte. ¿Cómo te has sentido últimamente?"
