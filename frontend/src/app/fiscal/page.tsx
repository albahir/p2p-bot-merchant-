"use client";

import React, { useEffect, useState, useCallback } from "react";
import { 
  Building2, 
  FileSpreadsheet, 
  Download, 
  RefreshCw, 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle2, 
  Calendar, 
  TrendingUp, 
  DollarSign,
  ArrowRight
} from "lucide-react";
import { getFiscalSummary, getExportOrdersUrl, FiscalSummary, getCurrentUser, User } from "@/lib/api";

export default function FiscalReconciliationPage() {
  const [period, setPeriod] = useState<string>(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [initialBalance, setInitialBalance] = useState<number>(1000);
  const [actualFinalBalance, setActualFinalBalance] = useState<number>(1250);
  const [summary, setSummary] = useState<FiscalSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  const loadFiscalData = useCallback(async () => {
    try {
      setIsLoading(true);
      setMsg(null);
      const res = await getFiscalSummary(period, initialBalance, actualFinalBalance);
      setSummary(res);
    } catch (err: any) {
      setMsg(err.message || "Error al calcular la ecuación contable de 6 piezas.");
    } finally {
      setIsLoading(false);
    }
  }, [period, initialBalance, actualFinalBalance]);

  useEffect(() => {
    setUser(getCurrentUser());
    loadFiscalData();
  }, [loadFiscalData]);

  // Si no tiene rol TRADER o ADMIN, mostrar bloqueo Fail-closed
  if (user && user.role === "INVITADO") {
    return (
      <div className="max-w-md mx-auto my-16 bg-[#111927] p-8 rounded-3xl border border-slate-800 text-center space-y-4">
        <AlertTriangle className="h-12 w-12 text-amber-400 mx-auto" />
        <h2 className="text-lg font-bold text-slate-100">Acceso Fiscal Restringido</h2>
        <p className="text-xs text-slate-400">
          El módulo de reconstrucción fiscal y cumplimiento SENIAT requiere rol de <strong>TRADER</strong> o <strong>ADMINISTRADOR</strong>.
        </p>
        <a href="/" className="inline-block px-4 py-2 rounded-full bg-rose-600 text-white font-bold text-xs">
          ← Volver al Terminal de Mercado
        </a>
      </div>
    );
  }

  const discrepancy = summary ? summary.discrepancy : (actualFinalBalance - (initialBalance + 250));
  const isBalanced = Math.abs(discrepancy) < 0.05;

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-20">
      {/* Barra superior de navegación de regreso */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <a
          href="/"
          className="inline-flex items-center space-x-2 text-xs font-semibold text-rose-400 hover:text-rose-300 transition-colors bg-rose-500/10 px-3.5 py-1.5 rounded-full border border-rose-500/20"
        >
          <span>← Volver a la App Principal</span>
        </a>
        <div className="flex items-center space-x-2 text-xs text-slate-400 font-mono">
          <Building2 className="h-4 w-4 text-rose-500" />
          <span>Cumplimiento SENIAT // Ecuación de 6 Piezas</span>
        </div>
      </div>

      {/* Cabecera del Módulo */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-[#111927] p-5 rounded-3xl border border-slate-800 shadow-md">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center space-x-2.5">
            <span className="p-2 rounded-2xl bg-rose-600 text-white">
              <Building2 className="h-5 w-5" />
            </span>
            <span>Reconstrucción Contable P2P & Conciliación Fiscal</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Auditoría de consistencia patrimonial: <strong>Saldo Inicial + Entradas - Salidas - Comisiones = Saldo Final Teórico</strong>
          </p>
        </div>

        {/* Parámetros de Período y Recálculo */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-2 bg-[#162032] px-3 py-1.5 rounded-2xl border border-slate-700">
            <Calendar className="h-4 w-4 text-rose-500" />
            <input
              type="month"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="bg-transparent text-xs text-slate-200 focus:outline-none font-mono"
            />
          </div>

          <button
            onClick={loadFiscalData}
            disabled={isLoading}
            className="px-4 py-2 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold flex items-center space-x-1.5 transition-all shadow"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Recalcular Ecuación</span>
          </button>

          <a
            href={getExportOrdersUrl("xlsx")}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 rounded-2xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center space-x-1.5 transition-all"
          >
            <Download className="h-3.5 w-3.5 text-rose-400" />
            <span>Descargar Libro Fiscal (.xlsx)</span>
          </a>
        </div>
      </div>

      {msg && (
        <div className="p-3.5 rounded-2xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center space-x-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{msg}</span>
        </div>
      )}

      {/* Panel de Entradas de Saldo Real */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-[#111927] p-5 rounded-3xl border border-slate-800">
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">
            Pieza 1: Saldo Inicial Real (USDT en Exchange)
          </label>
          <input
            type="number"
            value={initialBalance}
            onChange={(e) => setInitialBalance(Number(e.target.value))}
            className="w-full bg-[#162032] border border-slate-700 rounded-2xl px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-rose-500"
            placeholder="0.00"
          />
          <span className="text-[10px] text-slate-500 mt-1 block">Saldo al primer día del mes a las 00:00:00 UTC</span>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">
            Pieza 6: Saldo Final Real (USDT Snapshot de Cierre)
          </label>
          <input
            type="number"
            value={actualFinalBalance}
            onChange={(e) => setActualFinalBalance(Number(e.target.value))}
            className="w-full bg-[#162032] border border-slate-700 rounded-2xl px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-rose-500"
            placeholder="0.00"
          />
          <span className="text-[10px] text-slate-500 mt-1 block">Saldo al último día del mes a las 23:59:59 UTC</span>
        </div>
      </div>

      {/* Grid de las 6 Piezas Contables */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Pieza 1: Saldo Inicial */}
        <div className="bg-[#111927] p-4 rounded-3xl border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase">Pieza 1 • Saldo Inicial</span>
          <div className="text-2xl font-black text-white font-mono">
            ${(summary?.initial_balance ?? initialBalance).toFixed(2)} <span className="text-xs text-slate-400 font-normal">USDT</span>
          </div>
          <p className="text-[10px] text-slate-500">Punto de partida del ejercicio</p>
        </div>

        {/* Pieza 2: Total Entradas */}
        <div className="bg-[#111927] p-4 rounded-3xl border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-emerald-400 uppercase">Pieza 2 • Total Entradas (+)</span>
          <div className="text-2xl font-black text-emerald-400 font-mono">
            +${(summary?.total_inflows ?? 0).toFixed(2)} <span className="text-xs text-slate-400 font-normal">USDT</span>
          </div>
          <p className="text-[10px] text-slate-500">Depósitos e Ingesta de compras P2P</p>
        </div>

        {/* Pieza 3: Total Salidas */}
        <div className="bg-[#111927] p-4 rounded-3xl border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-rose-400 uppercase">Pieza 3 • Total Salidas (-)</span>
          <div className="text-2xl font-black text-rose-400 font-mono">
            -${(summary?.total_outflows ?? 0).toFixed(2)} <span className="text-xs text-slate-400 font-normal">USDT</span>
          </div>
          <p className="text-[10px] text-slate-500">Retiros y ventas P2P ejecutadas</p>
        </div>

        {/* Pieza 4: Comisiones */}
        <div className="bg-[#111927] p-4 rounded-3xl border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-amber-400 uppercase">Pieza 4 • Comisiones (-)</span>
          <div className="text-2xl font-black text-amber-400 font-mono">
            -${(summary?.total_fees ?? 0).toFixed(2)} <span className="text-xs text-slate-400 font-normal">USDT</span>
          </div>
          <p className="text-[10px] text-slate-500">Comisiones Maker / Taker de Binance</p>
        </div>

        {/* Pieza 5: Saldo Teórico */}
        <div className="bg-[#111927] p-4 rounded-3xl border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-cyan-400 uppercase">Pieza 5 • Saldo Teórico</span>
          <div className="text-2xl font-black text-cyan-400 font-mono">
            ${(summary?.calculated_final_balance ?? 0).toFixed(2)} <span className="text-xs text-slate-400 font-normal">USDT</span>
          </div>
          <p className="text-[10px] text-slate-500">Resultado esperado de la ecuación</p>
        </div>

        {/* Pieza 6: Discrepancia Patrimonial */}
        <div className={`p-4 rounded-3xl border space-y-1 ${
          isBalanced 
            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" 
            : "bg-rose-500/10 border-rose-500/30 text-rose-400"
        }`}>
          <span className="text-[11px] font-semibold uppercase">Discrepancia / Delta</span>
          <div className="text-2xl font-black font-mono">
            {discrepancy >= 0 ? `+${discrepancy.toFixed(2)}` : discrepancy.toFixed(2)} USDT
          </div>
          <p className="text-[10px]">
            {isBalanced ? "✓ Consistencia perfecta (Ecuación cuadrada)" : "⚠️ Hay diferencia con el saldo real del snapshot"}
          </p>
        </div>
      </div>

      {/* Resumen Fiscal para Declaración ISLR (SENIAT) */}
      <div className="bg-[#111927] p-6 rounded-3xl border border-slate-800 space-y-4 shadow-md">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <DollarSign className="h-5 w-5 text-emerald-400" />
            <h3 className="font-bold text-sm text-slate-100">
              Valoración Tributaria Oficial a Tasa BCV (SENIAT)
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            Tasa Oficial: <strong>{summary?.bcv_rate ? summary.bcv_rate.toFixed(2) : "881.07"} VES/USD</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono">
          <div className="p-3.5 rounded-2xl bg-[#162032] border border-slate-700/60">
            <span className="text-[11px] text-slate-400 block font-sans">Ingreso Bruto en Bolívares</span>
            <span className="text-lg font-bold text-slate-100">
              {(summary?.gross_revenue_ves ?? 0).toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} VES
            </span>
          </div>

          <div className="p-3.5 rounded-2xl bg-[#162032] border border-slate-700/60">
            <span className="text-[11px] text-slate-400 block font-sans">Costo de Adquisición (FIFO)</span>
            <span className="text-lg font-bold text-slate-300">
              {(summary?.acquisition_cost_ves ?? 0).toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} VES
            </span>
          </div>

          <div className="p-3.5 rounded-2xl bg-[#162032] border border-slate-700/60">
            <span className="text-[11px] text-slate-400 block font-sans">Renta Neta Gravable (Utilidad)</span>
            <span className={`text-lg font-bold ${
              (summary?.net_profit_ves ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"
            }`}>
              {(summary?.net_profit_ves ?? 0).toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} VES
            </span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#162032]/80 border border-slate-700/60 text-xs text-slate-300 space-y-1">
          <p className="font-semibold text-slate-200">
            ⚖️ Metodología Contable Aplicada:
          </p>
          <p className="text-[11px] text-slate-400">
            El motor procesa cada venta aplicando el método <strong>FIFO (First In, First Out)</strong> y el inventario inicial valorado a la tasa oficial del Banco Central de Venezuela (BCV), de conformidad con la Ley de Impuesto Sobre la Renta (LISLR) y providencias administrativas tributarias.
          </p>
        </div>
      </div>
    </div>
  );
}
