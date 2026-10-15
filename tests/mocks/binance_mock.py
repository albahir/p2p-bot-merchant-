"""Mocks y respuestas simuladas para pruebas de la API Binance P2P."""

from typing import Dict, Any

MOCK_ORDER_BOOK: Dict[str, Any] = {
    "code": "000000",
    "message": "SUCCESS",
    "data": [
        {
            "adv": {
                "advNo": "11223344",
                "tradeType": "BUY",
                "asset": "USDT",
                "fiatUnit": "VES",
                "price": "36.80",
                "surplusAmount": "1000.00"
            },
            "advertiser": {
                "nickName": "MerchantPro",
                "monthOrderCount": 250,
                "monthFinishRate": 0.99
            }
        }
    ],
    "total": 1,
    "success": True
}

MOCK_USER_ORDER_HISTORY: Dict[str, Any] = {
    "code": "000000",
    "message": "SUCCESS",
    "data": [
        {
            "orderNumber": "BINANCE_ORD_001",
            "advNo": "11223344",
            "tradeType": "BUY",
            "asset": "USDT",
            "fiat": "VES",
            "totalPrice": "3650.00",
            "amount": "100.00",
            "unitPrice": "36.50",
            "commission": "0.00",
            "orderStatus": "COMPLETED",
            "createTime": 1700000000000
        }
    ],
    "total": 1,
    "success": True
}
