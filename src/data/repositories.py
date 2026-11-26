"""Repositorios de datos siguiendo el patrón Repository para acceso seguro y desacoplado."""

from datetime import date, datetime
from typing import Any, cast

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.data.models import (
    BankVoucher,
    BCVRateHistory,
    EncryptedSecret,
    FiscalPeriodSnapshot,
    IdentityCache,
    JournalEntry,
    MarketHourlyRollup,
    MarketSnapshot,
    Order,
    SecurityEvent,
    User,
    WalletMovement,
)


def _apply_user_scope(db: Session, query: Any, model_cls: Any, user_id: int | None) -> Any:
    """Aisla estrictamente las consultas por propietario confidencial (user_id).
    Un usuario autenticado jamás lee registros de otro operador ni filas huérfanas (user_id IS NULL).
    """
    _ = db
    if user_id is None:
        return query
    return query.filter(model_cls.user_id == user_id)


class OrderRepository:
    """Acceso a datos de órdenes para ingesta, motor fiscal y dashboard."""

    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def get_by_order_number(self, order_number: str, user_id: int | None = None) -> Order | None:
        uid = user_id if user_id is not None else self.user_id
        q = self.db.query(Order).filter(Order.order_number == order_number)
        q = _apply_user_scope(self.db, q, Order, uid)
        return q.first()

    def create(self, order: Order) -> Order:
        if order.user_id is None and self.user_id is not None:
            order.user_id = self.user_id  # type: ignore[assignment]
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def list_completed(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        user_id: int | None = None,
    ) -> list[Order]:
        uid = user_id if user_id is not None else self.user_id
        query = self.db.query(Order).filter(Order.order_status == "COMPLETED")
        query = _apply_user_scope(self.db, query, Order, uid)
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
        user_id: int | None = None,
        payment_method: str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        sort_by: str = "date_desc",
    ) -> tuple[int, list[Order]]:
        uid = user_id if user_id is not None else self.user_id
        query = _apply_user_scope(self.db, self.db.query(Order), Order, uid)
        if trade_type:
            query = query.filter(Order.trade_type == trade_type.upper())
        if order_status:
            norm_status = order_status.strip().upper()
            if norm_status == "CANCELLED":
                query = query.filter(Order.order_status.in_(["CANCELLED", "CANCELLED_BY_SYSTEM"]))
            else:
                query = query.filter(Order.order_status == norm_status)
        if payment_method and payment_method.strip():
            pm_pattern = f"%{payment_method.strip()}%"
            query = query.filter(Order.payment_method.ilike(pm_pattern))
        if min_amount is not None:
            query = query.filter(Order.crypto_amount >= float(min_amount))  # type: ignore[arg-type]
        if max_amount is not None:
            query = query.filter(Order.crypto_amount <= float(max_amount))  # type: ignore[arg-type]
        if start_date:
            query = query.filter(Order.created_at >= start_date)  # type: ignore[arg-type]
        if end_date:
            query = query.filter(Order.created_at <= end_date)  # type: ignore[arg-type]
        if search:
            s = f"%{search}%"
            query = query.filter(
                (Order.order_number.ilike(s))
                | (Order.counterparty_name.ilike(s))
                | (Order.payment_method.ilike(s))
            )
        total = query.count()
        sort_map = {
            "date_desc": Order.created_at.desc(),
            "date_asc": Order.created_at.asc(),
            "amount_desc": Order.crypto_amount.desc(),
            "amount_asc": Order.crypto_amount.asc(),
            "price_desc": Order.unit_price.desc(),
            "price_asc": Order.unit_price.asc(),
        }
        order_clause = sort_map.get(sort_by, Order.created_at.desc())
        items = query.order_by(order_clause, Order.id.desc()).offset(skip).limit(limit).all()
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

    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def create(self, movement: WalletMovement) -> WalletMovement:
        if movement.user_id is None and self.user_id is not None:
            movement.user_id = self.user_id  # type: ignore[assignment]
        self.db.add(movement)
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def get_by_txid(self, txid: str, user_id: int | None = None) -> WalletMovement | None:
        uid = user_id if user_id is not None else self.user_id
        q = self.db.query(WalletMovement).filter(WalletMovement.txid == txid)
        q = _apply_user_scope(self.db, q, WalletMovement, uid)
        return q.first()

    def list_by_period(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        asset: str | None = None,
        movement_type: str | None = None,
        user_id: int | None = None,
    ) -> list[WalletMovement]:
        uid = user_id if user_id is not None else self.user_id
        query = _apply_user_scope(self.db, self.db.query(WalletMovement), WalletMovement, uid)
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
        user_id: int | None = None,
    ) -> list[WalletMovement]:
        uid = user_id if user_id is not None else self.user_id
        query = self.db.query(WalletMovement).filter(WalletMovement.status == "COMPLETED")
        query = _apply_user_scope(self.db, query, WalletMovement, uid)
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

    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def create(self, voucher: BankVoucher, auto_commit: bool = True) -> BankVoucher:
        if voucher.user_id is None and self.user_id is not None:
            voucher.user_id = self.user_id  # type: ignore[assignment]
        self.db.add(voucher)
        if auto_commit:
            self.db.commit()
            self.db.refresh(voucher)
        else:
            self.db.flush()
        return voucher

    def get_by_reference(self, reference_number: str, user_id: int | None = None) -> BankVoucher | None:
        uid = user_id if user_id is not None else self.user_id
        q = self.db.query(BankVoucher).filter(BankVoucher.reference_number == reference_number)
        q = _apply_user_scope(self.db, q, BankVoucher, uid)
        return q.first()

    def list_unmatched(self, user_id: int | None = None) -> list[BankVoucher]:
        uid = user_id if user_id is not None else self.user_id
        q = self.db.query(BankVoucher).filter(BankVoucher.verification_status == "UNMATCHED")
        q = _apply_user_scope(self.db, q, BankVoucher, uid)
        return q.order_by(BankVoucher.created_at.desc()).all()

    def match_with_order(self, voucher_id: int, order_number: str) -> BankVoucher | None:
        voucher = self.get_by_id(voucher_id)
        if voucher:
            voucher.associated_order_number = order_number  # type: ignore[assignment]
            voucher.verification_status = "MATCHED"  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(voucher)
            return voucher
        return None

    def get_by_id(self, voucher_id: int, user_id: int | None = None) -> BankVoucher | None:
        uid = user_id if user_id is not None else self.user_id
        q = self.db.query(BankVoucher).filter(BankVoucher.id == voucher_id)
        q = _apply_user_scope(self.db, q, BankVoucher, uid)
        return q.first()

    def update(self, voucher: BankVoucher) -> BankVoucher:
        self.db.commit()
        self.db.refresh(voucher)
        return voucher

    def list_all(self, limit: int = 500, user_id: int | None = None) -> list[BankVoucher]:
        uid = user_id if user_id is not None else self.user_id
        q = _apply_user_scope(self.db, self.db.query(BankVoucher), BankVoucher, uid)
        return q.order_by(BankVoucher.created_at.desc()).limit(limit).all()

    def list_associated_order_numbers(self, user_id: int | None = None) -> set[str]:
        """Retorna el conjunto completo de órdenes ya conciliadas del usuario sin truncar por límite de filas."""
        uid = user_id if user_id is not None else self.user_id
        q: Any = self.db.query(BankVoucher.associated_order_number).filter(
            cast(Any, BankVoucher.associated_order_number).is_not(None)
        )
        q = _apply_user_scope(self.db, q, BankVoucher, uid)
        return {str(row[0]) for row in q.distinct().all() if row[0]}

    def list_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: int | None = None,
    ) -> list[BankVoucher]:
        """Retorna todos los comprobantes del usuario dentro de una ventana temporal (sin límite arbitrario)."""
        uid = user_id if user_id is not None else self.user_id
        q = self.db.query(BankVoucher).filter(
            or_(
                and_(
                    cast(Any, BankVoucher.voucher_date).is_not(None),
                    cast(Any, BankVoucher.voucher_date >= start_date),
                    cast(Any, BankVoucher.voucher_date <= end_date),
                ),
                and_(
                    cast(Any, BankVoucher.voucher_date).is_(None),
                    cast(Any, BankVoucher.created_at >= start_date),
                    cast(Any, BankVoucher.created_at <= end_date),
                ),
            )
        )
        q = _apply_user_scope(self.db, q, BankVoucher, uid)
        return q.order_by(BankVoucher.created_at.desc()).all()


class FiscalSnapshotRepository:
    """Gestor de snapshots mensuales y reconciliación contable de 6 piezas."""

    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def get_by_period(self, period: str, user_id: int | None = None) -> FiscalPeriodSnapshot | None:
        uid = user_id if user_id is not None else self.user_id
        q = self.db.query(FiscalPeriodSnapshot).filter(FiscalPeriodSnapshot.period == period)
        q = _apply_user_scope(self.db, q, FiscalPeriodSnapshot, uid)
        return q.first()

    def get_latest_snapshot(self, user_id: int | None = None) -> FiscalPeriodSnapshot | None:
        uid = user_id if user_id is not None else self.user_id
        q = _apply_user_scope(self.db, self.db.query(FiscalPeriodSnapshot), FiscalPeriodSnapshot, uid)
        return q.order_by(FiscalPeriodSnapshot.period.desc()).first()

    def upsert_snapshot(self, snapshot: FiscalPeriodSnapshot) -> FiscalPeriodSnapshot:
        if snapshot.user_id is None and self.user_id is not None:
            snapshot.user_id = self.user_id  # type: ignore[assignment]
        uid = int(snapshot.user_id) if snapshot.user_id is not None else self.user_id
        existing = self.get_by_period(str(snapshot.period), user_id=uid)
        if not existing:
            self.db.add(snapshot)
            self.db.commit()
            self.db.refresh(snapshot)
            return snapshot

        existing.user_id = snapshot.user_id  # type: ignore[assignment]
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

    def get_by_email(self, email: str) -> User | None:
        clean_email = email.strip().lower()
        if not clean_email:
            return None
        return self.db.query(User).filter(User.email == clean_email).first()

    def get_by_telegram_id(self, telegram_id: str | int) -> User | None:
        return self.db.query(User).filter(User.telegram_id == str(telegram_id)).first()

    def get_by_identifier(self, identifier: str) -> User | None:
        """Busca un usuario por alias (username), correo electrónico o Telegram ID."""
        clean = identifier.strip()
        if not clean:
            return None
        user = self.get_by_username(clean)
        if user:
            return user
        if "@" in clean:
            user = self.get_by_email(clean)
            if user:
                return user
        return self.get_by_telegram_id(clean)

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "INVITADO",
        telegram_id: str | int | None = None,
        is_active: bool = True,
        full_name: str | None = None,
        tax_id: str | None = None,
        email: str | None = None,
        security_question: str | None = None,
        security_answer_hash: str | None = None,
        recovery_key_hash: str | None = None,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            telegram_id=str(telegram_id) if telegram_id is not None else None,
            is_active=is_active,
            full_name=full_name.strip() if full_name else None,
            tax_id=tax_id.strip().upper() if tax_id else None,
            email=email.strip().lower() if email else None,
            security_question=security_question.strip() if security_question else None,
            security_answer_hash=security_answer_hash,
            recovery_key_hash=recovery_key_hash,
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
            try:
                from src.api.deps import invalidate_user_auth_cache

                invalidate_user_auth_cache(user_id)
            except ImportError:
                pass
            return user
        return None

    def set_active_status(self, user_id: int, is_active: bool) -> User | None:
        user = self.get_by_id(user_id)
        if user:
            user.is_active = is_active  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(user)
            try:
                from src.api.deps import invalidate_user_auth_cache

                invalidate_user_auth_cache(user_id)
            except ImportError:
                pass
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


class BCVHistoryRepository:
    """Acceso persistente y consulta de tasas oficiales del BCV indexadas por Fecha Valor."""

    def __init__(self, db: Session):
        self.db = db

    def get_rate_by_date(self, fecha_valor: date) -> BCVRateHistory | None:
        """Obtiene la tasa oficial registrada para una Fecha Valor específica."""
        return (
            self.db.query(BCVRateHistory)
            .filter(BCVRateHistory.fecha_valor == fecha_valor)
            .first()
        )

    def upsert_rate(self, rate_item: BCVRateHistory) -> BCVRateHistory:
        """Inserta o actualiza la tasa oficial para la fecha valor dada (idempotente)."""
        existing = self.get_rate_by_date(cast(date, rate_item.fecha_valor))
        if existing:
            existing.usd_rate = rate_item.usd_rate  # type: ignore[assignment]
            existing.eur_rate = rate_item.eur_rate  # type: ignore[assignment]
            existing.source = rate_item.source  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(existing)
            return existing

        self.db.add(rate_item)
        self.db.commit()
        self.db.refresh(rate_item)
        return rate_item

    def list_rates(self, start_date: date, end_date: date) -> list[BCVRateHistory]:
        """Lista las tasas registradas en un rango de fechas ordenadas cronológicamente."""
        return (
            self.db.query(BCVRateHistory)
            .filter(
                BCVRateHistory.fecha_valor >= start_date,  # type: ignore[arg-type]
                BCVRateHistory.fecha_valor <= end_date,  # type: ignore[arg-type]
            )
            .order_by(BCVRateHistory.fecha_valor.asc())
            .all()
        )

    def get_latest_rate(self) -> BCVRateHistory | None:
        """Retorna la última tasa registrada en el sistema."""
        return (
            self.db.query(BCVRateHistory)
            .order_by(BCVRateHistory.fecha_valor.desc())
            .first()
        )


class JournalEntryRepository:
    """Gestor de asientos contables del Libro Diario con trazabilidad y encadenamiento criptográfico."""

    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def create_entry(self, entry: JournalEntry, auto_commit: bool = True) -> JournalEntry:
        """Persiste un asiento contable en el Libro Diario."""
        if entry.user_id is None and self.user_id is not None:
            entry.user_id = self.user_id  # type: ignore[assignment]
        self.db.add(entry)
        if auto_commit:
            self.db.commit()
            self.db.refresh(entry)
        return entry

    def get_next_entry_number(self, user_id: int | None = None) -> int:
        """Retorna el siguiente número consecutivo de asiento."""
        last = self.get_last_entry(user_id=user_id)
        return int(last.entry_number + 1) if last else 1

    def get_last_entry(self, user_id: int | None = None) -> JournalEntry | None:
        """Retorna la última línea asentada en el Libro Diario para mantener la cadena SHA-256 lineal."""
        uid = user_id if user_id is not None else self.user_id
        q = _apply_user_scope(self.db, self.db.query(JournalEntry), JournalEntry, uid)
        return q.order_by(JournalEntry.entry_number.desc(), JournalEntry.id.desc()).first()

    def list_entries(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        account_code: str | None = None,
        user_id: int | None = None,
    ) -> list[JournalEntry]:
        """Consulta asientos del Libro Diario dentro de un rango temporal opcional."""
        uid = user_id if user_id is not None else self.user_id
        query = _apply_user_scope(self.db, self.db.query(JournalEntry), JournalEntry, uid)
        if start_date:
            query = query.filter(JournalEntry.date_time >= start_date)  # type: ignore[arg-type]
        if end_date:
            query = query.filter(JournalEntry.date_time <= end_date)  # type: ignore[arg-type]
        if account_code:
            query = query.filter(JournalEntry.account_code == account_code)  # type: ignore[arg-type]
        return query.order_by(JournalEntry.entry_number.asc(), JournalEntry.id.asc()).all()

    def get_by_reference(self, reference: str, user_id: int | None = None) -> list[JournalEntry]:
        """Busca asientos asociados a una referencia bancaria específica."""
        uid = user_id if user_id is not None else self.user_id
        q = self.db.query(JournalEntry).filter(JournalEntry.reference == reference)
        q = _apply_user_scope(self.db, q, JournalEntry, uid)
        return q.all()


class MarketDataRepository:
    """Acceso histórico para instantáneas P2P minuto/ciclo y rollups horarios OHLC (SPEC-025)."""

    def __init__(self, db: Session):
        self.db = db

    def add_snapshot(self, snapshot: MarketSnapshot) -> MarketSnapshot:
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def list_snapshots(
        self,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        limit: int = 1000,
    ) -> list[MarketSnapshot]:
        q = self.db.query(MarketSnapshot)
        if start_dt is not None:
            q = q.filter(MarketSnapshot.timestamp >= start_dt)  # type: ignore[arg-type]
        if end_dt is not None:
            q = q.filter(MarketSnapshot.timestamp <= end_dt)  # type: ignore[arg-type]
        rows = q.order_by(MarketSnapshot.timestamp.desc()).limit(limit).all()
        rows.reverse()
        return rows

    def get_latest_snapshot(self) -> MarketSnapshot | None:
        return self.db.query(MarketSnapshot).order_by(MarketSnapshot.timestamp.desc()).first()

    def get_rollup_by_hour(self, hora_utc: datetime) -> MarketHourlyRollup | None:
        return (
            self.db.query(MarketHourlyRollup)
            .filter(MarketHourlyRollup.hora_utc == hora_utc)
            .first()
        )

    def upsert_hourly_rollup(self, rollup: MarketHourlyRollup) -> MarketHourlyRollup:
        existing = self.get_rollup_by_hour(cast(datetime, rollup.hora_utc))
        if not existing:
            self.db.add(rollup)
            self.db.commit()
            self.db.refresh(rollup)
            return rollup

        ex = cast(Any, existing)
        rl = cast(Any, rollup)
        ex.buy_high = max(float(ex.buy_high), float(rl.buy_high))
        ex.buy_low = min(float(ex.buy_low), float(rl.buy_low))
        ex.buy_close = float(rl.buy_close)
        ex.sell_high = max(float(ex.sell_high), float(rl.sell_high))
        ex.sell_low = min(float(ex.sell_low), float(rl.sell_low))
        ex.sell_close = float(rl.sell_close)
        ex.bcv_close = float(rl.bcv_close)
        ex.brecha_close = float(rl.brecha_close)
        ex.vol_buy_sum = float(rl.vol_buy_sum)
        ex.vol_sell_sum = float(rl.vol_sell_sum)
        ex.samples_count = int(ex.samples_count) + int(rl.samples_count)
        ex.bank_matrix_json = rl.bank_matrix_json
        self.db.commit()
        self.db.refresh(existing)
        return existing

    def list_hourly_rollups(
        self,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        limit: int = 1000,
    ) -> list[MarketHourlyRollup]:
        q = self.db.query(MarketHourlyRollup)
        if start_dt is not None:
            q = q.filter(MarketHourlyRollup.hora_utc >= start_dt)  # type: ignore[arg-type]
        if end_dt is not None:
            q = q.filter(MarketHourlyRollup.hora_utc <= end_dt)  # type: ignore[arg-type]
        rows = q.order_by(MarketHourlyRollup.hora_utc.desc()).limit(limit).all()
        rows.reverse()
        return rows

    def prune_old_snapshots(self, days_keep: int = 30, now_utc: datetime | None = None) -> int:
        """Elimina snapshots minuciosos antiguos preservando los rollups horarios OHLC."""
        from src.core.market_analytics import clear_stale_hourly_cutoff

        cutoff = clear_stale_hourly_cutoff(now_utc=now_utc, days_keep=max(1, int(days_keep)))
        deleted = (
            self.db.query(MarketSnapshot)
            .filter(MarketSnapshot.timestamp < cutoff)  # type: ignore[arg-type]
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return int(deleted or 0)



