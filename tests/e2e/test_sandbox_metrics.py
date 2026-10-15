"""Prueba de Integración y E2E: Simulación en Sandbox y actualización dinámica de métricas.

Verifica:
1. Realismo del sandbox (order book P2P, anunciantes, límites, spread y comisiones).
2. Cumplimiento Fail-closed en ventanas de tiempo (>30 días).
3. Ingesta idempotente con HistoryIngestor (ingesta inicial vs reintento).
4. Discriminación correcta de estados (órdenes COMPLETED vs CANCELLED).
5. Población de tasas oficiales BCV y cálculo de comisiones.
6. Actualización dinámica de métricas operativas (volumen, conteo de órdenes).
7. Cálculo fiscal correcto (FIFO vs Costo Promedio) con ganancia neta en VES y USD.
8. Reacción dinámica de métricas ante la ejecución de un nuevo trade simulado.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.binance_mock import MockBinanceP2PClient
from src.core.history_ingestor import HistoryIngestor
from src.data.database import Base
from src.data.models import Order
from src.data.repositories import OrderRepository
from src.reporting.tax_engine import FIFOCostMethod, WeightedAverageCostMethod


@pytest.fixture
def test_db_session():
    """Crea una base de datos SQLite en memoria aislada para la prueba."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return session_factory


def test_sandbox_order_book_realism():
    """Verifica que el libro de órdenes del Sandbox simule un mercado realista en Venezuela."""
    client = MockBinanceP2PClient()
    
    # Order book para compra de USDT (anunciantes vendiendo a comerciantes)
    book_buy = client.get_order_book(asset="USDT", fiat="VES", trade_type="BUY", rows=5)
    assert book_buy.success is True
    assert len(book_buy.data) == 5
    for item in book_buy.data:
        assert float(item.adv.price) > 30.0
        assert item.advertiser.monthOrderCount > 100
        assert item.advertiser.monthFinishRate >= 0.95
        assert float(item.adv.minSingleTransAmount) > 0

    # Order book para venta de USDT (anunciantes comprando a comerciantes con spread)
    book_sell = client.get_order_book(asset="USDT", fiat="VES", trade_type="SELL", rows=5)
    assert book_sell.success is True
    assert len(book_sell.data) == 5
    # El precio de venta en el order book debe ser superior al de compra (spread positivo)
    assert float(book_sell.data[0].adv.price) > float(book_buy.data[0].adv.price)


def test_sandbox_fail_closed_on_large_window():
    """Verifica regla constitucional: consultas mayores a 30 días deben fallar cerrado."""
    client = MockBinanceP2PClient()
    start_ts = 1700000000000
    end_ts = start_ts + (32 * 24 * 60 * 60 * 1000)  # 32 días

    with pytest.raises(ValueError, match="FAIL-CLOSED"):
        client.get_order_history("ALL", start_ts, end_ts)


def test_sandbox_ingestion_and_metrics_lifecycle(test_db_session):
    """Prueba el ciclo completo: Sandbox -> Ingestor -> DB -> KPIs -> FIFO/Average -> Nuevo Trade."""
    client = MockBinanceP2PClient(enable_default_orders=True)
    ingestor = HistoryIngestor(client, db_session_factory=test_db_session)

    # 1. Primera Ingesta: deben registrarse 5 órdenes (2 BUY, 1 CANCELLED, 2 SELL)
    inserted_first = ingestor.ingest_recent_orders(trade_type="ALL", days_back=7)
    assert inserted_first == 5, f"Se esperaban 5 órdenes iniciales, se insertaron {inserted_first}"

    # 2. Prueba de Idempotencia: una segunda sincronización idéntica debe insertar 0 órdenes
    inserted_second = ingestor.ingest_recent_orders(trade_type="ALL", days_back=7)
    assert inserted_second == 0, "Idempotencia falló: se duplicaron órdenes ya existentes"

    # 3. Verificación de almacenamiento en DB y filtrado de CANCELLED
    db = test_db_session()
    repo = OrderRepository(db)
    all_orders = db.query(Order).all()
    completed_orders = repo.list_completed()
    db.close()

    assert len(all_orders) == 5
    assert len(completed_orders) == 4, "Las órdenes canceladas no deben figurar como completadas"

    # Verificar que todas las órdenes tienen tasa BCV oficial asignada (> 0)
    for ord_item in all_orders:
        assert ord_item.bcv_rate > 0.0, f"Orden {ord_item.order_number} no tiene bcv_rate válido"

    # 4. Cálculo de Métricas Operativas Iniciales
    total_volume_ves = sum(o.fiat_amount for o in completed_orders)
    # Compras: 3650.00 + 5490.00 = 9140.00 VES
    # Ventas: 4536.00 + 4940.00 = 9476.00 VES
    # Total: 18616.00 VES
    assert total_volume_ves == 18616.00

    # 5. Motor Fiscal: Método FIFO
    fifo = FIFOCostMethod()
    fifo_results = fifo.process_orders(completed_orders)
    assert len(fifo_results) == 2, "Deben liquidarse exactamente las 2 órdenes de SELL"

    fifo_profit_ves = sum(r.net_profit_fiat for r in fifo_results)
    fifo_profit_usd = sum(r.net_profit_usd for r in fifo_results)

    # El comerciante tuvo spread positivo y comisiones cubiertas: ganancia neta debe ser > 0
    assert fifo_profit_ves > 300.0, f"Ganancia FIFO inesperada: {fifo_profit_ves}"
    assert fifo_profit_usd > 5.0, f"Ganancia USD inesperada: {fifo_profit_usd}"

    # 6. Motor Fiscal: Método Costo Promedio Ponderado
    avg_engine = WeightedAverageCostMethod()
    avg_results = avg_engine.process_orders(completed_orders)
    assert len(avg_results) == 2

    avg_profit_ves = sum(r.net_profit_fiat for r in avg_results)
    assert avg_profit_ves > 300.0

    # Las ganancias por lote individual difieren entre FIFO y Promedio
    assert fifo_results[0].acquisition_cost_fiat != avg_results[0].acquisition_cost_fiat

    # 7. Simulación Dinámica: El comerciante ejecuta una nueva venta en el Sandbox
    # Venta de 50 USDT a 38.50 VES = 1925.00 VES con 2.00 Bs de comisión
    client.add_simulated_trade(
        order_number="202610140006",
        trade_type="SELL",
        amount=50.0,
        unit_price=38.50,
        fee_fiat=2.0,
        status="COMPLETED"
    )

    # Sincronizar de nuevo: debe detectar exactamente 1 orden nueva
    inserted_dynamic = ingestor.ingest_recent_orders(trade_type="ALL", days_back=7)
    assert inserted_dynamic == 1, "Debe insertarse exactamente la nueva orden simulada"

    # 8. Verificación de Métricas Actualizadas dinámicamente
    db = test_db_session()
    repo = OrderRepository(db)
    updated_completed = repo.list_completed()
    db.close()

    assert len(updated_completed) == 5
    new_total_volume = sum(o.fiat_amount for o in updated_completed)
    assert new_total_volume == 18616.00 + 1925.00

    new_fifo_results = fifo.process_orders(updated_completed)
    assert len(new_fifo_results) == 3  # Ahora hay 3 ventas procesadas

    new_profit_ves = sum(r.net_profit_fiat for r in new_fifo_results)
    assert new_profit_ves > fifo_profit_ves, "La nueva venta debe incrementar la ganancia neta"
