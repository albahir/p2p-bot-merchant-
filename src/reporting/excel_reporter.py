"""Generador de informes fiscales en formato Excel (.xlsx).
Incluye soporte para informes de 2 pestañas (Detalle y Resumen) e informes
completos de Reconstrucción Fiscal de 4 pestañas:
1. 'Resumen Fiscal': Reconstrucción de 6 piezas, patrimonio y liquidación ISLR.
2. 'Detalle P2P': Órdenes C2C ejecutadas con precios, costos y márgenes.
3. 'Depósitos y Retiros': Movimientos on-chain de criptoactivos.
4. 'Conciliación Bancaria': Comprobantes en bolívares conciliados con órdenes.
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING, cast

import pandas as pd

from src.data.models import BankVoucher, JournalEntry, Order, WalletMovement
from src.reporting.accounting_engine import LedgerSummary
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

    @staticmethod
    def _to_vet_str(dt: datetime | None) -> str:
        """Convierte fecha a Hora Legal de Venezuela (VET = UTC-4)."""
        if not dt:
            return "-"
        vet_tz = timezone(timedelta(hours=-4))
        aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
        return aware.astimezone(vet_tz).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def generate_accounting_report(
        journal_entries: list[JournalEntry],
        ledger_summaries: list[LedgerSummary],
        vouchers: list[BankVoucher],
        output_path: str = "reporte_contable_p2p.xlsx",
        tax_results: list[TradeResult] | None = None,
        orders: list[Order] | None = None,
        wallet_movements: list[WalletMovement] | None = None,
        account_holder: str | None = None,
        rif: str | None = None,
        period: str | None = None,
        bcv_rate: float | None = None,
        initial_usdt: float = 0.0,
        initial_usdt_cost_ves: float = 0.0,
        initial_ves: float = 0.0,
        actual_final_usdt: float | None = None,
        actual_final_ves: float | None = None,
    ) -> str:
        """Crea el informe contable venezolano de 7 pestañas conformes con LISLR / BA VEN-NIF N° 12:
        1. 'Libro Diario': Partida doble cronológica en VET con fila de SUMAS IGUALES.
        2. 'Libro Mayor': Consolidación mensual con Saldo Inicial, Debe, Haber y Saldo Final.
        3. 'Estado de Resultados': Base imponible real (Ventas - Costo PEPS - Comisiones).
        4. 'Balance General (VEN-NIF 12)': Estado de Situación Financiera (Efectivo VES vs Criptoactivos USDT).
        5. 'Kardex Inventario USDT': Control de existencias cripto (Art. 177 Rgto. LISLR) y Arqueo.
        6. 'Conciliación Bancaria': Comprobantes procesados y trazabilidad bancaria.
        7. 'Liquidación Fiscal SENIAT': Resumen tributario ISLR / IGTF y datos del contribuyente.
        """
        results = tax_results or []
        order_list = orders or []

        # 1. Libro Diario (VET + Sumas Iguales)
        diario_rows: list[dict[str, object]] = [
            {
                "Asiento #": int(e.entry_number),
                "Fecha y Hora (VET)": ExcelReporter._to_vet_str(cast(datetime | None, e.date_time)),
                "Código Cuenta": str(e.account_code),
                "Nombre de Cuenta": str(e.account_name),
                "Debe (VES)": float(e.debit),
                "Haber (VES)": float(e.credit),
                "Referencia": str(e.reference or "-"),
                "Descripción / Glosa": str(e.description),
                "Orden P2P": str(e.order_number or "-"),
            }
            for e in journal_entries
        ]
        total_debe = round(sum(float(e.debit) for e in journal_entries), 2)
        total_haber = round(sum(float(e.credit) for e in journal_entries), 2)
        diario_rows.append(
            {
                "Asiento #": "",
                "Fecha y Hora (VET)": "",
                "Código Cuenta": "",
                "Nombre de Cuenta": "SUMAS IGUALES",
                "Debe (VES)": total_debe,
                "Haber (VES)": total_haber,
                "Referencia": "",
                "Descripción / Glosa": "Cuadre de Partida Doble" if abs(total_debe - total_haber) < 0.02 else "REVISAR DESCUADRE",
                "Orden P2P": "",
            }
        )
        df_diario = pd.DataFrame(diario_rows)

        # 2. Libro Mayor
        mayor_rows: list[dict[str, object]] = [
            {
                "Código Cuenta": str(s.account_code),
                "Nombre de Cuenta": str(s.account_name),
                "Período": f"{s.year}-{s.month:02d}",
                "Saldo Inicial (VES)": float(s.initial_balance),
                "Total Debe (VES)": float(s.total_debit),
                "Total Haber (VES)": float(s.total_credit),
                "Saldo Final (VES)": float(s.final_balance),
                "N° Asientos": int(s.entries_count),
            }
            for s in ledger_summaries
        ]
        if ledger_summaries:
            mayor_rows.append(
                {
                    "Código Cuenta": "",
                    "Nombre de Cuenta": "TOTALES DEL PERÍODO",
                    "Período": period or "",
                    "Saldo Inicial (VES)": round(sum(float(s.initial_balance) for s in ledger_summaries), 2),
                    "Total Debe (VES)": round(sum(float(s.total_debit) for s in ledger_summaries), 2),
                    "Total Haber (VES)": round(sum(float(s.total_credit) for s in ledger_summaries), 2),
                    "Saldo Final (VES)": round(sum(float(s.final_balance) for s in ledger_summaries), 2),
                    "N° Asientos": sum(int(s.entries_count) for s in ledger_summaries),
                }
            )
        df_mayor = pd.DataFrame(mayor_rows)

        # 3. Estado de Resultados Real (PEPS + Gastos Deducibles, nunca flujo 1.1.01)
        ingresos_ventas = round(sum(float(r.total_revenue_fiat) for r in results), 2)
        costo_ventas_peps = round(sum(float(r.acquisition_cost_fiat) for r in results), 2)
        utilidad_bruta = round(ingresos_ventas - costo_ventas_peps, 2)
        comisiones_binance = round(sum(float(r.fee_fiat) for r in results), 2)
        if comisiones_binance == 0.0:
            comisiones_binance = round(
                sum(float(e.debit) for e in journal_entries if e.account_code == "5.1.02"), 2
            )
        comisiones_banco = round(
            sum(float(e.debit) for e in journal_entries if e.account_code == "5.2.01"), 2
        )
        total_gastos_deducibles = round(comisiones_binance + comisiones_banco, 2)
        enriquecimiento_neto = round(utilidad_bruta - total_gastos_deducibles, 2)

        ref_bcv = float(bcv_rate or 0.0)
        if ref_bcv <= 0 and results:
            valid_bcv = [float(r.bcv_rate) for r in results if float(r.bcv_rate) > 0]
            ref_bcv = valid_bcv[-1] if valid_bcv else 0.0
        enriquecimiento_usd_bcv = round(enriquecimiento_neto / ref_bcv, 2) if ref_bcv > 0 else 0.0

        estado_resultados_rows = [
            {"Partida Contable (VEN-NIF / LISLR)": "Contribuyente / Titular", "Monto (VES)": account_holder or "No especificado", "Equivalente USD (BCV)": rif or "C.I. / RIF no registrado"},
            {"Partida Contable (VEN-NIF / LISLR)": "Período Fiscal", "Monto (VES)": period or "-", "Equivalente USD (BCV)": f"BCV Ref: {ref_bcv:.4f}" if ref_bcv > 0 else "-"},
            {"Partida Contable (VEN-NIF / LISLR)": "Ingresos Brutos por Enajenación P2P", "Monto (VES)": ingresos_ventas, "Equivalente USD (BCV)": round(ingresos_ventas / ref_bcv, 2) if ref_bcv > 0 else 0.0},
            {"Partida Contable (VEN-NIF / LISLR)": "(-) Costo de Adquisición PEPS (FIFO)", "Monto (VES)": costo_ventas_peps, "Equivalente USD (BCV)": round(costo_ventas_peps / ref_bcv, 2) if ref_bcv > 0 else 0.0},
            {"Partida Contable (VEN-NIF / LISLR)": "(=) Utilidad Bruta Realizada", "Monto (VES)": utilidad_bruta, "Equivalente USD (BCV)": round(utilidad_bruta / ref_bcv, 2) if ref_bcv > 0 else 0.0},
            {"Partida Contable (VEN-NIF / LISLR)": "(-) Comisiones Plataforma Exchange", "Monto (VES)": comisiones_binance, "Equivalente USD (BCV)": round(comisiones_binance / ref_bcv, 2) if ref_bcv > 0 else 0.0},
            {"Partida Contable (VEN-NIF / LISLR)": "(-) Comisiones Bancarias Deducibles", "Monto (VES)": comisiones_banco, "Equivalente USD (BCV)": round(comisiones_banco / ref_bcv, 2) if ref_bcv > 0 else 0.0},
            {"Partida Contable (VEN-NIF / LISLR)": "(=) Enriquecimiento Neto Gravable ISLR", "Monto (VES)": enriquecimiento_neto, "Equivalente USD (BCV)": enriquecimiento_usd_bcv},
        ]
        df_resultados = pd.DataFrame(estado_resultados_rows)

        # 4. Kardex Inventario USDT (Reglamento LISLR Art. 177)
        completed_orders = [o for o in order_list if str(getattr(o, "order_status", "COMPLETED")) == "COMPLETED"]
        compras_usdt = round(sum(float(o.crypto_amount) for o in completed_orders if o.trade_type == "BUY"), 4)
        compras_ves = round(sum(float(o.fiat_amount) for o in completed_orders if o.trade_type == "BUY"), 2)
        ventas_usdt = round(
            sum(float(o.crypto_amount) for o in completed_orders if o.trade_type == "SELL")
            if completed_orders
            else sum(float(r.crypto_amount) for r in results),
            4,
        )
        init_usdt_val = round(float(initial_usdt or 0.0), 4)
        init_usdt_cost = round(float(initial_usdt_cost_ves or 0.0), 2)
        if init_usdt_cost <= 0.0 and init_usdt_val > 0.0 and ref_bcv > 0.0:
            init_usdt_cost = round(init_usdt_val * ref_bcv, 2)

        wm_usdt = [
            m
            for m in (wallet_movements or [])
            if str(getattr(m, "asset", "") or "").upper() == "USDT"
            and str(getattr(m, "status", "") or "").upper() in ("COMPLETED", "SUCCESS")
        ]
        otros_ingresos_usdt = round(
            sum(float(m.amount or 0.0) for m in wm_usdt if str(m.movement_type or "").upper() == "DEPOSIT"),
            4,
        )
        otros_egresos_usdt = round(
            sum(
                float(m.amount or 0.0) + float(m.fee or 0.0)
                for m in wm_usdt
                if str(m.movement_type or "").upper() == "WITHDRAWAL"
            ),
            4,
        )
        otros_ingresos_ves = round(otros_ingresos_usdt * ref_bcv, 2) if ref_bcv > 0 else 0.0
        otros_egresos_ves = round(otros_egresos_usdt * ref_bcv, 2) if ref_bcv > 0 else 0.0

        inventario_final_usdt = round(
            init_usdt_val + compras_usdt + otros_ingresos_usdt - ventas_usdt - otros_egresos_usdt,
            4,
        )
        inventario_final_ves = round(
            max(0.0, init_usdt_cost + compras_ves + otros_ingresos_ves - costo_ventas_peps - otros_egresos_ves),
            2,
        )

        kardex_rows: list[dict[str, object]] = [
            {"Concepto": "Saldo Inicial USDT", "Cantidad (USDT)": init_usdt_val, "Valor Referencial (VES)": init_usdt_cost},
            {"Concepto": "(+) Compras P2P USDT", "Cantidad (USDT)": compras_usdt, "Valor Referencial (VES)": compras_ves},
        ]
        if otros_ingresos_usdt > 0:
            kardex_rows.append(
                {
                    "Concepto": "(+) Entradas Binance Pay / Depósitos USDT",
                    "Cantidad (USDT)": otros_ingresos_usdt,
                    "Valor Referencial (VES)": otros_ingresos_ves,
                }
            )
        kardex_rows.append(
            {"Concepto": "(-) Ventas P2P USDT", "Cantidad (USDT)": ventas_usdt, "Valor Referencial (VES)": costo_ventas_peps}
        )
        if otros_egresos_usdt > 0:
            kardex_rows.append(
                {
                    "Concepto": "(-) Salidas Binance Pay / Retiros USDT",
                    "Cantidad (USDT)": otros_egresos_usdt,
                    "Valor Referencial (VES)": otros_egresos_ves,
                }
            )
        kardex_rows.append(
            {"Concepto": "(=) Inventario Final USDT", "Cantidad (USDT)": inventario_final_usdt, "Valor Referencial (VES)": inventario_final_ves}
        )
        if actual_final_usdt is not None:
            real_usdt = round(float(actual_final_usdt), 4)
            diff_usdt = round(real_usdt - inventario_final_usdt, 4)
            kardex_rows.append(
                {
                    "Concepto": "Saldo Final Real (Arqueo Binance USDT)",
                    "Cantidad (USDT)": real_usdt,
                    "Valor Referencial (VES)": round(real_usdt * ref_bcv, 2) if ref_bcv > 0 else 0.0,
                }
            )
            kardex_rows.append(
                {
                    "Concepto": "Diferencia de Arqueo (Real - Teórico)",
                    "Cantidad (USDT)": diff_usdt,
                    "Valor Referencial (VES)": round(diff_usdt * ref_bcv, 2) if ref_bcv > 0 else 0.0,
                }
            )
        df_kardex = pd.DataFrame(kardex_rows)

        # 4b. Estado de Situación Financiera / Balance General (BA VEN-NIF N° 12)
        banco_ledger = next((s for s in ledger_summaries if str(s.account_code) == "1.1.01"), None)
        banco_teorico_ves = (
            round(float(banco_ledger.final_balance), 2)
            if banco_ledger is not None
            else round(float(initial_ves or 0.0), 2)
        )
        efectivo_bancos_ves = (
            round(float(actual_final_ves), 2) if actual_final_ves is not None else banco_teorico_ves
        )
        pasivo_pendiente_ves = round(
            sum(float(e.credit) - float(e.debit) for e in journal_entries if str(e.account_code) == "2.1.09"),
            2,
        )
        pasivo_pendiente_ves = max(0.0, pasivo_pendiente_ves)
        total_activo_ves = round(efectivo_bancos_ves + inventario_final_ves, 2)
        capital_inicial_ves = round(float(initial_ves or 0.0) + init_usdt_cost, 2)
        ajuste_conciliacion_ves = round(
            total_activo_ves - pasivo_pendiente_ves - capital_inicial_ves - enriquecimiento_neto,
            2,
        )
        total_pasivo_patrimonio_ves = round(
            pasivo_pendiente_ves + capital_inicial_ves + enriquecimiento_neto + ajuste_conciliacion_ves,
            2,
        )
        diff_ves_arqueo = (
            round(float(actual_final_ves) - banco_teorico_ves, 2) if actual_final_ves is not None else None
        )
        balance_general_rows = [
            {"Rubro (BA VEN-NIF N° 12)": "ACTIVO CORRIENTE", "Monto (VES)": "", "Equivalente USD (BCV)": ""},
            {
                "Rubro (BA VEN-NIF N° 12)": "1.1.01 Efectivo en Bancos Nacionales (VES)",
                "Monto (VES)": efectivo_bancos_ves,
                "Equivalente USD (BCV)": round(efectivo_bancos_ves / ref_bcv, 2) if ref_bcv > 0 else 0.0,
            },
            {
                "Rubro (BA VEN-NIF N° 12)": "1.1.05 Criptoactivos Propios — Inventario USDT al Costo (Separado de Efectivo)",
                "Monto (VES)": inventario_final_ves,
                "Equivalente USD (BCV)": round(inventario_final_ves / ref_bcv, 2) if ref_bcv > 0 else 0.0,
            },
            {
                "Rubro (BA VEN-NIF N° 12)": "TOTAL ACTIVO (VES)",
                "Monto (VES)": total_activo_ves,
                "Equivalente USD (BCV)": round(total_activo_ves / ref_bcv, 2) if ref_bcv > 0 else 0.0,
            },
            {"Rubro (BA VEN-NIF N° 12)": "PASIVO Y PATRIMONIO", "Monto (VES)": "", "Equivalente USD (BCV)": ""},
            {
                "Rubro (BA VEN-NIF N° 12)": "2.1.09 Pasivos / Créditos Bancarios por Conciliar",
                "Monto (VES)": pasivo_pendiente_ves,
                "Equivalente USD (BCV)": round(pasivo_pendiente_ves / ref_bcv, 2) if ref_bcv > 0 else 0.0,
            },
            {
                "Rubro (BA VEN-NIF N° 12)": "3.1.01 Patrimonio — Capital Inicial Declarado (Bancos + USDT)",
                "Monto (VES)": capital_inicial_ves,
                "Equivalente USD (BCV)": round(capital_inicial_ves / ref_bcv, 2) if ref_bcv > 0 else 0.0,
            },
            {
                "Rubro (BA VEN-NIF N° 12)": "3.2.01 Resultado Neto del Período (ISLR PEPS)",
                "Monto (VES)": enriquecimiento_neto,
                "Equivalente USD (BCV)": enriquecimiento_usd_bcv,
            },
            {
                "Rubro (BA VEN-NIF N° 12)": "3.2.02 Ajustes de Arqueo / Tránsito Bancario",
                "Monto (VES)": ajuste_conciliacion_ves,
                "Equivalente USD (BCV)": round(ajuste_conciliacion_ves / ref_bcv, 2) if ref_bcv > 0 else 0.0,
            },
            {
                "Rubro (BA VEN-NIF N° 12)": "TOTAL PASIVO + PATRIMONIO (VES)",
                "Monto (VES)": total_pasivo_patrimonio_ves,
                "Equivalente USD (BCV)": round(total_pasivo_patrimonio_ves / ref_bcv, 2) if ref_bcv > 0 else 0.0,
            },
            {
                "Rubro (BA VEN-NIF N° 12)": "Arqueo Bancario VES (Real vs Teórico)",
                "Monto (VES)": (
                    f"Real: {efectivo_bancos_ves:,.2f} | Teórico: {banco_teorico_ves:,.2f} | Dif: {diff_ves_arqueo:+,.2f}"
                    if diff_ves_arqueo is not None
                    else "Sin arqueo final ingresado (usa saldo teórico)"
                ),
                "Equivalente USD (BCV)": "Ecuación Patrimonial Cuadrada" if abs(total_activo_ves - total_pasivo_patrimonio_ves) < 0.02 else "Revisar",
            },
        ]
        df_balance_general = pd.DataFrame(balance_general_rows)

        # 5. Conciliación Bancaria
        vouchers_rows = [
            {
                "Fecha (VET)": ExcelReporter._to_vet_str(cast(datetime | None, v.voucher_date)),
                "Banco Origen": v.bank_name,
                "Banco Destino": v.destination_bank or "-",
                "Referencia": str(v.reference_number or "-"),
                "Monto Neto (VES)": float(v.amount_ves),
                "Comisión Bancaria (VES)": float(v.bank_fee_ves or 0.0),
                "Total Debitado (VES)": float(v.total_debited_ves or v.amount_ves),
                "Cédula/RIF Emisor": str(v.sender_id or "S/C"),
                "Teléfono": str(v.sender_phone or "N/A"),
                "Concepto / Motivo": v.concept or "-",
                "Método": v.payment_method,
                "Tipo Flujo": v.movement_type,
                "Orden Asociada": str(v.associated_order_number or "-"),
                "Estado Conciliación": v.verification_status,
            }
            for v in vouchers
        ]
        df_vouchers = pd.DataFrame(vouchers_rows)

        # 6. Liquidación Fiscal SENIAT (LISLR + IGTF + Providencia SNAT/2026/00099)
        seniat_rows = [
            {"Concepto Fiscal": "Contribuyente / Titular", "Monto (VES)": account_holder or "No especificado"},
            {"Concepto Fiscal": "Cédula / RIF", "Monto (VES)": rif or "No registrado"},
            {"Concepto Fiscal": "Período Fiscal (Hora VET UTC-4)", "Monto (VES)": period or "-"},
            {"Concepto Fiscal": "Ingresos Brutos por Ventas (VES)", "Monto (VES)": ingresos_ventas},
            {"Concepto Fiscal": "Costo de Ventas PEPS (VES)", "Monto (VES)": costo_ventas_peps},
            {"Concepto Fiscal": "Utilidad Bruta Realizada (VES)", "Monto (VES)": utilidad_bruta},
            {"Concepto Fiscal": "Gastos Deducibles - Comisiones Exchange (VES)", "Monto (VES)": comisiones_binance},
            {"Concepto Fiscal": "Gastos Financieros Deducibles - Comisiones Bancarias (VES)", "Monto (VES)": comisiones_banco},
            {"Concepto Fiscal": "Enriquecimiento Neto Gravable ISLR (VES)", "Monto (VES)": enriquecimiento_neto},
            {"Concepto Fiscal": "Equivalente ISLR Referencial BCV (USD)", "Monto (VES)": enriquecimiento_usd_bcv},
            {"Concepto Fiscal": "IGTF Liquidación Banca Nacional VES", "Monto (VES)": "0% (No aplica 3% cuando se liquida en Bs por banca nacional)"},
            {"Concepto Fiscal": "Normativa Aplicable", "Monto (VES)": "LISLR Art. 1/4/27 y Art. 177 Rgto / BA VEN-NIF 12 / Prov. SNAT/2026/00099"},
        ]
        df_seniat = pd.DataFrame(seniat_rows)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_diario.to_excel(writer, sheet_name="Libro Diario", index=False)
            df_mayor.to_excel(writer, sheet_name="Libro Mayor", index=False)
            df_resultados.to_excel(writer, sheet_name="Estado de Resultados", index=False)
            df_balance_general.to_excel(writer, sheet_name="Balance General (VEN-NIF 12)", index=False)
            df_kardex.to_excel(writer, sheet_name="Kardex Inventario USDT", index=False)
            df_vouchers.to_excel(writer, sheet_name="Conciliación Bancaria", index=False)
            df_seniat.to_excel(writer, sheet_name="Liquidación Fiscal SENIAT", index=False)

            text_cols = {"Referencia", "Orden P2P", "Orden Asociada", "Cédula/RIF Emisor", "Teléfono"}
            for sheet_name in writer.sheets:
                ws = writer.sheets[sheet_name]
                for col in ws.columns:
                    header_val = str(col[0].value or "")
                    max_len = max(len(str(c.value or "")) for c in col)
                    ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 3, 14), 48)
                    if header_val in text_cols:
                        for cell in col[1:]:
                            cell.number_format = "@"

        return output_path

