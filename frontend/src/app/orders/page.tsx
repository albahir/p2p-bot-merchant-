"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import {
  FiscalSummary,
  OrderItem,
  OrderListResponse,
  OrderSortBy,
  User,
  VENEZUELAN_BANK_CATALOG,
  downloadOrdersExport,
  getCachedApiResponse,
  getCurrentUser,
  getFiscalSummary,
  getOrders,
  syncOrders,
  uploadOrdersFile,
} from "@/lib/api";

type CostMethod = "FIFO" | "AVERAGE";
type TradeFilter = "ALL" | "BUY" | "SELL";
type StatusFilter = "COMPLETED" | "ALL" | "CANCELLED";
type DatePreset = "ALL" | "TODAY" | "7D" | "30D" | "MONTH";

const SYNC_WINDOWS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "180d", days: 180 },
];

const LIVE_POLL_INTERVAL_MS = 30_000;

function formatVetDate(date: Date): string {
  try {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Caracas",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(date);
  } catch {
    const vet = new Date(date.getTime() - 4 * 60 * 60 * 1000);
    return vet.toISOString().slice(0, 10);
  }
}

function formatVetTime(date: Date): string {
  try {
    return new Intl.DateTimeFormat("es-VE", {
      timeZone: "America/Caracas",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(date);
  } catch {
    return date.toTimeString().slice(0, 8);
  }
}

function getVetDatePresetRange(preset: DatePreset): { from: string; to: string } {
  if (preset === "ALL") return { from: "", to: "" };
  const now = new Date();
  const todayStr = formatVetDate(now);
  if (preset === "TODAY") {
    return { from: todayStr, to: todayStr };
  }
  if (preset === "7D") {
    const start = new Date(now.getTime() - 6 * 24 * 60 * 60 * 1000);
    return { from: formatVetDate(start), to: todayStr };
  }
  if (preset === "30D") {
    const start = new Date(now.getTime() - 29 * 24 * 60 * 60 * 1000);
    return { from: formatVetDate(start), to: todayStr };
  }
  // MONTH: desde el día 1 del mes actual en hora VET (UTC-4)
  return { from: `${todayStr.slice(0, 7)}-01`, to: todayStr };
}

export default function OrdersPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const syncInFlightRef = useRef<boolean>(false);
  const initialUser = typeof window !== "undefined" ? getCurrentUser() : null;
  const initialOrdersRes =
    typeof window !== "undefined"
      ? getCachedApiResponse<OrderListResponse>("/api/orders?page=1&page_size=20&order_status=COMPLETED")
      : null;
  const initialSummary =
    typeof window !== "undefined"
      ? getCachedApiResponse<FiscalSummary>("/api/fiscal/summary?cost_method=FIFO")
      : null;

  const [user, setUser] = useState<User | null>(initialUser);
  const [orders, setOrders] = useState<OrderItem[]>(initialOrdersRes?.items || []);
  const [totalOrders, setTotalOrders] = useState<number>(initialOrdersRes?.total || 0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 20;

  const [tradeFilter, setTradeFilter] = useState<TradeFilter>("ALL");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("COMPLETED");
  const [bankFilter, setBankFilter] = useState<string>("");
  const [datePreset, setDatePreset] = useState<DatePreset>("ALL");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [minAmount, setMinAmount] = useState<string>("");
  const [maxAmount, setMaxAmount] = useState<string>("");
  const [sortBy, setSortBy] = useState<OrderSortBy>("date_desc");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [costMethod, setCostMethod] = useState<CostMethod>("FIFO");
  const [syncDays, setSyncDays] = useState<number>(30);

  const [fiscalSummary, setFiscalSummary] = useState<FiscalSummary | null>(initialSummary);
  const [loading, setLoading] = useState<boolean>(!initialOrdersRes);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [liveMode, setLiveMode] = useState<boolean>(false);
  const [liveSyncing, setLiveSyncing] = useState<boolean>(false);
  const [lastLiveSyncAt, setLastLiveSyncAt] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const hasActiveFilters = useMemo(() => {
    return Boolean(
      tradeFilter !== "ALL" ||
        statusFilter !== "COMPLETED" ||
        bankFilter ||
        dateFrom ||
        dateTo ||
        minAmount.trim() ||
        maxAmount.trim() ||
        sortBy !== "date_desc" ||
        searchQuery.trim()
    );
  }, [
    tradeFilter,
    statusFilter,
    bankFilter,
    dateFrom,
    dateTo,
    minAmount,
    maxAmount,
    sortBy,
    searchQuery,
  ]);

  function handleResetFilters() {
    setPage(1);
    setTradeFilter("ALL");
    setStatusFilter("COMPLETED");
    setBankFilter("");
    setDatePreset("ALL");
    setDateFrom("");
    setDateTo("");
    setMinAmount("");
    setMaxAmount("");
    setSortBy("date_desc");
    setSearchQuery("");
  }

  function handleApplyDatePreset(preset: DatePreset) {
    const range = getVetDatePresetRange(preset);
    setPage(1);
    setDatePreset(preset);
    setDateFrom(range.from);
    setDateTo(range.to);
  }

  const loadOrdersAndSummary = useCallback(
    async (opts?: { silent?: boolean; fresh?: boolean }) => {
      const current = getCurrentUser();
      setUser(current);
      if (!current || current.role === "INVITADO") {
        setLoading(false);
        return;
      }

      if (!opts?.silent) setLoading(true);
      try {
        const apiMethod = costMethod === "AVERAGE" ? "AVG" : "FIFO";
        const parsedMin = minAmount.trim() !== "" ? Number(minAmount) : undefined;
        const parsedMax = maxAmount.trim() !== "" ? Number(maxAmount) : undefined;
        const [ordersRes, summaryRes] = await Promise.all([
          getOrders({
            page,
            page_size: pageSize,
            trade_type: tradeFilter === "ALL" ? undefined : tradeFilter,
            order_status: statusFilter === "ALL" ? undefined : statusFilter,
            payment_method: bankFilter || undefined,
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
            min_amount:
              parsedMin !== undefined && Number.isFinite(parsedMin) && parsedMin >= 0
                ? parsedMin
                : undefined,
            max_amount:
              parsedMax !== undefined && Number.isFinite(parsedMax) && parsedMax >= 0
                ? parsedMax
                : undefined,
            sort_by: sortBy,
            search: searchQuery.trim() || undefined,
            fresh: opts?.fresh,
          }),
          getFiscalSummary(undefined, undefined, undefined, apiMethod).catch(() => null),
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
        if (!opts?.silent) setLoading(false);
      }
    },
    [
      page,
      tradeFilter,
      statusFilter,
      bankFilter,
      dateFrom,
      dateTo,
      minAmount,
      maxAmount,
      sortBy,
      searchQuery,
      costMethod,
    ]
  );

  useEffect(() => {
    loadOrdersAndSummary();
  }, [loadOrdersAndSummary]);

  // Modo En Vivo (30s): sondeo ligero de las últimas 24h (solo 2 peticiones API, peso 2/5000).
  // Se pausa automáticamente en pestañas ocultas y se detiene Fail-Closed si falla Binance.
  useEffect(() => {
    if (!liveMode || !user || user.role === "INVITADO") return;

    let cancelled = false;

    const runLiveCheck = async () => {
      if (cancelled) return;
      if (typeof document !== "undefined" && document.visibilityState !== "visible") {
        return;
      }
      if (syncInFlightRef.current) return;

      syncInFlightRef.current = true;
      setLiveSyncing(true);
      try {
        const res = await syncOrders(1, undefined, undefined, undefined, null, true);
        if (cancelled) return;
        setLastLiveSyncAt(formatVetTime(new Date()));
        const inserted = res.orders_inserted || 0;
        const updated = res.orders_updated || 0;
        if (inserted > 0 || updated > 0) {
          await loadOrdersAndSummary({ silent: true, fresh: true });
          if (!cancelled) {
            setFeedback({
              type: "success",
              text: `En vivo: ${inserted} orden(es) nueva(s)${
                updated > 0 ? ` y ${updated} actualizada(s)` : ""
              } cargadas desde Binance P2P.`,
            });
          }
        }
      } catch (err: any) {
        if (!cancelled) {
          setLiveMode(false);
          setFeedback({
            type: "error",
            text: `Modo En Vivo detenido (Fail-Closed): ${
              err.message || "verifica tus API Keys de Binance en Configuración."
            }`,
          });
        }
      } finally {
        syncInFlightRef.current = false;
        if (!cancelled) setLiveSyncing(false);
      }
    };

    void runLiveCheck();
    const timer = window.setInterval(() => {
      void runLiveCheck();
    }, LIVE_POLL_INTERVAL_MS);

    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void runLiveCheck();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [liveMode, user, loadOrdersAndSummary]);

  async function handleSyncBinance() {
    if (syncInFlightRef.current) return;
    setFeedback(null);
    syncInFlightRef.current = true;
    setIsSyncing(true);
    try {
      const res = await syncOrders(
        syncDays,
        tradeFilter === "ALL" ? undefined : tradeFilter,
        undefined,
        undefined,
        null,
        true
      );
      setFeedback({
        type: "success",
        text:
          res?.message ||
          `Sincronización oficial Binance (${syncDays} días) completada.`,
      });
      await loadOrdersAndSummary({ fresh: true });
    } catch (err: any) {
      setFeedback({
        type: "error",
        text:
          err.message ||
          "Fallo en ingesta Binance P2P. Verifica tus API Keys en Configuración.",
      });
    } finally {
      syncInFlightRef.current = false;
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
    const completed = orders.filter((o) => o.order_status === "COMPLETED");
    if (!completed.length) return 0;
    const totalCrypto = completed.reduce((acc, o) => acc + (o.crypto_amount || 0), 0);
    const totalFiat = completed.reduce((acc, o) => acc + (o.fiat_amount || 0), 0);
    return totalCrypto > 0 ? totalFiat / totalCrypto : 0;
  }, [orders]);

  const totalPages = Math.max(1, Math.ceil(totalOrders / pageSize));

  if (!user || user.role === "INVITADO") {
    return (
      <AppShell
        title="Ganancias Reales y Órdenes"
        badge="ACCESO RESTRINGIDO"
        subtitle="Módulo protegido por control de roles para operadores Comerciante y Administrador."
      >
        <div className="max-w-lg mx-auto my-12 p-6 rounded-2xl bg-surface-container-low border border-[#1e2430] text-center space-y-4">
          <span className="material-symbols-outlined text-[36px] text-primary">
            lock
          </span>
          <h2 className="text-base font-bold text-white">
            Se requiere sesión activa con rol Comerciante o Administrador
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
      title="Órdenes y ganancias"
      badge={costMethod === "AVERAGE" ? "PROMEDIO" : "PEPS"}
      subtitle="Historial de compras, ventas y utilidad neta."
      actions={
        /* Grupo Único de Exportación Autenticada (Bearer sin fuga de JWT en URL) */
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={async () => {
              try {
                await downloadOrdersExport("csv_semicolon", {
                  trade_type: tradeFilter,
                  order_status: statusFilter,
                  payment_method: bankFilter,
                  date_from: dateFrom,
                  date_to: dateTo,
                  search: searchQuery,
                });
              } catch (err: any) {
                setFeedback({
                  type: "error",
                  text: err.message || "No se pudo exportar el CSV de órdenes.",
                });
              }
            }}
            className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-secondary/50 text-xs font-mono text-slate-200 flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <span className="material-symbols-outlined text-[16px] text-secondary">
              download
            </span>
            <span>CSV</span>
          </button>
          <button
            type="button"
            onClick={async () => {
              try {
                await downloadOrdersExport("xlsx", {
                  trade_type: tradeFilter,
                  order_status: statusFilter,
                  payment_method: bankFilter,
                  date_from: dateFrom,
                  date_to: dateTo,
                  search: searchQuery,
                });
              } catch (err: any) {
                setFeedback({
                  type: "error",
                  text: err.message || "No se pudo exportar el Excel de órdenes.",
                });
              }
            }}
            className="px-3 py-1.5 rounded-lg bg-tertiary/15 border border-tertiary/35 hover:bg-tertiary/25 text-xs font-mono font-semibold text-tertiary flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <span className="material-symbols-outlined text-[16px]">table_view</span>
            <span>Excel (.xlsx)</span>
          </button>
        </div>
      }
    >
      <div className="space-y-5">
        {feedback && (
          <div
            role="alert"
            aria-live="polite"
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
              aria-label="Cerrar notificación"
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
                Sincronizando historial oficial Binance P2P ({syncDays} días)...
              </span>
              <span className="text-slate-400">Monitoreando cuota de peso API</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
              <div className="h-full w-2/3 bg-primary-container animate-pulse rounded-full" />
            </div>
          </div>
        )}

        {/* 4 KPIs (2 por fila en móvil) */}
        <section className="grid grid-cols-2 xl:grid-cols-4 gap-2.5 sm:gap-3">
          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span className="truncate">Ganancia neta ({costMethod === "AVERAGE" ? "Promedio" : "PEPS"})</span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-tertiary shrink-0">
                trending_up
              </span>
            </div>
            <div
              className={`mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold tabular-nums truncate ${
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
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 tabular-nums truncate">
              ≈ ${(fiscalSummary?.net_profit_usd ?? 0).toFixed(2)} USD BCV
            </div>
          </div>

          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span className="truncate">Volumen</span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-secondary shrink-0">
                swap_horiz
              </span>
            </div>
            <div className="mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold text-white tabular-nums truncate">
              {(fiscalSummary?.volume_operated ?? 0).toLocaleString("es-VE", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{" "}
              USDT
            </div>
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 tabular-nums truncate">
              Bs.{" "}
              {(fiscalSummary?.volume_operated_ves ?? 0).toLocaleString("es-VE", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{" "}
              • {fiscalSummary?.orders_count ?? 0} completadas
            </div>
          </div>

          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span className="truncate">Comisiones</span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-primary shrink-0">
                percent
              </span>
            </div>
            <div className="mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold text-primary tabular-nums truncate">
              {(fiscalSummary?.total_fees ?? 0).toLocaleString("es-VE", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 4,
              })}{" "}
              USDT
            </div>
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 tabular-nums truncate">
              Bs.{" "}
              {(fiscalSummary?.total_fees_ves ?? 0).toLocaleString("es-VE", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </div>
          </div>

          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span className="truncate">Precio promedio</span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-slate-300 shrink-0">
                analytics
              </span>
            </div>
            <div className="mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold text-white tabular-nums truncate">
              {avgUnitPrice > 0 ? `Bs. ${avgUnitPrice.toFixed(2)}` : "Bs. --"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              BCV: Bs. {(fiscalSummary?.bcv_rate ?? 0).toFixed(2)}
            </div>
          </div>
        </section>

        {/* Barra de sincronización e importación */}
        <section className="p-3.5 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-2.5">
          <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full xl:w-auto">
              <div className="flex items-center justify-between sm:justify-start gap-2 w-full sm:w-auto">
                <span className="text-xs font-semibold text-white shrink-0">
                  API Binance (máx. 6 meses):
                </span>
                <div className="flex-1 sm:flex-initial grid grid-cols-4 sm:flex items-center gap-1 bg-surface-container p-1 rounded-lg border border-[#1e2430]">
                  {SYNC_WINDOWS.map((w) => (
                    <button
                      key={w.days}
                      type="button"
                      onClick={() => setSyncDays(w.days)}
                      className={`px-2 py-1 sm:py-0.5 rounded text-[11px] font-mono text-center transition-colors ${
                        syncDays === w.days
                          ? "bg-primary-container text-on-primary font-bold"
                          : "text-slate-400 hover:text-white"
                      }`}
                    >
                      {w.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center gap-2 w-full sm:w-auto">
                <button
                  type="button"
                  onClick={handleSyncBinance}
                  disabled={isSyncing}
                  className="px-3 py-2 sm:py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-50 transition-all flex items-center justify-center gap-1.5 whitespace-nowrap cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[16px]">cloud_sync</span>
                  <span>{isSyncing ? "Sincronizando..." : `Sincronizar (${syncDays}d)`}</span>
                </button>

                {/* Modo En Vivo (30s) */}
                <button
                  type="button"
                  aria-pressed={liveMode}
                  onClick={() => {
                    setFeedback(null);
                    setLiveMode((prev) => !prev);
                  }}
                  className={`px-3 py-2 sm:py-1.5 rounded-lg border text-xs font-mono font-semibold flex items-center justify-center gap-1.5 whitespace-nowrap transition-colors cursor-pointer ${
                    liveMode
                      ? "bg-tertiary/15 border-tertiary/50 text-tertiary hover:bg-tertiary/25"
                      : "bg-surface-container border-[#1e2430] text-slate-300 hover:border-tertiary/40 hover:text-white"
                  }`}
                  title="Activa la consulta ligera cada 30 segundos (últimas 24h) para cargar nuevas órdenes completadas en vivo"
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      liveMode
                        ? liveSyncing
                          ? "bg-tertiary animate-ping"
                          : "bg-tertiary animate-pulse"
                        : "bg-slate-500"
                    }`}
                  />
                  <span>{liveMode ? "En vivo (30s)" : "En vivo: OFF"}</span>
                </button>

                {/* Carga Manual de Histórico CSV / XLSX (para 365d+ o >6 meses) */}
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
                  className="col-span-2 sm:col-span-1 px-3 py-2 sm:py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-primary-container/50 text-xs font-mono text-slate-200 flex items-center justify-center gap-1.5 whitespace-nowrap transition-colors cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[16px] text-primary">
                    upload_file
                  </span>
                  <span>
                    <span className="sm:hidden">{isUploading ? "Importando..." : "Importar (.csv/.xlsx)"}</span>
                    <span className="hidden sm:inline">{isUploading ? "Importando..." : "Importar (.csv / .xlsx)"}</span>
                  </span>
                </button>
              </div>
            </div>

            {liveMode && (
              <div className="flex items-center gap-2 text-[11px] font-mono text-tertiary bg-tertiary/10 border border-tertiary/25 rounded-lg px-2.5 py-1.5 shrink-0">
                <span className="material-symbols-outlined text-[15px]">
                  {liveSyncing ? "sync" : "sensors"}
                </span>
                <span>
                  {liveSyncing
                    ? "Consultando Binance..."
                    : lastLiveSyncAt
                    ? `Última revisión: ${lastLiveSyncAt} VET`
                    : "Escuchando nuevas órdenes..."}
                </span>
              </div>
            )}
          </div>

          <p className="text-[11px] text-slate-400 leading-relaxed">
            La API oficial de Binance entrega hasta <strong className="text-slate-200">180 días (6 meses)</strong>, omite automáticamente órdenes canceladas y auto-concilia tus comprobantes. Activa <strong className="text-tertiary">En vivo (30s)</strong> para cargar automáticamente operaciones recién completadas (consulta ligera de 24h con pausa automática en segundo plano y parada Fail-Closed). Para <strong className="text-slate-200">365 días+</strong> usa <strong className="text-slate-200">Importar (.csv / .xlsx)</strong>.
          </p>
        </section>

        {/* Controles: Búsqueda + Filtro COMPRA/VENTA + Filtro Estado + Método Costo + Filtros Avanzados */}
        <section className="p-3.5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-3">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-2.5 sm:gap-3">
            <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-2 w-full lg:w-auto">
              {/* Filtro Tipo Operación */}
              <div className="p-0.5 rounded-lg bg-surface-container border border-[#1e2430] grid grid-cols-3 sm:flex items-center text-xs font-mono w-full sm:w-auto">
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
                    className={`px-2.5 py-1 rounded-md text-center transition-colors ${
                      tradeFilter === tab.id
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Filtro Estado de Orden (por defecto solo COMPLETADAS para mantener limpia la conciliación) */}
              <div className="p-0.5 rounded-lg bg-surface-container border border-[#1e2430] grid grid-cols-3 sm:flex items-center text-xs font-mono w-full sm:w-auto">
                {(
                  [
                    { id: "COMPLETED", label: "COMPLETADAS" },
                    { id: "ALL", label: "TODOS" },
                    { id: "CANCELLED", label: "CANCELADAS" },
                  ] as const
                ).map((st) => (
                  <button
                    key={st.id}
                    type="button"
                    onClick={() => {
                      setPage(1);
                      setStatusFilter(st.id);
                    }}
                    className={`px-2.5 py-1 rounded-md text-center transition-colors ${
                      statusFilter === st.id
                        ? st.id === "CANCELLED"
                          ? "bg-error/25 text-red-200 font-bold"
                          : "bg-tertiary/20 text-tertiary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {st.label}
                  </button>
                ))}
              </div>

              {/* Selector Método Fiscal PEPS / Costo Promedio */}
              <div className="p-0.5 rounded-lg bg-surface-container border border-[#1e2430] grid grid-cols-2 sm:flex items-center text-xs font-mono w-full sm:w-auto">
                <button
                  type="button"
                  onClick={() => setCostMethod("FIFO")}
                  className={`px-2.5 py-1 rounded-md text-center transition-colors ${
                    costMethod === "FIFO"
                      ? "bg-secondary text-on-secondary font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  PEPS
                </button>
                <button
                  type="button"
                  onClick={() => setCostMethod("AVERAGE")}
                  className={`px-2.5 py-1 rounded-md text-center transition-colors ${
                    costMethod === "AVERAGE"
                      ? "bg-secondary text-on-secondary font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Promedio
                </button>
              </div>
            </div>

            {/* Buscador por Número de Orden, Contraparte o Banco */}
            <div className="relative w-full lg:w-72">
              <span className="material-symbols-outlined text-[16px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2">
                search
              </span>
              <input
                type="search"
                enterKeyHint="search"
                aria-label="Buscar por número de orden, contraparte o banco"
                value={searchQuery}
                onChange={(e) => {
                  setPage(1);
                  setSearchQuery(e.target.value);
                }}
                placeholder="Buscar Nº orden, contraparte o banco..."
                className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white font-mono placeholder:text-slate-500"
              />
            </div>
          </div>

          {/* Fila de Filtros Avanzados: Banco, Fechas (VET), Rango USDT y Ordenamiento */}
          <div className="pt-2.5 border-t border-[#1e2430]/80 flex flex-wrap items-end gap-2">
            {/* Banco / Método de Pago */}
            <label className="flex flex-col gap-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 min-w-[155px] flex-1 sm:flex-initial">
              <span>Banco / Método</span>
              <select
                aria-label="Filtrar por banco o método de pago"
                value={bankFilter}
                onChange={(e) => {
                  setPage(1);
                  setBankFilter(e.target.value);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white font-mono"
              >
                <option value="">Todos los bancos</option>
                {VENEZUELAN_BANK_CATALOG.map((bank) => (
                  <option key={bank} value={bank}>
                    {bank}
                  </option>
                ))}
              </select>
            </label>

            {/* Atajos rápidos de Fecha (VET UTC-4) */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                Período (VET)
              </span>
              <div className="p-0.5 rounded-lg bg-surface-container border border-[#1e2430] flex items-center text-[11px] font-mono">
                {(
                  [
                    { id: "ALL", label: "Todo" },
                    { id: "TODAY", label: "Hoy" },
                    { id: "7D", label: "7d" },
                    { id: "30D", label: "30d" },
                    { id: "MONTH", label: "Mes" },
                  ] as const
                ).map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => handleApplyDatePreset(p.id)}
                    className={`px-2 py-1 rounded transition-colors ${
                      datePreset === p.id
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Rango de Fechas Exacto (VET) */}
            <label className="flex flex-col gap-1 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Desde</span>
              <input
                type="date"
                aria-label="Fecha desde (hora Venezuela)"
                value={dateFrom}
                onChange={(e) => {
                  setPage(1);
                  setDatePreset("ALL");
                  setDateFrom(e.target.value);
                }}
                className="px-2 py-1 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white font-mono"
              />
            </label>

            <label className="flex flex-col gap-1 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Hasta</span>
              <input
                type="date"
                aria-label="Fecha hasta (hora Venezuela)"
                value={dateTo}
                onChange={(e) => {
                  setPage(1);
                  setDatePreset("ALL");
                  setDateTo(e.target.value);
                }}
                className="px-2 py-1 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white font-mono"
              />
            </label>

            {/* Rango Monto USDT */}
            <label className="flex flex-col gap-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 w-24">
              <span>Mín USDT</span>
              <input
                type="number"
                min="0"
                step="any"
                inputMode="decimal"
                aria-label="Monto mínimo en USDT"
                value={minAmount}
                onChange={(e) => {
                  setPage(1);
                  setMinAmount(e.target.value);
                }}
                placeholder="0"
                className="px-2 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white font-mono tabular-nums placeholder:text-slate-600"
              />
            </label>

            <label className="flex flex-col gap-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 w-24">
              <span>Máx USDT</span>
              <input
                type="number"
                min="0"
                step="any"
                inputMode="decimal"
                aria-label="Monto máximo en USDT"
                value={maxAmount}
                onChange={(e) => {
                  setPage(1);
                  setMaxAmount(e.target.value);
                }}
                placeholder="∞"
                className="px-2 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white font-mono tabular-nums placeholder:text-slate-600"
              />
            </label>

            {/* Ordenamiento */}
            <label className="flex flex-col gap-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 min-w-[145px]">
              <span>Ordenar por</span>
              <select
                aria-label="Ordenar listado de órdenes"
                value={sortBy}
                onChange={(e) => {
                  setPage(1);
                  setSortBy(e.target.value as OrderSortBy);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white font-mono"
              >
                <option value="date_desc">Más recientes</option>
                <option value="date_asc">Más antiguas</option>
                <option value="amount_desc">Mayor USDT</option>
                <option value="amount_asc">Menor USDT</option>
                <option value="price_desc">Mayor tasa Bs.</option>
                <option value="price_asc">Menor tasa Bs.</option>
              </select>
            </label>

            {hasActiveFilters && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="px-2.5 py-1.5 rounded-lg bg-surface-container border border-[#2a3446] hover:border-error/40 hover:text-red-200 text-xs font-mono text-slate-300 flex items-center gap-1 transition-colors cursor-pointer"
              >
                <span className="material-symbols-outlined text-[15px]">filter_alt_off</span>
                <span>Limpiar</span>
              </button>
            )}
          </div>
        </section>

        {statusFilter !== "COMPLETED" && (
          <div className="px-3.5 py-2 rounded-lg bg-surface-container border border-[#1e2430] text-[11px] text-slate-400 flex items-center gap-2">
            <span className="material-symbols-outlined text-[15px] text-secondary shrink-0">info</span>
            <span>
              Las órdenes <strong className="text-slate-200">canceladas</strong> son solo informativas: quedan excluidas automáticamente de tu ganancia neta, volumen fiscal, Libro Diario y conciliación bancaria.
            </span>
          </div>
        )}

        {/* Lista Compacta en Móvil + Tabla Densa en Escritorio */}
        <section className="rounded-xl bg-surface-container-low border border-[#1e2430] overflow-hidden defer-render">
          <div className="md:hidden divide-y divide-[#1e2430]/70 text-xs">
            {loading ? (
              <div className="py-10 text-center text-slate-400 font-mono">
                Cargando libro de órdenes P2P...
              </div>
            ) : orders.length === 0 ? (
              <div className="py-10 px-4 text-center text-slate-400 font-mono">
                No se encontraron órdenes. Usa &ldquo;Sincronizar&rdquo; o importa tu CSV/Excel de Binance.
              </div>
            ) : (
              orders.map((o) => {
                const isBuy = o.trade_type === "BUY";
                const isCancelled =
                  o.order_status === "CANCELLED" ||
                  o.order_status === "CANCELLED_BY_SYSTEM";
                const statusTxt =
                  o.order_status === "COMPLETED"
                    ? "COMPLETADA"
                    : isCancelled
                    ? "CANCELADA"
                    : o.order_status === "PENDING"
                    ? "PENDIENTE"
                    : o.order_status;
                return (
                  <div key={`mob-${o.order_number}`} className="p-3.5 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-mono font-bold text-white">
                            #{o.order_number.slice(-8)}
                          </span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold uppercase ${
                              isBuy
                                ? "bg-tertiary/15 text-tertiary border border-tertiary/30"
                                : "bg-primary-container/15 text-primary border border-primary-container/30"
                            }`}
                          >
                            {isBuy ? "COMPRA" : "VENTA"}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-300 truncate mt-0.5">
                          {o.counterparty_name || "Contraparte P2P"}
                        </div>
                        {o.payment_method && (
                          <span className="mt-1 inline-block px-1.5 py-0.5 rounded bg-surface-container-high border border-[#242c3b] text-[9px] font-mono text-secondary">
                            {o.payment_method}
                          </span>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <span
                          className={`px-2 py-0.5 rounded text-[9px] font-mono ${
                            isCancelled
                              ? "bg-error/15 text-red-300 border border-error/30"
                              : "bg-surface-container-high text-slate-300"
                          }`}
                        >
                          {statusTxt}
                        </span>
                        <div className="text-[10px] font-mono text-slate-500 mt-1">
                          {o.created_at?.slice(0, 16).replace("T", " ")}
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2 pt-1 border-t border-[#1e2430]/50 font-mono tabular-nums text-[11px]">
                      <div>
                        <div className="text-[9px] text-slate-500 uppercase">Cantidad</div>
                        <div className="text-white font-semibold">
                          {o.crypto_amount.toFixed(2)} {o.asset}
                        </div>
                        <div className="text-[10px] text-slate-400">
                          @ Bs. {o.unit_price.toFixed(2)}
                        </div>
                      </div>
                      <div>
                        <div className="text-[9px] text-slate-500 uppercase">Total VES</div>
                        <div className="text-white font-semibold">
                          Bs.{" "}
                          {o.fiat_amount.toLocaleString("es-VE", {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </div>
                        <div className="text-[10px] text-secondary">
                          BCV {o.bcv_rate > 0 ? o.bcv_rate.toFixed(2) : "--"}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-[9px] text-slate-500 uppercase">Comisión</div>
                        <div className="text-slate-300">
                          {o.fee_crypto > 0
                            ? `${o.fee_crypto.toFixed(3)} ${o.asset}`
                            : `Bs. ${o.fee_fiat.toFixed(2)}`}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="hidden md:block overflow-x-auto overscroll-x-contain">
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 z-10 bg-surface-container">
                <tr className="border-b border-[#1e2430] bg-surface-container/95 text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  <th scope="col" className="py-3 px-4">Fecha / Nº Orden</th>
                  <th scope="col" className="py-3 px-4">Tipo</th>
                  <th scope="col" className="py-3 px-4">Contraparte / Banco</th>
                  <th scope="col" className="py-3 px-4 text-right">Cantidad USDT</th>
                  <th scope="col" className="py-3 px-4 text-right">Precio Unit.</th>
                  <th scope="col" className="py-3 px-4 text-right">Total VES</th>
                  <th scope="col" className="py-3 px-4 text-right">BCV Hist.</th>
                  <th scope="col" className="py-3 px-4 text-right">Comisión</th>
                  <th scope="col" className="py-3 px-4 text-right">Estado</th>
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
                        <td className="py-3 px-4 max-w-[180px]">
                          <div className="text-slate-300 truncate">
                            {o.counterparty_name || "Contraparte P2P"}
                          </div>
                          {o.payment_method && (
                            <span className="mt-0.5 inline-block px-1.5 py-0.2 rounded bg-surface-container-high border border-[#242c3b] text-[10px] font-mono text-secondary truncate max-w-[165px]">
                              {o.payment_method}
                            </span>
                          )}
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
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                              o.order_status === "CANCELLED" ||
                              o.order_status === "CANCELLED_BY_SYSTEM"
                                ? "bg-error/15 text-red-300 border border-error/30"
                                : "bg-surface-container-high text-slate-300"
                            }`}
                          >
                            {o.order_status === "COMPLETED"
                              ? "COMPLETADA"
                              : o.order_status === "CANCELLED" ||
                                o.order_status === "CANCELLED_BY_SYSTEM"
                              ? "CANCELADA"
                              : o.order_status === "PENDING"
                              ? "PENDIENTE"
                              : o.order_status}
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
