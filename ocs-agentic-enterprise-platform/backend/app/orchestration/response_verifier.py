"""ResponseVerifier: validación de la respuesta final del agente.

Comprobaciones duras (fallan la verificación):
- respuesta vacía o demasiado corta
- presencia de patrones de secretos

Comprobaciones blandas (generan issues que penalizan la confianza):
- secciones requeridas ausentes
- citas a herramientas no ejecutadas o documentos no aportados
- falta de declaración de incertidumbre con entradas pobres
- falta de recomendaciones cuando el formato las exige
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.agents.base import BaseAgent
from app.security.sanitization import find_secret_patterns, normalize_for_matching

_MIN_OUTPUT_CHARS = 40
_SHORT_TASK_CHARS = 200

_TOOL_CITATION = re.compile(r"\[(?:herramienta|tool)\s*:\s*([a-z0-9_\-]+)\]", re.IGNORECASE)
_DOC_FABRICATION = re.compile(
    r"(?i)(seg[uú]n el documento (adjunto|proporcionado|subido)|"
    r"en el documento (adjunto|proporcionado|subido)|according to the (attached|provided) document)"
)
_UNCERTAINTY = re.compile(
    r"(?i)(incertidumbre|no dispongo|falta(n)? (datos|informaci[oó]n)|no se especifica|"
    r"sin datos suficientes|limitaci[oó]n|no puedo verificar|por confirmar|supuesto)"
)


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class VerificationReport:
    passed: bool
    checks: list[VerificationCheck] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    sections_ratio: float = 1.0


class ResponseVerifier:
    """Valida la salida del agente antes de entregarla al usuario."""

    def verify(
        self,
        output: str,
        agent: BaseAgent,
        task: str,
        tools_used: list[str],
        documents_used: int,
    ) -> VerificationReport:
        checks: list[VerificationCheck] = []
        issues: list[str] = []
        hard_failure = False

        # 1. No vacía / longitud mínima (dura)
        stripped = (output or "").strip()
        non_empty = len(stripped) >= _MIN_OUTPUT_CHARS
        checks.append(
            VerificationCheck(
                name="respuesta_no_vacia",
                passed=non_empty,
                detail=f"{len(stripped)} caracteres (mínimo {_MIN_OUTPUT_CHARS}).",
            )
        )
        if not non_empty:
            hard_failure = True
            issues.append("La respuesta está vacía o es demasiado corta.")

        # 2. Sin secretos (dura)
        secret_hits = find_secret_patterns(stripped)
        checks.append(
            VerificationCheck(
                name="sin_secretos",
                passed=not secret_hits,
                detail="Sin patrones de secretos." if not secret_hits else f"Patrones: {', '.join(secret_hits)}",
            )
        )
        if secret_hits:
            hard_failure = True
            issues.append("La respuesta contiene posibles secretos/credenciales.")

        # 3. Secciones requeridas (blanda)
        normalized_output = normalize_for_matching(stripped)
        required = agent.output_format
        present = [
            section
            for section in required
            if normalize_for_matching(section) in normalized_output
        ]
        ratio = len(present) / len(required) if required else 1.0
        sections_ok = ratio >= 0.6
        checks.append(
            VerificationCheck(
                name="formato_secciones",
                passed=sections_ok,
                detail=f"{len(present)}/{len(required)} secciones requeridas presentes.",
            )
        )
        if not sections_ok:
            missing = [s for s in required if s not in present]
            issues.append(f"Faltan secciones requeridas: {', '.join(missing[:5])}.")

        # 4. Citas de herramientas no ejecutadas (blanda)
        cited_tools = {match.lower() for match in _TOOL_CITATION.findall(stripped)}
        fabricated_tools = sorted(cited_tools - {name.lower() for name in tools_used})
        checks.append(
            VerificationCheck(
                name="evidencia_herramientas",
                passed=not fabricated_tools,
                detail="Citas de herramientas consistentes."
                if not fabricated_tools
                else f"Cita herramientas no ejecutadas: {', '.join(fabricated_tools)}",
            )
        )
        if fabricated_tools:
            issues.append(
                f"La respuesta cita herramientas que no se ejecutaron: {', '.join(fabricated_tools)}."
            )

        # 5. Referencias a documentos inexistentes (blanda)
        doc_fabrication = bool(_DOC_FABRICATION.search(stripped)) and documents_used == 0
        checks.append(
            VerificationCheck(
                name="evidencia_documentos",
                passed=not doc_fabrication,
                detail="Referencias documentales consistentes."
                if not doc_fabrication
                else "Referencia a documentos aportados, pero no se usó ninguno.",
            )
        )
        if doc_fabrication:
            issues.append("La respuesta alude a documentos aportados sin que se usara ninguno.")

        # 6. Incertidumbre declarada con entrada corta (blanda)
        uncertainty_declared = bool(_UNCERTAINTY.search(stripped))
        needs_uncertainty = len((task or "").strip()) < _SHORT_TASK_CHARS
        uncertainty_ok = uncertainty_declared or not needs_uncertainty
        checks.append(
            VerificationCheck(
                name="incertidumbre_declarada",
                passed=uncertainty_ok,
                detail="Incertidumbre declarada."
                if uncertainty_declared
                else ("No requerida (entrada amplia)." if uncertainty_ok else "Entrada corta sin declaración de incertidumbre."),
            )
        )
        if not uncertainty_ok:
            issues.append("Entrada con poca información y sin declaración de incertidumbre.")

        # 7. Recomendaciones presentes si el formato las exige (blanda)
        requires_recommendations = any(
            "recomendacion" in normalize_for_matching(section) for section in required
        )
        has_recommendations = "recomendacion" in normalized_output
        recommendations_ok = has_recommendations or not requires_recommendations
        checks.append(
            VerificationCheck(
                name="recomendaciones",
                passed=recommendations_ok,
                detail="Incluye recomendaciones." if has_recommendations else "No requeridas." if recommendations_ok else "Faltan recomendaciones requeridas.",
            )
        )
        if not recommendations_ok:
            issues.append("El formato exige recomendaciones y no se encontraron.")

        return VerificationReport(
            passed=not hard_failure,
            checks=checks,
            issues=issues,
            sections_ratio=round(ratio, 2),
        )
