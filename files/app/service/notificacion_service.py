"""
Servicio de notificaciones — Email + WebSocket push
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import asyncio

from app.config import settings


async def notificar_sos_a_admin(evento, usuario=None):
    nombre  = usuario.nombre if usuario else "Usuario anónimo"
    email   = usuario.email  if usuario else "No disponible"

    asunto = f"🆘 ALERTA SOS — {evento.tipo_accion.upper()} — {nombre}"
    cuerpo = f"""
ALERTA DE EMERGENCIA — ApoYo FES Acatlán
==========================================
Tipo:       {evento.tipo_accion}
Estudiante: {nombre}
Email:      {email}
Descripción:{evento.descripcion or 'No especificada'}
Fecha/Hora: {evento.creado_en}
IP:         {evento.ip_address or 'No disponible'}
{f'Ubicación: https://maps.google.com/?q={evento.latitud},{evento.longitud}' if evento.latitud else ''}
---
Panel: https://apoyofes.unam.mx/api/docs
    """

    if settings.SMTP_USER and settings.SMTP_PASSWORD:
        try:
            destinatario = getattr(settings, "ADMIN_ALERT_EMAIL", None) or settings.EMAIL_FROM
            await enviar_email(destinatario=destinatario, asunto=asunto, cuerpo=cuerpo)
        except Exception as e:
            print(f"Error enviando email SOS: {e}")

    try:
        from app.websocket import notificar_sos_en_vivo
        await notificar_sos_en_vivo({
            "evento_id": evento.id,
            "tipo": evento.tipo_accion,
            "usuario": nombre,
            "descripcion": evento.descripcion,
        })
    except Exception:
        pass


async def enviar_email(destinatario: str, asunto: str, cuerpo: str, html: Optional[str] = None):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    msg["To"]      = destinatario
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _enviar_smtp, msg, destinatario)


def _enviar_smtp(msg, destinatario: str):
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as srv:
        srv.starttls()
        srv.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        srv.sendmail(settings.EMAIL_FROM, destinatario, msg.as_string())


async def enviar_email_resend(destinatario: str, asunto: str, html: str, texto: str = ""):
    """Envía email usando Resend. Requiere RESEND_API_KEY en .env"""
    if not settings.RESEND_API_KEY:
        raise RuntimeError("Resend no configurado. Define RESEND_API_KEY en tu archivo .env")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _enviar_resend, destinatario, asunto, html, texto)


def _enviar_resend(destinatario: str, asunto: str, html: str, texto: str):
    import resend
    resend.api_key = settings.RESEND_API_KEY
    resend.Emails.send({
        "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
        "to": [destinatario],
        "subject": asunto,
        "html": html,
        "text": texto or asunto,
    })

async def notificar_contacto_emergencia(evento, usuario):
    """Notifica al contacto de emergencia del usuario cuando activa el botón SOS."""
    if not usuario:
        return
    nombre_emergencia = getattr(usuario, 'emergencia_nombre', None)
    email_emergencia  = getattr(usuario, 'emergencia_email',  None)
    tel_emergencia    = getattr(usuario, 'emergencia_telefono', None)

    if not email_emergencia and not tel_emergencia:
        return  # No hay contacto registrado

    asunto = f"⚠️ {usuario.nombre} necesita apoyo — ApoYo FES Acatlán"
    cuerpo = f"""Hola{' ' + nombre_emergencia if nombre_emergencia else ''},

{usuario.nombre} activó el botón SOS en la plataforma ApoYo FES Acatlán.

Esto puede significar que necesita apoyo emocional en este momento.
Por favor comunícate con {usuario.nombre} a la brevedad.

--- Información del evento ---
Tipo:       {evento.tipo_accion}
Fecha/Hora: {evento.creado_en}
Descripción: {evento.descripcion or 'No especificada'}

Si necesitas orientación profesional, contacta:
📞 SAPTEL 24hrs: 800 290 0024
📍 Psicopedagogía FES Acatlán: 55 5623 1666

Este mensaje fue enviado automáticamente por ApoYo FES Acatlán.
No respondas a este correo.
"""
    if settings.SMTP_USER and settings.SMTP_PASSWORD and email_emergencia:
        try:
            await enviar_email(
                destinatario=email_emergencia,
                asunto=asunto,
                cuerpo=cuerpo,
            )
        except Exception as e:
            print(f"Error notificando contacto emergencia: {e}")

    # Log SMS simulado (integrar con Twilio en producción)
    if tel_emergencia:
        import logging
        logging.getLogger("apoyofes").info(
            f"[SMS SIMULADO] SOS → {tel_emergencia} ({nombre_emergencia}): "
            f"{usuario.nombre} necesita apoyo."
        )


async def notificacion_inactividad(db_session, usuario):
    """
    Crea una notificación in-app de inactividad (2+ días sin entrar).
    Llamada desde el scheduler periódico.
    """
    from app.models import Notificacion
    import uuid

    notif = Notificacion(
        id         = str(uuid.uuid4()),
        usuario_id = usuario.id,
        titulo     = "¿Cómo te has sentido? 💙",
        mensaje    = (
            "Llevamos un par de días sin saber de ti. "
            "¿Todo bien? Si quieres, puedes escribir cómo te sientes en tu diario "
            "o chatear con KAI — estamos aquí cuando lo necesites. 🌿"
        ),
        tipo       = "recordatorio",
        leida      = False,
    )
    db_session.add(notif)
    await db_session.commit()
