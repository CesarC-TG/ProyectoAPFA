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


def _generar_link_gcal(
    fecha_hora,
    duracion_min: int,
    titulo: str,
    descripcion: str,
    ubicacion: str,
) -> str:
    from datetime import timezone, timedelta
    from urllib.parse import quote
    if fecha_hora.tzinfo is None:
        fecha_hora = fecha_hora.replace(tzinfo=timezone.utc)
    fin = fecha_hora + timedelta(minutes=duracion_min)
    fmt = "%Y%m%dT%H%M%SZ"
    inicio_str = fecha_hora.astimezone(timezone.utc).strftime(fmt)
    fin_str    = fin.astimezone(timezone.utc).strftime(fmt)
    params = (
        f"action=TEMPLATE"
        f"&text={quote(titulo)}"
        f"&dates={inicio_str}/{fin_str}"
        f"&details={quote(descripcion)}"
        f"&location={quote(ubicacion)}"
    )
    return f"https://calendar.google.com/calendar/render?{params}"


async def enviar_email_cita(
    *,
    estudiante_email: str,
    estudiante_nombre: str,
    psicologo_email: str,
    psicologo_nombre: str,
    fecha_hora,           # datetime
    duracion_min: int,
    modalidad: str,
    motivo: str,
    tipo: str = "nueva",  # "nueva" | "confirmada"
) -> None:
    """
    Envía correo de notificación de cita a estudiante y psicólogo.
    Incluye link pre-rellenado de Google Calendar.
    Ejecutar como background task para no bloquear la respuesta HTTP.
    """
    from datetime import timezone

    if fecha_hora.tzinfo is None:
        fecha_hora = fecha_hora.replace(tzinfo=timezone.utc)

    _DIAS  = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    _MESES = ["enero","febrero","marzo","abril","mayo","junio",
              "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    fecha_str = f"{_DIAS[fecha_hora.weekday()]} {fecha_hora.day} de {_MESES[fecha_hora.month-1]} de {fecha_hora.year}"
    hora_str  = fecha_hora.strftime("%H:%M")
    modal_str = "Videollamada 📹" if modalidad == "videollamada" else "Presencial 🏛"
    ubicacion = "Videollamada" if modalidad == "videollamada" else "FES Acatlán, Edificio D, Planta Baja"

    titulo_gcal = "Cita de orientación — KAI FES Acatlán"
    desc_gcal = (
        f"Cita de orientación psicológica\n"
        f"Modalidad: {modalidad}\n"
        f"Psicólogo/a: {psicologo_nombre}\n"
        f"Estudiante: {estudiante_nombre}\n"
        f"{('Motivo: ' + motivo) if motivo else ''}"
    ).strip()

    gcal_link = _generar_link_gcal(fecha_hora, duracion_min, titulo_gcal, desc_gcal, ubicacion)

    encabezado = "✅ Cita confirmada" if tipo == "confirmada" else "📅 Nueva cita programada"
    color_header = "#276266"

    def _html(nombre_dest: str, otro_nombre: str, rol_otro: str) -> str:
        return f"""
<!DOCTYPE html><html lang="es"><body style="margin:0;padding:0;background:#F8F7F4;font-family:'DM Sans',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">
  <tr><td style="background:{color_header};padding:28px 32px;text-align:center">
    <p style="margin:0;color:#fff;font-size:22px;font-weight:700">{encabezado}</p>
    <p style="margin:8px 0 0;color:rgba(255,255,255,.8);font-size:14px">KAI — ApoYo FES Acatlán</p>
  </td></tr>
  <tr><td style="padding:28px 32px">
    <p style="margin:0 0 6px;color:#2F3E46;font-size:15px">Hola, <strong>{nombre_dest}</strong> 👋</p>
    <p style="margin:0 0 24px;color:#7A8B94;font-size:14px;line-height:1.6">
      {"Tu cita ha sido confirmada." if tipo == "confirmada" else "Se ha agendado una nueva cita."} Aquí están los detalles:
    </p>
    <table width="100%" cellpadding="0" cellspacing="0"
      style="background:#F8F7F4;border-radius:12px;padding:20px;margin-bottom:24px">
      <tr><td style="padding:6px 0">
        <span style="font-size:12px;color:#7A8B94;text-transform:uppercase;letter-spacing:.06em">Fecha</span>
        <p style="margin:2px 0 0;font-size:15px;font-weight:600;color:#2F3E46">📅 {fecha_str}</p>
      </td></tr>
      <tr><td style="padding:6px 0">
        <span style="font-size:12px;color:#7A8B94;text-transform:uppercase;letter-spacing:.06em">Hora</span>
        <p style="margin:2px 0 0;font-size:15px;font-weight:600;color:#2F3E46">🕐 {hora_str} hrs · {duracion_min} min</p>
      </td></tr>
      <tr><td style="padding:6px 0">
        <span style="font-size:12px;color:#7A8B94;text-transform:uppercase;letter-spacing:.06em">Modalidad</span>
        <p style="margin:2px 0 0;font-size:15px;font-weight:600;color:#2F3E46">{modal_str}</p>
      </td></tr>
      <tr><td style="padding:6px 0">
        <span style="font-size:12px;color:#7A8B94;text-transform:uppercase;letter-spacing:.06em">{rol_otro}</span>
        <p style="margin:2px 0 0;font-size:15px;font-weight:600;color:#2F3E46">👤 {otro_nombre}</p>
      </td></tr>
      {f'<tr><td style="padding:6px 0"><span style="font-size:12px;color:#7A8B94;text-transform:uppercase;letter-spacing:.06em">Motivo</span><p style="margin:2px 0 0;font-size:14px;color:#2F3E46">{motivo}</p></td></tr>' if motivo else ''}
    </table>
    <div style="text-align:center;margin-bottom:24px">
      <a href="{gcal_link}" target="_blank"
        style="display:inline-block;background:#276266;color:#fff;padding:13px 28px;
               border-radius:50px;font-size:14px;font-weight:700;text-decoration:none;
               box-shadow:0 4px 12px rgba(39,98,102,.3)">
        📆 Agregar a Google Calendar
      </a>
    </div>
    <p style="margin:0;font-size:12px;color:#7A8B94;text-align:center;line-height:1.6">
      Si necesitas cancelar o reagendar, hazlo desde la app KAI.<br>
      Psicopedagogía FES Acatlán · Edificio D, PB · 55 5623 1666
    </p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""

    texto_plano = (
        f"{encabezado}\n\n"
        f"Fecha: {fecha_str} a las {hora_str} hrs\n"
        f"Modalidad: {modal_str}\n"
        f"Psicólogo/a: {psicologo_nombre}\n"
        f"Estudiante: {estudiante_nombre}\n"
        f"{('Motivo: ' + motivo + chr(10)) if motivo else ''}"
        f"\nAgrega al calendario:\n{gcal_link}\n\n"
        f"KAI — ApoYo FES Acatlán"
    )

    if not (settings.SMTP_USER and settings.SMTP_PASSWORD):
        return

    asunto = f"{encabezado} — {fecha_str} {hora_str} hrs"
    for email_dest, nombre_dest, otro_nombre, rol_otro in [
        (estudiante_email, estudiante_nombre, psicologo_nombre, "Psicólogo/a"),
        (psicologo_email,  psicologo_nombre,  estudiante_nombre, "Estudiante"),
    ]:
        try:
            await enviar_email(
                destinatario=email_dest,
                asunto=asunto,
                cuerpo=texto_plano,
                html=_html(nombre_dest, otro_nombre, rol_otro),
            )
        except Exception as e:
            print(f"Error enviando email de cita a {email_dest}: {e}")


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
