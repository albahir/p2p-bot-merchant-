"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import {
  BCVRates,
  RateQuote,
  getArbitrageMatrix,
  getBCVRates,
} from "@/lib/api";

type OrderRole = "MAKER" | "TAKER";
type BankTransferType = "SAME_BANK" | "INTERBANK_PM";

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

  const [quotes, setQuotes] = useState<RateQuote[]>([]);
  const [bcv, setBcv] = useState<BCVRates | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      getArbitrageMatrix(capitalUsdt || 100).catch(() => null),
      getBCVRates().catch(() => null),
    ]).then(([matrixData, bcvData]) => {
      if (!mounted) return;
      if (bcvData) setBcv(bcvData);
      if (matrixData?.quotes?.length) {
        setQuotes(matrixData.quotes);
        // Autocompletar tasas iniciales si no vinieron por query params
        setBuyRate((prev) => (prev > 0 ? prev : matrixData.quotes[0].buy_rate));
        setSellRate((prev) =>
          prev > 0
            ? prev
            : matrixData.quotes[Math.min(1, matrixData.quotes.length - 1)].sell_rate
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

  // Motor matemático exacto de ciclo P2P en Binance
  const simulation = useMemo(() => {
    const validCapital = Math.max(0, capitalUsdt || 0);
    const validBuy = Math.max(0.01, buyRate || 0.01);
    const validSell = Math.max(0.01, sellRate || 0.01);

    const buyBinanceFeeRate = buyRole === "MAKER" ? 0.0005 : 0.0; // En Binance P2P Venezuela: Maker suele pagar fee fijo/0.05%-0.10% o Taker 0.00-0.10%; usamos estándar explícito seleccionado por usuario:
    // Nota: permitimos control explícito Maker 0.00% vs Taker 0.10% como solicitó el operador
    void buyBinanceFeeRate;

    const leg1FeePct = buyRole === "MAKER" ? 0 : 0.001; // Maker 0.00% | Taker 0.10%
    const leg2FeePct = sellRole === "MAKER" ? 0 : 0.001;
    const bankFeePct = bankTransferType === "SAME_BANK" ? 0 : 0.003; // 0.30% Pago Móvil / Interbancario

    // Paso 1: Desembolso VES para comprar `validCapital` USDT brutos
    const baseVesIn = validCapital * validBuy;
    const bankFeeVes = baseVesIn * bankFeePct;
    const totalVesInvested = baseVesIn + bankFeeVes;

    // USDT netos acreditados tras comisión de pierna 1
    const usdtAfterBuyFee = validCapital * (1 - leg1FeePct);
    const buyFeeUsdt = validCapital - usdtAfterBuyFee;

    // Punto de equilibrio (Break-Even en Bs/USDT para no perder dinero en Pierna 2)
    const breakEvenSellRate =
      usdtAfterBuyFee * (1 - leg2FeePct) > 0
        ? totalVesInvested / (usdtAfterBuyFee * (1 - leg2FeePct))
        : 0;

    // Paso 3: Liquidación de USDT netos a Bolívares en `sellBank`
    const usdtSoldEffective = usdtAfterBuyFee * (1 - leg2FeePct);
    const sellFeeUsdt = usdtAfterBuyFee - usdtSoldEffective;
    const grossVesOut = usdtSoldEffective * validSell;

    const netProfitVes = grossVesOut - totalVesInvested;
    const netProfitUsdt = validSell > 0 ? netProfitVes / validSell : 0;
    const bcvUsd = bcv?.usd || 0;
    const netProfitBcvUsd = bcvUsd > 0 ? netProfitVes / bcvUsd : 0;
    const netRoiPct =
      totalVesInvested > 0 ? (netProfitVes / totalVesInvested) * 100 : 0;

    // Proyecciones multiciclo (interés simple vs compuesto diario)
    const dailyProfitUsdt = netProfitUsdt * cyclesPerDay;
    const dailyProfitVes = netProfitVes * cyclesPerDay;
    const weeklyProfitUsdt = dailyProfitUsdt * 6;
    const monthlyProfitUsdt = dailyProfitUsdt * 26;

    const compoundFactor =
      netRoiPct > -99
        ? Math.pow(1 + netRoiPct / 100, cyclesPerDay) - 1
        : 0;
    const compoundDailyUsdt = validCapital * compoundFactor;

    return {
      totalVesInvested,
      bankFeeVes,
      usdtAfterBuyFee,
      buyFeeUsdt,
      sellFeeUsdt,
      breakEvenSellRate,
      grossVesOut,
      netProfitVes,
      netProfitUsdt,
      netProfitBcvUsd,
      netRoiPct,
      dailyProfitUsdt,
      dailyProfitVes,
      weeklyProfitUsdt,
      monthlyProfitUsdt,
      compoundDailyUsdt,
    };
  }, [capitalUsdt, buyRate, sellRate, buyRole, sellRole, bankTransferType, cyclesPerDay, bcv]);

  const isProfitable = simulation.netProfitVes > 0;

  return (
    <AppShell
      title="Calculadora Instantánea de Ciclos P2P"
      badge="BINANCE P2P • VES"
      subtitle="Simulación exacta de arbitraje de ida y vuelta con punto de equilibrio, comisiones Maker/Taker y deducción Pago Móvil (0.3%)."
      actions={
        <Link
          href="/"
          className="px-3 py-1.5 rounded-lg bg-surface-container border border-[#1e2430] hover:border-primary-container/50 text-xs font-mono text-slate-200 flex items-center gap-1.5"
        >
          <span className="material-symbols-outlined text-[16px] text-primary">
            grid_view
          </span>
          <span>Volver a Matriz</span>
        </Link>
      }
    >
      <div className="space-y-5">
        {/* 4 KPIs Principales Corregidos (Sin duplicar título de Ruta de Venta) */}
        <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          {/* KPI 1 */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Capital Total Requerido</span>
              <span className="material-symbols-outlined text-[16px] text-secondary">
                account_balance_wallet
              </span>
            </div>
            <div className="mt-2 text-xl font-mono font-bold text-white tabular-nums">
              Bs. {simulation.totalVesInvested.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              Base: {capitalUsdt} USDT • Fee Banco: Bs. {simulation.bankFeeVes.toFixed(2)}
            </div>
          </div>

          {/* KPI 2 */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>Tasa Mínima Break-Even</span>
              <span className="material-symbols-outlined text-[16px] text-primary">
                balance
              </span>
            </div>
            <div className="mt-2 text-xl font-mono font-bold text-primary tabular-nums">
              Bs. {simulation.breakEvenSellRate.toFixed(2)}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              Venta actual: Bs. {sellRate.toFixed(2)} / USDT
            </div>
          </div>

          {/* KPI 3 Corregido: GANANCIA NETA POR CICLO */}
          <div className="p-4 rounded-xl bg-surface-container border border-primary-container/30">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-primary">
              <span>Ganancia Neta por Ciclo</span>
              <span className="material-symbols-outlined text-[16px] text-tertiary">
                paid
              </span>
            </div>
            <div
              className={`mt-2 text-xl font-mono font-bold tabular-nums ${
                isProfitable ? "text-tertiary" : "text-error"
              }`}
            >
              {simulation.netProfitUsdt >= 0 ? "+" : ""}
              {simulation.netProfitUsdt.toFixed(2)} USDT
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-300 tabular-nums">
              {simulation.netProfitVes >= 0 ? "+" : ""}Bs.{" "}
              {simulation.netProfitVes.toLocaleString("es-VE", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </div>
          </div>

          {/* KPI 4 */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-[#1e2430]">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
              <span>ROI Neto Real por Vuelta</span>
              <span className="material-symbols-outlined text-[16px] text-tertiary">
                monitoring
              </span>
            </div>
            <div
              className={`mt-2 text-xl font-mono font-bold tabular-nums ${
                isProfitable ? "text-tertiary" : "text-error"
              }`}
            >
              {simulation.netRoiPct >= 0 ? "+" : ""}
              {simulation.netRoiPct.toFixed(2)}%
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400 tabular-nums">
              {simulation.netProfitBcvUsd !== 0
                ? `Eq. Contable BCV: $${simulation.netProfitBcvUsd.toFixed(2)}`
                : "Sin IGTF • Solo API Binance"}
            </div>
          </div>
        </section>

        {/* Grilla Principal: Parámetros (Izquierda) + Desglose de 3 Pasos y Proyección (Derecha) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Panel Izquierdo: Parámetros de Ejecución */}
          <section className="lg:col-span-5 p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-4">
            <div className="flex items-center justify-between border-b border-[#1e2430] pb-3">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-primary">
                  tune
                </span>
                Parámetros del Ciclo
              </h2>
              <span className="px-2 py-0.5 rounded bg-tertiary/15 text-tertiary text-[10px] font-mono font-bold">
                USDT / VES
              </span>
            </div>

            {/* Volumen del Ciclo */}
            <div>
              <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                Volumen Operativo por Ciclo (USDT)
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  step="10"
                  value={capitalUsdt}
                  onChange={(e) => setCapitalUsdt(Number(e.target.value))}
                  className="flex-1 px-3.5 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] focus:border-primary-container focus:outline-hidden text-sm font-mono font-bold text-white tabular-nums"
                />
                {[100, 250, 500, 1000].map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => setCapitalUsdt(preset)}
                    className={`px-2.5 py-2 rounded-lg text-xs font-mono border transition-colors ${
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

            {/* Pierna 1: Compra de USDT */}
            <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">
                  1. Ruta de Entrada (Compra USDT)
                </span>
                <div className="flex rounded-md bg-surface-container-lowest p-0.5 border border-[#1e2430] text-[10px] font-mono">
                  <button
                    type="button"
                    onClick={() => setBuyRole("MAKER")}
                    className={`px-2 py-0.5 rounded ${
                      buyRole === "MAKER"
                        ? "bg-tertiary text-on-tertiary font-bold"
                        : "text-slate-400"
                    }`}
                  >
                    Maker 0%
                  </button>
                  <button
                    type="button"
                    onClick={() => setBuyRole("TAKER")}
                    className={`px-2 py-0.5 rounded ${
                      buyRole === "TAKER"
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-400"
                    }`}
                  >
                    Taker 0.1%
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[10px] font-mono text-slate-400 mb-1">
                    Banco Origen
                  </label>
                  <select
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
                  <label className="block text-[10px] font-mono text-slate-400 mb-1">
                    Tasa Compra (Bs/USDT)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={buyRate}
                    onChange={(e) => setBuyRate(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono font-bold text-white tabular-nums focus:border-primary-container focus:outline-hidden"
                  />
                </div>
              </div>
            </div>

            {/* Pierna 2: Venta de USDT */}
            <div className="p-3.5 rounded-xl bg-surface-container border border-[#1e2430] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">
                  2. Ruta de Salida (Venta USDT)
                </span>
                <div className="flex rounded-md bg-surface-container-lowest p-0.5 border border-[#1e2430] text-[10px] font-mono">
                  <button
                    type="button"
                    onClick={() => setSellRole("MAKER")}
                    className={`px-2 py-0.5 rounded ${
                      sellRole === "MAKER"
                        ? "bg-tertiary text-on-tertiary font-bold"
                        : "text-slate-400"
                    }`}
                  >
                    Maker 0%
                  </button>
                  <button
                    type="button"
                    onClick={() => setSellRole("TAKER")}
                    className={`px-2 py-0.5 rounded ${
                      sellRole === "TAKER"
                        ? "bg-primary-container text-on-primary font-bold"
                        : "text-slate-400"
                    }`}
                  >
                    Taker 0.1%
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[10px] font-mono text-slate-400 mb-1">
                    Banco Destino
                  </label>
                  <select
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
                  <label className="block text-[10px] font-mono text-slate-400 mb-1">
                    Tasa Venta (Bs/USDT)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={sellRate}
                    onChange={(e) => setSellRate(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest border border-[#1e2430] text-xs font-mono font-bold text-primary tabular-nums focus:border-primary-container focus:outline-hidden"
                  />
                </div>
              </div>
            </div>

            {/* Selector Explícito de Comisión Bancaria Venezolana */}
            <div>
              <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                Fricción Bancaria Nacional (VES)
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
                  <div className="text-xs font-mono font-bold">0.00% Mismo Banco</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    Transferencia intrabancaria
                  </div>
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
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    Comisión interbancaria BCV
                  </div>
                </button>
              </div>
            </div>
          </section>

          {/* Panel Derecho: Flujo de 3 Pasos + Simulador de Rotación Diaria */}
          <section className="lg:col-span-7 space-y-5">
            {/* Desglose en 3 Pasos exclusivamente en Binance P2P */}
            <div className="p-5 rounded-xl bg-surface-container-low border border-[#1e2430] space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="material-symbols-outlined text-[18px] text-secondary">
                    schema
                  </span>
                   Trazabilidad del Ciclo en Binance P2P
                </h2>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                    isProfitable
                      ? "bg-tertiary/15 text-tertiary"
                      : "bg-error/15 text-error"
                  }`}
                >
                  {isProfitable ? "CICLO VIABLE" : "SPREAD INSUFICIENTE"}
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
                      <span>Fee Binance:</span>
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
                      <span>Break-Even:</span>
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

                <div className="flex items-center gap-1 bg-surface-container p-1 rounded-lg border border-[#1e2430]">
                  {[1, 3, 5, 8].map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setCyclesPerDay(n)}
                      className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
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
