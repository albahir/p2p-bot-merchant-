"""Servicio SMTP para envío seguro de códigos de verificación por correo electrónico."""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger("email_verifier")


class EmailVerificationService:
    """Envía códigos OTP de 6 dígitos mediante servidor SMTP (Gmail / Outlook / Relay)."""

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

    def send_verification_code(self, to_email: str, code: str) -> tuple[bool, str | None]:
        """Despacha el código de verificación SMTP de 6 dígitos sin exponer credenciales en logs."""
        if not self.is_configured:
            return False, "Credenciales SMTP no configuradas en el servidor."

        msg = EmailMessage()
        msg["Subject"] = f"Código de verificación: {code}"
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg.set_content(
            f"Tu código de verificación es: {code}\n\n"
            "Válido por 15 minutos.\n"
            "Si no solicitaste este registro, ignora este mensaje."
        )
        msg.add_alternative(
            f"""
            <div style="font-family:Segoe UI,Arial,sans-serif;background:#0a0e13;color:#e2e8f0;padding:24px;border-radius:12px;">
              <h2 style="color:#f59e0b;margin:0 0 12px 0;">Verificación de correo</h2>
              <p style="margin:0 0 16px 0;font-size:14px;">Ingresa el siguiente código de 6 dígitos para confirmar tu correo:</p>
              <div style="font-family:monospace;font-size:28px;font-weight:700;letter-spacing:6px;color:#ffffff;background:#141920;padding:14px 20px;border-radius:8px;display:inline-block;border:1px solid #1e2430;">
                {code}
              </div>
              <p style="margin:16px 0 0 0;font-size:12px;color:#94a3b8;">Válido por 15 minutos.</p>
            </div>
            """,
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
