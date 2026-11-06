"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import {
  ArbitrageMatrix,
  BCVRates,
  RateQuote,
  getArbitrageMatrix,
  getBCVRates,
} from "@/lib/api";
import { useWebSocket } from "@/lib/useWebSocket";

type ValuationMode = "PARALELO" | "BCV";

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
  "Pago Móvil",
];

const TICKET_PRESETS = [50, 100, 250, 500, 1000];

export default function SpreadMatrixPage() {
  const [amountUsdt, setAmountUsdt] = useState<number>(100);
  const [valuationMode, setValuationMode] = useState<ValuationMode>("PARALELO");
  const [selectedBankChip, setSelectedBankChip] = useState<string>("Todos");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [matrix, setMatrix] = useState<ArbitrageMatrix | null>(null);
  const [bcv, setBcv] = useState<BCVRates | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMarketData = useCallback(async (ticket: number) => {
    setError(null);
    try {
      const [matrixData, bcvData] = await Promise.all([
        getArbitrageMatrix(ticket),
        getBCVRates().catch(() => null),
      ]);
      setMatrix(matrixData);
      if (bcvData) setBcv(bcvData);
    } catch (err: any) {
      setError(
        err.message ||
          "No se pudo conectar con el motor de arbitraje FastAPI. Verifica que el backend esté activo."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchMarketData(amountUsdt);
    const interval = setInterval(() => fetchMarketData(amountUsdt), 20000);
    return () => clearInterval(interval);
  }, [amountUsdt, fetchMarketData]);

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

  // Filtrado reactivo de cotizaciones bancarias
  const filteredQuotes = useMemo<RateQuote[]>(() => {
    const list = matrix?.quotes || [];
    return list.filter((q) => {
      const nameLower = q.bank_name.toLowerCase();
      const matchesChip =
        selectedBankChip === "Todos" ||
        nameLower.includes(selectedBankChip.toLowerCase());
      const matchesSearch =
        !searchQuery.trim() ||
        nameLower.includes(searchQuery.trim().toLowerCase());
      return matchesChip && matchesSearch;
    });
  }, [matrix, selectedBankChip, searchQuery]);

  // Cálculo del Top 3 de rutas cruzadas reales (deduciendo 0.3% Pago Móvil interbancario)
  const topRoutes = useMemo<ComputedRoute[]>(() => {
    const quotes = matrix?.quotes || [];
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
  }, [matrix, amountUsdt]);

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
      title="Matriz de Spreads & Bancos"
      badge="USDT / VES • EN VIVO"
      subtitle="Arbitraje sobre libro oficial Binance C2C con ajuste automático de comisión interbancaria (Pago Móvil 0.3%)."
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
              fetchMarketData(amountUsdt);
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
              onClick={() => fetchMarketData(amountUsdt)}
              className="px-2.5 py-1 rounded bg-error/20 hover:bg-error/30 text-white font-mono text-[11px] shrink-0"
            >
              Reintentar
            </button>
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

          {/* KPI 3: Mejor Spread Neto */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Mejor ROI Neto Ciclo</span>
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
                ? `Bruto: ${optimalRoute.grossSpreadPct.toFixed(2)}% • Fee Banco: ${optimalRoute.bankFeePct}%`
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
                : "Ticket configurable abajo"}
            </div>
          </div>
        </section>

        {/* Barra de Filtros Bancarios y Ticket */}
        <section className="p-3.5 rounded-xl bg-surface-container-low border border-[#1e2430] flex flex-col xl:flex-row xl:items-center justify-between gap-3">
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

          {/* Derecha: Búsqueda + Selector de Ticket USDT */}
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

            <div className="flex items-center gap-1 bg-surface-container p-1 rounded-lg border border-[#1e2430]">
              <span className="px-2 text-[10px] font-mono uppercase text-slate-400">
                Ticket:
              </span>
              {TICKET_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setAmountUsdt(preset)}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono tabular-nums transition-colors ${
                    amountUsdt === preset
                      ? "bg-primary-container text-on-primary font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* Tabla Institucional de Liquidez y Spreads por Banco */}
        <section className="rounded-xl bg-surface-container-low border border-[#1e2430] overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1e2430] flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-primary">
                table_rows
              </span>
              <h2 className="text-sm font-bold text-white">
                Libro de Tasas por Método Bancario (Ticket {amountUsdt} USDT)
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
                  <th className="py-3 px-4 text-right">Spread Intrabanco</th>
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

                    const simHref = `/calculator?buyBank=${encodeURIComponent(
                      q.bank_name
                    )}&buyRate=${q.buy_rate.toFixed(2)}&sellBank=${encodeURIComponent(
                      q.bank_name
                    )}&sellRate=${q.sell_rate.toFixed(2)}&amount=${amountUsdt}`;

                    return (
                      <tr
                        key={q.bank_name}
                        className="hover:bg-surface-container/70 transition-colors"
                      >
                        <td className="py-3 px-4 font-semibold text-white">
                          <div className="flex items-center gap-2.5">
                            <span className="w-7 h-7 rounded-md bg-surface-container-high border border-[#1e2430] flex items-center justify-center text-[10px] font-mono font-bold text-primary">
                              {q.bank_name.slice(0, 3).toUpperCase()}
                            </span>
                            <div>
                              <div>{q.bank_name}</div>
                              <div className="text-[10px] font-mono text-slate-500">
                                Intrabanco 0% comisión
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
                          <div className="text-[10px] text-slate-500 mt-0.5">
                            {q.spread_ves >= 0 ? "+" : ""}Bs. {q.spread_ves.toFixed(2)}
                          </div>
                        </td>
                        <td
                          className={`py-3 px-4 text-right font-mono tabular-nums font-semibold ${
                            intraProfitVes > 0 ? "text-tertiary" : "text-slate-400"
                          }`}
                        >
                          <div>
                            {intraProfitUsd >= 0 ? "+" : ""}
                            {intraProfitUsd.toFixed(2)}{" "}
                            {valuationMode === "PARALELO" ? "USDT" : "USD"}
                          </div>
                          <div className="text-[10px] text-slate-500 font-normal">
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
                            <span className="text-[11px] font-mono text-slate-400 tabular-nums">
                              {q.total_ads} ads
                            </span>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Link
                            href={simHref}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-primary-container/15 hover:bg-primary-container text-primary hover:text-on-primary border border-primary-container/30 text-[11px] font-mono font-semibold transition-all whitespace-nowrap"
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

        {/* Top 3 Rutas de Arbitraje Cruzado (Con Deducción Pago Móvil 0.3%) */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-tertiary">
                hub
              </span>
              Top 3 Rutas de Arbitraje Cruzado (Neto Post-Comisión Bancaria)
            </h2>
            <span className="text-[11px] font-mono text-slate-400">
              Interbancario descuenta 0.30% Pago Móvil automáticamente
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
                        #{idx + 1} {route.isSameBank ? "Intrabancario 0%" : "Interbancario 0.3%"}
                      </span>
                      <span
                        className={`text-sm font-mono font-bold tabular-nums ${
                          route.netRoiPct > 0 ? "text-tertiary" : "text-error"
                        }`}
                      >
                        {route.netRoiPct >= 0 ? "+" : ""}
                        {route.netRoiPct.toFixed(2)}% ROI Neto
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 p-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs">
                      <div>
                        <div className="text-[10px] font-mono text-slate-500">
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
                        <div className="text-[10px] font-mono text-slate-500">
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
                      <span className="text-slate-400">Neto: </span>
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
                      className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 transition-all flex items-center gap-1"
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
