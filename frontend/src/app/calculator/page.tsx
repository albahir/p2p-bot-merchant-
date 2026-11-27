"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { BankAmountInput } from "@/components/bank-amount-input";
import { BankLogo } from "@/components/bank-logo";
import { BinanceTierBadge } from "@/components/binance-tier-badge";
import { PerspectiveToggle } from "@/components/perspective-toggle";
import { PerspectiveMode, usePerspective } from "@/lib/perspective-context";
import {
  ArbitrageMatrix,
  BCVRates,
  RateQuote,
  VENEZUELAN_BANK_CATALOG,
  getArbitrageMatrix,
  getBCVRates,
  getCachedApiResponse,
} from "@/lib/api";
import {
  BankTransferType,
  CycleDirection,
  DEFAULT_VES_BASE_MAKER_FEE_PCT,
  MERCHANT_TIERS,
  MerchantTier,
  OrderRole,
  calculateP2PCycle,
  compareMerchantTiers,
  computeTargetRateForMargin,
  formatFeePct,
  getMerchantTierConfig,
} from "@/lib/p2p-calculator";

const STORAGE_TIER_KEY = "p2p_calc_merchant_tier";
const STORAGE_CUSTOM_FEE_KEY = "p2p_calc_custom_maker_pct";
const STORAGE_DIRECTION_KEY = "p2p_calc_direction";

function getTierBadgeClasses(tier: MerchantTier, active: boolean): string {
  if (!active) {
    return "bg-surface-container border-[#1e2430] text-slate-400 hover:text-white hover:border-slate-600";
  }
  switch (tier) {
    case "BRONZE":
      return "bg-amber-700/25 border-amber-500/70 text-amber-200 font-bold";
    case "SILVER":
      return "bg-slate-400/20 border-slate-300/70 text-white font-bold";
    case "GOLD":
      return "bg-yellow-500/20 border-yellow-400/80 text-yellow-200 font-bold";
    case "CUSTOM":
      return "bg-secondary/20 border-secondary/70 text-secondary font-bold";
    default:
      return "bg-primary-container/20 border-primary-container text-primary font-bold";
  }
}

function fmtBs(val: number): string {
  return val.toLocaleString("es-VE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function CalculatorContent() {
  const searchParams = useSearchParams();
  const { perspective, setPerspective } = usePerspective();

  const urlRoleParam = searchParams.get("role");
  const initialRole: OrderRole =
    urlRoleParam === "TAKER" || urlRoleParam === "MAKER"
      ? urlRoleParam
      : perspective;

  const [cycleDirection, setCycleDirection] =
    useState<CycleDirection>("USDT_VES_USDT");
  const [capitalUsdt, setCapitalUsdt] = useState<number>(
    Number(searchParams.get("amount")) || 250
  );
  const [buyBank, setBuyBank] = useState<string>(
    searchParams.get("buyBank") || "Banesco"
  );
  const [sellBank, setSellBank] = useState<string>(
    searchParams.get("sellBank") || "Banco de Venezuela"
  );
  const [buyRate, setBuyRate] = useState<number>(
    Number(searchParams.get("buyRate")) || 0
  );
  const [sellRate, setSellRate] = useState<number>(
    Number(searchParams.get("sellRate")) || 0
  );

  const [merchantTier, setMerchantTier] = useState<MerchantTier>("STANDARD");
  const [customMakerFeePct, setCustomMakerFeePct] = useState<number>(
    DEFAULT_VES_BASE_MAKER_FEE_PCT
  );
  const [buyRole, setBuyRole] = useState<OrderRole>(initialRole);
  const [sellRole, setSellRole] = useState<OrderRole>(initialRole);

  const [bankTransferType, setBankTransferType] = useState<BankTransferType>(
    searchParams.get("buyBank") &&
      searchParams.get("sellBank") &&
      searchParams.get("buyBank") === searchParams.get("sellBank")
      ? "SAME_BANK"
      : "INTERBANK_PM"
  );
  const [customBankFeePct, setCustomBankFeePct] = useState<number>(0.3);
  const [splitOrdersCount, setSplitOrdersCount] = useState<number>(1);
  const [minBankFeePerOrderVes, setMinBankFeePerOrderVes] = useState<number>(0);

  const [cyclesPerDay, setCyclesPerDay] = useState<number>(3);
  const [operatingDaysPerMonth, setOperatingDaysPerMonth] = useState<number>(26);
  const [desiredMarginPct, setDesiredMarginPct] = useState<number>(1.0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const savedTier = localStorage.getItem(STORAGE_TIER_KEY) as MerchantTier | null;
    if (savedTier && MERCHANT_TIERS.some((t) => t.id === savedTier)) {
      setMerchantTier(savedTier);
    }
    const savedCustom = Number(localStorage.getItem(STORAGE_CUSTOM_FEE_KEY));
    if (Number.isFinite(savedCustom) && savedCustom >= 0 && savedCustom <= 5) {
      setCustomMakerFeePct(savedCustom);
    }
    const savedDir = localStorage.getItem(STORAGE_DIRECTION_KEY) as CycleDirection | null;
    if (savedDir === "USDT_VES_USDT" || savedDir === "VES_USDT_VES") {
      setCycleDirection(savedDir);
    }
  }, []);

  function handleSelectDirection(dir: CycleDirection) {
    setCycleDirection(dir);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_DIRECTION_KEY, dir);
    }
  }

  function handleSelectTier(nextTier: MerchantTier) {
    setMerchantTier(nextTier);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_TIER_KEY, nextTier);
    }
  }

  function handleChangeCustomFee(rawVal: string) {
    const parsed = Number(rawVal.replace(",", "."));
    const safe = Number.isFinite(parsed) ? Math.min(5, Math.max(0, parsed)) : 0;
    setCustomMakerFeePct(safe);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_CUSTOM_FEE_KEY, String(safe));
    }
  }

  const initialMatrix =
    typeof window !== "undefined"
      ? getCachedApiResponse<ArbitrageMatrix>(
          "/api/spreads/matrix?amount_usdt=100&merchant_only=false"
        )
      : null;
  const initialBcv =
    typeof window !== "undefined"
      ? getCachedApiResponse<BCVRates>("/api/spreads/bcv")
      : null;

  const [quotes, setQuotes] = useState<RateQuote[]>(initialMatrix?.quotes || []);
  const [bcv, setBcv] = useState<BCVRates | null>(initialBcv);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      getArbitrageMatrix(capitalUsdt || 100).catch(() => null),
      getBCVRates().catch(() => null),
    ]).then(([matrixData, bcvData]) => {
      if (!mounted) return;
      if (bcvData) setBcv(bcvData);

      const fallbackRef =
        bcvData?.p2p_usdt_ref && bcvData.p2p_usdt_ref > 0
          ? bcvData.p2p_usdt_ref
          : 0;

      if (matrixData?.quotes?.length) {
        const seen = new Set<string>();
        const deduped = matrixData.quotes.filter((q) => {
          if (seen.has(q.bank_name)) return false;
          seen.add(q.bank_name);
          return true;
        });
        setQuotes(deduped);

        const savedMode =
          urlRoleParam === "TAKER" || urlRoleParam === "MAKER"
            ? urlRoleParam
            : typeof window !== "undefined" &&
              localStorage.getItem("p2p_perspective_mode") === "TAKER"
            ? "TAKER"
            : "MAKER";
        const q0 = deduped[0];
        const q1 = deduped[Math.min(1, deduped.length - 1)];
        const defaultBuy =
          savedMode === "MAKER" ? q0.buy_rate : q0.sell_rate || fallbackRef;
        const defaultSell =
          savedMode === "MAKER" ? q1.sell_rate : q1.buy_rate || fallbackRef;

        setBuyRate((prev) => (prev > 0 ? prev : defaultBuy));
        setSellRate((prev) => (prev > 0 ? prev : defaultSell));
      } else if (fallbackRef > 0) {
        setBuyRate((prev) => (prev > 0 ? prev : fallbackRef));
        setSellRate((prev) => (prev > 0 ? prev : Number((fallbackRef * 1.008).toFixed(2))));
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (urlRoleParam === "TAKER" || urlRoleParam === "MAKER") {
      setPerspective(urlRoleParam);
      return;
    }
    setBuyRole(perspective);
    setSellRole(perspective);
  }, [perspective, urlRoleParam, setPerspective]);

  function handleSwitchGlobalPerspective(nextMode: PerspectiveMode) {
    setBuyRole(nextMode);
    setSellRole(nextMode);
    const foundBuy = quotes.find((q) => q.bank_name === buyBank);
    if (foundBuy) {
      const nextBuyR = nextMode === "MAKER" ? foundBuy.buy_rate : foundBuy.sell_rate;
      if (nextBuyR > 0) setBuyRate(nextBuyR);
    }
    const foundSell = quotes.find((q) => q.bank_name === sellBank);
    if (foundSell) {
      const nextSellR = nextMode === "MAKER" ? foundSell.sell_rate : foundSell.buy_rate;
      if (nextSellR > 0) setSellRate(nextSellR);
    }
  }

  function handleChangeBuyLegRole(nextRole: OrderRole) {
    setBuyRole(nextRole);
    const found = quotes.find((q) => q.bank_name === buyBank);
    if (found) {
      const rate = nextRole === "MAKER" ? found.buy_rate : found.sell_rate;
      if (rate > 0) setBuyRate(rate);
    }
  }

  function handleChangeSellLegRole(nextRole: OrderRole) {
    setSellRole(nextRole);
    const found = quotes.find((q) => q.bank_name === sellBank);
    if (found) {
      const rate = nextRole === "MAKER" ? found.sell_rate : found.buy_rate;
      if (rate > 0) setSellRate(rate);
    }
  }

  function handleSelectBuyBank(name: string) {
    setBuyBank(name);
    const found = quotes.find((q) => q.bank_name === name);
    if (found) {
      const rate = buyRole === "MAKER" ? found.buy_rate : found.sell_rate;
      if (rate > 0) setBuyRate(rate);
    }
    setBankTransferType(name === sellBank ? "SAME_BANK" : "INTERBANK_PM");
  }

  function handleSelectSellBank(name: string) {
    setSellBank(name);
    const found = quotes.find((q) => q.bank_name === name);
    if (found) {
      const rate = sellRole === "MAKER" ? found.sell_rate : found.buy_rate;
      if (rate > 0) setSellRate(rate);
    }
    setBankTransferType(buyBank === name ? "SAME_BANK" : "INTERBANK_PM");
  }

  const bankSelectList = useMemo(() => {
    if (quotes.length > 0) {
      const names = quotes.map((q) => q.bank_name);
      for (const fallback of [buyBank, sellBank]) {
        if (fallback && !names.includes(fallback)) names.push(fallback);
      }
      return names;
    }
    return [...VENEZUELAN_BANK_CATALOG];
  }, [quotes, buyBank, sellBank]);

  const refP2pRate = bcv?.p2p_usdt_ref && bcv.p2p_usdt_ref > 0 ? bcv.p2p_usdt_ref : 0;

  const simulationInput = useMemo(
    () => ({
      capitalUsdt,
      buyRate,
      sellRate,
      buyRole,
      sellRole,
      cycleDirection,
      bankTransferType,
      customBankFeePct,
      splitOrdersCount,
      minBankFeePerOrderVes,
      merchantTier,
      baseMakerFeePct: DEFAULT_VES_BASE_MAKER_FEE_PCT,
      customMakerFeePct,
      cyclesPerDay,
      operatingDaysPerMonth,
      refP2pRate,
    }),
    [
      capitalUsdt,
      buyRate,
      sellRate,
      buyRole,
      sellRole,
      cycleDirection,
      bankTransferType,
      customBankFeePct,
      splitOrdersCount,
      minBankFeePerOrderVes,
      merchantTier,
      customMakerFeePct,
      cyclesPerDay,
      operatingDaysPerMonth,
      refP2pRate,
    ]
  );

  const simulation = useMemo(
    () => calculateP2PCycle(simulationInput),
    [simulationInput]
  );

  const tierComparison = useMemo(
    () => compareMerchantTiers(simulationInput),
    [simulationInput]
  );

  const targetRateSolveFor = cycleDirection === "USDT_VES_USDT" ? "BUY" : "SELL";
  const targetRateValue = useMemo(
    () => computeTargetRateForMargin(simulationInput, desiredMarginPct, targetRateSolveFor),
    [simulationInput, desiredMarginPct, targetRateSolveFor]
  );

  const activeTierConfig = getMerchantTierConfig(merchantTier);
  const formattedMakerFee = formatFeePct(simulation.effectiveMakerFeePct);
  const isUsdCycle = cycleDirection === "USDT_VES_USDT";
  const isDifferentBankMultiCycle = buyBank !== sellBank && cyclesPerDay > 1;

  const statusBadge =
    simulation.profitStatus === "INCOMPLETE"
      ? { label: "INGRESA TASAS", cls: "bg-slate-800 text-slate-300 border-slate-700" }
      : simulation.profitStatus === "LOSS"
      ? { label: "EN PÉRDIDA", cls: "bg-error/15 text-error border-error/40" }
      : simulation.profitStatus === "MARGINAL"
      ? { label: "MUY JUSTO (<0,30%)", cls: "bg-amber-500/15 text-amber-300 border-amber-500/40" }
      : { label: "RENTABLE", cls: "bg-tertiary/15 text-tertiary border-tertiary/40" };

  return (
    <AppShell
      title="Calculadora de ciclos"
      badge={
        buyRole === sellRole
          ? buyRole === "MAKER"
            ? "MODO MAKER"
            : "MODO TAKER"
          : "MODO HÍBRIDO"
      }
      subtitle={
        isUsdCycle
          ? "Ciclo USDT → Bs → USDT: vendes USDT, recibes Bs (0% banco) y recompras protegiendo tu capital en cripto."
          : "Ciclo Bs → USDT → Bs: inviertes bolívares (pagando comisión al enviar) y liquidas de vuelta a Bs."
      }
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <PerspectiveToggle onSelectMode={handleSwitchGlobalPerspective} />
          <Link
            href="/"
            className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-primary-container/50 text-xs font-mono text-slate-200 flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-[16px] text-primary">
              grid_view
            </span>
            <span>Volver a matriz</span>
          </Link>
        </div>
      }
    >
      <div className="space-y-5">
        {/* Aviso si falta tasa real (nunca sustituye por 0,01) */}
        {!simulation.hasValidRates && (
          <div
            role="status"
            className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/35 flex flex-wrap items-center justify-between gap-3 text-xs text-amber-200"
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-amber-400">
                info
              </span>
              <span>
                Introduce una <strong>Tasa Compra</strong> y una <strong>Tasa Venta</strong> válidas (mayores a Bs. 0,00) para calcular tu punto de equilibrio y ganancia real.
              </span>
            </div>
            {refP2pRate > 0 && (
              <button
                type="button"
                onClick={() => {
                  if (buyRate <= 0) setBuyRate(refP2pRate);
                  if (sellRate <= 0) setSellRate(Number((refP2pRate * 1.008).toFixed(2)));
                }}
                className="px-3 py-1 rounded-lg bg-primary-container text-on-primary font-mono text-[11px] font-bold cursor-pointer"
              >
                Usar ref. P2P (Bs. {refP2pRate.toFixed(2)})
              </button>
            )}
          </div>
        )}

        {/* Alerta de Riesgo Cambiario cuando hay tasas reales y el resultado es pérdida */}
        {simulation.hasValidRates && simulation.profitStatus === "LOSS" && (
          <div
            role="alert"
            aria-live="polite"
            className="p-3.5 rounded-xl bg-error/15 border border-error/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
          >
            <div className="flex items-start sm:items-center gap-2.5">
              <span className="material-symbols-outlined text-[20px] text-error shrink-0">
                warning
              </span>
              <div>
                <div className="font-bold text-white">
                  Alerta — Ciclo en Pérdida ({simulation.netRoiPct.toFixed(2)}% ROI)
                </div>
                <div className="text-slate-300 mt-0.5">
                  {isUsdCycle ? (
                    <>
                      Tu recompra (<span className="font-mono text-error font-semibold">Bs. {buyRate.toFixed(2)}</span>) supera tu límite máximo de equilibrio (<span className="font-mono text-primary font-semibold">Bs. {simulation.breakEvenRate.toFixed(2)}</span>), perdiendo <span className="font-mono text-error font-semibold">{Math.abs(simulation.netProfitUsdt).toFixed(2)} USDT</span>.
                    </>
                  ) : (
                    <>
                      Tu venta (<span className="font-mono text-error font-semibold">Bs. {sellRate.toFixed(2)}</span>) está debajo del equilibrio (<span className="font-mono text-primary font-semibold">Bs. {simulation.breakEvenRate.toFixed(2)}</span>), perdiendo <span className="font-mono text-error font-semibold">Bs. {fmtBs(Math.abs(simulation.netProfitVes))}</span>.
                    </>
                  )}
                </div>
              </div>
            </div>
            {targetRateValue > 0 && (
              <button
                type="button"
                onClick={() =>
                  isUsdCycle ? setBuyRate(targetRateValue) : setSellRate(targetRateValue)
                }
                className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary font-mono text-[11px] font-bold hover:brightness-110 transition-all shrink-0 cursor-pointer"
              >
                Ajustar a +{desiredMarginPct.toFixed(1)}% (Bs. {targetRateValue.toFixed(2)})
              </button>
            )}
          </div>
        )}

        {/* 4 KPIs Principales (sin distorsión BCV ni errores por 0,00) */}
        <section className="grid grid-cols-2 xl:grid-cols-4 gap-2.5 sm:gap-3">
          {/* KPI 1 */}
          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span className="truncate">
                {isUsdCycle ? "Bolívares Generados" : "Capital Requerido"}
              </span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-secondary shrink-0">
                account_balance_wallet
              </span>
            </div>
            <div className="mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold text-white tabular-nums truncate">
              {simulation.hasValidRates
                ? `Bs. ${fmtBs(simulation.totalVesInvested)}`
                : "—"}
            </div>
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 tabular-nums leading-tight truncate">
              {simulation.hasValidRates
                ? `Base: ${capitalUsdt} USDT • Com. envío: Bs. ${fmtBs(simulation.bankFeeVes)}`
                : `Lote base: ${capitalUsdt} USDT`}
            </div>
          </div>

          {/* KPI 2 */}
          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span className="truncate">
                {isUsdCycle ? "Máx. Recompra (0%)" : "Tasa Equilibrio (0%)"}
              </span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-primary shrink-0">
                balance
              </span>
            </div>
            <div className="mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold text-primary tabular-nums truncate">
              {simulation.hasValidRates && simulation.breakEvenRate > 0
                ? `Bs. ${simulation.breakEvenRate.toFixed(2)}`
                : "—"}
            </div>
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 tabular-nums truncate">
              {simulation.hasValidRates
                ? isUsdCycle
                  ? `Recompra actual: Bs. ${buyRate.toFixed(2)}`
                  : `Venta actual: Bs. ${sellRate.toFixed(2)}`
                : "Sin tasa activa"}
            </div>
          </div>

          {/* KPI 3: Ganancia Neta por Ciclo */}
          <div className="p-3 sm:p-4 rounded-xl bg-surface-container border border-primary-container/30 min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-primary">
              <span className="truncate">Ganancia por Ciclo</span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-tertiary shrink-0">
                paid
              </span>
            </div>
            <div
              className={`mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold tabular-nums truncate ${
                !simulation.hasValidRates
                  ? "text-slate-400"
                  : simulation.netProfitUsdt > 0
                  ? "text-tertiary"
                  : "text-error"
              }`}
            >
              {simulation.hasValidRates
                ? `${simulation.netProfitUsdt >= 0 ? "+" : ""}${simulation.netProfitUsdt.toFixed(2)} USDT`
                : "—"}
            </div>
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-300 tabular-nums truncate">
              {simulation.hasValidRates
                ? `${simulation.netProfitVes >= 0 ? "+" : ""}Bs. ${fmtBs(simulation.netProfitVes)}`
                : isUsdCycle
                ? "Cierra en USDT reales"
                : "Cierra en Bs"}
            </div>
          </div>

          {/* KPI 4: Retorno Neto Real (sin distorsión BCV) */}
          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span className="truncate">Retorno Neto Real</span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-tertiary shrink-0">
                monitoring
              </span>
            </div>
            <div
              className={`mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold tabular-nums truncate ${
                !simulation.hasValidRates
                  ? "text-slate-400"
                  : simulation.profitStatus === "PROFITABLE"
                  ? "text-tertiary"
                  : simulation.profitStatus === "MARGINAL"
                  ? "text-amber-300"
                  : "text-error"
              }`}
            >
              {simulation.hasValidRates
                ? `${simulation.netRoiPct >= 0 ? "+" : ""}${simulation.netRoiPct.toFixed(2)}%`
                : "—"}
            </div>
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 tabular-nums truncate">
              {simulation.hasValidRates
                ? `Spread neto real • ${cyclesPerDay} ${cyclesPerDay === 1 ? "ciclo" : "ciclos"}/día`
                : "Completa las tasas"}
            </div>
          </div>
        </section>

        {/* Grilla Principal */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Panel Izquierdo: Parámetros de Ejecución */}
          <section className="lg:col-span-5 p-4 sm:p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-4">
            <div className="flex items-center justify-between gap-2 border-b border-[#1e2430] pb-3 flex-wrap">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-primary">
                  tune
                </span>
                Parámetros
              </h2>

              {/* Dirección del ciclo: USDT -> Bs -> USDT vs Bs -> USDT -> Bs */}
              <div
                role="group"
                aria-label="Dirección del ciclo comercial"
                className="p-0.5 rounded-lg bg-surface-container border border-[#1e2430] flex items-center text-[10px] font-mono"
              >
                <button
                  type="button"
                  aria-pressed={isUsdCycle}
                  onClick={() => handleSelectDirection("USDT_VES_USDT")}
                  className={`px-2 py-1 rounded-md transition-colors cursor-pointer whitespace-nowrap ${
                    isUsdCycle
                      ? "bg-tertiary text-on-tertiary font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  USDT → Bs → USDT
                </button>
                <button
                  type="button"
                  aria-pressed={!isUsdCycle}
                  onClick={() => handleSelectDirection("VES_USDT_VES")}
                  className={`px-2 py-1 rounded-md transition-colors cursor-pointer whitespace-nowrap ${
                    !isUsdCycle
                      ? "bg-primary-container text-on-primary font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Bs → USDT → Bs
                </button>
              </div>
            </div>

            {/* Volumen del Ciclo */}
            <div>
              <label
                htmlFor="calc-capital-usdt"
                className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
              >
                {isUsdCycle ? "Capital Inicial (USDT)" : "Lote a Operar (USDT)"}
              </label>
              <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                <BankAmountInput
                  id="calc-capital-usdt"
                  value={capitalUsdt}
                  onChange={setCapitalUsdt}
                  ariaLabel="Monto Operativo por Ciclo (USDT)"
                  className="w-full sm:flex-1 min-w-0 px-3.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm font-mono font-bold text-white tabular-nums"
                />
                <div className="grid grid-cols-4 sm:flex items-center gap-1.5 shrink-0">
                  {[100, 250, 500, 1000].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setCapitalUsdt(preset)}
                      className={`px-2 py-2 rounded-lg text-xs font-mono border text-center transition-colors cursor-pointer ${
                        capitalUsdt === preset
                          ? "bg-primary-container text-on-primary font-bold border-primary-container"
                          : "bg-surface-container border-[#1e2430] text-slate-300 hover:text-white"
                      }`}
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Nivel de Comerciante Binance P2P (Con nombres claros debajo de cada escudo; base oficial VES 0,25%) */}
            <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-2.5">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <label className="text-[11px] font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[15px] text-primary">
                    workspace_premium
                  </span>
                  Nivel Comerciante Binance (VES)
                </label>
                <span className="text-[10px] font-mono text-primary font-semibold">
                  Maker: {formattedMakerFee} • Taker: 0%
                </span>
              </div>

              <div className="grid grid-cols-5 gap-1.5">
                {MERCHANT_TIERS.map((tier) => {
                  const active = merchantTier === tier.id;
                  return (
                    <button
                      key={tier.id}
                      type="button"
                      onClick={() => handleSelectTier(tier.id)}
                      title={`${tier.label} — ${tier.requirementHint}`}
                      aria-label={`${tier.label}: ${tier.requirementHint}`}
                      aria-pressed={active}
                      className={`py-2 px-1 rounded-lg border flex flex-col items-center justify-center gap-1 transition-all cursor-pointer ${getTierBadgeClasses(
                        tier.id,
                        active
                      )}`}
                    >
                      <BinanceTierBadge tier={tier.id} size={22} />
                      <span className="text-[9px] font-sans font-semibold leading-none truncate max-w-full">
                        {tier.shortLabel}
                      </span>
                      <span className="text-[9px] font-mono leading-none opacity-85">
                        {tier.id === "CUSTOM"
                          ? "%"
                          : tier.discountPct > 0
                          ? `-${tier.discountPct}%`
                          : "0%"}
                      </span>
                    </button>
                  );
                })}
              </div>

              {merchantTier === "CUSTOM" ? (
                <div className="flex items-center justify-between gap-2 pt-1">
                  <label
                    htmlFor="calc-custom-maker-fee"
                    className="text-[11px] text-slate-400"
                  >
                    Comisión Maker exacta (%):
                  </label>
                  <div className="flex items-center gap-1.5">
                    <input
                      id="calc-custom-maker-fee"
                      type="number"
                      min={0}
                      max={5}
                      step={0.005}
                      value={customMakerFeePct}
                      onChange={(e) => handleChangeCustomFee(e.target.value)}
                      className="w-24 px-2.5 py-1 rounded-md bg-surface-container-lowest border border-[#1e2430] focus:border-secondary focus:outline-hidden text-xs font-mono font-bold text-white text-right tabular-nums"
                    />
                    <span className="text-xs font-mono text-slate-400">%</span>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-2 text-[10px] font-mono text-slate-400 pt-0.5">
                  <span>{activeTierConfig.requirementHint}</span>
                  <span>Comisión estándar: 0,25%</span>
                </div>
              )}
            </div>

            {/* Pierna de VENTA USDT (Recibir Bs = 0% comisión bancaria) */}
            <div
              className={`p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-3 ${
                isUsdCycle ? "" : "order-last"
              }`}
            >
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="text-xs font-bold text-white">
                  {isUsdCycle ? "1. Venta USDT (Recibes Bs)" : "2. Salida / Venta USDT (Recibes Bs)"}
                </span>
                <div className="flex rounded-md bg-surface-container-lowest p-0.5 border border-[#1e2430] text-[10px] font-mono shrink-0">
                  <button
                    type="button"
                    onClick={() => handleChangeSellLegRole("MAKER")}
                    className={`px-2 py-0.5 rounded cursor-pointer ${
                      sellRole === "MAKER"
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Publicar ({formattedMakerFee})
                  </button>
                  <button
                    type="button"
                    onClick={() => handleChangeSellLegRole("TAKER")}
                    className={`px-2 py-0.5 rounded cursor-pointer ${
                      sellRole === "TAKER"
                        ? "bg-tertiary text-on-tertiary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Tomar (0%)
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label
                    htmlFor="calc-sell-bank"
                    className="block text-[10px] font-mono text-slate-400 mb-1"
                  >
                    Banco donde recibes Bs
                  </label>
                  <div className="flex items-center gap-2">
                    <BankLogo bankName={sellBank} size={28} />
                    <select
                      id="calc-sell-bank"
                      value={sellBank}
                      onChange={(e) => handleSelectSellBank(e.target.value)}
                      className="flex-1 min-w-0 px-2.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs text-white focus:border-primary-container focus:outline-hidden"
                    >
                      {bankSelectList.map((b) => (
                        <option key={`sell-${b}`} value={b}>
                          {b}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label
                    htmlFor="calc-sell-rate"
                    className="block text-[10px] font-mono text-slate-400 mb-1"
                  >
                    Tasa Venta (Bs/USDT)
                  </label>
                  <BankAmountInput
                    id="calc-sell-rate"
                    value={sellRate}
                    onChange={setSellRate}
                    ariaLabel="Tasa Venta (Bs/USDT)"
                    className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono font-bold text-primary tabular-nums focus:border-primary-container focus:outline-hidden"
                  />
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-[10px] font-mono text-tertiary bg-tertiary/10 border border-tertiary/25 rounded-md px-2.5 py-1">
                <span className="material-symbols-outlined text-[14px]">check_circle</span>
                <span>Recibir Bs al vender USDT cuesta 0% de comisión bancaria.</span>
              </div>
            </div>

            {/* Pierna de COMPRA / RECOMPRA USDT (Aquí es donde TÚ envías Bs -> aplica comisión bancaria) */}
            <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-3">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="text-xs font-bold text-white">
                  {isUsdCycle ? "2. Recompra USDT (Envías Bs)" : "1. Entrada / Compra USDT (Envías Bs)"}
                </span>
                <div className="flex rounded-md bg-surface-container-lowest p-0.5 border border-[#1e2430] text-[10px] font-mono shrink-0">
                  <button
                    type="button"
                    onClick={() => handleChangeBuyLegRole("MAKER")}
                    className={`px-2 py-0.5 rounded cursor-pointer ${
                      buyRole === "MAKER"
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Publicar ({formattedMakerFee})
                  </button>
                  <button
                    type="button"
                    onClick={() => handleChangeBuyLegRole("TAKER")}
                    className={`px-2 py-0.5 rounded cursor-pointer ${
                      buyRole === "TAKER"
                        ? "bg-tertiary text-on-tertiary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Tomar (0%)
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label
                    htmlFor="calc-buy-bank"
                    className="block text-[10px] font-mono text-slate-400 mb-1"
                  >
                    Banco desde donde envías Bs
                  </label>
                  <div className="flex items-center gap-2">
                    <BankLogo bankName={buyBank} size={28} />
                    <select
                      id="calc-buy-bank"
                      value={buyBank}
                      onChange={(e) => handleSelectBuyBank(e.target.value)}
                      className="flex-1 min-w-0 px-2.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs text-white focus:border-primary-container focus:outline-hidden"
                    >
                      {bankSelectList.map((b) => (
                        <option key={`buy-${b}`} value={b}>
                          {b}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label
                    htmlFor="calc-buy-rate"
                    className="block text-[10px] font-mono text-slate-400 mb-1"
                  >
                    Tasa Compra (Bs/USDT)
                  </label>
                  <BankAmountInput
                    id="calc-buy-rate"
                    value={buyRate}
                    onChange={setBuyRate}
                    ariaLabel="Tasa Compra (Bs/USDT)"
                    className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono font-bold text-white tabular-nums focus:border-primary-container focus:outline-hidden"
                  />
                </div>
              </div>

              {/* Comisión bancaria ubicada dentro de la compra (envío de Bs) */}
              <div className="pt-2 border-t border-[#1e2430] space-y-2">
                <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  Comisión bancaria al enviar Bs
                </label>
                <div className="grid grid-cols-3 gap-1.5">
                  <button
                    type="button"
                    onClick={() => setBankTransferType("SAME_BANK")}
                    className={`p-2 rounded-lg border text-center transition-all cursor-pointer ${
                      bankTransferType === "SAME_BANK"
                        ? "bg-tertiary/15 border-tertiary text-white"
                        : "bg-surface-container-lowest border-[#1e2430] text-slate-400 hover:text-white"
                    }`}
                  >
                    <div className="text-[11px] font-mono font-bold">0% Mismo</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setBankTransferType("INTERBANK_PM")}
                    className={`p-2 rounded-lg border text-center transition-all cursor-pointer ${
                      bankTransferType === "INTERBANK_PM"
                        ? "bg-primary-container/15 border-primary-container text-white"
                        : "bg-surface-container-lowest border-[#1e2430] text-slate-400 hover:text-white"
                    }`}
                  >
                    <div className="text-[11px] font-mono font-bold">0,30% PM</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setBankTransferType("CUSTOM")}
                    className={`p-2 rounded-lg border text-center transition-all cursor-pointer ${
                      bankTransferType === "CUSTOM"
                        ? "bg-secondary/15 border-secondary text-white"
                        : "bg-surface-container-lowest border-[#1e2430] text-slate-400 hover:text-white"
                    }`}
                  >
                    <div className="text-[11px] font-mono font-bold">Manual</div>
                  </button>
                </div>

                {bankTransferType === "CUSTOM" && (
                  <div className="grid grid-cols-3 gap-2 pt-1 text-[10px] font-mono">
                    <div>
                      <span className="text-slate-400 block mb-0.5">% Comisión</span>
                      <input
                        type="number"
                        min={0}
                        max={5}
                        step={0.05}
                        value={customBankFeePct}
                        onChange={(e) => setCustomBankFeePct(Number(e.target.value) || 0)}
                        className="w-full px-2 py-1 rounded bg-surface-container-lowest border border-[#1e2430] text-white text-right tabular-nums"
                      />
                    </div>
                    <div>
                      <span className="text-slate-400 block mb-0.5">N° órdenes</span>
                      <input
                        type="number"
                        min={1}
                        max={50}
                        value={splitOrdersCount}
                        onChange={(e) =>
                          setSplitOrdersCount(Math.max(1, Math.round(Number(e.target.value) || 1)))
                        }
                        className="w-full px-2 py-1 rounded bg-surface-container-lowest border border-[#1e2430] text-white text-right tabular-nums"
                      />
                    </div>
                    <div>
                      <span className="text-slate-400 block mb-0.5">Mín. Bs/ord</span>
                      <input
                        type="number"
                        min={0}
                        step={1}
                        value={minBankFeePerOrderVes}
                        onChange={(e) => setMinBankFeePerOrderVes(Math.max(0, Number(e.target.value) || 0))}
                        className="w-full px-2 py-1 rounded bg-surface-container-lowest border border-[#1e2430] text-white text-right tabular-nums"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* Panel Derecho */}
          <section className="lg:col-span-7 space-y-5">
            {/* Resumen del ciclo */}
            <div className="p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-4">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="material-symbols-outlined text-[18px] text-secondary">
                    schema
                  </span>
                  Resumen del ciclo ({isUsdCycle ? "USDT → Bs → USDT" : "Bs → USDT → Bs"})
                </h2>
                <span
                  className={`px-2.5 py-0.5 rounded border text-[10px] font-mono font-bold ${statusBadge.cls}`}
                >
                  {statusBadge.label}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {isUsdCycle ? (
                  <>
                    {/* Paso 1: Venta USDT -> Bs */}
                    <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                      <div className="text-[10px] font-mono uppercase text-primary font-bold">
                        Paso 1 • Venta P2P
                      </div>
                      <div className="text-xs font-semibold text-white mt-1 flex items-center gap-1.5">
                        <BankLogo bankName={sellBank} size={18} />
                        <span className="truncate">USDT → {sellBank}</span>
                      </div>
                      <div className="mt-2 pt-2 border-t border-[#1e2430] space-y-1 text-[11px] font-mono tabular-nums">
                        <div className="flex justify-between text-slate-400">
                          <span>Bs recibidos:</span>
                          <span className="text-white">
                            {simulation.hasValidRates ? `Bs. ${fmtBs(simulation.vesReceivedOnSell)}` : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Banco (recibir):</span>
                          <span className="text-tertiary">0% (Bs. 0,00)</span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Com. Binance:</span>
                          <span>
                            {simulation.hasValidRates ? `-${simulation.sellFeeUsdt.toFixed(3)} U` : "—"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Paso 2: Capital en Banco */}
                    <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                      <div className="text-[10px] font-mono uppercase text-secondary font-bold">
                        Paso 2 • En Banco
                      </div>
                      <div className="text-xs font-semibold text-white mt-1 truncate">
                        Bolívares Disponibles
                      </div>
                      <div className="mt-2 pt-2 border-t border-[#1e2430] space-y-1 text-[11px] font-mono tabular-nums">
                        <div className="flex justify-between text-slate-400">
                          <span>Saldo banco:</span>
                          <span className="text-white font-bold">
                            {simulation.hasValidRates ? `Bs. ${fmtBs(simulation.vesReceivedOnSell)}` : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Máx. recompra:</span>
                          <span className="text-primary">
                            {simulation.hasValidRates ? `Bs. ${simulation.breakEvenRate.toFixed(2)}` : "—"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Paso 3: Recompra USDT */}
                    <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                      <div className="text-[10px] font-mono uppercase text-tertiary font-bold">
                        Paso 3 • Recompra P2P
                      </div>
                      <div className="text-xs font-semibold text-white mt-1 flex items-center gap-1.5">
                        <BankLogo bankName={buyBank} size={18} />
                        <span className="truncate">{buyBank} → USDT</span>
                      </div>
                      <div className="mt-2 pt-2 border-t border-[#1e2430] space-y-1 text-[11px] font-mono tabular-nums">
                        <div className="flex justify-between text-slate-400">
                          <span>Banco (enviar):</span>
                          <span className="text-amber-300">
                            {simulation.hasValidRates ? `-Bs. ${fmtBs(simulation.bankFeeVes)}` : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>USDT finales:</span>
                          <span className="text-white">
                            {simulation.hasValidRates ? `${simulation.finalUsdtOut.toFixed(2)} U` : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Utilidad neta:</span>
                          <span
                            className={`font-bold ${
                              !simulation.hasValidRates
                                ? "text-slate-400"
                                : simulation.netProfitUsdt > 0
                                ? "text-tertiary"
                                : "text-error"
                            }`}
                          >
                            {simulation.hasValidRates
                              ? `${simulation.netProfitUsdt >= 0 ? "+" : ""}${simulation.netProfitUsdt.toFixed(2)} U`
                              : "—"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    {/* Paso 1: Compra P2P */}
                    <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                      <div className="text-[10px] font-mono uppercase text-secondary font-bold">
                        Paso 1 • Compra P2P
                      </div>
                      <div className="text-xs font-semibold text-white mt-1 flex items-center gap-1.5">
                        <BankLogo bankName={buyBank} size={18} />
                        <span className="truncate">{buyBank} → USDT</span>
                      </div>
                      <div className="mt-2 pt-2 border-t border-[#1e2430] space-y-1 text-[11px] font-mono tabular-nums">
                        <div className="flex justify-between text-slate-400">
                          <span>Inversión total:</span>
                          <span className="text-white">
                            {simulation.hasValidRates ? `Bs. ${fmtBs(simulation.totalVesInvested)}` : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Banco (enviar):</span>
                          <span className="text-amber-300">
                            {simulation.hasValidRates ? `Bs. ${fmtBs(simulation.bankFeeVes)}` : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Com. Binance:</span>
                          <span>
                            {simulation.hasValidRates ? `-${simulation.buyFeeUsdt.toFixed(3)} U` : "—"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Paso 2: Inventario Neto */}
                    <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                      <div className="text-[10px] font-mono uppercase text-primary font-bold">
                        Paso 2 • Inventario Neto
                      </div>
                      <div className="text-xs font-semibold text-white mt-1 truncate">
                        Billetera Binance Fondos
                      </div>
                      <div className="mt-2 pt-2 border-t border-[#1e2430] space-y-1 text-[11px] font-mono tabular-nums">
                        <div className="flex justify-between text-slate-400">
                          <span>USDT netos:</span>
                          <span className="text-primary font-bold">
                            {simulation.hasValidRates ? `${simulation.usdtAfterBuyFee.toFixed(3)} U` : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Mín. venta:</span>
                          <span>
                            {simulation.hasValidRates ? `Bs. ${simulation.breakEvenRate.toFixed(2)}` : "—"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Paso 3: Liquidación P2P */}
                    <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                      <div className="text-[10px] font-mono uppercase text-tertiary font-bold">
                        Paso 3 • Liquidación P2P
                      </div>
                      <div className="text-xs font-semibold text-white mt-1 flex items-center gap-1.5">
                        <BankLogo bankName={sellBank} size={18} />
                        <span className="truncate">USDT → {sellBank}</span>
                      </div>
                      <div className="mt-2 pt-2 border-t border-[#1e2430] space-y-1 text-[11px] font-mono tabular-nums">
                        <div className="flex justify-between text-slate-400">
                          <span>Retorno VES:</span>
                          <span className="text-white">
                            {simulation.hasValidRates ? `Bs. ${fmtBs(simulation.grossVesOut)}` : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Banco (recibir):</span>
                          <span className="text-tertiary">0%</span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Utilidad neta:</span>
                          <span
                            className={`font-bold ${
                              !simulation.hasValidRates
                                ? "text-slate-400"
                                : simulation.netProfitVes > 0
                                ? "text-tertiary"
                                : "text-error"
                            }`}
                          >
                            {simulation.hasValidRates
                              ? `${simulation.netProfitUsdt >= 0 ? "+" : ""}${simulation.netProfitUsdt.toFixed(2)} U`
                              : "—"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Resumen de Comisiones Binance valoradas a tasa real (no promedio con 0,01) */}
              <div className="px-3.5 py-2.5 rounded-xl bg-surface-container border border-[#1e2430] flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] font-mono tabular-nums">
                <div className="flex items-center gap-2 text-slate-300 flex-wrap">
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container-high border border-[#283140] text-[10px] text-white font-semibold">
                    <BinanceTierBadge tier={merchantTier} size={15} />
                    <span>{formattedMakerFee}</span>
                  </span>
                  <span>
                    Comisión Binance:{" "}
                    <strong className="text-primary">
                      {simulation.hasValidRates
                        ? `${simulation.totalBinanceFeeUsdt.toFixed(3)} USDT`
                        : "—"}
                    </strong>{" "}
                    {simulation.hasValidRates && (
                      <span className="text-slate-400">
                        (≈ Bs. {fmtBs(simulation.totalBinanceFeeVes)})
                      </span>
                    )}
                  </span>
                </div>
                {simulation.hasValidRates && simulation.vipSavingsUsdt > 0.0005 && (
                  <span className="text-tertiary font-semibold">
                    Ahorro VIP: +{simulation.vipSavingsUsdt.toFixed(3)} USDT/ciclo
                  </span>
                )}
              </div>

              {/* Calculador Inverso: "¿A qué tasa publicar para ganar X% neto?" */}
              <div className="p-3.5 rounded-xl bg-surface-container-lowest border border-primary-container/25 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="text-xs font-bold text-white flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[16px] text-primary">
                      ads_click
                    </span>
                    Calculador Inverso: Quiero ganar{" "}
                    <span className="text-primary font-mono">{desiredMarginPct.toFixed(2)}%</span> neto
                  </div>
                  <div className="text-[11px] font-mono text-slate-300">
                    {targetRateValue > 0 ? (
                      isUsdCycle ? (
                        <>
                          Publica tu anuncio de <strong>recompra</strong> a:{" "}
                          <strong className="text-tertiary">Bs. {targetRateValue.toFixed(2)}</strong>
                        </>
                      ) : (
                        <>
                          Publica tu anuncio de <strong>venta</strong> a:{" "}
                          <strong className="text-tertiary">Bs. {targetRateValue.toFixed(2)}</strong>
                        </>
                      )
                    ) : (
                      "Ingresa la tasa base de la otra pierna para calcular tu tasa objetivo."
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1.5 flex-wrap shrink-0">
                  {[0.5, 1.0, 1.5, 2.0].map((mPct) => (
                    <button
                      key={mPct}
                      type="button"
                      onClick={() => setDesiredMarginPct(mPct)}
                      className={`px-2 py-1 rounded text-[10px] font-mono border cursor-pointer transition-colors ${
                        desiredMarginPct === mPct
                          ? "bg-primary-container text-on-primary font-bold border-primary-container"
                          : "bg-surface-container border-[#1e2430] text-slate-300 hover:text-white"
                      }`}
                    >
                      +{mPct}%
                    </button>
                  ))}
                  {targetRateValue > 0 && (
                    <button
                      type="button"
                      onClick={() =>
                        isUsdCycle ? setBuyRate(targetRateValue) : setSellRate(targetRateValue)
                      }
                      className="px-2.5 py-1 rounded bg-tertiary text-on-tertiary text-[10px] font-mono font-bold hover:brightness-110 cursor-pointer"
                    >
                      Aplicar
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Comparativa en Vivo por Nivel VIP (compacta en móvil sin desbordes ni saltos de línea) */}
            <div className="p-4 sm:p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-3">
              <div>
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="material-symbols-outlined text-[18px] text-primary">
                    military_tech
                  </span>
                  Impacto por Nivel de Comerciante
                </h2>
                <p className="text-xs text-slate-400">
                  Toca cualquier nivel para aplicarlo (base Maker VES 0,25%).
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs font-mono tabular-nums">
                  <thead>
                    <tr className="border-b border-[#1e2430] text-[10px] uppercase tracking-wider text-slate-400 whitespace-nowrap">
                      <th scope="col" className="py-2 pr-2">Nivel</th>
                      <th scope="col" className="py-2 px-1.5 text-right">Fee</th>
                      <th scope="col" className="py-2 px-1.5 text-right">Equilibrio</th>
                      <th scope="col" className="py-2 px-1.5 text-right">Gan./Ciclo</th>
                      <th scope="col" className="py-2 pl-2 text-right hidden sm:table-cell">
                        Mes ({operatingDaysPerMonth}d)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1e2430]/70 whitespace-nowrap">
                    {tierComparison.map(({ tier, config, result }) => {
                      const isSelected = merchantTier === tier;
                      const rowProfit = result.hasValidRates && result.netProfitUsdt > 0;
                      return (
                        <tr
                          key={tier}
                          onClick={() => handleSelectTier(tier)}
                          className={`cursor-pointer transition-colors ${
                            isSelected
                              ? "bg-primary-container/10"
                              : "hover:bg-surface-container/70"
                          }`}
                        >
                          <td className="py-2.5 pr-2">
                            <div className="flex items-center gap-1.5">
                              <BinanceTierBadge tier={tier} size={18} />
                              <span className="font-sans font-semibold text-white text-[11px]">
                                {config.shortLabel}
                              </span>
                              {config.discountPct > 0 && (
                                <span className="px-1 py-0.2 rounded bg-tertiary/15 text-tertiary text-[9px] font-bold">
                                  -{config.discountPct}%
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-2.5 px-1.5 text-right text-slate-300">
                            {formatFeePct(result.effectiveMakerFeePct)}
                          </td>
                          <td className="py-2.5 px-1.5 text-right text-primary">
                            {result.hasValidRates
                              ? `Bs. ${result.breakEvenRate.toFixed(2)}`
                              : "—"}
                          </td>
                          <td
                            className={`py-2.5 px-1.5 text-right font-semibold ${
                              !result.hasValidRates
                                ? "text-slate-400"
                                : rowProfit
                                ? "text-tertiary"
                                : "text-error"
                            }`}
                          >
                            {result.hasValidRates
                              ? `${result.netProfitUsdt >= 0 ? "+" : ""}${result.netProfitUsdt.toFixed(2)} U`
                              : "—"}
                          </td>
                          <td
                            className={`py-2.5 pl-2 text-right font-bold hidden sm:table-cell ${
                              !result.hasValidRates
                                ? "text-slate-400"
                                : result.monthlyProfitUsdt >= 0
                                ? "text-white"
                                : "text-error"
                            }`}
                          >
                            {result.hasValidRates
                              ? `${result.monthlyProfitUsdt >= 0 ? "+" : ""}${result.monthlyProfitUsdt.toFixed(2)} U`
                              : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Proyección Lineal Compacta (sin interés compuesto ficticio ni días rígidos) */}
            <div className="p-4 sm:p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <h2 className="text-sm font-bold text-white">
                    Estimación Teórica a Spread Constante
                  </h2>
                  <p className="text-[11px] text-slate-400">
                    Cálculo lineal rotando {capitalUsdt} USDT (sin interés compuesto).
                  </p>
                </div>

                <div className="flex items-center gap-2 flex-wrap text-xs font-mono">
                  <div className="flex items-center gap-1 bg-surface-container p-1 rounded-lg border border-[#1e2430]">
                    {[1, 3, 5, 8].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setCyclesPerDay(n)}
                        className={`px-2 py-0.5 rounded text-[11px] transition-colors cursor-pointer ${
                          cyclesPerDay === n
                            ? "bg-primary-container text-on-primary font-bold"
                            : "text-slate-400 hover:text-white"
                        }`}
                      >
                        {n}x
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center gap-1 bg-surface-container p-1 rounded-lg border border-[#1e2430]">
                    {[20, 26, 30].map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => setOperatingDaysPerMonth(d)}
                        className={`px-2 py-0.5 rounded text-[11px] transition-colors cursor-pointer ${
                          operatingDaysPerMonth === d
                            ? "bg-surface-container-high text-white font-bold"
                            : "text-slate-400 hover:text-white"
                        }`}
                      >
                        {d}d
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {isDifferentBankMultiCycle && (
                <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-200 flex items-start gap-2">
                  <span className="material-symbols-outlined text-[16px] text-amber-400 shrink-0 mt-0.5">
                    swap_horiz
                  </span>
                  <span>
                    <strong>Salto entre bancos ({sellBank} ≠ {buyBank}):</strong> para repetir {cyclesPerDay} ciclos al día entre cuentas distintas, el segundo ciclo requiere operar en sentido inverso o fondear entre tus cuentas propias (considerando límites diarios de Pago Móvil).
                  </span>
                </div>
              )}

              <div className="grid grid-cols-3 gap-2.5">
                <div className="p-3 rounded-xl bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    Diario ({cyclesPerDay} cic.)
                  </div>
                  <div
                    className={`mt-1 text-sm sm:text-base font-mono font-bold tabular-nums ${
                      !simulation.hasValidRates
                        ? "text-slate-400"
                        : simulation.dailyProfitUsdt >= 0
                        ? "text-tertiary"
                        : "text-error"
                    }`}
                  >
                    {simulation.hasValidRates
                      ? `${simulation.dailyProfitUsdt >= 0 ? "+" : ""}${simulation.dailyProfitUsdt.toFixed(2)} U`
                      : "—"}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    Semana (6d)
                  </div>
                  <div
                    className={`mt-1 text-sm sm:text-base font-mono font-bold tabular-nums ${
                      !simulation.hasValidRates
                        ? "text-slate-400"
                        : simulation.weeklyProfitUsdt >= 0
                        ? "text-white"
                        : "text-error"
                    }`}
                  >
                    {simulation.hasValidRates
                      ? `${simulation.weeklyProfitUsdt >= 0 ? "+" : ""}${simulation.weeklyProfitUsdt.toFixed(2)} U`
                      : "—"}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    Mes ({operatingDaysPerMonth}d)
                  </div>
                  <div
                    className={`mt-1 text-sm sm:text-base font-mono font-bold tabular-nums ${
                      !simulation.hasValidRates
                        ? "text-slate-400"
                        : simulation.monthlyProfitUsdt >= 0
                        ? "text-primary"
                        : "text-error"
                    }`}
                  >
                    {simulation.hasValidRates
                      ? `${simulation.monthlyProfitUsdt >= 0 ? "+" : ""}${simulation.monthlyProfitUsdt.toFixed(2)} U`
                      : "—"}
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}

export default function CalculatorPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background text-slate-400 flex items-center justify-center font-mono text-xs">
          Cargando simulador institucional de ciclos P2P...
        </div>
      }
    >
      <CalculatorContent />
    </Suspense>
  );
}
