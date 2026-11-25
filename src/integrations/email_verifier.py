"""Servicio SMTP para envío seguro de códigos de verificación por correo electrónico."""

import html
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger("email_verifier")

APP_BASE_URL = "https://sistemap2pmerchant.com"
APP_LOGO_URL = f"{APP_BASE_URL}/logo-120.png"


class EmailVerificationService:
    """Envía códigos OTP de 6 dígitos mediante servidor SMTP (Resend / Gmail / Relay)."""

    def __init__(self, settings: Any):
        self.host = str(getattr(settings, "SMTP_HOST", "smtp.gmail.com") or "smtp.gmail.com").strip()
        try:
            self.port = int(getattr(settings, "SMTP_PORT", 587) or 587)
        except (ValueError, TypeError):
            self.port = 587
        self.user = str(getattr(settings, "SMTP_USER", "") or "").strip()
        self.password = str(getattr(settings, "SMTP_PASSWORD", "") or "").strip()
        self.from_email = str(getattr(settings, "SMTP_FROM_EMAIL", "") or "").strip() or self.user
        self.use_tls = bool(getattr(settings, "SMTP_USE_TLS", True))

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    @staticmethod
    def render_otp_html(code: str, purpose: str = "register") -> str:
        """Renderiza la plantilla HTML responsiva estilo Comerciante P2P (Obsidian + Ámbar)."""
        safe_code = html.escape(code.strip())
        is_recovery = purpose == "recovery"
        eyebrow = "RECUPERACIÓN DE ACCESO" if is_recovery else "VERIFICACIÓN DE CUENTA"
        headline = (
            "Restablece tu contraseña" if is_recovery else "Confirma tu correo electrónico"
        )
        intro = (
            "Recibimos una solicitud para restablecer el acceso a tu cuenta en Comerciante P2P. "
            "Ingresa este código de seguridad en la pantalla de recuperación:"
            if is_recovery
            else "Estás a un paso de activar tu perfil en Comerciante P2P. "
            "Ingresa este código de 6 dígitos en la pantalla de registro:"
        )
        cta_label = "Volver a recuperación" if is_recovery else "Abrir Comerciante P2P"
        cta_url = f"{APP_BASE_URL}/login" if is_recovery else APP_BASE_URL

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{headline} — Comerciante P2P</title>
</head>
<body style="margin:0;padding:0;background-color:#0b0e14;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
  <!-- Preheader invisible para vista previa en bandeja -->
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">
    Tu código de seguridad es {safe_code}. Válido por 15 minutos en Comerciante P2P.
  </div>

  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#0b0e14;padding:28px 12px;">
    <tr>
      <td align="center" valign="top">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;border-collapse:separate;border-spacing:0;background-color:#111620;border:1px solid #1e2430;border-radius:16px;overflow:hidden;">

          <!-- HERO OSCURO (Estilo Obsidian + Ámbar) -->
          <tr>
            <td align="center" style="background-color:#0d1118;padding:36px 28px 32px 28px;border-bottom:2px solid #f59e0b;">
              <img src="{APP_LOGO_URL}" width="64" height="64" alt="Comerciante P2P" style="display:block;width:64px;height:64px;border-radius:14px;border:1px solid #1e2430;margin:0 auto 16px auto;" />
              <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#f59e0b;margin:0 0 8px 0;">
                {eyebrow}
              </div>
              <h1 style="margin:0 0 12px 0;font-size:26px;line-height:1.25;font-weight:700;color:#ffffff;">
                {headline}
              </h1>
              <p style="margin:0 auto 24px auto;max-width:460px;font-size:14px;line-height:1.6;color:#cbd5e1;">
                {intro}
              </p>

              <!-- CAJA PROTAGONISTA DEL CÓDIGO OTP -->
              <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin:0 auto 20px auto;">
                <tr>
                  <td align="center" style="background-color:#0b0e14;border:1.5px solid #f59e0b;border-radius:12px;padding:18px 34px;">
                    <span style="font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;font-size:34px;font-weight:800;letter-spacing:10px;color:#ffffff;display:inline-block;padding-left:10px;">
                      {safe_code}
                    </span>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 24px 0;font-size:12px;color:#94a3b8;">
                Este código es de un solo uso y expira en <strong style="color:#f8fafc;">15 minutos</strong>.
              </p>

              <!-- BOTÓN PILL CTA -->
              <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center">
                <tr>
                  <td align="center" style="background-color:#f59e0b;border-radius:999px;">
                    <a href="{cta_url}" target="_blank" rel="noopener noreferrer" style="display:inline-block;padding:12px 28px;font-size:13px;font-weight:700;color:#0b0e14;text-decoration:none;letter-spacing:0.3px;">
                      {cta_label}
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- BANDA DE 3 PILARES DE SEGURIDAD (Inspirada en el layout modular) -->
          <tr>
            <td style="background-color:#141a26;padding:24px 20px;border-bottom:1px solid #1e2430;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td width="33.33%" align="center" valign="top" style="padding:6px 8px;">
                    <div style="font-size:18px;line-height:1;margin-bottom:8px;">&#128274;</div>
                    <div style="font-size:12px;font-weight:700;color:#f8fafc;margin-bottom:4px;">Código cifrado</div>
                    <div style="font-size:11px;line-height:1.45;color:#94a3b8;">Validación HMAC segura y bloqueo anti-fuerza bruta.</div>
                  </td>
                  <td width="33.33%" align="center" valign="top" style="padding:6px 8px;">
                    <div style="font-size:18px;line-height:1;margin-bottom:8px;">&#9201;</div>
                    <div style="font-size:12px;font-weight:700;color:#f8fafc;margin-bottom:4px;">Vigencia 15 min</div>
                    <div style="font-size:11px;line-height:1.45;color:#94a3b8;">Se invalida automáticamente al usarlo o vencer.</div>
                  </td>
                  <td width="33.33%" align="center" valign="top" style="padding:6px 8px;">
                    <div style="font-size:18px;line-height:1;margin-bottom:8px;">&#128737;</div>
                    <div style="font-size:12px;font-weight:700;color:#f8fafc;margin-bottom:4px;">Uso personal</div>
                    <div style="font-size:11px;line-height:1.45;color:#94a3b8;">Nunca compartas este código con terceros ni soporte.</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- AVISO DE SEGURIDAD Y PIE -->
          <tr>
            <td align="center" style="background-color:#0f141d;padding:20px 28px 24px 28px;">
              <p style="margin:0 0 12px 0;font-size:12px;line-height:1.55;color:#94a3b8;">
                Si no solicitaste este código, puedes ignorar este mensaje de forma segura; tu cuenta permanece protegida.
              </p>
              <p style="margin:0;font-size:11px;color:#64748b;">
                &copy; 2026 <strong style="color:#cbd5e1;">Comerciante P2P</strong> &middot;
                <a href="{APP_BASE_URL}" style="color:#f59e0b;text-decoration:none;">sistemap2pmerchant.com</a> &middot;
                <a href="{APP_BASE_URL}/privacy" style="color:#94a3b8;text-decoration:underline;">Privacidad</a> &middot;
                <a href="{APP_BASE_URL}/terms" style="color:#94a3b8;text-decoration:underline;">Condiciones</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    def send_verification_code(
        self,
        to_email: str,
        code: str,
        purpose: str = "register",
    ) -> tuple[bool, str | None]:
        """Despacha el código de verificación SMTP de 6 dígitos sin exponer credenciales en logs."""
        if not self.is_configured:
            return False, "Credenciales SMTP no configuradas en el servidor."

        is_recovery = purpose == "recovery"
        from_header = (
            self.from_email
            if "<" in self.from_email
            else f"Comerciante P2P <{self.from_email}>"
        )
        subject = (
            f"Recuperación de acceso — Código {code}"
            if is_recovery
            else f"Comerciante P2P — Código de verificación: {code}"
        )

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_header
        msg["To"] = to_email
        msg.set_content(
            f"Comerciante P2P ({APP_BASE_URL})\n\n"
            f"Tu código de seguridad de 6 dígitos es: {code}\n\n"
            "Válido por 15 minutos. Nunca compartas este código con terceros.\n"
            "Si no realizaste esta solicitud, ignora este mensaje."
        )
        msg.add_alternative(
            self.render_otp_html(code=code, purpose=purpose),
            subtype="html",
        )

        context = ssl.create_default_context()
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=8.0, context=context) as server:
                    server.login(self.user, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=8.0) as server:
                    server.ehlo()
                    if self.use_tls:
                        server.starttls(context=context)
                        server.ehlo()
                    server.login(self.user, self.password)
                    server.send_message(msg)
            logger.info("SMTP: Código de verificación enviado correctamente a destino.")
            return True, None
        except smtplib.SMTPAuthenticationError:
            err = "Autenticación SMTP rechazada. Verifica SMTP_USER y App Password en config/.env."
            logger.warning("SMTP: Fallo de autenticación.")
            return False, err
        except (smtplib.SMTPException, OSError, TimeoutError) as err:
            err_msg = f"No se pudo conectar al servidor SMTP ({self.host}:{self.port}): {type(err).__name__}"
            logger.warning("SMTP: %s", err_msg)
            return False, err_msg
