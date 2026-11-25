/**
 * Motor matemático puro de simulación de ciclos Binance P2P con niveles VIP de comerciante.
 *
 * Estructura oficial Binance P2P (zona VES, vigencia 2026):
 * - Taker (tomar anuncio existente / directo): 0.00% de comisión Binance P2P.
 * - Maker (publicar anuncio propio): tarifa base VES 0.25% (configurable a 0.35% o manual)
 *   con descuentos oficiales del Programa VIP de Comerciantes Verificados:
 *   - Estándar / Normal: 0% descuento (0.25%)
 *   - Bronce: -20% descuento (0.20%)
 *   - Plata: -30% descuento (0.175%)
 *   - Oro: -50% descuento (0.125%)
 */

export type OrderRole = "MAKER" | "TAKER";
export type BankTransferType = "SAME_BANK" | "INTERBANK_PM";
export type MerchantTier = "STANDARD" | "BRONZE" | "SILVER" | "GOLD" | "CUSTOM";

export interface MerchantTierConfig {
  id: MerchantTier;
  label: string;
  shortLabel: string;
  discountPct: number;
  requirementHint: string;
}

export const DEFAULT_VES_BASE_MAKER_FEE_PCT = 0.25;
export const LEGACY_BASE_MAKER_FEE_PCT = 0.35;
export const BINANCE_P2P_TAKER_FEE_PCT = 0;
export const VENEZUELA_INTERBANK_FEE_PCT = 0.3;

export const MERCHANT_TIERS: readonly MerchantTierConfig[] = [
  {
    id: "STANDARD",
    label: "Estándar",
    shortLabel: "Normal",
    discountPct: 0,
    requirementHint: "Sin descuento VIP (tarifa base Maker)",
  },
  {
    id: "BRONZE",
    label: "Bronce",
    shortLabel: "Bronce",
    discountPct: 20,
    requirementHint: "Comerciante Verificado Bronce (-20% Maker)",
  },
  {
    id: "SILVER",
    label: "Plata",
    shortLabel: "Plata",
    discountPct: 30,
    requirementHint: "Comerciante Verificado Plata (-30% Maker)",
  },
  {
    id: "GOLD",
    label: "Oro",
    shortLabel: "Oro",
    discountPct: 50,
    requirementHint: "Comerciante Verificado Oro (-50% Maker)",
  },
  {
    id: "CUSTOM",
    label: "Personalizado",
    shortLabel: "Manual",
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
  bankTransferType: BankTransferType;
  merchantTier: MerchantTier;
  baseMakerFeePct?: number;
  customMakerFeePct?: number;
  cyclesPerDay: number;
  bcvUsd?: number;
}

export interface P2PCycleSimulation {
  effectiveMakerFeePct: number;
  leg1FeePct: number;
  leg2FeePct: number;
  bankFeePct: number;
  totalVesInvested: number;
  bankFeeVes: number;
  usdtAfterBuyFee: number;
  buyFeeUsdt: number;
  sellFeeUsdt: number;
  totalBinanceFeeUsdt: number;
  totalBinanceFeeVes: number;
  breakEvenSellRate: number;
  grossVesOut: number;
  netProfitVes: number;
  netProfitUsdt: number;
  netProfitBcvUsd: number;
  netRoiPct: number;
  dailyProfitUsdt: number;
  dailyProfitVes: number;
  weeklyProfitUsdt: number;
  monthlyProfitUsdt: number;
  compoundDailyUsdt: number;
  vipSavingsVes: number;
  vipSavingsUsdt: number;
  monthlyVipSavingsUsdt: number;
}

function computeRawCycle(input: P2PCycleInput) {
  const validCapital = Math.max(0, input.capitalUsdt || 0);
  const validBuy = Math.max(0.01, input.buyRate || 0.01);
  const validSell = Math.max(0.01, input.sellRate || 0.01);
  const cycles = Math.max(1, Math.round(input.cyclesPerDay || 1));

  const effectiveMakerFeePct = getEffectiveMakerFeePct(
    input.merchantTier,
    input.baseMakerFeePct ?? DEFAULT_VES_BASE_MAKER_FEE_PCT,
    input.customMakerFeePct ?? DEFAULT_VES_BASE_MAKER_FEE_PCT
  );

  const leg1FeePct =
    input.buyRole === "MAKER" ? effectiveMakerFeePct : BINANCE_P2P_TAKER_FEE_PCT;
  const leg2FeePct =
    input.sellRole === "MAKER" ? effectiveMakerFeePct : BINANCE_P2P_TAKER_FEE_PCT;
  const bankFeePct =
    input.bankTransferType === "SAME_BANK" ? 0 : VENEZUELA_INTERBANK_FEE_PCT;

  const leg1FeeRate = leg1FeePct / 100;
  const leg2FeeRate = leg2FeePct / 100;
  const bankFeeRate = bankFeePct / 100;

  // Paso 1: Desembolso VES para comprar `validCapital` USDT brutos
  const baseVesIn = validCapital * validBuy;
  const bankFeeVes = baseVesIn * bankFeeRate;
  const totalVesInvested = baseVesIn + bankFeeVes;

  // USDT netos acreditados tras comisión de pierna 1
  const usdtAfterBuyFee = validCapital * (1 - leg1FeeRate);
  const buyFeeUsdt = validCapital - usdtAfterBuyFee;

  // Paso 3: Liquidación de USDT netos a Bolívares en pierna 2
  const usdtSoldEffective = usdtAfterBuyFee * (1 - leg2FeeRate);
  const sellFeeUsdt = usdtAfterBuyFee - usdtSoldEffective;
  const totalBinanceFeeUsdt = buyFeeUsdt + sellFeeUsdt;
  const totalBinanceFeeVes = buyFeeUsdt * validBuy + sellFeeUsdt * validSell;

  // Punto de equilibrio exacto (Bs/USDT para utilidad neta = 0)
  const breakEvenSellRate =
    usdtSoldEffective > 0 ? totalVesInvested / usdtSoldEffective : 0;

  const grossVesOut = usdtSoldEffective * validSell;
  const netProfitVes = grossVesOut - totalVesInvested;
  const netProfitUsdt = validSell > 0 ? netProfitVes / validSell : 0;
  const bcvUsd = input.bcvUsd || 0;
  const netProfitBcvUsd = bcvUsd > 0 ? netProfitVes / bcvUsd : 0;
  const netRoiPct =
    totalVesInvested > 0 ? (netProfitVes / totalVesInvested) * 100 : 0;

  // Proyecciones multiciclo (interés simple vs compuesto diario)
  const dailyProfitUsdt = netProfitUsdt * cycles;
  const dailyProfitVes = netProfitVes * cycles;
  const weeklyProfitUsdt = dailyProfitUsdt * 6;
  const monthlyProfitUsdt = dailyProfitUsdt * 26;

  const compoundFactor =
    netRoiPct > -99 ? Math.pow(1 + netRoiPct / 100, cycles) - 1 : 0;
  const compoundDailyUsdt = validCapital * compoundFactor;

  return {
    effectiveMakerFeePct,
    leg1FeePct,
    leg2FeePct,
    bankFeePct,
    totalVesInvested,
    bankFeeVes,
    usdtAfterBuyFee,
    buyFeeUsdt,
    sellFeeUsdt,
    totalBinanceFeeUsdt,
    totalBinanceFeeVes,
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
}

export function calculateP2PCycle(input: P2PCycleInput): P2PCycleSimulation {
  const raw = computeRawCycle(input);
  const cycles = Math.max(1, Math.round(input.cyclesPerDay || 1));

  if (input.merchantTier === "STANDARD") {
    return {
      ...raw,
      vipSavingsVes: 0,
      vipSavingsUsdt: 0,
      monthlyVipSavingsUsdt: 0,
    };
  }

  const baseline = computeRawCycle({
    ...input,
    merchantTier: "STANDARD",
  });
  const vipSavingsVes = raw.netProfitVes - baseline.netProfitVes;
  const vipSavingsUsdt = raw.netProfitUsdt - baseline.netProfitUsdt;
  const monthlyVipSavingsUsdt = vipSavingsUsdt * cycles * 26;

  return {
    ...raw,
    vipSavingsVes,
    vipSavingsUsdt,
    monthlyVipSavingsUsdt,
  };
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
