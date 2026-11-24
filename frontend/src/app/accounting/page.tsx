"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { BankAmountInput } from "@/components/bank-amount-input";
import { StatementImportModal } from "@/components/statement-import-modal";
import {
  AccountingPeriodConfig,
  FiscalSummary,
  JournalEntryItem,
  LedgerSummaryItem,
  StatementCommitResponse,
  StatementPreviewResponse,
  UploadVoucherResponse,
  User,
  VENEZUELAN_BANK_CATALOG,
  bankMatchesProfile,
  canonicalBankName,
  closeFiscalPeriod,
  createManualVoucher,
  downloadAccountingExcel,
  downloadAccountingPdf,
  getAccountingPeriodConfig,
  getCachedApiResponse,
  getCachedUserBanks,
  getCurrentUser,
  getFiscalSnapshot,
  getFiscalSummary,
  getJournalEntries,
  getLedgerSummaries,
  getLiveBalance,
  getUserBanksSettings,
  matchVoucherWithOrder,
  previewBankStatement,
  reconcileOrphanVouchers,
  saveAccountingPeriodConfig,
  saveUserBanksSettings,
  syncOrders,
  uploadVoucherFile,
} from "@/lib/api";

type AccountingTab = "JOURNAL" | "LEDGER" | "FISCAL_6";

interface BankBreakdownItem {
  bank_name: string;
  initial_ves: number;
  inflows_ves: number;
  outflows_ves: number;
  theoretical_ves: number;
}

interface LiveBalanceState {
  year: number;
  month: number;
  initial_usdt: number;
  inflow_usdt: number;
  outflow_usdt: number;
  theoretical_usdt: number;
  total_initial_ves: number;
  total_inflows_ves: number;
  total_outflows_ves: number;
  total_theoretical_ves: number;
  bank_breakdown: BankBreakdownItem[];
}

const MONTHS = [
  { value: 1, label: "Enero" },
  { value: 2, label: "Febrero" },
  { value: 3, label: "Marzo" },
  { value: 4, label: "Abril" },
  { value: 5, label: "Mayo" },
  { value: 6, label: "Junio" },
  { value: 7, label: "Julio" },
  { value: 8, label: "Agosto" },
  { value: 9, label: "Septiembre" },
  { value: 10, label: "Octubre" },
  { value: 11, label: "Noviembre" },
  { value: 12, label: "Diciembre" },
];

export default function AccountingPage() {
  const voucherInputRef = useRef<HTMLInputElement>(null);
  const statementInputRef = useRef<HTMLInputElement>(null);
  const now = new Date();
  const initY = now.getFullYear();
  const initM = now.getMonth() + 1;

  const initialUser = typeof window !== "undefined" ? getCurrentUser() : null;
  const cachedUserBanks = typeof window !== "undefined" ? getCachedUserBanks() : null;
  const defaultBanksList =
    cachedUserBanks && cachedUserBanks.preferred_banks.length > 0
      ? cachedUserBanks.preferred_banks
      : ["Banco de Venezuela", "Mercantil"];
  const defaultBankBalances: Record<string, number> = (() => {
    const map: Record<string, number> = {};
    for (const b of defaultBanksList) {
      map[b] = Number(cachedUserBanks?.bank_initial_balances?.[b] ?? 0);
    }
    return map;
  })();

  const initialBalance =
    typeof window !== "undefined"
      ? getCachedApiResponse<LiveBalanceState>(
          `/api/accounting/balances/live?year=${initY}&month=${initM}&initial_usdt=0&initial_ves=0`
        )
      : null;
  const initialJournal =
    typeof window !== "undefined"
      ? getCachedApiResponse<JournalEntryItem[]>("/api/accounting/journal?")
      : null;

  const [user, setUser] = useState<User | null>(null);
  const [year, setYear] = useState<number>(initY);
  const [month, setMonth] = useState<number>(initM);
  const [userBanks, setUserBanks] = useState<string[]>(defaultBanksList);
  const [bankInitialMap, setBankInitialMap] = useState<Record<string, number>>(defaultBankBalances);
  const [committedBankMap, setCommittedBankMap] = useState<Record<string, number>>(defaultBankBalances);
  const [showBankSelector, setShowBankSelector] = useState<boolean>(false);
  const [initialUsdt, setInitialUsdt] = useState<number>(0);
  const [committedUsdt, setCommittedUsdt] = useState<number>(0);
  const [initialUsdtCostVes, setInitialUsdtCostVes] = useState<number>(0);
  const [periodConfig, setPeriodConfig] = useState<AccountingPeriodConfig | null>(null);
  const [syncingPeriodOrders, setSyncingPeriodOrders] = useState<boolean>(false);
  const [closeActualUsdt, setCloseActualUsdt] = useState<number>(0);
  const [closeActualBanks, setCloseActualBanks] = useState<Record<string, number>>({});
  const reqSeqRef = useRef<number>(0);
  const periodHydratingRef = useRef<boolean>(false);
  const banksSyncedRef = useRef<boolean>(false);
  const [activeTab, setActiveTab] = useState<AccountingTab>("JOURNAL");

  const initialVes = userBanks.reduce(
    (sum, b) => sum + (Number(bankInitialMap[b]) || 0),
    0
  );
  const committedVes = userBanks.reduce(
    (sum, b) => sum + (Number(committedBankMap[b]) || 0),
    0
  );

  const [liveBalance, setLiveBalance] = useState<LiveBalanceState | null>(initialBalance);
  const [journalEntries, setJournalEntries] = useState<JournalEntryItem[]>(initialJournal || []);
  const [ledgerSummaries, setLedgerSummaries] = useState<LedgerSummaryItem[]>([]);
  const [fiscalSummary, setFiscalSummary] = useState<FiscalSummary | null>(null);

  const [lastVoucher, setLastVoucher] = useState<UploadVoucherResponse | null>(null);
  const [manualOrderNumber, setManualOrderNumber] = useState<string>("");

  const [loading, setLoading] = useState<boolean>(!initialJournal && !initialBalance);
  const [uploadingOcr, setUploadingOcr] = useState<boolean>(false);
  const [uploadingStatement, setUploadingStatement] = useState<boolean>(false);
  const [statementPreview, setStatementPreview] = useState<StatementPreviewResponse | null>(null);
  const [statementSourceFile, setStatementSourceFile] = useState<File | null>(null);
  const [reconciling, setReconciling] = useState<boolean>(false);
  const [showCloseModal, setShowCloseModal] = useState<boolean>(false);
  const [closeConfirmText, setCloseConfirmText] = useState<string>("");
  const [periodClosed, setPeriodClosed] = useState<boolean>(false);

  // Flujo de Conciliación Manual Ultrarrápido (<5s con atajo Alt+N)
  const [showManualModal, setShowManualModal] = useState<boolean>(false);
  const [savingManual, setSavingManual] = useState<boolean>(false);
  const [manualBank, setManualBank] = useState<string>("Banesco");
  const [manualRef, setManualRef] = useState<string>("");
  const [manualAmountVes, setManualAmountVes] = useState<number>(0);
  const [manualMovementType, setManualMovementType] = useState<"DEBIT" | "CREDIT">("DEBIT");
  const [manualPaymentMethod, setManualPaymentMethod] = useState<
    "PAGO_MOVIL" | "TRANSFER" | "INTERBANK"
  >("PAGO_MOVIL");
  const [manualOrderLink, setManualOrderLink] = useState<string>("");

  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Sincronizar bancos registrados del usuario desde el servidor al montar
  useEffect(() => {
    setUser(getCurrentUser());
    if (banksSyncedRef.current) return;
    banksSyncedRef.current = true;
    getUserBanksSettings()
      .then((res) => {
        if (res && res.preferred_banks && res.preferred_banks.length > 0) {
          setUserBanks(res.preferred_banks);
          setManualBank(res.preferred_banks[0]);
        }
      })
      .catch(() => null);
  }, []);

  // Cargar apertura y arqueo aislados por período (YYYY-MM) con arrastre automático Mes N-1 -> Mes N
  useEffect(() => {
    const current = getCurrentUser();
    if (!current || current.role === "INVITADO") return;
    let cancelled = false;
    periodHydratingRef.current = true;
    getAccountingPeriodConfig(year, month)
      .then((cfg) => {
        if (cancelled) return;
        setPeriodConfig(cfg);
        setBankInitialMap(cfg.initial_banks || {});
        setCommittedBankMap(cfg.initial_banks || {});
        setInitialUsdt(cfg.initial_usdt || 0);
        setCommittedUsdt(cfg.initial_usdt || 0);
        setInitialUsdtCostVes(cfg.initial_usdt_cost_ves || 0);
        setPeriodClosed(Boolean(cfg.is_closed));
      })
      .catch(() => null)
      .finally(() => {
        if (!cancelled) {
          setTimeout(() => {
            periodHydratingRef.current = false;
          }, 150);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [year, month]);

  const persistCurrentPeriodOpening = useCallback(
    (nextBanks: Record<string, number>, nextUsdt: number, nextCostVes?: number) => {
      if (periodHydratingRef.current) return;
      const bcvDay1 = periodConfig?.bcv_day1_rate || 0;
      const effCost =
        nextCostVes !== undefined
          ? nextCostVes
          : initialUsdtCostVes > 0
          ? initialUsdtCostVes
          : nextUsdt > 0 && bcvDay1 > 0
          ? Number((nextUsdt * bcvDay1).toFixed(2))
          : 0;
      void saveAccountingPeriodConfig({
        year,
        month,
        initial_usdt: nextUsdt,
        initial_usdt_cost_ves: effCost,
        initial_banks: nextBanks,
      })
        .then((saved) => setPeriodConfig(saved))
        .catch(() => null);
    },
    [year, month, initialUsdtCostVes, periodConfig?.bcv_day1_rate]
  );

  // Debounce de 750ms para saldos iniciales por banco aislados al período actual
  useEffect(() => {
    if (periodHydratingRef.current) return;
    const timer = setTimeout(() => {
      setCommittedBankMap((prev) => {
        const prevJson = JSON.stringify(prev);
        const nextJson = JSON.stringify(bankInitialMap);
        if (prevJson === nextJson) return prev;
        persistCurrentPeriodOpening(bankInitialMap, initialUsdt);
        return { ...bankInitialMap };
      });
    }, 750);
    return () => clearTimeout(timer);
  }, [bankInitialMap, initialUsdt, persistCurrentPeriodOpening]);

  useEffect(() => {
    if (periodHydratingRef.current) return;
    const timer = setTimeout(() => {
      setCommittedUsdt((prev) => {
        if (prev === initialUsdt) return prev;
        const bcvDay1 = periodConfig?.bcv_day1_rate || 0;
        const autoCost = initialUsdt > 0 && bcvDay1 > 0 ? Number((initialUsdt * bcvDay1).toFixed(2)) : 0;
        setInitialUsdtCostVes(autoCost);
        persistCurrentPeriodOpening(bankInitialMap, initialUsdt, autoCost);
        return initialUsdt;
      });
    }, 750);
    return () => clearTimeout(timer);
  }, [initialUsdt, bankInitialMap, periodConfig?.bcv_day1_rate, persistCurrentPeriodOpening]);

  function handleUpdateBankInitial(bankName: string, amount: number) {
    setBankInitialMap((prev) => ({
      ...prev,
      [bankName]: amount,
    }));
  }

  function handleCommitBankInitial(bankName: string, amount: number) {
    const nextMap = {
      ...bankInitialMap,
      [bankName]: amount,
    };
    setBankInitialMap(nextMap);
    setCommittedBankMap((prev) => {
      if (JSON.stringify(prev) === JSON.stringify(nextMap)) return prev;
      persistCurrentPeriodOpening(nextMap, initialUsdt);
      return nextMap;
    });
  }

  async function handleSyncPeriodOrders() {
    setFeedback(null);
    setSyncingPeriodOrders(true);
    const mLabel = MONTHS.find((m) => m.value === month)?.label || String(month);
    try {
      const res = await syncOrders(31, undefined, year, month);
      setFeedback({
        type: "success",
        text:
          res?.message ||
          `Órdenes de ${mLabel} ${year} sincronizadas con tasa BCV histórica.`,
      });
      const cfg = await getAccountingPeriodConfig(year, month).catch(() => null);
      if (cfg) setPeriodConfig(cfg);
      await loadAccountingData();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text:
          err.message ||
          `No se pudo sincronizar ${mLabel} ${year} desde Binance API. Verifica tu API Key o sube el Excel en Órdenes.`,
      });
    } finally {
      setSyncingPeriodOrders(false);
    }
  }

  function handleToggleUserBank(rawBank: string) {
    const canon = canonicalBankName(rawBank);
    if (!canon) return;
    const exists = userBanks.includes(canon);
    if (exists && userBanks.length <= 1) {
      setFeedback({
        type: "error",
        text: "Debes mantener al menos 1 banco activo en tu perfil contable.",
      });
      return;
    }
    const nextBanks = exists
      ? userBanks.filter((b) => b !== canon)
      : [...userBanks, canon];
    const nextBals: Record<string, number> = {};
    for (const b of nextBanks) {
      nextBals[b] = Number(bankInitialMap[b] ?? 0);
    }
    setUserBanks(nextBanks);
    setBankInitialMap(nextBals);
    setCommittedBankMap(nextBals);
    void saveUserBanksSettings({
      preferred_banks: nextBanks,
      bank_initial_balances: nextBals,
    });
  }

  const loadAccountingData = useCallback(async () => {
    const current = getCurrentUser();
    setUser(current);
    if (!current || current.role === "INVITADO") {
      setLoading(false);
      return;
    }

    const seq = ++reqSeqRef.current;
    setLoading(true);
    const periodStr = `${year}-${String(month).padStart(2, "0")}`;
    const startDate = `${periodStr}-01`;
    const lastDay = new Date(year, month, 0).getDate();
    const endDate = `${periodStr}-${String(lastDay).padStart(2, "0")}T23:59:59`;

    try {
      const [liveRes, journalRes, ledgerRes, fiscalRes, snapshotRes] = await Promise.all([
        getLiveBalance(year, month, committedUsdt, committedVes, committedBankMap).catch(
          () => null
        ),
        getJournalEntries(startDate, endDate).catch(() => []),
        getLedgerSummaries(year, month, undefined, committedVes).catch(() => []),
        getFiscalSummary(periodStr, committedUsdt).catch(() => null),
        getFiscalSnapshot(periodStr).catch(() => null),
      ]);

      // Descartar respuestas antiguas fuera de orden (evita que un dígito previo sobrescriba la tarjeta)
      if (seq !== reqSeqRef.current) return;

      if (liveRes) setLiveBalance(liveRes);
      setJournalEntries(journalRes || []);
      setLedgerSummaries(ledgerRes || []);
      if (fiscalRes) setFiscalSummary(fiscalRes);
      setPeriodClosed(Boolean(snapshotRes?.is_closed));
    } catch (err: any) {
      if (seq !== reqSeqRef.current) return;
      setFeedback({
        type: "error",
        text: err.message || "Error al consultar el motor contable SENIAT.",
      });
    } finally {
      if (seq === reqSeqRef.current) {
        setLoading(false);
      }
    }
  }, [year, month, committedUsdt, committedVes, committedBankMap]);

  useEffect(() => {
    loadAccountingData();
  }, [loadAccountingData]);

  // Atajo de teclado global Alt+N para abrir el Asiento Manual Ultrarrápido en <5s
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.altKey && e.key.toLowerCase() === "n") {
        e.preventDefault();
        if (!periodClosed) {
          setShowManualModal((prev) => !prev);
        }
      } else if (e.key === "Escape" && showManualModal) {
        setShowManualModal(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [periodClosed, showManualModal]);

  async function handleCreateManualVoucher(e: React.FormEvent) {
    e.preventDefault();
    const amountNum = Number(manualAmountVes);
    if (!manualRef.trim() || !amountNum || amountNum <= 0) {
      setFeedback({
        type: "error",
        text: "Ingresa una referencia bancaria válida y un monto mayor a 0,00 VES.",
      });
      return;
    }

    setFeedback(null);
    setSavingManual(true);
    try {
      const res = await createManualVoucher({
        bank_name: manualBank,
        reference_number: manualRef.trim(),
        amount_ves: amountNum,
        movement_type: manualMovementType,
        payment_method: manualPaymentMethod,
        order_number: manualOrderLink.trim() || undefined,
      });
      setShowManualModal(false);
      setManualRef("");
      setManualAmountVes(0);
      setManualOrderLink("");
      setFeedback({
        type: "success",
        text: `Pago manual #${res.reference_number} (${res.bank_name} • Bs. ${res.amount_ves.toFixed(
          2
        )}) asentado (${res.verification_status}).`,
      });
      await loadAccountingData();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error al registrar el comprobante manual.",
      });
    } finally {
      setSavingManual(false);
    }
  }

  async function handleUploadReceipt(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) {
      setFeedback({
        type: "error",
        text: "El comprobante supera el límite de 15 MB. Comprímelo o recorta la captura antes de subirlo.",
      });
      if (voucherInputRef.current) voucherInputRef.current.value = "";
      return;
    }
    setFeedback(null);
    setUploadingOcr(true);
    try {
      const res = await uploadVoucherFile(file);
      setLastVoucher(res);
      setFeedback({
        type: "success",
        text: `Comprobante OCR #${res.reference_number} (${res.bank_name} • Bs. ${res.amount_ves.toFixed(
          2
        )}) procesado.`,
      });
      await loadAccountingData();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo extraer el recibo bancario mediante OCR.",
      });
    } finally {
      setUploadingOcr(false);
      if (voucherInputRef.current) voucherInputRef.current.value = "";
    }
  }

  async function handleUploadStatement(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) {
      setFeedback({
        type: "error",
        text: "El estado de cuenta supera el límite de 25 MB. Divide el período o sube el PDF/captura optimizada.",
      });
      if (statementInputRef.current) statementInputRef.current.value = "";
      return;
    }
    setFeedback(null);
    setUploadingStatement(true);
    try {
      const previewRes = await previewBankStatement(file);
      setStatementSourceFile(file);
      setStatementPreview(previewRes);
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo leer el estado de cuenta bancario.",
      });
    } finally {
      setUploadingStatement(false);
      if (statementInputRef.current) statementInputRef.current.value = "";
    }
  }

  async function handleAutoReconcile() {
    setFeedback(null);
    setReconciling(true);
    try {
      const res = await reconcileOrphanVouchers(48);
      setFeedback({
        type: "success",
        text:
          res?.message ||
          `Auto-conciliación ejecutada (${res?.matched_count ?? 0} recibos vinculados).`,
      });
      await loadAccountingData();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Error al auto-conciliar comprobantes huérfanos.",
      });
    } finally {
      setReconciling(false);
    }
  }

  async function handleManualMatch(e: React.FormEvent) {
    e.preventDefault();
    if (!lastVoucher || !manualOrderNumber.trim()) return;
    try {
      await matchVoucherWithOrder(lastVoucher.voucher_id, manualOrderNumber.trim());
      setFeedback({
        type: "success",
        text: `Comprobante #${lastVoucher.reference_number} vinculado con orden ${manualOrderNumber.trim()}.`,
      });
      setManualOrderNumber("");
      setLastVoucher(null);
      await loadAccountingData();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "No se pudo vincular el comprobante a la orden.",
      });
    }
  }

  if (!user || user.role === "INVITADO") {
    return (
      <AppShell
        title="Contabilidad y Libro Diario SENIAT"
        badge="ACCESO RESTRINGIDO"
        subtitle="Módulo contable en partida doble reservado para operadores Comerciante y Administrador."
      >
        <div className="max-w-lg mx-auto my-12 p-6 rounded-2xl bg-surface-container-low border border-[#1e2430] text-center space-y-4">
          <span className="material-symbols-outlined text-[36px] text-primary">
            menu_book
          </span>
          <h2 className="text-base font-bold text-white">
            Inicia sesión con rol Comerciante o Administrador
          </h2>
          <p className="text-xs text-slate-400">
            Accede al Libro Diario encadenado con SHA-256, Libro Mayor mensual y conciliación OCR de recibos bancarios.
          </p>
          <Link
            href="/login"
            className="inline-block px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold"
          >
            Ir al Inicio de Sesión
          </Link>
        </div>
      </AppShell>
    );
  }

  const netFlowVes =
    (liveBalance?.total_inflows_ves ?? 0) - (liveBalance?.total_outflows_ves ?? 0);
  const displayedTheoreticalVes = initialVes + netFlowVes;

  const netFlowUsdt =
    (liveBalance?.inflow_usdt ?? 0) - (liveBalance?.outflow_usdt ?? 0);
  const displayedTheoreticalUsdt = initialUsdt + netFlowUsdt;

  // Subcajas dinámicas por cada banco registrado del usuario con su saldo inicial + entradas - salidas
  const bankBoxes: BankBreakdownItem[] = userBanks.map((bName) => {
    const matched = (liveBalance?.bank_breakdown || []).find((item) =>
      bankMatchesProfile(item.bank_name, [bName])
    );
    const initVal = Number(bankInitialMap[bName]) || 0;
    const inflows = matched?.inflows_ves ?? 0;
    const outflows = matched?.outflows_ves ?? 0;
    return {
      bank_name: bName,
      initial_ves: initVal,
      inflows_ves: inflows,
      outflows_ves: outflows,
      theoretical_ves: initVal + inflows - outflows,
    };
  });

  return (
    <AppShell
      title="Contabilidad"
      badge={periodClosed ? "CERRADO" : undefined}
      subtitle="Libros, saldos y conciliación de pagos."
      actions={
        <div className="flex items-center gap-2 flex-wrap">
          {/* Selector de Período Mes / Año */}
          <div className="flex items-center gap-1 bg-surface-container px-2 py-1 rounded-lg border border-[#1e2430] text-xs font-mono">
            <select
              aria-label="Seleccionar mes contable"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="bg-transparent text-white focus:outline-hidden"
            >
              {MONTHS.map((m) => (
                <option key={m.value} value={m.value} className="bg-[#141920]">
                  {m.label}
                </option>
              ))}
            </select>
            <select
              aria-label="Seleccionar año contable"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="bg-transparent text-primary font-bold focus:outline-hidden"
            >
              {[2025, 2026, 2027].map((y) => (
                <option key={y} value={y} className="bg-[#141920]">
                  {y}
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            onClick={async () => {
              try {
                await downloadAccountingExcel(year, month);
              } catch (err: any) {
                setFeedback({
                  type: "error",
                  text: err.message || "Error al descargar el libro contable en Excel.",
                });
              }
            }}
            className="px-3 py-1.5 rounded-lg bg-tertiary/15 border border-tertiary/35 text-tertiary text-xs font-mono font-semibold hover:bg-tertiary/25 flex items-center gap-1.5 whitespace-nowrap cursor-pointer"
          >
            <span className="material-symbols-outlined text-[15px]">grid_on</span>
            <span>Excel</span>
          </button>

          <button
            type="button"
            onClick={async () => {
              try {
                await downloadAccountingPdf(year, month);
              } catch (err: any) {
                setFeedback({
                  type: "error",
                  text: err.message || "Error al descargar el informe contable en PDF.",
                });
              }
            }}
            className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-secondary/50 text-slate-200 text-xs font-mono flex items-center gap-1.5 whitespace-nowrap cursor-pointer"
          >
            <span className="material-symbols-outlined text-[15px] text-secondary">
              picture_as_pdf
            </span>
            <span>PDF</span>
          </button>

          <button
            type="button"
            onClick={() => {
              const initActualBanks: Record<string, number> = {};
              for (const b of bankBoxes) {
                initActualBanks[b.bank_name] =
                  periodConfig?.actual_final_banks?.[b.bank_name] ??
                  Number(b.theoretical_ves.toFixed(2));
              }
              setCloseActualBanks(initActualBanks);
              setCloseActualUsdt(
                periodConfig?.actual_final_usdt ??
                  Number(
                    (
                      fiscalSummary?.calculated_final_balance ??
                      displayedTheoreticalUsdt
                    ).toFixed(4)
                  )
              );
              setShowCloseModal(true);
            }}
            className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 flex items-center gap-1 whitespace-nowrap cursor-pointer"
          >
            <span className="material-symbols-outlined text-[15px]">lock_clock</span>
            <span>Cerrar mes</span>
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
                {feedback.type === "success" ? "task_alt" : "error"}
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

        {/* Barra compacta de Modo del Período (Histórico vs En vivo) + Flujo en 4 Pasos */}
        <section className="p-3 sm:p-3.5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-bold border ${
                  periodConfig?.is_historical_month
                    ? "bg-secondary/15 border-secondary/35 text-secondary"
                    : "bg-tertiary/15 border-tertiary/35 text-tertiary"
                }`}
              >
                {periodConfig?.is_historical_month
                  ? `AUDITORÍA HISTÓRICA · ${MONTHS.find((m) => m.value === month)?.label?.toUpperCase()} ${year}`
                  : `MES EN CURSO · ${MONTHS.find((m) => m.value === month)?.label?.toUpperCase()} ${year}`}
              </span>
              {periodConfig?.source === "carried_over" && periodConfig.carried_from && (
                <span className="text-[10px] font-mono text-primary bg-primary-container/10 border border-primary-container/30 px-2 py-0.5 rounded-md">
                  Saldo inicial heredado de {periodConfig.carried_from}
                </span>
              )}
              {periodConfig && periodConfig.bcv_day1_rate > 0 && (
                <span className="text-[10px] font-mono text-slate-400">
                  BCV día 1: Bs. {periodConfig.bcv_day1_rate.toFixed(4)}
                </span>
              )}
            </div>

            <button
              type="button"
              onClick={handleSyncPeriodOrders}
              disabled={syncingPeriodOrders}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-mono font-semibold border flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50 ${
                (periodConfig?.orders_count_in_period ?? 0) === 0
                  ? "bg-primary-container/15 border-primary-container/50 text-primary hover:bg-primary-container/25"
                  : "bg-surface-container border-[#1e2430] text-slate-200 hover:border-primary-container/40"
              }`}
            >
              <span
                className={`material-symbols-outlined text-[14px] ${
                  syncingPeriodOrders ? "animate-spin" : ""
                }`}
              >
                cloud_sync
              </span>
              <span>
                {syncingPeriodOrders
                  ? `Sincronizando ${MONTHS.find((m) => m.value === month)?.label}...`
                  : `Sincronizar ${MONTHS.find((m) => m.value === month)?.label} (${periodConfig?.orders_count_in_period ?? 0} órd.)`}
              </span>
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 text-[10px] font-mono">
            {[
              {
                n: "1",
                label: "Apertura (Bs + USDT)",
                done: periodConfig?.source === "saved" || initialVes > 0 || initialUsdt > 0,
              },
              {
                n: "2",
                label: "Órdenes y Pagos",
                done: (periodConfig?.orders_count_in_period ?? 0) > 0 || journalEntries.length > 0,
              },
              {
                n: "3",
                label: "Arqueo Final Real",
                done: periodConfig?.actual_final_usdt !== null && periodConfig?.actual_final_usdt !== undefined,
              },
              {
                n: "4",
                label: "Cerrar y Descargar",
                done: periodClosed,
              },
            ].map((s) => (
              <div
                key={s.n}
                className={`px-2.5 py-1.5 rounded-lg border flex items-center gap-1.5 truncate ${
                  s.done
                    ? "bg-tertiary/10 border-tertiary/30 text-tertiary"
                    : "bg-surface-container border-[#1e2430] text-slate-400"
                }`}
              >
                <span className="font-bold">{s.done ? "✓" : `${s.n}.`}</span>
                <span className="truncate">{s.label}</span>
              </div>
            ))}
          </div>
        </section>

        {/* 3 Tarjetas Bento de Saldos y Conciliación OCR (En móvil: Saldos VES y USDT lado a lado en una línea) */}
        <section className="grid grid-cols-2 lg:grid-cols-12 gap-2.5 sm:gap-4">
          {/* Card 1: Saldo Bancario Desglosado por los Bancos del Usuario */}
          <div className="col-span-2 lg:col-span-5 p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0 flex flex-col justify-between gap-2.5 sm:gap-3.5">
            <div className="flex items-start justify-between gap-2 min-w-0">
              <div className="min-w-0">
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 truncate">
                  Saldo total en mis bancos (VES)
                </div>
                <div className="mt-0.5 sm:mt-1 text-base sm:text-2xl font-mono font-bold text-white tabular-nums truncate">
                  Bs.{" "}
                  {displayedTheoreticalVes.toLocaleString("es-VE", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </div>
                <div className="text-[10px] font-mono text-slate-400 tabular-nums truncate">
                  Inicial sumado: Bs.{" "}
                  {initialVes.toLocaleString("es-VE", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowBankSelector((prev) => !prev)}
                aria-expanded={showBankSelector}
                className={`px-2.5 py-1.5 rounded-lg text-[11px] font-mono font-semibold flex items-center gap-1.5 border transition-colors shrink-0 cursor-pointer ${
                  showBankSelector
                    ? "bg-primary-container text-on-primary border-primary-container"
                    : "bg-surface-container border-[#1e2430] text-primary hover:border-primary-container/50"
                }`}
              >
                <span className="material-symbols-outlined text-[15px]" aria-hidden="true">
                  account_balance
                </span>
                <span>Mis bancos ({userBanks.length})</span>
              </button>
            </div>

            {showBankSelector && (
              <div className="p-2.5 rounded-xl bg-surface-container-lowest border border-primary-container/30 space-y-2">
                <div className="flex items-center justify-between gap-2 text-[10px] font-mono text-slate-300">
                  <span>Selecciona los bancos con los que trabajas:</span>
                  <span className="text-primary">{userBanks.length} activos</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {VENEZUELAN_BANK_CATALOG.map((bankOpt) => {
                    const active = userBanks.includes(bankOpt);
                    return (
                      <button
                        key={bankOpt}
                        type="button"
                        onClick={() => handleToggleUserBank(bankOpt)}
                        aria-pressed={active}
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-mono transition-colors flex items-center gap-1 cursor-pointer ${
                          active
                            ? "bg-primary-container text-on-primary font-bold"
                            : "bg-surface-container text-slate-400 hover:text-white border border-[#1e2430]"
                        }`}
                      >
                        <span>{active ? "✓" : "+"}</span>
                        <span>{bankOpt}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Subcajas por Banco con su propio campo de Saldo Inicial VES */}
            <div className="grid grid-cols-2 sm:grid-cols-2 gap-2">
              {bankBoxes.map((b) => {
                const inputId = `bank-init-${b.bank_name.replace(/\s+/g, "-").toLowerCase()}`;
                return (
                  <div
                    key={b.bank_name}
                    className="p-2.5 rounded-lg bg-surface-container border border-[#1e2430] min-w-0 flex flex-col justify-between gap-1.5"
                  >
                    <div className="flex items-center justify-between gap-1 min-w-0">
                      <span
                        className="text-[10px] font-mono uppercase text-primary truncate font-bold"
                        title={b.bank_name}
                      >
                        {b.bank_name}
                      </span>
                      <span className="text-[9px] font-mono text-slate-400 tabular-nums shrink-0">
                        +{b.inflows_ves.toFixed(0)} / -{b.outflows_ves.toFixed(0)}
                      </span>
                    </div>

                    <div className="text-xs sm:text-sm font-mono font-bold text-white tabular-nums truncate">
                      Bs.{" "}
                      {b.theoretical_ves.toLocaleString("es-VE", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </div>

                    <div className="pt-1 border-t border-[#1e2430]/80 flex items-center justify-between gap-1.5">
                      <label
                        htmlFor={inputId}
                        className="text-[9px] font-mono uppercase text-slate-400 shrink-0"
                      >
                        Inicial:
                      </label>
                      <BankAmountInput
                        id={inputId}
                        value={b.initial_ves}
                        onChange={(val) => handleUpdateBankInitial(b.bank_name, val)}
                        onCommit={(val) => handleCommitBankInitial(b.bank_name, val)}
                        ariaLabel={`Saldo inicial en ${b.bank_name} (VES)`}
                        className="w-full max-w-[125px] px-2 py-0.5 rounded bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-right text-[11px] font-mono text-primary tabular-nums"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Card 2: Saldo USDT */}
          <div className="col-span-2 lg:col-span-3 p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0 flex flex-col justify-between gap-2.5 sm:gap-4">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2 min-w-0">
              <div className="min-w-0">
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 truncate">
                  Saldo USDT
                </div>
                <div className="mt-0.5 sm:mt-1 text-base sm:text-2xl font-mono font-bold text-tertiary tabular-nums truncate">
                  {displayedTheoreticalUsdt.toFixed(2)} USDT
                </div>
              </div>
              <div className="sm:text-right shrink-0">
                <label className="block text-[9px] font-mono uppercase text-slate-400">
                  Inicial USDT
                </label>
                <BankAmountInput
                  value={initialUsdt}
                  onChange={setInitialUsdt}
                  onCommit={setCommittedUsdt}
                  ariaLabel="Saldo Inicial USDT"
                  className="w-full sm:w-24 mt-0.5 px-2 py-1 rounded bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-right text-xs font-mono text-tertiary tabular-nums"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-1.5 sm:gap-2 text-[11px] sm:text-xs font-mono tabular-nums">
              <div className="p-2 rounded-lg bg-surface-container border border-[#1e2430] min-w-0">
                <div className="text-[9px] text-slate-400 uppercase truncate">Compras</div>
                <div className="text-tertiary font-semibold mt-0.5 truncate">
                  +{(liveBalance?.inflow_usdt ?? 0).toFixed(2)}
                </div>
              </div>
              <div className="p-2 rounded-lg bg-surface-container border border-[#1e2430] min-w-0">
                <div className="text-[9px] text-slate-400 uppercase truncate">Ventas</div>
                <div className="text-primary font-semibold mt-0.5 truncate">
                  -{(liveBalance?.outflow_usdt ?? 0).toFixed(2)}
                </div>
              </div>
            </div>
          </div>

          {/* Card 3: Conciliación */}
          <div className="col-span-2 lg:col-span-4 p-3.5 sm:p-4 rounded-xl bg-surface-container border border-[#1e2430] min-w-0 flex flex-col justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-secondary">
                document_scanner
              </span>
              <span className="text-xs font-bold text-white">
                Conciliar pagos
              </span>
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed">
              Sube capturas, estados de cuenta bancarios (.pdf/.xlsx/.csv) o registra pagos manuales.
            </p>

            <input
              ref={voucherInputRef}
              type="file"
              accept="image/*,.pdf"
              onChange={handleUploadReceipt}
              className="hidden"
            />

            <input
              ref={statementInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.xlsx,.xls,.csv,.txt"
              onChange={handleUploadStatement}
              className="hidden"
            />

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => voucherInputRef.current?.click()}
                disabled={uploadingOcr || periodClosed}
                className="px-3 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-50 flex items-center justify-center gap-1.5 whitespace-nowrap cursor-pointer"
              >
                <span className="material-symbols-outlined text-[16px]">
                  add_photo_alternate
                </span>
                <span>{uploadingOcr ? "Leyendo..." : "Subir recibo"}</span>
              </button>

              <button
                type="button"
                onClick={() => statementInputRef.current?.click()}
                disabled={uploadingStatement || periodClosed}
                className="px-3 py-2 rounded-lg bg-secondary/15 border border-secondary/35 text-secondary text-xs font-bold hover:bg-secondary/25 disabled:opacity-50 flex items-center justify-center gap-1.5 whitespace-nowrap cursor-pointer"
              >
                <span className="material-symbols-outlined text-[16px]">
                  account_balance
                </span>
                <span>{uploadingStatement ? "Analizando..." : "Estado bancario"}</span>
              </button>

              <button
                type="button"
                onClick={() => setShowManualModal(true)}
                disabled={periodClosed}
                title="Atajo: Alt+N"
                className="px-3 py-2 rounded-lg bg-surface-container-high border border-slate-700 hover:border-primary-container/60 text-xs font-mono text-white flex items-center justify-center gap-1.5 whitespace-nowrap cursor-pointer"
              >
                <span className="material-symbols-outlined text-[16px] text-primary">
                  keyboard
                </span>
                <span>Manual</span>
              </button>

              <button
                type="button"
                onClick={handleAutoReconcile}
                disabled={reconciling || periodClosed}
                className="px-3 py-2 rounded-lg bg-surface-container-high border border-[#1e2430] hover:border-secondary/50 text-xs font-mono text-slate-200 flex items-center justify-center gap-1.5 whitespace-nowrap cursor-pointer"
              >
                <span className="material-symbols-outlined text-[16px] text-secondary">
                  auto_fix_high
                </span>
                <span>{reconciling ? "Cruzando..." : "Auto-conciliar"}</span>
              </button>
            </div>
          </div>
        </section>

        {/* Tarjeta de Vinculación Manual si el último recibo OCR quedó huérfano */}
        {lastVoucher && (
          <section className="p-4 rounded-xl bg-surface-container border border-secondary/40 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="text-xs space-y-1">
              <div className="font-bold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] text-secondary">
                  receipt
                </span>
                Recibo OCR Detectado: {lastVoucher.bank_name} • Ref #
                {lastVoucher.reference_number}
              </div>
              <div className="font-mono text-slate-300 tabular-nums">
                Monto: Bs. {lastVoucher.amount_ves.toFixed(2)} | Comisión Bancaria: Bs.{" "}
                {lastVoucher.bank_fee_ves.toFixed(2)} | Estado:{" "}
                <span className="text-primary">
                  {lastVoucher.verification_status === "MATCHED"
                    ? "CONCILIADO"
                    : lastVoucher.verification_status === "UNMATCHED"
                    ? "SIN CONCILIAR"
                    : lastVoucher.verification_status === "VERIFIED"
                    ? "VERIFICADO"
                    : lastVoucher.verification_status}
                </span>
              </div>
            </div>

            <form onSubmit={handleManualMatch} className="flex items-center gap-2">
              <input
                type="text"
                value={manualOrderNumber}
                onChange={(e) => setManualOrderNumber(e.target.value)}
                placeholder="Nº Orden Binance P2P"
                className="px-3 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono text-white"
              />
              <button
                type="submit"
                className="px-3 py-1.5 rounded-lg bg-secondary text-on-secondary text-xs font-bold whitespace-nowrap"
              >
                Vincular Orden
              </button>
              <button
                type="button"
                onClick={() => setLastVoucher(null)}
                className="text-xs text-slate-400 hover:text-white px-2"
              >
                Cerrar
              </button>
            </form>
          </section>
        )}

        {/* Pestañas Contables: Libro Diario | Libro Mayor | Ecuación Fiscal 6 Piezas */}
        <section className="rounded-xl bg-surface-container-low border border-[#1e2430] overflow-hidden defer-render">
          <div className="px-4 py-3 border-b border-[#1e2430] flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-1 bg-surface-container p-1 rounded-lg border border-[#1e2430] text-xs font-mono">
              <button
                type="button"
                onClick={() => setActiveTab("JOURNAL")}
                className={`px-3 py-1 rounded-md transition-colors ${
                  activeTab === "JOURNAL"
                    ? "bg-primary-container text-on-primary font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Libro Diario ({journalEntries.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("LEDGER")}
                className={`px-3 py-1 rounded-md transition-colors ${
                  activeTab === "LEDGER"
                    ? "bg-primary-container text-on-primary font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Libro Mayor ({ledgerSummaries.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("FISCAL_6")}
                className={`px-3 py-1 rounded-md transition-colors ${
                  activeTab === "FISCAL_6"
                    ? "bg-primary-container text-on-primary font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Cuadre mensual
              </button>
            </div>
          </div>

          <div
            role="tabpanel"
            aria-hidden={activeTab !== "JOURNAL"}
            className={`spa-tab-panel ${activeTab === "JOURNAL" ? "" : "inactive"}`}
          >
            <div className="overflow-x-auto overscroll-x-contain">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 z-10 bg-surface-container">
                  <tr className="border-b border-[#1e2430] bg-surface-container/95 text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    <th scope="col" className="py-3 px-4">Asiento / Fecha</th>
                    <th scope="col" className="py-3 px-4">Cuenta</th>
                    <th scope="col" className="py-3 px-4">Concepto</th>
                    <th scope="col" className="py-3 px-4 text-right">Debe (VES)</th>
                    <th scope="col" className="py-3 px-4 text-right">Haber (VES)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2430]/70 text-xs">
                  {loading ? (
                    <tr>
                      <td colSpan={5} className="py-10 text-center text-slate-400 font-mono">
                        Cargando asientos...
                      </td>
                    </tr>
                  ) : journalEntries.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-10 text-center text-slate-400 font-mono">
                        Sin asientos en este mes.
                      </td>
                    </tr>
                  ) : (
                    journalEntries.map((entry, idx) => (
                      <tr
                        key={`${entry.entry_number}-${entry.account_code}-${idx}`}
                        className="hover:bg-surface-container/70 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono tabular-nums">
                          <div className="text-white font-semibold">
                            #{entry.entry_number}
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {entry.date_time}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-mono text-primary text-[11px] mr-1.5">
                            {entry.account_code}
                          </span>
                          <span className="text-white font-medium">
                            {entry.account_name}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-300 max-w-xs truncate">
                          <div>{entry.description}</div>
                          <div className="text-[10px] font-mono text-slate-500">
                            Ref: {entry.reference}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-tertiary font-semibold">
                          {entry.debit > 0 ? `Bs. ${entry.debit.toFixed(2)}` : "-"}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-primary font-semibold">
                          {entry.credit > 0 ? `Bs. ${entry.credit.toFixed(2)}` : "-"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div
            role="tabpanel"
            aria-hidden={activeTab !== "LEDGER"}
            className={`spa-tab-panel ${activeTab === "LEDGER" ? "" : "inactive"}`}
          >
            <div className="overflow-x-auto overscroll-x-contain">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 z-10 bg-surface-container">
                  <tr className="border-b border-[#1e2430] bg-surface-container/95 text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    <th scope="col" className="py-3 px-4">Código</th>
                    <th scope="col" className="py-3 px-4">Cuenta Mayor</th>
                    <th scope="col" className="py-3 px-4 text-right">Saldo Inicial</th>
                    <th scope="col" className="py-3 px-4 text-right">Total Debe</th>
                    <th scope="col" className="py-3 px-4 text-right">Total Haber</th>
                    <th scope="col" className="py-3 px-4 text-right">Saldo Final</th>
                    <th scope="col" className="py-3 px-4 text-right">Movimientos</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2430]/70 text-xs">
                  {ledgerSummaries.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-10 text-center text-slate-400 font-mono">
                        Sin saldos consolidados en el Libro Mayor para este mes.
                      </td>
                    </tr>
                  ) : (
                    ledgerSummaries.map((l) => (
                      <tr
                        key={l.account_code}
                        className="hover:bg-surface-container/70 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono text-primary font-semibold">
                          {l.account_code}
                        </td>
                        <td className="py-3 px-4 text-white font-medium">
                          {l.account_name}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-slate-400">
                          Bs. {l.initial_balance.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-tertiary">
                          Bs. {l.total_debit.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-primary">
                          Bs. {l.total_credit.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-white font-bold">
                          Bs. {l.final_balance.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-slate-400">
                          {l.entries_count}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div
            role="tabpanel"
            aria-hidden={activeTab !== "FISCAL_6"}
            className={`spa-tab-panel ${activeTab === "FISCAL_6" ? "" : "inactive"}`}
          >
            <div className="p-3.5 sm:p-5 grid grid-cols-2 lg:grid-cols-3 gap-2.5 sm:gap-3.5">
              {[
                {
                  title: "1. Saldo Inicial Declarado (USDT)",
                  val: fiscalSummary?.initial_balance ?? 0,
                  unit: "USDT",
                  tone: "text-white",
                },
                {
                  title: "2. Entradas Operativas (Compras/Depósitos USDT)",
                  val: fiscalSummary?.total_inflows ?? 0,
                  unit: "USDT",
                  tone: "text-tertiary",
                },
                {
                  title: "3. Salidas Operativas (Ventas/Retiros USDT)",
                  val: fiscalSummary?.total_outflows ?? 0,
                  unit: "USDT",
                  tone: "text-primary",
                },
                {
                  title: "4. Comisiones Cripto Deducibles (USDT)",
                  val: fiscalSummary?.total_fees ?? 0,
                  unit: "USDT",
                  tone: "text-slate-200",
                },
                {
                  title: "5. Saldo Final Teórico (USDT)",
                  val: fiscalSummary?.calculated_final_balance ?? 0,
                  unit: "USDT",
                  tone: "text-secondary",
                },
                {
                  title: "6. Utilidad Neta Fiscal (VES)",
                  val: fiscalSummary?.net_profit_ves ?? 0,
                  unit: "VES",
                  tone: "text-tertiary",
                },
              ].map((piece) => (
                <div
                  key={piece.title}
                  className="p-3 sm:p-4 rounded-xl bg-surface-container border border-[#1e2430] min-w-0"
                >
                  <div className="text-[10px] font-mono uppercase text-slate-400 truncate">
                    {piece.title}
                  </div>
                  <div
                    className={`mt-1.5 sm:mt-2 text-base sm:text-lg font-mono font-bold tabular-nums truncate ${piece.tone}`}
                  >
                    {piece.unit === "VES"
                      ? `Bs. ${piece.val.toLocaleString("es-VE", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}`
                      : `${piece.val.toLocaleString("es-VE", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 4,
                        })} USDT`}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Modal de Conciliación Manual Ultrarrápida (<5s sin mouse • Atajo Alt+N) */}
        {showManualModal && (
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Asiento Manual Ultrarrápido"
            className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4 overscroll-contain"
          >
            <form
              onSubmit={handleCreateManualVoucher}
              className="w-full max-w-md rounded-2xl bg-surface-container-low border border-primary-container/40 p-6 space-y-4 shadow-2xl max-h-[90vh] overflow-y-auto overscroll-contain"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-primary font-bold text-base">
                  <span className="material-symbols-outlined">bolt</span>
                  <span>Asiento Manual Ultrarrápido (Respaldo sin OCR)</span>
                </div>
                <span className="px-2 py-0.5 rounded bg-surface-container-high text-[10px] font-mono text-slate-300">
                  Alt+N • Intro
                </span>
              </div>
              <p className="text-xs text-slate-300">
                Registra un pago o cobro bancario en menos de 5 segundos usando solo el teclado (<kbd className="text-primary font-mono">Tab</kbd> para navegar, <kbd className="text-primary font-mono">Intro</kbd> para guardar y conciliar).
              </p>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="manual-ref"
                    className="block text-[10px] font-mono uppercase text-slate-300 mb-1"
                  >
                    Referencia Bancaria *
                  </label>
                  <input
                    id="manual-ref"
                    type="text"
                    autoFocus
                    required
                    autoComplete="off"
                    enterKeyHint="next"
                    value={manualRef}
                    onChange={(e) => setManualRef(e.target.value)}
                    placeholder="Ej. 00998877"
                    className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs font-mono text-white"
                  />
                </div>
                <div>
                  <label
                    htmlFor="manual-amount-ves"
                    className="block text-[10px] font-mono uppercase text-slate-300 mb-1"
                  >
                    Monto (VES) *
                  </label>
                  <BankAmountInput
                    id="manual-amount-ves"
                    required
                    value={manualAmountVes}
                    onChange={setManualAmountVes}
                    ariaLabel="Monto en Bolívares (VES)"
                    className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs font-mono text-primary font-bold text-right tabular-nums"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label
                    htmlFor="manual-bank"
                    className="block text-[10px] font-mono uppercase text-slate-300 mb-1"
                  >
                    Banco
                  </label>
                  <select
                    id="manual-bank"
                    value={manualBank}
                    onChange={(e) => setManualBank(e.target.value)}
                    className="w-full px-2.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs text-white"
                  >
                    <optgroup label="★ Mis bancos">
                      {userBanks.map((b) => (
                        <option key={`my-${b}`} value={b}>
                          {b}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="Otros bancos">
                      {VENEZUELAN_BANK_CATALOG.filter((b) => !userBanks.includes(b)).map(
                        (b) => (
                          <option key={`other-${b}`} value={b}>
                            {b}
                          </option>
                        )
                      )}
                    </optgroup>
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="manual-op"
                    className="block text-[10px] font-mono uppercase text-slate-300 mb-1"
                  >
                    Operación
                  </label>
                  <select
                    id="manual-op"
                    value={manualMovementType}
                    onChange={(e) =>
                      setManualMovementType(e.target.value as "DEBIT" | "CREDIT")
                    }
                    className="w-full px-2.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono text-white"
                  >
                    <option value="DEBIT">Egreso (Compra)</option>
                    <option value="CREDIT">Ingreso (Venta)</option>
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="manual-channel"
                    className="block text-[10px] font-mono uppercase text-slate-300 mb-1"
                  >
                    Canal
                  </label>
                  <select
                    id="manual-channel"
                    value={manualPaymentMethod}
                    onChange={(e) =>
                      setManualPaymentMethod(
                        e.target.value as "PAGO_MOVIL" | "TRANSFER" | "INTERBANK"
                      )
                    }
                    className="w-full px-2.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono text-white"
                  >
                    <option value="PAGO_MOVIL">Pago Móvil (0.3%)</option>
                    <option value="TRANSFER">Mismo Banco (0%)</option>
                    <option value="INTERBANK">Interbancario</option>
                  </select>
                </div>
              </div>

              <div>
                <label
                  htmlFor="manual-order-link"
                  className="block text-[10px] font-mono uppercase text-slate-300 mb-1"
                >
                  Nº Orden Binance P2P (Opcional — si se omite, cruza por monto)
                </label>
                <input
                  id="manual-order-link"
                  type="text"
                  autoComplete="off"
                  enterKeyHint="done"
                  value={manualOrderLink}
                  onChange={(e) => setManualOrderLink(e.target.value)}
                  placeholder="Ej. 20261114000123"
                  className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-xs font-mono text-white"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowManualModal(false)}
                  className="px-3.5 py-2 rounded-lg bg-surface-container text-xs text-slate-300 hover:text-white"
                >
                  Cancelar (Esc)
                </button>
                <button
                  type="submit"
                  disabled={savingManual}
                  className="px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold hover:brightness-110 disabled:opacity-50 cursor-pointer"
                >
                  {savingManual ? "Asentando..." : "Asentar y Conciliar (Intro)"}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Modal de Arqueo Final Real y Cierre Mensual */}
        {showCloseModal && (() => {
          const theoUsdt = Number(
            (fiscalSummary?.calculated_final_balance ?? displayedTheoreticalUsdt).toFixed(4)
          );
          const diffUsdt = Number((closeActualUsdt - theoUsdt).toFixed(4));
          const theoTotalVes = Number(displayedTheoreticalVes.toFixed(2));
          const actualTotalVes = Number(
            Object.values(closeActualBanks)
              .reduce((acc, v) => acc + (Number(v) || 0), 0)
              .toFixed(2)
          );
          const diffVes = Number((actualTotalVes - theoTotalVes).toFixed(2));
          const isUsdtOk = Math.abs(diffUsdt) <= 0.05;
          const isVesOk = Math.abs(diffVes) <= 1.0;

          return (
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Arqueo Final y Cierre Contable"
              className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4 overscroll-contain"
            >
              <div className="w-full max-w-lg rounded-2xl bg-surface-container-low border border-primary-container/40 p-5 sm:p-6 space-y-4 shadow-2xl max-h-[90vh] overflow-y-auto overscroll-contain">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-primary font-bold text-base">
                    <span className="material-symbols-outlined">fact_check</span>
                    <span>
                      Arqueo y Cierre · {MONTHS.find((m) => m.value === month)?.label} {year}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">
                  Ingresa tu <strong className="text-white">saldo real de cierre</strong> en Binance y bancos para comparar contra el cálculo teórico. Ese saldo real pasará automáticamente como apertura del mes siguiente.
                </p>

                {/* Arqueo USDT */}
                <div className="p-3 rounded-xl bg-surface-container border border-[#1e2430] space-y-2">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-slate-300 font-semibold">Binance USDT (Real vs Teórico)</span>
                    <span className={isUsdtOk ? "text-tertiary font-bold" : "text-amber-400 font-bold"}>
                      {isUsdtOk ? "✓ Cuadrado" : `Dif: ${diffUsdt >= 0 ? "+" : ""}${diffUsdt.toFixed(2)} USDT`}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[11px] font-mono text-slate-400">
                      Teórico: {theoUsdt.toFixed(2)} USDT
                    </span>
                    <BankAmountInput
                      value={closeActualUsdt}
                      onChange={setCloseActualUsdt}
                      ariaLabel="Saldo final real en Binance USDT"
                      className="w-36 px-2.5 py-1.5 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-right text-xs font-mono text-tertiary font-bold tabular-nums"
                    />
                  </div>
                </div>

                {/* Arqueo Bancos VES */}
                <div className="p-3 rounded-xl bg-surface-container border border-[#1e2430] space-y-2">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-slate-300 font-semibold">Bancos VES (Real vs Teórico)</span>
                    <span className={isVesOk ? "text-tertiary font-bold" : "text-amber-400 font-bold"}>
                      {isVesOk ? "✓ Cuadrado" : `Dif: ${diffVes >= 0 ? "+" : ""}Bs. ${diffVes.toFixed(2)}`}
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {bankBoxes.map((b) => (
                      <div key={b.bank_name} className="flex items-center justify-between gap-2 text-xs font-mono">
                        <div className="min-w-0">
                          <div className="text-white truncate">{b.bank_name}</div>
                          <div className="text-[10px] text-slate-400">
                            Teórico: Bs. {b.theoretical_ves.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </div>
                        </div>
                        <BankAmountInput
                          value={closeActualBanks[b.bank_name] ?? 0}
                          onChange={(val) =>
                            setCloseActualBanks((prev) => ({ ...prev, [b.bank_name]: val }))
                          }
                          ariaLabel={`Saldo final real en ${b.bank_name}`}
                          className="w-36 px-2.5 py-1 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-right text-xs font-mono text-primary font-bold tabular-nums"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] text-slate-300 mb-1.5">
                    Escribe <code className="text-primary font-mono font-bold">CERRAR-MES</code> para sellar el período:
                  </label>
                  <input
                    type="text"
                    autoComplete="off"
                    aria-label="Confirmación textual CERRAR-MES"
                    enterKeyHint="done"
                    value={closeConfirmText}
                    onChange={(e) => setCloseConfirmText(e.target.value)}
                    placeholder="Escribe CERRAR-MES"
                    className="w-full px-3.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-sm font-mono text-white"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => {
                      setCloseConfirmText("");
                      setShowCloseModal(false);
                    }}
                    className="px-3.5 py-2 rounded-lg bg-surface-container text-xs text-slate-300 cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    disabled={closeConfirmText !== "CERRAR-MES"}
                    onClick={async () => {
                      try {
                        const periodStr = `${year}-${String(month).padStart(2, "0")}`;
                        const savedCfg = await saveAccountingPeriodConfig({
                          year,
                          month,
                          initial_usdt: initialUsdt,
                          initial_usdt_cost_ves: initialUsdtCostVes,
                          initial_banks: bankInitialMap,
                          actual_final_usdt: closeActualUsdt,
                          actual_final_banks: closeActualBanks,
                          mark_closed: true,
                        });
                        setPeriodConfig(savedCfg);
                        const closedRes = await closeFiscalPeriod({
                          period: periodStr,
                          initial_balance: initialUsdt,
                          actual_final_balance: closeActualUsdt,
                        });
                        setFiscalSummary(closedRes);
                        setPeriodClosed(true);
                        setCloseConfirmText("");
                        setShowCloseModal(false);
                        setFeedback({
                          type: "success",
                          text: `Período ${periodStr} sellado (${closedRes.status}). Arqueo real guardado para el Excel/PDF y arrastrado al mes siguiente.`,
                        });
                      } catch (err: any) {
                        setFeedback({
                          type: "error",
                          text: err.message || "Error al persistir el cierre mensual en base de datos.",
                        });
                      }
                    }}
                    className="px-4 py-2 rounded-lg bg-primary-container text-on-primary text-xs font-bold disabled:opacity-40 cursor-pointer"
                  >
                    Confirmar Sello Contable
                  </button>
                </div>
              </div>
            </div>
          );
        })()}

        <StatementImportModal
          isOpen={Boolean(statementPreview)}
          preview={statementPreview}
          sourceFile={statementSourceFile}
          onClose={() => {
            setStatementPreview(null);
            setStatementSourceFile(null);
          }}
          onPreviewUpdated={(updated) => setStatementPreview(updated)}
          onCommitted={async (res: StatementCommitResponse) => {
            setStatementPreview(null);
            setStatementSourceFile(null);
            setFeedback({
              type: "success",
              text: `Estado de cuenta (${res.bank_name}) importado: ${res.created_vouchers} comprobante(s), ${res.matched_orders} conciliado(s) con Binance, ${res.bank_fees_recorded} comisión(es) y ${res.journal_entries_created} asiento(s) en Libro Diario.`,
            });
            await loadAccountingData();
          }}
          onError={(msg: string) =>
            setFeedback({
              type: "error",
              text: msg,
            })
          }
        />
      </div>
    </AppShell>
  );
}
