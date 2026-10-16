"""Tests unitarios para KeepAlivePinger (anti-suspensión en Nube)."""

from unittest.mock import MagicMock, patch

from src.main import KeepAlivePinger


def test_keep_alive_pinger_inactive_when_no_url(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("KEEP_ALIVE_URL", raising=False)
    pinger = KeepAlivePinger(target_url=None)
    pinger.start()
    assert pinger.is_running is False


def test_keep_alive_pinger_starts_and_stops_cleanly():
    pinger = KeepAlivePinger(target_url="https://mock-service.onrender.com", interval_seconds=1)
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock(status_code=200)
        mock_get.return_value = mock_resp

        pinger.start()
        assert pinger.is_running is True
        pinger.stop()
        assert pinger.is_running is False
