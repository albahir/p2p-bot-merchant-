/**
 * Motor matemático puro de simulación de ciclos Binance P2P (USDT / VES) con niveles VIP.
 *
 * Reglas operativas reales en Venezuela:
 * - Taker (Tomar anuncio): 0.00% comisión Binance P2P.
 * - Maker (Publicar anuncio): tarifa base VES 0.25% con descuentos VIP oficiales:
 *   - Estándar: 0% descuento (0.25%)
 *   - Bronce: -20% descuento (0.20%)
 *   - Plata: -30% descuento (0.175%)
 *   - Oro: -50% descuento (0.125%)
 * - Banca venezolana: la comisión bancaria (hasta 0.30% Pago Móvil / Crédito Inmediato o
 *   fraccionamiento con mínimo por orden) SIEMPRE la paga quien envía los bolívares
 *   (al COMPRAR USDT). Recibir bolívares (al VENDER USDT) cuesta 0% comisión bancaria.
 * - Dos direcciones de ciclo:
 *   1) USDT -> Bs -> USDT (Venta y Recompra): protege y mide crecimiento real en USDT.
 *   2) Bs -> USDT -> Bs (Compra y Venta): mide inversión en Bs, equilibrio de venta y ROI neto.
 */

export type OrderRole = "MAKER" | "TAKER";
export type BankTransferType = "SAME_BANK" | "INTERBANK_PM" | "CUSTOM";
export type CycleDirection = "USDT_VES_USDT" | "VES_USDT_VES";
export type MerchantTier = "STANDARD" | "BRONZE" | "SILVER" | "GOLD" | "CUSTOM";
export type CycleProfitStatus = "INCOMPLETE" | "LOSS" | "MARGINAL" | "PROFITABLE";

export interface MerchantTierConfig {
  id: MerchantTier;
  label: string;
  shortLabel: string;
  discountPct: number;
  requirementHint: string;
}

export const DEFAULT_VES_BASE_MAKER_FEE_PCT = 0.25;
export const BINANCE_P2P_TAKER_FEE_PCT = 0;
export const VENEZUELA_INTERBANK_FEE_PCT = 0.3;

export const MERCHANT_TIERS: readonly MerchantTierConfig[] = [
  {
    id: "STANDARD",
    label: "Estándar",
    shortLabel: "Estándar",
    discountPct: 0,
    requirementHint: "Sin descuento VIP (0,25% Maker)",
  },
  {
    id: "BRONZE",
    label: "Bronce",
    shortLabel: "Bronce",
    discountPct: 20,
    requirementHint: "Comerciante Verificado Bronce (-20%)",
  },
  {
    id: "SILVER",
    label: "Plata",
    shortLabel: "Plata",
    discountPct: 30,
    requirementHint: "Comerciante Verificado Plata (-30%)",
  },
  {
    id: "GOLD",
    label: "Oro",
    shortLabel: "Oro",
    discountPct: 50,
    requirementHint: "Comerciante Verificado Oro (-50%)",
  },
  {
    id: "CUSTOM",
    label: "Manual %",
    shortLabel: "Manual %",
    discountPct: 0,
    requirementHint: "Define tu comisión Maker exacta (%)",
  },
] as const;

export const COMPARABLE_TIERS: readonly MerchantTier[] = [
  "STANDARD",
  "BRONZE",
  "SILVER",
  "GOLD",
] as const;

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, value));
}

function roundPct(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}

export function getMerchantTierConfig(tier: MerchantTier): MerchantTierConfig {
  return MERCHANT_TIERS.find((t) => t.id === tier) || MERCHANT_TIERS[0];
}

/**
 * Retorna la comisión Maker efectiva en puntos porcentuales (ej. 0.20 = 0.20%).
 */
export function getEffectiveMakerFeePct(
  tier: MerchantTier,
  baseMakerFeePct: number = DEFAULT_VES_BASE_MAKER_FEE_PCT,
  customMakerFeePct: number = DEFAULT_VES_BASE_MAKER_FEE_PCT
): number {
  if (tier === "CUSTOM") {
    return roundPct(clamp(customMakerFeePct, 0, 5));
  }
  const safeBase = clamp(baseMakerFeePct, 0, 5);
  const cfg = getMerchantTierConfig(tier);
  return roundPct(safeBase * (1 - cfg.discountPct / 100));
}

export function formatFeePct(pct: number): string {
  const clean = roundPct(pct);
  if (clean === 0) return "0%";
  const decimals = Number.isInteger(clean * 100) ? 2 : 3;
  return `${clean.toLocaleString("es-VE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}%`;
}

export interface P2PCycleInput {
  capitalUsdt: number;
  buyRate: number;
  sellRate: number;
  buyRole: OrderRole;
  sellRole: OrderRole;
  cycleDirection?: CycleDirection;
  bankTransferType: BankTransferType;
  customBankFeePct?: number;
  splitOrdersCount?: number;
  minBankFeePerOrderVes?: number;
  merchantTier: MerchantTier;
  baseMakerFeePct?: number;
  customMakerFeePct?: number;
  cyclesPerDay: number;
  operatingDaysPerMonth?: number;
  refP2pRate?: number;
  bcvUsd?: number;
}

export interface P2PCycleSimulation {
  hasValidRates: boolean;
  cycleDirection: CycleDirection;
  profitStatus: CycleProfitStatus;
  effectiveMakerFeePct: number;
  buyBinanceFeePct: number;
  sellBinanceFeePct: number;
  bankFeePct: number;
  effectiveBankFeePct: number;
  /** Bolívares base de la operación de compra/recompra (sin fee bancario) */
  baseVesMoved: number;
  /** Comisión bancaria cobrada exclusivamente al enviar bolívares (compra) */
  bankFeeVes: number;
  /** Total en Bolívares requeridos/invertidos en la compra (VES -> USDT -> VES) o recibidos en venta (USDT -> VES -> USDT) */
  totalVesInvested: number;
  /** Paso intermedio: USDT netos tras compra (VES->USDT->VES) o Bs netos recibidos al vender (USDT->VES->USDT) */
  usdtAfterBuyFee: number;
  vesReceivedOnSell: number;
  finalUsdtOut: number;
  buyFeeUsdt: number;
  sellFeeUsdt: number;
  totalBinanceFeeUsdt: number;
  totalBinanceFeeVes: number;
  /** En VES->USDT->VES es tasa mínima de venta; en USDT->VES->USDT es tasa máxima de recompra */
  breakEvenRate: number;
  breakEvenSellRate: number;
  grossVesOut: number;
  netProfitVes: number;
  netProfitUsdt: number;
  netRoiPct: number;
  dailyProfitUsdt: number;
  dailyProfitVes: number;
  weeklyProfitUsdt: number;
  monthlyProfitUsdt: number;
  vipSavingsVes: number;
  vipSavingsUsdt: number;
  monthlyVipSavingsUsdt: number;
}

function resolveBankFee(
  baseVesSent: number,
  bankTransferType: BankTransferType,
  customBankFeePct: number,
  splitOrdersCount: number,
  minBankFeePerOrderVes: number
): { bankFeePct: number; bankFeeVes: number; effectiveBankFeePct: number } {
  if (bankTransferType === "SAME_BANK" || baseVesSent <= 0) {
    return { bankFeePct: 0, bankFeeVes: 0, effectiveBankFeePct: 0 };
  }
  const pct =
    bankTransferType === "CUSTOM"
      ? clamp(customBankFeePct, 0, 5)
      : VENEZUELA_INTERBANK_FEE_PCT;
  const pctFeeVes = baseVesSent * (pct / 100);
  const splits = Math.max(1, Math.round(splitOrdersCount || 1));
  const minPerOrder = Math.max(0, minBankFeePerOrderVes || 0);
  const minFloorVes = splits * minPerOrder;
  const bankFeeVes = Math.max(pctFeeVes, minFloorVes);
  const effectiveBankFeePct = baseVesSent > 0 ? (bankFeeVes / baseVesSent) * 100 : pct;
  return { bankFeePct: pct, bankFeeVes, effectiveBankFeePct };
}

function emptySimulation(
  direction: CycleDirection,
  effectiveMakerFeePct: number,
  buyBinanceFeePct: number,
  sellBinanceFeePct: number,
  bankFeePct: number
): P2PCycleSimulation {
  return {
    hasValidRates: false,
    cycleDirection: direction,
    profitStatus: "INCOMPLETE",
    effectiveMakerFeePct,
    buyBinanceFeePct,
    sellBinanceFeePct,
    bankFeePct,
    effectiveBankFeePct: bankFeePct,
    baseVesMoved: 0,
    bankFeeVes: 0,
    totalVesInvested: 0,
    usdtAfterBuyFee: 0,
    vesReceivedOnSell: 0,
    finalUsdtOut: 0,
    buyFeeUsdt: 0,
    sellFeeUsdt: 0,
    totalBinanceFeeUsdt: 0,
    totalBinanceFeeVes: 0,
    breakEvenRate: 0,
    breakEvenSellRate: 0,
    grossVesOut: 0,
    netProfitVes: 0,
    netProfitUsdt: 0,
    netRoiPct: 0,
    dailyProfitUsdt: 0,
    dailyProfitVes: 0,
    weeklyProfitUsdt: 0,
    monthlyProfitUsdt: 0,
    vipSavingsVes: 0,
    vipSavingsUsdt: 0,
    monthlyVipSavingsUsdt: 0,
  };
}

function resolveProfitStatus(netRoiPct: number): CycleProfitStatus {
  if (netRoiPct <= 0) return "LOSS";
  if (netRoiPct < 0.3) return "MARGINAL";
  return "PROFITABLE";
}

function computeRawCycle(input: P2PCycleInput): Omit<P2PCycleSimulation, "vipSavingsVes" | "vipSavingsUsdt" | "monthlyVipSavingsUsdt"> {
  const direction: CycleDirection = input.cycleDirection || "VES_USDT_VES";
  const capital = Math.max(0, input.capitalUsdt || 0);
  const buyRate = Number.isFinite(input.buyRate) && input.buyRate > 0 ? input.buyRate : 0;
  const sellRate = Number.isFinite(input.sellRate) && input.sellRate > 0 ? input.sellRate : 0;
  const cycles = Math.max(1, Math.round(input.cyclesPerDay || 1));
  const opDays = Math.max(1, Math.min(31, Math.round(input.operatingDaysPerMonth || 26)));

  const effectiveMakerFeePct = getEffectiveMakerFeePct(
    input.merchantTier,
    input.baseMakerFeePct ?? DEFAULT_VES_BASE_MAKER_FEE_PCT,
    input.customMakerFeePct ?? DEFAULT_VES_BASE_MAKER_FEE_PCT
  );
  const buyBinanceFeePct =
    input.buyRole === "MAKER" ? effectiveMakerFeePct : BINANCE_P2P_TAKER_FEE_PCT;
  const sellBinanceFeePct =
    input.sellRole === "MAKER" ? effectiveMakerFeePct : BINANCE_P2P_TAKER_FEE_PCT;

  const customBankPct = input.customBankFeePct ?? VENEZUELA_INTERBANK_FEE_PCT;

  if (capital <= 0 || buyRate <= 0 || sellRate <= 0) {
    const emptyPct =
      input.bankTransferType === "SAME_BANK"
        ? 0
        : input.bankTransferType === "CUSTOM"
        ? customBankPct
        : VENEZUELA_INTERBANK_FEE_PCT;
    return emptySimulation(
      direction,
      effectiveMakerFeePct,
      buyBinanceFeePct,
      sellBinanceFeePct,
      emptyPct
    );
  }

  const buyFeeRate = buyBinanceFeePct / 100;
  const sellFeeRate = sellBinanceFeePct / 100;
  const valuationRate =
    direction === "USDT_VES_USDT"
      ? buyRate
      : (input.refP2pRate && input.refP2pRate > 0 ? input.refP2pRate : sellRate);

  if (direction === "USDT_VES_USDT") {
    // 1. Paso 1: Vender `capital` USDT en Binance P2P -> recibes Bs en tu banco (0% fee bancario al recibir)
    const usdtSoldEffective = capital * (1 - sellFeeRate);
    const sellFeeUsdt = capital - usdtSoldEffective;
    const vesReceivedOnSell = usdtSoldEffective * sellRate;

    // 2. Paso 3: Usar esos Bs recibidos para RECOMPRAR USDT enviando Bs desde tu banco (aquí sí pagas comisión bancaria)
    const pctBank =
      input.bankTransferType === "SAME_BANK"
        ? 0
        : input.bankTransferType === "CUSTOM"
        ? clamp(customBankPct, 0, 5)
        : VENEZUELA_INTERBANK_FEE_PCT;
    const pctRate = pctBank / 100;
    const splits = Math.max(1, Math.round(input.splitOrdersCount || 1));
    const minPerOrder = Math.max(0, input.minBankFeePerOrderVes || 0);
    const minFloorVes = input.bankTransferType === "SAME_BANK" ? 0 : splits * minPerOrder;

    // Si hay comisión porcentual, baseVesSent + fee = vesReceivedOnSell -> baseVesSent = vesReceived / (1 + pctRate)
    const candBaseByPct = vesReceivedOnSell / (1 + pctRate);
    const candFeeByPct = vesReceivedOnSell - candBaseByPct;
    let baseVesSent = candBaseByPct;
    let bankFeeVes = candFeeByPct;
    if (minFloorVes > candFeeByPct && vesReceivedOnSell > minFloorVes) {
      bankFeeVes = minFloorVes;
      baseVesSent = vesReceivedOnSell - minFloorVes;
    } else if (minFloorVes >= vesReceivedOnSell) {
      bankFeeVes = vesReceivedOnSell;
      baseVesSent = 0;
    }
    const effectiveBankFeePct = baseVesSent > 0 ? (bankFeeVes / baseVesSent) * 100 : pctBank;

    const grossReboughtUsdt = buyRate > 0 ? baseVesSent / buyRate : 0;
    const buyFeeUsdt = grossReboughtUsdt * buyFeeRate;
    const finalUsdtOut = grossReboughtUsdt - buyFeeUsdt;

    const totalBinanceFeeUsdt = sellFeeUsdt + buyFeeUsdt;
    // Todas las comisiones USDT se valoran a tasa P2P real de referencia (nunca al promedio con 0.01)
    const totalBinanceFeeVes = totalBinanceFeeUsdt * valuationRate;

    const netProfitUsdt = finalUsdtOut - capital;
    const netProfitVes = netProfitUsdt * buyRate;
    const netRoiPct = capital > 0 ? (netProfitUsdt / capital) * 100 : 0;

    // Tasa máxima de recompra (equilibrio) para recuperar exactamente `capital` USDT vendiendo a `sellRate`
    // finalUsdtOut == capital => baseVesSent = capital * buyRate / (1 - buyFeeRate)
    const denomFactor = (1 - buyFeeRate) * (1 + pctRate);
    let breakEvenRate = 0;
    if (denomFactor > 0) {
      const rateByPct = (vesReceivedOnSell * (1 - buyFeeRate)) / (capital * (1 + pctRate));
      const rateByMin =
        vesReceivedOnSell > minFloorVes
          ? ((vesReceivedOnSell - minFloorVes) * (1 - buyFeeRate)) / capital
          : 0;
      breakEvenRate = minFloorVes > 0 ? Math.min(rateByPct, rateByMin) : rateByPct;
    }

    const dailyProfitUsdt = netProfitUsdt * cycles;
    const dailyProfitVes = netProfitVes * cycles;
    const weeklyProfitUsdt = dailyProfitUsdt * 6;
    const monthlyProfitUsdt = dailyProfitUsdt * opDays;

    return {
      hasValidRates: true,
      cycleDirection: direction,
      profitStatus: resolveProfitStatus(netRoiPct),
      effectiveMakerFeePct,
      buyBinanceFeePct,
      sellBinanceFeePct,
      bankFeePct: pctBank,
      effectiveBankFeePct,
      baseVesMoved: baseVesSent,
      bankFeeVes,
      totalVesInvested: vesReceivedOnSell,
      usdtAfterBuyFee: finalUsdtOut,
      vesReceivedOnSell,
      finalUsdtOut,
      buyFeeUsdt,
      sellFeeUsdt,
      totalBinanceFeeUsdt,
      totalBinanceFeeVes,
      breakEvenRate,
      breakEvenSellRate: breakEvenRate,
      grossVesOut: vesReceivedOnSell,
      netProfitVes,
      netProfitUsdt,
      netRoiPct,
      dailyProfitUsdt,
      dailyProfitVes,
      weeklyProfitUsdt,
      monthlyProfitUsdt,
    };
  }

  // Dirección 2: VES -> USDT -> VES (Inversión inicial en Bolívares)
  const baseVesIn = capital * buyRate;
  const bankCalc = resolveBankFee(
    baseVesIn,
    input.bankTransferType,
    customBankPct,
    input.splitOrdersCount ?? 1,
    input.minBankFeePerOrderVes ?? 0
  );
  const totalVesInvested = baseVesIn + bankCalc.bankFeeVes;

  const usdtAfterBuyFee = capital * (1 - buyFeeRate);
  const buyFeeUsdt = capital - usdtAfterBuyFee;

  const usdtSoldEffective = usdtAfterBuyFee * (1 - sellFeeRate);
  const sellFeeUsdt = usdtAfterBuyFee - usdtSoldEffective;
  const totalBinanceFeeUsdt = buyFeeUsdt + sellFeeUsdt;
  // Valorado a tasa de salida P2P real
  const totalBinanceFeeVes = totalBinanceFeeUsdt * valuationRate;

  const breakEvenSellRate =
    usdtSoldEffective > 0 ? totalVesInvested / usdtSoldEffective : 0;

  // En la venta recibes Bs en tu cuenta: 0% comisión bancaria al recibir
  const grossVesOut = usdtSoldEffective * sellRate;
  const netProfitVes = grossVesOut - totalVesInvested;
  const netProfitUsdt = sellRate > 0 ? netProfitVes / sellRate : 0;
  const netRoiPct = totalVesInvested > 0 ? (netProfitVes / totalVesInvested) * 100 : 0;

  const dailyProfitUsdt = netProfitUsdt * cycles;
  const dailyProfitVes = netProfitVes * cycles;
  const weeklyProfitUsdt = dailyProfitUsdt * 6;
  const monthlyProfitUsdt = dailyProfitUsdt * opDays;

  return {
    hasValidRates: true,
    cycleDirection: direction,
    profitStatus: resolveProfitStatus(netRoiPct),
    effectiveMakerFeePct,
    buyBinanceFeePct,
    sellBinanceFeePct,
    bankFeePct: bankCalc.bankFeePct,
    effectiveBankFeePct: bankCalc.effectiveBankFeePct,
    baseVesMoved: baseVesIn,
    bankFeeVes: bankCalc.bankFeeVes,
    totalVesInvested,
    usdtAfterBuyFee,
    vesReceivedOnSell: grossVesOut,
    finalUsdtOut: usdtAfterBuyFee + netProfitUsdt,
    buyFeeUsdt,
    sellFeeUsdt,
    totalBinanceFeeUsdt,
    totalBinanceFeeVes,
    breakEvenRate: breakEvenSellRate,
    breakEvenSellRate,
    grossVesOut,
    netProfitVes,
    netProfitUsdt,
    netRoiPct,
    dailyProfitUsdt,
    dailyProfitVes,
    weeklyProfitUsdt,
    monthlyProfitUsdt,
  };
}

export function calculateP2PCycle(input: P2PCycleInput): P2PCycleSimulation {
  const raw = computeRawCycle(input);
  if (!raw.hasValidRates || input.merchantTier === "STANDARD") {
    return {
      ...raw,
      vipSavingsVes: 0,
      vipSavingsUsdt: 0,
      monthlyVipSavingsUsdt: 0,
    };
  }

  const cycles = Math.max(1, Math.round(input.cyclesPerDay || 1));
  const opDays = Math.max(1, Math.min(31, Math.round(input.operatingDaysPerMonth || 26)));

  const baseline = computeRawCycle({
    ...input,
    merchantTier: "STANDARD",
  });
  const vipSavingsVes = raw.netProfitVes - baseline.netProfitVes;
  const vipSavingsUsdt = raw.netProfitUsdt - baseline.netProfitUsdt;
  const monthlyVipSavingsUsdt = vipSavingsUsdt * cycles * opDays;

  return {
    ...raw,
    vipSavingsVes,
    vipSavingsUsdt,
    monthlyVipSavingsUsdt,
  };
}

/**
 * Calculador Inverso: dado un margen neto deseado (%) por ciclo y tus comisiones reales,
 * devuelve exactamente a qué tasa publicar tu anuncio objetivo.
 * - En VES -> USDT -> VES: calcula Tasa Venta objetivo partiendo de Tasa Compra conocida.
 * - En USDT -> Bs -> USDT: calcula Tasa Recompra objetivo partiendo de Tasa Venta conocida
 *   (o Tasa Venta objetivo si prefieres ajustar la salida partiendo de la recompra conocida).
 */
export function computeTargetRateForMargin(
  input: P2PCycleInput,
  targetNetMarginPct: number,
  solveFor: "SELL" | "BUY" = input.cycleDirection === "USDT_VES_USDT" ? "BUY" : "SELL"
): number {
  const targetRatio = 1 + clamp(targetNetMarginPct, -50, 100) / 100;
  const sim = computeRawCycle(input);
  const capital = Math.max(0, input.capitalUsdt || 0);
  if (capital <= 0) return 0;

  const buyFeeRate = sim.buyBinanceFeePct / 100;
  const sellFeeRate = sim.sellBinanceFeePct / 100;
  const bankRate = sim.bankFeePct / 100;
  const splits = Math.max(1, Math.round(input.splitOrdersCount || 1));
  const minFloorVes =
    input.bankTransferType === "SAME_BANK"
      ? 0
      : splits * Math.max(0, input.minBankFeePerOrderVes || 0);

  if (solveFor === "SELL") {
    if (input.buyRate <= 0) return 0;
    const baseVes = capital * input.buyRate;
    const bankVes = Math.max(baseVes * bankRate, minFloorVes);
    const totalCostVes = baseVes + bankVes;
    const effectiveSold = capital * (1 - buyFeeRate) * (1 - sellFeeRate);
    if (effectiveSold <= 0) return 0;
    if ((input.cycleDirection || "USDT_VES_USDT") === "VES_USDT_VES") {
      return Number(((totalCostVes * targetRatio) / effectiveSold).toFixed(2));
    }
    // En USDT->VES->USDT buscando SELL dado BUY y target USDT = capital * targetRatio:
    const neededBaseRebuy = (capital * targetRatio * input.buyRate) / Math.max(0.01, 1 - buyFeeRate);
    const neededBankRebuy = Math.max(neededBaseRebuy * bankRate, minFloorVes);
    const neededVes = neededBaseRebuy + neededBankRebuy;
    const soldUsdt = capital * (1 - sellFeeRate);
    return soldUsdt > 0 ? Number((neededVes / soldUsdt).toFixed(2)) : 0;
  }

  // solveFor === "BUY" (tasa máxima de recompra en USDT -> Bs -> USDT dado sellRate)
  if (input.sellRate <= 0) return 0;
  const vesFromSell = capital * (1 - sellFeeRate) * input.sellRate;
  const targetUsdtOut = capital * targetRatio;
  if (targetUsdtOut <= 0) return 0;
  const grossBuyNeeded = targetUsdtOut / Math.max(0.01, 1 - buyFeeRate);
  const byPct = vesFromSell / ((1 + bankRate) * grossBuyNeeded);
  const byMin = vesFromSell > minFloorVes ? (vesFromSell - minFloorVes) / grossBuyNeeded : 0;
  const ans = minFloorVes > 0 ? Math.min(byPct, byMin) : byPct;
  return ans > 0 ? Number(ans.toFixed(2)) : 0;
}

export interface TierComparisonRow {
  tier: MerchantTier;
  config: MerchantTierConfig;
  result: P2PCycleSimulation;
}

export function compareMerchantTiers(
  input: Omit<P2PCycleInput, "merchantTier">
): TierComparisonRow[] {
  return COMPARABLE_TIERS.map((tier) => ({
    tier,
    config: getMerchantTierConfig(tier),
    result: calculateP2PCycle({
      ...input,
      merchantTier: tier,
    }),
  }));
}
