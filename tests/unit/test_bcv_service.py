"""Tests unitarios para BCVService y scraping oficial de la tasa de cambio."""

from unittest.mock import MagicMock, patch

from src.reporting.bcv_service import BCVService

SAMPLE_BCV_HTML = """
<div class="view-content">
  <div id="euro" class="col-sm-12 col-xs-12 ">
    <div class="field-content">
      <div class="row recuadrotsmc">
        <div class="col-sm-6 col-xs-6"><span> EUR </span></div>
        <div class="col-sm-6 col-xs-6 centrado textp"><strong class="strong-tb"> 985,72980800</strong></div>
      </div>
    </div>
  </div>
  <div id="dolar" class="col-sm-12 col-xs-12 ">
    <div class="field-content">
      <div class="row recuadrotsmc">
        <div class="col-sm-6 col-xs-6"><span> USD </span></div>
        <div class="col-sm-6 col-xs-6 centrado textp"> <strong class="strong-tb">880,11590000</strong> </div>
      </div>
    </div>
  </div>
  <span class="date-display-single" property="dc:date" content="2026-10-16T00:00:00-04:00">Viernes, 16 Octubre 2026</span>
</div>
"""


def test_bcv_parse_html_structure():
    """Debe extraer con precisión la tasa USD, EUR y la fecha valor del HTML oficial del BCV."""
    service = BCVService()
    parsed = service._parse_bcv_html(SAMPLE_BCV_HTML)

    assert parsed["usd"] == 880.1159
    assert parsed["eur"] == 985.729808
    assert "16 Octubre 2026" in parsed["fecha_valor"]


def test_bcv_fetch_current_rate_live_success():
    """Debe retornar la tasa parseada directamente del portal oficial."""
    service = BCVService()
    mock_resp = MagicMock(status_code=200, text=SAMPLE_BCV_HTML)

    with patch("httpx.Client.get", return_value=mock_resp):
        rate = service.fetch_current_rate()
        assert rate == 880.1159


def test_bcv_fallback_when_scrape_fails():
    """Si el scraping oficial falla, debe intentar la API de respaldo o valor de referencia."""
    service = BCVService()

    with patch.object(service, "_scrape_bcv_official", return_value=None):
        with patch.object(service, "_fetch_from_fallback_api", return_value=875.50):
            rate = service.fetch_current_rate()
            assert rate == 875.50

        with patch.object(service, "_fetch_from_fallback_api", return_value=None):
            rate_default = service.fetch_current_rate()
            assert rate_default > 0
