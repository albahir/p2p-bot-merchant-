"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ChartVisualMode, TradingCandlesChart } from "@/components/trading-candles-chart";
import { useTelemetry } from "@/lib/telemetry-context";
import {
  MarketAnalyticsResponse,
  MarketCandlesResponse,
  MarketSideMode,
  MarketTimeframe,
  getCachedApiResponse,
  getMarketAnalytics,
  getMarketCandles,
  triggerMarketCollect,
} from "@/lib/api";

const SIDE_MODES: Array<{ id: MarketSideMode; label: string; shortLabel: string; desc: string }> = [
  { id: "sell", label: "USDT · Venta", shortLabel: "USDT · Venta", desc: "Tasa al vender USDT a bolívares" },
  { id: "buy", label: "USDT · Compra", shortLabel: "USDT · Compra", desc: "Tasa al comprar USDT con bolívares" },
  { id: "bank", label: "Por Banco & Monto", shortLabel: "Por Banco", desc: "Curva filtrada por banco específico" },
  { id: "evolucion", label: "Evolución P2P vs BCV", shortLabel: "P2P vs BCV", desc: "Brecha visual sobre mismo eje" },
  { id: "brecha", label: "Brecha (%)", shortLabel: "Brecha (%)", desc: "Porcentaje sobre dólar oficial BCV" },
];

const TIMEFRAMES: MarketTimeframe[] = ["1m", "5m", "15m", "1h", "4h", "1D"];

const TICKET_PRESETS: Array<{ label: string; ves: number }> = [
  { label: "Bs 250K", ves: 250_000 },
  { label: "Bs 500K", ves: 500_000 },
  { label: "Bs 1M", ves: 1_000_000 },
  { label: "Bs 3M", ves: 3_000_000 },
  { label: "Bs 5M", ves: 5_000_000 },
];

function fmtNum(val: number | null | undefined, digits = 2): string {
  if (val === null || val === undefined || Number.isNaN(val)) return "—";
  return val.toLocaleString("es-VE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export default function MarketPage() {
  const { user } = useTelemetry();
  const [side, setSide] = useState<MarketSideMode>("sell");
  const [timeframe, setTimeframe] = useState<MarketTimeframe>("5m");
  const [bank, setBank] = useState<string>("*");
  const [ticketVes, setTicketVes] = useState<number>(1_000_000);
  const [ticketInput, setTicketInput] = useState<string>("1000000");

  const [chartMode, setChartMode] = useState<ChartVisualMode>("candles");
  const [showTechMode, setShowTechMode] = useState<boolean>(false);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  const initialCandlesCache = useMemo(
    () =>
      getCachedApiResponse<MarketCandlesResponse>(
        "/api/market/candles?side=sell&timeframe=5m&bank=*&ticket_ves=1000000&limit=240"
      ),
    []
  );
  const initialAnalyticsCache = useMemo(
    () =>
      getCachedApiResponse<MarketAnalyticsResponse>(
        "/api/market/analytics?bank=*&ticket_ves=1000000"
      ),
    []
  );

  const [candlesData, setCandlesData] = useState<MarketCandlesResponse | null>(initialCandlesCache);
  const [analytics, setAnalytics] = useState<MarketAnalyticsResponse | null>(initialAnalyticsCache);
  const [loading, setLoading] = useState<boolean>(!initialCandlesCache);
  const [collecting, setCollecting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadCandles = useCallback(
    async (fresh = false, signal?: AbortSignal) => {
      try {
        setErrorMessage(null);
        const cRes = await getMarketCandles({
          side,
          timeframe,
          bank,
          ticketVes,
          limit: 240,
          fresh,
          signal,
        });
        if (!signal?.aborted) {
          setCandlesData(cRes);
        }
      } catch (err) {
        if ((err as Error)?.name === "AbortError") return;
        setErrorMessage(
          err instanceof Error ? err.message : "No se pudieron cargar las velas de mercado."
        );
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [side, timeframe, bank, ticketVes]
  );

  const loadAnalytics = useCallback(
    async (fresh = false, signal?: AbortSignal) => {
      try {
        const aRes = await getMarketAnalytics({ bank, ticketVes, side, fresh, signal });
        if (!signal?.aborted) {
          setAnalytics(aRes);
        }
      } catch (err) {
        if ((err as Error)?.name === "AbortError") return;
        setErrorMessage(
          err instanceof Error ? err.message : "No se pudieron cargar las métricas de mercado."
        );
      }
    },
    [bank, ticketVes, side]
  );

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    void loadCandles(false, controller.signal);
    return () => controller.abort();
  }, [loadCandles]);

  useEffect(() => {
    const controller = new AbortController();
    void loadAnalytics(false, controller.signal);
    return () => controller.abort();
  }, [loadAnalytics]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = window.setInterval(() => {
      void Promise.all([loadCandles(true), loadAnalytics(true)]);
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, loadCandles, loadAnalytics]);

  const handleManualCollect = async () => {
    setCollecting(true);
    setStatusMessage(null);
    setErrorMessage(null);
    try {
      const res = await triggerMarketCollect({ bank, ticketVes });
      setStatusMessage(res.message);
      if (res.captured) {
        await Promise.all([loadCandles(true), loadAnalytics(true)]);
      }
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "No se pudo capturar snapshot en vivo."
      );
    } finally {
      setCollecting(false);
    }
  };

  const handleApplyTicket = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = Number(ticketInput.replace(/[^\d.]/g, ""));
    if (Number.isFinite(parsed) && parsed > 0) {
      setTicketVes(Math.min(500_000_000, Math.max(1000, parsed)));
    }
  };

  const unitSuffix = side === "brecha" ? "%" : "Bs";
  const bankOptions = candlesData?.bank_options ?? [
    "*",
    "Banesco",
    "Pago Móvil",
    "Banco de Venezuela",
    "Mercantil",
    "Bancamiga",
    "BBVA Provincial",
    "BNC",
  ];

  const imbalancePct = analytics ? Math.round(analytics.depth_summary.imbalance * 100) : 0;

  return (
    <AppShell>
      <div className="space-y-4 pb-10">
        {/* Cabecera Terminal */}
        <header className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800/80 bg-[#101419] px-4 py-3.5">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-slate-100">
                Comportamiento del USDT (Velas en Vivo)
              </h1>
              <span
                title="Filtra picos aislados para mostrar solo tasas sostenidas del libro"
                className="inline-flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-mono font-semibold text-amber-400"
              >
                VISTA INDEPENDIENTE · ANTI-PICOS
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Evolución del USDT minuto a minuto, liquidez real para tu monto y fuerza entre compradores y vendedores.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-[#0a0e13] px-2.5 py-1.5 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="accent-amber-500"
              />
              <span>Auto 60s</span>
            </label>

            {user && (
              <button
                type="button"
                onClick={() => void handleManualCollect()}
                disabled={collecting}
                className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 px-3.5 py-1.5 text-xs font-semibold text-slate-950 transition-colors"
              >
                <span className="material-symbols-outlined text-[16px]">
                  {collecting ? "sync" : "add_chart"}
                </span>
                {collecting ? "Capturando..." : "Capturar ahora"}
              </button>
            )}
          </div>
        </header>

        {statusMessage && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-2 text-xs text-emerald-300">
            {statusMessage}
          </div>
        )}
        {errorMessage && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3.5 py-2 text-xs text-rose-300">
            {errorMessage}
          </div>
        )}

        {/* KPI Strip */}
        <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          <div className="rounded-xl border border-slate-800/80 bg-[#101419] p-3.5">
            <div className="text-[11px] font-medium text-slate-400">Mejor Tasa en Binance P2P</div>
            <div className="mt-1.5 space-y-0.5 font-mono tabular-nums">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400 font-sans">Si vendes USDT:</span>
                <span className="text-sm font-bold text-emerald-400">
                  {fmtNum(analytics?.live_p2p_sell)} Bs
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400 font-sans">Si compras USDT:</span>
                <span className="text-sm font-semibold text-sky-400">
                  {fmtNum(analytics?.live_p2p_buy)} Bs
                </span>
              </div>
            </div>
            <div className="mt-1.5 text-[11px] font-mono text-slate-400 tabular-nums">
              {analytics && analytics.live_p2p_buy > 0 && analytics.live_p2p_sell > 0
                ? analytics.live_p2p_buy >= analytics.live_p2p_sell
                  ? `Margen anunciante: +${fmtNum(analytics.live_p2p_buy - analytics.live_p2p_sell)} Bs (${fmtNum(((analytics.live_p2p_buy - analytics.live_p2p_sell) / analytics.live_p2p_sell) * 100)}%)`
                  : `Margen directo: +${fmtNum(analytics.live_p2p_sell - analytics.live_p2p_buy)} Bs (${fmtNum(((analytics.live_p2p_sell - analytics.live_p2p_buy) / analytics.live_p2p_buy) * 100)}%)`
                : "Sin puntas disponibles"}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800/80 bg-[#101419] p-3.5">
            <div className="text-[11px] font-medium text-slate-400">BCV Oficial y Brecha</div>
            <div className="mt-1 flex items-baseline gap-2.5 font-mono tabular-nums">
              <span className="text-lg font-bold text-slate-100">
                {fmtNum(analytics?.live_bcv)} Bs
              </span>
              <span className="text-sm font-bold text-amber-400">
                +{fmtNum(analytics?.brecha_pct)}%
              </span>
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              {analytics?.brecha_velocity !== null && analytics?.brecha_velocity !== undefined
                ? Math.abs(analytics.brecha_velocity) < 0.05
                  ? `Ritmo: Estable (${fmtNum(analytics.brecha_velocity)}% / hora)`
                  : analytics.brecha_velocity > 0
                  ? `Ritmo: Subiendo (+${fmtNum(analytics.brecha_velocity)}% / hora)`
                  : `Ritmo: Bajando (${fmtNum(analytics.brecha_velocity)}% / hora)`
                : "Ritmo: Esperando más lecturas"}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800/80 bg-[#101419] p-3.5">
            <div className="flex items-center justify-between gap-2 text-[11px] font-medium text-slate-400">
              <span>Presión Compra / Venta</span>
              <span className="font-mono text-[10px] text-amber-400">
                {bank === "*" ? "Todos" : bank}
              </span>
            </div>
            <div className="mt-1 flex items-baseline gap-2.5 font-mono tabular-nums">
              <span className="text-base font-bold text-slate-100">
                {analytics?.order_flow
                  ? `${analytics.order_flow.buy_ads_share_pct.toFixed(0)}% C / ${analytics.order_flow.sell_ads_share_pct.toFixed(0)}% V`
                  : "—"}
              </span>
              <span className="text-[11px] text-slate-400">
                {analytics?.order_flow
                  ? `${analytics.order_flow.total_buy_ads + analytics.order_flow.total_sell_ads} anuncios`
                  : ""}
              </span>
            </div>
            <div className="mt-1 text-[11px] text-slate-400 leading-snug">
              {analytics?.order_flow?.pressure_label ?? "Calculando presión del libro..."}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800/80 bg-[#101419] p-3.5">
            <div className="flex items-center justify-between text-[11px] font-medium text-slate-400">
              <span>Liquidez Top 20 y Banco Líder</span>
              <span className="font-mono text-slate-500">
                {analytics ? `${analytics.samples_total} lect.` : "—"}
              </span>
            </div>
            <div className="mt-1 flex items-baseline gap-2 font-mono tabular-nums">
              <span className="text-base font-bold text-emerald-400">
                {analytics
                  ? `${fmtNum(analytics.depth_summary.top20.buy_usdt + analytics.depth_summary.top20.sell_usdt, 0)} USDT`
                  : "—"}
              </span>
              {analytics?.liquidity_alert.detected && (
                <span className="text-[10px] text-rose-400 font-semibold">Liquidez baja</span>
              )}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 truncate tabular-nums">
              {analytics?.banks_snapshot?.[0]
                ? `Líder: ${analytics.banks_snapshot[0].bank} (${fmtNum(analytics.banks_snapshot[0].sell_best)} / ${fmtNum(analytics.banks_snapshot[0].buy_best)} Bs)`
                : "Sin desglose bancario activo"}
            </div>
          </div>
        </section>

        {/* Controles de Modo, Temporalidad, Banco y Ticket */}
        <section className="rounded-xl border border-slate-800/80 bg-[#101419] p-3.5 space-y-3">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-2.5">
            {/* 5 Modos en 2 filas limpias en móvil (2 arriba + 3 abajo) */}
            <div className="grid grid-cols-6 sm:flex sm:flex-wrap items-center gap-1.5 w-full lg:w-auto">
              {SIDE_MODES.map((m, idx) => (
                <button
                  key={m.id}
                  type="button"
                  title={m.desc}
                  onClick={() => setSide(m.id)}
                  className={`${
                    idx < 2 ? "col-span-3" : "col-span-2"
                  } sm:col-auto px-2 sm:px-3 py-1.5 rounded-lg text-[11px] sm:text-xs font-semibold text-center whitespace-nowrap transition-colors ${
                    side === m.id
                      ? "bg-amber-500 text-slate-950"
                      : "bg-[#0a0e13] border border-slate-800 text-slate-300 hover:border-slate-700"
                  }`}
                >
                  <span className="sm:hidden">{m.shortLabel}</span>
                  <span className="hidden sm:inline">{m.label}</span>
                </button>
              ))}
            </div>

            {/* Temporalidades distribuidas simétricamente */}
            <div className="grid grid-cols-6 sm:flex items-center gap-1 rounded-lg border border-slate-800 bg-[#0a0e13] p-1 w-full lg:w-auto">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  type="button"
                  onClick={() => setTimeframe(tf)}
                  className={`px-2 sm:px-2.5 py-1 rounded text-xs font-mono font-semibold text-center transition-colors ${
                    timeframe === tf
                      ? "bg-slate-800 text-amber-400"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-2.5 pt-2 border-t border-slate-800/70">
            {/* Tipo de gráfico + Overlays agrupados en 2 filas ordenadas en móvil */}
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full lg:w-auto">
              <div className="grid grid-cols-3 sm:inline-flex rounded-lg border border-slate-800 bg-[#0a0e13] p-0.5 text-xs w-full sm:w-auto">
                {(
                  [
                    { id: "candles", label: "Velas" },
                    { id: "line", label: "Línea" },
                    { id: "area", label: "Área" },
                  ] as const
                ).map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    disabled={side === "evolucion"}
                    onClick={() => setChartMode(t.id)}
                    className={`px-2.5 py-1 rounded font-medium text-center disabled:opacity-40 ${
                      chartMode === t.id
                        ? "bg-slate-800 text-slate-100"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-1 sm:flex items-center gap-2 w-full sm:w-auto">
                <button
                  type="button"
                  title="Activa medias móviles EMA 9/21 y fuerza RSI 14 (herramientas de análisis técnico avanzado)"
                  onClick={() => setShowTechMode((v) => !v)}
                  disabled={side === "evolucion"}
                  className={`px-3 py-1.5 sm:py-1 rounded-lg border text-xs font-medium text-center whitespace-nowrap transition-colors disabled:opacity-40 ${
                    showTechMode
                      ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                      : "border-slate-800 bg-[#0a0e13] text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Modo técnico (EMA / RSI)
                </button>
              </div>
            </div>

            {/* Banco + Ticket VWAP */}
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full lg:w-auto">
              <select
                value={bank}
                onChange={(e) => setBank(e.target.value)}
                aria-label="Filtrar por banco"
                className="w-full sm:w-auto rounded-lg border border-slate-700 bg-[#0a0e13] px-2.5 py-1.5 text-xs text-slate-200 focus:border-amber-500 focus:outline-none"
              >
                {bankOptions.map((b) => (
                  <option key={b} value={b}>
                    {b === "*" ? "Todos los bancos" : b}
                  </option>
                ))}
              </select>

              <div className="grid grid-cols-5 sm:flex items-center gap-1 w-full sm:w-auto">
                {TICKET_PRESETS.map((p) => {
                  const isTracked = p.ves === 250_000 || p.ves === 1_000_000 || p.ves === 5_000_000;
                  return (
                    <button
                      key={p.ves}
                      type="button"
                      title={
                        isTracked
                          ? `${p.label}: actualiza historial de velas + Tasa Real (VWAP)`
                          : `${p.label}: calcula Tasa Real (VWAP) en vivo`
                      }
                      onClick={() => {
                        setTicketVes(p.ves);
                        setTicketInput(String(p.ves));
                      }}
                      className={`px-1 sm:px-2 py-1 rounded text-[10px] sm:text-[11px] font-mono text-center whitespace-nowrap tabular-nums transition-colors ${
                        ticketVes === p.ves
                          ? "bg-amber-500/20 border border-amber-500/50 text-amber-300"
                          : "bg-[#0a0e13] border border-slate-800 text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {p.label}
                      {isTracked ? " •" : ""}
                    </button>
                  );
                })}
              </div>

              <form onSubmit={handleApplyTicket} className="flex items-center gap-1.5 w-full sm:w-auto">
                <input
                  type="text"
                  value={ticketInput}
                  onChange={(e) => setTicketInput(e.target.value)}
                  aria-label="Monto ticket en bolívares"
                  className="flex-1 min-w-0 sm:w-28 rounded-lg border border-slate-700 bg-[#0a0e13] px-2.5 py-1.5 sm:py-1 text-xs font-mono text-slate-100 tabular-nums focus:border-amber-500 focus:outline-none"
                  placeholder="Ticket Bs"
                />
                <button
                  type="submit"
                  className="px-3 py-1.5 sm:py-1 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 shrink-0 whitespace-nowrap"
                >
                  Calcular monto
                </button>
              </form>
            </div>
          </div>
        </section>

        {/* Área Principal: Gráfico + Microestructura Lateral */}
        <section className="grid grid-cols-1 xl:grid-cols-12 gap-4">
          <div className="xl:col-span-8 space-y-2">
            {loading && !candlesData ? (
              <div className="h-[520px] rounded-xl border border-slate-800 bg-[#0a0e13] flex items-center justify-center text-xs font-mono text-slate-400">
                Cargando velas y series históricas...
              </div>
            ) : (
              <TradingCandlesChart
                candles={candlesData?.candles ?? []}
                ema9={candlesData?.ema9 ?? []}
                ema21={candlesData?.ema21 ?? []}
                rsi14={candlesData?.rsi14 ?? []}
                bcvSeries={candlesData?.bcv_series ?? []}
                band={null}
                side={side}
                chartMode={chartMode}
                showEma={showTechMode}
                showRsi={showTechMode}
                unitSuffix={unitSuffix}
              />
            )}

            {candlesData?.warnings && candlesData.warnings.length > 0 && (
              <div className="rounded-lg border border-amber-500/25 bg-amber-500/5 px-3.5 py-2 text-[11px] text-amber-300/90 space-y-0.5">
                {candlesData.warnings.map((w, i) => (
                  <div key={i}>• {w}</div>
                ))}
              </div>
            )}
          </div>

          {/* Columna Derecha: Tasa Real para tu Monto + Liquidez Disponible */}
          <aside className="xl:col-span-4 space-y-3">
            {/* Tasa Promedio Real por Monto */}
            <div className="rounded-xl border border-slate-800/80 bg-[#101419] p-4 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-bold text-slate-100">
                  Tasa Real para {fmtNum(ticketVes, 0)} Bs
                </h2>
                <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded">
                  PROMEDIO PONDERADO
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div className="rounded-lg border border-slate-800 bg-[#0a0e13] p-3">
                  <div className="text-[11px] text-slate-400">Al Vender USDT</div>
                  <div className="mt-1 text-base font-mono font-bold text-emerald-400 tabular-nums">
                    {analytics?.vwap_sell.vwap_price ? `${fmtNum(analytics.vwap_sell.vwap_price)} Bs` : "—"}
                  </div>
                  <div className="mt-1 text-[10px] font-mono text-slate-400 tabular-nums">
                    1er anuncio: {fmtNum(analytics?.vwap_sell.best_price)} Bs
                  </div>
                  <div
                    className={`mt-1 text-[10px] font-mono tabular-nums ${
                      analytics?.vwap_sell.top_price_covers_ticket
                        ? "text-emerald-400"
                        : analytics?.vwap_sell.fillable
                        ? "text-amber-300"
                        : "text-rose-400"
                    }`}
                  >
                    {!analytics
                      ? "—"
                      : !analytics.vwap_sell.fillable
                      ? `Solo cubre ${fmtNum(analytics.vwap_sell.covered_ves, 0)} Bs`
                      : analytics.vwap_sell.top_price_covers_ticket
                      ? "Cubre con 1 anuncio"
                      : `${analytics.vwap_sell.ads_needed} anuncios · dif ${fmtNum(analytics.vwap_sell.slippage_pct)}%`}
                  </div>
                </div>

                <div className="rounded-lg border border-slate-800 bg-[#0a0e13] p-3">
                  <div className="text-[11px] text-slate-400">Al Comprar USDT</div>
                  <div className="mt-1 text-base font-mono font-bold text-sky-400 tabular-nums">
                    {analytics?.vwap_buy.vwap_price ? `${fmtNum(analytics.vwap_buy.vwap_price)} Bs` : "—"}
                  </div>
                  <div className="mt-1 text-[10px] font-mono text-slate-400 tabular-nums">
                    1er anuncio: {fmtNum(analytics?.vwap_buy.best_price)} Bs
                  </div>
                  <div
                    className={`mt-1 text-[10px] font-mono tabular-nums ${
                      analytics?.vwap_buy.top_price_covers_ticket
                        ? "text-emerald-400"
                        : analytics?.vwap_buy.fillable
                        ? "text-amber-300"
                        : "text-rose-400"
                    }`}
                  >
                    {!analytics
                      ? "—"
                      : !analytics.vwap_buy.fillable
                      ? `Solo cubre ${fmtNum(analytics.vwap_buy.covered_ves, 0)} Bs`
                      : analytics.vwap_buy.top_price_covers_ticket
                      ? "Cubre con 1 anuncio"
                      : `${analytics.vwap_buy.ads_needed} anuncios · dif ${fmtNum(analytics.vwap_buy.slippage_pct)}%`}
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Un anuncio en 1er lugar suele tener poco saldo. Este cálculo promedia los anuncios reales necesarios hasta llenar tus {fmtNum(ticketVes, 0)} Bs.
              </p>
            </div>

            {/* Conteo de Órdenes / Anuncios Compra vs Venta por Banco */}
            <div className="rounded-xl border border-slate-800/80 bg-[#101419] p-4 space-y-3">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div>
                  <h2 className="text-sm font-bold text-slate-100">
                    Órdenes Compra vs Venta
                  </h2>
                  <div className="text-[11px] font-mono text-amber-300/90 mt-0.5">
                    Banco: {analytics?.order_flow?.bank_filter || (bank === "*" ? "Todos" : bank)}
                  </div>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-200 tabular-nums">
                  {((analytics?.order_flow?.total_buy_ads ?? 0) + (analytics?.order_flow?.total_sell_ads ?? 0)).toLocaleString("es-VE")} activos
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div className="rounded-lg border border-sky-500/25 bg-sky-500/5 p-3">
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                    <span>COMPRA (Oferta)</span>
                    <span className="text-sky-400 font-bold">
                      {analytics?.order_flow ? `${analytics.order_flow.buy_ads_share_pct.toFixed(0)}%` : "—"}
                    </span>
                  </div>
                  <div className="mt-1 text-xl font-mono font-bold text-sky-400 tabular-nums">
                    {analytics?.order_flow ? analytics.order_flow.total_buy_ads.toLocaleString("es-VE") : "—"}
                  </div>
                  <div className="mt-0.5 text-[10px] font-mono text-slate-400 tabular-nums">
                    {analytics?.order_flow
                      ? `${analytics.order_flow.buy_merchants_count} verif. · ${analytics.order_flow.buy_month_orders_sum.toLocaleString("es-VE")} órds/mes`
                      : "—"}
                  </div>
                </div>

                <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-3">
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                    <span>VENTA (Demanda)</span>
                    <span className="text-emerald-400 font-bold">
                      {analytics?.order_flow ? `${analytics.order_flow.sell_ads_share_pct.toFixed(0)}%` : "—"}
                    </span>
                  </div>
                  <div className="mt-1 text-xl font-mono font-bold text-emerald-400 tabular-nums">
                    {analytics?.order_flow ? analytics.order_flow.total_sell_ads.toLocaleString("es-VE") : "—"}
                  </div>
                  <div className="mt-0.5 text-[10px] font-mono text-slate-400 tabular-nums">
                    {analytics?.order_flow
                      ? `${analytics.order_flow.sell_merchants_count} verif. · ${analytics.order_flow.sell_month_orders_sum.toLocaleString("es-VE")} órds/mes`
                      : "—"}
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="h-2.5 w-full rounded-full bg-slate-800 overflow-hidden flex">
                  <div
                    className="h-full bg-sky-400/85 transition-all"
                    style={{
                      width: `${analytics?.order_flow?.buy_ads_share_pct ?? 50}%`,
                    }}
                  />
                  <div
                    className="h-full bg-emerald-400/85 transition-all"
                    style={{
                      width: `${analytics?.order_flow?.sell_ads_share_pct ?? 50}%`,
                    }}
                  />
                </div>
                <div className="text-[11px] font-mono text-slate-300">
                  {analytics?.order_flow?.pressure_label || "Consultando comportamiento del libro..."}
                </div>
              </div>
            </div>

            {/* Dinero Disponible en el Libro */}
            <div className="rounded-xl border border-slate-800/80 bg-[#101419] p-4 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-bold text-slate-100">Dinero en el Libro</h2>
                <span
                  className={`text-[11px] font-mono font-semibold ${
                    imbalancePct > 10
                      ? "text-emerald-400"
                      : imbalancePct < -10
                      ? "text-rose-400"
                      : "text-slate-300"
                  }`}
                >
                  {imbalancePct > 10
                    ? `+${imbalancePct}% más compradores`
                    : imbalancePct < -10
                    ? `+${Math.abs(imbalancePct)}% más vendedores`
                    : "Libro equilibrado"}
                </span>
              </div>

              {analytics?.liquidity_alert.detected && (
                <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-[11px] text-rose-300">
                  Alerta de liquidez baja: volumen actual al {analytics.liquidity_alert.ratio_pct}% respecto a las últimas 2 horas.
                </div>
              )}

              <div className="space-y-1.5">
                <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden flex">
                  <div
                    className={`h-full transition-all ${
                      imbalancePct < -10
                        ? "bg-rose-500/80"
                        : imbalancePct > 10
                        ? "bg-emerald-500/80"
                        : "bg-amber-500/80"
                    }`}
                    style={{
                      width: `${Math.max(10, Math.min(90, 50 + imbalancePct / 2))}%`,
                    }}
                  />
                </div>
                <div className="flex justify-between text-[10px] font-mono text-slate-500">
                  <span>Más vendiendo</span>
                  <span>Equilibrio</span>
                  <span>Más comprando</span>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-[11px] font-mono tabular-nums">
                  <thead>
                    <tr className="text-slate-500 border-b border-slate-800">
                      <th className="py-1.5 text-left font-medium">Tramo</th>
                      <th className="py-1.5 text-right font-medium">Vendiendo (Compra)</th>
                      <th className="py-1.5 text-right font-medium">Comprando (Venta)</th>
                      <th
                        title="Porcentaje que concentra el anuncio #1 dentro de ese tramo"
                        className="py-1.5 text-right font-medium"
                      >
                        Líder #1
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-200">
                    {(
                      [
                        { label: "Top 5", b: analytics?.depth_summary.top5 },
                        { label: "Top 10", b: analytics?.depth_summary.top10 },
                        { label: "Top 20", b: analytics?.depth_summary.top20 },
                      ] as const
                    ).map((row) => (
                      <tr key={row.label}>
                        <td className="py-1.5 text-slate-300 font-semibold">{row.label}</td>
                        <td className="py-1.5 text-right text-sky-400">
                          {row.b ? fmtNum(row.b.buy_usdt, 0) : "—"}
                        </td>
                        <td className="py-1.5 text-right text-emerald-400">
                          {row.b ? fmtNum(row.b.sell_usdt, 0) : "—"}
                        </td>
                        <td className="py-1.5 text-right text-slate-400">
                          {row.b ? `${row.b.top1_share_pct.toFixed(0)}%` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </aside>
        </section>

        {/* Desglose en Vivo por Banco */}
        <section className="rounded-xl border border-slate-800/80 bg-[#101419] p-4 space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-bold text-slate-100">
                Tasas y Liquidez por Banco (Hora Actual)
              </h2>
              <p className="text-[11px] text-slate-400">
                Haz clic en cualquier banco para ver su gráfica individual y calcular cuánto te cuesta operar allí.
              </p>
            </div>
            {bank !== "*" && (
              <button
                type="button"
                onClick={() => setBank("*")}
                className="text-xs text-amber-400 hover:underline font-mono"
              >
                Limpiar filtro ({bank})
              </button>
            )}
          </div>

          {/* Vista en tarjetas para móvil sin recorte ni solapamiento */}
          <div className="md:hidden space-y-2">
            {(analytics?.banks_snapshot ?? []).length === 0 ? (
              <div className="py-4 text-center text-xs font-mono text-slate-500">
                Sin desglose bancario activo todavía.
              </div>
            ) : (
              analytics?.banks_snapshot.map((row) => (
                <button
                  key={`mob-${row.bank}`}
                  type="button"
                  onClick={() => {
                    setBank(row.bank);
                    setSide("bank");
                  }}
                  className={`w-full text-left p-3 rounded-lg border transition-colors ${
                    bank === row.bank
                      ? "border-amber-500/50 bg-amber-500/10"
                      : "border-slate-800 bg-[#0a0e13]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-xs font-bold text-slate-100 truncate">
                      {row.bank}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 tabular-nums shrink-0">
                      C:{row.buy_ads_count ?? 0} · V:{row.sell_ads_count ?? 0} · {fmtNum(row.vol_buy + row.vol_sell, 0)} U
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[11px] font-mono tabular-nums">
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase">Vendes</div>
                      <div className="text-emerald-400 font-semibold">{fmtNum(row.sell_best)} Bs</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-500 uppercase">Techo 1h</div>
                      <div className="text-amber-400 font-semibold">
                        {row.sustained_high_pc ? `${fmtNum(row.sustained_high_pc)} Bs` : "—"}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[9px] text-slate-500 uppercase">Compras</div>
                      <div className="text-sky-400 font-semibold">{fmtNum(row.buy_best)} Bs</div>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="hidden md:block overflow-x-auto">
            <table className="w-full min-w-[640px] text-xs font-mono tabular-nums">
              <thead>
                <tr className="text-slate-400 border-b border-slate-800 whitespace-nowrap">
                  <th className="py-2 pr-3 text-left font-medium">Banco / Método</th>
                  <th className="py-2 px-2 text-right font-medium">Si vendes USDT</th>
                  <th className="py-2 px-2 text-right font-medium">Promedio Venta</th>
                  <th
                    title="Precio más alto confirmado en al menos 2 lecturas seguidas dentro de la hora (sin picos falsos)"
                    className="py-2 px-2 text-right font-medium"
                  >
                    Techo firme (1h)
                  </th>
                  <th className="py-2 px-2 text-right font-medium">Si compras USDT</th>
                  <th className="py-2 px-2 text-right font-medium">Anuncios (C / V)</th>
                  <th className="py-2 pl-2 text-right font-medium">Liquidez USDT</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {(analytics?.banks_snapshot ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-4 text-center text-slate-500">
                      Sin desglose bancario activo todavía.
                    </td>
                  </tr>
                ) : (
                  analytics?.banks_snapshot.map((row) => (
                    <tr
                      key={row.bank}
                      onClick={() => {
                        setBank(row.bank);
                        setSide("bank");
                      }}
                      className={`cursor-pointer transition-colors hover:bg-slate-800/40 whitespace-nowrap ${
                        bank === row.bank ? "bg-amber-500/10" : ""
                      }`}
                    >
                      <td className="py-2 pr-3 font-sans font-semibold text-slate-200">{row.bank}</td>
                      <td className="py-2 px-2 text-right text-emerald-400">{fmtNum(row.sell_best)} Bs</td>
                      <td className="py-2 px-2 text-right text-slate-300">{fmtNum(row.sell_avg)} Bs</td>
                      <td className="py-2 px-2 text-right text-amber-400">
                        {row.sustained_high_pc ? `${fmtNum(row.sustained_high_pc)} Bs` : "—"}
                      </td>
                      <td className="py-2 px-2 text-right text-sky-400">{fmtNum(row.buy_best)} Bs</td>
                      <td className="py-2 px-2 text-right">
                        <span className="text-sky-400">{row.buy_ads_count ?? 0}</span>
                        <span className="text-slate-600"> / </span>
                        <span className="text-emerald-400">{row.sell_ads_count ?? 0}</span>
                      </td>
                      <td className="py-2 pl-2 text-right text-slate-300">
                        {fmtNum(row.vol_buy + row.vol_sell, 0)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
