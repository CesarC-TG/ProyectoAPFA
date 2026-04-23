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
