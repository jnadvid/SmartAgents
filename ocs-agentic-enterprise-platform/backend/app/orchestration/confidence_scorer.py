"""ConfidenceScorer: confianza aproximada de una ejecución.

Heurística transparente y auditable (el desglose se guarda en el
Chain-of-Work). No es una probabilidad calibrada: es un indicador
operativo para que el usuario sepa cuánto revisar la salida.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.orchestration.response_verifier import VerificationReport


@dataclass(frozen=True)
class ConfidenceReport:
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class ConfidenceScorer:
    """Calcula un score 0.05-0.95 a partir de factores observables."""

    BASE = 0.50

    def score(
        self,
        task_chars: int,
        tools_succeeded: int,
        tools_failed: int,
        documents_used: int,
        verification: VerificationReport,
        uncertainty_declared: bool,
        output_chars: int,
    ) -> ConfidenceReport:
        breakdown: dict[str, float] = {"base": self.BASE}
        notes: list[str] = []

        # Completitud de la entrada
        if task_chars >= 800:
            breakdown["entrada_completa"] = 0.10
        elif task_chars >= 200:
            breakdown["entrada_completa"] = 0.05
        else:
            breakdown["entrada_completa"] = -0.05
            notes.append("Entrada breve: poco contexto para el agente.")

        # Evidencia: herramientas y documentos
        breakdown["herramientas_ok"] = min(0.15, 0.05 * tools_succeeded)
        if tools_failed:
            breakdown["herramientas_fallidas"] = -min(0.15, 0.05 * tools_failed)
            notes.append(f"{tools_failed} herramienta(s) fallaron o no estaban disponibles.")
        if documents_used:
            breakdown["evidencia_documental"] = 0.05

        # Validación de la respuesta
        if verification.passed:
            breakdown["verificacion"] = 0.10
        else:
            breakdown["verificacion"] = -0.25
            notes.append("La verificación de la respuesta falló.")
        soft_issues = len(verification.issues) if verification.passed else max(0, len(verification.issues) - 1)
        if soft_issues:
            breakdown["issues_blandos"] = -min(0.16, 0.04 * soft_issues)
            notes.append(f"{soft_issues} aviso(s) del verificador.")

        # Consistencia de la salida
        breakdown["estructura_salida"] = round(0.10 * verification.sections_ratio, 3)
        if output_chars < 200:
            breakdown["salida_corta"] = -0.05
            notes.append("Salida corta para el formato requerido.")

        # Honestidad epistémica: declarar incertidumbre suma
        if uncertainty_declared:
            breakdown["incertidumbre_declarada"] = 0.05

        raw = sum(breakdown.values())
        final = max(0.05, min(0.95, raw))
        return ConfidenceReport(
            score=round(final, 2),
            breakdown={key: round(value, 3) for key, value in breakdown.items()},
            notes=notes,
        )
