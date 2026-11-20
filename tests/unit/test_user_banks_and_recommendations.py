"""Tests unitarios TDD para perfil de bancos del usuario, saldos por banco y motor de recomendación de spreads."""

import json
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.routes.accounting import get_live_balance
from src.api.routes.settings import get_user_banks_settings, save_user_banks_settings
from src.api.schemas.auth import UserPublicResponse
from src.api.schemas.settings import UpdateUserBanksRequest
from src.core.spread_monitor import BankRateQuote, SpreadMonitor
from src.data.database import Base
from src.data.models import BankVoucher, Order, User
from src.reporting.accounting_engine import AccountingEngine


def _create_test_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_cls = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return session_cls()


def test_user_banks_persistence_and_public_hydration() -> None:
    """Verifica que los bancos y saldos por banco del usuario se guarden en BD y se hidraten en UserPublicResponse."""
    db = _create_test_session()
    user = User(
        username="operador_bancos",
        password_hash="hash_test",
        role="TRADER",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    req = UpdateUserBanksRequest(
        preferred_banks=["Venezuela", "Mercantil"],
        bank_initial_balances={
            "Venezuela": 54545.0,
            "Mercantil": 4464646.0,
        },
    )
    res = save_user_banks_settings(req=req, current_user=user, db=db)

    assert "Banco de Venezuela" in res.preferred_banks
    assert "Mercantil" in res.preferred_banks
    assert res.bank_initial_balances["Banco de Venezuela"] == 54545.0
    assert res.bank_initial_balances["Mercantil"] == 4464646.0
    assert res.total_initial_ves == 4519191.0

    # Consultar vía GET /api/settings/banks
    fetched = get_user_banks_settings(current_user=user)
    assert fetched.total_initial_ves == 4519191.0
    assert fetched.bank_initial_balances["Banco de Venezuela"] == 54545.0

    # Verificar hidratación automática al iniciar sesión (UserPublicResponse)
    public_user = UserPublicResponse.model_validate(user)
    assert public_user.preferred_banks == ["Banco de Venezuela", "Mercantil"]
    assert public_user.bank_initial_balances["Banco de Venezuela"] == 54545.0
    assert public_user.bank_initial_balances["Mercantil"] == 4464646.0


def test_accounting_live_balance_uses_per_bank_balances_and_aliases() -> None:
    """Verifica que Contabilidad desglose y sume saldos iniciales + flujos por cada banco registrado del usuario."""
    db = _create_test_session()
    user = User(
        username="trader_multibanco",
        password_hash="hash_test",
        role="TRADER",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    save_user_banks_settings(
        req=UpdateUserBanksRequest(
            preferred_banks=["Venezuela", "Mercantil"],
            bank_initial_balances={
                "Venezuela": 54545.0,
                "Mercantil": 4464646.0,
            },
        ),
        current_user=user,
        db=db,
    )

    # Registrar una compra P2P pagada desde BDV / Venezuela por Bs. 10.000
    uid = int(user.id)
    order_buy = Order(
        user_id=uid,
        order_number="ORD-BDV-001",
        trade_type="BUY",
        asset="USDT",
        fiat="VES",
        fiat_amount=10000.0,
        crypto_amount=10.0,
        unit_price=1000.0,
        bcv_rate=900.0,
        order_status="COMPLETED",
        created_at=datetime(2026, 11, 15, 14, 0, 0, tzinfo=UTC).replace(tzinfo=None),
    )
    voucher_buy = BankVoucher(
        user_id=uid,
        bank_name="Venezuela",
        reference_number="REF-BDV-100",
        amount_ves=10000.0,
        bank_fee_ves=0.0,
        total_debited_ves=10000.0,
        payment_method="PAGO_MOVIL",
        movement_type="DEBIT",
        associated_order_number="ORD-BDV-001",
        verification_status="MATCHED",
        voucher_date=datetime(2026, 11, 15, 14, 5, 0, tzinfo=UTC).replace(tzinfo=None),
    )
    db.add_all([order_buy, voucher_buy])
    db.commit()
    db.refresh(order_buy)
    db.refresh(voucher_buy)

    engine = AccountingEngine(db=db, user_id=uid)
    engine.record_p2p_trade(order=order_buy, voucher=voucher_buy, user_id=uid)

    # Consultar saldo en vivo sin pasar initial_ves escalar (usa los saldos por banco del perfil del usuario)
    live = get_live_balance(
        db=db,
        current_user=user,
        year=2026,
        month=11,
        initial_usdt=50.0,
        initial_ves=0.0,
    )

    assert live.total_initial_ves == 4519191.0
    assert live.total_outflows_ves == 10000.0
    assert live.total_theoretical_ves == 4509191.0

    by_name = {b.bank_name: b for b in live.bank_breakdown}
    assert "Banco de Venezuela" in by_name
    assert "Mercantil" in by_name
    assert by_name["Banco de Venezuela"].initial_ves == 54545.0
    assert by_name["Banco de Venezuela"].outflows_ves == 10000.0
    assert by_name["Banco de Venezuela"].theoretical_ves == 44545.0
    assert by_name["Mercantil"].initial_ves == 4464646.0
    assert by_name["Mercantil"].theoretical_ves == 4464646.0

    # También debe permitir override explícito por query param bank_balances_json desde el frontend
    override_json = json.dumps({"Banco de Venezuela": 100000.0, "Mercantil": 200000.0})
    live_override = get_live_balance(
        db=db,
        current_user=user,
        year=2026,
        month=11,
        initial_usdt=50.0,
        initial_ves=0.0,
        bank_balances_json=override_json,
    )
    assert live_override.total_initial_ves == 300000.0
    assert live_override.total_theoretical_ves == 290000.0


def test_spread_monitor_recommend_for_user_profile_and_toggle_all() -> None:
    """Verifica el algoritmo de recomendación de spreads adaptado a los bancos del usuario con opción de ver todos."""
    quotes = [
        BankRateQuote(bank_name="Banesco", buy_rate=1050.0, sell_rate=1075.0, total_ads=25, liquidity_pct=90.0),
        BankRateQuote(bank_name="Banco de Venezuela", buy_rate=1055.0, sell_rate=1072.0, total_ads=30, liquidity_pct=95.0),
        BankRateQuote(bank_name="Mercantil", buy_rate=1052.0, sell_rate=1074.0, total_ads=20, liquidity_pct=85.0),
        BankRateQuote(bank_name="Bancamiga", buy_rate=1048.0, sell_rate=1080.0, total_ads=10, liquidity_pct=60.0),
    ]

    monitor = SpreadMonitor()

    # 1. Modo MY_BANKS (Recomendación personalizada para el perfil del usuario: Venezuela + Mercantil)
    rec_my_banks = monitor.recommend_for_user_profile(
        quotes=quotes,
        preferred_banks=["Venezuela", "Mercantil"],
        bank_balances={"Venezuela": 54545.0, "Mercantil": 4464646.0},
        amount_usdt=100.0,
        mode="MY_BANKS",
    )

    assert rec_my_banks["mode"] == "MY_BANKS"
    filtered_names = [q["bank_name"] for q in rec_my_banks["quotes"]]
    assert filtered_names == ["Mercantil", "Banco de Venezuela"] or set(filtered_names) == {
        "Banco de Venezuela",
        "Mercantil",
    }
    assert all(q["is_user_bank"] is True for q in rec_my_banks["quotes"])

    # Verificar que las rutas recomendadas en modo MY_BANKS solo usen bancos del usuario
    routes = rec_my_banks["recommended_routes"]
    assert len(routes) > 0
    for r in routes:
        assert r["buy_bank"] in ("Banco de Venezuela", "Mercantil")
        assert r["sell_bank"] in ("Banco de Venezuela", "Mercantil")

    # Mercantil tiene Bs. 4.464.646 (>= 105.200 Bs requeridos para 100 USDT), mientras Venezuela tiene 54.545 (< 105.500)
    mercantil_buy_routes = [r for r in routes if r["buy_bank"] == "Mercantil"]
    bdv_buy_routes = [r for r in routes if r["buy_bank"] == "Banco de Venezuela"]
    assert all(r["has_sufficient_balance"] is True for r in mercantil_buy_routes)
    assert all(r["has_sufficient_balance"] is False for r in bdv_buy_routes)

    # 2. Modo ALL_BANKS (Ver todos los bancos sin perder etiquetas de perfil)
    rec_all = monitor.recommend_for_user_profile(
        quotes=quotes,
        preferred_banks=["Venezuela", "Mercantil"],
        bank_balances={"Venezuela": 54545.0, "Mercantil": 4464646.0},
        amount_usdt=100.0,
        mode="ALL_BANKS",
    )
    assert rec_all["mode"] == "ALL_BANKS"
    assert len(rec_all["quotes"]) == 4
    user_flagged = [q["bank_name"] for q in rec_all["quotes"] if q["is_user_bank"]]
    assert set(user_flagged) == {"Banco de Venezuela", "Mercantil"}
