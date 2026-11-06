"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import {
  FiscalSummary,
  OrderItem,
  User,
  getCurrentUser,
  getExportOrdersUrl,
  getFiscalSummary,
  getOrders,
  syncOrders,
  uploadOrdersFile,
} from "@/lib/api";

type CostMethod = "FIFO" | "AVERAGE";
type TradeFilter = "ALL" | "BUY" | "SELL";

const SYNC_WINDOWS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "180d", days: 180 },
  { label: "365d", days: 365 },
];

export default function OrdersPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [user, setUser] = useState<User | null>(null);
  const [orders, setOrders] = useState<OrderItem[]>([]);
  const [totalOrders, setTotalOrders] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 20;

  const [tradeFilter, setTradeFilter] = useState<TradeFilter>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [costMethod, setCostMethod] = useState<CostMethod>("FIFO");
  const [syncDays, setSyncDays] = useState<number>(30);

  const [fiscalSummary, setFiscalSummary] = useState<FiscalSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const loadOrdersAndSummary = useCallback(async () => {
    const current = getCurrentUser();
    setUser(current);
    if (!current || current.role === "INVITADO") {
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const [ordersRes, summaryRes] = await Promise.all([
        getOrders({
          page,
          page_size: pageSize,
          trade_type: tradeFilter === "ALL" ? undefined : tradeFilter,
          search: searchQuery.trim() || undefined,
        }),
        getFiscalSummary().catch(() => null),
      ]);
      setOrders(ordersRes.items || []);
      setTotalOrders(ordersRes.total || 0);
      if (summaryRes) setFiscalSummary(summaryRes);
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error consultando historial de órdenes P2P.",
      });
    } finally {
      setLoading(false);
    }
  }, [page, tradeFilter, searchQuery]);

  useEffect(() => {
    loadOrdersAndSummary();
  }, [loadOrdersAndSummary]);

  async function handleSyncBinance() {
    setFeedback(null);
    setIsSyncing(true);
    try {
      const res = await syncOrders(
        syncDays,
        tradeFilter === "ALL" ? undefined : tradeFilter
      );
      setFeedback({
        type: "success",
        text:
          res?.message ||
          `Sincronización oficial Binance (${syncDays} días) completada.`,
      });
      await loadOrdersAndSummary();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text:
          err.message ||
          "Fallo en ingesta Binance P2P. Verifica tus API Keys en Configuración.",
      });
    } finally {
      setIsSyncing(false);
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFeedback(null);
    setIsUploading(true);
    try {
      const res = await uploadOrdersFile(file);
      setFeedback({
        type: "success",
        text:
          res?.message ||
          `Archivo "${file.name}" importado exitosamente al motor fiscal.`,
      });
      await loadOrdersAndSummary();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error al importar archivo CSV/Excel de Binance.",
      });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const avgUnitPrice = useMemo(() => {
    if (!orders.length) return 0;
    const totalCrypto = orders.reduce((acc, o) => acc + (o.crypto_amount || 0), 0);
    const totalFiat = orders.reduce((acc, o) => acc + (o.fiat_amount || 0), 0);
    return totalCrypto > 0 ? totalFiat / totalCrypto : 0;
  }, [orders]);

  const totalPages = Math.max(1, Math.ceil(totalOrders / pageSize));

  if (!user || user.role === "INVITADO") {
    return (
      <AppShell
        title="Ganancias Reales & Órdenes"
        badge="ACCESO RESTRINGIDO"
        subtitle="Módulo protegido por control RBAC para operadores TRADER y ADMIN."
      >
        <div className="max-w-lg mx-auto my-12 p-6 rounded-2xl bg-surface-container-low border border-[#1e2430] text-center space-y-4">
          <span className="material-symbols-outlined text-[36px] text-primary">
            lock
          </span>
          <h2 className="text-base font-bold text-white">
            Se requiere sesión activa con rol TRADER o ADMIN
          </h2>
          <p className="text-xs text-slate-400">
            Inicia sesión con tu cuenta autorizada para sincronizar órdenes de Binance P2P y auditar utilidades netas.
          </p>
          <div className="flex justify-center gap-3 pt-2">
            <Link
              href="/login"
              className="px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold"
            >
              Iniciar Sesión
            </Link>
            <Link
              href="/register"
              className="px-4 py-2 rounded-lg bg-surface-container border border-[#1e2430] text-xs text-slate-200"
            >
              Crear Cuenta
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Ganancias Reales & Órdenes"
      badge={`MOTOR ${costMethod}`}
      subtitle="Ingesta histórica oficial Binance C2C, importación manual y cálculo de utilidad neta realizada."
      actions={
        /* Grupo Único de Exportación (sin duplicados) */
        <div className="flex items-center gap-2">
          <a
            href={getExportOrdersUrl("csv_semicolon")}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-secondary/50 text-xs font-mono text-slate-200 flex items-center gap-1.5 transition-colors"
          >
            <span className="material-symbols-outlined text-[16px] text-secondary">
              download
            </span>
            <span>CSV</span>
          </a>
          <a
            href={getExportOrdersUrl("xlsx")}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1.5 rounded-lg bg-tertiary/15 border border-tertiary/35 hover:bg-tertiary/25 text-xs font-mono font-semibold text-tertiary flex items-center gap-1.5 transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">table_view</span>
            <span>Excel (.xlsx)</span>
          </a>
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
                {feedback.type === "success" ? "check_circle" : "error"}
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

        {/* Barra de Progreso Condicional (SOLO visible cuando hay sincronización activa) */}
        {isSyncing && (
          <div className="p-3.5 rounded-xl bg-surface-container border border-primary-container/40 space-y-2">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-primary flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] animate-spin">
                  sync
                </span>
                Sincronizando historial oficial Binance C2C ({syncDays} días)...
              </span>
              <span className="text-slate-400">Monitoreando x-mbx-used-weight</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
              <div className="h-full w-2/3 bg-primary-container animate-pulse rounded-full" />
            </div>
          </div>
        )}

        {/* 4 KPIs Fiscales y Operativos */}
        <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Utilidad Neta ({costMethod})</span>
              <span className="material-symbols-outlined text-[16px] text-tertiary">
                trending_up
              </span>
            </div>
            <div
              className={`mt-2 text-xl font-mono font-bold tabular-nums ${
                (fiscalSummary?.net_profit_ves ?? 0) >= 0
                  ? "text-tertiary"
                  : "text-error"
              }`}
            >
              {fiscalSummary
                ? `Bs. ${fiscalSummary.net_profit_ves.toLocaleString("es-VE", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}`
                : "Bs. 0,00"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              Eq. Fiscal BCV: ${(fiscalSummary?.net_profit_usd ?? 0).toFixed(2)} USD
            </div>
          </div>

          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Volumen Operado</span>
              <span className="material-symbols-outlined text-[16px] text-secondary">
                swap_horiz
              </span>
            </div>
            <div className="mt-2 text-xl font-mono font-bold text-white tabular-nums">
              Bs.{" "}
              {(fiscalSummary?.volume_operated ?? 0).toLocaleString("es-VE", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              {totalOrders} órdenes registradas en BD
            </div>
          </div>

          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Comisiones Acumuladas</span>
              <span className="material-symbols-outlined text-[16px] text-primary">
                percent
              </span>
            </div>
            <div className="mt-2 text-xl font-mono font-bold text-primary tabular-nums">
              Bs.{" "}
              {(fiscalSummary?.total_fees ?? 0).toLocaleString("es-VE", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400">
              Deducidas de base imponible
            </div>
          </div>

          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Precio Ponderado Página</span>
              <span className="material-symbols-outlined text-[16px] text-slate-300">
                analytics
              </span>
            </div>
            <div className="mt-2 text-xl font-mono font-bold text-white tabular-nums">
              {avgUnitPrice > 0 ? `Bs. ${avgUnitPrice.toFixed(2)}` : "Bs. --"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              BCV Período: Bs. {(fiscalSummary?.bcv_rate ?? 0).toFixed(2)}
            </div>
          </div>
        </section>

        {/* Barra de Ingesta Binance API + Carga de Archivo CSV/Excel */}
        <section className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430] flex flex-col xl:flex-row xl:items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-white mr-1">
              Ingesta API Binance:
            </span>
            <div className="flex items-center gap-1 bg-surface-container p-1 rounded-lg border border-[#1e2430]">
              {SYNC_WINDOWS.map((w) => (
                <button
                  key={w.days}
                  type="button"
                  onClick={() => setSyncDays(w.days)}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                    syncDays === w.days
                      ? "bg-primary-container text-on-primary font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {w.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={handleSyncBinance}
              disabled={isSyncing}
              className="px-3.5 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-50 transition-all flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-[16px]">cloud_sync</span>
              <span>{isSyncing ? "Sincronizando..." : `Sincronizar (${syncDays}d)`}</span>
            </button>
          </div>

          {/* Carga Manual de Histórico CSV / XLSX */}
          <div className="flex items-center gap-2.5 flex-wrap">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="px-3.5 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-primary-container/50 text-xs font-mono text-slate-200 flex items-center gap-1.5 transition-colors"
            >
              <span className="material-symbols-outlined text-[16px] text-primary">
                upload_file
              </span>
              <span>
                {isUploading ? "Importando archivo..." : "Importar Histórico (.csv / .xlsx)"}
              </span>
            </button>
          </div>
        </section>

        {/* Controles Restaurados: Búsqueda + Filtro COMPRA/VENTA + Método Costo FIFO/Promedio */}
        <section className="p-3.5 rounded-xl bg-surface-container-low border border-[#1e2430] flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Filtro Tipo Operación */}
            <div className="p-0.5 rounded-lg bg-surface-container border border-[#1e2430] flex items-center text-xs font-mono">
              {(
                [
                  { id: "ALL", label: "TODAS" },
                  { id: "BUY", label: "COMPRAS" },
                  { id: "SELL", label: "VENTAS" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => {
                    setPage(1);
                    setTradeFilter(tab.id);
                  }}
                  className={`px-2.5 py-1 rounded-md transition-colors ${
                    tradeFilter === tab.id
                      ? "bg-primary-container text-on-primary font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Selector Método Fiscal FIFO / Costo Promedio */}
            <div className="p-0.5 rounded-lg bg-surface-container border border-[#1e2430] flex items-center text-xs font-mono">
              <button
                type="button"
                onClick={() => setCostMethod("FIFO")}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  costMethod === "FIFO"
                    ? "bg-secondary text-on-secondary font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                FIFO (PEPS)
              </button>
              <button
                type="button"
                onClick={() => setCostMethod("AVERAGE")}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  costMethod === "AVERAGE"
                    ? "bg-secondary text-on-secondary font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Costo Promedio
              </button>
            </div>
          </div>

          {/* Buscador por Número de Orden o Contraparte */}
          <div className="relative w-full lg:w-72">
            <span className="material-symbols-outlined text-[16px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2">
              search
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setPage(1);
                setSearchQuery(e.target.value);
              }}
              placeholder="Buscar Nº orden o contraparte..."
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white font-mono placeholder:text-slate-500"
            />
          </div>
        </section>

        {/* Tabla Densa Paginada de Órdenes */}
        <section className="rounded-xl bg-surface-container-low border border-[#1e2430] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#1e2430] bg-surface-container/60 text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  <th className="py-3 px-4">Fecha / Nº Orden</th>
                  <th className="py-3 px-4">Tipo</th>
                  <th className="py-3 px-4">Contraparte</th>
                  <th className="py-3 px-4 text-right">Cantidad USDT</th>
                  <th className="py-3 px-4 text-right">Precio Unit.</th>
                  <th className="py-3 px-4 text-right">Total VES</th>
                  <th className="py-3 px-4 text-right">BCV Hist.</th>
                  <th className="py-3 px-4 text-right">Comisión</th>
                  <th className="py-3 px-4 text-right">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2430]/70 text-xs">
                {loading ? (
                  <tr>
                    <td colSpan={9} className="py-10 text-center text-slate-400 font-mono">
                      Cargando libro de órdenes P2P...
                    </td>
                  </tr>
                ) : orders.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-10 text-center text-slate-400 font-mono">
                      No se encontraron órdenes. Usa &ldquo;Sincronizar&rdquo; o importa tu CSV/Excel de Binance.
                    </td>
                  </tr>
                ) : (
                  orders.map((o) => {
                    const isBuy = o.trade_type === "BUY";
                    return (
                      <tr
                        key={o.order_number}
                        className="hover:bg-surface-container/70 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono tabular-nums">
                          <div className="text-white font-semibold">
                            #{o.order_number.slice(-8)}
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {o.created_at?.slice(0, 16).replace("T", " ")}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                              isBuy
                                ? "bg-tertiary/15 text-tertiary border border-tertiary/30"
                                : "bg-primary-container/15 text-primary border border-primary-container/30"
                            }`}
                          >
                            {isBuy ? "COMPRA" : "VENTA"}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-300 truncate max-w-[140px]">
                          {o.counterparty_name || "Contraparte P2P"}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-white font-semibold">
                          {o.crypto_amount.toFixed(2)} {o.asset}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-slate-300">
                          Bs. {o.unit_price.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-white font-semibold">
                          Bs.{" "}
                          {o.fiat_amount.toLocaleString("es-VE", {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-secondary">
                          {o.bcv_rate > 0 ? `Bs. ${o.bcv_rate.toFixed(2)}` : "--"}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-slate-400">
                          {o.fee_crypto > 0
                            ? `${o.fee_crypto.toFixed(3)} USDT`
                            : `Bs. ${o.fee_fiat.toFixed(2)}`}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className="px-2 py-0.5 rounded bg-surface-container-high text-[10px] font-mono text-slate-300">
                            {o.order_status}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Paginación */}
          <div className="px-4 py-3 border-t border-[#1e2430] flex items-center justify-between text-xs font-mono text-slate-400">
            <span>
              Página {page} de {totalPages} ({totalOrders} registros)
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-2.5 py-1 rounded bg-surface-container border border-[#1e2430] disabled:opacity-40 hover:text-white"
              >
                Anterior
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-2.5 py-1 rounded bg-surface-container border border-[#1e2430] disabled:opacity-40 hover:text-white"
              >
                Siguiente
              </button>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
