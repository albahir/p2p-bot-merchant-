"""Gestión cifrada de API Keys y secretos en reposo mediante AES-256-GCM.
Decodifica únicamente en memoria volátil. Nunca persiste secretos en texto plano.
"""

import binascii
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.data.database import SessionLocal
from src.data.repositories import SecurityRepository
from src.security.audit_logger import AuditLogger

logger = logging.getLogger("api_key_manager")


class ApiKeyManager:
    """Administrador de claves y secretos cifrados con AES-256-GCM."""

    def __init__(
        self,
        master_key: str,
        audit_logger: AuditLogger | None = None,
        db_session_factory=SessionLocal
    ):
        if not master_key or len(master_key) < 32:
            raise ValueError("FAIL-CLOSED: La clave maestra debe tener al menos 32 caracteres.")

        # Derivar o truncar 32 bytes para AES-256
        if len(master_key) == 64:
            try:
                self._key_bytes = binascii.unhexlify(master_key)
            except Exception:
                self._key_bytes = master_key[:32].encode("utf-8")
        else:
            self._key_bytes = master_key[:32].encode("utf-8")

        self.aesgcm = AESGCM(self._key_bytes)
        self.audit = audit_logger or AuditLogger(db_session_factory)
        self.session_factory = db_session_factory

    def store_secret(self, key_name: str, plaintext: str, ip_address: str = "127.0.0.1") -> None:
        """Cifra un secreto con AES-256-GCM y lo persiste en la base de datos."""
        nonce = os.urandom(12)  # 96 bits recomendado para GCM
        # AESGCM.encrypt en cryptography devuelve ciphertext + 16 bytes de tag al final
        encrypted = self.aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        ciphertext_bytes = encrypted[:-16]
        tag_bytes = encrypted[-16:]

        nonce_hex = binascii.hexlify(nonce).decode("utf-8")
        ciphertext_hex = binascii.hexlify(ciphertext_bytes).decode("utf-8")
        tag_hex = binascii.hexlify(tag_bytes).decode("utf-8")

        db = self.session_factory()
        try:
            repo = SecurityRepository(db)
            repo.upsert_secret(
                key_name=key_name,
                nonce=nonce_hex,
                ciphertext=ciphertext_hex,
                tag=tag_hex
            )
            self.audit.log(
                event_type="STORE_SECRET",
                key_identifier=key_name,
                ip_address=ip_address,
                status="SUCCESS"
            )
        except Exception as e:
            self.audit.log(
                event_type="STORE_SECRET",
                key_identifier=key_name,
                ip_address=ip_address,
                status="FAILED"
            )
            raise RuntimeError(f"FAIL-CLOSED: Error al almacenar secreto cifrado: {e}") from e
        finally:
            db.close()

    def get_secret(self, key_name: str, ip_address: str = "127.0.0.1") -> str:
        """Recupera y descifra un secreto en memoria volátil."""
        db = self.session_factory()
        try:
            repo = SecurityRepository(db)
            record = repo.get_secret(key_name)
            if not record:
                self.audit.log(
                    event_type="READ_SECRET",
                    key_identifier=key_name,
                    ip_address=ip_address,
                    status="FAILED"
                )
                raise KeyError(f"FAIL-CLOSED: Secreto '{key_name}' no encontrado.")

            nonce = binascii.unhexlify(record.nonce)
            ciphertext = binascii.unhexlify(record.ciphertext)
            tag = binascii.unhexlify(record.tag)

            # Reconstruir payload esperado por AESGCM (ciphertext + tag)
            encrypted = ciphertext + tag
            decrypted_bytes = self.aesgcm.decrypt(nonce, encrypted, None)

            self.audit.log(
                event_type="READ_SECRET",
                key_identifier=key_name,
                ip_address=ip_address,
                status="SUCCESS"
            )
            return decrypted_bytes.decode("utf-8")
        except KeyError:
            raise
        except Exception as e:
            self.audit.log(
                event_type="READ_SECRET",
                key_identifier=key_name,
                ip_address=ip_address,
                status="FAILED"
            )
            raise ValueError(f"FAIL-CLOSED: Fallo en descifrado o integridad comprometida: {e}") from e
        finally:
            db.close()
