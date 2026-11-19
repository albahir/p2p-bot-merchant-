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

const PRESET_SECURITY_QUESTIONS = [
  "¿Cuál fue tu primer banco en Venezuela?",
  "¿Cuál es el nombre de tu primera mascota?",
  "¿En qué ciudad naciste?",
  "¿Cuál es el segundo apellido de tu madre?",
  "¿Cuál fue el modelo de tu primer teléfono o vehículo?",
];

export default function RegisterPage() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();

  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [telegramId, setTelegramId] = useState("");
  const [googleSheetId, setGoogleSheetId] = useState("");
  const [selectedQuestionPreset, setSelectedQuestionPreset] = useState(
    PRESET_SECURITY_QUESTIONS[0]
  );
  const [customQuestion, setCustomQuestion] = useState("");
  const [securityAnswer, setSecurityAnswer] = useState("");
  const [showAnswer, setShowAnswer] = useState(false);

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [generatedRecoveryKey, setGeneratedRecoveryKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const effectiveSecurityQuestion =
    selectedQuestionPreset === "__custom__"
      ? customQuestion.trim()
      : selectedQuestionPreset;

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
    if (!fullName.trim() || fullName.trim().length < 2) {
      setError("Ingresa tu nombre completo o nombre de operador para identificar tu perfil.");
      return;
    }
    if (!email.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setError("Ingresa un correo electrónico válido para recuperación segura de cuenta.");
      return;
    }
    if (!effectiveSecurityQuestion || effectiveSecurityQuestion.length < 5) {
      setError("Selecciona o escribe una pregunta de seguridad válida.");
      return;
    }
    if (!securityAnswer.trim() || securityAnswer.trim().length < 3) {
      setError("La respuesta secreta debe tener al menos 3 caracteres.");
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
      const res = await registerUser({
        username: username.trim(),
        password,
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        telegram_id: telegramId.trim() || undefined,
        google_sheet_id: googleSheetId.trim() || undefined,
        security_question: effectiveSecurityQuestion,
        security_answer: securityAnswer.trim(),
      });
      if (res.recovery_key) {
        setGeneratedRecoveryKey(res.recovery_key);
      } else {
        router.push("/");
      }
    } catch (err: any) {
      setError(err.message || "Error al crear la cuenta de operador.");
    } finally {
      setLoading(false);
    }
  }

  function handleDownloadBackupTxt() {
    if (!generatedRecoveryKey) return;
    const text = [
      "=== RESPALDO DE RECUPERACIÓN DE PERFIL — SISTEMA COMERCIANTE P2P ===",
      `Alias de Operador: ${username.trim()}`,
      `Nombre: ${fullName.trim()}`,
      `Correo de Respaldo: ${email.trim().toLowerCase()}`,
      `Llave Maestra de Recuperación (Uso Único): ${generatedRecoveryKey}`,
      `Fecha de Emisión: ${new Date().toISOString()}`,
      "",
      "IMPORTANTE: Guarda esta llave en un gestor de contraseñas o lugar físico seguro.",
      "Solo se muestra una vez; al utilizarla para recuperar tu cuenta rotará automáticamente.",
    ].join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `respaldo-p2p-${username.trim()}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="min-h-screen bg-background text-on-surface flex flex-col justify-between relative overflow-x-hidden">
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[720px] h-[360px] rounded-full bg-secondary/6 blur-[140px]" />

      {/* Topbar Sticky para scroll cómodo en laptop y teléfono */}
      <header className="sticky top-0 z-20 h-16 px-5 lg:px-10 flex items-center justify-between border-b border-[#1e2430] bg-surface/85 backdrop-blur-md">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary-container/15 border border-primary-container/30 flex items-center justify-center text-primary-container">
            <span className="material-symbols-outlined text-[18px]">bolt</span>
          </div>
          <div>
            <span className="text-sm font-bold text-white tracking-tight">
              Sistema Comerciante P2P
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

      {/* Tarjeta Central Amplia y Ordenada */}
      <main className="relative z-10 flex-1 flex items-center justify-center p-4 sm:p-6 py-8">
        <div className="w-full max-w-3xl rounded-2xl bg-surface-container-low border border-[#1e2430] shadow-2xl p-5 sm:p-8">
          <div className="mb-6 pb-4 border-b border-[#1e2430]">
            <h1 className="text-xl font-bold text-white tracking-tight">
              Crear cuenta
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Configura tu perfil y respaldo de recuperación.
            </p>
          </div>

          {error && (
            <div
              role="alert"
              aria-live="polite"
              className="mb-5 p-3 rounded-lg bg-error/10 border border-error/30 flex items-start gap-2.5 text-xs text-red-200"
            >
              <span className="material-symbols-outlined text-[18px] text-error shrink-0 mt-0.5" aria-hidden="true">
                error
              </span>
              <span>{error}</span>
            </div>
          )}

          {generatedRecoveryKey ? (
            <div className="space-y-5">
              <div className="p-4 rounded-xl bg-tertiary/10 border border-tertiary/30 space-y-2">
                <div className="flex items-center gap-2 text-tertiary font-bold text-sm">
                  <span className="material-symbols-outlined text-[20px]">verified_user</span>
                  <span>¡Cuenta Creada Exitosamente!</span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Guarda esta <strong className="text-white">Llave Maestra de Recuperación</strong> en un lugar seguro.
                  Por seguridad, <strong className="text-amber-300">solo se muestra esta única vez</strong> y te permitirá recuperar tu cuenta aunque pierdas acceso a Telegram o olvides tu contraseña.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-surface-container-lowest border border-primary-container/40 text-center space-y-2">
                <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400">
                  Llave Maestra de Respaldo (Uso Único)
                </div>
                <div className="text-lg sm:text-xl font-mono font-bold tracking-[0.15em] text-primary select-all">
                  {generatedRecoveryKey}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard?.writeText(generatedRecoveryKey);
                    setCopiedKey(true);
                  }}
                  className="py-2.5 px-4 rounded-lg bg-surface-container border border-[#1e2430] hover:border-primary-container text-xs font-mono font-semibold text-white flex items-center justify-center gap-2"
                >
                  <span className="material-symbols-outlined text-[16px] text-primary">
                    {copiedKey ? "check" : "content_copy"}
                  </span>
                  <span>{copiedKey ? "¡Llave Copiada!" : "Copiar Llave"}</span>
                </button>
                <button
                  type="button"
                  onClick={handleDownloadBackupTxt}
                  className="py-2.5 px-4 rounded-lg bg-surface-container border border-[#1e2430] hover:border-secondary text-xs font-mono font-semibold text-white flex items-center justify-center gap-2"
                >
                  <span className="material-symbols-outlined text-[16px] text-secondary">
                    download
                  </span>
                  <span>Descargar Respaldo (.txt)</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => router.push("/")}
                className="w-full py-2.5 px-4 rounded-lg bg-primary-container text-on-primary font-bold text-sm hover:brightness-110 transition-all flex items-center justify-center gap-2"
              >
                <span>Ya guardé mi llave, ir a la Terminal</span>
                <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
              </button>
            </div>
          ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Nombre Completo */}
              <div>
                <label
                  htmlFor="reg-fullname"
                  className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
                >
                  Nombre Completo / Operador *
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true">
                    person
                  </span>
                  <input
                    id="reg-fullname"
                    type="text"
                    required
                    minLength={2}
                    autoComplete="name"
                    enterKeyHint="next"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="ej. Carlos Mendoza"
                    className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white placeholder:text-slate-600"
                  />
                </div>
              </div>

              {/* Correo Electrónico */}
              <div>
                <label
                  htmlFor="reg-email"
                  className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
                >
                  Correo de Respaldo *
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true">
                    mail
                  </span>
                  <input
                    id="reg-email"
                    type="email"
                    required
                    autoComplete="email"
                    enterKeyHint="next"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="ej. carlos@correo.com"
                    className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white font-mono placeholder:text-slate-600"
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Alias */}
              <div>
                <label
                  htmlFor="reg-username"
                  className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
                >
                  Alias de Operador *
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true">
                    badge
                  </span>
                  <input
                    id="reg-username"
                    type="text"
                    required
                    minLength={3}
                    autoComplete="username"
                    enterKeyHint="next"
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
                  <label
                    htmlFor="reg-telegram"
                    className="text-[11px] font-mono uppercase tracking-wider text-slate-400"
                  >
                    ID de Telegram (Opcional)
                  </label>
                  {isTelegramValid && (
                    <span className="text-[10px] font-mono text-tertiary flex items-center gap-0.5">
                      <span className="material-symbols-outlined text-[13px]" aria-hidden="true">verified</span>
                      Formato válido
                    </span>
                  )}
                </div>
                <div className="relative">
                  <span className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true">
                    send
                  </span>
                  <input
                    id="reg-telegram"
                    type="tel"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    enterKeyHint="next"
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

            {/* Bloque 2: Pregunta y Respuesta Secreta */}
            <div className="p-4 rounded-xl bg-surface-container border border-[#1e2430] space-y-3">
              <div className="flex items-center gap-1.5 text-[11px] font-mono font-bold uppercase tracking-wider text-primary">
                <span className="material-symbols-outlined text-[15px]">shield_lock</span>
                <span>Recuperación de cuenta</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                <div>
                  <label
                    htmlFor="reg-sec-question"
                    className="block text-[10px] font-mono uppercase text-slate-400 mb-1.5"
                  >
                    Pregunta de Seguridad *
                  </label>
                  <select
                    id="reg-sec-question"
                    value={selectedQuestionPreset}
                    onChange={(e) => setSelectedQuestionPreset(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white"
                  >
                    {PRESET_SECURITY_QUESTIONS.map((q) => (
                      <option key={q} value={q}>
                        {q}
                      </option>
                    ))}
                    <option value="__custom__">Escribir pregunta personalizada...</option>
                  </select>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label
                      htmlFor="reg-sec-answer"
                      className="text-[10px] font-mono uppercase text-slate-400"
                    >
                      Respuesta Secreta *
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowAnswer(!showAnswer)}
                      className="text-[10px] font-mono text-slate-400 hover:text-white"
                    >
                      {showAnswer ? "Ocultar" : "Mostrar"}
                    </button>
                  </div>
                  <input
                    id="reg-sec-answer"
                    type={showAnswer ? "text" : "password"}
                    required
                    minLength={3}
                    autoComplete="off"
                    enterKeyHint="next"
                    value={securityAnswer}
                    onChange={(e) => setSecurityAnswer(e.target.value)}
                    placeholder="Mínimo 3 caracteres"
                    className="w-full px-3 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white font-mono placeholder:text-slate-600"
                  />
                </div>
              </div>

              {selectedQuestionPreset === "__custom__" && (
                <input
                  id="reg-sec-custom-question"
                  type="text"
                  required
                  minLength={5}
                  value={customQuestion}
                  onChange={(e) => setCustomQuestion(e.target.value)}
                  placeholder="Escribe tu pregunta secreta personal..."
                  className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white"
                />
              )}
            </div>

            {/* Contraseñas */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label
                    htmlFor="reg-password"
                    className="text-[11px] font-mono uppercase tracking-wider text-slate-400"
                  >
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
                  id="reg-password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  autoComplete="new-password"
                  enterKeyHint="next"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Mínimo 8 caracteres"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm text-white font-mono placeholder:text-slate-600"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label
                    htmlFor="reg-confirm-password"
                    className="text-[11px] font-mono uppercase tracking-wider text-slate-400"
                  >
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
                  Hoja Contable de Google Sheets (Opcional)
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
                  placeholder="Pega el enlace completo de Google Sheets o ID del documento"
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
              <span>{loading ? "Registrando Operador..." : "Crear Cuenta y Generar Llave Maestra"}</span>
            </button>
          </form>
          )}

          <div className="mt-5 pt-4 border-t border-[#1e2430] flex items-center justify-between text-xs">
            <span className="text-slate-400">¿Ya posees credenciales activas?</span>
            <Link href="/login" className="font-semibold text-primary hover:underline">
              Iniciar Sesión →
            </Link>
          </div>
        </div>
      </main>

      <footer className="relative z-10 py-4 px-6 border-t border-[#1e2430] bg-surface/60 text-center text-[11px] font-mono text-slate-500">
        Permisos de rol (ADMINISTRADOR / COMERCIANTE / INVITADO) verificados contra Base de Datos y lista inmutable .env
      </footer>
    </div>
  );
}
