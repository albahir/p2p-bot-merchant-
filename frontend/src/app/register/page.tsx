"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { registerUser } from "@/lib/api";
import { useTheme } from "@/lib/theme-context";

function computePasswordStrength(pw: string): {
  score: number;
  label: string;
  colorClass: string;
} {
  if (!pw) return { score: 0, label: "Sin definir", colorClass: "bg-slate-700" };
  let score = 0;
  if (pw.length >= 8) score += 1;
  if (pw.length >= 12) score += 1;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score += 1;
  if (/\d/.test(pw) || /[^A-Za-z0-9]/.test(pw)) score += 1;

  if (score <= 1) return { score: 1, label: "Débil", colorClass: "bg-error" };
  if (score === 2) return { score: 2, label: "Aceptable", colorClass: "bg-primary-container" };
  if (score === 3) return { score: 3, label: "Fuerte", colorClass: "bg-secondary" };
  return { score: 4, label: "Institucional", colorClass: "bg-tertiary" };
}

export default function RegisterPage() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();

  const [username, setUsername] = useState("");
  const [telegramId, setTelegramId] = useState("");
  const [googleSheetId, setGoogleSheetId] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const strength = useMemo(() => computePasswordStrength(password), [password]);
  const isTelegramValid = useMemo(
    () => telegramId.trim().length >= 5 && /^\d+$/.test(telegramId.trim()),
    [telegramId]
  );
  const passwordsMatch =
    password.length > 0 && confirmPassword.length > 0 && password === confirmPassword;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (username.trim().length < 3) {
      setError("El alias de operador debe tener al menos 3 caracteres.");
      return;
    }
    if (password.length < 8) {
      setError("La contraseña debe tener mínimo 8 caracteres.");
      return;
    }
    if (password !== confirmPassword) {
      setError("La confirmación de contraseña no coincide.");
      return;
    }
    if (telegramId.trim() && !/^\d+$/.test(telegramId.trim())) {
      setError("El ID de Telegram debe contener únicamente dígitos numéricos.");
      return;
    }

    setLoading(true);
    try {
      await registerUser({
        username: username.trim(),
        password,
        telegram_id: telegramId.trim() || undefined,
        google_sheet_id: googleSheetId.trim() || undefined,
      });
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Error al crear la cuenta de operador.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-on-surface flex flex-col justify-between relative overflow-hidden">
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[720px] h-[360px] rounded-full bg-secondary/6 blur-[140px]" />

      {/* Topbar */}
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
              Registro de Operadores
            </span>
          </div>
        </Link>

        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="text-xs text-slate-400 hover:text-white transition-colors"
          >
            Ya tengo cuenta
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

      {/* Tarjeta Central (rounded-2xl corregido) */}
      <main className="relative z-10 flex-1 flex items-center justify-center p-4 py-8">
        <div className="w-full max-w-xl rounded-2xl bg-surface-container-low border border-[#1e2430] shadow-2xl p-6 sm:p-8">
          <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-tertiary/12 border border-tertiary/30 text-[10px] font-mono font-semibold uppercase tracking-wider text-tertiary mb-2.5">
                <span className="material-symbols-outlined text-[14px]">person_add</span>
                Alta de Operador P2P
              </div>
              <h1 className="text-xl font-bold text-white tracking-tight">
                Crear Cuenta de Operador
              </h1>
              <p className="text-xs text-slate-400 mt-1">
                Vincula tu ID de Telegram para heredar permisos TRADER/ADMIN autorizados y alertas BCV.
              </p>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] text-right">
              <div className="text-[9px] font-mono uppercase text-slate-400">Moneda Base</div>
              <div className="text-xs font-mono font-bold text-primary">VES (Bolívar)</div>
            </div>
          </div>

          {error && (
            <div className="mb-5 p-3 rounded-lg bg-error/10 border border-error/30 flex items-start gap-2.5 text-xs text-red-200">
              <span className="material-symbols-outlined text-[18px] text-error shrink-0 mt-0.5">
                error
              </span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Alias */}
              <div>
                <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                  Alias de Operador *
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2">
                    badge
                  </span>
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="ej. trader_caracas"
                    className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white font-mono placeholder:text-slate-600"
                  />
                </div>
              </div>

              {/* Telegram ID */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
                    Telegram ID (Numérico)
                  </label>
                  {isTelegramValid && (
                    <span className="text-[10px] font-mono text-tertiary flex items-center gap-0.5">
                      <span className="material-symbols-outlined text-[13px]">verified</span>
                      Formato válido
                    </span>
                  )}
                </div>
                <div className="relative">
                  <span className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2">
                    send
                  </span>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={telegramId}
                    onChange={(e) => setTelegramId(e.target.value.replace(/\s+/g, ""))}
                    placeholder="ej. 6326947793"
                    className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-secondary focus:outline-hidden text-sm text-white font-mono tabular-nums placeholder:text-slate-600"
                  />
                </div>
                <p className="text-[10px] text-slate-500 mt-1">
                  Envía <code className="text-secondary">/id</code> al bot de Telegram para obtenerlo.
                </p>
              </div>
            </div>

            {/* Contraseñas */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
                    Contraseña *
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="text-[10px] font-mono text-slate-400 hover:text-white"
                  >
                    {showPassword ? "Ocultar" : "Mostrar"}
                  </button>
                </div>
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Mínimo 8 caracteres"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white font-mono placeholder:text-slate-600"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
                    Confirmar Contraseña *
                  </label>
                  {confirmPassword.length > 0 && (
                    <span
                      className={`text-[10px] font-mono ${
                        passwordsMatch ? "text-tertiary" : "text-error"
                      }`}
                    >
                      {passwordsMatch ? "Coincide" : "No coincide"}
                    </span>
                  )}
                </div>
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repite tu contraseña"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white font-mono placeholder:text-slate-600"
                />
              </div>
            </div>

            {/* Medidor de Fortaleza de 4 Segmentos */}
            <div className="p-3 rounded-lg bg-surface-container border border-[#1e2430]">
              <div className="flex items-center justify-between text-[11px] font-mono mb-1.5">
                <span className="text-slate-400">Fortaleza Criptográfica</span>
                <span className="text-white font-semibold">{strength.label}</span>
              </div>
              <div className="grid grid-cols-4 gap-1.5">
                {[1, 2, 3, 4].map((seg) => (
                  <div
                    key={seg}
                    className={`h-1.5 rounded-full transition-colors ${
                      strength.score >= seg ? strength.colorClass : "bg-slate-800"
                    }`}
                  />
                ))}
              </div>
            </div>

            {/* Google Sheet Opcional */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
                  Google Sheet Contable (Opcional)
                </label>
                <span className="text-[10px] font-mono text-slate-500">
                  Sincronización Libro Diario
                </span>
              </div>
              <div className="relative">
                <span className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2">
                  table_chart
                </span>
                <input
                  type="text"
                  value={googleSheetId}
                  onChange={(e) => setGoogleSheetId(e.target.value)}
                  placeholder="Pega URL completa de Google Sheets o ID del documento"
                  className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-tertiary focus:outline-hidden text-xs text-white font-mono placeholder:text-slate-600"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-lg bg-primary-container text-on-primary font-bold text-sm hover:brightness-110 disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-lg shadow-primary-container/10"
            >
              <span className="material-symbols-outlined text-[18px]">how_to_reg</span>
              <span>{loading ? "Registrando Operador..." : "Crear Cuenta e Ingresar"}</span>
            </button>
          </form>

          <div className="mt-5 pt-4 border-t border-[#1e2430] flex items-center justify-between text-xs">
            <span className="text-slate-400">¿Ya posees credenciales activas?</span>
            <Link href="/login" className="font-semibold text-primary hover:underline">
              Iniciar Sesión →
            </Link>
          </div>
        </div>
      </main>

      <footer className="relative z-10 py-4 px-6 border-t border-[#1e2430] bg-surface/60 text-center text-[11px] font-mono text-slate-500">
        Permisos RBAC (ADMIN / TRADER / INVITADO) verificados contra Base de Datos y lista inmutable .env
      </footer>
    </div>
  );
}
