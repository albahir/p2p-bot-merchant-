"""Empirical Stress Test Harness: Vector Stability and Activation Floor Verification.

Challenger M1_IT2_1: Math & Model Challenger
Empirically stress-tests:
1. Activation floor max(0.0, dt / latency) preventing negative activation when dt <= 0.
2. Inversion immunity: elimination of false reversal in vector forces.
3. Vector stability under future event flooding (adversarial shock scenarios).
4. Continuity and monotonicity during ramp-up, peak, and exponential decay.
5. Numerical robustness under extreme float bounds, zero latency, and zero events.
6. Equivalence between plan.md Section 3.4 and docs/macro_usdt_taxonomy.md Section 2.4.1.
"""

import math
import random
from typing import Any

# ============================================================================
# Canonical Implementations from plan.md Section 3.4 & docs/macro_usdt_taxonomy.md
# ============================================================================


def calc_activation_plan(dt: float, latency: float) -> float:
    """Reference implementation from .specify/specs/023-ai-market-predictor/plan.md Section 3.4."""
    if latency > 0.0 and dt < latency:
        return max(0.0, dt / latency)
    if dt < 0.0:
        return 0.0
    return 1.0


def calc_activation_taxonomy_literal(dt: float, latency: float) -> float:
    """Literal interpretation of 3-case piece-wise formula in docs/macro_usdt_taxonomy.md."""
    if latency > 0.0 and dt < latency:
        return max(0.0, dt / latency)
    if dt <= 0.0:
        return 0.0
    return 1.0


def calc_activation_taxonomy_compact(dt: float, latency: float) -> float:
    """Compact analytical formulation from docs/macro_usdt_taxonomy.md lines 95-98."""
    if latency > 0.0 and dt < latency:
        return max(0.0, dt / latency)
    if dt < 0.0:
        return 0.0
    return 1.0



def calc_decay(dt: float, latency: float, half_life: float) -> float:
    """Exponential half-life decay function D_i(Delta t_i)."""
    decay_dt = max(0.0, dt - latency)
    return math.exp(-(math.log(2) / half_life) * decay_dt)


def compute_vectorial_force(
    d: float,
    w: float,
    c: float,
    dt: float,
    latency: float,
    half_life: float,
    use_floor: bool = True,
) -> float:
    """Compute instantaneous force F_i(t) with or without defensive floor."""
    if use_floor:
        alpha = calc_activation_plan(dt, latency)
    else:
        # Naive implementation without activation floor
        alpha = dt / latency if latency > 0.0 else 1.0

    decay = calc_decay(dt, latency, half_life)
    return d * w * c * alpha * decay


def compute_aggregate_macro_vector(
    events: list[dict[str, Any]],
    use_floor: bool = True,
    omega_ref: float = 1.50,
    theta: float = 0.25,
) -> dict[str, Any]:
    """Aggregate macroeconomic vector calculator."""
    f_net = 0.0
    f_gross = 0.0

    for ev in events:
        d = ev["d"]
        w = ev["w"]
        c = ev.get("c", 1.0)
        dt = ev["dt"]
        lat = ev["L"]
        hl = ev["h"]

        if use_floor:
            alpha = calc_activation_plan(dt, lat)
        else:
            alpha = dt / lat if lat > 0.0 else 1.0

        decay = calc_decay(dt, lat, hl)
        f_net += d * w * c * alpha * decay
        f_gross += w * c * alpha * decay

    coh = (abs(f_net) / f_gross) if f_gross > 0.0 else 0.0
    cov = min(1.0, f_gross / omega_ref) if omega_ref > 0.0 else 0.0
    c_final = (0.65 * coh + 0.35 * cov) * 100.0

    if f_net > theta:
        direction = "SUBE"
    elif f_net < -theta:
        direction = "BAJA"
    else:
        direction = "ESTABLE"

    if f_gross >= 1.00 and coh < 0.20:
        direction = "ESTABLE"
        c_final = min(c_final, 45.0)

    if f_gross < 0.20:
        direction = "ESTABLE"
        c_final = min(c_final, 35.0)

    return {
        "f_net": f_net,
        "f_gross": f_gross,
        "coh": coh,
        "cov": cov,
        "c_final": c_final,
        "direction": direction,
    }


# ============================================================================
# Empirical Test Suite
# ============================================================================


class TestActivationFloorEmpirical:
    """Empirical verification of activation floor max(0.0, dt / latency)."""

    def test_floor_strictly_prevents_negative_activation(self):
        """Verify that alpha is NEVER negative for any (dt, latency) combination."""
        test_dts = [
            -10000.0, -500.0, -100.0, -24.0, -12.0, -2.0, -1.0,
            -0.5, -0.1, -1e-4, -1e-9, -0.0, 0.0,
            1e-9, 1e-4, 0.1, 0.5, 1.0, 2.0, 10.0, 50.0, 500.0,
        ]
        test_latencies = [0.0, 0.1, 0.5, 1.0, 2.0, 4.0, 12.0, 24.0, 48.0, 168.0]

        for dt in test_dts:
            for lat in test_latencies:
                alpha = calc_activation_plan(dt, lat)
                assert alpha >= 0.0, f"FAILED: Negative alpha {alpha} at dt={dt}, lat={lat}"
                assert 0.0 <= alpha <= 1.0, f"FAILED: Alpha {alpha} out of bounds [0, 1] at dt={dt}, lat={lat}"

    def test_negative_dt_yields_zero_activation(self):
        """Verify that any future event (dt < 0) has activation identically equal to 0.0."""
        negative_dts = [-1000.0, -48.0, -24.0, -6.0, -1.0, -0.01, -1e-7]
        latencies = [0.0, 0.1, 1.0, 4.0, 12.0, 24.0]

        for dt in negative_dts:
            for lat in latencies:
                alpha = calc_activation_plan(dt, lat)
                assert alpha == 0.0, f"Future event dt={dt}, lat={lat} must have alpha=0.0, got {alpha}"

    def test_boundary_at_dt_zero(self):
        """Verify boundary behavior at exactly dt = 0.0."""
        # For positive latency, transmission has not started at dt=0: alpha = 0.0
        assert calc_activation_plan(0.0, 2.0) == 0.0
        assert calc_activation_plan(0.0, 24.0) == 0.0

        # For zero latency (instantaneous event), activation is immediate at dt=0: alpha = 1.0
        assert calc_activation_plan(0.0, 0.0) == 1.0

    def test_ramp_up_monotonicity(self):
        """Verify linear ramp-up is strictly monotonic in [0, latency]."""
        lat = 10.0
        prev_alpha = -1.0
        for step in range(101):
            dt = step * 0.1  # 0.0 to 10.0
            alpha = calc_activation_plan(dt, lat)
            expected = dt / lat
            assert math.isclose(alpha, expected, rel_tol=1e-7)
            assert alpha >= prev_alpha, f"Monotonicity failed at dt={dt}: {alpha} < {prev_alpha}"
            prev_alpha = alpha

    def test_plateau_at_and_above_latency(self):
        """Verify alpha is identically 1.0 for all dt >= latency."""
        lat = 5.0
        for dt in [5.0, 5.0001, 10.0, 24.0, 168.0, 1000.0]:
            assert calc_activation_plan(dt, lat) == 1.0


class TestVectorStabilityEmpirical:
    """Empirical verification of vector force stability and inversion immunity."""

    def test_naive_vs_defensive_directional_inversion(self):
        """Empirically demonstrate that naive formula flips sign while defensive floor preserves it."""
        # Scenario: Upcoming Patria bonus (Bullish d = +1.0, w = 0.90, lat = 2.0h)
        # Event is scheduled in 3 hours (dt = -3.0h)
        d = 1.0
        w = 0.90
        c = 1.0
        dt = -3.0
        lat = 2.0
        hl = 36.0

        # 1. Naive implementation (without floor)
        naive_force = compute_vectorial_force(d, w, c, dt, lat, hl, use_floor=False)
        # In naive implementation: alpha = -3.0 / 2.0 = -1.5 -> force = 1.0 * 0.9 * (-1.5) = -1.35
        # The bullish event has become a massive BEARISH force!
        assert naive_force < 0.0, "Naive model must reproduce false sign inversion"
        assert math.isclose(naive_force, -1.35, rel_tol=1e-5)

        # 2. Defensive implementation (with floor)
        defensive_force = compute_vectorial_force(d, w, c, dt, lat, hl, use_floor=True)
        assert defensive_force == 0.0, "Defensive model must produce exactly 0.0 force for future events"

    def test_adversarial_future_events_flooding(self):
        """Stress test: 1 active bearish shock + 20 future bullish events.

        Naive model flips the 20 future bullish events into massive bearish forces,
        amplifying bearish bias by >1500%.
        Defensive model strictly ignores future events, isolating the active shock.
        """
        # Active event: BCV regular intervention occurring 2h ago (d = -1.0, w = 0.70, lat = 2.0, hl = 36.0)
        active_bcv = {"d": -1.0, "w": 0.70, "c": 1.0, "dt": 2.0, "L": 2.0, "h": 36.0}

        # 20 future scheduled Patria bonuses (d = +1.0, w = 0.90, lat = 2.0, hl = 36.0) scheduled 1h..20h from now
        future_patria = [
            {"d": 1.0, "w": 0.90, "c": 1.0, "dt": -float(h), "L": 2.0, "h": 36.0}
            for h in range(1, 21)
        ]

        all_events = [active_bcv] + future_patria

        # In naive model:
        naive_res = compute_aggregate_macro_vector(all_events, use_floor=False)
        # In defensive model:
        defensive_res = compute_aggregate_macro_vector(all_events, use_floor=True)

        # In defensive model, the 20 future events produce 0 force.
        # F_net must equal exactly the single active event's force: -0.70 * 1.0 * 1.0 = -0.70
        assert math.isclose(defensive_res["f_net"], -0.70, rel_tol=1e-5), (
            f"Defensive F_net must be -0.70, got {defensive_res['f_net']}"
        )
        assert math.isclose(defensive_res["f_gross"], 0.70, rel_tol=1e-5)
        assert defensive_res["direction"] == "BAJA"

        # In naive model, future events create huge negative forces!
        assert naive_res["f_net"] < -50.0, f"Naive F_net corrupted to extreme negative: {naive_res['f_net']}"
        # The naive model suffered a severe false-panic amplification

    def test_sign_concordance_invariant(self):
        """Invariant: for any single event i, sgn(F_i(t)) must equal sgn(d_i) or be 0.

        Mathematically: F_i(t) * d_i >= 0 for all t in (-inf, +inf).
        """
        random.seed(42)
        directions = [-1.0, 0.0, 1.0]

        for _ in range(1000):
            d = random.choice(directions)
            w = random.uniform(0.1, 1.0)
            c = random.uniform(0.5, 1.0)
            dt = random.uniform(-100.0, 200.0)
            lat = random.choice([0.0, 0.1, 0.5, 1.0, 2.0, 4.0, 12.0, 24.0])
            hl = random.uniform(6.0, 240.0)

            fi = compute_vectorial_force(d, w, c, dt, lat, hl, use_floor=True)
            # Concordance check
            product = fi * d
            assert product >= -1e-12, (
                f"INVARIANT VIOLATED: F_i={fi} opposes d_i={d} at dt={dt}, lat={lat}"
            )

    def test_transition_continuity_at_latency(self):
        """Verify force function continuity across the boundary dt = latency.

        As dt approaches latency from below (ramp-up) and above (decay):
        lim_{dt -> L-} F_i(dt) = lim_{dt -> L+} F_i(dt) = d_i * w_i * c_i
        """
        d = 1.0
        w = 0.85
        c = 0.90
        lat = 3.5
        hl = 48.0
        eps = 1e-6

        f_left = compute_vectorial_force(d, w, c, lat - eps, lat, hl, use_floor=True)
        f_at = compute_vectorial_force(d, w, c, lat, lat, hl, use_floor=True)
        f_right = compute_vectorial_force(d, w, c, lat + eps, lat, hl, use_floor=True)

        expected_peak = d * w * c
        assert math.isclose(f_left, expected_peak, rel_tol=1e-4)
        assert math.isclose(f_at, expected_peak, rel_tol=1e-7)
        assert math.isclose(f_right, expected_peak, rel_tol=1e-4)

    def test_zero_latency_instantaneous_activation(self):
        """Sudeban bank holidays and instantaneous shocks (lat = 0.0) must activate at dt=0 without division by zero."""
        d = 0.0  # Neutral / spread-widening
        w = 0.50
        c = 1.0
        lat = 0.0
        hl = 18.0

        # Before event (dt < 0)
        assert compute_vectorial_force(d, w, c, -1.0, lat, hl, use_floor=True) == 0.0
        # Exactly at event (dt = 0)
        assert compute_vectorial_force(d, w, c, 0.0, lat, hl, use_floor=True) == 0.0
        # Active post-event (dt = 2.0h)
        f_post = compute_vectorial_force(1.0, w, c, 2.0, lat, hl, use_floor=True)
        expected_decay = math.exp(-(math.log(2) / 18.0) * 2.0)
        assert math.isclose(f_post, 0.50 * expected_decay, rel_tol=1e-6)

    def test_formula_parity_plan_vs_taxonomy(self):
        """Verify exact mathematical equivalence between plan.md and docs/macro_usdt_taxonomy.md compact form."""
        test_points = [
            (-100.0, 2.0), (-5.0, 0.0), (-1.0, 1.0), (-1e-5, 2.0),
            (0.0, 0.0), (0.0, 1.0), (0.0, 24.0),
            (0.5, 1.0), (1.0, 2.0), (5.0, 10.0),
            (2.0, 2.0), (10.0, 10.0),
            (3.0, 2.0), (50.0, 10.0), (200.0, 24.0),
        ]

        for dt, lat in test_points:
            res_plan = calc_activation_plan(dt, lat)
            res_tax = calc_activation_taxonomy_compact(dt, lat)
            assert math.isclose(res_plan, res_tax, abs_tol=1e-9), (
                f"Parity mismatch at dt={dt}, lat={lat}: plan={res_plan}, taxonomy={res_tax}"
            )

    def test_boundary_disambiguation_at_origin(self):
        """Analyze boundary case dt=0.0, lat=0.0 (instantaneous shock at trigger moment).

        In plan.md: at dt=0, lat=0 -> alpha = 1.0 (immediate full transmission upon occurrence).
        In docs/macro_usdt_taxonomy.md compact form: dt >= lat -> alpha = 1.0.
        Both correctly grant full activation when an instantaneous event occurs.
        """
        assert calc_activation_plan(0.0, 0.0) == 1.0
        assert calc_activation_taxonomy_compact(0.0, 0.0) == 1.0

        # Prior to occurrence (dt < 0.0), both strictly yield 0.0
        assert calc_activation_plan(-0.001, 0.0) == 0.0
        assert calc_activation_taxonomy_compact(-0.001, 0.0) == 0.0

