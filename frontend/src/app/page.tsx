"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { BankAmountInput } from "@/components/bank-amount-input";
import {
  ArbitrageMatrix,
  BCVRates,
  FilteredOrderbook,
  RateQuote,
  getArbitrageMatrix,
  getBCVRates,
  getFilteredOrderbook,
} from "@/lib/api";
import { useWebSocket } from "@/lib/useWebSocket";

type ValuationMode = "PARALELO" | "BCV";
type SpreadViewMode = "AMBOS" | "BANCO" | "PRECIO";

interface ComputedRoute {
  id: string;
  buyBank: string;
  buyRate: number;
  sellBank: string;
  sellRate: number;
  isSameBank: boolean;
  bankFeePct: number;
  grossSpreadPct: number;
  netRoiPct: number;
  netProfitVes: number;
  netProfitUsdt: number;
}

const BANK_FILTERS = [
  "Todos",
  "Banesco",
  "Mercantil",
  "Venezuela",
  "Provincial",
  "BNC",
  "Bancamiga",
  "Pago Móvil",
];

const TICKET_PRESETS = [50, 100, 250, 500, 1000];

export default function SpreadMatrixPage() {
  const [amountUsdt, setAmountUsdt] = useState<number>(100);
  const [debouncedUsdt, setDebouncedUsdt] = useState<number>(100);
  const [valuationMode, setValuationMode] = useState<ValuationMode>("PARALELO");
  const [spreadViewMode, setSpreadViewMode] = useState<SpreadViewMode>("AMBOS");
  const [selectedBankChip, setSelectedBankChip] = useState<string>("Todos");
  const [merchantOnly, setMerchantOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [matrix, setMatrix] = useState<ArbitrageMatrix | null>(null);
  const [orderbook, setOrderbook] = useState<FilteredOrderbook | null>(null);
  const [bcv, setBcv] = useState<BCVRates | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [orderbookLoading, setOrderbookLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [pinnedBanks, setPinnedBanks] = useState<string[]>([]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedUsdt(amountUsdt > 0 ? amountUsdt : 100);
    }, 300);
    return () => clearTimeout(timer);
  }, [amountUsdt]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("p2p_pinned_banks");
        if (saved) {
          setPinnedBanks(JSON.parse(saved));
        }
      } catch {
        // Ignorar errores de lectura de localStorage
      }
    }
  }, []);

  function togglePinBank(bankName: string) {
    setPinnedBanks((prev) => {
      const next = prev.includes(bankName)
        ? prev.filter((b) => b !== bankName)
        : [...prev, bankName];
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("p2p_pinned_banks", JSON.stringify(next));
        } catch {
          // Ignorar errores de escritura en localStorage
        }
      }
      return next;
    });
  }

  // Cargar tasa BCV una sola vez al montar (se reutiliza la caché compartida y la tabla bcv_rate_history)
  useEffect(() => {
    getBCVRates()
      .then((bcvData) => {
        if (bcvData) setBcv(bcvData);
      })
      .catch(() => null);
  }, []);

  const fetchMatrixData = useCallback(async () => {
    setError(null);
    try {
      const matrixData = await getArbitrageMatrix(debouncedUsdt, merchantOnly);
      setMatrix(matrixData);
    } catch (err: any) {
      setError(
        err.message ||
          "No se pudo conectar con el motor de arbitraje FastAPI. Verifica que el backend esté activo."
      );
    } finally {
      setLoading(false);
    }
  }, [debouncedUsdt, merchantOnly]);

  const fetchOrderbookData = useCallback(async () => {
    try {
      const orderbookData = await getFilteredOrderbook({
        amount_usdt: debouncedUsdt,
        bank: selectedBankChip,
        merchant_only: merchantOnly,
        rows: 8,
      });
      if (orderbookData) setOrderbook(orderbookData);
    } catch {
      // Silencioso en fallo parcial de libro de órdenes
    } finally {
      setOrderbookLoading(false);
    }
  }, [debouncedUsdt, merchantOnly, selectedBankChip]);

  const fetchMarketData = useCallback(async () => {
    await Promise.all([fetchMatrixData(), fetchOrderbookData()]);
  }, [fetchMatrixData, fetchOrderbookData]);

  useEffect(() => {
    setLoading(true);
    fetchMatrixData();
    const interval = setInterval(() => fetchMatrixData(), 20000);
    return () => clearInterval(interval);
  }, [fetchMatrixData]);

  useEffect(() => {
    setOrderbookLoading(true);
    fetchOrderbookData();
    const interval = setInterval(() => fetchOrderbookData(), 20000);
    return () => clearInterval(interval);
  }, [fetchOrderbookData]);

  useWebSocket((msg) => {
    if (msg.type === "spread_update" && msg.data) {
      setMatrix((prev) => ({ ...(prev || {}), ...msg.data }));
    } else if (msg.type === "bcv_update" && msg.data) {
      setBcv((prev) => ({ ...(prev || {}), ...msg.data }));
    }
  });

  const bcvUsd = bcv?.usd || matrix?.bcv_official_usd || 0;
  const p2pRef = useMemo(() => {
    if (bcv?.p2p_usdt_ref && bcv.p2p_usdt_ref > 0) return bcv.p2p_usdt_ref;
    if (matrix?.quotes?.length) {
      const avg =
        matrix.quotes.reduce((acc, q) => acc + (q.buy_rate + q.sell_rate) / 2, 0) /
        matrix.quotes.length;
      return avg;
    }
    return 0;
  }, [bcv, matrix]);

  const brechaPct =
    bcv?.brecha_pct ??
    (bcvUsd > 0 && p2pRef > 0 ? ((p2pRef - bcvUsd) / bcvUsd) * 100 : 0);

  // Deduplicación defensiva por nombre de banco + Filtrado reactivo + Bancos Fijados (Pinning) arriba
  const uniqueQuotes = useMemo<RateQuote[]>(() => {
    const raw = matrix?.quotes || [];
    const seen = new Set<string>();
    const deduped: RateQuote[] = [];
    for (const q of raw) {
      if (!seen.has(q.bank_name)) {
        seen.add(q.bank_name);
        deduped.push(q);
      }
    }
    return deduped;
  }, [matrix]);

  const filteredQuotes = useMemo<RateQuote[]>(() => {
    const filtered = uniqueQuotes.filter((q) => {
      const nameLower = q.bank_name.toLowerCase();
      const matchesChip =
        selectedBankChip === "Todos" ||
        nameLower.includes(selectedBankChip.toLowerCase());
      const matchesSearch =
        !searchQuery.trim() ||
        nameLower.includes(searchQuery.trim().toLowerCase());
      return matchesChip && matchesSearch;
    });
    return [...filtered].sort((a, b) => {
      const aPinned = pinnedBanks.includes(a.bank_name) ? 1 : 0;
      const bPinned = pinnedBanks.includes(b.bank_name) ? 1 : 0;
      if (aPinned !== bPinned) return bPinned - aPinned;
      return b.spread_pct - a.spread_pct;
    });
  }, [uniqueQuotes, selectedBankChip, searchQuery, pinnedBanks]);

  const negativeSpreadQuotes = useMemo<RateQuote[]>(() => {
    return uniqueQuotes.filter(
      (q) => q.buy_rate > 0 && q.sell_rate > 0 && q.sell_rate < q.buy_rate
    );
  }, [uniqueQuotes]);

  // Cálculo del Top 3 de rutas cruzadas reales (deduciendo 0.3% Pago Móvil interbancario)
  const topRoutes = useMemo<ComputedRoute[]>(() => {
    const quotes = uniqueQuotes;
    if (!quotes.length) return [];

    const routes: ComputedRoute[] = [];
    for (const buyQ of quotes) {
      if (buyQ.buy_rate <= 0) continue;
      for (const sellQ of quotes) {
        if (sellQ.sell_rate <= 0) continue;
        const isSameBank = buyQ.bank_name === sellQ.bank_name;
        const bankFeePct = isSameBank ? 0 : 0.3;
        const capitalVes = amountUsdt * buyQ.buy_rate;
        const grossVesOut = amountUsdt * sellQ.sell_rate;
        const interbankFeeVes = isSameBank ? 0 : capitalVes * 0.003;
        const netProfitVes = grossVesOut - capitalVes - interbankFeeVes;
        const grossSpreadPct = ((sellQ.sell_rate - buyQ.buy_rate) / buyQ.buy_rate) * 100;
        const netRoiPct = capitalVes > 0 ? (netProfitVes / capitalVes) * 100 : 0;
        const netProfitUsdt = sellQ.sell_rate > 0 ? netProfitVes / sellQ.sell_rate : 0;

        routes.push({
          id: `${buyQ.bank_name}->${sellQ.bank_name}`,
          buyBank: buyQ.bank_name,
          buyRate: buyQ.buy_rate,
          sellBank: sellQ.bank_name,
          sellRate: sellQ.sell_rate,
          isSameBank,
          bankFeePct,
          grossSpreadPct,
          netRoiPct,
          netProfitVes,
          netProfitUsdt,
        });
      }
    }

    return routes.sort((a, b) => b.netRoiPct - a.netRoiPct).slice(0, 3);
  }, [uniqueQuotes, amountUsdt]);

  const optimalRoute = topRoutes[0] || null;

  const optimalUsdValue = useMemo(() => {
    if (!optimalRoute) return 0;
    if (valuationMode === "PARALELO") {
      return optimalRoute.netProfitUsdt;
    }
    return bcvUsd > 0 ? optimalRoute.netProfitVes / bcvUsd : 0;
  }, [optimalRoute, valuationMode, bcvUsd]);

  return (
    <AppShell
      title="Matriz de Márgenes y Bancos"
      badge="USDT / VES • EN VIVO"
      subtitle="Arbitraje sobre libro oficial Binance P2P con ajuste automático de comisión interbancaria (Pago Móvil 0,30%)."
      actions={
        <>
          {/* Selector de Valuación Dual */}
          <div className="p-0.5 rounded-lg bg-surface-container-low border border-[#1e2430] flex items-center text-[11px] font-mono">
            <button
              type="button"
              onClick={() => setValuationMode("PARALELO")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                valuationMode === "PARALELO"
                  ? "bg-primary-container text-on-primary font-bold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              USD Paralelo Real
            </button>
            <button
              type="button"
              onClick={() => setValuationMode("BCV")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                valuationMode === "BCV"
                  ? "bg-secondary text-on-secondary font-bold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              USD Legal BCV
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              setLoading(true);
              fetchMarketData();
            }}
            className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-primary-container/50 text-xs font-mono text-slate-200 flex items-center gap-1.5 transition-colors"
          >
            <span
              className={`material-symbols-outlined text-[16px] text-primary ${
                loading ? "animate-spin" : ""
              }`}
            >
              refresh
            </span>
            <span>Actualizar</span>
          </button>
        </>
      }
    >
      <div className="space-y-5">
        {error && (
          <div className="p-3.5 rounded-xl bg-error/10 border border-error/30 flex items-center justify-between gap-3 text-xs text-red-200">
            <div className="flex items-center gap-2.5">
              <span className="material-symbols-outlined text-[18px] text-error">
                warning
              </span>
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => fetchMarketData()}
              className="px-2.5 py-1 rounded bg-error/20 hover:bg-error/30 text-white font-mono text-[11px] shrink-0"
            >
              Reintentar
            </button>
          </div>
        )}

        {/* Alerta de Cobertura de Riesgo Cambiario (Spread Intrabanco Negativo) */}
        {negativeSpreadQuotes.length > 0 && (
          <div className="p-3.5 rounded-xl bg-error/15 border border-error/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <div className="flex items-start sm:items-center gap-2.5">
              <span className="material-symbols-outlined text-[20px] text-error shrink-0">
                trending_down
              </span>
              <div>
                <div className="font-bold text-white">
                  Alerta de Riesgo Cambiario — Margen Intrabanco Negativo Detectado
                </div>
                <div className="text-slate-300 mt-0.5">
                  Tasas invertidas (Venta &lt; Compra) en:{" "}
                  <span className="font-mono font-semibold text-error">
                    {negativeSpreadQuotes
                      .map((q) => `${q.bank_name} (${q.spread_pct.toFixed(2)}%)`)
                      .join(", ")}
                  </span>
                  {bcvUsd > 0 && ` • Tasa BCV: Bs. ${bcvUsd.toFixed(2)}`}
                </div>
              </div>
            </div>
            <span className="px-2.5 py-1 rounded bg-error/25 border border-error/40 text-error font-mono text-[10px] font-bold uppercase shrink-0">
              Evitar Ciclo Intrabanco
            </span>
          </div>
        )}

        {/* Fila Bento de 5 KPIs Institucionales */}
        <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
          {/* KPI 1: Tasa Oficial BCV */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Dólar Oficial BCV</span>
              <span className="material-symbols-outlined text-[16px] text-secondary">
                account_balance
              </span>
            </div>
            <div className="mt-2 text-xl font-mono font-bold text-white tabular-nums">
              {bcvUsd > 0 ? `Bs. ${bcvUsd.toFixed(2)}` : "Bs. --"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              {bcv?.eur ? `EUR BCV: Bs. ${bcv.eur.toFixed(2)}` : "Fuente Oficial BCV"}
            </div>
          </div>

          {/* KPI 2: Referencia P2P & Brecha */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Promedio USDT P2P</span>
              <span className="material-symbols-outlined text-[16px] text-primary">
                currency_exchange
              </span>
            </div>
            <div className="mt-2 text-xl font-mono font-bold text-white tabular-nums">
              {p2pRef > 0 ? `Bs. ${p2pRef.toFixed(2)}` : "Bs. --"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-primary tabular-nums">
              Brecha Cambiaria: {brechaPct >= 0 ? "+" : ""}
              {brechaPct.toFixed(2)}%
            </div>
          </div>

          {/* KPI 3: Mejor Margen Neto */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Mejor Retorno Neto Ciclo</span>
              <span className="material-symbols-outlined text-[16px] text-tertiary">
                trending_up
              </span>
            </div>
            <div
              className={`mt-2 text-xl font-mono font-bold tabular-nums ${
                optimalRoute && optimalRoute.netRoiPct > 0
                  ? "text-tertiary"
                  : optimalRoute
                  ? "text-error"
                  : "text-slate-400"
              }`}
            >
              {optimalRoute
                ? `${optimalRoute.netRoiPct >= 0 ? "+" : ""}${optimalRoute.netRoiPct.toFixed(2)}%`
                : "--"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              {optimalRoute
                ? `Bruto: ${optimalRoute.grossSpreadPct.toFixed(2)}% • Comisión Banco: ${optimalRoute.bankFeePct}%`
                : "Esperando cotizaciones"}
            </div>
          </div>

          {/* KPI 4: Ruta Óptima */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Ruta Óptima Detectada</span>
              <span className="material-symbols-outlined text-[16px] text-primary-container">
                alt_route
              </span>
            </div>
            <div className="mt-2 text-sm font-bold text-white truncate">
              {optimalRoute
                ? `${optimalRoute.buyBank} → ${optimalRoute.sellBank}`
                : "Escaneando bancos..."}
            </div>
            <div className="mt-1.5 text-[11px] font-mono text-slate-400 tabular-nums">
              {optimalRoute
                ? `C: ${optimalRoute.buyRate.toFixed(2)} | V: ${optimalRoute.sellRate.toFixed(2)}`
                : "Sin ruta activa"}
            </div>
          </div>

          {/* KPI 5: Retorno Neto Estimado */}
          <div className="p-4 rounded-xl bg-surface-container border border-primary-container/30">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-primary">
              <span>
                Retorno ({amountUsdt} USDT •{" "}
                {valuationMode === "PARALELO" ? "Real" : "BCV"})
              </span>
              <span className="material-symbols-outlined text-[16px] text-primary">
                payments
              </span>
            </div>
            <div
              className={`mt-2 text-xl font-mono font-bold tabular-nums ${
                optimalUsdValue > 0 ? "text-tertiary" : "text-slate-300"
              }`}
            >
              {optimalRoute
                ? `${optimalUsdValue >= 0 ? "+" : ""}${optimalUsdValue.toFixed(2)} ${
                    valuationMode === "PARALELO" ? "USDT" : "USD BCV"
                  }`
                : "--"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              {optimalRoute
                ? `${optimalRoute.netProfitVes >= 0 ? "+" : ""}Bs. ${optimalRoute.netProfitVes.toFixed(2)} netos`
                : "Monto configurable abajo"}
            </div>
          </div>
        </section>

        {/* Barra de Filtros Oficiales (Estilo Binance P2P: Banco + Monto + Verificados + Modo de Vista) */}
        <section className="p-3.5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-3">
          {/* Fila 1: Selector de Vista (Ambos / Spread por Banco / Spread por Precio) + Filtro Comerciante Verificado */}
          <div className="flex flex-wrap items-center justify-between gap-2.5 pb-2.5 border-b border-[#1e2430]">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mr-1">
                Modo de Análisis:
              </span>
              {(
                [
                  { id: "AMBOS", label: "Vista Dual (Banco + Precio)", icon: "dashboard" },
                  { id: "BANCO", label: "Spread por Banco", icon: "account_balance" },
                  { id: "PRECIO", label: "Spread por Precio (Libro Binance)", icon: "candlestick_chart" },
                ] as const
              ).map((tab) => {
                const active = spreadViewMode === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setSpreadViewMode(tab.id)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${
                      active
                        ? "bg-primary-container text-on-primary font-bold"
                        : "bg-surface-container text-slate-300 hover:text-white border border-[#1e2430]"
                    }`}
                  >
                    <span className="material-symbols-outlined text-[15px]">{tab.icon}</span>
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => setMerchantOnly((prev) => !prev)}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono flex items-center gap-1.5 border transition-colors ${
                  merchantOnly
                    ? "bg-amber-500/20 border-amber-400/50 text-amber-300 font-bold"
                    : "bg-surface-container border-[#1e2430] text-slate-300 hover:text-white"
                }`}
                title="Filtrar solo comerciantes verificados en el libro de órdenes de Binance P2P"
              >
                <span className="material-symbols-outlined text-[15px] text-amber-400">
                  verified
                </span>
                <span>Solo Comerciantes Verificados</span>
              </button>

              {orderbook && (
                <span className="px-2.5 py-1 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-[11px] font-mono text-slate-300 tabular-nums">
                  Filtro Binance:{" "}
                  <strong className="text-primary">
                    Bs. {orderbook.trans_amount_ves.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </strong>
                </span>
              )}
            </div>
          </div>

          {/* Fila 2: Chips de Bancos + Búsqueda + Monto Operativo en USDT */}
          <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3">
            {/* Izquierda: Activo Fijo USDT + Chips de Bancos */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2.5 py-1.5 rounded-lg bg-tertiary/15 border border-tertiary/30 text-tertiary text-xs font-mono font-bold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-tertiary" />
                USDT
              </span>
              <div className="h-5 w-px bg-[#1e2430] mx-1 hidden sm:block" />
              {BANK_FILTERS.map((bank) => {
                const active = selectedBankChip === bank;
                return (
                  <button
                    key={bank}
                    type="button"
                    onClick={() => setSelectedBankChip(bank)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                      active
                        ? "bg-primary-container text-on-primary font-semibold"
                        : "bg-surface-container text-slate-400 hover:text-white border border-[#1e2430]"
                    }`}
                  >
                    {bank}
                  </button>
                );
              })}
            </div>

            {/* Derecha: Búsqueda + Selector de Monto USDT */}
            <div className="flex items-center gap-2.5 flex-wrap">
              <div className="relative flex-1 sm:flex-initial">
                <span className="material-symbols-outlined text-[16px] text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2">
                  search
                </span>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filtrar banco..."
                  className="w-full sm:w-44 pl-8 pr-3 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white placeholder:text-slate-500"
                />
              </div>

              <div className="flex items-center gap-1.5 bg-surface-container p-1 rounded-lg border border-[#1e2430]">
                <span className="px-2 text-[10px] font-mono uppercase text-slate-300">
                  Monto USDT:
                </span>
                <BankAmountInput
                  value={amountUsdt}
                  onChange={setAmountUsdt}
                  ariaLabel="Monto Operativo en USDT"
                  className="w-24 px-2 py-0.5 rounded bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-right text-[11px] font-mono font-bold text-primary tabular-nums"
                />
                {TICKET_PRESETS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => setAmountUsdt(preset)}
                    className={`px-2 py-0.5 rounded text-[11px] font-mono tabular-nums transition-colors ${
                      amountUsdt === preset
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-300 hover:text-white"
                    }`}
                  >
                    {preset}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* SECCIÓN 1: SPREAD POR PRECIO Y LIBRO DE ANUNCIOS EN VIVO (TAL CUAL COMO EN BINANCE P2P) */}
        {(spreadViewMode === "AMBOS" || spreadViewMode === "PRECIO") && (
          <section className="rounded-xl bg-surface-container-low border border-[#1e2430] overflow-hidden space-y-4 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#1e2430]">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[19px] text-primary">
                  candlestick_chart
                </span>
                <div>
                  <h2 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>Spread por Precio — Libro de Anuncios Binance P2P</span>
                    <span className="px-2 py-0.5 rounded bg-primary-container/20 text-primary text-[10px] font-mono">
                      {selectedBankChip === "Todos" ? "Todos los Bancos" : selectedBankChip} • {amountUsdt} USDT
                    </span>
                  </h2>
                  <p className="text-[11px] text-slate-400">
                    Anuncios filtrados en vivo por límite en Bolívares (
                    {orderbook
                      ? `Bs. ${orderbook.trans_amount_ves.toLocaleString("es-VE", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}`
                      : `~${amountUsdt} USDT`}
                    ), método de pago y estado de comerciante.
                  </p>
                </div>
              </div>

              {orderbook && orderbook.best_buy_price > 0 && orderbook.best_sell_price > 0 && (
                <Link
                  href={`/calculator?buyBank=${encodeURIComponent(
                    selectedBankChip === "Todos" ? "Pago Móvil" : selectedBankChip
                  )}&buyRate=${(orderbook.recommended_mode === "MAKER"
                    ? orderbook.best_sell_price
                    : orderbook.best_buy_price
                  ).toFixed(2)}&sellBank=${encodeURIComponent(
                    selectedBankChip === "Todos" ? "Pago Móvil" : selectedBankChip
                  )}&sellRate=${(orderbook.recommended_mode === "MAKER"
                    ? orderbook.best_buy_price
                    : orderbook.best_sell_price
                  ).toFixed(2)}&amount=${amountUsdt}`}
                  className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-mono font-bold flex items-center gap-1.5 hover:brightness-110 transition-all"
                >
                  <span>Simular Ciclo por Precio</span>
                  <span className="material-symbols-outlined text-[15px]">calculate</span>
                </Link>
              )}
            </div>

            {/* Tarjetas de Puntas y Spread por Precio (Maker vs Taker) */}
            {orderbook && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="p-3 rounded-lg bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    Mejor Precio Compra (Columna Comprar)
                  </div>
                  <div className="mt-1 text-lg font-mono font-bold text-tertiary tabular-nums">
                    {orderbook.best_buy_price > 0
                      ? `Bs. ${orderbook.best_buy_price.toFixed(2)}`
                      : "--"}
                  </div>
                  <div className="text-[11px] font-mono text-slate-400 truncate">
                    {orderbook.buy_ads[0]
                      ? `${orderbook.buy_ads[0].nick_name} (${orderbook.buy_ads[0].finish_rate_pct}%)`
                      : "Sin anuncios para este monto"}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    Mejor Precio Venta (Columna Vender)
                  </div>
                  <div className="mt-1 text-lg font-mono font-bold text-primary tabular-nums">
                    {orderbook.best_sell_price > 0
                      ? `Bs. ${orderbook.best_sell_price.toFixed(2)}`
                      : "--"}
                  </div>
                  <div className="text-[11px] font-mono text-slate-400 truncate">
                    {orderbook.sell_ads[0]
                      ? `${orderbook.sell_ads[0].nick_name} (${orderbook.sell_ads[0].finish_rate_pct}%)`
                      : "Sin anuncios para este monto"}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-surface-container border border-[#1e2430]">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono uppercase text-slate-400">
                      Spread Comerciante (Maker)
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-primary-container/20 text-primary text-[9px] font-mono">
                      Con Anuncio
                    </span>
                  </div>
                  <div
                    className={`mt-1 text-lg font-mono font-bold tabular-nums ${
                      orderbook.maker_spread_pct > 0 ? "text-tertiary" : "text-error"
                    }`}
                  >
                    {orderbook.maker_spread_pct >= 0 ? "+" : ""}
                    {orderbook.maker_spread_pct.toFixed(2)}% (
                    {orderbook.maker_spread_ves >= 0 ? "+" : ""}Bs.{" "}
                    {orderbook.maker_spread_ves.toFixed(2)})
                  </div>
                  <div className="text-[11px] font-mono text-slate-400">
                    Compras a Bs. {orderbook.best_sell_price.toFixed(2)} → Vendes a Bs.{" "}
                    {orderbook.best_buy_price.toFixed(2)}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-surface-container border border-[#1e2430]">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono uppercase text-slate-400">
                      Spread Directo (Taker)
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-surface-container-high text-slate-300 text-[9px] font-mono">
                      Sin Anuncio
                    </span>
                  </div>
                  <div
                    className={`mt-1 text-lg font-mono font-bold tabular-nums ${
                      orderbook.taker_spread_pct > 0 ? "text-tertiary" : "text-error"
                    }`}
                  >
                    {orderbook.taker_spread_pct >= 0 ? "+" : ""}
                    {orderbook.taker_spread_pct.toFixed(2)}% (
                    {orderbook.taker_spread_ves >= 0 ? "+" : ""}Bs.{" "}
                    {orderbook.taker_spread_ves.toFixed(2)})
                  </div>
                  <div className="text-[11px] font-mono text-slate-400">
                    Neto ({amountUsdt} USDT):{" "}
                    <strong className={orderbook.net_profit_ves >= 0 ? "text-tertiary" : "text-error"}>
                      {orderbook.net_profit_ves >= 0 ? "+" : ""}Bs.{" "}
                      {orderbook.net_profit_ves.toFixed(2)}
                    </strong>
                  </div>
                </div>
              </div>
            )}

            {/* Dos Columnas: Anuncios de Compra vs Anuncios de Venta (Igual que Binance P2P) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Columna Izquierda: Pestaña COMPRAR USDT */}
              <div className="rounded-lg bg-surface-container-lowest border border-[#1e2430] overflow-hidden">
                <div className="px-3.5 py-2.5 bg-tertiary/10 border-b border-[#1e2430] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-tertiary" />
                    <span className="text-xs font-bold text-white">
                      Libro Comprar USDT (Menor a Mayor Precio)
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-tertiary">
                    {orderbook?.buy_ads?.length || 0} anuncios compatibles
                  </span>
                </div>

                <div className="divide-y divide-[#1e2430]/70 max-h-80 overflow-y-auto">
                  {orderbookLoading && !orderbook ? (
                    <div className="p-6 text-center text-xs font-mono text-slate-400">
                      Filtrando anuncios de compra en Binance P2P...
                    </div>
                  ) : !orderbook?.buy_ads?.length ? (
                    <div className="p-6 text-center text-xs font-mono text-slate-400">
                      No hay anuncios de compra para {amountUsdt} USDT en {selectedBankChip}.
                    </div>
                  ) : (
                    orderbook.buy_ads.map((ad, i) => (
                      <div
                        key={`buy-${ad.adv_no}-${i}`}
                        className="p-3 hover:bg-surface-container/60 transition-colors flex items-center justify-between gap-3 text-xs"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-white truncate">
                              {ad.nick_name}
                            </span>
                            {ad.is_merchant && (
                              <span
                                className="material-symbols-outlined text-[14px] text-amber-400"
                                title="Comerciante Verificado Binance P2P"
                              >
                                verified
                              </span>
                            )}
                            <span className="text-[10px] font-mono text-slate-400">
                              {ad.month_orders} órds • {ad.finish_rate_pct}%
                            </span>
                          </div>
                          <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
                            Disp: <strong className="text-slate-200">{ad.surplus_usdt.toFixed(2)} USDT</strong> • Límite:{" "}
                            <span className="text-slate-300">
                              Bs. {ad.min_ves.toLocaleString("es-VE")} – Bs.{" "}
                              {ad.max_ves.toLocaleString("es-VE")}
                            </span>
                          </div>
                          <div className="mt-1 flex items-center gap-1 flex-wrap">
                            {ad.banks.map((b) => (
                              <span
                                key={`${ad.adv_no}-${b}`}
                                className="px-1.5 py-0.2 rounded bg-surface-container-high text-[10px] font-mono text-slate-300"
                              >
                                {b}
                              </span>
                            ))}
                          </div>
                        </div>

                        <div className="text-right shrink-0">
                          <div className="text-sm font-mono font-bold text-tertiary tabular-nums">
                            Bs. {ad.price.toFixed(2)}
                          </div>
                          <Link
                            href={`/calculator?buyBank=${encodeURIComponent(
                              ad.banks[0] || selectedBankChip
                            )}&buyRate=${ad.price.toFixed(2)}&sellBank=${encodeURIComponent(
                              orderbook.sell_ads[0]?.banks[0] || ad.banks[0] || selectedBankChip
                            )}&sellRate=${(orderbook.best_sell_price || ad.price).toFixed(
                              2
                            )}&amount=${amountUsdt}`}
                            className="mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded bg-tertiary/15 hover:bg-tertiary/25 text-tertiary text-[10px] font-mono font-semibold"
                          >
                            Usar Compra
                          </Link>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Columna Derecha: Pestaña VENDER USDT */}
              <div className="rounded-lg bg-surface-container-lowest border border-[#1e2430] overflow-hidden">
                <div className="px-3.5 py-2.5 bg-primary-container/10 border-b border-[#1e2430] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-primary" />
                    <span className="text-xs font-bold text-white">
                      Libro Vender USDT (Mayor a Menor Precio)
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-primary">
                    {orderbook?.sell_ads?.length || 0} anuncios compatibles
                  </span>
                </div>

                <div className="divide-y divide-[#1e2430]/70 max-h-80 overflow-y-auto">
                  {orderbookLoading && !orderbook ? (
                    <div className="p-6 text-center text-xs font-mono text-slate-400">
                      Filtrando anuncios de venta en Binance P2P...
                    </div>
                  ) : !orderbook?.sell_ads?.length ? (
                    <div className="p-6 text-center text-xs font-mono text-slate-400">
                      No hay anuncios de venta para {amountUsdt} USDT en {selectedBankChip}.
                    </div>
                  ) : (
                    orderbook.sell_ads.map((ad, i) => (
                      <div
                        key={`sell-${ad.adv_no}-${i}`}
                        className="p-3 hover:bg-surface-container/60 transition-colors flex items-center justify-between gap-3 text-xs"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-white truncate">
                              {ad.nick_name}
                            </span>
                            {ad.is_merchant && (
                              <span
                                className="material-symbols-outlined text-[14px] text-amber-400"
                                title="Comerciante Verificado Binance P2P"
                              >
                                verified
                              </span>
                            )}
                            <span className="text-[10px] font-mono text-slate-400">
                              {ad.month_orders} órds • {ad.finish_rate_pct}%
                            </span>
                          </div>
                          <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
                            Disp: <strong className="text-slate-200">{ad.surplus_usdt.toFixed(2)} USDT</strong> • Límite:{" "}
                            <span className="text-slate-300">
                              Bs. {ad.min_ves.toLocaleString("es-VE")} – Bs.{" "}
                              {ad.max_ves.toLocaleString("es-VE")}
                            </span>
                          </div>
                          <div className="mt-1 flex items-center gap-1 flex-wrap">
                            {ad.banks.map((b) => (
                              <span
                                key={`${ad.adv_no}-${b}`}
                                className="px-1.5 py-0.2 rounded bg-surface-container-high text-[10px] font-mono text-slate-300"
                              >
                                {b}
                              </span>
                            ))}
                          </div>
                        </div>

                        <div className="text-right shrink-0">
                          <div className="text-sm font-mono font-bold text-primary tabular-nums">
                            Bs. {ad.price.toFixed(2)}
                          </div>
                          <Link
                            href={`/calculator?buyBank=${encodeURIComponent(
                              orderbook.buy_ads[0]?.banks[0] || ad.banks[0] || selectedBankChip
                            )}&buyRate=${(orderbook.best_buy_price || ad.price).toFixed(
                              2
                            )}&sellBank=${encodeURIComponent(
                              ad.banks[0] || selectedBankChip
                            )}&sellRate=${ad.price.toFixed(2)}&amount=${amountUsdt}`}
                            className="mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded bg-primary-container/20 hover:bg-primary-container/30 text-primary text-[10px] font-mono font-semibold"
                          >
                            Usar Venta
                          </Link>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* SECCIÓN 2: SPREAD POR BANCO (MATRIZ INTERBANCARIA) */}
        {(spreadViewMode === "AMBOS" || spreadViewMode === "BANCO") && (
        <section className="rounded-xl bg-surface-container-low border border-[#1e2430] overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1e2430] flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-primary">
                table_rows
              </span>
              <h2 className="text-sm font-bold text-white">
                Libro de Tasas por Método Bancario (Monto {amountUsdt} USDT)
              </h2>
            </div>
            <span className="text-[11px] font-mono text-slate-400 tabular-nums">
              {filteredQuotes.length} métodos monitoreados
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#1e2430] bg-surface-container/60 text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  <th className="py-3 px-4">Banco / Canal VES</th>
                  <th className="py-3 px-4 text-right">Compra USDT (Bs)</th>
                  <th className="py-3 px-4 text-right">Venta USDT (Bs)</th>
                  <th className="py-3 px-4 text-right">Margen Intrabanco</th>
                  <th className="py-3 px-4 text-right">
                    Ganancia ({amountUsdt} USDT)
                  </th>
                  <th className="py-3 px-4">Liquidez / Anuncios</th>
                  <th className="py-3 px-4 text-right">Simulador</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2430]/70 text-xs">
                {loading && filteredQuotes.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-slate-400 font-mono">
                      Consultando libro de órdenes oficial de Binance P2P...
                    </td>
                  </tr>
                ) : filteredQuotes.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-slate-400 font-mono">
                      No hay cotizaciones para el filtro seleccionado.
                    </td>
                  </tr>
                ) : (
                  filteredQuotes.map((q) => {
                    const isPinned = pinnedBanks.includes(q.bank_name);
                    const intraProfitVes = (q.sell_rate - q.buy_rate) * amountUsdt;
                    const intraProfitUsd =
                      valuationMode === "PARALELO"
                        ? q.sell_rate > 0
                          ? intraProfitVes / q.sell_rate
                          : 0
                        : bcvUsd > 0
                        ? intraProfitVes / bcvUsd
                        : 0;
                    const isPositive = q.spread_pct > 0;
                    const isNegativeSpread = q.sell_rate < q.buy_rate;

                    // Acción de 1 Clic (Deep Linking Inteligente):
                    // Pre-selecciona automáticamente el mejor banco destino (mismo banco 0% o interbancario 0.3%)
                    const allQuotes = matrix?.quotes || [q];
                    let bestTargetBank = q.bank_name;
                    let bestTargetSellRate = q.sell_rate;
                    let bestNetVes = intraProfitVes;

                    for (const candidate of allQuotes) {
                      if (candidate.sell_rate <= 0) continue;
                      const same = candidate.bank_name === q.bank_name;
                      const feeVes = same ? 0 : amountUsdt * q.buy_rate * 0.003;
                      const netCandidate =
                        amountUsdt * candidate.sell_rate -
                        amountUsdt * q.buy_rate -
                        feeVes;
                      if (netCandidate > bestNetVes) {
                        bestNetVes = netCandidate;
                        bestTargetBank = candidate.bank_name;
                        bestTargetSellRate = candidate.sell_rate;
                      }
                    }

                    const simHref = `/calculator?buyBank=${encodeURIComponent(
                      q.bank_name
                    )}&buyRate=${q.buy_rate.toFixed(2)}&sellBank=${encodeURIComponent(
                      bestTargetBank
                    )}&sellRate=${bestTargetSellRate.toFixed(2)}&amount=${amountUsdt}`;

                    return (
                      <tr
                        key={q.bank_name}
                        className={`hover:bg-surface-container/70 transition-colors ${
                          isPinned ? "bg-primary-container/5" : ""
                        }`}
                      >
                        <td className="py-3 px-4 font-semibold text-white">
                          <div className="flex items-center gap-2.5">
                            <button
                              type="button"
                              onClick={() => togglePinBank(q.bank_name)}
                              title={
                                isPinned
                                  ? "Desfijar banco de la parte superior"
                                  : "Fijar banco favorito en la parte superior"
                              }
                              className={`p-1 rounded transition-colors cursor-pointer ${
                                isPinned
                                  ? "text-primary bg-primary-container/20 border border-primary-container/40"
                                  : "text-slate-400 hover:text-white hover:bg-surface-container-high"
                              }`}
                            >
                              <span className="material-symbols-outlined text-[15px]">
                                push_pin
                              </span>
                            </button>
                            <span className="w-7 h-7 rounded-md bg-surface-container-high border border-[#1e2430] flex items-center justify-center text-[10px] font-mono font-bold text-primary">
                              {q.bank_name.slice(0, 3).toUpperCase()}
                            </span>
                            <div>
                              <div className="flex items-center gap-1.5">
                                <span>{q.bank_name}</span>
                                {isPinned && (
                                  <span className="px-1.5 py-0.2 rounded bg-primary-container/20 text-primary text-[9px] font-mono uppercase">
                                    Fijado
                                  </span>
                                )}
                                {isNegativeSpread && (
                                  <span className="px-1.5 py-0.2 rounded bg-error/20 text-error text-[9px] font-mono uppercase">
                                    Tasa Invertida
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] font-mono text-slate-300">
                                {bestTargetBank === q.bank_name
                                  ? "Intrabanco 0% comisión"
                                  : `Ruta óptima → ${bestTargetBank} (0,30% PM)`}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-slate-200">
                          Bs. {q.buy_rate.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-white font-semibold">
                          Bs. {q.sell_rate.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                              isPositive
                                ? "bg-tertiary/15 text-tertiary"
                                : "bg-error/15 text-error"
                            }`}
                          >
                            {q.spread_pct >= 0 ? "+" : ""}
                            {q.spread_pct.toFixed(2)}%
                          </span>
                          <div className="text-[11px] text-slate-300 mt-0.5">
                            {q.spread_ves >= 0 ? "+" : ""}Bs. {q.spread_ves.toFixed(2)}
                          </div>
                        </td>
                        <td
                          className={`py-3 px-4 text-right font-mono tabular-nums font-semibold ${
                            intraProfitVes > 0 ? "text-tertiary" : "text-slate-300"
                          }`}
                        >
                          <div>
                            {intraProfitUsd >= 0 ? "+" : ""}
                            {intraProfitUsd.toFixed(2)}{" "}
                            {valuationMode === "PARALELO" ? "USDT" : "USD"}
                          </div>
                          <div className="text-[11px] text-slate-300 font-normal">
                            {intraProfitVes >= 0 ? "+" : ""}Bs. {intraProfitVes.toFixed(2)}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                              <div
                                className="h-full bg-secondary rounded-full"
                                style={{
                                  width: `${Math.min(100, Math.max(10, q.liquidity_pct))}%`,
                                }}
                              />
                            </div>
                            <span className="text-[11px] font-mono text-slate-300 tabular-nums">
                              {q.total_ads} anuncios
                            </span>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Link
                            href={simHref}
                            title={`Simular compra en ${q.bank_name} y venta óptima en ${bestTargetBank}`}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container-high hover:bg-primary-container text-slate-200 hover:text-on-primary border border-slate-700 hover:border-primary-container text-[11px] font-mono font-semibold transition-all whitespace-nowrap"
                          >
                            <span>Simular</span>
                            <span className="material-symbols-outlined text-[14px]">
                              north_east
                            </span>
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
        )}

        {/* Mejores 3 Rutas de Arbitraje Cruzado (Con Deducción Pago Móvil 0,30%) */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-tertiary">
                hub
              </span>
              Mejores 3 Rutas de Arbitraje Cruzado (Neto Post-Comisión Bancaria)
            </h2>
            <span className="text-[11px] font-mono text-slate-400">
              Interbancario descuenta 0,30% Pago Móvil automáticamente
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3.5">
            {topRoutes.map((route, idx) => {
              const simUrl = `/calculator?buyBank=${encodeURIComponent(
                route.buyBank
              )}&buyRate=${route.buyRate.toFixed(2)}&sellBank=${encodeURIComponent(
                route.sellBank
              )}&sellRate=${route.sellRate.toFixed(2)}&amount=${amountUsdt}`;

              return (
                <div
                  key={route.id}
                  className={`p-4 rounded-xl border flex flex-col justify-between gap-4 ${
                    idx === 0
                      ? "bg-surface-container border-primary-container/40"
                      : "bg-surface-container-low border-[#1e2430]"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                          idx === 0
                            ? "bg-primary-container text-on-primary"
                            : "bg-surface-container-high text-slate-300"
                        }`}
                      >
                        #{idx + 1} {route.isSameBank ? "Intrabancario 0%" : "Interbancario 0,30%"}
                      </span>
                      <span
                        className={`text-sm font-mono font-bold tabular-nums ${
                          route.netRoiPct > 0 ? "text-tertiary" : "text-error"
                        }`}
                      >
                        {route.netRoiPct >= 0 ? "+" : ""}
                        {route.netRoiPct.toFixed(2)}% Retorno Neto
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 p-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs">
                      <div>
                        <div className="text-[10px] font-mono text-slate-300">
                          1. COMPRA EN
                        </div>
                        <div className="font-semibold text-white truncate mt-0.5">
                          {route.buyBank}
                        </div>
                        <div className="font-mono text-slate-300 tabular-nums">
                          Bs. {route.buyRate.toFixed(2)}
                        </div>
                      </div>
                      <div className="border-l border-[#1e2430] pl-2.5">
                        <div className="text-[10px] font-mono text-slate-300">
                          2. VENTA EN
                        </div>
                        <div className="font-semibold text-white truncate mt-0.5">
                          {route.sellBank}
                        </div>
                        <div className="font-mono text-primary tabular-nums">
                          Bs. {route.sellRate.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-[#1e2430]">
                    <div className="text-xs font-mono tabular-nums">
                      <span className="text-slate-300">Neto: </span>
                      <span
                        className={`font-bold ${
                          route.netProfitVes > 0 ? "text-tertiary" : "text-error"
                        }`}
                      >
                        {route.netProfitUsdt >= 0 ? "+" : ""}
                        {route.netProfitUsdt.toFixed(2)} USDT
                      </span>
                    </div>
                    <Link
                      href={simUrl}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1 ${
                        idx === 0
                          ? "bg-primary-container text-on-primary hover:brightness-110"
                          : "bg-surface-container-high border border-slate-700 text-slate-200 hover:border-primary-container/50 hover:text-white"
                      }`}
                    >
                      <span>Cargar en Simulador</span>
                      <span className="material-symbols-outlined text-[15px]">
                        calculate
                      </span>
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
