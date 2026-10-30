"""Script CLI para extraer el histórico de órdenes Binance P2P vía API oficial y guardarlo en CSV.

Uso:
    python scripts/export_binance_orders.py [--days 30] [--type ALL] [--output data/exports/orders.csv]
"""

import argparse
import os
import sys
from datetime import UTC, datetime

# Agregar la raíz del repositorio al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import Settings
from src.core.binance_client import BinanceP2PClient
from src.core.binance_history_syncer import BinanceHistorySyncer
from src.data.database import SessionLocal
from src.security.api_key_manager import ApiKeyManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta órdenes históricas de Binance P2P a un archivo CSV.")
    parser.add_argument("--days", type=int, default=30, help="Días hacia atrás a consultar (máximo 30).")
    parser.add_argument("--type", choices=["ALL", "BUY", "SELL"], default="ALL", help="Tipo de orden a consultar.")
    parser.add_argument("--format", choices=["csv", "xlsx", "both"], default="both", help="Formato de exportación.")
    parser.add_argument("--output", type=str, default="", help="Ruta de guardado base para los archivos.")
    args = parser.parse_args()

    print("[*] Iniciando extractor de órdenes históricas Binance P2P...")
    settings = Settings()

    km = ApiKeyManager(master_key=settings.MASTER_ENCRYPTION_KEY, db_session_factory=SessionLocal)
    api_key = km.get_secret("binance_api_key") or ""
    private_key = km.get_secret("binance_private_key") or ""

    if not api_key:
        print("[!] Error: No se encontró 'binance_api_key' configurada.")
        print("    Regístrala en el Dashboard (Credenciales & RBAC) antes de ejecutar la extracción.")
        sys.exit(1)

    if not private_key:
        print("[!] Error: No se encontró 'binance_private_key' configurada.")
        print("    Binance requiere firma con Secret Key o Private Key Ed25519 para consultar órdenes.")
        sys.exit(1)

    db = SessionLocal()
    try:
        client = BinanceP2PClient(api_key=api_key, private_key_pem=private_key)
        syncer = BinanceHistorySyncer()

        print(f"[*] Consultando órdenes de los últimos {args.days} días (Tipo: {args.type})...")
        res = syncer.sync_orders(client=client, db=db, days=args.days, trade_type=args.type)

        if not res.success:
            print(f"[!] Fallo en la extracción: {res.error_message}")
            sys.exit(1)

        print("[+] Extracción completada exitosamente:")
        print(f"    - Total órdenes obtenidas: {res.total_fetched}")
        print(f"    - Compras (BUY):           {res.buy_orders}")
        print(f"    - Ventas (SELL):          {res.sell_orders}")
        print(f"    - Nuevas insertadas en BD:{res.orders_inserted}")
        print(f"    - Ya existentes en BD:    {res.orders_existing}")
        print(f"    - Volumen USDT negociado: {res.total_volume_usdt:,.2f} USDT")

        output_base = args.output
        if not output_base:
            os.makedirs("data/exports", exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            output_base = f"data/exports/binance_p2p_orders_{timestamp}"

        base_without_ext = os.path.splitext(output_base)[0]
        os.makedirs(os.path.dirname(os.path.abspath(base_without_ext)), exist_ok=True)

        if args.format in ("csv", "both") and res.csv_bytes:
            csv_path = f"{base_without_ext}.csv"
            with open(csv_path, "wb") as f:
                f.write(res.csv_bytes)
            print(f"[+] Archivo CSV (delimitador ';') exportado en: {csv_path}")

        if args.format in ("xlsx", "both") and res.excel_bytes:
            xlsx_path = f"{base_without_ext}.xlsx"
            with open(xlsx_path, "wb") as f:
                f.write(res.excel_bytes)
            print(f"[+] Archivo Excel nativo (.xlsx) exportado en: {xlsx_path}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
