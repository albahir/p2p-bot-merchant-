"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import {
  GoogleSheetsConfigResponse,
  GoogleSheetsSyncResponse,
  User,
  completeGoogleOAuth,
  disconnectGoogleOAuth,
  getCachedSheetsSettings,
  getCurrentUser,
  getSheetsSettings,
  saveGoogleOAuthClientConfig,
  saveSheetsSettings,
  startGoogleOAuth,
  syncSheetsNow,
} from "@/lib/api";

export default function SheetsSyncPage() {
  const initialUser = typeof window !== "undefined" ? getCurrentUser() : null;
  const initialConfig = typeof window !== "undefined" ? getCachedSheetsSettings() : null;

  const [user, setUser] = useState<User | null>(initialUser);
  const [config, setConfig] = useState<GoogleSheetsConfigResponse | null>(initialConfig);
  const [sheetInput, setSheetInput] = useState<string>(initialConfig?.google_sheet_id || initialUser?.google_sheet_id || "");
  const [authMode, setAuthMode] = useState<"OAUTH2" | "SERVICE_ACCOUNT">(
    initialConfig?.google_auth_type === "SERVICE_ACCOUNT" ? "SERVICE_ACCOUNT" : "OAUTH2"
  );
  const [lastSync, setLastSync] = useState<GoogleSheetsSyncResponse | null>(null);

  const [showApiForm, setShowApiForm] = useState<boolean>(false);
  const [oauthClientId, setOauthClientId] = useState<string>("");
  const [oauthClientSecret, setOauthClientSecret] = useState<string>("");

  const [loading, setLoading] = useState<boolean>(!initialConfig);
  const [saving, setSaving] = useState<boolean>(false);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [connectingGoogle, setConnectingGoogle] = useState<boolean>(false);
  const [copiedEmail, setCopiedEmail] = useState<boolean>(false);
  const oauthHandledRef = useRef<boolean>(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const loadConfig = useCallback(async (fresh = false) => {
    const current = getCurrentUser();
    setUser(current);
    if (!current || current.role === "INVITADO") {
      setLoading(false);
      return;
    }

    const cached = fresh ? null : getCachedSheetsSettings();
    if (cached) {
      setConfig((prev) => prev || cached);
      setSheetInput((prev) => prev || cached.google_sheet_id || "");
      setLoading(false);
    } else {
      setLoading(true);
    }
    try {
      const res = await getSheetsSettings(fresh);
      setConfig(res);
      setSheetInput(res.google_sheet_id || "");
      if (res.google_auth_type === "SERVICE_ACCOUNT" && !res.oauth_connected && res.service_account_email && !res.oauth_available) {
        setAuthMode("SERVICE_ACCOUNT");
      } else if (res.google_auth_type === "SERVICE_ACCOUNT" || res.google_auth_type === "OAUTH2") {
        setAuthMode(res.google_auth_type);
      }
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo cargar la configuración.",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
    const code = params?.get("code");
    const state = params?.get("state");
    const oauthErr = params?.get("error");

    if (oauthErr) {
      window.history.replaceState({}, "", "/sheets");
      setFeedback({ type: "error", text: "Autorización con Google cancelada." });
      loadConfig(true);
      return;
    }

    if (code && state) {
      if (oauthHandledRef.current) return;
      oauthHandledRef.current = true;
      const redirectUri = `${window.location.origin}/sheets`;
      window.history.replaceState({}, "", "/sheets");
      setConnectingGoogle(true);
      completeGoogleOAuth({ code, state, redirect_uri: redirectUri })
        .then((res) => {
          setConfig(res);
          setSheetInput(res.google_sheet_id || "");
          setAuthMode("OAUTH2");
          setLoading(false);
          setFeedback({ type: "success", text: res.message || "Cuenta de Google conectada." });
        })
        .catch((err: any) => {
          setFeedback({ type: "error", text: err.message || "No se pudo completar la conexión con Google." });
          loadConfig(true);
        })
        .finally(() => {
          setConnectingGoogle(false);
        });
      return;
    }

    loadConfig(false);
  }, [loadConfig]);

  async function handleConnectGoogle() {
    setFeedback(null);
    setConnectingGoogle(true);
    try {
      const redirectUri = typeof window !== "undefined" ? `${window.location.origin}/sheets` : undefined;
      const { authorization_url } = await startGoogleOAuth(redirectUri);
      window.location.href = authorization_url;
    } catch (err: any) {
      setConnectingGoogle(false);
      setShowApiForm(true);
      setFeedback({
        type: "error",
        text: err.message || "Configura tu Client ID y Client Secret de Google API.",
      });
    }
  }

  async function handleSaveOAuthCreds(e: React.FormEvent) {
    e.preventDefault();
    if (!oauthClientId.trim() || !oauthClientSecret.trim()) return;
    setFeedback(null);
    setSaving(true);
    try {
      const redirectUri = typeof window !== "undefined" ? `${window.location.origin}/sheets` : undefined;
      const res = await saveGoogleOAuthClientConfig({
        client_id: oauthClientId.trim(),
        client_secret: oauthClientSecret.trim(),
        redirect_uri: redirectUri,
      });
      setConfig(res);
      setOauthClientId("");
      setOauthClientSecret("");
      setShowApiForm(false);
      setFeedback({ type: "success", text: res.message || "Credenciales guardadas." });
    } catch (err: any) {
      setFeedback({ type: "error", text: err.message || "No se pudieron guardar las credenciales." });
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnectOAuth() {
    setFeedback(null);
    setSaving(true);
    try {
      const res = await disconnectGoogleOAuth();
      setConfig(res);
      setFeedback({ type: "success", text: res.message || "Cuenta desconectada." });
    } catch (err: any) {
      setFeedback({ type: "error", text: err.message || "Error al desconectar cuenta." });
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveSheet(e: React.FormEvent) {
    e.preventDefault();
    setFeedback(null);
    setSaving(true);
    try {
      const res = await saveSheetsSettings({
        google_sheet_id: sheetInput.trim() || null,
        google_auth_type: authMode,
      });
      setConfig(res);
      setSheetInput(res.google_sheet_id || "");
      setFeedback({ type: "success", text: res.message || "Hoja guardada." });
    } catch (err: any) {
      setFeedback({ type: "error", text: err.message || "No se pudo guardar el enlace." });
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnectSheet() {
    setFeedback(null);
    setSaving(true);
    try {
      const res = await saveSheetsSettings({
        google_sheet_id: null,
        google_auth_type: authMode,
      });
      setConfig(res);
      setSheetInput("");
      setLastSync(null);
      setFeedback({ type: "success", text: "Hoja desvinculada." });
    } catch (err: any) {
      setFeedback({ type: "error", text: err.message || "Error al desvincular la hoja." });
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
        type: res.success ? "success" : "error",
        text: res.message,
      });
      await loadConfig();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo sincronizar con Google Sheets.",
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
      <AppShell title="Google Sheets" subtitle="Sincroniza tu contabilidad en la nube.">
        <div className="max-w-md mx-auto my-12 p-6 rounded-2xl bg-surface-container-low border border-[#1e2430] text-center space-y-4">
          <span className="material-symbols-outlined text-[36px] text-tertiary">table_chart</span>
          <h2 className="text-base font-bold text-white">Inicia sesión para continuar</h2>
          <p className="text-xs text-slate-400">
            Disponible para cuentas de comerciante o administrador.
          </p>
          <Link
            href="/login"
            className="inline-block px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold"
          >
            Iniciar sesión
          </Link>
        </div>
      </AppShell>
    );
  }

  const hasSheet = Boolean(config?.google_sheet_id);
  const oauthConnected = Boolean(config?.oauth_connected);
  const canSync = hasSheet || oauthConnected;
  const redirectHint =
    typeof window !== "undefined" ? `${window.location.origin}/sheets` : "http://localhost:3000/sheets";

  return (
    <AppShell
      title="Google Sheets"
      badge={canSync ? "CONECTADO" : "SIN CONECTAR"}
      subtitle="Sincroniza órdenes y contabilidad con tu hoja de cálculo."
      actions={
        <div className="flex items-center gap-2">
          {config?.google_sheet_url && (
            <a
              href={config.google_sheet_url}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-tertiary/50 text-xs font-mono text-slate-200 flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-[15px] text-tertiary">open_in_new</span>
              <span>Abrir hoja</span>
            </a>
          )}
          <button
            type="button"
            onClick={handleSyncNow}
            disabled={!canSync || syncing || connectingGoogle}
            className="px-3.5 py-1.5 rounded-lg bg-tertiary text-on-tertiary text-xs font-bold hover:brightness-110 disabled:opacity-40 flex items-center gap-1.5 cursor-pointer"
          >
            <span className={`material-symbols-outlined text-[16px] ${syncing ? "animate-spin" : ""}`}>
              sync
            </span>
            <span>{syncing ? "Sincronizando..." : "Sincronizar"}</span>
          </button>
        </div>
      }
    >
      <div className="space-y-5">
        {feedback && (
          <div
            role="alert"
            aria-live="polite"
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
              aria-label="Cerrar notificación"
              className="text-slate-400 hover:text-white"
            >
              ✕
            </button>
          </div>
        )}

        {/* Resumen compacto (2 por fila en móvil) */}
        <section className="grid grid-cols-2 md:grid-cols-3 gap-2.5 sm:gap-3.5">
          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 truncate">
              Hoja vinculada
            </div>
            <div
              className={`mt-1.5 text-sm sm:text-base font-mono font-bold flex items-center gap-2 truncate ${
                hasSheet ? "text-tertiary" : "text-primary"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full shrink-0 ${
                  hasSheet ? "bg-tertiary animate-pulse" : "bg-primary-container"
                }`}
              />
              <span className="truncate">{loading ? "Cargando..." : hasSheet ? "Lista" : "Pendiente"}</span>
            </div>
            <div className="mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 truncate">
              {config?.google_sheet_id || "Se creará al conectar con Google"}
            </div>
          </div>

          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 truncate">
              Método de acceso
            </div>
            <div className="mt-1.5 text-sm sm:text-base font-mono font-bold text-white truncate">
              {oauthConnected ? "Cuenta Google" : "Cuenta de servicio"}
            </div>
            <div className="mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 truncate">
              {config?.google_account_email ||
                (oauthConnected ? "Sesión activa" : config?.service_account_email || "Sin configurar")}
            </div>
          </div>

          <div className="col-span-2 md:col-span-1 p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 truncate">
              Última sincronización
            </div>
            <div className="mt-1.5 text-sm sm:text-base font-mono font-bold text-secondary tabular-nums truncate">
              {lastSync
                ? `${lastSync.rows_exported} órds / ${lastSync.journal_entries_exported} asientos`
                : "Sin ejecutar"}
            </div>
            <div className="mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 truncate">
              4 pestañas automáticas
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Conexión Google */}
          <section className="lg:col-span-7 p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-5">
            <div className="flex items-center justify-between gap-2 flex-wrap border-b border-[#1e2430] pb-3">
              <h2 className="text-sm font-bold text-white">Conexión directa</h2>
              <div className="inline-flex rounded-lg bg-surface-container p-0.5 border border-[#1e2430] text-[11px] font-mono">
                <button
                  type="button"
                  onClick={() => setAuthMode("OAUTH2")}
                  className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${
                    authMode === "OAUTH2"
                      ? "bg-primary-container text-on-primary font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Cuenta de Google
                </button>
                <button
                  type="button"
                  onClick={() => setAuthMode("SERVICE_ACCOUNT")}
                  className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${
                    authMode === "SERVICE_ACCOUNT"
                      ? "bg-primary-container text-on-primary font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Cuenta de servicio
                </button>
              </div>
            </div>

            {authMode === "OAUTH2" ? (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-surface-container border border-[#1e2430] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold text-white">
                      {oauthConnected
                        ? `Conectado${config?.google_account_email ? `: ${config.google_account_email}` : ""}`
                        : "Accede con tu cuenta de Google"}
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      {oauthConnected
                        ? "Autorización activa para crear y actualizar tu hoja."
                        : "Autoriza acceso a Google Sheets sin compartir correos manualmente."}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {oauthConnected ? (
                      <button
                        type="button"
                        onClick={handleDisconnectOAuth}
                        disabled={saving}
                        className="px-3 py-1.5 rounded-lg bg-error/10 border border-error/30 text-error text-xs font-mono hover:bg-error/20 cursor-pointer"
                      >
                        Desconectar
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={handleConnectGoogle}
                        disabled={connectingGoogle}
                        className="px-3.5 py-2 rounded-lg bg-white text-slate-900 text-xs font-bold hover:bg-slate-200 disabled:opacity-50 flex items-center gap-2 cursor-pointer"
                      >
                        <span className="material-symbols-outlined text-[16px]">login</span>
                        <span>{connectingGoogle ? "Conectando..." : "Conectar con Google"}</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Aviso de Uso Limitado de APIs de Google */}
                <p className="text-[11px] leading-relaxed text-slate-400">
                  Solo creamos o actualizamos la hoja de Google Sheets que indiques aquí. El uso de
                  datos de Google cumple con la{" "}
                  <Link href="/privacy" className="text-primary hover:underline">
                    Política de Privacidad y Uso Limitado (Limited Use)
                  </Link>
                  ; nunca compartimos datos de Google con terceros ni modelos de IA.
                </p>

                {/* Configuración opcional de API OAuth desde la UI */}
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-400 font-mono">
                    {config?.oauth_available ? "API Google lista" : "Falta configurar API de Google Cloud"}
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowApiForm((prev) => !prev)}
                    className="text-primary hover:underline font-mono cursor-pointer"
                  >
                    {showApiForm ? "Ocultar credenciales API" : "Configurar credenciales Google API"}
                  </button>
                </div>

                {showApiForm && (
                  <form
                    onSubmit={handleSaveOAuthCreds}
                    className="p-4 rounded-xl bg-surface-container border border-[#1e2430] space-y-3"
                  >
                    <p className="text-[11px] text-slate-400">
                      Autoriza en Google Cloud esta URL de redirección:{" "}
                      <code className="text-secondary font-mono">{redirectHint}</code>
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label
                          htmlFor="google-oauth-client-id"
                          className="block text-[10px] font-mono uppercase text-slate-400 mb-1"
                        >
                          Client ID
                        </label>
                        <input
                          id="google-oauth-client-id"
                          type="text"
                          required
                          autoComplete="off"
                          value={oauthClientId}
                          onChange={(e) => setOauthClientId(e.target.value)}
                          placeholder="xxx.apps.googleusercontent.com"
                          className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono text-white"
                        />
                      </div>
                      <div>
                        <label
                          htmlFor="google-oauth-client-secret"
                          className="block text-[10px] font-mono uppercase text-slate-400 mb-1"
                        >
                          Client Secret
                        </label>
                        <input
                          id="google-oauth-client-secret"
                          type="password"
                          required
                          autoComplete="off"
                          value={oauthClientSecret}
                          onChange={(e) => setOauthClientSecret(e.target.value)}
                          placeholder="GOCSPX-..."
                          className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono text-white"
                        />
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <button
                        type="submit"
                        disabled={saving}
                        className="px-3.5 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-50 cursor-pointer"
                      >
                        {saving ? "Guardando..." : "Guardar API Google"}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            ) : (
              <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-2">
                <div className="text-[11px] font-semibold text-white">
                  Comparte tu hoja como Editor con este correo:
                </div>
                <div className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-surface-container-lowest border border-[#1e2430]">
                  <code className="text-xs font-mono text-secondary truncate">
                    {config?.service_account_email || "Sin cuenta de servicio en servidor"}
                  </code>
                  {config?.service_account_email && (
                    <button
                      type="button"
                      onClick={handleCopyServiceEmail}
                      className="px-2.5 py-1 rounded bg-secondary/15 text-secondary text-[11px] font-mono font-semibold hover:bg-secondary/25 shrink-0 cursor-pointer"
                    >
                      {copiedEmail ? "Copiado" : "Copiar"}
                    </button>
                  )}
                </div>
              </div>
            )}

            <form onSubmit={handleSaveSheet} className="space-y-3 pt-2 border-t border-[#1e2430]">
              <div>
                <label
                  htmlFor="google-sheet-url"
                  className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
                >
                  Enlace o ID de hoja (opcional si usas Cuenta Google)
                </label>
                <input
                  id="google-sheet-url"
                  type="text"
                  autoComplete="url"
                  enterKeyHint="done"
                  value={sheetInput}
                  onChange={(e) => setSheetInput(e.target.value)}
                  placeholder="https://docs.google.com/spreadsheets/d/..."
                  className="w-full px-3.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-tertiary focus:outline-hidden text-xs font-mono text-white placeholder:text-slate-600"
                />
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-50 cursor-pointer"
                >
                  {saving ? "Guardando..." : "Guardar"}
                </button>

                {hasSheet && (
                  <button
                    type="button"
                    onClick={handleDisconnectSheet}
                    disabled={saving}
                    className="px-3.5 py-2 rounded-lg bg-error/10 border border-error/30 text-error text-xs font-mono hover:bg-error/20 cursor-pointer"
                  >
                    Quitar hoja
                  </button>
                )}
              </div>
            </form>
          </section>

          {/* Pestañas exportadas */}
          <section className="lg:col-span-5 p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-3">
            <h2 className="text-sm font-bold text-white">Pestañas sincronizadas</h2>
            <div className="space-y-2">
              {[
                { tab: "Detalle Fiscal", desc: "Órdenes cerradas, comisiones y ganancia neta." },
                { tab: "Resumen Ejecutivo", desc: "Totales y margen consolidado." },
                { tab: "Libro Diario", desc: "Asientos en partida doble (Debe y Haber)." },
                { tab: "Libro Mayor", desc: "Saldos consolidados por cuenta." },
              ].map((item) => (
                <div
                  key={item.tab}
                  className="p-3 rounded-lg bg-surface-container border border-[#1e2430]"
                >
                  <div className="text-xs font-mono font-bold text-tertiary">{item.tab}</div>
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
