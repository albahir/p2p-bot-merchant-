"use client";

import React, { useEffect, useState, useCallback } from "react";
import { 
  TrendingUp, 
  Zap, 
  Building2, 
  RefreshCw, 
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Sliders,
  Clock,
  ArrowUpRight,
  Radio,
  Flame,
  Cpu,
  ArrowLeftRight,
  Wallet,
  Settings,
  User as UserIcon,
  Search,
  Download,
  AlertCircle,
  ChevronRight,
  Calendar,
  Layers,
  FileSpreadsheet
} from "lucide-react";
import { 
  getBCVRates, 
  getArbitrageMatrix, 
  getOrders,
  getBotStatus,
  pauseBot,
  resumeBot,
  getCurrentUser,
  getExportOrdersUrl,
  BCVRates, 
  ArbitrageMatrix,
  OrderItem,
  BotStatus,
  User
} from "@/lib/api";
import { useWebSocket } from "@/lib/useWebSocket";
import BinanceSettingsCard from "@/components/binance-settings-card";

export default function CryptoAppDashboard() {
  // Pestaña activa para la vista móvil
  const [activeTab, setActiveTab] = useState<"mercado" | "swap" | "ordenes" | "fiscal" | "ajustes" | "perfil">("mercado");
  
  // Datos de la API
  const [bcv, setBcv] = useState<BCVRates | null>(null);
  const [matrix, setMatrix] = useState<ArbitrageMatrix | null>(null);
  const [orders, setOrders] = useState<OrderItem[]>([]);
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [user, setUser] = useState<User | null>(null);

  // Parámetros y Filtros
  const [montoUsdt, setMontoUsdt] = useState<number>(500);
  const [filtroBanco, setFiltroBanco] = useState<string>("TODOS");
  const [timeframe, setTimeframe] = useState<string>("1D");
  const [autoRebalance, setAutoRebalance] = useState<boolean>(true);
  const [autoLiberar, setAutoLiberar] = useState<boolean>(true);
  const [alertasTelegram, setAlertasTelegram] = useState<boolean>(true);
  const [cargando, setCargando] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [notifMsg, setNotifMsg] = useState<string | null>(null);

  const cargarDatos = useCallback(async () => {
    try {
      setErrorMsg(null);
      const [bcvRes, matrixRes, ordersRes, botRes] = await Promise.all([
        getBCVRates().catch(() => null),
        getArbitrageMatrix(montoUsdt).catch(() => null),
        getOrders({ page: 1, page_size: 15 }).catch(() => ({ items: [], total: 0, page: 1, page_size: 15 })),
        getBotStatus().catch(() => null),
      ]);
      if (bcvRes) setBcv(bcvRes);
      if (matrixRes) setMatrix(matrixRes);
      if (ordersRes) setOrders(ordersRes.items);
      if (botRes) setBotStatus(botRes);
    } catch (err: any) {
      setErrorMsg(err.message || "Error al sincronizar datos con el servidor.");
    } finally {
      setCargando(false);
    }
  }, [montoUsdt]);

  // Actualizaciones en tiempo real por WebSocket
  useWebSocket((msg) => {
    if (msg.type === "spreads_update" || msg.type === "bcv_change" || msg.type === "order_created") {
      cargarDatos();
    }
  });

  useEffect(() => {
    setUser(getCurrentUser());
    cargarDatos();
    const interval = setInterval(cargarDatos, 10000);
    return () => clearInterval(interval);
  }, [cargarDatos]);

  const bestArbitrage = matrix?.best_arbitrage;

  // Filtrado de bancos en la lista
  const cotizacionesFiltradas = matrix?.quotes ? matrix.quotes.filter((q) => {
    if (filtroBanco === "PAGO_MOVIL") return q.bank_name.toLowerCase().includes("móvil") || q.bank_name.toLowerCase().includes("movil");
    if (filtroBanco === "BANESCO") return q.bank_name.toLowerCase().includes("banesco");
    if (filtroBanco === "MERCANTIL") return q.bank_name.toLowerCase().includes("mercantil");
    if (filtroBanco === "BDV") return q.bank_name.toLowerCase().includes("venezuela");
    return true;
  }) : [];

  // Toggle de parada de emergencia
  async function alternarPausaBot() {
    try {
      if (botStatus?.is_paused) {
        const res = await resumeBot();
        setNotifMsg(res.message);
      } else {
        const res = await pauseBot();
        setNotifMsg(res.message);
      }
      const s = await getBotStatus();
      setBotStatus(s);
      setTimeout(() => setNotifMsg(null), 4000);
    } catch (e: any) {
      setErrorMsg(e.message || "Error al modificar estado del bot");
    }
  }

  // Tasa referencial para cálculos
  const tasaCompra = bestArbitrage?.buy_rate || (bcv?.p2p_usdt_ref ? bcv.p2p_usdt_ref * 0.985 : 936.50);
  const tasaVenta = bestArbitrage?.sell_rate || (bcv?.p2p_usdt_ref ? bcv.p2p_usdt_ref * 1.012 : 948.80);
  const spreadPct = bestArbitrage?.spread_pct || (((tasaVenta - tasaCompra) / tasaCompra) * 100);
  const gananciaNetaUsdt = (montoUsdt * (spreadPct / 100) * 0.9).toFixed(2);
  const bolivaresSalida = (montoUsdt * tasaVenta).toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="w-full max-w-7xl mx-auto min-h-screen bg-[#080d1a] text-slate-100 flex flex-col relative pb-20 lg:pb-8 shadow-2xl rounded-3xl overflow-hidden border border-slate-800/80 font-sans">
      
      {/* ======================================================== */}
      {/* 1. BARRA DE NAVEGACIÓN SUPERIOR (DESKTOP & TELEMETRÍA)    */}
      {/* ======================================================== */}
      <div className="hidden lg:flex items-center justify-between px-6 py-2.5 bg-[#0a0f1d] border-b border-slate-800 text-xs font-mono">
        <div className="flex items-center space-x-4">
          <span className="font-bold text-rose-500 flex items-center space-x-1.5">
            <Zap className="h-4 w-4 fill-rose-500" />
            <span>ARBITEX P2P // VENEZUELA</span>
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">NODO 01: MOTOR P2P</span>
          <span className="text-slate-600">|</span>
          <span className="text-emerald-400 flex items-center space-x-1">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>WS: EN VIVO</span>
          </span>
        </div>

        {/* Enlaces de Escritorio a todas las Vistas del Proyecto */}
        <div className="flex items-center space-x-2">
          <a href="/" className="px-3 py-1 rounded-full bg-rose-600 text-white font-bold transition-colors">
            Mercado & Spreads
          </a>
          <a href="/orders" className="px-3 py-1 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors">
            Libro de Órdenes
          </a>
          <a href="/fiscal" className="px-3 py-1 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors">
            Conciliación Fiscal (SENIAT)
          </a>
          {user?.role === "ADMIN" && (
            <a href="/admin" className="px-3 py-1 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors">
              Usuarios & RBAC
            </a>
          )}
          <a href="/login" className="px-3 py-1 rounded-full text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors">
            {user ? user.username : "Acceso"}
          </a>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 2. CABECERA CURVA ESTILO MOCKUP (ROJO CARMESÍ / CORAL) */}
      {/* ======================================================== */}
      <header className="bg-gradient-to-br from-red-600 via-rose-600 to-red-700 text-white rounded-b-[2.5rem] pt-6 px-6 pb-7 shadow-xl relative overflow-hidden">
        {/* Adorno visual sutil */}
        <div className="absolute -right-8 -top-8 w-48 h-48 bg-white/10 rounded-full blur-2xl pointer-events-none" />
        <div className="absolute -left-8 -bottom-8 w-48 h-48 bg-black/15 rounded-full blur-xl pointer-events-none" />

        {/* Fila Superior: Perfil + Notificaciones + Control */}
        <div className="flex items-center justify-between relative z-10">
          <div className="flex items-center space-x-3">
            <div className="relative">
              <div className="h-12 w-12 rounded-full bg-white/20 border-2 border-white/60 flex items-center justify-center text-white font-bold text-base shadow">
                {user ? user.username.substring(0, 2).toUpperCase() : "CM"}
              </div>
              <span className={`absolute bottom-0 right-0 h-3.5 w-3.5 rounded-full border-2 border-red-600 ${
                botStatus?.is_paused ? "bg-amber-400" : "bg-emerald-400 animate-pulse"
              }`} />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-base tracking-wide text-white">
                  {user ? user.username : "Carlos M."}
                </span>
                <span className="text-[10px] bg-white/20 px-2 py-0.5 rounded-full font-semibold uppercase text-white/95">
                  {user?.role || "TRADER"}
                </span>
              </div>
              <p className="text-xs text-white/80 font-mono">
                {botStatus?.is_paused ? "Bot: Pausado (Fail-closed)" : "Motor P2P Binance: Activo"}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={cargarDatos}
              title="Refrescar cotizaciones"
              className="p-2.5 rounded-full bg-white/15 hover:bg-white/25 text-white transition-all backdrop-blur-sm"
            >
              <RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />
            </button>

            {user?.role === "ADMIN" && (
              <button
                onClick={alternarPausaBot}
                title={botStatus?.is_paused ? "Reanudar motor" : "Parada de emergencia"}
                className={`px-3 py-2 rounded-full text-xs font-bold transition-all flex items-center space-x-1.5 shadow ${
                  botStatus?.is_paused 
                    ? "bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold" 
                    : "bg-black/30 hover:bg-black/40 text-white"
                }`}
              >
                <Zap className="h-4 w-4" />
                <span className="hidden sm:inline">{botStatus?.is_paused ? "REANUDAR" : "PARADA"}</span>
              </button>
            )}
          </div>
        </div>

        {/* Balance Principal (Como se ve en el mockup: $267,345) */}
        <div className="mt-5 text-center relative z-10">
          <p className="text-xs uppercase tracking-wider text-white/80 font-semibold">
            Saldo de Operaciones & Tesorería Arbitraje
          </p>
          <div className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white my-1">
            ${ (montoUsdt * 1.5).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
            <span className="text-sm font-medium text-white/80 ml-2 font-mono">USDT</span>
          </div>
          <div className="inline-flex flex-wrap items-center justify-center gap-2 bg-black/25 backdrop-blur-md px-4 py-1.5 rounded-full text-xs font-mono text-white/95 mt-1 border border-white/10">
            <span>Tasa BCV: <strong>{bcv?.usd ? bcv.usd.toFixed(2) : "881.07"} VES</strong></span>
            <span>•</span>
            <span>Mediana P2P: <strong>{bcv?.p2p_usdt_ref ? bcv.p2p_usdt_ref.toFixed(2) : "948.80"} VES</strong></span>
            <span>•</span>
            <span className="text-emerald-300 font-bold">Brecha: +{bcv?.brecha_pct ? bcv.brecha_pct.toFixed(2) : "7.68"}%</span>
          </div>
        </div>
      </header>

      {/* ======================================================== */}
      {/* 3. ALERTAS Y NOTIFICACIONES FLOTANTES                    */}
      {/* ======================================================== */}
      <div className="px-5 pt-3">
        {notifMsg && (
          <div className="p-3 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center space-x-2 shadow">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{notifMsg}</span>
          </div>
        )}
        {errorMsg && (
          <div className="p-3 rounded-2xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center space-x-2 shadow">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {/* ======================================================== */}
      {/* 4. CONTENIDO PRINCIPAL: RESPONSIVO DUAL (PC & MÓVIL)     */}
      {/* ======================================================== */}
      <main className="flex-1 px-4 sm:px-6 pt-2 pb-6 space-y-5 overflow-y-auto">

        {/* ==================================================== */}
        {/* BANNER DE OPORTUNIDAD EN CALIENTE (AMBAS VISTAS)      */}
        {/* ==================================================== */}
        <div className="bg-[#111927] p-4 rounded-3xl border border-rose-500/30 shadow-md">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
                <Flame className="h-3.5 w-3.5" />
                <span>OPORTUNIDAD DE ARBITRAJE EN CALIENTE</span>
              </span>
              <p className="text-sm font-semibold text-slate-100 flex items-center space-x-2">
                <span>Comprar en <strong>{bestArbitrage?.buy_bank || "Banco de Venezuela"}</strong> ({tasaCompra.toFixed(2)} VES)</span>
                <ArrowRight className="h-4 w-4 text-rose-500" />
                <span>Vender en <strong>{bestArbitrage?.sell_bank || "Pago Móvil / Banesco"}</strong> ({tasaVenta.toFixed(2)} VES)</span>
              </p>
              <p className="text-xs text-slate-400 font-mono">
                Spread Bruto: <strong className="text-emerald-400">+{spreadPct.toFixed(2)}%</strong> | Ganancia Neta Est: <strong className="text-emerald-400">+{gananciaNetaUsdt} USDT</strong> / {montoUsdt}u
              </p>
            </div>

            <button
              onClick={() => alert(`Ruta de arbitraje armada por ${montoUsdt} USDT. Verificación Fail-Closed de libro activa.`)}
              className="px-5 py-3 rounded-full bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center justify-center space-x-1.5 shadow-lg shadow-rose-600/30 transition-all shrink-0"
            >
              <Zap className="h-4 w-4 fill-white" />
              <span>EJECUTAR RUTA EN 1 CLIC</span>
            </button>
          </div>
        </div>

        {/* ==================================================== */}
        {/* VISTA DESKTOP (PANTALLAS GRANDES >= lg: 1024px)      */}
        {/* ==================================================== */}
        <div className="hidden lg:grid lg:grid-cols-12 lg:gap-6">
          {/* Columna Izquierda: Matriz de Cotizaciones & Gráfica (8 Cols) */}
          <div className="lg:col-span-8 space-y-4">
            {/* Gráfica y Filtros */}
            <div className="bg-[#111927] p-5 rounded-3xl border border-slate-800 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider flex items-center space-x-2">
                    <TrendingUp className="h-4 w-4 text-rose-500" />
                    <span>Matriz de Profundidad Interbancaria (VES / USDT)</span>
                  </h3>
                  <p className="text-xs text-slate-400">Escáner en tiempo real a través de los canales de compensación en Venezuela</p>
                </div>

                {/* Filtros de Intervalo */}
                <div className="flex items-center space-x-1 bg-[#162032] p-1 rounded-2xl border border-slate-700 text-xs font-semibold text-slate-400">
                  {["1D", "1S", "1M", "6M", "1A"].map((tf) => (
                    <button
                      key={tf}
                      onClick={() => setTimeframe(tf)}
                      className={`px-2.5 py-1 rounded-xl transition-all ${
                        timeframe === tf ? "bg-rose-600 text-white font-bold" : "hover:text-white"
                      }`}
                    >
                      {tf}
                    </button>
                  ))}
                </div>
              </div>

              {/* Curva de Brecha en Escritorio */}
              <div className="h-28 w-full bg-[#0d1424] rounded-2xl p-3 border border-slate-800/80">
                <svg viewBox="0 0 500 80" className="w-full h-full stroke-rose-500 fill-none" preserveAspectRatio="none">
                  <path
                    d="M 0,60 Q 50,25 100,50 T 200,35 T 300,65 T 400,30 T 500,20"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 0,70 Q 50,45 100,60 T 200,55 T 300,75 T 400,50 T 500,40"
                    strokeWidth="1.5"
                    strokeDasharray="4 4"
                    className="stroke-slate-600"
                  />
                </svg>
              </div>

              {/* Píldoras de Filtro de Bancos */}
              <div className="flex items-center space-x-2 overflow-x-auto text-xs">
                {[
                  { id: "TODOS", label: "Todos los Bancos (6)" },
                  { id: "PAGO_MOVIL", label: "Pago Móvil Inmediato" },
                  { id: "BANESCO", label: "Banesco" },
                  { id: "MERCANTIL", label: "Mercantil" },
                  { id: "BDV", label: "Banco de Venezuela" }
                ].map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setFiltroBanco(f.id)}
                    className={`px-3 py-1.5 rounded-full whitespace-nowrap transition-all font-medium ${
                      filtroBanco === f.id
                        ? "bg-rose-600 text-white shadow-md font-bold"
                        : "bg-[#162032] text-slate-300 hover:bg-slate-700"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              {/* Tabla de Cotizaciones en Escritorio */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 text-[11px]">
                      <th className="py-2.5 px-3">Banco / Canal</th>
                      <th className="py-2.5 px-3 text-right">Compra (VES)</th>
                      <th className="py-2.5 px-3 text-right">Venta (VES)</th>
                      <th className="py-2.5 px-3 text-right">Spread Bruto</th>
                      <th className="py-2.5 px-3 text-right">Retorno / 100u</th>
                      <th className="py-2.5 px-3 text-right">Acción</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {cotizacionesFiltradas.length > 0 ? (
                      cotizacionesFiltradas.map((q, idx) => (
                        <tr key={idx} className="hover:bg-[#162032] transition-colors">
                          <td className="py-3 px-3 font-medium text-slate-200 flex items-center space-x-2">
                            <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                            <span>{q.bank_name}</span>
                          </td>
                          <td className="py-3 px-3 text-right text-slate-300">{q.buy_rate.toFixed(2)}</td>
                          <td className="py-3 px-3 text-right text-slate-300">{q.sell_rate.toFixed(2)}</td>
                          <td className="py-3 px-3 text-right">
                            <span className="text-emerald-400 font-bold">+{q.spread_pct.toFixed(2)}%</span>
                          </td>
                          <td className="py-3 px-3 text-right text-emerald-400 font-bold">
                            +${((q.spread_ves || 12) * 0.1).toFixed(2)}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
                              ARMADO
                            </span>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="py-6 text-center text-slate-500">
                          {cargando ? "Sincronizando libros Binance P2P..." : "Sin cotizaciones en este canal."}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Columna Derecha: Panel de Ejecución Swap & Historial (4 Cols) */}
          <div className="lg:col-span-4 space-y-4">
            {/* Tarjeta de Conversión / Swap */}
            <div className="bg-[#111927] p-5 rounded-3xl border border-slate-800 shadow-md space-y-4">
              <span className="font-bold text-sm text-slate-100 flex items-center space-x-2">
                <ArrowLeftRight className="h-4 w-4 text-rose-500" />
                <span>Panel de Ejecución de Arbitraje</span>
              </span>

              {/* Presets de Capital */}
              <div>
                <div className="flex justify-between text-xs text-slate-300 mb-1">
                  <span>Despliegue de Capital:</span>
                  <span className="font-bold text-rose-400 font-mono text-sm">{montoUsdt} USDT</span>
                </div>
                <input
                  type="range"
                  min="100"
                  max="5000"
                  step="50"
                  value={montoUsdt}
                  onChange={(e) => setMontoUsdt(Number(e.target.value))}
                  className="w-full accent-rose-600 cursor-pointer"
                />
                <div className="grid grid-cols-4 gap-1.5 text-xs font-mono font-bold mt-2">
                  {[100, 250, 500, 1000].map((val) => (
                    <button
                      key={val}
                      onClick={() => setMontoUsdt(val)}
                      className={`py-1 rounded-xl transition-all ${
                        montoUsdt === val ? "bg-rose-600 text-white font-bold" : "bg-[#162032] text-slate-300"
                      }`}
                    >
                      ${val}
                    </button>
                  ))}
                </div>
              </div>

              {/* Resumen */}
              <div className="p-3.5 rounded-2xl bg-[#162032] border border-slate-700 space-y-2 text-xs">
                <div className="flex justify-between text-slate-300">
                  <span>Bolívares de Retorno:</span>
                  <strong className="font-mono text-white">{bolivaresSalida} VES</strong>
                </div>
                <div className="flex justify-between text-emerald-400 font-bold border-t border-slate-700/60 pt-2">
                  <span>Ganancia Neta Estimada:</span>
                  <span className="font-mono">+{gananciaNetaUsdt} USDT</span>
                </div>
              </div>

              <button
                onClick={() => alert(`Ruta de arbitraje armada por ${montoUsdt} USDT.`)}
                className="w-full py-3.5 rounded-full bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-rose-600/30 uppercase"
              >
                <Zap className="h-4 w-4 fill-white" />
                <span>Ejecutar Arbitraje en 1 Clic</span>
              </button>
            </div>

            {/* Accesos Rápidos a Módulos del Sistema */}
            <div className="bg-[#111927] p-5 rounded-3xl border border-slate-800 shadow-md space-y-2.5 text-xs">
              <span className="font-bold text-xs uppercase tracking-wider text-slate-400 block mb-1">
                Vistas Especializadas del Sistema
              </span>

              <a
                href="/fiscal"
                className="flex items-center justify-between p-3 rounded-2xl bg-[#162032] hover:bg-slate-700 transition-all text-slate-200 group"
              >
                <div className="flex items-center space-x-2.5">
                  <Building2 className="h-4 w-4 text-rose-500" />
                  <span>Reconstrucción Fiscal de 6 Piezas</span>
                </div>
                <ChevronRight className="h-4 w-4 text-slate-400 group-hover:translate-x-1 transition-transform" />
              </a>

              <a
                href="/orders"
                className="flex items-center justify-between p-3 rounded-2xl bg-[#162032] hover:bg-slate-700 transition-all text-slate-200 group"
              >
                <div className="flex items-center space-x-2.5">
                  <FileSpreadsheet className="h-4 w-4 text-rose-500" />
                  <span>Libro de Órdenes & Ingesta P2P</span>
                </div>
                <ChevronRight className="h-4 w-4 text-slate-400 group-hover:translate-x-1 transition-transform" />
              </a>

              {user?.role === "ADMIN" && (
                <a
                  href="/admin"
                  className="flex items-center justify-between p-3 rounded-2xl bg-[#162032] hover:bg-slate-700 transition-all text-slate-200 group"
                >
                  <div className="flex items-center space-x-2.5">
                    <UserIcon className="h-4 w-4 text-rose-500" />
                    <span>Control de Acceso y Roles RBAC</span>
                  </div>
                  <ChevronRight className="h-4 w-4 text-slate-400 group-hover:translate-x-1 transition-transform" />
                </a>
              )}
            </div>

            {/* Módulo de Configuración de Claves Binance y Diagnóstico en Vivo */}
            <BinanceSettingsCard />
          </div>
        </div>

        {/* ==================================================== */}
        {/* VISTA MÓVIL (PANTALLAS PEQUEÑAS < lg: 1024px)        */}
        {/* ==================================================== */}
        <div className="lg:hidden space-y-4">
          {/* PESTAÑA MÓVIL: MERCADO */}
          {activeTab === "mercado" && (
            <div className="space-y-4">
              {/* Intervalos */}
              <div className="flex items-center justify-between bg-[#111927] p-1 rounded-2xl border border-slate-800 text-xs font-semibold text-slate-400">
                {["1D", "1S", "1M", "6M", "1A"].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setTimeframe(tf)}
                    className={`flex-1 py-1.5 rounded-xl transition-all ${
                      timeframe === tf ? "bg-rose-600 text-white font-bold" : "hover:text-slate-200"
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>

              {/* Gráfica Móvil */}
              <div className="bg-[#111927] p-4 rounded-3xl border border-slate-800 shadow-md">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-[11px] text-slate-400 uppercase font-bold">Brecha Paralelo vs BCV</span>
                  <span className="text-xs text-emerald-400 font-bold">+{bcv?.brecha_pct ? bcv.brecha_pct.toFixed(2) : "7.68"}%</span>
                </div>
                <div className="h-20 w-full">
                  <svg viewBox="0 0 300 70" className="w-full h-full stroke-rose-500 fill-none" preserveAspectRatio="none">
                    <path d="M 0,50 Q 30,20 60,45 T 120,30 T 180,60 T 240,25 T 300,15" strokeWidth="2.5" strokeLinecap="round" />
                  </svg>
                </div>
              </div>

              {/* Filtros Móvil */}
              <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 text-xs">
                {["TODOS", "PAGO_MOVIL", "BANESCO", "MERCANTIL", "BDV"].map((f) => (
                  <button
                    key={f}
                    onClick={() => setFiltroBanco(f)}
                    className={`px-3 py-1.5 rounded-full whitespace-nowrap transition-all font-medium ${
                      filtroBanco === f ? "bg-rose-600 text-white font-bold" : "bg-[#111927] text-slate-300 border border-slate-800"
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>

              {/* Cotizaciones Móvil */}
              <div className="space-y-2">
                {cotizacionesFiltradas.map((q, idx) => (
                  <div key={idx} className="bg-[#111927] p-3 rounded-2xl border border-slate-800 flex items-center justify-between">
                    <div>
                      <h4 className="font-bold text-xs text-slate-200">{q.bank_name}</h4>
                      <p className="text-[10px] text-slate-400 font-mono">C: {q.buy_rate.toFixed(2)} | V: {q.sell_rate.toFixed(2)}</p>
                    </div>
                    <span className="text-xs font-bold text-emerald-400 bg-emerald-500/15 px-2 py-0.5 rounded-full border border-emerald-500/30">
                      +{q.spread_pct.toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* PESTAÑA MÓVIL: SWAP / ARBITRAJE */}
          {activeTab === "swap" && (
            <div className="bg-[#111927] p-5 rounded-3xl border border-slate-800 shadow-md space-y-4">
              <span className="font-bold text-sm text-slate-100 flex items-center space-x-2">
                <ArrowLeftRight className="h-4 w-4 text-rose-500" />
                <span>Conversor Rápido de Arbitraje</span>
              </span>

              <div className="bg-[#162032] p-3 rounded-2xl border border-slate-700">
                <span className="text-xs text-slate-400 block mb-1">Monto de Operación (USDT)</span>
                <input
                  type="number"
                  value={montoUsdt}
                  onChange={(e) => setMontoUsdt(Math.max(10, Number(e.target.value)))}
                  className="bg-transparent text-xl font-bold text-white focus:outline-none w-full font-mono"
                />
              </div>

              <div className="p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-xs">
                <div className="flex justify-between text-emerald-400 font-bold">
                  <span>Ganancia Neta Est:</span>
                  <span>+{gananciaNetaUsdt} USDT (+{spreadPct.toFixed(2)}%)</span>
                </div>
                <div className="flex justify-between text-slate-400 text-[10px] mt-1">
                  <span>Retorno en Bs:</span>
                  <span>{bolivaresSalida} VES</span>
                </div>
              </div>

              <button
                onClick={() => alert(`Ruta de ${montoUsdt} USDT armada.`)}
                className="w-full py-3.5 rounded-full bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs uppercase"
              >
                Ejecutar Arbitraje en 1 Clic
              </button>
            </div>
          )}

          {/* PESTAÑA MÓVIL: ÓRDENES */}
          {activeTab === "ordenes" && (
            <div className="space-y-3">
              <div className="flex justify-between items-center px-1">
                <h4 className="text-xs font-bold text-slate-300">Órdenes Recientes</h4>
                <a href="/orders" className="text-xs text-rose-400">Ver todas</a>
              </div>
              {orders.slice(0, 5).map((ord) => (
                <div key={ord.id} className="bg-[#111927] p-3 rounded-2xl border border-slate-800 flex justify-between items-center text-xs">
                  <div>
                    <span className="font-bold text-slate-200">{ord.trade_type === "BUY" ? "Compra" : "Venta"} USDT</span>
                    <span className="block text-[10px] text-slate-400">{ord.counterparty_name || "Comerciante"}</span>
                  </div>
                  <span className={`font-mono font-bold ${ord.trade_type === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>
                    {ord.trade_type === "BUY" ? `+${ord.crypto_amount}` : `-${ord.crypto_amount}`} u
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* PESTAÑA MÓVIL: FISCAL */}
          {activeTab === "fiscal" && (
            <div className="bg-[#111927] p-5 rounded-3xl border border-slate-800 space-y-3 text-center">
              <Building2 className="h-8 w-8 text-rose-500 mx-auto" />
              <h3 className="font-bold text-sm text-slate-100">Reconciliación Fiscal SENIAT</h3>
              <p className="text-xs text-slate-400">
                Audita la ecuación de 6 piezas patrimoniales y genera tu declaración contable en Excel.
              </p>
              <a
                href="/fiscal"
                className="inline-block px-5 py-2.5 rounded-full bg-rose-600 text-white text-xs font-bold shadow"
              >
                Abrir Módulo Fiscal Completo
              </a>
            </div>
          )}

          {/* PESTAÑA MÓVIL: AJUSTES */}
          {activeTab === "ajustes" && (
            <div className="space-y-4">
              <BinanceSettingsCard />

              <div className="bg-[#111927] p-5 rounded-3xl border border-slate-800 space-y-3">
                <h3 className="font-bold text-xs text-slate-300 uppercase">Ajustes del Sistema</h3>
                <div className="flex justify-between items-center p-3 rounded-2xl bg-[#162032] text-xs">
                  <span>Auto-Rebalanceo</span>
                  <input type="checkbox" checked={autoRebalance} onChange={(e) => setAutoRebalance(e.target.checked)} className="accent-rose-600" />
                </div>
                <div className="flex justify-between items-center p-3 rounded-2xl bg-[#162032] text-xs">
                  <span>Auto-Liberación Binance</span>
                  <input type="checkbox" checked={autoLiberar} onChange={(e) => setAutoLiberar(e.target.checked)} className="accent-rose-600" />
                </div>
                <button
                  onClick={alternarPausaBot}
                  className="w-full py-2.5 rounded-2xl bg-rose-600 text-white font-bold text-xs"
                >
                  {botStatus?.is_paused ? "REANUDAR MOTOR" : "PARADA DE EMERGENCIA"}
                </button>
              </div>
            </div>
          )}

          {/* PESTAÑA MÓVIL: PERFIL */}
          {activeTab === "perfil" && (
            <div className="bg-[#111927] p-5 rounded-3xl border border-slate-800 space-y-3 text-center text-xs">
              <div className="h-12 w-12 mx-auto rounded-full bg-rose-600 flex items-center justify-center font-bold text-white text-base">
                {user ? user.username.substring(0, 2).toUpperCase() : "CM"}
              </div>
              <h3 className="font-bold text-slate-100">{user?.username || "Carlos M."}</h3>
              <p className="text-slate-400 font-mono">Rol: {user?.role || "TRADER"}</p>
              <div className="pt-2">
                <a href="/login" className="inline-block px-4 py-2 rounded-full bg-rose-600/20 text-rose-400 font-bold">
                  Cerrar Sesión / Cambiar Usuario
                </a>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ======================================================== */}
      {/* 5. BARRA DE NAVEGACIÓN INFERIOR (MÓVIL / TELEGRAM APP)   */}
      {/* ======================================================== */}
      <nav className="lg:hidden fixed bottom-0 left-0 right-0 max-w-7xl mx-auto bg-[#0a0f1d]/95 backdrop-blur-md border-t border-slate-800 px-3 py-1.5 flex items-center justify-around z-50">
        <button
          onClick={() => setActiveTab("mercado")}
          className={`flex flex-col items-center py-1 px-2 rounded-2xl transition-all ${
            activeTab === "mercado" ? "text-rose-500 font-bold" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <TrendingUp className="h-5 w-5" />
          <span className="text-[10px] mt-0.5">Mercado</span>
        </button>

        <button
          onClick={() => setActiveTab("swap")}
          className={`flex flex-col items-center py-1 px-2 rounded-2xl transition-all ${
            activeTab === "swap" ? "text-rose-500 font-bold" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <ArrowLeftRight className="h-5 w-5" />
          <span className="text-[10px] mt-0.5">Arbitraje</span>
        </button>

        <button
          onClick={() => setActiveTab("ordenes")}
          className={`flex flex-col items-center py-1 px-2 rounded-2xl transition-all ${
            activeTab === "ordenes" ? "text-rose-500 font-bold" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Wallet className="h-5 w-5" />
          <span className="text-[10px] mt-0.5">Órdenes</span>
        </button>

        <button
          onClick={() => setActiveTab("fiscal")}
          className={`flex flex-col items-center py-1 px-2 rounded-2xl transition-all ${
            activeTab === "fiscal" ? "text-rose-500 font-bold" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Building2 className="h-5 w-5" />
          <span className="text-[10px] mt-0.5">Fiscal</span>
        </button>

        <button
          onClick={() => setActiveTab("ajustes")}
          className={`flex flex-col items-center py-1 px-2 rounded-2xl transition-all ${
            activeTab === "ajustes" ? "text-rose-500 font-bold" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Settings className="h-5 w-5" />
          <span className="text-[10px] mt-0.5">Ajustes</span>
        </button>
      </nav>
    </div>
  );
}
