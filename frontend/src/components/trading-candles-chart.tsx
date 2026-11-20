"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ColorType,
  CrosshairMode,
  IChartApi,
  ISeriesApi,
  LineStyle,
  LogicalRange,
  MouseEventParams,
  Time,
  UTCTimestamp,
  createChart,
} from "lightweight-charts";
import {
  MarketCandlePoint,
  MarketLinePoint,
  MarketPercentileBand,
  MarketSideMode,
} from "@/lib/api";

export type ChartVisualMode = "candles" | "line" | "area";

interface TradingCandlesChartProps {
  candles: MarketCandlePoint[];
  ema9: MarketLinePoint[];
  ema21: MarketLinePoint[];
  rsi14: MarketLinePoint[];
  bcvSeries: MarketLinePoint[];
  band: MarketPercentileBand | null;
  side: MarketSideMode;
  chartMode: ChartVisualMode;
  showEma: boolean;
  showRsi: boolean;
  unitSuffix: string;
}

interface HoverOhlc {
  timeLabel: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
  rsi?: number | null;
  bcv?: number | null;
}

function formatVetTime(epochSec: number): string {
  try {
    const dt = new Date(epochSec * 1000);
    return new Intl.DateTimeFormat("es-VE", {
      timeZone: "America/Caracas",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(dt);
  } catch {
    return String(epochSec);
  }
}

export function TradingCandlesChart({
  candles,
  ema9,
  ema21,
  rsi14,
  bcvSeries,
  band,
  side,
  chartMode,
  showEma,
  showRsi,
  unitSuffix,
}: TradingCandlesChartProps) {
  const mainContainerRef = useRef<HTMLDivElement | null>(null);
  const rsiContainerRef = useRef<HTMLDivElement | null>(null);
  const mainChartRef = useRef<IChartApi | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);

  const latestHover = useMemo<HoverOhlc | null>(() => {
    if (!candles.length) return null;
    const last = candles[candles.length - 1];
    const lastRsi = rsi14.length ? rsi14[rsi14.length - 1]?.value ?? null : null;
    const lastBcv = bcvSeries.length ? bcvSeries[bcvSeries.length - 1]?.value ?? null : null;
    return {
      timeLabel: formatVetTime(last.time),
      open: last.open,
      high: last.high,
      low: last.low,
      close: last.close,
      volume: last.volume ?? null,
      rsi: lastRsi,
      bcv: lastBcv,
    };
  }, [candles, rsi14, bcvSeries]);

  const [hoverInfo, setHoverInfo] = useState<HoverOhlc | null>(latestHover);

  useEffect(() => {
    setHoverInfo(latestHover);
  }, [latestHover]);

  useEffect(() => {
    const mainEl = mainContainerRef.current;
    if (!mainEl) return;

    const candleByTime = new Map<number, MarketCandlePoint>();
    for (const c of candles) {
      candleByTime.set(c.time, c);
    }
    const rsiByTime = new Map<number, number | null>();
    for (const pt of rsi14) {
      rsiByTime.set(pt.time, pt.value);
    }
    const bcvByTime = new Map<number, number | null>();
    for (const pt of bcvSeries) {
      bcvByTime.set(pt.time, pt.value);
    }

    const baseChartOptions = {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0e13" },
        textColor: "#94a3b8",
        fontFamily: '"JetBrains Mono", "Inter", monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(30, 36, 48, 0.55)" },
        horzLines: { color: "rgba(30, 36, 48, 0.55)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "rgba(245, 158, 11, 0.45)", labelBackgroundColor: "#181f29" },
        horzLine: { color: "rgba(245, 158, 11, 0.45)", labelBackgroundColor: "#181f29" },
      },
      rightPriceScale: {
        borderColor: "#1e2430",
        scaleMargins: { top: 0.08, bottom: side === "evolucion" ? 0.08 : 0.22 },
      },
      timeScale: {
        borderColor: "#1e2430",
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 4,
      },
      localization: {
        timeFormatter: (time: Time) =>
          typeof time === "number" ? formatVetTime(time) : String(time),
        priceFormatter: (price: number) => `${price.toFixed(2)} ${unitSuffix}`,
      },
    };

    const mainChart = createChart(mainEl, {
      ...baseChartOptions,
      width: mainEl.clientWidth || 640,
      height: 390,
    });
    mainChartRef.current = mainChart;

    let primarySeries:
      | ISeriesApi<"Candlestick">
      | ISeriesApi<"Line">
      | ISeriesApi<"Area">;

    if (side === "evolucion") {
      const p2pLine = mainChart.addLineSeries({
        color: "#f59e0b",
        lineWidth: 2,
        title: "P2P Medio",
      });
      p2pLine.setData(
        candles.map((c) => ({ time: c.time as UTCTimestamp, value: c.close }))
      );

      const bcvLine = mainChart.addLineSeries({
        color: "#38bdf8",
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        title: "BCV Oficial",
      });
      bcvLine.setData(
        bcvSeries.map((pt) =>
          pt.value === null || pt.value === undefined
            ? { time: pt.time as UTCTimestamp }
            : { time: pt.time as UTCTimestamp, value: pt.value }
        )
      );
      primarySeries = p2pLine;
    } else {
      if (chartMode === "line") {
        const line = mainChart.addLineSeries({
          color: "#f59e0b",
          lineWidth: 2,
          title: side === "brecha" ? "Brecha %" : "P2P",
        });
        line.setData(
          candles.map((c) => ({ time: c.time as UTCTimestamp, value: c.close }))
        );
        primarySeries = line;
      } else if (chartMode === "area") {
        const area = mainChart.addAreaSeries({
          lineColor: "#f59e0b",
          topColor: "rgba(245, 158, 11, 0.30)",
          bottomColor: "rgba(245, 158, 11, 0.02)",
          lineWidth: 2,
          title: side === "brecha" ? "Brecha %" : "P2P",
        });
        area.setData(
          candles.map((c) => ({ time: c.time as UTCTimestamp, value: c.close }))
        );
        primarySeries = area;
      } else {
        const candleSeries = mainChart.addCandlestickSeries({
          upColor: "#10b981",
          downColor: "#ef4444",
          borderUpColor: "#10b981",
          borderDownColor: "#ef4444",
          wickUpColor: "#10b981",
          wickDownColor: "#ef4444",
        });
        candleSeries.setData(
          candles.map((c) => ({
            time: c.time as UTCTimestamp,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }))
        );
        primarySeries = candleSeries;
      }

      const hasVol = candles.some((c) => c.volume !== null && c.volume !== undefined && c.volume > 0);
      if (hasVol) {
        const volumeSeries = mainChart.addHistogramSeries({
          priceFormat: { type: "volume" },
          priceScaleId: "vol_scale",
          lastValueVisible: false,
          priceLineVisible: false,
        });
        mainChart.priceScale("vol_scale").applyOptions({
          scaleMargins: { top: 0.85, bottom: 0.0 },
        });
        volumeSeries.setData(
          candles.map((c) => ({
            time: c.time as UTCTimestamp,
            value: c.volume ?? 0,
            color:
              c.close >= c.open
                ? "rgba(16, 185, 129, 0.28)"
                : "rgba(239, 68, 68, 0.28)",
          }))
        );
      }

      if (showEma && ema9.length > 0) {
        const ema9Series = mainChart.addLineSeries({
          color: "#f59e0b",
          lineWidth: 1,
          title: "EMA 9",
          priceLineVisible: false,
          lastValueVisible: false,
        });
        ema9Series.setData(
          ema9
            .filter((p) => p.value !== null && p.value !== undefined)
            .map((p) => ({ time: p.time as UTCTimestamp, value: Number(p.value) }))
        );
      }
      if (showEma && ema21.length > 0) {
        const ema21Series = mainChart.addLineSeries({
          color: "#38bdf8",
          lineWidth: 1,
          title: "EMA 21",
          priceLineVisible: false,
          lastValueVisible: false,
        });
        ema21Series.setData(
          ema21
            .filter((p) => p.value !== null && p.value !== undefined)
            .map((p) => ({ time: p.time as UTCTimestamp, value: Number(p.value) }))
        );
      }

      if (band && candles.length > 0) {
        primarySeries.createPriceLine({
          price: band.ceiling,
          color: "rgba(16, 185, 129, 0.7)",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: "P95 Techo 90%",
        });
        primarySeries.createPriceLine({
          price: band.floor,
          color: "rgba(239, 68, 68, 0.7)",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: "P05 Piso 90%",
        });
      }
    }

    mainChart.timeScale().fitContent();

    let rsiChart: IChartApi | null = null;
    const rsiEl = rsiContainerRef.current;
    const hasEnoughForRsi = candles.length >= 15;
    const shouldRenderRsi = showRsi && side !== "evolucion" && rsiEl !== null && hasEnoughForRsi;

    if (shouldRenderRsi && rsiEl) {
      rsiChart = createChart(rsiEl, {
        ...baseChartOptions,
        width: rsiEl.clientWidth || 640,
        height: 135,
        rightPriceScale: {
          borderColor: "#1e2430",
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        localization: {
          timeFormatter: (time: Time) =>
            typeof time === "number" ? formatVetTime(time) : String(time),
          priceFormatter: (price: number) => price.toFixed(1),
        },
      });
      rsiChartRef.current = rsiChart;

      const rsiLine = rsiChart.addLineSeries({
        color: "#a78bfa",
        lineWidth: 2,
        title: "RSI 14",
        autoscaleInfoProvider: () => ({
          priceRange: { minValue: 10, maxValue: 90 },
        }),
      });
      rsiLine.setData(
        rsi14.map((pt) =>
          pt.value === null || pt.value === undefined
            ? { time: pt.time as UTCTimestamp }
            : { time: pt.time as UTCTimestamp, value: pt.value }
        )
      );
      rsiLine.createPriceLine({
        price: 70,
        color: "rgba(239, 68, 68, 0.5)",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        title: "70",
      });
      rsiLine.createPriceLine({
        price: 30,
        color: "rgba(16, 185, 129, 0.5)",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        title: "30",
      });
      rsiLine.createPriceLine({
        price: 50,
        color: "rgba(148, 163, 184, 0.25)",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: false,
        title: "",
      });
      rsiChart.timeScale().fitContent();
    } else {
      rsiChartRef.current = null;
    }

    let isSyncing = false;
    const syncMainToRsi = (range: LogicalRange | null) => {
      if (isSyncing || !range || !rsiChart) return;
      isSyncing = true;
      rsiChart.timeScale().setVisibleLogicalRange(range);
      isSyncing = false;
    };
    const syncRsiToMain = (range: LogicalRange | null) => {
      if (isSyncing || !range) return;
      isSyncing = true;
      mainChart.timeScale().setVisibleLogicalRange(range);
      isSyncing = false;
    };

    mainChart.timeScale().subscribeVisibleLogicalRangeChange(syncMainToRsi);
    if (rsiChart) {
      rsiChart.timeScale().subscribeVisibleLogicalRangeChange(syncRsiToMain);
    }

    const onCrosshairMove = (param: MouseEventParams<Time>) => {
      if (!param.time || typeof param.time !== "number") {
        setHoverInfo(latestHover);
        return;
      }
      const c = candleByTime.get(param.time);
      if (!c) return;
      setHoverInfo({
        timeLabel: formatVetTime(c.time),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume ?? null,
        rsi: rsiByTime.get(c.time) ?? null,
        bcv: bcvByTime.get(c.time) ?? null,
      });
    };
    mainChart.subscribeCrosshairMove(onCrosshairMove);

    const resizeObserver = new ResizeObserver(() => {
      if (mainEl) {
        mainChart.applyOptions({ width: mainEl.clientWidth });
      }
      if (rsiChart && rsiEl) {
        rsiChart.applyOptions({ width: rsiEl.clientWidth });
      }
    });
    resizeObserver.observe(mainEl);
    if (rsiEl) resizeObserver.observe(rsiEl);

    return () => {
      resizeObserver.disconnect();
      mainChart.unsubscribeCrosshairMove(onCrosshairMove);
      mainChart.timeScale().unsubscribeVisibleLogicalRangeChange(syncMainToRsi);
      if (rsiChart) {
        rsiChart.timeScale().unsubscribeVisibleLogicalRangeChange(syncRsiToMain);
        rsiChart.remove();
      }
      mainChart.remove();
      mainChartRef.current = null;
      rsiChartRef.current = null;
    };
  }, [candles, ema9, ema21, rsi14, bcvSeries, band, side, chartMode, showEma, showRsi, unitSuffix, latestHover]);

  const handleFitContent = () => {
    mainChartRef.current?.timeScale().fitContent();
    rsiChartRef.current?.timeScale().fitContent();
  };

  const handleScrollToPresent = () => {
    mainChartRef.current?.timeScale().scrollToRealTime();
    rsiChartRef.current?.timeScale().scrollToRealTime();
  };

  return (
    <div className="rounded-xl border border-slate-800/90 bg-[#0a0e13] overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 border-b border-slate-800/80 bg-[#101419]">
        {hoverInfo ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-mono tabular-nums">
            <span className="text-slate-400">{hoverInfo.timeLabel} VET</span>
            <span className="text-slate-300">
              Apertura: <strong className="text-slate-100">{hoverInfo.open.toFixed(2)}</strong>
            </span>
            <span className="text-slate-300">
              Máx: <strong className="text-emerald-400">{hoverInfo.high.toFixed(2)}</strong>
            </span>
            <span className="text-slate-300">
              Mín: <strong className="text-rose-400">{hoverInfo.low.toFixed(2)}</strong>
            </span>
            <span className="text-slate-300">
              Cierre: <strong className="text-amber-400">{hoverInfo.close.toFixed(2)} {unitSuffix}</strong>
            </span>
            {hoverInfo.volume !== null && hoverInfo.volume !== undefined && (
              <span className="text-slate-400">
                Volumen: <strong className="text-slate-200">{hoverInfo.volume.toFixed(0)} USDT</strong>
              </span>
            )}
            {hoverInfo.bcv !== null && hoverInfo.bcv !== undefined && side === "evolucion" && (
              <span className="text-sky-400">
                BCV: <strong>{hoverInfo.bcv.toFixed(2)} Bs</strong>
              </span>
            )}
            {hoverInfo.rsi !== null && hoverInfo.rsi !== undefined && side !== "evolucion" && (
              <span className="text-violet-400">
                Fuerza (RSI): <strong>{hoverInfo.rsi.toFixed(1)}</strong>
              </span>
            )}
          </div>
        ) : (
          <div className="text-[11px] font-mono text-slate-500">
            Esperando lecturas en vivo para dibujar las velas...
          </div>
        )}

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleFitContent}
            className="px-2.5 py-1 rounded-md border border-slate-700/80 bg-slate-900/80 hover:border-amber-500/60 text-[11px] font-medium text-slate-300 transition-colors"
          >
            Ver todo
          </button>
          <button
            type="button"
            onClick={handleScrollToPresent}
            className="px-2.5 py-1 rounded-md border border-slate-700/80 bg-slate-900/80 hover:border-amber-500/60 text-[11px] font-medium text-amber-400 transition-colors"
          >
            Ir al final
          </button>
        </div>
      </div>

      <div className="relative">
        <div ref={mainContainerRef} className="w-full h-[390px]" />
        {candles.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0a0e13]/85 text-center px-6">
            <span className="material-symbols-outlined text-amber-400 text-3xl mb-2">
              candlestick_chart
            </span>
            <p className="text-sm font-semibold text-slate-200">
              Aún no hay suficientes velas guardadas
            </p>
            <p className="text-xs text-slate-400 mt-1 max-w-md">
              Pulsa <strong>Capturar ahora</strong> arriba para guardar el primer dato de Binance P2P y BCV. Cada 2 minutos se añadirá una nueva lectura automática.
            </p>
          </div>
        )}
      </div>

      {showRsi && side !== "evolucion" && candles.length > 0 && (
        <div className="border-t border-slate-800/80">
          <div className="flex items-center justify-between px-3.5 py-1.5 bg-[#101419]/80 text-[11px] font-mono text-slate-400">
            <span>Fuerza compra/venta (RSI) · Abajo de 30 = barato / Arriba de 70 = sobrecalentado</span>
            <span className="text-violet-400">
              {candles.length >= 15 && hoverInfo?.rsi !== null && hoverInfo?.rsi !== undefined
                ? `Actual: ${hoverInfo.rsi.toFixed(1)}`
                : `${candles.length}/15 velas`}
            </span>
          </div>
          {candles.length >= 15 && <div ref={rsiContainerRef} className="w-full h-[135px]" />}
        </div>
      )}
    </div>
  );
}
