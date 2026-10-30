"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Lock, User as UserIcon, Send, ShieldCheck, AlertCircle } from "lucide-react";
import { login, loginTelegramWebApp } from "@/lib/api";

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        ready: () => void;
        expand: () => void;
      };
    };
  }
}

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Auto-detección si se abre dentro de Telegram Mini App (TMA)
  useEffect(() => {
    if (typeof window !== "undefined" && window.Telegram?.WebApp?.initData) {
      const initData = window.Telegram.WebApp.initData;
      if (initData) {
        setIsLoading(true);
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        loginTelegramWebApp(initData)
          .then(() => {
            router.push("/");
          })
          .catch((err) => {
            setErrorMsg(`Fallo de login TMA: ${err.message}`);
          })
          .finally(() => {
            setIsLoading(false);
          });
      }
    }
  }, [router]);

  async function handleClassicLogin(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);
    try {
      await login(username, password);
      router.push("/");
    } catch (err: any) {
      setErrorMsg(err.message || "Credenciales incorrectas.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="max-w-md mx-auto my-8 glass-panel p-6 sm:p-8 rounded-3xl border border-slate-800 space-y-6">
      <div className="pb-2 border-b border-slate-800 flex justify-between items-center">
        <a
          href="/"
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-rose-400 hover:text-rose-300 transition-colors"
        >
          <span>← Volver a la App</span>
        </a>
      </div>
      <div className="text-center space-y-2">
        <div className="inline-flex p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 mb-1">
          <ShieldCheck className="h-8 w-8" />
        </div>
        <h1 className="font-mono text-xl font-bold text-slate-100 tracking-wide">
          ACCESO AL SISTEMA
        </h1>
        <p className="text-xs text-slate-400 font-mono">
          Terminal Multi-Usuario P2P Merchant
        </p>
      </div>

      {errorMsg && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-mono flex items-center space-x-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Formulario clásico de acceso */}
      <form onSubmit={handleClassicLogin} className="space-y-4 text-xs font-mono">
        <div>
          <label className="block text-slate-400 mb-1 font-semibold">USUARIO</label>
          <div className="relative">
            <UserIcon className="h-4 w-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
              placeholder="admin / trader"
            />
          </div>
        </div>

        <div>
          <label className="block text-slate-400 mb-1 font-semibold">CONTRASEÑA</label>
          <div className="relative">
            <Lock className="h-4 w-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
              placeholder="••••••••••••"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-800 text-slate-950 font-bold font-mono text-xs transition-colors"
        >
          {isLoading ? "Validando credenciales..." : "Ingresar con Contraseña"}
        </button>
      </form>

      {/* Separador */}
      <div className="relative flex py-2 items-center">
        <div className="flex-grow border-t border-slate-800"></div>
        <span className="flex-shrink mx-4 text-slate-500 text-[10px] font-mono uppercase">
          o acceso instantáneo
        </span>
        <div className="flex-grow border-t border-slate-800"></div>
      </div>

      {/* Botón de inicio con Telegram */}
      <div className="space-y-2 text-center">
        <p className="text-[11px] text-slate-400 font-mono mb-2">
          Autentícate con tu cuenta autorizada de Telegram
        </p>

        <div className="p-3 bg-sky-500/10 border border-sky-500/20 rounded-xl flex items-center justify-center space-x-2 text-sky-400 font-mono text-xs">
          <Send className="h-4 w-4" />
          <span>Telegram SSO & Mini App Activo</span>
        </div>
      </div>
    </div>
  );
}
