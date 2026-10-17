"""Tests unitarios para el servicio de verificación de identidad y extracción de cédula."""

from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.security.identity_service import IdentityService, extract_cedula_from_payment_details


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_extract_cedula_from_various_formats():
    # Formato con guión
    assert extract_cedula_from_payment_details("Pago Móvil V-18234567 04141234567") == ("V", "18234567")
    # Formato con puntos
    assert extract_cedula_from_payment_details("CI: 19.876.543 Banesco") == ("V", "19876543")
    # Extranjero
    assert extract_cedula_from_payment_details("Titular: E-82123456") == ("E", "82123456")
    # Diccionario con campos bancarios
    data_dict = {
        "bankName": "Banco de Venezuela",
        "account": "01020000000000000000",
        "identification": "V20111222",
    }
    assert extract_cedula_from_payment_details(data_dict) == ("V", "20111222")
    # Texto sin cédula
    assert extract_cedula_from_payment_details("Transferencia inmediata") is None


def test_identity_service_cache_hit():
    db = setup_in_memory_db()
    service = IdentityService(db=db)

    # Pre-cargar en caché
    service.save_to_cache("V", "18234567", "CARLOS ALBERTO PEREZ", source="MANUAL")

    result = service.lookup("V", "18234567")
    assert result.is_valid is True
    assert result.full_name == "CARLOS ALBERTO PEREZ"
    assert result.source == "CACHE"


def test_identity_service_seniat_success():
    db = setup_in_memory_db()
    service = IdentityService(db=db)

    mock_xml = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <rif:Rif xmlns:rif="http://seniat.gob.ve">
        <rif:Nombre>MARIA EUGENIA GONZALEZ</rif:Nombre>
        <rif:AgenteRetencionIVA>NO</rif:AgenteRetencionIVA>
    </rif:Rif>
    """

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = mock_xml

    with patch.object(service._client, "get", return_value=mock_response):
        result = service.lookup("V", "20333444")
        assert result.is_valid is True
        assert result.full_name == "MARIA EUGENIA GONZALEZ"
        assert result.source == "SENIAT"

        # Verificar que se guardó en la caché de BD
        cached = service.lookup_cache("V", "20333444")
        assert cached is not None
        assert cached.full_name == "MARIA EUGENIA GONZALEZ"


def test_identity_service_fallback_to_cne_when_seniat_fails():
    db = setup_in_memory_db()
    service = IdentityService(db=db)

    mock_html = """
    <html>
        <body>
            <table class="datos_elector">
                <tr><td>Cédula:</td><td>V-15444555</td></tr>
                <tr><td>Primer Nombre:</td><td>JUAN</td></tr>
                <tr><td>Segundo Nombre:</td><td>JOSE</td></tr>
                <tr><td>Primer Apellido:</td><td>RAMIREZ</td></tr>
                <tr><td>Segundo Apellido:</td><td>BLANCO</td></tr>
            </table>
        </body>
    </html>
    """

    # Simular fallo en SENIAT y éxito en CNE
    def side_effect(url, **kwargs):
        resp = MagicMock()
        if "seniat.gob.ve" in url:
            resp.status_code = 500
            resp.text = "Error interno"
        elif "cne.gob.ve" in url:
            resp.status_code = 200
            resp.text = mock_html
        return resp

    with patch.object(service._client, "get", side_effect=side_effect):
        result = service.lookup("V", "15444555")
        assert result.is_valid is True
        assert "JUAN" in result.full_name
        assert "RAMIREZ" in result.full_name
        assert result.source == "CNE"


def test_identity_service_fails_when_all_sources_fail():
    db = setup_in_memory_db()
    service = IdentityService(db=db)

    mock_fail = MagicMock()
    mock_fail.status_code = 503
    mock_fail.text = "Service Unavailable"

    with patch.object(service._client, "get", return_value=mock_fail):
        result = service.lookup("V", "99999999")
        assert result.is_valid is False
        assert result.full_name == ""
        assert "No se pudo verificar" in (result.error_message or "")
