"""Repositorios de datos siguiendo el patrón Repository para acceso seguro y desacoplado."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from src.data.models import (
    BankVoucher,
    EncryptedSecret,
    FiscalPeriodSnapshot,
    Order,
    SecurityEvent,
    WalletMovement,
)


class OrderRepository:
    """Acceso a datos de órdenes para ingesta, motor fiscal y dashboard."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_order_number(self, order_number: str) -> Order | None:
        result = self.db.query(Order).filter(Order.order_number == order_number).first()
        return cast(Order | None, result)

    def create(self, order: Order) -> Order:
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def list_completed(self, start_date: datetime | None = None, end_date: datetime | None = None) -> list[Order]:
        query = self.db.query(Order).filter(Order.order_status == "COMPLETED")
        if start_date:
            query = query.filter(cast(Any, Order.created_at >= start_date))
        if end_date:
            query = query.filter(cast(Any, Order.created_at <= end_date))
        results = query.order_by(Order.created_at.asc()).all()
        return cast(list[Order], results)


class SecurityRepository:
    """Acceso a eventos de auditoría y almacenamiento de secretos."""

    def __init__(self, db: Session):
        self.db = db

    def get_last_event(self) -> SecurityEvent | None:
        result = self.db.query(SecurityEvent).order_by(SecurityEvent.id.desc()).first()
        return cast(SecurityEvent | None, result)

    def log_event(self, event: SecurityEvent) -> SecurityEvent:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_secret(self, key_name: str) -> EncryptedSecret | None:
        result = self.db.query(EncryptedSecret).filter(EncryptedSecret.key_name == key_name).first()
        return cast(EncryptedSecret | None, result)

    def upsert_secret(self, key_name: str, nonce: str, ciphertext: str, tag: str) -> EncryptedSecret:
        secret = self.get_secret(key_name)
        if not secret:
            secret = EncryptedSecret(
                key_name=key_name,
                nonce=nonce,
                ciphertext=ciphertext,
                tag=tag,
            )
            self.db.add(secret)
        else:
            secret.nonce = nonce  # type: ignore[assignment]
            secret.ciphertext = ciphertext  # type: ignore[assignment]
            secret.tag = tag  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(secret)
        return cast(EncryptedSecret, secret)


class WalletMovementRepository:
    """Acceso a movimientos de billetera (Depósitos y Retiros on-chain)."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, movement: WalletMovement) -> WalletMovement:
        self.db.add(movement)
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def get_by_txid(self, txid: str) -> WalletMovement | None:
        result = self.db.query(WalletMovement).filter(WalletMovement.txid == txid).first()
        return cast(WalletMovement | None, result)

    def list_by_period(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        asset: str | None = None,
        movement_type: str | None = None,
    ) -> list[WalletMovement]:
        query = self.db.query(WalletMovement)
        if start_date:
            query = query.filter(cast(Any, WalletMovement.timestamp >= start_date))
        if end_date:
            query = query.filter(cast(Any, WalletMovement.timestamp <= end_date))
        if asset:
            query = query.filter(WalletMovement.asset == asset)
        if movement_type:
            query = query.filter(WalletMovement.movement_type == movement_type)
        results = query.order_by(WalletMovement.timestamp.asc()).all()
        return cast(list[WalletMovement], results)

    def list_completed(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        asset: str | None = None,
        movement_type: str | None = None,
    ) -> list[WalletMovement]:
        query = self.db.query(WalletMovement).filter(WalletMovement.status == "COMPLETED")
        if start_date:
            query = query.filter(cast(Any, WalletMovement.timestamp >= start_date))
        if end_date:
            query = query.filter(cast(Any, WalletMovement.timestamp <= end_date))
        if asset:
            query = query.filter(WalletMovement.asset == asset)
        if movement_type:
            query = query.filter(WalletMovement.movement_type == movement_type)
        results = query.order_by(WalletMovement.timestamp.asc()).all()
        return cast(list[WalletMovement], results)


class BankVoucherRepository:
    """Acceso a comprobantes bancarios en bolívares (Pago Móvil / Transferencias)."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, voucher: BankVoucher) -> BankVoucher:
        self.db.add(voucher)
        self.db.commit()
        self.db.refresh(voucher)
        return voucher

    def get_by_reference(self, reference_number: str) -> BankVoucher | None:
        result = self.db.query(BankVoucher).filter(BankVoucher.reference_number == reference_number).first()
        return cast(BankVoucher | None, result)

    def list_unmatched(self) -> list[BankVoucher]:
        results = (
            self.db.query(BankVoucher)
            .filter(BankVoucher.verification_status == "UNMATCHED")
            .order_by(BankVoucher.created_at.desc())
            .all()
        )
        return cast(list[BankVoucher], results)

    def match_with_order(self, voucher_id: int, order_number: str) -> BankVoucher | None:
        voucher = self.db.query(BankVoucher).filter(BankVoucher.id == voucher_id).first()
        if voucher:
            voucher.associated_order_number = order_number  # type: ignore[assignment]
            voucher.verification_status = "MATCHED"  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(voucher)
            return cast(BankVoucher, voucher)
        return None


class FiscalSnapshotRepository:
    """Gestor de snapshots mensuales y reconciliación contable de 6 piezas."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_period(self, period: str) -> FiscalPeriodSnapshot | None:
        result = self.db.query(FiscalPeriodSnapshot).filter(FiscalPeriodSnapshot.period == period).first()
        return cast(FiscalPeriodSnapshot | None, result)

    def get_latest_snapshot(self) -> FiscalPeriodSnapshot | None:
        result = (
            self.db.query(FiscalPeriodSnapshot)
            .order_by(FiscalPeriodSnapshot.period.desc())
            .first()
        )
        return cast(FiscalPeriodSnapshot | None, result)

    def upsert_snapshot(self, snapshot: FiscalPeriodSnapshot) -> FiscalPeriodSnapshot:
        existing = self.get_by_period(str(snapshot.period))
        if not existing:
            self.db.add(snapshot)
            self.db.commit()
            self.db.refresh(snapshot)
            return snapshot

        existing.initial_balance = snapshot.initial_balance  # type: ignore[assignment]
        existing.inflows_deposits = snapshot.inflows_deposits  # type: ignore[assignment]
        existing.inflows_p2p_buys = snapshot.inflows_p2p_buys  # type: ignore[assignment]
        existing.outflows_withdrawals = snapshot.outflows_withdrawals  # type: ignore[assignment]
        existing.outflows_p2p_sells = snapshot.outflows_p2p_sells  # type: ignore[assignment]
        existing.volume_operated = snapshot.volume_operated  # type: ignore[assignment]
        existing.total_fees = snapshot.total_fees  # type: ignore[assignment]
        existing.calculated_final_balance = snapshot.calculated_final_balance  # type: ignore[assignment]
        existing.actual_final_balance = snapshot.actual_final_balance  # type: ignore[assignment]
        existing.discrepancy = snapshot.discrepancy  # type: ignore[assignment]
        existing.gross_revenue_ves = snapshot.gross_revenue_ves  # type: ignore[assignment]
        existing.acquisition_cost_ves = snapshot.acquisition_cost_ves  # type: ignore[assignment]
        existing.net_profit_ves = snapshot.net_profit_ves  # type: ignore[assignment]
        existing.net_profit_usd = snapshot.net_profit_usd  # type: ignore[assignment]
        existing.status = snapshot.status  # type: ignore[assignment]

        self.db.commit()
        self.db.refresh(existing)
        return cast(FiscalPeriodSnapshot, existing)

