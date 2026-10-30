"use client";

import React, { useState, useEffect } from "react";
import {
  KeyRound,
  ShieldCheck,
  RefreshCw,
  Activity,
  Clock,
  Gauge,
  AlertCircle,
  CheckCircle2,
  Lock,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import {
  getBinanceSettings,
  saveBinanceSettings,
  verifyBinanceConnection,
  BinanceStatusResponse,
  VerifyBinanceResponse,
} from "@/lib/api";

export default function BinanceSettingsCard() {
  const [status, setStatus] = useState<BinanceStatusResponse | null>(null);
  const [verifyResult, setVerifyResult] = useState<VerifyBinanceResponse | null>(null);

  // Formulario
  const [showForm, setShowForm] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [keyType, setKeyType] = useState<"HMAC" | "Ed25519">("HMAC");

  // Indicadores de carga y feedback
  const [isLoading, setIsLoading] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    setIsLoading(true);
    try {
      const data = await getBinanceSettings();
      setStatus(data);
    } catch {
      // Si no está autenticado o hay fallo de red
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSaveKeys(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    if (!apiKey.trim() || !secretKey.trim()) {
      setMessage({ text: "Debes ingresar tanto la API Key como el Secret/Clave Privada.", type: "error" });
      return;
    }

    setIsLoading(true);
    try {
      const updated = await saveBinanceSettings({
        api_key: apiKey.trim(),
        secret_key: secretKey.trim(),
        key_type: keyType,
      });
      setStatus(updated);
      setApiKey("");
      setSecretKey("");
      setShowForm(false);
      setMessage({
        text: "Credenciales de Binance cifradas con AES-256-GCM y almacenadas exitosamente.",
        type: "success",
      });
    } catch (err: any) {
      setMessage({
        text: err.message || "Error al almacenar las credenciales de Binance.",
        type: "error",
      });
    } finally {
      setIsLoading(false);
    }
  }

  async function handleVerifyLive() {
    setIsVerifying(true);
    setMessage(null);
    setVerifyResult(null);
    try {
      const result = await verifyBinanceConnection();
      setVerifyResult(result);
      if (result.success) {
        setMessage({ text: result.message, type: "success" });
      } else {
        setMessage({ text: result.message, type: "error" });
      }
    } catch (err: any) {
      setMessage({
        text: err.message || "Error al verificar conexión con Binance.",
        type: "error",
      });
    } finally {
      setIsVerifying(false);
    }
  }

  return (
    <div className="bg-[#111927] border border-slate-800 rounded-3xl p-5 sm:p-6 shadow-md space-y-5">
      {/* Cabecera del Módulo */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <KeyRound className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
              <span>Binance API Keys & Diagnóstico en Caliente</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-bold">
                AES-256-GCM
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Conexión oficial con Binance C2C con monitoreo de cuota y compensación de drift
            </p>
          </div>
        </div>

        {/* Acciones principales */}
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={handleVerifyLive}
            disabled={isVerifying || !status?.is_configured}
            className="px-3.5 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:bg-slate-800 disabled:text-slate-500 text-slate-950 text-xs font-bold font-mono transition-all flex items-center space-x-1.5 shadow-sm active:scale-95"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isVerifying ? "animate-spin" : ""}`} />
            <span>{isVerifying ? "Verificando..." : "Verificar en Vivo"}</span>
          </button>
          <button
            type="button"
            onClick={() => setShowForm(!showForm)}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold font-mono transition-all flex items-center space-x-1.5 border border-slate-700"
          >
            <Lock className="h-3.5 w-3.5 text-amber-400" />
            <span>{showForm ? "Ocultar" : "Modificar Claves"}</span>
            {showForm ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Alerta de Mensaje */}
      {message && (
        <div
          className={`p-3.5 rounded-2xl border text-xs font-mono flex items-start space-x-2.5 ${
            message.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
              : "bg-rose-500/10 border-rose-500/30 text-rose-300"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400 mt-0.5" />
          ) : (
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* Resumen de Estado de Credenciales */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
        {/* Tarjeta 1: Estado de Claves */}
        <div className="bg-[#162032] p-3.5 rounded-2xl border border-slate-700/80 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block">
            ESTADO DE LLAVES
          </span>
          <div className="flex items-center space-x-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                status?.is_configured ? "bg-emerald-400 animate-pulse" : "bg-rose-500"
              }`}
            />
            <span className="font-bold text-slate-200">
              {status?.is_configured ? "Cifradas en Reposo" : "No Configuradas"}
            </span>
          </div>
          <p className="text-[11px] text-slate-400 truncate">
            Key: <strong className="text-slate-200">{status?.api_key_masked || "Sin configurar"}</strong>
          </p>
        </div>

        {/* Tarjeta 2: Algoritmo y Permisos */}
        <div className="bg-[#162032] p-3.5 rounded-2xl border border-slate-700/80 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block">
            TIPO & PERMISOS
          </span>
          <div className="flex items-center space-x-1.5 text-slate-200 font-bold">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span>Firma {status?.key_type || "HMAC"}</span>
          </div>
          <p className="text-[11px] text-slate-400">
            Permisos: <strong className="text-emerald-400">Lectura + P2P Trading</strong>
          </p>
        </div>

        {/* Tarjeta 3: Telemetría en Caliente */}
        <div className="bg-[#162032] p-3.5 rounded-2xl border border-slate-700/80 space-y-1">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block">
            SALUD DE CONEXIÓN
          </span>
          <div className="flex items-center justify-between">
            <span className="text-slate-300">Latencia / Ping:</span>
            <span className="font-bold text-emerald-400">
              {verifyResult ? `${verifyResult.latency_ms} ms` : "Sin verificar"}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400">Peso API Consumido:</span>
            <span className={`font-bold ${verifyResult && verifyResult.used_weight > 4000 ? "text-rose-400" : "text-slate-200"}`}>
              {verifyResult ? `${verifyResult.used_weight} / 5000` : "0 / 5000"}
            </span>
          </div>
        </div>
      </div>

      {/* Cuadro de Telemetría Detallada tras Verificación en Vivo */}
      {verifyResult && (
        <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="font-bold text-slate-200 flex items-center space-x-1.5">
              <Activity className="h-4 w-4 text-emerald-400" />
              <span>Diagnóstico de Servidor Oficial Binance:</span>
            </span>
            <span
              className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                verifyResult.success
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                  : "bg-rose-500/20 text-rose-400 border border-rose-500/30"
              }`}
            >
              {verifyResult.success ? "EN LÍNEA (OPERATIVO)" : "DESCONECTADO"}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
            <div className="bg-[#111927] p-2.5 rounded-xl border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Ping Latencia</span>
              <span className="font-bold text-emerald-400 text-sm">{verifyResult.latency_ms} ms</span>
            </div>
            <div className="bg-[#111927] p-2.5 rounded-xl border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Deriva Horaria (Drift)</span>
              <span className={`font-bold text-sm ${Math.abs(verifyResult.clock_drift_ms) > 1000 ? "text-amber-400" : "text-emerald-400"}`}>
                {verifyResult.clock_drift_ms} ms
              </span>
            </div>
            <div className="bg-[#111927] p-2.5 rounded-xl border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Peso Consumido</span>
              <span className="font-bold text-slate-100 text-sm">{verifyResult.used_weight} / 5000</span>
            </div>
            <div className="bg-[#111927] p-2.5 rounded-xl border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Regla Fail-Closed</span>
              <span className="font-bold text-emerald-400 text-sm">PROTEGIDO</span>
            </div>
          </div>
        </div>
      )}

      {/* Formulario Expandible para Ingresar Nuevas Claves */}
      {showForm && (
        <form onSubmit={handleSaveKeys} className="p-4 bg-slate-950/90 border border-slate-800 rounded-2xl space-y-3.5 text-xs font-mono">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <span className="font-bold text-slate-200">Ingresar o Renovar Credenciales Binance</span>
            <span className="text-[10px] text-slate-500">Nunca se muestran en texto plano</span>
          </div>

          <div>
            <label className="block text-slate-300 mb-1 font-semibold">
              API KEY PÚBLICA (BINANCE)
            </label>
            <input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              required
              className="w-full bg-[#111927] border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-amber-400 transition-colors font-mono"
              placeholder="Pega tu API Key de 64 caracteres"
            />
          </div>

          <div>
            <label className="block text-slate-300 mb-1 font-semibold">
              SECRET KEY (HMAC) O CLAVE PRIVADA PEM (ED25519)
            </label>
            <input
              type="password"
              value={secretKey}
              onChange={(e) => setSecretKey(e.target.value)}
              required
              className="w-full bg-[#111927] border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-amber-400 transition-colors font-mono"
              placeholder="••••••••••••••••••••••••••••••••"
            />
          </div>

          <div>
            <label className="block text-slate-300 mb-1 font-semibold">
              TIPO DE ALGORITMO DE FIRMA
            </label>
            <div className="flex space-x-3 text-slate-300">
              <label className="flex items-center space-x-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="keyType"
                  value="HMAC"
                  checked={keyType === "HMAC"}
                  onChange={() => setKeyType("HMAC")}
                  className="accent-amber-400"
                />
                <span>HMAC-SHA256 (Estándar)</span>
              </label>
              <label className="flex items-center space-x-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="keyType"
                  value="Ed25519"
                  checked={keyType === "Ed25519"}
                  onChange={() => setKeyType("Ed25519")}
                  className="accent-amber-400"
                />
                <span>Ed25519 / RSA (Recomendado Binance)</span>
              </label>
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-2">
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 rounded-xl border border-slate-700 text-slate-400 hover:text-slate-200 font-mono text-xs"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:bg-slate-800 text-slate-950 font-bold font-mono text-xs transition-all shadow-md"
            >
              {isLoading ? "Cifrando..." : "Guardar Cifrado (AES-256)"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
