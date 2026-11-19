"""Test suite for Challenger M1_IT2_2: Remediation Verification Challenger.

Empirically challenges and verifies that all 5 issues raised by Challenger 2 are resolved:
1. TaxonomyCategory enum validation: All 7 prompt categories instantiate without ValidationError.
2. Delimiter collision in SHA-256: Pipe-delimited chaining formula prevents boundary bleed.
3. Contract enums across tasks.md and plan.md: Full consistency and absence of legacy enums.
4. Confidence capping validator: CORREGIDO and AJUSTADO_FAIL_CLOSED strictly capped at <= 75.0%.
5. ASCII field: MacroEventItem uses ASCII 'resumen_factico' (absence of 'resumen_fáctico').
6. Direct execution of Python code extracted verbatim from plan.md Section 8 and Section 10.
"""

import hashlib
import re
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

import pytest
from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator

# ============================================================================
# Re-created Reference Models from plan.md Section 8
# ============================================================================


class TaxonomyCategory(str, Enum):
    """Categorías macroeconómicas canónicas según taxonomía venezolana (Prompt 7.1 y SPEC-023)."""

    GASTO_PUBLICO_PATRIA = "GASTO_PUBLICO_PATRIA"
    INTERVENCION_CAMBIARIA_BCV = "INTERVENCION_CAMBIARIA_BCV"
    POLITICA_MONETARIA_LIQUIDEZ = "POLITICA_MONETARIA_LIQUIDEZ"
    CALENDARIO_FISCAL_SENIAT = "CALENDARIO_FISCAL_SENIAT"
    REGULACION_CAMBIARIA_BANCARIA = "REGULACION_CAMBIARIA_BANCARIA"
    OPERATIVA_MERCADO_P2P = "OPERATIVA_MERCADO_P2P"
    GEOPOLITICA_PETROLERA = "GEOPOLITICA_PETROLERA"


MacroCategoryEnum = TaxonomyCategory


class SourceCredibility(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class PredictionDirection(str, Enum):
    SUBE = "SUBE"
    BAJA = "BAJA"
    ESTABLE = "ESTABLE"


class TimeframeHorizon(str, Enum):
    HORIZONTE_24_48H = "24h-48h"
    HORIZONTE_3_5D = "3-5 dias"
    HORIZONTE_SEMANAL = "semanal"


class AuditVerdictEnum(str, Enum):
    APROBADO = "APROBADO"
    CORREGIDO = "CORREGIDO"
    AJUSTADO_FAIL_CLOSED = "AJUSTADO_FAIL_CLOSED"
    RECHAZADO = "RECHAZADO"


class MacroEventItem(BaseModel):
    """Evento macroeconómico individual normalizado por el Buscador."""

    event_id: str = Field(..., description="Identificador único del evento")
    code: str = Field(..., description="Código corto del evento (ej. GP-01, IC-01)")
    categoria: TaxonomyCategory
    titulo: str = Field(..., min_length=5, max_length=150)
    resumen_factico: str = Field(
        ..., min_length=10, max_length=500, description="Resumen fáctico y objetivo"
    )
    fuente_nombre: str
    fuente_url: str | None = None
    credibilidad: SourceCredibility
    cifras_especificadas: bool = False
    monto_relevante: float | None = None
    unidad_monto: str | None = None
    timestamp_evento_utc: datetime
    base_weight: float | None = Field(None, ge=0.10, le=1.00)
    vector_direction: int | None = Field(None)
    latency_hours: float | None = Field(None, ge=0.0)
    half_life_hours: float | None = Field(None, gt=0.0)


class MacroContextPayload(BaseModel):
    """Colección de contexto macroeconómico enviada al Predictor."""

    timestamp_extraccion: datetime
    eventos: list[MacroEventItem]
    tasa_p2p_actual: float = Field(gt=0.0)
    tasa_bcv_actual: float = Field(gt=0.0)
    brecha_cambiaria_porcentaje: float
    fuentes_consultadas: list[str]


MacroContextCollection = MacroContextPayload


class AuditMetadata(BaseModel):
    """Metadatos de auditoría y trazabilidad criptográfica."""

    predictor_model: str
    reviewer_model: str
    cross_family_verified: bool = True
    prev_hash: str
    prediction_hash: str
    timestamp_utc: datetime
    execution_duration_ms: int


class FinalUSDTPrediction(BaseModel):
    """Predicción final consolidada, auditada y lista para difusión."""

    id: str
    veredicto: AuditVerdictEnum
    direccion: PredictionDirection
    lapso_estimado: TimeframeHorizon
    confiabilidad_porcentaje: float = Field(ge=0.0, le=100.0)
    justificacion_auditada: str
    factores_clave: list[str]
    riesgos_invalidacion: list[str]
    metadata: AuditMetadata

    @field_validator("confiabilidad_porcentaje")
    @classmethod
    def validar_confianza_maxima_si_corregido(cls, v: float, info: ValidationInfo) -> float:
        """Acota la confiabilidad a un máximo de 75.0% si el veredicto es CORREGIDO o AJUSTADO_FAIL_CLOSED."""
        if v > 100.0 or v < 0.0:
            raise ValueError("La confiabilidad debe estar entre 0.0 y 100.0")

        if info.data and "veredicto" in info.data:
            veredicto = info.data["veredicto"]
            veredicto_str = veredicto.value if hasattr(veredicto, "value") else str(veredicto)

            if veredicto_str in ("CORREGIDO", "AJUSTADO_FAIL_CLOSED") and v > 75.0:
                return 75.0

        return v


def compute_prediction_hash(
    prev_hash: str,
    timestamp_iso: str,
    direction: str,
    timeframe: str,
    confidence: float,
    model: str,
    justification: str,
) -> str:
    """Calcula el hash criptográfico SHA-256 de la cadena canónica pipe-delimited."""
    conf_str = f"{float(confidence):.2f}"
    clean_model = model.strip().replace("|", "/")
    clean_just = justification.strip().replace("|", "/")
    canonical_payload = (
        f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{conf_str}|{clean_model}|{clean_just}"
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


# ============================================================================
# Empirical Tests
# ============================================================================


class TestTaxonomyCategoryRemediation:
    """Challenge 1: TaxonomyCategory enum validation against Prompt 7.1."""

    PROMPT_CATEGORIES: ClassVar[list[str]] = [
        "GASTO_PUBLICO_PATRIA",
        "INTERVENCION_CAMBIARIA_BCV",
        "POLITICA_MONETARIA_LIQUIDEZ",
        "CALENDARIO_FISCAL_SENIAT",
        "REGULACION_CAMBIARIA_BANCARIA",
        "OPERATIVA_MERCADO_P2P",
        "GEOPOLITICA_PETROLERA",
    ]

    def test_instantiation_of_all_7_prompt_categories(self):
        """All 7 prompt categories must instantiate without ValidationError."""
        for cat in self.PROMPT_CATEGORIES:
            item = MacroEventItem(
                event_id=f"EVT-{cat}-001",
                code="GP-01",
                categoria=cat,  # Pass raw string as LLM JSON would
                titulo=f"Evento de prueba para {cat}",
                resumen_factico="Resumen fáctico verificado con más de 10 caracteres",
                fuente_nombre="BCV Portal",
                credibilidad=SourceCredibility.ALTA,
                timestamp_evento_utc=datetime.now(UTC),
            )
            assert item.categoria == TaxonomyCategory(cat)
            assert item.categoria.value == cat

    def test_macro_category_enum_alias(self):
        """MacroCategoryEnum must be an alias of TaxonomyCategory for backwards compatibility."""
        assert MacroCategoryEnum is TaxonomyCategory
        for cat in self.PROMPT_CATEGORIES:
            assert MacroCategoryEnum(cat) == TaxonomyCategory(cat)

    def test_invalid_category_rejection(self):
        """Old incorrect category names or arbitrary strings must raise ValidationError."""
        legacy_invalid = [
            "PAGO_PATRIA_NOMINA",  # Old name from initial draft
            "INTERVENCION_BCV",  # Old name from initial draft
            "LIQUIDEZ_MONETARIA_M2",  # Old name
            "FACTORES_ESTACIONALES_TRIBUTARIOS",  # Old name
            "POLITICA_SANCIONES",  # Old name
            "CATEGORIA_INVENTADA",
        ]
        for invalid_cat in legacy_invalid:
            with pytest.raises(ValidationError):
                MacroEventItem(
                    event_id="EVT-FAIL-001",
                    code="GP-01",
                    categoria=invalid_cat,
                    titulo="Evento inválido",
                    resumen_factico="Resumen fáctico verificado de longitud válida",
                    fuente_nombre="Desconocida",
                    credibilidad=SourceCredibility.BAJA,
                    timestamp_evento_utc=datetime.now(UTC),
                )

    def test_prompt_7_1_text_matches_enum_in_plan_md(self):
        """Empirically extract prompt 7.1 from plan.md and check 100% equivalence."""
        plan_path = Path(".specify/specs/023-ai-market-predictor/plan.md")
        content = plan_path.read_text(encoding="utf-8")

        prompt_match = re.search(r"### 7\.1 Rol 1.*?\n(.*?)\n### 7\.2 Rol 2", content, re.DOTALL)
        assert prompt_match, "Could not find Section 7.1 in plan.md"
        prompt_text = prompt_match.group(1)

        extracted_cats = re.findall(r"-\s+([A-Z0-9_]+):", prompt_text)
        assert len(extracted_cats) == 7
        assert set(extracted_cats) == set(self.PROMPT_CATEGORIES)
        enum_values = {e.value for e in TaxonomyCategory}
        assert set(extracted_cats) == enum_values


class TestDelimiterCollisionSHA256:
    """Challenge 2: SHA-256 pre-image delimiter collision resistance."""

    def test_boundary_bleed_collision_resistance(self):
        """Verify that pipe delimiters prevent boundary-bleed between adjacent fields."""
        prev = "0" * 64
        ts = "2026-11-17T00:00:00Z"
        conf = 85.0
        model = "claude-3-5-sonnet"
        just = "Analisis macroeconomico riguroso"

        # Case A: direction='SUB', timeframe='E24h'
        h_a = compute_prediction_hash(prev, ts, "SUB", "E24h", conf, model, just)

        # Case B: direction='SUBE', timeframe='24h'
        h_b = compute_prediction_hash(prev, ts, "SUBE", "24h", conf, model, just)

        # Under un-delimited concatenation, h_a == h_b. Under pipe-delimited, h_a != h_b.
        assert h_a != h_b, "CRITICAL: Hash collision detected between ('SUB', 'E24h') and ('SUBE', '24h')!"

    def test_confidence_decimal_formatting_collision_resistance(self):
        """Verify fixed 2-decimal formatting prevents number-boundary collisions."""
        prev = "0" * 64
        ts = "2026-11-17T00:00:00Z"
        direction = "SUBE"
        timeframe = "24h-48h"

        # If confidence 7.5 vs 75.0:
        h1 = compute_prediction_hash(prev, ts, direction, timeframe, 7.5, "model", "just")
        h2 = compute_prediction_hash(prev, ts, direction, timeframe, 75.0, "model", "just")
        assert h1 != h2

    def test_pipe_sanitization_in_model_and_justification(self):
        """Verify that any '|' injected into model or justification is sanitized to '/'."""
        prev = "0" * 64
        ts = "2026-11-17T00:00:00Z"
        malicious_model = "gpt-4o|SUBE|24h-48h|99.00|injected"
        h = compute_prediction_hash(
            prev, ts, "ESTABLE", "semanal", 50.0, malicious_model, "normal justification"
        )
        assert len(h) == 64
        # Verify sanitization in canonical string
        conf_str = f"{50.0:.2f}"
        clean_model = malicious_model.strip().replace("|", "/")
        canonical_str = f"{prev}|{ts}|ESTABLE|semanal|{conf_str}|{clean_model}|normal justification"
        assert canonical_str.count("|") == 6, "Canonical string must contain exactly 6 pipe delimiters!"
        assert hashlib.sha256(canonical_str.encode("utf-8")).hexdigest() == h

    def test_chain_tamper_detection(self):
        """Verify that tampering with any block breaks all downstream hashes."""
        chain = []
        prev = "0" * 64
        for i in range(10):
            ts = f"2026-11-17T0{i:02d}:00:00Z"
            d = "SUBE" if i % 2 == 0 else "BAJA"
            h = compute_prediction_hash(prev, ts, d, "24h-48h", 70.0 + i, "model", f"justification {i}")
            chain.append({"prev": prev, "ts": ts, "d": d, "h": h})
            prev = h

        # Verify chain integrity
        for i in range(1, 10):
            assert chain[i]["prev"] == chain[i - 1]["h"]

        # Tamper with block 3 direction
        tampered_h3 = compute_prediction_hash(
            chain[3]["prev"], chain[3]["ts"], "ESTABLE", "24h-48h", 73.0, "model", "justification 3"
        )
        assert tampered_h3 != chain[3]["h"]
        # Downstream link broken
        assert tampered_h3 != chain[4]["prev"]


class TestContractEnumsConsistency:
    """Challenge 3: Verify contract enums across tasks.md, plan.md, and PROJECT.md."""

    def test_tasks_md_uses_spanish_enums(self):
        """tasks.md must NOT contain legacy MarketDirection or TimeHorizon enums."""
        tasks_path = Path(".specify/specs/023-ai-market-predictor/tasks.md")
        content = tasks_path.read_text(encoding="utf-8")

        # Must not contain legacy English enums
        assert "MarketDirection" not in content, "Legacy MarketDirection found in tasks.md"
        assert "TimeHorizon" not in content, "Legacy TimeHorizon found in tasks.md"
        assert "BULLISH" not in content, "Legacy BULLISH found in tasks.md"
        assert "BEARISH" not in content, "Legacy BEARISH found in tasks.md"

        # Must contain harmonized contracts
        assert "PredictionDirection" in content
        assert "TimeframeHorizon" in content
        assert "AuditVerdictEnum" in content
        assert "TaxonomyCategory" in content
        assert "MacroContextPayload" in content
        assert "resumen_factico" in content

    def test_tasks_md_atomic_task_count(self):
        """tasks.md must maintain exactly 26 atomic tasks (T23.1 to T23.26)."""
        tasks_path = Path(".specify/specs/023-ai-market-predictor/tasks.md")
        content = tasks_path.read_text(encoding="utf-8")

        task_matches = re.findall(r"- \[(?: |x)\] (T23\.\d+):", content)
        assert len(task_matches) == 26
        assert task_matches[0] == "T23.1"
        assert task_matches[-1] == "T23.26"

    def test_plan_md_enum_values_match_tasks_md(self):
        """plan.md and tasks.md must agree on enum values."""
        plan_path = Path(".specify/specs/023-ai-market-predictor/plan.md")
        plan_content = plan_path.read_text(encoding="utf-8")

        # PredictionDirection values: SUBE, BAJA, ESTABLE
        for val in ["SUBE", "BAJA", "ESTABLE"]:
            assert f'"{val}"' in plan_content

        # TimeframeHorizon values: "24h-48h", "3-5 dias", "semanal"
        for val in ["24h-48h", "3-5 dias", "semanal"]:
            assert f'"{val}"' in plan_content

        # AuditVerdictEnum values: APROBADO, CORREGIDO, AJUSTADO_FAIL_CLOSED, RECHAZADO
        for val in ["APROBADO", "CORREGIDO", "AJUSTADO_FAIL_CLOSED", "RECHAZADO"]:
            assert f'"{val}"' in plan_content


class TestConfidenceCappingValidator:
    """Challenge 4: Confidence capping validator for CORREGIDO / AJUSTADO_FAIL_CLOSED."""

    def _make_prediction(self, veredicto: Any, confidence: float) -> FinalUSDTPrediction:
        return FinalUSDTPrediction(
            id="PRED-202611-001",
            veredicto=veredicto,
            direccion=PredictionDirection.SUBE,
            lapso_estimado=TimeframeHorizon.HORIZONTE_24_48H,
            confiabilidad_porcentaje=confidence,
            justificacion_auditada="Justificación auditada de longitud suficiente para pasar validación",
            factores_clave=["Inyección de liquidez M2"],
            riesgos_invalidacion=["Intervención BCV no programada"],
            metadata=AuditMetadata(
                predictor_model="deepseek-r1",
                reviewer_model="claude-3-5-sonnet",
                cross_family_verified=True,
                prev_hash="0" * 64,
                prediction_hash="a" * 64,
                timestamp_utc=datetime.now(UTC),
                execution_duration_ms=450,
            ),
        )

    def test_capping_when_corregido_and_confidence_above_75(self):
        """When veredicto is CORREGIDO and confidence > 75%, it must be capped at 75.0%."""
        p = self._make_prediction(AuditVerdictEnum.CORREGIDO, 95.0)
        assert p.confiabilidad_porcentaje == 75.0

    def test_capping_when_ajustado_fail_closed_and_confidence_above_75(self):
        """When veredicto is AJUSTADO_FAIL_CLOSED and confidence > 75%, it must be capped at 75.0%."""
        p = self._make_prediction(AuditVerdictEnum.AJUSTADO_FAIL_CLOSED, 88.0)
        assert p.confiabilidad_porcentaje == 75.0

    def test_capping_with_string_enum_values(self):
        """Validator must handle string literal veredicto values without failing."""
        p1 = self._make_prediction("CORREGIDO", 92.5)
        assert p1.confiabilidad_porcentaje == 75.0

        p2 = self._make_prediction("AJUSTADO_FAIL_CLOSED", 82.0)
        assert p2.confiabilidad_porcentaje == 75.0

    def test_no_capping_when_confidence_already_below_75(self):
        """When confidence <= 75%, it must not be altered for CORREGIDO."""
        p = self._make_prediction(AuditVerdictEnum.CORREGIDO, 65.0)
        assert p.confiabilidad_porcentaje == 65.0

        p_exact = self._make_prediction(AuditVerdictEnum.CORREGIDO, 75.0)
        assert p_exact.confiabilidad_porcentaje == 75.0

    def test_no_capping_when_aprobado(self):
        """When veredicto is APROBADO, high confidence must be preserved."""
        p = self._make_prediction(AuditVerdictEnum.APROBADO, 98.0)
        assert p.confiabilidad_porcentaje == 98.0

    def test_no_capping_when_rechazado(self):
        """When veredicto is RECHAZADO, confidence is not capped by this validator."""
        p = self._make_prediction(AuditVerdictEnum.RECHAZADO, 90.0)
        assert p.confiabilidad_porcentaje == 90.0

    def test_out_of_bounds_confidence_rejection(self):
        """Confidence outside 0.0 to 100.0 must raise ValidationError."""
        with pytest.raises(ValidationError):
            self._make_prediction(AuditVerdictEnum.APROBADO, 105.0)

        with pytest.raises(ValidationError):
            self._make_prediction(AuditVerdictEnum.CORREGIDO, -5.0)


class TestASCIIFieldValidation:
    """Challenge 5: Verify ASCII field 'resumen_factico' in MacroEventItem."""

    def test_macro_event_item_has_ascii_resumen_factico(self):
        """MacroEventItem model must have attribute 'resumen_factico' and NOT 'resumen_fáctico'."""
        item = MacroEventItem(
            event_id="EVT-001",
            code="IC-01",
            categoria=TaxonomyCategory.INTERVENCION_CAMBIARIA_BCV,
            titulo="Intervención Regular BCV",
            resumen_factico="Inyección de $60M en mesas de cambio según reporte oficial",
            fuente_nombre="BCV",
            credibilidad=SourceCredibility.ALTA,
            timestamp_evento_utc=datetime.now(UTC),
        )
        assert hasattr(item, "resumen_factico")
        assert not hasattr(item, "resumen_fáctico")
        assert item.resumen_factico == "Inyección de $60M en mesas de cambio según reporte oficial"

    def test_resumen_factico_length_validation(self):
        """resumen_factico must enforce min_length=10 and max_length=500."""
        # Too short (<10 chars)
        with pytest.raises(ValidationError):
            MacroEventItem(
                event_id="EVT-001",
                code="IC-01",
                categoria=TaxonomyCategory.INTERVENCION_CAMBIARIA_BCV,
                titulo="Intervención",
                resumen_factico="Corto",
                fuente_nombre="BCV",
                credibilidad=SourceCredibility.ALTA,
                timestamp_evento_utc=datetime.now(UTC),
            )

        # Valid length
        item = MacroEventItem(
            event_id="EVT-001",
            code="IC-01",
            categoria=TaxonomyCategory.INTERVENCION_CAMBIARIA_BCV,
            titulo="Intervención",
            resumen_factico="A" * 500,
            fuente_nombre="BCV",
            credibilidad=SourceCredibility.ALTA,
            timestamp_evento_utc=datetime.now(UTC),
        )
        assert len(item.resumen_factico) == 500

        # Too long (>500 chars)
        with pytest.raises(ValidationError):
            MacroEventItem(
                event_id="EVT-001",
                code="IC-01",
                categoria=TaxonomyCategory.INTERVENCION_CAMBIARIA_BCV,
                titulo="Intervención",
                resumen_factico="A" * 501,
                fuente_nombre="BCV",
                credibilidad=SourceCredibility.ALTA,
                timestamp_evento_utc=datetime.now(UTC),
            )

    def test_absence_of_accented_identifier_in_specs(self):
        """resumen_fáctico must be absent from both plan.md and tasks.md."""
        for path_str in [
            ".specify/specs/023-ai-market-predictor/plan.md",
            ".specify/specs/023-ai-market-predictor/tasks.md",
        ]:
            content = Path(path_str).read_text(encoding="utf-8")
            assert "resumen_fáctico" not in content, f"Found 'resumen_fáctico' in {path_str}"


class TestPlanMdVerbatimCodeExecution:
    """Challenge 6: Direct extraction and execution of Python code from plan.md."""

    def test_plan_md_section_8_and_10_execution(self):
        """Python blocks in plan.md Section 8 and Section 10 must execute cleanly without error."""
        plan_content = Path(".specify/specs/023-ai-market-predictor/plan.md").read_text(encoding="utf-8")

        # Extract Section 8 code
        idx8 = plan_content.find("## 8. Esquemas Formales Pydantic v2")
        code8_start = plan_content.find("```python", idx8) + len("```python\n")
        code8_end = plan_content.find("```", code8_start)
        code8 = plan_content[code8_start:code8_end]

        ns: dict[str, Any] = {}
        exec(code8, ns)  # noqa: S102

        # Verify symbols created
        assert "TaxonomyCategory" in ns
        assert "MacroEventItem" in ns
        assert "FinalUSDTPrediction" in ns

        # Test FinalUSDTPrediction confidence capping with extracted class
        ExtractedFinal = ns["FinalUSDTPrediction"]
        ExtractedVerdict = ns["AuditVerdictEnum"]
        ExtractedDir = ns["PredictionDirection"]
        ExtractedTime = ns["TimeframeHorizon"]
        ExtractedMeta = ns["AuditMetadata"]

        meta = ExtractedMeta(
            predictor_model="deepseek-r1",
            reviewer_model="claude-3-5-sonnet",
            cross_family_verified=True,
            prev_hash="0" * 64,
            prediction_hash="b" * 64,
            timestamp_utc=datetime.now(UTC),
            execution_duration_ms=500,
        )

        pred_corregido = ExtractedFinal(
            id="PRED-001",
            veredicto=ExtractedVerdict.CORREGIDO,
            direccion=ExtractedDir.SUBE,
            lapso_estimado=ExtractedTime.HORIZONTE_24_48H,
            confiabilidad_porcentaje=92.0,
            justificacion_auditada="Justificación válida de prueba con longitud suficiente",
            factores_clave=["F1"],
            riesgos_invalidacion=["R1"],
            metadata=meta,
        )
        assert pred_corregido.confiabilidad_porcentaje == 75.0, (
            f"Extracted class failed capping! Expected 75.0, got {pred_corregido.confiabilidad_porcentaje}"
        )

        # Extract Section 10 hash function
        idx10 = plan_content.find("## 10. Persistencia, Trazabilidad SHA-256")
        hash_code_start = plan_content.find("```python\nimport hashlib", idx10) + len("```python\n")
        hash_code_end = plan_content.find("```", hash_code_start)
        hash_code = plan_content[hash_code_start:hash_code_end]

        exec(hash_code, ns)  # noqa: S102
        assert "compute_prediction_hash" in ns
        extracted_hash_fn = ns["compute_prediction_hash"]

        h = extracted_hash_fn("0" * 64, "2026-11-17T00:00:00Z", "SUBE", "24h-48h", 75.0, "claude", "just")
        assert len(h) == 64
