"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Lock,
  User as UserIcon,
  Send,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  KeyRound,
  UserPlus,
  LogIn,
  HelpCircle,
  ArrowLeft,
} from "lucide-react";
import {
  login,
  loginTelegramWebApp,
  registerUser,
  recoverPassword,
  resetPassword,
} from "@/lib/api";

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

type AuthTab = "login" | "register" | "recovery";

export default function LoginPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<AuthTab>("login");

  // Campos de formulario
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [telegramId, setTelegramId] = useState("");

  // Campos de recuperación
  const [recoveryCode, setRecoveryCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [recoveryStep, setRecoveryStep] = useState<1 | 2>(1);

  // Estados de interfaz
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

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
          .catch((err: any) => {
            setErrorMsg(`Fallo de login TMA: ${err.message}`);
          })
          .finally(() => {
            setIsLoading(false);
          });
      }
    }
  }, [router]);

  function resetFormFeedback() {
    setErrorMsg(null);
    setSuccessMsg(null);
  }

  // 1. Manejo de Inicio de Sesión
  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    resetFormFeedback();
    try {
      await login(username.trim(), password);
      router.push("/");
    } catch (err: any) {
      setErrorMsg(err.message || "Usuario o contraseña incorrectos.");
    } finally {
      setIsLoading(false);
    }
  }

  // 2. Manejo de Registro de Usuario
  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    resetFormFeedback();

    if (password.length < 8) {
      setErrorMsg("La contraseña debe contener al menos 8 caracteres.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMsg("Las contraseñas ingresadas no coinciden.");
      return;
    }

    setIsLoading(true);
    try {
      await registerUser({
        username: username.trim(),
        password,
        telegram_id: telegramId.trim() || undefined,
      });
      setSuccessMsg("¡Cuenta creada exitosamente! Ingresando al panel...");
      setTimeout(() => {
        router.push("/");
      }, 1000);
    } catch (err: any) {
      setErrorMsg(err.message || "Error al crear la cuenta. Verifica los datos.");
    } finally {
      setIsLoading(false);
    }
  }

  // 3. Manejo de Envío de Código OTP
  async function handleRequestRecoveryOtp(e: React.FormEvent) {
    e.preventDefault();
    resetFormFeedback();
    if (!username.trim()) {
      setErrorMsg("Ingresa tu nombre de usuario o Telegram ID.");
      return;
    }

    setIsLoading(true);
    try {
      const res = await recoverPassword(username.trim());
      setSuccessMsg(res.message);
      if (res.debug_code) {
        // En desarrollo local o sin bot configurado
        setRecoveryCode(res.debug_code);
      }
      setRecoveryStep(2);
    } catch (err: any) {
      setErrorMsg(err.message || "No se pudo despachar el código de recuperación.");
    } finally {
      setIsLoading(false);
    }
  }

  // 4. Manejo de Confirmación de Nueva Contraseña con OTP
  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    resetFormFeedback();

    if (newPassword.length < 8) {
      setErrorMsg("La nueva contraseña debe tener al menos 8 caracteres.");
      return;
    }

    setIsLoading(true);
    try {
      const res = await resetPassword(username.trim(), recoveryCode.trim(), newPassword);
      setSuccessMsg(res.message);
      setTimeout(() => {
        setActiveTab("login");
        setRecoveryStep(1);
        setPassword("");
        resetFormFeedback();
      }, 1500);
    } catch (err: any) {
      setErrorMsg(err.message || "Código inválido o expirado.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-[85vh] flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl backdrop-blur-md space-y-6">
        {/* Cabecera superior con retorno */}
        <div className="flex justify-between items-center pb-2 border-b border-slate-800/80">
          <a
            href="/"
            className="inline-flex items-center space-x-1.5 text-xs font-semibold text-rose-400 hover:text-rose-300 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Volver a la Terminal</span>
          </a>
          <span className="text-[11px] font-mono text-slate-500 uppercase tracking-widest">
            v2.0 P2P Bot
          </span>
        </div>

        {/* Título e Icono */}
        <div className="text-center space-y-2">
          <div className="inline-flex p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mb-1 shadow-inner">
            <ShieldCheck className="h-8 w-8" />
          </div>
          <h1 className="text-xl font-bold font-mono tracking-wide text-slate-100">
            SISTEMA P2P MERCHANT
          </h1>
          <p className="text-xs text-slate-400 font-sans">
            Autenticación segura multi-usuario con arquitectura Fail-Closed
          </p>
        </div>

        {/* Switcher de Pestañas: Iniciar Sesión / Crear Cuenta */}
        {activeTab !== "recovery" && (
          <div className="grid grid-cols-2 p-1 bg-slate-950/80 border border-slate-800 rounded-2xl text-xs font-semibold">
            <button
              type="button"
              onClick={() => {
                setActiveTab("login");
                resetFormFeedback();
              }}
              className={`py-2.5 rounded-xl transition-all flex items-center justify-center space-x-2 ${
                activeTab === "login"
                  ? "bg-slate-800 text-emerald-400 shadow-md font-bold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <LogIn className="h-3.5 w-3.5" />
              <span>Iniciar Sesión</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab("register");
                resetFormFeedback();
              }}
              className={`py-2.5 rounded-xl transition-all flex items-center justify-center space-x-2 ${
                activeTab === "register"
                  ? "bg-slate-800 text-emerald-400 shadow-md font-bold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <UserPlus className="h-3.5 w-3.5" />
              <span>Crear Cuenta</span>
            </button>
          </div>
        )}

        {/* Notificaciones de Error o Éxito */}
        {errorMsg && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-start space-x-2.5">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-start space-x-2.5">
            <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-emerald-400" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* TAB 1: FORMULARIO INICIAR SESIÓN */}
        {activeTab === "login" && (
          <form onSubmit={handleLogin} className="space-y-4 text-xs font-mono">
            <div>
              <label className="block text-slate-300 mb-1.5 font-semibold">
                NOMBRE DE USUARIO
              </label>
              <div className="relative">
                <UserIcon className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoComplete="username"
                  className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors"
                  placeholder="admin / trader"
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-slate-300 font-semibold">CONTRASEÑA</label>
                <button
                  type="button"
                  onClick={() => {
                    setActiveTab("recovery");
                    resetFormFeedback();
                  }}
                  className="text-[11px] text-emerald-400 hover:text-emerald-300 underline font-sans"
                >
                  ¿Olvidaste tu contraseña?
                </button>
              </div>
              <div className="relative">
                <Lock className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors"
                  placeholder="••••••••••••"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-800 text-slate-950 font-bold font-mono text-xs transition-all shadow-lg shadow-emerald-500/20 active:scale-[0.99]"
            >
              {isLoading ? "Validando credenciales..." : "Ingresar a la Terminal"}
            </button>
          </form>
        )}

        {/* TAB 2: FORMULARIO CREAR CUENTA (REGISTRO) */}
        {activeTab === "register" && (
          <form onSubmit={handleRegister} className="space-y-4 text-xs font-mono">
            <div>
              <label className="block text-slate-300 mb-1.5 font-semibold">
                NUEVO USUARIO
              </label>
              <div className="relative">
                <UserIcon className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors"
                  placeholder="Elige un alias (ej: trader_caracas)"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-300 mb-1.5 font-semibold">
                CONTRASEÑA (MÍNIMO 8 CARACTERES)
              </label>
              <div className="relative">
                <Lock className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors"
                  placeholder="••••••••••••"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-300 mb-1.5 font-semibold">
                CONFIRMAR CONTRASEÑA
              </label>
              <div className="relative">
                <Lock className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors"
                  placeholder="Repite la contraseña"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-300 mb-1.5 font-semibold flex justify-between">
                <span>TELEGRAM ID NUMÉRICO (OPCIONAL)</span>
                <span className="text-[10px] text-slate-500 font-normal">Para alertas y OTP</span>
              </label>
              <div className="relative">
                <Send className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="text"
                  value={telegramId}
                  onChange={(e) => setTelegramId(e.target.value)}
                  className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors"
                  placeholder="Ej: 123456789"
                />
              </div>
              <p className="text-[10px] text-slate-500 mt-1 font-sans">
                Si tu ID está en la lista de administradores, se te otorgará rol ADMIN automáticamente.
              </p>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-800 text-slate-950 font-bold font-mono text-xs transition-all shadow-lg shadow-emerald-500/20 active:scale-[0.99]"
            >
              {isLoading ? "Creando cuenta..." : "Crear Cuenta de Usuario"}
            </button>
          </form>
        )}

        {/* TAB 3: RECUPERACIÓN DE CONTRASEÑA VÍA TELEGRAM OTP */}
        {activeTab === "recovery" && (
          <div className="space-y-4 text-xs font-mono">
            <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-2xl flex items-center justify-between">
              <span className="font-semibold text-slate-300">Recuperar Acceso</span>
              <button
                type="button"
                onClick={() => {
                  setActiveTab("login");
                  resetFormFeedback();
                }}
                className="text-[11px] text-slate-400 hover:text-slate-200"
              >
                Volver a Iniciar Sesión
              </button>
            </div>

            {recoveryStep === 1 ? (
              <form onSubmit={handleRequestRecoveryOtp} className="space-y-4">
                <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
                  Ingresa tu nombre de usuario o tu ID numérico de Telegram vinculado. Te enviaremos un código de seguridad OTP de 6 dígitos.
                </p>

                <div>
                  <label className="block text-slate-300 mb-1.5 font-semibold">
                    USUARIO O TELEGRAM ID
                  </label>
                  <div className="relative">
                    <UserIcon className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                      className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
                      placeholder="Nombre de usuario o ID"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-3 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:bg-slate-800 text-slate-950 font-bold font-mono text-xs transition-all"
                >
                  {isLoading ? "Despachando código..." : "Enviar Código OTP a Telegram"}
                </button>
              </form>
            ) : (
              <form onSubmit={handleResetPassword} className="space-y-4">
                <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
                  Ingresa el código OTP de 6 dígitos que recibiste y define tu nueva contraseña.
                </p>

                <div>
                  <label className="block text-slate-300 mb-1.5 font-semibold">
                    CÓDIGO OTP (6 DÍGITOS)
                  </label>
                  <div className="relative">
                    <KeyRound className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
                    <input
                      type="text"
                      maxLength={6}
                      value={recoveryCode}
                      onChange={(e) => setRecoveryCode(e.target.value)}
                      required
                      className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-slate-200 font-mono tracking-widest text-base focus:outline-none focus:border-emerald-500"
                      placeholder="123456"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-300 mb-1.5 font-semibold">
                    NUEVA CONTRASEÑA
                  </label>
                  <div className="relative">
                    <Lock className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
                    <input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      required
                      className="w-full bg-slate-950/70 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-slate-200 focus:outline-none focus:border-emerald-500"
                      placeholder="••••••••••••"
                    />
                  </div>
                </div>

                <div className="flex space-x-2">
                  <button
                    type="button"
                    onClick={() => setRecoveryStep(1)}
                    className="w-1/3 py-2.5 rounded-xl border border-slate-800 text-slate-400 hover:text-slate-200 font-mono text-xs"
                  >
                    Atrás
                  </button>
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-2/3 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-800 text-slate-950 font-bold font-mono text-xs transition-all shadow-md"
                  >
                    {isLoading ? "Actualizando..." : "Restablecer"}
                  </button>
                </div>
              </form>
            )}
          </div>
        )}

        {/* Separador */}
        <div className="relative flex py-1 items-center">
          <div className="flex-grow border-t border-slate-800"></div>
          <span className="flex-shrink mx-4 text-slate-500 text-[10px] font-mono uppercase tracking-wider">
            Canales de acceso seguro
          </span>
          <div className="flex-grow border-t border-slate-800"></div>
        </div>

        {/* Banner de Telegram SSO y Bot */}
        <div className="p-3.5 bg-sky-500/10 border border-sky-500/20 rounded-2xl flex items-center justify-between text-sky-400 text-xs font-mono">
          <div className="flex items-center space-x-2.5">
            <Send className="h-4 w-4 shrink-0" />
            <div>
              <p className="font-bold text-[11px]">Telegram SSO / Mini App</p>
              <p className="text-[10px] text-slate-400 font-sans">
                Acceso sin contraseña mediante el bot oficial
              </p>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-sky-500/20 border border-sky-500/40 text-[10px] font-bold text-sky-300">
            EN LÍNEA
          </span>
        </div>
      </div>
    </div>
  );
}
