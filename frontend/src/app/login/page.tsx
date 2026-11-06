"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  login,
  loginTelegram,
  loginTelegramWebApp,
  recoverPassword,
  resetPassword,
} from "@/lib/api";
import { useTheme } from "@/lib/theme-context";

type AuthMode = "login" | "recover_request" | "recover_reset";

export default function LoginPage() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const telegramWidgetRef = useRef<HTMLDivElement>(null);

  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Recuperación vía OTP Telegram
  const [resetCode, setResetCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [hasTelegramMiniApp, setHasTelegramMiniApp] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const tg = (window as any).Telegram?.WebApp;
    if (tg?.initData) {
      setHasTelegramMiniApp(true);
    }

    // Widget oficial de Telegram SSO si está configurado el username del bot
    const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
    if (botUsername && telegramWidgetRef.current && mode === "login") {
      (window as any).onTelegramAuth = async (tgUser: Record<string, any>) => {
        setError(null);
        setLoading(true);
        try {
          await loginTelegram(tgUser);
          router.push("/");
        } catch (err: any) {
          setError(err.message || "No se pudo autenticar con Telegram.");
        } finally {
          setLoading(false);
        }
      };

      telegramWidgetRef.current.innerHTML = "";
      const script = document.createElement("script");
      script.src = "https://telegram.org/js/telegram-widget.js?22";
      script.async = true;
      script.setAttribute("data-telegram-login", botUsername);
      script.setAttribute("data-size", "large");
      script.setAttribute("data-radius", "8");
      script.setAttribute("data-onauth", "onTelegramAuth(user)");
      script.setAttribute("data-request-access", "write");
      telegramWidgetRef.current.appendChild(script);
    }
  }, [mode, router]);

  async function handleLoginSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInfoMessage(null);

    if (!username.trim() || !password) {
      setError("Ingresa tu alias de operador y contraseña.");
      return;
    }

    setLoading(true);
    try {
      await login(username.trim(), password);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Credenciales inválidas o cuenta suspendida.");
    } finally {
      setLoading(false);
    }
  }

  async function handleTelegramMiniAppLogin() {
    const tg = (window as any).Telegram?.WebApp;
    if (!tg?.initData) return;
    setError(null);
    setLoading(true);
    try {
      await loginTelegramWebApp(tg.initData);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Error verificando firma HMAC de Telegram Mini App.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRequestOtp(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInfoMessage(null);

    if (!username.trim()) {
      setError("Ingresa tu alias de operador para enviar el código por Telegram.");
      return;
    }

    setLoading(true);
    try {
      const res = await recoverPassword(username.trim());
      setInfoMessage(
        res.message ||
          "Si el usuario tiene Telegram vinculado, se envió un código OTP de 6 dígitos."
      );
      setMode("recover_reset");
    } catch (err: any) {
      setError(err.message || "No fue posible solicitar la recuperación.");
    } finally {
      setLoading(false);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInfoMessage(null);

    if (!resetCode.trim() || newPassword.length < 8) {
      setError("Ingresa el código OTP de 6 dígitos y una contraseña de al menos 8 caracteres.");
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setError("Las nuevas contraseñas no coinciden.");
      return;
    }

    setLoading(true);
    try {
      const res = await resetPassword(username.trim(), resetCode.trim(), newPassword);
      setInfoMessage(res.message || "Contraseña actualizada exitosamente. Inicia sesión.");
      setPassword("");
      setResetCode("");
      setNewPassword("");
      setConfirmNewPassword("");
      setMode("login");
    } catch (err: any) {
      setError(err.message || "Código OTP inválido o expirado.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-on-surface flex flex-col justify-between relative overflow-hidden">
      {/* Resplandor ambiental sutil Obsidian */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[680px] h-[340px] rounded-full bg-primary-container/8 blur-[130px]" />

      {/* Barra Superior */}
      <header className="relative z-10 h-16 px-5 lg:px-10 flex items-center justify-between border-b border-[#1e2430] bg-surface/80 backdrop-blur-md">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary-container/15 border border-primary-container/30 flex items-center justify-center text-primary-container">
            <span className="material-symbols-outlined text-[18px]">bolt</span>
          </div>
          <div>
            <span className="text-sm font-bold text-white tracking-tight">
              P2P Merchant OS
            </span>
            <span className="hidden sm:inline ml-2 text-[10px] font-mono uppercase tracking-widest text-slate-400">
              Institutional Arbitrage Engine
            </span>
          </div>
        </Link>

        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-xs text-slate-400 hover:text-white flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">grid_view</span>
            <span className="hidden sm:inline">Matriz Pública</span>
          </Link>
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

      {/* Tarjeta Central de Autenticación */}
      <main className="relative z-10 flex-1 flex items-center justify-center p-4 py-10">
        <div className="w-full max-w-md rounded-2xl bg-surface-container-low border border-[#1e2430] shadow-2xl p-6 sm:p-8">
          {/* Encabezado */}
          <div className="mb-6">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary-container/10 border border-primary-container/25 text-[10px] font-mono font-semibold uppercase tracking-wider text-primary mb-3">
              <span className="material-symbols-outlined text-[14px]">lock</span>
              Terminal Segura RBAC
            </div>
            <h1 className="text-xl font-bold text-white tracking-tight">
              {mode === "login"
                ? "Acceso a la Mesa Operativa"
                : "Recuperación vía Telegram OTP"}
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              {mode === "login"
                ? "Ingresa tus credenciales de operador para gestionar spreads, órdenes y contabilidad SENIAT."
                : "Recibe un código temporal de un solo uso en tu Telegram vinculado."}
            </p>
          </div>

          {/* Alerta Condicional de Error (oculta por defecto salvo error real) */}
          {error && (
            <div className="mb-5 p-3 rounded-lg bg-error/10 border border-error/30 flex items-start gap-2.5 text-xs text-red-200">
              <span className="material-symbols-outlined text-[18px] text-error shrink-0 mt-0.5">
                gpp_maybe
              </span>
              <span>{error}</span>
            </div>
          )}

          {infoMessage && (
            <div className="mb-5 p-3 rounded-lg bg-tertiary/10 border border-tertiary/30 flex items-start gap-2.5 text-xs text-emerald-200">
              <span className="material-symbols-outlined text-[18px] text-tertiary shrink-0 mt-0.5">
                check_circle
              </span>
              <span>{infoMessage}</span>
            </div>
          )}

          {mode === "login" && (
            <>
              <form onSubmit={handleLoginSubmit} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                    Alias de Operador
                  </label>
                  <div className="relative">
                    <span className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2">
                      person
                    </span>
                    <input
                      type="text"
                      autoComplete="username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="ej. admin o trader_p2p"
                      className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white placeholder:text-slate-600 font-mono"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
                      Contraseña
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        setError(null);
                        setInfoMessage(null);
                        setMode("recover_request");
                      }}
                      className="text-[11px] text-primary hover:underline"
                    >
                      ¿Olvidaste tu contraseña?
                    </button>
                  </div>
                  <div className="relative">
                    <span className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2">
                      key
                    </span>
                    <input
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full pl-10 pr-10 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white placeholder:text-slate-600 font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                      aria-label="Mostrar u ocultar contraseña"
                    >
                      <span className="material-symbols-outlined text-[18px]">
                        {showPassword ? "visibility_off" : "visibility"}
                      </span>
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 px-4 rounded-lg bg-primary-container text-on-primary font-bold text-sm hover:brightness-110 disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-lg shadow-primary-container/10"
                >
                  <span className="material-symbols-outlined text-[18px]">login</span>
                  <span>{loading ? "Verificando..." : "Ingresar a la Terminal"}</span>
                </button>
              </form>

              {/* SSO con Telegram */}
              {hasTelegramMiniApp && (
                <div className="mt-4 pt-4 border-t border-[#1e2430]">
                  <button
                    type="button"
                    onClick={handleTelegramMiniAppLogin}
                    disabled={loading}
                    className="w-full py-2.5 px-4 rounded-lg bg-secondary/15 border border-secondary/35 text-secondary font-semibold text-xs hover:bg-secondary/25 transition-all flex items-center justify-center gap-2"
                  >
                    <span className="material-symbols-outlined text-[18px]">send</span>
                    <span>Acceso Instantáneo vía Telegram Mini App</span>
                  </button>
                </div>
              )}

              <div ref={telegramWidgetRef} className="mt-4 flex justify-center empty:hidden" />

              <div className="mt-6 pt-5 border-t border-[#1e2430] flex items-center justify-between text-xs">
                <span className="text-slate-400">¿Nuevo operador en la mesa?</span>
                <Link
                  href="/register"
                  className="font-semibold text-primary hover:underline flex items-center gap-1"
                >
                  <span>Crear Cuenta</span>
                  <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
                </Link>
              </div>
            </>
          )}

          {mode === "recover_request" && (
            <form onSubmit={handleRequestOtp} className="space-y-4">
              <div>
                <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                  Alias de Operador Registrado
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Tu usuario en P2P Merchant OS"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white font-mono"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-lg bg-primary-container text-on-primary font-bold text-sm hover:brightness-110 disabled:opacity-50 transition-all"
              >
                {loading ? "Enviando OTP..." : "Enviar Código OTP por Telegram"}
              </button>

              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setMode("login");
                }}
                className="w-full py-2 text-xs text-slate-400 hover:text-white"
              >
                ← Volver al inicio de sesión
              </button>
            </form>
          )}

          {mode === "recover_reset" && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                  Código OTP de 6 dígitos (Telegram)
                </label>
                <input
                  type="text"
                  maxLength={6}
                  value={resetCode}
                  onChange={(e) => setResetCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="000000"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-center tracking-[0.35em] text-base text-primary font-mono font-bold"
                />
              </div>

              <div>
                <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                  Nueva Contraseña
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Mínimo 8 caracteres"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white font-mono"
                />
              </div>

              <div>
                <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                  Confirmar Nueva Contraseña
                </label>
                <input
                  type="password"
                  value={confirmNewPassword}
                  onChange={(e) => setConfirmNewPassword(e.target.value)}
                  placeholder="Repite la nueva contraseña"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white font-mono"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-lg bg-tertiary text-on-tertiary font-bold text-sm hover:brightness-110 disabled:opacity-50 transition-all"
              >
                {loading ? "Actualizando..." : "Restablecer Contraseña"}
              </button>

              <button
                type="button"
                onClick={() => setMode("login")}
                className="w-full py-2 text-xs text-slate-400 hover:text-white"
              >
                ← Cancelar y volver
              </button>
            </form>
          )}
        </div>
      </main>

      {/* Pie Criptográfico */}
      <footer className="relative z-10 py-4 px-6 border-t border-[#1e2430] bg-surface/60 flex flex-wrap items-center justify-center gap-4 text-[11px] font-mono text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-tertiary" />
          AES-256-GCM Vault
        </span>
        <span>•</span>
        <span>PBKDF2-HMAC-SHA256 (600k iter)</span>
        <span>•</span>
        <span>API Oficial Binance P2P</span>
      </footer>
    </div>
  );
}
