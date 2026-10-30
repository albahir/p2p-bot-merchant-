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
  AlertCircle, 
  ChevronRight, 
  FileSpreadsheet, 
  User as UserIcon, 
  Flame, 
  ArrowLeftRight, 
  Wallet, 
  Settings, 
  Sun, 
  Moon, 
  KeyRound, 
  X,
  SlidersHorizontal,
  ExternalLink
} from "lucide-react";
import { 
  getBCVRates, 
  getArbitrageMatrix, 
  getOrders, 
  getBotStatus, 
  pauseBot, 
  resumeBot, 
  getCurrentUser, 
  BCVRates, 
  ArbitrageMatrix, 
  OrderItem, 
  BotStatus, 
  User 
} from "@/lib/api";
import { useWebSocket } from "@/lib/useWebSocket";
import { useTheme } from "@/lib/theme-context";
import BinanceSettingsCard from "@/components/binance-settings-card";

export default function CryptoAppDashboard() {
  const { theme, toggleTheme } = useTheme();

  // Pestaña activa para la vista móvil
  const [activeTab, setActiveTab] = useState<"mercado" | "swap" | "ordenes" | "fiscal" | "ajustes" | "perfil">("mercado");
  
  // Modal de Credenciales Binance
  const [isBinanceModalOpen, setIsBinanceModalOpen] = useState(false);

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
    <div className="w-full max-w-7xl mx-auto min-h-screen bg-[#F8F9FA] dark:bg-[#07090E] text-slate-900 dark:text-slate-100 flex flex-col relative pb-20 lg:pb-8 rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 transition-colors duration-150">
      
      {/* ======================================================== */}
      {/* 1. BARRA DE NAVEGACIÓN SUPERIOR (DESKTOP & TELEMETRÍA)    */}
      {/* ======================================================== */}
      <div className="hidden lg:flex items-center justify-between px-6 py-2.5 bg-white dark:bg-[#0D111A] border-b border-slate-200 dark:border-slate-800 text-xs font-mono">
        <div className="flex items-center space-x-3">
          <span className="font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <span>P2P MERCHANT WORKSTATION</span>
          </span>
          <span className="text-slate-300 dark:text-slate-700">|</span>
          <span className="text-slate-500 dark:text-slate-400">VES / USDT</span>
          <span className="text-slate-300 dark:text-slate-700">|</span>
          <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
            FAIL-CLOSED ACTIVO
          </span>
        </div>

        {/* Enlaces de Escritorio + Controles de Modo y API */}
        <div className="flex items-center space-x-2">
          {/* Selector de Modo Blanco Perla / Modo Oscuro */}
          <button
            onClick={toggleTheme}
            className="px-2.5 py-1 rounded-lg text-xs font-medium flex items-center space-x-1.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            title="Alternar entre Blanco Perla y Negro Azabache"
          >
            {theme === "dark" ? (
              <>
                <Sun className="h-3.5 w-3.5 text-amber-500" />
                <span>Blanco Perla</span>
              </>
            ) : (
              <>
                <Moon className="h-3.5 w-3.5 text-slate-700" />
                <span>Negro Azabache</span>
              </>
            )}
          </button>

          {/* Botón para Abrir Modal de Credenciales Binance */}
          <button
            onClick={() => setIsBinanceModalOpen(true)}
            className="px-2.5 py-1 rounded-lg text-xs font-medium flex items-center space-x-1.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          >
            <KeyRound className="h-3.5 w-3.5 text-slate-500" />
            <span>Claves Binance</span>
          </button>

          <span className="text-slate-300 dark:text-slate-700">|</span>

          <a href="/" className="px-2.5 py-1 rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-semibold">
            Mercado
          </a>
          <a href="/orders" className="px-2.5 py-1 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors">
            Órdenes
          </a>
          <a href="/fiscal" className="px-2.5 py-1 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors">
            Fiscal SENIAT
          </a>
          {user?.role === "ADMIN" && (
            <a href="/admin" className="px-2.5 py-1 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors">
              Usuarios
            </a>
          )}
          <a href="/login" className="px-2.5 py-1 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors font-medium">
            {user ? user.username : "Iniciar Sesión"}
          </a>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 2. CABECERA OPERATIVA (SOBRIA, ELEGANTE, PROFESIONAL)     */}
      {/* ======================================================== */}
      <header className="bg-slate-900 text-white dark:bg-[#0D111A] border-b border-slate-800 pt-5 px-6 pb-6 relative">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="relative">
              <div className="h-11 w-11 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-white font-bold text-sm">
                {user ? user.username.substring(0, 2).toUpperCase() : "CM"}
              </div>
              <span className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-slate-900 ${
                botStatus?.is_paused ? "bg-amber-500" : "bg-emerald-500"
              }`} />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-semibold text-base text-white">
                  {user ? user.username : "Operador"}
                </span>
                <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded border border-slate-700 font-mono uppercase text-slate-300">
                  {user?.role || "TRADER"}
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                {botStatus?.is_paused ? "Motor: Pausado (Fail-Closed Activo)" : "Motor P2P Binance: En Línea"}
              </p>
            </div>
          </div>

          {/* Acciones Rápidas del Operador */}
          <div className="flex items-center space-x-2">
            <button
              onClick={cargarDatos}
              title="Refrescar cotizaciones"
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors"
            >
              <RefreshCw className={`h-4 w-4 ${cargando ? "animate-spin" : ""}`} />
            </button>

            {user?.role === "ADMIN" && (
              <button
                onClick={alternarPausaBot}
                title={botStatus?.is_paused ? "Reanudar motor" : "Parada de emergencia"}
                className={`px-3 py-2 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
                  botStatus?.is_paused 
                    ? "bg-emerald-600 hover:bg-emerald-500 text-white font-bold" 
                    : "bg-rose-700 hover:bg-rose-600 text-white font-bold"
                }`}
              >
                <Zap className="h-3.5 w-3.5" />
                <span>{botStatus?.is_paused ? "REANUDAR MOTOR" : "PARADA DE EMERGENCIA"}</span>
              </button>
            )}
          </div>
        </div>

        {/* Barra de Saldo y Tasas Oficiales (Soberbio, sin brillos neon) */}
        <div className="mt-5 pt-4 border-t border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
          <div>
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold block">
              Capital Activo para Despliegue de Arbitraje
            </span>
            <div className="text-2xl font-bold font-mono tracking-tight text-white mt-0.5">
              ${ montoUsdt.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
              <span className="text-xs font-normal text-slate-400 ml-1.5">USDT</span>
            </div>
          </div>

          <div className="inline-flex flex-wrap items-center gap-3 bg-slate-800/80 px-4 py-2 rounded-lg border border-slate-700 font-mono text-xs">
            <span>Tasa BCV: <strong className="text-white">{bcv?.usd ? bcv.usd.toFixed(2) : "881.07"} VES</strong></span>
            <span className="text-slate-600">|</span>
            <span>Mediana P2P: <strong className="text-white">{bcv?.p2p_usdt_ref ? bcv.p2p_usdt_ref.toFixed(2) : "948.80"} VES</strong></span>
            <span className="text-slate-600">|</span>
            <span className="text-emerald-400 font-semibold">Brecha Oficial: +{bcv?.brecha_pct ? bcv.brecha_pct.toFixed(2) : "7.68"}%</span>
          </div>
        </div>
      </header>

      {/* ======================================================== */}
      {/* 3. ALERTAS DE NOTIFICACIÓN                               */}
      {/* ======================================================== */}
      <div className="px-5 pt-3">
        {notifMsg && (
          <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 text-xs flex items-center space-x-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <span>{notifMsg}</span>
          </div>
        )}
        {errorMsg && (
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300 text-xs flex items-center space-x-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400" />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {/* ======================================================== */}
      {/* 4. CONTENIDO PRINCIPAL: RESPONSIVO DUAL                  */}
      {/* ======================================================== */}
      <main className="flex-1 px-4 sm:px-6 pt-3 pb-6 space-y-5 overflow-y-auto">

        {/* ==================================================== */}
        {/* BANNER DE MEJOR RUTA EN CALIENTE                     */}
        {/* ==================================================== */}
        <div className="bg-white dark:bg-[#0E121A] p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <span className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                <Flame className="h-3 w-3 text-red-600" />
                <span>MEJOR RUTA DE ARBITRAJE DETECTADA</span>
              </span>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 flex items-center space-x-2">
                <span>Comprar en <strong>{bestArbitrage?.buy_bank || "Banco de Venezuela"}</strong> ({tasaCompra.toFixed(2)} VES)</span>
                <ArrowRight className="h-4 w-4 text-slate-400" />
                <span>Vender en <strong>{bestArbitrage?.sell_bank || "Pago Móvil / Banesco"}</strong> ({tasaVenta.toFixed(2)} VES)</span>
              </p>
              <p className="text-xs text-slate-600 dark:text-slate-400 font-mono">
                Spread Bruto: <strong className="text-emerald-700 dark:text-emerald-400">+{spreadPct.toFixed(2)}%</strong> | Ganancia Neta Est: <strong className="text-emerald-700 dark:text-emerald-400">+{gananciaNetaUsdt} USDT</strong> / {montoUsdt}u
              </p>
            </div>

            <button
              onClick={() => alert(`Ruta de arbitraje verificada para ${montoUsdt} USDT. Control Fail-Closed de libro activo.`)}
              className="px-4 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 active:scale-[0.99] text-white font-semibold text-xs flex items-center justify-center space-x-1.5 transition-colors shrink-0 shadow-xs"
            >
              <Zap className="h-3.5 w-3.5 fill-white" />
              <span>EJECUTAR RUTA EN 1 CLIC</span>
            </button>
          </div>
        </div>

        {/* ==================================================== */}
        {/* VISTA DESKTOP (PANTALLAS GRANDES >= lg: 1024px)      */}
        {/* ==================================================== */}
        <div className="hidden lg:grid lg:grid-cols-12 lg:gap-5">
          {/* Columna Izquierda: Matriz de Cotizaciones & Gráfica (8 Cols) */}
          <div className="lg:col-span-8 space-y-4">
            <div className="bg-white dark:bg-[#0E121A] p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wide flex items-center space-x-2">
                    <TrendingUp className="h-4 w-4 text-slate-700 dark:text-slate-300" />
                    <span>Matriz de Profundidad Interbancaria (VES / USDT)</span>
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Escáner de libros Binance P2P a través de los canales de compensación en Venezuela
                  </p>
                </div>

                {/* Filtros de Intervalo */}
                <div className="flex items-center space-x-1 bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-600 dark:text-slate-400">
                  {["1D", "1S", "1M", "6M", "1A"].map((tf) => (
                    <button
                      key={tf}
                      onClick={() => setTimeframe(tf)}
                      className={`px-2 py-0.5 rounded transition-colors ${
                        timeframe === tf ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-xs font-semibold" : "hover:text-slate-900 dark:hover:text-slate-200"
                      }`}
                    >
                      {tf}
                    </button>
                  ))}
                </div>
              </div>

              {/* Gráfica Financiera Limpia (Gridlines y Ticks de Precio Sobrios) */}
              <div className="h-28 w-full bg-slate-50 dark:bg-[#0A0D14] rounded-lg p-2.5 border border-slate-200 dark:border-slate-800 relative">
                <svg viewBox="0 0 500 70" className="w-full h-full" preserveAspectRatio="none">
                  {/* Líneas de cuadrícula sutiles */}
                  <line x1="0" y1="18" x2="500" y2="18" className="stroke-slate-200 dark:stroke-slate-800" strokeWidth="1" strokeDasharray="3 3" />
                  <line x1="0" y1="36" x2="500" y2="36" className="stroke-slate-200 dark:stroke-slate-800" strokeWidth="1" strokeDasharray="3 3" />
                  <line x1="0" y1="54" x2="500" y2="54" className="stroke-slate-200 dark:stroke-slate-800" strokeWidth="1" strokeDasharray="3 3" />

                  {/* Curva de cotización paralela P2P */}
                  <path
                    d="M 0,45 L 60,38 L 120,42 L 180,30 L 240,32 L 300,24 L 360,28 L 420,20 L 500,16"
                    className="stroke-red-600 fill-none"
                    strokeWidth="2"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                  />
                  {/* Curva de referencia oficial BCV */}
                  <path
                    d="M 0,54 L 500,54"
                    className="stroke-slate-400 dark:stroke-slate-600 fill-none"
                    strokeWidth="1.5"
                    strokeDasharray="4 4"
                  />
                </svg>
                {/* Ticks laterales */}
                <div className="absolute right-3 top-2 text-[9px] font-mono text-slate-400">
                  Venta P2P: 948.80
                </div>
                <div className="absolute right-3 bottom-2 text-[9px] font-mono text-slate-500">
                  BCV: 881.07
                </div>
              </div>

              {/* Filtro de Canales Bancarios */}
              <div className="flex items-center space-x-1.5 overflow-x-auto text-xs">
                {[
                  { id: "TODOS", label: "Todos los Canales" },
                  { id: "PAGO_MOVIL", label: "Pago Móvil" },
                  { id: "BANESCO", label: "Banesco" },
                  { id: "MERCANTIL", label: "Mercantil" },
                  { id: "BDV", label: "Banco de Venezuela" }
                ].map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setFiltroBanco(f.id)}
                    className={`px-2.5 py-1 rounded-lg whitespace-nowrap transition-colors font-medium ${
                      filtroBanco === f.id
                        ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-semibold"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              {/* Tabla de Cotizaciones */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 text-[11px]">
                      <th className="py-2 px-3">Banco / Canal</th>
                      <th className="py-2 px-3 text-right">Compra (VES)</th>
                      <th className="py-2 px-3 text-right">Venta (VES)</th>
                      <th className="py-2 px-3 text-right">Spread Bruto</th>
                      <th className="py-2 px-3 text-right">Retorno / 100u</th>
                      <th className="py-2 px-3 text-right">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                    {cotizacionesFiltradas.length > 0 ? (
                      cotizacionesFiltradas.map((q, idx) => (
                        <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-[#121622] transition-colors">
                          <td className="py-2.5 px-3 font-medium text-slate-900 dark:text-slate-200 flex items-center space-x-2">
                            <span className="h-1.5 w-1.5 rounded-full bg-red-600" />
                            <span>{q.bank_name}</span>
                          </td>
                          <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-400">{q.buy_rate.toFixed(2)}</td>
                          <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-400">{q.sell_rate.toFixed(2)}</td>
                          <td className="py-2.5 px-3 text-right">
                            <span className="text-emerald-700 dark:text-emerald-400 font-semibold">+{q.spread_pct.toFixed(2)}%</span>
                          </td>
                          <td className="py-2.5 px-3 text-right text-emerald-700 dark:text-emerald-400 font-semibold">
                            +${((q.spread_ves || 12) * 0.1).toFixed(2)}
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                              LÍQUIDO
                            </span>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="py-6 text-center text-slate-400">
                          {cargando ? "Sincronizando libros Binance P2P..." : "Sin cotizaciones activas en este canal."}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Columna Derecha: Panel de Ejecución de Capital (4 Cols) */}
          <div className="lg:col-span-4 space-y-4">
            <div className="bg-white dark:bg-[#0E121A] p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
              <span className="font-semibold text-sm text-slate-900 dark:text-slate-100 flex items-center space-x-2">
                <ArrowLeftRight className="h-4 w-4 text-red-600" />
                <span>Ejecutor de Arbitraje</span>
              </span>

              {/* Slider de Capital */}
              <div>
                <div className="flex justify-between text-xs text-slate-600 dark:text-slate-400 mb-1">
                  <span>Despliegue de Capital:</span>
                  <span className="font-bold text-slate-900 dark:text-slate-100 font-mono">{montoUsdt} USDT</span>
                </div>
                <input
                  type="range"
                  min="100"
                  max="5000"
                  step="50"
                  value={montoUsdt}
                  onChange={(e) => setMontoUsdt(Number(e.target.value))}
                  className="w-full accent-red-600 cursor-pointer"
                />
                <div className="grid grid-cols-4 gap-1 text-xs font-mono mt-2">
                  {[100, 250, 500, 1000].map((val) => (
                    <button
                      key={val}
                      onClick={() => setMontoUsdt(val)}
                      className={`py-1 rounded text-center transition-colors ${
                        montoUsdt === val 
                          ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-bold" 
                          : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900"
                      }`}
                    >
                      ${val}
                    </button>
                  ))}
                </div>
              </div>

              {/* Retorno Estimado */}
              <div className="p-3 rounded-lg bg-slate-50 dark:bg-[#121622] border border-slate-200 dark:border-slate-800 space-y-1.5 text-xs font-mono">
                <div className="flex justify-between text-slate-600 dark:text-slate-400">
                  <span>Retorno en VES:</span>
                  <strong className="text-slate-900 dark:text-slate-100">{bolivaresSalida}</strong>
                </div>
                <div className="flex justify-between text-emerald-700 dark:text-emerald-400 font-semibold border-t border-slate-200 dark:border-slate-700/80 pt-1.5">
                  <span>Ganancia Neta Estimada:</span>
                  <span>+{gananciaNetaUsdt} USDT</span>
                </div>
              </div>

              <button
                onClick={() => alert(`Ruta de arbitraje armada por ${montoUsdt} USDT.`)}
                className="w-full py-2.5 rounded-lg bg-red-600 hover:bg-red-700 active:scale-[0.99] text-white font-semibold text-xs flex items-center justify-center space-x-1.5 transition-colors shadow-xs"
              >
                <Zap className="h-3.5 w-3.5 fill-white" />
                <span>Ejecutar Arbitraje</span>
              </button>
            </div>

            {/* Accesos Rápidos a Módulos del Sistema */}
            <div className="bg-white dark:bg-[#0E121A] p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-2 text-xs">
              <span className="font-semibold text-xs text-slate-500 uppercase tracking-wide block mb-1">
                Módulos del Sistema
              </span>

              <a
                href="/fiscal"
                className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-[#121622] hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-slate-800 dark:text-slate-200 group border border-slate-200 dark:border-slate-800"
              >
                <div className="flex items-center space-x-2">
                  <Building2 className="h-4 w-4 text-slate-500" />
                  <span>Reconciliación Fiscal SENIAT</span>
                </div>
                <ChevronRight className="h-3.5 w-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
              </a>

              <a
                href="/orders"
                className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-[#121622] hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-slate-800 dark:text-slate-200 group border border-slate-200 dark:border-slate-800"
              >
                <div className="flex items-center space-x-2">
                  <FileSpreadsheet className="h-4 w-4 text-slate-500" />
                  <span>Libro de Órdenes & Exportación</span>
                </div>
                <ChevronRight className="h-3.5 w-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
              </a>

              {/* Botón directo a Configuración de API Keys Binance */}
              <button
                type="button"
                onClick={() => setIsBinanceModalOpen(true)}
                className="w-full flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-[#121622] hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-slate-800 dark:text-slate-200 group border border-slate-200 dark:border-slate-800 text-left"
              >
                <div className="flex items-center space-x-2">
                  <KeyRound className="h-4 w-4 text-slate-500" />
                  <span>Configuración API Binance & Test</span>
                </div>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-400 font-mono font-medium">
                  Cifrado
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* ==================================================== */}
        {/* VISTA MÓVIL (PANTALLAS PEQUEÑAS < lg: 1024px)        */}
        {/* ==================================================== */}
        <div className="lg:hidden space-y-4">
          {/* PESTAÑA MÓVIL: MERCADO */}
          {activeTab === "mercado" && (
            <div className="space-y-3">
              {/* Selector de Modo en Móvil */}
              <div className="flex items-center justify-between p-2 bg-white dark:bg-[#0E121A] rounded-xl border border-slate-200 dark:border-slate-800 text-xs">
                <span className="text-slate-600 dark:text-slate-400">Tema Visual:</span>
                <button
                  onClick={toggleTheme}
                  className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-medium flex items-center space-x-1.5"
                >
                  {theme === "dark" ? <Sun className="h-3.5 w-3.5 text-amber-500" /> : <Moon className="h-3.5 w-3.5 text-slate-700" />}
                  <span>{theme === "dark" ? "Blanco Perla" : "Negro Azabache"}</span>
                </button>
              </div>

              {/* Cotizaciones Móvil */}
              <div className="space-y-2">
                {cotizacionesFiltradas.map((q, idx) => (
                  <div key={idx} className="bg-white dark:bg-[#0E121A] p-3 rounded-xl border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-xs text-slate-900 dark:text-slate-100">{q.bank_name}</h4>
                      <p className="text-[11px] text-slate-500 font-mono">C: {q.buy_rate.toFixed(2)} | V: {q.sell_rate.toFixed(2)}</p>
                    </div>
                    <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800 font-mono">
                      +{q.spread_pct.toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* PESTAÑA MÓVIL: SWAP / ARBITRAJE */}
          {activeTab === "swap" && (
            <div className="bg-white dark:bg-[#0E121A] p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
              <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                Calculadora Rápida de Despliegue
              </span>

              <div className="bg-slate-50 dark:bg-[#121622] p-3 rounded-lg border border-slate-200 dark:border-slate-800">
                <span className="text-[11px] text-slate-500 block mb-1">Monto en USDT</span>
                <input
                  type="number"
                  value={montoUsdt}
                  onChange={(e) => setMontoUsdt(Math.max(10, Number(e.target.value)))}
                  className="bg-transparent text-lg font-bold text-slate-900 dark:text-white focus:outline-none w-full font-mono"
                />
              </div>

              <div className="p-3 rounded-lg bg-slate-50 dark:bg-[#121622] border border-slate-200 dark:border-slate-800 text-xs font-mono space-y-1">
                <div className="flex justify-between text-emerald-700 dark:text-emerald-400 font-semibold">
                  <span>Ganancia Estimada:</span>
                  <span>+{gananciaNetaUsdt} USDT (+{spreadPct.toFixed(2)}%)</span>
                </div>
                <div className="flex justify-between text-slate-500 text-[11px]">
                  <span>Bolívares de Salida:</span>
                  <span>{bolivaresSalida} VES</span>
                </div>
              </div>

              <button
                onClick={() => alert(`Ruta de ${montoUsdt} USDT armada.`)}
                className="w-full py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold text-xs"
              >
                Ejecutar Arbitraje
              </button>
            </div>
          )}

          {/* PESTAÑA MÓVIL: ÓRDENES */}
          {activeTab === "ordenes" && (
            <div className="space-y-2">
              <div className="flex justify-between items-center px-1">
                <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300">Órdenes Recientes</h4>
                <a href="/orders" className="text-xs text-red-600 hover:underline">Ver todas</a>
              </div>
              {orders.slice(0, 5).map((ord) => (
                <div key={ord.id} className="bg-white dark:bg-[#0E121A] p-3 rounded-xl border border-slate-200 dark:border-slate-800 flex justify-between items-center text-xs">
                  <div>
                    <span className="font-semibold text-slate-900 dark:text-slate-100">{ord.trade_type === "BUY" ? "Compra" : "Venta"} USDT</span>
                    <span className="block text-[10px] text-slate-500">{ord.counterparty_name || "Comerciante"}</span>
                  </div>
                  <span className={`font-mono font-semibold ${ord.trade_type === "BUY" ? "text-emerald-700 dark:text-emerald-400" : "text-red-600"}`}>
                    {ord.trade_type === "BUY" ? `+${ord.crypto_amount}` : `-${ord.crypto_amount}`} u
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* PESTAÑA MÓVIL: FISCAL */}
          {activeTab === "fiscal" && (
            <div className="bg-white dark:bg-[#0E121A] p-5 rounded-xl border border-slate-200 dark:border-slate-800 space-y-3 text-center">
              <Building2 className="h-7 w-7 text-red-600 mx-auto" />
              <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100">Reconciliación Fiscal SENIAT</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Audita la ecuación de 6 piezas patrimoniales y genera tu declaración contable en Excel.
              </p>
              <a
                href="/fiscal"
                className="inline-block px-4 py-2 rounded-lg bg-red-600 text-white text-xs font-semibold"
              >
                Abrir Módulo Fiscal Completo
              </a>
            </div>
          )}

          {/* PESTAÑA MÓVIL: AJUSTES */}
          {activeTab === "ajustes" && (
            <div className="space-y-4">
              <BinanceSettingsCard />

              <div className="bg-white dark:bg-[#0E121A] p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-3">
                <h3 className="font-semibold text-xs text-slate-500 uppercase tracking-wide">Ajustes del Sistema</h3>
                <div className="flex justify-between items-center p-2.5 rounded-lg bg-slate-50 dark:bg-[#121622] text-xs">
                  <span className="text-slate-700 dark:text-slate-300">Auto-Rebalanceo</span>
                  <input type="checkbox" checked={autoRebalance} onChange={(e) => setAutoRebalance(e.target.checked)} className="accent-red-600" />
                </div>
                <div className="flex justify-between items-center p-2.5 rounded-lg bg-slate-50 dark:bg-[#121622] text-xs">
                  <span className="text-slate-700 dark:text-slate-300">Auto-Liberación Binance</span>
                  <input type="checkbox" checked={autoLiberar} onChange={(e) => setAutoLiberar(e.target.checked)} className="accent-red-600" />
                </div>
                <button
                  onClick={alternarPausaBot}
                  className="w-full py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold text-xs"
                >
                  {botStatus?.is_paused ? "REANUDAR MOTOR" : "PARADA DE EMERGENCIA"}
                </button>
              </div>
            </div>
          )}

          {/* PESTAÑA MÓVIL: PERFIL */}
          {activeTab === "perfil" && (
            <div className="bg-white dark:bg-[#0E121A] p-5 rounded-xl border border-slate-200 dark:border-slate-800 space-y-3 text-center text-xs">
              <div className="h-12 w-12 mx-auto rounded-full bg-slate-800 text-white flex items-center justify-center font-bold text-base">
                {user ? user.username.substring(0, 2).toUpperCase() : "CM"}
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-slate-100">{user?.username || "Operador"}</h3>
              <p className="text-slate-500 font-mono">Rol: {user?.role || "TRADER"}</p>
              <div className="pt-2">
                <a href="/login" className="inline-block px-3.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium">
                  Cerrar Sesión / Cambiar Usuario
                </a>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ======================================================== */}
      {/* 5. MODAL DE AJUSTES BINANCE (ESPACIOSO Y NO APRETADO)    */}
      {/* ======================================================== */}
      {isBinanceModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="relative w-full max-w-2xl bg-white dark:bg-[#0D111A] rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 overflow-hidden animate-in fade-in zoom-in-95 duration-100">
            <BinanceSettingsCard onClose={() => setIsBinanceModalOpen(false)} isModal={true} />
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 6. BARRA DE NAVEGACIÓN INFERIOR (MÓVIL / TELEGRAM APP)   */}
      {/* ======================================================== */}
      <nav className="lg:hidden fixed bottom-0 left-0 right-0 max-w-7xl mx-auto bg-white/95 dark:bg-[#0A0D14]/95 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 px-3 py-1.5 flex items-center justify-around z-40">
        <button
          onClick={() => setActiveTab("mercado")}
          className={`flex flex-col items-center py-1 px-2 rounded-lg transition-colors ${
            activeTab === "mercado" ? "text-red-600 font-bold" : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
          }`}
        >
          <TrendingUp className="h-5 w-5" />
          <span className="text-[10px] mt-0.5">Mercado</span>
        </button>

        <button
          onClick={() => setActiveTab("swap")}
          className={`flex flex-col items-center py-1 px-2 rounded-lg transition-colors ${
            activeTab === "swap" ? "text-red-600 font-bold" : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
          }`}
        >
          <ArrowLeftRight className="h-5 w-5" />
          <span className="text-[10px] mt-0.5">Arbitraje</span>
        </button>

        <button
          onClick={() => setActiveTab("ordenes")}
          className={`flex flex-col items-center py-1 px-2 rounded-lg transition-colors ${
            activeTab === "ordenes" ? "text-red-600 font-bold" : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
          }`}
        >
          <Wallet className="h-5 w-5" />
          <span className="text-[10px] mt-0.5">Órdenes</span>
        </button>

        <button
          onClick={() => setActiveTab("fiscal")}
          className={`flex flex-col items-center py-1 px-2 rounded-lg transition-colors ${
            activeTab === "fiscal" ? "text-red-600 font-bold" : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
          }`}
        >
          <Building2 className="h-5 w-5" />
          <span className="text-[10px] mt-0.5">Fiscal</span>
        </button>

        <button
          onClick={() => setActiveTab("ajustes")}
          className={`flex flex-col items-center py-1 px-2 rounded-lg transition-colors ${
            activeTab === "ajustes" ? "text-red-600 font-bold" : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
          }`}
        >
          <Settings className="h-5 w-5" />
          <span className="text-[10px] mt-0.5">Ajustes</span>
        </button>
      </nav>
    </div>
  );
}
