"use client";

import React, { useEffect, useState } from "react";
import { 
  Zap, 
  Layers, 
  FileSpreadsheet, 
  Users, 
  AlertOctagon, 
  Download, 
  Activity, 
  User as UserIcon, 
  LogOut,
  Radio
} from "lucide-react";
import { getCurrentUser, logout, getBotStatus, pauseBot, resumeBot, User, BotStatus, getExportOrdersUrl } from "@/lib/api";

export function TerminalHeader() {
  const [user, setUser] = useState<User | null>(null);
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    setUser(getCurrentUser());
    cargarEstado();
    const interval = setInterval(cargarEstado, 8000);
    return () => clearInterval(interval);
  }, []);

  async function cargarEstado() {
    try {
      const s = await getBotStatus();
      setBotStatus(s);
    } catch {
      // Ignorar si aún no hay sesión
    }
  }

  async function alternarPausa() {
    if (!user || user.role !== "ADMIN" || isProcessing) return;
    setIsProcessing(true);
    try {
      if (botStatus?.is_paused) {
        await resumeBot();
      } else {
        await pauseBot();
      }
      await cargarEstado();
    } catch (e: any) {
      alert(e.message || "Error al alternar estado del bot");
    } finally {
      setIsProcessing(false);
    }
  }

  const estaPausado = botStatus?.is_paused ?? false;

  return (
    <header className="sticky top-0 z-50 bg-[#080c10]/95 backdrop-blur-md border-b border-[#1a2636] px-4 lg:px-6 py-2.5">
      <div className="max-w-[1720px] mx-auto flex items-center justify-between">
        {/* Identidad de Marca y Telemetría */}
        <div className="flex items-center space-x-4">
          <a href="/" className="flex items-center space-x-2.5 group">
            <div className="h-8 w-8 rounded-lg bg-[#00e599]/10 border border-[#00e599]/30 flex items-center justify-center group-hover:border-[#00e599]/60 transition-colors">
              <Zap className="h-4 w-4 text-[#00e599]" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-mono font-bold text-sm tracking-wider text-slate-100">
                  ARBITEX // VES-USDT
                </span>
              </div>
              <div className="flex items-center space-x-2 text-[10px] font-mono text-[#00d1ff]">
                <span className="flex items-center space-x-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#00e599] animate-pulse" />
                  <span>12ms LATENCIA</span>
                </span>
                <span className="text-slate-600">//</span>
                <span className="text-slate-400">P2P ENGINE v4.2</span>
              </div>
            </div>
          </a>

          {/* Menú de Navegación Superior */}
          <nav className="hidden lg:flex items-center space-x-1 pl-4 border-l border-[#1a2636] text-[11px] font-mono font-semibold">
            <a
              href="/"
              className="px-3 py-1.5 rounded-md bg-[#16212e] text-[#00e599] border border-[#00e599]/20 flex items-center space-x-1.5 transition-colors"
            >
              <Layers className="h-3.5 w-3.5" />
              <span>MATRIZ DE SPREADS</span>
            </a>
            <a
              href="/orders"
              className="px-3 py-1.5 rounded-md hover:bg-[#121b27] text-slate-300 hover:text-slate-100 transition-colors flex items-center space-x-1.5"
            >
              <FileSpreadsheet className="h-3.5 w-3.5 text-slate-400" />
              <span>LIBRO DE ÓRDENES</span>
            </a>
            {user?.role === "ADMIN" && (
              <a
                href="/admin"
                className="px-3 py-1.5 rounded-md hover:bg-[#121b27] text-slate-300 hover:text-slate-100 transition-colors flex items-center space-x-1.5"
              >
                <Users className="h-3.5 w-3.5 text-slate-400" />
                <span>ADMINISTRACIÓN RBAC</span>
              </a>
            )}
          </nav>
        </div>

        {/* Controles de Emergencia & Estado del Bot */}
        <div className="flex items-center space-x-3">
          {/* Indicador de Estado del Bot */}
          <div className="flex items-center space-x-2 px-3 py-1 rounded-md bg-[#0c131a] border border-[#1a2636]">
            <span className={`h-2 w-2 rounded-full ${estaPausado ? "bg-[#f59e0b] animate-ping" : "bg-[#00e599]"}`} />
            <span className="text-[11px] font-mono font-bold tracking-wide text-slate-200">
              BOT: {estaPausado ? "PAUSADO" : "ACTIVO"}
            </span>
          </div>

          {/* Botón de Parada de Emergencia (Kill Switch) */}
          {user?.role === "ADMIN" && (
            <button
              onClick={alternarPausa}
              disabled={isProcessing}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-[11px] font-mono font-bold border transition-all ${
                estaPausado 
                  ? "bg-[#00e599]/10 text-[#00e599] border-[#00e599]/40 hover:bg-[#00e599]/20" 
                  : "bg-[#ff4d4d]/10 text-[#ff4d4d] border-[#ff4d4d]/40 hover:bg-[#ff4d4d]/20"
              }`}
              title={estaPausado ? "Reanudar operaciones" : "Parada total de emergencia"}
            >
              <AlertOctagon className="h-3.5 w-3.5" />
              <span>{estaPausado ? "REANUDAR MOTOR" : "PARADA DE EMERGENCIA"}</span>
            </button>
          )}

          {/* Exportar Logs / Excel */}
          <a
            href={getExportOrdersUrl("xlsx")}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-[#121b27] hover:bg-[#16212e] text-slate-300 hover:text-slate-100 border border-[#1a2636] text-[11px] font-mono transition-colors"
            title="Descargar histórico fiscal en Excel"
          >
            <Download className="h-3.5 w-3.5 text-[#00e599]" />
            <span>EXPORTAR LOGS</span>
          </a>

          {/* Perfil de Usuario */}
          {user ? (
            <div className="flex items-center space-x-2 pl-2 border-l border-[#1a2636]">
              <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-[#0c131a] border border-[#1a2636]">
                <UserIcon className="h-3 w-3 text-slate-400" />
                <span className="text-xs font-mono text-slate-200 font-semibold">{user.username}</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#16212e] text-[#00e599] font-bold border border-[#00e599]/30">
                  {user.role}
                </span>
              </div>
              <button
                onClick={logout}
                className="text-slate-400 hover:text-[#ff4d4d] p-1.5 rounded hover:bg-[#121b27] transition-colors"
                title="Cerrar sesión"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <a
              href="/login"
              className="text-xs font-mono bg-[#00e599] hover:bg-[#00c985] text-slate-950 font-bold px-3 py-1.5 rounded-md transition-colors"
            >
              Acceso Terminal
            </a>
          )}
        </div>
      </div>
    </header>
  );
}
