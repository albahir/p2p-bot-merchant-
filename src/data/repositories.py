"""Repositorios de datos siguiendo el patrón Repository para acceso seguro y desacoplado."""

from datetime import datetime

from sqlalchemy.orm import Session

from src.data.models import (
    BankVoucher,
    EncryptedSecret,
    FiscalPeriodSnapshot,
    IdentityCache,
    Order,
    SecurityEvent,
    User,
    WalletMovement,
)


class OrderRepository:
    """Acceso a datos de órdenes para ingesta, motor fiscal y dashboard."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_order_number(self, order_number: str) -> Order | None:
        return self.db.query(Order).filter(Order.order_number == order_number).first()

    def create(self, order: Order) -> Order:
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def list_completed(self, start_date: datetime | None = None, end_date: datetime | None = None) -> list[Order]:
        query = self.db.query(Order).filter(Order.order_status == "COMPLETED")
        if start_date:
            query = query.filter(Order.created_at >= start_date)  # type: ignore[arg-type]
        if end_date:
            query = query.filter(Order.created_at <= end_date)  # type: ignore[arg-type]
        return query.order_by(Order.created_at.asc()).all()

    def list_paginated(
        self,
        skip: int = 0,
        limit: int = 50,
        trade_type: str | None = None,
        order_status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        search: str | None = None,
    ) -> tuple[int, list[Order]]:
        query = self.db.query(Order)
        if trade_type:
            query = query.filter(Order.trade_type == trade_type.upper())
        if order_status:
            query = query.filter(Order.order_status == order_status.upper())
        if start_date:
            query = query.filter(Order.created_at >= start_date)  # type: ignore[arg-type]
        if end_date:
            query = query.filter(Order.created_at <= end_date)  # type: ignore[arg-type]
        if search:
            s = f"%{search}%"
            query = query.filter(
                (Order.order_number.like(s)) | (Order.counterparty_name.like(s))
            )
        total = query.count()
        items = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
        return total, items


class SecurityRepository:
    """Acceso a eventos de auditoría y almacenamiento de secretos."""

    def __init__(self, db: Session):
        self.db = db

    def get_last_event(self) -> SecurityEvent | None:
        return self.db.query(SecurityEvent).order_by(SecurityEvent.id.desc()).first()

    def log_event(self, event: SecurityEvent) -> SecurityEvent:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_secret(self, key_name: str) -> EncryptedSecret | None:
        return self.db.query(EncryptedSecret).filter(EncryptedSecret.key_name == key_name).first()

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
        return secret


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
        return self.db.query(WalletMovement).filter(WalletMovement.txid == txid).first()

    def list_by_period(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        asset: str | None = None,
        movement_type: str | None = None,
    ) -> list[WalletMovement]:
        query = self.db.query(WalletMovement)
        if start_date:
            query = query.filter(WalletMovement.timestamp >= start_date)  # type: ignore[arg-type]
        if end_date:
            query = query.filter(WalletMovement.timestamp <= end_date)  # type: ignore[arg-type]
        if asset:
            query = query.filter(WalletMovement.asset == asset)
        if movement_type:
            query = query.filter(WalletMovement.movement_type == movement_type)
        return query.order_by(WalletMovement.timestamp.asc()).all()

    def list_completed(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        asset: str | None = None,
        movement_type: str | None = None,
    ) -> list[WalletMovement]:
        query = self.db.query(WalletMovement).filter(WalletMovement.status == "COMPLETED")
        if start_date:
            query = query.filter(WalletMovement.timestamp >= start_date)  # type: ignore[arg-type]
        if end_date:
            query = query.filter(WalletMovement.timestamp <= end_date)  # type: ignore[arg-type]
        if asset:
            query = query.filter(WalletMovement.asset == asset)
        if movement_type:
            query = query.filter(WalletMovement.movement_type == movement_type)
        return query.order_by(WalletMovement.timestamp.asc()).all()


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
        return self.db.query(BankVoucher).filter(BankVoucher.reference_number == reference_number).first()

    def list_unmatched(self) -> list[BankVoucher]:
        return (
            self.db.query(BankVoucher)
            .filter(BankVoucher.verification_status == "UNMATCHED")
            .order_by(BankVoucher.created_at.desc())
            .all()
        )

    def match_with_order(self, voucher_id: int, order_number: str) -> BankVoucher | None:
        voucher = self.db.query(BankVoucher).filter(BankVoucher.id == voucher_id).first()
        if voucher:
            voucher.associated_order_number = order_number  # type: ignore[assignment]
            voucher.verification_status = "MATCHED"  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(voucher)
            return voucher
        return None


class FiscalSnapshotRepository:
    """Gestor de snapshots mensuales y reconciliación contable de 6 piezas."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_period(self, period: str) -> FiscalPeriodSnapshot | None:
        return self.db.query(FiscalPeriodSnapshot).filter(FiscalPeriodSnapshot.period == period).first()

    def get_latest_snapshot(self) -> FiscalPeriodSnapshot | None:
        return (
            self.db.query(FiscalPeriodSnapshot)
            .order_by(FiscalPeriodSnapshot.period.desc())
            .first()
        )

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
        return existing


class UserRepository:
    """Acceso y gestión de usuarios del sistema y roles RBAC."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_telegram_id(self, telegram_id: str | int) -> User | None:
        return self.db.query(User).filter(User.telegram_id == str(telegram_id)).first()

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "INVITADO",
        telegram_id: str | int | None = None,
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            telegram_id=str(telegram_id) if telegram_id is not None else None,
            is_active=is_active,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_role(self, user_id: int, role: str) -> User | None:
        user = self.get_by_id(user_id)
        if user:
            user.role = role  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(user)
            return user
        return None

    def set_active_status(self, user_id: int, is_active: bool) -> User | None:
        user = self.get_by_id(user_id)
        if user:
            user.is_active = is_active  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(user)
            return user
        return None

    def update_password(self, user_id: int, new_password_hash: str) -> User | None:
        user = self.get_by_id(user_id)
        if user:
            user.password_hash = new_password_hash  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(user)
            return user
        return None

    def list_all(self) -> list[User]:
        return self.db.query(User).order_by(User.id.asc()).all()


class IdentityRepository:
    """Acceso y almacenamiento persistente de identidades consultadas (Cédula -> Titular)."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_cedula(self, nationality: str, cedula: str) -> IdentityCache | None:
        """Busca una identidad por nacionalidad y número de cédula."""
        nat = nationality.strip().upper()
        clean_num = "".join(filter(str.isdigit, cedula))
        return (
            self.db.query(IdentityCache)
            .filter(IdentityCache.nationality == nat, IdentityCache.cedula == clean_num)
            .first()
        )

    def upsert(
        self,
        nationality: str,
        cedula: str,
        full_name: str,
        source: str = "MANUAL",
        queried_by: str | None = None,
    ) -> IdentityCache:
        """Guarda o actualiza de forma permanente la identidad consultada en la base de datos."""
        nat = nationality.strip().upper() or "V"
        clean_num = "".join(filter(str.isdigit, cedula))
        name = full_name.strip().upper()

        record = self.get_by_cedula(nat, clean_num)
        if not record:
            record = IdentityCache(
                nationality=nat,
                cedula=clean_num,
                full_name=name,
                source=source,
                queried_by=queried_by,
            )
            self.db.add(record)
        else:
            record.full_name = name  # type: ignore[assignment]
            record.source = source  # type: ignore[assignment]
            if queried_by and not record.queried_by:
                record.queried_by = queried_by  # type: ignore[assignment]

        self.db.commit()
        self.db.refresh(record)
        return record

    def list_all(self, limit: int = 200) -> list[IdentityCache]:
        """Retorna las identidades consultadas y almacenadas ordenadas por más recientes."""
        return (
            self.db.query(IdentityCache)
            .order_by(IdentityCache.id.desc())
            .limit(limit)
            .all()
        )

    def search(self, query: str) -> list[IdentityCache]:
        """Busca identidades por coincidencia en número de cédula o nombre."""
        q = f"%{query.strip().upper()}%"
        return (
            self.db.query(IdentityCache)
            .filter(
                (IdentityCache.cedula.like(q)) | (IdentityCache.full_name.like(q))
            )
            .order_by(IdentityCache.id.desc())
            .limit(50)
            .all()
        )

    def count(self) -> int:
        return self.db.query(IdentityCache).count()


