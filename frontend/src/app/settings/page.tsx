"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import {
  BinanceStatusResponse,
  BotStatus,
  TelegramStatusResponse,
  User,
  authorizeTelegramUser,
  getBinanceSettings,
  getBotStatus,
  getCurrentUser,
  getTelegramSettings,
  listUsers,
  pauseBot,
  resumeBot,
  saveBinanceSettings,
  sendTelegramTestAlert,
  updateUserRole,
  updateUserSheet,
  updateUserStatus,
  verifyBinanceConnection,
} from "@/lib/api";

export default function SettingsSecurityPage() {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [binanceStatus, setBinanceStatus] = useState<BinanceStatusResponse | null>(
    null
  );
  const [telegramStatus, setTelegramStatus] =
    useState<TelegramStatusResponse | null>(null);
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [operators, setOperators] = useState<User[]>([]);

  // Formulario Write-Only para llaves Binance (CERO exposición de secretos en DOM)
  const [keyType, setKeyType] = useState<"Ed25519" | "HMAC">("Ed25519");
  const [apiKeyInput, setApiKeyInput] = useState<string>("");
  const [secretKeyInput, setSecretKeyInput] = useState<string>("");

  // Formulario Admin RBAC para pre-autorizar operador por Telegram ID
  const [newTgId, setNewTgId] = useState<string>("");
  const [newUsername, setNewUsername] = useState<string>("");
  const [newRole, setNewRole] = useState<"ADMIN" | "TRADER" | "INVITADO">("TRADER");

  // Edición inline de Sheet ID por operador
  const [editingSheetUserId, setEditingSheetUserId] = useState<number | null>(null);
  const [editingSheetVal, setEditingSheetVal] = useState<string>("");

  const [loading, setLoading] = useState<boolean>(true);
  const [savingKeys, setSavingKeys] = useState<boolean>(false);
  const [verifyingBinance, setVerifyingBinance] = useState<boolean>(false);
  const [testingTelegram, setTestingTelegram] = useState<boolean>(false);
  const [togglingBot, setTogglingBot] = useState<boolean>(false);
  const [authorizingUser, setAuthorizingUser] = useState<boolean>(false);

  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const loadAllSettings = useCallback(async () => {
    const user = getCurrentUser();
    setCurrentUser(user);
    if (!user || user.role === "INVITADO") {
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const [bStatus, tStatus, engineStatus] = await Promise.all([
        getBinanceSettings().catch(() => null),
        getTelegramSettings().catch(() => null),
        getBotStatus().catch(() => null),
      ]);

      if (bStatus) {
        setBinanceStatus(bStatus);
        if (bStatus.key_type === "HMAC" || bStatus.key_type === "Ed25519") {
          setKeyType(bStatus.key_type);
        }
      }
      if (tStatus) setTelegramStatus(tStatus);
      if (engineStatus) setBotStatus(engineStatus);

      if (user.role === "ADMIN") {
        const usersList = await listUsers().catch(() => []);
        setOperators(usersList);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAllSettings();
  }, [loadAllSettings]);

  async function handleSaveBinanceKeys(e: React.FormEvent) {
    e.preventDefault();
    setFeedback(null);
    if (!apiKeyInput.trim() || !secretKeyInput.trim()) {
      setFeedback({
        type: "error",
        text: "Ingresa tanto la API Key como la clave privada/secreta para cifrarlas en AES-256-GCM.",
      });
      return;
    }

    setSavingKeys(true);
    try {
      const res = await saveBinanceSettings({
        api_key: apiKeyInput.trim(),
        secret_key: secretKeyInput.trim(),
        key_type: keyType,
      });
      setBinanceStatus(res);
      // Limpieza inmediata de memoria del navegador (Regla Constitucional #5)
      setApiKeyInput("");
      setSecretKeyInput("");
      setFeedback({
        type: "success",
        text:
          res.message ||
          "Credenciales cifradas con AES-256-GCM y almacenadas de forma segura.",
      });
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error al guardar credenciales de Binance.",
      });
    } finally {
      setSavingKeys(false);
    }
  }

  async function handleVerifyBinance() {
    setFeedback(null);
    setVerifyingBinance(true);
    try {
      const res = await verifyBinanceConnection();
      setFeedback({
        type: res.is_connected ? "success" : "error",
        text: `${res.message} (Latencia: ${res.latency_ms} ms | Deriva NTP: ${res.clock_drift_ms} ms | Weight: ${res.used_weight}/${res.max_weight})`,
      });
      setBinanceStatus((prev) =>
        prev
          ? {
              ...prev,
              is_connected: res.is_connected,
              latency_ms: res.latency_ms,
              clock_drift_ms: res.clock_drift_ms,
              used_weight: res.used_weight,
              max_weight: res.max_weight,
            }
          : prev
      );
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Fallo verificando conectividad con la API oficial de Binance.",
      });
    } finally {
      setVerifyingBinance(false);
    }
  }

  async function handleTestTelegram() {
    setFeedback(null);
    setTestingTelegram(true);
    try {
      const res = await sendTelegramTestAlert();
      setFeedback({
        type: res.success ? "success" : "error",
        text: res.message,
      });
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error enviando alerta sanitizada por Telegram.",
      });
    } finally {
      setTestingTelegram(false);
    }
  }

  async function handleToggleEmergencyPause() {
    if (currentUser?.role !== "ADMIN") return;
    setFeedback(null);
    setTogglingBot(true);
    try {
      if (botStatus?.is_paused) {
        await resumeBot();
        setFeedback({
          type: "success",
          text: "Motor operativo P2P reanudado correctamente.",
        });
      } else {
        await pauseBot();
        setFeedback({
          type: "success",
          text: "Pausa Fail-Closed activada. Todas las operaciones automáticas están detenidas.",
        });
      }
      await loadAllSettings();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo cambiar el estado del motor.",
      });
    } finally {
      setTogglingBot(false);
    }
  }

  async function handleAuthorizeOperator(e: React.FormEvent) {
    e.preventDefault();
    if (!newTgId.trim()) return;
    setFeedback(null);
    setAuthorizingUser(true);
    try {
      const created = await authorizeTelegramUser({
        telegram_id: newTgId.trim(),
        username: newUsername.trim() || undefined,
        role: newRole,
      });
      setNewTgId("");
      setNewUsername("");
      setFeedback({
        type: "success",
        text: `Operador ${created.username} (TG: ${created.telegram_id}) autorizado en BD con rol ${created.role}.`,
      });
      await loadAllSettings();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error al autorizar operador por Telegram ID.",
      });
    } finally {
      setAuthorizingUser(false);
    }
  }

  async function handleRoleChange(
    targetUser: User,
    role: "ADMIN" | "TRADER" | "INVITADO"
  ) {
    setFeedback(null);
    try {
      await updateUserRole(targetUser.id, role);
      setFeedback({
        type: "success",
        text: `Rol de ${targetUser.username} actualizado a ${role}.`,
      });
      await loadAllSettings();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo cambiar el rol del operador.",
      });
    }
  }

  async function handleToggleStatus(targetUser: User) {
    setFeedback(null);
    try {
      await updateUserStatus(targetUser.id, !targetUser.is_active);
      setFeedback({
        type: "success",
        text: `Estado de ${targetUser.username}: ${
          !targetUser.is_active ? "Activo" : "Suspendido"
        }.`,
      });
      await loadAllSettings();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo cambiar el estado del operador.",
      });
    }
  }

  async function handleSaveUserSheet(userId: number) {
    setFeedback(null);
    try {
      await updateUserSheet(userId, editingSheetVal.trim() || null);
      setEditingSheetUserId(null);
      setEditingSheetVal("");
      setFeedback({
        type: "success",
        text: "Google Sheet del operador actualizado.",
      });
      await loadAllSettings();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo actualizar la hoja del operador.",
      });
    }
  }

  if (!currentUser || currentUser.role === "INVITADO") {
    return (
      <AppShell
        title="Configuración API, Seguridad & Operadores"
        badge="ACCESO RESTRINGIDO"
        subtitle="Bóveda criptográfica AES-256-GCM y gobierno RBAC para operadores autorizados."
      >
        <div className="max-w-lg mx-auto my-12 p-6 rounded-2xl bg-surface-container-low border border-[#1e2430] text-center space-y-4">
          <span className="material-symbols-outlined text-[36px] text-primary">
            shield_lock
          </span>
          <h2 className="text-base font-bold text-white">
            Se requiere sesión activa con rol TRADER o ADMIN
          </h2>
          <p className="text-xs text-slate-400">
            Inicia sesión para gestionar llaves cifradas de Binance P2P, alertas sanitizadas de Telegram y operadores RBAC.
          </p>
          <Link
            href="/login"
            className="inline-block px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold"
          >
            Iniciar Sesión
          </Link>
        </div>
      </AppShell>
    );
  }

  const usedWeight = binanceStatus?.used_weight ?? 0;
  const maxWeight = binanceStatus?.max_weight ?? 6000;
  const isPaused = botStatus?.is_paused ?? false;

  return (
    <AppShell
      title="Configuración API, Seguridad & Operadores"
      badge="ZERO-SECRETS • AES-256-GCM"
      subtitle="Gestión criptográfica de credenciales Binance C2C, políticas Fail-Closed, sanitización Telegram y control de acceso RBAC."
      actions={
        <button
          type="button"
          onClick={handleVerifyBinance}
          disabled={verifyingBinance}
          className="px-3.5 py-1.5 rounded-lg bg-secondary/15 border border-secondary/35 text-secondary text-xs font-mono font-semibold hover:bg-secondary/25 flex items-center gap-1.5"
        >
          <span
            className={`material-symbols-outlined text-[16px] ${
              verifyingBinance ? "animate-spin" : ""
            }`}
          >
            network_check
          </span>
          <span>
            {verifyingBinance ? "Auditando API..." : "Diagnosticar Conexión Binance"}
          </span>
        </button>
      }
    >
      <div className="space-y-5">
        {feedback && (
          <div
            className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 text-xs ${
              feedback.type === "success"
                ? "bg-tertiary/10 border-tertiary/30 text-emerald-200"
                : "bg-error/10 border-error/30 text-red-200"
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">
                {feedback.type === "success" ? "verified_user" : "gpp_bad"}
              </span>
              <span>{feedback.text}</span>
            </div>
            <button
              type="button"
              onClick={() => setFeedback(null)}
              className="text-slate-400 hover:text-white"
            >
              ✕
            </button>
          </div>
        )}

        {/* 4 KPIs de Telemetría de Seguridad Institucional */}
        <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Bóveda en Reposo</span>
              <span className="material-symbols-outlined text-[16px] text-tertiary">
                enhanced_encryption
              </span>
            </div>
            <div className="mt-2 text-lg font-mono font-bold text-tertiary">
              AES-256-GCM
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400">
              Firma activa: {binanceStatus?.key_type || keyType}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Monitor x-mbx-used-weight</span>
              <span className="material-symbols-outlined text-[16px] text-primary">
                speed
              </span>
            </div>
            <div
              className={`mt-2 text-lg font-mono font-bold tabular-nums ${
                usedWeight >= 5000 ? "text-error" : "text-white"
              }`}
            >
              {usedWeight} / {maxWeight}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400">
              Pausa automática &gt; 5,000 (60s)
            </div>
          </div>

          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Deriva de Reloj & Latencia</span>
              <span className="material-symbols-outlined text-[16px] text-secondary">
                schedule
              </span>
            </div>
            <div className="mt-2 text-lg font-mono font-bold text-secondary tabular-nums">
              {binanceStatus ? `${binanceStatus.clock_drift_ms} ms` : "-- ms"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              Latencia REST: {binanceStatus ? `${binanceStatus.latency_ms} ms` : "--"}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Arquitectura Fail-Closed</span>
              <span className="material-symbols-outlined text-[16px] text-primary">
                security
              </span>
            </div>
            <div
              className={`mt-2 text-lg font-mono font-bold ${
                isPaused ? "text-error" : "text-tertiary"
              }`}
            >
              {isPaused ? "DETENIDO (PAUSA)" : "PROTECCIÓN ACTIVA"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400">
              Cero RPA • Solo API Oficial Binance
            </div>
          </div>
        </section>

        {/* Fila Central: Bóveda Binance (Izquierda) + Telegram & Fail-Closed (Derecha) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Tarjeta 1: Credenciales Binance C2C (Sanitizadas — Cero Secretos en DOM) */}
          <section className="lg:col-span-7 p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-4">
            <div className="border-b border-[#1e2430] pb-3 flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-primary">
                  vpn_key
                </span>
                <h2 className="text-sm font-bold text-white">
                  Credenciales Oficiales Binance P2P (Write-Only Vault)
                </h2>
              </div>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                  binanceStatus?.is_configured
                    ? "bg-tertiary/15 text-tertiary"
                    : "bg-primary-container/15 text-primary"
                }`}
              >
                {binanceStatus?.is_configured ? "LLAVE CIFRADA" : "NO CONFIGURADA"}
              </span>
            </div>

            {/* Resumen Enmascarado Actual (NUNCA expone la llave completa ni en el portapapeles) */}
            <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="text-[10px] font-mono uppercase text-slate-400">
                  API Key Activa (Enmascarada por Regla Constitucional #5)
                </div>
                <div className="mt-1 text-sm font-mono font-bold text-white tracking-wider">
                  {binanceStatus?.api_key_masked || "Sin llave registrada"}
                </div>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap">
                {(binanceStatus?.permissions?.length
                  ? binanceStatus.permissions
                  : ["READING", "P2P_TRADING"]
                ).map((perm) => (
                  <span
                    key={perm}
                    className="px-2 py-0.5 rounded bg-surface-container-high border border-[#1e2430] text-[10px] font-mono text-slate-300"
                  >
                    {perm}
                  </span>
                ))}
              </div>
            </div>

            <form onSubmit={handleSaveBinanceKeys} className="space-y-3.5">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
                  Algoritmo Criptográfico de Firma
                </label>
                <div className="flex rounded-lg bg-surface-container p-0.5 border border-[#1e2430] text-xs font-mono">
                  <button
                    type="button"
                    onClick={() => setKeyType("Ed25519")}
                    className={`px-3 py-1 rounded-md transition-colors ${
                      keyType === "Ed25519"
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Ed25519 (Recomendado)
                  </button>
                  <button
                    type="button"
                    onClick={() => setKeyType("HMAC")}
                    className={`px-3 py-1 rounded-md transition-colors ${
                      keyType === "HMAC"
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    HMAC-SHA256
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1">
                  Nueva API Key de Binance (Solo Escritura)
                </label>
                  <input
                  type="password"
                  autoComplete="off"
                  disabled={currentUser?.role !== "ADMIN"}
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder="Introduce nueva API Key para rotar credencial..."
                  className="w-full px-3.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs font-mono text-white placeholder:text-slate-600 disabled:opacity-50"
                />
              </div>

              <div>
                <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1">
                  {keyType === "Ed25519"
                    ? "Clave Privada Ed25519 (PEM / Base64 — Solo Escritura)"
                    : "Secret Key HMAC-SHA256 (Solo Escritura)"}
                </label>
                <input
                  type="password"
                  autoComplete="off"
                  disabled={currentUser?.role !== "ADMIN"}
                  value={secretKeyInput}
                  onChange={(e) => setSecretKeyInput(e.target.value)}
                  placeholder="Se cifra en AES-256-GCM y jamás vuelve a enviarse al navegador..."
                  className="w-full px-3.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs font-mono text-white placeholder:text-slate-600 disabled:opacity-50"
                />
              </div>

              <div className="flex items-center justify-between gap-2 pt-1 flex-wrap">
                <span className="text-[10px] font-mono text-slate-500">
                  {currentUser?.role === "ADMIN"
                    ? "Permisos requeridos: Enable Reading + P2P. Prohibido Enable Withdrawals."
                    : "Solo rol ADMIN puede rotar llaves maestras de Binance."}
                </span>
                <button
                  type="submit"
                  disabled={savingKeys || currentUser?.role !== "ADMIN"}
                  className="px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-50"
                >
                  {savingKeys ? "Cifrando..." : "Rotar & Cifrar Credenciales"}
                </button>
              </div>
            </form>
          </section>

          {/* Tarjeta 2: Notificador Sanitizado Telegram + Controles Fail-Closed */}
          <section className="lg:col-span-5 p-5 rounded-xl bg-surface-container-low border border-[#1e2430] flex flex-col justify-between gap-4">
            <div className="space-y-4">
              <div className="border-b border-[#1e2430] pb-3 flex items-center justify-between">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="material-symbols-outlined text-[18px] text-secondary">
                    send
                  </span>
                  Telegram & Reglas Fail-Closed
                </h2>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                    telegramStatus?.is_configured
                      ? "bg-secondary/15 text-secondary"
                      : "bg-slate-800 text-slate-400"
                  }`}
                >
                  {telegramStatus?.is_configured ? "BOT CONECTADO" : "SIN TOKEN"}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-surface-container border border-[#1e2430] space-y-2 text-xs font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Token Sanitizado:</span>
                  <span className="text-white">
                    {telegramStatus?.bot_token_masked || "No configurado"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Tu Telegram Vinculado:</span>
                  <span className="text-secondary">
                    {telegramStatus?.linked_chat_id || currentUser.telegram_id || "Sin vincular"}
                  </span>
                </div>
              </div>

              <div className="space-y-2 text-xs">
                {[
                  {
                    label: "Detención Fail-Closed ante errores 5xx, timeout o IP no autorizada",
                    active: telegramStatus?.fail_closed_5xx_enabled ?? true,
                  },
                  {
                    label: "Pausa preventiva de 60s si x-mbx-used-weight supera 5,000",
                    active: telegramStatus?.weight_pause_enabled ?? true,
                  },
                  {
                    label: "Filtro Regex anti-filtración de secretos en logs y Telegram",
                    active: telegramStatus?.log_sanitization_enabled ?? true,
                  },
                ].map((policy) => (
                  <div
                    key={policy.label}
                    className="p-2.5 rounded-lg bg-surface-container border border-[#1e2430] flex items-center justify-between gap-2"
                  >
                    <span className="text-[11px] text-slate-300">{policy.label}</span>
                    <span className="px-2 py-0.5 rounded bg-tertiary/15 text-tertiary text-[10px] font-mono font-bold shrink-0">
                      {policy.active ? "ON" : "OFF"}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-3 border-t border-[#1e2430] flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={handleTestTelegram}
                disabled={testingTelegram}
                className="px-3.5 py-2 rounded-lg bg-secondary/15 border border-secondary/35 text-secondary text-xs font-mono font-semibold hover:bg-secondary/25"
              >
                {testingTelegram ? "Enviando..." : "Enviar Alerta de Prueba"}
              </button>

              {currentUser.role === "ADMIN" && (
                <button
                  type="button"
                  onClick={handleToggleEmergencyPause}
                  disabled={togglingBot}
                  className={`px-3.5 py-2 rounded-lg text-xs font-bold ${
                    isPaused
                      ? "bg-tertiary text-on-tertiary"
                      : "bg-error text-on-error"
                  }`}
                >
                  {isPaused ? "Reanudar Motor P2P" : "Parada Fail-Closed"}
                </button>
              )}
            </div>
          </section>
        </div>

        {/* Sección Exclusiva ADMIN: Gobierno de Operadores RBAC (.env + Base de Datos) */}
        {currentUser.role === "ADMIN" && (
          <section className="rounded-xl bg-surface-container-low border border-[#1e2430] overflow-hidden">
            <div className="p-4 border-b border-[#1e2430] flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="material-symbols-outlined text-[18px] text-primary">
                    admin_panel_settings
                  </span>
                  Gobierno de Operadores RBAC & Persistencia Dual (.env + Base de Datos)
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Autoriza operadores dinámicamente en SQLite/PostgreSQL o audita permisos declarados en variables de entorno.
                </p>
              </div>

              {/* Alta Rápida por Telegram ID */}
              <form
                onSubmit={handleAuthorizeOperator}
                className="flex items-center gap-2 flex-wrap"
              >
                <input
                  type="text"
                  inputMode="numeric"
                  value={newTgId}
                  onChange={(e) => setNewTgId(e.target.value.replace(/\D/g, ""))}
                  placeholder="Telegram ID (ej. 2076708117)"
                  className="w-48 px-3 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono text-white"
                />
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="Alias opcional"
                  className="w-36 px-3 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono text-white"
                />
                <select
                  value={newRole}
                  onChange={(e) =>
                    setNewRole(e.target.value as "ADMIN" | "TRADER" | "INVITADO")
                  }
                  className="px-2.5 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono text-primary"
                >
                  <option value="TRADER">TRADER</option>
                  <option value="ADMIN">ADMIN</option>
                  <option value="INVITADO">INVITADO</option>
                </select>
                <button
                  type="submit"
                  disabled={authorizingUser || !newTgId}
                  className="px-3.5 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-40 whitespace-nowrap"
                >
                  {authorizingUser ? "Autorizando..." : "+ Autorizar Operador"}
                </button>
              </form>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[#1e2430] bg-surface-container/60 text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    <th className="py-3 px-4">Operador</th>
                    <th className="py-3 px-4">Telegram ID</th>
                    <th className="py-3 px-4">Rol RBAC</th>
                    <th className="py-3 px-4">Origen del Permiso</th>
                    <th className="py-3 px-4">Google Sheet Contable</th>
                    <th className="py-3 px-4">Estado</th>
                    <th className="py-3 px-4 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2430]/70 text-xs">
                  {loading ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400 font-mono">
                        Cargando directorio de operadores...
                      </td>
                    </tr>
                  ) : operators.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400 font-mono">
                        No hay operadores registrados.
                      </td>
                    </tr>
                  ) : (
                    operators.map((op) => {
                      const isEnvImmutable =
                        op.permission_source?.includes("Inmutable") ?? false;
                      return (
                        <tr
                          key={op.id}
                          className="hover:bg-surface-container/70 transition-colors"
                        >
                          <td className="py-3 px-4 font-semibold text-white">
                            {op.username}
                          </td>
                          <td className="py-3 px-4 font-mono tabular-nums text-secondary">
                            {op.telegram_id || "—"}
                          </td>
                          <td className="py-3 px-4">
                            <select
                              disabled={isEnvImmutable || op.id === currentUser.id}
                              value={op.role}
                              onChange={(e) =>
                                handleRoleChange(
                                  op,
                                  e.target.value as "ADMIN" | "TRADER" | "INVITADO"
                                )
                              }
                              className="px-2 py-1 rounded bg-surface-container border border-[#1e2430] text-xs font-mono font-bold text-white disabled:opacity-60"
                            >
                              <option value="ADMIN">ADMIN</option>
                              <option value="TRADER">TRADER</option>
                              <option value="INVITADO">INVITADO</option>
                            </select>
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-mono whitespace-nowrap ${
                                op.permission_source?.includes(".env")
                                  ? "bg-primary-container/15 text-primary border border-primary-container/30"
                                  : "bg-surface-container-high text-slate-300 border border-[#1e2430]"
                              }`}
                            >
                              {op.permission_source || "Base de Datos"}
                            </span>
                          </td>
                          <td className="py-3 px-4 font-mono text-[11px]">
                            {editingSheetUserId === op.id ? (
                              <div className="flex items-center gap-1.5">
                                <input
                                  type="text"
                                  value={editingSheetVal}
                                  onChange={(e) => setEditingSheetVal(e.target.value)}
                                  placeholder="URL o ID Sheet"
                                  className="w-36 px-2 py-1 rounded bg-surface-container-lowest border border-[#1e2430] text-white text-[11px]"
                                />
                                <button
                                  type="button"
                                  onClick={() => handleSaveUserSheet(op.id)}
                                  className="px-2 py-1 rounded bg-tertiary text-on-tertiary font-bold text-[10px]"
                                >
                                  OK
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setEditingSheetUserId(null)}
                                  className="text-slate-400 hover:text-white px-1"
                                >
                                  ✕
                                </button>
                              </div>
                            ) : (
                              <div className="flex items-center gap-2">
                                <span className="text-slate-400 truncate max-w-[130px]">
                                  {op.google_sheet_id
                                    ? `${op.google_sheet_id.slice(0, 12)}…`
                                    : "Sin hoja"}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setEditingSheetUserId(op.id);
                                    setEditingSheetVal(op.google_sheet_id || "");
                                  }}
                                  className="text-primary hover:underline text-[10px] whitespace-nowrap"
                                >
                                  Asignar
                                </button>
                              </div>
                            )}
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold whitespace-nowrap ${
                                op.is_active
                                  ? "bg-tertiary/15 text-tertiary"
                                  : "bg-error/15 text-error"
                              }`}
                            >
                              {op.is_active ? "ACTIVO" : "SUSPENDIDO"}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right">
                            <div className="inline-flex items-center gap-1.5 whitespace-nowrap">
                              {op.role === "INVITADO" && (
                                <button
                                  type="button"
                                  onClick={() => handleRoleChange(op, "TRADER")}
                                  className="px-2.5 py-1 rounded bg-tertiary/15 hover:bg-tertiary/25 text-tertiary border border-tertiary/30 text-[10px] font-mono font-bold whitespace-nowrap"
                                >
                                  Aprobar Trader
                                </button>
                              )}
                              {op.id !== currentUser.id && !isEnvImmutable && (
                                <button
                                  type="button"
                                  onClick={() => handleToggleStatus(op)}
                                  className={`px-2.5 py-1 rounded border text-[10px] font-mono font-bold whitespace-nowrap ${
                                    op.is_active
                                      ? "bg-error/10 border-error/30 text-error hover:bg-error/20"
                                      : "bg-tertiary/10 border-tertiary/30 text-tertiary hover:bg-tertiary/20"
                                  }`}
                                >
                                  {op.is_active ? "Suspender" : "Reactivar"}
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </AppShell>
  );
}
