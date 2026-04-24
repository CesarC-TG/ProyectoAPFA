"""
Router de Autenticación — registro, login (email/teléfono), OAuth, refresh, logout, recuperar contraseña
"""
import random

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
import secrets, string
from app.models import VerificacionRegistro  

from app.database import get_db
from app.models import Usuario, SesionUsuario, RolUsuario
from app.schemas import (
    UsuarioCrear, LoginRequest, LoginTelefonoRequest,
    GoogleAuthRequest, PasswordResetRequest, PasswordResetEmailRequest,
    TokenResponse, RefreshTokenRequest, MensajeRespuesta, UsuarioRespuesta,
    SolicitarVerificacionRequest, VerificarCodigoRequest,
)
from app.service.auth_service import (
    hashear_password, verificar_password,
    crear_access_token, crear_refresh_token, decodificar_token,
    verificar_google_token, login_o_registro_google,
    get_current_user,
    verificar_bloqueo, registrar_intento_fallido, limpiar_intentos_fallidos,
    _emitir_tokens_y_sesion,
)
from app.config import settings
from app.service.notificacion_service import enviar_email

router = APIRouter()


# ── Registro con email/contraseña ──────────────────────────

@router.post("/registro", response_model=TokenResponse, status_code=201)
async def registrar_usuario(
    datos: UsuarioCrear,
    db: AsyncSession = Depends(get_db),
):
    # Verificar email único
    result = await db.execute(select(Usuario).where(Usuario.email == datos.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El correo ya está registrado.")

    # Verificar teléfono único si se proporcionó
    if datos.telefono:
        res_tel = await db.execute(select(Usuario).where(Usuario.telefono == datos.telefono))
        if res_tel.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="El número de teléfono ya está registrado.")

    nuevo_usuario = Usuario(
        nombre        = datos.nombre,
        apellidos     = getattr(datos, 'apellidos', None),
        email         = datos.email,
        telefono      = datos.telefono,
        carrera       = datos.carrera,
        semestre      = datos.semestre,
        password_hash = hashear_password(datos.password) if datos.password else None,
        rol           = RolUsuario.ESTUDIANTE,
    )
    db.add(nuevo_usuario)
    await db.commit()
    await db.refresh(nuevo_usuario)

    return await _emitir_tokens_y_sesion(nuevo_usuario, db, {})


# ── Login con email/contraseña ─────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    datos: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Usuario).where(Usuario.email == datos.email))
    usuario = result.scalar_one_or_none()

    if not usuario or not usuario.password_hash:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    await verificar_bloqueo(usuario)

    if not verificar_password(datos.password, usuario.password_hash):
        await registrar_intento_fallido(usuario, db)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not usuario.activo:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    await limpiar_intentos_fallidos(usuario, db)

    request_info = {
        "user_agent": request.headers.get("user-agent"),
        "ip": request.client.host if request.client else None,
    }
    return await _emitir_tokens_y_sesion(usuario, db, request_info)


# ── Login con número de teléfono ───────────────────────────

@router.post("/login-telefono", response_model=TokenResponse)
async def login_telefono(
    datos: LoginTelefonoRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Login usando número de teléfono + contraseña."""
    tel = datos.telefono.strip().replace(" ", "").replace("-", "")
    result = await db.execute(select(Usuario).where(Usuario.telefono == tel))
    usuario = result.scalar_one_or_none()

    if not usuario or not usuario.password_hash:
        raise HTTPException(status_code=401, detail="Número de teléfono o contraseña inválidos")

    await verificar_bloqueo(usuario)

    if not verificar_password(datos.password, usuario.password_hash):
        await registrar_intento_fallido(usuario, db)
        raise HTTPException(status_code=401, detail="Número de teléfono o contraseña inválidos")

    if not usuario.activo:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    await limpiar_intentos_fallidos(usuario, db)

    return await _emitir_tokens_y_sesion(usuario, db, {
        "user_agent": request.headers.get("user-agent"),
        "ip": request.client.host if request.client else None,
    })


# ── Recuperar contraseña por teléfono ─────────────────────

@router.post("/recuperar-password", response_model=MensajeRespuesta)
async def recuperar_password(
    datos: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Genera contraseña temporal buscando por EMAIL o TELÉFONO.
    Acepta: { "email": "..." } o { "telefono": "..." }
    En desarrollo devuelve la nueva contraseña en el mensaje para facilitar las pruebas.
    En producción conectar con proveedor de email/SMS.
    """
    usuario = None

    # Buscar por email primero
    if datos.email:
        result = await db.execute(
            select(Usuario).where(Usuario.email == datos.email.strip().lower())
        )
        usuario = result.scalar_one_or_none()

    # Si no, buscar por teléfono
    elif datos.telefono:
        tel = datos.telefono.strip().replace(" ", "").replace("-", "")
        result = await db.execute(select(Usuario).where(Usuario.telefono == tel))
        usuario = result.scalar_one_or_none()

    # Respuesta genérica siempre (no filtrar si existe o no)
    if not usuario:
        return {"mensaje": "Si los datos están registrados, recibirás tu contraseña temporal."}

    # Generar contraseña temporal legible (letras + dígitos, sin confusibles)
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    nueva_pass = ''.join(secrets.choice(alphabet) for _ in range(8))

    usuario.password_hash = hashear_password(nueva_pass)
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta   = None
    await db.commit()

    # TODO producción: enviar email real con smtplib/sendgrid o SMS con Twilio
    # send_email(usuario.email, f"Tu contraseña temporal KAI: {nueva_pass}")

    # Enviar email con la contraseña temporal
    email_enviado = False
    try:
        html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px;background:#f8f7f4">
  <div style="background:#276266;border-radius:12px;padding:20px;text-align:center;margin-bottom:20px">
    <h2 style="color:#fff;margin:0">🔑 Contraseña temporal</h2>
    <p style="color:rgba(255,255,255,.8);margin:6px 0 0;font-size:13px">KAI · ApoYo FES Acatlán</p>
  </div>
  <p style="color:#555">Hola <strong>{usuario.nombre}</strong>,</p>
  <p style="color:#555">Solicitaste recuperar tu contraseña.</p>
  <div style="background:#fff;border-radius:10px;padding:20px;text-align:center;margin:20px 0;border:2px dashed #276266">
    <p style="margin:0;font-size:12px;color:#888">Tu nueva contraseña temporal:</p>
    <p style="font-size:30px;font-weight:700;color:#276266;letter-spacing:4px;margin:10px 0">{nueva_pass}</p>
  </div>
  <p style="color:#555;font-size:13px">Inicia sesión con esta contraseña y cámbiala desde tu perfil.</p>
  <hr style="border:none;border-top:1px solid #eee;margin:20px 0"/>
  <p style="color:#aaa;font-size:11px">Si no solicitaste este cambio, ignora este correo.<br/>Equipo KAI · FES Acatlán, UNAM</p>
</div>"""
        txt = f"Hola {usuario.nombre},Tu contraseña temporal para KAI es: {nueva_pass}Ingresa y cámbiala desde tu perfil.— Equipo KAI FES Acatlán"
        await enviar_email(
            destinatario=usuario.email,
            asunto="🔑 Tu contraseña temporal — KAI FES Acatlán",
            cuerpo=txt,
            html=html,
        )
        email_enviado = True
    except Exception as e:
        print(f"[WARN] Email no enviado a {usuario.email}: {e}")

    if email_enviado:
        return {"mensaje": f"✅ Te enviamos una contraseña temporal a {usuario.email}. Revisa tu bandeja (y spam)."}
    else:
        # Fallback visible para desarrollo si SMTP no está configurado
        via = f"correo {usuario.email}" if datos.email else "teléfono registrado"
        return {"mensaje": f"✅ Contraseña generada para {via}. [Configura SMTP en .env para envío automático] Contraseña temporal: {nueva_pass}"}


# ── Google OAuth ───────────────────────────────────────────

@router.post("/google", response_model=TokenResponse)
async def login_google(
    datos: GoogleAuthRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    google_data = await verificar_google_token(datos.token)
    return await login_o_registro_google(google_data, db, {
        "user_agent": request.headers.get("user-agent"),
        "ip": request.client.host if request.client else None,
    })


# ── Refresh de tokens ──────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refrescar_token(
    datos: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = decodificar_token(datos.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    result = await db.execute(
        select(SesionUsuario).where(
            SesionUsuario.refresh_token == datos.refresh_token,
            SesionUsuario.activa == True,
        )
    )
    sesion = result.scalar_one_or_none()
    if not sesion:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")

    usuario = await db.get(Usuario, sesion.usuario_id)
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario inactivo")

    nuevo_access  = crear_access_token({"sub": usuario.id, "rol": usuario.rol})
    nuevo_refresh = crear_refresh_token(usuario.id)

    sesion.refresh_token = nuevo_refresh
    sesion.ip_address    = request.client.host if request.client else None
    await db.commit()

    return {
        "access_token":  nuevo_access,
        "refresh_token": nuevo_refresh,
        "token_type":    "bearer",
        "expires_in":    settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "usuario":       usuario,
    }


# ── Logout ─────────────────────────────────────────────────

@router.post("/logout", response_model=MensajeRespuesta)
async def cerrar_sesion(
    datos: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    result = await db.execute(
        select(SesionUsuario).where(
            SesionUsuario.refresh_token == datos.refresh_token,
            SesionUsuario.usuario_id == usuario.id,
        )
    )
    sesion = result.scalar_one_or_none()
    if sesion:
        sesion.activa = False
        await db.commit()
    return {"mensaje": "Sesión cerrada correctamente"}


@router.post("/logout-all", response_model=MensajeRespuesta)
async def cerrar_todas_sesiones(
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    result = await db.execute(
        select(SesionUsuario).where(
            SesionUsuario.usuario_id == usuario.id,
            SesionUsuario.activa == True,
        )
    )
    sesiones = result.scalars().all()
    for s in sesiones:
        s.activa = False
    await db.commit()
    return {"mensaje": f"{len(sesiones)} sesión(es) cerrada(s)"}


# ── Perfil del usuario actual ──────────────────────────────

@router.get("/me", response_model=UsuarioRespuesta)
async def obtener_mi_perfil(usuario: Usuario = Depends(get_current_user)):
    return usuario

# ── Solicitar verificación por email ──────────────────────

from sqlalchemy import update

@router.post("/solicitar-verificacion", response_model=MensajeRespuesta)
async def solicitar_verificacion(
    datos: SolicitarVerificacionRequest,
    db:    AsyncSession = Depends(get_db),
):
    """
    Genera un código de 6 dígitos, lo guarda en BD con TTL de 10 min
    y lo envía por email usando Resend.
    """
    email = datos.email.strip().lower()

    if not email.endswith('@pcpuma.acatlan.unam.mx'):
        raise HTTPException(status_code=400, detail="Solo se aceptan correos @pcpuma.acatlan.unam.mx")

    result = await db.execute(select(Usuario).where(Usuario.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Este correo ya tiene una cuenta registrada.")

    # Invalidar códigos previos del mismo email
    await db.execute(
        update(VerificacionRegistro)
        .where(VerificacionRegistro.email == email, VerificacionRegistro.usado == False)
        .values(usado=True)
    )

    codigo = str(random.randint(100000, 999999))

    verif = VerificacionRegistro(
        email     = email,
        codigo    = codigo,
        expira_en = datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(verif)
    await db.commit()

    html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px;background:#f8f7f4">
  <div style="background:#276266;border-radius:12px;padding:20px;text-align:center;margin-bottom:20px">
    <h2 style="color:#fff;margin:0">Verificación de cuenta</h2>
    <p style="color:rgba(255,255,255,.8);margin:6px 0 0;font-size:13px">APFA · FES Acatlán</p>
  </div>
  <p style="color:#555">Hola <strong>{datos.nombre}</strong>,</p>
  <p style="color:#555">Tu código de verificación para crear tu cuenta es:</p>
  <div style="background:#fff;border-radius:10px;padding:20px;text-align:center;margin:20px 0;border:2px dashed #276266">
    <p style="font-size:38px;font-weight:700;color:#276266;letter-spacing:8px;margin:0">{codigo}</p>
    <p style="margin:8px 0 0;font-size:12px;color:#888">Válido por 10 minutos</p>
  </div>
  <p style="color:#555;font-size:13px">Si no solicitaste este código, ignora este mensaje.</p>
  <hr style="border:none;border-top:1px solid #eee;margin:20px 0"/>
  <p style="color:#aaa;font-size:11px">Equipo APFA · FES Acatlán, UNAM</p>
</div>"""

    try:
        await enviar_email(
            destinatario=email,
            asunto="Tu código de verificación — APFA FES Acatlán",
            cuerpo=f"Hola {datos.nombre}, tu código de verificación es: {codigo}. Válido por 10 minutos.",
            html=html,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo enviar el correo: {e}")

    return {"mensaje": f"Código enviado a {email}. Revisa tu bandeja de entrada (y spam)."}


# ── Verificar código ───────────────────────────────────────

@router.post("/verificar-codigo", response_model=MensajeRespuesta)
async def verificar_codigo(
    datos: VerificarCodigoRequest,
    db:    AsyncSession = Depends(get_db),
):
    """Valida que el código de 6 dígitos sea correcto y no haya expirado."""
    email  = datos.email.strip().lower()
    codigo = datos.codigo.strip()

    result = await db.execute(
        select(VerificacionRegistro)
        .where(
            VerificacionRegistro.email  == email,
            VerificacionRegistro.codigo == codigo,
            VerificacionRegistro.usado  == False,
        )
        .order_by(VerificacionRegistro.creado_en.desc())
        .limit(1)
    )
    verif = result.scalar_one_or_none()

    if not verif:
        raise HTTPException(status_code=400, detail="Código incorrecto. Verifica e intenta de nuevo.")

    ahora = datetime.now(timezone.utc)
    expira = verif.expira_en if verif.expira_en.tzinfo else verif.expira_en.replace(tzinfo=timezone.utc)
    if ahora > expira:
        verif.usado = True
        await db.commit()
        raise HTTPException(status_code=400, detail="El código ha expirado. Solicita uno nuevo.")

    verif.usado = True
    await db.commit()

    return {"mensaje": "Código verificado correctamente."}