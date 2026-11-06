"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import {
  FiscalSummary,
  JournalEntryItem,
  LedgerSummaryItem,
  UploadVoucherResponse,
  User,
  getCurrentUser,
  getExportAccountingExcelUrl,
  getExportAccountingPdfUrl,
  getFiscalSummary,
  getJournalEntries,
  getLedgerSummaries,
  getLiveBalance,
  matchVoucherWithOrder,
  reconcileOrphanVouchers,
  uploadVoucherFile,
} from "@/lib/api";

type AccountingTab = "JOURNAL" | "LEDGER" | "FISCAL_6";

interface BankBreakdownItem {
  bank_name: string;
  initial_ves: number;
  inflows_ves: number;
  outflows_ves: number;
  theoretical_ves: number;
}

interface LiveBalanceState {
  year: number;
  month: number;
  initial_usdt: number;
  inflow_usdt: number;
  outflow_usdt: number;
  theoretical_usdt: number;
  total_initial_ves: number;
  total_inflows_ves: number;
  total_outflows_ves: number;
  total_theoretical_ves: number;
  bank_breakdown: BankBreakdownItem[];
}

const MONTHS = [
  { value: 1, label: "Enero" },
  { value: 2, label: "Febrero" },
  { value: 3, label: "Marzo" },
  { value: 4, label: "Abril" },
  { value: 5, label: "Mayo" },
  { value: 6, label: "Junio" },
  { value: 7, label: "Julio" },
  { value: 8, label: "Agosto" },
  { value: 9, label: "Septiembre" },
  { value: 10, label: "Octubre" },
  { value: 11, label: "Noviembre" },
  { value: 12, label: "Diciembre" },
];

export default function AccountingPage() {
  const voucherInputRef = useRef<HTMLInputElement>(null);
  const now = new Date();

  const [user, setUser] = useState<User | null>(null);
  const [year, setYear] = useState<number>(now.getFullYear());
  const [month, setMonth] = useState<number>(now.getMonth() + 1);
  const [initialVes, setInitialVes] = useState<number>(0);
  const [initialUsdt, setInitialUsdt] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<AccountingTab>("JOURNAL");

  const [liveBalance, setLiveBalance] = useState<LiveBalanceState | null>(null);
  const [journalEntries, setJournalEntries] = useState<JournalEntryItem[]>([]);
  const [ledgerSummaries, setLedgerSummaries] = useState<LedgerSummaryItem[]>([]);
  const [fiscalSummary, setFiscalSummary] = useState<FiscalSummary | null>(null);

  const [lastVoucher, setLastVoucher] = useState<UploadVoucherResponse | null>(null);
  const [manualOrderNumber, setManualOrderNumber] = useState<string>("");

  const [loading, setLoading] = useState<boolean>(true);
  const [uploadingOcr, setUploadingOcr] = useState<boolean>(false);
  const [reconciling, setReconciling] = useState<boolean>(false);
  const [showCloseModal, setShowCloseModal] = useState<boolean>(false);
  const [closeConfirmText, setCloseConfirmText] = useState<string>("");
  const [periodClosed, setPeriodClosed] = useState<boolean>(false);

  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const loadAccountingData = useCallback(async () => {
    const current = getCurrentUser();
    setUser(current);
    if (!current || current.role === "INVITADO") {
      setLoading(false);
      return;
    }

    setLoading(true);
    const periodStr = `${year}-${String(month).padStart(2, "0")}`;
    const startDate = `${periodStr}-01`;

    try {
      const [liveRes, journalRes, ledgerRes, fiscalRes] = await Promise.all([
        getLiveBalance(year, month, initialUsdt, initialVes).catch(() => null),
        getJournalEntries(startDate).catch(() => []),
        getLedgerSummaries(year, month, undefined, initialVes).catch(() => []),
        getFiscalSummary(periodStr, initialVes).catch(() => null),
      ]);

      if (liveRes) setLiveBalance(liveRes);
      setJournalEntries(journalRes || []);
      setLedgerSummaries(ledgerRes || []);
      if (fiscalRes) setFiscalSummary(fiscalRes);
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error al consultar el motor contable SENIAT.",
      });
    } finally {
      setLoading(false);
    }
  }, [year, month, initialUsdt, initialVes]);

  useEffect(() => {
    loadAccountingData();
  }, [loadAccountingData]);

  async function handleUploadReceipt(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFeedback(null);
    setUploadingOcr(true);
    try {
      const res = await uploadVoucherFile(file);
      setLastVoucher(res);
      setFeedback({
        type: "success",
        text: `Comprobante OCR #${res.reference_number} (${res.bank_name} • Bs. ${res.amount_ves.toFixed(
          2
        )}) procesado.`,
      });
      await loadAccountingData();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo extraer el recibo bancario mediante OCR.",
      });
    } finally {
      setUploadingOcr(false);
      if (voucherInputRef.current) voucherInputRef.current.value = "";
    }
  }

  async function handleAutoReconcile() {
    setFeedback(null);
    setReconciling(true);
    try {
      const res = await reconcileOrphanVouchers(48);
      setFeedback({
        type: "success",
        text:
          res?.message ||
          `Auto-conciliación ejecutada (${res?.matched_count ?? 0} recibos vinculados).`,
      });
      await loadAccountingData();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error al auto-conciliar comprobantes huérfanos.",
      });
    } finally {
      setReconciling(false);
    }
  }

  async function handleManualMatch(e: React.FormEvent) {
    e.preventDefault();
    if (!lastVoucher || !manualOrderNumber.trim()) return;
    try {
      await matchVoucherWithOrder(lastVoucher.voucher_id, manualOrderNumber.trim());
      setFeedback({
        type: "success",
        text: `Comprobante #${lastVoucher.reference_number} vinculado con orden ${manualOrderNumber.trim()}.`,
      });
      setManualOrderNumber("");
      setLastVoucher(null);
      await loadAccountingData();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo vincular el comprobante a la orden.",
      });
    }
  }

  if (!user || user.role === "INVITADO") {
    return (
      <AppShell
        title="Contabilidad & Libro Diario SENIAT"
        badge="ACCESO RESTRINGIDO"
        subtitle="Módulo contable en partida doble reservado para operadores TRADER y ADMIN."
      >
        <div className="max-w-lg mx-auto my-12 p-6 rounded-2xl bg-surface-container-low border border-[#1e2430] text-center space-y-4">
          <span className="material-symbols-outlined text-[36px] text-primary">
            menu_book
          </span>
          <h2 className="text-base font-bold text-white">
            Inicia sesión con rol TRADER o ADMIN
          </h2>
          <p className="text-xs text-slate-400">
            Accede al Libro Diario encadenado con SHA-256, Libro Mayor mensual y conciliación OCR de recibos bancarios.
          </p>
          <Link
            href="/login"
            className="inline-block px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold"
          >
            Ir al Inicio de Sesión
          </Link>
        </div>
      </AppShell>
    );
  }

  // Subcajas reales de bancos (corrige el bug de Stitch que repetía "SALDO INICIAL DEL MES" 3 veces)
  const bankBoxes: BankBreakdownItem[] =
    liveBalance?.bank_breakdown && liveBalance.bank_breakdown.length > 0
      ? liveBalance.bank_breakdown.slice(0, 3)
      : [
          {
            bank_name: "Banesco",
            initial_ves: 0,
            inflows_ves: 0,
            outflows_ves: 0,
            theoretical_ves: 0,
          },
          {
            bank_name: "BDV / Pago Móvil",
            initial_ves: 0,
            inflows_ves: 0,
            outflows_ves: 0,
            theoretical_ves: 0,
          },
          {
            bank_name: "Mercantil",
            initial_ves: 0,
            inflows_ves: 0,
            outflows_ves: 0,
            theoretical_ves: 0,
          },
        ];

  return (
    <AppShell
      title="Contabilidad, Libro Diario & Conciliación OCR"
      badge={periodClosed ? "PERÍODO CERRADO" : "PARTIDA DOBLE SHA-256"}
      subtitle="Libros contables auditables (formato SENIAT), saldos teóricos en vivo y conciliación de comprobantes bancarios."
      actions={
        <div className="flex items-center gap-2 flex-wrap">
          {/* Selector de Período Mes / Año */}
          <div className="flex items-center gap-1 bg-surface-container px-2 py-1 rounded-lg border border-[#1e2430] text-xs font-mono">
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="bg-transparent text-white focus:outline-hidden"
            >
              {MONTHS.map((m) => (
                <option key={m.value} value={m.value} className="bg-[#141920]">
                  {m.label}
                </option>
              ))}
            </select>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="bg-transparent text-primary font-bold focus:outline-hidden"
            >
              {[2025, 2026, 2027].map((y) => (
                <option key={y} value={y} className="bg-[#141920]">
                  {y}
                </option>
              ))}
            </select>
          </div>

          <a
            href={getExportAccountingExcelUrl(year, month)}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1.5 rounded-lg bg-tertiary/15 border border-tertiary/35 text-tertiary text-xs font-mono font-semibold hover:bg-tertiary/25 flex items-center gap-1.5 whitespace-nowrap"
          >
            <span className="material-symbols-outlined text-[15px]">grid_on</span>
            <span>Excel 4 Pestañas</span>
          </a>

          <a
            href={getExportAccountingPdfUrl(year, month)}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-secondary/50 text-slate-200 text-xs font-mono flex items-center gap-1.5 whitespace-nowrap"
          >
            <span className="material-symbols-outlined text-[15px] text-secondary">
              picture_as_pdf
            </span>
            <span>PDF Ejecutivo</span>
          </a>

          <button
            type="button"
            onClick={() => setShowCloseModal(true)}
            className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 flex items-center gap-1 whitespace-nowrap"
          >
            <span className="material-symbols-outlined text-[15px]">lock_clock</span>
            <span>Cerrar Mes</span>
          </button>
        </div>
      }
    >
      <div className="space-y-5">
        {feedback && (
          <div
            className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 text-xs ${
              feedback.type === "success"
                ? "bg-tertiary/10 border-tertiary/30 text-emerald-200"
                : "bg-error/10 border-error/30 text-red-200"
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">
                {feedback.type === "success" ? "task_alt" : "error"}
              </span>
              <span>{feedback.text}</span>
            </div>
            <button
              type="button"
              onClick={() => setFeedback(null)}
              className="text-slate-400 hover:text-white"
            >
              ✕
            </button>
          </div>
        )}

        {/* 3 Tarjetas Bento de Saldos y Conciliación OCR (Corregidas sin IGTF ni desbordes) */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Card 1: Saldo Bancario Teórico Consolidado VES + Subcajas por Banco Real */}
          <div className="lg:col-span-5 p-4 rounded-xl bg-surface-container-low border border-[#1e2430] flex flex-col justify-between gap-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  Saldo Teórico Consolidado en Bancos (VES)
                </div>
                <div className="mt-1 text-2xl font-mono font-bold text-white tabular-nums">
                  Bs.{" "}
                  {(liveBalance?.total_theoretical_ves ?? 0).toLocaleString("es-VE", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </div>
              </div>
              <div className="text-right">
                <label className="block text-[9px] font-mono uppercase text-slate-500">
                  Inicial VES
                </label>
                <input
                  type="number"
                  value={initialVes}
                  onChange={(e) => setInitialVes(Number(e.target.value))}
                  className="w-28 mt-0.5 px-2 py-1 rounded bg-surface-container-lowest border border-[#1e2430] text-right text-xs font-mono text-primary tabular-nums"
                />
              </div>
            </div>

            {/* Subcajas con Nombres Reales de Bancos (Banesco, BDV, Mercantil...) */}
            <div className="grid grid-cols-3 gap-2">
              {bankBoxes.map((b) => (
                <div
                  key={b.bank_name}
                  className="p-2.5 rounded-lg bg-surface-container border border-[#1e2430]"
                >
                  <div className="text-[10px] font-mono uppercase text-primary truncate font-semibold">
                    {b.bank_name}
                  </div>
                  <div className="mt-1 text-xs font-mono font-bold text-white tabular-nums truncate">
                    Bs. {b.theoretical_ves.toFixed(2)}
                  </div>
                  <div className="text-[9px] font-mono text-slate-500 tabular-nums truncate">
                    +{b.inflows_ves.toFixed(0)} / -{b.outflows_ves.toFixed(0)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Card 2: Inventario Cripto Teórico (USDT) */}
          <div className="lg:col-span-3 p-4 rounded-xl bg-surface-container-low border border-[#1e2430] flex flex-col justify-between gap-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  Inventario Cripto (USDT)
                </div>
                <div className="mt-1 text-2xl font-mono font-bold text-tertiary tabular-nums">
                  {(liveBalance?.theoretical_usdt ?? 0).toFixed(2)} USDT
                </div>
              </div>
              <div className="text-right">
                <label className="block text-[9px] font-mono uppercase text-slate-500">
                  Inicial USDT
                </label>
                <input
                  type="number"
                  value={initialUsdt}
                  onChange={(e) => setInitialUsdt(Number(e.target.value))}
                  className="w-20 mt-0.5 px-2 py-1 rounded bg-surface-container-lowest border border-[#1e2430] text-right text-xs font-mono text-tertiary tabular-nums"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs font-mono tabular-nums">
              <div className="p-2 rounded-lg bg-surface-container border border-[#1e2430]">
                <div className="text-[9px] text-slate-400 uppercase">Compras P2P</div>
                <div className="text-tertiary font-semibold mt-0.5">
                  +{(liveBalance?.inflow_usdt ?? 0).toFixed(2)}
                </div>
              </div>
              <div className="p-2 rounded-lg bg-surface-container border border-[#1e2430]">
                <div className="text-[9px] text-slate-400 uppercase">Ventas P2P</div>
                <div className="text-primary font-semibold mt-0.5">
                  -{(liveBalance?.outflow_usdt ?? 0).toFixed(2)}
                </div>
              </div>
            </div>
          </div>

          {/* Card 3: Motor OCR de Comprobantes Bancarios y Auto-Conciliación */}
          <div className="lg:col-span-4 p-4 rounded-xl bg-surface-container border border-[#1e2430] flex flex-col justify-between gap-3">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-secondary">
                  document_scanner
                </span>
                <span className="text-xs font-bold text-white">
                  Conciliación OCR Bancaria
                </span>
              </div>
              <span className="px-2 py-0.5 rounded bg-secondary/15 text-secondary text-[10px] font-mono font-semibold whitespace-nowrap">
                Tolerancia 48h
              </span>
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed">
              Extrae referencia, banco, monto VES y comisión Pago Móvil desde capturas bancarias para asentar el gasto automáticamente.
            </p>

            <input
              ref={voucherInputRef}
              type="file"
              accept="image/*,.pdf"
              onChange={handleUploadReceipt}
              className="hidden"
            />

            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => voucherInputRef.current?.click()}
                disabled={uploadingOcr || periodClosed}
                className="flex-1 px-3 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-50 flex items-center justify-center gap-1.5 whitespace-nowrap"
              >
                <span className="material-symbols-outlined text-[16px]">
                  add_photo_alternate
                </span>
                <span>{uploadingOcr ? "Analizando OCR..." : "Cargar Recibo"}</span>
              </button>

              <button
                type="button"
                onClick={handleAutoReconcile}
                disabled={reconciling || periodClosed}
                className="px-3 py-2 rounded-lg bg-surface-container-high border border-[#1e2430] hover:border-secondary/50 text-xs font-mono text-slate-200 flex items-center gap-1.5 whitespace-nowrap"
              >
                <span className="material-symbols-outlined text-[16px] text-secondary">
                  auto_fix_high
                </span>
                <span>{reconciling ? "Cruzando..." : "Auto-Conciliar"}</span>
              </button>
            </div>
          </div>
        </section>

        {/* Tarjeta de Vinculación Manual si el último recibo OCR quedó huérfano */}
        {lastVoucher && (
          <section className="p-4 rounded-xl bg-surface-container border border-secondary/40 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="text-xs space-y-1">
              <div className="font-bold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] text-secondary">
                  receipt
                </span>
                Recibo OCR Detectado: {lastVoucher.bank_name} • Ref #
                {lastVoucher.reference_number}
              </div>
              <div className="font-mono text-slate-300 tabular-nums">
                Monto: Bs. {lastVoucher.amount_ves.toFixed(2)} | Comisión Bancaria: Bs.{" "}
                {lastVoucher.bank_fee_ves.toFixed(2)} | Estado:{" "}
                <span className="text-primary">{lastVoucher.verification_status}</span>
              </div>
            </div>

            <form onSubmit={handleManualMatch} className="flex items-center gap-2">
              <input
                type="text"
                value={manualOrderNumber}
                onChange={(e) => setManualOrderNumber(e.target.value)}
                placeholder="Nº Orden Binance P2P"
                className="px-3 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono text-white"
              />
              <button
                type="submit"
                className="px-3 py-1.5 rounded-lg bg-secondary text-on-secondary text-xs font-bold whitespace-nowrap"
              >
                Vincular Orden
              </button>
              <button
                type="button"
                onClick={() => setLastVoucher(null)}
                className="text-xs text-slate-400 hover:text-white px-2"
              >
                Cerrar
              </button>
            </form>
          </section>
        )}

        {/* Pestañas Contables: Libro Diario | Libro Mayor | Ecuación Fiscal 6 Piezas */}
        <section className="rounded-xl bg-surface-container-low border border-[#1e2430] overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1e2430] flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-1 bg-surface-container p-1 rounded-lg border border-[#1e2430] text-xs font-mono">
              <button
                type="button"
                onClick={() => setActiveTab("JOURNAL")}
                className={`px-3 py-1 rounded-md transition-colors ${
                  activeTab === "JOURNAL"
                    ? "bg-primary-container text-on-primary font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Libro Diario ({journalEntries.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("LEDGER")}
                className={`px-3 py-1 rounded-md transition-colors ${
                  activeTab === "LEDGER"
                    ? "bg-primary-container text-on-primary font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Libro Mayor ({ledgerSummaries.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("FISCAL_6")}
                className={`px-3 py-1 rounded-md transition-colors ${
                  activeTab === "FISCAL_6"
                    ? "bg-primary-container text-on-primary font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Conciliación 6 Piezas
              </button>
            </div>

            <span className="text-[11px] font-mono text-slate-400">
               Cadena de integridad SHA-256 verificada • Moneda Funcional VES
            </span>
          </div>

          {activeTab === "JOURNAL" && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[#1e2430] bg-surface-container/60 text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    <th className="py-3 px-4">Asiento / Fecha</th>
                    <th className="py-3 px-4">Código & Cuenta</th>
                    <th className="py-3 px-4">Concepto / Referencia</th>
                    <th className="py-3 px-4 text-right">Debe (VES)</th>
                    <th className="py-3 px-4 text-right">Haber (VES)</th>
                    <th className="py-3 px-4 text-right">Hash SHA-256</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2430]/70 text-xs">
                  {loading ? (
                    <tr>
                      <td colSpan={6} className="py-10 text-center text-slate-400 font-mono">
                        Consultando asientos en partida doble...
                      </td>
                    </tr>
                  ) : journalEntries.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-10 text-center text-slate-400 font-mono">
                        No hay asientos en el período seleccionado. Sincroniza órdenes o carga recibos OCR.
                      </td>
                    </tr>
                  ) : (
                    journalEntries.map((entry, idx) => (
                      <tr
                        key={`${entry.entry_number}-${entry.account_code}-${idx}`}
                        className="hover:bg-surface-container/70 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono tabular-nums">
                          <div className="text-white font-semibold">
                            #{entry.entry_number}
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {entry.date_time}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-mono text-primary text-[11px] mr-1.5">
                            {entry.account_code}
                          </span>
                          <span className="text-white font-medium">
                            {entry.account_name}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-300 max-w-xs truncate">
                          <div>{entry.description}</div>
                          <div className="text-[10px] font-mono text-slate-500">
                            Ref: {entry.reference}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-tertiary font-semibold">
                          {entry.debit > 0 ? `Bs. ${entry.debit.toFixed(2)}` : "-"}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-primary font-semibold">
                          {entry.credit > 0 ? `Bs. ${entry.credit.toFixed(2)}` : "-"}
                        </td>
                        <td className="py-3 px-4 text-right font-mono text-[10px] text-slate-500">
                          {entry.entry_hash?.slice(0, 10)}…
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === "LEDGER" && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[#1e2430] bg-surface-container/60 text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    <th className="py-3 px-4">Código</th>
                    <th className="py-3 px-4">Cuenta Mayor</th>
                    <th className="py-3 px-4 text-right">Saldo Inicial</th>
                    <th className="py-3 px-4 text-right">Total Debe</th>
                    <th className="py-3 px-4 text-right">Total Haber</th>
                    <th className="py-3 px-4 text-right">Saldo Final</th>
                    <th className="py-3 px-4 text-right">Movimientos</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2430]/70 text-xs">
                  {ledgerSummaries.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-10 text-center text-slate-400 font-mono">
                        Sin saldos consolidados en el Libro Mayor para este mes.
                      </td>
                    </tr>
                  ) : (
                    ledgerSummaries.map((l) => (
                      <tr
                        key={l.account_code}
                        className="hover:bg-surface-container/70 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono text-primary font-semibold">
                          {l.account_code}
                        </td>
                        <td className="py-3 px-4 text-white font-medium">
                          {l.account_name}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-slate-400">
                          Bs. {l.initial_balance.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-tertiary">
                          Bs. {l.total_debit.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-primary">
                          Bs. {l.total_credit.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-white font-bold">
                          Bs. {l.final_balance.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-slate-400">
                          {l.entries_count}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === "FISCAL_6" && (
            <div className="p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {[
                {
                  title: "1. Saldo Inicial Declarado",
                  val: fiscalSummary?.initial_balance ?? 0,
                  tone: "text-white",
                },
                {
                  title: "2. Entradas Operativas (Ventas VES)",
                  val: fiscalSummary?.total_inflows ?? 0,
                  tone: "text-tertiary",
                },
                {
                  title: "3. Salidas Operativas (Compras VES)",
                  val: fiscalSummary?.total_outflows ?? 0,
                  tone: "text-primary",
                },
                {
                  title: "4. Comisiones Deducibles",
                  val: fiscalSummary?.total_fees ?? 0,
                  tone: "text-slate-200",
                },
                {
                  title: "5. Saldo Final Calculado",
                  val: fiscalSummary?.calculated_final_balance ?? 0,
                  tone: "text-secondary",
                },
                {
                  title: "6. Utilidad Neta Fiscal (VES)",
                  val: fiscalSummary?.net_profit_ves ?? 0,
                  tone: "text-tertiary",
                },
              ].map((piece) => (
                <div
                  key={piece.title}
                  className="p-4 rounded-xl bg-surface-container border border-[#1e2430]"
                >
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    {piece.title}
                  </div>
                  <div
                    className={`mt-2 text-lg font-mono font-bold tabular-nums ${piece.tone}`}
                  >
                    Bs.{" "}
                    {piece.val.toLocaleString("es-VE", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Modal Fail-Closed de Cierre Mensual */}
        {showCloseModal && (
          <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="w-full max-w-md rounded-2xl bg-surface-container-low border border-primary-container/40 p-6 space-y-4 shadow-2xl">
              <div className="flex items-center gap-2 text-primary font-bold text-base">
                <span className="material-symbols-outlined">gpp_maybe</span>
                <span>Confirmación Fail-Closed de Cierre Contable</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Estás sellando el período{" "}
                <strong className="text-white">
                  {MONTHS.find((m) => m.value === month)?.label} {year}
                </strong>
                . Se bloqueará la carga de recibos OCR adicionales en la sesión actual y podrás descargar los respaldos firmados. Escribe{" "}
                <code className="text-primary font-mono font-bold">CERRAR-MES</code> para confirmar:
              </p>
              <input
                type="text"
                value={closeConfirmText}
                onChange={(e) => setCloseConfirmText(e.target.value)}
                placeholder="Escribe CERRAR-MES"
                className="w-full px-3.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-sm font-mono text-white"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setCloseConfirmText("");
                    setShowCloseModal(false);
                  }}
                  className="px-3.5 py-2 rounded-lg bg-surface-container text-xs text-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  disabled={closeConfirmText !== "CERRAR-MES"}
                  onClick={() => {
                    setPeriodClosed(true);
                    setCloseConfirmText("");
                    setShowCloseModal(false);
                    setFeedback({
                      type: "success",
                      text: `Período ${month}/${year} sellado en modo lectura. Descarga tu Excel o PDF auditable arriba.`,
                    });
                  }}
                  className="px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold disabled:opacity-40"
                >
                  Confirmar Sello Contable
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
