import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_VES_BASE_MAKER_FEE_PCT,
  calculateP2PCycle,
  compareMerchantTiers,
  computeTargetRateForMargin,
  getEffectiveMakerFeePct,
} from "../src/lib/p2p-calculator";

test("effective maker fee applies official Binance P2P VIP discounts on 0.25% VES base", () => {
  assert.equal(DEFAULT_VES_BASE_MAKER_FEE_PCT, 0.25);
  assert.equal(getEffectiveMakerFeePct("STANDARD", 0.25), 0.25);
  assert.equal(getEffectiveMakerFeePct("BRONZE", 0.25), 0.2);
  assert.equal(getEffectiveMakerFeePct("SILVER", 0.25), 0.175);
  assert.equal(getEffectiveMakerFeePct("GOLD", 0.25), 0.125);
});

test("effective maker fee scales with 0.35% legacy/alternate base and custom override", () => {
  assert.equal(getEffectiveMakerFeePct("STANDARD", 0.35), 0.35);
  assert.equal(getEffectiveMakerFeePct("BRONZE", 0.35), 0.28);
  assert.equal(getEffectiveMakerFeePct("SILVER", 0.35), 0.245);
  assert.equal(getEffectiveMakerFeePct("GOLD", 0.35), 0.175);
  assert.equal(getEffectiveMakerFeePct("CUSTOM", 0.25, 0.08), 0.08);
  assert.equal(getEffectiveMakerFeePct("CUSTOM", 0.25, 0), 0);
});

test("Binance P2P roles: TAKER pays 0% fee and MAKER pays tier effective fee", () => {
  const takerBoth = calculateP2PCycle({
    capitalUsdt: 1000,
    buyRate: 100,
    sellRate: 102,
    buyRole: "TAKER",
    sellRole: "TAKER",
    bankTransferType: "SAME_BANK",
    merchantTier: "STANDARD",
    baseMakerFeePct: 0.25,
    cyclesPerDay: 3,
    bcvUsd: 100,
  });

  assert.equal(takerBoth.buyFeeUsdt, 0);
  assert.equal(takerBoth.sellFeeUsdt, 0);
  assert.equal(takerBoth.totalBinanceFeeUsdt, 0);
  assert.equal(takerBoth.netProfitVes, 2000);

  const makerBothGold = calculateP2PCycle({
    capitalUsdt: 1000,
    buyRate: 100,
    sellRate: 102,
    buyRole: "MAKER",
    sellRole: "MAKER",
    bankTransferType: "SAME_BANK",
    merchantTier: "GOLD",
    baseMakerFeePct: 0.25,
    cyclesPerDay: 3,
    bcvUsd: 100,
  });

  // 0.125% on buy (1.25 USDT) and 0.125% on remaining 998.75 USDT (~1.2484375 USDT)
  assert.ok(Math.abs(makerBothGold.buyFeeUsdt - 1.25) < 1e-6);
  assert.ok(Math.abs(makerBothGold.sellFeeUsdt - 1.2484375) < 1e-6);
  assert.ok(makerBothGold.vipSavingsVes > 0);
});

test("higher VIP tier strictly improves net profit and lowers break-even sell rate", () => {
  const comparisons = compareMerchantTiers({
    capitalUsdt: 500,
    buyRate: 1000,
    sellRate: 1015,
    buyRole: "MAKER",
    sellRole: "MAKER",
    bankTransferType: "INTERBANK_PM",
    baseMakerFeePct: 0.25,
    cyclesPerDay: 4,
    bcvUsd: 900,
  });

  assert.equal(comparisons.length, 4);
  const [std, bronze, silver, gold] = comparisons;
  assert.equal(std.tier, "STANDARD");
  assert.equal(bronze.tier, "BRONZE");
  assert.equal(silver.tier, "SILVER");
  assert.equal(gold.tier, "GOLD");

  // Break-even strictly decreases Standard > Bronze > Silver > Gold
  assert.ok(std.result.breakEvenSellRate > bronze.result.breakEvenSellRate);
  assert.ok(bronze.result.breakEvenSellRate > silver.result.breakEvenSellRate);
  assert.ok(silver.result.breakEvenSellRate > gold.result.breakEvenSellRate);

  // Net profit strictly increases Standard < Bronze < Silver < Gold
  assert.ok(std.result.netProfitVes < bronze.result.netProfitVes);
  assert.ok(bronze.result.netProfitVes < silver.result.netProfitVes);
  assert.ok(silver.result.netProfitVes < gold.result.netProfitVes);

  // Break-even identity check: selling at breakEvenSellRate produces ~0 net profit
  const atBreakEven = calculateP2PCycle({
    capitalUsdt: 500,
    buyRate: 1000,
    sellRate: gold.result.breakEvenSellRate,
    buyRole: "MAKER",
    sellRole: "MAKER",
    bankTransferType: "INTERBANK_PM",
    merchantTier: "GOLD",
    baseMakerFeePct: 0.25,
    cyclesPerDay: 4,
    bcvUsd: 900,
  });
  assert.ok(Math.abs(atBreakEven.netProfitVes) < 1e-6);
});

test("zero buyRate or sellRate returns safe incomplete state without 0.01 distortion", () => {
  const zeroBuy = calculateP2PCycle({
    capitalUsdt: 250,
    buyRate: 0,
    sellRate: 1094.99,
    buyRole: "MAKER",
    sellRole: "MAKER",
    cycleDirection: "VES_USDT_VES",
    bankTransferType: "INTERBANK_PM",
    merchantTier: "STANDARD",
    cyclesPerDay: 3,
  });

  assert.equal(zeroBuy.hasValidRates, false);
  assert.equal(zeroBuy.profitStatus, "INCOMPLETE");
  assert.equal(zeroBuy.totalVesInvested, 0);
  assert.equal(zeroBuy.netProfitUsdt, 0);
  assert.equal(zeroBuy.netRoiPct, 0);
});

test("USDT -> Bs -> USDT direction and target rate solver preserve real USDT math", () => {
  const res = calculateP2PCycle({
    capitalUsdt: 500,
    buyRate: 1080,
    sellRate: 1100,
    buyRole: "MAKER",
    sellRole: "MAKER",
    cycleDirection: "USDT_VES_USDT",
    bankTransferType: "INTERBANK_PM",
    merchantTier: "STANDARD",
    cyclesPerDay: 2,
  });

  assert.equal(res.hasValidRates, true);
  assert.ok(res.netProfitUsdt > 0);
  assert.ok(res.breakEvenRate > 1080 && res.breakEvenRate < 1100);
  // Valoración consistente de comisión Binance a tasa real (~1.248 U * 1080 Bs/U ≈ 1347 Bs, nunca la mitad)
  assert.ok(Math.abs(res.totalBinanceFeeVes - res.totalBinanceFeeUsdt * 1080) < 0.01);

  const targetBuy = computeTargetRateForMargin(
    {
      capitalUsdt: 500,
      buyRate: 1080,
      sellRate: 1100,
      buyRole: "MAKER",
      sellRole: "MAKER",
      cycleDirection: "USDT_VES_USDT",
      bankTransferType: "INTERBANK_PM",
      merchantTier: "STANDARD",
      cyclesPerDay: 2,
    },
    1.0,
    "BUY"
  );
  assert.ok(targetBuy > 0 && targetBuy < res.breakEvenRate);
});
