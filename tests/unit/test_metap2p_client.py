"""Tests unitarios para MetaP2PClient y su integración en IdentityService."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.database import Base
from src.integrations.metap2p_client import MetaP2PClient
from src.security.identity_service import IdentityService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_metap2p_login_and_search_success():
    client = MetaP2PClient(email="trader@test.com", password="SecretPassword123")

    mock_login_resp = MagicMock()
    mock_login_resp.status_code = 200
    mock_login_resp.json.return_value = {
        "access_token": "mock_jwt_token_12345",
        "user": {"email": "trader@test.com"}
    }

    mock_search_resp = MagicMock()
    mock_search_resp.status_code = 200
    mock_search_resp.json.return_value = {
        "full_name": "MANUEL ALEJANDRO RODRIGUEZ PEREZ",
        "dni_prefix": "V",
        "dni_number": "18234567",
        "dni": "V18234567",
        "rif": "V182345670",
        "birth_date": "1990-05-12",
        "cne": {
            "estado": "MIRANDA",
            "municipio": "SUCRE",
            "parroquia": "PETARE",
            "centro_electoral": "U.E. COLEGIO SUCRE"
        }
    }

    with patch.object(client._http, "post", return_value=mock_login_resp) as mock_post, \
         patch.object(client._http, "get", return_value=mock_search_resp) as mock_get:

        info = client.search_dni("18234567")

        assert mock_post.called
        assert mock_get.called
        assert info.is_valid is True
        assert info.cedula == "18234567"
        assert info.nationality == "V"
        assert info.full_name == "MANUEL ALEJANDRO RODRIGUEZ PEREZ"
        assert info.source == "METAP2P"


def test_metap2p_record_not_found():
    client = MetaP2PClient(email="trader@test.com", password="SecretPassword123")
    client._access_token = "cached_token"

    mock_search_resp = MagicMock()
    mock_search_resp.status_code = 400
    mock_search_resp.json.return_value = {"error": "RECORD_NOT_FOUND"}

    with patch.object(client._http, "get", return_value=mock_search_resp):
        info = client.search_dni("99999999")

        assert info.is_valid is False
        assert "no encontrada" in info.error_message.lower() or "not found" in info.error_message.lower()


def test_metap2p_token_expiry_auto_renew():
    client = MetaP2PClient(email="trader@test.com", password="SecretPassword123")
    client._access_token = "expired_token"

    mock_401 = MagicMock()
    mock_401.status_code = 401

    mock_login_resp = MagicMock()
    mock_login_resp.status_code = 200
    mock_login_resp.json.return_value = {"access_token": "new_refreshed_token"}

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {
        "full_name": "CARLOS EDUARDO PEREZ",
        "dni_prefix": "V",
        "dni_number": "20123456"
    }

    # Primera llamada a get devuelve 401, segunda 200 tras re-login
    with patch.object(client._http, "get", side_effect=[mock_401, mock_200]), \
         patch.object(client._http, "post", return_value=mock_login_resp) as mock_login:

        info = client.search_dni("20123456")

        assert mock_login.called
        assert client._access_token == "new_refreshed_token"
        assert info.is_valid is True
        assert info.full_name == "CARLOS EDUARDO PEREZ"


def test_identity_service_with_metap2p_integration(db_session):
    mock_metap2p = MagicMock(spec=MetaP2PClient)
    from src.security.identity_service import IdentityInfo
    mock_metap2p.search_dni.return_value = IdentityInfo(
        nationality="V",
        cedula="18234567",
        full_name="MANUEL ALEJANDRO RODRIGUEZ PEREZ",
        is_valid=True,
        source="METAP2P"
    )

    service = IdentityService(db=db_session, metap2p_client=mock_metap2p)

    # 1. Primera consulta: usa MetaP2P y almacena en caché local
    info = service.lookup(nationality="V", cedula="18234567")
    assert info.is_valid is True
    assert info.full_name == "MANUEL ALEJANDRO RODRIGUEZ PEREZ"
    assert info.source == "METAP2P"
    assert mock_metap2p.search_dni.call_count == 1

    # 2. Segunda consulta: debe responder directamente de la caché sin llamar a MetaP2P
    mock_metap2p.search_dni.reset_mock()
    info_cached = service.lookup(nationality="V", cedula="18234567")
    assert info_cached.is_valid is True
    assert info_cached.full_name == "MANUEL ALEJANDRO RODRIGUEZ PEREZ"
    assert info_cached.source == "CACHE"
    assert mock_metap2p.search_dni.call_count == 0
