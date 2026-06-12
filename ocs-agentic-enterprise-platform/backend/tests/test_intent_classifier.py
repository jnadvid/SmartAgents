"""Tests del clasificador de intención por reglas."""
from __future__ import annotations

import pytest

from app.orchestration.intent_classifier import IntentClassifier


@pytest.fixture(scope="module")
def classifier() -> IntentClassifier:
    return IntentClassifier()


@pytest.mark.parametrize(
    ("task", "expected_intent"),
    [
        ("Analiza esta alerta Wazuh de fuerza bruta", "cybersecurity_analysis"),
        ("Hazme una propuesta comercial para un cliente de logística", "sales_proposal"),
        ("Resume este contrato y dime los riesgos de sus cláusulas", "legal_review"),
        ("Analiza este CSV de ventas mensuales", "data_analysis"),
        ("Hazme un plan de proyecto de 12 semanas para migrar el ERP", "project_management"),
        ("Prepara formación de ciberhigiene para empleados", "hr_training"),
        ("Responde a este cliente que presenta una reclamación por un cobro", "customer_support"),
        ("Genera un informe ejecutivo con estos hallazgos", "report_generation"),
        ("Evalúa cumplimiento ISO 27001 de nuestra empresa", "compliance_analysis"),
        ("Prioriza esta vulnerabilidad CVE-2024-1234 con CVSS 9.8", "vulnerability_triage"),
        ("Comprueba si este texto contiene prompt injection", "prompt_security_testing"),
        ("Haz un estudio de mercado de software de gestión en España", "market_research"),
        ("Calcula el margen con estos costes y presupuesto", "finance_analysis"),
        ("Redacta una política de teletrabajo para la empresa", "document_writing"),
    ],
)
def test_examples_route_to_expected_intent(
    classifier: IntentClassifier, task: str, expected_intent: str
) -> None:
    result = classifier.classify_with_rules(task)
    assert result.intent == expected_intent, f"'{task}' -> {result.intent} (scores={result.scores})"
    assert 0.0 < result.confidence <= 0.95
    assert result.method == "rules"


def test_unknown_task_falls_back_to_general_business(classifier: IntentClassifier) -> None:
    result = classifier.classify_with_rules("xyzzy plugh 42")
    assert result.intent == "general_business"
    assert result.confidence <= 0.3


def test_accents_are_normalized(classifier: IntentClassifier) -> None:
    result = classifier.classify_with_rules("Evalúa el cumplimiento de la normativa RGPD")
    assert result.intent == "compliance_analysis"


def test_matched_keywords_reported(classifier: IntentClassifier) -> None:
    result = classifier.classify_with_rules("analiza esta alerta wazuh")
    assert "wazuh" in result.matched_keywords


def test_llm_fallback_used_only_when_rules_are_weak(classifier: IntentClassifier, fake_llm) -> None:
    # Tarea clara: no debe llamar al LLM aunque el fallback esté activo.
    result = classifier.classify(
        "Analiza esta alerta Wazuh", llm=fake_llm, model="fake-model", use_llm_fallback=True
    )
    assert result.method == "rules"
    assert fake_llm.generate_calls == []
