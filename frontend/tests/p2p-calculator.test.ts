import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_VES_BASE_MAKER_FEE_PCT,
  calculateP2PCycle,
  compareMerchantTiers,
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
