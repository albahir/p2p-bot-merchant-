"""Test suite for Challenger M1_1: Mathematical & Macro Model Challenge.

Empirically validates:
1. Activation and exponential half-life decay functions over 1h, 12h, 24h, 72h, 168h.
2. Vectorial forces F_net, F_gross, directional coherence Coh, coverage Cov.
3. Confidence calibration under conflicting signals (bounding under 65-70%).
4. Edge cases (zero events, extreme inputs, stale news >7 days) degrading gracefully to ESTABLE/NEUTRAL.
5. Pydantic v2 schemas defined in docs/macro_usdt_taxonomy.md.
"""

import math
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError, field_validator

# ============================================================================
# Canonical Definitions from docs/macro_usdt_taxonomy.md
# ============================================================================

TAXONOMY_14_EVENTS = [
    # code, dir, weight, latency_h, half_life_h
    ("EVT_PATRIA_GUERRA_ACTIVOS", 1.0, 0.90, 1.0, 36.0),
    ("EVT_PATRIA_GUERRA_JUBILADOS", 1.0, 0.65, 2.0, 24.0),
    ("EVT_PATRIA_AGUINALDOS_FRAC", 1.0, 1.00, 1.5, 72.0),
    ("EVT_BCV_INTERVENCION_REGULAR", -1.0, 0.70, 2.0, 36.0),
    ("EVT_BCV_INTERVENCION_AGRESIVA", -1.0, 0.95, 1.0, 48.0),
    ("EVT_BCV_INTERVENCION_DEFICIT", 1.0, 0.85, 3.0, 40.0),
    ("EVT_BCV_LIQUIDEZ_M2_SPIKE", 1.0, 0.60, 12.0, 96.0),
    ("EVT_SENIAT_PAGO_QUINCENA", -1.0, 0.65, 0.5, 24.0),
    ("EVT_SENIAT_ZAFRA_ISLR_MAR", -1.0, 0.85, 24.0, 120.0),
    ("EVT_SUDEBAN_LUNES_BANCARIO", 0.0, 0.50, 0.0, 18.0),
    ("EVT_OFAC_LICENCIA_RENOVADA", -1.0, 0.90, 2.0, 168.0),
    ("EVT_OFAC_LICENCIA_REVOCADA", 1.0, 1.00, 1.0, 240.0),
    ("EVT_REGULACION_FISCALIZACION", 1.0, 0.70, 4.0, 48.0),
    ("EVT_CAIDA_PAGO_MOVIL_NAC", 0.0, 0.55, 0.1, 6.0),
]


def calc_activation(dt: float, latency: float) -> float:
    """Activation function alpha_i(delta_t_i)."""
    if latency > 0.0 and dt < latency:
        return max(0.0, dt / latency)
    return 1.0


def calc_decay(dt: float, latency: float, half_life: float) -> float:
    """Exponential half-life decay function D_i(delta_t_i)."""
    decay_dt = max(0.0, dt - latency)
    return math.exp(-(math.log(2) / half_life) * decay_dt)


def compute_vectorial_state(
    events: list[dict[str, Any]],
    omega_ref: float = 1.50,
    theta: float = 0.25,
    gamma1: float = 0.65,
    gamma2: float = 0.35,
) -> dict[str, Any]:
    """Compute aggregate macroeconomic vector, coherence, coverage, and confidence."""
    f_net = 0.0
    f_gross = 0.0

    for ev in events:
        d = ev["d"]
        w = ev["w"]
        c = ev.get("c", 1.0)
        dt = ev["dt"]
        lat = ev["L"]
        hl = ev["h"]

        alpha = calc_activation(dt, lat)
        d_decay = calc_decay(dt, lat, hl)

        fi = d * w * c * alpha * d_decay
        gi = w * c * alpha * d_decay

        f_net += fi
        f_gross += gi

    coh = (abs(f_net) / f_gross) if f_gross > 0.0 else 0.0
    cov = min(1.0, f_gross / omega_ref) if omega_ref > 0.0 else 0.0

    c_additive = (gamma1 * coh + gamma2 * cov) * 100.0
    c_mult = 100.0 * coh * cov

    if f_net > theta:
        direction = "SUBE"
    elif f_net < -theta:
        direction = "BAJA"
    else:
        direction = "ESTABLE"

    flags = []
    c_final = c_additive

    # Safeguards
    if f_gross >= 1.00 and coh < 0.20:
        direction = "ESTABLE"
        c_final = min(c_final, 45.0)
        flags.append("HIGH_AMBIGUITY_COLLIDING_FORCES")

    if f_gross < 0.20:
        direction = "ESTABLE"
        c_final = min(c_final, 35.0)
        flags.append("INSUFFICIENT_MACRO_EVIDENCE")

    return {
        "f_net": f_net,
        "f_gross": f_gross,
        "coh": coh,
        "cov": cov,
        "c_additive": c_additive,
        "c_mult": c_mult,
        "c_final": c_final,
        "direction": direction,
        "flags": flags,
    }


# ============================================================================
# Pydantic v2 Schemas from Section 7
# ============================================================================


class MacroCategoryEnum(str, Enum):
    GASTO_PUBLICO_PATRIA = "GASTO_PUBLICO_PATRIA"
    INTERVENCION_CAMBIARIA_BCV = "INTERVENCION_CAMBIARIA_BCV"
    POLITICA_MONETARIA_LIQUIDEZ = "POLITICA_MONETARIA_LIQUIDEZ"
    CALENDARIO_FISCAL_SENIAT = "CALENDARIO_FISCAL_SENIAT"
    REGULACION_CAMBIARIA_BANCARIA = "REGULACION_CAMBIARIA_BANCARIA"
    OPERATIVA_MERCADO_P2P = "OPERATIVA_MERCADO_P2P"
    GEOPOLITICA_PETROLERA = "GEOPOLITICA_PETROLERA"


class DirectionEnum(str, Enum):
    SUBE = "SUBE"
    BAJA = "BAJA"
    ESTABLE = "ESTABLE"


class CriticalityEnum(str, Enum):
    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


class ImpactWindowEnum(str, Enum):
    INMEDIATO_0_6H = "INMEDIATO_0_6H"
    CORTO_PLAZO_24H = "CORTO_PLAZO_24H"
    MEDIANO_PLAZO_72H = "MEDIANO_PLAZO_72H"
    SEMANAL_TENDENCIAL = "SEMANAL_TENDENCIAL"


class MacroEventItem(BaseModel):
    event_id: str = Field(..., description="Identificador único, ej. EVT-202611-BCV-INT-001")
    code: str = Field(..., description="Código canónico de la taxonomía de 14 eventos")
    category: MacroCategoryEnum
    name: str = Field(..., min_length=5, max_length=150)
    trigger_timestamp_utc: datetime
    source_name: str
    source_channel: str
    source_confidence: float = Field(ge=0.0, le=1.0)
    criticality: CriticalityEnum
    base_weight: float = Field(ge=0.10, le=1.00)
    vector_direction: int = Field(
        ..., description="+1 para alcista, -1 para bajista, 0 para neutral"
    )
    latency_hours: float = Field(ge=0.0)
    half_life_hours: float = Field(gt=0.0)
    expected_window: ImpactWindowEnum
    summary_verified: str = Field(..., max_length=500)
    raw_attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("vector_direction")
    @classmethod
    def validate_direction(cls, v: int) -> int:
        if v not in (-1, 0, 1):
            raise ValueError("vector_direction debe ser -1, 0 o 1")
        return v


class MarketRateSnapshot(BaseModel):
    timestamp_utc: datetime
    p2p_rate_ves: float = Field(gt=0.0)
    bcv_rate_ves: float = Field(gt=0.0)
    brecha_porcentual: float
    spread_banesco_pct: float | None = None
    spread_bdv_pct: float | None = None


class VectorialMacroAnalysis(BaseModel):
    active_events_count: int
    gross_force: float
    net_force: float
    directional_coherence: float = Field(ge=0.0, le=1.0)
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    calibrated_confidence_pct: float = Field(ge=0.0, le=100.0)
    dominant_direction: DirectionEnum
    warning_flags: list[str] = Field(default_factory=list)


# ============================================================================
# Tests
# ============================================================================


class TestMacroModelEmpiricalValidation:
    """Empirical stress tests for macro model equations, decay, and calibration."""

    def test_decay_across_horizons(self):
        """Verify exponential decay D_i over 1h, 12h, 24h, 72h, 168h."""
        for code, d, w, lat, hl in TAXONOMY_14_EVENTS:
            # At t <= lat, decay factor must be exactly 1.0 (pre-decay)
            d_at_lat = calc_decay(lat, lat, hl)
            assert math.isclose(d_at_lat, 1.0, rel_tol=1e-6), f"{code}: D at latency must be 1.0"

            # At t = lat + hl, decay factor must be exactly 0.5 (half-life definition)
            d_at_one_hl = calc_decay(lat + hl, lat, hl)
            assert math.isclose(d_at_one_hl, 0.5, rel_tol=1e-6), (
                f"{code}: D at 1 half-life must be 0.5"
            )

            # At t = lat + 2*hl, decay factor must be 0.25
            d_at_two_hl = calc_decay(lat + 2 * hl, lat, hl)
            assert math.isclose(d_at_two_hl, 0.25, rel_tol=1e-6), (
                f"{code}: D at 2 half-lives must be 0.25"
            )

            # Decay must be monotonically non-increasing
            d_prev = 1.0
            for t in [1.0, 12.0, 24.0, 72.0, 168.0]:
                d_curr = calc_decay(t, lat, hl)
                assert 0.0 <= d_curr <= 1.0
                assert d_curr <= d_prev + 1e-9, f"{code}: Decay must not increase over time"
                d_prev = d_curr

    def test_fast_decay_events(self):
        """Events like interbank payment outage (h=6h) must extinguish in 24-72h."""
        # EVT_CAIDA_PAGO_MOVIL_NAC: L=0.1, h=6.0
        d_24 = calc_decay(24.0, 0.1, 6.0)
        d_72 = calc_decay(72.0, 0.1, 6.0)
        assert d_24 < 0.07, "Payment outage should be >93% decayed at 24h"
        assert d_72 < 0.0003, "Payment outage should be >99.9% decayed at 72h"

    def test_slow_decay_events(self):
        """Structural shocks like OFAC license revoked (h=240h) must maintain >60% after 7 days."""
        # EVT_OFAC_LICENCIA_REVOCADA: L=1.0, h=240.0
        d_168 = calc_decay(168.0, 1.0, 240.0)
        assert d_168 > 0.60, f"OFAC shock at 7 days must maintain >60%, got {d_168:.3f}"

    def test_conflicting_signals_bcv_vs_patria(self):
        """Conflicting signals (BCV intervention vs Patria bonus) must bound confidence < 70%."""
        # Scenario: BCV Regular (d=-1, w=0.70, c=1.0, L=2.0, h=36) vs Patria Activos (d=+1, w=0.90, c=1.0, L=1.0, h=36)
        # Evaluated at t=2.0h (both forces fully ramped up)
        ev_patria = {"d": 1.0, "w": 0.90, "c": 1.0, "dt": 2.0, "L": 1.0, "h": 36.0}
        ev_bcv = {"d": -1.0, "w": 0.70, "c": 1.0, "dt": 2.0, "L": 2.0, "h": 36.0}

        res = compute_vectorial_state([ev_patria, ev_bcv])

        # F_net should be small positive (+0.18)
        assert 0.0 < res["f_net"] < 0.25, f"Expected F_net near +0.18, got {res['f_net']}"
        # Coherence should be low (~0.116)
        assert res["coh"] < 0.20, f"Expected low coherence due to conflict, got {res['coh']}"
        # Direction should be ESTABLE (since |F_net| <= 0.25 or via HIGH_AMBIGUITY flag)
        assert res["direction"] == "ESTABLE"
        # Confidence must be bounded under 65% in both additive and multiplicative
        assert res["c_additive"] <= 45.0 or res["c_final"] <= 45.0
        assert res["c_mult"] < 20.0
        assert "HIGH_AMBIGUITY_COLLIDING_FORCES" in res["flags"]

    def test_conflicting_signals_aguinaldo_vs_bcv_shock(self):
        """Massive conflicting signals (Aguinaldos w=1.0 vs BCV Shock w=0.95)."""
        ev_aguinaldo = {"d": 1.0, "w": 1.00, "c": 1.0, "dt": 2.0, "L": 1.5, "h": 72.0}
        ev_bcv_shock = {"d": -1.0, "w": 0.95, "c": 1.0, "dt": 2.0, "L": 1.0, "h": 48.0}

        res = compute_vectorial_state([ev_aguinaldo, ev_bcv_shock])

        # Near perfect cancellation: F_net ~ +0.06
        assert abs(res["f_net"]) < 0.10
        # High gross force (~1.93)
        assert res["f_gross"] > 1.80
        # Severe conflict: coherence < 0.05
        assert res["coh"] < 0.05
        # Direction forced to ESTABLE
        assert res["direction"] == "ESTABLE"
        # Calibrated confidence capped <= 45% (specifically ~37%)
        assert res["c_final"] <= 45.0
        assert "HIGH_AMBIGUITY_COLLIDING_FORCES" in res["flags"]

    def test_edge_case_zero_events(self):
        """Zero events must degrade gracefully to ESTABLE with zero division safety."""
        res = compute_vectorial_state([])
        assert res["f_net"] == 0.0
        assert res["f_gross"] == 0.0
        assert res["coh"] == 0.0
        assert res["cov"] == 0.0
        assert res["c_final"] == 0.0
        assert res["direction"] == "ESTABLE"
        assert "INSUFFICIENT_MACRO_EVIDENCE" in res["flags"]

    def test_edge_case_extreme_inputs(self):
        """Extreme inputs (10x bullish w=1.0) must not cause overflow or >100% confidence."""
        extreme_events = [
            {"d": 1.0, "w": 1.0, "c": 1.0, "dt": 2.0, "L": 1.0, "h": 72.0} for _ in range(10)
        ]
        res = compute_vectorial_state(extreme_events)
        assert res["f_net"] > 9.0
        assert res["coh"] == 1.0
        assert res["cov"] == 1.0
        assert res["c_final"] == 100.0
        assert res["direction"] == "SUBE"

    def test_edge_case_stale_news(self):
        """Stale news (>7 days / 168h) must degrade into INSUFFICIENT_MACRO_EVIDENCE."""
        stale_events = [
            {"d": 1.0, "w": 0.90, "c": 1.0, "dt": 200.0, "L": 1.0, "h": 36.0},
            {"d": -1.0, "w": 0.70, "c": 1.0, "dt": 200.0, "L": 2.0, "h": 36.0},
        ]
        res = compute_vectorial_state(stale_events)
        assert res["f_gross"] < 0.10, "Gross force should be nearly zero after 200h"
        assert res["direction"] == "ESTABLE"
        assert res["c_final"] <= 35.0
        assert "INSUFFICIENT_MACRO_EVIDENCE" in res["flags"]

    def test_vulnerability_negative_delta_t(self):
        """Demonstrate mathematical vulnerability if dt < 0 in naive implementation."""
        dt_future = -4.0  # Event scheduled in 4 hours
        latency = 8.0

        # Naive implementation without max(0, dt):
        naive_alpha = dt_future / latency
        assert naive_alpha < 0, "Naive alpha produces negative value for future event"
        # Inverted force sign:
        inverted_force = (+1.0) * 0.90 * naive_alpha
        assert inverted_force < 0, "Bullish event became bearish because dt < 0!"

        # Defensive implementation with max(0, dt):
        safe_alpha = calc_activation(dt_future, latency)
        assert safe_alpha == 0.0, "Defensive activation must be 0.0 for future event"


class TestPydanticSchemasValidation:
    """Validation of Pydantic v2 schemas defined in docs/macro_usdt_taxonomy.md."""

    def test_valid_macro_event_item(self):
        item = MacroEventItem(
            event_id="EVT-202611-BCV-INT-001",
            code="EVT_BCV_INTERVENCION_REGULAR",
            category=MacroCategoryEnum.INTERVENCION_CAMBIARIA_BCV,
            name="Intervención Cambiaria Regular Semanal",
            trigger_timestamp_utc=datetime.now(UTC),
            source_name="BCV Oficial",
            source_channel="bcv.org.ve",
            source_confidence=1.0,
            criticality=CriticalityEnum.ALTO,
            base_weight=0.70,
            vector_direction=-1,
            latency_hours=2.0,
            half_life_hours=36.0,
            expected_window=ImpactWindowEnum.CORTO_PLAZO_24H,
            summary_verified="Asignación regular de $70M a bancos",
            raw_attributes={"amount_usd": 70000000},
        )
        assert item.code == "EVT_BCV_INTERVENCION_REGULAR"
        assert item.vector_direction == -1
        assert item.base_weight == 0.70

    def test_invalid_vector_direction_rejection(self):
        with pytest.raises(ValidationError):
            MacroEventItem(
                event_id="EVT-002",
                code="EVT_PATRIA_GUERRA_ACTIVOS",
                category=MacroCategoryEnum.GASTO_PUBLICO_PATRIA,
                name="Bono Guerra",
                trigger_timestamp_utc=datetime.now(UTC),
                source_name="Patria",
                source_channel="Telegram",
                source_confidence=0.9,
                criticality=CriticalityEnum.ALTO,
                base_weight=0.9,
                vector_direction=2,  # Invalid: only -1, 0, 1 allowed
                latency_hours=1.0,
                half_life_hours=36.0,
                expected_window=ImpactWindowEnum.CORTO_PLAZO_24H,
                summary_verified="Bono guerra activo",
            )

    def test_invalid_base_weight_rejection(self):
        with pytest.raises(ValidationError):
            MacroEventItem(
                event_id="EVT-003",
                code="EVT_PATRIA_GUERRA_ACTIVOS",
                category=MacroCategoryEnum.GASTO_PUBLICO_PATRIA,
                name="Bono Guerra",
                trigger_timestamp_utc=datetime.now(UTC),
                source_name="Patria",
                source_channel="Telegram",
                source_confidence=0.9,
                criticality=CriticalityEnum.ALTO,
                base_weight=1.5,  # Invalid: max 1.00
                vector_direction=1,
                latency_hours=1.0,
                half_life_hours=36.0,
                expected_window=ImpactWindowEnum.CORTO_PLAZO_24H,
                summary_verified="Bono guerra activo",
            )

    def test_market_rate_snapshot_validation(self):
        snapshot = MarketRateSnapshot(
            timestamp_utc=datetime.now(UTC),
            p2p_rate_ves=54.20,
            bcv_rate_ves=46.50,
            brecha_porcentual=((54.20 - 46.50) / 46.50) * 100.0,
            spread_banesco_pct=0.6,
            spread_bdv_pct=1.1,
        )
        assert snapshot.brecha_porcentual > 16.0
        assert snapshot.p2p_rate_ves > 0

        # Negative rate must be rejected
        with pytest.raises(ValidationError):
            MarketRateSnapshot(
                timestamp_utc=datetime.now(UTC),
                p2p_rate_ves=-10.0,
                bcv_rate_ves=46.50,
                brecha_porcentual=0.0,
            )

    def test_vectorial_analysis_schema(self):
        analysis = VectorialMacroAnalysis(
            active_events_count=2,
            gross_force=1.85,
            net_force=0.10,
            directional_coherence=0.054,
            evidence_coverage=1.0,
            calibrated_confidence_pct=38.5,
            dominant_direction=DirectionEnum.ESTABLE,
            warning_flags=["HIGH_AMBIGUITY_COLLIDING_FORCES"],
        )
        assert analysis.dominant_direction == DirectionEnum.ESTABLE
        assert analysis.calibrated_confidence_pct == 38.5
