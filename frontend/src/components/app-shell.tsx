"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BCVRates,
  BinanceStatusResponse,
  BotStatus,
  User,
  getBCVRates,
  getBinanceSettings,
  getBotStatus,
  getCurrentUser,
  loginTelegramWebApp,
  logout,
  pauseBot,
  resumeBot,
} from "@/lib/api";
import { useTheme } from "@/lib/theme-context";
import { useWebSocket } from "@/lib/useWebSocket";

interface NavItem {
  href: string;
  label: string;
  shortLabel: string;
  icon: string;
  requiresTrader?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Matriz de Spreads & Bancos",
    shortLabel: "Matriz",
    icon: "grid_view",
  },
  {
    href: "/calculator",
    label: "Calculadora de Ciclos",
    shortLabel: "Calculadora",
    icon: "calculate",
  },
  {
    href: "/orders",
    label: "Ganancias & Órdenes",
    shortLabel: "Órdenes",
    icon: "receipt_long",
    requiresTrader: true,
  },
  {
    href: "/accounting",
    label: "Contabilidad & Diario",
    shortLabel: "Contabilidad",
    icon: "menu_book",
    requiresTrader: true,
  },
  {
    href: "/sheets",
    label: "Sincronización Sheets",
    shortLabel: "Sheets",
    icon: "sync_alt",
    requiresTrader: true,
  },
  {
    href: "/settings",
    label: "Configuración API & Seg",
    shortLabel: "Seguridad",
    icon: "tune",
    requiresTrader: true,
  },
];

interface AppShellProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  badge?: string;
  actions?: React.ReactNode;
}

export function AppShell({ children, title, subtitle, badge, actions }: AppShellProps) {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [bcv, setBcv] = useState<BCVRates | null>(null);
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [binanceStatus, setBinanceStatus] = useState<BinanceStatusResponse | null>(null);
  const [togglingBot, setTogglingBot] = useState(false);

  const loadTelemetry = useCallback(async () => {
    const currentUser = getCurrentUser();
    setUser(currentUser);

    try {
      const rates = await getBCVRates();
      setBcv(rates);
    } catch {
      // Silencioso en modo desconectado
    }

    try {
      const status = await getBotStatus();
      setBotStatus(status);
    } catch {
      // Silencioso si backend aún no responde
    }

    if (currentUser && (currentUser.role === "ADMIN" || currentUser.role === "TRADER")) {
      try {
        const binance = await getBinanceSettings();
        setBinanceStatus(binance);
      } catch {
        // Silencioso para usuarios sin permisos o backend desconectado
      }
    }
  }, []);

  useEffect(() => {
    // Auto-SSO silencioso cuando se abre desde Telegram Mini App
    if (typeof window !== "undefined") {
      const tg = (window as any).Telegram?.WebApp;
      if (tg) {
        tg.ready?.();
        tg.expand?.();
        if (!getCurrentUser() && tg.initData) {
          loginTelegramWebApp(tg.initData)
            .then((res) => {
              setUser(res.user);
              loadTelemetry();
            })
            .catch(() => {});
        }
      }
    }

    loadTelemetry();
    const interval = setInterval(loadTelemetry, 25000);
    return () => clearInterval(interval);
  }, [loadTelemetry]);

  const { isConnected: wsConnected } = useWebSocket((msg) => {
    if (msg.type === "bcv_update" && msg.data) {
      setBcv((prev) => ({ ...(prev || {}), ...msg.data }));
    } else if (msg.type === "bot_status" && msg.data) {
      setBotStatus((prev) => ({ ...(prev || {}), ...msg.data }));
    }
  });

  async function handleToggleBot() {
    if (!user || user.role !== "ADMIN" || togglingBot) return;
    setTogglingBot(true);
    try {
      if (botStatus?.is_paused) {
        await resumeBot();
      } else {
        await pauseBot();
      }
      await loadTelemetry();
    } catch {
      // Ignorar error visualmente, mantenido fail-closed
    } finally {
      setTogglingBot(false);
    }
  }

  const usedWeight = binanceStatus?.used_weight ?? 0;
  const maxWeight = binanceStatus?.max_weight ?? 6000;
  const weightColor =
    usedWeight >= 5000
      ? "text-error border-error/40 bg-error/10"
      : usedWeight >= 3500
      ? "text-primary border-primary-container/40 bg-primary-container/10"
      : "text-slate-300 border-[#1e2430] bg-surface-container";

  const isPaused = botStatus?.is_paused ?? false;

  const roleBadgeStyle =
    user?.role === "ADMIN"
      ? "bg-primary-container/15 text-primary border-primary-container/30"
      : user?.role === "TRADER"
      ? "bg-tertiary/15 text-tertiary border-tertiary/30"
      : "bg-slate-800 text-slate-400 border-slate-700";

  return (
    <div className="min-h-screen bg-background text-on-surface flex flex-col lg:flex-row">
      {/* Overlay móvil */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-xs lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar Institucional */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-surface border-r border-[#1e2430] flex flex-col justify-between transition-transform duration-200 lg:translate-x-0 ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div>
          {/* Identidad de Marca */}
          <div className="h-16 px-5 flex items-center justify-between border-b border-[#1e2430]">
            <Link href="/" className="flex items-center gap-3 group">
              <div className="w-9 h-9 rounded-lg bg-primary-container/15 border border-primary-container/30 flex items-center justify-center text-primary-container group-hover:bg-primary-container/25 transition-colors">
                <span className="material-symbols-outlined text-[20px]">bolt</span>
              </div>
              <div>
                <div className="text-sm font-bold tracking-tight text-white leading-none">
                  P2P Merchant OS
                </div>
                <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mt-1">
                  Binance Arbitrage
                </div>
              </div>
            </Link>
            <button
              type="button"
              onClick={() => setMobileMenuOpen(false)}
              className="lg:hidden text-slate-400 hover:text-white p-1"
              aria-label="Cerrar menú"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>

          {/* Menú Operativo de 6 Módulos */}
          <div className="px-3 py-4">
            <div className="px-3 mb-2 text-[10px] font-mono uppercase tracking-widest text-slate-500">
              Mesa Operativa
            </div>
            <nav className="space-y-1">
              {NAV_ITEMS.map((item) => {
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname === item.href || pathname?.startsWith(`${item.href}/`);
                const isRestricted =
                  item.requiresTrader && (!user || user.role === "INVITADO");

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-xs transition-all ${
                      isActive
                        ? "bg-primary-container/12 text-primary font-semibold border-r-2 border-primary-container"
                        : "text-slate-400 hover:text-white hover:bg-surface-container-low font-medium"
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span
                        className={`material-symbols-outlined text-[18px] ${
                          isActive ? "text-primary-container" : "text-slate-500"
                        }`}
                      >
                        {item.icon}
                      </span>
                      <span className="truncate">{item.label}</span>
                    </div>
                    {isRestricted && (
                      <span
                        className="material-symbols-outlined text-[14px] text-slate-600"
                        title="Requiere rol TRADER o ADMIN"
                      >
                        lock
                      </span>
                    )}
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>

        {/* Pie del Sidebar: Seguridad + Operador RBAC */}
        <div className="p-3 border-t border-[#1e2430] space-y-2.5">
          <div className="px-3 py-2 rounded-lg bg-surface-container-low border border-[#1e2430] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[15px] text-tertiary">
                verified_user
              </span>
              <span className="text-[10px] font-mono text-slate-400">
                Fail-Closed • AES-256
              </span>
            </div>
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? "bg-tertiary animate-pulse" : "bg-primary-container"
              }`}
              title={wsConnected ? "WebSocket en vivo" : "Polling REST activo"}
            />
          </div>

          {user ? (
            <div className="p-2.5 rounded-lg bg-surface-container border border-[#1e2430] flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-primary-container/20 border border-primary-container/30 flex items-center justify-center font-mono text-xs font-bold text-primary shrink-0">
                  {user.username.slice(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-white truncate">
                    {user.username}
                  </div>
                  <span
                    className={`inline-block mt-0.5 px-1.5 py-0.2 text-[9px] font-mono font-bold uppercase rounded border ${roleBadgeStyle}`}
                  >
                    {user.role}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={logout}
                className="p-1.5 rounded-md text-slate-400 hover:text-error hover:bg-error/10 transition-colors shrink-0"
                title="Cerrar sesión"
              >
                <span className="material-symbols-outlined text-[18px]">logout</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <Link
                href="/login"
                className="px-3 py-2 rounded-lg bg-primary-container text-on-primary font-semibold text-xs text-center hover:brightness-110 transition-all"
              >
                Ingresar
              </Link>
              <Link
                href="/register"
                className="px-3 py-2 rounded-lg bg-surface-container border border-[#1e2430] text-slate-300 font-medium text-xs text-center hover:text-white hover:border-slate-600 transition-all"
              >
                Registro
              </Link>
            </div>
          )}
        </div>
      </aside>

      {/* Contenedor Principal */}
      <div className="flex-1 flex flex-col lg:pl-64 min-w-0">
        {/* Topbar de Telemetría en Tiempo Real */}
        <header className="sticky top-0 z-30 h-16 bg-surface/95 backdrop-blur-md border-b border-[#1e2430] px-4 lg:px-6 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-1.5 rounded-lg bg-surface-container border border-[#1e2430] text-slate-300 hover:text-white"
              aria-label="Abrir navegación"
            >
              <span className="material-symbols-outlined text-[20px]">menu</span>
            </button>

            {/* Telemetría BCV, USDT/VES y Weight */}
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
              <div className="px-2.5 py-1 rounded-md bg-surface-container border border-[#1e2430] flex items-center gap-1.5 shrink-0">
                <span className="text-[10px] font-mono uppercase text-slate-400">BCV</span>
                <span className="text-xs font-mono font-semibold text-secondary tabular-nums">
                  {bcv?.usd ? `Bs. ${bcv.usd.toFixed(2)}` : "Bs. --"}
                </span>
              </div>

              <div className="px-2.5 py-1 rounded-md bg-surface-container border border-[#1e2430] flex items-center gap-1.5 shrink-0">
                <span className="text-[10px] font-mono uppercase text-slate-400">
                  USDT/VES
                </span>
                <span className="text-xs font-mono font-semibold text-tertiary tabular-nums">
                  {bcv?.p2p_usdt_ref ? `Bs. ${bcv.p2p_usdt_ref.toFixed(2)}` : "Bs. --"}
                </span>
                {typeof bcv?.brecha_pct === "number" && (
                  <span className="text-[10px] font-mono text-primary hidden sm:inline tabular-nums">
                    ({bcv.brecha_pct >= 0 ? "+" : ""}
                    {bcv.brecha_pct.toFixed(1)}%)
                  </span>
                )}
              </div>

              <div
                className={`hidden md:flex px-2.5 py-1 rounded-md border items-center gap-1.5 shrink-0 ${weightColor}`}
                title="Consumo x-mbx-used-weight de Binance API (Pausa automática > 5000)"
              >
                <span className="material-symbols-outlined text-[14px]">speed</span>
                <span className="text-[11px] font-mono tabular-nums">
                  Weight: {usedWeight}/{maxWeight}
                </span>
              </div>
            </div>
          </div>

          {/* Controles Derechos: Estado del Motor + Tema [OSCURO | ATENUADO] */}
          <div className="flex items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={handleToggleBot}
              disabled={user?.role !== "ADMIN" || togglingBot}
              title={
                user?.role === "ADMIN"
                  ? isPaused
                    ? "Clic para reanudar motor operativo"
                    : "Clic para activar pausa Fail-Closed"
                  : "Estado del motor P2P"
              }
              className={`px-2.5 py-1 rounded-md border text-[11px] font-mono font-semibold flex items-center gap-1.5 transition-colors ${
                isPaused
                  ? "bg-error/15 border-error/40 text-error"
                  : "bg-tertiary/12 border-tertiary/30 text-tertiary"
              } ${user?.role === "ADMIN" ? "cursor-pointer hover:brightness-110" : "cursor-default"}`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isPaused ? "bg-error" : "bg-tertiary animate-pulse"
                }`}
              />
              <span className="hidden sm:inline">
                {isPaused ? "PAUSA FAIL-CLOSED" : "MOTOR ACTIVO"}
              </span>
            </button>

            {/* Conmutador unificado [OSCURO | ATENUADO] */}
            <div className="p-0.5 rounded-lg bg-surface-container-low border border-[#1e2430] flex items-center text-[10px] font-mono">
              <button
                type="button"
                onClick={() => setTheme("dark")}
                className={`px-2 py-1 rounded-md transition-colors ${
                  theme === "dark"
                    ? "bg-primary-container text-on-primary font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                OSCURO
              </button>
              <button
                type="button"
                onClick={() => setTheme("dim")}
                className={`px-2 py-1 rounded-md transition-colors ${
                  theme === "dim"
                    ? "bg-primary-container text-on-primary font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                ATENUADO
              </button>
            </div>
          </div>
        </header>

        {/* Encabezado Contextual Opcional de la Vista */}
        {(title || actions) && (
          <div className="px-4 lg:px-6 pt-5 pb-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                {title && (
                  <h1 className="text-lg lg:text-xl font-bold tracking-tight text-white">
                    {title}
                  </h1>
                )}
                {badge && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-primary-container/15 text-primary border border-primary-container/30">
                    {badge}
                  </span>
                )}
              </div>
              {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
            </div>
            {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
          </div>
        )}

        {/* Área de Contenido Denso */}
        <main className="flex-1 px-4 lg:px-6 py-4 pb-20 lg:pb-8">{children}</main>

        {/* Navegación Inferior Móvil / Telegram Mini App */}
        <nav className="lg:hidden fixed bottom-0 inset-x-0 z-30 h-14 bg-surface/95 backdrop-blur-md border-t border-[#1e2430] grid grid-cols-6">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname?.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center justify-center gap-0.5 text-[9px] font-medium ${
                  isActive ? "text-primary" : "text-slate-400 hover:text-white"
                }`}
              >
                <span className="material-symbols-outlined text-[18px]">{item.icon}</span>
                <span className="truncate max-w-[54px]">{item.shortLabel}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
