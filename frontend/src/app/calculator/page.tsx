"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { BankAmountInput } from "@/components/bank-amount-input";
import { BinanceTierBadge } from "@/components/binance-tier-badge";
import {
  ArbitrageMatrix,
  BCVRates,
  RateQuote,
  getArbitrageMatrix,
  getBCVRates,
  getCachedApiResponse,
} from "@/lib/api";
import {
  BankTransferType,
  DEFAULT_VES_BASE_MAKER_FEE_PCT,
  LEGACY_BASE_MAKER_FEE_PCT,
  MERCHANT_TIERS,
  MerchantTier,
  OrderRole,
  calculateP2PCycle,
  compareMerchantTiers,
  formatFeePct,
  getMerchantTierConfig,
} from "@/lib/p2p-calculator";

const STORAGE_TIER_KEY = "p2p_calc_merchant_tier";
const STORAGE_BASE_FEE_KEY = "p2p_calc_base_maker_pct";
const STORAGE_CUSTOM_FEE_KEY = "p2p_calc_custom_maker_pct";

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

function CalculatorContent() {
  const searchParams = useSearchParams();

  const [capitalUsdt, setCapitalUsdt] = useState<number>(
    Number(searchParams.get("amount")) || 250
  );
  const [buyBank, setBuyBank] = useState<string>(
    searchParams.get("buyBank") || "Banesco"
  );
  const [sellBank, setSellBank] = useState<string>(
    searchParams.get("sellBank") || "Pago Móvil"
  );
  const [buyRate, setBuyRate] = useState<number>(
    Number(searchParams.get("buyRate")) || 0
  );
  const [sellRate, setSellRate] = useState<number>(
    Number(searchParams.get("sellRate")) || 0
  );

  const [merchantTier, setMerchantTier] = useState<MerchantTier>("STANDARD");
  const [baseMakerFeePct, setBaseMakerFeePct] = useState<number>(
    DEFAULT_VES_BASE_MAKER_FEE_PCT
  );
  const [customMakerFeePct, setCustomMakerFeePct] = useState<number>(
    DEFAULT_VES_BASE_MAKER_FEE_PCT
  );
  const [buyRole, setBuyRole] = useState<OrderRole>("MAKER");
  const [sellRole, setSellRole] = useState<OrderRole>("MAKER");
  const [bankTransferType, setBankTransferType] = useState<BankTransferType>(
    searchParams.get("buyBank") &&
      searchParams.get("sellBank") &&
      searchParams.get("buyBank") === searchParams.get("sellBank")
      ? "SAME_BANK"
      : "INTERBANK_PM"
  );
  const [cyclesPerDay, setCyclesPerDay] = useState<number>(3);

  // Restaurar nivel VIP de comerciante guardado en el navegador
  useEffect(() => {
    if (typeof window === "undefined") return;
    const savedTier = localStorage.getItem(STORAGE_TIER_KEY) as MerchantTier | null;
    if (savedTier && MERCHANT_TIERS.some((t) => t.id === savedTier)) {
      setMerchantTier(savedTier);
    }
    const savedBase = Number(localStorage.getItem(STORAGE_BASE_FEE_KEY));
    if (Number.isFinite(savedBase) && savedBase > 0 && savedBase <= 5) {
      setBaseMakerFeePct(savedBase);
    }
    const savedCustom = Number(localStorage.getItem(STORAGE_CUSTOM_FEE_KEY));
    if (Number.isFinite(savedCustom) && savedCustom >= 0 && savedCustom <= 5) {
      setCustomMakerFeePct(savedCustom);
    }
  }, []);

  function handleSelectTier(nextTier: MerchantTier) {
    setMerchantTier(nextTier);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_TIER_KEY, nextTier);
    }
  }

  function handleSelectBaseFee(nextBase: number) {
    setBaseMakerFeePct(nextBase);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_BASE_FEE_KEY, String(nextBase));
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
      ? getCachedApiResponse<ArbitrageMatrix>("/api/spreads/matrix?amount_usdt=100&merchant_only=false")
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
      if (matrixData?.quotes?.length) {
        const seen = new Set<string>();
        const deduped = matrixData.quotes.filter((q) => {
          if (seen.has(q.bank_name)) return false;
          seen.add(q.bank_name);
          return true;
        });
        setQuotes(deduped);
        // Autocompletar tasas iniciales si no vinieron por query params
        setBuyRate((prev) => (prev > 0 ? prev : deduped[0].buy_rate));
        setSellRate((prev) =>
          prev > 0
            ? prev
            : deduped[Math.min(1, deduped.length - 1)].sell_rate
        );
      } else {
        setBuyRate((prev) => (prev > 0 ? prev : 45.2));
        setSellRate((prev) => (prev > 0 ? prev : 46.15));
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  // Sincronizar automáticamente comisión bancaria al cambiar bancos
  function handleSelectBuyBank(name: string) {
    setBuyBank(name);
    const found = quotes.find((q) => q.bank_name === name);
    if (found) setBuyRate(found.buy_rate);
    setBankTransferType(name === sellBank ? "SAME_BANK" : "INTERBANK_PM");
  }

  function handleSelectSellBank(name: string) {
    setSellBank(name);
    const found = quotes.find((q) => q.bank_name === name);
    if (found) setSellRate(found.sell_rate);
    setBankTransferType(buyBank === name ? "SAME_BANK" : "INTERBANK_PM");
  }

  // Motor matemático exacto de ciclo P2P en Binance con niveles VIP de comerciante
  const simulation = useMemo(
    () =>
      calculateP2PCycle({
        capitalUsdt,
        buyRate,
        sellRate,
        buyRole,
        sellRole,
        bankTransferType,
        merchantTier,
        baseMakerFeePct,
        customMakerFeePct,
        cyclesPerDay,
        bcvUsd: bcv?.usd || 0,
      }),
    [
      capitalUsdt,
      buyRate,
      sellRate,
      buyRole,
      sellRole,
      bankTransferType,
      merchantTier,
      baseMakerFeePct,
      customMakerFeePct,
      cyclesPerDay,
      bcv,
    ]
  );

  const tierComparison = useMemo(
    () =>
      compareMerchantTiers({
        capitalUsdt,
        buyRate,
        sellRate,
        buyRole,
        sellRole,
        bankTransferType,
        baseMakerFeePct,
        customMakerFeePct,
        cyclesPerDay,
        bcvUsd: bcv?.usd || 0,
      }),
    [
      capitalUsdt,
      buyRate,
      sellRate,
      buyRole,
      sellRole,
      bankTransferType,
      baseMakerFeePct,
      customMakerFeePct,
      cyclesPerDay,
      bcv,
    ]
  );

  const activeTierConfig = getMerchantTierConfig(merchantTier);
  const formattedMakerFee = formatFeePct(simulation.effectiveMakerFeePct);
  const isProfitable = simulation.netProfitVes > 0;

  return (
    <AppShell
      title="Calculadora de ciclos"
      subtitle="Simula compra, venta y comisiones."
      actions={
        <Link
          href="/"
          className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-primary-container/50 text-xs font-mono text-slate-200 flex items-center gap-1.5"
        >
          <span className="material-symbols-outlined text-[16px] text-primary">
            grid_view
          </span>
          <span>Volver a matriz</span>
        </Link>
      }
    >
      <div className="space-y-5">
        {/* Alerta de Cobertura de Riesgo Cambiario cuando el Spread se vuelve negativo o insuficiente */}
        {!isProfitable && buyRate > 0 && sellRate > 0 && (
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
                  Alerta de Riesgo Cambiario — Ciclo en Pérdida ({simulation.netRoiPct.toFixed(2)}% Retorno)
                </div>
                <div className="text-slate-300 mt-0.5">
                  La tasa de venta actual (<span className="font-mono text-error font-semibold">Bs. {sellRate.toFixed(2)}</span>) está por debajo del punto de equilibrio (<span className="font-mono text-primary font-semibold">Bs. {simulation.breakEvenSellRate.toFixed(2)}</span>), generando una pérdida neta de <span className="font-mono text-error font-semibold">Bs. {Math.abs(simulation.netProfitVes).toFixed(2)}</span>.
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setSellRate(Number((simulation.breakEvenSellRate * 1.008).toFixed(2)))}
              className="px-3 py-1.5 rounded-lg bg-primary-container text-on-primary font-mono text-[11px] font-bold hover:brightness-110 transition-all shrink-0 cursor-pointer"
            >
              Ajustar a Tasa Objetivo (+0,8%)
            </button>
          </div>
        )}

        {/* 4 KPIs Principales Corregidos (2 por fila en móvil) */}
        <section className="grid grid-cols-2 xl:grid-cols-4 gap-2.5 sm:gap-3">
          {/* KPI 1 */}
          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span className="truncate sm:hidden">Capital req.</span>
              <span className="truncate hidden sm:inline">Capital Total Requerido</span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-secondary shrink-0">
                account_balance_wallet
              </span>
            </div>
            <div className="mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold text-white tabular-nums truncate">
              Bs. {simulation.totalVesInvested.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 tabular-nums leading-tight break-words">
              Base: {capitalUsdt} USDT • Com: Bs. {simulation.bankFeeVes.toFixed(2)}
            </div>
          </div>

          {/* KPI 2 */}
          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span className="truncate">Tasa Equilibrio</span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-primary shrink-0">
                balance
              </span>
            </div>
            <div className="mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold text-primary tabular-nums truncate">
              Bs. {simulation.breakEvenSellRate.toFixed(2)}
            </div>
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 tabular-nums truncate">
              Venta: Bs. {sellRate.toFixed(2)} / USDT
            </div>
          </div>

          {/* KPI 3 Corregido: GANANCIA NETA POR CICLO */}
          <div className="p-3 sm:p-4 rounded-xl bg-surface-container border border-primary-container/30 min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-primary">
              <span className="truncate">Ganancia por Ciclo</span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-tertiary shrink-0">
                paid
              </span>
            </div>
            <div
              className={`mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold tabular-nums truncate ${
                isProfitable ? "text-tertiary" : "text-error"
              }`}
            >
              {simulation.netProfitUsdt >= 0 ? "+" : ""}
              {simulation.netProfitUsdt.toFixed(2)} USDT
            </div>
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-300 tabular-nums truncate">
              {simulation.netProfitVes >= 0 ? "+" : ""}Bs.{" "}
              {simulation.netProfitVes.toLocaleString("es-VE", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </div>
          </div>

          {/* KPI 4 */}
          <div className="p-3 sm:p-4 rounded-xl bg-surface-container-low border border-[#1e2430] min-w-0">
            <div className="flex items-center justify-between gap-1.5 min-w-0 text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span className="truncate">Retorno Neto Real</span>
              <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-tertiary shrink-0">
                monitoring
              </span>
            </div>
            <div
              className={`mt-1.5 sm:mt-2 text-base sm:text-xl font-mono font-bold tabular-nums truncate ${
                isProfitable ? "text-tertiary" : "text-error"
              }`}
            >
              {simulation.netRoiPct >= 0 ? "+" : ""}
              {simulation.netRoiPct.toFixed(2)}%
            </div>
            <div className="mt-0.5 sm:mt-1 text-[10px] sm:text-[11px] font-mono text-slate-400 tabular-nums truncate">
              {simulation.netProfitBcvUsd !== 0
                ? `≈ $${simulation.netProfitBcvUsd.toFixed(2)} BCV`
                : `${cyclesPerDay} ciclos / día`}
            </div>
          </div>
        </section>

        {/* Grilla Principal */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Panel Izquierdo: Parámetros de Ejecución */}
          <section className="lg:col-span-5 p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-4">
            <div className="flex items-center justify-between border-b border-[#1e2430] pb-3">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-primary">
                  tune
                </span>
                Parámetros
              </h2>
            </div>

            {/* Volumen del Ciclo */}
            <div>
              <label
                htmlFor="calc-capital-usdt"
                className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5"
              >
                Monto (USDT)
              </label>
              <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                <BankAmountInput
                  id="calc-capital-usdt"
                  value={capitalUsdt}
                  onChange={setCapitalUsdt}
                  ariaLabel="Volumen Operativo por Ciclo (USDT)"
                  className="w-full sm:flex-1 min-w-0 px-3.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm font-mono font-bold text-white tabular-nums"
                />
                <div className="grid grid-cols-4 sm:flex items-center gap-1.5 shrink-0">
                  {[100, 250, 500, 1000].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setCapitalUsdt(preset)}
                      className={`px-2 py-2 rounded-lg text-xs font-mono border text-center transition-colors ${
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

            {/* Nivel de Comerciante Binance P2P (Descuentos VIP sobre Comisión Maker) */}
            <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-2.5">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <label className="text-[11px] font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[15px] text-primary">
                    workspace_premium
                  </span>
                  Nivel Comerciante Binance
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
                      <BinanceTierBadge tier={tier.id} size={24} />
                      <span className="text-[9px] font-mono leading-none opacity-90">
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
                <div className="flex items-center justify-between gap-2 flex-wrap pt-0.5 text-[10px] font-mono text-slate-400">
                  <span>{activeTierConfig.requirementHint}</span>
                  <div className="flex items-center gap-1">
                    <span className="text-slate-500">Base:</span>
                    {[DEFAULT_VES_BASE_MAKER_FEE_PCT, LEGACY_BASE_MAKER_FEE_PCT].map(
                      (baseOpt) => (
                        <button
                          key={baseOpt}
                          type="button"
                          onClick={() => handleSelectBaseFee(baseOpt)}
                          className={`px-1.5 py-0.5 rounded border transition-colors cursor-pointer ${
                            baseMakerFeePct === baseOpt
                              ? "bg-surface-container-high border-primary-container/60 text-white font-semibold"
                              : "border-[#1e2430] text-slate-400 hover:text-white"
                          }`}
                        >
                          {formatFeePct(baseOpt)}
                        </button>
                      )
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Pierna 1: Compra de USDT */}
            <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-white">
                  1. Ruta de Entrada (Compra USDT)
                </span>
                <div className="flex rounded-md bg-surface-container-lowest p-0.5 border border-[#1e2430] text-[10px] font-mono shrink-0">
                  <button
                    type="button"
                    onClick={() => setBuyRole("MAKER")}
                    className={`px-2 py-0.5 rounded cursor-pointer ${
                      buyRole === "MAKER"
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Anuncio {formattedMakerFee}
                  </button>
                  <button
                    type="button"
                    onClick={() => setBuyRole("TAKER")}
                    className={`px-2 py-0.5 rounded cursor-pointer ${
                      buyRole === "TAKER"
                        ? "bg-tertiary text-on-tertiary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Directo 0%
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label
                    htmlFor="calc-buy-bank"
                    className="block text-[10px] font-mono text-slate-400 mb-1"
                  >
                    Banco Origen
                  </label>
                  <select
                    id="calc-buy-bank"
                    value={buyBank}
                    onChange={(e) => handleSelectBuyBank(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs text-white focus:border-primary-container focus:outline-hidden"
                  >
                    {quotes.length > 0 ? (
                      quotes.map((q) => (
                        <option key={`buy-${q.bank_name}`} value={q.bank_name}>
                          {q.bank_name}
                        </option>
                      ))
                    ) : (
                      <>
                        <option value="Banesco">Banesco</option>
                        <option value="Mercantil">Mercantil</option>
                        <option value="Banco de Venezuela">Banco de Venezuela</option>
                        <option value="Pago Móvil">Pago Móvil</option>
                      </>
                    )}
                  </select>
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
            </div>

            {/* Pierna 2: Venta de USDT */}
            <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-white">
                  2. Ruta de Salida (Venta USDT)
                </span>
                <div className="flex rounded-md bg-surface-container-lowest p-0.5 border border-[#1e2430] text-[10px] font-mono shrink-0">
                  <button
                    type="button"
                    onClick={() => setSellRole("MAKER")}
                    className={`px-2 py-0.5 rounded cursor-pointer ${
                      sellRole === "MAKER"
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Anuncio {formattedMakerFee}
                  </button>
                  <button
                    type="button"
                    onClick={() => setSellRole("TAKER")}
                    className={`px-2 py-0.5 rounded cursor-pointer ${
                      sellRole === "TAKER"
                        ? "bg-tertiary text-on-tertiary font-bold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    Directo 0%
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label
                    htmlFor="calc-sell-bank"
                    className="block text-[10px] font-mono text-slate-400 mb-1"
                  >
                    Banco Destino
                  </label>
                  <select
                    id="calc-sell-bank"
                    value={sellBank}
                    onChange={(e) => handleSelectSellBank(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs text-white focus:border-primary-container focus:outline-hidden"
                  >
                    {quotes.length > 0 ? (
                      quotes.map((q) => (
                        <option key={`sell-${q.bank_name}`} value={q.bank_name}>
                          {q.bank_name}
                        </option>
                      ))
                    ) : (
                      <>
                        <option value="Pago Móvil">Pago Móvil</option>
                        <option value="Banesco">Banesco</option>
                        <option value="Mercantil">Mercantil</option>
                        <option value="Banco de Venezuela">Banco de Venezuela</option>
                      </>
                    )}
                  </select>
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
            </div>

            {/* Selector Explícito de Comisión Bancaria Venezolana */}
            <div>
              <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                Comisión bancaria
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setBankTransferType("SAME_BANK")}
                  className={`p-2.5 rounded-lg border text-left transition-all ${
                    bankTransferType === "SAME_BANK"
                      ? "bg-tertiary/15 border-tertiary text-white"
                      : "bg-surface-container border-[#1e2430] text-slate-400 hover:text-white"
                  }`}
                >
                  <div className="text-xs font-mono font-bold">0% Mismo banco</div>
                </button>
                <button
                  type="button"
                  onClick={() => setBankTransferType("INTERBANK_PM")}
                  className={`p-2.5 rounded-lg border text-left transition-all ${
                    bankTransferType === "INTERBANK_PM"
                      ? "bg-primary-container/15 border-primary-container text-white"
                      : "bg-surface-container border-[#1e2430] text-slate-400 hover:text-white"
                  }`}
                >
                  <div className="text-xs font-mono font-bold">0.30% Pago Móvil</div>
                </button>
              </div>
            </div>
          </section>

          {/* Panel Derecho */}
          <section className="lg:col-span-7 space-y-5">
            <div className="p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="material-symbols-outlined text-[18px] text-secondary">
                    schema
                  </span>
                  Resumen del ciclo
                </h2>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                    isProfitable
                      ? "bg-tertiary/15 text-tertiary"
                      : "bg-error/15 text-error"
                  }`}
                >
                  {isProfitable ? "RENTABLE" : "EN PÉRDIDA"}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* Paso 1 */}
                <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-secondary font-bold">
                    Paso 1 • Compra P2P
                  </div>
                  <div className="text-xs font-semibold text-white mt-1">
                    VES → USDT ({buyBank})
                  </div>
                  <div className="mt-2 pt-2 border-t border-[#1e2430] space-y-1 text-[11px] font-mono tabular-nums">
                    <div className="flex justify-between text-slate-400">
                      <span>Inversión:</span>
                      <span className="text-white">
                        Bs. {simulation.totalVesInvested.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Comisión Binance:</span>
                      <span>-{simulation.buyFeeUsdt.toFixed(3)} USDT</span>
                    </div>
                  </div>
                </div>

                {/* Paso 2 */}
                <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-primary font-bold">
                    Paso 2 • Inventario Neto
                  </div>
                  <div className="text-xs font-semibold text-white mt-1">
                    Billetera de Fondos Binance
                  </div>
                  <div className="mt-2 pt-2 border-t border-[#1e2430] space-y-1 text-[11px] font-mono tabular-nums">
                    <div className="flex justify-between text-slate-400">
                      <span>Disponible:</span>
                      <span className="text-primary font-bold">
                        {simulation.usdtAfterBuyFee.toFixed(3)} USDT
                      </span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Equilibrio:</span>
                      <span>Bs. {simulation.breakEvenSellRate.toFixed(2)}</span>
                    </div>
                  </div>
                </div>

                {/* Paso 3 */}
                <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-tertiary font-bold">
                    Paso 3 • Liquidación P2P
                  </div>
                  <div className="text-xs font-semibold text-white mt-1">
                    USDT → VES ({sellBank})
                  </div>
                  <div className="mt-2 pt-2 border-t border-[#1e2430] space-y-1 text-[11px] font-mono tabular-nums">
                    <div className="flex justify-between text-slate-400">
                      <span>Retorno VES:</span>
                      <span className="text-white">
                        Bs. {simulation.grossVesOut.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Comisión Binance:</span>
                      <span>-{simulation.sellFeeUsdt.toFixed(3)} USDT</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Utilidad Neta:</span>
                      <span
                        className={`font-bold ${
                          isProfitable ? "text-tertiary" : "text-error"
                        }`}
                      >
                        {simulation.netProfitUsdt >= 0 ? "+" : ""}
                        {simulation.netProfitUsdt.toFixed(2)} USDT
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Resumen de Comisión Total Binance y Ahorro VIP */}
              <div className="px-3.5 py-2.5 rounded-xl bg-surface-container border border-[#1e2430] flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] font-mono tabular-nums">
                <div className="flex items-center gap-2 text-slate-300 flex-wrap">
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container-high border border-[#283140] text-[10px] text-white font-semibold">
                    <BinanceTierBadge tier={merchantTier} size={15} />
                    <span>{formattedMakerFee}</span>
                  </span>
                  <span>
                    Comisión total Binance:{" "}
                    <strong className="text-primary">
                      {simulation.totalBinanceFeeUsdt.toFixed(3)} USDT
                    </strong>{" "}
                    <span className="text-slate-400">
                      (≈ Bs. {simulation.totalBinanceFeeVes.toFixed(2)})
                    </span>
                  </span>
                </div>
                {simulation.vipSavingsUsdt > 0.0005 && (
                  <span className="text-tertiary font-semibold">
                    Ahorro VIP: +{simulation.vipSavingsUsdt.toFixed(3)} USDT/ciclo (+
                    {simulation.monthlyVipSavingsUsdt.toFixed(2)} USDT/mes)
                  </span>
                )}
              </div>
            </div>

            {/* Comparativa en Vivo por Nivel VIP de Comerciante */}
            <div className="p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <h2 className="text-sm font-bold text-white flex items-center gap-2">
                    <span className="material-symbols-outlined text-[18px] text-primary">
                      military_tech
                    </span>
                    Impacto por Nivel de Comerciante (Binance P2P)
                  </h2>
                  <p className="text-xs text-slate-400">
                    Haz clic en un nivel para aplicarlo (base Maker {formatFeePct(baseMakerFeePct)} • {cyclesPerDay}{" "}
                    {cyclesPerDay === 1 ? "ciclo" : "ciclos"}/día).
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs font-mono tabular-nums">
                  <thead>
                    <tr className="border-b border-[#1e2430] text-[10px] uppercase tracking-wider text-slate-400">
                      <th scope="col" className="py-2 pr-3">Nivel</th>
                      <th scope="col" className="py-2 px-2 text-right">Fee Maker</th>
                      <th scope="col" className="py-2 px-2 text-right">Equilibrio</th>
                      <th scope="col" className="py-2 px-2 text-right">Ciclo (USDT)</th>
                      <th scope="col" className="py-2 pl-2 text-right">Mes (26d)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1e2430]/70">
                    {tierComparison.map(({ tier, config, result }) => {
                      const isSelected = merchantTier === tier;
                      const rowProfit = result.netProfitUsdt > 0;
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
                          <td className="py-2.5 pr-3">
                            <div className="flex items-center gap-2" title={config.label}>
                              <BinanceTierBadge tier={tier} size={20} />
                              {config.discountPct > 0 ? (
                                <span className="px-1.5 py-0.5 rounded bg-tertiary/15 text-tertiary text-[10px] font-bold">
                                  -{config.discountPct}%
                                </span>
                              ) : (
                                <span className="text-[10px] text-slate-400">0%</span>
                              )}
                            </div>
                          </td>
                          <td className="py-2.5 px-2 text-right text-slate-300">
                            {formatFeePct(result.effectiveMakerFeePct)}
                          </td>
                          <td className="py-2.5 px-2 text-right text-primary">
                            Bs. {result.breakEvenSellRate.toFixed(2)}
                          </td>
                          <td
                            className={`py-2.5 px-2 text-right font-semibold ${
                              rowProfit ? "text-tertiary" : "text-error"
                            }`}
                          >
                            {result.netProfitUsdt >= 0 ? "+" : ""}
                            {result.netProfitUsdt.toFixed(2)} U
                          </td>
                          <td
                            className={`py-2.5 pl-2 text-right font-bold ${
                              result.monthlyProfitUsdt >= 0
                                ? "text-white"
                                : "text-error"
                            }`}
                          >
                            {result.monthlyProfitUsdt >= 0 ? "+" : ""}
                            {result.monthlyProfitUsdt.toFixed(2)} U
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Proyección de Velocidad de Rotación Diaria */}
            <div className="p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <h2 className="text-sm font-bold text-white">
                    Proyección por Velocidad de Rotación de Capital
                  </h2>
                  <p className="text-xs text-slate-400">
                    Estimación operativa rotando el mismo bloque de {capitalUsdt} USDT durante la jornada.
                  </p>
                </div>

                <div className="grid grid-cols-4 sm:flex items-center gap-1 w-full sm:w-auto bg-surface-container p-1 rounded-lg border border-[#1e2430]">
                  {[1, 3, 5, 8].map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setCyclesPerDay(n)}
                      className={`px-1.5 sm:px-2.5 py-1 rounded text-[11px] sm:text-xs font-mono text-center whitespace-nowrap transition-colors ${
                        cyclesPerDay === n
                          ? "bg-primary-container text-on-primary font-bold"
                          : "text-slate-400 hover:text-white"
                      }`}
                    >
                      {n} {n === 1 ? "Ciclo" : "Ciclos"}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    Jornada Diaria ({cyclesPerDay} vueltas)
                  </div>
                  <div
                    className={`mt-1.5 text-lg font-mono font-bold tabular-nums ${
                      simulation.dailyProfitUsdt >= 0 ? "text-tertiary" : "text-error"
                    }`}
                  >
                    {simulation.dailyProfitUsdt >= 0 ? "+" : ""}
                    {simulation.dailyProfitUsdt.toFixed(2)} USDT
                  </div>
                  <div className="text-[11px] font-mono text-slate-400 tabular-nums mt-0.5">
                    Compuesto: {simulation.compoundDailyUsdt >= 0 ? "+" : ""}
                    {simulation.compoundDailyUsdt.toFixed(2)} USDT
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    Proyección Semanal (6 días)
                  </div>
                  <div
                    className={`mt-1.5 text-lg font-mono font-bold tabular-nums ${
                      simulation.weeklyProfitUsdt >= 0 ? "text-white" : "text-error"
                    }`}
                  >
                    {simulation.weeklyProfitUsdt >= 0 ? "+" : ""}
                    {simulation.weeklyProfitUsdt.toFixed(2)} USDT
                  </div>
                  <div className="text-[11px] font-mono text-slate-400 tabular-nums mt-0.5">
                    {cyclesPerDay * 6} ciclos ejecutados
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430]">
                  <div className="text-[10px] font-mono uppercase text-slate-400">
                    Proyección Mensual (26 días)
                  </div>
                  <div
                    className={`mt-1.5 text-lg font-mono font-bold tabular-nums ${
                      simulation.monthlyProfitUsdt >= 0 ? "text-primary" : "text-error"
                    }`}
                  >
                    {simulation.monthlyProfitUsdt >= 0 ? "+" : ""}
                    {simulation.monthlyProfitUsdt.toFixed(2)} USDT
                  </div>
                  <div className="text-[11px] font-mono text-slate-400 tabular-nums mt-0.5">
                    {cyclesPerDay * 26} ciclos acumulados
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
