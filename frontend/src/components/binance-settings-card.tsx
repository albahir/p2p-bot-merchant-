"use client";

import React, { useState, useEffect } from "react";
import {
  KeyRound,
  ShieldCheck,
  RefreshCw,
  Activity,
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

interface BinanceSettingsCardProps {
  onClose?: () => void;
  isModal?: boolean;
}

export default function BinanceSettingsCard({ onClose, isModal = false }: BinanceSettingsCardProps) {
  const [status, setStatus] = useState<BinanceStatusResponse | null>(null);
  const [verifyResult, setVerifyResult] = useState<VerifyBinanceResponse | null>(null);

  // Formulario de edición
  const [showForm, setShowForm] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [keyType, setKeyType] = useState<"HMAC" | "Ed25519">("HMAC");

  // Estados de carga y alertas
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
      // Ignorar si no está autenticado
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSaveKeys(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    if (!apiKey.trim() || !secretKey.trim()) {
      setMessage({
        text: "Ingresa tanto la API Key pública como la Secret/Privada.",
        type: "error",
      });
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
        text: "Credenciales de Binance cifradas con AES-256-GCM y almacenadas de forma segura.",
        type: "success",
      });
    } catch (err: any) {
      setMessage({
        text: err.message || "Error al cifrar credenciales de Binance.",
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
    <div className={`bg-white dark:bg-[#0D111A] border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm space-y-4 text-slate-800 dark:text-slate-100 ${isModal ? "w-full" : ""}`}>
      {/* Cabecera del Módulo */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800/80">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
            <KeyRound className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Credenciales Oficiales Binance API
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/80 font-medium">
                AES-256-GCM
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Conexión directa C2C con firma criptográfica y monitor de API Weight
            </p>
          </div>
        </div>

        {/* Acciones principales */}
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={handleVerifyLive}
            disabled={isVerifying || !status?.is_configured}
            className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-white text-white dark:text-slate-900 text-xs font-medium transition-colors flex items-center space-x-1.5 disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isVerifying ? "animate-spin" : ""}`} />
            <span>{isVerifying ? "Verificando..." : "Probar Conexión"}</span>
          </button>
          <button
            type="button"
            onClick={() => setShowForm(!showForm)}
            className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-medium transition-colors flex items-center space-x-1"
          >
            <Lock className="h-3 w-3 text-slate-500" />
            <span>{showForm ? "Cerrar" : "Modificar"}</span>
            {showForm ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs font-medium"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Mensajes de notificación */}
      {message && (
        <div
          className={`p-3 rounded-lg border text-xs flex items-start space-x-2 ${
            message.type === "success"
              ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900 text-emerald-800 dark:text-emerald-300"
              : "bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
          ) : (
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400 mt-0.5" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* Resumen de Estado en Fila Horizontal Adaptativa */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
        {/* Tarjeta 1: Estado de Claves */}
        <div className="bg-slate-50 dark:bg-[#121722] p-3 rounded-lg border border-slate-200 dark:border-slate-800/80 space-y-1">
          <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold tracking-wider block">
            Estado de Llaves
          </span>
          <div className="flex items-center space-x-2">
            <span
              className={`h-2 w-2 rounded-full ${
                status?.is_configured ? "bg-emerald-500" : "bg-rose-500"
              }`}
            />
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              {status?.is_configured ? "Cifradas en Reposo" : "No Configuradas"}
            </span>
          </div>
          <p className="text-[11px] text-slate-600 dark:text-slate-400 font-mono truncate">
            {status?.api_key_masked || "Sin configurar"}
          </p>
        </div>

        {/* Tarjeta 2: Tipo de Llave */}
        <div className="bg-slate-50 dark:bg-[#121722] p-3 rounded-lg border border-slate-200 dark:border-slate-800/80 space-y-1">
          <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold tracking-wider block">
            Algoritmo & Permisos
          </span>
          <div className="flex items-center space-x-1.5 font-semibold text-slate-900 dark:text-slate-100">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
            <span>Firma {status?.key_type || "HMAC-SHA256"}</span>
          </div>
          <p className="text-[11px] text-slate-600 dark:text-slate-400">
            Permisos: <span className="font-medium text-emerald-700 dark:text-emerald-400">Lectura + P2P</span>
          </p>
        </div>

        {/* Tarjeta 3: Telemetría de Red */}
        <div className="bg-slate-50 dark:bg-[#121722] p-3 rounded-lg border border-slate-200 dark:border-slate-800/80 space-y-1">
          <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold tracking-wider block">
            Salud de Conexión
          </span>
          <div className="flex items-center justify-between">
            <span className="text-slate-600 dark:text-slate-400">Latencia Ping:</span>
            <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">
              {verifyResult ? `${verifyResult.latency_ms} ms` : "Sin prueba"}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-500 dark:text-slate-400">Cuota API:</span>
            <span className="font-mono font-medium text-slate-700 dark:text-slate-300">
              {verifyResult ? `${verifyResult.used_weight} / 5000` : "0 / 5000"}
            </span>
          </div>
        </div>
      </div>

      {/* Diagnóstico en Vivo Expandido tras pulsar 'Probar Conexión' */}
      {verifyResult && (
        <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-[#121722] border border-slate-200 dark:border-slate-800 space-y-2.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-900 dark:text-slate-100 flex items-center space-x-1.5">
              <Activity className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
              <span>Respuesta Oficial Servidor Binance:</span>
            </span>
            <span
              className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                verifyResult.success
                  ? "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                  : "bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800"
              }`}
            >
              {verifyResult.success ? "Conexión Activa" : "Desconectado"}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
            <div className="p-2 rounded bg-white dark:bg-[#0D111A] border border-slate-200 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 text-[10px] block">Latencia Red</span>
              <span className="font-bold text-slate-900 dark:text-slate-100">{verifyResult.latency_ms} ms</span>
            </div>
            <div className="p-2 rounded bg-white dark:bg-[#0D111A] border border-slate-200 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 text-[10px] block">Desfase Reloj</span>
              <span className={`font-bold ${Math.abs(verifyResult.clock_drift_ms) > 1000 ? "text-amber-600 dark:text-amber-400" : "text-slate-900 dark:text-slate-100"}`}>
                {verifyResult.clock_drift_ms} ms
              </span>
            </div>
            <div className="p-2 rounded bg-white dark:bg-[#0D111A] border border-slate-200 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 text-[10px] block">Peso Consumido</span>
              <span className="font-bold text-slate-900 dark:text-slate-100">{verifyResult.used_weight} / 5000</span>
            </div>
            <div className="p-2 rounded bg-white dark:bg-[#0D111A] border border-slate-200 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 text-[10px] block">Protocolo</span>
              <span className="font-bold text-emerald-700 dark:text-emerald-400">FAIL-CLOSED</span>
            </div>
          </div>
        </div>
      )}

      {/* Formulario Desplegable para Guardar Nuevas Claves */}
      {showForm && (
        <form onSubmit={handleSaveKeys} className="p-4 bg-slate-50 dark:bg-[#121722] border border-slate-200 dark:border-slate-800 rounded-lg space-y-3 text-xs">
          <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-700">
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              Actualizar Llaves API de Binance
            </span>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              Cifrado AES-256 en reposo
            </span>
          </div>

          <div>
            <label className="block text-slate-700 dark:text-slate-300 mb-1 font-medium">
              API KEY PÚBLICA
            </label>
            <input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              required
              className="w-full bg-white dark:bg-[#0D111A] border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-slate-100 focus:outline-none focus:border-slate-600 dark:focus:border-slate-400 font-mono text-xs"
              placeholder="Pega la API Key pública de Binance"
            />
          </div>

          <div>
            <label className="block text-slate-700 dark:text-slate-300 mb-1 font-medium">
              SECRET KEY (HMAC) O CLAVE PRIVADA PEM (ED25519)
            </label>
            <input
              type="password"
              value={secretKey}
              onChange={(e) => setSecretKey(e.target.value)}
              required
              className="w-full bg-white dark:bg-[#0D111A] border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-slate-100 focus:outline-none focus:border-slate-600 dark:focus:border-slate-400 font-mono text-xs"
              placeholder="••••••••••••••••••••••••••••••••"
            />
          </div>

          <div>
            <label className="block text-slate-700 dark:text-slate-300 mb-1 font-medium">
              TIPO DE FIRMA
            </label>
            <div className="flex space-x-4 text-slate-700 dark:text-slate-300">
              <label className="flex items-center space-x-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="keyType"
                  value="HMAC"
                  checked={keyType === "HMAC"}
                  onChange={() => setKeyType("HMAC")}
                  className="accent-slate-900 dark:accent-slate-100"
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
                  className="accent-slate-900 dark:accent-slate-100"
                />
                <span>Ed25519 / RSA (Recomendado)</span>
              </label>
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-2">
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-3.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-medium"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs shadow-sm transition-colors"
            >
              {isLoading ? "Guardando..." : "Guardar Cifrado"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
