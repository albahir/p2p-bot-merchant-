"""Validador de claves criptográficas y formato PEM para API Keys de Binance."""

import logging

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

logger = logging.getLogger("key_validator")


class KeyValidationError(ValueError):
    """Excepción lanzada cuando una clave criptográfica no cumple el formato esperado."""


class KeyValidator:
    """Validador estricto de claves antes de cifrarlas y guardarlas en base de datos."""

    @staticmethod
    def validate_api_key(api_key: str) -> str:
        """Valida que una API Key no esté vacía y tenga una longitud y caracteres razonables."""
        cleaned = api_key.strip()
        if not cleaned:
            raise KeyValidationError("La API Key no puede estar vacía.")
        if len(cleaned) < 32:
            raise KeyValidationError("La API Key es demasiado corta (mínimo 32 caracteres esperados).")
        return cleaned

    @staticmethod
    def validate_private_key_pem(pem_str: str) -> str:
        """Valida que una clave privada sea un bloque PEM sintácticamente válido (Ed25519 o RSA).
        
        Fail-closed: si la clave está incompleta, corrupta o no tiene encabezados válidos, rechaza.
        """
        cleaned = pem_str.strip()
        if not cleaned:
            raise KeyValidationError("La clave privada no puede estar vacía.")

        if "-----BEGIN" not in cleaned or "-----END" not in cleaned:
            raise KeyValidationError(
                "Formato de clave inválido: Debe incluir los encabezados '-----BEGIN PRIVATE KEY-----' y '-----END PRIVATE KEY-----'."
            )

        try:
            # Intento de deserialización estricto sin contraseña (o None)
            key = load_pem_private_key(cleaned.encode("utf-8"), password=None)
            if not isinstance(key, (Ed25519PrivateKey, RSAPrivateKey)):
                raise KeyValidationError(
                    "Tipo de clave no admitido por Binance: Se requiere Ed25519 (recomendada) o RSA."
                )
            logger.info("Clave privada PEM validada sintácticamente con éxito.")
            return cleaned
        except KeyValidationError:
            raise
        except Exception as e:
            raise KeyValidationError(f"Error procesando la clave privada PEM: Formato corrupto o contraseña requerida ({e})")
