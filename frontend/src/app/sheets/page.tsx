"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import {
  GoogleSheetsConfigResponse,
  GoogleSheetsSyncResponse,
  User,
  getCurrentUser,
  getSheetsSettings,
  saveSheetsSettings,
  syncSheetsNow,
} from "@/lib/api";

export default function SheetsSyncPage() {
  const [user, setUser] = useState<User | null>(null);
  const [config, setConfig] = useState<GoogleSheetsConfigResponse | null>(null);
  const [sheetInput, setSheetInput] = useState<string>("");
  const [authType, setAuthType] = useState<"SERVICE_ACCOUNT" | "OAUTH2">(
    "SERVICE_ACCOUNT"
  );
  const [lastSync, setLastSync] = useState<GoogleSheetsSyncResponse | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [copiedEmail, setCopiedEmail] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const loadConfig = useCallback(async () => {
    const current = getCurrentUser();
    setUser(current);
    if (!current || current.role === "INVITADO") {
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const res = await getSheetsSettings();
      setConfig(res);
      setSheetInput(res.google_sheet_id || "");
      if (res.google_auth_type === "OAUTH2") {
        setAuthType("OAUTH2");
      } else {
        setAuthType("SERVICE_ACCOUNT");
      }
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error consultando configuración de Google Sheets.",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  async function handleSaveSheet(e: React.FormEvent) {
    e.preventDefault();
    setFeedback(null);
    setSaving(true);
    try {
      const res = await saveSheetsSettings({
        google_sheet_id: sheetInput.trim() || null,
        google_auth_type: authType,
      });
      setConfig(res);
      setSheetInput(res.google_sheet_id || "");
      setFeedback({
        type: "success",
        text: res.message || "Hoja de Google Sheets vinculada correctamente.",
      });
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo guardar el ID de Google Sheets.",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnect() {
    setFeedback(null);
    setSaving(true);
    try {
      const res = await saveSheetsSettings({
        google_sheet_id: null,
        google_auth_type: authType,
      });
      setConfig(res);
      setSheetInput("");
      setLastSync(null);
      setFeedback({
        type: "success",
        text: "Hoja de cálculo desvinculada de tu perfil operativo.",
      });
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error al desvincular la hoja de cálculo.",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleSyncNow() {
    setFeedback(null);
    setSyncing(true);
    try {
      const res = await syncSheetsNow();
      setLastSync(res);
      setFeedback({
        type: "success",
        text:
          res.message ||
          `Sincronización completada: ${res.rows_exported} órdenes y ${res.journal_entries_exported} asientos exportados.`,
      });
      await loadConfig();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text:
          err.message ||
          "Error exportando a Google Sheets. Verifica que compartiste la hoja con el correo Service Account.",
      });
    } finally {
      setSyncing(false);
    }
  }

  function handleCopyServiceEmail() {
    if (!config?.service_account_email) return;
    navigator.clipboard?.writeText(config.service_account_email);
    setCopiedEmail(true);
    setTimeout(() => setCopiedEmail(false), 2000);
  }

  if (!user || user.role === "INVITADO") {
    return (
      <AppShell
        title="Sincronización Google Sheets"
        badge="ACCESO RESTRINGIDO"
        subtitle="Exportación automática en la nube reservada para operadores TRADER y ADMIN."
      >
        <div className="max-w-lg mx-auto my-12 p-6 rounded-2xl bg-surface-container-low border border-[#1e2430] text-center space-y-4">
          <span className="material-symbols-outlined text-[36px] text-tertiary">
            sync_alt
          </span>
          <h2 className="text-base font-bold text-white">
            Inicia sesión con rol TRADER o ADMIN
          </h2>
          <p className="text-xs text-slate-400">
            Vincula tu propia hoja de Google Sheets para recibir órdenes FIFO, Libro Diario y Libro Mayor en tiempo real.
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

  const isConnected = Boolean(config?.is_connected && config?.google_sheet_id);

  return (
    <AppShell
      title="Sincronización Google Sheets"
      badge={isConnected ? "CONECTADO" : "PENDIENTE DE VÍNCULO"}
      subtitle="Puente directo entre el motor contable FIFO/SENIAT y tu hoja de cálculo individual en Google Cloud."
      actions={
        <div className="flex items-center gap-2">
          {config?.google_sheet_url && (
            <a
              href={config.google_sheet_url}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-tertiary/50 text-xs font-mono text-slate-200 flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-[15px] text-tertiary">
                open_in_new
              </span>
              <span>Abrir Google Sheet</span>
            </a>
          )}
          <button
            type="button"
            onClick={handleSyncNow}
            disabled={!isConnected || syncing}
            className="px-3.5 py-1.5 rounded-lg bg-tertiary text-on-tertiary text-xs font-bold hover:brightness-110 disabled:opacity-40 flex items-center gap-1.5"
          >
            <span
              className={`material-symbols-outlined text-[16px] ${
                syncing ? "animate-spin" : ""
              }`}
            >
              sync
            </span>
            <span>{syncing ? "Exportando..." : "Sincronizar Ahora"}</span>
          </button>
        </div>
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
                {feedback.type === "success" ? "check_circle" : "error"}
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

        {/* 3 KPIs de Estado de Conexión */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
              Estado del Vínculo
            </div>
            <div
              className={`mt-2 text-lg font-mono font-bold flex items-center gap-2 ${
                isConnected ? "text-tertiary" : "text-primary"
              }`}
            >
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  isConnected ? "bg-tertiary animate-pulse" : "bg-primary-container"
                }`}
              />
              {loading
                ? "Verificando..."
                : isConnected
                ? "HOJA VINCULADA"
                : "SIN HOJA ASIGNADA"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 truncate">
              {config?.google_sheet_id
                ? `ID: ${config.google_sheet_id}`
                : "Pega la URL de tu Google Sheet abajo"}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
              Modo de Autenticación Cloud
            </div>
            <div className="mt-2 text-lg font-mono font-bold text-white">
              {authType === "SERVICE_ACCOUNT" ? "Service Account" : "OAuth 2.0"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400">
              API Oficial Google Sheets v4 (TLS 1.3)
            </div>
          </div>

          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
              Última Corrida Manual
            </div>
            <div className="mt-2 text-lg font-mono font-bold text-secondary tabular-nums">
              {lastSync
                ? `${lastSync.rows_exported} órdenes / ${lastSync.journal_entries_exported} asientos`
                : "Lista para exportar"}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400">
              Operador aislado: {user.username}
            </div>
          </div>
        </section>

        {/* Configuración y Paso a Paso */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Formulario Principal */}
          <section className="lg:col-span-7 p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-4">
            <div className="border-b border-[#1e2430] pb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-tertiary">
                  link
                </span>
                Configuración de Hoja Contable del Operador
              </h2>
              <span className="text-[10px] font-mono text-slate-400">
                Multi-Tenant por Usuario
              </span>
            </div>

            {/* Correo Service Account Copiable */}
            <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-2">
              <div className="text-[11px] font-semibold text-white">
                Paso 1: Comparte tu hoja de Google Sheets como &ldquo;Editor&rdquo; con la cuenta de servicio:
              </div>
              <div className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430]">
                <code className="text-xs font-mono text-secondary truncate">
                  {config?.service_account_email ||
                    "Configura GOOGLE_SERVICE_ACCOUNT_JSON en el servidor para habilitar escritura Cloud"}
                </code>
                {config?.service_account_email && (
                  <button
                    type="button"
                    onClick={handleCopyServiceEmail}
                    className="px-2.5 py-1 rounded bg-secondary/15 text-secondary text-[11px] font-mono font-semibold hover:bg-secondary/25 shrink-0"
                  >
                    {copiedEmail ? "¡Copiado!" : "Copiar Correo"}
                  </button>
                )}
              </div>
            </div>

            <form onSubmit={handleSaveSheet} className="space-y-4">
              <div>
                <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                  Paso 2: URL Completa o Spreadsheet ID de Google Sheets
                </label>
                <input
                  type="text"
                  value={sheetInput}
                  onChange={(e) => setSheetInput(e.target.value)}
                  placeholder="https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-tertiary focus:outline-hidden text-xs font-mono text-white placeholder:text-slate-600"
                />
                <p className="text-[10px] text-slate-500 mt-1">
                  El sistema extrae automáticamente el identificador alfanumérico desde el enlace.
                </p>
              </div>

              <div className="flex items-center justify-between gap-3 flex-wrap pt-2">
                <div className="flex items-center gap-2">
                  <button
                    type="submit"
                    disabled={saving}
                    className="px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-50"
                  >
                    {saving ? "Guardando..." : "Guardar Vínculo"}
                  </button>

                  {isConnected && (
                    <button
                      type="button"
                      onClick={handleDisconnect}
                      disabled={saving}
                      className="px-3.5 py-2 rounded-lg bg-error/10 border border-error/30 text-error text-xs font-mono hover:bg-error/20"
                    >
                      Desvincular
                    </button>
                  )}
                </div>

                <span className="text-[11px] font-mono text-slate-500">
                  Cero credenciales expuestas en navegador
                </span>
              </div>
            </form>
          </section>

          {/* Estructura de Pestañas Sincronizadas */}
          <section className="lg:col-span-5 p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-3.5">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-primary">
                dataset
              </span>
              Estructura Contable Exportada
            </h2>
            <p className="text-xs text-slate-400">
              Cada sincronización actualiza de forma idempotente las pestañas financieras de tu libro:
            </p>

            <div className="space-y-2.5">
              {[
                {
                  tab: "1. Resumen_Fiscal",
                  desc: "KPIs mensuales en VES y USD BCV, utilidad neta FIFO y comisiones deducibles.",
                },
                {
                  tab: "2. Ordenes_P2P",
                  desc: "Historial cronológico de compras y ventas verificadas en Binance C2C con tasa BCV histórica.",
                },
                {
                  tab: "3. Libro_Diario_SENIAT",
                  desc: "Asientos contables en partida doble (Debe = Haber) con sello criptográfico SHA-256.",
                },
                {
                  tab: "4. Libro_Mayor",
                  desc: "Saldos iniciales, débitos, créditos y cierres consolidados por cuenta contable.",
                },
              ].map((item) => (
                <div
                  key={item.tab}
                  className="p-3 rounded-lg bg-surface-container border border-[#1e2430]"
                >
                  <div className="text-xs font-mono font-bold text-tertiary">
                    {item.tab}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{item.desc}</div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
