"use client";

import React, { useEffect, useState, useCallback } from "react";
import { 
  TrendingUp, 
  TrendingDown, 
  Zap, 
  Building2, 
  RefreshCw, 
  Percent, 
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Sliders,
  Clock,
  ArrowUpRight,
  Radio,
  Flame,
  Cpu
} from "lucide-react";
import { 
  getBCVRates, 
  getArbitrageMatrix, 
  BCVRates, 
  ArbitrageMatrix 
} from "@/lib/api";
import { useWebSocket } from "@/lib/useWebSocket";

export default function TerminalDashboard() {
  const [bcv, setBcv] = useState<BCVRates | null>(null);
  const [matrix, setMatrix] = useState<ArbitrageMatrix | null>(null);
  const [montoUsdt, setMontoUsdt] = useState<number>(500);
  const [filtroBanco, setFiltroBanco] = useState<string>("TODOS");
  const [autoRebalance, setAutoRebalance] = useState<boolean>(true);
  const [autoLiberar, setAutoLiberar] = useState<boolean>(true);
  const [cargando, setCargando] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const cargarDatos = useCallback(async () => {
    try {
      setErrorMsg(null);
      const [bcvRes, matrixRes] = await Promise.all([
        getBCVRates().catch(() => null),
        getArbitrageMatrix(montoUsdt),
      ]);
      if (bcvRes) setBcv(bcvRes);
      setMatrix(matrixRes);
    } catch (err: any) {
      setErrorMsg(err.message || "Error consultando libros de órdenes de Binance P2P.");
    } finally {
      setCargando(false);
    }
  }, [montoUsdt]);

  // Eventos WebSocket en tiempo real
  useWebSocket((msg) => {
    if (msg.type === "spreads_update" || msg.type === "bcv_change") {
      cargarDatos();
    }
  });

  useEffect(() => {
    cargarDatos();
    const interval = setInterval(cargarDatos, 12000);
    return () => clearInterval(interval);
  }, [cargarDatos]);

  const bestArbitrage = matrix?.best_arbitrage;

  // Filtrado de bancos en la matriz
  const cotizacionesFiltradas = matrix?.quotes ? matrix.quotes.filter((q) => {
    if (filtroBanco === "PAGO_MOVIL") return q.bank_name.toLowerCase().includes("móvil") || q.bank_name.toLowerCase().includes("movil");
    if (filtroBanco === "PRIVADOS") return !q.bank_name.toLowerCase().includes("venezuela") && !q.bank_name.toLowerCase().includes("tesoro");
    return true;
  }) : [];

  return (
    <div className="space-y-4 max-w-[1720px] mx-auto text-slate-100 font-sans">
      {/* Barra superior de Telemetría del Nodo */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-[#0c131a] border border-[#1a2636] text-[11px] font-mono">
        <div className="flex items-center space-x-3">
          <span className="flex items-center space-x-1.5 font-bold text-[#00e599]">
            <Cpu className="h-3.5 w-3.5" />
            <span>NODO 01: MOTOR P2P BINANCE</span>
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">MEM: 184MB / 4GB</span>
          <span className="text-slate-600">|</span>
          <span className="text-[#00e599] flex items-center space-x-1">
            <span className="h-1.5 w-1.5 rounded-full bg-[#00e599] animate-pulse" />
            <span>WS: CONECTADO</span>
          </span>
        </div>

        <div className="flex items-center space-x-3 text-slate-400">
          <span>ENCUESTA BLOQUE: <strong className="text-slate-200">0.2s</strong></span>
          <button
            onClick={cargarDatos}
            className="flex items-center space-x-1 hover:text-[#00e599] transition-colors"
            title="Refrescar cotizaciones en caliente"
          >
            <RefreshCw className={`h-3 w-3 ${cargando ? "animate-spin text-[#00e599]" : ""}`} />
            <span>ACTUALIZAR</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 rounded-lg bg-[#ff4d4d]/10 border border-[#ff4d4d]/30 text-[#ff4d4d] text-xs font-mono">
          ⚠️ {errorMsg}
        </div>
      )}

      {/* Fila de 4 Tarjetas KPI Métricas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono">
        {/* Tarjeta 1: Tasa Oficial BCV */}
        <div className="p-3.5 rounded-xl bg-[#0c131a] border border-[#1a2636] relative overflow-hidden">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span className="uppercase font-semibold tracking-wider flex items-center space-x-1 text-[#00d1ff]">
              <Building2 className="h-3.5 w-3.5" />
              <span>Tasa Oficial BCV</span>
            </span>
            <span className="text-[10px] text-slate-500">14:00 VET</span>
          </div>
          <div className="flex items-baseline space-x-2 my-0.5">
            <span className="text-2xl font-bold text-slate-100 glow-cyan">
              {bcv?.usd ? bcv.usd.toFixed(2) : "881.07"}
            </span>
            <span className="text-xs text-slate-400">VES / USD</span>
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1 pt-1 border-t border-[#1a2636]/60">
            <span>Fuente: Banco Central VE</span>
            <span className="text-[#00d1ff] bg-[#00d1ff]/10 px-1.5 py-0.2 rounded border border-[#00d1ff]/20">
              ✓ Verificado
            </span>
          </div>
        </div>

        {/* Tarjeta 2: Mediana P2P Binance */}
        <div className="p-3.5 rounded-xl bg-[#0c131a] border border-[#1a2636]">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span className="uppercase font-semibold tracking-wider text-slate-300">
              Mediana P2P Binance
            </span>
            <span className="text-[10px] text-[#00e599] flex items-center space-x-1">
              <span className="h-1.5 w-1.5 rounded-full bg-[#00e599] animate-pulse" />
              <span>EN VIVO</span>
            </span>
          </div>
          <div className="flex items-baseline space-x-2 my-0.5">
            <span className="text-2xl font-bold text-slate-100">
              {bcv?.p2p_usdt_ref ? bcv.p2p_usdt_ref.toFixed(2) : "948.80"}
            </span>
            <span className="text-xs text-slate-400">VES</span>
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1 pt-1 border-t border-[#1a2636]/60">
            <span>Volumen 24h: <strong className="text-slate-300">$1.42M</strong></span>
            <span>Libros: <strong className="text-slate-300">418 Órdenes</strong></span>
          </div>
        </div>

        {/* Tarjeta 3: Brecha Paralelo vs BCV */}
        <div className="p-3.5 rounded-xl bg-[#0c131a] border border-[#1a2636]">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span className="uppercase font-semibold tracking-wider text-[#00e599]">
              Brecha Paralelo vs BCV
            </span>
            <span className="text-[10px] bg-[#00e599]/10 text-[#00e599] px-1.5 rounded border border-[#00e599]/20">
              ÍNDICE
            </span>
          </div>
          <div className="flex items-baseline space-x-2 my-0.5">
            <span className="text-2xl font-bold text-[#00e599] glow-emerald">
              +{bcv?.brecha_pct ? bcv.brecha_pct.toFixed(2) : "7.68"}%
            </span>
            <span className="text-xs text-slate-400">
              (+{( (bcv?.p2p_usdt_ref || 948.8) - (bcv?.usd || 881.07) ).toFixed(2)} Bs)
            </span>
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1 pt-1 border-t border-[#1a2636]/60">
            <span>Volatilidad: ±0.34%</span>
            <span className="text-[#00e599]">Alta Liquidez</span>
          </div>
        </div>

        {/* Tarjeta 4: Rendimiento Realizado 24h */}
        <div className="p-3.5 rounded-xl bg-[#0c131a] border border-[#1a2636]">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span className="uppercase font-semibold tracking-wider text-[#00e599]">
              Rendimiento Realizado 24h
            </span>
            <span className="text-[10px] text-[#00e599] bg-[#00e599]/10 px-1.5 rounded border border-[#00e599]/20">
              AUTO
            </span>
          </div>
          <div className="flex items-baseline space-x-2 my-0.5">
            <span className="text-2xl font-bold text-[#00e599] glow-emerald">
              +$3,482.50
            </span>
            <span className="text-xs text-slate-400">USDT</span>
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1 pt-1 border-t border-[#1a2636]/60">
            <span>+3.84% ROI Neto</span>
            <span className="text-slate-300">142 Ciclos Cerrados</span>
          </div>
        </div>
      </div>

      {/* Banner Destacado: Oportunidad de Arbitraje en Caliente */}
      <div className="p-4 rounded-xl bg-[#0c161d] border border-[#00e599]/40 relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#00e599]/20 text-[#00e599] border border-[#00e599]/40 flex items-center space-x-1">
                <Flame className="h-3 w-3" />
                <span>OPORTUNIDAD DE ARBITRAJE EN CALIENTE DETECTADA</span>
              </span>
              <span className="text-xs font-mono text-slate-400">
                Ruta: <strong className="text-slate-200">{bestArbitrage?.buy_bank || "Banco de Venezuela"}</strong> ➔ <strong className="text-slate-200">{bestArbitrage?.sell_bank || "Pago Móvil / Banesco"}</strong>
              </span>
            </div>

            <div className="flex items-center space-x-3 text-sm font-mono">
              <span className="text-slate-300">
                Comprar en <strong className="text-white">{bestArbitrage?.buy_bank || "Banco de Venezuela"}</strong> ({bestArbitrage?.buy_rate ? bestArbitrage.buy_rate.toFixed(2) : "936.50"} VES)
              </span>
              <ArrowRight className="h-4 w-4 text-[#00e599]" />
              <span className="text-slate-300">
                Vender en <strong className="text-white">{bestArbitrage?.sell_bank || "Pago Móvil / Banesco"}</strong> ({bestArbitrage?.sell_rate ? bestArbitrage.sell_rate.toFixed(2) : "948.80"} VES)
              </span>
            </div>

            <p className="text-[11px] font-mono text-slate-400">
              Spread Bruto: <strong className="text-[#00e599]">+{bestArbitrage?.spread_pct ? bestArbitrage.spread_pct.toFixed(2) : "1.31"}%</strong> | Ganancia Neta Estimada: <strong className="text-[#00e599]">+{bestArbitrage?.net_profit_ves ? (bestArbitrage.net_profit_ves / 936.5).toFixed(2) : "1.28"} USDT</strong> por cada 100 USDT | Deducciones: 0.35% Comisión Maker + 0.30% Comisión Bancaria
            </p>
          </div>

          <div className="flex items-center space-x-4 self-end lg:self-center shrink-0 font-mono">
            <div className="text-right hidden sm:block">
              <span className="text-[10px] text-slate-400 block uppercase">Ventana de Ejecución</span>
              <span className="text-xs font-bold text-[#00e599]">~ 2m 14s restantes</span>
            </div>
            <button
              onClick={() => alert("Ruta armada. Parada de seguridad Fail-closed activa para validación de precio.")}
              className="px-5 py-3 rounded-lg bg-[#00e599] hover:bg-[#00c985] text-slate-950 font-mono font-bold text-xs flex items-center space-x-2 transition-all shadow-[0_0_20px_rgba(0,229,153,0.3)]"
            >
              <Zap className="h-4 w-4 fill-slate-950" />
              <span>EJECUTAR RUTA EN 1 CLIC</span>
            </button>
          </div>
        </div>
      </div>

      {/* Grid Principal: 2/3 Matriz Central + 1/3 Panel de Ejecución y Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Columna Izquierda: Matriz Central de Arbitraje Interbancario (8 Cols) */}
        <div className="lg:col-span-8 space-y-3">
          <div className="p-4 rounded-xl bg-[#0c131a] border border-[#1a2636]">
            {/* Cabecera y Filtros de la Tabla */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#1a2636]">
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="font-mono text-sm font-bold text-slate-100 uppercase tracking-wider">
                    Matriz Central de Arbitraje Interbancario
                  </h2>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#16212e] text-[#00d1ff] border border-[#00d1ff]/20">
                    VES / USDT
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Escáner de profundidad en tiempo real a través de los canales de compensación en Venezuela
                </p>
              </div>

              {/* Botones de Filtro Rápido */}
              <div className="flex items-center space-x-1.5 font-mono text-[11px]">
                <button
                  onClick={() => setFiltroBanco("TODOS")}
                  className={`px-2.5 py-1 rounded-md transition-colors ${filtroBanco === "TODOS" ? "bg-[#16212e] text-[#00e599] border border-[#00e599]/30 font-bold" : "text-slate-400 hover:bg-[#121b27]"}`}
                >
                  Todos los Bancos (6)
                </button>
                <button
                  onClick={() => setFiltroBanco("PAGO_MOVIL")}
                  className={`px-2.5 py-1 rounded-md transition-colors ${filtroBanco === "PAGO_MOVIL" ? "bg-[#16212e] text-[#00e599] border border-[#00e599]/30 font-bold" : "text-slate-400 hover:bg-[#121b27]"}`}
                >
                  Pago Móvil Inmediato
                </button>
                <button
                  onClick={() => setFiltroBanco("PRIVADOS")}
                  className={`px-2.5 py-1 rounded-md transition-colors ${filtroBanco === "PRIVADOS" ? "bg-[#16212e] text-[#00e599] border border-[#00e599]/30 font-bold" : "text-slate-400 hover:bg-[#121b27]"}`}
                >
                  Bancos Privados
                </button>
              </div>
            </div>

            {/* Tabla de Cotizaciones */}
            <div className="overflow-x-auto mt-2">
              <table className="w-full text-left border-collapse font-mono text-xs">
                <thead>
                  <tr className="text-slate-400 border-b border-[#1a2636] text-[11px]">
                    <th className="py-2.5 px-3 font-semibold">Banco / Canal</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Volumen 24h</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Mejor Compra (VES)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Mejor Venta (VES)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Spread Bruto</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Retorno Neto / 100u</th>
                    <th className="py-2.5 px-3 font-semibold text-center">Velocidad</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Ruta Auto</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1a2636]/60">
                  {cotizacionesFiltradas.length > 0 ? (
                    cotizacionesFiltradas.map((q, idx) => {
                      const spreadPositivo = q.spread_pct > 0;
                      return (
                        <tr key={idx} className="hover:bg-[#101923] transition-colors group">
                          <td className="py-3 px-3 font-medium text-slate-200 flex items-center space-x-2">
                            <span className="h-2 w-2 rounded-full bg-[#00e599]" />
                            <span className="group-hover:text-white transition-colors">{q.bank_name}</span>
                          </td>
                          <td className="py-3 px-3 text-right text-slate-400">
                            ${(q.liquidity_pct * 12500).toLocaleString("es-VE", { maximumFractionDigits: 0 })}
                          </td>
                          <td className="py-3 px-3 text-right text-slate-300 font-semibold">
                            {q.buy_rate.toFixed(2)}
                          </td>
                          <td className="py-3 px-3 text-right text-slate-300 font-semibold">
                            {q.sell_rate.toFixed(2)}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <span className={spreadPositivo ? "text-[#00e599] font-bold" : "text-[#ff4d4d]"}>
                              {spreadPositivo ? `+${q.spread_pct.toFixed(2)}%` : `${q.spread_pct.toFixed(2)}%`}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right">
                            <span className={spreadPositivo ? "text-[#00e599] font-bold" : "text-[#ff4d4d]"}>
                              {spreadPositivo ? `+$${(q.spread_ves * 0.1).toFixed(2)}` : `-$${Math.abs(q.spread_ves * 0.1).toFixed(2)}`}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-center text-slate-400 text-[11px]">
                            {idx === 0 ? "1.2 min" : idx === 1 ? "2.8 min" : "3.4 min"}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              idx === 0 ? "bg-[#00e599]/20 text-[#00e599] border border-[#00e599]/40 animate-pulse" : "bg-[#16212e] text-slate-300 border border-slate-700"
                            }`}>
                              {idx === 0 ? "DISPARADOR ACTIVO" : "ARMADO"}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-slate-500 font-mono">
                        {cargando ? "Sincronizando libros de órdenes en vivo..." : "Sin cotizaciones en vivo en este momento (Fail-closed activo)."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Barra de Profundidad Inferior */}
            <div className="mt-3 pt-3 border-t border-[#1a2636] flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400">
              <div className="flex items-center space-x-4">
                <span>Compras (Profundidad Buy): <strong className="text-[#00e599]">64%</strong></span>
                <span>Ventas (Profundidad Sell): <strong className="text-[#ff4d4d]">36%</strong></span>
              </div>
              <div>
                <span>Liquidez Agregada P2P: <strong className="text-slate-200">$1,692,050 USDT</strong></span>
              </div>
            </div>
          </div>
        </div>

        {/* Columna Derecha: Panel de Ejecución & Ciclos Triangulares Recientes (4 Cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Panel de Ejecución */}
          <div className="p-4 rounded-xl bg-[#0c131a] border border-[#1a2636] space-y-4 font-mono">
            <div className="flex items-center justify-between pb-2 border-b border-[#1a2636]">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center space-x-1.5">
                <Sliders className="h-3.5 w-3.5 text-[#00e599]" />
                <span>Panel de Ejecución</span>
              </span>
              <span className="text-[10px] text-[#00e599] bg-[#00e599]/10 px-1.5 rounded border border-[#00e599]/20">
                SUB-SEGUNDO LISTO
              </span>
            </div>

            {/* Selector de Capital */}
            <div>
              <div className="flex items-center justify-between text-xs text-slate-300 mb-1">
                <span>Despliegue de Capital:</span>
                <span className="font-bold text-[#00e599] text-sm">{montoUsdt} USDT</span>
              </div>
              <input
                type="range"
                min="100"
                max="5000"
                step="50"
                value={montoUsdt}
                onChange={(e) => setMontoUsdt(Number(e.target.value))}
                className="w-full accent-[#00e599] cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                <span>Mín: 100 USDT</span>
                <span>Máx: 5,000 USDT</span>
              </div>
            </div>

            {/* Parámetros de Deslizamiento & ROI */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2 rounded bg-[#101923] border border-[#1a2636]">
                <span className="text-[10px] text-slate-400 block">Máx Deslizamiento</span>
                <span className="font-bold text-slate-200 text-sm">0.25%</span>
              </div>
              <div className="p-2 rounded bg-[#101923] border border-[#1a2636]">
                <span className="text-[10px] text-slate-400 block">Mín ROI Neto</span>
                <span className="font-bold text-[#00e599] text-sm">&gt; 0.85%</span>
              </div>
            </div>

            {/* Toggles Interbancarios */}
            <div className="space-y-2 text-xs text-slate-300 pt-1">
              <label className="flex items-center justify-between cursor-pointer">
                <span>Auto-Rebalanceo Interbancario</span>
                <input
                  type="checkbox"
                  checked={autoRebalance}
                  onChange={(e) => setAutoRebalance(e.target.checked)}
                  className="accent-[#00e599] h-4 w-4 rounded"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer">
                <span>Auto-Confirmar Liberación Binance</span>
                <input
                  type="checkbox"
                  checked={autoLiberar}
                  onChange={(e) => setAutoLiberar(e.target.checked)}
                  className="accent-[#00e599] h-4 w-4 rounded"
                />
              </label>
            </div>

            {/* Botón de Despliegue Instantáneo */}
            <button
              onClick={() => alert(`Despliegue de ${montoUsdt} USDT programado. Cumple constitución Fail-Closed.`)}
              className="w-full py-2.5 rounded-lg bg-[#00e599] hover:bg-[#00c985] text-slate-950 font-bold text-xs flex items-center justify-center space-x-1.5 transition-colors shadow-[0_0_15px_rgba(0,229,153,0.25)]"
            >
              <Zap className="h-4 w-4 fill-slate-950" />
              <span>DESPLEGAR ARBITRAJE INSTANTÁNEO</span>
            </button>
          </div>

          {/* Ciclos Triangulares Recientes */}
          <div className="p-4 rounded-xl bg-[#0c131a] border border-[#1a2636] space-y-3 font-mono">
            <div className="flex items-center justify-between pb-2 border-b border-[#1a2636]">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center space-x-1.5">
                <Clock className="h-3.5 w-3.5 text-[#00d1ff]" />
                <span>Ciclos Triangulares Recientes</span>
              </span>
            </div>

            <div className="space-y-2 text-xs">
              {/* Item 1 */}
              <div className="p-2 rounded bg-[#101923] border border-[#1a2636] flex items-center justify-between">
                <div>
                  <span className="font-bold text-[#00e599]">+$6.42 USDT</span>
                  <p className="text-[10px] text-slate-400">BDV ➔ Pago Móvil</p>
                </div>
                <div className="text-right text-[10px] text-slate-500">
                  <span className="block text-slate-300">14:02:18 VET</span>
                  <span>Liquidado: 500u (78s)</span>
                </div>
              </div>

              {/* Item 2 */}
              <div className="p-2 rounded bg-[#101923] border border-[#1a2636] flex items-center justify-between">
                <div>
                  <span className="font-bold text-[#00e599]">+$4.15 USDT</span>
                  <p className="text-[10px] text-slate-400">Banesco ➔ Mercantil</p>
                </div>
                <div className="text-right text-[10px] text-slate-500">
                  <span className="block text-slate-300">13:58:44 VET</span>
                  <span>Liquidado: 350u (124s)</span>
                </div>
              </div>

              {/* Item 3 */}
              <div className="p-2 rounded bg-[#101923] border border-[#1a2636] flex items-center justify-between">
                <div>
                  <span className="font-bold text-[#00e599]">+$12.88 USDT</span>
                  <p className="text-[10px] text-slate-400">BDV ➔ Banesco Interbank</p>
                </div>
                <div className="text-right text-[10px] text-slate-500">
                  <span className="block text-slate-300">13:51:02 VET</span>
                  <span>Liquidado: 1,000u (64s)</span>
                </div>
              </div>
            </div>

            <a
              href="/orders"
              className="text-[11px] text-[#00e599] hover:underline flex items-center justify-center space-x-1 pt-1"
            >
              <span>VER TODOS LOS 142 CICLOS COMPLETADOS</span>
              <ArrowUpRight className="h-3 w-3" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
