"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  RecoveryMethod,
  RecoveryOptions,
  getRecoveryOptions,
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

  // Recuperación Multi-Método (Telegram OTP / Pregunta Secreta / Llave Maestra)
  const [recoveryMethod, setRecoveryMethod] = useState<RecoveryMethod>("email_otp");
  const [showOtherMethods, setShowOtherMethods] = useState(false);
  const [recoveryOptions, setRecoveryOptions] = useState<RecoveryOptions | null>(null);
  const [rotatedRecoveryKey, setRotatedRecoveryKey] = useState<string | null>(null);
  const [resetCode, setResetCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  function clearLoginFieldError(field: string) {
    setFieldErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  function validateLoginField(field: string): string {
    let msg = "";
    if (field === "username") {
      const val = username.trim();
      if (val.length < 3) {
        msg = "Ingresa tu alias, correo electrónico o Telegram ID (mínimo 3 caracteres).";
      } else if (/\s/.test(val)) {
        msg = "El identificador no debe contener espacios.";
      }
    } else if (field === "password") {
      if (!password || password.length < 6) {
        msg = "La contraseña debe tener al menos 6 caracteres.";
      }
    } else if (field === "resetCode") {
      const val = resetCode.trim();
      if (recoveryMethod === "telegram_otp" && !/^\d{6}$/.test(val)) {
        msg = "El código OTP debe tener exactamente 6 dígitos numéricos.";
      } else if (recoveryMethod === "security_question" && val.length < 3) {
        msg = "La respuesta secreta debe tener al menos 3 caracteres.";
      } else if (recoveryMethod === "recovery_key" && val.length < 8) {
        msg = "Ingresa la Llave Maestra completa (P2P-XXXX-XXXX-XXXX).";
      }
    } else if (field === "newPassword") {
      if (newPassword.length < 8) {
        msg = "La nueva contraseña debe tener mínimo 8 caracteres.";
      }
    } else if (field === "confirmNewPassword") {
      if (!confirmNewPassword || confirmNewPassword !== newPassword) {
        msg = "Las nuevas contraseñas no coinciden.";
      }
    }

    setFieldErrors((prev) => {
      if (!msg && !prev[field]) return prev;
      const next = { ...prev };
      if (msg) next[field] = msg;
      else delete next[field];
      return next;
    });
    return msg;
  }
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
          window.location.assign("/");
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
      window.location.assign("/");
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
      window.location.assign("/");
    } catch (err: any) {
      setError(err.message || "Error verificando firma HMAC de Telegram Mini App.");
    } finally {
      setLoading(false);
    }
  }

  async function handleInspectRecoveryOptions(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInfoMessage(null);
    setRotatedRecoveryKey(null);

    if (!username.trim()) {
      setError("Ingresa tu alias, correo electrónico o ID de Telegram.");
      return;
    }

    setLoading(true);
    try {
      const opts = await getRecoveryOptions(username.trim());
      setRecoveryOptions(opts);
      if (opts.is_locked) {
        setError(
          "Esta cuenta se encuentra bloqueada temporalmente por múltiples intentos fallidos de recuperación (15 min)."
        );
        return;
      }

      setShowOtherMethods(false);
      if (opts.has_email) {
        setRecoveryMethod("email_otp");
        const res = await recoverPassword(username.trim(), "email");
        if (res.success) {
          setInfoMessage(
            res.message || "Código OTP de 6 dígitos enviado a tu correo vinculado."
          );
        } else {
          setError(res.message || "No se pudo enviar el código por correo.");
        }
      } else if (opts.has_telegram) {
        setRecoveryMethod("telegram_otp");
        const res = await recoverPassword(username.trim(), "telegram");
        if (res.success && res.has_telegram) {
          setInfoMessage(
            res.message ||
              "Se envió un código OTP de 6 dígitos a tu Telegram vinculado."
          );
        } else {
          setError(
            res.message ||
              "No se pudo conectar con Telegram (timeout de red). Usa Pregunta Secreta o Llave Maestra."
          );
        }
      } else if (opts.has_security_question) {
        setRecoveryMethod("security_question");
      } else if (opts.has_recovery_key) {
        setRecoveryMethod("recovery_key");
      } else {
        setRecoveryMethod("email_otp");
        setInfoMessage(
          "Si el perfil existe y dispone de métodos configurados, elige el método de verificación abajo."
        );
      }
      setResetCode("");
      setMode("recover_reset");
    } catch (err: any) {
      setError(err.message || "No fue posible consultar las opciones de recuperación.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSendEmailOtp() {
    setError(null);
    setInfoMessage(null);
    setLoading(true);
    try {
      const res = await recoverPassword(username.trim(), "email");
      if (res.success) {
        setInfoMessage(
          res.message || "Código OTP de 6 dígitos enviado a tu correo vinculado."
        );
      } else {
        setError(res.message || "No se pudo enviar el código OTP por correo.");
      }
    } catch (err: any) {
      setError(err.message || "No se pudo enviar el código OTP por correo.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSendTelegramOtp() {
    setError(null);
    setInfoMessage(null);
    setLoading(true);
    try {
      const res = await recoverPassword(username.trim());
      if (res.success && res.has_telegram) {
        setInfoMessage(
          res.message ||
            "Código OTP de 6 dígitos enviado a tu Telegram vinculado."
        );
      } else {
        setError(
          res.message ||
            "No se pudo enviar el código OTP porque api.telegram.org no respondió (timeout / bloqueo de ISP). Usa Pregunta Secreta o Llave Maestra."
        );
      }
    } catch (err: any) {
      setError(err.message || "No se pudo enviar el código OTP por Telegram.");
    } finally {
      setLoading(false);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInfoMessage(null);

    if (!resetCode.trim() || newPassword.length < 8) {
      setError(
        "Completa la verificación requerida y define una contraseña de al menos 8 caracteres."
      );
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setError("Las nuevas contraseñas no coinciden.");
      return;
    }

    setLoading(true);
    try {
      const res = await resetPassword(
        username.trim(),
        resetCode.trim(),
        newPassword,
        recoveryMethod
      );
      setInfoMessage(res.message || "Contraseña actualizada exitosamente. Inicia sesión.");
      if (res.new_recovery_key) {
        setRotatedRecoveryKey(res.new_recovery_key);
      }
      setPassword("");
      setResetCode("");
      setNewPassword("");
      setConfirmNewPassword("");
      setMode("login");
    } catch (err: any) {
      setError(err.message || "Verificación fallida o código expirado.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-on-surface flex flex-col justify-between relative overflow-x-hidden">
      {/* Resplandor ambiental sutil Obsidian */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[680px] h-[340px] rounded-full bg-primary-container/8 blur-[130px]" />

      {/* Barra Superior */}
      <header className="sticky top-0 z-20 h-16 px-5 lg:px-10 flex items-center justify-between border-b border-[#1e2430] bg-surface/85 backdrop-blur-md">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary-container/15 border border-primary-container/30 flex items-center justify-center text-primary-container">
            <span className="material-symbols-outlined text-[18px]" aria-hidden="true">bolt</span>
          </div>
          <span className="text-sm font-bold text-white tracking-tight">
            Sistema P2P
          </span>
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
            <h1 className="text-xl font-bold text-white tracking-tight">
              {mode === "login"
                ? "Iniciar sesión"
                : "Recuperar acceso"}
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              {mode === "login"
                ? "Ingresa con tu usuario y contraseña."
                : "Elige un método para restablecer tu contraseña."}
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

          {rotatedRecoveryKey && (
            <div className="mb-5 p-3.5 rounded-lg bg-primary-container/10 border border-primary-container/35 text-xs space-y-1.5">
              <div className="font-mono font-bold text-primary uppercase text-[10px]">
                Nueva Llave Maestra Rotada (Guárdala):
              </div>
              <div className="font-mono font-bold text-white tracking-wider select-all">
                {rotatedRecoveryKey}
              </div>
              <button
                type="button"
                onClick={() => navigator.clipboard?.writeText(rotatedRecoveryKey)}
                className="text-[11px] font-mono text-primary hover:underline"
              >
                Copiar nueva llave
              </button>
            </div>
          )}

          {mode === "login" && (
            <>
              <form onSubmit={handleLoginSubmit} className="space-y-4">
                <div>
                  <label
                    htmlFor="login-username"
                    className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
                  >
                    Usuario o correo
                  </label>
                  <div className="relative">
                    <span className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2">
                      person
                    </span>
                    <input
                      id="login-username"
                      type="text"
                      required
                      autoComplete="username"
                      autoCorrect="off"
                      autoCapitalize="none"
                      spellCheck={false}
                      enterKeyHint="next"
                      aria-invalid={Boolean(fieldErrors.username)}
                      aria-describedby={fieldErrors.username ? "login-username-err" : undefined}
                      value={username}
                      onChange={(e) => {
                        setUsername(e.target.value.replace(/\s+/g, ""));
                        clearLoginFieldError("username");
                      }}
                      onBlur={() => validateLoginField("username")}
                      placeholder="ej. admin, correo@gmail.com o ID"
                      className={`w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-sm text-white placeholder:text-slate-600 font-mono ${
                        fieldErrors.username
                          ? "border-error focus:border-error"
                          : "border-[#1e2430] focus:border-primary-container"
                      }`}
                    />
                  </div>
                  {fieldErrors.username && (
                    <p id="login-username-err" className="text-[10px] text-error mt-1">
                      {fieldErrors.username}
                    </p>
                  )}
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label
                      htmlFor="login-password"
                      className="text-[11px] font-mono uppercase tracking-wider text-slate-400"
                    >
                      Contraseña
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        setError(null);
                        setInfoMessage(null);
                        setFieldErrors({});
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
                      id="login-password"
                      type={showPassword ? "text" : "password"}
                      required
                      minLength={6}
                      autoComplete="current-password"
                      enterKeyHint="done"
                      aria-invalid={Boolean(fieldErrors.password)}
                      aria-describedby={fieldErrors.password ? "login-password-err" : undefined}
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        clearLoginFieldError("password");
                      }}
                      onBlur={() => validateLoginField("password")}
                      placeholder="••••••••••••"
                      className={`w-full pl-10 pr-10 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-sm text-white placeholder:text-slate-600 font-mono ${
                        fieldErrors.password
                          ? "border-error focus:border-error"
                          : "border-[#1e2430] focus:border-primary-container"
                      }`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-pressed={showPassword}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                      aria-label="Mostrar u ocultar contraseña"
                    >
                      <span className="material-symbols-outlined text-[18px]">
                        {showPassword ? "visibility_off" : "visibility"}
                      </span>
                    </button>
                  </div>
                  {fieldErrors.password && (
                    <p id="login-password-err" className="text-[10px] text-error mt-1">
                      {fieldErrors.password}
                    </p>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 px-4 rounded-lg bg-primary-container text-on-primary font-bold text-sm hover:brightness-110 disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-lg shadow-primary-container/10"
                >
                  <span className="material-symbols-outlined text-[18px]" aria-hidden="true">login</span>
                  <span>{loading ? "Verificando..." : "Iniciar sesión"}</span>
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
                    <span>Acceso vía Telegram</span>
                  </button>
                </div>
              )}

              <div ref={telegramWidgetRef} className="mt-4 flex justify-center empty:hidden" />

              <div className="mt-6 pt-5 border-t border-[#1e2430] flex items-center justify-between text-xs">
                <span className="text-slate-400">¿No tienes cuenta?</span>
                <Link
                  href="/register"
                  className="font-semibold text-primary hover:underline flex items-center gap-1"
                >
                  <span>Crear cuenta</span>
                  <span className="material-symbols-outlined text-[15px]" aria-hidden="true">arrow_forward</span>
                </Link>
              </div>
            </>
          )}

          {mode === "recover_request" && (
            <form onSubmit={handleInspectRecoveryOptions} className="space-y-4">
              <div>
                <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                  Alias, Correo Electrónico o Telegram ID
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="ej. trader_caracas o correo@ejemplo.com"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white font-mono"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-lg bg-primary-container text-on-primary font-bold text-sm hover:brightness-110 disabled:opacity-50 transition-all"
              >
                {loading ? "Consultando métodos..." : "Continuar con Recuperación Segura"}
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
              {recoveryMethod === "email_otp" && (
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <label
                      htmlFor="login-email-otp"
                      className="text-[11px] font-mono uppercase tracking-wider text-slate-400"
                    >
                      Código OTP por Correo (6 dígitos)
                    </label>
                    <button
                      type="button"
                      onClick={handleSendEmailOtp}
                      disabled={loading}
                      className="text-[11px] font-mono text-primary hover:underline disabled:opacity-50"
                    >
                      Enviar / Reenviar
                    </button>
                  </div>
                  <input
                    id="login-email-otp"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    required
                    value={resetCode}
                    onChange={(e) => {
                      setResetCode(e.target.value.replace(/\D/g, "").slice(0, 6));
                      clearLoginFieldError("resetCode");
                    }}
                    placeholder="000000"
                    className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm font-mono tracking-[0.25em] text-white"
                  />
                </div>
              )}

              {recoveryMethod === "security_question" && (
                <div className="space-y-2">
                  <div className="p-2.5 rounded-lg bg-surface-container border border-[#1e2430] text-xs text-slate-200">
                    <span className="block text-[10px] font-mono uppercase text-primary mb-0.5">
                      Pregunta de Seguridad Configurada:
                    </span>
                    {recoveryOptions?.security_question ||
                      "Ingresa la respuesta de tu pregunta secreta registrada."}
                  </div>
                  <div>
                    <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                      Tu Respuesta Secreta
                    </label>
                    <input
                      type="text"
                      value={resetCode}
                      onChange={(e) => setResetCode(e.target.value)}
                      placeholder="Escribe tu respuesta..."
                      className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white font-mono"
                    />
                  </div>
                </div>
              )}

              {recoveryMethod === "recovery_key" && (
                <div>
                  <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                    Llave Maestra de Respaldo (P2P-XXXX-XXXX-XXXX)
                  </label>
                  <input
                    type="text"
                    value={resetCode}
                    onChange={(e) => setResetCode(e.target.value.toUpperCase())}
                    placeholder="P2P-XXXX-XXXX-XXXX"
                    className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-center tracking-widest text-sm text-primary font-mono font-bold"
                  />
                </div>
              )}

              {recoveryMethod === "telegram_otp" && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label
                      htmlFor="login-otp"
                      className="block text-[11px] font-mono uppercase tracking-wider text-slate-400"
                    >
                      Código OTP de 6 dígitos (Telegram)
                    </label>
                    <button
                      type="button"
                      onClick={handleSendTelegramOtp}
                      disabled={loading}
                      className="text-[11px] font-mono text-secondary hover:underline"
                    >
                      Enviar / Reenviar OTP
                    </button>
                  </div>
                  <input
                    id="login-otp"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    autoCorrect="off"
                    autoCapitalize="none"
                    spellCheck={false}
                    enterKeyHint="next"
                    maxLength={6}
                    aria-invalid={Boolean(fieldErrors.resetCode)}
                    value={resetCode}
                    onChange={(e) => {
                      setResetCode(e.target.value.replace(/\D/g, "").slice(0, 6));
                      clearLoginFieldError("resetCode");
                    }}
                    onBlur={() => validateLoginField("resetCode")}
                    placeholder="000000"
                    className={`w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-center tracking-[0.35em] text-base text-primary font-mono font-bold ${
                      fieldErrors.resetCode
                        ? "border-error focus:border-error"
                        : "border-[#1e2430] focus:border-primary-container"
                    }`}
                  />
                  {fieldErrors.resetCode && (
                    <p className="text-[10px] text-error mt-1">{fieldErrors.resetCode}</p>
                  )}
                </div>
              )}

              <div>
                <button
                  type="button"
                  onClick={() => setShowOtherMethods((prev) => !prev)}
                  className="text-xs font-mono text-primary hover:underline cursor-pointer"
                >
                  {showOtherMethods ? "Ocultar otros métodos" : "Probar otra manera"}
                </button>
                {showOtherMethods && (
                  <div className="mt-2 grid grid-cols-2 gap-1.5 p-1.5 rounded-lg bg-surface-container border border-[#1e2430] text-[10px] font-mono">
                    {(
                      [
                        ["email_otp", "OTP Correo"],
                        ["telegram_otp", "OTP Telegram"],
                        ["security_question", "Pregunta Secreta"],
                        ["recovery_key", "Llave Maestra"],
                      ] as Array<[RecoveryMethod, string]>
                    )
                      .filter(([id]) => id !== recoveryMethod)
                      .map(([id, label]) => (
                        <button
                          key={id}
                          type="button"
                          onClick={() => {
                            setRecoveryMethod(id);
                            setResetCode("");
                            setError(null);
                            setInfoMessage(null);
                            setShowOtherMethods(false);
                          }}
                          className="py-1.5 px-2 rounded text-slate-300 hover:text-white hover:bg-surface-container-low transition-colors text-left"
                        >
                          {label}
                        </button>
                      ))}
                  </div>
                )}
              </div>

              <div>
                <label
                  htmlFor="login-new-password"
                  className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
                >
                  Nueva Contraseña
                </label>
                <input
                  id="login-new-password"
                  type="password"
                  minLength={8}
                  autoComplete="new-password"
                  enterKeyHint="next"
                  aria-invalid={Boolean(fieldErrors.newPassword)}
                  value={newPassword}
                  onChange={(e) => {
                    setNewPassword(e.target.value);
                    clearLoginFieldError("newPassword");
                  }}
                  onBlur={() => validateLoginField("newPassword")}
                  placeholder="Mínimo 8 caracteres"
                  className={`w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-sm text-white font-mono ${
                    fieldErrors.newPassword
                      ? "border-error focus:border-error"
                      : "border-[#1e2430] focus:border-primary-container"
                  }`}
                />
                {fieldErrors.newPassword && (
                  <p className="text-[10px] text-error mt-1">{fieldErrors.newPassword}</p>
                )}
              </div>

              <div>
                <label
                  htmlFor="login-confirm-new-password"
                  className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
                >
                  Confirmar Nueva Contraseña
                </label>
                <input
                  id="login-confirm-new-password"
                  type="password"
                  minLength={8}
                  autoComplete="new-password"
                  enterKeyHint="done"
                  aria-invalid={Boolean(fieldErrors.confirmNewPassword)}
                  value={confirmNewPassword}
                  onChange={(e) => {
                    setConfirmNewPassword(e.target.value);
                    clearLoginFieldError("confirmNewPassword");
                  }}
                  onBlur={() => validateLoginField("confirmNewPassword")}
                  placeholder="Repite la nueva contraseña"
                  className={`w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-sm text-white font-mono ${
                    fieldErrors.confirmNewPassword
                      ? "border-error focus:border-error"
                      : "border-[#1e2430] focus:border-primary-container"
                  }`}
                />
                {fieldErrors.confirmNewPassword && (
                  <p className="text-[10px] text-error mt-1">{fieldErrors.confirmNewPassword}</p>
                )}
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
    </div>
  );
}
