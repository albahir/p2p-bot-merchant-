"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Calendar,
  CheckCircle2,
  DollarSign,
  Download,
  FileSpreadsheet,
  FileText,
  Filter,
  Landmark,
  RefreshCw,
  Search,
  ShieldCheck,
  UploadCloud,
  Wallet,
} from "lucide-react";

import {
  getCurrentUser,
  getExportAccountingExcelUrl,
  getExportAccountingPdfUrl,
  getJournalEntries,
  getLedgerSummaries,
  JournalEntryItem,
  LedgerSummaryItem,
  uploadVoucherFile,
  UploadVoucherResponse,
  User,
} from "@/lib/api";

export default function AccountingPage() {
  const [user, setUser] = useState<User | null>(null);
  const now = new Date();
  const [year, setYear] = useState<number>(now.getFullYear());
  const [month, setMonth] = useState<number>(now.getMonth() + 1);

  // Estados de datos
  const [journalEntries, setJournalEntries] = useState<JournalEntryItem[]>([]);
  const [ledgerSummaries, setLedgerSummaries] = useState<LedgerSummaryItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Filtros de Libro Diario
  const [searchRef, setSearchRef] = useState<string>("");
  const [selectedAccount, setSelectedAccount] = useState<string>("ALL");
  const [activeTab, setActiveTab] = useState<"DIARIO" | "MAYOR">("DIARIO");

  // Estado de carga de comprobantes
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadFeedback, setUploadFeedback] = useState<UploadVoucherResponse | null>(null);

  const loadData = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMsg(null);
      const [entries, ledgers] = await Promise.all([
        getJournalEntries(),
        getLedgerSummaries(year, month),
      ]);
      setJournalEntries(entries);
      setLedgerSummaries(ledgers);
    } catch (err: any) {
      setErrorMsg(err.message || "Error al cargar la información contable.");
    } finally {
      setIsLoading(false);
    }
  }, [year, month]);

  useEffect(() => {
    setUser(getCurrentUser());
    loadData();
  }, [loadData]);

  // Manejo de Dropzone para Comprobantes
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setIsUploading(true);
      setUploadFeedback(null);
      const res = await uploadVoucherFile(file);
      setUploadFeedback(res);
      await loadData();
    } catch (err: any) {
      setErrorMsg(err.message || "Error procesando el comprobante bancario.");
    } finally {
      setIsUploading(false);
    }
  };

  // Filtrado de Libro Diario
  const filteredEntries = journalEntries.filter((e) => {
    const matchesAccount = selectedAccount === "ALL" || e.account_code === selectedAccount;
    const q = searchRef.toLowerCase();
    const matchesSearch =
      !searchRef ||
      e.reference.toLowerCase().includes(q) ||
      e.description.toLowerCase().includes(q) ||
      e.account_name.toLowerCase().includes(q);
    return matchesAccount && matchesSearch;
  });

  // Cálculos de totales
  const totalDebe = filteredEntries.reduce((sum, e) => sum + e.debit, 0);
  const totalHaber = filteredEntries.reduce((sum, e) => sum + e.credit, 0);
  const isJournalBalanced = Math.abs(totalDebe - totalHaber) < 0.01;

  // Cuentas destacadas
  const bancoVES = ledgerSummaries.find((s) => s.account_code === "1.1.01");
  const activoUSDT = ledgerSummaries.find((s) => s.account_code === "1.1.05");
  const comisionesBanco = ledgerSummaries.find((s) => s.account_code === "5.2.01");

  return (
    <div className="w-full max-w-7xl mx-auto space-y-5 font-sans pb-16">
      {/* Barra de Navegación y Retorno */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800 text-xs">
        <div className="flex items-center space-x-4">
          <a
            href="/"
            className="inline-flex items-center space-x-1.5 font-semibold text-slate-700 dark:text-slate-300 hover:text-red-600 dark:hover:text-red-400 transition-colors"
          >
            <span>← Terminal Principal</span>
          </a>
          <span className="text-slate-400 dark:text-slate-600">|</span>
          <a
            href="/fiscal"
            className="inline-flex items-center space-x-1.5 font-semibold text-slate-700 dark:text-slate-300 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors"
          >
            <span>Reconstrucción Fiscal (6 Piezas) →</span>
          </a>
        </div>
        <div className="flex items-center space-x-2 text-slate-500 font-mono text-[11px]">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
          <span>Partida Doble // Encadenamiento Criptográfico SHA-256</span>
        </div>
      </div>

      {/* Cabecera del Módulo */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-white dark:bg-[#0D111A] p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-2.5">
            <span className="p-2 rounded-lg bg-red-600 text-white">
              <BookOpen className="h-4 w-4" />
            </span>
            <span>Sistema Contable P2P: Libro Diario & Libro Mayor</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Registro cronológico inmutable con cuadre de partida doble (Debe = Haber) y conciliación automática.
          </p>
        </div>

        {/* Parámetros de Período y Botones de Exportación */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center space-x-2 bg-slate-50 dark:bg-[#121622] px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700">
            <Calendar className="h-3.5 w-3.5 text-slate-400" />
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="bg-transparent text-xs font-semibold text-slate-800 dark:text-slate-200 outline-none"
            >
              {[2024, 2025, 2026, 2027].map((y) => (
                <option key={y} value={y} className="dark:bg-[#121622]">
                  {y}
                </option>
              ))}
            </select>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="bg-transparent text-xs font-semibold text-slate-800 dark:text-slate-200 outline-none"
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m} className="dark:bg-[#121622]">
                  Mes {m.toString().padStart(2, "0")}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={loadData}
            disabled={isLoading}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-lg text-xs font-semibold transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Actualizar</span>
          </button>

          <a
            href={getExportAccountingExcelUrl(year, month)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold transition-colors shadow-xs"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            <span>Excel (.xlsx)</span>
          </a>

          <a
            href={getExportAccountingPdfUrl(year, month)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold transition-colors shadow-xs"
          >
            <FileText className="h-3.5 w-3.5" />
            <span>PDF SENIAT</span>
          </a>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-400 text-xs flex items-center space-x-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Tarjetas de Saldo del Libro Mayor */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Banco Nacional VES */}
        <div className="bg-white dark:bg-[#0D111A] p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <Landmark className="h-3.5 w-3.5 text-blue-500" />
              1.1.01 Banco Nacional VES
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">
              Activo Circulante
            </span>
          </div>
          <div className="space-y-1">
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100">
              Bs. {(bancoVES?.final_balance || 0).toLocaleString("es-VE", { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-slate-500 dark:text-slate-400 flex justify-between">
              <span>Saldo Inicial: Bs. {(bancoVES?.initial_balance || 0).toLocaleString("es-VE", { minimumFractionDigits: 2 })}</span>
              <span>Movs: {bancoVES?.entries_count || 0}</span>
            </div>
          </div>
          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-between text-[11px]">
            <span className="text-emerald-600 dark:text-emerald-400 font-mono">
              + Debe: Bs. {(bancoVES?.total_debit || 0).toLocaleString("es-VE", { minimumFractionDigits: 2 })}
            </span>
            <span className="text-rose-600 dark:text-rose-400 font-mono">
              - Haber: Bs. {(bancoVES?.total_credit || 0).toLocaleString("es-VE", { minimumFractionDigits: 2 })}
            </span>
          </div>
        </div>

        {/* Activos Criptográficos USDT */}
        <div className="bg-white dark:bg-[#0D111A] p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <Wallet className="h-3.5 w-3.5 text-emerald-500" />
              1.1.05 Activos Cripto USDT
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400">
              Inventario Cripto
            </span>
          </div>
          <div className="space-y-1">
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100">
              Bs. {(activoUSDT?.final_balance || 0).toLocaleString("es-VE", { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-slate-500 dark:text-slate-400 flex justify-between">
              <span>Saldo Inicial: Bs. {(activoUSDT?.initial_balance || 0).toLocaleString("es-VE", { minimumFractionDigits: 2 })}</span>
              <span>Movs: {activoUSDT?.entries_count || 0}</span>
            </div>
          </div>
          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-between text-[11px]">
            <span className="text-emerald-600 dark:text-emerald-400 font-mono">
              + Compras: Bs. {(activoUSDT?.total_debit || 0).toLocaleString("es-VE", { minimumFractionDigits: 2 })}
            </span>
            <span className="text-rose-600 dark:text-rose-400 font-mono">
              - Ventas: Bs. {(activoUSDT?.total_credit || 0).toLocaleString("es-VE", { minimumFractionDigits: 2 })}
            </span>
          </div>
        </div>

        {/* Comisiones Bancarias Deducibles */}
        <div className="bg-white dark:bg-[#0D111A] p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <DollarSign className="h-3.5 w-3.5 text-amber-500" />
              5.2.01 Gastos Comisiones Bancarias
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400">
              Gasto Deducible
            </span>
          </div>
          <div className="space-y-1">
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100">
              Bs. {(comisionesBanco?.total_debit || 0).toLocaleString("es-VE", { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-slate-500 dark:text-slate-400">
              Tarifa interbancaria (0.30% en débitos de compras)
            </div>
          </div>
          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500">
            Deducción legal directa para declaración de ISLR
          </div>
        </div>
      </div>

      {/* Zona de Arrastre de Comprobantes (Dropzone Multimodal) */}
      <div className="bg-white dark:bg-[#0D111A] p-4 rounded-xl border border-dashed border-slate-300 dark:border-slate-700 hover:border-red-500 transition-colors">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-red-50 dark:bg-red-950/40 rounded-xl text-red-600">
              <UploadCloud className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100">
                Carga Masiva de Comprobantes Bancarios (Pago Móvil / Transferencias)
              </h3>
              <p className="text-[11px] text-slate-500">
                Soporta imágenes JPG y PNG. Extracción OCR multimodal automática y auto-asiento contable.
              </p>
            </div>
          </div>
          <label className="cursor-pointer px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-bold transition-colors shrink-0">
            {isUploading ? "Analizando comprobante..." : "Seleccionar Comprobante"}
            <input
              type="file"
              accept="image/jpeg,image/png"
              className="hidden"
              onChange={handleFileUpload}
              disabled={isUploading}
            />
          </label>
        </div>

        {uploadFeedback && (
          <div className="mt-3 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-xs text-emerald-600 dark:text-emerald-400 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>
                Comprobante #{uploadFeedback.voucher_id} de {uploadFeedback.bank_name} por Bs. {uploadFeedback.amount_ves} procesado con éxito.
              </span>
            </div>
            <span className="font-mono text-[11px] font-bold">
              {uploadFeedback.verification_status === "MATCHED"
                ? `AUTO-CONCILIADO con orden ${uploadFeedback.matched_order_number}`
                : "PENDIENTE POR VINCULAR"}
            </span>
          </div>
        )}
      </div>

      {/* Selector de Pestaña Contable */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800">
        <div className="flex space-x-6 text-xs font-bold">
          <button
            onClick={() => setActiveTab("DIARIO")}
            className={`pb-2.5 transition-colors border-b-2 ${
              activeTab === "DIARIO"
                ? "border-red-600 text-red-600 dark:text-red-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            Libro Diario (Partida Doble)
          </button>
          <button
            onClick={() => setActiveTab("MAYOR")}
            className={`pb-2.5 transition-colors border-b-2 ${
              activeTab === "MAYOR"
                ? "border-red-600 text-red-600 dark:text-red-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            Libro Mayor (Consolidación Mensual)
          </button>
        </div>

        {activeTab === "DIARIO" && (
          <div className="flex items-center space-x-2 pb-2">
            <span
              className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded ${
                isJournalBalanced
                  ? "bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400"
                  : "bg-rose-50 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400"
              }`}
            >
              {isJournalBalanced ? "✓ CUADRE DEBE = HABER" : "⚠ DESCUADRE DETECTADO"}
            </span>
          </div>
        )}
      </div>

      {/* Contenido de Pestaña: LIBRO DIARIO */}
      {activeTab === "DIARIO" && (
        <div className="space-y-3">
          {/* Barra de Filtros */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-white dark:bg-[#0D111A] p-3 rounded-xl border border-slate-200 dark:border-slate-800">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Buscar por referencia o glosa..."
                value={searchRef}
                onChange={(e) => setSearchRef(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 bg-slate-50 dark:bg-[#121622] rounded-lg border border-slate-200 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-200 outline-none"
              />
            </div>
            <div className="flex items-center space-x-2 text-xs">
              <Filter className="h-3.5 w-3.5 text-slate-400" />
              <select
                value={selectedAccount}
                onChange={(e) => setSelectedAccount(e.target.value)}
                className="bg-slate-50 dark:bg-[#121622] px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-200 outline-none"
              >
                <option value="ALL">Todas las Cuentas</option>
                <option value="1.1.01">1.1.01 Bancos VES</option>
                <option value="1.1.05">1.1.05 Activos USDT</option>
                <option value="5.2.01">5.2.01 Comisiones Bancarias</option>
              </select>
            </div>
          </div>

          {/* Tabla de Asientos */}
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0D111A]">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-[#121622] border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="py-2.5 px-3">Asiento</th>
                  <th className="py-2.5 px-3">Fecha</th>
                  <th className="py-2.5 px-3">Cuenta</th>
                  <th className="py-2.5 px-3">Detalle / Glosa</th>
                  <th className="py-2.5 px-3 text-right">Debe (VES)</th>
                  <th className="py-2.5 px-3 text-right">Haber (VES)</th>
                  <th className="py-2.5 px-3">Referencia</th>
                  <th className="py-2.5 px-3">Hash Criptográfico</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                {filteredEntries.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-slate-400 font-sans">
                      No se encontraron asientos contables registrados.
                    </td>
                  </tr>
                ) : (
                  filteredEntries.map((e, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                      <td className="py-2 px-3 font-bold text-slate-900 dark:text-slate-100">
                        #{e.entry_number}
                      </td>
                      <td className="py-2 px-3 text-slate-500">{e.date_time}</td>
                      <td className="py-2 px-3 font-semibold text-blue-600 dark:text-blue-400">
                        {e.account_code}
                      </td>
                      <td className="py-2 px-3 font-sans text-slate-800 dark:text-slate-200 max-w-xs truncate">
                        {e.description}
                      </td>
                      <td className="py-2 px-3 text-right text-emerald-600 dark:text-emerald-400 font-bold">
                        {e.debit > 0 ? e.debit.toLocaleString("es-VE", { minimumFractionDigits: 2 }) : "-"}
                      </td>
                      <td className="py-2 px-3 text-right text-rose-600 dark:text-rose-400 font-bold">
                        {e.credit > 0 ? e.credit.toLocaleString("es-VE", { minimumFractionDigits: 2 }) : "-"}
                      </td>
                      <td className="py-2 px-3 text-slate-600 dark:text-slate-400">{e.reference}</td>
                      <td className="py-2 px-3 text-slate-400 text-[10px] truncate max-w-[120px]" title={e.entry_hash}>
                        {e.entry_hash.slice(0, 16)}...
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              <tfoot className="bg-slate-50 dark:bg-[#121622] font-mono font-bold text-xs border-t border-slate-200 dark:border-slate-800">
                <tr>
                  <td colSpan={4} className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-400">
                    Totales Período:
                  </td>
                  <td className="py-2.5 px-3 text-right text-emerald-600 dark:text-emerald-400">
                    Bs. {totalDebe.toLocaleString("es-VE", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-right text-rose-600 dark:text-rose-400">
                    Bs. {totalHaber.toLocaleString("es-VE", { minimumFractionDigits: 2 })}
                  </td>
                  <td colSpan={2} className="py-2.5 px-3 text-[11px] text-slate-400">
                    Diferencia: Bs. {Math.abs(totalDebe - totalHaber).toFixed(2)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Contenido de Pestaña: LIBRO MAYOR */}
      {activeTab === "MAYOR" && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0D111A]">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 dark:bg-[#121622] border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="py-2.5 px-3">Código</th>
                <th className="py-2.5 px-3">Cuenta Contable</th>
                <th className="py-2.5 px-3">Período</th>
                <th className="py-2.5 px-3 text-right">Saldo Inicial (VES)</th>
                <th className="py-2.5 px-3 text-right">Total Debe (VES)</th>
                <th className="py-2.5 px-3 text-right">Total Haber (VES)</th>
                <th className="py-2.5 px-3 text-right">Saldo Final (VES)</th>
                <th className="py-2.5 px-3 text-center">N° Movs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
              {ledgerSummaries.map((s, idx) => (
                <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                  <td className="py-2.5 px-3 font-bold text-blue-600 dark:text-blue-400">
                    {s.account_code}
                  </td>
                  <td className="py-2.5 px-3 font-sans font-semibold text-slate-900 dark:text-slate-100">
                    {s.account_name}
                  </td>
                  <td className="py-2.5 px-3 text-slate-500">
                    {s.year}-{s.month.toString().padStart(2, "0")}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-700 dark:text-slate-300">
                    {s.initial_balance.toLocaleString("es-VE", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-right text-emerald-600 dark:text-emerald-400 font-bold">
                    {s.total_debit.toLocaleString("es-VE", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-right text-rose-600 dark:text-rose-400 font-bold">
                    {s.total_credit.toLocaleString("es-VE", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-900 dark:text-slate-100 font-bold text-xs">
                    {s.final_balance.toLocaleString("es-VE", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-center text-slate-500">{s.entries_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
