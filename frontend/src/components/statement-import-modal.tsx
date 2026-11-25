"use client";

import React, { useEffect, useState } from "react";
import {
  StatementAction,
  StatementCommitRowPayload,
  StatementCommitResponse,
  StatementPreviewResponse,
  StatementPreviewRow,
  commitBankStatement,
  previewBankStatement,
} from "@/lib/api";

type StatementFilterTab =
  | "ALL"
  | "UNMATCHED"
  | "MATCHED"
  | "FEES"
  | "MISMATCH"
  | "DUPLICATES";

interface EditableRow extends StatementPreviewRow {
  selectedAction: StatementAction;
  selectedOrder: string;
}

interface StatementImportModalProps {
  isOpen: boolean;
  preview: StatementPreviewResponse | null;
  sourceFile: File | null;
  onClose: () => void;
  onPreviewUpdated: (updated: StatementPreviewResponse) => void;
  onCommitted: (res: StatementCommitResponse) => void;
  onError: (msg: string) => void;
}

export function StatementImportModal({
  isOpen,
  preview,
  sourceFile,
  onClose,
  onPreviewUpdated,
  onCommitted,
  onError,
}: StatementImportModalProps) {
  const [bankName, setBankName] = useState<string>("");
  const [rows, setRows] = useState<EditableRow[]>([]);
  const [colMap, setColMap] = useState<Record<string, string>>({});
  const [reloadingMap, setReloadingMap] = useState<boolean>(false);
  const [committing, setCommitting] = useState<boolean>(false);
  const [filterTab, setFilterTab] = useState<StatementFilterTab>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const PAGE_SIZE = 50;

  useEffect(() => {
    if (!preview) return;
    setBankName(preview.bank_name || "");
    setRows(
      preview.rows.map((r) => ({
        ...r,
        selectedAction: r.suggested_action,
        selectedOrder: r.matched_order_number || "",
      }))
    );
    setColMap({});
    setFilterTab("ALL");
    setSearchQuery("");
    setPage(1);
  }, [preview]);

  if (!isOpen || !preview) return null;

  const activeRows = rows.filter(
    (r) => r.selectedAction !== "IGNORE" && r.selectedAction !== "DUPLICATE_EXISTING"
  );
  const matchedCount = rows.filter((r) => r.selectedAction === "P2P_MATCH").length;
  const unmatchedCount = rows.filter((r) => r.selectedAction === "P2P_UNMATCHED").length;
  const feesCount = rows.filter((r) => r.selectedAction === "BANK_FEE").length;
  const mismatchCount = rows.filter((r) => r.balance_ok === false).length;
  const ignoredOrDupCount = rows.length - activeRows.length;

  const qLower = searchQuery.trim().toLowerCase();
  const filteredRows = rows.filter((r) => {
    if (filterTab === "UNMATCHED" && r.selectedAction !== "P2P_UNMATCHED") return false;
    if (filterTab === "MATCHED" && r.selectedAction !== "P2P_MATCH") return false;
    if (filterTab === "FEES" && r.selectedAction !== "BANK_FEE") return false;
    if (filterTab === "MISMATCH" && r.balance_ok !== false) return false;
    if (
      filterTab === "DUPLICATES" &&
      r.selectedAction !== "DUPLICATE_EXISTING" &&
      r.selectedAction !== "IGNORE"
    ) {
      return false;
    }
    if (qLower) {
      const hay = `${r.date_vet} ${r.reference_number} ${r.concept} ${r.amount_ves.toFixed(2)}`.toLowerCase();
      if (!hay.includes(qLower)) return false;
    }
    return true;
  });

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * PAGE_SIZE;
  const visibleRows = filteredRows.slice(pageStart, pageStart + PAGE_SIZE);

  function updateRowAction(rowIndex: number, action: StatementAction) {
    setRows((prev) =>
      prev.map((r) =>
        r.row_index === rowIndex
          ? {
              ...r,
              selectedAction: action,
              selectedOrder: action === "P2P_MATCH" ? r.selectedOrder : "",
            }
          : r
      )
    );
  }

  function updateRowOrder(rowIndex: number, orderNum: string) {
    setRows((prev) =>
      prev.map((r) =>
        r.row_index === rowIndex
          ? {
              ...r,
              selectedOrder: orderNum,
              selectedAction: orderNum ? "P2P_MATCH" : r.selectedAction,
            }
          : r
      )
    );
  }

  function handleIgnoreAllUnmatched() {
    setRows((prev) =>
      prev.map((r) =>
        r.selectedAction === "P2P_UNMATCHED"
          ? { ...r, selectedAction: "IGNORE" }
          : r
      )
    );
  }

  async function handleApplyMapping(e: React.FormEvent) {
    e.preventDefault();
    if (!sourceFile) return;
    setReloadingMap(true);
    try {
      const updated = await previewBankStatement(sourceFile, {
        bank_name: bankName.trim() || undefined,
        column_mapping: colMap,
      });
      onPreviewUpdated(updated);
    } catch (err: any) {
      onError(err.message || "No se pudo aplicar el mapeo de columnas.");
    } finally {
      setReloadingMap(false);
    }
  }

  async function handleConfirmCommit() {
    if (!bankName.trim()) {
      onError("Indica el nombre del banco antes de confirmar.");
      return;
    }
    setCommitting(true);
    try {
      const payloadRows: StatementCommitRowPayload[] = rows.map((r) => ({
        row_index: r.row_index,
        date_vet: r.date_vet,
        reference_number: r.reference_number,
        concept: r.concept,
        movement_type: r.movement_type,
        amount_ves: r.amount_ves,
        payment_method: r.payment_method,
        action: r.selectedAction,
        order_number:
          r.selectedAction === "P2P_MATCH" && r.selectedOrder.trim()
            ? r.selectedOrder.trim()
            : null,
        bank_fee_ves: r.selectedAction === "BANK_FEE" ? r.amount_ves : r.bank_fee_ves,
      }));
      const res = await commitBankStatement({
        bank_name: bankName.trim(),
        rows: payloadRows,
      });
      onCommitted(res);
    } catch (err: any) {
      onError(err.message || "No se pudo guardar el estado de cuenta.");
    } finally {
      setCommitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Previsualización Universal de Estado de Cuenta"
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-3 sm:p-5 overscroll-contain"
    >
      <div className="w-full max-w-6xl rounded-2xl bg-surface-container-low border border-[#1e2430] shadow-2xl flex flex-col max-h-[92vh] overflow-hidden">
        {/* Cabecera */}
        <div className="px-5 py-4 border-b border-[#1e2430] flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[20px] text-secondary">
                account_balance
              </span>
              <h3 className="text-sm sm:text-base font-bold text-white">
                Estado de cuenta ({preview.file_type})
              </h3>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                  preview.balance_verified
                    ? "bg-tertiary/15 border-tertiary/30 text-tertiary"
                    : "bg-primary-container/15 border-primary-container/35 text-primary"
                }`}
              >
                {preview.balance_verified
                  ? "✓ Saldo verificado"
                  : preview.balance_mismatch_count > 0
                  ? `⚠ ${preview.balance_mismatch_count} fila(s) con diferencia`
                  : "Sin columna saldo verificable"}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5 font-mono tabular-nums">
              Método: {preview.extraction_method} • Orden: {preview.detected_order}
              {preview.opening_balance !== null && preview.opening_balance !== undefined
                ? ` • Saldo inicial: Bs. ${preview.opening_balance.toFixed(2)}`
                : ""}
              {preview.closing_balance !== null && preview.closing_balance !== undefined
                ? ` • Final: Bs. ${preview.closing_balance.toFixed(2)}`
                : ""}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <label htmlFor="stmt-bank-input" className="sr-only">
              Banco del estado de cuenta
            </label>
            <input
              id="stmt-bank-input"
              type="text"
              value={bankName}
              onChange={(e) => setBankName(e.target.value)}
              placeholder="Nombre del banco"
              className="px-3 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono text-white w-48"
            />
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-slate-400 hover:text-white cursor-pointer"
              aria-label="Cerrar previsualización"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>
        </div>

        {/* Alertas */}
        {preview.warnings.length > 0 && (
          <div className="px-5 py-2.5 bg-primary-container/10 border-b border-primary-container/25 text-xs text-amber-200 space-y-0.5">
            {preview.warnings.map((w, i) => (
              <div key={i}>• {w}</div>
            ))}
          </div>
        )}

        {/* Mapeador manual de columnas para CSV/Excel atípicos */}
        {preview.needs_column_mapping && preview.detected_columns.length > 0 && (
          <form
            onSubmit={handleApplyMapping}
            className="px-5 py-4 bg-surface-container border-b border-[#1e2430] space-y-3"
          >
            <div className="text-xs font-bold text-white">
              Asigna las columnas de tu archivo para este banco:
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
              {[
                { key: "date", label: "Fecha *" },
                { key: "concept", label: "Concepto" },
                { key: "reference", label: "Referencia" },
                { key: "debit", label: "Débito / Cargo" },
                { key: "credit", label: "Crédito / Abono" },
                { key: "amount", label: "Monto único" },
                { key: "balance", label: "Saldo" },
              ].map((field) => (
                <div key={field.key}>
                  <label className="block text-[10px] font-mono text-slate-400 mb-1">
                    {field.label}
                  </label>
                  <select
                    value={colMap[field.key] || ""}
                    onChange={(e) =>
                      setColMap((prev) => ({ ...prev, [field.key]: e.target.value }))
                    }
                    className="w-full px-2 py-1.5 rounded bg-surface-container-lowest border border-[#1e2430] text-[11px] text-white"
                  >
                    <option value="">(Omitir)</option>
                    {preview.detected_columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            <button
              type="submit"
              disabled={reloadingMap}
              className="px-3.5 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-bold cursor-pointer"
            >
              {reloadingMap ? "Aplicando..." : "Aplicar mapeo"}
            </button>
          </form>
        )}

        {/* Barra de Filtros, Búsqueda y Paginación para alto volumen */}
        {rows.length > 0 && (
          <div className="px-5 py-2.5 bg-surface-container/60 border-b border-[#1e2430] flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono">
            <div className="flex flex-wrap items-center gap-1.5">
              {(
                [
                  { id: "ALL", label: `Todos (${rows.length})` },
                  { id: "UNMATCHED", label: `Pendientes (${unmatchedCount})` },
                  { id: "MATCHED", label: `P2P (${matchedCount})` },
                  { id: "FEES", label: `Comisiones (${feesCount})` },
                  ...(mismatchCount > 0
                    ? [{ id: "MISMATCH" as StatementFilterTab, label: `Descuadres (${mismatchCount})` }]
                    : []),
                  { id: "DUPLICATES", label: `Excluidas (${ignoredOrDupCount})` },
                ] as Array<{ id: StatementFilterTab; label: string }>
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => {
                    setFilterTab(tab.id);
                    setPage(1);
                  }}
                  className={`px-2.5 py-1 rounded-md border transition-colors cursor-pointer ${
                    filterTab === tab.id
                      ? "bg-surface-container-high border-slate-500 text-white font-semibold"
                      : "bg-surface-container border-[#1e2430] text-slate-400 hover:text-white"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <input
                type="search"
                aria-label="Filtrar movimientos por referencia, concepto o monto"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                placeholder="Buscar ref, concepto o monto..."
                className="px-2.5 py-1 rounded-md bg-surface-container-lowest border border-[#1e2430] text-[11px] text-white w-52"
              />
              {totalPages > 1 && (
                <div className="flex items-center gap-1 text-slate-300 tabular-nums">
                  <button
                    type="button"
                    disabled={safePage <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="px-2 py-1 rounded bg-surface-container border border-[#1e2430] disabled:opacity-40 cursor-pointer"
                  >
                    ‹
                  </button>
                  <span className="px-1.5">
                    {safePage}/{totalPages}
                  </span>
                  <button
                    type="button"
                    disabled={safePage >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    className="px-2 py-1 rounded bg-surface-container border border-[#1e2430] disabled:opacity-40 cursor-pointer"
                  >
                    ›
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tabla de Movimientos (Paginada 50/pág para fluidez con 6,000–25,000 filas) */}
        <div className="flex-1 overflow-auto overscroll-x-contain p-4">
          {rows.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-400">
              No se extrajeron movimientos en este archivo. Revisa el formato o asigna las columnas arriba.
            </div>
          ) : visibleRows.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-400">
              Ningún movimiento coincide con el filtro actual.
            </div>
          ) : (
            <table className="w-full text-left border-collapse text-xs">
              <thead className="sticky top-0 z-10 bg-surface-container text-[10px] font-mono uppercase text-slate-400 border-b border-[#1e2430]">
                <tr>
                  <th scope="col" className="py-2 px-2.5">Fecha (VET)</th>
                  <th scope="col" className="py-2 px-2.5">Ref</th>
                  <th scope="col" className="py-2 px-2.5">Concepto</th>
                  <th scope="col" className="py-2 px-2.5">Tipo</th>
                  <th scope="col" className="py-2 px-2.5 text-right">Monto (Bs.)</th>
                  <th scope="col" className="py-2 px-2.5 text-right">Saldo (Bs.)</th>
                  <th scope="col" className="py-2 px-2.5">Clasificación</th>
                  <th scope="col" className="py-2 px-2.5">Orden Binance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2430]/70">
                {visibleRows.map((r) => (
                  <tr
                    key={r.row_index}
                    className={`${
                      r.selectedAction === "IGNORE" || r.selectedAction === "DUPLICATE_EXISTING"
                        ? "opacity-50"
                        : "hover:bg-surface-container/50"
                    }`}
                  >
                    <td className="py-2 px-2.5 font-mono text-slate-300 whitespace-nowrap">
                      {r.date_vet}
                    </td>
                    <td className="py-2 px-2.5 font-mono text-slate-400 whitespace-nowrap">
                      {r.reference_number}
                    </td>
                    <td className="py-2 px-2.5 text-slate-200 max-w-xs truncate" title={r.concept}>
                      {r.concept}
                    </td>
                    <td className="py-2 px-2.5 font-mono whitespace-nowrap">
                      <span
                        className={
                          r.movement_type === "CREDIT" ? "text-tertiary" : "text-primary"
                        }
                      >
                        {r.movement_type === "CREDIT" ? "INGRESO" : "EGRESO"}
                      </span>
                    </td>
                    <td className="py-2 px-2.5 font-mono font-semibold text-white text-right tabular-nums whitespace-nowrap">
                      {r.amount_ves.toFixed(2)}
                    </td>
                    <td className="py-2 px-2.5 font-mono text-right tabular-nums whitespace-nowrap">
                      {r.balance_ves !== null && r.balance_ves !== undefined ? (
                        <span
                          className={
                            r.balance_ok === false ? "text-error font-bold" : "text-slate-400"
                          }
                          title={
                            r.balance_ok === false
                              ? `Diferencia de saldo: Bs. ${r.balance_discrepancy.toFixed(2)}`
                              : "Cuadre verificado"
                          }
                        >
                          {r.balance_ves.toFixed(2)} {r.balance_ok === false ? "⚠" : ""}
                        </span>
                      ) : (
                        <span className="text-slate-600">-</span>
                      )}
                    </td>
                    <td className="py-2 px-2.5">
                      <select
                        aria-label={`Acción fila ${r.row_index}`}
                        value={r.selectedAction}
                        onChange={(e) =>
                          updateRowAction(r.row_index, e.target.value as StatementAction)
                        }
                        className="px-2 py-1 rounded bg-surface-container-lowest border border-[#1e2430] text-[11px] text-white font-mono"
                      >
                        <option value="P2P_MATCH">Orden P2P</option>
                        <option value="P2P_UNMATCHED">P2P sin orden</option>
                        <option value="BANK_FEE">Comisión bancaria</option>
                        <option value="INTERNAL_TRANSFER">Capital / traspaso propio</option>
                        <option value="DUPLICATE_EXISTING">Duplicado (omitir)</option>
                        <option value="IGNORE">Ignorar (gasto personal)</option>
                      </select>
                    </td>
                    <td className="py-2 px-2.5">
                      {r.selectedAction === "P2P_MATCH" ? (
                        <select
                          aria-label={`Orden P2P fila ${r.row_index}`}
                          value={r.selectedOrder}
                          onChange={(e) => updateRowOrder(r.row_index, e.target.value)}
                          className="px-2 py-1 rounded bg-surface-container-lowest border border-[#1e2430] text-[11px] font-mono text-secondary max-w-[190px]"
                        >
                          <option value="">-- Elegir orden --</option>
                          {preview.available_orders.map((ord) => (
                            <option key={ord.order_number} value={ord.order_number}>
                              {ord.order_number.slice(-8)} ({ord.trade_type} Bs.{ord.fiat_amount.toFixed(2)})
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span className="text-[10px] font-mono text-slate-500">
                          {r.notes || "-"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3.5 border-t border-[#1e2430] bg-surface-container flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono text-slate-300 tabular-nums">
            <span>A importar: <strong className="text-white">{activeRows.length}</strong></span>
            <span>P2P: <strong className="text-secondary">{matchedCount}</strong></span>
            <span>Comisiones: <strong className="text-tertiary">{feesCount}</strong></span>
            <span>Excluidas: <strong className="text-slate-400">{ignoredOrDupCount}</strong></span>
            {rows.some((r) => r.selectedAction === "P2P_UNMATCHED") && (
              <button
                type="button"
                onClick={handleIgnoreAllUnmatched}
                className="px-2.5 py-1 rounded bg-surface-container-high border border-[#1e2430] hover:border-primary-container/50 text-[10px] text-amber-300 cursor-pointer"
              >
                Excluir no conciliados
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-2 rounded-lg bg-surface-container-high text-xs text-slate-300 hover:text-white cursor-pointer"
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={committing || activeRows.length === 0}
              onClick={handleConfirmCommit}
              className="px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-45 cursor-pointer"
            >
              {committing ? "Guardando..." : `Importar ${activeRows.length} movimiento(s)`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
