"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  TelegramBotInfo,
  VENEZUELAN_BANK_CATALOG,
  getTelegramBotInfo,
  registerUser,
  sendEmailVerificationCode,
  verifyEmailCode,
} from "@/lib/api";
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

const EMAIL_DOMAIN_OPTIONS = [
  "@gmail.com",
  "@hotmail.com",
  "@outlook.com",
  "@yahoo.com",
  "@icloud.com",
  "__custom__",
] as const;

type EmailDomainOption = (typeof EMAIL_DOMAIN_OPTIONS)[number];
type TaxDocPrefix = "NONE" | "V" | "E" | "J" | "G" | "P";
type WizardStep = 1 | 2 | 3;

const WIZARD_STEPS: Array<{ id: WizardStep; title: string; subtitle: string; icon: string }> = [
  {
    id: 1,
    title: "Identidad",
    subtitle: "Nombre, usuario, correo y documento",
    icon: "badge",
  },
  {
    id: 2,
    title: "Seguridad",
    subtitle: "Telegram, clave y pregunta secreta",
    icon: "verified_user",
  },
  {
    id: 3,
    title: "Bancos",
    subtitle: "Bancos de operación y Sheets",
    icon: "account_balance",
  },
];

const TAX_PREFIX_OPTIONS: Array<{
  id: TaxDocPrefix;
  label: string;
  desc: string;
  placeholder: string;
  isRif: boolean;
}> = [
  { id: "V", label: "V-", desc: "Venezolano", placeholder: "19456789", isRif: false },
  { id: "E", label: "E-", desc: "Extranjero", placeholder: "82345678", isRif: false },
  { id: "J", label: "J-", desc: "Jurídico", placeholder: "40123456-7", isRif: true },
  { id: "G", label: "G-", desc: "Gubernamental", placeholder: "20001234-5", isRif: true },
  { id: "P", label: "P-", desc: "Pasaporte", placeholder: "12345678", isRif: false },
  { id: "NONE", label: "Sin RIF", desc: "Omitir", placeholder: "Opcional", isRif: false },
];

export default function RegisterPage() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const stepHeadingRef = useRef<HTMLHeadingElement>(null);

  const [step, setStep] = useState<WizardStep>(1);

  // Paso 1: Identidad
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [taxPrefix, setTaxPrefix] = useState<TaxDocPrefix>("V");
  const [taxNumber, setTaxNumber] = useState("");
  const [emailLocal, setEmailLocal] = useState("");
  const [emailDomain, setEmailDomain] = useState<EmailDomainOption>("@gmail.com");
  const [customEmailInput, setCustomEmailInput] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [emailCodeSent, setEmailCodeSent] = useState(false);
  const [emailSendingCode, setEmailSendingCode] = useState(false);
  const [emailSmtpConfigured, setEmailSmtpConfigured] = useState(false);
  const [emailVerificationToken, setEmailVerificationToken] = useState("");
  const [emailVerifying, setEmailVerifying] = useState(false);
  const [emailStatusMsg, setEmailStatusMsg] = useState<{
    text: string;
    tone: "info" | "ok" | "warn" | "error";
  } | null>(null);

  // Paso 2: Telegram obligatorio + Contraseña + Recuperación
  const [telegramId, setTelegramId] = useState("");
  const [botInfo, setBotInfo] = useState<TelegramBotInfo | null>(null);
  const [copiedBotHandle, setCopiedBotHandle] = useState(false);
  const [selectedQuestionPreset, setSelectedQuestionPreset] = useState(
    PRESET_SECURITY_QUESTIONS[0]
  );
  const [customQuestion, setCustomQuestion] = useState("");
  const [securityAnswer, setSecurityAnswer] = useState("");
  const [showAnswer, setShowAnswer] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Paso 3: Bancos y Google Sheets
  const [preferredBanks, setPreferredBanks] = useState<string[]>([
    "Banco de Venezuela",
    "Mercantil",
  ]);
  const [googleSheetId, setGoogleSheetId] = useState("");

  // Finalización
  const [generatedRecoveryKey, setGeneratedRecoveryKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    getTelegramBotInfo()
      .then((info) => setBotInfo(info))
      .catch(() => null);
  }, []);

  const selectedTaxMeta =
    TAX_PREFIX_OPTIONS.find((opt) => opt.id === taxPrefix) || TAX_PREFIX_OPTIONS[0];

  const formattedTaxId = useMemo(() => {
    if (taxPrefix === "NONE") return "";
    const digits = taxNumber.replace(/\D/g, "");
    if (!digits) return "";
    if (selectedTaxMeta.isRif && digits.length >= 9) {
      return `${taxPrefix}-${digits.slice(0, 8)}-${digits.slice(8, 9)}`;
    }
    return `${taxPrefix}-${digits}`;
  }, [taxPrefix, taxNumber, selectedTaxMeta.isRif]);

  const email = useMemo(() => {
    if (emailDomain === "__custom__") {
      return customEmailInput.trim().toLowerCase();
    }
    const local = emailLocal.trim().toLowerCase();
    return local ? `${local}${emailDomain}` : "";
  }, [emailLocal, emailDomain, customEmailInput]);

  const effectiveSecurityQuestion =
    selectedQuestionPreset === "__custom__"
      ? customQuestion.trim()
      : selectedQuestionPreset;

  const strength = useMemo(() => computePasswordStrength(password), [password]);
  const isTelegramValid = useMemo(
    () => /^\d{5,15}$/.test(telegramId.trim()),
    [telegramId]
  );
  const passwordsMatch =
    password.length > 0 && confirmPassword.length > 0 && password === confirmPassword;

  function clearFieldError(field: string) {
    setFieldErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  function resetEmailVerification() {
    setEmailVerificationToken("");
    setEmailCodeSent(false);
    setEmailCode("");
    setEmailStatusMsg(null);
  }

  function handleEmailTextChange(raw: string) {
    const cleaned = raw.replace(/\s+/g, "").toLowerCase();
    clearFieldError("email");
    resetEmailVerification();

    if (emailDomain === "__custom__") {
      setCustomEmailInput(cleaned);
      return;
    }

    if (cleaned.includes("@")) {
      const [localPart, domainPart] = cleaned.split("@", 2);
      const withAt = domainPart ? `@${domainPart}` : "";
      const matched = EMAIL_DOMAIN_OPTIONS.find(
        (d) => d !== "__custom__" && d === withAt
      );
      if (matched) {
        setEmailLocal(localPart);
        setEmailDomain(matched);
      } else if (domainPart) {
        setEmailDomain("__custom__");
        setCustomEmailInput(cleaned);
      } else {
        setEmailLocal(localPart);
      }
      return;
    }

    setEmailLocal(cleaned);
  }

  function handleEmailDomainChange(nextDomain: EmailDomainOption) {
    clearFieldError("email");
    resetEmailVerification();
    if (nextDomain === "__custom__") {
      const seed = emailLocal.trim().toLowerCase();
      setCustomEmailInput(seed ? `${seed}@` : "");
      setEmailDomain("__custom__");
      return;
    }
    if (emailDomain === "__custom__" && customEmailInput.includes("@")) {
      setEmailLocal(customEmailInput.split("@")[0]);
    } else if (emailDomain === "__custom__" && customEmailInput.trim()) {
      setEmailLocal(customEmailInput.trim());
    }
    setEmailDomain(nextDomain);
  }

  async function handleSendEmailCode() {
    const emailErr = validateField("email");
    if (emailErr) {
      document.getElementById("reg-email")?.focus();
      return;
    }
    setEmailSendingCode(true);
    setEmailStatusMsg(null);
    setError(null);
    try {
      const res = await sendEmailVerificationCode(email);
      setEmailSmtpConfigured(Boolean(res.smtp_configured));
      if (res.sent) {
        setEmailCodeSent(true);
        setEmailCode("");
        setEmailStatusMsg({ text: res.message, tone: "info" });
        setTimeout(() => document.getElementById("reg-email-code")?.focus(), 0);
      } else {
        setEmailCodeSent(false);
        setEmailStatusMsg({ text: res.message, tone: "warn" });
      }
    } catch (err: any) {
      setEmailStatusMsg({
        text: err.message || "No se pudo enviar el código al correo.",
        tone: "error",
      });
    } finally {
      setEmailSendingCode(false);
    }
  }

  async function handleVerifyEmailCode(codeOverride?: string) {
    const cleaned = (codeOverride ?? emailCode).replace(/\D/g, "").slice(0, 6);
    if (cleaned.length !== 6) {
      setEmailStatusMsg({ text: "Ingresa los 6 dígitos.", tone: "error" });
      document.getElementById("reg-email-code")?.focus();
      return;
    }
    setEmailVerifying(true);
    setEmailStatusMsg(null);
    setError(null);
    try {
      const res = await verifyEmailCode(email, cleaned);
      if (res.verified && res.verification_token) {
        setEmailVerificationToken(res.verification_token);
        setEmailCodeSent(false);
        setEmailCode("");
        setEmailStatusMsg({ text: res.message || "Correo verificado.", tone: "ok" });
      }
    } catch (err: any) {
      setEmailStatusMsg({
        text: err.message || "Código incorrecto o expirado.",
        tone: "error",
      });
    } finally {
      setEmailVerifying(false);
    }
  }

  function handleTaxPrefixChange(nextPrefix: TaxDocPrefix) {
    setTaxPrefix(nextPrefix);
    if (nextPrefix === "NONE") {
      setTaxNumber("");
    } else {
      const meta = TAX_PREFIX_OPTIONS.find((opt) => opt.id === nextPrefix);
      const digits = taxNumber.replace(/\D/g, "");
      if (meta?.isRif && digits.length === 9) {
        setTaxNumber(`${digits.slice(0, 8)}-${digits.slice(8, 9)}`);
      } else {
        setTaxNumber(digits);
      }
    }
    clearFieldError("taxId");
  }

  function handleTaxNumberChange(raw: string) {
    const trimmedUpper = raw.trim().toUpperCase();
    const prefixMatch = trimmedUpper.match(/^([VEJGP])[- ]?(.*)$/);
    let effectiveIsRif = selectedTaxMeta.isRif;
    let rawDigitsSource = raw;
    if (prefixMatch) {
      const detected = prefixMatch[1] as TaxDocPrefix;
      if (detected !== taxPrefix) {
        setTaxPrefix(detected);
        effectiveIsRif =
          TAX_PREFIX_OPTIONS.find((opt) => opt.id === detected)?.isRif ?? false;
      }
      rawDigitsSource = prefixMatch[2];
    }

    const digits = rawDigitsSource.replace(/\D/g, "").slice(0, 9);
    if (effectiveIsRif && digits.length === 9) {
      setTaxNumber(`${digits.slice(0, 8)}-${digits.slice(8, 9)}`);
    } else {
      setTaxNumber(digits);
    }
    clearFieldError("taxId");
  }

  function validateField(field: string, overrideValue?: string): string {
    let msg = "";
    switch (field) {
      case "fullName": {
        const val = (overrideValue ?? fullName).trim();
        if (val.length < 2) msg = "Ingresa tu nombre completo (mínimo 2 caracteres).";
        else if (!/^[\p{L}\p{M}\s.'-]+$/u.test(val))
          msg = "El nombre solo debe contener letras, espacios o puntos.";
        break;
      }
      case "email": {
        const val = (overrideValue ?? email).trim();
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(val))
          msg = "Ingresa un correo válido (ej. carlos@gmail.com).";
        break;
      }
      case "username": {
        const val = (overrideValue ?? username).trim();
        if (val.length < 3) msg = "El alias debe tener al menos 3 caracteres.";
        else if (!/^[a-zA-Z0-9._-]+$/.test(val))
          msg = "Solo letras, números, punto, guion o guion bajo (sin espacios).";
        break;
      }
      case "taxId": {
        if (taxPrefix !== "NONE") {
          const digits = (overrideValue ?? taxNumber).replace(/\D/g, "");
          if (digits.length > 0) {
            if (selectedTaxMeta.isRif && digits.length !== 9) {
              msg = `El RIF ${taxPrefix}- requiere exactamente 9 dígitos (8 cuerpo + 1 verificador).`;
            } else if (!selectedTaxMeta.isRif && (digits.length < 6 || digits.length > 9)) {
              msg = `La identificación ${taxPrefix}- requiere entre 6 y 9 dígitos.`;
            }
          }
        }
        break;
      }
      case "telegramId": {
        const val = (overrideValue ?? telegramId).trim();
        if (!val) {
          msg = "El ID de Telegram es obligatorio para alertas y recuperación OTP.";
        } else if (!/^\d{5,15}$/.test(val)) {
          msg = "El ID de Telegram debe tener entre 5 y 15 dígitos numéricos.";
        }
        break;
      }
      case "securityAnswer": {
        const val = (overrideValue ?? securityAnswer).trim();
        if (val.length < 3) msg = "La respuesta secreta debe tener al menos 3 caracteres.";
        break;
      }
      case "customQuestion": {
        if (selectedQuestionPreset === "__custom__") {
          const val = (overrideValue ?? customQuestion).trim();
          if (val.length < 5) msg = "Escribe tu pregunta secreta (mínimo 5 caracteres).";
        }
        break;
      }
      case "password": {
        const val = overrideValue ?? password;
        if (val.length < 8) msg = "La contraseña debe tener mínimo 8 caracteres.";
        break;
      }
      case "confirmPassword": {
        const val = overrideValue ?? confirmPassword;
        if (!val || val !== password) msg = "Las contraseñas no coinciden.";
        break;
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

  function focusInvalidField(checks: Array<[string, string, string]>): boolean {
    const firstInvalid = checks.find(([, msg]) => Boolean(msg));
    if (firstInvalid) {
      setError(firstInvalid[1]);
      if (typeof document !== "undefined") {
        document.getElementById(firstInvalid[2])?.focus();
      }
      return false;
    }
    return true;
  }

  function goToStep(nextStep: WizardStep) {
    setError(null);
    setStep(nextStep);
    setTimeout(() => {
      stepHeadingRef.current?.focus();
    }, 0);
  }

  async function validateStep1AndNext() {
    const ok = focusInvalidField([
      ["fullName", validateField("fullName"), "reg-fullname"],
      ["email", validateField("email"), "reg-email"],
      ["username", validateField("username"), "reg-username"],
      ["taxId", validateField("taxId"), "reg-tax-id"],
    ]);
    if (!ok) return;

    if (!emailVerificationToken) {
      if (!emailCodeSent) {
        setEmailSendingCode(true);
        setEmailStatusMsg(null);
        try {
          const res = await sendEmailVerificationCode(email);
          setEmailSmtpConfigured(Boolean(res.smtp_configured));
          if (res.sent) {
            setEmailCodeSent(true);
            setEmailCode("");
            setEmailStatusMsg({ text: res.message, tone: "info" });
            setError("Enviamos automáticamente un código de 6 dígitos a tu correo para verificarlo.");
            setTimeout(() => document.getElementById("reg-email-code")?.focus(), 0);
            return;
          }
          // Si SMTP no está activo en entorno dev, permite avanzar sin bloquear registro
        } catch (err: any) {
          setEmailStatusMsg({
            text: err.message || "No se pudo enviar el código al correo.",
            tone: "error",
          });
          setError(err.message || "Verifica tu correo antes de continuar.");
          return;
        } finally {
          setEmailSendingCode(false);
        }
      } else if (emailSmtpConfigured) {
        const msg = "Ingresa los 6 dígitos enviados a tu correo para verificarlo automáticamente.";
        setError(msg);
        document.getElementById("reg-email-code")?.focus();
        return;
      }
    }
    goToStep(2);
  }

  function validateStep2AndNext() {
    const checks: Array<[string, string, string]> = [
      ["telegramId", validateField("telegramId"), "reg-telegram"],
      ["password", validateField("password"), "reg-password"],
      ["confirmPassword", validateField("confirmPassword"), "reg-confirm-password"],
      ["securityAnswer", validateField("securityAnswer"), "reg-sec-answer"],
    ];
    if (selectedQuestionPreset === "__custom__") {
      checks.push(["customQuestion", validateField("customQuestion"), "reg-sec-custom-question"]);
    }
    const ok = focusInvalidField(checks);
    if (ok) goToStep(3);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (step === 1) {
      validateStep1AndNext();
      return;
    }
    if (step === 2) {
      validateStep2AndNext();
      return;
    }

    if (preferredBanks.length === 0) {
      setError("Selecciona al menos 1 banco con el que operas.");
      return;
    }

    const ok1 = focusInvalidField([
      ["fullName", validateField("fullName"), "reg-fullname"],
      ["email", validateField("email"), "reg-email"],
      ["username", validateField("username"), "reg-username"],
      ["taxId", validateField("taxId"), "reg-tax-id"],
    ]);
    if (!ok1) {
      goToStep(1);
      return;
    }

    const ok2 = focusInvalidField([
      ["telegramId", validateField("telegramId"), "reg-telegram"],
      ["password", validateField("password"), "reg-password"],
      ["confirmPassword", validateField("confirmPassword"), "reg-confirm-password"],
      ["securityAnswer", validateField("securityAnswer"), "reg-sec-answer"],
    ]);
    if (!ok2) {
      goToStep(2);
      return;
    }

    setLoading(true);
    try {
      const res = await registerUser({
        username: username.trim(),
        password,
        full_name: fullName.trim(),
        tax_id: formattedTaxId || undefined,
        email: email.trim().toLowerCase(),
        email_verification_token: emailVerificationToken || undefined,
        telegram_id: telegramId.trim(),
        google_sheet_id: googleSheetId.trim() || undefined,
        preferred_banks: preferredBanks,
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
      `Telegram ID: ${telegramId.trim()}`,
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

  const activeStepMeta = WIZARD_STEPS.find((s) => s.id === step) || WIZARD_STEPS[0];

  return (
    <div className="min-h-screen bg-background text-on-surface flex flex-col justify-between relative overflow-x-hidden">
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[720px] h-[360px] rounded-full bg-secondary/6 blur-[140px]" />

      {/* Topbar Sticky */}
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

      {/* Tarjeta Central Guiada por Pasos */}
      <main className="relative z-10 flex-1 flex items-center justify-center p-4 sm:p-6 py-8">
        <div className="w-full max-w-2xl rounded-2xl bg-surface-container-low border border-[#1e2430] shadow-2xl p-5 sm:p-8">
          <div className="mb-5 pb-4 border-b border-[#1e2430] space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h1 className="text-xl font-bold text-white tracking-tight">
                Crear cuenta
              </h1>
              {!generatedRecoveryKey && (
                <span className="px-2.5 py-1 rounded-lg bg-surface-container border border-[#1e2430] text-[11px] font-mono text-primary font-bold shrink-0">
                  {step} / 3
                </span>
              )}
            </div>

            {!generatedRecoveryKey && (
              <nav aria-label="Progreso de registro" className="space-y-2">
                <ol className="grid grid-cols-3 gap-2">
                  {WIZARD_STEPS.map((s) => {
                    const isCurrent = step === s.id;
                    const isCompleted = step > s.id;
                    const canNavigate = isCompleted;
                    return (
                      <li
                        key={s.id}
                        aria-current={isCurrent ? "step" : undefined}
                        className="min-w-0"
                      >
                        <button
                          type="button"
                          disabled={!canNavigate && !isCurrent}
                          onClick={() => {
                            if (canNavigate) goToStep(s.id);
                          }}
                          className={`w-full p-2 rounded-xl border text-left transition-colors flex items-center gap-2 min-w-0 ${
                            isCurrent
                              ? "bg-primary-container/15 border-primary-container text-white"
                              : isCompleted
                              ? "bg-tertiary/10 border-tertiary/40 text-emerald-200 hover:bg-tertiary/15 cursor-pointer"
                              : "bg-surface-container border-[#1e2430] text-slate-500 cursor-default"
                          }`}
                        >
                          <span
                            className={`w-6 h-6 rounded-full text-[11px] font-mono font-bold flex items-center justify-center shrink-0 ${
                              isCurrent
                                ? "bg-primary-container text-on-primary"
                                : isCompleted
                                ? "bg-tertiary text-on-tertiary"
                                : "bg-surface-container-high text-slate-400"
                            }`}
                          >
                            {isCompleted ? "✓" : s.id}
                          </span>
                          <span className="text-[11px] font-semibold truncate">{s.title}</span>
                        </button>
                      </li>
                    );
                  })}
                </ol>
                <progress
                  value={step}
                  max={3}
                  aria-label={`Paso ${step} de 3: ${activeStepMeta.title}`}
                  className="w-full h-1.5 rounded-full overflow-hidden accent-primary-container bg-surface-container"
                />
              </nav>
            )}
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
            <form onSubmit={handleSubmit} noValidate className="space-y-5">
              {/* Encabezado focalizable de cada paso */}
              <div className="flex items-center gap-2.5">
                <span className="material-symbols-outlined text-[20px] text-primary" aria-hidden="true">
                  {activeStepMeta.icon}
                </span>
                <div>
                  <h2
                    ref={stepHeadingRef}
                    tabIndex={-1}
                    className="text-sm font-bold text-white focus:outline-hidden"
                  >
                    Paso {step}: {activeStepMeta.title}
                  </h2>
                  <p className="text-[11px] text-slate-400">{activeStepMeta.subtitle}</p>
                </div>
              </div>

              {/* PASO 1: IDENTIDAD */}
              {step === 1 && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Nombre Completo */}
                    <div>
                      <label
                        htmlFor="reg-fullname"
                        className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
                      >
                        Nombre completo *
                      </label>
                      <div className="relative">
                        <span
                          className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2"
                          aria-hidden="true"
                        >
                          person
                        </span>
                        <input
                          id="reg-fullname"
                          name="full_name"
                          type="text"
                          required
                          minLength={2}
                          autoComplete="name"
                          enterKeyHint="next"
                          aria-invalid={Boolean(fieldErrors.fullName)}
                          aria-describedby={fieldErrors.fullName ? "reg-fullname-err" : undefined}
                          value={fullName}
                          onChange={(e) => {
                            setFullName(e.target.value);
                            clearFieldError("fullName");
                          }}
                          onBlur={() => validateField("fullName")}
                          placeholder="Carlos Mendoza"
                          className={`w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-sm text-white placeholder:text-slate-600 ${
                            fieldErrors.fullName
                              ? "border-error focus:border-error"
                              : "border-[#1e2430] focus:border-primary-container"
                          }`}
                        />
                      </div>
                      {fieldErrors.fullName && (
                        <p id="reg-fullname-err" className="text-[10px] text-error mt-1">
                          {fieldErrors.fullName}
                        </p>
                      )}
                    </div>

                    {/* Usuario */}
                    <div>
                      <label
                        htmlFor="reg-username"
                        className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
                      >
                        Usuario *
                      </label>
                      <div className="relative">
                        <span
                          className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2"
                          aria-hidden="true"
                        >
                          badge
                        </span>
                        <input
                          id="reg-username"
                          name="username"
                          type="text"
                          required
                          minLength={3}
                          maxLength={30}
                          autoComplete="username"
                          autoCorrect="off"
                          autoCapitalize="none"
                          spellCheck={false}
                          enterKeyHint="next"
                          aria-invalid={Boolean(fieldErrors.username)}
                          aria-describedby={fieldErrors.username ? "reg-username-err" : undefined}
                          value={username}
                          onChange={(e) => {
                            setUsername(e.target.value.replace(/[^a-zA-Z0-9._-]/g, ""));
                            clearFieldError("username");
                          }}
                          onBlur={() => validateField("username")}
                          placeholder="trader_caracas"
                          className={`w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-sm text-white font-mono placeholder:text-slate-600 ${
                            fieldErrors.username
                              ? "border-error focus:border-error"
                              : "border-[#1e2430] focus:border-primary-container"
                          }`}
                        />
                      </div>
                      {fieldErrors.username && (
                        <p id="reg-username-err" className="text-[10px] text-error mt-1">
                          {fieldErrors.username}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Correo con Paleta Desplegable */}
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <label
                        htmlFor="reg-email"
                        className="text-[11px] font-mono uppercase tracking-wider text-slate-400"
                      >
                        Correo electrónico *
                      </label>
                      {emailVerificationToken ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-mono font-semibold text-tertiary">
                          <span className="material-symbols-outlined text-[13px]" aria-hidden="true">
                            verified
                          </span>
                          Verificado
                        </span>
                      ) : email && /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email) ? (
                        <button
                          type="button"
                          onClick={handleSendEmailCode}
                          disabled={emailSendingCode}
                          className="text-[10px] font-mono font-semibold text-primary hover:underline disabled:opacity-50 cursor-pointer"
                        >
                          {emailSendingCode
                            ? "Enviando..."
                            : emailCodeSent
                            ? "Reenviar código"
                            : "Verificar correo"}
                        </button>
                      ) : null}
                    </div>
                    <div
                      className={`flex items-stretch rounded-lg bg-surface-container-lowest border overflow-hidden focus-within:ring-1 ${
                        fieldErrors.email
                          ? "border-error focus-within:border-error focus-within:ring-error/40"
                          : emailVerificationToken
                          ? "border-tertiary/50 focus-within:border-tertiary focus-within:ring-tertiary/30"
                          : "border-[#1e2430] focus-within:border-primary-container focus-within:ring-primary-container/30"
                      }`}
                    >
                      <div className="relative flex-1 min-w-0">
                        <span
                          className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                          aria-hidden="true"
                        >
                          mail
                        </span>
                        <input
                          id="reg-email"
                          name="email"
                          type={emailDomain === "__custom__" ? "email" : "text"}
                          inputMode="email"
                          required
                          autoComplete="email"
                          autoCorrect="off"
                          autoCapitalize="none"
                          spellCheck={false}
                          enterKeyHint="next"
                          aria-invalid={Boolean(fieldErrors.email)}
                          aria-describedby={fieldErrors.email ? "reg-email-err" : undefined}
                          value={emailDomain === "__custom__" ? customEmailInput : emailLocal}
                          onChange={(e) => handleEmailTextChange(e.target.value)}
                          onBlur={() => validateField("email")}
                          placeholder={
                            emailDomain === "__custom__" ? "carlos@dominio.com" : "carlos.p2p"
                          }
                          className="w-full h-full pl-10 pr-2 py-2.5 bg-transparent focus:outline-hidden text-sm text-white font-mono placeholder:text-slate-600"
                        />
                      </div>
                      <select
                        id="reg-email-domain"
                        name="email_domain"
                        aria-label="Dominio del correo"
                        value={emailDomain}
                        onChange={(e) => handleEmailDomainChange(e.target.value as EmailDomainOption)}
                        className="px-2.5 py-2.5 bg-surface-container border-l border-[#1e2430] text-xs font-mono font-semibold text-primary focus:outline-hidden cursor-pointer shrink-0"
                      >
                        {EMAIL_DOMAIN_OPTIONS.map((dom) => (
                          <option key={dom} value={dom} className="bg-[#141920] text-white">
                            {dom === "__custom__" ? "Otro..." : dom}
                          </option>
                        ))}
                      </select>
                    </div>
                    {emailCodeSent && !emailVerificationToken && (
                      <div className="mt-2 flex items-center gap-2">
                        <input
                          id="reg-email-code"
                          name="email_otp"
                          type="text"
                          inputMode="numeric"
                          autoComplete="one-time-code"
                          maxLength={6}
                          value={emailCode}
                          onChange={(e) => {
                            const nextVal = e.target.value.replace(/\D/g, "").slice(0, 6);
                            setEmailCode(nextVal);
                            if (emailStatusMsg?.tone === "error") setEmailStatusMsg(null);
                            if (nextVal.length === 6 && !emailVerifying) {
                              void handleVerifyEmailCode(nextVal);
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              void handleVerifyEmailCode();
                            }
                          }}
                          placeholder="Código 6 dígitos"
                          aria-label="Código de verificación de correo"
                          className="flex-1 min-w-0 px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs font-mono tracking-[0.25em] text-white placeholder:tracking-normal placeholder:text-slate-600"
                        />
                        <button
                          type="button"
                          onClick={() => void handleVerifyEmailCode()}
                          disabled={emailVerifying || emailCode.length !== 6}
                          className="px-3 py-2 rounded-lg bg-primary-container/20 border border-primary-container/40 text-xs font-semibold text-primary hover:bg-primary-container/30 disabled:opacity-40 cursor-pointer shrink-0"
                        >
                          {emailVerifying ? "Validando..." : "Confirmar"}
                        </button>
                      </div>
                    )}
                    {emailStatusMsg && !fieldErrors.email && (
                      <p
                        className={`text-[10px] mt-1 ${
                          emailStatusMsg.tone === "ok"
                            ? "text-tertiary"
                            : emailStatusMsg.tone === "error"
                            ? "text-error"
                            : emailStatusMsg.tone === "warn"
                            ? "text-amber-400"
                            : "text-slate-400"
                        }`}
                      >
                        {emailStatusMsg.text}
                      </p>
                    )}
                    {fieldErrors.email && (
                      <p id="reg-email-err" className="text-[10px] text-error mt-1">
                        {fieldErrors.email}
                      </p>
                    )}
                  </div>

                  {/* Cédula o RIF con Paleta Desplegable */}
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-1.5 flex-wrap">
                      <label
                        htmlFor="reg-tax-id"
                        className="text-[11px] font-mono uppercase tracking-wider text-slate-400"
                      >
                        Cédula o RIF (Opcional)
                      </label>
                      {formattedTaxId && (
                        <span className="text-[10px] font-mono text-primary font-bold">
                          {formattedTaxId}
                        </span>
                      )}
                    </div>

                    <div
                      className={`flex items-stretch rounded-lg bg-surface-container-lowest border overflow-hidden focus-within:ring-1 ${
                        fieldErrors.taxId
                          ? "border-error focus-within:border-error focus-within:ring-error/40"
                          : "border-[#1e2430] focus-within:border-primary-container focus-within:ring-primary-container/30"
                      }`}
                    >
                      <select
                        id="reg-tax-prefix"
                        name="tax_prefix"
                        aria-label="Tipo de documento"
                        value={taxPrefix}
                        onChange={(e) => handleTaxPrefixChange(e.target.value as TaxDocPrefix)}
                        className="px-3 py-2.5 bg-surface-container border-r border-[#1e2430] text-xs font-mono font-bold text-primary focus:outline-hidden cursor-pointer shrink-0"
                      >
                        {TAX_PREFIX_OPTIONS.map((opt) => (
                          <option key={opt.id} value={opt.id} className="bg-[#141920] text-white">
                            {opt.label}
                          </option>
                        ))}
                      </select>

                      <div className="relative flex-1 min-w-0">
                        <span
                          className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                          aria-hidden="true"
                        >
                          id_card
                        </span>
                        <input
                          id="reg-tax-id"
                          name="tax_number"
                          type="text"
                          inputMode="numeric"
                          disabled={taxPrefix === "NONE"}
                          autoComplete="off"
                          autoCorrect="off"
                          autoCapitalize="none"
                          spellCheck={false}
                          enterKeyHint="next"
                          maxLength={selectedTaxMeta.isRif ? 10 : 9}
                          aria-invalid={Boolean(fieldErrors.taxId)}
                          aria-describedby={fieldErrors.taxId ? "reg-tax-err" : undefined}
                          value={taxNumber}
                          onChange={(e) => handleTaxNumberChange(e.target.value)}
                          onBlur={() => validateField("taxId")}
                          placeholder={selectedTaxMeta.placeholder}
                          className="w-full h-full pl-10 pr-3 py-2.5 bg-transparent focus:outline-hidden text-sm text-white font-mono tabular-nums placeholder:text-slate-600 disabled:opacity-45"
                        />
                      </div>
                    </div>
                    {fieldErrors.taxId && (
                      <p id="reg-tax-err" className="text-[10px] text-error mt-1">
                        {fieldErrors.taxId}
                      </p>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={validateStep1AndNext}
                    className="w-full py-2.5 px-4 rounded-lg bg-primary-container text-on-primary font-bold text-sm hover:brightness-110 transition-all flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <span>Siguiente</span>
                    <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                      arrow_forward
                    </span>
                  </button>
                </div>
              )}

              {/* PASO 2: TELEGRAM OBLIGATORIO, CONTRASEÑA Y RECUPERACIÓN */}
              {step === 2 && (
                <div className="space-y-4">
                  {/* Guía de Bot de Telegram + Input Obligatorio */}
                  <div className="p-3.5 rounded-xl bg-secondary/8 border border-secondary/30 space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-[18px] text-secondary" aria-hidden="true">
                          smart_toy
                        </span>
                        <span className="text-xs font-bold text-white">
                          Vincular Bot de Telegram *
                        </span>
                      </div>
                      {botInfo?.bot_url ? (
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <a
                            href={botInfo.bot_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-2.5 py-1 rounded-lg bg-secondary text-on-secondary text-[11px] font-bold hover:brightness-110 flex items-center gap-1"
                          >
                            <span>Abrir {botInfo.bot_mention || botInfo.bot_name}</span>
                            <span className="material-symbols-outlined text-[13px]" aria-hidden="true">
                              open_in_new
                            </span>
                          </a>
                          {botInfo.bot_mention && (
                            <button
                              type="button"
                              onClick={() => {
                                navigator.clipboard?.writeText(botInfo.bot_mention || "");
                                setCopiedBotHandle(true);
                                setTimeout(() => setCopiedBotHandle(false), 2000);
                              }}
                              className="px-2 py-1 rounded-lg bg-surface-container border border-[#1e2430] text-[10px] font-mono text-slate-200 hover:text-white cursor-pointer"
                            >
                              {copiedBotHandle ? "✓ Copiado" : `Copiar ${botInfo.bot_mention}`}
                            </button>
                          )}
                        </div>
                      ) : (
                        <span className="text-[10px] font-mono text-secondary">
                          Envía /id al bot del sistema en Telegram
                        </span>
                      )}
                    </div>

                    <p className="text-[11px] text-slate-300 leading-relaxed">
                      1. Abre{" "}
                      <strong className="text-white">
                        {botInfo?.bot_mention || botInfo?.bot_name || "nuestro bot en Telegram"}
                      </strong>{" "}
                      y toca <strong className="text-secondary">Iniciar</strong> o envía{" "}
                      <code className="px-1 py-0.5 rounded bg-surface-container text-secondary font-mono">/id</code>.
                      <br />
                      2. El bot responderá con tu número único; cópialo y pégalo abajo.
                    </p>

                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label
                            htmlFor="reg-telegram"
                            className="text-[11px] font-mono uppercase tracking-wider text-slate-300"
                          >
                            ID de Telegram *
                          </label>
                          {isTelegramValid && (
                            <span className="text-[10px] font-mono text-tertiary flex items-center gap-0.5">
                              <span className="material-symbols-outlined text-[13px]" aria-hidden="true">
                                verified
                              </span>
                              Válido
                            </span>
                          )}
                        </div>
                        <div className="relative">
                          <span
                            className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2"
                            aria-hidden="true"
                          >
                            send
                          </span>
                          <input
                            id="reg-telegram"
                            name="telegram_id"
                            type="tel"
                            required
                            inputMode="numeric"
                            pattern="[0-9]{5,15}"
                            maxLength={15}
                            enterKeyHint="next"
                            aria-invalid={Boolean(fieldErrors.telegramId)}
                            aria-describedby={fieldErrors.telegramId ? "reg-telegram-err" : undefined}
                            value={telegramId}
                            onChange={(e) => {
                              setTelegramId(e.target.value.replace(/\D/g, ""));
                              clearFieldError("telegramId");
                            }}
                            onBlur={() => validateField("telegramId")}
                            placeholder="6326947793"
                            className={`w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-sm text-white font-mono tabular-nums placeholder:text-slate-600 ${
                              fieldErrors.telegramId
                                ? "border-error focus:border-error"
                                : "border-[#1e2430] focus:border-secondary"
                            }`}
                          />
                        </div>
                        {fieldErrors.telegramId && (
                          <p id="reg-telegram-err" className="text-[10px] text-error mt-1">
                            {fieldErrors.telegramId}
                          </p>
                        )}
                      </div>
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
                          aria-pressed={showPassword}
                          onClick={() => setShowPassword(!showPassword)}
                          className="text-[10px] font-mono text-slate-400 hover:text-white"
                        >
                          {showPassword ? "Ocultar" : "Mostrar"}
                        </button>
                      </div>
                      <input
                        id="reg-password"
                        name="password"
                        type={showPassword ? "text" : "password"}
                        required
                        minLength={8}
                        autoComplete="new-password"
                        enterKeyHint="next"
                        aria-invalid={Boolean(fieldErrors.password)}
                        aria-describedby={fieldErrors.password ? "reg-password-err" : undefined}
                        value={password}
                        onChange={(e) => {
                          setPassword(e.target.value);
                          clearFieldError("password");
                          if (confirmPassword && e.target.value === confirmPassword) {
                            clearFieldError("confirmPassword");
                          }
                        }}
                        onBlur={() => validateField("password")}
                        placeholder="Mínimo 8 caracteres"
                        className={`w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-sm text-white font-mono placeholder:text-slate-600 ${
                          fieldErrors.password
                            ? "border-error focus:border-error"
                            : "border-[#1e2430] focus:border-primary-container"
                        }`}
                      />
                      {fieldErrors.password && (
                        <p id="reg-password-err" className="text-[10px] text-error mt-1">
                          {fieldErrors.password}
                        </p>
                      )}
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
                        id="reg-confirm-password"
                        name="confirm_password"
                        type={showPassword ? "text" : "password"}
                        required
                        minLength={8}
                        autoComplete="new-password"
                        enterKeyHint="next"
                        aria-invalid={Boolean(fieldErrors.confirmPassword)}
                        aria-describedby={fieldErrors.confirmPassword ? "reg-confirm-password-err" : undefined}
                        value={confirmPassword}
                        onChange={(e) => {
                          setConfirmPassword(e.target.value);
                          clearFieldError("confirmPassword");
                        }}
                        onBlur={() => validateField("confirmPassword")}
                        placeholder="Repite tu contraseña"
                        className={`w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-sm text-white font-mono placeholder:text-slate-600 ${
                          fieldErrors.confirmPassword
                            ? "border-error focus:border-error"
                            : "border-[#1e2430] focus:border-primary-container"
                        }`}
                      />
                      {fieldErrors.confirmPassword && (
                        <p id="reg-confirm-password-err" className="text-[10px] text-error mt-1">
                          {fieldErrors.confirmPassword}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Medidor de Fortaleza */}
                  <div className="p-2.5 rounded-lg bg-surface-container border border-[#1e2430]">
                    <div className="flex items-center justify-between text-[11px] font-mono mb-1.5">
                      <span className="text-slate-400">Seguridad de contraseña</span>
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

                  {/* Pregunta y Respuesta Secreta */}
                  <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-3">
                    <div className="flex items-center gap-1.5 text-[11px] font-mono font-bold uppercase tracking-wider text-primary">
                      <span className="material-symbols-outlined text-[15px]" aria-hidden="true">
                        shield_lock
                      </span>
                      <span>Pregunta de respaldo</span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label
                          htmlFor="reg-sec-question"
                          className="block text-[10px] font-mono uppercase text-slate-400 mb-1.5"
                        >
                          Pregunta de Seguridad *
                        </label>
                        <select
                          id="reg-sec-question"
                          name="security_question"
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
                            aria-pressed={showAnswer}
                            onClick={() => setShowAnswer(!showAnswer)}
                            className="text-[10px] font-mono text-slate-400 hover:text-white"
                          >
                            {showAnswer ? "Ocultar" : "Mostrar"}
                          </button>
                        </div>
                        <input
                          id="reg-sec-answer"
                          name="security_answer"
                          type={showAnswer ? "text" : "password"}
                          required
                          minLength={3}
                          autoComplete="off"
                          autoCorrect="off"
                          autoCapitalize="none"
                          spellCheck={false}
                          enterKeyHint="next"
                          aria-invalid={Boolean(fieldErrors.securityAnswer)}
                          aria-describedby={fieldErrors.securityAnswer ? "reg-sec-answer-err" : undefined}
                          value={securityAnswer}
                          onChange={(e) => {
                            setSecurityAnswer(e.target.value);
                            clearFieldError("securityAnswer");
                          }}
                          onBlur={() => validateField("securityAnswer")}
                          placeholder="Mínimo 3 caracteres"
                          className={`w-full px-3 py-2.5 rounded-lg bg-surface-container-lowest border focus:outline-hidden text-xs text-white font-mono placeholder:text-slate-600 ${
                            fieldErrors.securityAnswer
                              ? "border-error focus:border-error"
                              : "border-[#1e2430] focus:border-primary-container"
                          }`}
                        />
                        {fieldErrors.securityAnswer && (
                          <p id="reg-sec-answer-err" className="text-[10px] text-error mt-1">
                            {fieldErrors.securityAnswer}
                          </p>
                        )}
                      </div>
                    </div>

                    {selectedQuestionPreset === "__custom__" && (
                      <div>
                        <input
                          id="reg-sec-custom-question"
                          name="custom_security_question"
                          type="text"
                          required
                          minLength={5}
                          aria-invalid={Boolean(fieldErrors.customQuestion)}
                          value={customQuestion}
                          onChange={(e) => {
                            setCustomQuestion(e.target.value);
                            clearFieldError("customQuestion");
                          }}
                          onBlur={() => validateField("customQuestion")}
                          placeholder="Escribe tu pregunta secreta personal..."
                          className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs text-white"
                        />
                        {fieldErrors.customQuestion && (
                          <p className="text-[10px] text-error mt-1">{fieldErrors.customQuestion}</p>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => goToStep(1)}
                      enterKeyHint="previous"
                      className="px-4 py-2.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-slate-500 text-xs font-mono text-slate-200 flex items-center gap-1.5 cursor-pointer shrink-0"
                    >
                      <span className="material-symbols-outlined text-[16px]" aria-hidden="true">
                        arrow_back
                      </span>
                      <span>Anterior</span>
                    </button>
                    <button
                      type="button"
                      onClick={validateStep2AndNext}
                      className="flex-1 py-2.5 px-4 rounded-lg bg-primary-container text-on-primary font-bold text-sm hover:brightness-110 transition-all flex items-center justify-center gap-2 cursor-pointer"
                    >
                      <span>Siguiente</span>
                      <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                        arrow_forward
                      </span>
                    </button>
                  </div>
                </div>
              )}

              {/* PASO 3: BANCOS Y GOOGLE SHEETS */}
              {step === 3 && (
                <div className="space-y-4">
                  {/* Bancos con los que opera */}
                  <div className="p-4 rounded-xl bg-surface-container border border-[#1e2430] space-y-3">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="text-[11px] font-mono uppercase tracking-wider text-white font-semibold">
                        ¿Con qué bancos trabajas? ({preferredBanks.length}) *
                      </span>
                      <span className="text-[10px] font-mono text-primary">
                        Personaliza tus saldos y spreads recomendados
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {VENEZUELAN_BANK_CATALOG.map((bankOpt) => {
                        const active = preferredBanks.includes(bankOpt);
                        return (
                          <button
                            key={bankOpt}
                            type="button"
                            aria-pressed={active}
                            onClick={() =>
                              setPreferredBanks((prev) =>
                                prev.includes(bankOpt)
                                  ? prev.filter((b) => b !== bankOpt)
                                  : [...prev, bankOpt]
                              )
                            }
                            className={`px-2.5 py-1.5 rounded-lg text-xs font-mono transition-colors flex items-center gap-1 cursor-pointer ${
                              active
                                ? "bg-primary-container text-on-primary font-bold"
                                : "bg-surface-container-low text-slate-400 hover:text-white border border-[#1e2430]"
                            }`}
                          >
                            <span>{active ? "✓" : "+"}</span>
                            <span>{bankOpt}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Google Sheet Opcional */}
                  <div>
                    <label
                      htmlFor="reg-google-sheet"
                      className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
                    >
                      Google Sheets (Opcional)
                    </label>
                    <div className="relative">
                      <span
                        className="material-symbols-outlined text-[18px] text-slate-500 absolute left-3 top-1/2 -translate-y-1/2"
                        aria-hidden="true"
                      >
                        table_chart
                      </span>
                      <input
                        id="reg-google-sheet"
                        name="google_sheet_id"
                        type="text"
                        autoComplete="off"
                        autoCorrect="off"
                        autoCapitalize="none"
                        spellCheck={false}
                        enterKeyHint="done"
                        value={googleSheetId}
                        onChange={(e) => setGoogleSheetId(e.target.value)}
                        placeholder="Enlace o ID de tu hoja (opcional)"
                        className="w-full pl-10 pr-3 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-tertiary focus:outline-hidden text-xs text-white font-mono placeholder:text-slate-600"
                      />
                    </div>
                  </div>

                  {/* Resumen de Confirmación */}
                  <div className="p-3 rounded-xl bg-surface-container-lowest border border-[#1e2430] text-[11px] font-mono space-y-1">
                    <div className="flex justify-between gap-2">
                      <span className="text-slate-400">Usuario:</span>
                      <span className="text-white truncate">{fullName} (@{username})</span>
                    </div>
                    <div className="flex justify-between gap-2">
                      <span className="text-slate-400">Correo / Telegram:</span>
                      <span className="text-secondary truncate">{email} • {telegramId}</span>
                    </div>
                    <div className="flex justify-between gap-2">
                      <span className="text-slate-400">Bancos:</span>
                      <span className="text-primary truncate">{preferredBanks.join(", ") || "Ninguno"}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => goToStep(2)}
                      enterKeyHint="previous"
                      className="px-4 py-2.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-slate-500 text-xs font-mono text-slate-200 flex items-center gap-1.5 cursor-pointer shrink-0"
                    >
                      <span className="material-symbols-outlined text-[16px]" aria-hidden="true">
                        arrow_back
                      </span>
                      <span>Anterior</span>
                    </button>
                    <button
                      type="submit"
                      disabled={loading}
                      enterKeyHint="done"
                      className="flex-1 py-2.5 px-4 rounded-lg bg-primary-container text-on-primary font-bold text-sm hover:brightness-110 disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-lg shadow-primary-container/10 cursor-pointer"
                    >
                      <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                        how_to_reg
                      </span>
                      <span>{loading ? "Creando cuenta..." : "Crear cuenta"}</span>
                    </button>
                  </div>
                </div>
              )}
            </form>
          )}

          <div className="mt-5 pt-4 border-t border-[#1e2430] flex items-center justify-between text-xs">
            <span className="text-slate-400">¿Ya tienes cuenta?</span>
            <Link href="/login" className="font-semibold text-primary hover:underline">
              Iniciar sesión →
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
