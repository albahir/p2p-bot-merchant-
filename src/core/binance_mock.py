"""Simulador local (Sandbox/Mock) para Binance P2P.
Permite simular la ingesta y flujo completo de órdenes P2P sin requerir claves reales ni arriesgar capital.
Cumple estrictamente con los esquemas Pydantic oficiales de Binance (BinanceOrderHistoryResponse, BinanceSearchResponse).
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

from src.core.binance_schemas import (
    BinanceAdDetail,
    BinanceAdvertiserInfo,
    BinanceOrderHistoryResponse,
    BinanceOrderMatchItem,
    BinanceSearchOrderItem,
    BinanceSearchResponse,
    BinanceTradeMethod,
    TradeTypeEnum,
)

logger = logging.getLogger("binance_mock_client")


class MockBinanceP2PClient:
    """Simulador realista de la API C2C/P2P de Binance para pruebas y modo Sandbox en Mission Control."""

    def __init__(
        self,
        api_key: str = "mock_api_key_test_sandbox",
        private_key_pem: str = "mock_private_key_pem",
        base_url: str = "https://mock.binance.local",
        recv_window: int = 5000,
        enable_default_orders: bool = True
    ):
        self.api_key = api_key
        self.private_key_pem = private_key_pem
        self.base_url = base_url
        self.recv_window = recv_window
        self.last_used_weight = 45
        self.orders: list[dict[str, Any]] = []

        if enable_default_orders:
            self._load_realistic_default_orders()

    def _load_realistic_default_orders(self) -> None:
        """Carga un ciclo de comercio P2P realista de un comerciante en Venezuela (VES/USDT).
        Incluye compras de inventario (bid), ventas con spread (ask), comisiones y una orden cancelada.
        """
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        day_ms = 24 * 60 * 60 * 1000

        self.orders = [
            # 1. Compra Lote 1: 100 USDT @ 36.50 VES (hace 3 días)
            {
                "orderNumber": "202610140001",
                "advNo": "ADV_BUY_101",
                "tradeType": "BUY",
                "asset": "USDT",
                "fiat": "VES",
                "fiatSymbol": "Bs",
                "amount": "100.00000000",
                "totalPrice": "3650.00000000",
                "unitPrice": "36.5000",
                "orderStatus": "COMPLETED",
                "createTime": now_ms - (3 * day_ms),
                "advertisementRole": "MAKER",
                "commission": "3.65",  # 0.1% comisión maker en VES
                "takerCommission": "0.00",
                "counterPartNickName": "Vendedor_Seguro_01"
            },
            # 2. Compra Lote 2: 150 USDT @ 36.60 VES (hace 2 días)
            {
                "orderNumber": "202610140002",
                "advNo": "ADV_BUY_102",
                "tradeType": "BUY",
                "asset": "USDT",
                "fiat": "VES",
                "fiatSymbol": "Bs",
                "amount": "150.00000000",
                "totalPrice": "5490.00000000",
                "unitPrice": "36.6000",
                "orderStatus": "COMPLETED",
                "createTime": now_ms - (2 * day_ms),
                "advertisementRole": "MAKER",
                "commission": "5.49",  # 0.1% comisión
                "takerCommission": "0.00",
                "counterPartNickName": "P2P_Trader_Vzla"
            },
            # 3. Orden Cancelada (no debe impactar inventario ni impuestos) (hace 1 día)
            {
                "orderNumber": "202610140003",
                "advNo": "ADV_BUY_102",
                "tradeType": "BUY",
                "asset": "USDT",
                "fiat": "VES",
                "fiatSymbol": "Bs",
                "amount": "50.00000000",
                "totalPrice": "1825.00000000",
                "unitPrice": "36.5000",
                "orderStatus": "CANCELLED",
                "createTime": now_ms - (1 * day_ms + 3600000),
                "advertisementRole": "MAKER",
                "commission": "0.00",
                "takerCommission": "0.00",
                "counterPartNickName": "Usuario_Inactivo"
            },
            # 4. Venta Lote Parcial 1: 120 USDT @ 37.80 VES (hace 18 horas) -> Margen positivo
            {
                "orderNumber": "202610140004",
                "advNo": "ADV_SELL_201",
                "tradeType": "SELL",
                "asset": "USDT",
                "fiat": "VES",
                "fiatSymbol": "Bs",
                "amount": "120.00000000",
                "totalPrice": "4536.00000000",
                "unitPrice": "37.8000",
                "orderStatus": "COMPLETED",
                "createTime": now_ms - (18 * 3600 * 1000),
                "advertisementRole": "MAKER",
                "commission": "4.54",  # 0.1% comisión
                "takerCommission": "0.00",
                "counterPartNickName": "Comprador_PagoMovil"
            },
            # 5. Venta Lote Parcial 2: 130 USDT @ 38.00 VES (hace 6 horas) -> Cierra posición con ganancia
            {
                "orderNumber": "202610140005",
                "advNo": "ADV_SELL_202",
                "tradeType": "SELL",
                "asset": "USDT",
                "fiat": "VES",
                "fiatSymbol": "Bs",
                "amount": "130.00000000",
                "totalPrice": "4940.00000000",
                "unitPrice": "38.0000",
                "orderStatus": "COMPLETED",
                "createTime": now_ms - (6 * 3600 * 1000),
                "advertisementRole": "MAKER",
                "commission": "4.94",  # 0.1% comisión
                "takerCommission": "0.00",
                "counterPartNickName": "Inversor_Caracas"
            }
        ]

    def add_simulated_trade(
        self,
        order_number: str,
        trade_type: str,
        amount: float,
        unit_price: float,
        fee_fiat: float = 0.0,
        status: str = "COMPLETED",
        asset: str = "USDT",
        fiat: str = "VES",
        counterpart: str = "Simulated_User"
    ) -> dict[str, Any]:
        """Permite a tests y simulaciones agregar operaciones en tiempo de ejecución."""
        total_price = round(amount * unit_price, 2)
        order = {
            "orderNumber": order_number,
            "advNo": f"ADV_SIM_{order_number}",
            "tradeType": trade_type.upper(),
            "asset": asset,
            "fiat": fiat,
            "fiatSymbol": "Bs" if fiat == "VES" else "$",
            "amount": f"{amount:.8f}",
            "totalPrice": f"{total_price:.8f}",
            "unitPrice": f"{unit_price:.4f}",
            "orderStatus": status.upper(),
            "createTime": int(time.time() * 1000),
            "advertisementRole": "MAKER",
            "commission": f"{fee_fiat:.2f}",
            "takerCommission": "0.00",
            "counterPartNickName": counterpart
        }
        self.orders.append(order)
        return order

    def check_weight(self, headers: Any | None = None) -> None:
        """Simula monitoreo de peso de API."""
        logger.debug(f"MOCK API Used Weight: {self.last_used_weight}")

    def search_p2p_ads(
        self,
        asset: str = "USDT",
        fiat: str = "VES",
        trade_type: str = "BUY",
        page: int = 1,
        rows: int = 10,
        pay_types: list[str] | None = None,
        trans_amount: float | None = None,
        merchant_check: bool = False,
        use_public_bapi: bool = False,
    ) -> BinanceSearchResponse:
        """Devuelve un order book simulado realista con anunciantes activos y bancos en Venezuela."""
        # Precios calibrados según el mercado VES (~1001 a 1018 VES)
        base_price = 1002.50 if trade_type == "BUY" else 1012.80

        merchant_data = [
            ("Merchant_Caracas_P2P", 1450, 0.995, ["Banco de Venezuela", "Pago Móvil"], ["SpecificBank", "PagoMovil"]),
            ("Cambios_Express_VE", 980, 0.991, ["Banesco", "Pago Móvil"], ["Banesco", "PagoMovil"]),
            ("PagoMovil_Seguro", 1200, 0.989, ["Pago Móvil"], ["PagoMovil"]),
            ("Crypto_Vzla_OFICIAL", 3200, 0.998, ["Mercantil", "Banesco"], ["Mercantil", "Banesco"]),
            ("Finanzas_Rapidas_VE", 640, 0.985, ["Bancamiga", "Banco de Venezuela"], ["Bancamiga", "SpecificBank"]),
            ("Banesco_PagoMovil_P2P", 890, 0.992, ["Banesco"], ["Banesco"]),
            ("Provincial_Instant", 430, 0.981, ["BBVA Banco Provincial"], ["BBVABancoProvincial"]),
            ("Mercantil_Directo", 1100, 0.994, ["Mercantil"], ["Mercantil"]),
            ("BNC_Crypto_Fast", 520, 0.987, ["BNC", "Pago Móvil"], ["BancoNacionaldeCredito", "PagoMovil"]),
            ("Activo_Cambios", 310, 0.982, ["Banco Activo"], ["BancoActivo"]),
        ]

        items = []
        for i, (name, orders_count, finish_rate, bank_labels, pay_type_codes) in enumerate(merchant_data):
            if merchant_check and orders_count < 500:
                continue

            # Si se especificó pay_types, comprobar coincidencia
            if pay_types:
                matched = False
                for pt in pay_types:
                    pt_clean = pt.strip().lower()
                    if any(pt_clean in code.lower() or pt_clean in label.lower() for code in pay_type_codes for label in bank_labels):
                        matched = True
                        break
                if not matched:
                    continue

            price_offset = round(i * 0.40, 2)
            calculated_price = round(base_price - price_offset if trade_type == "BUY" else base_price + price_offset, 2)

            min_amt = 500.0 + (i * 200.0)
            max_amt = 50000.0 + (i * 5000.0)
            if trans_amount is not None and (trans_amount < min_amt or trans_amount > max_amt):
                continue

            methods = [
                BinanceTradeMethod(
                    tradeMethodName=label,
                    payType=code,
                    tradeMethodShortName=label,
                )
                for label, code in zip(bank_labels, pay_type_codes)
            ]

            item = BinanceSearchOrderItem(
                adv=BinanceAdDetail(
                    advNo=f"11002233{i+1:03d}",
                    tradeType=TradeTypeEnum(trade_type),
                    asset=asset,
                    fiatUnit=fiat,
                    price=str(calculated_price),
                    surplusAmount=str(1000.0 + (i * 250.0)),
                    minSingleTransAmount=f"{min_amt:.2f}",
                    maxSingleTransAmount=f"{max_amt:.2f}",
                    tradeMethods=methods,
                ),
                advertiser=BinanceAdvertiserInfo(
                    nickName=name,
                    monthOrderCount=orders_count,
                    monthFinishRate=finish_rate,
                ),
            )
            items.append(item)
            if len(items) >= rows:
                break

        return BinanceSearchResponse(
            code="000000",
            message="SUCCESS",
            success=True,
            total=len(items),
            data=items,
        )

    def get_order_book(
        self,
        asset: str = "USDT",
        fiat: str = "VES",
        trade_type: str = "BUY",
        page: int = 1,
        rows: int = 10,
        pay_types: list[str] | None = None,
        trans_amount: float | None = None,
        merchant_check: bool = False,
    ) -> BinanceSearchResponse:
        """Alias retrocompatible para search_p2p_ads."""
        return self.search_p2p_ads(
            asset=asset,
            fiat=fiat,
            trade_type=trade_type,
            page=page,
            rows=rows,
            pay_types=pay_types,
            trans_amount=trans_amount,
            merchant_check=merchant_check,
        )

    def get_order_history(
        self,
        trade_type: str,
        start_timestamp: int,
        end_timestamp: int,
        page: int = 1,
        rows: int = 50
    ) -> BinanceOrderHistoryResponse:
        """Devuelve el histórico simulado filtrado por trade_type (BUY, SELL o ALL).
        Cumple estrictamente con la ventana máxima de 30 días y validación de tipos Pydantic.
        """
        thirty_days_ms = 30 * 24 * 60 * 60 * 1000
        if (end_timestamp - start_timestamp) > thirty_days_ms:
            raise ValueError("FAIL-CLOSED: La ventana de consulta histórica no puede superar los 30 días.")

        # Filtrar por tipo
        t_filter = trade_type.upper()
        if t_filter in ("BUY", "SELL"):
            filtered_raw = [o for o in self.orders if o["tradeType"] == t_filter]
        else:
            filtered_raw = list(self.orders)

        # Convertir a objetos validados Pydantic
        items = [BinanceOrderMatchItem.model_validate(o) for o in filtered_raw]

        return BinanceOrderHistoryResponse(
            code="000000",
            message="SUCCESS",
            success=True,
            total=len(items),
            data=items
        )

    def create_ad(self, ad_payload: dict[str, Any]) -> dict[str, Any]:
        return {"code": "000000", "message": "SUCCESS", "data": "MOCK_ADV_NEW_001", "success": True}

    def update_ad(self, ad_no: str, update_payload: dict[str, Any]) -> dict[str, Any]:
        return {"code": "000000", "message": "SUCCESS", "data": True, "success": True}

    def pause_ad(self, ad_no: str) -> dict[str, Any]:
        return {"code": "000000", "message": "SUCCESS", "data": True, "success": True}
