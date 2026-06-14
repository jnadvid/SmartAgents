"""Clasificador de intención de tareas.

Fase 1 (siempre): reglas por palabras clave ponderadas (ES/EN, sin acentos).
Fase 2 (opcional): si la confianza de las reglas es baja y hay LLM
disponible, se pide a Ollama que elija una categoría del catálogo cerrado.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.llm.base import BaseLLMProvider, LLMProviderError
from app.security.sanitization import normalize_for_matching

logger = logging.getLogger(__name__)

INTENT_CATEGORIES: tuple[str, ...] = (
    "general_business",
    "document_writing",
    "document_analysis",
    "data_analysis",
    "legal_review",
    "sales_proposal",
    "market_research",
    "finance_analysis",
    "project_management",
    "hr_training",
    "customer_support",
    "report_generation",
    "cybersecurity_analysis",
    "compliance_analysis",
    "vulnerability_triage",
    "prompt_security_testing",
    # Programación
    "software_architecture",
    "backend_development",
    "frontend_development",
    "code_review",
    "software_testing",
    "devops_ci_cd",
    "database_engineering",
    "technical_documentation",
    # Ciberseguridad (especializada)
    "incident_response",
    "threat_intelligence",
    "application_security",
    # Psicología
    "organizational_psychology",
    "ux_psychology",
    "wellbeing",
    # Negocio / operaciones (especializado)
    "business_strategy",
    "operations_management",
    # RRHH (especializado)
    "recruitment",
    "people_operations",
    # Compliance (especializado)
    "data_protection",
    # Proyectos (especializado)
    "agile_coaching",
)

# Palabras clave normalizadas (minúsculas, sin acentos).
# strong = señal específica del dominio (peso 3); weak = señal genérica (peso 1).
INTENT_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "document_writing": {
        "strong": [
            "redacta", "escribe un", "escribeme", "borrador de", "redactar",
            "politica de empresa", "procedimiento interno", "redaccion de",
            "email para", "correo para", "carta para", "comunicado",
        ],
        "weak": ["documento", "texto", "email", "correo", "plantilla"],
    },
    "document_analysis": {
        "strong": [
            "analiza este documento", "audita este documento", "revisa este documento",
            "auditoria documental", "resume este documento", "analiza el documento",
            "coherencia del documento", "revisa el acta",
        ],
        "weak": ["acta", "anexo"],
    },
    "data_analysis": {
        "strong": [
            "csv", "analiza estos datos", "dataset", "tabla de datos", "hoja de calculo",
            "analisis de datos", "estadisticas de", "analiza esta tabla", "tsv",
        ],
        "weak": ["datos", "tabla", "kpi", "metricas", "excel", "tendencia"],
    },
    "legal_review": {
        "strong": [
            "contrato", "clausula", "nda", "acuerdo de confidencialidad",
            "terminos y condiciones", "revision legal", "juridico", "anexo contractual",
        ],
        "weak": ["legal", "obligaciones", "jurisdiccion", "firma"],
    },
    "sales_proposal": {
        "strong": [
            "propuesta comercial", "oferta comercial", "cotizacion", "presupuesto para el cliente",
            "argumentario de venta", "email de venta", "pitch", "propuesta economica",
        ],
        "weak": ["venta", "propuesta", "oferta", "comercial", "lead", "oportunidad"],
    },
    "market_research": {
        "strong": [
            "estudio de mercado", "analisis de mercado", "investigacion de mercado",
            "competidores", "competencia", "posicionamiento", "benchmarking", "sector de",
        ],
        "weak": ["mercado", "tendencias", "nicho", "segmento"],
    },
    "finance_analysis": {
        "strong": [
            "presupuesto", "margen", "rentabilidad", "facturacion", "flujo de caja",
            "cashflow", "costes", "costos", "punto de equilibrio", "roi", "tesoreria",
            "cuenta de resultados", "escenario financiero",
        ],
        "weak": ["finanzas", "financiero", "ingresos", "gastos", "precio"],
    },
    "project_management": {
        "strong": [
            "plan de proyecto", "cronograma", "hitos", "gantt", "planificacion del proyecto",
            "hoja de ruta del proyecto", "gestion del proyecto", "sprint",
        ],
        "weak": ["proyecto", "tareas", "fases", "entregables", "deadline"],
    },
    "hr_training": {
        "strong": [
            "formacion", "onboarding", "plan de capacitacion", "curso para empleados",
            "material didactico", "ruta de aprendizaje", "capacitacion", "plan de acogida",
        ],
        "weak": ["empleados", "rrhh", "recursos humanos", "talento", "cuestionario"],
    },
    "customer_support": {
        "strong": [
            "responde a este cliente", "responder al cliente", "respuesta al cliente",
            "reclamacion", "queja", "ticket de soporte", "atencion al cliente",
            "cliente enfadado", "cliente molesto", "incidencia de cliente",
        ],
        "weak": ["soporte", "cliente", "respuesta", "devolucion"],
    },
    "report_generation": {
        "strong": [
            "informe ejecutivo", "resumen ejecutivo", "genera un informe", "reporte ejecutivo",
            "informe tecnico", "informe para direccion", "convierte en informe",
        ],
        "weak": ["informe", "reporte"],
    },
    "cybersecurity_analysis": {
        "strong": [
            "wazuh", "siem", "alerta de seguridad", "incidente de seguridad", "malware",
            "ransomware", "phishing", "ioc", "edr", "ids", "intrusion", "ataque",
            "fuerza bruta", "analiza esta alerta", "threat hunting", "soc",
        ],
        "weak": ["seguridad", "firewall", "log", "amenaza"],
    },
    "compliance_analysis": {
        "strong": [
            "iso 27001", "cumplimiento", "rgpd", "gdpr", "ens", "nis2", "dora",
            "soc 2", "auditoria de cumplimiento", "gap analysis", "normativa",
            "proteccion de datos", "compliance",
        ],
        "weak": ["controles", "auditoria", "marco"],
    },
    "vulnerability_triage": {
        "strong": [
            "cve-", "cvss", "vulnerabilidad", "vulnerabilidades", "parche", "parcheo",
            "nessus", "openvas", "triaje de vulnerabilidades", "exploit",
        ],
        "weak": ["patch", "escaneo"],
    },
    "prompt_security_testing": {
        "strong": [
            "prompt injection", "inyeccion de prompt", "jailbreak", "system prompt",
            "seguridad del prompt", "seguridad de prompts", "prompt malicioso",
            "robustez del prompt", "llm security",
        ],
        "weak": ["prompt"],
    },
    "general_business": {
        "strong": [
            "estrategia de negocio", "toma de decisiones", "productividad",
            "organiza mi", "plan de accion", "decision estrategica",
        ],
        "weak": ["negocio", "empresa", "reunion", "organizacion", "decision"],
    },
    # ----------------------------- Programación -----------------------------
    "software_architecture": {
        "strong": [
            "arquitectura de software", "diseno de arquitectura", "patron de diseno",
            "microservicios", "monolito", "diagrama de componentes", "adr",
            "escalabilidad del sistema", "diseno del sistema",
        ],
        "weak": ["arquitectura"],
    },
    "backend_development": {
        "strong": [
            "escribe codigo", "implementa una funcion", "api rest", "endpoint",
            "crea una clase", "funcion en python", "implementa el backend",
            "logica de negocio en", "programa una funcion",
        ],
        "weak": ["backend", "codigo", "funcion", "script", "programar"],
    },
    "frontend_development": {
        "strong": [
            "componente react", "interfaz de usuario", "maqueta la pantalla",
            "formulario web", "diseno responsive", "vue", "tailwind", "hoja de estilos",
        ],
        "weak": ["frontend", "css", "html", "ui", "boton"],
    },
    "code_review": {
        "strong": [
            "revisa este codigo", "revision de codigo", "code review", "revisa el codigo",
            "analiza este codigo", "calidad del codigo", "refactoriza", "refactor",
        ],
        "weak": ["revisar codigo", "mantenibilidad"],
    },
    "software_testing": {
        "strong": [
            "test unitario", "tests unitarios", "pruebas unitarias", "casos de prueba",
            "test de integracion", "cobertura de tests", "pytest", "genera tests",
            "plan de pruebas",
        ],
        "weak": ["testing", "qa"],
    },
    "devops_ci_cd": {
        "strong": [
            "ci/cd", "pipeline de despliegue", "github actions", "dockerfile",
            "kubernetes", "infraestructura como codigo", "terraform",
            "despliegue continuo", "integracion continua",
        ],
        "weak": ["docker", "devops", "pipeline"],
    },
    "database_engineering": {
        "strong": [
            "esquema de base de datos", "modelo de datos", "consulta sql",
            "optimiza esta consulta", "indices de base de datos", "normalizacion",
            "diseno de base de datos", "migracion de base de datos",
        ],
        "weak": ["sql", "base de datos"],
    },
    "technical_documentation": {
        "strong": [
            "documenta el codigo", "documentacion tecnica", "escribe el readme",
            "documenta la api", "docstring", "documentacion del codigo", "manual tecnico",
        ],
        "weak": ["readme"],
    },
    # ------------------------- Ciberseguridad (esp.) ------------------------
    "incident_response": {
        "strong": [
            "respuesta a incidentes", "incident response", "plan de respuesta a incidentes",
            "contencion del incidente", "dfir", "erradicacion", "recuperacion tras incidente",
            "forense digital",
        ],
        "weak": [],
    },
    "threat_intelligence": {
        "strong": [
            "inteligencia de amenazas", "threat intel", "cti", "actor de amenazas",
            "ttps", "indicadores de compromiso", "campana de amenazas", "diamond model",
        ],
        "weak": [],
    },
    "application_security": {
        "strong": [
            "seguridad de la aplicacion", "appsec", "owasp", "modelado de amenazas",
            "stride", "analisis sast", "auditoria de seguridad del codigo",
            "vulnerabilidad en el codigo", "codigo seguro",
        ],
        "weak": [],
    },
    # ------------------------------ Psicología ------------------------------
    "organizational_psychology": {
        "strong": [
            "psicologia organizacional", "clima laboral", "dinamica de equipo",
            "gestion del cambio", "motivacion del equipo", "seguridad psicologica",
            "cultura de equipo", "cohesion del equipo",
        ],
        "weak": ["motivacion", "liderazgo"],
    },
    "ux_psychology": {
        "strong": [
            "psicologia del usuario", "carga cognitiva", "sesgos cognitivos",
            "ux research", "patron oscuro", "comportamiento del usuario", "diseno persuasivo",
        ],
        "weak": ["ux", "usabilidad"],
    },
    "wellbeing": {
        "strong": [
            "bienestar laboral", "prevencion del burnout", "burnout", "gestion del estres",
            "salud laboral", "estres en el trabajo", "agotamiento profesional",
        ],
        "weak": ["bienestar"],
    },
    # ----------------------- Negocio / operaciones (esp.) -------------------
    "business_strategy": {
        "strong": [
            "estrategia competitiva", "estrategia corporativa", "ventaja competitiva",
            "modelo de negocio", "analisis dafo", "swot", "cinco fuerzas", "go to market",
        ],
        "weak": [],
    },
    "operations_management": {
        "strong": [
            "mejora de procesos", "optimizacion de procesos", "cuello de botella",
            "eficiencia operativa", "lean", "six sigma", "procedimiento operativo",
            "gestion de operaciones",
        ],
        "weak": ["operaciones"],
    },
    # ------------------------------ RRHH (esp.) -----------------------------
    "recruitment": {
        "strong": [
            "descripcion de puesto", "oferta de empleo", "proceso de seleccion",
            "entrevista de trabajo", "reclutamiento", "criterios de cribado",
            "perfil del candidato", "contratar a",
        ],
        "weak": ["seleccion", "candidato", "vacante"],
    },
    "people_operations": {
        "strong": [
            "evaluacion del desempeno", "plan de carrera", "gestion del desempeno",
            "people ops", "politica de personal", "retencion de talento", "feedback al empleado",
        ],
        "weak": [],
    },
    # --------------------------- Compliance (esp.) --------------------------
    "data_protection": {
        "strong": [
            "delegado de proteccion de datos", "dpo", "registro de actividades de tratamiento",
            "tratamiento de datos personales", "eipd", "dpia", "bases de legitimacion",
            "encargado del tratamiento",
        ],
        "weak": [],
    },
    # ---------------------------- Proyectos (esp.) --------------------------
    "agile_coaching": {
        "strong": [
            "scrum", "kanban", "agile coach", "retrospectiva", "daily standup",
            "ceremonias agiles", "refinamiento del backlog", "tablero kanban",
        ],
        "weak": ["agil", "backlog"],
    },
}

_STRONG_WEIGHT = 3
_WEAK_WEIGHT = 1
_LLM_FALLBACK_THRESHOLD = 0.55


@dataclass(frozen=True)
class IntentResult:
    """Resultado de la clasificación de intención."""

    intent: str
    confidence: float
    method: str  # "rules" | "llm" | "rules_fallback"
    matched_keywords: list[str] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)


def _keyword_matches(normalized_text: str, keyword: str) -> bool:
    if " " in keyword or "-" in keyword:
        return keyword in normalized_text
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", normalized_text) is not None


class IntentClassifier:
    """Clasificador híbrido: reglas ponderadas + fallback LLM opcional."""

    def classify_with_rules(self, task: str) -> IntentResult:
        normalized = normalize_for_matching(task or "")
        scores: dict[str, int] = {}
        matched: dict[str, list[str]] = {}

        for intent, groups in INTENT_KEYWORDS.items():
            score = 0
            hits: list[str] = []
            for keyword in groups.get("strong", []):
                if _keyword_matches(normalized, keyword):
                    score += _STRONG_WEIGHT
                    hits.append(keyword)
            for keyword in groups.get("weak", []):
                if _keyword_matches(normalized, keyword):
                    score += _WEAK_WEIGHT
                    hits.append(keyword)
            if score:
                scores[intent] = score
                matched[intent] = hits

        if not scores:
            return IntentResult(
                intent="general_business",
                confidence=0.25,
                method="rules",
                matched_keywords=[],
                scores={},
            )

        ranking = sorted(scores.items(), key=lambda kv: -kv[1])
        top_intent, top_score = ranking[0]
        second_score = ranking[1][1] if len(ranking) > 1 else 0
        margin = top_score - second_score
        confidence = min(0.95, 0.35 + 0.08 * min(top_score, 6) + 0.07 * min(margin, 4))

        return IntentResult(
            intent=top_intent,
            confidence=round(confidence, 2),
            method="rules",
            matched_keywords=matched.get(top_intent, []),
            scores=scores,
        )

    def classify_with_llm(
        self, task: str, llm: BaseLLMProvider, model: str
    ) -> IntentResult | None:
        """Clasificación avanzada con Ollama. Devuelve None si falla."""
        categories = ", ".join(INTENT_CATEGORIES)
        prompt = (
            "Clasifica la siguiente tarea empresarial en UNA única categoría del catálogo.\n"
            f"Catálogo cerrado: {categories}\n\n"
            f"Tarea: {task[:2000]}\n\n"
            'Responde SOLO con JSON válido: {"intent": "<categoria>", "confidence": <0.0-1.0>}'
        )
        try:
            result = llm.generate(
                prompt=prompt,
                model=model,
                system_prompt="Eres un clasificador estricto. Devuelves únicamente JSON válido.",
                temperature=0.0,
                max_tokens=80,
            )
        except LLMProviderError as exc:
            logger.warning("Fallback LLM de clasificación no disponible: %s", exc)
            return None

        text = result.text.strip()
        intent: str | None = None
        confidence = 0.6

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                candidate = str(data.get("intent", "")).strip()
                if candidate in INTENT_CATEGORIES:
                    intent = candidate
                raw_confidence = data.get("confidence")
                if isinstance(raw_confidence, (int, float)):
                    confidence = max(0.0, min(1.0, float(raw_confidence)))
            except (json.JSONDecodeError, TypeError, ValueError):
                intent = None

        if intent is None:
            # Último recurso: buscar el nombre de una categoría en la respuesta.
            for category in INTENT_CATEGORIES:
                if category in text:
                    intent = category
                    confidence = 0.55
                    break

        if intent is None:
            return None
        return IntentResult(intent=intent, confidence=round(confidence, 2), method="llm")

    def classify(
        self,
        task: str,
        llm: BaseLLMProvider | None = None,
        model: str | None = None,
        use_llm_fallback: bool = False,
    ) -> IntentResult:
        """Clasifica la tarea. Las reglas mandan; el LLM solo refuerza casos dudosos."""
        rules_result = self.classify_with_rules(task)
        if (
            use_llm_fallback
            and llm is not None
            and model
            and rules_result.confidence < _LLM_FALLBACK_THRESHOLD
        ):
            llm_result = self.classify_with_llm(task, llm, model)
            if llm_result is not None:
                return IntentResult(
                    intent=llm_result.intent,
                    confidence=llm_result.confidence,
                    method="llm",
                    matched_keywords=rules_result.matched_keywords,
                    scores=rules_result.scores,
                )
            return IntentResult(
                intent=rules_result.intent,
                confidence=rules_result.confidence,
                method="rules_fallback",
                matched_keywords=rules_result.matched_keywords,
                scores=rules_result.scores,
            )
        return rules_result
