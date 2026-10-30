"use client";

import React, { useEffect, useState, useCallback } from "react";
import { 
  FileSpreadsheet, 
  Download, 
  RefreshCw, 
  Search, 
  Filter, 
  CheckCircle2, 
  Clock, 
  AlertCircle,
  FileText
} from "lucide-react";
import { 
  getOrders, 
  syncOrders, 
  getExportOrdersUrl, 
  OrderItem, 
  getCurrentUser,
  User 
} from "@/lib/api";

export default function OrdersPage() {
  const [orders, setOrders] = useState<OrderItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [tradeType, setTradeType] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncDays, setSyncDays] = useState<number>(30);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    setUser(getCurrentUser());
  }, []);

  const loadOrders = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await getOrders({
        page,
        page_size: 25,
        trade_type: tradeType || undefined,
        search: search || undefined,
      });
      setOrders(res.items);
      setTotal(res.total);
    } catch (err: any) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [page, tradeType, search]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  async function handleSync() {
    setIsSyncing(true);
    setSyncMessage(null);
    try {
      const res = await syncOrders(syncDays, tradeType || undefined);
      setSyncMessage(res.message);
      await loadOrders();
    } catch (err: any) {
      setSyncMessage(`Error: ${err.message}`);
    } finally {
      setIsSyncing(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Encabezado y Acciones de Exportación */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="font-mono text-xl font-bold text-slate-100 flex items-center space-x-2">
            <FileSpreadsheet className="h-6 w-6 text-emerald-400" />
            <span>HISTORIAL DE ÓRDENES BINANCE P2P</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            {total} órdenes registradas e ingestadas para reconciliación fiscal
          </p>
        </div>

        {/* Botones de Descarga Directa */}
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={getExportOrdersUrl("xlsx")}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-mono font-bold transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Descargar Excel (.xlsx)</span>
          </a>

          <a
            href={getExportOrdersUrl("csv_semicolon")}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-mono transition-colors"
          >
            <FileText className="h-3.5 w-3.5" />
            <span>CSV (;)</span>
          </a>

          <a
            href={getExportOrdersUrl("csv_comma")}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-mono transition-colors"
          >
            <FileText className="h-3.5 w-3.5" />
            <span>CSV (,)</span>
          </a>
        </div>
      </div>

      {/* Panel de Extracción Directa desde Binance API (TRADER / ADMIN) */}
      {(user?.role === "ADMIN" || user?.role === "TRADER") && (
        <div className="glass-panel p-4 rounded-xl border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-mono text-xs font-bold text-slate-200 uppercase flex items-center space-x-2">
              <RefreshCw className="h-3.5 w-3.5 text-emerald-400" />
              <span>Sincronizador Automático Binance P2P API</span>
            </h3>
            <span className="text-[10px] font-mono text-slate-400">
              GET /sapi/v1/c2c/orderMatch/listUserOrderHistory
            </span>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="flex items-center space-x-2 text-xs font-mono text-slate-300">
              <span>Ventana:</span>
              <input
                type="range"
                min="1"
                max="30"
                value={syncDays}
                onChange={(e) => setSyncDays(Number(e.target.value))}
                className="w-32 accent-emerald-500 cursor-pointer"
              />
              <span className="font-bold text-emerald-400">{syncDays} días</span>
            </div>

            <button
              onClick={handleSync}
              disabled={isSyncing}
              className="flex items-center space-x-2 px-4 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-800 text-slate-950 disabled:text-slate-500 font-mono text-xs font-bold transition-colors"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isSyncing ? "animate-spin" : ""}`} />
              <span>{isSyncing ? "Sincronizando con Binance..." : "Extraer Órdenes en Caliente"}</span>
            </button>
          </div>

          {syncMessage && (
            <p className="text-xs font-mono text-emerald-400 bg-emerald-500/10 p-2 rounded border border-emerald-500/20">
              {syncMessage}
            </p>
          )}
        </div>
      )}

      {/* Barra de Filtros y Búsqueda */}
      <div className="glass-panel p-3 rounded-xl border border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <div className="relative w-full sm:w-64">
            <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Buscar por orden o contraparte..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div className="flex items-center space-x-1">
            <Filter className="h-3.5 w-3.5 text-slate-400" />
            <select
              value={tradeType}
              onChange={(e) => {
                setTradeType(e.target.value);
                setPage(1);
              }}
              className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="">Todas</option>
              <option value="BUY">Solo Compras (BUY)</option>
              <option value="SELL">Solo Ventas (SELL)</option>
            </select>
          </div>
        </div>

        <span className="text-slate-400 text-[11px]">
          Página {page} de {Math.max(1, Math.ceil(total / 25))}
        </span>
      </div>

      {/* Tabla de Órdenes */}
      <div className="glass-panel rounded-xl border border-slate-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <thead>
              <tr className="bg-slate-900/60 border-b border-slate-800 text-slate-400">
                <th className="py-3 px-4 font-semibold">N° Orden</th>
                <th className="py-3 px-4 font-semibold">Tipo</th>
                <th className="py-3 px-4 font-semibold">Contraparte</th>
                <th className="py-3 px-4 font-semibold text-right">Cantidad Cripto</th>
                <th className="py-3 px-4 font-semibold text-right">Monto Fiat</th>
                <th className="py-3 px-4 font-semibold text-right">Precio Unitario</th>
                <th className="py-3 px-4 font-semibold text-right">Tasa BCV</th>
                <th className="py-3 px-4 font-semibold text-center">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/40">
              {orders.length > 0 ? (
                orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-900/30 transition-colors">
                    <td className="py-3 px-4 text-slate-200 font-medium">
                      {o.order_number}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${o.trade_type === "BUY" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30" : "bg-rose-500/10 text-rose-400 border border-rose-500/30"}`}>
                        {o.trade_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      {o.counterparty_name || "--"}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-200 font-bold">
                      {o.crypto_amount.toFixed(2)} {o.asset}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-300">
                      {o.fiat_amount.toLocaleString("es-VE", { minimumFractionDigits: 2 })} {o.fiat}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-300">
                      {o.unit_price.toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-400">
                      {o.bcv_rate ? o.bcv_rate.toFixed(2) : "--"}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300">
                        {o.order_status}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500 font-mono">
                    {isLoading ? "Cargando órdenes..." : "No se encontraron órdenes registradas."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Paginador */}
        {total > 25 && (
          <div className="p-3 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300"
            >
              Anterior
            </button>
            <span className="text-slate-400">Página {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * 25 >= total}
              className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300"
            >
              Siguiente
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
