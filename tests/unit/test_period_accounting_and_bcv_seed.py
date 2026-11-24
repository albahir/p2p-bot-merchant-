"""Pruebas TDD para Seed BCV histórico, sincronización por mes exacto, saldos por período y Balance General VEN-NIF 12."""

from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.routes.accounting import (
    PeriodConfigUpdateRequest,
    _build_accounting_export_context,
    get_period_config,
    save_period_config,
)
from src.core.binance_history_syncer import BinanceHistorySyncer
from src.core.binance_schemas import BinanceOrderMatchItem
from src.data.models import Base, JournalEntry, Order, User
from src.reporting.bcv_history_service import BCVHistoryService
from src.reporting.excel_reporter import ExcelReporter
from src.reporting.pdf_reporter import PDFReporter


def _setup_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    return db


def test_bcv_seed_loads_60_rates_idempotently_and_resolves_october_dates() -> None:
    """Debe sembrar los 60 días hábiles del BCV sin duplicar y resolver fines de semana al viernes anterior."""
    db = _setup_db()
    try:
        svc = BCVHistoryService(db)
        inserted_first = svc.seed_historical_rates_if_missing()
        assert inserted_first == 60
        inserted_second = svc.seed_historical_rates_if_missing()
        assert inserted_second == 0

        # Fecha exacta en octubre
        assert svc.get_rate_for_date(date(2026, 10, 1)) == 860.1753
        # Sábado 2026-10-31 debe resolver al viernes 2026-10-30 (889.2553)
        assert svc.get_rate_for_date(date(2026, 10, 31)) == 889.2553
        # Feriado lunes 2026-10-12 (Día de la Resistencia Indígena) -> viernes anterior 2026-10-09 (875.6505)
        assert svc.get_rate_for_date(date(2026, 10, 12)) == 875.6505
        # Fecha reciente noviembre
        assert svc.get_rate_for_date(date(2026, 11, 24)) == 919.8227
    finally:
        db.close()


def test_binance_sync_exact_month_vet_assigns_historical_bcv_rate_per_order() -> None:
    """Al sincronizar Octubre 2026 en VET, debe dividir 31 días en 2 ventanas y asignar la tasa BCV de cada fecha."""
    db = _setup_db()
    try:
        BCVHistoryService(db).seed_historical_rates_if_missing()
        calls: list[tuple[str, int, int]] = []

        vet_tz = timezone(timedelta(hours=-4))
        oct_01_ms = int(datetime(2026, 10, 1, 10, 30, tzinfo=vet_tz).astimezone(UTC).timestamp() * 1000)
        oct_31_ms = int(datetime(2026, 10, 31, 22, 0, tzinfo=vet_tz).astimezone(UTC).timestamp() * 1000)

        class FakeBinanceClient:
            def get_order_history(
                self,
                trade_type: str,
                start_timestamp: int,
                end_timestamp: int,
                page: int = 1,
                rows: int = 50,
            ) -> Any:
                calls.append((trade_type, start_timestamp, end_timestamp))
                items: list[BinanceOrderMatchItem] = []
                if trade_type == "BUY" and start_timestamp <= oct_01_ms <= end_timestamp:
                    items.append(
                        BinanceOrderMatchItem(
                            orderNumber="OCT_BUY_001",
                            advNo="ADV1",
                            tradeType="BUY",
                            asset="USDT",
                            fiat="VES",
                            fiatSymbol="Bs",
                            amount="100.0",
                            totalPrice="95000.0",
                            unitPrice="950.0",
                            orderStatus="COMPLETED",
                            createTime=oct_01_ms,
                            commission="0.0",
                            takerCommission="0.0",
                            counterPartNickName="TraderA",
                            payMethodName="Banesco",
                        )
                    )
                if trade_type == "SELL" and start_timestamp <= oct_31_ms <= end_timestamp:
                    items.append(
                        BinanceOrderMatchItem(
                            orderNumber="OCT_SELL_002",
                            advNo="ADV2",
                            tradeType="SELL",
                            asset="USDT",
                            fiat="VES",
                            fiatSymbol="Bs",
                            amount="100.0",
                            totalPrice="99000.0",
                            unitPrice="990.0",
                            orderStatus="COMPLETED",
                            createTime=oct_31_ms,
                            commission="0.1",
                            takerCommission="0.0",
                            counterPartNickName="TraderB",
                            payMethodName="Banesco",
                        )
                    )
                return SimpleNamespace(data=items)

        res = BinanceHistorySyncer().sync_orders(
            client=FakeBinanceClient(),
            db=db,
            year=2026,
            month=10,
            trade_type="ALL",
            user_id=1,
        )
        assert res.success is True
        assert res.orders_inserted == 2
        # Octubre tiene 31 días -> 2 ventanas (<=30d c/u) x 2 tipos (BUY, SELL) = 4 llamadas
        assert len(calls) == 4
        for _, w_start, w_end in calls:
            assert (w_end - w_start) <= 30 * 24 * 60 * 60 * 1000

        o1 = db.query(Order).filter(Order.order_number == "OCT_BUY_001").first()
        o2 = db.query(Order).filter(Order.order_number == "OCT_SELL_002").first()
        assert o1 is not None and o2 is not None
        # Tasa BCV del 01/10 (860.1753) y del 31/10 sábado -> 30/10 (889.2553), NO la tasa de noviembre!
        assert abs(float(o1.bcv_rate) - 860.1753) < 0.0005
        assert abs(float(o2.bcv_rate) - 889.2553) < 0.0005
    finally:
        db.close()


def test_period_balances_isolation_carryover_and_financial_exports(tmp_path: Path) -> None:
    """Los saldos de 2026-10 no pisan 2026-11, se arrastran al mes siguiente y viajan al Excel/PDF con Balance General."""
    db = _setup_db()
    try:
        BCVHistoryService(db).seed_historical_rates_if_missing()
        user = User(
            username="operador_fiscal",
            password_hash="hashed",
            full_name="Carlos Comerciante",
            tax_id="V-18456789",
            role="TRADER",
            is_active=True,
            preferred_banks_json='["Banesco", "Mercantil"]',
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # 1. Guardar apertura y cierre real de Octubre 2026
        oct_saved = save_period_config(
            payload=PeriodConfigUpdateRequest(
                year=2026,
                month=10,
                initial_usdt=200.0,
                initial_usdt_cost_ves=172035.06,
                initial_banks={"Banesco": 50000.0, "Mercantil": 30000.0},
                actual_final_usdt=250.0,
                actual_final_banks={"Banesco": 62000.0, "Mercantil": 35000.0},
                mark_closed=True,
            ),
            db=db,
            current_user=user,
        )
        assert oct_saved.period == "2026-10"
        assert oct_saved.initial_usdt == 200.0
        assert oct_saved.actual_final_usdt == 250.0
        assert oct_saved.is_closed is True

        # 2. Consultar Noviembre 2026 (sin guardar aún) -> debe arrastrar saldo final real de Octubre
        nov_cfg = get_period_config(year=2026, month=11, db=db, current_user=user)
        assert nov_cfg.source == "carried_over"
        assert nov_cfg.carried_from == "2026-10"
        assert nov_cfg.initial_usdt == 250.0
        assert nov_cfg.initial_banks["Banesco"] == 62000.0
        assert nov_cfg.initial_banks["Mercantil"] == 35000.0

        # 3. Verificar que Octubre mantiene sus propios saldos aislados
        oct_cfg = get_period_config(year=2026, month=10, db=db, current_user=user)
        assert oct_cfg.source == "saved"
        assert oct_cfg.initial_usdt == 200.0
        assert oct_cfg.initial_banks["Banesco"] == 50000.0

        # 4. Agregar una compra y una venta en Octubre + asiento contable para probar Excel y PDF
        vet_tz = timezone(timedelta(hours=-4))
        dt_buy = datetime(2026, 10, 5, 11, 0, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
        dt_sell = datetime(2026, 10, 10, 15, 0, tzinfo=vet_tz).astimezone(UTC).replace(tzinfo=None)
        db.add(
            Order(
                user_id=user.id,
                order_number="ORD_OCT_1",
                trade_type="BUY",
                asset="USDT",
                fiat="VES",
                fiat_amount=95000.0,
                crypto_amount=100.0,
                unit_price=950.0,
                fee_fiat=0.0,
                fee_crypto=0.0,
                bcv_rate=871.3689,
                order_status="COMPLETED",
                created_at=dt_buy,
            )
        )
        db.add(
            Order(
                user_id=user.id,
                order_number="ORD_OCT_2",
                trade_type="SELL",
                asset="USDT",
                fiat="VES",
                fiat_amount=99500.0,
                crypto_amount=100.0,
                unit_price=995.0,
                fee_fiat=99.5,
                fee_crypto=0.1,
                bcv_rate=875.6505,
                order_status="COMPLETED",
                created_at=dt_sell,
            )
        )
        db.add(
            JournalEntry(
                user_id=user.id,
                entry_number=1,
                date_time=dt_sell,
                account_code="1.1.01",
                account_name="Banco Nacional VES - Banesco",
                debit=99500.0,
                credit=0.0,
                reference="REF999",
                description="Venta P2P ORD_OCT_2",
                order_number="ORD_OCT_2",
                prev_hash="0" * 64,
                entry_hash="a" * 64,
            )
        )
        db.add(
            JournalEntry(
                user_id=user.id,
                entry_number=1,
                date_time=dt_sell,
                account_code="1.1.05",
                account_name="Activos Criptográficos - USDT",
                debit=0.0,
                credit=99500.0,
                reference="REF999",
                description="Salida USDT ORD_OCT_2",
                order_number="ORD_OCT_2",
                prev_hash="a" * 64,
                entry_hash="b" * 64,
            )
        )
        db.commit()

        ctx = _build_accounting_export_context(db, user, 2026, 10)
        assert ctx["initial_usdt"] == 200.0
        assert ctx["initial_ves"] == 80000.0
        assert ctx["actual_final_usdt"] == 250.0
        assert ctx["actual_final_ves"] == 97000.0

        xlsx_path = str(tmp_path / "octubre_seniat.xlsx")
        ExcelReporter.generate_accounting_report(
            journal_entries=ctx["entries"],
            ledger_summaries=ctx["ledgers"],
            vouchers=ctx["vouchers"],
            output_path=xlsx_path,
            tax_results=ctx["tax_results"],
            orders=ctx["orders"],
            account_holder=ctx["account_holder"],
            rif=ctx["tax_id"],
            period=ctx["period"],
            bcv_rate=ctx["bcv_rate"],
            initial_usdt=ctx["initial_usdt"],
            initial_usdt_cost_ves=ctx["initial_usdt_cost_ves"],
            initial_ves=ctx["initial_ves"],
            actual_final_usdt=ctx["actual_final_usdt"],
            actual_final_ves=ctx["actual_final_ves"],
        )
        wb = openpyxl.load_workbook(xlsx_path)
        assert "Balance General (VEN-NIF 12)" in wb.sheetnames
        assert "Kardex Inventario USDT" in wb.sheetnames
        ws_kardex = wb["Kardex Inventario USDT"]
        assert ws_kardex["B2"].value == 200.0  # Saldo Inicial USDT real, NO 0.0

        ws_mayor = wb["Libro Mayor"]
        banco_rows = [row for row in ws_mayor.iter_rows(min_row=2, values_only=True) if row[0] == "1.1.01"]
        assert banco_rows and banco_rows[0][3] == 80000.0  # Saldo Inicial VES real en Mayor

        pdf_path = str(tmp_path / "octubre_seniat.pdf")
        PDFReporter(company_name=ctx["account_holder"], rif=ctx["tax_id"] or "V-0").generate_accounting_pdf(
            journal_entries=ctx["entries"],
            ledger_summaries=ctx["ledgers"],
            vouchers=ctx["vouchers"],
            output_path=pdf_path,
            tax_results=ctx["tax_results"],
            orders=ctx["orders"],
            period=ctx["period"],
            initial_usdt=ctx["initial_usdt"],
            initial_usdt_cost_ves=ctx["initial_usdt_cost_ves"],
            initial_ves=ctx["initial_ves"],
            actual_final_usdt=ctx["actual_final_usdt"],
            actual_final_ves=ctx["actual_final_ves"],
        )
        pdf_bytes = Path(pdf_path).read_bytes()
        assert b"ESTADO DE SITUACION FINANCIERA" in pdf_bytes
        assert b"KARDEX DE INVENTARIO USDT" in pdf_bytes
        assert b"SUMAS IGUALES LIBRO DIARIO" in pdf_bytes
    finally:
        db.close()
