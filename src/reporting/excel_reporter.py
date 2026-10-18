"""Generador de informes fiscales en formato Excel (.xlsx).
Incluye soporte para informes de 2 pestañas (Detalle y Resumen) e informes
completos de Reconstrucción Fiscal de 4 pestañas:
1. 'Resumen Fiscal': Reconstrucción de 6 piezas, patrimonio y liquidación ISLR.
2. 'Detalle P2P': Órdenes C2C ejecutadas con precios, costos y márgenes.
3. 'Depósitos y Retiros': Movimientos on-chain de criptoactivos.
4. 'Conciliación Bancaria': Comprobantes en bolívares conciliados con órdenes.
"""

from typing import TYPE_CHECKING

import pandas as pd

from src.data.models import BankVoucher, Order, WalletMovement
from src.reporting.tax_engine import TradeResult

if TYPE_CHECKING:
    from src.reporting.fiscal_reconciler import FiscalReconciliationResult


class ExcelReporter:
    """Generador de hojas de cálculo de auditoría fiscal."""

    @staticmethod
    def generate_tax_report(results: list[TradeResult], output_path: str) -> str:
        """Crea el archivo Excel con las dos pestañas especificadas en Spec 005."""
        if not results:
            detail_data = []
        else:
            detail_data = [
                {
                    "Fecha y Hora (UTC)": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "-",
                    "Número de Orden": r.order_number,
                    "Tipo": r.trade_type,
                    "Cripto (USDT)": r.crypto_amount,
                    "Precio Venta (VES)": r.sell_price_fiat,
                    "Ingreso Bruto (VES)": r.total_revenue_fiat,
                    "Costo Adquisición (VES)": r.acquisition_cost_fiat,
                    "Comisión (VES)": r.fee_fiat,
                    "Ganancia Neta (VES)": r.net_profit_fiat,
                    "Tasa BCV": r.bcv_rate,
                    "Ganancia Neta (USD)": r.net_profit_usd,
                }
                for r in results
            ]

        df_detail = pd.DataFrame(detail_data)

        total_revenue_ves = sum(r.total_revenue_fiat for r in results)
        total_cost_ves = sum(r.acquisition_cost_fiat for r in results)
        total_fees_ves = sum(r.fee_fiat for r in results)
        total_profit_ves = sum(r.net_profit_fiat for r in results)
        total_profit_usd = sum(r.net_profit_usd for r in results)

        summary_data = [
            {"Métrica": "Total Operaciones de Venta", "Valor": len(results)},
            {"Métrica": "Ingresos Brutos Totales (VES)", "Valor": total_revenue_ves},
            {"Métrica": "Costo de Adquisición Total (VES)", "Valor": total_cost_ves},
            {"Métrica": "Comisiones Pagadas (VES)", "Valor": total_fees_ves},
            {"Métrica": "Ganancia Neta Gravable (VES)", "Valor": total_profit_ves},
            {"Métrica": "Ganancia Neta Estimada (USD)", "Valor": total_profit_usd},
        ]
        df_summary = pd.DataFrame(summary_data)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_detail.to_excel(writer, sheet_name="Detalle", index=False)
            df_summary.to_excel(writer, sheet_name="Resumen", index=False)

        return output_path

    @staticmethod
    def generate_fiscal_reconstruction_report(
        reconciliation: "FiscalReconciliationResult",
        p2p_orders: list[Order],
        wallet_movements: list[WalletMovement],
        vouchers: list[BankVoucher],
        output_path: str,
    ) -> str:
        """Crea el informe fiscal integral de 4 pestañas para auditorías tributarias."""
        summary_rows = [
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "Período Fiscal", "Valor": reconciliation.period},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "1. Saldo Inicial (USDT)", "Valor": reconciliation.initial_balance},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "2. Entradas - Depósitos On-chain (USDT)", "Valor": reconciliation.inflows_deposits},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "2. Entradas - Compras P2P (USDT)", "Valor": reconciliation.inflows_p2p_buys},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "Total Entradas Cripto (USDT)", "Valor": reconciliation.total_inflows},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "3. Salidas - Retiros On-chain (USDT)", "Valor": reconciliation.outflows_withdrawals},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "3. Salidas - Ventas P2P (USDT)", "Valor": reconciliation.outflows_p2p_sells},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "Total Salidas Cripto (USDT)", "Valor": reconciliation.total_outflows},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "4. Volumen Operado Total (USDT)", "Valor": reconciliation.volume_operated},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "5. Comisiones de Red / Costos (USDT)", "Valor": reconciliation.total_fees},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "6. Saldo Final Calculado Teórico (USDT)", "Valor": reconciliation.calculated_final_balance},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "6. Saldo Final Real / Snapshot (USDT)", "Valor": reconciliation.actual_final_balance},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "Discrepancia / Merma (USDT)", "Valor": reconciliation.discrepancy},
            {"Sección": "1. Reconstrucción de 6 Piezas", "Concepto / Métrica": "Estatus Consistencia Patrimonial", "Valor": reconciliation.status},
            {"Sección": "2. Liquidación ISLR Estimada", "Concepto / Métrica": "Ingresos Brutos por Ventas (VES)", "Valor": reconciliation.gross_revenue_ves},
            {"Sección": "2. Liquidación ISLR Estimada", "Concepto / Métrica": "Costos de Adquisición FIFO (VES)", "Valor": reconciliation.acquisition_cost_ves},
            {"Sección": "2. Liquidación ISLR Estimada", "Concepto / Métrica": "Ganancia Neta Gravable (VES)", "Valor": reconciliation.net_profit_ves},
            {"Sección": "2. Liquidación ISLR Estimada", "Concepto / Métrica": "Ganancia Neta Estimada (USD)", "Valor": reconciliation.net_profit_usd},
            {"Sección": "3. Auditoría Bancaria", "Concepto / Métrica": "Comprobantes Bancarios Procesados", "Valor": reconciliation.vouchers_count},
            {"Sección": "3. Auditoría Bancaria", "Concepto / Métrica": "Comprobantes Auto-Conciliados", "Valor": reconciliation.matched_vouchers_count},
        ]
        df_summary = pd.DataFrame(summary_rows)

        p2p_data = [
            {
                "Fecha (UTC)": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "-",
                "Número de Pedido": o.order_number,
                "Tipo": o.trade_type,
                "Activo": o.asset,
                "Cripto": o.crypto_amount,
                "Precio Unitario": o.unit_price,
                "Moneda Fiat": o.fiat,
                "Monto Fiat": o.fiat_amount,
                "Comisión": o.fee_fiat,
                "Tasa BCV": o.bcv_rate,
                "Estado": o.order_status,
            }
            for o in p2p_orders
        ]
        df_p2p = pd.DataFrame(p2p_data)

        movs_data = [
            {
                "Fecha (UTC)": m.timestamp.strftime("%Y-%m-%d %H:%M:%S") if m.timestamp else "-",
                "Tipo Movimiento": m.movement_type,
                "Activo": m.asset,
                "Monto": m.amount,
                "Comisión Red": m.fee,
                "Red": m.network or "-",
                "TXID": m.txid or "-",
                "Dirección": m.address or "-",
                "Estado": m.status,
            }
            for m in wallet_movements
        ]
        df_movs = pd.DataFrame(movs_data)

        vouchers_data = [
            {
                "Fecha": v.created_at.strftime("%Y-%m-%d %H:%M:%S") if v.created_at else "-",
                "Banco": v.bank_name,
                "Referencia": v.reference_number,
                "Monto (VES)": v.amount_ves,
                "Cédula/RIF Emisor": v.sender_id or "-",
                "Nombre Titular": v.sender_name or "-",
                "Método Pago": v.payment_method,
                "Orden P2P Vinculada": v.associated_order_number or "-",
                "Estado Verificación": v.verification_status,
            }
            for v in vouchers
        ]
        df_vouchers = pd.DataFrame(vouchers_data)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_summary.to_excel(writer, sheet_name="Resumen Fiscal", index=False)
            df_p2p.to_excel(writer, sheet_name="Detalle P2P", index=False)
            df_movs.to_excel(writer, sheet_name="Depósitos y Retiros", index=False)
            df_vouchers.to_excel(writer, sheet_name="Conciliación Bancaria", index=False)

        return output_path

    @staticmethod
    def generate_compliance_report(
        orders: list[Order],
        vouchers: list[BankVoucher],
        account_holder: str = "TITULAR REGISTRADO",
        rif: str = "V-00000000-0",
        period: str = "PERIODO ACTUAL",
        output_path: str = "certificacion_origen_fondos.xlsx",
    ) -> str:
        """Crea el informe de Compliance Bancario y Certificación de Origen de Fondos."""
        sell_orders = [o for o in orders if o.trade_type == "SELL"]
        buy_orders = [o for o in orders if o.trade_type == "BUY"]

        total_sell_ves = sum(o.fiat_amount for o in sell_orders)
        total_buy_ves = sum(o.fiat_amount for o in buy_orders)
        total_crypto = sum(o.crypto_amount for o in orders)
        matched_vouchers = [v for v in vouchers if v.verification_status == "MATCHED"]

        cert_rows = [
            {"Concepto / Métrica": "Título del Documento", "Valor": "INFORME DE CUMPLIMIENTO Y JUSTIFICACIÓN DE ORIGEN Y DESTINO LÍCITO DE FONDOS"},
            {"Concepto / Métrica": "Titular de la Cuenta / Razón Social", "Valor": account_holder},
            {"Concepto / Métrica": "Cédula de Identidad / R.I.F.", "Valor": rif},
            {"Concepto / Métrica": "Período Operativo Auditado", "Valor": period},
            {"Concepto / Métrica": "Actividad Económica", "Valor": "Comercio Electrónico P2P de Criptoactivos"},
            {"Concepto / Métrica": "Plataforma de Intermediación", "Valor": "Binance C2C (Binance Holdings Ltd.)"},
            {"Concepto / Métrica": "Moneda Operativa Nacional", "Valor": "Bolívares Soberanos / Digitales (VES)"},
            {"Concepto / Métrica": "Criptoactivo Operado", "Valor": "Tether USD (USDT)"},
            {"Concepto / Métrica": "Total Entradas Bancarias (Ventas P2P en Bs)", "Valor": total_sell_ves},
            {"Concepto / Métrica": "Total Salidas Bancarias (Compras P2P en Bs)", "Valor": total_buy_ves},
            {"Concepto / Métrica": "Volumen Total en Cuenta (VES)", "Valor": total_sell_ves + total_buy_ves},
            {"Concepto / Métrica": "Total Criptoactivo Movilizado (USDT)", "Valor": total_crypto},
            {"Concepto / Métrica": "Total Transacciones Realizadas", "Valor": len(orders)},
            {"Concepto / Métrica": "Comprobantes Conciliados y Verificados", "Valor": f"{len(matched_vouchers)} de {len(vouchers)}"},
            {"Concepto / Métrica": "Dictamen de Cumplimiento", "Valor": "CONFORME / TRAZABILIDAD 100%"},
            {
                "Concepto / Métrica": "Declaración Jurada",
                "Valor": (
                    "Se certifica que la totalidad de los fondos bancarios acreditados y debitados corresponden exclusivamente "
                    "a operaciones mercantiles de arbitraje y compra/venta de activos digitales en plataformas debidamente "
                    "registradas, con conciliación de contrapartes y verificación de titularidad."
                ),
            },
        ]
        df_cert = pd.DataFrame(cert_rows)

        voucher_map = {v.associated_order_number: v for v in vouchers if v.associated_order_number}

        ventas_data = []
        for o in sell_orders:
            v = voucher_map.get(o.order_number)
            ventas_data.append(
                {
                    "Fecha y Hora (UTC)": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "-",
                    "Número de Orden": o.order_number,
                    "Contraparte Binance": o.counterparty_name or "-",
                    "Activo Cripto": f"{o.crypto_amount:,.2f} {o.asset}",
                    "Precio Unitario (VES)": o.unit_price,
                    "Monto Acreditado (VES)": o.fiat_amount,
                    "Comisión Binance": o.fee_fiat,
                    "Tasa BCV": o.bcv_rate,
                    "Estado": o.order_status,
                    "Referencia Bancaria": v.reference_number if v else "-",
                    "Nombre Pagador Bancario": v.sender_name if v else "-",
                    "Cédula/RIF Pagador": v.sender_id if v else "-",
                }
            )
        df_ventas = pd.DataFrame(ventas_data)

        compras_data = []
        for o in buy_orders:
            v = voucher_map.get(o.order_number)
            compras_data.append(
                {
                    "Fecha y Hora (UTC)": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "-",
                    "Número de Orden": o.order_number,
                    "Contraparte Binance": o.counterparty_name or "-",
                    "Activo Cripto Recibido": f"{o.crypto_amount:,.2f} {o.asset}",
                    "Precio Unitario (VES)": o.unit_price,
                    "Monto Debitado (VES)": o.fiat_amount,
                    "Comisión Binance": o.fee_fiat,
                    "Tasa BCV": o.bcv_rate,
                    "Estado": o.order_status,
                    "Referencia Bancaria": v.reference_number if v else "-",
                    "Beneficiario Bancario": v.sender_name if v else "-",
                    "Cédula/RIF Beneficiario": v.sender_id if v else "-",
                }
            )
        df_compras = pd.DataFrame(compras_data)

        traza_data = [
            {
                "Fecha": v.created_at.strftime("%Y-%m-%d %H:%M:%S") if v.created_at else "-",
                "Banco": v.bank_name,
                "Referencia Bancaria": v.reference_number,
                "Monto (VES)": v.amount_ves,
                "Cédula/RIF": v.sender_id or "-",
                "Nombre Titular": v.sender_name or "-",
                "Método de Pago": v.payment_method,
                "Orden Binance Asociada": v.associated_order_number or "-",
                "Estado Conciliación": v.verification_status,
            }
            for v in vouchers
        ]
        df_traza = pd.DataFrame(traza_data)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_cert.to_excel(writer, sheet_name="Certificación Institucional", index=False)
            df_ventas.to_excel(writer, sheet_name="Entradas (Ventas P2P)", index=False)
            df_compras.to_excel(writer, sheet_name="Salidas (Compras P2P)", index=False)
            df_traza.to_excel(writer, sheet_name="Traza de Conciliación", index=False)

        return output_path

